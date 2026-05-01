# 백엔드 구조 핵심 보고서

작성 기준: 2026-04-29

## 1. 핵심 정의

본 백엔드는 **FastAPI가 요청을 받고, LangGraph가 분석 흐름을 조율하며, DB/RAG/ML 결과를 통합해 프론트엔드용 `SimulationOutput` JSON으로 반환하는 구조**이다.

```text
Frontend
  -> FastAPI API
  -> LangGraph Workflow
  -> DB / RAG / ML Models
  -> SimulationOutput
```

## 2. 핵심 실행 흐름

대표 엔드포인트는 `POST /simulate`이다.

```text
1. Frontend가 출점 조건 전송
2. main.py가 SimulationInput 검증
3. _run_pipeline()이 AgentState 생성
4. LangGraph가 분석 노드 실행
5. ML/RAG/DB 결과를 통합
6. map_state_to_simulation_output()이 응답 JSON 생성
```

즉, 백엔드의 중심 흐름은 다음 네 파일로 이해할 수 있다.

| 파일 | 핵심 역할 |
|---|---|
| `backend/src/main.py` | API 진입점, `/simulate` 실행, 응답 변환 |
| `backend/src/agents/graph.py` | LangGraph 분석 순서 정의 |
| `backend/src/schemas/` | 요청/응답 데이터 계약 |
| `models/interface.py` | TCN, 폐업률, BEP 등 ML 결과 통합 |

## 3. 계층별 역할

| 계층 | 경로 | 역할 |
|---|---|---|
| API | `backend/src/main.py`, `backend/src/api/` | 요청 수신, 검증, 응답 반환 |
| Schema | `backend/src/schemas/` | 입력/출력 구조 정의 |
| Agent | `backend/src/agents/` | 분석 워크플로우 조율 |
| Node | `backend/src/agents/nodes/` | 상권, 인구, 법률, 경쟁, 트렌드 분석 |
| Service | `backend/src/services/` | 외부 API, 브랜드, 인증, 데이터 조회 |
| Database | `backend/src/database/` | PostgreSQL, Redis, pgvector 연결 |
| ML | `models/` | TCN 매출 예측, 폐업위험도, BEP, SHAP |

## 4. LangGraph 분석 순서

```text
operational_fit
  -> ranking_phase
  -> llm_analysis_phase
  -> ml_prediction_phase
  -> synthesis
```

| 단계 | 역할 |
|---|---|
| `operational_fit` | 입지 적합도 계산 |
| `ranking_phase` | 후보 동 점수화 및 추천 동 선정 |
| `llm_analysis_phase` | 상권, 인구, 법률, 트렌드, 경쟁 분석 병렬 실행 |
| `ml_prediction_phase` | TCN 매출 예측, 폐업률, BEP, SHAP 실행 |
| `synthesis` | 전체 분석 결과를 최종 보고서로 종합 |

## 5. 주요 데이터 흐름

| 저장소/모델 | 역할 |
|---|---|
| PostgreSQL | 매출, 점포, 인구, 임대료, 브랜드, 사용자, 이력 저장 |
| Redis | rate limit, 캐시, 중복 요청 방지 |
| pgvector | 법률 문서 RAG 검색 |
| `ModelOutput.generate()` | ML 모델 결과 통합 |

ML 결과는 주로 다음 항목으로 반환된다.

| 결과 | 의미 |
|---|---|
| `revenue_forecast` | TCN 기반 매출 예측 |
| `closure_rate` | 최근 실측 기반 폐업률 |
| `closure_risk` | LightGBM + TCNClassifier 기반 폐업위험도 |
| `bep` | 손익분기점 계산 |
| `shap_result` | 예측 근거 설명 |

## 6. 주요 API

| API | 역할 |
|---|---|
| `POST /simulate` | 전체 분석 실행 |
| `POST /analyze` | 분석 실행 후 `{status, data}` 형태로 반환 |
| `POST /analyze/quick` | LLM 없이 빠른 입지 랭킹 |
| `POST /predict` | 선택 동에 대한 ML 예측만 실행 |
| `POST /simulate-abm` | ABM 행동 시뮬레이션 실행 |
| `GET /health` | 서버 상태 확인 |

## 7. 반드시 기억할 점

- 백엔드 핵심은 `main.py -> graph.py -> nodes -> models/interface.py -> SimulationOutput` 흐름이다.
- 프론트엔드는 백엔드 내부 구조를 직접 알 필요 없이 `SimulationOutput`만 사용한다.
- 현재 예측 모델의 중심은 **TCN**이다.
- `models/lstm_forecast/`는 현재 운영 핵심이 아니라 레거시 비교용이다.
- 법률 분석은 pgvector 검색 결과를 LLM이 구조화하는 RAG 방식이다.
