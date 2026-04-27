"""TCN imputation 3모델 비교 스크립트 테스트.

`validation/experiments/tcn/compare_imputed.py` 의 핵심 함수
(`compute_metrics`, `build_comparison_table`)가 toy 백테스트 CSV를 받아
정상 동작하는지 확인한다.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from validation.experiments.tcn.compare_imputed import (
    build_comparison_table,
    compute_metrics,
)


def _toy_csv(tmp_path: Path, name: str, mape_target: float) -> Path:
    """주어진 MAPE를 만족하는 toy 백테스트 CSV 생성."""
    actual = [1.0e9, 2.0e9, 3.0e9, 4.0e9]
    pred = [a * (1 + mape_target / 100.0) for a in actual]
    df = pd.DataFrame(
        {
            "test_year": [2024] * 4,
            "dong_code": ["11440555"] * 4,
            "dong_name": ["서교동"] * 4,
            "industry_code": ["CS100001", "CS100002", "CS100003", "CS100004"],
            "industry_name": ["A", "B", "C", "D"],
            "actual_annual_sales": actual,
            "predicted_annual_sales": pred,
            "abs_error": [abs(a - p) for a, p in zip(actual, pred)],
            "mape_pct": [mape_target] * 4,
        }
    )
    p = tmp_path / name
    df.to_csv(p, index=False, encoding="utf-8-sig")
    return p


def test_compute_metrics_returns_overall_mape(tmp_path):
    csv = _toy_csv(tmp_path, "x.csv", 10.0)
    m = compute_metrics(csv)
    assert m["mape"] == pytest.approx(10.0, abs=0.5)
    assert m["n_samples"] == 4


def test_build_comparison_table_shows_three_models(tmp_path):
    a = _toy_csv(tmp_path, "a.csv", 15.0)
    b = _toy_csv(tmp_path, "b.csv", 8.0)
    c = _toy_csv(tmp_path, "c.csv", 12.0)
    table = build_comparison_table({"Original": a, "TCN-A": b, "TCN-B": c})
    assert "Original" in table["model"].values
    assert "TCN-A" in table["model"].values
    assert "TCN-B" in table["model"].values
    assert len(table) == 3
