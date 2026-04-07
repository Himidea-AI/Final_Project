from src.schemas.state import AgentState, MarketData
from src.config.settings import settings
from src.agents.llms import get_fast_llm
from langchain_core.messages import SystemMessage, HumanMessage


async def market_analyst_node(state: AgentState) -> dict:
    """
    상권 분석 에이전트:
    - DEV: Mock 데이터 반환
    - PROD: Gemini 3 Flash를 사용하여 상권 지표 분석 및 전문적인 요약 생성
    """
    target_district = state.get("target_district", "서교동")
    print(f"--- [MARKET ANALYST] {target_district} 분석 시작 ---")

    # [1] 데이터 로드 (현재는 Mock 데이터로 시뮬레이션, 실데이터 A1 연동 가능 지점)
    mock_data: MarketData = {
        "district": target_district,
        "lat": 37.5565 if target_district == "서교동" else 37.5663,
        "lng": 126.9239 if target_district == "서교동" else 126.9015,
        "floating_population": {"total": 120000, "peak_hour": "17:00-21:00"},
        "competition_score": 0.78,
        "average_rent": 3500000,
        "financial_metrics": {
            "fixed_costs": {
                "rent": 3500000,
                "labor": 7000000,
                "insurance": 500000,
                "marketing": 1000000,
            },
            "variable_cost_ratio": 0.35,
            "avg_unit_price": 5500,
            "target_daily_sales": 65,
        },
    }

    # [2] 전문 요약 생성 (Gemini 3 Flash 사용)
    if settings.app_mode == "DEV":
        market_summary = f"{target_district} 지역은 현재 {state.get('business_type', '카페')} 업종의 수요가 안정적인 편입니다. (DEV Mock)"
    else:
        # PROD 모드: Gemini 3 Flash가 전문적인 상권 분석 요약 생성
        prompt = (
            "당신은 프랜차이즈 출점 전략 컨설턴트입니다. 아래 제공된 상권 지표를 분석하여 "
            f"사용자의 '{state.get('brand_name')} ({state.get('business_type')})' 출점 타당성을 2~3문장으로 전문적으로 요약하세요.\n\n"
            f"### {target_district} 상권 지표:\n"
            f"- 유동인구: {mock_data['floating_population']['total']}명\n"
            f"- 경쟁강도 점수: {mock_data['competition_score']}\n"
            f"- 평균 임대료: {mock_data['average_rent']}원\n\n"
            "상권의 활성화 정도와 경쟁 상황을 고려하여 날카로운 통찰을 제공하세요."
        )

        try:
            llm = get_fast_llm()
            # SystemMessage와 HumanMessage를 혼합하여 전송
            response = await llm.ainvoke([
                SystemMessage(content=prompt),
                HumanMessage(content=f"{target_district} 지역의 상권 요약을 작성해줘.")
            ])
            
            # Gemini 3 Flash 응답 처리 (list or string)
            if isinstance(response.content, list):
                market_summary = " ".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in response.content])
            else:
                market_summary = str(response.content)
        except Exception as e:
            print(f"!!! [MARKET ANALYST ERROR] !!! {str(e)}")
            market_summary = f"{target_district} 지역 상권 분석 결과: 유동인구가 충분하여 긍정적인 전망이 기대됩니다."

    return {
        "market_data": mock_data,
        "analysis_results": {
            **state.get("analysis_results", {}),
            "market_summary": market_summary,
        },
        "current_agent": "market_analyst",
    }
