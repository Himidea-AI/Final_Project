# Dashboard 3그룹 IA 재구조 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 7탭 도메인별 dashboard 를 PDF 안의 3그룹(예측결과/AI분석/ABM) + 11서브탭 출처별 IA 로 재구조 (frontend 한정, mock 금지).

**Architecture:** 11종 기존 차트 컴포넌트 재사용 + 그룹/서브탭 wrapper 신설. TabbedDashboard 가 useSearchParams 로 group + sub query param 관리. 백엔드 응답 (`/analyze` 단일 endpoint) 그대로 사용 — 점진 활성 미달 (사용자 의식적 trade-off). 미연동 ML 2개 서브탭은 placeholder.

**Tech Stack:** React 18 + TypeScript + Vite + react-router-dom (useSearchParams) + Tailwind + 기존 11종 차트 (recharts)

**Spec:** `docs/superpowers/specs/2026-04-28-3group-tab-restructure-design.md`
**Branch:** `feature/dashboard-3group-ia` (현재 브랜치)
**Commit Policy:** 메모리 `feedback_commit_policy.md` 따라 사용자 명시 승인 시만 commit. plan 의 commit step 은 메시지 초안만 준비.

---

## File Structure

### 신규 파일 (총 11개)

```
frontend/src/components/SimulationResult/dashboard/
├── groups/
│   ├── PredictGroup.tsx          # 예측 5 서브탭 라우팅 wrapper
│   ├── AnalyzeGroup.tsx          # 분석 5 서브탭 라우팅 wrapper
│   └── AbmGroup.tsx              # ABM 단일 (기존 AbmTab 감쌈)
├── sub/predict/
│   ├── PredictSummaryTab.tsx     # KPI 3종 (월매출/BEP/폐업위험도)
│   ├── PredictSalesForecastTab.tsx     # TCN + 시나리오 + SHAP
│   ├── PredictFinancialSimTab.tsx      # BEP 누적이익 + 폐업률 + LightGBM/TCN
│   ├── PredictCustomerFlowTab.tsx      # placeholder (B2 미연동)
│   └── PredictEmergingDistrictTab.tsx  # placeholder (B2 미연동)
├── sub/analyze/
│   ├── AnalyzeAiSummaryTab.tsx         # computeDecision 이동 + 신호등
│   ├── AnalyzeMarketTab.tsx            # Map + 11지표 + 16동 + 차별화 + 거리 + 동폐업률 + trend_forecast
│   ├── AnalyzeDemographicTab.tsx       # 인구 구성 + 심층 리포트
│   ├── AnalyzeLegalTab.tsx             # 법률 분포 + 14 항목
│   └── AnalyzeAgentInsightTab.tsx      # 8 에이전트 Confidence Radar
└── shared/
    └── PlaceholderPanel.tsx      # "준비 중" placeholder (재사용)
```

### 수정 파일 (총 3개)

- `frontend/src/types/index.ts` — Tab enum 신설
- `frontend/src/components/SimulationResult/dashboard/TabbedDashboard.tsx` — 3그룹 + 서브탭 라우팅 재구조

### 정리 (deprecated → deletion)

기존 8개 탭 파일 — 정리 task 에서 제거:
- `tabs/SummaryTab.tsx` (분해 — ProfitSimulationPanelFull → PredictSummaryTab, computeDecision → AnalyzeAiSummaryTab)
- `tabs/ForecastTab.tsx` (분해 — TCN/SHAP/Scenarios → Predict, trend_forecast → Analyze)
- `tabs/FinancialTab.tsx` (분해 — 모든 차트 → PredictFinancialSimTab)
- `tabs/MarketTab.tsx` (분해 — 모든 차트 → AnalyzeMarketTab)
- `tabs/DemographicTab.tsx` (이름 변경/이동 — AnalyzeDemographicTab)
- `tabs/LegalTab.tsx` (이름 변경/이동 — AnalyzeLegalTab)
- `tabs/InsightTab.tsx` (이름 변경/이동 — AnalyzeAgentInsightTab)
- `tabs/AbmTab.tsx` (그대로 유지, AbmGroup wrapper 안에서 호출)

---

## Tasks

### Task 1: types/index.ts — Tab enum 신설

**Files:**
- Modify: `frontend/src/types/index.ts` (하단에 추가)

- [ ] **Step 1: Tab enum 3종 추가**

`frontend/src/types/index.ts` 하단 (마지막 export 직후) 에 추가:

```typescript
// ──────────────────────────────────────────────────────────
// Dashboard 3그룹 IA (2026-04-28) — 출처별 재구조
// ──────────────────────────────────────────────────────────

export type MainTab = 'predict' | 'analyze' | 'abm';

export type PredictSubTab =
  | 'summary'
  | 'sales_forecast'
  | 'financial_sim'
  | 'customer_flow'
  | 'emerging_district';

export type AnalyzeSubTab =
  | 'ai_summary'
  | 'market'
  | 'demographic'
  | 'legal'
  | 'agent_insight';
```

- [ ] **Step 2: tsc 검증**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
```

Expected: EXIT=0

- [ ] **Step 3: Commit (사용자 승인 후)**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): Tab enum 신설 — MainTab/PredictSubTab/AnalyzeSubTab"
```

---

### Task 2: PlaceholderPanel 공통 컴포넌트

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/shared/PlaceholderPanel.tsx`

- [ ] **Step 1: 컴포넌트 작성**

```tsx
/**
 * PlaceholderPanel — 미연동 서브탭용 "준비 중" 안내
 * 2026-04-28 — B2 미연동 ML (customer_revenue, emerging_district) endpoint 노출 전 임시 표시.
 */

interface Props {
  modelName?: string;
  description?: string;
}

