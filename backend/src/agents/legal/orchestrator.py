"""법률 평가 Orchestrator — 9 룰 + 4 specialist 병렬 실행.

진입점: ``run_legal_evaluation`` — ``asyncio.gather`` 로 13 개 평가를
병렬 실행하고 ``return_exceptions=True`` 로 한 항목 실패가 전체에
영향 주지 않도록 격리.

반환 순서는 ``_RULE_ENGINE_ORDER`` 와 1:1 대응 (13 dict).

2026-05-02: school_zone (학교환경위생정화구역) 룰 추가 — 주점 출점 후보지
좌표 기반 50m/200m 거리 평가. 좌표 미입력 시 caution fallback.
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
    "school_zone",
    "commercial_lease_law",
    "labor_law",
    "vat_law",
    "sewage_law",
    "franchise_law",
    "fair_trade_law",
    "building_law",
    "privacy_law",
]


def _fallback_for_type(type_name: str, exc: Exception) -> dict:
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
    """gather 결과 1 개를 dict 로 정규화. 예외/형식 오류는 fallback.

    SystemExit/KeyboardInterrupt 등 BaseException 은 의도적 종료라 catch 하지 않음.
    """
    type_name = _RULE_ENGINE_ORDER[idx] if 0 <= idx < len(_RULE_ENGINE_ORDER) else "unknown"
    if isinstance(result, Exception):
        return _fallback_for_type(type_name, result)
    if not isinstance(result, dict):
        return _fallback_for_type(type_name, ValueError(f"예상치 못한 반환 타입: {type(result).__name__}"))
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
    lat: float | None = None,
    lon: float | None = None,
    territory_radius_m: int | None = None,
) -> list[dict]:
    """9 룰 + 4 specialist 병렬 평가 → 13 dict 반환.

    Args:
        brand: 브랜드명 (specialist 입력).
        business_type: 업종 (cafe/restaurant/pub 또는 한글; 편의점 등 운영 카테고리도 입력 가능).
        district: 행정동 (마포 16 동 또는 기타).
        store_area_pyeong: 평수 (default 15.0 호출자가 보장).
        ftc_data: ``check_ftc_franchise`` 결과 dict (또는 ``None``).
        lat: 출점 후보지 위도 (학교환경위생정화구역 거리 계산용; 주점만 트리거).
        lon: 출점 후보지 경도 (lat 와 함께 입력될 때만 유효).

    Returns:
        ``len == 13`` 의 dict 리스트. 각 dict 는 ``type, level, summary, recommendation,
        articles`` 필드를 가지며 ``_RULE_ENGINE_ORDER`` 순서로 정렬됨.
    """
    # 룰 9 개 — 동기 pure-Python (~ms). asyncio.to_thread executor 점유 회피 위해
    # 직접 호출 후 dict 로 수집 — 이벤트루프 블로킹 위험 없음.
    rule_results: list[dict] = []
    for fn, args in (
        (rules.rule_food_hygiene, (business_type,)),
        (rules.rule_safety_regulation, (business_type, store_area_pyeong)),
        (rules.rule_fire_safety, (business_type, store_area_pyeong)),
        (rules.rule_accessibility, (business_type, store_area_pyeong)),
        (rules.rule_school_zone, (business_type, lat, lon)),
        (rules.rule_commercial_lease, ()),
        (rules.rule_labor, ()),
        (rules.rule_vat, ()),
        (rules.rule_sewage, (business_type,)),
    ):
        try:
            rule_results.append(fn(*args))
        except Exception as e:
            type_name = _RULE_ENGINE_ORDER[len(rule_results)]
            rule_results.append(_fallback_for_type(type_name, e))

    # specialist 4 개 — RAG + LLM (I/O bound) 병렬 실행
    # franchise_law 영업지역 분석 = 공실 스팟 좌표 (lat/lon) 기준 500m 반경.
    # 좌표 None 이면 specialist 가 행정동 centroid 폴백 사용.
    specialist_tasks = [
        specialists.specialist_franchise_law(brand, business_type, district, ftc_data, lat, lon, territory_radius_m),
        specialists.specialist_fair_trade_law(brand, business_type, district),
        specialists.specialist_building_law(business_type, district),
        specialists.specialist_privacy_law(brand, business_type, ftc_data),
    ]

    expected_total = len(rule_results) + len(specialist_tasks)
    if expected_total != len(_RULE_ENGINE_ORDER):
        raise ValueError(
            f"rule + specialist 합계와 _RULE_ENGINE_ORDER 길이 불일치: {expected_total} vs {len(_RULE_ENGINE_ORDER)}"
        )

    specialist_results = await asyncio.gather(*specialist_tasks, return_exceptions=True)

    return rule_results + [_to_risk_dict(r, idx + len(rule_results)) for idx, r in enumerate(specialist_results)]
