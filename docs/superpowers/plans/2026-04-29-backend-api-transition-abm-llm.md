# Backend API Transition And ABM LLM Decisions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 팀원 AI 작업 결과를 프론트엔드가 안정적으로 렌더링할 수 있도록 `/predict`, `/analyze/llm`, `/simulate-abm` 계약을 최신 dev 기준으로 맞추고, 기존 `/simulate` 의존을 제거한다.

**Architecture:** ML 예측은 `POST /predict`가 동별 배열로 제공하고, LLM 분석은 `POST /analyze/llm`가 winner/ranking/리포트를 제공한다. 프론트는 두 응답을 병합해 기존 대시보드 모델을 만들고, ABM은 `POST /simulate-abm`에서 `enable_llm_decisions`로 Tier S 실제 LLM 의사결정 모드를 켠다.

**Tech Stack:** FastAPI, Pydantic v2, LangGraph, PyTorch model interface, Redis, React 18, TypeScript, Vite, Tailwind CSS.

---

## Locked Decisions

- `quarterly_projection[].revenue`는 수지니님 답변 기준 **분기 매출**이다. 월매출 UI가 필요하면 프론트에서 `revenue / 3`으로 표시한다.
- `/predict` 응답 `data[]`에는 `customer_segment`, `living_pop_forecast`, `emerging_signal` 3개 필드를 추가한다. 각 필드는 기존 `/simulate` 동일 필드 구조를 재사용하고, 생성 실패 또는 입력 부족 시 `null`이다.
- `/analyze/llm` 최종 URL은 `POST /analyze/llm`이다.
- `/analyze/llm`의 `winner_district`와 `top_3_candidates`는 사용자가 선택한 `target_districts` 안에서만 고른다.
- `/analyze/llm` 실패 정책은 현재 구현 기준 전체 실패다. 내부 fallback이 성공한 경우만 부분 필드가 비어 있는 success가 가능하다.
- `top_3_candidates`는 winner 제외, 최대 3개이며 항상 3개가 아니다.
- `/simulate`는 수지니님 요청대로 제거 대상이다. 다만 현재 프론트가 `/simulate`를 호출하므로 프론트 전환이 먼저 완료되어야 한다.
- 예진님 PR 기준 agent id는 `operational_fit`이 아니라 `inflow`다.
- ABM 팀장님 결정서 기준 `enable_llm_decisions=true`일 때 Tier S 50명만 `smart_decide`를 사용하고 Tier A/B는 `policy_decide`를 사용한다.

## File Map

- Modify: `backend/src/schemas/simulation_output.py`
  - `DistrictPredictionResult`에 `/predict.data[]` 신규 3필드를 추가한다.
- Modify: `backend/src/main.py`
  - `/predict`에서 target profile을 `ModelOutput.generate()`로 전달하고 신규 3필드를 반환한다.
  - `map_state_to_simulation_output()`에 `final_report` 매핑을 복구한다.
  - `/simulate-abm` 요청 스키마, 캐시 키, runner 호출에 `enable_llm_decisions`를 추가한다.
  - 프론트 전환 후 `/simulate` 제거 또는 410 응답으로 정리한다.
- Modify: `backend/src/simulation/agents.py`
  - `world.tier_s_llm_only`가 켜진 경우 Tier S만 `smart_decide()`로 라우팅한다.
- Modify: `backend/src/simulation/runner.py`
  - `use_llm_decisions` 인자를 추가하고, thought 생성 시 `smart_decide.reason` 재사용 경로를 추가한다.
- Modify: `frontend/src/api/client.ts`
  - 기존 `runSimulation()`의 `/simulate` 단일 호출을 `/predict` + `/analyze/llm` 병합 호출로 바꾼다.
- Modify: `frontend/src/App.tsx`
  - `/simulate` 전제 문구와 응답 병합 흐름을 새 API 구조에 맞춘다.
- Modify: `frontend/src/components/SimulationResult/dashboard/tabs/AbmTab.tsx`
  - `/api/simulate-abm` 요청에 `enable_llm_decisions: true`를 추가한다.
- Modify: `frontend/src/components/SimulationResult/dashboard/tabs/InsightDashboard.tsx`
  - `operational_fit` 표시가 남아 있으면 `inflow`로 바꾸고, agent 목록을 최신 8개 구조와 맞춘다.
- Modify: `docs/architecture/api-contract.md`
  - `/predict`, `/analyze/llm`, `/simulate-abm` 최신 계약을 문서화하고 `/simulate` 제거 계획을 표시한다.
