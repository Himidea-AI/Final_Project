# 폐업 위험도 모델 D layer (threshold + top-K) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hard threshold (0.65/0.40) → val proba quantile fit + 새 `predict_topk()` API 추가. metrics.json 에 fit 된 threshold 저장 → predict.py 가 동적 load.

**Architecture:** `train.py` 가 학습 후 ensemble val proba 의 q90/q70 quantile 을 metrics.json `thresholds` 키에 저장. `predict.py` 의 `_classify` 가 `_load_risk_levels()` (lru_cache) 로 동적 load. 새 `predict_topk(targets, k_pct)` 함수가 다수 (dong, industry) 조합에서 top K% 추천.

**Tech Stack:** Python, NumPy quantile, json, functools.lru_cache, pytest, LightGBM, PyTorch (기존).

**선행 spec:** `docs/superpowers/specs/2026-05-01-closure-risk-d-layer-threshold-topk-design.md`

---

## File Structure

| 파일 | 변경 유형 |
|---|---|
| `models/closure_risk/predict.py` | Modify (`_load_risk_levels` 신규, `_classify` 동적화, `predict_topk` 신규) |
| `models/closure_risk/train.py` | Modify (threshold quantile fit + metrics_summary 추가) |
| `tests/test_closure_risk_topk.py` | Create (~10 신규 unit test) |
| `tests/test_closure_risk_regression.py` | Modify (default fallback 보강 1 test) |
| `models/closure_risk/weights/metrics.json` | Update (production retrain) |
| `models/closure_risk/weights/calibration_curve.png` | Update (production retrain) |
| `models/closure_risk/weights/closure_risk_lgbm.pkl` | Update (production retrain) |
| `models/closure_risk/weights/closure_risk_tcn_scaler.pkl` | Update (production retrain) |
| `models/closure_risk/weights/ensemble_weights.pkl` | Update (production retrain) |
| `docs/retrospective/2026-05-01-d-layer.md` | Create (D layer 회고, C layer 회고와 별도) |

---

## Task 1: `_load_risk_levels` + `_classify` 동적화 + 5 test

**Files:**
- Modify: `models/closure_risk/predict.py` (top of file, helpers)
- Test: `tests/test_closure_risk_topk.py` (신규)

- [ ] **Step 1: 신규 test 파일 생성 + 5 test 작성**

Create `tests/test_closure_risk_topk.py`:

```python
"""D layer (threshold + top-K) unit test."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def clear_risk_levels_cache():
    """`_load_risk_levels` lru_cache clear — test 격리."""
    from models.closure_risk import predict as predict_mod
    predict_mod._load_risk_levels.cache_clear()
    yield
    predict_mod._load_risk_levels.cache_clear()


def test_load_risk_levels_from_metrics(tmp_path, monkeypatch, clear_risk_levels_cache):
    """metrics.json 의 fit threshold 정확히 load."""
    from models.closure_risk import predict as predict_mod

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps({
            "thresholds": {"danger": 0.4523, "caution": 0.3145,
                           "danger_quantile": 0.90, "caution_quantile": 0.70}
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(predict_mod, "WEIGHTS_DIR", tmp_path)

    levels = predict_mod._load_risk_levels()
    assert levels[0] == (0.4523, "danger")
    assert levels[1] == (0.3145, "caution")
    assert levels[2] == (0.0, "safe")


def test_load_risk_levels_fallback_on_missing(tmp_path, monkeypatch, clear_risk_levels_cache):
    """metrics.json 미존재 → default fallback."""
    from models.closure_risk import predict as predict_mod
    monkeypatch.setattr(predict_mod, "WEIGHTS_DIR", tmp_path)

    levels = predict_mod._load_risk_levels()
    assert levels == ((0.65, "danger"), (0.40, "caution"), (0.0, "safe"))


def test_load_risk_levels_fallback_on_corrupt(tmp_path, monkeypatch, clear_risk_levels_cache):
    """JSON parse 실패 → default fallback."""
    from models.closure_risk import predict as predict_mod

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(predict_mod, "WEIGHTS_DIR", tmp_path)

    levels = predict_mod._load_risk_levels()
    assert levels == ((0.65, "danger"), (0.40, "caution"), (0.0, "safe"))


def test_classify_uses_loaded_threshold(tmp_path, monkeypatch, clear_risk_levels_cache):
    """fit threshold 적용 확인."""
    from models.closure_risk import predict as predict_mod

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps({"thresholds": {"danger": 0.45, "caution": 0.30,
                                    "danger_quantile": 0.90, "caution_quantile": 0.70}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(predict_mod, "WEIGHTS_DIR", tmp_path)

    assert predict_mod._classify(0.50) == "danger"   # >= 0.45
    assert predict_mod._classify(0.40) == "caution"  # 0.30~0.45
    assert predict_mod._classify(0.20) == "safe"     # < 0.30


def test_classify_default_when_no_metrics(tmp_path, monkeypatch, clear_risk_levels_cache):
    """metrics.json 미존재 시 default 0.65/0.40 사용."""
    from models.closure_risk import predict as predict_mod
    monkeypatch.setattr(predict_mod, "WEIGHTS_DIR", tmp_path)

    assert predict_mod._classify(0.7) == "danger"
    assert predict_mod._classify(0.5) == "caution"
    assert predict_mod._classify(0.1) == "safe"
```

