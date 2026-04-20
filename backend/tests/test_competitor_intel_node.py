"""competitor_intel 노드 단위 테스트.

LLM/Redis 를 mock 처리하고, Python 서비스는 실제 DB 호출.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.nodes.competitor_intel import (
    BRAND_INDUSTRY_MAP,
    BUSINESS_TYPE_FALLBACK,
    _compute_adjusted_revenue,
    _resolve_industry,
    competitor_intel_node,
)


class TestResolveIndustry:
    def test_brand_priority(self):
        """brand_name 이 있으면 우선."""
        keyword, code, label = _resolve_industry("빽다방", "restaurant")
        assert keyword == "커피"
        assert code == "CS100010"
        assert label == "cafe"

    def test_business_type_fallback(self):
        """brand_name 매핑 없으면 business_type."""
        keyword, code, label = _resolve_industry("알수없는브랜드", "chicken")
        assert keyword == "치킨"
        assert code == "CS100007"

    def test_all_none_returns_default(self):
        keyword, code, label = _resolve_industry("알수없는", "알수없는")
        assert keyword == ""
        assert code is None
        assert label == "default"


class TestComputeAdjustedRevenue:
    def test_bench_not_available(self):
        bench = {"benchmark_available": False}
        cannibal = {"estimated_revenue_impact_pct": -0.1}
        comp = {"saturation_level": "medium"}
        assert _compute_adjusted_revenue(bench, cannibal, comp) is None

    def test_base_plus_cannibal_minus_saturation(self):
        """3.19억 × (1 - 0.1 - 0.1) = 2.552억."""
        bench = {"benchmark_available": True, "avg_sales_per_store": 319_087_000}
        cannibal = {"estimated_revenue_impact_pct": -0.1}
        comp = {"saturation_level": "high"}  # -0.10
        result = _compute_adjusted_revenue(bench, cannibal, comp)
        assert result == pytest.approx(319_087_000 * 0.80, rel=0.001)

    def test_sparse_boosts_revenue(self):
        bench = {"benchmark_available": True, "avg_sales_per_store": 500_000_000}
        cannibal = {"estimated_revenue_impact_pct": 0}
        comp = {"saturation_level": "sparse"}  # +0.10
        result = _compute_adjusted_revenue(bench, cannibal, comp)
        assert result == pytest.approx(500_000_000 * 1.10, rel=0.001)


class TestIndustryMaps:
    def test_brand_map_completeness(self):
        expected = {"이디야커피", "빽다방", "메가MGC커피", "스타벅스", "교촌치킨", "맘스터치"}
        assert expected.issubset(set(BRAND_INDUSTRY_MAP.keys()))

    def test_business_type_fallback_korean_and_english(self):
        """영/한 양쪽 키 지원."""
        assert "cafe" in BUSINESS_TYPE_FALLBACK
        assert "카페" in BUSINESS_TYPE_FALLBACK


@pytest.mark.asyncio
class TestCompetitorIntelNode:
    """노드 통합 테스트 — 실 DB + LLM/Redis mock."""

    async def test_missing_brand_returns_error(self):
        state = {"target_district": "서교동"}
        result = await competitor_intel_node(state)
        r = result["competitor_intel_result"]
        assert "error" in r
        assert "brand_name" in r["error"]

    async def test_unknown_district_returns_error(self):
        state = {"target_district": "존재하지않는동", "brand_name": "빽다방"}
        result = await competitor_intel_node(state)
        r = result["competitor_intel_result"]
        assert "error" in r
        assert "dong_code" in r["error"]

    async def test_baekdabang_seogyo_full_flow(self):
        """빽다방 서교동 — 전체 플로우 (LLM 모킹)."""
        mock_llm_out = MagicMock()
        mock_llm_out.model_dump.return_value = {
            "market_entry_signal": "yellow",
            "differentiation_position": "커피 포화 지역, 빽다방 저가 포지셔닝 강조",
            "key_opportunities": ["가격 경쟁력", "테이크아웃 수요"],
            "key_risks": ["이미 메가/빽 7개 이상"],
            "recommended_actions": ["차별화 메뉴"],
            "narrative": "테스트 narrative",
        }

        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_llm_out)

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured

        with (
            patch("src.agents.nodes.competitor_intel.get_fast_llm", return_value=mock_llm),
            patch("src.agents.nodes.competitor_intel._try_cache_get", AsyncMock(return_value=None)),
            patch("src.agents.nodes.competitor_intel._try_cache_set", AsyncMock(return_value=None)),
        ):
            state = {
                "target_district": "서교동",
                "brand_name": "빽다방",
                "business_type": "cafe",
            }
            result = await competitor_intel_node(state)

        r = result["competitor_intel_result"]
        assert "error" not in r
        assert r["market_entry_signal"] == "yellow"
        assert r["competition_500m"]["total_competitors"] >= 5  # 서교동 커피 포화
        assert r["cannibalization"]["same_brand_nearby"] >= 0
        assert r["brand_benchmark"]["benchmark_available"] is True
        assert r["brand_benchmark"]["franchise_count_national"] == 1449
        assert r["adjusted_estimated_revenue"] is not None
        assert r["meta"]["dong_code"] == "11440660"

    async def test_starbucks_bench_unavailable_still_works(self):
        """스타벅스(FTC 미등재)도 에러 없이 반환."""
        mock_llm_out = MagicMock()
        mock_llm_out.model_dump.return_value = {
            "market_entry_signal": "green",
            "differentiation_position": "직영",
            "key_opportunities": [],
            "key_risks": [],
            "recommended_actions": [],
            "narrative": "ok",
        }
        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_llm_out)
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured

        with (
            patch("src.agents.nodes.competitor_intel.get_fast_llm", return_value=mock_llm),
            patch("src.agents.nodes.competitor_intel._try_cache_get", AsyncMock(return_value=None)),
            patch("src.agents.nodes.competitor_intel._try_cache_set", AsyncMock(return_value=None)),
        ):
            state = {
                "target_district": "서교동",
                "brand_name": "스타벅스",
                "business_type": "cafe",
            }
            result = await competitor_intel_node(state)

        r = result["competitor_intel_result"]
        assert "error" not in r
        assert r["brand_benchmark"]["benchmark_available"] is False
        assert r["adjusted_estimated_revenue"] is None  # 벤치마크 없어 계산 불가
        assert r["peer_brands"] == []  # industry_medium 없어 peer 없음