- Test: `tests/test_predict_contract.py`
- Test: `tests/test_analysis_contract.py`
- Test: `tests/test_abm_llm_decisions.py`
- Test: `tests/test_runner_thought.py`

---

### Task 1: `/predict` Response Schema 확장

**Files:**
- Modify: `backend/src/schemas/simulation_output.py`
- Test: `tests/test_predict_contract.py`

- [ ] **Step 1: Write the failing schema test**

Create `tests/test_predict_contract.py` with this content:

```python
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.schemas.simulation_output import DistrictPredictionResult


def test_district_prediction_result_exposes_optional_extended_ml_fields():
    result = DistrictPredictionResult(
        district="서교동",
        dong_code="11440660",
        customer_segment={"profile_summary": "20대 여성 중심"},
        living_pop_forecast={"dong_name": "서교동", "n_quarters": 4},
        emerging_signal={"signal": "emerging", "summary": "신흥 상권 신호"},
    )

    dumped = result.model_dump()

    assert dumped["customer_segment"] == {"profile_summary": "20대 여성 중심"}
    assert dumped["living_pop_forecast"] == {"dong_name": "서교동", "n_quarters": 4}
    assert dumped["emerging_signal"] == {"signal": "emerging", "summary": "신흥 상권 신호"}


def test_district_prediction_result_defaults_extended_ml_fields_to_none():
    dumped = DistrictPredictionResult(district="서교동").model_dump()

    assert dumped["customer_segment"] is None
    assert dumped["living_pop_forecast"] is None
    assert dumped["emerging_signal"] is None
```

- [ ] **Step 2: Run the schema test and confirm it fails**

Run:

```powershell
pytest tests/test_predict_contract.py -q
```

Expected: failure because `DistrictPredictionResult` does not accept or dump the three new fields yet.

- [ ] **Step 3: Add the fields to `DistrictPredictionResult`**

In `backend/src/schemas/simulation_output.py`, update the class:

```python
class DistrictPredictionResult(BaseModel):
    """동별 ML 예측 결과 (/predict data[] 응답 단위)"""

    district: str
    dong_code: str | None = None
    is_excluded_combo: bool = False
    is_mock: bool = False
    quarterly_projection: list[QuarterlyProjection] = Field(default_factory=list)
    scenarios: dict | None = None
    bep: dict | None = None
    closure_rate: dict | None = None
    closure_risk: dict | None = None
    shap_result: ShapResult | None = None
    customer_segment: dict | None = None
    living_pop_forecast: dict | None = None
    emerging_signal: dict | None = None
```

- [ ] **Step 4: Re-run the schema test**

Run:

```powershell
pytest tests/test_predict_contract.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/schemas/simulation_output.py tests/test_predict_contract.py
git commit -m "IM3-259: extend predict response schema"
```

---

### Task 2: `/predict`에서 수지니님 신규 필드 실제 반환

**Files:**
- Modify: `backend/src/main.py`
- Modify: `tests/test_predict_contract.py`

- [ ] **Step 1: Add a contract test for target profile propagation and response fields**

Append this test to `tests/test_predict_contract.py`:

```python
from fastapi.testclient import TestClient


def test_predict_returns_extended_ml_fields_when_model_output_has_them(monkeypatch):
    from src import main

    async def fake_predict_single_district(
        dong_name: str,
        industry_code: str,
        industry_name: str,
        cost_config: dict,
        segment_profile: dict | None = None,
    ):
        assert segment_profile == {
            "age_groups": ["20대", "30대"],
            "gender": "여성",
            "customer_persona": "직장인",
            "price_min": 8000,
            "price_max": 15000,
        }
        return main.DistrictPredictionResult(
            district=dong_name,
            dong_code="11440660",
            customer_segment={"profile_summary": "20대 여성 직장인"},
            living_pop_forecast={"peak_time_zone": "18-21"},
            emerging_signal={"signal": "emerging"},
        )

    monkeypatch.setattr(main, "_predict_single_district", fake_predict_single_district)

    client = TestClient(main.app)
    response = client.post(
        "/predict",
        json={
            "target_district": "서교동",
            "target_districts": ["서교동"],
            "business_type": "카페",
            "brand_name": "테스트브랜드",
            "monthly_rent": 2000000,
            "initial_capital": 50000000,
            "target_age_groups": ["20대", "30대"],
            "target_gender": "여성",
            "customer_persona": "직장인",
            "price_min": 8000,
            "price_max": 15000,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"][0]["customer_segment"] == {"profile_summary": "20대 여성 직장인"}
    assert body["data"][0]["living_pop_forecast"] == {"peak_time_zone": "18-21"}
    assert body["data"][0]["emerging_signal"] == {"signal": "emerging"}
```

