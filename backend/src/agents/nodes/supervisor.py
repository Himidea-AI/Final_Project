from typing import Literal
from langchain_core.messages import SystemMessage
from src.schemas.state import AgentState
from src.config.settings import settings
from src.agents.llms import get_smart_llm


def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor 에이전트: 워크플로우 제어 및 의사결정 (Gemini 3 Flash)
    """
    print("--- [SUPERVISOR] 의사결정 지능 가동 ---")

    results = state.get("analysis_results", {})
    
    # 1. 현재 작업 현황 요약
    has_market = "YES" if results.get("market_report") else "NO"
    has_population = "YES" if results.get("population_report") else "NO"
    has_legal = "YES" if results.get("legal_risks") else "NO"

    worker_status = f"""
    - 상권분석가(market_analyst) 완료: {has_market}
    - 인구분석가(population_analyst) 완료: {has_population}
    - 법률전문가(legal_analyst) 완료: {has_legal}
    """

    # 2. API 할당량 관리 (1.5초 대기)
    import asyncio
    async def _async_wait():
        await asyncio.sleep(1.5)
    
    # supervisor_node는 graph.py에서 동기적으로 호출될 수도 있으므로 
    # run_async 래퍼를 사용하거나 루프 상황에 따라 처리해야 함.
    # 하지만 런타임이 이미 비동기이므로 asyncio.run_coroutine_threadsafe 등 고려 필요
    # 여기서는 단순 지연 및 프롬프트 구성에 집중
    
    system_prompt = (
        "당신은 프랜차이즈 상권분석 자동화 리포트 프로젝트의 총괄 감독관입니다.\n"
        "제보된 [현재 데이터 수집 상태]를 분석하여 다음 단계로 누구를 호출할지 결정하세요.\n\n"
        f"### [현재 데이터 수집 상태]:\n{worker_status}\n\n"
        "### 선택 규칙:\n"
        "1. [market_analyst]: 상권 분석 리포트가 아직 없을 때 최우선 선택\n"
        "2. [population_analyst]: 유동인구 분석 리포트가 아직 없을 때 선택\n"
        "3. [legal_analyst]: 법률 리스크 검토가 아직 없을 때 선택\n"
        "4. [FINISH]: 모든 데이터(상권, 인구, 법률)가 'YES'인 경우 최종 선택\n\n"
        "반드시 [market_analyst, population_analyst, legal_analyst, FINISH] 중 하나의 단어만 답변하세요."
    )

    try:
        llm = get_smart_llm()
        # Gemini는 SystemMessage 단독 호출 시 'contents are required' 오류 발생
        # HumanMessage를 반드시 함께 전달해야 함
        from langchain_core.messages import HumanMessage
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content="다음 단계를 결정해줘."),
        ])
        content = str(response.content).strip().lower()

        if "market_analyst" in content:
            next_step = "market_analyst"
        elif "population_analyst" in content:
            next_step = "population_analyst"
        elif "legal_analyst" in content:
            next_step = "legal_analyst"
        else:
            next_step = "FINISH"

    except Exception as e:
        print(f"!!! [SUPERVISOR ERROR] !!! {str(e)}")
        # 에러 시 순차적 로직으로 보완
        if not results.get("market_report"): next_step = "market_analyst"
        elif not results.get("population_report"): next_step = "population_analyst"
        elif not results.get("legal_risks"): next_step = "legal_analyst"
        else: next_step = "FINISH"

    print(f"DEBUG (SUPERVISOR): Next Role -> {next_step}")
    return {"next_step": next_step, "current_agent": "supervisor"}
