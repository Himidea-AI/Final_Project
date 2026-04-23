# 마포구 프랜차이즈 상권분석 시뮬레이터 — 기술 스펙 문서

> **Version:** 1.0  
> **Date:** 2026-04-02  
> **Team:** Himidea-AI (6명)  
> **Duration:** 5주 (2026-04-02 ~ 2026-05-07)

---

## 1. 프로젝트 개요

### 1.1 목적

프랜차이즈 출점 의사결정을 AI Agent 기반으로 자동화하는 시뮬레이션 플랫폼.  
마포구 16개 행정동을 대상으로 카니발리제이션(자기 잠식), 경쟁 환경, 매출 예측, 법률 리스크를 종합 분석한다.

### 1.2 핵심 차별점

기존 서비스가 **현재의 스냅샷**만 보여준다면, 본 시뮬레이터는 **"시간의 흐름 + 경쟁자 반응 + 정책 변화"**를 반영한 **미래 예측 시뮬레이션**을 수행한다.

### 1.3 페르소나

| 구분 | 대상 | 니즈 |
|------|------|------|
| **A — 예비 창업자 (B2C)** | 퇴직 후 마포구 음식점 창업 고려 중인 50대 | 내 예산으로 어느 동네, 어떤 업종이 가장 안전한가 |
| **B — 프랜차이즈 본사 (B2B)** | 신규 가맹점 입지 검토를 월 수십 건 처리 | 후보지 빠른 스크리닝, 보고서 자동 생성 |
| **C — 컨설팅 기관 (B2B)** | 소진공, 지역 창업센터 | 상담 고객에게 데이터 기반 근거 제시 |

### 1.4 시뮬레이션 분석 항목

- 월세/보증금(권리금 포함), 인건비/재료비(원가율)/공과금/마케팅비/관리비
- 업종 허가 가능 여부, 위생/소방 인허가 조건
- 마포구 젠트리피케이션 방지 협약 및 지역 인허가 제한 사항 (RAG 반영)
- 유동인구, 접근성(교통/주차), 가시성(도로 노출도)
- 주변인구(주중/주말), 연령/가구 구성(1인가구 밀집 여부)
- 소비 패턴 및 주요 소비 카테고리
- 경쟁환경(경쟁 점포 가격대/고객 만족도)
- 상권 생태계(앵커 시설 유무), 주변 점포 공실률, 상권 성장성
- 업종별 평균 영업 기간 및 폐업률 시계열 분석 (마포구 빠른 유행주기 반영)

---

## 2. 시스템 아키텍처

### 2.1 전체 구조

```
외부 데이터                    수집·정제 파이프라인           PostgreSQL (정형 데이터)
(소상공인/서울 생활인구/        → Batch Jobs / ETL /    →
 SGIS/국토부/공정위/              Parser / Validator
 golmok/Naver DataLab)                                     ┌─→ 분석 엔진 (Rule Functions + ML Model)
                                                           │
                              ChromaDB (비정형 문서 RAG) ─┐ │
                                                         ↓ ↓
                              FastAPI Backend ←──────── LangGraph Agent Layer
                              (REST API / Orchestrator)    (분석 / 재분석 / 전략추천)
                                 │
                    ┌────────────┼────────────┐
                    ↓            ↓            ↓
              Redis (캐시/     React Frontend   Nginx + Docker Compose
              작업상태/결과)   (입력/지도/차트)   (Reverse Proxy / Static Serve)
```

### 2.2 데이터 흐름

1. **수집**: 7개 외부 API → `src/data_pipeline/fetch.py`
2. **정제**: 컬럼 정규화, 결측치 처리 → `src/data_pipeline/preprocess.py`
3. **적재**: PostgreSQL + ChromaDB → `src/data_pipeline/load.py`
4. **분석**: 규칙 기반 엔진(`src/engine/`) + ML 모델(`src/ml_models/`)
5. **AI Agent**: LangGraph 워크플로우로 분석 결과 종합 → `src/ai/`
6. **서빙**: FastAPI REST API → React Frontend 시각화

