# API Contract — Frontend Input (C1 → C2)

> **작성**: C1 강민 · **수신**: C2 혁
> **목적**: 백엔드가 `POST /simulate` 응답 스키마를 고정하기 위해, 프론트(대시보드 8탭 + 히스토리/PDF/HQ)가 실제로 사용하는 필드와 null/empty/error 정책을 명세합니다.
> **기준 코드**: `feature/demographic-depth-agent` 브랜치, `frontend/src/types/index.ts`, `frontend/src/components/SimulationResult/dashboard/**`.
>
> ⚠️ **이번 사이클 원칙(전 항목 공통)**: *값이 없으면 빈 값을 만들지 말 것.* 프론트는 null/빈 배열을 받으면 "미산정" 안내를 띄우는 방향으로 통일했습니다(거짓 양성 판정은 본부 영업 보고서 신뢰도에 치명타). 백엔드도 폴백 매직넘버 대신 명시적 null/empty + 사유 필드(또는 별도 status) 권장.

---

## 1. 프론트가 호출하는 API 전수

| Method | Path | Auth | 사용 화면 | 비고 |
|---|---|---|---|---|
| GET  | `/health` | - | (없음, smoke test) | |
| POST | `/simulate` | JWT | 시뮬레이션 결과 대시보드 8탭 전부 | **메인 분석 API** · timeout 600s |
| POST | `/analyze` | JWT | 지도 단독 화면(`AnalysisResult`) | 현재 사용 빈도 낮음 |
| GET  | `/report/{request_id}` | JWT | 미사용(SimulationOutput 캐시 회수용 예약) | |
| GET  | `/status/{job_id}` | JWT | 미사용(향후 비동기 job 패턴 도입 시) | 자세한 건 §6 참조 |
| GET  | `/population/live?dongs=` | JWT | (TBD) 실시간 유동인구 | |
| POST | `/simulate-abm` | JWT | 대시보드 ABM 탭 (`AbmTab`, `AbmPersonaMap`) | businessType + persona 시뮬레이션 |
| GET  | `/mapo/spots-all?per_dong=N` | JWT | ABM 페르소나 지도 핀 | |
| GET  | `/mapo/spots/{district}?limit=N` | JWT | 단일 동 핀 | |
| POST | `/simulation-history` | JWT | 결과 저장 | `SaveSimulationPayload` |
| GET  | `/simulation-history?...` | JWT | 히스토리 리스트 + 비교 트레이 | `HistoryFilterParams` |
| GET  | `/simulation-history/{id}` | JWT | 히스토리 상세 + PDF 재출력 | snake_case JSONB 그대로 반환 |
| DELETE | `/simulation-history/{id}` | JWT | 히스토리 삭제 | |
| POST | `/auth/login` · `/auth/manager/login` · `/auth/signup` · `/auth/manager/signup` · `/auth/verify-invite` · `/auth/invite-code` · `/auth/managers` · `/auth/manager/{id}/approve|reject` | mixed | 로그인/가입/매니저 관리/HQ | 백엔드 합의 별도 트랙 |
| POST | `/biz/lookup` | - | 가입 시 사업자 조회 | |
| GET  | `/ops/token-usage?from=&to=` | JWT | HQ → TokenBurnrateSection | **현재 404, B1 예진 구현 대기** (`frontend/src/types/tokenUsage.ts` 스펙 주석 참조) |

**공통 헤더(인터셉터 자동주입)**: `X-Tenant-ID: spotter-demo-workspace-01` (mock — 멀티테넌시 도입 시 JWT payload `workspace_id`로 교체), `Authorization: Bearer <token>` (localStorage `spotter_auth`에서 추출).

**응답 봉투 호환**: `/simulate` 응답이 `{status: 'success', data: {...}}` 또는 raw `SimulationOutput` 양쪽 다 도착할 수 있어 `runSimulation()`이 언래핑합니다(`api/client.ts:121-130`). 새 엔드포인트는 봉투 일관성 권장 — 봉투를 쓸 거면 모든 success/error 응답에 `status` 필드를 보장해 주세요.

---

## 2. `/simulate` 응답 — 화면별 필드 매핑

