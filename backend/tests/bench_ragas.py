"""SP6+ — Ragas 통합 RAG 정확도 평가.

기존 bench_human_golden.py (193 사람 라벨)에 Ragas 4지표 추가:
- LLMContextPrecisionWithReference  : retrieved chunk의 관련성 (rank-aware)
- LLMContextRecall                  : ground truth 정보가 retrieved chunk에 있는가
- Faithfulness  (옵션, --with-answer): LLM 답변이 청크에 충실한가 (환각 측정)
- ResponseRelevancy (옵션)          : LLM 답변이 질문에 적합한가

실행:
    cd backend && python -m tests.bench_ragas --sample 50
    cd backend && python -m tests.bench_ragas --sample 50 --with-answer

env:
    OPENAI_API_KEY   : Ragas LLM 평가에 사용 (gpt-4.1-mini)
    RAGAS_SAMPLE     : 케이스 샘플 수 (default 50 — 비용 절약)

비용 추정 (gpt-4.1-mini 기준):
    50 케이스 × 2 LLM calls (precision + recall) = 100 calls × $0.0002 = ~$0.02
    --with-answer: 추가 50 LLM calls + Ragas 평가 → ~$0.05
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import selectors
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.chains.retriever import LegalDocumentRetriever  # noqa: E402

# SP6: golden CSV 경로 — env (GOLDEN_CSV_PATH) > --golden-csv 인자 > 기본 경로 순.
# 기본 경로는 git 미추적 시 즉시 실패하므로 override 가능하게 함.
DEFAULT_GOLDEN_CSV = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "golden_set_v3_final.csv"
GOLDEN_CSV = Path(os.getenv("GOLDEN_CSV_PATH", str(DEFAULT_GOLDEN_CSV)))


def _load_cases(sample: int = 0, csv_path: Path | None = None) -> list[dict]:
    cases = []
    path = csv_path or GOLDEN_CSV
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            law = (row.get("law") or "").strip()
            query = (row.get("query") or "").strip()
            filter_attr = (row.get("source_filter") or "").strip()
            expected_str = (row.get("expected_articles") or "").strip()
            if not law or not query or not expected_str:
                continue
            expected = [a.strip() for a in expected_str.split("/") if a.strip()]
            cases.append({"law": law, "query": query, "filter_attr": filter_attr, "expected": expected})

    if sample and sample < len(cases):
        # 균등 sampling — 각 법률 카테고리에서 비율대로
        from collections import defaultdict

        by_law = defaultdict(list)
        for c in cases:
            by_law[c["law"]].append(c)
        sampled: list[dict] = []
        ratio = sample / len(cases)
        for _law, items in by_law.items():
            n = max(1, int(len(items) * ratio))
            sampled.extend(items[:n])
        return sampled[:sample]
    return cases


async def _retrieve_for_case(retriever, case: dict, k: int) -> list[str]:
    """case 1개에 대한 retrieved chunks 텍스트 list 반환."""
    sf = getattr(retriever, case["filter_attr"], None)
    docs = await retriever.search(case["query"], top_k=k, source_filter=sf)
    contexts = []
    for d in docs:
        content = d.get("content", "").strip()
        if content:
            contexts.append(content[:600])  # Ragas 비용 절약
    return contexts[:k]


_LAW_DB_MAP = {
    "가맹사업법": "가맹사업법",
    "개인정보보호법": "개인정보 보호법",
    "건축법": "건축법",
    "근로기준법": "근로기준법",
    "부가가치세법": "부가가치세법",
    "상가임대차보호법": "상가임대차법",
    "소방시설법": "소방시설법",
    "식품위생법": "식품위생법",
    # SP6+ 추가 fetch (2026-05-01)
    "공정거래법": "독점규제 및 공정거래에 관한 법률",
    "장애인편의법": "장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률",
    "하수도법": "하수도법",
}


async def _fetch_article_bodies(law: str, articles: list[str], conn) -> dict[str, str]:
    """expected article 번호 → 실제 본문 텍스트 fetch (article별 모든 row join)."""
    from collections import defaultdict

    from sqlalchemy import text as sql_text

    db_source = _LAW_DB_MAP.get(law)
    if not db_source or not articles:
        return {}
    rows = await conn.execute(
        sql_text(
            """
            SELECT cmetadata->>'article' AS art, document
            FROM langchain_pg_embedding
            WHERE cmetadata->>'category' = '법령_본문'
              AND cmetadata->>'source' = :source
              AND cmetadata->>'article' = ANY(:arts)
            """
        ),
        {"source": db_source, "arts": articles},
    )
    accum: dict[str, list[str]] = defaultdict(list)
    for art, doc in rows:
        if doc:
            accum[art].append(doc.strip())
    return {a: " ".join(parts) for a, parts in accum.items()}


def _build_reference(expected: list[str], law: str, bodies: dict[str, str]) -> str:
    """expected article 번호 → ground truth reference text.

    bodies dict에 실제 본문이 있으면 본문 인용, 없으면 article 번호만.
    """
    if not expected:
        return ""
    parts = []
    for art in expected:
        body = bodies.get(art)
        if body:
            snippet = body.strip()[:800]
            parts.append(f"[{art}] {snippet}")
        else:
            parts.append(f"[{art}] (본문 미수록)")
    return f"정답 조문 ({law}):\n" + "\n\n".join(parts)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=int(os.getenv("RAGAS_SAMPLE", "50")))
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--with-answer", action="store_true", help="LLM 답변 생성 + Faithfulness/Relevancy 평가")
    parser.add_argument(
        "--golden-csv",
        type=Path,
        default=GOLDEN_CSV,
        help="Golden set CSV 경로 (env GOLDEN_CSV_PATH 또는 기본 경로 override)",
    )
    args = parser.parse_args()

    print("=== Ragas RAG 평가 ===")
    print(f"CSV: {args.golden_csv}")
    cases = _load_cases(sample=args.sample, csv_path=args.golden_csv)
    print(f"케이스: {len(cases)}개 (샘플 {args.sample})")
    print(f"top_k: {args.top_k}, with_answer: {args.with_answer}")
    print()

    # Phase 1 — RAG 검색
    print(f"[1/3] RAG 검색 ({len(cases)}건)...")
    retriever = LegalDocumentRetriever()
    t0 = time.perf_counter()
    contexts_per_case = []
    for i, c in enumerate(cases, 1):
        contexts = await _retrieve_for_case(retriever, c, args.top_k)
        contexts_per_case.append(contexts)
        if i % 20 == 0:
            print(f"  retrieve {i}/{len(cases)} ({time.perf_counter() - t0:.1f}s)")
    print(f"  완료 ({time.perf_counter() - t0:.1f}s)")

    # Phase 2 — (옵션) LLM 답변 생성
    answers = []
    if args.with_answer:
        print(f"\n[2/3] LLM 답변 생성 ({len(cases)}건)...")
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage

        answer_llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
        t0 = time.perf_counter()
        for i, (c, ctxs) in enumerate(zip(cases, contexts_per_case), 1):
            ctx_text = "\n\n".join(f"[{j + 1}] {x}" for j, x in enumerate(ctxs[:5]))
            try:
                resp = await answer_llm.ainvoke(
                    [
                        SystemMessage(content="아래 법률 문서를 참고하여 질문에 답하세요. 근거 조문을 인용하세요."),
                        HumanMessage(content=f"질문: {c['query']}\n\n[참고 문서]\n{ctx_text}\n\n답변:"),
                    ]
                )
                answers.append(resp.content)
            except Exception as e:
                answers.append(f"답변 생성 실패: {e}")
            if i % 20 == 0:
                print(f"  answer {i}/{len(cases)} ({time.perf_counter() - t0:.1f}s)")
        print(f"  완료 ({time.perf_counter() - t0:.1f}s)")
    else:
        # answer 없을 때 Ragas는 reference 기반 metric만 사용
        answers = [""] * len(cases)

    # Phase 3 — Ragas 평가
    print("\n[3/3] Ragas 평가...")
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import LLMContextPrecisionWithReference, LLMContextRecall
    from langchain_openai import ChatOpenAI

    eval_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4.1-mini", temperature=0))

    # 조문 본문 fetch (Recall 정확도 향상 — reference에 실제 본문 인용)
    print("  조문 본문 fetch...")
    from sqlalchemy.ext.asyncio import create_async_engine

    pg_url = os.getenv("POSTGRES_URL", "").replace("postgresql://", "postgresql+asyncpg://")
    bodies_per_case: list[dict[str, str]] = []
    fetched = 0
    if pg_url:
        eng = create_async_engine(pg_url)
        async with eng.connect() as conn:
            for c in cases:
                bodies = await _fetch_article_bodies(c["law"], c["expected"], conn)
                bodies_per_case.append(bodies)
                fetched += len(bodies)
        await eng.dispose()
    else:
        bodies_per_case = [{} for _ in cases]
    print(f"  본문 fetch: {fetched} 조문 본문 / {sum(len(c['expected']) for c in cases)} 기대 조문")

    samples = []
    for c, ctxs, ans, bodies in zip(cases, contexts_per_case, answers, bodies_per_case):
        samples.append(
            {
                "user_input": c["query"],
                "retrieved_contexts": ctxs,
                "reference": _build_reference(c["expected"], c["law"], bodies),
                "response": ans,
            }
        )

    dataset = EvaluationDataset.from_list(samples)

    metrics = [
        LLMContextPrecisionWithReference(llm=eval_llm),
        LLMContextRecall(llm=eval_llm),
    ]
    if args.with_answer:
        from ragas.metrics import Faithfulness, ResponseRelevancy
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from langchain_huggingface import HuggingFaceEmbeddings

        emb = LangchainEmbeddingsWrapper(
            HuggingFaceEmbeddings(model_name="BAAI/bge-m3", model_kwargs={"device": "cpu"})
        )
        metrics.append(Faithfulness(llm=eval_llm))
        metrics.append(ResponseRelevancy(llm=eval_llm, embeddings=emb))

    t0 = time.perf_counter()
    result = evaluate(dataset=dataset, metrics=metrics)
    elapsed = time.perf_counter() - t0
    print(f"  완료 ({elapsed:.1f}s)")
    print()

    # 결과 출력
    print("##############################################")
    print("# Ragas 평가 결과 (193 사람 골든셋, 샘플)")
    print("##############################################")
    df = result.to_pandas()
    for col in df.columns:
        if col not in ("user_input", "retrieved_contexts", "reference", "response"):
            mean = df[col].mean() if df[col].dtype in ("float64", "int64") else None
            if mean is not None:
                print(f"  {col:<35} {mean:.3f}")
    print()
    print(f"케이스: {len(cases)} / 평가 시간: {elapsed:.1f}s")

    # JSON 저장
    out_path = Path(__file__).resolve().parent.parent.parent / "bench_ragas.json"
    df.to_json(str(out_path), orient="records", force_ascii=False, indent=2)
    print(f"saved → {out_path}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(main())
