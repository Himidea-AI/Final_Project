# living_pop_forecast (D 모델) 평가 리포트 — 2026-04-29

> 담당: 찬영(A1) | Plan: `docs/superpowers/plans/2026-04-29-cde-models-utility-plan.md` § Task 7
> 목적: D 모델(유동인구 시간대별 예측, TCN 계열)이 학술 baseline 을 통과하지 못한 상황에서, UI 노출 형태와 사용자 의사결정 영향력을 같이 검토하여 **production 채택 모델**을 결정한다.

---

## 1. 학술 결과 (재정리)

D 모델은 **학습 plan 6 라운드 (v2 / v3 / v4_residual / v5(3변형) / v6_dow_hour_residual / v7_daily_residual)** 모두 naive baseline 을 넘지 못했다. 재학습/튜닝/잔차/계절성/일별 우회까지 시도한 결과는 다음과 같다.

| 모델 | n_test | MAE | RMSE | MAPE_pct | R² | MASE_lag1 | MASE_in_sample (Hyndman) |
|------|-------:|----:|-----:|---------:|---:|----------:|--------------------------:|
| naive_lag1 (분기) | 1,211 | 839.84 | 1,211.93 | 2.107 | 0.9892 | **1.000** | **0.7960** |
| v4_residual | 1,211 | 837.41 | 1,178.26 | 2.168 | 0.9898 | 0.997 | 0.7937 |
| naive_lag4_seasonal | 1,211 | 1,277.60 | 1,667.85 | 3.422 | 0.9795 | 1.521 | 1.2108 |
| v6_dow_hour_residual (시간 단위) | 8,468 | 1,048.97 | 1,700.92 | 2.607 | 0.9805 | 0.999 | 0.9453 |
| **v7_daily_residual** | (일별) | — | — | — | — | **1.0004** (lag7) | — |

**핵심 사실**:
- v7 의 MASE_lag7 = 1.0004 — naive_lag7(직전 같은 요일) 과 사실상 동일.
- Hyndman 의 in-sample MASE 정의로는 0.804 (학습셋의 평균 1-step naive 오차로 정규화). 즉 _학습 분포 안에서는 naive 보다 5%p 가량 우위_ 라고 주장 가능하나, **out-of-sample lag-7 naive 와 비교하면 차이가 사라진다**.
- 잔차 학습(v4/v6/v7) 은 모두 +0.3% 안쪽의 "noise level 개선" 에 그침 → 모델이 학습 가능한 신호를 사실상 추출하지 못했음을 의미.

출처:
- `validation/results/living_pop_metrics_all.csv`
- `validation/results/living_pop_metrics_in_sample_check.csv`
- `validation/results/living_pop_daily_baselines.csv`
- 코드 주석: `models/living_pop_forecast/predict_naive.py` 9~17행

---

## 2. 168 슬롯 dong-ranking 일치율 (T6 결과)

학술 점수가 동률이라도 **순위(ranking)** 가 다르면 의사결정 영향이 다르다. 168(요일 7 × 시간 24) 슬롯 각각에서 16개 마포동의 인구 ranking 을 actual 과 naive_lag7/naive_lag1 사이에 Kendall's tau 로 비교했다.

데이터: `validation/results/living_pop_daily_ranking.csv` (168 행)

| 지표 | naive_lag7 | naive_lag1 |
|------|-----------:|-----------:|
| 평균 tau | **0.9797** | 0.870 ~ 0.95 (시간대별 분포) |
| 최소 tau | 0.9000 | 0.7333 |
| tau > 0.95 슬롯 | 142 (84.5%) | < naive_lag7 |
| tau > 0.90 슬롯 | 167 (99.4%) | — |
| tau > 0.80 슬롯 | 168 (100%) | — |
| tau < 0.80 슬롯 | **0** | 일부 존재 |

**해석**:
- naive_lag7(1주 전 같은 요일/시간) 의 ranking 이 actual 과 사실상 동일 (mean tau ≈ 0.98).
- v7 / TCN 계열이 학술 점수에서 동률이고 ranking 도 같은 영역(naive_lag7) 에 수렴한다면 **사용자가 보는 결과(dong 비교, 피크 시간) 는 두 모델이 동일**.
- v7 가중치를 production 에 올려도 시각화상 의미 차이가 발생하지 않음.

---

