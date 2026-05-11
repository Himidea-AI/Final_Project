"""Ragas 탐색 demo — 다중 케이스 점수 분포 + 어려운 케이스 분석 + 임의 query.

흐름:
A. 골든셋 sample=10 → Precision/Recall 점수 분포
B. 점수 0~0.5 (어려운 케이스) 분석 — 왜 낮은지
C. 임의 query (RAG 결과만, reference 없이) 5개 시연

실행:
    cd backend && python -m tests.demo_ragas_explore
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
    _build_reference,
    _fetch_article_bodies,
)


def hr(label: str = "") -> None:
    print("\n" + "=" * 70)
    if label:
        print(f"  {label}")
        print("=" * 70)


async def evaluate_case(case: dict, retriever, ragas_llm, engine) -> dict:
    """1 case → Precision + Recall + 매칭 article 수.

    매 케이스마다 새 connection 사용 (LLM 호출 사이 idle timeout 방지).
    """
    from ragas.dataset_schema import SingleTurnSample
    from ragas.metrics import LLMContextPrecisionWithReference, LLMContextRecall

    expected = [a.strip() for a in case["expected_articles"].split("/")]
    source_filter = getattr(LegalDocumentRetriever, case["source_filter"], None)

    docs = await retriever.search(case["query"], top_k=5, source_filter=source_filter)
    retrieved_articles = [(d.get("metadata") or {}).get("article", "") for d in docs]
    matched_count = len(set(expected) & set(retrieved_articles))

    async with engine.connect() as conn:
        bodies = await _fetch_article_bodies(case["law"], expected, conn)
    reference = _build_reference(expected, case["law"], bodies)
    contexts = [d.get("content") or "" for d in docs]

    sample = SingleTurnSample(
        user_input=case["query"],
        reference=reference,
        retrieved_contexts=contexts,
    )
    p_metric = LLMContextPrecisionWithReference(llm=ragas_llm)
    r_metric = LLMContextRecall(llm=ragas_llm)

    p = await p_metric.single_turn_ascore(sample)
    r = await r_metric.single_turn_ascore(sample)

    return {
        "law": case["law"],
        "query": case["query"][:50],
        "expected": expected,
        "retrieved": retrieved_articles,
        "matched_count": matched_count,
        "precision": float(p),
        "recall": float(r),
    }


async def main() -> None:
    csv_path = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "golden_set_v3_final.csv"
    with open(csv_path, encoding="utf-8-sig") as f:
        cases = list(csv.DictReader(f))

    # 다양성 확보 — 법령별 1~2개씩 샘플링
    seen_laws: dict[str, int] = {}
    sample_cases: list[dict] = []
    for c in cases:
        law = c["law"]
        if seen_laws.get(law, 0) < 2:
            sample_cases.append(c)
            seen_laws[law] = seen_laws.get(law, 0) + 1
        if len(sample_cases) >= 10:
            break

    # ─────────────────────────────────────────────
    # A — sample=10 점수 분포
    # ─────────────────────────────────────────────
    hr(f"PART A — {len(sample_cases)} 케이스 점수 분포")
    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper

    llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
    ragas_llm = LangchainLLMWrapper(llm)

    from sqlalchemy.ext.asyncio import create_async_engine

    pg_url = os.environ["POSTGRES_URL"].replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(pg_url)
    retriever = LegalDocumentRetriever()

    results: list[dict] = []
    try:
        for i, c in enumerate(sample_cases, 1):
            print(f"  [{i}/{len(sample_cases)}] {c['law']:14s} {c['query'][:40]}...")
            r = await evaluate_case(c, retriever, ragas_llm, engine)
            results.append(r)
            print(
                f"      매칭 {r['matched_count']}/{len(r['expected'])}  "
                f"P={r['precision']:.2f}  R={r['recall']:.2f}"
            )
    finally:
        await engine.dispose()

    # 평균
    avg_p = sum(r["precision"] for r in results) / len(results)
    avg_r = sum(r["recall"] for r in results) / len(results)
    print(f"\n  평균: Precision {avg_p:.3f} / Recall {avg_r:.3f}")

    # ─────────────────────────────────────────────
    # B — 어려운 케이스 분석 (점수 낮은 것)
    # ─────────────────────────────────────────────
    hr("PART B — 어려운 케이스 분석 (P or R < 0.6)")
    hard = [r for r in results if r["precision"] < 0.6 or r["recall"] < 0.6]
    if not hard:
        print("  (점수 낮은 케이스 없음 — 샘플이 쉬움)")
        # 그래도 가장 낮은 것 1개 보여줌
        worst = min(results, key=lambda x: x["precision"] + x["recall"])
        hard = [worst]
        print("  대신 가장 낮은 케이스:")
    for r in hard:
        expected_set = set(r["expected"])
        retrieved_set = set(r["retrieved"])
        miss = expected_set - retrieved_set
        extra = retrieved_set - expected_set
        print(f"\n  [{r['law']}] {r['query']}")
        print(f"    expected : {r['expected']}")
        print(f"    retrieved: {r['retrieved']}")
        print(f"    miss     : {sorted(miss)}  ← RAG가 못 찾음")
        print(f"    extra    : {sorted(extra)}  ← RAG가 추가로 가져옴")
        print(f"    P={r['precision']:.2f} R={r['recall']:.2f}")
        print("    원인 후보:")
        if miss:
            print("      • 누락 article — query 키워드와 본문 의미 매칭 부족")
        if extra:
            print("      • 추가 article — 의미상 연관성 있어 RAG가 가져옴 (false positive 아님)")

    # ─────────────────────────────────────────────
    # C — 임의 query 시연 (reference 없이 RAG 결과만)
    # ─────────────────────────────────────────────
    hr("PART C — 임의 query 시연 (RAG 결과만)")
    custom_queries = [
        ("커피숍 영업신고 구청 어디", "FOOD_HYGIENE_SOURCES"),
        ("프랜차이즈 영업지역 보호", "FRANCHISE_LAW_SOURCES"),
        ("CCTV 안내판 부착 의무", "PRIVACY_LAW_SOURCES"),
        ("최저임금 미지급 처벌", "LABOR_LAW_SOURCES"),
        ("그리스트랩 음식점 의무", "SEWAGE_LAW_SOURCES"),
    ]
    for q, sf_name in custom_queries:
        sf = getattr(LegalDocumentRetriever, sf_name, None)
        docs = await retriever.search(q, top_k=3, source_filter=sf)
        print(f"\n  query: '{q}'  (filter={sf_name})")
        for j, d in enumerate(docs, 1):
            meta = d.get("metadata") or {}
            art = meta.get("article", "?")
            src = meta.get("source", "?")
            content = (d.get("content") or "")[:80].replace("\n", " ")
            print(f"    [{j}] {src} {art} → {content}...")

    hr("끝")
    print("관찰:")
    print("- 평균 점수 = 사람 직관과 약간 다름 (Ragas는 의미 기반 LLM 판정)")
    print("- 어려운 케이스 = query 키워드 부족 / 동의어 / cross-법령 참조")
    print("- top_k 5는 핵심 article 누락 가능성 — 8 절충 또는 multi-query N=5 시도")


if __name__ == "__main__":
    asyncio.run(main())
