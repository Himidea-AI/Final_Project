"""마포구 1000 에이전트 LLM ABM 시뮬레이션 PoC.

실행:
    cd backend && python -m src.simulation.runner   # X (라이브러리)
    python scripts/sim_mapo_poc.py                  # O

옵션:
    --days N        : 시뮬레이션 일수 (default: 1)
    --tier-s N      : Tier S 에이전트 수 (default: 50)
    --mock          : 강제 mock 모드 (API 키 무시)
    --small         : 100 에이전트로 빠른 테스트
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

# Windows 콘솔 한글 출력
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# backend/src 를 import path에 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.simulation.config import (  # noqa: E402
    ModelConfig,
    PopulationMix,
    Scenario,
    TierDistribution,
    TimeConfig,
    estimate_cost,
)
from src.simulation.runner import run_simulation  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=1)
    p.add_argument("--tier-s", type=int, default=50)
    p.add_argument("--tier-a", type=int, default=200)
    p.add_argument("--mock", action="store_true")
    p.add_argument("--small", action="store_true", help="100 agents 빠른 테스트 (LLM 25%)")
    p.add_argument("--n100", action="store_true", help="100 agents 풀 테스트 (LLM 40%, External calibrated)")
    p.add_argument("--tiny", action="store_true", help="20 agents 초소형 (Qwen용)")
    p.add_argument("--rds", action="store_true", help="RDS 실제 마포 점포 사용")
    p.add_argument("--pgvector", action="store_true", help="pgvector 메모리 검색 활성화")
    p.add_argument("--clear-memory", action="store_true", help="시작 전 sim_agent_memory 비우기")
    p.add_argument("--qwen", action="store_true", help="Ollama Qwen2.5:3b 강제 사용 (로컬, 무료)")
    p.add_argument("--gemini", action="store_true", help="Tier S/A 모두 Gemini flash-lite 강제 사용 (클라우드 API)")
    p.add_argument("--openai", action="store_true", help="Tier S/A 모두 OpenAI (gpt-4o-mini / gpt-4.1-nano) 강제")
    p.add_argument("--weekend", action="store_true", help="모든 날을 주말로 강제")
    p.add_argument("--rent-shock", type=float, default=0.0, help="임대료/가격 충격률 (예: 0.30=+30%)")
    p.add_argument("--concurrency", type=int, default=4, help="LLM 에이전트 동시 호출 수 (Ollama NUM_PARALLEL과 일치)")
    p.add_argument("--profiles", action="store_true", help="RDS 기반 개인화된 AgentProfile 사용")
    p.add_argument("--chat", action="store_true", help="에이전트 간 원시어 DSL 대화 활성화")
    p.add_argument("--chat-per-step", type=int, default=2, help="시간당 최대 대화 쌍")
    p.add_argument("--trajectory", action="store_true", help="에이전트 위치 궤적 저장 (지도 시각화용)")
    p.add_argument("--all-llm", action="store_true", help="tiny/small에서도 Tier B=0 → 전원 LLM 호출")
    p.add_argument("--dsl", action="store_true", help="DSL 의사결정 모드 (Tier S/A/B 모두 brain.dsl_decide)")
    p.add_argument(
        "--policy",
        action="store_true",
        help="Policy Generator 모드 (LLM 11회만 + Python 점수함수, 9h→2min)",
    )
    p.add_argument("--out", default="data/processed/sim_result.json")
    args = p.parse_args()

    if args.tiny:
        pop = PopulationMix(residents=8, commuters=2, visitors=1, owners=1, ext_commuters=6, ext_visitors=2)
        # all-llm: 20명 전원 LLM (Tier B=0)
        if getattr(args, "all_llm", False):
            tier = TierDistribution(tier_s=2, tier_a=18, tier_b=0)
        else:
            tier = TierDistribution(tier_s=2, tier_a=5, tier_b=13)
    elif args.n100:
        # 1000명 기본 비율을 1/10로 축소 + LLM 비중 약간 상향
        # residents 40 / commuters 10 / visitors 5 / owners 5 / ext_commuters 30 / ext_visitors 10 = 100
        pop = PopulationMix(residents=40, commuters=10, visitors=5, owners=5, ext_commuters=30, ext_visitors=10)
        if getattr(args, "all_llm", False):
            tier = TierDistribution(tier_s=10, tier_a=90, tier_b=0)
        else:
            tier = TierDistribution(tier_s=10, tier_a=30, tier_b=60)
    elif args.small:
        pop = PopulationMix(residents=40, commuters=10, visitors=5, owners=5, ext_commuters=30, ext_visitors=10)
        if getattr(args, "all_llm", False):
            tier = TierDistribution(tier_s=5, tier_a=95, tier_b=0)
        else:
            tier = TierDistribution(tier_s=5, tier_a=20, tier_b=75)
    else:
        pop = PopulationMix()  # 420/120/80/60/220/100 = 1000 (통계청 기반)
        tier = TierDistribution(tier_s=args.tier_s, tier_a=args.tier_a, tier_b=1000 - args.tier_s - args.tier_a)

    if args.qwen:
        cfg = ModelConfig(
            mock_mode=args.mock,
            tier_s_provider="ollama",
            tier_s_model="qwen2.5:3b",
            tier_a_provider="ollama",
            tier_a_model="qwen2.5:3b",
        )
    elif args.gemini:
        cfg = ModelConfig(
            mock_mode=args.mock,
            tier_s_provider="gemini",
            tier_s_model="gemini-2.5-flash-lite",
            tier_a_provider="gemini",
            tier_a_model="gemini-2.5-flash-lite",
        )
    elif args.openai:
        cfg = ModelConfig(
            mock_mode=args.mock,
            tier_s_provider="openai",
            tier_s_model="gpt-4o-mini",
            tier_a_provider="openai",
            tier_a_model="gpt-4.1-nano",
        )
    else:
        cfg = ModelConfig(mock_mode=args.mock)
    time_cfg = TimeConfig()

    # 사전 비용 추정 (이벤트 기반 활성화율 가정 ~50%)
    pre = estimate_cost(
        tier_s_calls=int(tier.tier_s * time_cfg.total_steps * 0.5 * args.days),
        tier_a_calls=int(tier.tier_a * time_cfg.total_steps * 0.5 * args.days),
        cfg=cfg,
    )
    print("\n사전 비용 추정 (활성화율 50% 가정):")
    print(f"  Tier S: ${pre['tier_s_usd']:.4f}")
    print(f"  Tier A: ${pre['tier_a_usd']:.4f}")
    print(f"  TOTAL : ${pre['total_usd']:.4f}\n")

    scenario = Scenario(weekend_force=args.weekend, rent_shock_pct=args.rent_shock)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    traj_path = out.with_name(out.stem + "_trajectory.json") if args.trajectory else None

    result = run_simulation(
        days=args.days,
        pop=pop,
        tier=tier,
        cfg=cfg,
        time_cfg=time_cfg,
        verbose=True,
        use_rds=args.rds,
        use_pgvector=args.pgvector,
        pgvector_clear=args.clear_memory,
        scenario=scenario,
        save_path=out,
        llm_concurrency=args.concurrency,
        use_profiles=args.profiles,
        enable_chat=args.chat,
        chat_per_step=args.chat_per_step,
        trajectory_path=traj_path,
        use_dsl=args.dsl,
        use_policy=args.policy,
    )

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "days": result.days,
                "total_decisions": result.total_decisions,
                "tier_s_calls": result.tier_s_calls,
                "tier_a_calls": result.tier_a_calls,
                "estimated_cost_usd": result.estimated_cost_usd,
                "top_stores": result.top_stores,
                "sample_stories": result.sample_stories,
                "category_totals": result.category_totals,
                "dong_totals": result.dong_totals,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\n[저장] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
