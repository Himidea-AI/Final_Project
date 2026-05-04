# Emerging District UX 재설계 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emerging district 카드의 사용자 친화도 정비 + autoencoder consecutive 메트릭 의미 정직화 + 백엔드가 이미 송출 중인 tier/raw evidence를 UI에 노출.

**Architecture:** 3 레이어 변경. (1) `models/emerging_district/predict.py`의 `_count_consecutive_anomalies`를 per-quarter MSE 기반으로 재정의, `train.py`에 quarter_threshold 산출 추가. (2) `predict_fallback.py`의 5 tier summary를 사용자 친화 한국어로 정비. (3) frontend `EmergingSignal` 타입에 tier/raw 추가, `EmergingSignalCard`를 라벨 사전 + tier 배지 + summary + raw chip으로 재구성.

**Tech Stack:** Python 3.x (pytest, torch, sklearn, pandas) / TypeScript React (vitest, @testing-library/react)

**Spec:** `docs/superpowers/specs/2026-05-04-emerging-district-ux-redesign-design.md`

---

## File Structure

| 파일 | 작업 | Task |
|---|---|---|
| `tests/test_emerging_district.py` | 신규 | T1, T3, T4 |
| `models/emerging_district/predict.py` | 수정 (line 106-138) | T2 |
| `models/emerging_district/train.py` | 수정 (line 145, 162 근처) | T3 |
| `models/emerging_district/predict_fallback.py` | 수정 (line 43, 252, 265-268, 282-284, 297-300, 310) | T4 |
| (실행) `python -m models.emerging_district.train` | 마이그레이션 | T5 |
| `frontend/src/types/index.ts` | 수정 (line 313-327, 443-465) | T6 |
| `frontend/.../PredictEmergingDistrictTab.tsx` | 수정 (line 54 cast 제거) | T6 |
| `frontend/.../EmergingSignalCard.test.tsx` | 신규 | T7-T10 |
| `frontend/.../EmergingSignalCard.tsx` | 수정 (전면 재구성) | T7-T10 |

---

## Task 1: 백엔드 테스트 스캐폴딩 + per-quarter consecutive 실패 테스트

**Files:**
- Create: `tests/test_emerging_district.py`

- [ ] **Step 1.1: 신규 테스트 파일 작성 — sys.path 부트스트랩 + StubModel + 첫 케이스 (마지막 1분기 outlier)**

`tests/test_emerging_district.py`:
```python
"""emerging_district 모델 테스트.

per-quarter consecutive 메트릭 + 5 tier fallback summary 정합성 검증.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch
from sklearn.preprocessing import MinMaxScaler

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class _StubModel(torch.nn.Module):
    """recon = zeros. timestep MSE = mean(x ** 2)."""

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.zeros_like(x)


def _make_group_df(quarter_values: list[list[float]]) -> pd.DataFrame:
    """quarter_values[i] = i번째 분기의 [f1, f2] 값."""
    arr = np.asarray(quarter_values, dtype=np.float32)
    return pd.DataFrame(
        {
            "quarter": list(range(len(arr))),
            "f1": arr[:, 0],
            "f2": arr[:, 1],
        }
    )


def _make_meta(quarter_threshold: float | None = 0.5) -> dict:
    meta: dict = {
        "window_size": 8,
        "feature_names": ["f1", "f2"],
        "threshold": 0.5,
    }
    if quarter_threshold is not None:
        meta["quarter_threshold"] = quarter_threshold
    return meta


def _make_scaler(quarter_values: list[list[float]]) -> MinMaxScaler:
    scaler = MinMaxScaler()
    scaler.fit(np.asarray(quarter_values, dtype=np.float32))
    return scaler


# ---------------------------------------------------------------------------
# per-quarter consecutive 메트릭 검증
# ---------------------------------------------------------------------------


def test_consecutive_last_one_quarter_outlier():
    """마지막 1분기만 outlier → consecutive=1."""
    from models.emerging_district.predict import _count_consecutive_anomalies

    # 10분기, 마지막만 [1.0, 1.0] (mean(x**2)=1.0 > 0.5), 나머지는 [0,0] (=0 < 0.5)
    quarter_values = [[0.0, 0.0]] * 9 + [[1.0, 1.0]]
    df = _make_group_df(quarter_values)
    meta = _make_meta(quarter_threshold=0.5)
    scaler = _make_scaler(quarter_values + [[0.0, 0.0], [1.0, 1.0]])  # 전체 range 잡기
    model = _StubModel()

    count = _count_consecutive_anomalies(df, model, meta, scaler)
    assert count == 1
```

- [ ] **Step 1.2: 테스트 실행 → 실패 확인**

Run:
```
pytest tests/test_emerging_district.py::test_consecutive_last_one_quarter_outlier -v
```

Expected: FAIL — 현행 `_count_consecutive_anomalies`는 8분기 평균 MSE를 계산하므로 마지막 윈도우 평균은 `(0*7 + 1.0)/8 = 0.125 < 0.5`로 임계 미만 → count=0.
실패 메시지: `assert 0 == 1`

---

## Task 2: predict.py — `_count_consecutive_anomalies` per-quarter 재정의

**Files:**
- Modify: `models/emerging_district/predict.py:106-138`
- Test: `tests/test_emerging_district.py`

- [ ] **Step 2.1: predict.py 함수 재작성**

`models/emerging_district/predict.py` line 106-138 교체:

```python
def _count_consecutive_anomalies(
    group_df,
    model: LSTMAutoencoder,
    meta: dict,
    scaler: MinMaxScaler,
) -> int:
    """뒤에서부터 분기 단위 연속 이상 분기 수 카운트.

    윈도우는 1분기씩 뒤로 밀지만, 비교는 윈도우의 마지막 timestep MSE만 사용 →
    "분기 t의 패턴이 평소와 다른가"를 분기 단위로 판정. quarter_threshold 미존재
    시 기존 threshold 로 fallback (구버전 meta 호환).
    """
    window_size = meta["window_size"]
    feature_names = meta["feature_names"]
    quarter_threshold = meta.get("quarter_threshold", meta["threshold"])

    group_df = group_df.sort_values("quarter")
    feat_vals = group_df[feature_names].values.astype(np.float32)

    if len(feat_vals) < window_size:
        return 0

    feat_scaled = scaler.transform(feat_vals)
    count = 0

    for i in range(len(feat_scaled) - window_size, -1, -1):
        seq = feat_scaled[i : i + window_size]
        _dev = next(model.parameters()).device
        x_t = torch.from_numpy(seq).unsqueeze(0).to(_dev)  # (1, window, features)
        with torch.no_grad():
            recon = model(x_t)
        last_err = float(((recon[:, -1, :] - x_t[:, -1, :]) ** 2).mean().item())
        if last_err > quarter_threshold:
            count += 1
        else:
            break

    return count
```

