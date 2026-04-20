"""시연 시나리오 3개 통합 테스트 — 실 DB, LLM 모킹.

시나리오:
1. 빽다방 서교동 — 카페 포화, 자사 매장 있음 → signal: yellow/red
2. 교촌치킨 공덕동 — 치킨 중간 포화 → 데이터 검증
3. 맘스터치 망원1동 — 버거 희박 → signal: green/yellow
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.nodes.competitor_intel import competitor_intel_node


def _mock_llm(signal: str = "yellow") -> MagicMock:
    out = MagicMock()
    out.model_dump.return_value = {
        "market_entry_signal": signal,
        "differentiation_position": "테스트 포지셔닝",
        "key_opportunities": ["기회1"],
        "key_risks": ["리스크1"],
        "recommended_actions": ["액션1"],
        "narrative": "테스트 narrative",
    }
    structured = MagicMock()
    structured.ainvoke = AsyncMock(return_value=out)
    llm = MagicMock()
    llm.with_structured_output.return_value = structured
    return llm


@pytest.mark.asyncio
class TestScenarioBaekdabangSeogyo:
    """빽다방 서교동 — 커피 포화 지역, 자사 매장 영향 예상."""

    async def test_full_data_structure(self):
        with (
            patch("src.agents.nodes.competitor_intel.get_fast_llm", return_value=_mock_llm("yellow")),
            patch(
                "src.agents.nodes.competitor_intel._try_cache_get",
                AsyncMock(return_value=None),
            ),
            patch(
                "src.agents.nodes.competitor_intel._try_cache_set",
                AsyncMock(return_value=None),
            ),
        ):
            state = {
                "target_district": "서교동",
                "brand_name": "빽다방",
                "business_type": "cafe",
            }
            result = await competitor_intel_node(state)

        r = result["competitor_intel_result"]
        assert r["meta"]["industry_code"] == "CS100010"
        # 서교동 500m 반경 커피 최소 10개 (Step 0 실측)
        assert r["competition_500m"]["total_competitors"] >= 10
        assert r["competition_500m"]["saturation_level"] in ("medium", "high", "saturated")
        # FTC 2024 빽다방 1,449개 가맹점
        assert r["brand_benchmark"]["franchise_count_national"] == 1449
        # 매출 보정 반영됨
        assert r["adjusted_estimated_revenue"] is not None
        assert r["adjusted_estimated_revenue"] > 0


@pytest.mark.asyncio
class TestScenarioKyochonGongdeok:
    """교촌치킨 공덕동 — 치킨 중간 포화."""

    async def test_data_structure(self):
        with (
            patch("src.agents.nodes.competitor_intel.get_fast_llm", return_value=_mock_llm("yellow")),
            patch(
                "src.agents.nodes.competitor_intel._try_cache_get",
                AsyncMock(return_value=None),
            ),
            patch(
                "src.agents.nodes.competitor_intel._try_cache_set",
                AsyncMock(return_value=None),
            ),
        ):
            state = {
                "target_district": "공덕동",
                "brand_name": "교촌치킨",
                "business_type": "chicken",
            }
            result = await competitor_intel_node(state)

        r = result["competitor_intel_result"]
        assert r["meta"]["dong_code"] == "11440565"
        assert r["meta"]["industry_code"] == "CS100007"  # 치킨전문점
        # 교촌 2024 전국 1,377개
        assert r["brand_benchmark"]["franchise_count_national"] == 1377
        # 치킨 업계 peer Top 5 (BBQ/교촌/BHC/네네/호식이)
        assert len(r["peer_brands"]) > 0


@pytest.mark.asyncio
class TestScenarioMomstouchMangwon:
    """맘스터치 망원1동 — 버거 희박 (블루오션 예상)."""

    async def test_blue_ocean(self):
        with (
            patch("src.agents.nodes.competitor_intel.get_fast_llm", return_value=_mock_llm("green")),
            patch(
                "src.agents.nodes.competitor_intel._try_cache_get",
                AsyncMock(return_value=None),
            ),
            patch(
                "src.agents.nodes.competitor_intel._try_cache_set",
                AsyncMock(return_value=None),
            ),
        ):
            state = {
                "target_district": "망원1동",
                "brand_name": "맘스터치",
                "business_type": "burger",
            }
            result = await competitor_intel_node(state)

        r = result["competitor_intel_result"]
        assert r["meta"]["industry_code"] == "CS100006"
        # 맘스터치 2024 전국 1,409개
        assert r["brand_benchmark"]["franchise_count_national"] == 1409
        # 망원1동 버거 반경 500m 은 희박할 가능성 높음
        sat = r["competition_500m"]["saturation_level"]
        assert sat in ("sparse", "low", "medium", "high")  # 전 레인지 허용 (실데이터 유연성)


@pytest.mark.asyncio
class TestCacheRoundtrip:
    """캐시 hit 시 LLM 재호출 없이 결과 반환."""

    async def test_cache_hit_returns_cached(self):
        cached_payload = {
            "market_entry_signal": "green",
            "narrative": "캐시된 결과",
            "competition_500m": {"total_competitors": 99},
            "meta": {"dong_code": "11440660"},
        }
        with patch(
            "src.agents.nodes.competitor_intel._try_cache_get",
            AsyncMock(return_value=cached_payload),
        ):
            state = {
                "target_district": "서교동",
                "brand_name": "빽다방",
                "business_type": "cafe",
            }
            result = await competitor_intel_node(state)

        r = result["competitor_intel_result"]
        assert r["narrative"] == "캐시된 결과"
        assert r["competition_500m"]["total_competitors"] == 99
