# NULL + Orphan + Categorical 잘못된 값 전수 감사 (2026-05-04 v2)

> 분석: backend/src 코드 + DB 실측 (information_schema + 컬럼별 NULL 분포 + FK orphan)
> 범위: PR #178~#182 머지 후 상태 (88→87 테이블, alembic head=91b66e68ec18)

---

## 1. 요약 (Top 10 위험)

| # | 항목 | 위치 | 위험도 | 권장 fix |
|---|---|---|---|---|
| 1 | `fetchone()` 결과 None 미검증 | `agents/tools.py:480, 573` | **HIGH** | `if row is None: return ...` |
| 2 | `fetchone()[0]` 직접 인덱싱 | `scripts/create_test_user.py:90, 169` | **HIGH** | `r = .fetchone(); if r: id = r[0]` |
| 3 | `scenario.new_store.get(...)` chain — new_store=None 시 AttributeError | `simulation/runner.py:537-565` | **HIGH** | `if scenario.new_store: ...` |
| 4 | `auth.py:883/895` f-string `{table}` 동적 + role 검증 | `services/auth.py` | **HIGH** | `CASE WHEN role` 또는 dispatch dict |
| 5 | `business_type` 입력 검증 부재 (`SimulationInput` Pydantic) | `schemas/simulation_input.py:19` | **HIGH** | `Literal[10종]` 또는 `enum.Enum` + validator |
| 6 | `lat/lon` 범위 검증 없음 (마포 외 좌표 통과) | `schemas/simulation_input.py:46-49` | MED | `Field(ge=37.5, le=37.65), Field(ge=126.85, le=126.95)` |
| 7 | `quarter` 형식 검증 부재 (문자열 "2024Q1" 입력 시 캐스트 실패) | `database/models.py:134/147` | MED | Pydantic `@validator` 정수형 강제 |
| 8 | `evaluate.py:35` `.get(code, code)` fallback 입력값 그대로 — 잘못된 코드 통과 | `evaluate.py:35` | MED | `cs_code_of()` 헬퍼 사용 |
| 9 | LLM 출력 `market_entry_signal` schema mismatch (예: "Green"/"초록") | `agents/nodes/competitor_intel.py:461` | MED | LLM 사후 검증 + fallback |
| 10 | `dong_code` 미매핑 시 fallback 없음 — `resolve_dong_code(None)` chain 깨짐 | `services/dong_resolver.py:26-43` | MED | `.strip()` + fuzzy match + 명시적 로깅 |

---

## 2. SQL 결과 NULL 미처리

### Critical (`fetchone()` 후 직접 attr/index 접근)

```python
# tools.py:480 — row 가 None 일 수 있음
row = (await session.execute(...)).fetchone()
revenue = row.monthly_sales  # ⚠️ AttributeError 위험

# tools.py:573 — 동일 패턴
sample = int(row.n or 0)  # row=None 시 AttributeError

# scripts/create_test_user.py:90
new_id = conn.execute(text("INSERT ... RETURNING id")).fetchone()[0]
# fetchone()=None 시 TypeError
```

**Fix 패턴**:
```python
row = result.fetchone()
if row is None:
    return None  # 또는 적절한 default
revenue = row.monthly_sales
```

### `.scalar()` (단일 값) — 양호

`tools.py:405, 453, 601, 613, 623` 모두 `is None` 검증 후 사용 — OK.

---

## 3. dict.get() 매핑 누락 시 잘못된 fallback

### 매핑 미스 입력값 흐름

| 입력 | normalize_key 결과 | 후속 영향 |
|---|---|---|
| `"기타 외식"` | `None` | `get_entry(None)` → None → caller fallback 부재 시 crash |
| `"음료 (커피 외)"` | None | by_cs_code 역조회 실패, naver_industry 매칭 실패 |
| `"피자"` | `"패스트푸드"` (alias) | OK ✓ |
| 사용자 typo (공백/특수문자) | None | LLM fallback 의존 |

### `evaluate.py:35` 위험

```python
code = _BUSINESS_TYPE_TO_CODE.get(industry_m_code, industry_m_code)
# fallback 이 입력값 그대로 — "기타 외식" 같은 미매핑 값 그대로 DB 쿼리 → 0 row
```

