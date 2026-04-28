"""신규 매장 inject 회귀 테스트.

검증 대상:
    - `/simulate-abm` 엔드포인트가 `new_store_spec` 에 `popularity_boost` 를
      주입해 runner 가 신규 매장을 의미 있는 weight 로 시뮬에 반영하는지.
    - `run_simulation(scenario.new_store=...)` 가 synthetic world 에서 new_spot_*
      매장 visit 을 발생시키고 `new_store_visits`/`new_store_revenue` 가
      0 보다 크게 집계되는지 (popularity_boost=5.0 기준).
    - `popularity_boost=1.0` (구 default) 대비 5.0 (현 default) 이 평균적으로
      visit 수가 더 많은지 — 마이크로 벤치 시드 1개로 확인.

⚠️ 비용 발생 0 — `ModelConfig(mock_mode=True)` + synthetic world.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.simulation.config import ModelConfig, PopulationMix, Scenario, TierDistribution  # noqa: E402
from src.simulation.runner import run_simulation  # noqa: E402
from src.simulation.vacancy_inject import DEFAULT_POPULARITY_BOOST  # noqa: E402


def _run(boost: float, seed: int = 42):
    """공통 시뮬 1회 — 신규 매장 1개 주입 (도화동 음식점)."""
    pop = PopulationMix(residents=300, commuters=100, visitors=50, owners=20, ext_commuters=20, ext_visitors=10)
    tier = TierDistribution(tier_s=5, tier_a=20, tier_b=475)
    cfg = ModelConfig(n_personas=500, mock_mode=True)
    scenario = Scenario(
        new_store={
            "district": "도화동",
            "brand": "TestNew",
            "category": "음식점",
            "lat": 37.546,
            "lon": 126.953,
            "popularity_boost": boost,
        },
    )
    return run_simulation(
        days=1,
        pop=pop,
        tier=tier,
        cfg=cfg,
        seed=seed,
        verbose=False,
        use_rds=False,  # synthetic — RDS 의존 X
        use_profiles=False,
        seed_memory=False,
        enable_llm_thought=False,
        scenario=scenario,
    )


def test_new_store_injected_to_synthetic_world():
    """popularity_boost=5.0 → 신규 매장이 visit 받음 (회귀 보호 핵심).

    이 test 가 visits=0 으로 fail 하면 inject path 또는 candidate 등록이 깨진 것.
    """
    result = _run(boost=DEFAULT_POPULARITY_BOOST)
    assert result.new_store_visits > 0, (
        f"신규 매장 visits=0 — inject 가 candidate 에 반영 안 됨 (synthetic world). "
        f"result.new_store_visits={result.new_store_visits}, "
        f"new_store_revenue={result.new_store_revenue}"
    )
    assert result.new_store_revenue > 0, "visits>0 인데 revenue=0 — apply() 에서 spend 누락"
    assert result.new_store_visit_share_pct > 0, (
        f"visit_share_pct=0 — total_visits 분모/분자 계산 오류. share={result.new_store_visit_share_pct}"
    )
    # 도화동 dong_totals 에도 신규 매장 visit 가 합산되어야 함
    dt = result.dong_totals or {}
    assert dt.get("도화동", {}).get("visits", 0) >= result.new_store_visits, (
        f"도화동 dong_totals.visits ({dt.get('도화동')}) 가 new_store_visits ({result.new_store_visits}) "
        f"보다 적음 — 집계 누락"
    )


def test_new_store_popularity_boost_increases_visits():
    """popularity_boost=5.0 이 1.0 대비 평균 더 많은 visit (신호 비교).

    sample size 가 작아서 매번 strictly > 는 보장 못 하지만, 동일 seed 에서
    비교하면 5.0 이 평균적으로 1.0 이상이어야 함. 같은 seed 로 단일 비교.
    """
    low = _run(boost=1.0, seed=42)
    high = _run(boost=5.0, seed=42)
    # synthetic world (30 stores per dong) 에서도 5.0 이 1.0 보다 많이 받아야 함.
    # 작은 시뮬 noise 로 동률 가능 → ≥ 로 검증.
    assert high.new_store_visits >= low.new_store_visits, (
        f"popularity_boost=5.0 ({high.new_store_visits}) 가 "
        f"1.0 ({low.new_store_visits}) 보다 적음 — weight 가중치 무력화 가능성"
    )


def test_simulate_abm_endpoint_passes_popularity_boost(monkeypatch):
    """/simulate-abm endpoint 가 new_store_spec 에 popularity_boost 키를
    DEFAULT_POPULARITY_BOOST 로 채워서 run_simulation 에 전달하는지 확인.

    실제 시뮬 X — run_simulation 을 monkeypatch 로 capture 후 spec 검증만.
    """
    from fastapi.testclient import TestClient
    from src.simulation.runner import SimulationResult

    captured: dict = {}

    def _fake_run_simulation(*args, **kwargs):
        captured["scenario"] = kwargs.get("scenario")
        return SimulationResult(
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
        )

    import src.simulation.runner as runner_mod

    monkeypatch.setattr(runner_mod, "run_simulation", _fake_run_simulation)

    from src.main import app

    client = TestClient(app)
    payload = {
        "target_district": "도화동",
        "business_type": "음식점",
        "brand_name": "RegressionGuard",
        "langgraph_result": {},
        "n_agents": 50,
        "days": 1,
        "spot_lat": 37.546,
        "spot_lon": 126.953,
        "scenario": {
            "weather_override": None,
            "date_override": None,
            "weekend_force": False,
            "rent_shock_pct": 0.0,
        },
        "enable_llm_thought": False,
    }
    resp = client.post("/simulate-abm", json=payload)
    assert resp.status_code == 200, f"endpoint 실패: {resp.status_code} {resp.text[:300]}"

    scn = captured.get("scenario")
    assert scn is not None, "run_simulation 이 호출되지 않음 (monkeypatch 미적용?)"
    assert scn.new_store is not None, "scenario.new_store 누락"
    boost = scn.new_store.get("popularity_boost")
    assert boost == DEFAULT_POPULARITY_BOOST, (
        f"main.py 가 new_store.popularity_boost 를 DEFAULT_POPULARITY_BOOST({DEFAULT_POPULARITY_BOOST}) "
        f"로 설정해야 함. 실제: {boost}"
    )
    # 좌표도 spec 에 그대로 들어가야 함 (지도 marker 정확성)
    assert scn.new_store.get("lat") == 37.546
    assert scn.new_store.get("lon") == 126.953
    assert scn.new_store.get("district") == "도화동"
    assert scn.new_store.get("category") == "음식점"
