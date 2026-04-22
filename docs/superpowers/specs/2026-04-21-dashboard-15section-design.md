# SPOTTER 대시보드 15 섹션 통합 리포트 — 설계 스펙

**작성일**: 2026-04-21
**담당**: C1 (강민) — `frontend/` + 백엔드 4 필드 보강 (수정 허가 받음)
**기준 문서**: v2 지시서 (2026-04-21, 프로젝트 컨텍스트 정합)
**상태**: 설계 승인 완료, 구현 계획 대기

---

## 1. 배경 및 목표

SPOTTER 시뮬레이션 결과 화면은 현재 `App.tsx` 7,567줄 내 `SimulatorDashboard` 함수(line 2236~) 내부에 인라인 구현돼 있다. 최근 3개 신규 에이전트(`demographic_depth` / `trend_forecaster` / `competitor_intel`)가 추가되고, 각종 신규 카드(AI Verdict, closure_risk, legal articles drawer 등)가 누적되면서 **정보 밀도·시선 흐름·페르소나(B2B 본사 영업팀) 정합성이 흐려진 상태**다.

이 작업은 결과 리포트를 **15 섹션의 통합 레이아웃**으로 전면 재구성하는 동시에, 흩어진 기존 구현을 섹션별 컴포넌트로 이관해 유지보수성을 회복한다. 목표:

- **실데이터 연동 최대화**: mock 하드코딩을 실 API 응답 파생 값으로 전면 교체
- **최적 시각화**: 각 섹션의 데이터 성격(시계열·분포·순위·지리)에 맞는 표/그래프 선택
- **페르소나 정합**: 프랜차이즈 본사 영업팀 매니저가 "네트워크 전체 이득"을 판단하기 쉽게
- **기존 기능 100% 보존**: VS 비교 / PDF·XLSX / AI Verdict / Legal 14 / QuarterlyProjection / SHAP / 시나리오 3종 등

## 2. 전제 및 제약

- **담당 영역**: C1(강민) `frontend/` 단독 작업. 백엔드 4 필드 보강은 수정 허가 받았으므로 본인이 직접 처리.
- **페르소나**: 프랜차이즈 본사 영업팀 매니저 (창업자 아님). "이 자리 들어가도 돼?" 톤 금지. "네트워크 전체에 이득이야?" 톤 유지.
- **디자인 토큰**: Zinc base + Amber 강조. 인라인 hex 금지. Pretendard + lucide-react + Recharts + Framer Motion + Zustand 외 의존성 추가 없음.
- **기존 보존 (절대)**:
  - VS 비교 모드 토글 / PDF · XLSX 다운로드 / AI Verdict 신호등
  - 7대 지표 레이더 / QuarterlyProjection / ShapChart / Legal 14항목 (조항 본문 전부)
  - 시나리오 3종 / FloatingWidget / BeforeUnloadGuard / ToastHost / useCompletionToast / simulationStore / SimulationContext / ProtectedRoute / VITE_USE_MOCK 동작
- **변경**: 기존 "AI 애널리스트 종합의견" 블록은 §11 Agent Attribution 카드 그리드로 대체 (하드룰).

## 3. 확정된 설계 결정 (Q&A 이력)

| 항목 | 결정 |
|-----|------|
| 일정 | 여유 / Big Bang 접근법 |
| §05 Map | 카카오맵 전면 도입 + 에이전트 아이콘·레이저 제거 |
| §11 데이터 소스 | 백엔드 `agent_attributions[]` 필드 신설 (C 옵션) |
| §11 카드 배치 | §11 독립 overview 그리드 + 섹션별 compact 카드 양쪽 배치 |
| §03 KPI 전략 | 기존 4 StatCard 폐기 → v2 5 KPI로 리매핑 (C) |
| §03 매출잠재력 표시 | 금액 먼저 + 등급 배지 (B) |
| §03 법률안전도 | `overall_legal_risk` 배지 그대로 (B) |
| §13 Legal 시각화 | 테이블 뷰 + 우측 드로어 (C). 아코디언 없음 |
| demographic 배치 | §04 Scorecard + §13 narrative 양쪽 |
| closure_risk 배치 | §10 Timeline 메인 + §13 경고 요약 |
| trend_forecaster 배치 | §10 단독 + §11 그리드 포함 |

