# ABM 프레임워크 비교 분석 + 우리 코드 도입 계획

작성: A1 (찬영) — 2026-04-21
대상: 마포구 1000명 LLM ABM (`backend/src/simulation/`) 9시간 → 5분 가속

---

## 1. 배경

현재 풀 시뮬(1000명 × 20시간) 기준 약 9시간 소요. 발표 시연용 5분 안쪽 단축을 위해 4개 ABM 프레임워크의 핵심 패턴을 분석하고 우리 코드에 도입할 부분만 추출.

분석 대상:
- **OASIS** (camel-ai/oasis) — LLM 소셜미디어 100만 에이전트
- **Mesa** (projectmesa/mesa) — Python ABM 표준
- **ABIDES** (jpmorganchase/abides-jpmc-public) — 금융 시장 discrete-event
- **CityFlow** (cityflow-project/CityFlow) — 도시 교통 C++ 코어

---

## 2. 통합 비교표

| Framework | 도메인 | 핵심 자산 | 부적합 | 차용 등급 |
|---|---|---|---|---|
| **OASIS** | 소셜미디어 LLM | Channel(asyncio.Queue) + Semaphore + 리플렉션 디스패치 | 액션이 post/like 종속 | **A+** |
| **Mesa** | 범용 ABM | AgentSet.shuffle_do + schedule_event(at=t) + DataCollector | LLM 가속 도구 0, Mesa-LLM은 alpha | **B** |
| **ABIDES** | 금융 시장 | PriorityQueue wakeup + 메시지 기반 상호작용 + latency matrix | 단일 스레드, ms 단위 가정 | **A** |
| **CityFlow** | 도시 교통 | roadnet JSON 스키마 + tick/snapshot API + C++ 코어 | LLM 가정 없음, 물리 연산용 | **C** (스키마만) |

---

## 3. Framework별 핵심 코드 패턴

### 3.1 OASIS — Agent ↔ Platform 분리 (`oasis/social_platform/channel.py`, `platform.py`)

Agent는 상태를 직접 안 건드리고 Channel에 메시지만 던진 뒤 결과 await:

```python
# agent_action.py
async def perform_action(self, message, type):
    msg_id = await self.channel.write_to_receive_queue(
        (self.agent_id, message, type))
    response = await self.channel.read_from_send_queue(msg_id)
    return response[2]
```

Platform은 단일 코루틴이 모든 액션을 직렬 처리 → DB 락 경합 0:

```python
# platform.py
async def running(self):
    while True:
        msg_id, (agent_id, msg, action) = await self.channel.receive_from()
        fn = getattr(self, ActionType(action).value, None)  # 리플렉션 디스패치
        result = await fn(agent_id=agent_id, **params)
        await self.channel.send_to((msg_id, agent_id, result))
```

1000명 동시 실행 (`env.py`):

```python
self.llm_semaphore = asyncio.Semaphore(128)
tasks = [self._perform_llm_action(a) for a in agents]
await asyncio.gather(*tasks)
self.platform.sandbox_clock.time_step += 1
```

### 3.2 Mesa — AgentSet + Discrete Event Scheduler (`mesa/agent.py`, `mesa/model.py`)

신버전(2024+)은 `time.py` 폐기 후 AgentSet + 이벤트 큐로 전환:

```python
class Model:
    def __init__(self, *, rng=None):
        self.agents: AgentSet
        self._event_list: EventList
    def step(self):
        self.agents.shuffle_do("step")  # RandomActivation 대체
    def schedule_event(self, fn, *, at=None, after=None): ...
```

DataCollector로 metrics 자동 집계:

```python
DataCollector(
    model_reporters={"total_revenue": lambda m: sum(s.revenue for s in m.stores)},
    agent_reporters={"spend": "spent_today"},
)
```

### 3.3 ABIDES — PriorityQueue 기반 wakeup (`abides_core/kernel.py`)

```python
while not self.messages.empty() and self.current_time <= self.stop_time:
    self.current_time, event = self.messages.get()
    sender_id, recipient_id, message = event
    # dispatch to agent.receive_message(...)
```

Agent가 미래 시각에 wakeup 예약:

```python
agent.set_wakeup(t=current_time + timedelta(minutes=30))
# → kernel이 30분 뒤 자동 호출
```

1000 agents/1day 금융 시뮬: 약 30초~2분 (latency model on 기준)

### 3.4 CityFlow — C++ 코어 + Python wrapper

```python
eng = cityflow.Engine("config.json", thread_num=8)
for _ in range(3600):
    eng.next_step()
    vehicles = eng.get_vehicles()
```

roadnet JSON 스키마 (intersection + road) — 우리 16개 동 + 인접 그래프 표현에 직접 활용 가능.

---

## 4. 우리 코드 도입 우선순위

### 즉시 (1~2일, 가장 큰 가속)

#### ① OASIS Channel + Semaphore 패턴
- **대상 파일**: `backend/src/simulation/runner.py`, 신규 `channel.py`
- **변경 내용**:
  - 현재: `ThreadPoolExecutor(max_workers=4)` 고정 + RDS 동시쓰기 위험
  - 개선: `asyncio.Semaphore(S=16, A=64, B=128)` + 단일 RDS consumer 코루틴
