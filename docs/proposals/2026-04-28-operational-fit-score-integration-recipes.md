# operational_fit_score — 6개 활용처별 상세 적용 레시피

**작성일:** 2026-04-28
**작성자:** A1 찬영
**전제:** [`2026-04-28-operational-fit-score-applicability.md`](./2026-04-28-operational-fit-score-applicability.md) 의 §2 활용 가능성 검토 결과를 바탕으로, **각 활용처별로 통합 지점·코드 스니펫·검증 방법·롤백 절차를 풀버전으로 정리**한 적용 가이드.

각 레시피는 Phase 1(MVP, 1~2시간) → Phase 2(검증, 반나절) → Phase 3(배포, 별도 sprint) 3단계로 구성. 단계별로 멈출 수 있어서 ROI가 안 나오면 Phase 1에서 즉시 폐기 가능.

---

## 공통 인프라

먼저 모든 활용처가 공유하는 op_fit score 접근 헬퍼를 만든다. 각 활용처별로 같은 코드를 반복하지 않도록.

### 공통 헬퍼 — `services/operational_fit_loader.py` 신규

**위치:** `backend/src/services/operational_fit_loader.py` (신규)

**역할:** 캐시된 op_fit 점수를 dict로 제공. 16동 × subway/bus/fclty/total 4개 점수.

```python
# backend/src/services/operational_fit_loader.py
"""op_fit_score 캐시 로더 — 모든 다운스트림 활용처 공유.

전제: services/operational_fit_scorer.py 가 이미 score 산출. 본 모듈은 그 결과를
dict 형태로 캐시 + 빠른 조회 인터페이스 제공.
"""
from __future__ import annotations
from functools import lru_cache
from typing import Literal

ScoreKind = Literal["total", "subway", "bus", "fclty"]


@lru_cache(maxsize=1)
def load_all_scores() -> dict[str, dict[str, float]]:
    """16동 × 4종 점수 dict.

    Returns
    -------
    {dong_code: {"total": 47.6, "subway": 30.1, "bus": 52.4, "fclty": 51.8}}
    """
    from src.services.operational_fit_scorer import compute_scores
    return compute_scores()


def get_score(dong_code: str, kind: ScoreKind = "total") -> float | None:
    """단일 동의 단일 점수. None=조회 실패."""
    data = load_all_scores()
    return data.get(dong_code, {}).get(kind)


def get_all(kind: ScoreKind = "total") -> dict[str, float]:
    """16동 전체의 단일 점수 dict — softmax/normalization 입력용."""
    return {d: s.get(kind, 0.0) for d, s in load_all_scores().items()}
```

본 헬퍼가 모든 6개 활용처의 진입점. 각 활용처 코드는 `from src.services.operational_fit_loader import ...` 로 시작.

---

## 1. 🔥 TCN 매출 예측 입력 피처 (35번째 피처 추가)

### 1-A. 통합 지점

| 파일 | 라인 | 변경 |
|---|---|---|
| `models/lstm_forecast/data_prep.py` | 38-91 (`SALES_FEATURES` ~ `ALL_FEATURES`) | 새 카테고리 `OPFIT_FEATURES` 추가 |
| `models/lstm_forecast/data_prep.py` | `build_timeseries()` 내부 | op_fit dict join (동 단위 broadcast) |
| `models/tcn_forecast/train.py` | DEFAULT config | 영향 없음 (input_size 자동 인식) |
| `models/tcn_forecast/weights/` | 전체 | **재학습 필수** — 기존 34피처 가중치 무효화 |

### 1-B. 코드 변경

```python
# models/lstm_forecast/data_prep.py 추가
OPFIT_FEATURES = [
    "op_fit_total",   # 0.10·subway + 0.40·bus + 0.50·fclty (10~100)
    "op_fit_subway",  # 지하철 서브점수
    "op_fit_bus",     # 버스 서브점수
    "op_fit_fclty",   # 집객시설 서브점수
]
ALL_FEATURES = SALES_FEATURES + STORE_FEATURES + POP_FEATURES + RENT_FEATURES + EXTRA_FEATURES + GOLMOK_FEATURES + OPFIT_FEATURES
# input_size: 34 → 38
```

