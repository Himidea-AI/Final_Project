# validation/sum_consistency.py
"""Multi-Output 예측 결과의 sum constraint raking post-processing.

5종 constraint × {sales, count} = 10회 적용:
  1) weekday + weekend = monthly
  2) Σ(mon~sun) = monthly
  3) Σ(time_00_06~21_24) = monthly
  4) male + female = monthly
  5) Σ(age_10~60_above) = monthly
"""

from __future__ import annotations

import pandas as pd

SUM_CONSTRAINTS_SALES: list[tuple[list[str], str]] = [
    (["weekday_sales", "weekend_sales"], "monthly_sales"),
    ([f"{d}_sales" for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]], "monthly_sales"),
    ([f"time_{t}_sales" for t in ["00_06", "06_11", "11_14", "14_17", "17_21", "21_24"]], "monthly_sales"),
    (["male_sales", "female_sales"], "monthly_sales"),
    ([f"age_{a}_sales" for a in ["10", "20", "30", "40", "50", "60_above"]], "monthly_sales"),
]

SUM_CONSTRAINTS_COUNT: list[tuple[list[str], str]] = [
    ([c.replace("_sales", "_count") for c in subs], total.replace("_sales", "_count"))
    for subs, total in SUM_CONSTRAINTS_SALES
]


def enforce_sum_consistency(
    pred_df: pd.DataFrame,
    constraints: list[tuple[list[str], str]],
) -> pd.DataFrame:
    """raking: pred_df[sub_cols] *= total / sub_sum.

    sub_sum = 0 인 행은 변경 없음 (division-by-zero 방지).
    """
    df = pred_df.copy()
    for sub_cols, total_col in constraints:
        sub_sum = df[sub_cols].sum(axis=1)
        # sub_sum > 0 인 row 만 raking 적용
        mask = sub_sum > 0
        scale = pd.Series(1.0, index=df.index)
        scale.loc[mask] = df.loc[mask, total_col] / sub_sum.loc[mask]
        for col in sub_cols:
            df[col] = df[col] * scale
    return df
