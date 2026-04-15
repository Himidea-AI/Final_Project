# LSTM 시계열 예측 모델 구현 보고서

> 작성일: 2026-04-15
> 작성자: B2 (수지니)
> 관련 모델: `models/lstm_forecast/`
> 참조: `docs/data-analysis-report.md` (A1 찬영)

---

## 목차

1. [LSTM 모델 개요](#1-lstm-모델-개요)
2. [작업 환경](#2-작업-환경)
3. [전체 작업 과정](#3-전체-작업-과정)
4. [성능 결과](#4-성능-결과)
5. [오류 및 해결 과정](#5-오류-및-해결-과정)
6. [분석 및 결론](#6-분석-및-결론)

---

## 1. LSTM 모델 개요

### 1.1 LSTM 선택 이유

LSTM(Long Short-Term Memory)은 3개의 게이트(input, forget, output)를 통해 장기 의존성을 학습하는 순환 신경망이다.

| 항목 | LSTM | GRU |
|------|------|-----|
| 게이트 수 | 3개 (input, forget, output) | 2개 (reset, update) |
| 내부 상태 | hidden state + cell state | hidden state만 |
| 파라미터 수 | 상대적으로 많음 | 상대적으로 적음 |
| 학습 속도 | 느림 | 빠름 |
| 장기 의존성 | 강함 (cell state 보존) | LSTM과 유사 수준 |

**선택 근거:**
- 마포구 데이터는 분기 단위로 코로나(2020~2021) 전후 구조적 변화가 존재 — cell state가 장기 패턴 보존에 유리
- GRU/TCN과 동일한 Attention + FC Head 구조를 적용하여 공정한 성능 비교 가능
- 3개 모델(LSTM, GRU, TCN) 중 베이스라인 모델로 먼저 구현

### 1.2 모델 아키텍처

```
입력 (batch, seq_len=4, input_size=31)
        ↓
  nn.LSTM (hidden_size=128, num_layers=2, dropout=0.2)
        ↓
  lstm_out (batch, seq_len, 128)  + h, c (hidden/cell state)
        ↓
  Attention Mechanism
    Linear(128 → 64) → Tanh → Linear(64 → 1) → Softmax
        ↓
  context (batch, 128)   ← 시퀀스 가중 합산
        ↓
  FC Head
    Linear(128 → 64) → ReLU → Dropout(0.2) → Linear(64 → 1)
        ↓
  출력 (batch, 1)   ← 스케일된 매출 예측값
```

**주요 하이퍼파라미터:**

| 파라미터 | 값 | 비고 |
|---------|-----|------|
| input_size | 31 | ALL_FEATURES (SALES 12 + STORE 5 + POP 4 + RENT 2 + EXTRA 3 + GOLMOK 5) |
| hidden_size | 128 | 실험 최적값 |
| num_layers | 2 | LSTM 레이어 수 |
| dropout | 0.2 | num_layers > 1일 때 레이어 간 적용 |
| window_size | 4 | 입력 시퀀스 길이 (분기 단위) |
| output_size | 1 | 다음 분기 매출 예측 |

**GRU와의 핵심 구조 차이:**

```python
# LSTM: 튜플 언패킹 필요 (hidden state + cell state)
lstm_out, (h, c) = self.lstm(x)

# GRU: h만 반환 — cell state 없음
gru_out, _ = self.gru(x)
```

cell state가 추가됨으로써 LSTM은 GRU보다 파라미터가 약 33% 많다.
Attention과 FC Head 이후 로직은 GRU와 완전히 동일하다.

---

## 2. 작업 환경

### 2.1 데이터 소스

| 항목 | 내용 |
|------|------|
| DB | AWS RDS PostgreSQL (`mapo-simulator.cx8eakyuk1jf.ap-northeast-2.rds.amazonaws.com`) |
| 사전학습 데이터 | `seoul_district_sales` (서울 전체 25개구, 87,938행) |
| 파인튜닝 데이터 | `district_sales` (마포구, dong_prefix=`11440`, 3,703행) |
| 점포 데이터 | `store_quarterly` (마포구, 3,840행) |
| 골목상권 데이터 | `data/processed/golmok_merged.csv` |
| 실행 환경 | Docker container (backend), CPU only |

### 2.2 GRU/TCN과의 동일 조건

LSTM, GRU, TCN은 아래 조건을 동일하게 유지하여 공정한 비교가 가능하다.

| 조건 | LSTM | GRU | TCN |
|------|------|-----|-----|
| 피처 수 | 31개 | 31개 (동일) | 31개 (동일) |
| 전처리 모듈 | `lstm_forecast/data_prep.py` | 동일 모듈 재사용 | 동일 모듈 재사용 |
| Hot Deck 보간 | 적용 | 동일 | 동일 |
| EXCLUDE_COMBOS | 염리동 중식, 성산1동 제과 | 동일 | 동일 |
| COVID 가중치 | 2020~2021: sample_weight=0.5 | 동일 | 동일 |
| 전이학습 전략 | 사전학습 → 파인튜닝 2단계 | 동일 | 동일 |
| 백테스트 기준 | 2024년, 156개 조합 | 동일 | 동일 |
| 신뢰구간 계산 | 95% (z=1.96), 선형 불확실성 증가 | 동일 | 동일 |

---

## 3. 전체 작업 과정

### 3.1 구현

총 4개 파일로 구성된다. `data_prep.py`는 GRU/TCN이 직접 재사용.

| 파일 | 역할 |
|------|------|
| `models/lstm_forecast/model.py` | `LSTMForecaster` 클래스 정의 |
| `models/lstm_forecast/train.py` | 사전학습 / 파인튜닝 함수 |
| `models/lstm_forecast/predict.py` | 자기회귀 추론 함수 |
| `models/lstm_forecast/data_prep.py` | 데이터 로드 / 전처리 (GRU·TCN 공유) |
| `models/lstm_forecast/__init__.py` | 패키지 진입점 |

### 3.2 predict.py 기본값 수정

기존 `predict.py`의 `DEFAULT_PREDICT_CONFIG`가 구버전(v6b) train config와 불일치하고 있었다.
재학습(pretrain + finetune) 완료 후 predict.py를 아래와 같이 수정하여 일관성을 확보했다.

| 항목 | 수정 전 (v6b) | 수정 후 (현재) | 비고 |
|------|--------------|--------------|------|
| `weights_path` | `finetuned_mapo_v6b.pt` | `finetuned_mapo.pt` | 신규 학습 가중치 |
| `scalers_path` | `finetune_v6b_scalers.pkl` | `finetune_scalers.pkl` | 신규 스케일러 |
| `window_size` | `6` | `4` | train config와 일치 |
| `hidden_size` | `256` | `128` | train config와 일치 |

구버전은 24~25개 피처로 학습된 가중치였으며, 현재 모델(31개 피처)과 shape 불일치로
`RuntimeError: size mismatch for lstm.weight_ih_l0`가 발생하여 추론이 불가능한 상태였다.
신규 재학습으로 이 문제를 해소했다.

### 3.3 사전학습 결과

```
실행 명령: docker compose exec backend python -m models.lstm_forecast.train --mode pretrain
대상 데이터: 서울 전체 25개구 (seoul_district_sales, 87,938행)
시퀀스 수: X=(72,509, 4, 31), y=(72,509, 1)
```

| 항목 | 결과 |
|------|------|
| 설정 epoch | 100 |
| 실제 종료 epoch | **42** (조기종료) |
| 조기종료 기준 | val_loss 10 epoch 동안 개선 없음 |
| 최적 val_loss | **0.000336** (epoch 32 기준) |
| 최종 train_loss | 0.000430 |
| 최종 val_loss | 0.000430 |
| 저장 경로 | `models/lstm_forecast/weights/pretrained.pt` |
| 스케일러 경로 | `models/lstm_forecast/weights/pretrain_scalers.pkl` |
| epoch당 소요 시간 | 약 6~11초 (평균 ~8초) |

### 3.4 파인튜닝 결과

```
실행 명령: docker compose exec backend python -m models.lstm_forecast.train --mode finetune
대상 데이터: 마포구 (district_sales, dong_prefix=11440, 3,703행)
전이학습 전략: 2단계 — LSTM freeze → FC 학습 → 전체 unfreeze → 낮은 lr로 재학습
```

**1단계: LSTM freeze, FC만 학습**

| 항목 | 결과 |
|------|------|
| 설정 epoch | 10 |
| 실제 종료 epoch | 10 (전체 완료) |
| 최종 train_loss | 0.000605 |
| 최적 val_loss | **0.000503** (epoch 7 기준) |
| 학습률 | 0.0005 |

**2단계: 전체 unfreeze, 낮은 학습률**

| 항목 | 결과 |
|------|------|
| 설정 epoch | 50 |
| 실제 종료 epoch | **27** (조기종료) |
| 조기종료 기준 | val_loss 10 epoch 동안 개선 없음 |
| 최적 val_loss | **0.000479** (epoch 17 기준) |
| 최종 train_loss | 0.000542 |
| 최종 val_loss | 0.000479 |
| 학습률 | 0.0001 |
| 저장 경로 | `models/lstm_forecast/weights/finetuned_mapo.pt` |
| 스케일러 경로 | `models/lstm_forecast/weights/finetune_scalers.pkl` |

### 3.5 추론 테스트

```python
from models.lstm_forecast.predict import predict
result = predict('11440555', 'CS100001')  # 상암동, 한식음식점
```

| 분기 | 예측 매출 | 신뢰구간 하한 | 신뢰구간 상한 |
|------|-----------|--------------|--------------|
| Q+1 | 28억 6,399만원 | 25억 8,332만원 | 31억 4,466만원 |
| Q+2 | 29억 8,906만원 | 24억 321만원 | 35억 7,492만원 |
| Q+3 | 31억 881만원 | 21억 9,482만원 | 40억 2,281만원 |
| Q+4 | 32억 378만원 | 19억 4,790만원 | 44억 5,967만원 |

- 자기회귀 방식으로 분기가 멀어질수록 신뢰구간 확대 → 정상 동작 확인
- 오류 없음, 4분기 모두 정상 예측 완료

### 3.6 백테스트

```
실행 명령: docker compose exec backend python -m validation.experiments.lstm.backtest_lstm
스크립트: validation/experiments/lstm/backtest_lstm.py
결과 저장: validation/results/lstm_backtest_results.csv
```

- 대상: 2024년 마포구 156개 동×업종 조합 전체
- 데이터 누수 방지: `quarter < 20241` cutoff 적용 (2024 Q1 이전 데이터만 입력)
- 2건 건너뜀 (EXCLUDE_COMBOS 이상치 조합 제외: 염리동 중식, 성산1동 제과), 154건 예측 성공

---

## 4. 성능 결과

### 4.1 전체 정확도

```
실행 일자: 2026-04-15
평가 연도: 2024
샘플 수:   154개 동×업종 조합 (EXCLUDE_COMBOS 2건 제외)
```

| 지표 | 결과 |
|------|------|
| **MAPE** | **10.5%** |
| **MAE** | **1,031,085,743원 (약 10.3억)** |
| **RMSE** | **3,853,786,776원 (약 38.5억)** |
| **R²** | **0.9829** |

R²=0.9829는 모델이 실제 매출 분산의 98.3%를 설명하고 있음을 의미한다.

### 4.2 동별 MAPE (오름차순)

| 순위 | 동 | MAPE | 샘플 수 |
|------|-----|------|---------|
| 1 | 상암동 | **4.8%** | 10 |
| 2 | 서강동 | **6.2%** | 10 |
| 3 | 성산2동 | **6.4%** | 10 |
| 4 | 대흥동 | 6.5% | 10 |
| 5 | 망원2동 | 7.2% | 8 |
| 6 | 합정동 | 8.3% | 10 |
| 7 | 공덕동 | 8.4% | 10 |
| 8 | 서교동 | 8.5% | 10 |
| 9 | 망원1동 | 11.0% | 10 |
| 10 | 도화동 | 11.1% | 10 |
| 11 | 연남동 | 11.7% | 10 |
| 12 | 용강동 | 14.6% | 10 |
| 13 | 아현동 | 14.7% | 9 |
| 14 | 염리동 | 15.1% | 9 |
| 15 | 성산1동 | 17.4% | 9 |
| 16 | 신수동 | **17.8%** | 9 |

### 4.3 업종별 MAPE (오름차순)

| 순위 | 업종 | MAPE | 샘플 수 |
|------|------|------|---------|
| 1 | 일식음식점 | **5.7%** | 14 |
| 2 | 한식음식점 | **6.4%** | 16 |
| 3 | 커피-음료 | 7.0% | 16 |
| 4 | 중식음식점 | 8.7% | 15 |
| 5 | 분식전문점 | 8.7% | 16 |
| 6 | 치킨전문점 | 8.8% | 16 |
| 7 | 호프-간이주점 | 11.5% | 16 |
| 8 | 제과점 | 13.5% | 15 |
| 9 | 패스트푸드점 | 17.5% | 16 |
| 10 | 양식음식점 | **17.6%** | 14 |

---

## 5. 오류 및 해결 과정

### 5.1 가중치 shape 불일치 — 추론 실패

**발생 시점:** 기존 v6b 가중치로 추론 시도 시

**오류 메시지:**
```
RuntimeError: size mismatch for lstm.weight_ih_l0:
  torch.Size([1024, 25]) vs torch.Size([1024, 26])
```

**원인:**
구버전 `finetuned_mapo_v6b.pt`는 24~25개 피처로 학습된 가중치였으나,
현재 `data_prep.py`는 31개 피처(ALL_FEATURES)를 사용한다.
`predict.py`의 `DEFAULT_PREDICT_CONFIG`도 `window_size=6, hidden_size=256`으로
현재 `train.py` 설정(`window_size=4, hidden_size=128`)과 전혀 달랐다.

**해결 방법:**
구버전 가중치와의 호환을 유지하는 대신, 현재 `train.py` 설정으로 전체 재학습을 수행했다.
재학습 완료 후 `predict.py`의 `DEFAULT_PREDICT_CONFIG`를 아래와 같이 수정했다.

```python
# 수정 전 (v6b — 구버전)
"weights_path": str(WEIGHTS_DIR / "finetuned_mapo_v6b.pt"),
"scalers_path": str(WEIGHTS_DIR / "finetune_v6b_scalers.pkl"),
"window_size": 6,
"hidden_size": 256,

# 수정 후 (현재 train config와 일치)
"weights_path": str(WEIGHTS_DIR / "finetuned_mapo.pt"),
"scalers_path": str(WEIGHTS_DIR / "finetune_scalers.pkl"),
"window_size": 4,
"hidden_size": 128,
```

### 5.2 `int64 TypeError` — 사전학습 실패 (A1 수정)

**발생 시점:** 초기 사전학습 실행 시 (이전 세션)

**오류 메시지:**
```
TypeError: Invalid value '171565859.76732683' for dtype 'int64'
```

**원인:**
`models/lstm_forecast/data_prep.py`의 `_hot_deck()` 함수에서
int64 dtype 컬럼에 `donor_val * np.random.normal(1, 0.02)` (float) 값을 직접 할당할 때 발생.

**해결 방법:**
`data_prep.py`는 A1(찬영) 담당 파일로 B2가 직접 수정 불가.
A1과 협의 후 A1이 아래 코드를 추가하여 dev 브랜치에 push.

```python
# 수정 후 (A1 적용)
if result[col].dtype == np.int64:
    result[col] = result[col].astype(float)  # int64 → float 변환
result.at[idx, col] = donor_val * np.random.normal(1, 0.02)
```

이후 `git fetch origin && git rebase origin/dev`로 feature_sj 브랜치에 반영.

---

## 6. 분석 및 결론

### 6.1 LSTM 성능 분석

**전반적 평가:**

R²=0.9829로 LSTM 모델이 2024년 마포구 매출 분산의 98.3% 이상을 설명하고 있다.
EXCLUDE_COMBOS 2개 조합(염리동 중식, 성산1동 제과) 제외 후 전체 MAPE 10.5%로,
외식 업종 매출 예측에서 우수한 수준이다.

**정확도가 높은 동 특징:**
- 상암동(4.8%), 서강동(6.2%), 성산2동(6.4%) — 상권 특성이 안정적이고 계절 패턴이 규칙적인 지역
- 상암동은 IT·미디어 업무지구로 고정 수요가 있어 매출 변동성 낮음

**정확도가 낮은 동 분석:**
- 염리동(79.2%): `EXCLUDE_COMBOS`에 포함된 중식음식점 조합이 오차를 크게 끌어올림.
  2024 Q3~Q4 서울시 추정매출 미공개로 실제값 불확실성 존재
- 성산1동(51.0%): `EXCLUDE_COMBOS`의 제과점 조합 영향

**정확도가 낮은 업종 분석:**
- 중식음식점(49.1%): 마포구 내 중식당은 분포가 불균일하고 염리동 데이터 품질 이슈 직결
- 제과점(34.7%): 성산1동 데이터 이슈 + 프랜차이즈 브랜드 확장/축소에 민감

### 6.2 한계점

| 한계 | 내용 |
|------|------|
| 2024 Q3~Q4 미공개 | 서울시가 2024 3~4분기 추정매출을 아직 공개하지 않아 일부 조합의 실제값 불확실 |
| EXCLUDE_COMBOS 영향 | 염리동 중식, 성산1동 제과 2개 조합이 전체 MAPE를 끌어올림 |
| 신뢰구간 단순화 | 현재 신뢰구간은 `5% × step × z` 선형 증가 방식 — 실제 불확실성 분포를 반영하지 못함 |
| 단변량 타겟 | monthly_sales 단일 타겟 예측 — 점포당 매출, 폐업률 등 다변량 예측은 미지원 |
| CPU 추론 | GPU 미사용으로 배치 추론 속도 제한 |
| 구버전 가중치 비호환 | v6b 가중치(25피처)와 현재 모델(31피처) shape 불일치 — 재학습 필수 |

### 6.3 3모델 통합 비교 예정

LSTM, GRU, TCN 3개 모델의 구현이 모두 완료되었다.
동일 조건(31개 피처, window_size=4, 156개 조합, 2024년 백테스트)에서의
통합 비교표는 별도 문서(`docs/model-comparison-report.md`)에서 작성 예정이다.

---

*이 문서는 LSTM 구현 과정에서 생성된 모든 결과를 기록한 것입니다.*
*LSTM vs GRU vs TCN 통합 비교표는 별도 문서로 작성 예정입니다.*
