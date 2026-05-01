"""법률 평가 Orchestrator — 8 룰 + 4 specialist 병렬 실행.

진입점: ``run_legal_evaluation`` — ``asyncio.gather`` 로 12 개 평가를
병렬 실행하고 ``return_exceptions=True`` 로 한 항목 실패가 전체에
영향 주지 않도록 격리.

반환 순서는 ``_RULE_ENGINE_ORDER`` 와 1:1 대응 (12 dict).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.agents.legal import rules, specialists

logger = logging.getLogger(__name__)


# tasks 리스트와 1:1 대응 — 예외 처리 시 type 식별에 사용
_RULE_ENGINE_ORDER: list[str] = [
    "food_hygiene",
    "safety_regulation",
    "fire_safety_law",
    "accessibility_law",
    "commercial_lease_law",
    "labor_law",
    "vat_law",
    "sewage_law",
    "franchise_law",
    "fair_trade_law",
    "building_law",
    "privacy_law",
]


def _fallback_for_type(type_name: str, exc: BaseException) -> dict:
    """예외 발생 시 caution 기본값 dict."""
    logger.warning(f"[legal orchestrator] {type_name} 평가 실패: {exc}")
    return {
        "type": type_name,
        "level": "caution",
        "summary": f"{type_name} 평가 중 오류 발생 — 수동 검토 필요.",
        "recommendation": (
            f"[근거: {type_name}]\n"
            "• 자동 평가 실패 — 전문가 상담 또는 재시도 권장\n"
            f"❌ 오류: {type(exc).__name__}: {str(exc)[:100]}"
        ),
        "articles": [],
        "is_fallback": True,
    }


def _to_risk_dict(result: Any, idx: int) -> dict:
    """gather 결과 1 개를 dict 로 정규화. 예외/형식 오류는 fallback."""
    type_name = _RULE_ENGINE_ORDER[idx] if 0 <= idx < len(_RULE_ENGINE_ORDER) else "unknown"
    if isinstance(result, BaseException):
        return _fallback_for_type(type_name, result)
    if not isinstance(result, dict):
        return _fallback_for_type(
            type_name, ValueError(f"예상치 못한 반환 타입: {type(result).__name__}")
        )
    # type 강제 보정 (specialist LLM 이 다른 type 으로 반환할 위험)
    if result.get("type") != type_name:
        result = {**result, "type": type_name}
    return result


async def run_legal_evaluation(
    brand: str,
    business_type: str,
    district: str,
    store_area_pyeong: float,
    ftc_data: dict | None,
) -> list[dict]:
    """8 룰 + 4 specialist 병렬 평가 → 12 dict 반환.

    Args:
        brand: 브랜드명 (specialist 입력).
        business_type: 업종 (cafe/restaurant/convenience 또는 한글).
        district: 행정동 (마포 16 동 또는 기타).
        store_area_pyeong: 평수 (default 15.0 호출자가 보장).
        ftc_data: ``check_ftc_franchise`` 결과 dict (또는 ``None``).

    Returns:
        ``len == 12`` 의 dict 리스트. 각 dict 는 ``type, level, summary, recommendation,
        articles`` 필드를 가지며 ``_RULE_ENGINE_ORDER`` 순서로 정렬됨.
    """
    # 룰 8 개 — 동기 함수이므로 ``asyncio.to_thread`` 로 병렬화 (사실상 즉시 반환).
    tasks = [
        # --- 8 룰 ---
        asyncio.to_thread(rules.rule_food_hygiene, business_type),
        asyncio.to_thread(rules.rule_safety_regulation, business_type, store_area_pyeong),
        asyncio.to_thread(rules.rule_fire_safety, business_type, store_area_pyeong),
        asyncio.to_thread(rules.rule_accessibility, business_type, store_area_pyeong),
        asyncio.to_thread(rules.rule_commercial_lease),
        asyncio.to_thread(rules.rule_labor),
        asyncio.to_thread(rules.rule_vat),
        asyncio.to_thread(rules.rule_sewage, business_type),
        # --- 4 specialist ---
        specialists.specialist_franchise_law(brand, business_type, district, ftc_data),
        specialists.specialist_fair_trade_law(brand, business_type, district),
        specialists.specialist_building_law(business_type, district),
        specialists.specialist_privacy_law(brand, business_type, ftc_data),
    ]
    assert len(tasks) == len(_RULE_ENGINE_ORDER), (
        f"tasks/_RULE_ENGINE_ORDER 길이 불일치: {len(tasks)} vs {len(_RULE_ENGINE_ORDER)}"
    )

    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [_to_risk_dict(r, idx) for idx, r in enumerate(results)]
