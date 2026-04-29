# SPOTTER 코드베이스 종합 리뷰

**작성일:** 2026-04-28
**작성자:** A1 찬영
**브랜치:** `IM3-243-dong-fk-followup`
**범위:** backend/, frontend/, models/, validation/, scripts/, data/, infrastructure 전체

---

## 0. Executive Summary

### 프로젝트 정체성

SPOTTER는 **마포구 프랜차이즈 출점 시뮬레이터**다. 사용자가 입력한 (브랜드 + 후보 동 + 자본금 + 타겟고객)에 대해 8개 LangGraph 에이전트와 5개 ML 모델이 30~40초 안에 의사결정 보고서(매출 예측·BEP·법률 리스크·경쟁 강도·인구 적합성·신생 상권 신호 등)를 생성한다.

### 시스템 규모

| 영역 | 규모 |
|---|---|
| Backend (Python) | `main.py` 1,389줄 + 8 에이전트 + 22 마이그레이션 |
| Frontend (TS/React) | `App.tsx` 4,842줄 + 8 dashboard tabs + 26 TypeScript interface |
| ML 모델 | 5개 (TCN 매출, TCNClassifier 폐업위험, MLP 고객, Autoencoder 신생상권, TCN 인구) + LSTM/GRU baseline |
| 외부 API | 12개 (Anthropic, OpenAI, Gemini, Kakao, FTC, NTS, 서울열린, SGIS, SEMAS, Naver DataLab, KOSIS, LangSmith) |
| DB | PostgreSQL (RDS) + Redis + ChromaDB |
| 테스트 | pytest 24개 + frontend vitest |

### 핵심 아키텍처

```
[ Frontend (Vite :3000) ]
    ↓ POST /api/simulate (vite proxy → :8000)
[ Backend FastAPI (uvicorn :8000) ]
    ↓ app_graph.ainvoke()
[ LangGraph 5-Phase DAG ]
    Phase 0: operational_fit (50ms, Python)
    Phase 1: ranking_phase (district_ranking, ~5-10s)
    Phase 2: llm_analysis_phase (6 LLM 노드 asyncio.gather, ~15-20s)
    Phase 2.5: ml_prediction_phase (TCN + SHAP + BEP, ~5s)
    Phase 3: synthesis (8 결과 통합, ~3s)
    ↓
[ SimulationOutput JSON ]
    ↓
[ TabbedDashboard (8 tabs) ]
```

---

## 1. 프로젝트 디렉토리 구조

```
final project/
├── backend/                    # FastAPI + LangGraph + DB
│   ├── src/
│   │   ├── main.py             # FastAPI 진입점 (1,389줄)
│   │   ├── agents/             # LangGraph 에이전트
│   │   │   ├── graph.py        # 4 phase 노드 (290줄)
│   │   │   └── nodes/          # 9개 에이전트 (synthesis, legal, market_analyst, ...)
│   │   ├── api/                # 보조 REST 라우터
│   │   ├── chains/             # RAG/LangChain
│   │   ├── config/             # 상수, 설정
│   │   ├── database/           # ORM 모델, vector DB
│   │   ├── schemas/            # Pydantic 스키마
│   │   ├── services/           # 비즈니스 로직
│   │   └── simulation/         # ABM (archetypes, policy_executor, world)
│   ├── alembic/versions/       # 22 마이그레이션
│   ├── scripts/                # diagnostics, verify
│   └── tests/                  # backend 단위 테스트
├── frontend/                   # React + Vite SPA
│   ├── src/
│   │   ├── App.tsx             # 7 routes, 4842줄
│   │   ├── main.tsx            # 진입점
│   │   ├── api/client.ts       # axios + interceptors
│   │   ├── pages/              # IntroScene, JoinUs, AccordionGallery, ...
│   │   ├── components/
│   │   │   ├── SimulationResult/dashboard/  # 8 tabs + charts + shared
│   │   │   ├── SimulationHistory/
│   │   │   ├── PDF/, TokenBurnrate/, kakao/, simulation/, ui/
│   │   ├── stores/             # Zustand (simulationStore)
│   │   ├── contexts/           # AuthContext, TransitionContext
│   │   ├── hooks/              # useTokenUsage, useCustomerSegmentPreview
│   │   ├── auth/               # JWT 처리
│   │   ├── constants/          # decisionThresholds (SSOT)
│   │   ├── types/index.ts      # 26+ interface (16KB)
│   │   ├── viewmodels/         # backend → frontend mapping
│   │   └── utils/              # formatters, pdfPropsBuilder
│   ├── vite.config.ts          # port 3000, proxy /api → :8000
│   ├── nginx.conf              # 프로덕션 reverse proxy
│   └── package.json
├── models/                     # ML 모델
│   ├── interface.py            # ModelOutput.generate() 통합 호출
│   ├── tcn_forecast/           # 매출 예측 (메인)
│   ├── lstm_forecast/          # baseline (data_prep 공유)
│   ├── gru_forecast/           # baseline
│   ├── closure_risk/           # 폐업위험도 (LightGBM + TCNClassifier)
│   ├── customer_revenue/       # 타겟 고객 MLP
│   ├── emerging_district/      # 신생 상권 Autoencoder
│   ├── living_pop_forecast/    # 인구 예측 TCN
│   ├── revenue_predictor/      # BEP, 폐업률
│   └── explainability/         # SHAP, build_scenarios
├── validation/                 # 백테스트, ABM vs Grid, imputation
│   ├── accuracy_metrics.py     # mape/mae/rmse/r²
│   ├── experiments/{lstm,gru,tcn}/
│   ├── abm_vs_grid_*.py        # Phase I/Full PSE-3 검증 4종
│   ├── phase_a_seoul_10ind.py
│   ├── phase_b_seoul_63ind.py
│   ├── reverse_engineer_sales_v3.py
│   ├── brand_vacancy_validator.py
│   └── results/                # CSV 산출물
├── scripts/                    # 데이터 수집/변환 스크립트
│   ├── imputed_to_sales_schema.py  # imputed CSV → RDS 스키마 어댑터
│   ├── extract_mapo_migration.py
│   ├── cache_*.py              # 외부 API 캐싱
│   └── collect_*.py            # 외부 API 수집
├── data/
│   ├── pipeline/               # 변환 파이프라인
│   ├── processed/              # CSV 산출물 (sales_imp_*, golmok_*, etc.)
│   ├── geo/, legal/, demo/, seoul_card/
├── docs/                       # 13 카테고리 문서
│   ├── architecture/           # API 계약, ERD, 아키텍처
│   ├── abm-simulation/         # ABM 검증 24개
│   ├── sales-imputation/       # Imputation 알고리즘 32개
│   ├── superpowers/{specs,plans}/
│   ├── retrospective/, issues/, proposals/, team/, database/, presentation/
├── tests/                      # pytest 24개
├── notebooks/                  # 탐색 jupyter
├── docker-compose.yml, .env.example
└── .github/workflows/          # CI/CD
```

