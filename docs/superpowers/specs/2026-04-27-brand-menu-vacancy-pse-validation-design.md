# 브랜드 메뉴 가격 연결 + Vacancy_PSE 매출 정확도 5트랙 검증 — Design

작성: A1 (찬영) — 2026-04-27
Branch: IM3-243-dong-fk-followup
Status: Design (사용자 검토 대기)

---

## 1. 개요 (한 줄 요약)

vacancy_pse 가 산출하는 매장 매출이 현재 `price_level` 추상값 fallback 으로만 계산되는 갭을 닫는다. **DB의 `kakao_store_menu` 에서 브랜드별 메뉴/가격을 가져와 가상 vacancy 매장에 attach** 하고, 동시에 **5트랙 정확도 검증 protocol** (V1a/V1b/V1c/V2/CI) 로 production-readiness 를 정직하게 평가한다.

부수 deliverable: 1000 ag 시뮬 시각화 (사용자 vision) 의 **데이터 인터페이스** 도 본 spec 에 포함 (`collect_trajectory`, `dump_visits` 옵션). 실제 frontend 페이지는 별도 spec.

## 2. Product Vision

본 spec 은 더 큰 product vision 의 building block 이다:

> **사용자 GUI**: 사장님이 공실 spot 클릭 → 1000 에이전트가 마포구 지도 위에 점으로 표시되며 시간대별 동선 진행 → spot 위치 강조 → 시간 슬라이더로 7시→8시→... 진행 → spot 들어오는 방문객 trail 시각화 → 시뮬 끝나면 매출/방문 통계 + 동선 replay.

본 spec 은:
- **백엔드 정확도 강화** (메뉴 가격 연결) — 매출 추정의 *절대값* 정확도
- **검증 protocol** (5트랙) — production 사용 가능 수준인지 *정량적 판정*
- **시각화 데이터 인터페이스** — `evaluate_vacancy_pse(collect_trajectory=True, dump_visits=True)` → trajectory + 방문 이벤트 list 반환

실제 frontend 시각화 페이지 + 새 API endpoint 는 본 spec 후속 spec (사용자 본인 또는 C1 강민 진행).

## 3. 배경 — 현재 시스템과 갭

### 3.1 이미 작동 중인 인프라

- **vacancy_pse**: 1000 ag × N=5 PSE seed → 일/분기/연 매출 + 카니발 + zero-sum 분석 (`backend/src/simulation/vacancy_pse.py`)
- **vacancy_evaluation_service** + REST API 3개 (`/single`, `/batch`, `/health`)
- **DB**: `kakao_store_menu` (점포별 메뉴/가격), `kakao_store.brand_name`, `district_sales` (분기 매출), `ftc_brand_franchise.avrgSlsAmt` (브랜드 전국 연 평균), `sales_imp_mapo.csv` (동×업종 매장 수)
- **brand_mapping_resolver**: `get_all_mapo_stores_by_brand(brand_name)` 함수 이미 존재
- **시각화 인프라**: `/api/simulation/*` 7개 endpoint 작동 중, `runner.py` 의 `collect_trajectory` 인자 존재
- **메뉴 기반 spend logic**: `agents.py:413-421`, `policy_executor.py:638-646` — `if store.menu_items: spend = chosen["price"] × mult` 이미 작동

### 3.2 갭 (B 작업의 본질)

`vacancy_inject.py:96-107` 에서 신규 vacancy 매장을 주입할 때 **`menu_items` 를 채우지 않음** (기본값 빈 리스트). 즉 vacancy 시뮬은 추상 fallback (`base[category] × price_level × uniform(0.7, 1.3)`) 으로만 매출 계산. 사용자가 의도하는 "DB 메뉴 가격 연결 매출" 이 vacancy 시뮬에서만 누락.

또한 **매출 정확도 검증 자체가 0건**. OVERVIEW.md 의 측정값 (Pearson r 0.291~0.849) 은 *공간 분포* 정확도. *매장 매출 절대값* 검증은 아직 한 번도 안 함 → "production-ready 수준인가" 의문에 답이 없음.

## 4. 명확화 결정 기록 (brainstorm 결과)

| 결정 항목 | 선택 | 이유 |
|---|---|---|
| 작업 트랙 | **B 옵션** — 기존 vacancy_pse 개선 (메뉴 가격 연결 강화) | 신규 구축 (A) 또는 추천 에이전트 강화 (C) 보다 ROI 높음 |
| 메뉴 source | **F 옵션** — 브랜드별 menu (kakao_store_menu × kakao_store.brand_name) | 프랜차이즈 대상 프로그램. 동·카테고리 평균 (A) 보다 정확 |
| 마포 0매장 브랜드 | **제외** (예: 스타벅스) — 명확한 에러 | fallback chain 불필요, design 깔끔 |
| 사용자 직접 메뉴 입력 | **제외** | 프랜차이즈는 메뉴 정해져 있어 입력 부담 비효율 |
| 검증 데이터 source | **DB 만** (외부 실측 매출 부재) | 매장 단위 실측 매출 외부 source 없음 |
| 검증 합격선 | **엄격** (r ≥ 0.85, MAPE ≤ 25%, ratio 0.7~1.5, CI ≤ 10%) | 사용자 지정. fail 가능성 인정 = 정직한 평가 |
| 시뮬 days | **검증=90 (분기)** + **운영=1 (현재 default 유지)** | district_sales 단위와 직접 일치 |
| 정적 환경 (날씨/계절/트렌드) | **무시 (옵션 4)** + multi-quarter 평균 ground truth + future work 명시 | 시뮬 개선 (옵션 3) 은 별도 spec |
| 시각화 인터페이스 | **옵션 C** — 데이터 출력만 본 spec, frontend 페이지는 별도 | spec scope 작게 유지 |
| 구현 위치 | **A 옵션** — simulation/ 직접 수정 | 본인 owner 코드 (git log 확인) |
| LLM 호출 정책 | **Mode B (default)** — Pure Policy + 한국어 Template 자연어 → 비용 $0. **Mode C (가용 시)** — Tier S 50명 GPT-4.1 mini, 750명은 template (운영 $0.3/평가) | "Affordable Generative Agents" (arxiv 2402.02053) + GeekNews "agent 보다 workflow 우선" 가이드와 일치. 학술/뉴스 입증 |
| LLM 호출 모델 | **GPT-4.1 mini** (옵션 3 활성 시) | 사용자 프로젝트 표준 모델 |
| 검증 LLM 정책 | **mock 강제** (검증은 LLM 무관) | 매출 정확도 검증에 LLM 영향 ~3% (Policy 가 결정 logic dominant) |

## 5. 아키텍처 / 컴포넌트

### 5.1 high-level 흐름

```
[사용자/API caller]
  brand_name="이디야", category="카페", spot={dong, lat, lon}
        │
        ▼
services/vacancy_evaluation_service.evaluate_top_vacancies
        │ ① brand_name → menu_items 변환 요청
        ▼
services/brand_menu_loader.load_brand_menu_items   ← 신규 (services/, A1 owner)
        │ get_all_mapo_stores_by_brand → kakao_store_menu JOIN → list[{name, price}]
        ▼
simulation/vacancy_pse.evaluate_vacancy_pse   ← menu_items 인자 추가
        │ menu_items 패스스루
        ▼
simulation/vacancy_inject.inject_vacancy_as_store   ← menu_items 인자 추가 (1줄)
        │ Store(menu_items=menu_items)
        ▼
[기존 시뮬 흐름] agents.py:413 의 menu 기반 spend 자동 활성
```

