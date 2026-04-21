"""Pydantic schemas for trend_forecaster agent output.

설계 원칙:
- LLM structured output이 생성하는 필드만 이 모듈에서 정의.
- 정량 데이터(industry_trend/dong_trend/change_ix/macro samples)는 코드에서 별도 조립.
- Output 최종 report는 노드에서 LLM 결과 + 정량 데이터 합성해 dict로 리턴.
"""

from typing import Literal

from pydantic import BaseModel, Field


class TrendForecastOutput(BaseModel):
    """trend_forecaster LLM structured output."""

    forecast_score: int = Field(
        ge=0,
        le=100,
        description="향후 12개월 종합 전망 점수 0-100 (100에 가까울수록 진출 긍정)",
    )
    forecast_direction: Literal[
        "strong_growth",
        "growth",
        "stable",
        "decline",
        "strong_decline",
    ] = Field(description="향후 12개월 방향성 분류")
    forecast_confidence: Literal["high", "medium", "low"] = Field(
        description="분석 신뢰도 — 데이터 최신성·일관성에 따라 결정",
    )
    key_drivers: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="주요 성장/안정 동인 (구체적 수치 근거 포함)",
    )
    risks: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="리스크 요인 (구체적 수치 근거 포함)",
    )
    narrative: str = Field(
        description="본사 영업팀 보고용 3-5문장 종합 요약 — 업종/지역/상권/거시 순으로",
    )
