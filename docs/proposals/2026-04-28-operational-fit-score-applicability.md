# operational_fit_score 활용 가능성 검토 — ABM 및 다른 영역

**작성일:** 2026-04-28
**작성자:** A1 찬영
**대상 문서:** [`docs/proposals/operational_fit_scorer.md`](./operational_fit_scorer.md) (산출 공식·검증 기록)
**브랜치:** `IM3-243-dong-fk-followup`

---

## 0. Executive Summary

`operational_fit_score`(0.10·subway + 0.40·bus + 0.50·fclty)는 마포 16동 × 8분기 매출 회귀로 검증된 **R²=0.55의 정적 입지 적합도 점수**다. 본 문서는 이 점수를 (a) 본인이 작업 중인 ABM(1,000 에이전트, Policy 55 하드코딩)에, (b) 다른 6개 영역에 적용할 가치를 평가한다.

**핵심 결론:**
- ✅ **본인 ABM 작업에 적용 가치 큼** — 매출 ground-truth와 일관된 가중치라 검증 신뢰도 ↑
- ✅ 본인 영역에서 직접 진행 가능한 가장 ROI 높은 작업: **`abm_vs_grid_*.py` 검증 baseline 강화** (이번 PR commit에 포함됨)
- 🔥 다른 영역 6곳 활용 가능 (TCN 피처, closure_risk, frontend, emerging_district, 정책 시뮬레이터, 추천 시스템)
- ⚠️ 한계: 마포 16동 한정, 정적, 지하철 가중치 R²=0.004로 미흡, TCN 피처와 중복 가능성

---

## 1. 본인 ABM 작업과의 적합성

### 1-1. 현재 ABM 구조 (memory + 본 PR commit 기준)

| 항목 | 현 상태 |
|---|---|
| 에이전트 수 | 1,000개 (마포구) |
| 정책 | Policy 55 **하드코딩** + Archetype 30종 |
| 비용 | LLM $0 (Haiku+Flash → 하드코딩 진화) |
| 검증 | Phase I/Full PSE-3 (`validation/abm_vs_grid_*.py` 4종) |
| 환경 | 마포 16동 |

### 1-2. ABM에 들어갈 수 있는 자리 (3가지)

#### ✅ 1-2-A. 에이전트 출점 위치 선택 가중치 (가장 적합)

archetype 별 선호도 × `operational_fit_score`로 weighted softmax 추첨:

```python
# archetype 가 "유동인구 의존형" 인 경우
weight[dong] = base_pref[dong] * (op_fit[dong] / 100) ** alpha
prob = softmax(weight)
chosen_dong = random.choices(dongs, weights=prob)
```

**장점:**
- 가중치 0.10/0.40/0.50이 이미 마포 8분기 매출 회귀(R²=0.55)로 검증됨 → ABM 결과와 매출 ground-truth 정합성 ↑
- 16동 정확히 매칭 (스코어가 16동 단위로 산출됨)
- 정적 점수라 시뮬레이션 매 step 재계산 불필요 → ABM 비용 부담 없음

**제약:**
- Policy 55 하드코딩 구조에서 **선호도 결정이 archetype 내부에 들어 있다면 외부 score 주입이 어려움**
- archetype 정의 인터페이스 사전 확인 필요

#### ⚠️ 1-2-B. 생존확률 / 폐업률 보정 (조건부 적합)

```python
base_survival_prob = closure_rate(dong, industry)
adjusted = base_survival_prob * (op_fit[dong] / 50)  # 50=중앙값
```

**장점:** 매출과 생존 모두에 동일 입지 신호 반영 → ABM 일관성

**제약:**
- closure_risk 모델(LightGBM+TCN)이 이미 입지 관련 피처를 학습 → **이중 가중**으로 over-fit 위험
- ABM이 closure_rate를 어떤 소스에서 가져오는지에 따라 가치 다름

#### ❌ 1-2-C. 매 분기 동적 보정 (부적합)

operational_fit_score는 **정적 점수**(시설 수/거리 기반, 분기별 거의 변동 없음). ABM의 시간 진화 변수로 부적합. 정적 prior로만 사용 권장.

### 1-3. 본 PR `validation/abm_vs_grid_*.py` 와의 연결