별도 트랙 — 검증 protocol:

```
validation/brand_vacancy_validator.run_5track_validation   ← 신규
  ├─ Step A. 실측 데이터 (district_sales, sales_imp_mapo, ftc 64-cell)
  ├─ Step B. 시뮬 (V1a/b/c 공유 64-cell + V2 단일 vacancy)
  ├─ Step C. 5트랙 측정 (V1a/V1b/V1c/V2/CI)
  ├─ Step D. 합격 판정 + diagnose
  └─ Step E. report (JSON + Markdown)
```

### 5.2 컴포넌트 표

| 컴포넌트 | 위치 | 신규/수정 | 책임 |
|---|---|---|---|
| `load_brand_menu_items(brand_name)` | `backend/src/services/brand_menu_loader.py` | **신규** | brand_name → 마포 같은 브랜드 매장들의 메뉴 통합 → `list[{name, price}]` |
| `evaluate_top_vacancies(...)` | `backend/src/services/vacancy_evaluation_service.py` | **수정** | `brand_name` 인자 추가, brand_menu_loader 호출, vacancy_pse 에 menu_items 패스 |
| `evaluate_vacancy_pse(...)` | `backend/src/simulation/vacancy_pse.py` | **수정** | `menu_items`, `collect_trajectory`, `trajectory_sample_size`, `dump_visits` 인자 추가 |
| `inject_vacancy_as_store(...)` | `backend/src/simulation/vacancy_inject.py` | **수정** | `menu_items: list[dict] \| None = None` 인자 추가 |
| `run_5track_validation(...)` | `validation/brand_vacancy_validator.py` | **신규** | 5트랙 검증 protocol 실행 + 합격선 판정 + report |
| `_track_v1a/v1b/v1c/v2/ci(...)` | 같은 파일 | **신규** | 각 트랙 측정 단위 함수 (단위 테스트 가능) |
| `diagnose_failure(...)` | 같은 파일 | **신규** | 5트랙 결과 → fail 진단 메시지 자동 생성 |

### 5.3 책임 경계

- `brand_menu_loader` — 시뮬 호출 X, vacancy 위치 X. brand_name → menu_items 변환만.
- `vacancy_inject` — brand 모름. 받은 menu_items 를 Store 에 set 만.
- `vacancy_pse` — brand 모름 (menu_items 만 알면 됨). PSE seed loop + cannibal 측정만.
- `brand_vacancy_validator` — 시뮬 변경 X. PSE 호출만. 측정 + 합격 판정 + report.

### 5.4 새 시그니처

```python
# services/brand_menu_loader.py (신규)
class BrandNotFoundError(ValueError): ...
class BrandMenuEmptyError(ValueError): ...

def load_brand_menu_items(brand_name: str) -> list[dict[str, Any]]:
    """brand_name → list[{"name": str, "price": int}]. 마포 매장 0개면 BrandNotFoundError."""

# vacancy_inject.py (수정)
def inject_vacancy_as_store(
    world, vacancy_spot, category,
    name=None, seats=DEFAULT_SEATS, rating=DEFAULT_RATING,
    price_level=DEFAULT_PRICE_LEVEL,
    popularity_boost=DEFAULT_POPULARITY_BOOST,
    menu_items: list[dict] | None = None,        # ← 추가
) -> str: ...

# vacancy_pse.py (수정)
def evaluate_vacancy_pse(
    vacancy_spot, category,
    n_seeds=5, days=1,
    popularity_boost=DEFAULT_POPULARITY_BOOST,
    with_cannibalization=True,
    pop_mix=None, tier_dist=None, cfg=None, seeds=None,
    verbose=False,
    menu_items: list[dict] | None = None,        # ← B 작업
    collect_trajectory: bool = False,            # ← 시각화 인터페이스
    trajectory_sample_size: int = 300,           # ←
    dump_visits: bool = False,                   # ←
    use_dialog_templates: bool = True,           # ← 옵션 2: Policy + Template 자연어
    enable_llm: bool = False,                    # ← 옵션 3: Tier S 50명 LLM (gradient 활성)
    llm_tier_policy: str = "S_only",             # ← "none" | "S_only" | "S_and_A" | "all"
    llm_max_tokens: int = 30,                    # ← 짧은 자연어
    llm_call_interval: int = 4,                  # ← 시간 단위, default 4시간마다
) -> dict: ...

# vacancy_evaluation_service.py (수정)
def evaluate_top_vacancies(
    vacancy_spots, category,
    top_n=5, n_seeds=5, days=1,
    with_cannibalization=False,
    popularity_boost=None,
    pre_filter_score=None, verbose=False,
    brand_name: str | None = None,               # ← 추가, 모든 vacancy_spots 에 공통 적용
) -> list[dict]: ...
```

**`brand_name` 적용 범위**: `evaluate_top_vacancies` 의 `brand_name` 인자는 **vacancy_spots 리스트 전체에 공통 적용** (한 사용자가 한 브랜드의 여러 후보 입지 비교하는 시나리오 가정). 만약 vacancy 별로 다른 브랜드 평가가 필요하면 호출을 brand 별로 분리해야 함 (현재 design scope 외).

`brand_name=None`, `menu_items=None`, `collect_trajectory=False`, `dump_visits=False` 기본값으로 **하위 호환성 100%**.

## 6. 데이터 흐름

### 6.1 메뉴 attach 흐름

1. `evaluate_top_vacancies(brand_name="이디야", ...)` 호출
2. `brand_menu_loader.load_brand_menu_items("이디야")`
   - `get_all_mapo_stores_by_brand("이디야")` → `[{kakao_id, dong, lat, lon, ...}, ...]`
   - 결과 0건: `raise BrandNotFoundError`
   - kakao_id 리스트 → `kakao_store_menu` JOIN
     ```sql
     SELECT menu_name, AVG(price)::int AS price
     FROM kakao_store_menu
     WHERE kakao_id IN :kids AND price IS NOT NULL AND price > 0
     GROUP BY menu_name
     ORDER BY AVG(price) DESC
     LIMIT 30
     ```
   - 결과 0건: `raise BrandMenuEmptyError`
   - return `list[{"name": str, "price": int}]`
3. `evaluate_vacancy_pse(spot, category, menu_items=menu_items)` 호출
4. PSE seed loop 안에서 `inject_vacancy_as_store(world, spot, category, menu_items=menu_items)`
5. `Store(menu_items=menu_items)` 생성 → `world.add_store(store)`
6. 시뮬 진행 시 `agents.py:413` 의 `if store.menu_items:` 분기가 vacancy 매장에서도 True → 메뉴 가격에서 sampling → `spend = chosen["price"] × mult`

### 6.2 검증 흐름

