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

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
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


def diagnose_failure(tracks: dict[str, dict]) -> list[str]:
    """5 트랙 결과 → fail 진단 메시지 list."""
    diagnoses: list[str] = []
    if not tracks["v1a"].get("pass"):
        r = tracks["v1a"].get("pearson_r")
        mape = tracks["v1a"].get("mape")
        diagnoses.append(
            f"V1a fail (r={r}, MAPE={mape}): 동×업종 매출 분포 격차. "
            f"가능 원인: (1) popularity_boost=5.0, (2) 정적 시뮬 한계 [브레인스토밍 옵션 3 future spec], "
            f"(3) IPF calibration 미적용. → IPF + boost=1.0 재측정 권장."
        )
    if not tracks["v1b"].get("pass"):
        r = tracks["v1b"].get("pearson_r")
        diagnoses.append(
            f"V1b fail (r={r}): 방문 수 분포 격차. visits 의 sample size noise 가능. "
            f"→ agent 1000→3000 또는 PSE n 늘리기."
        )
    if not tracks["v1c"].get("pass"):
        r = tracks["v1c"].get("mean_ratio")
        if r is not None and r > V1C_RATIO_MAX:
            diagnoses.append(
                f"V1c fail (ratio={r} > {V1C_RATIO_MAX}): 시뮬 매장 동 평균보다 {(r - 1) * 100:.0f}% 높음. "
                f"popularity_boost 또는 페르소나 spend_tendency 과대. → boost=1.0 재측정."
            )
        elif r is not None:
            diagnoses.append(
                f"V1c fail (ratio={r} < {V1C_RATIO_MIN}): 시뮬 매장 동 평균의 {r * 100:.0f}% 과소. "
                f"메뉴 가격 source 점검 또는 visits 과소."
            )
    if not tracks["v2"].get("pass"):
        if tracks["v2"].get("status") == "skipped":
            diagnoses.append("V2 skipped: ftc 에 brand row 없음. → 브랜드명 alias 점검.")
        else:
            r = tracks["v2"].get("ratio")
            if r is not None and r > V2_RATIO_MAX:
                diagnoses.append(
                    f"V2 fail (ratio={r} > {V2_RATIO_MAX}): 시뮬 매출 전국 평균 {(r - 1) * 100:.0f}% 초과."
                )
            elif r is not None:
                diagnoses.append(f"V2 fail (ratio={r} < {V2_RATIO_MIN}): 시뮬 매출 전국 평균의 {r * 100:.0f}% 미만.")
    if not tracks["ci"].get("pass"):
        ci = tracks["ci"].get("ci_ratio")
        if ci is not None:
            diagnoses.append(
                f"CI fail (CI/mean={ci * 100:.1f}% > {CI_MAX * 100:.0f}%): PSE 변동 과다. "
                f"→ n_seeds 3→5→10 또는 days 90→180."
            )
    return diagnoses


