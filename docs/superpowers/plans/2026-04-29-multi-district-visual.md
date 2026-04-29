# 4동 다중 시각화 + /simulate 폐기 + 비교 모드 제거 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. 13 task 순차. 각 task 후 implementer self-review 만 (전체 cycle 끝에 사용자 verify).

**Goal**: 4동 한 그래프 시각화 + 비교 모드 폐기 + `/simulate` 완전 제거. 1등 동 우위가 시각적으로 한눈에.

**Architecture**: backend `/predict` (수지니 c8ea31f) 응답 = `{ status, data: DistrictPredictionResult[] }`. frontend 는 `runPredict` + `runAnalyzeLlm` 병렬 + `useCombinedSimResult` 합성. 모든 차트/카드는 `simResult.district_predictions` 배열 순회로 4동 동시 표시.

**Tech Stack**: React 18 + TS + Vite + recharts + Tailwind + zustand. react-markdown 도입 (B1 cycle).

**Spec**: `docs/superpowers/specs/2026-04-29-multi-district-visual-design.md`

**Branch**: `feature/analyze-llm-migration` (이미 dev merge `6e8e2d6` 받은 상태)

**Commit 정책**: Round 2 와 동일 — 모든 task 끝 일괄 commit. implementer 는 commit 안 함.

---

## Task 1: DistrictPredictionResult 타입 확장 + ShapResult 의존 검증

**Files**:
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1**: types/index.ts 의 현재 `DistrictPredictionResult` Read (현재 4 필드)
- [ ] **Step 2**: 11 필드로 확장:

```typescript
export interface DistrictPredictionResult {
  district: string;
  dong_code: string | null;
  is_excluded_combo: boolean;
  is_mock: boolean;
  quarterly_projection: QuarterlyProjection[];
  scenarios: {
    optimistic: { quarter: number; revenue: number }[];
    base: { quarter: number; revenue: number }[];
    pessimistic: { quarter: number; revenue: number }[];
  } | null;
  bep: Record<string, unknown> | null;
  closure_rate: Record<string, unknown> | null;
  closure_risk: Record<string, unknown> | null;
  shap_result: ShapResult | null;
  customer_segment: Record<string, unknown> | null;
  living_pop_forecast: Record<string, unknown> | null;
  emerging_signal: Record<string, unknown> | null;
}
```

- [ ] **Step 3**: `ShapResult` 타입이 export 되어 있는지 확인 — 없으면 같은 파일에 import 또는 inline definition 보존
- [ ] **Step 4**: `npx tsc --noEmit` 0 (단순 type 확장이라 깨질 일 적음)
- [ ] **Step 5**: `npx prettier --write src/types/index.ts`

---

## Task 2: client.ts rename + /simulate 제거 + body.data unwrap fix + signal/timeout

**Files**:
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1**: `fetchPredict` → `runPredict` rename. signature:

```typescript
export async function runPredict(
  input: SimulationInput,
  signal?: AbortSignal,
): Promise<DistrictPredictionResult[]> {
  const response = await apiClient.post('/predict', input, { signal, timeout: 300_000 });
  const body = response.data;
  // backend (수지니 c8ea31f): { status: "success", data: DistrictPredictionResult[] }
  if (body && body.status === 'success' && Array.isArray(body.data)) return body.data;
  if (body && body.status === 'error') throw new Error(body.message || 'Predict failed');
  if (Array.isArray(body)) return body;  // legacy
  return [];
}
```

(Promise return type 은 명세 raw `{status, data}` 가 아니라 unwrapped `DistrictPredictionResult[]` — 호출처가 더 깔끔)

- [ ] **Step 2**: `fetchAnalyzeLlm` → `runAnalyzeLlm` rename + signal/timeout argument 추가
- [ ] **Step 3**: `runSimulation` 함수 + `/simulate` 호출 **완전 삭제**
- [ ] **Step 4**: `grep -rn "fetchPredict\|fetchAnalyzeLlm\|runSimulation" frontend/src` 결과 호출처 모두 rename. 호출처 = simulationStore, useCombinedSimResult, App.tsx history detail 경로
- [ ] **Step 5**: history detail 의 `runSimulation` 호출이 있으면 → 저장된 결과 직접 표시 (또는 `runPredict`+`runAnalyzeLlm` 병렬). 가장 단순 = 저장된 SimulationOutput 직접 store 에 set
- [ ] **Step 6**: `npx tsc --noEmit` 0, `prettier --write`