## 4. 아키텍처 & 파일 구조

```
frontend/src/
├── pages/
│   └── SimulatorDashboard.tsx           🆕 App.tsx에서 추출 (입력 + 결과 컨테이너)
│
├── components/
│   ├── AgentMapVisualizer.tsx           ♻️ 카카오맵 리팩터 (기존 D3 폐기)
│   └── SimulationResult/
│       ├── IntegratedReport.tsx         🆕 15 섹션 orchestrator
│       ├── sections/
│       │   ├── CommandBar.tsx           §01
│       │   ├── HeadlineBlock.tsx        §02
│       │   ├── PrimaryKPIs.tsx          §03 (5 KPI)
│       │   ├── Scorecard.tsx            §04
│       │   ├── MapSection.tsx           §05 (카카오맵)
│       │   ├── IndicatorGrid.tsx        §06 (7대 지표)
│       │   ├── QuarterlyForecast.tsx    §07
│       │   ├── ScenarioSplit.tsx        §08
│       │   ├── ShapContribution.tsx     §09
│       │   ├── TimelineForecast.tsx     §10
│       │   ├── AgentAttribution.tsx     §11 (8 카드 그리드)
│       │   ├── DistrictRankings.tsx     §12
│       │   ├── InsightsGrid.tsx         §13 (Legal 테이블 + 드로어)
│       │   ├── DecisionMemo.tsx         §14 (라이트 톤 isolated)
│       │   └── ReportFooter.tsx         §15
│       ├── shared/
│       │   ├── SectionLabel.tsx
│       │   ├── Sparkline.tsx
│       │   ├── AgentCard.tsx            full/compact variant
│       │   └── LegalDrawer.tsx
│       └── (기존 유지) QuarterlyProjectionChart.tsx / ShapChart.tsx / MetricCharts.tsx / ReportViewer.tsx
│
└── types/index.ts                       🆕 AgentId / AgentAttribution / AgentKind / ReportSection / TimelineEvent 타입 추가
```

**App.tsx**: 7,567줄 → 약 5,000줄 (SimulatorDashboard 추출). 다른 페이지 함수(IntroScene/About/Explore/JoinUs/LoginPage) 미변경.

**신규 의존성**: 카카오맵 JS SDK (이미 `.env`에 `VITE_KAKAO_MAP_API_KEY` 설정됨). Vite 동적 로드 방식 사용 → 다른 페이지 번들에는 포함 안 됨.

## 5. 데이터 바인딩 (15 섹션 × 실 백엔드 응답)

**원칙**: mock 하드코딩 0. 모두 실 API 응답에서 파생. 필드 없으면 명시적 empty state.

### §01 ~ §05 (상단)

| § | 소스 |
|---|---|
| §01 CommandBar | `simulationStore.{runId, startedAt, phase}` + `simResult.agent_attributions.length` + VS 비교 토글 + PDF/XLSX 버튼 |
| §02 Headline | `simResult.ai_recommendation` (첫 문장=headline, 나머지=pull-quote) + `overall_legal_risk` + `competitor_intel.market_entry_signal` + `winner_district` |
| §03 PrimaryKPIs | 매출잠재력: `quarterly_projection[0].revenue` + `market_report.estimated_revenue` 등급 / 임대료: `market_report.rent_affordability` / 경쟁강도: `competitor_intel.competition_500m.saturation_score/saturation_level` / 법률안전도: `overall_legal_risk` / 전망: `trend_forecast.forecast.{score, direction}` |
| §04 Scorecard | `demographic_report.{brand_target_match_score, core_demographic}` + `analysis_metrics` 5영역 그룹핑 (매출/인구/경쟁/법률/트렌드) |
| §05 MapSection | `winner_district` 좌표 + `competitor_intel.competition_500m.samples[].{lat,lng}` + `scouting_results[].{district,score,closure_rate}` → 16동 choropleth |

