# 결측 매출 역산 v4 재설계 — 신뢰도 정직화 + ABM 스노우볼 통제 — Design

작성: A1 (찬영) — 2026-04-27
Branch: IM3-243-dong-fk-followup
Status: Design (사용자 검토 대기)

---

## 1. 개요 (한 줄 요약)

마포 137 결측 매출 셀의 **48개 numeric 컬럼 전체** (sales 24 + count 24)를 **Multi-Output ExtraTrees + 6 seed 앙상블 + 95% CI**로 정직 복원하고, **MNAR/KOSIS leak 오류 4종을 수정**하며, ABM popularity 계산에 **confidence 가중**을 전파해 "예측의 예측" 스노우볼을 통제한다.

부수 deliverable: 4종 검증 감사(MNAR/LODO/TS/Q1) + 6개 추가 지표(OoM/F1/MASE/RMSLE/Pearson r/Random)를 6 seed 앙상블 분산까지 반영해 재실행하고, **합계 일관성 raking** post-processing 으로 5종 sum constraint 보장, **production-ready 자동 판정 체계**를 구축한다.

## 2. Product Vision

본 spec 은 더 큰 product vision 의 building block 이다:

> **사용자 가치**: 마포 매출 데이터에 137 결측이 있어 ABM popularity_boost / TCN 시계열 학습 / 사용자 대시보드의 동·업종 매출 표시가 모두 영향을 받음. 이 결측을 **정직한 신뢰구간과 함께** 복원해 다운스트림이 "이 셀은 추정값이고 ±X% 신뢰" 정보를 받아 자체 의사결정에 반영 가능하게 한다.

본 spec 은:
- **검증 방법론 정직화** — 기존 v3 의 4종 leak/오해 수정 (MNAR dong_avg leak, KOSIS 항목 혼합, WAPE를 신뢰구간으로 오해, 단일 시드)
- **다운스트림 인터페이스** — `world_loader._load_dong_industry_weight()` 에 confidence 가중 추가 → ABM popularity 가 외삽 셀 영향 자동 축소
- **5트랙 검증의 ground truth 자격** — 다른 세션의 V1c 검증이 우리 `sales_imp_mapo.csv` 를 ground truth 로 사용하므로, 우리가 1단계 더 엄격해야 그 검증이 신뢰성 가짐

TCN 재학습은 별도 세션에서 진행 중인 brand-menu 작업과의 충돌 회피를 위해 본 sprint 외 (후속 spec).

## 3. 배경 — 현재 시스템과 갭

### 3.1 현재 작동 중인 v3 시스템

- **`reverse_engineer_sales_v3.py`** — KOSIS DT_1KC2023 (서울 숙박·음식점업 서비스업생산지수) anchor + ExtraTrees Optuna 200 trials 튜닝
- **결과**: MNAR WAPE 13.35% (튜닝본), Pearson r 0.99, RMSLE 0.334
- **산출**: `validation/results/imputed_sales_v3.csv` (137 결측 셀의 `monthly_sales` 1개 컬럼만 복원, confidence 0.74 일괄)
- **다운스트림**: `data/processed/sales_imp_mapo.csv` 형태로 다른 세션 5트랙 검증의 V1c ground truth 로 사용 중

**v3 의 한계 (본 spec 핵심 갭):** `district_sales` 테이블의 **48개 numeric 컬럼** 중 `monthly_sales` 1개만 복원 → 나머지 47개 (요일/시간대/성별/연령 세분 sales 23개 + count 24개) 는 NULL. 다른 세션 부록 A 가 사용하는 12개 매출 피처 (weekday/weekend/age 등) 도 결측 셀에서 비어있음.

### 3.2 갭 — 발견된 4종 오류 + 해석 오류 3종

**역산 코드 review 에서 발견:**

| # | 오류 | 위치 | 영향 |
|:--:|:-----|:-----|:-----|
| 1 | **MNAR/LODO CV의 dong_avg leak** | `reverse_engineer_sales_v3.py:86-95` | dong_avg_store / combo_avg_store 가 전체 데이터로 계산된 후 X에 박혀 있어 fold 분리해도 leak. v3 의 MNAR 25.7% 가 1~3%p 낙관 가능 |
| 2 | **KOSIS 항목 혼합** | `probe_kosis_pairing.py:59` + `reverse_engineer_sales_v3.py:57-58` | itmId="ALL" fallback 시 경상지수+불변지수가 평균으로 섞임. anchor 정밀도 저하 |
| 3 | **Audit 단계 음수 예측 미처리** | `reverse_engineer_sales_v3.py:116-120` | clip(0) 이 final_impute_and_save 에서만 적용, CV 평가 단계에선 음수 예측 그대로 → WAPE 미세 왜곡 |
| 4 | **단일 시드 (random_state=42 고정)** | 전 코드 | 표준편차/신뢰구간 없음. v3 가 v2 보다 2~3%p 좋다는 차이가 noise 일 가능 |

**해석 오류 (수치보다 사용 방식 문제):**

| # | 오류 | 위치 |
|:--:|:-----|:-----|
| A | **WAPE = 신뢰구간으로 오해** | `restoration_process_detailed.md:441-446` — "true_sales ∈ [pred×0.743, pred×1.257]" 로 표기. WAPE 는 평균 절대 % 오차이지 95% CI 가 아님 |
| B | **confidence 공식 통계 근거 없음** | `confidence = max(0.60, 1.0 - WAPE/100)` — 직관적이나 확률적 의미 없음 |
| C | **v2 vs v3 의 2~3%p 차이를 유의미한 개선으로 단정** | 단일 시드 + variance 추정 없이 |

### 3.3 다운스트림 스노우볼 분석 결과

이전 분석에서 정량화한 누적 오차:

| 사용 패턴 | Stage 1 | Stage 2 | Stage 3 | 누적 |
|:---------|:-------:|:-------:|:-------:|:----:|
| imputed → 마포 전체 매출 합계 | ±25% | (평균화) | — | ±3% ✅ |
| imputed → ABM popularity → 매장 선택 분포 | ±25% | (정규화) | (가중치) | ±2% ✅ |
| imputed → ABM 신규 매장 매출 추정 | ±25% | ±10% | ±20% (샘플) | ±35% ⚠️ |
| imputed → 단일 셀 BEP/폐업 단정 | ±25% | — | — | ±25% + 임계값 위험 ❌ |

→ 본 spec 은 (1) 절대 오차 자체를 줄이고, (2) confidence 를 다운스트림에 전파해 위 ⚠️/❌ 경로의 위험을 통제한다.

## 4. 명확화 결정 기록 (brainstorm 결과)

