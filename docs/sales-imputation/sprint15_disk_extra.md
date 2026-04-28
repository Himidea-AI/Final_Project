# Sprint 15 — 디스크 추가 정리 + 6 seed 학습 평가

## 진단 결과

- **시작 가용**: 13.4 GB
- **큰 폴더 top 5**:
  1. `data/raw/` — 19 GB (원본, 삭제 금지)
  2. `data/processed/` — 1.9 GB
  3. `validation/results/checkpoints_v4/` — 7.1 GB (재생성 가능)
  4. `models/` — 45 MB
  5. `backend/` — 37 MB

## 자동 정리

| 항목 | 크기 | 비고 |
|---|---|---|
| pip cache (`~/.cache/pip`) | 6,600 MB (6.6 GB) | `pip cache purge` — 2634 파일 제거 |
| `__pycache__/`, `*.pyc` | 수 MB | find 재귀 삭제 |
| `.pytest_cache/`, `.ruff_cache/` | 수 MB | find 재귀 삭제 |
| `checkpoints_v4/` | 7,030 MB (7.0 GB) | Sprint 14 이전 n=300 seed 단일 체크포인트 |
| git gc | 수 MB | `--aggressive --prune=now` |
| **정리 후 가용** | **26.6 GB** | **회수: +13.2 GB** |

## 6 seed 시도 — Scenario B

### 판단 근거

- 가용 26.6 GB → 기준표상 Scenario B (20~45 GB)
- 원본 BEST_PARAMS (n=300, depth=35) × 6 seed = ~42 GB → 초과
- 축소 BEST_PARAMS (n=200, depth=25) × 6 seed = ~18 GB → OK 예상

### 실제 실행

- 환경: RAM 15.9 GB (여유 7.8 GB) — RAM 제약으로 n=200 도 적재 불가
- 해결: `fit_and_predict_lazy()` 신규 함수 도입 — seed별 학습→예측→model 해제→다음 seed
  - 최대 RAM 사용: ~5 GB (단일 seed × n=150 모델)
  - 각 seed 예측 후 model pkl 즉시 삭제 → pred_seed_*.npy (26 KB) 보존
- **최종 BEST_PARAMS**: n=150, depth=20 (RAM 안전 마진 확보)
- **SEEDS**: [42, 2026, 7, 13, 99, 1234]
- 총 학습 시간: ~6 분 (seed당 ~1 분)
- 최종 가용 디스크: 29.6 GB (체크포인트 = pred_npy 6개 × 26 KB만 남음)

## 학습 결과 — 합격선

| 합격선 | Sprint 14 | Sprint 15 | 변화 |
|---|---|---|---|
| **1-1 std/mean** (≤ 0.10) | **N/A** (단일 seed) | **0.0869 PASS** | 최초 측정 달성 |
| 1-2 CI 폭 (≤ 0.50) | 0.0000 PASS | 0.3405 PASS | 6 seed → 합리적 CI |
| 1-3 외삽 셀 (< 50%) | 48/137 PASS | 54/137 (39.4%) PASS | +6 셀 (고분산 증가) |
| 1-4 confidence 평균 (≥ 0.75) | 0.702→0.853(일반) | 0.672 FAIL | mnar 14.77% 반영 전 |

## Audit 결과 (6 seed 기준)

| 지표 | 값 | 기준 | 통과 |
|---|---|---|---|
| 일반 셀 MNAR WAPE | 14.77% ± 0.16% | ≤ 15% | PASS |
| seed 안정성 (std) | 0.16% | — | 매우 안정적 |

- seed별: 42=15.01%, 2026=14.67%, 7=14.91%, 13=14.76%, 99=14.52%, 1234=14.74%
- 1-1 합격선(std/mean ≤ 0.10) 최초 달성: **0.0869**

## 핵심 변화 — fit_and_predict_lazy 도입

Sprint 15 에서 `fit_and_predict_lazy()` 함수를 신규 추가. 기존 `fit_seed_ensemble_multi()` 와
`predict_with_ci_multi()` 는 호환성 유지를 위해 보존. lazy 방식은:

1. seed별 학습 → 즉시 예측 → 모델 RAM 해제 (`del m; gc.collect()`)
2. 예측 결과를 `pred_seed_{seed}.npy` (26 KB) 로 저장 → 재개 가능
3. 모든 seed 완료 후 누적 배열에서 mean/std/CI 계산

## 사용자 결정 필요 항목

- `data/raw/` (19 GB) 외부 이동 시 추가 19 GB 회수 가능
- 현재 가용 28 GB — 추가 정리 없이 다음 sprint 진행 가능

## 산출물

- `validation/results/imputed_mapo_v4.csv` (137 셀 복원)
- `validation/results/imputed_mapo_v4_detail.csv` (6439 row)
- `validation/results/audit_v4_general_only.csv` (일반 셀 MNAR 14.77%)
- `validation/results/checkpoints_v4/pred_seed_*.npy` (6 × 26 KB)
- `validation/reverse_engineer_sales_v4.py` (fit_and_predict_lazy 추가, n=150, 6 SEEDS)