---

## 2. Backend 상세 (`backend/src/`)

### 2-1. FastAPI 진입점 (`main.py` 1,389줄)

Module-level 초기화:
- L10-22: Windows cp949 콘솔 인코딩 우회, sys.path 추가
- L31: aioredis import
- L34-56: LangSmith 트레이싱 환경변수 (langchain import 전 필수)
- L45-49: `.env` 로드
- **L107**: `app_graph = compile_workflow()` — **module-level 동기 호출** (LangGraph DAG 컴파일)

Startup events:
- **L139-147**: `@app.on_event("startup")` — `_warmup_customer_revenue()` MLP 모델 워밍업

Middleware:
- **CORS** (L113-119): `localhost:3000` + Docker nginx 허용
- **Rate Limit** (L150-171): IP당 시간당 10회 `/simulate`·`/analyze` 제한 (Redis 고정 윈도우, fail-open)

등록된 router (3개):
- `simulation_history` (L122-124, JWT) — 분석 이력 CRUD
- `vacancy_evaluation` (L126-129, 무인증) — ABM PSE 평가
- `customer_segment` (L131-134, 무인증) — MLP 단발 호출

핵심 endpoint:

| Endpoint | Line | 역할 | 인증 |
|---|---|---|---|
| `POST /simulate` | 1116 | 전체 LangGraph + ABM | 선택 |
| `POST /analyze` | 662 | 경량 LLM (rate-limited) | 선택 |
| `POST /analyze/quick` | 705 | district_ranking only (~1s) | 선택 |
| `POST /simulate-abm` | 1207 | ABM 행동 시뮬 단독 | 선택 |
| `POST /biz/lookup` | 759 | 사업자번호 → 프랜차이즈 매핑 | 무 |
| `POST /auth/{signup,login,...}` | — | JWT 발급, 팀 관리 | 무/JWT |
| `GET /population/live` | 1070 | 실시간 유동인구 | 무 |

### 2-2. LangGraph 워크플로우 (`agents/graph.py` 290줄)

5-Phase DAG 구조:

```
operational_fit_node     ← Phase 0 (50ms, Python only)
        ↓
ranking_phase_node       ← Phase 1 (~5-10s, district_ranking 단독)
        ↓
llm_analysis_phase_node  ← Phase 2 (~15-20s, 6 LLM asyncio.gather)
    ├─ market_analyst_node
    ├─ population_analyst_node
    ├─ legal_node
    ├─ demographic_depth_node
    ├─ trend_forecaster_node
    └─ competitor_intel_node
        ↓
ml_prediction_phase_node ← Phase 2.5 (~5s, ModelOutput.generate + SHAP)
        ↓
synthesis_node           ← Phase 3 (~3s, 8개 결과 통합 + LLM 최종 리포트)
        ↓
END
```

**노드별 책임:**

| 노드 | 책임 | 주요 출력 필드 |
|---|---|---|
| `operational_fit` | 16동 교통·집객 점수 (Hansen 1959 + E2SFCA 2009) | `analysis_metrics.operational_fit_score` |
| `ranking_phase` | 16동 ranking + winner_district 확정 | `district_rankings`, `top_3_candidates`, `winner_district` |
| `market_analyst` | 경쟁사·매출·임대료 (DB + Gemini) | `market_data` |
| `population_analyst` | 유동인구 추이 | `analysis_results.population_summary` |
| `legal` | RAG 14개 법률 리스크 | `legal_risks`, `overall_legal_risk` |
| `demographic_depth` | 인구통계 심화 + customer_revenue 호출 | `demographic_report`, `customer_segment` |
| `trend_forecaster` | Naver DataLab SNS 트렌드 | `trend_forecast` |
| `competitor_intel` | FTC + Kakao 경쟁 분석 + 차별화 | `competitor_intel` |
| `ml_prediction_phase` | TCN 매출 예측 + BEP + 폐업위험도 + SHAP | `quarterly_projection`, `bep`, `closure_risk`, `shap_result`, `customer_segment` |
| `synthesis` | 8개 결과 통합 + LLM 최종 리포트 | `final_report`, `ai_recommendation`, `analysis_report`, `agent_attributions` |

**AgentState** (`schemas/state.py:20-72`):
- Input: business_type, brand_name, target_district(s), monthly_rent_budget, store_area, population_weight, initial_capital, target_age_groups, target_gender, target_time_slots, target_day_type
- Data slots: market_data, legal_info, scouting_results, winner_district, tcn_sim_result, shap_result, operational_fit_results, competitor_intel_result
- Output: analysis_results, analysis_metrics, overall_legal_risk, agent_attributions

**Token 모니터링** (graph.py:19-154): 파이프라인 예산 16,000 토큰, 초과 시 경고.

### 2-3. Schemas (`backend/src/schemas/`)

| 파일 | 역할 |
|---|---|
| `simulation_input.py` | `SimulationInput` Pydantic — 입력 |
| `simulation_output.py` | `SimulationOutput` Pydantic — 응답 (30+ 필드) |
| `state.py` | `AgentState` TypedDict (LangGraph state) |
| `demographic.py` | DemographicReport |
| `competition_models.py` | CompetitorIntel |
| `district_data.py` | DistrictRanking |
| `report_models.py`, `simulation_history.py`, `structured_output.py` | 보조 |

### 2-4. Services (`backend/src/services/`)

| Service | 역할 |
|---|---|
| `operational_fit_scorer.py` | 16동 교통·집객 점수 (R²=0.55) |
| `dong_resolver.py` | 행정동명 ↔ 동코드 매핑 (단일 소스) |
| `commercial_intelligence.py` | Kakao API 경쟁업체 + FTC 프랜차이즈 판정 |
| `population_api.py` | 서울 열린데이터 실시간 유동인구 |
| `auth.py` | NTS 사업자 검증 + JWT + 팀 관리 |
| `biz_mapper.py` | 사업자번호 → 프랜차이즈 |
| `ftc_franchise.py` | FTC 가맹점주 정보 |
| `law_api.py` | ChromaDB RAG 검색 |
| `simulation_history_service.py` | 분석 이력 CRUD |
| `vacancy_evaluation_service.py` | ABM PSE 평가 |

### 2-5. Database (`backend/src/database/`)

