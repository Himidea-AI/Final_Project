# C 모델 (customer_revenue) 실용 가치 평가 리포트

- **평가일**: 2026-04-28 ~ 2026-04-29
- **모델 ID**: customer_revenue MLPPredictor (P1-C)
- **Spec**: `docs/superpowers/specs/2026-04-29-cde-models-utility-design.md`
- **Plan**: `docs/superpowers/plans/2026-04-29-cde-models-utility-plan.md` (Phase 1, Task 1~5)
- **결과 CSV**:
  - `validation/results/customer_revenue_metrics.csv`
  - `validation/results/customer_revenue_scenario2.csv`
- **결론**: **C 모델 폐기 + group_mean baseline 채택 권고**

---

## 0. Executive Summary

C 모델(customer_revenue MLP)을 학술/실용/UI 3축으로 평가한 결과, **3축 모두에서 production 가치를 정당화하지 못함**.

- **학술 fail**: 그룹 평균(naive baseline)이 18% 더 정확 (MAE 0.0319 vs 0.0378). MASE 16개 차원 중 1개만 < 1.0.
- **실용 fail**: Scenario 2 (합정 카페 4분기) 에서 30대여성/50대 비율의 model vs naive 차이가 모두 5%p 미만 → **사용자 의사결정 결정 동일성 4/4**.
- **UI fail**: 대시보드 카드 1개 + PDF 5페이지에 단순 비율/매출 텍스트로 노출되지만, 동일한 출력값을 group_mean baseline 으로 교체해도 사용자 인지 차이가 거의 없음.

→ 결정: **C 모델 폐기**. `_run_customer_revenue` 호출을 group_mean baseline 으로 교체. Frontend 카드/PDF 페이지는 호환 인터페이스 유지(폐기 영향 0).

---

## 1. 학술 평가

### 1.1 측정 결과 (`validation/results/customer_revenue_metrics.csv`)

| 모델 | MAE_overall | KL_age | KL_gender | KL_time | KL_day |
|------|------------:|-------:|----------:|--------:|-------:|
| **c_model** | **0.0378** | 0.0463 | 0.00555 | **0.0797** | 0.01056 |
| group_mean (baseline) | **0.0319** | 0.0429 | 0.00555 | **0.0471** | 0.00600 |
| global_mean | 0.0749 | 0.1009 | 0.0247 | 0.2640 | 0.0269 |
| industry_only | 0.0537 | 0.0878 | 0.0106 | 0.0975 | 0.0251 |

### 1.2 MASE (16 차원, group_mean=1.0 기준)

| 차원 | c_model MASE | 평가 |
|------|-------------:|------|
| age_10_ratio | **2.92** | fail |
| age_20_ratio | 0.71 | **pass** (유일한 우위) |
| age_30_ratio | 1.17 | fail |
| age_40_ratio | 1.17 | fail |
| age_50_ratio | 0.96 | borderline |
| age_60_above_ratio | 1.01 | fail |
| male_ratio | 1.07 | fail |
| female_ratio | 1.07 | fail |
| time_00_06_ratio | 1.56 | fail |
| time_06_11_ratio | 2.11 | fail |
| time_11_14_ratio | 1.34 | fail |
| time_14_17_ratio | 1.31 | fail |
| time_17_21_ratio | 1.37 | fail |
| time_21_24_ratio | 1.21 | fail |
| weekday_ratio | 1.35 | fail |
| weekend_ratio | 1.35 | fail |

**MASE < 1.0 차원: 1/16 (age_20_ratio 만)**. 나머지 15개 차원은 group_mean(분기 × 동 × 업종 평균)이 더 정확.

### 1.3 게이트 판정

| 기준 | 임계 | 측정 | 결과 |
|------|------|------|------|
| segment-wise MASE < 1.0 | 16/16 차원 | 1/16 차원 | **fail** |
| MAE < group_mean × 0.8 | 0.0255 | 0.0378 | **fail (48% 더 큼)** |
| KL_time 개선 | < group_mean | 0.0797 vs 0.0471 | **fail (69% 악화)** |