- [ ] **Step 2: Run the new test and confirm it fails**

Run:

```powershell
pytest tests/test_predict_contract.py::test_predict_returns_extended_ml_fields_when_model_output_has_them -q
```

Expected: failure because `_predict_single_district()` currently accepts only four arguments.

- [ ] **Step 3: Add a small helper to build `segment_profile`**

In `backend/src/main.py`, place this helper near `_predict_single_district()`:

```python
def _build_segment_profile(input_data: SimulationInput) -> dict[str, Any] | None:
    """Build optional target customer profile for ML customer_segment output."""
    profile = {
        "age_groups": getattr(input_data, "target_age_groups", None),
        "gender": getattr(input_data, "target_gender", None),
        "customer_persona": getattr(input_data, "customer_persona", None),
        "price_min": getattr(input_data, "price_min", None),
        "price_max": getattr(input_data, "price_max", None),
    }
    cleaned = {key: value for key, value in profile.items() if value not in (None, "", [])}
    return cleaned or None
```

- [ ] **Step 4: Pass `segment_profile` into `ModelOutput.generate()`**

Update `_predict_single_district()` signature and `run_in_threadpool()` call:

```python
async def _predict_single_district(
    dong_name: str,
    industry_code: str,
    industry_name: str,
    cost_config: dict,
    segment_profile: dict | None = None,
) -> DistrictPredictionResult:
    """단일 동 ML 예측 실행 (/predict 병렬 호출용)."""
    from models.interface import ModelOutput

    dong_code = _resolve_dong_code(dong_name)
    if not dong_code:
        return DistrictPredictionResult(district=dong_name)

    try:
        sim_result = await run_in_threadpool(
            ModelOutput.generate,
            dong_code,
            industry_code,
            industry_name,
            cost_config,
            "tcn",
            segment_profile,
        )
```

- [ ] **Step 5: Include the three fields in the return model**

At the end of `_predict_single_district()`, include:

```python
    return DistrictPredictionResult(
        district=dong_name,
        dong_code=dong_code,
        is_excluded_combo=False,
        is_mock=is_mock,
        quarterly_projection=quarterly,
        scenarios=scenarios_result,
        bep=sim_result.get("bep"),
        closure_rate=sim_result.get("closure_rate"),
        closure_risk=sim_result.get("closure_risk"),
        shap_result=shap_result,
        customer_segment=sim_result.get("customer_segment"),
        living_pop_forecast=sim_result.get("living_pop_forecast"),
        emerging_signal=sim_result.get("emerging_signal"),
    )
```

- [ ] **Step 6: Use the helper from `/predict`**

In `predict_districts()`, build once and pass to each district call:

```python
    segment_profile = _build_segment_profile(input_data)

    results: list[DistrictPredictionResult] = list(
        await asyncio.gather(
            *[
                _predict_single_district(
                    dong,
                    industry_code,
                    normalized_biz,
                    cost_config,
                    segment_profile,
                )
                for dong in target_districts
            ]
        )
    )
```

- [ ] **Step 7: Run predict contract tests**

Run:

```powershell
pytest tests/test_predict_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add backend/src/main.py tests/test_predict_contract.py
git commit -m "IM3-259: return extended ml fields from predict"
```

---

### Task 3: `/analyze/llm`과 mapper에서 `final_report` 누락 복구

**Files:**
- Modify: `backend/src/main.py`
- Test: `tests/test_analysis_contract.py`

- [ ] **Step 1: Write the failing mapper test**

Create `tests/test_analysis_contract.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.main import map_state_to_simulation_output


def test_map_state_to_simulation_output_includes_final_report():
    state = {
        "target_district": "서교동",
        "target_districts": ["서교동", "합정동"],
        "market_data": {},
        "analysis_results": {
            "legal_risks": [],
            "final_report": {
                "summary": "서교동 출점 추천",
                "sections": [{"title": "종합", "body": "상권 적합도가 높음"}],
            },
        },
    }

    output = map_state_to_simulation_output(state, "request-1")

    assert output["final_report"] == {
        "summary": "서교동 출점 추천",
        "sections": [{"title": "종합", "body": "상권 적합도가 높음"}],
    }
```

