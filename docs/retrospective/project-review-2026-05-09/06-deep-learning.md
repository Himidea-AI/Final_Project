# 06. 딥러닝(여러 층으로 쌓은 신경망으로 복잡한 패턴을 학습하는 머신러닝 분야) 모델 리뷰 — 마포구 프랜차이즈 시뮬레이터

> 작성일: 2026-05-09
> 범위: DL(딥러닝) 예측/대체 모델 전용 — LLM(대형 언어 모델) 에이전트·ABM(에이전트 기반 시뮬레이션)·LGBM/CatBoost(트리 기반 머신러닝 모델) 제외

---

## 한 줄 진단

**TCN(Temporal Convolutional Network. 1D 합성곱으로 시계열을 처리. RNN 보다 안정적) 본격 운영 진입 (4 건 버그 수정 완료) + 시드(난수 초깃값. 고정해야 결과 재현 가능) 미고정 / 모델 lineage(어떤 데이터·설정으로 학습되었는지의 이력) 추적 부재 / 일부 폐기 모델 잔존 warmup(서버 시작 시 모델을 미리 메모리에 올려 첫 응답을 빠르게 만드는 절차).**

## 비전문가용 요약

- **무엇이 잘 됐나요?** TCN 결측 보간(빠진 값을 채워 넣는 작업) 모델이 본격 운영에 진입했고, 누수(leakage. 학습 단계에서 미래 정보가 새어 들어가 점수가 부풀려지는 현상) 4.4%p 정량화·notna(파이썬 pandas 의 "NaN(빈 값)이 아니다" 라는 뜻의 함수) 버그 수정 등 4 건의 결함이 반영됐습니다. 음수 결과를 명시적으로 문서화하는 문화도 강점.
- **무엇이 문제인가요?**
  - 학습할 때마다 결과가 달라집니다 (PyTorch(메타가 만든 딥러닝 프레임워크. 파이썬에서 텐서 연산·자동 미분 제공) 시드 미고정). 같은 입력으로 모델을 재학습해도 결과가 재현 안 됩니다.
  - 어떤 데이터·하이퍼파라미터(학습 전에 사람이 직접 정해 주는 설정값)로 학습된 모델인지 기록(metadata.json. 모델 학습 정보가 담긴 설정 파일)이 없어 운영 이슈 추적이 어렵습니다.
  - 폐기 결정된 customer revenue MLP(Multi-Layer Perceptron. 가장 기본적인 완전 연결 신경망(뉴런처럼 동작하는 노드를 층층이 쌓아 입력을 출력으로 변환하는 모델)) 가 startup warmup 에 잔존.
- **얼마나 위험한가요?** P1(우선순위 1단계, 즉시 처리). 운영에는 즉각적 위험 없으나 신뢰성·재현성 부채.
- **얼마나 걸리나요?** 시드 통일 0.5 일. metadata.json 발행 1 일. warmup 정리 0.5 일.

## 가장 시급한 3 가지

| # | 위치 | 문제 | 수정 |
|---|------|------|------|
| H-1 | `models/closure_risk/train.py` | PyTorch seed 미설정 | `torch.manual_seed`(CPU 난수 시드 고정) + `torch.cuda.manual_seed_all`(GPU 측 난수 시드 고정) |
| H-2 | `models/*/` | `metadata.json` 없음 → 모델 lineage 추적 불가 | 학습 스크립트에서 metadata.json 자동 발행 |
| H-3 | `backend/src/main.py` startup | 폐기된 customer revenue MLP warmup 잔존 | 해당 코드 제거 |

---

## 모델 지형도 — 어떤 DL 이 살아 있고 어떤 게 죽었나

이 프로젝트의 딥러닝은 출발할 때만 해도 LSTM(Long Short-Term Memory. 시계열 학습용 순환 신경망)·GRU(Gated Recurrent Unit. LSTM 보다 단순한 순환 신경망)·TCN 세 가지 분기 매출 모델, TCN 기반 결측 보간, 생활인구 일별 예측, 그리고 고객 매출 비율을 다루는 MLP 까지 다섯 갈래로 뻗어 있었습니다. 그러나 2026-05-09 시점에 살아남아 운영에 들어간 DL 은 **TCN 분기 매출 예측 단 한 가지** 입니다. 나머지는 실험으로 끝났거나 naive baseline(가장 단순한 예측 — 직전 주 같은 시간 값을 그대로 복사)·통계 규칙으로 대체됐습니다.

### 매출 분기 예측 (LSTM / GRU / TCN)

