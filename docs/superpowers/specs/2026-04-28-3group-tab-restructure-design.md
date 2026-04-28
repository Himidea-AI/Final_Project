# Dashboard 3그룹 IA 재구조 — Frontend 한정 — Design Spec

**Date**: 2026-04-28
**Author**: 강민 (PM + Frontend Lead) + Claude
**Branch**: `feature/dashboard-3group-ia`
**Status**: Draft → User Review

---

## 1. Context

PDF 안 (`Data_Source_and_UI_Restructuring_Plan.pdf`) + chichi 회신 + 강민 최종 결정으로 다음 결정:

- 직전 brainstorming 의 (a-2) 7탭 progressive 채움 결정 **공식 무효화**
- PDF 안의 **3그룹 IA (예측 결과 / AI 분석 / ABM)** + 11 서브탭 채택
- **그러나 backend 는 건드리지 않음** (B1 예진 영역 위임 부담 + Phase 1 cycle 분리)
- 결과: PDF 의 시각 IA 약속 충족 + "ML 25초 우선 활성" 약속 미달 (사용자 의식적 trade-off)
- **mock 데이터 금지** — 값 없으면 빈 셀(`—`) 또는 placeholder

직전 cycle 5건 처리:
- 7탭 + ultra-wide + 노란선 (04-24): **폐기** — 새 3그룹+11서브탭으로
- 11종 차트 (04-27): **컴포넌트 재사용 + 그룹별 재배치**
- Master Oversight HistoryCard 배지 (04-27): /hq 라우트 그대로, 결과 화면만 새 IA
- manager 권한 분리 (04-28): 영향 없음 (인증 흐름 무관)
- manager_signup 보안 hotfix: 별 cycle 에서 commit `6bf516f` 완료

---

## 2. 최종 IA 구조

### 2-A. 예측 결과 그룹 (ML 기반 — 기존 backend `/analyze` 응답의 ML 필드만 표시)

| 서브탭 | 컴포넌트 (재사용) | 데이터 원천 | 연동 상태 |
|---|---|---|---|
| **예측 요약** | KPI 카드 3종 (월매출 / BEP / 폐업위험도 점수) | `final_report.profit_simulation`, `closure_risk` | ✅ |
| **매출 예측** | `QuarterlyProjectionChart` + `ScenariosComparisonChart` + `ShapInsightCard` | `quarterly_projection`, `scenarios`, `shap_result` | ✅ |
| **재무 시뮬레이션** | `BepCumulativeProfitChart` + `ClosureRateHistoryChart` + `ClosureSignalsBar` + `SurvivalRateKpi` | `quarterly_projection.cumulative_profit`, `closure_rate`, `closure_risk.top_signals_lgbm/tcn`, `market_report.survival_rate` | ✅ |
| **고객·유동인구** | placeholder | (B2 미연동 — `/customer-segment`, `/living-pop-forecast` endpoint 노출 후) | 🟡 placeholder |
| **신흥상권 감지** | placeholder | (B2 미연동 — `/emerging-district` endpoint 노출 후) | 🟡 placeholder |

### 2-B. AI 분석 그룹 (LLM 기반 — 기존 `/analyze` 응답의 LLM 필드만 표시)

| 서브탭 | 컴포넌트 (재사용/이동) | 데이터 원천 |
|---|---|---|
| **AI 분석 요약** | `computeDecision` 결과 (이동) + 창업 신호등 + synthesis 자연어 | `final_report.summary`, `overall_legal_risk`, `competitor_intel.market_entry_signal` |
| **상권 분석** | `MapSection`, `IndicatorGrid`, `DistrictRankings`, `FlowVsRevenueScatter`, `DifferentiationCard`, `CannibalizationDistanceChart`, `IndustryClosureTrendCard` + **trend_forecast 패키지 (TrendSparklinesPanel + TrendDriversRisks + narrative 모달, ForecastTab 에서 이동)** | `competitor_intel`, `market_report`, `district_rankings`, `trend_forecast` |
| **인구 분석** | `CoreDemographicDonut`, `WeekdayWeekendBar`, `StackedAgeBar`, `MetricBox`, narrative | `demographic_report` |
| **법률 리스크** | `LegalDistributionBar` + 14개 항목 리스트 + 조항 + 체크리스트 | `legal_risks` |
| **에이전트 근거** | `AgentConfidenceRadar` + 8 에이전트 reasoning 카드 | `agent_attributions` |

### 2-C. ABM 시뮬레이터 그룹 (독립)

- 현 ABM 탭 (`AbmTab` + `AbmPersonaMap` + `VacancySpotMarker` + `VacancyStatsPanel` 등) **그대로 유지**
- `/vacancy_evaluation` endpoint 그대로

---

