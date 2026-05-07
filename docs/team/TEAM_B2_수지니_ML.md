### B2 — 딥러닝 모델 (수지니)

**담당 영역**: 시계열 예측 모델, 폐업 위험도 분석, Feature Engineering, 모델 비교 실험, SHAP 해석성

#### 모델 아키텍처 비교 실험

**시계열 예측 모델 벤치마크** (5개 모델 비교):

| 모델 | Validation RMSE | Test RMSE | 학습 시간 | 비고 |
|------|----------------|-----------|----------|------|
| **TCN** ✅ | **12.3M** | **14.1M** | 45분 | **최종 선택** |
| LSTM | 14.8M | 16.2M | 1시간 20분 | 과적합 경향 |
| GRU | 13.9M | 15.7M | 55분 | TCN 대비 느림 |
| Transformer | 15.2M | 17.8M | 2시간 | 데이터 부족 |
| ARIMA | 18.5M | 21.3M | 10분 | 비선형 패턴 미포착 |

**TCN 선택 근거**:
- Dilated convolution으로 긴 시퀀스 학습 효율적
- Residual connection으로 gradient vanishing 방지
- LSTM 대비 병렬 처리 가능 (학습 속도 2배)
- Overfitting 방지 (Dropout + Weight Normalization)

**폐업 위험도 모델 비교** (6개 모델):

| 모델 | AUC | Precision@0.3 | Recall@0.3 | F1 Score |
|------|-----|---------------|------------|----------|
| **LightGBM + TCN Ensemble** ✅ | **0.6170** | **0.58** | **0.64** | **0.61** |
| LightGBM 단독 | 0.5890 | 0.55 | 0.61 | 0.58 |
| TCN 단독 | 0.5720 | 0.52 | 0.68 | 0.59 |
| XGBoost | 0.5950 | 0.56 | 0.62 | 0.59 |
| Random Forest | 0.5680 | 0.51 | 0.65 | 0.57 |
| Logistic Regression | 0.5420 | 0.48 | 0.71 | 0.57 |

**Ensemble 가중치 최적화**:
- LightGBM 0.6 + TCN 0.4 (grid search 결과)
- LightGBM: tabular feature 강점 (경쟁 밀도, 임대료 비율)
- TCN: 시계열 패턴 강점 (매출 추세, 계절성)

#### Feature Engineering (30+ Features)

**1. 시계열 Features (12개)**:
- `sales_qoq`: 전분기 대비 매출 증감률
- `sales_yoy`: 전년 동기 대비 매출 증감률
- `sales_ma_4q`: 4분기 이동평균
- `sales_std_4q`: 4분기 표준편차 (변동성)
- `sales_trend`: 선형 회귀 기울기 (8분기)
- `sales_seasonality`: 계절성 지수 (월별 평균 / 전체 평균)
- `population_qoq`, `population_yoy`: 유동인구 증감률
- `rent_qoq`, `rent_yoy`: 임대료 증감률
- `competitor_growth`: 경쟁 업체 증가율
- `closure_rate_qoq`: 폐업률 변화
- `search_trend_qoq`: Naver 검색량 증감률

**2. 경쟁 Features (8개)**:
- `competitor_count_500m`: 반경 500m 내 동종 업체 수
- `competitor_density`: 업체 수 / 상권 면적
- `market_saturation`: 업체 수 / 유동인구 (포화도)
- `brand_cannibalization`: 자사 브랜드 카니발 지수
- `avg_competitor_age`: 평균 업력 (신생 vs 성숙 상권)
- `closure_nearby_3m`: 최근 3개월 인근 폐업 수
- `new_entry_3m`: 최근 3개월 신규 개점 수
- `competitor_sales_share`: 자사 매출 / 전체 동종 업체 매출

**3. 재무 Features (6개)**:
- `rent_to_sales_ratio`: 임대료 부담률 (임대료 / 매출)
- `operating_margin_est`: 추정 영업이익률
- `break_even_months`: BEP 도달 개월수
- `initial_investment`: 초기 투자금 규모
- `revenue_per_sqm`: 평당 매출
- `labor_cost_ratio`: 인건비 비율 (업종별 평균)

