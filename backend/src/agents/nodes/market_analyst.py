from src.schemas.state import AgentState, MarketData
from src.config.settings import settings
from src.agents.llms import get_fast_llm
from src.agents.tools import MarketDataTool
from src.database.postgres import PostgresClient
from langchain_core.messages import SystemMessage, HumanMessage

# DB 클라이언트 및 툴 초기화 (싱글톤 패턴 권장)
db_client = PostgresClient(settings.postgres_url)
market_tool = MarketDataTool(db_client)

async def market_analyst_node(state: AgentState) -> dict:
    """
    상권 분석 에이전트:
    - 실데이터 Binding: tools.py를 통해 DB에서 경쟁사, 유동인구, 매출, 임대료 데이터 수집
    - 통계적 요약본 기반 Gemini 3 Flash 분석 생성
    """
    target_district = state.get("target_district", "서교동")
    business_type = state.get("business_type", "카페")
    
    print(f"--- [MARKET ANALYST] {target_district} 실데이터 분석 시작 ---")

    # [1] DB 연결 (필요 시)
    if db_client.engine is None:
        await db_client.connect()

    # [2] 실데이터 수집 (MarketDataTool 사용)
    # 실제 상권 분석 시에는 좌표 정보가 필요하므로 state에서 가져오거나 기본값 사용
    lat = state.get("market_data", {}).get("lat", 37.5565) # 홍대입구 기본값
    lon = state.get("market_data", {}).get("lng", 126.9239)

    # 병렬 데이터 수집 (속도 최적화)
    import asyncio
    pop_task = market_tool.get_population_trends(target_district)
    sales_task = market_tool.get_commercial_insights(target_district, business_type)
    comp_task = market_tool.get_competitor_stats(lat, lon, business_type) # industry_code 매핑 필요
    rent_task = market_tool.get_rent_insight(target_district)

    pop_data, sales_data, comp_data, rent_data = await asyncio.gather(
        pop_task, sales_task, comp_task, rent_task
    )

    # 데이터 통합 및 통계 요약 생성
    real_market_data: MarketData = {
        "district": target_district,
        "lat": lat,
        "lng": lon,
        "floating_population": {
            "total": pop_data.get("current_pop", 0),
            "trend": pop_data.get("summary", ""),
            "qoq_growth": pop_data.get("qoq_growth")
        },
        "competition_score": comp_data.get("competitor_count", 0) / 100, # 단순 점수화
        "average_rent": rent_data.get("avg_rent_3_3m2", 0),
        "sales_insight": sales_data.get("statistical_summary", ""),
        "rent_status": rent_data.get("summary", ""),
        "financial_metrics": state.get("market_data", {}).get("financial_metrics", {}) # 기존 설정 유지
    }

    # [3] 전문 요약 생성 (Gemini 3 Flash 사용)
    if settings.app_mode == "DEV" and not settings.demo_mode:
        market_summary = (
            f"{target_district} 지역 상권 요약: 유동인구 {pop_data.get('current_pop'):,}명, "
            f"경쟁 {comp_data.get('competitor_count')}개소. {sales_data.get('trend')} 추세입니다. (DEV Real-Data)"
        )
    else:
        # PROD 모드: 실데이터 통계 요약을 바탕으로 페르소나 기반 분석
        prompt = (
            "당신은 상권 분석 전문가이자 프랜차이즈 전략 컨설턴트입니다. "
            "아래 제공된 '실데이터 통계 요약'을 분석하여 예비 점주에게 전문가 수준의 출점 타당성 보고서를 작성하세요.\n\n"
            f"### {target_district} 실데이터 분석 요약:\n"
            f"- 유동인구: {pop_data.get('summary')}\n"
            f"- 매출 추이: {sales_data.get('statistical_summary')}\n"
            f"- 경쟁 상황: {comp_data.get('summary')}\n"
            f"- 임대료 수준: {rent_data.get('summary')}\n\n"
            "분석 지침:\n"
            "1. 수치(YoY, QoQ 등)를 언급하여 신뢰도를 높이세요.\n"
            "2. 임대료 대비 예상 매출의 적절성을 코멘트하세요.\n"
            "3. 2~3문장으로 날카롭고 전문적인 결론을 내리세요."
        )

        try:
            llm = get_fast_llm()
            response = await llm.ainvoke([
                SystemMessage(content=prompt),
                HumanMessage(content=f"{target_district}의 종합 상권 분석 리포트를 작성해줘.")
            ])
            
            if isinstance(response.content, list):
                market_summary = " ".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in response.content])
            else:
                market_summary = str(response.content)
        except Exception as e:
            print(f"!!! [MARKET ANALYST ERROR] !!! {str(e)}")
            market_summary = f"{target_district} 지역 분석: 실데이터 수집 완료되었으나 요약 생성 중 오류가 발생했습니다."

    return {
        "market_data": real_market_data,
        "analysis_results": {
            **state.get("analysis_results", {}),
            "market_summary": market_summary,
        },
        "current_agent": "market_analyst",
    }
