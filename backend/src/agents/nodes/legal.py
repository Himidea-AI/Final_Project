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
import os

from src.agents.state import AgentState
from src.chains.prompts import LEGAL_AGENT_SYSTEM_PROMPT, build_legal_prompt
from src.chains.retriever import LegalDocumentRetriever
from src.config.settings import settings
from src.services.ftc_franchise import FtcFranchiseClient
from src.services.law_api import LawApiClient


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
    LLM 호출 — LLM_PROVIDER 환경변수로 백엔드를 선택.

    LLM_PROVIDER=ollama     : 로컬 Ollama (기본값, 무료)
    LLM_PROVIDER=anthropic  : Anthropic Claude API (유료)
    LLM_PROVIDER=gemini     : Google Gemini API (유료)
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()

    if provider == "anthropic":
        import anthropic as _anthropic
        from src.config.constants import LLM_MODEL, LLM_TIMEOUT

        client = _anthropic.Anthropic()
        message = client.messages.create(
            model=LLM_MODEL,
            max_tokens=1024,
            timeout=LLM_TIMEOUT,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text

    if provider == "gemini":
        from langchain_core.messages import HumanMessage, SystemMessage
        from src.agents.llms import get_fast_llm

        llm = get_fast_llm()
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_message)])
        return response.content if isinstance(response.content, str) else str(response.content)

    # 기본값: Ollama
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_ollama import ChatOllama

    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
    llm = ChatOllama(model=ollama_model, temperature=0.1)
    # qwen3.5 thinking 모델 — /no_think 프리픽스로 추론 단계 스킵해 속도 향상
    prefixed_message = f"/no_think\n{user_message}"
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=prefixed_message)])
    content = response.content if isinstance(response.content, str) else str(response.content)
    return content


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


def check_franchise_law(state: AgentState, docs: list[dict]) -> dict:
    """
    가맹사업법 검토 — 영업지역 보장 의무 및 출점 제한 검토.

    주요 검토 항목:
    - 동일 브랜드 기존 점포와의 거리 (영업지역 침해 여부)
    - 정보공개서 기재 사항 준수
    - 가맹금 예치 의무

    Args:
        docs: _fetch_all_docs_parallel()에서 병렬 검색된 가맹사업법 문서

    Returns:
        dict: {type, level, summary, articles, recommendation}
    """
    brand = state.get("brand_name") or "해당 브랜드"
    district = state.get("target_district", "")

    question = (
        f"'{brand}' 브랜드가 '{district}'에 신규 출점할 때 가맹사업법상 영업지역 침해 리스크는 어떻게 됩니까? "
        "기존 가맹점과의 거리 보호 의무, 정보공개서 의무를 중심으로 검토해 주세요. "
        "마지막 줄에 리스크 수준을 '안전', '주의', '위험' 중 하나로 명시하세요."
    )

    user_message = build_legal_prompt(docs, question)

    try:
        response = _call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        articles = [d["metadata"].get("law_article", "") for d in docs]
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


def check_commercial_lease_law(state: AgentState, docs: list[dict]) -> dict:
    """
    상가임대차보호법 검토 — 임차인 보호 범위 및 권리금 리스크 검토.

    주요 검토 항목:
    - 권리금 회수 기회 보호 (제10조의4)
    - 계약갱신요구권 행사 가능 여부 (최대 10년)
    - 환산보증금 기준 충족 여부 (서울 9억 원)

    Args:
        docs: _fetch_all_docs_parallel()에서 병렬 검색된 상가임대차보호법 문서

    Returns:
        dict: {type, level, summary, articles, recommendation}
    """
    district = state.get("target_district", "")

    question = (
        f"'{district}'에서 프랜차이즈 점포를 임차할 때 상가임대차보호법상 주요 리스크는 무엇입니까? "
        "권리금 회수 보호, 계약갱신요구권, 환산보증금 기준을 중심으로 검토해 주세요. "
        "마지막 줄에 리스크 수준을 '안전', '주의', '위험' 중 하나로 명시하세요."
    )

    user_message = build_legal_prompt(docs, question)

    try:
        response = _call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        articles = [d["metadata"].get("law_article", "") for d in docs]
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


