# C/D/E 모델 실용 가치 평가 spec

- **작성일**: 2026-04-29
- **담당**: 찬영 (A1)
- **branch**: IM3-243-dong-fk-followup
- **상태**: spec — 사용자 리뷰 대기

## 1. 배경

### 1.1 문제 정의

마포구 상권분석 시뮬레이터 (SPOTTER) 의 핵심 ML 모델 3개 — **C (customer_revenue), D (living_pop_forecast), E (emerging_district)** — 가 production 에서 실제 사용자 (창업자) 의사결정에 가치를 주는지 검증되지 않음.

D 모델은 6 라운드 학술 평가 결과 모든 architecture 가 naive baseline 동급 (MASE ~1.0). E 모델은 합성 anomaly detection 0% (slope baseline 28% 대비 압도적 fail). C 모델은 학술 평가 X.

학술 fail 만으로 production 결정하지 않고, **실용 가치 (사용자 시나리오 + UI 노출)** 기준으로 재평가한다.

### 1.2 새 데이터 (emerging-trend B1, 2026-04-29 적재)

E 모델 재학습 ROI 를 결정적으로 바꾸는 5 테이블:
- `seoul_subway_passenger_daily` — 지하철 승하차 일별 (선행 지표)
- `seoul_dong_migration_monthly` — 20-30대 전입/전출 월별 (가장 빠른 신흥 신호)
- `seoul_ttareungi_usage_daily` — 따릉이 동별 일별 (동행 지표)
- `master_subway_station`, `master_ttareungi_station` — 마스터

기존 E 모델 6 피처 (sales, store_count, closure_rate, trend_score, open_count, close_count) 가 모두 **후행 지표**인 반면, B1 은 **선행 지표** — 신흥 상권의 진정한 "조기 감지" 가능.

## 2. 평가 Framework (3 축)

각 모델을 다음 3 축으로 평가:

### 축 1: 학술 baseline 비교
- 모델의 통계적 우월성 측정
- 표준 metric (MASE, AUC-ROC, MAE on ratio)
- baseline 정의: naive (lag 또는 그룹 평균), 단순 heuristic

### 축 2: 시나리오 분석 (3 시나리오)
사용자가 시뮬레이터 쓰는 핵심 시나리오에서 모델 출력 vs baseline 출력 비교:
- **Scenario 1: 입지 선정** — "30대 직장인 카페, 합정 vs 망원 vs 연남"
- **Scenario 2: 타겟 전략** — "합정 카페에 30대 여성 vs 50대 부부"
- **Scenario 3: 진입 타이밍** — "망원동 떠오르나? 지금 진입?"

각 시나리오에서 차이가 사용자 결정을 다르게 만드는지 검증.

### 축 3: UI 노출 분석
frontend dashboard 에서 모델 결과가 어떻게 노출되는지:
- 노출 위치 (어느 컴포넌트)
- 노출 형태 (숫자/차트/문장)
- 사용자가 해당 정보를 결정에 활용하는 형태

### 종합 판단 (각 모델별)

| 결과 | 결정 |
|---|---|
| 학술 통과 OR 실용 가치 명확 | ✅ 채택 |
| baseline (단순 규칙) 동급 | ⚠️ 대체 (모델 폐기, baseline 사용) |
| 학술 + 실용 모두 fail | ❌ 폐기 |

## 3. C 모델 평가 절차

### 3.1 Task 재정리
- 입력: dong (16) + industry (10) + quarter sin/cos + year_norm
- 출력: 16 차원 세그먼트 비율 (age 6 + gender 2 + time_zone 6 + weekday 2)
- 시뮬레이터 사용처: 동×업종에서 타겟 세그먼트의 매출 기여도

### 3.2 학술 baseline (신규 측정)

**Baseline 정의**:
- A. naive (dong, industry) 그룹 평균 비율 — 분기 무시
- B. global mean — 동/업종 무시
- C. industry-only 평균 — 동 무시

**Metric**:
- MAE on ratio (16 차원 평균)
- KL divergence (모델 분포 vs 실제 분포)
- 16 segment 별 MASE (baseline A 대비)

**게이트**:
- segment-wise MASE < 1.0 → 의미있는 모델
- MAE < baseline A 의 80% → 실용 개선 가능성

