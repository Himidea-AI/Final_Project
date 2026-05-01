# Dashboard Hub 재디자인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 시뮬 완료 시 진입하던 TabbedDashboard 를 폐기하고, 회사명 + 3 큰 카드 hub 화면 + 라우트 분리 디테일 페이지 구조로 재디자인 (frontend 한정).

**Architecture:** 새 `DashboardHub` (작은 헤더 + 3 `HubCard`) + 라우트 페이지 3개 (`DashboardPredictPage` / `DashboardAnalyzePage` / `DashboardAbmPage` — 각각 ← Hub back + 직전 cycle 의 그룹 wrapper 호출). `/dashboard`, `/dashboard/predict|analyze|abm` 라우트 신설. SimulatorDashboard 결과 영역의 `<TabbedDashboard>` 호출을 navigate('/dashboard') 로 교체. 11종 차트 + sub/groups + 디자인 토큰 그대로 보존.

**Tech Stack:** React 18 + TypeScript + Vite + react-router-dom + Tailwind (cyan/stone/indigo/amber 토큰 + animate-spin-slow 기존 정의 재사용)

**Spec:** `docs/superpowers/specs/2026-04-28-dashboard-hub-redesign-design.md`
**Branch:** `feature/dashboard-hub-redesign` (현재 브랜치)
**Commit Policy:** 메모리 `feedback_commit_policy.md` — 사용자 명시 승인 시만 commit. plan 의 commit step 은 메시지 초안만.

---

## File Structure

### 신규 (5)
```
frontend/src/components/SimulationResult/dashboard/
├── HubCard.tsx              # 공통 카드 (hero img + 제목 + 설명 + arrow + 레이저)
├── DashboardHub.tsx         # 작은 헤더 + 3 HubCard 렌더 (라우트 /dashboard)
frontend/src/pages/dashboard/
├── DashboardPredictPage.tsx  # ← Hub back + <PredictGroup>
├── DashboardAnalyzePage.tsx  # ← Hub back + <AnalyzeGroup>
└── DashboardAbmPage.tsx      # ← Hub back + <AbmGroup>
```

### 수정 (3)
- `frontend/src/App.tsx` — 라우트 정의 (`/dashboard`, `/dashboard/predict|analyze|abm`) + SimulatorDashboard 결과 영역에서 `<TabbedDashboard>` 제거 + `navigate('/dashboard')` 호출
- `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSummaryTab.tsx` — KPI 5개로 확장 (월매출/유동인구/경쟁강도/BEP/폐업위험도)
- `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx` — 1등 동 + Top 3 칩 추가

### 삭제 (1-3, 검토 후)
- `frontend/src/components/SimulationResult/dashboard/TabbedDashboard.tsx` — 사용처 (App.tsx + SimulationHistoryDetail.tsx) 모두 교체 후 삭제
- `frontend/src/components/SimulationResult/dashboard/shared/KpiMiniGrid.tsx` — sub-tab 안 재사용 안 하면 삭제
- `frontend/src/components/SimulationResult/dashboard/shared/GradeCard.tsx` — 미사용이면 삭제

---

## Tasks

### Task 1: HubCard 공통 컴포넌트

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/HubCard.tsx`

- [ ] **Step 1: 컴포넌트 작성**

```tsx
/**
 * HubCard — Dashboard Hub 의 3 카드 공통 컴포넌트.
 * - Hero 이미지 (Unsplash CDN, lazy load) + 제목 + 짧은 설명 + arrow CTA
 * - hover: 이미지 scale 1.10 (700ms ease-in-out), 카드 -translate-y-2
 * - 외곽 레이저 효과 (PricingCard.tsx:28-31 패턴 — conic-gradient + animate-spin-slow)
 * - 색 시멘틱: indigo (예측) / cyan (분석) / amber (ABM)
 * - touch ≥44pt (카드 전체 클릭), focus ring, reduced-motion respect
 */

import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

type Accent = 'indigo' | 'cyan' | 'amber';

interface Props {
  to: string;
  title: string;
  description: string;
  imgSrc: string;
  imgAlt: string;
  accent: Accent;
}

const ACCENT_CLASS: Record<Accent, { laser: string; arrow: string; ring: string }> = {
  indigo: {
    laser: 'conic-gradient(from 0deg, transparent 0%, transparent 40%, #818cf8 50%, #a5b4fc 60%, transparent 100%)',
    arrow: 'text-indigo-400',
    ring: 'focus-visible:ring-indigo-400',
  },
  cyan: {
    laser: 'conic-gradient(from 0deg, transparent 0%, transparent 40%, #22d3ee 50%, #67e8f9 60%, transparent 100%)',
    arrow: 'text-cyan-400',
    ring: 'focus-visible:ring-cyan-400',
  },
  amber: {
    laser: 'conic-gradient(from 0deg, transparent 0%, transparent 40%, #f59e0b 50%, #fbbf24 60%, transparent 100%)',
    arrow: 'text-amber-400',
    ring: 'focus-visible:ring-amber-400',
  },
};