- [ ] **Step 2.2: StubModel 보완 — `parameters()` 호환**

`_StubModel`은 `torch.nn.Module` 상속이지만 파라미터가 없으므로 `next(model.parameters())`가 StopIteration. 더미 파라미터 추가.

`tests/test_emerging_district.py`의 `_StubModel` 수정:

```python
class _StubModel(torch.nn.Module):
    """recon = zeros. timestep MSE = mean(x ** 2)."""

    def __init__(self) -> None:
        super().__init__()
        # device 추적용 더미 파라미터 (predict.py가 next(model.parameters()).device 사용)
        self._dummy = torch.nn.Parameter(torch.zeros(1), requires_grad=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.zeros_like(x)
```

- [ ] **Step 2.3: 테스트 PASS 확인**

Run: `pytest tests/test_emerging_district.py::test_consecutive_last_one_quarter_outlier -v`
Expected: PASS

- [ ] **Step 2.4: 추가 케이스 4개 작성 — 마지막 2분기 outlier / 전부 정상 / break 정상 / quarter_threshold 누락 fallback**

`tests/test_emerging_district.py` 끝에 추가:

```python
def test_consecutive_last_two_quarter_outliers():
    """마지막 2분기 outlier → consecutive=2."""
    from models.emerging_district.predict import _count_consecutive_anomalies

    quarter_values = [[0.0, 0.0]] * 8 + [[1.0, 1.0], [1.0, 1.0]]
    df = _make_group_df(quarter_values)
    meta = _make_meta(quarter_threshold=0.5)
    scaler = _make_scaler(quarter_values)
    model = _StubModel()

    count = _count_consecutive_anomalies(df, model, meta, scaler)
    assert count == 2


def test_consecutive_all_normal():
    """모든 분기 정상 → consecutive=0."""
    from models.emerging_district.predict import _count_consecutive_anomalies

    quarter_values = [[0.0, 0.0]] * 10
    df = _make_group_df(quarter_values)
    meta = _make_meta(quarter_threshold=0.5)
    scaler = _make_scaler([[0.0, 0.0], [1.0, 1.0]])
    model = _StubModel()

    count = _count_consecutive_anomalies(df, model, meta, scaler)
    assert count == 0


def test_consecutive_break_when_normal_inserted():
    """마지막은 outlier지만 그 직전 분기가 정상이면 break — consecutive=1만."""
    from models.emerging_district.predict import _count_consecutive_anomalies

    # 9분기 정상 + 마지막 outlier. 직전 분기는 정상 (MSE=0)이므로 break.
    quarter_values = [[0.0, 0.0]] * 9 + [[1.0, 1.0]]
    df = _make_group_df(quarter_values)
    meta = _make_meta(quarter_threshold=0.5)
    scaler = _make_scaler([[0.0, 0.0], [1.0, 1.0]])
    model = _StubModel()

    count = _count_consecutive_anomalies(df, model, meta, scaler)
    assert count == 1


def test_consecutive_quarter_threshold_fallback():
    """meta에 quarter_threshold 키 없으면 기존 threshold로 fallback."""
    from models.emerging_district.predict import _count_consecutive_anomalies

    quarter_values = [[0.0, 0.0]] * 9 + [[1.0, 1.0]]
    df = _make_group_df(quarter_values)
    meta = _make_meta(quarter_threshold=None)  # 키 누락
    assert "quarter_threshold" not in meta
    scaler = _make_scaler([[0.0, 0.0], [1.0, 1.0]])
    model = _StubModel()

    # threshold=0.5 fallback 으로 동일 결과 기대
    count = _count_consecutive_anomalies(df, model, meta, scaler)
    assert count == 1
```

- [ ] **Step 2.5: 5개 테스트 모두 PASS 확인**

Run: `pytest tests/test_emerging_district.py -v -k consecutive`
Expected: 5 passed

- [ ] **Step 2.6: 회귀 — 기존 sensitivity 테스트 PASS**

Run: `pytest tests/test_sensitivity.py -v`
Expected: 26 passed

- [ ] **Step 2.7: Stage + commit (CLAUDE.md 정책에 따라 user 승인 후 commit)**

```
git add tests/test_emerging_district.py models/emerging_district/predict.py
git status
```

Stage 후 user에게 commit 승인 요청. 커밋 메시지 (승인 시):
```
fix(emerging_district): consecutive 메트릭을 per-quarter MSE로 재정의

- _count_consecutive_anomalies가 8분기 윈도우 평균 대신 마지막 timestep MSE만
  비교하도록 변경 → "분기 t가 평소와 다른가" 분기 단위 의미와 1:1 대응
- meta.quarter_threshold 신규 키 사용, 누락 시 threshold fallback (구버전 호환)
- 신규 테스트 5개: per-quarter outlier 카운트 + fallback 검증
```

---

## Task 3: train.py — quarter_threshold 산출 + meta 저장

**Files:**
- Modify: `models/emerging_district/train.py:144-170`
- Test: `tests/test_emerging_district.py` (검증은 의미상 마이그레이션 단계에서 직접)

- [ ] **Step 3.1: train.py에 quarter_threshold 산출 코드 추가**

`models/emerging_district/train.py` line 144 (`train_errors = np.concatenate(errs)`) 직후, line 145 (`threshold = float(...)`) 보다 앞에 삽입:

