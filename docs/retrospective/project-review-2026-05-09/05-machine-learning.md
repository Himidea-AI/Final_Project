# 05. Machine Learning Review -- 마포 프랜차이즈 시뮬레이터

**작성일**: 2026-05-09  
**작성자**: 시니어 코드 리뷰어 (Claude Sonnet 4.6)  
**범위**: Non-deep-learning ML(머신러닝, 데이터를 보고 규칙을 학습하는 알고리즘) -- 경사 부스팅, 회귀, 결측 보간 (TCN/GRU/LSTM 딥러닝 제외)  
**데이터 기준**: models/closure_risk/weights/metrics.json, docs/ml-models/ 전체, validation/ 스크립트

> 비전문가 안내: 이 문서는 머신러닝(데이터를 보고 규칙을 학습하는 알고리즘)으로 만든 다섯 가지 모델을 진단합니다. 전문 용어는 처음 등장할 때 괄호 안에 풀어 설명합니다. 모델 자체보다 "어떤 결정이 어떤 근거로 내려졌는가"가 더 중요합니다.

---

## 🚨 한 줄 진단

**운영 RDS(AWS 가 관리해 주는 PostgreSQL 데이터베이스 서비스) 자격증명(호스트·계정·비밀번호)이 5 개 파일에 평문 fallback(환경 변수가 없을 때 자동으로 쓰이는 기본값) 으로 노출 + SHAP(개별 예측에 어떤 피처가 얼마나 영향을 줬는지 설명하는 기법) 실패 무음 + PyTorch 시드 미고정.**

## 비전문가용 요약

- **무엇이 문제인가요?**
  - 운영 데이터베이스 비밀번호가 코드 5 곳에 평문으로 박혀 있습니다. 깃 히스토리에도 남아 있어, 코드를 본 사람이라면 누구나 운영 DB 에 접근 가능합니다.
  - 모델이 "어떤 변수가 결과에 영향을 미쳤는지" 설명하는 SHAP 단계가 실패해도 빈 결과로 폴백(다른 경로로 우회) → 운영에서 설명이 사라져도 모릅니다.
  - 검증(val) AUC(Area Under ROC Curve. 분류 모델의 좋고 나쁨을 0~1 사이 한 숫자로 요약. 0.5=동전 던지기, 1.0=완벽) 0.5694 < 테스트(test) AUC 0.6152 — 일반적으로 그 반대여야 함. 데이터 누수(미래 정보가 학습에 새어 들어가는 현상. 평가가 과대 평가됨) 또는 split(학습·검증·테스트 데이터 분할) 오류 가능성.
- **얼마나 위험한가요?** RDS 자격증명 노출은 보안 P0(가장 시급한 단계). 비밀번호 회전 + fallback 제거가 최우선.
- **얼마나 걸리나요?** 비밀번호 회전 + fallback 제거 0.5 일. 시드 통일 0.5 일. AUC 역전 조사는 1 ~ 2 일.

## 가장 시급한 4 가지 (P0)

| # | 위치 | 문제 | 수정 |
|---|------|------|------|
| P0-1 | `models/closure_risk/data_prep.py:165` 외 4 파일 | RDS 비밀번호 평문 fallback | 비밀번호 회전 + fallback 제거 + `os.environ["POSTGRES_URL"]`(AWS 관리형 PostgreSQL 의 연결 문자열) 강제 |
| P0-2 | `models/closure_risk/train.py` | PyTorch seed(난수 시드, 같은 결과를 재현하기 위한 고정값) 미설정 → TCN(시계열 신경망 모델) 비결정성 | `torch.manual_seed`, `numpy.random.seed`, `random.seed` 통일 |
| P0-3 | `models/closure_risk/predict.py` `_top_signals_*` | `except Exception: return []` 무음 SHAP 실패 | `logger.warning` + Sentry(에러 추적 SaaS) |
| P0-4 | `backend/src/main.py` startup | warmup(서버 기동 시 모델을 미리 로드해 첫 요청 지연을 줄이는 작업) 무음 (`except Exception: print("warmup skip")`) | 구조화 로그 |

---

## 1. 모델 인벤토리 (Models Inventory)

이 프로젝트는 폐업 위험도, 고객 매출, 신흥 상권, BEP(Break-Even Point. 손익분기점) 분석, 유동인구 예측까지 다섯 가지 도메인의 ML 모델을 같은 저장소 안에서 운영하고 있다. 모델별 학습 산출물(가중치 파일 등)은 모두 `models/<도메인>/weights/` 디렉터리에 모여 있어 추론 코드가 단일 경로로 로딩한다.

### 1.1 학습 아티팩트(학습이 끝난 뒤 저장되는 결과물 파일들)가 어디에 있는가

폐업 위험 모델(Closure Risk)은 `models/closure_risk/weights/` 아래에 LightGBM(LGBM, Microsoft 가 만든 경사 부스팅 트리 모델. 작은 트리 여러 개를 순차로 학습) 분류기(`closure_risk_lgbm.pkl`), TCN 분류기(`closure_risk_tcn.pt`), 앙상블(여러 모델 결과를 합치는 기법) 가중치(`ensemble_weights.pkl`), 보정기(calibration, 예측 확률이 실제 비율과 일치하도록 보정)(`ensemble_calibrator.pkl`), Stage1 산업 prior(사전 정보, 집단 평균 같은 사전 지식)(`stage1_industry_prior.pkl`), B-3 동 잔차 lookup(`b3_dong_residual_lookup.pkl`), 평가 지표(`metrics.json`) 일곱 종류를 내려놓는다. 추론 시 한꺼번에 메모리에 적재된다.

고객 매출 모델(Customer Revenue)은 `models/customer_revenue/weights/customer_mlp.pt`(MLP=Multi-Layer Perceptron, 가장 단순한 신경망)와 segment 매핑 pkl 두 개를 사용했지만, 평가 결과(2026-04-29 기준) group_mean baseline(그룹별 평균값을 그대로 예측으로 쓰는 가장 단순한 기준 모델) 보다 못해 운영에서는 사실상 폐기 결정이 내려진 상태다(섹션 5 참조). 신흥 상권(Emerging District)은 오토인코더(입력을 압축했다가 복원하며 이상 패턴을 잡는 신경망)와 변화지수 분류기(서울/마포 두 개)로 구성된다. 매출 예측(Revenue Predictor / BEP)은 `pretrained.pt`, `scaler.pkl`, `survival_model.pt`로 구성된다. 유동인구 예측(Living Pop Forecast)은 v2 TCN 가중치와 16동 LODO(Leave-One-Dong-Out, 한 동을 빼고 나머지로 학습해 일반화를 검증) 가중치 16개가 디스크에 남아 있으나, 운영은 naive baseline(직전 값을 그대로 예측으로 쓰는 가장 단순한 방식)으로 대체되었다(섹션 6 참조).

### 1.2 CatBoost(Yandex 가 만든 경사 부스팅 모델. 카테고리 변수에 강함)는 왜 디렉터리에 남아 있는가