export function HubCard({ to, title, description, imgSrc, imgAlt, accent }: Props) {
  const a = ACCENT_CLASS[accent];

  return (
    <Link
      to={to}
      aria-label={`${title} 화면 진입`}
      className={`group relative flex flex-col overflow-hidden rounded-3xl border border-stone-800/60 bg-stone-900/60 shadow-sm transition-all duration-300 ease-out hover:-translate-y-2 hover:shadow-2xl hover:shadow-indigo-500/10 motion-reduce:transition-none motion-reduce:hover:translate-y-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[#1e1b18] ${a.ring}`}
    >
      {/* 외곽 레이저 (PricingCard 패턴) */}
      <div
        className="absolute inset-[-50%] z-0 animate-spin-slow opacity-0 group-hover:opacity-100 transition-opacity duration-500 motion-reduce:hidden"
        style={{ background: a.laser }}
        aria-hidden="true"
      />

      {/* 카드 안 콘텐츠 (레이저 위에 z-10) */}
      <div className="relative z-10 flex h-full flex-col rounded-3xl bg-stone-900/95">
        {/* Hero 이미지 — aspect-video, group-hover scale */}
        <div className="aspect-video overflow-hidden rounded-t-3xl">
          <img
            src={imgSrc}
            alt={imgAlt}
            loading="lazy"
            width={640}
            height={360}
            className="h-full w-full object-cover transition-transform duration-700 ease-in-out group-hover:scale-110 motion-reduce:transition-none motion-reduce:group-hover:scale-100"
          />
        </div>

        {/* 텍스트 영역 */}
        <div className="flex flex-1 flex-col p-8">
          <h3 className="text-2xl font-black text-stone-100 tracking-tight">{title}</h3>
          <p className="mt-3 flex-1 text-sm text-stone-400 leading-relaxed">{description}</p>

          <div className={`mt-6 inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest ${a.arrow}`}>
            진입
            <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-1 motion-reduce:transition-none" />
          </div>
        </div>
      </div>
    </Link>
  );
}
```

- [ ] **Step 2: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/HubCard.tsx
```

Expected: EXIT=0

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/HubCard.tsx
git commit -m "feat(dashboard): HubCard 공통 카드 — hero img + 레이저 + arrow CTA"
```

---

### Task 2: DashboardHub 화면

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/DashboardHub.tsx`

- [ ] **Step 1: 컴포넌트 작성**

```tsx
/**
 * DashboardHub — 시뮬 완료 진입점 (라우트 /dashboard).
 * 작은 헤더 (회사명 + 시뮬 일시 + 문서ID) + 3 HubCard 가로 배치.
 * mobile stack, lg 이상 가로 3등분.
 */

import type { SimulationOutput } from '../../../types';
import { formatDocumentId } from '../../../types/simulationHistory';
import { HubCard } from './HubCard';

interface Props {
  simResult: SimulationOutput;
  brandName: string;
  savedHistoryId?: number | null;
}

// Unsplash 스톡 이미지 — 추후 마포구 자체 사진 교체 가능
const HUB_IMAGES = {
  predict: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800&auto=format&fit=crop&q=80',
  analyze: 'https://images.unsplash.com/photo-1486325212027-8081e485255e?w=800&auto=format&fit=crop&q=80',
  abm: 'https://images.unsplash.com/photo-1519567241046-7f570eee3ce6?w=800&auto=format&fit=crop&q=80',
};

export function DashboardHub({ simResult, brandName, savedHistoryId }: Props) {
  const docId = formatDocumentId(savedHistoryId ?? null);
  const createdAt = new Date().toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });

  return (
    <div className="mx-auto max-w-[1728px] px-8 py-12">
      {/* 작은 헤더 */}
      <header className="mb-12 flex items-end justify-between border-b border-stone-800/60 pb-6">
        <h1 className="text-2xl font-black text-stone-100 tracking-tight">{brandName || '—'}</h1>
        <div className="text-right">
          <div className="text-[10px] font-mono uppercase tracking-widest text-stone-500">
            {docId}
          </div>
          <div className="mt-1 text-[10px] font-mono text-stone-600">{createdAt}</div>
        </div>
      </header>

      {/* 3 HubCard — mobile stack, lg 가로 3등분 */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <HubCard
          to="/dashboard/predict"
          title="예측 결과"
          description="ML 기반 매출 · 재무 · 폐업 위험도 정량 예측"
          imgSrc={HUB_IMAGES.predict}
          imgAlt="데이터 차트 시각화"
          accent="indigo"
        />
        <HubCard
          to="/dashboard/analyze"
          title="AI 분석"
          description="LLM 기반 상권 · 인구 · 법률 · 경쟁 정성 분석"
          imgSrc={HUB_IMAGES.analyze}
          imgAlt="도시 거리 풍경"
          accent="cyan"
        />
        <HubCard
          to="/dashboard/abm"
          title="ABM 시뮬레이터"
          description="100명 에이전트 행동 시뮬레이션 + 공실 평가"
          imgSrc={HUB_IMAGES.abm}
          imgAlt="사람들이 다니는 거리"
          accent="amber"
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/DashboardHub.tsx
```

