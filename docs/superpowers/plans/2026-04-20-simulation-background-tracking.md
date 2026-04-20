# 시뮬레이션 백그라운드 실행 추적 — 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 시뮬레이션 실행 중 페이지를 이동해도 진행 상태가 유지되고, 플로팅 위젯으로 어떤 페이지에서든 확인·복귀·취소할 수 있도록 한다.

**Architecture:** Zustand 전역 store가 fetch와 상태를 보유하고, App 최상위에 마운트된 플로팅 위젯·beforeunload 가드·토스트 호스트가 store를 구독한다. `SimulatorDashboard`의 로컬 `useState`는 store로 이관한다. A단계는 타이머 기반 진행률(기존 UX 동일), B단계(백엔드 job_id)에서는 store 내부만 폴링으로 교체.

**Tech Stack:** React 18, TypeScript, Vite, Zustand(신규), axios(기존), Tailwind CSS(기존), Vitest + @testing-library/react(신규, store 단위 테스트용)

**Jira:** IM3-205
**Spec:** `docs/superpowers/specs/2026-04-19-simulation-background-tracking-design.md`

---

## File Structure

### 새로 만들 파일

```
frontend/
├── vitest.config.ts                                       [NEW] 테스트 러너 설정
├── src/
│   ├── test/
│   │   └── setup.ts                                       [NEW] jsdom + global test setup
│   ├── stores/
│   │   ├── simulationStore.ts                             [NEW] Zustand store (핵심)
│   │   ├── simulationStore.test.ts                        [NEW] store 단위 테스트
│   │   └── toastStore.ts                                  [NEW] 경량 토스트 전역 store
│   ├── components/simulation/
│   │   ├── SimulationFloatingWidget.tsx                   [NEW] 우측 하단 미니 위젯
│   │   ├── BeforeUnloadGuard.tsx                          [NEW] beforeunload 리스너
│   │   └── ToastHost.tsx                                  [NEW] 토스트 렌더러
│   └── hooks/
│       └── useCompletionToast.ts                          [NEW] status 전이 → 토스트 훅
```

### 수정할 파일

- `frontend/package.json` — `zustand`, `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom` 추가
- `frontend/src/api/client.ts` — `runSimulation`에 옵셔널 `AbortSignal` 파라미터 추가 (기존 호출자 영향 없음)
- `frontend/src/App.tsx` — `runSim` 호출부 교체, 로컬 useState 4개 제거, 위젯·가드·토스트호스트 마운트

### 책임 경계

| 파일 | 책임 | 의존 |
|------|------|------|
| `simulationStore.ts` | 상태 + 액션 + fetch + 타이머 (UI 미지) | axios, zustand |
| `toastStore.ts` | 토스트 큐 관리 | zustand |
| `SimulationFloatingWidget.tsx` | store 구독 → 상태별 시각화 | react-router-dom |
| `BeforeUnloadGuard.tsx` | `beforeunload` 리스너 | — |
| `ToastHost.tsx` | 토스트 큐 렌더 | framer-motion (선택) |
| `useCompletionToast.ts` | status 전이 감지 → 토스트 발화 | 두 store |

---

## Task 1: 의존성 + 테스트 러너 세팅

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test/setup.ts`
- Modify: `frontend/.gitignore` (필요 시 coverage 폴더)

- [ ] **Step 1: zustand와 테스트 devDeps 추가**

현재 작업 디렉토리: `frontend/`.
실행:
```bash
cd frontend && npm install zustand
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom @vitest/ui
```

- [ ] **Step 2: vitest 설정 파일 생성**

파일: `frontend/vitest.config.ts`
```ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
});
```

- [ ] **Step 3: 테스트 setup 파일 생성**

파일: `frontend/src/test/setup.ts`
```ts
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});
```

- [ ] **Step 4: package.json에 test 스크립트 추가**

`frontend/package.json`의 `"scripts"`에 추가:
```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 5: 스모크 테스트로 러너 동작 확인**

파일: `frontend/src/test/smoke.test.ts`
```ts
import { describe, it, expect } from 'vitest';

describe('smoke', () => {
  it('works', () => {
    expect(1 + 1).toBe(2);
  });
});
```

실행: `cd frontend && npm test`
기대: smoke 테스트 통과. 통과 확인 후 파일 삭제.

- [ ] **Step 6: Prettier 적용 후 커밋**

```bash
cd frontend && npx prettier --write vitest.config.ts src/test/setup.ts
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/src/test/setup.ts
git commit -m "IM3-205: chore(C1): Vitest + zustand 도입 (프론트 테스트 인프라 초기화)"
```

---

## Task 2: simulationStore — 타입 & 초기 상태

**Files:**
- Create: `frontend/src/stores/simulationStore.ts`
- Create: `frontend/src/stores/simulationStore.test.ts`

- [ ] **Step 1: 실패 테스트 작성 — 초기 상태**

파일: `frontend/src/stores/simulationStore.test.ts`
```ts
import { describe, it, expect, beforeEach } from 'vitest';
import { useSimulationStore } from './simulationStore';

describe('simulationStore — 초기 상태', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
  });

  it('초기에는 idle', () => {
    const s = useSimulationStore.getState();
    expect(s.status).toBe('idle');
    expect(s.progress).toBe(0);
    expect(s.result).toBeNull();
    expect(s.error).toBeNull();
    expect(s.params).toBeNull();
  });
});
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

실행: `cd frontend && npx vitest run src/stores/simulationStore.test.ts`
기대: "Cannot find module './simulationStore'" 에러

- [ ] **Step 3: store 스켈레톤 작성**

파일: `frontend/src/stores/simulationStore.ts`
```ts
import { create } from 'zustand';
import type { SimulationInput, SimulationOutput } from '@/types';