```
run_5track_validation("이디야", "카페", days=90, n_seeds=3, multi_quarter_avg=4)

Step A. 실측 데이터 (multi-quarter 평균 ground truth)
─────────────────────────────────
SELECT dong_name, industry_name,
       AVG(monthly_sales)::bigint  AS quarterly_sales_avg,   -- 컬럼명 misleading: 실제 분기 매출
       AVG(monthly_count)::bigint  AS quarterly_count_avg
FROM district_sales
WHERE dong_code LIKE '114%'
  AND quarter IN (최근 N=4 분기)
GROUP BY dong_name, industry_name
→ 64 cell (16동 × 4업종) 의 multi-quarter 평균

sales_imp_mapo.csv  (동×업종 매장당 평균 매출 = monthly_sales / store_count)
ftc_brand_franchise.avrgSlsAmt  (브랜드 전국 연 평균 천원/년 → ×1000 = 원/년)

Step B. 시뮬 데이터
─────────────────────────────────
① 동×업종 매트릭스 (vacancy 미주입, 일반 시뮬, days=90 × N=3 PSE)
   for seed: run_simulation(days=90, ..., seed=seed, collect_trajectory=False)
   → world.stores 에서 dong/category 별 합산 → 64 cell × (revenue, visits)
   → 매장당 평균 = 합 / 매장 수 → 64 cell × per_store
② 단일 vacancy V2 시뮬 (대표 위치, vacancy_pse, days=90 × N=3 PSE)
   menu_items = brand_menu_loader.load_brand_menu_items("이디야")
   evaluate_vacancy_pse(spot=대표위치, "카페",
                       menu_items=menu_items,   # validator 가 직접 변환 후 전달
                       n_seeds=3, days=90, with_cannibalization=False)
   → 시뮬 90일 매출 ÷ 90 × 365 = 연 매출 환산

Step C. 5트랙 측정
─────────────────────────────────
V1a = pearson_r(시뮬 64-cell 매출, 실측 64-cell 매출) + mape(...)
V1b = pearson_r(시뮬 64-cell visits, 실측 monthly_count) + mape(...)
V1c = mean[ 시뮬 매장 매출 / 실측 매장 평균 매출 ]   # 64-cell 의 ratio 평균
V2  = 시뮬 vacancy 연 매출 / ftc.avrgSlsAmt × 1000
CI  = pse_summary["revenue_per_day"]["ci95"] / pse_summary["revenue_per_day"]["mean"]

Step D. 합격선 판정 + 진단
─────────────────────────────────
pass_v1a = (r ≥ 0.85) AND (mape ≤ 0.25)
pass_v1b = (r ≥ 0.80) AND (mape ≤ 0.30)
pass_v1c = 0.7 ≤ ratio ≤ 1.5
pass_v2  = 0.7 ≤ ratio ≤ 1.5
pass_ci  = ci_ratio ≤ 0.10
production_ready = ALL([pass_v1a, pass_v1b, pass_v1c, pass_v2, pass_ci])
diagnoses = diagnose_failure(tracks)  # fail 시 사용자 친화적 진단 메시지

Step E. report
─────────────────────────────────
JSON: validation/results/<brand>_5track.json
MD:   validation/results/<brand>_5track_report.md
```

### 6.3 단위 환산 표 (days=90 으로 환산 0)

| 트랙 | 시뮬 측 | 실측 측 | 환산 |
|---|---|---|---|
| V1a 매출 | days=90 시뮬 종료 후 `revenue_today` (90일 누적) | `district_sales.monthly_sales` (실제 분기 매출) | **단위 직접 일치, 환산 X** |
| V1b 방문 | `visits_today` (90일 누적) | `district_sales.monthly_count` (실제 분기 건수) | 단위 직접 일치 |
| V1c 매장 평균 | 시뮬 매장당 매출 평균 (그 동·업종 매장 평균) | `monthly_sales / store_count` (분기 매장 평균) | 단위 직접 일치 |
| V2 브랜드 | 시뮬 90일 매출 ÷ 90 × 365 = 연 매출 | `ftc.avrgSlsAmt × 1000` (원/년) | 분기 → 연 (×4.06) |
| CI | 비율 | — | 단위 자동 상쇄 |

### 6.4 시간 부담

- 동×업종 매트릭스 시뮬: days=90 × N=3 = 270분 ≈ **4.5시간**
- 단일 vacancy 시뮬: days=90 × N=3 = 270분 ≈ **4.5시간**
- **검증 1회 총 ~9시간** (1회만 측정, 결과 cache)

운영 vs 검증 분리:
- 운영 vacancy_pse API: days=1 (현재 default 유지) — 응답 5~10분
- 검증: days=90 (분기 단위 직접 비교) — 1회 9시간

## 7. 오류 처리

### 7.1 예외 클래스

| 예외 | 위치 | 발생 |
|---|---|---|
| `BrandNotFoundError` | `services/brand_menu_loader.py` | 마포에 brand_name 매장 0개 |
| `BrandMenuEmptyError` | 같음 | 매장 N≥1 but `kakao_store_menu` 의 가격>0 메뉴 0건 |
| `ValidationDataIncompleteError` | `validation/brand_vacancy_validator.py` | 검증 데이터 일부 누락 (cell 부분 부재) |
| `VacancyInjectionError` (기존) | `vacancy_inject.py` | 좌표/카테고리 검증 실패 |

### 7.2 레이어별 오류 처리

```
brand_menu_loader  → raise (호출자가 결정)
vacancy_evaluation_service:
  - BrandNotFoundError → 그 vacancy 만 스킵 (skip_invalid 패턴)
  - BrandMenuEmptyError → log.warning + menu_items=None fallback (추상 매출)
brand_vacancy_validator:
  - 트랙 단위 try/except (V1a fail 해도 V1b 진행)
  - partial report 작성, 어느 트랙이 왜 실패했는지 기록
```

### 7.3 트랙별 부분 실패

| 실패 모드 | 처리 |
|---|---|
| V1a/V1b: 64 cell 중 일부 row 부재 | 누락 cell 제외하고 r/MAPE 계산 + sample size 보고 |
| V1c: store_count = 0 (sales_imp_mapo 부재) | V1c skip + report 명시 |
| V2: ftc.avrgSlsAmt = NULL (등록 안 된 브랜드) | V2 skip + **production_ready 자동 fail** (V2 빠지면 통과 불가) |
| CI: PSE seed 일부 crash | 성공 seed 만 CI 계산 + N 명시 (N<3 면 CI 보고 X) |
| 시뮬 timeout/OOM | log.error + 부분 결과 dump → 사용자가 환경 조정 후 재실행 |

### 7.4 운영 API 의 오류 응답

```python
if brand_name:
    try:
        menu_items = brand_menu_loader.load_brand_menu_items(brand_name)
    except BrandNotFoundError as e:
        return {"error": "BRAND_NOT_FOUND", "message": str(e), "rankings": []}  # 400
    except BrandMenuEmptyError as e:
        log.warning(...)
        menu_items = None  # 200 + 추상 fallback
```

## 8. 테스트

### 8.1 테스트 파일 위치

| 파일 | 위치 | 카테고리 |
|---|---|---|
| `test_brand_menu_loader.py` | `backend/tests/` | 단위 |
| `test_vacancy_inject_menu.py` | `backend/tests/` | 단위 |
| `test_vacancy_pse_brand.py` | `backend/tests/` | 통합 (mock LLM, days=1, N=1) |
| `test_vacancy_evaluation_service_brand.py` | `backend/tests/` | 통합 |
| `test_brand_vacancy_validator.py` | `tests/` (top-level) | 단위 + 통합 |
| `test_validator_diagnose.py` | `tests/` | 단위 |

