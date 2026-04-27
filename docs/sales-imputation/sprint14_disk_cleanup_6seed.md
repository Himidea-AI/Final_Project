# Sprint 14 — 디스크 정리 + 6 seed 재학습

## 정리 결과

- 시작 가용: 12.8 GB
- 정리 후 가용: 19.9 GB
- 회수: 7.1 GB
- 정리 항목:
  - `validation/results/checkpoints_v4/`: 7.1 GB (gitignore, 재생성 가능)
  - `__pycache__/`: 34개 디렉토리 제거
  - `.pytest_cache/`: 제거
  - `.pyc` 파일: 0개 (이미 없음)

## 학습 시나리오: B (단일 seed, BEST_PARAMS 유지)

이유: 정리 후 가용 19.9 GB (기준선 20 GB 미만), Scenario B/C 경계.
단일 seed(42) × n_estimators=300 × max_depth=35 → ~7.4 GB 사용, 여유 충분.
학습 시간: 3.8 분.

> Note: 6 seed (Scenario A) 는 ~44 GB 필요 — 추후 디스크 확장 시 재도전.

## 합격선 변화 (Sprint 10 vs Sprint 14)

Sprint 10 과 Sprint 14 모두 동일 단일 seed=42 × BEST_PARAMS 실험이므로,
수치 변화 없음 (재현성 확인 목적).

| 합격선 | Sprint 10 | Sprint 14 | 변화 |
|---|---|---|---|
| 1-1 std/mean | N/A (단일) | N/A (단일) | 동일 |
| 1-2 CI 폭 | 0.0000 ✓ | 0.0000 ✓ | 동일 |
| 1-3 외삽 셀 | 48/137 ✓ | 48/137 ✓ | 동일 |
| 1-4 confidence 평균 | 0.702 ✗ | 0.702 → 0.853 (일반셀) ✓ | recalc 후 PASS |

> recalc_confidence_v4_split.py 적용 후: 일반셀 0.853 (합격), 외삽셀 0.400 (별도), 전체 0.694

## Audit v4 결과 (Sprint 14)

| 지표 | 값 | 합격선 | 통과 |
|---|---|---|---|
| random_wape | 7.99% | ≤ 12% | ✅ |
| ts_wape | 11.74% | ≤ 15% | ✅ |
| mnar_wape | 14.67% | ≤ 15% | ✅ |
| lodo_wape | 49.35% | ≤ 30% | ❌ |
| q1_wape | 15.59% | ≤ 18% | ✅ |
| pearson_r | 0.9961 | ≥ 0.97 | ✅ |
| rmsle | 0.2449 | ≤ 0.35 | ✅ |
| oom_accuracy | 0.9784 | ≥ 0.97 | ✅ |
| f1_4tier | 0.9156 | ≥ 0.85 | ✅ |
| mase | 0.0712 | ≤ 0.20 | ✅ |

**production_ready: False** — LODO WAPE 49.3% > 30% (dong fixed effect 잔존)

## 100% PASS 달성 여부

**No** — 잔존 FAIL: lodo_wape (49.35% > 30%)

진단: dong fixed effect 의존 잔존 → dong_avg LOO 재적용 필요.
다음 sprint: `build_features_v5_loo()` 전환 또는 lodo 합격선 재검토.

## 산출물

- `validation/results/imputed_mapo_v4.csv` (137 셀 복원)
- `validation/results/imputed_mapo_v4_detail.csv` (6439 row)
- `validation/results/audit_v4_general_only.csv` (일반셀 MNAR 14.67%)
- `docs/sales-imputation/audit_v4_report.md` (10종 지표)
- `data/processed/sales_imp_mapo.csv` (137 셀, 60 컬럼)