export type SimulationStatus = 'idle' | 'running' | 'done' | 'error';

interface SimulationState {
  status: SimulationStatus;
  progress: number;
  stage: string;
  result: SimulationOutput | null;
  error: string | null;
  params: SimulationInput | null;
  startedAt: number | null;

  _abortController: AbortController | null;
  _progressTimer: ReturnType<typeof setInterval> | null;

  startSimulation: (params: SimulationInput) => Promise<void>;
  cancelSimulation: () => void;
  dismissResult: () => void;
  reset: () => void;
}

const INITIAL_STATE = {
  status: 'idle' as SimulationStatus,
  progress: 0,
  stage: '',
  result: null,
  error: null,
  params: null,
  startedAt: null,
  _abortController: null,
  _progressTimer: null,
};

export const useSimulationStore = create<SimulationState>((set, get) => ({
  ...INITIAL_STATE,

  startSimulation: async () => {
    // Task 3에서 구현
  },
  cancelSimulation: () => {
    // Task 6에서 구현
  },
  dismissResult: () => {
    // Task 10에서 구현
  },
  reset: () => {
    const { _abortController, _progressTimer } = get();
    _abortController?.abort();
    if (_progressTimer) clearInterval(_progressTimer);
    set(INITIAL_STATE);
  },
}));
```

- [ ] **Step 4: 테스트 재실행 → PASS 확인**

실행: `cd frontend && npx vitest run src/stores/simulationStore.test.ts`
기대: 1 passed

- [ ] **Step 5: Prettier 적용 후 커밋**

```bash
cd frontend && npx prettier --write src/stores/simulationStore.ts src/stores/simulationStore.test.ts
git add frontend/src/stores/simulationStore.ts frontend/src/stores/simulationStore.test.ts
git commit -m "IM3-205: feat(C1): simulationStore 스켈레톤 + 초기 상태 테스트"
```

---

## Task 3: API 확장 — `runSimulation`에 AbortSignal 추가

**Files:**
- Modify: `frontend/src/api/client.ts:56-59`

- [ ] **Step 1: 기존 호출자에 영향 없는 옵셔널 파라미터로 확장**

`frontend/src/api/client.ts`의 `runSimulation` 수정:
```ts
/** 시뮬레이션 실행 요청 */
export async function runSimulation(
  input: SimulationInput,
  signal?: AbortSignal,
): Promise<SimulationOutput> {
  const response = await apiClient.post('/simulate', input, { signal });
  return response.data;
}
```

- [ ] **Step 2: 빌드 타입 체크**

실행: `cd frontend && npx tsc --noEmit`
기대: 에러 없음 (옵셔널이라 기존 호출부 영향 없음)

- [ ] **Step 3: Prettier + 커밋**

```bash
cd frontend && npx prettier --write src/api/client.ts
git add frontend/src/api/client.ts
git commit -m "IM3-205: feat(C1): runSimulation에 AbortSignal 옵셔널 파라미터 추가"
```

---

## Task 4: simulationStore — startSimulation 성공 경로

**Files:**
- Modify: `frontend/src/stores/simulationStore.ts`
- Modify: `frontend/src/stores/simulationStore.test.ts`

- [ ] **Step 1: 실패 테스트 작성 — 성공 전이**

`simulationStore.test.ts`에 추가:
```ts
import { vi } from 'vitest';
import * as api from '@/api/client';
import type { SimulationInput, SimulationOutput } from '@/types';

const MOCK_INPUT: SimulationInput = {
  business_type: 'cafe',
  brand_name: 'Test',
  target_district: '서교동',
  existing_stores: [],
  initial_investment: 0,
  monthly_rent: 1000000,
  simulation_months: 12,
  scenarios: [],
};

const MOCK_OUTPUT = {
  request_id: 'r1',
  target_district: '서교동',
  analysis_report: 'ok',
  analysis_metrics: {
    district_grade: 'NORMAL',
    growth_rate: 0,
    competition_score: 0,
    rent_affordability: 'SAFE',
  },
  simulation_months: 12,
  quarterly_projection: [],
  comparison: [],
  legal_risks: [],
} as unknown as SimulationOutput;

describe('simulationStore — startSimulation 성공', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('running으로 전이하고 params·startedAt을 저장한다', async () => {
    vi.spyOn(api, 'runSimulation').mockResolvedValue(MOCK_OUTPUT);
    const p = useSimulationStore.getState().startSimulation(MOCK_INPUT);

    const mid = useSimulationStore.getState();
    expect(mid.status).toBe('running');
    expect(mid.params).toEqual(MOCK_INPUT);
    expect(mid.startedAt).toBeGreaterThan(0);
    expect(mid._abortController).not.toBeNull();

    await p;
    const final = useSimulationStore.getState();
    expect(final.status).toBe('done');
    expect(final.progress).toBe(100);
    expect(final.result).toEqual(MOCK_OUTPUT);
  });
});
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

실행: `cd frontend && npx vitest run src/stores/simulationStore.test.ts`
기대: running 전이 실패 (액션 내용 아직 비어 있음)

- [ ] **Step 3: startSimulation 구현**

`simulationStore.ts`의 `startSimulation` 교체:
```ts
startSimulation: async (params) => {
  const abortController = new AbortController();
  const startedAt = Date.now();

  set({
    status: 'running',
    progress: 0,
    stage: 'INITIALIZING AI ENGINE',
    result: null,
    error: null,
    params,
    startedAt,
    _abortController: abortController,
  });

  try {
    const { runSimulation } = await import('@/api/client');
    const result = await runSimulation(params, abortController.signal);

    // Stale response guard
    if (get().startedAt !== startedAt) return;

    set({
      status: 'done',
      progress: 100,
      stage: 'COMPLETE',
      result,
      _abortController: null,
    });
  } catch (err: unknown) {
    // Task 5에서 에러 처리
    throw err;
  }
},
```

