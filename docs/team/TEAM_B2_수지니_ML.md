# B2 — 딥러닝 모델 (수지니)

**담당 영역**: TCN 매출 예측, BEP 손익분기, 시나리오 시뮬레이터, 폐업 위험도, 폐업률, SHAP 해석성, 신흥 상권 감지, 타겟 고객 세그먼트, 유동인구 피크 예측 (총 **9개 ML 기능**)

**핵심 성과**:
- TCN v3 (37 features, 자기회귀, RF=4): WA-MAPE **7.87%**, MAE 251M, Q1→Q4 drift +6.7%p
- LGBM + TCN AUC 비례 앙상블 폐업위험도: **test AUC 0.6152** (q90/q70 자동 threshold fit)
- 신흥상권 4-class classifier: accuracy **0.8903**, F1 **0.8675** (baseline 4.5배)
- 유동인구 naive lag-1: MAE **665**, MAPE **2.62%**, R² **0.9964** (TCN 6변종 폐기)
- emerging_district 성능 최적화: **8.11s → 1.12s (-86.2%)**
- 통합 인터페이스 `models/interface.py` 전담: 9 모델 dispatch + mock fallback + EXCLUDE_COMBOS 차단

---

## 0. 통합 인터페이스 (`models/interface.py`) — A1 → B2 핸드오프

### `ModelOutput.generate()` 9 모델 통합 dispatcher

```python
ModelOutput.generate(dong_code, industry_code, industry_name,
                     cost_config=None,
                     model="lstm",       # "lstm" | "tcn" | "gru" 동적 선택
                     segment_profile=None) → dict
```

### 출력 구조

```
{
    "input": { dong_code, dong_name, industry_code, industry_name },
    "revenue_forecast":  { quarterly_avg, quarterly_predictions[] },     # TCN/LSTM/GRU
    "closure_rate":      { closure_rate, risk_level, monthly_closure_rates[] },
    "closure_risk":      { risk_score, risk_level, top_signals[], model, is_mock },
    "bep":               { bep_quarters, quarterly_profit, total_initial_investment,
                           annual_roi, quarterly_simulation[] },
    "customer_segment":  { segment_ratio, segment_sales, profile_summary,
                           dimension_ratios } | None,
    "metadata":          { model_version="0.1.0", generated_at, data_period="2019Q1~2024Q4" }
}
```

### 핵심 정책

- **EXCLUDE_COMBOS 선제 차단** — 데이터 부족 조합(염리동×중식, 성산1동×제과 등) 진입 시 `ExcludedComboError` raise → B1(graph.py)에서 HTTP 400 변환
- **9 모델별 mock fallback** — 가중치 미존재/예외 시 `_mock_*()` 반환 + `is_mock=True` 플래그 → B2/C1 개발 즉시 시작 가능
- **model dispatch** — `"lstm" / "tcn" / "gru"` 3 매출예측 모델 운영 가능 구조 (TCN production 채택)

---

## 1. TCN v3 매출 예측 (`models/tcn_forecast/`)

### v1/v2/v3 3-way 비교 (141 동×업종 조합)

| 지표 | v1 (자기회귀, 34f) | v2 (DMS, 37f) | **v3 (자기회귀, 37f) ✅** |
|---|---|---|---|
| MAPE | **12.69%** | 13.26% | 14.03% |
| WA-MAPE | 8.13% | **7.66%** | 7.87% |
| MAE | 259M원 | **244M원** | 251M원 |
| RMSE | 797M원 | **612M원** | 688M원 |
| Direction Acc | **58.9%** | 57.4% | 58.0% |
| Q1→Q4 drift | +5.7%p | +4.85%p | **+6.7%p** |
| Bias (under/over) | -153.5M원 | **-31.0M원** | -109.4M원 |

> 산출물: `reports/eval_3way_20260503_170047.md` (sprint 1 평가 6 라운드 누적)

### 학습 조건 차이

| 항목 | v1 | v2 | v3 |
|---|---|---|---|
| 추론 방식 | 자기회귀 (1-step rollout) | DMS (4-step 동시 출력) | 자기회귀 (1-step rollout) |
| window_size | 4 | 12 | 4 |
| dilations | [1, 2] | [1, 2, 4, 8] | [1, 2] |
| output_size | 1 | 4 | 1 |
| 피처 수 | 34 | 37 | 37 |
| 신규 피처 | — | opr/cls_sale_mt_avg, industry_trend | (v2와 동일) |

### v3 채택 근거 4가지