def _collect_actual_data(brand_name: str, category: str, multi_quarter_avg: int) -> dict[str, Any]:
    """실측 데이터 수집 — district_sales, sales_imp_mapo, ftc.

    실제 구현은 SQL/CSV 호출. 본 spec 의 spec 6.2 Step A 참조.
    Mock-friendly 인터페이스 (테스트에서 patch).
    """
    import os

    import pandas as pd
    from sqlalchemy import text
    from src.database.sync_engine import get_sync_engine

    engine = get_sync_engine(os.environ["POSTGRES_URL"])

    # district_sales — 마포 64-cell 분기 매출 + 건수, multi-quarter 평균
    sql_district = text("""
        SELECT dong_name, industry_name,
               AVG(monthly_sales)::bigint AS quarterly_sales_avg,
               AVG(monthly_count)::bigint AS quarterly_count_avg
          FROM district_sales
         WHERE dong_code LIKE '114%'
           AND quarter IN (
               SELECT DISTINCT quarter FROM district_sales
                WHERE dong_code LIKE '114%'
                ORDER BY quarter DESC LIMIT :n
           )
         GROUP BY dong_name, industry_name
    """)
    district_sales: dict[tuple, float] = {}
    district_count: dict[tuple, float] = {}
    with engine.connect() as conn:
        for r in conn.execute(sql_district, {"n": multi_quarter_avg}).mappings():
            key = (r["dong_name"], r["industry_name"])
            district_sales[key] = float(r["quarterly_sales_avg"] or 0)
            district_count[key] = float(r["quarterly_count_avg"] or 0)

    # per_store_avg — sales_imp_mapo.csv 의 monthly_sales / store_count
    csv_path = Path("data/processed/sales_imp_mapo.csv")
    per_store_avg: dict[tuple, float] = {}
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        # 최근 분기 N개 평균
        recent_quarters = sorted(df["quarter"].unique())[-multi_quarter_avg:]
        df = df[df["quarter"].isin(recent_quarters)]
        df = df[df["store_count"] > 0]
        df["per_store"] = df["monthly_sales"] / df["store_count"]
        agg = df.groupby(["dong_name", "industry_name"])["per_store"].mean()
        per_store_avg = {idx: float(v) for idx, v in agg.items()}

    # ftc — brand 연 평균 매출 (천원 → 원)
    sql_ftc = text("""
        SELECT AVG("avrgSlsAmt")::bigint AS yearly_avg_thousand
          FROM ftc_brand_franchise
         WHERE "brandNm" ILIKE :brand
           AND yr = (SELECT MAX(yr) FROM ftc_brand_franchise WHERE "brandNm" ILIKE :brand)
    """)
    ftc_avg = None
    with engine.connect() as conn:
        row = conn.execute(sql_ftc, {"brand": f"%{brand_name}%"}).mappings().first()
        if row and row["yearly_avg_thousand"]:
            ftc_avg = int(row["yearly_avg_thousand"]) * 1000  # 천원 → 원

    return {
        "district_sales": district_sales,
        "district_count": district_count,
        "per_store_avg": per_store_avg,
        "ftc_avg": ftc_avg,
    }


def _run_validation_simulations(brand_name: str, category: str, days: int, n_seeds: int) -> dict[str, Any]:
    """시뮬 데이터 수집 — 동×업종 매트릭스 + V2 단일 vacancy.

    실제 시뮬 호출 — ~9시간 소요 (days=90 × n_seeds × 2 시뮬).
    Mock-friendly 인터페이스 (테스트에서 patch).
    """
    from statistics import mean

    from src.services.brand_menu_loader import load_brand_menu_items
    from src.simulation.config import ModelConfig, PopulationMix, TierDistribution
    from src.simulation.runner import run_simulation
    from src.simulation.vacancy_pse import evaluate_vacancy_pse
    from src.simulation.world_loader import load_world_from_rds

    DEFAULT_SEEDS = [42, 123, 7777, 99, 2024][:n_seeds]
    cfg = ModelConfig()
    cfg.tier_s_provider = "mock"  # 검증은 항상 mock 강제
    cfg.tier_a_provider = "mock"

    # ① 동×업종 매트릭스 (vacancy 미주입, 일반 시뮬, days × N=n_seeds)
    matrix_revenues: list[dict[tuple, float]] = []
    matrix_visits: list[dict[tuple, float]] = []
    per_store_per_seed: list[dict[tuple, float]] = []
    for s in DEFAULT_SEEDS:
        logger.info(f"[validator] 동×업종 매트릭스 시뮬 seed={s} ({days}일)")
        world, hm = load_world_from_rds()
        run_simulation(
            days=days,
            cfg=cfg,
            pop=PopulationMix(),
            tier=TierDistribution(),
            world=world,
            hours_map=hm,
            use_rds=False,
            use_profiles=True,
            use_policy=True,
            collect_trajectory=False,
            seed=s,
            verbose=False,
            seed_memory=True,
            memory_seed_days=14,
        )
        # 동×업종 합산
        rev_agg: dict[tuple, float] = {}
        vis_agg: dict[tuple, float] = {}
        cnt_agg: dict[tuple, int] = {}
        for store in world.stores.values():
            key = (store.dong, store.category)
            rev_agg[key] = rev_agg.get(key, 0) + store.revenue_today
            vis_agg[key] = vis_agg.get(key, 0) + store.visits_today
            cnt_agg[key] = cnt_agg.get(key, 0) + 1
        matrix_revenues.append(rev_agg)
        matrix_visits.append(vis_agg)
        # per-store 평균
        per_store_per_seed.append({k: rev_agg[k] / max(cnt_agg[k], 1) for k in rev_agg})

    # 평균 (across seeds)
    all_keys = set().union(*(m.keys() for m in matrix_revenues))
    revenue_avg = {k: mean(m.get(k, 0) for m in matrix_revenues) for k in all_keys}
    visits_avg = {k: mean(m.get(k, 0) for m in matrix_visits) for k in all_keys}
    per_store_avg = {k: mean(m.get(k, 0) for m in per_store_per_seed) for k in all_keys}

    # ② 단일 vacancy V2 시뮬 — 대표 위치
    spot = _pick_representative_spot(brand_name, category)
    menu_items = load_brand_menu_items(brand_name)
    pse_result = evaluate_vacancy_pse(
        vacancy_spot=spot,
        category=category,
        n_seeds=n_seeds,
        days=days,
        with_cannibalization=False,
        cfg=cfg,
        menu_items=menu_items,
    )
    rev_per_day = pse_result["pse_summary"]["revenue_per_day"]["mean"]
    vacancy_yearly_rev = (rev_per_day / max(days, 1)) * 365 if days >= 30 else rev_per_day * 365 / days

    return {
        "dong_industry_revenue": revenue_avg,
        "dong_industry_visits": visits_avg,
        "per_store_revenue": per_store_avg,
        "vacancy_yearly_rev": vacancy_yearly_rev,
        "pse_summary": pse_result["pse_summary"],
    }