| # | 결정 항목 | 선택 | 이유 |
|:--:|:--|:--|:--|
| Q1 | 재설계 범위 | **B + C** (검증 방법론 + 데이터 수집 둘 다) | 모델만 바꿔서는 leak/해석 오류 안 풀림 |
| Q2 | 성공 기준 | **B + D** (신뢰도 정직성 + 다운스트림 실측 성능) | (A) 정확도 자체는 13% 벽이 작은 셀 한계로 어려움. (C) 외부 자료는 통제 밖 |
| Q3 | 시간 제약 | **B (1주 sprint)** | (A) 3일은 모자람, (C/D) 외부 자료는 응답 지연 |
| Q4 | 다운스트림 범위 | **(D) - TCN = imputed + ABM** | TCN 은 다른 세션 충돌 회피. ABM 은 우리 통제 가능 |
| Q5 | 다른 세션 영역 | **brand-menu + 5트랙 검증** | 같은 브랜치, 같은 owner. `sales_imp_mapo.csv` 가 V1c ground truth |
| Q6 | 신뢰구간 산출 | **6 seed 앙상블** | 1주 안에 가능, 5트랙 V1c 가 lower/upper 직접 활용 가능 |
| Q7 | 학습 path | **D (사전 실험 후 결정)** — 마포 단독 vs 서울→마포 vs Hybrid | Phase B 서울 imputed (28.83%) 결과는 "전체 imputed" 이지 "서울 학습 → 마포 예측" 결과가 아님. 미측정 |
| Q7-2 | 24분기 전체 결측 셀 | **(C) confidence 강제 ≤ 0.4** | (B) NaN 유지는 다른 세션 V1c cell coverage 저하. (D) 별도 컬럼은 다른 세션 코드 수정 필요 |
| 합격선 | **엄격** (MNAR ≤ 15%, Pearson r ≥ 0.97, OoM ≥ 97%) | Ground truth 로 쓰이므로 다운스트림보다 1단계 엄격 |

## 5. 아키텍처 / 컴포넌트

### 5.1 high-level 흐름

```
[Phase 0 — 사전 실험 0.5일]
  ┌─────────────────────────────────────┐
  │ 0-1. KOSIS 항목 분리 (경상/불변/혼합)│
  │ 0-2. dong_avg LOO leak 수정         │
  │ 0-3. 3 학습 path 비교                │
  │   → 합격 path 결정                    │
  └─────────────────────────────────────┘
            ↓
[Phase 1 — 본 학습 1.5일]
  6 seed × ExtraTrees Optuna 200 trials
  → predict_with_ci → mean ± 1.96·std
  → detect_extrapolation_cells
  → calculate_confidence
  → imputed_mapo_v4.csv ⭐
            ↓
[Phase 2 — 감사 재실행 1일]
  4종 CV (Random/TS/MNAR/LODO) × 6 seed
  + 추가 6 지표 (Pearson r/RMSLE/OoM/F1/MASE/Q1)
  → audit_v4_report.md
  → 합격 시 Phase 3, fail 시 confidence 일괄 0.10 하향
            ↓
[Phase 3 — ABM 통합 1.5일]
  seoul_district_sales_imputed_v4 테이블 적재
  world_loader._load_dong_industry_weight() 수정
    → confidence 가중 popularity 계산
  다른 세션 회귀 테스트 통과 확인
            ↓
[Phase 4 — Sensitivity 0.5일]
  ABM 시뮬 2회 (imputed 사용 vs 미사용)
  → popularity 분포 + 매장 선택 분포 비교
  → sensitivity_v4_report.md
            ↓
[Phase 5 — 통합 1일]
  data/processed/sales_imp_mapo.csv ← v4
  다른 세션 5트랙 V1c 1회 실행 → 결과 확인
```

### 5.2 컴포넌트 표

| 컴포넌트 | 위치 | 신규/수정 | 책임 |
|:---|:---|:---|:---|
| `probe_kosis_item_split.py` | `scripts/` | **신규** | KOSIS DT_1KC2023 의 itm_id 별 anchor + Pearson r 측정 |
| `audit_dong_avg_leak.py` | `validation/` | **신규** | MNAR/LODO CV 에서 dong_avg LOO 적용 후 WAPE 변화 측정 |
| `compare_learning_paths.py` | `validation/` | **신규** | 3 path × 6 seed × MNAR-mimic CV 비교 |
| `reverse_engineer_sales_v4.py` | `validation/` | **신규** | 본 학습 — 6 seed 앙상블 + 95% CI + confidence |
| `audit_v4.py` | `validation/` | **신규** | 4종 CV + 6 추가 지표 6 seed 평균 측정 |
| `sensitivity_v4_abm.py` | `validation/` | **신규** | imputed 사용/미사용 ABM 시뮬 비교 |
| `exceptions.py` | `validation/` | **신규** | 8종 예외 클래스 |
| `_load_dong_industry_weight()` | `backend/src/simulation/world_loader.py` | **수정** | LEFT JOIN seoul_district_sales_imputed_v4 + confidence 가중 |
| 단위 테스트 4종 | `tests/`, `backend/tests/` | **신규** | imputed_v4 / audit_v4 / world_loader confidence / 다른 세션 회귀 |

### 5.3 책임 경계

- `probe_kosis_item_split` — KOSIS API + DB 마포 매출만 안다. 학습 모델, ABM 모름
- `compare_learning_paths` — 3 path 학습 + MNAR CV. confidence, ABM 모름
- `reverse_engineer_sales_v4` — 본 학습 + 6 seed + 95% CI. ABM, sensitivity 모름
- `audit_v4` — v4 결과 CSV + 4종 감사 + 추가 지표. ABM, sensitivity 모름
- `sensitivity_v4_abm` — v4 CSV + ABM 시뮬 (read-only). 학습 로직 모름
- `world_loader` 수정분 — confidence 컬럼 + popularity 가중. 학습 로직, audit 모름

### 5.4 새 시그니처

