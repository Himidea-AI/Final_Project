"""1회용: 한 쿼리에 대해 retrieval 단계별 trace 출력."""

import asyncio
import os
import selectors
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
for p in (Path(__file__).parents[2] / ".env", Path(__file__).parents[3] / ".env"):
    if p.exists():
        load_dotenv(p)
        break

# trace 활성
os.environ["RAG_TRACE_ENABLED"] = "true"
os.environ["RAG_TRACE_DIR"] = "rag_trace_inspect"

# parent path
sys.path.insert(0, str(Path(__file__).parents[2]))


async def main() -> None:
    from src.chains.retriever import LegalDocumentRetriever

    retriever = LegalDocumentRetriever()

    QUERY = "권리금 회수 기회 보호 상가임대차보호법"
    SOURCE_FILTER = retriever.LEASE_LAW_STRICT_SOURCES

    print("=" * 72)
    print(f"QUERY: {QUERY}")
    print(f"SOURCE_FILTER: {SOURCE_FILTER}")
    print("=" * 72)

    # HyDE 확장 미리보기
    expanded = await retriever._expand_query_hybrid(QUERY)
    print(f"\n[0차 HyDE 확장]\n  original : {QUERY}")
    print(f"  expanded : {expanded}\n")

    # vector top-5 직접 호출
    vs = retriever._db.vectorstore
    filt = {"source": {"$in": SOURCE_FILTER}}
    vec = await vs.asimilarity_search_with_relevance_scores(QUERY, k=5, filter=filt)
    print("[1차 Vector top-5]")
    for i, (doc, score) in enumerate(vec, 1):
        m = doc.metadata
        print(
            f"  {i}. score={score:.4f} | {m.get('source')} {m.get('article')} | {doc.page_content[:60]}..."
        )

    # BM25 top-5
    bm25 = retriever._bm25_search(QUERY, SOURCE_FILTER, top_k=5)
    print("\n[2차 BM25 top-5]")
    for i, (idx, sc) in enumerate(bm25, 1):
        text, meta = retriever._bm25_docs[idx] if idx < len(retriever._bm25_docs) else ("", {})
        print(
            f"  {i}. score={sc:.4f} | {meta.get('source')} {meta.get('article')} | {text[:60]}..."
        )

    # 최종 (RRF + parent dedup)
    final = await retriever.search(QUERY, top_k=10, source_filter=SOURCE_FILTER)
    print("\n[3-7차 최종 RRF+parent_dedup top-10]")
    for i, doc in enumerate(final, 1):
        m = doc.get("metadata", {})
        is_parent = "P" if m.get("is_parent") else " "
        print(
            f"  {i}. [{is_parent}] {m.get('source')} {m.get('article')} | rel={m.get('relevance')} | {doc.get('content', '')[:60]}..."
        )


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(main())
