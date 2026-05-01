"""ABM vs KT presence — 4 metric variant 비교 (Phase H/I/J).

목적:
    `ceiling-analysis.md` §7-A 의 미시도 수학적 도구 실측:
    - V1 (baseline): raw count Pearson (현재 main, 0.79 expected)
    - V2 (Phase I-a): KT residence baseline 차감 → visit residual vs ABM
    - V3 (Phase I-b): 양쪽 모두 residence baseline 차감 (ABM hour-min)
    - V4 (Phase J): lagged Pearson(ABM(t), KT(t+Δt)) Δt=0~3h sweep

검증 데이터:
    living_population_grid 2026-Q1 평균 (3-month, real noise 흡수)
    마포 16동 × 24시간 = 384 cells

ABM:
    1K agents × 1d, mock LLM, use_policy=True (cost $0.001)
    seed=42 (단일 seed — 변형 비교용, 절대 baseline X)

사용:
    python validation/abm_vs_grid_decomposed.py
"""

from __future__ import annotations

import io
import os
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

Q1_START = "2026-01-01"
Q1_END = "2026-03-31"


def load_kt_q1_avg() -> pd.DataFrame:
    """KT 2026-Q1 마포 평균 presence (16동 × 24h)."""
    sql = text(
        """SELECT dong_code, tt, AVG(spop) AS presence
        FROM living_population_grid
        WHERE ymd BETWEEN :s AND :e AND dong_code LIKE '11440%'
        GROUP BY dong_code, tt
        ORDER BY dong_code, tt"""
    )
    with engine.connect() as c:
        return pd.read_sql(sql, c, params={"s": Q1_START, "e": Q1_END})


def run_abm_1k(seed: int = 42) -> list[dict]:
    """1K agent / 1d / mock / Policy → trajectory list."""
    backend_src = REPO_ROOT / "backend"
    if str(backend_src) not in sys.path:
        sys.path.insert(0, str(backend_src))
    from src.simulation.config import ModelConfig, PopulationMix, TierDistribution
    from src.simulation.runner import run_simulation

    cfg = ModelConfig(
        n_personas=1000,
        tier_s_provider="mock",
        tier_a_provider="mock",
    )
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


def trajectory_to_dong_hour(trajectory: list[dict]) -> pd.DataFrame:
    """trajectory → (dong_code, tt, count)."""
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
    rows = [{"dong_code": k[0], "tt": k[1], "abm": v} for k, v in counts.items()]
    return pd.DataFrame(rows)


def pearson(x: pd.Series, y: pd.Series) -> float:
    """간단 Pearson r (NaN/0 변동 안전)."""
    from scipy.stats import pearsonr

    if x.std() == 0 or y.std() == 0:
        return float("nan")
    r, _ = pearsonr(x, y)
    return float(r)


def compute_variants(kt: pd.DataFrame, abm: pd.DataFrame) -> dict[str, float]:
    """4 metric variant 계산 후 dict 반환."""
    merged = kt.merge(abm, on=["dong_code", "tt"], how="inner")
    if merged.empty:
        return {"error": "no overlap"}

    n = len(merged)
    out = {"n_samples": n}

    # ─── V1: raw Pearson (baseline) ───
    out["V1_raw_pearson"] = pearson(merged["presence"], merged["abm"])

    # ─── V2: Phase I-a — KT residence baseline 차감 ───
    # 각 동의 03~07시 평균 = residence baseline
    nighttime = merged[merged["tt"].between(3, 7)]
    kt_baseline = nighttime.groupby("dong_code")["presence"].mean().to_dict()
    merged["kt_visit_residual"] = merged.apply(lambda r: r["presence"] - kt_baseline.get(r["dong_code"], 0), axis=1)
    out["V2_kt_residual_pearson"] = pearson(merged["kt_visit_residual"], merged["abm"])

    # ─── V3: Phase I-b — 양쪽 모두 baseline 차감 ───
    # ABM 도 03~07시 평균 차감
    abm_nighttime = merged[merged["tt"].between(3, 7)]
    abm_baseline = abm_nighttime.groupby("dong_code")["abm"].mean().to_dict()
    merged["abm_visit_residual"] = merged.apply(lambda r: r["abm"] - abm_baseline.get(r["dong_code"], 0), axis=1)
    out["V3_both_residual_pearson"] = pearson(merged["kt_visit_residual"], merged["abm_visit_residual"])

    # ─── V4: Phase J — lagged Pearson Δt sweep ───
    pivoted_kt = merged.pivot(index="tt", columns="dong_code", values="presence")
    pivoted_abm = merged.pivot(index="tt", columns="dong_code", values="abm")

    lag_results = {}
    for delta in (-2, -1, 0, 1, 2, 3):
        # ABM 을 delta 만큼 shift (양수 = ABM 이 KT 보다 앞섬)
        if delta > 0:
            abm_shifted = pivoted_abm.shift(-delta)
        else:
            abm_shifted = pivoted_abm.shift(-delta)
        # 정렬 후 stack 으로 비교
        merged_shifted = (
            pivoted_kt.subtract(0).stack().rename("kt").to_frame().join(abm_shifted.stack().rename("abm")).dropna()
        )
        if len(merged_shifted) < 10:
            continue
        lag_results[f"lag_{delta:+d}"] = pearson(merged_shifted["kt"], merged_shifted["abm"])
    out["V4_lagged"] = lag_results

    # ─── V5: 추가 — KT residual normalize + ABM residual normalize (z-score) ───
    # 각 동 내 z-score 정규화 → 동 간 비교 noise 제거
    def zscore(series: pd.Series) -> pd.Series:
        if series.std() == 0:
            return series * 0
        return (series - series.mean()) / series.std()

    merged["kt_z"] = merged.groupby("dong_code")["presence"].transform(zscore)
    merged["abm_z"] = merged.groupby("dong_code")["abm"].transform(zscore)
    out["V5_per_dong_zscore_pearson"] = pearson(merged["kt_z"], merged["abm_z"])

    # ─── V6: residual + z-score 조합 ───
    merged["kt_resid_z"] = merged.groupby("dong_code")["kt_visit_residual"].transform(zscore)
    merged["abm_resid_z"] = merged.groupby("dong_code")["abm_visit_residual"].transform(zscore)
    out["V6_residual_zscore_pearson"] = pearson(merged["kt_resid_z"], merged["abm_resid_z"])

    return out


