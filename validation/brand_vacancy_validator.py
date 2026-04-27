"""5트랙 검증 protocol — brand 별 vacancy_pse 의 production-readiness 평가.

5트랙 측정 + 합격선 (엄격) 판정 + diagnose 진단 + JSON/MD report 생성.

학술 근거 (spec 16절):
    - Park 2024 (1052명 LLM 시뮬) — 같은 규모 학술 baseline
    - Affordable Generative Agents — 비용 절감 + 검증
    - Brussels ABM 0.96 — 학계 천장

사용:
    python -m validation.brand_vacancy_validator --brand 이디야 --category 카페
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import scipy.stats

logger = logging.getLogger(__name__)


# 합격선 (spec 9.1 엄격 정의)
V1A_R_MIN = 0.85
V1A_MAPE_MAX = 0.25
V1B_R_MIN = 0.80
V1B_MAPE_MAX = 0.30
V1C_RATIO_MIN = 0.7
V1C_RATIO_MAX = 1.5
V2_RATIO_MIN = 0.7
V2_RATIO_MAX = 1.5
CI_MAX = 0.10
MIN_CELLS_FOR_PEARSON = 10  # Cohen 1988, 통계 안정성


def _track_v1a(sim_revenue: dict[tuple, float], actual_revenue: dict[tuple, float]) -> dict[str, Any]:
    """V1a — 동×업종 매출 64-cell Pearson r + MAPE."""
    common = set(sim_revenue.keys()) & set(actual_revenue.keys())
    if len(common) < MIN_CELLS_FOR_PEARSON:
        return {"status": "incomplete", "n_cells": len(common), "pass": False}
    sim_arr = np.array([sim_revenue[k] for k in common])
    act_arr = np.array([actual_revenue[k] for k in common])
    if np.std(sim_arr) == 0 or np.std(act_arr) == 0:
        return {
            "status": "incomplete",
            "n_cells": len(common),
            "pass": False,
            "reason": "zero variance",
        }
    r, _ = scipy.stats.pearsonr(sim_arr, act_arr)
    mape = float(np.mean(np.abs(sim_arr - act_arr) / np.maximum(act_arr, 1)))
    return {
        "status": "ok",
        "n_cells": len(common),
        "pearson_r": round(float(r), 4),
        "mape": round(mape, 4),
        "pass": bool(r >= V1A_R_MIN and mape <= V1A_MAPE_MAX),
        "thresholds": {"r_min": V1A_R_MIN, "mape_max": V1A_MAPE_MAX},
    }


def _track_v1b(sim_visits: dict[tuple, float], actual_count: dict[tuple, float]) -> dict[str, Any]:
    """V1b — 동×업종 방문 64-cell Pearson r + MAPE. V1a 보다 약간 느슨."""
    common = set(sim_visits.keys()) & set(actual_count.keys())
    if len(common) < MIN_CELLS_FOR_PEARSON:
        return {"status": "incomplete", "n_cells": len(common), "pass": False}
    sim_arr = np.array([sim_visits[k] for k in common])
    act_arr = np.array([actual_count[k] for k in common])
    if np.std(sim_arr) == 0 or np.std(act_arr) == 0:
        return {
            "status": "incomplete",
            "n_cells": len(common),
            "pass": False,
            "reason": "zero variance",
        }
    r, _ = scipy.stats.pearsonr(sim_arr, act_arr)
    mape = float(np.mean(np.abs(sim_arr - act_arr) / np.maximum(act_arr, 1)))
    return {
        "status": "ok",
        "n_cells": len(common),
        "pearson_r": round(float(r), 4),
        "mape": round(mape, 4),
        "pass": bool(r >= V1B_R_MIN and mape <= V1B_MAPE_MAX),
        "thresholds": {"r_min": V1B_R_MIN, "mape_max": V1B_MAPE_MAX},
    }


def _track_v1c(sim_per_store: dict[tuple, float], actual_per_store: dict[tuple, float]) -> dict[str, Any]:
    """V1c — 매장당 매출 ratio (cell-wise ratio 의 mean)."""
    common = set(sim_per_store.keys()) & set(actual_per_store.keys())
    if len(common) < MIN_CELLS_FOR_PEARSON:
        return {"status": "incomplete", "n_cells": len(common), "pass": False}
    ratios = [sim_per_store[k] / max(actual_per_store[k], 1) for k in common]
    mean_ratio = float(np.mean(ratios))
    median_ratio = float(np.median(ratios))
    return {
        "status": "ok",
        "n_cells": len(common),
        "mean_ratio": round(mean_ratio, 3),
        "median_ratio": round(median_ratio, 3),
        "pass": bool(V1C_RATIO_MIN <= mean_ratio <= V1C_RATIO_MAX),
        "thresholds": {"ratio_min": V1C_RATIO_MIN, "ratio_max": V1C_RATIO_MAX},
    }


def _track_v2(sim_yearly: float, ftc_avg_yearly: int | None) -> dict[str, Any]:
    """V2 — 브랜드 연 매출 ratio (전국 평균과 비교)."""
    if ftc_avg_yearly is None or ftc_avg_yearly == 0:
        return {"status": "skipped", "reason": "ftc data missing", "pass": False}
    ratio = sim_yearly / ftc_avg_yearly
    return {
        "status": "ok",
        "ratio": round(float(ratio), 3),
        "sim_yearly_won": int(sim_yearly),
        "ftc_yearly_won": int(ftc_avg_yearly),
        "pass": bool(V2_RATIO_MIN <= ratio <= V2_RATIO_MAX),
        "thresholds": {"ratio_min": V2_RATIO_MIN, "ratio_max": V2_RATIO_MAX},
    }


def _track_ci(pse_summary: dict[str, Any]) -> dict[str, Any]:
    """CI — PSE 95% CI / mean ≤ 10%."""
    rev = pse_summary.get("revenue_per_day", {})
    mean = rev.get("mean", 0)
    ci95 = rev.get("ci95", 0)
    if mean == 0:
        return {"status": "incomplete", "pass": False}
    ci_ratio = ci95 / mean
    return {
        "status": "ok",
        "ci_ratio": round(float(ci_ratio), 4),
        "pass": bool(ci_ratio <= CI_MAX),
        "thresholds": {"ci_max": CI_MAX},
    }