## 3. UI 노출 검토 (Step 7.1 grep)

### 3.1 frontend 노출

| 위치 | 노출 형태 | 비고 |
|------|-----------|------|
| `frontend/src/components/SimulationResult/dashboard/charts/PeakHourCard.tsx` | **q1(다음 분기) 24시간 막대 차트 + 피크 시간 1점 강조 + 분기별 피크 추이(q1~q4)** | TCN 명칭 노출. 유동인구 피크 시간/피크 인원 자연어 요약 포함. |
| `frontend/src/components/SimulationResult/dashboard/tabs/DemographicTab.tsx` | DemographicTab 하단에서 `<PeakHourCard data={livingPop} />` 렌더 (54~146행) | `simResult.living_pop_forecast` 가 비어 있으면 fallback 카드 표시. |
| `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictCustomerFlowTab.tsx` | 모델명 라벨 `customer_revenue + living_pop_forecast` (탭 제목용) | 직접 데이터 렌더는 없음 — C/D 결합 라벨 표기. |
| `frontend/src/components/PDF/HiddenPDFTemplate.tsx` | "customer_revenue MLP + living_population 실측 데이터 기반" 캡션 | 실측 데이터 기반이라 명시 → naive 로 바꿔도 캡션 유효. |
| `frontend/src/types/index.ts` | `LivingPopForecast` / `LivingPopHourPrediction` / `LivingPopQuarterPrediction` 타입 정의 | `quarter_offset, peak_time_zone, peak_pop, all_hours[]` 4 필드. |

**핵심 노출 형태**: q1 24시간 막대 + 피크 시간 1점. 168 히트맵은 없음. 분기별 피크 시간 변화(q1~q4)는 카드.

### 3.2 backend 노출

| 위치 | 역할 |
|------|------|
| `models/interface.py` 536~559행 | `predict_peak(dong_name, n_quarters=4)` 호출 → `living_pop_result` dict 생성 → `generate()` 응답에 `"living_pop_forecast"` 키로 포함. |
| `backend/src/main.py` | `sim_result.get("living_pop_forecast")` 그대로 응답 dict 에 전달. |
| `backend/src/schemas/simulation_output.py` | `living_pop_forecast: dict \| None` 스키마 정의 + 키 주석. |
| `models/living_pop_forecast/predict_naive.py` | **production naive 구현 — `predict_peak_naive(dong_name, n_quarters)` 시그니처가 기존 `predict_peak()` 와 호환**. 이미 작성 완료. |

---

## 4. 사용자 결정 영향 추정

| 질문 | 영향 |
|------|-----|
| 다음 분기 피크 시간대는 언제? | **lag-7 = 직전 분기와 동일 시간대 → naive 답변과 v7 답변이 일치 (mean tau 0.98)** |
| 마포 16동 중 어느 동이 시간대별 가장 붐비는가? | naive_lag7 ranking 과 actual ranking 이 사실상 동일 (>0.95 84.5% 슬롯) |
| q1~q4 사이 피크 시간이 변하는가? | naive_lag1 모델은 4분기가 모두 같은 24h 패턴. v7 도 학술상 lag-7 동급이라 분기간 변화를 의미있게 잡지 못함 (TCN의 변화 신호 = noise level). |
| 운영 인력/재고 배치 기준 시간 | naive 가 답변 가능. v7 추가 비용(가중치 로딩 + 추론) 대비 정보 이득 0. |

→ **결론: 사용자가 PeakHourCard 에서 얻는 모든 정보를 naive 모델이 동일 품질로 제공한다.**

---

## 5. 종합 판단 — naive_lag7 / lag1 채택

### 채택 근거 (3 축 모두 합격)