세 모델은 모두 동일한 입력 피처(모델에 넣는 변수) 31~34 개(SALES 12 + STORE 5 + POP 4 + RENT 2 + EXTRA 6 + GOLMOK 5)와 `window_size=4`(=1 년) (Window size / lookback. 과거 몇 시점을 입력으로 쓸지) 를 공유하며, log1p(로그 변환. 매출처럼 분포가 치우친 값에 사용) → MinMaxScaler(데이터를 0~1 사이로 스케일링) → np.expm1(로그를 되돌리는 지수 변환) 역변환 파이프라인(데이터 처리 단계의 흐름)을 똑같이 씁니다. 학습 데이터 누수를 막기 위해 `train_cutoff_quarter=20241`(2024년 1분기까지만 학습에 사용) 를 강제하고, COVID 분기(2020~2021) 에는 weighted MSE(가중 평균 제곱 오차. 특정 시점에 가중치를 다르게 부여) 의 가중치 0.5 를 부여해 영향력을 줄였습니다. 6-run(같은 학습을 여섯 번 반복) 평균 MAPE(평균 절대 백분율 오차. 낮을수록 좋음) 는 LSTM 10.66%, GRU 11.41%, TCN 11.52% 로 LSTM 이 살짝 앞서지만 차이가 1%p 안쪽이며, persona(기획에서 정한 모델 선택 기준 인격) 기반 우선순위(R²(설명력 지표. 1 에 가까울수록 좋음) > RMSE(평균 제곱근 오차. 낮을수록 좋음) > MAE(평균 절대 오차. 낮을수록 좋음) > MAPE)에서 TCN 이 R²=0.9925 로 1 위를 차지했기 때문에 **TCN 이 production(실제 운영 환경) 으로 채택**됐습니다. TCN 은 또한 시드 고정 3-run 의 표준편차가 0.11% 에 불과해 안정성 면에서도 가장 좋았습니다. LSTM 의 best val_loss(검증 손실. 학습 중 보지 못한 데이터에서 측정한 오차) 는 0.000336, GRU 는 0.000318, TCN 은 0.000287 이고 파라미터(학습으로 정해지는 모델 내부 숫자) 수는 각각 ~229K / ~168K / ~145K 로 TCN 이 가장 가벼운 것도 채택에 유리하게 작용했습니다.

### TCN imputation (TCN-A vs TCN-B-rebuild)

여기서 imputation(빠진 값을 추정해서 채우기) 은 결측 보간을 의미합니다. TCN-A 는 cutoff(학습에 쓸 데이터의 시간 경계선) 없이 학습해 모든 지표가 가장 좋아 보였지만(MAPE 10.9%, MAE 7.9 억 원, R² 0.9964), 학습 시점에 미래 분기를 본 **데이터 누수**가 있었습니다. 누수를 차단한 TCN-B-rebuild 는 MAPE 15.3%, MAE 9.8 억 원, R² 0.9957 로 다소 떨어지지만 운영 안전성 측면에서 옳은 선택이었고 결국 **TCN-B-rebuild 가 채택**됐습니다. 두 변형 사이의 MAPE 차이 4.4%p 가 곧 누수 패널티의 정량 측정값입니다. 기존 Hot Deck(비슷한 다른 행의 값을 가져와 빈 칸을 채우는 통계 기법) 방식의 MAPE 18.3% 와 비교하면 TCN-B 도 충분히 우수합니다.

### 생활인구 예측 — 7 라운드 끝에 Naive 로 후퇴

생활인구 일별 예측은 `TCNForecaster` 클래스를 그대로 재사용하되 입력을 5 차원에서 21 차원(dong_one_hot(동을 16 개 0/1 값으로 표현하는 인코딩) 16 차원 추가)으로 늘려 v2 를 만들었고, LODO(Leave-One-Domain-Out. 한 도메인을 제외하고 학습·평가) 16-fold(16 번 나누어 교차 검증) 평균이 0.01339 ± 0.01138 으로 양호했습니다. 다만 서조동 한 곳이 LODO 0.05091 로 전체 평균의 4 배에 달하는 이상치였습니다. 이후 v3 라운드 1~7 까지 일곱 번 변형을 시도했습니다. R1 sin/cos 시간 인코딩(시간을 사인·코사인 값으로 표현해 주기성을 알려 주는 기법)(MASE(평가 지표. 1 미만이면 baseline 보다 나음) 1.31), R2 외부 피처(1.18), R3 Transformer(자연어 모델 GPT 의 기반 구조. 시계열에도 적용 가능)(2.07), R4 LSTM 대체(1.22), R5 TCN+LSTM 앙상블(여러 모델의 예측을 합치는 기법)(1.19), R6 residual(잔차. 정답과 예측의 차이) 보정(0.89, split 결함), R7 time-sorted split(시간 순서대로 학습/평가 데이터를 나누는 방식) 재측정(MASE 1.042) 까지 모두 naive 를 넘지 못했습니다. 핵심 실패 원인은 sin/cos 인코딩이 강한 자기상관(어제 값이 오늘 값을 잘 설명하는 성질) 신호 위에 노이즈로 작용한 것, 그리고 `evaluate_all._split_indices` 의 group-order 분할(그룹 순서대로 잘라서 시간 정렬이 어긋나는 결함이 있는 분할) 결함이었습니다. 자세한 내용은 `docs/ml-models/evaluation/living-pop-forecast-v2-vs-v3-report.md:474` 에 정리되어 있습니다. 결론적으로 **production 모델은 `predict_naive.py` 의 naive_lag7**(7 일 전 같은 시간 값을 그대로 가져옴) 이며, Kendall tau(두 시계열 순위가 얼마나 일치하는지. 1 에 가까울수록 일치) 평균 0.9797(168 시간슬롯=1 주 168 시간 단위) 으로 단순한 직전 주 동시간 값 복사가 모든 DL 변형을 이깁니다.

