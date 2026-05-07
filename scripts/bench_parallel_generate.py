"""ModelOutput.generate() 병렬화 전/후 실측 벤치마크.

사용:
    python scripts/bench_parallel_generate.py

병렬 버전 측정 → git stash → 베이스라인 측정 → git stash pop은
이 스크립트 외부에서 수행한다. 이 스크립트는 단순히 N회 generate를 돌려 평균/표준편차를 출력한다.
"""

from __future__ import annotations

import statistics
import time

from models.interface import ModelOutput
from models.revenue_predictor.bep import BEPCalculator

# 측정 대상 — 4개 동 × 1개 업종 (마포구 4개 동, 한식음식점)
TARGETS = [
    ("11440530", "CS100001", "서교동", "한식음식점"),
    ("11440550", "CS100001", "합정동", "한식음식점"),
    ("11440545", "CS100001", "망원동", "한식음식점"),
    ("11440505", "CS100001", "연남동", "한식음식점"),
]

WARMUP = 1
N_RUNS = 3


def _bench_one(dong_code: str, industry_code: str, industry_name: str) -> float:
    cost_cfg = BEPCalculator.get_default_costs(
        industry_name, initial_capital=130_000_000, monthly_rent=2_000_000
    )
    t = time.perf_counter()
    ModelOutput.generate(dong_code, industry_code, industry_name, cost_cfg, "tcn")
    return time.perf_counter() - t


def main() -> None:
    print(f"=== Bench: WARMUP={WARMUP}, N_RUNS={N_RUNS} per target ===")
    all_runs: list[float] = []
    for dong_code, industry_code, dong_name, industry_name in TARGETS:
        print(f"\n[{dong_name} / {industry_name}] dong={dong_code} industry={industry_code}")
        # warm-up (모델 캐시 로드)
        for _ in range(WARMUP):
            try:
                _bench_one(dong_code, industry_code, industry_name)
            except Exception as exc:
                print(f"  warmup 실패: {exc}")
                break
        # 측정
        runs: list[float] = []
        for i in range(N_RUNS):
            try:
                t = _bench_one(dong_code, industry_code, industry_name)
                runs.append(t)
                print(f"  run {i + 1}: {t:.2f}s")
            except Exception as exc:
                print(f"  run {i + 1} 실패: {exc}")
        if runs:
            avg = statistics.mean(runs)
            std = statistics.stdev(runs) if len(runs) > 1 else 0.0
            print(f"  평균={avg:.2f}s ± {std:.2f}s")
            all_runs.extend(runs)

    if all_runs:
        print("\n=== 전체 통합 ===")
        print(f"  총 {len(all_runs)}회, 평균={statistics.mean(all_runs):.2f}s, "
              f"std={statistics.stdev(all_runs) if len(all_runs) > 1 else 0:.2f}s, "
              f"min={min(all_runs):.2f}s, max={max(all_runs):.2f}s")


if __name__ == "__main__":
    main()