```python
# validation/reverse_engineer_sales_v4.py (신규)

SEEDS = [42, 2026, 7, 13, 99, 1234]

# 48 컬럼 정의
SALES_COLS = [
    "monthly_sales", "weekday_sales", "weekend_sales",
    "mon_sales", "tue_sales", "wed_sales", "thu_sales", "fri_sales", "sat_sales", "sun_sales",
    "time_00_06_sales", "time_06_11_sales", "time_11_14_sales",
    "time_14_17_sales", "time_17_21_sales", "time_21_24_sales",
    "male_sales", "female_sales",
    "age_10_sales", "age_20_sales", "age_30_sales",
    "age_40_sales", "age_50_sales", "age_60_above_sales",
]   # 24
COUNT_COLS = [c.replace("_sales", "_count") for c in SALES_COLS]   # 24
TARGET_COLS = SALES_COLS + COUNT_COLS   # 48

# 합계 일관성 5종 (sales 기준, count 동일 적용)
SUM_CONSTRAINTS = [
    (["weekday_sales", "weekend_sales"],                         "monthly_sales"),
    ([f"{d}_sales" for d in ["mon","tue","wed","thu","fri","sat","sun"]], "monthly_sales"),
    ([f"time_{t}_sales" for t in ["00_06","06_11","11_14","14_17","17_21","21_24"]], "monthly_sales"),
    (["male_sales", "female_sales"],                             "monthly_sales"),
    ([f"age_{a}_sales" for a in ["10","20","30","40","50","60_above"]], "monthly_sales"),
]

def fit_seed_ensemble_multi(
    X: pd.DataFrame,
    Y: pd.DataFrame,    # shape (n_alive, 48)
    seeds: list[int],
    best_params: dict,
) -> list[MultiOutputRegressor]:
    """6 seed × MultiOutputRegressor(ExtraTrees) — 48 컬럼 동시 학습."""
    return [
        MultiOutputRegressor(
            ExtraTreesRegressor(**best_params, random_state=s),
            n_jobs=-1,
        ).fit(X, Y) for s in seeds
    ]

def predict_with_ci_multi(
    models: list[MultiOutputRegressor],
    X_missing: pd.DataFrame,
    store_count: np.ndarray,
) -> dict[str, pd.DataFrame]:
    """6 seed × 48 컬럼 예측 → 각 컬럼별 mean / std / lower_95 / upper_95.

    Returns: {
        "mean":     pd.DataFrame (137, 48),
        "std":      pd.DataFrame (137, 48),
        "lower_95": pd.DataFrame (137, 48),
        "upper_95": pd.DataFrame (137, 48),
        "ci_width_ratio": pd.DataFrame (137, 48),
    }
    """

def enforce_sum_consistency(
    pred_df: pd.DataFrame,
    constraints: list[tuple[list[str], str]] = SUM_CONSTRAINTS,
) -> pd.DataFrame:
    """5종 sum constraint 를 raking 으로 강제 (sales + count 각 5종 = 10회 적용).

    각 constraint:
      sub_sum = pred_df[sub_cols].sum(axis=1)
      scale   = pred_df[total_col] / sub_sum.replace(0, 1)
      pred_df[sub_cols] = pred_df[sub_cols].multiply(scale, axis=0)

    적용 후 |sub_sum − total| / total ≤ 0.01 (합격선 2-11/2-12) 보장.
    """

def detect_extrapolation_cells(
    df_missing: pd.DataFrame,
    pred_dict: dict,
    threshold_ratio: float = 1.8,
) -> np.ndarray:
    """외삽 셀 = (24Q 전체 결측) OR (monthly_sales std / median_std ≥ 1.8).

    monthly_sales 기준만 사용 (47개 세부 컬럼은 monthly 에 종속).
    """

def calculate_confidence(
    pred_dict: dict,
    extrap_mask: np.ndarray,
    audit_metrics: dict,
) -> np.ndarray:
    """confidence 는 monthly_sales 기준 1개만 산출 (대표값).

    base                   = max(0.60, 1.0 - mnar_wape / 100)
    ci_penalty             = 1.0 - min(0.3, monthly_ci_width - 0.5) if > 0.5 else 1.0
    extrapolation_penalty  = 0.4 / base (외삽) | 1.0 (일반)
    → clip(0.10, 1.0)
    """

# validation/audit_v4.py (신규)

def run_audit_v4(df, X, seeds) -> dict:
    """4종 CV (random/ts/mnar/lodo/q1) + 6 추가 지표 6 seed 평균."""

def diagnose_failure(audit: dict) -> list[str]:
    """엄격 합격선 미달 시 진단 메시지 자동 생성."""

# backend/src/simulation/world_loader.py (수정)

def _load_dong_industry_weight(engine) -> dict[tuple[str, str], float]:
    """v4: confidence 가중 추가.

    SQL: LEFT JOIN seoul_district_sales_imputed_v4 + COALESCE
    공식: weighted_avg(d, cat) = Σ(sales × confidence) / Σ(confidence)
          popularity(d, cat)   = 0.5 + (weighted_avg / max_weighted_avg)
    """
```

**하위 호환성 보장:** `seoul_district_sales_imputed_v4` 테이블이 비어있을 때 LEFT JOIN 의 `COALESCE(v.confidence, 1.0)` 가 1.0 fallback → **다른 세션이 v4 도입 전 시점에 호출해도 정상 동작**.

## 6. 데이터 흐름

### 6.1 핵심 산출물 — `imputed_mapo_v4.csv` (wide) + `imputed_mapo_v4_detail.csv` (long)

**Hybrid 형식** — wide 는 다른 세션 SELECT * 호환, long 은 신뢰구간 부담 분리.

#### 6.1.1 `imputed_mapo_v4.csv` (wide, 메타 + 48 imputed 컬럼)

| 카테고리 | 컬럼 | 비고 |
|:--------|:----|:-----|
| 메타 (8) | `quarter`, `dong_code`, `dong_name`, `industry_code`, `industry_name`, `store_count`, `kosis_index`, `source` | source = "original" / "imputed_v4" / "extrapolated_v4" |
| sales (24) | `monthly_sales`, `weekday_sales`, `weekend_sales`, `mon_sales`~`sun_sales` (7), `time_00_06_sales`~`time_21_24_sales` (6), `male_sales`, `female_sales`, `age_10_sales`~`age_60_above_sales` (6) | 결측 셀은 v4 imputed, 원본 셀은 그대로 |
| count (24) | sales 동일 패턴의 `_count` | 동일 |
| 메타 (3) | `extrapolation_flag` (bool), `confidence` (float, monthly 기준 1개), `created_at` (timestamp) | confidence 는 47 컬럼 공통 |

**컬럼 순서 보존:** v3 의 `monthly_sales`, `store_count` 위치 그대로 (다른 세션 코드 호환). 새 컬럼은 끝에 추가.

#### 6.1.2 `imputed_mapo_v4_detail.csv` (long, 47 컬럼 × 95% CI)

| 컬럼 | 타입 | 의미 |
|:---|:---|:---|
| `quarter` | int | YYYYQ |
| `dong_code` | str | 11440xxx |
| `industry_code` | str | CS100001~CS100010 |
| `column_name` | str | 'monthly_sales', 'weekday_sales', ..., 'age_60_above_count' (47개) |
| `imputed_value` | bigint | 6 seed 평균 |
| `lower_95` | bigint | mean − 1.96×std (음수 시 0) |
| `upper_95` | bigint | mean + 1.96×std |
| `std` | float | 6 seed 표준편차 |
| `ci_width_ratio` | float | (upper − lower) / mean |
| `confidence` | float | monthly 기준 1개 (147 셀 모두 같음) |

