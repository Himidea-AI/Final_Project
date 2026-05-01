# /simulate-abm — LLM Thought 응답 필드 추가

작성: A1 (찬영) — 2026-04-28
Branch: IM3-243-dong-fk-followup
Endpoint: `POST /simulate-abm`
Tag: `abm-simulation`

---

## 0. 변경 요약

기존 `/simulate-abm` 응답에 **Tier S 50 LLM thought** (시각화용 내적 독백) 5개 필드를 추가했다. 회귀 호환성을 위해 default off 로 동작하며, frontend 가 명시적으로 `enable_llm_thought=true` 를 보낼 때만 LLM 호출이 발생한다.

| 항목 | 변경 |
|---|---|
| Request body | `enable_llm_thought: bool = False` 신규 필드 |
| Response body | `thoughts`, `thought_calls`, `thought_input_tokens`, `thought_output_tokens`, `thought_cached_tokens` 5개 필드 추가 |
| Default | `enable_llm_thought=False` (기존 호출자 회귀 X) |
| 비용 추정 | 5000 agents × 1 day × Tier S 50 ≈ **$0.05/시뮬** (cache 활성, Haiku 기준) |

## 1. Request

### 1.1 추가 필드

```typescript
{
  // ... 기존 필드 (target_district, business_type, brand_name, langgraph_result,
  //                  n_agents, days, scenario, spot_lat, spot_lon) ...

  enable_llm_thought?: boolean;  // default false
}
```

| 필드 | 타입 | default | 설명 |
|---|---|---|---|
| `enable_llm_thought` | `boolean` | `false` | Tier S 상위 5% 에이전트의 시간대별 LLM 내적 독백 생성 여부. **true 시 LLM 비용 발생** — demo / 시각화 시나리오에서만 켜라. 기본 5000 시뮬레이션은 false 유지 권장. |

### 1.2 예시

```json
{
  "target_district": "공덕동",
  "business_type": "카페",
  "brand_name": "스모크 테스트",
  "langgraph_result": { /* LangGraph 5 에이전트 분석 결과 */ },
  "n_agents": 5000,
  "days": 1,
  "enable_llm_thought": true
}
```

## 2. Response

### 2.1 추가 필드 schema

```typescript
{
  // ... 기존 필드 (status, target_district, n_personas, daily_visits_mean,
  //                  trajectory, dong_totals, ...) ...

  thoughts: ThoughtEntry[];        // enable_llm_thought=false 면 [] (빈 배열)
  thought_calls: number;           // LLM 호출 횟수 (배치 단위)
  thought_input_tokens: number;    // 누적 input 토큰
  thought_output_tokens: number;   // 누적 output 토큰
  thought_cached_tokens: number;   // 누적 cache hit 토큰 (비용 절감 측정용)
}

interface ThoughtEntry {
  day: number;          // 시뮬 day index (1-based)
  hour: number;         // 시뮬 시간 (0~23, 방금 진행한 hour)
  agent_id: string;     // 에이전트 식별자
  archetype: string;    // persona_id (예: "office_worker", "univ_student")
  thought: string;      // LLM 생성 1~2문장 한국어 내적 독백
  lat: number | null;   // 에이전트가 위치한 동의 centroid 위도
  lon: number | null;   // 에이전트가 위치한 동의 centroid 경도
}
```

### 2.2 thoughts 항목 예시

```json
{
  "day": 1,
  "hour": 12,
  "agent_id": "agent_2031",
  "archetype": "office_worker",
  "thought": "점심에 합정 카페에서 아메리카노 마시고 싶다. 새 매장 확인해봐야지.",
  "lat": 37.5495,
  "lon": 126.9136
}
```

### 2.3 응답 동작

| 시나리오 | `thoughts` | `thought_calls` |
|---|---|---|
| `enable_llm_thought=false` (default) | `[]` | `0` |
| `enable_llm_thought=true`, 1 day, n_agents=5000 | 약 **1,200 entries** (Tier S 50 × 24 h) | 24 (시간당 1 batch) |
| `enable_llm_thought=true`, 1 day, n_agents=100 | 약 **120 entries** (Tier S 5 × 24 h) | 24 |

## 3. 비용 / 성능 가이드

### 3.1 비용

- Tier S 모델: Anthropic `claude-haiku-4` (또는 ANTHROPIC 키 부재 시 OpenAI gpt-4o-mini 자동 fallback)
- 1 thought ≈ 80 input tokens (memory + world state) + 40 output tokens
- prompt cache 활성 (system / world state 부분 재사용) → cached_tokens 비율 80%+
- **5000 agents × 1 day × Tier S 5%**: ~1,200 thoughts ≈ **$0.05** (cache 활성 기준)
- cache 비활성 worst case: ~$0.20

### 3.2 캐시

- Redis `abm_sim:*` 캐시 키에 `enable_llm_thought` 포함 → true/false 분리 캐싱
- TTL 1시간: 같은 spot/시나리오/`enable_llm_thought` 조합은 즉시 반환 (LLM 재호출 X)
- 캐시 본문에 `thoughts` 포함 (trajectory 만 제외)

### 3.3 frontend 사용 권장 패턴

1. **default UX**: `enable_llm_thought=false` 로 호출 → 5000 agents 빠르게 처리, thought 풍선 X
2. **demo / "AI 생각 보기" 버튼**: `enable_llm_thought=true` 로 재호출 → thoughts 풍선 시각화 활성
3. 같은 시나리오는 Redis 캐시로 재사용 (TTL 1시간)

## 4. 회귀 안전성

기존 frontend 호출 (n_agents=5000, `enable_llm_thought` 미지정):

- Pydantic default `False` 적용 → `enable_llm_thought=False`
- runner.run_simulation 내부 `if enable_llm_thought:` 분기로 LLM 호출 skip
- 응답에 `thoughts: []`, `thought_calls: 0` 포함 (필드 추가만, 기존 필드 변경 없음)
- → 비용 변동 X, 성능 회귀 X

## 5. 관련 파일

| 파일 | 변경 |
|---|---|
| `backend/src/main.py:1218` | `AbmSimulationRequest.enable_llm_thought: bool = False` 추가 |
| `backend/src/main.py:1296` | 캐시 키에 `enable_llm_thought` 포함 |
| `backend/src/main.py:1327` | `abm_run(..., enable_llm_thought=req.enable_llm_thought)` 전달 |
| `backend/src/main.py:1390-1395` | response dict 에 thoughts/thought_calls/... 5개 추가 |
| `backend/src/simulation/runner.py:313` | `SimulationResult.thoughts: list` 필드 추가 |
| `backend/src/simulation/runner.py:1045` | `SimulationResult(thoughts=thoughts_log if enable_llm_thought else [], ...)` 전달 |
