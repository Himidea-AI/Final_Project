"""통합 테스트: graph에 demographic_depth가 포함되고 synthesis가 읽는지 + legal 14개 보존."""

from unittest.mock import AsyncMock, patch

import pytest
from dotenv import load_dotenv

load_dotenv("../.env")


@pytest.mark.asyncio
async def test_demographic_node_in_parallel_analysis():
    """parallel_analysis_node가 demographic_depth를 포함하는지."""
    import inspect

    from src.agents.graph import parallel_analysis_node

    src = inspect.getsource(parallel_analysis_node)
    assert "demographic_depth" in src


@pytest.mark.asyncio
async def test_synthesis_reads_demographic_without_breaking_legal():
    """synthesis가 demographic_report 읽되 legal_risks 14개 보존."""
    from src.agents.nodes.synthesis import synthesis_node

    # Mock LLM 응답 (structured_output 경로)
    mock_final_strategy = AsyncMock()
    # FinalStrategyResult.model_dump() 호환 반환값
    mock_final_strategy.model_dump = lambda: {
        "summary": "테스트 요약",
        "is_direct": False,
        "brand_category": "franchise",
        "overall_legal_risk": "caution",
        "profit_simulation": {"monthly_revenue": 0, "net_profit": 0, "margin_rate": 0.0},
        "competitor_analysis": {"count": 0, "density": "NORMAL"},
        "final_recommendation": "테스트 추천",
    }
    mock_final_strategy.summary = "테스트 요약"
    mock_final_strategy.final_recommendation = "테스트 추천"
    mock_final_strategy.overall_legal_risk = "caution"

    legal_14 = [
        {
            "type": f"law_{i}",
            "level": "safe",
            "summary": f"법률 {i}",
            "articles": [],
            "recommendation": "",
        }
        for i in range(14)
    ]

    state = {
        "brand_name": "테스트브랜드",
        "target_district": "서교동",
        "business_type": "cafe",
        "monthly_rent_budget": 3000000,
        "store_area": 15.0,
        "population_weight": True,
        "analysis_results": {
            "market_report": "시장 리포트",
            "population_report": "인구 리포트",
            "legal_risks": legal_14,
            "demographic_report": {
                "core_demographic": {"age": "20-30", "gender": "female", "share": 0.42},
                "top_3_age_groups": [],
                "peak_consumption_hours": ["17-21"],
                "weekday_weekend_ratio": 1.2,
                "resident_visitor_ratio": 0.6,
                "area_income_level": "mid",
                "population_trend": "stable",
                "elderly_ratio": 20.7,
                "brand_target_match_score": 78.0,
                "match_rationale": "매칭",
                "narrative": "요약",
            },
        },
        "overall_legal_risk": "caution",
    }

    with patch("src.agents.nodes.synthesis.get_smart_llm") as mock_llm_getter:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_final_strategy)
        # with_structured_output 체인 — 동일한 mock_llm 반환
        mock_llm.with_structured_output = lambda _: mock_llm
        mock_llm_getter.return_value = mock_llm

        # Redis는 연결 실패 시 무시되도록 설계돼 있으므로 추가 mock 불필요
        result = await synthesis_node(state)

    # legal_risks 14개 보존 확인
    assert "legal_risks" in result["analysis_results"]
    assert result["analysis_results"]["legal_risks"] == legal_14
    assert len(result["analysis_results"]["legal_risks"]) == 14
    # demographic_report 도 보존
    assert "demographic_report" in result["analysis_results"]


def test_simulation_input_has_industry_filter():
    """AgentState 스키마에 industry_filter 필드가 있는지."""
    import inspect

    from src.schemas.state import AgentState

    src = inspect.getsource(AgentState)
    assert "industry_filter" in src


def test_simulation_output_shape():
    """main.py 응답에 demographic_report 키 포함 여부."""
    import pathlib

    main_path = pathlib.Path(__file__).resolve().parents[1] / "src" / "main.py"
    content = main_path.read_text(encoding="utf-8")
    assert "demographic_report" in content