### 8.2 핵심 테스트 케이스

**`test_brand_menu_loader.py`**:
- 정상 — list 반환 (n>0, name/price 포함)
- 마포 0매장 → `BrandNotFoundError`
- 매장 N≥1 + 메뉴 0건 → `BrandMenuEmptyError`
- 메뉴명 dedup (5매장 같은 메뉴 → unique)
- 가격 평균 (매장별 가격 다름 → AVG)
- 캐싱 (같은 brand 두 번 호출 → DB 1회)

**`test_vacancy_inject_menu.py`**:
- `menu_items` 인자 → `Store.menu_items` 에 set
- `menu_items=None` → 빈 list 기본값 (하위 호환)

**`test_vacancy_pse_brand.py`** (`@pytest.mark.slow`):
- `menu_items` 제공 시 vacancy 매출 = 메뉴 가격 sampling (avg_spend ≈ menu price ± mult)
- `menu_items=None` → 추상 fallback 동작
- `collect_trajectory=True` → result 에 trajectory list
- `dump_visits=True` → result 에 visits_events list
- 기본 호출 → trajectory/visits_events 필드 None 또는 부재 (응답 작음)
- 회귀: 기존 인자 시그니처 그대로 호출 → 동일 결과 구조

**`test_vacancy_evaluation_service_brand.py`**:
- `brand_name` 인자 → brand_menu_loader 호출 → vacancy_pse 에 패스
- `brand_name=None` → loader 호출 X
- `BrandNotFoundError` → error 응답 + 다른 vacancy 평가 진행

**`test_brand_vacancy_validator.py`**:
- `_track_v1a` 단위: sim≈actual×1.05 → r≈0.99, mape≈5%, pass=True
- `_track_v1a` 단위: sim 무작위 → pass=False
- `_track_v1c` ratio in/out 합격선
- `_track_v2` ratio in/out + skipped 처리
- `_track_ci` 저변동 → pass / 고변동 → fail
- `run_5track_validation` 모두 통과 → `production_ready=True`
- 1트랙 fail → `production_ready=False` + diagnoses 메시지 포함
- V2 skipped → 자동 production_not_ready

### 8.3 fixture 전략

- `small_world` (`backend/tests/conftest.py`) — 동 2개 + 매장 10개 (시뮬 빠름)
- `mock_db_brand_with_menu` — brand_mapping_resolver / kakao_store_menu mock SQL
- `mock_district_sales_64cell` (`tests/conftest.py`) — 64 cell mock
- 모든 단위 테스트는 real DB 의존 X. 통합 테스트만 actual ABM (mock LLM, days=1, N=1).

### 8.4 CI 정책

```bash
# 빠른 단위 (~10초, CI 기본)
pytest backend/tests/test_brand_menu_loader.py
pytest tests/test_brand_vacancy_validator.py -k "not slow"

# 통합 (~5분, slow mark, 야간 schedule)
pytest backend/tests/test_vacancy_pse_brand.py -m slow

# 검증 protocol 자체 실행 (~9시간, 별도 script)
python -m validation.brand_vacancy_validator --brand 이디야 --category 카페
```

### 8.5 커버리지 목표

| 파일 | 목표 |
|---|---|
| `services/brand_menu_loader.py` | ≥ 90% |
| `simulation/vacancy_inject.py` (수정 부분) | 100% |
| `simulation/vacancy_pse.py` (수정 부분) | 100% |
| `validation/brand_vacancy_validator.py` | ≥ 85% |

## 9. 5트랙 검증 protocol 상세

### 9.1 합격선 정의 + 근거

| 트랙 | 측정값 | 합격선 | 근거 |
|---|---|---|---|
| V1a | 동×업종 매출 64-cell Pearson r + MAPE | r ≥ 0.85, MAPE ≤ 25% | Brussels 학계 천장 0.96 × 88% (학계 상위) |
| V1b | 동×업종 visits 64-cell Pearson r + MAPE | r ≥ 0.80, MAPE ≤ 30% | sample noise 보정 (V1a 보다 -0.05) |
| V1c | 매장당 매출 ratio (mean of cell ratios) | 0.7 ~ 1.5 | 가맹 매출 분석 통상 0.5~2.0 의 strict 절반 |
| V2 | 시뮬 연 매출 / ftc 연 평균 ratio | 0.7 ~ 1.5 | 같음 |
| CI | PSE 95% CI / mean | ≤ 10% | 의사결정 단위 (1억±10% = 의미있는 오차) |

### 9.2 합격선 의미 (각 trial 의 X/Y 정의)

**V1a Pearson r**:
- X축 (시뮬): 64 cell 의 시뮬 매출 합 (예: 서교동 카페 335개 매장 시뮬 매출 합 = 8.5억/분기)
- Y축 (실측): `district_sales.monthly_sales` (예: 서교동 카페 monthly_sales = 9.2억/분기)
- r = 1.0 (완벽 일치) → 0.85 (Brussels 0.96 × 88%) → 0.0 (무관)
- MAPE = `mean(|X - Y| / Y)` × 100% — 평균 절대 % 오차

**V1c Ratio**:
- 분자: 시뮬 1매장 분기 매출
- 분모: 그 동×업종 평균 매장 매출 = `monthly_sales / store_count`
- ratio = 1.0 (시뮬 매장 = 동 평균) → 0.7~1.5 (strict 합격선)
- ratio > 1.5 → 시뮬 매장이 평균보다 50% 초과 → fail (popularity_boost 영향 의심)

**V2 Ratio**:
- 분자: 시뮬 연 매출 (예: 이디야 서교동 시뮬 연 1.2억)
- 분모: `ftc.avrgSlsAmt × 1000` (예: 이디야 전국 연 평균 1.5억)
- ratio = 0.8 → 합격 (마포가 평균 80% 수준)

**CI**:
- N=3 PSE seed → mean = 15.2, std = 0.78, 95% CI = 1.96 × std/√3 = 0.88
- CI/mean = 5.8% → 합격 (≤ 10%)

### 9.3 5트랙 분리 logic — 두 직교 차원

| | (a) 매출 | (b) 방문 |
|---|---|---|
| **(1) 동 합산** | V1a (district_sales.monthly_sales) | V1b (district_sales.monthly_count) |
| **(2) 단일 매장 — 마포 분포** | V1c (sales_imp_mapo 매장 평균) | (불가, 매장 단위 visits 실측 X) |
| **(2) 단일 매장 — 브랜드 분포** | V2 (ftc.avrgSlsAmt) | (불가) |
| 신뢰성 | CI (PSE N=3 seed 안정성) — trial 무관 | |

각 trial 이 **막는 fail mode 가 다름**:
- V1a 만 통과 → 동 합산 cancellation (매장 단위 비현실 가능) 안 막음 → V1c 가 막아줌
- V1c 만 통과 → 단일 매장 우연 통과 (다른 동/브랜드 fail 가능) → V1a 가 막아줌
- V1a + V1c 매출만 → "가격 × 방문" 의 가격 곱셈이 방문 오류 가렸을 가능 → V1b 가 막아줌
- 마포 통과 (V1a/V1b/V1c) → 브랜드 단위 비현실 가능 → V2 가 막아줌
- 4트랙 통과 → 1번 운 좋은 seed 가능 → CI 가 막아줌

