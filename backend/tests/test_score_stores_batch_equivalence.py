"""score_stores_batch == [score_store(s) for s in stores] 회귀 검증.

A 단계 (numpy/precompute batch) 진입 시 score_store 의 모든 path 가 batch 로
재현되는지 확인. random store 1000 케이스로 abs diff < 1e-9 보장.

수치가 1e-9 보다 큰 차이 나면 batch 로직 회귀 발생 — visits_log/매출 분포에
직접 영향. 본 테스트는 ABM run 자체는 돌리지 않고 score 만 격리 비교.
"""

from __future__ import annotations

import math
import random

import pytest

from src.simulation.agents import Agent, Role, Tier
from src.simulation.policy_executor import score_store, score_stores_batch
from src.simulation.policy_generator import PersonaPolicy
from src.simulation.world import Store, World


def _make_world(seed: int = 42, n_stores: int = 200) -> World:
    rng = random.Random(seed)
    cats = ["카페", "음식점", "편의점", "주점", "기타"]
    weights = [0.30, 0.40, 0.10, 0.15, 0.05]
    world = World()
    world.dongs = ["서교동", "합정동", "망원동", "서강동", "공덕동", "성산1동"]
    world.current_hour = 14
    world.weekday = 3  # 목요일
    world.weather = "맑음"
    world.month = 5
    world.is_weekend = False
    world.is_holiday = False
    world.is_payday = False

    sid = 1
    for dong in world.dongs:
        for _ in range(n_stores // len(world.dongs)):
            cat = rng.choices(cats, weights=weights)[0]
            world.add_store(
                Store(
                    store_id=sid,
                    name=f"{dong}_{cat}_{sid}",
                    dong=dong,
                    category=cat,
                    seats=rng.randint(8, 80),
                    rating=round(rng.uniform(3.0, 5.0), 1),
                    price_level=rng.randint(1, 3),
                    visits_today=rng.randint(0, 30),
                    popularity_boost=round(rng.uniform(0.5, 1.5), 2),
                    lat=37.555 + rng.uniform(-0.02, 0.02),
                    lon=126.92 + rng.uniform(-0.04, 0.04),
                )
            )
            sid += 1

    # 실측 boost dict 일부 채우기
    for d in world.dongs:
        for h in range(24):
            world.adstrd_flpop_boost[(d, h, world.weekday)] = round(rng.uniform(0.7, 1.5), 2)
            for g in ("20s", "30s", "40s", "50s", "60s"):
                world.time_age_boost[(g, d, h, world.weekday)] = round(rng.uniform(0.5, 1.8), 2)
        world.ofs_dong_score[d] = round(rng.uniform(20.0, 95.0), 2)

    return world


def _make_agent(seed: int = 42, has_profile: bool = True) -> Agent:
    rng = random.Random(seed)
    a = Agent(
        agent_id=1,
        tier=Tier.B,
        role=Role.RESIDENT,
        name="테스트",
        age=rng.randint(20, 65),
        gender=rng.choice(["M", "F"]),
        home_dong="서교동",
        income_level=rng.randint(1, 3),
    )
    a.current_dong = rng.choice(["서교동", "합정동", "망원동"])
    # store_satisfaction / blacklist / habit / learned_prefs 일부 채움
    a.store_satisfaction = {1: 0.8, 5: 0.3, 12: 0.95}
    a.blacklist = {99, 200}
    a.habit_store = {14: 7, 12: 3}
    a.learned_prefs = {"카페": 0.7, "음식점": 0.4, "주점": 0.5, "편의점": 0.6}
    a.pending_recommendations = [
        {"store_id": 5, "from_agent": 99, "category": "카페", "strength": 0.8},
        {"store_id": 20, "from_agent": 88, "category": "음식점", "strength": 0.6},
    ]
    a.visited_today = [3, 7, 11]

    if has_profile:
        from src.simulation.profile_builder import AgentProfile

        a.profile = AgentProfile(
            age=a.age,
            gender=a.gender,
            home_dong=a.home_dong,
            role=a.role,
            income_level=a.income_level,
            daily_budget=30000.0,
            price_sensitivity=0.65,
            mobility_score=0.6,
            pref_cafe=0.7,
            pref_restaurant=0.5,
            pref_pub=0.4,
            pref_convenience=0.6,
            lifestyle_tag="20대 직장인",
        )
    return a


def _make_policy() -> PersonaPolicy:
    return PersonaPolicy(
        policy_id="resident_맑음_afternoon",
        role="resident",
        weather="맑음",
        time_block="afternoon",
        mobility=0.55,
        indoor_preference=0.6,
        distance_sensitivity=0.5,
        crowd_tolerance=0.4,
        cafe_preference=0.7,
        meal_preference=0.55,
        pub_preference=0.3,
        cvs_preference=0.3,
        dong_affinity={"서교동": 0.8, "합정동": 0.6, "망원동": 0.4},
        visit_probability=0.5,
        repeat_visit_bonus=0.15,
        spend_tendency=0.5,
    )


@pytest.mark.parametrize("seed", [42, 7, 100, 2026])
def test_batch_matches_single(seed: int) -> None:
    """score_stores_batch 와 score_store 단일 호출 결과가 모든 매장에서 동치."""
    world = _make_world(seed=seed, n_stores=300)
    agent = _make_agent(seed=seed, has_profile=(seed % 2 == 0))
    policy = _make_policy()
    stores = list(world.stores.values())

    single = [score_store(s, agent, policy, world) for s in stores]
    batch = score_stores_batch(stores, agent, policy, world)

    assert len(single) == len(batch)
    diffs = [abs(a - b) for a, b in zip(single, batch, strict=True)]
    max_diff = max(diffs)
    assert max_diff < 1e-9, (
        f"score_stores_batch 회귀 발생 (seed={seed}): max abs diff={max_diff:.6e}.\n"
        f"first 5 single={single[:5]}\nfirst 5 batch={batch[:5]}"
    )


def test_batch_empty_returns_empty() -> None:
    """빈 stores list → 빈 결과."""
    world = _make_world()
    agent = _make_agent()
    policy = _make_policy()
    out = score_stores_batch([], agent, policy, world)
    assert out == []


def test_batch_handles_blacklist_zero() -> None:
    """blacklist 매장은 score=0.0 (단일 score_store 와 동치)."""
    world = _make_world(seed=1, n_stores=20)
    agent = _make_agent(seed=1)
    policy = _make_policy()
    stores = list(world.stores.values())
    # 첫 매장 강제 blacklist 추가
    agent.blacklist.add(stores[0].store_id)

    single = [score_store(s, agent, policy, world) for s in stores]
    batch = score_stores_batch(stores, agent, policy, world)
    assert single[0] == 0.0
    assert batch[0] == 0.0
    for s_, b_ in zip(single[1:], batch[1:], strict=True):
        assert math.isclose(s_, b_, abs_tol=1e-9)


def test_batch_handles_no_profile() -> None:
    """agent.profile=None 인 경우도 단일 score_store 와 동치."""
    world = _make_world(seed=2, n_stores=50)
    agent = _make_agent(seed=2, has_profile=False)
    policy = _make_policy()
    stores = list(world.stores.values())

    single = [score_store(s, agent, policy, world) for s in stores]
    batch = score_stores_batch(stores, agent, policy, world)
    diffs = [abs(a - b) for a, b in zip(single, batch, strict=True)]
    assert max(diffs) < 1e-9