저장소에 `catboost_info/` 디렉터리가 있고 1,300 iteration(반복 학습 횟수) 학습 로그(`catboost_training.json`)가 보존되어 있지만, 현재 `models/` 어느 서브모듈도 CatBoost 모델을 직접 로딩하지 않는다. 매출 보간(missing value imputation, 결측치를 채워 넣는 작업) SOTA(State-Of-The-Art, 현 시점 최고 수준) 비교 실험(`validation/sota_comparison.py`)에서만 후보로 등장했고, MNAR(Missing Not At Random. 결측이 무작위가 아니라 특정 조건에서 집중) WAPE(Weighted Absolute Percentage Error. MAPE 의 가중 평균 버전) 26.10%로 ExtraTrees(여러 결정 트리(if/else 분기로 예측하는 가장 단순한 모델 단위) 결과를 평균내는 앙상블 모델)(15.96%)에 밀려 production 채택에서 제외됐다. 즉 **CatBoost는 실험 산출물일 뿐 운영 의존성이 아니다.** 디렉터리가 남아 있어 가끔 신규 멤버가 운영 모델로 오해하니, README 한 줄로 "실험용" 표시를 해두면 좋다.

---

## 2. 폐점 위험 모델 (Closure-Risk Model)

폐점 위험 모델은 이 프로젝트에서 가장 정성을 들인 영역이고, 12 sprint(짧은 단위 개선 주기)에 걸친 실험 로그가 남아 있다. 한 마디로 정리하면 "LightGBM과 TCN을 가중 앙상블한 2단계 stacking(스태킹, 여러 모델 출력을 또 다른 모델의 입력으로 쓰는 앙상블 기법) 구조이고, 산업·동 계층의 prior/잔차 피처(feature, 모델 입력에 쓰이는 변수 하나)로 데이터 부족을 보완한다."

### 2.1 어떤 구조인가

LightGBM(트리 기반)과 TCNClassifier(시계열 신경망)를 별도로 학습한 뒤 가중 평균하는 단순 앙상블이다. 가중치는 검증 AUC 에 비례하도록 동적 산출되며 현재 `w_lgbm=0.480`, `w_tcn=0.520`으로 저장되어 있다. 위에 한 층이 더 올라가는데, Stage1 에서 산업(업종) 수준 LGBMRegressor(LGBM 의 회귀 버전, 숫자 값을 예측)가 산업 평균 위험을 예측하고 그 결과(`industry_prior_pred`)가 Stage2 동(洞) 수준 LGBM의 입력 피처로 들어간다. Wolpert(1992)의 stacked generalization 을 그대로 적용한 형태이고, 데이터가 적은 동·업종 조합에서 산업 평균이 강한 사전 정보 역할을 한다.

### 2.2 어떤 피처를 쓰는가

`models/closure_risk/data_prep.py:169-202`에 17개 LightGBM 피처가 정의되어 있다. 폐업률 lag(과거 시점 값. lag1=직전 분기, lag2=2분기 전)(1·2분기 전 폐업률, 분기 차분), 점포 수 lag·변화량·프랜차이즈 비율, 매출 YoY(Year-over-Year, 전년 동분기 대비) 변화율과 직전 분기 매출, 버스/행정동 유동인구, 임대료 1층 lag·변화량, 공실률, trend score, 분기 순번이 기본 14개다. 여기에 2026-05-01 sprint A-2에서 더해진 `industry_prior_pred`(Stage1 산업 prior 예측)와 sprint B-3에서 더해진 `dong_closure_rate_residual_lag1`(동 폐업률 - 산업 평균, train-only(학습 데이터로만 통계량을 계산하는 방식, 누수 방지)로 fit)이 결정타다. 두 피처가 KEEP(유지로 채택)로 살아남았다는 사실이 12 sprint 중 가장 큰 성과다.

반면 sprint B-1에서 시도한 8개 신규 파생 피처(평일/주말 매출 YoY, 연령대 매출 비중 등)는 production rollback(운영에서 되돌림) 상태다. AUC 0.024 하락(commit 9b09cd1)으로 효과가 없었다.

### 2.3 시간 누수(leakage, 미래 정보가 학습에 새어 들어가 평가가 과대 평가되는 현상)를 어떻게 막았는가

`models/closure_risk/data_prep.py:29-83`의 `_time_based_split`은 quarter(분기) 기준 시간 순 train/val/test split(학습·검증·테스트 데이터 3분할)이다. Bergmeir & Benitez(2012)에서 권고하는 시계열 표준 split이다. 이전 legacy(예전, 이미 대체된 옛날 버전) 버전은 `dong_code, industry_code, quarter`로 정렬한 뒤 마지막 N%를 자르는 방식이라 사실상 random split(무작위 분할)이 되었고 temporal leakage(시간 누수) 위험이 있었다. 2026-04-29에 수정되었고, `docs/ml-models/evaluation/closure-risk-validation-fix.md`에 변경 근거가 남아 있다.

라벨(label, 모델이 맞춰야 하는 정답값) 생성도 train-only다. `_make_labels(train_quarters=...)`은 train 분기 데이터로만 industry p75 분위수(하위 75% 지점의 값)를 fit(통계량 계산/학습)하고 그 임계값으로 test/val 의 라벨을 매긴다. Stage1과 B-3 잔차 피처도 동일 원칙을 따른다. 누수 차단은 학술 표준에 부합한다.

### 2.4 성능은 어디까지 왔는가

`models/closure_risk/weights/metrics.json` 기준 production 가중치 성능은 다음과 같다.

| 모델 | Val AUC | Test AUC | Test PR-AUC(Precision-Recall 기반 AUC. 클래스 불균형 시 더 적합) | Test Brier(Brier score, 예측 확률이 실제 정답과 얼마나 가까운지 평가하는 지표. 낮을수록 좋음) |
|------|---------|---------|------------|-----------|
| LightGBM | 0.5529 | 0.6115 | 0.3186 | 0.2131 |
| TCN | 0.5980 | 0.5896 | 0.3231 | 0.1957 |
| **Ensemble** | 0.5694 | **0.6152** | 0.3197 | 0.1923 |

Ensemble Test AUC 0.6152는 메모리에 기록된 production AUC 0.6170(+20% lift, 기준 모델 대비 향상도) 수치와 근사 일치한다. Brier score 0.1923은 보정(calibration)이 어느 정도 작동하고 있음을 시사한다. 다만 검증(val) AUC 0.5694가 테스트 AUC 0.6152보다 낮다는 점은 중대한 신호다(섹션 16 M-4 참조). 분포 shift(데이터 분포가 시간에 따라 달라지는 현상) 가능성, val 분기에 어려운 시장 이벤트가 몰렸을 가능성, 또는 hyperparameter(학습 전에 사람이 정하는 모델 옵션)가 test set 에 우연히 맞은 가능성이 모두 열려 있다. positive ratio(양성 클래스 비율. 폐업 라벨 비율) 자체도 val 20.6% / test 26.1%로 기간별 불균형이 있다(scale_pos_weight(LightGBM 에서 양성 클래스 가중치 조정) 사용 중).