### 2.3 API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `POST` | `/api/simulate` | 시뮬레이션 요청 (비동기 job 생성) |
| `GET` | `/api/result/{id}` | 시뮬레이션 결과 조회 |
| `GET` | `/api/report/{id}` | 리포트 조회 (PDF/JSON) |
| `POST` | `/api/analyze` | AI Agent 자연어 분석 요청 |

---

## 3. 기술 스택

### 3.1 Frontend

| 기술 | 용도 |
|------|------|
| React 18+ (TypeScript) | UI 프레임워크 |
| Vite | 빌드 도구 |
| Tailwind CSS | 스타일링 |
| React Router | 페이지 라우팅 |
| Axios | HTTP 클라이언트 |
| Recharts | 차트 시각화 (매출 추이, TOP 5 이유, BEP 비교) |
| React-Leaflet | 지도 시각화 (히트맵, Choropleth, 마커 팝업) |

### 3.2 Backend

| 기술 | 용도 |
|------|------|
| FastAPI | 웹 프레임워크 |
| Uvicorn | ASGI 서버 (단독) |
| Pydantic v2 + pydantic-settings | 데이터 검증 + 환경변수 관리 |
| SQLAlchemy (SQLModel) | ORM + DB 테이블 정의 |
| httpx | 비동기 HTTP 클라이언트 |
| tenacity | API 호출 재시도 로직 |

### 3.3 AI / Agent

| 기술 | 용도 |
|------|------|
| LangChain | 외부 데이터(API, DB) 연결 및 도구 활용 |
| LangGraph | 에이전트 간 협업 및 순환(Cycle) 로직 설계 |
| Anthropic SDK | LLM 호출 |
| OpenAI SDK | 임베딩 + 백업 LLM |

> **선택 이유**: CrewAI는 순차적 업무에 강하지만, 본 프로젝트는 "경쟁자 반응 → 매출 변화 → 전략 재수정"과 같은 **순환과 상태 유지**가 필수적. LangGraph가 복잡한 제어 흐름 설계에 가장 적합.

### 3.4 RAG

| 기술 | 용도 |
|------|------|
| ChromaDB | 벡터 DB (로컬, 무료) |
| LangChain Retrievers | 검색기 |
| PyPDF2 / pdfplumber | PDF 파싱 (가맹사업법, 상가임대차보호법) |
| lxml | XML 파싱 (공정위 정보공개서) |

### 3.5 Deep Learning

| 기술 | 용도 |
|------|------|
| PyTorch (XGBoost) | 매출 예측 모델 |
| scikit-learn | 피처 엔지니어링, 전처리 |
| SHAP | 설명 가능한 AI (예측 근거 시각화) |
| pandas / numpy | 데이터 처리 |

### 3.6 Database

| DB | 용도 | 비고 |
|----|------|------|
| PostgreSQL 16 | 구조화된 데이터 (상권 통계, 유동인구, 시나리오) | Supabase 플랜 사용 예정 |
| ChromaDB | 비정형 문서 (가맹사업법, 판례, 리포트) — RAG용 | 로컬 무료 |
| Redis 7 | 동일 조건 시뮬레이션 결과 캐시 + 작업 상태 관리 | |

### 3.7 DevOps / 코드 품질

| 기술 | 용도 |
|------|------|
| Docker + Docker Compose | 컨테이너화 (PostgreSQL, Redis, ChromaDB, Nginx) |
| Nginx (alpine) | 리버스 프록시 + SSL(TLS) + React 정적 파일 서빙 |
| Ruff | Python linter + formatter |
| Pre-commit Hooks | 커밋 시점 자동 코드 정렬 |
| pytest | 테스트 |

---

## 4. 디렉토리 구조

