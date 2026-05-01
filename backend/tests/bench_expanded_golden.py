"""SP3 — LLM-judge로 골든셋 expected articles 확장 후 재측정.

기존 bench_result.json의 LLM-judge details를 활용해 의미상 관련(YES) article을
원래 expected에 추가하여 expanded golden set을 만든다. 이 expanded set으로 다시
측정하면 검색 시스템의 진짜 의미 정확도(false negative 보정)를 볼 수 있다.

실행:
    cd backend && python -m tests.bench_expanded_golden

전제:
    이전 bench_rag_accuracy 실행 → bench_result.json 존재 (llm_judge.details 포함)
"""

from __future__ import annotations

import asyncio
import json
import re
import selectors
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.chains.retriever import LegalDocumentRetriever  # noqa: E402

from .bench_rag_accuracy import BENCHMARK_CASES, compute_rag_metrics  # noqa: E402


def _build_expanded_cases() -> tuple[list[tuple], dict]:
    """기존 bench_result.json의 LLM-judge YES를 expected에 추가.

    반환:
        expanded_cases: [(law, query, filter_attr, expanded_expected), ...]
        stats: {original_total, expanded_total, added}
    """
    bench_path = Path(__file__).resolve().parent.parent.parent / "bench_result.json"
    if not bench_path.exists():
        raise FileNotFoundError(f"{bench_path} 없음. 먼저 bench_rag_accuracy 실행.")
    with open(bench_path, encoding="utf-8") as f:
        bench = json.load(f)

    # (law, query) → LLM-YES article 집합
    yes_by_case: dict[tuple, set[str]] = defaultdict(set)
    for d in bench.get("llm_judge", {}).get("details", []):
        if d.get("relevant") is True:
            key = (d["law"], d["query"])
            yes_by_case[key].add(d["article"])

    expanded = []
    orig_total = 0
    exp_total = 0
    added_total = 0
    for law, query, filter_attr, expected in BENCHMARK_CASES:
        original_set = set(expected)
        yes_set = yes_by_case.get((law, query), set())
        merged = list(original_set | yes_set)
        # 안정 정렬
        merged.sort()
        expanded.append((law, query, filter_attr, merged))
        orig_total += len(original_set)
        exp_total += len(merged)
        added_total += len(yes_set - original_set)

    return expanded, {
        "original_total": orig_total,
        "expanded_total": exp_total,
        "added": added_total,
    }


async def _run_with_cases(retriever: LegalDocumentRetriever, cases: list[tuple], k: int = 10) -> dict:
    metrics_per_case = []
    for _law, query, filter_attr, expected in cases:
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
    K = 10
    expanded_cases, stats = _build_expanded_cases()

    print("=== 골든셋 확장 (LLM-judge YES 추가) ===")
    print(f"원본 expected total: {stats['original_total']}")
    print(f"확장 expected total: {stats['expanded_total']}")
    print(f"추가된 article 수:    {stats['added']}")
    print()

    retriever = LegalDocumentRetriever()

    print("[1/2] 원본 골든셋으로 측정...")
    t0 = time.perf_counter()
    m_orig = await _run_with_cases(retriever, BENCHMARK_CASES, k=K)
    print(f"  완료 ({time.perf_counter() - t0:.1f}s)")

    print("[2/2] 확장 골든셋으로 측정...")
    t0 = time.perf_counter()
    m_exp = await _run_with_cases(retriever, expanded_cases, k=K)
    print(f"  완료 ({time.perf_counter() - t0:.1f}s)")
    print()

    # 비교 출력
    def fmt(label: str, val_o: float, val_e: float, suffix: str = "") -> str:
        delta = val_e - val_o
        sign = "+" if delta >= 0 else ""
        return f"  {label:<14} {val_o:.3f}{suffix}  →  {val_e:.3f}{suffix}  ({sign}{delta:.3f})"

    print("=== 비교 (원본 → 확장) ===")
    print(fmt("Recall@10", m_orig["recall@k"], m_exp["recall@k"]))
    print(fmt("Precision@10", m_orig["precision@k"], m_exp["precision@k"]))
    print(fmt("MRR", m_orig["mrr"], m_exp["mrr"]))
    print(fmt("NDCG@10", m_orig["ndcg@k"], m_exp["ndcg@k"]))
    print(fmt("Hit@10 rate", m_orig["hit@k_rate"], m_exp["hit@k_rate"]))
    print()

    # JSON 저장
    out_path = Path(__file__).resolve().parent.parent.parent / "bench_expanded_golden.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "k": K,
                "stats": stats,
                "metrics_original": m_orig,
                "metrics_expanded": m_exp,
                "expanded_cases": [
                    {"law": law, "query": q, "filter_attr": f, "expected": exp} for law, q, f, exp in expanded_cases
                ],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"saved → {out_path}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(main())
