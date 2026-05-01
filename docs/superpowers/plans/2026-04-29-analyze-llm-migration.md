# /predict + /analyze/llm 분리 호출 마이그레이션 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 `/simulate` 단일 호출을 `/predict` + `/analyze/llm` 두 endpoint **병렬 호출** 로 마이그레이션. 응답을 `SimulationOutput` 형태로 합성해 기존 컴포넌트 호환성 보존, 부분 성공 허용.

**Architecture:** zustand store 에 `prediction` / `analysis` 두 슬라이스 분리. `Promise.allSettled` 로 병렬 fetch. `useCombinedSimResult` hook 이 useMemo 로 두 슬라이스를 `SimulationOutput` 호환 객체로 합성 → 기존 컴포넌트 prop 인터페이스 보존. 한쪽 실패 시 그 슬라이스만 재시도.

**Tech Stack:** React 18 + TypeScript + zustand 4.x + axios + vitest + Vite + Tailwind

**관련 spec:** `docs/superpowers/specs/2026-04-29-analyze-llm-migration-design.md`

---

## File Structure

| 파일 | 역할 | 상태 |
|------|------|------|
| `frontend/src/types/index.ts` | `DistrictPredictionResult`, `AnalysisOutput` 타입 추가 + `district_predictions` field 추가 | Modify |
| `frontend/src/api/client.ts` | `fetchPredict`, `fetchAnalyzeLlm` 함수 추가. 기존 `simulate()` 는 deprecated 주석 | Modify |
| `frontend/src/stores/simulationStore.ts` | `prediction` / `analysis` 슬라이스 분리. `startSimulation` Promise.allSettled 흐름 | Modify |
| `frontend/src/stores/simulationStore.test.ts` | Promise.allSettled 분기 (둘 다 ok / 둘 다 fail / 부분 성공) 테스트 추가 | Modify |
| `frontend/src/hooks/useCombinedSimResult.ts` | useMemo 합성 selector hook. `buildCombinedResult` helper 포함 | **Create** |
| `frontend/src/hooks/useCombinedSimResult.test.tsx` | hook 단위 테스트 — 합성 정합성 + 부분 데이터 케이스 | **Create** |
| `frontend/src/App.tsx` | 두 곳의 store 호출 (`SimulatorDashboard` + `DashboardOutlet` + `DashboardHubRouteElement`) 을 `useCombinedSimResult` 로 교체 | Modify |
| `frontend/src/components/simulation/SimulationFloatingWidget.tsx` | 부분 실패 UI — 한쪽 슬라이스만 실패 시 재시도 버튼 (`fetchPredict` / `fetchAnalyzeLlm` 단독 재호출) | Modify |
| `frontend/src/components/SimulationResult/sections/DistrictRankings.tsx` | `is_excluded_combo: true` 동에 "예측 불가" 배지 + 회색 처리 | Modify |

**범위 외**:
- `/history/save` 별도 endpoint — B1 sub-task. plan 에 포함 X.
- 영향 없는 컴포넌트 (DashboardHub / PredictGroup 5 서브탭 / AnalyzeGroup 5 서브탭 / AbmGroup / MapSection / MarketMap) — 합성된 `SimulationOutput` 그대로 받으므로 변경 0.

---

## Task 1: 타입 추가 (DistrictPredictionResult, AnalysisOutput)

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 신규 타입 정의 추가**

`types/index.ts` 파일 끝에 추가:

```typescript
/** /predict 응답의 동별 예측 entry. spec §3 + B1 schemas/simulation_output.py 의 DistrictPredictionResult 매칭. */
export interface DistrictPredictionResult {
  district: string;
  is_excluded_combo: boolean;
  quarterly_projection?: QuarterlyProjection;
  closure_risk?: ClosureRisk;
  shap_result?: ShapResult;
  bep_months?: number | null;
  predicted_monthly_revenue?: number | null;
}

/** /analyze/llm 응답. SimulationOutput 의 ML 필드 빠진 subset. spec §3. */
export type AnalysisOutput = Omit<
  SimulationOutput,
  | 'quarterly_projection'
  | 'closure_risk'
  | 'shap_result'
  | 'bep_months'
  | 'predicted_monthly_revenue'
  | 'district_predictions'
>;
```

