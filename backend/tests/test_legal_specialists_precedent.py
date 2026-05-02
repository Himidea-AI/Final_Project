"""법률 specialist 판례(precedent) RAG 통합 unit tests.

검증 항목:
1. ``_articles_from_precedent_docs`` 가 판례 메타데이터 → ``kind='precedent'`` 형태로 변환.
2. ``_articles_from_law_docs`` 가 ``category='판례'`` 청크는 자동으로 제외.
3. ``LegalDocumentRetriever.search_precedents`` 시그니처 (async, top_k 기본값).
4. ``_search_precedents_safe`` flag 비활성/예외 시 빈 리스트 반환 (graceful).
5. specialist mock 실행 결과 articles 에 판례 prepend (kind='precedent') 포함.
6. ``_format_precedents`` 빈 입력 → ``(관련 판례 없음)`` 텍스트.
7. precedent query builder 도메인 키워드 포함.

LLM/DB 의존성은 monkeypatch 로 stub.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src.agents.legal import specialists  # noqa: E402
from src.agents.legal.specialists import (  # noqa: E402
    _articles_from_law_docs,
    _articles_from_precedent_docs,
    _explain_articles_batch,
    _format_precedents,
    _precedent_query_building,
    _precedent_query_fair_trade,
    _precedent_query_franchise,
    _precedent_query_privacy,
    _sanitize_law_content,
    _search_precedents_safe,
)
from src.chains.retriever import LegalDocumentRetriever  # noqa: E402


# ---------------------------------------------------------------------------
# 헬퍼: 판례 청크 / 법조문 청크 mock factory
# ---------------------------------------------------------------------------


def _precedent_chunk(case_no: str, case_name: str, content: str) -> dict:
    return {
        "content": content,
        "metadata": {
            "category": "판례",
            "article": case_no,
            "source": case_name,
            "chunk_id": f"prec_{case_no}",
        },
    }


def _law_chunk(source: str, article: str, content: str) -> dict:
    return {
        "content": content,
        "metadata": {
            "category": "법령_본문",
            "source": source,
            "article": article,
            "chunk_id": f"law_{source}_{article}",
        },
    }


# ---------------------------------------------------------------------------
# 1. _articles_from_precedent_docs
# ---------------------------------------------------------------------------


class TestArticlesFromPrecedentDocs:
    def test_basic_extraction(self) -> None:
        docs = [
            _precedent_chunk("2024다294033", "권리금 사건", "[판시사항] 임대차 보호 인정"),
            _precedent_chunk("2023다100100", "가맹사업 사건", "[판결요지] 영업지역 침해"),
        ]
        out = _articles_from_precedent_docs(docs, max_n=2)
        assert len(out) == 2
        assert out[0]["article_ref"] == "대법원 2024다294033"
        assert out[0]["kind"] == "precedent"
        assert "[판시사항]" in out[0]["content"]
        assert out[1]["article_ref"] == "대법원 2023다100100"

    def test_max_n_limit(self) -> None:
        docs = [_precedent_chunk(f"2024다{i:06d}", f"사건{i}", f"내용{i}") for i in range(5)]
        out = _articles_from_precedent_docs(docs, max_n=2)
        assert len(out) == 2

    def test_dedup_by_ref(self) -> None:
        # 같은 사건번호 반복 → 1개만
        docs = [
            _precedent_chunk("2024다294033", "사건A", "내용1"),
            _precedent_chunk("2024다294033", "사건A", "내용2"),
        ]
        out = _articles_from_precedent_docs(docs, max_n=3)
        assert len(out) == 1

    def test_fallback_to_case_name(self) -> None:
        # 사건번호 없으면 사건명으로 fallback (50자 truncate)
        docs = [
            {
                "content": "내용",
                "metadata": {"category": "판례", "source": "긴 사건명입니다 " * 10},
            }
        ]
        out = _articles_from_precedent_docs(docs, max_n=1)
        assert len(out) == 1
        assert len(out[0]["article_ref"]) <= 50
        assert out[0]["kind"] == "precedent"

    def test_content_truncate_400(self) -> None:
        long_content = "가" * 800
        docs = [_precedent_chunk("2024다1", "사건", long_content)]
        out = _articles_from_precedent_docs(docs, max_n=1)
        assert len(out[0]["content"]) <= 400

    def test_empty_skip(self) -> None:
        docs = [
            {"content": "", "metadata": {"category": "판례", "article": "2024다1"}},
        ]
        out = _articles_from_precedent_docs(docs, max_n=2)
        assert out == []


# ---------------------------------------------------------------------------
# 2. _articles_from_law_docs — 판례 청크 제외 검증
# ---------------------------------------------------------------------------


class TestArticlesFromLawDocs:
    def test_law_only_extraction(self) -> None:
        docs = [
            _law_chunk("가맹사업법", "제12조의4", "영업지역 보호 조항"),
            _law_chunk("가맹사업법", "제9조", "허위과장 정보 금지"),
        ]
        out = _articles_from_law_docs(docs, max_n=3)
        assert len(out) == 2
        assert all(a["kind"] == "article" for a in out)
        assert "가맹사업법 제12조의4" in out[0]["article_ref"]

    def test_precedent_chunks_excluded(self) -> None:
        # 법조문 + 판례 혼합 → 판례는 제외
        docs = [
            _law_chunk("가맹사업법", "제12조의4", "법조문"),
            _precedent_chunk("2024다1", "사건명", "판례 내용"),
            _law_chunk("가맹사업법", "제9조", "조문2"),
        ]
        out = _articles_from_law_docs(docs, max_n=5)
        assert len(out) == 2
        for a in out:
            assert a["kind"] == "article"
            assert "대법원" not in a["article_ref"]


# ---------------------------------------------------------------------------
# 3. LegalDocumentRetriever.search_precedents 시그니처
# ---------------------------------------------------------------------------


class TestSearchPrecedentsSignature:
    def test_method_exists(self) -> None:
        assert hasattr(LegalDocumentRetriever, "search_precedents")

    def test_is_async(self) -> None:
        method = LegalDocumentRetriever.search_precedents
        assert inspect.iscoroutinefunction(method)

    def test_default_top_k(self) -> None:
        sig = inspect.signature(LegalDocumentRetriever.search_precedents)
        assert sig.parameters["top_k"].default == 3


# ---------------------------------------------------------------------------
# 4. _search_precedents_safe — flag/예외 graceful
# ---------------------------------------------------------------------------


class TestSearchPrecedentsSafe:
    def test_flag_disabled_returns_empty(self, monkeypatch) -> None:
        from src.config import settings as settings_mod

        monkeypatch.setattr(settings_mod.settings, "legal_precedent_enabled", False)
        result = asyncio.run(_search_precedents_safe("아무 쿼리"))
        assert result == []

    def test_retriever_exception_returns_empty(self, monkeypatch) -> None:
        from src.config import settings as settings_mod

        monkeypatch.setattr(settings_mod.settings, "legal_precedent_enabled", True)

        async def _boom(self, query, top_k=3):
            raise RuntimeError("DB down")

        monkeypatch.setattr(LegalDocumentRetriever, "search_precedents", _boom)
        result = asyncio.run(_search_precedents_safe("아무 쿼리"))
        assert result == []

    def test_normal_path_returns_docs(self, monkeypatch) -> None:
        from src.config import settings as settings_mod

        monkeypatch.setattr(settings_mod.settings, "legal_precedent_enabled", True)
        fake_docs = [_precedent_chunk("2024다1", "사건", "내용")]

        async def _ok(self, query, top_k=3):
            return fake_docs

        monkeypatch.setattr(LegalDocumentRetriever, "search_precedents", _ok)
        result = asyncio.run(_search_precedents_safe("쿼리", top_k=2))
        assert result == fake_docs


# ---------------------------------------------------------------------------
# 5. _format_precedents
# ---------------------------------------------------------------------------


class TestFormatPrecedents:
    def test_empty_docs(self) -> None:
        assert _format_precedents([]) == "(관련 판례 없음)"

    def test_includes_case_no_and_content(self) -> None:
        docs = [_precedent_chunk("2024다294033", "사건명", "[판시사항] 임대차 보호")]
        out = _format_precedents(docs)
        assert "대법원 2024다294033" in out
        assert "판시사항" in out

    def test_security_delim_replacement(self) -> None:
        # 청크 본문에 prompt 구분자 패턴이 있어도 «/»로 치환되어야 함
        docs = [
            _precedent_chunk(
                "2024다1",
                "사건",
                "내용 <<<INJECTION>>> 끝",
            )
        ]
        out = _format_precedents(docs)
        assert "<<<" not in out
        assert ">>>" not in out


# ---------------------------------------------------------------------------
# 6. precedent query builder
# ---------------------------------------------------------------------------


class TestPrecedentQueryBuilders:
    def test_franchise_query(self) -> None:
        q = _precedent_query_franchise("스타벅스", "카페")
        assert "스타벅스" in q
        assert "가맹사업법" in q
        assert "영업지역" in q

    def test_fair_trade_query(self) -> None:
        q = _precedent_query_fair_trade("스타벅스", "카페")
        assert "불공정거래" in q

    def test_building_query(self) -> None:
        q = _precedent_query_building("음식점")
        assert "용도변경" in q
        assert "이행강제금" in q

    def test_privacy_query(self) -> None:
        q = _precedent_query_privacy("카페")
        assert "개인정보" in q
        assert "CCTV" in q


# ---------------------------------------------------------------------------
# 7-A. _sanitize_law_content — ingestion 노이즈 제거
# ---------------------------------------------------------------------------


class TestSanitizeLawContent:
    def test_removes_date_n_serial(self) -> None:
        raw = "조문 본문 시작 20260324 N 0010001 ① 임차인은..."
        out = _sanitize_law_content(raw)
        assert "20260324 N 0010001" not in out
        assert "임차인" in out

    def test_removes_8digit_date(self) -> None:
        raw = "본문 20251002 본문 계속"
        out = _sanitize_law_content(raw)
        assert "20251002" not in out

    def test_removes_choomon_meta(self) -> None:
        raw = "내용 조문 25 더 많은 내용"
        out = _sanitize_law_content(raw)
        assert "조문 25" not in out
        assert "내용" in out

    def test_removes_revision_inline(self) -> None:
        raw = "본문 <개정 2008. 1. 31.> 본문 계속"
        out = _sanitize_law_content(raw)
        assert "<개정" not in out
        assert "본문" in out

    def test_removes_bonjo_meta(self) -> None:
        raw = "[본조신설 2013.8.13] 제10조의4 본문"
        out = _sanitize_law_content(raw)
        assert "[본조신설" not in out
        assert "제10조의4" in out

    def test_collapses_multi_space(self) -> None:
        raw = "단어1     단어2"
        out = _sanitize_law_content(raw)
        assert "  " not in out


# ---------------------------------------------------------------------------
# 7. specialist E2E mock — articles 에 precedent kind 포함
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_specialist_franchise_includes_precedent_articles(monkeypatch) -> None:
    """franchise specialist mock LLM 결과 articles 에 precedent kind 포함 검증."""
    from src.agents.legal import specialists as specialists_mod
    from src.config import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "legal_precedent_enabled", True)

    fake_law_docs = [_law_chunk("가맹사업법", "제12조의4", "영업지역 보호")]
    fake_precedents = [_precedent_chunk("2024다294033", "영업지역침해사건", "[판시사항] 인접 출점 위반")]

    # retriever.search → 법령 청크
    async def _fake_search(self, query, top_k=10, source_filter=None):
        return fake_law_docs

    # retriever.search_precedents → 판례 청크
    async def _fake_precedents(self, query, top_k=3):
        return fake_precedents

    monkeypatch.setattr(LegalDocumentRetriever, "search", _fake_search)
    monkeypatch.setattr(LegalDocumentRetriever, "search_precedents", _fake_precedents)

    # territory 분석 stub
    async def _fake_territory(brand, district, business_type):
        return {}

    monkeypatch.setattr(specialists_mod, "_analyze_territory", _fake_territory)

    # LLM stub — structured output 흉내
    class _FakeLLM:
        def with_structured_output(self, *_a, **_kw):
            return self

        async def ainvoke(self, _msgs):
            from src.schemas.structured_output import LegalRiskItem

            return LegalRiskItem(
                type="franchise_law",
                level="caution",
                summary="평가 stub",
                recommendation="권고 stub",
            )

    monkeypatch.setattr(specialists_mod, "_get_specialist_llm", lambda: _FakeLLM())

    result = await specialists_mod.specialist_franchise_law(
        brand="스타벅스",
        business_type="카페",
        district="공덕동",
        ftc_data=None,
    )

    assert result["type"] == "franchise_law"
    articles = result.get("articles", [])
    # 판례 1개 이상 포함
    precedent_arts = [a for a in articles if a.get("kind") == "precedent"]
    assert len(precedent_arts) >= 1, f"판례가 articles 에 포함되지 않음: {articles}"
    assert "대법원" in precedent_arts[0]["article_ref"]
    # 법조문도 포함
    law_arts = [a for a in articles if a.get("kind") == "article"]
    assert len(law_arts) >= 1


@pytest.mark.asyncio
async def test_specialist_privacy_includes_precedent_articles(monkeypatch) -> None:
    """privacy specialist 도 동일 구조 검증."""
    from src.agents.legal import specialists as specialists_mod
    from src.config import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "legal_precedent_enabled", True)

    fake_law_docs = [_law_chunk("개인정보 보호법", "제25조", "CCTV 안내")]
    fake_precedents = [_precedent_chunk("2023다99999", "CCTV 사건", "[판시사항] 무단공개")]

    async def _fake_search(self, query, top_k=10, source_filter=None):
        return fake_law_docs

    async def _fake_precedents(self, query, top_k=3):
        return fake_precedents

    monkeypatch.setattr(LegalDocumentRetriever, "search", _fake_search)
    monkeypatch.setattr(LegalDocumentRetriever, "search_precedents", _fake_precedents)

    class _FakeLLM:
        def with_structured_output(self, *_a, **_kw):
            return self

        async def ainvoke(self, _msgs):
            from src.schemas.structured_output import LegalRiskItem

            return LegalRiskItem(
                type="privacy_law",
                level="caution",
                summary="stub",
                recommendation="stub",
            )

    monkeypatch.setattr(specialists_mod, "_get_specialist_llm", lambda: _FakeLLM())

    result = await specialists_mod.specialist_privacy_law(
        brand="브랜드",
        business_type="카페",
        ftc_data=None,
    )

    articles = result.get("articles", [])
    assert any(a.get("kind") == "precedent" for a in articles)


@pytest.mark.asyncio
async def test_specialist_disabled_flag_no_precedents(monkeypatch) -> None:
    """flag OFF → 판례 검색 skip → articles 에 precedent kind 없음."""
    from src.agents.legal import specialists as specialists_mod
    from src.config import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "legal_precedent_enabled", False)

    fake_law_docs = [_law_chunk("건축법", "제19조", "용도변경")]

    async def _fake_search(self, query, top_k=10, source_filter=None):
        return fake_law_docs

    # search_precedents 가 호출되면 안 되지만 안전망으로 구현
    called = {"n": 0}

    async def _fake_precedents(self, query, top_k=3):
        called["n"] += 1
        return []

    monkeypatch.setattr(LegalDocumentRetriever, "search", _fake_search)
    monkeypatch.setattr(LegalDocumentRetriever, "search_precedents", _fake_precedents)

    class _FakeLLM:
        def with_structured_output(self, *_a, **_kw):
            return self

        async def ainvoke(self, _msgs):
            from src.schemas.structured_output import LegalRiskItem

            return LegalRiskItem(
                type="building_law",
                level="caution",
                summary="stub",
                recommendation="stub",
            )

    monkeypatch.setattr(specialists_mod, "_get_specialist_llm", lambda: _FakeLLM())

    result = await specialists_mod.specialist_building_law(
        business_type="음식점",
        district="공덕동",
    )

    articles = result.get("articles", [])
    assert all(a.get("kind") != "precedent" for a in articles)
    # flag OFF 일 때 _search_precedents_safe 가 search_precedents 를 호출하지 않아야 함
    assert called["n"] == 0


# ---------------------------------------------------------------------------
# 8. _explain_articles_batch — B 단계 LLM 풀어쓰기
# ---------------------------------------------------------------------------


class _FakeMessage:
    """LLM 응답 mock — .content 속성만 노출."""

    def __init__(self, content: str) -> None:
        self.content = content


class _FakeExplainLLM:
    """_explain_articles_batch 전용 stub — JSON 배열 문자열 반환."""

    def __init__(self, payload: str) -> None:
        self._payload = payload

    async def ainvoke(self, _msgs):
        return _FakeMessage(self._payload)


class TestExplainArticlesBatch:
    def test_empty_articles_passthrough(self) -> None:
        out = asyncio.run(_explain_articles_batch([], "스타벅스", "카페", "공덕동", "가맹사업법"))
        assert out == []

    def test_flag_disabled_returns_original(self, monkeypatch) -> None:
        from src.config import settings as settings_mod

        monkeypatch.setattr(settings_mod.settings, "legal_article_explanation_enabled", False)
        articles = [{"article_ref": "가맹사업법 제12조의4", "content": "본문", "kind": "article"}]
        out = asyncio.run(_explain_articles_batch(articles, "스타벅스", "카페", "공덕동", "가맹사업법"))
        assert out == articles
        assert "explanation" not in out[0]

    def test_injects_explanation_from_llm(self, monkeypatch) -> None:
        from src.config import settings as settings_mod

        monkeypatch.setattr(settings_mod.settings, "legal_article_explanation_enabled", True)
        payload = (
            '[{"index": 1, "explanation": "이 사례 인접 출점 협의 의무"},'
            ' {"index": 2, "explanation": "허위 광고 금지"}]'
        )
        monkeypatch.setattr(
            specialists,
            "_get_specialist_llm",
            lambda: _FakeExplainLLM(payload),
        )
        articles = [
            {"article_ref": "가맹사업법 제12조의4", "content": "본문1", "kind": "article"},
            {"article_ref": "가맹사업법 제9조", "content": "본문2", "kind": "article"},
        ]
        out = asyncio.run(_explain_articles_batch(articles, "스타벅스", "카페", "공덕동", "가맹사업법"))
        assert out[0]["explanation"] == "이 사례 인접 출점 협의 의무"
        assert out[1]["explanation"] == "허위 광고 금지"
        # content 보존 (mutate 금지)
        assert out[0]["content"] == "본문1"

    def test_handles_code_block_wrapping(self, monkeypatch) -> None:
        from src.config import settings as settings_mod

        monkeypatch.setattr(settings_mod.settings, "legal_article_explanation_enabled", True)
        payload = '```json\n[{"index": 1, "explanation": "케이스 설명"}]\n```'
        monkeypatch.setattr(
            specialists,
            "_get_specialist_llm",
            lambda: _FakeExplainLLM(payload),
        )
        articles = [{"article_ref": "법 제1조", "content": "본문", "kind": "article"}]
        out = asyncio.run(_explain_articles_batch(articles, "B", "카페", "공덕동", "가맹사업법"))
        assert out[0]["explanation"] == "케이스 설명"

    def test_llm_failure_returns_original(self, monkeypatch) -> None:
        from src.config import settings as settings_mod

        monkeypatch.setattr(settings_mod.settings, "legal_article_explanation_enabled", True)

        class _BoomLLM:
            async def ainvoke(self, _msgs):
                raise RuntimeError("LLM down")

        monkeypatch.setattr(specialists, "_get_specialist_llm", lambda: _BoomLLM())
        articles = [{"article_ref": "법 제1조", "content": "본문", "kind": "article"}]
        out = asyncio.run(_explain_articles_batch(articles, "B", "카페", "공덕동", "가맹사업법"))
        assert out == articles
        assert "explanation" not in out[0]

    def test_invalid_json_returns_original(self, monkeypatch) -> None:
        from src.config import settings as settings_mod

        monkeypatch.setattr(settings_mod.settings, "legal_article_explanation_enabled", True)
        monkeypatch.setattr(
            specialists,
            "_get_specialist_llm",
            lambda: _FakeExplainLLM("이건 JSON 이 아닙니다"),
        )
        articles = [{"article_ref": "법 제1조", "content": "본문", "kind": "article"}]
        out = asyncio.run(_explain_articles_batch(articles, "B", "카페", "공덕동", "가맹사업법"))
        assert out == articles

    def test_partial_index_map(self, monkeypatch) -> None:
        """LLM 이 일부 index 만 반환해도 누락된 항목은 explanation 없이 반환."""
        from src.config import settings as settings_mod

        monkeypatch.setattr(settings_mod.settings, "legal_article_explanation_enabled", True)
        payload = '[{"index": 1, "explanation": "첫번째만"}]'
        monkeypatch.setattr(
            specialists,
            "_get_specialist_llm",
            lambda: _FakeExplainLLM(payload),
        )
        articles = [
            {"article_ref": "법 제1조", "content": "본문1", "kind": "article"},
            {"article_ref": "법 제2조", "content": "본문2", "kind": "article"},
        ]
        out = asyncio.run(_explain_articles_batch(articles, "B", "카페", "공덕동", "가맹사업법"))
        assert out[0]["explanation"] == "첫번째만"
        assert "explanation" not in out[1]
