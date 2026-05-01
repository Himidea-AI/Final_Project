"""법률 룰 엔진 unit tests — 8 함수 × 면적 경계/업종 케이스.

면적 경계:
- safety_regulation: 30평(99㎡) → safe, 31평(102.3㎡) → danger
- accessibility_law: 90평(297㎡) → safe, 91평(300.3㎡) → danger
- fire_safety_law: 30평 → caution, 31평 → danger

업종:
- food_hygiene: 카페/cafe → danger, 음식점/restaurant → danger, 편의점/convenience → caution
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
    rule_accessibility,
    rule_commercial_lease,
    rule_fire_safety,
    rule_food_hygiene,
    rule_labor,
    rule_safety_regulation,
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

    def test_convenience_caution(self):
        r = rule_food_hygiene("convenience")
        assert r["level"] == "caution"

    def test_korean_cafe_equivalent_to_english(self):
        ko = rule_food_hygiene("카페")
        en = rule_food_hygiene("cafe")
        assert ko["level"] == en["level"] == "danger"

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

    def test_convenience_always_safe(self):
        r = rule_safety_regulation("convenience", 200.0)
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

    def test_convenience_large_safe(self):
        # 편의점은 300㎡ 이상이어도 의무 대상 아님 (식품접객업 아님)
        r = rule_accessibility("convenience", 200.0)
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

    def test_cafe_safe(self):
        r = rule_sewage("cafe")
        assert r["level"] == "safe"

    def test_convenience_safe(self):
        r = rule_sewage("convenience")
        assert r["level"] == "safe"

    def test_korean_restaurant(self):
        r = rule_sewage("음식점")
        assert r["level"] == "caution"


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
        ],
    )
    def test_schema_keys(self, rule_call):
        r = rule_call()
        assert {"type", "level", "summary", "recommendation", "articles"} <= set(r.keys())
        assert r["level"] in {"safe", "caution", "danger"}
        assert isinstance(r["articles"], list)
        assert isinstance(r["recommendation"], str) and len(r["recommendation"]) > 0