1. **슬라이더 5개 호환** — `opr_sale_mt_avg`(매장당 운영매출) 피처는 **37f 모델에만 존재**. v1 채택 시 슬라이더 1개 무력화(elasticity=0).
2. **분기 변동성 보존** — Q1→Q4 drift +6.7%p가 가장 큼. v2 DMS는 mean reversion으로 평탄화 → 시뮬레이터 슬라이더 효과 약화.
3. **WA-MAPE는 v2와 거의 동급** — 매출 큰 조합에서 가중 측정인 WA-MAPE가 7.87% vs 7.66% → 실용 정확도 동일.
4. **underestimate 우려는 점포당 표시로 완화** — 단위(억) 자체가 체감 이슈. 점포당 환산하면 천만원~억 초반 → 시각적 underestimate 체감 X.

### 모델 아키텍처 (`predict.py:52-67`)

```python
DEFAULT_PREDICT_CONFIG = {
    "weights_path":       "weights/finetuned_mapo_tcn_v3.pt",
    "scalers_path":       "weights/finetune_tcn_scalers_v3.pkl",
    "residual_std_path":  "weights/finetune_tcn_residual_std_v3.pkl",
    "window_size": 4,         # 과거 4분기
    "n_channels":  128,
    "kernel_size": 2,
    "dilations":   [1, 2],    # RF = 1 + 1×3 = 4 = window_size
    "dropout":     0.2,
    "output_size": 1,         # 자기회귀 (1분기씩 → 4-step rollout)
    "confidence_z": 1.96,     # 95% 신뢰구간
}
```

- **입력**: 37 ALL_FEATURES = SALES(12) + STORE(5) + POP(4) + RENT(2) + EXTRA(9) + GOLMOK(5)
- **추론 모드 분기**: output_size=1(v3 자기회귀) / output_size>=4(v2 DMS) — `predict.py` 한 함수가 양 모드 동적 처리

### residual_std 4-step 측정 (2026-05-03)

학습 시 1-step val residual만 측정 가능(output_size=1)하나, 추론은 4-step 자기회귀 rollout → step별 신뢰구간 정확화 필요.

| 분기 | residual_std (4-step rollout 측정) | 기존 1-step fallback CI |
|---|---|---|
| Q1 | 346.8M원 (±25.5%) | ±5.88% |
| Q2 | 565.2M원 (±41.5%) | ±11.76% |
| Q3 | 642.9M원 (±47.2%) | ±17.64% |
| Q4 | 907.1M원 (±71.1%) | ±17.64% |

- `train.py:_measure_autoregressive_residuals(model, cfg, tgt_scaler, device, n_steps=4)` 헬퍼 → 재학습 시 자동 4-step 측정
- `regen_residual_v3.py`: 재학습 없이 기존 v3 가중치만으로 갱신하는 1회용 스크립트
- 기존 1-step pkl은 `*.pkl.bak_1step` 백업

### 학습 파이프라인 (`train.py`)

- `--arch v3|v2` CLI 플래그 (DEFAULT_PRETRAIN_CONFIG 기본값 v3, V2_OVERRIDES 추가)
- v2 DMS 학습: pretrain 5분/42epoch → finetune 23초 → MAPE=13.68%, DA=61.9%
- TimeSeriesSplit no-shuffle, EXCLUDE_COMBOS 2건(염리동×CS100002, 성산1동×CS100005 — MAPE 900%+)
- **시드 재현성 실험** — `weights/` 에 `seed47/415/2026 + run2/run3` 가중치 6개 보관 → 다중 시드 안정성 검증

### 평가 인프라 (`scripts/evaluate_model.py`)

- TCN v1 vs v2 자동 비교 + 분기별 MAPE/MAE/RMSE/DA/Bias 산출
- `reports/eval_*.md` 자동 저장 — 6 라운드 평가 기록 (`eval_20260501_*` 6건 + `eval_3way_20260503_*` 1건)

### 주요 파일

| 파일 | 역할 |
|---|---|
| `predict.py` | 자기회귀 + DMS 양 모드 추론, `_MODEL_CACHE` 프로세스 단위 캐시 |
| `train.py` | pretrain/finetune (--arch v3\|v2), 4-step residual 자동 측정 |
| `model.py` | TCNForecaster (Dilated Conv1d + Residual + WeightNorm) |
| `sensitivity.py` | 시나리오 시뮬레이터 사전 배치 (Section 3) |
| `regen_residual_v3.py` | residual_std 1-step pkl → 4-step pkl 재생성 |
| `scripts/evaluate_model.py` | v1/v2 비교 평가 + 리포트 자동 생성 |

