# 폐업 위험도 모델 D layer (threshold + top-K) — Design Spec

> **상태**: 브레인스토밍 완료, 사용자 승인 (2026-05-01).
> **작업 영역**: `models/closure_risk/` (B2 — 수지니 영역, A1 찬영 cross-team contribution).
> **선행 작업**: `2026-04-29-closure-risk-validation-fix-design.md` (E layer ✅), `2026-05-01-closure-risk-c-layer-label-fix-design.md` (C layer ✅).
> **Plan 단계**: 본 spec 통과 후 `writing-plans` skill 으로 implementation plan 작성.

## Goal

폐업 위험도 모델의 의사결정 layer 를 두 축으로 개선:
1. **Hard threshold (0.65/0.40) → val proba 기반 quantile threshold** 자동 fit. 학습 시 metrics.json 에 저장 → predict.py 가 동적 load.
2. **Top-K ranking API (`predict_topk`) 추가** — 다수 (dong×industry) 조합에서 위험도 상위 K% 추천. 호출자 (frontend, simulation) 의 "이 동네에서 가장 위험한 곳?" 직관적 use case 직접 지원.

## Background

C layer fix (2026-05-01, commit 7e2e2ab) 후 ensemble test AUC 0.5983 으로 의미 있는 신호 회복. 하지만 production 추론 단계의 threshold 는 여전히 hard-coded:

`models/closure_risk/predict.py:26-30`:
```python
RISK_LEVELS = [
    (0.65, "danger"),
    (0.40, "caution"),
    (0.00, "safe"),
]
```

문제:
- ensemble proba 분포가 `metrics.json` 기준 [0.15, 0.55] 에 좁게 갇혀 있음 (`metrics.json` n_per_bin: `[0, 43, 197, 214, 146, 20, 0, 0, 0, 0]`).
- proba >= 0.65 sample = **0건** — production 에서 "danger" 라벨 0건. threshold 작동 X.
- 0.65/0.40 의 학술 근거 없음 — 임의 설정.

또한:
- **현재 모델 AUC 0.60 수준** 이라 threshold 의 절대값보다 **순위 (ranking)** 가 더 유효한 정보.
- P@10 = 0.30 (random baseline 0.22 대비 1.36× 리프트) → top-K 추천이 binary 차단보다 실용적.
- 사용자 (창업주) 의사결정: "내 동네에서 위험한 가게 어디?" → top-K API 가 자연스러움.

본 spec 은 두 축 (threshold fit + top-K API) 을 함께 도입하여 D layer 의 "의사결정" 가치를 회복한다.

## Architecture

```
[학습]
train.py → evaluate → ensemble_val_proba 계산 → quantile fit
    ↓
metrics.json {
    ...,
    "thresholds": {
        "danger_quantile": 0.90, "caution_quantile": 0.70,
        "danger": <val_proba.quantile(0.90)>,
        "caution": <val_proba.quantile(0.70)>
    }
}

[추론 - 단일]
predict(dong, industry) → risk_score
    ↓ _classify(score)
    ↓ _load_risk_levels() ← lru_cache
    ↓ metrics.json 의 thresholds 동적 load (없으면 default fallback)
    → "danger" / "caution" / "safe"

[추론 - 배치 / Top-K]
predict_topk(targets: list[(dong, industry)], k_pct=10)
    ↓ for target in targets: predict(target)  # cache 재사용
    ↓ sort by risk_score DESC
    ↓ slice top max(1, n*k_pct/100)
    → list[dict] with rank
```

## Components

### 1. `predict.py` — `_load_risk_levels()` + `_classify` 동적화

```python
import json
from functools import lru_cache

@lru_cache(maxsize=1)
def _load_risk_levels() -> tuple[tuple[float, str], ...]:
    """metrics.json 에서 fit 된 quantile threshold load.

    metrics.json 미존재 / 손상 / thresholds 키 없음 → default fallback.

    Returns:
        ((danger_thr, "danger"), (caution_thr, "caution"), (0.0, "safe"))
    """
    metrics_path = WEIGHTS_DIR / "metrics.json"
    if metrics_path.exists():
        try:
            with open(metrics_path, encoding="utf-8") as f:
                m = json.load(f)
            t = m.get("thresholds", {})
            if "danger" in t and "caution" in t:
                return (
                    (float(t["danger"]), "danger"),
                    (float(t["caution"]), "caution"),
                    (0.0, "safe"),
                )
        except (json.JSONDecodeError, OSError, ValueError) as e:
            logger.warning("metrics.json threshold load 실패 — default fallback: %s", e)
    return ((0.65, "danger"), (0.40, "caution"), (0.00, "safe"))


def _classify(score: float) -> str:
    """위험도 점수 → 레벨. metrics.json 의 fit threshold 우선."""
    for threshold, level in _load_risk_levels():
        if score >= threshold:
            return level
    return "safe"
```

기존 `RISK_LEVELS` module-level 상수는 **유지** (회귀 호환 + 명시적 default 표시). `_classify` 만 동적 load 사용.

