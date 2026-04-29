# 사용자 입력 → 백엔드 → 응답 → 프론트 렌더 — End-to-End 데이터 흐름 단절 분석

**작성일:** 2026-04-28
**작성자:** A1 찬영
**브랜치:** `IM3-243-dong-fk-followup`
**대상:** 사용자가 시뮬레이션 화면에서 입력한 값이 백엔드까지 정확히 전달되고, 응답이 정확히 화면에 표시되는지 전 계층 검증
**관련 issue:** [2026-04-28-summary-tab-empty-cards.md](./2026-04-28-summary-tab-empty-cards.md)

---

## 0. Executive Summary

전체 데이터 흐름 5계층(Frontend 입력 → API 요청 → AgentState → 응답 빌더 → Frontend 렌더)을 교차 검증한 결과, **총 24건의 drift/gap**이 발견됐다. 이 중 **7건은 P0/P1 (사용자 화면에 직접 영향)**, 나머지는 P2/P3 (정리·문서화 권장).

### 가장 큰 4가지 단절

| # | 단절 | 위치 | 영향 |
|---|---|---|---|
| **A** | **`final_report` 키가 응답 빌더에서 매핑 안 됨** | `main.py` 응답 빌더 (348~638) | SummaryTab 카드 3, FinancialTab 거의 전체 빈 상태 |
| **B** | **`agent_attributions` 9개 모두 미수집** | `synthesis_node` 출력 + main.py 응답 빌더 | InsightTab 8 에이전트 카드 모두 dashed border |
| **C** | **AgentState TypedDict에 4개 `target_*` 필드 미정의** | `state.py` | 타입 체크 실패 (런타임 동작은 함) |
| **D** | **TS interface에 `target_districts`, `industry_filter` 누락** | `types/index.ts` | 타입 안정성 부재 |

### 가장 큰 결론

- **사용자 입력은 모두 백엔드까지 잘 전달된다** (Frontend → API → state 계층 OK).
- **백엔드 노드들도 결과를 잘 채운다** (분석은 정상 작동).
- **문제는 (1) 응답 빌더가 `final_report`/`agent_attributions`를 응답 dict에 안 옮기는 점**과 **(2) 일부 노드의 모델 추론 실패**에 있다.

---

## 1. 분석 방법

데이터 흐름 5단계를 4개 Explore agent로 병렬 분석:

```
[ Frontend 입력 폼 ]
     ↓ (1) Agent A: Frontend → API request
[ POST /api/simulate body ]
     ↓ (2) Agent B: Pydantic 검증 → AgentState 초기화
[ AgentState ]
     ↓ (3) Agent B: 9개 노드의 read/write
[ state 누적 ]
     ↓ (4) Agent C: 응답 빌더 → SimulationOutput
[ SimulationOutput JSON ]
     ↓ (5) Agent D: Frontend 8 tabs 매핑
[ 사용자 화면 ]
```

**검증 대상:**
- 30+ TypeScript interface (types/index.ts)
- AgentState TypedDict (state.py 35 필드)
- SimulationOutput Pydantic (31 필드, simulation_output.py:126-170)
- 9개 LangGraph 노드 (read/write)
- 8개 dashboard tabs (props 사용 패턴)

---

## 2. 계층별 단절 상세

### 2-1. 계층 ①: Frontend 입력 폼 → API request body

#### ✅ 잘 되는 부분
- App.tsx:800-858의 **13개 useState 변수가 모두 params에 포함**되어 전송됨 (App.tsx:1351-1373)
- target_age_groups, target_gender, target_time_slots, target_day_type, target_monthly_sales 모두 정상 전송

#### ❌ Drift 발견

**Drift #1 — TS interface에 2개 필드 누락 (P1, HIGH)**

`frontend/src/types/index.ts:6-28`의 `SimulationInput` interface가 2개 필드 미정의:

| 필드 | App.tsx 전송 | TS interface | Pydantic | 상태 |
|---|---|---|---|---|
| `target_districts` | ✅ (line 1355) | ❌ 미정의 | ✅ | **TS 타입 안정성 부재** |
| `industry_filter` | ✅ (line 1366) | ❌ 미정의 | ✅ | **TS 타입 안정성 부재** |