대시보드는 **8탭** 구조입니다(SummaryTab → MarketTab → AbmTab → DemographicTab → FinancialTab → ForecastTab → LegalTab → InsightTab). 동일한 `SimulationOutput` 객체를 모든 탭이 공유합니다.

### 2.1 SummaryTab (Hero + 3 DecisionCard)

| 화면 요소 | 사용 필드 | 비고 |
|---|---|---|
| 추천 행정동 / 부제 | `winner_district`, `target_district`, `target_districts[]` | winner 없으면 target 폴백 |
| 종합 verdict (GO/HOLD/STOP/**UNKNOWN**) | `overall_legal_risk`, `competitor_intel.market_entry_signal` | 둘 중 하나라도 null이면 **UNKNOWN** |
| 법률 카드 | `overall_legal_risk` ('safe'\|'caution'\|'danger') | `'safe'` 폴백 금지 — null 그대로 |
| 진입 신호 카드 | `competitor_intel.market_entry_signal` ('green'\|'yellow'\|'red') | null이면 "진입 신호 미산정" |
| BEP 카드 | `final_report.profit_simulation.bep_months`(=개월) ↔ 분기 환산 | null이면 stone, **인건비 면책 문구 항시** |

### 2.2 MarketTab

| 화면 요소 | 사용 필드 |
|---|---|
| 7개 정규화 지표 (0~100) | `market_report.{floating_population, rent_index, competition_intensity, estimated_revenue, survival_rate, closure_rate, growth_potential, accessibility}` |
| 동별 랭킹 표 | `district_rankings[]` (rank, district, score, sales_growth, closure_rate, **bep_quarters**, zoning_risk) — winner 표시는 `winner_district === district` 매칭 |
| 추천 동 배지 | `winner_district`, `top_3_candidates[]` |
| 공실 페널티 적용 배지 | `vacancy_applied: boolean` |

### 2.3 AbmTab

| 화면 요소 | 사용 필드 / API |
|---|---|
| 모드 토글 (`map` ↔ `abm`) | UI 로컬 |
| 지도 마커 | `all_competitor_locations[]` (id, place_name, brand_name?, lat, lng, distance_m?, is_franchise?, source_dong?) |
| 페르소나 시뮬 | `POST /simulate-abm` (request body에 businessType 필요) |

### 2.4 DemographicTab

| 화면 요소 | 사용 필드 (`demographic_report.*`) |
|---|---|
| 핵심 인구 도넛 | `core_demographic.{age,gender,share}` |
| 연령 분포 누적바 | `top_3_age_groups[]` |
| 시간대 피크 | `peak_consumption_hours[]` ·  *(opt)* `peak_hour_matrix[7][24]` |
| 평일/주말 비율 | `weekday_weekend_ratio` |
| 거주/방문 비율 | `resident_visitor_ratio` (null 가능) |
| 소득/인구 추세/고령자/타겟 매칭 | `area_income_level`, `population_trend`, `elderly_ratio`, `brand_target_match_score`, `match_rationale` |
| narrative 카드 | `narrative` (필수 string) |

### 2.5 FinancialTab

| 화면 요소 | 사용 필드 |
|---|---|
| 월매출 / 운영비 / 영업이익 / 마진 | `final_report.profit_simulation.{monthly_revenue, monthly_cost, net_profit, margin_rate}` |
| BEP 월수 (인건비 면책 명시) | `final_report.profit_simulation.bep_months` |
| 분석 신뢰도 | `agent_attributions[id="synthesis"].confidence` × 100 — null이면 "—" |
| 폐업 위험도 게이지 (0~100) | `closure_risk.risk_score` (백엔드는 0~1 소수, 프론트가 ×100) |
| LightGBM 요약(과거패턴) | `closure_risk.{summary_lgbm[], top_signals_lgbm[]}` |
| TCN 요약(시계열) | `closure_risk.{summary_tcn[], top_signals_tcn[]}` (실패 시 빈 배열 허용) |

### 2.6 ForecastTab

| 화면 요소 | 사용 필드 |
|---|---|
| 분기 매출 라인 | `quarterly_projection[]` (quarter, revenue, cumulative_profit, confidence_lower/upper) |
| (Track B #107) 80%/95% CI 밴드 | `quarterly_projection[].{ci_80_lower,ci_80_upper,ci_95_lower,ci_95_upper}` (옵션) |
| 시나리오 (낙관/기본/비관) | `scenarios.{optimistic, base, pessimistic}[]` |
| SHAP waterfall | `shap_result.{feature_importance[], base_value, predicted_value}` |
| 트렌드 전망 카드 | `trend_forecast.{forecast,industry_trend,change_ix,macro}` |

### 2.7 LegalTab

| 화면 요소 | 사용 필드 |
|---|---|
| 종합 신호등 | `overall_legal_risk` |
| 항목별 카드 | `legal_risks[].{type, risk_level, detail, recommendation, articles[].article_ref/content, checklist[]}` · `is_fallback` 배지 |

### 2.8 InsightTab

| 화면 요소 | 사용 필드 |
|---|---|
| 에이전트 8종 신뢰도 레이더 | `agent_attributions[].{id, display_name, kind, sources[], verdict, reasoning, confidence}` (8개 ID는 §3.5 참조) — 누락 에이전트는 footer에 "결측 N개" 노출 |
| 에이전트 카드 | 동일 `agent_attributions[]` |
| 상권 종합 점수 | `analysis_metrics.{district_grade, growth_rate, competition_score, rent_affordability, main_target_age, peak_time}` |
| 종합 리포트 | `analysis_report` (markdown), `final_report.summary`, `final_report.final_recommendation` |
| 타겟 고객 매출 | `customer_segment.{segment_ratio, segment_sales, identified_sales, total_sales_ref, profile_summary, dimension_ratios}` |

---

## 3. SimulationOutput 필드 정책 (필수 · optional · null · empty · 명칭변경 · 추가요청)

### 3.1 필수 (없으면 화면 못 그림)

```
request_id          string
target_district     string
analysis_report     string (markdown 가능)
analysis_metrics    {district_grade, growth_rate, competition_score, rent_affordability}
simulation_months   int
quarterly_projection  array (≥1 권장 · 4개일 때 가장 잘 보임)
comparison          array (비어있어도 OK, but 키 자체는 존재)
legal_risks         array (비어있어도 OK)
```

### 3.2 화면 동작에 강하게 권장 (없으면 카드 자체가 비어 보임)

```
winner_district               → SummaryTab/MarketTab winner 강조
top_3_candidates              → MarketTab top 배지
district_rankings             → MarketTab 메인 표
overall_legal_risk            → SummaryTab 결재 verdict (없으면 UNKNOWN)
market_report (8개 지표)      → MarketTab 게이지
final_report.profit_simulation → FinancialTab 핵심 카드
agent_attributions            → InsightTab 레이더 + 신뢰도
```

### 3.3 Optional / Nullable (없으면 "미산정" 빈 상태로 우아하게 처리)

```
shap_result            null 가능 — null이면 SHAP waterfall 자리에 안내 카드
closure_risk           null 가능 — null이면 폐업 위험 패널 dashed empty
competitor_intel       null 가능 — market_entry_signal/cannibalization 미노출
trend_forecast         null 가능 — 트렌드 카드 미노출
demographic_report     null 가능 — DemographicTab 전체 placeholder
customer_segment       null 가능 — 타겟 고객 카드 미노출
financial_report       optional Record
all_competitor_locations  빈 배열 가능
vacancy_applied        false 가능
scenarios              null 가능
```

### 3.4 빈 배열 허용 (절대 mock으로 채우지 말 것)

```
legal_risks                 []
comparison                  []
top_3_candidates            []
district_rankings           []
quarterly_projection        []  (단, 0개면 ForecastTab에 안내)
agent_attributions          []  (단, 0개면 InsightTab 레이더 placeholder)
all_competitor_locations    []
closure_risk.top_signals_lgbm   []
closure_risk.top_signals_tcn    []  (TCN SHAP 실패 시 정상 케이스)
closure_risk.summary_lgbm        []
closure_risk.summary_tcn         []
shap_result.feature_importance   []
shap_result.summary              []
```

### 3.5 명칭/구조 변경 합의(2026-04-27, 이미 코드 반영됨)

| 변경 전 | 변경 후 | 위치 |
|---|---|---|
| `bep_months` | **`bep_quarters`** (분기 단위 int) | `district_rankings[].bep_quarters` (final_report.profit_simulation.bep_months는 별개로 월 단위 그대로 유지) |
| `closure_risk.top_signals` | **`top_signals_lgbm` + `top_signals_tcn`** | `closure_risk` |
| `closure_risk.summary` | **`summary_lgbm` + `summary_tcn`** | `closure_risk` |

### 3.6 프론트가 백엔드에 추가 요청하는 필드 (현재 미존재)

| 필드 | 용도 | 우선순위 |
|---|---|---|
| **에이전트 공통 `status`** ('success'\|'partial'\|'pending'\|'error'\|'skipped') | InsightTab에서 결측 사유 노출, UNKNOWN verdict 정확화 | **P0** |
| **`quarterly_projection.data_quality`** ('full'\|'partial'\|'imputed') | 분기별 신뢰도 표시 | P1 |
| **`closure_risk.confidence_level`** ('high'\|'medium'\|'low') | TCN 저신뢰 조합 경고 | P1 |
| **`final_report.profit_simulation.includes_labor_cost: boolean`** | BEP 면책 자동 노출/제거 (현재는 항시 노출) | P1 |
| **`market_report.*_source`** (각 지표 데이터 소스) | InsightTab 근거 카드 | P2 |
| **agent_attributions[].sources_detail** (URL/file/query 형태) | 근거 클릭 시 모달 | P2 |

### 3.7 절대 보내지 말아야 하는 것 (거짓 양성 방지)

- 데이터 없을 때 임의 default 값 (`risk_score: 50`, `confidence: 0.9`, `signal: 'green'`, `legal_risk: 'safe'` 등). **null 또는 omit이 정답.**
- "mock" 표시 없는 mock 응답. mock일 때는 반드시 `is_mock: true` (`shap_result`, `closure_risk`에는 이미 존재) 또는 응답 봉투에 `data_source: 'mock'`.
- 단위 변환된 값(예: 0~1 → 0~100)을 같은 필드명으로 섞어 보내기. 한 필드 = 한 단위.

---

## 4. 에러 처리 정책

| 상황 | 백엔드 응답 (요청) | 프론트 동작 |
|---|---|---|
| 입력 검증 실패 | HTTP 422 + `{detail: [{loc, msg}]}` (FastAPI 기본) | 입력 폼에 인라인 에러 |
| 인증 만료/누락 | HTTP 401 | 인터셉터가 `spotter_auth` 삭제 + `/login?reason=session_expired&redirect=...` |
| 권한 부족 (테넌시 위반) | HTTP 403 | 토스트 "권한 없음" |
| LLM/모델 일부 실패 | **HTTP 200 + 해당 필드만 null/empty + 가능하면 `agent_attributions[].status='error'`** | 해당 카드만 placeholder, 다른 탭 정상 |
| LLM/모델 전부 실패 | HTTP 200 + `{status:'error', message}` 또는 HTTP 502 | 전역 에러 화면 + 재시도 버튼 |
| 타임아웃 (≥10분) | axios 측 ECONNABORTED | 토스트 "분석 시간 초과 — 다시 시도" |
| 외부 API 장애 (한국은행/네이버 등) | 200 + 해당 sub-필드 null + `agent_attributions[id="trend_forecaster"].status='partial'` | 카드 옆 "외부 데이터 일시 결측" 마이크로카피 |

**핵심**: 프론트 정책은 *"부분 실패는 200 + null이 1순위, 전체 실패만 4xx/5xx"*. 그래야 본부 영업이 단일 실패 때문에 전체 보고서를 못 보는 사태를 막습니다.

---

## 5. 샘플 SimulationOutput JSON (현실 응답 형태)

> camelCase 변환 없이 백엔드가 보내는 그대로의 snake_case. 모든 nullable은 의도적으로 null/빈 배열로 채웠습니다.

```json
{
  "request_id": "sim_2026-04-24_a1b2c3",
  "target_district": "서교동",
  "target_districts": ["서교동", "합정동", "망원1동"],
  "analysis_report": "## 종합 결론\n서교동은 평일 오후 유동인구가...",
  "analysis_metrics": {
    "district_grade": "GOOD",
    "growth_rate": 0.087,
    "competition_score": 62,
    "rent_affordability": "mid",
    "main_target_age": "30대",
    "peak_time": "12-14시"
  },
  "simulation_months": 12,
  "quarterly_projection": [
    { "quarter": 1, "revenue": 38000000, "cumulative_profit": -12000000,
      "confidence_lower": 32000000, "confidence_upper": 44000000,
      "ci_80_lower": null, "ci_80_upper": null, "ci_95_lower": null, "ci_95_upper": null },
    { "quarter": 2, "revenue": 41500000, "cumulative_profit": -3000000,
      "confidence_lower": 35000000, "confidence_upper": 48000000,
      "ci_80_lower": null, "ci_80_upper": null, "ci_95_lower": null, "ci_95_upper": null },
    { "quarter": 3, "revenue": 44000000, "cumulative_profit": 7500000,
      "confidence_lower": 37000000, "confidence_upper": 51000000,
      "ci_80_lower": null, "ci_80_upper": null, "ci_95_lower": null, "ci_95_upper": null },
    { "quarter": 4, "revenue": 46500000, "cumulative_profit": 19000000,
      "confidence_lower": 39000000, "confidence_upper": 54000000,
      "ci_80_lower": null, "ci_80_upper": null, "ci_95_lower": null, "ci_95_upper": null }
  ],
  "comparison": [
    { "district": "서교동", "score": 78.4, "revenue": 41500000, "bep": 8, "survival": 0.71, "cannibalization": 0.18 }
  ],
  "legal_risks": [
    {
      "type": "가맹사업법 정보공개서",
      "risk_level": "caution",
      "detail": "정보공개서 등록 후 14일 경과 의무 미충족 우려",
      "recommendation": "공정위 등록일 확인 후 가맹계약 진행",
      "articles": [
        { "article_ref": "가맹사업법 제7조", "content": "..." }
      ],
      "checklist": [],
      "is_fallback": false
    }
  ],
  "ai_recommendation": "서교동 진입 권장 — 단, 카니발리제이션 18% 감안",
  "map_data": null,

  "market_report": {
    "floating_population": 78,
    "rent_index": 64,
    "competition_intensity": 71,
    "estimated_revenue": 73,
    "survival_rate": 68,
    "closure_rate": 24,
    "growth_potential": 76,
    "accessibility": 82
  },

  "winner_district": "서교동",
  "top_3_candidates": ["서교동", "합정동", "망원1동"],
  "district_rankings": [
    { "rank": 1, "district": "서교동", "score": 78.4,
      "sales_growth": 0.087, "sales_score": 82,
      "pop_growth": 0.034, "pop_score": 76,
      "avg_rent": 4200000, "rent_score": 64,
      "vacancy_rate": 0.06, "zoning_risk": "safe",
      "bep_quarters": 3, "closure_rate": 0.24 },
    { "rank": 2, "district": "합정동", "score": 74.1,
      "sales_growth": 0.061, "sales_score": 75,
      "pop_growth": 0.028, "pop_score": 71,
      "avg_rent": 4500000, "rent_score": 60,
      "vacancy_rate": 0.05, "zoning_risk": "safe",
      "bep_quarters": 4, "closure_rate": 0.21 }
  ],
  "overall_legal_risk": "caution",
  "vacancy_applied": true,

  "financial_report": {},

  "shap_result": {
    "feature_importance": [
      { "rank": 1, "feature": "floating_population", "feature_ko": "유동인구",
        "shap_value": 4200000, "abs_shap": 4200000, "direction": "positive" },
      { "rank": 2, "feature": "competitor_density", "feature_ko": "경쟁 밀도",
        "shap_value": -1800000, "abs_shap": 1800000, "direction": "negative" }
    ],
    "base_value": 36000000,
    "predicted_value": 41500000,
    "predicted_value_unit": "원",
    "summary": ["유동인구가 가장 큰 양(+) 기여요인입니다."],
    "is_mock": false
  },

  "scenarios": {
    "optimistic": [{ "quarter": 1, "revenue": 44000000 }, { "quarter": 2, "revenue": 48000000 }, { "quarter": 3, "revenue": 52000000 }, { "quarter": 4, "revenue": 55000000 }],
    "base":       [{ "quarter": 1, "revenue": 38000000 }, { "quarter": 2, "revenue": 41500000 }, { "quarter": 3, "revenue": 44000000 }, { "quarter": 4, "revenue": 46500000 }],
    "pessimistic":[{ "quarter": 1, "revenue": 32000000 }, { "quarter": 2, "revenue": 34500000 }, { "quarter": 3, "revenue": 36000000 }, { "quarter": 4, "revenue": 37500000 }]
  },

  "closure_risk": {
    "risk_score": 0.27,
    "risk_level": "caution",
    "top_signals_lgbm": [
      { "feature": "임대료 상승률", "feature_key": "rent_growth_yoy", "contribution": 0.12 },
      { "feature": "유동인구 변화", "feature_key": "floating_pop_change", "contribution": -0.08 }
    ],
    "summary_lgbm": ["과거 마포구 동종업종 폐업 패턴 대비 평균 수준입니다."],
    "top_signals_tcn": [],
    "summary_tcn": [],
    "is_mock": false
  },

  "competitor_intel": {
    "market_entry_signal": "yellow",
    "competition_500m": {
      "samples": [
        { "place_name": "스타벅스 홍대2호점", "distance_m": 240, "is_franchise": true }
      ]
    },
    "cannibalization": { "estimated_revenue_impact_pct": -0.18 }
  },

  "trend_forecast": {
    "forecast": { "score": 72, "direction": "growth", "confidence": "medium",
      "narrative": "2025 Q4 기준 마포 카페 검색 트렌드 +14% YoY" },
    "industry_trend": { "direction": "up" },
    "change_ix": { "change_ix_label": "상권확장" },
    "macro": { "base_rate": 3.25 }
  },

  "demographic_report": {
    "core_demographic": { "age": "30대", "gender": "여성", "share": 0.34 },
    "top_3_age_groups": [
      { "age_group": "30대", "share": 0.34 },
      { "age_group": "20대", "share": 0.28 },
      { "age_group": "40대", "share": 0.21 }
    ],
    "peak_consumption_hours": ["12-14시", "18-20시"],
    "weekday_weekend_ratio": 1.4,
    "resident_visitor_ratio": 0.65,
    "area_income_level": "mid",
    "population_trend": "stable",
    "elderly_ratio": 0.12,
    "brand_target_match_score": 0.78,
    "match_rationale": "타겟 30대 여성 비중 34% — 브랜드 핵심 페르소나와 일치",
    "narrative": "서교동은 30대 여성 직장인 비중이 높고 점심·저녁 피크가 뚜렷합니다.",
    "peak_hour_matrix": null
  },

  "agent_attributions": [
    { "id": "market_analyst", "display_name": "상권 분석", "kind": "Hybrid",
      "sources": ["서울 열린데이터(유동인구)", "국토부 실거래가"],
      "verdict": "양호", "reasoning": "유동인구 78점, 임대료 64점", "confidence": 0.82 },
    { "id": "population_analyst", "display_name": "인구 분석", "kind": "Python",
      "sources": ["KOSIS 인구주택총조사 2024"],
      "verdict": "안정", "reasoning": "30대 유입 +3.4%", "confidence": 0.74 },
    { "id": "demographic_depth", "display_name": "인구 심층", "kind": "Hybrid",
      "sources": ["서울 생활인구 2024 Q4"],
      "verdict": "타겟 매칭 우수", "reasoning": "...", "confidence": 0.78 },
    { "id": "competitor_intel", "display_name": "경쟁 인텔", "kind": "Python",
      "sources": ["카카오 로컬 API"],
      "verdict": "주의", "reasoning": "500m 12개 매장", "confidence": 0.69 },
    { "id": "trend_forecaster", "display_name": "트렌드 예측", "kind": "Hybrid",
      "sources": ["네이버 데이터랩 2024", "한국은행 ECOS"],
      "verdict": "성장", "reasoning": "검색량 +14% YoY", "confidence": 0.66 },
    { "id": "legal", "display_name": "법률 리스크", "kind": "RAG",
      "sources": ["가맹사업법", "임대차보호법"],
      "verdict": "주의", "reasoning": "정보공개서 등록 확인 필요", "confidence": 0.81 },
    { "id": "district_ranking", "display_name": "입지 랭킹", "kind": "Python",
      "sources": ["내부 가중치 모델 v3"],
      "verdict": "1위", "reasoning": "종합 78.4점", "confidence": 0.84 },
    { "id": "synthesis", "display_name": "종합", "kind": "LLM",
      "sources": ["전 에이전트 결과 종합"],
      "verdict": "GO(조건부)", "reasoning": "법률 caution 해소 시 진입 권장", "confidence": 0.77 }
  ],

  "all_competitor_locations": [
    { "id": "k_12345", "place_name": "스타벅스 홍대2호점", "brand_name": "스타벅스",
      "lat": 37.5563, "lng": 126.9236, "distance_m": 240, "is_franchise": true, "source_dong": "서교동" }
  ],

  "customer_segment": {
    "segment_ratio": 0.34,
    "segment_sales": 14110000,
    "identified_sales": 41500000,
    "total_sales_ref": 41500000,
    "profile_summary": "30대 여성 평일 점심",
    "dimension_ratios": { "age:30대": 0.34, "gender:female": 0.58, "time:lunch": 0.41, "day:weekday": 0.71 }
  },

  "final_report": {
    "summary": "서교동 1순위 추천. 단 경쟁 포화도 yellow 주의.",
    "is_direct": false,
    "brand_category": "cafe",
    "overall_legal_risk": "caution",
    "final_recommendation": "서교동 진입 + 6개월 내 차별화 메뉴 1종 출시 권장",
    "profit_simulation": {
      "monthly_revenue": 41500000,
      "monthly_cost": 32000000,
      "net_profit": 9500000,
      "margin_rate": 0.229,
      "bep_months": 8.4
    },
    "competitor_analysis": {
      "count": 12,
      "density": "high"
    }
  }
}
```

### 5.1 부분 실패 샘플 (LLM 일부 에이전트 실패 시)

```json
{
  "request_id": "sim_2026-04-24_partial",
  "target_district": "서교동",
  "analysis_report": "...",
  "analysis_metrics": { "district_grade": "GOOD", "growth_rate": 0.087, "competition_score": 62, "rent_affordability": "mid" },
  "simulation_months": 12,
  "quarterly_projection": [],
  "comparison": [],
  "legal_risks": [],

  "shap_result": null,
  "closure_risk": null,
  "trend_forecast": null,
  "demographic_report": null,

  "agent_attributions": [
    { "id": "market_analyst", "display_name": "상권 분석", "kind": "Hybrid", "sources": [], "verdict": "—",
      "reasoning": "DB 연결 실패", "confidence": null }
  ]
}
```

→ 프론트는 위 응답을 받으면 SummaryTab에서 **UNKNOWN** verdict, 각 탭 카드는 dashed empty state로 그립니다. 프로덕션 사고가 아니라 정상 부분실패 케이스로 처리됩니다.

---

## 6. (참고) 프론트 측 미해결 아키텍처 이슈

C2 명세 작업과 직접 관련은 없지만 백엔드 합의 필요 — 별도 트랙으로 협의 부탁드립니다.

1. **F5 새로고침 시 상태 소실**: 현재 `runSimulation()`은 동기형(10분 axios). job_id 기반 비동기 패턴(`POST /simulate` → `{job_id}` → `GET /status/{job_id}` 폴링 또는 SSE) 도입 시 새로고침 복원 가능. `getStatus()` 시그니처는 이미 `JobStatus` 형태로 예약돼 있음(`api/client.ts:147`).
2. **LLM rate-limit / quota**: 동시 시뮬레이션 N개 초과 시 백엔드 429 응답 후 토스트 안내가 깔끔.
3. **`/ops/token-usage`**: 현재 404 정상, B1 예진 구현 대기. 응답 스키마는 `frontend/src/types/tokenUsage.ts` 주석 참조(LangSmith 연동 가정).

---

## 변경 이력

| 날짜 | 작성자 | 내용 |
|---|---|---|
| 2026-04-24 | C1 강민 | 초안 — C2 혁 요청 응답. dashboard 8탭 / mock-fallback 제거 / bep_quarters / closure_risk lgbm·tcn 분리 / UNKNOWN verdict 모두 반영 |
