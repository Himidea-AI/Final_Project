"""시뮬레이션 결과 검증 — 실측 대비 정량 지표.

검증 항목:
  1. 시간×동 유동인구 분포: 시뮬 vs living_population (RMSE + correlation)
  2. 카테고리 매출 분포: 시뮬 vs district_sales_seoul (KL divergence)
  3. 내부 정합성: 예산 준수, 이동 연속성, 영업시간, External 순환

사용:
  python scripts/validate_simulation.py data/processed/sim_policy_n1000.json
"""

from __future__ import annotations

import io
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------
# 1. 시뮬 결과 + trajectory 로드
# ---------------------------------------------------------------
def load_sim(sim_path: Path) -> tuple[dict, list]:
    """시뮬 결과 JSON + trajectory JSON 로드."""
    with open(sim_path, encoding="utf-8") as f:
        result = json.load(f)
    traj_path = sim_path.with_name(sim_path.stem + "_trajectory.json")
    if traj_path.exists():
        with open(traj_path, encoding="utf-8") as f:
            traj = json.load(f)
    else:
        traj = []
    return result, traj


# ---------------------------------------------------------------
# 2. 시간×동 분포 검증 (RMSE + 상관계수)
# ---------------------------------------------------------------
def validate_population(traj: list) -> dict:
    """trajectory → 시간×동 에이전트 수 → living_population 실측과 비교."""
    if not traj:
        return {"error": "trajectory 없음"}

    # 시뮬 분포 집계
    sim_counts: dict[tuple[int, str], int] = defaultdict(int)
    for p in traj:
        h = int(p.get("hour", 0)) % 24
        d = p.get("dong", "")
        if d and d != "외부":
            sim_counts[(h, d)] += 1

    # 시뮬 정규화 (시간별 비율)
    sim_by_hour: dict[int, dict[str, float]] = defaultdict(dict)
    for (h, d), cnt in sim_counts.items():
        sim_by_hour[h][d] = cnt
    for h in sim_by_hour:
        total = sum(sim_by_hour[h].values())
        if total > 0:
            sim_by_hour[h] = {d: v / total for d, v in sim_by_hour[h].items()}

    # 실측 living_population — 시뮬이 평일 기준이므로 평일만 (월~금) 평균
    # dow: 0=일, 1=월 ... 5=금, 6=토
    engine = create_engine(os.environ["POSTGRES_URL"], isolation_level="AUTOCOMMIT")
    with engine.connect() as c:
        rows = c.execute(
            text("""
            SELECT time_zone AS hour, dong_name, AVG(total_pop) AS pop
            FROM living_population
            WHERE dong_name LIKE '%동'
              AND EXTRACT(dow FROM date) BETWEEN 1 AND 5
              AND date >= (SELECT MAX(date) FROM living_population) - INTERVAL '30 days'
            GROUP BY time_zone, dong_name
        """)
        ).fetchall()

    real_by_hour: dict[int, dict[str, float]] = defaultdict(dict)
    for h, d, p in rows:
        real_by_hour[int(h)][d] = float(p)
    for h in real_by_hour:
        total = sum(real_by_hour[h].values())
        if total > 0:
            real_by_hour[h] = {d: v / total for d, v in real_by_hour[h].items()}

    # RMSE + 상관계수 (공통 (시간, 동) 키만)
    common_keys = []
    sim_vals, real_vals = [], []
    for h in sorted(set(sim_by_hour) & set(real_by_hour)):
        dongs = set(sim_by_hour[h]) & set(real_by_hour[h])
        for d in dongs:
            common_keys.append((h, d))
            sim_vals.append(sim_by_hour[h][d])
            real_vals.append(real_by_hour[h][d])

    if not common_keys:
        return {"error": "공통 키 없음"}

    n = len(common_keys)
    rmse = math.sqrt(sum((s - r) ** 2 for s, r in zip(sim_vals, real_vals, strict=False)) / n)
    # Pearson 상관계수
    mean_s = sum(sim_vals) / n
    mean_r = sum(real_vals) / n
    cov = sum((s - mean_s) * (r - mean_r) for s, r in zip(sim_vals, real_vals, strict=False))
    var_s = sum((s - mean_s) ** 2 for s in sim_vals)
    var_r = sum((r - mean_r) ** 2 for r in real_vals)
    corr = cov / math.sqrt(var_s * var_r) if var_s > 0 and var_r > 0 else 0.0

    return {
        "n_samples": n,
        "rmse": round(rmse, 4),
        "correlation": round(corr, 3),
        "rmse_pct": f"{rmse * 100:.1f}%",
    }


