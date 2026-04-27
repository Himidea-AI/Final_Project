"""Phase H/I/J/K/L 종합 측정 — PSE N=3.

수학적 도구 종합 실측:
  - Phase H: Little's Law dwell weighting (action 별 가중)
  - Phase I: KT residence baseline 차감 (확정 통과)
  - Phase J: Lagged correlation Δt sweep
  - Phase K: 분포 metric (Wasserstein, KL)
  - Phase L: IPF marginal calibration
  - 보조: Moran's I 공간 자기상관 비교

참조: docs/abm-simulation/ceiling-analysis.md §7-A
"""

from __future__ import annotations

import io
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, wasserstein_distance
from sqlalchemy import create_engine, text

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

engine = create_engine(os.environ["POSTGRES_URL"])

MAPO_DONG_CODE = {
    "아현동": "11440555",
    "공덕동": "11440565",
    "도화동": "11440585",
    "용강동": "11440590",
    "대흥동": "11440600",
    "염리동": "11440610",
    "신수동": "11440630",
    "서강동": "11440655",
    "서교동": "11440660",
    "합정동": "11440680",
    "망원1동": "11440690",
    "망원2동": "11440700",
    "연남동": "11440710",
    "성산1동": "11440720",
    "성산2동": "11440730",
    "상암동": "11440740",
}

# Little's Law dwell time (분 단위) — action 별 체류시간 가정
DWELL_BY_ACTION = {
    "visit": 60,  # 매장 방문 (카페/음식점 평균)
    "rest": 30,  # 휴식
    "go_home": 480,  # 집 (8h, 야간 stay)
    "work": 480,  # 직장 (8h)
    "stay": 60,  # 일반 stay (1h)
    "wait": 30,  # 대기
    None: 60,  # 미정 default
}

SEEDS = [42, 123, 7777]


def load_kt() -> pd.DataFrame:
    sql = text(
        """SELECT dong_code, tt, AVG(spop) AS presence
        FROM living_population_grid
        WHERE ymd BETWEEN '2026-01-01' AND '2026-03-31' AND dong_code LIKE '11440%'
        GROUP BY dong_code, tt"""
    )
    with engine.connect() as c:
        return pd.read_sql(sql, c)