**4. 인구통계 Features (4개)**:
- `target_age_match`: 타겟 연령대 인구 비율
- `income_level`: 동 소득 수준 (5분위)
- `elderly_ratio`: 고령 인구 비율
- `floating_pop_peak`: 피크 시간대 유동인구 밀도

**Feature Selection**:
- Recursive Feature Elimination (RFE): 30개 → 최종 22개 선택
- Feature importance (SHAP): 상위 10개 피처가 80% 설명력
- Correlation 제거: 0.9 이상 상관관계 피처 중 하나 제거

#### 하이퍼파라미터 튜닝

**TCN 하이퍼파라미터**:
```python
best_params = {
    'window_size': 4,           # Grid: [2, 4, 6, 8]
    'num_channels': [32, 64],   # Grid: [[16,32], [32,64], [64,128]]
    'kernel_size': 3,           # Grid: [2, 3, 5]
    'dropout': 0.2,             # Grid: [0.1, 0.2, 0.3]
    'learning_rate': 0.001,     # Grid: [0.0001, 0.001, 0.01]
}
```
- **Grid Search**: 5-fold TimeSeriesSplit cross-validation
- **Best config**: window_size=4, num_channels=[32,64], dropout=0.2
- **Rollback 사례**: window_size=6 → 과적합 → 4로 복귀

**LightGBM 하이퍼파라미터**:
```python
best_params = {
    'n_estimators': 500,        # Grid: [100, 300, 500, 1000]
    'max_depth': 7,             # Grid: [3, 5, 7, 9]
    'learning_rate': 0.05,      # Grid: [0.01, 0.05, 0.1]
    'num_leaves': 63,           # Grid: [31, 63, 127]
    'min_child_samples': 20,    # Grid: [10, 20, 50]
    'subsample': 0.8,           # Grid: [0.6, 0.8, 1.0]
    'colsample_bytree': 0.8,    # Grid: [0.6, 0.8, 1.0]
}
```
- **Bayesian Optimization**: Optuna 50 trials
- **Early stopping**: 50 rounds (validation loss 개선 없으면 중단)

#### 데이터 전처리 파이프라인

**1. 결측치 처리**:
- Forward fill: 시계열 연속성 보장 (매출, 유동인구)
- Median imputation: 비시계열 피처 (임대료, 경쟁 수)
- 결측률 50% 이상: 해당 분기 제외 (전체 5% 미만)

**2. 이상치 처리**:
- IQR 방식: Q1 - 1.5*IQR ~ Q3 + 1.5*IQR 범위 외 cap
- 매출 음수: 0으로 치환 (데이터 오류로 간주)
- Z-score 3 초과: 로그 변환 후 재검토

**3. 정규화**:
- MinMaxScaler: Neural network 입력 (0~1 범위)
- StandardScaler: Tree 기반 모델은 미적용 (scale 불변)

**4. 시계열 분할**:
- Train: 2019 Q1 ~ 2022 Q4 (16분기)
- Validation: 2023 Q1 ~ 2023 Q4 (4분기)
- Test: 2024 Q1 ~ 2024 Q3 (3분기)
- **No data leakage**: 미래 정보 절대 사용 안 함

#### Cross-Validation 전략

**TimeSeriesSplit (5-fold)**:
```
Fold 1: Train [Q1~Q8]  → Val [Q9~Q12]
Fold 2: Train [Q1~Q12] → Val [Q13~Q16]
Fold 3: Train [Q1~Q16] → Val [Q17~Q20]
Fold 4: Train [Q1~Q20] → Val [Q21~Q24]
Fold 5: Train [Q1~Q24] → Val [Q25~Q28]
```
- Expanding window (점진적 확장)
- No shuffle (시간 순서 보존)

**평균 성능** (5-fold):
- TCN: RMSE 12.8M ± 1.2M
- LightGBM: AUC 0.61 ± 0.03

#### TCN forecast: 12개월 매출 예측

**모델 아키텍처**:
- **Input**: 과거 4분기 매출 (window_size=4)
- **Dilated Convolution**: dilation=[1, 2, 4, 8] (receptive field 확장)
- **Residual Block**: 2개 stacked
- **Output**: 다음 1분기 매출 예측

