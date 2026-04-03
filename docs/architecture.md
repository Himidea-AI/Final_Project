# 프로젝트 아키텍처

## 디렉토리 구조

```
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py                  # FastAPI 앱 진입점 (라우트 등록)
│       ├── agents/                  # LangGraph 워크플로우
│       │   ├── graph.py             # StateGraph 컴파일
│       │   ├── state.py             # AgentState 정의
│       │   ├── edges.py             # 엣지 로직
│       │   └── nodes/               # 8개 분석 노드 + supervisor
│       │       ├── commercial.py    # 상권 분석
│       │       ├── population.py    # 유동/주거 인구
│       │       ├── demographics.py  # 인구통계
│       │       ├── cost.py          # 임대료/투자비용
│       │       ├── competition.py   # 직접/간접 경쟁
│       │       ├── trend.py         # 트렌드 (SNS/시장)
│       │       ├── legal.py         # 법률 리스크 (RAG)
│       │       ├── report.py        # 최종 리포트
│       │       └── supervisor.py    # 재분석 판단
│       ├── chains/                  # RAG & 프롬프트 체인
│       │   ├── prompts.py           # 노드별 LLM 프롬프트
│       │   └── retriever.py         # ChromaDB RAG 리트리버
│       ├── config/                  # 설정 & 상수 (공통 — 단독 수정 금지)
│       │   ├── settings.py          # Pydantic Settings (.env 로드)
│       │   ├── constants.py         # 비즈니스 상수 (행정동, 업종, 경쟁 반경)
│       │   └── prompts_config.py    # 프롬프트 버전 관리 (v0.1.0)
│       ├── database/                # DB 클라이언트
│       │   ├── postgres.py          # PostgreSQL
│       │   ├── redis_client.py      # Redis 캐싱
│       │   └── vector_db.py         # ChromaDB 벡터 DB
│       ├── schemas/                 # Pydantic 데이터 모델 (API 계약)
│       │   ├── simulation_input.py  # SimulationInput, ExistingStoreInput
│       │   ├── simulation_output.py # SimulationOutput, MonthlyProjection
│       │   ├── competition_models.py
│       │   ├── district_data.py
│       │   └── report_models.py
│       └── services/                # 외부 API 연동
│           ├── base_client.py       # BaseAPIClient (retry 로직)
│           ├── seoul_opendata.py    # 서울 공공데이터
│           ├── semas_api.py         # 소상공인진흥공단
│           ├── sgis_api.py          # 통계지리정보
│           ├── molit_api.py         # 국토부 부동산
│           ├── ftc_franchise.py     # 공정위 가맹사업
│           ├── golmok_api.py        # 골목상권
│           └── sns_trend.py         # 네이버 데이터랩
├── frontend/
│   ├── src/
│   │   ├── main.tsx                 # React 진입점
│   │   ├── App.tsx                  # 라우트 정의 (6개 페이지)
│   │   ├── api/client.ts            # Axios HTTP 클라이언트 (/api 프록시)
│   │   ├── components/              # 재사용 UI 컴포넌트
│   │   │   ├── Layout.tsx           # 사이드바 + 헤더
│   │   │   ├── ChartComponent.tsx   # Recharts 시각화
│   │   │   ├── MapComponent.tsx     # React-Leaflet 지도
│   │   │   └── ScoreCard.tsx        # 정보 카드
│   │   ├── pages/                   # 페이지 컴포넌트
│   │   │   ├── InputPage.tsx        # 조건 입력 폼
│   │   │   ├── MapView.tsx          # 행정동 히트맵
│   │   │   ├── ReportView.tsx       # 상세 리포트
│   │   │   ├── BepSimulator.tsx     # 손익분기점 분석
│   │   │   ├── Comparison.tsx       # 행정동 비교
│   │   │   └── Cannibalization.tsx  # 카니발리제이션
│   │   ├── types/index.ts           # TypeScript 인터페이스
│   │   └── assets/mapo_geo.json     # 마포구 GeoJSON
│   ├── .prettierrc
│   ├── .eslintrc.cjs
│   └── package.json
├── models/                          # 딥러닝 모델
├── data/                            # 데이터 (raw/는 수정 금지)
├── tests/                           # 백엔드 테스트
├── validation/                      # 검증
├── docs/                            # 문서
├── notebooks/                       # Jupyter 노트북
├── docker-compose.yml
└── .env.example
```

## 모듈 간 의존 관계

```
Frontend (React)
  └─→ Backend API (FastAPI main.py)
        ├─→ agents/graph.py (LangGraph 워크플로우 실행)
        │     ├─→ agents/nodes/* (8개 분석 노드)
        │     │     ├─→ services/* (외부 API 호출)
        │     │     ├─→ chains/* (RAG 검색, 프롬프트)
        │     │     └─→ database/* (DB 읽기/쓰기)
        │     └─→ agents/edges.py (노드 간 라우팅)
        ├─→ schemas/* (입출력 데이터 검증)
        └─→ config/* (설정, 상수)
```

- **Frontend → Backend**: `/api` 프록시를 통해 백엔드 API 호출 (Nginx 또는 Vite proxy)
- **Backend → Agents**: `POST /simulate` → `graph.py`가 LangGraph 워크플로우 실행
- **Agents → Services/Chains/DB**: 각 노드가 필요한 서비스를 직접 호출
- **Config**: 모든 백엔드 모듈이 `config/`를 참조 (단독 수정 금지)