def run_abm(seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """trajectory → (raw_count, dwell_weighted) 두 DataFrame 반환."""
    backend = REPO_ROOT / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from src.simulation.config import ModelConfig, PopulationMix, TierDistribution
    from src.simulation.runner import run_simulation

    cfg = ModelConfig(n_personas=1000, tier_s_provider="mock", tier_a_provider="mock")
    result = run_simulation(
        cfg=cfg,
        pop=PopulationMix(),
        tier=TierDistribution(),
        days=1,
        use_rds=True,
        use_profiles=True,
        collect_trajectory=True,
        trajectory_sample_size=1000,
        use_policy=True,
        verbose=False,
        seed=seed,
        seed_memory=True,
        memory_seed_days=14,
    )
    raw_counts: dict[tuple, int] = defaultdict(int)
    dwell_counts: dict[tuple, float] = defaultdict(float)
    for e in result.trajectory or []:
        dong = e.get("dong")
        if not dong or dong == "외부":
            continue
        code = MAPO_DONG_CODE.get(dong)
        if not code:
            continue
        h = int(e.get("hour", 0))
        action = e.get("action")
        raw_counts[(code, h)] += 1
        # Little's Law: weight = dwell / 60 (1 hour 안에서 분율)
        dwell_counts[(code, h)] += DWELL_BY_ACTION.get(action, 60) / 60.0
    raw = pd.DataFrame([{"dong_code": k[0], "tt": k[1], "abm": v} for k, v in raw_counts.items()])
    dwell = pd.DataFrame([{"dong_code": k[0], "tt": k[1], "abm_dwell": v} for k, v in dwell_counts.items()])
    return raw, dwell


def safe_pearson(x: pd.Series, y: pd.Series) -> float:
    if x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(pearsonr(x, y)[0])


def ipf_calibrate(
    matrix: np.ndarray, row_target: np.ndarray, col_target: np.ndarray, max_iter: int = 50, tol: float = 1e-4
) -> np.ndarray:
    """Iterative Proportional Fitting — matrix 의 row/col sum 을 target 에 맞춤."""
    M = matrix.astype(float).copy()
    M[M < 1e-9] = 1e-9  # zero 회피
    for _ in range(max_iter):
        rs = M.sum(axis=1, keepdims=True)
        M *= row_target.reshape(-1, 1) / rs
        cs = M.sum(axis=0, keepdims=True)
        M *= col_target.reshape(1, -1) / cs
        if np.allclose(M.sum(axis=1), row_target, atol=tol) and np.allclose(M.sum(axis=0), col_target, atol=tol):
            break
    return M


def morans_I(values: np.ndarray, weights: np.ndarray) -> float:
    """공간 자기상관 Moran's I."""
    n = len(values)
    mean_v = values.mean()
    dev = values - mean_v
    num = 0.0
    for i in range(n):
        for j in range(n):
            num += weights[i, j] * dev[i] * dev[j]
    denom = (dev**2).sum()
    W = weights.sum()
    if denom == 0 or W == 0:
        return 0.0
    return float((n / W) * (num / denom))


def measure_all(kt: pd.DataFrame, abm_raw: pd.DataFrame, abm_dwell: pd.DataFrame) -> dict:
    merged = kt.merge(abm_raw, on=["dong_code", "tt"], how="inner")
    merged = merged.merge(abm_dwell, on=["dong_code", "tt"], how="inner")

    out = {"n_cells": len(merged)}

    # ─── Baseline V1: raw Pearson ───
    out["V1_raw"] = safe_pearson(merged["presence"], merged["abm"])

    # ─── Phase H: Little's Law dwell weighting ───
    out["H_dwell_weighted"] = safe_pearson(merged["presence"], merged["abm_dwell"])

    # ─── Phase I-a: KT residence baseline 차감 ───
    nighttime = merged[merged["tt"].between(3, 7)]
    kt_baseline = nighttime.groupby("dong_code")["presence"].mean().to_dict()
    merged["kt_resid"] = merged.apply(lambda r: max(0, r["presence"] - kt_baseline.get(r["dong_code"], 0)), axis=1)
    out["I_kt_residual"] = safe_pearson(merged["kt_resid"], merged["abm"])
    out["I_kt_residual_dwell"] = safe_pearson(merged["kt_resid"], merged["abm_dwell"])  # H+I 조합

    # ─── Phase J: Lagged correlation Δt sweep ───
    pivoted_kt = merged.pivot(index="tt", columns="dong_code", values="presence")
    pivoted_abm = merged.pivot(index="tt", columns="dong_code", values="abm")
    lag_results = {}
    for delta in (-3, -2, -1, 0, 1, 2, 3):
        if delta == 0:
            shifted = pivoted_abm
        else:
            shifted = pivoted_abm.shift(-delta)
        m_lag = pivoted_kt.stack().rename("kt").to_frame().join(shifted.stack().rename("abm")).dropna()
        if len(m_lag) > 10:
            lag_results[delta] = safe_pearson(m_lag["kt"], m_lag["abm"])
    out["J_lagged"] = lag_results
    out["J_best_lag"] = max(lag_results, key=lag_results.get)
    out["J_best_pearson"] = lag_results[out["J_best_lag"]]

    # ─── Phase L: IPF marginal calibration ───
    try:
        kt_mat = pivoted_kt.fillna(0).values
        abm_mat = pivoted_abm.fillna(0).values
        # row target = KT 동별 24h 합, col target = KT 시간별 16동 합
        # (matrix 형태 통일: kt_mat shape (24, 16), abm_mat 같음)
        row_t = kt_mat.sum(axis=1)
        col_t = kt_mat.sum(axis=0)
        # IPF: ABM matrix 를 KT marginal 에 맞춤
        abm_calib = ipf_calibrate(abm_mat + 1e-6, row_t, col_t)
        # Pearson 비교
        out["L_ipf_calibrated"] = safe_pearson(pd.Series(kt_mat.flatten()), pd.Series(abm_calib.flatten()))
    except Exception as ex:
        out["L_ipf_error"] = str(ex)

    # ─── Phase K-1: Wasserstein distance ───
    # 두 pivoted matrix 의 hour/dong 축 정렬 (intersection)
    common_hours = sorted(set(pivoted_kt.index) & set(pivoted_abm.index))
    common_dongs = sorted(set(pivoted_kt.columns) & set(pivoted_abm.columns))
    kt_aligned = pivoted_kt.loc[common_hours, common_dongs].fillna(0)
    abm_aligned = pivoted_abm.loc[common_hours, common_dongs].fillna(0)

    kt_hour_dist = kt_aligned.sum(axis=1).values.astype(float)
    abm_hour_dist = abm_aligned.sum(axis=1).values.astype(float)
    if kt_hour_dist.sum() > 0:
        kt_hour_dist = kt_hour_dist / kt_hour_dist.sum()
    if abm_hour_dist.sum() > 0:
        abm_hour_dist = abm_hour_dist / abm_hour_dist.sum()
    n_h = len(common_hours)
    out["K_wasserstein_hour"] = float(
        wasserstein_distance(np.arange(n_h), np.arange(n_h), u_weights=kt_hour_dist, v_weights=abm_hour_dist)
    )

    kt_dong_dist = kt_aligned.sum(axis=0).values.astype(float)
    abm_dong_dist = abm_aligned.sum(axis=0).values.astype(float)
    if kt_dong_dist.sum() > 0:
        kt_dong_dist = kt_dong_dist / kt_dong_dist.sum()
    if abm_dong_dist.sum() > 0:
        abm_dong_dist = abm_dong_dist / abm_dong_dist.sum()
    n_d = len(common_dongs)
    out["K_wasserstein_dong"] = float(
        wasserstein_distance(np.arange(n_d), np.arange(n_d), u_weights=kt_dong_dist, v_weights=abm_dong_dist)
    )

    # ─── Phase K-2: KL divergence ───
    eps = 1e-10
    kl_hour = float((kt_hour_dist * np.log((kt_hour_dist + eps) / (abm_hour_dist + eps))).sum())
    kl_dong = float((kt_dong_dist * np.log((kt_dong_dist + eps) / (abm_dong_dist + eps))).sum())
    out["K_kl_hour"] = kl_hour
    out["K_kl_dong"] = kl_dong

    return out


def summarize(values: list[float]) -> dict:
    if not values:
        return {"mean": 0, "ci95": 0}
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0
    sem = std / (len(values) ** 0.5) if len(values) > 1 else 0
    return {"mean": round(mean, 4), "ci95": round(1.96 * sem, 4)}


def main():
    print(f"=== Phase H/I/J/K/L 종합 PSE N={len(SEEDS)} ===\n")
    kt = load_kt()
    print(f"KT Q1 평균 로드: {len(kt)}행\n")

    all_results = []
    for s in SEEDS:
        print(f"[seed={s}] ABM 시뮬...", flush=True)
        raw, dwell = run_abm(s)
        r = measure_all(kt, raw, dwell)
        all_results.append(r)
        print(
            f"  V1={r['V1_raw']:+.4f}  H={r['H_dwell_weighted']:+.4f}  I={r['I_kt_residual']:+.4f}  J(lag={r['J_best_lag']})={r['J_best_pearson']:+.4f}  L={r.get('L_ipf_calibrated', 'N/A'):+.4f}"
            if "L_ipf_calibrated" in r
            else f"  V1={r['V1_raw']:+.4f}"
        )

    print("\n" + "=" * 75)
    print("=== PSE 평균 ± 95% CI ===")
    print("=" * 75)
    metrics = [
        ("V1 raw Pearson (baseline)", "V1_raw"),
        ("H Little's Law dwell weighted", "H_dwell_weighted"),
        ("I KT residence baseline 차감", "I_kt_residual"),
        ("I + H 조합 (residence + dwell)", "I_kt_residual_dwell"),
        ("J best lag Pearson", "J_best_pearson"),
        ("L IPF marginal calibrated", "L_ipf_calibrated"),
    ]
    base = summarize([r["V1_raw"] for r in all_results])
    print(f"\n{'Metric':45s} | mean ± CI95     | Δ vs V1 | 판정")
    print("-" * 95)
    for label, key in metrics:
        vals = [r[key] for r in all_results if key in r and not (isinstance(r[key], float) and np.isnan(r[key]))]
        if not vals:
            continue
        s = summarize(vals)
        delta = s["mean"] - base["mean"]
        ci_combined = (base["ci95"] ** 2 + s["ci95"] ** 2) ** 0.5
        verdict = (
            "✅ stat-sig"
            if abs(delta) > ci_combined and delta > 0
            else ("⚠️ marginal" if abs(delta) > ci_combined else "❌ noise")
        )
        print(f"{label:45s} | {s['mean']:+.4f} ± {s['ci95']:.4f} | {delta:+.4f} | {verdict}")

    print("\n=== Phase J lagged sweep (avg across seeds) ===")
    lag_avg = {}
    for delta in (-3, -2, -1, 0, 1, 2, 3):
        vals = [r["J_lagged"][delta] for r in all_results if delta in r["J_lagged"]]
        if vals:
            lag_avg[delta] = summarize(vals)
            print(f"  Δt={delta:+d}h: {lag_avg[delta]['mean']:+.4f} ± {lag_avg[delta]['ci95']:.4f}")

    print("\n=== Phase K 분포 metric (낮을수록 좋음) ===")
    for key, label in [
        ("K_wasserstein_hour", "Wasserstein hour 분포"),
        ("K_wasserstein_dong", "Wasserstein 동 분포"),
        ("K_kl_hour", "KL divergence hour"),
        ("K_kl_dong", "KL divergence 동"),
    ]:
        vals = [r[key] for r in all_results if key in r]
        s = summarize(vals)
        print(f"  {label:30s}: {s['mean']:.4f} ± {s['ci95']:.4f}")


if __name__ == "__main__":
    main()
