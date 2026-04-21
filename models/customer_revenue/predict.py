"""
타겟 고객 매출 기여 예측 추론

predict(dong_code, industry_code, profile, monthly_sales) → 세그먼트 기여 매출

담당: B2 — 수지니
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_pw = os.environ.get("POSTGRES_PASSWORD", "postgres")
_host = os.environ.get("POSTGRES_HOST", "192.168.0.28")
_port = os.environ.get("POSTGRES_PORT", "5432")
_db = os.environ.get("POSTGRES_DB", "mapo_simulator")
DB_URL = os.environ.get("POSTGRES_URL", f"postgresql://postgres:{_pw}@{_host}:{_port}/{_db}")

from models.customer_revenue.data_prep import DONG_TO_IDX, INDUSTRY_TO_IDX, load_mappings  # noqa: E402
from models.customer_revenue.model import WEIGHTS_DIR, MLPPredictor, build_model  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 세그먼트 컬럼 → 프로필 매핑
# ---------------------------------------------------------------------------

# 연령대 한글 → 비율 컬럼
_AGE_MAP: dict[str, str] = {
    "10대": "age_10_ratio",
    "20대": "age_20_ratio",
    "30대": "age_30_ratio",
    "40대": "age_40_ratio",
    "50대": "age_50_ratio",
    "60대이상": "age_60_above_ratio",
}

# 성별 → 비율 컬럼
_GENDER_MAP: dict[str, str] = {
    "male": "male_ratio",
    "female": "female_ratio",
}

# 시간대 → 비율 컬럼
_TIME_MAP: dict[str, str] = {
    "time_00_06": "time_00_06_ratio",
    "time_06_11": "time_06_11_ratio",
    "time_11_14": "time_11_14_ratio",
    "time_14_17": "time_14_17_ratio",
    "time_17_21": "time_17_21_ratio",
    "time_21_24": "time_21_24_ratio",
}

# 요일 타입 → 비율 컬럼
_DAY_MAP: dict[str, str] = {
    "weekday": "weekday_ratio",
    "weekend": "weekend_ratio",
}

# 시간대 슬롯 → time_zone 값 매핑 (living_population.time_zone: 1~23)
_TIME_ZONE_MAP: dict[str, tuple[int, ...]] = {
    "time_00_06": (1, 2, 3, 4, 5, 6),
    "time_06_11": (7, 8, 9, 10, 11),
    "time_11_14": (12, 13, 14),
    "time_14_17": (15, 16, 17),
    "time_17_21": (18, 19, 20, 21),
    "time_21_24": (22, 23),
}

# 연령대 → 5세 단위 컬럼 접미사 매핑 (gender prefix 조합: male_/female_)
_AGE_COL_SUFFIXES: dict[str, tuple[str, ...]] = {
    "10대": ("10_14", "15_19"),
    "20대": ("20_24", "25_29"),
    "30대": ("30_34", "35_39"),
    "40대": ("40_44", "45_49"),
    "50대": ("50_54", "55_59"),
    "60대이상": ("60_64", "65_69", "70_74", "70_plus"),
}

# 전체 세그먼트 순서 (model.SEGMENT_COLS와 동기화)
_SEGMENT_COLS = [
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
_SEG_IDX = {col: i for i, col in enumerate(_SEGMENT_COLS)}


# ---------------------------------------------------------------------------
# 프로필 데이터클래스
# ---------------------------------------------------------------------------


@dataclass
class SegmentProfile:
    """타겟 고객 프로필.

    Examples
    --------
    >>> profile = SegmentProfile(
    ...     age_groups=["30대", "40대"],
    ...     gender="female",
    ...     time_slots=["time_11_14", "time_14_17"],
    ...     day_type="weekend",
    ... )
    """

    age_groups: list[str] = field(default_factory=list)
    """연령대 목록. 예: ["20대", "30대"]. 빈 리스트 = 전체 연령 선택."""

    gender: str = "all"
    """성별. "male" | "female" | "all"."""

    time_slots: list[str] = field(default_factory=list)
    """시간대 목록. 예: ["time_11_14", "time_14_17"]. 빈 리스트 = 전체 시간대."""

    day_type: str = "all"
    """요일 타입. "weekday" | "weekend" | "all"."""

    def summary(self) -> str:
        """프로필 한글 요약."""
        parts: list[str] = []
        if self.age_groups:
            parts.append("+".join(self.age_groups))
        if self.gender != "all":
            parts.append("여성" if self.gender == "female" else "남성")
        if self.time_slots:
            parts.append("+".join(self.time_slots))
        if self.day_type != "all":
            parts.append("주말" if self.day_type == "weekend" else "주중")
        return " ".join(parts) if parts else "전체 고객"


# ---------------------------------------------------------------------------
# living_population 교차 비율 캐시 + 로더
# ---------------------------------------------------------------------------

_living_pop_cache: dict[tuple[str, str], float] = {}


def _load_living_pop_ratio(
    dong_code: str,
    profile: SegmentProfile,
    db_url: str = DB_URL,
) -> float | None:
    """living_population 실측값으로 교차 세그먼트 비율을 계산한다.

    프로필(연령×성별×시간대×요일)에 해당하는 생활인구를 집계하여
    해당 동 전체 인구 대비 비율을 반환한다. DB 접속 실패 시 None.

    Parameters
    ----------
    dong_code : str
        행정동 코드 (마포구 16개 동).
    profile : SegmentProfile
        타겟 고객 프로필.
    db_url : str
        PostgreSQL 접속 URL.

    Returns
    -------
    float or None
        교차 세그먼트 비율 (0~1). DB 실패 시 None.
    """
    cache_key = (dong_code, profile.summary())
    if cache_key in _living_pop_cache:
        return _living_pop_cache[cache_key]

    try:
        from sqlalchemy import create_engine, text

        # 시간대 필터
        if profile.time_slots:
            tz_values = []
            for ts in profile.time_slots:
                tz_values.extend(_TIME_ZONE_MAP.get(ts, ()))
            tz_filter = f"AND time_zone IN ({','.join(str(v) for v in tz_values)})"
        else:
            tz_filter = "AND time_zone != 0"  # 일합계(0) 제외, 전체 시간대

        # 요일 필터
        if profile.day_type == "weekday":
            dow_filter = "AND EXTRACT(DOW FROM date) IN (1,2,3,4,5)"
        elif profile.day_type == "weekend":
            dow_filter = "AND EXTRACT(DOW FROM date) IN (0,6)"
        else:
            dow_filter = ""

        # 성별×연령 집계 컬럼 결정
        genders = ["male", "female"] if profile.gender == "all" else [profile.gender]
        age_suffixes: list[str] = []
        if profile.age_groups:
            for ag in profile.age_groups:
                age_suffixes.extend(_AGE_COL_SUFFIXES.get(ag, ()))
        else:
            # 전체 연령: 5세 단위 전체
            all_suffixes = (
                "0_9",
                "10_14",
                "15_19",
                "20_24",
                "25_29",
                "30_34",
                "35_39",
                "40_44",
                "45_49",
                "50_54",
                "55_59",
                "60_64",
                "65_69",
                "70_74",
                "70_plus",
            )
            age_suffixes = list(all_suffixes)

        if age_suffixes:
            seg_cols = " + ".join(f"COALESCE({g}_{s}, 0)" for g in genders for s in age_suffixes)
        else:
            seg_cols = "total_pop"

        query = text(f"""
            SELECT
                SUM({seg_cols}) AS seg_pop,
                SUM(total_pop)  AS total_pop
            FROM living_population
            WHERE dong_code = :dong_code
              {tz_filter}
              {dow_filter}
        """)  # noqa: S608

        engine = create_engine(db_url, echo=False, connect_args={"connect_timeout": 5})
        try:
            with engine.connect() as conn:
                row = conn.execute(query, {"dong_code": dong_code}).fetchone()
        finally:
            engine.dispose()

        if row is None or not row.total_pop:
            return None

        ratio = float(row.seg_pop or 0) / float(row.total_pop)
        ratio = max(0.0, min(ratio, 1.0))
        _living_pop_cache[cache_key] = ratio
        logger.debug("living_pop 교차 비율 [%s %s]: %.4f", dong_code, profile.summary(), ratio)
        return ratio

    except Exception as exc:
        logger.debug("living_pop 조회 실패, MLP fallback: %s", exc)
        return None


# ---------------------------------------------------------------------------
# 모델 캐시
# ---------------------------------------------------------------------------

_cache: dict = {}


def _load_model() -> tuple[MLPPredictor, dict, dict]:
    """모델 + 매핑을 로드한다 (캐시)."""
    global _cache  # noqa: PLW0603
    if _cache:
        return _cache["model"], _cache["dong_to_idx"], _cache["industry_to_idx"]

    weights_path = WEIGHTS_DIR / "customer_mlp.pt"
    if not weights_path.exists():
        raise FileNotFoundError(
            f"MLP 가중치를 찾을 수 없습니다: {weights_path}\n"
            "먼저 학습을 실행하세요: python -m models.customer_revenue.train"
        )

    model = build_model()
    model.load_weights(weights_path)

    try:
        dong_to_idx, industry_to_idx = load_mappings()
    except FileNotFoundError:
        dong_to_idx, industry_to_idx = DONG_TO_IDX, INDUSTRY_TO_IDX

    _cache = {"model": model, "dong_to_idx": dong_to_idx, "industry_to_idx": industry_to_idx}
    logger.info("MLPPredictor 로드 완료")
    return model, dong_to_idx, industry_to_idx


# ---------------------------------------------------------------------------
# 세그먼트 비율 결합 (독립 가정 곱셈)
# ---------------------------------------------------------------------------


def _combined_ratio(
    ratios: np.ndarray,
    profile: SegmentProfile,
    dong_code: str | None = None,
) -> float:
    """
    예측된 세그먼트 비율 벡터(16차원)에서 프로필에 해당하는 결합 비율을 계산한다.

    결합 방식:
        - MLP 독립 가정: (연령 합) × (성별) × (시간대 합) × (요일)
        - living_population 실측 교차 비율과 50:50 가중 평균 (dong_code 있을 때)
        - DB 조회 실패 시 MLP 독립 가정만 사용 (fallback)

    Returns
    -------
    float
        결합 비율 (0~1)
    """
    # 연령 비율 합산
    if profile.age_groups:
        unknown_ages = [ag for ag in profile.age_groups if ag not in _AGE_MAP]
        if unknown_ages:
            logger.warning("알 수 없는 age_group 무시됨: %s", unknown_ages)
        age_ratio = sum(ratios[_SEG_IDX[_AGE_MAP[ag]]] for ag in profile.age_groups if ag in _AGE_MAP)
        age_ratio = min(age_ratio, 1.0)
    else:
        age_ratio = 1.0  # 전체 연령 = 제약 없음

    # 성별 비율
    if profile.gender in _GENDER_MAP:
        gender_ratio = float(ratios[_SEG_IDX[_GENDER_MAP[profile.gender]]])
    else:
        gender_ratio = 1.0

    # 시간대 비율 합산
    if profile.time_slots:
        time_ratio = sum(ratios[_SEG_IDX[_TIME_MAP[ts]]] for ts in profile.time_slots if ts in _TIME_MAP)
        time_ratio = min(time_ratio, 1.0)
    else:
        time_ratio = 1.0

    # 요일 비율
    if profile.day_type in _DAY_MAP:
        day_ratio = float(ratios[_SEG_IDX[_DAY_MAP[profile.day_type]]])
    else:
        day_ratio = 1.0

    mlp_ratio = age_ratio * gender_ratio * time_ratio * day_ratio

    # living_population 실측 교차 비율 보정 (50:50 가중 평균)
    if dong_code:
        living_ratio = _load_living_pop_ratio(dong_code, profile)
        if living_ratio is not None:
            return mlp_ratio * 0.5 + living_ratio * 0.5

    return mlp_ratio


# ---------------------------------------------------------------------------
# 추론 함수
# ---------------------------------------------------------------------------


def predict(
    dong_code: str,
    industry_code: str,
    profile: SegmentProfile,
    monthly_sales: float | None = None,
    quarter_num: int = 1,
    config: dict | None = None,
) -> dict:
    """특정 동×업종에서 타겟 프로필 고객의 예상 매출 기여를 예측한다.

    Parameters
    ----------
    dong_code : str
        행정동 코드 (예: "11440660").
    industry_code : str
        업종 코드 (예: "CS100001").
    profile : SegmentProfile
        타겟 고객 프로필.
    monthly_sales : float, optional
        기준 월 매출. None이면 세그먼트 비율만 반환.
    quarter_num : int
        예측 분기 (1~4). 계절성 반영에 사용.
    config : dict, optional
        설정 오버라이드 (현재 미사용).

    Returns
    -------
    dict
        {
            "segment_ratio": float,       # 전체 매출 대비 세그먼트 비율
            "segment_sales": float | None,# 세그먼트 예상 매출 (monthly_sales 있을 때)
            "total_sales_ref": float | None,
            "profile_summary": str,       # "30대 여성 주말 오후" 형태
            "dimension_ratios": dict,     # 차원별 개별 비율 (디버깅용)
        }
    """
    model, dong_to_idx, industry_to_idx = _load_model()

    if dong_code not in dong_to_idx:
        raise ValueError(f"알 수 없는 dong_code: {dong_code}. 마포구 16개 동만 지원합니다.")
    if industry_code not in industry_to_idx:
        raise ValueError(f"알 수 없는 industry_code: {industry_code}")

    d_idx = torch.tensor([dong_to_idx[dong_code]], dtype=torch.long)
    i_idx = torch.tensor([industry_to_idx[industry_code]], dtype=torch.long)

    angle = 2 * math.pi * (quarter_num - 1) / 4
    q_enc = torch.tensor([[math.sin(angle), math.cos(angle)]], dtype=torch.float32)

    with torch.no_grad():
        ratios = model(d_idx, i_idx, q_enc).squeeze(0).numpy()  # (16,)

    seg_ratio = _combined_ratio(ratios, profile, dong_code=dong_code)
    seg_sales = round(monthly_sales * seg_ratio) if monthly_sales is not None else None

    # 차원별 비율 (디버깅/설명용)
    dimension_ratios = {col: round(float(ratios[idx]), 4) for col, idx in _SEG_IDX.items()}

    return {
        "segment_ratio": round(seg_ratio, 4),
        "segment_sales": seg_sales,
        "total_sales_ref": monthly_sales,
        "profile_summary": profile.summary(),
        "dimension_ratios": dimension_ratios,
    }


def predict_all_dongs(
    industry_code: str,
    profile: SegmentProfile,
    monthly_sales_map: dict[str, float] | None = None,
    quarter_num: int = 1,
) -> list[dict]:
    """마포 16개 동 전체에 대해 세그먼트 예측을 수행하여 비교 분석을 반환한다.

    Parameters
    ----------
    industry_code : str
        업종 코드.
    profile : SegmentProfile
        타겟 고객 프로필.
    monthly_sales_map : dict[str, float], optional
        동코드 → 월 매출 매핑. None이면 비율만 계산.
    quarter_num : int
        예측 분기.

    Returns
    -------
    list[dict]
        각 원소: { dong_code, segment_ratio, segment_sales, rank }
        segment_ratio 내림차순 정렬.
    """
    from models.customer_revenue.data_prep import DONG_CODES

    results = []
    for dong_code in DONG_CODES:
        try:
            monthly_sales = monthly_sales_map.get(dong_code) if monthly_sales_map else None
            result = predict(dong_code, industry_code, profile, monthly_sales, quarter_num)
            result["dong_code"] = dong_code
            results.append(result)
        except Exception as exc:
            logger.warning("dong_code=%s 예측 실패: %s", dong_code, exc)

    results.sort(key=lambda r: r["segment_ratio"], reverse=True)
    for rank, r in enumerate(results, 1):
        r["rank"] = rank

    return results