def check_food_hygiene(state: AgentState, docs: list[dict]) -> dict:
    """
    식품위생법 검토 — 업종별 영업신고/허가 및 위생 기준 검토.

    주요 검토 항목:
    - 영업 종류별 신고·허가 의무 (식품위생법 시행규칙)
    - 위생교육 이수 의무
    - 영업장 시설 기준

    Args:
        docs: _fetch_all_docs_parallel()에서 병렬 검색된 식품위생법 문서

    Returns:
        dict: {type, level, summary, articles, recommendation}
    """
    business_type = state.get("business_type", "")
    district = state.get("target_district", "")

    question = (
        f"'{district}'에서 '{business_type}' 업종으로 프랜차이즈 창업 시 식품위생법상 "
        "영업신고·허가 의무, 위생교육 이수 요건, 시설 기준을 검토해 주세요. "
        "마지막 줄에 리스크 수준을 '안전', '주의', '위험' 중 하나로 명시하세요."
    )

    user_message = build_legal_prompt(docs, question)

    try:
        response = _call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        articles = [d["metadata"].get("law_article", "") for d in docs]
        return {
            "type": "food_hygiene",
            "level": level,
            "summary": response,
            "articles": articles,
            "recommendation": "영업신고 전 관할 보건소 위생과 확인 권장" if level != "safe" else "",
        }
    except Exception as e:
        return {
            "type": "food_hygiene",
            "level": "caution",
            "summary": f"식품위생법 검토 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "수동 법률 검토 필요",
        }


def check_safety_regulation(state: AgentState, docs: list[dict]) -> dict:
    """
    다중이용업소 안전관리법 검토 — 소방·안전 시설 의무 검토.

    주요 검토 항목:
    - 다중이용업소 해당 여부 (면적·업종 기준)
    - 소방시설 설치 의무 (간이스프링클러, 비상구 등)
    - 안전시설 완비증명서 발급 의무

    Args:
        docs: _fetch_all_docs_parallel()에서 병렬 검색된 다중이용업소법 문서

    Returns:
        dict: {type, level, summary, articles, recommendation}
    """
    business_type = state.get("business_type", "")

    question = (
        f"'{business_type}' 업종 프랜차이즈 창업 시 다중이용업소의 안전관리에 관한 특별법상 "
        "다중이용업소 해당 여부, 소방시설 설치 의무, 안전시설 완비증명서 발급 요건을 검토해 주세요. "
        "마지막 줄에 리스크 수준을 '안전', '주의', '위험' 중 하나로 명시하세요."
    )

    user_message = build_legal_prompt(docs, question)

    try:
        response = _call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        articles = [d["metadata"].get("law_article", "") for d in docs]
        return {
            "type": "safety_regulation",
            "level": level,
            "summary": response,
            "articles": articles,
            "recommendation": "소방서 안전시설 완비증명서 사전 확인 필수" if level != "safe" else "",
        }
    except Exception as e:
        return {
            "type": "safety_regulation",
            "level": "caution",
            "summary": f"다중이용업소 안전관리법 검토 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "수동 법률 검토 필요",
        }