def main():
    print("=== Phase H/I/J — ABM 출력 변환 + metric 변경 측정 ===\n")
    print(f"검증 데이터: KT presence Q1 2026 평균 ({Q1_START} ~ {Q1_END})")
    print("ABM: 1K agent / 1d / mock / Policy / seed=42\n")

    print("[1/3] KT presence Q1 평균 로드 중...")
    kt = load_kt_q1_avg()
    print(f"  → {len(kt):,}행, {kt['dong_code'].nunique()}동")

    print("[2/3] ABM 시뮬 실행 중 (1K agent, ~1분)...")
    trajectory = run_abm_1k(seed=42)
    print(f"  → trajectory {len(trajectory):,}건")
    abm = trajectory_to_dong_hour(trajectory)
    print(f"  → 집계 {len(abm):,}행, {abm['dong_code'].nunique()}동")

    print("[3/3] 6 metric variant 계산 중...\n")
    results = compute_variants(kt, abm)

    print("=" * 60)
    print("=== 결과 (single seed, 비교 ratio 만 의미 있음) ===")
    print("=" * 60)

    print(f"\n매칭 cells: {results['n_samples']}")
    print(f"\n📌 V1  raw Pearson (baseline)              : {results['V1_raw_pearson']:+.4f}")
    print("   (sim-mode-matrix 의 ~0.79 baseline 과 비교 가능)")

    print(f"\n🔬 V2  KT residence baseline 차감          : {results['V2_kt_residual_pearson']:+.4f}")
    print("   (Phase I-a: visit residual 만 비교)")

    print(f"\n🔬 V3  양쪽 모두 baseline 차감             : {results['V3_both_residual_pearson']:+.4f}")
    print("   (Phase I-b: 가장 정밀한 visit 신호 비교)")

    print(f"\n🔬 V5  per-dong z-score 정규화             : {results['V5_per_dong_zscore_pearson']:+.4f}")
    print("   (동 magnitude 차이 제거, 시간 패턴만)")

    print(f"\n🔬 V6  residual + per-dong z-score 조합    : {results['V6_residual_zscore_pearson']:+.4f}")
    print("   (Phase I-b + 정규화)")

    print("\n🕐 V4  lagged Pearson Δt sweep:")
    for k, v in results.get("V4_lagged", {}).items():
        marker = " ← peak" if v == max(results["V4_lagged"].values()) else ""
        print(f"     {k}h : {v:+.4f}{marker}")

    print("\n" + "=" * 60)
    print("=== 해석 ===")
    print("=" * 60)
    base = results["V1_raw_pearson"]
    for label, key in [
        ("V2 residual", "V2_kt_residual_pearson"),
        ("V3 both residual", "V3_both_residual_pearson"),
        ("V5 z-score", "V5_per_dong_zscore_pearson"),
        ("V6 residual+z", "V6_residual_zscore_pearson"),
    ]:
        if key in results:
            d = results[key] - base
            sign = "+" if d > 0 else ""
            verdict = "✅ 천장 돌파" if d > 0.05 else ("⚠️ 의미 있는 lift" if d > 0.02 else "❌ noise")
            print(f"  {label:25s}: Δ {sign}{d:.4f}  {verdict}")


if __name__ == "__main__":
    main()
