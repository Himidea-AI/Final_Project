"""specialist_franchise_law 영업지역 정량 룰 unit test.

`_territory_to_level` 임계값 검증 + `_INDUSTRY_LABEL_MAP` 매핑.
RAG/LLM 의존성 없음.
"""

from src.agents.legal.specialists import (
    _INDUSTRY_DEFAULT,
    _INDUSTRY_LABEL_MAP,
    _territory_to_level,
)
from src.config.constants import BIZ_NORMALIZE


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


class TestIndustryLabelMap:
    """_analyze_territory 업종 → industry 라벨 동적 매핑.

    BIZ_NORMALIZE → _INDUSTRY_LABEL_MAP → analyze_cannibalization industry.
    """

    def _resolve(self, business_type: str) -> str:
        biz = BIZ_NORMALIZE.get((business_type or "").lower(), business_type or "")
        return _INDUSTRY_LABEL_MAP.get(biz, _INDUSTRY_DEFAULT)

    def test_cafe_english(self):
        assert self._resolve("cafe") == "cafe"

    def test_coffee_korean_normalizes_to_cafe(self):
        # 사용자 신고: "커피"가 카페 매핑돼야 cannibalization 정확 산출
        assert self._resolve("커피") == "cafe"

    def test_restaurant_korean(self):
        assert self._resolve("음식점") == "restaurant"

    def test_korean_food_normalizes_to_restaurant(self):
        for biz in ("한식", "중식", "일식", "분식", "치킨"):
            assert self._resolve(biz) == "restaurant", f"{biz} → restaurant 기대"

    def test_convenience(self):
        assert self._resolve("편의점") == "convenience"

    def test_unmapped_falls_back_to_default(self):
        # BIZ_NORMALIZE 미등록 임의 입력 — cafe 강제 매핑되지 않아야 함
        assert self._resolve("미용실") == _INDUSTRY_DEFAULT
        assert self._resolve("스튜디오") == _INDUSTRY_DEFAULT


class TestSafeFloorSkip:
    """rule engine 경로에서 _SAFE_FLOOR 가 safety_regulation safe 를 보존."""

    def test_convenience_large_area_stays_safe(self):
        # 편의점 200평 → 다중이용업 미해당 → safety_regulation safe
        from src.agents.legal.rules import rule_safety_regulation

        r = rule_safety_regulation("convenience", 200.0)
        assert r["level"] == "safe"
        # rule engine 경로에서는 legal.py _SAFE_FLOOR skip 으로 caution 강제 안 됨

    def test_cafe_small_area_safe(self):
        from src.agents.legal.rules import rule_safety_regulation

        r = rule_safety_regulation("cafe", 25.0)
        assert r["level"] == "safe"
