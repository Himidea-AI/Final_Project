# Phase 6 redo — Hero Editorial 패턴 (워터마크 제거 + opacity modifier 안 쓰기)

작성일: 2026-04-30
작업자: Claude (frontend lead — 강민 위임)
브랜치: `feature/analyze-llm-migration`

## 배경

이전 Phase 6 / 6a 작업 중 PowerShell regex 사고로 git restore 발생. 재작업 시 두 가지 룰 강화:

1. **워터마크 제거**: 좌상단 거대 텍스트 (`text-[14rem→20rem]`) 패턴 폐기 — 시각 노이즈만 크고 정보 가치 0.
2. **opacity modifier on color tokens 금지**: Tailwind v3 의 `bg-chart-4/10`, `text-primary/[0.05]` 같은 패턴이 CSS variable 기반 색 토큰에서 안정 작동 안 함 (검정 fallback 으로 hero 가림 사례 확인). solid 토큰 (`bg-chart-4`, `text-chart-4`, `border-chart-4`) 만 사용 — 알파 modifier 없이.

## 작업 범위

수정 파일 (6개):

- `frontend/src/components/SimulationResult/dashboard/DashboardHub.tsx`
- `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx`
- `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeMarketTab.tsx`
- `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeDemographicTab.tsx`
- `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeLegalTab.tsx`
- `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAgentInsightTab.tsx`

미수정 (절대 룰):
- `App.tsx`, `AnalyzeGroup.tsx`, `TabButton.tsx`
- `MarketTab` / `DemographicTab` / `LegalTab` / `InsightTab` 본문 — wrapper 만 외피화
- `src/reference/figma-crm-kit/**`
- `*.test.tsx`

## 핵심 패턴

### Hero (12-col split — 좌 7 / 우 5)

좌측: Tag 캡슐 (border + small caps) → Hero 빅 타이포 (`text-5xl→6xl tracking-tighter`) → 서브 카피.
우측: 빅넘버 (`text-6xl→7xl text-{accent}`) + 단위 + small caps 라벨 (`h-px w-12 bg-{accent}` 가는 가로 줄 + 텍스트).

좌·우가 다른 col 에 있어 텍스트 겹침 없음. 모바일에서는 stack.

### Magazine column

`relative pl-6` 컨테이너에 `absolute left-0 top-1 bottom-1 w-1 rounded-full bg-{accent}` 띠 — solid color, alpha 없음. Small caps 영문 헤더 + 한국어 큰 헤더 → 기존 컴포넌트 그대로 wrap.

### Bottom emphasis (선택)

`rounded-3xl border border-{accent} p-8` — 배경 X, border 만. AnalyzeAiSummaryTab 의 최종 권고, AnalyzeMarketTab 의 거시·트렌드 환경 자리.

## 탭별 변경 요약

### 1) DashboardHub — `accent` (cream wash) + `chart-4` (winner)

- Hero rounded-3xl `bg-accent` (토큰 자체가 cream — alpha modifier 아님)
- 좌 7: SPOTTER REPORT 배지 + brandName + winnerDistrict (`text-5xl→6xl`) + 서브 카피
- 우 5: winnerScore (`text-6xl→7xl text-chart-4`) + Trophy 아이콘 + 새 시뮬 버튼 + docId/createdAt
- DEEP DIVE 구분선 (small caps + border line) → 기존 3 HubCard 유지

### 2) AnalyzeAiSummaryTab — `chart-4` (Vibrant Purple, AI 톤)

- Hero: AI SYNTHESIS 배지 + winnerDistrict + winnerScore (`/100`)
- Top 3 메달 칩: 1ST=chart-4 / 2ND=chart-3 / 3RD=warning (border solid + Trophy 아이콘 + 동명)
- Magazine column: SYNTHESIS 띠 → 기존 `<SynthesisSections>`
- Bottom emphasis: `border border-chart-4 rounded-3xl p-8` — 최종 권고 (ReactMarkdown)

### 3) AnalyzeMarketTab — `primary` (Deep Blue)

- Hero: MARKET LANDSCAPE 배지 + winnerDistrict + market_report 빅넘버
  - `floating_population` → `accessibility` → `competition_intensity` 폴백 (기존 로직 보존)
  - 라벨: REGIONAL ACTIVITY / ACCESSIBILITY / COMPETITION
- Magazine column: MARKET BREAKDOWN 띠 → 기존 `<MarketTab>`
- Bottom emphasis: 거시·트렌드 환경 (`border border-primary rounded-3xl p-8`) + 전체 해석 모달 버튼 + TrendSparklinesPanel + TrendDriversRisks

### 4) AnalyzeDemographicTab — `chart-3` (Teal Green)

- Hero: DEMOGRAPHIC PROFILE 배지 + `${age} ${mapGender(gender)}` (예 "30대 여성") + share% 빅넘버
  - share 없으면 brand_target_match_score 폴백 (라벨 BRAND MATCH)
  - 둘 다 없으면 헤드라인 "인구 분석 리포트" 폴백 + 빅넘버 '—'
- Magazine column: DEMOGRAPHIC BREAKDOWN 띠 → 기존 `<DemographicTab>`

### 5) AnalyzeLegalTab — `chart-2` (Vivid Red, tone-aware)

- Hero 빅 라벨: `overall_legal_risk` 정규화 → HIGH / CAUTION / LOW / UNKNOWN (영문 그대로 기관 톤 유지)
- 빅넘버: `legal_risks` 중 HIGH/MEDIUM 카운트 / 전체 (라벨 HAZARD HITS)
- 등급별 색 매핑: HIGH=chart-2, CAUTION=warning, LOW=success, UNKNOWN=muted-foreground/border
- Magazine column: LEGAL BREAKDOWN 띠 → 기존 `<LegalTab>` (DecisionCard + InsightsGrid 등)

