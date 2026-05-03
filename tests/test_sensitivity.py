"""sensitivity.py 헬퍼 함수 단위 테스트."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, StandardScaler

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"
for _p in (_ROOT, _BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from src.api.sensitivity import _load_json  # noqa: E402

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
            "vacancy_rate": [1.0, 2.0, 3.0, 4.0],
            "cpi_index": [2.0, 4.0, 6.0, 8.0],
            "opr_sale_mt_avg": [8.0, 6.0, 4.0, 2.0],
        }
    )
    result = compute_correlations(df)
    assert "vacancy_rate→cpi_index" in result
    assert abs(result["vacancy_rate→cpi_index"] - 1.0) < 0.001
    assert abs(result["vacancy_rate→opr_sale_mt_avg"] + 1.0) < 0.001
    assert "cpi_index→opr_sale_mt_avg" in result


def test_compute_correlations_missing_column():
    df = pd.DataFrame(
        {
            "vacancy_rate": [1.0, 2.0, 3.0],
            "cpi_index": [2.0, 4.0, 6.0],
        }
    )
    result = compute_correlations(df)
    assert "vacancy_rate→cpi_index" in result
    assert "vacancy_rate→opr_sale_mt_avg" not in result
    assert "cpi_index→opr_sale_mt_avg" not in result


def test_compute_correlations_rounds_to_4_decimals():
    df = pd.DataFrame(
        {
            "vacancy_rate": [1.0, 2.0, 3.0, 4.0, 5.0],
            "cpi_index": [1.1, 2.3, 2.9, 4.2, 4.8],
            "opr_sale_mt_avg": [5.0, 4.0, 3.0, 2.0, 1.0],
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


def test_slider_features_has_four_sliders():
    assert set(SLIDER_FEATURES.keys()) == {"vacancy_rate", "trend_score", "cpi_index", "opr_sale_mt_avg"}
    assert SLIDER_FEATURES["vacancy_rate"] == ["vacancy_rate"]
    assert SLIDER_FEATURES["trend_score"] == ["trend_score"]
    assert SLIDER_FEATURES["cpi_index"] == ["cpi_index"]
    assert SLIDER_FEATURES["opr_sale_mt_avg"] == ["opr_sale_mt_avg"]


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


def test_sensitivity_endpoint_returns_correct_structure(monkeypatch, tmp_path):
    """캐시 파일을 mock으로 주입하여 /predict/sensitivity 응답 구조를 검증."""
    import json
    import sys
    from pathlib import Path

    _BACKEND = Path(__file__).resolve().parents[1] / "backend"
    if str(_BACKEND) not in sys.path:
        sys.path.insert(0, str(_BACKEND))

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    mock_cache = {
        "11440530_CS100001": {
            "baseline": [15000000.0, 15500000.0, 16000000.0, 15800000.0],
            "elasticity": {
                "rent_1f": {"-30": -8.2, "-20": -5.1, "-10": -2.4, "0": 0.0, "+10": 2.6, "+20": 5.3, "+30": 8.1},
                "vacancy_rate": {"-30": -3.1, "-20": -2.0, "-10": -1.0, "0": 0.0, "+10": 1.1, "+20": 2.2, "+30": 3.4},
                "floating_pop": {"-30": -12.0, "-20": -8.0, "-10": -4.0, "0": 0.0, "+10": 4.1, "+20": 8.3, "+30": 12.5},
                "trend_score": {"-30": -5.0, "-20": -3.3, "-10": -1.6, "0": 0.0, "+10": 1.7, "+20": 3.4, "+30": 5.2},
                "quarter_num": {"Q1": -3.2, "Q2": 1.1, "Q3": 5.8, "Q4": -2.4},
            },
        }
    }
    mock_corr = {
        "floating_pop→rent_1f": 0.63,
        "floating_pop→vacancy_rate": -0.41,
        "rent_1f→vacancy_rate": -0.38,
    }

    cache_file = tmp_path / "sensitivity_cache.json"
    corr_file = tmp_path / "feature_correlations.json"
    cache_file.write_text(json.dumps(mock_cache), encoding="utf-8")
    corr_file.write_text(json.dumps(mock_corr), encoding="utf-8")

    monkeypatch.setenv("SENSITIVITY_CACHE_PATH", str(cache_file))
    monkeypatch.setenv("SENSITIVITY_CORR_PATH", str(corr_file))

    import importlib

    import src.api.sensitivity as sens_mod

    importlib.reload(sens_mod)

    app_test = FastAPI()
    app_test.include_router(sens_mod.router)
    client = TestClient(app_test)

    response = client.get("/predict/sensitivity?dong_code=11440530&industry_code=CS100001")
    assert response.status_code == 200
    body = response.json()
    assert "elasticity" in body
    assert "correlations" in body
    assert "baseline_sales" in body
    assert len(body["baseline_sales"]) == 4
    assert set(body["elasticity"].keys()) == {"rent_1f", "vacancy_rate", "floating_pop", "trend_score", "quarter_num"}


def test_sensitivity_endpoint_404_for_unknown_combo(monkeypatch, tmp_path):
    """캐시에 없는 조합 요청 시 404 반환."""
    import sys
    from pathlib import Path

    _BACKEND = Path(__file__).resolve().parents[1] / "backend"
    if str(_BACKEND) not in sys.path:
        sys.path.insert(0, str(_BACKEND))

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    cache_file = tmp_path / "sensitivity_cache.json"
    corr_file = tmp_path / "feature_correlations.json"
    cache_file.write_text("{}", encoding="utf-8")
    corr_file.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("SENSITIVITY_CACHE_PATH", str(cache_file))
    monkeypatch.setenv("SENSITIVITY_CORR_PATH", str(corr_file))

    import importlib

    import src.api.sensitivity as sens_mod

    importlib.reload(sens_mod)

    app_test = FastAPI()
    app_test.include_router(sens_mod.router)
    client = TestClient(app_test)

    response = client.get("/predict/sensitivity?dong_code=99999999&industry_code=CS999999")
    assert response.status_code == 404


def test_load_json_missing_file_logs_warning(tmp_path, caplog):
    """존재하지 않는 경로 → 빈 dict 반환 + warning 로그."""
    missing = tmp_path / "does_not_exist.json"
    with caplog.at_level(logging.WARNING, logger="src.api.sensitivity"):
        result = _load_json(missing)

    assert result == {}
    assert any(record.levelno == logging.WARNING for record in caplog.records)
    assert any("not found" in record.getMessage() for record in caplog.records)


def test_load_json_invalid_json_logs_error(tmp_path, caplog):
    """깨진 JSON 파일 → 빈 dict 반환 + error 로그."""
    broken = tmp_path / "broken.json"
    broken.write_text("{not valid json", encoding="utf-8")

    with caplog.at_level(logging.ERROR, logger="src.api.sensitivity"):
        result = _load_json(broken)

    assert result == {}
    assert any(record.levelno == logging.ERROR for record in caplog.records)
    assert any("Failed to parse" in record.getMessage() for record in caplog.records)


def _make_etag_test_client(monkeypatch, tmp_path):
    """ETag 테스트용 TestClient + 캐시 파일 경로 반환."""
    import json

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    mock_cache = {
        "11440530_CS100001": {
            "baseline": [1000.0, 1000.0, 1000.0, 1000.0],
            "elasticity": {
                "rent_1f": {"-30": 0.0, "-20": 0.0, "-10": 0.0, "0": 0.0, "+10": 0.0, "+20": 0.0, "+30": 0.0},
                "vacancy_rate": {"-30": 0.0, "-20": 0.0, "-10": 0.0, "0": 0.0, "+10": 0.0, "+20": 0.0, "+30": 0.0},
                "floating_pop": {"-30": 0.0, "-20": 0.0, "-10": 0.0, "0": 0.0, "+10": 0.0, "+20": 0.0, "+30": 0.0},
                "trend_score": {"-30": 0.0, "-20": 0.0, "-10": 0.0, "0": 0.0, "+10": 0.0, "+20": 0.0, "+30": 0.0},
                "quarter_num": {"Q1": 0.0, "Q2": 0.0, "Q3": 0.0, "Q4": 0.0},
            },
        }
    }
    cache_file = tmp_path / "sensitivity_cache.json"
    corr_file = tmp_path / "feature_correlations.json"
    cache_file.write_text(json.dumps(mock_cache), encoding="utf-8")
    corr_file.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("SENSITIVITY_CACHE_PATH", str(cache_file))
    monkeypatch.setenv("SENSITIVITY_CORR_PATH", str(corr_file))

    import importlib

    import src.api.sensitivity as sens_mod

    importlib.reload(sens_mod)

    app_test = FastAPI()
    app_test.include_router(sens_mod.router)
    return TestClient(app_test), cache_file


def test_sensitivity_endpoint_returns_etag_header(monkeypatch, tmp_path):
    """200 응답에 ETag + Cache-Control 헤더가 설정되어야 한다."""
    client, _ = _make_etag_test_client(monkeypatch, tmp_path)
    response = client.get("/predict/sensitivity?dong_code=11440530&industry_code=CS100001")
    assert response.status_code == 200
    assert "etag" in {k.lower() for k in response.headers}
    assert response.headers["etag"].startswith('"') and response.headers["etag"].endswith('"')
    assert "must-revalidate" in response.headers.get("cache-control", "")


def test_sensitivity_endpoint_returns_304_on_etag_match(monkeypatch, tmp_path):
    """If-None-Match가 현재 ETag와 일치하면 304 + 빈 본문."""
    client, _ = _make_etag_test_client(monkeypatch, tmp_path)
    first = client.get("/predict/sensitivity?dong_code=11440530&industry_code=CS100001")
    etag = first.headers["etag"]

    second = client.get(
        "/predict/sensitivity?dong_code=11440530&industry_code=CS100001",
        headers={"If-None-Match": etag},
    )
    assert second.status_code == 304
    assert second.headers["etag"] == etag
    assert second.content == b""


def test_sensitivity_endpoint_returns_200_on_etag_mismatch(monkeypatch, tmp_path):
    """If-None-Match가 다른 값이면 200으로 본문 반환."""
    client, _ = _make_etag_test_client(monkeypatch, tmp_path)
    response = client.get(
        "/predict/sensitivity?dong_code=11440530&industry_code=CS100001",
        headers={"If-None-Match": '"stale-etag-value"'},
    )
    assert response.status_code == 200
    assert "elasticity" in response.json()
