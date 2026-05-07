# 마포구 프랜차이즈 상권분석 시뮬레이터

AI Agent 기반 프랜차이즈 출점 시뮬레이션 플랫폼

## 프로젝트 개요

프랜차이즈 본사 영업기획팀이 마포구 내 신규 출점 후보지를 동(洞) 단위로 시뮬레이션하여,
카니발리제이션(자기 잠식), 경쟁 환경, 매출 예측, 법률 리스크를 종합 분석하는 AI 도구입니다.

## 핵심 기능

- **상권 분석**: 마포구 16개 행정동의 생활인구, 경쟁 밀도, 소비 패턴 분석
- **카니발리제이션 분석**: 같은 브랜드 기존 매장과의 매출 잠식률 산출 (Pancras et al. 2012 모델)
- **간접 경쟁 분석**: 동일 업종 + 대체재(배달 야식 등) 경쟁 반영
- **매출 예측 (7+ 모델)**: LSTM/TCN/GRU forecast (12개월 매출), closure_risk LightGBM+TCN ensemble, customer_revenue MLP, revenue_predictor BEP, SHAP explainability, emerging_district 분류
- **법률 리스크**: 9 rules + 4 RAG specialists 코드 정의 → **운영 5 카테고리 (food_hygiene/labor/vat/privacy/sewage) 비활성** → 실제 활성 **8 카테고리** (5 입지 룰 + 3 specialist) 반환 (BGE-m3 + Kiwi BM25 RRF + GPT-4.1-mini rerank)
- **ABM 시뮬레이션**: 마포 5,000 에이전트 (Tier S/A/B 계층화, LLM 활성 시 gpt-4.1-mini 통일 — v5 2026-04-29)
- **사업자번호 기반 운영 업종 자동 차단**: FTC 가맹사업 정보공개서 매칭으로 운영 외 업종 dropdown disable
- **What-if 시나리오**: 경쟁 진입, 임대료 변동, 정책 변화 시 재시뮬레이션

## 기술 스택

### 인프라 / 배포

| 항목 | 기술 |
|------|------|
| 컨테이너 | Docker, Docker Compose |
| 프론트 서빙 | Nginx |
| 백엔드 서버 | Uvicorn |
| DB | AWS RDS (PostgreSQL 16 + pgvector + HNSW index) — local docker postgres 제거 완료 |
| 캐시 | Redis 7 |
| Vector DB | AWS RDS pgvector + HNSW index (BGE-m3 1024D, 10,255 legal chunks) |

### 백엔드

| 분류 | 기술 |
|------|------|
| 프레임워크 | FastAPI, Pydantic v2 |
| ORM / 마이그레이션 | SQLAlchemy 2.0, Alembic, asyncpg, psycopg3 |
| AI 오케스트레이션 | LangGraph, LangChain |
| LLM | Claude (Anthropic), Gemini (Google), OpenAI |
| 임베딩 / RAG | pgvector, sentence-transformers, LangChain-HuggingFace |
| 딥러닝 모델 | PyTorch(TCN), scikit-learn, SHAP |
| 데이터 처리 | pandas, numpy, geopandas |
| PDF 파싱 | pdfplumber, PyPDF2 |
| 관측성 | LangSmith |
| 인증 | bcrypt + JWT (HS256) |
| HTTP 클라이언트 | httpx, requests, tenacity (재시도) |
| ABM | 자체 구현 — `backend/src/simulation/` (mesa 등 외부 ABM 라이브러리 미사용) |

### 프론트엔드

| 분류 | 기술 |
|------|------|
| 프레임워크 | React 18, TypeScript 5, Vite 6 |
| 스타일 | Tailwind CSS, PostCSS |
| 지도 | Leaflet, react-leaflet |
| 차트 | Recharts |
| 애니메이션 | Framer Motion |
| HTTP | Axios |
| 마크다운 | react-markdown |
| 내보내기 | jsPDF, html2canvas, xlsx |
| 아이콘 | lucide-react |
| 라우팅 | react-router-dom v6 |

### 개발 도구

| 분류 | 기술 |
|------|------|
| Python 포맷터 | Ruff (check + format) |
| JS 포맷터 | Prettier |
| JS 린터 | ESLint |
| Git 훅 | pre-commit (Ruff + Prettier 자동 실행) |
| 이슈 트래킹 | Jira |

## 팀원별 담당 영역

### 트랙 A — 데이터 + RAG

| 역할 | 담당자 | 담당 디렉토리 |
|------|--------|-------------|
| A1 — 데이터 엔지니어 | 찬영 | `backend/src/services/`, `backend/src/database/`, `data/` |
| A2 — RAG + 법률 | 봉환 | `backend/src/chains/`, `backend/src/database/vector_db.py` |

### 트랙 B — AI 엔진

| 역할 | 담당자 | 담당 디렉토리 |
|------|--------|-------------|
| B1 — LangGraph Agent | 예진 | `backend/src/agents/`, `backend/src/schemas/` |
| B2 — 딥러닝 모델 | 수지니 | `models/`, `validation/` |

### 트랙 C — 프론트엔드 + 배포