## 3. 핵심 변경 영역

### 3-1. types/index.ts — Tab enum 신설

```typescript
export type MainTab = 'predict' | 'analyze' | 'abm';

export type PredictSubTab =
  | 'summary'
  | 'sales_forecast'
  | 'financial_sim'
  | 'customer_flow'      // placeholder
  | 'emerging_district'; // placeholder

export type AnalyzeSubTab =
  | 'ai_summary'
  | 'market'
  | 'demographic'
  | 'legal'
  | 'agent_insight';
```

기존 단일 탭 enum (e.g. `TabId`) → 신규 구조로 교체. 컴파일 에러로 누락 지점 자동 탐지.

### 3-2. TabbedDashboard 신규 구조

`frontend/src/components/SimulationResult/dashboard/TabbedDashboard.tsx` 전면 재작성:
- Top-level: 3 그룹 탭 바 (예측 결과 / AI 분석 / ABM)
- Sub-level: 그룹별 서브탭 바 (예측 = 5, 분석 = 5, ABM = 단일)
- URL query param: `?group=predict|analyze|abm&sub=<sub_id>` (deep link)

### 3-3. 11종 차트 그룹 매핑 (재사용, 위치만 변경)

| 컴포넌트 | 직전 위치 | 새 위치 |
|---|---|---|
| `BepCumulativeProfitChart` | ForecastTab | 예측·재무 시뮬레이션 |
| `ScenariosComparisonChart` | ForecastTab | 예측·매출 예측 |
| `TrendSparklinesPanel` | ForecastTab | **분석·상권 분석** (이동) |
| `TrendDriversRisks` | ForecastTab | **분석·상권 분석** (이동) |
| `ShapInsightCard` | ForecastTab | 예측·매출 예측 |
| `SurvivalRateKpi` | FinancialTab | 예측·재무 시뮬레이션 |
| `ClosureRateHistoryChart` | FinancialTab | 예측·재무 시뮬레이션 |
| `ClosureSignalsBar` | FinancialTab | 예측·재무 시뮬레이션 |
| `DifferentiationCard` | MarketTab | 분석·상권 분석 |
| `CannibalizationDistanceChart` | MarketTab | 분석·상권 분석 |
| `IndustryClosureTrendCard` | MarketTab | 분석·상권 분석 |

### 3-4. computeDecision 이동

- 현재: `SummaryTab` 내부 — `overall_legal_risk` (LLM) 사용
- 새 위치: AI 분석·요약 서브탭
- `predict-summary` 서브탭은 ML 숫자 카드만 (월매출 / BEP / 폐업위험도 점수)

### 3-5. trend_forecast 컴포넌트 이동

- 직전 cycle 에서 `ForecastTab` 에 추가한 `TrendSparklinesPanel` + `TrendDriversRisks` + narrative 모달 — **데이터 원천이 LLM (`trend_forecaster` 에이전트)** 이라 분석 그룹으로 이동
- ForecastTab (구) 흔적 X — ForecastTab 자체가 사라짐 (서브탭으로 분해)

### 3-6. 미연동 서브탭 처리

`고객·유동인구` + `신흥상권 감지` 서브탭은 **탭 노출 + placeholder 컴포넌트만**:

```tsx
<div className="flex flex-col items-center justify-center h-64 text-stone-500">
  <p className="text-sm">준비 중입니다.</p>
  <p className="text-xs mt-1">해당 분석 모델 연동 후 활성화됩니다.</p>
</div>
```

서브탭 버튼 비활성화 X — 클릭은 가능, 내용만 placeholder.

### 3-7. null 표시 통일

응답 필드가 null/undefined 인 경우 모든 위치에서 `—` (em dash) 표시. mock fallback 금지.

### 3-8. vitest 처리

새 IA 로 깨지는 vitest 테스트 → `it.skip` 으로 일시 비활성화. 안정화 후 별 cycle 에서 재작성.

### 3-9. 라우트 query param

기존 `/result/:id` 또는 `/dashboard` 라우트 (정확한 경로는 작업 시 확인) + `?group=predict|analyze|abm&sub=<sub_id>` 파라미터:
- 새로고침 후 마지막 보던 위치 복원
- 딥링크 공유 가능
- ABM 그룹은 `?group=abm`

### 3-10. ABM 그룹 진입점

GlobalNav 또는 dashboard 내부 — 별 메뉴 권장 (chichi N5 회신). 단 정확한 위치 (메인 탭 vs 헤더 별 메뉴) 는 구현 시 결정.

---

## 4. Out of Scope