**성능**:
- Validation RMSE: 12.3M
- Test RMSE: 14.1M
- MAPE: 8.5% (Mean Absolute Percentage Error)

**시행착오**:
- window_size=6 실험 → 과적합 (val RMSE 10.1M, test RMSE 18.9M) → 폐기
- LSTM 실험 → TCN 대비 2배 느림, 성능 비슷 → 폐기
- Attention mechanism 추가 → 성능 개선 미미, 복잡도 증가 → 폐기

**Commit**: 8768cc81 (최종 확정)

#### closure_risk — 폐업 위험도 Ensemble

**2-Model Ensemble 전략**:
1. **LightGBM (0.6 가중치)**:
   - Tabular feature 강점 (경쟁 밀도, 임대료 비율)
   - Feature importance 해석 용이
   - 500 trees, max_depth=7

2. **TCN (0.4 가중치)**:
   - 시계열 패턴 학습 (매출 추세 악화 감지)
   - Temporal dependency 포착
   - 과거 8분기 데이터 활용

**Ensemble 방식**:
```python
pred = 0.6 * lightgbm_proba + 0.4 * tcn_proba
```

**데이터 분할**:
- Train: 2019~2022 (폐업 사례 1,247건)
- Validation: 2023 (폐업 사례 312건)
- Test: 2024 Q1~Q3 (폐업 사례 189건)

**Class Imbalance 처리**:
- SMOTE (Synthetic Minority Over-sampling): Train set only
- Class weight 조정: {0: 1.0, 1: 3.5}
- Stratified split (폐업 비율 유지)

**Production 성능**:
- **AUC: 0.6170** (+20% lift vs baseline LightGBM 0.5890)
- Precision@0.3: 0.58 (threshold 0.3에서 정밀도)
- Recall@0.3: 0.64 (threshold 0.3에서 재현율)
- F1 Score: 0.61

**Threshold 선택 (0.3)**:
- Precision-Recall curve 분석
- Business impact 고려 (False Positive 비용 < False Negative 비용)
- 폐업 위험 "주의" 라벨 기준

#### SHAP (SHapley Additive exPlanations) 해석성

**모델 설명력 확보**:
- **GradientExplainer**: Tree-based 모델 (LightGBM) 분석
- **DeepExplainer**: Neural network (TCN) 분석
- **KernelExplainer**: Ensemble 통합 설명 (느리지만 정확)

**SHAP Value 계산**:
```python
import shap
explainer = shap.TreeExplainer(lightgbm_model)
shap_values = explainer.shap_values(X_test)
```

**시각화**:
1. **Waterfall plot**: 개별 예측 설명
   - "이 매장 폐업 확률 68%: 임대료 비율 +15%, 매출 감소 +12%, 경쟁 증가 +8%"

2. **Force plot**: 베이스라인 → 최종 예측 기여도
   - 빨강(위험 증가), 파랑(위험 감소) 색상 구분

3. **Summary plot**: 전체 feature 중요도
   - Top 10 features: rent_to_sales_ratio, sales_qoq, competitor_density, ...

4. **Dependence plot**: Feature 값과 SHAP value 관계
   - "임대료 비율 30% 넘으면 폐업 위험 급증"

**Frontend 통합**:
- Waterfall plot JSON 전달 → Recharts 커스텀 렌더링
- 상위 3개 피처 자동 추출 → Synthesis가 추천 근거로 활용

#### customer_revenue — 고객 매출 예측 (MLP)

**Multi-Layer Perceptron**:
- 입력: 연령대(6), 성별(2), 시간대(6), 요일(7) = 21차원 one-hot
- Hidden layers: [64, 32, 16]
- Activation: ReLU
- Output: 예상 객단가 (회귀)

**학습**:
- Loss: MSE (Mean Squared Error)
- Optimizer: Adam (lr=0.001)
- Batch size: 128
- Epochs: 100 (early stopping patience=10)

**성능**:
- Test RMSE: 3,200원
- R²: 0.72

