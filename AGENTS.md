# AGENTS.md — 마포구 프랜차이즈 상권분석 시뮬레이터

> 이 파일은 모든 AI 코딩 에이전트(Claude, Gemini, Cursor, Copilot, Antigravity, Codex 등)가 읽는 공통 규칙입니다.

## 프로젝트 개요

마포구 내 프랜차이즈 신규 출점 시뮬레이션 플랫폼. LangGraph 기반 멀티 에이전트가 상권, 인구, 경쟁, 법률 등을 분석합니다.

- 아키텍처 & 디렉토리 구조: [`docs/architecture/architecture.md`](docs/architecture/architecture.md)
- API 엔드포인트 & 스키마: [`docs/architecture/api-contract.md`](docs/architecture/api-contract.md)
- 환경변수 & 설정 파일: [`docs/architecture/env-guide.md`](docs/architecture/env-guide.md)
- 도메인 용어집: [`docs/architecture/glossary.md`](docs/architecture/glossary.md)

## 팀원별 담당 영역 (절대 준수)

### 트랙 A — 데이터 + RAG (2명)

| 역할 | 담당자 | 담당 디렉토리 |
|------|--------|-------------|
| A1 — 데이터 엔지니어 | 찬영 | `backend/src/services/`, `backend/src/database/`, `data/` |
| A2 — RAG + 법률 | 봉환 | `backend/src/chains/`, `backend/src/database/vector_db.py`, `backend/src/services/ftc_franchise.py` |

### 트랙 A-1 추가 — 딥러닝 예측 모델 (찬영 + 수지니 공동)

A1 찬영이 데이터 엔지니어링을, B2 수지니가 LSTM 모델 학습/최적화/검증을 함께 담당합니다.

| Task | 담당자 | 디렉토리 | 산출물 |
|------|--------|---------|--------|
| 서울 전체 데이터 전처리 | 찬영 (A1) | `data/pipeline/`, `data/processed/` | 사전학습용 CSV + DB 적재 |
| LSTM 매출 예측 (사전학습+파인튜닝) | 찬영 (A1) + 수지니 (B2) | `models/lstm_forecast/` | 월 예상매출 |
| 생존률/폐업률 예측 | 찬영 (A1) + 수지니 (B2) | `models/revenue_predictor/` | 생존률, BEP |
| 백테스팅 (2024년 검증) | 찬영 (A1) + 수지니 (B2) | `validation/` | 정확도 리포트 |
| 피처 엔지니어링/골목상권 데이터 | 수지니 (B2) | `validation/`, `data/processed/golmok_*` | 피처 효과 분석 |
| 예측 신뢰도 평가 | 수지니 (B2) | `validation/` | 저신뢰 조합 분류 |

### 트랙 B — AI 엔진 (2명)

| 역할 | 담당자 | 담당 디렉토리 |
|------|--------|-------------|
| B1 — LangGraph Agent | 예진 | `backend/src/agents/`, `backend/src/schemas/` |
| B2 — 시뮬레이션 + 설명 + LSTM | 수지니 | `models/explainability/`, `models/lstm_forecast/`, `models/revenue_predictor/`, `validation/` |

#### B2 세부 Task

| Task | 담당자 | 디렉토리 | 산출물 |
|------|--------|---------|--------|
| LSTM 모델 학습/최적화 | 수지니 (B2) | `models/lstm_forecast/`, `validation/` | 모델 가중치, MAPE 리포트 |
| 피처 엔지니어링 | 수지니 (B2) | `validation/`, `data/processed/golmok_*` | 골목상권 피처, 생활인구 피처 |
| 예측 결과 생성/신뢰도 | 수지니 (B2) | `validation/full_prediction_all.py` | 156개 조합 예측 + confidence |
| 12개월 시뮬레이션 | 수지니 (B2) | `models/explainability/` | 월별 시나리오 (계절성/비용 반영) |
| SHAP 분석 | 수지니 (B2) | `models/explainability/` | 피처 기여도 시각화 |
| 시나리오 비교 | 수지니 (B2) | `validation/scenario_comparison.py` | 낙관/비관/기본 시나리오 |

#### LSTM → 시뮬레이션 인터페이스

수지니가 LSTM 모델 학습/최적화와 시뮬레이션을 모두 담당합니다.
인터페이스 모듈: `models/interface.py` (`ModelOutput.generate()`)

```
LSTM 모델 (models/lstm_forecast/) — 수지니 (B2)
├── 학습/파인튜닝 (validation/train_v9.py)
├── 피처 엔지니어링 (validation/test_golmok_features.py)
├── 예측 (validation/full_prediction_all.py)
│   ├── 월 예상매출 (156개 조합)
│   ├── 생존률 + 리스크 등급
│   ├── BEP + ROI
│   └── 신뢰도 (high/low)
      ↓
models/interface.py (ModelOutput.generate) — 통합 호출 + mock fallback
      ↓
시뮬레이션 (models/explainability/) — 수지니 (B2)
├── 12개월 월별 시나리오 (계절성/비용 반영)
├── SHAP 피처 기여도 분석
└── 시각화
```

#### 현재 LSTM v9 상태

