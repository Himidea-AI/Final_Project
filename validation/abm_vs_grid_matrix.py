"""ABM vs 격자 생활인구 — 전체 조합 매트릭스 검증.

축:
  - 요일: 평일(월-금) / 토요일 / 일요일
  - 날씨: 맑음 / 비 / 눈
  - 계절: 봄(3-5) / 여름(6-8) / 가을(9-11) / 겨울(12-2)

각 (weekday × weather × season) 조합 → 해당 조건 만족하는 대표 날짜 1개 선정,
ABM 을 scenario.date_override + weather_override 로 실행 → 격자 실데이터 비교.

출력: 36 조합 × {Pearson, Spearman, MAPE, Peak-hour, Kendall τ} 매트릭스 CSV/콘솔.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, pearsonr, spearmanr
from sqlalchemy import create_engine, text

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

engine = create_engine(os.environ["POSTGRES_URL"])

# backend import
backend_path = REPO_ROOT / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

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

WEEKDAY_TYPES = ["평일", "토요일", "일요일"]
WEATHER_TYPES = ["맑음", "비", "눈"]
SEASONS = {"봄": (3, 4, 5), "여름": (6, 7, 8), "가을": (9, 10, 11), "겨울": (12, 1, 2)}


def classify_weather(row) -> str:
    """날씨 row → 맑음/비/눈 분류."""
    snow = float(row["snow_new"] or 0)
    rain = float(row["rain_day"] or 0)
    if snow > 0:
        return "눈"
    if rain > 5:
        return "비"
    return "맑음"


def classify_weekday(d: date) -> str:
    dow = d.weekday()
    if dow == 5:
        return "토요일"
    if dow == 6:
        return "일요일"
    return "평일"


def classify_season(d: date) -> str:
    for name, months in SEASONS.items():
        if d.month in months:
            return name
    return "?"


def pick_representative_dates() -> dict[tuple, date]:
    """grid 보유 기간에서 (weekday, weather, season) 조합별 대표 날짜 1개씩 선정."""
    sql = text("""
        SELECT w.date, w.rain_day, w.snow_new
        FROM weather_daily w
        WHERE w.stn_name='서울'
          AND w.date BETWEEN (SELECT MIN(ymd) FROM living_population_grid)
                        AND (SELECT MAX(ymd) FROM living_population_grid)
        ORDER BY w.date
    """)
    with engine.connect() as c:
        rows = c.execute(sql).mappings().all()

    buckets: dict[tuple, list[date]] = defaultdict(list)
    for r in rows:
        d = r["date"]
        if isinstance(d, str):
            d = date.fromisoformat(d)
        combo = (classify_weekday(d), classify_weather(r), classify_season(d))
        buckets[combo].append(d)

    # 각 조합에서 중간 날짜 하나 선정 (최근치 편향 회피)
    reps: dict[tuple, date] = {}
    for k, ds in buckets.items():
        if ds:
            reps[k] = ds[len(ds) // 2]
    return reps


def load_grid_day(d: date) -> pd.DataFrame:
    sql = text("""
        SELECT dong_code, tt, SUM(spop) AS total_pop
        FROM living_population_grid
        WHERE ymd = :d
        GROUP BY dong_code, tt
    """)
    with engine.connect() as c:
        return pd.read_sql(sql, c, params={"d": d.isoformat()})


def run_abm_for_scenario(target_date: date, weather: str) -> pd.DataFrame:
    """ABM scenario 주입해 실행 → trajectory 집계."""
    from src.simulation.config import (
        ModelConfig,
        PopulationMix,
        Scenario,
        TierDistribution,
    )
    from src.simulation.runner import run_simulation

    cfg = ModelConfig(
        n_personas=10000,  # 10K — cell 희소성 해소, MAPE 개선 기대
        tier_a_provider="openai",
        tier_a_model="gpt-4.1-nano",
    )
    scenario = Scenario(
        weather_override=weather,
        date_override=target_date.isoformat(),
        weekend_force=classify_weekday(target_date) != "평일",
    )
    res = run_simulation(
        cfg=cfg,
        pop=PopulationMix(),
        tier=TierDistribution(),
        scenario=scenario,
        days=1,
        use_rds=True,
        use_profiles=True,
        collect_trajectory=True,
        trajectory_sample_size=1000,
        use_policy=True,  # Policy 기반 decision — Tier S/A LLM per-tick 호출 제거 ($0.37→$0.002)
        verbose=False,
    )
    # trajectory → (dong_code, tt, agents) df
    counts: dict[tuple, int] = defaultdict(int)
    for e in res.trajectory or []:
        name = e.get("dong")
        if not name or name == "외부":
            continue
        code = MAPO_DONG_CODE.get(name)
        if not code:
            continue
        counts[(code, int(e.get("hour", 0)))] += 1
    return pd.DataFrame([{"dong_code": k[0], "tt": k[1], "agents": v} for k, v in counts.items()])


def metrics(real: pd.DataFrame, sim: pd.DataFrame) -> dict:
    merged = real.merge(sim, on=["dong_code", "tt"], how="inner")
    if merged.empty or merged["agents"].sum() == 0:
        return None
    merged["real_norm"] = merged["total_pop"] / merged["total_pop"].sum()
    merged["sim_norm"] = merged["agents"] / merged["agents"].sum()

    p_r, _ = pearsonr(merged["real_norm"], merged["sim_norm"])
    s_r, _ = spearmanr(merged["real_norm"], merged["sim_norm"])
    mape = float(
        (np.abs(merged["real_norm"] - merged["sim_norm"]) / merged["real_norm"].replace(0, np.nan)).mean() * 100
    )

    real_peak = merged.loc[merged.groupby("dong_code")["total_pop"].idxmax()].set_index("dong_code")["tt"]
    sim_peak = merged.loc[merged.groupby("dong_code")["agents"].idxmax()].set_index("dong_code")["tt"]
    common = real_peak.index.intersection(sim_peak.index)
    peak_acc = (real_peak.loc[common] == sim_peak.loc[common]).mean() if len(common) else 0

    rr = merged.groupby("dong_code")["total_pop"].sum().rank(ascending=False)
    sr = merged.groupby("dong_code")["agents"].sum().rank(ascending=False)
    kt, _ = kendalltau(rr.reindex(sr.index).dropna(), sr)

    return {
        "n": len(merged),
        "pearson": round(float(p_r), 3),
        "spearman": round(float(s_r), 3),
        "mape_pct": round(mape, 1),
        "peak_acc": round(float(peak_acc), 3),
        "kendall": round(float(kt), 3),
    }


def main():
    print("=== ABM × 격자 매트릭스 검증 ===\n")
    reps = pick_representative_dates()
    print(f"전체 조합 수: {len(WEEKDAY_TYPES) * len(WEATHER_TYPES) * len(SEASONS)} / 실 데이터 매칭: {len(reps)}\n")

    results = []
    done = 0
    total = len(reps)
    for (wd, wx, sea), d in sorted(reps.items()):
        done += 1
        label = f"{sea}·{wd}·{wx} ({d.isoformat()})"
        print(f"[{done:2}/{total}] {label}", flush=True)
        try:
            real = load_grid_day(d)
            sim = run_abm_for_scenario(d, wx)
            m = metrics(real, sim)
            if m:
                results.append({"weekday": wd, "weather": wx, "season": sea, "date": d.isoformat(), **m})
                print(
                    f"        r={m['pearson']:+.3f}  ρ={m['spearman']:+.3f}  MAPE={m['mape_pct']:.1f}%  peak={m['peak_acc']:.0%}  τ={m['kendall']:+.3f}"
                )
        except Exception as e:
            print(f"        FAILED: {e}")

    if not results:
        print("결과 없음")
        return

    df = pd.DataFrame(results)
    out_dir = REPO_ROOT / "validation" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "abm_vs_grid_matrix.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\n[saved] {csv_path}\n")

    print("=== 축별 평균 ===")
    for col in ["weekday", "weather", "season"]:
        print(f"\n-- by {col} --")
        agg = df.groupby(col)[["pearson", "spearman", "mape_pct", "peak_acc", "kendall"]].mean().round(3)
        print(agg.to_string())

    print("\n=== 전체 평균 ===")
    overall = df[["pearson", "spearman", "mape_pct", "peak_acc", "kendall"]].mean().round(3)
    print(overall.to_string())


if __name__ == "__main__":
    main()
