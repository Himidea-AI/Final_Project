# Kakao Store 전수 수집 파이프라인 설계

- 작성일: 2026-04-20
- 담당: A1 (찬영)
- 대상 테이블: `kakao_store`, (신규 마이그레이션)

## 배경

현재 `kakao_store`는 10개 카테고리 × 약 150개 **프랜차이즈 브랜드 키워드** 검색으로만 적재되어 있다. 개인 점포가 빠져 있어 상권 밀도 분석, 경쟁 분석, ABM 시뮬레이션의 "주변 점포" 피처로 쓰기 어렵다. 위·경도까지 포함된 전수 데이터가 필요하다는 요구가 확인되었다.

`store_info` (소진공 공시) 테이블에 전수 데이터가 있으나 영업시간·실시간 상태가 없고 갱신 주기가 길다. 카카오 로컬 API를 그리드 기반으로 긁어 `kakao_store`에 합쳐 넣어, 기존 `kakao_store_hours` 파이프라인(영업시간 크롤링)과 자연스럽게 연동한다.

## 목표

1. 카카오 로컬 API를 **그리드 기반 카테고리 검색**으로 전환해 마포구 내 음식점(FD6) + 카페(CE7) 전수 수집.
2. `category_name` 파싱으로 10개 세부 카테고리(한식/중식/일식/양식/커피-음료/치킨/분식/제과/패스트푸드/호프) 자동 분류.
3. 기존 브랜드 검색 모드는 보존(`--mode=brands`), 신규 모드 `--mode=categories` 추가.
4. `kakao_store_hours`의 FK 연결을 보존하기 위해 **UPSERT** 방식으로 적재.
5. 스키마에 `is_franchise` 컬럼 추가, `brand_name`은 브랜드 매칭된 경우에만 채움.

## 비목표

- `kakao_store_hours` 수집 로직 변경 없음 (단지 더 많은 kakao_id가 잡히게 될 뿐).
- 편의점(CS2), 미용실, 약국(PM9) 등 FD6·CE7 외 카테고리는 이번 범위에서 제외.
- 마포 외 지역 확장은 범위 외 (bbox 하드코딩 유지).

## 아키텍처

```
[Grid Generator]
    ↓ (500m × 500m 셀 ~200개)
[Category Search (FD6, CE7)]
    ↓ (셀당 max 45건 제한)
[Adaptive Split]
    ↓ (45건 초과 셀은 4분할 재귀 호출)
[Dedupe by kakao_id]
    ↓
[Classifier: category_name prefix → 10 + 기타]
    ↓
[Brand Matcher: NORMALIZE_RULES]
    ↓ (매칭 → brand_name + is_franchise=true)
[UPSERT kakao_store (ON CONFLICT kakao_id DO UPDATE)]
    ↓
[CSV export (검증용)]
```

## 구성 요소

### 1. `data/pipeline/collect_kakao_stores.py` (리팩토링)

기존 단일-모드 스크립트를 두 개 모드로 분기:

- `--mode=brands` (기본값, 기존 동작 보존): BRANDS 딕셔너리 키워드 검색
- `--mode=categories` (신규): 그리드 기반 카테고리 검색

공통 헬퍼(`normalize_brand`, `extract_dong`, DB 적재)는 공유.

#### 새로 추가되는 함수

```python
def generate_grid(rect: tuple, cell_m: int = 500) -> list[tuple]:
    """bbox를 cell_m 미터 격자로 분할."""

def search_category(code: str, rect: tuple, page: int = 1) -> dict:
    """카카오 category.json 엔드포인트 호출."""

def collect_cell(code: str, rect: tuple, depth: int = 0) -> list[dict]:
    """한 셀 수집, is_end=false && page=3 도달시 4분할 재귀."""

def classify_category(category_name: str) -> str:
    """카카오 category_name → 10개 + '기타' 매핑."""

def upsert_stores(df: pd.DataFrame, db_url: str) -> tuple[int, int]:
    """ON CONFLICT DO UPDATE 로 적재. (inserted, updated) 반환."""
```

### 2. 카테고리 분류 매핑

`category_name`은 카카오가 `"음식점 > 한식 > 국밥"` 같이 ` > ` 구분 문자열로 반환한다. 앞 2단계 prefix로 분류:

| prefix | 프로젝트 카테고리 |
|---|---|
| `음식점 > 한식` | 한식음식점 |
| `음식점 > 중식` | 중식음식점 |
| `음식점 > 일식` | 일식음식점 |
| `음식점 > 양식` | 양식음식점 |
| `음식점 > 치킨` | 치킨전문점 |
| `음식점 > 분식` | 분식전문점 |
| `음식점 > 패스트푸드` | 패스트푸드점 |
| `음식점 > 제과,베이커리` | 제과점 |
| `음식점 > 술집` | 호프-간이주점 |
| `카페` (접두 매칭) | 커피-음료 |
| 그 외 (`음식점 > 도시락`, `음식점 > 간식` 등) | 기타 |