### 2.5 12 sprint 로드맵: 무엇이 살아남았고 무엇이 굴러떨어졌나

KEEP 7개 sprint는 평가 표준화(E), 시간 기반 split(C), 3분할 test(D), 산업 p75 라벨(A), 동 잔차 피처(B-3), LGBM L1/L2 정규화(과적합 방지를 위해 가중치 크기를 제한하는 기법)(S8), B-3 lookup pkl 저장(S9)이다. 모두 데이터 분할·라벨·정규화 같은 기반 인프라이지 화려한 모델 변경이 아니다.

ROLLBACK 5개는 신규 8 파생 피처(B-1, AUC 0.024 하락), Isotonic(보정 알고리즘 두 종류 중 하나. Platt 와 함께 isotonic / Platt 로 흔히 묶임) calibration(D-3, AUC 0.038 하락 + threshold collapse(분류 임계값이 한쪽으로 쏠리는 현상)), Additive ensemble(A-2 grid search w=0), TCN dropout(과적합 방지를 위해 학습 중 일부 노드를 끄는 기법) 0.2→0.3(S10, noise(통계적으로 의미 없는 변동)), num_leaves(LGBM 트리당 잎 개수) 31→15(S11, AUC 0.017 하락), n_estimators(트리 개수) 200→100(S12, noise)이다. 메모리 기록대로 hyperparameter sweep(여러 옵션을 바꿔가며 실험)는 이미 plateau(개선이 정체된 구간)에 도달했고, 다음으로 의미 있는 변화는 새 ETL(Extract-Transform-Load, 데이터 추출·가공·적재 파이프라인)(B-4) 도입 이후가 될 가능성이 높다.

### 2.6 추론 서빙(serving, 학습된 모델을 실제 요청에 응답시키는 단계)은 어떻게 돌아가는가

`models/closure_risk/predict.py`의 `_load_models()`는 모듈 수준 dict 캐시(`_cache`)를 사용해 startup 시 1회만 로드하고 이후 재사용한다. SHAP 설명은 LightGBM 쪽은 TreeExplainer(SHAP 의 알고리즘 변형. 트리 모델용), TCN 쪽은 GradientExplainer(SHAP 의 알고리즘 변형. 신경망용)를 우선 시도하고 실패하면 DeepExplainer로 fallback 한다. `predict_topk()`는 마포 16동 × 10업종 = 최대 160 조합을 순회하면서 공유 캐시 덕에 model reload가 발생하지 않는다. `EXCLUDE_COMBOS`로 학습에서 제외된 조합은 추론에서도 자동 차단된다.

문제는 SHAP fallback 이 `except Exception: return []` 한 줄로 무음 처리된다는 점이다(섹션 16 H-3 참조). 운영에서 설명이 사라져도 메트릭으로 잡히지 않는다.

---

## 3. 매출 결측 보간 (Sales Imputation)

### 왜 중요한가

서울 전역 `seoul_district_sales` 테이블은 424동 × 10업종 × 24분기 = 101,760 grid(셀 격자) 중 13,822 셀이 결측이다. 마포만 보면 16동 × 16분기 × 16업종 부근에서 137건이 비어 있다. 이 결측을 채우지 못하면 폐업 모델·경쟁 모델이 동일 grid를 사용할 때 학습 데이터가 끊긴다. 보간 품질이 모든 다운스트림(downstream, 이 결과를 받아 쓰는 후속 모델·기능) 모델의 상한선이 된다.

### 3.1 결측 메커니즘과 평가 방식

핵심 통찰은 결측이 단순 random 이 아니라 MNAR(Missing Not At Random. 결측이 무작위가 아니라 특정 조건에서 집중)이라는 점이다. 점포 수 15개 이하 소규모 셀에서 결측이 집중적으로 발생한다(영업 비밀, 신고 누락, 매출 0 셀의 통계 처리 등 복합 원인). 따라서 평가도 동일 조건 셀(`store_count <= 15`)에 대해 5-fold CV(데이터를 5 등분해 돌아가며 평가)로 결측을 인위 재현해 측정한다 -- 이른바 **MNAR-Mimic CV**다. 또한 `validation/audit_dong_avg_leak.py`는 dong 평균 prior 계산 시 fold 사이 누수가 없는지 LOO(Leave-One-Out, 데이터 한 건씩 빼고 평가하는 방식) 방식으로 감사한다.

### 3.2 어떤 모델이 이겼는가

`docs/ml-models/imputation/sales-model-comparison.md` v3 MNAR WAPE 비교 결과는 다음과 같다.

| 모델 | MNAR WAPE | Pearson r(두 변수 간 선형 상관계수. -1~1) |
|------|----------|----------|
| **ExtraTrees** | **15.96%** | 0.955 |
| RandomForest(여러 결정 트리 결과를 평균내는 앙상블 모델) | 18.03% | 0.949 |
| GBM(Gradient Boosting Machine, 경사 부스팅 일반형) | 25.71% | 0.914 |
| HistGBM(히스토그램 기반 GBM, sklearn 의 빠른 구현) | 22.96% | 0.918 |
| Ridge(L2 정규화 선형 회귀) | 60.00% | 0.370 |

`docs/ml-models/imputation/sales-sota-comparison.md`의 SOTA 라이브러리까지 포함한 결과는 더 인상적이다.

| 모델 | MNAR WAPE | 비고 |
|------|----------|------|
| **ExtraTrees** | **15.96%** | 1위 |
| RandomForest | 18.03% | |
| XGBoost(또 다른 인기 경사 부스팅 라이브러리) | 18.53% | |
| LightGBM | 22.64% | |
| CatBoost | 26.10% | |
| HyperImpute/hyperimpute(연구 라이브러리) | 64.09% | 162초 |
| HyperImpute/missforest | 186.51% | FAIL |

연구 라이브러리(HyperImpute/missforest)가 우리 도메인에서는 처참하게 무너졌고, ExtraTrees가 학술 SOTA를 누른 흔치 않은 사례다. 도메인 데이터 특성이 트리 앙상블에 강하게 부합했음을 보여준다.

### 3.3 하이퍼파라미터와 전이 학습 결정

`validation/phase_a_seoul_10ind.py:39-48`의 ExtraTrees 최종 파라미터는 Optuna(하이퍼파라미터 자동 탐색 라이브러리) 튜닝 후 확정된 `n_estimators=300, max_depth=35, min_samples_leaf=1, min_samples_split=2, max_features=1.0, bootstrap=False, random_state=42`이다.

