# Phase 6a — AnalyzeGroup 4-탭 Editorial 패턴 확장 리포트

작성일: 2026-04-30
작업자: Claude (frontend lead — 강민 위임)
브랜치: `feature/analyze-llm-migration`

## 작업 범위

`AnalyzeAiSummaryTab` 의 editorial 패턴 (배경 거대 워터마크 + Tag 캡슐 + Hero 빅 타이포 + 빅넘버 + 좌측 4px gradient 색 띠 magazine column + bottom emphasis 박스) 을 AnalyzeGroup 의 나머지 4 sub-탭에 확장 적용.

수정 파일 (4개):

- `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeMarketTab.tsx`
- `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeDemographicTab.tsx`
- `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeLegalTab.tsx`
- `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAgentInsightTab.tsx`

기존 `MarketTab` / `DemographicTab` / `LegalTab` / `InsightTab` (사용처 다수) 는 손대지 않음 — 4 wrapper 만 editorial 외피로 감쌌으므로 다른 페이지/뷰 회귀 위험 없음.

---

## 탭별 변경 요약

### 1) AnalyzeMarketTab.tsx — `primary` (Deep Blue)

| 요소 | 적용 |
|---|---|
| 배경 워터마크 | `text-[14rem→18rem] text-primary/10` 좌상단 "M" |
| Tag 캡슐 | `bg-primary/10 ... text-primary` + `MapPin` 아이콘 + "상권 지리 · MARKET" |
| Hero 헤드라인 | `text-6xl→7xl font-black tracking-tighter text-foreground` — `winner_district` (없으면 `target_district`) |
| 빅넘버 | `text-7xl→8xl text-primary` — `floating_population` 우선, 폴백 `accessibility` → `competition_intensity` (`market_report` 정규화 0~100). 라벨 `REGIONAL ACTIVITY` / `ACCESSIBILITY` / `COMPETITION` |
| Magazine column | 좌측 4px gradient `from-primary via-primary/60 to-primary/0` + small caps `MARKET BREAKDOWN` 헤더 → 기존 `<MarketTab>` 데이터 그대로 재사용 |
| Bottom emphasis | `rounded-3xl bg-primary/5 p-8` + 우상단 ✦ 워터마크 — 트렌드 거시 환경 (`TrendSparklinesPanel` + `TrendDriversRisks`) |

데이터 자리 보존: 기존 `MarketTab` (Kakao 지도, IndicatorGrid, DistrictRankings, 에이전트 분석 요약 3카드, EmergingSignalCard, FlowVsRevenueScatter, DifferentiationCard, CannibalizationDistanceChart, IndustryClosureTrendCard, HHI 카드) + 트렌드 거시 패널/드라이버·리스크 그대로.

### 2) AnalyzeDemographicTab.tsx — `chart-3` (Teal Green)

| 요소 | 적용 |
|---|---|
| 배경 워터마크 | `text-[12rem→16rem] text-chart-3/10` 좌상단 "POP" |
| Tag 캡슐 | `bg-chart-3/10 text-chart-3` + `Users` 아이콘 + "인구 분석 · DEMOGRAPHIC" |
| Hero 헤드라인 | `text-6xl→7xl font-black` — `core_demographic` 의 `{age} {mapGender(gender)}` (예: "30대 여성"). 데이터 없으면 5xl "인구 분석 리포트" 폴백 |
| 빅넘버 | `text-7xl→8xl text-chart-3` — `core_demographic.share` × 100 → `CORE SHARE`. share 없을 때 `brand_target_match_score` → `BRAND MATCH` 폴백. 둘 다 없으면 hero 자체 hide |
| Magazine column | 좌측 4px gradient `from-chart-3 via-chart-3/60 to-chart-3/0` + `DEMOGRAPHIC BREAKDOWN` → 기존 `<DemographicTab>` 그대로 |

데이터 자리 보존: `CoreDemographicDonut` / `StackedAgeBar` / `WeekdayWeekendBar` / 4 MetricBox / narrative + match_rationale / `CustomerSegmentCard` 모두 유지.

### 3) AnalyzeLegalTab.tsx — `chart-2` (Vivid Red)

| 요소 | 적용 |
|---|---|
| 배경 워터마크 | `text-[16rem→20rem] text-chart-2/10` 좌상단 "!" — 가장 큰 사이즈로 위험 톤 강조 |
| Tag 캡슐 | tone-aware (`bg-chart-2/10` ↔ `bg-warning/10` ↔ `bg-success/10` ↔ `bg-muted/10`) + `AlertTriangle` + "법률 리스크 · LEGAL" |
| Hero 헤드라인 | `text-6xl→7xl text-{tone}` — `overall_legal_risk` 정규화 → `HIGH` / `CAUTION` / `LOW` / `UNKNOWN`. 데이터 없을 때 `UNKNOWN` 표시하며 "legal 에이전트 실행 대기" 서브카피 |
| 빅넘버 | `text-7xl→8xl text-{tone}` — `legal_risks` 중 HIGH/MEDIUM 카운트 (`hazardCount`) / 전체 건수. 라벨 `HAZARD HITS` |
| Magazine column | 좌측 4px gradient `from-chart-2 via-chart-2/60 to-chart-2/0` + `LEGAL BREAKDOWN` → 기존 `<LegalTab>` (DecisionCard + LegalDistributionBar + InsightsGrid) 그대로 |

