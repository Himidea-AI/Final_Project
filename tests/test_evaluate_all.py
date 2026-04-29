"""validation/experiments/living_pop/evaluate_all.py 단위 테스트."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# 평가 자체는 living_population CSV 캐시 또는 DB 가 필요하므로,
# CI 환경(데이터 부재) 에서는 자동 skip 처리.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIVING_POP_CSV = PROJECT_ROOT / "data" / "processed" / "living_pop_quarterly.csv"
HAS_DATA = LIVING_POP_CSV.exists() or bool(os.environ.get("POSTGRES_URL"))

# evaluate_all 자체 import 는 항상 가능해야 한다 (모듈 import 가 무거운 의존성을 끌지 않도록).
from validation.experiments.living_pop.evaluate_all import (  # noqa: E402
    DEFAULT_VERSIONS,
    EVALUATORS,
    _format_markdown_table,
    _resolve_versions,
    main,
    run_evaluators,
)

# ---------------------------------------------------------------------------
# 가벼운 단위 테스트 (데이터 불필요)
# ---------------------------------------------------------------------------


def test_evaluators_registry_keys():
    """알려진 모든 변형이 EVALUATORS 에 등록되어 있다."""
    expected = {
        "naive_lag1",
        "naive_lag4_seasonal",
        "v2",
        "v3",
        "v4_residual",
        "arima",
    }
    assert expected.issubset(set(EVALUATORS.keys()))


def test_default_versions_includes_baselines():
    """default 평가 명단에 baseline 들이 포함되어 있다."""
    assert "naive_lag1" in DEFAULT_VERSIONS
    assert "naive_lag4_seasonal" in DEFAULT_VERSIONS


def test_resolve_versions_csv():
    """--versions 파라미터가 콤마 구분 list 로 파싱된다."""
    out = _resolve_versions("naive_lag1,v2", None)
    assert out == ["naive_lag1", "v2"]


def test_resolve_versions_default():
    """미지정 시 DEFAULT_VERSIONS 반환."""
    out = _resolve_versions(None, None)
    assert out == list(DEFAULT_VERSIONS)


def test_resolve_versions_filter():
    """--filter 부분 매치 — v4 → v4_residual."""
    out = _resolve_versions(None, "v4")
    assert out == ["v4_residual"]


def test_format_markdown_table_smoke():
    """markdown 표 포맷이 정상 동작한다."""
    df = pd.DataFrame(
        [
            {
                "version": "naive_lag1",
                "n_test": 1211,
                "MAE": 840.0,
                "RMSE": 1212.0,
                "NRMSE_pct": 3.20,
                "MAPE_pct": 2.11,
                "sMAPE_pct": 2.10,
                "R2": 0.9892,
                "MASE": 1.0,
            },
            {
                "version": "v4_residual",
                "n_test": 1211,
                "MAE": 837.0,
                "RMSE": 1178.0,
                "NRMSE_pct": 3.11,
                "MAPE_pct": 2.17,
                "sMAPE_pct": 2.15,
                "R2": 0.9898,
                "MASE": 0.866,
            },
        ]
    )
    out = _format_markdown_table(df)
    assert "version" in out
    assert "MASE" in out
    # MASE 오름차순: 0.866 (v4_residual) 먼저
    v4_idx = out.find("v4_residual")
    n_idx = out.find("naive_lag1")
    assert 0 <= v4_idx < n_idx


def test_format_markdown_table_includes_mase_in_sample():
    """MASE_in_sample 컬럼이 있으면 markdown 표 헤더에 포함된다."""
    df = pd.DataFrame(
        [
            {
                "version": "v4_residual",
                "n_test": 1211,
                "MAE": 837.0,
                "RMSE": 1178.0,
                "NRMSE_pct": 3.11,
                "MAPE_pct": 2.17,
                "sMAPE_pct": 2.15,
                "R2": 0.9898,
                "MASE": 0.997,
                "MASE_in_sample": 0.905,
            },
        ]
    )
    out = _format_markdown_table(df)
    assert "MASE_in_sample" in out
    assert "0.905" in out


# ---------------------------------------------------------------------------
# 데이터 의존 테스트 (CSV/DB 필요)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_DATA, reason="living_pop_quarterly.csv / POSTGRES_URL 부재")
def test_evaluator_returns_tuple():
    """각 evaluator (가벼운 baseline) 가 (y_true, y_pred, y_naive, y_train_actuals)
    4-tuple 반환."""
    fn = EVALUATORS["naive_lag1"]
    result = fn()
    assert isinstance(result, tuple) and len(result) == 4
    y_true, y_pred, y_naive, y_train_actuals = result
    assert isinstance(y_true, np.ndarray)
    assert isinstance(y_pred, np.ndarray)
    assert isinstance(y_naive, np.ndarray)
    assert isinstance(y_train_actuals, np.ndarray)
    assert y_true.shape == y_pred.shape == y_naive.shape
    assert y_true.size > 0
    # train actuals 는 train split 의 1차원 시계열
    assert y_train_actuals.ndim == 1
    assert y_train_actuals.size > 0


@pytest.mark.skipif(not HAS_DATA, reason="living_pop_quarterly.csv / POSTGRES_URL 부재")
def test_naive_lag1_self_mase_one():
    """naive 자체를 모델로 evaluate 하면 MASE = 1.0."""
    df, warnings = run_evaluators(["naive_lag1"])
    assert len(df) == 1
    row = df.iloc[0]
    assert row["version"] == "naive_lag1"
    assert row["MASE"] == pytest.approx(1.0, abs=1e-6)


@pytest.mark.skipif(not HAS_DATA, reason="living_pop_quarterly.csv / POSTGRES_URL 부재")
def test_naive_lag4_seasonal_runs():
    """seasonal naive 도 정상 실행 + MASE finite."""
    df, _ = run_evaluators(["naive_lag4_seasonal"])
    assert len(df) == 1
    row = df.iloc[0]
    assert np.isfinite(row["MASE"])
    assert row["MASE"] > 0


@pytest.mark.skipif(not HAS_DATA, reason="living_pop_quarterly.csv / POSTGRES_URL 부재")
def test_main_smoke(tmp_path: Path, capsys: pytest.CaptureFixture):
    """main(--versions naive_lag1,naive_lag4_seasonal) 가 정상 동작 + CSV 생성."""
    out_csv = tmp_path / "metrics.csv"
    rc = main(
        [
            "--versions",
            "naive_lag1,naive_lag4_seasonal",
            "--output",
            str(out_csv),
        ]
    )
    assert rc == 0
    assert out_csv.exists()
    df = pd.read_csv(out_csv)
    assert set(df["version"]) == {"naive_lag1", "naive_lag4_seasonal"}

    captured = capsys.readouterr()
    # markdown 표가 stdout 에 출력됐는지
    assert "version" in captured.out
    assert "MASE" in captured.out