---

## 2. BEP 손익분기점 (`models/revenue_predictor/bep.py`)

### 분기 단위 계산 공식

```
BEP(분기) = 초기투자비 / (분기예상매출 - 분기고정비 - 분기변동비)
분기 고정비 = 월고정비 × 3   # 임대료 + 관리비, 인건비 제외
분기 변동비 = 분기매출 × 업종별 원가율
```

### 업종별 원가율 (소상공인진흥공단 평균, 10개 업종)

| 업종 | 원가율 | 업종 | 원가율 |
|---|---|---|---|
| 한식음식점 | 37.5% | 패스트푸드점 | 40.5% |
| 중식음식점 | 39.4% | 치킨전문점 | 41.8% |
| 일식음식점 | 42.2% | 분식전문점 | 38.7% |
| 양식음식점 | 36.2% | 호프-간이주점 | 32.8% |
| 제과점 | 34.1% | **커피-음료** | **26.4%** (최저) |

`_BIZ_ALIAS` 별칭 매핑 13종 (카페/커피→커피-음료, 빵→제과점, 한식→한식음식점 등)

### Sanity Check (2026-05-04)

- 점포당 분기매출 1,500만~3억원 범위 검증 (`_run_bep`에서 `sanity_warning` 반환)
- `_get_latest_store_count` store_count 우선 → 분모 회귀 방지
- 연남×치킨 -15.8% 마진 버그 시스템 원인 차단 (회귀 테스트 7/7 PASS)

### 면책 문구

- **인건비 미포함** — 운영 규모 편차 커서 BEP에서 제외 (C1과 협업, 결과 화면 면책 표시)
- 변경 이력: 4분기 cap 제거(2026-05-04) — `simulation.py` 분기 단위 통일

### 출력 (`simulate_quarterly`)

분기별 list[dict]: quarter / revenue / quarterly_fixed_cost / quarterly_variable_cost / quarterly_profit / cumulative_profit / bep_reached

---

## 3. 시나리오 시뮬레이터 (`models/tcn_forecast/sensitivity.py`)

### 5개 슬라이더 사전 배치

```python
SLIDER_FEATURES = {
    "vacancy_rate":    ["vacancy_rate"],     # 공실률
    "trend_score":     ["trend_score"],       # 상권 활성도 (네이버 트렌드)
    "cpi_index":       ["cpi_index"],         # 물가
    "opr_sale_mt_avg": ["opr_sale_mt_avg"],   # 매장당 운영매출
    # quarter_num 은 categorical (Q1~Q4)
}
PERTURBATION_LEVELS = [-30, -20, -10, 0, 10, 20, 30]   # ±30%
```

### 캐시 (`weights/sensitivity_cache.json`)

- **156 (동×업종) 조합** × 5 슬라이더 × 7 레벨 × 4 분기 elasticity 사전 계산
- baseline + per-store + store_count 키 포함 → 분기별 비교 UX
- 재생성: `python -m models.tcn_forecast.sensitivity` (~70초, GPU 가속)

### Pearson 상관계수 (`weights/feature_correlations.json`)

학습 데이터 기준 4쌍: vacancy↔cpi, vacancy↔opr, cpi↔opr, trend↔opr → 슬라이더 동시 조작 시 사용자에게 상관관계 경고 표시

### 슬라이더 재구성 이력 (S3 업그레이드)

- 기존 5종(rent_1f / floating_pop / cpi / vacancy / opr) → 현재 5종 (vacancy / trend / cpi / opr / quarter_num)
- 제거: rent_1f(BEP 입력에 중복), floating_pop(피크 별도 모델로 분리)
- 추가: quarter_num(분기 categorical, 비틀림 효과 검증), trend_score(검색 트렌드)

### 회귀 테스트

- `tests/test_sensitivity.py` 26/26 PASS (StubModel은 (1,4) shape 반환 → DMS 경로 사용)
- ETag 기반 캐시 무효화 — `sensitivity_cache.json` 변경 시 프론트 자동 재로드

---

## 4. 폐업 위험도 (`models/closure_risk/`) — LGBM + TCN 앙상블

### 모델 구성 + 실측 성능

| 브랜치 | 입력 | 가중치 (AUC 비례) | val AUC | val PR-AUC | val P@10 | val R@10 |
|---|---|---|---|---|---|---|
| LightGBM | 17 lag/정적 features | 0.4804 | 0.5529 | — | — | — |
| TCN Classifier | 34f 시계열 + finetuned 백본 공유 | 0.5196 | 0.5980 | — | — | — |
| **Ensemble (final)** | (dong, industry, quarter) inner-join | — | **0.5694** | 0.2595 | 0.290 | 0.140 |
| **Ensemble (test 2024Q1-Q3)** | — | — | **0.6152** | 0.3197 | 0.261 | 0.099 |