→ **5개 동시 통과 = 마포 공간 + 마포 절대값 + 브랜드 절대값 + 안정성 모두 검증**.

### 9.4 측정 함수 outline

```python
def _track_v1a(sim_revenue: dict, actual_revenue: dict) -> dict:
    common = sim_revenue.keys() & actual_revenue.keys()
    # n_cells < 10: Pearson r 의 통계적 안정성 학계 통상 N≥10 (Cohen 1988).
    # 그 미만이면 sample variance dominant → 합격/불합격 판정 신뢰성 X
    if len(common) < 10:
        return {"status": "incomplete", "n_cells": len(common), "pass": False}
    sim_arr = np.array([sim_revenue[k] for k in common])
    act_arr = np.array([actual_revenue[k] for k in common])
    r, _ = scipy.stats.pearsonr(sim_arr, act_arr)
    mape = float(np.mean(np.abs(sim_arr - act_arr) / np.maximum(act_arr, 1)))
    return {
        "status": "ok", "n_cells": len(common),
        "pearson_r": round(r, 4), "mape": round(mape, 4),
        "pass": r >= 0.85 and mape <= 0.25,
        "thresholds": {"r_min": 0.85, "mape_max": 0.25},
    }

def _track_v1b(sim_visits, actual_count) -> dict:
    # 동일 구조, threshold = r_min 0.80, mape_max 0.30
    ...

def _track_v1c(sim_per_store: dict, actual_per_store: dict) -> dict:
    common = sim_per_store.keys() & actual_per_store.keys()
    ratios = [sim_per_store[k] / max(actual_per_store[k], 1) for k in common]
    mean_ratio = float(np.mean(ratios))
    return {
        "status": "ok", "n_cells": len(ratios),
        "mean_ratio": round(mean_ratio, 3),
        "median_ratio": round(float(np.median(ratios)), 3),
        "pass": 0.7 <= mean_ratio <= 1.5,
        "thresholds": {"ratio_min": 0.7, "ratio_max": 1.5},
    }

def _track_v2(sim_yearly: float, ftc_avg_yearly: int | None) -> dict:
    if ftc_avg_yearly is None or ftc_avg_yearly == 0:
        return {"status": "skipped", "reason": "ftc data missing", "pass": False}
    ratio = sim_yearly / ftc_avg_yearly
    return {
        "status": "ok", "ratio": round(ratio, 3),
        "sim_yearly_won": int(sim_yearly), "ftc_yearly_won": int(ftc_avg_yearly),
        "pass": 0.7 <= ratio <= 1.5,
    }

def _track_ci(pse_summary: dict) -> dict:
    rev = pse_summary["revenue_per_day"]
    if rev["mean"] == 0:
        return {"status": "incomplete", "pass": False}
    ci_ratio = rev["ci95"] / rev["mean"]
    return {
        "status": "ok", "ci_ratio": round(ci_ratio, 4),
        "pass": ci_ratio <= 0.10,
        "thresholds": {"ci_max": 0.10},
    }
```

### 9.5 진단 메시지 자동 생성

```python
def diagnose_failure(tracks: dict) -> list[str]:
    diagnoses = []
    if not tracks["v1a"].get("pass"):
        r, mape = tracks["v1a"].get("pearson_r"), tracks["v1a"].get("mape")
        diagnoses.append(
            f"V1a fail (r={r}, MAPE={mape}): 동×업종 매출 분포 격차. 가능 원인: "
            f"(1) popularity_boost=5.0, (2) 정적 시뮬 한계 [옵션 3 future], "
            f"(3) IPF calibration 미적용. → IPF + boost=1.0 재측정."
        )
    if not tracks["v1c"].get("pass"):
        r = tracks["v1c"].get("mean_ratio")
        if r > 1.5:
            diagnoses.append(
                f"V1c fail (ratio={r} > 1.5): 시뮬 매장 동 평균보다 {(r-1)*100:.0f}% 높음. "
                f"popularity_boost 또는 페르소나 spend_tendency 과대. → boost=1.0 재측정."
            )
        else:
            diagnoses.append(
                f"V1c fail (ratio={r} < 0.7): 시뮬 매장 동 평균의 {r*100:.0f}% 과소. "
                f"메뉴 가격 source 점검 또는 visits 과소."
            )
    if not tracks["v2"].get("pass"):
        if tracks["v2"].get("status") == "skipped":
            diagnoses.append("V2 skipped: ftc 에 brand row 없음. → 브랜드명 alias 점검.")
        else:
            r = tracks["v2"].get("ratio")
            if r > 1.5:
                diagnoses.append(f"V2 fail (ratio={r} > 1.5): 시뮬 매출 전국 평균 {(r-1)*100:.0f}% 초과.")
            else:
                diagnoses.append(f"V2 fail (ratio={r} < 0.7): 시뮬 매출 전국 평균의 {r*100:.0f}% 미만.")
    if not tracks["ci"].get("pass"):
        ci = tracks["ci"].get("ci_ratio")
        diagnoses.append(
            f"CI fail (CI/mean={ci*100:.1f}% > 10%): PSE 변동 과다. → n_seeds 3→5→10 또는 days 90→180."
        )
    if not tracks["v1b"].get("pass"):
        diagnoses.append("V1b fail: 방문 수 분포 격차. → agent 1000→3000 또는 PSE n 늘리기.")
    return diagnoses
```

### 9.6 report 형식

**JSON** — `validation/results/<brand>_5track.json`:
```json
{
  "brand_name": "이디야",
  "category": "카페",
  "config": {"days": 90, "n_seeds": 3, "multi_quarter_avg": 4},
  "tracks": {
    "v1a": {"pearson_r": 0.812, "mape": 0.298, "n_cells": 56, "pass": false},
    "v1b": {"pearson_r": 0.78, "mape": 0.31, "pass": false},
    "v1c": {"mean_ratio": 2.45, "pass": false},
    "v2":  {"ratio": 1.92, "pass": false},
    "ci":  {"ci_ratio": 0.087, "pass": true}
  },
  "production_ready": false,
  "diagnoses": ["V1a fail ...", "V1c fail (ratio=2.45 > 1.5) ..."],
  "limitations": [
    "정적 시뮬 환경 — 90일 동안 같은 날씨/같은 월. 옵션 3 future work.",
    "매장 단위 실측 매출 부재 — 동×업종 평균으로 V1c 측정."
  ],
  "timestamp": "2026-04-27T..."
}
```

**Markdown** — `validation/results/<brand>_5track_report.md`: 사람이 읽는 형식, 표 + 합격/불합격 + 진단 + 다음 액션.

### 9.7 CLI 인터페이스

```bash
# 단일 브랜드
python -m validation.brand_vacancy_validator --brand 이디야 --category 카페 --days 90 --n-seeds 3

# 일괄
python -m validation.brand_vacancy_validator --brands 이디야,MEGA,빽다방 --category 카페

# multi_quarter_avg 조정
python -m validation.brand_vacancy_validator --brand 이디야 --multi-quarter-avg 8
```

