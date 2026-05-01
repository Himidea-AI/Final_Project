# Phase 8 — Legacy Dashboard Dead Code Removal

## 요약

`frontend/src/App.tsx` 안에 보존되어 있던 옛 비교모드 dashboard JSX (1,800줄+) 와
연관 dead state/handler/import 일괄 제거.

| 지표              | 전        | 후        | Δ            |
| ----------------- | --------- | --------- | ------------ |
| App.tsx 라인 수   | 4,827     | 2,743     | **−2,084**   |
| TS 컴파일 에러    | 0         | 0         | =            |
| ESLint 문제       | 14 (11E+3W) | 8 (5E+3W) | **−6 errors** |
| Vite prod 빌드    | OK        | OK        | =            |

## 제거된 dead 분기

### 분기 1 — small toggle (구 viewMode toggle 박스)

라인 1961-1999 (전 4,827줄 기준)

```tsx
{!isSplitMode && viewMode === 'legacy' && (
  <div className="flex bg-card rounded-lg border border-border p-1 shadow-inner">
    {/* 데이터 뷰 / AI 에이전트 맵 / ABM 시뮬 맵 토글 */}
  </div>
)}
```

→ 통째 삭제 (39줄).

### 분기 2 — 옛 dashboard JSX 본체

라인 2130-3988 (전 4,827줄 기준, 약 1,800줄)

```tsx
{!isSplitMode && viewMode === 'legacy' && (
  <>
    {/* AI Verdict 신호등 배너 + 4 Stats Cards + 차트 + 테이블 + AgentMap + AbmPersonaMap */}
  </>
)}
```

→ 라인 2124-2129 의 보존용 주석까지 포함하여 통째 삭제 (1,866줄).

이 블록은 `viewMode === 'legacy'` 가 항상 false 이므로 절대 렌더되지 않음.
`/dashboard` 라우트 분리 (Phase H4) 이후 routing 으로 대체됨.

## 제거된 dead state / handler

| 식별자 | 종류 | 사용처 |
| --- | --- | --- |
| `viewMode` | useState | dead 분기 분기 조건만 |
| `dashboardMode` / `setDashboardMode` | useState | 분기 1 + 분기 2 내부 |
| `chartView` / `setChartView` | useState | 분기 2 내 차트 토글 |
| `tableView` / `setTableView` | useState | 분기 2 내 테이블 토글 |
| `expandedRow` / `setExpandedRow` | useState | 분기 2 내 행 펼침 |
| `handleSort` | useCallback | 분기 2 내 SortHeader |
| `handleTableViewChange` | useCallback | 분기 2 내 toggle |
| `tableDensity` / `setTableDensity` | useState | 분기 2 내 density toggle |
| `popLoading` / `setPopLoading` | useState | 분기 2 내 loading 표시 |
| `abmResult` / `setAbmResult` | useState | 분기 2 내 ABM 시뮬 |
| `abmLoading` / `setAbmLoading` | useState | 분기 2 내 ABM 시뮬 |
| `abmError` / `setAbmError` | useState | 분기 2 내 ABM 시뮬 |
| `abmFocusSpot` / `setAbmFocusSpot` | useState | 분기 2 내 지도 포커스 |
| `monthlyChartData` | derived | 분기 2 내 차트 |
| `hasMarketReport`, `radarValues`, `radarVertices`, `radarPointsStr`, `RADAR_LABELS`, `_safeNum` | derived | 분기 2 내 레이더 차트 |
| `RechartsDarkTooltip` (function) | local fn | 분기 2 내 차트 툴팁 |

`sortKey` / `sortDir` 은 PDF/Excel 내보내기에서 `sortRows()` 호출 시 인자로 쓰이므로
정적 상수 (`null` / `'asc'`) 로 변환하여 보존. setter 미호출 → 정렬은 입력 순서대로.

## 제거된 dead import

```diff
-import { QuarterlyProjectionChart } from '...';
-import { ShapChart } from '...';
-import { StatCard, SortHeader, TableRow, InsightCard } from '.../DashboardPanelView';
-import AgentMapVisualizer from '...';
-import AbmPersonaMap from '...';
-import { AreaChart, Area, XAxis, Tooltip as RechartsTooltipWrapper, ResponsiveContainer } from 'recharts';
-import { motion } from 'framer-motion';

  // lucide-react 에서 제거된 16종:
- Activity, Users, TrendingUp, ShieldAlert, CheckCircle2,
- BarChart3, Crosshair, AlertTriangle, Scale, Rows3,
- AlignJustify, List, Network, BarChartBig, Map as MapIcon, Lightbulb, ClipboardList
```

## 검증 결과

- `npx tsc --noEmit` → **PASS** (no errors)
- `npx prettier --write src/App.tsx` → unchanged (이미 포맷 OK)
- `npx eslint src/App.tsx` → 8 problems (5 errors + 3 warnings),
  baseline 14 → 후 8 (감소 6, 모두 dead 분기 안의 `no-explicit-any`)
  - 잔여 5 errors 는 *현재 사용 중* 인 코드의 `any` 타입 — 이번 cycle 의 범위 외
- `npx vite build` → **PASS**, dist/index-*.js 704 kB (이전 533 kB +α — Phase B2/D 작업 누적)

## 안전 검증

- `viewMode === 'integrated'` 분기는 손대지 않음 — TabbedDashboard 단일 뷰 유지.
- 라우팅 / 헤더 / `useEffect` / `runSim` 등 *살아있는* 코드 변경 X.
- `sortedCannRows`, `sortedNeighborhoodRows`, `dynamicCannRows`, `dynamicNeighborhoodRows`,
  `_competitorSamples` 는 PDF/Excel export 와 `IntegratedReport` 에서 여전히 소비되므로 보존.
- `popData`, `setPopData`, `useEffect(fetchPop)` 도 보존 (다른 곳 사용 중).

## 후속 권고

- 잔여 ESLint `no-explicit-any` 5건은 별도 cycle 에서 타입 좁히기 (특히 `popData: any`,
  `abm` 관련 변수 — 이미 제거되어 더 줄어듦. 남은 것은 `_competitorSamples`, `simResult` 외부 응답).
- App.tsx 2,743줄도 여전히 무거움 — `SimulatorDashboard` 본체 추출 시 1,500줄 미만 가능.
