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
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"

load_dotenv(PROJECT_ROOT / "backend" / ".env")

DB_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://postgres:MapoSpotter1!%23@mapo-simulator.cx8eakyuk1jf.ap-northeast-2.rds.amazonaws.com:5432/mapo_simulator",
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

# 연도 정규화 상수 (data_prep + predict 공유 — 한 곳에서만 선언)
YEAR_BASE: int = 2019  # 학습 데이터 최소 연도 (2019Q1 ~ 2024Q4 확인)
YEAR_SCALE: float = 10.0  # 10년 스케일 → 2019=0.0, 2024=0.5, 2029=1.0


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
    """세그먼트 비율을 계산한다.

    연령/성별: 신원 파악된 고객 매출(카드 결제) 기준 → 그룹 합=1.0 보장
    시간대/요일: 전체 monthly_sales 기준 → 그룹 합=1.0 (현금 포함 전 거래에 시간/요일 기록)

    신원 파악 고객 = 연령 데이터가 있는 거래 (카드 결제)
    현금 거래는 시간/요일은 기록되나 연령/성별 미파악 → 연령/성별 분모에서 제외
    """
    df = df.copy()

    # 신원 파악된 고객 매출 (연령 6개 합 = 카드 결제 매출)
    _age_src_cols = [
        c
        for c in [
            "age_10_sales",
            "age_20_sales",
            "age_30_sales",
            "age_40_sales",
            "age_50_sales",
            "age_60_above_sales",
        ]
        if c in df.columns
    ]
    identified_sales = df[_age_src_cols].sum(axis=1).clip(lower=1.0)

    safe_monthly = df["monthly_sales"].clip(lower=1.0)

    # 연령/성별: identified_sales 기준 (현금 익명 거래 제외 → 그룹 합=1.0)
    _age_gender_src = {
        "age_10_sales",
        "age_20_sales",
        "age_30_sales",
        "age_40_sales",
        "age_50_sales",
        "age_60_above_sales",
        "male_sales",
        "female_sales",
    }

    for src_col, ratio_col in _RATIO_MAP.items():
        if src_col not in df.columns:
            df[ratio_col] = 0.0
            continue
        if src_col in _age_gender_src:
            # 신원 파악 고객 기준: 연령 6개 합=1, 성별 2개 합=1
            df[ratio_col] = (df[src_col] / identified_sales).clip(0.0, 1.0)
        else:
            # 시간대/요일: monthly_sales 기준 (전 거래 시간/요일 기록됨 → 합=1.0)
            df[ratio_col] = (df[src_col] / safe_monthly).clip(0.0, 1.0)

    return df


# ---------------------------------------------------------------------------
# 학습 데이터 생성
# ---------------------------------------------------------------------------


