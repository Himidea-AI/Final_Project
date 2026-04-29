"""P1 — archetype-home_dong 매칭 검증.

목적:
    - `_pick_archetype_for` 가 home_dong 의 preferred_dongs 매칭 archetype 을 70% 우선 선택
    - matched 가 0 일 때 others 풀에서 random fallback (에러 X)
    - OWNER role agent 는 여전히 f&b_owner archetype 부여 (회귀 안전)
    - 100 Tier S agent (다양 home_dong) 분포가 random uniform 보다 매칭 비율 높음

학술 근거: Argyle et al. 2023 — synthetic persona joint distribution 정합성.
"""

from __future__ import annotations

import random
import sys
from collections import Counter
from pathlib import Path

# tests 디렉토리에서 실행되어도 backend 패키지가 임포트되도록 sys.path 보정.
_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.simulation.agents import Agent, Role, Tier  # noqa: E402
from src.simulation.personas import (  # noqa: E402
    ARCHETYPES,
    _pick_archetype_for,
    assign_personas,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_agent(
    agent_id: int,
    home_dong: str,
    role: Role = Role.RESIDENT,
    tier: Tier = Tier.S,
) -> Agent:
    return Agent(
        agent_id=agent_id,
        tier=tier,
        role=role,
        name=f"agent_{agent_id}",
        age=30,
        gender="M",
        home_dong=home_dong,
    )


# ---------------------------------------------------------------------------
# 1. _pick_archetype_for — matched 우선 (70%) 검증
# ---------------------------------------------------------------------------
def test_pick_archetype_prefers_matched_dong():
    """home_dong=연남동 → 1000 sample 시 matched archetype 비율 ≥ 60%.

    연남동 매칭 archetype: creative_freelancer, student_couple, tourist_foreign.
    이론 기대치 70% — 분산 허용 ±10% → 60% 하한.
    """
    rng = random.Random(42)
    matched_ids = {arc["id"] for arc in ARCHETYPES[:-1] if "연남동" in arc["preferred_dongs"]}
    assert matched_ids == {"creative_freelancer", "student_couple", "tourist_foreign"}, (
        f"매칭 archetype 가정 깨짐: {matched_ids}"
    )

    counts = Counter()
    n_iter = 1000
    for _ in range(n_iter):
        arc = _pick_archetype_for("연남동", rng)
        counts[arc["id"]] += 1

    matched_total = sum(counts[i] for i in matched_ids)
    ratio = matched_total / n_iter
    assert ratio >= 0.60, f"matched 비율 < 60% (실제 {ratio:.2%}, counts={dict(counts)})"
    # 다양성 보존 — 30% 가량은 mismatch 가 나와야 함 (학술 noise)
    assert ratio <= 0.85, f"matched 비율 > 85% — 다양성 부족 (실제 {ratio:.2%}, counts={dict(counts)})"


def test_pick_archetype_falls_back_to_others():
    """home_dong=존재안하는동 → matched 0 → others 풀 random (예외 X)."""
    rng = random.Random(42)
    seen_ids = set()
    for _ in range(50):
        arc = _pick_archetype_for("존재안하는동", rng)
        seen_ids.add(arc["id"])
    # 7종 archetype (f&b_owner 제외) 중 다수가 등장해야 함 (uniform)
    assert "f&b_owner" not in seen_ids, "OWNER 전용 archetype 가 일반 풀에 노출됨"
    assert len(seen_ids) >= 4, f"others fallback 다양성 부족: 본 archetype {seen_ids}"


def test_pick_archetype_handles_none_home_dong():
    """home_dong=None / "" 도 예외 없이 others 풀 random 처리."""
    rng = random.Random(42)
    for invalid in (None, ""):
        arc = _pick_archetype_for(invalid, rng)
        assert arc["id"] != "f&b_owner", "OWNER 전용 archetype 부여됨"
        assert "id" in arc and "label" in arc and "preferred_dongs" in arc


def test_pick_archetype_partial_match_hongdae():
    """tourist_foreign 의 '홍대(서교)' — 부분 매칭 처리 확인.

    home_dong='서교동' 은 student_couple(서교동 정확) + tourist_foreign(홍대(서교) 부분)
    둘 다 매칭되어야 함.
    """
    rng = random.Random(42)
    matched_ids = set()
    for _ in range(2000):
        arc = _pick_archetype_for("서교동", rng)
        matched_ids.add(arc["id"])
    # 부분 매칭이 작동해 tourist_foreign 도 다수 matched 풀로 들어가야 함
    # (정확 매칭 student_couple + 부분 매칭 tourist_foreign 둘 다 본 적 있어야 함)
    assert "student_couple" in matched_ids
    assert "tourist_foreign" in matched_ids


# ---------------------------------------------------------------------------
# 2. assign_personas 회귀 — OWNER 보존
# ---------------------------------------------------------------------------
def test_pick_archetype_owner_unaffected():
    """OWNER role Tier S 는 여전히 f&b_owner (ARCHETYPES[-1]) 부여."""
    agents = [
        _make_agent(1, home_dong="연남동", role=Role.OWNER, tier=Tier.S),
        _make_agent(2, home_dong="공덕동", role=Role.OWNER, tier=Tier.S),
        _make_agent(3, home_dong="서교동", role=Role.RESIDENT, tier=Tier.S),
    ]
    personas = assign_personas(agents, seed=42)
    assert agents[0].persona_id == "f&b_owner"
    assert agents[1].persona_id == "f&b_owner"
    assert agents[2].persona_id != "f&b_owner"
    assert personas[1].archetype_id == "f&b_owner"
    assert personas[2].archetype_id == "f&b_owner"
    assert personas[3].archetype_id != "f&b_owner"


def test_assign_personas_skips_non_tier_s():
    """Tier A/B agent 는 persona_id 안 받음 (회귀 안전)."""
    agents = [
        _make_agent(1, home_dong="연남동", tier=Tier.A),
        _make_agent(2, home_dong="공덕동", tier=Tier.B),
        _make_agent(3, home_dong="서교동", tier=Tier.S),
    ]
    personas = assign_personas(agents, seed=42)
    assert agents[0].persona_id is None
    assert agents[1].persona_id is None
    assert agents[2].persona_id is not None
    assert set(personas.keys()) == {3}


def test_assign_personas_seed_reproducibility():
    """같은 seed → 같은 archetype 부여 (재현성)."""
    agents_a = [
        _make_agent(i, home_dong=d, tier=Tier.S)
        for i, d in enumerate(["연남동", "공덕동", "상암동", "서교동", "대흥동"], start=1)
    ]
    agents_b = [
        _make_agent(i, home_dong=d, tier=Tier.S)
        for i, d in enumerate(["연남동", "공덕동", "상암동", "서교동", "대흥동"], start=1)
    ]
    assign_personas(agents_a, seed=123)
    assign_personas(agents_b, seed=123)
    ids_a = [a.persona_id for a in agents_a]
    ids_b = [a.persona_id for a in agents_b]
    assert ids_a == ids_b, f"seed 재현성 깨짐: {ids_a} != {ids_b}"


# ---------------------------------------------------------------------------
# 3. 분포 현실성 — uniform random 보다 matched 비율 ↑
# ---------------------------------------------------------------------------
def test_assign_personas_distribution_realistic():
    """100 Tier S agent (다양 home_dong) → matched 비율이 uniform random 보다 ↑.

    Uniform random baseline: 7종 archetype 중 평균 매칭 archetype 수 ~2.3개
    → matched 비율 ≈ 2.3/7 = 33%. 가중 샘플링은 ≥ 50% 기대.
    """
    # 7개 동을 다양하게 분포 (각 archetype 가 1개 이상 매칭되도록)
    home_dongs = [
        "연남동",
        "합정동",
        "망원1동",  # creative_freelancer
        "공덕동",
        "도화동",
        "용강동",  # office_worker
        "상암동",
        "성산1동",  # broadcasting_staff
        "서교동",  # student_couple (tourist_foreign 부분)
        "대흥동",
        "염리동",
        "아현동",  # retired_local
        "성산2동",
        "망원2동",  # young_parent
    ]
    agents = []
    for i in range(100):
        dong = home_dongs[i % len(home_dongs)]
        agents.append(_make_agent(i + 1, home_dong=dong, tier=Tier.S))

    personas = assign_personas(agents, seed=42)

    # archetype 별 preferred_dongs 사전
    pref_map = {arc["id"]: arc["preferred_dongs"] for arc in ARCHETYPES[:-1]}

    matched = 0
    for a in agents:
        prefs = pref_map.get(a.persona_id, [])
        if a.home_dong in prefs or any(a.home_dong in p or p in a.home_dong for p in prefs):
            matched += 1

    ratio = matched / len(agents)
    assert ratio >= 0.50, f"matched 비율 < 50% (실제 {ratio:.2%}) — 가중 샘플링 효과 미흡"
    # personas dict 도 동일 크기
    assert len(personas) == len(agents)


def test_assign_personas_diversity_preserved():
    """모든 agent 가 같은 home_dong 이어도 다양성 보존 — 30% 는 mismatch 가능."""
    # 100 agent 모두 연남동 거주 → 매칭 archetype: creative_freelancer/student_couple/tourist_foreign
    agents = [_make_agent(i + 1, home_dong="연남동", tier=Tier.S) for i in range(100)]
    assign_personas(agents, seed=42)
    archetype_ids = {a.persona_id for a in agents}
    # 매칭 3 + others 4 = 최대 7. 다양성 보존 시 4종 이상 등장 기대
    assert len(archetype_ids) >= 4, f"동일 home_dong 에서 다양성 부족 — 본 archetype {archetype_ids}"