Expected: EXIT=0

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/DashboardHub.tsx
git commit -m "feat(dashboard): DashboardHub — 작은 헤더 + 3 HubCard"
```

---

### Task 3: 라우트 페이지 wrapper 3개 (← Hub back + 그룹 호출)

**Files:**
- Create: `frontend/src/pages/dashboard/DashboardPredictPage.tsx`
- Create: `frontend/src/pages/dashboard/DashboardAnalyzePage.tsx`
- Create: `frontend/src/pages/dashboard/DashboardAbmPage.tsx`

- [ ] **Step 1: 공통 BackToHub 인라인 + 3 파일**

각 파일 동일 패턴. 본문은 직전 cycle 의 PredictGroup / AnalyzeGroup / AbmGroup 호출.

`DashboardPredictPage.tsx`:

```tsx
/**
 * DashboardPredictPage — /dashboard/predict 라우트.
 * ← Hub back 버튼 + PredictGroup (5 서브탭).
 */

import { ArrowLeft } from 'lucide-react';
import { Link, useOutletContext } from 'react-router-dom';
import type { SimulationOutput } from '../../types';
import type { DetailModalContent } from '../../components/SimulationResult/dashboard/shared/DetailModal';
import { PredictGroup } from '../../components/SimulationResult/dashboard/groups/PredictGroup';

interface OutletCtx {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export default function DashboardPredictPage() {
  const { simResult, openModal } = useOutletContext<OutletCtx>();

  return (
    <div className="mx-auto max-w-[1728px] px-8 py-8">
      <div className="mb-6">
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-stone-500 transition-colors hover:text-stone-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-400 rounded-md px-1 py-0.5"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Hub
        </Link>
      </div>
      <PredictGroup simResult={simResult} openModal={openModal} />
    </div>
  );
}
```

`DashboardAnalyzePage.tsx`:

```tsx
import { ArrowLeft } from 'lucide-react';
import { Link, useOutletContext } from 'react-router-dom';
import type { SimulationOutput } from '../../types';
import type { DetailModalContent } from '../../components/SimulationResult/dashboard/shared/DetailModal';
import { AnalyzeGroup } from '../../components/SimulationResult/dashboard/groups/AnalyzeGroup';

interface OutletCtx {
  simResult: SimulationOutput;
  openModal: (content: DetailModalContent) => void;
}

export default function DashboardAnalyzePage() {
  const { simResult, openModal } = useOutletContext<OutletCtx>();
  return (
    <div className="mx-auto max-w-[1728px] px-8 py-8">
      <div className="mb-6">
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-stone-500 transition-colors hover:text-stone-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-400 rounded-md px-1 py-0.5"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Hub
        </Link>
      </div>
      <AnalyzeGroup simResult={simResult} openModal={openModal} />
    </div>
  );
}
```

`DashboardAbmPage.tsx`:

```tsx
import { ArrowLeft } from 'lucide-react';
import { Link, useOutletContext } from 'react-router-dom';
import type { SimulationOutput } from '../../types';
import { AbmGroup } from '../../components/SimulationResult/dashboard/groups/AbmGroup';

interface OutletCtx {
  simResult: SimulationOutput;
  brandName: string;
  businessType?: string | null;
}

export default function DashboardAbmPage() {
  const { simResult, brandName, businessType } = useOutletContext<OutletCtx>();
  return (
    <div className="mx-auto max-w-[1728px] px-8 py-8">
      <div className="mb-6">
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-stone-500 transition-colors hover:text-stone-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-400 rounded-md px-1 py-0.5"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Hub
        </Link>
      </div>
      <AbmGroup simResult={simResult} brandName={brandName} businessType={businessType} />
    </div>
  );
}
```

(`AbmGroup` 의 props 시그니처 정확 — T12 결과: simResult + brandName + businessType)

- [ ] **Step 2: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
mkdir -p src/pages/dashboard
# 위 3 파일 작성 후
npx tsc --noEmit
npx prettier --write src/pages/dashboard/DashboardPredictPage.tsx src/pages/dashboard/DashboardAnalyzePage.tsx src/pages/dashboard/DashboardAbmPage.tsx
```

EXIT=0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/dashboard/
git commit -m "feat(dashboard): 3 라우트 페이지 (Predict/Analyze/Abm) — ← Hub back + Group"
```

---

### Task 4: App.tsx 라우트 정의 + 시뮬 완료 navigate

**Files:**
- Modify: `frontend/src/App.tsx`

`App.tsx:2155` 부근 `<TabbedDashboard simResult={rawSimResult} ... />` 호출 영역 변경 + 4400+ 라인 부근 라우트 정의에 `/dashboard/*` nested route 추가.

- [ ] **Step 1: 새 라우트 추가**

`<Route path="/simulator">` 정의 부근 (`App.tsx:4415` 근처) 다음에 `/dashboard` nested route 추가:

```tsx
<Route
  path="/dashboard"
  element={
    <ProtectedRoute>
      <DashboardLayout
        simResult={rawSimResult}
        brandName={user?.company_name || ''}
        businessType={businessType}
        savedHistoryId={savedHistoryId}
      />
    </ProtectedRoute>
  }
>
  <Route index element={<DashboardHub /> /* hub — context 받아서 표시 */} />
  <Route path="predict" element={<DashboardPredictPage />} />
  <Route path="analyze" element={<DashboardAnalyzePage />} />
  <Route path="abm" element={<DashboardAbmPage />} />