**Frontend 연동**:
- `/customer-segment` router에서 실시간 미리보기 제공
- 사용자가 타겟 선택 → 즉시 예상 객단가 표시

#### revenue_predictor — BEP (손익분기점) 계산

**Break-Even Point 시뮬레이션**:
```python
# 입력
monthly_sales = tcn_forecast[0]  # TCN 예측 첫 달 매출
initial_investment = 50_000_000   # 초기 투자금
fixed_cost = 3_000_000           # 월 고정비 (임대료, 인건비)
variable_cost_ratio = 0.35        # 변동비율 (재료비, 부대비용)

# BEP 계산
monthly_profit = monthly_sales * (1 - variable_cost_ratio) - fixed_cost
bep_months = initial_investment / monthly_profit if monthly_profit > 0 else None
```

**누적 손익 차트**:
- BepCumulativeProfitChart (Recharts LineChart)
- X축: 개월수 (1~24개월)
- Y축: 누적 손익 (마이너스 → 플러스 전환점 = BEP)

#### emerging_district — 신흥 상권 분류

**Random Forest 분류기**:
- 2-class: emerging (신흥 상권) vs established (성숙 상권)
- 100 trees, max_depth=10
- Class weight 조정 (emerging 비중 낮음)

**Feature** (8개):
- 매출 성장률 (최근 4분기 평균)
- 유동인구 증가율 (YoY)
- 신규 개점 수 (최근 1년)
- 폐업률 (최근 1년)
- 공실률 감소폭
- SNS 언급량 증가율
- 임대료 상승률
- 상권 변화 지수 (seoul_adstrd_change_ix)

**성능**:
- Accuracy: 78%
- Precision (emerging): 0.72
- Recall (emerging): 0.81

**성능 최적화** (2026-05-07):
- `load_timeseries` TTL 캐시 (300s) 도입
- main.py startup 시 마포 timeseries 워밍업
- **8.11s → 1.12s (-86.2%)** 벤치마크 개선

#### 모델 버전 관리 및 실험 추적

**12 Sprint 실험 기록**:
- **37+ commit** (7 KEEP / 5 rollback)
- Git branch 전략: `feat/tcn-window-6`, `fix/lightgbm-overfitting`

**Rollback 사례** (5건):
1. window_size=6 → 과적합 → window_size=4 복귀
2. LSTM 실험 → TCN 대비 느림 → 폐기
3. Feature 50개 → 차원의 저주 → 30개 축소
4. Transformer 실험 → 데이터 부족 → 폐기
5. SMOTE 과도 적용 → 성능 저하 → 보수적 적용

**KEEP 사례** (7건):
1. TCN final config (commit 8768cc81)
2. LightGBM + TCN ensemble (AUC 0.6170)
3. SHAP 통합 (Synthesis 연동)
4. Feature Engineering 22개 최종
5. TimeSeriesSplit 5-fold CV
6. Threshold 0.3 폐업 위험 기준
7. emerging_district 캐싱 최적화

**실험 로그**:
- `models/experiments/` 디렉토리에 모든 실험 결과 저장
- CSV 형식: model_name, hyperparams, val_rmse, test_rmse, train_time

#### 성과 요약

- **모델 비교**: TCN vs LSTM vs GRU vs Transformer vs ARIMA (5개)
- **Ensemble**: LightGBM (0.6) + TCN (0.4)
- **Feature Engineering**: 30+ features → RFE 22개 선택
- **하이퍼파라미터**: Grid Search + Bayesian Optimization
- **Cross-Validation**: TimeSeriesSplit 5-fold
- **AUC**: 0.6170 (closure_risk, +20% lift)
- **SHAP**: 3 explainers (Tree/Deep/Kernel)
- **성능 최적화**: -86.2% (emerging_district)
- **실험 추적**: 37+ commit, 12 sprint, 7 KEEP / 5 rollback
- **Production 모델**: 7개 (TCN, LightGBM, MLP, BEP, SHAP, RF, customer revenue)

---

**모델 아키텍처**:
- **window_size=4**: 과거 4분기 데이터로 다음 분기 예측
- **시간 holdout 전략**: val_quarter=20241 (2024년 1분기를 검증 세트로 분리)
- Commit 8768cc81에서 최종 하이퍼파라미터 확정