def check_ftc_franchise(state: AgentState) -> dict:
    """
    공정위 가맹사업 정보공개서 검토 — 브랜드 폐점률·매출·가맹금 리스크 판정.

    주요 검토 항목:
    - 폐점률 (10% 초과 시 위험, 5% 초과 시 주의)
    - 평균 매출액 (1억 미만 시 주의)
    - 가맹금 수준 (1000만 원 초과 시 주의)

    Returns:
        dict: {type, level, summary, articles, recommendation}
    """
    brand = state.get("brand_name") or ""

    if not brand:
        return {
            "type": "ftc_franchise",
            "level": "caution",
            "summary": "브랜드명이 입력되지 않아 공정위 정보공개서 조회를 건너뜁니다.",
            "articles": [],
            "recommendation": "브랜드명 입력 후 재검토 권장",
        }

    if not settings.ftc_api_key:
        return {
            "type": "ftc_franchise",
            "level": "caution",
            "summary": "FTC_API_KEY가 설정되지 않아 공정위 정보공개서 조회를 건너뜁니다.",
            "articles": [],
            "recommendation": "환경변수 FTC_API_KEY 설정 후 재검토 권장",
        }

    try:
        client = FtcFranchiseClient(api_key=settings.ftc_api_key)
        detail = _run_async(client.get_brand_detail(brand))

        if not detail:
            return {
                "type": "ftc_franchise",
                "level": "caution",
                "summary": f"'{brand}' 브랜드의 공정위 정보공개서를 찾을 수 없습니다.",
                "articles": [],
                "recommendation": "공정위 가맹사업정보제공시스템 직접 확인 권장",
            }

        churn_rate = detail.get("churn_rate", 0.0)
        avg_sales = detail.get("avg_sales_amount", 0)
        franchise_fee = detail.get("franchise_fee", 0)
        store_count = detail.get("store_count_total", 0)

        # 리스크 레벨 판정
        if churn_rate > 0.10:
            level = "danger"
        elif churn_rate > 0.05 or avg_sales < 100_000_000:
            level = "caution"
        else:
            level = "safe"

        summary = (
            f"'{detail.get('brand_name', brand)}' ({detail.get('corp_name', '')}) "
            f"정보공개서 기준 — "
            f"전체 가맹점 수: {store_count}개, "
            f"폐점률: {churn_rate:.1%}, "
            f"평균 매출액: {avg_sales:,}원, "
            f"가입비: {franchise_fee:,}원. "
        )
        if level == "danger":
            summary += "폐점률이 10%를 초과하여 사업 안정성 리스크가 높습니다."
        elif level == "caution":
            summary += "폐점률 또는 매출 수준에서 주의가 필요합니다."
        else:
            summary += "공정위 지표 기준 안정적인 브랜드로 판단됩니다."

        recommendation = ""
        if level == "danger":
            recommendation = "가맹본부 재무 상태 및 폐점 원인 심층 확인 필수"
        elif level == "caution":
            recommendation = "가맹 계약 전 정보공개서 원문 직접 검토 권장"

        return {
            "type": "ftc_franchise",
            "level": level,
            "summary": summary,
            "articles": [],
            "recommendation": recommendation,
        }

    except Exception as e:
        return {
            "type": "ftc_franchise",
            "level": "caution",
            "summary": f"공정위 정보공개서 조회 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "공정위 가맹사업정보제공시스템 직접 확인 권장",
        }


def check_zoning_regulation(state: AgentState) -> dict:
    """
    용도지역 규제 검토 — 대상 행정동의 용도지역에서 해당 업종 영업 가능 여부.

    LLM 없이 constants 기반 규칙으로 판정 (빠르고 결정론적).

    Returns:
        dict: {type, level, zone, business_type, allowed, summary}
    """
    district = state.get("target_district", "")
    business_type = state.get("business_type", "")  # "cafe" | "restaurant" | "convenience"

    zone = _DISTRICT_ZONE_MAP.get(district, "근린상업지역")  # 알 수 없는 동은 상업지역으로 가정
    rules = _ZONING_RULES.get(zone, {"허용": [], "제한": []})

    # business_type 코드 → 한글 매핑
    type_label = {"cafe": "카페", "restaurant": "음식점", "convenience": "편의점"}.get(business_type, business_type)

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
        "articles": [],
        "recommendation": "토지이음(eum.go.kr)에서 실제 용도지역을 확인하세요." if level != "safe" else "",
    }


