"""SP3 — RRF 가중치 grid search.

bench_rag_accuracy.py와 같은 BENCHMARK_CASES 사용.
LLM-judge skip (RAG metrics만 측정 — 빠르고 deterministic).

실행:
    cd backend && python -m tests.bench_rrf_grid

env:
    GRID_WEIGHTS  : "0.3,0.4,0.5,0.6,0.7" (default)
    GRID_K        : top-K (default 10)
"""

from __future__ import annotations

import asyncio
import os
import re
import selectors
import sys
import time
from pathlib import Path

# 부모 모듈 import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.chains.retriever import LegalDocumentRetriever  # noqa: E402

from .bench_rag_accuracy import BENCHMARK_CASES, compute_rag_metrics  # noqa: E402


async def _run_one(retriever: LegalDocumentRetriever, k: int) -> dict:
    """현재 RRF 가중치로 BENCHMARK_CASES 전체 실행."""
    metrics_per_case = []
    for _law, query, filter_attr, expected in BENCHMARK_CASES:
        sf = getattr(retriever, filter_attr, None)
        docs = await retriever.search(query, top_k=k, source_filter=sf)
        ranked = []
        for d in docs:
            art = d.get("metadata", {}).get("article", "")
            if art and art not in ("전문", "미분류", "N/A"):
                normalized = re.sub(r"_\d+$", "", art)
                if normalized not in ranked:
                    ranked.append(normalized)
        m = compute_rag_metrics(expected, ranked, k=k)
        metrics_per_case.append(m)

    n = len(metrics_per_case)
    return {
        "recall@k": sum(m["recall@k"] for m in metrics_per_case) / n,
        "precision@k": sum(m["precision@k"] for m in metrics_per_case) / n,
        "mrr": sum(m["mrr"] for m in metrics_per_case) / n,
        "ndcg@k": sum(m["ndcg@k"] for m in metrics_per_case) / n,
        "hit@k_rate": sum(m["hit@k"] for m in metrics_per_case) / n,
        "n_cases": n,
    }


async def main() -> None:
    weights_str = os.getenv("GRID_WEIGHTS", "0.3,0.4,0.5,0.6,0.7")
    weights = [float(w.strip()) for w in weights_str.split(",")]
    k = int(os.getenv("GRID_K", "10"))

    print(f"=== RRF grid search (vector_w ∈ {weights}, k={k}) ===")
    print(f"{'vec_w':>5} {'bm25_w':>6} {'R@10':>6} {'MRR':>6} {'NDCG':>6} {'Hit@10':>7} {'time_s':>7}")
    print("-" * 60)

    rows = []
    for vw in weights:
        bw = round(1.0 - vw, 3)
        # env override (settings.rrf_vector_weight 이 외부 env 인스턴스 참조)
        os.environ["RRF_VECTOR_WEIGHT"] = str(vw)
        os.environ["RRF_BM25_WEIGHT"] = str(bw)
        # settings 모듈 reload — singleton settings 인스턴스 재생성
        import importlib

        import src.config.settings as _settings_mod

        importlib.reload(_settings_mod)

        # retriever 인스턴스도 새로 — 이전 BM25 인덱스는 재사용 OK
        retriever = LegalDocumentRetriever()

        t0 = time.perf_counter()
        m = await _run_one(retriever, k)
        elapsed = time.perf_counter() - t0
        rows.append((vw, bw, m, elapsed))

        print(
            f"{vw:>5.2f} {bw:>6.2f} "
            f"{m['recall@k']:>6.3f} {m['mrr']:>6.3f} {m['ndcg@k']:>6.3f} "
            f"{m['hit@k_rate'] * 100:>6.1f}% {elapsed:>7.1f}"
        )

    # 최적 가중치 (NDCG@K 기준)
    best = max(rows, key=lambda r: r[2]["ndcg@k"])
    print()
    print(
        f"최적 (NDCG@K): vec_w={best[0]:.2f} bm25_w={best[1]:.2f} "
        f"NDCG@10={best[2]['ndcg@k']:.3f} Recall={best[2]['recall@k']:.3f} "
        f"MRR={best[2]['mrr']:.3f} Hit@10={best[2]['hit@k_rate'] * 100:.1f}%"
    )

    # JSON 저장
    import json as _json

    out = Path(__file__).resolve().parent.parent.parent / "bench_rrf_grid.json"
    with open(out, "w", encoding="utf-8") as f:
        _json.dump(
            {
                "k": k,
                "weights_tested": weights,
                "rows": [{"vector_w": vw, "bm25_w": bw, **m, "elapsed_s": round(t, 1)} for vw, bw, m, t in rows],
                "best_by_ndcg": {
                    "vector_w": best[0],
                    "bm25_w": best[1],
                    **best[2],
                },
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"saved → {out}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(main())
