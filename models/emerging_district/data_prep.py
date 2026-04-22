"""
신흥 상권 조기 감지 데이터 전처리

load_emerging_data(): district_sales + store_quarterly 병합 (trend_score 포함)
build_windows(): sliding window numpy 배열 생성

담당: B2 — 수지니
참조: models/lstm_forecast/data_prep.py (build_timeseries 재사용)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / "backend" / ".env")

DB_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://postgres:MapoSpotter1!%23@mapo-simulator.cx8eakyuk1jf.ap-northeast-2.rds.amazonaws.com:5432/mapo_simulator",
)

# Autoencoder 입력 피처 (6개)
EMERGING_FEATURES = [
    "monthly_sales",
    "store_count",
    "closure_rate",
    "trend_score",
    "open_count",
    "close_count",
]


def load_emerging_data(
    db_url: str = DB_URL,
    dong_prefix: str = "11440",
) -> pd.DataFrame:
    """district_sales + store_quarterly 병합 시계열 로드.

    lstm_forecast/data_prep.py의 build_timeseries() 재사용.
    trend_score(네이버 트렌드)도 자동 포함됨.

    Parameters
    ----------
    db_url : str
        PostgreSQL 접속 URL.
    dong_prefix : str
        행정동 코드 앞자리 필터 (기본 "11440" = 마포구).

    Returns
    -------
    pd.DataFrame
        시계열 데이터 (quarter, dong_code, industry_code + EMERGING_FEATURES).
    """
    from models.lstm_forecast.data_prep import build_timeseries, load_sales_data, load_store_data  # noqa: E402

    sales_df = load_sales_data(db_url=db_url, dong_prefix=dong_prefix)
    store_df = load_store_data(db_url=db_url, dong_prefix=dong_prefix)
    ts = build_timeseries(sales_df, store_df)

    # 누락 피처 0 패딩
    for col in EMERGING_FEATURES:
        if col not in ts.columns:
            logger.warning("누락 피처 (0으로 채움): %s", col)
            ts[col] = 0.0

    return ts


def build_windows(
    df: pd.DataFrame,
    window_size: int = 8,
) -> tuple[np.ndarray, list[dict], dict]:
    """(dong_code, industry_code) 그룹별 sliding window 시퀀스 생성.

    Parameters
    ----------
    df : pd.DataFrame
        load_emerging_data() 반환값.
    window_size : int
        윈도우 크기 (분기 수, 기본 8).

    Returns
    -------
    X : ndarray shape (N, window_size, n_features)
    meta_rows : list[dict]
        각 window의 메타 {dong_code, industry_code, last_quarter}.
    scalers : dict
        {(dong_code, industry_code): MinMaxScaler} — 추론 시 재사용.
    """
    X_list: list[np.ndarray] = []
    meta_rows: list[dict] = []
    scalers: dict[tuple[str, str], MinMaxScaler] = {}
    gk = ["dong_code", "industry_code"]

    for (dc, ic), group in df.groupby(gk):
        group = group.sort_values("quarter")
        if len(group) < window_size:
            continue

        feat_vals = group[EMERGING_FEATURES].values.astype(np.float32)
        scaler = MinMaxScaler()
        feat_scaled = scaler.fit_transform(feat_vals)
        scalers[(dc, ic)] = scaler

        quarters = group["quarter"].values
        for i in range(len(group) - window_size + 1):
            X_list.append(feat_scaled[i : i + window_size])
            meta_rows.append(
                {
                    "dong_code": dc,
                    "industry_code": ic,
                    "last_quarter": int(quarters[i + window_size - 1]),
                }
            )

    if not X_list:
        raise ValueError("window 생성 실패 — 데이터 부족 (window_size보다 짧은 시계열만 존재)")

    X = np.array(X_list, dtype=np.float32)
    logger.info("window 생성 완료: %d 샘플, shape=%s", len(X), X.shape)
    return X, meta_rows, scalers
