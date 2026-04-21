# ABM 프레임워크 차용 패턴 종합 추출 계획

작성: A1 (찬영) — 2026-04-21
대상: 마포구 1000명 LLM ABM (`backend/src/simulation/`)
자매 문서: `docs/abm-framework-adoption-plan.md` (속도 관점만 정리)

---

## 0. 이 문서의 범위

속도 가속뿐 아니라 **아키텍처·확장성·데이터 수집·시각화·코드 품질·미래 호환성** 전 영역에서 4개 프레임워크로부터 흡수할 패턴을 추출한다.

분석 대상:
- **OASIS** (camel-ai/oasis) — LLM 소셜미디어 100만 에이전트
- **Mesa** (projectmesa/mesa) — Python ABM 표준
- **ABIDES** (jpmorganchase/abides-jpmc-public) — 금융 시장 discrete-event
- **CityFlow** (cityflow-project/CityFlow) — 도시 교통 C++ 코어

---

## 1. 카테고리별 추출 패턴

### 1.1 성능 (Performance)

| 출처 | 패턴 | 우리 적용 | 예상 효과 |
|---|---|---|---|
| OASIS | `asyncio.Semaphore(128)` + `asyncio.gather` step | `runner.py` Tier별 동시호출 상한 분리 | 4~5× |
| OASIS | 단일 consumer Platform 코루틴 (DB 쓰기 직렬화) | RDS 동시쓰기 충돌 차단 | 안정성 ↑ |
| ABIDES | `set_wakeup(t)` PriorityQueue | tick polling 제거 → 필요할 때만 호출 | 10× |
| Mesa | `AgentSet.select(...).shuffle_do(...)` | Tier 필터 일관화 | 코드 간결 |
| CityFlow | `thread_num` 기반 C++ 코어 | 물리 연산 분리 (미도입) | 해당 없음 |

### 1.2 아키텍처 (Architecture)

| 출처 | 패턴 | 우리 적용 | 이점 |
|---|---|---|---|
| OASIS | **Agent ↔ Platform 분리** (Channel을 통해서만 통신) | 신규 `channel.py` + `MapoPlatform` 신설 | 테스트 용이, 에이전트 로직이 DB에 독립 |
| ABIDES | **Kernel lifecycle hooks** (`kernel_initializing/starting/terminating`) | `runner.py`에 훅 4개 정의 | 시나리오 셋업/티어다운 일관화 |
| ABIDES | **메시지 기반 Agent 간 통신** | 현재 친구 초대(`pending_invites`)를 메시지로 재설계 | 느슨한 결합, async 전환 용이 |
| Mesa | **Model/Agent/Space 3축 분리** | `World/Agent/DongNetwork` 명시 분리 | 책임 명확 |
| CityFlow | **Engine/Wrapper 이중 구조** | Python 앞단 + numpy/Cython 뒷단 (미래 고려) | 핫스팟 격리 |

### 1.3 확장성 (Extensibility)

| 출처 | 패턴 | 우리 적용 | 이점 |
|---|---|---|---|
| OASIS | **리플렉션 디스패치** — `getattr(self, action.value)` | `agents.py apply()`의 if/elif 제거 | 액션 추가 시 메서드만 만들면 됨 |
| OASIS | **LLM tool 자동 등록** (`get_openai_function_list()`) | DSL verb 추가 시 tool 스키마 자동 생성 | 프롬프트 동기화 자동 |
| Mesa | **`Agent.create_agents(cls, model, n, *a, **kw)` 팩토리** | `spawn_agents` 리팩터 | 역할 추가 용이 |
| ABIDES | **ActionType / MessageType Enum** | 신규 `action_types.py` 중앙화 | switch 분기 타입 안정성 |

### 1.4 데이터 수집 / 분석 (Metrics & Analysis)

| 출처 | 패턴 | 우리 적용 | 이점 |
|---|---|---|---|
| Mesa | **`DataCollector(model_reporters, agent_reporters)`** — lambda 기반 집계 | 신규 `data_collector.py` 포팅 | pandas DF 자동 변환, 시계열 기록 |
| ABIDES | **Kernel log → 결정론적 재현** | 현재 `event_log`를 JSONL로 덤프 | 리플레이 디버깅 |
| CityFlow | **`engine.get_state()` snapshot API** | 매 tick마다 `world.snapshot()` 반환 | 프론트 live sync |
| OASIS | **Token 소비 통계 내장** | 현재 `BrainStats.tier_s_calls` 확장 | LLM 비용 추적 |