- [ ] **Step 2: test fail 확인**

Run: `python -m pytest tests/test_closure_risk_topk.py::test_load_risk_levels_from_metrics tests/test_closure_risk_topk.py::test_load_risk_levels_fallback_on_missing -v`
Expected: FAIL — `_load_risk_levels` 미존재 (`AttributeError`).

- [ ] **Step 3: predict.py 에 `_load_risk_levels` 추가 + `_classify` 동적화**

Open `models/closure_risk/predict.py`. 

Top imports 에 추가 (line 1~20 부근):
```python
import json
from functools import lru_cache
```
(이미 있으면 skip)

`RISK_LEVELS` 상수 (line 26-30) 그대로 유지. 그 직후 (line 31 부근) 에 helper 추가:

```python
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
    return ((0.65, "danger"), (0.40, "caution"), (0.0, "safe"))
```

기존 `_classify` (line 33-37) 를 다음으로 교체:
```python
def _classify(score: float) -> str:
    """위험도 점수 → 레벨. metrics.json fit threshold 우선."""
    for threshold, level in _load_risk_levels():
        if score >= threshold:
            return level
    return "safe"
```

- [ ] **Step 4: test 통과 확인**

Run: `python -m pytest tests/test_closure_risk_topk.py -v`
Expected: 5 passed.

- [ ] **Step 5: 회귀 test 통과 확인**

Run: `python -m pytest tests/test_closure_risk_regression.py -v`
Expected: 4 passed (현재 metrics.json 에 thresholds 키 미존재 → default fallback → `_classify(0.7)=="danger"`, `_classify(0.5)=="caution"`, `_classify(0.1)=="safe"` 그대로 통과).

만약 회귀 fail 시: 현재 metrics.json 의 thresholds 키 부재 확인 + default fallback 정상 작동 확인.

- [ ] **Step 6: ruff + commit**

