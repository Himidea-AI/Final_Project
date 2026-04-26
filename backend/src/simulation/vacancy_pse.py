"""Vacancy 평가의 PSE (Paired Seed Evaluation) 통합.

목적:
    vacancy_inject 의 단일 seed 결과는 매장 단위 noise dominant.
    N=5 seed 평균 + 95% CI 로 통계적으로 신뢰할 수 있는 vacancy 평가 산출.

학술 근거:
    - Paired Seed Evaluation (arXiv 2512.24145, 2025) — 같은 seed 로 baseline/treatment
      비교 시 variance 감소 + tight CI

사용:
    from src.simulation.vacancy_pse import evaluate_vacancy_pse
    result = evaluate_vacancy_pse(
        vacancy_spot={"dong": "서교동", "lat": ..., "lon": ...},
        category="카페",
        n_seeds=5,                # PSE N
        days=1,
        with_cannibalization=True,
    )
    # result["pse_summary"]["visits_per_day"] = {"mean": 8.2, "ci95": 1.4, ...}
"""

from __future__ import annotations

import statistics
from typing import Any

from .config import ModelConfig, PopulationMix, TierDistribution
from .runner import run_simulation
from .vacancy_inject import (
    DEFAULT_POPULARITY_BOOST,
    compare_to_dong_average,
    evaluate_vacancy_store,
    inject_vacancy_as_store,
    measure_cannibalization,
)
from .world_loader import load_world_from_rds


DEFAULT_SEEDS: list[int] = [42, 123, 7777, 99, 2024]


