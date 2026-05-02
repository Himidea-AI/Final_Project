"""법률 평가 Orchestrator E2E 테스트.

specialist는 LLM/RAG 의존성이 크므로 monkeypatch 로 stub 주입.
룰 8개는 실제 함수 그대로 실행.

검증 항목:
1. 12 항목 모두 반환
2. _RULE_ENGINE_ORDER 와 type set 일치
3. 한 specialist 실패 시 11 정상 + 1 fallback caution
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src.agents.legal import orchestrator, specialists  # noqa: E402
from src.agents.legal.orchestrator import (  # noqa: E402
    _RULE_ENGINE_ORDER,
    run_legal_evaluation,
)


# ---------------------------------------------------------------------------
# Stub specialist (LLM/RAG 회피)
# ---------------------------------------------------------------------------


def _stub_result(type_name: str, level: str = "caution") -> dict:
    return {
        "type": type_name,
        "level": level,
        "summary": f"[stub] {type_name} 평가",
        "recommendation": f"[stub] {type_name} 권고사항",
        "articles": [],
    }


async def _stub_franchise(brand, business_type, district, ftc_data):
    return _stub_result("franchise_law", "caution")


async def _stub_fair_trade(brand, business_type, district):
    return _stub_result("fair_trade_law", "caution")


async def _stub_building(business_type, district):
    return _stub_result("building_law", "caution")


async def _stub_privacy(brand, business_type, ftc_data):
    return _stub_result("privacy_law", "caution")


@pytest.fixture
def patch_specialists(monkeypatch):
    """4 specialist 모두 stub 으로 교체 — LLM/Redis 호출 없음."""
    monkeypatch.setattr(specialists, "specialist_franchise_law", _stub_franchise)
    monkeypatch.setattr(specialists, "specialist_fair_trade_law", _stub_fair_trade)
    monkeypatch.setattr(specialists, "specialist_building_law", _stub_building)
    monkeypatch.setattr(specialists, "specialist_privacy_law", _stub_privacy)


# ---------------------------------------------------------------------------
# 정상 경로 — 12 항목
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_13_items(patch_specialists):
    risks = await run_legal_evaluation(
        brand="스타벅스",
        business_type="cafe",
        district="공덕동",
        store_area_pyeong=20.0,
        ftc_data=None,
    )
    assert len(risks) == 13
    types = [r["type"] for r in risks]
    # 순서 확인
    assert types == _RULE_ENGINE_ORDER


@pytest.mark.asyncio
async def test_types_unique_and_complete(patch_specialists):
    risks = await run_legal_evaluation(
        brand="이디야",
        business_type="cafe",
        district="서교동",
        store_area_pyeong=15.0,
        ftc_data=None,
    )
    types = {r["type"] for r in risks}
    assert types == set(_RULE_ENGINE_ORDER)
    assert len(types) == 13
    assert "school_zone" in types


@pytest.mark.asyncio
async def test_all_levels_valid(patch_specialists):
    risks = await run_legal_evaluation(
        brand="A",
        business_type="restaurant",
        district="합정동",
        store_area_pyeong=15.0,
        ftc_data=None,
    )
    for r in risks:
        assert r["level"] in {"safe", "caution", "danger"}
        assert "summary" in r
        assert "recommendation" in r
        assert "articles" in r


# ---------------------------------------------------------------------------
# 실패 격리 — 한 specialist 실패 시 나머지 정상
# ---------------------------------------------------------------------------


async def _raising_specialist(*args, **kwargs):
    raise RuntimeError("simulated LLM failure")


@pytest.mark.asyncio
async def test_specialist_failure_isolated(monkeypatch):
    """franchise_law specialist 가 raise 해도 나머지 11 정상 + 1 fallback caution."""
    monkeypatch.setattr(specialists, "specialist_franchise_law", _raising_specialist)
    monkeypatch.setattr(specialists, "specialist_fair_trade_law", _stub_fair_trade)
    monkeypatch.setattr(specialists, "specialist_building_law", _stub_building)
    monkeypatch.setattr(specialists, "specialist_privacy_law", _stub_privacy)

    risks = await run_legal_evaluation(
        brand="실패브랜드",
        business_type="cafe",
        district="공덕동",
        store_area_pyeong=20.0,
        ftc_data=None,
    )
    assert len(risks) == 13
    franchise = next(r for r in risks if r["type"] == "franchise_law")
    assert franchise["level"] == "caution"
    assert franchise.get("is_fallback") is True
    # 나머지 12 항목 중 룰 9 개는 정상 (fallback 아님)
    others = [r for r in risks if r["type"] != "franchise_law"]
    rules_only = [r for r in others if r["type"] in {
        "food_hygiene", "safety_regulation", "fire_safety_law", "accessibility_law",
        "school_zone", "commercial_lease_law", "labor_law", "vat_law", "sewage_law",
    }]
    for r in rules_only:
        assert not r.get("is_fallback"), f"{r['type']} 이 예기치 않게 fallback 처리됨"


@pytest.mark.asyncio
async def test_multiple_specialist_failures(monkeypatch):
    """여러 specialist 가 실패해도 12 항목 보장."""
    monkeypatch.setattr(specialists, "specialist_franchise_law", _raising_specialist)
    monkeypatch.setattr(specialists, "specialist_fair_trade_law", _raising_specialist)
    monkeypatch.setattr(specialists, "specialist_building_law", _stub_building)
    monkeypatch.setattr(specialists, "specialist_privacy_law", _stub_privacy)

    risks = await run_legal_evaluation(
        brand="x",
        business_type="cafe",
        district="망원동",
        store_area_pyeong=10.0,
        ftc_data=None,
    )
    assert len(risks) == 13
    types = {r["type"] for r in risks}
    assert "franchise_law" in types
    assert "fair_trade_law" in types


# ---------------------------------------------------------------------------
# 룰 결과 검증 — 면적이 룰에 정확히 반영
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_area_propagates_to_rules(patch_specialists):
    """31평이면 safety_regulation 이 danger 로 나와야 함 (룰 직접 호출 검증)."""
    risks = await run_legal_evaluation(
        brand="x",
        business_type="cafe",
        district="합정동",
        store_area_pyeong=31.0,
        ftc_data=None,
    )
    safety = next(r for r in risks if r["type"] == "safety_regulation")
    assert safety["level"] == "danger"
    fire = next(r for r in risks if r["type"] == "fire_safety_law")
    assert fire["level"] == "danger"


@pytest.mark.asyncio
async def test_small_area_safe_for_safety(patch_specialists):
    risks = await run_legal_evaluation(
        brand="x",
        business_type="cafe",
        district="합정동",
        store_area_pyeong=15.0,
        ftc_data=None,
    )
    safety = next(r for r in risks if r["type"] == "safety_regulation")
    assert safety["level"] == "safe"


# ---------------------------------------------------------------------------
# school_zone — orchestrator 좌표 전달 경로 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_school_zone_safe_for_cafe(patch_specialists):
    """카페는 좌표와 무관하게 학교 거리 룰 적용 X (safe)."""
    risks = await run_legal_evaluation(
        brand="스타벅스",
        business_type="cafe",
        district="서교동",
        store_area_pyeong=15.0,
        ftc_data=None,
        lat=37.5532,
        lon=126.9217,
    )
    sz = next(r for r in risks if r["type"] == "school_zone")
    assert sz["level"] == "safe"


@pytest.mark.asyncio
async def test_school_zone_caution_for_pub_no_coord(patch_specialists):
    """주점 좌표 미입력 시 caution."""
    risks = await run_legal_evaluation(
        brand="펍",
        business_type="pub",
        district="서교동",
        store_area_pyeong=15.0,
        ftc_data=None,
    )
    sz = next(r for r in risks if r["type"] == "school_zone")
    assert sz["level"] == "caution"


# ---------------------------------------------------------------------------
# _to_risk_dict 단위 동작 검증
# ---------------------------------------------------------------------------


def test_to_risk_dict_handles_exception():
    out = orchestrator._to_risk_dict(RuntimeError("boom"), 0)
    assert out["type"] == _RULE_ENGINE_ORDER[0]
    assert out["level"] == "caution"
    assert out["is_fallback"] is True


def test_to_risk_dict_corrects_type():
    """specialist 가 잘못된 type 으로 반환해도 orchestrator 가 보정."""
    franchise_idx = _RULE_ENGINE_ORDER.index("franchise_law")
    out = orchestrator._to_risk_dict(
        {"type": "wrong_type", "level": "safe", "summary": "x", "recommendation": "y", "articles": []},
        franchise_idx,
    )
    assert out["type"] == "franchise_law"


def test_to_risk_dict_handles_non_dict():
    out = orchestrator._to_risk_dict("not a dict", 0)
    assert out["level"] == "caution"
    assert out.get("is_fallback") is True
