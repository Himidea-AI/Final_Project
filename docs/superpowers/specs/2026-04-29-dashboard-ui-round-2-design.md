# Dashboard UI 정합성 Round 2 — Design

**일자**: 2026-04-29
**담당**: C1 강민 (frontend)
**관련 PR**: #142 (analyze-llm 마이그레이션) 머지 후 / 또는 동시 진행
**관련 spec**: 기존 Hub Redesign + 3그룹 IA 위에 정합성 패치

## 1. Summary

본부 영업팀 시연 검증 후 발견된 UI 정합성 + 데이터 정확성 항목 7개 묶음. 핵심 = **데이터 진실성** (분석 신뢰도 0.85 하드코딩 제거, 다중 동 표시 누락 fix), **UI 정합성** (마크다운 렌더링, 중복 카드 제거, 위치 정합), **불필요 중복 제거** (예측 요약 탭).

`/predict + /analyze/llm` 마이그레이션 (#142) 후 데이터 흐름 안정화된 상태에서 진행. 합성된 `SimulationOutput` 의 `district_predictions` 활용.

## 2. 변경 항목

### 2.1 react-markdown 도입 (synthesis ai_recommendation)

**문제**: backend 가 `## 추천 입지` 같은 마크다운 H2 헤더를 응답에 포함. frontend 가 plain text 로 렌더 → 헤더가 `## 추천 입지` 그대로 보임.

**해결**: `react-markdown` 패키지 도입. `ai_recommendation` / `final_recommendation` 표시 컴포넌트에서 `<ReactMarkdown>` 사용.

**영향 파일**:
- `frontend/package.json` (패키지 추가)
- `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx` (synthesis 종합 + 최종 권고 섹션)
- 다른 `ai_recommendation` 사용처 (확인 후 적용)

**스타일**: Tailwind `prose-sm prose-invert` plugin — 또는 inline className mapping (h2/h3/p/strong/ul 등).

### 2.2 PredictSummaryTab 제거

**문제**: 예측 요약 탭의 5 KPI (월매출/BEP/폐업위험/유동인구/경쟁강도) 가 다른 4 서브탭 (Sales/Financial/CustomerFlow/Emerging) 에 분산되어 있어 **중복**. 본부 영업팀이 같은 정보 두 번 보는 비효율.

**해결**:
- `PredictGroup` 5 서브탭 → 4 서브탭
- `PredictSummaryTab.tsx` 파일 삭제
- 기본 활성 탭 = Sales (또는 CustomerFlow — 강민 선호)
- 라우팅 경로 `/dashboard/predict?sub=summary` → `/dashboard/predict?sub=sales` 으로 redirect (있으면)

**영향 파일**:
- `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSummaryTab.tsx` (Delete)
- `frontend/src/components/SimulationResult/dashboard/groups/PredictGroup.tsx` (서브탭 list 4개로)
- `frontend/src/types/index.ts` (PredictSubTab enum 에서 'summary' 제거)

### 2.3 QuarterlyProjectionChart — 라벨 + 분기 표시 fix

**문제 1**: 차트 제목 "TCN-v2 분기별 매출 예측" → 사용자에 모델명 노출 (불필요).
**해결**: "분기별 예상 매출" 로 변경.

**문제 2**: 분기가 14개 표시됨 (현재 backend 가 그만큼 보냈거나 frontend slice 누락). 사용자 직관 = 1~4분기.
**해결**: `quarterly_projection.slice(0, 4)` 처리 + X축 라벨 "Q1, Q2, Q3, Q4".

**영향 파일**:
- `frontend/src/components/SimulationResult/QuarterlyProjectionChart.tsx`
- `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx`

### 2.4 QuarterlyProjectionChart — 다중 동 라인 (★)

**문제**: `/predict` 응답이 `data: DistrictPredictionResult[]` (최대 4개 동) 인데 frontend 는 `simResult.quarterly_projection` (단일 동, winner 만) 표시. **나머지 동 데이터 누락**.

**해결**:
- `QuarterlyProjectionChart` props 변경:
  ```typescript
  // before
  data: QuarterlyProjection[]
  // after
  data: { district: string; projection: QuarterlyProjection[] }[]
  ```
- 각 동별 별도 `<Line>` (recharts) — 색상 indigo / cyan / amber / rose (4동 한정)
- 범례 표시 (동 이름)
- **신뢰구간 (Area)** — 범례 + 단일 동 선택 토글 또는 winner 만 음영. C1 재량 (선택).

**호출처 변경**: `PredictSalesForecastTab` 에서 `simResult.district_predictions` 사용:
```tsx
<QuarterlyProjectionChart
  data={(simResult.district_predictions ?? [])
    .filter((p) => !p.is_excluded_combo)
    .map((p) => ({ district: p.district, projection: p.quarterly_projection ?? [] }))}
  winnerDistrict={simResult.winner_district}
/>
```

**영향 파일**:
- `frontend/src/components/SimulationResult/QuarterlyProjectionChart.tsx`
- `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictSalesForecastTab.tsx`

### 2.5 유동인구피크 (PeakHourCard) 위치 이동

**문제**: `living_pop_forecast` 의 PeakHourCard 가 [AI 분석] - [인구분석] (`DemographicTab`) 에 있음. 유동인구 = 예측 영역이 자연스러움.

**해결**:
- `DemographicTab.tsx` L145 부근의 PeakHourCard 패널 제거
- `PredictCustomerFlowTab.tsx` 에 PeakHourCard 추가 (이미 `modelName="customer_revenue + living_pop_forecast"` 텍스트는 있음 — 차트 본체 추가)

**영향 파일**:
- `frontend/src/components/SimulationResult/dashboard/tabs/DemographicTab.tsx` (제거)
- `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictCustomerFlowTab.tsx` (추가)

### 2.6 분석 신뢰도 완전 제거

**문제**: backend `synthesis.py` 의 `confidence=0.85` **하드코딩 placeholder**. 모든 시뮬에서 동일 값. 본부 영업팀에 "AI 85% 확신" misleading.

**해결**: frontend 에서 분석 신뢰도 표시 자체 제거.
- `PredictFinancialSimTab.tsx`:
  - `synthAttr.confidence` 추출 + `confidencePct` 변수 제거
  - `<ProfitSimulationPanelFull confidencePct={...}>` prop 제거
- `ProfitSimulationPanelFull` 컴포넌트 (재무 시뮬 전체 패널):
  - `confidencePct` prop 제거
  - "분석 신뢰도" 라벨 + 진행바 영역 제거

향후 backend 가 실 confidence 산출하면 별도 cycle 에서 다시 추가 가능.

**영향 파일**:
- `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictFinancialSimTab.tsx`
- (`ProfitSimulationPanelFull` 정의 위치 — 같은 파일 내부 또는 별도 파일)

### 2.7 AnalyzeAiSummaryTab 레이아웃 — EntrySignalLight 제거 + 상하 위치 변경

**문제**:
1. **창업 진입 신호 (EntrySignalLight)** 가 LLM 출처 통합 판단 (DecisionCard) 과 모순 (STOP vs 진입 권장 동시 표시) — 사용자 혼란
2. 현재 상단 = 좌(LLM)/우(Entry), 하단 = synthesis. 영업팀장은 종합 결론 먼저 보고 근거를 보조로 보는 흐름이 자연스러움

**해결**:
- `EntrySignalLight` 카드 제거 (DecisionCard 가 같은 정보 제공, 더 정확)
- 위치 변경: **상단 = synthesis 종합 + 최종 권고**, **하단 = LLM 출처 통합 판단 (DecisionCard)** — 보조 카드처럼

**영향 파일**:
- `frontend/src/components/SimulationResult/dashboard/sub/analyze/AnalyzeAiSummaryTab.tsx`

## 3. 영향 없는 컴포넌트

이미 `useCombinedSimResult` 합성 결과를 받는 컴포넌트는 prop 인터페이스 보존 → 변경 0:
- DashboardHub, DashboardOutlet
- AbmGroup
- MapSection, MarketMap (어제 fix 완료)
- DistrictRankings (#142 의 ExcludedCombo 처리 완료)

## 4. Test Plan

### 4.1 자동
- tsc EXIT=0
- vitest 풀 — 기존 테스트 + 마이그레이션 9건 통과 유지
- build EXIT=0

### 4.2 수동 (강민 직접)
- [ ] AnalyzeAiSummaryTab 의 ai_recommendation 마크다운 렌더 (## 헤더가 H2 로 보임)
- [ ] PredictGroup 4 탭 (Summary 사라짐), 기본 Sales 활성
- [ ] QuarterlyProjectionChart "분기별 예상 매출" 제목 + Q1~Q4 + 다중 동 라인 + 범례
- [ ] PredictCustomerFlowTab 안 PeakHourCard 표시
- [ ] DemographicTab 안 PeakHourCard 사라짐
- [ ] PredictFinancialSimTab 의 "분석 신뢰도 85%" 영역 사라짐
- [ ] AnalyzeAiSummaryTab: 위 synthesis + 최종 권고, 아래 DecisionCard. EntrySignalLight 사라짐
- [ ] (강민) F12 Network 에서 customer-segment 422 detail 확인 → backend 측 fix 요청

## 5. Assumptions

1. `react-markdown` 9.x + `remark-gfm` 도입. Tailwind `@tailwindcss/typography` plugin 또는 inline className mapping. 안전한 plugin 도입 우선 — 기존 design 깨지지 않게.
2. `simResult.district_predictions` 가 `useCombinedSimResult` 합성 결과에 보존됨 (#142 commit `af5eb04` 검증 완료).
3. PredictSummaryTab 제거 후 기본 탭 = Sales. URL `?sub=summary` 진입 시 Sales 로 redirect.
4. Backend `synthesis.py` 의 `confidence=0.85` 하드코딩 → frontend 에서 표시 제거. 향후 backend 가 실 산출하면 별도 cycle.
5. `EntrySignalLight` 컴포넌트 자체는 삭제 X (다른 곳에서 쓰일 수도) — AnalyzeAiSummaryTab 에서만 호출 제거. 사용처 0 이면 후속 dead code 정리 가능.

## 6. 마이그레이션 단계 (plan 에서 세부화)

| Task | 작업 | 영향 |
|------|------|------|
| 1 | react-markdown 패키지 설치 + AnalyzeAiSummaryTab synthesis 텍스트 마크다운 렌더 | 패키지 + 1 컴포넌트 |
| 2 | PredictSummaryTab 제거 + PredictGroup 4탭 정리 | 1 파일 삭제 + 2 파일 수정 |
| 3 | QuarterlyProjectionChart 라벨 + 분기 1~4 표시 fix | 1~2 파일 |
| 4 | QuarterlyProjectionChart 다중 동 라인 + 범례 | 큰 변경 — 1 파일 + 호출처 |
| 5 | 유동인구피크 위치 이동 (Demographic → CustomerFlow) | 2 파일 |
| 6 | 분석 신뢰도 제거 | 1~2 파일 |
| 7 | AnalyzeAiSummaryTab 레이아웃 — EntrySignalLight 제거 + 상하 변경 | 1 파일 |
| 8 | 정합성 검증 (tsc + vitest + build) | 검증만 |

각 task plan 에서 step-by-step 세부화.
