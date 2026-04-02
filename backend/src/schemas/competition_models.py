"""
경쟁 분석 관련 모델 — 직접경쟁, 간접경쟁, 카니발리제이션 데이터 구조
"""
from pydantic import BaseModel, Field


class DirectCompetition(BaseModel):
    """직접 경쟁 데이터 — 동일 업종"""
    same_category_count: int = 0
    radius_500m: int = 0
    radius_1km: int = 0
    saturation_index: float = 0.0


class CannibalizationImpact(BaseModel):
    """카니발리제이션 영향 — 동일 브랜드 기존 매장"""
    store_address: str
    distance_m: float = 0.0
    revenue_impact_ratio: float = 0.0
    estimated_loss: int = 0


class IndirectCompetition(BaseModel):
    """간접 경쟁 데이터 — 대체재 카테고리"""
    category: str
    store_count: int = 0
    weight: float = 0.5


class CompetitionAnalysis(BaseModel):
    """경쟁 분석 종합 결과"""
    direct: DirectCompetition = Field(default_factory=DirectCompetition)
    cannibalization: list[CannibalizationImpact] = Field(default_factory=list)
    indirect: list[IndirectCompetition] = Field(default_factory=list)
    total_competition_score: float = 0.0
    net_revenue_gain: int = 0