```bash
ruff check --fix models/closure_risk/predict.py tests/test_closure_risk_topk.py
ruff format models/closure_risk/predict.py tests/test_closure_risk_topk.py
git add models/closure_risk/predict.py tests/test_closure_risk_topk.py
git commit -m "$(cat <<'EOF'
feat(closure_risk): _load_risk_levels + _classify 동적 threshold (D layer T1)

metrics.json 의 thresholds 키 (danger/caution quantile fit) 를 lru_cache 로
1회 load. 미존재/손상 시 default (0.65/0.40) fallback. _classify 가 동적
threshold 사용 — 학습 시 fit 된 quantile 자동 적용.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `train.py` threshold quantile fit + metrics_summary 추가

**Files:**
- Modify: `models/closure_risk/train.py` (`train()` 의 evaluate 단계)

- [ ] **Step 1: 회귀 test 추가 (metrics.json 에 thresholds 키 존재 검증)**

Append to `tests/test_closure_risk_topk.py`:

```python
def test_train_writes_thresholds_to_metrics(monkeypatch, tmp_path):
    """train() 실행 후 metrics.json 의 thresholds field 가 생성되어야 함.

    DB 호출 없는 sanity test — 실제 retrain 은 T4 에서.
    여기서는 이미 존재하는 weights/metrics.json 의 thresholds field 만 검증.
    """
    from models.closure_risk.model import WEIGHTS_DIR

    metrics_path = WEIGHTS_DIR / "metrics.json"
    if not metrics_path.exists():
        pytest.skip("metrics.json 미존재 — production retrain 후 검증 가능")

    with open(metrics_path, encoding="utf-8") as f:
        m = json.load(f)

    # T2 commit 후 production retrain (T4) 실행 시 thresholds 가 채워짐
    # 본 test 는 retrain 후에만 의미 있음 (skip 가능)
    if "thresholds" not in m:
        pytest.skip("thresholds key 미존재 — T4 retrain 후 검증 가능")

    t = m["thresholds"]
    assert "danger" in t and "caution" in t
    assert 0.0 <= t["caution"] <= t["danger"] <= 1.0
    assert t["danger_quantile"] >= t["caution_quantile"]
```

- [ ] **Step 2: train.py 의 evaluate 단계에 threshold fit 추가**

Open `models/closure_risk/train.py`. evaluate 단계 — `metrics_summary` build 직전 (즉, `metrics_summary = {...}` 전) 에 threshold fit 코드 추가:

```python
# threshold fit (val proba 의 quantile)
import numpy as np  # 이미 import 되어 있음
DANGER_Q = 0.90
CAUTION_Q = 0.70
if len(ensemble_val_proba) > 0:
    thresholds = {
        "danger_quantile": DANGER_Q,
        "caution_quantile": CAUTION_Q,
        "danger": float(np.quantile(ensemble_val_proba, DANGER_Q)),
        "caution": float(np.quantile(ensemble_val_proba, CAUTION_Q)),
    }
    logger.info(
        "threshold fit — danger>=%.4f (q%d), caution>=%.4f (q%d)",
        thresholds["danger"], int(DANGER_Q * 100),
        thresholds["caution"], int(CAUTION_Q * 100),
    )
else:
    thresholds = {
        "danger_quantile": DANGER_Q, "caution_quantile": CAUTION_Q,
        "danger": 0.65, "caution": 0.40,
    }
    logger.warning("ensemble_val_proba 비어있음 — default threshold 0.65/0.40 fallback")
```

`metrics_summary = {...}` dict 안에 `"thresholds": thresholds,` field 추가.

- [ ] **Step 3: train.py 가 import 가능한지 sanity check**

Run: `python -c "from models.closure_risk.train import train, DEFAULT_CONFIG; print('OK')"`
Expected: prints "OK".

- [ ] **Step 4: ruff + commit**

```bash
ruff check --fix models/closure_risk/train.py tests/test_closure_risk_topk.py
ruff format models/closure_risk/train.py tests/test_closure_risk_topk.py
git add models/closure_risk/train.py tests/test_closure_risk_topk.py
git commit -m "$(cat <<'EOF'
feat(closure_risk): train.py threshold quantile fit (D layer T2)

ensemble val proba 의 q90/q70 quantile 을 metrics.json 의 thresholds 키에
저장. predict.py 의 _load_risk_levels 가 자동 load 하여 production 추론에서
fit 된 threshold 사용. ensemble_val_proba 비어있는 edge case 는 default
fallback.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `predict_topk()` 함수 + 5 test

