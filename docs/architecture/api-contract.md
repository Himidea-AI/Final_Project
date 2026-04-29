# API Contract - Frontend/Backend Agreement

> 기준일: 2026-04-27  
> 기준 브랜치: `dev` (`feature/demographic-depth-agent` merge 반영)  
> 상세 프론트 입력 문서: [`api-contract-frontend-input.md`](api-contract-frontend-input.md)

이 문서는 프론트엔드(C1)와 백엔드/C2가 공유하는 공식 API 계약입니다.  
핵심 원칙은 **데이터가 없으면 임의 값을 만들지 않고 `null` 또는 빈 배열로 보낸다**입니다.

## 1. Common Rules

### 1.1 Response Shape

`POST /simulate`는 현재 raw `SimulationOutput`을 반환합니다. 프론트는 하위 호환을 위해 아래 두 형태를 모두 처리합니다.

```json
{ "status": "success", "data": { "...": "SimulationOutput" } }
```

또는

```json
{ "request_id": "sim_xxx", "...": "SimulationOutput" }
```

신규 엔드포인트는 가능하면 envelope를 통일합니다.

```json
{
  "status": "success",
  "data": {}
}
```

실패 응답은 다음 형태를 권장합니다.

```json
{
  "status": "error",
  "message": "사용자에게 보여줄 수 있는 오류 메시지"
}
```

### 1.2 Null/Empty Policy

보내지 말아야 할 것:

- 데이터 없을 때 임의 기본값: `risk_score: 50`, `legal_risk: "safe"`, `signal: "green"`, `confidence: 0.9`
- mock 표시 없는 mock 응답
- 같은 필드에 서로 다른 단위 섞기

보내야 할 것:

- 미산정 scalar: `null`
- 미산정 list: `[]`
- mock 데이터: `is_mock: true` 또는 envelope의 `data_source: "mock"`
- 부분 실패: HTTP 200 + 해당 필드만 `null`/`[]` + 가능하면 `agent_attributions[].status`

## 2. Frontend Called APIs

| Method | Path | Auth | Purpose | Status |
|---|---|---|---|---|
| GET | `/health` | none | smoke test | active |
| POST | `/predict` | JWT | ML-only district predictions | active |
| POST | `/analyze/llm` | JWT | LLM analysis without ML prediction | active |
| POST | `/simulate-abm` | JWT | ABM persona simulation | active |
| POST | `/simulate` | JWT | legacy combined simulation/dashboard API | deprecated |
| POST | `/analyze` | JWT | legacy standalone map/location analysis | deprecated, lower priority |
| GET | `/report/{request_id}` | JWT | reserved report fetch | mock/reserved |
| GET | `/status/{job_id}` | JWT | reserved async job polling | mock/reserved |
| GET | `/population/live?dongs=` | JWT | realtime population | active/TBD UI |
| GET | `/mapo/spots/{dong_name}?limit=N` | JWT | Mapo spot pins | active |
| POST | `/simulation-history` | JWT | save simulation result | active |
| GET | `/simulation-history?...` | JWT | history list/compare tray | active |
| GET | `/simulation-history/{id}` | JWT | history detail/PDF re-render | active |
| DELETE | `/simulation-history/{id}` | JWT | delete history item | active |
| POST | `/biz/lookup` | none | business registration lookup | active |
| GET | `/ops/token-usage?from=&to=` | JWT | HQ token burnrate | not implemented |

공통 헤더:

```http
Authorization: Bearer <token>
X-Tenant-ID: spotter-demo-workspace-01
```

## 2.1 Active Backend API Split

New clients should call the split backend flow:

- `POST /predict`: returns ML/TCP prediction data for 1-4 selected districts.
- `POST /analyze/llm`: returns LLM analysis and `data.final_report`; it does not own ML prediction.
- `POST /simulate-abm`: returns ABM persona simulation output and LLM decision stats.

`POST /simulate` remains available only as a legacy compatibility route. The FastAPI route is marked deprecated and returns deprecation headers. Frontend migration handoff: use `/predict` + `/analyze/llm` for the main dashboard flow, then call `/simulate-abm` only when the user opens/runs ABM.

`quarterly_projection[].revenue` is quarterly revenue. Monthly UI labels must divide it by 3.

`POST /predict` `data[]` includes nullable ML extension fields: `customer_segment`, `living_pop_forecast`, `emerging_signal`.