ORM 모델 (`models.py` 1,616줄):
- 인구: `LivingPopulation`, `SgisPopulation`, `SgisHousehold`
- 상업: `StoreQuarterly`, `KakaoStore`, `GolmokStore`
- 임대: `GolmokRent`, `JeonseDongMaster`
- 인프라: `DongSubwayAccess`, `BusBoardingDaily`
- 시설: `SeoulAdstrdFclty`, `NaverVacancy`
- 법률: `LegalDocument`, `FtcBrandFranchise`
- 사용자: `Users`, `ManagerUsers`, `InviteCodes`, `SimulationHistory`

Vector DB: ChromaDB — `legal_documents` 임베딩 (RAG 검색)

마이그레이션 (`alembic/versions/`): 22개. 최근 추가:
- `a8b2c4d6e8f0` (04-27): `dong_centroid` 신설 — 16동 좌표 영구 저장
- `d1a2b3c4e5f6` (04-25): `seoul_dong_master` 신설 (425동, ML 학습용)
- `e2b3c4d5f6a7` (04-25): seoul_district_sales/stores FK 추가
- `b8c4d2e1f395`, `c9d4e5f1a8b3` (04-25): FK Group B1/B2

### 2-6. ABM Simulation (`backend/src/simulation/`)

| 모듈 | 역할 |
|---|---|
| `world.py` | 마포 16동 가상 세계 (좌표·상점·주민 초기화) |
| `world_loader.py` | DB → 가상 세계 로더 |
| `archetypes.py` | 소비자 페르소나 (가격민감도·브랜드충성도 등) |
| `agents.py` | 소비자 에이전트 행동 로직 |
| `policy_executor.py` | 정책 시나리오 적용 (날씨·가격·요일강제) |
| `profile_builder.py` | 신규 매장 프로필 (타겟고객 매칭) |
| `runner.py` | 메인 시뮬 루프 (n_agents × days) |

실행 흐름: `/simulate-abm` → Scenario 구성 → GameMaster(ModelConfig·PopulationMix·TierDistribution) 초기화 → run_simulation → 매출·폐업률·경쟁 영향 결과.

ABM 결과 캐시: Redis SHA256 키 (24h).

### 2-7. 데이터 흐름 — `POST /simulate` 콜체인

```
1. FastAPI handler (main.py:1116)
   ↓
2. _run_pipeline(input_data) (main.py:291)
   - 초기 state 구성 (HumanMessage 주입)
   - app_graph.ainvoke(initial_state)
   ↓
3. LangGraph 실행
   a) operational_fit → 16동 교통·집객 점수 (50ms)
   b) ranking_phase → winner_district 확정 (5-10s, op_fit 15% 가중치)
   c) llm_analysis_phase → 6 LLM 병렬 (asyncio.gather, 15-20s)
   d) ml_prediction_phase → ModelOutput.generate + SHAP (5s)
   e) synthesis → 8개 결과 통합 + LLM 최종 리포트 (3s)
   ↓
4. map_state_to_simulation_output() (main.py:348)
   - state → SimulationOutput 스키마 변환
5. _collect_all_competitor_locations() (main.py:241)
   - winner + top3 동 경쟁업체 좌표 수집
6. HTTP 200 JSON 응답

총: ~30-40초 (캐시 없음) / ~3-5초 (캐시 히트)
```

캐시 정책:
- `market:{district}:{biz_type}` (24h)
- `v7:synthesis:{brand}:{winner}:{districts}:{biz}:{rent}:{area}:{pop_w}` (24h)
- `abm_sim:{SHA256(params)}` (24h)

---

## 3. Frontend 상세 (`frontend/src/`)

### 3-1. 진입점 + 빌드

`main.tsx`: BrowserRouter → `<App />` (StrictMode)

`vite.config.ts`:
- L18: port 3000
- L19-24: proxy `/api → http://localhost:8000` (rewrite로 prefix 제거)
- L32-37: manualChunks 분리 (react-vendor, chart-vendor, motion-vendor, icons-vendor)

`package.json`:
- React 18.3.0, React Router 6.28.0
- Zustand 5.0.12, Recharts 2.15.4, Framer Motion 12.38.0
- axios 1.7.0, html2canvas, jspdf, xlsx (PDF/Excel export)

### 3-2. 라우팅 (App.tsx 4,842줄, L4497-4583)

| 경로 | 컴포넌트 | 보호 |
|---|---|---|
| `/` | IntroScene (lazy) | — |
| `/about` | AboutPage (lazy) | — |
| `/joinus` | JoinUsPage | — |
| `/explore` | AccordionGallery (lazy) | — |
| `/contact` | ContactPage (lazy) | — |
| `/simulator` | SimulatorDashboard | ProtectedRoute |
| `/hq` | HQCommandCenter | ProtectedRoute (master) |
| `/hq/managers/:id` | ManagerDetail | ProtectedRoute |
| `/dashboard/history/:id` | SimulationHistoryDetail | ProtectedRoute |
| `/dashboard/compare` | SimulationCompare | ProtectedRoute |
| `/login` | LoginPage | — |

### 3-3. SimulatorDashboard 흐름

상태 (L800-850):
- `reportState`: 'idle' | 'loading' | 'result'
- `simResult` (camelCase 뷰모델), `rawSimResult` (snake_case 원본)
- `selectedDongs[]`, `businessType`, `targetAgeGroups`, `targetGender`, `targetTimeSlots`, `targetDayType`
- `chartView`, `tableView`, `dashboardMode`, `activeDrawer`

흐름:
1. 입력 폼 좌측 패널 (마포 4동 선택 제한, 업종 드롭다운, 자본금/임차료/타겟고객)
2. `handleRunSim()` → Zustand `simulationStore.startSimulation(params)`
3. AbortController + fake progress (90%까지 100초 동안 증가)
4. `runSimulation(params, signal)` (api/client.ts:119-137) → `POST /api/simulate`
5. envelope 처리: `{status:'success', data:{...}}` 또는 raw `SimulationOutput`
6. `setRawSimResult` + viewmodel 매핑
7. `<TabbedDashboard simResult={rawSimResult} />` 8개 탭 렌더

### 3-4. 8 Dashboard Tabs

| Tab | 역할 | 주요 사용 필드 |
|---|---|---|
| **SUMMARY** | 의사결정 3카드 | `final_report.profit_simulation`, `competitor_intel`, `quarterly_projection`, `overall_legal_risk` |
| **MARKET** | 지도 + 경쟁 강도 | `market_report`, `district_rankings`, `competitor_intel.cannibalization` |
| **ABM** | 공실 시뮬 | `vacancy_spots`, `/api/simulate-abm` |
| **DEMOGRAPHIC** | 인구·고객 | `demographic_report`, `customer_segment`, `living_pop_forecast` |
| **FINANCIAL** | 재무 | `final_report.profit_simulation`, `closure_rate`, `closure_risk` |
| **FORECAST** | 예측 + SHAP | `quarterly_projection`, `scenarios`, `shap_result`, `trend_forecast` |
| **LEGAL** | 법률 리스크 | `legal_risks`, `overall_legal_risk` |
| **INSIGHT** | 8 에이전트 근거 | `agent_attributions` |

