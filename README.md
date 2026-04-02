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

| 역할 | 담당 디렉토리 |
|------|-------------|
| A — 데이터 엔지니어 | `backend/src/services/`, `backend/src/database/`, `data/` |
| B — AI Agent 개발자 | `backend/src/agents/`, `backend/src/schemas/` |
| C — 딥러닝 모델 | `models/` |
| D — RAG + 법률 | `backend/src/chains/` |
| E — 프론트엔드 | `frontend/` |
| F — PM / 검증 | `validation/`, `models/lstm_forecast/`, `docs/` |

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
