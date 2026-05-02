"""시뮬 시나리오 종합 평가 — Layer 3/4 (룰엔진 + specialist 출력 정확도).

흐름:
1. scenario_golden_set.csv 읽기
2. 각 시나리오로 orchestrator.run_legal_evaluation 호출
3. expected_levels (카테고리별 기대값) + expected_keywords (특정 카테고리 summary 포함어) 비교
4. 카테고리별 일치율 + overall 일치율 산출

expected_levels 형식:
- "food_hygiene=danger" — 정확 일치
- "franchise_law>=caution" — caution 이상 (caution 또는 danger OK)

실행:
    cd backend && python -m tests.bench_scenario
    cd backend && python -m tests.bench_scenario --csv path/to/scenarios.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.legal.orchestrator import run_legal_evaluation  # noqa: E402

_LEVEL_ORDER = {"safe": 0, "caution": 1, "danger": 2}
_OVERALL_ORDER = {"safe": 0, "caution": 1, "danger": 2}

DEFAULT_CSV = Path(__file__).resolve().parent / "scenario_golden_set.csv"


def parse_expected_levels(raw: str) -> dict[str, tuple[str, str]]:
    """'food_hygiene=danger;franchise_law>=caution' → {category: (op, level)}."""
    result: dict[str, tuple[str, str]] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        if ">=" in part:
            cat, level = part.split(">=", 1)
            result[cat.strip()] = (">=", level.strip())
        elif "=" in part:
            cat, level = part.split("=", 1)
            result[cat.strip()] = ("=", level.strip())
    return result


def parse_keywords(raw: str) -> dict[str, list[str]]:
    """'fair_trade_law=마포구|상생협력;food_hygiene=즉석조리' → {category: [keywords]}."""
    result: dict[str, list[str]] = {}
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        cat, kws = part.split("=", 1)
        result[cat.strip()] = [k.strip() for k in kws.split("|") if k.strip()]
    return result


def check_level(actual: str, op: str, expected: str) -> bool:
    a = _LEVEL_ORDER.get(actual, -1)
    e = _LEVEL_ORDER.get(expected, -1)
    if op == "=":
        return a == e
    if op == ">=":
        return a >= e
    return False


def compute_overall(risks: list[dict]) -> str:
    """legal.py _CRITICAL_TYPES 와 동일 로직."""
    _CRITICAL = {"food_hygiene", "fire_safety_law", "building_law"}
    danger_types = [r["type"] for r in risks if r.get("level") == "danger"]
    has_critical = any(t in _CRITICAL for t in danger_types)
    has_caution = any(r.get("level") == "caution" for r in risks)
    if has_critical or len(danger_types) >= 2:
        return "danger"
    if danger_types or has_caution:
        return "caution"
    return "safe"


async def evaluate_scenario(case: dict) -> dict:
    expected_levels = parse_expected_levels(case["expected_levels"])
    expected_keywords = parse_keywords(case.get("expected_keywords", ""))
    expected_overall = case["expected_overall"]

    risks = await run_legal_evaluation(
        brand=case["brand_name"],
        business_type=case["business_type"],
        district=case["district"],
        store_area_pyeong=float(case["store_area"]),
        ftc_data=None,
    )
    by_type = {r["type"]: r for r in risks}

    # 카테고리 level 검증
    level_results: list[dict] = []
    for cat, (op, expected) in expected_levels.items():
        r = by_type.get(cat)
        actual = r.get("level", "?") if r else "MISSING"
        ok = check_level(actual, op, expected) if r else False
        level_results.append(
            {"cat": cat, "op": op, "expected": expected, "actual": actual, "ok": ok}
        )

    # 키워드 검증
    keyword_results: list[dict] = []
    for cat, keywords in expected_keywords.items():
        r = by_type.get(cat)
        text = ""
        if r:
            text = (r.get("summary", "") or "") + " " + (r.get("recommendation", "") or "")
        for kw in keywords:
            ok = kw in text
            keyword_results.append(
                {"cat": cat, "keyword": kw, "ok": ok, "text_snippet": text[:80]}
            )

    actual_overall = compute_overall(risks)

    return {
        "scenario_id": case["scenario_id"],
        "brand": case["brand_name"],
        "biz": case["business_type"],
        "district": case["district"],
        "area": case["store_area"],
        "level_results": level_results,
        "keyword_results": keyword_results,
        "expected_overall": expected_overall,
        "actual_overall": actual_overall,
        "overall_ok": actual_overall == expected_overall,
        "note": case.get("note", ""),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    args = ap.parse_args()

    with open(args.csv, encoding="utf-8-sig") as f:
        cases = list(csv.DictReader(f))

    print(f"\n시나리오 {len(cases)}개 평가 시작\n")
    results: list[dict] = []
    for c in cases:
        print(f"[{c['scenario_id']}] {c['brand_name']} / {c['business_type']} / {c['district']} / {c['store_area']}평")
        r = await evaluate_scenario(c)
        results.append(r)
        # 카테고리 fail
        fails = [lr for lr in r["level_results"] if not lr["ok"]]
        if fails:
            for f in fails:
                print(f"  ✗ {f['cat']}: expected {f['op']}{f['expected']}, actual={f['actual']}")
        kw_fails = [kw for kw in r["keyword_results"] if not kw["ok"]]
        if kw_fails:
            for kw in kw_fails:
                print(f"  ✗ {kw['cat']} keyword '{kw['keyword']}' 누락 (snippet: {kw['text_snippet']})")
        if r["overall_ok"]:
            print(f"  ✓ overall {r['actual_overall']}")
        else:
            print(f"  ✗ overall expected={r['expected_overall']}, actual={r['actual_overall']}")
        print(f"    note: {r['note']}")
        print()

    # ─────────────────────────────────────────────
    # 요약
    # ─────────────────────────────────────────────
    print("=" * 70)
    print("종합 정확도")
    print("=" * 70)
    total_levels = sum(len(r["level_results"]) for r in results)
    correct_levels = sum(sum(1 for lr in r["level_results"] if lr["ok"]) for r in results)
    total_keywords = sum(len(r["keyword_results"]) for r in results)
    correct_keywords = sum(sum(1 for kw in r["keyword_results"] if kw["ok"]) for r in results)
    correct_overall = sum(1 for r in results if r["overall_ok"])
    print(f"  Level 정확도   : {correct_levels}/{total_levels} ({correct_levels/total_levels*100:.1f}%)")
    if total_keywords > 0:
        print(f"  Keyword 일치   : {correct_keywords}/{total_keywords} ({correct_keywords/total_keywords*100:.1f}%)")
    print(f"  Overall 정확도 : {correct_overall}/{len(results)} ({correct_overall/len(results)*100:.1f}%)")

    # 카테고리별
    print("\n  카테고리별 정확도:")
    cat_stats: dict[str, list[bool]] = {}
    for r in results:
        for lr in r["level_results"]:
            cat_stats.setdefault(lr["cat"], []).append(lr["ok"])
    for cat in sorted(cat_stats.keys()):
        oks = cat_stats[cat]
        acc = sum(oks) / len(oks) * 100
        print(f"    {cat:20s} {sum(oks)}/{len(oks)} ({acc:.0f}%)")


if __name__ == "__main__":
    asyncio.run(main())