**Row 수**: 137 셀 × 47 컬럼 = **6,439 row**.

### 6.2 DB 인터페이스 — 신규 테이블 2개

CLAUDE.md 의 DB 네이밍 규칙 (`seoul_` 접두사) 준수.

#### 6.2.1 `seoul_district_sales_imputed_v4` (wide, 48 imputed 컬럼)

```sql
CREATE TABLE seoul_district_sales_imputed_v4 (
    quarter            bigint    NOT NULL,
    dong_code          text      NOT NULL,
    industry_code      text      NOT NULL,

    -- 24 sales 컬럼
    monthly_sales       bigint,
    weekday_sales       bigint,  weekend_sales       bigint,
    mon_sales bigint, tue_sales bigint, wed_sales bigint, thu_sales bigint,
    fri_sales bigint, sat_sales bigint, sun_sales bigint,
    time_00_06_sales bigint, time_06_11_sales bigint, time_11_14_sales bigint,
    time_14_17_sales bigint, time_17_21_sales bigint, time_21_24_sales bigint,
    male_sales bigint, female_sales bigint,
    age_10_sales bigint, age_20_sales bigint, age_30_sales bigint,
    age_40_sales bigint, age_50_sales bigint, age_60_above_sales bigint,

    -- 24 count 컬럼 (동일 패턴)
    monthly_count integer,
    weekday_count integer, weekend_count integer,
    -- ... (sales 와 동일 24개 _count)

    -- 메타
    extrapolation_flag boolean   NOT NULL DEFAULT false,
    confidence         double precision NOT NULL DEFAULT 1.0,  -- monthly 기준 1개
    source             text      NOT NULL,  -- 'original' | 'imputed_v4' | 'extrapolated_v4'
    created_at         timestamp NOT NULL DEFAULT NOW(),
    PRIMARY KEY (quarter, dong_code, industry_code)
);
COMMENT ON TABLE seoul_district_sales_imputed_v4 IS
  '담당: 찬영(A1) | 137 결측 셀 48 컬럼 Multi-Output ExtraTrees 6 seed 앙상블 복원 | 출처: KOSIS DT_1KC2023';
CREATE INDEX ix_v4_quarter_dong ON seoul_district_sales_imputed_v4(quarter, dong_code);
```

#### 6.2.2 `seoul_district_sales_imputed_v4_detail` (long, 47 컬럼 × 95% CI)

```sql
CREATE TABLE seoul_district_sales_imputed_v4_detail (
    quarter         bigint    NOT NULL,
    dong_code       text      NOT NULL,
    industry_code   text      NOT NULL,
    column_name     text      NOT NULL,  -- 'monthly_sales', ..., 'age_60_above_count'
    imputed_value   bigint    NOT NULL,
    lower_95        bigint    NOT NULL,
    upper_95        bigint    NOT NULL,
    std             double precision,
    ci_width_ratio  double precision,
    confidence      double precision NOT NULL DEFAULT 1.0,
    PRIMARY KEY (quarter, dong_code, industry_code, column_name)
);
COMMENT ON TABLE seoul_district_sales_imputed_v4_detail IS
  '담당: 찬영(A1) | imputed_v4 의 47 세부 컬럼별 6 seed 95% CI long format | 행 수: 137 × 47 = 6,439';
CREATE INDEX ix_v4_detail_lookup ON seoul_district_sales_imputed_v4_detail(quarter, dong_code, industry_code);
```

**기존 `district_sales_seoul` 은 건드리지 않음.**

### 6.3 world_loader SQL 변경

```sql
-- v4 적용 후 (우리만 수정)
SELECT s.dong_name, s.industry_name,
       AVG(COALESCE(v.imputed_sales, s.monthly_sales))::double precision avg_sales,
       AVG(COALESCE(v.confidence, 1.0))::double precision avg_conf
FROM district_sales_seoul s
LEFT JOIN seoul_district_sales_imputed_v4 v
  ON s.quarter = v.quarter
 AND s.dong_code = v.dong_code
 AND s.industry_code = v.industry_code
WHERE s.quarter >= (SELECT MAX(quarter) - 1 FROM district_sales_seoul)
GROUP BY 1, 2
```

→ v4 가 없으면 기존 동작, 있으면 confidence 가중.

### 6.4 다른 세션 인터페이스 — `sales_imp_mapo.csv`

다른 세션의 V1c 검증 사용:
```
sales_imp_mapo[per_store] = monthly_sales / store_count
ratios = sim_per_store / actual_per_store
pass_v1c = (0.7 <= mean(ratios) <= 1.5)  # 다른 세션 합격선
```

**우리 v4 적용 시:**
- 기존 컬럼 (`monthly_sales`, `store_count`) 이름·순서 100% 보존
- 새 컬럼 (`lower_95`, `upper_95`, `confidence`, `extrapolation_flag`) 끝에 추가
- → **다른 세션 V1c 코드 변경 0** (기존 컬럼만 사용)
- → V1c ground truth 가 더 정확해짐 (137 결측 셀 imputed 추가) → V1c 합격 가능성 ↑

### 6.5 시간 부담 측정

| Phase | 작업 | 예상 시간 |
|:--|:--|:--:|
| 0-1 | KOSIS 항목 분리 + Pearson r | 5분 |
| 0-2 | dong_avg LOO + MNAR 재측정 | 30분 |
| 0-3 | 3 path × 6 seed × 5-fold | 4~8시간 (야간 batch) |
| 1 | 6 seed × ExtraTrees Optuna 200 trials | 75분 (마포) / 5시간 (서울) |
| 1 | 외삽 감지 + confidence | 5분 |
| 2 | 4종 감사 + 추가 지표 | 90분 |
| 3 | DB 적재 + world_loader 수정 + 회귀 테스트 | 2시간 |
| 4 | ABM Sensitivity (시뮬 2회 × N=3 seed × days=1) | 1시간 |
| 5 | sales_imp_mapo.csv 교체 + V1c 1회 | 30분 |

**총: 14~22시간** (1주 sprint 내 충분)

## 7. 오류 처리

### 7.1 예외 클래스

```python
# validation/exceptions.py (신규)

class ImputationError(Exception): ...
class KOSISFetchError(ImputationError): ...
class KOSISItemAmbiguousError(ImputationError): ...
class LearningPathInvalidError(ImputationError): ...
class EnsembleInstabilityError(ImputationError): ...
class ExtrapolationCellOverflowError(ImputationError): ...
class AuditFailureWithDiagnoses(ImputationError): ...
class V4DBLoadError(ImputationError): ...
class WorldLoaderRegressionError(ImputationError): ...
class SensitivityZeroImpactError(ImputationError): ...
```

