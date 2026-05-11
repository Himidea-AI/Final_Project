"""competitor_intel 평가 framework 시범 실행.

목적: evaluator 동작 검증 + 첫 metric 산출.
입력: 합성 fixture 10건 (다양한 cannibal/saturation 조합 + LLM signal).
출력: accuracy + confusion matrix + 케이스별 결과.

⚠️ 합성 fixture 의 LLM signal 은 실제 출력이 아닌 "전형적 LLM 응답 패턴" 모방.
   실제 정확도 측정은 Redis 캐시 dump → fixture 변환 후 별도 실행.

사용:
    cd backend
    python -m scripts.eval.run_competitor_intel_demo
"""

from __future__ import annotations

import asyncio
import io
import sys

# Windows cp949 콘솔 인코딩 → UTF-8 강제 (한글·유니코드 출력 깨짐 방지)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, "C:\\dev\\Final_project\\backend")  # noqa

from src.evaluation.competitor_intel_eval import CompetitorIntelEvaluator


# 합성 fixture — 10 케이스, expected vs LLM 출력 다양성.
# expected (룰엔진 임계값):
#   green : cannibal_pct < 0.05  AND  saturation in {sparse, low}
#   yellow: 0.05 <= cannibal_pct <= 0.15  OR  saturation == medium
#   red   : cannibal_pct > 0.15  OR  saturation in {high, saturated}
FIXTURES = [
    # green 정답 케이스 (LLM 도 green) — 일치
    {
        "case_id": "case01_green_correct",
        "simulated_output": {
            "market_entry_signal": "green",
            "cannibalization": {"estimated_revenue_impact_pct": -0.03},
            "competition_500m": {"saturation_level": "low"},
        },
    },
    # green 정답 케이스 (LLM 은 yellow) — 보수적 LLM 오답
    {
        "case_id": "case02_green_to_yellow",
        "simulated_output": {
            "market_entry_signal": "yellow",
            "cannibalization": {"estimated_revenue_impact_pct": -0.02},
            "competition_500m": {"saturation_level": "sparse"},
        },
    },
    # yellow 정답 (cannibal 7%) — LLM yellow 정답
    {
        "case_id": "case03_yellow_correct_cannibal",
        "simulated_output": {
            "market_entry_signal": "yellow",
            "cannibalization": {"estimated_revenue_impact_pct": -0.07},
            "competition_500m": {"saturation_level": "low"},
        },
    },
    # yellow 정답 (saturation medium) — LLM yellow 정답
    {
        "case_id": "case04_yellow_correct_medium",
        "simulated_output": {
            "market_entry_signal": "yellow",
            "cannibalization": {"estimated_revenue_impact_pct": -0.04},
            "competition_500m": {"saturation_level": "medium"},
        },
    },
    # yellow 정답이지만 LLM 은 green (낙관적 오답)
    {
        "case_id": "case05_yellow_to_green",
        "simulated_output": {
            "market_entry_signal": "green",
            "cannibalization": {"estimated_revenue_impact_pct": -0.10},
            "competition_500m": {"saturation_level": "low"},
        },
    },
    # red 정답 (cannibal 30%) — LLM red 정답
    {
        "case_id": "case06_red_correct_cannibal",
        "simulated_output": {
            "market_entry_signal": "red",
            "cannibalization": {"estimated_revenue_impact_pct": -0.30},
            "competition_500m": {"saturation_level": "medium"},
        },
    },
    # red 정답 (saturation high) — LLM red 정답
    {
        "case_id": "case07_red_correct_high",
        "simulated_output": {
            "market_entry_signal": "red",
            "cannibalization": {"estimated_revenue_impact_pct": -0.04},
            "competition_500m": {"saturation_level": "high"},
        },
    },
    # red 정답 (saturated) — LLM yellow (위험 과소평가)
    {
        "case_id": "case08_red_to_yellow",
        "simulated_output": {
            "market_entry_signal": "yellow",
            "cannibalization": {"estimated_revenue_impact_pct": -0.08},
            "competition_500m": {"saturation_level": "saturated"},
        },
    },
    # 50% 캡 도달 케이스 — red 정답
    {
        "case_id": "case09_red_capped",
        "simulated_output": {
            "market_entry_signal": "red",
            "cannibalization": {"estimated_revenue_impact_pct": -0.50},
            "competition_500m": {"saturation_level": "high"},
        },
    },
    # green 정답 (이상적 케이스) — LLM green
    {
        "case_id": "case10_green_ideal",
        "simulated_output": {
            "market_entry_signal": "green",
            "cannibalization": {"estimated_revenue_impact_pct": -0.01},
            "competition_500m": {"saturation_level": "sparse"},
        },
    },
]


async def main() -> None:
    evaluator = CompetitorIntelEvaluator(fixtures=FIXTURES)
    summary = await evaluator.run()

    print("=" * 60)
    print("competitor_intel 평가 결과 (합성 fixture 10건)")
    print("=" * 60)
    for line in summary.report_lines():
        print(line)
    print()
    print("케이스별 결과:")
    for r in summary.raw_results:
        mark = "✓" if r.passed else "✗"
        print(f"  {mark} {r.case_id}: expected={r.expected:6} actual={r.actual:6}")
    print()
    print("=" * 60)
    print(f"📊 정확도: {summary.metric_mean:.1%} ({summary.n_passed}/{summary.n_cases})")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
