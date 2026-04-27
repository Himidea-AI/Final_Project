"""공실 → ABM 가상 매장 주입 + 시뮬 결과 집계.

목적:
    LangGraph district_ranking 노드가 추출한 공실 좌표(`vacancy_spots`)를
    ABM World 에 가상 Store 로 주입하여 1000 agent 시뮬에 노출.
    시뮬 종료 후 가상 매장의 visits/revenue 를 집계해 "이 공실에 X 업종을
    차렸을 때의 예상 성과" 를 정량화.

기존 자산:
    - runner.py 의 scenario.new_store 는 단일 매장 주입만 지원
    - 본 모듈은 배치 주입 + 결과 집계 API 를 제공 (LangGraph 다중 추천 대응)

사용 흐름:
    1. district_ranking 노드 → state["vacancy_spots"] = [{dong, lat, lon, ...}, ...]
    2. inject_vacancies_batch(world, spots, category="카페") → vacancy_id 리스트
    3. run_simulation(world, ...) — 기존 score_store 가 자동으로 가상 매장 평가
    4. evaluate_vacancies_batch(world, vacancy_ids) → 매장별 visits/revenue
"""

from __future__ import annotations

from typing import Any

from .world import Store, World


VACANCY_ID_PREFIX = "vacancy"
ALLOWED_CATEGORIES = ("음식점", "카페", "주점", "편의점", "기타")
DEFAULT_SEATS = 30
DEFAULT_RATING = 4.0
DEFAULT_PRICE_LEVEL = 2


class VacancyInjectionError(ValueError):
    """공실 주입 실패 (좌표 누락, 동 불일치 등)."""


def inject_vacancy_as_store(
    world: World,
    vacancy_spot: dict[str, Any],
    category: str,
    name: str | None = None,
    seats: int = DEFAULT_SEATS,
    rating: float = DEFAULT_RATING,
    price_level: int = DEFAULT_PRICE_LEVEL,
    popularity_boost: float = 1.0,
) -> str:
    """공실 1개 → 가상 Store 로 주입. world.add_store() 만 하면 시뮬 자동 적용.

    Args:
        world: ABM World 인스턴스
        vacancy_spot: {"dong": str, "lat": float, "lon": float, ...} (district_ranking._load_vacancy_spots 출력)
        category: 가상으로 차릴 업종 (음식점/카페/주점/편의점/기타)
        name: 매장 이름 (생략 시 "VACANCY_{idx}_{dong}")
        seats: 좌석 수 (혼잡도 계산에 영향)
        rating: 평점 (신규라 중립 4.0 권장)
        price_level: 가격대 1~3 (저~고)
        popularity_boost: 신규 매장 인지도 (1.0 = 중립, > 1.0 = 마케팅 효과)

    Returns:
        주입된 매장의 store_id (string, 기존 매장과 충돌 없음)

    Raises:
        VacancyInjectionError: 좌표 누락, 동 매칭 실패, 카테고리 무효 시
    """
    dong = vacancy_spot.get("dong") or vacancy_spot.get("district")
    lat = vacancy_spot.get("lat")
    lon = vacancy_spot.get("lon")

    if not dong:
        raise VacancyInjectionError("vacancy_spot 에 'dong' 또는 'district' 키 필요")
    if dong not in world.dongs:
        raise VacancyInjectionError(f"'{dong}' 가 world.dongs 에 없음 (등록된 동: {len(world.dongs)}개)")
    if lat is None or lon is None:
        raise VacancyInjectionError(f"vacancy_spot lat/lon 누락 (dong={dong})")
    if category not in ALLOWED_CATEGORIES:
        raise VacancyInjectionError(f"category '{category}' 는 허용 카테고리 {ALLOWED_CATEGORIES} 외")

    # 기존 vacancy 매장 수 기반 idx — 같은 동에서 충돌 방지
    existing_count = sum(1 for sid in world.stores if isinstance(sid, str) and sid.startswith(VACANCY_ID_PREFIX))
    vid = f"{VACANCY_ID_PREFIX}_{existing_count}_{dong}"

    store = Store(
        store_id=vid,  # type: ignore[arg-type]  # 기존 runner.py new_store 패턴과 동일하게 string 허용
        name=name or f"VACANCY_{existing_count}_{dong}",
        dong=dong,
        category=category,
        seats=seats,
        rating=rating,
        price_level=price_level,
        lat=float(lat),
        lon=float(lon),
        is_open_now=True,
        popularity_boost=popularity_boost,
    )
    world.add_store(store)
    return vid


def inject_vacancies_batch(
    world: World,
    vacancy_spots: list[dict[str, Any]],
    category: str,
    skip_invalid: bool = True,
    **store_overrides: Any,
) -> list[str]:
    """공실 여러 개 → 가상 매장 일괄 주입 (모두 같은 카테고리).

    Args:
        world: ABM World
        vacancy_spots: district_ranking 노드 출력 좌표 리스트
        category: 일괄 적용 카테고리
        skip_invalid: True 면 실패한 spot 은 스킵 (로그만), False 면 즉시 raise
        **store_overrides: seats/rating/price_level/popularity_boost 일괄 적용

    Returns:
        성공적으로 주입된 vacancy_id 리스트 (입력 순서, 실패는 제외)
    """
    injected: list[str] = []
    for i, spot in enumerate(vacancy_spots):
        try:
            vid = inject_vacancy_as_store(world, spot, category, **store_overrides)
            injected.append(vid)
        except VacancyInjectionError as e:
            if not skip_invalid:
                raise
            print(f"[vacancy_inject] spot {i} 스킵: {e}")
    return injected


def evaluate_vacancy_store(
    world: World,
    vacancy_id: str,
    days_simulated: int = 1,
) -> dict[str, Any]:
    """가상 매장 1개 시뮬 결과 집계.

    주의: world.stores[vid].visits_today / revenue_today 는 reset_daily() 호출 시
    초기화됨. 다일 시뮬에서는 매일 누적값을 별도로 보존하거나 마지막 날만 집계.

    Args:
        world: 시뮬 종료 후의 World
        vacancy_id: inject_vacancy_as_store 가 반환한 ID
        days_simulated: 시뮬 일수 (per-day 평균 계산용)

    Returns:
        {dong, category, lat, lon, visits, revenue, occupancy, visits_per_day, revenue_per_day}
    """
    if vacancy_id not in world.stores:
        raise VacancyInjectionError(f"vacancy_id '{vacancy_id}' 가 world.stores 에 없음")
    s = world.stores[vacancy_id]
    days = max(days_simulated, 1)
    return {
        "vacancy_id": vacancy_id,
        "dong": s.dong,
        "category": s.category,
        "lat": s.lat,
        "lon": s.lon,
        "visits": s.visits_today,
        "revenue": s.revenue_today,
        "occupancy": s.occupancy,
        "visits_per_day": s.visits_today / days,
        "revenue_per_day": s.revenue_today / days,
    }


def evaluate_vacancies_batch(
    world: World,
    vacancy_ids: list[str],
    days_simulated: int = 1,
) -> list[dict[str, Any]]:
    """여러 가상 매장 결과 일괄 집계 (visits 내림차순)."""
    results = [evaluate_vacancy_store(world, vid, days_simulated) for vid in vacancy_ids]
    results.sort(key=lambda r: r["visits"], reverse=True)
    return results
