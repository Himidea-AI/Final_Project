# 시뮬레이션 백그라운드 실행 추적 — 설계 스펙

**작성일**: 2026-04-19
**담당**: C1 (강민) — `frontend/`
**상태**: 설계 승인 완료, 구현 계획 대기

## 1. 배경 및 문제

SPOTTER 시뮬레이션은 평균 50~80초(최대 120초) 소요되는 LangGraph 기반 분석이다. 현재 구조에서는 사용자가 `/simulator`에서 RUN을 누른 뒤 다른 페이지(`/explore`, `/about` 등)로 이동하면 다음 문제가 발생한다.

- `SimulatorDashboard`가 언마운트되면서 `reportState`, `simResult` 등 로컬 `useState`가 소실됨
- 진행 상태를 어디서도 볼 수 없어 사용자가 시뮬레이션 진행 여부를 알 수 없음
- 결과가 도착해도 받아 보여줄 컴포넌트가 없어 사용자가 다시 `/simulator`로 돌아가더라도 처음부터 다시 실행해야 함

## 2. 해결 방식 — 하이브리드 접근 (A → B)

백엔드 변경을 최소화하면서 장기 확장 경로를 확보하는 2단계 접근.

- **A단계 (이번 스펙 범위, C1 단독)**: 프론트엔드 전역 store로 시뮬레이션 상태를 올려 페이지 이동에 독립적으로 유지. 진행률은 현재와 동일하게 타이머 기반(가짜) 유지.
- **B단계 (미래, 백엔드 협업)**: 백엔드 `/simulate`가 `job_id` 반환 + 별도 상태 조회 엔드포인트 지원하면, store 내부 구현만 교체하고 UI는 그대로 두는 확장.

A단계 인터페이스를 B단계로 확장 가능한 모양으로 설계해, 리팩터링 비용을 최소화한다.

## 3. 결정된 요구사항

| 항목 | 결정 | 이유 |
|-----|-----|-----|
| 범위 | C (하이브리드) | 혼자 구현 가능 + 미래 확장성 확보 |
| 페이지 이동 시 표시 | B (플로팅 미니 위젯) | cyber 톤과 어울림, 클릭 복귀 UX 자연스러움 |
| 동시 실행 | B (단일 + 취소·교체) | 주 사용 흐름이 "조건 조정 → 다시 돌리기" 반복 |
| 완료 UX | C (토스트 + 위젯 DONE 유지) | 강제 이동 없이 놓치지 않게 알림 |
| 새로고침 | A (beforeunload 경고) | 1~2분 분석 실수로 날리는 케이스 방지 |
| 상태 관리 | Zustand | 셀렉터로 선택적 구독, App.tsx 스플리팅 로드맵과 방향 일치, B단계 확장 용이 |

## 4. 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│  <App>                                                  │
│  ├─ <BrowserRouter>                                     │
│  │  ├─ /simulator  ──→ <SimulatorDashboard>             │
│  │  ├─ /explore    ──→ <AccordionGallery>               │
│  │  └─ ...                                              │
│  │                                                      │
│  ├─ <SimulationFloatingWidget>  (라우팅 바깥, 항상 마운트)│
│  └─ <BeforeUnloadGuard>         (라우팅 바깥)            │
└─────────────────────────────────────────────────────────┘
          ▲                              ▲
          │ subscribe                    │ subscribe
          │                              │
    ┌─────┴──────────────────────────────┴─────┐
    │  useSimulationStore  (Zustand singleton) │
    │                                          │
    │  status / progress / stage / result      │
    │  error / params / startedAt              │
    │                                          │
    │  startSimulation / cancelSimulation /    │
    │  dismissResult                           │
    └──────────────────────────────────────────┘
                        │
                        │ fetch(/simulate, signal)
                        ▼
                  [FastAPI 백엔드 — 변경 없음]
