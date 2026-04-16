# 마포구 프랜차이즈 상권분석 시뮬레이터

AI Agent 기반 프랜차이즈 출점 시뮬레이션 플랫폼

## 프로젝트 개요

프랜차이즈 본사 영업기획팀이 마포구 내 신규 출점 후보지를 동(洞) 단위로 시뮬레이션하여,
카니발리제이션(자기 잠식), 경쟁 환경, 매출 예측, 법률 리스크를 종합 분석하는 AI 도구입니다.

## 핵심 기능

- **상권 분석**: 마포구 16개 행정동의 생활인구, 경쟁 밀도, 소비 패턴 분석
- **카니발리제이션 분석**: 같은 브랜드 기존 매장과의 매출 잠식률 산출
- **간접 경쟁 분석**: 동일 업종 + 대체재(배달 야식 등) 경쟁 반영
- **매출 예측**: 딥러닝 기반 12개월 매출 추이 시뮬레이션
- **법률 리스크**: RAG 기반 가맹사업법/상가임대차보호법 자동 검토
- **What-if 시나리오**: 경쟁 진입, 임대료 변동, 정책 변화 시 재시뮬레이션

## 기술 스택

| 영역 | 스택 |
|------|------|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS + Recharts + React-Leaflet |
| Backend | FastAPI + Uvicorn + Pydantic v2 + SQLAlchemy |
| AI/Agent | LangChain + LangGraph + Anthropic SDK + OpenAI SDK |
| RAG | ChromaDB + OpenAI Embeddings + lxml + PyPDF2 |
| Deep Learning | PyTorch + scikit-learn + SHAP |
| Database | PostgreSQL 16 + Redis 7 + ChromaDB |
| DevOps | Docker + Docker Compose + Nginx |

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

### 병렬 워크플로우 (현재 구조)

```
START
  │
  ▼
parallel_analysis ──────────────────────────────────────
  ├── Market Analyst      상권 데이터 수집 + LLM 분석
  ├── Population Analyst  유동인구 추이 + LLM 분석
  ├── Legal Analyst       RAG 기반 법률 리스크 14개 항목
  └── District Ranking    마포구 16개 동 정량 스코어링 (LLM 없음)
  │         (asyncio.gather — 동시 실행)
  ▼
synthesis             4개 결과 종합 → 최종 전략 리포트 생성
  │
  ▼
END
```

> **변경 이력** : 초기 `Supervisor → 순차 실행` 구조에서 병렬 실행으로 전환. Supervisor / ContextAnalyst 노드 제거. 응답 속도 약 3배 향상 (cold start 기준 ~35초).

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
| 동 선택 | market / population 에이전트 | 심층 분석 텍스트 및 차트 지표 변경 |
| 업종 선택 | 전 에이전트 DB 쿼리 | 업종별 매출/경쟁/법률 데이터 분리 |
| 상권 반경 | market_analyst | 경쟁 업체 탐색 반경 (기본 500m) |
| 임대료 예산 + 매장 면적 | district_ranking | 예산 초과 동 순위 하락 |
| 인구 가중치 | district_ranking | 가중치 동적 변경 → winner_district 변경 |
| 목표 객단가 | synthesis LLM | ai_recommendation 텍스트 반영 |
| 주 타겟 시간대 | synthesis LLM | ai_recommendation 텍스트 반영 |
| 초기 자본금 | synthesis LLM | ai_recommendation 텍스트 반영 |

### API 주요 응답 필드

`POST /simulate` 및 `POST /analyze` 공통 응답:

```jsonc
{
  "ai_recommendation": "AI 최종 분석 요약 (synthesis 에이전트)",
  "winner_district": "성산2동",            // 1순위 추천 행정동
  "top_3_candidates": ["성산1동", "망원2동", "염리동"],
  "district_rankings": [ /* 16개 동 전체 점수 테이블 */ ],
  "market_report": {                       // 프론트 차트용 0~100 지표
    "floating_population": 70,
    "rent_index": 50,
    "competition_intensity": 60,
    "estimated_revenue": 75,
    "survival_rate": 40,
    "growth_potential": 30,
    "accessibility": 75
  },
  "legal_risks": [ /* 14개 법률 리스크 항목 */ ],
  "overall_legal_risk": "CAUTION"
}
```

### Redis 캐싱 전략

| 에이전트 | 캐시 키 | TTL |
|---------|--------|-----|
| market | `market:{district}:{biz_type}` | 24h |
| population | `population:{district}:{biz_type}` | 24h |
| legal | `legal:{brand}:{district}:{biz_type}` | 24h |
| synthesis | `synthesis:{brand}:{district}:{biz}:{budget}:{area}:{pop_weight}` | 24h |

---

## B1 — LangGraph Agent 완료 작업 이력

> 담당: 예진 (`backend/src/agents/`, `backend/src/schemas/`)

### IM3-180 · IM3-32 (2026-04)

| 구분 | 내용 |
|------|------|
| 병렬 워크플로우 | Supervisor 제거, 4개 에이전트 `asyncio.gather` 병렬 실행 |
| District Ranking | 마포구 16개 동 정량 스코어링 에이전트 신규 개발 |
| LLM 전환 | `gemini-2.5-flash` → `gpt-4.1-mini` (429 쿼터 소진 대응) |
| 파일 삭제 | `supervisor.py`, `context_analyst.py` 제거 |

### IM3-144 (2026-04)

| 구분 | 내용 |
|------|------|
| 프론트 실데이터 연동 | `ai_recommendation`, `market_report`(7개 지표), `winner_district`, `top_3_candidates` API 응답 추가 |
| 요청 중복 방지 | `_run_pipeline()` dedup — 동시 요청 시 파이프라인 공유로 DB 풀 고갈 방지 |
| 입력값 전반영 | 9개 사용자 입력 → 랭킹 가중치·예산 필터·synthesis 프롬프트 반영 |
| 업종코드 정규화 | `"cafe"` → `"CS100010"` 자동 변환 (`_SALES_CODE_MAP` 추가) |
| `_KAKAO_CATEGORY_MAP` | 영문 업종명(cafe, chicken 등) 매핑 추가 |
| LLM 프롬프트 개선 | `competition_score` 0.0~1.0 스케일 명시, `rent_affordability` SAFE/CAUTION/DANGER 명시 |

---

## 실행 방법

### Docker Compose (권장)

```bash
# 환경 설정
cp .env.example .env
# .env 파일에 API 키 입력

# 전체 서비스 실행
docker compose up --build
```

- Frontend: http://localhost (Nginx)
- Backend API: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- ChromaDB: localhost:8001

### 개발 모드 (로컬)

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