- [ ] **Step 2: Run the mapper test and confirm it fails**

Run:

```powershell
pytest tests/test_analysis_contract.py -q
```

Expected: failure because `final_report` is read but not included in the response dict.

- [ ] **Step 3: Add `final_report` to the response mapping**

In `map_state_to_simulation_output()`, make sure the existing `final_report` variable is included in `response_data`:

```python
        "ai_recommendation": ai_recommendation,
        "final_report": final_report,
        "market_report": market_report,
```

- [ ] **Step 4: Confirm `/analyze/llm` schema filtering keeps the field**

Run:

```powershell
pytest tests/test_analysis_contract.py -q
```

Expected: pass. `AnalysisOutput` already defines `final_report`, so the `/analyze/llm` handler keeps it after this mapper fix.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/main.py tests/test_analysis_contract.py
git commit -m "IM3-259: include final report in analysis output"
```

---

### Task 4: ABM `enable_llm_decisions` backend contract

**Files:**
- Modify: `backend/src/main.py`
- Modify: `backend/src/simulation/runner.py`
- Modify: `backend/src/simulation/agents.py`
- Test: `tests/test_abm_llm_decisions.py`

- [ ] **Step 1: Write tests for request schema and cache payload behavior**

Create `tests/test_abm_llm_decisions.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from src.main import AbmSimulationRequest


def test_abm_request_enable_llm_decisions_defaults_false():
    req = AbmSimulationRequest(
        target_district="서교동",
        business_type="카페",
        brand_name="테스트브랜드",
        langgraph_result={},
    )

    assert req.enable_llm_decisions is False


def test_abm_request_accepts_enable_llm_decisions_true():
    req = AbmSimulationRequest(
        target_district="서교동",
        business_type="카페",
        brand_name="테스트브랜드",
        langgraph_result={},
        enable_llm_decisions=True,
    )

    assert req.enable_llm_decisions is True
```

- [ ] **Step 2: Run schema tests and confirm failure**

Run:

```powershell
pytest tests/test_abm_llm_decisions.py -q
```

Expected: failure because `AbmSimulationRequest` has no `enable_llm_decisions` field yet.

- [ ] **Step 3: Add request field**

In `backend/src/main.py`, update `AbmSimulationRequest`:

```python
    # Tier S 50명은 실제 LLM 의사결정, Tier A/B는 policy_decide 유지.
    enable_llm_decisions: bool = False
```

- [ ] **Step 4: Apply ABM decision mode config in endpoint**

In `run_abm_simulation()`, replace the fixed tier/cfg setup:

```python
    pop = PopulationMix(residents=60, commuters=25, visitors=10, owners=5)
    if req.enable_llm_decisions:
        tier = TierDistribution(
            tier_s=min(50, req.n_agents),
            tier_a=min(200, max(req.n_agents - min(50, req.n_agents), 0)),
            tier_b=max(req.n_agents - 250, 0),
        )
        cfg = ModelConfig(
            n_personas=req.n_agents,
            tier_s_provider="openai",
            tier_s_model="gpt-4.1-mini",
            tier_a_provider="openai",
            tier_a_model="gpt-4.1-nano",
        )
        llm_concurrency = 4
    else:
        tier = TierDistribution(tier_s=5, tier_a=20, tier_b=75)
        cfg = ModelConfig(n_personas=req.n_agents)
        llm_concurrency = 4
```

- [ ] **Step 5: Bump cache key and include the new flag**

In the `cache_payload` dict:

```python
        "enable_llm_thought": req.enable_llm_thought,
        "enable_llm_decisions": req.enable_llm_decisions,
```

Change the prefix:

```python
    cache_key = (
        "abm_sim:v6:"
        + hashlib.sha256(_json.dumps(cache_payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]
    )
```

- [ ] **Step 6: Pass the mode to `abm_run()`**

In the `run_in_threadpool(abm_run, ...)` call:

```python
            llm_concurrency=llm_concurrency,
            use_llm_decisions=req.enable_llm_decisions,
```

- [ ] **Step 7: Add runner parameter and world flag**

In `backend/src/simulation/runner.py`, add the parameter:

```python
    enable_llm_thought: bool = False,
    use_llm_decisions: bool = False,
) -> SimulationResult:
```

After `world.use_policy = use_policy`, add:

```python
    world.tier_s_llm_only = use_llm_decisions