```
마포구_상권_시뮬레이터/
├── README.md
├── .gitignore
├── .env.example
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
├── AI_CODE_GEN_RULES.md                        # 팀 공통 엔지니어링 프로토콜
│
├── data/
│   ├── raw/                                    # 원본 수집 데이터 (CSV, JSON, XML, PDF)
│   └── processed/                              # 전처리 후 분석/학습용 데이터
│
├── nginx/
│   └── default.conf                            # reverse proxy 설정
│
├── notebooks/                                  # EDA, 가설 검증, 실험용 노트북
│
├── docs/
│   └── architecture.md                         # 시스템 구조 및 데이터 흐름
│
├── src/                                        # 메인 소스 코드
│   ├── main.py                                 # FastAPI 실행 진입점
│   │
│   ├── api/
│   │   └── simulation.py                       # 시뮬레이션 요청/조회 엔드포인트
│   │
│   ├── core/
│   │   ├── config.py                           # 환경변수, 상수, 설정 관리
│   │   └── db.py                               # PostgreSQL/Redis 연결 설정
│   │
│   ├── schemas/
│   │   ├── state.py                            # LangGraph 공유 상태 (AgentState)
│   │   └── models.py                           # 요청/응답/분석 결과 모델
│   │
│   ├── database/
│   │   ├── models.py                           # SQLAlchemy 테이블 정의
│   │   ├── repository.py                       # PostgreSQL 조회/저장 로직
│   │   └── vector_db.py                        # ChromaDB 벡터 저장소
│   │
│   ├── data_pipeline/                          # 외부 데이터 수집/정제/적재
│   │   ├── fetch.py                            # 7개 API 호출
│   │   ├── preprocess.py                       # 정제, 컬럼 정규화, 결측 처리
│   │   └── load.py                             # PostgreSQL/ChromaDB 적재
│   │
│   ├── engine/                                 # 규칙/계산 기반 분석 (LLM 없음)
│   │   ├── scoring.py                          # 상권 점수 계산
│   │   ├── bep.py                              # 손익분기점 계산
│   │   └── risk.py                             # 리스크 계산
│   │
│   ├── ml_models/                              # 예측 모델
│   │   ├── train.py                            # 모델 학습
│   │   ├── predict.py                          # 추론
│   │   ├── features.py                         # 피처 엔지니어링
│   │   ├── explain.py                          # SHAP 설명 가능성
│   │   └── weights/                            # 모델 가중치 (.pt)
│   │
│   ├── ai/                                     # LangGraph + LLM + RAG
│   │   ├── agent.py                            # 워크플로우 구성/실행
│   │   ├── nodes.py                            # 단계별 노드 실행
│   │   ├── prompts.py                          # 프롬프트 템플릿
│   │   └── rag/
│   │       ├── chunker.py                      # 법률/문서 청킹
│   │       └── retriever.py                    # ChromaDB 검색기
│   │
│   ├── services/
│   │   └── simulation_service.py               # 전체 흐름 오케스트레이션
│   │
│   └── tasks/
│       └── simulation_task.py                  # 비동기/장시간 작업 처리
│
├── frontend/
│   ├── package.json
│   └── src/
│       ├── App.tsx
│       ├── pages/
│       │   ├── SimulationPage.tsx               # 조건 입력 화면
│       │   └── ResultPage.tsx                   # 결과 출력 화면
│       ├── components/
│       │   ├── Form.tsx                         # 입력 폼
│       │   ├── Chart.tsx                        # 차트 시각화
│       │   └── map/
│       │       ├── MapView.tsx                  # React-Leaflet 지도 메인
│       │       ├── HeatmapLayer.tsx             # 상권 밀집도/유동인구 히트맵
│       │       └── MarkerPopup.tsx              # 점포/행정동 상세 팝업
│       └── api/
│           └── simulationApi.ts                # 백엔드 API 호출
│
└── tests/
    └── test_simulation.py                      # 전체 시뮬레이션 흐름 테스트
```

---

## 5. 데이터 소스

### 5.1 사용 확정 API (6개)

