# `/predict` + `/analyze/llm` 분리 호출 마이그레이션 — Design

**일자**: 2026-04-29
**담당**: C1 강민 (frontend) · B1 (backend endpoint 정의 + `/history/save` 신설)
**관련 PR**: [B1] IM3-259 endpoint split (이미 머지)

## 1. Summary

기존 `/simulate` 단일 호출 (LangGraph 8 agent 풀파이프) 을 **`/predict` + `/analyze/llm` 두 endpoint 병렬 호출** 로 마이그레이션. 응답을 frontend 에서 `SimulationOutput` 형태로 합성해 기존 컴포넌트 호환성 max. 에러는 `Promise.allSettled` 로 부분 성공 허용.

`/simulate` 자체는 deprecated 아님 (backend 보존). 다만 frontend 가 더 이상 호출 X. ExcludedComboError 동은 `is_excluded_combo: true` 플래그로 표시.

## 2. Architecture

### 2.1 데이터 흐름 (현재 vs 변경 후)

**현재**:
```
사용자 입력 → /simulate 호출 (LangGraph 풀)
              ↓ (60~90초)
       SimulationOutput
              ↓
        store.result
              ↓
     모든 컴포넌트 사용
```

**변경 후**:
```
사용자 입력 → Promise.allSettled([
                fetch('/predict', payload),
                fetch('/analyze/llm', payload),
              ])
                       ↓ (병렬, 25~30초 단축)
              prediction / analysis 두 슬라이스
                       ↓
              useMemo 합성 (SimulationOutput 호환)
                       ↓
              모든 컴포넌트 사용 (변경 최소)
                       ↓
              frontend → POST /history/save 별도 호출
```

### 2.2 Store 슬라이스 (`simulationStore.ts`)

```ts
interface SimulationStore {
  // 기존
  status: 'idle' | 'running' | 'done' | 'error';
  progress: number;
  stage: string;
  params: SimulationInput | null;
  startedAt: number | null;
  savedHistoryId: number | null;

  // 신규 — 슬라이스 분리
  prediction: {
    status: 'idle' | 'running' | 'done' | 'error';
    data: DistrictPredictionResult[] | null; // /predict 응답
    error: string | null;
  };
  analysis: {
    status: 'idle' | 'running' | 'done' | 'error';
    data: AnalysisOutput | null; // /analyze/llm 응답
    error: string | null;
  };

  // 기존 result 는 derived (useMemo 합성) — 직접 set X
  startSimulation: (params: SimulationInput) => Promise<void>;
  dismissResult: () => void;
}
```

`status` 는 두 슬라이스의 합성: 둘 다 done = `done`, 하나라도 running = `running`, 둘 다 error = `error`, 한쪽만 error = `done` (부분 성공).

### 2.3 SimulationOutput 합성 (selector / useMemo)

`AnalysisOutput` = `SimulationOutput` 에서 ML 필드 (`quarterly_projection`, `closure_risk`, `shap_result` 등) 빠진 subset. 두 슬라이스 합성:

```ts
function buildCombinedResult(
  prediction: DistrictPredictionResult[] | null,
  analysis: AnalysisOutput | null,
): SimulationOutput | null {
  if (!analysis && !prediction) return null;
  return {
    ...(analysis ?? {}),
    // ML 필드는 winner 동의 prediction 에서 추출
    quarterly_projection: prediction?.find((p) => p.district === analysis?.winner_district)?.quarterly_projection,
    closure_risk: prediction?.find(...)?.closure_risk,
    shap_result: prediction?.find(...)?.shap_result,
    // prediction list 자체도 보존 (동 비교 카드용)
    district_predictions: prediction ?? [],
  } as SimulationOutput;
}
```

소비처:
```ts
const result = useSimulationStore((s) => {
  return buildCombinedResult(s.prediction.data, s.analysis.data);
});
// 또는 selector hook 으로 분리
const result = useCombinedSimResult();
```

기존 `useSimulationStore((s) => s.result)` 는 모두 새 selector hook 으로 교체. 컴포넌트 자체는 변경 없음 (받는 prop = SimulationOutput).

## 3. Public Interfaces

### 3.1 `api/client.ts` 신규 함수