### 3.3 시나리오 분석 (Scenario 2 핵심)

"합정동 카페 30대 여성 타겟 vs 50대 부부 타겟"
- C 모델 답: 30대 X% / 50대 Y%
- naive 답: 카페 업종 전체 평균 비율
- 차이 임계: 5%p 이상이면 사용자 결정 다를 가능성, 미만이면 동일

### 3.4 UI 노출
- backend `[customer_revenue P1-C]` field 의 frontend 사용처 검토
- 노출 형태 (텍스트/차트/표)
- 사용자가 16 차원 비율을 보고 타겟 결정에 활용하는 형태

### 3.5 산출물
- 학술 metric 표 (MAE, KL, segment MASE)
- Scenario 2 모델 vs naive 비교
- UI 노출 분석
- 종합 판단

## 4. D 모델 평가 절차 (일별 24h 단위)

### 4.1 Task 단위 변경
이전 분기 평균이 아닌 **일별 (date × dong × time_zone)** 단위로 평가. 사용자 시나리오에서 "토요일 18시 합정 인구" 같은 구체적 답이 가치.

### 4.2 학술 결과 (이미 측정, 인용)
- v7_daily_residual: MAE 1,062, MASE_lag7 = **1.0004** (naive_lag7 동급)
- naive_lag7: MAE 1,039, R² 0.9707
- naive_lag1: MAE 1,375
- → 학술 fail (모델 = naive_lag7 정도)

### 4.3 시나리오 분석 (Scenario 1 핵심)

