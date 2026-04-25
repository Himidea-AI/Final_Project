"""ABM 시뮬 출력 vs 서울 250m 격자 생활인구 (living_population_grid) 검증.

비교 축:
    1) 동 × 시간 → 총 생활인구 패턴 상관 (Pearson r / Spearman ρ / MAPE)
    2) 피크 시간대 상위 3개 일치율 (per-dong)
    3) 동 간 상대 순위 Kendall τ

ABM 출력 획득:
    POST /simulate-abm (trajectory 포함) → agent_id×시간별 동 분포 집계

실 데이터:
    DB living_population_grid → (dong_code, TT) 로 집계
    cell 단위는 ABM 해상도 맞지 않아 동 단위 집계로 변환

사용:
    python validation/abm_vs_grid.py --date 2026-02-15
    python validation/abm_vs_grid.py --date-range 2026-02-01:2026-02-28
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

engine = create_engine(os.environ["POSTGRES_URL"])

# ABM dong name → 서울 행정동 코드 (8자리, living_population/living_population_grid 저장 형식)
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
CODE_TO_DONG = {v: k for k, v in MAPO_DONG_CODE.items()}


def load_grid_hourly(date_str: str) -> pd.DataFrame:
    """지정 날짜의 living_population_grid 를 동×시간 집계로 반환 (dong_code 8자리 그대로)."""
    sql = text("""
        SELECT dong_code, tt, SUM(spop) as total_pop
        FROM living_population_grid
        WHERE ymd = :d
        GROUP BY dong_code, tt
        ORDER BY dong_code, tt
    """)
    with engine.connect() as c:
        df = pd.read_sql(sql, c, params={"d": date_str})
    return df


def load_grid_range(start: str, end: str) -> pd.DataFrame:
    """기간 평균 — 동×시간별 평균 생활인구 (요일/일별 variance 흡수)."""
    sql = text("""
        SELECT dong_code, tt, AVG(spop) as avg_pop
        FROM living_population_grid
        WHERE ymd BETWEEN :s AND :e
        GROUP BY dong_code, tt
    """)
    with engine.connect() as c:
        df = pd.read_sql(sql, c, params={"s": start, "e": end})
    return df


def run_abm_sim(days: int = 1) -> dict:
    """ABM 시뮬 실행 → trajectory 포함 결과 dict 반환."""
    # backend/src 를 path 에 추가 (validation/ 에서 실행 가정)
    backend_src = REPO_ROOT / "backend"
    if str(backend_src) not in sys.path:
        sys.path.insert(0, str(backend_src))
    from src.simulation.config import (
        ModelConfig,
        PopulationMix,
        Scenario,
        TierDistribution,
    )
    from src.simulation.runner import run_simulation

    # v2: 10K 스케일, archetype + time_block 활용
    cfg = ModelConfig(
        n_personas=10000,
        tier_a_provider="openai",
        tier_a_model="gpt-4.1-nano",
    )
    result = run_simulation(
        cfg=cfg,
        pop=PopulationMix(),
        tier=TierDistribution(),
        scenario=Scenario(),
        days=days,
        use_rds=True,
        use_profiles=True,
        collect_trajectory=True,
        trajectory_sample_size=1000,
        use_policy=True,  # Policy 기반 — $0.37 → $0.002/run
        verbose=False,
    )
    return {
        "trajectory": result.trajectory or [],
        "dong_totals": result.dong_totals or {},
    }


def abm_trajectory_to_dong_hour(trajectory: list) -> pd.DataFrame:
    """ABM trajectory (agent_id×hour×dong) → 동×시간 에이전트 수 집계."""
    counts: dict[tuple, int] = defaultdict(int)
    for e in trajectory:
        dong_name = e.get("dong")
        if not dong_name or dong_name == "외부":
            continue
        code = MAPO_DONG_CODE.get(dong_name)
        if not code:
            continue
        h = int(e.get("hour", 0))
        counts[(code, h)] += 1
    rows = [{"dong_code": k[0], "tt": k[1], "agents": v} for k, v in counts.items()]
    return pd.DataFrame(rows)


def compute_metrics(real: pd.DataFrame, sim: pd.DataFrame) -> dict:
    """동×시간 매칭 후 Pearson, Spearman, MAPE, peak-hour accuracy 계산."""
    # normalize — 값 크기 맞추기 위해 총합 1 로 정규화 (상대 패턴 비교)
    merged = real.merge(sim, on=["dong_code", "tt"], how="inner")
    if merged.empty:
        return {"error": "no overlap between real and sim"}

    r_tot = merged["total_pop"].sum() if "total_pop" in merged.columns else merged["avg_pop"].sum()
    s_tot = merged["agents"].sum()
    if r_tot == 0 or s_tot == 0:
        return {"error": "zero total in real or sim"}

    real_col = "total_pop" if "total_pop" in merged.columns else "avg_pop"
    merged["real_norm"] = merged[real_col] / r_tot
    merged["sim_norm"] = merged["agents"] / s_tot

    from scipy.stats import kendalltau, pearsonr, spearmanr

    p_r, p_p = pearsonr(merged["real_norm"], merged["sim_norm"])
    s_r, s_p = spearmanr(merged["real_norm"], merged["sim_norm"])

    # MAPE (정규화 값 기준)
    mape_val = float(
        (np.abs(merged["real_norm"] - merged["sim_norm"]) / merged["real_norm"].replace(0, np.nan)).mean() * 100
    )

    # 동별 peak hour 일치율
    real_peak = merged.loc[merged.groupby("dong_code")[real_col].idxmax(), ["dong_code", "tt"]].set_index("dong_code")[
        "tt"
    ]
    sim_peak = merged.loc[merged.groupby("dong_code")["agents"].idxmax(), ["dong_code", "tt"]].set_index("dong_code")[
        "tt"
    ]
    common = real_peak.index.intersection(sim_peak.index)
    peak_match = int((real_peak.loc[common] == sim_peak.loc[common]).sum())
    peak_total = len(common)

    # 동별 총량 순위 Kendall
    real_rank = merged.groupby("dong_code")[real_col].sum().rank(ascending=False)
    sim_rank = merged.groupby("dong_code")["agents"].sum().rank(ascending=False)
    rk = real_rank.reindex(sim_rank.index).dropna()
    sk = sim_rank.reindex(rk.index)
    kt, kt_p = kendalltau(rk, sk)

    return {
        "n_samples": len(merged),
        "pearson_r": float(p_r),
        "pearson_p": float(p_p),
        "spearman_r": float(s_r),
        "spearman_p": float(s_p),
        "mape_pct": mape_val,
        "peak_hour_match": peak_match,
        "peak_hour_total": peak_total,
        "peak_hour_acc": peak_match / peak_total if peak_total else 0,
        "kendall_tau": float(kt),
        "kendall_p": float(kt_p),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD 단일 날짜 검증")
    ap.add_argument("--date-range", help="YYYY-MM-DD:YYYY-MM-DD 기간 평균 검증")
    args = ap.parse_args()

    print("=== ABM vs 격자 생활인구 검증 ===\n")

    if args.date:
        real = load_grid_hourly(args.date)
        label = args.date
    elif args.date_range:
        s, e = args.date_range.split(":")
        real = load_grid_range(s, e)
        label = f"{s}~{e} 평균"
    else:
        ap.error("--date 또는 --date-range 필수")

    print(f"[실데이터] {label}  동수={real['dong_code'].nunique()}  행수={len(real)}")

    print("[ABM] 시뮬 실행 중 (days=1, n_personas=1000)...")
    sim_result = run_abm_sim(days=1)
    sim = abm_trajectory_to_dong_hour(sim_result["trajectory"])
    print(f"[ABM] trajectory 집계: 동수={sim['dong_code'].nunique()}  행수={len(sim)}")

    metrics = compute_metrics(real, sim)
    print("\n=== 검증 결과 ===")
    if "error" in metrics:
        print(f"ERROR: {metrics['error']}")
        return
    print(f"매칭 샘플     : {metrics['n_samples']}")
    print(f"Pearson r     : {metrics['pearson_r']:+.3f}  (p={metrics['pearson_p']:.2e})")
    print(f"Spearman ρ    : {metrics['spearman_r']:+.3f}  (p={metrics['spearman_p']:.2e})")
    print(f"MAPE (정규화) : {metrics['mape_pct']:.1f}%")
    print(f"피크시간 일치 : {metrics['peak_hour_match']}/{metrics['peak_hour_total']} = {metrics['peak_hour_acc']:.0%}")
    print(f"Kendall τ     : {metrics['kendall_tau']:+.3f}  (p={metrics['kendall_p']:.2e})")


if __name__ == "__main__":
    main()