전이 학습(transfer learning, 다른 도메인 모델을 가져와 finetune(미세 조정)) 실험 결과(`docs/ml-models/imputation/sales-step2-transfer-learning.md`)는 더욱 흥미롭다. Mapo-only ExtraTrees가 WAPE 13.35%, Pearson r 0.965로 최고 성능이었고, 서울 전역에서 학습한 Seoul_ET(58.67%), Seoul_FT(61.01%), Seoul_TabPFN(57.64%)은 마포 도메인에서 모두 크게 열화했다. 결국 **Mapo-only 모델이 최종 채택**되었고, "더 큰 데이터 = 더 좋은 모델"이라는 직관과 정반대 결론이 데이터로 증명되었다.

### 3.4 Production 사용 방식

보간 자체는 training data 준비 단계(offline, 미리 1회 실행하고 결과만 저장)에서 1회 실행되고, production inference(추론, 실제 요청 처리) 시점에는 이미 imputed 결과가 DB에 적재되어 있는 상태다. 결과물은 `validation/results/imputed_mapo_full_v3.csv`에 보존된다. 이 분리 덕에 inference latency(요청 응답 지연)에는 영향이 없다.

---

## 4. 경쟁 모델 (Competition Model)

`docs/ml-models/competition/competition-model.md`에 정의된 경쟁 분석은 ML이 아닌 **순수 룰 기반(if/else 규칙으로 구성, 학습 없음) 3-Layer 프레임워크**다. Layer 1 직접 경쟁(반경 500m/1km/1.5km 동업종 점포 수와 포화도 지수, 가중치 1.0), Layer 2 카니발리제이션(동일 브랜드 자기잠식, 거리 기반 decay(거리에 따라 영향이 줄어드는 함수), 가중치 1.5), Layer 3 간접 경쟁(대체재 카테고리 소비 예산 경쟁, 가중치 0.5)으로 구성된다. 경쟁 반경 기준은 500m 이내 위험, 500m~1km 주의, 1km 이상 안전이다.

### 왜 ML이 아닌가

직접 경쟁의 메커니즘이 매우 명확하고(거리 + 동일 업종 + 점포 수), ML로 학습할 라벨(경쟁 강도 정답)을 만들 수 없기 때문이다. 도메인 지식 기반 휴리스틱(경험 규칙)이 더 빠르고 설명 가능하다. 다만 `docs/ml-models/model-adoption-roadmap.md`에는 Huff 모델(점포 인력과 거리 감쇠로 시장 점유율을 확률화하는 고전 상권 모형)로 개선하자는 검토가 있고, 이는 점포의 인력(매장 면적·브랜드력)과 거리 감쇠를 결합한 확률적 시장 점유 모형이다. 아직 미구현이며 우선순위는 P2 영역이다.

성능 평가 수치는 없다. ML이 아니므로 회고에서 별도 KPI(Key Performance Indicator, 핵심 성과 지표)는 두지 않는다.

---

## 5. 고객 매출 평가 (Customer Revenue Evaluation)

`docs/ml-models/evaluation/customer-revenue-evaluation-2026-04-29.md`의 결론은 단호하다: **C 모델(MLP) 폐기.** 학술·실용·UI 세 축 모두에서 group_mean baseline 이 더 나았기 때문이다.

학술 축에서 MAE(Mean Absolute Error, 평균 절대 오차)는 MLP 0.0378 대 group_mean 0.0319로 18% 악화되었다. 실용 축에서는 합정 카페 4분기 시뮬레이션 결과 분기마다 결정이 동일했고 차이도 5pp(percentage point) 이하라 의사결정에 영향을 주지 못했다. UI 축에서는 baseline으로 교체해도 사용자 인지가 불가능했다 -- 즉 사용자 입장에서 모델 차이가 없다는 뜻이다. 16개 차원 중 MASE(Mean Absolute Scaled Error. 단순 baseline 대비 얼마나 잘했는지. 1 미만이면 baseline 보다 나음) < 1.0인 차원은 `age_20_ratio` 단 하나였고, 나머지 15개는 모두 group_mean이 더 정확했다.

### 어떻게 처리되는가

`models/customer_revenue/predict.py`는 `_legacy_mlp.py`로 리네임 권고가 나와 있고, 대체 모델은 (분기 × 동 × 업종) group_mean baseline 이다. 프론트엔드 `CustomerSegmentCard`와 PDF 5페이지는 인터페이스를 그대로 유지하므로 사용자에게는 변화가 없다. 다만 `backend/src/main.py`의 `_warmup_customer_revenue()` startup 핸들러가 아직 살아 있어 불필요한 모델 로딩 시간이 남아 있다(섹션 16 M-1).

### 왜 중요한가

이 결과는 "ML이 항상 baseline을 이기는 게 아니다"라는 소중한 교훈을 문서화한 사례다. 이런 음성 결과(negative result, 가설이 기각된 결과)를 실제로 폐기까지 가져간 의사결정 문화가 본 프로젝트의 가장 큰 강점 중 하나다(섹션 15-1 참조).

---

## 6. 생활인구 예측 (Living-Pop Forecast)

### 6.1 6라운드 학술 평가

`docs/ml-models/evaluation/living-pop-forecast-v2-vs-v3-report.md`에 6라운드의 도전과 실패가 모두 기록되어 있다.

| 모델 | Task | MASE (same-period) | MASE (Hyndman in-sample) | 결론 |
|------|------|-------------------|--------------------------|------|
| v2 (TCN dong_one_hot) | 분기 | 2.54 | ~4.5 | FAIL |
| v3 (sin/cos+외부) | 분기 | 13.08 | ~13 | FAIL (R²(결정계수. 모델이 데이터 분산을 얼마나 설명하는지. 1=완벽)=-0.21) |
| v4_residual | 분기 | 1.042 (시간순 재측정) | 0.905 | FAIL |
| v5 group features | 분기 | 1.005~1.292 | -- | FAIL, 폐기 |
| ARIMA(고전 통계 시계열 모델) | 분기 | 2.54 | -- | FAIL |
| v6_dow_hour_residual | dow×hour | 0.999 | 0.945 | FAIL (naive 동급) |
| v7_daily_residual | 일별 | 1.0004 (lag7) | 0.804 | FAIL |
| **naive_lag1** | 분기 | 1.000 | 0.796 | **Production 채택** |
| **naive_lag7** | 일별 | 1.000 | -- | **Production 채택** |

여섯 차례 모델을 바꾸고도 단순 naive baseline 을 이기지 못했다. 그리고 마지막 결정은 **naive 를 운영에 올리는 것**이었다.

### 6.2 왜 naive를 못 이기는가

마포 16동 × 24시간대 분기 평균 유동인구는 자기상관(autocorrelation, 직전 값과 현재 값이 비슷한 정도)이 극도로 높다(naive_lag1 MAPE(Mean Absolute Percentage Error. 예측이 실제값에서 평균 몇 % 빗나갔는지) 2.11%). Makridakis et al.(2018)의 M4 논문에서 보고한 random walk inefficiency(무작위 보행 데이터에서는 단순 모델이 복잡 모델을 이기는 함정) 함정과 동일한 데이터 특성이다. 안정적인 시계열에서는 직전 값을 그대로 쓰는 게 최선의 예측이고, 복잡한 모델이 이를 능가하려면 매우 강한 외부 신호가 필요한데 마포 유동인구에서는 그 신호가 없다.