**Files:**
- Modify: `models/closure_risk/predict.py` (`predict_topk` 신규)
- Test: `tests/test_closure_risk_topk.py` (5 신규 test)

- [ ] **Step 1: 5 신규 test 추가**

Append to `tests/test_closure_risk_topk.py`:

```python
def test_predict_topk_returns_top_k_pct(monkeypatch):
    """len = ceil(n × k_pct / 100). EXCLUDE_COMBOS 제외 후 카운트."""
    from models.closure_risk import predict as predict_mod

    # predict() 를 mock — 결정적 risk_score 반환
    def fake_predict(dong, industry, config=None):
        score = 0.1 + (int(dong[-3:]) % 10) * 0.05  # 0.1~0.55 분포
        return {
            "risk_score": score, "risk_level": "safe",
            "top_signals_lgbm": [], "summary_lgbm": [],
            "top_signals_tcn": [], "summary_tcn": [],
            "model": "test", "is_mock": False,
        }

    monkeypatch.setattr(predict_mod, "predict", fake_predict)
    # EXCLUDE_COMBOS 비우기 (test 격리)
    monkeypatch.setattr(predict_mod, "EXCLUDE_COMBOS", set())

    targets = [(f"114403{i:02d}", "CS100001") for i in range(20)]
    result = predict_mod.predict_topk(targets, k_pct=10)

    assert len(result) == max(1, int(20 * 10 / 100))   # = 2
    assert all("rank" in r for r in result)
    assert result[0]["rank"] == 1


def test_predict_topk_sorted_desc(monkeypatch):
    """risk_score 내림차순 정렬."""
    from models.closure_risk import predict as predict_mod

    scores_map = {
        ("d1", "i1"): 0.5,
        ("d2", "i1"): 0.2,
        ("d3", "i1"): 0.8,
        ("d4", "i1"): 0.1,
    }

    def fake_predict(dong, industry, config=None):
        return {
            "risk_score": scores_map[(dong, industry)], "risk_level": "safe",
            "top_signals_lgbm": [], "summary_lgbm": [],
            "top_signals_tcn": [], "summary_tcn": [],
            "model": "test", "is_mock": False,
        }

    monkeypatch.setattr(predict_mod, "predict", fake_predict)
    monkeypatch.setattr(predict_mod, "EXCLUDE_COMBOS", set())

    targets = list(scores_map.keys())
    result = predict_mod.predict_topk(targets, k_pct=100)  # 전체 반환

    scores = [r["risk_score"] for r in result]
    assert scores == sorted(scores, reverse=True)


def test_predict_topk_empty_targets():
    """빈 list 입력 → 빈 list 반환."""
    from models.closure_risk import predict as predict_mod
    assert predict_mod.predict_topk([], k_pct=10) == []


def test_predict_topk_excludes_excluded_combos(monkeypatch):
    """EXCLUDE_COMBOS 의 target 자동 필터."""
    from models.closure_risk import predict as predict_mod

    def fake_predict(dong, industry, config=None):
        return {
            "risk_score": 0.5, "risk_level": "caution",
            "top_signals_lgbm": [], "summary_lgbm": [],
            "top_signals_tcn": [], "summary_tcn": [],
            "model": "test", "is_mock": False,
        }

    monkeypatch.setattr(predict_mod, "predict", fake_predict)
    monkeypatch.setattr(predict_mod, "EXCLUDE_COMBOS", {("d_excluded", "i_excluded")})

    targets = [("d_excluded", "i_excluded"), ("d1", "i1"), ("d2", "i1")]
    result = predict_mod.predict_topk(targets, k_pct=100)

    excluded = [(r["dong_code"], r["industry_code"]) for r in result
                if (r["dong_code"], r["industry_code"]) == ("d_excluded", "i_excluded")]
    assert len(excluded) == 0
    assert len(result) == 2  # excluded 제거 후 2개


def test_predict_topk_handles_mock_results(monkeypatch):
    """is_mock=True 결과의 risk_score=None 도 graceful (sort 시 마지막)."""
    from models.closure_risk import predict as predict_mod

    def fake_predict(dong, industry, config=None):
        if dong == "d_mock":
            return {
                "risk_score": None, "risk_level": "unknown",
                "top_signals_lgbm": [], "summary_lgbm": [],
                "top_signals_tcn": [], "summary_tcn": [],
                "model": "test", "is_mock": True,
            }
        return {
            "risk_score": 0.5, "risk_level": "caution",
            "top_signals_lgbm": [], "summary_lgbm": [],
            "top_signals_tcn": [], "summary_tcn": [],
            "model": "test", "is_mock": False,
        }

    monkeypatch.setattr(predict_mod, "predict", fake_predict)
    monkeypatch.setattr(predict_mod, "EXCLUDE_COMBOS", set())

    targets = [("d_mock", "i1"), ("d1", "i1"), ("d2", "i1")]
    result = predict_mod.predict_topk(targets, k_pct=100)

    # mock 결과는 마지막
    assert result[-1]["is_mock"] is True
    assert result[-1]["risk_score"] is None
```