### 3-5. API 클라이언트 (`api/client.ts`)

axios 인스턴스 (L47-51): `baseURL: '/api'`, `timeout: 120000` (2분)

요청 인터셉터 (L57-77):
- `X-Tenant-ID` 헤더 (multi-tenant 준비)
- JWT Bearer 자동 주입 (`localStorage.spotter_auth`)

응답 인터셉터 (L88-110):
- 401 → localStorage wipe + `/login` 강제 이동

주요 함수:
- `runSimulation` (POST /simulate, 10분 timeout)
- `analyzeLocation` (POST /analyze)
- `getReport`, `getStatus`
- `getLivePopulation` (GET /population/live)
- `fetchCustomerSegment` (POST /customer-segment, ~100ms)
- `saveSimulationHistory`, `listSimulationHistory` (JWT)

### 3-6. 타입 시스템 (`types/index.ts`, 16KB)

핵심 interface (26+):

```typescript
SimulationInput {
  business_type, brand_name, target_district,
  existing_stores: ExistingStore[],
  monthly_rent, scenarios,
  target_age_groups?, target_gender?, target_time_slots?, target_day_type?
}

SimulationOutput {
  request_id, target_district, winner_district, top_3_candidates,
  quarterly_projection: QuarterlyProjection[],     // TCN 4분기
  comparison: DistrictComparison[],
  legal_risks: LegalRisk[],
  market_report?: { 7개 정규화 지표 },
  district_rankings?: DistrictRanking[],
  shap_result?: ShapResult,
  closure_risk?: ClosureRisk,
  competitor_intel?: CompetitorIntel,
  trend_forecast?: TrendForecast,
  demographic_report?: DemographicReport,
  customer_segment?: CustomerSegment,
  living_pop_forecast?: LivingPopForecast,
  emerging_signal?: EmergingSignal,
  final_report?: { profit_simulation, ... },
  agent_attributions?: AgentAttribution[]
}
```

### 3-7. 상태 관리

**Zustand store** (`stores/simulationStore.ts`):
```typescript
SimulationState {
  status: 'idle' | 'running' | 'done' | 'error'
  progress: number, stage: string
  result: SimulationOutput | null
  savedHistoryId: number | null   // SPTR-000142 형식
  startSimulation(params), cancelSimulation(), reset()
}
```
Fake progress (L105-110): 90%까지 100초 동안 증가.

**Auth Context** (`auth/AuthContext.tsx`):
- localStorage 키: `spotter_auth = {user, brand, token}`
- Zombie 방지 (L64-66): user 있는데 token 없으면 wipe

**TransitionContext**: 암전 트랜지션 (페이지 이동 효과)

### 3-8. 디자인 시스템

- Tailwind + CSS Variables (`index.css`), darkMode: "class"
- 차트: Recharts 2.15.4
- 애니메이션: Framer Motion 12.38.0
- 아이콘: Lucide Icons 1.7.0
- PDF/Excel: jsPDF + html2canvas + xlsx (dynamic import)

### 3-9. 빌드/배포

```bash
npm run dev              # vite dev (port 3000)
npm run build            # tsc + vite build → dist/
npm run build:analyze    # stats.html 생성
```

---

## 4. ML 모델 상세 (`models/`)

### 4-1. ModelOutput 통합 (`models/interface.py`)

`ModelOutput.generate()` (L373-577) — 5 파트 직렬 호출:

```python
def generate(
    dong_code, industry_code, industry_name,
    cost_config: dict | None = None,
    model: str = "lstm",
    segment_profile: dict | None = None,
) -> dict:
    # 1. 매출 예측 (L424-439): _run_lstm/tcn/gru_forecast
    # 2. 폐업률 (L441-450): _run_closure_rate
    # 3. 폐업위험도 (L452-464): closure_risk_predict (LightGBM + TCN)
    # 4. BEP (L466-491): _run_bep
    # 5. 타겟 고객 (L493-509): _run_customer_revenue (segment_profile 있을 때만)
```

각 단계 예외 시 `_mock_*()` 폴백 (L415-491). `ExcludedComboError`만 재전파 → HTTP 400.

### 4-2. TCN 매출 예측 (`models/tcn_forecast/`)

**TCNForecaster** (model.py:197-407):
- Input Projection: Linear(input_size → n_channels=128)
- TemporalBlock × 2: dilation=[1,2], kernel_size=2
  - Receptive field = 1 + (2-1)×(1+2) = **4** (= window_size)
  - CausalConv1d (왼쪽 패딩, 미래 누수 방지)
  - LayerNorm + ReLU + Dropout 0.2
  - Residual connection
- FC Head: Linear(128→64) → ReLU → Dropout → Linear(1)

**Pretrain → Finetune 2단계**:
- Pretrain (서울, dong_prefix=None): batch=64, epochs=100, lr=1e-3 → `pretrained_tcn_seed2026.pt`
- Finetune (마포, dong_prefix="11440"): batch=32, 2단계
  1. **Freeze**: TCN 고정, FC만 (10 epoch, lr=5e-4)
  2. **Unfreeze**: 전체 (50 epoch, lr=1e-4)
- `freeze_tcn()` / `unfreeze_tcn()` (model.py:378-399)

**Sample Weight** (data_prep.py:638): 코로나 시기(2020~2021) row에 weight=0.5, 다른 시기 1.0. 학습 손실 = `(w * (pred - y)²).mean()`.

**가중치 변형** (사용자 본 PR commit 기준):
- `finetuned_mapo_tcn.pt`, `_run2`, `_run3`, `_seed47`, `_seed415`, `_seed2026`, `_34f`
- 사용자 작업: `_imp_a` (마포 imputed finetune), `_imp_b`/`_imp_b2` (서울+마포 imputed), `_orig` (RDS 실측 cutoff=20241)

**추론** (predict.py:66-228): 자기회귀 sliding window, 4분기 예측 합산 = 연 매출. uncertainty_factor = min(0.03×i, 0.25).

### 4-3. 폐업위험도 (`models/closure_risk/`)

**TCNClassifier** (model.py:28-78):
- TCNForecaster conv 블록 재사용 (전이학습)
- FC head 교체: 회귀 → 이진 분류 (logit)
- `load_pretrained_tcn()` (L95-122): pretrained_tcn.pt에서 fc 제외 + shape 불일치 제외 로드