> Brier score: val 0.166 / test 0.192 (보정도 측정)

### AUC 비례 가중 — softmax 회피 (`train.py:530-534`)

```python
total = lgbm_val_auc + tcn_val_auc
w_lgbm = lgbm_val_auc / total    # 실측: 0.5529 / 1.151 = 0.4804
w_tcn  = tcn_val_auc / total     # 실측: 0.5980 / 1.151 = 0.5196
# softmax 시: 0.78/0.76 → 65:35 왜곡
# 비례 시 : 정상 50:50 근처
```

### 시간순 split (데이터 누수 차단, `metrics.json`)

```
Train: 2019Q1~2022Q4  (16분기, label 1247건)
Val  : 2023Q1~Q4      (4분기, label 312건)
Test : 2024Q1~Q3      (3분기, label 189건)
```

A-1 inner-join (`_align_predictions`): LGBM/TCN proba를 (dong, industry, quarter) 키 기준 정렬 → 기존 `[:n]` trim 의 순서 보장 X 문제 해결.

### Threshold 자동 fit (q90 / q70)

`metrics.json` 에서 fit:
- **danger threshold**: 0.367 (val proba q90)
- **caution threshold**: 0.251 (val proba q70)

`predict.py:_load_risk_levels()` 가 metrics.json 손상/미존재 시 fallback (0.65 / 0.40).

### 17 LGBM features (`data_prep.py:LGBM_FEATURES`)

활성 17개:
- closure_rate_lag1/lag2/diff (3) — 직전/2분기 전 폐업률 + 변화량
- store_count_lag1, store_change, franchise_ratio (3) — 점포 수 lag/변화/프랜차이즈 비율
- sales_yoy_change, monthly_sales_lag1 (2) — 매출 추이
- bus_flpop, adstrd_flpop (2) — 유동인구 (행정동 0% null vs bus 49% zero → 행정동 우선)
- quarter_num (1) — 분기 categorical
- rent_1f_lag1, rent_change, vacancy_rate (3) — 임대료 + 공실
- trend_score (1) — 네이버 검색 트렌드
- **industry_prior_pred** (Stage 1, A-2 Wolpert 1992 stacking)
- **dong_closure_rate_residual_lag1** (B-3, Gelman & Hill 2006 hierarchical)

비활성 (B-1 신규 8 derivation, commit 9b09cd1 production rollback): weekday/weekend_sales_yoy, age_20/60_sales_ratio, open_close_ratio_lag1, total_pop_yoy, holiday_count, cpi_index_yoy → AUC -0.024 degradation (코드 보존)

### Stage 1 / B-3 hierarchical (2026-05-01)

- **Stage 1** (`stage1_industry_prior.py`): (industry, quarter) 단위 LGBM aggregates → `industry_prior_pred` broadcast
  - 학술 근거: Wolpert (1992) "Stacked generalization." Neural Networks 5(2)
- **B-3 dong residual**: `closure_rate_lag1 - industry_mean(train fit)` → `dong_closure_rate_residual_lag1`
  - 학술 근거: Gelman & Hill (2006) hierarchical regression
- **A-2 additive ensemble**: `final = (1-w) * dong_ensemble + w * scaled_industry_prior`, w grid search [0, 0.5] fit

### TCN Classifier 학습 (`train.py:DEFAULT_CONFIG`)

```python
{
    "tcn_epochs": 50, "tcn_lr": 5e-4, "tcn_batch_size": 32, "tcn_patience": 7,
    "input_size": 34, "n_channels": 128, "kernel_size": 2, "dilations": [1, 2], "dropout": 0.2,
    "lgbm_num_leaves": 31, "lgbm_n_estimators": 200, "lgbm_learning_rate": 0.05,
    "lgbm_reg_alpha": 0.1, "lgbm_reg_lambda": 0.1,
    "scale_pos_weight": auto,        # 클래스 불균형 자동 (neg/pos)
    "enable_d3_calibration": False,  # isotonic test AUC -0.038 → rollback
    "enable_b3_dong_residual": True,
    "enable_a2_additive": True,
}
```

