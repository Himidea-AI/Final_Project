# 폐업 위험도 모델 B layer (feature 확장) — Design Spec

> **상태**: 브레인스토밍 완료, 사용자 승인 (2026-05-01).
> **작업 영역**: `models/closure_risk/` (B2 — 수지니 영역, A1 찬영 cross-team contribution).
> **선행 작업**: E ✅ (2026-04-30), C ✅ (2026-05-01 오전), D ✅ (2026-05-01 오후).
> **Plan 단계**: 본 spec 통과 후 `writing-plans` skill 으로 implementation plan 작성.

## Goal

LGBM 의 lag/static feature 16개 → **24개로 확장**. 기존 `build_timeseries` 가 이미 RDS 에서 load 하지만 LGBM 이 사용 X 인 신호 (`weekday_sales`, `weekend_sales`, age-segmented sales, `open_count`/`close_count`, `total_pop`, `cpi_index`, `holiday_count`) 의 yoy/ratio/lag derivation 8개를 추가하여 자기상관 lag 위주 feature set 의 한계 (AUC 0.60) 를 넘어선다.

새 ETL 없음 — 기존 `_engineer_lag_features` 함수에 derivation 만 추가.

## Background

D layer fix (오후, commit 181b84f) 후 production metrics:
- ensemble val AUC = 0.5950 / test AUC = 0.5974
- threshold fit: danger=0.4100, caution=0.3026
- predict_topk API ✅

학습 신호 자체는 본질적으로 변하지 않은 상태 (D 는 후처리 layer). 다음 본질적 한계는 **feature 의 단조로움**:

`models/closure_risk/data_prep.py:96-115` 의 `LGBM_FEATURES` 16개 중 11개가 **자기상관 lag** (closure_rate / store_count / sales 의 lag1/lag2/yoy/diff). label 정의가 `next_closure_rate > industry_p75_train` 인데 best predictor 가 `closure_rate_lag1` 인 것은 자명 — 외부 신호 (exo) 부재가 AUC 천장을 설정.

`models/lstm_forecast/data_prep.py:25-98` 의 `ALL_FEATURES` 34개 중 LGBM 미사용 25개:
- SALES 12개 (weekday/weekend, male/female, age 10/20/30/40/50/60+)
- STORE 2개 (open_count, close_count)
- POP 4개 (total_pop, avg_age, total_households, resident_pop)
- EXTRA 2개 (cpi_index, holiday_count)
- GOLMOK 5개 (store_franchise, store_normal, floating_pop, pop_per_store_gm, normal_ratio)

본 spec 은 이 중 **8개에서 derivation 한 신규 LGBM feature** 를 추가. 도메인 정당성 + 데이터 가용성 (`build_timeseries` 가 이미 load) 동시에 만족하는 후보로 선별.

## Architecture

```
build_closure_risk_dataset()
    ├── load_base_data()                # ALL_FEATURES 34개 load
    └── _engineer_lag_features()        # 16 LGBM feature 생성 (기존)
                                        # + 8 신규 feature (B-1)
        ↓
return df_unlabeled (24 LGBM feature)
        ↓
... 기존 split → label → train pipeline (변경 없음)
```

## Components

### 1. 신규 feature 8종

`_engineer_lag_features` 끝부분에 추가:

| # | 이름 | 정의 | 도메인 정당성 |
|---|---|---|---|
| 1 | `weekday_sales_yoy` | `(weekday_sales − weekday_sales_lag4) / (\|weekday_sales_lag4\| + 1)` | 평일 매출 yoy. 직장 상권의 핵심 신호 |
| 2 | `weekend_sales_yoy` | 동일 패턴 with `weekend_sales` | 주말 매출 yoy. 주거 상권의 핵심 신호 |
| 3 | `age_20_sales_ratio` | `age_20_sales / max(monthly_sales, 1)` | 20대 매출 비중. 트렌디 업종 신호 (홍대, 합정) |
| 4 | `age_60_sales_ratio` | `age_60_above_sales / max(monthly_sales, 1)` | 60대+ 매출 비중. 안정/정체 신호 |
| 5 | `open_close_ratio_lag1` | `open_count_lag1 / max(close_count_lag1, 1)` | 창업/폐업 흐름 (직전 분기). 1.0 미만 → 폐업 우세 |
| 6 | `total_pop_yoy` | `(total_pop − total_pop_lag4) / (\|total_pop_lag4\| + 1)` | 거주인구 yoy. 인구 감소 → 수요 감소 |
| 7 | `holiday_count` | 그대로 (분기 공휴일 수) | 계절성 보강. quarter_num 만으로 부족한 분기 차이 |
| 8 | `cpi_index_yoy` | `(cpi_index − cpi_index_lag4) / (\|cpi_index_lag4\| + 1)` | 물가 yoy. 거시 비용 압박 신호 |

