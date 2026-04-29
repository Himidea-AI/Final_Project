# SummaryTab 3개 카드 빈 상태 — 5가지 독립 fail 원인 분석

**발생일:** 2026-04-28
**보고자:** A1 찬영
**우선순위:** 🔴 High (사용자 첫 화면 핵심 카드 모두 빈 상태)
**브랜치:** `IM3-243-dong-fk-followup` (origin/dev + feature/demographic-depth-agent 머지된 상태)
**환경:** localhost (FastAPI uvicorn :8000 + Vite :3000)

---

## 1. 증상

`http://localhost:3000/simulator?tab=summary` 진입 시 SummaryTab의 3개 의사결정 카드가 모두 빈 상태로 표시.

| 카드 | 표시 내용 | 기대 |
|---|---|---|
| 이 가게 경쟁력은 뭘까? | "분석 대기" + 빈 키워드 | 진입 권장(GO/HOLD/STOP/UNKNOWN) 판정 + 경쟁점 수 + 적합도 |
| 얼마나 벌 수 있을까? | "—" 또는 "값을 데이터에서 추출하지 못했습니다" | 연 P50 매출 + P10/P90 신뢰구간 |
| 언제 본전을 뽑을까? | "—" | BEP 개월 + 월 매출/운영비/이익 |

스크린샷: 다운로드의 `화면 캡처 2026-04-28 020828.png`.

---

## 2. 진단 환경

### 인프라 검증 결과 (모두 ✅)

| 계층 | 상태 |
|---|---|
| 백엔드 uvicorn (port 8000, PID 20344, 1080 MB) | ✅ HTTP 200, 0.21s |
| Vite dev server (port 3000) | ✅ HTTP 200 |
| Vite proxy `/api → :8000` (rewrite) | ✅ |
| `vite.config.ts:18-25` | ✅ port 3000, proxy 정상 |
| `POST /api/simulate` | ✅ HTTP 200, **60,723 bytes** 응답 |
| TypeScript 컴파일 (`npx tsc --noEmit`) | ✅ 에러 없음 |
| CORS allow-origin | ✅ |
| JWT (`role=master`, exp 미래) | ✅ |
| `x-tenant-id: spotter-demo-workspace-01` | ✅ |

### DB 의존 노드 응답 검증 (모두 ✅)

응답에서 다음 9개 노드가 정상 데이터를 반환 → **DB 자체 문제 아님**:

| 노드 | DB 호출 | 응답 |
|---|---|---|
| `legal_risks` | RAG vector DB + chunks | ✅ franchise_law MEDIUM, commercial_lease_law HIGH |
| `demographic_report` | `living_population`, `resident_pop` | ✅ "30-40 mixed 21.7%" |
| `living_pop_forecast` | `living_population` | ✅ 4분기 예측 |
| `vacancy_spots` | `vacancy_pse`, 좌표 | ✅ 6개 좌표 |
| `district_rankings` | `district_sales`, 임대료 | ✅ 4개 동 ranking |
| `map_data` | dong_centroid | ✅ |
| `emerging_signal` | autoencoder + DB 피처 | ✅ normal 0.554 |
| `quarterly_projection` (TCN) | `district_sales` + `seoul_district_stores` | ✅ 9억/분기 |
| `shap_result` | TCN 33피처 | ✅ feature_importance + predicted_value |

별도 dry-run 검증: `customer_revenue → living_population` SQL이 마포 16동 × 4 프로필 = **64건 모두 정상 조회** (`docs/issues/2026-04-28-summary-tab-empty-cards.md` 의 부록 참조).

---

## 3. 응답 본문 요약 (60 KB)

`POST /api/simulate` 의 raw `SimulationOutput` 형태 (envelope 없음):