def _pick_representative_spot(brand_name: str, category: str) -> dict[str, Any]:
    """V2 시뮬용 단일 spot — 마포 브랜드 매장 좌표 중심점에 가장 가까운 실제 매장."""
    from statistics import mean as _mean

    from src.services.brand_mapping_resolver import get_all_mapo_stores_by_brand

    stores = get_all_mapo_stores_by_brand(brand_name)
    if not stores:
        from src.services.brand_menu_loader import BrandNotFoundError

        raise BrandNotFoundError(f"마포에 '{brand_name}' 매장 없음")
    center_lat = _mean(s["lat"] for s in stores if s.get("lat"))
    center_lon = _mean(s["lon"] for s in stores if s.get("lon"))

    def dist_sq(s):
        return (s["lat"] - center_lat) ** 2 + (s["lon"] - center_lon) ** 2

    nearest = min((s for s in stores if s.get("lat")), key=dist_sq)
    return {"dong": nearest["dong_name"], "lat": nearest["lat"], "lon": nearest["lon"]}


def _dump_report(report: dict[str, Any], output_dir: Path, brand_name: str) -> None:
    """JSON + Markdown report dump."""
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_brand = brand_name.replace("/", "_").replace(" ", "_")
    json_path = output_dir / f"{safe_brand}_5track.json"
    md_path = output_dir / f"{safe_brand}_5track_report.md"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    # Markdown report
    lines = [
        f"# {brand_name} 5트랙 검증 Report\n",
        f"- 검증 시각: {report['timestamp']}",
        f"- 카테고리: {report['category']}",
        f"- 설정: days={report['config']['days']}, n_seeds={report['config']['n_seeds']}, multi_quarter_avg={report['config']['multi_quarter_avg']}",
        f"- **production_ready: {'✅ YES' if report['production_ready'] else '❌ NO'}**\n",
        "## 트랙별 결과\n",
        "| 트랙 | 측정값 | 합격선 | 결과 |",
        "|---|---|---|---|",
    ]
    for k in ["v1a", "v1b", "v1c", "v2", "ci"]:
        t = report["tracks"][k]
        passed = "✅ PASS" if t.get("pass") else "❌ FAIL"
        if t.get("status") == "skipped":
            passed = "⚠️ SKIPPED"
        elif t.get("status") == "incomplete":
            passed = "⚠️ INCOMPLETE"
        if k == "v1a":
            value = f"r={t.get('pearson_r')}, MAPE={t.get('mape')}"
            thresh = f"r ≥ {V1A_R_MIN}, MAPE ≤ {V1A_MAPE_MAX}"
        elif k == "v1b":
            value = f"r={t.get('pearson_r')}, MAPE={t.get('mape')}"
            thresh = f"r ≥ {V1B_R_MIN}, MAPE ≤ {V1B_MAPE_MAX}"
        elif k == "v1c":
            value = f"mean_ratio={t.get('mean_ratio')}"
            thresh = f"{V1C_RATIO_MIN}~{V1C_RATIO_MAX}"
        elif k == "v2":
            value = f"ratio={t.get('ratio')}"
            thresh = f"{V2_RATIO_MIN}~{V2_RATIO_MAX}"
        else:
            value = f"ci_ratio={t.get('ci_ratio')}"
            thresh = f"≤ {CI_MAX}"
        lines.append(f"| {k.upper()} | {value} | {thresh} | {passed} |")

    if report.get("diagnoses"):
        lines.append("\n## 진단\n")
        for d in report["diagnoses"]:
            lines.append(f"- {d}")

    if report.get("limitations"):
        lines.append("\n## Limitations\n")
        for limit in report["limitations"]:
            lines.append(f"- {limit}")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"[validator] report dumped: {json_path}, {md_path}")


