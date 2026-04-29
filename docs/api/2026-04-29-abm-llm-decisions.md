# /simulate-abm — Tier S LLM 의사결정 + Thought Feed 명세서

**작성일**: 2026-04-29
**작성자**: A1 (찬영)
**스코프**: ABM 시뮬레이션 엔드포인트의 LLM 의사결정 모드 도입 + frontend 시각화 변경

---

## 1. 변경 배경

### 1.1 이전 상태
- `/simulate-abm` 의 모든 5,000 agent 가 `policy_decide` (pure Python, deterministic) 로 의사결정
- LLM 호출은 오직 `generate_thought` (Tier S 50명 풍선 텍스트) 만 → 행동에 영향 0
- 결과적으로 Tier S/A/B 라벨이 행동을 분기하지 않음 (시각화 풍선용으로만 활용)
- 사용자 피드백: *"LLM 적용된 애들은 좀 달라야 되는 거 아니야?"*

### 1.2 새 모드 (이번 변경)
- **Tier S 50명 전용 LLM 의사결정** — `smart_decide` (gpt-4.1-mini) 활성
- **Tier A/B** — 기존 `policy_decide` 유지 (deterministic, 비용 0)
- **Thought 풍선** — `generate_thought` 별도 호출 폐지, `smart_decide.reason` 필드 재활용 → LLM 호출 50% 절감
- **Frontend** — 풍선 hover 한 명만 표시, 우측 패널에 시간순 thought feed

---

## 2. Endpoint

### POST `/simulate-abm`

#### 2.1 Request Body — `AbmSimulationRequest`

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `target_district` | `str` | (필수) | 마포 16동 중 1개. 예: `"서교동"` |
| `business_type` | `str` | (필수) | 업종 (cafe/restaurant 등) |
| `brand_name` | `str` | (필수) | 신규 매장 브랜드명 |
| `langgraph_result` | `dict` | (필수) | `/simulate` 응답 — analysis_metrics + market_report 추출용 |
| `n_agents` | `int` | `100` | 5000 권장 |
| `days` | `int` | `1` | 시뮬 일수 |
| `scenario` | `AbmScenarioParams` | `{}` | weather/date/weekend/rent_shock |
| `spot_lat` | `float \| None` | `None` | 공실 스팟 클릭 좌표 |
| `spot_lon` | `float \| None` | `None` | |
| `store_area` | `float` | `15.0` | 신규 매장 평수 → seats=평×2 |
| **`enable_llm_thought`** | `bool` | `False` | Tier S 풍선 텍스트 활성 |
| **`enable_llm_decisions`** | `bool` | `False` | **NEW**: Tier S LLM 의사결정 활성 |

#### 2.2 enable_llm_decisions 동작

`True` 시:
- `TierDistribution(tier_s=50, tier_a=200, tier_b=n_agents-250)` 강제 (auto-scale 우회)
- `world.tier_s_llm_only = True` 플래그 설정 → `agents.py:decide()` 가 Tier S 만 `smart_decide` 라우팅
- `cfg.tier_s_provider="openai"`, `cfg.tier_s_model="gpt-4.1-mini"`, `cfg.tier_a_*` 동일
- `llm_concurrency=4` (OpenAI 500 RPM 보호)

`False` 시 (기본):
- `TierDistribution(5, 20, 75)` 비율 → runner.py 가 n_personas 기준 비례 scale
- 모든 Tier 가 `policy_decide` (pure Python, LLM 0회)

---

## 3. Response Schema

### 3.1 주요 필드

