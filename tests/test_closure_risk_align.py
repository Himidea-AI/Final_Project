"""A-1 inner-join alignment 단위 test."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest  # noqa: F401

from models.closure_risk.train import _align_predictions, _build_tcn_sequences


def test_align_predictions_inner_join():
    """같은 (dong, industry, quarter) key 만 ensemble."""
    lgbm_proba = np.array([0.1, 0.2, 0.3, 0.4])
    lgbm_keys = [("d1", "i1", 20211), ("d2", "i1", 20211), ("d3", "i1", 20211), ("d4", "i1", 20211)]
    tcn_proba = np.array([0.5, 0.6, 0.7])
    tcn_keys = [("d1", "i1", 20211), ("d2", "i1", 20211), ("d4", "i1", 20211)]
    label_dict = {k: 0 for k in lgbm_keys}

    aligned_lgbm, aligned_tcn, aligned_y, common = _align_predictions(
        lgbm_proba, lgbm_keys, tcn_proba, tcn_keys, label_dict
    )
    assert len(aligned_lgbm) == 3
    assert len(aligned_tcn) == 3
    assert len(common) == 3
    assert ("d3", "i1", 20211) not in common


def test_align_predictions_handles_no_overlap():
    """common keys 0건 → 빈 array."""
    lgbm_proba = np.array([0.1])
    lgbm_keys = [("d1", "i1", 20211)]
    tcn_proba = np.array([0.5])
    tcn_keys = [("d2", "i2", 20212)]
    label_dict = {("d1", "i1", 20211): 0, ("d2", "i2", 20212): 1}

    aligned_lgbm, aligned_tcn, aligned_y, common = _align_predictions(
        lgbm_proba, lgbm_keys, tcn_proba, tcn_keys, label_dict
    )
    assert len(aligned_lgbm) == 0
    assert len(common) == 0


def test_align_predictions_preserves_order():
    """common keys 가 sorted 순서."""
    lgbm_proba = np.array([0.1, 0.2])
    lgbm_keys = [("d2", "i1", 20211), ("d1", "i1", 20211)]
    tcn_proba = np.array([0.5, 0.6])
    tcn_keys = [("d2", "i1", 20211), ("d1", "i1", 20211)]
    label_dict = {k: 0 for k in lgbm_keys}

    _, _, _, common = _align_predictions(lgbm_proba, lgbm_keys, tcn_proba, tcn_keys, label_dict)
    assert common == sorted(common)


def test_align_predictions_y_uses_label_dict():
    """aligned_y 는 label_dict 의 값을 sorted common key 순서로 채운다."""
    lgbm_proba = np.array([0.1, 0.2])
    lgbm_keys = [("d1", "i1", 20211), ("d2", "i1", 20211)]
    tcn_proba = np.array([0.5, 0.6])
    tcn_keys = [("d1", "i1", 20211), ("d2", "i1", 20211)]
    label_dict = {("d1", "i1", 20211): 1, ("d2", "i1", 20211): 0}

    _, _, aligned_y, common = _align_predictions(lgbm_proba, lgbm_keys, tcn_proba, tcn_keys, label_dict)
    assert aligned_y[0] == label_dict[common[0]]
    assert aligned_y[1] == label_dict[common[1]]


def test_build_tcn_sequences_returns_keys():
    """_build_tcn_sequences 가 9-tuple 반환 (...val_keys, test_keys 마지막 2개)."""
    rng = np.random.default_rng(0)
    rows = []
    # train_quarters 에 들어갈 label 분기를 만들려면 window(4) 이전 분기도 필요.
    # quarters [20181..20184] 는 lookback 으로 사용되고, 20191~ 부터 label 분기.
    for d in range(2):
        for ind in ["I001"]:
            for q in [
                20181,
                20182,
                20183,
                20184,
                20191,
                20192,
                20193,
                20194,
                20201,
                20202,
                20203,
                20204,
            ]:
                rows.append(
                    {
                        "dong_code": f"d{d}",
                        "industry_code": ind,
                        "quarter": q,
                        "monthly_sales": float(rng.uniform(1e6, 1e7)),
                        "store_count": 10,
                    }
                )
    df = pd.DataFrame(rows)
    y = pd.Series([0] * len(df), index=df.index)

    result = _build_tcn_sequences(
        df,
        y,
        window_size=4,
        feature_cols=["monthly_sales", "store_count"],
        train_quarters={20191, 20192, 20193, 20194},
        val_quarters={20201, 20202},
        test_quarters={20203, 20204},
    )
    assert len(result) == 9, f"expected 9-tuple return, got {len(result)}"
    val_keys = result[7]
    test_keys = result[8]
    assert isinstance(val_keys, list)
    assert isinstance(test_keys, list)
    if val_keys:
        assert all(isinstance(k, tuple) and len(k) == 3 for k in val_keys)
    if test_keys:
        assert all(isinstance(k, tuple) and len(k) == 3 for k in test_keys)
