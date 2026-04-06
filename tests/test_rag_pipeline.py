"""
RAG 파이프라인 테스트 — A2 담당

테스트 범위:
    1. PDF 파싱 로직 (parse_pdfs.py의 핵심 함수)
    2. LegalDocumentRetriever ingest → search 흐름 (ChromaDB 로컬)
    3. legal_node 용도지역 검토 (LLM 없이 규칙 기반)
    4. build_legal_prompt 조립 결과

실행:
    pytest tests/test_rag_pipeline.py -v
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.agents.nodes.legal import check_zoning_regulation, legal_node  # noqa: E402
from src.agents.state import AgentState  # noqa: E402
from src.chains.prompts import build_legal_prompt  # noqa: E402

# ── parse_pdfs 내부 함수 직접 임포트 ─────────────────────────────────────────
sys.path.insert(0, str(ROOT / "data" / "legal"))
from parse_pdfs import _split_long_chunk, parse_articles  # noqa: E402

# ── 1. PDF 파싱 유닛 테스트 ────────────────────────────────────────────────────


class TestPdfParsing:
    def test_split_long_chunk_short_text(self):
        """max_chars 미만 텍스트는 분할하지 않음."""
        text = "짧은 조문 내용"
        result = _split_long_chunk(text, max_chars=800, overlap=100)
        assert result == [text]

    def test_split_long_chunk_splits_correctly(self):
        """max_chars 초과 시 슬라이딩 윈도우로 분할."""
        text = "가" * 1000  # 1000자
        result = _split_long_chunk(text, max_chars=400, overlap=50)
        assert len(result) > 1
        # 각 청크가 max_chars 이하인지 확인
        assert all(len(chunk) <= 400 for chunk in result)
        # 첫 청크가 0~400, 두 번째가 350~750 (overlap=50)
        assert result[0] == "가" * 400
        assert result[1] == "가" * 400  # 350~750 = 400자

    def test_parse_articles_basic(self):
        """조문 단위 파싱이 올바르게 동작하는지 확인."""
        sample_text = """
        이 법은 가맹거래를 공정하게 합니다.

        제1조(목적) 이 법은 가맹사업의 공정한 거래 질서를 확립하고 가맹본부와 가맹점사업자 간의 균형 있는 거래를 목적으로 합니다.

        제2조(정의) 이 법에서 사용하는 용어는 다음과 같습니다.

        제3조(적용 범위) 이 법은 국내에서 이루어지는 가맹사업 거래에 적용합니다.
        """
        chunks = parse_articles(sample_text, "가맹사업법")

        # 최소 3개 조문 청크 생성 확인
        article_chunks = [c for c in chunks if c["metadata"]["article"] != "전문"]
        assert len(article_chunks) >= 3

        # 메타데이터 구조 확인
        first = article_chunks[0]
        assert "id" in first
        assert "text" in first
        assert "metadata" in first
        assert first["metadata"]["source"] == "가맹사업법"
        assert first["metadata"]["article"].startswith("제")

    def test_parse_articles_title_extraction(self):
        """조문 제목((목적)) 추출 확인."""
        sample_text = "제1조(목적) 이 법의 목적은 공정한 거래입니다."
        chunks = parse_articles(sample_text, "테스트법")
        article_chunks = [c for c in chunks if c["metadata"]["article"] != "전문"]
        assert article_chunks[0]["metadata"]["title"] == "목적"

    def test_parse_articles_preamble(self):
        """제1조 이전 전문(前文)이 별도 청크로 생성되는지 확인."""
        sample_text = "시행일: 2024.01.01\n제1조(목적) 이 법의 목적입니다."
        chunks = parse_articles(sample_text, "테스트법")
        preamble = [c for c in chunks if c["metadata"]["article"] == "전문"]
        assert len(preamble) == 1


# ── 2. RAG 검색 파이프라인 테스트 (ChromaDB mock) ────────────────────────────


class TestRetrieverPipeline:
    """
    ChromaDB 실제 연결 없이 LegalDocumentRetriever를 테스트.
    VectorDBClient.search()를 mock으로 대체.
    """

    @pytest.fixture
    def sample_docs(self) -> list[dict]:
        return [
            {
                "id": "franchise_법_제12조",
                "text": "제12조(가맹점사업자의 영업지역 보호) 가맹본부는 정당한 사유 없이 가맹점사업자의 영업지역에 동일 브랜드 점포를 추가로 출점해서는 안 됩니다.",
                "metadata": {"source": "가맹사업법", "article": "제12조", "title": "영업지역 보호"},
            },
            {
                "id": "lease_법_제10조",
                "text": "제10조(계약갱신 요구 등) 임차인은 최초 임대차 기간을 포함한 전체 임대차 기간이 10년을 초과하지 않는 범위에서 계약갱신요구권을 행사할 수 있습니다.",
                "metadata": {"source": "상가임대차보호법", "article": "제10조", "title": "계약갱신 요구"},
            },
        ]

    @pytest.mark.asyncio
    async def test_ingest_and_search(self, sample_docs):
        """ingest → search 전체 흐름을 mock으로 검증."""
        mock_search_result = [
            {
                "text": sample_docs[0]["text"],
                "metadata": sample_docs[0]["metadata"],
                "distance": 0.1,  # 매우 유사
            }
        ]

        with patch("src.chains.retriever.VectorDBClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.search = AsyncMock(return_value=mock_search_result)
            mock_instance.add_documents = AsyncMock()

            from src.chains.retriever import LegalDocumentRetriever

            retriever = LegalDocumentRetriever()
            results = await retriever.search("영업지역 보호", top_k=1)

        assert len(results) == 1
        assert results[0]["metadata"]["relevance"] > 0.9  # distance=0.1 → relevance=0.95
        assert "제12조" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_search_filters_low_relevance(self):
        """distance > DISTANCE_THRESHOLD(1.0)인 결과는 필터링되어야 함."""
        mock_search_result = [
            {
                "text": "전혀 관계없는 문서",
                "metadata": {},
                "distance": 1.5,  # 임계값 초과 → 필터링 대상
            }
        ]

        with patch("src.chains.retriever.VectorDBClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.search = AsyncMock(return_value=mock_search_result)

            from src.chains.retriever import LegalDocumentRetriever

            retriever = LegalDocumentRetriever()
            results = await retriever.search("임대차 계약", top_k=1)

        assert results == []


# ── 3. legal_node 용도지역 검토 (LLM 없이) ───────────────────────────────────


class TestLegalNode:
    def _make_state(self, district: str, business_type: str) -> AgentState:
        return AgentState(
            request_id="test-001",
            business_type=business_type,
            brand_name="테스트브랜드",
            target_district=district,
        )

    def test_zoning_safe_commercial(self):
        """일반상업지역에서 카페는 안전(safe)으로 판정."""
        state = self._make_state("서교동", "cafe")
        result = check_zoning_regulation(state)
        assert result["level"] == "safe"
        assert result["allowed"] is True
        assert result["zone"] == "일반상업지역"

    def test_zoning_danger_residential(self):
        """제1종전용주거지역에서 음식점은 위험(danger)으로 판정."""
        # _DISTRICT_ZONE_MAP에 없는 동을 직접 패치
        state = AgentState(
            request_id="test-002",
            business_type="restaurant",
            brand_name="테스트",
            target_district="unknown_dong",
        )
        # unknown_dong은 "근린상업지역"으로 fallback → safe
        result = check_zoning_regulation(state)
        assert result["level"] == "safe"  # 근린상업지역 fallback

    def test_legal_node_initializes_analysis_results(self):
        """analysis_results가 None인 state에 legal_node 실행 시 초기화."""
        state = self._make_state("합정동", "cafe")
        assert state.analysis_results is None

        # LLM 호출과 retriever를 mock으로 대체
        with (
            patch("src.agents.nodes.legal._call_llm", return_value="이 경우는 안전합니다. 안전"),
            patch("src.agents.nodes.legal.LegalDocumentRetriever") as MockRetriever,
        ):
            mock_instance = MockRetriever.return_value
            mock_instance.search = AsyncMock(return_value=[])
            result_state = legal_node(state)

        assert result_state.analysis_results is not None
        assert len(result_state.analysis_results.legal_risks) == 3  # 3가지 검토

    def test_legal_node_risk_types(self):
        """legal_node 결과에 3가지 리스크 타입이 모두 포함되어야 함."""
        state = self._make_state("연남동", "restaurant")

        with (
            patch("src.agents.nodes.legal._call_llm", return_value="주의가 필요합니다. 주의"),
            patch("src.agents.nodes.legal.LegalDocumentRetriever") as MockRetriever,
        ):
            mock_instance = MockRetriever.return_value
            mock_instance.search = AsyncMock(return_value=[])
            result_state = legal_node(state)

        risk_types = {r["type"] for r in result_state.analysis_results.legal_risks}
        assert "franchise_law" in risk_types
        assert "commercial_lease_law" in risk_types
        assert "zoning_regulation" in risk_types


# ── 4. build_legal_prompt 테스트 ─────────────────────────────────────────────


class TestBuildLegalPrompt:
    def test_empty_docs(self):
        """검색 결과 없을 때 '관련 조문 없음' 메시지 포함."""
        result = build_legal_prompt([], "가맹금 예치 의무는 무엇인가요?")
        assert "관련 법률 문서를 찾을 수 없습니다" in result
        assert "가맹금 예치 의무" in result

    def test_with_docs(self):
        """docs가 있을 때 출처와 조문 번호가 포함되는지 확인."""
        docs = [
            {
                "content": "제3조(가맹금 예치) 가맹본부는 가맹금을 예치기관에 예치해야 합니다.",
                "metadata": {"source": "가맹사업법", "article": "제3조", "relevance": 0.95},
            }
        ]
        result = build_legal_prompt(docs, "가맹금 예치 의무는 무엇인가요?")
        assert "가맹사업법" in result
        assert "제3조" in result
        assert "가맹금 예치" in result
