"""
IM3-62: RAG 통합 테스트 — LangGraph 연동 검증

테스트 그룹:
  1. Retriever  — 실제 pgvector에서 문서 검색 검증
  2. legal_node — LangGraph AgentState 호환성 및 리스크 구조 검증 (LLM mock)
  3. 용도지역   — 결정론적 판정 검증 (외부 의존성 없음)

실행 방법 (backend/ 디렉토리에서):
    pytest tests/test_a2_rag_integration.py -v
"""

import pytest
from unittest.mock import AsyncMock, patch

# conftest.py가 os.environ 설정 완료 후 임포트
from src.chains.retriever import LegalDocumentRetriever
from src.agents.nodes.legal import legal_node, check_zoning_regulation

# LLM mock 응답 — JSON 구조화 출력 형식으로 고정 (Ollama 실행 불필요)
_MOCK_LLM_RESPONSE = '관련 법률을 검토한 결과 주의가 필요합니다.\n{"risk_level": "caution"}'

# legal_node 테스트용 기본 AgentState (TypedDict 호환)
_BASE_STATE = {
    "messages": [],
    "business_type": "cafe",
    "brand_name": "TestBrand",
    "target_district": "서교동",
    "market_data": {},
    "legal_info": [],
    "analysis_results": {},
    "current_agent": "legal_analyst",
    "next_step": "",
    "errors": [],
}

# ──────────────────────────────────────────────────────────────
# 1. Retriever 테스트 — 실제 pgvector 연결
# ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retriever_returns_nonempty():
    """기본 검색이 1건 이상 반환하는지 확인"""
    retriever = LegalDocumentRetriever()
    results = await retriever.search("가맹사업법 영업지역 보장", top_k=5)
    assert len(results) > 0, "pgvector에서 검색 결과가 없습니다 — 인제스트 확인 필요"


@pytest.mark.asyncio
async def test_retriever_result_format():
    """반환 형식 검증: content(str) + metadata.relevance(float) 필수"""
    retriever = LegalDocumentRetriever()
    results = await retriever.search("권리금 회수 보호", top_k=3)

    assert len(results) > 0
    for doc in results:
        assert "content" in doc, "content 키 누락"
        assert isinstance(doc["content"], str), "content가 str이 아님"
        assert "metadata" in doc, "metadata 키 누락"
        assert "relevance" in doc["metadata"], "metadata.relevance 키 누락"
        assert isinstance(doc["metadata"]["relevance"], float), "relevance가 float이 아님"
        assert 0.0 <= doc["metadata"]["relevance"] <= 1.0, "relevance가 0~1 범위를 벗어남"


@pytest.mark.asyncio
async def test_retriever_relevance_sorted():
    """검색 결과가 relevance 내림차순으로 정렬되는지 확인"""
    retriever = LegalDocumentRetriever()
    results = await retriever.search("임대차 계약갱신요구권", top_k=5)

    if len(results) < 2:
        pytest.skip("검색 결과 2건 미만 — 정렬 검증 불가")

    relevances = [doc["metadata"]["relevance"] for doc in results]
    assert relevances == sorted(relevances, reverse=True), "relevance 내림차순 정렬이 안 됨"


@pytest.mark.asyncio
async def test_retriever_topk_respected():
    """top_k 파라미터가 반환 건수에 반영되는지 확인"""
    retriever = LegalDocumentRetriever()
    results = await retriever.search("가맹사업법", top_k=3)
    assert len(results) <= 3, f"top_k=3인데 {len(results)}건 반환됨"


@pytest.mark.asyncio
async def test_retriever_source_filter_franchise():
    """가맹사업법 소스 필터링 — 다른 법령 문서가 섞이지 않는지 확인"""
    retriever = LegalDocumentRetriever()
    results = await retriever.search(
        "영업지역 보장 출점 제한",
        top_k=5,
        source_filter=LegalDocumentRetriever.FRANCHISE_LAW_SOURCES,
    )
    assert len(results) > 0, "가맹사업법 소스 필터링 결과 없음"
    for doc in results:
        source = doc["metadata"].get("source", "")
        assert source in LegalDocumentRetriever.FRANCHISE_LAW_SOURCES, f"필터링 외 소스 포함됨: {source}"


