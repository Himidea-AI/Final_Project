# ML Models — 정리 인덱스

흩어져있던 머신러닝 모델 문서를 한 폴더로 통합. 2026-05-09 정리.

## 구조

```
docs/ml-models/
├── README.md                      ← 이 파일
├── model-adoption-roadmap.md      ← 통합 로드맵 (LLM-ABM 패턴 차용)
│
├── timeseries/                    유동인구·시계열 예측 (D 모델 계열)
│   ├── gru-model-report.md
│   ├── lstm-model-report.md
│   ├── tcn-model-report.md
│   └── model-comparison-report.md  (LSTM vs GRU vs TCN 통합 비교)
│
├── evaluation/                    실용 가치·검증 리포트
│   ├── closure-risk-validation-fix.md     (B 모델: 폐업 위험)
│   ├── customer-revenue-evaluation-2026-04-29.md  (C 모델: 고객 매출)
│   ├── living-pop-daily-evaluation-2026-04-29.md  (D 모델: 일별 평가)
│   ├── living-pop-forecast-v2-report.md           (D v1 vs v2)
│   └── living-pop-forecast-v2-vs-v3-report.md     (D v2 vs v3)
│
├── imputation/                    결측치 보간 / TCN imputation
│   ├── tcn-imputed-comparison-report.md
│   ├── tcn-imputed-comparison-test-cases.md
│   ├── sales-model-comparison.md         (5 모델 v1/v2/v3 비교)
│   ├── sales-sota-comparison.md          (SOTA imputation 라이브러리 검증)
│   └── sales-step2-transfer-learning.md  (Seoul-wide transfer)
│
└── competition/                   경쟁 분석 모델
    └── competition-model.md       (3-Layer 경쟁 분석 프레임워크)
```

## 모델 매핑 (코드 ↔ 문서)

| 코드 위치 | 모델명 | 주요 문서 |
|----------|--------|----------|
| `models/closure_risk/` | B — LightGBM + TCN 폐업 위험 | evaluation/closure-risk-validation-fix.md |
| `models/customer_revenue/` | C — MLP 고객 매출 기여 | evaluation/customer-revenue-evaluation-2026-04-29.md |
| `models/living_pop_forecast/` | D — TCN 24h 유동인구 | evaluation/living-pop-* 시리즈 |
| `models/lstm_forecast/` | LSTM 분기 매출 | timeseries/lstm-model-report.md |
| `models/gru_forecast/` | GRU 분기 매출 | timeseries/gru-model-report.md |
| `models/tcn_forecast/` | TCN 분기 매출 | timeseries/tcn-model-report.md |
| `models/emerging_district/` | 신흥 상권 autoencoder | (별도 문서 미정리) |
| `models/explainability/` | SHAP 설명 | (별도 문서 미정리) |

## 외부 참조

- 회고: `docs/retrospective/2026-04-30.md`, `2026-05-01-{a,b,b3,d,d3}-layer.md` (closure_risk sprint별)
- 실행 plan: `docs/superpowers/plans/2026-04-29-cde-models-utility-plan.md`
- 데이터 파이프라인: `docs/architecture/` (옮기지 않은 비-모델 문서)

## 정리 정책

- ABM 시뮬 자체 (페르소나·정책·시나리오)는 `docs/abm-simulation/` 유지 — 시뮬 시스템 문서
- 모델 정의·평가·비교만 본 폴더로 이동
- 회고는 `docs/retrospective/` 에 그대로 (시점별 기록)
- superpowers plans/specs는 `docs/superpowers/` 에 그대로 (워크플로우 문서)