### 3. Alembic 마이그레이션

신규 리비전 `<timestamp>_kakao_store_add_is_franchise.py`:

```python
def upgrade():
    op.add_column('kakao_store',
        sa.Column('is_franchise', sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.alter_column('kakao_store', 'brand_name',
        existing_type=sa.String(100), nullable=True
    )
    op.create_index('ix_kakao_store_is_franchise', 'kakao_store', ['is_franchise'])
```

`models.py`의 `KakaoStore` 클래스에 `is_franchise`, `brand_name` nullable 반영.

### 4. UPSERT 구현

`psycopg2.extras.execute_values` 또는 SQLAlchemy `insert().on_conflict_do_update()` 사용:

```sql
INSERT INTO kakao_store (kakao_id, place_name, brand_name, category, ...)
VALUES (...)
ON CONFLICT (kakao_id) DO UPDATE SET
    place_name = EXCLUDED.place_name,
    category = EXCLUDED.category,
    category_detail = EXCLUDED.category_detail,
    address = EXCLUDED.address,
    road_address = EXCLUDED.road_address,
    dong_name = EXCLUDED.dong_name,
    lat = EXCLUDED.lat,
    lon = EXCLUDED.lon,
    phone = EXCLUDED.phone,
    place_url = EXCLUDED.place_url,
    is_franchise = EXCLUDED.is_franchise,
    brand_name = COALESCE(EXCLUDED.brand_name, kakao_store.brand_name),
    collected_at = NOW();
```

`brand_name`은 `COALESCE`로 기존 값 보존 (브랜드 모드에서 채운 값을 카테고리 모드가 덮어쓰지 않도록).

## 데이터 흐름 예시

1. `generate_grid((126.88, 37.53, 126.96, 37.59), 500)` → 약 208개 셀
2. 각 셀마다 `search_category("FD6", cell, page=1..3)` + `search_category("CE7", cell, page=1..3)`
3. `is_end=false && page=3` 도달하면 45건 초과 → `collect_cell(depth+1)`로 4분할 재귀 (max depth=3, 최소 62.5m 셀)
4. 셀 경계 중복은 `kakao_id` set으로 dedupe
5. `category_name`, 장소명으로 10개 분류 + 브랜드 정규화
6. 배치 UPSERT (chunksize 500)
7. `data/processed/kakao_store_full_mapo.csv`로 검증 덤프

## 에러 처리

| 상황 | 대응 |
|---|---|
| API 429/5xx | `time.sleep(1)` 후 최대 3회 재시도, 실패시 해당 셀 스킵 + 로그 |
| `is_end=false && depth≥3` | 경고 로그, 해당 셀은 45건만 남기고 진행 (마포 밀도상 거의 없을 것) |
| `category_name` 누락/이상 | `기타`로 분류, 경고 로그 |
| bbox 마포 경계 밖 점포 | `address`에 "마포구" 없는 건 필터 (기존 로직 유지) |

## 테스트

1. **단위 테스트** (`tests/test_kakao_crawl.py`):
   - `generate_grid`: 주어진 bbox를 정확히 분할하는지
   - `classify_category`: 10개 + 기타 매핑 정확도
   - `collect_cell` (mocked API): 45건 도달시 adaptive split 동작
2. **통합 테스트** (수동):
   - 작은 bbox(합정동 1블록)로 `--mode=categories` 실행 → CSV 확인
   - UPSERT 재실행으로 중복/갱신 정상 동작 확인
3. **검증 쿼리**:
   ```sql
   SELECT category, COUNT(*), COUNT(*) FILTER (WHERE is_franchise) AS franchise_cnt
   FROM kakao_store GROUP BY category ORDER BY 2 DESC;
   ```

## 기대 효과

- 개인 점포까지 포함된 약 8,000~12,000건의 위·경도 완비 데이터
- 상권 밀도(500m 내 경쟁 점포 수), ABM 시뮬레이션 에이전트 배치, `vacancy_enriched` 보강 피처로 즉시 활용 가능
- `kakao_store_hours`에 크롤링 대상이 확장되어 영업시간 데이터도 자연 증가

## 운영

- 1회성 수집이 기본. 월 1회 재실행으로 신규/폐업 반영 (UPSERT이므로 안전).
- 카카오 API 쿼터: 하루 30만건 한도 내 여유 있음 (1회 800호출 수준).