**영향**: 런타임 동작은 OK (axios가 dict 그대로 전송). 단 TypeScript 컴파일 시 타입 검증 안 됨 → 오타·필드명 변경 시 IDE 경고 없이 통과.

**해결**: `types/index.ts`에 2줄 추가 (5분 작업)
```typescript
target_districts?: string[];
industry_filter?: string | null;
```

---

### 2-2. 계층 ②: API request → AgentState 초기화

#### ✅ 잘 되는 부분
- Pydantic SimulationInput (`simulation_input.py:16-51`)이 17개 필드 모두 수용
- `main.py:303-338`에서 5개 target_* 필드를 모두 state에 주입

#### ❌ Drift 발견

**Drift #2 — `existing_stores` 항상 빈 배열로 강제 (P2, MEDIUM)**

`backend/src/main.py:1356`:
```python
"existing_stores": [],   # ← 사용자 입력 무시, 빈 배열로 강제
```

**원인**: 의도적 TODO (기존 매장 분석 미구현). 코드 주석에 명시 필요.

**Drift #3 — `scenarios` 필드 AgentState 미정의 (P3, LOW)**

`backend/src/schemas/state.py`의 `AgentState` TypedDict에 `scenarios` 필드 정의 없음. 사용자가 `scenarios: ["base"]` 보내도 state로 전달 안 됨.

**영향**: 현재 항상 ["base"] 단일 시나리오로 동작 → 응답 빌더가 별도로 `build_scenarios()` 호출. 미래 확장 시 (낙관/기본/비관 명시적 선택) 필요.

**Drift #4 — AgentState TypedDict에 4개 `target_*` 필드 미정의 (P0, CRITICAL)**

`state.py`에 다음 필드들이 **TypedDict 선언에 없음**:

| 필드 | main.py 주입 | state.py 정의 | 노드 사용 |
|---|---|---|---|
| `target_age_groups` | ✅ line 333 | ❌ | ✅ graph.py:200 |
| `target_gender` | ✅ line 334 | ❌ | ✅ graph.py:201 |
| `target_time_slots` | ✅ line 335 | ❌ | ✅ graph.py:202 |
| `target_day_type` | ✅ line 336 | ❌ | ✅ graph.py:203 |
| `target_monthly_sales` | ✅ line 337 | ❌ | ❌ **어느 노드도 사용 안 함** |

**영향**:
- 런타임 동작 OK (TypedDict는 dict 호환이라 필드 추가 가능)
- 타입 체커(mypy/pyright) 경고 발생
- `target_monthly_sales`는 **dead state** (입력 받아 무시됨)

**해결**: `state.py`에 5필드 추가 + `target_monthly_sales` 사용처 명확화 (또는 input 스키마에서 제거).

---

### 2-3. 계층 ③: AgentState → 9개 노드 read/write

#### ✅ 잘 되는 부분
- Phase 0 (operational_fit) → Phase 3 (synthesis) 5단계 데이터 흐름 정상
- 각 노드가 필요한 state 필드 읽고 결과를 명확히 채움

#### ❌ Drift 발견

**Drift #5 — `customer_segment` 저장 슬롯 미정의 (P2, MEDIUM)**

`models/interface.py:_run_customer_revenue()` 결과가 `sim_result["customer_segment"]`에 저장되지만, AgentState 자체에는 `customer_segment` 슬롯이 없음. 응답 빌더가 `state.tcn_sim_result.customer_segment`로 접근.

**해결**: AgentState에 `customer_segment_result: dict | None` 슬롯 추가 → 명시성 향상.

**Drift #6 — Dead state 필드 3건 (P3, LOW)**

| 필드 | 정의 위치 | 사용 노드 | 상태 |
|---|---|---|---|
| `brand_analysis` | state.py:48 | ❌ 어느 노드도 안 채움/안 읽음 | Dead — 메모리 낭비 |
| `next_step` | state.py:57 | ❌ Supervisor 라우팅 미사용 | Dead — 미구현 supervisor |
| `target_monthly_sales` | main.py:337 | ❌ 어느 노드도 안 읽음 | Dead — 사용자 입력 무시 |

