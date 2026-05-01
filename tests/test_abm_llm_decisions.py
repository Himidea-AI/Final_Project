from __future__ import annotations

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.config.constants import MAPO_DISTRICTS  # noqa: E402
from src.main import AbmSimulationRequest  # noqa: E402
from src.simulation.agents import Agent, Decision, Role, Tier  # noqa: E402
from src.simulation.runner import SimulationResult  # noqa: E402


def test_abm_request_enable_llm_decisions_defaults_false():
    req = AbmSimulationRequest(
        target_district=MAPO_DISTRICTS[0],
        business_type="cafe",
        brand_name="Test Brand",
        langgraph_result={},
    )

    assert req.enable_llm_decisions is False


def test_abm_request_accepts_enable_llm_decisions_true():
    req = AbmSimulationRequest(
        target_district=MAPO_DISTRICTS[0],
        business_type="cafe",
        brand_name="Test Brand",
        langgraph_result={},
        enable_llm_decisions=True,
    )

    assert req.enable_llm_decisions is True


class _BrainSpy:
    def __init__(self):
        self.smart_calls = 0

    def smart_decide(self, agent, world):
        self.smart_calls += 1
        return Decision(action="eat", target_store_id=None, target_dong=agent.home_dong, reason="smart")


def _agent(tier: Tier) -> Agent:
    return Agent(
        agent_id=1,
        tier=tier,
        role=Role.RESIDENT,
        name="tester",
        age=30,
        gender="F",
        home_dong=MAPO_DISTRICTS[0],
    )


def test_tier_s_llm_only_routes_only_tier_s_to_smart_decide(monkeypatch):
    import src.simulation.policy_executor as policy_executor

    policy_calls = {"count": 0}

    def fake_policy_decide(agent, world, rng):
        policy_calls["count"] += 1
        return Decision(action="rest", target_store_id=None, target_dong=agent.home_dong, reason="policy")

    monkeypatch.setattr(policy_executor, "policy_decide", fake_policy_decide)

    world = SimpleNamespace(tier_s_llm_only=True, use_policy=True, current_hour=12)
    brain = _BrainSpy()

    assert _agent(Tier.S).decide(world, brain, rng=None).reason == "smart"
    assert _agent(Tier.A).decide(world, brain, rng=None).reason == "policy"
    assert _agent(Tier.B).decide(world, brain, rng=None).reason == "policy"
    assert brain.smart_calls == 1
    assert policy_calls["count"] == 2


def test_simulate_abm_endpoint_passes_llm_decision_mode_and_returns_stats(monkeypatch):
    captured: dict = {}
    target_district = MAPO_DISTRICTS[0]

    def fake_run_simulation(*args, **kwargs):
        captured.update(kwargs)
        tier = kwargs["tier"]
        assert tier.tier_s == 50
        assert tier.tier_a == 50
        assert tier.tier_b == 0
        return SimulationResult(
            days=1,
            total_decisions=10,
            tier_s_calls=24,
            tier_a_calls=0,
            estimated_cost_usd=0.12,
            top_stores=[],
            sample_stories=[],
            category_totals={},
            dong_totals={target_district: {"visits": 10, "revenue": 100_000.0}},
            daily_visits=10,
            daily_revenue=100_000.0,
            thoughts=[{"agent_id": 1, "day": 1, "hour": 12, "thought": "smart", "lat": None, "lon": None}],
            thought_calls=0,
            thought_input_tokens=0,
            thought_output_tokens=0,
            thought_cached_tokens=0,
        )

    import src.simulation.runner as runner_mod

    monkeypatch.setattr(runner_mod, "run_simulation", fake_run_simulation)

    from src.main import app

    client = TestClient(app)
    response = client.post(
        "/simulate-abm",
        json={
            "target_district": target_district,
            "business_type": "cafe",
            "brand_name": f"Test Brand {uuid.uuid4()}",
            "langgraph_result": {},
            "n_agents": 100,
            "days": 1,
            "enable_llm_thought": True,
            "enable_llm_decisions": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert captured["use_llm_decisions"] is True
    assert body["thought_calls"] == 0
    assert body["tier_s_calls"] == 24
    assert body["tier_a_calls"] == 0
    assert body["estimated_cost_usd"] == 0.12