방금 머지된 4개 검증 스크립트(`abm_vs_grid_decomposed`, `_full_phase`, `_investigate`, `_pse3`)에서 **`operational_fit_score`를 baseline grid의 weighting**으로 활용 가능:

```python
# abm_vs_grid_full_phase.py 등에서
grid_weight[dong] = op_fit[dong]   # 균일 분포 대신 op_fit 가중
```

→ ABM이 "균일 grid 보다 나은가?" 라는 질문에서 **"op_fit grid 보다 나은가?"** 로 베이스라인이 강화된다 (더 엄격한 검증).

---

## 2. 다른 영역 활용 가능성 (6곳)

### 2-1. 🔥 TCN 매출 예측 입력 피처 (가장 ROI 높음)

현재 `ALL_FEATURES` 34개 중 입지 직접 변수는 `bus_flpop`, `adstrd_flpop`, `subway_statn_co` 정도. **`operational_fit_score` 자체를 1피처로 추가** 시:

| 효과 |
|---|
| 비매출 22 피처 중 1자리 → input_size 35로 확장 |
| 매출 R²=0.55 사전 합성 정보를 TCN에 주입 — 학습 수렴 속도 ↑ |
| SHAP에서 `op_fit` 기여도가 명시적으로 분리되어 해석성 ↑ |

**제약:** TCN-A/B 가중치는 input_size=34로 학습됨 → 재학습 필요. 본인 plan(`docs/superpowers/plans/2026-04-25-tcn-imputed-vs-original-comparison.md` 부록 E)과 동일한 방식으로 진행 가능.

### 2-2. closure_risk 모델 피처 (적합)

`models/closure_risk/` LightGBM+TCN 앙상블이 동·업종 폐업위험도를 예측. `operational_fit_score` 추가 시 fail 케이스(현재 응답에서 `risk_score: null`)의 보강 신호 가능. 다만 closure_risk fail 자체는 모델 추론 코드 문제이므로 우선순위 낮음.

### 2-3. Frontend Dashboard 노출 (이미 부분 노출)

응답에 `analysis_metrics.operational_fit_score: 47.6` 이 이미 포함됨. **SummaryTab의 "이 가게 경쟁력은 뭘까" 카드 보강 데이터**로 활용 가능:

```typescript
// SummaryTab.tsx 카드 1 items 배열에 추가
{ text: `입지 적합도 ${Math.round(opFit)}점`, highlight: opFit >= 70 }
```

→ 카드가 "분석 대기"일 때도 op_fit 만 표시할 수 있어 fallback 가치 ↑.

(관련: [`docs/issues/2026-04-28-summary-tab-empty-cards.md`](../issues/2026-04-28-summary-tab-empty-cards.md))

### 2-4. emerging_district autoencoder 보강

`models/emerging_district/` 신생/이상 상권 탐지. **op_fit이 낮은데 매출 anomaly 양수** 인 동 = 입지 핸디캡 극복 상권 → 신생 상권 후보 식별 정확도 ↑.

### 2-5. 시나리오 시뮬레이션 (정책 효과 측정)

`operational_fit_scorer.py`의 `calibrate_weights_from_shap()` 자동 캘리브레이션 기능과 결합:

- 가상 시나리오: "신규 지하철역 개통" → 거리 d 재계산 → op_fit 재산출 → ABM 매출 변화량
- 정책 simulator로 활용 가치 큼

### 2-6. 추천 시스템 (아직 없는 영역)

1순위 동 추천 (`top_3_candidates: ["아현동", "도화동", "용강동"]`)에 op_fit 가중치 추가:

```python
score[dong] = 0.6 * tcn_revenue[dong] + 0.4 * op_fit[dong]
```

→ 응답의 `district_rankings` 보강 가능.

---

## 3. 한계 · 주의사항