"30대 직장인 토요일 18시 카페, 합정 vs 망원 vs 연남"
- 모델 답: 24h × 4분기 또는 168 슬롯 (24h × 7요일)
- naive_lag7 답: 1주 전 같은 요일/시간대 값
- 검증: 168 슬롯의 동 ranking 일치율 (Kendall's tau)
- 임계: 16동 ranking 의 1, 2위가 모델/naive 에서 같으면 결정 동일

### 4.4 UI 노출
- backend `[living_population P1-D]` field 의 frontend 사용처
- AbmTab / Dashboard / SimulationResult 어디서 노출
- 노출 형태: peak_time_zone (대표 1점)? 24h 라인 차트? 168 슬롯 히트맵?
- 핵심 질문: 사용자가 24개 시점을 보는지, peak 만 보는지

### 4.5 산출물
- v7_daily_residual 학술 결과 (인용)
- Scenario 1 동 ranking 일치율
- UI 노출 분석
- 종합 판단: naive_lag7 채택 vs 모델 유지

## 5. E 모델 평가 절차 (B1 데이터 활용 + 재학습 시도)

### 5.1 Task 재정리
- LSTM Autoencoder anomaly detection
- 입력 (현재): 6 피처 후행 지표 (sales 변화)
- 입력 (재학습 후): 6 + B1 5 피처 = 11 피처 (선행 지표 추가)
- 출력: anomaly_score + signal (emerging/declining/normal)

### 5.2 학술 평가 보강

**Phase 5A: 현재 모델 학술 평가 (이미 측정됨)**
- 합성 anomaly detection: 0/50 (slope baseline 28%)
- baseline 들과 일치도 kappa ~0

**Phase 5B: change_ix supervised AUC (신규)**
- `seoul_adstrd_change_ix` 의 HH/HL/LH/LL → 신흥/쇠퇴 ground truth
- HL→LH 전이 = 신흥 (positive)
- HH→HL 전이 = 쇠퇴 (positive)
- 현재 LSTM AE anomaly_score 의 AUC-ROC 측정
- 게이트: AUC > 0.7 → 의미있는 모델, 0.5~0.7 → 약함, < 0.5 → 폐기

**Phase 5C: B1 데이터 단독 신호 강도 (신규)**
- 지하철 승하차 분기별 증감률 → AUC vs change_ix
- 20-30대 전입률 → AUC
- 따릉이 이용 변화율 → AUC
- 가설: B1 단독 baseline 도 LSTM AE 보다 강력 가능성

### 5.3 LSTM 재학습 (B1 피처 추가)

**입력 변경**: 6 → 11 피처 (B1 5 추가)
**공간 확장**: 마포 16동 → 서울 424동 (24배 데이터)
**코드 결함 수정**:
- train/val split: 시간순 단순 분할 → 그룹 내 stratified split
- group-level MinMaxScaler 분리 → global scaler + log1p
- threshold 95%ile → AUC-based threshold

**게이트**: change_ix supervised AUC > 0.7 → 모델 채택. 미통과 시 폐기.

### 5.4 시나리오 분석 (Scenario 3 핵심)

"망원동 떠오르나? 카페 차릴 만한가?"
- 모델 답: anomaly_score, signal
- baseline 답:
  - slope-based: 매출/store_count slope 부호
  - **B1 trend**: 지하철 승하차 증감 + 20-30대 전입률
  - **change_ix**: 서울시 공식 stage
- 4 가지 답 일치도 분석

### 5.5 UI 노출
- backend `EmergingResult` 의 frontend 사용처
- 자연어 summary ("망원동 카페: 최근 3분기 연속 이상 감지...") 노출 위치
- anomaly_score (0~1) 가 표시되는지, signal 만 보이는지
- 사용자가 진입 결정에 활용하는 형태

### 5.6 Production 결정 — 재학습 시도 + 3-tier Fallback

**Phase 5D-1: 재학습 결과 따라**:
- AUC > 0.7 → LSTM AE 채택 + 보조 fallback
- AUC < 0.7 → LSTM AE 폐기

**Phase 5D-2: Fallback 시스템 (3-tier)**:
1. **1차**: `change_ix` 직접 — 서울시 공식 라벨 (가장 정당성 ↑)
2. **2차**: B1 trend baseline — 지하철 + 20-30대 전입 (선행 지표)
3. **3차**: slope baseline — 매출/store_count (후행 지표)

각 tier 데이터 부재 시 다음 tier 로 자동 fallback.

### 5.7 산출물
- 현재 LSTM AE 학술 평가 (합성 anomaly + change_ix AUC)
- B1 단독 신호 AUC (LSTM 대안 가능성 진단)
- 재학습 결과 (AUC + train metric)
- Scenario 3 모델/B1/slope/change_ix 일치도
- UI summary 텍스트 사용자 가치 평가
- 3-tier fallback 시스템 production 코드

## 6. Implementation Phase + 일정

| Phase | 작업 | 일정 |
|---|---|---|
| 1 | C 모델 학술 baseline + 시나리오 + UI | 2일 |
| 2 | D 모델 일별 24h 시나리오 + UI | 1일 |
| 3A | E 모델 학술 보강 (change_ix AUC + B1 단독 신호) | 0.5일 |
| 3B | E 모델 LSTM 재학습 (서울 + B1 11 피처) | 1.5일 |
| 3C | E 모델 3-tier fallback 시스템 구현 | 1일 |
| 3D | E 모델 결정 게이트 (재학습 vs 폐기) | 0.5일 |
| 4 | 통합 spec + retrospective | 0.5일 |
| **합계** | | **6.5~7일** |

## 7. 산출물

### 코드
- C 모델: 결정 따라 `predict.py` 유지/대체/폐기
- D 모델: `predict_naive.py` (이미 작성됨, naive_lag7 기반)
- E 모델: 3-tier fallback `predict_emerging.py` (change_ix 1차 + B1 trend 2차 + slope 3차)

### 문서
- 본 spec (`docs/superpowers/specs/2026-04-29-cde-models-utility-design.md`)
- implementation plan (`docs/superpowers/plans/2026-04-29-cde-models-utility-plan.md`, writing-plans 결과)
- 평가 결과 docs (`docs/abm-simulation/`)

### 평가 결과
- C/D/E 각 모델 학술 metric 표
- 3 시나리오 모델 vs baseline 비교
- UI 노출 분석
- 최종 production 결정 (각 모델별)

## 8. 다음 단계

본 spec 사용자 승인 후 `superpowers:writing-plans` 스킬로 implementation plan 작성. plan 에서 각 Phase 의 task 단위 분해 + 검증 절차 + 게이트 정의.

## 9. 참고

- D 모델 학술 평가 결과: `docs/abm-simulation/living-pop-forecast-v2-vs-v3-report.md`
- E 모델 DB 보강 조사: 본 spec § 1.2
- B1 데이터 spec: `docs/superpowers/specs/2026-04-29-emerging-trend-data-b1-design.md`
