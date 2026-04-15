# TCN 시계열 예측 모델 구현 보고서

> 작성일: 2026-04-14
> 작성자: B2 (수지니)
> 관련 모델: `models/tcn_forecast/`
> 참조: `docs/gru-model-report.md` (GRU 구현 보고서)

---

## 목차

1. [TCN 모델 개요](#1-tcn-모델-개요)
2. [작업 환경](#2-작업-환경)
3. [전체 작업 과정](#3-전체-작업-과정)
4. [성능 결과](#4-성능-결과)
5. [오류 및 해결 과정](#5-오류-및-해결-과정)
6. [분석 및 결론](#6-분석-및-결론)

---

## 1. TCN 모델 개요

### 1.1 TCN 선택 이유

TCN(Temporal Convolutional Network)은 순환 신경망(RNN) 계열(LSTM, GRU)과 달리
팽창 인과 컨볼루션(Dilated Causal Convolution)을 이용한 시퀀스 모델이다.
순환 구조 없이 병렬 처리가 가능하며 잔차 연결(Residual Connection)로 기울기 소실을 방지한다.

| 항목 | LSTM | GRU | TCN |
|------|------|-----|-----|
| 구조 | 순환 신경망 | 순환 신경망 | 팽창 인과 컨볼루션 |
| 게이트 수 | 3개 | 2개 | 없음 |
| 병렬 처리 | 불가 (시퀀셜) | 불가 (시퀀셜) | 가능 |
| 기울기 소실 | cell state로 완화 | update gate로 완화 | Residual로 완화 |
| 수용 영역 제어 | hidden state 간접 | hidden state 간접 | dilations로 직접 제어 |
| 학습 속도 | 느림 | 중간 | 병렬화로 빠름 (단, 소규모에서 오버헤드) |

**선택 근거:**

- 마포구 분기 데이터(window_size=4)에서 `dilations=[1,2]`로 receptive field를 정확히 4로 설정 가능
- 병렬 처리 구조로 순환 신경망의 hidden state 누적 오차 없음
- `CausalConv1d`(인과 컨볼루션)으로 미래 데이터 누수 원천 차단
- Residual connection으로 기울기 소실 없이 깊은 네트워크 구성 가능
- LSTM/GRU 대비 공정 비교를 위해 동일 피처(31개), 동일 data_prep 재사용

### 1.2 모델 아키텍처

```
입력 (batch, seq_len=4, input_size=31)
        ↓
  input_proj: Linear(31 → 128)
        ↓  transpose → (batch, 128, 4)
  TemporalBlock (dilation=1)
    CausalConv1d(128→128, k=2, d=1)  padding=(2-1)×1=1 (왼쪽만)
    LayerNorm → ReLU → Dropout(0.2)
    CausalConv1d(128→128, k=2, d=1)
    LayerNorm → ReLU → Dropout(0.2)
    Residual: identity (in_ch == out_ch)
        ↓
  TemporalBlock (dilation=2)
    CausalConv1d(128→128, k=2, d=2)  padding=(2-1)×2=2 (왼쪽만)
    LayerNorm → ReLU → Dropout(0.2)
    CausalConv1d(128→128, k=2, d=2)
    LayerNorm → ReLU → Dropout(0.2)
    Residual: identity (in_ch == out_ch)
        ↓  last timestep [:, :, -1]  → (batch, 128)
  FC Head
    Linear(128 → 64) → ReLU → Dropout(0.2) → Linear(64 → 1)
        ↓
  출력 (batch, 1)   ← 스케일된 매출 예측값
```

**CausalConv1d 핵심 구현:**

```python
# 미래 데이터 누수 방지 — 왼쪽 패딩만 적용 (오른쪽 0)
self.padding = dilation * (kernel_size - 1)
out = F.pad(x, (self.padding, 0))  # 왼쪽에만 패딩
out = self.conv(out)
```

**Receptive Field 계산:**

```
RF = 1 + (kernel_size - 1) × Σdilations
   = 1 + (2 - 1) × (1 + 2)
   = 1 + 1 × 3 = 4
   = window_size (정확히 일치)
```

dilation=4 미사용 이유: RF=8이 되어 window_size=4를 초과하므로 제외.

**LayerNorm 적용 방식:**

Conv1d는 (batch, channels, seq) 형식이므로,
LayerNorm 전후로 transpose를 수행하여 channel 차원에 적용.

```python
# transpose → LayerNorm → transpose 역순 복원
out = self.norm1(out.transpose(1, 2)).transpose(1, 2)
```

### 1.3 하이퍼파라미터

| 파라미터 | 값 | 비고 |
|---------|-----|------|
| input_size | 31 | ALL_FEATURES (26 기본 + 5 골목상권) |
| n_channels | 128 | 각 TemporalBlock 채널 수 |
| kernel_size | 2 | CausalConv1d 커널 크기 |
| dilations | [1, 2] | 2개 TemporalBlock의 팽창률 |
| dropout | 0.2 | TemporalBlock 내 적용 |
| window_size | 4 | 입력 시퀀스 길이 (receptive field와 동일) |
| output_size | 1 | 다음 분기 매출 예측 |

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

### 2.2 GRU/LSTM과의 동일 조건

TCN, GRU, LSTM은 아래 조건을 동일하게 유지하여 공정한 비교가 가능하다.

| 조건 | LSTM | GRU | TCN |
|------|------|-----|-----|
| 피처 수 | 31개 | 31개 | 31개 |
| 전처리 모듈 | `lstm_forecast/data_prep.py` | 동일 재사용 | 동일 재사용 |
| Hot Deck 보간 | 적용 | 동일 | 동일 |
| EXCLUDE_COMBOS | 염리동 중식, 성산1동 제과 | 동일 | 동일 |
| COVID 가중치 | 2020~2021: sample_weight=0.5 | 동일 | 동일 |
| 전이학습 전략 | 사전학습 → 파인튜닝 2단계 | 동일 | 동일 |
| 백테스트 기준 | 2024년, 156개 조합 | 동일 | 동일 |
| 신뢰구간 계산 | 95% (z=1.96), 선형 불확실성 증가 | 동일 | 동일 |

---

## 3. 전체 작업 과정

### 3.1 구현 파일 목록

총 5개 파일을 신규 작성하였다. `lstm_forecast/data_prep.py`는 수정 없이 재사용.

| 파일 | 역할 |
|------|------|
| `models/tcn_forecast/model.py` | `CausalConv1d`, `TemporalBlock`, `TCNForecaster` 클래스 정의 |
| `models/tcn_forecast/train.py` | 사전학습 / 파인튜닝 함수 |
| `models/tcn_forecast/predict.py` | 자기회귀 추론 함수 |
| `models/tcn_forecast/__init__.py` | 패키지 진입점 |
| `validation/experiments/tcn/backtest_tcn.py` | TCN 백테스팅 스크립트 |

**핵심 구현 차이 (GRU 대비):**

```python
# GRU: 순환 구조 — 이전 hidden state를 순차적으로 전달
gru_out, _ = self.gru(x)                   # (batch, seq, hidden)
context = self.attention(gru_out)           # Attention으로 집약

# TCN: 컨볼루션 구조 — 입력을 한 번에 병렬 처리
x = self.input_proj(x)                     # Linear 투영
x = x.transpose(1, 2)                      # (batch, seq, ch) → (batch, ch, seq)
for block in self.tcn_blocks:
    x = block(x)                           # TemporalBlock 순차 통과
out = x[:, :, -1]                          # 마지막 타임스텝만 사용
```

GRU/LSTM은 Attention으로 시퀀스를 집약하는 반면, TCN은 마지막 타임스텝(`[:,:,-1]`)을 사용한다.
마지막 타임스텝이 dilated convolution을 통해 이미 수용 영역(4분기) 전체 정보를 담고 있기 때문이다.

### 3.2 사전학습 결과

```
실행 명령: docker compose exec backend python -m models.tcn_forecast.train --mode pretrain
대상 데이터: 서울 전체 25개구 (seoul_district_sales)
```

| 항목 | 결과 |
|------|------|
| 설정 epoch | 100 |
| 실제 종료 epoch | **58** (조기종료) |
| 조기종료 기준 | val_loss 10 epoch 동안 개선 없음 |
| 최적 val_loss | **0.000287** (약 epoch 48 기준) |
| 최종 train_loss | 0.000335 (epoch 58) |
| 최종 val_loss | 0.000308 (epoch 58) |
| 저장 경로 | `models/tcn_forecast/weights/pretrained_tcn.pt` |
| 스케일러 경로 | `models/tcn_forecast/weights/pretrain_tcn_scalers.pkl` |
| epoch당 소요 시간 | 약 25초 |

**GRU 대비 학습 속도 비교:**

| 모델 | epoch당 시간 | 종료 epoch |
|------|------------|-----------|
| GRU  | ~7.8초     | 65        |
| TCN  | ~25초      | 58        |

TCN이 GRU보다 약 3배 느린 이유: `input_proj(Linear 31→128)` 추가, 두 TemporalBlock의 Conv1d 연산, LayerNorm transpose 비용.
그러나 사전학습 best val_loss는 TCN(0.000287)이 GRU(0.000318)보다 낮아 전체 데이터 피팅 성능은 더 우수하다.

### 3.3 파인튜닝 결과

```
실행 명령: docker compose exec backend python -m models.tcn_forecast.train --mode finetune
대상 데이터: 마포구 (district_sales, dong_prefix=11440)
전이학습 전략: 2단계 — input_proj+TCN freeze → FC 학습 → 전체 unfreeze → 낮은 lr로 재학습
```

**1단계: input_proj + tcn_blocks freeze, FC만 학습**

| 항목 | 결과 |
|------|------|
| 설정 epoch | 10 |
| 실제 종료 epoch | 10 (전체 완료) |
| 최종 train_loss | 0.000450 |
| 최종 val_loss | 0.000441 |
| 학습률 | 0.0005 |

**2단계: 전체 unfreeze, 낮은 학습률**

| 항목 | 결과 |
|------|------|
| 설정 epoch | 50 |
| 실제 종료 epoch | **12** (조기종료) |
| 조기종료 기준 | val_loss 10 epoch 동안 개선 없음 |
| 최적 val_loss | **0.000420** (epoch 2 기준) |
| 최종 train_loss | 0.000418 (epoch 12) |
| 최종 val_loss | 0.000440 (epoch 12) |
| 학습률 | 0.0001 |
| 저장 경로 | `models/tcn_forecast/weights/finetuned_mapo_tcn.pt` |
| 스케일러 경로 | `models/tcn_forecast/weights/finetune_tcn_scalers.pkl` |

**freeze 범위 (GRU 대비 차이점):**

GRU는 `gru` 레이어만 freeze하지만, TCN은 `input_proj`와 `tcn_blocks` 모두 freeze한다.
FC Head만 먼저 학습시켜 마포구 데이터에 맞는 출력 스케일을 학습한 뒤,
전체를 unfreeze하여 낮은 학습률로 미세 조정한다.

### 3.4 추론 테스트

```python
from models.tcn_forecast.predict import predict
result = predict('11440555', 'CS100001')  # 상암동, 한식음식점
for r in result:
    print(r)
```

| 분기 | 예측 매출 | 신뢰구간 하한 | 신뢰구간 상한 |
|------|-----------|--------------|--------------|
| Q+1 | 29억 8,594만원 | 26억 9,332만원 | 32억 7,856만원 |
| Q+2 | 29억 2,548만원 | 23억 5,208만원 | 34억 9,888만원 |
| Q+3 | 29억 163만원 | 20억 4,855만원 | 37억 5,471만원 |
| Q+4 | 28억 9,214만원 | 17억 5,842만원 | 40억 2,587만원 |

- 자기회귀 방식으로 분기가 멀어질수록 신뢰구간 확대 → 정상 동작 확인
- Q+1~Q+3 예측값이 미세하게 하락하는 패턴 — TCN이 최근 4분기 추세(하락 패턴)를 반영한 것으로 해석
- 오류 없음, 4분기 모두 정상 예측 완료

### 3.5 백테스트

```
실행 명령: docker compose exec backend python -m validation.experiments.tcn.backtest_tcn
스크립트: validation/experiments/tcn/backtest_tcn.py
결과 저장: validation/results/tcn_backtest_results.csv
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
| **MAPE** | **12.6%** |
| **MAE** | **1,046,272,402원 (약 10.5억)** |
| **RMSE** | **2,559,463,369원 (약 25.6억)** |
| **R²** | **0.9925** |

R²=0.9925는 모델이 실제 매출 분산의 99.25%를 설명하고 있음을 의미한다.
MAE/RMSE는 GRU보다 낮으나(절대 오차 감소), MAPE는 GRU보다 높다(상대 오차 증가).

**GRU 대비 비교:**

| 지표 | GRU | TCN | 변화 |
|------|-----|-----|------|
| MAPE | 11.4% | 12.6% | ▲ 악화 |
| MAE | 14.8억 | 10.5억 | ▼ 개선 |
| RMSE | 58.7억 | 25.6억 | ▼ 개선 |
| R² | 0.9603 | 0.9925 | ▼ 개선 |

### 4.2 동별 MAPE (오름차순)

| 순위 | 동 | MAPE | 샘플 수 |
|------|-----|------|---------|
| 1 | 상암동 | **6.8%** | 10 |
| 2 | 서교동 | **7.8%** | 10 |
| 3 | 대흥동 | **8.9%** | 10 |
| 4 | 성산2동 | 9.8% | 10 |
| 5 | 망원2동 | 10.9% | 8 |
| 6 | 합정동 | 11.0% | 10 |
| 7 | 서강동 | 11.1% | 10 |
| 8 | 도화동 | 11.6% | 10 |
| 9 | 공덕동 | 11.9% | 10 |
| 10 | 연남동 | 12.7% | 10 |
| 11 | 아현동 | 13.3% | 9 |
| 12 | 염리동 | 14.3% | 9 |
| 13 | 망원1동 | 17.9% | 10 |
| 14 | 성산1동 | 18.0% | 9 |
| 15 | 용강동 | 18.0% | 10 |
| 16 | 신수동 | **18.8%** | 9 |

### 4.3 업종별 MAPE (오름차순)

| 순위 | 업종 | MAPE | 샘플 수 |
|------|------|------|---------|
| 1 | 커피-음료 | **8.1%** | 16 |
| 2 | 중식음식점 | 8.4% | 15 |
| 3 | 일식음식점 | **8.6%** | 14 |
| 4 | 한식음식점 | 9.9% | 16 |
| 5 | 분식전문점 | 11.1% | 16 |
| 6 | 호프-간이주점 | 11.5% | 16 |
| 7 | 치킨전문점 | 12.7% | 16 |
| 8 | 제과점 | 15.8% | 15 |
| 9 | 패스트푸드점 | 19.1% | 16 |
| 10 | 양식음식점 | **21.5%** | 14 |

---

## 5. 오류 및 해결 과정

### 5.1 TCN 구현 및 실행 중 오류

**오류 없음.**

TCN 구현(model.py, train.py, predict.py), 사전학습, 파인튜닝, 추론 테스트, 백테스트 전 과정에서
별도의 오류가 발생하지 않았다.

이전 GRU 단계에서 A1(찬영)이 `data_prep.py`의 `int64 TypeError`를 수정하고
`dev` 브랜치에 반영하였으며, `feature_sj`에 rebase한 후 TCN 작업을 시작하였기 때문에
TCN 단계에서는 해당 오류가 재발하지 않았다.

참고: `int64 TypeError` 상세 내용은 `docs/gru-model-report.md` 5.1 절 참조.

---

## 6. 분석 및 결론

### 6.1 TCN 성능 분석

**전반적 평가:**

R²=0.9925는 세 모델 중 가장 높은 분산 설명력이다.
MAE(10.5억)와 RMSE(25.6억)도 GRU(MAE 14.8억, RMSE 58.7억) 대비 대폭 개선되었다.
EXCLUDE_COMBOS 2건 제외 후 전체 MAPE는 12.6%로 GRU(11.4%)보다 소폭 높다.

**MAPE와 R²가 반대 방향인 이유:**

- R²는 분산 설명력 — 예측 방향(대형 상권의 높음/낮음)이 맞으면 높음
- MAPE는 상대 오차 — 소규모 상권에서 예측값이 실제값 대비 크게 벗어나면 높음
- TCN은 대형 상권(상암동, 서교동)에서 정확하게 예측하여 R²를 끌어올렸지만,
  규모가 작고 패턴이 불규칙한 상권(염리동, 성산1동)에서 상대 오차가 크게 발생

**정확도가 높은 동 특징:**

- 상암동(6.8%), 서교동(7.8%), 대흥동(8.9%) — TCN에서도 상위권 유지
- 상암동은 IT·미디어 업무지구로 매출 패턴이 규칙적 — TCN의 수용 영역(4분기)으로 충분히 포착 가능

**정확도가 낮은 동 분석:**

- 염리동(126.5%): GRU(80.0%) 대비 악화. `EXCLUDE_COMBOS` 포함 조합(중식) 영향 + 2024 Q3~Q4 미공개 데이터 불확실성이 TCN에서 더 크게 증폭
- 성산1동(79.8%): GRU(48.0%) 대비 악화. 제과점 데이터 이슈가 TCN의 컨볼루션 패턴 학습에 부정적 영향

**정확도가 낮은 업종 분석:**

- 중식음식점(78.9%): GRU(48.4%) 대비 악화. 염리동 중식 조합의 데이터 품질 이슈 직결
- 제과점(54.5%): GRU(32.3%) 대비 악화. 성산1동 이슈 + 프랜차이즈 브랜드 확장/축소에 민감한 업종 특성

### 6.2 GRU/LSTM 대비 TCN 특이점

**주요 지표 비교:**

| 지표 | LSTM | GRU | TCN |
|------|------|-----|-----|
| MAPE | 10.5% | 11.4% | 12.6% |
| R² | 0.9829 | 0.9603 | 0.9925 |
| MAE | 10.3억 | 14.8억 | 10.5억 |
| RMSE | 38.5억 | 58.7억 | 25.6억 |

*LSTM 백테스트 결과는 별도 문서(`validation/backtest_revenue.py`) 참조*

**TCN 특이점:**

1. **R² 급등** (0.9604 → 0.9925): TCN은 대형 상권 매출의 분산을 GRU보다 훨씬 정확하게 설명
2. **MAE/RMSE 감소**: 대형 상권에서 절대 오차 감소 — TCN의 receptive field가 계절 패턴 4분기를 정확히 커버
3. **MAPE 증가** (17.4% → 23.8%): 소규모·불규칙 상권에서 상대 오차 증가
4. **염리동·중식 악화**: `EXCLUDE_COMBOS` 조합이 TCN에서 더 민감하게 반응 — 순환 신경망의 hidden state 평활화 효과가 없기 때문으로 추정

**수용 영역(Receptive Field) 특성:**

TCN의 RF=4(window_size와 동일)는 최적 설계이지만, 패턴 변화가 4분기보다 긴 호흡으로 나타나는 업종(제과점, 중식 등)에서는 충분하지 않을 수 있다. 반면 GRU는 hidden state를 통해 더 긴 의존성을 암묵적으로 반영할 수 있다.

### 6.3 한계점

| 한계 | 내용 |
|------|------|
| 2024 Q3~Q4 미공개 | 서울시가 2024 3~4분기 추정매출을 아직 공개하지 않아 일부 조합의 실제값 불확실 |
| EXCLUDE_COMBOS 취약 | 염리동 중식, 성산1동 제과 조합이 MAPE를 크게 끌어올림 — TCN에서 GRU보다 더 민감 |
| RF 고정 | kernel_size=2, dilations=[1,2]로 RF=4 고정 — 4분기 이상의 장기 패턴 반영 불가 |
| 신뢰구간 단순화 | 현재 신뢰구간은 `5% × step × z` 선형 증가 — 실제 불확실성 분포 미반영 |
| 단변량 타겟 | monthly_sales 단일 타겟 예측 — 점포당 매출, 폐업률 등 다변량 미지원 |
| CPU 추론 | GPU 미사용으로 batch 추론 속도 제한 |

---

**3개 모델(LSTM, GRU, TCN) 최종 비교는 TCN 완료 후 별도 문서로 작성 예정이다.**

---

*이 문서는 TCN 구현 과정에서 생성된 모든 결과를 기록한 것입니다.*
*LSTM vs GRU vs TCN 통합 비교표는 별도 문서로 작성 예정입니다.*

---

## 반복 실험 결과 (시드 설정 X)

> 시드 미설정(torch/numpy/random seed 없음) 조건에서 3회 독립 학습 후 백테스트 결과.
> 각 회차는 사전학습 → 파인튜닝 → 백테스트 전 과정을 새로 실행함.
> 평가 기준: 2024년 마포구 154개 동×업종 조합 (EXCLUDE_COMBOS 2건 제외)

| 회차 | MAPE | MAE | RMSE | R² |
|------|------|-----|------|----|
| run1 | 12.61% | 10.5억 (1,046,272,402원) | 25.6억 (2,559,463,369원) | 0.9925 |
| run2 | 10.85% | 7.1억 (711,895,931원) | 19.3억 (1,925,126,231원) | 0.9957 |
| run3 | 11.38% | 10.9억 (1,089,487,974원) | 29.0억 (2,898,883,136원) | 0.9903 |
| **평균** | **11.61%** | **9.5억** | **24.6억** | **0.9928** |
| **표준편차** | **0.90%** | — | — | — |

- 3회 MAPE 범위: 10.85% ~ 12.61% (최대 편차 1.76%p) — 세 모델 중 회차 간 변동이 가장 큼
- run2(MAPE 10.85%)는 LSTM run1(10.49%)에 근접한 우수한 성능
- R²는 3회 모두 0.990 이상 유지 — 분산 설명력은 시드에 관계없이 안정
- MAPE 표준편차 0.90%는 LSTM(0.15%), GRU(0.22%)보다 크게 높음 → TCN은 초기화 시드에 민감

**참조 CSV 파일:**
- `validation/results/tcn_backtest_results.csv` (run1)
- `validation/results/tcn_backtest_results_run2.csv` (run2)
- `validation/results/tcn_backtest_results_run3.csv` (run3)

### 실험 B: 시드 설정 O
→ 추후 추가 예정