</Route>
```

`DashboardLayout` 은 임시 inline 컴포넌트 또는 새 파일. context 를 자식에게 outlet 으로 전달.

**구현 단순화** — `<DashboardLayout>` 신규 파일 대신 inline:

```tsx
import { Outlet } from 'react-router-dom';

// App.tsx 안 inline
function DashboardLayout({ simResult, brandName, businessType, savedHistoryId, openModal }) {
  if (!simResult) return <Navigate to="/simulator" replace />;
  return <Outlet context={{ simResult, brandName, businessType, savedHistoryId, openModal }} />;
}
```

또는 더 단순히 — Outlet 안 쓰고 라우트별로 직접 props 전달. 그러나 react-router v6 nested route + outlet context 패턴이 더 깔끔.

**라우트 정확 형태** (App.tsx 기존 ProtectedRoute 패턴 따라):

```tsx
<Route
  path="/dashboard"
  element={
    <ProtectedRoute>
      <DashboardOutlet
        simResult={rawSimResult}
        brandName={user?.company_name || ''}
        businessType={businessType}
        savedHistoryId={savedHistoryId}
      />
    </ProtectedRoute>
  }
>
  <Route
    index
    element={
      <DashboardHub
        simResult={rawSimResult!}
        brandName={user?.company_name || ''}
        savedHistoryId={savedHistoryId}
      />
    }
  />
  <Route path="predict" element={<DashboardPredictPage />} />
  <Route path="analyze" element={<DashboardAnalyzePage />} />
  <Route path="abm" element={<DashboardAbmPage />} />
</Route>
```

**`DashboardOutlet` inline 정의** (App.tsx 안):

```tsx
function DashboardOutlet({
  simResult,
  brandName,
  businessType,
  savedHistoryId,
}: {
  simResult: SimulationOutput | null;
  brandName: string;
  businessType?: string | null;
  savedHistoryId?: number | null;
}) {
  const [modalContent, setModalContent] = useState<DetailModalContent | null>(null);
  const openModal = (content: DetailModalContent) => setModalContent(content);

  if (!simResult) return <Navigate to="/simulator" replace />;

  return (
    <>
      <Outlet context={{ simResult, brandName, businessType, savedHistoryId, openModal }} />
      <DetailModal content={modalContent} onClose={() => setModalContent(null)} />
    </>
  );
}
```

(DetailModal import 필요 — App.tsx 에 이미 있을 가능성)

- [ ] **Step 2: SimulatorDashboard 안의 `<TabbedDashboard>` 제거 + navigate 호출**

`App.tsx:2155` 부근:

```tsx
// before
{!isSplitMode && rawSimResult && (
  <TabbedDashboard
    simResult={rawSimResult}
    savedHistoryId={savedHistoryId}
    brandName={user?.company_name || ''}
    businessType={businessType}
  />
)}

// after — 시뮬 완료 시 자동 navigate, 결과 영역은 link 만 남김
{!isSplitMode && rawSimResult && (
  <NavigateToDashboard />
)}
```

`NavigateToDashboard` inline:
```tsx
import { Navigate } from 'react-router-dom';

function NavigateToDashboard() {
  return <Navigate to="/dashboard" replace />;
}
```

**대안** — useEffect 에서 navigate 호출 (rawSimResult 도착 시):

```tsx
useEffect(() => {
  if (!isSplitMode && rawSimResult) {
    navigate('/dashboard', { replace: true });
  }
}, [rawSimResult, isSplitMode, navigate]);
```

이 방법이 더 명확하고 SimulatorDashboard 에서 결과 영역 자체를 비울 수 있음.

- [ ] **Step 3: imports 추가**

App.tsx 상단 import 영역:

```tsx
import { Outlet } from 'react-router-dom';
import { DashboardHub } from './components/SimulationResult/dashboard/DashboardHub';
import DashboardPredictPage from './pages/dashboard/DashboardPredictPage';
import DashboardAnalyzePage from './pages/dashboard/DashboardAnalyzePage';
import DashboardAbmPage from './pages/dashboard/DashboardAbmPage';
```

**TabbedDashboard import 는 일단 유지** (Task 7 에서 제거 — SimulationHistoryDetail.tsx 도 같이 처리).

- [ ] **Step 4: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/App.tsx
```

EXIT=0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat(route): /dashboard nested route + 시뮬 완료 시 자동 navigate"
```

---

### Task 5: PredictSummaryTab KPI 5개 확장

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSummaryTab.tsx`