```python
    train_errors = np.concatenate(errs)
    threshold = float(np.percentile(train_errors, cfg["threshold_percentile"]))
    logger.info(
        "threshold (p%d) = %.6f  (mean=%.6f, std=%.6f)",
        cfg["threshold_percentile"],
        threshold,
        train_errors.mean(),
        train_errors.std(),
    )

    # per-quarter (last timestep) MSE 분포 — consecutive 메트릭 분기 단위 임계
    qerrs: list[np.ndarray] = []
    with torch.no_grad():
        for i in range(0, len(X_tr_t), 128):
            batch = X_tr_t[i : i + 128]
            recon_b = model(batch)
            qerr = ((recon_b[:, -1, :] - batch[:, -1, :]) ** 2).mean(dim=-1).cpu().numpy()
            qerrs.append(qerr)
    quarter_errors = np.concatenate(qerrs)
    quarter_threshold = float(np.percentile(quarter_errors, cfg["threshold_percentile"]))
    logger.info(
        "quarter_threshold (p%d) = %.6f  (mean=%.6f, std=%.6f)",
        cfg["threshold_percentile"],
        quarter_threshold,
        quarter_errors.mean(),
        quarter_errors.std(),
    )
```

- [ ] **Step 3.2: meta dict에 quarter_threshold 추가**

`train.py` line 157-166 의 `meta` dict 정의를 다음과 같이 수정 (한 줄 추가):

```python
    meta = {
        "input_size": input_size,
        "hidden_size": cfg["hidden_size"],
        "num_layers": cfg["num_layers"],
        "window_size": cfg["window_size"],
        "threshold": threshold,
        "quarter_threshold": quarter_threshold,
        "threshold_percentile": cfg["threshold_percentile"],
        "feature_names": list(EMERGING_FEATURES),
        "best_val_loss": best_val_loss,
    }
```

- [ ] **Step 3.3: train.py 코드 신택스 검증 (실행 X)**

Run: `python -m py_compile models/emerging_district/train.py`
Expected: no output (no syntax error)

- [ ] **Step 3.4: Stage (커밋은 마지막에 user 승인 후)**

```
git add models/emerging_district/train.py
```

---

## Task 4: predict_fallback.py — 5 tier summary 한국어 정비

**Files:**
- Modify: `models/emerging_district/predict_fallback.py:42-50, 241-311`
- Test: `tests/test_emerging_district.py`

- [ ] **Step 4.1: 실패 테스트 작성 — 5 tier summary 한국어 단언**

`tests/test_emerging_district.py` 끝에 추가:

```python
# ---------------------------------------------------------------------------
# 5 tier fallback summary 한국어 정비 검증
# ---------------------------------------------------------------------------


def test_summary_change_ix_korean(monkeypatch):
    """change_ix tier — 'LH' 코드 미노출, 한국어 신호명 사용."""
    from models.emerging_district import predict_fallback as pf

    monkeypatch.setattr(pf, "_lookup_change_ix", lambda _d: "LH")
    result = pf.predict_emerging_4tier("11440680", "CS100002")
    assert result["tier"] == "change_ix"
    assert "LH" not in result["summary"]
    assert "11440680" not in result["summary"]
    assert "CS100002" not in result["summary"]
    assert "서울시 상권변화지표" in result["summary"]
    assert "신흥 상권" in result["summary"]


def test_summary_classifier_korean(monkeypatch):
    """classifier tier — F1 노출 제거, '신뢰도' 한국어 사용."""
    from models.emerging_district import predict_fallback as pf

    monkeypatch.setattr(pf, "_lookup_change_ix", lambda _d: None)
    monkeypatch.setattr(pf, "_classifier_predict", lambda _d, _i: ("LH", 0.87))
    result = pf.predict_emerging_4tier("11440680", "CS100002")
    assert result["tier"] == "classifier"
    assert "F1" not in result["summary"]
    assert "stage" not in result["summary"]
    assert "AI 모델 판정" in result["summary"]
    assert "신뢰도 87%" in result["summary"]
    assert "신흥 상권" in result["summary"]


def test_summary_b1_trend_korean(monkeypatch):
    """b1_trend tier — '20-30대 전입' 표현 정비."""
    from models.emerging_district import predict_fallback as pf

    monkeypatch.setattr(pf, "_lookup_change_ix", lambda _d: None)
    monkeypatch.setattr(pf, "_classifier_predict", lambda _d, _i: None)
    monkeypatch.setattr(
        pf,
        "_lookup_b1_trend",
        lambda _d: {"subway_growth": 0.05, "migration_2030_rate": 0.02},
    )
    result = pf.predict_emerging_4tier("11440680", "CS100002")
    assert result["tier"] == "b1_trend"
    assert "B1" not in result["summary"]
    assert "20·30대 유입" in result["summary"]
    assert "지하철" in result["summary"]


def test_summary_slope_korean(monkeypatch):
    """slope tier — '매출 상승 / 점포수 유지' 동사화."""
    from models.emerging_district import predict_fallback as pf

    monkeypatch.setattr(pf, "_lookup_change_ix", lambda _d: None)
    monkeypatch.setattr(pf, "_classifier_predict", lambda _d, _i: None)
    monkeypatch.setattr(pf, "_lookup_b1_trend", lambda _d: None)
    monkeypatch.setattr(
        pf, "_lookup_slope", lambda _d, _i: {"sales_slope": 1.2, "store_slope": 0.0}
    )
    result = pf.predict_emerging_4tier("11440680", "CS100002")
    assert result["tier"] == "slope"
    assert "slope" not in result["summary"]
    assert "매출 상승" in result["summary"]
    assert "점포수 유지" in result["summary"]


def test_summary_none_korean(monkeypatch):
    """none tier — '데이터 검증 중' 표현."""
    from models.emerging_district import predict_fallback as pf

    monkeypatch.setattr(pf, "_lookup_change_ix", lambda _d: None)
    monkeypatch.setattr(pf, "_classifier_predict", lambda _d, _i: None)
    monkeypatch.setattr(pf, "_lookup_b1_trend", lambda _d: None)
    monkeypatch.setattr(pf, "_lookup_slope", lambda _d, _i: None)
    result = pf.predict_emerging_4tier("11440680", "CS100002")
    assert result["tier"] == "none"
    assert "normal 가정" not in result["summary"]
    assert "데이터 검증 중" in result["summary"]
    assert "안정 상권" in result["summary"]
```