**해결**: 정리 또는 사용처 추가.

**Drift #7 — `existing_stores`, `scenarios` 입력 dead end (P2, MEDIUM)**

사용자가 입력해도:
- `existing_stores` → main.py:1356에서 강제 `[]`
- `scenarios` → state.py에 슬롯 자체 없음

→ 어느 노드도 이 두 필드를 못 봄.

**Drift #8 — Phase 2 노드들의 `*_result` 키가 synthesis에 미수집 (P0, CRITICAL)**

각 노드(market_analyst, population_analyst, demographic_depth, trend_forecaster, competitor_intel, operational_fit, district_ranking, legal)가 `state.analysis_results["{node}_result"]`에 attribution을 채운다. 그러나 `synthesis_node`가 이를 9개 배열로 묶어 `state.agent_attributions`에 저장하지 않음.

**결과**: 응답 빌더(`main.py:634`)가 `state.get("agent_attributions") or []`로 조회 시 항상 **빈 배열 `[]`** 반환.

**영향**: **InsightTab의 8개 에이전트 카드 모두 dashed border + opacity-60 (line 70-73)** — 사용자가 "분석 진행 안 됨" 으로 오해.

---

### 2-4. 계층 ④: state → SimulationOutput 응답 빌더

#### ✅ 잘 되는 부분
- 30+ Pydantic 필드 중 25개 정상 매핑
- `legal_risks`, `district_rankings`, `competitor_intel`, `market_report`, `demographic_report`, `quarterly_projection`, `customer_segment`, `living_pop_forecast`, `emerging_signal`, `closure_rate`, `closure_risk`, `shap_result` 등 응답 정상

#### ❌ Drift 발견

**Drift #9 — `final_report` 키가 응답 dict에 매핑 안 됨 (P0, CRITICAL)** ⚠️

이게 가장 큰 단절. 코드 추적 결과:

1. `synthesis_node` (synthesis.py:332) 가 정상으로 채움:
```python
new_analysis_results["final_report"] = final_strategy.model_dump()
```

2. `main.py:348-638`의 응답 빌더에서 `response_data` dict에 **`final_report` 키를 추가하는 코드 자체가 없음**.

3. 결과: 응답 JSON에 `final_report` 키가 통째로 누락.

**영향**:
- **SummaryTab 카드 2 (매출)**: `monthlyRev = ps?.monthly_revenue` (`fr?.profit_simulation` 의존) → null → "—"
- **SummaryTab 카드 3 (BEP)**: `bepMonths = ps?.bep_months` → null → "—"
- **FinancialTab**: `final_report.profit_simulation` → null → ProfitSimulationPanelFull 모든 값 "—"

**해결**: main.py 응답 빌더에 1줄 추가:
```python
"final_report": state.get("analysis_results", {}).get("final_report"),
```

**Drift #10 — `quarterly_projection` 길이 16 vs frontend 4 하드코딩 (P1, HIGH)**

`build_quarterly_projection()` (simulation.py:94-120)가 `bep_quarterly_simulation` 길이만큼 (보통 16분기) 반환. 그러나:

- SummaryTab.tsx:83: `hasQp = fullQuarters.length === 4` ❌
- ForecastTab.tsx:82: `qp = simResult.quarterly_projection ?? []` ✅

**영향**: SummaryTab 카드 2가 `=== 4` 매칭 실패 → `hasPartialQp` 분기 → "4분기 중 16분기" 같이 모호한 표시.

**해결**: SummaryTab.tsx:83의 `=== 4` 를 `>= 1` 또는 `>= 4` 로 변경 (1줄 수정).

**Drift #11 — `agent_attributions` 응답에 빈 배열 (P0, CRITICAL)**

상위 Drift #8과 연결. 응답 빌더가 `state.agent_attributions` 또는 `state.analysis_results.agent_attributions`를 읽으려 하지만 둘 다 비어 있음 → `[]`.

