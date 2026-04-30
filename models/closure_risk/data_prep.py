"""
폐업위험도 예측 데이터 전처리 — 레이블 생성 + lag 피처 엔지니어링

build_closure_risk_dataset():
    - district_sales + store_quarterly → 분기별 (dong_code, industry_code) 집계
    - 레이블(고위험=1): 다음 분기 closure_rate > 업종평균×1.5
                       OR store_count 2분기 연속 감소
                       OR monthly_sales 전년동기 -25% 이상
    - lag 피처: closure_rate_lag1/2, store_change, sales_yoy 등
    - 추가 피처: rent_1f_lag1/rent_change(임대료), vacancy_rate(공실률),
                 trend_score(네이버 트렌드), adstrd_flpop(행정동 유동인구)

담당: B2 — 수지니
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _time_based_split(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """quarter 기준 시간순 train/val/test 3분할.

    같은 quarter 데이터는 한 split 에만 들어감 (boundary 명확).
    train + val + test 합 = 100% (남은 부분 = test).

    Args:
        df: "quarter" 컬럼 포함 (예: "2020Q1", "2024Q4").
        train_ratio: 0~1, train 비율.
        val_ratio: 0~1, val 비율. test_ratio = 1 - train_ratio - val_ratio.

    Returns:
        (train_df, val_df, test_df).

    Raises:
        ValueError:
            - 분기 수 < 7 (기본 비율 0.70/0.15 기준 train 4 / val 1 / test 2 최소).
            - train_ratio + val_ratio >= 1.0 (test set 비어있음).
            - quarter 컬럼에 null 값 존재.

    학술 근거:
        Bergmeir & Benítez (2012) "On the use of cross-validation for time series".
        시계열 random split 은 temporal leakage → val_AUC 부풀림.
    """
    null_count = int(df["quarter"].isna().sum())
    if null_count > 0:
        raise ValueError(f"quarter 컬럼에 null {null_count}건. dropna(subset=['quarter']) 또는 fillna() 후 호출하세요.")

    quarters = sorted(df["quarter"].unique())
    n_q = len(quarters)
    if n_q < 7:
        raise ValueError(
            f"분기 수 부족 ({n_q}). 최소 7분기 필요 (train 5 / val 1 / test 1). split_strategy='random' 사용 권장."
        )

    if train_ratio + val_ratio >= 1.0:
        raise ValueError(
            f"train_ratio({train_ratio}) + val_ratio({val_ratio}) >= 1.0: "
            f"test set 이 비어있음. 합 < 1.0 으로 조정 필요."
        )

    train_end_idx = int(n_q * train_ratio) - 1
    val_end_idx = int(n_q * (train_ratio + val_ratio)) - 1
    train_end = quarters[train_end_idx]
    val_end = quarters[val_end_idx]

    train = df[df["quarter"] <= train_end].copy()
    val = df[(df["quarter"] > train_end) & (df["quarter"] <= val_end)].copy()
    test = df[df["quarter"] > val_end].copy()

    return train, val, test


def _compute_industry_p75_train(
    df: pd.DataFrame,
    train_quarters: set[int],
    min_samples: int = 4,
) -> tuple[pd.Series, float]:
    """Train rows 의 industry 별 closure_rate 75 percentile 계산.

    Args:
        df: 전체 dataset (lag feature 까지 적용된 상태).
        train_quarters: train split 분기 set (e.g. {20191, ...}).
        min_samples: industry 별 최소 sample 수. 미만 시 NaN (fallback 대상).

    Returns:
        (industry_p75 Series indexed by industry_code, global_p75 float).
        Sample 부족한 industry 는 industry_p75 에 NaN, 호출자가 fallback 처리.

    Raises:
        ValueError: train_quarters 에 해당 row 0건.

    학술 근거:
        Bergmeir & Benítez (2012) 시계열 leakage 차단 — train-only quantile fit.
    """
    train_df = df[df["quarter"].isin(train_quarters)]
    if len(train_df) == 0:
        raise ValueError(f"train_quarters={train_quarters} 에 해당 row 0건")

    global_p75 = float(train_df["closure_rate"].quantile(0.75))

    counts = train_df.groupby("industry_code")["closure_rate"].size()
    p75 = train_df.groupby("industry_code")["closure_rate"].quantile(0.75)
    p75 = p75.where(counts >= min_samples, np.nan)

    return p75, global_p75


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "processed"

load_dotenv(PROJECT_ROOT / "backend" / ".env")

DB_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://postgres:MapoSpotter1!%23@mapo-simulator.cx8eakyuk1jf.ap-northeast-2.rds.amazonaws.com:5432/mapo_simulator",
)

# LightGBM 브랜치용 lag/정적 피처
LGBM_FEATURES = [
    "closure_rate_lag1",  # 직전 분기 폐업률
    "closure_rate_lag2",  # 2분기 전 폐업률
    "closure_rate_diff",  # 폐업률 변화량 (lag1 - lag2)
    "store_count_lag1",  # 직전 분기 점포 수
    "store_change",  # 점포 수 변화 (현재 - lag1)
    "franchise_ratio",  # 프랜차이즈 비율
    "sales_yoy_change",  # 전년 동기 매출 변화율
    "monthly_sales_lag1",  # 직전 분기 매출 (log1p)
    "bus_flpop",  # 버스 유동인구 (CSV 캐시)
    "quarter_num",  # 계절성 (1~4)
    # 임대료/공실 — build_timeseries()가 RDS(seoul_golmok_rent)에서 실제 로드
    "rent_1f_lag1",  # 직전 분기 1층 환산임대료 (고정비용 지표)
    "rent_change",  # 임대료 변화율 (임대료 상승 → 폐업 위험 ↑)
    "vacancy_rate",  # 공실률 (상권 경기 침체 신호)
    # 상권 수요 — 실제 데이터 존재 확인 (null 0%, zero 9.3%)
    "trend_score",  # 네이버 검색 트렌드 (업종 관심도 감소 → 수요 감소 신호)
    # 유동인구 — adstrd_flpop(null 0%, zero 0%)이 bus_flpop(zero 49%)보다 완전
    "adstrd_flpop",  # 행정동 전체 유동인구
]

# TCN 브랜치는 data_prep.ALL_FEATURES 34개 시계열 그대로 사용


# ---------------------------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------------------------


def _load_from_db(query: str, db_url: str = DB_URL) -> pd.DataFrame:
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url, echo=False)
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(query), conn)
    finally:
        engine.dispose()


def load_base_data(db_url: str = DB_URL, dong_prefix: str = "11440") -> pd.DataFrame:
    """district_sales + store_quarterly 병합 데이터 로드 (마포구 기본)."""
    from models.lstm_forecast.data_prep import (
        build_timeseries,
        load_sales_data,
        load_store_data,
    )

    sales_df = load_sales_data(db_url=db_url, dong_prefix=dong_prefix)
    store_df = load_store_data(db_url=db_url, dong_prefix=dong_prefix)
    ts = build_timeseries(sales_df, store_df)
    return ts


# ---------------------------------------------------------------------------
# 레이블 생성
# ---------------------------------------------------------------------------


def _make_labels(
    df: pd.DataFrame,
    train_quarters: set[int] | None,
    *,
    drop_unseen_industry: bool = True,
) -> pd.DataFrame:
    """단일 quantile 기반 label 생성 (C-B1).

    label = 1 ⟺ next_closure_rate > industry_p75_train.
    train_quarters 의 closure_rate 만으로 p75 fit (leakage 차단).

    Args:
        df: lag feature 까지 적용된 dataset.
        train_quarters: train split 분기 set. None / 빈 set → ValueError.
        drop_unseen_industry: True (default) 이면 train 에 없거나 sample 부족
            (min_samples<4) 인 industry row drop. False 이면 global_p75 fallback.

    Returns:
        df + ["label", "industry_p75"] 컬럼. 마지막 분기 (next 없음) row drop.

    Raises:
        ValueError: train_quarters 가 None 또는 빈 set.
    """
    if not train_quarters:
        raise ValueError("train_quarters 필수 — leakage 차단 위해 None / 빈 set 금지")

    df = df.copy().sort_values(["dong_code", "industry_code", "quarter"])
    gk = ["dong_code", "industry_code"]

    df["next_closure_rate"] = df.groupby(gk)["closure_rate"].shift(-1)

    p75_series, global_p75 = _compute_industry_p75_train(df, train_quarters)
    df["industry_p75"] = df["industry_code"].map(p75_series)

    if drop_unseen_industry:
        unseen_count = int(df["industry_p75"].isna().sum())
        if unseen_count > 0:
            logger.warning("train 에 없거나 sample 부족 industry → %d row drop", unseen_count)
        df = df[df["industry_p75"].notna()].copy()
    else:
        df["industry_p75"] = df["industry_p75"].fillna(global_p75)

    df["label"] = (df["next_closure_rate"] > df["industry_p75"]).astype(int)
    df = df[df["next_closure_rate"].notna()].copy()
    df = df.drop(columns=["next_closure_rate"])

    return df


# ---------------------------------------------------------------------------
# lag 피처 엔지니어링 (LightGBM 브랜치용)
# ---------------------------------------------------------------------------


def _engineer_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """LGBM_FEATURES에 해당하는 lag/파생 피처를 계산한다."""
    df = df.copy().sort_values(["dong_code", "industry_code", "quarter"])
    gk = ["dong_code", "industry_code"]

    # 폐업률 lag
    df["closure_rate_lag1"] = df.groupby(gk)["closure_rate"].shift(1)
    df["closure_rate_lag2"] = df.groupby(gk)["closure_rate"].shift(2)
    df["closure_rate_diff"] = df["closure_rate_lag1"] - df["closure_rate_lag2"]

    # 점포 수 변화
    df["store_count_lag1"] = df.groupby(gk)["store_count"].shift(1)
    df["store_change"] = df["store_count"] - df["store_count_lag1"]

    # 프랜차이즈 비율
    total = df["store_count"].clip(lower=1)
    df["franchise_ratio"] = df.get("franchise_count", pd.Series(0, index=df.index)) / total

    # 전년동기 매출 변화율 (log1p 공간에서 계산)
    df["monthly_sales_lag1"] = df.groupby(gk)["monthly_sales"].shift(1)
    sales_4q = df.groupby(gk)["monthly_sales"].shift(4)
    df["sales_yoy_change"] = (df["monthly_sales"] - sales_4q) / (sales_4q.abs() + 1e-6)

    # 임대료 lag (build_timeseries에서 RDS seoul_golmok_rent로 실제 로드됨)
    if "rent_1f" in df.columns:
        df["rent_1f_lag1"] = df.groupby(gk)["rent_1f"].shift(1)
        df["rent_change"] = (df["rent_1f"] - df["rent_1f_lag1"]) / (df["rent_1f_lag1"].abs() + 1)
    else:
        df["rent_1f_lag1"] = 0.0
        df["rent_change"] = 0.0

    return df


# ---------------------------------------------------------------------------
# 메인 데이터셋 빌드
# ---------------------------------------------------------------------------


def build_closure_risk_dataset(
    db_url: str = DB_URL,
    dong_prefix: str = "11440",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """폐업위험도 학습용 데이터셋 빌드.

    Returns
    -------
    df_full : pd.DataFrame
        전체 데이터 (시계열 포함 — TCN 브랜치 시퀀스 생성용)
    X_lgbm : pd.DataFrame
        LightGBM 브랜치 입력 피처
    y : pd.Series
        레이블 (0/1)
    """
    logger.info("폐업위험도 데이터셋 빌드 중...")
    df = load_base_data(db_url=db_url, dong_prefix=dong_prefix)

    # lag 피처 계산
    df = _engineer_lag_features(df)

    # 레이블 생성
    df = _make_labels(df)

    logger.info(
        "레이블 분포 — 고위험(1): %d / 저위험(0): %d (총 %d)",
        df["label"].sum(),
        (df["label"] == 0).sum(),
        len(df),
    )

    # LightGBM 입력 피처 추출
    missing = [f for f in LGBM_FEATURES if f not in df.columns]
    if missing:
        logger.warning("누락 피처 (0으로 채움): %s", missing)
        for f in missing:
            df[f] = 0.0

    X_lgbm = df[LGBM_FEATURES].fillna(0).astype(float)
    y = df["label"].astype(int)

    return df, X_lgbm, y