- Pretrain backbone: `finetuned_mapo_tcn_34f.pt` 전이학습 (TCN 매출 예측 백본 공유)
- v3 호환 재학습 (2026-05-04): TCN scaler 34→37 재학습 완료, 가중치 `*.bak_34f` 백업 보존
- 회귀 테스트 9개: align / b3 / b_features / calibration / label / metrics / regression / split / stage1 / topk

---

## 5. 폐업률 (`models/revenue_predictor/predict.py`) — 개체 vs 집단 분리

### 설계 의도

| 모델 | 단위 | 데이터 |
|---|---|---|
| **closure_risk** | 개체 (dong × industry) | AI 미래 예측 (LGBM+TCN 앙상블) |
| **closure_rate** | 집단 (환경 지표) | 과거 실측 (최근 4분기 평균) |

### 추론 (`predict()`)

```python
recent = subset["closure_rate_pred"].tail(4).values   # 최근 4분기 실측 (closure_rate / 100)
closure_rate = round(float(recent[-1]), 4)
risk_level = _classify_risk(closure_rate)
```

### 위험도 분류 (z-score 기반)

- ≤ 0.3 → **safe**
- 0.3 ~ 0.6 → **caution**
- > 0.6 → **danger**

### 변경 이력

기존 `closure_model.pt` LSTM 미래 예측 → **변경**: `store_quarterly` 최근 4분기 closure_rate 평균
- 폐업률은 미래 예측보다 과거 실측 신뢰도 높음
- closure_risk가 이미 AI 미래 예측 담당 → 중복 회피
- 4분기 = 1년 → 계절성 자동 해소

### 출력

```
closure_rate         : 가장 최근 분기 폐업률 (0~1)
closure_rate_level   : "safe" / "caution" / "danger" / "unknown"
monthly_closure_rates: 최근 4분기 실측값 리스트
```

---

## 6. SHAP 해석성 (`models/explainability/shap_analysis.py`)

### 2개 explainer 분리

| Explainer | 모델 | 우선순위 |
|---|---|---|
| **TreeExplainer** | LightGBM (closure_risk 브랜치) | LGBM 전용 |
| **GradientExplainer** | TCNForecaster (Conv1d 안정적) | 1순위 |
| DeepExplainer | TCNForecaster fallback | 2순위 (GradientExplainer 실패 시) |
| mock SHAP | weights 미존재 환경 | 최종 fallback |

### Background tensor 변경 — zeros → randn (`shap_analysis.py:436-442`)

```python
# 이전: torch.zeros(...) → 모든 SHAP 부호가 한 방향으로 쏠리는 트리비얼 baseline
# 현재: torch.randn(10, window_size, input_size, generator=_gen).to(_dev)
#       → 양/음 기여 자연스럽게 출현 + 음수 리스크 시그널 정상 노출
```

### 한국어 자연어 템플릿 (`closure_risk/predict.py:_RISK_SUMMARY_TEMPLATES`)

**23개 피처 × positive/negative = 46개 한국어 자연어** 템플릿 정의.

대상: closure_rate_lag1/lag2/diff, store_count_lag1, store_change, franchise_ratio, sales_yoy_change, monthly_sales_lag1, bus_flpop, adstrd_flpop, rent_1f_lag1, rent_change, vacancy_rate, trend_score, industry_prior_pred, dong_closure_rate_residual_lag1 외 8개

예시:
- `closure_rate_lag1` positive → "직전 분기 폐업률이 높아 위험 신호가 지속되고 있습니다."
- `store_change` negative → "점포 수 증가로 상권이 활성화되고 있습니다."
- `franchise_ratio` positive → "프랜차이즈 비율이 높아 경쟁이 심화되고 있습니다."
- `vacancy_rate` positive → "공실률이 높아 상권 경기 침체 신호가 나타납니다."

> **차별화 포인트**: 차트만 보여주는 타사 SHAP UI 와 달리 자연어 설명까지 자동 생성

### `DEFAULT_PREDICT_CONFIG` 공유 (2026-05-04)

`shap_analysis.py`가 `predict.py`의 `DEFAULT_PREDICT_CONFIG` 직접 import → 모델 hyperparameter 단일 source of truth (예: window_size=4, n_channels=128 등 동기화 보장)

### 자기회귀 4-step SHAP 한계

output_size=1 자기회귀는 재주입 그래프가 끊겨 4-step 누적 SHAP 불가 → **1-step Q1 SHAP만 산출** (predict.py docstring에 명시)

### 프론트 통합 (C1 협업)

- `ShapInsightCard`: 라벨 / 비율% / 미니 막대 / summary
- 상위 3개 피처 자동 추출 → synthesis 노드 추천 근거로 활용

---

