# Phase 4 영역 C 보고 — dashboard 명명색 치환

## 통계
- 치환 인스턴스: 약 32 (named class 그룹)
- 영향 파일: 4
- dark: prefix 폐기: 0
- unmapped (보고): 0

## 영역
- `frontend/src/components/dashboard/DashboardPanelView.tsx`
- `frontend/src/pages/dashboard/DashboardAbmPage.tsx`
- `frontend/src/pages/dashboard/DashboardAnalyzePage.tsx`
- `frontend/src/pages/dashboard/DashboardPredictPage.tsx`

(영역 B 책임 `components/SimulationResult/dashboard/**` 는 손대지 않음.)

## 파일별 변경 요약

### `components/dashboard/DashboardPanelView.tsx`
- `text-indigo-400` → `text-primary` (4건: hover icon, hover row icon, insight TrendingUp/Users)
- `text-emerald-500` / `text-rose-500` → `text-success` / `text-danger` (StatCard trend)
- `text-emerald-400` / `text-amber-400` / `text-rose-400` → `text-success` / `text-warning` / `text-danger` (위험등급 라벨, 인사이트 Scale 아이콘)
- `bg-emerald-500/10 text-emerald-500 border-emerald-500/20` → `bg-success/10 text-success border-success/20` (Safe status)
- `bg-indigo-500/10 text-indigo-400 border-indigo-500/20` → `bg-primary/10 text-primary border-primary/20` (Warning, 개월 status — 2건)
- `bg-rose-500` / `bg-emerald-500` → `bg-danger` / `bg-success` (severity dots)
- `hover:bg-rose-500/10 hover:text-rose-400` → `hover:bg-danger/10 hover:text-danger` (ThumbsDown)
- 4-패널 colorMap: amber/emerald/sky/rose-500 → warning/success/primary/danger (의미적 §7 매핑)
- 4-패널 badgeColorMap: 동일 매핑 (4건 cls)
- accentColor fallback `'text-amber-500'` → `'text-warning'`
- winnerWrapCls `ring-indigo-500/30` → `ring-primary/30`
- winnerBadgeCls `bg-indigo-500/20 text-indigo-400 border-indigo-500/30` → `bg-primary/20 text-primary border-primary/30`
- isWinner 외곽선 `border-indigo-500/40` → `border-primary/40`
- MapPin winner `text-indigo-400` → `text-primary`
- `text-white` 8건 → `text-foreground` (StatCard 값, TableRow col3, 패널 디스트릭트 라벨, 4 stat 값, radar 헤더, AI 인사이트 헤더)

### `pages/dashboard/{Abm,Analyze,Predict}Page.tsx` (3 파일 동일 패턴)
- Hub 백 버튼 `text-stone-500 hover:text-stone-100 ring-stone-400` → `text-muted-foreground hover:text-foreground ring-border`

## Unmapped (강민 결정 필요)
없음. cyan/violet/purple/fuchsia 인스턴스 영역 내 미발견.

## 보존 항목 (의도)
- Mock 색 hex `rgba(129,140,248,0.2)` `rgba(244,63,94,0.2)` `rgba(16,185,129,0.15)` `rgba(99,102,241,0.15)` 형태의 인라인 SVG fill/shadow 는 Phase 2 영역의 hex 책임이라 그대로 둠 (named class 변환 범위 외).
- `var(--success)` `var(--danger)` `var(--primary)` `var(--border)` `var(--muted-foreground)` `var(--foreground)` 등 이미 시맨틱 변수로 적힌 SVG props 는 그대로 둠.

## tsc / prettier 결과
- `npx prettier --write src/components/dashboard/ src/pages/dashboard/` — PASS (DashboardPanelView.tsx 1건 reformat, 3 페이지 unchanged)
- `npx tsc --noEmit` — PASS (출력 없음, 에러 없음)

## 검증 grep
4 파일 전체에서 named tone class (`stone|zinc|gray|slate|neutral|indigo|sky|blue|rose|red|pink|emerald|green|amber|yellow|orange|cyan|violet|purple|fuchsia|teal-(50|100|...|950)`) 및 `text-white`/`bg-white`/`text-black`/`bg-black` 인스턴스 0건.