### 7.2 Phase 별 오류 처리 정책

| Phase | 오류 | 처리 |
|:--|:--|:--|
| 0-1 | `KOSISFetchError` | 3회 재시도 (5s sleep) → 모두 실패 시 기존 anchor CSV 그대로 + warning |
| 0-1 | `KOSISItemAmbiguousError` | 혼합 anchor 로 fallback + spec 에 정직 명시 |
| 0-2 | LOO 계산 시 빈 fold | 해당 fold skip + 부분 평균 보고 |
| 0-3 | `LearningPathInvalidError` | 마포 단독 path 강제 fallback + warning |
| 1 | `EnsembleInstabilityError` | **즉시 중단** — 하이퍼파라미터 재튜닝 (Phase 1 추가 1일) |
| 1 | `ExtrapolationCellOverflowError` (외삽 ≥ 50%) | **즉시 중단** — Phase 0-3 학습 path 재선정 |
| 1 | 6 seed 중 일부 학습 fail | 성공 seed 만으로 평균 + N 명시 (N<3 이면 fail) |
| 2 | `AuditFailureWithDiagnoses` (5종 이상 fail) | **중단 X** — 정직 보고 + confidence 일괄 0.10 하향 + Phase 3 진입 |
| 2 | 일부 지표 NaN | 해당 지표 status="incomplete" + 다른 지표로 합격 판정 |
| 3 | `V4DBLoadError` | 트랜잭션 rollback + 기존 v3 상태 보존 |
| 3 | `WorldLoaderRegressionError` | 즉시 git revert + 다른 세션 알림 |
| 4 | `SensitivityZeroImpactError` (|차이| < 1%) | **중단 X** — "imputed 도입 가치 의문" 명시 + Phase 5 진행 여부 사용자 결정 |
| 5 | sales_imp_mapo.csv 교체 후 V1c fail | rollback (`v3_backup` 복원) + 다른 세션 협의 |

### 7.3 롤백 전략

| 단계 | trigger | 절차 |
|:--|:--|:--|
| Phase 1 후 | 합격선 1-1, 1-3 fail | git revert + Phase 0-3 재실행 |
| Phase 2 후 | 5종 이상 fail | confidence 일괄 0.10 하향 + 진행 (롤백 X) |
| Phase 3 후 | 회귀 fail | git revert + DB drop table |
| Phase 5 후 | V1c fail | `cp sales_imp_mapo.csv.v3_backup sales_imp_mapo.csv` |

**롤백 안전 장치:** Phase 5 시작 직전 v3 백업 + DB 복제 테이블 생성.

### 7.4 인터럽트 복구 (장시간 학습 중단 시)

```python
# 각 seed 학습 완료 시 즉시 디스크 저장
def fit_seed_ensemble_with_checkpoint(X, y, seeds, best_params, checkpoint_dir):
    models = []
    for seed in seeds:
        ckpt = f"{checkpoint_dir}/model_seed_{seed}.pkl"
        if os.path.exists(ckpt):
            models.append(joblib.load(ckpt)); continue
        m = ExtraTreesRegressor(**best_params, random_state=seed).fit(X, y)
        joblib.dump(m, ckpt); models.append(m)
    return models
```

→ 정전, OOM, 노트북 절전 등 중단 시에도 재실행하면 이어서 학습.

## 8. 테스트

### 8.1 테스트 파일 위치

| 파일 | 위치 | 카테고리 |
|:--|:--|:--|
| `test_imputed_v4.py` | `tests/` | 단위 |
| `test_audit_v4.py` | `tests/` | 단위 |
| `test_other_session_compat.py` | `tests/` | 통합 (회귀 ⭐) |
| `test_dong_industry_weight_confidence.py` | `backend/tests/` | 단위 |

### 8.2 핵심 테스트 케이스

**`test_imputed_v4.py`:**
- `test_predict_with_ci_multi_returns_48_cols` — 6 seed × 48 컬럼 예측 → 모든 컬럼 존재
- `test_lower_95_never_negative_all_cols` — 47 컬럼 모두 lower_95 ≥ 0
- `test_extrapolation_detection_24q_full` — (아현동, 양식음식점) flag=True
- `test_extrapolation_detection_high_variance` — monthly_sales std ≥ median×1.8 셀 flag=True
- `test_confidence_extrapolation_max_04` — extrapolation 셀 confidence ≤ 0.40
- `test_confidence_normal_min_065` — 일반 imputed 셀 confidence ≥ 0.65
- `test_six_seed_stability_monthly` — monthly_sales std/mean ≤ 0.10
- `test_ci_width_ratio_monthly` — monthly_sales ci_width_ratio ≤ 0.50
- `test_sum_consistency_weekday_weekend` — `weekday + weekend == monthly_sales` (오차 ≤ 1%)
- `test_sum_consistency_dow_7days` — `mon + tue + ... + sun == monthly_sales`
- `test_sum_consistency_time_6buckets` — `time_00_06 + ... + time_21_24 == monthly_sales`
- `test_sum_consistency_gender` — `male + female == monthly_sales`
- `test_sum_consistency_age_6buckets` — `age_10 + ... + age_60_above == monthly_sales`
- `test_sum_consistency_count_versions` — count 5종 sum constraint 동일 검증
- `test_enforce_sum_consistency_idempotent` — 두 번 호출해도 결과 동일

**`test_audit_v4.py`:**
- `test_diagnose_failure_when_mnar_over_15` — MNAR 16% → diagnose 메시지 포함
- `test_audit_metrics_all_pass_with_perfect_predictions` — sim ≈ actual×1.001 → 모두 통과
- `test_oom_accuracy_calculation` — 100 셀 중 97개 0.5x~2.0x → OoM = 0.97
- `test_f1_4tier_macro` — sklearn f1_score(macro) 와 일치
- `test_audit_handles_partial_nan` — 일부 NaN → 해당 셀 제외하고 계산

**`test_dong_industry_weight_confidence.py` ⭐:**
- `test_world_loader_backward_compat_empty_v4` — v4 비어있을 때 v3 결과와 동일
- `test_world_loader_uses_imputed_when_available` — v4 row 존재 시 결측 동·업종도 popularity 정의
- `test_world_loader_confidence_weighting` — confidence=0.4 셀 영향 = 1.0 셀의 40%
- `test_world_loader_all_zero_confidence_fallback` — 모든 confidence=0 → DEFAULT 1.0 fallback
- `test_world_loader_popularity_range_05_15` — 결과 popularity ∈ [0.5, 1.5]

