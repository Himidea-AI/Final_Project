import asyncio
import json
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.state import AgentState
from src.schemas.structured_output import FinalStrategyResult
from src.agents.llms import get_fast_llm

async def synthesis_node(state: AgentState) -> dict:
    """
    최종 합성 에이전트 (Synthesis Agent):
    - [데이터 보존] legal_node가 생성한 14개 법률 리스크 데이터를 절대 훼손하지 않고 그대로 유지합니다.
    - 상권 분석, 유동인구 분석, 법률 검토 결과를 종합하여 최종 창업 전략 리포트를 생성합니다.
    - FinalStrategyResult 스키마에 맞춰 정형화된 JSON 데이터를 생성합니다.
    """
    print("--- [SYNTHESIS] 최종 전략 합성 및 데이터 검증 시작 ---")
    
    # 1. 데이터 추출 (기존 에이전트들의 결과물)
    analysis_results = state.get("analysis_results", {})
    market_report = analysis_results.get("market_report", "상권 분석 정보 없음")
    population_report = analysis_results.get("population_report", "인구 분석 정보 없음")
    
    # [중요] 14개의 법률 리스크 데이터 (절대 보존)
    legal_risks = analysis_results.get("legal_risks", [])
    overall_legal_risk = state.get("overall_legal_risk", "Caution")
    
    brand_name = state.get("brand_name", "미지정 브랜드")
    business_type = state.get("business_type", "카페")
    target_district = state.get("target_district", "마포구")
    
    # 2. LLM 합성용 컨텍스트 구성
    legal_summary_for_llm = "\n".join([
        f"- {r.get('type', '미분류')}: {r.get('level', 'Normal')} (요약: {r.get('summary', '')[:100]}...)" 
        for r in legal_risks
    ])

    prompt = (
        "당신은 프랜차이즈 창업 전략 수석 컨설턴트입니다. "
        "지금까지 수집된 상권, 인구, 법률 데이터를 종합하여 예비 점주를 위한 최종 전략 리포트를 작성하세요.\n\n"
        f"### [분석 대상 데이터]\n"
        f"1. 브랜드: {brand_name} ({business_type})\n"
        f"2. 대상 지역: {target_district}\n"
        f"3. 상권 분석 요약: {market_report[:500]}\n"
        f"4. 유동인구 분석 요약: {population_report[:500]}\n"
        f"5. 법률 리스크 검토 결과 (14개 항목):\n{legal_summary_for_llm}\n\n"
        "### 요구사항:\n"
        "1. 모든 데이터를 종합하여 신뢰할 수 있는 창업 가부를 결정하고 전략적 제언을 하십시오.\n"
        "2. 반드시 FinalStrategyResult 스키마에 맞춰 정형 데이터를 응답하십시오.\n"
        f"3. 종합 법률 리스크 등급은 반드시 '{overall_legal_risk}'를 반영하십시오.\n"
    )

    try:
        # LLM 호출 (Structured Output)
        llm = get_fast_llm().with_structured_output(FinalStrategyResult)
        
        # API 할당량 관리를 위한 미세 대기
        await asyncio.sleep(1.5)
        
        final_strategy: FinalStrategyResult = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"{brand_name}의 {target_district} 출점 최종 전략 보고서를 완성해줘.")
        ])
        
        print(f"--- [SYNTHESIS] 최종 보고서 생성 완료 (등급: {final_strategy.overall_legal_risk}) ---")

    except Exception as e:
        print(f"!!! [SYNTHESIS ERROR] !!! {str(e)}")
        # 에러 발생 시 Fallback (데이터 보존을 위한 최소 데이터 구성)
        final_strategy = FinalStrategyResult(
            summary=f"{brand_name} {target_district} 분석 결과 요약 생성 중 오류 발생",
            is_direct=False,
            brand_category="franchise",
            overall_legal_risk=overall_legal_risk,
            profit_simulation={"monthly_revenue": 0, "net_profit": 0, "margin_rate": 0.0},
            competitor_analysis={"count": 0, "density": "NORMAL"},
            final_recommendation=f"분석 중 기술적 오류가 발생했습니다: {str(e)}"
        )

    # 3. 데이터 업데이트 (기존 legal_risks를 100% 보존하며 final_report 추가)
    new_analysis_results = dict(analysis_results)
    new_analysis_results["final_report"] = final_strategy.model_dump()
    
    # [검증] legal_risks가 누락되지 않았는지 다시 한 번 확인
    if "legal_risks" not in new_analysis_results:
        new_analysis_results["legal_risks"] = legal_risks

    return {
        "analysis_results": new_analysis_results,
        "current_agent": "synthesis"
    }
