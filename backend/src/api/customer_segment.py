"""customer_segment REST API — /simulate와 무관한 독립 호출.

LangGraph 전체 파이프라인 없이 customer_revenue MLP만 호출하여
~100ms 안에 segment 분석 결과 반환. frontend 실시간 미리보기용.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agents.tools import MarketDataTool as _MarketDataTool
from src.services.dong_resolver import resolve_dong_code

router = APIRouter(prefix="/customer-segment", tags=["customer-segment"])

_BIZ_TO_INDUSTRY_CODE: dict[str, str] = _MarketDataTool._SALES_CODE_MAP


class SegmentRequest(BaseModel):
    target_district: str = Field(description="마포구 행정동명 (예: '서교동')")
    business_type: str = Field(description="업종 한글명 (예: '카페')")
    target_age_groups: list[str] = Field(default_factory=list)
    target_gender: str | None = Field(default=None, description="'male' | 'female' | None")
    target_time_slots: list[str] = Field(default_factory=list)
    target_day_type: str | None = Field(default=None, description="'weekday' | 'weekend' | None")
    target_monthly_sales: int | None = Field(default=None)
    quarter_num: int = Field(default=1, ge=1, le=4)


class SegmentResponse(BaseModel):
    segment_ratio: float
    segment_sales: float | None = None
    identified_sales: float | None = None
    total_sales_ref: float | None = None
    profile_summary: str
    dimension_ratios: dict[str, float] = Field(default_factory=dict)


@router.post("", response_model=SegmentResponse)
def predict_segment(body: SegmentRequest) -> dict:
    """타겟 고객 매출 기여 예측 — MLP 모델 직접 호출."""
    # dong/industry 코드 변환
    dong_code = resolve_dong_code(body.target_district)
    if not dong_code:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 행정동: '{body.target_district}'. 마포구 16동만 지원.",
        )
    if body.business_type not in _BIZ_TO_INDUSTRY_CODE:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 업종: '{body.business_type}'. (silent fallback 차단 — 잘못된 결과 예방)",
        )
    industry_code = _BIZ_TO_INDUSTRY_CODE[body.business_type]

    # SegmentProfile dict 변환
    profile = None
    if body.target_age_groups or body.target_gender or body.target_time_slots or body.target_day_type:
        profile = {
            "age_groups": body.target_age_groups,
            "gender": body.target_gender,
            "time_slots": body.target_time_slots,
            "day_type": body.target_day_type,
        }

    # MLP 호출
    from models.interface import _run_customer_revenue

    try:
        result = _run_customer_revenue(
            dong_code,
            industry_code,
            profile_dict=profile,
            monthly_sales=body.target_monthly_sales,
            quarter_num=body.quarter_num,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"MLP 가중치 없음: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"세그먼트 분석 실패: {exc}") from exc

    return result
