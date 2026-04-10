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
import json
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
# 행정동 16개 + 법정동 별칭 포함 (법정동으로 입력해도 동일 결과 반환)
_DISTRICT_ZONE_MAP: dict[str, str] = {
    # ── 행정동 (16개) ──────────────────────────────────────────
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
    # ── 법정동 별칭 → 행정동 용도지역으로 매핑 ────────────────
    # 망원1·2동 권역
    "망원동": "근린상업지역",
    # 성산1·2동 권역
    "성산동": "근린상업지역",
    # 공덕동 권역
    "토정동": "일반상업지역",
    "마포동": "일반상업지역",
    "신정동": "일반상업지역",
    "대도동": "일반상업지역",
    # 도화동 권역
    "현석동": "근린상업지역",
    # 서강동 권역
    "창전동": "근린상업지역",
    "노고산동": "근린상업지역",
    "산천동": "근린상업지역",
    # 합정동 권역
    "양화동": "근린상업지역",
    # 대흥동 권역
    "용문동": "제2종일반주거지역",
    # 아현동 권역
    "공덕1동": "일반상업지역",
    "공덕2동": "일반상업지역",
    # 상암동 권역
    "성암동": "일반상업지역",
    "중암동": "일반상업지역",
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
        import time

        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1,
        )
        # 429 RESOURCE_EXHAUSTED 시 최대 2회 재시도 (지수 백오프)
        for attempt in range(3):
            try:
                response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_message)])
                return response.content if isinstance(response.content, str) else str(response.content)
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    wait = 30 * (2**attempt)  # 30s → 60s
                    print(f"[Gemini] 429 발생, {wait}초 후 재시도 ({attempt + 1}/2)")
                    time.sleep(wait)
                else:
                    raise

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