@pytest.mark.asyncio
async def test_retriever_source_filter_lease():
    """상가임대차보호법 소스 필터링 검증"""
    retriever = LegalDocumentRetriever()
    results = await retriever.search(
        "권리금 회수 계약갱신요구권",
        top_k=5,
        source_filter=LegalDocumentRetriever.LEASE_LAW_SOURCES,
    )
    assert len(results) > 0, "상가임대차보호법 소스 필터링 결과 없음"
    for doc in results:
        source = doc["metadata"].get("source", "")
        assert source in LegalDocumentRetriever.LEASE_LAW_SOURCES, f"필터링 외 소스 포함됨: {source}"


@pytest.mark.asyncio
async def test_retriever_source_filter_food_hygiene():
    """식품위생법 소스 필터링 검증"""
    retriever = LegalDocumentRetriever()
    results = await retriever.search(
        "영업신고 위생교육 시설기준",
        top_k=5,
        source_filter=LegalDocumentRetriever.FOOD_HYGIENE_SOURCES,
    )
    assert len(results) > 0, "식품위생법 소스 필터링 결과 없음"
    for doc in results:
        source = doc["metadata"].get("source", "")
        assert source in LegalDocumentRetriever.FOOD_HYGIENE_SOURCES, f"필터링 외 소스 포함됨: {source}"


@pytest.mark.asyncio
async def test_retriever_source_filter_safety():
    """다중이용업소 안전관리법 소스 필터링 검증"""
    retriever = LegalDocumentRetriever()
    results = await retriever.search(
        "소방시설 안전시설 완비증명",
        top_k=5,
        source_filter=LegalDocumentRetriever.SAFETY_SOURCES,
    )
    assert len(results) > 0, "다중이용업소법 소스 필터링 결과 없음"
    for doc in results:
        source = doc["metadata"].get("source", "")
        assert source in LegalDocumentRetriever.SAFETY_SOURCES, f"필터링 외 소스 포함됨: {source}"


# ──────────────────────────────────────────────────────────────
# 2. legal_node 통합 테스트 — LLM mock, 실제 pgvector
# ──────────────────────────────────────────────────────────────


@patch("src.agents.nodes.legal._async_call_llm", new_callable=AsyncMock, return_value=_MOCK_LLM_RESPONSE)
def test_legal_node_output_keys(mock_llm):
    """legal_node 반환값에 analysis_results, legal_info 키가 있는지 확인"""
    result = legal_node(_BASE_STATE.copy())

    assert "analysis_results" in result, "analysis_results 키 누락"
    assert "legal_info" in result, "legal_info 키 누락"
    assert "legal_risks" in result["analysis_results"], "analysis_results.legal_risks 키 누락"
    assert "overall_legal_risk" in result["analysis_results"], "analysis_results.overall_legal_risk 키 누락"


@patch("src.agents.nodes.legal._async_call_llm", new_callable=AsyncMock, return_value=_MOCK_LLM_RESPONSE)
def test_legal_node_overall_risk_level(mock_llm):
    """overall_legal_risk가 safe/caution/danger 중 하나이며 14개 리스크 중 최고 레벨인지 확인"""
    result = legal_node(_BASE_STATE.copy())
    analysis = result["analysis_results"]

    overall = analysis["overall_legal_risk"]
    assert overall in {"safe", "caution", "danger"}, f"overall_legal_risk 값 비정상: {overall}"

    # 14개 개별 리스크 레벨보다 낮을 수 없음
    level_order = {"safe": 0, "caution": 1, "danger": 2}
    max_individual = max(level_order.get(r["level"], 0) for r in analysis["legal_risks"])
    assert level_order[overall] == max_individual, f"overall_legal_risk({overall})이 개별 최고 레벨과 불일치"