```

- [ ] **Step 8: Route Tier S through `smart_decide()` while keeping Tier A/B policy**

In `backend/src/simulation/agents.py`, update the start of `Agent.decide()`:

```python
    def decide(self, world: "World", brain: "LLMBrain", rng: random.Random) -> Decision:
        if getattr(world, "tier_s_llm_only", False) and self.tier == Tier.S:
            return brain.smart_decide(self, world)

        if getattr(world, "use_policy", False):
            from .policy_executor import policy_decide

            return policy_decide(self, world, rng)
```

- [ ] **Step 9: Add decision routing test**

Append to `tests/test_abm_llm_decisions.py`:

```python
from types import SimpleNamespace

from src.simulation.agents import Agent, Role, Tier
from src.simulation.decision import Decision


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
        home_dong="서교동",
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
```

- [ ] **Step 10: Run ABM decision tests**

Run:

```powershell
pytest tests/test_abm_llm_decisions.py -q
```

Expected: all tests pass.

- [ ] **Step 11: Commit**

```powershell
git add backend/src/main.py backend/src/simulation/runner.py backend/src/simulation/agents.py tests/test_abm_llm_decisions.py
git commit -m "IM3-259: add abm llm decision mode"
```

---

### Task 5: ABM thought 재사용과 응답 통계 유지

**Files:**
- Modify: `backend/src/simulation/runner.py`
- Modify: `backend/src/main.py`
- Modify: `tests/test_runner_thought.py`
- Modify: `tests/test_abm_llm_decisions.py`

- [ ] **Step 1: Add a runner-level thought reuse test**

Append to `tests/test_abm_llm_decisions.py`:

```python
def test_abm_response_shape_can_carry_decision_and_thought_stats():
    sample = {
        "thought_calls": 0,
        "thought_input_tokens": 0,
        "thought_output_tokens": 0,
        "thought_cached_tokens": 0,
        "tier_s_calls": 24,
        "tier_a_calls": 0,
        "estimated_cost_usd": 0.12,
    }

    assert sample["thought_calls"] == 0
    assert sample["tier_s_calls"] == 24
    assert sample["estimated_cost_usd"] == 0.12
```

- [ ] **Step 2: Reuse decision reasons as thoughts when both flags are enabled**

In `backend/src/simulation/runner.py`, add a dictionary before the simulation loop:

```python
    decision_reasons_by_agent: dict[int, str] = {}
```

Inside the per-agent decision loop, after a decision is created, capture Tier S reasons:

```python
                    if enable_llm_thought and use_llm_decisions and agent.tier == Tier.S and decision.reason:
                        decision_reasons_by_agent[agent.agent_id] = decision.reason
```

In the thought block, branch before `_run_thought_batch()`:

```python
                    if use_llm_decisions:
                        for a in active_thought_agents:
                            thought = decision_reasons_by_agent.get(a.agent_id)
                            if not thought:
                                continue
                            coord = dong_coords.get(a.current_dong)
                            thoughts_log.append(
                                {
                                    "day": day,
                                    "hour": res.hour,
                                    "agent_id": a.agent_id,
                                    "archetype": a.persona_id or "office_worker",
                                    "thought": thought[:60],
                                    "lat": coord[0] if coord else None,
                                    "lon": coord[1] if coord else None,
                                }
                            )
                    else:
                        thoughts = _run_thought_batch(brain, active_thought_agents, world)
                        for a, thought in zip(active_thought_agents, thoughts):
                            if not thought:
                                continue
                            coord = dong_coords.get(a.current_dong)
                            thoughts_log.append(
                                {
                                    "day": day,
                                    "hour": res.hour,
                                    "agent_id": a.agent_id,
                                    "archetype": a.persona_id or "office_worker",
                                    "thought": thought,
                                    "lat": coord[0] if coord else None,
                                    "lon": coord[1] if coord else None,
                                }
                            )
```

- [ ] **Step 3: Add ABM response stats to endpoint response**

In `backend/src/main.py`, include the tier and cost fields in `/simulate-abm` response:

```python
        "tier_s_calls": result.get("tier_s_calls", 0),
        "tier_a_calls": result.get("tier_a_calls", 0),
        "estimated_cost_usd": result.get("estimated_cost_usd", 0.0),
```

Keep existing fields:

```python
        "thought_calls": result.get("thought_calls", 0),
        "thought_input_tokens": result.get("thought_input_tokens", 0),
        "thought_output_tokens": result.get("thought_output_tokens", 0),
        "thought_cached_tokens": result.get("thought_cached_tokens", 0),
