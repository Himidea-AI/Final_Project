# 4동 다중 시각화 + /simulate 폐기 + 비교 모드 제거 — Design

**일자**: 2026-04-29
**담당**: C1 강민 (frontend)
**관련 cycle**: IM3-259 (#142 머지) + Round 2 (b4f1ba5) 후속

## 1. 핵심 의도

> "네 개의 동을 선택해서 시뮬레이션을 돌렸을 때, 한 그래프 안에 4동이 동시에 그려져서 1등 동의 우위가 시각적으로 한눈에 드러나게."

비교 모드 (사용자가 동을 두 번 선택해 비교) 의 기능을 **단일 시뮬레이션 한 번에 4동 동시 시각화**로 흡수. 비교 페이지 + 라우트 + 버튼 모두 제거. 그래프/카드 모두 4동 병치.

## 2. 변경 항목

### 2.1 API client rename + /simulate 완전 제거

**현재**: `fetchPredict` / `fetchAnalyzeLlm` (B4 cycle 도입). `runSimulation` (`/simulate`) 은 `@deprecated` 만 표기 후 history detail fallback 으로 유지.

**변경**:
- `fetchPredict` → `runPredict` rename (명세 일치)
- `fetchAnalyzeLlm` → `runAnalyzeLlm` rename
- `runSimulation` 함수 + `/simulate` 호출 **완전 제거**
- history detail fallback 도 `runPredict` + `runAnalyzeLlm` 분리 호출로 마이그레이션 (또는 history detail 자체가 저장된 결과를 그대로 표시 — `/simulate` 재호출 불필요)
- 두 함수 모두 `signal?: AbortSignal` argument + `timeout: 300_000` 명시

```typescript
export async function runPredict(
  input: SimulationInput,
  signal?: AbortSignal,
): Promise<{ status: string; data: DistrictPredictionResult[] }> {
  const response = await apiClient.post('/predict', input, { signal, timeout: 300_000 });
  return response.data;
}

export async function runAnalyzeLlm(
  input: SimulationInput,
  signal?: AbortSignal,
): Promise<AnalysisOutput> {
  const response = await apiClient.post('/analyze/llm', input, { signal, timeout: 300_000 });
  return response.data;
}
```

**영향 파일**:
- `frontend/src/api/client.ts`
- 호출처: simulationStore, useCombinedSimResult, App.tsx history detail 경로 등

### 2.2 DistrictPredictionResult 타입 확장

**현재**:
```typescript
export interface DistrictPredictionResult {
  district: string;
  is_excluded_combo: boolean;
  quarterly_projection?: QuarterlyProjection;  // 단일
  // (4 필드만)
}
```

**변경 (명세 그대로)**:
```typescript
export interface DistrictPredictionResult {
  district: string;
  dong_code: string | null;
  is_excluded_combo: boolean;
  is_mock: boolean;
  quarterly_projection: QuarterlyProjection[];  // 배열 4분기
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

**리스크**: backend `/predict` 응답이 실제로 위 형태와 다르면 type mismatch + runtime undefined. plan 에서 backend schema 검증 task 선행 — backend 가 array 안 보내면 frontend 에서 `Array.isArray` 가드 + fallback. 핵심: type 은 명세 따름.

### 2.3 simulationStore 슬라이스 그대로

A3 에서 이미 분리됨 (`PredictionSlice` data: `DistrictPredictionResult[] | null`). 본 cycle 변경 없음 — 단 useCombinedSimResult 가 단일 동 가공하던 부분이 이번에 다중 동 그대로 노출 가능하도록 추가 노출.

### 2.4 QuarterlyProjectionChart — 검토

B4 에서 이미 다중 동 멀티 라인 + 범례 + winner 강조 완료. 명세 = "신뢰구간 Area는 첫 번째 동 기준" — 현재 winner 동 기준. **명세대로 첫 번째 동 (= series[0])** 으로 변경. 색상 indigo/cyan/amber/rose 명세 일치.

`data: { district; projection: QuarterlyProjection[] }[]` 시그니처는 이미 일치 (B4).

**변경**: CI 음영 기준 winnerDistrict → series[0] 으로 (또는 winner 가 0번이면 그대로).

### 2.5 BepCumulativeProfitChart — 다중 동 멀티 라인 (신규)

**현재**: `data: QuarterlyProjection[]` 단일 동.

**변경**:
```typescript
interface Props {
  data: { district: string; projection: QuarterlyProjection[] }[];
  height?: number;
}
```
- 동별 Line, 색상 indigo/cyan/amber/rose 4 팔레트
- 범례 표시
- BEP 도달 ReferenceLine = 첫 번째 동 기준 (명세)

호출처 `PredictFinancialSimTab.tsx` 도 동시 수정.

### 2.6 ScenariosComparisonChart — 동 선택 드롭다운 + 3라인

**현재**: 단일 동 scenarios prop.

**변경**:
```typescript
interface Props {
  allScenarios: { district: string; scenarios: { optimistic; base; pessimistic } }[];
}
```
- 상단 동 선택 dropdown (기본 = 첫 번째 동 = 1등 동 보장)
- 선택된 동의 낙관/기본/비관 3라인

### 2.7 ClosureRiskPanel / ClosureRatePanel — 컴포넌트 분리 + 동별 카드 grid

**현재**: 두 패널 모두 `tabs/FinancialTab.tsx` 안에 inline 정의. 단일 동.

**변경**:
- 두 패널을 별도 파일로 분리 (`charts/ClosureRatePanel.tsx`, `charts/ClosureRiskPanel.tsx`) — 단일 카드 단위
- props: `{ district: string; closure_risk?: ... }` / `{ district: string; closure_rate?: ... }`
- `PredictFinancialSimTab` 에서 grid 호출:

```tsx
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
  {predictResult.map(r => (
    <ClosureRiskPanel key={r.district} district={r.district} closureRisk={r.closure_risk} />
  ))}
</div>
```

### 2.8 ShapInsightCard — 동별 카드 grid

**현재**: 단일 동 SHAP.

**변경**:
- props: `{ district: string; shapResult: ShapResult | null }` 형태 받도록 (이미 그렇거나 작은 수정)
- 호출처 = `PredictSalesForecastTab` 또는 PredictFinancialSimTab — `predictResult.map` grid 적용

### 2.9 PredictCustomerFlowTab — 동별 카드 grid 활성화

**현재**: B5 결과 단일 동 living_pop_forecast 의 PeakHourCard 만.

**변경**:
- `predictResult` 배열을 받아 동별 PeakHourCard + customer_segment 카드 grid 렌더
- placeholder 메시지 (customer_revenue 미연동) 제거 — `customer_segment` 데이터 있으면 카드 표시

### 2.10 PredictEmergingDistrictTab — placeholder 해제 + 동별 grid

**현재**: placeholder 추정.

**변경**:
- `predictResult.map(r => emerging_signal)` 동별 카드 grid
- 신흥상권 감지 신호 (이미 정의된 컴포넌트가 있으면 재사용; 없으면 단순 카드)

### 2.11 비교 모드 완전 제거

**삭제**:
- `frontend/src/pages/SimulationCompare.tsx`
- `frontend/src/components/PDF/CompareHiddenTemplate.tsx`

**수정**:
- `frontend/src/App.tsx`: `import SimulationCompare`, `path="/dashboard/compare"` 라우트 + 비교 모드 관련 상태/네비게이션 제거
- `frontend/src/components/SimulationHistory/HistoryList.tsx`: 비교 버튼 + 관련 state 제거
- `frontend/src/components/SimulationHistory/HistoryCard.tsx`: 비교 버튼 제거
- `frontend/src/utils/pdfPropsBuilder.ts`: compare 관련 builder 제거 또는 단순화

### 2.12 confidencePct 잔존 정리

B6 에서 `PredictFinancialSimTab` 만 처리. 잔존:
- `tabs/FinancialTab.tsx` (legacy — ClosureRatePanel/ClosureRiskPanel 분리하면서 어차피 영향)
- `tabs/InsightTab.tsx` (활성)
- `pages/SimulationCompare.tsx` (제거되므로 자동 해소)
- `components/PDF/CompareHiddenTemplate.tsx` (제거되므로 자동 해소)
- `utils/pdfPropsBuilder.ts` (수정)

본 cycle 에서 함께 정리.

## 3. 영향 없는 컴포넌트

- DashboardHub, DashboardOutlet (라우팅 wrapper)
- AbmGroup (별도 도메인)
- AnalyzeAiSummaryTab (B7 결과 유지)
- AnalyzeMarketTab

## 4. Test Plan

### 4.1 자동
- tsc EXIT=0
- vitest 73/73 유지 (또는 새 컴포넌트 테스트 추가)
- build EXIT=0
- prettier OK

### 4.2 수동 (강민)
- 시뮬 1동 / 2동 / 3동 / 4동 선택 후 각 차트가 동 수만큼 라인/카드
- QuarterlyProjectionChart 4 라인 + 1등 동 (winner) 강조 + 범례
- BepCumulativeProfitChart 4 라인
- ScenariosComparisonChart 동 선택 dropdown 작동 + 3라인
- ClosureRiskPanel/RatePanel/ShapInsightCard grid 4개 카드
- PredictCustomerFlowTab + PredictEmergingDistrictTab 동별 카드 grid
- /dashboard/compare 라우트 404 (비교 모드 제거)
- HistoryList/HistoryCard 비교 버튼 사라짐
- history detail 진입 시 저장된 4동 결과 그대로 표시

## 5. Assumptions (2026-04-29 dev merge 후 검증 완료)

1. ✅ backend `/predict` 응답 = `{ status: "success", data: DistrictPredictionResult[] }` (수지니 c8ea31f 실측). 최대 4동 (`[:4]` truncate).
2. ✅ `quarterly_projection` 동마다 배열 (`build_quarterly_projection` 결과). 명세 일치.
3. ⚠️ backend `DistrictPredictionResult` 8 필드만 구현 — `customer_segment, living_pop_forecast, emerging_signal` **3 필드 미구현**. frontend type 에는 명세대로 11 필드 다 정의 (optional/nullable). 호출처 동별 grid 는 `r.customer_segment != null` 가드로 hide. 백엔드 3 필드 추가는 별도 cycle (수지니 영역).
4. 🚨 현재 `fetchPredict` 버그 — backend 가 `body.data` 보내는데 frontend 가 `body.results` unwrap → 빈 배열 반환. Task 2 (rename + signal/timeout) 에서 함께 fix.
5. 🛡️ **quarterly_projection 필드 보존 원칙** (수지니 명시 요청): type 시그니처 변경 (single→array) 은 OK 지만 필드 자체 삭제/이름변경 금지. SimulationOutput / DistrictPredictionResult / 차트 컴포넌트 모두에서 보존.
6. history detail 의 저장 포맷 = 통합 SimulationOutput. 본 cycle 에서 history detail 은 그대로 — 단 `runSimulation` 사용 코드만 제거. 저장된 결과 직접 표시.
7. 비교 모드 PDF (`CompareHiddenTemplate`) 제거 → PDF export 의 비교 기능 사라짐. 일반 PDF (`HiddenPDFTemplate`) 는 유지.
8. confidencePct 잔존 — InsightTab 도 활성 영역이라 함께 제거.
3. history detail 의 저장 포맷 = 통합 SimulationOutput. 본 cycle 에서 history detail 은 그대로 — 단 `runSimulation` 사용 코드만 제거. 저장된 결과 직접 표시.
4. 비교 모드 PDF (`CompareHiddenTemplate`) 제거 → PDF export 의 비교 기능 사라짐. 본 cycle 에서 함께 정리. 일반 PDF (`HiddenPDFTemplate`) 는 유지.
5. confidencePct 잔존 — InsightTab 도 활성 영역이라 함께 제거.
6. EmergingSignalCard, CustomerSegmentCard 등 기존 단일 동 카드 컴포넌트는 props 시그니처 그대로 두고 호출처에서 grid 로 wrap.

## 6. Task 단계 (plan 에서 세부화)

| Task | 작업 | 영향 |
|------|------|------|
| 1 | DistrictPredictionResult 타입 확장 + ShapResult 등 의존 타입 검증 | types/index.ts |
| 2 | client.ts rename (runPredict/runAnalyzeLlm) + runSimulation 제거 + signal/timeout argument | client.ts + 호출처 |
| 3 | 비교 모드 완전 제거 — 파일 2개 삭제 + App.tsx 라우트 + HistoryList/HistoryCard 버튼 + pdfPropsBuilder | 6 파일 |
| 4 | useCombinedSimResult — district_predictions 다중 동 그대로 노출 (구조 변경) | hook |
| 5 | QuarterlyProjectionChart — CI 음영 기준 winner → series[0] | 1 파일 |
| 6 | BepCumulativeProfitChart 다중 동 멀티 라인 | 1 파일 + 호출처 |
| 7 | ScenariosComparisonChart 동 선택 dropdown + 3라인 | 1 파일 + 호출처 |
| 8 | ClosureRatePanel / ClosureRiskPanel — FinancialTab inline 분리 + 별도 파일 | 3 파일 |
| 9 | ClosureRatePanel/RiskPanel + ShapInsightCard 동별 카드 grid 호출 | PredictFinancialSimTab + PredictSalesForecastTab |
| 10 | PredictCustomerFlowTab 동별 grid (PeakHourCard + customer_segment 카드) | 1 파일 |
| 11 | PredictEmergingDistrictTab placeholder 해제 + 동별 grid | 1 파일 |
| 12 | InsightTab + pdfPropsBuilder confidencePct 잔존 정리 | 2 파일 |
| 13 | 정합성 검증 (tsc + vitest + build + prettier) + 일괄 commit | 검증만 |