기본값: `--days 90`, `--n-seeds 3`, `--multi-quarter-avg 4`, `--category 카페`.

**검증은 항상 LLM 비활성** (`enable_llm=False`, `use_dialog_templates=True` 도 무관). 매출 정확도 검증에 LLM 영향 미미 (Policy 가 결정 logic dominant) + 비용 $0. CLI 가 자동으로 mock 강제.

**`_pick_representative_spot` outline**:

```python
def _pick_representative_spot(brand_name: str, category: str) -> dict:
    """V2 시뮬용 단일 spot 선정 — 브랜드 마포 매장 좌표의 중심점.

    이유: 마포 브랜드 매장 N개 모두 시뮬 시 시간 N배. 좌표 중심점 1회로
    "마포 평균 입지의 그 브랜드" 라는 대표값 산출 (sensitivity 는 옵션 --all-spots).
    """
    stores = get_all_mapo_stores_by_brand(brand_name)
    if not stores:
        raise BrandNotFoundError(...)
    # 가장 가까운 실제 동·좌표 사용 (중심점이 강 위에 떨어지지 않도록)
    center_lat = mean(s["lat"] for s in stores)
    center_lon = mean(s["lon"] for s in stores)
    nearest = min(stores, key=lambda s: haversine(s["lat"], s["lon"], center_lat, center_lon))
    return {"dong": nearest["dong_name"], "lat": nearest["lat"], "lon": nearest["lon"]}
```

옵션 `--all-spots` 시: 모든 매장 위치 각각 시뮬 → 평균 매출 사용 (시간 N배 부담, sensitivity ↑).

## 10. LLM 호출 정책 + 자연어 대화

본 spec 의 **운영 vacancy_pse 시뮬에서 자연어 대화 (chats endpoint 데이터) 출력 정책**.

### 10.1 핵심 원칙 (학술/뉴스 근거)

> **"매출 정확도 측정에 LLM 필요 X. 자연어 대화 표현에만 LLM 필요. 자연어도 template 으로 시작, LLM 은 가용 시 점진적 활성."**

