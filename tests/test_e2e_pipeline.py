"""
통합 E2E 파이프라인 테스트 — A2 + B1 공동

이 테스트가 하는 일:
  parallel_analysis → synthesis 전체 흐름에서
  각 에이전트의 결과가 최종 응답까지 손실 없이 전달되는지 검증합니다.

테스트 범위:
  C-1: legal → synthesis 14개 법률 리스크 보존
  C-2: ranking → synthesis 랭킹 데이터 보존
  C-3: Redis 캐시 히트/미스 시 데이터 정합성
  C-4: parallel_analysis_node 병합 로직
  C-5: synthesis LLM 실패 시 fallback 데이터 보존

실행:
    pytest tests/test_e2e_pipeline.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.agents.graph import parallel_analysis_node  # noqa: E402

# ── 테스트용 에이전트 결과 fixtures ─────────────────────────────────────────


def _make_legal_risks(count: int = 14) -> list[dict]:
    """14개 법률 리스크 mock 데이터 생성"""
    types = [
        "franchise_law",
        "commercial_lease_law",
        "zoning_regulation",
        "food_hygiene",
        "safety_regulation",
        "ftc_franchise",
        "building_law",
        "fire_safety_law",
        "labor_law",
        "vat_law",
        "privacy_law",
        "accessibility_law",
        "sewage_law",
        "fair_trade_law",
    ]
    return [
        {
            "type": types[i] if i < len(types) else f"type_{i}",
            "level": ["safe", "caution", "danger"][i % 3],
            "summary": f"법률 {i + 1} 검토 완료",
            "articles": [],
            "recommendation": f"권고사항 {i + 1}",
        }
        for i in range(count)
    ]


def _make_ranking_results() -> list[dict]:
    """16개 행정동 랭킹 mock 데이터"""
    from src.config.constants import MAPO_DISTRICTS

    return [
        {
            "district": dong,
            "score": round(90 - i * 3.5, 1),
            "rank": i + 1,
            "sales_score": 80.0,
            "pop_score": 70.0,
            "rent_score": 60.0,
            "sales_growth": 10.0,
            "pop_growth": 5.0,
            "avg_rent": 50000.0,
            "vacancy_rate": 3.0 + i,
        }
        for i, dong in enumerate(MAPO_DISTRICTS)
    ]


def _make_market_result() -> dict:
    """market_analyst_node 결과 mock"""
    return {
        "analysis_results": {
            "market_report": "서교동 상권 분석: 매출 성장률 12%, 유동인구 증가",
        },
        "analysis_metrics": {
            "district_grade": "GOOD",
            "growth_rate": 12.0,
            "competition_score": 0.6,
            "rent_affordability": "SAFE",
            "population_score": 8.5,
        },
        "market_data": {"lat": 37.5563, "lng": 126.9236, "avg_revenue": 35000000},
    }


def _make_population_result() -> dict:
    """population_analyst_node 결과 mock"""
    return {
        "analysis_results": {
            "population_report": "서교동 유동인구: 일 평균 45,000명, 20~30대 주력",
        },
        "analysis_metrics": {},
    }


def _make_legal_result() -> dict:
    """legal_node 결과 mock"""
    risks = _make_legal_risks(14)
    return {
        "analysis_results": {
            "legal_risks": risks,
            "overall_legal_risk": "caution",
        },
        "legal_info": [{"content": "가맹사업법 조문", "metadata": {"source": "가맹사업법"}}],
        "overall_legal_risk": "caution",
    }


def _make_ranking_result() -> dict:
    """district_ranking_node 결과 mock"""
    ranked = _make_ranking_results()
    return {
        "scouting_results": ranked,
        "winner_district": ranked[0]["district"],
        "top_3_candidates": [r["district"] for r in ranked[1:4]],
        "vacancy_applied": True,
        "current_agent": "district_ranking",
    }


# ── C-4: parallel_analysis_node 병합 테스트 ──────────────────────────────────


class TestParallelAnalysisMerge:
    """
    parallel_analysis_node가 4개 에이전트 결과를 올바르게 병합하는지 검증.
    market + population + legal의 analysis_results가 합쳐지고,
    ranking의 scouting_results가 별도 필드로 전달되는지 확인.
    """

    @pytest.fixture
    def mock_agents(self):
        """4개 에이전트 노드를 mock으로 대체"""
        with (
            patch("src.agents.graph.market_analyst_node", new_callable=AsyncMock) as mock_market,
            patch("src.agents.graph.population_analyst_node", new_callable=AsyncMock) as mock_pop,
            patch("src.agents.graph.legal_node", new_callable=AsyncMock) as mock_legal,
            patch("src.agents.graph.district_ranking_node", new_callable=AsyncMock) as mock_ranking,
        ):
            mock_market.return_value = _make_market_result()
            mock_pop.return_value = _make_population_result()
            mock_legal.return_value = _make_legal_result()
            mock_ranking.return_value = _make_ranking_result()

            yield {
                "market": mock_market,
                "population": mock_pop,
                "legal": mock_legal,
                "ranking": mock_ranking,
            }

    @pytest.mark.asyncio
    async def test_all_4_agents_called(self, mock_agents):
        """4개 에이전트가 모두 호출되는지 확인."""
        state = {"business_type": "카페", "target_district": "서교동"}
        await parallel_analysis_node(state)

        mock_agents["market"].assert_called_once()
        mock_agents["population"].assert_called_once()
        mock_agents["legal"].assert_called_once()
        mock_agents["ranking"].assert_called_once()

    @pytest.mark.asyncio
    async def test_legal_risks_preserved_in_merge(self, mock_agents):
        """C-1: legal의 14개 법률 리스크가 병합 후에도 보존."""
        state = {"business_type": "카페", "target_district": "서교동"}
        result = await parallel_analysis_node(state)

        legal_risks = result["analysis_results"]["legal_risks"]
        assert len(legal_risks) == 14
        risk_types = {r["type"] for r in legal_risks}
        assert "franchise_law" in risk_types
        assert "zoning_regulation" in risk_types
        assert "fair_trade_law" in risk_types

    @pytest.mark.asyncio
    async def test_overall_legal_risk_from_legal_node(self, mock_agents):
        """overall_legal_risk가 legal 노드 결과를 우선 사용."""
        state = {"business_type": "카페", "target_district": "서교동"}
        result = await parallel_analysis_node(state)

        assert result["overall_legal_risk"] == "caution"

    @pytest.mark.asyncio
    async def test_ranking_data_separate_fields(self, mock_agents):
        """C-2: 랭킹 데이터가 별도 필드로 전달."""
        state = {"business_type": "카페", "target_district": "서교동"}
        result = await parallel_analysis_node(state)

        assert len(result["scouting_results"]) == 16
        assert result["winner_district"] == "아현동"  # MAPO_DISTRICTS[0]
        assert len(result["top_3_candidates"]) == 3

    @pytest.mark.asyncio
    async def test_market_report_in_analysis(self, mock_agents):
        """market 분석 리포트가 analysis_results에 포함."""
        state = {"business_type": "카페", "target_district": "서교동"}
        result = await parallel_analysis_node(state)

        assert "market_report" in result["analysis_results"]
        assert "서교동" in result["analysis_results"]["market_report"]

    @pytest.mark.asyncio
    async def test_population_report_in_analysis(self, mock_agents):
        """population 분석 리포트가 analysis_results에 포함."""
        state = {"business_type": "카페", "target_district": "서교동"}
        result = await parallel_analysis_node(state)

        assert "population_report" in result["analysis_results"]

    @pytest.mark.asyncio
    async def test_metrics_merged(self, mock_agents):
        """analysis_metrics가 market + population에서 병합."""
        state = {"business_type": "카페", "target_district": "서교동"}
        result = await parallel_analysis_node(state)

        assert result["analysis_metrics"]["district_grade"] == "GOOD"
        assert result["analysis_metrics"]["growth_rate"] == 12.0

    @pytest.mark.asyncio
    async def test_market_data_passed_through(self, mock_agents):
        """market_data(좌표, 매출)가 그대로 전달."""
        state = {"business_type": "카페", "target_district": "서교동"}
        result = await parallel_analysis_node(state)

        assert result["market_data"]["lat"] == 37.5563
        assert result["market_data"]["avg_revenue"] == 35000000


# ── C-1: legal → synthesis 법률 리스크 보존 ──────────────────────────────────


class TestLegalToSynthesisPreservation:
    """
    legal_node가 생성한 14개 법률 리스크가
    synthesis_node를 거쳐 최종 응답에서도 100% 보존되는지 검증.
    """

    @pytest.fixture
    def mock_synthesis_deps(self):
        """synthesis_node의 LLM과 Redis를 mock"""
        mock_redis_mod = MagicMock()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_redis.aclose = AsyncMock()
        mock_redis_mod.from_url.return_value = mock_redis

        mock_strategy = MagicMock()
        mock_strategy.summary = "테스트 요약"
        mock_strategy.overall_legal_risk = "caution"
        mock_strategy.final_recommendation = "테스트 권고"
        mock_strategy.model_dump.return_value = {
            "summary": "테스트 요약",
            "overall_legal_risk": "caution",
            "final_recommendation": "테스트 권고",
        }

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_strategy)

        with (
            patch("src.agents.nodes.synthesis.get_smart_llm", return_value=mock_llm),
            patch("src.agents.nodes.synthesis.settings") as mock_settings,
            patch.dict("sys.modules", {"redis.asyncio": mock_redis_mod, "redis": MagicMock()}),
        ):
            mock_settings.redis_url = "redis://localhost:6379/0"
            yield {"redis": mock_redis, "llm": mock_llm}

    @pytest.mark.asyncio
    async def test_14_risks_survive_synthesis(self, mock_synthesis_deps):
        """14개 법률 리스크가 synthesis 통과 후에도 모두 존재."""
        from src.agents.nodes.synthesis import synthesis_node

        risks = _make_legal_risks(14)
        ranked = _make_ranking_results()

        state = {
            "brand_name": "이디야커피",
            "business_type": "카페",
            "target_district": "서교동",
            "target_price_range": "",
            "operating_hours": [],
            "initial_capital": 100000000,
            "monthly_rent_budget": 2000000,
            "store_area": 15.0,
            "population_weight": True,
            "analysis_results": {
                "market_report": "상권 분석 완료",
                "population_report": "인구 분석 완료",
                "legal_risks": risks,
                "overall_legal_risk": "caution",
            },
            "overall_legal_risk": "caution",
            "scouting_results": ranked,
            "winner_district": ranked[0]["district"],
            "top_3_candidates": [r["district"] for r in ranked[1:4]],
        }

        result = await synthesis_node(state)

        # 14개 법률 리스크 전부 보존
        output_risks = result["analysis_results"]["legal_risks"]
        assert len(output_risks) == 14

        # 타입 전부 일치
        input_types = {r["type"] for r in risks}
        output_types = {r["type"] for r in output_risks}
        assert input_types == output_types

    @pytest.mark.asyncio
    async def test_overall_legal_risk_preserved(self, mock_synthesis_deps):
        """overall_legal_risk가 synthesis를 거쳐도 원본 유지."""
        from src.agents.nodes.synthesis import synthesis_node

        state = {
            "brand_name": "BBQ",
            "business_type": "치킨",
            "target_district": "대흥동",
            "target_price_range": "",
            "operating_hours": [],
            "initial_capital": 0,
            "monthly_rent_budget": 0,
            "store_area": 15.0,
            "population_weight": True,
            "analysis_results": {
                "market_report": "분석",
                "population_report": "분석",
                "legal_risks": _make_legal_risks(14),
                "overall_legal_risk": "danger",
            },
            "overall_legal_risk": "danger",
            "scouting_results": [],
            "winner_district": "대흥동",
            "top_3_candidates": [],
        }

        result = await synthesis_node(state)
        assert result["overall_legal_risk"] == "danger"

    @pytest.mark.asyncio
    async def test_legal_risks_not_overwritten_by_final_report(self, mock_synthesis_deps):
        """final_report 추가 시 legal_risks가 덮어쓰이지 않는지 확인."""
        from src.agents.nodes.synthesis import synthesis_node

        risks = _make_legal_risks(14)
        state = {
            "brand_name": "스타벅스",
            "business_type": "카페",
            "target_district": "합정동",
            "target_price_range": "",
            "operating_hours": [],
            "initial_capital": 0,
            "monthly_rent_budget": 0,
            "store_area": 15.0,
            "population_weight": True,
            "analysis_results": {
                "market_report": "분석",
                "population_report": "분석",
                "legal_risks": risks,
            },
            "overall_legal_risk": "safe",
            "scouting_results": [],
            "winner_district": "합정동",
            "top_3_candidates": [],
        }

        result = await synthesis_node(state)

        # final_report가 추가되었지만 legal_risks는 그대로
        assert "final_report" in result["analysis_results"]
        assert "legal_risks" in result["analysis_results"]
        assert len(result["analysis_results"]["legal_risks"]) == 14


# ── C-2: ranking → synthesis 랭킹 데이터 보존 ────────────────────────────────


class TestRankingToSynthesisPreservation:
    """
    ranking 에이전트의 scouting_results, winner_district, top_3_candidates가
    synthesis 최종 응답의 analysis_results에 보존되는지 검증.
    """

    @pytest.fixture
    def mock_synthesis_deps(self):
        """synthesis_node의 LLM과 Redis mock (위와 동일)"""
        mock_redis_mod = MagicMock()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_redis.aclose = AsyncMock()
        mock_redis_mod.from_url.return_value = mock_redis

        mock_strategy = MagicMock()
        mock_strategy.summary = "요약"
        mock_strategy.overall_legal_risk = "safe"
        mock_strategy.final_recommendation = "권고"
        mock_strategy.model_dump.return_value = {
            "summary": "요약",
            "overall_legal_risk": "safe",
            "final_recommendation": "권고",
        }

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_strategy)

        with (
            patch("src.agents.nodes.synthesis.get_smart_llm", return_value=mock_llm),
            patch("src.agents.nodes.synthesis.settings") as mock_settings,
            patch.dict("sys.modules", {"redis.asyncio": mock_redis_mod, "redis": MagicMock()}),
        ):
            mock_settings.redis_url = "redis://localhost:6379/0"
            yield

    @pytest.mark.asyncio
    async def test_district_rankings_preserved(self, mock_synthesis_deps):
        """16개 동 랭킹이 synthesis 결과에 보존."""
        from src.agents.nodes.synthesis import synthesis_node

        ranked = _make_ranking_results()
        state = {
            "brand_name": "이디야커피",
            "business_type": "카페",
            "target_district": "서교동",
            "target_price_range": "",
            "operating_hours": [],
            "initial_capital": 0,
            "monthly_rent_budget": 0,
            "store_area": 15.0,
            "population_weight": True,
            "analysis_results": {"market_report": "", "population_report": "", "legal_risks": []},
            "overall_legal_risk": "safe",
            "scouting_results": ranked,
            "winner_district": ranked[0]["district"],
            "top_3_candidates": [r["district"] for r in ranked[1:4]],
        }

        result = await synthesis_node(state)

        # district_rankings로 저장됨 (main.py가 이 키를 읽음)
        assert result["analysis_results"]["district_rankings"] == ranked
        assert len(result["analysis_results"]["district_rankings"]) == 16

    @pytest.mark.asyncio
    async def test_winner_district_preserved(self, mock_synthesis_deps):
        """winner_district가 synthesis 결과에 보존."""
        from src.agents.nodes.synthesis import synthesis_node

        ranked = _make_ranking_results()
        state = {
            "brand_name": "이디야커피",
            "business_type": "카페",
            "target_district": "서교동",
            "target_price_range": "",
            "operating_hours": [],
            "initial_capital": 0,
            "monthly_rent_budget": 0,
            "store_area": 15.0,
            "population_weight": True,
            "analysis_results": {"market_report": "", "population_report": "", "legal_risks": []},
            "overall_legal_risk": "safe",
            "scouting_results": ranked,
            "winner_district": "아현동",
            "top_3_candidates": ["공덕동", "도화동", "용강동"],
        }

        result = await synthesis_node(state)

        assert result["analysis_results"]["winner_district"] == "아현동"
        assert result["analysis_results"]["top_3_candidates"] == ["공덕동", "도화동", "용강동"]


# ── C-3: Redis 캐시 정합성 ───────────────────────────────────────────────────


class TestRedisCacheConsistency:
    """
    Redis 캐시 히트 시에도 legal_risks가 누락되지 않고,
    캐시 미스 시와 동일한 결과를 반환하는지 검증.
    """

    @pytest.mark.asyncio
    async def test_cache_hit_restores_legal_risks(self):
        """캐시 히트 시 legal_risks가 정상 복원."""
        from src.agents.nodes.synthesis import synthesis_node

        cached_risks = _make_legal_risks(14)
        cached_data = json.dumps(
            {
                "final_report": {
                    "summary": "캐시된 요약",
                    "overall_legal_risk": "caution",
                    "final_recommendation": "캐시",
                },
                "market_summary": "캐시된 요약\n\n캐시",
                "overall_legal_risk": "caution",
                "legal_risks": cached_risks,
            },
            ensure_ascii=False,
        )

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=cached_data)  # 캐시 히트
        mock_redis.aclose = AsyncMock()

        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url.return_value = mock_redis

        with (
            patch("src.agents.nodes.synthesis.aioredis", mock_redis_mod),
            patch("src.agents.nodes.synthesis.settings") as mock_settings,
        ):
            mock_settings.redis_url = "redis://localhost:6379/0"

            state = {
                "brand_name": "이디야커피",
                "business_type": "카페",
                "target_district": "서교동",
                "monthly_rent_budget": 0,
                "store_area": 15.0,
                "population_weight": True,
                "analysis_results": {"legal_risks": []},  # state에는 빈 리스크
            }

            result = await synthesis_node(state)

        # 캐시에서 복원된 legal_risks 확인
        assert len(result["analysis_results"]["legal_risks"]) == 14
        assert result["overall_legal_risk"] == "caution"

    @pytest.mark.asyncio
    async def test_cache_miss_still_preserves_risks(self):
        """캐시 미스 시에도 state의 legal_risks가 보존."""
        from src.agents.nodes.synthesis import synthesis_node

        mock_redis_mod = MagicMock()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # 캐시 미스
        mock_redis.set = AsyncMock()
        mock_redis.aclose = AsyncMock()
        mock_redis_mod.from_url.return_value = mock_redis

        mock_strategy = MagicMock()
        mock_strategy.summary = "요약"
        mock_strategy.overall_legal_risk = "safe"
        mock_strategy.final_recommendation = "권고"
        mock_strategy.model_dump.return_value = {
            "summary": "요약",
            "overall_legal_risk": "safe",
            "final_recommendation": "권고",
        }

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=mock_strategy)

        risks = _make_legal_risks(14)

        with (
            patch("src.agents.nodes.synthesis.get_smart_llm", return_value=mock_llm),
            patch("src.agents.nodes.synthesis.settings") as mock_settings,
            patch.dict("sys.modules", {"redis.asyncio": mock_redis_mod, "redis": MagicMock()}),
        ):
            mock_settings.redis_url = "redis://localhost:6379/0"

            state = {
                "brand_name": "이디야커피",
                "business_type": "카페",
                "target_district": "서교동",
                "target_price_range": "",
                "operating_hours": [],
                "initial_capital": 0,
                "monthly_rent_budget": 0,
                "store_area": 15.0,
                "population_weight": True,
                "analysis_results": {
                    "market_report": "분석",
                    "population_report": "분석",
                    "legal_risks": risks,
                },
                "overall_legal_risk": "safe",
                "scouting_results": [],
                "winner_district": "서교동",
                "top_3_candidates": [],
            }

            result = await synthesis_node(state)

        assert len(result["analysis_results"]["legal_risks"]) == 14


# ── C-5: synthesis LLM 실패 시 데이터 보존 ───────────────────────────────────


class TestSynthesisLlmFailure:
    """
    synthesis에서 LLM 호출이 실패해도 기존 에이전트 결과가 보존되는지 검증.
    """

    @pytest.mark.asyncio
    async def test_llm_failure_preserves_all_data(self):
        """LLM 예외 발생 시에도 legal_risks, rankings 모두 보존."""
        from src.agents.nodes.synthesis import synthesis_node

        mock_redis_mod = MagicMock()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_redis.aclose = AsyncMock()
        mock_redis_mod.from_url.return_value = mock_redis

        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM API timeout"))

        risks = _make_legal_risks(14)
        ranked = _make_ranking_results()

        with (
            patch("src.agents.nodes.synthesis.get_smart_llm", return_value=mock_llm),
            patch("src.agents.nodes.synthesis.settings") as mock_settings,
            patch.dict("sys.modules", {"redis.asyncio": mock_redis_mod, "redis": MagicMock()}),
        ):
            mock_settings.redis_url = "redis://localhost:6379/0"

            state = {
                "brand_name": "이디야커피",
                "business_type": "카페",
                "target_district": "서교동",
                "target_price_range": "",
                "operating_hours": [],
                "initial_capital": 0,
                "monthly_rent_budget": 0,
                "store_area": 15.0,
                "population_weight": True,
                "analysis_results": {
                    "market_report": "분석",
                    "population_report": "분석",
                    "legal_risks": risks,
                },
                "overall_legal_risk": "caution",
                "scouting_results": ranked,
                "winner_district": ranked[0]["district"],
                "top_3_candidates": [r["district"] for r in ranked[1:4]],
            }

            result = await synthesis_node(state)

        # LLM 실패해도 데이터 보존
        assert len(result["analysis_results"]["legal_risks"]) == 14
        assert len(result["analysis_results"]["district_rankings"]) == 16
        assert result["analysis_results"]["winner_district"] == ranked[0]["district"]
        assert result["overall_legal_risk"] == "caution"
        # fallback final_report이 생성됨
        assert "오류 발생" in result["analysis_results"]["final_report"]["summary"]
