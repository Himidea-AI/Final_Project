"""emerging_district 모델 테스트.

per-quarter consecutive 메트릭 + 5 tier fallback summary 정합성 검증.
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
    monkeypatch.setattr(pf, "_lookup_slope", lambda _d, _i: {"sales_slope": 1.2, "store_slope": 0.0})
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


# ---------------------------------------------------------------------------
# quarter_history 8 분기 시계열 검증
# ---------------------------------------------------------------------------

TEST_DONG = "11440680"
TEST_INDUSTRY = "CS100001"


def _make_predict_fixtures() -> tuple:
    """predict() 단위 테스트용 stub model + meta + DataFrame 반환."""
    n_quarters = 16  # window_size(8) 보다 충분히 많은 분기
    quarter_values = [[float(i % 3), float((i + 1) % 3)] for i in range(n_quarters)]
    df_all = pd.DataFrame(
        {
            "dong_code": [TEST_DONG] * n_quarters,
            "industry_code": [TEST_INDUSTRY] * n_quarters,
            "quarter": list(range(n_quarters)),
            "f1": [v[0] for v in quarter_values],
            "f2": [v[1] for v in quarter_values],
            "monthly_sales": [1000.0 + i * 10 for i in range(n_quarters)],
            "store_count": [10.0 + i * 0.1 for i in range(n_quarters)],
        }
    )
    meta = {
        "window_size": 8,
        "feature_names": ["f1", "f2"],
        "threshold": 0.5,
        "quarter_threshold": 0.5,
        "input_size": 2,
        "hidden_size": 16,
        "num_layers": 1,
    }
    model = _StubModel()
    return df_all, meta, model


def test_quarter_history_length_eight(monkeypatch):
    """quarter_history 가 정확히 8 분기 + 라벨 정합."""
    import models.emerging_district.predict as pred_mod
    from models.emerging_district.predict import predict

    df_all, meta, model = _make_predict_fixtures()

    import models.emerging_district.data_prep as data_prep_mod

    monkeypatch.setattr(pred_mod, "_load_model", lambda: (model, meta))
    monkeypatch.setattr(
        data_prep_mod,
        "load_emerging_data",
        lambda **_kwargs: df_all,
    )

    result = predict(dong_code=TEST_DONG, industry_code=TEST_INDUSTRY)

    assert "quarter_history" in result
    qh = result["quarter_history"]
    assert qh is not None
    assert isinstance(qh, list)
    assert len(qh) == 8
    assert qh[0]["quarter"] == "Q-7"
    assert qh[-1]["quarter"] == "현재"
    for entry in qh:
        assert 0.0 <= entry["anomaly_score"] <= 1.0