- [ ] **Step 4: 테스트 재실행 → PASS 확인**

실행: `cd frontend && npx vitest run src/stores/simulationStore.test.ts`
기대: 2 passed

- [ ] **Step 5: Prettier + 커밋**

```bash
cd frontend && npx prettier --write src/stores/simulationStore.ts src/stores/simulationStore.test.ts
git add frontend/src/stores/simulationStore.ts frontend/src/stores/simulationStore.test.ts
git commit -m "IM3-205: feat(C1): startSimulation 성공 경로 (running→done)"
```

---

## Task 5: simulationStore — 에러 처리 & AbortError 분기

**Files:**
- Modify: `frontend/src/stores/simulationStore.ts`
- Modify: `frontend/src/stores/simulationStore.test.ts`

- [ ] **Step 1: 에러 테스트 2개 추가**

`simulationStore.test.ts`에 추가:
```ts
import axios from 'axios';

describe('simulationStore — 에러', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('fetch 실패 시 error 상태로 전이한다', async () => {
    vi.spyOn(api, 'runSimulation').mockRejectedValue(new Error('network down'));
    await useSimulationStore.getState().startSimulation(MOCK_INPUT);
    const s = useSimulationStore.getState();
    expect(s.status).toBe('error');
    expect(s.error).toContain('network down');
  });

  it('AbortError는 error로 기록하지 않는다', async () => {
    const abortErr = new axios.Cancel('canceled');
    vi.spyOn(api, 'runSimulation').mockRejectedValue(abortErr);
    await useSimulationStore.getState().startSimulation(MOCK_INPUT);
    const s = useSimulationStore.getState();
    expect(s.status).not.toBe('error');
  });
});
```

- [ ] **Step 2: 테스트 실행 → FAIL 확인**

실행: `cd frontend && npx vitest run src/stores/simulationStore.test.ts`
기대: 두 에러 테스트 FAIL (throw된 채 테스트에 unhandled rejection)

- [ ] **Step 3: startSimulation의 catch 블록 구현**

`simulationStore.ts`의 catch 블록 교체:
```ts
} catch (err: unknown) {
  // Stale response: 이미 다른 실행으로 교체됨
  if (get().startedAt !== startedAt) return;

  // Axios의 cancel/abort는 에러로 취급하지 않음
  const isAbort =
    (err as { name?: string })?.name === 'CanceledError' ||
    (err as { name?: string })?.name === 'AbortError' ||
    axios.isCancel?.(err);

  if (isAbort) {
    // cancelSimulation에서 이미 상태 정리했으므로 추가 set 불필요
    return;
  }

  const message =
    err instanceof Error ? err.message : typeof err === 'string' ? err : '알 수 없는 오류';
  set({
    status: 'error',
    error: message,
    _abortController: null,
  });
}
```

파일 상단 import에 추가:
```ts
import axios from 'axios';
```

- [ ] **Step 4: 테스트 재실행 → PASS 확인**

실행: `cd frontend && npx vitest run src/stores/simulationStore.test.ts`
기대: 4 passed

- [ ] **Step 5: Prettier + 커밋**

```bash
cd frontend && npx prettier --write src/stores/simulationStore.ts src/stores/simulationStore.test.ts
git add frontend/src/stores/simulationStore.ts frontend/src/stores/simulationStore.test.ts
git commit -m "IM3-205: feat(C1): 에러 처리 + AbortError 분기"
```

---

## Task 6: simulationStore — cancelSimulation

**Files:**
- Modify: `frontend/src/stores/simulationStore.ts`
- Modify: `frontend/src/stores/simulationStore.test.ts`

- [ ] **Step 1: 테스트 추가**

```ts
describe('simulationStore — cancelSimulation', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('running을 idle로 되돌리고 abort를 호출한다', async () => {
    let capturedSignal: AbortSignal | undefined;
    vi.spyOn(api, 'runSimulation').mockImplementation(async (_p, signal) => {
      capturedSignal = signal;
      return new Promise<SimulationOutput>(() => {}); // 영영 resolve 안 됨
    });

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    expect(useSimulationStore.getState().status).toBe('running');

    useSimulationStore.getState().cancelSimulation();
    expect(useSimulationStore.getState().status).toBe('idle');
    expect(capturedSignal?.aborted).toBe(true);
  });
});
```

- [ ] **Step 2: FAIL 확인**

실행: `cd frontend && npx vitest run src/stores/simulationStore.test.ts`

- [ ] **Step 3: 구현**

`simulationStore.ts`의 `cancelSimulation` 교체:
```ts
cancelSimulation: () => {
  const { _abortController, _progressTimer } = get();
  _abortController?.abort();
  if (_progressTimer) clearInterval(_progressTimer);
  set({
    status: 'idle',
    progress: 0,
    stage: '',
    _abortController: null,
    _progressTimer: null,
    startedAt: null,
  });
},
```

- [ ] **Step 4: PASS 확인**

- [ ] **Step 5: Prettier + 커밋**

```bash
git add frontend/src/stores/simulationStore.ts frontend/src/stores/simulationStore.test.ts
git commit -m "IM3-205: feat(C1): cancelSimulation 구현"
```

---

## Task 7: simulationStore — 교체 실행 + Stale Guard

**Files:**
- Modify: `frontend/src/stores/simulationStore.ts`
- Modify: `frontend/src/stores/simulationStore.test.ts`

- [ ] **Step 1: 교체 테스트 추가**

