"""Industry-level prior model — A-2 hierarchical Stage 1.

(industry, quarter) 단위 aggregates 로 'industry 평균 next_closure_rate'
예측. Stage 2 (dong-level LGBM) 의 입력 feature `industry_prior_pred` 로 활용.

학술 근거:
    Wolpert, D. H. (1992). "Stacked generalization." Neural Networks 5(2).
    Hierarchical regression — Gelman & Hill (2006).

담당: B2 (수지니) 영역, A1 (찬영) cross-team contribution.
"""

from __future__ import annotations

import logging

import lightgbm as lgb
import pandas as pd

logger = logging.getLogger(__name__)


STAGE1_FEATURES = [
    "ind_closure_rate_lag1",
    "ind_closure_rate_lag2",
    "ind_store_count_lag1",
    "ind_sales_yoy",
]


def _aggregate_industry_quarter(df: pd.DataFrame) -> pd.DataFrame:
    """(industry, quarter) 단위 mean 집계.

    Returns:
        df with columns: industry_code, quarter, ind_closure_rate, ind_store_count,
                         ind_monthly_sales (각각 mean across dong)
    """
    agg = (
        df.groupby(["industry_code", "quarter"])
        .agg(
            ind_closure_rate=("closure_rate", "mean"),
            ind_store_count=("store_count", "mean"),
            ind_monthly_sales=("monthly_sales", "mean"),
        )
        .reset_index()
    )
    return agg


def _engineer_industry_lag(agg: pd.DataFrame) -> pd.DataFrame:
    """industry-level lag/yoy 피처 + next_closure_rate target."""
    agg = agg.sort_values(["industry_code", "quarter"]).copy()
    g = agg.groupby("industry_code")
    agg["ind_closure_rate_lag1"] = g["ind_closure_rate"].shift(1)
    agg["ind_closure_rate_lag2"] = g["ind_closure_rate"].shift(2)
    agg["ind_store_count_lag1"] = g["ind_store_count"].shift(1)
    sales_lag4 = g["ind_monthly_sales"].shift(4)
    agg["ind_sales_yoy"] = (agg["ind_monthly_sales"] - sales_lag4) / (sales_lag4.abs() + 1)
    agg["ind_next_closure_rate"] = g["ind_closure_rate"].shift(-1)
    return agg


def train_industry_prior_stage1(
    df: pd.DataFrame,
    train_quarters: set[int],
) -> tuple[object, pd.DataFrame]:
    """Stage 1 LGBM regressor — industry 평균 next_closure_rate 예측.

    Args:
        df: 전체 dataset (lag feature 적용 + label 포함).
        train_quarters: train split 분기 set.

    Returns:
        (lgbm_model, agg_with_features) — agg 는 모든 (industry, quarter) row +
        STAGE1_FEATURES + industry_prior_pred (predict 후 broadcast 용).

    Raises:
        ValueError: train data < 5 rows.
    """
    agg = _aggregate_industry_quarter(df)
    agg = _engineer_industry_lag(agg)

    train_agg = agg[agg["quarter"].isin(train_quarters) & agg["ind_next_closure_rate"].notna()].copy()

    if len(train_agg) < 5:
        raise ValueError(f"Stage 1 train data 부족: {len(train_agg)} rows (최소 5)")

    X = train_agg[STAGE1_FEATURES].fillna(0).values
    y = train_agg["ind_next_closure_rate"].values

    model = lgb.LGBMRegressor(
        num_leaves=15,
        n_estimators=100,
        learning_rate=0.05,
        random_state=42,
        verbose=-1,
    )
    model.fit(X, y)
    logger.info(
        "Stage 1 industry prior model 학습 완료 — train rows=%d, train_quarters=%d",
        len(train_agg),
        len(train_quarters),
    )
    return model, agg


def predict_industry_prior(
    df: pd.DataFrame,
    model: object,
    agg: pd.DataFrame,
) -> pd.DataFrame:
    """df 에 industry_prior_pred 컬럼 추가 (같은 (industry, quarter) row 에 broadcast).

    Args:
        df: target dataset (dong-level rows).
        model: trained Stage 1 LGBMRegressor.
        agg: industry-quarter aggregates (engineered with STAGE1_FEATURES).

    Returns:
        df with new "industry_prior_pred" column.
    """
    agg = agg.copy()
    X = agg[STAGE1_FEATURES].fillna(0).values
    agg["industry_prior_pred"] = model.predict(X)

    df = df.copy()
    # build_closure_risk_dataset 가 LGBM_FEATURES 누락 컬럼 0 으로 채움 →
    # df 에 이미 industry_prior_pred 존재 가능. merge 시 _x/_y 충돌 방지.
    if "industry_prior_pred" in df.columns:
        df = df.drop(columns=["industry_prior_pred"])
    df = df.merge(
        agg[["industry_code", "quarter", "industry_prior_pred"]],
        on=["industry_code", "quarter"],
        how="left",
    )
    df["industry_prior_pred"] = df["industry_prior_pred"].fillna(0.0)
    return df