```jsonc
{
  "request_id": "d5ddc7e6-b3a6-44ea-ad9d-bb8225376471",
  "target_district": "공덕동",
  "winner_district": "공덕동",
  "target_districts": ["공덕동", "아현동", "도화동", "용강동"],
  "top_3_candidates": ["아현동", "도화동", "용강동"],
  "simulation_quarters": 16,
  "vacancy_applied": true,

  // ✅ 정상 채워진 필드
  "legal_risks": [{ "type": "franchise_law", "risk_level": "MEDIUM" }, ...],
  "overall_legal_risk": "danger",
  "closure_rate": { "closure_rate": 0.065, "risk_level": "safe" },
  "demographic_report": { "core_demographic": { "age": "30-40", "gender": "mixed", "share": 0.217 } },
  "living_pop_forecast": { "dong_code": "11440565", "n_quarters": 4, ... },
  "vacancy_spots": [{ "id": 1232, "dong_name": "도화동", "listing_count": 7 }, ...],
  "district_rankings": [{ "district": "공덕동", "sales_growth": -17.87, "avg_rent": 162568 }, ...],
  "shap_result": { "feature_importance": [...], "predicted_value": 901173850.33 },
  "quarterly_projection": [{ "quarter": 1, "revenue": 901173850, "cumulative_profit": -46395939, "confidence_lower": 848184828, ... }],
  "analysis_metrics": { "operational_fit_score": 47.6, ... },
  "emerging_signal": { "anomaly_score": 0.554, "signal": "normal" },
  "ai_recommendation": "메가엠지씨커피의 공덕동 출점은 ...",
  "analysis_report": "메가엠지씨커피의 공덕동 출점은 ...",
  "agent_attributions": [...],
  "comparison": [{ "district": "공덕동", "score": 44.4, "bep": 15 }],
  "map_data": { "center": { "lat": 37.543, "lng": 126.9519 } },
  "market_report": { "floating_population": 64, "rent_index": 53, "competition_intensity": 85, "estimated_revenue": 15 },

  // ❌ Fail / 빈 필드
  "competitor_intel": {
    "error": "브랜드/업종 매핑 실패: 메가엠지씨커피(MEGA MGC COFFEE)/커피",
    "narrative": "지원하지 않는 브랜드/업종 조합입니다."
    // market_entry_signal, cannibalization, competition_500m 키 모두 누락
  },
  "closure_risk": {
    "risk_score": null,
    "risk_level": "unknown",
    "top_signals_lgbm": [],
    "summary_lgbm": [],
    "top_signals_tcn": []
  },
  "customer_segment": null,
  "scenarios": {},
  "trend_forecast": {},
  "financial_report": {}

  // ❌ 응답에 통째로 없는 키
  // "final_report" — SummaryTab 카드 3 의 모든 값 의존
}
```

---

## 4. 5가지 독립 Fail 원인 — 상세 분석

### 🔴 원인 1: `final_report.profit_simulation` 키가 응답에 **아예 없음** (가장 심각)

**영향**: 카드 3 ("언제 본전을 뽑을까") 거의 전체 + 카드 2 폴백.

**Frontend 코드** (`frontend/src/components/SimulationResult/dashboard/tabs/SummaryTab.tsx:50-61`):
```typescript
const fr = simResult.final_report ?? null;        // ← 응답에 키 없음 → null
const ps = fr?.profit_simulation ?? null;          // ← null
const netProfit = ps?.net_profit ?? null;          // ← null
const monthlyRev = ps?.monthly_revenue ?? quarterlyToMonthly(firstQ?.revenue ?? null);
const monthlyCost = ps?.monthly_cost ?? null;      // ← null
const bepMonths = ps?.bep_months ?? null;          // ← null
const margin = ps?.margin_rate ?? null;            // ← null
```

**근본 원인**:
- 백엔드가 응답에 `final_report` 객체를 채우지 않음
- 분리된 키들 — `analysis_report`(LLM 텍스트), `analysis_metrics`(수치), `comparison[].bep`(15분기 등) — 로 데이터를 보내고 있음
- frontend SummaryTab은 **이전 schema (`final_report.profit_simulation.*`)** 를 그대로 기대

**추정 원인**: Sprint 8 (`feature/demographic-depth-agent` 머지) 후 백엔드 schema가 분리됐는데 SummaryTab이 따라가지 않은 schema drift.

**확인 필요 위치**:
- `backend/src/agents/nodes/synthesis.py` — `final_report` 빌더 누락 여부
- `backend/src/main.py` — `simulate` 응답 빌더에서 `final_report` 채우는 코드
- `backend/src/schemas/simulation_output.py` — `final_report` 필드 정의 여부