### 1.5 시각화 / UX (Visualization)

| 출처 | 패턴 | 우리 적용 | 이점 |
|---|---|---|---|
| CityFlow | **roadnet JSON 스키마** (intersection + road) | 16개 동 + 인접 그래프를 `mapo_roadnet.json`으로 표준화 | 프론트 Leaflet 지도와 직접 연결 |
| CityFlow | **Replay 파일 포맷** (tick별 state JSON) | 현재 `trajectory.json`을 CityFlow 스타일로 정규화 | 공용 시각화 도구 활용 |
| Mesa | **mesa-viz Solara** | 미적용 (우리 Next.js와 충돌) | 참고만 |
| OASIS | **`env.step()` + platform.get_state()** | WebSocket live push 설계 참고 | 발표용 실시간 시각화 |

### 1.6 코드 품질 / 테스트 (Code Quality)

| 출처 | 패턴 | 우리 적용 | 이점 |
|---|---|---|---|
| OASIS | `ManualAction` / `LLMAction` dataclass 분리 | 결정 생성과 실행 분리 | 단위 테스트 용이 |
| Mesa | **RNG 강제 주입** (`rng=np.random.default_rng(seed)`) | 에이전트별 RNG 명시 | 재현성 |
| ABIDES | **단위 테스트용 MockKernel** | 신규 `test_utils.py`에 `MockWorld` 추가 | 시뮬 외부 로직 테스트 |
| 공통 | `@dataclass(frozen=True)` 불변 메시지 | 메시지/정책 불변화 | race condition 차단 |

### 1.7 미래 호환성 (Future Compatibility)

| 출처 | 패턴 | 우리 적용 | 미래 이점 |
|---|---|---|---|
| OASIS | **PettingZoo 스타일 인터페이스** | `env.reset()/step()/obs/rew` 추가 | RL 정책 학습·distillation 시 호환 |
| Mesa | **Gymnasium 연동 예제** | Agent에 `observation_space/action_space` 정의 | Gym 기반 도구 전체 활용 |
| ABIDES | **Stable-Baselines3 래퍼** | 향후 policy distillation 도구 재사용 | FireAct 스타일 distill 용이 |
| CityFlow | **C++ 포팅 가이드** (pybind11) | 핫스팟 식별 후 선택적 포팅 | v2 단계 10× 추가 가속 |

---

## 2. 프레임워크별 종합 가치

| Framework | 도메인 매칭 | 코드 재사용 | 패턴 차용 | 종합 등급 |
|---|---|---|---|---|
| **OASIS** | 중 (소셜미디어이지만 LLM 구조 동일) | 하 (액션 종속) | **상** (Channel/Semaphore/디스패치) | **A+** |
| **ABIDES** | 중 (금융이지만 discrete-event 일반화) | 중 (Kernel/메시지 구조) | **상** (PriorityQueue/메시지) | **A** |
| **Mesa** | 상 (범용 ABM) | 중 (DataCollector/AgentSet) | 중 (신버전 API) | **B+** |
| **CityFlow** | 하 (교통 물리) | 하 (C++ 코어) | 하 (스키마만) | **C** |

---

## 3. 우리 코드에 적용할 14개 패턴 — 한눈에

### 즉시 (1~3일, 핵심 가속 + 아키텍처 정리)

1. **OASIS Channel + Semaphore** → `channel.py` 신규, `runner.py` 리팩터
2. **ABIDES PriorityQueue wakeup** → `event_scheduler.py` 신규
3. **OASIS 리플렉션 디스패치** → `agents.py apply()` 리팩터
4. **ABIDES Kernel lifecycle hooks** → `runner.py` 4개 훅 정의
5. **ActionType Enum 중앙화** → `action_types.py` 신규

### 중기 (1주, 품질·분석)

6. **Mesa AgentSet 시그니처** → `scheduler.py` 리팩터
7. **Mesa DataCollector 포팅** → `data_collector.py` 신규
8. **OASIS LLM tool 자동 등록** → `brain.py`에 DSL verb 자동 파싱
9. **ABIDES 메시지 기반 Agent 통신** → `pending_invites` 재설계
10. **CityFlow roadnet JSON** → `mapo_roadnet.json` 생성 + 프론트 연동

### 장기 (v2, 미래 확장)

11. **PettingZoo 인터페이스** → RL distillation 대비
12. **Gymnasium obs/action space** → Gym 도구 활용
13. **C++ 핫스팟 포팅** → v2 10× 추가 가속
14. **Stable-Baselines3 래퍼** → policy distillation 파이프라인

---

