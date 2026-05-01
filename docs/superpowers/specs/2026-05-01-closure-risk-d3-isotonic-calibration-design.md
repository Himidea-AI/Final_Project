# 폐업 위험도 모델 D-3 (isotonic calibration) — Design Spec

> **상태**: 사용자 승인 (2026-05-01).
> **선행 작업**: E/C/D/A ✅ (production: A-3 commit 2461362, test AUC 0.6139).

## Goal

Ensemble proba 의 isotonic regression calibration. 분포 [0.15, 0.55] 에 좁게 갇힌 문제 해결 — proba 가 actual frequency 와 매칭되도록 monotonic 변환. AUC 변화 X (rank 보존), Brier score 개선 기대.

## Background

A-3 후 production:
- test AUC 0.6139 ⭐
- proba 분포 여전히 좁음 (`metrics.json` calibration n_per_bin: 0.15~0.55 에 몰림)
- Brier 0.191 — confidence 이 의미 잃은 상태 (모든 sample 이 비슷한 proba)

학술 표준: Niculescu-Mizil & Caruana (2005) — proba calibration 으로 confidence 회복. Isotonic regression 이 sigmoid (Platt) 보다 유연.

## Architecture

```
train.py 의 evaluate 단계:
    ensemble_val_proba 계산 후 →
    isotonic_calibrator.fit(ensemble_val_proba, aligned_y_val) →
    weights/ensemble_calibrator.pkl 저장 →
    threshold fit 은 calibrated_val_proba 기준으로 (consistency)

predict.py 의 predict():
    raw ensemble proba 계산 →
    calibrator.transform(raw) → calibrated proba →
    _classify(calibrated) (threshold fit 도 calibrated 기준)
```

## Components

### 1. `train.py` calibrator fit + 저장

```python
from sklearn.isotonic import IsotonicRegression

# evaluate 단계, ensemble_val_proba 계산 직후
calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
if len(val_common) >= 10:
    calibrator.fit(ensemble_val_proba, aligned_y_val)
    calibrated_val_proba = calibrator.transform(ensemble_val_proba)
    calibrated_test_proba = calibrator.transform(ensemble_test_proba) if len(test_common) > 0 else ensemble_test_proba
    logger.info("isotonic calibrator fit — val raw range [%.3f, %.3f] → calibrated [%.3f, %.3f]",
                ensemble_val_proba.min(), ensemble_val_proba.max(),
                calibrated_val_proba.min(), calibrated_val_proba.max())
else:
    calibrator = None
    calibrated_val_proba = ensemble_val_proba
    calibrated_test_proba = ensemble_test_proba
    logger.warning("calibration skip — val sample %d < 10", len(val_common))

# 저장
import pickle
with open(WEIGHTS_DIR / "ensemble_calibrator.pkl", "wb") as f:
    pickle.dump(calibrator, f)
```

### 2. `train.py` threshold fit (calibrated 기준)

기존 `np.quantile(ensemble_val_proba, ...)` → `np.quantile(calibrated_val_proba, ...)` 로 교체. 일관성 — production 도 calibrated proba 사용.

evaluate / metrics 도 calibrated proba 기준 (정직한 metric).

### 3. `predict.py` 의 calibrator 적용

`_load_models()` 가 calibrator load (없으면 None fallback):
```python
cal_path = WEIGHTS_DIR / "ensemble_calibrator.pkl"
calibrator = None
if cal_path.exists():
    with open(cal_path, "rb") as f:
        calibrator = pickle.load(f)
```

`predict()` 의 risk_score 계산 직후:
```python
raw_score = w_lgbm * p_lgbm + w_tcn * p_tcn
if calibrator is not None:
    risk_score = float(calibrator.transform([raw_score])[0])
else:
    risk_score = raw_score
risk_score = round(risk_score, 4)
```

`predict_topk` 는 자동 통과 (predict() 호출 chain).

### 4. metrics.json schema 확장

```json
{
  ...,
  "thresholds": { ... },
  "calibration_info": {
    "method": "isotonic",
    "val_raw_range": [0.18, 0.55],
    "val_calibrated_range": [0.05, 0.78]
  }
}
```

## Risks

| Risk | Mitigation |
|---|---|
| AUC 변화 (monotonic 보장 X 가능) | IsotonicRegression 은 monotonic — AUC 보존 보장 |
| 작은 val set 으로 calibrator overfit | val ≥ 10 가드. fit 실패 시 None fallback |
| calibrator pkl 미존재 시 production 추론 | predict() 가 None fallback (raw proba 사용) |
| 학습 시점 calibrated proba ↔ 추론 시점 mismatch | `transform` 일관 적용 + threshold 도 calibrated 기준 |

## Testing

`tests/test_closure_risk_calibration.py` (~5 test):
1. `test_calibrator_preserves_ranking` — fit/transform 후 sorted order 동일 (AUC 보장)
2. `test_calibrator_clips_out_of_bounds` — train 범위 외 input 도 [0, 1] clip
3. `test_calibrator_loaded_from_pkl` — predict.py 가 pkl 자동 load
4. `test_predict_with_calibrator_in_range` — calibrated risk_score 가 [0, 1]
5. `test_predict_works_without_calibrator_pkl` — pkl 미존재 → graceful (raw 사용)

## Tasks (5)

| # | 내용 | 작업량 |
|---|---|---|
| T1 | `train.py` calibrator fit + save + threshold/evaluate 갱신 + 2 unit test | 2h |
| T2 | `predict.py` calibrator load + apply + 3 test | 1.5h |
| T3 | retrain + Brier 비교 + 의사결정 (keep/rollback) | 0.5h |
| T4 | 회고 | 0.5h |

총 ~4.5h. T1+T2 결합 가능 (단일 commit 으로 묶음).

## Out of Scope

- Platt scaling 비교 (별도 spec)
- LGBM/TCN 별도 calibration (post-ensemble 채택)
- Cross-validated calibration (val 단일 fit)
- B-3, B-4 (별도 spec)
