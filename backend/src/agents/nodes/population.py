import json
import asyncio
import redis.asyncio as aioredis
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.state import AgentState
from src.schemas.structured_output import PopulationAnalysisOutput
from src.agents.nodes.market_analyst import db_client
from src.agents.nodes.district_ranking import shared_population_trends
from src.agents.llms import get_fast_llm
from src.config.settings import settings

_CACHE_TTL = 86400  # 24시간


async def population_analyst_node(state: AgentState) -> dict:
    """
    유동인구 분석 에이전트:
    - 실데이터 기반 행정동 유동인구 추이 분석
    - 피크 시간대 및 주요 타겟층 도출
    """
    target_district = state.get("target_district", "서교동")
    business_type = state.get("business_type", "카페")
    print(f"--- [POPULATION ANALYST] {target_district} 입동인구 분석 시작 ---")

    # Redis 캐시 조회
    cache_key = f"population:{target_district}:{business_type}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = None if settings.debug else await _redis.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            print(f"[population_analyst] 캐시 히트: {cache_key}")
            analysis = dict(state.get("analysis_results", {}))
            analysis["population_report"] = cached_data["population_report"]
            await _redis.aclose()
            return {
                "analysis_results": analysis,
                "analysis_metrics": {**state.get("analysis_metrics", {}), **cached_data["metrics"]},
                "current_agent": "population_analyst",
            }
    except Exception as e:
        print(f"[population_analyst] Redis 캐시 조회 실패 (무시하고 계속): {e}")
        if _redis is not None:  # 조회 실패 시 연결 누수 방지
            try:
                await _redis.aclose()
            except Exception:
                pass
        _redis = None

    # 1. 실데이터 수집 (DB 연결 확인)
    if db_client.engine is None:
        await db_client.connect()
    # district_ranking_node와 동일 dong에 대한 호출은 shared_population_trends가 dedupe
    pop_data = await shared_population_trends(target_district)

    if "error" in pop_data:
        print(f"!!! [POPULATION ANALYST DATA ERROR] !!! {pop_data['error']}")
        analysis_results = state.get("analysis_results", {})
        analysis_results["population_report"] = f"{target_district} 인구 데이터 조회 실패: {pop_data['error']}"
        return {"analysis_results": analysis_results, "current_agent": "population_analyst"}

    # 2. API 할당량 관리 (2초 대기)
    print("[WAIT] API 할당량 관리를 위해 2초 대기 중...")
    await asyncio.sleep(2)

    # 3. LLM 분석 (Structured Output)
    system_content = (
        "당신은 인구통계학 및 상권 유동인구 분석 전문가입니다. "
        "제보된 실데이터를 바탕으로 해당 지역의 유동인구 특성분석 리포트를 작성하세요.\n\n"
        f"### {target_district} 유동인구 실데이터:\n"
        f"- 현재 생활인구: {pop_data.get('current_pop', 0):,}명\n"
        f"- 전분기 대비 성장률(QoQ): {pop_data.get('qoq_growth', 0)}%\n"
        f"- 전년 대비 성장률(YoY): {pop_data.get('yoy_growth', 0)}%\n"
        f"- 종합 요약: {pop_data.get('summary', '')}\n\n"
        "report 필드: 유동인구의 양적/질적 변화를 분석하고 창업 시 고려할 인구학적 통계치를 포함하세요.\n"
        "어조: 정교하고 분석적인 톤을 유지하세요."
    )

    try:
        llm = get_fast_llm().with_structured_output(PopulationAnalysisOutput)
        result: PopulationAnalysisOutput = await llm.ainvoke(
            [
                SystemMessage(content=system_content),
                HumanMessage(content=f"{target_district} 지역의 유동인구 심층 분석을 수행해줘."),
            ]
        )

        population_report = result.report
        new_metrics = {
            "population_score": result.population_score,
            "main_target_age": result.main_target_age,
            "peak_time": result.peak_time,
        }

    except Exception as e:
        print(f"!!! [POPULATION ANALYST ERROR] !!! {str(e)}")
        population_report = f"{target_district} 인구 분석 중 오류가 발생했습니다."
        new_metrics = {}

    analysis_results = state.get("analysis_results", {})
    analysis_results["population_report"] = population_report

    # Redis 캐시 저장 (finally로 연결 누수 방지)
    if _redis is not None:
        try:
            await _redis.set(
                cache_key,
                json.dumps({"population_report": population_report, "metrics": new_metrics}, ensure_ascii=False),
                ex=_CACHE_TTL,
            )
            print(f"[population_analyst] 캐시 저장: {cache_key} (TTL: {_CACHE_TTL}s)")
        except Exception as e:
            print(f"[population_analyst] Redis 캐시 저장 실패 (무시): {e}")
        finally:
            try:
                await _redis.aclose()
            except Exception:
                pass

    return {
        "analysis_results": analysis_results,
        "analysis_metrics": {**state.get("analysis_metrics", {}), **new_metrics},
        "current_agent": "population_analyst",
    }