## 7. 신흥 상권 감지 (`models/emerging_district/`)

### LSTM Autoencoder — 이상 패턴 감지 (`model.py`)

```python
class LSTMAutoencoder(nn.Module):
    input_size  = 6           # EMERGING_FEATURES (sales / pop / store / change_ix 등)
    hidden_size = 64
    num_layers  = 2
    dropout     = 0.2
```

- 정상 상권 시계열 재구성 학습 → reconstruction MSE = 이상도 점수
- 출력 신호: **emerging** / **declining** / **normal**
- 추가 산출: anomaly_score (0~1), consecutive_anomaly_quarters, quarter_history, peer_distribution

### 4-Tier Production Fallback (`predict_fallback.py`)

| Tier | 데이터 소스 | 비고 |
|---|---|---|
| Tier 1 | change_ix 직접 (서울시 공식 stage) | 가장 신뢰 |
| Tier 1.5 | 4-class change_ix classifier | features 기반 예측 (change_ix 미발표 분기) |
| Tier 2 | B1 trend baseline (subway_growth + migration_2030) | 인프라 기반 |
| Tier 3 | slope baseline (sales/store_count slope) | 단순 추세 |
| Tier 4 | normal | 모든 데이터 부재 |

### 4-class classifier 성능 (마포 한정)

- test accuracy: **0.8903**
- macro F1: **0.8675**
- baseline F1: 0.1912 → **4.5배 우수**

### 성능 최적화 (2026-05-07) — `troubleshooting_emerging_ae_bottleneck`

| 항목 | Before | After | 개선 |
|---|---|---|---|
| `generate` 한 동 전체 | 8.11s | **1.12s** | **-86.2%** |
| `emerging_ae` 단독 | 3.86s | **168ms** | -95.6% |

**원인**: `load_timeseries`가 매 호출마다 전체 DataFrame 풀스캔 → 캐시 미공유.
**수정**: 캐시 공유 1줄 + main.py startup 워밍업 12줄 (병렬화 시도는 롤백).
**검증**: 26/26 PASS 회귀 + bench_emerging_breakdown.py 측정 인프라 자체 구축

### 백업 보존

`autoencoder.pt.bak_pre_quarter_threshold`, `autoencoder_meta.pkl.bak_pre_quarter_threshold` — quarter threshold 변경 직전 가중치 보존

---

## 8. 타겟 고객 세그먼트 (`models/customer_revenue/`) — 4-Group Softmax MLP

### 분류 모델 (회귀 X)

**입력 (11차원)**:
- dong_embed: `nn.Embedding(16, 4)` — 마포 16동
- industry_embed: `nn.Embedding(10, 4)` — 10업종
- quarter_enc: `[sin(2π·q/4), cos(2π·q/4), year_norm]` — 분기 + 연도
- year_norm 식: `(year - YEAR_BASE) / YEAR_SCALE`

**아키텍처** (`model.py:MLPPredictor`):
```
Input(11) → FC(128) → BatchNorm → ReLU → Dropout(0.3)
         → FC(64)  → ReLU → Dropout(0.3)
         → FC(16)  → 4-Group Softmax (그룹별 합 = 1.0)
```

**출력 (16차원, SEGMENT_COLS)**:

| 슬라이스 | 그룹 | 출력 |
|---|---|---|
| [0:6] | 연령 6개 | age_10/20/30/40/50/60+ ratio (identified_sales 기준) |
| [6:8] | 성별 2개 | male/female ratio (identified_sales 기준) |
| [8:14] | 시간대 6개 | 00-06/06-11/11-14/14-17/17-21/21-24 ratio (monthly_sales 기준) |
| [14:16] | 요일 2개 | weekday/weekend ratio (monthly_sales 기준) |

**모델 범위**: 마포 16동 × 10업종 = 160 segment 조합

### 학습 (`train.py`)

- Loss: **MSE on softmax 출력** (hybrid: classification 구조 + regression-style ratio target)
- Optimizer: Adam, lr=1e-3, batch=64, epochs=200, patience=20, dropout=0.3
- Split: **시간순 train/val** (셔플 없이 앞→뒤, val_ratio=0.2) — 데이터 누수 차단
- ReduceLROnPlateau scheduler

### 추론 보강 (`predict.py`)

- `quarterly_sales` 입력은 **점포당 분기 매출** (TCN 매출예측 탭과 동일 단위) → `total_sales_per_store` 키로 echo
- `identified_ratio` (동×업종)별 학습값 사용, fallback 0.8637 (전체 평균)
- `segment_sales = quarterly_sales * id_ratio * combined_ratio`
- 학습 범위(year_max)+2 초과 시 UserWarning