```ts
describe('simulationStore — 교체 실행', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('실행 중 startSimulation 재호출 시 이전 AbortController가 abort된다', async () => {
    const signals: AbortSignal[] = [];
    vi.spyOn(api, 'runSimulation').mockImplementation(async (_p, signal) => {
      signals.push(signal!);
      return new Promise<SimulationOutput>(() => {});
    });

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    useSimulationStore.getState().startSimulation({ ...MOCK_INPUT, brand_name: 'Other' });

    expect(signals[0].aborted).toBe(true);
    expect(signals[1].aborted).toBe(false);
    expect(useSimulationStore.getState().params?.brand_name).toBe('Other');
    expect(useSimulationStore.getState().progress).toBe(0);
  });

  it('교체 후 이전 fetch가 뒤늦게 resolve되어도 무시된다 (stale guard)', async () => {
    let resolveFirst!: (v: SimulationOutput) => void;
    const firstPromise = new Promise<SimulationOutput>((res) => {
      resolveFirst = res;
    });
    vi.spyOn(api, 'runSimulation')
      .mockImplementationOnce(() => firstPromise)
      .mockResolvedValueOnce(MOCK_OUTPUT);

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    await useSimulationStore.getState().startSimulation({ ...MOCK_INPUT, brand_name: 'B' });

    // 두 번째가 완료된 상태
    expect(useSimulationStore.getState().status).toBe('done');

    // 첫 번째가 뒤늦게 resolve
    resolveFirst({ ...MOCK_OUTPUT, request_id: 'STALE' } as SimulationOutput);
    await Promise.resolve();

    // 상태가 STALE로 덮이지 않아야 함
    expect(useSimulationStore.getState().result?.request_id).toBe('r1');
  });
});
```

- [ ] **Step 2: FAIL 확인**

- [ ] **Step 3: startSimulation 앞쪽에 pre-cancel 추가**

`simulationStore.ts`의 `startSimulation` 시작부 교체:
```ts
startSimulation: async (params) => {
  // 교체 정책: 실행 중이면 먼저 취소
  const { _abortController: prevAbort, _progressTimer: prevTimer } = get();
  prevAbort?.abort();
  if (prevTimer) clearInterval(prevTimer);

  const abortController = new AbortController();
  const startedAt = Date.now();

  set({
    status: 'running',
    progress: 0,
    stage: 'INITIALIZING AI ENGINE',
    result: null,
    error: null,
    params,
    startedAt,
    _abortController: abortController,
    _progressTimer: null,
  });
  // ... (이하 기존 try/catch)
```

(Stale guard는 이미 Task 4에서 `if (get().startedAt !== startedAt) return;`로 구현됨. 재확인만.)

- [ ] **Step 4: PASS 확인**

- [ ] **Step 5: Prettier + 커밋**

```bash
git add frontend/src/stores/simulationStore.ts frontend/src/stores/simulationStore.test.ts
git commit -m "IM3-205: feat(C1): 실행 중 재호출 시 취소-교체 정책 + stale guard"
```

---

## Task 8: simulationStore — 진행률 타이머 & stage 매핑

**Files:**
- Modify: `frontend/src/stores/simulationStore.ts`
- Modify: `frontend/src/stores/simulationStore.test.ts`

- [ ] **Step 1: 타이머 테스트 추가 (가짜 타이머 사용)**

```ts
describe('simulationStore — 진행률 타이머', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('startSimulation 호출 후 시간에 따라 progress가 증가한다', async () => {
    vi.spyOn(api, 'runSimulation').mockImplementation(
      async () => new Promise<SimulationOutput>(() => {}),
    );

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    expect(useSimulationStore.getState().progress).toBe(0);

    vi.advanceTimersByTime(10_000); // 10초 경과
    const p = useSimulationStore.getState().progress;
    expect(p).toBeGreaterThanOrEqual(8);
    expect(p).toBeLessThanOrEqual(10);
  });

  it('progress는 90%를 초과하지 않는다', async () => {
    vi.spyOn(api, 'runSimulation').mockImplementation(
      async () => new Promise<SimulationOutput>(() => {}),
    );

    useSimulationStore.getState().startSimulation(MOCK_INPUT);
    vi.advanceTimersByTime(200_000); // 200초
    expect(useSimulationStore.getState().progress).toBeLessThanOrEqual(90);
  });
});
```

- [ ] **Step 2: FAIL 확인**

- [ ] **Step 3: 타이머 + stage 매핑 구현**

`simulationStore.ts` 상단에 stage 테이블 추가:
```ts
const STAGES: readonly { at: number; text: string }[] = [
  { at: 0, text: 'INITIALIZING AI ENGINE' },
  { at: 5, text: 'CONNECTING TO DATABASE' },
  { at: 10, text: 'FETCHING KT TELECOM DATA' },
  { at: 20, text: 'ANALYZING COMPETITION DENSITY' },
  { at: 30, text: 'QUERYING POPULATION TRENDS' },
  { at: 40, text: 'CALCULATING RENT-TO-REVENUE RATIO' },
  { at: 50, text: 'ANALYZING CANNIBALIZATION RATE' },
  { at: 60, text: 'CROSS-CHECKING LEGAL RISKS' },
  { at: 70, text: 'RUNNING WHAT-IF SCENARIOS' },
  { at: 80, text: 'GENERATING 12-MONTH FORECAST' },
  { at: 88, text: 'SYNTHESIZING MULTI-AGENT RESULTS' },
];

function stageFor(progress: number): string {
  let current = STAGES[0].text;
  for (const s of STAGES) {
    if (progress >= s.at) current = s.text;
  }
  return current;
}
```

