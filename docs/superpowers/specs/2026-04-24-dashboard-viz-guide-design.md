# SPOTTER 대시보드 시각화 가이드 적용 — 설계 스펙

**작성일**: 2026-04-24
**담당**: C1 (강민) — `frontend/` 단독 작업
**기준 문서**: 「SPOTTER 대시보드 — 데이터 유형별 시각화 가이드」 (2026-04-23)
**상태**: 설계 승인 완료, 구현 계획 대기

---

## 1. 배경 및 목표

2026-04-21 v4.2 TabbedDashboard 리디자인으로 15 섹션 통합 리포트가 4 탭 구조(요약·상권·예측·AI 근거)로 재편됐다. 그러나 이 시점의 차트 선택은 가이드(Cleveland & McGill 1985, Tufte, Wilke 2019, GrowthFactor Glass Box 2025) 기준에서 보면 격차가 존재한다.

**가장 큰 격차:**
- `demographic_report` 섹션이 텍스트 + MetricBox만으로 구성 — 차트 0개
- `shap_result`가 단순 좌/우 split bar — 가이드 ⭐ Waterfall 미적용
- KPI Mini Grid 4종이 Big Number만 — Sparkline + Bullet 부재
- `agent_attributions[]` 8종이 카드 grid만 — 다차원 한눈 Radar 부재
- `market_entry_signal` 데이터가 verdict 계산에만 사용, 신호등 시각화 부재
- `legal_risks[]` 등급 분포가 모달 안에서만 색상 구분 — 상위 수준 한눈 분포 부재

이 작업은 가이드의 **모든 적용 가능 룰**을 현재 `SimulationOutput` 데이터에 매핑해 **11종 신규/교체 차트**를 4 탭에 통합한다.

**원칙:**
- "표현 가능한 모든 것 시각화" — 같은 값이라도 시각화 이득이 있으면 적용
- Cleveland 서열 상위 우선 (Position > Length > Angle > Area > Color)
- Glass Box (단일 수치보다 신뢰구간·근거)
- 가이드 ⭐ 4종 중 데이터 가용한 3종 모두 적용 (Waterfall / Bullet / KPI+Sparkline). 나머지 1종(Calendar Heatmap)은 Track B로 분리.

## 2. 전제 및 제약

