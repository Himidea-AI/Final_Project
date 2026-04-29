# Dashboard UI 정합성 Round 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 본부 영업팀 시연 검증 후 발견된 7 개 정합성 항목 fix — 마크다운 렌더, 중복 탭 제거, 다중 동 차트, 위치 이동, 가짜 신뢰도 제거, 레이아웃 정합.

**Architecture:** 기존 컴포넌트 prop 인터페이스 보존 위주의 작은 변경. `react-markdown` 패키지만 신규 도입. `simResult.district_predictions` (#142 마이그레이션 산물) 활용한 다중 동 차트.

**Tech Stack:** React 18 + TypeScript + recharts + react-markdown (신규) + Tailwind + vitest

**관련 spec:** `docs/superpowers/specs/2026-04-29-dashboard-ui-round-2-design.md`

---

## File Structure

| 파일 | 역할 | 상태 |
|------|------|------|
| `frontend/package.json` | `react-markdown` 9.x 추가 | Modify |
| `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx` | (1) synthesis 마크다운 렌더 + (7) EntrySignalLight 제거 + 상하 위치 변경 | Modify |
| `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSummaryTab.tsx` | 삭제 | **Delete** |
| `frontend/src/components/SimulationResult/dashboard/groups/PredictGroup.tsx` | 5 서브탭 → 4 서브탭 | Modify |
| `frontend/src/types/index.ts` | `PredictSubTab` enum 에서 'summary' 제거 (있으면) | Modify |
| `frontend/src/components/SimulationResult/QuarterlyProjectionChart.tsx` | (3) 라벨 + 1~4분기 + (4) 다중 동 라인 | Modify |
| `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx` | (3,4) 호출처 — district_predictions 다중 동 전달 | Modify |
| `frontend/src/components/SimulationResult/dashboard/tabs/DemographicTab.tsx` | (5) PeakHourCard 패널 제거 | Modify |
| `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictCustomerFlowTab.tsx` | (5) PeakHourCard 추가 | Modify |
| `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictFinancialSimTab.tsx` | (6) 분석 신뢰도 영역 제거 | Modify |

---

## Task 1: react-markdown 도입 + AnalyzeAiSummaryTab synthesis 마크다운 렌더

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx`

- [ ] **Step 1: react-markdown 설치**

```bash
cd /c/mapo-franchise-simulator/frontend && npm install react-markdown remark-gfm
```

react-markdown 9.x + remark-gfm 도입.

- [ ] **Step 2: AnalyzeAiSummaryTab 에 ReactMarkdown 적용**

`AnalyzeAiSummaryTab.tsx` 의 synthesis 종합 분석 + 최종 권고 부분에서 plain text 표시를 ReactMarkdown 으로 교체:

```tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// ... synthesis 텍스트 표시 부분
{synthesisText && (
  <div className="prose prose-sm prose-invert max-w-none">
    <ReactMarkdown remarkPlugins={[remarkGfm]}>{synthesisText}</ReactMarkdown>
  </div>
)}
```

만약 `prose-invert` plugin 이 Tailwind 에 없으면 inline className 매핑 사용:

```tsx
<ReactMarkdown
  components={{
    h1: ({ node, ...props }) => <h1 className="text-xl font-black text-stone-100 mb-3 mt-4" {...props} />,
    h2: ({ node, ...props }) => <h2 className="text-lg font-bold text-stone-100 mb-2 mt-3" {...props} />,
    h3: ({ node, ...props }) => <h3 className="text-base font-semibold text-stone-200 mb-2 mt-2" {...props} />,
    p: ({ node, ...props }) => <p className="text-sm text-stone-300 leading-relaxed mb-2" {...props} />,
    strong: ({ node, ...props }) => <strong className="font-bold text-stone-100" {...props} />,
    ul: ({ node, ...props }) => <ul className="list-disc pl-5 text-sm text-stone-300 space-y-1" {...props} />,
    ol: ({ node, ...props }) => <ol className="list-decimal pl-5 text-sm text-stone-300 space-y-1" {...props} />,
    li: ({ node, ...props }) => <li className="leading-relaxed" {...props} />,
  }}
  remarkPlugins={[remarkGfm]}
>
  {synthesisText}
</ReactMarkdown>
```

**참고**: `synthesisText` 변수명은 실제 코드에 맞게 (예: `simResult.ai_recommendation` 또는 `final_recommendation`).

- [ ] **Step 3: 다른 ai_recommendation 사용처 grep 후 동일 처리**

```bash
grep -rn "ai_recommendation\|final_recommendation" frontend/src/components --include="*.tsx" | head -10
```

추가 사용처 있으면 같은 ReactMarkdown 패턴 적용. 단 본 task 범위는 AnalyzeAiSummaryTab — 다른 곳은 별도 task 로 명시.

- [ ] **Step 4: tsc + build**

```bash
npx tsc --noEmit
npm run build
```
EXIT=0 양쪽.

- [ ] **Step 5: prettier + commit**

```bash
npx prettier --write src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx
git add frontend/package.json frontend/package-lock.json frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx
git commit -m "feat(synthesis): react-markdown 도입 — ## 헤더 plain text 표시 fix

backend 가 marked syntax (## 추천 입지 등) 응답에 포함시키지만 frontend 가
plain text 로 렌더하던 버그. ReactMarkdown + remarkGfm 으로 H1/H2/H3/strong/list
정상 렌더. components prop 으로 Tailwind className mapping (prose 의존 회피).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: PredictSummaryTab 제거 + PredictGroup 4 서브탭

**Files:**
- Delete: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSummaryTab.tsx`
- Modify: `frontend/src/components/SimulationResult/dashboard/groups/PredictGroup.tsx`
- Modify: `frontend/src/types/index.ts` (만약 'summary' enum 있으면)

- [ ] **Step 1: 사용처 grep**

```bash
grep -rn "PredictSummaryTab" frontend/src --include="*.tsx" --include="*.ts"
grep -n "summary" frontend/src/types/index.ts
```

PredictSummaryTab 호출처 = PredictGroup 일 가능성. enum 'summary' 가 PredictSubTab 에 있으면 제거.

- [ ] **Step 2: PredictGroup 변경**

`PredictGroup.tsx` 의 서브탭 list 에서 summary 제거:

```tsx
// before
const SUBTABS = [
  { key: 'summary', label: '예측 요약', component: PredictSummaryTab },
  { key: 'sales', label: '매출 예측', component: PredictSalesForecastTab },
  ...
];

// after
const SUBTABS = [
  { key: 'sales', label: '매출 예측', component: PredictSalesForecastTab },
  { key: 'financial', label: '재무 시뮬레이션', component: PredictFinancialSimTab },
  { key: 'customer_flow', label: '고객 & 유동인구', component: PredictCustomerFlowTab },
  { key: 'emerging', label: '신흥상권 감지', component: PredictEmergingDistrictTab },
];
```

기본 활성 탭이 'summary' 였으면 'sales' 로 변경. URL `?sub=summary` redirect 처리:

```tsx
// 기본값 설정
const activeSub = (searchParams.get('sub') as PredictSubTab | null) ?? 'sales';
// summary 진입 시 sales 로 redirect
useEffect(() => {
  if (searchParams.get('sub') === 'summary') {
    setSearchParams({ sub: 'sales' }, { replace: true });
  }
}, [searchParams, setSearchParams]);
```

(search params 라이브러리 — react-router 의 useSearchParams 사용 가정. 실 패턴은 grep 후 동일하게)

- [ ] **Step 3: PredictSummaryTab.tsx 삭제**

```bash
rm frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSummaryTab.tsx
```

- [ ] **Step 4: types/index.ts 의 enum 'summary' 제거 (있으면)**

```typescript
// before
export type PredictSubTab = 'summary' | 'sales' | 'financial' | 'customer_flow' | 'emerging';
// after
export type PredictSubTab = 'sales' | 'financial' | 'customer_flow' | 'emerging';
```

- [ ] **Step 5: tsc + grep**

```bash
npx tsc --noEmit
grep -rn "PredictSummaryTab\|'summary'" frontend/src --include="*.tsx" --include="*.ts"
```

tsc EXIT=0. grep 결과 0건 (PredictSummaryTab 사용처 모두 제거됨).

- [ ] **Step 6: Commit**

```bash
git rm frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSummaryTab.tsx
git add frontend/src/components/SimulationResult/dashboard/groups/PredictGroup.tsx frontend/src/types/index.ts
git commit -m "feat(predict): PredictSummaryTab 제거 — 4탭 통일

5 KPI 가 다른 4 서브탭에 분산되어 중복. 본부 영업팀 사용 흐름상
직접 Sales/Financial/CustomerFlow/Emerging 진입이 자연스러움.
URL ?sub=summary → ?sub=sales redirect 추가.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: QuarterlyProjectionChart 라벨 + 1~4분기 fix

**Files:**
- Modify: `frontend/src/components/SimulationResult/QuarterlyProjectionChart.tsx`
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx`

- [ ] **Step 1: 차트 제목 변경**

`PredictSalesForecastTab.tsx` 또는 `QuarterlyProjectionChart.tsx` 의 제목/heading 부분:

```tsx
// before
<h4>TCN-v2 분기별 매출 예측</h4>
// after
<h4>분기별 예상 매출</h4>
```

(grep 으로 정확한 위치 확인 — "TCN-v2" 또는 "분기별 매출 예측" 으로 검색)

- [ ] **Step 2: 분기 1~4 slice + X축 라벨 변경**

`QuarterlyProjectionChart.tsx` 의 데이터 처리:

```tsx
// data prop 받은 후
const limitedData = data.slice(0, 4); // 1~4 분기만
const chartData = limitedData.map((q, idx) => ({
  ...q,
  label: `Q${idx + 1}`,
}));
```

X축의 dataKey 가 `quarter_label` 이나 비슷한 string field 면 그것 사용. recharts XAxis:

```tsx
<XAxis dataKey="label" />
```

- [ ] **Step 3: tsc**

```bash
npx tsc --noEmit
```
EXIT=0.

- [ ] **Step 4: prettier + commit**

```bash
npx prettier --write src/components/SimulationResult/QuarterlyProjectionChart.tsx src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx
git add frontend/src/components/SimulationResult/QuarterlyProjectionChart.tsx frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx
git commit -m "fix(chart): 분기별 매출 — 라벨 + 1~4분기 표시

'TCN-v2 분기별 매출 예측' → '분기별 예상 매출' (모델명 노출 제거).
data.slice(0, 4) + X축 'Q1/Q2/Q3/Q4' 라벨 — 사용자 직관 매칭.
14분기까지 표시되던 bug fix.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: QuarterlyProjectionChart 다중 동 라인 + 범례 (★)

**Files:**
- Modify: `frontend/src/components/SimulationResult/QuarterlyProjectionChart.tsx`
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx`

- [ ] **Step 1: QuarterlyProjectionChart props 변경**

```typescript
// before
interface Props {
  data: QuarterlyProjection[];
  // ... 기존 props
}

// after
interface Props {
  /** 동별 분기 데이터 — 신규 다중 동 모드 */
  data: { district: string; projection: QuarterlyProjection[] }[];
  /** 신뢰구간 음영을 표시할 동 (없으면 winner). 1개 동만 음영 */
  highlightDistrict?: string;
  // ... 기존 다른 props
}
```

- [ ] **Step 2: 차트 렌더 변경**

```tsx
const COLORS = ['#818cf8', '#22d3ee', '#fbbf24', '#f43f5e']; // indigo / cyan / amber / rose (4동)

// data 합치기 — 각 분기 row 에 동별 매출 column 추가
const merged: Array<Record<string, any>> = [];
const maxQuarters = Math.max(...data.map((d) => d.projection.length), 0);
for (let i = 0; i < Math.min(maxQuarters, 4); i++) {
  const row: Record<string, any> = { label: `Q${i + 1}` };
  data.forEach((d) => {
    const q = d.projection[i];
    if (q) row[d.district] = q.revenue ?? null;
  });
  merged.push(row);
}

return (
  <ResponsiveContainer width="100%" height={400}>
    <ComposedChart data={merged}>
      <XAxis dataKey="label" />
      <YAxis tickFormatter={(v) => `${(v / 10000).toFixed(0)}만`} />
      <Tooltip />
      <Legend />
      {data.map((d, idx) => (
        <Line
          key={d.district}
          type="monotone"
          dataKey={d.district}
          stroke={COLORS[idx % COLORS.length]}
          strokeWidth={d.district === highlightDistrict ? 3 : 2}
          dot={d.district === highlightDistrict}
          name={d.district}
        />
      ))}
      {/* 신뢰구간 (음영) — winner 동만 — 별도 area dataKey 추가 필요. 단순 구현은 생략 가능 */}
    </ComposedChart>
  </ResponsiveContainer>
);
```

(기존 신뢰구간 Area 처리는 Step 4 의 자유 옵션. 단순 구현 시 winner 동만 strokeWidth + dot 강조로 충분.)

- [ ] **Step 3: PredictSalesForecastTab 호출처 변경**

```tsx
// before
<QuarterlyProjectionChart data={simResult.quarterly_projection ?? []} />

// after
<QuarterlyProjectionChart
  data={(simResult.district_predictions ?? [])
    .filter((p) => !p.is_excluded_combo)
    .map((p) => ({ district: p.district, projection: p.quarterly_projection ?? [] }))
    .filter((d) => d.projection.length > 0)}
  highlightDistrict={simResult.winner_district ?? undefined}
/>
```

`simResult.district_predictions` 가 비어있는 fallback (단일 동 모드) — 빈 배열이면 차트 hide 또는 winner 만 단일 라인.

- [ ] **Step 4: tsc**

```bash
npx tsc --noEmit
```
EXIT=0.

- [ ] **Step 5: prettier + commit**

```bash
npx prettier --write src/components/SimulationResult/QuarterlyProjectionChart.tsx src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx
git add frontend/src/components/SimulationResult/QuarterlyProjectionChart.tsx frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx
git commit -m "feat(chart): QuarterlyProjectionChart 다중 동 라인 + 범례

/predict 다중 동 응답 (district_predictions 1~4동) 을 색상 구분 라인으로
중첩 표시. 범례에 동명 노출. winner 동은 strokeWidth 3 + dot 으로 강조.
색상: indigo/cyan/amber/rose 4동 한정.

기존 단일 동 모드 (winner 만) 는 district_predictions 비어있을 때 빈 차트.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 유동인구피크 위치 이동 (Demographic → CustomerFlow)

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/tabs/DemographicTab.tsx`
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictCustomerFlowTab.tsx`

- [ ] **Step 1: DemographicTab 의 PeakHourCard 패널 제거**

`DemographicTab.tsx` 의 L145 부근 `living_pop_forecast` 패널 (PeakHourCard 포함) 영역 제거:

```bash
grep -n "PeakHourCard\|living_pop_forecast" frontend/src/components/SimulationResult/dashboard/tabs/DemographicTab.tsx
```

해당 섹션 (`{/* [D — living_pop_forecast P1-D] 유동인구 피크 시간 예측 (TCN) */}` 코멘트 + PeakHourCard JSX) 통째로 삭제.

- [ ] **Step 2: PredictCustomerFlowTab 에 PeakHourCard 추가**

`PredictCustomerFlowTab.tsx` 의 적절한 위치 (modelName "customer_revenue + living_pop_forecast" 텍스트 근처) 에 PeakHourCard 추가:

```tsx
import { PeakHourCard } from '../../charts/PeakHourCard';

// JSX 안
{simResult.living_pop_forecast && (
  <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8">
    <h4 className="text-sm font-black text-stone-100 mb-6 flex items-center gap-2 uppercase tracking-tight">
      유동인구 피크 시간 예측
    </h4>
    <PeakHourCard data={simResult.living_pop_forecast} />
  </div>
)}
```

(PeakHourCard props 가 정확한 이름 확인 — `data` 또는 `forecast` 등. grep 후 호출처 패턴에 맞춤)

- [ ] **Step 3: tsc**

```bash
npx tsc --noEmit
```
EXIT=0.

- [ ] **Step 4: prettier + commit**

```bash
npx prettier --write src/components/SimulationResult/dashboard/tabs/DemographicTab.tsx src/components/SimulationResult/dashboard/sub/predict/PredictCustomerFlowTab.tsx
git add frontend/src/components/SimulationResult/dashboard/tabs/DemographicTab.tsx frontend/src/components/SimulationResult/dashboard/sub/predict/PredictCustomerFlowTab.tsx
git commit -m "feat(predict): 유동인구피크시간 위치 이동 — Demographic → CustomerFlow

living_pop_forecast 가 'AI 분석 - 인구분석' 에 있던 것을 '예측 결과 -
고객&유동인구' 로 이동. 예측 영역이 의미상 더 정합. DemographicTab 의 P1-D
섹션 제거, PredictCustomerFlowTab 에 PeakHourCard 추가.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 분석 신뢰도 완전 제거

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictFinancialSimTab.tsx`

- [ ] **Step 1: synthAttr.confidence 추출 + confidencePct 변수 제거**

`PredictFinancialSimTab.tsx` L26-28 제거:

```typescript
// before
const synthAttr = simResult.agent_attributions?.find((a) => a.id === 'synthesis');
const confidencePct =
  synthAttr?.confidence != null ? Math.round(synthAttr.confidence * 100) : null;

// after
// (모두 제거 — 분석 신뢰도가 backend hardcoded 0.85 이라 의미 없음)
```

- [ ] **Step 2: ProfitSimulationPanelFull 의 confidencePct prop 제거**

```tsx
// before
<ProfitSimulationPanelFull
  monthlyRev={monthlyRev}
  monthlyCost={monthlyCost}
  netProfit={netProfit}
  margin={margin}
  bepMonths={bepMonths}
  confidencePct={confidencePct}
/>

// after
<ProfitSimulationPanelFull
  monthlyRev={monthlyRev}
  monthlyCost={monthlyCost}
  netProfit={netProfit}
  margin={margin}
  bepMonths={bepMonths}
/>
```

- [ ] **Step 3: ProfitSimulationPanelFull 컴포넌트 정의에서 분석 신뢰도 영역 제거**

같은 파일 내부 (L67~ ) 의 ProfitSimulationPanelFull props + JSX:

```typescript
// before
interface ProfitPanelProps {
  monthlyRev: number | null;
  monthlyCost: number | null;
  netProfit: number | null;
  margin: number | null;
  bepMonths: number | null;
  confidencePct: number | null; // 제거
}

// after
interface ProfitPanelProps {
  monthlyRev: number | null;
  monthlyCost: number | null;
  netProfit: number | null;
  margin: number | null;
  bepMonths: number | null;
}
```

JSX L135 부근 "분석 신뢰도" 라벨 + 값 + 진행바 (`confidencePct` 사용 영역) 통째로 제거.

- [ ] **Step 4: tsc**

```bash
npx tsc --noEmit
```
EXIT=0.

- [ ] **Step 5: prettier + commit**

```bash
npx prettier --write src/components/SimulationResult/dashboard/sub/predict/PredictFinancialSimTab.tsx
git add frontend/src/components/SimulationResult/dashboard/sub/predict/PredictFinancialSimTab.tsx
git commit -m "fix(financial): 분석 신뢰도 완전 제거 — backend hardcoded 0.85 placeholder

backend synthesis.py 의 confidence=0.85 가 모든 시뮬에서 동일 값. 본부
영업팀에 'AI 85% 확신' misleading. 데이터 없음 정책상 제거. 향후 backend가
실 confidence 산출 시 별도 cycle 에서 재추가.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: AnalyzeAiSummaryTab 레이아웃 — EntrySignalLight 제거 + 상하 위치 변경

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx`

- [ ] **Step 1: 현재 레이아웃 파악**

```bash
grep -n "EntrySignalLight\|DecisionCard\|synthesis" frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx
```

현재 추정:
- 상단 grid: 좌(DecisionCard) / 우(EntrySignalLight)
- 하단: synthesis + 최종 권고

- [ ] **Step 2: EntrySignalLight 제거**

JSX 에서 `<EntrySignalLight ... />` 호출 제거. import 도 (다른 곳에서 안 쓰면 — 확인 후) 제거.

```bash
grep -rn "EntrySignalLight" frontend/src --include="*.tsx"
```

다른 사용처 0 이면 import 제거 OK.

- [ ] **Step 3: 위치 변경 — synthesis 상단, DecisionCard 하단**

```tsx
return (
  <div className="space-y-6">
    {/* 상단 — synthesis 종합 + 최종 권고 (이미 Task 1 에서 react-markdown 처리됨) */}
    <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8">
      {/* synthesis ReactMarkdown 영역 */}
    </div>

    {/* 하단 — LLM 출처 통합 판단 (DecisionCard) */}
    {/* 1등 동 + Top 3 칩 (#H6 기존 작업) 도 이 영역과 묶을지 강민 결정 — 일단 분리 보존 */}
    <DecisionCard ... />
  </div>
);
```

기존 grid (좌/우) 가 있으면 단일 column 으로. 1등 동 + Top 3 칩 (#H6) 영역은 보존 (Task 7 은 EntrySignalLight + 상하 변경 한정).

- [ ] **Step 4: tsc**

```bash
npx tsc --noEmit
```
EXIT=0.

- [ ] **Step 5: prettier + commit**

```bash
npx prettier --write src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx
git add frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx
git commit -m "fix(analyze): EntrySignalLight 제거 + synthesis 상단 / DecisionCard 하단

EntrySignalLight 와 DecisionCard 가 같은 정보를 다르게 표시 (STOP vs 진입권장
모순). DecisionCard 가 LLM 출처 통합 판단으로 더 정확. EntrySignalLight 제거.

영업팀장 사용 시나리오: synthesis 종합 결론 먼저 → DecisionCard (보조) 흐름.
상하 위치 변경.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: 정합성 검증

**Files:** (검증만)

- [ ] **Step 1: tsc**

```bash
cd /c/mapo-franchise-simulator/frontend && npx tsc --noEmit
```
EXIT=0.

- [ ] **Step 2: vitest**

```bash
npx vitest run
```

73건 (이전 마이그레이션) 모두 통과 + 본 cycle 의 신규 컴포넌트 변경이 기존 테스트 깨지 않는지.

- [ ] **Step 3: build**

```bash
npm run build
```

EXIT=0. 메인 chunk size — 이전 596 kB. react-markdown 추가로 ~50 kB 정도 증가 예상 — 600~650 kB 안. 단 chunk warning 더 길어질 수 있음 (acceptable).

- [ ] **Step 4: prettier**

```bash
npx prettier --write src
```

drift 없으면 0 변경.

- [ ] **Step 5: 수동 검증 (강민 직접)**

체크리스트 수행:
- [ ] AnalyzeAiSummaryTab 상단 synthesis 마크다운 H1/H2 정상 렌더
- [ ] EntrySignalLight 사라짐, DecisionCard 하단
- [ ] PredictGroup 4탭 (Summary 제거, 기본 Sales)
- [ ] 분기별 매출: "분기별 예상 매출" 제목 + Q1~Q4 + 다중 동 라인 + 범례
- [ ] PredictCustomerFlowTab 안 PeakHourCard 표시
- [ ] DemographicTab 안 PeakHourCard 사라짐
- [ ] PredictFinancialSimTab "분석 신뢰도 85%" 영역 사라짐

Self-Review:

**1. Spec coverage:**
- §2.1 react-markdown → Task 1 ✓
- §2.2 PredictSummaryTab 제거 → Task 2 ✓
- §2.3 라벨 + 1~4분기 → Task 3 ✓
- §2.4 다중 동 라인 → Task 4 ✓
- §2.5 PeakHour 위치 → Task 5 ✓
- §2.6 분석 신뢰도 → Task 6 ✓
- §2.7 EntrySignal + 레이아웃 → Task 7 ✓
- §4 검증 → Task 8 ✓

**2. Placeholder scan:** 없음. 신뢰구간 음영 정책 (winner 만 강조 — strokeWidth + dot) 명시.

**3. Type consistency:** `PredictSubTab` enum 변경, `QuarterlyProjectionChart` props 변경 — Task 2/3/4 일관 사용.