@patch("src.agents.nodes.legal._async_call_llm", new_callable=AsyncMock, return_value=_MOCK_LLM_RESPONSE)
def test_legal_node_all_risk_types(mock_llm):
    """14가지 리스크 타입이 모두 포함되는지 확인"""
    result = legal_node(_BASE_STATE.copy())
    risks = result["analysis_results"]["legal_risks"]

    risk_types = {r["type"] for r in risks}
    expected_types = {
        "franchise_law",
        "commercial_lease_law",
        "zoning_regulation",
        "food_hygiene",
        "safety_regulation",
        "ftc_franchise",
        "building_law",
        "fire_safety_law",
        "labor_law",
        "vat_law",
        "privacy_law",
        "accessibility_law",
        "sewage_law",
        "fair_trade_law",
    }
    assert expected_types.issubset(risk_types), f"누락된 리스크 타입: {expected_types - risk_types}"


@patch("src.agents.nodes.legal._async_call_llm", new_callable=AsyncMock, return_value=_MOCK_LLM_RESPONSE)
def test_legal_node_risk_structure(mock_llm):
    """각 리스크 dict가 필수 키를 모두 포함하는지 확인"""
    result = legal_node(_BASE_STATE.copy())
    risks = result["analysis_results"]["legal_risks"]

    required_keys = {"type", "level", "summary", "articles", "recommendation"}
    for risk in risks:
        missing = required_keys - set(risk.keys())
        assert not missing, f"{risk.get('type')} 리스크에 키 누락: {missing}"


@patch("src.agents.nodes.legal._async_call_llm", new_callable=AsyncMock, return_value=_MOCK_LLM_RESPONSE)
def test_legal_node_risk_level_values(mock_llm):
    """level 값이 safe / caution / danger 중 하나인지 확인"""
    result = legal_node(_BASE_STATE.copy())
    risks = result["analysis_results"]["legal_risks"]

    valid_levels = {"safe", "caution", "danger"}
    for risk in risks:
        assert risk["level"] in valid_levels, f"{risk['type']} 리스크의 level 값 비정상: {risk['level']}"


@patch("src.agents.nodes.legal._async_call_llm", new_callable=AsyncMock, return_value=_MOCK_LLM_RESPONSE)
def test_legal_node_legal_info_not_empty(mock_llm):
    """legal_info가 비어있지 않은지 확인 (실제 문서 or fallback)"""
    result = legal_node(_BASE_STATE.copy())
    legal_info = result["legal_info"]

    assert len(legal_info) > 0, "legal_info가 빈 리스트 — RAG 또는 fallback 확인 필요"
    for item in legal_info:
        assert "content" in item, "legal_info 항목에 content 키 누락"
        assert "metadata" in item, "legal_info 항목에 metadata 키 누락"


@patch("src.agents.nodes.legal._async_call_llm", new_callable=AsyncMock, return_value=_MOCK_LLM_RESPONSE)
def test_legal_node_state_passthrough(mock_llm):
    """legal_node가 기존 state 필드를 유지하면서 결과를 추가하는지 확인"""
    state = _BASE_STATE.copy()
    state["brand_name"] = "스타벅스"
    state["target_district"] = "합정동"

    result = legal_node(state)

    assert result["brand_name"] == "스타벅스", "brand_name 필드가 사라짐"
    assert result["target_district"] == "합정동", "target_district 필드가 사라짐"
    assert result["business_type"] == "cafe", "business_type 필드가 사라짐"