- **담당 영역**: C1(강민) `frontend/` 단독. 백엔드 확장은 Track B로 분리 (Issue #106, #107).
- **의존성 추가 금지**: Recharts + D3 + Framer Motion 기존 스택만 사용. Sparkline·Waterfall·Bullet 모두 Recharts 커스텀으로 구현.
- **데이터 부재 처리**: `null/undefined` → "—" 텍스트, 차트 부재 → dashed border placeholder + 에이전트명. **mock 데이터 절대 금지** (IM3-144 schema mismatch incident 근거).
- **dev convention 준수**:
  - 법률 등급 라벨 통일: `safe/caution/danger` → "필수이행/확인필요/참고사항"
  - `LegalRisk.is_fallback` 필드 시각 마커 옵션 (dashed)
  - `labor_law` 한글명 "근로기준법" (dev `App.tsx`에서 통일)
- **자동 활성화 (forward compat)**: Track B(#106 #107) 백엔드 확장 머지 시 프론트 코드 변경 없이 새 차트가 자동 활성화되도록 필드 존재 분기 작성.
- **기존 보존**:
  - 4탭 구조 (Summary/Market/Forecast/Insight)
  - DecisionCard×3, MapSection (Kakao SDK), IndicatorGrid, DistrictRankings, InsightsGrid + LegalDrawer
  - QuarterlyProjectionChart 기본 구조 (확장만)

## 3. 확정된 설계 결정 (Q&A 이력)

| 항목 | 결정 | 근거 |
|---|---|---|
| 라이브러리 | Recharts only (의존성 0) | Waterfall PoC 검증 완료 (`charts/WaterfallChart.tsx`) |
| 색 시스템 | Indigo 400(#818cf8) 메인 유지 (옵션 A) | v4.2 다크 테마 일관성, B2B SaaS 톤 (Tableau/Linear/Datadog 계열) |
| Sequential | Indigo 100 → 950 (Choropleth) | 가이드 §3-3 |
| Diverging | Rose 500 ← Zinc 500 → Indigo 400 | 가이드 §3-3 |
| 긍정/경고/부정 | Emerald 500 / Amber 500 / Rose 500 | 가이드 §3-3 |
| Summary 탭 그루핑 | "인구 구성" Collapsible Section (Donut + Stacked HBar + Side-by-side Bar) | 강민 제안 A |
| Forecast 탭 순서 | 예측(Line+CI) → 근거(SHAP Waterfall) → 리스크(Bullet) | 강민 제안 B |
| 차트 9종 → 11종 | `market_entry_signal` 신호등(#10) + `legal_risks` 분포(#11) 추가 | 가이드 §1-10 + §1-3 |
| Track B 분리 | Calendar Heatmap(#106) + 2단계 신뢰밴드(#107) 백엔드 확장 별도 PR | 데이터 부재 |

## 4. 11종 차트 매핑 — 탭별 배치

### Summary 탭 (7개 신규/교체)

```
1. DecisionCard × 3 (기존 유지)
2. 🆕 Market Entry Signal Light (#10) — 큰 Badge + Icon, Hero 영역 또는 DecisionCard 1 강화
3. KPI Mini Grid 4종
   ├─ + Sparkline (#4) — Recharts LineChart mini variant, quarterly_projection 월 환산 파생
   └─ + Bullet (#3) — div 3-layer (range/target/actual)
4. ProfitSimulationPanelFull (기존 유지) — 추후 Sparkline 자연 흡수
5. 🆕 인구 구성 Collapsible Section
   ├─ Donut (#5) — core_demographic.share
   ├─ Stacked Horizontal Bar (#2) — top_3_age_groups[]
   └─ Side-by-side Bar (#6) — weekday_weekend_ratio
6. DemographicReportSection (기존 narrative + MetricBox는 Collapsible 하위로 보존)
```

### Market 탭 (1개 신규)

```
1. MapSection (기존 유지) — vacancy_applied 배지 포함
2. IndicatorGrid (기존 Radar) + DistrictRankings (기존 Sorted Bar)
3. 🆕 Scatter Plot (#8) — 16동 x=floating_population, y=estimated_revenue, winner 강조
4. 🆕 Legal Risks Distribution Bar (#11) — 등급별 stacked horizontal bar (필수이행/확인필요/참고사항)
   └─ InsightsGrid (legalOnly) 상단 배치
```

### Forecast 탭 (2개: 1교체 + 1신규)

```
1. QuarterlyProjectionChart (기존 Line + Confidence Area)
   └─ Track B #107 머지 시 자동으로 2단계 밴드(80%/95%) 활성화
2. SHAP horizontal bar → 🔄 Waterfall Chart (#1) 교체
   └─ charts/WaterfallChart.tsx (PoC 완료)
3. 🆕 Bullet (#9) — closure_risk.risk_score (0-100)
```

### Insight 탭 (1개 신규)

```
1. 🆕 Radar Chart (#7) — 8 Agent Confidence overview, 상단 배치
2. AGENTS_LIST 8 카드 grid (기존 유지)
```

## 5. 차트별 데이터 매핑 + 구현 가이드

### #1 SHAP Waterfall (PoC 완료)

- **컴포넌트**: `dashboard/charts/WaterfallChart.tsx` (159줄, Recharts BarChart + stacked Bar 패턴)
- **소스**: `simResult.shap_result` (`base_value` + `feature_importance[].shap_value` + `predicted_value`)
- **변환**: `WaterfallStep[]` 형식 (`base` → `contribution × N` → `final`)
- **색**: Stone 400(base) / Emerald 500(positive) / Rose 500(negative) / Indigo 400(final)
- **배치**: `ForecastTab` 내 기존 SHAP horizontal bar 영역 교체

### #2 Stacked Horizontal Bar (top_3_age_groups)

- **컴포넌트**: `dashboard/charts/StackedAgeBar.tsx` (신규, ~80줄)
- **소스**: `demographic_report.top_3_age_groups[].share`
- **데이터 누락 시**: dashed placeholder + "demographic_depth 분석 대기"
- **단위**: % (소수점 1자리)

### #3 Bullet Chart (KPI 4종)

- **컴포넌트**: `dashboard/charts/BulletChart.tsx` (신규, ~60줄, Tailwind div 3-layer)
- **소스**: `market_report.{floating_population, competition_intensity, ...}` 0-100 정규화 지표
- **레이어**:
  - Background range: 0-100 (Stone 800)
  - Qualitative: 0-40 / 40-70 / 70-100 (Stone 700 단계 그라데이션)
  - Actual: 실측치 막대 (Indigo 400)
  - Target/Reference: 70 (목표선, dashed Indigo 200)
- **배치**: `KpiMiniGrid` 각 항목 하단

### #4 Sparkline (KPI 카드)

- **컴포넌트**: `dashboard/charts/Sparkline.tsx` (신규, ~40줄, Recharts LineChart mini variant)
- **소스**: `quarterly_projection[].revenue` 4 포인트 그대로 (월 환산은 단일 값 분배라 가짜 디테일 우려 — 분기 단위로 명시)
- **크기**: 80×24 px (KPI 카드 하단 풀와이드)
- **색**: 트렌드 방향에 따라 Emerald(증가) / Rose(감소) / Stone(유지)

### #5 Donut (core_demographic)

- **컴포넌트**: `dashboard/charts/CoreDemographicDonut.tsx` (신규, ~70줄, Recharts PieChart innerRadius)
- **소스**: `demographic_report.core_demographic` (`age` + `gender` + `share`)
- **세그먼트**: 메인(예: "30대 여성 42%") + 기타(58%)
- **중앙 라벨**: `${age} ${gender}` Big Number

### #6 Side-by-side Bar (주중/주말)

- **컴포넌트**: `dashboard/charts/WeekdayWeekendBar.tsx` (신규, ~50줄, Recharts BarChart 2 Bar)
- **소스**: `demographic_report.weekday_weekend_ratio` (단일 ratio 값 → [weekday=ratio, weekend=1-ratio])
- **단위**: %

### #7 Radar (8 Agent Confidence)

- **컴포넌트**: `dashboard/charts/AgentConfidenceRadar.tsx` (신규, ~80줄, Recharts RadarChart)
- **소스**: `agent_attributions[].confidence` × 8 (없는 에이전트는 0 또는 null)
- **각도 매핑**: AGENTS_LIST 순서 따름
- **배치**: `InsightTab` 상단 overview, grid 위

### #8 Scatter Plot (유동인구 vs 매출)

- **컴포넌트**: `dashboard/charts/FlowVsRevenueScatter.tsx` (신규, ~90줄, Recharts ScatterChart)
- **소스**: `district_rankings[]`에서 동별 floating_population + estimated_revenue 추출 (또는 `comparison[]` 활용)
- **강조**: `winner_district`는 큰 점 + Indigo 400, 나머지 Stone 500
- **추세선**: 선형 회귀 (간이 계산 client-side)
- **배치**: `MarketTab` IndicatorGrid + DistrictRankings 그리드 다음 행

### #9 Bullet (Closure Risk)

- **컴포넌트**: #3 BulletChart 재사용
- **소스**: `closure_risk.risk_score` (0-100)
- **Qualitative**: 0-30(safe) / 30-60(caution) / 60-100(danger)
- **배치**: `ForecastTab` SHAP Waterfall 다음

### #10 Market Entry Signal Light

- **컴포넌트**: `dashboard/charts/EntrySignalLight.tsx` (신규, ~50줄, 단순 Badge + Icon)
- **소스**: `competitor_intel.market_entry_signal` (`green` | `yellow` | `red`)
- **표시**: 큰 원형 Badge (Emerald/Amber/Rose) + Lucide Icon (CheckCircle/AlertCircle/XCircle)
- **배치**: `SummaryTab` 최상단 Hero 영역 (DecisionCard 3종 위). Hero가 좁으면 DecisionCard 1 우측 끝 inline fallback.

### #11 Legal Risks Distribution Bar

- **컴포넌트**: `dashboard/charts/LegalDistributionBar.tsx` (신규, ~70줄, Recharts BarChart layout="vertical" stackId)
- **소스**: `legal_risks[]`을 `risk_level` (HIGH/MEDIUM/LOW) 카운트
- **라벨**: dev convention "필수이행 / 확인필요 / 참고사항"
- **`is_fallback === true` 처리**: 옵션 dashed segment (가이드라인 미세 시각 분리)
- **배치**: `MarketTab` 또는 InsightsGrid 상단 sticky

## 6. Empty State 정책

| 데이터 상태 | UI 처리 | 근거 |
|---|---|---|
| 필드 자체 `null/undefined` | "—" 텍스트 | IM3-144 incident |
| 배열 빈 (예: `top_3_age_groups: []`) | dashed border placeholder + 에이전트명 + "분석 대기" | 명시적 빈 상태 |
| 부분 부재 (예: SHAP top 4 중 2개) | 있는 것만 렌더, 빈 셀 X | 진실성 우선 |
| 차트 전체 부재 | placeholder 한 줄 + 에이전트명 (예: "demographic_depth 분석 대기") | 사용자에게 책임 위치 명확 |
| Mock fallback | **금지** — `is_mock === true`인 SHAP/closure_risk는 `dashed placeholder` 렌더 + 경고 배지 | IM3-144 incident |

## 7. Track B (백엔드 확장 — 별도 PR)

이번 PR 범위 외, 자동 활성화 코드만 심어둠.

| Issue | 필드 | 활성화 차트 | 프론트 분기 |
|---|---|---|---|
| #106 | `DemographicReport.peak_hour_matrix: number[7][24]` | Calendar Heatmap (가이드 ⭐) | 필드 존재 시 `<CalendarHeatmap>` 렌더, 없으면 기존 텍스트 fallback |
| #107 | `QuarterlyProjection.ci_80_lower/upper` + `ci_95_lower/upper` | Graded Confidence Band 2단계 | `ci_95_*` 존재 시 2단계 Area, 없으면 기존 단일 밴드 |

## 8. 디자인 시스템

### 색

```
메인:        Indigo 400 (#818cf8)
긍정:        Emerald 500 (#22c55e)
경고:        Amber 500 (#f59e0b)
부정:        Rose 500 (#ef4444)
배경 base:   #0C0B0A (v4.2)
카드 배경:   Stone 900/40 + 800/60 border
보조 데이터: Stone 500-700
Sequential:  Indigo 100 → 950 (Choropleth)
Diverging:   Rose 500 ← Zinc 500 → Indigo 400
```

### 차트 인코딩 우선순위 (Cleveland & McGill 1985)

```
1. Position (막대·점)           ← 항상 우선
2. Length (막대 길이)
3. Angle / Slope (기울기)
4. Area (버블·트리맵)
5. Color hue                   ← 의미 있는 색만
```

### 금지

- ❌ 3D 차트
- ❌ Pie chart with 5+ slices
- ❌ Y축 truncation (zero baseline 필수)
- ❌ Rainbow 팔레트
- ❌ 6개 이상 라인
- ❌ 축 라벨/단위 누락
- ❌ Mock 데이터 fallback

## 9. 변경 영향 범위

```
신규 파일 (10):
  dashboard/charts/
    WaterfallChart.tsx          (#1, PoC 완료)
    StackedAgeBar.tsx           (#2)
    BulletChart.tsx             (#3, #9 재사용)
    Sparkline.tsx               (#4)
    CoreDemographicDonut.tsx    (#5)
    WeekdayWeekendBar.tsx       (#6)
    AgentConfidenceRadar.tsx    (#7)
    FlowVsRevenueScatter.tsx    (#8)
    EntrySignalLight.tsx        (#10)
    LegalDistributionBar.tsx    (#11)

수정 파일 (5):
  dashboard/tabs/SummaryTab.tsx   — KPI 카드에 Sparkline+Bullet, 인구 구성 Collapsible 추가, EntrySignalLight 통합
  dashboard/tabs/MarketTab.tsx    — Scatter + LegalDistributionBar 추가
  dashboard/tabs/ForecastTab.tsx  — SHAP horizontal bar → Waterfall 교체, Closure Bullet 추가
  dashboard/tabs/InsightTab.tsx   — Radar overview 상단 추가
  dashboard/shared/KpiMiniGrid.tsx — Bullet + Sparkline 슬롯

영향 없음:
  IndicatorGrid / DistrictRankings / MapSection / InsightsGrid / LegalDrawer (dev 라벨 통일 자동 반영)
  QuarterlyProjectionChart (Track B #107 분기 코드만 추가, 기본 동작 유지)
```

## 10. 완료 조건

- [ ] 11개 신규 차트 컴포넌트 모두 구현 + TS 통과 + vite build 통과
- [ ] 4 탭에 차트 통합, 가이드 §3 Visual Hierarchy (Hero → KPI Grid → Detail) 준수
- [ ] 데이터 부재 시 "—" 또는 dashed placeholder 렌더 (mock 절대 X)
- [ ] Track B 자동 활성화 분기 (#106 `peak_hour_matrix`, #107 `ci_95_*`) 코드 심어둠
- [ ] dev convention 통합 라벨 ("필수이행/확인필요/참고사항", "근로기준법") 준수
- [ ] Recharts only — package.json 의존성 추가 0
- [ ] eslint baseline 신규 위반 0 (기존 App.tsx 위반은 이번 PR 외 영역이라 무관)
- [ ] prettier 포맷 적용
- [ ] PR 단일 (다커밋 OK) — 메모리 "에이전트당 단일 브랜치 관례"

## 11. 후속 작업 (Out of Scope)

- 백엔드 확장 PR (Track B #106 #107) — 별도 이슈, 머지 시 자동 활성화
- ABM 1000명 시뮬 시각화 — ABM 데이터 자체 없음, 추후 별도 스펙
- 모바일/작은 화면 대응 — 가이드 체크리스트 항목, 후속 PR
- 색약 접근성 audit (단일 색 의존 금지) — 후속 PR