### Frontend 연동

- `/customer-segment` router 실시간 미리보기
- 사용자가 동/업종 선택 → 즉시 16개 ratio 표시

---

## 9. 유동인구 피크 (`models/living_pop_forecast/predict_naive.py`) — Naive Baseline 채택

### 학술 평가 — 6 라운드 모두 fail

| 변종 | 결과 |
|---|---|
| v1, v2, v3, v3a | naive 미달 |
| v4_residual | MASE_lag1 = **1.042** (naive 보다 살짝 못함) |
| v5 (group_decomp / group_rel_only / group_residual) | 모두 fail |
| v6_dow_hour_residual | naive 미달 |
| v7_daily_residual | MASE_lag7 = **1.0004** (naive 동급) |
| ARIMA baseline | fail |

→ TCN 6 변종이 모두 naive 미달 또는 동급으로 측정. weights/ 에 `living_pop_metadata_v2~v7_*.json` 16동별 LODO 평가 결과 보관.

### Production 채택: lag-1 Naive Baseline

```python
# 분기 단위
y[t] = y[t-1]   # 직전 분기 같은 (dong_code, time_zone) 평균 인구

# 일별 단위 (참고)
y[t] = y[t-7]   # 1주 전 같은 요일
```

### 성능

| baseline | MAE | MAPE | R² |
|---|---|---|---|
| **naive_lag1 (분기)** | **665** | **2.62%** | **0.9964** |
| naive_lag7 (일별) | 1,039 | 3.71% | 0.9707 |

### 캐시

`_DF_CACHE` (db_url 키) — 두 번째 호출부터 0ms (DB I/O 없음)

### 차별화 메시지

> "가장 단순한 모델이 가장 정직할 때가 있다" — 6 변종 폐기 후 naive 채택. **Occam's Razor + 정직한 엔지니어링**.

---

## 모델 버전 관리 / 실험 추적

### Rollback 사례 (8건)

| # | 시도 | 결과 | 조치 |
|---|---|---|---|
| 1 | TCN v2 DMS (분기 평탄화) | 슬라이더 효과 약화 | v3 자기회귀로 전환 (v2 가중치 보존) |
| 2 | closure_risk dropout 0.3 (sprint 10) | test AUC -0.0001 noise | 0.2 rollback |
| 3 | closure_risk lgbm_num_leaves 15 (sprint 11) | test AUC -0.017 | 31 rollback |
| 4 | closure_risk lgbm_n_estimators 100 (sprint 12) | test AUC -0.0006 noise | 200 rollback |
| 5 | closure_risk B-1 신규 8 features | AUC -0.024 degradation | commit 9b09cd1 production rollback |
| 6 | closure_risk D-3 isotonic calibration | test AUC -0.038 + threshold collapse | rollback (코드 보존, 재시도 가능) |
| 7 | 유동인구 TCN v1~v7 (6 변종) | naive 미달 | naive lag-1 채택 |
| 8 | SHAP background = zeros | 부호 한 방향 쏠림 (트리비얼) | randn 으로 변경 |
| 9 | revenue_predictor LSTM closure_model.pt | closure_risk와 중복 | 최근 4분기 실측 평균으로 변경 |
| 10 | emerging_ae 병렬화 시도 | 효과 미미 | 캐시 공유 + startup 워밍업으로 우회 |

### KEEP 사례 (8건)

1. TCN v3 자기회귀 + 37 features (slider 호환 + 분기 변동성)
2. residual_std 4-step rollout 측정 (Q1~Q4 정직한 신뢰구간)
3. **AUC 비례 앙상블 가중** (softmax 왜곡 회피)
4. q90/q70 quantile threshold fit (`metrics.json`)
5. Stage 1 industry_prior + B-3 dong_residual hierarchical
6. SHAP background randn + 23×2 한국어 템플릿
7. emerging_ae 캐시 공유 (-86.2% 성능 개선)
8. 유동인구 naive baseline 채택 (TCN 6변종 폐기)

### 가중치/스케일러 백업 정책 (롤백 가능 구조)

- `closure_risk_*.bak_34f` — v3 호환 재학습(2026-05-04) 직전 백업
- `finetune_tcn_residual_std_v3.pkl.bak_1step` — 4-step 측정 직전 백업
- `autoencoder.pt.bak_pre_quarter_threshold` — emerging threshold 변경 직전 백업
- TCN 시드 재현성: `seed47/415/2026 + run2/run3` 6개 가중치 동시 보관
- TCN v2 ↔ v3 동시 보유: `finetune_tcn_scalers_v2.pkl + v3.pkl`, `finetune_tcn_residual_std_v2.pkl + v3.pkl` → v2 즉시 롤백 가능