**앙상블** (predict.py:47-87):
- LightGBM (`closure_risk_lgbm.pkl`) + TCN (`closure_risk_tcn.pt`)
- 가중치: `ensemble_weights.pkl` (기본 50:50)
- score = 0.5×lgbm_prob + 0.5×tcn_sigmoid
- 등급: `[(0.65, "danger"), (0.40, "caution"), (0.00, "safe")]`

**SHAP** (predict.py:176-195): LightGBM TreeExplainer → 상위 3 피처 + 한국어 매핑

### 4-4. 타겟 고객 (`models/customer_revenue/`)

**MLP**: 입력 SegmentProfile + monthly_sales + quarter_num → 출력 segment_ratio + segment_sales

**SegmentProfile dataclass** (predict.py:124-149):
```python
age_groups: list[str]   # ["20대", "30대"]
gender: str             # "male" | "female" | "all"
time_slots: list[str]   # ["time_11_14", "time_14_17"]
day_type: str           # "weekday" | "weekend" | "all"
```

**living_population SQL** (predict.py:171-279):
- `_AGE_COL_SUFFIXES`: `"60대이상"` → `("60_64", "65_69", "70_74", "70_plus")` (⚠️ 공백 없음)
- `_TIME_ZONE_MAP`: `"time_11_14"` → `(12, 13, 14)`
- 결과: `seg_pop / total_pop` ratio (L0~1.0 clamp)

### 4-5. 신생 상권 (`models/emerging_district/`)

LSTM Autoencoder:
- 인코더(시계열 압축) + 디코더(복원) → `reconstruction_error → anomaly_score`
- 신호 분류 (predict.py:81-100):
  - **Emerging**: 매출 ↑ AND 점포 수 ↑↓ ≥0
  - **Declining**: 매출 ↓ OR 점포 ↓
  - **Normal**: 그 외

### 4-6. 인구 예측 (`models/living_pop_forecast/`)

TCN (window_size=8, n_channels=64, dilations=[1,2,4]) — 분기별 24시간대 피크 시간/인구. 모듈 레벨 캐시 (predict.py:54-70).

### 4-7. SHAP (`models/explainability/`)

- `explain_tcn_prediction()`: GradientExplainer/DeepExplainer → 피처별 기여도 + 한국어 매핑
- `build_scenarios()`: TCN 매출 → 낙관/기본/비관 3 시나리오 (계절성 보존)

### 4-8. BEP (`models/revenue_predictor/`)

`BEPCalculator` (bep.py:49-155): 분기 단위 BEP
```
bep_quarters = ceil(total_initial_investment / quarterly_profit)
quarterly_profit = quarterly_revenue - fixed_cost - variable_cost
```

`predict.py`: 폐업률 (실측 4분기 평균)

### 4-9. 공통 데이터 준비 (`models/lstm_forecast/data_prep.py`)

**ALL_FEATURES 34개** (L91):
```python
SALES_FEATURES (12): monthly_sales, monthly_count, weekday/weekend/gender/age_*_sales
STORE_FEATURES (5):  store_count, franchise_count, open/close_count, closure_rate
POP_FEATURES (4):    total_pop, avg_age, total_households, resident_pop
RENT_FEATURES (2):   rent_1f, vacancy_rate
EXTRA_FEATURES (6):  cpi_index, quarter_num, trend_score, holiday_count, bus_flpop, adstrd_flpop
GOLMOK_FEATURES (5): store_franchise, store_normal, floating_pop, pop_per_store_gm, normal_ratio
```

**Hot Deck 보간** (L287-340): NearestNeighbors(k=5) 유사 동에서 결측 채움. ⚠️ `qdf[col] == 0` 도 결측 처리 (사용자가 발견한 함정).

**`prepare_dataloaders()`**: MinMaxScaler → window=4 슬라이딩 → DataLoader. 사용자 추가 인자: `sales_csv_override`, `train_cutoff_quarter`.

### 4-10. 전이학습 그래프

```
pretrained_tcn.pt (서울 전체)
    ↓ load_pretrained_tcn()
finetuned_mapo_tcn_*.pt (마포)
    ├→ TCNClassifier → closure_risk_tcn.pt
    └→ TCNForecaster → living_pop_tcn.pt (독립 학습)
```

### 4-11. 가중치 산출물 위치/명명

| 모델 | 위치 | 파일명 |
|---|---|---|
| TCN 매출 (Pretrain) | tcn_forecast/weights/ | `pretrained_tcn_seed2026.pt` |
| TCN 매출 (Finetune) | 동일 | `finetuned_mapo_tcn_34f.pt` (현재 활성), `_imp_a/b/b2/orig` (실험 변형) |
| TCNClassifier | closure_risk/weights/ | `closure_risk_tcn.pt` |
| LightGBM | 동일 | `closure_risk_lgbm.pkl` |
| MLP | customer_revenue/weights/ | `customer_mlp.pt` |
| LSTM AE | emerging_district/weights/ | `autoencoder.pt` |
| TCN 인구 | living_pop_forecast/weights/ | `living_pop_tcn.pt` |
| Scaler | 각 모델 weights/ | `*_scaler.pkl`, `*_meta.pkl` |

---

## 5. Validation 상세 (`validation/`)

### 5-1. 정확도 메트릭 (`accuracy_metrics.py`)

- `mape()` (L10-17): 0 제외 평균 절대 비율 오차
- `mae()` (L20-24), `rmse()` (L32-36)
- `r_squared()` (L44-52): R²
- `calculate_directional_accuracy()` (L55-65): 상승/하락 방향 정확도
- `generate_accuracy_report()` (L68-111): 종합 (overall + 라벨별)

### 5-2. 백테스트 스크립트

| 모델 | 파일 | 결과 CSV |
|---|---|---|
| LSTM | `experiments/lstm/backtest_lstm.py` | `lstm_backtest_results*.csv` (6 seed) |
| GRU | `experiments/gru/backtest_gru.py` | `gru_backtest_results*.csv` (6 seed) |
| TCN | `experiments/tcn/backtest_tcn.py` | `tcn_backtest_results*.csv` (사용자 작업으로 imp_a/imp_b/imp_b2/orig 추가) |

각 CSV 컬럼: `(test_year, dong_code, industry_code, actual_annual_sales, predicted_annual_sales, abs_error, mape_pct)`

### 5-3. ABM vs Grid 검증 4종 (사용자 본 PR)

- `abm_vs_grid.py` — 기본 검증 (Pearson r, Spearman ρ, MAPE, 피크 시간 일치, Kendall τ)
- `abm_vs_grid_matrix.py` — 16동×16동 상호작용
- `abm_vs_grid_decomposed.py` — 요소별 분해 (store_count, 요일, 시간대)
- `abm_vs_grid_pse3.py` — Phase I/Full PSE-3 정책 효과

