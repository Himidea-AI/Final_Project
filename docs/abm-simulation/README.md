# ABM Simulation & Models

마포 프랜차이즈 에이전트 기반 모델(ABM) 시뮬레이션, 딥러닝 모델, 정책 생성기 관련 문서.

## 🏗️ 시뮬레이션 아키텍처

| 파일 | 내용 |
|:-----|:-----|
| [`sim-architecture-deep-dive.md`](sim-architecture-deep-dive.md) | 시뮬레이션 엔진 내부 구조 |
| [`sim-real-gap-analysis.md`](sim-real-gap-analysis.md) | 시뮬레이션 ↔ 실데이터 gap 분석 |
| [`sim-comparison-matrix.md`](sim-comparison-matrix.md) | 버전별 비교 매트릭스 |
| [`sim-validation-progression.md`](sim-validation-progression.md) | **검증 진척 로그** (전체 실험 기록) |

## 🎨 프론트엔드 통합

| 파일 | 내용 |
|:-----|:-----|
| [`simulation-frontend-integration.md`](simulation-frontend-integration.md) | FE ↔ 시뮬레이션 API 통합 |
| [`simulation-visual-roadmap.md`](simulation-visual-roadmap.md) | 시각화 로드맵 |

## 🤖 모델 리포트

> **이동 알림 (2026-05-09)**: 머신러닝 모델 문서는 [`docs/ml-models/`](../ml-models/README.md) 로 통합 이동.
> 본 ABM 시뮬레이션 README 에는 시뮬 시스템 자체 문서만 남김.

| 카테고리 | 위치 |
|:---------|:-----|
| 시계열 모델 비교 (LSTM/GRU/TCN) | [`docs/ml-models/timeseries/`](../ml-models/timeseries/) |
| 모델 평가 리포트 (closure_risk·customer_revenue·living_pop) | [`docs/ml-models/evaluation/`](../ml-models/evaluation/) |
| 결측치 보간 / TCN imputation | [`docs/ml-models/imputation/`](../ml-models/imputation/) |
| 모델 채택 로드맵 | [`docs/ml-models/model-adoption-roadmap.md`](../ml-models/model-adoption-roadmap.md) |

## 🧩 에이전트 & 정책

| 파일 | 내용 |
|:-----|:-----|
| [`agent-weight-reference.md`](agent-weight-reference.md) | 에이전트 가중치 레퍼런스 |
| [`agent-dsl-cost-analysis.md`](agent-dsl-cost-analysis.md) | DSL 방식 비용 분석 |
| [`policy-generator-design.md`](policy-generator-design.md) | 정책 생성기 설계 |

## 🔧 프레임워크

| 파일 | 내용 |
|:-----|:-----|
| [`abm-framework-adoption-plan.md`](abm-framework-adoption-plan.md) | ABM 프레임워크 채택 계획 |
| [`abm-framework-extraction-plan.md`](abm-framework-extraction-plan.md) | 추출 계획 |
| [`langgraph-abm-integration-roadmap.md`](langgraph-abm-integration-roadmap.md) | LangGraph 통합 로드맵 |