- [ ] **Step 4.2: 테스트 실행 → 실패 확인**

Run: `pytest tests/test_emerging_district.py -v -k summary_`
Expected: 5 tests FAIL — 현행 summary는 dong_code/industry_code raw + 영문 코드 그대로.

- [ ] **Step 4.3: predict_fallback.py에 _SIGNAL_KO 모듈 상수 추가**

`models/emerging_district/predict_fallback.py` line 42 (기존 `_CHANGE_IX_SIGNAL = {...}` 위) 에 추가:

```python
_SIGNAL_KO = {
    "emerging": "신흥 상권",
    "declining": "쇠퇴 상권",
    "normal": "안정 상권",
}


_CHANGE_IX_SIGNAL = {
    "LH": "emerging",
    "HH": "normal",
    "HL": "declining",
    "LL": "normal",
}
```

- [ ] **Step 4.4: change_ix tier summary 정비 (line 246-253)**

`predict_fallback.py:246-253`의 EmergingFallbackResult 생성을 다음과 같이 변경:

```python
    cix = _lookup_change_ix(dong_code)
    if cix is not None:
        signal = _CHANGE_IX_SIGNAL.get(cix, "normal")
        return EmergingFallbackResult(
            dong_code=dong_code,
            industry_code=industry_code,
            signal=signal,
            tier="change_ix",
            raw={"change_ix": cix},
            summary=f"서울시 상권변화지표 기준 — {_SIGNAL_KO[signal]}",
        )
```

- [ ] **Step 4.5: classifier tier summary 정비 (line 256-269)**

`predict_fallback.py:256-269` 변경:

```python
    cls_result = _classifier_predict(dong_code, industry_code)
    if cls_result is not None:
        cls_stage, prob = cls_result
        signal = _CHANGE_IX_SIGNAL.get(cls_stage, "normal")
        return EmergingFallbackResult(
            dong_code=dong_code,
            industry_code=industry_code,
            signal=signal,
            tier="classifier",
            raw={"predicted_stage": cls_stage, "confidence": round(prob, 4)},
            summary=f"AI 모델 판정 — {_SIGNAL_KO[signal]} (신뢰도 {prob * 100:.0f}%)",
        )
```

- [ ] **Step 4.6: b1_trend tier summary 정비 (line 271-285)**

`predict_fallback.py:271-285` 변경:

```python
    b1 = _lookup_b1_trend(dong_code)
    if b1 is not None:
        signal = _b1_trend_to_signal(b1)
        return EmergingFallbackResult(
            dong_code=dong_code,
            industry_code=industry_code,
            signal=signal,
            tier="b1_trend",
            raw=b1,
            summary=(
                f"지하철 {b1['subway_growth']:+.1%} · "
                f"20·30대 유입 {b1['migration_2030_rate']:+.1%} — "
                f"{_SIGNAL_KO[signal]} 신호"
            ),
        )
```

- [ ] **Step 4.7: slope tier summary 정비 (line 287-301)**

부호별 동사 매핑 함수 추가 + summary 변경. `predict_fallback.py:287-301` 변경:

```python
    slope = _lookup_slope(dong_code, industry_code)
    if slope is not None:
        signal = _slope_to_signal(slope)
        sales_verb = _slope_verb(slope["sales_slope"])
        store_verb = _slope_verb(slope["store_slope"])
        return EmergingFallbackResult(
            dong_code=dong_code,
            industry_code=industry_code,
            signal=signal,
            tier="slope",
            raw=slope,
            summary=(
                f"최근 3분기 매출 {sales_verb} · 점포수 {store_verb} — "
                f"{_SIGNAL_KO[signal]} 신호"
            ),
        )
```

`_slope_to_signal` 함수 (line 226-233) 위에 헬퍼 추가:

```python
def _slope_verb(value: float) -> str:
    """slope 부호별 사용자 친화 한국어 동사. 임계 0.5는 frontend chip 부호와 동일."""
    if value > 0.5:
        return "상승"
    if value < -0.5:
        return "하락"
    return "유지"
```

- [ ] **Step 4.8: none tier summary 정비 (line 303-311)**

`predict_fallback.py:303-311` 변경:

```python
    # Tier 4: 모든 데이터 부재
    return EmergingFallbackResult(
        dong_code=dong_code,
        industry_code=industry_code,
        signal="normal",
        tier="none",
        raw={},
        summary="데이터 검증 중 — 안정 상권으로 가정",
    )
```

- [ ] **Step 4.9: 5 summary 테스트 PASS 확인**

Run: `pytest tests/test_emerging_district.py -v -k summary_`
Expected: 5 passed

- [ ] **Step 4.10: 회귀 — 전체 신규 테스트 + sensitivity 테스트 PASS**

Run:
```
pytest tests/test_emerging_district.py tests/test_sensitivity.py -v
```
Expected: 10 passed (신규 5 consecutive + 5 summary) + 26 (sensitivity) = 36

- [ ] **Step 4.11: Stage**

```
git add models/emerging_district/predict_fallback.py tests/test_emerging_district.py
```

---

## Task 5: 마이그레이션 — train.py 1회 실행으로 meta 갱신

**Files:**
- Touch: `models/emerging_district/weights/autoencoder_meta.pkl` (재생성)

- [ ] **Step 5.1: 백업**

Bash:
```
cp models/emerging_district/weights/autoencoder_meta.pkl models/emerging_district/weights/autoencoder_meta.pkl.bak_pre_quarter_threshold
```

Expected: 백업 파일 생성, 원본 그대로.

- [ ] **Step 5.2: train.py 실행**

Bash (PYTHONIOENCODING=utf-8 권장 — 메모리 참고):
```
PYTHONIOENCODING=utf-8 python -m models.emerging_district.train
```

Expected log 마지막 부분에:
```
[AE] ... best_val_loss=...
threshold (p95) = 0.04...
quarter_threshold (p95) = 0.0...
메타 저장: ...autoencoder_meta.pkl
학습 완료 — best_val_loss=..., threshold=...
```

`quarter_threshold` 로그 행이 보이면 성공. 가중치는 다시 학습되어도 best_val_loss가 비슷해야 함 (재현성). 큰 차이가 나면 random seed 부재가 원인이지만 본 작업의 핵심은 meta 키 추가이므로 무방.

