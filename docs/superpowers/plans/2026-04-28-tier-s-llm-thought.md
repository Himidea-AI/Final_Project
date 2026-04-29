# Tier S 50 LLM Thought 적용 Plan

> **사용자 결정**: 5000 agents + Tier S 50명만 LLM (옵션 1, r=0.95 학술 가치 보존).
> dry-run 검증 완료: 50 calls $0.0071, 평균 0.86s, 다양성 issue 발견.

**Goal**: 5000 agents 시뮬에서 Tier S 50명만 LLM thought 생성 → frontend 풍선 + 클릭 페르소나 카드. 학술 검증(Pearson r=0.95) 보존.

**Architecture**: Decision logic은 policy 그대로 → 통계 분포 유지. 별도 thought generator (의사결정과 분리) 매 시간 Tier S 50명 호출. trajectory에 `thoughts` sidecar log → /simulate-abm 응답 → frontend 시각화.

**Tech Stack**: Python (backend brain.py + runner.py), OpenAI gpt-4.1-mini (prompt cache), React (AbmPersonaMap 풍선 + modal).

**예상 비용**: $0.05/시뮬 (cache 활성), Latency +24s (parallel 50 batch).

---

## Task 1: brain.py `generate_thought()` 메서드 추가

**Files**: `backend/src/simulation/brain.py` (수정), `tests/test_brain_thought.py` (신규)

**Step 1**: `generate_thought(agent, world) -> str` 메서드 추가
- input: archetype, hour, weather, mood, hunger
- LLM call (gpt-4.1-mini), cache system prompt
- Fallback: dialog_templates.py sample_dialog
- output: 한국어 ≤ 12자

**Step 2**: 테스트 — mock_mode + 실제 호출 분기

**Step 3**: 회귀 — `tests/` 통과

## Task 2: runner.py thought_log + Tier S 식별

**Files**: `backend/src/simulation/runner.py`

**Step 1**: spawn_agents 결과에서 `tier == Tier.S` 인 agent 50명 (n_agents 비율 X 절대값) 식별
- 5000 scale 시 Tier S 절대수 250 → 첫 50명만 LLM_THOUGHT_ENABLED

**Step 2**: 매 hour 루프에서 50 agent 에 `brain.generate_thought()` 호출 → `thoughts_log` append

**Step 3**: parallel batch 50 (asyncio.gather) — latency 절감

**Step 4**: trajectory_path 시 `thoughts` sidecar dump (chats처럼)

## Task 3: /simulate-abm 응답에 thoughts 필드

**Files**: `backend/src/main.py`

**Step 1**: run_abm_simulation 결과에 `thoughts: List[Dict]` 포함
- {agent_id, hour, day, archetype, thought, lat, lon}

**Step 2**: AbmSimulationRequest에 `enable_llm_thought: bool = True` 옵션

## Task 4: Frontend AbmPersonaMap thoughts 표시 ⚠️ 다른 세션 진행

> 본 plan 은 backend 만 진행. frontend (T4, T5) 는 별도 세션이 동시 작업 중.
> backend API contract: `/simulate-abm` 응답에 `thoughts: List[Dict]` 필드 추가.
> 각 entry: `{day: int, hour: int, agent_id: int, archetype: str, thought: str, lat: float|None, lon: float|None}`

**Files**: `frontend/src/components/AbmPersonaMap.tsx`

**Step 1**: abmResult.thoughts → 시간별 매핑
- 현재 displayHour 와 일치하는 thought 풍선 표시
- 50 dot 위에 12자 풍선 (한 글자 7px × 12 = 84px wide)

**Step 2**: Tier S 50 dot 시각 강조 — 노란 테두리 (다른 4950 dot 대비)

**Step 3**: 풍선 fade in/out (3 tick spawn, 15 tick fade)

## Task 5: 페르소나 카드 (dot 클릭)

**Files**: `frontend/src/components/AbmPersonaMap.tsx`, `frontend/src/components/PersonaCard.tsx` (신규)

**Step 1**: dot click handler 추가 — 좌표 + nearest agent 식별
- canvas click → screen→agent 매핑 (반경 5px 이내)
- only Tier S 50 clickable

**Step 2**: PersonaCard 모달 — archetype, age, dong, 시간별 thought 타임라인, visit count, revenue

**Step 3**: thought timeline (0~23시 그리드 + 풍선)

## Task 6: prompt tuning (다양성)

**Files**: `backend/src/simulation/brain.py`

**Step 1**: temperature 0.8 → 1.2

**Step 2**: prompt에 "직전 출력과 다른 단어 사용" 추가

**Step 3**: 다양성 측정 — 100 sample 중 unique 비율 ≥ 70% 목표

## Task 7: 회귀 테스트 + 문서

**Files**: `tests/test_runner_thought.py`, `docs/abm-simulation/llm-thought.md`

**Step 1**: e2e — 5000 agents × 1day × 50 thought 생성 → 비용 < $0.10

**Step 2**: r=0.95 회귀 — validation/brand_vacancy_validator.py 한 번 더 (Tier S 50 LLM 활성)

**Step 3**: 문서 — 비용/latency/quality 결과 정리

## Risks

| Risk | Mitigation |
|---|---|
| LLM drift → r 하락 | thought 은 의사결정과 분리. Decision은 policy 그대로 → r 보존 |
| OpenAI rate limit | parallel batch 50 + retry exponential backoff |
| 다양성 부족 (dry-run 50% 중복) | Task 6 prompt tuning + temperature 1.2 |
| 실시간 시뮬 latency +24s | progress bar 추가 |
| 5000 dot 중 50개 풍선 인지 어려움 | 노란 테두리 + 풍선 fade 강조 |

## Phase 분할 (smallest increment)

- **Phase 1 (Task 1+2+3)**: backend thought 생성 + 응답 통합 (~3.5h)
- **Phase 2 (Task 4+5)**: frontend 풍선 + 카드 (~3.5h)
- **Phase 3 (Task 6+7)**: tuning + 검증 (~2.5h)

총 예상 9.5시간.
