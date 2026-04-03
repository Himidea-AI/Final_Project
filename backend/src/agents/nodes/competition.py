"""
경쟁분석 Agent — 직접경쟁 + 카니발리제이션 + 간접경쟁(대체재) 분석

Phase 2: 미로피쉬 디지털 트윈 도입
- 망원1동 타겟일 경우, 로컬 Ollama (phi3) 모델을 호출하여 가상의 경쟁 점주 AI의 창발적 적대 행동을 시뮬레이션함.
"""
from datetime import datetime
import json
import httpx
import asyncio
from src.agents.state import AgentState, AnalysisResults

def log_agent(agent_name: str, status: str, message: str) -> None:
    """공통 Agentic Logging 함수 (미로피쉬 흐름 모니터링)"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{agent_name} ({status})] - {message}")

async def ask_ollama_phi3(prompt: str) -> str:
    """로컬 Ollama의 Phi-3 모델에게 직접 질의하는 비동기 브릿지"""
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "phi3",
        "system": "You are a realistic local franchise owner and a hardcore market analyst in Seoul. Answer in simple, plain Korean. Focus ONLY on realistic business survival, revenue, and marketing strategies. DO NOT use any IT jargon, code, or technology terms under any circumstances.",
        "prompt": prompt,
        "stream": False
    }
    
    # 기본 응답(LLM이 꺼져있을 경우 대비 Fallback)
    fallback_response = "저가 공세로 대응하겠습니다."
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=15.0)
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
    log_agent("MiroFishAdapter", "THINKING", "망원1동 미로피쉬 디지털 트윈 시뮬레이션 환경(Ollama-Phi3)을 초기화합니다.")
    
    # 가상의 에이전트 2명: A(저가형 프랜차이즈 사장), B(인스타 감성 개인카페/음식점 사장)
    # Phi-3 등 소형 모델의 추론 성능(특히 한국어)을 높이기 위해 프롬프트를 영어로 주고, 생각(Thought) 과정을 영어로 거친 뒤 한국어로 번역해 발화하게 합니다.
    prompt_a = (
        f"You are the owner of a low-cost franchise store in Mangwon 1-dong. "
        f"A new '{business_type}' store just opened nearby. "
        f"1. First, think step by step in English about your aggressive marketing or discount strategy to defend your sales. "
        f"2. Then, provide your final answer in ONE short Korean sentence.\n"
        f"Format:\nThought: [Your English thoughts]\nKorean Answer: [Your final Korean sentence]"
    )
    prompt_b = (
        f"You are the owner of a hip boutique store in Mangwon 1-dong. "
        f"A new '{business_type}' store just opened nearby. "
        f"1. First, think step by step in English about how to improve service and keep your regular customers. "
        f"2. Then, provide your final answer in ONE short Korean sentence.\n"
        f"Format:\nThought: [Your English thoughts]\nKorean Answer: [Your final Korean sentence]"
    )
    
    log_agent("Competitor_Agent_A", "TOOL_CALL", "프랜차이즈 점주의 반응을 시뮬레이션 중 (Phi-3 호출)...")
    response_a = await ask_ollama_phi3(prompt_a)
    log_agent("Competitor_Agent_A", "SUCCESS", f"발화: \"{response_a}\"")
    
    log_agent("Competitor_Agent_B", "TOOL_CALL", "개인 매장 점주의 반응을 시뮬레이션 중 (Phi-3 호출)...")
    response_b = await ask_ollama_phi3(prompt_b)
    log_agent("Competitor_Agent_B", "SUCCESS", f"발화: \"{response_b}\"")
    
    summary = f"[디지털트윈 경고] 망원1동 기존 상권의 강한 방어가 예상됩니다.\n- 저가매장 대응: {response_a}\n- 감성매장 대응: {response_b}"
    return summary

def competition_node(state: AgentState) -> AgentState:
    """
    경쟁분석 Agent 메인 노드 — LangGraph에서 호출되는 진입점
    Phase 2 미로피쉬 어댑터 로직을 포함.
    (주의: StateGraph의 노드는 동기/비동기 모두 지원하지만 현재 설계상 동기 래퍼로 작성)
    """
    if "망원1동" in state.target_district:
        log_agent("CompetitionNode", "THINKING", "타겟이 '망원1동'입니다. 미로피쉬 로컬 트윈을 가동합니다.")
        # Async 함수를 실행하기 위한 이벤트 루프 처리
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        micro_sim_result = loop.run_until_complete(_simulate_digital_twin_mangwon(state.business_type))
        
        # State에 결과 반영
        # state의 analysis_results가 없을 수 있으므로 초기화 방어
        if not state.analysis_results:
            state.analysis_results = AnalysisResults()
        
        state.analysis_results.cannibalization_impact = {
            "mirofish_twin_summary": micro_sim_result,
            "threat_level": "High"
        }
    else:
        log_agent("CompetitionNode", "THINKING", "망원1동 외의 지역입니다. 기본 정량적 경쟁 지수를 계산합니다(더미).")
        if not state.analysis_results:
            state.analysis_results = AnalysisResults()
        state.analysis_results.cannibalization_impact = {
            "threat_level": "Medium"
        }
        
    log_agent("CompetitionNode", "SUCCESS", "경쟁/카니발리제이션 분석 노드 처리를 완료했습니다.")
    # State 객체를 반환하거나 수정된 필드를 딕셔너리로 반환 (LangGraph 버전에 맞춰 전체 state 리턴)
    return state
