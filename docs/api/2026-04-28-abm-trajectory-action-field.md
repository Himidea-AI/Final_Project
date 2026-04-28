# ABM trajectory.action 필드 추가 + Tier S thought_agents trajectory 강제 포함 (frontend → backend handoff)

> **수신**: backend Tier S thought 작업 세션 (plan: `docs/superpowers/plans/2026-04-28-tier-s-llm-thought.md`)
> **발신**: frontend 시각화 세션 (이 문서)
> **날짜**: 2026-04-28
> **우선순위**: P1 — Tier S thought 풍선과 dot 시각이 실제 행동과 일치하려면 필요

## 🟢 적용 상태 (2026-04-28 17:00 KST 기준)

| 항목 | 상태 | 위치 |
|---|---|---|
| `Decision.action` enum (visit/work/rest/move/leave) | ✅ 기구현 | `agents.py:84` |
| `Agent.current_action` 필드 + Decision 적용 시 update | ✅ 기구현 | `agents.py:111,448` |
| `trajectory[i].action` 응답 포함 | ✅ 기구현 | `runner.py:849` |
| `_trajectory_sample_ids` 에 thought_agents union | ✅ **이 세션 적용** | `runner.py:633-634` |
| Frontend rest/visit/work/move 4종 분기 렌더 | ✅ 적용 | `AbmPersonaMap.tsx:1198-1247` |
| Frontend `"leave"` → 'move' 와 동일 처리 (default else) | ✅ 자동 | (분기 없음 = move) |

**남은 작업 없음.** 이 문서는 적용 완료 기록으로 보존.

---

## ⚠️ 핵심 버그 (먼저 처리) — Tier S 50명 중 ~5명만 풍선 보임

**증상**: 사용자 시연 시 Tier S 50명 thought 생성됐는데 실제 풍선 5개 정도만 보임.

**원인**: trajectory 샘플과 thought 대상이 **별개 집합**이라 교집합이 적음.

`runner.py:581-587` (현재 코드)
```python
_trajectory_sample_ids = {a.agent_id for a in _r.sample(agents, sample_n)}
```
→ 5000명 중 **무작위 300명** 샘플링.

`runner.py:617`
```python
thought_agents = _select_thought_agents(agents, n=50)
```
→ Tier S 250명 중 non-ext 우선 **50명** (다른 기준).

기댓값: 250 × 300/5000 = **15명** 만 trajectory 에 들어감.
그중 active_thought_agents (외부 필터) 통과: ~10명.
그중 현재 displayHour 일치: ~3-7명. → **사용자 시각 5개**.

### 수정 요청

`runner.py:581-587` trajectory 샘플링 로직을 **thought_agents union** 으로:

```python
_trajectory_sample_ids: set[int] = set()
if collect_trajectory and agents:
    import random as _sample_rng
    _r = _sample_rng.Random(seed)
    sample_n = min(trajectory_sample_size, len(agents))
    _trajectory_sample_ids = {a.agent_id for a in _r.sample(agents, sample_n)}

# ⚠️ thought 대상은 항상 trajectory 에 포함 — 풍선/PersonaCard 가시성 필수
if enable_llm_thought and thought_agents:
    _trajectory_sample_ids |= {a.agent_id for a in thought_agents}
```

영향:
- payload 크기: 50 × 16h × ~50bytes = **+40 KB** (gzip 후 ~5KB), 무시 가능
- 통계 분석 (agent 분포 추정 등): random sample 300 + 추가 50 (Tier S non-ext 편향) → 분석 시 분리해 사용 권장
- 회귀 위험: 거의 없음. trajectory 가 "최소 N 개" 라는 제약만 깨지지 않으면 됨.

### 검증

```bash
curl -X POST http://localhost:8000/simulate-abm -d '{...,"enable_llm_thought":true,"n_agents":5000}' \
  | jq '[.trajectory[].agent_id] | unique | length'
# 기대: 300~350 (300 random + 50 thought, 일부 중복 허용)

curl ... | jq '[.thoughts[].agent_id] | unique | length'
# 기대: 50

curl ... | jq '[.trajectory[].agent_id] | unique | tostring' \
  | python -c "import sys,json; t=set(json.loads(sys.stdin.read()))" 그리고
curl ... | jq '[.thoughts[].agent_id] | unique' 
# thought 의 agent_id 가 trajectory agent_id 집합의 부분집합이어야 함 (subset).
```

