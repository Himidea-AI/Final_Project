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

import pandas as pd
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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
    "rent_change",   # 임대료 변화율 (임대료 상승 → 폐업 위험 ↑)
    "vacancy_rate",  # 공실률 (상권 경기 침체 신호)
    # 상권 수요 — 실제 데이터 존재 확인 (null 0%, zero 9.3%)
    "trend_score",   # 네이버 검색 트렌드 (업종 관심도 감소 → 수요 감소 신호)
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


def _make_labels(df: pd.DataFrame) -> pd.DataFrame:
    """다음 분기 기준 3중 조건 고위험 레이블 생성.

    조건 (하나라도 해당 → 1):
        ① 다음 분기 closure_rate > 업종 전체 평균 × 1.5
        ② 다음 2분기 연속 store_count 감소
        ③ 다음 분기 monthly_sales 전년동기 대비 -25% 이상
    """
    df = df.copy().sort_values(["dong_code", "industry_code", "quarter"])
    gk = ["dong_code", "industry_code"]

    # 다음 분기 값 shift
    df["next_closure_rate"] = df.groupby(gk)["closure_rate"].shift(-1)
    df["next_store_count"] = df.groupby(gk)["store_count"].shift(-1)
    df["next2_store_count"] = df.groupby(gk)["store_count"].shift(-2)
    df["next_monthly_sales"] = df.groupby(gk)["monthly_sales"].shift(-1)

    # 전년동기 매출 (4분기 전)
    df["sales_4q_ago"] = df.groupby(gk)["monthly_sales"].shift(4)

    # 업종별 평균 closure_rate (분기 전체 기준)
    # 업종별 전 분기 통합 평균 (시계열 leakage 아님 — 임계값 기준선으로만 사용)
    industry_avg = df.groupby("industry_code")["closure_rate"].transform("mean")

    # 조건 ①: 다음 분기 폐업률 > 업종 평균 × 1.5
    cond1 = df["next_closure_rate"] > industry_avg * 1.5

    # 조건 ②: 다음 2분기 연속 store_count 감소
    cond2 = (df["next_store_count"] < df["store_count"]) & (df["next2_store_count"] < df["next_store_count"])

    # 조건 ③: 다음 분기 매출 전년동기 -25% 이상 하락
    yoy_change = (df["next_monthly_sales"] - df["sales_4q_ago"]) / (df["sales_4q_ago"].abs() + 1e-6)
    cond3 = yoy_change < -0.25

    df["label"] = (cond1 | cond2 | cond3).astype(int)

    # 다음 분기 데이터 없는 마지막 행 제거
    df = df[df["next_closure_rate"].notna()].copy()

    # 임시 컬럼 제거
    drop_cols = ["next_closure_rate", "next_store_count", "next2_store_count", "next_monthly_sales", "sales_4q_ago"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

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
