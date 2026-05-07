# 마포구 프랜차이즈 상권분석 시뮬레이터

AI Agent 기반 프랜차이즈 출점 시뮬레이션 플랫폼

## 프로젝트 개요

프랜차이즈 본사 영업기획팀이 마포구 내 신규 출점 후보지를 동(洞) 단위로 시뮬레이션하여,
카니발리제이션(자기 잠식), 경쟁 환경, 매출 예측, 법률 리스크를 종합 분석하는 AI 도구입니다.

### 핵심 기능

- **상권 분석**: 마포구 16개 행정동의 생활인구, 경쟁 밀도, 소비 패턴 분석
- **카니발리제이션 분석**: 같은 브랜드 기존 매장과의 매출 잠식률 산출
- **매출 예측**: TCN/LSTM/LightGBM 기반 12개월 forecast
- **법률 리스크**: 13 카테고리 (9 deterministic rules + 4 RAG specialists)
- **ABM 시뮬레이션**: 마포 5,000 에이전트 LLM 기반 의사결정
- **What-if 시나리오**: 경쟁 진입, 임대료 변동 시 재시뮬레이션

---

## 기술 스택

### 백엔드
- **Framework**: FastAPI, Pydantic v2
- **AI**: LangGraph, LangChain, OpenAI, Anthropic, Google Gemini
- **Database**: PostgreSQL 16 (AWS RDS) + pgvector + HNSW index
- **Cache**: Redis 7
- **ML**: PyTorch (TCN), LightGBM, SHAP, scikit-learn
- **ABM**: mesa (5,000 agents)

### 프론트엔드
- **Framework**: React 18, TypeScript 5, Vite 6
- **Styling**: Tailwind CSS
- **Visualization**: Recharts, Leaflet
- **State**: Zustand

### 인프라
- **Containerization**: Docker Compose
- **Database**: AWS RDS PostgreSQL 16
- **Reverse Proxy**: Nginx
- **Observability**: LangSmith

---

## 팀 구조

### 트랙 A — 데이터 + RAG

| 역할 | 담당자 | 주요 작업 |
|------|--------|----------|
| A1 — 데이터 + DB + RAG + ABM | 찬영 | DB 설계 (78 ORM), ETL 파이프라인 (5종), RAG 최적화, ABM 시뮬레이션 |
| A2 — RAG + 법률 | 봉환 | 법률 문서 청킹 (10,255 chunks), BGE-m3 + Kiwi BM25 하이브리드 검색 |

### 트랙 B — AI 엔진

| 역할 | 담당자 | 주요 작업 |
|------|--------|----------|
| B1 — LangGraph Agent | 예진 | 5-Phase 워크플로우, 10개 에이전트 노드 (5,326 lines), 상태 관리 |
| B2 — 딥러닝 모델 | 수지니 | TCN 매출 예측, LightGBM+TCN Ensemble (AUC 0.617), Feature Engineering (30+) |

### 트랙 C — 프론트엔드 + 배포

| 역할 | 담당자 | 주요 작업 |
|------|--------|----------|
| C1 — 프론트엔드 | 강민 | 12 Routes, 3-Pipeline 대시보드, 20+ 차트, Zustand 상태 관리 |
| C2 — 인프라 | 혁 | Docker Compose, AWS RDS 연결 |

---

## 📚 문서

### 팀원별 상세 기술 문서

각 팀원의 상세한 기술 구현 내용은 별도 문서로 작성되어 있습니다:

- **[B1 - LangGraph Agent 아키텍처 (예진)](docs/team/TEAM_B1_예진_LangGraph.md)**
  - 5-Phase LangGraph 워크플로우 설계
  - 10개 에이전트 노드 구현 (5,326 lines)
  - AgentState 상태 관리 (82 필드)
  - MarketDataTool 데이터 바인딩 (18 메서드)
  - LLM 통합 및 최적화 (Retry Proxy, 토큰 예산 관리)
  - LangSmith 트레이싱 통합 (전체 워크플로우 관측성)
  - 정확도 평가 시스템 v7 (50%→87.5%)

- **[A1 - 데이터 + DB + RAG + ABM (찬영)](docs/team/TEAM_A1_찬영_데이터.md)**
  - Database 스키마 설계 (78 ORM, 1,019 컬럼)
  - Alembic 마이그레이션 관리
  - 외부 API ETL 파이프라인 (5종)
  - Legal RAG 최적화 (MRR 0.931, Hit@10 100%)
  - ABM 시뮬레이션 (5,000 에이전트)
  - Brand 매핑 시스템

- **[C1 - 프론트엔드 (강민)](docs/team/TEAM_C1_강민_프론트.md)**
  - 복합 대시보드 아키텍처 (12 routes, 3-pipeline)
  - 데이터 시각화 (Recharts 20+ 차트)
  - Zustand 상태 관리 (3-store)
  - 인증 및 세션 관리
  - 비동기 작업 처리 (Real-time Polling)

- **[B2 - 딥러닝 모델 (수지니)](docs/team/TEAM_B2_수지니_ML.md)**
  - 모델 아키텍처 비교 (TCN vs LSTM vs GRU vs Transformer)
  - Feature Engineering (30+ features)
  - 하이퍼파라미터 튜닝
  - LightGBM+TCN Ensemble (AUC 0.617)
  - SHAP 해석성