### 5-4. Sales-Imputation v3 (`reverse_engineer_sales_v3.py`)

설계:
- Target: `log(monthly_sales)` → `log(sales_per_store)` (L60)
- Dong one-hot 제거 → 동 레벨 외부 통계 (L65-95)
- Features: kosis_index, franchise_ratio, open_ratio, closure_rate, seasonality, 업종 dummy
- 검증: Random 5-fold + MNAR-Mimic 5-fold (주 지표) + 셀 크기 분위 별 WAPE
- 출력: `imputed_sales_v3.csv`, `imputed_seoul_sales_63ind.csv` (66MB), `imputed_mapo_full_v3.csv` (11MB)

### 5-5. brand_vacancy_validator

5-track 브랜드 검증 (이디야, 메가커피 등):
- track별 mean_ratio, pass 여부, production_ready 종합 판정

### 5-6. 결과 CSV 명명 규칙

| 패턴 | 예 |
|---|---|
| `{model}_backtest_results{_suffix}.csv` | `lstm_backtest_results_seed47.csv` |
| `imputed_{region}_{ver}.csv` | `imputed_mapo_full_v3.csv` |
| `imputed_seoul_sales_{n}ind{_v}.csv` | `imputed_seoul_sales_63ind_v4.csv` |
| `phase_{scope}_{test}.{txt,json}` | `phase_full_pse3_summary.json` |

---

## 6. Data Pipeline (`scripts/`, `data/`)

### 6-1. 외부 데이터 수집

| 출처 | 스크립트 | 산출물 |
|---|---|---|
| Kakao Map | `collect_kakao_menus.py` | 메뉴 정보 |
| Naver Trend | `collect_naver_trend_rebuild.py` | `district_trend_timeseries.csv` |
| 서울 열린데이터 | `cache_adstrd_flpop.py`, `cache_bus_flpop.py` | `adstrd_flpop_quarterly.csv` (286KB) |
| KOSIS | `probe_kosis_pairing.py` | imputation anchor series |
| 공실 | `cache_realtime_hotspots.py` | 실시간 핫스팟 캐시 |

### 6-2. 어댑터 (`scripts/imputed_to_sales_schema.py`, 사용자 작업)

- `adapt_mapo_imputed()` (L38-67): `<col>_final` → `<col>` 매핑, `_pred/_imputed/_adjusted/_recovered/_final` 모두 drop
- `adapt_seoul_imputed()` (L70-118): `imputed_sales` → `monthly_sales`, RDS join + 결측 1e-9 fillna (Hot Deck 폭증 우회)

### 6-3. data/processed/ 산출물

| 카테고리 | 파일 | 크기 |
|---|---|---|
| 매출 | `district_sales.csv` | 1.48MB |
| 가게 | `district_stores.csv` | 248KB |
| 유동인구 | `adstrd_flpop_quarterly.csv` | 286KB |
| 골목상권 | `golmok_*.csv` (6개) | 12.5MB |
| 지표 | `golmok_index_seoul.csv` | 4MB |
| Imputed (gitignored) | `sales_imp_seoul.csv` (218MB), `seoul_migration_mapo_202601.csv` (94MB) | — |

---

## 7. Database (`backend/alembic/`, ORM)

22개 마이그레이션 (`alembic/versions/`).

마스터 테이블:
- `dong_mapping` (마포 16동, 운영용) — 동코드↔동명 양방향
- `seoul_dong_master` (서울 425동, ML/학습용) — 자식 테이블 UNION + 정규화
- `dong_centroid` (16동 좌표) — store_info 평균, 향후 Kakao Geocoding으로 갱신 가능

Vector DB (ChromaDB):
- `legal_documents` 임베딩 (RAG 검색)
- `chunks.json` (data/legal/processed/) — 법률 텍스트 청크

---

## 8. Infrastructure (Docker, Nginx)

### 8-1. docker-compose.yml

| 서비스 | 이미지 | 포트 | 의존 |
|---|---|---|---|
| frontend | Node 20 → Nginx | 80/443 | backend |
| backend | Python 3.12 | 8000 | redis |
| postgres | (주석) | 5432 | (RDS 외부 이관) |
| redis | redis:7-alpine | 6379 | — |

backend 명령:
```bash
alembic upgrade head && python -m src.database.seed && uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### 8-2. Dockerfile (2단계 빌드)

- Backend: builder (gcc/libpq/gdal + venv 생성) → runtime (libpq5/gdal-bin + venv 복사)
- Frontend: build (vite) → production (nginx + dist 복사)

### 8-3. nginx.conf

- `/` → React SPA (try_files SPA fallback)
- `/api/` → backend:8000 (300초 timeout, WebSocket 지원)

### 8-4. CI/CD (`.github/workflows/`)

- `auto-pr-title.yml`: PR 제목 자동화
- `deploy.yml`: push → 테스트 + 빌드 + 배포

---

## 9. 의존성 관리

### 9-1. Backend (`backend/requirements.txt`)

| 카테고리 | 패키지 |
|---|---|
| 프레임워크 | fastapi, uvicorn, pydantic |
| ORM/DB | sqlalchemy, asyncpg, psycopg/psycopg2, alembic |
| AI/Agent | langchain, langgraph, anthropic, openai |
| 딥러닝 | torch (CPU 전용), scikit-learn, shap |
| 데이터 | pandas, numpy, geopandas |
| 캐싱 | redis |

### 9-2. Frontend (`frontend/package.json`)

| 카테고리 | 패키지 |
|---|---|
| UI | react, react-dom, lucide-react |
| 라우팅 | react-router-dom |
| 차트 | recharts |
| 상태 | zustand |
| 빌드 | vite, typescript |
| 테스트 | vitest |
| Export | html2canvas, jspdf, xlsx |

---

## 10. 외부 통합 (12개 API)

| 외부 | 용도 | env |
|---|---|---|
| Anthropic | Claude (Opus/Haiku) | ANTHROPIC_API_KEY |
| OpenAI | 임베딩, 폴백 | OPENAI_API_KEY |
| Google Gemini | 폴백 LLM | GOOGLE_API_KEY |
| Kakao Map | 경쟁업체 좌표 | (URL only) |
| FTC | 가맹점주 정보 | FTC_API_KEY |
| NTS | 사업자 검증 | NTS_API_KEY |
| 서울 열린 | 생활인구·매출 | SEOUL_OPENDATA_KEY |
| SGIS | 인구 통계 | SGIS_API_KEY + SECRET |
| SEMAS | 점포 정보 | SEMAS_API_KEY |
| Naver DataLab | SNS 트렌드 | NAVER_CLIENT_ID + SECRET |
| KOSIS | 통계청 anchor | KOSIS_API_KEY |
| LangSmith | LLM 트레이싱 | LANGCHAIN_API_KEY |

---

## 11. 테스트 (`tests/`, 24개 + frontend)

| 그룹 | 파일 |
|---|---|
| API | `test_api_response.py`, `test_e2e_api.py` |
| 검증 | `test_audit_v4.py`, `test_brand_vacancy_validator.py`, `test_compare_imputed.py` |
| 모델 | `test_imputed_v4.py`, `test_competition.py` |
| 파이프라인 | `test_e2e_pipeline.py`, `test_full_workflow.py`, `test_data_prep_overrides.py` |
| DB/Schema | `test_database.py`, `test_schemas.py`, `test_imputed_to_sales_schema.py` |
| RAG/노드 | `test_rag_pipeline.py`, `test_node_direct.py` |
| 기타 | `test_kakao_crawl.py`, `test_legal_scenarios.py`, ... |

`backend/pyproject.toml`: `asyncio_mode = "auto"`.
사용자 본 PR 추가: `test_compare_imputed.py`, `test_data_prep_overrides.py`, `test_imputed_to_sales_schema.py` (8 tests).

---

## 12. docs/ 13 카테고리

| 카테고리 | 파일 수 | 책임 |
|---|---|---|
| sales-imputation | 32 | Imputation 알고리즘, Phase A/B, v3/v4 재설계 |
| abm-simulation | 24 | ABM 검증, 모델 비교, 정책 생성기 |
| superpowers/{specs,plans} | 30+ | 설계·구현 plan |
| architecture | 11 | API 계약, 서비스 아키텍처 |
| team | 9 | WBS, 일일 TODO |
| database | 7 | DB 스키마, ERD, 데이터 사전 |
| retrospective | 4 | 일/주 회고 |
| issues | 2 | 본인 추가 (SummaryTab fail) |
| proposals | 3 | op_fit 평가·통합 가이드 (본인 추가 2건) |

---

## 13. 핵심 데이터 흐름 — End-to-End

```
[사용자 입력]
  ↓ 프론트 폼 (마포 16동 中 4동 선택, 업종, 자본금, 타겟고객 4필드)