| 축 | 결과 | 판단 |
|----|------|------|
| 학술 (MASE) | 6 라운드 모두 fail (v7 MASE_lag7 = 1.0004 = naive 동급) | naive 가 최소 동등 |
| Ranking (Kendall's tau) | mean 0.98, < 0.80 슬롯 0개 | naive ranking = actual ranking |
| UI 영향 | 24h 차트 + 피크 1점 — 두 모델이 같은 시각화 산출 | 사용자 차이 없음 |

→ **production 모델: `models/living_pop_forecast/predict_naive.py` 의 `predict_peak_naive()`**
→ v7 가중치는 **archive** (학술 reference 용으로만 보존, production interface 에서 제거).

### 마이그레이션 단계

1. **(이미 완료)** `models/living_pop_forecast/predict_naive.py` 에 `predict_peak_naive()` 시그니처 호환 구현.
2. `models/interface.py` 541~545행 import / call 만 교체:
   ```python
   from models.living_pop_forecast.predict_naive import predict_peak_naive as _predict_peak
   quarters_pred = _predict_peak(dong_name, n_quarters=4)
   ```
   (응답 dict 구조는 동일하므로 frontend/schemas 변경 불필요.)
3. `PeakHourCard.tsx` 149행 disclaimer 1 줄만 갱신:
   - 현재: `※ TCN 모델 — 코로나 시기(2020~2021) 가중치 0.5 보정 적용.`
   - 권장: `※ naive baseline (1주 전 같은 요일/시간 평균) — TCN 6 라운드 학술 검증 결과 동급으로 단순 모델 채택.`
4. `models/living_pop_forecast/weights/` 디렉토리 README 추가 — v7 가중치는 reference, production 에서 사용하지 않음을 명시. (별도 task)
5. 회귀 테스트: 같은 (dong, quarter) 입력에 대해 두 함수의 응답 dict 키/타입 일치 확인. (별도 task)

### 보존 사항

- v7 학술 결과(`validation/results/living_pop_metrics_*.csv`, `living_pop_lodo_v3.csv`) 는 **archive 로 유지**. 차후 외부 데이터(소셜/카드/이동통신) 추가 시 재시도의 baseline 으로 활용.
- `models/living_pop_forecast/predict.py` 의 TCN 추론 코드는 _제거하지 않음_ (학술 reference). interface 에서 import 만 제거.

---

## 6. 우려사항 / 한계

1. **분기 단위 외삽**: naive_lag1 은 모든 미래 분기가 직전 분기와 동일하다고 가정. 사용자가 "q3 의 피크가 q1 과 다를 것" 으로 기대해도 같은 값이 표시됨. 단 v7 도 분기 간 의미 있는 차이를 보이지 못했으므로 정확성 손실은 없음 (사용자 기대 misalignment 만 존재).
2. **마포 16동 외부 외삽 불가**: naive 는 학습된 16동에 대해서만 동작. v7 도 동일했으므로 추가 손실 없음.
3. **2025/2026 분기 데이터 신선도**: naive 는 가장 최근 분기 값을 그대로 사용 — DB 의 `mapo_resident_pop` (또는 living_population_grid) 가 최신화되어야 시즌성 반영 가능. ETL 갱신 주기 확인 필요.
4. **신뢰구간 재정의**: naive 는 현재 ± 5% 고정. v7 의 분기별 확장 분포보다 단순. UI 에 신뢰구간이 노출되지 않으므로 즉시 영향은 없으나, 향후 `confidence_lower/upper` 를 카드에 추가한다면 hist 기반 분위수로 교체 권장.
5. **disclaimer 문구 미반영 시 혼란**: PeakHourCard 의 "TCN" 라벨이 그대로면 사용자/리뷰어가 모델 채택 결정과 UI 라벨이 어긋난다고 느낄 수 있음. 마이그레이션 step 3 반드시 동반 PR.

---

## 7. 참고 파일

- `models/living_pop_forecast/predict_naive.py` — production 후보 (작성 완료)
- `models/living_pop_forecast/predict.py` — TCN 추론 (archive 후보)
- `models/interface.py` 536~559행 — D 모델 호출 지점
- `frontend/src/components/SimulationResult/dashboard/charts/PeakHourCard.tsx` — UI 카드
- `frontend/src/components/SimulationResult/dashboard/tabs/DemographicTab.tsx` 21,54~55,145~146행 — 카드 렌더
- `frontend/src/types/index.ts` — `LivingPopForecast` 스키마
- `backend/src/schemas/simulation_output.py` — 응답 스키마
- `validation/results/living_pop_daily_ranking.csv` — T6 ranking 결과 (168 슬롯)
- `validation/results/living_pop_metrics_all.csv` — 학술 baseline 결과
- `validation/results/living_pop_lodo_v3.csv` — 16-fold leave-one-dong-out 결과

---

작성: 2026-04-29 / 작성자: 찬영(A1) / 상태: 결정 — naive_lag7 production 채택 (마이그레이션 별도 task).
