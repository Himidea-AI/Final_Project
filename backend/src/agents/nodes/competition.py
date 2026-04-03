"""
경쟁분석 Agent — 직접경쟁 + 카니발리제이션 + 간접경쟁(대체재) 분석

Phase 2: 미로피쉬 디지털 트윈 도입
- 망원1동 타겟일 경우, 로컬 Ollama (Qwen-3.5 9B) 모델을 호출하여 가상의 경쟁 점주 AI의 창발적 적대 행동을 시뮬레이션함.
"""
from datetime import datetime
import json
import httpx
import asyncio
from src.agents.state import AgentState, AnalysisResults

def log_agent(agent_name: str, status: str, message: str) -> None:
    """공통 Agentic Logging 함수 (미로피쉬 흐름 모니터링)"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{agent_name} ({status})] - {message}")

async def ask_ollama_local(prompt: str) -> str:
    """로컬 Ollama 모델에게 직접 질의하는 비동기 브릿지"""
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen3.5:0.8b",
        "system": (
            "너는 망원동에서 10년 넘게 카페를 운영한 베테랑 사장님이야. IT 용어나 번역체는 절대 쓰지 마.\n\n"
            "[답변 가이드라인]\n"
            "1. 생각하는 과정 서술이나 영어 문장을 일절 생략하고, 즉시 한국어 구어체 답변만 짧게 말해.\n"
            "2. '계약발샵', '카팡가' 같은 없는 단어는 절대 쓰지 마.\n"
            "3. 실제 장사꾼들이 쓰는 '단골', '할인', '홍보', '입소문' 같은 단어만 사용해.\n\n"
            "[말투 예시 - 반드시 이 톤을 따라할 것]\n"
            "- '옆집에 저가 커피 들어오면 우리도 당분간 아침마다 1+1 쿠폰 뿌려야지 뭐.'\n"
            "- '인테리어를 좀 바꿔볼까? 망원동 감성에 맞춰서 로컬 작가들 전시라도 열어봐야겠어.'\n"
            "- '데이터고 뭐고 일단 우리 집 원두 맛부터 다시 잡아보는 게 상책이야.'"
        ),
        "prompt": prompt,
        "stream": False
    }
    
    # 기본 응답(LLM이 꺼져있을 경우 대비 Fallback)
    fallback_response = "저가 공세로 대응하겠습니다."
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=300.0)
            if response.status_code == 200:
                result = response.json()
                return result.get("response", fallback_response).strip()
            else:
                return fallback_response
    except Exception as e:
        log_agent("MiroFishAdapter", "ERROR", f"Ollama 연결 실패. LLM이 켜져있지 않음. (사유: {str(e)})")
        return fallback_response

async def _simulate_digital_twin_mangwon(business_type: str) -> str:
    """미로피쉬 쇼규모 테스트: 망원1동 경쟁자 AI의 창발적 동적 반응 시뮬레이션"""
    log_agent("MiroFishAdapter", "THINKING", "망원1동 미로피쉬 디지털 트윈 시뮬레이션 환경(Ollama Qwen-3.5-0.8B)을 초기화합니다.")
    
    # 가상의 에이전트 2명: A(저가형 프랜차이즈 사장), B(인스타 감성 개인카페/음식점 사장)
    prompt_a = (
        f"You are the owner of a low-cost franchise store in Mangwon 1-dong. "
        f"A new '{business_type}' store just opened nearby. "
        f"What is your immediate, aggressive marketing strategy? Provide your FINAL answer directly in ONE short Korean sentence starting with '[발화]'. No English, no thinking process."
    )
    prompt_b = (
        f"You are the owner of a hip boutique store in Mangwon 1-dong. "
        f"A new '{business_type}' store just opened nearby. "
        f"How will you keep your regular customers? Provide your FINAL answer directly in ONE short Korean sentence starting with '[발화]'. No English, no thinking process."
    )
    
    log_agent("Competitor_Agent_A", "TOOL_CALL", "프랜차이즈 점주의 반응을 시뮬레이션 중 초경량 0.8B...")
    response_a = await ask_ollama_local(prompt_a)
    log_agent("Competitor_Agent_A", "SUCCESS", f"발화: \"{response_a}\"")
    
    log_agent("Competitor_Agent_B", "TOOL_CALL", "개인 매장 점주의 반응을 시뮬레이션 중 초경량 0.8B...")
    response_b = await ask_ollama_local(prompt_b)
    log_agent("Competitor_Agent_B", "SUCCESS", f"발화: \"{response_b}\"")
    
    summary = f"[디지털트윈 경고] 망원1동 기존 상권의 강한 방어가 예상됩니다.\n- 저가매장 대응: {response_a}\n- 감성매장 대응: {response_b}"
    return summary

def competition_node(state: AgentState) -> AgentState:
    """
    경쟁분석 Agent 메인 노드 — LangGraph에서 호출되는 진입점
    Phase 2 미로피쉬 어댑터 로직을 포함.
    (주의: StateGraph의 노드는 동기/비동기 모두 지원하지만 현재 설계상 동기 래퍼로 작성)
    """
    if "망원1동" in getattr(state, "target_district", state.get("target_district") if isinstance(state, dict) else ""):
        log_agent("CompetitionNode", "THINKING", "타겟이 '망원1동'입니다. 미로피쉬 로컬 트윈을 가동합니다.")
        # Async 함수를 실행하기 위한 이벤트 루프 처리
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        b_type = getattr(state, "business_type", state.get("business_type") if isinstance(state, dict) else "카페")
        micro_sim_result = loop.run_until_complete(_simulate_digital_twin_mangwon(b_type))
        
        # State에 결과 반영
        # state의 analysis_results가 없을 수 있으므로 초기화 방어
        if isinstance(state, dict):
            if not state.get("analysis_results"):
                state["analysis_results"] = AnalysisResults()
            state["analysis_results"].cannibalization_impact = {
                "mirofish_twin_summary": micro_sim_result,
                "threat_level": "High"
            }
        else:
            if not state.analysis_results:
                state.analysis_results = AnalysisResults()
            state.analysis_results.cannibalization_impact = {
                "mirofish_twin_summary": micro_sim_result,
                "threat_level": "High"
            }
    else:
        log_agent("CompetitionNode", "THINKING", "망원1동 외의 지역입니다. 기본 정량적 경쟁 지수를 계산합니다(더미).")
        if isinstance(state, dict):
            if not state.get("analysis_results"):
                state["analysis_results"] = AnalysisResults()
            state["analysis_results"].cannibalization_impact = {
                "threat_level": "Medium"
            }
        else:
            if not state.analysis_results:
                state.analysis_results = AnalysisResults()
            state.analysis_results.cannibalization_impact = {
                "threat_level": "Medium"
            }
        
    log_agent("CompetitionNode", "SUCCESS", "경쟁/카니발리제이션 분석 노드 처리를 완료했습니다.")
    return state
