"""
법규검토 Agent — RAG 기반 가맹사업법/상가임대차보호법 리스크 검토

주요 데이터 소스:
  - ChromaDB에 인덱싱된 가맹사업법 / 상가임대차보호법 조문
  - 업종별 용도지역 규제 (constants.py)

리스크 레벨:
  - "safe"    : 특별한 법률 리스크 없음
  - "caution" : 주의 필요, 사전 확인 권고
  - "danger"  : 위반 가능성 높음, 전문가 상담 필수
"""

import asyncio
import concurrent.futures

import anthropic

from src.agents.state import AgentState, AnalysisResults
from src.chains.prompts import LEGAL_AGENT_SYSTEM_PROMPT, build_legal_prompt
from src.chains.retriever import LegalDocumentRetriever
from src.config.constants import LLM_MODEL, LLM_TIMEOUT

def _run_async(coro):
    """
    동기 컨텍스트에서 비동기 코루틴 실행.

    FastAPI/LangGraph 등 이미 이벤트 루프가 돌고 있는 환경에서
    asyncio.run()을 직접 호출하면 RuntimeError가 발생한다.
    별도 스레드에서 새 루프를 만들어 실행하면 안전하게 처리된다.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


# ── 용도지역별 허용 업종 규칙 ────────────────────────────────────────────────
# 마포구 내 주요 용도지역과 음식점/카페 영업 가능 여부
# (실제 입지 확인 시 국토부 토지이음 API로 보완 필요)
_ZONING_RULES: dict[str, dict] = {
    "제1종전용주거지역": {"허용": [], "제한": ["카페", "음식점", "편의점"]},
    "제2종전용주거지역": {"허용": [], "제한": ["카페", "음식점", "편의점"]},
    "제1종일반주거지역": {"허용": ["편의점"], "제한": ["카페", "음식점"]},
    "제2종일반주거지역": {"허용": ["편의점", "카페"], "제한": ["음식점"]},
    "제3종일반주거지역": {"허용": ["편의점", "카페", "음식점"], "제한": []},
    "준주거지역": {"허용": ["편의점", "카페", "음식점"], "제한": []},
    "일반상업지역": {"허용": ["편의점", "카페", "음식점"], "제한": []},
    "근린상업지역": {"허용": ["편의점", "카페", "음식점"], "제한": []},
}

# 마포구 대부분의 상권(서교동, 합정동, 공덕동 등)은 근린상업/일반상업 지역
_DISTRICT_ZONE_MAP: dict[str, str] = {
    "서교동": "일반상업지역",
    "합정동": "근린상업지역",
    "공덕동": "일반상업지역",
    "망원1동": "근린상업지역",
    "망원2동": "근린상업지역",
    "연남동": "제3종일반주거지역",
    "대흥동": "제2종일반주거지역",
    "염리동": "제2종일반주거지역",
    "성산1동": "근린상업지역",
    "성산2동": "근린상업지역",
    "상암동": "일반상업지역",
    "아현동": "근린상업지역",
    "도화동": "근린상업지역",
    "용강동": "근린상업지역",
    "신수동": "제2종일반주거지역",
    "서강동": "근린상업지역",
}


def _call_llm(system_prompt: str, user_message: str) -> str:
    """
    Claude API 호출 — 법률 텍스트 해석용.

    LLM_TIMEOUT, LLM_MAX_RETRIES는 constants.py에서 관리.
    """
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=LLM_MODEL,
        max_tokens=1024,
        timeout=LLM_TIMEOUT,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def _extract_risk_level(llm_response: str) -> str:
    """
    LLM 응답에서 리스크 레벨 파싱.

    LLM 응답에 "위험", "주의", "안전" 키워드가 포함되어 있다고 가정.
    명확하지 않으면 "caution"으로 보수적으로 처리.
    """
    lower = llm_response.lower()
    if "위험" in lower or "danger" in lower or "위반" in lower:
        return "danger"
    if "안전" in lower or "safe" in lower or "문제없" in lower:
        return "safe"
    return "caution"


def check_franchise_law(state: AgentState, retriever: LegalDocumentRetriever) -> dict:
    """
    가맹사업법 검토 — 영업지역 보장 의무 및 출점 제한 검토.

    주요 검토 항목:
    - 동일 브랜드 기존 점포와의 거리 (영업지역 침해 여부)
    - 정보공개서 기재 사항 준수
    - 가맹금 예치 의무

    Returns:
        dict: {type, level, summary, articles, recommendation}
    """
    brand = state.brand_name or "해당 브랜드"
    district = state.target_district

    query = f"{brand} 영업지역 보장 동일 브랜드 출점 제한 가맹사업법"
    docs = _run_async(retriever.search(query, top_k=5, source_filter=LegalDocumentRetriever.FRANCHISE_LAW_SOURCES))

    question = (
        f"'{brand}' 브랜드가 '{district}'에 신규 출점할 때 가맹사업법상 영업지역 침해 리스크는 어떻게 됩니까? "
        "기존 가맹점과의 거리 보호 의무, 정보공개서 의무를 중심으로 검토해 주세요. "
        "마지막 줄에 리스크 수준을 '안전', '주의', '위험' 중 하나로 명시하세요."
    )

    user_message = build_legal_prompt(docs, question)

    try:
        response = _call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        articles = [d["metadata"].get("article", "") for d in docs]
        return {
            "type": "franchise_law",
            "level": level,
            "summary": response,
            "articles": articles,
            "recommendation": "가맹본부에 영업지역 확인 후 계약 진행 권장" if level != "safe" else "",
        }
    except Exception as e:
        return {
            "type": "franchise_law",
            "level": "caution",
            "summary": f"가맹사업법 검토 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "수동 법률 검토 필요",
        }


def check_commercial_lease_law(state: AgentState, retriever: LegalDocumentRetriever) -> dict:
    """
    상가임대차보호법 검토 — 임차인 보호 범위 및 권리금 리스크 검토.

    주요 검토 항목:
    - 권리금 회수 기회 보호 (제10조의4)
    - 계약갱신요구권 행사 가능 여부 (최대 10년)
    - 환산보증금 기준 충족 여부 (서울 9억 원)

    Returns:
        dict: {type, level, summary, articles, recommendation}
    """
    district = state.target_district

    query = "권리금 회수 기회 보호 계약갱신요구권 환산보증금 상가임대차보호법"
    docs = _run_async(retriever.search(query, top_k=5, source_filter=LegalDocumentRetriever.LEASE_LAW_SOURCES))

    question = (
        f"'{district}'에서 프랜차이즈 점포를 임차할 때 상가임대차보호법상 주요 리스크는 무엇입니까? "
        "권리금 회수 보호, 계약갱신요구권, 환산보증금 기준을 중심으로 검토해 주세요. "
        "마지막 줄에 리스크 수준을 '안전', '주의', '위험' 중 하나로 명시하세요."
    )

    user_message = build_legal_prompt(docs, question)

    try:
        response = _call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        articles = [d["metadata"].get("article", "") for d in docs]
        return {
            "type": "commercial_lease_law",
            "level": level,
            "summary": response,
            "articles": articles,
            "recommendation": "임대차 계약 전 법무사/변호사 검토 권장" if level == "danger" else "",
        }
    except Exception as e:
        return {
            "type": "commercial_lease_law",
            "level": "caution",
            "summary": f"상가임대차보호법 검토 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "수동 법률 검토 필요",
        }


def check_zoning_regulation(state: AgentState) -> dict:
    """
    용도지역 규제 검토 — 대상 행정동의 용도지역에서 해당 업종 영업 가능 여부.

    LLM 없이 constants 기반 규칙으로 판정 (빠르고 결정론적).

    Returns:
        dict: {type, level, zone, business_type, allowed, summary}
    """
    district = state.target_district
    business_type = state.business_type  # "cafe" | "restaurant" | "convenience"

    zone = _DISTRICT_ZONE_MAP.get(district, "근린상업지역")  # 알 수 없는 동은 상업지역으로 가정
    rules = _ZONING_RULES.get(zone, {"허용": [], "제한": []})

    # business_type 코드 → 한글 매핑
    type_label = {"cafe": "카페", "restaurant": "음식점", "convenience": "편의점"}.get(
        business_type, business_type
    )

    if type_label in rules["제한"]:
        level = "danger"
        summary = f"'{district}'의 용도지역({zone})에서 '{type_label}' 영업은 제한될 수 있습니다."
    elif type_label in rules["허용"] or not rules["제한"]:
        level = "safe"
        summary = f"'{district}'의 용도지역({zone})에서 '{type_label}' 영업 가능합니다."
    else:
        level = "caution"
        summary = f"'{district}'의 용도지역({zone}) 규제를 현장 확인 후 영업 가능 여부를 판단하세요."

    return {
        "type": "zoning_regulation",
        "level": level,
        "zone": zone,
        "business_type": type_label,
        "allowed": level != "danger",
        "summary": summary,
    }


def legal_node(state: AgentState) -> AgentState:
    """
    법규검토 Agent 메인 노드 — LangGraph에서 호출되는 진입점.

    3가지 법률 검토를 수행하고 결과를 state.analysis_results.legal_risks에 저장.
    검토 중 오류가 발생해도 다른 검토는 계속 진행 (부분 실패 허용).
    """
    retriever = LegalDocumentRetriever()

    risks: list[dict] = []

    # 1. 가맹사업법 검토
    franchise_result = check_franchise_law(state, retriever)
    risks.append(franchise_result)

    # 2. 상가임대차보호법 검토
    lease_result = check_commercial_lease_law(state, retriever)
    risks.append(lease_result)

    # 3. 용도지역 규제 검토 (LLM 없이 규칙 기반)
    zoning_result = check_zoning_regulation(state)
    risks.append(zoning_result)

    # state 업데이트 — analysis_results가 없으면 초기화
    if state.analysis_results is None:
        state = state.model_copy(update={"analysis_results": AnalysisResults()})

    updated_results = state.analysis_results.model_copy(update={"legal_risks": risks})
    return state.model_copy(update={"analysis_results": updated_results})
