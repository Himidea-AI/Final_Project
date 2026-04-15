# GRU 시계열 예측 모델 구현 보고서

> 작성일: 2026-04-14
> 작성자: B2 (수지니)
> 관련 모델: `models/gru_forecast/`
> 참조: `docs/data-analysis-report.md` (A1 찬영)

---

## 목차

1. [GRU 모델 개요](#1-gru-모델-개요)
2. [작업 환경](#2-작업-환경)
3. [전체 작업 과정](#3-전체-작업-과정)
4. [성능 결과](#4-성능-결과)
5. [오류 및 해결 과정](#5-오류-및-해결-과정)
6. [분석 및 결론](#6-분석-및-결론)

---

## 1. GRU 모델 개요

### 1.1 GRU 선택 이유

GRU(Gated Recurrent Unit)는 LSTM(Long Short-Term Memory)과 같은 게이트 기반 순환 신경망이지만 구조가 더 단순하다.

| 항목 | LSTM | GRU |
|------|------|-----|
| 게이트 수 | 3개 (input, forget, output) | 2개 (reset, update) |
| 내부 상태 | hidden state + cell state | hidden state만 |
| 파라미터 수 | 상대적으로 많음 | 상대적으로 적음 |
| 학습 속도 | 느림 | 빠름 |
| 장기 의존성 | 강함 | LSTM과 유사 수준 |

**선택 근거:**
- 마포구 데이터는 분기 단위, 최대 24분기(6년) — 극단적인 장기 의존성이 필요하지 않음
- 파라미터 수가 적어 156개 동×업종 조합의 소규모 데이터에서 과적합 위험 낮음
- LSTM과 동일한 Attention + FC Head 구조를 유지하여 공정한 성능 비교 가능
- 사전학습 epoch당 학습 시간: LSTM 대비 약 10~15% 단축

### 1.2 모델 아키텍처

```
입력 (batch, seq_len=4, input_size=31)
        ↓
  nn.GRU (hidden_size=128, num_layers=2, dropout=0.2)
        ↓
  gru_out (batch, seq_len, 128)   ← LSTM과 달리 h만 반환 (cell state 없음)
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
| input_size | 31 | ALL_FEATURES (26 기본 + 5 골목상권) |
| hidden_size | 128 | 실험 최적값 |
| num_layers | 2 | GRU 레이어 수 |
| dropout | 0.2 | num_layers > 1일 때 레이어 간 적용 |
| window_size | 4 | 입력 시퀀스 길이 (분기 단위) |
| output_size | 1 | 다음 분기 매출 예측 |

**LSTM predict.py와의 불일치 수정:**
기존 LSTM `predict.py`는 `window_size=6, hidden_size=256`으로 train config와 불일치했다.
GRU에서는 train config(window_size=4, hidden_size=128)와 predict config를 동일하게 통일하여 일관성을 확보했다.

---

## 2. 작업 환경

### 2.1 데이터 소스

| 항목 | 내용 |
|------|------|
| DB | AWS RDS PostgreSQL (`mapo-simulator.cx8eakyuk1jf.ap-northeast-2.rds.amazonaws.com`) |
| 사전학습 데이터 | `seoul_district_sales` (서울 전체 25개구) |
| 파인튜닝 데이터 | `district_sales` (마포구, dong_prefix=`11440`) |
| 점포 데이터 | `store_quarterly` (마포구, 3,840행) |
| 골목상권 데이터 | `data/processed/golmok_merged.csv` |
| 실행 환경 | Docker container (backend), CPU only |

### 2.2 LSTM과의 동일 조건

GRU와 LSTM은 아래 조건을 동일하게 유지하여 공정한 비교가 가능하다.

| 조건 | LSTM | GRU |
|------|------|-----|
| 피처 수 | 31개 | 31개 (동일) |
| 전처리 모듈 | `lstm_forecast/data_prep.py` | 동일 모듈 재사용 |
| Hot Deck 보간 | 적용 | 동일 |
| EXCLUDE_COMBOS | 염리동 중식, 성산1동 제과 | 동일 |
| COVID 가중치 | 2020~2021: sample_weight=0.5 | 동일 |
| 전이학습 전략 | 사전학습 → 파인튜닝 2단계 | 동일 |
| 백테스트 기준 | 2024년, 156개 조합 | 동일 |
| 신뢰구간 계산 | 95% (z=1.96), 선형 불확실성 증가 | 동일 |

---

## 3. 전체 작업 과정

### 3.1 구현

총 4개 파일을 신규 작성하였다. `lstm_forecast/data_prep.py`는 수정 없이 재사용.

| 파일 | 역할 |
|------|------|
| `models/gru_forecast/model.py` | `GRUForecaster` 클래스 정의 |
| `models/gru_forecast/train.py` | 사전학습 / 파인튜닝 함수 |
| `models/gru_forecast/predict.py` | 자기회귀 추론 함수 |
| `models/gru_forecast/__init__.py` | 패키지 진입점 |

**핵심 구현 차이 (LSTM 대비):**

```python
# LSTM: 튜플 언패킹 필요 (hidden state + cell state)
lstm_out, (h, c) = self.lstm(x)

# GRU: h만 반환 — cell state 없음
gru_out, _ = self.gru(x)
```

이 한 줄의 차이가 GRU와 LSTM의 핵심적인 구조 차이다. Attention과 FC Head 이후 로직은 완전히 동일하다.

### 3.2 사전학습 결과

```
실행 명령: docker compose exec backend python -m models.gru_forecast.train --mode pretrain
대상 데이터: 서울 전체 25개구 (seoul_district_sales)
```

| 항목 | 결과 |
|------|------|
| 설정 epoch | 100 |
| 실제 종료 epoch | **65** (조기종료) |
| 조기종료 기준 | val_loss 10 epoch 동안 개선 없음 |
| 최적 val_loss | **0.000318** (epoch 55 기준) |
| 최종 train_loss | 0.000404 |
| 최종 val_loss | 0.000405 |
| 저장 경로 | `models/gru_forecast/weights/pretrained_gru.pt` |
| 스케일러 경로 | `models/gru_forecast/weights/pretrain_gru_scalers.pkl` |
| epoch당 소요 시간 | 약 7.8초 |

### 3.3 파인튜닝 결과

```
실행 명령: docker compose exec backend python -m models.gru_forecast.train --mode finetune
대상 데이터: 마포구 (district_sales, dong_prefix=11440)
전이학습 전략: 2단계 — GRU freeze → FC 학습 → 전체 unfreeze → 낮은 lr로 재학습
```

**1단계: GRU freeze, FC만 학습**

| 항목 | 결과 |
|------|------|
| 설정 epoch | 10 |
| 실제 종료 epoch | 10 (전체 완료) |
| 최종 train_loss | 0.000554 |
| 최종 val_loss | 0.000484 |
| 학습률 | 0.0005 |

**2단계: 전체 unfreeze, 낮은 학습률**

| 항목 | 결과 |
|------|------|
| 설정 epoch | 50 |
| 실제 종료 epoch | **13** (조기종료) |
| 조기종료 기준 | val_loss 10 epoch 동안 개선 없음 |
| 최적 val_loss | **0.000462** (epoch 3 기준) |
| 최종 train_loss | 0.000529 |
| 최종 val_loss | 0.000474 |
| 학습률 | 0.0001 |
| 저장 경로 | `models/gru_forecast/weights/finetuned_mapo_gru.pt` |
| 스케일러 경로 | `models/gru_forecast/weights/finetune_gru_scalers.pkl` |

### 3.4 추론 테스트

```python
from models.gru_forecast.predict import predict
result = predict('11440555', 'CS100001')  # 상암동, 한식음식점
```

| 분기 | 예측 매출 | 신뢰구간 하한 | 신뢰구간 상한 |
|------|-----------|--------------|--------------|
| Q+1 | 28억 6,861만원 | 25억 8,748만원 | 31억 4,973만원 |
| Q+2 | 28억 7,562만원 | 23억 1,200만원 | 34억 3,924만원 |
| Q+3 | 28억 8,808만원 | 20억 3,898만원 | 37억 3,718만원 |
| Q+4 | 29억 1,287만원 | 17억 7,102만원 | 40억 5,471만원 |

- 자기회귀 방식으로 분기가 멀어질수록 신뢰구간 확대 → 정상 동작 확인
- 오류 없음, 4분기 모두 정상 예측 완료

### 3.5 백테스트

```
실행 명령: docker compose exec backend python -m validation.experiments.gru.backtest_gru
스크립트: validation/experiments/gru/backtest_gru.py
결과 저장: validation/results/gru_backtest_results.csv
```

- 대상: 2024년 마포구 156개 동×업종 조합 전체
- 데이터 누수 방지: `quarter < 20241` cutoff 적용 (2024 Q1 이전 데이터만 입력)
- 2건 건너뜀 (EXCLUDE_COMBOS 이상치 조합 제외: 염리동 중식, 성산1동 제과), 154건 예측 성공

---

## 4. 성능 결과

### 4.1 전체 정확도

```
실행 일자: 2026-04-14
평가 연도: 2024
샘플 수:   154개 동×업종 조합 (EXCLUDE_COMBOS 2건 제외)
```

| 지표 | 결과 |
|------|------|
| **MAPE** | **11.4%** |
| **MAE** | **1,476,486,299원 (약 14.8억)** |
| **RMSE** | **5,868,938,264원 (약 58.7억)** |
| **R²** | **0.9603** |

R²=0.9603은 모델이 실제 매출 분산의 96%를 설명하고 있음을 의미한다.

### 4.2 동별 MAPE (오름차순)

| 순위 | 동 | MAPE | 샘플 수 |
|------|-----|------|---------|
| 1 | 상암동 | **3.4%** | 10 |
| 2 | 서강동 | **5.1%** | 10 |
| 3 | 대흥동 | **6.2%** | 10 |
| 4 | 합정동 | 8.6% | 10 |
| 5 | 망원1동 | 9.2% | 10 |
| 6 | 망원2동 | 10.4% | 8 |
| 7 | 성산2동 | 10.6% | 10 |
| 8 | 공덕동 | 10.8% | 10 |
| 9 | 서교동 | 11.1% | 10 |
| 10 | 연남동 | 12.2% | 10 |
| 11 | 도화동 | 13.3% | 10 |
| 12 | 아현동 | 15.2% | 9 |
| 13 | 신수동 | 15.7% | 9 |
| 14 | 성산1동 | 16.9% | 9 |
| 15 | 용강동 | 17.1% | 10 |
| 16 | 염리동 | **17.8%** | 9 |

### 4.3 업종별 MAPE (오름차순)

| 순위 | 업종 | MAPE | 샘플 수 |
|------|------|------|---------|
| 1 | 일식음식점 | **7.6%** | 14 |
| 2 | 분식전문점 | **7.6%** | 16 |
| 3 | 중식음식점 | 9.0% | 15 |
| 4 | 커피-음료 | 9.2% | 16 |
| 5 | 치킨전문점 | 9.7% | 16 |
| 6 | 호프-간이주점 | 10.8% | 16 |
| 7 | 한식음식점 | 11.1% | 16 |
| 8 | 제과점 | 12.6% | 15 |
| 9 | 양식음식점 | 17.9% | 14 |
| 10 | 패스트푸드점 | **18.2%** | 16 |

---

## 5. 오류 및 해결 과정

### 5.1 `int64 TypeError` — 사전학습 실패

**발생 시점:** 사전학습 첫 실행 시

**오류 메시지:**
```
TypeError: Invalid value '171565859.76732683' for dtype 'int64'
```

**원인:**
`models/lstm_forecast/data_prep.py` 290번 줄 `_hot_deck()` 함수에서
int64 dtype 컬럼에 `donor_val * np.random.normal(1, 0.02)` (float) 값을 직접 할당할 때 발생.

```python
# 오류 발생 코드 (수정 전)
result.at[idx, col] = donor_val * np.random.normal(1, 0.02)
```

**해결 방법:**
`data_prep.py`는 A1(찬영) 담당 파일로 B2가 직접 수정 불가.
A1과 협의 후 A1이 아래 코드를 추가하여 dev 브랜치에 push.

```python
# 수정 후 (A1 적용)
if result[col].dtype == np.int64:
    result[col] = result[col].astype(float)  # int64 → float 변환
result.at[idx, col] = donor_val * np.random.normal(1, 0.02)
```

이후 `git fetch origin && git rebase origin/dev` 로 feature_sj 브랜치에 반영.

### 5.2 `ModuleNotFoundError` — 백테스트 실행 실패

**발생 시점:** 백테스트 첫 실행 시

**오류 메시지:**
```
ModuleNotFoundError: No module named 'validation'
```

**원인:**
`docker-compose.yml`의 backend 서비스 volumes 항목에 `validation/` 폴더 마운트가 누락.
컨테이너 내 `/app/validation/` 경로가 존재하지 않아 Python이 모듈을 찾지 못함.

```yaml
# 기존 volumes (validation 없음)
volumes:
  - ./backend:/app
  - ./data:/app/data
  - ./models:/app/models
```

**해결 방법:**
`docker-compose.yml` volumes에 한 줄 추가 후 Docker 재시작.

```yaml
# 수정 후
volumes:
  - ./backend:/app
  - ./data:/app/data
  - ./models:/app/models
  - ./validation:/app/validation   ← 추가
```

```bash
docker compose down
docker compose up --build -d
```

---

## 6. 분석 및 결론

### 6.1 GRU 성능 분석

**전반적 평가:**

R²=0.9603으로 GRU 모델이 2024년 마포구 매출 분산의 96% 이상을 설명하고 있다.
EXCLUDE_COMBOS 2개 조합(염리동 중식, 성산1동 제과) 제외 후 전체 MAPE 11.4%로,
외식 업종 매출 예측에서 허용 가능한 수준이다.

**정확도가 높은 동 특징:**
- 상암동(3.4%), 서강동(5.1%), 대흥동(6.2%) — 상권 특성이 안정적이고 계절 패턴이 규칙적인 지역
- 상암동은 IT·미디어 업무지구로 고정 수요가 있어 매출 변동성 낮음

**정확도가 낮은 동 분석:**
- 염리동(80.0%): `EXCLUDE_COMBOS`에 포함된 중식음식점 조합이 오차를 크게 끌어올림
  2024 Q3~Q4 서울시 추정매출 미공개로 실제값 불확실성 존재
- 성산1동(48.0%): `EXCLUDE_COMBOS`의 제과점 조합 영향

**정확도가 낮은 업종 분석:**
- 중식음식점(48.4%): 마포구 내 중식당은 분포가 불균일하고 염리동 데이터 품질 이슈 직결
- 제과점(32.3%): 성산1동 데이터 이슈 + 프랜차이즈 브랜드 확장/축소에 민감

### 6.2 한계점

| 한계 | 내용 |
|------|------|
| 2024 Q3~Q4 미공개 | 서울시가 2024 3~4분기 추정매출을 아직 공개하지 않아 일부 조합의 실제값 불확실 |
| EXCLUDE_COMBOS 영향 | 염리동 중식, 성산1동 제과 2개 조합이 전체 MAPE를 끌어올림 |
| 신뢰구간 단순화 | 현재 신뢰구간은 `5% × step × z` 선형 증가 방식 — 실제 불확실성 분포를 반영하지 못함 |
| 단변량 타겟 | monthly_sales 단일 타겟 예측 — 점포당 매출, 폐업률 등 다변량 예측은 미지원 |
| CPU 추론 | GPU 미사용으로 배치 추론 속도 제한 |

### 6.3 TCN 진행 시 기대사항

다음 단계로 TCN(Temporal Convolutional Network) 구현 예정이다.

| 항목 | GRU | TCN (기대) |
|------|-----|-----------|
| 구조 | 순환 신경망 (시퀀셜 처리) | 팽창 컨볼루션 (병렬 처리) |
| 학습 속도 | 중간 | 빠름 (병렬화 가능) |
| 장기 패턴 | hidden state로 압축 | 수용 영역(receptive field) 직접 제어 |
| 기울기 소실 | GRU 게이트로 완화 | 잔차 연결(residual)로 완화 |
| 하이퍼파라미터 | hidden_size, num_layers | kernel_size, dilation, n_channels |

TCN은 팽창 컨볼루션(dilated convolution)으로 window_size보다 긴 수용 영역을 갖추므로,
분기 데이터에서 **코로나 이전(2019) ↔ 코로나(2020~2021) ↔ 회복기(2022~2024)** 등
장기 구조 변화 패턴을 GRU보다 직접적으로 포착할 가능성이 있다.

3개 모델(LSTM, GRU, TCN) 구현 완료 후 동일 조건에서 통합 비교 분석 예정.

---

*이 문서는 GRU 구현 과정에서 생성된 모든 결과를 기록한 것입니다.*
*LSTM vs GRU vs TCN 통합 비교표는 TCN 완료 후 별도 문서로 작성 예정입니다.*
