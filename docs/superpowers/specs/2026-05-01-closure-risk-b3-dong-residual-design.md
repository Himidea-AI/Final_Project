# 폐업 위험도 모델 B-3 (dong residual feature) — Design Spec

> **상태**: 사용자 승인 (2026-05-01).
> **선행**: A-3 ✅ KEEP (production: commit 2461362, test AUC 0.6139).

## Goal

LGBM_FEATURES 에 단일 hierarchical-grounded feature 추가:

`dong_closure_rate_residual_lag1 = closure_rate_lag1 - industry_avg_closure_rate_lag1_train_fit(industry_code)`

"이 dong×industry 의 직전 분기 폐업률이 같은 업종 평균보다 얼마나 높/낮았는가" — A-3 의 industry-level prior (Stage 1) 와 보완적인 dong-specific deviation 신호.

## Background

A-3 후 production AUC 0.6139. B-1 (단순 derivation 8개) rollback, D-3 (calibration) rollback. AUC 0.60 plateau 의 가능한 원인:
- 자기상관 lag 위주 feature
- industry-level dynamic (A-3 Stage 1 으로 일부 해소)
- **dong-level deviation 신호 부재**

본 spec 의 가설: closure_rate_lag1 (절대값) 외에 **industry baseline 대비 상대값 (residual)** 이 LGBM 에 의미 있는 split feature.

학술 근거: hierarchical regression 의 partial pooling — Gelman & Hill (2006). residual decomposition 표준.

## Components

### 1. `_engineer_lag_features` 에 derivation 추가

```python
# B-3 hierarchical residual feature (2026-05-01)
# train-only fit 로 leakage 차단 — 호출자가 train_quarters 전달 시에만 활용
# build_closure_risk_dataset 호출 단계에서는 0 fallback,
# train.py 의 split 후 단계에서 명시 호출.
df["dong_closure_rate_residual_lag1"] = 0.0  # default fallback
```

신규 helper:
```python
def add_dong_residual_feature(
    df: pd.DataFrame,
    train_quarters: set[int],
) -> pd.DataFrame:
    """B-3: dong-industry 의 lag1 closure_rate residual (vs train industry mean).

    Args:
        df: lag feature 까지 적용된 dataset (closure_rate_lag1 컬럼 존재).
        train_quarters: train split 분기.

    Returns:
        df with dong_closure_rate_residual_lag1 column.
    """
    train_df = df[df["quarter"].isin(train_quarters)]
    industry_mean = train_df.groupby("industry_code")["closure_rate_lag1"].mean()
    global_mean = float(train_df["closure_rate_lag1"].mean())

    df = df.copy()
    df["_industry_mean_lag1"] = df["industry_code"].map(industry_mean).fillna(global_mean)
    df["dong_closure_rate_residual_lag1"] = df["closure_rate_lag1"].fillna(0) - df["_industry_mean_lag1"]
    df = df.drop(columns=["_industry_mean_lag1"])
    return df
```

### 2. `LGBM_FEATURES` 에 추가 (16 → 17)

`data_prep.py:LGBM_FEATURES`:
```python
"industry_prior_pred",  # A-2 Stage 1
# B-3 dong residual (2026-05-01)
"dong_closure_rate_residual_lag1",  # closure_rate_lag1 - industry mean (train fit)
```

cfg flag 로 toggle:
```python
DEFAULT_CONFIG: dict = {
    ...,
    "enable_b3_dong_residual": True,  # 본 sprint default. 실패 시 False rollback
}
```

`build_closure_risk_dataset` 의 `for f in missing: df[f] = 0.0` 로 default fallback 보장 (split 전).

### 3. `train.py` 통합

```python
# _make_labels 직후, Stage 1 호출 직후
from models.closure_risk.data_prep import add_dong_residual_feature
if cfg.get("enable_b3_dong_residual", True):
    df_labeled = add_dong_residual_feature(df_labeled, train_quarters)
    logger.info("B-3 dong residual 추가. range=[%.4f, %.4f]",
                float(df_labeled["dong_closure_rate_residual_lag1"].min()),
                float(df_labeled["dong_closure_rate_residual_lag1"].max()))
```

### 4. `predict.py` 무영향

- `_engineer_lag_features` 가 default 0.0 으로 컬럼 채움 → predict() 의 latest 에서 0 lookup
- BUT: 정확한 residual lookup 위해 train 시 저장된 industry_mean dict 도 pkl 저장하면 더 좋음

simple 버전 (본 sprint): predict.py 는 0 fallback 만. 효과 작을 수 있으나 빠른 검증.

확장 버전 (필요시): industry_mean dict 를 ensemble_weights.pkl 또는 별도 pkl 에 저장.

## Tasks (3)

| # | 내용 |
|---|---|
| T1 | `add_dong_residual_feature` helper + LGBM_FEATURES 17 + cfg flag + train.py 통합 + 3 unit test |
| T2 | production retrain + 의사결정 |
| T3 | 회고 |

## Risks

| Risk | Mitigation |
|---|---|
| 단일 feature noise (B-1 패턴) | cfg flag rollback 가능 |
| predict.py 의 0 fallback 으로 production 효과 X | T2 retrain 시 train metric 으로 검증. 효과 시 별도 sprint 로 lookup pkl 저장 |
| LGBM 이 이미 implicit residual 학습 | 정직한 진단 — feature redundancy 확인 |

## 의사결정 규칙

A/D-3 패턴:
- Test AUC ≥ A-3 baseline (0.6139) → keep
- 그 외 → rollback (weight 복원 + cfg flag False default)