`startSimulation`의 `set({ status: 'running', ... })` 직후에 타이머 시작 추가:
```ts
const timer = setInterval(() => {
  const elapsed = (Date.now() - startedAt) / 1000;
  const p = Math.min(90, elapsed * 0.9);
  set({ progress: p, stage: stageFor(p) });
}, 500);
set({ _progressTimer: timer });
```

성공 `set({ status: 'done', ... })` 직전과 에러 처리 분기에서 타이머 정리:
```ts
const { _progressTimer } = get();
if (_progressTimer) clearInterval(_progressTimer);
// 그리고 set에 _progressTimer: null 포함
```

- [ ] **Step 4: PASS 확인**

- [ ] **Step 5: Prettier + 커밋**

```bash
git add frontend/src/stores/simulationStore.ts frontend/src/stores/simulationStore.test.ts
git commit -m "IM3-205: feat(C1): 진행률 타이머 + 11단계 stage 매핑"
```

---

## Task 9: simulationStore — dismissResult

**Files:**
- Modify: `frontend/src/stores/simulationStore.ts`
- Modify: `frontend/src/stores/simulationStore.test.ts`

- [ ] **Step 1: 테스트 추가**

```ts
describe('simulationStore — dismissResult', () => {
  beforeEach(() => {
    useSimulationStore.getState().reset();
    vi.restoreAllMocks();
  });

  it('done 상태를 idle로 되돌리고 result를 null로 만든다', async () => {
    vi.spyOn(api, 'runSimulation').mockResolvedValue(MOCK_OUTPUT);
    await useSimulationStore.getState().startSimulation(MOCK_INPUT);
    expect(useSimulationStore.getState().status).toBe('done');

    useSimulationStore.getState().dismissResult();
    const s = useSimulationStore.getState();
    expect(s.status).toBe('idle');
    expect(s.result).toBeNull();
  });
});
```

- [ ] **Step 2: FAIL 확인**

- [ ] **Step 3: 구현**

```ts
dismissResult: () => {
  const { status } = get();
  if (status !== 'done' && status !== 'error') return;
  set({
    status: 'idle',
    progress: 0,
    stage: '',
    result: null,
    error: null,
    params: null,
    startedAt: null,
  });
},
```

- [ ] **Step 4: PASS 확인 + 전체 테스트 실행**

실행: `cd frontend && npm test`
기대: 모든 테스트 green

- [ ] **Step 5: Prettier + 커밋**

```bash
git add frontend/src/stores/simulationStore.ts frontend/src/stores/simulationStore.test.ts
git commit -m "IM3-205: feat(C1): dismissResult 구현 + store 완성"
```

---

## Task 10: toastStore — 경량 토스트 큐

**Files:**
- Create: `frontend/src/stores/toastStore.ts`

- [ ] **Step 1: 구현**

```ts
import { create } from 'zustand';

export type ToastVariant = 'success' | 'error' | 'info';

export interface Toast {
  id: string;
  variant: ToastVariant;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  durationMs?: number;
}

interface ToastState {
  toasts: Toast[];
  push: (t: Omit<Toast, 'id'>) => string;
  dismiss: (id: string) => void;
}

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: (t) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const toast: Toast = { durationMs: 5000, ...t, id };
    set({ toasts: [...get().toasts, toast] });
    if (toast.durationMs && toast.durationMs > 0) {
      setTimeout(() => get().dismiss(id), toast.durationMs);
    }
    return id;
  },
  dismiss: (id) => {
    set({ toasts: get().toasts.filter((x) => x.id !== id) });
  },
}));
```

- [ ] **Step 2: Prettier + 커밋**

```bash
cd frontend && npx prettier --write src/stores/toastStore.ts
git add frontend/src/stores/toastStore.ts
git commit -m "IM3-205: feat(C1): 경량 토스트 큐 store"
```

---

## Task 11: ToastHost 컴포넌트

**Files:**
- Create: `frontend/src/components/simulation/ToastHost.tsx`

- [ ] **Step 1: 구현 (Tailwind, SPOTTER cyber 톤)**

```tsx
import { useToastStore } from '@/stores/toastStore';
import { X, CheckCircle2, AlertCircle, Info } from 'lucide-react';

const VARIANT_STYLES: Record<string, { ring: string; icon: JSX.Element }> = {
  success: {
    ring: 'ring-cyan-400/60',
    icon: <CheckCircle2 className="h-5 w-5 text-cyan-400" />,
  },
  error: {
    ring: 'ring-red-500/60',
    icon: <AlertCircle className="h-5 w-5 text-red-400" />,
  },
  info: {
    ring: 'ring-slate-400/60',
    icon: <Info className="h-5 w-5 text-slate-200" />,
  },
};

export function ToastHost() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed top-6 right-6 z-[60] flex flex-col gap-2">
      {toasts.map((t) => {
        const style = VARIANT_STYLES[t.variant] ?? VARIANT_STYLES.info;
        return (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-3 rounded-lg bg-slate-900/95 px-4 py-3 shadow-lg ring-1 ${style.ring} min-w-[280px] max-w-sm text-slate-100`}
          >
            {style.icon}
            <div className="flex-1">
              <div className="text-sm font-semibold">{t.title}</div>
              {t.description && (
                <div className="mt-0.5 text-xs text-slate-300">{t.description}</div>
              )}
              {t.action && (
                <button
                  onClick={() => {
                    t.action!.onClick();
                    dismiss(t.id);
                  }}
                  className="mt-2 text-xs font-medium text-cyan-300 hover:text-cyan-200"
                >
                  {t.action.label} →
                </button>
              )}
            </div>
            <button
              onClick={() => dismiss(t.id)}
              className="text-slate-400 hover:text-slate-200"
              aria-label="닫기"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Prettier + 커밋**

