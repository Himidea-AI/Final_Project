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

import requests

def ask_ollama_local(prompt: str) -> str:
    """로컬 Ollama 모델에게 직접 질의하는 동기 브릿지"""
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "qwen3.5:9b",
        "system": (
            "너는 마포구 망원동 상권에서 10년 넘게 살아남은 베테랑 카페 사장님이다. IT/테크 용어는 철저하게 배제하시오.\n\n"
            "[답변 가이드라인]\n"
            "1. 생각하는 과정은 영어(Thought)로 작성하여 치밀하게 논리를 세우되, 출력(Korean Answer)은 반드시 쫀득한 한국어 구어체로 답해라.\n"
            "2. '단골', '할인', '홍보', '입소문', '원두 맛', '전시회', '바가지' 등 실제 장사꾼들이 쓰는 살아있는 단어만 구사할 것.\n"
            "3. '계약발사', '카팡가' 등 AI 특유의 알 수 없는 외계어(Hallucination)는 엄격히 금지함.\n"
            "4. 장황하게 설명하지 말고, 딱 하나의 날카로운 현실적 '대응 행동(Action)'만을 1~2문장으로 내뱉어라.\n\n"
            "[말투 예시 - 반드시 이 톤을 준수할 것]\n"
            "- '옆집에 저가 커피 들어오면 우리도 당분간 아침마다 1+1 쿠폰 뿌려야지 뭐.'\n"
            "- '인테리어를 좀 바꿔볼까? 망원동 감성에 맞춰서 로컬 작가들 전시라도 열어봐야겠어.'\n"
            "- '데이터고 뭐고 일단 우리 집 원두 맛부터 다시 잡아보는 게 상책이야.'"
        ),
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 300,
            "temperature": 0.7
        }
    }
    
    fallback_response = "저가 공세로 대응하겠습니다."
    
    try:
        response = requests.post(url, json=payload, timeout=600.0)
        if response.status_code == 200:
            result = response.json()
            return result.get("response", fallback_response).strip()
        else:
            return fallback_response
    except Exception as e:
        log_agent("MiroFishAdapter", "ERROR", f"Ollama 연결 실패. LLM이 켜져있지 않음. (사유: {str(e)})")
        return fallback_response

def _simulate_digital_twin_mangwon(business_type: str) -> str:
    """미로피쉬 쇼규모 테스트: 망원1동 경쟁자 AI의 창발적 동적 반응 시뮬레이션"""
    log_agent("MiroFishAdapter", "THINKING", "망원1동 미로피쉬 디지털 트윈 시뮬레이션 환경(Ollama Qwen-3.5-9B)을 초기화합니다.")
    
    # 가상의 에이전트 2명: A(저가형 프랜차이즈 사장), B(인스타 감성 개인카페/음식점 사장)
    prompt_a = (
        f"Target: 망원1동 저가형 프랜차이즈 소상공인.\n"
        f"Event: A new '{business_type}' store just opened right next to your cafe.\n"
        f"1. First, Think step by step in English about your aggressive marketing or discount strategies to protect your revenue.\n"
        f"2. Then, provide your final answer in ONE short Korean sentence spoken like a real street-smart business owner.\n"
        f"Format:\nThought: [Your English thoughts]\n[발화] [Your final Korean sentence]"
    )
    prompt_b = (
        f"Target: 망원1동 감성 개인 매장(로스터리/디저트) 사장님.\n"
        f"Event: A new '{business_type}' store just opened right next to your cafe.\n"
        f"1. First, Think step by step in English about how to improve interior/service and retain your regular customers.\n"
        f"2. Then, provide your final answer in ONE short Korean sentence spoken like a real street-smart business owner.\n"
        f"Format:\nThought: [Your English thoughts]\n[발화] [Your final Korean sentence]"
    )
    
    log_agent("Competitor_Agent_A", "TOOL_CALL", "프랜차이즈 점주의 반응을 시뮬레이션 중 (Qwen 9B)...")
    response_a = ask_ollama_local(prompt_a)
    log_agent("Competitor_Agent_A", "SUCCESS", f"발화: \"{response_a}\"")
    
    log_agent("Competitor_Agent_B", "TOOL_CALL", "개인 매장 점주의 반응을 시뮬레이션 중 (Qwen 9B)...")
    response_b = ask_ollama_local(prompt_b)
    log_agent("Competitor_Agent_B", "SUCCESS", f"발화: \"{response_b}\"")
    
    summary = f"[디지털트윈 경고] 망원1동 기존 상권의 강한 방어가 예상됩니다.\n- 저가매장 대응: {response_a}\n- 감성매장 대응: {response_b}"
    return summary

def competition_node(state: AgentState) -> AgentState:
    """
    경쟁분석 Agent 메인 노드 — LangGraph에서 호출되는 진입점
    Phase 2 미로피쉬 어댑터 로직을 포함.
    """
    if "망원1동" in getattr(state, "target_district", state.get("target_district") if isinstance(state, dict) else ""):
        log_agent("CompetitionNode", "THINKING", "타겟이 '망원1동'입니다. 미로피쉬 로컬 트윈을 가동합니다.")
            
        b_type = getattr(state, "business_type", state.get("business_type") if isinstance(state, dict) else "카페")
        micro_sim_result = _simulate_digital_twin_mangwon(b_type)
        
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
