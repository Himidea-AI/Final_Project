"""법률 룰 엔진 unit tests — 8 함수 × 면적 경계/업종 케이스.

면적 경계:
- safety_regulation: 30평(99㎡) → safe, 31평(102.3㎡) → danger (카페/음식점)
- safety_regulation: 주점은 면적 무관 danger
- accessibility_law: 90평(297㎡) → safe, 91평(300.3㎡) → danger
- fire_safety_law: 30평 → caution, 31평 → danger / 주점은 면적 무관 danger

업종:
- food_hygiene: 카페/cafe → danger, 음식점/restaurant → danger, 주점/pub → danger
- 미지원 업종 (예: 미용실) → caution
- BIZ_NORMALIZE: "카페" == "cafe" 동등성
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# tests/ 디렉토리에서 backend/src 임포트 가능하도록
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src.agents.legal.rules import (  # noqa: E402
    ACCESSIBILITY_THRESHOLD_M2,
    MULTI_USE_THRESHOLD_M2,
    SCHOOL_ABSOLUTE_ZONE_M,
    SCHOOL_RELATIVE_ZONE_M,
    rule_accessibility,
    rule_commercial_lease,
    rule_fire_safety,
    rule_food_hygiene,
    rule_labor,
    rule_safety_regulation,
    rule_school_zone,
    rule_sewage,
    rule_vat,
    _pyeong_to_m2,
)


# ---------------------------------------------------------------------------
# 1. food_hygiene
# ---------------------------------------------------------------------------


class TestFoodHygiene:
    def test_cafe_danger(self):
        r = rule_food_hygiene("cafe")
        assert r["type"] == "food_hygiene"
        assert r["level"] == "danger"
        assert "제37조" in r["recommendation"]

    def test_restaurant_danger(self):
        r = rule_food_hygiene("restaurant")
        assert r["level"] == "danger"
        assert "영업신고" in r["recommendation"] or "신고" in r["recommendation"]

    def test_pub_danger(self):
        r = rule_food_hygiene("pub")
        assert r["level"] == "danger"
        # 단란/유흥 영업허가 명시 (제37조 제1항)
        assert "허가" in r["summary"] or "제1항" in r["recommendation"]

    def test_korean_pub_equivalent(self):
        ko = rule_food_hygiene("주점")
        en = rule_food_hygiene("pub")
        assert ko["level"] == en["level"] == "danger"

    def test_pub_variants_normalized(self):
        for biz in ("호프", "단란주점", "유흥주점", "술집", "bar"):
            assert rule_food_hygiene(biz)["level"] == "danger", f"{biz} should be danger"

    def test_korean_cafe_equivalent_to_english(self):
        ko = rule_food_hygiene("카페")
        en = rule_food_hygiene("cafe")
        assert ko["level"] == en["level"] == "danger"

    def test_coffee_normalized_to_cafe(self):
        # frontend가 "커피"로 보낼 때도 카페와 동일 처리
        assert rule_food_hygiene("커피")["level"] == "danger"

    def test_bakery_normalized_to_cafe(self):
        assert rule_food_hygiene("베이커리")["level"] == "danger"

    def test_korean_food_normalized_to_restaurant(self):
        for biz in ("한식", "중식", "일식", "분식"):
            assert rule_food_hygiene(biz)["level"] == "danger", f"{biz} should be danger"

    def test_unknown_business_type_caution(self):
        r = rule_food_hygiene("unknown_biz")
        assert r["level"] == "caution"


# ---------------------------------------------------------------------------
# 2. safety_regulation — 100㎡ 면적 경계
# ---------------------------------------------------------------------------


class TestSafetyRegulation:
    def test_30_pyeong_safe(self):
        # 30평 = 99㎡ < 100㎡ → safe
        r = rule_safety_regulation("cafe", 30.0)
        assert r["type"] == "safety_regulation"
        assert r["level"] == "safe"

    def test_31_pyeong_danger(self):
        # 31평 = 102.3㎡ ≥ 100㎡ → danger
        r = rule_safety_regulation("cafe", 31.0)
        assert r["level"] == "danger"
        assert "다중이용업소법" in r["recommendation"] or "완비증명" in r["recommendation"]

    def test_exact_boundary_just_below(self):
        # 30.30평 = 99.99㎡ < 100㎡ — safe
        r = rule_safety_regulation("cafe", 30.30)
        assert r["level"] == "safe"

    def test_exact_boundary_just_above(self):
        # 30.31평 = 100.023㎡ ≥ 100㎡ — danger
        r = rule_safety_regulation("cafe", 30.31)
        assert r["level"] == "danger"

    def test_restaurant_large_danger(self):
        r = rule_safety_regulation("음식점", 50.0)
        assert r["level"] == "danger"

    def test_pub_small_area_danger(self):
        # 주점은 면적 무관 다중이용업 (단란/유흥) — 10평이어도 danger
        r = rule_safety_regulation("pub", 10.0)
        assert r["level"] == "danger"

    def test_pub_korean_small_area_danger(self):
        r = rule_safety_regulation("주점", 15.0)
        assert r["level"] == "danger"
        assert "다중이용업" in r["summary"]

    def test_unknown_business_safe(self):
        # 미지원 업종 (예: 미용실) — 다중이용업 미해당 → safe
        r = rule_safety_regulation("미용실", 200.0)
        assert r["level"] == "safe"

    def test_threshold_constant_correct(self):
        assert MULTI_USE_THRESHOLD_M2 == 100.0


# ---------------------------------------------------------------------------
# 3. fire_safety_law
# ---------------------------------------------------------------------------


class TestFireSafety:
    def test_small_caution(self):
        r = rule_fire_safety("cafe", 20.0)
        assert r["type"] == "fire_safety_law"
        assert r["level"] == "caution"

    def test_large_danger(self):
        r = rule_fire_safety("cafe", 50.0)
        assert r["level"] == "danger"
        assert "소방시설법" in r["recommendation"] or "제12조" in r["recommendation"]

    def test_boundary_30_pyeong_caution(self):
        # 30평 = 99㎡ < 100㎡ → caution
        r = rule_fire_safety("restaurant", 30.0)
        assert r["level"] == "caution"

    def test_boundary_31_pyeong_danger(self):
        r = rule_fire_safety("restaurant", 31.0)
        assert r["level"] == "danger"

    def test_pub_small_area_danger(self):
        # 주점은 면적 무관 소방시설 강화 — 10평이어도 danger
        r = rule_fire_safety("pub", 10.0)
        assert r["level"] == "danger"
        assert "다중이용업" in r["summary"] or "소방시설" in r["recommendation"]

    def test_pub_korean_danger(self):
        assert rule_fire_safety("주점", 5.0)["level"] == "danger"


# ---------------------------------------------------------------------------
# 4. accessibility_law — 300㎡ 경계
# ---------------------------------------------------------------------------


class TestAccessibility:
    def test_90_pyeong_safe(self):
        # 90평 = 297㎡ < 300㎡ → safe
        r = rule_accessibility("cafe", 90.0)
        assert r["type"] == "accessibility_law"
        assert r["level"] == "safe"

    def test_91_pyeong_danger(self):
        # 91평 = 300.3㎡ ≥ 300㎡ → danger
        r = rule_accessibility("cafe", 91.0)
        assert r["level"] == "danger"
        assert "편의시설" in r["summary"] or "장애인" in r["summary"]

    def test_pub_large_danger(self):
        # 주점도 ≥300㎡ 시 편의시설 의무 대상
        r = rule_accessibility("pub", 91.0)
        assert r["level"] == "danger"

    def test_pub_small_safe(self):
        # 주점이라도 300㎡ 미만은 safe
        r = rule_accessibility("주점", 50.0)
        assert r["level"] == "safe"

    def test_unknown_biz_large_safe(self):
        # 식품접객업 외 업종은 300㎡ 이상이어도 본 룰엔진 기준 safe
        r = rule_accessibility("미용실", 200.0)
        assert r["level"] == "safe"

    def test_threshold_constant_correct(self):
        assert ACCESSIBILITY_THRESHOLD_M2 == 300.0


# ---------------------------------------------------------------------------
# 5. commercial_lease_law — 항상 caution
# ---------------------------------------------------------------------------


class TestCommercialLease:
    def test_always_caution(self):
        r = rule_commercial_lease()
        assert r["type"] == "commercial_lease_law"
        assert r["level"] == "caution"
        assert "권리금" in r["recommendation"] or "제10조" in r["recommendation"]

    def test_articles_present(self):
        r = rule_commercial_lease()
        assert isinstance(r["articles"], list)
        assert len(r["articles"]) >= 1


# ---------------------------------------------------------------------------
# 6. labor_law — 항상 caution
# ---------------------------------------------------------------------------


class TestLabor:
    def test_always_caution(self):
        r = rule_labor()
        assert r["type"] == "labor_law"
        assert r["level"] == "caution"
        assert "근로계약서" in r["recommendation"] or "제17조" in r["recommendation"]


# ---------------------------------------------------------------------------
# 7. vat_law — 항상 caution
# ---------------------------------------------------------------------------


class TestVat:
    def test_always_caution(self):
        r = rule_vat()
        assert r["type"] == "vat_law"
        assert r["level"] == "caution"
        assert "사업자등록" in r["recommendation"] or "제8조" in r["recommendation"]


# ---------------------------------------------------------------------------
# 8. sewage_law — 음식점만 caution
# ---------------------------------------------------------------------------


class TestSewage:
    def test_restaurant_caution(self):
        r = rule_sewage("restaurant")
        assert r["type"] == "sewage_law"
        assert r["level"] == "caution"
        assert "그리스트랩" in r["recommendation"] or "유분" in r["recommendation"]

    def test_cafe_caution(self):
        # 카페(휴게음식점)도 식품위생법 시행규칙 별표 14 시설기준 적용
        # 세척수·음료 잔여물 배출 → 배수설비 기준 검토 필요
        r = rule_sewage("cafe")
        assert r["level"] == "caution"
        assert "휴게음식점" in r["summary"] or "별표 14" in r["recommendation"]

    def test_coffee_korean_caution(self):
        # "커피" 한글 입력도 카페 정규화 → caution
        assert rule_sewage("커피")["level"] == "caution"

    def test_pub_caution(self):
        # 주점도 알코올 잔여물·세척수 → 배수설비 caution
        r = rule_sewage("pub")
        assert r["level"] == "caution"
        assert "알코올" in r["summary"] or "그리스트랩" in r["recommendation"]

    def test_korean_pub_caution(self):
        assert rule_sewage("주점")["level"] == "caution"
        assert rule_sewage("호프")["level"] == "caution"

    def test_unknown_biz_safe(self):
        # 식품접객업 외 업종 → safe
        r = rule_sewage("미용실")
        assert r["level"] == "safe"

    def test_korean_restaurant(self):
        r = rule_sewage("음식점")
        assert r["level"] == "caution"


# ---------------------------------------------------------------------------
# 9. school_zone — 학교환경위생정화구역 (학교보건법 제6조)
# ---------------------------------------------------------------------------


# 망원초등학교 (mock fallback 좌표) 기준 거리 case 좌표
_MOCK_SCHOOL_LAT = 37.5567
_MOCK_SCHOOL_LON = 126.9038


def _offset_lat(meters: float) -> float:
    """기준 위도에서 N미터 이동한 위도 — 1deg ≈ 111_000m."""
    return _MOCK_SCHOOL_LAT + meters / 111_000.0


# 학교 1개 fixture (절대정화구역 거리 검증용)
_SAMPLE_SCHOOLS = [
    {
        "name": "테스트초등학교",
        "school_type": "초등학교",
        "lat": _MOCK_SCHOOL_LAT,
        "lon": _MOCK_SCHOOL_LON,
        "district": "망원1동",
    }
]


class TestSchoolZone:
    def test_constants_correct(self):
        assert SCHOOL_ABSOLUTE_ZONE_M == 50.0
        assert SCHOOL_RELATIVE_ZONE_M == 200.0

    def test_cafe_always_safe_with_coord(self):
        # 카페는 학교 옆이어도 safe (룰 적용 대상 X)
        r = rule_school_zone(
            "cafe",
            _MOCK_SCHOOL_LAT,
            _MOCK_SCHOOL_LON,
            schools=_SAMPLE_SCHOOLS,
        )
        assert r["type"] == "school_zone"
        assert r["level"] == "safe"

    def test_restaurant_always_safe_with_coord(self):
        r = rule_school_zone(
            "restaurant",
            _MOCK_SCHOOL_LAT,
            _MOCK_SCHOOL_LON,
            schools=_SAMPLE_SCHOOLS,
        )
        assert r["level"] == "safe"

    def test_unknown_biz_safe(self):
        r = rule_school_zone("미용실", 37.55, 126.90, schools=_SAMPLE_SCHOOLS)
        assert r["level"] == "safe"

    def test_pub_no_coord_caution(self):
        # 좌표 미입력 → 보수적 caution
        r = rule_school_zone("pub", None, None, schools=_SAMPLE_SCHOOLS)
        assert r["level"] == "caution"
        assert "좌표" in r["summary"] or "정화구역" in r["recommendation"]

    def test_pub_korean_no_coord_caution(self):
        r = rule_school_zone("주점", None, 126.9, schools=_SAMPLE_SCHOOLS)
        assert r["level"] == "caution"

    def test_pub_within_50m_danger(self):
        # 학교 좌표 그대로 (거리 0) → 절대정화구역 danger
        r = rule_school_zone(
            "pub",
            _MOCK_SCHOOL_LAT,
            _MOCK_SCHOOL_LON,
            schools=_SAMPLE_SCHOOLS,
        )
        assert r["level"] == "danger"
        assert "절대정화구역" in r["summary"] or "절대정화" in r["recommendation"]
        # 가장 가까운 학교 정보 노출
        assert "nearest_school" in r
        assert r["nearest_school"]["distance_m"] <= 50.0

    def test_pub_korean_within_50m_danger(self):
        r = rule_school_zone(
            "주점",
            _MOCK_SCHOOL_LAT,
            _MOCK_SCHOOL_LON,
            schools=_SAMPLE_SCHOOLS,
        )
        assert r["level"] == "danger"

    def test_pub_at_100m_relative_zone_danger(self):
        # 학교에서 약 100m 떨어진 위도 (50m < 100m < 200m) → 상대정화구역 danger
        lat = _offset_lat(100.0)
        r = rule_school_zone("pub", lat, _MOCK_SCHOOL_LON, schools=_SAMPLE_SCHOOLS)
        assert r["level"] == "danger"
        assert "상대정화구역" in r["summary"] or "심의" in r["recommendation"]
        assert r["nearest_school"]["distance_m"] > 50.0
        assert r["nearest_school"]["distance_m"] <= 200.0

    def test_pub_at_200m_boundary(self):
        # 정확히 200m → 상대정화구역 (≤ 200) → danger
        lat = _offset_lat(199.0)
        r = rule_school_zone("pub", lat, _MOCK_SCHOOL_LON, schools=_SAMPLE_SCHOOLS)
        assert r["level"] == "danger"

    def test_pub_far_safe(self):
        # 학교에서 500m 떨어진 위치 → safe
        lat = _offset_lat(500.0)
        r = rule_school_zone("pub", lat, _MOCK_SCHOOL_LON, schools=_SAMPLE_SCHOOLS)
        assert r["level"] == "safe"
        assert "200m" in r["summary"] or "정화구역" in r["recommendation"]

    def test_pub_empty_schools_safe(self):
        # 학교 리스트 빈 입력 → safe
        r = rule_school_zone("pub", 37.55, 126.90, schools=[])
        assert r["level"] == "safe"

    def test_pub_picks_closest_when_multiple(self):
        # 두 학교 중 더 가까운 (50m 이내) 쪽이 절대정화구역 트리거
        schools = [
            {"name": "먼학교", "school_type": "고등학교", "lat": _offset_lat(180.0), "lon": _MOCK_SCHOOL_LON},
            {"name": "가까운학교", "school_type": "초등학교", "lat": _MOCK_SCHOOL_LAT, "lon": _MOCK_SCHOOL_LON},
        ]
        r = rule_school_zone("pub", _MOCK_SCHOOL_LAT, _MOCK_SCHOOL_LON, schools=schools)
        assert r["level"] == "danger"
        assert r["nearest_school"]["name"] == "가까운학교"


# ---------------------------------------------------------------------------
# 헬퍼: _pyeong_to_m2
# ---------------------------------------------------------------------------


class TestPyeongToM2:
    def test_30_pyeong(self):
        assert _pyeong_to_m2(30.0) == pytest.approx(99.0, rel=1e-6)

    def test_negative_clamped(self):
        assert _pyeong_to_m2(-5.0) == 0.0

    def test_none_safe(self):
        assert _pyeong_to_m2(None) == 0.0


# ---------------------------------------------------------------------------
# 공통 schema 검증
# ---------------------------------------------------------------------------


class TestSchema:
    @pytest.mark.parametrize(
        "rule_call",
        [
            lambda: rule_food_hygiene("cafe"),
            lambda: rule_safety_regulation("cafe", 30.0),
            lambda: rule_fire_safety("cafe", 30.0),
            lambda: rule_accessibility("cafe", 30.0),
            lambda: rule_commercial_lease(),
            lambda: rule_labor(),
            lambda: rule_vat(),
            lambda: rule_sewage("restaurant"),
            lambda: rule_school_zone("cafe", 37.55, 126.90, schools=[]),
            lambda: rule_school_zone("pub", None, None, schools=[]),
            lambda: rule_school_zone("pub", 37.55, 126.90, schools=[]),
        ],
    )
    def test_schema_keys(self, rule_call):
        r = rule_call()
        assert {"type", "level", "summary", "recommendation", "articles"} <= set(r.keys())
        assert r["level"] in {"safe", "caution", "danger"}
        assert isinstance(r["articles"], list)
        assert isinstance(r["recommendation"], str) and len(r["recommendation"]) > 0
