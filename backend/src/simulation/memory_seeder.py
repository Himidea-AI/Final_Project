"""Memory Seeder — Cold Start 완화용 가상 visit_history 주입.

목적:
    ABM 시작 시점에 모든 agent.visit_history 가 비어있으면 Layer 2 기억
    (learned_prefs, habit_store, recall_satisfaction) 이 1~2일 동안 작동하지 않아
    초반 매장 선택이 편향됨. 14일치 가상 방문을 사전에 주입해 Cold Start 완화.

설계:
    1. agent.profile 의 카테고리 선호 (pref_cafe/restaurant/pub/cvs) 따라 카테고리 가중치
    2. agent.home_dong 매장 우선 (현실 거주민 행동 근사)
    3. 시간대는 식사·휴식 hour 분포 (8/12/18/20/22)
    4. 만족도 0.5~0.8 범위 (현실 baseline, 너무 높지 않게)
    5. record_visit() 가 자동으로 learned_prefs / habit_store 업데이트

사용:
    from .memory_seeder import seed_all_agents
    seed_all_agents(agents, world, days_of_history=14, verbose=True)
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agents import Agent
    from .world import World


# 시간대 분포 — 식사/휴식 hour 가중치
_HOUR_WEIGHTS: dict[int, float] = {
    8: 0.10,  # 아침 (카페/편의점)
    12: 0.25,  # 점심 (음식점)
    13: 0.10,
    18: 0.20,  # 저녁 (음식점)
    19: 0.15,
    20: 0.05,
    22: 0.10,  # 야간 (주점/카페)
    23: 0.05,
}

# 카테고리별 baseline 만족도 분포 (현실 평균 ~0.65)
_CAT_BASE_SATISFACTION = {
    "카페": (0.55, 0.80),
    "음식점": (0.50, 0.78),
    "주점": (0.50, 0.75),
    "편의점": (0.45, 0.70),
    "기타": (0.50, 0.75),
}


def _pick_category(profile, rng: random.Random) -> str:
    """agent.profile 선호도 기반 카테고리 가중 샘플."""
    if profile is None:
        # profile 없으면 균등 + 음식점 약간 boost
        return rng.choices(
            ["카페", "음식점", "주점", "편의점"],
            weights=[0.30, 0.40, 0.15, 0.15],
        )[0]
    weights = [
        max(0.05, profile.pref_cafe),
        max(0.05, profile.pref_restaurant),
        max(0.05, profile.pref_pub),
        max(0.05, profile.pref_convenience),
    ]
    return rng.choices(["카페", "음식점", "주점", "편의점"], weights=weights)[0]


def _pick_hour(rng: random.Random) -> int:
    """시간대 가중 샘플."""
    hours = list(_HOUR_WEIGHTS.keys())
    weights = list(_HOUR_WEIGHTS.values())
    return rng.choices(hours, weights=weights)[0]


def _sample_satisfaction(category: str, rng: random.Random) -> float:
    lo, hi = _CAT_BASE_SATISFACTION.get(category, (0.50, 0.75))
    return round(rng.uniform(lo, hi), 3)


def seed_one_agent(
    agent: "Agent",
    world: "World",
    days_of_history: int,
    visits_per_day: tuple[int, int],
    rng: random.Random,
) -> int:
    """한 agent 에 가상 visit 주입. 반환: 주입된 visit 수."""
    injected = 0
    home = agent.home_dong
    available_dongs = [home] if home in world.dongs else list(world.dongs[:1])

    for day_back in range(1, days_of_history + 1):
        n_visits = rng.randint(*visits_per_day)
        for _ in range(n_visits):
            cat = _pick_category(getattr(agent, "profile", None), rng)
            dong = rng.choice(available_dongs)
            stores = world.stores_in_dong(dong, category=cat)
            if not stores:
                # 카테고리 없으면 동 전체에서 랜덤
                stores = world.stores_in_dong(dong)
            if not stores:
                continue
            store = rng.choice(stores)
            hour = _pick_hour(rng)
            sat = _sample_satisfaction(cat, rng)
            try:
                agent.record_visit(
                    day=-day_back,  # 음수 = 과거
                    hour=hour,
                    store_id=store.store_id,
                    category=store.category,  # store 의 실제 카테고리
                    satisfaction=sat,
                )
                injected += 1
            except Exception:
                # record_visit 실패 시 스킵 (agent.visit_history 자체 없을 가능성 등)
                continue
    return injected


def seed_all_agents(
    agents: list["Agent"],
    world: "World",
    days_of_history: int = 14,
    visits_per_day: tuple[int, int] = (0, 2),
    seed: int = 42,
    verbose: bool = False,
) -> dict:
    """전체 agent 에 가상 visit_history 주입.

    Args:
        agents: ABM 에이전트 리스트
        world: World 인스턴스 (stores_by_dong 사용)
        days_of_history: 과거 며칠치 주입 (기본 14)
        visits_per_day: (min, max) 일평균 방문 (기본 0~2회)
        seed: 재현성용 RNG seed
        verbose: 로그 출력 여부

    Returns:
        {agents_seeded, total_visits, avg_visits_per_agent}
    """
    rng = random.Random(seed)
    total = 0
    seeded = 0
    for agent in agents:
        n = seed_one_agent(agent, world, days_of_history, visits_per_day, rng)
        if n > 0:
            seeded += 1
            total += n

    summary = {
        "agents_seeded": seeded,
        "agents_total": len(agents),
        "total_visits": total,
        "avg_visits_per_agent": round(total / max(seeded, 1), 2),
        "days_of_history": days_of_history,
    }
    if verbose:
        print(
            f"  [memory_seeder] {seeded}/{len(agents)} agents 에 "
            f"가상 visit {total}건 주입 (평균 {summary['avg_visits_per_agent']:.1f}/agent, "
            f"{days_of_history}일치)"
        )
    return summary