- [ ] **Step 5.3: meta 키 검증 — Python REPL 직접 확인**

Bash:
```
python -c "import pickle; m = pickle.load(open('models/emerging_district/weights/autoencoder_meta.pkl', 'rb')); print('keys:', list(m.keys())); print('quarter_threshold:', m.get('quarter_threshold'))"
```

Expected:
```
keys: [..., 'threshold', 'quarter_threshold', ...]
quarter_threshold: <float>
```

- [ ] **Step 5.4: smoke — predict 1회 실행해 mock 미반환 확인**

Bash:
```
python -c "from models.emerging_district.predict import predict; r = predict('11440680', 'CS100002'); print('is_mock:', r['is_mock']); print('consecutive:', r['consecutive_anomaly_quarters']); print('signal:', r['signal'])"
```

Expected: `is_mock: False` (실 데이터로 추론). consecutive 값이 이전 대비 더 직관적인지 확인.

- [ ] **Step 5.5: Stage meta 변경**

```
git add models/emerging_district/weights/autoencoder_meta.pkl
```

(.pt 가중치는 재학습으로 변경되었을 수 있으니 git status 확인 후 의도적 변경만 stage. 보수적 접근: meta만 stage하고 .pt는 unstaged 유지하다 user 결정 따름.)

---

## Task 6: 프론트엔드 타입 확장 + cast 제거

**Files:**
- Modify: `frontend/src/types/index.ts:313-327, 443-465`
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx:54`

- [ ] **Step 6.1: EmergingSignal 인터페이스 확장**

`frontend/src/types/index.ts` line 319 의 `EmergingSignal` 인터페이스 교체:

```typescript
/**
 * [E — emerging_district] 상권 조기 감지 (LSTM Autoencoder + 4-tier fallback)
 *
 * predict 응답. 4-tier fallback (change_ix → classifier → b1_trend → slope → none)
 * 이 signal/summary/tier/raw 를 1차 결정, autoencoder 가 anomaly_score +
 * consecutive_anomaly_quarters 보강.
 */
export interface EmergingSignal {
  dong_code: string;
  industry_code: string;
  anomaly_score: number; // 0~1 (1에 가까울수록 평소 패턴과 다름)
  signal: 'emerging' | 'declining' | 'normal';
  consecutive_anomaly_quarters: number;
  summary: string;
  tier: 'change_ix' | 'classifier' | 'b1_trend' | 'slope' | 'none';
  raw: Record<string, number | string>;
  is_mock?: boolean;
}
```

- [ ] **Step 6.2: DistrictPredictionResult.emerging_signal 강타입화**

`frontend/src/types/index.ts` line 443-465 영역의 `DistrictPredictionResult` 인터페이스에서 `emerging_signal` 필드를 다음으로 변경:

```typescript
  emerging_signal: EmergingSignal | null;
```

(주석은 기존 그대로 유지.)

- [ ] **Step 6.3: PredictEmergingDistrictTab.tsx의 cast 제거**

`frontend/src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx:54`:

기존:
```tsx
              <EmergingSignalCard
                signal={p.emerging_signal as unknown as EmergingSignal}
                district={districtLabel}
              />
```

변경:
```tsx
              <EmergingSignalCard
                signal={p.emerging_signal}
                district={districtLabel}
              />
```

- [ ] **Step 6.4: TypeScript 컴파일 검증**

Bash:
```
cd frontend && npx tsc --noEmit
```

Expected: no error. 만약 다른 컴포넌트에서 emerging_signal 을 약타입으로 다루는 곳이 있어 타입 에러 발생하면 그 컴포넌트의 prop type도 동시 수정 필요.

- [ ] **Step 6.5: Prettier**

Bash:
```
cd frontend && npx prettier --write src/types/index.ts src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx
```

- [ ] **Step 6.6: Stage**

```
git add frontend/src/types/index.ts frontend/src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx
```

---

## Task 7: EmergingSignalCard — 라벨 단어 사전 정비 + 테스트 스캐폴딩

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx`
- Modify: `frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx`

- [ ] **Step 7.1: 신규 테스트 파일 + label 분기 테스트 작성**

`frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EmergingSignalCard } from './EmergingSignalCard';
import type { EmergingSignal } from '../../../../types';

const mkSignal = (overrides: Partial<EmergingSignal> = {}): EmergingSignal => ({
  dong_code: '11440680',
  industry_code: 'CS100002',
  anomaly_score: 0.5,
  signal: 'normal',
  consecutive_anomaly_quarters: 0,
  summary: '데이터 검증 중 — 안정 상권으로 가정',
  tier: 'none',
  raw: {},
  is_mock: true,
  ...overrides,
});

describe('EmergingSignalCard — 라벨 단어 사전', () => {
  it('"이상도" 표현 미노출', () => {
    render(<EmergingSignalCard signal={mkSignal()} district="합정동" />);
    expect(screen.queryByText(/이상도/)).toBeNull();
  });

  it('KPI 라벨이 "평소 대비 변화"', () => {
    render(<EmergingSignalCard signal={mkSignal()} district="합정동" />);
    expect(screen.getByText('평소 대비 변화')).toBeInTheDocument();
  });

  it('signal=normal 일 때 "안정 상권" 표시', () => {
    render(<EmergingSignalCard signal={mkSignal({ signal: 'normal' })} district="합정동" />);
    expect(screen.getByText('안정 상권')).toBeInTheDocument();
  });

  it('게이지 좌우 라벨 "낮음" / "높음"', () => {
    render(<EmergingSignalCard signal={mkSignal()} district="합정동" />);
    expect(screen.getByText('낮음')).toBeInTheDocument();
    expect(screen.getByText('높음')).toBeInTheDocument();
  });
});
```

- [ ] **Step 7.2: 테스트 실행 → 실패 확인**

Bash:
```
cd frontend && npx vitest run src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx --reporter=verbose
```

Expected: 4 tests FAIL — 현재는 "이상도", "이상도 점수", "정상 상권", "0", "0.5", "1" 표기.

- [ ] **Step 7.3: EmergingSignalCard.tsx — 라벨 단어 교체**

`frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx` 다음 영역 수정:

`SIGNAL_STYLES.normal.label` (line 39):
```typescript
  normal: {
    label: '안정 상권',
    text: 'text-success',
    bar: 'bg-success',
    Icon: ShieldCheck,
  },
```

KPI 라벨 (line 110 영역):
```tsx
          <div className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest mt-1">
            평소 대비 변화
          </div>
```

게이지 영역 (line 116-132 전체) 교체:
```tsx
      <div>
        <div className="flex justify-between items-center mb-2">
          <span className="text-[0.625rem] font-black text-muted-foreground uppercase tracking-widest">
            평소와 다른 정도
          </span>
          <span className="text-[0.6875rem] font-black text-muted-foreground tabular-nums">
            {signal.anomaly_score.toFixed(2)}
          </span>
        </div>
        <div className="w-full bg-card h-2 rounded-full overflow-hidden">
          <div className={`h-full ${style.bar} transition-all`} style={{ width: `${scorePct}%` }} />
        </div>
        <div className="flex justify-between text-[0.5625rem] font-bold text-muted-foreground tabular-nums mt-1">
          <span>낮음</span>
          <span>높음</span>
        </div>
      </div>
```

- [ ] **Step 7.4: 4 테스트 PASS 확인**

Bash:
```
cd frontend && npx vitest run src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx --reporter=verbose
```

Expected: 4 passed

- [ ] **Step 7.5: Prettier + stage**

```
cd frontend && npx prettier --write src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx
git add frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx
```

---

## Task 8: EmergingSignalCard — tier 헤더 배지 (mock 배지 흡수)

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx`
- Modify: `frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx:79-89`

- [ ] **Step 8.1: 실패 테스트 추가 — tier 5 케이스**

`EmergingSignalCard.test.tsx` 끝에 추가:

```typescript
describe('EmergingSignalCard — tier 헤더 배지', () => {
  it('change_ix → "공식 데이터" 배지', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({ tier: 'change_ix', is_mock: false })}
        district="합정동"
      />
    );
    expect(screen.getByText('공식 데이터')).toBeInTheDocument();
  });

  it('classifier → "AI 판정" 배지', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({ tier: 'classifier', is_mock: false })}
        district="합정동"
      />
    );
    expect(screen.getByText('AI 판정')).toBeInTheDocument();
  });

  it('b1_trend → "보조 신호" 배지', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({ tier: 'b1_trend', is_mock: false })}
        district="합정동"
      />
    );
    expect(screen.getByText('보조 신호')).toBeInTheDocument();
  });

  it('slope → "보조 신호" 배지', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({ tier: 'slope', is_mock: false })}
        district="합정동"
      />
    );
    expect(screen.getByText('보조 신호')).toBeInTheDocument();
  });

  it('none → "데이터 검증 중" 배지 (is_mock 별도 미렌더)', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({ tier: 'none', is_mock: true })}
        district="합정동"
      />
    );
    expect(screen.getByText('데이터 검증 중')).toBeInTheDocument();
    // is_mock 별도 배지 흡수 — "데이터 신뢰도 검증 중" 미노출
    expect(screen.queryByText('데이터 신뢰도 검증 중')).toBeNull();
  });
});
```

- [ ] **Step 8.2: 5 테스트 실패 확인**

Bash:
```
cd frontend && npx vitest run src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx -t "tier 헤더" --reporter=verbose
```

Expected: 5 FAIL.

- [ ] **Step 8.3: EmergingSignalCard.tsx — tier 배지 매핑 + mock 배지 자리 교체**

`EmergingSignalCard.tsx` 파일 상단 import 직후 (`SIGNAL_STYLES` 위) 추가:

```typescript
const TIER_BADGE: Record<EmergingSignal['tier'], { label: string; cls: string }> = {
  change_ix: {
    label: '공식 데이터',
    cls: 'text-success bg-success/10 border-success/20',
  },
  classifier: {
    label: 'AI 판정',
    cls: 'text-primary bg-primary/10 border-primary/20',
  },
  b1_trend: {
    label: '보조 신호',
    cls: 'text-warning bg-warning/10 border-warning/20',
  },
  slope: {
    label: '보조 신호',
    cls: 'text-warning bg-warning/10 border-warning/20',
  },
  none: {
    label: '데이터 검증 중',
    cls: 'text-warning bg-warning/10 border-warning/20',
  },
};
```

기존 mock 배지 영역 (line 80-89) 교체:

```tsx
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h3 className="text-xl font-black italic leading-none tracking-tight text-foreground">
          {district ?? '—'}
        </h3>
        {(() => {
          const badge = TIER_BADGE[signal.tier] ?? TIER_BADGE.none;
          const showAlertIcon = signal.tier === 'none';
          return (
            <div
              className={`px-3 py-1 ${badge.cls} border rounded-full text-[0.625rem] font-black flex items-center gap-1.5`}
            >
              {showAlertIcon && <AlertCircle size={10} />}
              {badge.label}
            </div>
          );
        })()}
      </div>
```

(AlertCircle import는 이미 line 18에 존재.)

- [ ] **Step 8.4: 5 tier 테스트 PASS + 기존 4 라벨 테스트 PASS 확인**

Bash:
```
cd frontend && npx vitest run src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx --reporter=verbose
```

Expected: 9 passed (4 라벨 + 5 tier)

- [ ] **Step 8.5: Prettier + stage**

```
cd frontend && npx prettier --write src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx
git add frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx
```

---

## Task 9: EmergingSignalCard — summary 한 줄 표시

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx`
- Modify: `frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx`

- [ ] **Step 9.1: 실패 테스트 추가**

`EmergingSignalCard.test.tsx` 끝에 추가:

```typescript
describe('EmergingSignalCard — summary 한 줄', () => {
  it('signal.summary 문자열을 그대로 렌더', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({
          tier: 'change_ix',
          is_mock: false,
          summary: '서울시 상권변화지표 기준 — 신흥 상권',
        })}
        district="합정동"
      />
    );
    expect(screen.getByText('서울시 상권변화지표 기준 — 신흥 상권')).toBeInTheDocument();
  });
});
```

- [ ] **Step 9.2: 실패 확인**