---

### 🔴 원인 2: `quarterly_projection.length !== 4` (카드 2 직접 원인)

**영향**: 카드 2 ("얼마나 벌 수 있을까") `hasQp = false` → "—" 또는 부분 표시.

**Frontend 코드** (`SummaryTab.tsx:77-87`):
```typescript
const fullQuarters = qp.filter(
  (q) => typeof q.revenue === 'number'
      && typeof q.confidence_lower === 'number'
      && typeof q.confidence_upper === 'number',
);
const hasQp = fullQuarters.length === 4;   // ← TCN은 4분기 예측 고정 (하드코딩)
const hasPartialQp = fullQuarters.length > 0 && fullQuarters.length < 4;
```

**근본 원인**:
- 응답의 `simulation_quarters: 16` — 16분기 시뮬레이션
- `quarterly_projection` 길이도 16일 가능성 → `length === 4` 항상 false
- 또는 16분기 중 일부의 `confidence_lower`/`confidence_upper`가 null이면 필터에서 빠져 length 줄어듦

**확인 필요**: 응답의 `quarterly_projection` 배열 길이 + 각 분기의 `confidence_lower`/`confidence_upper` 채워짐 여부.

**04-25 commit 단서**: `refactor(B2): monthly → quarterly 네이밍 통일` — 이 시점에 분기 수 정책 변경 가능성.

---

### 🟡 원인 3: `competitor_intel` 브랜드 매핑 fail (카드 1 직접 원인)

**영향**: 카드 1 ("이 가게 경쟁력은 뭘까") → "분석 대기" 표시.

**Frontend 코드** (`SummaryTab.tsx:66-69`):
```typescript
const legalRaw = simResult.overall_legal_risk ?? null;            // ← "danger" ✅
const entryRaw = (ci?.market_entry_signal as string | undefined) ?? null;  // ← null ❌
const verdict = computeDecision(legalRaw, entryRaw);              // → UNKNOWN
```

**`computeDecision`** (`frontend/src/constants/decisionThresholds.ts:20-28`):
```typescript
if (legal == null || entry == null) return 'UNKNOWN';   // ← "분석 대기"
```

**Backend 코드** (`backend/src/agents/nodes/competitor_intel.py:304-312`):
```python
return {
    "error": f"브랜드/업종 매핑 실패: {brand_name}({...})/{industry_or_biz}",
    "narrative": "지원하지 않는 브랜드/업종 조합입니다.",
    # market_entry_signal, cannibalization, competition_500m 키 누락
}
```

**근본 원인**:
- `competitor_intel.py` 의 brand_name → industry 매핑 dict가 `메가엠지씨커피` / `MEGA MGC COFFEE` 미커버
- `business_type=커피` fallback 매핑도 미커버 (`_BIZ_TYPE_NORMALIZE` 에 부재)

**확인 필요 위치**:
- `backend/src/agents/nodes/competitor_intel.py:78` — `brand_name 우선, business_type fallback. 그래도 없으면 default`
- `backend/src/agents/nodes/competitor_intel.py:59` — `business_type → industry 매핑`

---

### 🟡 원인 4: `customer_segment: null` (카드 1 부수 + DemographicTab 영향)

**영향**: SummaryTab 카드 1의 `demo.brand_target_match_score` 보강 데이터 누락. DemographicTab 핵심 데이터 누락.

**Backend 코드** (`backend/src/agents/graph.py:200`):
```python
sim_result = ModelOutput.generate(
    dong_code, industry_code, biz,
    model="tcn",
    cost_config=cost_config,
    # ← segment_profile 인자 누락!
)
```

**`models/interface.py:366-373` 시그니처**:
```python
def generate(
    dong_code: str,
    industry_code: str,
    industry_name: str,
    cost_config: dict | None = None,
    model: str = "lstm",
    segment_profile: dict | None = None,   # ← 이미 정의됨
) -> dict:
```

**근본 원인**: graph.py 가 `ModelOutput.generate` 를 호출할 때 `segment_profile` 인자를 빠뜨림 → `_run_customer_revenue` 가 호출 안 되거나 빈 결과 반환.