### 2. `data_prep.py:LGBM_FEATURES` 리스트 갱신

기존 16 → 24:
```python
LGBM_FEATURES = [
    # 기존 16
    "closure_rate_lag1", "closure_rate_lag2", "closure_rate_diff",
    "store_count_lag1", "store_change",
    "franchise_ratio",
    "sales_yoy_change", "monthly_sales_lag1",
    "bus_flpop", "quarter_num",
    "rent_1f_lag1", "rent_change", "vacancy_rate",
    "trend_score",
    "adstrd_flpop",
    # B-1 신규 8
    "weekday_sales_yoy", "weekend_sales_yoy",
    "age_20_sales_ratio", "age_60_sales_ratio",
    "open_close_ratio_lag1",
    "total_pop_yoy", "holiday_count", "cpi_index_yoy",
]
```

### 3. `_engineer_lag_features()` 신규 derivation

기존 `_engineer_lag_features` 끝부분 (현재 line 230 근처) 에 추가:

```python
    # B-1 신규 feature 8종
    gk = ["dong_code", "industry_code"]

    # weekday/weekend yoy
    if "weekday_sales" in df.columns:
        wd_lag4 = df.groupby(gk)["weekday_sales"].shift(4)
        df["weekday_sales_yoy"] = (df["weekday_sales"] - wd_lag4) / (wd_lag4.abs() + 1)
    else:
        df["weekday_sales_yoy"] = 0.0

    if "weekend_sales" in df.columns:
        we_lag4 = df.groupby(gk)["weekend_sales"].shift(4)
        df["weekend_sales_yoy"] = (df["weekend_sales"] - we_lag4) / (we_lag4.abs() + 1)
    else:
        df["weekend_sales_yoy"] = 0.0

    # age ratio
    monthly = df["monthly_sales"].clip(lower=1)
    df["age_20_sales_ratio"] = df.get("age_20_sales", pd.Series(0, index=df.index)) / monthly
    df["age_60_sales_ratio"] = df.get("age_60_above_sales", pd.Series(0, index=df.index)) / monthly

    # open/close ratio (lag1)
    if "open_count" in df.columns and "close_count" in df.columns:
        open_lag1 = df.groupby(gk)["open_count"].shift(1)
        close_lag1 = df.groupby(gk)["close_count"].shift(1)
        df["open_close_ratio_lag1"] = open_lag1 / close_lag1.clip(lower=1)
    else:
        df["open_close_ratio_lag1"] = 1.0

    # total_pop yoy
    if "total_pop" in df.columns:
        pop_lag4 = df.groupby(gk)["total_pop"].shift(4)
        df["total_pop_yoy"] = (df["total_pop"] - pop_lag4) / (pop_lag4.abs() + 1)
    else:
        df["total_pop_yoy"] = 0.0

    # holiday_count — 그대로 (build_timeseries 에서 load)
    if "holiday_count" not in df.columns:
        df["holiday_count"] = 0

    # cpi yoy
    if "cpi_index" in df.columns:
        cpi_lag4 = df.groupby(gk)["cpi_index"].shift(4)
        df["cpi_index_yoy"] = (df["cpi_index"] - cpi_lag4) / (cpi_lag4.abs() + 1)
    else:
        df["cpi_index_yoy"] = 0.0
```

### 4. NaN 처리

shift(4) / shift(1) 가 처음 N분기 row 에서 NaN 생성. 기존 pipeline 의 `df[LGBM_FEATURES].fillna(0)` 가 LGBM 입력 단계에서 처리 — 추가 작업 불필요.

### 5. `predict.py` 한글 매핑 보강

`_FEATURE_KO` (line 95-111) 에 신규 8개 추가:
```python
_FEATURE_KO = {
    # ... 기존 ...
    "weekday_sales_yoy": "평일 매출 전년동기 변화율",
    "weekend_sales_yoy": "주말 매출 전년동기 변화율",
    "age_20_sales_ratio": "20대 매출 비중",
    "age_60_sales_ratio": "60대+ 매출 비중",
    "open_close_ratio_lag1": "직전 분기 창업/폐업 비율",
    "total_pop_yoy": "거주인구 전년동기 변화율",
    "holiday_count": "분기 공휴일 수",
    "cpi_index_yoy": "물가 전년동기 변화율",
}
```

`_RISK_SUMMARY_TEMPLATES` 도 동일 8개에 대해 positive/negative 자연어 추가.

### 6. 호환성