- **전체 MAPE**: 18.7% (골목상권 피처 적용 시)
- **모델 가중치**: `models/lstm_forecast/weights/finetuned_mapo_v9.pt`
- **최적 설정**: guide-density 보간 + window=4 + hidden=128 + pop_per_store
- **유효 피처**: store_franchise, floating_pop, pop_per_store_gm, store_normal, survival_5y
- **제외 조합**: 염리동 중식, 성산1동 제과 (MAPE 900%+)
- **저신뢰 조합**: 신수동 치킨/패스트푸드, 성산1동 양식, 도화동 양식, 대흥동 치킨
- **데이터**: `data/processed/golmok_*.csv` (골목상권 API 크롤링), `data/processed/living_population_dong_mapo.csv` (생활인구)

### 트랙 C — 프론트엔드 + 배포 (2명)

| 역할 | 담당자 | 담당 디렉토리 |
|------|--------|-------------|
| C1 — 프론트엔드 | 강민 | `frontend/` |
| C2 — 인프라 + PM | 혁 | Docker, Nginx, `docs/`, `tests/` |

**공통 파일** (`backend/src/config/`, `docker-compose.yml`, `.env.example`, `README.md`)은 팀 협의 후에만 수정합니다.

### 핵심 규칙

- **다른 팀원의 디렉토리에 있는 파일을 수정하지 마세요.**
- 인터페이스(스키마, API 엔드포인트)를 변경해야 할 경우 **기존 인터페이스를 유지하면서 확장**하세요.
- 기존 함수의 시그니처를 변경하면 다른 팀원의 코드가 깨집니다.

## 코드 컨벤션

### Python (Backend)

- **포매터/린터**: Ruff (설정: `pyproject.toml`, line-length=120, target=py312)
- **네이밍**: 모듈/함수 `snake_case`, 클래스 `PascalCase`, 상수 `UPPER_CASE`
- **타입 힌트**: 모든 함수에 파라미터/리턴 타입 명시
- **주석**: 도메인 용어는 한국어 주석 허용, 코드 로직 설명은 영어
- **import 순서**: stdlib → third-party → local (Ruff isort가 자동 정렬)

### TypeScript (Frontend)

- **포매터**: Prettier (설정: `frontend/.prettierrc`)
- **린터**: ESLint (설정: `frontend/.eslintrc.cjs`)
- **네이밍**: 컴포넌트/페이지 `PascalCase`, 함수/변수 `camelCase`, 타입/인터페이스 `PascalCase`
- **스타일링**: Tailwind CSS 유틸리티 클래스 사용, 인라인 스타일 금지
- **API 타입**: `src/types/index.ts`에 정의, 백엔드 스키마와 일치시킬 것

### Git (Jira 연동)

- **Jira 프로젝트 키**: `IM3`
- **브랜치 네이밍**: `IM3-<이슈번호>-<담당영역>-<설명>` (예: `IM3-28-agents-add-supervisor-retry`) — **영어만 사용 (한글 브랜치명은 push 불가)**
- **커밋 메시지**: Jira 이슈 키로 시작 (예: `IM3-28: 경쟁분석 노드 재시도 로직 추가`)
- **PR 제목**: Jira 이슈 키 포함 (예: `IM3-28: 경쟁분석 노드 재시도 로직 추가`)
- **PR**: 본인 담당 디렉토리 외 파일이 포함되면 반드시 해당 팀원 리뷰 요청

## 기술 스택 (변경 금지)

| 영역 | 스택 |
|------|------|
| Backend | FastAPI + Pydantic v2 + SQLAlchemy |
| AI/Agent | LangChain + LangGraph + Anthropic SDK |
| RAG | ChromaDB + OpenAI Embeddings |
| Deep Learning | PyTorch + scikit-learn |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Database | PostgreSQL 16 + Redis 7 + ChromaDB |

## 파일 생성/수정 규칙

1. **새 파일 생성 시** 해당 디렉토리의 `__init__.py` 또는 `index.ts`에 export 추가
2. **새 의존성 추가 시** `requirements.txt` 또는 `package.json`에 버전 명시
3. **환경변수 추가 시** `.env.example`에 반드시 추가
4. **API 엔드포인트 추가/변경 시** `backend/src/main.py` 라우트 등록 확인
5. **README.md, docker-compose.yml** 등 공통 파일은 단독 수정 금지

## 에러 핸들링

- 외부 API 호출 실패 시 `base_client.py`의 retry 로직 활용, 직접 try/except 남발 금지

## 테스트

- 테스트 파일 위치: `tests/` (백엔드), `frontend/` 내 (프론트엔드)
- **본인 담당 코드의 테스트는 본인이 작성** (`tests/` 디렉토리 내 본인 관련 테스트 파일 수정 가능)
- 새 기능 추가 시 최소 1개 이상의 테스트 작성
- 테스트 함수명은 `test_<기능>_<시나리오>` 형식으로 작성

## 주의사항

- `.env` 파일을 절대 커밋하지 마세요
- `data/raw/` 디렉토리의 원본 데이터를 수정하지 마세요
- 모델 가중치 파일(`.pt`, `.pth`, `.onnx`)은 커밋하지 마세요
- LLM 모델명은 `backend/src/config/constants.py`에서 관리합니다. 하드코딩 금지.