- [ ] **Step 2: test fail 확인**

Run: `python -m pytest tests/test_closure_risk_topk.py -v`
Expected: 5 새 test FAIL — `predict_topk` 미존재 (`AttributeError`).

- [ ] **Step 3: predict.py 에 `predict_topk` 추가**

Open `models/closure_risk/predict.py`. 파일 끝 (마지막 함수 `_mock_result` 뒤) 에 추가:

```python
import math


def predict_topk(
    targets: list[tuple[str, str]],
    k_pct: int = 10,
    config: dict | None = None,
) -> list[dict]:
    """다수 (dong, industry) 조합에서 위험도 top K% 추천.

    Args:
        targets: (dong_code, industry_code) tuple list. EXCLUDE_COMBOS 자동 제외.
        k_pct: 상위 K% (1~100). 1 미만 → 1, 100 초과 → 100 으로 clamp.
        config: db_url 등 override.

    Returns:
        list[dict] — 각 dict 키:
            "dong_code", "industry_code", "risk_score" (float|None),
            "risk_level", "rank" (int, top=1),
            "top_signals_lgbm", "top_signals_tcn",
            "summary_lgbm", "summary_tcn", "is_mock"

        길이 = max(1, ceil(n_valid * k_pct / 100)).
        risk_score=None (is_mock=True) 결과는 sort 시 마지막.
    """
    if not targets:
        return []

    k_pct = max(1, min(100, k_pct))

    # EXCLUDE_COMBOS 필터
    valid = [(d, i) for (d, i) in targets if (d, i) not in EXCLUDE_COMBOS]
    excluded_n = len(targets) - len(valid)
    if excluded_n > 0:
        logger.info("predict_topk: EXCLUDE_COMBOS %d targets 제외", excluded_n)

    if not valid:
        return []

    results = []
    for dong, industry in valid:
        try:
            res = predict(dong, industry, config=config)
        except ExcludedComboError:
            continue
        results.append({"dong_code": dong, "industry_code": industry, **res})

    # sort: risk_score DESC, None 은 마지막
    def _sort_key(r):
        score = r.get("risk_score")
        return (1 if score is None else 0, -(score if score is not None else 0))

    results.sort(key=_sort_key)

    n = len(results)
    k = max(1, math.ceil(n * k_pct / 100))
    top = results[:k]

    for i, r in enumerate(top, start=1):
        r["rank"] = i

    return top
```

- [ ] **Step 4: test 통과 확인**

Run: `python -m pytest tests/test_closure_risk_topk.py -v`
Expected: 10 passed (T1: 5, T3: 5).

- [ ] **Step 5: 전체 closure_risk regression 통과**

Run: `python -m pytest tests/test_closure_risk_*.py -v`
Expected: ~34 passed (label 6 + split 6 + metrics 8 + regression 4 + topk 10).

