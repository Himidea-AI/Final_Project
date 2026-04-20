"""
타겟 고객 매출 기여 예측 — 데이터 전처리

district_sales에서 연령/성별/시간대/요일 세그먼트 비율을 계산하여
MLPPredictor 학습용 (X, y) 배열을 생성한다.

동코드/업종코드 인덱스 매핑은 학습 시 결정되어 weights/와 함께 저장된다.

담당: B2 — 수지니
"""

from __future__ import annotations

import logging
import math
import os
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"

_pw = os.environ.get("POSTGRES_PASSWORD", "postgres")
_host = os.environ.get("POSTGRES_HOST", "192.168.0.28")
_port = os.environ.get("POSTGRES_PORT", "5432")
_db = os.environ.get("POSTGRES_DB", "mapo_simulator")
DB_URL = os.environ.get(
    "POSTGRES_URL",
    f"postgresql://postgres:{_pw}@{_host}:{_port}/{_db}",
)

# 세그먼트 비율 컬럼 (모델 출력 16개)
SEGMENT_COLS = [
    "age_10_ratio",
    "age_20_ratio",
    "age_30_ratio",
    "age_40_ratio",
    "age_50_ratio",
    "age_60_above_ratio",
    "male_ratio",
    "female_ratio",
    "time_00_06_ratio",
    "time_06_11_ratio",
    "time_11_14_ratio",
    "time_14_17_ratio",
    "time_17_21_ratio",
    "time_21_24_ratio",
    "weekday_ratio",
    "weekend_ratio",
]

# 세그먼트 원본 컬럼 → 비율 컬럼 매핑
_RATIO_MAP: dict[str, str] = {
    "age_10_sales": "age_10_ratio",
    "age_20_sales": "age_20_ratio",
    "age_30_sales": "age_30_ratio",
    "age_40_sales": "age_40_ratio",
    "age_50_sales": "age_50_ratio",
    "age_60_above_sales": "age_60_above_ratio",
    "male_sales": "male_ratio",
    "female_sales": "female_ratio",
    "time_00_06_sales": "time_00_06_ratio",
    "time_06_11_sales": "time_06_11_ratio",
    "time_11_14_sales": "time_11_14_ratio",
    "time_14_17_sales": "time_14_17_ratio",
    "time_17_21_sales": "time_17_21_ratio",
    "time_21_24_sales": "time_21_24_ratio",
    "weekday_sales": "weekday_ratio",
    "weekend_sales": "weekend_ratio",
}

# 마포구 16개 동 코드 (고정 순서 — 인덱스 기준)
DONG_CODES = [
    "11440555",
    "11440565",
    "11440585",
    "11440590",
    "11440600",
    "11440610",
    "11440630",
    "11440655",
    "11440660",
    "11440680",
    "11440690",
    "11440700",
    "11440710",
    "11440720",
    "11440730",
    "11440740",
]

# 업종 코드 (고정 순서 — 인덱스 기준)
INDUSTRY_CODES = [
    "CS100001",
    "CS100002",
    "CS100003",
    "CS100004",
    "CS100005",
    "CS100006",
    "CS100007",
    "CS100008",
    "CS100009",
    "CS100010",
]

DONG_TO_IDX: dict[str, int] = {c: i for i, c in enumerate(DONG_CODES)}
INDUSTRY_TO_IDX: dict[str, int] = {c: i for i, c in enumerate(INDUSTRY_CODES)}


# ---------------------------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------------------------


def load_district_sales(db_url: str = DB_URL) -> pd.DataFrame:
    """district_sales 테이블을 로드한다 (마포구 필터)."""
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url, echo=False, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as conn:
            df = pd.read_sql(
                text(
                    "SELECT * FROM district_sales "
                    "WHERE dong_code::text LIKE '11440%' "
                    "ORDER BY quarter, dong_code, industry_code"
                ),
                conn,
            )
        logger.info("district_sales 로드 완료: %d rows", len(df))
        return df
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# 세그먼트 비율 계산
# ---------------------------------------------------------------------------