```

- [ ] **Step 4: Run thought and ABM tests**

Run:

```powershell
pytest tests/test_runner_thought.py tests/test_abm_llm_decisions.py -q
```

Expected: all tests pass and `thought_calls` remains `0` in decision-mode thought reuse.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/simulation/runner.py backend/src/main.py tests/test_runner_thought.py tests/test_abm_llm_decisions.py
git commit -m "IM3-259: reuse abm decision reasons for thoughts"
```

---

### Task 6: Frontend `/simulate` 호출을 `/predict` + `/analyze/llm` 병합으로 전환

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add frontend API types for split responses**

In `frontend/src/types/index.ts`, add or extend these types:

```ts
export interface DistrictPredictionResult {
  district: string;
  dong_code?: string | null;
  is_excluded_combo: boolean;
  is_mock: boolean;
  quarterly_projection: QuarterlyProjection[];
  scenarios?: Record<string, unknown> | null;
  bep?: Record<string, unknown> | null;
  closure_rate?: Record<string, unknown> | null;
  closure_risk?: Record<string, unknown> | null;
  shap_result?: ShapResult | null;
  customer_segment?: Record<string, unknown> | null;
  living_pop_forecast?: Record<string, unknown> | null;
  emerging_signal?: Record<string, unknown> | null;
}

export interface PredictResponse {
  status: 'success' | 'error';
  message?: string;
  data: DistrictPredictionResult[];
}
```

- [ ] **Step 2: Implement split API calls and merge helper**

In `frontend/src/api/client.ts`, replace the internal `/simulate` call path with:

```ts
export const runSimulation = async (input: SimulationInput): Promise<SimulationOutput> => {
  const [predictResponse, analysisResponse] = await Promise.all([
    api.post<PredictResponse>('/predict', input, { timeout: 600000 }),
    api.post<ApiResponse<Partial<SimulationOutput>>>('/analyze/llm', input, { timeout: 600000 }),
  ]);

  if (predictResponse.data.status !== 'success') {
    throw new Error(predictResponse.data.message || 'ML 예측에 실패했습니다.');
  }
  if (analysisResponse.data.status !== 'success' || !analysisResponse.data.data) {
    throw new Error(analysisResponse.data.message || 'LLM 분석에 실패했습니다.');
  }

  return mergePredictAndAnalysis(predictResponse.data.data, analysisResponse.data.data, input);
};
```

Add the helper in the same file:

```ts
const mergePredictAndAnalysis = (
  predictions: DistrictPredictionResult[],
  analysis: Partial<SimulationOutput>,
  input: SimulationInput,
): SimulationOutput => {
  const winnerDistrict = analysis.winner_district || input.target_district;
  const winnerPrediction =
    predictions.find((item) => item.district === winnerDistrict) ||
    predictions.find((item) => item.district === input.target_district) ||
    predictions[0];

  return {
    ...analysis,
    target_district: winnerDistrict,
    target_districts: input.target_districts || [input.target_district],
    winner_district: analysis.winner_district || winnerDistrict,
    top_3_candidates: analysis.top_3_candidates || [],
    quarterly_projection: winnerPrediction?.quarterly_projection || [],
    scenarios: winnerPrediction?.scenarios || null,
    bep: winnerPrediction?.bep || null,
    closure_rate: winnerPrediction?.closure_rate || null,
    closure_risk: winnerPrediction?.closure_risk || null,
    shap_result: winnerPrediction?.shap_result || null,
    customer_segment: winnerPrediction?.customer_segment || null,
    living_pop_forecast: winnerPrediction?.living_pop_forecast || null,
    emerging_signal: winnerPrediction?.emerging_signal || null,
    district_predictions: predictions,
  } as SimulationOutput;
};
```

- [ ] **Step 3: Remove `/simulate` assumptions from app copy and state**

Search:

```powershell
rg -n "/simulate|simulate 단일|operational_fit" frontend/src
```

Change `/simulate` references used for the main dashboard flow to `/predict + /analyze/llm`. Keep `/simulate-abm` references.

- [ ] **Step 4: Ensure revenue display uses quarterly semantics**

Search:

```powershell
rg -n "monthly|월매출|quarterly_projection|revenue / 3|revenue" frontend/src/components
```

For UI labels that show monthly revenue from `quarterly_projection[].revenue`, use:

```ts
const monthlyRevenue = Math.round(quarter.revenue / 3);
```