### 폐기된 customer revenue MLP

고객 매출 비율을 예측하던 MLP 는 group_mean baseline(업종·동 단위 평균값을 그대로 사용하는 단순 비교 기준) 보다 MAE 가 0.0378 vs 0.0319 로 약 18% 더 나빴습니다. 16 개 차원 중 MASE<1.0 을 만족한 것이 age_20_ratio(20대 매출 비율) 단 1 개뿐이어서 **group_mean 으로 대체**됐고 MLP 코드는 보존만 한 채 비활성화됐습니다. 다만 backend startup warmup 에는 아직 이 모델 로딩 코드가 남아 있어 H-3 으로 정리 대상에 올라 있습니다.

---

## TCN 분기 예측이 production 까지 간 길

### 아키텍처가 단순하고 가볍다

TCN 의 핵심 블록은 `models/tcn_forecast/model.py:40` 의 `CausalConv1d`(Causal Conv. 미래 시점 정보를 보지 못하게 padding 만 왼쪽에 주는 합성곱(필터를 슬라이딩하며 특징을 추출)) 입니다. `F.pad(x, (self.padding, 0))` 으로 왼쪽 패딩(빈 값 채우기)만 주어 미래 시점이 과거를 오염시키지 않도록 설계됐고, 이는 시계열 모델에서 가장 흔한 누수 사고를 구조적으로 차단합니다. 그 위에 dilation(합성곱 필터에 간격을 두고 넓은 시야를 확보하는 트릭) 1·2 의 두 단계 TemporalBlock 이 LayerNorm(층 정규화. 학습을 안정화하는 기법) → ReLU(음수를 0 으로 만들고 양수는 통과시키는 비선형 함수) → Dropout(학습 중 일부 뉴런을 무작위로 끄는 정규화 기법) 을 끼고 residual connection(입력을 출력에 더해 깊은 네트워크에서 gradient(기울기) 소실을 막는 구조) 으로 더해진 뒤 1x1 conv → AdaptiveAvgPool1d(시계열 길이에 맞춰 평균을 자동 계산해 주는 풀링) → FC(Fully Connected. 모든 입력과 출력이 연결된 완전 연결층) 로 출력으로 빠집니다. 수용 필드(receptive field. 모델이 한 번에 보는 시간 범위)는 1 + (3-1) × (1+2) = 7 로 window_size=4 를 충분히 덮습니다. LSTM/GRU 보다 파라미터가 30~40% 적으면서도 best val_loss 가 가장 낮다는 점이 결정적이었습니다.

### 두 단계 전이학습이 소량 데이터 문제를 풀었다

전이학습(pretrain / finetune. 대규모 데이터로 사전 학습 후 작은 도메인 데이터로 미세 조정) 이란 큰 데이터로 먼저 일반적인 패턴을 익힌 모델을 작은 데이터에 맞게 다시 다듬는 방식입니다. 마포구 데이터만으로는 TCN 을 학습시키기에 양이 부족하기 때문에, 서울 전국 65 개 업종의 가맹점 데이터로 먼저 pretrain 한 뒤 마포 데이터로 finetune 합니다. finetune 은 다시 두 단계로 쪼개져 있는데, 첫 5 epoch(학습 데이터 전체를 한 번 도는 단위) 은 `freeze_tcn()`(freeze. 전이 학습 시 일부 층 가중치를 고정) 으로 backbone(모델의 핵심 본체)을 고정하고 FC head(맨 마지막 출력층) 만 lr=5e-4 (lr / learning rate. 학습 속도를 결정하는 하이퍼파라미터) 로 학습한 뒤, 그다음에 `unfreeze_tcn()`(unfreeze. 고정을 풀어 다시 학습 가능하게 만듦) 으로 풀어 lr=1e-4 로 전체 파라미터를 천천히 미세조정합니다. 관련 코드는 `models/tcn_forecast/model.py` 의 `freeze_tcn()` 과 `models/lstm_forecast/train.py:DEFAULT_FINETUNE_CONFIG` 에 들어 있습니다. 이 구조 덕분에 마포 표본이 적어도 catastrophic forgetting(기존에 배운 내용을 새 학습 중에 통째로 잊어버리는 현상) 없이 안정적으로 적응합니다.