- **예상 효과**: **3~5배 가속** + RDS 충돌 차단

#### ② ABIDES `set_wakeup(t)` PriorityQueue
- **대상 파일**: 신규 `backend/src/simulation/event_scheduler.py`
- **변경 내용**:
  - 현재: tick polling (모든 에이전트가 매 시간 체크 → 활성화율 50%여도 100% LLM 호출 대기)
  - 개선: 에이전트가 "11:30 visit_store 완료, 다음 결정은 13:00" 같은 이벤트만 큐잉
- **예상 효과**: 실제 LLM 호출 50% → 5%, **10배 가속의 핵심**

### 중기 (1주, 안정성·확장성)

#### ③ OASIS 리플렉션 디스패치
- **대상 파일**: `backend/src/simulation/agents.py`의 `apply()` 분기 제거
- **변경 예시**:
  ```python
  # 현재: if dec.action == "visit": ... elif dec.action == "move": ...
  # 개선: getattr(self, f"_apply_{dec.action}", None)(dec, world)
  ```
- **이점**: 액션 추가 시 switch문 수정 불필요

#### ④ Mesa AgentSet 시그니처
- **대상 파일**: `backend/src/simulation/scheduler.py`
- **변경 예시**:
  ```python
  world.agents.select(lambda a: a.tier == "S").shuffle_do("act")
  ```
- **이점**: Tier 필터링 통일 + 가독성 향상

#### ⑤ Mesa DataCollector 미니 포팅
- **대상 파일**: 신규 `backend/src/simulation/data_collector.py`
- **변경 내용**: `model_reporters / agent_reporters` 시그니처만 차용 → 시뮬 결과 집계 통일

### 미적용 (현재 단계엔 과함)

| 항목 | 이유 |
|---|---|
| **Mesa-LLM** 통째 도입 | alpha 단계, 1000명 검증 사례 없음. 6개월 후 1.0 릴리스·벤치 나오면 재평가 |
| **CityFlow C++ 포팅** | 우리 병목은 LLM이지 물리 연산이 아님. roadnet JSON **스키마만** 차용해 16개 동 + 인접 그래프 정의 |
| **OASIS 통째 채택** | 액션 시스템이 소셜미디어 종속, visit/spend/move 추가가 큰 작업 |

---

## 5. 예상 누적 효과

| 단계 | 1000명 시뮬 시간 | 누적 단축 |
|---|---|---|
| 현재 | 9h | — |
| ① Channel + Semaphore | 2h | 4.5× |
| ② PriorityQueue wakeup | 25min | 22× |
| ③④⑤ + 결정 캐싱 (GPTCache) | 8min | 67× |
| 사전 캐시 hit 시 | 0초 | ∞ |

목표 5분은 ① + ②만으로는 부족하고 ③④⑤ + 캐싱 조합이 필수. 발표용으로는 사전 캐시(`docs/demo-cache-strategy.md`)와 병행.

---

## 6. 구현 로드맵 (제안)

| 일정 | 작업 | 담당 |
|---|---|---|
| Day 1 | `channel.py` 신규 작성 + asyncio Semaphore 도입 | A1 |
| Day 2 | `event_scheduler.py` PriorityQueue wakeup 구현 | A1 |
| Day 3 | runner.py 통합 + 1000명 벤치 측정 | A1 |
| Day 4 | 리플렉션 디스패치 + AgentSet 시그니처 적용 | A1 |
| Day 5 | DataCollector 포팅 + 결정 캐싱(GPTCache) 도입 | A1 |
| Day 6 | 발표용 30개 시나리오 사전 캐시 배치 실행 | A1 |
| Day 7 | 프론트 연동 + 시연 리허설 | B1 + A1 |

---

## 7. 참고 파일 (원본 위치)

### OASIS
- `oasis/social_agent/agent.py:perform_action_by_llm`
- `oasis/social_agent/agent_action.py:perform_action`, `get_openai_function_list`
- `oasis/social_platform/platform.py:running`
- `oasis/social_platform/channel.py`
- `oasis/environment/env.py:step`, `reset`

### Mesa
- `mesa/agent.py` (AgentSet)
- `mesa/model.py` (schedule_event)
- `mesa/discrete_space/`
- 참고: https://github.com/projectmesa/mesa-llm (alpha)

### ABIDES
- `abides-core/abides_core/kernel.py:run`
- `abides-core/abides_core/agent.py:set_wakeup`

### CityFlow
- `src/engine/`, `src/roadnet/` (C++)
- README의 roadnet JSON 스키마 예제

---

## 8. 결정 필요 사항

1. **도입 순서 확정** — ①부터 순차 진행할지, ①+② 병렬 진행할지
2. **벤치마크 기준** — 어느 시점에 "1000명 5분 달성" 측정·검증할지
3. **사전 캐시와의 조합** — Day 6 사전 캐시는 ⑤까지 완료된 시뮬 엔진으로 돌릴지, 현재 엔진으로 돌릴지
