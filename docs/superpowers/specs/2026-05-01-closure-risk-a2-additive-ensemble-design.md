# 폐업 위험도 모델 A-2 additive ensemble — Design Spec

> **상태**: 사용자 승인 (2026-05-01).
> **선행**: B-3 KEEP (production: commit 1b171cc, test AUC 0.6149).

## Goal

A-3 의 industry_prior_pred 를 **feature input** + **additive ensemble** 둘 다 사용. final risk_score = `w_dong * (LGBM/TCN ensemble) + w_industry * industry_prior_pred`. val AUC 기반 weight fit.

## Background

A-3: industry_prior_pred 를 LGBM 의 feature 로 사용 → test AUC 0.6149.
B-3: dong residual feature 추가 → marginal +0.001.

다음 sprint 후보 중 가장 distinct = **additive ensemble** (구조 변경, feature 추가 X). 가설:
- LGBM 이 implicit 으로 학습한 industry signal 외에, industry_prior_pred 의 explicit additive 신호가 ranking 개선
- 또는: feature 와 additive 가 redundant → AUC 변화 X 또는 degradation (B-1 패턴)

## Design

### 1. Additive weight fit (val 기반)

train.py 의 ensemble 계산 직후:
```python
# val_common keys 의 industry_prior_pred lookup
industry_prior_val_aligned = np.array([
    df_labeled.loc[
        (df_labeled["dong_code"].astype(str) == k[0])
        & (df_labeled["industry_code"].astype(str) == k[1])
        & (df_labeled["quarter"].astype(int) == k[2]),
        "industry_prior_pred"
    ].iloc[0]
    for k in val_common
])

# scale 보정 — industry_prior_pred (0~0.5 mean) → 0~1 (X 2)
industry_prior_val_scaled = np.clip(industry_prior_val_aligned * 2, 0, 1)

# grid search w_industry [0.0, 0.5] step 0.05
best_w_industry = 0.0
best_auc = roc_auc_score(y_val_common, ensemble_val_proba)
for w_ind in np.arange(0.0, 0.55, 0.05):
    w_dong = 1.0 - w_ind
    candidate = w_dong * ensemble_val_proba + w_ind * industry_prior_val_scaled
    auc = roc_auc_score(y_val_common, candidate)
    if auc > best_auc:
        best_auc = auc
        best_w_industry = w_ind
```

### 2. Test 적용 (best_w_industry)

```python
# test_common keys 의 industry_prior_pred lookup (동일 패턴)
industry_prior_test_scaled = np.clip(... * 2, 0, 1)

if best_w_industry > 0:
    additive_test_proba = (1 - best_w_industry) * ensemble_test_proba + best_w_industry * industry_prior_test_scaled
    ensemble_val_proba_final = (1 - best_w_industry) * ensemble_val_proba + best_w_industry * industry_prior_val_scaled
else:
    # additive 효과 없음 — 그대로
    additive_test_proba = ensemble_test_proba
    ensemble_val_proba_final = ensemble_val_proba
```

### 3. ensemble_weights.pkl 확장

```python
ensemble_weights = {
    "w_lgbm": ..., "w_tcn": ...,
    "lgbm_auc": ..., "tcn_auc": ...,
    "input_size": ...,
    "additive_w_industry": best_w_industry,  # 신규
}
```

### 4. predict.py 통합 (T1 결과 keep 시)

```python
# ensemble proba 계산 직후
additive_w = ensemble_w.get("additive_w_industry", 0.0)
if additive_w > 0 and stage1_data is not None:
    industry_prior_scaled = min(max(industry_prior_pred * 2, 0), 1)
    raw_score = (1 - additive_w) * raw_score + additive_w * industry_prior_scaled
```

### 5. cfg flag

```python
"enable_a2_additive": True  # default trial
```

## Risks

| Risk | Mitigation |
|---|---|
| feature 와 additive 가 redundant → noise | val grid search 가 best_w_industry=0 선택 시 자동 skip |
| Test AUC degradation | 의사결정 규칙: test AUC < 0.6149 → rollback (cfg flag False) |
| 단일 val grid search overfit | step 0.05 small grid + threshold 조건 (best_auc > current AUC) |
| predict.py 호환성 | additive_w=0 fallback (자동 skip) |

## 의사결정 규칙

- Test AUC ≥ 0.6149 → keep (predict.py 통합 + 산출물 commit)
- 그 외 → rollback (cfg flag False, weight pkl 의 additive_w_industry 제거)

## Tasks (3)

| # | 내용 |
|---|---|
| T1 | train.py 통합 + grid search + ensemble_weights.pkl 확장 + retrain + 결과 평가 |
| T2 (조건부) | KEEP 시 predict.py 통합 + 회귀 test |
| T3 | 회고 |