→ 학술: **fail**. naive 가 18% 더 정확하며, 시간대 분포(KL_time) 에서 특히 심각하게 underperform.

---

## 2. 시나리오 분석 (Scenario 2)

### 2.1 시나리오 구성

- **상권**: 합정역 (`dong_code=11440680`)
- **업종**: 카페 (`industry_code=CS100002`)
- **분기**: 2024 1Q ~ 4Q
- **타겟**: 30대여성 (`age_30_ratio` × `female_ratio`), 50대 (`age_50_ratio`)
- **비교**: model 출력 vs naive (분기 × 동 × 업종 평균)

### 2.2 결과 (`validation/results/customer_revenue_scenario2.csv`)

| 분기 | model_30대여성 | naive_30대여성 | diff (pp) | model_50대 | naive_50대 | diff (pp) | 결정_달라짐 |
|------|-------------:|-------------:|----------:|----------:|----------:|----------:|:-----------:|
| 2024 1Q | 0.1096 | 0.1162 | -0.66 | 0.1655 | 0.1385 | +2.70 | **False** |
| 2024 2Q | 0.1094 | 0.1162 | -0.68 | 0.1653 | 0.1385 | +2.68 | **False** |
| 2024 3Q | 0.1107 | 0.1162 | -0.55 | 0.1618 | 0.1385 | +2.34 | **False** |
| 2024 4Q | 0.1108 | 0.1162 | -0.54 | 0.1620 | 0.1385 | +2.36 | **False** |

### 2.3 해석

- **30대여성**: 모든 분기에서 차이 ≤ 0.7pp. naive 와 사실상 동일.
- **50대**: 모든 분기에서 차이 ≤ 2.7pp (≤ 5pp 임계 미달). 점주 입장에서 "16% vs 14%" 수준의 미미한 차이.
- **결정 동일성**: 4/4 분기에서 model과 naive 가 동일한 타겟 추천 결과 → **점주 의사결정 영향 0**.

→ 실용: **fail**. 사용자가 "model 결과로 50대 타겟 마케팅 결정" vs "naive(분기 평균)로 50대 타겟 마케팅 결정" 간에 실질 차이가 없음.

---

## 3. UI 노출 검토

### 3.1 Frontend 노출 위치 (Step 5.1 grep 결과)

| 파일 | 역할 | 노출 형태 |
|------|------|-----------|
| `frontend/src/api/client.ts` | `customer_segment` REST 호출 (~100ms MLP 미리보기) | API 호출 |
| `frontend/src/App.tsx` | 좌측 패널 타겟 5필드 입력 + state 관리 | 입력 폼 |
| `frontend/src/hooks/useCustomerSegmentPreview.ts` | 입력 변경 시 자동 미리보기 호출 hook | 디바운스 호출 |
| `frontend/src/types/index.ts` | `CustomerSegment` 타입 정의 (`SimulationOutput.customer_segment`) | 타입 |
| `frontend/src/components/SimulationResult/dashboard/charts/CustomerSegmentCard.tsx` | **메인 노출 카드** (DemographicTab) | UI 카드 (텍스트 + 비율 바) |
| `frontend/src/components/SimulationResult/dashboard/tabs/DemographicTab.tsx` | DemographicTab 내 카드 마운트 | 탭 컨테이너 |
| `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictCustomerFlowTab.tsx` | "고객 유입 예측" 보조 탭에 모델명 라벨로만 사용 | 라벨 텍스트 |
| `frontend/src/components/PDF/HiddenPDFTemplate.tsx` | **PDF 보고서 5페이지** (조건부 — `customerSegment != null` 일 때만 렌더) | PDF 페이지 |
| `frontend/src/utils/pdfPropsBuilder.ts` | PDF builder 에 `customerSegment` 전달 | 전달 |

### 3.2 Backend 노출 위치