```ts
export async function fetchPredict(input: SimulationInput): Promise<DistrictPredictionResult[]> {
  const response = await apiClient.post('/predict', input);
  return response.data;
}

export async function fetchAnalyzeLlm(input: SimulationInput): Promise<AnalysisOutput> {
  const response = await apiClient.post('/analyze/llm', input);
  return response.data;
}

// 기존 startSimulation 호출 흐름 (App.tsx) — `/simulate` 호출 → Promise.allSettled 로 교체.
// 기존 simulate() 함수는 history detail 복원 / fallback 용으로 보존 (deprecated 표시).
```

### 3.2 `simulationStore.ts` API 변경

```ts
startSimulation: async (params) => {
  set({ status: 'running', params, prediction: { status: 'running', ... }, analysis: { ... } });
  const [predResult, analysisResult] = await Promise.allSettled([
    fetchPredict(params),
    fetchAnalyzeLlm(params),
  ]);

  // prediction 슬라이스
  if (predResult.status === 'fulfilled') {
    set({ prediction: { status: 'done', data: predResult.value, error: null } });
  } else {
    set({ prediction: { status: 'error', data: null, error: predResult.reason.message } });
  }
  // analysis 슬라이스 동일

  // 합성 status: 둘 다 fulfilled → done, 둘 다 rejected → error, 한쪽 → done (부분 성공)
  const allFailed = predResult.status === 'rejected' && analysisResult.status === 'rejected';
  set({ status: allFailed ? 'error' : 'done', progress: 100, stage: '' });
},
```

### 3.3 `/history/save` (B1 별도 sub-task)

```
POST /history/save
Body: {
  prediction: DistrictPredictionResult[] | null,
  analysis: AnalysisOutput | null,
  params: SimulationInput
}
Response: { id: number, ... }
```

frontend `useSaveSimulation` 이 호출. B1 endpoint 추가 전까지는 save 비활성 (강민이 sub-task 별도 진행).

### 3.4 ExcludedComboError 처리

`/predict` 응답의 각 entry 에 `is_excluded_combo: true` 플래그. frontend 처리:

- **동 비교 카드** 등에서 해당 동 row → 회색 처리 + "예측 불가" 배지
- 차트 (BulletChart, ClosureRiskPanel 등) → 비활성 placeholder
- **합성 selector** 에서 winner_district 가 excluded 면 → ML 필드 fallback (다른 후보 동 사용 또는 null)

## 4. Components 영향

### 4.1 수정 필요

| 파일 | 변경 |
|------|------|
| `src/api/client.ts` | `fetchPredict`, `fetchAnalyzeLlm` 추가. 기존 `simulate()` 는 deprecated 주석 |
| `src/stores/simulationStore.ts` | prediction/analysis 슬라이스 + Promise.allSettled 흐름 |
| `src/stores/simulationStore.test.ts` | 신 슬라이스 테스트 추가 |
| `src/hooks/useCombinedSimResult.ts` (신규) | useMemo 합성 selector hook |
| `src/App.tsx` | `useSimulationStore((s) => s.result)` → `useCombinedSimResult()` 교체 (1~2 곳) |
| `src/types/index.ts` | `DistrictPredictionResult`, `AnalysisOutput` 타입 추가 (B1 schema 따라) |
| `src/hooks/useSaveSimulation.ts` | `/history/save` 별도 호출로 변경 (B1 endpoint 후) |
| 시뮬 진행 위젯 (`SimulationFloatingWidget`) | 부분 실패 표시 — "AI 분석만 완료" / "ML 예측만 완료" 등 |

### 4.2 영향 없음 (그대로 사용)

- `DashboardHub`, `DashboardOutlet` — `useCombinedSimResult()` 받음
- `PredictGroup` 5 서브탭 — `simResult.quarterly_projection` 등 동일 접근
- `AnalyzeGroup` 5 서브탭 — `simResult.winner_district` 등 동일 접근
- `AbmGroup` — 기존 ABM 시뮬 (별도 endpoint, 영향 X)
- `MapSection`, `MarketMap` — 합성된 simResult 그대로 사용

기존 컴포넌트가 `SimulationOutput` 받는 prop 인터페이스 보존 → 변경 0. 합성 selector 가 호환 보장.