**관련 자료**: 본인이 작성한 plan `docs/superpowers/specs/2026-04-25-tcn-imputed-vs-original-comparison-design.md` 의 후속 — `C:\Users\804\.claude\plans\graph-py-segment-profile-declarative-micali.md` 에 정확한 수정안 명시.

**git blame**: `commit 59955d9 author soooojinn` (B2 수지니, 2026-04-24) — segment_profile 인자를 generate에 추가한 사람과 graph.py 호출에서 빠뜨린 사람이 동일 인물.

---

### 🟡 원인 5: `closure_risk` / `scenarios` / `trend_forecast` / `financial_report` 빈 상태

**영향**: SummaryTab 직접 영향 적음. 다른 탭(Financial, Insight, Forecast) 빈 상태.

#### 5-A. `closure_risk` — LightGBM+TCN 앙상블 fail

```json
{ "risk_score": null, "risk_level": "unknown",
  "top_signals_lgbm": [], "top_signals_tcn": [] }
```

**추정 원인**:
- `models/closure_risk/weights/closure_risk_tcn.pt` 또는 LightGBM 모델 가중치 로드 실패
- 또는 추론 코드에서 silent except → 빈 결과
- 사용자(A1) 영역 외 — B2 (수지니) 담당

#### 5-B. `scenarios: {}` — build_scenarios fail

`models/explainability/simulation.py:177` `build_scenarios()` 가 분기별 매출 → 낙관/기본/비관 derive.

**관찰**: TCN 결과(`quarterly_projection`)는 정상이므로 `build_scenarios` 내부 로직 문제 또는 main.py 호출 skip.

#### 5-C. `trend_forecast: {}` — trend_forecaster 노드 fail

추정: 외부 API(네이버 검색 트렌드, 한국은행 기준금리) 호출 실패 또는 LLM 호출 timeout/quota.

#### 5-D. `financial_report: {}` — placeholder 빈 상태

코드에서 채우는 곳 못 찾음. 미구현일 가능성.

---

## 5. 영향 매트릭스

| 응답 필드 | 백엔드 상태 | SummaryTab 카드 영향 | 다른 탭 영향 |
|---|---|---|---|
| `final_report.profit_simulation` | ❌ 키 없음 | 카드 3 모든 값 "—" | FinancialTab |
| `quarterly_projection` length | ⚠️ 16 ≠ 4 | 카드 2 hasQp false | ForecastTab |
| `competitor_intel.market_entry_signal` | ❌ null | 카드 1 → "분석 대기" | MarketTab, InsightTab |
| `customer_segment` | ❌ null | 카드 1 부수 | DemographicTab |
| `closure_risk` | ❌ 모델 fail | — | FinancialTab |
| `scenarios` | ❌ 빈 객체 | — | InsightTab |
| `trend_forecast` | ❌ 빈 객체 | — | ForecastTab |
| `financial_report` | ❌ 빈 객체 | — | FinancialTab |

---

## 6. 우선순위별 수정안

| # | 수정 위치 | 작업량 | 효과 | 담당 (AGENTS.md) |
|---|---|---|---|---|
| 1 | **Frontend SummaryTab — `=== 4` 를 `>= 4` 또는 `>= 1` 로 변경** | 1줄 | 카드 2 즉시 복구 | C1 (강민) |
| 2 | **Backend synthesis_node — `final_report.profit_simulation` 채우기** (`bep_months`, `monthly_revenue`, `monthly_cost`, `net_profit`, `margin_rate`) | 20~40줄 | 카드 3 즉시 복구 + 카드 2 폴백 | B2 (수지니) |
| 3 | **`competitor_intel.py` 브랜드 매핑에 `메가엠지씨커피` alias 추가** | 1~3줄 | 카드 1 복구 | B2/B1 |
| 4 | **`graph.py:200` `segment_profile` 인자 추가** (지난 plan 작업) | 7~9줄 | customer_segment 복구 | B2 (수지니 self-bug) |
| 5 | closure_risk 모델 추론 디버그 | 별도 | FinancialTab 회복 | B2 (수지니) |
| 6 | scenarios / trend_forecast / financial_report 노드 디버그 | 별도 | 다른 탭 회복 | B1·B2 |