**`test_other_session_compat.py`:**
- `test_brand_menu_loader_unaffected_by_v4` — 다른 세션 brand_menu_loader 영향 X
- `test_vacancy_pse_unaffected_by_v4` — vacancy_pse 시뮬 결과 구조 동일
- `test_brand_vacancy_validator_v1c_track_uses_v4` — V1c 가 새 sales_imp_mapo 자동 사용
- `test_living_pop_daily_boost_unaffected` — 다른 세션 함수 영향 X

### 8.3 fixture 전략

- `mock_engine_with_v4_table` — 137 셀 mock 데이터 + alive 100 셀
- `v3_baseline_weights` — v3 시점 popularity 결과 (회귀 비교용)
- `mock_imputed_csv_v4` — predict_with_ci 결과 mock

### 8.4 CI 정책

```bash
# 빠른 단위 (~10초, CI 기본)
pytest tests/test_imputed_v4.py
pytest tests/test_audit_v4.py
pytest backend/tests/test_dong_industry_weight_confidence.py

# 통합 (~5분, slow mark)
pytest tests/test_other_session_compat.py -m integration

# 본 학습 (~5시간, 별도 script — CI X)
python -m validation.reverse_engineer_sales_v4
```

### 8.5 커버리지 목표

| 파일 | 목표 |
|:--|:--:|
| `validation/reverse_engineer_sales_v4.py` | ≥ 90% |
| `validation/audit_v4.py` | ≥ 90% |
| `world_loader._load_dong_industry_weight()` | 100% (수정 부분) |

## 9. 엄격 합격선 + Fail 처리

### 9.1 Phase 0 — 사전 실험 합격선

| 실험 | 측정값 | 합격선 | Fail 시 |
|:--|:--|:--:|:--|
| 0-1 KOSIS 항목 분리 | 분리 r − 혼합 r | **≥ +0.03** | 분리 채택 X, 혼합 유지 |
| 0-2 MNAR LOO 수정 | WAPE 변화 | **차이 ≤ 3%p**이면 v3 결과 신뢰 | > 3%p 면 "v3는 leak로 과소평가" 정직 보고 |
| 0-3 학습 path 비교 | 최저 WAPE − 마포 단독 WAPE | **≥ −1.5%p** 시 그 path 채택 | 마포 단독 채택 |

### 9.2 Phase 1 — 본 학습 합격선

| 항목 | 측정값 | 합격선 | Fail 시 |
|:--|:--|:--:|:--|
| 1-1 6 seed 안정성 | seed 간 std/mean | **≤ 0.10** | 즉시 중단 — 재튜닝 |
| 1-2 95% CI 폭 | (upper−lower)/mean | **≤ 0.50** | 정직하나 사용 가치 한계 명시 |
| 1-3 외삽 셀 분산 | std/median_std | **≥ 1.8** 시 confidence 강제 ≤ 0.4 | < 1.8 면 일반 처리 |
| 1-4 confidence 평균 | 137셀 평균 | **≥ 0.75** | < 0.75 시 Phase 0-3 재실험 |

### 9.3 Phase 2 — 감사 합격선 ⭐

| 감사 | 합격선 | 근거 |
|:--|:--:|:--|
| 2-1 Random 10-fold WAPE | **≤ 12%** | 현재 튜닝본 ~10% |
| 2-2 Time-Series WAPE | **≤ 15%** | 누수 거의 없어야 |
| **2-3 MNAR WAPE (주 지표)** | **≤ 15%** | Lewis Reasonable 중간대 |
| 2-4 LODO WAPE | **≤ 30%** | v3 41.8% 대비 −11.8%p |
| 2-5 Q1 (작은 셀) WAPE | **≤ 18%** | 작은 셀도 신뢰 |
| 2-6 Pearson r | **≥ 0.97** | 다른 세션 V1a 0.85 + 0.12 |
| 2-7 RMSLE | **≤ 0.35** | 현재 0.334 ± 마진 |
| 2-8 OoM 정확도 | **≥ 97%** | 자릿수 보장 (현재 95.3%) |
| 2-9 F1 (4-tier) | **≥ 0.85** | 현재 0.819 |
| 2-10 MASE | **≤ 0.20** | 현재 0.224 |
| **2-11 합계 일관성 (sales)** | **max(\|sub_sum − monthly_sales\|/monthly_sales) ≤ 0.01** | raking post-processing 결과 검증 (1% 이내 미세 오차 허용) |
| **2-12 합계 일관성 (count)** | 동일, count 기준 | raking 적용 |
| **2-13 48 컬럼 평균 confidence** | 47 컬럼 confidence 평균 ≥ **0.70** | monthly 가 0.75 이상이면 세부 평균 0.70 보장 가능 |
| **2-14 세부 컬럼 OoM** | 47 컬럼 OoM 평균 ≥ **95%** | monthly 만 ≥ 97% 엄격, 세부는 노이즈 허용 |

### 9.4 Phase 3 — ABM 통합 합격선

| 항목 | 합격선 |
|:--|:--:|
| 3-1 popularity coverage | **= 64 (16동×4카테고리)** |
| 3-2 popularity 정상 범위 | 100% in [0.5, 1.5] |
| 3-3 가중 vs 비가중 popularity 상관 | **r ≥ 0.97** |
| 3-4 다른 세션 회귀 테스트 | **0건 fail** |

### 9.5 Phase 4 — Sensitivity 합격선

| 항목 | 합격선 |
|:--|:--:|
| 4-1 imputed 가치 정량화 | **|차이| ≥ 8%** |
| 4-2 5트랙 V1c 영향 | **0.85 ~ 1.18** + v3 대비 1.0 에 더 근접 |
| 4-3 외삽 셀 ABM 영향 | **변화 ≤ 7%** |

### 9.6 자동 진단 메시지 (Phase 2 예시)

```python
def diagnose_failure(audit: dict) -> list[str]:
    diagnoses = []
    if audit["mnar_wape"]["mean"] > 0.15:
        diagnoses.append(
            f"MNAR WAPE {audit['mnar_wape']['mean']*100:.1f}% > 15%: "
            f"결측 복원 신뢰성 부족. 가능 원인: "
            f"(1) 137 셀 작은 셀 비율 과다, (2) KOSIS anchor 부적합, "
            f"(3) hybrid 학습 효과 미미. → confidence 일괄 0.10 하향"
        )
    if audit["lodo_wape"]["mean"] > 0.30:
        diagnoses.append(
            f"LODO WAPE {audit['lodo_wape']['mean']*100:.1f}% > 30%: "
            f"dong fixed effect 의존 잔존. → dong_avg LOO 재적용"
        )
    if audit["pearson_r"]["value"] < 0.97:
        diagnoses.append(
            f"Pearson r {audit['pearson_r']['value']:.3f} < 0.97: "
            f"순위 보존 부족. → 외삽 셀 confidence 강화"
        )
    # ... 10 합격선 전부 진단
    return diagnoses
```