`POST /simulate-abm` accepts `enable_llm_decisions` (default `false`). When true, Tier S uses LLM decisions up to 50 agents, Tier A/B stay on policy decisions, and the response includes `tier_s_calls`, `tier_a_calls`, and `estimated_cost_usd`.

## 3. POST /simulate

Legacy/deprecated. New clients should use `/predict` + `/analyze/llm`.

### 3.1 Request

Backend schema: `backend/src/schemas/simulation_input.py`  
Frontend type: `frontend/src/types/index.ts` `SimulationInput`

```json
{
  "business_type": "cafe",
  "brand_name": "스타벅스",
  "target_district": "서교동",
  "target_districts": ["서교동", "합정동", "망원1동"],
  "existing_stores": [
    { "district": "공덕동", "address": "공덕동 123-4", "monthly_revenue": 32000000 }
  ],
  "monthly_rent": 3500000,
  "scenarios": ["base"],
  "store_area": 15.0,
  "target_price_range": "5to10k",
  "operating_hours": ["점심", "저녁"],
  "initial_capital": 50000000,
  "commercial_radius": 500,
  "population_weight": true,
  "industry_filter": null,
  "target_age_groups": ["30대"],
  "target_gender": "female",
  "target_time_slots": ["time_11_14"],
  "target_day_type": "weekday",
  "target_monthly_sales": null
}
```

### 3.2 Required Response Fields

These keys must exist even when values are empty.

| Field | Type | Null/Empty | Notes |
|---|---|---|---|
| `request_id` | string | required | simulation request id |
| `target_district` | string | required | selected/analysis district |
| `analysis_report` | string | `""` allowed | markdown/string report |
| `analysis_metrics` | object | `{}` allowed | dashboard summary metrics |
| `simulation_quarters` | int/null | null allowed | BEP 기준 분기 수 (최대 40) |
| `quarterly_projection` | array | `[]` allowed | mock 시 각 항목 `is_mock: true` 표시 |
| `comparison` | array | `[]` allowed | no mock row |
| `legal_risks` | array | `[]` allowed | empty means no risks or unavailable depending status |

### 3.3 Strongly Recommended Response Fields

| Field | Type | Null/Empty | Used By |
|---|---|---|---|
| `target_districts` | string[] | `[]` allowed | dashboard context |
| `winner_district` | string/null | null allowed | Summary/Market |
| `top_3_candidates` | string[] | `[]` allowed | Market |
| `district_rankings` | object[] | `[]` allowed | Market |
| `overall_legal_risk` | `safe/caution/danger/null` | null allowed | Summary/Legal |
| `market_report` | object/null | null allowed | Market KPI gauges |
| `final_report` | object/null | null allowed | Summary/Financial/Insight |
| `agent_attributions` | object[] | `[]` allowed | Insight |

### 3.4 Optional/Nullable Response Fields

| Field | Type | Null/Empty Policy |
|---|---|---|
| `shap_result` | object/null | null if SHAP unavailable |
| `closure_risk` | object/null | null if model unavailable |
| `competitor_intel` | object/null | null if competitor agent unavailable |
| `trend_forecast` | object/null | null if trend agent unavailable |
| `demographic_report` | object/null | null if demographic agent unavailable |
| `customer_segment` | object/null | null if segment analysis unavailable |
| `financial_report` | object | `{}` allowed |
| `all_competitor_locations` | array | `[]` allowed |
| `vacancy_applied` | boolean | `false` allowed |
| `vacancy_spots` | array | `[]` allowed |
| `scenarios` | object/null | null if unavailable |

## 4. Key Response Schemas

### 4.1 `market_report`

All values are normalized 0-100 unless noted. Missing values must be `null`.

```json
{
  "floating_population": 78,
  "rent_index": 64,
  "competition_intensity": 71,
  "estimated_revenue": 73,
  "survival_rate": 68,
  "closure_rate": 0.24,
  "growth_potential": 76,
  "accessibility": 82
}
```

`closure_rate` is a 0-1 ratio from the model. Do not convert it to 0-100 under the same field name.

### 4.2 `quarterly_projection`

```json
[
  {
    "quarter": 1,
    "revenue": 38000000,
    "cumulative_profit": -12000000,
    "confidence_lower": 32000000,
    "confidence_upper": 44000000,
    "ci_80_lower": null,
    "ci_80_upper": null,
    "ci_95_lower": null,
    "ci_95_upper": null
  }
]
```

When model output is unavailable, return `[]`. Do not synthesize temporary revenue numbers.