```

**핵심 원칙**:
1. Store는 App 바깥의 싱글톤 — 라우팅과 독립
2. Fetch는 store의 action 안에서 시작 — 컴포넌트 언마운트돼도 계속 진행
3. 플로팅 위젯과 beforeunload 가드는 App 최상위 마운트 — 페이지 전환에도 유지
4. `SimulatorDashboard`의 로컬 `useState`(`reportState`, `simResult`, `loadingProgress`, `loadingText`)는 store로 이관 — 중복 제거

## 5. Store 상세

### 데이터 모델

```ts
// frontend/src/stores/simulationStore.ts
type Status = 'idle' | 'running' | 'done' | 'error';

interface SimulationState {
  status: Status;
  progress: number;          // 0~100
  stage: string;             // 예: "QUERYING POPULATION TRENDS"
  result: SimResult | null;
  error: string | null;
  params: SimulationInput | null;
  startedAt: number | null;  // Date.now()

  // 내부 리소스 (UI 미노출)
  _abortController: AbortController | null;
  _progressTimer: number | null;

  // 액션
  startSimulation: (params: SimulationInput) => Promise<void>;
  cancelSimulation: () => void;
  dismissResult: () => void;
}
```

### 액션 명세

| 액션 | 전이 | 부수 효과 |
|------|------|----------|
| `startSimulation(params)` | 기존 running 있으면 cancel 선행 → `*→running`, progress=0 | 타이머 start, fetch 시작 (취소-교체 정책) |
| `cancelSimulation()` | `running→idle` | AbortController.abort(), 타이머 clear |
| `dismissResult()` | `done|error→idle` | result/error/params null |
| fetch 성공 | `running→done`, progress=100 | result 저장 |
| fetch 실패 (non-abort) | `running→error` | error 메시지 저장 |
| fetch AbortError | 무시 | 이미 cancel에서 상태 정리 완료 |

### 진행률 계산 (A단계)

- 기존 `App.tsx:2584-2596`의 11단계 stage 매핑 재사용
- 500ms마다 `progress = min(90, (Date.now() - startedAt) / 1000 * 0.9)`
- fetch 완료 순간 100%로 점프 (기존 UX 동일)
- **B단계 확장**: 이 타이머를 `fetchJobProgress(job_id)` 폴링으로 교체하면 나머지 컴포넌트 변경 없음

### Stale response guard

교체 실행 시 이전 fetch가 뒤늦게 resolve되는 race 방지:

```ts
const myStartedAt = Date.now();
set({ startedAt: myStartedAt, ... });
try {
  const result = await fetch(...);
  if (get().startedAt !== myStartedAt) return;  // 이미 교체됨 → 무시
  set({ status: 'done', result });
} catch ...
```

## 6. 컴포넌트 구조

### 새로 만들 파일

```
frontend/src/
├── stores/
│   └── simulationStore.ts           [NEW] Zustand store + 액션 + 타이머
├── components/simulation/
│   ├── SimulationFloatingWidget.tsx [NEW] 우측 하단 미니 위젯
│   └── BeforeUnloadGuard.tsx        [NEW] beforeunload 리스너
├── hooks/
│   └── useCompletionToast.ts        [NEW] status 전이 감지 → 토스트
└── types/
    └── index.ts                     [MODIFY] Status 타입 export