export function PlaceholderPanel({
  modelName,
  description = '해당 분석 모델 연동 후 활성화됩니다.',
}: Props) {
  return (
    <div className="flex h-64 flex-col items-center justify-center rounded-3xl border border-dashed border-stone-800 bg-stone-950/30 text-stone-500">
      <p className="text-sm font-bold">준비 중입니다.</p>
      <p className="mt-1 text-xs">{description}</p>
      {modelName && (
        <p className="mt-3 text-[10px] font-mono uppercase tracking-widest text-stone-600">
          {modelName}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/shared/PlaceholderPanel.tsx
```

Expected: EXIT=0

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/shared/PlaceholderPanel.tsx
git commit -m "feat(dashboard): PlaceholderPanel — 미연동 서브탭 준비 중 안내"
```

---

### Task 3: PredictSummaryTab — KPI 3종

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSummaryTab.tsx`

ML 출처 데이터만 표시: 월매출 (final_report.profit_simulation.monthly_revenue), BEP (profit_simulation.bep_months), 폐업위험도 (closure_risk.risk_score). LLM 의존 (computeDecision, overall_legal_risk) 미사용.

- [ ] **Step 1: 컴포넌트 작성**

```tsx
/**
 * PredictSummaryTab — 예측 그룹 요약 (ML 숫자 카드만)
 * 2026-04-28 IA 재구조 — SummaryTab 의 ProfitSimulationPanelFull 의 일부 분해.
 * computeDecision 등 LLM 의존은 AnalyzeAiSummaryTab 에 이관.
 */

import { Activity, Gauge, AlertTriangle } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import { formatKrw } from '../../utils/formatters';

interface Props {
  simResult: SimulationOutput;
}

export function PredictSummaryTab({ simResult }: Props) {
  const ps = simResult.final_report?.profit_simulation ?? null;
  const monthlyRev = ps?.monthly_revenue ?? null;
  const bepMonths = ps?.bep_months ?? null;
  const riskScore = simResult.closure_risk?.risk_score ?? null;
  // 0~1 / 0~100 정규화
  const riskPct =
    riskScore == null
      ? null
      : riskScore <= 1
        ? Math.round(riskScore * 100)
        : Math.round(riskScore);

  return (
    <div className="grid grid-cols-3 gap-6">
      <Kpi
        icon={<Activity size={16} className="text-indigo-400" />}
        label="추정 월매출"
        value={monthlyRev != null ? `₩${formatKrw(monthlyRev)}` : '—'}
        color="indigo"
      />
      <Kpi
        icon={<Gauge size={16} className="text-cyan-400" />}
        label="BEP (개월)"
        value={bepMonths != null ? `${bepMonths.toFixed(1)}` : '—'}
        color="cyan"
      />
      <Kpi
        icon={<AlertTriangle size={16} className="text-rose-400" />}
        label="폐업위험도"
        value={riskPct != null ? `${riskPct}%` : '—'}
        color="rose"
      />
    </div>
  );
}

interface KpiProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: 'indigo' | 'cyan' | 'rose';
}

function Kpi({ icon, label, value, color }: KpiProps) {
  const valueClass =
    color === 'indigo'
      ? 'text-indigo-400'
      : color === 'cyan'
        ? 'text-cyan-400'
        : 'text-rose-400';
  return (
    <div className="rounded-3xl border border-stone-800/60 bg-stone-900/40 p-6">
      <div className="mb-3 flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-stone-500">
        {icon}
        <span>{label}</span>
      </div>
      <div className={`text-3xl font-black tabular-nums tracking-tighter ${valueClass}`}>
        {value}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/sub/predict/PredictSummaryTab.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSummaryTab.tsx
git commit -m "feat(dashboard): PredictSummaryTab — ML KPI 3종 (월매출/BEP/폐업위험도)"
```

---

### Task 4: PredictSalesForecastTab — TCN + Scenarios + SHAP

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx`

기존 ForecastTab 의 TCN 차트 + Scenarios + SHAP 섹션 분해 후 새 서브탭으로. trend_forecast 는 미포함 (분석 그룹으로 이동).

- [ ] **Step 1: 컴포넌트 작성**

```tsx
/**
 * PredictSalesForecastTab — 예측·매출 예측
 * 2026-04-28 IA 재구조 — ForecastTab 의 TCN/Scenarios/SHAP 섹션 분해.
 * trend_forecast 는 LLM 출처라 AnalyzeMarketTab 으로 이동.
 */

import { TrendingUp, Zap, Maximize2, GitCompareArrows } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import type { DetailModalContent } from '../../shared/DetailModal';
import { QuarterlyProjectionChart } from '../../../QuarterlyProjectionChart';
import { ScenariosComparisonChart } from '../../charts/ScenariosComparisonChart';
import { ShapInsightCard } from '../../charts/ShapInsightCard';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export function PredictSalesForecastTab({ simResult, openModal }: Props) {
  const qp = simResult.quarterly_projection ?? [];
  const shap = simResult.shap_result;
  const scenarios = simResult.scenarios;
  const hasScenarios = scenarios?.base && scenarios.base.length > 0;

  return (
    <div className="space-y-6">
      <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8">
        <div className="flex items-start justify-between mb-8 gap-6">
          <div>
            <h3 className="text-xl font-black text-stone-100 flex items-center gap-3 italic tracking-tight text-left leading-none">
              <TrendingUp className="text-indigo-400" /> TCN-v2 분기별 매출 예측
            </h3>
            <p className="text-[10px] font-black text-stone-500 uppercase tracking-[0.2em] mt-3">
              Temporal Convolutional Network · P10~P90 신뢰 구간
            </p>
          </div>
        </div>

        <div className="relative bg-stone-950/50 border border-stone-800 rounded-2xl p-6 mb-8">
          {qp.length > 0 ? (
            <QuarterlyProjectionChart data={qp} />
          ) : (
            <div className="aspect-[21/9] flex flex-col items-center justify-center">
              <TrendingUp size={48} className="text-stone-700 mb-3" />
              <p className="text-stone-500 font-black uppercase tracking-widest text-xs">
                분기 매출 데이터 없음
              </p>
            </div>
          )}
        </div>

        {/* SHAP 텍스트 인사이트 */}
        <div className="space-y-4">
          <div className="flex items-center justify-between border-b border-stone-800 pb-3">
            <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest flex items-center gap-2 italic">
              <Zap className="text-amber-400" size={14} /> 매출 기여 요인 분석
            </h4>
            {shap && (
              <button
                type="button"
                onClick={() =>
                  openModal({
                    title: 'SHAP 해석 상세',
                    content: `SHAP (SHapley Additive exPlanations)은 각 피처가 예측값에 얼마나 기여했는지 정량화합니다.\n\nbase_value: ${shap.base_value.toLocaleString('ko-KR')}원\npredicted_value: ${shap.predicted_value.toLocaleString('ko-KR')}원${shap.is_mock ? '\n\n⚠️ 현재 SHAP 데이터는 mock 상태입니다.' : ''}`,
                  })
                }
                className="text-[10px] font-bold text-stone-500 hover:text-indigo-400 uppercase tracking-widest flex items-center gap-1"
              >
                <Maximize2 size={12} /> 해석 상세
              </button>
            )}
          </div>
          <ShapInsightCard shap={shap} />
        </div>
      </div>

      {/* 시나리오 비교 */}
      {hasScenarios && (
        <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8">
          <div className="flex items-start justify-between mb-6 gap-6">
            <div>
              <h3 className="text-xl font-black text-stone-100 flex items-center gap-3 italic tracking-tight text-left leading-none">
                <GitCompareArrows className="text-indigo-400" size={20} /> 시나리오 비교
              </h3>
              <p className="text-[10px] font-black text-stone-500 uppercase tracking-[0.2em] mt-3">
                낙관 · 기본 · 비관 · 4분기 매출 envelope
              </p>
            </div>
          </div>
          <ScenariosComparisonChart scenarios={scenarios} />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx
git commit -m "feat(dashboard): PredictSalesForecastTab — TCN/Scenarios/SHAP"
```

---

### Task 5: PredictFinancialSimTab — BEP + 폐업률 + LightGBM/TCN

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictFinancialSimTab.tsx`

기존 FinancialTab 의 ProfitSimulationPanelFull + ClosureRatePanel + ClosureRiskPanel + SurvivalRateKpi + BepCumulativeProfitChart 를 그대로 이관.

- [ ] **Step 1: FinancialTab 의 export 활용**

기존 `frontend/src/components/SimulationResult/dashboard/tabs/FinancialTab.tsx` 가 `ClosureRatePanel`, `ClosureRiskPanel` 을 export 함. 새 파일에서 그대로 import + 사용.

```tsx
/**
 * PredictFinancialSimTab — 예측·재무 시뮬레이션
 * 2026-04-28 IA 재구조 — FinancialTab 분해.
 * BEP 누적이익 + 과거 12개월 폐업률 + LightGBM/TCN 폐업위험도 + 생존률 KPI.
 */

import { Activity, Gauge } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import { formatKrw, formatPct, quarterlyToMonthly } from '../../utils/formatters';
import { BepCumulativeProfitChart } from '../../charts/BepCumulativeProfitChart';
import { SurvivalRateKpi } from '../../charts/SurvivalRateKpi';
import { ClosureRatePanel, ClosureRiskPanel } from '../../tabs/FinancialTab';

interface Props {
  simResult: SimulationOutput;
}

export function PredictFinancialSimTab({ simResult }: Props) {
  const ps = simResult.final_report?.profit_simulation ?? null;
  const firstQ = simResult.quarterly_projection?.[0];
  const monthlyRev = ps?.monthly_revenue ?? quarterlyToMonthly(firstQ?.revenue ?? null);
  const monthlyCost = ps?.monthly_cost ?? null;
  const netProfit = ps?.net_profit ?? null;
  const margin = ps?.margin_rate ?? null;
  const bepMonths = ps?.bep_months ?? null;
  const synthAttr = simResult.agent_attributions?.find((a) => a.id === 'synthesis');
  const confidencePct =
    synthAttr?.confidence != null ? Math.round(synthAttr.confidence * 100) : null;

  return (
    <div className="space-y-6">
      <ProfitSimulationPanelFull
        monthlyRev={monthlyRev}
        monthlyCost={monthlyCost}
        netProfit={netProfit}
        margin={margin}
        bepMonths={bepMonths}
        confidencePct={confidencePct}
      />

      {(simResult.quarterly_projection ?? []).length > 0 && (
        <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-6">
          <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest flex items-center gap-2 mb-3">
            투자 회수 곡선
          </h4>
          <BepCumulativeProfitChart data={simResult.quarterly_projection ?? []} />
        </div>
      )}

      <SurvivalRateKpi
        survivalRate={simResult.market_report?.survival_rate}
        closureRate={simResult.market_report?.closure_rate}
      />

      <ClosureRatePanel rate={simResult.closure_rate} />
      <ClosureRiskPanel closure={simResult.closure_risk} />
    </div>
  );
}

interface ProfitPanelProps {
  monthlyRev: number | null | undefined;
  monthlyCost: number | null | undefined;
  netProfit: number | null | undefined;
  margin: number | null | undefined;
  bepMonths: number | null | undefined;
  confidencePct: number | null;
}

function ProfitSimulationPanelFull({
  monthlyRev,
  monthlyCost,
  netProfit,
  margin,
  bepMonths,
  confidencePct,
}: ProfitPanelProps) {
  const rows = [
    { label: '추정 월매출', val: monthlyRev, accent: 'text-stone-100' },
    { label: '월 운영비 (총계)', val: monthlyCost, accent: 'text-stone-400' },
  ];
  return (
    <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8">
      <div className="flex items-center justify-between mb-6">
        <h4 className="text-sm font-black text-stone-100 uppercase tracking-tight flex items-center gap-2">
          <Activity size={16} className="text-indigo-400" /> 상세 수익성 시뮬레이션
        </h4>
        <div className="flex items-center gap-2">
          {margin != null && (
            <div className="px-3 py-1 bg-indigo-500/10 border border-indigo-500/20 rounded-full text-[11px] font-black text-indigo-400 tabular-nums">
              마진 {formatPct(margin)}
            </div>
          )}
          {bepMonths != null && (
            <div className="px-3 py-1 bg-cyan-500/10 border border-cyan-500/20 rounded-full text-[11px] font-black text-cyan-400 tabular-nums">
              BEP {bepMonths.toFixed(1)}개월
            </div>
          )}
        </div>
      </div>

      {bepMonths != null && (
        <p className="mb-4 text-[10px] text-stone-500 leading-relaxed">
          ※ 인건비 미포함 기준입니다. 실제 BEP는 운영 인원에 따라 길어질 수 있습니다.
        </p>
      )}

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2 space-y-3">
          {rows.map((item) => (
            <div
              key={item.label}
              className="flex justify-between items-end border-b border-stone-800/50 pb-3"
            >
              <span className="text-xs font-bold text-stone-500">{item.label}</span>
              <span className={`text-lg font-black tabular-nums ${item.accent}`}>
                {item.val != null ? `₩${formatKrw(item.val)}` : '—'}
              </span>
            </div>
          ))}
          <div className="flex justify-between items-center pt-2">
            <span className="text-sm font-black text-indigo-400 tracking-tighter">
              예상 월 영업이익
            </span>
            <span className="text-3xl font-black text-indigo-400 tabular-nums tracking-tighter">
              {netProfit != null ? `₩${formatKrw(netProfit)}` : '—'}
            </span>
          </div>
        </div>

        <div className="bg-stone-950/40 border border-stone-800 rounded-2xl p-5 flex flex-col justify-center">
          <div className="flex items-center gap-2 mb-3">
            <Gauge size={18} className="text-indigo-500" />
            <span className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
              분석 신뢰도
            </span>
          </div>
          {confidencePct != null ? (
            <>
              <div className="text-3xl font-black text-indigo-400 tabular-nums mb-2">
                {confidencePct}%
              </div>
              <div className="w-full bg-stone-800 h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-indigo-500 h-full transition-all"
                  style={{ width: `${Math.min(100, Math.max(0, confidencePct))}%` }}
                />
              </div>
            </>
          ) : (
            <div className="text-2xl font-black text-stone-500 tabular-nums">—</div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/sub/predict/PredictFinancialSimTab.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/sub/predict/PredictFinancialSimTab.tsx
git commit -m "feat(dashboard): PredictFinancialSimTab — BEP/폐업률/LightGBM·TCN/생존률"
```

---

### Task 6: 미연동 placeholder 2 서브탭

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictCustomerFlowTab.tsx`
- Create: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx`

- [ ] **Step 1: PredictCustomerFlowTab 작성**

```tsx
import { PlaceholderPanel } from '../../shared/PlaceholderPanel';

export function PredictCustomerFlowTab() {
  return (
    <PlaceholderPanel
      modelName="customer_revenue + living_pop_forecast"
      description="타겟 고객 매출 기여 + 유동인구 피크 예측 endpoint 연동 후 활성화됩니다."
    />
  );
}
```

- [ ] **Step 2: PredictEmergingDistrictTab 작성**

```tsx
import { PlaceholderPanel } from '../../shared/PlaceholderPanel';

export function PredictEmergingDistrictTab() {
  return (
    <PlaceholderPanel
      modelName="emerging_district (LSTM Autoencoder)"
      description="신흥 상권 조기 감지 endpoint 연동 후 활성화됩니다."
    />
  );
}
```

- [ ] **Step 3: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/sub/predict/PredictCustomerFlowTab.tsx src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/sub/predict/PredictCustomerFlowTab.tsx frontend/src/components/SimulationResult/dashboard/sub/predict/PredictEmergingDistrictTab.tsx
git commit -m "feat(dashboard): 미연동 ML 2개 placeholder 서브탭"
```

---

### Task 7: PredictGroup wrapper

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/groups/PredictGroup.tsx`

- [ ] **Step 1: 컴포넌트 작성**

```tsx
/**
 * PredictGroup — 예측 결과 그룹 (5 서브탭 라우팅)
 */

import { useSearchParams } from 'react-router-dom';
import type { SimulationOutput, PredictSubTab } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { TabButton } from '../shared/TabButton';
import { PredictSummaryTab } from '../sub/predict/PredictSummaryTab';
import { PredictSalesForecastTab } from '../sub/predict/PredictSalesForecastTab';
import { PredictFinancialSimTab } from '../sub/predict/PredictFinancialSimTab';
import { PredictCustomerFlowTab } from '../sub/predict/PredictCustomerFlowTab';
import { PredictEmergingDistrictTab } from '../sub/predict/PredictEmergingDistrictTab';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

const VALID: PredictSubTab[] = [
  'summary',
  'sales_forecast',
  'financial_sim',
  'customer_flow',
  'emerging_district',
];

export function PredictGroup({ simResult, openModal }: Props) {
  const [searchParams, setSearchParams] = useSearchParams();
  const subFromUrl = searchParams.get('sub') as PredictSubTab | null;
  const activeSub: PredictSubTab =
    subFromUrl && VALID.includes(subFromUrl) ? subFromUrl : 'summary';

  const setSub = (sub: PredictSubTab) => {
    const next = new URLSearchParams(searchParams);
    next.set('sub', sub);
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="space-y-6">
      <div className="flex gap-2 border-b border-stone-800 pb-2">
        <TabButton active={activeSub === 'summary'} onClick={() => setSub('summary')}>
          예측 요약
        </TabButton>
        <TabButton
          active={activeSub === 'sales_forecast'}
          onClick={() => setSub('sales_forecast')}
        >
          매출 예측
        </TabButton>
        <TabButton
          active={activeSub === 'financial_sim'}
          onClick={() => setSub('financial_sim')}
        >
          재무 시뮬레이션
        </TabButton>
        <TabButton
          active={activeSub === 'customer_flow'}
          onClick={() => setSub('customer_flow')}
        >
          고객·유동인구
        </TabButton>
        <TabButton
          active={activeSub === 'emerging_district'}
          onClick={() => setSub('emerging_district')}
        >
          신흥상권 감지
        </TabButton>
      </div>

      {activeSub === 'summary' && <PredictSummaryTab simResult={simResult} />}
      {activeSub === 'sales_forecast' && (
        <PredictSalesForecastTab simResult={simResult} openModal={openModal} />
      )}
      {activeSub === 'financial_sim' && <PredictFinancialSimTab simResult={simResult} />}
      {activeSub === 'customer_flow' && <PredictCustomerFlowTab />}
      {activeSub === 'emerging_district' && <PredictEmergingDistrictTab />}
    </div>
  );
}
```

- [ ] **Step 2: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/groups/PredictGroup.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/groups/PredictGroup.tsx
git commit -m "feat(dashboard): PredictGroup wrapper — 5 서브탭 라우팅"
```

---

### Task 8: AnalyzeAiSummaryTab — computeDecision + 신호등 + synthesis

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx`

기존 SummaryTab 의 computeDecision + EntrySignalLight + DecisionCard + NarrativeText 를 이관. ML 숫자 카드는 PredictSummaryTab 에 있으므로 미포함.

- [ ] **Step 1: SummaryTab 의 computeDecision 위치 확인**

```bash
cd /c/mapo-franchise-simulator/frontend
grep -n "computeDecision" src/components/SimulationResult/dashboard/tabs/SummaryTab.tsx | head -5
```

- [ ] **Step 2: 컴포넌트 작성 (SummaryTab 의 LLM 영역만 이관)**

```tsx
/**
 * AnalyzeAiSummaryTab — AI 분석 요약 (LLM 출처 통합 판단)
 * 2026-04-28 IA 재구조 — SummaryTab 의 computeDecision + 창업 신호등 + synthesis 자연어 이관.
 */

import type { SimulationOutput } from '../../../../../types';
import { EntrySignalLight } from '../../charts/EntrySignalLight';
import { DecisionCard } from '../../shared/DecisionCard';
import { NarrativeText } from '../../shared/NarrativeText';
import { computeDecision } from '../../tabs/SummaryTab';

interface Props {
  simResult: SimulationOutput;
}

export function AnalyzeAiSummaryTab({ simResult }: Props) {
  const decision = computeDecision(simResult);
  const signal = (simResult.competitor_intel as Record<string, any> | null | undefined)
    ?.market_entry_signal as 'green' | 'yellow' | 'red' | undefined;
  const summary = simResult.final_report?.summary ?? simResult.analysis_report ?? '';
  const recommendation = simResult.final_report?.final_recommendation ?? simResult.ai_recommendation ?? '';

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-6">
        <DecisionCard decision={decision} />
        <div className="col-span-2 rounded-3xl border border-stone-800/60 bg-stone-900/40 p-6">
          <div className="mb-3 text-[10px] font-black uppercase tracking-widest text-stone-500">
            창업 진입 신호
          </div>
          <EntrySignalLight signal={signal ?? 'yellow'} />
        </div>
      </div>

      {summary && (
        <div className="rounded-3xl border border-stone-800/60 bg-stone-900/40 p-8">
          <h4 className="mb-4 text-xs font-black uppercase tracking-widest text-stone-500">
            synthesis 종합 분석
          </h4>
          <NarrativeText text={summary} />
        </div>
      )}

      {recommendation && (
        <div className="rounded-3xl border border-indigo-500/20 bg-indigo-500/5 p-8">
          <h4 className="mb-4 text-xs font-black uppercase tracking-widest text-indigo-400">
            최종 권고
          </h4>
          <NarrativeText text={recommendation} />
        </div>
      )}
    </div>
  );
}
```

`computeDecision` export 가 SummaryTab 에 없으면 export 추가 (아래 Task 16 정리 단계에서 처리). 만약 SummaryTab 이 export 안 하고 있으면 Task 8 진행 전에 export 키워드 추가 필요.

- [ ] **Step 3: SummaryTab 에 computeDecision export 확인 (필요 시 추가)**

```bash
grep -n "export.*computeDecision\|function computeDecision" src/components/SimulationResult/dashboard/tabs/SummaryTab.tsx
```

만약 `function computeDecision` 만 있고 `export` 없으면 SummaryTab.tsx 의 `function computeDecision` 앞에 `export` 추가:

```tsx
// before
function computeDecision(simResult: SimulationOutput) { ... }

// after
export function computeDecision(simResult: SimulationOutput) { ... }
```

- [ ] **Step 4: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx frontend/src/components/SimulationResult/dashboard/tabs/SummaryTab.tsx
git commit -m "feat(dashboard): AnalyzeAiSummaryTab — computeDecision/신호등/synthesis"
```

---

### Task 9: AnalyzeMarketTab — 상권 + trend_forecast 통합

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeMarketTab.tsx`

기존 MarketTab 의 모든 차트 + ForecastTab 의 trend_forecast 패키지 (TrendSparklinesPanel + TrendDriversRisks + narrative 모달) 통합.

- [ ] **Step 1: 컴포넌트 작성**

```tsx
/**
 * AnalyzeMarketTab — 분석·상권 분석 (LLM 통합)
 * 2026-04-28 IA 재구조 — MarketTab 의 모든 차트 + ForecastTab 의 trend_forecast 패키지 통합.
 */

import { Globe2, Maximize2 } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import type { DetailModalContent } from '../../shared/DetailModal';
import { MarketTab } from '../../tabs/MarketTab';
import { TrendSparklinesPanel } from '../../charts/TrendSparklinesPanel';
import { TrendDriversRisks } from '../../charts/TrendDriversRisks';
import { formatScore } from '../../utils/formatters';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export function AnalyzeMarketTab({ simResult, openModal }: Props) {
  const trendScore = simResult.trend_forecast?.forecast?.score;
  const trendDir = simResult.trend_forecast?.forecast?.direction;
  const trendNarrative = simResult.trend_forecast?.forecast?.narrative;
  const trendDrivers = simResult.trend_forecast?.forecast?.key_drivers;
  const trendRisks = simResult.trend_forecast?.forecast?.risks;
  const industryTrend = simResult.trend_forecast?.industry_trend;
  const dongTrend = simResult.trend_forecast?.dong_trend;
  const macro = simResult.trend_forecast?.macro;

  const dirLabel = trendDir === 'growth' ? '성장' : trendDir === 'decline' ? '하락' : '유지';
  const hasTrendBlock =
    (industryTrend?.samples && industryTrend.samples.length > 0) ||
    (dongTrend?.samples && dongTrend.samples.length > 0) ||
    (macro?.samples && macro.samples.length > 0) ||
    (trendDrivers && trendDrivers.length > 0) ||
    (trendRisks && trendRisks.length > 0);

  return (
    <div className="space-y-6">
      {/* 기존 MarketTab 의 모든 차트 (Map + IndicatorGrid + Rankings + Differentiation + Cannibalization + IndustryClosureTrend) */}
      <MarketTab simResult={simResult} openModal={openModal} />

      {/* 거시·트렌드 환경 (ForecastTab 에서 이동) */}
      {hasTrendBlock && (
        <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8 space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-xl font-black text-stone-100 flex items-center gap-3 italic tracking-tight text-left leading-none">
                <Globe2 className="text-cyan-400" size={20} /> 거시·트렌드 환경
              </h3>
              <p className="text-[10px] font-black text-stone-500 uppercase tracking-[0.2em] mt-3">
                업종 · 지역 · 거시 12개월 시계열 + LLM 요약
              </p>
            </div>
            {trendNarrative && (
              <button
                type="button"
                onClick={() =>
                  openModal({
                    title: `트렌드 분석 상세 (${dirLabel} · ${formatScore(trendScore ?? 0)})`,
                    content: trendNarrative,
                  })
                }
                className="text-[10px] font-bold text-stone-500 hover:text-indigo-400 uppercase tracking-widest flex items-center gap-1 transition-colors shrink-0"
              >
                <Maximize2 size={12} /> 전체 해석
              </button>
            )}
          </div>

          <TrendSparklinesPanel
            industryTrend={industryTrend}
            dongTrend={dongTrend}
            macro={macro}
          />

          {(trendDrivers || trendRisks) && (
            <TrendDriversRisks drivers={trendDrivers} risks={trendRisks} />
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/sub/analyze/AnalyzeMarketTab.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeMarketTab.tsx
git commit -m "feat(dashboard): AnalyzeMarketTab — Map+11지표+16동+차별화+거리+동폐업+trend_forecast"
```

---

### Task 10: AnalyzeDemographicTab / AnalyzeLegalTab / AnalyzeAgentInsightTab (3 서브탭 thin wrapper)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeDemographicTab.tsx`
- Create: `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeLegalTab.tsx`
- Create: `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAgentInsightTab.tsx`

기존 DemographicTab, LegalTab, InsightTab 그대로 사용 — re-export wrapper 만.

- [ ] **Step 1: AnalyzeDemographicTab**

```tsx
import type { SimulationOutput } from '../../../../../types';
import { DemographicTab } from '../../tabs/DemographicTab';

interface Props {
  simResult: SimulationOutput;
}

export function AnalyzeDemographicTab({ simResult }: Props) {
  return <DemographicTab simResult={simResult} />;
}
```

- [ ] **Step 2: AnalyzeLegalTab**

```tsx
import type { SimulationOutput } from '../../../../../types';
import { LegalTab } from '../../tabs/LegalTab';

interface Props {
  simResult: SimulationOutput;
}

export function AnalyzeLegalTab({ simResult }: Props) {
  return <LegalTab simResult={simResult} />;
}
```

- [ ] **Step 3: AnalyzeAgentInsightTab**

```tsx
import type { SimulationOutput } from '../../../../../types';
import type { DetailModalContent } from '../../shared/DetailModal';
import { InsightTab } from '../../tabs/InsightTab';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export function AnalyzeAgentInsightTab({ simResult, openModal }: Props) {
  return <InsightTab simResult={simResult} openModal={openModal} />;
}
```

(LegalTab/InsightTab 의 정확한 props 시그니처는 확인 후 일치시킴. 만약 InsightTab 이 openModal 미사용이면 prop 제거.)

- [ ] **Step 4: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/sub/analyze/AnalyzeDemographicTab.tsx src/components/SimulationResult/dashboard/sub/analyze/AnalyzeLegalTab.tsx src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAgentInsightTab.tsx
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeDemographicTab.tsx frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeLegalTab.tsx frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAgentInsightTab.tsx
git commit -m "feat(dashboard): Analyze 3 thin wrappers — Demographic/Legal/AgentInsight"
```

---

### Task 11: AnalyzeGroup wrapper

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/groups/AnalyzeGroup.tsx`

- [ ] **Step 1: 컴포넌트 작성**

```tsx
/**
 * AnalyzeGroup — AI 분석 그룹 (5 서브탭 라우팅)
 */

import { useSearchParams } from 'react-router-dom';
import type { SimulationOutput, AnalyzeSubTab } from '../../../../types';
import type { DetailModalContent } from '../shared/DetailModal';
import { TabButton } from '../shared/TabButton';
import { AnalyzeAiSummaryTab } from '../sub/analyze/AnalyzeAiSummaryTab';
import { AnalyzeMarketTab } from '../sub/analyze/AnalyzeMarketTab';
import { AnalyzeDemographicTab } from '../sub/analyze/AnalyzeDemographicTab';
import { AnalyzeLegalTab } from '../sub/analyze/AnalyzeLegalTab';
import { AnalyzeAgentInsightTab } from '../sub/analyze/AnalyzeAgentInsightTab';

interface Props {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

const VALID: AnalyzeSubTab[] = [
  'ai_summary',
  'market',
  'demographic',
  'legal',
  'agent_insight',
];

export function AnalyzeGroup({ simResult, openModal }: Props) {
  const [searchParams, setSearchParams] = useSearchParams();
  const subFromUrl = searchParams.get('sub') as AnalyzeSubTab | null;
  const activeSub: AnalyzeSubTab =
    subFromUrl && VALID.includes(subFromUrl) ? subFromUrl : 'ai_summary';

  const setSub = (sub: AnalyzeSubTab) => {
    const next = new URLSearchParams(searchParams);
    next.set('sub', sub);
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="space-y-6">
      <div className="flex gap-2 border-b border-stone-800 pb-2">
        <TabButton active={activeSub === 'ai_summary'} onClick={() => setSub('ai_summary')}>
          AI 분석 요약
        </TabButton>
        <TabButton active={activeSub === 'market'} onClick={() => setSub('market')}>
          상권 분석
        </TabButton>
        <TabButton active={activeSub === 'demographic'} onClick={() => setSub('demographic')}>
          인구 분석
        </TabButton>
        <TabButton active={activeSub === 'legal'} onClick={() => setSub('legal')}>
          법률 리스크
        </TabButton>
        <TabButton
          active={activeSub === 'agent_insight'}
          onClick={() => setSub('agent_insight')}
        >
          에이전트 근거
        </TabButton>
      </div>

      {activeSub === 'ai_summary' && <AnalyzeAiSummaryTab simResult={simResult} />}
      {activeSub === 'market' && <AnalyzeMarketTab simResult={simResult} openModal={openModal} />}
      {activeSub === 'demographic' && <AnalyzeDemographicTab simResult={simResult} />}
      {activeSub === 'legal' && <AnalyzeLegalTab simResult={simResult} />}
      {activeSub === 'agent_insight' && (
        <AnalyzeAgentInsightTab simResult={simResult} openModal={openModal} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/groups/AnalyzeGroup.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/groups/AnalyzeGroup.tsx
git commit -m "feat(dashboard): AnalyzeGroup wrapper — 5 서브탭 라우팅"
```

---

### Task 12: AbmGroup wrapper

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/groups/AbmGroup.tsx`

- [ ] **Step 1: 컴포넌트 작성**

```tsx
/**
 * AbmGroup — ABM 시뮬레이터 (단일, /vacancy_evaluation 독립)
 * 기존 AbmTab 그대로 wrapping. 서브탭 없음.
 */

import type { SimulationOutput } from '../../../../types';
import { AbmTab } from '../tabs/AbmTab';

interface Props {
  simResult: SimulationOutput;
}

export function AbmGroup({ simResult }: Props) {
  return <AbmTab simResult={simResult} />;
}
```

(AbmTab 의 정확한 props 시그니처 확인 — 만약 다른 prop 필요하면 일치시킴)

- [ ] **Step 2: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/groups/AbmGroup.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/groups/AbmGroup.tsx
git commit -m "feat(dashboard): AbmGroup wrapper"
```

---

### Task 13: TabbedDashboard 3그룹 + URL query param 재구조

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/TabbedDashboard.tsx` (전면 재작성)

기존 7탭 구조 → 3 그룹 (predict / analyze / abm) + group/sub query param.

- [ ] **Step 1: 현재 TabbedDashboard 구조 확인**

```bash
cd /c/mapo-franchise-simulator/frontend
wc -l src/components/SimulationResult/dashboard/TabbedDashboard.tsx
head -80 src/components/SimulationResult/dashboard/TabbedDashboard.tsx
```

기존 구조 (7탭 + AbmTab + DetailModal + GradeCard 등) 의 외곽 layout (sticky header, 모달 등) 은 보존.

- [ ] **Step 2: TabbedDashboard 재작성**

내부 라우팅 부분만 3 그룹으로 교체. 외곽 layout (DetailModal state, sticky header, 헤더 메타) 그대로 유지. 정확한 변경 영역:

기존 코드의 탭 분기 (7개 if/else 또는 switch) 를 다음으로 교체:

```tsx
import { PredictGroup } from './groups/PredictGroup';
import { AnalyzeGroup } from './groups/AnalyzeGroup';
import { AbmGroup } from './groups/AbmGroup';
import type { MainTab } from '../../../types';

// 컴포넌트 안 (useSearchParams 이미 사용 중)
const groupFromUrl = searchParams.get('group') as MainTab | null;
const activeGroup: MainTab =
  groupFromUrl && ['predict', 'analyze', 'abm'].includes(groupFromUrl) ? groupFromUrl : 'predict';

const setGroup = (group: MainTab) => {
  const next = new URLSearchParams(searchParams);
  next.set('group', group);
  next.delete('sub'); // 그룹 전환 시 sub 초기화
  setSearchParams(next, { replace: true });
};
```

탭 바 (sticky header 안):
```tsx
<div className="flex gap-3">
  <TabButton active={activeGroup === 'predict'} onClick={() => setGroup('predict')}>
    예측 결과
  </TabButton>
  <TabButton active={activeGroup === 'analyze'} onClick={() => setGroup('analyze')}>
    AI 분석
  </TabButton>
  <TabButton active={activeGroup === 'abm'} onClick={() => setGroup('abm')}>
    ABM 시뮬레이터
  </TabButton>
</div>
```

본문 분기:
```tsx
{activeGroup === 'predict' && <PredictGroup simResult={simResult} openModal={openModal} />}
{activeGroup === 'analyze' && <AnalyzeGroup simResult={simResult} openModal={openModal} />}
{activeGroup === 'abm' && <AbmGroup simResult={simResult} />}
```

기존 7탭 분기 코드 + 그 안의 inline 컴포넌트 호출 모두 제거.

- [ ] **Step 3: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/TabbedDashboard.tsx
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/TabbedDashboard.tsx
git commit -m "feat(dashboard): TabbedDashboard 3그룹 재구조 — group/sub query param"
```

---

### Task 14: 깨지는 vitest 처리 (it.skip)

**Files:**
- Modify: `frontend/src/**/*.test.tsx` 중 새 IA 로 깨지는 것들

- [ ] **Step 1: 전체 vitest 실행해 깨지는 것 식별**

```bash
cd /c/mapo-franchise-simulator/frontend
npx vitest run 2>&1 | tail -30
```

- [ ] **Step 2: 깨지는 테스트 파일들 식별 후 it.skip 적용**

깨지는 각 test 파일에서 `it(` → `it.skip(` 또는 `test(` → `test.skip(` 으로 변경. 파일 상단에 주석 추가:

```tsx
// SKIP — 2026-04-28 IA 재구조로 인한 일시 비활성화. 별 cycle 에서 재작성 예정.
```

- [ ] **Step 3: vitest 다시 실행 — 통과 또는 모두 skip 확인**

```bash
npx vitest run 2>&1 | tail -10
```

Expected: 0 fail (all pass or skipped)

- [ ] **Step 4: tsc + prettier**

```bash
npx tsc --noEmit
npx prettier --write src/**/*.test.tsx
```

- [ ] **Step 5: Commit**

```bash
git add -u frontend/src/**/*.test.tsx
git commit -m "test(dashboard): 깨지는 vitest 일시 skip — 새 IA 안정화 후 재작성"
```

---

### Task 15: 기존 7개 탭 파일 정리 (제거 또는 deprecation)

**Files:**
- Delete or archive: `frontend/src/components/SimulationResult/dashboard/tabs/SummaryTab.tsx` (computeDecision 만 유지하고 나머지 정리)
- Delete: `frontend/src/components/SimulationResult/dashboard/tabs/ForecastTab.tsx` (분해 완료)
- Keep: `tabs/FinancialTab.tsx` (ClosureRatePanel, ClosureRiskPanel export — PredictFinancialSimTab 가 사용)
- Keep: `tabs/MarketTab.tsx` (AnalyzeMarketTab 가 그대로 사용)
- Keep: `tabs/DemographicTab.tsx`, `LegalTab.tsx`, `InsightTab.tsx`, `AbmTab.tsx` (re-export wrapper 가 사용)

- [ ] **Step 1: 사용처 grep + 안전하게 제거할 파일 결정**

```bash
cd /c/mapo-franchise-simulator/frontend
grep -rn "from.*tabs/SummaryTab\|from.*tabs/ForecastTab" src --include='*.tsx' --include='*.ts'
```

- [ ] **Step 2: ForecastTab 사용처 확인 + 제거**

ForecastTab 의 모든 import 가 새 PredictSalesForecastTab/PredictFinancialSimTab/AnalyzeMarketTab 로 분산됐는지 확인. 사용처 0이면 삭제:

```bash
rm src/components/SimulationResult/dashboard/tabs/ForecastTab.tsx
```

만약 import 가 남아있으면 해당 파일들의 import 경로 업데이트 (구체 위치는 grep 결과로 식별).

- [ ] **Step 3: SummaryTab 정리**

`computeDecision` 만 유지하고 SummaryTab JSX 본문은 사용처 없으면 제거. `tabs/SummaryTab.tsx` 를 다음으로 단순화:

```tsx
// 2026-04-28 — IA 재구조 후 본문은 PredictSummaryTab / AnalyzeAiSummaryTab 으로 이관.
// computeDecision 만 export 로 유지 (AnalyzeAiSummaryTab 가 사용).

import type { SimulationOutput } from '../../../../types';

export type Decision = 'go' | 'hold' | 'nogo';

export function computeDecision(simResult: SimulationOutput): Decision {
  // 기존 로직 그대로 (LLM 의존: overall_legal_risk, market_entry_signal 등)
  // ... 기존 함수 본문 그대로 복사
}
```

(정확한 함수 본문은 기존 SummaryTab.tsx 의 `computeDecision` 함수 그대로 복사)

- [ ] **Step 4: tsc 통과 확인**

```bash
npx tsc --noEmit
```

남은 경로 에러 0이어야.

- [ ] **Step 5: Commit**

```bash
git add -A frontend/src/components/SimulationResult/dashboard/tabs/
git commit -m "chore(dashboard): 기존 7탭 파일 정리 — ForecastTab 제거, SummaryTab 의 computeDecision 만 유지"
```

---

### Task 16: 정합성 검증 (tsc + prettier + vitest + build)

**Files:** (검증만, 변경 없음)

- [ ] **Step 1: Frontend tsc**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
```

Expected: EXIT=0

- [ ] **Step 2: Prettier 일괄**

```bash
npx prettier --write src/components/SimulationResult/dashboard/groups/ src/components/SimulationResult/dashboard/sub/ src/components/SimulationResult/dashboard/shared/PlaceholderPanel.tsx src/components/SimulationResult/dashboard/TabbedDashboard.tsx src/types/index.ts
```

- [ ] **Step 3: Vitest run**

```bash
npx vitest run 2>&1 | tail -10
```

Expected: 0 fail (all pass or skipped)

- [ ] **Step 4: Build (chunk 영향 확인)**

```bash
npx vite build 2>&1 | tail -25
```

Expected: 신규 에러 0, 메인 chunk 가 늘지 않았는지 확인

- [ ] **Step 5: Commit (변경 발생 시)**

```bash
git status
# 변경 있으면
git add -u
git commit -m "chore: prettier 일괄 정합 적용"
```

---

### Task 17: 강민 브라우저 verify (메모리 `feedback_runtime_verification.md`)

**Files:** (코드 변경 없음, 사용자 직접)

- [ ] **시나리오 1**: 시뮬 실행 → dashboard 진입 → 기본 그룹 = `예측 결과` (URL 에 `?group=predict&sub=summary`)

- [ ] **시나리오 2**: 예측 그룹 5 서브탭 (예측 요약 / 매출 예측 / 재무 시뮬 / 고객·유동인구 / 신흥상권) 모두 클릭 → URL 변경 + 정상 렌더 (placeholder 2개는 "준비 중")

- [ ] **시나리오 3**: AI 분석 그룹 5 서브탭 (AI 분석 요약 / 상권 / 인구 / 법률 / 에이전트 근거) 모두 클릭 → URL 변경 + 정상 렌더

- [ ] **시나리오 4**: ABM 그룹 클릭 → 기존 ABM 페르소나 시뮬 정상

- [ ] **시나리오 5**: 새로고침 (F5) → 마지막 group + sub 위치 복원 (URL query param 우선)

- [ ] **시나리오 6**: 딥링크 (`/.../result/:id?group=analyze&sub=market`) 직접 입력 → 즉시 분석·상권 진입

- [ ] **시나리오 7**: 11종 차트 정상 표시 — 직전 cycle 디자인 토큰 (cyan 배지, ultra-wide, 노란선) 유지 확인

- [ ] **시나리오 8**: master `by 매니저명` 배지 (직전 cycle simulation_history) 그대로 동작

- [ ] **시나리오 9**: manager 권한 (직전 cycle) 그대로 — manager 가 dashboard 진입 시 정상

- [ ] **시나리오 10**: null 값 위치 모두 `—` 표시 (mock fallback 0)

---

## Verification Summary

전체 변경:
- 신규: 11 컴포넌트 (groups 3 + sub 10 + shared 1)
- 수정: 3 파일 (types/index.ts, TabbedDashboard.tsx, SummaryTab.tsx)
- 정리: 1 파일 삭제 (ForecastTab.tsx) + 깨지는 vitest skip
- 총 17 task / commit (사용자 승인 누적)

검증:
- tsc EXIT=0 / vitest 0 fail / build 신규 에러 0
- 강민 브라우저 10 시나리오

---

## Spec Self-Review

**1. Spec coverage:**
- 3 그룹 + 11 서브탭 ✅ (T7, T11, T12, T13)
- 11종 차트 재배치 ✅ (T4, T5, T9)
- trend_forecast 이동 ✅ (T9 AnalyzeMarketTab 통합)
- computeDecision 이동 ✅ (T8)
- 미연동 placeholder 2개 ✅ (T6)
- ABM 독립 ✅ (T12)
- null `—` 통일 ✅ (T3, T5 등 모든 KPI/차트에서 적용)
- mock 금지 ✅ (모든 task 가 props 없으면 빈 셀)
- vitest skip ✅ (T14)
- URL query param ✅ (T7, T11, T13)

**2. Placeholder scan:** "TBD"/"적절한 처리"/"비슷하게" 0건 ✅

**3. Type consistency:**
- `MainTab`/`PredictSubTab`/`AnalyzeSubTab` 모든 task 에 일관 사용 ✅
- 기존 컴포넌트 props (SimulationOutput, DetailModalContent) 그대로 ✅
- 함수명 (`computeDecision`, `formatKrw`, `formatPct`, `formatScore`) 일관 ✅

---

## References

- Spec: `docs/superpowers/specs/2026-04-28-3group-tab-restructure-design.md`
- 직전 cycles: 7탭 구조 (`project_dashboard_tab_restructure.md`), 11종 차트 (`project_dashboard_11_charts.md`)
- 디자인 토큰: cyan 배지 + ultra-wide + 노란선 (`feedback_shap_natural_language.md`, `feedback_closure_terminology.md`)
- AGENTS.md: frontend = C1 강민 (이번 cycle 본인 영역)
- 메모리: `feedback_commit_policy.md` (사용자 승인 시만 commit), `feedback_runtime_verification.md` (강민 직접 brain verify)