| 역할 | 담당자 | 담당 디렉토리 |
|------|--------|-------------|
| C1 — 프론트엔드 | 강민 | `frontend/` |
| C2 — 인프라 + PM | 혁 | Docker, Nginx, `docs/`, `tests/` |

## AI 에이전트 아키텍처

### 5-Phase LangGraph 워크플로우 (2026-05 현재)

```
START
  │
  ▼
[Phase 0] inflow             교통·집객 인프라 16동 점수 (Python, ~50ms)
  │
  ▼
[Phase 1] ranking_phase      district_ranking (16동 정량 스코어링, LLM 없음)
  │                          → winner_district 확정 (inflow 15% 반영)
  ▼
[Phase 2] llm_analysis_phase 6 LLM 에이전트 병렬 (asyncio.gather)
  │   ├── Market Analyst        상권 + 매출 추이 LLM 분석
  │   ├── Population Analyst    생활인구 + 시간대 트렌드
  │   ├── Legal Analyst         9 rules + 4 specialists 정의 → 운영 5 비활성 → 활성 8 (5 입지 룰 + 3 specialist)
  │   ├── Demographic Depth     연령/성별 코호트 적합도
  │   ├── Trend Forecaster      Naver DataLab + SNS 트렌드
  │   └── Competitor Intel      직접/간접 경쟁 + 카니발리제이션
  ▼
[Phase 2.5] ml_prediction    TCN 매출 예측 + BEP + 폐업위험도 (LightGBM)
  │                          (full graph 만 실행 — slow_graph 는 제외)
  ▼
[Phase 3] synthesis          7 결과 종합 → ai_recommendation 생성
  │
  ▼
END
```

### 2-Endpoint 분리 (IM3-259, 2026-04~05)

빠른 ML 결과 + 느린 LLM 결과를 frontend 가 동시 polling 으로 받아 점진적 UI 갱신.

| Endpoint | 그래프 | 용도 | 응답 시간 |
|----------|--------|------|----------|
| `POST /predict` | (LangGraph 미사용) | 동 1~4 TCN/BEP/폐업률/SHAP 병렬 | ~10s |
| `POST /analyze/llm` | `slow_graph` (Phase 0~3, ML 제외) | 6 LLM + synthesis | ~80~140s |
| `POST /predict/async` + `GET /predict/{job_id}/status` | — | 250ms polling, 동별 진행률 | — |
| `POST /analyze/llm/async` + `GET /analyze/llm/{job_id}/status` | — | 250ms polling, 노드별 25%/50%/75%/100% | — |
| `POST /simulate-abm` | (LangGraph 미사용) | 마포 5,000 에이전트 ABM 시뮬 | ~30~60s |
| `GET /corp/operated-industries` | — | JWT user → corp 운영 업종/brand list (frontend dropdown gate) | ~50ms |
| `GET /stores/count-by-dongs?dongs=...&category=...` | — | 동 list × 업종 카테고리 매장 수 — frontend ScopeHint 라이브 카운트 | ~30ms |
| `POST /simulate` | `app_graph` (Phase 0~3 전체) | **deprecated** — IM3-259 이후 두 endpoint 분리 | ~150s |

> **변경 이력**: 초기 `Supervisor → 순차 실행` → 4 에이전트 병렬 → 5-Phase + 6 에이전트 + ML 분리 + LangGraph 2 인스턴스로 진화. `/simulate` 단일 endpoint 는 deprecated.

### Sub-routers (`backend/src/api/`)

main.py 40 endpoint 외 5개 도메인별 router 분리 (실측 18 endpoint):

| Router | Endpoint 수 | JWT | 용도 |
|--------|-----------|-----|------|
| `vacancy_evaluation` | 8 | No | ABM PSE 공실 평가 |
| `customer_segment` | 1 | No | MLP 단발 — frontend 실시간 미리보기 |
| `simulation_foresee` | 4 | Required | ML 예측 결과 저장 / 조회 / 삭제 |
| `simulation_ai` | 4 | Required | LLM 분석 결과 저장 / 조회 / 삭제 |
| `sensitivity` | 1 | No | TCN 시나리오 탄성치 캐시 서빙 |

### 행정동 입지 랭킹 알고리즘

마포구 16개 행정동을 LLM 없이 순수 Python 연산으로 점수화합니다.

| 지표 | 기본 가중치 | 인구가중치 ON | 인구가중치 OFF |
|------|-----------|------------|-------------|
| 매출 성장률 (QoQ) | 40% | 35% | 50% |
| 유동인구 성장률 (QoQ) | 30% | 45% | 10% |
| 임대료 저렴도 | 30% | 20% | 40% |

예산 초과 페널티: `월 임대료 예산 ÷ 매장 면적(평)` = 평당 허용 임대료. 초과 시 점수 최대 50% 감점.

### 사용자 입력 → 에이전트 반영 매핑

