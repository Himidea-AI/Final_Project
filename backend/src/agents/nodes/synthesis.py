import asyncio
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.state import AgentState
from src.agents.llms import get_fast_llm

async def synthesis_node(state: AgentState) -> dict:
    """
    최종 종합 분석 에이전트 (Synthesis Node):
    - 각 전문 에이전트(상권, 인구, 법률)의 개별 분석 결과물을 취합
    - 예비 점주를 위한 전문적이고 읽기 쉬운 '최종 종합 분석 보고서' 생성
    """
    print("--- [SYNTHESIS] 최종 종합 분석 보고서 작성 중 ---")

    results = state.get("analysis_results", {})
    market_report = results.get("market_report", "상권 분석 데이터 없음")
    population_report = results.get("population_report", "인구 분석 데이터 없음")
    
    # 법률 데이터 처리 (리스트 형태이므로 요약 필요)
    legal_risks = results.get("legal_risks", [])
    legal_summary = ""
    if legal_risks:
        legal_summary = "\n".join([f"- {risk.get('type')}: {risk.get('level').upper()} - {risk.get('summary')}" for risk in legal_risks])
    else:
        legal_summary = "법률 리스크 분석 데이터 없음"

    # [API Quota 관리] 2초 대기
    await asyncio.sleep(2)

    prompt = (
        "당신은 프랜차이즈 창업 전략 컨설팅 팀의 수석 리포터입니다. "
        "전문화된 각 팀(상권분석팀, 인구분석팀, 법률지원팀)의 개별 보고서를 바탕으로 "
        "예비 창업자를 위한 '최종 종합 분석 보고서'를 완성도 있게 작성하세요.\n\n"
        "### [입력 보고서 조각]\n"
        f"1. 상권 분석 결과:\n{market_report}\n\n"
        f"2. 유동인구 분석 결과:\n{population_report}\n\n"
        f"3. 법률 리스크 검토 결과:\n{legal_summary}\n\n"
        "### 작성 가이드라인:\n"
        "1. 제목은 반드시 '[최종 종합 분석 보고서]'로 시작하세요.\n"
        "2. 각 분야의 핵심 내용을 논리적으로 연결하여 결론(최종 추천 등급 및 창업 전략)을 도출하세요.\n"
        "3. 프랜차이즈 직원이 점주에게 직접 브리핑하는 것처럼 신뢰감 있고 전문적인 어조를 사용하세요.\n"
        "4. 마크다운(Markdown) 포맷을 사용하여 가독성을 높이세요."
    )

    try:
        llm = get_fast_llm()
        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"{state.get('target_district')} {state.get('brand_name', '해당 브랜드')} 창업 시뮬레이션 최종 보고서를 작성해줘.")
        ])
        
        final_report = str(response.content)
        
    except Exception as e:
        print(f"!!! [SYNTHESIS ERROR] !!! {str(e)}")
        # 에러 시 수동 병합
        final_report = (
            f"# [최종 종합 분석 보고서] - {state.get('target_district')}\n\n"
            f"## 1. 상권 및 매출 분석\n{market_report}\n\n"
            f"## 2. 유동인구 분석\n{population_report}\n\n"
            f"## 3. 법률 및 규제 리스크\n{legal_summary}\n\n"
            "⚠️ 분석 결과 생성 중 일부 오류가 발생하여 원본 데이터를 병합하여 제공합니다."
        )

    # 최종 결과물 업데이트 (analysis_results["market_summary"]는 기존 main.py와의 호환성을 위해 사용됨)
    results["market_summary"] = final_report

    return {
        "analysis_results": results,
        "current_agent": "synthesis"
    }