| # | 데이터 소스 | 제공 항목 | 갱신 주기 | 신뢰성 | 주의사항 |
|---|-----------|----------|----------|--------|---------|
| 1 | **소상공인시장진흥공단** | 상호명, 업종코드(247개), 주소, 좌표 | 분기 1회 | 높음 | 업종코드 837→247 개편, 과거 데이터 연계 불가 |
| 2 | **서울 생활인구** (OA-14991) | 시간대/요일별 생활인구 | 월 1회 | 높음 | 유동인구조사 중단됨, KT 통신 기반 "생활인구" 사용 |
| 3 | **통계청 SGIS** | 연령별 인구, 가구 구성, 1인가구 비율 | 연 1회 | 매우 높음 | OAuth2 인증 방식 (consumer_key/secret → access_token, 1시간 유효) |
| 4 | **국토교통부 실거래가** | 상가 임대 보증금/월세/면적 | 월 1회 | 매우 높음 | 상가 데이터 커버리지 부족 시 golmok 임대시세로 Fallback |
| 5 | **공정위 가맹사업 정보공개서** | 브랜드 매출, 가맹점 수, 인테리어 비용 | 연 1회 | 매우 높음 | API는 목록만, 상세는 XML 파싱 필요 |
| 6 | **서울 상권분석서비스** (golmok) | 폐업률, 생존율, 상권변화지표, 카드 추정매출 | 분기 1회 | 높음 | data.seoul.go.kr의 Open API 사용 (OA-15560, OA-15575) |

### 5.2 대체 결정

| 원래 계획 | 문제점 | 대체 방안 |
|----------|--------|----------|
| SNS 크롤링 (Instagram/블로그) | 이용약관 위반, 차단 리스크 | **Naver DataLab 트렌드 API** — 키워드 검색량 추이로 "힙 지수" 대체 |
| 카드사 빅데이터 (신한/BC) | 기업 제휴 없이 접근 불가 | **golmok 추정매출** — 서울시-카드사 협약 기반 가공 데이터 |

### 5.3 Fallback 정책

- **상가 임대 실거래가 부재 시**: 인근 행정동 평균값 + golmok 지역별 평균 임대료 + 층별/면적별 보정 계수 결합
- **외부 API 호출 실패 시**: Mock 데이터로 Fallback하여 서비스 중단 방지

---

## 6. 시뮬레이션 결과물

### 6.1 기본 분석 지표

- **상권 매력도 점수** (1~100점): 인구 대비 경쟁 강도 계산
- **주요 소비층 페르소나**: "이 동네는 30대 직장인 남성이 주말보다 평일에 많이 소비함"

### 6.2 재무 예측 지표 (핵심)

- **예상 월 매출액** (원)
- **손익분기점(BEP) 예상 시점**: "오픈 후 N개월 뒤부터 흑자"
- **요일/시간대별 예상 매출 비중**: 피크 타임 예측

### 6.3 생존 및 리스크 분석

- **12개월 생존 확률** (%)
- **경쟁사 침투 리스크**: "인근에 메가커피 진입 시 매출 하락 예상치"
- **법률 리스크 등급**: 가맹사업법/임대차보호법 위반 가능성 (안전/주의/위험)

### 6.4 전략 추천

- **최적 운영 전략**: "홀 중심보다 배달 80% 비중이 유리함"
- **적정 권장 임대료**: "이 매출 규모라면 임대료는 최대 250만 원까지"
- **Shadow Simulation** (목표): 동일 조건의 타 구(예: 강서구) 대조군 자동 생성 → 기회비용 제시

### 6.5 시나리오 분석

- **3시나리오**: 낙관 / 기본 / 비관
- **민감도 분석**: 임대료 변동, 경쟁 진입, 정책 변화 시 재시뮬레이션
- **오픈 초기 매출 곡선 보정**: 신규 오픈 효과 반영

---

## 7. LangGraph Agent 워크플로우

### 7.1 Agent 노드 구성