| 입력값 | 반영 위치 | 효과 |
|--------|---------|------|
| 동 선택 (target_district / target_districts) | market / population / TCN | 심층 분석 + 차트 + 동별 매출 예측 |
| 업종 선택 (business_type) | 전 에이전트 DB 쿼리 + corp_brand_resolver | 업종별 매출/경쟁/법률 분리 + 운영 외 업종 차단 |
| 상권 반경 (commercial_radius) | market_analyst | 경쟁 업체 탐색 반경 (기본 500m) |
| 자사 영업구역 거리 (territory_radius_m) | competitor_intel | 가맹사업법 §12-4 정량 룰 (기본 250m) |
| 임대료 예산 + 매장 면적 | district_ranking | 예산 초과 동 순위 하락 (평당 허용 임대료) |
| 인구 가중치 (population_weight) | district_ranking | 가중치 동적 변경 → winner_district 변경 |
| 사업자번호 (biz_number) | `_validate_and_resolve_brand` | corp 운영 외 업종 → HTTP 400 차단 + 다업종 brand auto-resolve |
| 자사 brand 명시 선택 (brand_name) | `corp_brand_resolver` honor-input | 동업종 다brand corp (예: 더본 한식 = 한신포차/새마을식당/본가) frontend dropdown 으로 명시 선택 — backend top frcsCnt 자동 override 회피 |
| 목표 객단가 / 시간대 / 초기 자본금 | synthesis LLM + BEP | ai_recommendation + BEP 개월수 |
| 타겟 연령대 (target_age_groups, 10~60대+) | demographic_depth | 연령 코호트 적합도 점수 |
| 타겟 성별 (target_gender, male/female/null) | demographic_depth | 성별 매출 비중 매칭 |
| 타겟 시간대 (target_time_slots, time_00_06 등) | trend_forecaster | 시간대별 유동인구 적합도 |
| 평일/주말 (target_day_type) | trend_forecaster | 요일 타입 트렌드 매칭 |
| 목표 월매출 (target_monthly_sales, 옵셔널) | BEP 가드 | BEP 도달 가능성 검증 |
| 매장 좌표 (store_lat / store_lon, 옵셔널) | rule_school_zone | 주점 업종 시 50/200m haversine 학교 buffer 룰 |

### API 주요 응답 필드

**`POST /analyze/llm`** 응답 (AnalysisOutput):

```jsonc
{
  "status": "success",
  "data": {
    "brand_name": "새마을식당",                      // 입력 브랜드 echo (Target 라벨 SoT)
    "business_type": "한식",                         // 입력 업종 echo
    "ai_recommendation": "AI 최종 분석 요약 (synthesis 에이전트)",
    "winner_district": "성산2동",
    "top_3_candidates": ["성산1동", "망원2동", "염리동"],
    "district_rankings": [ /* 16개 동 전체 점수 */ ],
    "market_report": {
      "floating_population": 70,
      "rent_index": 50,
      "competition_intensity": 60,
      "estimated_revenue": 75,
      "survival_rate": 40,
      "growth_potential": 30,
      "accessibility": 75
    },
    "legal_risks": [ /* 활성 8 카테고리 (5 입지 룰 + 3 specialist, 운영 5 비활성) */ ],
    "overall_legal_risk": "CAUTION",
    "all_competitor_locations": [ /* 지도 멀티핀 */ ],
    "same_brand_locations":   [ /* 카니발리제이션 시각화 */ ]
  }
}
```

**`POST /predict`** 응답 (DistrictPredictionResult[]):

```jsonc
{
  "status": "success",
  "data": [
    {
      "district": "성산2동",
      "predicted_monthly_revenue": 38500000,
      "quarterly_projection": [ /* 4 분기 매출 */ ],
      "bep_months": 14,
      "closure_risk": 0.23,
      "shap_result": { /* 폐업위험도 SHAP 기여도 */ }
    }
  ]
}
```

**`GET /corp/operated-industries`** (JWT 옵셔널):

```jsonc
{
  "company_name": "(주)더본코리아",
  "industries": ["분식","서양식","제과제빵","주점","중식","커피","피자","한식"],
  "brands": [
    {"name": "빽다방", "industry": "커피", "stores": 1712},
    {"name": "홍콩반점0410", "industry": "중식", "stores": 293}
  ]
}
```

비회원/CORP 미등록 시 `{"industries": null}` → frontend 모든 업종 허용 (graceful degrade).

**Brand dedup 정책** (`corp_brand_resolver.py`, 2026-05-07):
- `yr=2025` + `frcsCnt > 0` 만 후보로 (이전 `MAX(frcsCnt)+GROUP BY` 제거 — 연도별 표기 변형 'BBQ' vs '비비큐(BBQ)' 별 row 분리 회피)
- 2단계 정규화 dedup: ① exact match (괄호/공백 제거 + 대문자) ② substring 포함 — 같은 brand 다양 표기 통합 후 frcsCnt 큰 row 보존
- 결과: `(주)더본코리아` 27 brand → dedup 후 ~22 brand (5 표기 변형 합쳐짐)

### Redis 캐싱 전략 (24h TTL)

각 LLM 노드가 자체 `_CACHE_TTL = 86400` 으로 결과 캐싱. 모든 키는 `v{N}:` schema-version prefix 포함 — schema 변경 시 N 증분으로 무효화. 실제 키 구성은 노드 파일 참조.

