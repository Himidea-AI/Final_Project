"""ABM 시뮬 성능 프로파일러 — 1회성 진단 스크립트.

목적:
    /simulate-abm 호출이 5~7분 걸리는 진짜 hot line 식별.
    cProfile 로 cumulative + tottime 상위 30 line 출력.

실행:
    cd backend
    PYTHONUTF8=1 PYTHONIOENCODING=utf-8 python -u scripts/profile_abm.py

출력:
    profile_abm.prof (raw stats, snakeviz 가능)
    stdout — 상위 30 hot line (cumulative + tottime 정렬 2회)

설계:
    - LLM 비활성 (use_llm_decisions=False, enable_llm_thought=False) — Python hot loop 만 측정
    - n_agents=5000, days=1, hours=20 (실제 운영 케이스 동일)
    - verbose=False (print 노이즈 제거)
"""

from __future__ import annotations

import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
# backend/ 를 PYTHONPATH 에 추가 — `src.simulation.*` import
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.simulation.config import (  # noqa: E402
    ModelConfig,
    PopulationMix,
    Scenario,
    TierDistribution,
)
from src.simulation.runner import run_simulation  # noqa: E402


def main() -> None:
    print("[profile] ABM 시뮬 cProfile 시작...", flush=True)

    pop = PopulationMix(
        residents=300, commuters=50, visitors=20, owners=5,
        ext_commuters=100, ext_visitors=25,
    )
    # Tier S/A 도 LLM 끄고 policy_decide 만 측정 (Python hot loop 격리)
    tier = TierDistribution(tier_s=50, tier_a=200, tier_b=4750)
    cfg = ModelConfig(
        n_personas=5000,
        tier_s_provider="openai",
        tier_s_model="gpt-4.1-mini",
        tier_a_provider="openai",
        tier_a_model="gpt-4.1-mini",
        mock_mode=True,  # LLM 호출 mock → Python loop 만 측정
    )
    scenario = Scenario(new_store=None)

    pr = cProfile.Profile()
    t0 = time.time()
    pr.enable()
    try:
        run_simulation(
            days=1,
            pop=pop,
            tier=tier,
            cfg=cfg,
            scenario=scenario,
            seed=42,
            verbose=False,
            use_rds=True,
            use_profiles=True,
            collect_trajectory=True,
            seed_memory=False,
            use_llm_decisions=False,
            enable_llm_thought=False,
            llm_concurrency=8,
        )
    finally:
        pr.disable()

    elapsed = time.time() - t0
    print(f"[profile] 시뮬 완료 — 총 {elapsed:.1f}s", flush=True)

    out_path = Path(__file__).parent / "profile_abm.prof"
    pr.dump_stats(out_path)
    print(f"[profile] raw stats 저장: {out_path}", flush=True)

    print("\n" + "=" * 80)
    print("[Top 30 by CUMULATIVE TIME — 호출 트리 누적]")
    print("=" * 80)
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(30)
    print(s.getvalue())

    print("\n" + "=" * 80)
    print("[Top 30 by TOTTIME — 함수 자체 실행 시간 (자식 제외)]")
    print("=" * 80)
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("tottime").print_stats(30)
    print(s.getvalue())

    print("\n[profile] 분석:")
    print("  - cumulative 1~3 위가 진짜 bottleneck (top-down)")
    print("  - tottime 1~3 위가 hot leaf 함수 (실제 CPU 소비)")
    print("  - snakeviz 시각화: snakeviz scripts/profile_abm.prof")


if __name__ == "__main__":
    main()
