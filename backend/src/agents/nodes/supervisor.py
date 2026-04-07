from typing import Literal
from langchain_core.messages import SystemMessage
from src.schemas.state import AgentState
from src.config.settings import settings
from src.agents.llms import get_fast_llm


def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor 에이전트: 워크플로우 제어 및 의사결정 담당 (Gemini 3 Flash 사용)
    """
    print("--- [SUPERVISOR] 의사결정 중 ---")

    if settings.app_mode == "DEV":
        # Mock 의사결정 (기존 로직 유지)
        if not state.get("market_data"):
            next_step = "market_analyst"
        elif not state.get("legal_info"):
            next_step = "legal_analyst"
        else:
            next_step = "FINISH"
        print(f"DEBUG (DEV): Supervisor 시나리오 진행 -> {next_step}")
    else:
        # PROD 모드: Gemini 3 Flash가 실시간 판단
        # 현재 상태 파악
        has_market_data = "YES" if state.get("market_data") else "NO"
        has_legal_info = "YES" if state.get("legal_info") else "NO"

        system_prompt = (
            "당신은 마포구 프랜차이즈 시뮬레이터의 오케스트레이터입니다. "
            "현재까지 수집된 데이터 상태를 보고 다음 수행할 노드를 하나 고르세요.\n\n"
            f"### 현재 데이터 수집 상태:\n"
            f"- 상권 데이터 수집 완료: {has_market_data}\n"
            f"- 법률 데이터 수집 완료: {has_legal_info}\n\n"
            "### 선택 규칙:\n"
            "1. 상권 데이터가 'NO'이면: [market_analyst]를 선택하세요.\n"
            "2. 상권 데이터가 'YES'이고 법률 데이터가 'NO'이면: [legal_analyst]를 선택하세요.\n"
            "3. 모든 데이터가 'YES'이면: [FINISH]를 선택하세요.\n\n"
            "반드시 위 리스트 중 하나의 단어만 답변하세요."
        )

        messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
        try:
            llm = get_fast_llm()
            response = llm.invoke(messages)
            
            # Gemini 3 Flash can return content as a list or string
            if isinstance(response.content, list):
                content = " ".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in response.content])
            else:
                content = str(response.content)
            
            content = content.strip().lower()

            if "market_analyst" in content:
                next_step = "market_analyst"
            elif "legal_analyst" in content:
                next_step = "legal_analyst"
            else:
                next_step = "FINISH"
        except Exception as e:
            print(f"!!! [SUPERVISOR ERROR] !!! {str(e)}")
            # 에러 발생(쿼터 초과 등) 시에도 상태 필드를 보고 수동으로 다음 단계 결정
            if not state.get("market_data"):
                next_step = "market_analyst"
            elif not state.get("legal_info"):
                next_step = "legal_analyst"
            else:
                next_step = "FINISH"

        print(f"DEBUG (PROD): Gemini Flash Decision -> {next_step}")

    return {"next_step": next_step, "current_agent": "supervisor"}