### §06 ~ §10 (중단)

| § | 소스 | 시각화 |
|---|---|---|
| §06 IndicatorGrid | `market_report.{floating_population, rent_index, competition_intensity, estimated_revenue, closure_rate, growth_potential, accessibility}` (7지표 0-100) | Recharts RadarChart + 하단 AgentCard compact 3 (market / population / district_ranking) |
| §07 QuarterlyForecast | `quarterly_projection[]` + `scenarios.base` line | 기존 QuarterlyProjectionChart (LineChart + confidence band) + 하단 AgentCard compact 2 (trend / demographic) |
| §08 ScenarioSplit | `scenarios.{optimistic, base, pessimistic}` | Recharts ComposedChart (3 라인 병렬 또는 stacked) + AgentCard compact 1 (synthesis) |
| §09 ShapContribution | `shap_result.feature_importance[]` | 기존 ShapChart (horizontal bar) + AgentCard compact 2 (demographic / competitor) |
| §10 TimelineForecast | `trend_forecast.{industry_trend, change_ix, macro, forecast}` + `closure_risk.top_signals[]` 경고 | Recharts ComposedChart (6/12/24개월 타임라인 + 이벤트 마커) |

### §11 ~ §15 (하단)

| § | 소스 | 시각화 |
|---|---|---|
| §11 AgentAttribution | `simResult.agent_attributions[]` (백엔드 신설, 길이 8) | AgentCard full 8 그리드 (xl:grid-cols-4 md:grid-cols-2) |
| §12 DistrictRankings | `scouting_results[]` + `top_3_candidates`. VS 모드에서 `comparison[]` | 테이블 기본 + VS ON 시 선택 동 2~4개 병렬 컬럼 (기존 DashboardPanelView 재활용) |
| §13 InsightsGrid | `legal_info[14]` + `competitor_intel.{key_opportunities, key_risks, recommended_actions}` + `closure_risk.top_signals[]` | 탭 토글 (Legal/AI 인사이트/경쟁 리스크). Legal 탭: 14행 테이블 + 우측 드로어 |
| §14 DecisionMemo | 위 전부 집계 | GO/HOLD/NO + 근거 3 + 다음 액션 3. 라이트 톤 isolated `bg-zinc-50` |
| §15 ReportFooter | PDF/XLSX export 핸들러 | 정적 + 버튼 |

### Empty state 규약 (공통)

- `null` / `undefined` / `[]` / `all zero`: 섹션 회색 패널 + `"데이터 없음 — [이유]"` 메시지
- 부분 데이터: 채워진 것만 렌더, 누락은 `—` 표시
- 에러: `"분석 중 오류가 발생했습니다 · 새로고침"` + 재시도 버튼 (§05 지도, §11 에이전트 카드 등)

## 6. 백엔드 보강 필요 필드 (C1 직접 작업)

| # | 필드 | 섹션 | 구현 |
|---|-----|------|------|
| 1 | `agent_attributions: AgentAttribution[]` (길이 8 보장) | §11 + 섹션별 compact | 각 에이전트 노드가 `verdict`/`reasoning` 기록 → `parallel_analysis_node`가 수집 → `synthesis_node`가 response에 포함 |
| 2 | `competitor_intel.samples[].{lat, lng}` | §05 경쟁점 마커 | 이미 `kakao_store`에 있음 → `commercial_intelligence.py`의 `analyze_competition` 반환에 `lat/lng` 노출만 |
| 3 | `scenarios: {optimistic, base, pessimistic}` (각 `quarterly[]` + `probability?`) | §08 | 이미 있다면 확인만. 없으면 `scenarios.py` (신규) + synthesis에 연결 |
| 4 | `legal_info[].checklist: string[]` (선택: `isRequired: boolean`) | §13 드로어 창업 체크리스트 | 봉환 PR #80에 포함됐을 가능성 높음. 실측 후 없으면 `legal_node`에서 조문별 체크리스트 생성 |

