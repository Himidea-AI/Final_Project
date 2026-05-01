# 프로젝트 전체 구조 핵심 정리

작성 기준: 2026-04-29

## 1. 프로젝트 한 줄 정의

본 프로젝트는 **프론트엔드에서 출점 조건을 입력받고, 백엔드가 상권분석 워크플로우를 실행한 뒤, ML/RAG/DB 분석 결과를 대시보드로 제공하는 마포구 프랜차이즈 출점 시뮬레이터**이다.

## 2. 전체 흐름

```text
사용자
  -> Frontend
  -> Backend API
  -> LangGraph Agents
  -> Database / RAG / ML Models
  -> 분석 결과 JSON
  -> Dashboard
```

## 3. 핵심 디렉토리

| 경로 | 역할 |
|---|---|
| `frontend/` | React 기반 사용자 화면 |
| `backend/` | FastAPI 기반 API 서버 및 AI 분석 실행 |
| `models/` | TCN, 폐업위험도, BEP, SHAP 등 ML 모델 |
| `data/` | 원본/가공 데이터 |
| `validation/` | 모델 검증, 백테스트, 시나리오 비교 |
| `tests/`, `backend/tests/` | 테스트 코드 |
| `docs/` | 아키텍처, API, 데이터, 분석 문서 |
| `docker-compose.yml` | PostgreSQL, Redis, 백엔드, 프론트 실행 구성 |

## 4. 프론트엔드 구조

| 경로 | 역할 |
|---|---|
| `frontend/src/pages/` | 화면 단위 페이지 |
| `frontend/src/components/` | 재사용 UI 컴포넌트 |
| `frontend/src/api/` | 백엔드 API 호출 |
| `frontend/src/types/` | 백엔드 응답과 맞춘 TypeScript 타입 |
| `frontend/src/stores/` | 프론트 상태 관리 |

프론트엔드는 사용자의 출점 조건을 입력받아 백엔드 API를 호출하고, 응답받은 `SimulationOutput`을 차트, 지도, 리포트 형태로 보여준다.

## 5. 백엔드 구조

| 경로 | 역할 |
|---|---|
| `backend/src/main.py` | FastAPI 진입점 |
| `backend/src/api/` | 기능별 API 라우터 |
| `backend/src/agents/` | LangGraph 분석 워크플로우 |
| `backend/src/agents/nodes/` | 상권, 인구, 법률, 경쟁, 트렌드 분석 노드 |
| `backend/src/schemas/` | API 입력/출력 스키마 |
| `backend/src/services/` | 외부 API, 인증, 데이터 조회 서비스 |
| `backend/src/database/` | PostgreSQL, Redis, pgvector 연결 |
| `backend/src/simulation/` | ABM 행동 시뮬레이션 |

백엔드의 핵심 흐름은 `main.py -> graph.py -> nodes -> models/interface.py -> SimulationOutput`이다.

## 6. 모델 구조

| 경로 | 역할 |
|---|---|
| `models/tcn_forecast/` | TCN 기반 매출 예측 |
| `models/closure_risk/` | 폐업위험도 예측 |
| `models/revenue_predictor/` | 폐업률 및 BEP 계산 |
| `models/explainability/` | SHAP 설명 및 시나리오 변환 |
| `models/customer_revenue/` | 타겟 고객군 매출 분석 |
| `models/living_pop_forecast/` | 유동인구 피크 시간 예측 |
| `models/emerging_district/` | 신흥 상권 신호 감지 |
| `models/interface.py` | 모델 결과 통합 진입점 |

현재 운영 기준의 핵심 예측 모델은 **TCN**이며, LSTM은 레거시 비교용이다.

## 7. 데이터 저장소

| 저장소 | 역할 |
|---|---|
| PostgreSQL | 매출, 점포, 인구, 임대료, 브랜드, 사용자, 분석 이력 저장 |
| Redis | 캐시, rate limit, 중복 요청 방지 |
| pgvector | 법률 문서 RAG 검색 |
| CSV/Data files | 전처리 및 모델 학습용 데이터 |

## 8. 핵심 실행 시나리오

```text
1. 사용자가 프론트에서 브랜드, 업종, 후보 행정동 입력
2. 프론트가 백엔드 `/simulate` 호출
3. 백엔드가 LangGraph 분석 실행
4. 각 Agent가 DB/RAG/외부 API/ML 모델 호출
5. TCN 매출 예측, 폐업률, BEP, 법률 리스크, 경쟁 분석 생성
6. 백엔드가 결과를 `SimulationOutput`으로 반환
7. 프론트가 대시보드에 분석 결과 표시
```

## 9. 반드시 기억할 점

- `frontend/`는 화면과 사용자 경험을 담당한다.
- `backend/`는 API와 분석 실행을 담당한다.
- `models/`는 예측과 설명 가능성 결과를 만든다.
- `data/`와 `validation/`은 모델 학습과 검증 기반이다.
- 프로젝트의 중심 연결은 **Frontend -> Backend -> LangGraph -> Models/DB/RAG -> Dashboard**이다.