`SimulationOutput` 자체에 `district_predictions` 필드 추가:

```typescript
// SimulationOutput interface 안:
district_predictions?: DistrictPredictionResult[];
```

- [ ] **Step 2: tsc 검증**

Run:
```bash
cd /c/mapo-franchise-simulator/frontend && npx tsc --noEmit
```
Expected: EXIT=0. 기존 컴포넌트 영향 없음 (district_predictions 는 optional).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): DistrictPredictionResult + AnalysisOutput 추가

B1 IM3-259 schema 매칭. SimulationOutput 에 district_predictions
optional field 추가 — /predict 응답 합성 시 사용."
```

---

## Task 2: api/client 함수 추가 (fetchPredict, fetchAnalyzeLlm)

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: 두 함수 추가**

`api/client.ts` 의 `simulate()` 함수 다음에 추가:

```typescript
import type { DistrictPredictionResult, AnalysisOutput } from '../types';

/** ML 예측 — /predict (선택 동 1~4 병렬). 사용자 입력 그대로 받음. */
export async function fetchPredict(input: SimulationInput): Promise<DistrictPredictionResult[]> {
  const response = await apiClient.post('/predict', input);
  // 응답 형태: { results: DistrictPredictionResult[] } 또는 list — backend 확정 시 unwrap.
  const body = response.data;
  if (Array.isArray(body)) return body;
  if (body && Array.isArray(body.results)) return body.results;
  return [];
}

/** AI 분석 — /analyze/llm (winner 산출 + LLM 6 에이전트). */
export async function fetchAnalyzeLlm(input: SimulationInput): Promise<AnalysisOutput> {
  const response = await apiClient.post('/analyze/llm', input);
  return response.data as AnalysisOutput;
}
```

기존 `simulate()` 위에 deprecated 주석 추가:

```typescript
/**
 * @deprecated 2026-04-29 IM3-259 — /predict + /analyze/llm 분리 호출로 마이그레이션 진행 중.
 * 이 함수는 history detail 복원 등 fallback 경로에서만 사용. 신규 시뮬은 fetchPredict + fetchAnalyzeLlm 사용.
 */