`build_timeseries()` 의 timeseries DataFrame 구성 직후 (대략 `models/lstm_forecast/data_prep.py:520` 근처):

```python
# op_fit broadcast — 동 단위 정적 점수라 모든 분기 row에 동일 값
from src.services.operational_fit_loader import load_all_scores
op_scores = load_all_scores()  # {dong_code: {total, subway, bus, fclty}}

for kind in ("total", "subway", "bus", "fclty"):
    df[f"op_fit_{kind}"] = df["dong_code"].map(
        lambda dc: op_scores.get(dc, {}).get(kind, 0.0)
    )
```

### 1-C. 가중치·hyperparameter 결정

- **scaling:** op_fit은 이미 10~100 정규화. MinMaxScaler가 다른 피처와 자동 정렬.
- **TCN dilation/kernel:** 기존 그대로 (dilations=[1,2], kernel=2).
- **input_size:** 자동 인식 (data_prep이 `X.shape[2]` 반환).

### 1-D. 검증 metric

| 비교 | 기대 |
|---|---|
| baseline 34피처 TCN-A MAPE | **16.26%** (기존) |
| 38피처 TCN-A2 MAPE (op_fit 추가) | **15% 이하** (1%p+ 개선) |
| SHAP feature_importance | op_fit_total 또는 op_fit_bus 가 top-10 안에 진입 |
| collinearity (VIF) | op_fit vs bus_flpop, adstrd_flpop 상관계수 < 0.7 |

### 1-E. 위험·롤백

- **collinearity 위험:** op_fit_bus가 bus_flpop과 90%+ 상관일 가능성 → 둘 중 하나만 사용. SHAP에서 둘 다 낮으면 op_fit_bus 제거.
- **재학습 시간:** Pretrain 30분~수시간 + Finetune 5~15분. 본인 plan(`docs/superpowers/plans/2026-04-25-tcn-imputed-vs-original-comparison.md`) 부록 E와 동일 절차.
- **롤백:** `OPFIT_FEATURES = []` 한 줄 비우면 즉시 34피처로 복원.

### 1-F. 단계별 적용

1. **Phase 1 (1시간):** `OPFIT_FEATURES` 추가 + data_prep.py join 코드 + `--save-suffix opfit_v1` finetune (마포만, 빠른 검증)
2. **Phase 2 (반나절):** Pretrain 재실행 + 백테스트 + SHAP feature_importance 비교
3. **Phase 3 (별도 sprint):** TCN-A/B 모두 38피처로 재학습, weights/finetuned_mapo_tcn_38f.pt 명명, model registry 등록

---

## 2. closure_risk 모델 피처 추가

### 2-A. 통합 지점

| 파일 | 변경 |
|---|---|
| `models/closure_risk/data_prep.py` | feature 매트릭스 빌드 시 op_fit 4개 컬럼 추가 |
| `models/closure_risk/train.py` | LightGBM + TCN 둘 다 영향 (피처 1~4개 추가) |
| `models/closure_risk/predict.py` | inference 입력에 op_fit 포함 |
| `models/closure_risk/weights/` | **재학습 필수** |

### 2-B. 코드 변경

```python
# models/closure_risk/data_prep.py 의 feature 빌드 함수
from src.services.operational_fit_loader import load_all_scores

def build_features(...):
    df = ...  # 기존 로직
    op_scores = load_all_scores()
    df["op_fit_total"] = df["dong_code"].map(lambda dc: op_scores.get(dc, {}).get("total", 0))
    # 또는 4개 모두 추가 (LightGBM은 collinearity에 강건)
    return df
```

### 2-C. 가중치·hyperparameter 결정

- **LightGBM:** `feature_fraction=0.8` 그대로. op_fit이 자동으로 importance 평가됨.
- **TCN classifier:** sigmoid head 그대로. input_size + 1~4.
- **stacking 가중치:** 기존 LightGBM:TCN = 0.5:0.5 그대로 시작 → 검증 후 재조정.

