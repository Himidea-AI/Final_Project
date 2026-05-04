"""1회용 정성 테스트 — 실 사용자 시뮬레이션 쿼리 5종에 대해 retrieval top-5 dump.

BENCHMARK_CASES 외 자연어 쿼리에 retrieval이 overfit되지 않았는지 사람이 검토.
RRF default (vector=0.4 / bm25=0.6) 환경 사용.

실행:
    cd backend && python scripts/verify/_qual_test_rag.py

작업 종료 시 삭제 예정.
"""

from __future__ import annotations

import asyncio
import selectors
import sys
from pathlib import Path

# backend/ 를 sys.path 에 추가 (scripts/verify/_qual_test_rag.py 기준)
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from src.chains.retriever import LegalDocumentRetriever  # noqa: E402

QUERIES = [
    "마포구 망원동에서 카페 차리려는데 위생교육 받아야 하나",
    "직원 5명 음식점인데 주휴수당 안 줘도 되나",
    "임차인이 권리금 못 받았다고 소송 걸었는데 임대인 책임",
    "건축법상 근린생활시설 1종 vs 2종 차이",
    "프랜차이즈 가맹비 환불 가능한가",
]


async def main() -> None:
    retriever = LegalDocumentRetriever()
    print("=" * 90)
    print("정성 테스트 — RAG retrieval top-5 (RRF default vec=0.4/bm25=0.6, primary_boost=2.0)")
    print("=" * 90)

    for i, q in enumerate(QUERIES, 1):
        print(f"\n[Q{i}] {q}")
        print("-" * 90)
        try:
            docs = await retriever.search(q, top_k=5)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        if not docs:
            print("  (no results)")
            continue

        for rank, d in enumerate(docs, 1):
            md = d.get("metadata", {}) or {}
            article = md.get("article", "?")
            source = md.get("source", "?")
            category = md.get("category", "?")
            content = (d.get("content") or d.get("page_content") or "")[:120].replace("\n", " ")
            print(f"  {rank}. [{source}] {article} ({category})")
            print(f"     {content}...")

    print("\n" + "=" * 90)
    print("end")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(main())
