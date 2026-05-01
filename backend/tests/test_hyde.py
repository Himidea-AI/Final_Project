"""HyDE 하이브리드 쿼리 확장 테스트"""
import asyncio
import os
import sys

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _set_hyde_env(monkeypatch):
    """테스트 전 HYDE_ENABLED 초기화"""
    monkeypatch.setenv("HYDE_ENABLED", "false")


class TestHydeDictOnly:
    """HYDE_ENABLED=false일 때 사전 기반만 동작"""

    def test_dict_expand_no_llm(self):
        """사전 매칭이 되면 LLM 호출 없이 확장만 반환"""
        from src.chains.retriever import LegalDocumentRetriever

        result = asyncio.get_event_loop().run_until_complete(
            LegalDocumentRetriever._expand_query_hybrid("영업지역 침해 가맹사업법")
        )
        assert "제12조의4" in result
        assert "영업지역" in result

    def test_no_match_returns_original(self):
        """사전에 없는 쿼리는 원본 그대로 반환"""
        from src.chains.retriever import LegalDocumentRetriever

        query = "xyz 완전히 관련없는 쿼리 abc"
        result = asyncio.get_event_loop().run_until_complete(
            LegalDocumentRetriever._expand_query_hybrid(query)
        )
        assert result == query


class TestHydeOutputFormat:
    """HyDE 출력 형식 검증"""

    def test_hyde_expand_contains_legal_terms(self):
        """사전 확장 결과에 법률 키워드가 포함"""
        from src.chains.retriever import LegalDocumentRetriever

        result = asyncio.get_event_loop().run_until_complete(
            LegalDocumentRetriever._expand_query_hybrid("가맹본부가 내 매장 근처에 같은 브랜드 매장을 열었어요")
        )
        # 사전 매핑: "매장 근처" -> "영업지역 침해..."
        assert "영업지역" in result or "제12조의4" in result


class TestHydeFallback:
    """LLM 실패 시 사전 결과로 폴백"""

    def test_fallback_on_no_api_key(self, monkeypatch):
        """API 키 없으면 사전 결과만 반환 (에러 없음)"""
        monkeypatch.setenv("HYDE_ENABLED", "true")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        monkeypatch.setenv("OPENAI_API_KEY", "")

        # settings 재로드
        import importlib
        from src.config import settings as settings_mod
        importlib.reload(settings_mod)

        from src.chains.retriever import LegalDocumentRetriever

        result = asyncio.get_event_loop().run_until_complete(
            LegalDocumentRetriever._expand_query_hybrid("영업지역 보장 가맹사업법")
        )
        # 에러 없이 사전 결과 반환
        assert "영업지역" in result
        assert len(result) > 0