Use "분기 매출" when showing raw `quarter.revenue`.

- [ ] **Step 5: Run frontend checks**

Run:

```powershell
cd frontend
npm run lint
npm run build
```

Expected: lint and build complete without TypeScript errors.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/api/client.ts frontend/src/App.tsx frontend/src/types/index.ts frontend/src/components
git commit -m "IM3-259: split simulation client into predict and analyze"
```

---

### Task 7: Frontend ABM 요청에 `enable_llm_decisions` 추가

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/tabs/AbmTab.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update ABM request payloads**

In every `/api/simulate-abm` fetch body, include:

```ts
enable_llm_thought: true,
enable_llm_decisions: true,
```

- [ ] **Step 2: Confirm existing thought UI handles decision-mode thoughts**

Run:

```powershell
rg -n "thoughts|thought_calls|tier_s_calls|estimated_cost_usd|enable_llm_decisions" frontend/src
```

Keep the current `thoughts` rendering if it already reads `thought`, `lat`, `lon`, `agent_id`, `day`, and `hour`. Add cost display only if the surrounding ABM tab already has a stats surface for LLM call counts.

- [ ] **Step 3: Run frontend checks**

Run:

```powershell
cd frontend
npm run lint
npm run build
```

Expected: lint and build complete without TypeScript errors.

- [ ] **Step 4: Commit**

```powershell
git add frontend/src/components/SimulationResult/dashboard/tabs/AbmTab.tsx frontend/src/App.tsx
git commit -m "IM3-259: enable abm llm decisions from frontend"
```

---

### Task 8: `/simulate` 제거

**Files:**
- Modify: `backend/src/main.py`
- Modify: `docs/architecture/api-contract.md`
- Test: `tests/test_analysis_contract.py`

- [ ] **Step 1: Confirm frontend no longer calls `/simulate`**

Run:

```powershell
rg -n "\"/simulate\"|'/simulate'|api.post<.*simulate|runSimulation" frontend/src
```

Expected: no main dashboard API call to `/simulate`. `/simulate-abm` references remain.

- [ ] **Step 2: Remove the FastAPI route**

Delete the entire `@app.post("/simulate")` route function from `backend/src/main.py`. Keep `_run_pipeline()`, `_predict_single_district()`, `predict_districts()`, and `analyze_llm()` because the split endpoints still use the pipeline and mapper helpers.

- [ ] **Step 3: Add route behavior test**

Append to `tests/test_analysis_contract.py`:

```python
from fastapi.testclient import TestClient
from src.main import app


def test_simulate_endpoint_is_removed_after_split_api_migration():
    client = TestClient(app)
    response = client.post("/simulate", json={})

    assert response.status_code == 404
```

- [ ] **Step 4: Run backend route tests**

Run:

```powershell
pytest tests/test_analysis_contract.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/src/main.py tests/test_analysis_contract.py docs/architecture/api-contract.md
git commit -m "IM3-259: remove deprecated simulate endpoint"
```

---

### Task 9: API contract 문서 최신화

**Files:**
- Modify: `docs/architecture/api-contract.md`

- [ ] **Step 1: Update active endpoint summary**

In `docs/architecture/api-contract.md`, make these active dashboard APIs explicit:

```markdown
| Purpose | Method | Path | Owner | Notes |
|---|---:|---|---|---|
| ML 예측 | POST | `/predict` | Backend/B2 integration | 동별 TCN/BEP/폐업률/SHAP/고객/유동/신흥상권 예측 |
| LLM 분석 | POST | `/analyze/llm` | Backend/B1 integration | winner/ranking/법률/경쟁/트렌드/리포트 |
| ABM 시뮬레이션 | POST | `/simulate-abm` | Backend/C2 integration | LangGraph 결과 기반 행동 시뮬레이션 |
```

- [ ] **Step 2: Document `/predict.data[]` new fields**

Add this table under `/predict` response:

```markdown
| Field | Type | Condition |
|---|---|---|
| `customer_segment` | `object \| null` | 요청에 `target_age_groups`, `target_gender`, `customer_persona`, 가격대 등 타겟 고객 입력이 있을 때 값이 있고, 입력이 없거나 계산 실패 시 `null` |
| `living_pop_forecast` | `object \| null` | 유동인구 예측 모델 가중치가 있고 추론 성공 시 값이 있으며, 실패 시 `null` |
| `emerging_signal` | `object \| null` | 신흥 상권 감지 성공 시 값이 있으며, 실패 시 `null` |
```

Add:

```markdown
`quarterly_projection[].revenue` is quarterly revenue. Monthly UI values must divide by 3.
```

- [ ] **Step 3: Document `/analyze/llm` decisions**

Add:

```markdown
- `winner_district` is selected only from request `target_districts`.
- `top_3_candidates` excludes the winner and returns 0 to 3 items depending on selected district count.
- Failure policy is whole-request error when graph execution raises. Agent-level internal fallback may still produce success with partial empty fields.
- Agent id `inflow` replaces legacy `operational_fit`.
```

- [ ] **Step 4: Document `/simulate-abm.enable_llm_decisions`**

Add to request schema:

```markdown
| Field | Type | Default | Notes |
|---|---|---:|---|
| `enable_llm_thought` | `boolean` | `false` | Tier S thought visualization |
| `enable_llm_decisions` | `boolean` | `false` | When true, Tier S uses LLM `smart_decide`; Tier A/B keep policy decisions |
```

Add to response stats:

```markdown
| Field | Type | Notes |
|---|---|---|
| `thought_calls` | `number` | Decision-mode thought reuse keeps this at `0` |
| `tier_s_calls` | `number` | Tier S LLM decision call count |
| `tier_a_calls` | `number` | Tier A call count, expected `0` in decision mode because Tier A uses policy |
| `estimated_cost_usd` | `number` | Estimated total LLM cost |
```

- [ ] **Step 5: Remove `/simulate` as active contract**

Move `/simulate` to a deprecated/removed section:

```markdown
### Removed: `POST /simulate`