| 에이전트 | 키 패턴 (실측) | 파일 |
|---------|--------|------|
| market_analyst | `v2:market:{target_district}:{business_type}` | `nodes/market_analyst.py:32` |
| population | `v2:population:{target_district}:{business_type}` | `nodes/population.py:48` |
| legal | `v11:legal:{brand}:{district}:{biz}:{store_area}:{coord}:{territory}` | `nodes/legal.py:927` |
| demographic_depth | `v5:demographic:{brand_name}:{dong_code}:{industry_filter}` | `nodes/demographic_depth.py:582` |
| trend_forecaster | `v2:trend_forecast:{target_district}:{industry}:{brand_name}` | `nodes/trend_forecaster.py:46` |
| competitor_intel | `v4:competitor_intel:{dong_code}:{brand_name}:{spot_key}` | `nodes/competitor_intel.py:395` |
| district_ranking | `v14:ranking:{biz}:{pop_weight}:{budget}:{area}:{dists}:{brand}:{territory}` | `nodes/district_ranking.py:852` |
| synthesis | `v14:synthesis:{brand}:{winner}:{td_key}:{biz}:{budget}:{area}:{pop_weight}` | `nodes/synthesis.py:81` |

### Vector RAG (Legal)

AWS RDS pgvector + HNSW index 단일 저장.

- **임베딩 모델**: BGE-m3 (1024D, multilingual, 한국어 법률 텍스트 최적)
- **코퍼스**: 10,255 chunks (`backend/data/legal/processed/chunks.json`)
  - 가맹사업법 / 상가임대차보호법 / 식품위생법 / 근로기준법 / 소방시설법 / 건축법 / 다중이용업소법 / 학교보건법 / 마포구 조례
  - parent-child chunking (chunk_id → parent_articles.json 매핑)
- **검색**: Hybrid BM25 (Kiwi 한국어 형태소) + vector + RRF (vec=0.4 / bm25=0.6) — Recall 0.408 NDCG 0.273
- **재정렬**: gpt-4.1-mini list-wise — MRR 0.785→0.931 NDCG 0.642→0.776 (+19%/+21%)
- **본법 boost**: `PRIMARY_LAW_BOOST=2.0` — 시행령이 본법 article 밀어내는 현상 완화 (Hit 100% MRR 0.570)
- **부칙 감점**: `BM25_SUPPLEMENTARY_PENALTY=0.4` — 적용례/경과조치/특례 chunk 감점
- **HyDE / multi-query**: default OFF (효과 미미, 비용 부담)
- **판례 RAG**: 대법원 등 category='판례' chunk top_k=2 동시 검색 → summary/recommendation 인용

---

## ML 모델 레이어 (`models/`)

backend 외부 `models/` 디렉토리에 분리 — `sys.path` insert 후 `from models.xxx import ...` 패턴.

| 모델 | 용도 | 학습 전략 | 비고 |
|------|------|---------|------|
| `lstm_forecast` | 12개월 매출 추이 | 서울 pretrain → 마포 finetune, val_ratio=0.2 random | 34-feature scaler |
| `tcn_forecast` | TCN 변형 (n_channels=128, kernel=2, dilations=[1,2]) | val_quarter=20241 시간 holdout (commit 8768cc81) | window_size=4 |
| `gru_forecast` | GRU baseline | val_ratio=0.2 random | 비교용 |
| `closure_risk` | 폐업위험도 ensemble | **시간 holdout**: train 2019Q1~2022Q4 / val 2023Q1~Q4 / test 2024Q1~Q3 | LightGBM 0.48 + TCN 0.52, val AUC 0.569 / test AUC 0.615 (production +20% lift) |
| `customer_revenue` | 고객별 매출 MLP | interval split | 50K weights, 2026-04-29 retrain, startup 워밍업 |
| `revenue_predictor` | BEP 손익분기 + 12개월 생존율 | INDUSTRY_DEFAULTS 10 식음료 카테고리 | 변동비율 0.26~0.42 |
| `explainability` | SHAP 기여도 시각화 | GradientExplainer / DeepExplainer | mock fallback (seed=42) |
| `emerging_district` | 신흥/포화 상권 분류 | — | 신흥 트렌드 chip + 변화 1위 배지 |
| `living_pop_forecast` | 마포 동별 생활인구 시간대 피크 예측 | predict_naive (DB lag-1, TCN v2 weights 미제공) | 24시간대 × 분기별 peak hour 산출 |

---

## ABM 시뮬레이션 (`backend/src/simulation/`)

마포 5,000 에이전트 행위 기반 시뮬 — POST `/simulate-abm`. (backend default `n_agents=100`, frontend `AbmTab.tsx` 가 항상 `n_agents=5000` 명시 전송, Tier 분포 비율 5/20/75 자동 scale)

### Tier 분포 (3-tier 비용 최적화)

| Tier | 인구 | LLM | 비용 비중 |
|------|-----|-----|----------|
| **S** | 250 (5%) | gpt-4.1-mini (`main.py:2686` 가 ModelConfig 의 anthropic Haiku 기본값을 OpenAI 로 override, v5 통일 2026-04-29) | ~75% (고정밀 의사결정) |
| **A** | 1,000 (20%) | gpt-4.1-mini (Gemini Flash-Lite 기본값을 OpenAI 로 override) | ~20% |
| **B** | 3,750 (75%) | Rule-based (0 LLM) | 0% (사전 계산 policy) |