```json
{
  "request_id": "abm_20260429_xxx",
  "target_district": "서교동",
  "n_personas": 5000,
  "daily_visits_mean": 1234,
  "daily_visits_std": 45.2,
  "monthly_revenue_estimate": 81234567,
  "new_store_visits": 32,
  "new_store_revenue": 482000,
  "new_store_visit_share_pct": 2.6,
  "narrator_summary": "서교동 상권 기준...",

  "trajectory": [
    { "agent_id": 42, "day": 1, "hour": 12, "dong": "서교동",
      "action": "visit", "tier": "S", "role": "resident",
      "lat": 37.557, "lon": 126.923 }
  ],

  "density_grid": {
    "bbox": [37.524, 126.858, 37.590, 126.967],
    "cols": 128, "rows": 96,
    "hours": { "30": [0, 0, 5, 12, ...], "31": [...] },
    "max_count": 47
  },

  "thoughts": [
    { "day": 1, "hour": 12, "agent_id": 42,
      "archetype": "office_worker",
      "thought": "비빔밥 먹고 싶지만 예산이 부족해서 편의점에서 김밥 사먹어야지",
      "lat": 37.557, "lon": 126.923 }
  ],

  "thought_calls": 0,
  "thought_input_tokens": 0,
  "thought_output_tokens": 0,
  "thought_cached_tokens": 0,

  "tier_s_calls": 487,
  "tier_a_calls": 0,
  "estimated_cost_usd": 0.32,

  "cached": false
}
```

### 3.2 thoughts 배열 동작 변화

| 모드 | thoughts 출처 | 텍스트 길이 |
|------|------------|-----------|
| `enable_llm_thought=False` | (빈 배열) | — |
| `enable_llm_thought=True`, `enable_llm_decisions=False` | `generate_thought` 별도 LLM 호출 | 12자 (system prompt 강제) |
| **`enable_llm_thought=True`, `enable_llm_decisions=True`** | **`smart_decide.reason` 재활용 (LLM 추가 호출 0)** | **최대 60자** |

`thought_calls` / `thought_*_tokens` 는 `enable_llm_decisions=True` 시 0 (smart_decide 호출은 `tier_s_calls` 에 카운트).

---

## 4. 의사결정 라우팅 — 코드 위치

### 4.1 `agents.py:221-237`
```python
def decide(self, world, brain, rng) -> Decision:
    # NEW: Tier S 만 LLM 모드
    if getattr(world, "tier_s_llm_only", False) and self.tier == Tier.S:
        return brain.smart_decide(self, world)

    # 기존 — Tier A/B 가 그대로 policy 로 빠짐
    if getattr(world, "use_policy", False):
        return policy_decide(self, world, rng)

    # 기존 풀 LLM 모드 (use_policy=False 시)
    if self.tier == Tier.B: return self._rule_decide(world, rng)
    if self.tier == Tier.A: return brain.fast_decide(self, world)
    return brain.smart_decide(self, world)
```

### 4.2 `runner.py:440-450`
```python
# n_personas 기반 auto-enable
use_policy = True

# enable_llm_decisions 시 Tier S LLM 활성 플래그 (use_policy 는 그대로 True)
world.tier_s_llm_only = use_llm_decisions
```

### 4.3 `runner.py:990-1015` — thought_log 수집
```python
if enable_llm_thought and thought_agents and not is_warmup:
    if use_llm_decisions:
        # smart_decide.reason 재활용 (별도 LLM 호출 X)
        for aid, dec in res.decisions:
            if aid in _thought_agent_ids and dec.reason:
                thoughts_log.append({..., "thought": dec.reason[:60], ...})
    else:
        # 기존 — generate_thought 별도 호출
        thoughts = _run_thought_batch(brain, active_thought_agents, world)
```

---

## 5. Rate Limit 처리

### 5.1 OpenAI Tier 1 한도
- gpt-4.1-mini: **500 RPM**
- 동시 호출: smart_decide(ThreadPool 4) + thought batch(asyncio.Semaphore 4) = 합산 8 concurrent
- 평균 RPM: ~320 (한도 내)

### 5.2 429 자동 재시도
**`brain.py:_smart_decide_openai`**:
```python
delay = 0.5
for attempt in range(3):
    try:
        resp = self._openai.chat.completions.create(...)
        return self._parse_decision(text, agent, world)
    except Exception as e:
        if "429" in str(e) and attempt < 2:
            time.sleep(delay)
            delay *= 2  # 0.5s → 1s → 2s
            continue
        return self._mock_decide(...)  # fallback
```

