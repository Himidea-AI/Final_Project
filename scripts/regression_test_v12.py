"""v12 baseline 지표 회귀 테스트 — score_store/policy 변경 후 필수 실행.

리뷰어 권고 (2026-04-21 code-reviewer subagent):
  "score_store는 10+ 곱항, 계수 한 개만 건드려도 RMSE/KL/Pearson 셋 중 하나는
  반드시 흔들림. regression test 없이 변경하면 v12 지표 회귀 위험."

v12 선택 이유: 14개 버전 중 Pareto frontier 최적 (realism 10종 완비 +
RMSE 4.7% + KL 0.079 + External 90% 균형).

사용:
  python scripts/regression_test_v14.py
    → data/processed/sim_policy_v12_final_n1000.json 기준으로
       현재 시뮬 결과 (방금 돌린 최신 sim_policy_*_n1000.json) 비교

결과:
  ✅ PASS — v12 대비 허용 범위
  ⚠️ WARN — 허용 범위 벗어남
  ❌ FAIL — 크게 회귀 (0.5σ 이상)
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]

# v12 baseline (2026-04-21 재현 측정값 — sim_policy_v12_final_n1000.json)
V14_BASELINE = {
    "rmse_pct": 4.7,  # %
    "correlation": 0.677,
    "bus_correlation": 0.662,
    "kl_divergence": 0.079,
    "external_return_rate": 90.8,  # %
    "total_visits": 4184,
    "category_food_pct": 67.0,  # 음식점 % (편의점 제외 후)
}

# 허용 범위 (WARN / FAIL 기준)
TOLERANCE = {
    "rmse_pct": {"warn": 0.5, "fail": 1.0},
    "correlation": {"warn": 0.05, "fail": 0.10},
    "bus_correlation": {"warn": 0.05, "fail": 0.10},
    "kl_divergence": {"warn": 0.03, "fail": 0.08},
    "external_return_rate": {"warn": 3.0, "fail": 6.0},
    "total_visits": {"warn": 500, "fail": 1000},
    "category_food_pct": {"warn": 3.0, "fail": 7.0},
}


def _load_validate_result(sim_path: Path) -> dict:
    """validate_simulation.py를 내부 호출해서 지표 추출."""
    import subprocess

    result = subprocess.run(
        [sys.executable, "-X", "utf8", "scripts/validate_simulation.py", str(sim_path)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    out = result.stdout

    def _extract(keyword: str, line_prefix: str) -> float | None:
        for line in out.splitlines():
            if keyword in line and line_prefix in line:
                try:
                    return float(line.split(":")[-1].strip().rstrip("%"))
                except (ValueError, IndexError):
                    continue
        return None

    rmse = _extract("rmse_pct", "rmse_pct")
    corr = _extract("correlation", "correlation") if "correlation" in out else None

    return {"raw_stdout": out, "rmse_pct": rmse, "correlation": corr}


def evaluate(current: dict, baseline: dict = V14_BASELINE) -> tuple[str, list[str]]:
    """현재 지표 vs baseline 비교. (status, messages)."""
    msgs: list[str] = []
    worst = "PASS"
    for key, base_val in baseline.items():
        cur_val = current.get(key)
        if cur_val is None:
            msgs.append(f"  [?] {key}: 측정 실패 (skip)")
            continue
        diff = abs(cur_val - base_val)
        tol = TOLERANCE.get(key, {"warn": 0.1 * base_val, "fail": 0.2 * base_val})
        if diff > tol["fail"]:
            msgs.append(f"  ❌ {key}: {cur_val} (baseline {base_val}, Δ{diff:+.3f}) — FAIL")
            worst = "FAIL"
        elif diff > tol["warn"]:
            msgs.append(f"  ⚠️ {key}: {cur_val} (baseline {base_val}, Δ{diff:+.3f}) — WARN")
            if worst == "PASS":
                worst = "WARN"
        else:
            msgs.append(f"  ✅ {key}: {cur_val} (baseline {base_val}, Δ{diff:+.3f})")

    return worst, msgs


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sim",
        default="data/processed/sim_policy_n1000.json",
        help="비교 대상 시뮬 결과 JSON (기본: 방금 돌린 latest)",
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="현재 지표를 새 baseline으로 저장 (신중히 사용)",
    )
    args = parser.parse_args()

    sim_path = ROOT / args.sim
    if not sim_path.exists():
        print(f"❌ 비교 대상 시뮬 없음: {sim_path}")
        return 1

    # 시뮬 결과에서 직접 지표 추출 (JSON)
    with open(sim_path, encoding="utf-8") as f:
        result = json.load(f)
    cat_totals = result.get("category_totals", {})
    food_rev = cat_totals.get("음식점", {}).get("revenue", 0)
    cafe_rev = cat_totals.get("카페", {}).get("revenue", 0)
    pub_rev = cat_totals.get("주점", {}).get("revenue", 0)
    total_no_cvs = food_rev + cafe_rev + pub_rev
    food_pct = round(food_rev / total_no_cvs * 100, 1) if total_no_cvs else 0

    # validate_simulation.py 호출해서 RMSE/corr 등 추출
    vres = _load_validate_result(sim_path)
    out = vres.get("raw_stdout", "")

    # 정규표현식으로 핵심 지표 파싱
    import re

    def _grep_num(pattern: str) -> float | None:
        m = re.search(pattern, out)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
        return None

    # External 귀환율 파싱 — "external_return_rate: X/N" 형태 (N은 전체 ext 수)
    ext_match = re.search(r"external_return_rate:\s*(\d+)/(\d+)", out)
    ext_pct = 0.0
    if ext_match:
        num, denom = int(ext_match.group(1)), int(ext_match.group(2))
        if denom > 0:
            ext_pct = round(num / denom * 100, 1)

    current = {
        "rmse_pct": _grep_num(r"rmse_pct:\s*([\d.]+)%"),
        "correlation": _grep_num(r"correlation:\s*([-\d.]+)") or 0,
        "bus_correlation": 0.0,  # 아래에서 별도 파싱
        "kl_divergence": _grep_num(r"kl_divergence:\s*([\d.]+)"),
        "external_return_rate": ext_pct,
        "total_visits": _grep_num(r"total_visits:\s*(\d+)"),
        "category_food_pct": food_pct,
    }

    # bus_correlation은 두 번째 correlation — 별도 파싱
    corr_matches = re.findall(r"correlation:\s*([-\d.]+)", out)
    if len(corr_matches) >= 2:
        current["correlation"] = float(corr_matches[0])
        current["bus_correlation"] = float(corr_matches[1])

    print("=" * 70)
    print("  v12 Regression Test (Baseline)")
    print(f"  대상: {sim_path.name}")
    print("=" * 70)
    print()

    status, msgs = evaluate(current)
    for m in msgs:
        print(m)

    print()
    print("=" * 70)
    if status == "PASS":
        print("  ✅ 전체 PASS — v12 baseline 유지")
    elif status == "WARN":
        print("  ⚠️ WARN — 일부 지표 흔들림, 원인 점검 필요")
    else:
        print("  ❌ FAIL — v12 회귀! 최근 변경 롤백 검토 필수")
    print("=" * 70)

    if args.save_baseline:
        baseline_path = ROOT / "data" / "processed" / "regression_baseline.json"
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        print(f"\n[저장] {baseline_path.name}")

    return 0 if status != "FAIL" else 2


if __name__ == "__main__":
    sys.exit(main())