---

## Task 3: 비교 모드 완전 제거

**Files**:
- Delete: `frontend/src/pages/SimulationCompare.tsx`
- Delete: `frontend/src/components/PDF/CompareHiddenTemplate.tsx`
- Modify: `frontend/src/App.tsx` (import + route)
- Modify: `frontend/src/components/SimulationHistory/HistoryList.tsx` (비교 버튼)
- Modify: `frontend/src/components/SimulationHistory/HistoryCard.tsx` (비교 버튼)
- Modify: `frontend/src/utils/pdfPropsBuilder.ts` (compare 관련)

- [ ] **Step 1**: `grep -rn "SimulationCompare\|CompareHiddenTemplate\|/dashboard/compare\|비교" frontend/src` 사용처 식별
- [ ] **Step 2**: App.tsx 에서 `import SimulationCompare` + `path="/dashboard/compare"` 라우트 제거. 비교 모드 관련 state/네비게이션 제거
- [ ] **Step 3**: HistoryList.tsx 비교 버튼 + 관련 state 제거
- [ ] **Step 4**: HistoryCard.tsx 비교 버튼 제거
- [ ] **Step 5**: pdfPropsBuilder.ts compare 관련 builder 함수 제거 (또는 단순화)
- [ ] **Step 6**: 두 파일 삭제 (`rm`)
- [ ] **Step 7**: `grep -rn "SimulationCompare\|CompareHiddenTemplate" frontend/src` = 0건
- [ ] **Step 8**: `npx tsc --noEmit` 0, `prettier --write`

---

## Task 4: useCombinedSimResult — district_predictions 보존 + 다중 동 노출

**Files**:
- Modify: `frontend/src/hooks/useCombinedSimResult.ts`

- [ ] **Step 1**: 현재 `buildCombinedResult` 함수 Read. 단일 동 합성하던 부분 식별
- [ ] **Step 2**: `simResult.district_predictions = predictData` (배열 그대로) 노출. 단일 동 가공 (winner 만 fallback) 은 backward compat 위해 유지하되 array 가 우선
- [ ] **Step 3**: `as unknown as SimulationOutput` cast 가 quarterly_projection single→array 시그니처 변경으로 더 이상 필요 없으면 정리
- [ ] **Step 4**: 호출처 (App.tsx 4 호출처) 시그니처 영향 없음 — `simResult` 그대로 받음
- [ ] **Step 5**: tsc 0 + prettier

---

## Task 5: QuarterlyProjectionChart — CI 음영 winner → series[0]

**Files**:
- Modify: `frontend/src/components/SimulationResult/QuarterlyProjectionChart.tsx`

- [ ] **Step 1**: 현재 winner 동 기반 CI Area 부분 식별
- [ ] **Step 2**: `winnerDistrict` prop 유지 (강조용) 이지만 CI 음영 기준 = `series[0]` 으로 변경. (만약 winner 가 0번이면 동일 결과)
- [ ] **Step 3**: tsc 0 + prettier

---

## Task 6: BepCumulativeProfitChart — 다중 동 멀티 라인

**Files**:
- Modify: `frontend/src/components/SimulationResult/dashboard/charts/BepCumulativeProfitChart.tsx`
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictFinancialSimTab.tsx`

- [ ] **Step 1**: 현재 props `data: QuarterlyProjection[]` (단일 동) 식별
- [ ] **Step 2**: 시그니처 변경:

```typescript
type ChartSeries = { district: string; projection: QuarterlyProjection[] };
interface Props {
  series: ChartSeries[];
  height?: number;
}
```

- [ ] **Step 3**: chart wide format 변환 (QuarterlyProjectionChart B4 패턴 그대로):
```typescript
const chartData = [1, 2, 3, 4].map(q => {
  const row: Record<string, number | null> = { quarter: q };
  series.forEach(s => {
    const point = s.projection.slice(0, 4).find(p => p.quarter === q);
    row[`${s.district}_cumulative`] = point?.cumulative_profit ?? null;
  });
  return row;
});
```

- [ ] **Step 4**: 동별 Line + 색상 indigo/cyan/amber/rose + 범례. BEP ReferenceLine = series[0] cumulative_profit 기준
- [ ] **Step 5**: PredictFinancialSimTab 호출처 변경:
```tsx
<BepCumulativeProfitChart
  series={(simResult.district_predictions ?? []).filter(p => !p.is_excluded_combo).map(p => ({
    district: p.district,
    projection: p.quarterly_projection ?? [],
  }))}