**Fix**: `cs_code_of(industry_m_code) or "CS100010"` (default 명시).

---

## 4. JSON 컬럼 처리

| 위치 | 안전도 |
|---|---|
| `database/redis_client.py:54` — None 검증 후 json.loads | ✅ SAFE |
| `main.py:2141` — Redis get 조건 있음 | ✅ MED-OK |
| `simulation/brain.py:558,764,989` — text=None/empty 시 JSONDecodeError | ⚠️ MED |
| `agents/nodes/district_ranking.py:799` — cached upstream 검증 필요 | ⚠️ MED |

---

## 5. Pydantic 입력 검증 강화 권장

### `SimulationInput` 현재

```python
class SimulationInput(BaseModel):
    business_type: str          # ❌ 자유 문자열
    target_district: str        # ❌ 자유 문자열
    quarter: int                # OK (int)
    lat: float | None = None    # ❌ 범위 없음
    lon: float | None = None    # ❌ 범위 없음
```

### 권장

```python
from typing import Literal
from pydantic import Field, field_validator

class SimulationInput(BaseModel):
    business_type: Literal["한식","중식","일식","양식","제과","패스트푸드","치킨","분식","호프","커피"]
    target_district: str  # 별도 validator 로 16동 + alias 검증
    quarter: int = Field(ge=200001, le=210004)  # YYYYQ 형식
    lat: float | None = Field(default=None, ge=37.5, le=37.65)  # 마포 범위
    lon: float | None = Field(default=None, ge=126.85, le=126.95)

    @field_validator("target_district")
    @classmethod
    def _normalize_district(cls, v: str) -> str:
        from src.config.constants import MAPO_DISTRICTS
        v = v.strip()
        if v in MAPO_DISTRICTS or v in {"망원동","성산동","상수동"}:
            return v
        raise ValueError(f"unknown district: {v}")
```

---

## 6. DB 실측 (information_schema + 컬럼별 COUNT)

### 6.1 ✅ 무결 항목

- **Orphan FK: 0건** — 정의된 44개 FK constraint 모두 무결 (orphan row 없음)
- **`industry_code` 정합**: FK 미정의 테이블 (district_sales_seoul, imputed_v4, imputed_v4_detail) 모두 industry_master 의 101개 코드 안에 있음
- **`dong_code` 정합**: 미정의 테이블 (imputed_v4 시리즈) 모두 dong_mapping ∪ seoul_dong_master 안에 있음

### 6.2 🔴 100% NULL 컬럼 (정의됐지만 적재 0)

| 테이블 | 컬럼 | row | 영향 |
|---|---|---|---|
| **`rent_cost`** | `transaction_date, price, floor_area, floor` (4 컬럼 전부) | 248 | **테이블 자체 사용 불가** — 임대 가격 데이터 0 |
| **`kakao_store_hours`** | `mon_hours~sun_hours` (요일 7개) | 3,995 | **요일별 영업시간 미적재** — `headline_text` 만 활용 가능 |
| **`master_ttareungi_station`** | `dong_code, lat, lon, opened_at` | 5,541 | **마스터 빈 껍데기** — 따릉이 위치 기반 분석 불가 |
| **`seoul_realtime_hotspots`** | `cmrc_total_level, cmrc_payment_cnt, cmrc_payment_amt_min/max` | 1,876 | **상거래 핫스팟 핵심 컬럼 0** |
| **`dong_mapping`** | `floating_pop, avg_age, total_households, trdar_codes` | 16 | 마포 마스터의 인구·연령·가구·상권 메타 0 |
| `district_sales_seoul.raw_json` | 100% | 475,334 | raw 보존용 컬럼 미사용 |
| `living_population.male_70_74, female_70_74` | 100% | 968,064 | **`_70_plus` 와 중복 컬럼** — 스키마 결함 |
| `master_subway_station.sigungu_code, lat, lon` | 89.4% | 292 | 261건 좌표 없음 |
| `industry_master.industry_name_alt` | 100% | 101 | alt 표기 미사용 (제거 가능) |
| `weather_daily.snow_new` | 100% | 2,665 | 적재 누락 |
| `molit_nrg_trade.realty_type` | 100% | 8,731 | 적재 누락 |
| `seoul_dong_master.comment` | 100% | 431 | 미사용 |
| `ecos_timeseries.item_name2, cycle` | 100% | 2,783 | ECOS API 응답 미파싱 |
| `invite_codes.expires_at` | 100% | 16 | 만료 미설정 (영구 invite) |