Bash:
```
cd frontend && npx vitest run src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx -t "summary 한 줄" --reporter=verbose
```

Expected: 1 FAIL.

- [ ] **Step 9.3: EmergingSignalCard.tsx — 게이지 영역 직후에 summary 추가**

게이지 영역 닫는 `</div>` 직후 (line 133 근방), 컴포넌트 본문의 outermost `</div>` 닫기 직전에 추가:

```tsx
      <p className="text-xs text-foreground tracking-tight leading-relaxed">{signal.summary}</p>
```

(EmergingSignalCard 컴포넌트 본문의 끝 부분이 다음과 같이 구성되도록):
```tsx
      {/* ...게이지 영역... */}
      <p className="text-xs text-foreground tracking-tight leading-relaxed">{signal.summary}</p>
    </div>
  );
}
```

- [ ] **Step 9.4: PASS 확인**

Bash:
```
cd frontend && npx vitest run src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx --reporter=verbose
```

Expected: 10 passed (이전 9 + summary 1)

- [ ] **Step 9.5: Prettier + stage**

```
cd frontend && npx prettier --write src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx
git add frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx
```

---

## Task 10: EmergingSignalCard — raw evidence chip (tier별 동적)

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx`
- Modify: `frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx`

- [ ] **Step 10.1: 실패 테스트 추가 — 4 tier chip 렌더 + change_ix 미렌더 + 키 누락 케이스**

`EmergingSignalCard.test.tsx` 끝에 추가:

```typescript
describe('EmergingSignalCard — raw evidence chip', () => {
  it('classifier → "신뢰도 87%" chip', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({
          tier: 'classifier',
          raw: { predicted_stage: 'LH', confidence: 0.87 },
          is_mock: false,
        })}
        district="합정동"
      />
    );
    expect(screen.getByText(/신뢰도 87%/)).toBeInTheDocument();
  });

  it('b1_trend → "지하철" + "청년" chip 2개', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({
          tier: 'b1_trend',
          raw: { subway_growth: 0.05, migration_2030_rate: 0.02 },
          is_mock: false,
        })}
        district="합정동"
      />
    );
    expect(screen.getByText(/지하철 \+5\.0%/)).toBeInTheDocument();
    expect(screen.getByText(/청년 \+2\.0%/)).toBeInTheDocument();
  });

  it('slope → "매출 ↑" + "점포수 →" 부호 chip', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({
          tier: 'slope',
          raw: { sales_slope: 1.2, store_slope: 0.0 },
          is_mock: false,
        })}
        district="합정동"
      />
    );
    expect(screen.getByText(/매출 ↑/)).toBeInTheDocument();
    expect(screen.getByText(/점포수 →/)).toBeInTheDocument();
  });

  it('change_ix → chip 미렌더 (summary 만으로 충분)', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({
          tier: 'change_ix',
          raw: { change_ix: 'LH' },
          is_mock: false,
        })}
        district="합정동"
      />
    );
    expect(screen.queryByText(/LH/)).toBeNull();
  });

  it('none → chip 미렌더', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({ tier: 'none', raw: {}, is_mock: true })}
        district="합정동"
      />
    );
    // raw chip 영역에 텍스트가 없어야 함 (summary와 별개)
    expect(screen.queryByText(/지하철|청년|매출|점포수|신뢰도/)).toBeNull();
  });

  it('b1_trend 에서 raw 키 일부 누락 시 누락 chip 미렌더', () => {
    render(
      <EmergingSignalCard
        signal={mkSignal({
          tier: 'b1_trend',
          raw: { subway_growth: 0.05 }, // migration_2030_rate 누락
          is_mock: false,
        })}
        district="합정동"
      />
    );
    expect(screen.getByText(/지하철 \+5\.0%/)).toBeInTheDocument();
    expect(screen.queryByText(/청년/)).toBeNull();
  });
});
```

- [ ] **Step 10.2: 6 테스트 실패 확인**

Bash:
```
cd frontend && npx vitest run src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx -t "raw evidence" --reporter=verbose
```

Expected: 6 FAIL.

- [ ] **Step 10.3: EmergingSignalCard.tsx — chip 헬퍼 + 렌더 영역**

파일 상단 (`TIER_BADGE` 직후) 헬퍼 함수 추가:

```typescript
function _slopeArrow(value: number): string {
  if (value > 0.5) return '↑';
  if (value < -0.5) return '↓';
  return '→';
}