export async function simulate(input: SimulationInput): Promise<SimulationOutput> {
```

- [ ] **Step 2: tsc 검증**

Run:
```bash
cd /c/mapo-franchise-simulator/frontend && npx tsc --noEmit
```
Expected: EXIT=0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(api): fetchPredict + fetchAnalyzeLlm 추가

IM3-259 분리 호출. 기존 simulate() 는 deprecated 표시 (history 복원 fallback 용)."
```

---

## Task 3: simulationStore 슬라이스 분리 + Promise.allSettled

**Files:**
- Modify: `frontend/src/stores/simulationStore.ts`
- Test: `frontend/src/stores/simulationStore.test.ts`

- [ ] **Step 1: store 인터페이스 + 슬라이스 추가**

`simulationStore.ts` 의 store interface 변경:

```typescript
import type {
  SimulationInput,
  SimulationOutput,
  DistrictPredictionResult,
  AnalysisOutput,
} from '../types';

export type SliceStatus = 'idle' | 'running' | 'done' | 'error';

interface PredictionSlice {
  status: SliceStatus;
  data: DistrictPredictionResult[] | null;
  error: string | null;
}

interface AnalysisSlice {
  status: SliceStatus;
  data: AnalysisOutput | null;
  error: string | null;
}

export interface SimulationStore {
  // 합성 status (둘 다 fulfilled → done, 둘 다 rejected → error, 한쪽만 fulfilled → done)
  status: 'idle' | 'running' | 'done' | 'error';
  progress: number;
  stage: string;
  params: SimulationInput | null;
  startedAt: number | null;
  savedHistoryId: number | null;
  // result 는 deprecated — useCombinedSimResult() hook 사용
  /** @deprecated useCombinedSimResult() hook 사용. */
  result: SimulationOutput | null;
  error: string | null;

  // 신규 슬라이스
  prediction: PredictionSlice;
  analysis: AnalysisSlice;

  // actions
  startSimulation: (params: SimulationInput) => Promise<void>;
  retryPrediction: () => Promise<void>; // 부분 실패 재시도
  retryAnalysis: () => Promise<void>;
  dismissResult: () => void;
  setSavedHistoryId: (id: number | null) => void;
  cancelSimulation: () => void;
}
```

initial state:

```typescript
const initialPrediction: PredictionSlice = { status: 'idle', data: null, error: null };
const initialAnalysis: AnalysisSlice = { status: 'idle', data: null, error: null };
```

- [ ] **Step 2: startSimulation 변경 — Promise.allSettled**

기존 `startSimulation: async (params) => { ... }` 본문을 다음으로 교체:

```typescript
startSimulation: async (params) => {
  set({
    status: 'running',
    progress: 0,
    stage: '병렬 호출 시작',
    params,
    startedAt: Date.now(),
    savedHistoryId: null,
    result: null,
    error: null,
    prediction: { status: 'running', data: null, error: null },
    analysis: { status: 'running', data: null, error: null },
  });

  const [predResult, analysisResult] = await Promise.allSettled([
    fetchPredict(params),
    fetchAnalyzeLlm(params),
  ]);

  const predSlice: PredictionSlice =
    predResult.status === 'fulfilled'
      ? { status: 'done', data: predResult.value, error: null }
      : { status: 'error', data: null, error: predResult.reason?.message ?? '예측 실패' };

  const analysisSlice: AnalysisSlice =
    analysisResult.status === 'fulfilled'
      ? { status: 'done', data: analysisResult.value, error: null }
      : { status: 'error', data: null, error: analysisResult.reason?.message ?? '분석 실패' };

  const allFailed = predSlice.status === 'error' && analysisSlice.status === 'error';

  set({
    prediction: predSlice,
    analysis: analysisSlice,
    status: allFailed ? 'error' : 'done',
    progress: 100,
    stage: allFailed ? '시뮬 실패' : '완료',
    error: allFailed
      ? `예측/분석 모두 실패: ${predSlice.error} | ${analysisSlice.error}`
      : null,
  });
},
```

- [ ] **Step 3: retryPrediction / retryAnalysis 추가**

```typescript
retryPrediction: async () => {
  const params = get().params;
  if (!params) return;
  set({ prediction: { status: 'running', data: null, error: null } });
  try {
    const data = await fetchPredict(params);
    set({ prediction: { status: 'done', data, error: null } });
  } catch (e) {
    const msg = e instanceof Error ? e.message : '예측 재시도 실패';
    set({ prediction: { status: 'error', data: null, error: msg } });
  }
},

retryAnalysis: async () => {
  const params = get().params;
  if (!params) return;
  set({ analysis: { status: 'running', data: null, error: null } });
  try {
    const data = await fetchAnalyzeLlm(params);
    set({ analysis: { status: 'done', data, error: null } });
  } catch (e) {
    const msg = e instanceof Error ? e.message : '분석 재시도 실패';
    set({ analysis: { status: 'error', data: null, error: msg } });
  }
},
```

- [ ] **Step 4: dismissResult 변경**

```typescript
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
    savedHistoryId: null,
    prediction: initialPrediction,
    analysis: initialAnalysis,
  });
},
```

- [ ] **Step 5: 테스트 추가**

`simulationStore.test.ts` 에 새 describe 블록 추가:

```typescript
import { vi } from 'vitest';
import * as apiClient from '../api/client';

describe('simulationStore — Promise.allSettled', () => {
  beforeEach(() => {
    useSimulationStore.setState({
      status: 'idle',
      prediction: { status: 'idle', data: null, error: null },
      analysis: { status: 'idle', data: null, error: null },
    });
    vi.restoreAllMocks();
  });

  it('둘 다 성공 → status=done, 두 슬라이스 done', async () => {
    vi.spyOn(apiClient, 'fetchPredict').mockResolvedValue([
      { district: '공덕동', is_excluded_combo: false } as any,
    ]);
    vi.spyOn(apiClient, 'fetchAnalyzeLlm').mockResolvedValue({
      winner_district: '공덕동',
    } as any);

    await useSimulationStore.getState().startSimulation({ districts: ['공덕동'] } as any);

    const s = useSimulationStore.getState();
    expect(s.status).toBe('done');
    expect(s.prediction.status).toBe('done');
    expect(s.analysis.status).toBe('done');
    expect(s.prediction.data).toHaveLength(1);
    expect(s.analysis.data?.winner_district).toBe('공덕동');
  });

  it('predict 만 실패 → status=done (부분 성공), prediction.status=error', async () => {
    vi.spyOn(apiClient, 'fetchPredict').mockRejectedValue(new Error('predict 5xx'));
    vi.spyOn(apiClient, 'fetchAnalyzeLlm').mockResolvedValue({ winner_district: '공덕동' } as any);

    await useSimulationStore.getState().startSimulation({ districts: ['공덕동'] } as any);

    const s = useSimulationStore.getState();
    expect(s.status).toBe('done');
    expect(s.prediction.status).toBe('error');
    expect(s.prediction.error).toContain('predict 5xx');
    expect(s.analysis.status).toBe('done');
  });

  it('둘 다 실패 → status=error', async () => {
    vi.spyOn(apiClient, 'fetchPredict').mockRejectedValue(new Error('p fail'));
    vi.spyOn(apiClient, 'fetchAnalyzeLlm').mockRejectedValue(new Error('a fail'));

    await useSimulationStore.getState().startSimulation({ districts: ['공덕동'] } as any);

    const s = useSimulationStore.getState();
    expect(s.status).toBe('error');
    expect(s.error).toContain('p fail');
    expect(s.error).toContain('a fail');
  });

  it('retryPrediction 만 재호출 → analysis 슬라이스 보존', async () => {
    useSimulationStore.setState({
      params: { districts: ['공덕동'] } as any,
      prediction: { status: 'error', data: null, error: 'previous fail' },
      analysis: { status: 'done', data: { winner_district: '공덕동' } as any, error: null },
      status: 'done',
    });
    vi.spyOn(apiClient, 'fetchPredict').mockResolvedValue([
      { district: '공덕동', is_excluded_combo: false } as any,
    ]);

    await useSimulationStore.getState().retryPrediction();

    const s = useSimulationStore.getState();
    expect(s.prediction.status).toBe('done');
    expect(s.analysis.status).toBe('done'); // 보존
    expect(s.analysis.data?.winner_district).toBe('공덕동');
  });
});
```

- [ ] **Step 6: 테스트 실행 + tsc**

Run:
```bash
cd /c/mapo-franchise-simulator/frontend && npx vitest run src/stores/simulationStore.test.ts
```
Expected: 4 신규 테스트 통과. 기존 dismissResult 테스트도 통과.

```bash
npx tsc --noEmit
```
Expected: EXIT=0.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/stores/simulationStore.ts frontend/src/stores/simulationStore.test.ts
git commit -m "feat(store): prediction + analysis 슬라이스 분리

Promise.allSettled 로 /predict + /analyze/llm 병렬 호출. 부분 성공 허용.
retryPrediction/retryAnalysis 로 슬라이스별 재호출 가능.

기존 result field 는 useCombinedSimResult() 가 합성 — deprecated 표시."
```

---

## Task 4: useCombinedSimResult hook 신설

**Files:**
- Create: `frontend/src/hooks/useCombinedSimResult.ts`
- Create: `frontend/src/hooks/useCombinedSimResult.test.tsx`

- [ ] **Step 1: hook 파일 작성**

`frontend/src/hooks/useCombinedSimResult.ts` 신규:

```typescript
import { useMemo } from 'react';
import type {
  SimulationOutput,
  DistrictPredictionResult,
  AnalysisOutput,
} from '../types';
import { useSimulationStore } from '../stores/simulationStore';

/**
 * /predict + /analyze/llm 두 슬라이스를 SimulationOutput 호환 객체로 합성.
 * 기존 컴포넌트가 simResult 받는 prop 인터페이스 보존 → 변경 0.
 *
 * 부분 데이터 케이스:
 * - analysis 만 있음 (prediction 실패): ML 필드는 undefined, AI 분석 영역만 표시.
 * - prediction 만 있음 (analysis 실패): winner_district 없으므로 사용자 입력 동 기준.
 * - 둘 다 없음: null 반환.
 */
export function buildCombinedResult(
  prediction: DistrictPredictionResult[] | null,
  analysis: AnalysisOutput | null,
  fallbackTargetDistrict: string | undefined,
): SimulationOutput | null {
  if (!analysis && !prediction) return null;

  // winner 동 결정 — analysis 우선, 없으면 prediction 의 첫 entry 또는 fallback
  const winner =
    analysis?.winner_district ??
    prediction?.find((p) => !p.is_excluded_combo)?.district ??
    fallbackTargetDistrict ??
    null;

  // winner 동의 ML 필드 추출 (없으면 undefined)
  const winnerPred = prediction?.find((p) => p.district === winner && !p.is_excluded_combo);

  return {
    ...(analysis ?? ({} as AnalysisOutput)),
    quarterly_projection: winnerPred?.quarterly_projection ?? null,
    closure_risk: winnerPred?.closure_risk ?? null,
    shap_result: winnerPred?.shap_result ?? null,
    bep_months: winnerPred?.bep_months ?? null,
    predicted_monthly_revenue: winnerPred?.predicted_monthly_revenue ?? null,
    district_predictions: prediction ?? [],
  } as SimulationOutput;
}

/**
 * Combined SimulationOutput selector hook. zustand subscribe + useMemo.
 *
 * 기존 패턴 `useSimulationStore((s) => s.result)` 의 직접 대체.
 */
export function useCombinedSimResult(): SimulationOutput | null {
  const prediction = useSimulationStore((s) => s.prediction.data);
  const analysis = useSimulationStore((s) => s.analysis.data);
  const params = useSimulationStore((s) => s.params);

  return useMemo(
    () => buildCombinedResult(prediction, analysis, params?.target_district ?? undefined),
    [prediction, analysis, params],
  );
}
```

- [ ] **Step 2: 단위 테스트 작성**

`frontend/src/hooks/useCombinedSimResult.test.tsx` 신규:

```typescript
import { describe, it, expect } from 'vitest';
import { buildCombinedResult } from './useCombinedSimResult';

describe('buildCombinedResult', () => {
  it('둘 다 null → null', () => {
    expect(buildCombinedResult(null, null, undefined)).toBeNull();
  });

  it('analysis 만 있음 → ML 필드 null, winner=analysis.winner', () => {
    const result = buildCombinedResult(
      null,
      { winner_district: '공덕동', target_district: '공덕동' } as any,
      undefined,
    );
    expect(result?.winner_district).toBe('공덕동');
    expect(result?.quarterly_projection).toBeNull();
    expect(result?.closure_risk).toBeNull();
    expect(result?.district_predictions).toEqual([]);
  });

  it('prediction 만 있음 → winner=fallback, ML 필드는 첫 비-excluded entry', () => {
    const pred = [
      { district: '공덕동', is_excluded_combo: false, bep_months: 12 } as any,
    ];
    const result = buildCombinedResult(pred, null, '공덕동');
    expect(result?.winner_district).toBeUndefined(); // analysis 없음
    expect(result?.bep_months).toBe(12);
    expect(result?.district_predictions).toEqual(pred);
  });

  it('둘 다 있음 → winner=analysis 기준 ML 추출', () => {
    const pred = [
      { district: '공덕동', is_excluded_combo: false, bep_months: 12 } as any,
      { district: '합정동', is_excluded_combo: false, bep_months: 18 } as any,
    ];
    const analysis = { winner_district: '합정동', target_district: '공덕동' } as any;
    const result = buildCombinedResult(pred, analysis, '공덕동');
    expect(result?.winner_district).toBe('합정동');
    expect(result?.bep_months).toBe(18); // 합정동의 ML 추출
  });

  it('winner 가 excluded → ML 필드 null', () => {
    const pred = [
      { district: '공덕동', is_excluded_combo: true } as any,
    ];
    const analysis = { winner_district: '공덕동' } as any;
    const result = buildCombinedResult(pred, analysis, undefined);
    expect(result?.winner_district).toBe('공덕동');
    expect(result?.bep_months).toBeNull(); // excluded 라 추출 안 됨
  });
});
```

- [ ] **Step 3: 테스트 실행**

Run:
```bash
cd /c/mapo-franchise-simulator/frontend && npx vitest run src/hooks/useCombinedSimResult.test.tsx
```
Expected: 5 테스트 모두 통과.

- [ ] **Step 4: tsc 검증**

```bash
npx tsc --noEmit
```
Expected: EXIT=0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useCombinedSimResult.ts frontend/src/hooks/useCombinedSimResult.test.tsx
git commit -m "feat(hook): useCombinedSimResult 신설

prediction + analysis 두 슬라이스를 SimulationOutput 호환 객체로 합성.
buildCombinedResult helper 단위 테스트 5종 (null/단독/병합/excluded winner)."
```

---

## Task 5: App.tsx store 호출처 교체

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 호출처 grep 으로 식별**

Run:
```bash
cd /c/mapo-franchise-simulator/frontend && grep -n "useSimulationStore((s) => s.result)" src/App.tsx
```
예상 hits: SimulatorDashboard 안 1곳 + DashboardOutlet 안 1곳 + DashboardHubRouteElement 안 1곳 = 총 3곳.

- [ ] **Step 2: SimulatorDashboard 교체**

`App.tsx` 의 `SimulatorDashboard` 함수 안 (대략 L1290~1300):

before:
```typescript
const [rawSimResult, setRawSimResult] = useState<SimulationOutput | null>(null);
// ... mount-restore effect 안에서 store.result 사용
```

after — store.result 대신 useCombinedSimResult 도입은 mount-restore 영향 검토 후 진행. 우선 mount-restore 의 store 조회만 새 슬라이스 기반으로 변경:

```typescript
// 기존 mount-restore 안의:
//   if (reportState === 'idle' && s.status === 'done' && s.result)
// 변경:
//   const combined = buildCombinedResult(s.prediction.data, s.analysis.data, s.params?.target_district);
//   if (reportState === 'idle' && s.status === 'done' && combined)
import { buildCombinedResult } from './hooks/useCombinedSimResult';
// ...
useEffect(() => {
  const s = useSimulationStore.getState();
  const combined = buildCombinedResult(
    s.prediction.data,
    s.analysis.data,
    s.params?.target_district ?? undefined,
  );
  if (reportState === 'idle' && s.status === 'done' && combined) {
    setRawSimResult(combined);
    setSimResult(toSimResultViewModel(combined));
    setReportState('result');
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, []);
```

L1419 의 시뮬 완료 후 `simRes = storeState.result;` 도 변경:

before:
```typescript
const simRes = storeState.result;
```

after:
```typescript
const simRes = buildCombinedResult(
  storeState.prediction.data,
  storeState.analysis.data,
  storeState.params?.target_district ?? undefined,
);
if (!simRes) {
  throw new Error(storeState.error ?? 'Simulation failed');
}
```

- [ ] **Step 3: DashboardOutlet 교체**

`App.tsx:DashboardOutlet` 함수 변경:

before:
```typescript
function DashboardOutlet() {
  const simResult = useSimulationStore((s) => s.result);
  ...
```

after:
```typescript
import { useCombinedSimResult } from './hooks/useCombinedSimResult';

function DashboardOutlet() {
  const simResult = useCombinedSimResult();
  ...
```

- [ ] **Step 4: DashboardHubRouteElement 교체**

`App.tsx:DashboardHubRouteElement` 함수 동일하게:

before:
```typescript
function DashboardHubRouteElement() {
  const simResult = useSimulationStore((s) => s.result);
  ...
```

after:
```typescript
function DashboardHubRouteElement() {
  const simResult = useCombinedSimResult();
  ...
```

- [ ] **Step 5: tsc 검증 + grep**

```bash
npx tsc --noEmit
```
Expected: EXIT=0.

```bash
grep -n "useSimulationStore((s) => s.result)" src/App.tsx
```
Expected: 매칭 0건 (모두 교체됨).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "refactor(app): useCombinedSimResult 으로 store.result 직접 조회 교체

3 호출처 (SimulatorDashboard mount-restore + 시뮬 완료 콜백 + DashboardOutlet
+ DashboardHubRouteElement) 모두 변경. buildCombinedResult 합성 결과 사용."
```

---

## Task 6: SimulationFloatingWidget 부분 실패 UI

**Files:**
- Modify: `frontend/src/components/simulation/SimulationFloatingWidget.tsx`

- [ ] **Step 1: 부분 실패 분기 추가**

`SimulationFloatingWidget.tsx` 의 status='done' 단계 (현재 widget hide) 와 status='error' 단계 사이에 부분 실패 케이스 추가:

```typescript
import { Activity, Play, RefreshCw } from 'lucide-react';

export function SimulationFloatingWidget() {
  const status = useSimulationStore((s) => s.status);
  const predStatus = useSimulationStore((s) => s.prediction.status);
  const analysisStatus = useSimulationStore((s) => s.analysis.status);
  const predError = useSimulationStore((s) => s.prediction.error);
  const analysisError = useSimulationStore((s) => s.analysis.error);
  const retryPrediction = useSimulationStore((s) => s.retryPrediction);
  const retryAnalysis = useSimulationStore((s) => s.retryAnalysis);
  // ... 기존 hooks

  if (status === 'idle' || status === 'done') {
    // 둘 다 ok 면 widget hide. 단 부분 실패 면 표시.
    const hasPartialFail = predStatus === 'error' || analysisStatus === 'error';
    if (!hasPartialFail) return null;
    return (
      <div className={`${baseClasses} ring-amber-500/60`}>
        <div className="flex items-center gap-2 mb-2">
          <Activity className="h-5 w-5 text-amber-400" />
          <div className="flex-1 text-sm font-semibold text-slate-100">PARTIAL SUCCESS</div>
        </div>
        {predStatus === 'error' && (
          <div className="mb-2 text-xs text-rose-300">
            ML 예측 실패: {predError?.slice(0, 60)}
            <button
              type="button"
              onClick={() => retryPrediction()}
              className="ml-2 inline-flex items-center gap-1 rounded border border-rose-500/40 px-2 py-0.5 text-[11px] text-rose-200 hover:bg-rose-500/10"
            >
              <RefreshCw className="h-3 w-3" /> 재시도
            </button>
          </div>
        )}
        {analysisStatus === 'error' && (
          <div className="mb-2 text-xs text-rose-300">
            AI 분석 실패: {analysisError?.slice(0, 60)}
            <button
              type="button"
              onClick={() => retryAnalysis()}
              className="ml-2 inline-flex items-center gap-1 rounded border border-rose-500/40 px-2 py-0.5 text-[11px] text-rose-200 hover:bg-rose-500/10"
            >
              <RefreshCw className="h-3 w-3" /> 재시도
            </button>
          </div>
        )}
      </div>
    );
  }
  // ... 기존 running / error 분기
```

- [ ] **Step 2: tsc 검증**

```bash
npx tsc --noEmit
```
Expected: EXIT=0.

- [ ] **Step 3: 수동 검증 (개발 서버)**

코드상으로는 끝. 강민이 dev 서버에서 시뮬 돌려 부분 실패 시뮬레이션:
- backend 일시 중단 후 시뮬 돌리거나, network throttle 로 timeout 유도

자동 검증 어려우므로 코드 리뷰 통과 후 commit.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/simulation/SimulationFloatingWidget.tsx
git commit -m "feat(widget): 부분 실패 UI + 슬라이스별 재시도 버튼

predStatus/analysisStatus 둘 중 하나만 error 면 PARTIAL SUCCESS 토스트 표시.
재시도 버튼 → retryPrediction / retryAnalysis store action 호출.
기존 running/done/error 분기 보존."
```

---

## Task 7: ExcludedCombo 시각화 (DistrictRankings)

**Files:**
- Modify: `frontend/src/components/SimulationResult/sections/DistrictRankings.tsx`

- [ ] **Step 1: DistrictRankings 의 row 렌더 분기 추가**

`DistrictRankings.tsx` 안 ranking row 렌더링에서 `simResult.district_predictions` 의 해당 동 entry 의 `is_excluded_combo` 확인:

before (예시):
```tsx
{rankings.map((r) => (
  <tr key={r.district}>
    <td>{r.district}</td>
    <td>{r.score}</td>
    ...
  </tr>
))}
```

after:
```tsx
{rankings.map((r) => {
  const pred = simResult.district_predictions?.find((p) => p.district === r.district);
  const isExcluded = pred?.is_excluded_combo === true;
  return (
    <tr
      key={r.district}
      className={isExcluded ? 'opacity-50 bg-stone-900/40' : ''}
    >
      <td>
        {r.district}
        {isExcluded && (
          <span className="ml-2 rounded bg-stone-700 px-1.5 py-0.5 text-[10px] font-mono text-stone-400">
            예측 불가
          </span>
        )}
      </td>
      <td>{isExcluded ? '—' : r.score}</td>
      ...
    </tr>
  );
})}
```

`simResult` prop 이 없으면 받아오게 추가 (DistrictRankings 가 이미 받고 있을 가능성 — 확인 후 적용).

- [ ] **Step 2: tsc 검증**

```bash
npx tsc --noEmit
```
Expected: EXIT=0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/sections/DistrictRankings.tsx
git commit -m "feat(ranking): is_excluded_combo 동 회색 처리 + '예측 불가' 배지

/predict 응답의 ExcludedComboError 동을 시각적으로 비활성. score 등 ML 의존
필드는 '—' 처리. 강민/본부 영업팀이 'why 점수 0' 헷갈리지 않게 명시."
```

---

## Task 8: 정합성 검증

**Files:**
- (검증만, 코드 변경 X)

- [ ] **Step 1: tsc 풀 검증**

```bash
cd /c/mapo-franchise-simulator/frontend && npx tsc --noEmit
```
Expected: EXIT=0, 에러 0건.

- [ ] **Step 2: vitest 풀 실행**

```bash
npx vitest run
```
Expected: 모든 테스트 통과. Task 3 + Task 4 신규 테스트 9건 추가됨 (4 + 5).

- [ ] **Step 3: build**

```bash
npm run build
```
Expected: EXIT=0. bundle warning 정도는 OK (메인 chunk > 500kB 기존 경고만 유지).

- [ ] **Step 4: prettier**

```bash
npx prettier --write src
```
Expected: 변경 파일 목록 보고. 없으면 0.

- [ ] **Step 5: 수동 검증 체크리스트 (강민 직접)**

- [ ] 정상 케이스: 시뮬 끝나면 두 응답 모두 받고 `/dashboard` hub 이동, 모든 카드 정상
- [ ] 시간: 직전 60~90초 → 25~30초 단축 확인
- [ ] DistrictRankings 의 excluded 동 회색 + "예측 불가" 배지 (테스트 데이터 또는 backend 협의)
- [ ] backend 일시 중단으로 부분 실패 유도 → SimulationFloatingWidget 의 PARTIAL SUCCESS + 재시도 버튼
- [ ] 재시도 버튼 클릭 시 슬라이스 단독 재호출 + 다른 슬라이스 보존

- [ ] **Step 6: Commit (검증 결과 노트만)**

코드 변경 없으면 commit 생략. 검증 통과 사실은 PR description 에 기록.

```bash
# 변경 없으면 skip
# prettier 가 일부 정리하면:
git add frontend/src/
git commit -m "chore: prettier auto-format after migration"
```

---

## 별도 sub-task: history 저장 (Task 8 이후)

B1 의 `/history/save` endpoint 준비 후 별도 plan/cycle:

1. `/history/save` 호출 후 응답에서 `id` 받아 store.savedHistoryId set
2. `useSaveSimulation.ts` 의 호출 변경
3. SaveDialog UI 흐름 검증

이 plan 의 8 task 와 독립. B1 회신 후 강민이 결정.

---

## Self-Review

**1. Spec coverage:**
- §2.1 흐름 (Promise.allSettled) → Task 3 ✓
- §2.2 store 슬라이스 → Task 3 ✓
- §2.3 합성 selector → Task 4 ✓
- §3.1 api 함수 → Task 2 ✓
- §3.2 store action 변경 → Task 3 ✓
- §3.3 history endpoint → 별도 sub-task (계획 명시) ✓
- §3.4 ExcludedCombo → Task 7 ✓
- §4.1 수정 파일 표 → Tasks 모두 매칭 ✓
- §4.2 영향 없는 컴포넌트 → file structure 표에서 명시 ✓
- §5.1 부분 성공 UI → Task 6 ✓
- §5.2 합성 selector null 안전 → Task 4 의 buildCombinedResult ✓
- §6.1 자동 테스트 → Task 3 + 4 ✓
- §6.2 수동 검증 → Task 8 step 5 ✓

**2. Placeholder scan:** 없음. "TBD" / "..." / "Add error handling" 등 패턴 0.

**3. Type consistency:** `DistrictPredictionResult`, `AnalysisOutput`, `PredictionSlice`, `AnalysisSlice`, `SliceStatus`, `buildCombinedResult` — 모든 task 에서 일관 명명 사용. `useCombinedSimResult` hook 명도 Task 4 + Task 5 일관.