- `predict.py:367` 의 `x_lgbm = np.array([latest.get(f, 0.0) for f in LGBM_FEATURES])` — 자동으로 24 feature 사용 (LGBM_FEATURES list 가 단일 source of truth)
- `models/interface.py:485` — predict() signature 그대로
- 기존 weight pkl 은 16 feature 학습 → **재학습 필수** (T2 production retrain)
- TCN 은 영향 없음 (ALL_FEATURES 34 그대로)

## Data Flow

1. `build_timeseries` (기존) → 34개 ALL_FEATURES 컬럼 보유 df
2. `_engineer_lag_features` 호출:
   - 기존 16개 LGBM derivation
   - 신규 8개 B-1 derivation (yoy / ratio / lag)
3. `_make_labels` (기존) — label 생성, B-1 컬럼은 그대로 통과
4. split → train (LGBM 입력 24 feature)
5. evaluate / save (기존)

## Error Handling

| case | 처리 |
|---|---|
| 신규 feature 의 dependency column 미존재 (`weekday_sales` 누락 등) | 0.0 fallback (`if col in df.columns:` guard) |
| shift(4) NaN (첫 4분기) | 기존 `fillna(0)` (LGBM 입력 추출 시) |
| `monthly_sales` 가 0 | `clip(lower=1)` 로 division-by-zero 방지 |
| `close_count` 가 0 | `clip(lower=1)` 로 ratio 분모 보호 |
| LGBM 학습 시 신규 feature 가 모두 0 / 단일값 | LGBM 자동 처리 (split gain 0 → 무시). warning X |

## Testing

### 신규 단위 test — `tests/test_closure_risk_b_features.py` (~5 test)

1. `test_engineer_adds_8_new_features` — `_engineer_lag_features` 후 8 신규 컬럼 존재
2. `test_yoy_features_correct_with_lag4` — synthetic data 로 weekday/weekend/total_pop/cpi yoy 정확성
3. `test_age_ratio_features_bounded_0_to_1` — `age_20_sales_ratio`, `age_60_sales_ratio` 가 [0, 1] 또는 NaN
4. `test_open_close_ratio_handles_zero_close` — `close_count = 0` 시 division 안 깨짐 (clip 1)
5. `test_LGBM_FEATURES_count_is_24` — 리스트 길이 변화 검증

### 회귀 test

- 기존 35 closure_risk test 모두 통과 보장
  - `test_build_closure_risk_dataset_returns_df_only` 가 LGBM_FEATURES 누락 시 0 채움 → 기존 logic 그대로 통과 예상
  - `test_predict_does_not_use_label_pipeline` 영향 X
- predict.py SHAP test (있다면) 의 hidden assumption 점검 — `_FEATURE_KO` 의 키 순서 의존 X 확인

### Production retrain

- `python -m models.closure_risk.train` 실행
- AUC 비교 (vs D layer baseline 181b84f):
  - val AUC 0.5950 → ?
  - test AUC 0.5974 → ?
- threshold fit 자동 갱신 (D layer pipeline 그대로)
- pos_ratio 변화 X (label 정의 동일)

## Risks

| Risk | Mitigation |
|---|---|
| 신규 feature 가 무의미 → AUC 변화 0 | 정직한 진단 deliverable. 회고에 명시. 다음 sprint (B-2/B-3) 우선순위 도출 |
| 신규 feature 가 noise 추가 → AUC 하락 | LGBM 의 split gain 기반 자동 feature selection. learning_rate 0.05 + n_estimators 200 으로 보호 |
| `total_pop_yoy` 가 마포 16동 좁아 신호 약함 | 시도. 효과 미미하면 B-2 (spillover) 후 spec |
| `holiday_count` 데이터 누락 | guard + 0 fallback |
| 호출자가 hard-coded 16 feature 가정 | grep 으로 검증 — `LGBM_FEATURES` 만 source of truth |

## Out of Scope

- B-2 (인접 동 spillover) — 별도 spec
- B-3 (hierarchical industry-level stats) — 별도 spec
- A layer (LGBM/TCN proba inner-join) — 별도 spec
- D-3 (isotonic calibration) — 별도 spec
- 새 ETL / 데이터 source 추가 (카드매출 외부 등) — 별도 spec
- TCN feature 변경 — TCN 은 ALL_FEATURES 34 그대로 유지 (별도 sprint)

## 참고 학술 자료

- Domain knowledge encoding via aggregations (yoy, ratio) is standard in retail forecasting (Makridakis et al. M5 Competition 2020).
- Feature engineering vs structural changes: 본 sprint 는 feature engineering, A layer 는 structural — 별도 sprint 로 분리.