### `AgentAttribution` 타입 (백엔드 공통)

```ts
type AgentId =
  | 'market_analyst' | 'population_analyst' | 'legal' | 'district_ranking' | 'synthesis'
  | 'demographic_depth' | 'trend_forecaster' | 'competitor_intel';
type AgentKind = 'LLM' | 'Python' | 'Hybrid' | 'RAG';

interface AgentAttribution {
  id: AgentId;
  display_name: string;
  kind: AgentKind;
  sources: string[];       // ["district_sales", "seoul_realtime_hotspots", ...]
  verdict: string;         // 한 줄 판단 (80자 내)
  reasoning: string;       // 2~3 문장 설명
  confidence?: number;     // 0-1 옵션
}
```

## 7. §05 MapSection 상세

### 스택
- 카카오맵 JS SDK (`.env`의 `VITE_KAKAO_MAP_API_KEY`, Vite 동적 로드)
- 마포 16동 경계 GeoJSON → `public/mapo-dong.geo.json` (공공데이터포털, ~50KB)
- 신규 의존성 0

### 오버레이 레이어 스택 (z-index 하→상)

1. **베이스**: `kakao.maps.Map`, center = `winner_district` 좌표, level 4
2. **마포 16동 choropleth**: Polygon × 16, `scouting_results[].score` 기반 `amber-500/30` ~ `zinc-800/30` 그라데이션
3. **500m 반경 링**: `kakao.maps.Circle`, `strokeStyle:'dash'`, `strokeColor:#f59e0b`, `fillOpacity:0.05`
4. **경쟁점 마커**: CustomOverlay × N, 반경 내부 `bg-amber-500` / 외부 `bg-zinc-600`
5. **타겟 마커 pulse**: CustomOverlay + CSS `@keyframes pulse`
6. **Frosted glass 패널**: 지도 위 `absolute` DOM
   - 좌상단: 타겟 요약 (브랜드/업종/동/점수)
   - 좌하단: 범례 (반경/경쟁점 수/마커 색상 매핑)

### 상호작용

| 액션 | 결과 |
|---|---|
| 동 Polygon 클릭 | InfoWindow (score/closure_rate/BEP) |
| 경쟁점 마커 클릭 | 브랜드명/거리/카테고리 |
| 타겟 마커 클릭 | §01로 scrollIntoView |
| 마우스 휠 | 줌 변경 (오버레이 자동 추종) |

### Fallback

- 카카오 스크립트 로드 실패: 기존 `AgentMapVisualizer` D3 백업 사용 + "지도를 불러올 수 없습니다" 메시지
- `competitors[]` 빈 배열: 타겟 + 반경 원만. 범례에 "반경 500m 내 동종 경쟁점 없음" 표기
- `target.coordinates` null: `winner_district` 이름으로 카카오 Local API 좌표 조회 폴백

### 성능

- `competitors.length > 100` 시 `kakao.maps.MarkerClusterer`
- `IntersectionObserver`로 lazy (첫 렌더 부담 ↓)
- 지도 컨테이너 `height: 520px` 고정

## 8. §11 AgentCard 상세

### 컴포넌트 구조

```tsx
interface AgentCardProps {
  attribution: AgentAttribution;
  size: 'full' | 'compact';
  onExpand?: () => void;
}
```

- **Full** (§11 그리드): header + kind badge + sources chips + verdict (큰 글씨) + reasoning + confidence bar
- **Compact** (섹션 하단): 1줄 (아이콘 + displayName + kind + verdict)

### 아이콘 / 색상 매핑 (lucide-react)