기존 3 KPI (월매출/BEP/폐업위험도) + 추가 2개 (유동인구 점수 / 경쟁강도).

- [ ] **Step 1: KPI 추가**

기존 `PredictSummaryTab` 에 2개 KPI 추가. 5 KPI 가로 배치 (`grid-cols-5`) 또는 2x3 (`grid-cols-2 lg:grid-cols-5`).

기존 코드 (T3 cycle 작성):

```tsx
return (
  <div className="grid grid-cols-3 gap-6">
    <Kpi ... 월매출 ... />
    <Kpi ... BEP ... />
    <Kpi ... 폐업위험도 ... />
  </div>
);
```

변경:

```tsx
import { Activity, Gauge, AlertTriangle, Users, Swords } from 'lucide-react';
// ... (formatKrw 등 그대로)

export function PredictSummaryTab({ simResult }: Props) {
  const ps = simResult.final_report?.profit_simulation ?? null;
  const monthlyRev = ps?.monthly_revenue ?? null;
  const bepMonths = ps?.bep_months ?? null;
  const riskScore = simResult.closure_risk?.risk_score ?? null;
  const riskPct =
    riskScore == null
      ? null
      : riskScore <= 1
        ? Math.round(riskScore * 100)
        : Math.round(riskScore);

  // 추가: 유동인구 / 경쟁강도 (market_report 정규화 0-100)
  const flowScore = simResult.market_report?.floating_population ?? null;
  const competitionScore = simResult.market_report?.competition_intensity ?? null;

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5 lg:gap-6">
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
      <Kpi
        icon={<Users size={16} className="text-emerald-400" />}
        label="유동인구 점수"
        value={flowScore != null ? `${Math.round(flowScore)}` : '—'}
        color="emerald"
      />
      <Kpi
        icon={<Swords size={16} className="text-amber-400" />}
        label="경쟁강도"
        value={competitionScore != null ? `${Math.round(competitionScore)}` : '—'}
        color="amber"
      />
    </div>
  );
}
```

**Kpi 컴포넌트 color prop 확장**: 기존 `'indigo' | 'cyan' | 'rose'` → `+ 'emerald' | 'amber'`. 색상 매핑 추가:

```tsx
function Kpi({ icon, label, value, color }: KpiProps) {
  const valueClass =
    color === 'indigo'
      ? 'text-indigo-400'
      : color === 'cyan'
        ? 'text-cyan-400'
        : color === 'rose'
          ? 'text-rose-400'
          : color === 'emerald'
            ? 'text-emerald-400'
            : 'text-amber-400';
  // ... 기존 return
}

interface KpiProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: 'indigo' | 'cyan' | 'rose' | 'emerald' | 'amber';
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
git commit -m "feat(predict): PredictSummaryTab KPI 5개로 확장 (유동인구/경쟁강도 추가)"
```

---

### Task 6: AnalyzeAiSummaryTab 1등 동 + Top 3 추가

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx`

기존 (decision card + 신호등 + synthesis 자연어) + 추가:
- 1등 추천 동 (`simResult.winner_district`) 큰 글자 + 추천 이유 한 줄
- 후보 Top 3 (`simResult.top_3_candidates`) 칩 리스트

- [ ] **Step 1: 1등 동 + Top 3 카드 추가**

기존 컴포넌트 return 안 (decision/신호등 grid 위 또는 아래) 추가:

```tsx
{/* 1등 추천 동 + Top 3 */}
{simResult.winner_district && (
  <div className="rounded-3xl border border-cyan-500/20 bg-cyan-500/5 p-8">
    <div className="mb-3 flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-cyan-400">
      <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
      LLM 분석 1등 추천 입지
    </div>
    <div className="text-4xl font-black tracking-tighter text-stone-100">
      {simResult.winner_district}
    </div>
    {simResult.top_3_candidates && simResult.top_3_candidates.length > 0 && (
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="text-[10px] font-bold uppercase tracking-widest text-stone-500">
          Top 3 후보
        </span>
        {simResult.top_3_candidates.map((d) => (
          <span
            key={d}
            className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs font-bold text-cyan-300"
          >
            {d}
          </span>
        ))}
      </div>
    )}
  </div>
)}
```

위 카드를 `<div className="space-y-6">` 안 첫 위치에 배치 (decision card grid 위).

- [ ] **Step 2: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx
git commit -m "feat(analyze): AnalyzeAiSummaryTab — 1등 동 + Top 3 칩 추가"
```

---

### Task 7: TabbedDashboard 사용처 정리 + 삭제

**Files:**
- Modify: `frontend/src/pages/SimulationHistoryDetail.tsx` — `<TabbedDashboard>` 사용처 그대로 유지 또는 새 hub 흐름 적용
- Modify: `frontend/src/App.tsx` — TabbedDashboard import 제거
- Delete: `frontend/src/components/SimulationResult/dashboard/TabbedDashboard.tsx`

