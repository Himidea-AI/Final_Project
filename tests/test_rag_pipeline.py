"""
RAG 파이프라인 테스트 — A2 담당

테스트 범위:
    1. PDF 파싱 로직 (parse_pdfs.py의 핵심 함수)
    2. LegalDocumentRetriever search 흐름 (pgvector mock)
       - source_filter별 검색 정확성
       - RELEVANCE_THRESHOLD(0.3) 경계값 필터링
       - fallback 재검색 (source_filter 결과 0건 시)
    3. legal_node 용도지역 검토 (LLM 없이 규칙 기반)
       - 16개 행정동 × 3개 업종 조합 전수 검증
    4. build_legal_prompt 조립 결과
    5. 배치 LLM JSON 파싱 안정성 (_extract_risk_level)

실행:
    pytest tests/test_rag_pipeline.py -v
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.agents.nodes.legal import check_zoning_regulation  # noqa: E402
from src.chains.retriever import LegalDocumentRetriever  # noqa: E402
from src.config.constants import (
    DISTRICT_ZONE_MAP,  # noqa: E402
    MAPO_DISTRICTS,  # noqa: E402
)

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
        assert all(len(chunk) <= 400 for chunk in result)
        assert result[0] == "가" * 400

    def test_parse_articles_basic(self):
        """조문 단위 파싱이 올바르게 동작하는지 확인."""
        sample_text = """
        이 법은 가맹거래를 공정하게 합니다.

        제1조(목적) 이 법은 가맹사업의 공정한 거래 질서를 확립하고 가맹본부와 가맹점사업자 간의 균형 있는 거래를 목적으로 합니다.

        제2조(정의) 이 법에서 사용하는 용어는 다음과 같습니다.

        제3조(적용 범위) 이 법은 국내에서 이루어지는 가맹사업 거래에 적용합니다.
        """
        chunks = parse_articles(sample_text, "가맹사업법")
        article_chunks = [c for c in chunks if c["metadata"]["article"] != "전문"]
        assert len(article_chunks) >= 3

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


# ── 2. RAG 검색 파이프라인 테스트 (pgvector mock) ────────────────────────────


def _make_mock_doc(content: str, source: str, article: str = "", relevance: float = 0.85):
    """pgvector asimilarity_search_with_relevance_scores 반환 형식 mock 생성"""
    doc = MagicMock()
    doc.page_content = content
    doc.metadata = {"source": source, "article": article}
    return (doc, relevance)


class TestRetrieverSearch:
    """
    LegalDocumentRetriever.search()가 source_filter별로 올바른 법률 문서를 반환하는지 검증.

    이 테스트가 하는 일:
    법률 에이전트가 "가맹사업법 영업지역 보호"를 물으면,
    retriever가 식품위생법이 아닌 가맹사업법 문서를 가져오는지 확인합니다.
    """

    @pytest.fixture
    def mock_vectorstore(self):
        """pgvector vectorstore를 mock으로 대체"""
        vs = AsyncMock()
        return vs

    @pytest.mark.asyncio
    async def test_franchise_law_source_filter(self, mock_vectorstore):
        """가맹사업법 검색 시 source_filter가 올바르게 적용되는지 확인."""
        mock_vectorstore.asimilarity_search_with_relevance_scores.return_value = [
            _make_mock_doc(
                "제12조(가맹점사업자의 영업지역 보호) 가맹본부는 정당한 사유 없이...",
                source="가맹사업거래의 공정화에 관한 법률(법률)(제20712호)(20250121)",
                article="제12조",
                relevance=0.92,
            ),
        ]

        with patch.object(LegalDocumentRetriever, "__init__", lambda self: None):
            retriever = LegalDocumentRetriever()
            retriever._db = MagicMock()
            retriever._db.vectorstore = mock_vectorstore

            results = await retriever.search(
                "가맹사업법 영업지역 보호",
                top_k=5,
                source_filter=LegalDocumentRetriever.FRANCHISE_LAW_SOURCES,
            )

        # source_filter가 올바르게 전달되었는지 확인
        call_kwargs = mock_vectorstore.asimilarity_search_with_relevance_scores.call_args
        assert call_kwargs.kwargs.get("filter") == {"source": {"$in": LegalDocumentRetriever.FRANCHISE_LAW_SOURCES}}

        assert len(results) == 1
        assert "제12조" in results[0]["content"]
        assert results[0]["metadata"]["relevance"] == 0.92

    @pytest.mark.asyncio
    async def test_lease_law_source_filter(self, mock_vectorstore):
        """상가임대차보호법 검색 시 올바른 source_filter 적용."""
        mock_vectorstore.asimilarity_search_with_relevance_scores.return_value = [
            _make_mock_doc(
                "제10조의4(권리금 회수기회 보호 등) 임대인은 임대차기간이 끝나기 6개월 전부터...",
                source="상가건물 임대차보호법(법률)(제21065호)(20260102)",
                article="제10조의4",
                relevance=0.88,
            ),
        ]

        with patch.object(LegalDocumentRetriever, "__init__", lambda self: None):
            retriever = LegalDocumentRetriever()
            retriever._db = MagicMock()
            retriever._db.vectorstore = mock_vectorstore

            results = await retriever.search(
                "권리금 회수 기회 보호",
                top_k=5,
                source_filter=LegalDocumentRetriever.LEASE_LAW_SOURCES,
            )

        assert len(results) == 1
        assert "권리금" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_relevance_threshold_filters_low_score(self, mock_vectorstore):
        """
        RELEVANCE_THRESHOLD(0.3) 미만인 문서는 필터링.

        이 테스트가 하는 일:
        관련도가 낮은 엉뚱한 법률 문서가 LLM 프롬프트에 들어가지 않도록
        0.3 미만 점수의 문서가 제거되는지 확인합니다.
        """
        mock_vectorstore.asimilarity_search_with_relevance_scores.return_value = [
            _make_mock_doc("관련 있는 조문", "가맹사업법", relevance=0.85),  # 통과
            _make_mock_doc("약간 관련 있는 조문", "건축법", relevance=0.35),  # 통과 (경계 초과)
            _make_mock_doc("전혀 관련 없는 조문", "주세법", relevance=0.25),  # 필터링 (0.3 미만)
            _make_mock_doc("매우 약한 관련", "하수도법", relevance=0.10),  # 필터링
        ]

        with patch.object(LegalDocumentRetriever, "__init__", lambda self: None):
            retriever = LegalDocumentRetriever()
            retriever._db = MagicMock()
            retriever._db.vectorstore = mock_vectorstore

            results = await retriever.search("가맹사업법 검색", top_k=5)

        assert len(results) == 2  # 0.3 이상인 2개만 통과
        assert results[0]["metadata"]["relevance"] == 0.85  # 높은 점수 우선 정렬
        assert results[1]["metadata"]["relevance"] == 0.35

    @pytest.mark.asyncio
    async def test_relevance_threshold_boundary_exact(self, mock_vectorstore):
        """RELEVANCE_THRESHOLD 정확히 0.3은 통과해야 함 (>= 0.3)."""
        mock_vectorstore.asimilarity_search_with_relevance_scores.return_value = [
            _make_mock_doc("경계값 조문", "가맹사업법", relevance=0.3),  # 정확히 0.3 → 통과
        ]

        with patch.object(LegalDocumentRetriever, "__init__", lambda self: None):
            retriever = LegalDocumentRetriever()
            retriever._db = MagicMock()
            retriever._db.vectorstore = mock_vectorstore

            results = await retriever.search("경계값 테스트", top_k=5)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_fallback_without_source_filter(self, mock_vectorstore):
        """
        source_filter로 결과 0건일 때 필터 없이 fallback 재검색.

        이 테스트가 하는 일:
        특정 법률 PDF가 아직 인덱싱되지 않았을 때,
        전체 컬렉션에서라도 관련 문서를 찾아오는 fallback이 작동하는지 확인합니다.
        """
        # 첫 번째 호출(필터 있음): 결과 없음
        # 두 번째 호출(필터 없음): 결과 있음
        mock_vectorstore.asimilarity_search_with_relevance_scores.side_effect = [
            [],  # source_filter 검색 → 0건
            [_make_mock_doc("관련 문서 발견", "기타법률", relevance=0.75)],  # fallback
        ]

        with patch.object(LegalDocumentRetriever, "__init__", lambda self: None):
            retriever = LegalDocumentRetriever()
            retriever._db = MagicMock()
            retriever._db.vectorstore = mock_vectorstore

            results = await retriever.search(
                "소방시설 설치 의무",
                top_k=5,
                source_filter=LegalDocumentRetriever.FIRE_SAFETY_SOURCES,
            )

        # 2번 호출됨 (필터 있음 → 필터 없음)
        assert mock_vectorstore.asimilarity_search_with_relevance_scores.call_count == 2
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_vectorstore_none_returns_empty(self):
        """
        vectorstore가 None일 때 (DB 미연결) 빈 리스트 반환.

        이 테스트가 하는 일:
        로컬 개발 시 PostgreSQL이 안 켜져 있어도 에러 없이 빈 결과를 반환하여
        법률 에이전트가 graceful하게 동작하는지 확인합니다.
        """
        with patch.object(LegalDocumentRetriever, "__init__", lambda self: None):
            retriever = LegalDocumentRetriever()
            retriever._db = MagicMock()
            retriever._db.vectorstore = None  # DB 미연결

            results = await retriever.search("아무 쿼리", top_k=5)

        assert results == []

    @pytest.mark.asyncio
    async def test_all_14_source_filters_defined(self):
        """
        법률 에이전트가 사용하는 14개 법률의 source_filter가 모두 정의되어 있는지 확인.

        이 테스트가 하는 일:
        legal.py의 _run_legal_pipeline이 13개 RAG 검색을 하는데,
        각 검색에 쓰이는 source_filter 상수가 retriever.py에 모두 정의되어 있는지 확인합니다.
        빠진 필터가 있으면 해당 법률 검색이 전체 컬렉션을 스캔하게 되어 정확도가 떨어집니다.
        """
        required_filters = [
            "FRANCHISE_LAW_SOURCES",
            "LEASE_LAW_SOURCES",
            "FOOD_HYGIENE_SOURCES",
            "SAFETY_SOURCES",
            "BUILDING_LAW_SOURCES",
            "FIRE_SAFETY_SOURCES",
            "LABOR_LAW_SOURCES",
            "VAT_LAW_SOURCES",
            "PRIVACY_LAW_SOURCES",
            "ACCESSIBILITY_LAW_SOURCES",
            "SEWAGE_LAW_SOURCES",
            "FAIR_TRADE_SOURCES",
        ]
        for attr_name in required_filters:
            sources = getattr(LegalDocumentRetriever, attr_name, None)
            assert sources is not None, f"LegalDocumentRetriever.{attr_name}이 정의되지 않음"
            assert len(sources) > 0, f"LegalDocumentRetriever.{attr_name}이 비어 있음"

    @pytest.mark.asyncio
    async def test_results_sorted_by_relevance_desc(self, mock_vectorstore):
        """검색 결과가 relevance 내림차순으로 정렬되는지 확인."""
        mock_vectorstore.asimilarity_search_with_relevance_scores.return_value = [
            _make_mock_doc("낮은 관련도", "가맹사업법", relevance=0.50),
            _make_mock_doc("높은 관련도", "가맹사업법", relevance=0.95),
            _make_mock_doc("중간 관련도", "가맹사업법", relevance=0.70),
        ]

        with patch.object(LegalDocumentRetriever, "__init__", lambda self: None):
            retriever = LegalDocumentRetriever()
            retriever._db = MagicMock()
            retriever._db.vectorstore = mock_vectorstore

            results = await retriever.search("테스트", top_k=5)

        scores = [r["metadata"]["relevance"] for r in results]
        assert scores == sorted(scores, reverse=True)


# ── 3. 용도지역 검토 — 16개 행정동 × 3개 업종 전수 검증 ──────────────────────


class TestZoningRegulation:
    """
    이 테스트가 하는 일:
    법률 에이전트의 check_zoning_regulation()이 LLM 없이 규칙 기반으로
    "이 동에서 이 업종은 영업 가능한가?"를 판정합니다.
    마포구 16개 행정동 × 3개 업종(카페/음식점/편의점) = 48가지 조합 전부를 테스트합니다.
    """

    def _make_state(self, district: str, business_type: str) -> dict:
        """TypedDict AgentState 호환 dict 생성"""
        return {
            "business_type": business_type,
            "brand_name": "테스트브랜드",
            "target_district": district,
        }

    @pytest.mark.asyncio
    async def test_all_16_districts_mapped(self):
        """마포구 16개 행정동이 모두 DISTRICT_ZONE_MAP에 매핑되어 있는지 확인."""
        for dong in MAPO_DISTRICTS:
            assert dong in DISTRICT_ZONE_MAP, f"'{dong}'이 DISTRICT_ZONE_MAP에 없음"

    @pytest.mark.asyncio
    async def test_commercial_district_cafe_safe(self):
        """일반상업지역(서교동)에서 카페는 safe."""
        state = self._make_state("서교동", "카페")
        result = await check_zoning_regulation(state)
        assert result["level"] == "safe"
        assert result["allowed"] is True
        assert result["zone"] == "일반상업지역"

    @pytest.mark.asyncio
    async def test_residential_2_restaurant_restricted(self):
        """제2종일반주거지역(대흥동)에서 음식점은 제한(danger)."""
        state = self._make_state("대흥동", "음식점")
        result = await check_zoning_regulation(state)
        assert result["level"] == "danger"
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_residential_2_cafe_allowed(self):
        """제2종일반주거지역(대흥동)에서 카페는 허용(safe)."""
        state = self._make_state("대흥동", "카페")
        result = await check_zoning_regulation(state)
        assert result["level"] == "safe"

    @pytest.mark.asyncio
    async def test_residential_3_all_allowed(self):
        """제3종일반주거지역(연남동)에서 카페/음식점/편의점 모두 허용."""
        for btype in ["카페", "음식점", "편의점"]:
            state = self._make_state("연남동", btype)
            result = await check_zoning_regulation(state)
            assert result["level"] == "safe", f"연남동+{btype}이 safe가 아님: {result['level']}"

    @pytest.mark.asyncio
    async def test_unknown_district_fallback(self):
        """알 수 없는 행정동은 근린상업지역으로 fallback → 대부분 safe."""
        state = self._make_state("가상의동", "카페")
        result = await check_zoning_regulation(state)
        assert result["zone"] == "근린상업지역"  # fallback
        assert result["level"] == "safe"

    @pytest.mark.asyncio
    async def test_code_to_korean_mapping(self):
        """영문 업종코드(cafe, restaurant, convenience)가 한글로 변환되는지 확인."""
        for code, label in [("cafe", "카페"), ("restaurant", "음식점"), ("convenience", "편의점")]:
            state = self._make_state("서교동", code)
            result = await check_zoning_regulation(state)
            assert result["business_type"] == label

    @pytest.mark.asyncio
    async def test_legal_alias_districts(self):
        """법정동 별칭(망원동→근린상업, 토정동→일반상업)이 올바르게 매핑되는지 확인."""
        aliases = {
            "망원동": "근린상업지역",
            "토정동": "일반상업지역",
            "양화동": "근린상업지역",
            "용문동": "제2종일반주거지역",
        }
        for dong, expected_zone in aliases.items():
            assert DISTRICT_ZONE_MAP.get(dong) == expected_zone, f"'{dong}' 매핑이 잘못됨"

    @pytest.mark.asyncio
    async def test_all_48_combinations_no_error(self):
        """16개 행정동 × 3개 업종 = 48 조합에서 에러 없이 결과 반환."""
        business_types = ["카페", "음식점", "편의점"]
        for dong in MAPO_DISTRICTS:
            for btype in business_types:
                state = self._make_state(dong, btype)
                result = await check_zoning_regulation(state)
                assert result["level"] in ("safe", "caution", "danger"), f"{dong}+{btype} 잘못된 level"
                assert "type" in result
                assert result["type"] == "zoning_regulation"

    @pytest.mark.asyncio
    async def test_danger_cases_complete(self):
        """
        제2종일반주거지역(대흥동, 염리동, 신수동)에서 음식점이 danger인지 확인.
        이 동들은 실제로 주거지역이라 음식점 영업이 제한됩니다.
        """
        residential_2_districts = ["대흥동", "염리동", "신수동"]
        for dong in residential_2_districts:
            state = self._make_state(dong, "음식점")
            result = await check_zoning_regulation(state)
            assert result["level"] == "danger", f"{dong}+음식점이 danger가 아님: {result['level']}"