def _compute_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """monthly_sales 대비 각 세그먼트 비율을 계산한다."""
    df = df.copy()
    safe_total = df["monthly_sales"].clip(lower=1.0)  # 0 나누기 방지

    for src_col, ratio_col in _RATIO_MAP.items():
        if src_col in df.columns:
            df[ratio_col] = (df[src_col] / safe_total).clip(0.0, 1.0)
        else:
            df[ratio_col] = 0.0

    return df


# ---------------------------------------------------------------------------
# 분기 인코딩 (sin/cos)
# ---------------------------------------------------------------------------


def _quarter_encoding(quarter_num: int | float) -> tuple[float, float]:
    """분기 번호(1~4)를 sin/cos 인코딩으로 변환한다."""
    angle = 2 * math.pi * (quarter_num - 1) / 4
    return math.sin(angle), math.cos(angle)


# ---------------------------------------------------------------------------
# 학습 데이터 생성
# ---------------------------------------------------------------------------


def prepare_training_data(
    db_url: str = DB_URL,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """MLPPredictor 학습용 데이터를 준비한다.

    Returns
    -------
    dong_idx : np.ndarray (N,)  — 동 인덱스
    industry_idx : np.ndarray (N,)  — 업종 인덱스
    quarter_enc : np.ndarray (N, 2)  — sin/cos 인코딩
    y : np.ndarray (N, 16)  — 세그먼트 비율
    """
    df = load_district_sales(db_url=db_url)
    df = _compute_ratios(df)

    # dong_code / industry_code 인덱스 변환 (알 수 없는 코드는 제외)
    df["dong_code"] = df["dong_code"].astype(str)
    df["industry_code"] = df["industry_code"].astype(str)
    df = df[df["dong_code"].isin(DONG_TO_IDX) & df["industry_code"].isin(INDUSTRY_TO_IDX)]

    if df.empty:
        raise ValueError("학습 데이터가 없습니다. district_sales 테이블을 확인하세요.")

    dong_idx = df["dong_code"].map(DONG_TO_IDX).values.astype(np.int64)
    industry_idx = df["industry_code"].map(INDUSTRY_TO_IDX).values.astype(np.int64)

    # 분기 번호: quarter 컬럼 마지막 자리 (예: 20231 → 1), 유효 범위 1~4 필터
    df = df[df["quarter"] % 10 != 0]
    quarter_nums = (df["quarter"] % 10).values
    quarter_enc = np.array(
        [_quarter_encoding(q) for q in quarter_nums],
        dtype=np.float32,
    )

    y = df[SEGMENT_COLS].values.astype(np.float32)

    logger.info(
        "학습 데이터 준비 완료: %d samples, input=(dong+industry+qenc), output=16",
        len(dong_idx),
    )
    return dong_idx, industry_idx, quarter_enc, y


# ---------------------------------------------------------------------------
# 인덱스 매핑 저장/로드 (predict.py에서 사용)
# ---------------------------------------------------------------------------


def save_mappings(path: str | Path | None = None) -> None:
    """DONG_TO_IDX, INDUSTRY_TO_IDX를 pickle로 저장한다."""
    if path is None:
        path = WEIGHTS_DIR / "segment_mappings.pkl"
    with open(path, "wb") as f:
        pickle.dump({"dong_to_idx": DONG_TO_IDX, "industry_to_idx": INDUSTRY_TO_IDX}, f)
    logger.info("매핑 저장 완료: %s", path)


def load_mappings(path: str | Path | None = None) -> tuple[dict, dict]:
    """저장된 매핑을 로드한다."""
    if path is None:
        path = WEIGHTS_DIR / "segment_mappings.pkl"
    with open(path, "rb") as f:
        data = pickle.load(f)  # noqa: S301
    return data["dong_to_idx"], data["industry_to_idx"]