**중요**: `SimulationHistoryDetail.tsx` 가 TabbedDashboard 를 어떻게 사용하는지 먼저 확인 — 시뮬 이력 디테일 페이지에서 같은 dashboard 구조 표시. 새 hub 흐름과 통일 필요.

- [ ] **Step 1: SimulationHistoryDetail.tsx 읽기**

```bash
cd /c/mapo-franchise-simulator/frontend
grep -n "TabbedDashboard" src/pages/SimulationHistoryDetail.tsx
cat src/pages/SimulationHistoryDetail.tsx
```

`<TabbedDashboard simResult={...} brandName={...} ... />` 패턴 확인.

- [ ] **Step 2: SimulationHistoryDetail.tsx 의 TabbedDashboard 호출을 새 패턴으로 교체**

옵션 A (단순 — 이력 페이지도 hub 흐름):
```tsx
// before
<TabbedDashboard simResult={data.simulation_result} brandName={data.brand_name} ... />

// after — DashboardHub 직접 호출 (라우팅 없이)
<DashboardHub
  simResult={data.simulation_result}
  brandName={data.brand_name}
  savedHistoryId={data.id}
/>
```

이 경우 카드 클릭 → `/dashboard/predict` 등으로 navigate. 단 이력 페이지의 simResult 가 라우트 outlet context 에 들어가지 않음 → 디테일 페이지가 데이터 못 받음.

옵션 B (이력 페이지 자체에서 그룹 직접 호출 — 라우트 X):
```tsx
// 이력 페이지는 별 wrapper 컴포넌트 (HistoryDashboardView) 만들어서
// hub + 디테일 중 하나 선택하는 state 기반 분기
import { useState } from 'react';
// ...
const [view, setView] = useState<'hub' | 'predict' | 'analyze' | 'abm'>('hub');
// hub 화면은 DashboardHub 비슷하게 + 카드 onClick={() => setView('predict')}
```

→ 옵션 B 가 더 정확하지만 추가 wrapper 필요. **옵션 B 권장** — 라우트 분리 일관성 깨짐 방지.

새 wrapper `HistoryDashboardView.tsx` (frontend/src/pages/) 신규:

```tsx
import { useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import type { SimulationOutput } from '../types';
import type { DetailModalContent } from '../components/SimulationResult/dashboard/shared/DetailModal';
import { DetailModal } from '../components/SimulationResult/dashboard/shared/DetailModal';
import { DashboardHub } from '../components/SimulationResult/dashboard/DashboardHub';
import { PredictGroup } from '../components/SimulationResult/dashboard/groups/PredictGroup';
import { AnalyzeGroup } from '../components/SimulationResult/dashboard/groups/AnalyzeGroup';
import { AbmGroup } from '../components/SimulationResult/dashboard/groups/AbmGroup';

type View = 'hub' | 'predict' | 'analyze' | 'abm';

interface Props {
  simResult: SimulationOutput;
  brandName: string;
  businessType?: string | null;
  savedHistoryId?: number | null;
}

export function HistoryDashboardView({ simResult, brandName, businessType, savedHistoryId }: Props) {
  const [view, setView] = useState<View>('hub');
  const [modalContent, setModalContent] = useState<DetailModalContent | null>(null);
  const openModal = (content: DetailModalContent) => setModalContent(content);

  if (view === 'hub') {
    // hub 인라인 — DashboardHub 의 Link 가 라우트 변경하지 않게 onClick 으로 view setState
    // 단순 구현: HubCardButton 새로 만들지 말고 직접 인라인
    return (
      <>
        <div className="mx-auto max-w-[1728px] px-8 py-12">
          <header className="mb-12 flex items-end justify-between border-b border-stone-800/60 pb-6">
            <h1 className="text-2xl font-black text-stone-100 tracking-tight">{brandName || '—'}</h1>
            <div className="text-[10px] font-mono uppercase tracking-widest text-stone-500">
              저장된 시뮬 이력
            </div>
          </header>
          {/* 3 카드 — view setState 로 분기 (라우트 X) */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <button
              type="button"
              onClick={() => setView('predict')}
              className="rounded-3xl border border-stone-800/60 bg-stone-900/60 p-8 text-left transition-all hover:-translate-y-2 hover:shadow-2xl hover:shadow-indigo-500/10"
            >
              <h3 className="text-2xl font-black text-stone-100">예측 결과</h3>
              <p className="mt-3 text-sm text-stone-400">ML 기반 정량 예측</p>
            </button>
            <button
              type="button"
              onClick={() => setView('analyze')}
              className="rounded-3xl border border-stone-800/60 bg-stone-900/60 p-8 text-left transition-all hover:-translate-y-2 hover:shadow-2xl hover:shadow-cyan-500/10"
            >
              <h3 className="text-2xl font-black text-stone-100">AI 분석</h3>
              <p className="mt-3 text-sm text-stone-400">LLM 기반 정성 분석</p>
            </button>
            <button
              type="button"
              onClick={() => setView('abm')}
              className="rounded-3xl border border-stone-800/60 bg-stone-900/60 p-8 text-left transition-all hover:-translate-y-2 hover:shadow-2xl hover:shadow-amber-500/10"
            >
              <h3 className="text-2xl font-black text-stone-100">ABM 시뮬레이터</h3>
              <p className="mt-3 text-sm text-stone-400">에이전트 행동 시뮬</p>
            </button>
          </div>
        </div>
        <DetailModal content={modalContent} onClose={() => setModalContent(null)} />
      </>
    );
  }

  // 디테일 view
  return (
    <>
      <div className="mx-auto max-w-[1728px] px-8 py-8">
        <div className="mb-6">
          <button
            type="button"
            onClick={() => setView('hub')}
            className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-stone-500 transition-colors hover:text-stone-100"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Hub
          </button>
        </div>
        {view === 'predict' && <PredictGroup simResult={simResult} openModal={openModal} />}
        {view === 'analyze' && <AnalyzeGroup simResult={simResult} openModal={openModal} />}
        {view === 'abm' && (
          <AbmGroup simResult={simResult} brandName={brandName} businessType={businessType} />
        )}
      </div>
      <DetailModal content={modalContent} onClose={() => setModalContent(null)} />
    </>
  );
}
```

