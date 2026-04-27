# 대시보드 시각화 가이드 적용 — 11종 차트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SPOTTER TabbedDashboard v4.2에 시각화 가이드(2026-04-23) 기준 11종 신규/교체 차트를 Recharts-only로 통합한다.

**Architecture:** 각 차트는 `frontend/src/components/SimulationResult/dashboard/charts/*.tsx` 단일 파일 컴포넌트. 데이터 변환은 pure function으로 분리해 vitest unit test. 탭 통합은 기존 `tabs/{Summary,Market,Forecast,Insight}Tab.tsx`를 최소 수정으로. Track B(#106 #107) 백엔드 확장은 필드 존재 분기로 forward-compat. Mock 데이터 절대 금지 — 부재 시 dashed placeholder.

**Tech Stack:** React 18 + TypeScript + Recharts + Tailwind + vitest + @testing-library/react. 의존성 추가 0.

**Spec 참조:** `docs/superpowers/specs/2026-04-24-dashboard-viz-guide-design.md`

---

## File Structure

### 신규 파일 (charts/ — 10개)

| 파일 | 책임 | 재사용 |
|---|---|---|
| `charts/Sparkline.tsx` | KPI 카드 하단 미니 라인 (#4) | KPI 4종 |
| `charts/BulletChart.tsx` | 목표-실측 범위 시각화 (#3 #9) | KPI 4종 + Closure |
| `charts/EntrySignalLight.tsx` | GREEN/YELLOW/RED Badge (#10) | 단일 (SummaryTab Hero) |
| `charts/CoreDemographicDonut.tsx` | core_demographic 2-segment Donut (#5) | 단일 |
| `charts/WeekdayWeekendBar.tsx` | 주중/주말 ratio side-by-side (#6) | 단일 |
| `charts/StackedAgeBar.tsx` | top_3_age_groups stacked H-bar (#2) | 단일 |
| `charts/AgentConfidenceRadar.tsx` | 8 Agent confidence Radar (#7) | 단일 |
| `charts/FlowVsRevenueScatter.tsx` | 16동 유동인구 vs 매출 Scatter (#8) | 단일 |
| `charts/LegalDistributionBar.tsx` | risk_level stacked H-bar (#11) | 단일 |
| `charts/WaterfallChart.tsx` | SHAP Waterfall (#1, PoC 이미 있음 — 수정만) | 단일 |

### 수정 파일 (6개)

| 파일 | 수정 요지 |
|---|---|
| `dashboard/tabs/SummaryTab.tsx` | KPI에 Sparkline+Bullet, EntrySignalLight Hero 추가, 인구 구성 Collapsible Section |
| `dashboard/tabs/MarketTab.tsx` | Scatter + LegalDistributionBar 추가 |
| `dashboard/tabs/ForecastTab.tsx` | SHAP horizontal bar → Waterfall 교체, Closure Bullet 추가 |
| `dashboard/tabs/InsightTab.tsx` | Radar overview 상단 추가 |
| `dashboard/shared/KpiMiniGrid.tsx` | Sparkline + Bullet slot 확장 |
| `components/SimulationResult/QuarterlyProjectionChart.tsx` | Track B #107 ci_95 분기 (자동 활성화) |

### 테스트 파일 (10개)

각 차트의 pure function 변환 로직 위주. 컴포넌트 렌더는 smoke test.

---

## Task 1: Sparkline 컴포넌트

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/charts/Sparkline.tsx`
- Test: `frontend/src/components/SimulationResult/dashboard/charts/Sparkline.test.tsx`

- [ ] **Step 1: 테스트 작성**

```tsx
// Sparkline.test.tsx
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Sparkline, computeTrendDirection } from './Sparkline';

describe('computeTrendDirection', () => {
  it('마지막 > 첫 20% 초과면 up', () => {
    expect(computeTrendDirection([100, 110, 125])).toBe('up');
  });
  it('마지막 < 첫 20% 초과면 down', () => {
    expect(computeTrendDirection([100, 90, 70])).toBe('down');
  });
  it('20% 이내면 flat', () => {
    expect(computeTrendDirection([100, 105, 95])).toBe('flat');
  });
  it('데이터 2개 미만이면 flat', () => {
    expect(computeTrendDirection([100])).toBe('flat');
    expect(computeTrendDirection([])).toBe('flat');
  });
});

describe('Sparkline', () => {
  it('데이터 없으면 "—" 렌더', () => {
    const { container } = render(<Sparkline data={[]} />);
    expect(container.textContent).toContain('—');
  });
  it('데이터 있으면 SVG 렌더', () => {
    const { container } = render(<Sparkline data={[100, 110, 125, 120]} />);
    expect(container.querySelector('svg')).toBeTruthy();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/Sparkline.test.tsx
```

Expected: FAIL — "Cannot find module './Sparkline'"

- [ ] **Step 3: 컴포넌트 구현**

```tsx
// Sparkline.tsx
import { LineChart, Line, ResponsiveContainer } from 'recharts';

export type TrendDirection = 'up' | 'down' | 'flat';

export function computeTrendDirection(data: number[]): TrendDirection {
  if (data.length < 2) return 'flat';
  const first = data[0];
  const last = data[data.length - 1];
  if (first === 0) return last > 0 ? 'up' : 'flat';
  const pct = (last - first) / first;
  if (pct > 0.2) return 'up';
  if (pct < -0.2) return 'down';
  return 'flat';
}

const TREND_COLOR: Record<TrendDirection, string> = {
  up: '#22c55e',
  down: '#ef4444',
  flat: '#a8a29e',
};

interface Props {
  data: number[];
  width?: number;
  height?: number;
}

export function Sparkline({ data, width = 80, height = 24 }: Props) {
  if (!data || data.length === 0) {
    return <span className="text-[10px] text-stone-500">—</span>;
  }
  const dir = computeTrendDirection(data);
  const points = data.map((v, i) => ({ i, v }));
  return (
    <div style={{ width, height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 2, right: 0, left: 0, bottom: 2 }}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={TREND_COLOR[dir]}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/Sparkline.test.tsx
```

Expected: PASS — 6 tests

- [ ] **Step 5: 커밋**

```bash
git add src/components/SimulationResult/dashboard/charts/Sparkline.tsx src/components/SimulationResult/dashboard/charts/Sparkline.test.tsx
git commit -m "feat(dashboard): Sparkline 컴포넌트 (#4) — KPI 카드 미니 라인"
```

---

## Task 2: BulletChart 컴포넌트 (#3 #9 재사용)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/charts/BulletChart.tsx`
- Test: `frontend/src/components/SimulationResult/dashboard/charts/BulletChart.test.tsx`

- [ ] **Step 1: 테스트 작성**

```tsx
// BulletChart.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { BulletChart, qualitativeBand } from './BulletChart';

describe('qualitativeBand', () => {
  it('70 이상 → good', () => {
    expect(qualitativeBand(80, [40, 70])).toBe('good');
  });
  it('40-70 → ok', () => {
    expect(qualitativeBand(55, [40, 70])).toBe('ok');
  });
  it('40 미만 → bad', () => {
    expect(qualitativeBand(20, [40, 70])).toBe('bad');
  });
});

describe('BulletChart', () => {
  it('actual 값 표시', () => {
    render(<BulletChart actual={72} target={70} max={100} label="유동인구" />);
    expect(screen.getByText('72')).toBeInTheDocument();
    expect(screen.getByText('유동인구')).toBeInTheDocument();
  });
  it('actual null이면 "—"', () => {
    render(<BulletChart actual={null} target={70} max={100} label="유동인구" />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/BulletChart.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 컴포넌트 구현**

```tsx
// BulletChart.tsx
export type BulletBand = 'bad' | 'ok' | 'good';

export function qualitativeBand(value: number, thresholds: [number, number]): BulletBand {
  const [low, high] = thresholds;
  if (value >= high) return 'good';
  if (value >= low) return 'ok';
  return 'bad';
}

interface Props {
  /** 실측치 (null → 미측정). 0~max 범위. */
  actual: number | null | undefined;
  /** 목표선 위치. 생략 시 표시 안 함. */
  target?: number;
  /** 축 최대값. 기본 100. */
  max?: number;
  /** 하단 라벨. */
  label?: string;
  /** qualitative band 임계값 [low, high]. 기본 [40, 70]. */
  thresholds?: [number, number];
}

export function BulletChart({
  actual,
  target,
  max = 100,
  label,
  thresholds = [40, 70],
}: Props) {
  const hasValue = actual != null;
  const pct = hasValue ? Math.min(100, Math.max(0, (actual / max) * 100)) : 0;
  const targetPct =
    target != null ? Math.min(100, Math.max(0, (target / max) * 100)) : null;
  const [lowPct, highPct] = [
    (thresholds[0] / max) * 100,
    (thresholds[1] / max) * 100,
  ];

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-baseline justify-between">
        {label && (
          <span className="text-[9px] font-bold text-stone-500 uppercase tracking-widest">
            {label}
          </span>
        )}
        <span className="text-xs font-black text-stone-200 tabular-nums">
          {hasValue ? actual : '—'}
        </span>
      </div>
      <div className="relative h-2 w-full rounded-full bg-stone-800 overflow-hidden">
        {/* Qualitative band: bad / ok / good */}
        <div
          className="absolute top-0 left-0 h-full bg-stone-700/40"
          style={{ width: `${lowPct}%` }}
        />
        <div
          className="absolute top-0 h-full bg-stone-600/40"
          style={{ left: `${lowPct}%`, width: `${highPct - lowPct}%` }}
        />
        <div
          className="absolute top-0 h-full bg-stone-500/40"
          style={{ left: `${highPct}%`, width: `${100 - highPct}%` }}
        />
        {/* Actual bar */}
        {hasValue && (
          <div
            className="absolute top-0.5 h-1 rounded-full bg-indigo-400"
            style={{ width: `${pct}%` }}
          />
        )}
        {/* Target line */}
        {targetPct != null && (
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-indigo-200"
            style={{ left: `${targetPct}%` }}
          />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/BulletChart.test.tsx
```

Expected: PASS — 5 tests

- [ ] **Step 5: 커밋**

```bash
git add src/components/SimulationResult/dashboard/charts/BulletChart.tsx src/components/SimulationResult/dashboard/charts/BulletChart.test.tsx
git commit -m "feat(dashboard): BulletChart 컴포넌트 (#3 #9) — 목표-실측 범위 시각화"
```

---

## Task 3: KpiMiniGrid에 Sparkline + Bullet 통합

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/shared/KpiMiniGrid.tsx`

- [ ] **Step 1: 현재 파일 읽기 + 인터페이스 확장**

`KpiItem`에 `spark?: number[]` + `bullet?: { actual, target, thresholds }` slot 추가.

```tsx
// KpiMiniGrid.tsx — 기존 KpiItem 타입 확장
import { Sparkline } from '../charts/Sparkline';
import { BulletChart } from '../charts/BulletChart';

export interface KpiItem {
  label: string;
  value: string;
  sub?: string;
  tag?: string;
  tagColor?: 'emerald' | 'rose';
  /** Sparkline용 시계열 (없으면 표시 안 함) */
  spark?: number[];
  /** Bullet Chart 데이터 (없으면 표시 안 함) */
  bullet?: {
    actual: number | null;
    target?: number;
    max?: number;
    thresholds?: [number, number];
  };
}
```

- [ ] **Step 2: 렌더 로직 수정**

기존 KPI 카드 내부 `{item.sub && <p>...}` 다음에 Sparkline + Bullet slot 추가:

```tsx
{item.spark && item.spark.length > 0 && (
  <div className="mt-2">
    <Sparkline data={item.spark} />
  </div>
)}
{item.bullet && (
  <div className="mt-2">
    <BulletChart
      actual={item.bullet.actual}
      target={item.bullet.target}
      max={item.bullet.max ?? 100}
      thresholds={item.bullet.thresholds}
    />
  </div>
)}
```

- [ ] **Step 3: TS + build 확인**

```bash
npx tsc --noEmit
npx vite build
```

Expected: PASS + 빌드 통과 (chunk size 경고만)

- [ ] **Step 4: 커밋**

```bash
git add src/components/SimulationResult/dashboard/shared/KpiMiniGrid.tsx
git commit -m "feat(dashboard): KpiMiniGrid에 Sparkline + Bullet slot 추가"
```

---

## Task 4: EntrySignalLight 컴포넌트 (#10)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/charts/EntrySignalLight.tsx`
- Test: `frontend/src/components/SimulationResult/dashboard/charts/EntrySignalLight.test.tsx`

- [ ] **Step 1: 테스트 작성**

```tsx
// EntrySignalLight.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { EntrySignalLight } from './EntrySignalLight';

describe('EntrySignalLight', () => {
  it('green → "진입 권장" 라벨', () => {
    render(<EntrySignalLight signal="green" />);
    expect(screen.getByText('진입 권장')).toBeInTheDocument();
  });
  it('yellow → "조건부 진입"', () => {
    render(<EntrySignalLight signal="yellow" />);
    expect(screen.getByText('조건부 진입')).toBeInTheDocument();
  });
  it('red → "진입 비권장"', () => {
    render(<EntrySignalLight signal="red" />);
    expect(screen.getByText('진입 비권장')).toBeInTheDocument();
  });
  it('null → placeholder 렌더', () => {
    render(<EntrySignalLight signal={null} />);
    expect(screen.getByText(/데이터 부재|competitor_intel 대기|—/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/EntrySignalLight.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 컴포넌트 구현**

```tsx
// EntrySignalLight.tsx
import { CheckCircle2, AlertCircle, XCircle, HelpCircle } from 'lucide-react';

export type EntrySignal = 'green' | 'yellow' | 'red';

const SIGNAL_META: Record<
  EntrySignal,
  { label: string; colorBg: string; colorText: string; Icon: typeof CheckCircle2 }
> = {
  green: {
    label: '진입 권장',
    colorBg: 'bg-emerald-500/10 border-emerald-500/40',
    colorText: 'text-emerald-400',
    Icon: CheckCircle2,
  },
  yellow: {
    label: '조건부 진입',
    colorBg: 'bg-amber-500/10 border-amber-500/40',
    colorText: 'text-amber-400',
    Icon: AlertCircle,
  },
  red: {
    label: '진입 비권장',
    colorBg: 'bg-rose-500/10 border-rose-500/40',
    colorText: 'text-rose-400',
    Icon: XCircle,
  },
};

interface Props {
  signal: EntrySignal | null | undefined;
}

export function EntrySignalLight({ signal }: Props) {
  if (!signal || !(signal in SIGNAL_META)) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-xl border border-dashed border-stone-700 bg-stone-900/40 text-stone-500 text-xs">
        <HelpCircle size={14} />
        <span>competitor_intel 분석 대기 — 데이터 부재</span>
      </div>
    );
  }
  const meta = SIGNAL_META[signal];
  const Icon = meta.Icon;
  return (
    <div
      className={`flex items-center gap-3 px-4 py-2.5 rounded-xl border ${meta.colorBg}`}
    >
      <Icon className={meta.colorText} size={18} />
      <div className="flex flex-col">
        <span className={`text-[10px] font-black uppercase tracking-widest ${meta.colorText}`}>
          Entry Signal
        </span>
        <span className={`text-sm font-black ${meta.colorText}`}>{meta.label}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/EntrySignalLight.test.tsx
```

Expected: PASS — 4 tests

- [ ] **Step 5: 커밋**

```bash
git add src/components/SimulationResult/dashboard/charts/EntrySignalLight.tsx src/components/SimulationResult/dashboard/charts/EntrySignalLight.test.tsx
git commit -m "feat(dashboard): EntrySignalLight (#10) — market_entry_signal 신호등"
```

---

## Task 5: CoreDemographicDonut (#5)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/charts/CoreDemographicDonut.tsx`
- Test: `frontend/src/components/SimulationResult/dashboard/charts/CoreDemographicDonut.test.tsx`

- [ ] **Step 1: 테스트 작성**

```tsx
// CoreDemographicDonut.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { CoreDemographicDonut } from './CoreDemographicDonut';

describe('CoreDemographicDonut', () => {
  it('core 데이터 있으면 라벨 + share 렌더', () => {
    render(
      <CoreDemographicDonut
        core={{ age: '30대', gender: '여성', share: 0.42 }}
      />,
    );
    expect(screen.getByText(/30대.*여성|30대 여성/)).toBeInTheDocument();
    expect(screen.getByText(/42/)).toBeInTheDocument();
  });
  it('core null이면 placeholder 렌더', () => {
    render(<CoreDemographicDonut core={null} />);
    expect(screen.getByText(/분석 대기|데이터 부재/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/CoreDemographicDonut.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 컴포넌트 구현**

```tsx
// CoreDemographicDonut.tsx
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';

interface CoreDemo {
  age: string;
  gender: string;
  share: number; // 0.0 ~ 1.0
}

interface Props {
  core: CoreDemo | null | undefined;
}

export function CoreDemographicDonut({ core }: Props) {
  if (!core || typeof core.share !== 'number') {
    return (
      <div className="flex h-[140px] flex-col items-center justify-center rounded-2xl border border-dashed border-stone-800 text-stone-500 text-xs">
        <span>demographic_depth 분석 대기</span>
      </div>
    );
  }
  const sharePct = Math.round(core.share * 100);
  const data = [
    { name: 'main', value: sharePct },
    { name: 'rest', value: 100 - sharePct },
  ];

  return (
    <div className="relative h-[140px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            innerRadius={40}
            outerRadius={60}
            startAngle={90}
            endAngle={-270}
            dataKey="value"
            stroke="none"
          >
            <Cell fill="#818cf8" />
            <Cell fill="#292524" />
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <span className="text-[9px] font-black text-stone-500 uppercase tracking-widest">
          Core
        </span>
        <span className="text-sm font-black text-stone-100 tabular-nums">
          {core.age} {core.gender}
        </span>
        <span className="text-[11px] font-black text-indigo-400 tabular-nums">
          {sharePct}%
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/CoreDemographicDonut.test.tsx
```

Expected: PASS — 2 tests

- [ ] **Step 5: 커밋**

```bash
git add src/components/SimulationResult/dashboard/charts/CoreDemographicDonut.tsx src/components/SimulationResult/dashboard/charts/CoreDemographicDonut.test.tsx
git commit -m "feat(dashboard): CoreDemographicDonut (#5) — 주요 소비 연령대 share"
```

---

## Task 6: WeekdayWeekendBar (#6)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/charts/WeekdayWeekendBar.tsx`
- Test: `frontend/src/components/SimulationResult/dashboard/charts/WeekdayWeekendBar.test.tsx`

- [ ] **Step 1: 테스트 작성**

```tsx
// WeekdayWeekendBar.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { WeekdayWeekendBar, normalizeRatio } from './WeekdayWeekendBar';

describe('normalizeRatio', () => {
  it('ratio > 1이면 1로 clamp', () => {
    expect(normalizeRatio(1.5)).toBe(1);
  });
  it('ratio < 0이면 0으로 clamp', () => {
    expect(normalizeRatio(-0.3)).toBe(0);
  });
  it('정상 범위는 그대로', () => {
    expect(normalizeRatio(0.4)).toBe(0.4);
  });
  it('null/undefined → null', () => {
    expect(normalizeRatio(null)).toBe(null);
    expect(normalizeRatio(undefined)).toBe(null);
  });
});

describe('WeekdayWeekendBar', () => {
  it('ratio 있으면 라벨 렌더', () => {
    render(<WeekdayWeekendBar ratio={0.6} />);
    expect(screen.getByText(/주중/)).toBeInTheDocument();
    expect(screen.getByText(/주말/)).toBeInTheDocument();
  });
  it('ratio null이면 placeholder', () => {
    render(<WeekdayWeekendBar ratio={null} />);
    expect(screen.getByText(/분석 대기|데이터 부재/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/WeekdayWeekendBar.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 컴포넌트 구현**

```tsx
// WeekdayWeekendBar.tsx
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from 'recharts';

export function normalizeRatio(r: number | null | undefined): number | null {
  if (r == null || Number.isNaN(r)) return null;
  return Math.min(1, Math.max(0, r));
}

interface Props {
  /** 주중 비율 (0.0~1.0). 주말 = 1 - weekday. */
  ratio: number | null | undefined;
}

export function WeekdayWeekendBar({ ratio }: Props) {
  const n = normalizeRatio(ratio);
  if (n == null) {
    return (
      <div className="flex h-[120px] items-center justify-center rounded-2xl border border-dashed border-stone-800 text-stone-500 text-xs">
        demographic_depth 분석 대기
      </div>
    );
  }
  const data = [
    { label: '주중', value: Math.round(n * 100), color: '#818cf8' },
    { label: '주말', value: Math.round((1 - n) * 100), color: '#a8a29e' },
  ];
  return (
    <div className="h-[120px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 30, left: 30, bottom: 8 }}>
          <XAxis type="number" domain={[0, 100]} hide />
          <YAxis
            type="category"
            dataKey="label"
            tick={{ fontSize: 11, fill: '#a8a29e' }}
            axisLine={false}
            tickLine={false}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/WeekdayWeekendBar.test.tsx
```

Expected: PASS — 6 tests

- [ ] **Step 5: 커밋**

```bash
git add src/components/SimulationResult/dashboard/charts/WeekdayWeekendBar.tsx src/components/SimulationResult/dashboard/charts/WeekdayWeekendBar.test.tsx
git commit -m "feat(dashboard): WeekdayWeekendBar (#6) — 주중/주말 비율 side-by-side"
```

---

## Task 7: StackedAgeBar (#2)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/charts/StackedAgeBar.tsx`
- Test: `frontend/src/components/SimulationResult/dashboard/charts/StackedAgeBar.test.tsx`

- [ ] **Step 1: 테스트 작성**

```tsx
// StackedAgeBar.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { StackedAgeBar, normalizeAgeGroups } from './StackedAgeBar';

describe('normalizeAgeGroups', () => {
  it('빈 배열 → []', () => {
    expect(normalizeAgeGroups([])).toEqual([]);
  });
  it('정상 배열 share 합이 1.0 초과 시 정규화', () => {
    const result = normalizeAgeGroups([
      { age_group: '30대', share: 0.6 },
      { age_group: '20대', share: 0.5 },
      { age_group: '40대', share: 0.3 },
    ]);
    const sum = result.reduce((s, r) => s + r.share, 0);
    expect(sum).toBeCloseTo(1.0, 5);
  });
  it('share 합이 1 미만이면 "기타" 자동 추가', () => {
    const result = normalizeAgeGroups([
      { age_group: '30대', share: 0.4 },
      { age_group: '20대', share: 0.3 },
    ]);
    expect(result).toHaveLength(3);
    expect(result[2].age_group).toBe('기타');
    expect(result[2].share).toBeCloseTo(0.3, 5);
  });
});

describe('StackedAgeBar', () => {
  it('데이터 있으면 연령대 라벨 렌더', () => {
    render(
      <StackedAgeBar
        groups={[
          { age_group: '30대', share: 0.4 },
          { age_group: '20대', share: 0.3 },
        ]}
      />,
    );
    expect(screen.getByText('30대')).toBeInTheDocument();
  });
  it('빈 배열이면 placeholder', () => {
    render(<StackedAgeBar groups={[]} />);
    expect(screen.getByText(/분석 대기|데이터 부재/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/StackedAgeBar.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 컴포넌트 구현**

```tsx
// StackedAgeBar.tsx
interface AgeGroup {
  age_group: string;
  share: number;
}

export function normalizeAgeGroups(raw: AgeGroup[] | null | undefined): AgeGroup[] {
  if (!raw || raw.length === 0) return [];
  const sum = raw.reduce((s, r) => s + (r.share ?? 0), 0);
  if (sum <= 0) return [];
  if (sum > 1.0) {
    // 합이 1 초과 → 비율 재계산
    return raw.map((r) => ({ ...r, share: r.share / sum }));
  }
  if (sum < 0.99) {
    // "기타" 자동 추가 (1% 이상 gap일 때)
    return [...raw, { age_group: '기타', share: 1 - sum }];
  }
  return raw;
}

const COLORS = ['#818cf8', '#a5b4fc', '#c7d2fe', '#a8a29e'];

interface Props {
  groups: AgeGroup[] | null | undefined;
}

export function StackedAgeBar({ groups }: Props) {
  const normalized = normalizeAgeGroups(groups);
  if (normalized.length === 0) {
    return (
      <div className="flex h-[100px] items-center justify-center rounded-2xl border border-dashed border-stone-800 text-stone-500 text-xs">
        demographic_depth 분석 대기
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex h-8 w-full overflow-hidden rounded-xl border border-stone-800">
        {normalized.map((g, i) => (
          <div
            key={g.age_group}
            className="flex items-center justify-center text-[10px] font-black text-stone-100"
            style={{ width: `${g.share * 100}%`, backgroundColor: COLORS[i] ?? COLORS[3] }}
          >
            {g.share >= 0.08 ? `${Math.round(g.share * 100)}%` : ''}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-3 text-[10px]">
        {normalized.map((g, i) => (
          <div key={g.age_group} className="flex items-center gap-1.5">
            <div
              className="h-2 w-2 rounded-sm"
              style={{ backgroundColor: COLORS[i] ?? COLORS[3] }}
            />
            <span className="font-bold text-stone-400">{g.age_group}</span>
            <span className="tabular-nums text-stone-500">
              {Math.round(g.share * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/StackedAgeBar.test.tsx
```

Expected: PASS — 5 tests

- [ ] **Step 5: 커밋**

```bash
git add src/components/SimulationResult/dashboard/charts/StackedAgeBar.tsx src/components/SimulationResult/dashboard/charts/StackedAgeBar.test.tsx
git commit -m "feat(dashboard): StackedAgeBar (#2) — top_3_age_groups stacked H-bar"
```

---

## Task 8: AgentConfidenceRadar (#7)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/charts/AgentConfidenceRadar.tsx`
- Test: `frontend/src/components/SimulationResult/dashboard/charts/AgentConfidenceRadar.test.tsx`

- [ ] **Step 1: 테스트 작성**

```tsx
// AgentConfidenceRadar.test.tsx
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AgentConfidenceRadar, buildRadarData } from './AgentConfidenceRadar';
import type { AgentAttribution } from '../../../../types';

describe('buildRadarData', () => {
  it('8 에이전트 모두 0~100 점수로 변환', () => {
    const attrs: AgentAttribution[] = [
      {
        id: 'market_analyst',
        display_name: 'Market',
        kind: 'Python',
        sources: [],
        verdict: '',
        reasoning: '',
        confidence: 0.85,
      },
    ];
    const data = buildRadarData(attrs);
    expect(data).toHaveLength(8);
    const market = data.find((d) => d.id === 'market_analyst');
    expect(market?.score).toBe(85);
  });
  it('missing 에이전트는 score=0', () => {
    const data = buildRadarData([]);
    expect(data.every((d) => d.score === 0)).toBe(true);
  });
  it('confidence null → score=0', () => {
    const attrs: AgentAttribution[] = [
      {
        id: 'legal',
        display_name: 'Legal',
        kind: 'RAG',
        sources: [],
        verdict: '',
        reasoning: '',
      },
    ];
    const legal = buildRadarData(attrs).find((d) => d.id === 'legal');
    expect(legal?.score).toBe(0);
  });
});

describe('AgentConfidenceRadar', () => {
  it('SVG 렌더', () => {
    const { container } = render(<AgentConfidenceRadar attributions={[]} />);
    expect(container.querySelector('svg')).toBeTruthy();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/AgentConfidenceRadar.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 컴포넌트 구현**

```tsx
// AgentConfidenceRadar.tsx
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts';
import type { AgentAttribution, AgentId } from '../../../../types';

const AGENT_ORDER: { id: AgentId; label: string }[] = [
  { id: 'market_analyst', label: '시장' },
  { id: 'population_analyst', label: '유동' },
  { id: 'demographic_depth', label: '인구' },
  { id: 'competitor_intel', label: '경쟁' },
  { id: 'legal', label: '법률' },
  { id: 'trend_forecaster', label: '트렌드' },
  { id: 'district_ranking', label: '랭킹' },
  { id: 'synthesis', label: '종합' },
];

export interface RadarRow {
  id: AgentId;
  label: string;
  score: number;
}

export function buildRadarData(attributions: AgentAttribution[]): RadarRow[] {
  return AGENT_ORDER.map(({ id, label }) => {
    const attr = attributions.find((a) => a.id === id);
    const score = attr?.confidence != null ? Math.round(attr.confidence * 100) : 0;
    return { id, label, score };
  });
}

interface Props {
  attributions: AgentAttribution[];
}

export function AgentConfidenceRadar({ attributions }: Props) {
  const data = buildRadarData(attributions);
  return (
    <div className="h-[280px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="70%">
          <PolarGrid stroke="#292524" />
          <PolarAngleAxis
            dataKey="label"
            tick={{ fontSize: 10, fill: '#a8a29e' }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fontSize: 9, fill: '#57534e' }}
            axisLine={false}
          />
          <Radar
            dataKey="score"
            stroke="#818cf8"
            fill="#818cf8"
            fillOpacity={0.25}
            isAnimationActive={false}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/AgentConfidenceRadar.test.tsx
```

Expected: PASS — 4 tests

- [ ] **Step 5: 커밋**

```bash
git add src/components/SimulationResult/dashboard/charts/AgentConfidenceRadar.tsx src/components/SimulationResult/dashboard/charts/AgentConfidenceRadar.test.tsx
git commit -m "feat(dashboard): AgentConfidenceRadar (#7) — 8 에이전트 신뢰도 Radar"
```

---

## Task 9: FlowVsRevenueScatter (#8)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/charts/FlowVsRevenueScatter.tsx`
- Test: `frontend/src/components/SimulationResult/dashboard/charts/FlowVsRevenueScatter.test.tsx`

- [ ] **Step 1: 테스트 작성**

```tsx
// FlowVsRevenueScatter.test.tsx
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { FlowVsRevenueScatter, simpleLinearRegression } from './FlowVsRevenueScatter';
import type { DistrictRanking } from '../../../../types';

describe('simpleLinearRegression', () => {
  it('완벽 선형 데이터 → slope + intercept 복구', () => {
    const points = [
      { x: 0, y: 0 },
      { x: 1, y: 2 },
      { x: 2, y: 4 },
      { x: 3, y: 6 },
    ];
    const { slope, intercept } = simpleLinearRegression(points);
    expect(slope).toBeCloseTo(2, 5);
    expect(intercept).toBeCloseTo(0, 5);
  });
  it('데이터 2개 미만 → null', () => {
    expect(simpleLinearRegression([])).toBe(null);
    expect(simpleLinearRegression([{ x: 1, y: 1 }])).toBe(null);
  });
});

describe('FlowVsRevenueScatter', () => {
  it('SVG 렌더', () => {
    const rankings: DistrictRanking[] = [
      {
        rank: 1,
        district: '서교동',
        score: 85,
        sales_growth: 0.1,
        sales_score: 80,
        pop_growth: 0.05,
        pop_score: 75,
        avg_rent: 0,
        rent_score: 0,
        vacancy_rate: 0,
        zoning_risk: 'safe',
      },
    ];
    const { container } = render(
      <FlowVsRevenueScatter rankings={rankings} winnerDistrict="서교동" />,
    );
    expect(container.querySelector('svg')).toBeTruthy();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/FlowVsRevenueScatter.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 컴포넌트 구현**

```tsx
// FlowVsRevenueScatter.tsx
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  ReferenceLine,
  Cell,
} from 'recharts';
import type { DistrictRanking } from '../../../../types';

export function simpleLinearRegression(
  points: { x: number; y: number }[],
): { slope: number; intercept: number } | null {
  if (points.length < 2) return null;
  const n = points.length;
  const sumX = points.reduce((s, p) => s + p.x, 0);
  const sumY = points.reduce((s, p) => s + p.y, 0);
  const sumXY = points.reduce((s, p) => s + p.x * p.y, 0);
  const sumX2 = points.reduce((s, p) => s + p.x * p.x, 0);
  const denom = n * sumX2 - sumX * sumX;
  if (denom === 0) return null;
  const slope = (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;
  return { slope, intercept };
}

interface Props {
  rankings: DistrictRanking[];
  winnerDistrict?: string;
}

export function FlowVsRevenueScatter({ rankings, winnerDistrict }: Props) {
  const points = rankings
    .filter((r) => typeof r.pop_score === 'number' && typeof r.sales_score === 'number')
    .map((r) => ({
      x: r.pop_score,
      y: r.sales_score,
      district: r.district,
      isWinner: r.district === winnerDistrict,
    }));

  if (points.length === 0) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded-2xl border border-dashed border-stone-800 text-stone-500 text-xs">
        district_rankings 분석 대기
      </div>
    );
  }

  const reg = simpleLinearRegression(points.map((p) => ({ x: p.x, y: p.y })));
  const regLine =
    reg != null
      ? [
          { x: 0, y: reg.intercept },
          { x: 100, y: reg.intercept + reg.slope * 100 },
        ]
      : null;

  return (
    <div className="h-[320px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 16, right: 24, left: 16, bottom: 24 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#292524" />
          <XAxis
            type="number"
            dataKey="x"
            name="유동인구 점수"
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: '#a8a29e' }}
            label={{ value: '유동인구', fill: '#57534e', fontSize: 10, dy: 20 }}
          />
          <YAxis
            type="number"
            dataKey="y"
            name="매출 점수"
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: '#a8a29e' }}
            label={{ value: '매출', angle: -90, fill: '#57534e', fontSize: 10, dx: -10 }}
          />
          <Tooltip
            cursor={{ strokeDasharray: '3 3', stroke: '#818cf8' }}
            contentStyle={{
              backgroundColor: '#1a1a1a',
              border: '1px solid #44403c',
              borderRadius: 8,
              fontSize: 11,
            }}
            formatter={(_v, _n, item) => {
              const p = item?.payload as (typeof points)[0];
              return [`${p.district} (유동 ${p.x}·매출 ${p.y})`, ''];
            }}
            labelFormatter={() => ''}
          />
          {regLine && (
            <ReferenceLine
              segment={regLine}
              stroke="#818cf8"
              strokeDasharray="4 4"
              strokeOpacity={0.5}
            />
          )}
          <Scatter data={points} isAnimationActive={false}>
            {points.map((p, i) => (
              <Cell
                key={i}
                fill={p.isWinner ? '#818cf8' : '#a8a29e'}
                r={p.isWinner ? 8 : 4}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/FlowVsRevenueScatter.test.tsx
```

Expected: PASS — 3 tests

- [ ] **Step 5: 커밋**

```bash
git add src/components/SimulationResult/dashboard/charts/FlowVsRevenueScatter.tsx src/components/SimulationResult/dashboard/charts/FlowVsRevenueScatter.test.tsx
git commit -m "feat(dashboard): FlowVsRevenueScatter (#8) — 16동 유동인구 vs 매출 산점도"
```

---

## Task 10: LegalDistributionBar (#11)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/charts/LegalDistributionBar.tsx`
- Test: `frontend/src/components/SimulationResult/dashboard/charts/LegalDistributionBar.test.tsx`

- [ ] **Step 1: 테스트 작성**

```tsx
// LegalDistributionBar.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { LegalDistributionBar, countByLevel } from './LegalDistributionBar';
import type { LegalRisk } from '../../../../types';

describe('countByLevel', () => {
  it('각 등급 건수 카운트 (대소문자 무시)', () => {
    const risks: LegalRisk[] = [
      { type: 't', risk_level: 'HIGH', detail: '' },
      { type: 't', risk_level: 'danger', detail: '' },
      { type: 't', risk_level: 'MEDIUM', detail: '' },
      { type: 't', risk_level: 'low', detail: '' },
    ];
    const counts = countByLevel(risks);
    expect(counts.high).toBe(2); // HIGH + danger
    expect(counts.medium).toBe(1);
    expect(counts.low).toBe(1);
  });
  it('빈 배열 → 모두 0', () => {
    const counts = countByLevel([]);
    expect(counts.high).toBe(0);
    expect(counts.medium).toBe(0);
    expect(counts.low).toBe(0);
  });
  it('is_fallback 카운트 분리', () => {
    const risks: LegalRisk[] = [
      { type: 't', risk_level: 'HIGH', detail: '' },
      { type: 't', risk_level: 'HIGH', detail: '', is_fallback: true },
    ];
    const counts = countByLevel(risks);
    expect(counts.high).toBe(2);
    expect(counts.fallback).toBe(1);
  });
});

describe('LegalDistributionBar', () => {
  it('건수 있으면 라벨 렌더', () => {
    const risks: LegalRisk[] = [
      { type: 't', risk_level: 'HIGH', detail: '' },
      { type: 't', risk_level: 'MEDIUM', detail: '' },
    ];
    render(<LegalDistributionBar risks={risks} />);
    expect(screen.getByText(/필수이행/)).toBeInTheDocument();
    expect(screen.getByText(/확인필요/)).toBeInTheDocument();
  });
  it('빈 배열 → placeholder', () => {
    render(<LegalDistributionBar risks={[]} />);
    expect(screen.getByText(/분석 대기|데이터 부재/)).toBeTruthy();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/LegalDistributionBar.test.tsx
```

Expected: FAIL

- [ ] **Step 3: 컴포넌트 구현**

```tsx
// LegalDistributionBar.tsx
import type { LegalRisk } from '../../../../types';

export interface LevelCounts {
  high: number;
  medium: number;
  low: number;
  fallback: number;
}

export function countByLevel(risks: LegalRisk[]): LevelCounts {
  const out: LevelCounts = { high: 0, medium: 0, low: 0, fallback: 0 };
  for (const r of risks ?? []) {
    const lvl = String(r.risk_level ?? '').toUpperCase();
    if (lvl === 'HIGH' || lvl === 'DANGER') out.high++;
    else if (lvl === 'MEDIUM' || lvl === 'CAUTION') out.medium++;
    else out.low++;
    if (r.is_fallback) out.fallback++;
  }
  return out;
}

interface Props {
  risks: LegalRisk[] | null | undefined;
}

export function LegalDistributionBar({ risks }: Props) {
  if (!risks || risks.length === 0) {
    return (
      <div className="flex h-[80px] items-center justify-center rounded-2xl border border-dashed border-stone-800 text-stone-500 text-xs">
        legal 분석 대기
      </div>
    );
  }
  const counts = countByLevel(risks);
  const total = counts.high + counts.medium + counts.low;
  const pct = (n: number) => (total > 0 ? (n / total) * 100 : 0);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex h-6 w-full overflow-hidden rounded-lg border border-stone-800">
        <div
          className="flex items-center justify-center bg-rose-500/80 text-[9px] font-black text-white"
          style={{ width: `${pct(counts.high)}%` }}
          title={`필수이행 ${counts.high}`}
        >
          {counts.high >= 1 && pct(counts.high) > 10 ? counts.high : ''}
        </div>
        <div
          className="flex items-center justify-center bg-amber-500/80 text-[9px] font-black text-stone-950"
          style={{ width: `${pct(counts.medium)}%` }}
          title={`확인필요 ${counts.medium}`}
        >
          {counts.medium >= 1 && pct(counts.medium) > 10 ? counts.medium : ''}
        </div>
        <div
          className="flex items-center justify-center bg-emerald-500/80 text-[9px] font-black text-stone-950"
          style={{ width: `${pct(counts.low)}%` }}
          title={`참고사항 ${counts.low}`}
        >
          {counts.low >= 1 && pct(counts.low) > 10 ? counts.low : ''}
        </div>
      </div>
      <div className="flex flex-wrap gap-4 text-[10px]">
        <LegendItem color="bg-rose-500" label={`필수이행 ${counts.high}`} />
        <LegendItem color="bg-amber-500" label={`확인필요 ${counts.medium}`} />
        <LegendItem color="bg-emerald-500" label={`참고사항 ${counts.low}`} />
        {counts.fallback > 0 && (
          <span className="text-stone-500 italic">
            (fallback {counts.fallback})
          </span>
        )}
      </div>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className={`h-2 w-2 rounded-sm ${color}`} />
      <span className="font-bold text-stone-400 tabular-nums">{label}</span>
    </div>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/LegalDistributionBar.test.tsx
```

Expected: PASS — 5 tests

- [ ] **Step 5: 커밋**

```bash
git add src/components/SimulationResult/dashboard/charts/LegalDistributionBar.tsx src/components/SimulationResult/dashboard/charts/LegalDistributionBar.test.tsx
git commit -m "feat(dashboard): LegalDistributionBar (#11) — 법률 리스크 등급 분포"
```

---

## Task 11: WaterfallChart 단위 테스트 추가

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/charts/WaterfallChart.test.tsx`
- Modify (optional export): `frontend/src/components/SimulationResult/dashboard/charts/WaterfallChart.tsx`

PoC 단계에서 `buildRows`가 module-level function이지만 export되지 않음 → export 추가 후 테스트.

- [ ] **Step 1: `buildRows`를 named export로 전환**

`WaterfallChart.tsx`의 `function buildRows(...)`를 `export function buildRows(...)`로 변경.

- [ ] **Step 2: 테스트 작성**

```tsx
// WaterfallChart.test.tsx
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { WaterfallChart, buildRows, type WaterfallStep } from './WaterfallChart';

describe('buildRows', () => {
  const steps: WaterfallStep[] = [
    { label: 'Base', value: 100, kind: 'base' },
    { label: 'A', value: 30, kind: 'contribution' },
    { label: 'B', value: -20, kind: 'contribution' },
    { label: 'Final', value: 110, kind: 'final' },
  ];
  it('base/final의 spacer는 0', () => {
    const { rows } = buildRows(steps);
    expect(rows[0].spacer).toBe(0);
    expect(rows[3].spacer).toBe(0);
  });
  it('양수 contribution: spacer = 이전 running total', () => {
    const { rows } = buildRows(steps);
    expect(rows[1].spacer).toBe(100);
    expect(rows[1].bar).toBe(30);
  });
  it('음수 contribution: spacer = running + value (더 낮은 위치)', () => {
    const { rows } = buildRows(steps);
    expect(rows[2].spacer).toBe(100 + 30 + -20); // = 110 (running after A)은 아니고... 계산:
    // A 후 running = 130. B = -20. spacer = 130 + -20 = 110
    expect(rows[2].spacer).toBe(110);
    expect(rows[2].bar).toBe(20); // abs
  });
});

describe('WaterfallChart', () => {
  it('빈 steps → placeholder', () => {
    const { container } = render(<WaterfallChart steps={[]} />);
    expect(container.textContent).toContain('Waterfall 데이터 없음');
  });
  it('steps 있으면 SVG 렌더', () => {
    const steps: WaterfallStep[] = [
      { label: 'Base', value: 100, kind: 'base' },
      { label: 'Final', value: 100, kind: 'final' },
    ];
    const { container } = render(<WaterfallChart steps={steps} />);
    expect(container.querySelector('svg')).toBeTruthy();
  });
});
```

- [ ] **Step 3: 테스트 실행**

```bash
npx vitest run src/components/SimulationResult/dashboard/charts/WaterfallChart.test.tsx
```

Expected: PASS — 5 tests

- [ ] **Step 4: 커밋**

```bash
git add src/components/SimulationResult/dashboard/charts/WaterfallChart.tsx src/components/SimulationResult/dashboard/charts/WaterfallChart.test.tsx
git commit -m "test(dashboard): WaterfallChart buildRows 단위 테스트 + buildRows export"
```

---

## Task 12: ForecastTab에 Waterfall + Bullet 통합

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/tabs/ForecastTab.tsx`

기존 SHAP horizontal bar를 Waterfall로 교체하고, Closure Risk Bullet 카드를 신규 추가.

- [ ] **Step 1: Waterfall 데이터 변환 헬퍼 작성**

`ForecastTab.tsx` 상단에 import 추가 + 변환 함수:

```tsx
import { WaterfallChart, type WaterfallStep } from '../charts/WaterfallChart';
import { BulletChart } from '../charts/BulletChart';
import type { ShapResult, ClosureRisk } from '../../../../types';

function shapToWaterfall(shap: ShapResult | null | undefined): WaterfallStep[] {
  if (!shap) return [];
  const top = (shap.feature_importance ?? []).slice(0, 6); // top 6로 제한 (가이드 권장 5-6)
  const steps: WaterfallStep[] = [
    { label: 'Base', value: shap.base_value, kind: 'base' },
  ];
  top.forEach((f) => {
    steps.push({
      label: f.feature_ko || f.feature,
      value: f.shap_value,
      kind: 'contribution',
    });
  });
  steps.push({ label: 'Final', value: shap.predicted_value, kind: 'final' });
  return steps;
}
```

- [ ] **Step 2: SHAP 섹션 교체**

`ForecastTab.tsx`의 SHAP horizontal bar 영역 (line 79~133 주변, `{shapTop4.length > 0 ? ... }` 전체)을 다음으로 교체:

```tsx
{/* SHAP Waterfall */}
<div className="space-y-4">
  <div className="flex items-center justify-between border-b border-stone-800 pb-3">
    <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest flex items-center gap-2 italic">
      <Zap className="text-amber-400" size={14} /> 피처 기여도 분석 (SHAP Waterfall)
    </h4>
    {shap && (
      <button
        type="button"
        onClick={() => openModal({
          title: 'SHAP 해석 상세',
          content: `SHAP (SHapley Additive exPlanations)은 각 피처가 예측값에 얼마나 기여했는지 정량화합니다.\n\nbase_value: ${shap.base_value.toLocaleString('ko-KR')}원\npredicted_value: ${shap.predicted_value.toLocaleString('ko-KR')}원\n\n양수 피처는 매출을 밀어올리고, 음수는 낮춥니다.${shap.is_mock ? '\n\n⚠️ 현재 SHAP 데이터는 mock 상태입니다.' : ''}`,
        })}
        className="text-[10px] font-bold text-stone-500 hover:text-indigo-400 uppercase tracking-widest flex items-center gap-1 transition-colors"
      >
        <Maximize2 size={12} /> 해석 상세
      </button>
    )}
  </div>

  {shap ? (
    <WaterfallChart
      steps={shapToWaterfall(shap)}
      formatY={(n) => `${(n / 10000).toFixed(0)}만`}
      height={320}
    />
  ) : (
    <div className="rounded-lg border border-dashed border-stone-800 bg-stone-950/40 p-8 text-center text-xs text-stone-500">
      SHAP 해석 데이터 없음 — 모델 예측 신뢰도가 확정되면 표시됩니다
    </div>
  )}
</div>

{/* Closure Risk Bullet */}
<ClosureRiskPanel closure={simResult.closure_risk} />
```

기존 `formatShapValue`, `shapBarWidth` import는 더 이상 필요 없으면 제거.

- [ ] **Step 3: ClosureRiskPanel 내부 컴포넌트 추가**

`ForecastTab.tsx` 파일 하단에:

```tsx
function ClosureRiskPanel({ closure }: { closure: ClosureRisk | null | undefined }) {
  if (!closure) {
    return (
      <div className="rounded-2xl border border-dashed border-stone-800 bg-stone-950/40 p-6 text-center text-xs text-stone-500">
        closure_risk 분석 대기
      </div>
    );
  }
  return (
    <div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest flex items-center gap-2">
          폐업 위험도
        </h4>
        {closure.is_mock && (
          <span className="text-[9px] font-black text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded-full uppercase">
            MOCK
          </span>
        )}
      </div>
      <BulletChart
        actual={closure.risk_score}
        target={30}
        max={100}
        label="위험 점수"
        thresholds={[30, 60]}
      />
      {closure.summary && closure.summary.length > 0 && (
        <p className="mt-3 text-[11px] text-stone-400 leading-relaxed">
          {closure.summary[0]}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: TS + build 확인**

```bash
npx tsc --noEmit
npx vite build
```

Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/components/SimulationResult/dashboard/tabs/ForecastTab.tsx
git commit -m "feat(dashboard): ForecastTab SHAP → Waterfall 교체 + Closure Bullet 추가"
```

---

## Task 13: SummaryTab에 EntrySignalLight + 인구 구성 Collapsible 통합

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/tabs/SummaryTab.tsx`

- [ ] **Step 1: import 추가**

```tsx
import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { EntrySignalLight } from '../charts/EntrySignalLight';
import { CoreDemographicDonut } from '../charts/CoreDemographicDonut';
import { WeekdayWeekendBar } from '../charts/WeekdayWeekendBar';
import { StackedAgeBar } from '../charts/StackedAgeBar';
```

- [ ] **Step 2: EntrySignalLight를 Summary 최상단에 추가**

`SummaryTab`의 return 최상단 (기존 DecisionCard grid 위)에 삽입:

```tsx
{/* Hero: Market Entry Signal */}
{(() => {
  const signal = (ci?.market_entry_signal as 'green' | 'yellow' | 'red' | undefined) ?? null;
  return (
    <div className="flex justify-end">
      <EntrySignalLight signal={signal} />
    </div>
  );
})()}
```

- [ ] **Step 3: 인구 구성 Collapsible Section 추가**

기존 `DemographicReportSection` 함수 호출 위에 새 Collapsible 섹션 추가:

```tsx
<DemographicCompositionSection demo={demo} />
```

그리고 파일 하단에 새 컴포넌트 추가:

```tsx
function DemographicCompositionSection({
  demo,
}: {
  demo: SimulationOutput['demographic_report'];
}) {
  const [open, setOpen] = useState(true);
  const hasAny = Boolean(
    demo?.core_demographic ||
      (demo?.top_3_age_groups && demo.top_3_age_groups.length > 0) ||
      typeof demo?.weekday_weekend_ratio === 'number',
  );
  if (!hasAny) return null;

  return (
    <div className="bg-stone-900/30 border border-stone-800/40 rounded-3xl overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 p-6 hover:bg-stone-900/40 transition-colors"
      >
        {open ? (
          <ChevronDown size={16} className="text-stone-500" />
        ) : (
          <ChevronRight size={16} className="text-stone-500" />
        )}
        <h3 className="text-sm font-black text-stone-100 uppercase tracking-tight">
          인구 구성 상세
        </h3>
        <span className="text-[10px] font-black text-stone-500 uppercase tracking-widest">
          demographic_depth
        </span>
      </button>
      {open && (
        <div className="grid grid-cols-3 gap-6 p-6 pt-0">
          <CoreDemographicDonut core={demo?.core_demographic ?? null} />
          <StackedAgeBar groups={demo?.top_3_age_groups ?? []} />
          <WeekdayWeekendBar ratio={demo?.weekday_weekend_ratio} />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: KPI Grid에 spark + bullet 데이터 매핑**

`kpiItems` 배열(line 210 주변) 항목 각각에 `spark`와 `bullet` 추가. 예시 — 유동인구 점수:

```tsx
{
  label: '유동인구 점수',
  value:
    simResult.market_report?.floating_population != null
      ? `${formatScore(simResult.market_report.floating_population)}/100`
      : '—',
  sub: `${winnerDistrict} · 동 기준`,
  bullet: {
    actual: simResult.market_report?.floating_population ?? null,
    target: 70,
    max: 100,
  },
},
```

나머지 3개 KPI도 동일 패턴. 월매출은 `spark: qp.map((q) => q.revenue)` 추가.

- [ ] **Step 5: TS + build 확인**

```bash
npx tsc --noEmit
npx vite build
```

Expected: PASS

- [ ] **Step 6: 커밋**

```bash
git add src/components/SimulationResult/dashboard/tabs/SummaryTab.tsx
git commit -m "feat(dashboard): SummaryTab EntrySignalLight + 인구 구성 Collapsible + KPI bullet/sparkline 통합"
```

---

## Task 14: MarketTab에 Scatter + LegalDistributionBar 통합

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/tabs/MarketTab.tsx`

- [ ] **Step 1: import 추가**

```tsx
import { FlowVsRevenueScatter } from '../charts/FlowVsRevenueScatter';
import { LegalDistributionBar } from '../charts/LegalDistributionBar';
```

- [ ] **Step 2: 기존 IndicatorGrid + DistrictRankings 그리드 다음에 Scatter 섹션 추가**

```tsx
{/* Scatter: 유동인구 vs 매출 상관 */}
<div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8">
  <h4 className="text-sm font-black text-stone-100 mb-6 flex items-center gap-2 uppercase tracking-tight">
    유동인구 × 매출 상관 (16 동)
  </h4>
  <FlowVsRevenueScatter
    rankings={simResult.district_rankings ?? []}
    winnerDistrict={simResult.winner_district}
  />
</div>
```

- [ ] **Step 3: InsightsGrid(legalOnly) 상단에 LegalDistributionBar 삽입**

기존 `<InsightsGrid simResult={simResult} legalOnly />` 전에:

```tsx
<div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-6 mb-4">
  <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest mb-3">
    법률 리스크 등급 분포
  </h4>
  <LegalDistributionBar risks={simResult.legal_risks} />
</div>
```

- [ ] **Step 4: TS + build 확인**

```bash
npx tsc --noEmit
npx vite build
```

Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/components/SimulationResult/dashboard/tabs/MarketTab.tsx
git commit -m "feat(dashboard): MarketTab Scatter + LegalDistributionBar 통합"
```

---

## Task 15: InsightTab에 AgentConfidenceRadar 통합

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/tabs/InsightTab.tsx`

- [ ] **Step 1: import 추가**

```tsx
import { AgentConfidenceRadar } from '../charts/AgentConfidenceRadar';
```

- [ ] **Step 2: 기존 grid 위에 Radar overview 섹션 추가**

`InsightTab`의 return 내, 기존 제목 바로 아래 (grid-cols-4 위):

```tsx
<div className="bg-stone-900/40 border border-stone-800/60 rounded-3xl p-8 mb-6">
  <h4 className="text-xs font-black text-stone-500 uppercase tracking-widest mb-4">
    8 에이전트 신뢰도 Overview
  </h4>
  <AgentConfidenceRadar attributions={simResult.agent_attributions ?? []} />
</div>
```

- [ ] **Step 3: TS + build 확인**

```bash
npx tsc --noEmit
npx vite build
```

Expected: PASS

- [ ] **Step 4: 커밋**

```bash
git add src/components/SimulationResult/dashboard/tabs/InsightTab.tsx
git commit -m "feat(dashboard): InsightTab AgentConfidenceRadar overview 추가"
```

---

## Task 16: Track B forward-compat 분기 심기

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/components/SimulationResult/QuarterlyProjectionChart.tsx`
- Modify: `frontend/src/components/SimulationResult/dashboard/tabs/SummaryTab.tsx`

Track B #106 / #107 머지 시 프론트 코드 변경 없이 자동 활성화되도록 분기 코드만 미리 심어둠.

- [ ] **Step 1: 타입 확장 (optional 필드)**

`types/index.ts`의 `QuarterlyProjection`:

```tsx
export interface QuarterlyProjection {
  quarter: number;
  revenue: number;
  cumulative_profit: number;
  confidence_lower: number;
  confidence_upper: number;
  // Track B #107 — 백엔드 확장 시 자동 활성화
  ci_80_lower?: number | null;
  ci_80_upper?: number | null;
  ci_95_lower?: number | null;
  ci_95_upper?: number | null;
}
```

`types/index.ts`의 `DemographicReport`:

```tsx
export interface DemographicReport {
  core_demographic: { age: string; gender: string; share: number };
  top_3_age_groups: { age_group: string; share: number }[];
  peak_consumption_hours: string[];
  weekday_weekend_ratio: number;
  resident_visitor_ratio: number | null;
  area_income_level: string;
  population_trend: string;
  elderly_ratio: number | null;
  brand_target_match_score: number | null;
  match_rationale: string | null;
  narrative: string;
  // Track B #106 — 백엔드 확장 시 자동 활성화
  peak_hour_matrix?: number[][] | null; // [7][24]
}
```

- [ ] **Step 2: QuarterlyProjectionChart에 2단계 밴드 분기 추가**

기존 단일 Area 밴드 로직 위에 분기:

```tsx
// 기존: <Area dataKey="confidence_upper" ... /> / <Area dataKey="confidence_lower" ... />
// 교체: ci_95_* 있으면 2단계, 없으면 기존

const hasCI95 = data.some((d) => d.ci_95_upper != null && d.ci_95_lower != null);

{hasCI95 ? (
  <>
    {/* 95% 신뢰 밴드 (연한) */}
    <Area
      type="monotone"
      dataKey="ci_95_upper"
      stroke="none"
      fill="#818cf8"
      fillOpacity={0.08}
      stackId="ci95u"
      isAnimationActive={false}
    />
    <Area
      type="monotone"
      dataKey="ci_95_lower"
      stroke="none"
      fill="#0C0B0A"
      fillOpacity={1}
      stackId="ci95l"
      isAnimationActive={false}
    />
    {/* 80% 신뢰 밴드 (진한) */}
    <Area
      type="monotone"
      dataKey="ci_80_upper"
      stroke="none"
      fill="#818cf8"
      fillOpacity={0.22}
      isAnimationActive={false}
    />
    <Area
      type="monotone"
      dataKey="ci_80_lower"
      stroke="none"
      fill="#0C0B0A"
      fillOpacity={1}
      isAnimationActive={false}
    />
  </>
) : (
  // 기존 단일 밴드 fallback (confidence_lower/upper)
  <>
    <Area
      type="monotone"
      dataKey="confidence_upper"
      stroke="none"
      fill="#818cf8"
      fillOpacity={0.2}
      isAnimationActive={false}
    />
    <Area
      type="monotone"
      dataKey="confidence_lower"
      stroke="none"
      fill="#0C0B0A"
      fillOpacity={1}
      isAnimationActive={false}
    />
  </>
)}
```

주: Area로 밴드 표현 시 Recharts 패턴은 upper→lower 덮어쓰기. 정확한 컬러 블렌딩은 구현 중 미세 조정.

- [ ] **Step 3: SummaryTab에 Calendar Heatmap 자동 활성화 스텁**

`DemographicCompositionSection` (Task 13에서 추가) 그리드를 3 → 4 열로 확장하고 자동 활성화:

```tsx
const hasPeakMatrix = Array.isArray(demo?.peak_hour_matrix)
  && demo.peak_hour_matrix.length === 7;

// grid-cols-3 → grid-cols-4 (hasPeakMatrix일 때만)
<div className={`grid gap-6 p-6 pt-0 ${hasPeakMatrix ? 'grid-cols-4' : 'grid-cols-3'}`}>
  <CoreDemographicDonut core={demo?.core_demographic ?? null} />
  <StackedAgeBar groups={demo?.top_3_age_groups ?? []} />
  <WeekdayWeekendBar ratio={demo?.weekday_weekend_ratio} />
  {hasPeakMatrix && (
    <div className="flex h-[140px] items-center justify-center rounded-2xl border border-dashed border-stone-800 text-stone-500 text-xs">
      Calendar Heatmap — Track B #106 구현 대기
    </div>
  )}
</div>
```

주: Calendar Heatmap 실제 구현은 #106 머지 후 별도 task. 현재는 필드 수신 확인 placeholder.

- [ ] **Step 4: TS + build 확인**

```bash
npx tsc --noEmit
npx vite build
```

Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/types/index.ts src/components/SimulationResult/QuarterlyProjectionChart.tsx src/components/SimulationResult/dashboard/tabs/SummaryTab.tsx
git commit -m "feat(dashboard): Track B #106 #107 forward-compat 분기 (자동 활성화)"
```

---

## Task 17: Final Verification

**Files:** 전체

- [ ] **Step 1: 전체 테스트 실행**

```bash
npx vitest run
```

Expected: 모든 테스트 PASS (신규 10개 차트 + 기존 AgentCard/LegalDrawer/simulationStore)

- [ ] **Step 2: TS 컴파일 검증**

```bash
npx tsc --noEmit
```

Expected: exit 0

- [ ] **Step 3: Production 빌드**

```bash
npx vite build
```

Expected: `built in ~N.Ns` (chunk size 경고만 허용)

- [ ] **Step 4: Prettier 포맷**

```bash
npx prettier --write src/components/SimulationResult/dashboard src/types/index.ts src/components/SimulationResult/QuarterlyProjectionChart.tsx
```

Expected: 포맷 적용 리스트 출력

- [ ] **Step 5: ESLint baseline 비교**

```bash
npx eslint src/components/SimulationResult/dashboard 2>&1 | tail -15
```

Expected: 신규 위반 0 (기존 `as Record<string, any>` 3건은 spec 허용 — 프로젝트 패턴). 새로 추가된 `any` 없어야 함.

- [ ] **Step 6: dev convention 검증**

```bash
grep -rn "노동법\|safe\|caution\|danger" src/components/SimulationResult/dashboard/charts/LegalDistributionBar.tsx
```

Expected: "노동법" 없음. 라벨은 "필수이행/확인필요/참고사항"만 사용.

- [ ] **Step 7: 커밋**

포맷/자잘한 조정이 있으면:

```bash
git add -u
git commit -m "chore(dashboard): prettier + final verification"
```

없으면 skip.

---

## Self-Review 결과

**Spec coverage:**

- [x] §4 Summary 7개 차트: Task 1 (#4 Sparkline) + Task 2 (#3 Bullet) + Task 3 (KpiMiniGrid 통합) + Task 4 (#10 EntrySignalLight) + Task 5 (#5 Donut) + Task 6 (#6 WeekdayWeekend) + Task 7 (#2 StackedAge) + Task 13 (SummaryTab 통합)
- [x] §4 Market 2개: Task 9 (#8 Scatter) + Task 10 (#11 LegalDistribution) + Task 14 (MarketTab 통합)
- [x] §4 Forecast 2개: Task 11 (#1 Waterfall 테스트) + Task 12 (ForecastTab 통합, Closure Bullet 포함)
- [x] §4 Insight 1개: Task 8 (#7 Radar) + Task 15 (InsightTab 통합)
- [x] §5 차트별 구현 가이드: 각 Task에서 컴포넌트 경로·소스·배치 명시
- [x] §6 Empty State 정책: 각 차트에 null/빈 배열 분기 + placeholder 구현
- [x] §7 Track B forward-compat: Task 16
- [x] §8 디자인 시스템: Indigo #818cf8 메인 색상 모든 차트에 반영
- [x] §9 신규 10 + 수정 5 파일: Task 1-10 신규, Task 3 (KpiMiniGrid) + Task 12-16 수정
- [x] §10 완료 조건: Task 17 final verification

**Placeholder scan:** TBD/TODO/"implement later"/"similar to Task N" 패턴 없음 ✓

**Type consistency:**
- `WaterfallStep`: Task 11 (export 추가) → Task 12에서 `import { type WaterfallStep }` 사용 ✓
- `BulletChart` props: Task 2 (actual: number | null, target?, max?, label?, thresholds?) → Task 3 (KpiItem.bullet slot) + Task 12 (ClosureRiskPanel)에서 동일 사용 ✓
- `buildRadarData`: Task 8에서 export + AgentConfidenceRadar 내부 호출 ✓
- `countByLevel` return: Task 10 `LevelCounts { high, medium, low, fallback }` → 컴포넌트 내부 sole consumer ✓
- `LegalRisk.is_fallback`: dev에서 이미 `types/index.ts`에 추가된 optional 필드 (merge 완료) → Task 10 사용 ✓

**Scope check:** 단일 PR 가능 범위 (17 task, 각 ~5분 step). 브랜치 `feature/demographic-depth-agent` 단일 유지, 다커밋 (메모리 관례).

---

## 실행 옵션

Plan 저장 완료. 두 가지 실행 옵션:

1. **Subagent-Driven (recommended)** — 각 task마다 새 subagent 디스패치, task 사이 review, 빠른 반복
2. **Inline Execution** — 현 세션에서 executing-plans 스킬로 순차 실행, 체크포인트 review