### 6.3 🔴 50~99% NULL (대량 누락)

| 테이블 | 컬럼 | NULL% | row |
|---|---|---|---|
| **`kakao_store.brand_name`** | 브랜드 매핑 | **72.8%** | 4,413 (3,214 미매핑) |
| `mart_brand_territory.extraction_confidence` | 100% | 11,822 | 신뢰도 미적재 |
| `mart_brand_territory.territory_distance_m` | 98.1% | 11,822 | 거리 미적재 (11,596) |
| `mart_brand_territory.territory_text` | 97.5% | 11,822 | 영업지역 텍스트 미적재 |
| `kakao_store_menu.description` | 92.3% | 81,037 | 메뉴 설명 누락 |
| `kakao_store_menu.photo_url` | 87.0% | 81,037 | 사진 URL 누락 |
| `holiday_calendar.holiday_name` | 94.9% | 3,287 | (정상 — 비공휴일 row 다수) |
| `weather_daily.snow_max` | 96.4% | 2,665 | (정상 — 강설 0 day) |
| `jeonse_monthly_rent.renew_right_used` | 89.2% | 168,342 | 갱신권 사용 정보 부족 (정상 가능) |
| `jeonse_monthly_rent.prev_monthly_rent` | 85.4% | 168,342 | 이전 임대료 미공개 (정상) |
| `master_subway_station.sigungu_code/lat/lon` | 89.4% | 292 | **마포 외 261개 좌표 없음** |
| `weather_daily.rain_60m_max` | 73.8% | 2,665 | (정상 — 강우 0 day) |
| **`simulation_ai.market_entry_signal`** | **66.7%** | 3 (2 NULL) | 신호 적재 누락 — 코드 검증 필요 |
| `simulation_foresee.bep_months` | 75.0% | 4 (3 NULL) | BEP 미계산 |
| `store_info.building_name` | 54.2% | 30,488 | 건물명 미수집 (정상 가능) |

### 6.4 🟡 빈 문자열 vs NULL 혼재 (8건)

| 테이블.컬럼 | empty 수 | NULL 정책 위반 |
|---|---|---|
| `ecos_timeseries.item_code2` | 2,783 | (전체 row 가 empty — 차라리 NULL 권장) |
| `kakao_store.phone` | 1,071 | 통일 (NULL 또는 빈문자) 필요 |
| `kakao_store.road_address` | 16 | 동일 |
| `law_legislations.law_short_name` | 34 | |
| `law_precedents.body_text` | 4 | |
| `law_precedents.court_name` | 88 | |
| `law_precedents.judgment_type` | 88 | |
| `law_precedents.sentence` | 89 | |
| `molit_nrg_trade.cdeal_day` | 8,014 | (전체 row — 차라리 NULL 권장) |
| `molit_nrg_trade.cdeal_type` | 8,014 | (전체 row) |
| `molit_nrg_trade.floor` | 5,440 | |
| `molit_nrg_trade.build_year` | 1,015 | |

### 6.5 🟡 living_population_grid 다수 NULL (정상 가능)

10.5M rows × 연령/성별 28 컬럼 — `m_0_9` 71% NULL ~ `m_50_54` 32.6% NULL. 격자 단위라 일부 격자 인구 0인 게 정상. 단 분석 시 NULL 처리 통일 (NULL=0 가정) 필요.

---

## 6.6 ✅ Backfill 적용 (이번 PR)

`backend/scripts/diagnostics/backfill_master_meta.py` 작성 + 실행. derive 가능한 메타 채움:

| 컬럼 | 채움 | 출처 |
|---|---|---|
| `dong_mapping.floating_pop` | **16/16** ✅ | `living_population` AVG(total_pop) per dong |
| `dong_mapping.avg_age` | **16/16** ✅ | `living_population` 연령대(28컬럼) 가중평균 |
| `dong_mapping.total_households` | **12/16** ✅ | `sgis_household` indicator='total_households' 2024 |
| `industry_master.industry_name_alt` | **10/101** ✅ | `BUSINESS_TYPE_MAPPING.label_en` (CS100001~CS100010) |