### 2. `predict.py` — `predict_topk()` 신규

```python
def predict_topk(
    targets: list[tuple[str, str]],
    k_pct: int = 10,
    config: dict | None = None,
) -> list[dict]:
    """다수 (dong, industry) 조합에서 위험도 top K% 추천.

    Args:
        targets: (dong_code, industry_code) tuple list. 빈 list 입력 → [] 반환.
        k_pct: 상위 K%. 1~100 범위. 100 초과 시 100 으로 clamp.
        config: db_url 등 override (predict() 의 config 와 동일).

    Returns:
        list[dict] — 각 dict 키:
            "dong_code": str,
            "industry_code": str,
            "risk_score": float | None,
            "risk_level": str,
            "rank": int (1부터 시작, top 이 1),
            "top_signals_lgbm": list[dict],
            "top_signals_tcn": list[dict],
            "summary_lgbm": list[str],
            "summary_tcn": list[str],
            "is_mock": bool,

        길이 = max(1, ceil(n_valid * k_pct / 100)) where n_valid = EXCLUDE_COMBOS 제외 후.

    Note:
        - EXCLUDE_COMBOS 의 target 은 자동 제외 (호출자가 알 필요 없음, log 만)
        - is_mock=True 인 결과 (모델 미학습 / 데이터 부족) 도 포함되되 risk_score=None
        - cache (`_load_models`) 재사용 — N=160 (마포 16동 × 10업종) 도 1회 model load
    """
```

### 3. `train.py` — threshold quantile fit + metrics.json 저장

`train()` 의 evaluate 직후, `metrics_summary` build 시 `thresholds` field 추가:

```python
# evaluate 직후, ensemble_val_proba 가 이미 계산된 상태
DANGER_Q = 0.90
CAUTION_Q = 0.70
thresholds = {
    "danger_quantile": DANGER_Q,
    "caution_quantile": CAUTION_Q,
    "danger": float(np.quantile(ensemble_val_proba, DANGER_Q)),
    "caution": float(np.quantile(ensemble_val_proba, CAUTION_Q)),
}
logger.info("threshold fit — danger>=%.4f (q%d), caution>=%.4f (q%d)",
            thresholds["danger"], int(DANGER_Q*100),
            thresholds["caution"], int(CAUTION_Q*100))

metrics_summary["thresholds"] = thresholds
```

### 4. `metrics.json` schema 확장

```json
{
  "split_strategy": "time",
  "train_quarters": [...], "val_quarters": [...], "test_quarters": [...],
  "ensemble_weights": {...},
  "lgbm": {...}, "tcn": {...}, "ensemble": {...},
  "thresholds": {
    "danger_quantile": 0.90,
    "caution_quantile": 0.70,
    "danger": 0.4523,
    "caution": 0.3145
  }
}
```

### 5. 회귀 호환성

- `models/interface.py:485` — `closure_risk_predict(dong, industry)` 단일 호출. signature 그대로 → 영향 X
- `tests/test_closure_risk_regression.py:test_predict_py_interface_unchanged` — `RISK_LEVELS` module-level 상수 (default 0.65/0.40) 그대로 유지 → assertion 통과
- `_classify` 동작 변화: metrics.json 미존재 시 동일 (default), 존재 시 fit threshold 사용. 기존 test 가 `_classify(0.7) == "danger"` 등을 단언하는데, fit threshold 가 0.45 정도로 낮아져도 0.7 >= 0.45 → "danger" 그대로 — **assertion 통과**.
  - **Edge case**: `_classify(0.5) == "caution"` 가 fit threshold 후 깨질 수 있음. fit `caution=0.31` 이면 0.5 >= 0.31 → "caution" 통과. fit `danger=0.45` 이면 0.5 >= 0.45 → **"danger"** 가 되어 깨짐.
  - **Mitigation**: regression test 를 `_load_risk_levels` lru_cache clear 후 `monkeypatch` 로 metrics.json 미존재 시뮬레이션 → default fallback → 회귀 보존.

## Data Flow

### 학습 (train.py)
1. 기존 pipeline (load → split → label → LGBM/TCN 학습 → ensemble 가중치)
2. evaluate 시 `ensemble_val_proba` 계산
3. `np.quantile(ensemble_val_proba, [0.70, 0.90])` → caution/danger threshold
4. `metrics_summary["thresholds"]` 추가
5. `save_metrics_and_plot` 으로 저장

### 추론 단일 (predict)
1. `predict(dong, industry)` 호출 (기존 signature)
2. risk_score 산출
3. `_classify(score)` → `_load_risk_levels()` 캐시 hit 또는 metrics.json 1회 load
4. fit threshold 적용 → "danger"/"caution"/"safe"

### 추론 배치 (predict_topk)
1. `predict_topk(targets, k_pct=10)` 호출
2. EXCLUDE_COMBOS 필터 → valid targets
3. 각 valid target 에 대해 `predict()` 반복 호출 (cache 재사용)
4. risk_score 내림차순 sort (None 인 것은 마지막)
5. top `max(1, ceil(n_valid * k_pct / 100))` slice
6. `rank` 부여 (1부터)
7. list[dict] 반환

