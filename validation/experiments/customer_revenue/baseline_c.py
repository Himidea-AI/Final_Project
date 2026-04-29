"""C 모델 (customer_revenue) baseline 정의.

3 baseline:
- group_mean: (dong_code, industry_code) 그룹 평균
- global_mean: 전체 평균
- industry_only: industry_code 별 평균
"""

from __future__ import annotations

import pandas as pd


def group_mean_baseline(df: pd.DataFrame, segment_cols: list[str]) -> pd.DataFrame:
    """(dong_code, industry_code) 그룹별 segment_cols 평균."""
    return df.groupby(["dong_code", "industry_code"])[segment_cols].mean()


def global_mean_baseline(df: pd.DataFrame, segment_cols: list[str]) -> pd.Series:
    """전체 평균 segment 비율."""
    return df[segment_cols].mean()


def industry_only_baseline(df: pd.DataFrame, segment_cols: list[str]) -> pd.DataFrame:
    """industry_code 별 평균 (dong 무시)."""
    return df.groupby("industry_code")[segment_cols].mean()