> 주: `enable_llm_decisions=False` (기본) 시 전 Tier 가 policy_cache 만 사용해 LLM 호출 0건. `True` 일 때만 위 모델 적용.

### 구조

- **31 Archetype** (`backend/src/simulation/archetypes.py:ARCHETYPES`): homebody / routine_local / trendy_local / family_cook / fitness / night_owl 등 × 6 role (resident / commuter / visitor / owner / ext_commuter / ext_visitor)
- **Layer 2/3/5**:
  - L2: visit_history + learned_prefs + blacklist (incremental satisfaction index O(1))
  - L3: hunger / fatigue / mood / budget per tick
  - L5: pending_recommendations (친구 social network)
- **55 PersonaPolicy**: role × weather 조합 hardcoded (~11 LLM init call) → policy_cache.json → Tier B agent 0 LLM
- **Memory Seed**: Stanford UIST'23 Generative Agents 모델 (Tier S only) + batch_smart_decide fallback (Tier B)

### 비용 진화

`docs/abm-simulation/agent-dsl-cost-analysis.md` 참고:
- 초기 LLM 시뮬: $0.7/일
- DSL 압축 + Tier 계층화: **$0.05~0.07/일** (75~93% 절감)

### Frontend 통합

- `AgentMapVisualizer` (Leaflet 기반) — agent trajectory + current_action (rest/visit/work/move) 실시간 렌더
- `AbmTab` — dashboard 통합 뷰
- spot click → ABM 시뮬 trigger → 결과 overlay drill-down

---

## Frontend 라우트 + Dashboard 구조 (`frontend/src/`)

### Routes (실측 17 경로)

| 경로 | 컴포넌트 | 권한 |
|------|---------|------|
| `/` | IntroScene | Public |
| `/about` | AboutPage | Public |
| `/joinus` | JoinUsPage (master + manager signup) | Public |
| `/explore` | AccordionGallery (25 자치구 showcase) | Public |
| `/engine` | EnginePage | Public |
| `/contact` | ContactPage | Public |
| `/login` | LoginPage | Public |
| `/simulator` | SimulatorDashboard (메인 폼) | Auth |
| `/dashboard` (index) | DashboardHubRouteElement | Auth |
| `/dashboard/predict` | DashboardPredictPage | Auth |
| `/dashboard/analyze` | DashboardAnalyzePage | Auth |
| `/dashboard/abm` | DashboardAbmPage | Auth |
| `/dashboard/history/:id` | SimulationHistoryDetail (legacy) | Auth |
| `/dashboard/foresee/:id` | SimulationHistoryDetail (kind=foresee) | Auth |
| `/dashboard/ai/:id` | SimulationHistoryDetail (kind=ai) | Auth |
| `/hq` | HQCommandCenter | Auth (master/superadmin) |
| `/hq/managers/:id` | ManagerDetail | Auth |

### Dashboard Hub (3-card)

`DashboardHub` 진입 시 3 카드 — `/predict` (ML 결과) | `/analyze` (LLM 결과) | `/abm` (ABM 시뮬). 각 카드 disabled/loading state 분리.

### 5+ Core Tabs (per dashboard)

`AbmTab`, `DemographicTab`, `FinancialTab`, `InsightTab`, `LegalTab`, `MarketTab` + sub-tab drill-down (`PredictCustomerFlowTab`, `PredictFinancialSimTab`, `PredictSalesForecastTab`, `PredictScenarioSimTab`, `PredictEmergingDistrictTab`, `AnalyzeAgentInsightTab`, `AnalyzeAiSummaryTab`, ...).

### 차트 (Recharts 20+)

ClosureRateHistoryChart / CoreDemographicDonut / CustomerFlowSegmentChart / BepCumulativeProfitChart / AgentConfidenceRadar / ClosureRiskHeatmap / LegalDistributionBar / ScenarioForecastChart 등.

### State (Zustand)

- `simulationStore` — params + status + **prediction slice** (status, data, error, progress, stage) + **analysis slice** (동일 구조) + retry helper. IM3-259 dual-pipeline 대응.
  - **Dual-track save** (2026-05-07): `savedForeseeId` (ML 결과) + `savedAIId` (LLM 결과) 분리 state. Predict tab 과 Analyze tab 이 독립적으로 save 가능 (이전 단일 `savedHistoryId` 충돌 해소). legacy field 도 backward compat 으로 유지.
- `abmStore` — ABM 시뮬 별도 상태
- `toastStore` — toast notification

### Auth UX

- localStorage `spotter_auth = {user, brand, token}`
- JWT Bearer interceptor 자동 주입 (`X-Tenant-ID` + `Authorization`)
- 401 → localStorage 청소 + `/login?reason=session_expired&redirect=...` 리다이렉트
- Boot 시 zombie state self-heal (user 있고 token 없으면 청소)

---

## 트랙별 작업 이력

### B1 — LangGraph Agent (예진)