## 4. 우리가 **차용하지 않을** 것 (명시적 결정)

| 항목 | 이유 |
|---|---|
| OASIS 통째 채택 | 액션이 post/like 종속 → visit/spend/move 추가 오버헤드 큼 |
| Mesa 통째 채택 | LLM·비용·캐싱 가치가 우리 프로젝트의 80%, Mesa가 도와주는 영역은 20% |
| Mesa-LLM alpha | 1.0 릴리스·1K 벤치 전까지 미도입. 6개월 후 재평가 |
| CityFlow C++ 포팅 | 현재 병목은 LLM, 물리 연산 아님. v2 단계로 연기 |
| OASIS 소셜미디어 액션 23종 | 도메인 불일치, DSL(V/M/R/W)만 유지 |

---

## 5. 예상 통합 효과

### 5.1 성능
| 단계 | 1000명 시뮬 시간 | 근거 |
|---|---|---|
| 현재 | 9h | 기준 |
| 패턴 1+2 적용 | 25min | Semaphore + PriorityQueue |
| + 3, 6 | 15min | 디스패치/필터 오버헤드 제거 |
| + 결정 캐싱 + Policy Generator | 5min | `docs/policy-generator-design.md` 참조 |

### 5.2 아키텍처 개선
- 에이전트 로직이 RDS·LLM에 독립 → 단위 테스트 커버리지 +40% 예상
- 액션 추가 비용 90% 감소 (리플렉션 디스패치)
- 시뮬 리플레이 가능 → 디버깅 시간 단축

### 5.3 확장성
- PettingZoo 호환 → FireAct/Agent Distillation 논문 기법 즉시 적용 가능
- CityFlow roadnet JSON → 다른 구·시 확장 시 표준 포맷

### 5.4 심사 방어력
- ABIDES·OASIS·Mesa 3대 프레임워크 패턴 근거로 "정석 구조" 주장 가능
- `policy.rationale` + `kernel.event_log`로 모든 결정의 근거 즉답

---

## 6. 로드맵 (10일)

| Day | 작업 | 산출물 | 패턴 |
|---|---|---|---|
| 1 | Channel + Semaphore 구현 | `channel.py` | 1 |
| 2 | PriorityQueue wakeup | `event_scheduler.py` | 2 |
| 3 | 리플렉션 디스패치 + ActionType Enum | `agents.py`, `action_types.py` | 3, 5 |
| 4 | Kernel lifecycle hooks + AgentSet 시그니처 | `runner.py` | 4, 6 |
| 5 | DataCollector 포팅 | `data_collector.py` | 7 |
| 6 | LLM tool 자동 등록 | `brain.py` 수정 | 8 |
| 7 | 메시지 기반 Agent 통신 | `messaging.py` 신규 | 9 |
| 8 | roadnet JSON 생성 + 프론트 연동 | `mapo_roadnet.json` | 10 |
| 9 | 1000명 풀 벤치 측정 + 문서화 | 벤치 레포트 | — |
| 10 | 발표용 사전 캐시 배치 실행 | `demo_cache.json` | `demo-cache-strategy.md` 연계 |

---

## 7. 참고 원본 경로

### OASIS
- `oasis/social_agent/agent.py:perform_action_by_llm`
- `oasis/social_agent/agent_action.py:perform_action`, `get_openai_function_list`
- `oasis/social_platform/platform.py:running`
- `oasis/social_platform/channel.py`
- `oasis/environment/env.py:step`, `reset`

### Mesa
- `mesa/agent.py` (AgentSet, create_agents)
- `mesa/model.py` (schedule_event)
- `mesa/discrete_space/` (NetworkGrid)

### ABIDES
- `abides-core/abides_core/kernel.py:run`
- `abides-core/abides_core/agent.py:set_wakeup`, `receive_message`
- `abides-core/abides_core/latency_model.py`

### CityFlow
- `src/engine/engine.h` (next_step, get_vehicles)
- README의 roadnet JSON 스키마
- `src/roadnet/` (graph 구조)

---

## 8. 결정 필요 사항

1. **도입 순서** — 10일 로드맵대로 진행할지, 핵심 2~3개만 발표 전까지 집중할지
2. **담당 분리** — A1 단독 진행할지, B1/B2와 책임 분담할지
3. **발표 데모 구조** — 패턴 1+2+ Policy Generator로 5분 실시간 데모 vs 사전 캐시 중심 데모
4. **v2 로드맵** — PettingZoo/Gym 호환 + C++ 포팅은 발표 후 어느 분기에 시작할지
