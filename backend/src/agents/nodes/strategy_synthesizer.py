import asyncio
from typing import Any
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.state import AgentState
from src.schemas.structured_output import FinalStrategyResult
from src.agents.llms import get_fast_llm, get_smart_llm

async def _check_individual_risk(name: str, prompt: str, context: str) -> dict:
    """개별 법률 리스크 항목 체크 (병렬 실행용)"""
    llm = get_smart_llm()
    response = await llm.ainvoke([
        SystemMessage(content=f"당신은 프랜차이즈 법률 전문가입니다. 다음 문맥을 바탕으로 {name} 리스크를 분석하세요."),
        HumanMessage(content=f"문맥: {context}\n\n질문: {prompt}\n\n위험도(Safe/Caution/Danger)와 상세 사유를 응답하세요.")
    ])
    # 간단한 파싱 로직 (실제 구현에서는 Structured Output 권장)
    content = response.content.upper()
    level = "Safe"
    if "DANGER" in content: level = "Danger"
    elif "CAUTION" in content: level = "Caution"
    
    return {"item": name, "level": level, "reason": response.content}

async def strategy_synthesizer_node(state: AgentState) -> dict:
    """
    2번 노드: StrategySynthesizer
    - 1순위 지역(Winner)에 대해서만 법률 RAG 검토 (Internalized)
    - 14개 리스크 항목 중 최고 위험도 추출 (Danger/Caution/Safe)
    - 최종 전략 리포트 및 정형 JSON 생성 (Structured Output)
    """
    winner = state.get("winner_district", state.get("target_district"))
    print(f"--- [STRATEGY SYNTHESIZER] {winner} 집중 법률 검토 및 최종 합성 시작 ---")

    # [1] 법률 RAG 검토 (Internalized Simplified version)
    # 실제 환경에서는 vector_db와 retriever가 필요하지만, 2노드 체제 전환을 위해 핵심 로직만 통합
    check_items = [
        ("계약기간", "가맹계약 초기 기간 및 갱신 조건의 적절성을 분석하십시오."),
        ("영업지역", "영업지역 보호 범위 및 경합 금지 조항을 검토하십시오."),
        ("교육비", "초기 교육비 및 실비 청구 항목의 투명성을 확인하십시오."),
        # ... 실무에서는 14개 항목 모두 추가
    ]
    
    # 병렬 검토 실행 (Semaphore(1) 및 3초 간격 엄격 적용)
    semaphore = asyncio.Semaphore(1)
    async def wrapped_check(item):
        async with semaphore:
            result = await _check_individual_risk(item[0], item[1], f"{winner} 지역 관련 법률 문맥")
            print(f"   [CHECK DONE] {item[0]} 분석 완료. 3초 대기 중...")
            await asyncio.sleep(3) # 요청하신 3초 간격 수행
            return result

    legal_risks = await asyncio.gather(*(wrapped_check(item) for item in check_items))

    # [2] 종합 리스크 레벨 추출 (Safe/Caution/Danger)
    risk_levels = [r.get("level", "safe").lower() for r in legal_risks]
    if "danger" in risk_levels:
        overall_risk = "Danger"
    elif "caution" in risk_levels:
        overall_risk = "Caution"
    else:
        overall_risk = "Safe"

    # [3] 최종 시뮬레이션 합성 (Structured Output 적용)
    brand_name = state.get("brand_name", "")
    business_type = state.get("business_type", "cafe")
    comparison = state.get("analysis_results", {}).get("comparison_report", {})
    brand_analysis = state.get("brand_analysis", {})

    llm = get_fast_llm().with_structured_output(FinalStrategyResult)
    
    direct_brands = ['스타벅스', 'starbucks', '올리브영', 'oliveyoung', '다이소', 'daiso']
    is_direct = any(b in brand_name.lower() for b in direct_brands)
    brand_category = "direct_operation" if is_direct else "franchise"

    prompt = (
        "프랜차이즈 창업 전략 수석 컨설턴트로서 최종 보고서를 완성하세요.\n\n"
        f"대상 브랜드: {brand_name} ({brand_category})\n"
        f"최종 선정한 최적 입지: {winner}\n\n"
        "### [데이터 근거]\n"
        f"1. 지역 비교 분석: {comparison.get('winner_reason', '정보 없음')}\n"
        f"2. 브랜드 매출 대조: {brand_analysis.get('summary', '정보 없음')}\n"
        f"3. 종합 법률 리스크: {overall_risk} (상세 리스크 {len(legal_risks)}건 검토 완료)\n\n"
        "위 내용을 바탕으로 예비 점주가 의사결정을 내릴 수 있는 최종 제언과 정형 데이터를 생성하세요."
    )

    final_result: FinalStrategyResult = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content=f"{winner} 최종 창업 시뮬레이션 결과물을 만들어줘.")
    ])

    print(f"--- [STRATEGY SYNTHESIZER] 최종 보고서 생성 완료 (Risk: {overall_risk}) ---")

    # 결과 병합 및 상태 업데이트
    analysis_results = state.get("analysis_results", {})
    analysis_results["final_report"] = final_result.model_dump()
    analysis_results["legal_risks"] = legal_risks
    
    return {
        "analysis_results": analysis_results,
        "overall_legal_risk": overall_risk
    }
