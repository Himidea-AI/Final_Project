"""sensitivity.py 헬퍼 함수 단위 테스트."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, StandardScaler

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from models.tcn_forecast.sensitivity import (  # noqa: E402
    PERTURBATION_LEVELS,
    QUARTER_VALUES,
    SLIDER_FEATURES,
    _scale_quarter_value,
    compute_correlations,
    get_feature_indices,
)


def test_get_feature_indices_returns_correct_positions():
    features = ["a", "b", "c", "d", "e"]
    assert get_feature_indices(features, ["b", "d"]) == [1, 3]


def test_get_feature_indices_skips_missing():
    features = ["a", "b", "c"]
    assert get_feature_indices(features, ["a", "z", "c"]) == [0, 2]


def test_get_feature_indices_empty_target():
    features = ["a", "b", "c"]
    assert get_feature_indices(features, []) == []


def test_compute_correlations_perfect_positive():
    df = pd.DataFrame(
        {
            "floating_pop": [1.0, 2.0, 3.0, 4.0],
            "rent_1f": [2.0, 4.0, 6.0, 8.0],
            "vacancy_rate": [8.0, 6.0, 4.0, 2.0],
        }
    )
    result = compute_correlations(df)
    assert "floating_pop→rent_1f" in result
    assert "floating_pop→vacancy_rate" in result
    assert "rent_1f→vacancy_rate" in result
    assert abs(result["floating_pop→rent_1f"] - 1.0) < 0.001
    assert abs(result["floating_pop→vacancy_rate"] + 1.0) < 0.001


def test_compute_correlations_missing_column():
    df = pd.DataFrame(
        {
            "floating_pop": [1.0, 2.0, 3.0],
            "rent_1f": [2.0, 4.0, 6.0],
        }
    )
    result = compute_correlations(df)
    assert "floating_pop→rent_1f" in result
    assert "floating_pop→vacancy_rate" not in result
    assert "rent_1f→vacancy_rate" not in result


def test_compute_correlations_rounds_to_4_decimals():
    df = pd.DataFrame(
        {
            "floating_pop": [1.0, 2.0, 3.0, 4.0, 5.0],
            "rent_1f": [1.1, 2.3, 2.9, 4.2, 4.8],
            "vacancy_rate": [5.0, 4.0, 3.0, 2.0, 1.0],
        }
    )
    result = compute_correlations(df)
    for v in result.values():
        assert len(str(v).split(".")[-1]) <= 4


def test_perturbation_levels_includes_zero():
    assert 0 in PERTURBATION_LEVELS


def test_perturbation_levels_symmetric():
    positives = [x for x in PERTURBATION_LEVELS if x > 0]
    negatives = [-x for x in PERTURBATION_LEVELS if x < 0]
    assert sorted(positives) == sorted(negatives)


def test_quarter_values_cover_all_quarters():
    assert set(QUARTER_VALUES.keys()) == {"Q1", "Q2", "Q3", "Q4"}
    assert set(QUARTER_VALUES.values()) == {1, 2, 3, 4}


def test_slider_features_floating_pop_maps_three_features():
    assert len(SLIDER_FEATURES["floating_pop"]) == 3
    assert "bus_flpop" in SLIDER_FEATURES["floating_pop"]
    assert "adstrd_flpop" in SLIDER_FEATURES["floating_pop"]
    assert "floating_pop" in SLIDER_FEATURES["floating_pop"]


def test_scale_quarter_value_minmax_matches_sklearn():
    """MinMaxScaler 분기 — sklearn transform 결과와 일치해야 한다."""
    scaler = MinMaxScaler()
    # 두 피처 fit, quarter_idx=1 (두 번째 컬럼이 quarter 1~4)
    X = np.array([[10.0, 1.0], [20.0, 2.0], [30.0, 3.0], [40.0, 4.0]])
    scaler.fit(X)

    for q in (1, 2, 3, 4):
        # sklearn transform은 (n_samples, n_features) 형태 입력
        sklearn_scaled = scaler.transform(np.array([[0.0, float(q)]]))[0, 1]
        helper_scaled = _scale_quarter_value(scaler, quarter_idx=1, quarter_value=q)
        assert abs(helper_scaled - sklearn_scaled) < 1e-9


def test_scale_quarter_value_standard_matches_sklearn():
    """StandardScaler 분기 — sklearn transform 결과와 일치해야 한다."""
    scaler = StandardScaler()
    X = np.array([[10.0, 1.0], [20.0, 2.0], [30.0, 3.0], [40.0, 4.0]])
    scaler.fit(X)

    for q in (1, 2, 3, 4):
        sklearn_scaled = scaler.transform(np.array([[0.0, float(q)]]))[0, 1]
        helper_scaled = _scale_quarter_value(scaler, quarter_idx=1, quarter_value=q)
        assert abs(helper_scaled - sklearn_scaled) < 1e-9


def test_scale_quarter_value_standard_zero_std_returns_zero():
    """std≈0인 StandardScaler에서는 0.0을 반환 (분모 0 방지 분기)."""
    scaler = StandardScaler()
    X = np.array([[1.0, 5.0], [2.0, 5.0], [3.0, 5.0], [4.0, 5.0]])
    scaler.fit(X)
    # sklearn은 std=0인 컬럼을 자동으로 scale_=1로 보정하므로,
    # 안전 분기 검증을 위해 강제로 scale_[1]=0 설정
    scaler.scale_[1] = 0.0

    result = _scale_quarter_value(scaler, quarter_idx=1, quarter_value=3)
    assert result == 0.0