| 한계 | 설명 |
|---|---|
| **마포 16동 한정** | min-max 정규화가 16동 기준. 서울 426동 확장 시 재계산 필요 |
| **지하철 가중치 미흡 (R²=0.004)** | 동 행정중심 기준이라 경계 환승역 반영 불가. **Phase C polygon 거리 재계산 전엔 신뢰도 낮음** |
| **정적 점수** | 시설 변화 분기별 미미 → 시간 진화 시뮬레이션 부적합 |
| **TCN 피처와 중복 가능성** | bus_flpop, adstrd_flpop, fclty 카운트와 정보 중복 → SHAP 분석 시 collinearity 주의 |
| **0.10/0.40/0.50 가중치는 마포 매출 회귀 결과** | 다른 도메인(폐업률, 신생상권)에선 가중치 재 calibration 필요 |
| **R²=0.55** | 절반은 설명 못함. ABM의 1순위 신호 ❌, 보강 신호 ✅ |

---

## 4. 추천 우선순위

| # | 활용처 | ROI | 작업량 | 본인 영역? |
|---|---|---|---|---|
| 1 | **본인 ABM 출점 위치 가중치 (§1-2-A)** | 🔥 매우 높음 — 매출과 일관성 ↑, 비용 0 | 30~50줄 (archetype location_choice 수정) | ⚠️ A1·B2 공동 |
| 2 | **`abm_vs_grid_*.py` 검증 baseline 강화 (§1-3)** | 🔥 높음 — ABM 우위 입증 더 엄격 | 20~30줄 (grid weight) | ✅ **A1 단독 가능** |
| 3 | **SummaryTab 카드 1 보강 (§2-3)** | 🟡 중간 — frontend fallback 강화 | 1~2줄 | ❌ C1 |
| 4 | **TCN 매출 예측 35피처 확장 (§2-1)** | 🟡 중간 — 재학습 필요 | TCN 풀 재학습 | ⚠️ B2 |
| 5 | **추천 ranking 가중치 (§2-6)** | 🟡 중간 — district_rankings 강화 | 5~10줄 | ⚠️ B1 |
| 6 | closure_risk / emerging_district 피처 | 🟢 낮음 — 우선순위 낮은 노드들 | 별도 | ⚠️ B2 |

---

## 5. 결론

**본 ABM 작업에 적용 가치 큼** — 가중치 0.10/0.40/0.50이 마포 매출과 회귀 검증된 점이 결정적. ABM 결과의 매출 ground-truth와 일관성을 가질 수 있어 검증 신뢰도가 자연스레 ↑.

다른 영역에서도 6곳 이상 활용 가능하지만 **본인 영역 내에서 가장 빠르게 적용할 수 있는 것은 `abm_vs_grid_*.py`의 grid baseline 강화**다. 이게 본 PR(IM3-243)의 ABM 검증 작업과 자연스럽게 이어진다.

### 즉시 추천 액션

1. **단기 (이번 sprint 내)**: `abm_vs_grid_full_phase.py` 등에 op_fit grid baseline 추가 → ABM 우위 검증 강화
2. **중기 (다음 sprint)**: B2 협업으로 archetype location_choice 정책에 op_fit 가중치 주입
3. **장기**: TCN 35피처 재학습 + Phase C polygon 거리 재계산 후 가중치 재 calibration

---

## 6. 참고 자료

- 본 분석 대상 문서: [`docs/proposals/operational_fit_scorer.md`](./operational_fit_scorer.md)
- 학술 근거:
  - Hansen, W.G. (1959). _JAPA_ — Gravity accessibility 이론
  - McGrail & Humphreys (2009) — E2SFCA Gaussian decay
  - _Networks and Spatial Economics_ (Springer, 2025) — Hansen + ML 융합
  - 대한산업공학회지 (2024) — 공공데이터·XAI 상권 예측
- 본인 PR: https://github.com/Himidea-AI/Final_Project/pull/127 (IM3-243)
- 본 PR commit `9863189` ("ABM 시뮬레이션 sprint + 마포 인구 이동 분석") — `validation/abm_vs_grid_*.py` 4종
- ABM 메모리: `project_abm_hardcoded_evolution.md` (Policy 55 + Archetype 30종)
- TCN 비교 작업: [`docs/abm-simulation/tcn-imputed-comparison-report.md`](../abm-simulation/tcn-imputed-comparison-report.md)
- 관련 issue: [`docs/issues/2026-04-28-summary-tab-empty-cards.md`](../issues/2026-04-28-summary-tab-empty-cards.md) — `analysis_metrics.operational_fit_score` 가 응답에 정상 채워짐을 확인