### 5.3 Thought 배치 동시성 제한
**`runner.py:_batch_generate_thoughts`**:
```python
sem = asyncio.Semaphore(4)
async def _bounded(a):
    async with sem:
        return await _generate_thought_with_retry(brain, a, world)
```

---

## 6. 비용 / 시간 추정

### 6.1 LLM 호출 통계 (5000 agents, days=1)

| 모드 | smart_decide | thought | 총 LLM | 비용 | 시간 |
|------|-------------|---------|--------|------|------|
| Off (기본) | 0 | 0 | 0 | $0 | ~30~60s |
| Thought only | 0 | ~1,000 | 1,000 | ~$0.05 | ~60~90s |
| Decisions only | ~500 | 0 | 500 | ~$0.25 | ~90~150s |
| **Decisions + Thought** | ~500 | 0 (재활용) | **500** | **~$0.25~0.35** | **~120~180s** |
| Decisions + Thought (이전 — 중복 호출) | ~500 | ~1,000 | 1,500 | ~$0.50~0.70 | ~240~360s |

**현재 권장**: `enable_llm_decisions=True` + `enable_llm_thought=True` (둘 다 켜도 LLM 호출은 1set, reason 재활용으로 비용 절반).

### 6.2 활성률 (`is_active` 필터)

`scheduler.py:48-58`:
- `hour < 7 or >= 25`: 5% 활성
- `hour in (8, 12, 13, 18, 19, 20, 21)`: 100% 활성
- 기타: 30% 활성

→ 평균 활성률 ~50%. Tier S 50명 × 20h × 0.5 ≈ 500 calls/sim.

---

## 7. Caching

### 7.1 Redis 키 버전 이력

| 버전 | 도입일 | 변경 사항 |
|------|-------|----------|
| `abm_sim:v2:` | 2026-04-28 | `collect_trajectory=True` 회귀 fix + `thoughts` 필드 |
| `abm_sim:v3:` | 2026-04-28 | 신규 매장 `popularity_boost=5.0` (visits=0 회귀 fix) |
| `abm_sim:v4:` | 2026-04-29 | `use_llm_decisions` 도입 |
| `abm_sim:v5:` | 2026-04-29 | 전 Tier OpenAI gpt-4.1-mini 통일 |
| **`abm_sim:v6:`** | **2026-04-29** | **Tier S 50 전용 LLM (Tier A/B → policy)** |

### 7.2 cache_payload 구성
```python
{
  "district": req.target_district,
  "category": req.business_type,
  "brand": req.brand_name,
  "n_agents": req.n_agents,
  "days": req.days,
  "spot_lat": req.spot_lat,
  "spot_lon": req.spot_lon,
  "weather": req.scenario.weather_override,
  "date": req.scenario.date_override,
  "weekend": req.scenario.weekend_force,
  "rent_shock": req.scenario.rent_shock_pct,
  "enable_llm_thought": req.enable_llm_thought,
  "enable_llm_decisions": req.enable_llm_decisions,  # NEW
}
```
SHA256 해시 32자 + 버전 prefix.

---

## 8. Frontend 사용

### 8.1 호출 위치 (3곳)
- `frontend/src/components/SimulationResult/dashboard/tabs/AbmTab.tsx:108`
- `frontend/src/App.tsx:3816, 3903, 3949`

### 8.2 기본 body
```ts
{
  target_district: targetDistrict,
  business_type: businessType ?? 'cafe',
  brand_name: brandName,
  langgraph_result: simResult,
  n_agents: 5000,
  days: 1,
  spot_lat, spot_lon,
  scenario: { weather_override, date_override, weekend_force, rent_shock_pct },
  store_area: storeArea,
  enable_llm_thought: true,    // 풍선 표시
  enable_llm_decisions: true,  // Tier S 50 LLM 의사결정
}
```