```

### 수정할 파일

**`frontend/src/App.tsx`** (현재 6420줄)
- 라인 2478-2575 `runSim()` → `useSimulationStore.startSimulation()` 호출로 교체 (~10줄)
- 라인 2577-2615 진행률 타이머 `useEffect` → **삭제** (store로 이관)
- `reportState`, `simResult`, `loadingProgress`, `loadingText` `useState` → **삭제**, store 셀렉터로 읽기
- 라우터 밖에 `<SimulationFloatingWidget />`, `<BeforeUnloadGuard />` 추가

**`frontend/package.json`**: `zustand` 의존성 추가 (~1 kB gzip)

### 컴포넌트 책임

**`<SimulationFloatingWidget>`** — 우측 하단 `fixed bottom-6 right-6 z-50`
- `running`: 스피너 + "SIMULATING 45% · ETA 30s" + stage + 취소 X
- `done`: 체크 + "ANALYSIS COMPLETE" + "결과 보기" + dismiss X
- `error`: 경고 + "FAILED" + "재시도" + X
- `idle`: `null` 반환
- 클릭 시 `navigate('/simulator')`
- SPOTTER cyber 톤(dark + neon cyan) Tailwind 일관

**`<BeforeUnloadGuard>`**
- `useEffect`로 `beforeunload` 리스너 등록/해제
- `status === 'running'`일 때만 활성
- JSX는 `null` (behavior-only)

**`useCompletionToast()`**
- App 최상위에서 한 번 호출
- `useRef`로 이전 status 추적 → `running→done` 시 성공 토스트, `running→error` 시 실패 토스트
- 기존 토스트 라이브러리 재사용 (구현 단계에서 확인 — 없으면 단순 자체 구현)

### 책임 분리 원칙

- **store**: 비즈니스 로직 + 상태 + fetch + 타이머 (UI 모름)
- **위젯**: 상태 시각화 + 액션 트리거 (비즈니스 모름)
- **훅/가드**: 부수 효과 전담 (토스트, beforeunload)
- **`SimulatorDashboard`**: 로컬 상태 제거, store에서 읽기만

## 7. 데이터 흐름 (주요 시나리오)

### 시나리오 1 — 정상 완료 (`/simulator`에서 대기)
`RUN → startSimulation → status='running' + 타이머 + fetch → 500ms마다 progress tick → fetch resolve → status='done', progress=100, result 저장 → 결과 화면 렌더`

### 시나리오 2 — 도중에 `/explore`로 이동
- t=15s: 페이지 이동 → `SimulatorDashboard` 언마운트 (로컬 상태 없음)
- fetch는 store가 잡고 있어 계속 진행
- `<SimulationFloatingWidget>`은 App 최상위라 유지 → 우측 하단 표시
- t=60s: 완료 → 위젯 "DONE · 결과 보기"로 전환, `useCompletionToast`가 토스트 발화
- 사용자가 토스트/위젯 클릭 → `/simulator` 복귀 → store.result 읽어 즉시 표시

### 시나리오 3 — 실행 중 RUN 재클릭 (교체)
`startSimulation(newParams)` → 현재 running이면 `_abortController.abort()` + 타이머 clear → status='running', progress=0, params=newParams → 새 fetch

### 시나리오 4 — 에러
- `AbortError`: 정상 취소, 무시 (status 이미 idle)
- 그 외: `status='error'`, error=메시지, 위젯 "FAILED · 재시도", 에러 토스트

### 시나리오 5 — 새로고침/탭 닫기
- `<BeforeUnloadGuard>`가 `status==='running'`에서 `beforeunload` 핸들러 등록
- 브라우저 기본 확인창 표시

## 8. 에러 매트릭스

| 케이스 | 처리 |
|-------|------|
| 네트워크 실패 (offline, DNS) | `status='error'`, "네트워크 연결 확인" 메시지, 재시도 가능 |
| HTTP 5xx | `status='error'`, 상태코드+메시지, 재시도 가능 |
| HTTP 4xx (예: 400 잘못된 파라미터) | `status='error'`, 백엔드 detail, "조건 수정 필요" 안내 |
| 백엔드 120초 timeout | 504/timeout 응답 → error 처리 (위와 동일) |
| 사용자 수동 취소 | `AbortError` catch → 무시 (액션에서 idle 전이 완료) |
| 교체 실행 stale response | `startedAt` 불일치 검사로 무시 |
| 재시도 시 params null | 버튼 비활성화 (방어적) |
| 완료 후 dismiss 없이 다시 RUN | `done→running` 시 result 자동 클리어 |
| 탭 백그라운드 전환 | 별도 처리 없음. 타이머가 `Date.now() - startedAt` 기반이라 throttle돼도 복귀 시 자연 복구 |

## 9. YAGNI — 하지 않는 것

- ❌ sessionStorage 영속화 (A단계는 탭 생명주기까지만, B단계 `job_id` 생기면 자연 해결)
- ❌ 다중 동시 실행 (단일 정책 확정)
- ❌ 실제 백엔드 진행률 (A단계는 타이머)
- ❌ `navigator.onLine` 오프라인 감지 (fetch 실패 시점에 처리됨)
- ❌ 위젯 드래그/위치 기억 (우측 하단 고정)

## 10. 테스트 전략

### Store 단위 테스트 (`stores/simulationStore.test.ts`)
- `startSimulation`: idle→running 전이, params 저장, 타이머 시작
- `startSimulation` × 2회: 교체, 기존 `abort()` 호출 검증
- `cancelSimulation`: running→idle, 타이머 정리
- fetch 성공 모킹 → running→done, result 저장
- fetch 실패 모킹 → running→error, error 메시지
- `AbortError`는 error로 처리 안 되는지
- Stale response guard: 교체 후 이전 fetch resolve 무시

### 컴포넌트 테스트 (React Testing Library)
- `<SimulationFloatingWidget>`: status별 렌더링 스냅샷
- 위젯 "결과 보기" 클릭 → `navigate('/simulator')` 호출
- `<BeforeUnloadGuard>`: running 상태에서만 리스너 등록

### 수동 QA 체크리스트
1. `/simulator` RUN → `/explore` 이동 → 위젯 표시됨
2. 완료 후 위젯 "DONE", 토스트 발화
3. 위젯 클릭 → `/simulator` 복귀, 결과 즉시 표시
4. 실행 중 RUN 재클릭 → 이전 취소, 새로 시작 (progress 0 리셋)
5. 실행 중 새로고침 시도 → beforeunload 경고
6. 백엔드 에러 상황 → 위젯 FAILED, 재시도 동작

E2E 자동화는 현재 프론트엔드 테스트 인프라 확인 후 결정 (없으면 수동 QA로 대체).

## 11. B단계 확장 경로 (미래, 이번 스펙 밖)

백엔드가 `/simulate`를 job 모델로 전환했을 때 프론트 변경점:

```ts
// simulationStore.ts 내부만 교체
async startSimulation(params) {
  const { job_id } = await fetch('/simulate', {...}).then(r => r.json());  // 즉시 반환
  set({ jobId: job_id, status: 'running' });

  const poll = setInterval(async () => {
    const { progress, stage, status, result } =
      await fetch(`/simulate/status/${job_id}`).then(r => r.json());
    set({ progress, stage });
    if (status === 'done') { set({ result, status: 'done' }); clearInterval(poll); }
  }, 2000);
}
```

**영향 범위**: store 파일 내부만. 위젯/대시보드/토스트 훅 **전부 그대로**.

**추가 이득**:
- `sessionStorage`에 `jobId` 저장 → 새로고침 후 재개 가능
- B2B "후보지 3곳 비교" 필요 시 `Map<jobId, JobState>`로 store shape만 확장

## 12. 성공 기준 (Acceptance)

1. `/simulator` RUN 후 다른 페이지 이동해도 시뮬레이션 계속 진행
2. 다른 페이지에서 플로팅 위젯으로 진행률 확인 가능
3. 완료 순간 토스트 + 위젯 상태 전환
4. 위젯 클릭 시 `/simulator` 복귀 후 결과 즉시 표시
5. 실행 중 RUN 재클릭 시 이전 취소 + 새로 시작
6. 진행 중 새로고침 시도 시 브라우저 경고창
7. 실패 시 위젯 FAILED 상태 + 재시도 동작
8. `SimulatorDashboard` 로컬 `useState` 4개가 store로 이관되어 중복 제거

## 13. 스코프 & 담당

- **담당**: C1 (강민), `frontend/` 단독
- **건드리지 않는 영역**: `backend/*`, `data/*`, `models/*`
- **새 의존성**: `zustand` (프론트엔드 전용, AGENTS.md 규약상 C1이 추가 가능)
- **공통 파일 수정 없음**: `package.json`은 `frontend/` 하위라 공통 아님, `docker-compose.yml`·`README.md`·`.env.example` 미수정

## 14. 다음 단계

이 스펙 승인 후 `writing-plans` 스킬로 구현 계획 작성 예정.