### 2-D. 검증 metric

| 지표 | 기대 |
|---|---|
| AUC | baseline 대비 +0.01 이상 |
| 마포 16동 별 폐업 예측 정확도 | 분포 평탄화 (특정 동에 집중되던 오차 분산) |
| LightGBM feature_importance | op_fit_fclty 가 top-15 안 (의료·교육 시설이 폐업률에 강한 신호) |

### 2-E. 위험·롤백

- 현재 응답에서 closure_risk가 `risk_score: null`로 fail 중 → **closure_risk 자체 fix가 선행되어야** op_fit 통합 의미 있음
- 우선순위: **closure_risk fail 진단·복구 → 그 후 op_fit 통합**
- 롤백: feature 컬럼 4개 drop, 재학습

### 2-F. 단계별 적용

1. **Phase 0:** closure_risk fail 원인 진단 (별도 ticket 필요)
2. **Phase 1:** closure_risk 정상 작동 후, op_fit_total 1피처만 추가 → AUC 비교
3. **Phase 2:** 4피처 모두 추가, hyperparameter sweep
4. **Phase 3:** 배포

---

## 3. Frontend Dashboard SummaryTab 카드 1 보강

### 3-A. 통합 지점

| 파일 | 라인 | 변경 |
|---|---|---|
| `frontend/src/components/SimulationResult/dashboard/tabs/SummaryTab.tsx` | 64~73 (카드 1 items 배열) | items에 `입지 적합도` 행 추가 |
| `frontend/src/types/index.ts` | `SimulationOutput` 또는 `AnalysisMetrics` interface | `operational_fit_score?: number` 명시 (이미 응답에 있음) |

### 3-B. 코드 변경

응답에 `analysis_metrics.operational_fit_score: 47.6` 이 이미 채워져 있으므로 frontend만 수정:

```typescript
// SummaryTab.tsx
const opFit = simResult.analysis_metrics?.operational_fit_score ?? null;

// 카드 1 items 배열에 1줄 추가
items={[
  { text: matchScore != null ? `브랜드 적합도 ${Math.round(matchScore)}` : '브랜드 적합도 —', highlight: ... },
  { text: compCount != null ? `500m 내 경쟁점 ${compCount}개` : '경쟁점 데이터 없음', highlight: ... },
  // ⬇ 신규
  { text: opFit != null ? `입지 적합도 ${Math.round(opFit)}점` : '입지 적합도 —',
    highlight: opFit != null && opFit >= 70 },
  ...
]}
```

### 3-C. 가중치·hyperparameter 결정

- highlight 임계: 70점 (16동 중 상위 30%)
- 색상: highlight true → emerald, false → stone

### 3-D. 검증 metric

UI 검증 — Storybook 또는 실제 페이지에서:
- op_fit 47.6 → "입지 적합도 48점" 표시
- op_fit null → "입지 적합도 —" 표시
- op_fit 75 → highlight emerald

### 3-E. 위험·롤백

- 카드 1이 "분석 대기" UNKNOWN 상태에서도 op_fit은 **독립적으로 표시 가능** → fallback 가치 큼
- 롤백: items 배열에서 1줄 제거

### 3-F. 단계별 적용

1. **Phase 1 (5분):** SummaryTab.tsx 1줄 추가 + 즉시 dev server에서 확인
2. **Phase 2:** "입지 적합도" 클릭 시 모달로 subway/bus/fclty 3종 분해 + 도식 (`operational_fit_scorer.md`의 표를 시각화)
3. **Phase 3:** ForecastTab/MarketTab 등 다른 탭에도 op_fit 카드 확장

---

## 4. emerging_district autoencoder 보강 (이상 상권 탐지 강화)

### 4-A. 통합 지점