#### 7 LLM agent 정확도 v7 재설계 (2026-05-07)
- v6 LLM-as-judge → v7 rule-engine + 직접 metric 비교 (deterministic 평가)
- 정확도 향상: market_analyst 50%→87.5% (+37.5%p), demographic_depth 83%→100% (+16.7%p), trend_forecaster 67%→82% (+15.1%p)
- 캐시 schema: population/market_analyst 노드가 `raw_metrics` + `raw_inputs` 보존 (v1→v2 prefix)
- 신규 스크립트: `backend/scripts/eval/run_all_agents_v7.py` (382 line) + `seed_eval_cache.py` + `docs/team/agent-accuracy-v6-vs-v7.md`

#### emerging_district 성능 -86% (2026-05-07)
- `load_timeseries` TTL 캐시 (300s) — closure_risk / TCN / SHAP 와 공유
- main.py startup 시 마포 timeseries 워밍업 — 첫 호출 cold start 제거
- 벤치: 3.86s → 0.17s (-95.6%, 단일), 8.11s → 1.12s (-86.2%, 동별)
- 벤치 스크립트: `bench_per_component.py`, `bench_emerging_breakdown.py` 등 4종

#### IM3-259 · 2 endpoint 분리 (2026-04~05)
- `/predict` (TCN ML) + `/analyze/llm` (slow_graph) 분리 — frontend 동시 polling
- `app_graph` (full 5-Phase) + `slow_graph` (LLM 만, ML 제외) 2 인스턴스
- async polling endpoint + LangGraph `astream(stream_mode="updates")` 노드 진행률 hook
- ABM peak_hours fix — `trajectory_path` 가드가 `visits_log` 채움 차단했던 회귀 복구

#### IM3-180 · IM3-32 (2026-04)
- Supervisor / ContextAnalyst 제거, asyncio.gather 4 → 6 에이전트 병렬
- District Ranking 16동 정량 스코어링 신규 개발 (LLM 없음)
- LLM 전환: gemini-2.5-flash → gpt-4.1-mini

#### IM3-144 (2026-04)
- 프론트 실데이터 연동 (`ai_recommendation`, `market_report` 7 지표, `winner_district`, `top_3_candidates`)
- 요청 중복 방지 dedup (`_pending_pipelines`) — DB 풀 고갈 방지
- 9개 사용자 입력 → 랭킹 가중치·예산 필터·synthesis 프롬프트 전반영
- 업종코드 정규화 (`_SALES_CODE_MAP` CS100001~10)

### A1 — 데이터 + Brand 매핑 (찬영)

#### IM3-brand-mega-canonical-fix · corp 운영 외 업종 차단 (2026-05)
- `corp_brand_resolver` — users.company_name → ftc_brand_franchise.corpNm REGEXP_REPLACE ILIKE 매칭
- `GET /corp/operated-industries` — JWT user 자동 추출, 비회원/CORP 미등록 graceful degrade
- frontend dropdown 운영 외 업종 disable + line-through + click toast
- 다업종 corp 자동 brand 매핑: (주)더본코리아 8 업종 27 brand → 사용자 선택 업종의 top frcsCnt brand auto-resolve
- 동업종 다brand corp 명시 선택 dropdown (App.tsx, 2026-05-07): selectedBrandName state — 한식 선택 시 한신포차/새마을식당/본가 후보 노출, top frcsCnt auto-fallback
- corp_brand_resolver dedup (2026-05-07): yr=2025 + frcsCnt>0 필터 + 2단계 normalize ('BBQ' ↔ '비비큐(BBQ)' 표기 변형 통합)
- Target 라벨 buggfix (2026-05-07): AnalysisOutput schema 에 brand_name + business_type 필드 추가 — payload echo 로 frontend MapSection Target 표시가 authBrand fallback (등록 brand 빽다방) 으로 가는 회귀 차단

#### `/stores/count-by-dongs` 라이브 매장수 endpoint (2026-05-07)
- frontend ScopeHint 가 selectedDongs 변경 시 실시간 호출 — 동 list × business_type 카테고리 매장 수 집계
- 클라이언트 추정값 → 서버 SQL 집계로 교체 (정확도 100%)
- AbortController 패턴 + 로딩 spinner + fetch 실패 시 fallback

#### IM3-alembic-user-lifecycle-catchup · DB schema 정합 (2026-04~05)
- alembic phantom revision 복구 (a9c2d3e4f5b6 zombie 제거) → head `a8f3d2e7c1b9`
- simulation_history drop (91b66e68ec18) → simulation_foresee + simulation_ai 분리 대체
- 78 ORM / 1,019 컬럼 / 32 FK 전수조사 + ORM 정합 (IndustryMaster / MartBrandTerritory / DongCentroid 신규)
- dong_code FK Group A/B1/B2 audit (8자리 String 통일)
- master 메타 backfill (dong_mapping/industry_master/master_subway/ttareungi/realtime_hotspots/weather_daily)
- 외부 API 백필 (ETL 5종):
  - `fill_subway_coords_seoul.py` — 서울 지하철 좌표 채움
  - `fill_ttareungi_dong_code.py` — 따릉이 마포 dong_code haversine 매핑
  - `backfill_ecos_cycle.py` — ECOS cycle 컬럼 100% 채움 (2,783/2,783)
  - `refresh_realtime_hotspots.py` — 서울 실시간 핫스팟 갱신
  - `backfill_master_meta.py` — dong/industry 메타 enrichment