| 파일 | 역할 |
|------|------|
| `backend/src/main.py` | startup 시 MLP 워밍업, `/simulate` 응답에 `customer_segment` 포함, 별도 라우터 (`customer_segment` REST) 등록 |
| `backend/src/api/customer_segment.py` | `_run_customer_revenue` 단발 호출 endpoint (LangGraph 우회 미리보기) |
| `backend/src/agents/graph.py` | LangGraph 노드: 사용자 타겟 입력 → `SegmentProfile` dict 변환 |
| `backend/src/schemas/simulation_input.py` | 타겟 5필드 (`target_age_groups`, `target_gender`, `target_time_slots`, `target_day_types`) |
| `backend/src/schemas/simulation_output.py` | `customer_segment: dict | None` 응답 필드 |

### 3.3 메인 노출 형태 (CustomerSegmentCard)

`CustomerSegmentCard.tsx` 의 화면 출력:

1. **헤더 배지**: "전체의 X.X%" — `segment_ratio` 비율 (예: "전체의 8.4%")
2. **자연어 요약**: `profile_summary` (예: "30대 여성 점심시간 평일 고객")
3. **3 매출 카드**: 세그먼트 매출 / 식별 매출 / 전체 매출 기준 (₩ 포맷)
4. **차원 비율 바 6개**: `dimension_ratios` 상위 6 (가로 progress bar + % 텍스트)
5. **disclaimer**: "4차원 독립 가정(곱셈)으로 산출 ... 유동인구 실측치로 일부 보정"

### 3.4 PDF 노출 형태 (HiddenPDFTemplate Page 5)

- **조건부 렌더**: `customerSegment` 가 null 이면 PDF 4페이지, 있으면 5페이지.
- 페이지 5 내용: profile_summary 박스 + 3 매출 박스 + 4 차원 (10대~60대 / 남녀 / 시간대 / 요일) 비율 표.
- 푸터: "Analysis · customer_revenue MLP + living_population 실측 데이터 기반".

### 3.5 사용자 결정 영향 추정

| 노출 요소 | 사용자 결정 연결도 | 모델 vs baseline 차이 효과 |
|-----------|:-----------------:|:--------------------------:|
| `segment_ratio` (전체의 X.X%) | 중 | 합정 카페 4분기 ≤ 0.7pp → 점주 인지 불가 |
| `segment_sales` (₩) | 중 | 비율과 매출의 곱이므로 차이 비율 동일 |
| `dimension_ratios` 상위 6 | 저 | 시각 progress bar 형태, ≤ 3pp 차이는 길이 차 < 3px |
| `profile_summary` 자연어 | 저 | 모델 비율로 생성된 텍스트지만 group_mean 으로 동일 결과 |
| PDF Page 5 비율 표 | 중 | "30대 11.0% vs naive 11.6%" — 보고서 의사결정 영향 없음 |

→ UI: **카드/PDF 형태로 노출되긴 하지만 모델→baseline 교체 시 사용자가 인지할 차이가 발생하지 않음**. 노출 형태가 "비율" 단일 단위라 5pp 미만 차이는 UI 상에서 구분 불가.

---

## 4. 종합 판단

| 축 | 결과 | 근거 |
|----|------|------|
| 학술 | **fail** | MAE 0.0378 > group_mean 0.0319 (18% 악화), MASE < 1.0 인 차원 1/16 |
| 실용 (시나리오) | **fail** | Scenario 2 4/4 분기 결정 동일, 차이 모두 ≤ 5pp |
| UI | **fail** | 카드/PDF 노출 있지만 baseline 으로 교체 시 사용자 인지 불가 |

→ **3축 모두 fail. 결정: C 모델 폐기 + group_mean baseline 채택**

---

## 5. Production 권장 — group_mean baseline 마이그레이션

### 5.1 채택 baseline 정의

`group_mean`: **(분기 × 동 × 업종) 별 16 차원 평균**.