### 6.3 평가 split 결함의 발견

처음 v4_residual은 MASE 0.997, Hyndman 0.905로 보고되어 한때 production 후보였다. 그러나 `evaluate_all.py`의 `_split_indices`가 시간순이 아니라 그룹순 분할이었음이 발견되었고, 시간순으로 재측정하니 MASE 1.042로 naive에도 못 미쳤다. 이 발견 덕에 옵션 C/D(v4_residual 사용)는 폐기 확정되었다. 평가 인프라 자체의 결함을 잡아낸 사례라 의의가 크다.

### 6.4 어떻게 운영에 적용했는가

`models/living_pop_forecast/predict_naive.py`의 `predict_peak_naive()`는 기존 `predict_peak()`와 시그니처(함수 인자/반환 타입의 형태)가 완전 호환된다. `models/interface.py:541-545`에서 import 한 줄만 교체하면 된다. 16동 × 24시간 데이터 캐시(`_DF_CACHE`)도 별도로 둬서 DB 반복 쿼리를 차단했다.

---

## 7. 데이터 파이프라인 (Data Pipelines)

`data/pipeline/` 디렉터리에는 학습 데이터 준비를 위한 6개 주요 스크립트가 있다. `build_training_dataset.py`는 CPI(Consumer Price Index, 소비자 물가 지수) 월별 데이터를 분기 평균 CSV로 만들고 통합 학습 데이터셋을 구성한다. `preprocess_seoul_all.py`와 `preprocess_seoul_population.py`는 서울 전역 전처리와 유동인구 전처리를 담당한다. `collect_kakao_stores.py`는 Kakao API로 점포를 수집하고, `collect_subway_inflow.py`는 지하철 유입 데이터를 수집하며, `load_to_db.py`가 DB 적재를 마무리한다.

### CPI 하드코딩 문제

`build_training_dataset.py`의 `CPI_MONTHLY` dict 에는 2019~2024 근사값이 직접 박혀 있다. 외부 API 연동 없이 수동 입력이라, 2024 이후 분기를 추가할 때 갱신이 누락될 수 있다. KOSIS(통계청 국가통계포털) 또는 한국은행 OpenAPI 연동으로 대체하는 것이 P2 작업으로 잡혀 있다(섹션 17 참조).

---

## 8. 검증 인프라 (Validation Infrastructure)

`validation/` 디렉터리에는 11개 이상의 검증 스크립트가 있다. 핵심을 추리면, 매출 보간 v1/v2/v3 비교(`model_comparison_v1v2v3.py`), dong 평균 피처 fold-level 누수 감사(`audit_dong_avg_leak.py`), SOTA 보간 라이브러리 비교(`sota_comparison.py`), 하이퍼파라미터 탐색(`hyperparam_search.py`), 폐업·매출 백테스트(backtest, 과거 데이터로 모의 운영해 성능 측정)(`backtest_closure.py`, `backtest_revenue.py`), 서울 10업종/63업종 매출 역추적(`phase_a_seoul_10ind.py`, `phase_b_seoul_63ind.py`), 16-fold LODO 검증(`experiments/living_pop/lodo_validation.py`), customer revenue C 모델 학술 평가(`experiments/customer_revenue/baseline_c.py`)다.

`validation/metrics/forecast_metrics.py`에는 MAE, RMSE(Root Mean Squared Error, 제곱 오차의 제곱근), NRMSE(정규화 RMSE), MAPE, sMAPE(symmetric MAPE, 대칭형 MAPE), R², MASE(same-period), MASE(Hyndman in-sample)가 통합 구현되어 있어 C/D/E 모델이 모두 같은 지표 모듈을 공유한다. 평가 일관성이 확보되어 있다는 점은 본 프로젝트의 강점이다.

---

## 9. 노트북 (Notebooks)

`notebooks/` 디렉터리는 존재하지만 내부 파일이 없다(빈 디렉터리). 탐색적 분석(EDA, Exploratory Data Analysis)은 모두 `validation/` 스크립트와 `tests/` 단위 테스트로 옮겨져 수행되었다. 이는 코드 일관성에는 도움이 되지만, EDA 과정의 재현·감사가 어려워지는 부작용이 있다(섹션 16 L-1). 회고에서 언급된 "왜 그 피처를 골랐는가"의 흔적이 노트북에 남아 있어야 신규 멤버 인계가 수월해진다.

---

## 10. 피처 엔지니어링 (Feature Engineering)

### 10.1 폐점 위험 피처의 설계 철학

폐점 위험 모델 피처는 크게 lag, YoY, 변화량, 정적, 계층, 잔차 다섯 종류로 분류할 수 있다. lag 피처는 `closure_rate_lag1/2`, `store_count_lag1`, `monthly_sales_lag1`, `rent_1f_lag1`이다. YoY 피처는 `sales_yoy_change = (sales_t - sales_t-4) / |sales_t-4|`로 계산한다. 변화량 피처는 `closure_rate_diff`, `store_change`, `rent_change`다. 정적 피처는 `franchise_ratio`, `vacancy_rate`, `trend_score`, `adstrd_flpop`, `bus_flpop`이다.

가장 흥미로운 두 피처는 계층(A-2)의 `industry_prior_pred`와 잔차(B-3)의 `dong_closure_rate_residual_lag1`이다. 전자는 industry 수준 집계의 Stage1 LGBM 예측값을 그대로 동(洞) 모델 입력으로 넣는다 -- 산업 평균이라는 강한 사전이 동 데이터 부족을 보완한다. 후자는 `closure_rate_lag1 - industry_mean(train-only)`로, Gelman & Hill(2006)의 partial pooling(부분 통합, 개별 그룹과 전체 평균을 적절히 섞어 추정하는 베이지안 기법) 분해를 그대로 따왔다. 이 두 피처가 12 sprint 중 가장 큰 lift 를 만들었다.

### 10.2 누수 검증을 어떻게 하는가

`_make_labels(train_quarters=...)`는 train 분기만으로 industry p75 fit, `add_dong_residual_feature(train_quarters=...)`는 train 분기만으로 industry mean fit, `_compute_industry_p75_train()`은 `min_samples=4` 미만 industry는 NaN으로 두고 호출자에서 fallback 처리한다. `validation/audit_dong_avg_leak.py`는 fold-level dong_avg 피처 누수를 LOO 방식으로 감사하고 WAPE delta(차이) 3pp 이하를 합격선으로 삼는다.

### 10.3 매출 보간 피처

`validation/phase_a_seoul_10ind.py`에서 사용하는 피처는 `store_count`, `log_store_count`, `kosis_index`, dong 레벨 통계, 분기 계절성이다. ExtraTrees(Optuna 튜닝)가 final model로 채택되었다.

---

## 11. Train/Test Split

### 11.1 폐점 위험 모델

