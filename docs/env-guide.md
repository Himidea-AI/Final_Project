# 환경변수 & 설정 파일 가이드

## 환경변수

환경변수는 `.env`에서 관리하며, `backend/src/config/settings.py`가 Pydantic Settings로 로드합니다.

| 변수 | 용도 | 사용하는 팀원 |
|------|------|-------------|
| `ANTHROPIC_API_KEY` | Claude LLM 호출 | B (Agent), D (RAG) |
| `OPENAI_API_KEY` | 임베딩 생성 | D (RAG) |
| `POSTGRES_URL`, `POSTGRES_PASSWORD` | 메인 DB | A (데이터) |
| `REDIS_URL` | 캐싱, 작업 상태 | A (데이터) |
| `CHROMA_HOST`, `CHROMA_PORT` | 벡터 DB | D (RAG) |
| `SEOUL_OPENDATA_KEY` | 서울 공공데이터 API | A (데이터) |
| `SEMAS_API_KEY` | 소상공인진흥공단 API | A (데이터) |
| `SGIS_API_KEY`, `SGIS_SECRET_KEY` | 통계지리정보 API | A (데이터) |
| `MOLIT_API_KEY` | 국토부 부동산 API | A (데이터) |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 네이버 데이터랩 | A (데이터) |
| `LANGCHAIN_API_KEY`, `LANGCHAIN_TRACING_V2` | LangSmith 트레이싱 | B (Agent) |
| `DEBUG`, `DEMO_MODE` | 앱 동작 모드 | 전체 |

> 새 환경변수를 추가하면 반드시 `.env.example`에도 추가하세요.

## 주요 설정 파일

| 파일 | 역할 | 수정 시 주의 |
|------|------|------------|
| `backend/src/config/settings.py` | `.env` → Pydantic Settings 매핑 | 환경변수 추가 시 여기도 필드 추가 |
| `backend/src/config/constants.py` | 비즈니스 상수 (행정동, 업종, 경쟁 반경, LLM 모델명) | 하드코딩 대신 여기서 import |
| `backend/src/config/prompts_config.py` | 프롬프트 버전 관리 (v0.1.0) | 프롬프트 수정 시 버전 올릴 것 |
| `docker-compose.yml` | 서비스 구성 (5개 컨테이너) | 팀 협의 후 수정 |
| `pyproject.toml` | Ruff 린터 설정 + pytest 설정 | 공통 설정 — 팀 협의 |
| `frontend/.prettierrc` | 프론트엔드 포매터 설정 | E (프론트엔드)만 수정 |
| `frontend/.eslintrc.cjs` | 프론트엔드 린터 설정 | E (프론트엔드)만 수정 |