샘플 결과:
- 서교동 floating_pop = 71,445 (vs 주민등록 23,809) — 홍대 상권 합리적
- 상암동 floating_pop = 48,093 (vs 29,478) — DMC 합리적
- 서교동 avg_age = 36.2 (홍대 젊은층), 도화동 = 42.5 (주거지) 합리적

남은 NULL (별 작업 필요):
- `dong_mapping.total_households` 4/16 — 행정동 코드 변경 (아현/공덕/도화/서강 = 11440555/565/585/655). sgis 옛 코드 (11440750/760/770/780) 와 매핑 ETL 필요.
- `dong_mapping.trdar_codes` 16/16 — `golmok_*` 에 dong_code 컬럼 없음, trdar↔dong 매핑 테이블 별도 필요.

## 7. 🚨 데이터 품질 Critical 문제 (ETL 점검 시급)

### Top 5 — 코드 의존이 있는 데도 데이터 0

1. **`rent_cost` 248 row 핵심 컬럼 100% NULL** — 임대료 분석 코드가 이 테이블 참조하면 모두 0/None. ETL 적재 실패 또는 마이그레이션 후 데이터 손실.
2. **`kakao_store_hours` 요일별 영업시간 100% NULL** — 영업시간 분석 불가. ETL 의 hours parsing 누락.
3. **`master_ttareungi_station` 5,541 row 의 `dong_code`/`lat`/`lon` 100% NULL** — 따릉이 마스터 자체가 ID 만 있는 빈 껍데기. FK 정합 ✓ (모두 NULL 이라). 사용 불가.
4. **`seoul_realtime_hotspots.cmrc_*` 100% NULL** — 실시간 상거래 데이터 핵심 컬럼 0. ETL 점검 필요.
5. **`kakao_store.brand_name` 72.8% NULL** — 4,413 매장 중 3,214 매장 브랜드 미매핑. `biz_brand_mapping` / FTC 와 fuzzy 매칭 ETL 강화 필요.

### 스키마 결함

- **`living_population.male_70_74`, `female_70_74` 100% NULL** — `male_70_plus` / `female_70_plus` 와 중복 컬럼. 원천 데이터 포맷 변경 흡수용 의도지만 실제로는 새 포맷만 적재됨. **drop column 권장**.
- **`industry_master.industry_name_alt` 100% NULL** — 별칭 표기 컬럼 미사용. drop 또는 활용 결정 필요.
- **`invite_codes.expires_at` 100% NULL** — 만료 정책 부재. 의도적이면 nullable=False 의 default sentinel 도입 또는 column drop.
- **`seoul_dong_master.comment` 100% NULL** — 미사용.
- **`industry_code` 컬럼 dtype mismatch 검토 필요** (FK 정합은 OK).

---

## 7. Action Items 우선순위

### P0 (즉시 fix, 1줄~수줄)
1. `tools.py:480, 573` `fetchone()` 후 None 검증
2. `scripts/create_test_user.py:90, 169` `fetchone()[0]` 안전 패턴
3. `runner.py:537-565` `scenario.new_store` None 검증

### P1 (소규모 PR)
4. `auth.py:883/895` HIGH risk f-string → dispatch dict
5. `SimulationInput` Pydantic Literal + Field range 도입
6. `evaluate.py:35` fallback `cs_code_of()` 적용

### P2 (중규모 PR)
7. `dong_resolver` fuzzy match + 명시적 에러
8. LLM 출력 `Literal` schema 사후 검증
9. JSON 컬럼 read 시 None/empty 가드 통일

### P3 (별 PR)
10. Consumer 마이그레이션 (옛 dict 통합)
11. `relationship()` 도입
12. 미반영 FK 36개 ORM 추가

---

## 갱신 메모

DB 실측 결과 도착 시 `## 6. DB 실측` 섹션에 NULL 분포 / orphan / invalid 추가. 추가 후 audit doc 최종화.