quarter 기준 시간순 3분할(학술 표준). 같은 quarter는 한 split 에만 포함되며 분기 경계가 명확하다. 최소 7분기가 필요하고 미달 시 `ValueError`를 명시적으로 raise(예외를 발생시킴)한다. Random split 은 deprecated(폐기 예정 표시) 처리되어 WARNING 로그가 남고 `split_strategy=random`을 명시해야만 동작한다.

### 11.2 생활인구 예측

시간순 70/15/15 분할이 기본이다. 초기 `_split_indices`가 그룹순 분할이었던 결함은 발견 즉시 수정되었다(섹션 6.3 참조). LODO 16-fold는 동(洞)별 일반화 검증용이고, 그 과정에서 서교동 outlier(이상치, 다른 데이터들과 동떨어진 값)가 4배 악화로 드러나 별도 조사 대상이 되었다(섹션 16 L-2).

### 11.3 매출 보간

MNAR-Mimic 5-fold CV는 `store_count <= 15` 셀에 한정해 결측을 인위 재현한다. Phase A 서울 10업종에서는 random 10-fold CV를 사용한다. 폐점 모델에서 수정 전에 있었던 random split 잔재(val AUC 0.85 부풀림)를 같은 실수가 반복되지 않도록 회고 문서에 기록해두는 게 좋다.

---

## 12. 하이퍼파라미터 튜닝

### 12.1 LightGBM (폐점 위험)

`train.py`의 `DEFAULT_CONFIG`에 고정된 값은 `num_leaves=31`, `n_estimators=200`, `learning_rate=0.05`(학습 속도, 한 스텝마다 가중치를 얼마나 갱신할지), `reg_alpha=0.1`(S8 추가, L1 정규화 계수), `reg_lambda=0.1`(S8 추가, L2 정규화 계수)이다. S11에서 `num_leaves`를 15로 줄여보았으나 AUC 0.017 하락으로 rollback, S12에서 `n_estimators`를 100으로 줄였으나 noise로 rollback되었다. **Optuna는 사용하지 않았고 12회 수동 sprint로 sweep 한 결과 plateau 도달이 확정되었다.** 추가 튜닝은 B-4 새 ETL 이후로 미뤘다.

### 12.2 ExtraTrees (매출 보간)

Optuna 튜닝 결과는 `n_estimators=300, max_depth=35`이고 결과 고정 후 재실험은 없었다. 도메인 특성상 더 깊은 트리가 효과적이었다.

### 12.3 TCN (폐점 위험)

`tcn_epochs=50`(전체 데이터셋 반복 횟수), `tcn_lr=5e-4`, `tcn_batch_size=32`(한 번에 학습하는 샘플 수), `tcn_patience=7`(개선 없을 때 early stop 까지 기다릴 epoch 수), `dropout=0.2`. S10에서 dropout 을 0.3으로 올렸으나 AUC delta는 0.0001로 noise였고 rollback되었다.

---

## 13. 모델 서빙 (Model Serving)

### 13.1 FastAPI Startup 워밍업

`backend/src/main.py` 180-210줄에 두 개의 startup 핸들러가 있다. `_warmup_customer_revenue()`는 customer_revenue MLP 가중치를 로드해 첫 `/predict` 콜드 스타트(서버 기동 직후 캐시가 비어 있어 응답이 느린 현상)를 제거한다. `_warmup_timeseries_cache()`는 `load_timeseries()`의 TTL=300s(Time-To-Live, 캐시 유효 시간 5분) 캐시를 미리 채워서 첫 `/predict` 응답을 8.1초에서 4.4초로 46% 줄인 측정 결과가 있다.

문제는 두 핸들러 모두 `except Exception: print("warmup skip")` 한 줄로 무음 처리된다는 점이다(섹션 16 H-4). DB 다운 같은 실질적 장애가 무시되고 서버가 그대로 기동되며, 첫 실제 요청에서 느린 응답이나 에러가 발생한다. 또한 customer revenue MLP는 이미 폐기 결정된 모델인데 워밍업 핸들러가 살아 있다(섹션 16 M-1).

### 13.2 4-Layer Cache 구조

추론 latency를 잡기 위한 4단계 캐시가 있다. Layer 1은 `models/lstm_forecast/data_prep.py`의 `_CACHE_TTL`(300초)로, `load_timeseries()` 결과를 보관해 DB 반복 쿼리를 차단한다. Layer 2는 `models/closure_risk/predict.py`의 `_load_models()` 모듈 수준 dict로, LGBM/TCN/scaler/b3_lookup이 첫 로드 후 재사용된다. Layer 3는 `functools.lru_cache`(Python 내장 LRU 캐시 데코레이터)로 임계값 재계산을 방지한다. Layer 4는 `models/living_pop_forecast/predict_naive.py`의 `_DF_CACHE` dict로 naive 예측용 DB 결과를 캐시한다. 소규모 팀 프로젝트로는 운영 성숙도가 높다.

### 13.3 폐점 위험 추론 경로

`predict(dong_code, industry_code)` 호출이 들어오면, `_load_models()`가 cache hit 시 즉시 반환하고, B-3 dong 잔차 feature를 `b3_lookup` dict에서 조회하고, Stage1 industry prior를 예측해 LGBM_FEATURES 17개를 조립하고, LGBM `predict_proba`(클래스 확률 반환)와 TCN forward pass(신경망 입력→출력 한 번 통과)를 각각 실행한 뒤, w_lgbm=0.480 / w_tcn=0.520으로 앙상블하고, 마지막에 SHAP `_top_signals()`를 호출해 risk_score와 함께 반환한다. SHAP 부분에서 `except Exception: return []` 무음 fallback이 발생한다.

### 13.4 동시성 위험

`_cache` dict는 module-level 단순 dict로 asyncio concurrency(비동기 동시 실행)에서 double-init 경쟁 조건(race condition, 두 작업이 동시에 같은 자원을 초기화하려다 충돌하는 상황)이 가능하다. 현재 단일 워커 배포라 미발현이지만 `workers > 1`로 스케일하면 즉시 위험이 된다(섹션 16 M-5). `asyncio.Lock()` 또는 `threading.Lock()`(동시 접근을 직렬화하는 락) 추가가 P2 작업이다.

---

## 14. 코드 품질: 재현성, 버전 관리, 테스트

### 14.1 재현성 (Reproducibility)

LightGBM은 `train.py`의 `DEFAULT_CONFIG`에서 `random_state=42`(난수 시드 고정값)가 설정되어 있고, Stage1 LGBMRegressor도 `stage1_industry_prior.py`에서 동일하게 42로 고정되어 있다. ExtraTrees는 `validation/phase_a_seoul_10ind.py`의 `TUNED_PARAMS`에 `random_state=42`가 박혀 있다. `_time_based_split`은 결정론적 quarter 분할이라 시드가 불필요하다.

