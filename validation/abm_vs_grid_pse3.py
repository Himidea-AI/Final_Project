"""V1 vs V2 PSE N=3 — Phase I 안정성 확인.

V2 (KT residence baseline 차감) 의 lift +0.35 가 single seed noise 인지
실제 효과인지 PSE 로 검증.
"""

from __future__ import annotations

import io
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd
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

SEEDS = [42, 123, 7777]


def load_kt_q1_avg() -> pd.DataFrame:
    sql = text(
        """SELECT dong_code, tt, AVG(spop) AS presence
        FROM living_population_grid
        WHERE ymd BETWEEN '2026-01-01' AND '2026-03-31' AND dong_code LIKE '11440%'
        GROUP BY dong_code, tt"""
    )
    with engine.connect() as c:
        return pd.read_sql(sql, c)


def run_abm_seed(seed: int) -> list[dict]:
    backend_src = REPO_ROOT / "backend"
    if str(backend_src) not in sys.path:
        sys.path.insert(0, str(backend_src))
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
    return result.trajectory or []


def trajectory_to_df(trajectory: list[dict]) -> pd.DataFrame:
    counts: dict[tuple, int] = defaultdict(int)
    for e in trajectory:
        dong = e.get("dong")
        if not dong or dong == "외부":
            continue
        code = MAPO_DONG_CODE.get(dong)
        if not code:
            continue
        h = int(e.get("hour", 0))
        counts[(code, h)] += 1
    return pd.DataFrame([{"dong_code": k[0], "tt": k[1], "abm": v} for k, v in counts.items()])


def measure(kt: pd.DataFrame, abm: pd.DataFrame) -> tuple[float, float]:
    from scipy.stats import pearsonr

    merged = kt.merge(abm, on=["dong_code", "tt"], how="inner")
    if merged.empty:
        return float("nan"), float("nan")

    # V1: raw
    v1 = pearsonr(merged["presence"], merged["abm"])[0]

    # V2: KT residence baseline 차감 (03~07시 평균)
    nighttime = merged[merged["tt"].between(3, 7)]
    kt_baseline = nighttime.groupby("dong_code")["presence"].mean().to_dict()
    merged["kt_visit_residual"] = merged.apply(lambda r: r["presence"] - kt_baseline.get(r["dong_code"], 0), axis=1)
    v2 = pearsonr(merged["kt_visit_residual"], merged["abm"])[0]
    return float(v1), float(v2)


def summarize(values: list[float]) -> dict:
    if not values:
        return {"mean": 0, "ci95": 0, "n": 0}
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0
    sem = std / (len(values) ** 0.5) if len(values) > 1 else 0
    return {
        "mean": round(mean, 4),
        "ci95": round(1.96 * sem, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def main():
    print(f"=== Phase I PSE N={len(SEEDS)} — V1 vs V2 안정성 ===\n")
    kt = load_kt_q1_avg()
    print(f"KT Q1 평균 로드: {len(kt)}행\n")

    v1_vals, v2_vals = [], []
    for s in SEEDS:
        print(f"[seed={s}] ABM 시뮬...", flush=True)
        traj = run_abm_seed(s)
        abm = trajectory_to_df(traj)
        v1, v2 = measure(kt, abm)
        print(f"  V1={v1:+.4f}  V2={v2:+.4f}  (Δ={v2 - v1:+.4f})")
        v1_vals.append(v1)
        v2_vals.append(v2)

    v1_s = summarize(v1_vals)
    v2_s = summarize(v2_vals)
    delta = v2_s["mean"] - v1_s["mean"]
    ci_combined = (v1_s["ci95"] ** 2 + v2_s["ci95"] ** 2) ** 0.5

    print("\n" + "=" * 60)
    print(
        f"V1 (raw Pearson)             : {v1_s['mean']:+.4f} ± {v1_s['ci95']:.4f}  range [{v1_s['min']:+.4f}, {v1_s['max']:+.4f}]"
    )
    print(
        f"V2 (KT residence subtracted) : {v2_s['mean']:+.4f} ± {v2_s['ci95']:.4f}  range [{v2_s['min']:+.4f}, {v2_s['max']:+.4f}]"
    )
    print(f"Δ (V2 - V1)                  : {delta:+.4f}  combined CI ±{ci_combined:.4f}")

    if delta > ci_combined:
        print(f"\n✅ Δ > combined CI ({delta:.4f} > {ci_combined:.4f}) — 통계적 유의 lift")
    else:
        print("\n❌ Δ ≤ combined CI — noise")


if __name__ == "__main__":
    main()