- **[A2 - RAG + 법률 (봉환)](docs/team/TEAM_A2_봉환_RAG.md)**
  - 법률 문서 청킹 전략 (10,255 chunks)
  - BGE-m3 + Kiwi BM25 하이브리드 검색
  - RRF (Reciprocal Rank Fusion)
  - pgvector + HNSW Index

- **[C2 - 인프라 (혁)](docs/team/TEAM_C2_혁_인프라.md)**
  - Docker Compose 설정
  - AWS RDS 연결

### 기타 문서
- API 명세서
- 배포 가이드
- 아키텍처 다이어그램

---

## 빠른 시작

### 환경 설정

```bash
# 환경 변수 설정
cp .env.example .env
# .env 필수: POSTGRES_URL (AWS RDS endpoint)
#          + API 키 (ANTHROPIC, OPENAI, GOOGLE, FTC, KAKAO, ECOS, ...)
```

### Docker Compose 실행 (권장)

```bash
docker compose up --build
```

- Frontend: http://localhost
- Backend API: http://localhost:8000
- Redis: localhost:6379

### 로컬 개발 모드

```bash
# 백엔드
cd backend
pip install -r requirements.txt
uvicorn src.main:app --reload

# 프론트엔드
cd frontend
npm install
npm run dev
```

---

## 주요 Endpoint

### Simulation API

| Endpoint | Method | 설명 | 응답 시간 |
|----------|--------|------|----------|
| `/predict` | POST | ML 예측 (TCN/BEP/폐업률) | ~10s |
| `/analyze/llm` | POST | LLM 분석 (6 agents + synthesis) | ~80-140s |
| `/simulate-abm` | POST | ABM 시뮬레이션 (5,000 agents) | ~30-60s |
| `/predict/{job_id}/status` | GET | ML 진행률 polling | ~250ms |
| `/analyze/llm/{job_id}/status` | GET | LLM 진행률 polling | ~250ms |
| `/corp/operated-industries` | GET | 운영 업종/브랜드 조회 | ~50ms |
| `/stores/count-by-dongs` | GET | 동별 매장 수 집계 | ~30ms |

---

## Database Schema

**규모**: 78 ORM models / ~1,019 columns / 32 FK

### 주요 테이블 카테고리

| 카테고리 | 대표 테이블 |
|---------|-----------|
| Population | living_population, sgis_population, mapo_resident_pop |
| Sales | district_sales, golmok_commercial, seoul_district_sales |
| Rent | rent_cost, golmok_rent, seoul_golmok_rent |
| Business | industry_master, kakao_store, seoul_adstrd_* |
| Franchise | ftc_brand_franchise (16K rows), mart_brand_territory |
| Legal | law_legislations, law_precedents |
| Simulation | simulation_foresee (ML), simulation_ai (LLM) |

---

## AI 에이전트 아키텍처

### LangGraph 5-Phase 워크플로우

```
START
  ↓
[Phase 0] inflow             교통·집객 인프라 점수 (~50ms)
  ↓
[Phase 1] ranking_phase      16동 정량 스코어링 (LLM 없음)
  ↓
[Phase 2] llm_analysis       6 LLM 에이전트 병렬 실행
  │   ├── Market Analyst
  │   ├── Population Analyst
  │   ├── Legal Analyst (13 카테고리)
  │   ├── Demographic Depth
  │   ├── Trend Forecaster
  │   └── Competitor Intel
  ↓
[Phase 2.5] ml_prediction    TCN + BEP + 폐업률 (LightGBM)
  ↓
[Phase 3] synthesis          최종 전략 리포트 생성
  ↓
END
```

### 2-Endpoint 분리 (IM3-259)

빠른 ML 결과 + 느린 LLM 결과를 frontend가 동시 polling으로 점진적 UI 갱신

---

## 개발 도구

### 코드 품질

```bash
# 백엔드 (Ruff)
cd backend && ruff check --fix && ruff format

# 프론트엔드 (Prettier + ESLint)
cd frontend && npx prettier --write . && npx eslint --fix .
```

### Alembic 마이그레이션

```bash
cd backend
alembic current                          # 현재 버전 확인
alembic upgrade head                     # 최신 적용
alembic revision -m "변경 내용"          # 새 revision
```

---

## 주요 환경 변수

| 카테고리 | 변수 |
|---------|------|
| LLM | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` |
| DB | `POSTGRES_URL`, `REDIS_URL` |
| 외부 API | `FTC_API_KEY`, `KAKAO_API_KEY`, `ECOS_API_KEY`, `NAVER_CLIENT_ID` |
| 관측성 | `LANGCHAIN_API_KEY`, `LANGCHAIN_TRACING_V2` |
| 인증 | `JWT_SECRET_KEY`, `JWT_ALGORITHM` |

---

## 성과 지표

### AI 정확도
- Market Analyst: 50% → **87.5%** (+37.5%p, v6→v7)
- Demographic Depth: 83% → **100%** (+16.7%p)
- Trend Forecaster: 67% → **82%** (+15.1%p)

### ML 성능
- Closure Risk AUC: **0.617** (+20% lift vs baseline)
- TCN Forecast RMSE: **12.3M** (validation)

### RAG 검색
- MRR: 0.785 → **0.931** (+0.146)
- NDCG: 0.642 → **0.776** (+0.134)
- Hit@10: 62.1% → **100%** (+37.9%p)

### 시스템 성능
- emerging_district: 8.11s → **1.12s** (-86.2%)
- Redis 24h TTL 캐싱

---

## 라이선스

MIT License

---

## Contact

프로젝트 관련 문의: [이메일 주소]