async def _async_call_llm(system_prompt: str, user_message: str) -> str:
    """
    _call_llm의 비동기 버전 — asyncio.gather()로 LLM 호출을 병렬 실행할 때 사용.

    LLM_PROVIDER 환경변수로 백엔드를 선택 (동기 버전과 동일한 로직).
    Gemini 429 재시도는 asyncio.sleep으로 이벤트 루프를 블로킹하지 않음.
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()

    if provider == "anthropic":
        import anthropic as _anthropic
        from src.config.constants import LLM_MODEL, LLM_TIMEOUT

        client = _anthropic.AsyncAnthropic()
        message = await client.messages.create(
            model=LLM_MODEL,
            max_tokens=1024,
            timeout=LLM_TIMEOUT,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return message.content[0].text

    if provider == "gemini":
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1,
        )
        for attempt in range(3):
            try:
                response = await llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=user_message)])
                return response.content if isinstance(response.content, str) else str(response.content)
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    wait = 30 * (2**attempt)  # 30s → 60s
                    print(f"[Gemini] 429 발생, {wait}초 후 재시도 ({attempt + 1}/2)")
                    await asyncio.sleep(wait)  # 이벤트 루프 비블로킹 대기
                else:
                    raise

    # 기본값: Ollama
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_ollama import ChatOllama

    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
    llm = ChatOllama(model=ollama_model, temperature=0.1)
    prefixed_message = f"/no_think\n{user_message}"
    response = await llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=prefixed_message)])
    return response.content if isinstance(response.content, str) else str(response.content)


def _extract_risk_level(llm_response: str) -> str:
    """
    LLM 응답 마지막 줄의 JSON에서 리스크 레벨 파싱.

    1차: JSON {"risk_level": "..."} 파싱 (프롬프트에서 강제)
    2차: 키워드 매칭 fallback (LLM이 JSON 형식을 따르지 않은 경우)
    """
    import json
    import re

    # 1차: 마지막 줄 JSON 파싱
    last_line = llm_response.strip().splitlines()[-1].strip() if llm_response.strip() else ""
    try:
        data = json.loads(last_line)
        level = data.get("risk_level", "").lower()
        if level in ("safe", "caution", "danger"):
            return level
    except (json.JSONDecodeError, AttributeError):
        pass

    # 1차 실패 시: 응답 전체에서 JSON 패턴 탐색
    match = re.search(r'\{"risk_level"\s*:\s*"(safe|caution|danger)"\}', llm_response)
    if match:
        return match.group(1)

    # 2차 fallback: 키워드 매칭
    lower = llm_response.lower()
    if "위험" in lower or "danger" in lower or "위반" in lower:
        return "danger"
    if "안전" in lower or "safe" in lower or "문제없" in lower:
        return "safe"
    return "caution"


async def check_franchise_law(state: AgentState, docs: list[dict]) -> dict:
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
        '답변 맨 마지막 줄에 반드시 다음 JSON만 출력하세요: {"risk_level": "safe"} 또는 {"risk_level": "caution"} 또는 {"risk_level": "danger"}'
    )

    user_message = build_legal_prompt(docs, question)

    try:
        response = await _async_call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
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


async def check_commercial_lease_law(state: AgentState, docs: list[dict]) -> dict:
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
        '답변 맨 마지막 줄에 반드시 다음 JSON만 출력하세요: {"risk_level": "safe"} 또는 {"risk_level": "caution"} 또는 {"risk_level": "danger"}'
    )

    user_message = build_legal_prompt(docs, question)

    try:
        response = await _async_call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
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


async def check_food_hygiene(state: AgentState, docs: list[dict]) -> dict:
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
        '답변 맨 마지막 줄에 반드시 다음 JSON만 출력하세요: {"risk_level": "safe"} 또는 {"risk_level": "caution"} 또는 {"risk_level": "danger"}'
    )

    user_message = build_legal_prompt(docs, question)

    try:
        response = await _async_call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
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


async def check_safety_regulation(state: AgentState, docs: list[dict]) -> dict:
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
        '답변 맨 마지막 줄에 반드시 다음 JSON만 출력하세요: {"risk_level": "safe"} 또는 {"risk_level": "caution"} 또는 {"risk_level": "danger"}'
    )

    user_message = build_legal_prompt(docs, question)

    try:
        response = await _async_call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
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


async def check_building_law(state: AgentState, docs: list[dict]) -> dict:
    """
    건축법 검토 — 용도변경 및 건축물 용도 적합성 검토.

    주요 검토 항목:
    - 영업장 건축물 용도 적합 여부 (근린생활시설 등)
    - 용도변경 신고·허가 의무
    - 무허가·불법건축물 임차 리스크

    Args:
        docs: _fetch_all_docs_parallel()에서 병렬 검색된 건축법 문서

    Returns:
        dict: {type, level, summary, articles, recommendation}
    """
    business_type = state.get("business_type", "")
    district = state.get("target_district", "")

    question = (
        f"'{district}'에서 '{business_type}' 업종으로 창업할 때 건축법상 "
        "건축물 용도 적합성, 용도변경 신고·허가 의무, 불법건축물 임차 리스크를 검토해 주세요. "
        '답변 맨 마지막 줄에 반드시 다음 JSON만 출력하세요: {"risk_level": "safe"} 또는 {"risk_level": "caution"} 또는 {"risk_level": "danger"}'
    )

    user_message = build_legal_prompt(docs, question)

    try:
        response = await _async_call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        articles = [d["metadata"].get("law_article", "") for d in docs]
        return {
            "type": "building_law",
            "level": level,
            "summary": response,
            "articles": articles,
            "recommendation": "관할 구청 건축과에서 건축물 대장 및 용도 확인 필수" if level != "safe" else "",
        }
    except Exception as e:
        return {
            "type": "building_law",
            "level": "caution",
            "summary": f"건축법 검토 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "수동 법률 검토 필요",
        }


async def check_fire_safety_law(state: AgentState, docs: list[dict]) -> dict:
    """
    소방시설법 검토 — 소방시설 설치·유지 의무 검토.

    주요 검토 항목:
    - 업종·면적별 소방시설 설치 의무 (스프링클러, 소화기, 감지기 등)
    - 소방안전관리자 선임 의무
    - 소방시설 완공검사 및 정기점검 의무

    Args:
        docs: _fetch_all_docs_parallel()에서 병렬 검색된 소방시설법 문서

    Returns:
        dict: {type, level, summary, articles, recommendation}
    """
    business_type = state.get("business_type", "")

    question = (
        f"'{business_type}' 업종 창업 시 소방시설 설치 및 관리에 관한 법률상 "
        "소방시설 설치·유지 의무, 소방안전관리자 선임 요건, 완공검사 및 정기점검 의무를 검토해 주세요. "
        '답변 맨 마지막 줄에 반드시 다음 JSON만 출력하세요: {"risk_level": "safe"} 또는 {"risk_level": "caution"} 또는 {"risk_level": "danger"}'
    )

    user_message = build_legal_prompt(docs, question)

    try:
        response = await _async_call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        articles = [d["metadata"].get("law_article", "") for d in docs]
        return {
            "type": "fire_safety_law",
            "level": level,
            "summary": response,
            "articles": articles,
            "recommendation": "관할 소방서에서 소방시설 설치계획 사전 협의 권장" if level != "safe" else "",
        }
    except Exception as e:
        return {
            "type": "fire_safety_law",
            "level": "caution",
            "summary": f"소방시설법 검토 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "수동 법률 검토 필요",
        }


async def check_labor_law(state: AgentState, docs: list[dict]) -> dict:
    """
    근로기준법 검토 — 직원 고용 시 필수 준수 사항 검토.

    주요 검토 항목:
    - 근로계약서 작성·교부 의무
    - 최저임금 준수 의무
    - 주휴수당, 연장·야간근로 가산임금 의무
    - 4대 보험 가입 의무

    Args:
        docs: _fetch_all_docs_parallel()에서 병렬 검색된 근로기준법 문서

    Returns:
        dict: {type, level, summary, articles, recommendation}
    """
    business_type = state.get("business_type", "")

    question = (
        f"'{business_type}' 프랜차이즈 창업 시 직원 고용과 관련하여 근로기준법상 "
        "근로계약서 작성 의무, 최저임금 준수, 주휴수당 및 가산임금, 4대 보험 가입 의무를 검토해 주세요. "
        '답변 맨 마지막 줄에 반드시 다음 JSON만 출력하세요: {"risk_level": "safe"} 또는 {"risk_level": "caution"} 또는 {"risk_level": "danger"}'
    )

    user_message = build_legal_prompt(docs, question)

    try:
        response = await _async_call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        articles = [d["metadata"].get("law_article", "") for d in docs]
        return {
            "type": "labor_law",
            "level": level,
            "summary": response,
            "articles": articles,
            "recommendation": "고용노동부 표준근로계약서 양식 사용 및 노무사 상담 권장" if level != "safe" else "",
        }
    except Exception as e:
        return {
            "type": "labor_law",
            "level": "caution",
            "summary": f"근로기준법 검토 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "수동 법률 검토 필요",
        }


async def check_vat_law(state: AgentState, docs: list[dict]) -> dict:
    """
    부가가치세법 검토 — 사업자 유형 및 세금계산서 의무.

    주요 검토 항목:
    - 사업자등록 의무 (개업 전 등록)
    - 일반과세자 vs 간이과세자 기준 (연 매출 8천만 원)
    - 세금계산서·영수증 발행 의무
    """
    business_type = state.get("business_type", "")

    question = (
        f"'{business_type}' 프랜차이즈 창업 시 부가가치세법상 사업자등록 의무, "
        "일반과세자·간이과세자 판단 기준, 세금계산서 발행 의무를 검토해 주세요. "
        '답변 맨 마지막 줄에 반드시 다음 JSON만 출력하세요: {"risk_level": "safe"} 또는 {"risk_level": "caution"} 또는 {"risk_level": "danger"}'
    )
    user_message = build_legal_prompt(docs, question)
    try:
        response = await _async_call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        return {
            "type": "vat_law",
            "level": level,
            "summary": response,
            "articles": [d["metadata"].get("law_article", "") for d in docs],
            "recommendation": "세무사 상담을 통해 과세 유형 사전 결정 권장" if level != "safe" else "",
        }
    except Exception as e:
        return {
            "type": "vat_law",
            "level": "caution",
            "summary": f"부가가치세법 검토 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "수동 법률 검토 필요",
        }


async def check_privacy_law(state: AgentState, docs: list[dict]) -> dict:
    """
    개인정보 보호법 검토 — 고객 데이터 수집·처리 의무.

    주요 검토 항목:
    - 개인정보 수집 시 동의 의무
    - 개인정보 처리방침 공개 의무
    - CCTV 설치 시 안내판 부착 의무
    """
    business_type = state.get("business_type", "")

    question = (
        f"'{business_type}' 프랜차이즈 창업 시 개인정보 보호법상 "
        "고객 정보 수집·처리 동의 의무, 개인정보 처리방침 공개, CCTV 설치 요건을 검토해 주세요. "
        '답변 맨 마지막 줄에 반드시 다음 JSON만 출력하세요: {"risk_level": "safe"} 또는 {"risk_level": "caution"} 또는 {"risk_level": "danger"}'
    )
    user_message = build_legal_prompt(docs, question)
    try:
        response = await _async_call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        return {
            "type": "privacy_law",
            "level": level,
            "summary": response,
            "articles": [d["metadata"].get("law_article", "") for d in docs],
            "recommendation": "개인정보 처리방침 및 CCTV 안내문 사전 준비 필요" if level != "safe" else "",
        }
    except Exception as e:
        return {
            "type": "privacy_law",
            "level": "caution",
            "summary": f"개인정보 보호법 검토 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "수동 법률 검토 필요",
        }


async def check_accessibility_law(state: AgentState, docs: list[dict]) -> dict:
    """
    장애인편의증진법 검토 — 편의시설 설치 의무.

    주요 검토 항목:
    - 대상 시설 해당 여부 (면적 300㎡ 이상 등)
    - 장애인 주차구역, 경사로, 점자블록 등 편의시설 설치 의무
    """
    business_type = state.get("business_type", "")

    question = (
        f"'{business_type}' 프랜차이즈 창업 시 장애인·노인·임산부 등의 편의증진 보장에 관한 법률상 "
        "편의시설(경사로, 장애인 화장실, 점자블록 등) 설치 의무 대상 여부와 설치 기준을 검토해 주세요. "
        '답변 맨 마지막 줄에 반드시 다음 JSON만 출력하세요: {"risk_level": "safe"} 또는 {"risk_level": "caution"} 또는 {"risk_level": "danger"}'
    )
    user_message = build_legal_prompt(docs, question)
    try:
        response = await _async_call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        return {
            "type": "accessibility_law",
            "level": level,
            "summary": response,
            "articles": [d["metadata"].get("law_article", "") for d in docs],
            "recommendation": "인테리어 설계 전 편의시설 설치 의무 여부 관할 구청 확인 권장" if level != "safe" else "",
        }
    except Exception as e:
        return {
            "type": "accessibility_law",
            "level": "caution",
            "summary": f"장애인편의증진법 검토 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "수동 법률 검토 필요",
        }


async def check_sewage_law(state: AgentState, docs: list[dict]) -> dict:
    """
    하수도법/물환경보전법 검토 — 음식점 오수처리 및 유류분리기 설치 의무.

    주요 검토 항목:
    - 오수처리시설 설치 의무 (음식점)
    - 유류분리기(그리스 트랩) 설치 의무
    - 폐수 배출 허용 기준
    """
    business_type = state.get("business_type", "")

    question = (
        f"'{business_type}' 창업 시 하수도법 및 물환경보전법상 "
        "오수처리시설 설치 의무, 유류분리기(그리스 트랩) 설치 의무, 폐수 배출 기준을 검토해 주세요. "
        '답변 맨 마지막 줄에 반드시 다음 JSON만 출력하세요: {"risk_level": "safe"} 또는 {"risk_level": "caution"} 또는 {"risk_level": "danger"}'
    )
    user_message = build_legal_prompt(docs, question)
    try:
        response = await _async_call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        return {
            "type": "sewage_law",
            "level": level,
            "summary": response,
            "articles": [d["metadata"].get("law_article", "") for d in docs],
            "recommendation": "인테리어 공사 전 유류분리기 설치 계획 포함 여부 확인 필요" if level != "safe" else "",
        }
    except Exception as e:
        return {
            "type": "sewage_law",
            "level": "caution",
            "summary": f"하수도법/물환경보전법 검토 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "수동 법률 검토 필요",
        }


async def check_fair_trade_law(state: AgentState, docs: list[dict]) -> dict:
    """
    공정거래법 검토 — 불공정 가맹 계약 조항 리스크.

    주요 검토 항목:
    - 가맹본부의 불공정 거래 행위 금지
    - 부당한 거래 강제 (필수 물품 고가 공급 등)
    - 공정거래위원회 신고 가능 사항
    """
    brand = state.get("brand_name") or "해당 브랜드"

    question = (
        f"'{brand}' 프랜차이즈 가맹 계약 시 독점규제 및 공정거래에 관한 법률상 "
        "가맹본부의 불공정 거래 행위, 부당한 거래 강제, 필수 물품 공급 관련 리스크를 검토해 주세요. "
        '답변 맨 마지막 줄에 반드시 다음 JSON만 출력하세요: {"risk_level": "safe"} 또는 {"risk_level": "caution"} 또는 {"risk_level": "danger"}'
    )
    user_message = build_legal_prompt(docs, question)
    try:
        response = await _async_call_llm(LEGAL_AGENT_SYSTEM_PROMPT, user_message)
        level = _extract_risk_level(response)
        return {
            "type": "fair_trade_law",
            "level": level,
            "summary": response,
            "articles": [d["metadata"].get("law_article", "") for d in docs],
            "recommendation": "가맹 계약서 내 불공정 조항 법무사 검토 권장" if level != "safe" else "",
        }
    except Exception as e:
        return {
            "type": "fair_trade_law",
            "level": "caution",
            "summary": f"공정거래법 검토 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "수동 법률 검토 필요",
        }


async def check_ftc_franchise(state: AgentState) -> dict:
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
        detail = await client.get_brand_detail(brand)

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

    LLM 없이 constants 기반 규칙으로 판정 (빠르고 결정론적). I/O 없으므로 sync.

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


async def _run_legal_pipeline(state: dict) -> dict:
    """
    2단계 풀 파이프라인으로 법률 검토 수행.

    Phase 1 (병렬 18개): RAG×13 + 판례×4 + FTC API
                         zoning은 I/O 없는 규칙 기반이므로 즉시 실행
    Phase 2 (병렬 12개): LLM 기반 check 함수 동시 실행

    기존 순차 실행 대비 ~35~68초 → ~8~12초로 단축.
    동일 brand+district+business_type 조합은 Redis에 24시간 캐시.
    """
    import redis.asyncio as aioredis

    brand = state.get("brand_name") or "해당 브랜드"
    district = state.get("target_district", "")
    business_type = state.get("business_type", "")

    # Redis 캐시 조회 — 동일 조합 재요청 시 LLM 호출 없이 즉시 반환
    _CACHE_TTL = 86400  # 24시간
    cache_key = f"legal:{brand}:{district}:{business_type}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = await _redis.get(cache_key)
        if cached:
            print(f"[legal_node] 캐시 히트: {cache_key}")
            cached_data = json.loads(cached)
            analysis = dict(state.get("analysis_results") or {})
            analysis["legal_risks"] = cached_data["legal_risks"]
            await _redis.aclose()
            return {**state, "analysis_results": analysis, "legal_info": cached_data["legal_info"]}
    except Exception as e:
        print(f"[legal_node] Redis 캐시 조회 실패 (무시하고 계속): {e}")

    retriever = LegalDocumentRetriever()

    franchise_q = f"{brand} 영업지역 보장 동일 브랜드 출점 제한 가맹사업법"
    lease_q = "권리금 회수 기회 보호 계약갱신요구권 환산보증금 상가임대차보호법"
    food_q = f"{business_type} 영업신고 허가 위생교육 시설기준 식품위생법"
    safety_q = f"{business_type} 다중이용업소 소방시설 안전시설 완비증명 의무"
    summary_q = f"{business_type} {district} 프랜차이즈 법률 검토"
    building_q = f"{business_type} 건축물 용도 근린생활시설 용도변경 건축법"
    fire_q = f"{business_type} 소방시설 스프링클러 소화기 소방안전관리자 설치의무"
    labor_q = "근로계약서 최저임금 주휴수당 가산임금 4대보험 근로기준법"
    vat_q = "사업자등록 일반과세자 간이과세자 세금계산서 부가가치세"
    privacy_q = "개인정보 수집 동의 처리방침 CCTV 고객정보"
    accessibility_q = f"{business_type} 편의시설 경사로 장애인 설치의무"
    sewage_q = f"{business_type} 오수처리 유류분리기 그리스트랩 폐수 하수도"
    fair_trade_q = f"{brand} 가맹본부 불공정거래 거래강제 필수물품 공급"

    law_client = LawApiClient()

    # zoning: I/O 없는 규칙 기반 — 즉시 실행 후 Phase 1 병렬 대기
    zoning_result = check_zoning_regulation(state)

    # Phase 1: RAG×13 + 판례×4 + FTC API 병렬 실행 (총 18개)
    (
        franchise_docs,
        lease_docs,
        food_docs,
        safety_docs,
        legal_info_docs,
        building_docs,
        fire_docs,
        labor_docs,
        vat_docs,
        privacy_docs,
        accessibility_docs,
        sewage_docs,
        fair_trade_docs,
        franchise_prec,
        lease_prec,
        food_prec,
        safety_prec,
        ftc_result,
    ) = await asyncio.gather(
        # RAG 검색 (13개)
        retriever.search(franchise_q, top_k=5, source_filter=LegalDocumentRetriever.FRANCHISE_LAW_SOURCES),
        retriever.search(lease_q, top_k=5, source_filter=LegalDocumentRetriever.LEASE_LAW_SOURCES),
        retriever.search(food_q, top_k=5, source_filter=LegalDocumentRetriever.FOOD_HYGIENE_SOURCES),
        retriever.search(safety_q, top_k=5, source_filter=LegalDocumentRetriever.SAFETY_SOURCES),
        retriever.search(summary_q, top_k=10),
        retriever.search(building_q, top_k=5, source_filter=LegalDocumentRetriever.BUILDING_LAW_SOURCES),
        retriever.search(fire_q, top_k=5, source_filter=LegalDocumentRetriever.FIRE_SAFETY_SOURCES),
        retriever.search(labor_q, top_k=5, source_filter=LegalDocumentRetriever.LABOR_LAW_SOURCES),
        retriever.search(vat_q, top_k=5, source_filter=LegalDocumentRetriever.VAT_LAW_SOURCES),
        retriever.search(privacy_q, top_k=5, source_filter=LegalDocumentRetriever.PRIVACY_LAW_SOURCES),
        retriever.search(accessibility_q, top_k=5, source_filter=LegalDocumentRetriever.ACCESSIBILITY_LAW_SOURCES),
        retriever.search(sewage_q, top_k=5, source_filter=LegalDocumentRetriever.SEWAGE_LAW_SOURCES),
        retriever.search(fair_trade_q, top_k=5, source_filter=LegalDocumentRetriever.FAIR_TRADE_SOURCES),
        # 판례 검색 (4개)
        law_client.search_precedents("가맹사업", display=3),
        law_client.search_precedents("권리금", display=3),
        law_client.search_precedents("식품위생", display=3),
        law_client.search_precedents("다중이용업소", display=3),
        # FTC API — RAG docs 불필요, Phase 1에서 선행 실행
        check_ftc_franchise(state),
    )

    # Phase 2: LLM check 함수 12개 병렬 실행 (Phase 1 결과 docs 전달)
    (
        franchise_risk,
        lease_risk,
        food_risk,
        safety_risk,
        building_risk,
        fire_risk,
        labor_risk,
        vat_risk,
        privacy_risk,
        accessibility_risk,
        sewage_risk,
        fair_trade_risk,
    ) = await asyncio.gather(
        check_franchise_law(state, franchise_docs + franchise_prec),
        check_commercial_lease_law(state, lease_docs + lease_prec),
        check_food_hygiene(state, food_docs + food_prec),
        check_safety_regulation(state, safety_docs + safety_prec),
        check_building_law(state, building_docs),
        check_fire_safety_law(state, fire_docs),
        check_labor_law(state, labor_docs),
        check_vat_law(state, vat_docs),
        check_privacy_law(state, privacy_docs),
        check_accessibility_law(state, accessibility_docs),
        check_sewage_law(state, sewage_docs),
        check_fair_trade_law(state, fair_trade_docs),
    )

    risks = [
        franchise_risk,
        lease_risk,
        zoning_result,
        food_risk,
        safety_risk,
        ftc_result,
        building_risk,
        fire_risk,
        labor_risk,
        vat_risk,
        privacy_risk,
        accessibility_risk,
        sewage_risk,
        fair_trade_risk,
    ]

    precedents = franchise_prec + lease_prec + food_prec + safety_prec
    legal_info = (legal_info_docs + precedents) or [
        {"content": r["summary"], "metadata": {"source": r["type"], "relevance": 1.0}} for r in risks
    ]

    analysis = dict(state.get("analysis_results") or {})
    analysis["legal_risks"] = risks

    # Redis 캐시 저장 — 다음 동일 요청 시 즉시 반환
    if _redis is not None:
        try:
            await _redis.set(
                cache_key,
                json.dumps({"legal_risks": risks, "legal_info": legal_info}, ensure_ascii=False),
                ex=_CACHE_TTL,
            )
            print(f"[legal_node] 캐시 저장: {cache_key} (TTL: {_CACHE_TTL}s)")
        except Exception as e:
            print(f"[legal_node] Redis 캐시 저장 실패 (무시하고 계속): {e}")
        finally:
            await _redis.aclose()

    return {**state, "analysis_results": analysis, "legal_info": legal_info}


def legal_node(state) -> dict:
    """
    법규검토 Agent 메인 노드 — LangGraph에서 호출되는 진입점.

    2단계 풀 파이프라인(_run_legal_pipeline)을 동기 컨텍스트에서 실행.
    Pydantic AgentState / TypedDict AgentState 양쪽 모두 지원.

    파이프라인:
      Phase 1: RAG×13 + 판례×4 + FTC API + zoning 병렬 (총 18개 I/O)
      Phase 2: LLM check×12 병렬
    """
    if not isinstance(state, dict):
        state = state.model_dump()
    return _run_async(_run_legal_pipeline(state))


# graph.py(B1) 호환성 별칭
legal_analyst_node = legal_node