### 9.7 Done의 정확한 정의

**모두 충족해야 sprint done:**
- [ ] Phase 0~5 의 모든 합격선 통과 OR fail 시 정직 보고서 작성
- [ ] `imputed_mapo_v4.csv` 산출 (137 셀 + 12 컬럼)
- [ ] `audit_v4_report.md` 작성 (10 지표 + 합격/불합격 + diagnoses)
- [ ] `sensitivity_v4_report.md` 작성 (imputed 가치 정량화)
- [ ] `seoul_district_sales_imputed_v4` DB 테이블 적재
- [ ] `world_loader._load_dong_industry_weight()` 수정 + 단위 테스트 통과
- [ ] **다른 세션 회귀 테스트 0건 fail**
- [ ] `sales_imp_mapo.csv` v4 로 교체 + 5트랙 V1c 1회 실행
- [ ] 모든 코드 + 데이터 + 문서 git commit

**Done 이 아닌 것:**
- "production-ready 합격" 자체는 done 조건 아님 — Phase 2 의 MNAR 이 15% 를 넘어도 정직 보고서가 deliverable

## 10. 구현 순서 (writing-plans 단계에서 plan 으로 분해)

| Day | Phase | 작업 | 시간 |
|:--:|:--|:--|:--:|
| Day 1 오전 | 0-1 | KOSIS 항목 분리 | 0.5h |
| Day 1 오전 | 0-2 | dong_avg LOO 수정 | 1h |
| Day 1 오후 | 0-3 | 3 path 비교 (야간 batch) | 4~8h |
| Day 2 오전 | (검토) | Phase 0 결과 + 합격 path 결정 | 0.5h |
| Day 2 오전 | 1 | 본 학습 6 seed × MultiOutputRegressor(ExtraTrees) — 48 컬럼 | 3~6h |
| Day 2 오후 | 1 | 외삽 감지 + confidence 산출 + **합계 일관성 raking** | 1h |
| Day 3 종일 | 2 | 4종 CV + 6 추가 지표 + **48 컬럼 OoM/F1 측정** | 3h |
| Day 3 종일 | 2 | **합계 일관성 검증 (2-11/2-12)** + 합격선 판정 + diagnose | 1h |
| Day 4 오전 | 3 | DB 신규 테이블 **2개** 적재 (wide + detail, 6,439 row) + index | 1h |
| Day 4 오전 | 3 | world_loader 수정 + 단위 테스트 | 1.5h |
| Day 4 오후 | 3 | 다른 세션 회귀 테스트 | 1h |
| Day 5 오전 | 4 | ABM Sensitivity (시뮬 2회 × N=3) | 1h |
| Day 5 오후 | 5 | sales_imp_mapo 교체 (48 컬럼 wide) + V1c | 0.5h |
| Day 5 오후 | 5 | 모든 산출물 git commit | 0.5h |

**총: ~21시간** (1주 5영업일 × 8시간 = 40시간 중 절반, 야간 batch + 다른 작업 병행 가능. v3 대비 +4시간 = multi-output 학습 확장 + raking + DB 2 테이블)

## 11. Limitations & Future Work

### 11.1 본 spec 의 명시적 한계

1. **6 seed 가 통계적 정직 95% CI 의 근사** — 진짜 95% CI 는 부트스트랩 N≥1000 또는 베이지안 사후분포 필요. 6 seed 는 모델 불확실성만 잡고 데이터 불확실성은 부분적.
2. **외삽 셀 confidence 0.4 의 임의성** — 통계적 근거보다는 "사용자가 이건 못 믿겠다고 인지하는 임계값". 향후 conformal prediction 도입 시 정량화 가능.
3. **TCN 재학습 미포함** — 다른 세션 충돌 회피. v4 imputed 가 TCN 학습에 미치는 영향은 후속 spec.
4. **KOSIS DT_1KC2023 단일 anchor 한계** — 시도(서울)×분기 단위. 동·업종 해상도 차이 2단계. 추가 KOSIS 테이블 (DT_3KB9001, DT_1K41017) 결합은 후속 spec.
5. **마포 외 자치구 미확장** — 137 결측은 마포만. 서울 25개구 전체 imputed 는 후속 spec.
6. **Phase B 서울 imputed (MNAR 28.83%)와의 차별성 미확정** — Phase 0-3 실험 결과로 결정.
7. **Multi-Output ExtraTrees 합계 일관성 보장 X** — 학습 자체에 sum constraint 가 들어가지 않음. raking post-processing 으로 보정하지만 raking 은 비율 보존 → 원 모델 예측의 분포 정보 일부 손실. 합격선 2-11/2-12 (오차 ≤ 1%) 로 통제.
8. **count 컬럼의 정확도 한계** — count 는 sales 보다 노이즈 큼 (단가 변동, 결제 단위 차이). monthly_count 는 monthly_sales 와 strong 상관이지만 세부 count 는 원본도 분산 큼 → 합격선 2-13/2-14 가 sales 보다 완화 (confidence ≥ 0.70, OoM ≥ 95%).
9. **47 세부 컬럼 confidence 가 monthly 에 종속** — 세부 컬럼 별 정직 95% CI 는 산출하지만 confidence 점수는 monthly 1개. "sub 컬럼 X 의 신뢰도가 monthly 보다 높은가" 라는 질문엔 답하지 못함. 충분한 deliverable 이라 판단 (다운스트림은 monthly confidence 사용).
10. **MultiOutputRegressor 의 메모리 부담** — 6 seed × 48 컬럼 ExtraTrees → 학습 시 RAM 16GB+ 권장. 부족 시 컬럼 그룹별 batch 학습 fallback (Phase 1 0.5d 추가).

### 11.2 Future Work

**후속 sprint 후보:**
- TCN 재학습 + v4 imputed 사용 비교 (다른 세션 brand-menu 작업 완료 후)
- BEP / 폐업위험도 모듈에 confidence 가중 전파
- 137 결측의 마포 외 자치구 확장
- Conformal Prediction 도입으로 95% CI 정직성 강화
- KOSIS 추가 anchor 결합 (v5)

## 12. 변경 영향 / 호환성

### 12.1 기존 호출자 회귀 영향