| 파일 | 변경 |
|---|---|
| `models/emerging_district/data_prep.py` | autoencoder 입력 vector에 op_fit 추가 또는 anomaly post-filter로 op_fit 사용 |
| `models/emerging_district/predict.py` | anomaly_score를 op_fit으로 보정 |

### 4-B. 코드 변경 — 두 가지 전략

#### 전략 A. Autoencoder 입력 피처에 추가 (재학습 필요)
```python
# emerging_district/data_prep.py
features = [..., "op_fit_total"]  # 매출/유동인구/임대료 등에 1피처 추가
```
→ Autoencoder가 "정상 상권" 패턴을 op_fit과 함께 학습. anomaly_score가 입지 정상성을 반영.

#### 전략 B. Post-filter (재학습 불필요, **권장**)
```python
# emerging_district/predict.py 의 결과 후처리
from src.services.operational_fit_loader import get_score

def predict_emerging(dong_code, ...):
    raw = ...  # 기존 anomaly_score 산출
    op_fit = get_score(dong_code, "total") or 50.0

    # 입지 핸디캡 극복 상권 = "op_fit 낮은데 매출 anomaly 양수"
    # → 진짜 신생 상권 신호 강화
    if raw["anomaly_score"] > 0 and op_fit < 30:
        raw["signal"] = "emerging_strong"  # 입지 약점 극복
        raw["confidence"] *= 1.3
    elif raw["anomaly_score"] > 0 and op_fit > 70:
        raw["signal"] = "emerging_easy"  # 입지 좋아서 자연스러운 상승
        raw["confidence"] *= 0.9

    return raw
```

### 4-C. 가중치·hyperparameter 결정

- 임계: op_fit < 30 = 하위 25%, op_fit > 70 = 상위 30%
- confidence 보정: ±30% 이내

### 4-D. 검증 metric

- "emerging_strong" 신호 동들이 다음 분기 매출 실제로 상승했는지 (precision)
- 기존 anomaly 단독 vs op_fit 보정 anomaly 의 신생 상권 식별 정확도 비교

### 4-E. 위험·롤백

- 전략 B는 post-filter라 모델 재학습 없음 → 즉시 롤백 가능 (코드 6~10줄 제거)
- 전략 A는 autoencoder 재학습 필요 → 신중

### 4-F. 단계별 적용

1. **Phase 1 (1시간):** 전략 B 적용 + 마포 16동 backtest
2. **Phase 2:** 전략 A로 autoencoder 재학습 비교
3. **Phase 3:** 더 좋은 쪽 채택

---

## 5. 정책 시뮬레이션 (가상 시나리오 효과 측정)

### 5-A. 통합 지점

| 파일 | 변경 |
|---|---|
| `backend/src/services/operational_fit_scorer.py` | `recompute_with_scenario(...)` 함수 추가 (기존 scorer는 보존) |
| `backend/src/api/scenarios.py` (신규) | REST endpoint `/api/scenarios/op_fit_simulate` |
| 또는 `validation/policy_simulator.py` (신규) | 오프라인 batch 시뮬레이터 |

### 5-B. 코드 변경

```python
# backend/src/services/operational_fit_scorer.py 추가
def recompute_with_scenario(
    scenario: dict,
    base_dong: str | None = None,
) -> dict[str, dict[str, float]]:
    """가상 시나리오 적용 후 16동 op_fit 재산출.

    Parameters
    ----------
    scenario : dict
        {
          "type": "new_subway_station" | "new_bus_route" | "new_fclty",
          "dong_code": "11440680",
          "params": {
            "station_distance_m": 200,    # type="new_subway_station"
            "facility_type": "univ",      # type="new_fclty"
            "facility_count": 1,
            ...
          }
        }

    Returns
    -------
    재산출된 16동 점수 dict (기존 load_all_scores 와 같은 형태)
    """
    if scenario["type"] == "new_subway_station":
        # G(d, d₀) 재계산: d 가 station_distance_m 으로 줄어듦
        ...
    elif scenario["type"] == "new_fclty":
        # 시설 카운트 증가 → fclty 서브점수 재산출
        ...
    return new_scores
```

