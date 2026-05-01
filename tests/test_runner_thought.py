"""Tier S 50 LLM thought 통합 회귀 보호 테스트.

검증 대상:
    - `_select_thought_agents`: Tier S 50명 cap 정확성
    - `run_simulation(enable_llm_thought=...)`: thoughts 필드 채움/비움 분기
    - `LLMBrain.generate_thought` mock 모드 fallback (dialog_templates)
    - `/simulate-abm` endpoint 응답 스키마 (thoughts/thought_* 5개 필드)

비용 발생 0 — 전부 `ModelConfig(mock_mode=True)` + dialog_templates fallback,
또는 `run_simulation` 자체를 monkeypatch 로 우회.
"""

from __future__ import annotations

import sys
from pathlib import Path

# tests 디렉토리에서 실행되어도 backend 패키지가 임포트되도록 sys.path 보정.
_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from src.simulation.agents import Agent, Role, Tier  # noqa: E402
from src.simulation.config import ModelConfig, PopulationMix, TierDistribution  # noqa: E402
from src.simulation.dialog_templates import TEMPLATES  # noqa: E402
from src.simulation.runner import (  # noqa: E402
    SimulationResult,
    _select_thought_agents,
    run_simulation,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_agent(agent_id: int, tier: Tier, role: Role = Role.RESIDENT) -> Agent:
    return Agent(
        agent_id=agent_id,
        tier=tier,
        role=role,
        name=f"agent_{agent_id}",
        age=30,
        gender="M",
        home_dong="서교동",
    )


def _mixed_population(
    n_s: int,
    n_a: int,
    n_b: int,
    s_role: Role = Role.RESIDENT,
) -> list[Agent]:
    """Tier S/A/B 가 섞인 agent 리스트. agent_id 는 1 부터 순차 (선택 안정 순서 검증용)."""
    agents: list[Agent] = []
    aid = 1
    for _ in range(n_s):
        agents.append(_make_agent(aid, Tier.S, role=s_role))
        aid += 1
    for _ in range(n_a):
        agents.append(_make_agent(aid, Tier.A))
        aid += 1
    for _ in range(n_b):
        agents.append(_make_agent(aid, Tier.B))
        aid += 1
    return agents


# ---------------------------------------------------------------------------
# 1. _select_thought_agents 단위 테스트
# ---------------------------------------------------------------------------
def test_select_thought_agents_picks_first_50():
    """200 agents (Tier S 60 + A 80 + B 60) → 50 명 cap, 모두 Tier.S."""
    agents = _mixed_population(n_s=60, n_a=80, n_b=60)
    selected = _select_thought_agents(agents, n=50)
    assert len(selected) == 50
    assert all(a.tier == Tier.S for a in selected), "Tier S 외 agent 가 선택됨"
    # agent_id 오름차순으로 정렬되는지 (안정 순서)
    ids = [a.agent_id for a in selected]
    assert ids == sorted(ids), f"선택 결과가 agent_id 오름차순 아님: {ids[:5]}..."
    # 첫 50 Tier S 가 1..60 중 처음 50 (1..50) 이어야 함 — 안정 cap
    assert ids == list(range(1, 51)), f"첫 50 Tier S 가 1..50 이 아님: {ids[:5]}..."


def test_select_thought_agents_under_50_returns_all():
    """Tier S 30 명 only → 30 반환 (cap 미적용)."""
    agents = _mixed_population(n_s=30, n_a=100, n_b=100)
    selected = _select_thought_agents(agents, n=50)
    assert len(selected) == 30
    assert all(a.tier == Tier.S for a in selected)


def test_select_thought_agents_excludes_ext_first():
    """non-ext (resident/commuter 등) 우선 선택 — ext_commuter/visitor 는 마지막에 보충.

    5000 agents 시뮬에서 ext 비율이 ~80% 라 Tier S 풀에 ext 가 대량 포함될 수 있는데,
    ext 가 외부 시간엔 hour 루프에서 skip 되어 호출 수가 급감 (관찰: 30 calls vs 예상 100+).
    non-ext 우선 채택으로 활성 hour 비율을 높여 thought 호출 효율을 회복.

    풀: ext 50 (id 1..50) + non-ext 30 (id 51..80) → 50 cap 시
        non-ext 30 (id 51..80) + ext 20 (id 1..20) = 50.
    """
    agents: list[Agent] = []
    aid = 1
    # 먼저 ext 50명 (Tier S) — agent_id 가 작아 안정 순서 정렬 시 앞에 오도록 배치
    for _ in range(50):
        agents.append(_make_agent(aid, Tier.S, role=Role.EXT_COMMUTER))
        aid += 1
    # 그 다음 non-ext 30명 (Tier S, RESIDENT) — agent_id 51..80
    for _ in range(30):
        agents.append(_make_agent(aid, Tier.S, role=Role.RESIDENT))
        aid += 1

    selected = _select_thought_agents(agents, n=50)
    assert len(selected) == 50

    n_non_ext = sum(1 for a in selected if a.role not in (Role.EXT_COMMUTER, Role.EXT_VISITOR))
    n_ext = sum(1 for a in selected if a.role in (Role.EXT_COMMUTER, Role.EXT_VISITOR))
    assert n_non_ext == 30, f"non-ext 30 우선 선택 실패: non_ext={n_non_ext}, ext={n_ext}"
    assert n_ext == 20, f"ext 20 보충 실패: non_ext={n_non_ext}, ext={n_ext}"

    # non-ext 가 먼저 (앞 30개), ext 가 나중 (뒤 20개) — 그룹 내부는 agent_id 오름차순
    non_ext_ids = [a.agent_id for a in selected[:30]]
    ext_ids = [a.agent_id for a in selected[30:]]
    assert non_ext_ids == list(range(51, 81)), f"non-ext 안정 순서 깨짐: {non_ext_ids[:5]}..."
    assert ext_ids == list(range(1, 21)), f"ext 보충 안정 순서 깨짐: {ext_ids[:5]}..."


def test_select_thought_agents_ext_only_fills_cap():
    """Tier S 가 전부 ext 만 있을 때 → ext 로 cap 채움 (회귀 안전 — 빈 리스트 X)."""
    agents = _mixed_population(n_s=60, n_a=20, n_b=20, s_role=Role.EXT_VISITOR)
    selected = _select_thought_agents(agents, n=50)
    assert len(selected) == 50
    assert all(a.role == Role.EXT_VISITOR for a in selected)
    # agent_id 오름차순 (1..50)
    ids = [a.agent_id for a in selected]
    assert ids == list(range(1, 51)), f"ext only 안정 순서 깨짐: {ids[:5]}..."


# ---------------------------------------------------------------------------
# 2. run_simulation 회귀 (enable_llm_thought=False)
# ---------------------------------------------------------------------------
def test_runner_disabled_thoughts_returns_empty():
    """enable_llm_thought=False → thoughts==[], thought_calls==0 (회귀 안전)."""
    pop = PopulationMix(residents=40, commuters=10, visitors=5, owners=2, ext_commuters=2, ext_visitors=1)
    tier = TierDistribution(tier_s=10, tier_a=20, tier_b=30)
    cfg = ModelConfig(mock_mode=True)

    result = run_simulation(
        days=1,
        pop=pop,
        tier=tier,
        cfg=cfg,
        seed=42,
        verbose=False,
        use_rds=False,
        use_profiles=False,
        seed_memory=False,
        enable_llm_thought=False,
    )
    assert isinstance(result, SimulationResult)
    assert result.thoughts == [], f"비활성인데 thoughts 채워짐: len={len(result.thoughts)}"
    assert result.thought_calls == 0
    assert result.thought_input_tokens == 0
    assert result.thought_output_tokens == 0
    assert result.thought_cached_tokens == 0


# ---------------------------------------------------------------------------
# 3. run_simulation enable_llm_thought=True (mock 모드 → dialog_templates fallback)
# ---------------------------------------------------------------------------
def test_runner_enabled_thoughts_with_mock_mode():
    """mock_mode + enable_llm_thought=True → thoughts 채워짐, 모든 entry schema OK."""
    # 100 agents 중 Tier S 60 → 50 cap 발동 검증
    pop = PopulationMix(residents=60, commuters=20, visitors=10, owners=5, ext_commuters=3, ext_visitors=2)
    tier = TierDistribution(tier_s=60, tier_a=20, tier_b=20)
    cfg = ModelConfig(mock_mode=True)

    result = run_simulation(
        days=1,
        pop=pop,
        tier=tier,
        cfg=cfg,
        seed=42,
        verbose=False,
        use_rds=False,
        use_profiles=False,
        seed_memory=False,
        enable_llm_thought=True,
    )
    assert isinstance(result, SimulationResult)
    assert len(result.thoughts) > 0, "mock 모드에서도 dialog_templates fallback 으로 thought 가 채워져야 함"

    required_keys = {"day", "hour", "agent_id", "archetype", "thought", "lat", "lon"}
    for entry in result.thoughts:
        missing = required_keys - set(entry.keys())
        assert not missing, f"thought entry 필드 누락: {missing} (entry={entry})"
        # thought 내용 — fallback 길이는 dialog_templates 기준 30자 이내 (대부분 12자 이하)
        assert isinstance(entry["thought"], str)
        assert 0 < len(entry["thought"]) <= 30, f"thought 길이 이상: {entry['thought']!r} (len={len(entry['thought'])})"

    # 5000 cap (Tier S 50명) — 유니크 agent 수 ≤ 50
    unique_agent_ids = {t["agent_id"] for t in result.thoughts}
    assert len(unique_agent_ids) <= 50, f"thought 생성 agent 수 cap 초과: {len(unique_agent_ids)}"


# ---------------------------------------------------------------------------
# 4. archetype 검증 — agent.persona_id 와 일치, dialog_templates 키 중 하나
# ---------------------------------------------------------------------------
def test_thought_archetype_matches_agent():
    """thought entry archetype 이 dialog_templates 키 중 하나여야 함."""
    pop = PopulationMix(residents=40, commuters=10, visitors=5, owners=2, ext_commuters=2, ext_visitors=1)
    tier = TierDistribution(tier_s=40, tier_a=10, tier_b=10)
    cfg = ModelConfig(mock_mode=True)

    result = run_simulation(
        days=1,
        pop=pop,
        tier=tier,
        cfg=cfg,
        seed=42,
        verbose=False,
        use_rds=False,
        use_profiles=False,
        seed_memory=False,
        enable_llm_thought=True,
    )
    valid_archetypes = set(TEMPLATES.keys())
    assert result.thoughts, "thoughts 가 비어 있어 archetype 검증 불가"
    for entry in result.thoughts:
        assert entry["archetype"] in valid_archetypes, (
            f"archetype '{entry['archetype']}' 가 dialog_templates 키에 없음 (valid={valid_archetypes})"
        )


# ---------------------------------------------------------------------------
# 5. unknown archetype 부여 → office_worker fallback (LLMBrain.generate_thought 단위)
# ---------------------------------------------------------------------------
def test_thought_dialog_templates_fallback_no_unknown():
    """unknown archetype 부여한 agent → office_worker 로 매핑되어 '...' 회피."""
    from src.simulation.brain import LLMBrain
    from src.simulation.world import seed_synthetic_world

    cfg = ModelConfig(mock_mode=True)
    brain = LLMBrain(cfg=cfg, seed=42)
    agent = _make_agent(99, Tier.S)
    agent.persona_id = "unknown_xyz"  # dialog_templates 에 없는 archetype
    world = seed_synthetic_world(seed=42)
    # generate_thought 가 mock 모드 → _thought_template_fallback 호출
    # office_worker 에 fallback 되어 "..." default 회피.
    seen = {brain.generate_thought(agent, world) for _ in range(20)}
    assert "..." not in seen, "unknown archetype 에서 default '...' fallback 가 발생함 (office_worker 매핑 실패)"
    assert all(s.strip() != "" for s in seen), "빈 문자열 fallback 발생"
    # office_worker 템플릿 어휘 중 하나는 등장해야 함
    office_phrases = {phrase for situations in TEMPLATES["office_worker"].values() for phrase in situations}
    assert seen & office_phrases, f"unknown archetype 가 office_worker 로 매핑되지 않은 것으로 보임 — seen={seen}"


# ---------------------------------------------------------------------------
# 6. /simulate-abm endpoint 응답 스키마
# ---------------------------------------------------------------------------
def test_simulate_abm_endpoint_response_schema(monkeypatch):
    """POST /simulate-abm — thoughts/thought_* 5 필드 응답 스키마 검증.

    실제 시뮬을 돌리지 않고 `run_simulation` 을 monkeypatch 로 stub 해서
    DB 의존성 + LLM 비용을 차단. enable_llm_thought=False 시
    thoughts==[], thought_calls==0 응답 보장.
    """
    # Redis (rate-limit + cache) 도 mock — async aioredis.from_url 도 차단해야 함
    # 단, run_simulation 만 stub 하면 캐시 SET 이 시도되지만 실패 시 무시되도록
    # 이미 main.py 에 try/except 처리됨 (캐시 실패는 silent skip).
    stub_result = SimulationResult(
        days=1,
        total_decisions=0,
        tier_s_calls=0,
        tier_a_calls=0,
        estimated_cost_usd=0.0,
        top_stores=[],
        sample_stories=[],
        category_totals={},
        dong_totals={},
        daily_visits=0,
        daily_revenue=0.0,
        thoughts=[],
        thought_calls=0,
        thought_input_tokens=0,
        thought_output_tokens=0,
        thought_cached_tokens=0,
    )

    def _fake_run_simulation(*args, **kwargs):
        return stub_result

    # main.py 가 lazy import — `from src.simulation.runner import run_simulation as abm_run`
    # 따라서 source module 에 patch 하면 그 후 import 시 stub 이 사용됨.
    import src.simulation.runner as runner_mod

    monkeypatch.setattr(runner_mod, "run_simulation", _fake_run_simulation)

    # FastAPI 앱 로드
    from src.main import app

    client = TestClient(app)
    payload = {
        "target_district": "서교동",
        "business_type": "카페",
        "brand_name": "테스트브랜드",
        "langgraph_result": {},
        "n_agents": 50,
        "days": 1,
        "scenario": {
            "weather_override": None,
            "date_override": None,
            "weekend_force": False,
            "rent_shock_pct": 0.0,
        },
        "enable_llm_thought": False,
    }
    resp = client.post("/simulate-abm", json=payload)
    assert resp.status_code == 200, f"endpoint 실패: status={resp.status_code} body={resp.text[:300]}"
    body = resp.json()

    # 5 필드 모두 존재
    for key in (
        "thoughts",
        "thought_calls",
        "thought_input_tokens",
        "thought_output_tokens",
        "thought_cached_tokens",
    ):
        assert key in body, f"응답에 '{key}' 누락 (body keys={list(body.keys())[:20]})"

    # 타입/값
    assert isinstance(body["thoughts"], list), f"thoughts 타입 list 아님: {type(body['thoughts'])}"
    assert body["thought_calls"] == 0
    assert body["thought_input_tokens"] == 0
    assert body["thought_output_tokens"] == 0
    assert body["thought_cached_tokens"] == 0