def run_5track_validation(
    brand_name: str,
    category: str = "카페",
    days: int = 90,
    n_seeds: int = 3,
    multi_quarter_avg: int = 4,
    output_dir: Path | str = Path("validation/results/"),
    verbose: bool = True,
) -> dict[str, Any]:
    """5트랙 검증 protocol 1회 실행.

    Args:
        brand_name: 평가 브랜드 (예: "이디야"). 마포 매장 0 시 BrandNotFoundError.
        category: 업종 (default "카페").
        days: 시뮬 일수 (default 90 = 분기).
        n_seeds: PSE N (default 3).
        multi_quarter_avg: 실측 ground truth 평균 분기 수 (default 4 = 1년).
        output_dir: report dump 디렉토리.
        verbose: 진행 로그.

    Returns:
        report dict — tracks, production_ready, diagnoses, limitations.
    """
    if verbose:
        logger.info(f"[validator] '{brand_name}' 5트랙 검증 시작")
    actual = _collect_actual_data(brand_name, category, multi_quarter_avg)
    sim = _run_validation_simulations(brand_name, category, days, n_seeds)

    tracks = {
        "v1a": _track_v1a(sim["dong_industry_revenue"], actual["district_sales"]),
        "v1b": _track_v1b(sim["dong_industry_visits"], actual["district_count"]),
        "v1c": _track_v1c(sim["per_store_revenue"], actual["per_store_avg"]),
        "v2": _track_v2(sim["vacancy_yearly_rev"], actual["ftc_avg"]),
        "ci": _track_ci(sim["pse_summary"]),
    }

    production_ready = all(t.get("pass", False) for t in tracks.values())
    diagnoses = diagnose_failure(tracks) if not production_ready else []

    report = {
        "brand_name": brand_name,
        "category": category,
        "config": {"days": days, "n_seeds": n_seeds, "multi_quarter_avg": multi_quarter_avg},
        "tracks": tracks,
        "production_ready": production_ready,
        "diagnoses": diagnoses,
        "limitations": [
            "정적 시뮬 환경 — 90일 동안 같은 날씨/같은 월 (브레인스토밍 옵션 3 future spec).",
            "매장 단위 실측 매출 부재 — 동×업종 평균으로 V1c 측정.",
            "검증은 mock 강제 — Mode C/D LLM 활성 시 결정 분포 약간 변화 가능 (margin ~3%).",
        ],
        "timestamp": datetime.now(UTC).isoformat(),
    }
    _dump_report(report, Path(output_dir), brand_name)
    if verbose:
        status = "✅ production-ready" if production_ready else "❌ production-not-ready"
        logger.info(f"[validator] '{brand_name}' 검증 완료 — {status}")
    return report