---

## 배경

현재 `/simulate-abm` 응답의 `trajectory[]` entry 는 다음 필드만 포함:

```json
{ "day": 0, "hour": 14, "agent_id": 4123, "lat": 37.55, "lon": 126.91, "role": "resident" }
```

프런트는 hour 별 lat/lon 만 받아서 dot 을 보간 렌더하는데, **agent 가 지금 뭐 하는지(쉬는지·매장 방문인지·근무인지·이동 중인지) 알 수 없어** 모든 dot 을 똑같이 그립니다. 결과적으로 — 같은 lat/lon 에 머무르는 agent 도 wandering dot 으로 보이고, 매장 방문 순간이 시각적으로 강조되지 않습니다.

사용자 피드백:
> "한 에이전트가 다른 두 가게 사이만 왔다갔다 하는 게 아니라 그 근처의 가게를 방문하든 집에서 쉬든 이런 것을 표현하고 싶다"

## 요청 contract

`trajectory[]` 의 각 entry 에 `action` 필드 추가:

```python
# Pydantic 응답 스키마 / dict literal
{
    "day": 0,
    "hour": 14,
    "agent_id": 4123,
    "lat": 37.5512,
    "lon": 126.9087,
    "role": "resident",
    "action": "rest",  # ← 신규
}
```

### 허용 값 (4종)

| 값 | 의미 | 위치 일반적 패턴 |
|---|---|---|
| `"rest"` | 집·숙소·공원에서 휴식 | home dong centroid 근처 |
| `"visit"` | 매장 방문 (결제 가능) | 특정 store lat/lon |
| `"work"` | 근무 중 | 직장 dong centroid |
| `"move"` | 이동 중 | 두 지점 사이 어딘가 |

값은 lowercase, 위 4개 중 하나. 알 수 없으면 `"move"` (default 호환).

### 빈 값 / 누락

- 필드 누락 → 프런트가 `'move'` 로 fallback (현재 코드 적용 완료, AbmPersonaMap.tsx:474)
- `null` 도 OK (frontend `String(null) === 'null'` 이 되니 명시적 `"move"` 권장)

## 권장 구현 위치

### 1. `backend/src/simulation/runner.py` — trajectory append 시 action 추출

trajectory list 에 entry append 하는 곳(`_dump_trajectory` 또는 hour 루프 내) 에서 agent.current_action 또는 동등한 상태값 가져와서 함께 넣기:

```python
# runner.py 의 trajectory append 패턴 (예시 — 실제 위치는 line ~610-700 부근)
trajectory.append({
    "day": d,
    "hour": h,
    "agent_id": a.agent_id,
    "lat": pos[0],
    "lon": pos[1],
    "role": a.persona_role,
    "action": _classify_action(a),  # ← 추가
})
```

### 2. `_classify_action(agent)` 헬퍼 신설

agent 의 현재 상태(visiting_store / at_home / commuting / working) 를 기존 결정 로직에서 추출. 이미 hour 루프에서 `agent.choose_action()` 같은 의사결정이 있을 텐데, 그 결과를 `agent.current_action: str` 으로 저장만 하면 됩니다.

```python
def _classify_action(a: Agent) -> str:
    if a.visiting_store_id:        # 매장 좌표에 있으면
        return "visit"
    if a.at_workplace:             # 직장 dong 에 있고 work 시간대
        return "work"
    if a.is_moving or a.in_transit:
        return "move"
    return "rest"                  # 집에 있거나 활동 없음
```

(실제 필드명은 기존 Agent dataclass 에 따라 조정)

### 3. archetype 기반 자연스러운 분포 보장

이미 `archetypes.py` 의 30종 (homebody / trendy_local / night_owl / fitness …) 이 visit_probability·mobility 등으로 행동 차이를 만드므로, action 분류만 정확하면 자동으로 다양해짐. 추가 randomization 불필요.

예상 hour 14:00 분포:
- homebody: 85% rest, 10% visit, 5% move
- trendy_local: 30% rest, 50% visit, 20% move
- commuter (workday): 10% rest, 5% visit, 70% work, 15% move
- night_owl: 90% rest (아직 자거나), 10% move

