"""
생활인구 시계열 데이터 전처리 — 동×시간대 분기 집계 시계열 생성

living_population(일별 × 시간대) → 분기 평균 집계 → 슬라이딩 윈도우 시퀀스

집계 단위: (dong_code, time_zone, quarter)
  - total_avg_pop  : 분기 전체 평균 유동인구 (타겟)
  - weekday_avg_pop: 평일 평균
  - weekend_avg_pop: 주말 평균

담당: B2 — 수지니
참조: models/lstm_forecast/data_prep.py (DB 접속 패턴 동일)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from dotenv import load_dotenv
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 경로 / DB 접속
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "processed"

load_dotenv(PROJECT_ROOT / "backend" / ".env")

DB_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://postgres:MapoSpotter1!%23@mapo-simulator.cx8eakyuk1jf.ap-northeast-2.rds.amazonaws.com:5432/mapo_simulator",
)

# ---------------------------------------------------------------------------
# 피처 정의
# ---------------------------------------------------------------------------

# 입력 피처 (스케일링 대상)
POP_FEATURES = [
    "total_avg_pop",  # 분기 전체 평균 유동인구 (타겟 겸 피처)
    "weekday_avg_pop",  # 평일 평균
    "weekend_avg_pop",  # 주말 평균
    "time_zone_norm",  # 시간대 정규화 (0~1)
    "quarter_num",  # 계절성 (1~4)
]

TARGET_COL = "total_avg_pop"


# ---------------------------------------------------------------------------
# DB 유틸
# ---------------------------------------------------------------------------


def _load_from_db(query: str, db_url: str = DB_URL) -> pd.DataFrame:
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url, echo=False)
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(query), conn)
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# 데이터 로드 및 집계
# ---------------------------------------------------------------------------


def load_living_population(
    db_url: str = DB_URL,
    csv_path: str | Path | None = None,
) -> pd.DataFrame:
    """living_population을 동×시간대×분기 집계로 로드한다.

    CSV 캐시(data/processed/living_pop_quarterly.csv) 우선,
    없으면 DB 집계.

    Returns
    -------
    pd.DataFrame
        컬럼: quarter (int), dong_code, dong_name, time_zone,
               total_avg_pop, weekday_avg_pop, weekend_avg_pop
    """
    cache_csv = Path(csv_path) if csv_path else DATA_DIR / "living_pop_quarterly.csv"

    if cache_csv.exists():
        df = pd.read_csv(cache_csv, dtype={"dong_code": str})
        df["quarter"] = df["quarter"].astype(int)
        logger.info("생활인구 CSV 로드: %s (%d rows)", cache_csv, len(df))
        return df

    logger.info("living_population DB 집계 중...")
    try:
        df = _load_from_db(
            """
            SELECT
                (EXTRACT(YEAR FROM date)::int * 10
                 + EXTRACT(QUARTER FROM date)::int) AS quarter,
                dong_code,
                dong_name,
                time_zone,
                AVG(total_pop)                                           AS total_avg_pop,
                AVG(CASE WHEN EXTRACT(DOW FROM date) NOT IN (0, 6)
                         THEN total_pop END)                            AS weekday_avg_pop,
                AVG(CASE WHEN EXTRACT(DOW FROM date) IN (0, 6)
                         THEN total_pop END)                            AS weekend_avg_pop
            FROM living_population
            GROUP BY quarter, dong_code, dong_name, time_zone
            ORDER BY dong_code, time_zone, quarter
            """,
            db_url,
        )
        df["dong_code"] = df["dong_code"].astype(str)
        df["quarter"] = df["quarter"].astype(int)
        logger.info("DB 집계 완료: %d rows", len(df))

        # CSV 캐시 저장
        cache_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_csv, index=False)
        logger.info("CSV 캐시 저장: %s", cache_csv)

        return df
    except Exception as exc:
        raise FileNotFoundError(f"living_population 로드 실패. DB: {exc}") from exc


# ---------------------------------------------------------------------------
# 피처 엔지니어링
# ---------------------------------------------------------------------------


def build_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    """집계 데이터에 파생 피처를 추가하고 정렬한다."""
    df = df.copy()

    # 시간대 정규화 (0~23 → 0~1)
    df["time_zone_norm"] = df["time_zone"] / 23.0

    # 계절성 (분기 번호 1~4)
    df["quarter_num"] = (df["quarter"] % 10).astype(float)

    # 코로나 시기 가중치 (2020~2021 → 0.5)
    year = df["quarter"] // 10
    df["sample_weight"] = np.where((year >= 2020) & (year <= 2021), 0.5, 1.0)

    # 결측치 처리 (그룹별 선형 보간)
    gk = ["dong_code", "time_zone"]
    for col in ["total_avg_pop", "weekday_avg_pop", "weekend_avg_pop"]:
        df[col] = df.groupby(gk)[col].transform(lambda x: x.interpolate(method="linear", limit_direction="both"))
        df[col] = df.groupby(gk)[col].transform(lambda x: x.ffill().bfill())
        df[col] = df[col].fillna(0).astype(float)

    df = df.sort_values(["dong_code", "time_zone", "quarter"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# 시퀀스 생성
# ---------------------------------------------------------------------------


def prepare_sequences(
    data: pd.DataFrame,
    window_size: int = 8,
    target_col: str = TARGET_COL,
    feature_cols: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, MinMaxScaler, MinMaxScaler, np.ndarray]:
    """(dong_code, time_zone) 그룹별 sliding window 시퀀스를 생성한다.

    Parameters
    ----------
    data : pd.DataFrame
        build_timeseries() 출력.
    window_size : int
        입력 시퀀스 길이 (분기 수). 기본 8 = 2년.
    target_col : str
        예측 대상 컬럼 (기본 total_avg_pop).
    feature_cols : list[str], optional
        입력 피처. None이면 POP_FEATURES 사용.

    Returns
    -------
    X : np.ndarray, shape (N, window_size, n_features)
    y : np.ndarray, shape (N, 1)
    feature_scaler : MinMaxScaler
    target_scaler : MinMaxScaler
    sample_weights : np.ndarray, shape (N,)
    """
    if feature_cols is None:
        feature_cols = [c for c in POP_FEATURES if c in data.columns]

    if target_col not in feature_cols and target_col in data.columns:
        feature_cols = feature_cols + [target_col]
    feature_cols = [c for c in feature_cols if c in data.columns]

    if not feature_cols:
        raise ValueError("사용 가능한 피처 컬럼이 없습니다.")

    feat_scaler = MinMaxScaler()
    tgt_scaler = MinMaxScaler()
    feat_scaler.fit(data[feature_cols].values.astype(np.float32))
    tgt_scaler.fit(data[[target_col]].values.astype(np.float32))

    X_list: list[np.ndarray] = []
    y_list: list[np.ndarray] = []
    w_list: list[float] = []
    has_weight = "sample_weight" in data.columns

    for (_dong, _tz), group in data.groupby(["dong_code", "time_zone"]):
        if len(group) <= window_size:
            continue
        feat_vals = feat_scaler.transform(group[feature_cols].values.astype(np.float32))
        tgt_vals = tgt_scaler.transform(group[[target_col]].values.astype(np.float32))
        weights = group["sample_weight"].values if has_weight else np.ones(len(group))

        for i in range(len(group) - window_size):
            X_list.append(feat_vals[i : i + window_size])
            y_list.append(tgt_vals[i + window_size])
            w_list.append(float(weights[i + window_size]))

    if not X_list:
        raise ValueError(f"시퀀스를 생성할 수 없습니다. window_size={window_size}보다 긴 시계열이 없습니다.")

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    w = np.array(w_list, dtype=np.float32)
    return X, y, feat_scaler, tgt_scaler, w


# ---------------------------------------------------------------------------
# DataLoader 생성
# ---------------------------------------------------------------------------


def prepare_dataloaders(
    config: dict,
) -> tuple[DataLoader, DataLoader, MinMaxScaler, MinMaxScaler, int]:
    """config 기반으로 학습/검증 DataLoader를 생성한다."""
    db_url = config.get("db_url", DB_URL)
    csv_path = config.get("csv_path", None)
    window_size = config.get("window_size", 8)
    batch_size = config.get("batch_size", 64)
    val_ratio = config.get("val_ratio", 0.2)
    target_col = config.get("target_col", TARGET_COL)
    feature_cols = config.get("feature_cols", None)

    df = load_living_population(db_url=db_url, csv_path=csv_path)
    df = build_timeseries(df)
    logger.info(
        "시계열 구성 완료: %s (%d 동 × 24 시간대)",
        df.shape,
        df["dong_code"].nunique(),
    )

    X, y, feat_scaler, tgt_scaler, w = prepare_sequences(
        df, window_size=window_size, target_col=target_col, feature_cols=feature_cols
    )
    logger.info("시퀀스 생성 완료: X=%s, y=%s", X.shape, y.shape)

    input_size = X.shape[2]
    n_val = max(1, int(len(X) * val_ratio))
    n_train = len(X) - n_val

    X_train, X_val = X[:n_train], X[n_train:]
    y_train, y_val = y[:n_train], y[n_train:]
    w_train = w[:n_train]

    train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train), torch.from_numpy(w_train))
    val_ds = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    return train_loader, val_loader, feat_scaler, tgt_scaler, input_size