```bash
cd frontend && npx prettier --write src/components/simulation/ToastHost.tsx
git add frontend/src/components/simulation/ToastHost.tsx
git commit -m "IM3-205: feat(C1): ToastHost 컴포넌트"
```

---

## Task 12: useCompletionToast 훅

**Files:**
- Create: `frontend/src/hooks/useCompletionToast.ts`

- [ ] **Step 1: 구현 — status 전이 감지**

```ts
import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSimulationStore, type SimulationStatus } from '@/stores/simulationStore';
import { useToastStore } from '@/stores/toastStore';

export function useCompletionToast() {
  const status = useSimulationStore((s) => s.status);
  const error = useSimulationStore((s) => s.error);
  const push = useToastStore((s) => s.push);
  const navigate = useNavigate();
  const prevRef = useRef<SimulationStatus>('idle');

  useEffect(() => {
    const prev = prevRef.current;
    prevRef.current = status;

    if (prev === 'running' && status === 'done') {
      push({
        variant: 'success',
        title: 'ANALYSIS COMPLETE',
        description: '시뮬레이션 결과가 준비됐습니다.',
        action: { label: '결과 보기', onClick: () => navigate('/simulator') },
      });
    } else if (prev === 'running' && status === 'error') {
      push({
        variant: 'error',
        title: 'SIMULATION FAILED',
        description: error ?? '알 수 없는 오류',
      });
    }
  }, [status, error, push, navigate]);
}
```

- [ ] **Step 2: Prettier + 커밋**

```bash
cd frontend && npx prettier --write src/hooks/useCompletionToast.ts
git add frontend/src/hooks/useCompletionToast.ts
git commit -m "IM3-205: feat(C1): useCompletionToast — 완료/실패 토스트 발화"
```

---

## Task 13: SimulationFloatingWidget

**Files:**
- Create: `frontend/src/components/simulation/SimulationFloatingWidget.tsx`

- [ ] **Step 1: 구현 — 4개 상태 (idle/running/done/error)**

```tsx
import { useNavigate } from 'react-router-dom';
import { useSimulationStore } from '@/stores/simulationStore';
import { X, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';

export function SimulationFloatingWidget() {
  const status = useSimulationStore((s) => s.status);
  const progress = useSimulationStore((s) => s.progress);
  const stage = useSimulationStore((s) => s.stage);
  const startedAt = useSimulationStore((s) => s.startedAt);
  const params = useSimulationStore((s) => s.params);
  const cancel = useSimulationStore((s) => s.cancelSimulation);
  const dismiss = useSimulationStore((s) => s.dismissResult);
  const start = useSimulationStore((s) => s.startSimulation);
  const navigate = useNavigate();

  if (status === 'idle') return null;

  const goToSimulator = () => navigate('/simulator');

  const etaSec = startedAt
    ? Math.max(0, Math.round((90 - progress) / 0.9))
    : 0;

  const baseClasses =
    'fixed bottom-6 right-6 z-50 flex min-w-[280px] max-w-sm flex-col gap-2 rounded-xl bg-slate-900/95 p-4 shadow-2xl ring-1 backdrop-blur';

  if (status === 'running') {
    return (
      <div className={`${baseClasses} ring-cyan-400/60`}>
        <div className="flex items-center gap-2">
          <Loader2 className="h-5 w-5 animate-spin text-cyan-400" />
          <div className="flex-1 text-sm font-semibold text-slate-100">
            SIMULATING {Math.round(progress)}%
          </div>
          <button
            onClick={cancel}
            className="text-slate-400 hover:text-slate-200"
            aria-label="취소"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-slate-700">
          <div
            className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-blue-500 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span className="truncate">{stage}</span>
          <span>ETA ~{etaSec}s</span>
        </div>
        <button
          onClick={goToSimulator}
          className="mt-1 text-xs font-medium text-cyan-300 hover:text-cyan-200 self-start"
        >
          시뮬레이터로 이동 →
        </button>
      </div>
    );
  }

  if (status === 'done') {
    return (
      <div className={`${baseClasses} ring-cyan-400/60`}>
        <div className="flex items-center gap-2">
          <CheckCircle2 className="h-5 w-5 text-cyan-400" />
          <div className="flex-1 text-sm font-semibold text-slate-100">ANALYSIS COMPLETE</div>
          <button
            onClick={dismiss}
            className="text-slate-400 hover:text-slate-200"
            aria-label="닫기"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <button
          onClick={goToSimulator}
          className="rounded-md bg-cyan-500/20 px-3 py-2 text-sm font-medium text-cyan-200 hover:bg-cyan-500/30"
        >
          결과 보기 →
        </button>
      </div>
    );
  }

  // error
  return (
    <div className={`${baseClasses} ring-red-500/60`}>
      <div className="flex items-center gap-2">
        <AlertCircle className="h-5 w-5 text-red-400" />
        <div className="flex-1 text-sm font-semibold text-slate-100">SIMULATION FAILED</div>
        <button
          onClick={dismiss}
          className="text-slate-400 hover:text-slate-200"
          aria-label="닫기"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <button
        onClick={() => params && start(params)}
        disabled={!params}
        className="rounded-md bg-red-500/20 px-3 py-2 text-sm font-medium text-red-200 hover:bg-red-500/30 disabled:opacity-40"
      >
        재시도
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Prettier + 커밋**

```bash
cd frontend && npx prettier --write src/components/simulation/SimulationFloatingWidget.tsx
git add frontend/src/components/simulation/SimulationFloatingWidget.tsx
git commit -m "IM3-205: feat(C1): SimulationFloatingWidget 4개 상태 렌더링"
```

---

## Task 14: BeforeUnloadGuard

**Files:**
- Create: `frontend/src/components/simulation/BeforeUnloadGuard.tsx`

- [ ] **Step 1: 구현**

```tsx
import { useEffect } from 'react';
import { useSimulationStore } from '@/stores/simulationStore';