### TDD(Test-Driven Development. 먼저 실패하는 테스트를 쓰고 코드를 거기에 맞춰 통과시키는 방식) 가 imputation 어댑터의 NaN 덮어쓰기 버그를 잡았다

TCN imputation 어댑터(서로 다른 시스템을 이어 주는 변환층) `models/tcn_forecast/impute.py:222` 에는 원래 NaN(Not a Number. 비어 있는 값) 이 아닌 base 값(원본에 실제 존재하는 값)까지 TCN 예측으로 덮어쓰는 결정적 버그가 있었습니다. 수정 전 코드는 `df[col + "_final"] = df[col + "_base"]` 후에 `df.loc[mask, col + "_final"] = tcn_predictions` 형태였는데, mask(어느 행에 적용할지를 표시하는 True/False 배열) 정의가 어긋나 base 가 살아 있어야 할 자리도 TCN 값으로 갈아치웠습니다. 수정 후에는 `df[col + "_final"] = df[col + "_tcn"]` 로 일단 TCN 값을 깔고, `df.loc[df[col + "_base"].notna(), col + "_final"] = df[col + "_base"]` 로 base 가 존재하는 행만 되돌리는 방식으로 바꿨습니다. 이 수정은 `test_sales_csv_override`(CSV 우선), `test_train_cutoff_quarter_spy`(cutoff 전달 검증), `test_notna_mask_correctness`(notna 보존 검증) 외 5 개의 엣지 케이스(드물지만 까다로운 경계 상황) 테스트를 RED → GREEN(실패하던 테스트가 통과로 바뀌는 TDD 용어) 으로 전환시키며 `docs/ml-models/imputation/tcn-imputed-comparison-test-cases.md:line 222` 에 기록됐습니다.

---

## 생활인구 라운드 7 실패와 naive_lag7 으로의 후퇴

### 무엇이 일곱 번이나 안 됐나

v3 의 일곱 라운드는 모두 `evaluate_all` 의 split(데이터를 학습·검증·테스트로 나누는 작업) 방식이 group-order 였다는 결함을 끌고 갔기 때문에 R6 처럼 MASE 0.89 가 나오는 듯한 착시가 있었습니다. 이를 time-sorted split 으로 바꿔 R7 에서 재측정한 결과가 1.042 로 떨어지면서 v3 의 모든 시도가 naive 를 이길 수 없다는 사실이 확정됐습니다. 근본 원인은 두 가지로 정리됩니다. 첫째, 생활인구는 요일·시간 주기성과 자기상관이 매우 강해서 직전 주 같은 시간대 값을 그대로 가져오는 단순 규칙(naive_lag7)이 이미 정답에 매우 가깝습니다. 둘째, sin/cos 시간 인코딩과 같은 추가 피처는 이 강한 자기상관 신호 위에 노이즈로 작용했습니다.

### 왜 중요한가

DL 을 무리하게 끼워 넣었다면 운영 비용과 학습 파이프라인 복잡도를 끌어안고도 정확도 손해를 보는 결과가 됐을 것입니다. 7 라운드 동안 실패를 정직하게 기록하고 마지막에 naive 로 후퇴한 것은 이 프로젝트의 모범적인 결정입니다.

### 어떻게 고치나

production 추론(학습이 끝난 모델로 새 데이터에 대해 예측을 만드는 단계)은 이미 `predict_naive.py` 로 전환됐습니다. 다만 `living_pop_forecast/evaluate_all.py:_split_indices` 의 group-order 코드는 아직 그대로 남아 있어 추후 다시 v4 변형을 평가할 때 같은 실수가 재발할 위험이 있습니다. M1(중간 위험 1번) 항목으로 분류하여 time-order 분할로 교체해야 합니다.

---

## 폐기된 고객 매출 MLP — backend warmup 잔존 정리 필요

### 왜 폐기됐나

MLP 는 16 개 비율 차원(연령대·성별·요일·시간대 등) 중 단 하나(age_20_ratio) 에서만 MASE<1.0(즉 baseline 보다 나음) 을 만족했습니다. 나머지 15 개 차원에서는 group_mean(=업종·동 단위 평균값을 그대로 사용) 보다도 못한 예측을 내놓았고, 전체 MAE 도 0.0378 로 baseline 의 0.0319 보다 약 18% 나빴습니다. 평가의 자세한 내용은 `docs/ml-models/evaluation/customer-revenue-evaluation-2026-04-29.md` 에 정리되어 있습니다.

