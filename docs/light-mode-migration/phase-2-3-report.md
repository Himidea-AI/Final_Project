# Phase 2 영역 ③ 대시보드 보고

## 영역
- `frontend/src/components/dashboard/**`
- `frontend/src/pages/dashboard/**`
- `frontend/src/components/SimulationResult/dashboard/**`

## 통계
- 치환 hex 인스턴스: **약 110+** (DashboardPanelView 단독 약 60건 + chart 12파일 50+건)
- 영향 파일: **12** (.tsx 만)
- `dark:` prefix 폐기: **0** (이 영역에는 dark: 가 없었음 — 전부 인라인 hex / arbitrary value 였음)
- unmapped (보고): **0**

## 노란 띠 핵심 fix (룰 §8) — 영역 ② 위임
- `InsightsGrid.tsx:33` 의 `LEVEL_CLS.MEDIUM.strip = 'bg-yellow-500'` 와
  `InsightsGrid.tsx:192` 안전군 행 노란 띠는 실제로는
  `frontend/src/components/SimulationResult/sections/InsightsGrid.tsx` 에 위치.
- 영역 정의 ("SimulationResult/dashboard/**") 의 `sections/` 와 다름 → **영역 ② 가 우선** 규칙에 따라 손대지 않음.
- 영역 ② subagent 가 1줄 fix (`bg-yellow-500` → `bg-primary`) 수행 필요.

## 파일별 변경 요약

### components/dashboard/ (1)
- `DashboardPanelView.tsx`: 약 60건
  - `bg-[#2c2825]` → `bg-card` (다수)
  - `border-[#3a3633]` → `border-border` (다수)
  - `text-[#9ca3af]` → `text-muted-foreground` (다수)
  - `text-[#818cf8]` / `bg-[#818cf8]` / `border-[#818cf8]` → `text-primary` / `bg-primary` / `border-primary`
  - `text-[#e2e8f0]` → `text-foreground`
  - `text-[#d1d5db]` → `text-muted-foreground`
  - `bg-[#1e1b18]` → `bg-card`
  - `bg-[#3a3633]` → `bg-muted`, `hover:bg-[#3a3633]/50` → `hover:bg-muted/50`
  - `bg-[#818cf8]/[0.06]` → `bg-primary/[0.06]`, `bg-[#818cf8]/[0.05]` → `bg-primary/[0.05]`, `bg-[#818cf8]/10` → `bg-primary/10`
  - SVG inline: `#10b981` → `var(--success)`, `#f43f5e` → `var(--danger)`, `#818cf8` → `var(--primary)`, `#3a3633` → `var(--border)`, `#9ca3af` → `var(--muted-foreground)`, `#e2e8f0` → `var(--foreground)`

### pages/dashboard/ (3)
- `DashboardAbmPage.tsx` / `DashboardAnalyzePage.tsx` / `DashboardPredictPage.tsx`: **변경 없음** (`text-stone-*` 만 사용 — Tailwind named class, hex 없음)

### components/SimulationResult/dashboard/ (chart 11종 + shared/tab 4종)

#### Charts (룰 §12 axis/grid/tooltip 토큰화)
- `ClosureRateHistoryChart.tsx`: 12건 — 그리드/축/툴팁 + safe/danger ReferenceLine (`#22c55e` → `var(--success)`, `#ef4444` → `var(--danger)`)
- `CannibalizationDistanceChart.tsx`: 11건 — **5색 gradient (룰 §9)**: `['#ef4444','#f59e0b','#eab308','#84cc16','#22c55e']` → `[--danger, --warning, --decor-yellow, --decor-cyan, --success]` + axis/grid/tooltip
- `CoreDemographicDonut.tsx`: 2건 — `#818cf8` → `var(--primary)`, `#292524` → `var(--border)`
- `AgentConfidenceRadar.tsx`: 4건 — PolarGrid/Angle/Radius axis + Radar fill 토큰화
- `BepCumulativeProfitChart.tsx`: 12건 — **4동 비교 4색 (룰 §6)**: `['#818cf8','#22d3ee','#fbbf24','#fb7185']` → `[--chart-1, --chart-2, --chart-3, --chart-4]` + axis/grid/tooltip + amber 배지 → warning + BEP ReferenceLine `#10b981` → `var(--success)`
- `ScenariosComparisonChart.tsx`: 13건 — 시나리오 3색 (룰 §5): optimistic `#10b981` → `var(--success)`, base `#818cf8` → `var(--primary)`, pessimistic `#fb7185` → `var(--danger)` + axis/grid/tooltip
- `WaterfallChart.tsx`: 8건 — **SHAP 4색 (룰 §10)**: COLOR_BASE/FINAL/POS/NEG → muted-foreground/primary/success/danger + axis/grid/tooltip
- `Sparkline.tsx`: 3건 — TREND_COLOR up/down/flat → success/danger/muted-foreground
- `StackedAgeBar.tsx`: 1건 (배열) — indigo gradient `['#818cf8','#a5b4fc','#c7d2fe','#a8a29e']` → primary + opacity 변형 (color-mix) + muted-foreground
- `WeekdayWeekendBar.tsx`: 3건 — 주중 `#818cf8` → `var(--primary)`, 주말 `#a8a29e` → `var(--muted-foreground)`, axis tick
- `FlowVsRevenueScatter.tsx`: 9건 — winner highlight 토큰화 + axis/label/grid/cursor

#### Shared / Tabs / Hub
- `HubCard.tsx`: 6건 — 3 conic-gradient laser hex → CSS var (indigo→primary, cyan→chart-2, amber→warning), `ring-offset-[#1e1b18]` → `ring-offset-card`
- `DecisionCard.tsx`: 2건 — `bg-[#141210]` → `bg-card`, `border-[#141210]` → `border-card`
- `tabs/MarketTab.tsx`: 2건 — `bg-[#111113]` → `bg-card`, `bg-[#141210]/60` → `bg-card/60`
- `tabs/AbmTab.tsx`: 3건 — `bg-[#171717]/90` → `bg-muted/90`, `border-[#3a3633]` → `border-border`, `bg-[#818cf8]` → `bg-primary`

## 의도적 보존 (룰 §14)
- `bg-stone-*`, `text-stone-*`, `border-stone-*` Tailwind named class — System A 의 라이트 surface 와 일관 (Phase 0-D 결정)
- `text-amber-*` / `bg-amber-500/*` 등 일부 amber 클래스 — 영역 ② 의 `yellow-inventory-B.md` 가 별도 결정 항목으로 명시 (mock 배지/risk badge 등). 본 영역에서 명백히 차트 표면이거나 hex 인 것만 변환.
- `rgba(...)` shadow / fill — 룰에 명시 없는 case-by-case decoration glow → 보존
- `#fff` (1건, BepCumulativeProfitChart `activeDot stroke`) → `var(--card)` 로 일관 처리

## Unmapped (강민 결정 필요)
없음. 표 1~14 안에서 모두 매핑 완료.

## tsc / prettier 결과
- `npx prettier --write src/components/dashboard/ src/pages/dashboard/ src/components/SimulationResult/dashboard/` → **PASS** (15 파일 reformat, 나머지 unchanged)
- `npx tsc --noEmit` → **PASS** (출력 0줄, exit 0)

## 검증 후 잔존 hex
```
$ rg '#[0-9a-fA-F]{3,8}' src/components/dashboard src/pages/dashboard src/components/SimulationResult/dashboard
DemographicTab.tsx:83:  Calendar Heatmap — Track B #106 구현 대기   ← 코멘트 내 티켓번호, 색상 아님
```
실 hex 색상은 0건.