문제는 PyTorch와 NumPy 글로벌 시드다. `torch.manual_seed()`가 없고 `numpy.random.seed()`도 미설정이다. 결과적으로 TCN 학습 결과가 실행마다 달라지고, 그것을 기반으로 산출되는 ensemble weights(w_tcn=0.520)도 변동한다(섹션 16 H-2). 운영 가중치(`tcn.pt`)는 고정되어 있지만, 재학습 시 동일 결과가 보장되지 않는다는 게 큰 결함이다.

### 14.2 아티팩트 버전 관리

학습 가중치는 `models/closure_risk/weights/`에 `lgbm.pkl`, `tcn.pt`, `scaler.pkl`, `b3_lookup.json`, `metrics.json` 형태로 저장된다. 그런데 `.bak_34f` 같은 패턴의 백업 파일이 다수 존재하고 git으로 관리되지 않는다 -- 이는 정리 대상이다. 더 큰 문제는 `metrics.json`에 `trained_at` 타임스탬프나 git hash(커밋 해시, 코드 버전 식별자)가 없다는 점이다. 어느 시점·어느 commit에서 학습된 모델인지 사후 추적이 불가능하다. P1 작업으로 `trained_at`, `git_hash`, `python_version`, `dataset_hash` 같은 메타데이터 필드 추가가 잡혀 있다(섹션 17).

### 14.3 테스트 커버리지

`tests/`에는 closure_risk 관련 10개, living_pop_forecast 관련 8개 파일이 있다. closure_risk 쪽은 `test_closure_risk_split.py`(temporal split 경계, 비중복, 소규모 데이터 ValueError), `test_closure_risk_b3.py`(B-3 잔차 column 존재, train-only fit, LGBM_FEATURES 수=17), 그리고 label 생성·feature 조립·predict 인터페이스 등 8개가 더 있다. living_pop_forecast 쪽은 naive predict 인터페이스 호환성 테스트가 핵심이다.

테스트가 비어 있는 영역은 매출 보간 validation 스크립트(pytest 미연결), living_pop 일별 모델(v7), 경쟁 모델(rule-based, 테스트 없음), `_warmup_*` startup 핸들러다. 매출 보간은 운영 결과물이 DB에 적재되어 있어서 회귀 테스트(regression test, 기존 동작이 깨지지 않는지 검증)가 더 중요한데 누락되어 있다.

### 14.4 Import 스타일 이슈 한 가지

`models/emerging_district/data_prep.py:67`에는 `from models.lstm_forecast.data_prep import load_timeseries  # noqa: E402`가 있다. 함수 내부 lazy import(필요한 시점에만 import 하는 지연 임포트)로 circular dependency(모듈 A↔B 가 서로를 import 해서 순환되는 의존성)를 회피한 것인데, `noqa` 주석이 필요한 코드는 일반적으로 모듈 구조 재설계가 더 깔끔한 해결책이다. 우선순위는 낮다.

---

## 15. 강점

### 15.1 음성 결과(Negative Result) 문화

6라운드 living-pop 실패, customer revenue MLP 폐기, CPC/IPF/LLM-as-judge 거부 -- 이 모든 실패가 docs에 명문화되어 있다. 기술 부채를 숨기지 않고 결정 근거를 남기는 문화는 본 프로젝트의 가장 큰 자산이다. "ML이 baseline을 못 이긴다"는 결론이 실제 운영 폐기까지 이어진 흔치 않은 사례다.

### 15.2 시간 기반 분할 + 누수 방지의 엄격성

`_make_labels(train_quarters=...)`는 train 분기 분위수만 사용하고, `add_dong_residual_feature(train_quarters=...)`도 같은 원칙이다. LOO 누수 감사(`audit_dong_avg_leak.py`)와 LODO 16-fold CV는 파이프라인 전 단계에서 누수가 없음을 검증한다. 학술 표준 그대로다.

### 15.3 계층적 피처 엔지니어링의 학문성

Stage1 산업 prior → Stage2 LGBM 입력으로 이어지는 stacked generalization 은 Wolpert(1992)를 명시 인용하고, B-3 dong 잔차는 Gelman & Hill(2006)의 partial pooling 을 인용한다. 학문적 근거가 있는 피처 설계는 신뢰도와 인계 가능성이 모두 높다.

### 15.4 캐시 인프라

4-layer cache로 cold start 를 8.1s → 4.4s(46% 개선)로 줄였고 DB 반복 쿼리도 차단했다. 소규모 팀 프로젝트 기준으로 운영 성숙도가 높다.

### 15.5 SHAP 설명가능성

LightGBM은 TreeExplainer, TCN은 GradientExplainer→DeepExplainer 이중 경로로 사용자에게 top-3 feature signal 을 제공한다. black-box(내부 작동을 직접 들여다볼 수 없는 모델) 모델 신뢰도를 보완한다(다만 silent fallback 이슈가 있다, 섹션 16 H-3).

### 15.6 MNAR 벤치마크의 현실성

단순 random missing이 아니라 실제 결측 메커니즘(`store_count <= 15`)을 재현한 MNAR-Mimic CV로 모델을 선정했다. HyperImpute 같은 SOTA 라이브러리가 우리 도메인에서 망가진 것을 발견한 점은 학술과 실무의 간격을 보여주는 사례다.

---

## 16. 리스크 / 기술 부채

> 등급 안내: HIGH(시급, 운영 영향 큼) / MEDIUM(중요하지만 즉각 장애는 아님) / LOW(여유 있을 때 정리).

### HIGH

**H-1. DB 자격증명 하드코딩 (5개 파일)**

확인된 파일은 `models/closure_risk/data_prep.py:165`, `models/emerging_district/data_prep.py:31`이고 추정 파일은 `models/living_pop_forecast/data_prep.py`, `models/lstm_forecast/data_prep.py`, `validation/phase_a_seoul_10ind.py` 세 개다. 패턴은 `os.environ.get("POSTGRES_URL", "postgresql://postgres:MapoSpotter1!%23@mapo-simulator...")`로, fallback 문자열에 평문 비밀번호가 박혀 있다. `.env`(환경 변수 파일)가 미로드되면 자동으로 fallback이 사용되며, 깃 히스토리에도 그대로 남아 있다. 즉시 비밀번호 회전, fallback 제거, `.env` 미로드 시 `ValueError` raise로 전환해야 한다.

**H-2. PyTorch seed 미설정**

TCN 가중치 `tcn.pt`는 저장되어 있지만, 재학습 시 동일 결과가 보장되지 않는다. 앙상블 weights(w_tcn=0.520)도 실행마다 달라질 수 있다. `train.py` 상단에 `torch.manual_seed(42); torch.cuda.manual_seed_all(42); numpy.random.seed(42); random.seed(42)`를 추가해야 한다.

**H-3. Silent SHAP Fallback**

`models/closure_risk/predict.py`의 `_top_signals()`와 `_top_signals_tcn()`이 모두 `except Exception: return []` 한 줄로 끝난다. SHAP 실패 시 signals가 빈 리스트로 반환되고 호출자는 알 수 없다. 구체적 예외 타입(예: `ValueError`, `RuntimeError`)으로 좁히고 `logger.warning` + Sentry 알람을 추가해야 한다.

