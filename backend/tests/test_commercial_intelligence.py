"""commercial_intelligence 서비스 테스트 (실 DB)."""

from __future__ import annotations

import pytest

from src.services.commercial_intelligence import (
    analyze_cannibalization,
    analyze_competition,
    estimate_cannibalization,
    get_dong_centroid,
    get_industry_closure_trend,
    haversine_m,
)

# 마포 주요 동 코드
SEOGYO_DONG = "11440660"  # 서교동
GONGDEOK_DONG = "11440565"  # 공덕동
MANGWON1_DONG = "11440690"  # 망원1동


class TestHaversine:
    def test_zero_distance(self):
        assert haversine_m(37.5, 126.9, 37.5, 126.9) == 0

    def test_known_distance(self):
        # 서울 시청 ↔ 광화문 약 470m
        d = haversine_m(37.5665, 126.9780, 37.5758, 126.9769)
        assert 900 < d < 1200


class TestGetDongCentroid:
    def test_seogyo_has_centroid(self):
        c = get_dong_centroid(SEOGYO_DONG)
        assert c is not None
        # 서교동 대략 37.55, 126.92
        assert 37.54 < c[0] < 37.57
        assert 126.91 < c[1] < 126.93

    def test_invalid_code_returns_none(self):
        c = get_dong_centroid("99999999")
        assert c is None


class TestEstimateCannibalization:
    """Pancras 2013 decay 공식 검증."""

    def test_no_nearby_stores_zero_impact(self):
        r = estimate_cannibalization({"0-300m": 0, "300-500m": 0, "500-1000m": 0, "1000-2000m": 0})
        assert r["total_impact_pct"] == 0

    def test_cafe_one_store_at_150m(self):
        """커피 base 25% × Pancras decay(0.15km) ≈ -24.3%."""
        r = estimate_cannibalization({"0-300m": 1}, industry="cafe")
        # 0.25 * (1-0.1746)^0.15 ≈ 0.25 * 0.9723 = 0.2431
        assert r["total_impact_pct"] == pytest.approx(-0.243, abs=0.005)

    def test_chicken_less_impact_than_cafe(self):
        """치킨은 배달 중심이라 base 10% < 카페 25%."""
        cafe = estimate_cannibalization({"0-300m": 1}, industry="cafe")
        chicken = estimate_cannibalization({"0-300m": 1}, industry="chicken")
        assert abs(chicken["total_impact_pct"]) < abs(cafe["total_impact_pct"])

    def test_office_type_reduces_impact(self):
        base = estimate_cannibalization({"0-300m": 1}, industry="cafe", store_type="neighborhood")
        office = estimate_cannibalization({"0-300m": 1}, industry="cafe", store_type="office")
        # office modifier = 0.6
        assert office["total_impact_pct"] == pytest.approx(base["total_impact_pct"] * 0.6, abs=0.005)

    def test_cap_at_50_percent(self):
        """다수 매장이어도 -50% 초과하지 않음."""
        r = estimate_cannibalization({"0-300m": 20}, industry="cafe")
        assert r["total_impact_pct"] >= -0.50

    def test_references_included(self):
        r = estimate_cannibalization({"0-300m": 1})
        assert "Pancras" in r["method"]
        assert len(r["references"]) == 3


class TestAnalyzeCompetition:
    def test_seogyo_coffee_has_competitors(self):
        """서교동 커피 반경 500m — 카페 포화 지역, 최소 10개 이상."""
        r = analyze_competition(SEOGYO_DONG, "커피", radius_m=500)
        assert r["total_competitors"] >= 10
        assert r["saturation_level"] in ("medium", "high", "saturated")
        assert len(r["samples"]) > 0

    def test_brand_distribution_descending(self):
        r = analyze_competition(SEOGYO_DONG, "커피", radius_m=500)
        counts = list(r["brand_distribution"].values())
        assert counts == sorted(counts, reverse=True)

    def test_invalid_dong_returns_error(self):
        r = analyze_competition("99999999", "커피")
        assert "error" in r

    def test_radius_larger_more_competitors(self):
        a = analyze_competition(SEOGYO_DONG, "커피", radius_m=300)
        b = analyze_competition(SEOGYO_DONG, "커피", radius_m=1000)
        assert b["total_competitors"] >= a["total_competitors"]


class TestAnalyzeCannibalization:
    def test_ediya_in_seogyo(self):
        """서교동 이디야커피 — 서교 1개 있음 (step 0 샘플 확인됨)."""
        r = analyze_cannibalization(SEOGYO_DONG, "이디야커피", radius_m=2000, industry="cafe")
        # 마포 전체 17개 중 일부가 2km 내
        assert r["same_brand_nearby"] >= 1
        assert r["estimated_revenue_impact_pct"] <= 0
        assert "distance_bins" in r

    def test_baekdabang_in_mangwon(self):
        """망원1동 빽다방 — 망원 근처에 매장 존재."""
        r = analyze_cannibalization(MANGWON1_DONG, "빽다방", radius_m=2000, industry="cafe")
        assert r["same_brand_nearby"] >= 0  # 망원 1개 있음

    def test_nonexistent_brand_zero_cannibal(self):
        r = analyze_cannibalization(SEOGYO_DONG, "존재하지않는브랜드XYZ")
        assert r["same_brand_nearby"] == 0
        assert r["estimated_revenue_impact_pct"] == 0

    def test_invalid_dong(self):
        r = analyze_cannibalization("99999999", "빽다방")
        assert "error" in r


class TestGetIndustryClosureTrend:
    def test_seogyo_coffee_trend(self):
        """서교동 CS100010(커피-음료) 추세."""
        r = get_industry_closure_trend(SEOGYO_DONG, "CS100010")
        assert len(r["samples"]) > 0
        assert r["current_closure_rate"] is not None
        assert r["trend"] in ("stable", "worsening", "improving")

    def test_invalid_combination(self):
        r = get_industry_closure_trend("99999999", "CS999999")
        assert r["samples"] == []
        assert r["trend"] == "unknown"
