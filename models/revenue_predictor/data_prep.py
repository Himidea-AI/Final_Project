"""
폐업률 예측 모델 — 학습 데이터 전처리

store_quarterly 테이블(또는 CSV fallback)에서 점포 시계열 데이터를 로드하고
LSTM 입력에 적합한 sliding-window 시퀀스로 변환한다.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column mapping: CSV 원본 컬럼 → 내부 통일 컬럼
# ---------------------------------------------------------------------------
_CSV_COL_MAP = {
    "STDR_YYQU_CD": "quarter",
    "행정동코드": "dong_code",
    "행정동명": "dong_name",
    "SVC_INDUTY_CD": "industry_code",
    "SVC_INDUTY_CD_NM": "industry_name",
    "STOR_CO": "store_count",
    "OPBIZ_STOR_CO": "open_count",
    "CLSBIZ_STOR_CO": "close_count",
    "CLSBIZ_RT": "closure_rate",
    "FRC_STOR_CO": "franchise_count",
}

# 모델 입력 피처 (순서 고정)
FEATURE_COLS = [
    "store_count",
    "open_count",
    "close_count",
    "closure_rate",
    "franchise_count",
    "store_change_rate",
    "franchise_ratio",
    "closure_rate_pred",
]

# 프로젝트 루트 기준 CSV 경로
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MAPO_CSV = _PROJECT_ROOT / "data" / "processed" / "district_stores.csv"
_SEOUL_CSV = _PROJECT_ROOT / "data" / "processed" / "seoul_district_stores.csv"

# DB 접속 정보 (환경변수 우선)
_DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@192.168.0.28:5432/mapo_simulator")


# ---------------------------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------------------------


def _load_from_db(query: str) -> pd.DataFrame | None:
    """PostgreSQL에서 데이터를 로드한다. 실패 시 None 반환."""
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(_DB_URL)
        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn)
        logger.info("DB 로드 성공: %d rows", len(df))
        return df
    except Exception as exc:  # noqa: BLE001
        logger.warning("DB 로드 실패 — CSV fallback 사용: %s", exc)
        return None


def _load_csv(path: Path) -> pd.DataFrame:
    """CSV 파일을 로드하고 컬럼명을 통일한다."""
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.rename(columns=_CSV_COL_MAP, inplace=True)
    return df


def load_store_data(*, seoul: bool = False) -> pd.DataFrame:
    """
    점포 시계열 데이터를 로드한다.

    Args:
        seoul: True이면 서울 전체 데이터, False이면 마포구 데이터

    Returns:
        DataFrame with unified column names
    """
    if seoul:
        # 서울 전체: DB 우선, CSV fallback
        df = _load_from_db(
            "SELECT quarter, dong_code, dong_name, industry_code, industry_name, "
            "store_count, open_count, close_count, closure_rate, franchise_count "
            "FROM store_quarterly"
        )
        if df is None and _SEOUL_CSV.exists():
            df = _load_csv(_SEOUL_CSV)
        if df is None:
            logger.warning("서울 전체 데이터 없음 — 마포구 데이터로 대체")
            return load_store_data(seoul=False)
        return df

    # 마포구: DB 우선, CSV fallback
    df = _load_from_db(
        "SELECT quarter, dong_code, dong_name, industry_code, industry_name, "
        "store_count, open_count, close_count, closure_rate, franchise_count "
        "FROM store_quarterly WHERE dong_code::text LIKE '1144%'"
    )
    if df is None and _MAPO_CSV.exists():
        df = _load_csv(_MAPO_CSV)
    if df is None:
        raise FileNotFoundError("마포구 점포 데이터를 찾을 수 없습니다 (DB/CSV 모두 실패)")
    return df


# ---------------------------------------------------------------------------
# 피처 엔지니어링
# ---------------------------------------------------------------------------


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    파생 피처를 생성한다.

    추가되는 컬럼:
        - store_change_rate: 점포 증감률 (이전 분기 대비)
        - franchise_ratio:   프랜차이즈 비율 (franchise_count / store_count)
        - closure_rate_pred: 폐업률 (closure_rate/100, 0~1 스케일)
    """
    df = df.copy()

    # 수치형 변환
    for col in ["store_count", "open_count", "close_count", "closure_rate", "franchise_count"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # 그룹별 정렬 (동×업종×시간순)
    df.sort_values(["dong_code", "industry_code", "quarter"], inplace=True)

    # 점포 증감률
    df["store_change_rate"] = df.groupby(["dong_code", "industry_code"])["store_count"].pct_change().fillna(0)
    # inf 처리
    df["store_change_rate"] = df["store_change_rate"].replace([np.inf, -np.inf], 0).clip(-1, 1)

    # 프랜차이즈 비율
    df["franchise_ratio"] = np.where(df["store_count"] > 0, df["franchise_count"] / df["store_count"], 0)

    # 폐업률 (0~1 스케일)
    df["closure_rate_pred"] = (df["closure_rate"] / 100).clip(0, 1)

    return df


# ---------------------------------------------------------------------------
# Sliding window 시퀀스 생성
# ---------------------------------------------------------------------------


def create_sequences(
    df: pd.DataFrame,
    window_size: int = 6,
    target_col: str = "closure_rate_pred",
) -> tuple[np.ndarray, np.ndarray]:
    """
    동×업종 단위로 sliding window 시퀀스를 생성한다.

    Args:
        df: engineer_features()의 출력
        window_size: 입력 시퀀스 길이 (분기 수)
        target_col: 예측 대상 컬럼

    Returns:
        (X, y) where
            X: shape (N, window_size, n_features)
            y: shape (N,)  — 다음 분기 폐업률
    """
    sequences: list[np.ndarray] = []
    targets: list[float] = []

    grouped = df.groupby(["dong_code", "industry_code"])
    for _, group in grouped:
        if len(group) <= window_size:
            continue
        features = group[FEATURE_COLS].values  # (T, F)
        target = group[target_col].values
        for i in range(len(group) - window_size):
            sequences.append(features[i : i + window_size])
            targets.append(target[i + window_size])

    if not sequences:
        raise ValueError("시퀀스를 생성할 수 없습니다 — 데이터가 부족합니다")

    return np.array(sequences, dtype=np.float32), np.array(targets, dtype=np.float32)


# ---------------------------------------------------------------------------
# 정규화 + train/val 분할
# ---------------------------------------------------------------------------


def normalize_and_split(
    X: np.ndarray,
    y: np.ndarray,
    val_ratio: float = 0.2,
    scaler: MinMaxScaler | None = None,
) -> dict:
    """
    MinMax 정규화 후 train/val 분할.

    Args:
        X: (N, window_size, n_features)
        y: (N,)
        val_ratio: validation 비율
        scaler: 기존 scaler (None이면 새로 fit)

    Returns:
        dict with keys: X_train, X_val, y_train, y_val, scaler
    """
    n_samples, window_size, n_features = X.shape

    # 2D로 reshape → fit/transform → 원복
    X_flat = X.reshape(-1, n_features)
    if scaler is None:
        scaler = MinMaxScaler()
        X_flat = scaler.fit_transform(X_flat)
    else:
        X_flat = scaler.transform(X_flat)
    X_scaled = X_flat.reshape(n_samples, window_size, n_features).astype(np.float32)

    # 시간순 분할 (셔플하지 않음 — 시계열이므로)
    split_idx = int(n_samples * (1 - val_ratio))
    return {
        "X_train": X_scaled[:split_idx],
        "X_val": X_scaled[split_idx:],
        "y_train": y[:split_idx],
        "y_val": y[split_idx:],
        "scaler": scaler,
    }


# ---------------------------------------------------------------------------
# 통합 파이프라인
# ---------------------------------------------------------------------------


def prepare_training_data(
    *,
    seoul: bool = False,
    window_size: int = 6,
    val_ratio: float = 0.2,
) -> dict:
    """
    학습 데이터 전처리 전체 파이프라인.

    Returns:
        dict: X_train, X_val, y_train, y_val, scaler, feature_cols
    """
    df = load_store_data(seoul=seoul)
    df = engineer_features(df)
    X, y = create_sequences(df, window_size=window_size)
    result = normalize_and_split(X, y, val_ratio=val_ratio)
    result["feature_cols"] = FEATURE_COLS
    return result