## Error Handling

| case | 처리 |
|---|---|
| metrics.json 미존재 | `_load_risk_levels` default fallback ((0.65, "danger"), (0.40, "caution"), (0.00, "safe")). warning log X (정상 fallback) |
| metrics.json JSON parse 오류 | warning log + default fallback |
| metrics.json 에 thresholds 키 없음 | default fallback |
| `predict_topk(targets=[])` | `[]` 반환 (empty list) |
| `predict_topk(k_pct=0 / negative)` | `max(1, ...)` 보정으로 최소 1건 반환 |
| `predict_topk(k_pct>100)` | 100 으로 clamp (전체 반환) |
| EXCLUDE_COMBOS target | filter out + log info ("excluded N targets") |
| 일부 target 이 mock (모델 / 데이터 부족) | 결과에 포함, `risk_score=None`, `is_mock=True`. None 은 sort 시 마지막 |
| 모든 target 이 mock | 그대로 반환 (length = top K), 호출자에게 명시적 |

## Testing

### 신규 단위 test — `tests/test_closure_risk_topk.py` (~10 test)

**`_load_risk_levels` 관련 (3)**:
1. `test_load_risk_levels_from_metrics` — metrics.json 의 fit threshold 정확히 load
2. `test_load_risk_levels_fallback_on_missing` — metrics.json 미존재 → default
3. `test_load_risk_levels_fallback_on_corrupt` — JSON parse 실패 → default

**`_classify` dynamic (2)**:
4. `test_classify_uses_loaded_threshold` — fit threshold 적용 확인 (monkeypatch)
5. `test_classify_default_when_no_metrics` — metrics.json 미존재 시 0.65/0.40 default

**`predict_topk` 관련 (5)**:
6. `test_predict_topk_returns_top_k_pct` — len = ceil(n × k%/100)
7. `test_predict_topk_sorted_desc` — risk_score 내림차순
8. `test_predict_topk_empty_targets` — `[]` 입력 → `[]`
9. `test_predict_topk_excludes_excluded_combos` — EXCLUDE_COMBOS 필터
10. `test_predict_topk_handles_mock_results` — is_mock 결과 graceful handling + None sort

### 회귀 test 보강

`tests/test_closure_risk_regression.py:test_predict_py_interface_unchanged` 의 `_classify` 호출 시 `monkeypatch.setattr(predict_mod._load_risk_levels, "cache_clear")` 후 `monkeypatch` 로 WEIGHTS_DIR/metrics.json 가 default 만 사용되도록.

또는 더 간단하게: 별도 `test_classify_with_default_thresholds_works` 를 monkeypatch 로 추가.

### Production retrain

- `python -m models.closure_risk.train` → metrics.json 의 `thresholds` field 갱신 확인
- new threshold 값 record 회고

## Risks

| Risk | Mitigation |
|---|---|
| `_classify` 동적 threshold 가 회귀 test 깨뜨림 | metrics.json 미존재 / monkeypatch 로 default fallback 강제 → 회귀 통과 |
| `predict_topk` 가 N targets × DB 조회 → 느림 | `_load_models` cache 재사용. N=160 (마포 전체) 도 ~수십초. batch 최적화 (DB 쿼리 1회) 는 별도 spec |
| `_load_risk_levels` 가 lru_cache 로 stale (학습 후 metrics.json 갱신 시 인지 X) | 학습 → 추론은 별도 process. cache miss 시점에 read. process 내 갱신 시는 `_load_risk_levels.cache_clear()` 권장 (test에서 사용) |
| metrics.json 손상 시 silent fallback | warning log + default. 호출자가 metrics.json 의 `thresholds` 부재를 인지하려면 log 필수 |
| `predict_topk` 의 mock 결과를 top-K 에 포함할지 | 포함 (None sort 마지막) — 호출자가 `is_mock` 으로 필터 가능 |

## Out of Scope

- backend FastAPI endpoint (`/closure_risk/topk`) — 별도 spec
- frontend UI (위험 매장 추천 dashboard) — 별도 spec
- isotonic calibration / Platt scaling (D-3) — 별도 spec
- threshold 의 sensitivity 분석 (q90 vs q85 vs q95) — 학술 보강, 별도
- batch 추론 최적화 (DB 쿼리 1회 / multi-process predict_topk) — 성능 sprint, 별도
- ranking metric 추가 (NDCG, MAP) — evaluate.py 의 5 metric 외 추가, 별도 spec

## 참고 학술 자료

- Niculescu-Mizil & Caruana (2005) "Predicting good probabilities with supervised learning." — calibration 의 기초. 본 spec 은 calibration 까지 안 가지만 기반.
- Top-K decision 은 information retrieval / recommender system 표준 — 본 sprint 의 P@K, R@K metric 과 직접 매핑.