---

## 7. 책임 영역 요약 (AGENTS.md 기준)

A1 찬영(본인) 담당 영역(`backend/src/database/`, `services/`, `data/`)에서 **직접 처리 가능한 항목 0건**.

| 작업 | 담당 |
|---|---|
| #1 SummaryTab `=== 4` 수정 | C1 (강민) — `frontend/` |
| #2 synthesis_node `final_report` 채우기 | B2 (수지니) — `models/explainability/`, `models/revenue_predictor/`, `backend/src/agents/nodes/synthesis.py` |
| #3 브랜드 매핑 추가 | B2 또는 B1 — `backend/src/agents/nodes/competitor_intel.py` |
| #4 graph.py segment_profile | B2 (수지니 self-bug, git blame `commit 59955d9` 작성자) |
| #5 closure_risk fail | B2 — `models/closure_risk/` |
| #6 scenarios/trend/financial | B1·B2 — `backend/src/agents/nodes/`, `models/explainability/`, `models/revenue_predictor/` |

본인 PR(`IM3-243-dong-fk-followup` PR #127)에 들어간 작업(TCN imputation 비교, ABM sprint, AGENTS.md)은 본 issue 와 **무관**. 이 issue는 후속 ticket으로 분리하여 B1/B2/C1 에 인계 권장.

---

## 8. 검증 절차

### 8-1. fix 후 즉시 검증

```bash
# 1) 백엔드 재시작
cd backend && uvicorn src.main:app --reload --port 8000

# 2) /simulate 응답 검증
curl -X POST http://localhost:3000/api/simulate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT>" \
  -H "x-tenant-id: spotter-demo-workspace-01" \
  -d '{"target_district":"공덕동","business_type":"커피","brand_name":"메가엠지씨커피","monthly_rent":2000000,"store_area":15.0}' \
  | python -m json.tool | grep -E '"final_report|"competitor_intel|"customer_segment|"closure_risk"' | head
```

응답에서 다음이 모두 있어야 함:
- `final_report.profit_simulation.bep_months` 숫자
- `competitor_intel.market_entry_signal` "green"|"yellow"|"red"
- `customer_segment` 객체 (null 아님)
- `closure_risk.risk_score` 숫자

### 8-2. UI 검증

- `http://localhost:3000/simulator` 진입 → 입력 폼 채우고 시뮬레이션 시작
- SummaryTab 3개 카드:
  - 카드 1: "분석 대기" 가 아닌 GO/HOLD/STOP 중 하나
  - 카드 2: 연 매출 P50 + P10/P90 표시
  - 카드 3: BEP 개월 표시

---

## 9. 참고 자료

- 본인 PR: https://github.com/Himidea-AI/Final_Project/pull/127
- API 계약 문서: `docs/architecture/api-contract.md` (04-28 최신)
- `customer_revenue → living_population` dry-run 검증: 본 작업 세션에서 마포 16동 × 4 프로필 = 64건 정상 (DB 정상 입증)
- graph.py segment_profile plan: `C:\Users\804\.claude\plans\graph-py-segment-profile-declarative-micali.md`
- Frontend SummaryTab 코드: `frontend/src/components/SimulationResult/dashboard/tabs/SummaryTab.tsx:35-308`
- Decision threshold SSOT: `frontend/src/constants/decisionThresholds.ts`
- Vite proxy 설정: `frontend/vite.config.ts:17-26`

---

## 10. 결론

DB · 인프라 · 인증 · 빌드 모두 정상. **5가지 독립적 코드/schema 문제가 동시에 SummaryTab을 망가뜨린 상태**. 가장 빠른 회복은 **#1 (SummaryTab `=== 4` 한 줄 수정)** 으로 카드 2 즉시 부활. 카드 3 부활은 #2 (synthesis_node final_report 채우기) 에 의존하며 백엔드 작업이라 시간 더 걸림.

본 issue는 본인(A1) 영역 외 — B1/B2/C1 협업으로 fix 진행 권장.