**영향**: InsightTab의 8개 에이전트 카드 모두 dashed border, AgentConfidenceRadar 0/8 진행률.

**해결**: synthesis_node가 9개 노드의 `*_result` 키를 모아 `state.agent_attributions = [...]`로 set. 또는 응답 빌더에서 직접 수집.

**Drift #12 — `scenarios`/`trend_forecast`/`financial_report` 빈 객체 (P1, HIGH)**

| 필드 | 응답 상태 | 원인 |
|---|---|---|
| `scenarios` | `{}` | `build_scenarios()` 가 quarterly_predictions 비어있을 때 빈 dict 반환 |
| `trend_forecast` | `{}` | trend_forecaster_node 가 Redis 캐시/LLM 실패 시 빈 dict 설정 |
| `financial_report` | `{}` | `state.market_data["financial_metrics"]`가 채워지지 않음 (market_analyst가 안 채움) |

**해결**:
- `scenarios`: build_scenarios 내부 fallback 강화 (quarterly_predictions 검증)
- `trend_forecast`: trend_forecaster fail 진단 (LLM 호출 실패 케이스)
- `financial_report`: market_analyst가 채우도록 수정 또는 final_report.profit_simulation으로 통일

**Drift #13 — Dead Response 필드 6건 (P3, LOW)**

응답 빌더가 채우는데 어느 frontend 탭도 사용 안 함:

| 필드 | 응답 상태 | 사용처 |
|---|---|---|
| `comparison` | DistrictComparison[] 채워짐 | ❌ Dead |
| `analysis_report` | LLM 줄글 텍스트 채워짐 | ❌ Dead |
| `analysis_metrics` | 정량 지표 dict 채워짐 | ❌ Dead (frontend는 별도 *_report 필드만 사용) |
| `simulation_quarters` | int 채워짐 | ❌ Dead |
| `is_excluded_combo` | bool 채워짐 | ❌ Dead |
| `map_data` | center+markers 채워짐 | ❌ Dead (any 타입) |
| `request_id` | UUID 채워짐 | ❌ Dead (UI 미표시) |
| `all_competitor_locations` | dict[] 채워짐 | ❌ Dead (정의 명확하나 미사용) |

**해결**: frontend 탭에 노출 또는 응답에서 제거 (백엔드와 협의).

**Drift #14 — Phase 2 노드의 일부 결과 응답 미포함 (P2, MEDIUM)**