`SimulationHistoryDetail.tsx` 에서 `<TabbedDashboard ... />` 호출을 `<HistoryDashboardView ... />` 로 교체.

- [ ] **Step 3: TabbedDashboard.tsx 삭제**

App.tsx + SimulationHistoryDetail.tsx 사용처 0 확인 후:

```bash
cd /c/mapo-franchise-simulator/frontend
grep -rn "TabbedDashboard" src --include='*.tsx' --include='*.ts'
# 사용처 0 확인 후
rm src/components/SimulationResult/dashboard/TabbedDashboard.tsx
```

**기타 파일 grep hit (DetailModal/InsightTab/AbmTab/viewmodels)** — import 가 아니라 주석 또는 docstring 인지 확인. 만약 진짜 import 면 그것도 정리.

- [ ] **Step 4: tsc + prettier**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
npx prettier --write src/pages/SimulationHistoryDetail.tsx src/pages/HistoryDashboardView.tsx src/App.tsx
```

EXIT=0.

- [ ] **Step 5: Commit**

```bash
git add -A frontend/src/pages/HistoryDashboardView.tsx frontend/src/pages/SimulationHistoryDetail.tsx frontend/src/components/SimulationResult/dashboard/TabbedDashboard.tsx frontend/src/App.tsx
git commit -m "chore(dashboard): TabbedDashboard 삭제 — HistoryDashboardView 신규 + App.tsx 정리"
```

---

### Task 8: KpiMiniGrid / GradeCard 사용처 검토 + 처리

**Files:**
- 검토 대상: `frontend/src/components/SimulationResult/dashboard/shared/KpiMiniGrid.tsx`, `GradeCard.tsx`

- [ ] **Step 1: 사용처 grep**

```bash
cd /c/mapo-franchise-simulator/frontend
grep -rn "KpiMiniGrid\|GradeCard" src --include='*.tsx' --include='*.ts'
```

- [ ] **Step 2: 결정**

- 사용처 0 → 삭제
- 사용처 있음 + 새 흐름 호환 → 그대로 유지
- 사용처 있음 + 새 흐름 부적합 → 호출처 수정 또는 컴포넌트 폐기

PredictSummaryTab 의 KPI 5개 확장 (T5) 후 KpiMiniGrid 가 자체 KPI 표시 컴포넌트라 중복 가능성. 단순 redundancy 제거.

- [ ] **Step 3: 삭제 또는 수정 후 commit**

```bash
# 사용처 0 시
rm src/components/SimulationResult/dashboard/shared/KpiMiniGrid.tsx
rm src/components/SimulationResult/dashboard/shared/GradeCard.tsx
git add -A frontend/src/components/SimulationResult/dashboard/shared/
git commit -m "chore(dashboard): KpiMiniGrid/GradeCard 삭제 — 새 hub 흐름 후 사용처 0"
```

---

### Task 9: 정합성 검증

**Files:** (검증만)

- [ ] **Step 1: tsc**

```bash
cd /c/mapo-franchise-simulator/frontend
npx tsc --noEmit
```

EXIT=0.

- [ ] **Step 2: vitest**

```bash
npx vitest run 2>&1 | tail -10
```

64/64 passed (또는 새 IA 변경 영향 받는 test 있으면 it.skip).

- [ ] **Step 3: build**

```bash
npx vite build 2>&1 | tail -25
```

EXIT=0. 메인 chunk size 비교 (이전 cycle 579.17 kB).

- [ ] **Step 4: prettier 일괄**

```bash
npx prettier --write src/components/SimulationResult/dashboard/HubCard.tsx src/components/SimulationResult/dashboard/DashboardHub.tsx src/pages/dashboard/ src/pages/HistoryDashboardView.tsx src/App.tsx src/components/SimulationResult/dashboard/sub/predict/PredictSummaryTab.tsx src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx
```

- [ ] **Step 5: Commit (변경 시)**

```bash
git status
# 변경 있으면
git add -u
git commit -m "chore: prettier 일괄 정합 적용"
```

---

### Task 10: 강민 brain verify

**Files:** (코드 변경 없음, 사용자 직접)

- [ ] **시나리오 1**: 시뮬 실행 → 완료 → 자동 navigate `/dashboard` → DashboardHub 진입 (회사명 + 3 카드)
- [ ] **시나리오 2**: 카드 hover → 레이저 회전 + 이미지 scale + 카드 lift (300-700ms)
- [ ] **시나리오 3**: 예측 결과 카드 클릭 → `/dashboard/predict` → PredictGroup (5 서브탭) + 좌상단 ← Hub
- [ ] **시나리오 4**: AI 분석 카드 클릭 → `/dashboard/analyze` → AnalyzeGroup
- [ ] **시나리오 5**: ABM 카드 클릭 → `/dashboard/abm` → AbmGroup (vacancy_evaluation 정상)
- [ ] **시나리오 6**: ← Hub 클릭 → hub 복귀 / 브라우저 back 도 동일
- [ ] **시나리오 7**: 새로고침 (`/dashboard/analyze?sub=market`) → 위치 복원
- [ ] **시나리오 8**: PredictSummaryTab 5 KPI 정상 (월매출/유동인구/경쟁강도/BEP/폐업위험도)
- [ ] **시나리오 9**: AnalyzeAiSummaryTab 1등 동 (예: "공덕동") 큰 글자 + Top 3 칩
- [ ] **시나리오 10**: 검은 wrapper 사라짐 — 페이지 톤 자연스러움
- [ ] **시나리오 11**: 시뮬 이력 페이지 (`/dashboard/history/:id`) 진입 → HistoryDashboardView (state 기반 hub + 디테일 분기)
- [ ] **시나리오 12**: master `by 매니저명` 배지 (직전 cycle) 그대로
- [ ] **시나리오 13**: manager 권한 (직전 cycle) 그대로
- [ ] **시나리오 14**: mobile (375px) 카드 stack + hero 이미지 적정
- [ ] **시나리오 15**: reduced-motion OS 설정 시 애니메이션 비활성

---

## Verification Summary

전체 변경: 신규 5 + 수정 3 + 삭제 1-3 = **9-11 파일** / 10 task / 강민 verify 15 시나리오.

검증: tsc EXIT=0 / vitest 64/64 / build 신규 에러 0 / 강민 brain.

---

## Spec Self-Review

**1. Spec coverage:**
- ✅ Hub 화면 (작은 헤더 + 3 카드) → T1, T2
- ✅ 라우트 분리 (`/dashboard/*`) + ← Hub back → T3, T4
- ✅ 시뮬 완료 시 navigate → T4
- ✅ 검은 wrapper 제거 + 페이지 톤 통합 → T1 (HubCard `bg-stone-900/60` + 외곽 transparent)
- ✅ KPI 재배치 (ML 5개 / LLM 1등 동) → T5, T6
- ✅ 11종 차트 보존 → 수정 없음 (기존 sub/groups 재사용)
- ✅ 디자인 토큰 보존 → HubCard 가 stone/cyan/indigo/amber 그대로
- ✅ ui-ux-pro-max 체크리스트 → T1 의 컴포넌트 코드에 모두 적용 (touch / focus / reduced-motion / aria-label / image lazy + width/height)
- ✅ TabbedDashboard 폐기 → T7
- ✅ KpiMiniGrid / GradeCard 검토 → T8

**2. Placeholder scan:** "TBD"/"TODO" 0건. 모든 코드 블록 완전.

**3. Type consistency:**
- `SimulationOutput` import 경로 일관 (`'../../../../../types'` 5단계 — sub/predict 패턴, `'../../../types'` 3단계 — pages/dashboard 패턴)
- `DetailModalContent` 일관
- `Outlet context` 패턴 일관 (DashboardOutlet → 3 페이지 모두)
- HubCard `accent` prop = `'indigo' | 'cyan' | 'amber'` Hub 와 1:1
- PredictSummaryTab Kpi `color` prop = `'indigo' | 'cyan' | 'rose' | 'emerald' | 'amber'` (T5 에서 확장)

---

## References

- Spec: `docs/superpowers/specs/2026-04-28-dashboard-hub-redesign-design.md`
- 직전 cycle (3그룹 IA): `docs/superpowers/plans/2026-04-28-3group-tab-restructure.md` 의 sub/groups 재사용
- 레이저 효과 패턴: `frontend/src/pages/JoinUs/components/PricingCard.tsx:28-31`
- ServiceCard / ProjectCard (사용자 제공) — hover scale + arrow 영감
- ui-ux-pro-max 가이드 — CRITICAL/HIGH 체크리스트 spec/HubCard 코드 반영
- 메모리: `feedback_commit_policy`, `feedback_runtime_verification`, `project_dashboard_11_charts`
