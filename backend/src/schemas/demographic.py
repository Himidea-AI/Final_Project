"""Pydantic schemas for demographic_depth agent output."""

from typing import Literal

from pydantic import BaseModel, Field


class CoreDemographic(BaseModel):
    age: str = Field(description="주타겟 연령대 (예: '20-30')")
    gender: str = Field(description="주타겟 성별 (male/female/mixed)")
    share: float = Field(description="해당 세그먼트 매출 비중 (0-1)")


class TargetAlignmentAlert(BaseModel):
    """사용자 입력 타겟 vs 동·업종 실측 매출 분포 미스매치 알림.

    프론트 인구분석탭에서 '내 타겟이 이 입지의 실 소비층과 어긋남' 신호를 띄우는 데 사용.
    """

    dimension: Literal["age", "gender", "hours", "day", "price"] = Field(description="매칭 차원")
    severity: Literal["high", "medium", "low"] = Field(
        description="미스매치 강도. high=즉시 재검토, medium=주의, low=경미"
    )
    user_input: str = Field(description="사용자가 입력한 타겟값 (UI 표기용)")
    actual: str = Field(description="실측 값 요약 (예: '50대 35%·점심 피크')")
    message: str = Field(description="한 줄 액션 메시지 (예: '20대 타겟인데 실 매출 50대 1위')")


class AgeShare(BaseModel):
    age_group: str = Field(description="연령대 라벨 (10/20/30/40/50/60+)")
    share: float = Field(description="매출 비중 (0-1)")


class ReverseTargetSuggestion(BaseModel):
    """alert high 발생 시 실측 기반의 권장 타겟 프로필(역제안).

    "이 입지에서 *어떤 타겟* 으로 운영하면 정렬도가 90+ 가 되는가" 를 사용자에게
    보여주는 reverse-suggestion. 입지를 바꿀 수 없을 때 타겟·운영전략 재정의로
    적합도를 끌어올릴 수 있는지 판단 보조.
    """

    recommended_age_groups: list[str] = Field(
        default_factory=list, description="권장 타겟 연령대(매출 상위 1-2개). 예: ['20대','30대']"
    )
    recommended_gender: str | None = Field(default=None, description="권장 타겟 성별. 'male'/'female'/None(혼재)")
    recommended_hours: list[str] = Field(
        default_factory=list, description="권장 영업시간 카테고리(피크 기반). 예: ['점심','저녁']"
    )
    recommended_day_type: str | None = Field(default=None, description="권장 요일 타겟. 'weekday'/'weekend'/None")
    recommended_price_range: str | None = Field(
        default=None, description="권장 객단가 구간. 'lt5k'/'5to10k'/'10to15k'/'gt15k'/None"
    )
    rationale: str = Field(description="실측 매출 근거 1-2문장")


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
    # 사용자 입력 타겟(target_age_groups/target_gender/operating_hours/target_day_type/
    # target_price_range) 대비 실측 매출·소득 분포 미스매치 평가. 사용자 입력이 비면 빈 리스트.
    target_alignment: list[TargetAlignmentAlert] = Field(default_factory=list)
    # 0-100 점, 사용자 타겟 정렬도. 입력이 전혀 없으면 None.
    target_alignment_score: float | None = None
    # high severity alert 가 1개 이상 있을 때 채워지는 역제안. 정렬 양호 시 None.
    reverse_target_suggestion: ReverseTargetSuggestion | None = None