| id | icon | color | kind |
|---|---|---|---|
| `market_analyst` | `TrendingUp` | `text-blue-400` | LLM |
| `population_analyst` | `Users` | `text-emerald-400` | LLM |
| `legal` | `ShieldAlert` | `text-rose-400` | RAG |
| `district_ranking` | `Target` | `text-sky-400` | Python |
| `synthesis` | `Brain` | `text-amber-400` | LLM |
| `demographic_depth` | `UserSearch` | `text-violet-400` | LLM |
| `trend_forecaster` | `LineChart` | `text-cyan-400` | LLM |
| `competitor_intel` | `Crosshair` | `text-orange-400` | Hybrid |

### 섹션별 Compact 배치

| 섹션 | 붙는 에이전트 |
|---|---|
| §06 | market_analyst, population_analyst, district_ranking |
| §07 | trend_forecaster, demographic_depth |
| §08 | synthesis |
| §09 | demographic_depth, competitor_intel |
| §10 | trend_forecaster (§11과 중복 허용) |
| §12 | district_ranking |
| §13 | legal, competitor_intel, trend_forecaster |

## 9. §13 InsightsGrid 상세

### 탭 토글

| 탭 | 내용 | 데이터 |
|---|---|---|
| `legal` (기본) | 14행 테이블 + 우측 드로어 | `legal_info[]` |
| `ai_insights` | 카드 그리드 | 기존 AI 인사이트 이관 |
| `competitor_risks` | key_risks / key_opportunities 2열 대비 | `competitor_intel` |

### Legal Table (14행)

| # | Type | Risk Level | 조문 수 | 체크리스트 | > |
|---|------|-----------|---------|-----------|---|

- 행 left-border 4px로 Risk Level 색상 표시 (red/yellow/green)
- 행 클릭 → 우측 드로어 open + 해당 row `ring-2 ring-amber-500`
- Risk Level 컬럼 정렬 (HIGH→MEDIUM→LOW)
- 색상 단독 X, `● HIGH/MEDIUM/LOW` 라벨 병기

### Legal Drawer

- 너비: `w-[480px]` / 모바일 `w-full`
- Framer Motion slide-in from right
- `role="dialog" aria-modal="true"` + ESC close + focus trap
- 내부:
  1. 헤더 (X 닫기 + 법률 type + Risk 배지)
  2. **조항 본문** (`articles[].{article_ref, content}` 반복, left-border amber)
  3. **창업 체크리스트** (`checklist[]` 체크박스 UI, disabled)
  4. **AI 권고** (`recommendation`)

### 상단 경고 배너 (조건부)

```tsx
{closure_risk?.top_signals && closure_risk.risk_level !== 'safe' && (
  <div className="bg-rose-500/10 border border-rose-500/30 rounded-lg p-4 mb-4">
    <AlertTriangle /> 폐업 위험 신호 + top_signals.slice(0,3) 리스트
  </div>
)}
```

## 10. 디자인 토큰 & 공통 규약

- **팔레트**: Zinc + Amber (인라인 hex 금지)
- **Radius**: 카드 `rounded-lg` / 버튼 `rounded-md` / 드로어 `rounded-l-lg`
- **Spacing**: 카드 `p-4` / 섹션 `py-8` / 그리드 `gap-4`
- **폰트**: Pretendard. 숫자 `text-3xl font-bold`, 헤드 `text-xl font-semibold`, 본문 `text-sm`, 메타 `text-xs text-zinc-400`
- **아이콘**: lucide-react 전용 (이모지 0건)
- **애니메이션**: Framer Motion, 150~300ms
- **차트**: Recharts 전용
- **상태**: Zustand + React Context 기존 패턴
- **반응형**: `max-w-7xl mx-auto` + `xl:grid-cols-N md:grid-cols-2`

## 11. 성공 기준 (Acceptance)

1. ✅ 15 섹션 모두 렌더, 각 섹션은 백엔드 응답에서 파생된 실데이터 표시 (mock 폴백은 유지되지만 기본은 실데이터)
2. ✅ 기존 기능 100% 보존:
   - VS 비교 모드 토글 동작
   - PDF/XLSX 다운로드 시트 구성 유지
   - AI Verdict 신호등 (GO/HOLD/NO) 동작
   - Legal 14/14 항목 전부 + 조항 본문
   - QuarterlyProjection / ShapChart / MetricCharts 재사용
   - FloatingWidget / BeforeUnloadGuard / ToastHost / simulationStore
   - ProtectedRoute / VITE_USE_MOCK 양쪽