데이터 자리 보존: `DecisionCard` (LLM 출처 통합 판단 GO/HOLD/STOP), 등급 분포 막대, InsightsGrid legalOnly + LegalDrawer 전부 유지. tone-aware 카드 색상은 12색 시스템 토큰 (`chart-2`/`warning`/`success`/`muted`) 안에서만 동작.

### 4) AnalyzeAgentInsightTab.tsx — `decor-hot-pink` (Hot Pink)

| 요소 | 적용 |
|---|---|
| 배경 워터마크 | `text-[14rem→18rem] text-decor-hot-pink/10` 좌상단 "✦" |
| Tag 캡슐 | `bg-decor-hot-pink/10 text-decor-hot-pink` + `Radar` + "에이전트 근거 · ATTRIBUTION" |
| Hero 헤드라인 | `text-6xl→7xl font-black` — `agent_attributions` 중 confidence 1순위 에이전트의 `display_name`. attributions 없으면 "멀티 에이전트 분석" 5xl 폴백 |
| 빅넘버 | `text-7xl→8xl text-decor-hot-pink` — 1순위 confidence × 100 → `PEAK CONFIDENCE`. confidence 미수신 시 `agent_attributions.length` / 8 → `AGENTS COMPLETED` 폴백 |
| Magazine column | 좌측 4px gradient `from-decor-hot-pink via-decor-hot-pink/60 to-decor-hot-pink/0` + `AGENT BREAKDOWN` → 기존 `<InsightTab>` 그대로 |

데이터 자리 보존: `AgentConfidenceRadar` + 8 에이전트 카드 grid (verdict + reasoning + sources 배지 + 상세 모달) 전부 유지.

---

## 절대 룰 준수 검증

- [x] `App.tsx`, `AnalyzeAiSummaryTab.tsx`, `AnalyzeGroup.tsx` 미수정
- [x] `src/reference/figma-crm-kit/**` 손대지 않음
- [x] `*.test.tsx` 손대지 않음
- [x] 데이터 모델 변경 없음 — 모든 props/필드는 기존 `SimulationOutput` 타입 그대로
- [x] 시뮬레이션 logic 변경 없음
- [x] 12색 시스템 토큰만 사용 (`primary`, `chart-2/3`, `decor-hot-pink`, `warning`, `success`, `muted`, `muted-foreground`, `foreground`, `card`, `border`)
- [x] Tailwind 명명 색 (`text-stone-*`, `bg-blue-*` 등) 직접 사용 0건
- [x] 데이터 누락 시 hero hide 또는 서브카피 fallback — 가짜 데이터 삽입 0건 (§3.7 실데이터 룰)

## 검증 결과

```bash
$ cd frontend && npx prettier --write src/components/SimulationResult/dashboard/sub/analyze/
AnalyzeAgentInsightTab.tsx (unchanged)
AnalyzeAiSummaryTab.tsx (unchanged)
AnalyzeDemographicTab.tsx 13ms     # whitespace 정렬
AnalyzeLegalTab.tsx 19ms           # whitespace 정렬
AnalyzeMarketTab.tsx (unchanged)

$ cd frontend && npx tsc --noEmit && echo "TSC_OK"
TSC_OK
```

prettier: 모든 파일 통과 (2개 파일 자동 reformat — whitespace only).
tsc: 0 errors.

## 라이트 모드 회귀 점검

- 검정 배경 클래스 (`bg-black`, `bg-gray-900` 등) 추가 없음
- `text-white` 직접 사용 없음 — 모두 `text-foreground` / `text-{accent}` 토큰
- `border-white` / `bg-white` 직접 사용 없음
- 배경 워터마크는 `text-{accent}/10` (10% alpha) 으로 라이트·다크 양 모드에서 기존 토큰의 alpha 그라데이션을 따름

## 디자인 일관성 노트

4 탭이 동일 레이아웃 골격 (Hero 12-col grid → Magazine column → 선택적 bottom emphasis) 을 공유하므로 sub-탭 전환 시 시각적 리듬이 일정. 색만 정체성 별로 변하므로 본부 영업팀 사용자가 "어느 탭에 있는지" 색만으로 즉시 인식 가능 (Deep Blue 지리 / Teal Green 사람 / Vivid Red 위험 / Hot Pink 에이전트).

## 후속 후보

- AnalyzeMarketTab 의 본문 (`<MarketTab>`) 내부에도 editorial 톤이 일부 잔존 (예: `bg-card/40 border border-border/60 rounded-3xl p-8` 카드 외피 다수). 다음 cycle 에서 inner section 도 magazine column 으로 풀어낼 여지 있음. 이번 phase 는 wrapper-level 외피만 정비.
- LegalTab 의 InsightsGrid 표 표시는 본부 영업팀 검토 시 필요한 정보 밀도 유지를 위해 그대로 둠. 표 자체는 카드형 외피 안에 있어 editorial 톤과 약간 충돌 가능.
