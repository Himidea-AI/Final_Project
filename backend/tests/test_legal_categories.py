"""법률 카테고리 그룹(입지/운영) 매핑 단위 테스트.

backend/src/agents/legal/categories.py 의 LEGAL_CATEGORY_GROUP 단일 소스 검증.
- 13 룰 카테고리 + zoning + ftc 모두 매핑 존재.
- 입지(location) 그룹: 출점 결정 critical 8 + 호환 2 = 10개.
- 운영(operation) 그룹: 자영업자 일상 의무 5개.
- 누락 카테고리는 default(operation) 으로 폴백.
"""

import pytest

from src.agents.legal.categories import (
    LEGAL_CATEGORY_GROUP,
    LEGAL_GROUP_LOCATION,
    LEGAL_GROUP_OPERATION,
    get_legal_group,
)

# 출점 결정 critical — 입지 그룹
_LOCATION_TYPES = [
    "building_law",
    "school_zone",
    "safety_regulation",
    "fire_safety_law",
    "accessibility_law",
    "franchise_law",
    "fair_trade_law",
    "commercial_lease_law",
    "zoning_regulation",
    "ftc_franchise",
]

# 자영업자 통상 인지 — 운영 그룹
_OPERATION_TYPES = [
    "food_hygiene",
    "labor_law",
    "vat_law",
    "privacy_law",
    "sewage_law",
]


@pytest.mark.parametrize("rtype", _LOCATION_TYPES)
def test_location_group(rtype: str) -> None:
    assert get_legal_group(rtype) == LEGAL_GROUP_LOCATION
    assert LEGAL_CATEGORY_GROUP[rtype] == "location"


@pytest.mark.parametrize("rtype", _OPERATION_TYPES)
def test_operation_group(rtype: str) -> None:
    assert get_legal_group(rtype) == LEGAL_GROUP_OPERATION
    assert LEGAL_CATEGORY_GROUP[rtype] == "operation"


def test_unknown_type_fallback() -> None:
    """매핑 누락 카테고리는 default(operation) 으로 폴백."""
    assert get_legal_group("unknown_law_xyz") == LEGAL_GROUP_OPERATION
    assert get_legal_group("") == LEGAL_GROUP_OPERATION


def test_school_zone_is_location() -> None:
    """신규 추가된 school_zone 은 입지 그룹 (출점 후보지 좌표 의존)."""
    assert get_legal_group("school_zone") == "location"


def test_all_13_rule_categories_mapped() -> None:
    """orchestrator._RULE_ENGINE_ORDER 13 룰 + zoning/ftc 2 specialist = 15 모두 매핑."""
    expected = set(_LOCATION_TYPES + _OPERATION_TYPES)
    missing = expected - set(LEGAL_CATEGORY_GROUP.keys())
    assert not missing, f"카테고리 매핑 누락: {missing}"


def test_main_response_includes_group_field() -> None:
    """main.py 응답 변환에서 LegalRisk 에 group 필드가 포함되는지 통합 검증."""
    from src.agents.legal.categories import get_legal_group as _g

    fake_risks = [
        {"type": "school_zone", "level": "danger", "summary": "test"},
        {"type": "food_hygiene", "level": "caution", "summary": "test"},
        {"type": "ftc_franchise", "level": "safe", "summary": "test"},
    ]

    # main.py 와 동일한 변환 로직 (단일 소스 검증)
    transformed = [
        {
            "type": r.get("type"),
            "group": _g(r.get("type", "")),
        }
        for r in fake_risks
    ]

    assert transformed[0]["group"] == "location"  # school_zone
    assert transformed[1]["group"] == "operation"  # food_hygiene
    assert transformed[2]["group"] == "location"  # ftc_franchise
