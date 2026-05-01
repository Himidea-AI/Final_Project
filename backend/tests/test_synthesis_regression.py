"""synthesis 노드 회귀 테스트 — legal 14항목 보존 + competitor_intel 통합."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.nodes.synthesis import synthesis_node


def _mock_strategy() -> MagicMock:
    s = MagicMock()
    s.model_dump.return_value = {"summary": "ok", "final_recommendation": "ok"}
    s.overall_legal_risk = "caution"
    s.summary = "ok"
    s.final_recommendation = "ok"
    return s


def _mock_smart_llm(strategy: MagicMock) -> MagicMock:
    llm = MagicMock()
    llm.with_structured_output.return_value.ainvoke = AsyncMock(return_value=strategy)
    return llm


def _base_state_with_competitor() -> dict:
    return {
        "target_district": "서교동",
        "brand_name": "빽다방",
        "business_type": "카페",
        "overall_legal_risk": "caution",
        "winner_district": "서교동",
        "top_3_candidates": ["서교동", "연남동", "망원1동"],
        "scouting_results": [{"rank": 1, "district": "서교동", "score": 85}],
        "analysis_results": {
            "market_report": "상권 양호",
            "population_report": "유동인구 풍부",
            "legal_risks": [{"type": f"law_{i}", "level": "safe", "summary": f"검토 {i}"} for i in range(14)],
        },
        "competitor_intel_result": {
            "market_entry_signal": "yellow",
            "narrative": "CI narrative",
            "competition_500m": {"saturation_level": "high"},
            "cannibalization": {"estimated_revenue_impact_pct": -0.15},
        },
    }


@pytest.mark.asyncio
class TestSynthesisRegression:
    """competitor_intel 추가가 기존 flow 를 훼손하지 않음을 검증."""

    async def test_legal_risks_14_preserved(self):
        state = _base_state_with_competitor()
        with (
            patch("src.agents.nodes.synthesis.get_smart_llm", return_value=_mock_smart_llm(_mock_strategy())),
            patch("src.agents.nodes.synthesis.aioredis.from_url", side_effect=Exception("no redis")),
        ):
            result = await synthesis_node(state)

        legal_risks = result["analysis_results"]["legal_risks"]
        assert len(legal_risks) == 14, f"legal_risks 훼손: {len(legal_risks)}"
        assert legal_risks[13]["type"] == "law_13"
        assert all(r["type"].startswith("law_") for r in legal_risks)

    async def test_competitor_intel_result_forwarded(self):
        """synthesis 가 competitor_intel_result 를 파이프라인 끝까지 전달."""
        state = _base_state_with_competitor()
        with (
            patch("src.agents.nodes.synthesis.get_smart_llm", return_value=_mock_smart_llm(_mock_strategy())),
            patch("src.agents.nodes.synthesis.aioredis.from_url", side_effect=Exception("no redis")),
        ):
            result = await synthesis_node(state)

        assert "competitor_intel_result" in result
        assert result["competitor_intel_result"]["market_entry_signal"] == "yellow"

    async def test_missing_competitor_intel_does_not_break(self):
        """competitor_intel_result 가 없는 요청도 synthesis 정상 동작."""
        state = _base_state_with_competitor()
        state["competitor_intel_result"] = {}

        with (
            patch("src.agents.nodes.synthesis.get_smart_llm", return_value=_mock_smart_llm(_mock_strategy())),
            patch("src.agents.nodes.synthesis.aioredis.from_url", side_effect=Exception("no redis")),
        ):
            result = await synthesis_node(state)

        assert len(result["analysis_results"]["legal_risks"]) == 14

    async def test_competitor_intel_error_does_not_break(self):
        """competitor_intel 이 에러 상태여도 synthesis 프롬프트에서 무시."""
        state = _base_state_with_competitor()
        state["competitor_intel_result"] = {"error": "서비스 호출 실패"}

        with (
            patch("src.agents.nodes.synthesis.get_smart_llm", return_value=_mock_smart_llm(_mock_strategy())),
            patch("src.agents.nodes.synthesis.aioredis.from_url", side_effect=Exception("no redis")),
        ):
            result = await synthesis_node(state)

        # 여전히 legal_risks 14개
        assert len(result["analysis_results"]["legal_risks"]) == 14
        # final_report 정상 생성
        assert "final_report" in result["analysis_results"]