## 5. Error Handling

### 5.1 부분 성공 시나리오

| Prediction | Analysis | UI 동작 |
|-----------|---------|--------|
| ✅ done | ✅ done | 정상 (`status='done'`) |
| ❌ error | ✅ done | ML 카드 (BulletChart 등) "예측 일시 실패 + 재시도" 표시. AI 분석 영역 (winner/legal/추천) 정상 |
| ✅ done | ❌ error | AI 분석 영역 "분석 일시 실패 + 재시도" 표시. ML 카드 정상 (단 winner_district 모르므로 사용자 입력 동 기준) |
| ❌ error | ❌ error | 전체 실패. RUN SIMULATION 입력 화면 복귀 + toast |

**재시도 정책**: 사용자가 부분 실패한 슬라이스만 재호출 가능 (예: ML 카드의 "재시도" 버튼 → `fetchPredict(params)` 만 재호출, prediction 슬라이스만 update).

### 5.2 합성 selector 의 null 안전성

기존 컴포넌트는 `simResult.competitor_intel?.competition_500m?.samples` 같은 optional chaining 사용 중 (현재도 그렇게 처리). `useCombinedSimResult()` 가 부분 데이터 합성 시 비는 필드는 `null`/`undefined` 그대로 전달. 컴포넌트가 빈 상태 안전 처리.

## 6. Test Plan

### 6.1 자동 테스트

- `simulationStore.test.ts`: prediction/analysis 슬라이스 변경 — Promise.allSettled 분기 (둘 다 ok / 둘 다 fail / 부분) 시나리오
- `useCombinedSimResult` (신규 hook) 단위 테스트 — 합성 결과 정합성

### 6.2 수동 검증

- [ ] 정상 케이스: 시뮬 끝나면 두 응답 모두 받고 `/dashboard` hub 이동, 모든 카드 정상
- [ ] /predict 만 실패: AI 분석 영역 정상, ML 카드에 재시도 버튼
- [ ] /analyze/llm 만 실패: ML 카드 정상, AI 분석 영역에 재시도
- [ ] 둘 다 실패: 입력 화면 복귀 + 에러 toast
- [ ] ExcludedComboError 동: "예측 불가" 배지 + 차트 비활성
- [ ] 시간: 직전 60~90초 → 25~30초 단축 확인
- [ ] history 저장: B1 endpoint 후 별도 sub-task 검증

## 7. Assumptions

1. `/predict` 와 `/analyze/llm` 둘 다 사용자 입력 (`target_districts`, `industry_filter` 등) 그대로 받음. ranking 결정 외부 의존 없음.
2. `AnalysisOutput` 의 필드 = `SimulationOutput` 의 ML 제외 subset. 두 응답 합치면 기존 `SimulationOutput` 호환.
3. `/predict` 응답에 `is_excluded_combo: true` 가 entry 단위로 표시.
4. `/history/save` endpoint 추가 = B1 별도 sub-task. 이 spec 의 frontend 작업과 병렬 진행.
5. 기존 `/simulate` endpoint 는 deprecated 아니지만 frontend 호출 X. 단 history detail 복원 등 fallback 경로 검토 필요.
6. 마이그레이션 후에도 `useSimulationStore((s) => s.result)` 패턴 의존하던 코드는 모두 `useCombinedSimResult()` 로 교체. 누락 시 tsc 에러로 즉시 catch.

## 8. 마이그레이션 단계 (plan 에서 세부화)

| 단계 | 작업 | 의존 |
|------|------|------|
| 1 | types 추가 + api client 함수 신설 | - |
| 2 | simulationStore 슬라이스 분리 + Promise.allSettled | 1 |
| 3 | useCombinedSimResult hook 신설 | 2 |
| 4 | App.tsx 의 store 호출처 교체 | 3 |
| 5 | SimulationFloatingWidget 부분 실패 UI | 2 |
| 6 | ExcludedComboError 시각화 | 1, 4 |
| 7 | 정합성 검증 (tsc + vitest + 수동) | 1~6 |
| 8 | history 저장 (B1 endpoint 준비 후) | B1 |

각 단계별 구현 디테일은 plan 문서에서 세부화.