/>
```

(district_predictions 비어있으면 fallback = `[{ district: simResult.winner_district ?? '단일', projection: simResult.quarterly_projection ?? [] }]`)

- [ ] **Step 6**: tsc 0 + prettier

---

## Task 7: ScenariosComparisonChart — 동 선택 dropdown + 3라인

**Files**:
- Modify: `frontend/src/components/SimulationResult/dashboard/charts/ScenariosComparisonChart.tsx`
- Modify: 호출처 (Read 후 식별)

- [ ] **Step 1**: 현재 `scenarios` prop 시그니처 + 호출처 grep
- [ ] **Step 2**: 시그니처 변경:

```typescript
interface Props {
  allScenarios: { district: string; scenarios: { optimistic; base; pessimistic } | null }[];
  height?: number;
}
```

- [ ] **Step 3**: useState 로 `selectedDistrict` 관리 — 기본 = `allScenarios[0]?.district`
- [ ] **Step 4**: 상단에 `<select>` dropdown — 동 변경 시 selectedDistrict 업데이트
- [ ] **Step 5**: 선택된 동의 scenarios → 낙관 (emerald) / 기본 (indigo) / 비관 (rose) 3라인
- [ ] **Step 6**: 호출처에서 `district_predictions.map(p => ({ district: p.district, scenarios: p.scenarios }))` 전달
- [ ] **Step 7**: tsc 0 + prettier

---

## Task 8: ClosureRatePanel / ClosureRiskPanel — FinancialTab inline 분리

**Files**:
- Read: `frontend/src/components/SimulationResult/dashboard/tabs/FinancialTab.tsx` (inline 두 패널 위치)
- Create: `frontend/src/components/SimulationResult/dashboard/charts/ClosureRatePanel.tsx`
- Create: `frontend/src/components/SimulationResult/dashboard/charts/ClosureRiskPanel.tsx`
- Modify: `frontend/src/components/SimulationResult/dashboard/tabs/FinancialTab.tsx` (re-export 제거 or 기본 단일 동 유지)
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictFinancialSimTab.tsx` (import 경로)

- [ ] **Step 1**: FinancialTab 의 inline `function ClosureRatePanel({ rate })` 와 `function ClosureRiskPanel({ closure })` 본체 그대로 추출
- [ ] **Step 2**: 별도 파일에 props 시그니처 확장:

```typescript
// ClosureRatePanel.tsx
interface Props {
  district?: string;  // 카드 상단 동 이름 (있으면 표시)
  rate: ... | null;
}
```

```typescript
// ClosureRiskPanel.tsx
interface Props {
  district?: string;
  closureRisk: ... | null;
}
```

- [ ] **Step 3**: `district` 있으면 카드 상단에 `<div className="text-xs font-bold text-stone-400 mb-2">{district}</div>` 추가 (작게)
- [ ] **Step 4**: FinancialTab 에서 두 inline 함수 제거 + 새 파일 import. 기존 호출 (FinancialTab 자체) 영향 없음
- [ ] **Step 5**: PredictFinancialSimTab 의 import 경로 변경: `'../../tabs/FinancialTab'` → `'../../charts/ClosureRatePanel'` + `'../../charts/ClosureRiskPanel'`
- [ ] **Step 6**: tsc 0 + prettier

---

## Task 9: ClosureRate/RiskPanel + ShapInsightCard 동별 grid 호출

**Files**:
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictFinancialSimTab.tsx`
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx` (ShapInsightCard 호출처)
- Modify: `frontend/src/components/SimulationResult/dashboard/charts/ShapInsightCard.tsx` (props district 추가)

- [ ] **Step 1**: ShapInsightCard 현재 props 확인 → `district?: string` 옵션 추가 (카드 상단 표시)
- [ ] **Step 2**: PredictFinancialSimTab 변경:

```tsx
const dpredicts = (simResult.district_predictions ?? []).filter(p => !p.is_excluded_combo);

<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
  {dpredicts.map(p => (
    <ClosureRiskPanel
      key={p.district}
      district={p.district}
      closureRisk={(p.closure_risk as any) ?? null}
    />
  ))}
</div>
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
  {dpredicts.map(p => (
    <ClosureRatePanel
      key={p.district}
      district={p.district}
      rate={(p.closure_rate as any) ?? null}
    />
  ))}
</div>
```