[Frontend SimulationInput]
  ↓ axios POST /api/simulate (vite proxy → :8000)
[Backend FastAPI handler] (main.py:1116)
  ↓ rate_limit_middleware
  ↓ JWT validation (선택)
  ↓ _run_pipeline(input_data) (main.py:291)
[LangGraph DAG]
  ↓
  Phase 0: operational_fit_node
    → 16동 교통(0.10)·버스(0.40)·집객(0.50) 점수 (0~100)
    → state["operational_fit_results"]
  ↓
  Phase 1: ranking_phase_node
    → district_ranking_node (16동 ranking + winner 확정)
    → op_fit 15% 가중치 통합
    → state["winner_district"], state["top_3_candidates"]
  ↓
  Phase 2: llm_analysis_phase_node (asyncio.gather 병렬)
    ├ market_analyst_node     (DB + Gemini, Redis 24h 캐시)
    ├ population_analyst_node (DB + LLM)
    ├ legal_node              (ChromaDB RAG + LLM, 14 risks)
    ├ demographic_depth_node  (LivingPopulation 분석)
    ├ trend_forecaster_node   (Naver DataLab + LLM)
    └ competitor_intel_node   (FTC + Kakao + LLM, 차별화)
    → state["analysis_results"], state["legal_risks"], state["competitor_intel_result"], ...
  ↓
  Phase 2.5: ml_prediction_phase_node
    → ModelOutput.generate(dong_code, industry, biz, model="tcn", cost_config, segment_profile)
       ├ TCN 매출 예측 (pretrain → finetune partial load → 자기회귀 4분기)
       ├ closure_rate (실측 4분기 평균)
       ├ closure_risk (LightGBM + TCNClassifier 앙상블 50:50)
       ├ BEP (BEPCalculator 분기 단위)
       └ customer_revenue (segment_profile 있을 때 MLP + living_population SQL)
    → explain_tcn_prediction (SHAP) → top-5 피처 기여도
    → state["sim_result"], state["shap_result"]
  ↓
  Phase 3: synthesis_node
    → 8개 결과 통합 + LLM 최종 리포트
    → state["final_report"], state["ai_recommendation"], state["analysis_report"], state["agent_attributions"]
  ↓
[map_state_to_simulation_output] (main.py:348)
  → state → SimulationOutput Pydantic
[_collect_all_competitor_locations] (main.py:241)
  → 지도 멀티핀
[HTTP 200 JSON 응답]
  ↓
[Frontend SimulationOutput TS interface]
  ↓ Zustand setRawSimResult
[TabbedDashboard 8 tabs]
  ├ SummaryTab     (final_report.profit_simulation, competitor_intel, quarterly_projection)
  ├ MarketTab      (market_report, district_rankings, vacancy_spots)
  ├ AbmTab         (vacancy_spots → POST /api/simulate-abm 별도 호출)
  ├ DemographicTab (demographic_report, customer_segment, living_pop_forecast)
  ├ FinancialTab   (final_report.profit_simulation, closure_rate, closure_risk)
  ├ ForecastTab    (quarterly_projection, scenarios, shap_result, trend_forecast)
  ├ LegalTab       (legal_risks, overall_legal_risk)
  └ InsightTab     (agent_attributions, 8 에이전트 신뢰도 + reasoning)