### 6) AnalyzeAgentInsightTab — `decor-hot-pink`

- Hero: AGENT ATTRIBUTION 배지 + confidence 1순위 에이전트 display_name + confidence×100 빅넘버 (PEAK CONFIDENCE)
  - confidence 미수신 시 attributions.length / 8 폴백 (AGENTS COMPLETED)
  - 둘 다 없으면 "멀티 에이전트 분석" 폴백 + '—'
- Magazine column: AGENT BREAKDOWN 띠 → 기존 `<InsightTab>` (8 에이전트 카드 grid + AgentConfidenceRadar)

## 데이터 자리 보존 (실데이터 룰 §3.7)

| 컴포넌트 | 보존된 데이터 자리 |
|---|---|
| DashboardHub | brandName, winner_district, target_district, district_rankings[winner].score, savedHistoryId |
| AnalyzeAiSummaryTab | winner_district, top_3_candidates, district_rankings, final_report.summary, final_recommendation, ai_recommendation, analysis_report |
| AnalyzeMarketTab | winner_district, target_district, market_report.* (floating_population/accessibility/competition_intensity), trend_forecast.{forecast/industry_trend/dong_trend/macro/key_drivers/risks} |
| AnalyzeDemographicTab | demographic_report.{core_demographic, brand_target_match_score} + 기존 DemographicTab 전체 |
| AnalyzeLegalTab | overall_legal_risk, legal_risks[].risk_level + 기존 LegalTab 전체 (DecisionCard + LegalDistributionBar + InsightsGrid + LegalDrawer) |
| AnalyzeAgentInsightTab | agent_attributions[].{display_name, confidence} + 기존 InsightTab 전체 |

데이터 누락 시 hero 빅넘버는 `'—'` 표시, hero 헤드라인은 폴백 카피 (예 "AI 종합 분석", "멀티 에이전트 분석"). 가짜 데이터 삽입 0건.

## 검증

```bash
$ npx prettier --write src/components/SimulationResult/dashboard/DashboardHub.tsx \
                       src/components/SimulationResult/dashboard/sub/analyze/
DashboardHub.tsx (unchanged)
AnalyzeAgentInsightTab.tsx (unchanged)
AnalyzeAiSummaryTab.tsx (unchanged)
AnalyzeDemographicTab.tsx (unchanged)
AnalyzeLegalTab.tsx 9ms       # whitespace
AnalyzeMarketTab.tsx 8ms      # whitespace

$ npx tsc --noEmit
(0 errors, 0 output)

$ # 워터마크 잔재 검사
$ rg 'text-\[[0-9]+rem\]' src/components/SimulationResult/dashboard
(0 hits)

$ # opacity modifier on color tokens 검사 (sub/analyze)
$ rg '/\[0\.0[0-9]+\]|/5\b|/10\b|/20\b|/30\b|/40\b|/60\b|/80\b' \
     src/components/SimulationResult/dashboard/sub/analyze
(0 hits)

$ # DashboardHub 동일
$ rg '/\[0\.0[0-9]+\]|/5\b|/10\b|/20\b|/30\b|/40\b|/60\b|/80\b' \
     src/components/SimulationResult/dashboard/DashboardHub.tsx
(0 hits)
```

## 라이트 모드 회귀 점검

- 검정 배경 클래스 (`bg-black`, `bg-gray-900`) 추가 0건
- `text-white`, `border-white`, `bg-white` 직접 사용 0건 — 모두 `text-foreground` / `bg-card` / `border-border` / `text-{accent}` 토큰
- 12색 시스템 토큰만 사용 (primary, chart-2/3/4, decor-hot-pink, warning, success, muted-foreground, foreground, accent, border, card)
- Tailwind 명명 색 (`text-stone-*`, `bg-blue-*` 등) 직접 사용 0건

## 디자인 일관성 노트

5 sub-탭 + DashboardHub 가 동일 골격 (Hero 12-col split → Magazine column → 선택적 Bottom emphasis). 색만 정체성별로 다름:

- DashboardHub: cream wash + chart-4 winner
- AI Summary: chart-4 (purple)
- Market: primary (blue)
- Demographic: chart-3 (teal)
- Legal: chart-2 (red, tone-aware)
- Agent Insight: decor-hot-pink

본부 영업팀 사용자가 sub-탭 전환 시 "어디 있는지" 색만으로 즉시 인식 가능. 워터마크 제거 후에도 정체성 색 인식 유지.

## 후속 후보

- `MarketTab` / `DemographicTab` / `LegalTab` / `InsightTab` 본문에 잔존하는 `bg-card/40 border border-border/60 rounded-3xl p-8` 카드 외피 다수. 다음 cycle 에서 inner section 도 magazine column / 띠 패턴으로 풀어낼 여지.
- `HubCard.tsx` 의 conic-gradient laser 효과는 CSS variable (`var(--primary)` 등) 직접 참조라 alpha modifier 이슈 없음 — 그대로 둠. 다만 Hero 와 카드 영역의 색감 톤 차이가 살짝 분리감을 줌, 통일감 추가 작업 가능.
- DashboardHub 의 cream wash (`bg-accent`) 는 토큰 자체가 cream 이라 alpha 없는 solid. 다른 페이지 (PredictGroup, AbmGroup) 의 hub-equivalent 자리에도 동일 패턴 확장 가능 (다른 정체성 색으로).