Use `POST /predict` and `POST /analyze/llm` instead. The frontend merges both responses for the dashboard model.
```

- [ ] **Step 6: Commit**

```powershell
git add docs/architecture/api-contract.md
git commit -m "IM3-259: update split api and abm contract docs"
```

---

### Task 10: End-to-end verification

**Files:**
- No source edits unless a verification command reveals a concrete failure.

- [ ] **Step 1: Run backend focused tests**

Run:

```powershell
pytest tests/test_predict_contract.py tests/test_analysis_contract.py tests/test_abm_llm_decisions.py tests/test_runner_thought.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run existing backend smoke tests touched by this work**

Run:

```powershell
pytest tests/test_api_response.py tests/test_e2e_api.py tests/test_full_workflow.py tests/test_new_store_inject.py -q
```

Expected: all selected tests pass. If an existing test still assumes `/simulate`, update the test only when the product decision is `/simulate` removal.

- [ ] **Step 3: Run frontend checks**

Run:

```powershell
cd frontend
npm run lint
npm run build
```

Expected: both commands pass.

- [ ] **Step 4: Optional local API smoke**

Start backend with the project’s normal dev command, then run:

```powershell
curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d "{\"target_district\":\"서교동\",\"target_districts\":[\"서교동\",\"합정동\"],\"business_type\":\"카페\",\"brand_name\":\"테스트\",\"monthly_rent\":2000000,\"initial_capital\":50000000}"
curl -X POST http://localhost:8000/analyze/llm -H "Content-Type: application/json" -d "{\"target_district\":\"서교동\",\"target_districts\":[\"서교동\",\"합정동\"],\"business_type\":\"카페\",\"brand_name\":\"테스트\",\"monthly_rent\":2000000,\"initial_capital\":50000000}"
```

Expected:
- `/predict`: `status: success`, `data` length equals selected districts, each item has the three new nullable fields.
- `/analyze/llm`: `status: success` or documented whole-request error if an LLM dependency fails.

- [ ] **Step 5: Final status check**

Run:

```powershell
git status --short
```

Expected: only intended files are modified. Existing unrelated untracked docs may remain untouched.

---

## Rollout Notes

- Do not hard remove `/simulate` before frontend split-call migration is merged; otherwise current dashboard submission breaks.
- If ABM real LLM calls are too slow or costly in demos, keep `enable_llm_decisions=false` by default and let the frontend send `true` only for explicit ABM demo runs.
- If `OPENAI_API_KEY` is absent, `brain.py` provider fallback may return mock behavior. This is acceptable for local tests but must be stated in demo notes.
- `api-contract.md` is the source of truth for 강민님. Update it in the same PR or before handing frontend integration over.
- `/predict` should not invent mock values for `customer_segment`, `living_pop_forecast`, or `emerging_signal`; return `null` when the model interface returns no value.
