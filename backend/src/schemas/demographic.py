"""Pydantic schemas for demographic_depth agent output."""

from pydantic import BaseModel, Field


class CoreDemographic(BaseModel):
    age: str = Field(description="주타겟 연령대 (예: '20-30')")
    gender: str = Field(description="주타겟 성별 (male/female/mixed)")
    share: float = Field(description="해당 세그먼트 매출 비중 (0-1)")


class AgeShare(BaseModel):
    age_group: str = Field(description="연령대 라벨 (10/20/30/40/50/60+)")
    share: float = Field(description="매출 비중 (0-1)")


class DemographicAnalysis(BaseModel):
    """LLM이 structured output으로 생성하는 필드만. 정량 계산은 코드에서 별도."""

    brand_target_match_score: float | None = Field(
        default=None,
        description="브랜드가 주어졌을 때 타겟 매칭 점수 (0-100). 브랜드 없으면 None.",
    )
    match_rationale: str | None = Field(
        default=None,
        description="매칭 점수 근거 설명. 브랜드 없으면 None.",
    )
    narrative: str = Field(description="주 소비층·시간대·소득·트렌드를 3~5문장으로 요약")


class DemographicReport(BaseModel):
    """에이전트 최종 출력. State에 저장됨."""

    core_demographic: CoreDemographic
    top_3_age_groups: list[AgeShare] = Field(description="매출 상위 3개 연령대, share 내림차순")
    peak_consumption_hours: list[str] = Field(description="매출 피크 시간대 상위 2개 (예: '17-21')")
    weekday_weekend_ratio: float = Field(description="평일/주말 매출비 (>1 이면 평일 우위)")
    resident_visitor_ratio: float | None = Field(
        default=None,
        description="거주민 대비 방문객 비율. POI 매핑 없는 동은 None",
    )
    area_income_level: str = Field(description="high/mid/low/unknown (서울시 기준)")
    population_trend: str = Field(description="growing/stable/declining/unknown")
    elderly_ratio: float | None = Field(
        default=None,
        description="고령 비율 % (서울시 평균; 행정동 단위 데이터 없음)",
    )
    brand_target_match_score: float | None = None
    match_rationale: str | None = None
    narrative: str
