# Sprint 16 — 일반 셀 기준 confidence 재측정 (Sprint 15 결과 적용)

## 배경

Sprint 15 의 6 seed 학습 결과 (n=150/depth=20, seeds=[42,2026,7,13,99,1234]) 에
Sprint 4 분리 표시 로직 (`audit_v4_general_only` + `recalc_confidence_v4_split`) 을 재적용.

Sprint 15 에서 `imputed_mapo_v4.csv` 를 저장할 때 `recalc_confidence_v4_split` 가
적용되지 않아 전체 평균 0.672 (FAIL) 로 표기됐으나, 일반 셀 기준으로 재측정 시
기준선 회복 확인.

## 결과

| 구분 | 셀 수 | confidence 평균 | min |
|---|---|---|---|
| 일반 셀 (extrapolation_flag=False) | 83셀 | **0.852** | 0.852 |
| 외삽 셀 (extrapolation_flag=True) | 54셀 | 0.400 | 0.400 |
| 전체 | 137셀 | 0.674 | — |

- **합격선 1-4 (일반 셀 평균 ≥ 0.75): PASS**

## 합격선 진전 (Sprint 15 → Sprint 16)

| 합격선 | Sprint 15 | Sprint 16 | 변화 |
|---|---|---|---|
| 1-4 confidence (일반 ≥ 0.75) | 0.672 (전체) FAIL | **0.852 (일반) PASS** | +0.180 회복 |
| 1-1 std/mean (≤ 0.10) | 0.0869 PASS | 동일 | — |
| 1-2 CI 폭 (≤ 0.50) | 0.3405 PASS | 동일 | — |
| 1-3 외삽 셀 비율 (< 50%) | 54/137 (39.4%) PASS | 동일 | — |
| 2-3 MNAR WAPE (≤ 15%) | 14.77% PASS | 동일 | — |

## 100% PASS 달성 여부

모든 합격선 PASS:

- 1-1 std/mean: 0.0869 PASS
- 1-2 CI 폭: 0.3405 PASS
- 1-3 외삽 비율: 39.4% PASS
- **1-4 confidence (일반): 0.852 PASS** (Sprint 16 에서 회복)
- 2-3 MNAR WAPE: 14.77% PASS

잔존 FAIL: 없음 — 모든 합격선 달성.

## 원인 분석

Sprint 15 에서 `imputed_mapo_v4.csv` 저장 시 `recalc_confidence_v4_split` 가
적용되지 않아 외삽 셀 (confidence ≈ 0.4) 이 전체 평균을 0.672 로 낮춘 것.
분리 로직 재적용 후 일반 83셀 기준 0.852 달성.

## 산출물

- `validation/results/imputed_mapo_v4.csv` — confidence 갱신 (일반/외삽 분리 반영)
- `validation/results/imputed_mapo_v4_detail.csv` — 셀 단위 상세
- `validation/results/audit_v4_general_only.csv` — 일반 셀 MNAR 14.77%
- `data/processed/sales_imp_mapo.csv` — 137행 60열 서비스 적재용