**H-4. Startup Warmup Silent Failure**

`backend/src/main.py`의 `_warmup_customer_revenue()`와 `_warmup_timeseries_cache()`가 모두 `except Exception: print("warmup skip")`로 끝난다. DB 다운 같은 실질적 장애가 무시되고 기동이 계속된다. 첫 실제 요청에서 느린 응답이나 에러가 발생하지만 메트릭으로 잡히지 않는다.

### MEDIUM

**M-1. Customer Revenue MLP 미제거**

`_warmup_customer_revenue()`가 아직 실행 중이다. 평가 결과(2026-04-29) group_mean baseline 채택이 결정되었지만 MLP 코드가 잔존하고 매번 startup마다 가중치를 로드한다. 불필요한 모델 로딩 시간이 남아 있다.

**M-2. LGBM Early Stopping(검증 지표가 더 나아지지 않으면 학습을 중단해 과적합을 막는 기법) 미설정**

`lgbm_n_estimators=200`이 고정되어 있고 `eval_set + early_stopping_rounds`가 설정되지 않아 과적합 조기 감지가 불가능하다. Sprint 12에서 100→200을 시도하다가 rollback한 경험이 있어, 근본적으로는 early stopping을 통한 자동 결정이 정답이다.

**M-3. CPI 하드코딩**

`data/pipeline/build_training_dataset.py`의 `CPI_MONTHLY` dict는 2019-2024 근사값이 수동 입력되어 있다. 2024 이후 분기 추가 시 갱신이 누락될 위험이 있다.

**M-4. Val AUC < Test AUC 역전**

`metrics.json` 기준 LightGBM의 val AUC는 0.5694, test AUC는 0.6152다. 일반적인 방향(val ≥ test)과 반대다. 2023 validation 기간이 특히 어려운 시장 조건(코로나 재확산이나 금리 인상 등)이었거나, hyperparameter 선택이 test set에 과도하게 최적화됐을(=test set leakage 의심) 가능성이 모두 있다. 1~2일 분량의 조사가 필요하다.

**M-5. _cache 스레드 안전성**

module-level dict이고 asyncio lock이 없다. uvicorn `workers=1` 현재 안전하지만 스케일 시 즉시 위험이다.

### LOW

**L-1. notebooks/ 디렉토리 비어 있음**

탐색적 분석 과정이 보존되지 않아 재현·감사가 어렵다. EDA Jupyter 노트북을 복원하면 신규 멤버 인계가 수월해진다.

**L-2. 서교동 이상치 미처리**

living_pop 일별 데이터에서 서교동 tau(켄달 타우, 순위 상관계수)=0.5124가 전체 평균 0.9797 대비 이상치다. 원인 미조사 상태로 production에 반영된다.

---

## 17. 개선 우선순위

### P0 — 즉시 (보안·재현성)

DB 자격증명 제거가 최우선이다. `models/*/data_prep.py` 5개 파일의 fallback 문자열을 모두 삭제하고, `.env`가 없으면 `ValueError`를 raise하도록 강제한다. 비밀번호도 즉시 회전한다.

PyTorch seed는 `models/closure_risk/train.py` 상단에 `torch.manual_seed(42)` 한 줄로 시작해 numpy/random까지 일치시킨다.

SHAP silent fallback은 `models/closure_risk/predict.py`에서 `except Exception` → `except (ValueError, RuntimeError)` + `logger.warning`으로 좁힌다.

Warmup silent fallback은 `backend/src/main.py`에서 `except Exception as e: logger.error(...)` 패턴으로 바꾸고, 실패 원인을 메트릭/알람으로 끌어올린다.

### P1 — 단기 (품질·신뢰성)

Customer revenue MLP 제거: `backend/src/main.py`의 warmup 핸들러를 삭제하고 group_mean 서빙 코드만 남긴다. `models/customer_revenue/predict.py`는 `_legacy_mlp.py`로 리네임한다.

LGBM early stopping: `models/closure_risk/train.py`에 `early_stopping_rounds=30`과 `eval_set`을 추가한다.

모델 버전 메타데이터: `models/closure_risk/weights/metrics.json`에 `trained_at`, `git_hash`, `python_version` 필드를 추가한다.

Val < Test AUC 역전 조사: 2023 val 기간의 시장 이벤트를 확인하고 필요시 val 범위를 재조정한다.

### P2 — 중기 (운영·확장)

CPI 외부 API 연동: KOSIS API 또는 한국은행 OpenAPI를 연결하고 `CPI_MONTHLY` dict는 제거한다.

`_cache` 스레드 안전: `asyncio.Lock()` 또는 `threading.Lock()`을 추가한다.

서교동 이상치: 일별 데이터 원본을 확인하고 보정 또는 exclusion(제외)을 결정한다.

Imputation 모델 pytest 연결: `validation/phase_a_seoul_10ind.py`를 `tests/test_imputation.py`로 래핑한다.

Notebooks 복원: EDA 과정 Jupyter 노트북을 `notebooks/`에 보존한다.

---

## 참조 파일 경로

| 역할 | 경로 |
|------|------|
| Closure risk 학습 | `models/closure_risk/train.py` |
| Closure risk 추론 | `models/closure_risk/predict.py` |
| Closure risk 데이터 | `models/closure_risk/data_prep.py` |
| Closure risk 평가 | `models/closure_risk/evaluate.py` |
| Stage1 industry prior | `models/closure_risk/stage1_industry_prior.py` |
| Closure risk 가중치 | `models/closure_risk/weights/metrics.json` |
| Living pop naive | `models/living_pop_forecast/predict_naive.py` |
| Emerging district | `models/emerging_district/data_prep.py` |
| Imputation 학습 | `validation/phase_a_seoul_10ind.py` |
| LOO 누출 감사 | `validation/audit_dong_avg_leak.py` |
| Pipeline 데이터셋 | `data/pipeline/build_training_dataset.py` |
| FastAPI 메인 | `backend/src/main.py` |
| Closure risk split 문서 | `docs/ml-models/evaluation/closure-risk-validation-fix.md` |
| Imputation 비교 | `docs/ml-models/imputation/sales-model-comparison.md` |
| Imputation SOTA | `docs/ml-models/imputation/sales-sota-comparison.md` |
| Imputation 전이학습 | `docs/ml-models/imputation/sales-step2-transfer-learning.md` |
| Living pop 비교 | `docs/ml-models/evaluation/living-pop-forecast-v2-vs-v3-report.md` |
| Living pop 일별 | `docs/ml-models/evaluation/living-pop-daily-evaluation-2026-04-29.md` |
| Customer revenue | `docs/ml-models/evaluation/customer-revenue-evaluation-2026-04-29.md` |
| Competition model | `docs/ml-models/competition/competition-model.md` |
| Model adoption | `docs/ml-models/model-adoption-roadmap.md` |
| Tests closure risk | `tests/test_closure_risk_split.py`, `tests/test_closure_risk_b3.py` |