| 노드 출력 | state 키 | 응답 매핑 |
|---|---|---|
| market_analyst | `analysis_results["market_report"]` | ❌ 사용 안 함 (analysis_metrics가 우선) |
| population_analyst | `analysis_results["population_report"]` | ❌ 사용 안 함 |
| 각 노드 | `analysis_results["{node}_result"]` | ❌ 사용 안 함 (Drift #8 연결) |

**Drift #15 — `competitor_intel` state 키 이름 차이 (P3, LOW)**

- state 키: `competitor_intel_result`
- 응답 키: `competitor_intel`
- main.py:570 line: `"competitor_intel": state.get("competitor_intel_result")`

런타임 OK이나 명명 일관성 부재.

---

### 2-5. 계층 ⑤: 응답 → Frontend 8 tabs

#### ✅ 잘 되는 부분
- 8개 탭 모두 Empty State 폴백 로직 보유
- DemographicTab의 4조건 AND, ForecastTab의 3섹션 조건부 렌더 등 방어 코드 견고

#### ❌ Drift 발견

**Drift #16 — SummaryTab 5 fail (P0, 직전 issue 참조)**

이미 별도 issue로 정리: [`2026-04-28-summary-tab-empty-cards.md`](./2026-04-28-summary-tab-empty-cards.md)

요약:
1. `final_report` 누락 → 카드 3 빈 상태 (Drift #9)
2. `quarterly_projection.length !== 4` → 카드 2 빈 상태 (Drift #10)
3. `competitor_intel.error` → 카드 1 "분석 대기"
4. `customer_segment` null → 카드 1 부수
5. `closure_risk` null → 별도 영향

**Drift #17 — LegalTab의 빈 legal_risks UX (P1, HIGH)**

`LegalTab.tsx:24-66`: `legal_risks=[]`일 때 빈 테이블만 렌더, "법률 리스크 없음" 명확한 메시지 없음.

**영향**: 사용자가 "분석 안 됨" 으로 오해. 진짜로 리스크 없는 케이스인지 데이터 fail인지 구분 불가.

**Drift #18 — DemographicTab 4조건 AND 로직 (P2, MEDIUM)**

`DemographicTab.tsx:57-67`: `!hasAnyComposition && !hasReport && !hasCustomerSegment && !hasLivingPop` 모두 False일 때만 "데이터 없음" 표시. 즉 부분 fail 시 일부 차트만 빈 채로 렌더.

**영향**: 사용자가 어떤 데이터가 없는지 명확히 알기 어려움.

**Drift #19 — FinancialTab의 closure_risk null UX (P1, HIGH)**

`FinancialTab.tsx:199-271` `ClosureRiskPanel`: closure_risk null 시 "closure_risk 분석 대기" 문구만 표시. closure_rate(실측)와 다른 UX → 통일성 부재.

**Drift #20 — TS interface vs 실제 응답 mismatch (P2, MEDIUM)**

응답에는 있지만 TS interface에 명확히 정의되지 않거나 `any`인 필드:
- `map_data: any` (line 307) — 타입 미정의
- `financial_report: Record<string, unknown>` (line 330) — 약타입
- `all_competitor_locations`: 강타입이나 사용처 없음 (line 352-361)

---

## 3. Drift 종합 매트릭스 (24건)

| # | 계층 | Drift | 위치 | 우선순위 | 영향 | 해결 작업량 |
|---|---|---|---|---|---|---|
| 1 | ① | TS interface `target_districts`, `industry_filter` 누락 | types/index.ts:6-28 | P1 | 타입 안정성 | 2줄 추가 |
| 2 | ② | `existing_stores` 빈 배열 강제 | main.py:1356 | P2 | 기존 매장 분석 무시 | 의도적, 주석 추가 |
| 3 | ② | `scenarios` AgentState 미정의 | state.py | P3 | 미래 확장 제약 | 1줄 추가 |
| 4 | ② | `target_*` 4 필드 TypedDict 미정의 | state.py | P0 | 타입 체크 실패 | 5줄 추가 |
| 5 | ③ | `customer_segment` 슬롯 미정의 | state.py | P2 | 명시성 부재 | 1줄 추가 |
| 6 | ③ | `brand_analysis`, `next_step`, `target_monthly_sales` Dead | state.py, main.py | P3 | 메모리 낭비 | 정리 |
| 7 | ③ | `existing_stores`/`scenarios` 입력 dead | state.py + 노드 | P2 | 입력 무시 | 노드 추가 또는 input 제거 |
| 8 | ③ | Phase 2 `*_result` 키들이 synthesis에 미수집 | synthesis.py | P0 | agent_attributions 빈 배열 | 수집 로직 추가 |
| **9** | **④** | **`final_report` 응답 매핑 누락** | **main.py:348-638** | **P0** | **SummaryTab 카드 2,3 + FinancialTab 빈** | **1줄 추가** |
| 10 | ④ | `quarterly_projection` 길이 16 vs 4 | SummaryTab.tsx:83 | P1 | SummaryTab 카드 2 빈 | 1줄 수정 |
| 11 | ④ | `agent_attributions` 빈 배열 | main.py:634 | P0 | InsightTab 8 카드 dashed | Drift #8 fix 시 자동 |
| 12 | ④ | `scenarios`/`trend_forecast`/`financial_report` 빈 객체 | 각 노드 + main.py | P1 | 3 탭 부분 빈 | 노드 fail 진단 |
| 13 | ④ | Dead Response 필드 8건 | main.py 응답 빌더 | P3 | 메모리 낭비 | 정리 |
| 14 | ④ | Phase 2 결과 일부 응답 미포함 | main.py 응답 빌더 | P2 | market_report/population_report 누락 | 매핑 추가 |
| 15 | ④ | `competitor_intel_result` vs `competitor_intel` 명명 차이 | main.py:570 | P3 | 런타임 OK | 문서화 |
| 16 | ⑤ | SummaryTab 5 fail (별도 issue) | SummaryTab.tsx | P0 | 사용자 첫 화면 빈 | 5건 개별 수정 |
| 17 | ⑤ | LegalTab 빈 `legal_risks` UX | LegalTab.tsx:27-68 | P1 | 사용자 혼동 | empty state 메시지 추가 |
| 18 | ⑤ | DemographicTab 4조건 AND | DemographicTab.tsx:57-67 | P2 | 부분 fail 모호 | 개별 fallback |
| 19 | ⑤ | FinancialTab closure_risk null UX | FinancialTab.tsx:199-271 | P1 | UX 통일성 | 메시지 통일 |
| 20 | ⑤ | TS interface 약타입 (any/Record) | types/index.ts:307,330 | P2 | 타입 안정성 | 강타입 정의 |
| 21 | ⑤ | `competitor_intel.competition_500m` null 시 영향 | MarketTab.tsx:154-214 | P2 | 경쟁 분석 제한 | 명확한 fail 메시지 |
| 22 | ⑤ | AbmTab `vacancy_spots=[]` 시 마커 0개 | AbmTab.tsx:54-58 | P2 | 공실 시뮬 빈 | 로드 실패 배너 |
| 23 | ⑤ | InsightTab `agent_attributions=[]` 시 모두 dashed | InsightTab.tsx:18-154 | P0 | 8 카드 모두 빈 | Drift #8/11 fix 시 자동 |
| 24 | ④ | `simulation_quarters: 16` vs `quarterly_projection.length` | main.py + simulation.py | P2 | 길이 정합성 불명 | 진단 |

---

## 4. P0 (즉시 수정) 4건 — 가장 빠른 회복

### P0-1. `final_report` 응답 매핑 추가 (Drift #9)

**파일**: `backend/src/main.py`
**작업**: 응답 빌더(`map_state_to_simulation_output` 또는 같은 함수)에 1줄 추가

```python
# 응답 dict 구성 부분 (대략 line 572~635) 안에 추가
"final_report": state.get("analysis_results", {}).get("final_report"),
```

**효과**: SummaryTab 카드 3 (BEP) + FinancialTab `ProfitSimulationPanelFull` 즉시 부활.

---

### P0-2. SummaryTab `=== 4` 를 `>= 1` 로 (Drift #10)

**파일**: `frontend/src/components/SimulationResult/dashboard/tabs/SummaryTab.tsx`
**작업**: 1줄 수정

```typescript
// L83
- const hasQp = fullQuarters.length === 4;
+ const hasQp = fullQuarters.length >= 4;   // 16분기 환경에서도 정상
```

**효과**: SummaryTab 카드 2 즉시 부활 (16분기 합산 = 연 매출 4년치 → 4분기 합 P50 표시).

> 더 정확하게는 첫 4분기만 합산하도록 추가 수정:
> ```typescript
> const annualRevenue = fullQuarters.slice(0, 4).reduce((sum, q) => sum + (q.revenue ?? 0), 0);
> ```

---

### P0-3. AgentState TypedDict에 `target_*` 4 필드 추가 (Drift #4)

**파일**: `backend/src/schemas/state.py`
**작업**: TypedDict에 5줄 추가

```python
class AgentState(TypedDict):
    # ... 기존 필드들 ...
    target_age_groups: list[str]
    target_gender: str | None
    target_time_slots: list[str]
    target_day_type: str | None
    target_monthly_sales: int | None
```

**효과**: 타입 체크 통과. 런타임 동작 변화 없음 (이미 정상 작동 중).

---

### P0-4. `synthesis_node`가 9개 노드 attribution 수집 (Drift #8, #11)

**파일**: `backend/src/agents/nodes/synthesis.py`
**작업**: 약 20-30줄 추가 — 9개 노드 출력에서 `agent_attribution` 또는 `*_result` 키를 모아 배열화 후 `state["agent_attributions"]`에 저장.

```python
# synthesis_node 내부, final_strategy 계산 후
agent_keys = [
    "market_analyst_result", "population_analyst_result", "legal_result",
    "demographic_depth_result", "trend_forecaster_result", "operational_fit_result",
    "district_ranking_result", "competitor_intel_result"
]
agent_attributions = []
for key in agent_keys:
    result = analysis_results.get(key, {})
    attr = result.get("agent_attribution") or result.get("attribution")
    if attr:
        agent_attributions.append({**attr, "id": key.replace("_result", "")})

# synthesis 본인의 attribution 추가
agent_attributions.append({
    "id": "synthesis",
    "confidence": 0.85,
    "verdict": final_strategy.summary[:100],
    "reasoning": "...",
    "sources": [...]
})

return {
    "analysis_results": new_analysis_results,
    "overall_legal_risk": ...,
    "agent_attributions": agent_attributions,  # ← 신규
}
```

**효과**: InsightTab 8 카드 + AgentConfidenceRadar 즉시 부활.

---

## 5. P1 (1~2일 내) 5건

### P1-1. TS interface 2 필드 추가 (Drift #1)

```typescript
// frontend/src/types/index.ts SimulationInput
target_districts?: string[];
industry_filter?: string | null;
```

### P1-2. LegalTab 빈 `legal_risks` empty state (Drift #17)

```typescript
// LegalTab.tsx
if (!risks || risks.length === 0) {
  return <EmptyState message="법률 리스크 분석 결과가 없습니다 (분석 진행 중일 수 있음)" />;
}
```

### P1-3. FinancialTab closure_risk null UX 통일 (Drift #19)

`ClosureRatePanel` 의 fail UX와 `ClosureRiskPanel` 의 fail UX 메시지/스타일 통일.

### P1-4. `scenarios`/`trend_forecast`/`financial_report` fail 진단 (Drift #12)

각 노드의 silent except 블록을 logger로 노출 → 어떤 단계에서 실패하는지 추적.

### P1-5. SummaryTab 5 fail 별도 fix

직전 issue 참조: [`2026-04-28-summary-tab-empty-cards.md`](./2026-04-28-summary-tab-empty-cards.md).

---

## 6. P2/P3 (정리·문서화)

| # | 작업 |
|---|---|
| 1 | Dead state 필드 정리 (`brand_analysis`, `next_step`, `target_monthly_sales`) |
| 2 | Dead response 필드 정리 (`comparison`, `analysis_report`, `analysis_metrics`, `simulation_quarters`, `is_excluded_combo`, `map_data`, `request_id`, `all_competitor_locations`) |
| 3 | `existing_stores`, `scenarios` 입력 dead end 처리 (input 제거 또는 노드 사용처 추가) |
| 4 | `customer_segment` AgentState 슬롯 명시 |
| 5 | `competitor_intel_result` vs `competitor_intel` 명명 통일 |
| 6 | TS interface `map_data`, `financial_report` 강타입 정의 |
| 7 | DemographicTab 4조건 AND 로직 → 개별 차트 fallback |
| 8 | MarketTab `competitor_intel.competition_500m` null 명확한 메시지 |
| 9 | AbmTab `vacancy_spots=[]` 로드 실패 배너 |
| 10 | `simulation_quarters` 16 vs `quarterly_projection.length` 정합성 진단 |

---

## 7. 책임 영역 (AGENTS.md 기준)

본인(A1)의 단독 처리 가능 항목 표시:

| Drift | 영역 | 본인 단독? |
|---|---|---|
| #1 TS 2필드 | C1 (frontend types) | ❌ |
| #4 AgentState target_* 정의 | A1·B1 (schemas) | ⚠️ A1 일부 가능 |
| #5 customer_segment 슬롯 | A1·B1 | ⚠️ |
| #6 Dead state | A1·B1 | ✅ |
| #8 synthesis attribution 수집 | B1 (agents) | ❌ |
| **#9 final_report 응답 매핑** | **A1·B1** | ⚠️ main.py가 모두의 영역 |
| #10 SummaryTab `=== 4` | C1 | ❌ |
| #11 agent_attributions | B1 | ❌ |
| #12 scenarios/trend_forecast fail | B1·B2 | ❌ |
| #13 Dead response 정리 | A1·B1 | ⚠️ |
| #16 SummaryTab 5 fail | B1·B2·C1 | ❌ |
| #17 LegalTab UX | C1 | ❌ |

→ **본인 단독으로 진행할 수 있는 P0 작업이 거의 없음.** main.py 응답 빌더 부분(#9, #13)은 협의 후 가능. 나머지는 B1·B2·C1 협업.

---

## 8. 검증 절차

### 8-1. P0 fix 후 즉시 검증

```bash
# 1) 백엔드 재시작
cd backend && uvicorn src.main:app --reload

# 2) /simulate 호출 후 final_report + agent_attributions 확인
curl -X POST http://localhost:3000/api/simulate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT>" \
  -H "x-tenant-id: spotter-demo-workspace-01" \
  -d '{"target_district":"공덕동","business_type":"커피","brand_name":"메가엠지씨커피", ...}' \
  | python -m json.tool | head -100
```

응답에서 다음 모두 확인:
- `final_report.profit_simulation.bep_months` 숫자
- `final_report.profit_simulation.monthly_revenue/cost/profit` 숫자
- `agent_attributions` 배열 길이 8 이상
- 각 attribution의 `confidence`, `verdict`, `reasoning` 필드

### 8-2. UI 검증

브라우저에서 `localhost:3000/simulator` → 입력 폼 채우고 시뮬레이션 시작:
- SummaryTab 카드 3 BEP 개월 표시 (— 아닌 숫자)
- FinancialTab ProfitSimulationPanelFull 모든 값 채워짐
- InsightTab 8개 에이전트 카드 모두 solid border (dashed 아님)

### 8-3. 회귀 방지

기존 정상 동작 케이스 (브랜드명을 매핑된 것으로 입력):
- competitor_intel 정상 (market_entry_signal 채워짐)
- SummaryTab 카드 1 GO/HOLD/STOP 판정

---

## 9. 결론

**총 24건의 drift/gap** 중:
- **P0 4건** = 즉시 수정 시 사용자 화면 큰 폭 회복 (SummaryTab + InsightTab + FinancialTab)
- **P1 5건** = 1~2일 내 추가 fix
- **P2/P3 15건** = 정리·문서화

**가장 결정적 단일 fix**: `main.py` 응답 빌더에 `"final_report": state.get("analysis_results", {}).get("final_report")` **1줄 추가** — SummaryTab 카드 2,3 + FinancialTab ProfitSimulationPanelFull 동시 부활.

**가장 결정적 architecture 개선**: `synthesis_node`가 9개 노드 attribution을 배열화해 `state["agent_attributions"]`에 저장 — InsightTab 전체 부활.

본인(A1) 영역 내 단독 진행은 어렵고, B1·B2·C1 협업 ticket으로 분리 권장. 본 issue가 그 ticket 베이스 자료가 됨.

---

## 10. 참고 자료

- 직전 issue: [`docs/issues/2026-04-28-summary-tab-empty-cards.md`](./2026-04-28-summary-tab-empty-cards.md) — SummaryTab 5 fail
- 코드베이스 종합 리뷰: [`docs/architecture/codebase-review-2026-04-28.md`](../architecture/codebase-review-2026-04-28.md)
- API 계약: [`docs/architecture/api-contract.md`](../architecture/api-contract.md)
- op_fit 활용 평가: [`docs/proposals/2026-04-28-operational-fit-score-applicability.md`](../proposals/2026-04-28-operational-fit-score-applicability.md)
- op_fit 적용 레시피: [`docs/proposals/2026-04-28-operational-fit-score-integration-recipes.md`](../proposals/2026-04-28-operational-fit-score-integration-recipes.md)
- 본인 PR: https://github.com/Himidea-AI/Final_Project/pull/127

분석 방법: 4개 Explore agent 병렬 dispatch (Frontend↔API, API↔State, State↔Output, Output↔Tabs) → 24건 drift 종합.