def prepare_training_data(
    db_url: str = DB_URL,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict, int]:
    """MLPPredictor 학습용 데이터를 준비한다.

    Returns
    -------
    dong_idx : np.ndarray (N,)  — 동 인덱스
    industry_idx : np.ndarray (N,)  — 업종 인덱스
    quarter_enc : np.ndarray (N, 3)  — [sin, cos, year_norm] 인코딩
    y : np.ndarray (N, 16)  — 세그먼트 비율
    identified_ratios : dict  — {(dong_code, industry_code): float} 업종별 카드 비율
    year_max : int  — 학습 데이터 최대 연도 (mappings 저장용)
    """
    df = load_district_sales(db_url=db_url)
    df = _compute_ratios(df)

    # dong_code / industry_code 인덱스 변환 (알 수 없는 코드는 제외)
    df["dong_code"] = df["dong_code"].astype(str)
    df["industry_code"] = df["industry_code"].astype(str)
    df = df[df["dong_code"].isin(DONG_TO_IDX) & df["industry_code"].isin(INDUSTRY_TO_IDX)]

    if df.empty:
        raise ValueError("학습 데이터가 없습니다. district_sales 테이블을 확인하세요.")

    # 분기 번호: quarter 컬럼 마지막 자리 (예: 20231 → 1), 유효 범위 1~4 필터
    df = df[df["quarter"] % 10 != 0]

    # (동, 업종)별 identified_ratio 딕셔너리 계산
    # monthly_sales == 0 행 제외로 0 나눗셈 방지, clip(0,1)으로 이상치 처리
    _age_src_cols = [
        c
        for c in [
            "age_10_sales",
            "age_20_sales",
            "age_30_sales",
            "age_40_sales",
            "age_50_sales",
            "age_60_above_sales",
        ]
        if c in df.columns
    ]
    df_valid = df[df["monthly_sales"] > 0].copy()
    df_valid["_id_sales"] = df_valid[_age_src_cols].sum(axis=1)
    df_valid["_id_ratio"] = (df_valid["_id_sales"] / df_valid["monthly_sales"]).clip(0.0, 1.0)
    identified_ratios: dict[tuple[str, str], float] = (
        df_valid.groupby(["dong_code", "industry_code"])["_id_ratio"].mean().to_dict()
    )

    dong_idx = df["dong_code"].map(DONG_TO_IDX).values.astype(np.int64)
    industry_idx = df["industry_code"].map(INDUSTRY_TO_IDX).values.astype(np.int64)

    # 연도 추출 (quarter 필터 이후) + 정규화
    years = (df["quarter"].values // 10).astype(np.float32)
    year_norms = (years - YEAR_BASE) / YEAR_SCALE
    year_max = int(years.max())

    quarter_nums = (df["quarter"] % 10).values
    quarter_enc = np.array(
        [
            [math.sin(2 * math.pi * (q - 1) / 4), math.cos(2 * math.pi * (q - 1) / 4), year_norms[i]]
            for i, q in enumerate(quarter_nums)
        ],
        dtype=np.float32,
    )  # shape (N, 3)

    y = df[SEGMENT_COLS].values.astype(np.float32)

    logger.info(
        "학습 데이터 준비 완료: %d samples, year=%d~%d, input=(dong+industry+qenc3), output=16",
        len(y),
        int(years.min()),
        year_max,
    )
    return dong_idx, industry_idx, quarter_enc, y, identified_ratios, year_max


# ---------------------------------------------------------------------------
# 인덱스 매핑 저장/로드 (predict.py에서 사용)
# ---------------------------------------------------------------------------


def save_mappings(
    path: str | Path | None = None,
    identified_ratios: dict | None = None,
    year_max: int | None = None,
) -> None:
    """DONG_TO_IDX, INDUSTRY_TO_IDX, identified_ratios, year_max를 pickle로 저장한다."""
    if path is None:
        path = WEIGHTS_DIR / "segment_mappings.pkl"
    with open(path, "wb") as f:
        pickle.dump(
            {
                "dong_to_idx": DONG_TO_IDX,
                "industry_to_idx": INDUSTRY_TO_IDX,
                "identified_ratios": identified_ratios or {},
                "year_max": year_max or 2024,
            },
            f,
        )
    logger.info("매핑 저장 완료: %s", path)


def load_mappings(path: str | Path | None = None) -> tuple[dict, dict, dict, int]:
    """저장된 매핑을 로드한다.

    Returns
    -------
    dong_to_idx : dict
    industry_to_idx : dict
    identified_ratios : dict  — {(dong_code, industry_code): float}, 없으면 {}
    year_max : int  — 학습 데이터 최대 연도, 없으면 2024
    """
    if path is None:
        path = WEIGHTS_DIR / "segment_mappings.pkl"
    with open(path, "rb") as f:
        data = pickle.load(f)  # noqa: S301
    return (
        data["dong_to_idx"],
        data["industry_to_idx"],
        data.get("identified_ratios", {}),
        data.get("year_max", 2024),
    )