### 8.3 시각화 (`AbmPersonaMap.tsx`)

#### 풍선 (hover 한 명만)
- `hoveredTierSAgentRef` — mousemove 마다 Tier S dot hit-test (R²=14²)
- 50개 동시 풍선 → 마우스 올린 1명만 (지도 클러터 방지)
- 텍스트 30자 cap + ellipsis

#### Thought Feed Panel (우측, `AbmPersonaMap.tsx:2569-2638`)
- 시간순 ASC 스크롤 (max-h 280px)
- 각 행: hour, agent#, thought, archetype
- 클릭 → PersonaCard 모달 (해당 agent 의 하루 timeline)

#### Pan/Zoom 끊김 해결 (`AbmPersonaMap.tsx:1303-1370`)
- **A. CSS Transform**: drag 중 캔버스 frozen + `translate3d(dx, dy, 0)` 로 추종
- **B. Hex Cache**: `hexLatLngCacheRef = Map<zoomLevel, hexes[]>` — pointInPolygon 7M 연산 amortize
- 효과: dragstart ~50ms → <1ms, dragend ~120ms → 5ms

---

## 9. 회귀 / 알려진 한계

### 9.1 회귀 가능
- ❌ **시뮬 결과 수치 (visits/revenue/cannibalization)**: enable_llm_decisions=True 시 Tier S 50명만 LLM → 통계적 영향 미미하지만 ±5% 범위 변동 가능 (deterministic 보장 X)
- ❌ **재현성**: LLM 응답 비결정적 → seed 같아도 결과 다를 수 있음

### 9.2 한계
- Pan 중 hover hit-test 부정확 (canvas frozen, mouse 좌표 신선 → 미스매치). drag 끝나면 정상.
- Zoom 은 여전히 freeze (비선형 재투영 필요, transform 부적합).
- OpenAI Tier 1 (500 RPM) 가정. Tier 2 이상이면 `llm_concurrency=16` 으로 상향 가능.

---

## 10. 관련 코드 위치

| 변경 | 파일 | 라인 |
|------|------|------|
| Request schema | `backend/src/main.py` | 1462-1466 |
| Endpoint 분기 | `backend/src/main.py` | 1525-1565 |
| Tier 분배 강제 | `backend/src/main.py` | 1531-1546 |
| `use_llm_decisions` param | `backend/src/simulation/runner.py` | 397 |
| `world.tier_s_llm_only` 설정 | `backend/src/simulation/runner.py` | 460 |
| `agents.py` 라우터 | `backend/src/simulation/agents.py` | 221-237 |
| 429 재시도 | `backend/src/simulation/brain.py` | 267-310 |
| Thought batch semaphore | `backend/src/simulation/runner.py` | 245-260 |
| Thought reason 재활용 | `backend/src/simulation/runner.py` | 990-1015 |
| Frontend hover bubble | `frontend/src/components/AbmPersonaMap.tsx` | 1817-1860 |
| Frontend feed panel | `frontend/src/components/AbmPersonaMap.tsx` | 2569-2638 |
| Pan CSS transform | `frontend/src/components/AbmPersonaMap.tsx` | 1303-1370 |
| Hex cache | `frontend/src/components/AbmPersonaMap.tsx` | 815-885 |

---

## 11. 마이그레이션 노트

### 기존 클라이언트 (호환성)
- `enable_llm_decisions` 미전송 시 기본 `False` → 기존 동작 그대로
- `enable_llm_thought` 미전송 시 기본 `False` → 기존 동작 그대로
- 응답 schema 추가만 (필드 제거 X) → 기존 파서 영향 없음
- cache_key v5 → v6 자동 무효화 (기존 캐시 1회 miss 후 정상)

### 환경 변수
- `OPENAI_API_KEY` 필수 (없으면 `_auto_downgrade` → mock fallback, 시뮬 동작은 OK 단 LLM thought/decision 효과 없음)
- `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` 더 이상 사용 X (전 Tier OpenAI 통일)
