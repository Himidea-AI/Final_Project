"""RAG 검색 trace 도구 demo — 한 쿼리로 search() 실행 후 trace 파일 생성·예쁘게 출력.

실행:
    python -m backend.tests.demo_rag_trace
또는 backend 디렉토리 내에서:
    python tests/demo_rag_trace.py [선택: 검색어]

기본 검색어: "10년 계약갱신 기간 상가건물"

이 스크립트는 RAG_TRACE_ENABLED=true 를 강제 설정한 뒤 search() 를 호출하고,
생성된 JSONL의 마지막 줄을 읽어 사람이 보기 좋게 콘솔에 출력합니다.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import os
import sys
from pathlib import Path

# Windows asyncpg 호환 — ProactorEventLoop 회피
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _print_trace(trace: dict) -> None:
    """trace 1건을 사람이 읽기 좋게 출력."""
    print("=== RAG Trace ===")
    print(f"query: {trace.get('query')!r}")
    print(f"kind:  {trace.get('kind')}")
    print(f"top_k: {trace.get('top_k')}  source_filter: {trace.get('source_filter')}")
    print()

    expanded = trace.get("expanded_query")
    if expanded:
        print("[HyDE 확장]")
        if expanded == trace.get("query"):
            print("  (변경 없음 — 사전 매칭 안됨, HyDE_ENABLED=false 일 수 있음)")
        else:
            preview = expanded if len(expanded) <= 200 else expanded[:200] + "..."
            print(f"  -> {preview}")
        print()

    mq = trace.get("multi_query_variants")
    print("[Multi-query 변형]")
    if mq:
        for i, v in enumerate(mq, 1):
            print(f"  {i}. {v}")
    else:
        print("  (multi_query_enabled=false 또는 변형 없음)")
    print()

    vec = trace.get("vector_candidates") or []
    print(f"[벡터 후보 top {len(vec)}]")
    for c in vec:
        src = c.get("source") or "?"
        art = c.get("article") or "?"
        sc = c.get("score")
        print(f"  {c.get('rank'):>2}. {src} {art} (score {sc})")
        prev = (c.get("preview") or "").replace("\n", " ")
        if prev:
            print(f"      -> {prev[:120]}")
    print()

    bm = trace.get("bm25_candidates") or []
    print(f"[BM25 후보 top {len(bm)}]")
    for c in bm:
        src = c.get("source") or "?"
        art = c.get("article") or "?"
        sc = c.get("score")
        print(f"  {c.get('rank'):>2}. {src} {art} (score {sc})")
    print()

    rrf = trace.get("rrf_merged") or []
    print(f"[RRF 결합 top {len(rrf)}]")
    for c in rrf:
        src = c.get("source") or "?"
        art = c.get("article") or "?"
        rel = c.get("relevance")
        print(f"  {c.get('rank'):>2}. {src} {art} (relevance {rel})")
    print()

    pd = trace.get("parent_dedup") or {}
    if pd:
        print("[Parent dedup]")
        print(
            f"  before={pd.get('before_count')}, after={pd.get('after_count')}, "
            f"dropped={len(pd.get('dropped_chunk_ids') or [])}, "
            f"replaced={len(pd.get('parent_replacements') or [])}"
        )
        print()

    final = trace.get("final_top_k") or []
    print(f"[최종 top_k={len(final)}]")
    for c in final:
        src = c.get("source") or "?"
        art = c.get("article") or "?"
        is_parent = c.get("is_parent")
        prev = (c.get("preview") or "").replace("\n", " ")
        tag = " (parent)" if is_parent else ""
        print(f"  {c.get('rank'):>2}. {src} {art}{tag}")
        if prev:
            print(f"      -> {prev[:120]}")
    print()

    el = trace.get("elapsed_ms") or {}
    print(
        "elapsed: "
        + ", ".join(f"{k}={v}ms" for k, v in el.items())
    )


async def _run(query: str) -> None:
    # trace 강제 활성화 (env 우선)
    os.environ["RAG_TRACE_ENABLED"] = "true"

    # settings 가 import 시점에 env 를 읽으므로, 이 시점 이전 env 강제 설정 필요.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ 를 path 에 추가

    from src.chains.retriever import LegalDocumentRetriever
    from src.config.settings import settings

    # settings 객체가 캐시된 경우를 대비해 강제 override
    settings.rag_trace_enabled = True

    trace_dir = Path(settings.rag_trace_dir)
    trace_dir.mkdir(parents=True, exist_ok=True)
    print(f"[demo] trace_dir = {trace_dir.resolve()}")
    print(f"[demo] query = {query!r}")
    print()

    retriever = LegalDocumentRetriever()
    try:
        results = await retriever.search(query=query, top_k=5)
    except Exception as e:
        print(f"[demo] search 실패 (vectorstore 미연결 가능): {type(e).__name__}: {e}")
        return

    print(f"[demo] search 반환 문서 수: {len(results)}")

    # 마지막 줄 trace 읽기 — 시간 단위 파일 분할
    fname = trace_dir / f"rag_trace_{datetime.datetime.utcnow().strftime('%Y%m%d_%H')}.jsonl"
    if not fname.exists():
        print(f"[demo] trace 파일이 생성되지 않음 (예상 경로: {fname})")
        return

    last_line = ""
    with open(fname, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                last_line = line
    if not last_line:
        print(f"[demo] trace 파일은 있으나 비어있음: {fname}")
        return

    print(f"[demo] trace 파일: {fname}")
    print()
    try:
        trace = json.loads(last_line)
    except Exception as e:
        print(f"[demo] trace JSON 파싱 실패: {e}")
        return
    _print_trace(trace)


def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "10년 계약갱신 기간 상가건물"
    asyncio.run(_run(query))


if __name__ == "__main__":
    main()
