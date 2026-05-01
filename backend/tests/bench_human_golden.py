"""SP3 — 사람 라벨 golden_set_v3_final.csv로 RAG 객관 측정.

CSV 포맷: law,query,source_filter,expected_articles
expected_articles 구분자: ' / ' (slash with spaces).

193 케이스 (header 제외) — A2 봉환 작성. 사람이 직접 라벨한 정답이라 LLM-judge
augmentation 같은 self-fulfilling 위험 없음. **이 측정이 객관 baseline**.

실행:
    cd backend && python -m tests.bench_human_golden
"""

from __future__ import annotations

import asyncio
import csv
import json
import re
import selectors
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.chains.retriever import LegalDocumentRetriever  # noqa: E402

from .bench_rag_accuracy import compute_rag_metrics  # noqa: E402


GOLDEN_CSV = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "golden_set_v3_final.csv"


def _load_cases() -> list[tuple[str, str, str, list[str]]]:
    """CSV → [(law, query, filter_attr, expected_articles), ...]"""
    cases = []
    with open(GOLDEN_CSV, encoding="utf-8-sig") as f:  # utf-8-sig: BOM 처리
        reader = csv.DictReader(f)
        for row in reader:
            law = (row.get("law") or "").strip()
            query = (row.get("query") or "").strip()
            filter_attr = (row.get("source_filter") or "").strip()
            expected_str = (row.get("expected_articles") or "").strip()
            if not law or not query or not expected_str:
                continue
            expected = [a.strip() for a in expected_str.split("/") if a.strip()]
            cases.append((law, query, filter_attr, expected))
    return cases


async def _run(retriever: LegalDocumentRetriever, cases: list[tuple], k: int = 10) -> tuple[dict, list[dict]]:
    metrics_per_case = []
    per_case_records = []
    for law, query, filter_attr, expected in cases:
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
        per_case_records.append(
            {
                "law": law,
                "query": query[:60],
                "expected": expected,
                "retrieved_top": ranked[:k],
                "metrics": m,
            }
        )

    n = len(metrics_per_case)
    aggregate = {
        "recall@k": sum(m["recall@k"] for m in metrics_per_case) / n,
        "precision@k": sum(m["precision@k"] for m in metrics_per_case) / n,
        "mrr": sum(m["mrr"] for m in metrics_per_case) / n,
        "ndcg@k": sum(m["ndcg@k"] for m in metrics_per_case) / n,
        "hit@k_rate": sum(m["hit@k"] for m in metrics_per_case) / n,
        "n_cases": n,
    }
    return aggregate, per_case_records


async def main() -> None:
    K = 10
    cases = _load_cases()
    print("=== 사람 라벨 골든셋 측정 (golden_set_v3_final.csv) ===")
    print(f"CSV: {GOLDEN_CSV}")
    print(f"케이스 수: {len(cases)}")
    print()

    retriever = LegalDocumentRetriever()

    print(f"측정 시작 (top_k={K}, 약 {len(cases) * 2}~{len(cases) * 4}초 예상)...")
    t0 = time.perf_counter()
    aggregate, records = await _run(retriever, cases, k=K)
    elapsed = time.perf_counter() - t0
    print(f"완료 ({elapsed:.1f}s, {elapsed / len(cases):.2f}s/case)")
    print()

    print("=== 집계 ===")
    print(f"  Recall@10    : {aggregate['recall@k']:.3f}")
    print(f"  Precision@10 : {aggregate['precision@k']:.3f}")
    print(f"  MRR          : {aggregate['mrr']:.3f}")
    print(f"  NDCG@10      : {aggregate['ndcg@k']:.3f}")
    print(f"  Hit@10 rate  : {aggregate['hit@k_rate'] * 100:.1f}%")
    print(f"  케이스 수    : {aggregate['n_cases']}")
    print()

    # 법률별 분포
    by_law: dict[str, list[dict]] = {}
    for r in records:
        by_law.setdefault(r["law"], []).append(r["metrics"])
    print("=== 법률별 평균 ===")
    print(f"{'법률':<16} {'#':>4} {'R@10':>6} {'MRR':>6} {'NDCG':>6} {'Hit':>5}")
    print("-" * 50)
    for law, ms in sorted(by_law.items(), key=lambda x: -len(x[1])):
        n = len(ms)
        r = sum(m["recall@k"] for m in ms) / n
        mr = sum(m["mrr"] for m in ms) / n
        ng = sum(m["ndcg@k"] for m in ms) / n
        hit = sum(m["hit@k"] for m in ms) / n
        print(f"{law:<16} {n:>4} {r:>6.3f} {mr:>6.3f} {ng:>6.3f} {hit * 100:>4.0f}%")

    # JSON 저장
    out_path = Path(__file__).resolve().parent.parent.parent / "bench_human_golden.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "k": K,
                "n_cases": len(cases),
                "elapsed_s": round(elapsed, 1),
                "aggregate": aggregate,
                "by_law": {
                    law: {
                        "n": len(ms),
                        "recall@k": sum(m["recall@k"] for m in ms) / len(ms),
                        "mrr": sum(m["mrr"] for m in ms) / len(ms),
                        "ndcg@k": sum(m["ndcg@k"] for m in ms) / len(ms),
                        "hit@k_rate": sum(m["hit@k"] for m in ms) / len(ms),
                    }
                    for law, ms in by_law.items()
                },
                "records": records,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\nsaved → {out_path}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(main())