3. ✅ 페르소나(B2B 본사 영업팀) 톤 유지 — 창업자 톤 금지
4. ✅ Zinc/Amber 팔레트 일관 — 인라인 hex 0건
5. ✅ App.tsx는 SimulatorDashboard 영역만 분리. 타 페이지 미변경
6. ✅ 타입 strict, `any` 신규 0건
7. ✅ 기존 vitest 10 테스트 회귀 없음
8. ✅ 카카오맵 스크립트 로드 실패 시 D3 백업 동작
9. ✅ 백엔드 보강 4 필드 (agent_attributions / competitor lat·lng / scenarios / legal checklist) 모두 실 노출

## 12. 테스트 전략

- **vitest 단위 테스트**: 기존 simulationStore 10개 회귀 유지. 신규 단위 테스트는 `AgentCard` / `LegalDrawer` 2개만 (sprop variant + drawer open/close)
- **수동 QA 체크리스트** (v2 §2-C 계승):
  1. 시뮬레이션 실행 → 진행률 → 완료 토스트 → 결과 렌더
  2. VS 비교 모드 토글 양방향 동작
  3. PDF / XLSX 다운로드 정상
  4. §05 카카오맵 + 오버레이 렌더
  5. Legal 14/14 항목 전부 표시 + 드로어 조항 본문 확인
  6. `VITE_USE_MOCK=true/false` 양쪽 크래시 없음
  7. 분석 중 탭 닫기 → BeforeUnload 경고
  8. 분석 중 취소 → AbortController 정상
- **Playwright 재활용**: 기존 `scripts/dashboard_audit.py` 확장해 15 섹션 전체 스크린샷 캡처

## 13. 구현 범위 (Big Bang) vs Out of Scope

**In scope**:
- SimulatorDashboard 추출 + 15 섹션 신설
- 백엔드 4 필드 보강 (C1 직접)
- 카카오맵 도입 + 마포 GeoJSON 배치
- 기존 기능 전부 보존하며 재배치

**Out of scope**:
- 다른 페이지(IntroScene/About/Explore/JoinUs/LoginPage/HQCommandCenter) 수정 금지
- `index.css` / `tailwind.config.js` 토큰 값 변경 없음 (추가는 허용)
- 차트/지도/애니메이션 라이브러리 신규 도입 없음
- `AgentMapVisualizer`의 D3 시각화 완전 삭제 금지 (카카오맵 실패 시 폴백으로 유지)

## 14. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| 카카오맵 JS SDK 로드 실패 | 기존 `AgentMapVisualizer` D3 폴백 유지 + 에러 메시지 |
| 백엔드 4 필드 작업 중 충돌 | 프론트 fallback 먼저 구현 → 필드 오면 자동 전환 |
| App.tsx 분리 중 기존 기능 파손 | 추출 후 기존 렌더 경로 유지 → 각 섹션 점진 치환 |
| 페르소나 톤 훼손 | 카피·라벨 검토 체크리스트 (§2-C 수동 QA) |
| 기존 테스트 회귀 | 기존 10개 vitest 보존 확인 CI |

## 15. 다음 단계

1. 이 스펙 승인 후 `writing-plans` 스킬로 구현 계획 작성
2. 구현 계획 확정 후 subagent-driven execution (메모리 선호)
3. 백엔드 4 필드 보강은 별도 step (프론트 UI 뼈대 완성 후 또는 병행)

---

**참고**: Agent Attribution 8 에이전트 상세·아이콘·색상 매핑, §05 카카오맵 오버레이 스택, §13 Legal 드로어 상세 스펙은 §7~§9에 명시. 구현 단계에서 이 스펙을 기준으로 참조.
