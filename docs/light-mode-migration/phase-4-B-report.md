# Phase 4 영역 B 보고 — SimulationResult / simulation 명명색 치환

## 통계

- 영향 파일: 13
- 치환 인스턴스 (대표 카테고리 합산): 약 145건
  - stone-* → bg-card / bg-muted / text-foreground / text-muted-foreground / border-border (가장 비중 큼)
  - indigo-* / sky-* / blue-* → primary
  - rose-* / red-* / pink-* → danger
  - emerald-* / green-* → success
  - amber-* / yellow-* / orange-* → warning
  - slate-* / zinc-* / gray-* → 토큰 매핑
  - cyan-* / violet-* / teal-* → primary 또는 의미별 통합
- dark: prefix 폐기: 0 (영역 내 dark: 사용처 없음)
- unmapped (보고): 1 (MetricCharts.tsx GRADE_COLORS.GOOD `#3B82F6`, Phase 2 보고서에 이미 unmapped 로 표시되어 있어 그대로 보존)

## 영역 외 자리 (이번 phase 4-B 범위 밖, 별도 subagent 필요)

원래 우선처리 목록에 포함된 다음 파일은 dashboard/** 디렉토리 소속 → "절대 룰: dashboard/** 별도 subagent" 에 따라 미수정:

- `SimulationResult/dashboard/HubCard.tsx` (Hub 3 카드 다크 잔존 — 별도 subagent)
- `SimulationResult/dashboard/shared/SynthesisSections.tsx` (synthesis 헤더 다크)
- `SimulationResult/dashboard/charts/**` (각종 차트)
- `SimulationResult/dashboard/tabs/**`, `dashboard/sub/**`
  → 모두 dashboard subagent 가 처리해야 함.

`sections/IndicatorGrid.tsx` (radar 검정), `sections/DistrictRankings.tsx` (테이블 다크) 등 영역 안 자리는 모두 본 phase 에서 치환 완료.

## 파일별 변경 요약

- `SimulationResult/MetricCharts.tsx` — gray/blue/red/emerald/amber 명명색 → 토큰
- `SimulationResult/QuarterlyProjectionChart.tsx` — gray-400 / amber-500 mock 배지 → muted-foreground / warning
- `SimulationResult/ReportViewer.tsx` — 라이트 prose 색 (gray/blue) → foreground/muted-foreground/primary, blockquote 배경 indigo-light → primary/10
- `SimulationResult/ShapChart.tsx` — gray-400, yellow-500 mock 배지 → muted-foreground / warning
- `SimulationResult/sections/IndicatorGrid.tsx` — KPI 색칠 시스템 (emerald/amber/rose) + radar 박스 stone → success/warning/danger + bg-card
- `SimulationResult/sections/DistrictRankings.tsx` — 테이블 stone-700/800 + indigo + rose-400 → border-border/bg-card/bg-muted/primary/danger
- `SimulationResult/sections/InsightsGrid.tsx` — LEVEL_CLS (rose/yellow/emerald) + 탭 indigo + 안전군 emerald → semantic 토큰
- `SimulationResult/sections/MapSection.tsx` — 좌상/좌하 패널 stone-700 + indigo-400 → border-border/bg-card/primary
- `SimulationResult/sections/MarketMap.tsx` — error-state stone-700/rose-400 + 로딩 stone-500 → border-border/danger/muted-foreground (Kakao map DOM string 안 hex 는 phase 2 영역, 보존)
- `SimulationResult/shared/AgentCard.tsx` — AGENT_COLORS / KIND_BADGE 9종 + stone 표면 → primary/success/danger/warning + bg-card/muted/border-border
- `SimulationResult/shared/LegalDrawer.tsx` — RISK_BADGE (rose/yellow/green) + drawer stone + indigo article → danger/warning/success + bg-card/foreground/primary
- `SimulationResult/shared/SectionLabel.tsx` — stone-100 / stone-400 → foreground / muted-foreground
- `simulation/SimulationFloatingWidget.tsx` — slate/cyan/amber/rose/red 전체 → bg-card/primary/warning/danger + ring-* 토큰 매핑
- `simulation/SpotterAgentWorkflow.tsx` — text-emerald-500 → text-success (이미 대부분 토큰화 되어 있던 파일)
- `simulation/ToastHost.tsx` — slate/cyan/red 베이스 → bg-card/foreground/muted-foreground/success/danger/primary

(`simulation/BeforeUnloadGuard.tsx` 와 `shared/Sparkline.tsx` 는 명명색 사용 없음.)

## Unmapped (강민 결정 필요)

| file:line | 값 | 추정 맥락 |
|---|---|---|
| `SimulationResult/MetricCharts.tsx:25` | `#3B82F6` (GOOD grade themeColor) | Phase 2-2 에서 이미 unmapped 마킹. 스타일 시스템에 "good but not excellent" 토큰이 없어 보존. blue-500 의 라이트 컨트라스트 자체는 OK 라 라이트 모드 사용에 회귀 위험 없음. |

본 phase 에서 새로 발견된 cyan/purple unmapped 자리는 없음 — 모두 의미 매핑으로 흡수됨 (cyan ring → primary, violet/teal agent 색 → primary/success).

## tsc / prettier 결과

- `npx prettier --write` (영역 파일들): PASS (10 파일 reformat, 5 파일 unchanged)
- `npx tsc --noEmit`: PASS (오류 없음, 빈 출력)

## 회귀 위험

1. **에이전트 카드 색 단조화**: AGENT_COLORS 의 9개 에이전트가 4종 토큰 (primary/success/danger/warning) 으로 압축됨. 본부 영업팀이 시각적으로 에이전트를 구분하던 단서가 줄어듦 — Hub Redesign 이후 에이전트별 식별은 이미 아이콘+카드 헤더 라벨로 보강되어 있어 색만으로 구분 의존도는 낮음.
2. **InsightsGrid LEVEL_CLS.MEDIUM strip**: yellow-500 → primary 띠로 전환 (conversion-rules §8 3px 띠 통일 룰). text 는 warning 유지 — 띠 색과 텍스트 색이 다른 의도적 분리.
3. **dashboard 그룹과의 시각 일관성**: dashboard/** 가 아직 다크 잔존이므로 Hub → 탭 이동 시 sections 영역과 색온도 차이 가능. 다음 dashboard subagent 가 끝나면 완전 통일.