function _percentSigned(value: number): string {
  return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`;
}

function RawChip({
  signal,
}: {
  signal: EmergingSignal;
}): JSX.Element | null {
  const { tier, raw } = signal;

  if (tier === 'classifier' && typeof raw.confidence === 'number') {
    const pct = Math.round(raw.confidence * 100);
    return (
      <div className="rounded-2xl border border-border bg-secondary px-3 py-2 text-[0.6875rem] text-foreground">
        <div className="flex items-center justify-between mb-1">
          <span className="font-black">신뢰도</span>
          <span className="font-bold tabular-nums">{pct}%</span>
        </div>
        <div className="w-full bg-card h-1.5 rounded-full overflow-hidden">
          <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  }

  if (tier === 'b1_trend') {
    const sg = raw.subway_growth;
    const mr = raw.migration_2030_rate;
    return (
      <div className="flex flex-wrap gap-2">
        {typeof sg === 'number' && (
          <span className="rounded-full border border-border bg-secondary px-3 py-1 text-[0.6875rem] font-black text-foreground tabular-nums">
            지하철 {_percentSigned(sg)}
          </span>
        )}
        {typeof mr === 'number' && (
          <span className="rounded-full border border-border bg-secondary px-3 py-1 text-[0.6875rem] font-black text-foreground tabular-nums">
            청년 {_percentSigned(mr)}
          </span>
        )}
      </div>
    );
  }

  if (tier === 'slope') {
    const ss = raw.sales_slope;
    const sts = raw.store_slope;
    return (
      <div className="flex flex-wrap gap-2">
        {typeof ss === 'number' && (
          <span className="rounded-full border border-border bg-secondary px-3 py-1 text-[0.6875rem] font-black text-foreground">
            매출 {_slopeArrow(ss)}
          </span>
        )}
        {typeof sts === 'number' && (
          <span className="rounded-full border border-border bg-secondary px-3 py-1 text-[0.6875rem] font-black text-foreground">
            점포수 {_slopeArrow(sts)}
          </span>
        )}
      </div>
    );
  }

  // change_ix: summary 로 충분, chip 미렌더
  // none: 데이터 없음, chip 미렌더
  return null;
}
```

컴포넌트 본문 끝 (`<p>...summary...</p>` 직후) 에 RawChip 호출 추가:

```tsx
      <p className="text-xs text-foreground tracking-tight leading-relaxed">{signal.summary}</p>
      <RawChip signal={signal} />
    </div>
  );
}
```

- [ ] **Step 10.4: 6 chip 테스트 PASS + 누적 회귀 (10 + 6 = 16) 확인**

Bash:
```
cd frontend && npx vitest run src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx --reporter=verbose
```

Expected: 16 passed.

- [ ] **Step 10.5: Prettier + stage**

```
cd frontend && npx prettier --write src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx
git add frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.tsx frontend/src/components/SimulationResult/dashboard/charts/EmergingSignalCard.test.tsx
```

---

## Task 11: 전면 회귀 + 수동 smoke

- [ ] **Step 11.1: 백엔드 전체 테스트**

Bash:
```
PYTHONIOENCODING=utf-8 pytest tests/ -v --tb=short
```

Expected: 모든 기존 테스트 + 신규 10개 PASS. 실패 시 신규 변경이 회귀 일으킨 것이므로 원인 추적.

- [ ] **Step 11.2: 프론트 전체 vitest**

Bash:
```
cd frontend && npx vitest run --reporter=verbose
```

Expected: 모든 기존 차트 테스트 + 신규 16 PASS.

- [ ] **Step 11.3: TypeScript 타입체크**

Bash:
```
cd frontend && npx tsc --noEmit
```

Expected: no error.

- [ ] **Step 11.4: ruff (백엔드 lint/format)**

Bash:
```
ruff check --fix models/emerging_district/
ruff format models/emerging_district/
ruff check --fix tests/test_emerging_district.py
ruff format tests/test_emerging_district.py
```

Expected: 변경 없거나 minor formatting 적용.

- [ ] **Step 11.5: 수동 smoke — uvicorn 재시작 후 /predict 호출**

User 안내:
1. 기존 uvicorn 종료
2. `cd backend && uvicorn src.main:app --reload`
3. frontend dev 서버 시작 (`cd frontend && npm run dev`)
4. 브라우저 `/dashboard/predict?sub=emerging_district` 접속
5. 4동 카드 모두에서:
   - 헤더 우측 tier 배지 확인 (공식 데이터 / AI 판정 / 보조 신호 / 데이터 검증 중 중 하나)
   - "이상도" 표현이 사라지고 "평소 대비 변화" 노출
   - 게이지 좌우 라벨 "낮음 / 높음"
   - summary 한 줄이 사용자 친화 한국어
   - tier별 raw chip 적절히 렌더 (classifier=신뢰도 막대 / b1_trend=지하철+청년 / slope=매출+점포수 / change_ix·none=chip 없음)
   - is_mock 별도 배지 미렌더 확인

- [ ] **Step 11.6: 최종 git status + user commit 승인 요청**

Bash:
```
git status
git diff --stat HEAD
```

User에게 변경 파일 목록 + diff 요약 보고 후 commit 메시지 제안:

```
feat(emerging_district): UX 풀 정합 재설계 — per-quarter 메트릭 + tier 배지 + summary

- predict.py: _count_consecutive_anomalies 를 per-quarter MSE 기반 분기 단위 메트릭으로 재정의
- train.py: meta.quarter_threshold 산출 (forward 재실행, 가중치 재학습 X)
- predict_fallback.py: 5 tier summary 사용자 친화 한국어 정비, _SIGNAL_KO 모듈 상수
- types/index.ts: EmergingSignal 에 tier/raw 추가, DistrictPredictionResult.emerging_signal 강타입화
- EmergingSignalCard: 라벨 단어 사전 정비 + tier 헤더 배지 (mock 배지 흡수) + summary 한 줄 + tier별 raw chip
- 신규 테스트 26개 (백엔드 10 + 프론트 16)

Spec: docs/superpowers/specs/2026-05-04-emerging-district-ux-redesign-design.md
```

User 승인 후 단일 커밋 또는 task별 분할 커밋 중 user 선호에 따름.

---

## Self-Review 체크 (작성자 사후 점검)

**Spec coverage:**
- ✓ predict.py per-quarter 재정의 → Task 2
- ✓ train.py quarter_threshold → Task 3
- ✓ predict_fallback.py 5 tier summary → Task 4
- ✓ 마이그레이션 (forward 재실행) → Task 5
- ✓ types/index.ts EmergingSignal 확장 + DistrictPredictionResult 강타입 → Task 6
- ✓ PredictEmergingDistrictTab cast 제거 → Task 6
- ✓ EmergingSignalCard 라벨 단어 사전 → Task 7
- ✓ tier 헤더 배지 + mock 배지 흡수 → Task 8
- ✓ summary 한 줄 → Task 9
- ✓ tier별 raw chip + 옵셔널 누락 처리 → Task 10
- ✓ 백엔드 테스트 (consecutive 5 + summary 5) → Task 1, 2, 4
- ✓ 프론트 테스트 (라벨 4 + tier 5 + summary 1 + chip 6 = 16) → Task 7-10
- ✓ 회귀 + smoke → Task 11

**Placeholder scan:** 없음. 모든 step에 코드/명령/expected 명시.

**Type consistency:**
- `EmergingSignal['tier']` 5 케이스 (change_ix/classifier/b1_trend/slope/none) — Task 6, 8, 10에서 일관 사용.
- `_SIGNAL_KO` 매핑 — Task 4 에서 정의, predict_fallback 내부에서만 사용.
- `_slope_verb` (백엔드) ↔ `_slopeArrow` (프론트) 임계 0.5 일관.
- `RawChip` props (`signal: EmergingSignal`) ↔ `EmergingSignalCard` 사용처 — Task 10 에서 정의·사용.

수정 사항 없음.