```

총 소요 시간: **~30~40초** (캐시 없음) / **~3~5초** (캐시 히트).

---

## 14. 핵심 결정·약한 고리

### 14-1. 알려진 약점

| # | 항목 | 영향 | 위치 |
|---|---|---|---|
| 1 | `final_report.profit_simulation` 키 응답에 없음 | SummaryTab 카드 3 빈 상태 | synthesis 또는 main.py 응답 빌더 |
| 2 | `quarterly_projection.length === 4` 하드코딩 | simulation_quarters=16 환경에서 카드 2 fail | `SummaryTab.tsx:83` |
| 3 | `competitor_intel` 브랜드 매핑 dict 미커버 | 새 브랜드 입력 시 fallback narrative만 | `competitor_intel.py:78` |
| 4 | `graph.py:200` `segment_profile` 인자 누락 | customer_segment null | git blame: B2 (수지니, commit 59955d9) |
| 5 | `closure_risk` 모델 추론 fail | risk_score null, top_signals 빈 배열 | `closure_risk/predict.py` |
| 6 | `scenarios`, `trend_forecast`, `financial_report` 빈 객체 | 3개 탭 빈 상태 | 해당 노드들 |
| 7 | `_AGE_COL_SUFFIXES` 키 `"60대이상"` 공백 없음 | 입력 `"60대 이상"` 시 silent fallback | `customer_revenue/predict.py:88-95` |
| 8 | data_prep `_hot_deck`이 `qdf[col] == 0` 도 결측 처리 | sub-피처 0값 이 결측 폭증 트리거 | `data_prep.py` (사용자 발견) |
| 9 | 마포 imputed CSV는 v3 ExtraTrees Optuna로 채움 | 작은 매출 셀 WAPE 25% — TCN-A 일부 동·업종 과대 예측 (공덕 +67%) | `validation/phase_b_seoul_63ind.py` |
| 10 | Pydantic ↔ TS type 자동 codegen 없음 | schema drift 위험 (수동 동기화) | `frontend/src/types/index.ts` |

### 14-2. 핵심 설계 결정

| 결정 | 의미 |
|---|---|
| **module-level `compile_workflow()`** (main.py:107) | startup hang 위험 vs. lazy init 단순성 trade-off |
| **5-Phase DAG + asyncio.gather** | 30~40초 응답 보장 (Phase 2 6 LLM 병렬) |
| **Redis 캐시 24h** | 동일 입력 재실행 ~3-5초 |
| **ChromaDB RAG** | 법률 14 리스크 추출 (LLM hallucination 방지) |
| **TCN pretrain→finetune** | 서울 데이터로 일반화 + 마포 특화 |
| **TCNForecaster → TCNClassifier 전이학습** | 폐업위험도 모델 학습 데이터 부족 보완 |
| **dong_code FK 추가** (사용자 IM3-243 작업) | 데이터 무결성 |
| **simulation_quarters: 16** (B2 04-25 변경) | 4분기 → 16분기 확장, 단 frontend 미반영 |

### 14-3. 강한 부분

- **ABM + LLM 에이전트 + ML 모델 3층 통합**이 단일 응답에 결합
- **api-contract.md** 04-28 최신, response shape·null/empty 정책 명시
- **테스트 24개 + frontend vitest**, asyncio_mode auto
- **22 alembic 마이그레이션** + master 테이블 (dong_mapping/seoul_dong_master/dong_centroid)
- **Multi-track 협업**: A1·A2·B1·B2·C1·C2 6명 분담, AGENTS.md 영역 명시

---

## 15. 향후 작업 권장 (우선순위)

| # | 작업 | ROI | 본인 영역? |
|---|---|---|---|
| 1 | SummaryTab `=== 4` → `>= 1` 수정 (1줄, 카드 2 즉시 복구) | 🔥 | C1 |
| 2 | synthesis_node `final_report.profit_simulation` 채우기 (카드 3 복구) | 🔥 | B2 |
| 3 | `graph.py:200` `segment_profile` 인자 추가 (customer_segment 복구) | 🔥 | B2 |
| 4 | `competitor_intel` 브랜드 매핑 alias 추가 | 🟡 | B2 |
| 5 | `closure_risk` 모델 추론 디버그 | 🟡 | B2 |
| 6 | `services/operational_fit_loader.py` 공통 헬퍼 (모든 op_fit 활용처 진입점) | 🔥 | ✅ A1 |
| 7 | TCN 35피처 확장 (`op_fit_total` 추가) | 🟡 | B2 |
| 8 | Pydantic ↔ TS 자동 codegen (openapi-typescript) | 🟡 | C1·B2 |
| 9 | `_hot_deck` 의 `== 0` 결측 처리 옵션화 | 🟢 | B2 |
| 10 | LSTM 가중치 디렉토리 정리 (레거시 archive) | 🟢 | B2 |

---

## 16. 결론

SPOTTER는 **잘 분리된 6-track 협업 구조의 LangGraph 기반 multi-agent 시뮬레이터**다. 8 에이전트 + 5 ML 모델 + ABM이 30~40초 안에 마포 16동 출점 의사결정 보고서를 생성하며, Frontend는 8개 탭으로 이 결과를 시각화한다.

핵심 강점은 (1) **DB·인프라·인증·CORS 전 계층 정상 작동**, (2) **22 alembic 마이그레이션과 master 테이블로 데이터 무결성 보장**, (3) **Redis/ChromaDB로 성능과 정확성 균형**, (4) **ABM + LLM + ML의 3층 통합**.

알려진 약한 고리는 (1) **frontend ↔ backend schema drift** (`final_report` 키 누락, `=== 4` 하드코딩), (2) **노드 4개 fail** (closure_risk, scenarios, trend_forecast, customer_segment), (3) **Pydantic ↔ TS 수동 동기화**. 1~3건은 5분~한 시간 fix 가능한 단순 mismatch.

본인(A1) 단독 진행 가능한 **가장 ROI 높은 작업은 `services/operational_fit_loader.py` 공통 헬퍼 모듈 작성** (op_fit score 6개 활용처의 진입점). `validation/abm_vs_grid_*.py` baseline 강화도 본인 영역 확장 가치 큼.

---

## 17. 참고 자료

- API 계약: [`docs/architecture/api-contract.md`](./api-contract.md) (04-28 최신, 11KB)
- 아키텍처 개요: [`docs/architecture/architecture.md`](./architecture.md)
- ERD: [`docs/architecture/spotter_dashboard_api_schema.md`](./spotter_dashboard_api_schema.md)
- AGENTS.md: 6-track 영역 분담
- 본 PR: https://github.com/Himidea-AI/Final_Project/pull/127 (IM3-243)
- 본인 작업 spec: [`docs/superpowers/specs/2026-04-25-tcn-imputed-vs-original-comparison-design.md`](../superpowers/specs/2026-04-25-tcn-imputed-vs-original-comparison-design.md)
- 본인 작업 plan: [`docs/superpowers/plans/2026-04-25-tcn-imputed-vs-original-comparison.md`](../superpowers/plans/2026-04-25-tcn-imputed-vs-original-comparison.md)
- TCN 비교 결과: [`docs/abm-simulation/tcn-imputed-comparison-report.md`](../abm-simulation/tcn-imputed-comparison-report.md)
- TCN 테스트 케이스: [`docs/abm-simulation/tcn-imputed-comparison-test-cases.md`](../abm-simulation/tcn-imputed-comparison-test-cases.md)
- SummaryTab issue: [`docs/issues/2026-04-28-summary-tab-empty-cards.md`](../issues/2026-04-28-summary-tab-empty-cards.md)
- op_fit 활용 평가: [`docs/proposals/2026-04-28-operational-fit-score-applicability.md`](../proposals/2026-04-28-operational-fit-score-applicability.md)
- op_fit 적용 레시피: [`docs/proposals/2026-04-28-operational-fit-score-integration-recipes.md`](../proposals/2026-04-28-operational-fit-score-integration-recipes.md)