export function BeforeUnloadGuard() {
  const status = useSimulationStore((s) => s.status);

  useEffect(() => {
    if (status !== 'running') return;

    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      // Chrome requires returnValue to be set
      e.returnValue = '시뮬레이션이 진행 중입니다. 정말 나가시겠어요?';
      return e.returnValue;
    };

    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [status]);

  return null;
}
```

- [ ] **Step 2: Prettier + 커밋**

```bash
cd frontend && npx prettier --write src/components/simulation/BeforeUnloadGuard.tsx
git add frontend/src/components/simulation/BeforeUnloadGuard.tsx
git commit -m "IM3-205: feat(C1): BeforeUnloadGuard — 실행 중 새로고침 경고"
```

---

## Task 15: App.tsx 통합 — 신규 컴포넌트 마운트

**Files:**
- Modify: `frontend/src/App.tsx` (루트 App 컴포넌트 JSX 근처)

- [ ] **Step 1: import 추가 (파일 상단)**

`frontend/src/App.tsx` 상단 import 섹션에 추가:
```ts
import { SimulationFloatingWidget } from './components/simulation/SimulationFloatingWidget';
import { BeforeUnloadGuard } from './components/simulation/BeforeUnloadGuard';
import { ToastHost } from './components/simulation/ToastHost';
import { useCompletionToast } from './hooks/useCompletionToast';
```

- [ ] **Step 2: 루트 App 컴포넌트에 훅 + 컴포넌트 주입**

루트 컴포넌트(BrowserRouter/Routes를 렌더하는 곳) 내부에서:
```tsx
function RootShell() {
  useCompletionToast();  // 훅은 BrowserRouter 내부에서만 useNavigate 사용 가능
  return (
    <>
      <Routes>{/* 기존 라우트 */}</Routes>
      <SimulationFloatingWidget />
      <BeforeUnloadGuard />
      <ToastHost />
    </>
  );
}
```

구체적 위치: `<BrowserRouter>` 직계 children 자리에 `<RootShell />` 배치.

**주의**: `useCompletionToast`는 `useNavigate`를 사용하므로 반드시 `<BrowserRouter>` **안쪽** 컴포넌트에서 호출해야 함.

- [ ] **Step 3: 빌드 타입 체크**

실행: `cd frontend && npx tsc --noEmit`
기대: 에러 없음

- [ ] **Step 4: 개발 서버 실행 → 위젯 렌더 확인**

실행: `cd frontend && npm run dev`
브라우저에서 /simulator 접속. 아직 store와 연결 안 됐으므로 위젯 안 보여야 정상.

- [ ] **Step 5: Prettier + 커밋**

```bash
cd frontend && npx prettier --write src/App.tsx
git add frontend/src/App.tsx
git commit -m "IM3-205: feat(C1): App 루트에 플로팅 위젯·가드·ToastHost 마운트"
```

---

## Task 16: App.tsx — runSim → store.startSimulation 교체

**Files:**
- Modify: `frontend/src/App.tsx:2478-2615` (runSim 함수 + 로딩 진행률 useEffect)

- [ ] **Step 1: 기존 코드 확인 (2478줄 runSim, 2577-2615 진행률 useEffect)**

Read 명령으로 정확한 범위 확인 후 작업:
```bash
# 참고: 정확한 라인 번호는 수정 시점에 재확인
```

- [ ] **Step 2: runSim 함수 내부 교체**

`useCallback` 내부를 store 호출로 교체:
```tsx
const runSim = useCallback(async () => {
  // 기존: setReportState('loading'), setLoadingProgress(0), ...
  //       const data = await runSimulation(payload);
  //       setSimResult(mapped); setReportState('result');

  // 교체:
  const payload: SimulationInput = {
    /* 기존 payload 조립 로직 그대로 유지 */
  };
  await useSimulationStore.getState().startSimulation(payload);
  // 결과는 store 구독 셀렉터로 자동 반영됨 (Task 17에서 useState → 셀렉터 교체)
}, [/* 기존 의존성 */]);
```

import 추가:
```ts
import { useSimulationStore } from './stores/simulationStore';
```

- [ ] **Step 3: 기존 진행률 타이머 useEffect 삭제**

`frontend/src/App.tsx:2577-2615` 의 `setLoadingProgress`/`setLoadingText`를 돌리는 `useEffect` 블록 **통째로 삭제**. (store 내부 타이머로 이관됨)

- [ ] **Step 4: Prettier + 커밋**

```bash
cd frontend && npx prettier --write src/App.tsx
git add frontend/src/App.tsx
git commit -m "IM3-205: refactor(C1): runSim을 simulationStore.startSimulation으로 교체"
```

---

## Task 17: App.tsx — 로컬 useState 4개를 store 셀렉터로 교체

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 교체 대상 식별**

- `App.tsx:6014` — `const [reportState, setReportState] = useState<...>('idle');`
- `App.tsx:2141` — `const [loadingText, setLoadingText] = useState(...);`
- `App.tsx:2142` — `const [loadingProgress, setLoadingProgress] = useState(0);`
- `App.tsx:2145` — `const [simResult, setSimResult] = useState<SimResult | null>(null);`

- [ ] **Step 2: store 셀렉터 도입**

각 `useState`를 삭제하고 다음으로 교체:
```ts
// 예: SimulatorDashboard 내부
const status = useSimulationStore((s) => s.status);
const progress = useSimulationStore((s) => s.progress);
const stage = useSimulationStore((s) => s.stage);
const result = useSimulationStore((s) => s.result);