```
사용자 입력
    ↓
[Supervisor] ──→ [상권분석 Agent] ──→ 소상공인 API + golmok API
    │          ──→ [유동인구 Agent] ──→ 서울 생활인구 API
    │          ──→ [인구통계 Agent] ──→ 통계청 SGIS API
    │          ──→ [비용산정 Agent] ──→ 국토교통부 실거래가 API
    │          ──→ [경쟁분석 Agent] ──→ 소상공인 API (카니발리제이션 + 간접경쟁)
    │          ──→ [트렌드 Agent]   ──→ Naver DataLab API
    │          ──→ [법규검토 Agent] ──→ ChromaDB / RAG
    ↓
[Supervisor 재분석 판단] ──→ 재분석 필요 시 루프
    ↓
[리포트 Agent] → 결과 종합 → PostgreSQL 저장
```

### 7.2 Agent 단계적 연결

| 주차 | Agent 기능 | 설명 |
|------|-----------|------|
| 3주차 | **Agent 1**: 결과 해석 | 분석 결과를 자연어로 해석 (~API 호출 30줄) |
| 4주차 | **Agent 2**: 조건 재설정 | Function Calling으로 사용자 자연어 → 파라미터 변환 |
| 4주차 | **Agent 3**: 최종 추천 | BEP 결과 기반 종합 전략 추천 |

### 7.3 공유 상태 (AgentState)

```
PostgreSQL 테이블:
  simulation_state / analysis_result / prediction_result /
  legal_risk / strategy_recommendation / agent_report
```

---

## 8. Frontend 화면 구성

### 8.1 페이지

| 페이지 | 주요 기능 |
|--------|----------|
| **SimulationPage** | 업종 선택, 브랜드명, 대상 행정동, 투자금/임대료 입력 |
| **ResultPage** | 종합 분석 결과 출력 |

### 8.2 시각화 컴포넌트

| 컴포넌트 | 설명 |
|---------|------|
| **MapView** (React-Leaflet) | 마포구 행정동 지도 + 레이어 컨트롤(On/Off) |
| **HeatmapLayer** | 업종 밀도(Heatmap & Marker), 유동인구 핫스팟(Choropleth) |
| **MarkerPopup** | 점포/행정동 상세 정보 팝업 (실제 매물/임대 정보 포함) |
| **Chart** (Recharts) | TOP 5 지표 그래프, 매출 추이, BEP 비교(5개 동 동시) |
| **BEP 시뮬레이터** | 슬라이더로 조건 변경 → 실시간 BEP 재계산 |
| **AI 리포트** | LLM 생성 자연어 분석 스트리밍 출력 |

---

## 9. 팀 구성 및 역할

### 9.1 트랙별 배치

| 트랙 | 역할 | 담당자 | 담당 디렉토리 |
|------|------|--------|-------------|
| **A — 데이터 파이프라인** | A1: 데이터 엔지니어 | 찬영 | `src/data_pipeline/`, `src/database/`, `data/` |
| | A2: RAG + 법률 데이터 | 봉환 | `src/ai/rag/`, `src/database/vector_db.py` |
| **B — AI 엔진** | B1: LangGraph Agent | 예진 | `src/ai/`, `src/schemas/` |
| | B2: 예측 모델 | 수지니 | `src/ml_models/`, `src/engine/` |
| **C — 프론트엔드 + 배포** | C1: 프론트엔드 | 강민 | `frontend/` |
| | C2: 인프라 + PM | 혁 | Docker, Nginx, `docs/`, `tests/` |

### 9.2 트랙 간 의존성

```
트랙 A (데이터 파이프라인) ──2주차 금요일 샘플 전달──→ 트랙 B (AI 엔진)
트랙 A ──2주차 RAG 파이프라인──→ 트랙 B
트랙 B ──3주차 예측 결과──→ 트랙 B1 (LangGraph Agent)
트랙 B ──3주차 Agent API──→ 트랙 C (프론트엔드)
트랙 C2 ──1주차 Docker 환경──→ 전체
```

