# Phase 4 영역 D 보고 — Nav/공용/랜딩 명명색 치환

## 통계

- 치환 명명색 인스턴스: 약 320건 (예상 입력 기준 — leaf components 79 + SimulationHistory 59 + TokenBurnrate 29 + ui 4 + landing 16 + JoinUs 45 + LoginPage 2 + ManagerDetail 23 + HQCommandCenter 30 + HistoryDashboardView 1 + SimulationHistoryDetail 11 + VacancyStatsPanel 12-violet)
- 영향 파일: 27
- dark: prefix 폐기: 0 (영역 내 dark prefix 없음)
- unmapped (보고): 7 (모두 violet — 같은 파일)

## 파일별 변경 요약

### components/ leaf

- `src/components/AbmPersonaMap.tsx`: 49건 (emerald→success, rose→danger, stone→muted-foreground/foreground/muted, indigo→primary, cyan→primary, violet→primary[border 한 곳])
- `src/components/CommandPalette.tsx`: 3건 (rose→danger)
- `src/components/DetailDrawer.tsx`: 5건 (emerald→success, rose→danger, cyan→primary, indigo gradient→primary)
- `src/components/GlobalNav.tsx`: 11건 (rose→danger, emerald→success)
- `src/components/PersonaCard.tsx`: 16건 (slate-100/200/300→foreground, slate-400/500→muted-foreground, slate-700/800/900→border/muted/card)
- `src/components/VacancyStatsPanel.tsx`: 5건 치환 (emerald→success, rose→danger). violet 7건 unmapped.

### components/SimulationHistory

- `SaveDialog.tsx`: 13건
- `SaveButton.tsx`: 2건
- `HistoryList.tsx`: 6건
- `HistoryCard.tsx`: 16건
- `ActivityDashboard.tsx`: 22건

### components/TokenBurnrate, ui

- `TokenBurnrate/TokenBurnrateSection.tsx`: 29건
- `ui/SectionLabel.tsx`: 4건

### pages/

- `landing/IntroScene.tsx`: 2건 (gray-500/600 → muted-foreground/border)
- `landing/AccordionGallery.tsx`: 6건 (indigo→primary, gray→muted-foreground)
- `landing/ContactPage.tsx`: 4건 (indigo→primary)
- `landing/AboutPage.tsx`: 4건 (indigo→primary)
- `JoinUs/JoinUsPage.tsx`: 3건
- `JoinUs/components/RoleSelectView.tsx`: 4건
- `JoinUs/components/SignupForm.tsx`: 14건
- `JoinUs/components/ManagerSignupForm.tsx`: 24건
- `LoginPage.tsx`: 2건
- `HistoryDashboardView.tsx`: 1건
- `SimulationHistoryDetail.tsx`: 11건
- `ManagerDetail.tsx`: 23건
- `HQCommandCenter.tsx`: 30건

## Unmapped (강민 결정 필요)

| file:line | class | 추정 맥락 |
|---|---|---|
| `src/components/VacancyStatsPanel.tsx:24` | `border-violet-500/30` | vacancy_pse 패널 외곽 — chart-4(Vibrant Purple) 의미 |
| `src/components/VacancyStatsPanel.tsx:25` | `text-violet-300` | 패널 헤더 |
| `src/components/VacancyStatsPanel.tsx:46` | `border-violet-500/30` | 패널 외곽 (loading 분기 외) |
| `src/components/VacancyStatsPanel.tsx:47` | `text-violet-300` | 패널 헤더 |
| `src/components/VacancyStatsPanel.tsx:69` | `text-violet-300` | 분기 방문 강조값 |
| `src/components/VacancyStatsPanel.tsx:74` | `text-violet-300` | 분기 매출 강조값 |
| `src/components/VacancyStatsPanel.tsx:79` | `text-violet-300` | 연 매출 강조값 |

VacancyStatsPanel 의 violet 7건은 conversion-rules §15.4 ("Violet/Purple/Fuchsia → 그대로 두고 unmapped 보고") 에 따라 미치환.
- 추천 매핑: vacancy_pse 패널이 단일 데이터 카테고리 강조이므로 `text-chart-4` (Vibrant Purple) 또는 `text-primary` 통합 중 강민 선택.
- 다른 영역(예: AbmPersonaMap 의 violet-300/violet-500/40 1쌍)은 vacancy fetch 인디케이터 의미라 Phase 4 D 에서 `text-primary border-primary/40`로 통합 매핑함 (룰 §15 단서 "강조 액센트 → text-primary 통합" 적용).

## 처리하지 않은 인스턴스 (영역 외 또는 룰 외)

- `components/SimulationResult/**`, `components/dashboard/**`, `App.tsx`, `pages/dashboard/**`: 영역 외 (다른 subagent 담당)
- `*.test.tsx`: 룰 §14 (스냅샷 영향 회피)
- `components/PDF/HiddenPDFTemplate.tsx`: 룰 §14 (PDF 인쇄용)

## tsc / prettier 결과

- `npx prettier --write` (영역 27 파일): PASS (23 변경, 4 unchanged)
- `npx tsc --noEmit` (전역): PASS (no output, exit 0)