- [ ] **Step 6: ruff + commit**

```bash
ruff check --fix models/closure_risk/predict.py tests/test_closure_risk_topk.py
ruff format models/closure_risk/predict.py tests/test_closure_risk_topk.py
git add models/closure_risk/predict.py tests/test_closure_risk_topk.py
git commit -m "$(cat <<'EOF'
feat(closure_risk): predict_topk 다수 (dong, industry) top-K 추천 (D layer T3)

다수 (dong_code, industry_code) tuple 입력 → EXCLUDE_COMBOS 필터 → 각 target
predict() 호출 (cache 재사용) → risk_score 내림차순 sort → top K% slice +
rank 부여. is_mock=True 결과는 None sort 마지막.

호출자 (frontend, simulation) 의 'top-K 위험 매장 추천' use case 직접 지원.
P@K metric 과 직접 매핑.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Production retrain + threshold 갱신 검증

**Files:**
- Update (실행 산출물): `models/closure_risk/weights/*`

- [ ] **Step 1: production retrain**

```bash
cd "/c/Users/804/Documents/final project"
python -m models.closure_risk.train 2>&1 | tee /tmp/closure_risk_retrain_d.log
```

Expected:
- 기존 retrain log + 새로 "threshold fit — danger>=X.XXXX (q90), caution>=X.XXXX (q70)" log 출력
- metrics.json 갱신 — `thresholds` key 에 fit 값 기록

소요시간: ~2분.

- [ ] **Step 2: metrics.json 의 thresholds 검증**

```bash
python -c "
import json
with open('models/closure_risk/weights/metrics.json') as f:
    m = json.load(f)
t = m.get('thresholds', {})
print('danger:', t.get('danger'))
print('caution:', t.get('caution'))
print('danger_q:', t.get('danger_quantile'))
print('caution_q:', t.get('caution_quantile'))
assert 'danger' in t and 'caution' in t
assert t['caution'] < t['danger'] <= 1.0
print('OK')
"
```

Expected:
- danger 0.4~0.6 범위 (val_proba.quantile(0.90), 현재 분포 기준)
- caution 0.3~0.4 범위
- danger_q=0.9, caution_q=0.7

- [ ] **Step 3: predict.py 의 동적 threshold 적용 확인**

```bash
python -c "
from models.closure_risk import predict as p
p._load_risk_levels.cache_clear()
levels = p._load_risk_levels()
print('Loaded levels:', levels)
assert levels[0][0] != 0.65, '여전히 default — fit threshold load 실패'
print('OK — fit threshold 적용')
"
```

Expected: levels[0] 이 (0.65, "danger") 가 아닌 fit 된 값.

- [ ] **Step 4: regression test 재실행**

Run: `python -m pytest tests/test_closure_risk_regression.py -v`
Expected: 4 passed. **단, `test_predict_py_interface_unchanged` 의 `_classify(0.5) == "caution"` assertion 이 fit threshold 적용 후 깨질 수 있음.**

만약 깨지면: `_load_risk_levels.cache_clear()` 후 `monkeypatch` 로 metrics.json 미존재 시뮬레이션 → 추후 T5 commit 시 회귀 보강 필요. T4 step 에서는 일단 fail 시 spec 의 risk mitigation 으로 처리:

```python
# regression test 보강 — _classify 테스트를 default mode 로 격리
def test_predict_py_interface_unchanged(tmp_path, monkeypatch):
    from models.closure_risk import predict as p
    p._load_risk_levels.cache_clear()
    monkeypatch.setattr(p, "WEIGHTS_DIR", tmp_path)  # metrics.json 미존재 → default

    assert p._classify(0.7) == "danger"
    assert p._classify(0.5) == "caution"
    assert p._classify(0.1) == "safe"
```

- [ ] **Step 5: commit (산출물 + 회귀 test 보강)**

```bash
git add models/closure_risk/weights/metrics.json \
        models/closure_risk/weights/calibration_curve.png \
        models/closure_risk/weights/closure_risk_lgbm.pkl \
        models/closure_risk/weights/closure_risk_tcn_scaler.pkl \
        models/closure_risk/weights/ensemble_weights.pkl \
        tests/test_closure_risk_regression.py
git commit -m "$(cat <<'EOF'
chore(closure_risk): retrain with D layer threshold fit (T4)

production retrain — metrics.json 의 thresholds key 신규 fit
(val_proba.quantile(0.90/0.70) → danger/caution).

기존 hard 0.65/0.40 → fit 된 quantile threshold 자동 적용.
test_predict_py_interface_unchanged 는 monkeypatch (WEIGHTS_DIR=tmp) 로
default fallback 격리하여 회귀 보존.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 회고 작성

**Files:**
- Create: `docs/retrospective/2026-05-01-d-layer.md` (C layer 회고와 별도 파일 — 같은 날짜 두 sprint)

- [ ] **Step 1: 회고 작성**

내용 구조:
1. **요약** — D layer fix 완료. threshold 동적 fit + predict_topk API. before/after 비교
2. **배경** — C layer fix 후 분포 진단 (proba >= 0.65 = 0건). top-K reframe 의 정당성
3. **작업 내역** — 5 task subagent + commit SHA
4. **결과** — fit 된 threshold 값 (danger/caution), predict_topk 실 사용 예시
5. **다음 sprint 우선순위** — B (feature) → A (구조) → calibration (D-3, isotonic)
6. **배운 점** — threshold fit 의 효과, top-K reframe 의 학술적 근거, P@K metric 과 직접 매핑 등

- [ ] **Step 2: commit**

```bash
git add docs/retrospective/2026-05-01-d-layer.md
git commit -m "docs(closure_risk): 2026-05-01 D layer 회고 (threshold + top-K)"
```

---

## Verification — 최종 회귀

- [ ] **Step 1: 전체 closure_risk test 통과**

```bash
python -m pytest tests/test_closure_risk_*.py -v
```

Expected: 34 passed (label 6 + split 6 + metrics 8 + regression 4 + topk 10).

- [ ] **Step 2: ruff clean**

```bash
ruff check models/closure_risk/ tests/test_closure_risk_*.py
ruff format --check models/closure_risk/ tests/test_closure_risk_*.py
```

Expected: clean.

- [ ] **Step 3: git log 확인**

```bash
git log --oneline -8
```

Expected: 6 commit (spec/plan + T1~T5).

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| `_classify` 동적 threshold 로 기존 회귀 깨짐 | T4 의 monkeypatch (WEIGHTS_DIR=tmp) 로 default fallback 격리 |
| `predict_topk` 의 N=수십~수백 개 호출이 느림 | `_load_models` cache. N=160 (마포 전체) ~ 수십초 예상. 추후 batch 최적화 별도 spec |
| `_load_risk_levels` lru_cache 가 학습 후 stale | 학습-추론 별도 process. process 내 갱신 시 `cache_clear()` 호출 |
| `test_train_writes_thresholds_to_metrics` 가 retrain 전엔 skip | T4 retrain 후에만 의미. skip 으로 처리 |
| ensemble_val_proba 비어있는 edge case | T2 의 default threshold 0.65/0.40 fallback |

## Self-Review

1. **Spec coverage**: ✅ — `_load_risk_levels` (T1), `train.py` threshold fit (T2), `predict_topk` (T3), retrain + 회귀 보강 (T4), 회고 (T5).
2. **Placeholder scan**: ✅ — TBD/TODO 없음. 모든 step 에 실제 코드/명령.
3. **Type consistency**: ✅ — `_load_risk_levels() -> tuple[tuple[float, str], ...]`, `predict_topk(targets: list[tuple[str, str]], k_pct: int) -> list[dict]` 일관.

승인 후 subagent-driven-development 로 실행.