- 학습 데이터: 마포 16동 × 10업종 × 2019~2024 4분기 (학습 시 사용된 동일 train set)
- 저장 위치: `seoul_industry_segment_mean` (신규 테이블 권장) 또는 `static/customer_revenue_baseline.json`
- 16 차원 평균 = `age_10/20/30/40/50/60+ ratio` (6) + `male/female_ratio` (2) + `time_00_06/06_11/11_14/14_17/17_21/21_24 ratio` (6) + `weekday/weekend_ratio` (2)

### 5.2 마이그레이션 계획 (3 단계)

**Step A — baseline 저장 (1일)**:

1. `models/customer_revenue/baseline.py` 신설:
   ```python
   def predict_baseline(dong_code: str, industry_code: str, profile_dict: dict | None) -> dict:
       """16 차원 group_mean 을 dimension_ratios + segment_ratio + sales 추정으로 변환."""
   ```
2. 학습 데이터로 `(dong, industry) → 16 dim ratio` 사전 빌드 → JSON/DB 저장.
3. `(dong, industry)` 미존재 시 fallback: industry_only mean → global_mean.

**Step B — interface 교체 (0.5일)**:

1. `models/interface.py` 의 `_run_customer_revenue` 를 `predict_baseline` 호출로 교체.
2. 반환 dict 형식 100% 호환 유지 (`profile_summary`, `segment_ratio`, `segment_sales`, `identified_sales`, `total_sales_ref`, `dimension_ratios`).
3. `backend/src/main.py` 의 startup 워밍업 (`_warmup_customer_revenue`) 도 새 함수 호출로 변경.
4. **frontend 변경 0**: `CustomerSegment` 타입/카드/PDF 그대로 작동.

**Step C — 모델 자산 정리 (0.5일)**:

1. `models/customer_revenue/predict.py` → `models/customer_revenue/_legacy_mlp.py` 로 rename (참조 끊김).
2. `models/customer_revenue/checkpoints/` 보존 (재현성).
3. CustomerSegmentCard disclaimer 갱신:
   - 전: "4차원 독립 가정(곱셈)으로 산출 ... 유동인구 실측치로 일부 보정"
   - 후: "분기 × 동 × 업종 평균 분포 기반. 해당 조합 학습 데이터 평균."
4. PDF 푸터 갱신: "Analysis · 분기 × 동 × 업종 평균 분포 + living_population 실측 데이터".

### 5.3 회귀 검증

- `validation/experiments/customer_revenue/baseline_c.py` 재실행 → group_mean MAE 0.0319 재현 확인.
- Scenario 2 재실행 → 4/4 결정 동일성 유지 (당연 동일).
- frontend 카드/PDF 5페이지 visual regression: 비율 출력값 ≤ 3pp 차이로 사용자 인지 차이 없음을 스크린샷 비교로 확인.

### 5.4 폐기 대상 파일

- `models/customer_revenue/predict.py` (legacy 로 rename)
- `models/customer_revenue/train.py` (보존, 재학습 가능성 0)
- `models/customer_revenue/MLPPredictor` 클래스 (legacy)

### 5.5 보존 사항

- Frontend `CustomerSegmentCard`, PDF Page 5: **그대로 유지** (사용자 가시성 영향 없음, 데이터 출처 disclaimer 만 변경).
- `customer_segment` REST endpoint: **그대로 유지** (~100ms 미리보기 UX 보존, 내부 호출만 baseline 으로 교체).
- 타겟 5필드 입력 UI: **그대로 유지**.

---

## 6. 참고

- 학술 평가 스크립트: `validation/experiments/customer_revenue/baseline_c.py` (Task 3)
- 시나리오 분석 스크립트: `validation/experiments/customer_revenue/scenario_analysis.py` (Task 4)
- 메트릭 정의: `validation/metrics/forecast_metrics.py` (Task 1, KL/MAE/MASE 추가)
- 동일 패턴 D/E 모델 평가: Phase 2 (Task 6~7), Phase 3 (Task 8~12)
