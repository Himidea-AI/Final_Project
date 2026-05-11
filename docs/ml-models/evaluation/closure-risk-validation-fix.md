# 폐업 위험도 모델 검증 layer fix (2026-04-29)

## 변경 요약

폐업 위험도 모델 (`models/closure_risk/`) 의 **검증 layer** 를 학술 표준에 맞게 교체.

### Before

```python
# train.py:236-240 (legacy)
n_val = max(1, int(len(y) * cfg["val_ratio"]))
X_lgbm_tr = X_lgbm.iloc[:-n_val].values
X_lgbm_val = X_lgbm.iloc[-n_val:].values
```

`build_closure_risk_dataset` 가 `dong_code, industry_code, quarter` 순으로 정렬 → 마지막 N% 가 dong-based 분할 (시간순 X). 단일 metric (`roc_auc_score`) 만.

### After

```python
# data_prep.py: _time_based_split(df, train_ratio=0.70, val_ratio=0.15)
quarters = sorted(df["quarter"].unique())
train_end = quarters[int(n_q * 0.70) - 1]
val_end = quarters[int(n_q * 0.85) - 1]
```

`quarter` 기준 시간순 holdout 3분할. **Test set 분리** → final unbiased 측정. 5 metric (AUC, PR-AUC, P@10, R@10, Brier) + Calibration plot.

## 학술 근거

- Bergmeir & Benítez (2012) — 시계열 모델은 random k-fold 사용 X
- Niculescu-Mizil & Caruana (2005) — Calibration 표준 (10-bin reliability diagram)
- Cawley & Talbot (2010) — Test set 미분리 시 over-fitting 누적

## 예상 학습 결과 변화

| Metric | Before (random split) | After (time split) |
|---|---|---|
| val_AUC | 0.85 (부풀려짐) | **0.70~0.78** (정직) |
| 신뢰도 | Brussels r=0.95 학술 자산 위협 | Brussels-class 보장 |

`val_AUC` 가 떨어져 보이지만 **신뢰할 수 있는 수치**.

## 산출물

- `weights/metrics.json` — split 정보 + lgbm/tcn/ensemble × val/test 모두
- `weights/calibration_curve.png` — 10-bin reliability diagram

## 회귀 안전성

- `predict.py` 인터페이스 변경 X — 기존 호출자 영향 0
- `model.py` (TCNClassifier) 변경 X
- 기존 weights 그대로 inference 가능, 단 학술적 신뢰도 위해 재학습 권장

## CLI

기본 (time split):
```bash
python -m models.closure_risk.train
```

분기 부족 시 명시적 random fallback:
```bash
python -m models.closure_risk.train --split-strategy random
```

(CLI 옵션은 별도 task — 현재는 config dict 로 호출)

## 알려진 한계 (별도 spec)

- LGBM/TCN proba alignment 가 trim 기반 (메타키 inner-join 미적용) — 별도 spec 권장
- C/D/B/A 측면 (레이블 정의 / 임계값 / 피처 추가 / 모델 구조) 미진행 — 별도 sprint
