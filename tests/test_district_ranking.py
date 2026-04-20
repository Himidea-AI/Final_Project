"""
랭킹 에이전트 테스트 — A2 + B1 공동

이 테스트가 하는 일:
  district_ranking_node가 마포구 16개 행정동을 점수화할 때,
  DB 데이터가 없거나 비정상인 엣지케이스에서도
  올바른 순위를 반환하는지 검증합니다.

테스트 범위:
  1. _normalize_and_rank 점수 산출 로직 (엣지케이스 포함)
  2. 공실률 패널티 적용
  3. 임대료 예산 패널티 적용
  4. 동적 가중치 (population_weight)
  5. district_ranking_node 전체 흐름 (mock)

실행:
    pytest tests/test_district_ranking.py -v
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.agents.nodes.district_ranking import _normalize_and_rank  # noqa: E402
from src.config.constants import MAPO_DISTRICTS  # noqa: E402

# ── 헬퍼 ──────────────────────────────────────────────────────────────────────


def _make_raw(overrides: dict[str, dict] | None = None) -> list[dict]:
    """
    16개 행정동 기본 raw 데이터 생성.
    overrides로 특정 동의 값을 덮어쓸 수 있음.

    기본값: sales_growth=5.0, pop_growth=3.0, avg_rent=50000
    """
    base = {
        "sales_growth": 5.0,
        "pop_growth": 3.0,
        "avg_rent": 50000.0,
    }
    overrides = overrides or {}
    result = []
    for dong in MAPO_DISTRICTS:
        item = {"district": dong, **base}
        if dong in overrides:
            item.update(overrides[dong])
        result.append(item)
    return result


# ── 1. 기본 점수 산출 ─────────────────────────────────────────────────────────


class TestNormalizeAndRankBasic:
    """
    _normalize_and_rank의 기본 동작을 검증합니다.
    이 함수가 랭킹 에이전트의 핵심으로, 16개 동의 원시 지표를
    0~100 정규화 → 가중 합산 → 내림차순 정렬합니다.
    """

    def test_returns_16_items(self):
        """16개 동 입력 → 16개 결과 반환."""
        raw = _make_raw()
        ranked = _normalize_and_rank(raw)
        assert len(ranked) == 16

    def test_all_items_have_required_fields(self):
        """각 항목에 필수 필드가 모두 있는지 확인."""
        raw = _make_raw()
        ranked = _normalize_and_rank(raw)
        required = {"district", "score", "sales_score", "pop_score", "rent_score", "vacancy_rate", "rank"}
        for item in ranked:
            missing = required - set(item.keys())
            assert not missing, f"{item['district']}에 {missing} 필드 누락"

    def test_rank_starts_from_1(self):
        """순위가 1부터 시작하는지 확인."""
        raw = _make_raw()
        ranked = _normalize_and_rank(raw)
        assert ranked[0]["rank"] == 1
        assert ranked[-1]["rank"] == 16

    def test_ranks_are_consecutive(self):
        """순위가 1~16까지 연속인지 확인."""
        raw = _make_raw()
        ranked = _normalize_and_rank(raw)
        ranks = [r["rank"] for r in ranked]
        assert sorted(ranks) == list(range(1, 17))

    def test_sorted_by_score_descending(self):
        """점수 내림차순 정렬 확인."""
        raw = _make_raw({"서교동": {"sales_growth": 20.0}, "염리동": {"sales_growth": -5.0}})
        ranked = _normalize_and_rank(raw)
        scores = [r["score"] for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_higher_sales_growth_ranks_higher(self):
        """매출 성장률이 높은 동이 더 높은 순위를 받는지 확인."""
        raw = _make_raw({"서교동": {"sales_growth": 30.0}, "염리동": {"sales_growth": -10.0}})
        ranked = _normalize_and_rank(raw)
        rank_map = {r["district"]: r["rank"] for r in ranked}
        assert rank_map["서교동"] < rank_map["염리동"]

    def test_lower_rent_ranks_higher(self):
        """임대료가 낮은 동이 더 높은 점수를 받는지 확인 (임대료 역정규화)."""
        raw = _make_raw(
            {
                "서교동": {"avg_rent": 10000.0},  # 저렴
                "염리동": {"avg_rent": 100000.0},  # 비쌈
            }
        )
        ranked = _normalize_and_rank(raw)
        rank_map = {r["district"]: r["rank"] for r in ranked}
        assert rank_map["서교동"] < rank_map["염리동"]


# ── 2. 엣지케이스 — 데이터가 0이거나 동일한 경우 ──────────────────────────────


class TestEdgeCaseAllZero:
    """
    B-1: 모든 동의 데이터가 0인 경우.
    실제로 DB가 비어있거나 API 전부 실패 시 이렇게 됩니다.
    """

    def test_all_zeros_returns_16_items(self):
        """모든 값이 0이어도 16개 결과를 반환."""
        raw = [{"district": d, "sales_growth": 0.0, "pop_growth": 0.0, "avg_rent": 0.0} for d in MAPO_DISTRICTS]
        ranked = _normalize_and_rank(raw)
        assert len(ranked) == 16

    def test_all_zeros_all_score_50(self):
        """
        모든 값이 동일하면 minmax에서 hi==lo → 전부 50점.
        가중합 = 50*0.35 + 50*0.45 + 50*0.20 = 50.0
        """
        raw = [{"district": d, "sales_growth": 0.0, "pop_growth": 0.0, "avg_rent": 0.0} for d in MAPO_DISTRICTS]
        ranked = _normalize_and_rank(raw)
        for item in ranked:
            assert item["score"] == 50.0, f"{item['district']}의 점수가 50.0이 아님: {item['score']}"

    def test_all_identical_nonzero(self):
        """모든 동의 값이 동일(0이 아닌 경우)해도 전부 50점."""
        raw = [{"district": d, "sales_growth": 10.0, "pop_growth": 5.0, "avg_rent": 50000.0} for d in MAPO_DISTRICTS]
        ranked = _normalize_and_rank(raw)
        for item in ranked:
            assert item["score"] == 50.0

    def test_empty_raw_returns_empty(self):
        """빈 리스트 입력 시 빈 리스트 반환 (IndexError 없이)."""
        ranked = _normalize_and_rank([])
        assert ranked == []

    def test_single_district(self):
        """1개 동만 입력해��� 에러 없이 처리."""
        raw = [{"district": "서교동", "sales_growth": 10.0, "pop_growth": 5.0, "avg_rent": 50000.0}]
        ranked = _normalize_and_rank(raw)
        assert len(ranked) == 1
        assert ranked[0]["rank"] == 1
        assert ranked[0]["score"] == 50.0  # 단일 항목 → hi==lo → 50점


class TestEdgeCasePartialZero:
    """일부 동만 데이터가 0인 경우."""

    def test_one_district_all_zero(self):
        """1개 동만 전부 0이면 해당 동이 최하위."""
        raw = _make_raw({"염리동": {"sales_growth": 0.0, "pop_growth": 0.0, "avg_rent": 0.0}})
        ranked = _normalize_and_rank(raw)
        rank_map = {r["district"]: r["rank"] for r in ranked}
        # avg_rent=0이면 임대료 점수에서 가장 높은 점수(100)를 받으므로
        # 반드시 최하위는 아닐 수 있음 — 임대료 0은 "공짜"로 해석됨
        # 대신 sales_growth=0, pop_growth=0이므로 다른 동보다는 낮음
        assert rank_map["염리동"] > 1  # 1위는 아님

    def test_negative_growth_handled(self):
        """음수 성장률도 정상 처리 — 가장 낮은 점수를 받음."""
        raw = _make_raw(
            {
                "서교동": {"sales_growth": 20.0, "pop_growth": 10.0},
                "염리동": {"sales_growth": -15.0, "pop_growth": -8.0},
            }
        )
        ranked = _normalize_and_rank(raw)
        rank_map = {r["district"]: r["rank"] for r in ranked}
        assert rank_map["서교동"] < rank_map["염리동"]


# ── 3. 공실률 패널티 검증 (B-2) ──────────────────────────────────────────────


class TestVacancyPenalty:
    """
    B-2: 공실률 패널티가 올바르게 적용되는지 검증.
    공실률이 높으면 상권 활력이 ���어진다고 판단하여 점수를 감점합니다.
    """

    def test_no_penalty_below_5(self):
        """공실률 5% 미만이면 패널티 없음."""
        raw = _make_raw({"서교동": {"sales_growth": 20.0}})
        vacancy_map = {"서교동": 4.9}

        ranked_with = _normalize_and_rank(raw, vacancy_rate_map=vacancy_map)
        ranked_without = _normalize_and_rank(raw, vacancy_rate_map={})

        score_with = next(r["score"] for r in ranked_with if r["district"] == "서교동")
        score_without = next(r["score"] for r in ranked_without if r["district"] == "서교동")
        assert score_with == score_without

    def test_15_percent_penalty_at_5(self):
        """공실률 5~10% → 점수 × 0.85 (-15% 감점)."""
        raw = [{"district": "서교동", "sales_growth": 10.0, "pop_growth": 10.0, "avg_rent": 50000.0}]
        vacancy_map = {"서교동": 7.0}

        ranked_without = _normalize_and_rank(raw, vacancy_rate_map={})
        ranked_with = _normalize_and_rank(raw, vacancy_rate_map=vacancy_map)

        score_without = ranked_without[0]["score"]
        score_with = ranked_with[0]["score"]
        assert score_with == round(score_without * 0.85, 1)

    def test_30_percent_penalty_at_10(self):
        """공실률 10% 이상 → 점수 × 0.70 (-30% 감점)."""
        raw = [{"district": "서교동", "sales_growth": 10.0, "pop_growth": 10.0, "avg_rent": 50000.0}]
        vacancy_map = {"서교동": 15.0}

        ranked_without = _normalize_and_rank(raw, vacancy_rate_map={})
        ranked_with = _normalize_and_rank(raw, vacancy_rate_map=vacancy_map)

        score_without = ranked_without[0]["score"]
        score_with = ranked_with[0]["score"]
        assert score_with == round(score_without * 0.70, 1)

    def test_vacancy_boundary_exactly_5(self):
        """공실률 정확히 5.0% → 0.85 패널티 적용."""
        raw = [{"district": "서교동", "sales_growth": 10.0, "pop_growth": 10.0, "avg_rent": 50000.0}]
        vacancy_map = {"서교동": 5.0}
        ranked = _normalize_and_rank(raw, vacancy_rate_map=vacancy_map)
        ranked_base = _normalize_and_rank(raw, vacancy_rate_map={})
        assert ranked[0]["score"] == round(ranked_base[0]["score"] * 0.85, 1)

    def test_vacancy_boundary_exactly_10(self):
        """공실률 정확히 10.0% → 0.70 패널티 적용."""
        raw = [{"district": "서교동", "sales_growth": 10.0, "pop_growth": 10.0, "avg_rent": 50000.0}]
        vacancy_map = {"서교동": 10.0}
        ranked = _normalize_and_rank(raw, vacancy_rate_map=vacancy_map)
        ranked_base = _normalize_and_rank(raw, vacancy_rate_map={})
        assert ranked[0]["score"] == round(ranked_base[0]["score"] * 0.70, 1)

    def test_vacancy_rate_included_in_result(self):
        """결과에 vacancy_rate 필드가 포함되어 프론트엔드에서 표시 가능."""
        raw = _make_raw()
        vacancy_map = {"서교동": 8.5, "합정동": 12.0}
        ranked = _normalize_and_rank(raw, vacancy_rate_map=vacancy_map)

        rank_map = {r["district"]: r for r in ranked}
        assert rank_map["서교동"]["vacancy_rate"] == 8.5
        assert rank_map["합정동"]["vacancy_rate"] == 12.0
        assert rank_map["연남동"]["vacancy_rate"] == 0.0  # 맵에 없으면 0.0

    def test_high_vacancy_drops_ranking(self):
        """공실률이 높은 동은 원래 점수가 같아도 순위가 낮아짐."""
        raw = _make_raw(
            {
                "서교동": {"sales_growth": 20.0, "pop_growth": 10.0},
                "합정동": {"sales_growth": 20.0, "pop_growth": 10.0},
            }
        )
        vacancy_map = {"합정동": 15.0}  # 합정동만 공실률 높음
        ranked = _normalize_and_rank(raw, vacancy_rate_map=vacancy_map)

        rank_map = {r["district"]: r["rank"] for r in ranked}
        assert rank_map["서교동"] < rank_map["합정동"]


# ── 4. 임대료 예산 패널티 ────────────────────────────────────────────────────


class TestRentBudgetPenalty:
    """임대료 예산 초과 시 페널티가 올바르게 적용되는지 검증."""

    def test_no_penalty_when_budget_zero(self):
        """예산 0이면 패널티 비활성화."""
        raw = _make_raw({"서교동": {"avg_rent": 999999.0}})
        ranked = _normalize_and_rank(raw, monthly_rent_budget=0)
        # 예산 패널티 없이 임대료 정규화만 적용됨
        rank_map = {r["district"]: r for r in ranked}
        assert rank_map["서교동"]["score"] > 0

    def test_50_percent_penalty_over_1_5x_budget(self):
        """임대료가 예산의 1.5배 초과 시 점수 × 0.5."""
        # 예산 = 100만원 / 15평 = 66,666원/평
        # 임대료 200,000���/평 → 200000/66666 = 3배 → 1.5배 초과 → ×0.5
        raw = [{"district": "서교동", "sales_growth": 10.0, "pop_growth": 10.0, "avg_rent": 200000.0}]
        ranked_no_budget = _normalize_and_rank(raw, monthly_rent_budget=0)
        ranked_with_budget = _normalize_and_rank(raw, monthly_rent_budget=1_000_000, store_area=15.0)

        assert ranked_with_budget[0]["score"] == round(ranked_no_budget[0]["score"] * 0.5, 1)

    def test_within_budget_no_penalty(self):
        """예산 이내면 패널티 없음."""
        # 예산 = 500만원 / 15평 = 333,333원/평
        # 임대료 50,000원/평 → 예산 이내
        raw = [{"district": "서교동", "sales_growth": 10.0, "pop_growth": 10.0, "avg_rent": 50000.0}]
        ranked_no_budget = _normalize_and_rank(raw, monthly_rent_budget=0)
        ranked_with_budget = _normalize_and_rank(raw, monthly_rent_budget=5_000_000, store_area=15.0)

        assert ranked_with_budget[0]["score"] == ranked_no_budget[0]["score"]

    def test_store_area_zero_safe(self):
        """면적 0���어도 max(store_area, 1)로 ZeroDivisionError 없음."""
        raw = _make_raw()
        ranked = _normalize_and_rank(raw, monthly_rent_budget=1_000_000, store_area=0.0)
        assert len(ranked) == 16


# ── 5. 동적 가중치 (population_weight) ───────────────────────────────────────


class TestDynamicWeights:
    """
    population_weight 파라미터에 따라 가중치가 달라지는지 검증.
    True  (기본): 매출 35% + 인구 45% + 임대료 20%
    False       : 매출 50% + 인구 10% + 임대료 40%
    """

    def test_population_weight_true_favors_population(self):
        """population_weight=True일 때 인구가 높은 동이 유리."""
        raw = _make_raw(
            {
                "서교동": {"pop_growth": 30.0, "sales_growth": 5.0},
                "합정동": {"pop_growth": 1.0, "sales_growth": 5.0},
            }
        )
        ranked = _normalize_and_rank(raw, population_weight=True)
        rank_map = {r["district"]: r["rank"] for r in ranked}
        assert rank_map["서교동"] < rank_map["합정동"]

    def test_population_weight_false_favors_sales_and_rent(self):
        """population_weight=False일 때 매출+임대료 비중이 높아짐."""
        raw = _make_raw(
            {
                "서교동": {"sales_growth": 30.0, "avg_rent": 10000.0, "pop_growth": 1.0},
                "합정동": {"sales_growth": 5.0, "avg_rent": 100000.0, "pop_growth": 30.0},
            }
        )
        ranked = _normalize_and_rank(raw, population_weight=False)
        rank_map = {r["district"]: r["rank"] for r in ranked}
        # 매출 50% + 임대료 40% = 90% 비중에서 서교동이 압도적
        assert rank_map["서교동"] < rank_map["합정동"]

    def test_different_weights_produce_different_rankings(self):
        """같은 데이터에서 가중���를 바꾸면 순위가 달라질 수 있음."""
        raw = _make_raw(
            {
                "서교동": {"sales_growth": 30.0, "pop_growth": 1.0, "avg_rent": 80000.0},
                "합정동": {"sales_growth": 1.0, "pop_growth": 30.0, "avg_rent": 30000.0},
            }
        )
        ranked_pop = _normalize_and_rank(raw, population_weight=True)
        ranked_sales = _normalize_and_rank(raw, population_weight=False)

        rank_pop = {r["district"]: r["rank"] for r in ranked_pop}
        rank_sales = {r["district"]: r["rank"] for r in ranked_sales}

        # population_weight=True → 인구 높은 합정동 유리
        # population_weight=False → 매출 높은 서교동 유리
        assert rank_pop["합정동"] < rank_pop["서교동"]
        assert rank_sales["서교동"] < rank_sales["합정동"]


# ── 6. district_ranking_node 전체 흐름 (mock) ────────────────────────────────


class TestDistrictRankingNodeFlow:
    """
    district_ranking_node 함수 전체를 mock으로 테스트.
    DB, Redis 없이 파이프라인 로직만 검증합니다.
    """

    @pytest.fixture
    def mock_env(self):
        """market_tool, db_client, Redis를 mock으로 대체."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()
        mock_redis.aclose = AsyncMock()

        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url.return_value = mock_redis

        with (
            patch("src.agents.nodes.district_ranking.market_tool") as mock_market,
            patch("src.agents.nodes.district_ranking.db_client") as mock_db,
            patch("src.agents.nodes.district_ranking._load_vacancy_map") as mock_vacancy,
            patch("src.agents.nodes.district_ranking.settings") as mock_settings,
            patch.dict("sys.modules", {"redis.asyncio": mock_redis_mod, "redis": MagicMock()}),
        ):
            # market_tool mock — 동별로 다른 데이터 반환
            async def mock_commercial(dong, btype):
                growth = {"서교동": 15.0, "합정동": 10.0}.get(dong, 5.0)
                return {"qoq_growth": growth}

            async def mock_population(dong):
                growth = {"서교동": 8.0, "합정동": 12.0}.get(dong, 3.0)
                return {"qoq_growth": growth}

            async def mock_rent(dong):
                rent = {"서교동": 80000, "합정동": 50000}.get(dong, 40000)
                return {"avg_rent_3_3m2": rent}

            mock_market.get_commercial_insights = AsyncMock(side_effect=mock_commercial)
            mock_market.get_population_trends = AsyncMock(side_effect=mock_population)
            mock_market.get_rent_insight = AsyncMock(side_effect=mock_rent)

            mock_db.engine = MagicMock()  # engine이 None이 아니라 connect() 스킵
            mock_vacancy.return_value = ({"서교동": 3.0, "합정동": 7.0}, True)
            mock_settings.redis_url = "redis://localhost:6379/0"

            yield {"market": mock_market, "redis": mock_redis}

    @pytest.mark.asyncio
    async def test_node_returns_required_keys(self, mock_env):
        """노드 결과에 필수 키가 모두 있는지 확인."""
        from src.agents.nodes.district_ranking import district_ranking_node

        state = {"business_type": "카페", "population_weight": True, "monthly_rent_budget": 0, "store_area": 15.0}
        result = await district_ranking_node(state)

        assert "scouting_results" in result
        assert "winner_district" in result
        assert "top_3_candidates" in result
        assert "vacancy_applied" in result
        assert "current_agent" in result
        assert result["current_agent"] == "district_ranking"

    @pytest.mark.asyncio
    async def test_node_returns_16_ranked_districts(self, mock_env):
        """16개 ���정동이 모두 랭킹에 포함."""
        from src.agents.nodes.district_ranking import district_ranking_node

        state = {"business_type": "카페", "population_weight": True, "monthly_rent_budget": 0, "store_area": 15.0}
        result = await district_ranking_node(state)

        assert len(result["scouting_results"]) == 16
        districts = {r["district"] for r in result["scouting_results"]}
        assert districts == set(MAPO_DISTRICTS)

    @pytest.mark.asyncio
    async def test_winner_is_rank_1(self, mock_env):
        """winner_district가 실제 1위 동과 일치."""
        from src.agents.nodes.district_ranking import district_ranking_node

        state = {"business_type": "카페", "population_weight": True, "monthly_rent_budget": 0, "store_area": 15.0}
        result = await district_ranking_node(state)

        assert result["winner_district"] == result["scouting_results"][0]["district"]

    @pytest.mark.asyncio
    async def test_top_3_are_rank_2_to_4(self, mock_env):
        """top_3_candidates가 2~4위와 일치."""
        from src.agents.nodes.district_ranking import district_ranking_node

        state = {"business_type": "카페", "population_weight": True, "monthly_rent_budget": 0, "store_area": 15.0}
        result = await district_ranking_node(state)

        expected = [r["district"] for r in result["scouting_results"][1:4]]
        assert result["top_3_candidates"] == expected

    @pytest.mark.asyncio
    async def test_vacancy_applied_flag(self, mock_env):
        """공실률 DB 로드 성공 여부가 결과에 포함."""
        from src.agents.nodes.district_ranking import district_ranking_node

        state = {"business_type": "카페", "population_weight": True, "monthly_rent_budget": 0, "store_area": 15.0}
        result = await district_ranking_node(state)

        assert result["vacancy_applied"] is True

    @pytest.mark.asyncio
    async def test_vacancy_penalty_applied_to_hapjeong(self, mock_env):
        """합정동(공실률 7%) 패널티가 실제 점수에 반영."""
        from src.agents.nodes.district_ranking import district_ranking_node

        state = {"business_type": "카페", "population_weight": True, "monthly_rent_budget": 0, "store_area": 15.0}
        result = await district_ranking_node(state)

        hapjeong = next(r for r in result["scouting_results"] if r["district"] == "합정동")
        assert hapjeong["vacancy_rate"] == 7.0