- `dong_resolver.validate_dong_code(strict=True)` SoT helper

#### IM3-178 · `business_type_mapping` SoT 통합 (2026-04)
- 10종 TypedDict, ftc_keywords DB 정합 ('서양식'/'제과제빵'/'피자' → 패스트푸드)
- `_BIZ_TYPE_NORMALIZE` + `_KAKAO_CATEGORY_MAP` + `_SALES_CODE_MAP` 단일 소스화

### A2 — RAG + 법률 (봉환)

#### Legal Rule Engine (2026-05)
- 9 rules (food_hygiene / safety_regulation / fire_safety / accessibility / commercial_lease / labor / vat / sewage / school_zone) + 4 specialists (franchise_law / fair_trade_law / building_law / privacy_law) **코드 정의 13** → orchestrator `_RULE_ENGINE_ORDER` 가 운영 카테고리 5종 (food_hygiene/labor/vat/privacy/sewage) 비활성 → **실제 활성 8** (5 입지 룰 + 3 specialist) — frontend 미표시 + LLM 비용 절감 정책
- BGE-m3 + Kiwi BM25 RRF (vec=0.4 / bm25=0.6) — Recall 0.408 NDCG 0.273 Hit 62.1%
- Primary-law boost 2.0 (saturate) — Hit 100% MRR 0.570 NDCG 0.525
- OpenAI rerank (gpt-4.1-mini list-wise) — MRR 0.785→0.931 NDCG 0.642→0.776
- 판례 RAG (대법원) + Article LLM 풀어쓰기 (1~2문장 케이스 맞춤 설명)
- Legal z-score 폐점률 (2026-05-07): 하드코딩 10% threshold → FTC 업종별 평균/표준편차 기반 (예: 한식 평균 26.7% → 한신포차 12.9% z=-0.19 'safe' 정확 판정)
- Windows ProactorEventLoop 회피 (2026-05-07): pgvector retriever 가 sync engine + `asyncio.to_thread` 패턴 — Windows 환경 psycopg async InterfaceError 차단

### B2 — 딥러닝 모델 (수지니)

- TCN forecast: window_size=4, val_quarter=20241 (시간 holdout, commit 8768cc81)
- closure_risk LightGBM + TCN ensemble: train 2019~2022 / val 2023 / test 2024Q1~Q3
- production AUC 0.6170 (+20% lift), 12 sprint 37+ commit 7 KEEP / 5 rollback
- SHAP (GradientExplainer/DeepExplainer) 기여도 시각화

### C1 — 프론트엔드 (강민)

#### Light/Dark mode + Deep Blue palette (2026-05)
- 9 페르소나 PNG 매핑, 4-tier categorical palette
- IndicatorGrid chip + 단위 fix
- 시나리오 v2 재구조 + 동적 마포구

### C2 — 인프라 (혁)

- Docker Compose: Backend (uvicorn) / Frontend (Nginx) / Redis 7
- **AWS RDS 마이그레이션 (2026-04~05)**: docker-compose 로컬 postgres 제거 → POSTGRES_URL 외부 endpoint
- HNSW pg_vector index 마이그레이션 (cc33dd44ee55) — legal RAG 검색 가속
- LangSmith 트레이싱 통합
- Nginx 프록시: `/api/` → backend:8000, WebSocket upgrade + 300s timeout (시뮬 스트리밍)
- alembic 마이그레이션 chain head: `a8f3d2e7c1b9`

---

## Database Schema

**규모**: 78 ORM models / ~1,019 columns / 30 explicit `ForeignKey()` 선언 (`backend/src/database/models.py`)

### Naming Convention

| Prefix | 용도 | 예시 |
|--------|------|------|
| `master_` | 코드/마스터 (정적 reference) | `master_subway_station`, `master_ttareungi_station`, `master_dong`, `master_industry` |
| `seoul_` | 서울 전역 시계열 데이터 | `seoul_district_sales`, `seoul_subway_passenger_daily`, `seoul_dong_migration_monthly`, `seoul_adstrd_flpop` |
| `mapo_` | 마포구 전용 | `mapo_resident_pop`, `mapo_sns_sentiment` |
| (없음) | 서비스 기능 | `users`, `manager_users`, `simulation_foresee`, `simulation_ai`, `customer`, `invite_codes` |

### 카테고리별 주요 테이블