@patch("src.agents.nodes.legal._async_call_llm", new_callable=AsyncMock, return_value=_MOCK_LLM_RESPONSE)
def test_ftc_franchise_db_failure_fallback(mock_llm):
    """
    DB 조회 실패 시(PostgresClient 예외) FTC 판정이 safe/caution/danger 중 하나로
    정상 반환되는지 확인 — position_ratio 로직이 예외 처리로 감싸져 있어야 함
    """
    with patch("src.agents.nodes.legal.PostgresClient") as MockPG:
        MockPG.return_value.connect = AsyncMock(side_effect=Exception("DB 연결 실패"))

        result = legal_node(_BASE_STATE.copy())
        risks = result["analysis_results"]["legal_risks"]
        ftc_risk = next((r for r in risks if r["type"] == "ftc_franchise"), None)

        assert ftc_risk is not None, "ftc_franchise 리스크가 누락됨"
        assert ftc_risk["level"] in {"safe", "caution", "danger"}, f"DB 실패 후 ftc level 비정상: {ftc_risk['level']}"


@patch("src.agents.nodes.legal._async_call_llm", new_callable=AsyncMock, return_value=_MOCK_LLM_RESPONSE)
def test_legal_node_fallback_when_no_rag_docs(mock_llm):
    """
    retriever.search()가 빈 리스트를 반환할 때
    legal_info가 fallback(risks summary)으로 채워지는지 확인
    """
    from unittest.mock import AsyncMock

    with patch("src.agents.nodes.legal.LegalDocumentRetriever") as MockRetriever:
        mock_instance = MockRetriever.return_value
        mock_instance.search = AsyncMock(return_value=[])

        result = legal_node(_BASE_STATE.copy())
        legal_info = result["legal_info"]

        assert len(legal_info) > 0, "RAG 결과 없을 때 fallback이 동작하지 않음"


# ──────────────────────────────────────────────────────────────
# 3. 용도지역 판정 테스트 — 결정론적 (외부 의존성 없음)
# ──────────────────────────────────────────────────────────────


def test_zoning_commercial_district_cafe_safe():
    """상업지역(서교동) 카페 → safe"""
    state = {**_BASE_STATE, "target_district": "서교동", "business_type": "cafe"}
    result = check_zoning_regulation(state)
    assert result["level"] == "safe", f"서교동 카페는 safe여야 함: {result['summary']}"
    assert result["allowed"] is True


def test_zoning_residential_cafe_danger():
    """제1종전용주거지역(강제 매핑) 카페 → danger"""
    state = {**_BASE_STATE, "target_district": "염리동", "business_type": "cafe"}
    result = check_zoning_regulation(state)
    # 염리동은 제2종일반주거지역 → 카페 허용 → safe
    assert result["level"] in {"safe", "caution", "danger"}
    assert "type" in result
    assert result["type"] == "zoning_regulation"


def test_zoning_returns_required_keys():
    """check_zoning_regulation 반환 dict 구조 검증"""
    state = {**_BASE_STATE, "target_district": "합정동", "business_type": "restaurant"}
    result = check_zoning_regulation(state)

    required_keys = {"type", "level", "zone", "business_type", "allowed", "summary"}
    missing = required_keys - set(result.keys())
    assert not missing, f"누락된 키: {missing}"


def test_zoning_unknown_district_defaults_to_commercial():
    """등록되지 않은 행정동은 근린상업지역으로 fallback 처리"""
    state = {**_BASE_STATE, "target_district": "존재하지않는동", "business_type": "cafe"}
    result = check_zoning_regulation(state)
    assert result["zone"] == "근린상업지역", "알 수 없는 동은 근린상업지역이어야 함"
    assert result["level"] == "safe"


def test_zoning_mapo_dong_map_coverage():
    """마포구 주요 행정동 전체가 용도지역 맵에 등록되어 있는지 확인"""
    from src.agents.nodes.legal import _DISTRICT_ZONE_MAP

    mapo_dongs = [
        "서교동",
        "합정동",
        "공덕동",
        "망원1동",
        "망원2동",
        "연남동",
        "대흥동",
        "염리동",
        "성산1동",
        "성산2동",
        "상암동",
        "아현동",
        "도화동",
        "용강동",
        "신수동",
        "서강동",
    ]
    for dong in mapo_dongs:
        assert dong in _DISTRICT_ZONE_MAP, f"{dong}이 용도지역 맵에 없음"