근거:
- "Affordable Generative Agents" (arxiv 2402.02053) — LLM ABM 의 비용 절감 방향
- Tsinghua survey (Nature HSSC 2024) — LLM 은 "다양성/자연어", 결정 logic 은 rule-based
- GeekNews [AI 에이전트 개발을 멈추고, 더 똑똑한 LLM 워크플로우를 써라](https://news.hada.io/topic?id=21853) — "agent 라기보다 workflow + LLM optional"

### 10.2 모드 비교 (Mode A/B/C/D)

(brainstorm 의 "옵션 1/2/3/4" — 시뮬 환경/날씨 — 와 명확히 구분하기 위해 LLM 정책은 **Mode A/B/C/D** 로 명명)

| 모드 | 결정 logic | 자연어 대화 | 비용 (운영/검증) | 시간 (운영) | 본 spec |
|---|---|---|---|---|---|
| **Mode A. Pure Policy** | Policy 55 + Archetype 30 | ❌ | $0 / $0 | 5분 | 가능 (대화 X) |
| **Mode B. Policy + Template** ✅ default | + 30 archetype × 600 한국어 문장 | ⭐⭐ (반복 가능) | $0 / $0 | 5분 | **본 spec 채택** |
| **Mode C. Policy + Tier S LLM** ✅ 가용 시 | + Tier S 50명 GPT-4.1 mini, 750명 template | ⭐⭐⭐ | $0.3/평가, 검증 mock $0 | 6분 | **본 spec 옵션** (`enable_llm=True`) |
| **Mode D. LLM 전체 (1000명)** | + 1000명 GPT-4.1 mini | ⭐⭐⭐⭐⭐ | $6/평가, $672/검증 (4시간마다) | 6분~5h (비동기 인프라 필요) | Phase 3 future spec |

### 10.3 Mode B — Pure Policy + Template 자연어 (default)

**신규 컴포넌트**: `backend/src/simulation/dialog_templates.py` (사용자 owner)

```python
# simulation/dialog_templates.py (신규, ~1~2일 작업)

TEMPLATES: dict[str, dict[str, list[str]]] = {
    "creative_freelancer": {
        "morning_visit_cafe": [
            "오늘 작업할 카페 어디로 가지",
            "감성 있는 곳이 좋겠다",
            "와이파이 좋은 곳",
            # ... 30개
        ],
        "lunch_decide": [
            "가까운 곳 빨리",
            "오늘은 디저트도 같이",
            # ... 30개
        ],
        # situation 5종 × 30 = 150 한국어 문장
    },
    "office_worker": { ... },     # 30 archetype × 시간대 4 × 상황 5 = 600 한국어 문장
    # ... (Nemotron-Personas 30 archetype)
}

def pick_dialog(archetype: str, situation: str, hour: int, rng: random.Random) -> str:
    """archetype + situation 에서 한국어 짧은 문장 1개 sample."""
    bucket = TEMPLATES.get(archetype, {}).get(situation, ["..."])
    return rng.choice(bucket)
```

**사용처**:
- `agents.py:435` 의 `decision.reason` 자리 → 결정 시점에 `pick_dialog(archetype, situation, hour, rng)` 호출
- `world.event_log` 에 `{agent_id, hour, dialog: "..."}` 누적 (현재 인프라 그대로 활용)
- `evaluate_vacancy_pse` 결과 `visits_events` 에 dialog 메시지 포함 (`dump_visits=True` 시)

**테스트** (`tests/test_dialog_templates.py`):
- 30 archetype 모두 5 situation 정의되어 있는지 (coverage)
- pick_dialog 가 archetype/situation 모르는 경우 fallback 동작
- random seed 고정 시 재현성

### 10.4 Mode C — Tier S 50명 LLM (가용 시)

**활성 조건** (`evaluate_vacancy_pse(enable_llm=True, llm_tier_policy="S_only")`):
- Tier S 50명: GPT-4.1 mini, max_tokens 30, 4시간마다 호출
- Tier A 200명 + Tier B 750명: template (옵션 2 와 동일)

**비용** (운영, days=1, N=5 PSE):
- Tier S 호출 수 = 50 × 6 × 5 = 1,500 호출
- prompt 1400 token (1024+ → cache 활성), 변동 50, 출력 30
- 호출당: 1400×$0.10/1M + 50×$0.40/1M + 30×$1.60/1M = $0.000208
- **운영 1회: 1,500 × $0.000208 = $0.31**
- 일 100회 평가: $31 — 부담 없음

**Rate limit**:
- GPT-4.1 mini Tier 5: 30,000 RPM
- 운영 1회 1,500 호출 → 10초 안에 완료 가능 (3,000 RPS)
- Tier 1 (60 RPM) 이면 25초. **Tier 1 도 OK**

**환경 변수** (옵션 3 활성 조건):
- `OPENAI_API_KEY` 가 있으면 활성, 없으면 자동 fallback (template only)
- `vacancy_pse` 의 `enable_llm=True` + `cfg.tier_s_provider="openai"` + 키 존재 시만 진짜 호출

**검증은 Mode C 도 미사용** — 검증 protocol 은 항상 mock + template 강제 (비용 $0).

### 10.5 prompt 설계 (Mode C 활성 시 GPT-4.1 mini 호출)

OpenAI prompt cache 활용 위해 **1024+ token prompt** 강제:

```python
# 1400 token persona + context
PROMPT = """
당신은 마포구에 사는 {agent_name} ({age}세, {gender})입니다.
타입: {archetype_label}
특성: {archetype_traits}
소비 패턴: {spending_pattern}
선호 동: {preferred_dongs}
거주: {home_dong}
소득 수준: {income_level}/3
오늘 예산: {budget}원

[Layer 2] 어제까지 기억:
{memory_layer_2}   # ~300 token

[Layer 3] 친구 추천:
{memory_layer_3}   # ~200 token

현재: {hour}시, {weekday}, 날씨 {weather}, 위치 {current_dong}

응답: JSON 짧게. {"action": "visit|move|rest", "target_dong": "...", "spend": ..., "reason": "한 문장"}
"""

# 변동 (cache miss): 50 token = 매장 후보 3개
# - 매장 A (서교동, 거리 200m, 평점 4.3, 이디야)
# - 매장 B ...
```

→ 1400 fixed (cache hit, 90% 할인) + 50 variable + 30 output = 호출당 $0.000208.

### 10.6 자동 fallback chain

```
enable_llm=True + OPENAI_API_KEY 있음 + Tier S 분류
  → GPT-4.1 mini 호출
enable_llm=False (default) 또는 키 없음 또는 Tier A/B 분류
  → use_dialog_templates=True (default)
  → pick_dialog(archetype, situation) 사용 → reason 필드에 set
use_dialog_templates=False (특수 경우)
  → reason 필드 빈 문자열 (또는 정책 명 그대로)
```

### 10.7 Phase 진행

| Phase | LLM | 비용 | 본 spec? |
|---|---|---|---|
| **Phase 1 (본 spec)** — 메뉴 가격 + 검증 + Mode B default + Mode C 인터페이스 | template + (선택) Tier S 50 | $0~$0.3/평가 | ✅ |
| Phase 2 (별도 spec) — 비동기 LLM 인프라 (brain.py asyncio + batch + rate limit) | — | — | ❌ |
| Phase 3 (별도 spec) — 1000명 LLM 활성 + 시각화 chats 노출 | 1000명 GPT-4.1 mini | $6/평가, $672/검증 | ❌ |

## 11. Limitations & Future Work

### 11.1 본 spec 의 명시적 한계

1. **정적 시뮬 환경** — 90일 동안 같은 날씨/같은 월/같은 trend 로 반복. `runner.py:499` 의 `world.month = sim_start.month` 1회 set, `_load_weather_recent()` 도 1회 set. 평일/주말 cycle 만 변동. → V1a/V1b 의 시스템적 bias 가능성. 검증 ground truth 를 multi-quarter (4분기) 평균으로 일부 상쇄.

2. **매장 단위 실측 매출 부재** — DB / 외부 자료 모두 매장당 분기/연 매출 X. V1c 는 동×업종 평균과 비교 (브랜드 단위 검증 X). 진짜 매장 단위 검증은 가맹본부 POS 데이터 필요.

3. **`monthly_sales` / `monthly_count` 컬럼명 misleading** — 실제로 분기 단위. 서울 열린데이터 원본이 분기 매출. spec 본문에서 명시.

4. **PSE N=3 의 통계적 한계** — 학계 표준 N≥3 통과하지만 N=5 보다 CI 폭 ~30% 넓음. 시간 부담 trade-off.

5. **마포 0매장 브랜드 (예: 스타벅스) 평가 불가** — `BrandNotFoundError`. fallback chain 의도적 제거.

6. **자연어 대화의 다양성 제한 (Mode B)** — Template 600 한국어 문장은 반복 가능. 진짜 다양성 자연어는 Mode C/D 의 LLM 활성 시 가능. 시각화 chats 데이터 가독성에 영향 가능.

7. **Mode C 활성 검증 부재** — 검증 protocol 은 mock/template 만 사용. LLM 활성 시 결정 분포가 측정값을 약간 변화 가능 (margin ~3% 추정, but 실측 안 함). future spec 에서 Mode C 활성 검증 측정 권장.

### 11.2 Future Work

**시뮬 시간 변동 (brainstorm 옵션 3) — 별도 spec 권장**:

본 spec 진행 후 시뮬 시간 변동으로 갈 때 사전 작업 필요:
- `weather_daily` 의 마포 90일 데이터 가용성 점검 (현재 어느 기간 있는지 미확인)
- 일별 트렌드 source 부재 — SNS sentiment 일별 데이터 검토
- `score_store` 의 `month` 가중치 함수 활성화 여부 확인 (현재 month 가 1번 set 되니 day-loop 안에서 실제 영향 주는지 검증)
- 본 spec 합격선 (r ≥ 0.85 등) 은 정적 baseline 기준 → 시뮬 시간 변동 spec 첫 task 로 새 baseline + 5% margin 으로 재산출

시뮬 시간 변동 spec 진행 시 본 spec 의 인프라 (`brand_menu_loader`, `brand_vacancy_validator`, 5트랙 protocol) 100% 재사용 가능. 합격선 수치만 갱신.

**Phase 2 — 비동기 LLM 인프라 (별도 spec)**:

Mode D (1000명 LLM) 활성을 위해:
- `brain.py` 비동기화 (asyncio + httpx)
- 시뮬 day-loop 안 batch LLM 호출 (한 시간대 1000명 동시 → batch API)
- Rate limit 처리 (token bucket + retry-after)
- 비용 모니터링 dashboard
- 추정 시간 6~8일 작업

**Phase 3 — 1000명 LLM + 시각화 chats (별도 spec)**:

Phase 2 완료 후:
- 운영 vacancy_pse 에서 Mode D 옵션 활성
- chats 데이터 frontend 노출 (`/vacancy-evaluation/{job_id}/chats` endpoint)
- 비용: 운영 $6/평가, 검증 $672/회 — 사용자 비용 합격선 결정 필요

**시각화 frontend 페이지 — 별도 spec**:

본 spec 의 `collect_trajectory` / `dump_visits` 인터페이스 위에:
- 새 API endpoint (`/vacancy-evaluation/{job_id}/trajectory`, `.../visits`, `.../chats`)
- frontend 페이지: 마포 지도 + 1000 ag 시간대별 dot + spot 강조 + 시간 슬라이더 + 대화 말풍선
- 사용자 본인 또는 C1 강민이 진행

## 12. 변경 영향 / 호환성

### 12.1 기존 호출자 회귀 영향

| 호출자 | 영향 |
|---|---|
| `vacancy_evaluation_service.evaluate_top_vacancies` 의 기존 호출 (brand_name 없이) | **영향 X** — brand_name=None 기본값, 기존 동작 그대로 |
| `vacancy_pse.evaluate_vacancy_pse` 의 기존 호출 | **영향 X** — menu_items=None, collect_trajectory=False 기본값 |
| `vacancy_inject.inject_vacancy_as_store` 의 기존 호출 | **영향 X** — menu_items=None 기본값 |
| LangGraph 시나리오 / `district_ranking` 노드 | **영향 X** — 기존 인자만 사용 |
| Frontend 의 기존 API 호출 | **영향 X** — 응답 구조 확장만 (필드 추가, 기존 필드 유지) |

### 12.2 DB 변경

**없음**. 기존 테이블 (`kakao_store_menu`, `kakao_store`, `district_sales`, `sales_imp_mapo`, `ftc_brand_franchise`) 만 사용. 새 테이블/컬럼 X.

CLAUDE.md 의 "DB 테이블 네이밍 규칙" 무관 (새 테이블 X).

## 13. 사전 검증 체크리스트 (구현 전)

- [ ] `kakao_store_menu` 의 row 수 확인 (충분한지: 마포 브랜드별 100+ 메뉴 row)
- [ ] `ftc_brand_franchise` 의 마포 주요 브랜드 (이디야, MEGA, 빽다방, 스타벅스) coverage 확인
- [ ] `sales_imp_mapo.csv` 의 store_count 컬럼 NaN/0 비율 (V1c 의 cell coverage)
- [ ] `district_sales` 의 마포 64-cell 최근 분기 row 완전성
- [ ] `brand_mapping_resolver.get_all_mapo_stores_by_brand` 의 alias 매핑 (이디야 vs Ediya vs EDIYA)
- [ ] 시뮬 days=90 × N=3 의 메모리/시간 부담 환경 검증 (1회 ~9시간 가능 환경)
- [ ] Mode B template — Nemotron-Personas 30 archetype 의 정확한 archetype_id 리스트 확인 (`personas.py` 또는 `archetypes.py`)
- [ ] Mode C 사전 — `OPENAI_API_KEY` 환경 변수 가용성 (Mode C 활성 시만 필요, 없으면 자동 fallback)

## 14. 구현 순서 (writing-plans 단계에서 plan 으로 분해)

1. `services/brand_menu_loader.py` 신규 + 단위 테스트
2. `vacancy_inject.inject_vacancy_as_store` 에 `menu_items` 인자 추가 + 단위 테스트
3. **`simulation/dialog_templates.py` 신규** — 30 archetype × 600 한국어 문장 + 단위 테스트 (Mode B default 활성)
4. `vacancy_pse.evaluate_vacancy_pse` 에 `menu_items`, `collect_trajectory`, `dump_visits`, `use_dialog_templates`, `enable_llm`, `llm_*` 인자 추가 + 통합 테스트
5. `vacancy_evaluation_service.evaluate_top_vacancies` 에 `brand_name` 인자 추가 + 통합 테스트
6. `validation/brand_vacancy_validator.py` 신규 (5트랙 protocol) + 단위 테스트
7. CLI entry point + 일괄 실행 옵션
8. 사전 검증 체크리스트 항목 검증
9. 사용자 결정 브랜드 (예: 이디야) 1회 검증 실행 → report 산출 → production-ready 여부 정직 판정

## 15. 합격 기준 (본 spec 의 done 정의)

- 모든 단위 테스트 통과 + 통합 테스트 통과
- 기존 vacancy_pse 호출 회귀 없음 (기존 테스트 통과)
- 사용자 결정 브랜드 1개에 대해 5트랙 검증 1회 완료 (production-ready or production-not-ready 정직 판정 + 진단 메시지)
- report 가 `validation/results/` 에 dump 되어 있음 (JSON + Markdown)
- design doc + plan + 코드 변경 모두 커밋

production-ready 합격 자체는 본 spec 의 done 조건이 아님. **정직한 판정 + 진단** 자체가 deliverable.

## 16. 학술 / 뉴스 인용 (근거 자료)

본 spec 의 design 결정 (특히 LLM 회의론, Mode B default, Phase 진행) 의 학술/업계 근거.

### 16.1 학술 논문

- **Park et al. 2023** — "Generative Agents: Interactive Simulacra of Human Behavior". arxiv 2304.03442. ACM UIST 2023.
  - 25명 LLM 에이전트 baseline. 비용 thousands of dollars 보고.
- **Park et al. 2024** — "Generative Agent Simulations of 1,000 People". arxiv 2411.10109. Stanford HAI.
  - 1,052명 LLM 시뮬 (본 spec 과 같은 규모). 사회과학 benchmark 85% 정확도. 페르소나 = 2시간 인터뷰.
- **Affordable Generative Agents** — arxiv 2402.02053 (2024).
  - **본 spec Mode B (Policy + Template) 의 직접 학술 근거**. LLM 비용 절감 + hybrid 방향.
- **Tsinghua-FIB-Lab Survey** — "Large Language Models Empowered Agent-based Modeling and Simulation: A Survey and Perspectives". Nature Humanities & Social Sciences Communications 2024. arxiv 2312.11970.
  - LLM ABM 의 strengths (다양성/자연어) vs limitations (비용/일관성/재현성).
- **LLM-Augmented ABM Literature Review** (2024) — Challenges and Opportunities. themoonlight.io.
  - LLM-driven ABM 의 도전 과제 종합.
- **LLM-Based Multi-Agent System for Marketing/Consumer Behavior** — arxiv 2510.18155, ICEBE 2025.
  - 상업 시뮬 + 소비자 행동 (본 spec 과 가장 가까운 도메인). 11ag + 10 location.

### 16.2 GeekNews 한국 articles

- **[AI 에이전트 개발을 멈추고, 더 똑똑한 LLM 워크플로우를 써라](https://news.hada.io/topic?id=21853)**
  - 본 spec Mode B 의 직접 일치 — "agent 라기보다 workflow + LLM optional".
- **[효과적인 AI 에이전트 구축 (Anthropic 가이드)](https://news.hada.io/topic?id=21520)**
  - "단순 작업은 workflow, 복잡 작업만 agent" — LLM 사용 절제 강조.
- **[OpenAI의 에이전트 구축을 위한 실용 가이드](https://news.hada.io/topic?id=27459)**
  - LLM agent 비용/안정성 trade-off.

### 16.3 본 spec 의 정직한 학술 위치

| 측면 | 본 spec | 학술/뉴스 근거 |
|---|---|---|
| 1000ag 시뮬 LLM 없이 가능? | ✅ Mode B 로 가능 | Affordable Generative Agents 의 비용 절감 방향 |
| 매출 정확도 검증 LLM 필요? | ❌ Policy 의 결정 logic dominant | Tsinghua survey: LLM 은 다양성, 결정은 rule-based |
| 비용 thousands of dollars | ❌ Mode B = $0, Mode C = $0.3/평가 | Park 2024 의 비용 vs 본 spec 의 절감 |
| Phasing (Policy → Template → LLM) | ✅ 점진적 도달 | GeekNews "agent 보다 workflow 우선" |
| 자연어 대화 시각화 | template 우선, LLM future | hardcoded NLG 의 안정성 + 비용 |

→ 본 spec 의 Mode B + 가용 시 Mode C 전략은 **학술 입증 + 업계 best practice 와 일치**.

---

## 변경 로그

| 날짜 | 작성자 | 변경 |
|---|---|---|
| 2026-04-27 | A1 (찬영) | 초기 design 작성 (brainstorm 결과 종합) |
| 2026-04-27 | A1 (찬영) | LLM 호출 정책 섹션 (10) + 학술 인용 섹션 (16) 추가. Mode B default + Mode C 가용 옵션. brainstorm 옵션 vs LLM mode 명명 충돌 해결. |
