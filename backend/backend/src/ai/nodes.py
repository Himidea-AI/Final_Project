from datetime import datetime
from ..schemas.state import AgentState
from ..schemas.models import SimulationResult
from .prompts import SYSTEM_PROMPT_MARKET_ANALYSIS, SYSTEM_PROMPT_COMPETITION, SYSTEM_PROMPT_SUPERVISOR

def log_agent(agent_name: str, status: str, message: str) -> None:
    """공통 Agentic Logging 함수"""
    print(f"[{datetime.now()}] [{agent_name} ({status})] - {message}")

async def analyze_market_node(state: AgentState) -> dict:
    """상권 분석을 담당하는 노드 스켈레톤"""
    log_agent("AnalyzeMarketNode", "THINKING", f"{state.request.target_dong}의 인구 및 상권 기초 데이터를 확인합니다.")
    
    # 더미 로직 (추후 LLM 호출 및 실제 데이터 파싱 연동)
    dummy_summary = f"{state.request.target_dong} 지역은 유동인구가 많고 {state.request.business_type} 업종의 밀집도가 중간 수준입니다."
    
    log_agent("AnalyzeMarketNode", "SUCCESS", "기초 상권 분석 요약 완료.")
    
    # LangGraph에 업데이트할 상태 딕셔너리 반환 (또는 state 모델 수정 후 전체 반환)
    # 현재는 부분 업데이트 형식을 반환
    return {
        "market_analysis_summary": dummy_summary,
        "messages": state.messages + ["AnalyzeMarketNode 완료"]
    }

async def analyze_competition_node(state: AgentState) -> dict:
    """경쟁 심도(카니발리제이션)를 계산하고 분석하는 노드 스켈레톤"""
    log_agent("AnalyzeCompetitionNode", "THINKING", "경쟁점 매장 정보 및 예상 카니발리제이션 지수를 계산합니다.")
    
    dummy_comp_summary = f"해당 예산({state.request.budget}만원) 하에서 진입 시 주변 경쟁점과의 매출 간섭은 약 15%로 예상됩니다."
    
    log_agent("AnalyzeCompetitionNode", "SUCCESS", "경쟁 및 카니발리제이션 분석 완료.")
    
    return {
        "competition_analysis_summary": dummy_comp_summary,
        "messages": state.messages + ["AnalyzeCompetitionNode 완료"]
    }

async def supervisor_node(state: AgentState) -> dict:
    """분석 결과를 종합하여 최종 결과를 생성하거나 추가 분석을 지시하는 감독관 노드"""
    log_agent("SupervisorNode", "THINKING", "현재까지의 분석 내용을 기반으로 최종 검증을 수행합니다.")
    
    # 더미 판단: 분석이 모두 끝났다고 간주하고 최종 결과 도출
    log_agent("SupervisorNode", "SUCCESS", "최종 조언 및 지표 생성 완료.")
    
    final_result = SimulationResult(
        market_score=85.5,
        expected_monthly_revenue=35000000,
        bep_months=8,
        survival_rate_12m=75.2,
        strategy_recommendation="간접 경쟁이 일부 있으나 배달 비중을 30% 확보한다면 시장 안착이 수월할 것입니다."
    )
    
    return {
        "is_completed": True,
        "final_result": final_result,
        "messages": state.messages + ["SupervisorNode 완료 - 시뮬레이션 종료"]
    }
