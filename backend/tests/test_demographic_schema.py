"""Unit tests for DemographicReport schema (pure Pydantic, no DB)."""

from src.schemas.demographic import (
    AgeShare,
    CoreDemographic,
    DemographicAnalysis,
    DemographicReport,
)


def test_demographic_report_happy_path():
    r = DemographicReport(
        core_demographic=CoreDemographic(age="20-30", gender="female", share=0.42),
        top_3_age_groups=[
            AgeShare(age_group="20", share=0.45),
            AgeShare(age_group="30", share=0.25),
            AgeShare(age_group="40", share=0.15),
        ],
        peak_consumption_hours=["17-21", "11-14"],
        weekday_weekend_ratio=1.2,
        resident_visitor_ratio=0.6,
        area_income_level="mid",
        population_trend="stable",
        elderly_ratio=20.7,
        brand_target_match_score=78.0,
        match_rationale="20대 여성 주 고객과 정확히 매치",
        narrative="서교동 커피 매장은 20대 여성이 주 소비층이며...",
    )
    assert r.core_demographic.share == 0.42
    assert len(r.top_3_age_groups) == 3
    assert r.elderly_ratio == 20.7


def test_demographic_report_optional_fields_none():
    """브랜드·POI 없을 때: match_score, rationale, resident_visitor_ratio, elderly_ratio 모두 None 허용"""
    r = DemographicReport(
        core_demographic=CoreDemographic(age="30-40", gender="male", share=0.35),
        top_3_age_groups=[
            AgeShare(age_group="30", share=0.35),
            AgeShare(age_group="40", share=0.30),
            AgeShare(age_group="20", share=0.20),
        ],
        peak_consumption_hours=["12-14"],
        weekday_weekend_ratio=1.5,
        resident_visitor_ratio=None,
        area_income_level="unknown",
        population_trend="unknown",
        elderly_ratio=None,
        brand_target_match_score=None,
        match_rationale=None,
        narrative="분석 데이터 제한적",
    )
    assert r.brand_target_match_score is None
    assert r.elderly_ratio is None


def test_demographic_analysis_minimal():
    """LLM structured output 최소 호출: narrative만 필수"""
    a = DemographicAnalysis(narrative="간단 요약")
    assert a.brand_target_match_score is None
    assert a.match_rationale is None


def test_demographic_report_roundtrip_json():
    r = DemographicReport(
        core_demographic=CoreDemographic(age="20-30", gender="female", share=0.42),
        top_3_age_groups=[AgeShare(age_group="20", share=0.45)],
        peak_consumption_hours=[],
        weekday_weekend_ratio=1.0,
        resident_visitor_ratio=None,
        area_income_level="mid",
        population_trend="stable",
        elderly_ratio=20.7,
        brand_target_match_score=None,
        match_rationale=None,
        narrative="n",
    )
    j = r.model_dump()
    r2 = DemographicReport(**j)
    assert r2.core_demographic.age == "20-30"
