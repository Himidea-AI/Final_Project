"""specialist_franchise_law 영업지역 정량 룰 unit test.

`_territory_to_level` 임계값 검증. RAG/LLM 의존성 없음.
"""

from src.agents.legal.specialists import _territory_to_level


class TestTerritoryRule:
    def test_empty_returns_none(self):
        level, hint = _territory_to_level({})
        assert level is None
        assert hint == ""

    def test_no_nearby_returns_none(self):
        t = {"same_brand_500m": 0, "same_brand_2000m": 0, "closest_m": None, "impact_pct": 0.0}
        level, _ = _territory_to_level(t)
        assert level is None

    def test_one_within_500m_caution(self):
        t = {
            "same_brand_500m": 1,
            "same_brand_2000m": 1,
            "closest_m": 350.0,
            "impact_pct": -0.02,
        }
        level, hint = _territory_to_level(t)
        assert level == "caution"
        assert "1개" in hint
        assert "350m" in hint

    def test_one_within_500m_high_impact_danger(self):
        t = {
            "same_brand_500m": 1,
            "same_brand_2000m": 1,
            "closest_m": 200.0,
            "impact_pct": -0.08,
        }
        level, _ = _territory_to_level(t)
        assert level == "danger"

    def test_three_within_2000m_caution(self):
        t = {
            "same_brand_500m": 0,
            "same_brand_2000m": 3,
            "closest_m": 1500.0,
            "impact_pct": -0.03,
        }
        level, _ = _territory_to_level(t)
        assert level == "caution"

    def test_two_within_2000m_no_floor(self):
        # 2000m 내 2개 + 500m 내 0 → 임계값 미달, LLM 자유 판단
        t = {
            "same_brand_500m": 0,
            "same_brand_2000m": 2,
            "closest_m": 1200.0,
            "impact_pct": -0.01,
        }
        level, _ = _territory_to_level(t)
        assert level is None

    def test_impact_threshold_boundary(self):
        # impact_pct == -0.05 정확히 → danger (≤ -5%)
        t = {
            "same_brand_500m": 1,
            "same_brand_2000m": 1,
            "closest_m": 400.0,
            "impact_pct": -0.05,
        }
        level, _ = _territory_to_level(t)
        assert level == "danger"
