# Phase 2 영역 ② 시뮬레이터 보고

영역: `frontend/src/components/SimulationResult/**` + `frontend/src/components/simulation/**` (test 파일 제외).

## 통계
- 치환 hex 인스턴스: 약 90건 (Recharts props 60+, Tailwind arbitrary 22, inline style 8)
- 영향 파일: 7개 (이번 세션에서 직접 수정)
- dark: prefix 폐기: 0 (영역 내 `dark:` prefix 없음)
- unmapped (보고): 3 cluster — MetricCharts.tsx, MarketMap.tsx (대거), 일부 zinc 변형

## 사전 상태 메모
탐색 시점 기준으로 `dashboard/charts/**` 및 `dashboard/tabs/**` 의 다수 파일이 이미 다른 작업으로
시맨틱 토큰화가 적용된 상태였습니다 (예: ClosureRateHistoryChart, BepCumulativeProfitChart,
CannibalizationDistanceChart, FlowVsRevenueScatter, AgentConfidenceRadar, ScenariosComparisonChart,
WaterfallChart, WeekdayWeekendBar, StackedAgeBar, CoreDemographicDonut, Sparkline (dashboard),
HubCard, MarketTab, AbmTab, DecisionCard 등 전부 hex zero). 이번 영역 ②에서 새로 손댄 파일은
실제로 hex 가 남아있던 7건입니다.

## 파일별 변경 요약

### 본 작업에서 수정한 파일

- `src/components/SimulationResult/shared/Sparkline.tsx`
  - 기본 prop `color = '#f59e0b'` → `'var(--warning)'` (1건)

- `src/components/SimulationResult/ShapChart.tsx` (15건)
  - DIRECTION_COLOR: `#3B82F6/#EF4444/#94A3B8` → `var(--success)/var(--danger)/var(--muted-foreground)` (rule §10 SHAP semantics — positive=success, negative=danger)
  - Recharts axis tick / grid / tooltip / legend → `var(--muted-foreground)`/`var(--border)`/`var(--card)` (§12)
  - Tailwind `text-[#9ca3af]`, `bg-[#1e1b18]`, `border-[#3a3633]`, `text-[#f97316]`, `text-[#d1d5db]` → 시맨틱 토큰 (§1, §2, §3, §7)

- `src/components/SimulationResult/QuarterlyProjectionChart.tsx` (16건)
  - `COLORS` 상수: `['#818cf8','#22d3ee','#fbbf24','#fb7185']` → `['var(--chart-1)','var(--chart-2)','var(--chart-3)','var(--chart-4)']` (§6)
  - CartesianGrid stroke / XAxis · YAxis tick fill / Tooltip → §12 토큰
  - CI Area `fill="#818cf8"` (4×) → `fill="var(--chart-1)"`
  - activeDot `stroke="#fff"` → `stroke="var(--card)"`
  - BEP ReferenceLine `#10B981` → `var(--success)` (§7)

- `src/components/SimulationResult/MetricCharts.tsx` (3건 부분 변환)
  - GRADE_COLORS: `EXCELLENT #10B981` → `var(--success)`, `NORMAL #EAB308` → `var(--warning)`, `RISKY #EF4444` → `var(--danger)`
  - **Unmapped 잔존**: `#3B82F6` (GOOD), `#f1f5f9` (PolarGrid), `#94a3b8` (PolarAngleAxis) — 아래 Unmapped 표 참조

- `src/components/SimulationResult/sections/IndicatorGrid.tsx` (5건)
  - PolarGrid `#44403c` → `var(--border)`, PolarAngleAxis tick `#a8a29e` → `var(--muted-foreground)`
  - Radar stroke/fill `#6366f1` → `var(--primary)` (§4)
  - Tooltip 인라인 style: `rgba(24,24,27,0.95)`/`#3f3f46`/`#e4e4e7` → `var(--card)`/`var(--border)`/`var(--card-foreground)` (functional role mapping 적용)

- `src/components/SimulationResult/sections/MapSection.tsx` (2건)
  - 인라인 style `borderBottom: '11px/9px solid #ef4444'` → `var(--danger)`