### 왜 중요한가

DL 모델이 baseline 을 못 이긴다면 운영하는 의미가 없습니다. 코드 자체는 보존되어 있으나 추론 경로에서는 group_mean 으로 우회되어 사실상 dead code(실제로 실행되지 않는 죽은 코드) 입니다. 하지만 `backend/src/main.py` 의 startup 단계에서는 여전히 이 MLP 를 로딩하는 warmup 코드가 남아 있어 메모리·시작 시간을 잡아먹고 있고, 신규 작업자에게 혼란을 줍니다.

### 어떻게 고치나

H-3 항목으로 backend startup 의 customer revenue MLP warmup 호출을 제거하고, `models/customer_revenue/` 디렉토리 README 에 폐기 상태를 명시합니다.

---

## 코드 위치와 학습 진입점

학습·추론 코드는 모두 `models/` 디렉토리에 모델별 디렉토리로 분리되어 있습니다. `models/lstm_forecast/` 에는 `model.py`, `train.py`, `predict.py`(v6b 버그 수정), `data_prep.py` 가 있고, `models/gru_forecast/` 에는 `data_prep.py` 의 dtype(데이터 타입. int·float 등) 버그가 수정된 버전이 들어 있습니다. `models/tcn_forecast/` 의 `model.py` 에는 `CausalConv1d:40`, `TemporalBlock:106`, `TCNForecaster:199` 가 정의되어 있고 `train.py`, `predict.py`(4-step rollout. 4 단계 자기 회귀 예측), `impute.py`(notna 버그 수정) 가 함께 있습니다. `models/living_pop_forecast/` 는 `train.py` 가 `TCNForecaster` 를 재사용하지만 production 추론은 `predict_naive.py` 로 분리되어 있고, `models/customer_revenue/` 의 `model.py` 는 MLP 가 비활성화된 상태로 남아 있습니다.

`DEFAULT_PRETRAIN_CONFIG` 는 `window_size=4`, `hidden_size=64`(은닉층 차원), `num_channels=[64, 64]`(각 층의 채널 수), `kernel_size=3`(합성곱 필터 크기), `dilations=[1, 2]`, `dropout=0.2`, `lr=1e-3`, `patience=10`(검증 손실이 개선되지 않을 때 학습을 중단하기까지 기다리는 epoch 수), `batch_size=32`(한 번에 처리하는 샘플 묶음 크기) 로 고정되어 있고, `DEFAULT_FINETUNE_CONFIG` 는 `freeze_lr=5e-4`, `unfreeze_lr=1e-4`, `freeze_epochs=5` 입니다. dropout 은 0.2 로 고정되어 있고 튜닝 기록이 없다는 점이 M4 의 우려 사항입니다.

GRU 측에서 발견된 버그는 `gru_forecast/data_prep.py` 의 `_hot_deck()` 함수가 int64 컬럼에 float 값을 대입하면서 TypeError(타입 불일치 오류) 를 일으키던 것으로, `result[col] = result[col].astype(float)` 한 줄로 수정됐습니다. LSTM 의 `predict.py` v6b 는 window_size 와 hidden_size 가 학습 시점과 어긋나게 설정되어 있어 전체 재학습으로 해결됐습니다.

---

## 모델 아티팩트(학습 결과로 만들어진 산출물 파일들)와 lineage 부재

`models/**/artifacts/` 아래에 총 99 개의 `.pt` 파일(checkpoint / .pt 파일. PyTorch 의 학습된 모델 가중치 파일)이 누적되어 있습니다. `models/tcn_forecast/artifacts/` 에 약 35 개(pretrain + finetune 체크포인트), `models/lstm_forecast/artifacts/` 에 약 28 개(v6b 구버전 포함), `models/gru_forecast/artifacts/` 에 약 24 개, `models/living_pop_forecast/artifacts/` 에 약 12 개(v2, 미사용)가 들어 있습니다.

### 왜 중요한가

99 개 중 어떤 것이 production 인지, 어떤 데이터 cutoff 와 시드와 epoch 으로 학습됐는지는 **파일명만으로는 알 수 없습니다**. `metadata.json` 이 생성되지 않기 때문입니다. 운영 중 예측이 이상해졌을 때 어떤 체크포인트로 롤백(이전 안정 버전으로 되돌림)해야 하는지, 어떤 입력 분포 변화가 있었는지를 추적할 수 없습니다. 이는 H-2 로 등록된 가장 시급한 문제입니다.

