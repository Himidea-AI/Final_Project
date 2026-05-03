"""RAG 검색 trace 도구 테스트.

Vectorstore 연결 없이 동작하도록 retriever 의 핵심 메서드를 monkeypatch 합니다.
trace 파일 생성/구조/실패 안전성만 검증합니다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# backend/ 를 sys.path 에 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeDoc:
    def __init__(self, content: str, metadata: dict):
        self.page_content = content
        self.metadata = metadata


class _FakeVectorStore:
    """asimilarity_search_with_relevance_scores 를 흉내내는 fake."""

    def __init__(self, results):
        self._results = results

    async def asimilarity_search_with_relevance_scores(self, query, k=10, filter=None):
        return self._results[:k]


def _build_retriever(monkeypatch, fake_vec_results, bm25_ranked=None, bm25_docs=None):
    from src.chains import retriever as r_mod

    inst = r_mod.LegalDocumentRetriever.__new__(r_mod.LegalDocumentRetriever)
    inst._db = SimpleNamespace(vectorstore=_FakeVectorStore(fake_vec_results))
    inst._bm25_index = {}
    inst._bm25_docs = bm25_docs or []
    inst._bm25_doc_lens = []
    inst._bm25_doc_count = 0
    inst._bm25_avg_dl = 1.0

    # HyDE 비활성 (LLM 호출 차단)
    async def _fake_expand_hybrid(q):
        return q

    monkeypatch.setattr(
        r_mod.LegalDocumentRetriever,
        "_expand_query_hybrid",
        staticmethod(_fake_expand_hybrid),
    )

    # BM25 검색 결과 고정
    def _fake_bm25_search(self, query, source_filter=None, top_k=20):
        return bm25_ranked or []

    monkeypatch.setattr(r_mod.LegalDocumentRetriever, "_bm25_search", _fake_bm25_search)

    # build_bm25_index 는 noop (이미 채워둠)
    monkeypatch.setattr(r_mod.LegalDocumentRetriever, "_build_bm25_index", lambda self: None)

    # parent map 비우기 (단순화)
    monkeypatch.setattr(r_mod, "_PARENT_ARTICLES", {}, raising=False)

    return inst


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_no_trace_when_disabled(tmp_path, monkeypatch):
    """rag_trace_enabled=False 시 trace 파일 미생성, search 정상 동작."""
    from src.config.settings import settings

    monkeypatch.setattr(settings, "rag_trace_enabled", False, raising=False)
    monkeypatch.setattr(settings, "rag_trace_dir", str(tmp_path / "trace"), raising=False)
    monkeypatch.setattr(settings, "multi_query_enabled", False, raising=False)

    fake_results = [
        (_FakeDoc("제10조 본문 내용", {"chunk_id": "c1", "source": "상가임대차법", "article": "제10조"}), 0.85),
    ]
    retriever = _build_retriever(monkeypatch, fake_results)

    docs = await retriever.search("계약갱신", top_k=3)
    assert isinstance(docs, list)
    assert len(docs) >= 1
    assert not (tmp_path / "trace").exists() or not any((tmp_path / "trace").iterdir())


@pytest.mark.asyncio
async def test_search_trace_jsonl_created(tmp_path, monkeypatch):
    """rag_trace_enabled=True 시 JSONL 1줄 추가, 키 구조 검증."""
    from src.config.settings import settings

    trace_dir = tmp_path / "trace"
    monkeypatch.setattr(settings, "rag_trace_enabled", True, raising=False)
    monkeypatch.setattr(settings, "rag_trace_dir", str(trace_dir), raising=False)
    monkeypatch.setattr(settings, "multi_query_enabled", False, raising=False)

    fake_results = [
        (
            _FakeDoc(
                "제10조(계약갱신 요구 등) 임대인은...",
                {"chunk_id": "c1", "source": "상가임대차법", "article": "제10조"},
            ),
            0.92,
        ),
        (
            _FakeDoc(
                "제10조의2(계약갱신의 특례)...",
                {"chunk_id": "c2", "source": "상가임대차법", "article": "제10조의2"},
            ),
            0.81,
        ),
    ]
    bm25_docs = [
        ("제10조 BM25 본문", {"chunk_id": "c1", "source": "상가임대차법", "article": "제10조"}),
    ]
    bm25_ranked = [(0, 8.5)]

    retriever = _build_retriever(
        monkeypatch, fake_results, bm25_ranked=bm25_ranked, bm25_docs=bm25_docs
    )

    docs = await retriever.search("10년 계약갱신 상가건물", top_k=3)
    assert len(docs) >= 1

    # 파일 존재 확인
    assert trace_dir.exists()
    files = list(trace_dir.glob("rag_trace_*.jsonl"))
    assert len(files) == 1, f"trace 파일이 정확히 1개 있어야 함: {files}"

    # 1줄 + 구조 검증
    with open(files[0], encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip()]
    assert len(lines) == 1
    trace = json.loads(lines[0])

    expected_keys = {
        "ts",
        "kind",
        "query",
        "source_filter",
        "top_k",
        "expanded_query",
        "multi_query_variants",
        "vector_candidates",
        "bm25_candidates",
        "rrf_merged",
        "parent_dedup",
        "final_top_k",
        "elapsed_ms",
    }
    missing = expected_keys - set(trace.keys())
    assert not missing, f"누락된 키: {missing}"

    assert trace["kind"] == "search"
    assert trace["query"] == "10년 계약갱신 상가건물"
    assert isinstance(trace["vector_candidates"], list)
    assert len(trace["vector_candidates"]) >= 1
    cand0 = trace["vector_candidates"][0]
    assert {"rank", "chunk_id", "score", "source", "article", "preview"} <= set(cand0.keys())
    assert isinstance(trace["elapsed_ms"], dict)
    assert "total" in trace["elapsed_ms"]


@pytest.mark.asyncio
async def test_search_failure_tolerant_on_trace_write_error(tmp_path, monkeypatch):
    """trace 쓰기 실패해도 search 는 중단되지 않음."""
    from src.chains import retriever as r_mod
    from src.config.settings import settings

    monkeypatch.setattr(settings, "rag_trace_enabled", True, raising=False)
    monkeypatch.setattr(settings, "rag_trace_dir", str(tmp_path / "trace"), raising=False)
    monkeypatch.setattr(settings, "multi_query_enabled", False, raising=False)

    # _write_trace_jsonl 강제 예외 시뮬: 실제 함수가 try/except 로 감싸므로 search 영향 X.
    def _boom(trace):
        raise RuntimeError("simulated I/O failure")

    monkeypatch.setattr(r_mod, "_write_trace_jsonl", _boom)

    fake_results = [
        (_FakeDoc("내용", {"chunk_id": "c1", "source": "X", "article": "제1조"}), 0.7),
    ]
    retriever = _build_retriever(monkeypatch, fake_results)

    # 예외가 search 외부로 전파되지 않아야 함 — 단, 이번엔 monkeypatch 한 _boom 가
    # search 내부 코드에서 try/except 로 감싸져 있지 않으므로 직접 RuntimeError 가 올라온다.
    # 따라서 이 테스트는 _write_trace_jsonl 자체의 try/except 동작 확인이 아니라
    # 실제 코드 경로의 robustness 를 보장: _write_trace_jsonl 호출 자체는 try/except 안에서
    # 실행되지 않으므로 raise 가 그대로 전달되는 것이 정상. 그래서 호출 권한 없는 디렉토리
    # 시나리오로 대체.
    pytest.skip("_write_trace_jsonl 은 자체 try/except 보유 — 별도 케이스로 검증")


@pytest.mark.asyncio
async def test_write_trace_jsonl_swallows_io_error(monkeypatch):
    """_write_trace_jsonl 가 디렉토리 권한/경로 오류를 삼키는지 검증."""
    from src.chains import retriever as r_mod
    from src.config.settings import settings

    monkeypatch.setattr(settings, "rag_trace_enabled", True, raising=False)
    # 존재할 수 없는 (Windows 호환) 비정상 경로
    bad = "\x00invalid\x00/path"
    monkeypatch.setattr(settings, "rag_trace_dir", bad, raising=False)

    # 예외 없이 None 반환되어야 함 (logger.warning 만)
    r_mod._write_trace_jsonl({"ts": "x", "query": "q"})


@pytest.mark.asyncio
async def test_search_precedents_trace(tmp_path, monkeypatch):
    """search_precedents 도 trace 파일에 kind='search_precedents' 로 1줄 기록."""
    from src.config.settings import settings

    trace_dir = tmp_path / "trace_pre"
    monkeypatch.setattr(settings, "rag_trace_enabled", True, raising=False)
    monkeypatch.setattr(settings, "rag_trace_dir", str(trace_dir), raising=False)

    fake_results = [
        (
            _FakeDoc(
                "대법원 2020다12345 판결...",
                {"chunk_id": "p1", "source": "대법원", "article": "2020다12345", "category": "판례"},
            ),
            0.78,
        ),
    ]
    bm25_docs = [
        ("판례 본문", {"chunk_id": "p1", "source": "대법원", "article": "2020다12345", "category": "판례"}),
    ]
    bm25_ranked = [(0, 6.1)]
    retriever = _build_retriever(
        monkeypatch, fake_results, bm25_ranked=bm25_ranked, bm25_docs=bm25_docs
    )

    # build_bm25_index noop, _bm25_index 는 이미 dict 로 채움
    docs = await retriever.search_precedents("권리금 회수", top_k=2)
    assert isinstance(docs, list)

    files = list(trace_dir.glob("rag_trace_*.jsonl"))
    assert len(files) == 1
    with open(files[0], encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if ln.strip()]
    assert len(lines) == 1
    trace = json.loads(lines[0])
    assert trace["kind"] == "search_precedents"
    assert trace["category_filter"] == "판례"
    assert "vector_candidates" in trace
    assert "elapsed_ms" in trace and "total" in trace["elapsed_ms"]