### 5-C. ABM 정책 시뮬레이션 결합

```python
# 가상: 공덕동에 신규 지하철역 신설 시뮬레이션
from src.services.operational_fit_scorer import recompute_with_scenario
from validation.abm_vs_grid_full_phase import run_abm_simulation

scenario = {
    "type": "new_subway_station",
    "dong_code": "11440565",  # 공덕동
    "params": {"station_distance_m": 100}
}
new_scores = recompute_with_scenario(scenario)

# ABM 에이전트의 출점 위치 가중치를 new_scores 로 갈아끼우고 재시뮬레이션
abm_result_new = run_abm_simulation(op_fit_scores=new_scores, ...)
abm_result_baseline = run_abm_simulation(op_fit_scores=load_all_scores(), ...)

revenue_uplift = abm_result_new["mean_revenue"] - abm_result_baseline["mean_revenue"]
print(f"공덕동 신규역 효과: 매출 +{revenue_uplift:,.0f}원")
```

### 5-D. 가중치·hyperparameter 결정

- E2SFCA `d₀` (catchment 반경) 기존 1,000m 그대로
- 시설 가중치 14종 기존 그대로 (op_fit_scorer 정의)
- ABM 시드: 30개 (안정성)

### 5-E. 검증 metric

- 시나리오 적용 전후 매출 변화량의 ABM seed-to-seed 분산
- 분산이 예측 변화량보다 작아야 의미 있는 결과

### 5-F. 단계별 적용

1. **Phase 1 (반나절):** `recompute_with_scenario` 1개 시나리오(new_subway)만 구현 + ABM batch 검증
2. **Phase 2:** 4종 시나리오 (new_subway, new_bus, new_univ, new_hosp) 추가
3. **Phase 3:** REST endpoint 노출 + frontend "what-if 시뮬레이터" UI

---

## 6. 추천 시스템 — district_rankings 가중치

### 6-A. 통합 지점

| 파일 | 변경 |
|---|---|
| `backend/src/agents/nodes/district_ranking.py` | 최종 score 계산 시 op_fit 가중치 결합 |
| `backend/src/schemas/simulation_output.py` | `district_rankings[].score_components` 필드 추가 (해석성) |

### 6-B. 코드 변경

```python
# backend/src/agents/nodes/district_ranking.py
from src.services.operational_fit_loader import get_all

def rank_districts(...):
    scores = {}
    op_fit_all = get_all("total")  # {dong: total_score}

    for dong in candidate_dongs:
        revenue_score = ...   # TCN 매출 예측 정규화 (0~100)
        rent_score = ...      # 임대료 역수 정규화 (0~100)
        op_fit_score = op_fit_all.get(dong, 50.0)

        # 가중합 — 가중치는 PR 별 hyperparameter
        final_score = (
            0.50 * revenue_score
            + 0.20 * rent_score
            + 0.30 * op_fit_score
        )
        scores[dong] = {
            "final_score": final_score,
            "components": {
                "revenue": revenue_score,
                "rent": rent_score,
                "op_fit": op_fit_score,
            }
        }
    return sorted(scores.items(), key=lambda x: -x[1]["final_score"])
```

응답 예:
```json
"district_rankings": [
  {
    "district": "공덕동",
    "score": 67.3,
    "score_components": {
      "revenue": 78.0,
      "rent": 45.0,
      "op_fit": 47.6
    }
  }
]
```

→ frontend가 점수 분해를 시각화 가능 (레이더 차트 등).

### 6-C. 가중치 결정

| 가중치 | 근거 |
|---|---|
| revenue 0.50 | 매출 직접 예측이 가장 신뢰도 높음 (TCN MAPE ~15%) |
| op_fit 0.30 | R²=0.55, 매출 미반영 입지 신호 |
| rent 0.20 | 비용 측면 보완 |

다른 가중치 조합 가능 (sweep 권장).

### 6-D. 검증 metric

