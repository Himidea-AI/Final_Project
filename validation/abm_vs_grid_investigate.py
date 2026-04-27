"""V1 baseline 0.28 vs doc 0.79 mystery — 다양한 aggregation 시도.

가설:
  - flat Pearson (현재 측정) — 0.28
  - per-dong fraction normalize — sim-mode-matrix 0.79 일 가능성
  - per-dong z-score
  - log scale Pearson
  - per-dong Pearson 평균 (각 동 내 24h 패턴만)
  - across-hour Pearson 평균 (각 시간 16동 패턴만)
"""

from __future__ import annotations

import io
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
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


def load_kt_q1() -> pd.DataFrame:
    sql = text(
        """SELECT dong_code, tt, AVG(spop) AS presence
        FROM living_population_grid
        WHERE ymd BETWEEN '2026-01-01' AND '2026-03-31' AND dong_code LIKE '11440%'
        GROUP BY dong_code, tt"""
    )
    with engine.connect() as c:
        return pd.read_sql(sql, c)


def run_abm() -> pd.DataFrame:
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
        seed=42,
        seed_memory=True,
        memory_seed_days=14,
    )
    counts: dict[tuple, int] = defaultdict(int)
    for e in result.trajectory or []:
        dong = e.get("dong")
        if not dong or dong == "외부":
            continue
        code = MAPO_DONG_CODE.get(dong)
        if not code:
            continue
        h = int(e.get("hour", 0))
        counts[(code, h)] += 1
    return pd.DataFrame([{"dong_code": k[0], "tt": k[1], "abm": v} for k, v in counts.items()])


def safe_pearson(x: pd.Series, y: pd.Series) -> float:
    if x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(pearsonr(x, y)[0])


def main():
    print("=== V1 baseline 0.28 mystery — aggregation 6가지 시도 ===\n")
    kt = load_kt_q1()
    print("[1/2] ABM 시뮬...", flush=True)
    abm = run_abm()
    merged = kt.merge(abm, on=["dong_code", "tt"], how="inner")
    print(f"매칭 {len(merged)} cells, {merged['dong_code'].nunique()} 동")

    # ─── M1: flat Pearson (현재 측정 방식) ───
    M1 = safe_pearson(merged["presence"], merged["abm"])

    # ─── M2: total-sum normalize (abm_vs_grid.py 동일) ───
    r_tot = merged["presence"].sum()
    s_tot = merged["abm"].sum()
    merged["real_n"] = merged["presence"] / r_tot
    merged["sim_n"] = merged["abm"] / s_tot
    M2 = safe_pearson(merged["real_n"], merged["sim_n"])

    # ─── M3: per-dong fraction (각 동 내 24h 합 = 1) ───
    merged["real_dn"] = merged.groupby("dong_code")["presence"].transform(lambda s: s / s.sum())
    merged["sim_dn"] = merged.groupby("dong_code")["abm"].transform(lambda s: s / s.sum() if s.sum() else 0)
    M3 = safe_pearson(merged["real_dn"], merged["sim_dn"])

    # ─── M4: per-dong z-score ───
    def zscore(s):
        if s.std() == 0:
            return s * 0
        return (s - s.mean()) / s.std()

    merged["real_z"] = merged.groupby("dong_code")["presence"].transform(zscore)
    merged["sim_z"] = merged.groupby("dong_code")["abm"].transform(zscore)
    M4 = safe_pearson(merged["real_z"], merged["sim_z"])

    # ─── M5: log scale ───
    merged["real_log"] = np.log1p(merged["presence"])
    merged["sim_log"] = np.log1p(merged["abm"])
    M5 = safe_pearson(merged["real_log"], merged["sim_log"])

    # ─── M6: per-dong Pearson 평균 (각 동의 24h pattern fit) ───
    per_dong_r = []
    for dc, sub in merged.groupby("dong_code"):
        if len(sub) < 3:
            continue
        r = safe_pearson(sub["presence"], sub["abm"])
        if not np.isnan(r):
            per_dong_r.append(r)
    M6 = float(np.mean(per_dong_r)) if per_dong_r else float("nan")

    # ─── M7: per-hour Pearson 평균 (각 시간의 16동 spatial fit) ───
    per_hour_r = []
    for h, sub in merged.groupby("tt"):
        if len(sub) < 3:
            continue
        r = safe_pearson(sub["presence"], sub["abm"])
        if not np.isnan(r):
            per_hour_r.append(r)
    M7 = float(np.mean(per_hour_r)) if per_hour_r else float("nan")

    # ─── M8: residence baseline 차감 + per-dong fraction (Phase I + 정규화) ───
    nighttime = merged[merged["tt"].between(3, 7)]
    kt_baseline = nighttime.groupby("dong_code")["presence"].mean().to_dict()
    merged["kt_resid"] = merged.apply(lambda r: max(0, r["presence"] - kt_baseline.get(r["dong_code"], 0)), axis=1)
    M8_raw = safe_pearson(merged["kt_resid"], merged["abm"])
    merged["kt_resid_dn"] = merged.groupby("dong_code")["kt_resid"].transform(lambda s: s / s.sum() if s.sum() else 0)
    M8_dn = safe_pearson(merged["kt_resid_dn"], merged["sim_dn"])

    print("\n" + "=" * 70)
    print("Method                                                | Pearson r")
    print("=" * 70)
    print(f"M1 flat (raw count)                                    | {M1:+.4f}")
    print(f"M2 total-sum normalize (abm_vs_grid.py method)         | {M2:+.4f}")
    print(f"M3 per-dong fraction (each dong 24h sum=1)             | {M3:+.4f}")
    print(f"M4 per-dong z-score                                    | {M4:+.4f}")
    print(f"M5 log1p scale                                         | {M5:+.4f}")
    print(f"M6 per-dong Pearson avg (24h pattern within dong)      | {M6:+.4f}")
    print(f"M7 per-hour Pearson avg (16동 spatial fit per hour)    | {M7:+.4f}")
    print(f"M8 KT residence subtracted (raw)                       | {M8_raw:+.4f}")
    print(f"M9 KT residence subtracted + per-dong fraction         | {M8_dn:+.4f}")
    print("=" * 70)
    print("\nDoc claim (sim-mode-matrix): Phase 3a Q1 평균 = 0.8099")
    print("가장 근접한 method: ", end="")
    methods = {
        "M1 flat": M1,
        "M2 total-norm": M2,
        "M3 per-dong frac": M3,
        "M4 per-dong z": M4,
        "M5 log": M5,
        "M6 per-dong avg": M6,
        "M7 per-hour avg": M7,
        "M8 KT-resid raw": M8_raw,
        "M9 KT-resid+frac": M8_dn,
    }
    closest = min(methods.items(), key=lambda kv: abs(kv[1] - 0.81) if not np.isnan(kv[1]) else 99)
    print(f"{closest[0]} = {closest[1]:+.4f} (Δ={abs(closest[1] - 0.81):.3f})")


if __name__ == "__main__":
    main()