| 호출자 | 영향 |
|:--|:--|
| `world_loader._load_dong_industry_weight()` 의 기존 호출자 (load_world_from_rds) | **영향 X** — LEFT JOIN 의 COALESCE 가 v4 빈 상태에서 기존 동작 보존 |
| `vacancy_pse`, `vacancy_inject`, `vacancy_evaluation_service` | **영향 X** — 우리는 수정 X |
| 다른 세션의 `_load_living_population_daily()` 신규 함수 | **영향 X** — 다른 함수 |
| 다른 세션의 5트랙 V1c 검증 | **양방향 긍정** — sales_imp_mapo.csv 가 더 정확해져 V1c 합격 가능성 ↑ |
| Frontend / 대시보드 | **영향 X** — DB 변경은 신규 테이블 추가만 |

### 12.2 DB 변경

- **신규 테이블**: `seoul_district_sales_imputed_v4` (CLAUDE.md 네이밍 규칙 준수, COMMENT 포함)
- **기존 테이블**: 변경 X (`district_sales_seoul`, `store_quarterly` 등 그대로)

## 13. 사전 검증 체크리스트 (구현 시작 전)

- [ ] **A. KOSIS 메타데이터 확인** — `13102193311A.T1` (경상지수) `T2` (불변지수) 정확성 확인
- [ ] **B. 서울 imputed 데이터 가용성** — `validation/results/imputed_seoul_sales_10ind.csv` 존재 + 컬럼 호환성
- [ ] **C. district_sales_seoul 스키마** — `confidence` 컬럼 부재 확인
- [ ] **D. world_loader 호출처 grep** — `_load_dong_industry_weight()` 호출처 확인 (1곳)
- [ ] **E. 다른 세션 sync** — 우리 영역 (`_load_dong_industry_weight`) 변경 없음 확인
- [ ] **F. 6 seed × ExtraTrees Optuna 학습 시간 측정** — 1 seed × 200 trials = ~75분 측정
- [ ] **G. 디스크 공간** — checkpoint 6 모델 (각 ~50MB) + DB 신규 테이블 (~100MB) 여유
- [ ] **H. PostgreSQL 권한** — CREATE TABLE + INDEX 권한
- [ ] **I. brand_vacancy_validator 가용성** — Phase 5 시점에 다른 세션 5트랙 검증 완성 여부

## 14. 합격 기준 (본 spec 의 done 정의)

본 spec 의 done 은 **모든 산출물 + 정직한 합격/불합격 보고**. production-ready 자체는 조건 아님.

**산출물 인벤토리:**
- 코드 8 파일 (신규) + 1 파일 (수정 — `world_loader.py`)
- DB 테이블 1 개 (신규)
- 데이터 4 CSV (Phase 0~1 결과) + 1 CSV (`imputed_mapo_v4.csv` ⭐) + 1 교체 (`sales_imp_mapo.csv`)
- 문서 4 (spec, plan, audit_v4_report, sensitivity_v4_report)

**합격 시나리오 (best case):**
1. Phase 0-1: 경상지수 anchor r=0.94 (혼합 0.92 +0.02 — 미달, 혼합 유지)
2. Phase 0-2: LOO 후 MNAR 25.7%→26.5% (+0.8%p, 합격)
3. Phase 0-3: Hybrid path 마포 단독 대비 −2.1%p (합격, 채택)
4. Phase 1: 6 seed std/mean 0.08, CI 폭 0.45, confidence 평균 0.81
5. Phase 2: MNAR 13.2% (합격), LODO 28.5% (합격), 8/10 지표 합격
6. Phase 3: world_loader 회귀 0건 fail
7. Phase 4: sensitivity 12% (합격선 8% 초과)
8. Phase 5: V1c mean_ratio 1.05 (합격선 0.85~1.18 이내)

→ 모두 합격 → production-ready 정직 보고

**Fail 시나리오 (worst case):**
1. Phase 0-2: LOO 후 MNAR 25.7%→31.2% (+5.5%p, 합격선 ≤3%p 미달) → "v3 결과는 leak 로 과대평가, 진짜는 31%" 보고
2. Phase 1: confidence 평균 0.65 (합격선 0.75 미달) → ExtraTrees 재튜닝 1일 추가
3. Phase 2: MNAR 22% (미달), LODO 38% (미달) → confidence 일괄 0.10 하향
4. Phase 4: sensitivity 5% (미달) → "imputed 도입 가치 한계 명시" 보고

→ fail 이지만 정직한 한계 보고 = done

## 15. 학술 / 벤치마크 근거

### 15.1 합격선 정당성

| 합격선 | 근거 |
|:--|:--|
| MNAR WAPE ≤ 15% | Lewis (1982) "Reasonable" 중간대 (10~20%) |
| LODO WAPE ≤ 30% | Hyndman & Athanasopoulos (2023) leave-group-out 권장 |
| Pearson r ≥ 0.97 | Brussels 학계 0.96 천장의 +0.01 (다른 세션 V1a 0.85의 +0.12) |
| RMSLE ≤ 0.35 | Shadbahr et al. (2023) 중소 표본 imputation 벤치마크 |
| MASE ≤ 0.20 | Hyndman M5 competition 표준, naive 5배 우위 |
| F1 4-tier ≥ 0.85 | sklearn macro F1 일반 합격선 |
| OoM ≥ 97% | Makridakis et al. (2022) M5 평가 권장 |
| 6 seed std/mean ≤ 0.10 | 학계 ensemble 안정성 통상 기준 |
| 95% CI 폭 ≤ 50% | 의사결정 가치 임계 (±25% 범위) |

### 15.2 인용 논문

- **Lewis (1982)** — MAPE 4단계 스케일 원조
- **Shadbahr et al. (2023)** — Deep learning vs conventional for imputation. 중소 표본 (<10K)에서 ExtraTrees/RandomForest 가 SOTA
- **Hyndman & Athanasopoulos (2023)** — Forecasting: Principles and Practice (3rd ed.). MASE / TS CV 표준
- **Makridakis et al. (2022)** — M5 accuracy competition. OoM / scale-free metrics
- **Jarrett et al. (2022)** — HyperImpute (van der Schaar, NeurIPS). matrix imputation SOTA 한계
- **Vovk et al. (2005)** — Conformal Prediction. 정직한 95% CI 근거 (future work)

## 16. 변경 로그

| 날짜 | 작성자 | 변경 |
|:--|:--|:--|
| 2026-04-27 | A1 (찬영) | 초기 design 작성 (brainstorm Q1~Q7 + 6 Section 결정 종합) |
| 2026-04-27 | A1 (찬영) | **Multi-Output 확장** — 복원 대상 monthly_sales 1개 → district_sales 48개 numeric 컬럼 전체 (sales 24 + count 24). MultiOutputRegressor(ExtraTrees) 채택, 합계 일관성 raking post-processing 추가, DB 테이블 2개로 분리 (wide + detail), 합격선 4개 추가 (2-11/2-12/2-13/2-14), 한계 4개 추가 (7~10), 일정 17h → 21h 조정. |