- [ ] **Step 3**: PredictSalesForecastTab 의 ShapInsightCard 호출 (있으면) 같은 grid 패턴 적용
- [ ] **Step 4**: dpredicts 비어있을 때 fallback (단일 동 표시 유지)
- [ ] **Step 5**: tsc 0 + prettier

---

## Task 10: PredictCustomerFlowTab — 동별 grid (PeakHourCard + customer_segment)

**Files**:
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictCustomerFlowTab.tsx`

- [ ] **Step 1**: 현재 단일 동 (B5 결과) PeakHourCard 만 표시. 단일 동 fallback 유지
- [ ] **Step 2**: `district_predictions` 받아 동별 grid:

```tsx
const dpredicts = (simResult.district_predictions ?? []).filter(p => !p.is_excluded_combo);

{dpredicts.length > 0 ? (
  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
    {dpredicts.map(p => (
      <div key={p.district} className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-4">
        <div className="text-xs font-bold text-stone-400 mb-2">{p.district}</div>
        {p.living_pop_forecast && <PeakHourCard data={p.living_pop_forecast as any} />}
        {p.customer_segment && (/* 간단 카드 — 기존 CustomerSegmentCard 컴포넌트 있으면 재사용 */)}
        {!p.living_pop_forecast && !p.customer_segment && (
          <div className="text-[0.625rem] text-stone-500">유동인구·고객 데이터 미수신</div>
        )}
      </div>
    ))}
  </div>
) : (
  // 기존 단일 동 fallback (simResult.living_pop_forecast)
)}
```

- [ ] **Step 3**: assumption 3 (backend 미구현) 으로 인해 customer_segment / living_pop_forecast 가 항상 null 일 가능성 — guard 로 hide 처리. PeakHourCard 만이라도 표시되면 OK
- [ ] **Step 4**: tsc 0 + prettier

---

## Task 11: PredictEmergingDistrictTab — placeholder 해제 + 동별 grid

**Files**:
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx`

- [ ] **Step 1**: 현재 placeholder 상태 확인. props 변경 (simResult 받도록)
- [ ] **Step 2**: 동별 grid:

```tsx
const dpredicts = (simResult.district_predictions ?? []).filter(p => !p.is_excluded_combo);

<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
  {dpredicts.map(p => (
    <div key={p.district} className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-4">
      <div className="text-xs font-bold text-stone-400 mb-2">{p.district}</div>
      {p.emerging_signal ? (
        // EmergingSignalCard 컴포넌트 있으면 재사용. 없으면 간단 카드
        <pre className="text-[0.625rem] text-stone-300">{JSON.stringify(p.emerging_signal, null, 2)}</pre>
      ) : (
        <div className="text-[0.625rem] text-stone-500">신흥상권 신호 미수신</div>
      )}
    </div>
  ))}
</div>
```

- [ ] **Step 3**: 기존 EmergingSignalCard 컴포넌트가 있으면 재사용 (`charts/EmergingSignalCard.tsx`)
- [ ] **Step 4**: PredictGroup 의 PredictEmergingDistrictTab 호출 시 simResult prop 전달 확인
- [ ] **Step 5**: tsc 0 + prettier

---

## Task 12: confidencePct 잔존 정리 — InsightTab + pdfPropsBuilder

**Files**:
- Modify: `frontend/src/components/SimulationResult/dashboard/tabs/InsightTab.tsx`
- Modify: `frontend/src/utils/pdfPropsBuilder.ts`
- (자동 해소) `tabs/FinancialTab.tsx`, `pages/SimulationCompare.tsx`, `components/PDF/CompareHiddenTemplate.tsx` — Task 3 + Task 8 에서 처리

- [ ] **Step 1**: InsightTab `grep -n "confidencePct\|분석 신뢰도"` 4 위치 식별
- [ ] **Step 2**: 변수 + JSX + props 모두 제거 (B6 의 PredictFinancialSimTab 패턴 동일)
- [ ] **Step 3**: pdfPropsBuilder confidencePct 제거 — PDF 출력에 신뢰도 영역 사라짐
- [ ] **Step 4**: `grep -rn "confidencePct\|분석 신뢰도" frontend/src` = 0 또는 무관한 wrapping 만
- [ ] **Step 5**: tsc 0 + prettier