- 추천된 1순위 동의 백테스트 매출 vs 5순위 동의 매출 차이 (separability)
- A/B test: 기존 ranking vs op_fit 결합 ranking 사용자 클릭률/만족도

### 6-E. 위험·롤백

- 매출 성장 마이너스인 동(공덕 -17%)이 op_fit으로 부풀려질 수 있음
- 롤백: 가중치 0.50/0.50/0 (op_fit 제거)

### 6-F. 단계별 적용

1. **Phase 1 (2시간):** 가중치 0.50/0.20/0.30 하드코딩 + 응답에 score_components 추가
2. **Phase 2:** 가중치 sweep — A/B로 4가지 조합 비교
3. **Phase 3:** 사용자 행동 로그 기반 가중치 자동 학습

---

## 부록 A — op_fit 적용 시 공통 검증 체크리스트

각 활용처 적용 후 다음 5가지를 모두 확인:

- [ ] **회귀 테스트**: 기존 동작 (op_fit 미적용 케이스) 100% 호환
- [ ] **null safety**: op_fit dict가 비어 있을 때 (`get(...) or default`) 기본값 적용
- [ ] **caching 정합성**: `lru_cache(maxsize=1)` 가 process 간 공유 안 되므로 multi-worker 환경 주의
- [ ] **단위 테스트**: 16동 모두 점수 조회 가능, 17번째 동(서울 다른 구) 조회 시 None 반환
- [ ] **SHAP/feature importance**: op_fit이 의미있는 위치에 들어왔는지 (top-20 안)

## 부록 B — 통합 의사결정 매트릭스

| 활용처 | 작업량 | 재학습 | ROI | 본인 영역 | 우선순위 |
|---|---|---|---|---|---|
| 1. TCN 35피처 | 30~50줄 + 재학습 | ✅ TCN 풀 재학습 | 🔥 높음 | ❌ B2 | 4 |
| 2. closure_risk | 10~20줄 + 재학습 | ✅ LightGBM+TCN 재학습 | 🟡 중간 | ❌ B2 | 6 |
| 3. SummaryTab 카드 | 1~5줄 | ❌ | 🟡 중간 | ❌ C1 | 3 |
| 4. emerging post-filter | 10~20줄 | ❌ (전략 B) | 🟢 낮음 | ❌ B2 | 5 |
| 5. 정책 시뮬레이터 | 100~200줄 | ❌ | 🔥 높음 (신규 가치) | ⚠️ A1·B2 | 2 |
| 6. district_rankings | 20~30줄 | ❌ | 🟡 중간 | ❌ B1 | 1 |

## 부록 C — 본인(A1) 영역에서 직접 진행 가능 작업

위 6개 중 본인 영역에서 단독 진행 가능한 것은 없음. 그러나:

1. **공통 헬퍼 (`services/operational_fit_loader.py`)**: ✅ A1 영역(`backend/src/services/`) — 본인 단독 진행 가능. 모든 활용처가 이걸 import 하므로 **선행 작업으로 가장 높은 ROI**.
2. **정책 시뮬레이터 (#5)**: ⚠️ A1·B2 공동 — `backend/src/services/`에 `recompute_with_scenario` 추가 후 B2의 ABM 호출 결합.
3. **`abm_vs_grid_*.py` baseline 강화** (활용처 평가 §1-3): ✅ A1 단독 — 별도 문서 §4-1 이미 명시.

→ **즉시 추천: 공통 헬퍼 모듈 작성 (Phase 1, 1~2시간)**. 그 후 다른 영역 동료들이 import해서 사용.

---

## 7. 참고 자료

- [평가 본문](./2026-04-28-operational-fit-score-applicability.md)
- [op_fit 산출 공식 원본](./operational_fit_scorer.md)
- [관련 issue: SummaryTab 빈 카드](../issues/2026-04-28-summary-tab-empty-cards.md)
- [TCN 비교 plan (재학습 절차)](../superpowers/plans/2026-04-25-tcn-imputed-vs-original-comparison.md)
- 본 PR: https://github.com/Himidea-AI/Final_Project/pull/127