### 어떻게 고치나

`train.py` 종료 시점에 `config`(window/hidden/dilations 등), `seed`, `epoch`, `best_val_loss`, `git_hash`(코드 커밋 식별자), 그리고 학습 데이터의 분기 범위·행 수를 담은 `metadata.json` 을 자동 발행하도록 만들어야 합니다. 추가로 `models/**/artifacts/README.md` 를 작성해 production 으로 지정된 파일과 폐기된 파일을 명시적으로 구분합니다. 중기적으로는 MLflow(머신러닝 실험·모델 버전 관리 도구) 또는 DVC(Data Version Control. 큰 모델·데이터 파일을 git 처럼 관리해 주는 도구) 도입을 검토합니다.

---

## 추론 로딩과 데이터 파이프라인

추론은 `model = TCNForecaster(**config)` 로 인스턴스(클래스를 실제로 생성한 객체)를 만든 뒤 state_dict(모델의 모든 가중치를 담은 딕셔너리) 를 로드하는 단순한 구조입니다. CPU 단일 추론 응답 시간은 모든 모델이 50ms(밀리초. 1ms = 1/1000 초) 미만이며, 마포 규모에서는 GPU(그래픽 처리 장치. 딥러닝 학습에 흔히 쓰임) 가 필요하지 않습니다. 다만 서울 전역으로 확장할 경우 Mixed Precision(AMP. Automatic Mixed Precision. 16비트와 32비트 부동소수점을 섞어 학습 속도를 높이는 기법) 미적용이 병목이 될 수 있어 L1(낮은 위험 1번) 로 등록되어 있습니다.

데이터 파이프라인은 매출 타겟에 대해 `log1p` 를 먼저 씌운 뒤 store(매장) 단위로 fit(scaler 가 데이터의 최소·최대값을 학습) 한 MinMaxScaler 를 적용합니다. 추론 결과는 `np.expm1` 로 역변환합니다. 손실(loss. 모델 예측이 정답에서 얼마나 떨어졌는지를 나타내는 값)은 `loss = (w_batch.unsqueeze(1) * (pred - y_batch) ** 2).mean()` 형태의 가중 MSE(Mean Squared Error. 평균 제곱 오차) 이며, 코로나 분기에 가중치 0.5 를 곱해 영향을 절반으로 줄입니다. 시간 순으로 train 80% / val 10% / test 10%(학습용·검증용·테스트용 분리) 분할이 적용되며, `train_cutoff_quarter=20241` 로 2024Q1 이후 분기는 학습에서 차단됩니다.

scaler 는 store 별로 fit 되어 디스크에 저장되는데 경로가 코드 내부에 하드코딩(코드 안에 직접 박아 넣은 고정 값)되어 있어 M3 으로 분류되어 있습니다. config 화(설정 파일로 분리)하여 환경별로 다른 경로를 쓸 수 있게 만들어야 합니다.

---

## 재현성 — 시드, lineage, 그리고 99 개 .pt 의 정체

### 왜 중요한가

같은 학습 스크립트를 같은 데이터로 다시 돌렸을 때 결과가 매번 다르게 나오면, 모델이 더 좋아진 건지 운이 좋았던 건지 구분할 수 없습니다. 새 모델을 평가할 때마다 6-run 평균이라는 무거운 절차를 거쳐야 했던 것도 이 때문입니다. 일부 학습 스크립트에는 `torch.manual_seed(42); np.random.seed(42)` 가 적용되어 있지만 (TCN 3-run std(표준편차) 0.11% 도 이렇게 측정한 값), `models/closure_risk/train.py` 등 일부 진입점은 PyTorch 시드 설정이 누락되어 있습니다. CUDA(엔비디아 GPU 에서 병렬 연산을 돌리는 플랫폼) 측의 `torch.cuda.manual_seed_all` 도 빠져 있어 GPU 학습 시 비결정성(같은 입력이라도 결과가 달라지는 성질)이 그대로 남습니다.

### 어떻게 고치나

H-1 로 학습 진입점마다 `torch.manual_seed`, `torch.cuda.manual_seed_all`, `np.random.seed`(NumPy 의 난수 시드), `random.seed`(파이썬 표준 라이브러리의 난수 시드) 를 함께 설정하는 헬퍼(공통으로 쓰는 작은 도구 함수)를 통일합니다. L2 의 `random.seed()` 누락도 같은 자리에서 함께 정리합니다. 그 위에 H-2 의 `metadata.json` 을 결합하면, 어떤 시드와 어떤 데이터 cutoff 로 어떤 .pt 가 만들어졌는지 한 번에 추적할 수 있습니다.

---

## 성능 지표 정리

