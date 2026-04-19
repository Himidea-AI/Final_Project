import json
import redis.asyncio as aioredis
from src.schemas.state import AgentState, MarketData
from src.schemas.structured_output import MarketAnalysisOutput
from src.config.settings import settings
from src.agents.llms import get_fast_llm
from src.agents.tools import MarketDataTool
from src.database.postgres import PostgresClient
from langchain_core.messages import SystemMessage, HumanMessage

# DB 클라이언트 및 툴 초기화 (싱글톤 패턴 권장)
db_client = PostgresClient(settings.postgres_url)
market_tool = MarketDataTool(db_client)

_CACHE_TTL = 86400  # 24시간

async def market_analyst_node(state: AgentState) -> dict:
    """
    상권 분석 에이전트:
    - 실데이터 Binding: tools.py를 통해 DB에서 경쟁사, 유동인구, 매출, 임대료 데이터 수집
    - 통계적 요약본 기반 Gemini 3 Flash 분석 생성
    """
    target_district = state.get("target_district", "서교동")
    business_type = state.get("business_type", "카페")

    print(f"--- [MARKET ANALYST] {target_district} 실데이터 분석 시작 ---")

    # Redis 캐시 조회 (예진 synthesis 패턴 — 조회 실패 시 연결 누수 방지)
    cache_key = f"market:{target_district}:{business_type}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = await _redis.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            print(f"[market_analyst] 캐시 히트: {cache_key}")
            analysis = dict(state.get("analysis_results", {}))
            analysis["market_report"] = cached_data["market_report"]
            await _redis.aclose()
            return {
                "market_data": cached_data["market_data"],
                "analysis_results": analysis,
                "analysis_metrics": {**state.get("analysis_metrics", {}), **cached_data["metrics"]},
                "current_agent": "market_analyst",
            }
    except Exception as e:
        print(f"[market_analyst] Redis 캐시 조회 실패 (무시하고 계속): {e}")
        if _redis is not None:  # 조회 실패 시 연결 누수 방지
            try:
                await _redis.aclose()
            except Exception:
                pass
        _redis = None

    # [1] DB 연결 (필요 시)
    if db_client.engine is None:
        await db_client.connect()

    # [3] 실데이터 수집 (MarketDataTool 사용)
    lat = state.get("market_data", {}).get("lat", 37.5565)
    lon = state.get("market_data", {}).get("lng", 126.9239)
    commercial_radius = state.get("commercial_radius", 500)

    # 병렬 데이터 수집 (속도 최적화)
    import asyncio
    pop_task = market_tool.get_population_trends(target_district)
    sales_task = market_tool.get_commercial_insights(target_district, business_type)
    comp_task = market_tool.get_competitor_stats(lat, lon, business_type, radius_m=commercial_radius)
    rent_task = market_tool.get_rent_insight(target_district)

    pop_data, sales_data, comp_data, rent_data = await asyncio.gather(
        pop_task, sales_task, comp_task, rent_task
    )

    # 데이터 통합
    real_market_data: MarketData = {
        "district": target_district,
        "lat": lat,
        "lng": lon,
        "floating_population": {
            "total": pop_data.get("current_pop", 0),
            "trend": pop_data.get("summary", ""),
            "qoq_growth": pop_data.get("qoq_growth")
        },
        "competition_score": comp_data.get("competitor_count", 0) / 100,
        "average_rent": rent_data.get("avg_rent_3_3m2", 0),
        "sales_insight": sales_data.get("statistical_summary", ""),
        "rent_status": rent_data.get("summary", ""),
        "financial_metrics": state.get("market_data", {}).get("financial_metrics", {})
    }

    # 4. 전문 요약 및 구조화된 필드 생성 (Gemini 3 Flash 사용)
    # [API Quota 관리] 호출 전 2초 대기
    print("⏳ API 할당량 관리를 위해 2초 대기 중...")
    await asyncio.sleep(2)

    system_content = (
        "당신은 상권 분석 전문가이자 프랜차이즈 전략 컨설턴트입니다. "
        "공급된 실데이터를 분석하여 전문가 리포트와 정량 지표를 출력하세요.\n\n"
        f"### {target_district} 실데이터 분석 요약:\n"
        f"- 유동인구 추이: {pop_data.get('summary')}\n"
        f"- 매출 통계: {sales_data.get('statistical_summary')}\n"
        f"- 경쟁 및 밀집도: {comp_data.get('summary')}\n"
        f"- 임대료 및 적절성: {rent_data.get('summary')}\n\n"
        "report 필드: 상세 분석과 [프랜차이즈 전략팀 총평] 섹션 포함. '가장 큰 기회'와 '리스크' 명시.\n"
        "grade 필드: EXCELLENT / GOOD / NORMAL / RISKY 중 하나 (대문자).\n"
        "어조: 수치·사실 중심, 예비 창업자가 바로 이해할 수 있는 직관적 표현."
    )

    try:
        llm = get_fast_llm().with_structured_output(MarketAnalysisOutput)
        result: MarketAnalysisOutput = await llm.ainvoke([
            SystemMessage(content=system_content),
            HumanMessage(content=f"{target_district} {business_type} 업종의 심화 분석을 수행해줘."),
        ])

        market_summary = result.report
        final_metrics = {
            "district_grade": result.grade,
            "growth_rate": result.growth_rate,
            "competition_score": result.competition_score,
            "rent_affordability": result.rent_affordability,
        }

    except Exception as e:
        print(f"!!! [MARKET ANALYST ERROR] !!! {str(e)}")
        market_summary = f"{target_district} 지역 분석 중 오류가 발생했습니다."
        final_metrics = {"district_grade": "NORMAL"}

    analysis_results = state.get("analysis_results", {})
    analysis_results["market_report"] = market_summary

    # Redis 캐시 저장 (finally로 연결 누수 방지)
    if _redis is not None:
        try:
            await _redis.set(
                cache_key,
                json.dumps({
                    "market_report": market_summary,
                    "market_data": real_market_data,
                    "metrics": final_metrics,
                }, ensure_ascii=False, default=str),
                ex=_CACHE_TTL,
            )
            print(f"[market_analyst] 캐시 저장: {cache_key} (TTL: {_CACHE_TTL}s)")
        except Exception as e:
            print(f"[market_analyst] Redis 캐시 저장 실패 (무시): {e}")
        finally:
            try:
                await _redis.aclose()
            except Exception:
                pass

    return {
        "market_data": real_market_data,
        "analysis_results": analysis_results,
        "analysis_metrics": {**state.get("analysis_metrics", {}), **final_metrics},
        "current_agent": "market_analyst",
    }
