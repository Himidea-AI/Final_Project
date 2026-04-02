"""
행정동별 데이터 모델 — 각 동의 상권/인구/경쟁 데이터 구조
"""
from pydantic import BaseModel, Field


class FloatingPopulation(BaseModel):
    """유동인구 데이터"""
    weekday: int = 0
    weekend: int = 0
    peak_hour: str = ""


class ResidentPopulation(BaseModel):
    """주거인구 데이터"""
    total: int = 0
    age_20_39_ratio: float = 0.0


class DistrictProfile(BaseModel):
    """행정동 프로필 — 종합 데이터"""
    district_name: str
    floating_population: FloatingPopulation = Field(default_factory=FloatingPopulation)
    resident_population: ResidentPopulation = Field(default_factory=ResidentPopulation)
    rent_avg: int = 0
    closure_rate: float = 0.0
    business_density: float = 0.0