LSTM 은 사전학습 42 epoch, best val_loss 0.000336, 6-run 평균 MAPE 10.66%, 파라미터 ~229K, 추론 응답 50ms 미만입니다. GRU 는 65 epoch, 0.000318, 11.41%, ~168K, 50ms 미만입니다. TCN 은 58 epoch, 0.000287, 11.52%, ~145K, 50ms 미만이며 R²=0.9925 로 persona 우선순위에서 1 위를 차지했습니다. TCN 의 시드 고정 3-run 표준편차 0.11% 는 안정성이 가장 높음을 정량적으로 입증합니다.

TCN imputation 의 누수 패널티는 4.4%p (TCN-A 10.9% → TCN-B-rebuild 15.3%) 로 측정됐고, 기존 Hot Deck 의 18.3% 보다는 여전히 3%p 좋습니다. 생활인구 production 인 naive_lag7 은 168 시간슬롯에서 Kendall tau 평균 0.9797 을 기록합니다. 고객 매출 차원에서는 group_mean MAE 0.0319 가 MLP 의 0.0378 을 18% 차이로 앞섭니다.

---

## 코드 품질과 남아 있는 빚

이미 해결된 항목으로는 `train_cutoff_quarter=20241` 적용으로 누수 차단이 들어간 것, GRU `_hot_deck` 의 int64 TypeError 수정, LSTM v6b 의 window/hidden 불일치 재학습, TCN impute 의 notna 마스크 수정 네 건이 있습니다. Early stopping(검증 성능이 더 좋아지지 않으면 학습을 일찍 멈추는 기법) 은 `copy.deepcopy(model.state_dict())`(모델 가중치를 깊은 복사로 안전하게 떠 두기) 로 best 체크포인트를 안전하게 복사한 뒤 복원하므로 구현 자체는 올바릅니다.

남아 있는 코드 품질 부채(기술 부채. 빠르게 처리하느라 미뤄 둔 정리 작업)는 다음과 같습니다. `living_pop_forecast/evaluate_all.py:_split_indices` 의 group-order 분할 코드가 아직 time-order 로 교체되지 않은 것이 M1 입니다. autoregressive(방금 만든 예측을 다음 단계 입력으로 다시 넣어 이어 예측하는 방식) 4-step rollout 의 단계별 오차 누적이 정량화되지 않은 것이 M2 입니다. scaler 경로 하드코딩이 M3, dropout=0.2 고정·튜닝 기록 부재가 M4, 서조동 LODO outlier(평균에서 크게 벗어난 이상치) 0.05091 의 원인 분석 부재가 M5 입니다. 신뢰구간(예측이 얼마나 흔들릴 수 있는지를 보여 주는 범위)을 선형 ±σ(표준편차) 로 근사하고 있어 이상치 분기에서 과소 추정될 위험이 있고(H2), 99 개 .pt 의 버전 관리 부재가 H3 입니다. 운영 환경에는 즉각적 영향이 없지만 신뢰성을 갉아먹는 요소들입니다.

---

## 강점 — 칭찬받을 만한 의사결정들

이 프로젝트의 DL 측 의사결정에는 모범적인 패턴이 여럿 있습니다. 첫째, **persona 기반 모델 선택 기준** 을 명문화하여 R² > RMSE > MAE > MAPE 우선순위로 평가했고, 그 덕에 MAPE 가 가장 낮은 LSTM 이 아닌 R² 가 가장 높은 TCN 을 production 으로 보내는 일관된 결정을 내렸습니다. 둘째, **2 단계 전이학습**(서울 pretrain → 마포 finetune)과 freeze/unfreeze 분리로 소량 데이터 문제를 구조적으로 풀었습니다. 셋째, **COVID 가중치 0.5** 로 비정상 분기를 학습에서 제거하지 않고 영향만 감쇠시킨 것은 도메인 이해가 반영된 선택입니다. 넷째, TCN imputation 어댑터에 **8 개 단위 테스트(unit test. 함수 하나의 동작을 좁게 검증하는 자동화 테스트)를 RED→GREEN 으로 문서화**한 TDD 가 적용됐습니다. 다섯째, TCN-A vs TCN-B-rebuild 비교로 **데이터 누수 패널티를 4.4%p 라는 숫자**로 정량화했습니다. 여섯째, 생활인구 v3 라운드 1~7 을 정직하게 실패로 기록하고 **naive baseline 으로 후퇴**한 것은 DL 만능주의(딥러닝이면 다 된다는 잘못된 믿음)를 거부한 좋은 사례입니다. 일곱째, **TCN 시드 안정성을 3-run std=0.11%** 로 수치화했습니다. 여덟째, `CausalConv1d` 에서 `F.pad(x, (self.padding, 0))` 으로 미래 누수를 구조적으로 차단했습니다.