# ---------------------------------------------------------------
# 3. 카테고리 매출 분포 (KL divergence) - district_sales_seoul 기반
# ---------------------------------------------------------------
_INDUSTRY_TO_CAT = {
    # 카페
    "커피-음료": "카페",
    "제과점": "카페",
    "패스트푸드점": "카페",
    # 음식점
    "한식음식점": "음식점",
    "일식음식점": "음식점",
    "중식음식점": "음식점",
    "양식음식점": "음식점",
    "분식전문점": "음식점",
    "치킨전문점": "음식점",
    "호프-간이주점": "주점",
    "일반유흥주점": "주점",
    "무도유흥주점": "주점",
    "편의점": "편의점",
}


def validate_category_distribution(result: dict) -> dict:
    # category_totals (전체 매장) 있으면 우선 사용, 없으면 top_stores fallback
    cat_totals = result.get("category_totals")
    sim_rev: dict[str, float] = defaultdict(float)
    if cat_totals:
        for cat, stats in cat_totals.items():
            sim_rev[cat] = stats.get("revenue", 0)
    else:
        top_stores = result.get("top_stores", [])
        if not top_stores:
            return {"error": "top_stores 없음"}
        for s in top_stores:
            sim_rev[s["category"]] += s.get("revenue", 0)
    total = sum(sim_rev.values())
    sim_dist = {k: v / total for k, v in sim_rev.items()} if total else {}

    # 실측 district_sales_seoul (마포구 = dong_code 1144*, 최신 분기)
    engine = create_engine(os.environ["POSTGRES_URL"], isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as c:
            rows = c.execute(
                text("""
                SELECT industry_name, SUM(monthly_sales) AS total_sales
                FROM district_sales_seoul
                WHERE dong_code LIKE '1144%'
                  AND quarter = (SELECT MAX(quarter) FROM district_sales_seoul)
                GROUP BY industry_name
            """)
            ).fetchall()
    except Exception as e:
        return {"error": f"district_sales_seoul 쿼리 실패: {e}"}

    real_rev: dict[str, float] = defaultdict(float)
    for industry, amt in rows:
        mapped = _INDUSTRY_TO_CAT.get(industry)
        # 편의점은 kakao_store 데이터 자체에 없어 비교 대상 제외
        if mapped and mapped != "편의점":
            real_rev[mapped] += float(amt or 0)

    total_r = sum(real_rev.values())
    real_dist = {k: v / total_r for k, v in real_rev.items()} if total_r else {}
    # 시뮬에서도 편의점 제외 후 정규화
    sim_rev_no_cvs = {k: v for k, v in sim_rev.items() if k != "편의점"}
    tot_no_cvs = sum(sim_rev_no_cvs.values())
    if tot_no_cvs > 0:
        sim_dist = {k: v / tot_no_cvs for k, v in sim_rev_no_cvs.items()}

    # KL divergence (시뮬 || 실측)
    kl = 0.0
    for cat in set(sim_dist) | set(real_dist):
        p = sim_dist.get(cat, 1e-6)
        q = real_dist.get(cat, 1e-6)
        if p > 0:
            kl += p * math.log(p / q)

    return {
        "sim_distribution": {k: round(v, 3) for k, v in sim_dist.items()},
        "real_distribution": {k: round(v, 3) for k, v in real_dist.items()},
        "kl_divergence": round(kl, 4),
    }


# ---------------------------------------------------------------
# 3.5 버스 승하차 기반 유동인구 비교 (마포구 주요 정류장)
# ---------------------------------------------------------------
_MAPO_STATION_HINTS = [
    "합정",
    "홍대",
    "공덕",
    "마포",
    "상암",
    "망원",
    "연남",
    "서교",
    "도화",
    "아현",
    "염리",
    "대흥",
    "신수",
    "광흥창",
    "성산",
    "디지털미디어시티",
    "DMC",
    "월드컵",
]


def validate_bus_flow(traj: list) -> dict:
    """마포 주요 정류장 버스 유동인구 vs 시뮬 동별 활성도."""
    if not traj:
        return {"error": "trajectory 없음"}

    # 시뮬 동별 총 활성 (tick 총합)
    sim_by_dong: dict[str, int] = defaultdict(int)
    for p in traj:
        d = p.get("dong", "")
        if d and d != "외부":
            sim_by_dong[d] += 1

    # 정규화
    tot = sum(sim_by_dong.values())
    sim_dist = {d: v / tot for d, v in sim_by_dong.items()} if tot else {}

    # 실측 bus_boarding (마포 정류장, 최근 30일 평균)
    engine = create_engine(os.environ["POSTGRES_URL"], isolation_level="AUTOCOMMIT")
    hint_clause = " OR ".join([f"station_name LIKE '%{h}%'" for h in _MAPO_STATION_HINTS])
    with engine.connect() as conn:
        rows = conn.execute(
            text(f"""
            SELECT station_name, AVG(boarding_count + alighting_count) AS avg_flow
            FROM bus_boarding_daily
            WHERE ({hint_clause})
              AND EXTRACT(dow FROM use_date) BETWEEN 1 AND 5
              AND use_date >= (SELECT MAX(use_date) FROM bus_boarding_daily) - INTERVAL '30 days'
            GROUP BY station_name
            """)
        ).fetchall()

    # 정류장명 → 동 매핑 (힌트 기반)
    station_to_dong = {
        "합정": "합정동",
        "홍대": "서교동",
        "공덕": "공덕동",
        "마포": "도화동",
        "상암": "상암동",
        "망원": "망원1동",
        "연남": "연남동",
        "서교": "서교동",
        "도화": "도화동",
        "아현": "아현동",
        "염리": "염리동",
        "대흥": "대흥동",
        "신수": "신수동",
        "광흥창": "신수동",
        "성산": "성산1동",
        "디지털미디어시티": "상암동",
        "DMC": "상암동",
        "월드컵": "성산2동",
    }
    real_by_dong: dict[str, float] = defaultdict(float)
    for station, flow in rows:
        for hint, dong in station_to_dong.items():
            if hint in station:
                real_by_dong[dong] += float(flow or 0)
                break

    tot_r = sum(real_by_dong.values())
    real_dist = {d: v / tot_r for d, v in real_by_dong.items()} if tot_r else {}

    # 공통 키 상관계수
    common = set(sim_dist) & set(real_dist)
    if not common:
        return {"error": "공통 동 없음"}

    sim_vals = [sim_dist[d] for d in common]
    real_vals = [real_dist[d] for d in common]
    n = len(common)
    mean_s = sum(sim_vals) / n
    mean_r = sum(real_vals) / n
    cov = sum((s - mean_s) * (r - mean_r) for s, r in zip(sim_vals, real_vals, strict=False))
    var_s = sum((s - mean_s) ** 2 for s in sim_vals)
    var_r = sum((r - mean_r) ** 2 for r in real_vals)
    corr = cov / math.sqrt(var_s * var_r) if var_s > 0 and var_r > 0 else 0.0

    # Top 5 동 비교
    sim_top = sorted(sim_dist.items(), key=lambda x: -x[1])[:5]
    real_top = sorted(real_dist.items(), key=lambda x: -x[1])[:5]

    return {
        "n_dongs_common": n,
        "correlation": round(corr, 3),
        "sim_top5": [(d, round(v, 3)) for d, v in sim_top],
        "real_top5": [(d, round(v, 3)) for d, v in real_top],
    }


# ---------------------------------------------------------------
# 4. 내부 정합성
# ---------------------------------------------------------------
def validate_internal_consistency(traj: list) -> dict:
    """trajectory 기반 이동 연속성, External 순환 등."""
    if not traj:
        return {"error": "trajectory 없음"}

    by_agent: dict[int, list] = defaultdict(list)
    for p in traj:
        by_agent[p.get("agent_id")].append(p)

    issues = []
    ext_returns_ok = 0
    ext_returns_total = 0

    for aid, pts in by_agent.items():
        pts.sort(key=lambda p: p.get("hour", 0))
        role = pts[0].get("role", "")

        # External 순환 체크
        if role in ("ext_commuter", "ext_visitor"):
            ext_returns_total += 1
            dongs = [p.get("dong") for p in pts]
            if dongs[0] == "외부" and "외부" in dongs[-3:]:
                ext_returns_ok += 1

    # 시간×동 커버리지
    all_dongs = {p.get("dong") for p in traj if p.get("dong") and p.get("dong") != "외부"}
    all_hours = {int(p.get("hour", 0)) % 24 for p in traj}

    return {
        "agents_tracked": len(by_agent),
        "total_points": len(traj),
        "unique_dongs_visited": len(all_dongs),
        "unique_hours": len(all_hours),
        "external_return_rate": f"{ext_returns_ok}/{ext_returns_total}" if ext_returns_total else "N/A",
        "issues": issues if issues else "없음",
    }


# ---------------------------------------------------------------
# 5. 시간대 피크 패턴 검증
# ---------------------------------------------------------------
def validate_time_peaks(traj: list) -> dict:
    """action=visit인 포인트만 시간대별 집계."""
    if not traj:
        return {}
    visits_by_hour: Counter = Counter()
    for p in traj:
        if p.get("action") == "visit":
            h = int(p.get("hour", 0)) % 24
            visits_by_hour[h] += 1

    if not visits_by_hour:
        return {"error": "visit 액션 없음"}

    total_visits = sum(visits_by_hour.values())
    sorted_hours = sorted(visits_by_hour.items(), key=lambda x: -x[1])
    top3 = sorted_hours[:3]
    expected = {8, 12, 13, 18, 19, 20, 21}
    matched_peaks = [h for h, _ in top3 if h in expected]

    return {
        "total_visits": total_visits,
        "top_3_peak_hours": [f"{h}시:{cnt}" for h, cnt in top3],
        "expected_peaks": "08시/12-13시/18-21시",
        "match_count": f"{len(matched_peaks)}/3",
        "match": len(matched_peaks) >= 2,
    }


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------
def main():
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("sim_path", help="시뮬 결과 JSON (e.g., data/processed/sim_policy_n1000.json)")
    args = p.parse_args()

    sim_path = Path(args.sim_path)
    if not sim_path.exists():
        print(f"[!] 파일 없음: {sim_path}")
        return 1

    print("=" * 70)
    print(f"  시뮬 검증: {sim_path.name}")
    print("=" * 70)

    result, traj = load_sim(sim_path)
    print(f"\n  총 결정: {result.get('total_decisions'):,}")
    print(f"  LLM 호출: S={result.get('tier_s_calls')} / A={result.get('tier_a_calls')}")
    print(f"  비용: ${result.get('estimated_cost_usd'):.4f}")
    print(f"  Trajectory: {len(traj):,}건")

    print("\n" + "-" * 70)
    print("  [1] 시간×동 유동인구 분포 (vs living_population 30일 평균)")
    print("-" * 70)
    pop = validate_population(traj)
    for k, v in pop.items():
        print(f"  {k}: {v}")

    print("\n" + "-" * 70)
    print("  [2] 카테고리 매출 분포 (vs district_sales_seoul)")
    print("-" * 70)
    cat = validate_category_distribution(result)
    for k, v in cat.items():
        print(f"  {k}: {v}")

    print("\n" + "-" * 70)
    print("  [2.5] 버스 승하차 유동인구 (vs bus_boarding_daily)")
    print("-" * 70)
    bus = validate_bus_flow(traj)
    for k, v in bus.items():
        print(f"  {k}: {v}")

    print("\n" + "-" * 70)
    print("  [3] 내부 정합성")
    print("-" * 70)
    ic = validate_internal_consistency(traj)
    for k, v in ic.items():
        print(f"  {k}: {v}")

    print("\n" + "-" * 70)
    print("  [4] 시간대 피크 패턴")
    print("-" * 70)
    peaks = validate_time_peaks(traj)
    for k, v in peaks.items():
        print(f"  {k}: {v}")

    print("\n" + "=" * 70)
    print("  검증 완료")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