async def _fetch_all_docs_parallel(state: dict, retriever: LegalDocumentRetriever) -> tuple:
    """
    RAG 검색 5개 + 판례 API 검색 2개를 asyncio.gather()로 병렬 실행.

    순차 실행 대비 응답 시간을 대폭 단축.

    Returns:
        tuple: (franchise_docs, lease_docs, food_docs, safety_docs, summary_docs,
                franchise_prec, lease_prec)
    """
    brand = state.get("brand_name") or "해당 브랜드"
    district = state.get("target_district", "")
    business_type = state.get("business_type", "")

    franchise_q = f"{brand} 영업지역 보장 동일 브랜드 출점 제한 가맹사업법"
    lease_q = "권리금 회수 기회 보호 계약갱신요구권 환산보증금 상가임대차보호법"
    food_q = f"{business_type} 영업신고 허가 위생교육 시설기준 식품위생법"
    safety_q = f"{business_type} 다중이용업소 소방시설 안전시설 완비증명 의무"
    summary_q = f"{business_type} {district} 프랜차이즈 법률 검토"

    law_client = LawApiClient()

    return await asyncio.gather(
        # pgvector RAG 검색
        retriever.search(franchise_q, top_k=5, source_filter=LegalDocumentRetriever.FRANCHISE_LAW_SOURCES),
        retriever.search(lease_q, top_k=5, source_filter=LegalDocumentRetriever.LEASE_LAW_SOURCES),
        retriever.search(food_q, top_k=5, source_filter=LegalDocumentRetriever.FOOD_HYGIENE_SOURCES),
        retriever.search(safety_q, top_k=5, source_filter=LegalDocumentRetriever.SAFETY_SOURCES),
        retriever.search(summary_q, top_k=10),
        # 국가법령정보 판례 검색 (단일 핵심 키워드로 검색)
        law_client.search_precedents("가맹사업", display=3),
        law_client.search_precedents("권리금", display=3),
    )


def legal_node(state) -> dict:
    """
    법규검토 Agent 메인 노드 — LangGraph에서 호출되는 진입점.

    Pydantic AgentState / TypedDict AgentState 양쪽 모두 지원.
    결과는 analysis_results["legal_risks"]에 저장하고 dict로 반환.
    검토 중 오류가 발생해도 다른 검토는 계속 진행 (부분 실패 허용).

    최적화: _fetch_all_docs_parallel()로 RAG 검색 5개를 병렬 실행 후
            각 check 함수에 pre-fetched docs를 전달 (순차 검색 제거).
    """
    # Pydantic 모델이 넘어온 경우 dict로 정규화 (TypedDict는 이미 dict)
    if not isinstance(state, dict):
        state = state.model_dump()

    retriever = LegalDocumentRetriever()

    # RAG 검색 5개 + 판례 검색 2개 병렬 실행 (핵심 최적화)
    franchise_docs, lease_docs, food_docs, safety_docs, legal_info_docs, franchise_prec, lease_prec = _run_async(
        _fetch_all_docs_parallel(state, retriever)
    )

    risks: list[dict] = []

    # 1. 가맹사업법 검토 (RAG docs + 판례 병합)
    risks.append(check_franchise_law(state, franchise_docs + franchise_prec))

    # 2. 상가임대차보호법 검토 (RAG docs + 판례 병합)
    risks.append(check_commercial_lease_law(state, lease_docs + lease_prec))

    # 3. 용도지역 규제 검토 (LLM 없이 규칙 기반)
    risks.append(check_zoning_regulation(state))

    # 4. 식품위생법 검토 (pre-fetched docs 사용)
    risks.append(check_food_hygiene(state, food_docs))

    # 5. 다중이용업소 안전관리법 검토 (pre-fetched docs 사용)
    risks.append(check_safety_regulation(state, safety_docs))

    # 6. 공정위 가맹사업 정보공개서 검토
    risks.append(check_ftc_franchise(state))

    # legal_info: RAG 문서 + 판례 합산 (graph.py 로그 + supervisor 완료 신호용)
    precedents = franchise_prec + lease_prec
    legal_info = (legal_info_docs + precedents) or [
        {"content": r["summary"], "metadata": {"source": r["type"], "relevance": 1.0}} for r in risks
    ]

    # analysis_results dict 업데이트
    analysis = dict(state.get("analysis_results") or {})
    analysis["legal_risks"] = risks

    return {**state, "analysis_results": analysis, "legal_info": legal_info}


# graph.py(B1) 호환성 별칭
legal_analyst_node = legal_node