| 카테고리 | 테이블 |
|---------|--------|
| Population | living_population, sgis_population, sgis_household, mapo_resident_pop, seoul_population_quarterly |
| Sales | district_sales, golmok_commercial, golmok_sales, golmok_stores, seoul_district_sales, seoul_district_stores, cpi_dining_quarterly |
| Rent | rent_cost, golmok_rent, seoul_golmok_rent, jeonse_dong_master, rent_cost_summary_2025, jeonse_monthly_rent, small_store_rent_q |
| Location Master | dong_mapping, seoul_dong_master, dong_centroid, master_subway_station, master_ttareungi_station |
| Business | industry_master, store_info, store_quarterly, kakao_store, kakao_store_hours, kakao_store_menu, seoul_adstrd_(change_ix/fclty/flpop/stor) |
| Franchise / Brand | ftc_brand_franchise (16K), biz_brand_mapping, mart_brand_territory, naver_vacancy, vacancy_enriched |
| Auth | users, manager_users, invite_codes, customer |
| Simulation | simulation_foresee, simulation_ai (분리 저장) |
| Trends | naver_trend_industry, naver_trend_monthly, naver_trend_quarterly, mapo_sns_sentiment, seoul_trdar_(change_ix/flpop/stor) |
| Legal | law_legislations, law_precedents |
| Economic | ecos_key_statistics, ecos_timeseries, kosis_regional_income, molit_nrg_trade |
| Transport | bus_boarding_daily, seoul_subway_passenger_daily, seoul_ttareungi_usage_daily, seoul_dong_migration_monthly |
| 기타 | apt_trade_real, elderly_ratio_region, dong_subway_access, holiday_calendar, weather_daily, seoul_realtime_hotspots |

### Alembic Chain (최근 5)

| Revision | 설명 |
|----------|------|
| `a8f3d2e7c1b9` (head) | (가장 최근) |
| `91b66e68ec18` | drop simulation_history (zombie 정리, foresee/ai 분리 대체) |
| `f3c4d5e6a7b8` | jeonse_dong_master + FK 추가 |
| `f6ec0ac9d88c` | invite_codes + manager_users 신규 |
| `f1a2b3c4d5e6` | user lifecycle + emerging_trend merge |

---

## 실행 방법

### Docker Compose (권장)

```bash
# 환경 설정
cp .env.example .env
# .env 필수: POSTGRES_URL = AWS RDS endpoint (로컬 postgres 컨테이너 제거됨)
#          + API 키 (ANTHROPIC, OPENAI, GOOGLE, FTC, KAKAO, ECOS, NTS, ...)

# 전체 서비스 실행
docker compose up --build
```

- Frontend: http://localhost (Nginx)
- Backend API: http://localhost:8000
- Redis: localhost:6379
- PostgreSQL + pgvector: AWS RDS (외부) — `POSTGRES_URL` 환경 변수로 주입

> **참고**: 2026-04~05 기점으로 Postgres 컨테이너 제거 및 RDS 마이그레이션 완료. 로컬 개발은 `POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/mapo_simulator` fallback (settings.py default).

### 개발 모드 (로컬)

```bash
# 백엔드
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload  # 단일 worker (멀티 worker 시 _pending_pipelines/_async_job_tasks 분리됨)

# 프론트엔드
cd frontend
npm install
npm run dev
```

### 코드 품질 (commit 전 필수)

```bash
# 백엔드
cd backend && ruff check --fix && ruff format

# 프론트엔드
cd frontend && npx prettier --write .
```

### Alembic 마이그레이션

```bash
cd backend
alembic current                          # 현재 head
alembic upgrade head                     # 최신 적용
alembic revision -m "변경 내용"          # 새 revision (수동 작성)
```

### 주요 환경 변수

| 카테고리 | 변수 |
|---------|------|
| LLM | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` |
| DB | `POSTGRES_URL`, `POSTGRES_PASSWORD`, `REDIS_URL` |
| RAG 벡터 | `EMBEDDING_MODE` (settings.py default `openai` — **현재 dead config**, legal RAG 는 `vector_db.py`/`retriever.py` 가 항상 `BAAI/bge-m3` 하드코딩 사용), pgvector 는 `POSTGRES_URL` 재사용 |
| 외부 API | `FTC_API_KEY`, `KAKAO_API_KEY`, `ECOS_API_KEY`, `NTS_API_KEY`, `SEOUL_OPENDATA_KEY`, `SGIS_API_KEY`, `SGIS_SECRET_KEY`, `MOLIT_API_KEY`, `SEMAS_API_KEY`, `LAW_OC` |
| 트렌드 | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` |
| 관측성 | `LANGCHAIN_API_KEY`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_PROJECT` |
| 인증 | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES` |
| RAG 튜닝 | `RRF_VECTOR_WEIGHT=0.4`, `RRF_BM25_WEIGHT=0.6`, `PRIMARY_LAW_BOOST=2.0`, `BM25_SUPPLEMENTARY_PENALTY=0.4` |
| 재정렬 | `RERANK_ENABLED=true`, `RERANK_PROVIDER=openai`, `RERANK_OPENAI_MODEL=gpt-4.1-mini` |
| Rate limit | `RATE_LIMIT_MAX=10` (시간당, `main.py` 직접 환경변수 — settings.py 미편입) |
| Logging | `LOG_LEVEL` (`main.py` 직접 환경변수 — settings.py 미편입) |
| Legacy ChromaDB | `CHROMA_HOST` / `CHROMA_PORT` / `CHROMA_PERSIST_DIR` — settings.py 잔존, 현재 미사용 (pgvector 마이그레이션 후 dead) |
| App 모드 | `APP_MODE=PROD`, `DEBUG=false`, `DEMO_MODE=false`, `LLM_AGENTS_DISABLED=0` |