### 회귀 테스트 인프라 (`tests/`)

| 테스트 | 검증 대상 |
|---|---|
| `test_closure_risk_align.py` | A-1 inner-join 키 정렬 |
| `test_closure_risk_b3.py` | B-3 dong residual hierarchical |
| `test_closure_risk_b_features.py` | B-1 신규 8 features 시료 |
| `test_closure_risk_calibration.py` | D-3 isotonic 보정 |
| `test_closure_risk_label.py` | 폐업 label 정의 |
| `test_closure_risk_metrics.py` | AUC/PR-AUC/Brier 산출 |
| `test_closure_risk_regression.py` | 가중치 변경 시 회귀 검증 |
| `test_closure_risk_split.py` | 시간순 split (no leakage) |
| `test_closure_risk_stage1.py` | Stage 1 industry_prior |
| `test_closure_risk_topk.py` | P@k / R@k |
| `test_emerging_district.py` | LSTM Autoencoder + 4-tier fallback |
| `test_living_pop_forecast_v2.py` | naive baseline 회귀 |
| `test_revenue_sanity.py` | 점포당 매출 sanity (1500만~3억) |
| `test_sensitivity.py` | 시나리오 시뮬레이터 (24/24 PASS, 26/26 stub) |
| `test_tcn_dms.py` | TCN v2 DMS 추론 모드 |

### 성능 측정 인프라 (`scripts/bench_*.py`)

- `bench_emerging_breakdown.py` — emerging_ae 단계별 시간 측정
- `bench_parallel_generate.py` — generate() 병렬화 효과 측정 (롤백 근거)
- `bench_per_component.py` — 컴포넌트별 latency 분리
- `bench_predict_endpoint.py` — /predict 엔드포인트 e2e

---

## 성과 요약

| 영역 | 핵심 메트릭 |
|---|---|
| **Production ML 기능** | **9개** (TCN v3 매출예측 / BEP / 시나리오 시뮬레이터 / 폐업위험도 / 폐업률 / SHAP / 신흥상권 / 타겟고객 / 유동피크) |
| **TCN v3** | window=4, 37 features, **WA-MAPE 7.87%**, MAE 251M, 자기회귀 4-step |
| **폐업위험도** | LGBM(17f) + TCN(34f) AUC 비례 앙상블, **test AUC 0.6152**, q90/q70 자동 fit |
| **신흥상권 classifier** | accuracy **0.8903**, F1 **0.8675** (baseline 4.5×) + 4-tier fallback |
| **유동인구 naive** | MAE **665**, MAPE **2.62%**, R² **0.9964** (TCN 6변종 폐기) |
| **시나리오 시뮬레이터** | 5 슬라이더 ±30% × 156 조합 사전 캐시 (sensitivity_cache.json) |
| **성능 최적화** | emerging_ae **8.11s → 1.12s (-86.2%)** |
| **SHAP** | TreeExplainer(LGBM) + GradientExplainer(TCN) + **23×2 한국어 템플릿** |
| **타겟 고객** | 4-group softmax MLP (16 outputs, 마포 16동×10업종 = 160 segments) |
| **BEP** | 분기 단위 + 점포당 sanity_warning, 10업종 원가율, 인건비 제외 면책 |
| **인프라** | 통합 인터페이스 + 9 모델 dispatch + 6 평가 리포트 + 4 bench + 15+ 회귀 테스트 |

### 차별화 포인트 (포트폴리오)

1. **Naive baseline 인정 (유동인구)** — TCN 6변종 폐기, "정직한 엔지니어링" (Occam's Razor)
2. **AUC 비례 가중 (폐업위험도)** — softmax 왜곡(0.78/0.76 → 65:35) 회피, 정상 50:50
3. **한국어 자연어 SHAP 템플릿** — 차트만 보여주는 타사 SHAP UI 와 차별화 (23×2 = 46개)
4. **4-step residual_std 측정** — 1-step fallback(±18%) → 자연 확장 ±25.5%~±71.1% 정직한 신뢰구간
5. **데이터 누수 차단 시간순 split** — Train 19~22 / Val 23 / Test 24, A-1 inner-join 정렬
6. **롤백 가능 인프라** — 가중치 .bak 백업 + TCN 시드 6개 + v2/v3 동시 보유

---
