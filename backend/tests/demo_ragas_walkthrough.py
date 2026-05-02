"""Ragas 동작 시각화 — 1 케이스 step-by-step.

흐름:
1. 골든셋에서 1 case 읽기
2. RAG 검색 (top_k=5)
3. DB에서 expected article 본문 fetch (reference)
4. Ragas Precision/Recall LLM judge 실행
5. 각 단계 출력

실행:
    cd backend
    python -m tests.demo_ragas_walkthrough
"""

from __future__ import annotations

import asyncio
import csv
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.chains.retriever import LegalDocumentRetriever  # noqa: E402
from tests.bench_ragas import (  # noqa: E402
    _LAW_DB_MAP,
    _build_reference,
    _fetch_article_bodies,
)


def hr(label: str = "") -> None:
    print("\n" + "=" * 70)
    if label:
        print(f"  {label}")
        print("=" * 70)


async def main() -> None:
    # --- 1단계: 골든셋 1 case ---
    hr("STEP 1 — 골든셋 (사람이 작성한 정답)")
    csv_path = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "golden_set_v3_final.csv"
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cases = [r for r in reader]

    # 첫 케이스 선택 (상가임대차보호법 - 10년 계약갱신)
    case = cases[0]
    print(f"law       : {case['law']}")
    print(f"query     : {case['query']}")
    print(f"source_filter : {case['source_filter']}")
    print(f"expected_articles : {case['expected_articles']}")
    expected = [a.strip() for a in case["expected_articles"].split("/")]
    source_filter_name = case["source_filter"]

    # --- 2단계: RAG 검색 (시스템이 청크 가져옴) ---
    hr("STEP 2 — RAG 검색 (top_k=5)")
    retriever = LegalDocumentRetriever()
    source_filter = getattr(LegalDocumentRetriever, source_filter_name, None)
    docs = await retriever.search(case["query"], top_k=5, source_filter=source_filter)
    for i, d in enumerate(docs, 1):
        meta = d.get("metadata") or {}
        art = meta.get("article", "?")
        src = meta.get("source", "?")
        content = (d.get("content") or "")[:120].replace("\n", " ")
        print(f"  [{i}] {src} {art}")
        print(f"      → {content}...")

    # 정답 article과 매칭 확인
    retrieved_articles = {(d.get("metadata") or {}).get("article", "") for d in docs}
    matched = [a for a in expected if a in retrieved_articles]
    print(f"\n  검색 결과 article: {sorted(retrieved_articles)}")
    print(f"  expected 매칭   : {matched} / {expected}")

    # --- 3단계: Reference 빌드 (DB에서 본문 fetch) ---
    hr("STEP 3 — Reference (DB에서 정답 article 본문 fetch)")
    from sqlalchemy import create_engine
    from sqlalchemy.ext.asyncio import create_async_engine

    pg_url = os.environ["POSTGRES_URL"].replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(pg_url)
    try:
        async with engine.connect() as conn:
            bodies = await _fetch_article_bodies(case["law"], expected, conn)
    finally:
        await engine.dispose()

    print(f"  DB fetch 결과 ({len(bodies)} articles):")
    for art, body in bodies.items():
        print(f"    {art}: {body[:100]}...")
    reference = _build_reference(expected, case["law"], bodies)
    print(f"\n  reference 빌드 (총 {len(reference)} chars):")
    print(f"    {reference[:300]}...")

    # --- 4단계: Ragas Precision/Recall 실행 ---
    hr("STEP 4 — Ragas LLM judge (gpt-4.1-mini)")
    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import LLMContextPrecisionWithReference, LLMContextRecall

    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
    ragas_llm = LangchainLLMWrapper(llm)

    contexts = [d.get("content") or "" for d in docs]
    sample = {
        "user_input": case["query"],
        "reference": reference,
        "retrieved_contexts": contexts,
    }

    print(f"  Precision LLM judge: 각 청크마다 'reference 답변에 유용?' 0/1 판정")
    print(f"  Recall LLM judge   : reference의 각 statement가 청크에 있는지 0/1 판정")
    print(f"  쿼리: {case['query']}")
    print(f"  청크 5개 + reference 800자 → LLM 비교 중...\n")

    from ragas.dataset_schema import SingleTurnSample

    sample_obj = SingleTurnSample(**sample)

    precision_metric = LLMContextPrecisionWithReference(llm=ragas_llm)
    recall_metric = LLMContextRecall(llm=ragas_llm)

    p_score = await precision_metric.single_turn_ascore(sample_obj)
    r_score = await recall_metric.single_turn_ascore(sample_obj)

    print(f"  ContextPrecision = {p_score:.3f}")
    print(f"  ContextRecall    = {r_score:.3f}")

    hr("끝")
    print("Precision = retrieved 청크 중 정답에 유용한 비율 (rank-aware)")
    print("Recall    = 정답 reference 중 청크에 표현된 비율")
    print("\n44 케이스 전체 평균이 SP6+ 측정값:")
    print("  현재 baseline: Precision 0.676 / Recall 0.682")


if __name__ == "__main__":
    asyncio.run(main())