- `src/components/simulation/SpotterAgentWorkflow.tsx` (17건)
  - Tailwind 임의값 일괄: `text-[#e2e8f0]`/`text-[#9ca3af]`/`text-[#d1d5db]`/`text-[#6b7280]` → `text-foreground`/`text-muted-foreground` (§2)
  - `bg-[#2c2825]`/`bg-[#1e1b18]` → `bg-card` (§1)
  - `bg-[#3a3633]` (status pill 배경) → `bg-muted`
  - `border-[#3a3633]`/`border-[#404040]` → `border-border` (§3)
  - `text-[#404040]` (Circle 아이콘) → `text-muted-foreground`
  - `text-[#818cf8]`/`bg-[#818cf8]/10` → `text-primary`/`bg-primary/10` (§4)
  - `bg-emerald-500/10 text-emerald-500` → `bg-success/10 text-success` (§7)
  - `decoration-[#3a3633]` → `decoration-border`

### 영역 내였지만 수정 보류한 파일

- `src/components/SimulationResult/sections/MarketMap.tsx` — **전체 보류**.
  근거: (1) Kakao Maps native API config (`strokeColor`, `fillColor`) 가 CSS 변수 미지원 가능성,
  (2) HTML 템플릿 문자열 안의 zinc 계열 (`#71717a`, `#3f3f46`, `#e4e4e7`, `#a1a1aa`, `#f4f4f5`, `#27272a`, `#52525b`) 다수가 룰표 ✕.
  rule §0.5 "본인 영역 디렉토리 밖 파일은 수정 금지" 와 §15 "표에 없는 hex 발견 → 변환 중단" 양쪽 따라
  스코프 외 결정 필요 (강민 / 영역 ⑤ 라이브러리 담당과 협의).

## Unmapped (강민 결정 필요)

| file:line | hex | 추정 맥락 |
|---|---|---|
| MetricCharts.tsx:25 | `#3B82F6` | GRADE_COLORS.GOOD (Blue-500). 룰 §4 indigo 패밀리에 미포함. `var(--primary)`/`var(--chart-2)`? |
| MetricCharts.tsx:162 | `#f1f5f9` | PolarGrid stroke (slate-100, light radar grid). `var(--border)` 후보 |
| MetricCharts.tsx:165 | `#94a3b8` | PolarAngleAxis tick (slate-400). `var(--muted-foreground)` 후보 |
| MarketMap.tsx:99 | `#10b981` | rankingColor 반환 (score≥75 = success) — Kakao Maps API config 라 CSS var 미사용 |
| MarketMap.tsx:100 | `#f59e0b` | rankingColor (warning) — Kakao Maps API |
| MarketMap.tsx:101 | `#6b7280` | rankingColor (default muted) — Kakao Maps API |
| MarketMap.tsx:138 | `#f59e0b`, `#ffffff` | HTML template — pulse target overlay |
| MarketMap.tsx:157 | `#f59e0b`, `#71717a` | competitor info accent — `#71717a` (zinc-500) 미정의 |
| MarketMap.tsx:160 | `#e4e4e7`, `#3f3f46` | tooltip 텍스트/보더 (zinc-200/zinc-700) — 룰 ✕ |
| MarketMap.tsx:165–168 | `#a1a1aa`, `#f4f4f5`, `#fbbf24` | tooltip 보조/내부외부 표시 |
| MarketMap.tsx:218,221,258,284 | `#f59e0b`, `#27272a`, `#52525b` | Circle/Polygon stroke·fillColor (Kakao Maps API native) |
| MarketMap.tsx:310,311 | `#ef4444` | dot.style.cssText (DOM 인라인 — 변환 가능하지만 일관성 위해 보류) |

## 처리하지 않은 false-match (참고)

- `dashboard/tabs/DemographicTab.tsx:83` — "Track B #106 구현 대기" 텍스트의 `#106` 은 hex 아님

## tsc / prettier 결과

- `npx prettier --write src/components/SimulationResult/ src/components/simulation/`: PASS (포맷 차이만 적용)
- `npx tsc --noEmit`: PASS (영역 변경 후 타입 에러 없음)