def _summarize(values: list[float]) -> dict[str, float]:
    """N 개 측정값 → mean / std / 95% CI."""
    if not values:
        return {"mean": 0, "std": 0, "ci95": 0, "min": 0, "max": 0, "n": 0}
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    sem = std / (len(values) ** 0.5) if len(values) > 1 else 0.0
    return {
        "mean": round(mean, 3),
        "std": round(std, 3),
        "ci95": round(1.96 * sem, 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "n": len(values),
    }


def evaluate_vacancy_pse(
    vacancy_spot: dict[str, Any],
    category: str,
    n_seeds: int = 5,
    days: int = 1,
    popularity_boost: float = DEFAULT_POPULARITY_BOOST,
    with_cannibalization: bool = True,
    pop_mix: PopulationMix | None = None,
    tier_dist: TierDistribution | None = None,
    cfg: ModelConfig | None = None,
    seeds: list[int] | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """Vacancy 평가를 PSE N=n_seeds 로 측정 → 신뢰구간 산출.

    Args:
        vacancy_spot: {"dong", "lat", "lon", ...}
        category: 업종
        n_seeds: PSE N (기본 5, 권장 ≥ 3)
        days: 시뮬 일수
        popularity_boost: 신규 매장 인지도 (기본 DEFAULT_POPULARITY_BOOST=5.0)
        with_cannibalization: True 면 baseline 시뮬도 같이 돌려 카니발 측정 (시간 2배)
        pop_mix / tier_dist / cfg: 시뮬 설정 (생략 시 기본값)
        seeds: 명시 seed 리스트 (생략 시 DEFAULT_SEEDS [:n_seeds])
        verbose: 진행 로그

    Returns:
        {
            "vacancy_spot", "category", "n_seeds", "days", "popularity_boost",
            "per_seed": [{...}, ...],   # seed 별 raw 결과
            "pse_summary": {            # 핵심 — 95% CI 로 보고
                "visits_per_day": {mean, std, ci95, min, max, n},
                "revenue_per_day": {...},
                "occupancy": {...},
                "vacancy_vs_avg_visits_ratio": {...},
                "vacancy_vs_avg_revenue_ratio": {...},
                "cannibalization_pct": {...},   # with_cannibalization=True 시
                "synergy_pct": {...},
            },
            "narrative": "서교동 카페 vacancy 일평균 X명 ± Y..."
        }
    """
    seeds = (seeds or DEFAULT_SEEDS)[:n_seeds]
    cfg = cfg or ModelConfig()
    if cfg.tier_s_provider not in ("mock", "openai", "anthropic", "gemini", "ollama"):
        cfg.tier_s_provider = "mock"
    if cfg.tier_a_provider not in ("mock", "openai", "anthropic", "gemini", "ollama"):
        cfg.tier_a_provider = "mock"
    pop_mix = pop_mix or PopulationMix()
    tier_dist = tier_dist or TierDistribution()

    per_seed: list[dict[str, Any]] = []

    for s in seeds:
        if verbose:
            print(f"[PSE] seed={s} 측정 중...", flush=True)

        # with-vacancy 시뮬
        world_w, hm_w = load_world_from_rds()
        vid = inject_vacancy_as_store(world_w, vacancy_spot, category, popularity_boost=popularity_boost)
        run_simulation(
            days=days,
            cfg=cfg,
            pop=pop_mix,
            tier=tier_dist,
            world=world_w,
            hours_map=hm_w,
            use_rds=False,
            use_profiles=True,
            use_policy=True,
            collect_trajectory=False,
            seed=s,
            verbose=False,
            seed_memory=True,
            memory_seed_days=14,
        )
        v_eval = evaluate_vacancy_store(world_w, vid, days_simulated=days)
        cmp = compare_to_dong_average(world_w, vid, days_simulated=days)

        seed_result: dict[str, Any] = {
            "seed": s,
            "visits_per_day": v_eval["visits_per_day"],
            "revenue_per_day": v_eval["revenue_per_day"],
            "occupancy": v_eval["occupancy"],
            "vacancy_vs_avg_visits_ratio": cmp.get("vacancy_vs_avg_visits_ratio", 0),
            "vacancy_vs_avg_revenue_ratio": cmp.get("vacancy_vs_avg_revenue_ratio", 0),
            "dong_category_n_stores": cmp.get("dong_category_n_stores", 0),
        }

        # cannibalization (with baseline 시뮬 추가)
        if with_cannibalization:
            world_b, hm_b = load_world_from_rds()
            run_simulation(
                days=days,
                cfg=cfg,
                pop=pop_mix,
                tier=tier_dist,
                world=world_b,
                hours_map=hm_b,
                use_rds=False,
                use_profiles=True,
                use_policy=True,
                collect_trajectory=False,
                seed=s,
                verbose=False,
                seed_memory=True,
                memory_seed_days=14,
            )
            cann = measure_cannibalization(world_w, world_b, vid, radius_m=500)
            seed_result["cannibalization_pct"] = cann["same_category"]["cannibalization_pct"]
            seed_result["synergy_pct"] = cann["other_category"]["synergy_pct"]
            seed_result["same_cat_delta_visits"] = cann["same_category"]["delta_visits"]
            seed_result["same_cat_n_stores"] = cann["same_category"]["n_stores"]

        per_seed.append(seed_result)

    # PSE summary
    metric_keys = [
        "visits_per_day",
        "revenue_per_day",
        "occupancy",
        "vacancy_vs_avg_visits_ratio",
        "vacancy_vs_avg_revenue_ratio",
    ]
    if with_cannibalization:
        metric_keys += ["cannibalization_pct", "synergy_pct", "same_cat_delta_visits"]

    pse_summary = {k: _summarize([r[k] for r in per_seed if k in r]) for k in metric_keys}

    # 자연어 narrative
    vis = pse_summary["visits_per_day"]
    rev = pse_summary["revenue_per_day"]
    ratio = pse_summary["vacancy_vs_avg_visits_ratio"]
    narrative = (
        f"{vacancy_spot.get('dong', '?')} {category} 신규 매장 "
        f"(popularity_boost={popularity_boost}, PSE N={n_seeds}):\n"
        f"  - 일평균 방문 : {vis['mean']:.1f} ± {vis['ci95']:.1f} 명 "
        f"(95% CI, range [{vis['min']:.0f}, {vis['max']:.0f}])\n"
        f"  - 일평균 매출 : {rev['mean'] / 10000:.0f} ± {rev['ci95'] / 10000:.0f} 만원\n"
        f"  - 동 평균 대비: {ratio['mean']:.1f} ± {ratio['ci95']:.1f} 배"
    )
    if with_cannibalization:
        cann = pse_summary["cannibalization_pct"]
        narrative += f"\n  - 카니발 % : {cann['mean']:+.1f} ± {cann['ci95']:.1f}% (- = 시너지, + = 잠식)"

    return {
        "vacancy_spot": vacancy_spot,
        "category": category,
        "n_seeds": n_seeds,
        "days": days,
        "popularity_boost": popularity_boost,
        "with_cannibalization": with_cannibalization,
        "per_seed": per_seed,
        "pse_summary": pse_summary,
        "narrative": narrative,
    }