- backend graph.py 분할 / Redis state / `/predict` `/analyze` 분리 (Phase 1 — B1 예진 영역, 이번 cycle 미포함)
- B2 미연동 ML 3개 endpoint 노출 (Phase 3 — B2 수지니, 이번 cycle 미포함, 서브탭은 placeholder)
- 매니저별 필터 / Bell 드롭다운 master 어휘 라벨 분기 등 Minor (별 cycle)
- App.tsx SimulatorDashboard 추출 (Phase 2 — 코드 스플릿, 이번 cycle 미포함)

---

## 5. 변경 파일 예상 (총 25-35개)

### 신규
- `frontend/src/components/SimulationResult/dashboard/groups/PredictGroup.tsx`
- `frontend/src/components/SimulationResult/dashboard/groups/AnalyzeGroup.tsx`
- `frontend/src/components/SimulationResult/dashboard/groups/AbmGroup.tsx`
- `frontend/src/components/SimulationResult/dashboard/sub/Predict*Tab.tsx` × 5
- `frontend/src/components/SimulationResult/dashboard/sub/Analyze*Tab.tsx` × 5
- `frontend/src/components/SimulationResult/dashboard/shared/PlaceholderPanel.tsx`

### 수정
- `frontend/src/types/index.ts` — Tab enum 신설
- `frontend/src/components/SimulationResult/dashboard/TabbedDashboard.tsx` — 3그룹 + 11서브탭 구조
- `frontend/src/App.tsx` — 라우트 query param + dashboard render
- `frontend/src/components/SimulationResult/dashboard/tabs/SummaryTab.tsx` — 분리/제거
- `frontend/src/components/SimulationResult/dashboard/tabs/ForecastTab.tsx` — 분해/제거
- `frontend/src/components/SimulationResult/dashboard/tabs/FinancialTab.tsx` — 분해/제거
- `frontend/src/components/SimulationResult/dashboard/tabs/MarketTab.tsx` — 분해/제거
- `frontend/src/components/SimulationResult/dashboard/tabs/DemographicTab.tsx` — 분해/이동
- `frontend/src/components/SimulationResult/dashboard/tabs/LegalTab.tsx` — 이동
- `frontend/src/components/SimulationResult/dashboard/tabs/InsightTab.tsx` — 이동
- 기타 11종 차트 컴포넌트 import 경로 갱신

### 테스트 (skip 후 재작성)
- `frontend/src/components/**/*.test.tsx` — 새 IA 깨지는 것 it.skip

---

## 6. 검증 (강민 직접)

- 7탭 → 3그룹 + 11서브탭 IA 정상 렌더 (master/manager 둘 다)
- 11종 차트 새 위치에서 정상 표시
- 미연동 2개 서브탭 placeholder 정상 + 다른 서브탭 클릭 시 영향 X
- 딥링크 (`/dashboard?group=analyze&sub=market`) 새로고침 시 위치 복원
- ABM 탭 기존 동작 그대로 (vacancy_evaluation 호출 + 시각화)
- null 값 위치 모두 `—` (mock fallback 0)
- master `by 매니저명` 배지 (직전 cycle, simulation_history) 그대로 동작
- manager 권한 (직전 cycle) 그대로
- `npx tsc --noEmit` EXIT=0
- `npx vitest run` — skip 처리한 것 제외 모두 통과

---

## 7. 리스크 / 트레이드오프

- **PDF 핵심 약속 (25초 우선 활성) 미달** — 사용자 의식적 결정. backend 분리 별 cycle (Phase 1 — B1 예진).
- **vitest skip 누적** — 안정화 후 재작성 별 cycle. 그때까지 회귀 보호 약화
- **Mental model 변화** — 사용자 (본부 영업팀장) 가 도메인별(7탭) 익숙해진 상태에서 출처별(3그룹) 적응 곡선. 단 현재 베타 단계라 부담 작음
- **React.lazy + 새 그룹/서브탭 분리** — 코드 스플릿 부수 효과. 메인 chunk size 감소 가능 (Phase 2 일부 자연 달성)

---

## 8. References

- PDF: `Data_Source_and_UI_Restructuring_Plan.pdf`
- chichi 회신: 디스코드/슬랙 (사용자 보관)
- 직전 cycles:
  - `docs/superpowers/specs/2026-04-28-master-manager-permission-design.md`
  - 메모리: `project_dashboard_tab_restructure.md`, `project_dashboard_11_charts.md`
- 무효화: 직전 brainstorming 의 (a-2) 7탭 progressive 결정

---

## 9. 다음 단계

1. **사용자 review** — 이 spec 검토 + 이견 회신
2. spec 승인 시 → `superpowers:writing-plans` 진입 → 12-15 task bite-sized plan 작성
3. plan 승인 시 → `superpowers:subagent-driven-development` 진입 → task 단위 implementation
4. 작업 완료 후 PR `feature/dashboard-3group-ia` → `dev`