### 4.3 `district_rankings[]`

```json
{
  "rank": 1,
  "district": "서교동",
  "score": 78.4,
  "sales_growth": 0.087,
  "sales_score": 82,
  "pop_growth": 0.034,
  "pop_score": 76,
  "avg_rent": 4200000,
  "rent_score": 64,
  "vacancy_rate": 0.06,
  "zoning_risk": "safe",
  "bep_quarters": 3,
  "closure_rate": 0.24
}
```

Naming agreement:

- `bep_months` was changed to `bep_quarters` for `district_rankings[]`.
- `final_report.profit_simulation.bep_months` remains month-based and separate.

### 4.4 `closure_risk`

```json
{
  "risk_score": 0.27,
  "risk_level": "caution",
  "top_signals_lgbm": [
    { "feature": "임대료 상승률", "feature_key": "rent_growth_yoy", "contribution": 0.12 }
  ],
  "summary_lgbm": ["과거 마포구 동종업종 폐업 패턴 대비 평균 수준입니다."],
  "top_signals_tcn": [],
  "summary_tcn": [],
  "model": "lgbm_tcn_ensemble",
  "is_mock": false
}
```

Naming agreement:

- `top_signals` was split into `top_signals_lgbm` and `top_signals_tcn`.
- `summary` was split into `summary_lgbm` and `summary_tcn`.
- `risk_score` unit is 0-1. Frontend multiplies by 100 for display.

### 4.5 `shap_result`

```json
{
  "feature_importance": [
    {
      "rank": 1,
      "feature": "floating_population",
      "feature_ko": "유동인구",
      "shap_value": 4200000,
      "abs_shap": 4200000,
      "direction": "positive"
    }
  ],
  "base_value": 36000000,
  "predicted_value": 41500000,
  "predicted_value_unit": "원",
  "summary": ["유동인구가 가장 큰 양(+) 기여요인입니다."],
  "is_mock": false
}
```

### 4.6 `agent_attributions[]`

P0 agreement: every attribution may include `status`.

```json
{
  "id": "trend_forecaster",
  "display_name": "트렌드 예측",
  "kind": "Hybrid",
  "sources": ["naver_trend_industry", "ecos_timeseries"],
  "verdict": "성장",
  "reasoning": "검색량 +14% YoY",
  "confidence": 0.66,
  "status": "success"
}
```

Allowed `status` values:

| Value | Meaning |
|---|---|
| `success` | completed normally |
| `partial` | partial data or non-critical substep failed |
| `pending` | reserved for async/future jobs |
| `error` | agent failed |
| `skipped` | intentionally skipped or input missing |

Current backend can emit these IDs:

```text
market_analyst
population_analyst
legal
district_ranking
operational_fit
synthesis
demographic_depth
trend_forecaster
competitor_intel
```

Open UI decision: frontend document currently says "8 agents", but backend `dev` now includes `operational_fit`. Decide whether InsightTab shows 8 core agents and ignores `operational_fit`, or moves to 9 agents.

## 5. Error Policy

| Situation | Backend Response | Frontend Behavior |
|---|---|---|
| validation error | HTTP 422 + FastAPI `detail` | inline form error |
| auth missing/expired | HTTP 401 | clear auth and redirect |
| permission/tenant error | HTTP 403 | toast |
| partial LLM/model failure | HTTP 200 + only failed field `null`/`[]` + attribution `status` | placeholder only for failed card |
| total pipeline failure | HTTP 200 `{status:"error", message}` or HTTP 502 | global error + retry |
| rate limit | HTTP 429 `{status:"error", message}` | toast |

## 6. Backend Responsibilities From C1 Input

Accepted:

- Do not emit magic fallback numbers as if they are real data.
- Use `null`/`[]` for missing partial results.
- Keep `bep_quarters` in district rankings.
- Keep closure risk split as LightGBM and TCN fields.
- Add `agent_attributions[].status`.

Needs follow-up:

- Decide whether `operational_fit` is exposed as a 9th InsightTab agent.
- Define `/ops/token-usage`.
- Decide async simulation shape: `POST /simulate -> {job_id}` plus `GET /status/{job_id}`, or keep synchronous for demo.
- Add `quarterly_projection.data_quality` if B2 can provide it.
- Add `closure_risk.confidence_level` if B2 can provide it.
- Add `final_report.profit_simulation.includes_labor_cost` when cost model is finalized.