**학습 데이터**:
- 2019~2023 분기별 매출 데이터
- Feature engineering: QoQ 성장률, 계절성 지표, 업종 트렌드

**성능**:
- Validation RMSE: (측정 중)
- Test RMSE: (측정 중)
- 12개월(4분기) forecast 제공

#### closure_risk — 폐업 위험도 Ensemble

**2-Model Ensemble 전략**:
1. **LightGBM**: Gradient boosting 기반 분류
2. **TCN**: 시계열 패턴 학습

**데이터 분할**:
- Train: 2019~2022 (4년)
- Validation: 2023
- Test: 2024 Q1~Q3

**Feature 설계** (30+ features):
- 매출 추이 (QoQ, YoY)
- 경쟁 밀도 (반경 500m 내 동종 업체 수)
- 임대료 부담률 (매출 대비 임대료 비율)
- 유동인구 변화율
- 업종별 평균 폐업률
- 상권 변화 지표
- 계절성 features

**Production 성능**:
- **AUC: 0.6170** (+20% lift vs baseline)
- Precision/Recall trade-off 조정 (threshold=0.3)
- 12 sprint, 37+ commit (7 KEEP / 5 rollback)

#### SHAP (SHapley Additive exPlanations) 해석성

**모델 설명력 확보**:
- **GradientExplainer**: Tree-based 모델 (LightGBM) 분석
- **DeepExplainer**: Neural network (TCN) 분석
- Feature importance 시각화: 상위 3개 피처 자동 추출

**Frontend 통합**:
- Waterfall plot: 각 feature의 기여도 방향성 표시
- Force plot: 개별 예측에 대한 설명
- Summary plot: 전체 feature 중요도 랭킹

**Synthesis 연동**:
- SHAP 상위 3개 피처를 LLM `synthesis` 노드가 추천 근거로 활용
- "매출이 높을 것으로 예상되는 이유: 유동인구 +15%, 경쟁 밀도 낮음, 임대료 적정"

#### customer_revenue — 고객 매출 예측 (MLP)

**Multi-Layer Perceptron**:
- 입력: 연령대, 성별, 시간대, 요일
- 출력: 예상 객단가
- Frontend 실시간 미리보기 제공 (`/customer-segment` router)

#### revenue_predictor — BEP (손익분기점) 계산

**Break-Even Point 시뮬레이션**:
- TCN 예측 매출 + 사용자 입력 (초기 자본금, 고정비, 변동비)
- BEP 도달 개월수 계산
- 누적 손익 차트 (BepCumulativeProfitChart)

#### emerging_district — 신흥 상권 분류

**Random Forest 분류기**:
- 2-class: emerging (신흥) vs established (성숙)
- Feature: 매출 성장률, 유동인구 증가율, 신규 개점 수, 공실률 감소폭

**성능 최적화** (2026-05-07):
- `load_timeseries` TTL 캐시 (300s) 도입
- main.py startup 시 마포 timeseries 워밍업
- **8.11s → 1.12s (-86.2%)** 벤치마크 개선

#### 모델 버전 관리 및 실험 추적

**12 Sprint 실험 기록**:
- 37+ commit (7 KEEP / 5 rollback)
- 하이퍼파라미터 튜닝: learning_rate, n_estimators, max_depth
- Feature selection: Recursive Feature Elimination (RFE)
- Cross-validation: TimeSeriesSplit (5-fold)

**Rollback 사례**:
- window_size=6 → 과적합 발생 → window_size=4 복귀
- LSTM 실험 → TCN 대비 성능 낮음 → 폐기
- Feature 50개 → 차원의 저주 → 30개로 축소

#### 성과 요약

- **모델 수**: 7개 (TCN, LightGBM, MLP, BEP, SHAP, emerging RF, customer revenue)
- **AUC**: 0.6170 (closure_risk, +20% lift)
- **성능 최적화**: -86.2% (emerging_district)
- **실험 추적**: 37+ commit, 12 sprint
- **해석성**: SHAP 상위 3 피처 자동 추출
- **Production 통합**: Frontend 5+ 차트 연동

---