## 응답 크기 영향

trajectory_sample_size = 300, days=1, 16시간 = 4800 entries.

`"action": "rest"` 추가 시 약 16 bytes/entry × 4800 = **+76 KB**. gzip 후 무시 가능 (~5 KB).

## 캐시 영향

`backend/src/main.py:1300` cache_key prefix 가 이미 `abm_sim:v2:` 로 bumped (2026-04-28 이전 fix). action 필드 추가 시 schema 변경이지만, 같은 v2 prefix 안에서 backward-compatible (없어도 frontend 동작) 이라 추가 bump 불필요.

만약 strict 하게 schema 분리 원하면 `abm_sim:v3:` 로 bump 권장.

## 테스트 방법

backend 적용 후 다음 curl 한 번:

```bash
curl -X POST http://localhost:8000/simulate-abm \
  -H "Content-Type: application/json" \
  -d '{
    "target_district": "서교동",
    "business_type": "cafe",
    "brand_name": "test",
    "langgraph_result": {},
    "n_agents": 5000,
    "days": 1,
    "scenario": {"weather_override": null, "weekend_force": false, "rent_shock_pct": 0},
    "enable_llm_thought": true
  }' | jq '.trajectory[0:5]'
```

기대 출력:
```json
[
  { "day": 0, "hour": 6, "agent_id": 12, "lat": 37.55, "lon": 126.91,
    "role": "resident", "action": "rest" },
  { "day": 0, "hour": 7, "agent_id": 12, "lat": 37.55, "lon": 126.91,
    "role": "resident", "action": "rest" },
  ...
]
```

## frontend 측 적용 상태 (이 세션 기완료)

✅ `AbmPersonaMap.tsx:393-401` trajectoryPathsRef 타입에 `action: string` 포함
✅ `:466-481` 파싱 시 `e.action || 'move'` 추출
✅ `:1186-1247` 렌더 분기:
  - `rest` → 회색 dim, drift 거의 정지 (5%)
  - `visit` → 빨강 펄스 dot (1.6× 크기, sin 펄스)
  - `work` → 초록 정적, drift 8%
  - `move` → role 색 + 풀 wandering drift (100%)

backend 가 action 필드 안 보내도 모두 `'move'` 로 떨어지므로 **breaking change 없음**.

## 사용자 가시 효과

- homebody agent 가 하루 종일 집에 있으면 → 회색 dim dot 이 home 위치에 머무름 (현재: 다른 dot 처럼 wandering)
- 점심시간에 한두 명이 카페로 visit → 빨간 펄스 dot 이 매장에서 펄스 (현재: 평범한 wandering dot)
- 5000명 시뮬에 "이 시각엔 사람들 대부분이 일하고 있고, 일부는 점심 먹으러 카페에 갔구나" 가 시각적으로 보임

Tier S 50명의 thought ("점심 먹으러 카페") 와 dot 행동 (빨강 펄스 + 카페 좌표) 이 일치 → 신뢰감 ↑.

## 작업 분량 추정

| 단계 | 시간 |
|---|---|
| Agent dataclass 에 `current_action: str` 필드 추가 | 5분 |
| 결정 로직에서 action 설정 (이미 분기 있을 곳에 한 줄씩 set) | 20분 |
| trajectory append 시 action 포함 | 5분 |
| 회귀 테스트 (`tests/test_runner_thought.py` 같은 기존 테스트) 통과 확인 | 15분 |
| **총** | **~45분** |

## 참고 — frontend 가 미응답 처리하는 방식

```ts
// AbmPersonaMap.tsx:478
action: String(e.action || 'move'),
```

`undefined` / `null` / `""` 모두 `'move'` 로 떨어짐. 따라서 backend 우선순위 낮으면 일단 응답 schema 만 추가하고 default `"move"` 로 보내도 OK (frontend 가 알아서 wandering 모드로 표시).

다만 `"visit"` 만이라도 정확히 분류되면 시각적 효과가 큽니다 (매장 펄스). 단계적 적용 시:

1. **Phase 1 (15분)**: `"visit"` 만 정확히 — 나머지는 `"move"` default. 즉시 매장 visit 강조 OK.
2. **Phase 2 (30분)**: `"rest"` / `"work"` / `"move"` 모두 분류. 정확한 행동 시각화.
