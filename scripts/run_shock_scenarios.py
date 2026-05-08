"""ABM 충격 시나리오 비교 — base vs rent_shock vs weekend vs rainy.

발표/검증용. 동일 seed 로 4개 시나리오 실행 → 매출/카테고리별 차분 → JSON + markdown.

사용:
    python scripts/run_shock_scenarios.py --n-personas 1000 --seed 42
    python scripts/run_shock_scenarios.py --n-personas 5000  # 무거움, ~$0.04 LLM 비용 시나리오당

출력:
    data/processed/shock_scenarios_<timestamp>.json  # raw 결과
    docs/abm-simulation/shock-scenarios-<date>.md   # 차분 보고서
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from src.simulation.config import ModelConfig, Scenario  # noqa: E402
from src.simulation.runner import run_simulation  # noqa: E402

SCENARIOS: dict[str, Scenario] = {
    "base": Scenario(),
    "rent_shock_30pct": Scenario(rent_shock_pct=0.30),
    "weekend_force": Scenario(weekend_force=True),
    "rainy": Scenario(weather_override="비"),
}


def _aggregate(result: dict) -> dict:
    """run_simulation 결과 → 비교용 핵심 metric 추출."""
    cats = result.get("category_totals") or {}
    if not isinstance(cats, dict):
        cats = {}
    dongs = result.get("dong_totals") or {}
    total_rev = sum(c.get("revenue", 0.0) for c in cats.values())
    total_visits = sum(c.get("visits", 0) for c in cats.values())
    return {
        "total_revenue": round(total_rev, 0),
        "total_visits": total_visits,
        "by_category": {k: round(v.get("revenue", 0), 0) for k, v in cats.items()},
        "by_dong_top5": dict(
            sorted(
                ((k, round(v.get("revenue", 0), 0)) for k, v in dongs.items()),
                key=lambda x: x[1],
                reverse=True,
            )[:5]
        ),
        "estimated_cost_usd": result.get("estimated_cost_usd", 0.0),
    }


def _diff_pct(base: float, scenario: float) -> float:
    if base == 0:
        return 0.0
    return round((scenario - base) / base * 100, 2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-personas", type=int, default=1000, help="agent 수 (기본 1000)")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--use-rds", action="store_true", help="RDS world 로드 (기본은 synthetic)")
    args = parser.parse_args()

    cfg = ModelConfig(n_personas=args.n_personas)
    results: dict[str, dict] = {}

    print(f"[shock] N={args.n_personas}, days={args.days}, seed={args.seed}\n")
    for name, scenario in SCENARIOS.items():
        t0 = time.time()
        print(f"[run] {name}...")
        sim = run_simulation(
            days=args.days,
            cfg=cfg,
            seed=args.seed,
            scenario=scenario,
            verbose=False,
            use_rds=args.use_rds,
        )
        r = {
            "category_totals": getattr(sim, "category_totals", None) or {},
            "dong_totals": getattr(sim, "dong_totals", None) or {},
            "estimated_cost_usd": getattr(sim, "estimated_cost_usd", 0.0),
        }
        results[name] = _aggregate(r)
        results[name]["elapsed_sec"] = round(time.time() - t0, 1)
        print(
            f"  rev={results[name]['total_revenue']:,.0f} visits={results[name]['total_visits']:,} cost=${results[name]['estimated_cost_usd']}"
        )

    # 차분 (base 대비)
    base = results["base"]
    diff_table: dict[str, dict] = {}
    for name, r in results.items():
        if name == "base":
            continue
        diff_table[name] = {
            "revenue_pct": _diff_pct(base["total_revenue"], r["total_revenue"]),
            "visits_pct": _diff_pct(base["total_visits"], r["total_visits"]),
            "by_category_pct": {k: _diff_pct(base["by_category"].get(k, 0), v) for k, v in r["by_category"].items()},
        }

    out = {
        "config": {"n_personas": args.n_personas, "days": args.days, "seed": args.seed},
        "scenarios": results,
        "diff_vs_base": diff_table,
        "generated_at": datetime.now().isoformat(),
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = ROOT / "data" / "processed" / f"shock_scenarios_{ts}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[save] {json_path}")

    # markdown 보고서
    md = [f"# ABM 충격 시나리오 비교 ({datetime.now().strftime('%Y-%m-%d')})\n"]
    md.append(f"- N={args.n_personas} agents, days={args.days}, seed={args.seed}\n")
    md.append("## 시나리오별 핵심 지표\n")
    md.append("| 시나리오 | 매출(₩) | 방문 | 비용($) |")
    md.append("|---------|--------:|-----:|-------:|")
    for name, r in results.items():
        md.append(f"| {name} | {r['total_revenue']:,.0f} | {r['total_visits']:,} | {r['estimated_cost_usd']:.4f} |")
    md.append("\n## Base 대비 변화율 (%)\n")
    md.append("| 시나리오 | 매출 % | 방문 % |")
    md.append("|---------|------:|------:|")
    for name, d in diff_table.items():
        md.append(f"| {name} | {d['revenue_pct']:+.2f} | {d['visits_pct']:+.2f} |")

    md_path = ROOT / "docs" / "abm-simulation" / f"shock-scenarios-{datetime.now().strftime('%Y-%m-%d')}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"[save] {md_path}")


if __name__ == "__main__":
    main()