---

## 리스크 정리 — HIGH / MEDIUM / LOW

### HIGH

**H1 — metadata.json 부재**. 학습 결과물의 lineage 가 추적되지 않아 운영 이슈 발생 시 롤백·재현이 어렵습니다. 해결은 학습 종료 시점에 config·seed·epoch·val_loss·git_hash 를 담은 `metadata.json` 을 자동 발행하는 것입니다.

**H2 — 신뢰구간 선형 근사**. 현재 ±σ 형태의 선형 근사는 이상치 분기에서 과소 추정될 위험이 있습니다. 해결은 conformal prediction(데이터 분포 가정 없이 확률적으로 보장된 신뢰구간을 만들어 주는 기법) 도입입니다.

**H3 — 99 개 .pt 의 버전 관리 부재**. production 과 구버전이 섞여 있어 잘못된 체크포인트가 로드될 위험이 잠재합니다. MLflow/DVC 또는 최소한 per-artifact README.md 가 필요합니다.

### MEDIUM

**M1** — `living_pop_forecast/evaluate_all.py:_split_indices` 의 group-order 분할 코드가 아직 time-order 로 교체되지 않았습니다. **M2** — autoregressive 4-step rollout 의 단계별 오차 누적이 정량화되지 않았습니다. **M3** — store 별 MinMaxScaler 경로가 코드 내부에 하드코딩되어 있어 환경 이전 시 깨질 수 있습니다. **M4** — dropout=0.2 가 고정값이며 튜닝 기록이 없습니다. **M5** — 서조동 LODO outlier 0.05091 의 원인 분석이 없습니다.

### LOW

**L1** — Mixed Precision(AMP) 미적용. 마포 규모에서는 영향이 없지만 서울 전역 확장 시 학습 시간이 병목이 될 수 있습니다. **L2** — 일부 학습 파일에서 `random.seed()` 가 누락되어 있습니다.

---

## 개선 우선순위

### P1 — 즉시 (이번 주)

1. 학습 종료 시점에 `metadata.json` 자동 생성(config / seed / epoch / val_loss / git_hash 포함). H-1, H-2 와 직접 연결됩니다.
2. `models/**/artifacts/README.md` 작성으로 production 체크포인트 명시.
3. `living_pop_forecast/evaluate_all.py:_split_indices` 를 time-order split 으로 교체.
4. `backend/src/main.py` startup 에서 폐기된 customer revenue MLP warmup 호출 제거(H-3).

### P2 — 다음 스프린트(개발 주기 한 단위. 보통 1~2 주)

5. 백테스트(과거 데이터로 모델을 시뮬레이션해 성능을 평가) 단계별 MAPE 분해(step 1~4 별도 측정)로 autoregressive 오차 누적 정량화(M2).
6. scaler 아티팩트 경로 config 화(M3).
7. 구버전 .pt 정리 및 `.gitignore`(git 추적에서 제외할 파일 목록) 점검(H3 부분 해소).

### P3 — 중기

8. conformal prediction 기반 신뢰구간 도입(H2 해소).
9. MLflow 또는 DVC 도입으로 99 개 .pt 의 lineage 를 자동 관리(H3 완전 해소).
10. AMP 도입 준비(L1).
11. 서조동 LODO outlier 0.05091 원인 분석(M5).

---

## 참조 문서

| 문서 | 위치 |
|------|------|
| GRU 모델 리포트 | `docs/ml-models/timeseries/gru-model-report.md` |
| TCN 모델 리포트 | `docs/ml-models/timeseries/tcn-model-report.md` |
| LSTM 모델 리포트 | `docs/ml-models/timeseries/lstm-model-report.md` |
| 3 모델 비교 리포트 | `docs/ml-models/timeseries/model-comparison-report.md` |
| TCN imputation 비교 | `docs/ml-models/imputation/tcn-imputed-comparison-report.md` |
| TCN imputation 테스트 | `docs/ml-models/imputation/tcn-imputed-comparison-test-cases.md` |
| 생활인구 v2 리포트 | `docs/ml-models/evaluation/living-pop-forecast-v2-report.md` |
| 생활인구 v2 vs v3 | `docs/ml-models/evaluation/living-pop-forecast-v2-vs-v3-report.md` |
| 고객 매출 평가 | `docs/ml-models/evaluation/customer-revenue-evaluation-2026-04-29.md` |
| 생활인구 일별 평가 | `docs/ml-models/evaluation/living-pop-daily-evaluation-2026-04-29.md` |
| TCN 소스 | `models/tcn_forecast/model.py` |

---

*이 문서는 2026-05-09 기준 코드베이스 및 실험 기록을 반영합니다.*
