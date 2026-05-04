"""emerging_district 모델 테스트.

per-quarter consecutive 메트릭 정합성 검증.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import MinMaxScaler

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class _StubModel(torch.nn.Module):
    """recon = zeros. timestep MSE = mean(x ** 2)."""

    def __init__(self) -> None:
        super().__init__()
        # device 추적용 더미 파라미터 (predict.py가 next(model.parameters()).device 사용)
        self._dummy = torch.nn.Parameter(torch.zeros(1), requires_grad=False)

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