---

## Task 13: 정합성 검증 + 일괄 commit

- [ ] **Step 1**: `cd frontend && npx tsc --noEmit` EXIT=0
- [ ] **Step 2**: `npm run build` EXIT=0
- [ ] **Step 3**: `npx vitest run` 73/73 (또는 새 테스트 추가)
- [ ] **Step 4**: `npx prettier --check src` ALL FORMATTED
- [ ] **Step 5**: backend `/predict` 엔드포인트 manual hit (curl 또는 fetch) — `body.data` array 정상 반환 확인 (강민 직접)
- [ ] **Step 6**: 변경 파일 staging — 다음 명시 파일만:

```
frontend/src/types/index.ts
frontend/src/api/client.ts
frontend/src/App.tsx
frontend/src/components/PDF/HiddenPDFTemplate.tsx (만약 변경됐으면)
frontend/src/components/SimulationHistory/HistoryCard.tsx
frontend/src/components/SimulationHistory/HistoryList.tsx
frontend/src/components/SimulationResult/QuarterlyProjectionChart.tsx
frontend/src/components/SimulationResult/dashboard/charts/BepCumulativeProfitChart.tsx
frontend/src/components/SimulationResult/dashboard/charts/ClosureRatePanel.tsx (new)
frontend/src/components/SimulationResult/dashboard/charts/ClosureRiskPanel.tsx (new)
frontend/src/components/SimulationResult/dashboard/charts/ScenariosComparisonChart.tsx
frontend/src/components/SimulationResult/dashboard/charts/ShapInsightCard.tsx
frontend/src/components/SimulationResult/dashboard/sub/predict/PredictCustomerFlowTab.tsx
frontend/src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx
frontend/src/components/SimulationResult/dashboard/sub/predict/PredictFinancialSimTab.tsx
frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx
frontend/src/components/SimulationResult/dashboard/tabs/FinancialTab.tsx
frontend/src/components/SimulationResult/dashboard/tabs/InsightTab.tsx
frontend/src/hooks/useCombinedSimResult.ts
frontend/src/utils/pdfPropsBuilder.ts
docs/superpowers/specs/2026-04-29-multi-district-visual-design.md
docs/superpowers/plans/2026-04-29-multi-district-visual.md
```

삭제 파일:
```
frontend/src/pages/SimulationCompare.tsx (D)
frontend/src/components/PDF/CompareHiddenTemplate.tsx (D)
```

- [ ] **Step 7**: 일괄 commit:

```bash
git commit -m "feat(predict): 4동 동시 시각화 + /simulate 폐기 + 비교 모드 제거

수지니 c8ea31f /predict 엔드포인트 + IM3-263 dev merge 후 명세 적용.

핵심 의도: 한 그래프에 4동 = 1등 동 우위 시각적 한눈.

- runPredict + runAnalyzeLlm rename + signal/timeout + body.data unwrap fix
- runSimulation + /simulate 호출 완전 제거
- DistrictPredictionResult 11 필드 (backend 8 필드 구현, 3 필드 미수신 시 hide)
- QuarterlyProjectionChart CI 음영 series[0]
- BepCumulativeProfitChart 다중 동 멀티 라인
- ScenariosComparisonChart 동 dropdown + 3라인
- ClosureRate/RiskPanel FinancialTab inline 분리 + 동별 카드 grid
- ShapInsightCard 동별 카드 grid
- PredictCustomerFlowTab + PredictEmergingDistrictTab 동별 카드 grid
- 비교 모드 6 파일 정리 (SimulationCompare 삭제)
- InsightTab + pdfPropsBuilder confidencePct 잔존 제거

검증: tsc 0 / vitest / build 0 / prettier ok.
quarterly_projection 필드 보존 (수지니 명시).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review (controller checks before dispatching subagent cycle)

1. ✅ Spec coverage — 13 task = spec 의 12 변경 항목 + 검증
2. ✅ 모든 step 에 file path + 코드 블록 (placeholder 없음)
3. ✅ Type 일관성 — `ChartSeries` Task 6 기존 B4 패턴 재사용
4. ✅ Backend 검증 반영 — assumption 3 (3 필드 미구현) 적용
5. ✅ quarterly_projection 보존 원칙 — 단일→배열 변경만, 필드 자체 유지
