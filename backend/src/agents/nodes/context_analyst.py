import asyncio
from typing import List, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.state import AgentState
from src.schemas.structured_output import Top3ComparisonReport
from src.agents.llms import get_fast_llm
from src.agents.tools import MarketDataTool
from src.database.postgres import PostgresClient
from src.config.settings import settings
from src.config.constants import MAPO_DISTRICTS
from src.services.ftc_franchise import FtcFranchiseClient

# 싱글톤 인스턴스 (필요 시 가동)
db_client = PostgresClient(settings.postgres_url)
market_tool = MarketDataTool(db_client)
ftc_client = FtcFranchiseClient(api_key=settings.ftc_api_key)

async def context_analyst_node(state: AgentState) -> dict:
    """
    1번 노드: ContextAnalyst
    - 마포구 16개 행정동 전수 조사 (Python Scouting)
    - 브랜드 전국 데이터 대조 (FTC API)
    - LLM 기반 Top 3 비교 분석 및 최종 Winner 선정 (Structured Output)
    """
    print("--- [CONTEXT ANALYST] 마포구 전수 스카우팅 및 지역 대조 분석 시작 ---")
    
    business_type = state.get("business_type", "cafe")
    brand_name = state.get("brand_name", "")
    industry_code = {"cafe": "Q01A01", "restaurant": "Q01A02", "convenience": "Q02A01"}.get(business_type, "Q01A01")

    # [1] Python 스카우팅: 16개동 정량적 점수 산출
    scouting_tasks = []
    for dong in MAPO_DISTRICTS:
        scouting_tasks.append(_scout_district(dong, business_type, industry_code))
    
    scouting_results = await asyncio.gather(*scouting_tasks)
    
    # 점수 기준 내림차순 정렬 후 Top 3 선별
    sorted_results = sorted(scouting_results, key=lambda x: x["score"], reverse=True)
    top_3 = sorted_results[:3]
    top_3_names = [r["district"] for r in top_3]

    # [2] 브랜드 전국 매출 비교 (ftc_franchise.py - dev 고도화 버전 적용)
    # Top 1 지역의 행정동명과 브랜드 전국 데이터를 DB 세션 기반으로 대조
    async with db_client.get_session() as session:
        brand_comp_result = await ftc_client.compare_brand_to_district(
            brand_name, 
            top_3[0]["district"], 
            session
        )

    # [3] LLM 심층 비교 분석 (Structured Output 적용)
    llm = get_fast_llm().with_structured_output(Top3ComparisonReport)
    
    prompt = (
        "당신은 프랜차이즈 입지 선정 전문가입니다. 파이썬 스카우팅으로 선별된 상위 3개 지역의 데이터를 근거로 "
        f"'{brand_name}' 브랜드의 최적 출점지를 비교 분석하고 최종 1순위(Winner)를 확정하세요.\n\n"
        "### [스카우팅 데이터]\n"
    )
    for i, res in enumerate(top_3):
        prompt += f"{i+1}. {res['district']}: 점수={res['score']} (매출성장={res['sales_growth']}%, 인구={res['pop_trend']}%, 임대료={res['rent_score']})\n"
    
    prompt += f"\n### [브랜드 경쟁력 분석]\n{brand_comp_result.get('summary', '')}\n\n"
    prompt += "위 데이터를 바탕으로 각 지역의 전략적 가치(Pros/Cons)를 대조하여 Top3ComparisonReport 형식으로 출력하세요."

    comparison_report: Top3ComparisonReport = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content=f"마포구 {business_type} 업종 Top 3 지역을 비교 분석하고 최종 Winner를 확정해줘.")
    ])

    print(f"--- [CONTEXT ANALYST] Winner 선정 완료: {comparison_report.winner_district} ---")

    return {
        "scouting_results": sorted_results,
        "top_3_candidates": top_3_names,
        "winner_district": comparison_report.winner_district,
        "target_district": comparison_report.winner_district, # 2번 노드 호환용
        "brand_analysis": brand_comp_result,
        "analysis_results": {
            "comparison_report": comparison_report.model_dump(),
            "scouting_summary": f"마포구 16개동 중 {', '.join(top_3_names)}가 상위 후보지로 선정되었습니다."
        },
        "current_agent": "context_analyst"
    }

async def _scout_district(dong_name: str, business_type: str, industry_code: str) -> dict:
    """개별 행정동 정량적 점수 산출 (LLM 없이 Python으로만 수행)"""
    try:
        # 1. 매출 정보
        sales_data = await market_tool.get_commercial_insights(dong_name, industry_code)
        sales_growth = sales_data.get("qoq_growth", 0)
        avg_revenue = sales_data.get("avg_monthly_revenue", 0)

        # 2. 인구 정보
        pop_data = await market_tool.get_population_trends(dong_name)
        pop_growth = pop_data.get("qoq_growth", 0)

        # 3. 임대료 정보
        rent_data = await market_tool.get_rent_insight(dong_name)
        rent_val = rent_data.get("avg_rent_3_3m2", 200000)

        # [점수 계산 로직]
        # 성장성(40%) + 인구유입(30%) + 임대료 가성비(30%)
        # 단순화를 위해 임대료는 낮을수록 점수 높게 (최대 30만 기준 역순)
        rent_score = max(0, (300000 - rent_val) / 300000 * 100)
        
        final_score = (sales_growth * 0.4) + (pop_growth * 0.3) + (rent_score * 0.3)
        
        return {
            "district": dong_name,
            "score": round(final_score, 2),
            "sales_growth": sales_growth,
            "avg_revenue": avg_revenue,
            "pop_trend": pop_growth,
            "rent_score": round(rent_score, 2),
            "reason": f"매출성장률 {sales_growth}% 및 유동인구 증가율 {pop_growth}% 반영"
        }
    except Exception:
        return {
            "district": dong_name, 
            "score": -99, 
            "sales_growth": 0,
            "avg_revenue": 0, 
            "pop_trend": 0,
            "rent_score": 0,
            "reason": "데이터 수집 실패"
        }