---

## 10. 5주 개발 로드맵

### 1주차 — 기반 세팅 (병렬 시작 + 인터페이스 합의)

| 트랙 | 작업 내용 |
|------|----------|
| A1 | API 키 발급 + 7개 API 연동 테스트 + DB 스키마 설계 |
| A2 | 가맹사업법 + 상가임대차법 PDF 수집 + 핵심조항 수동 정리 |
| B1 | AgentState 설계 + `agent.py` 뼈대 + 상권/유동인구/인구통계 Agent 스켈레톤 |
| B2 | XGBoost 설계 + 학습 데이터 구조 정의 |
| C1 | React 프로젝트 세팅 + 페이지 라우팅 + 조건 입력 UI |
| C2 | Docker Compose 세팅 + GitHub 레포 세팅 + README |

> **1주차 핵심**: 엔진 ↔ UI 함수 인터페이스를 문서로 먼저 합의

### 2주차 — 핵심 구현 (데이터 샘플 전달 + 병렬 개발)

| 트랙 | 작업 내용 |
|------|----------|
| A1 | 전처리 파이프라인 + 마포구 16개 동 적재 + **엔진팀 샘플 CSV 전달** |
| A2 | ChromaDB 벡터화 + 검색 파이프라인 구축 |
| B1 | 경쟁분석 Agent (카니발리제이션 + 간접경쟁) + Supervisor 재분석 루프 |
| B2 | 모델 학습 + SHAP 설명 가능성 구현 |
| C1 | Leaflet 지도 + Recharts 차트 (히트맵 목업, BEP 슬라이더 프로토타입) |
| C2 | 백엔드 ↔ 프론트 API 연결 검증 + Nginx 리버스 프록시 설정 |

### 3주차 — 통합 연결 (가장 중요한 주)

| 트랙 | 작업 내용 |
|------|----------|
| A1 | 품질검증 + 결측치 처리 + 데모 데이터 |
| A2 | 법률 Agent 프롬프트 작성 + 테스트 |
| B1 | **실데이터 연결 + 통합 테스트** |
| B2 | 실제 데이터 기반 재학습 + 백테스트 |
| C1 | **API 연동 + 카니발리제이션 시각화** |
| C2 | 통합 테스트 + 도메인 연결 + SSL |

> **3주차 산출물**: 데이터 → 엔진 → UI 전체 연결된 작동 버전 (완성도 60%)  
> **Agent 1 연결**: 결과 해석 (API 호출 ~30줄)

### 4주차 — 고도화 + Agent

| 트랙 | 작업 내용 |
|------|----------|
| A1 | 데이터 최종 검증 + 오프라인 백업 |
| A2 | RAG 정확도 검증 + 법률 리스크 시나리오 테스트 |
| B1 | **프롬프트 튜닝 + 엣지 케이스 처리** |
| B2 | LSTM 시계열 추가(여유 시) + 정확도 리포트 |
| C1 | UI 폴리싱 + 반응형 + 데모 최적화 |
| C2 | 발표 자료 + 시연 스크립트 |

> **Agent 2 연결**: Function Calling (자연어 조건 재설정)  
> **Agent 3 연결**: 최종 추천 (BEP 결과 기반)  
> **산출물**: 전 기능 작동 버전 (완성도 90%)

### 5주차 — 마무리 + 발표

- 실제 마포구 케이스로 결과 검증, 엣지 케이스 버그 수정
- 발표용 데모 시나리오 (업종 변경, 조건 재설정, BEP 비교)
- 최종 발표 리허설
- **최종 산출물**: 완성 프로그램 + 발표 데모 + 분석 결과 문서

---

## 11. 코딩 프로토콜 (AI_CODE_GEN_RULES)

### Phase 1: Reasoning (코딩 전 설계)

