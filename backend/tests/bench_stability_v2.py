"""
메트릭 안정성 검증 — bench_rag_accuracy.py의 run_benchmark()를 5회 반복

기존 81.1%를 산출한 동일 스크립트로 측정하여 스크립트 차이가 아닌 메트릭 안정성만 측정.
실행: cd backend && python -m tests.bench_stability_v2
"""

import asyncio
import json
import selectors
import sys
from pathlib import Path

# bench_rag_accuracy의 run_benchmark를 그대로 import
from tests.bench_rag_accuracy import run_benchmark, BENCHMARK_CASES

NUM_RUNS = 5


async def run_stability():
    """run_benchmark()를 5회 반복하고 분산 측정."""
    all_results = []

    for i in range(NUM_RUNS):
        print(f"\n{'='*50}")
        print(f"RUN {i+1}/{NUM_RUNS}")
        print(f"{'='*50}")

        # run_benchmark()가 bench_result.json에 결과 저장
        await run_benchmark()

        # 결과 읽기
        result_path = Path(__file__).resolve().parent.parent.parent / "bench_result.json"
        with open(result_path, encoding="utf-8") as f:
            result = json.load(f)
        all_results.append(result)

        exact_pct = result["exact_match"]["accuracy_pct"]
        llm_pct = result["llm_judge"]["relevance_pct"]
        print(f"\n>>> Run {i+1}: Exact={exact_pct}%, LLM-judge={llm_pct}%")

    # 통계 계산
    exact_pcts = [r["exact_match"]["accuracy_pct"] for r in all_results]
    llm_pcts = [r["llm_judge"]["relevance_pct"] for r in all_results]

    def stats(values):
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / len(values)
        return {"values": values, "mean": round(mean, 2), "std_dev": round(var ** 0.5, 2), "min": min(values), "max": max(values)}

    summary = {
        "num_runs": NUM_RUNS,
        "exact_match": stats(exact_pcts),
        "llm_judge": stats(llm_pcts),
    }

    output_path = Path(__file__).resolve().parent.parent.parent / "bench_stability_v2.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"STABILITY REPORT ({NUM_RUNS} runs)")
    print(f"{'='*60}")
    print(f"Exact-match: {exact_pcts}")
    print(f"  Mean={summary['exact_match']['mean']}%, StdDev={summary['exact_match']['std_dev']}%")
    print(f"LLM-judge:   {llm_pcts}")
    print(f"  Mean={summary['llm_judge']['mean']}%, StdDev={summary['llm_judge']['std_dev']}%")
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(run_stability(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(run_stability())