// reportState 매핑 (기존 'idle'|'loading'|'result')
const reportState: 'idle' | 'loading' | 'result' =
  status === 'running' ? 'loading' : status === 'done' && result ? 'result' : 'idle';

// 기존 simResult 사용처는 result로 교체. 단, 기존 camelCase SimResult 구조 매핑이 존재한다면
// 매핑 로직을 유지하되 입력을 store.result로 변경
```

기존 `SimResult` 매핑 로직이 있다면(App.tsx:70 타입 참조), `SimulationOutput → SimResult` 매핑 함수를 `useMemo`로 감싸 그대로 유지:
```ts
const simResult = useMemo(
  () => (result ? mapOutputToSimResult(result) : null),
  [result],
);
```

기존 `setSimResult(mapped)` 호출 라인은 삭제 (store가 담당).

- [ ] **Step 3: setState 호출부 정리**

전역 grep으로 남은 `setReportState`, `setLoadingText`, `setLoadingProgress`, `setSimResult` 호출을 찾아 각각:
- `setReportState('loading')` → store.startSimulation에서 자동 처리. 해당 라인 삭제
- `setReportState('result')` → store.startSimulation의 성공 경로에서 자동. 삭제
- `setReportState('idle')` → store.dismissResult() 또는 store.cancelSimulation() 호출로 대체
- `setLoadingText(x)` / `setLoadingProgress(x)` → store에서 자동 계산. 삭제

- [ ] **Step 4: Props로 전달되던 reportState 등이 있다면 셀렉터로 교체**

`reportState: 'loading' | 'result' | 'idle'` props를 자식 컴포넌트로 내려주던 경로(예: `App.tsx:2132, 2135`)가 있다면, 자식에서도 동일하게 store 셀렉터로 직접 구독하도록 변경하여 **props drilling 제거**.

- [ ] **Step 5: 빌드 + 타입 체크**

실행: `cd frontend && npx tsc --noEmit && npm run build`
기대: 에러 없음

- [ ] **Step 6: Prettier + 커밋**

```bash
cd frontend && npx prettier --write src/App.tsx
git add frontend/src/App.tsx
git commit -m "IM3-205: refactor(C1): SimulatorDashboard 로컬 useState 4개를 store 셀렉터로 이관"
```

---

## Task 18: 수동 QA + 통합 검증

**Files:** (코드 변경 없음)

- [ ] **Step 1: 개발 서버 가동 + 수동 체크리스트**

실행: `cd frontend && npm run dev`

체크리스트 (모두 PASS해야 완료):
1. `/simulator` 진입 → RUN SIMULATION 버튼 클릭 → 진행률 증가 확인
2. 실행 중 `/explore`로 이동 → 우측 하단 플로팅 위젯 표시, 진행률 계속 증가
3. `/explore`에 있는 동안 시뮬레이션 완료 → 우측 상단 "ANALYSIS COMPLETE" 토스트 + 위젯이 "결과 보기" 버튼으로 전환
4. "결과 보기" 클릭 → `/simulator`로 이동, 결과 화면 즉시 표시 (재실행 안 함)
5. 실행 중 조건 바꾸고 RUN 재클릭 → 이전 요청 취소되고 progress 0부터 재시작
6. 실행 중 브라우저 새로고침 시도 → confirm 경고창 노출
7. 실행 중 위젯의 X(취소) 버튼 클릭 → 즉시 중단, 위젯 사라짐
8. 네트워크 차단 후 RUN → 위젯 "SIMULATION FAILED" + 재시도 버튼
9. 재시도 버튼 클릭 → 같은 params로 재실행
10. 완료 후 위젯 X 클릭 → 위젯 사라짐, 결과는 /simulator에 유지

- [ ] **Step 2: 전체 테스트 + 빌드 최종 확인**

실행:
```bash
cd frontend && npm test && npm run build
```
기대: 전부 PASS, 빌드 경고 없음

- [ ] **Step 3: Lint + format 체크**

```bash
cd frontend && npm run lint && npm run format:check
```
기대: 에러 없음

- [ ] **Step 4: 최종 커밋 (필요한 경우)**

위 과정에서 추가 수정이 생기면:
```bash
git add -p  # 변경사항 선택적 add
git commit -m "IM3-205: fix(C1): QA 피드백 반영"
```

- [ ] **Step 5: PR 준비 안내**

변경 요약:
- 신규 4 컴포넌트 + 2 store + 1 훅 + 테스트 인프라
- App.tsx의 시뮬레이션 실행/상태 로직을 store로 이관
- 기존 API 시그니처는 옵셔널 파라미터 추가로 호환 유지

PR 제목 형식: `IM3-205: 시뮬레이션 백그라운드 실행 추적 — 페이지 이동 시에도 진행 유지`

---

## 완료 기준 (스펙 12장과 매핑)

| # | 기준 | Task |
|---|------|------|
| 1 | 페이지 이동 후에도 시뮬레이션 계속 진행 | 4, 15 |
| 2 | 다른 페이지에서 플로팅 위젯으로 진행률 확인 | 8, 13, 15 |
| 3 | 완료 순간 토스트 + 위젯 전환 | 11, 12, 13 |
| 4 | 위젯 클릭 시 /simulator 복귀 + 결과 즉시 표시 | 13, 17 |
| 5 | 실행 중 RUN 재클릭 시 취소·교체 | 7 |
| 6 | 진행 중 새로고침 시 경고창 | 14 |
| 7 | 실패 시 FAILED + 재시도 | 5, 13 |
| 8 | 로컬 useState 4개 store 이관 | 17 |