1. **Problem Definition**: 진짜 해결해야 할 문제 정의
2. **Constraint Analysis**: 제약 조건 식별 (API 호출 제한, 데이터 시차, 비동기 필요성)
3. **Solution Strategy**: 구조 선택의 엔지니어링적 근거 제시
4. **No-Code First**: 코드 없이 해결 가능하면 먼저 제안

### Phase 2: Implementation Standards

- **Type Safety**: 모든 함수 인자/반환값에 타입 힌트 필수
- **Google Style Docstring**: 모든 Public 메서드 문서화
- **Single Responsibility**: 하나의 함수는 단 하나의 책임
- **Dependency Inversion**: 외부 API 연동 시 추상 클래스 선설계
- **Magic Values Zero**: 모든 상수를 config 객체로 관리

### Phase 3: Logging 표준

```python
print(f"[{datetime.now()}] [{self.__class__.__name__}] [{STATUS}] - {message}")
# STATUS: [THINKING], [TOOL_CALL], [SUCCESS], [ERROR]
```

### Phase 4: Quality Gate

- [ ] 동료 엔지니어가 1분 안에 로직을 이해할 수 있는가?
- [ ] 모든 변수/함수의 타입이 명확히 정의되었는가?
- [ ] 에이전트 동작 상태가 표준 포맷으로 로그 출력되는가?
- [ ] 과도한 엔지니어링 없이 문제의 본질만 해결했는가?
- [ ] 모든 에이전트 응답에 `step_id`와 `timestamp`가 포함되었는가?
- [ ] 외부 데이터 호출 실패 시 Fallback 데이터가 작동하는가?

---

## 12. 인터페이스 스펙 (JSON)

### 12.1 시뮬레이션 요청 (Client → API)

```json
{
  "business_type": "cafe",
  "brand_name": "이디야",
  "target_district": "망원1동",
  "existing_stores": [
    {"district": "서교동", "address": "서교동 123-4", "monthly_revenue": 32000000}
  ],
  "initial_investment": 150000000,
  "monthly_rent": 3500000,
  "simulation_months": 12,
  "scenarios": ["base", "competitor_entry", "rent_increase_20pct"]
}
```

### 12.2 시각화용 결과 (API → Frontend)

```json
{
  "request_id": "sim_20260402_001",
  "target_district": "망원1동",
  "monthly_projection": [
    {"month": 1, "revenue": 18000000, "cumulative_profit": -12000000},
    {"month": 12, "revenue": 26000000, "cumulative_profit": 15000000}
  ],
  "comparison": [
    {"district": "망원1동", "score": 72, "revenue": 26000000, "bep": 8, "survival": 0.68, "cannibalization": -0.18},
    {"district": "대흥동", "score": 78, "revenue": 18000000, "bep": 5, "survival": 0.91, "cannibalization": 0.0}
  ],
  "legal_risks": [
    {"type": "가맹사업법", "risk_level": "주의", "detail": "반경 500m 내 동일 브랜드 가맹점 1개 존재"}
  ],
  "ai_recommendation": "대흥동을 추천합니다. 자기 잠식이 없고 생존 확률이 91%로 가장 높습니다."
}
```

---

## 13. 1주차 Day 1 체크리스트

```
✅ 소상공인진흥공단 API 키 발급 → 마포구 망원1동 조회 테스트
✅ 서울 열린데이터광장 API 키 발급 → 생활인구 데이터 조회 테스트
✅ golmok 관련 Open API 엔드포인트 확인 (OA-15560 등)
✅ 공정위 정보공개서 API 키 발급 → 목록 조회 테스트
✅ 국토부 실거래가 API 키 발급 → 마포구 상가 임대 데이터 존재 확인
✅ Naver DataLab API 키 발급 (Naver Developers)
✅ 통계청 SGIS OAuth2 인증 테스트
⚠️ SNS 크롤링 코드 제거 → Naver DataLab API로 교체
⚠️ 카드사 직접 접근 코드 제거 → golmok 추정매출 사용
```
