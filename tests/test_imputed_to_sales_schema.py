"""Tests for `scripts.imputed_to_sales_schema` adapter."""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.imputed_to_sales_schema import (
    adapt_mapo_imputed,
    adapt_seoul_imputed,
)


def test_adapt_mapo_imputed_renames_final_to_base(tmp_path):
    """`_final` 컬럼이 base 컬럼명으로 매핑되어야 한다."""
    src = pd.DataFrame(
        {
            "quarter": [20191, 20192],
            "dong_code": ["11440555", "11440555"],
            "dong_name": ["서교동", "서교동"],
            "industry_code": ["CS100001", "CS100001"],
            "industry_name": ["한식음식점", "한식음식점"],
            "monthly_sales": [3.4e9, 3.5e9],
            "monthly_sales_final": [3.355e9, 3.5e9],
            "monthly_count": [94005, 95000],
            "monthly_count_final": [94005, 95000],
            "weekday_sales": [2.6e9, 2.7e9],
            "weekday_sales_final": [2.608e9, 2.7e9],
        }
    )
    src_path = tmp_path / "src.csv"
    out_path = tmp_path / "out.csv"
    src.to_csv(src_path, index=False, encoding="utf-8-sig")

    adapt_mapo_imputed(src_path, out_path)
    out = pd.read_csv(out_path, dtype={"dong_code": str})

    # _final 값이 base 컬럼에 들어왔어야 함
    assert out.loc[0, "monthly_sales"] == pytest.approx(3.355e9)
    # _final / _pred / _imputed 컬럼은 출력에 남지 않아야 함
    assert "monthly_sales_final" not in out.columns
    assert "monthly_sales_pred" not in out.columns
    assert "monthly_sales_imputed" not in out.columns
    # 필수 base 컬럼은 모두 있어야 함
    for c in [
        "quarter",
        "dong_code",
        "dong_name",
        "industry_code",
        "industry_name",
        "monthly_sales",
        "monthly_count",
        "weekday_sales",
    ]:
        assert c in out.columns


def test_adapt_seoul_imputed_overwrites_monthly_sales(tmp_path):
    """`imputed_sales`가 `monthly_sales`를 덮어써야 한다."""
    src = pd.DataFrame(
        {
            "quarter": [20191],
            "dong_code": ["11440555"],
            "dong_name": ["서교동"],
            "industry_code": ["CS100001"],
            "industry_name": ["한식"],
            "store_count": [88],
            "kosis_index": [111.4],
            "monthly_sales": [None],  # 결측
            "imputed_sales": [3.355e9],  # 채움값
            "is_missing": [True],
            "source": ["v3"],
            "confidence": [0.85],
        }
    )
    src_path = tmp_path / "seoul.csv"
    out_path = tmp_path / "out.csv"
    src.to_csv(src_path, index=False, encoding="utf-8-sig")

    adapt_seoul_imputed(src_path, out_path, db_url=None)  # DB 없이
    out = pd.read_csv(out_path, dtype={"dong_code": str})

    assert out.loc[0, "monthly_sales"] == pytest.approx(3.355e9)
    assert "imputed_sales" not in out.columns
    assert "is_missing" not in out.columns
    assert "source" not in out.columns
    assert "confidence" not in out.columns


def test_adapt_mapo_imputed_preserves_base_when_final_is_nan(tmp_path):
    """`_final`이 NaN인 row는 원본 base 값이 보존되어야 한다."""
    src = pd.DataFrame(
        {
            "quarter": [20191, 20192],
            "dong_code": ["11440555", "11440555"],
            "dong_name": ["서교동", "서교동"],
            "industry_code": ["CS100001", "CS100001"],
            "industry_name": ["한식", "한식"],
            "monthly_sales": [3.4e9, 3.5e9],
            "monthly_sales_final": [3.355e9, None],  # 두 번째 row: NaN
        }
    )
    src_path = tmp_path / "src.csv"
    out_path = tmp_path / "out.csv"
    src.to_csv(src_path, index=False, encoding="utf-8-sig")

    adapt_mapo_imputed(src_path, out_path)
    out = pd.read_csv(out_path, dtype={"dong_code": str})

    assert out.loc[0, "monthly_sales"] == pytest.approx(3.355e9)  # _final 값 적용
    assert out.loc[1, "monthly_sales"] == pytest.approx(3.5e9)  # base 값 보존
