import json
import asyncio
import logging
import redis.asyncio as aioredis
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.state import AgentState
from src.schemas.structured_output import PopulationAnalysisOutput
from src.agents.nodes._attribution_helpers import build_attribution
from src.agents.nodes.market_analyst import db_client, market_tool
from src.agents.nodes.district_ranking import shared_population_trends
from src.agents.llms import get_fast_llm
from src.config.settings import settings
from src.services.population_api import MAPO_DONG_CODES

logger = logging.getLogger(__name__)

# SGIS 클라이언트 (싱글톤, API 키 없으면 None)
_sgis_client = None


def _init_sgis_client():
    """SGIS API 키가 있을 때만 클라이언트 생성"""
    global _sgis_client
    if _sgis_client is None and settings.sgis_api_key and settings.sgis_secret_key:
        from src.services.sgis_api import SgisAPIClient

        _sgis_client = SgisAPIClient(
            consumer_key=settings.sgis_api_key,
            consumer_secret=settings.sgis_secret_key,
        )


_CACHE_TTL = 86400  # 24시간


async def population_analyst_node(state: AgentState) -> dict:
    """
    유동인구 분석 에이전트:
    - 실데이터 기반 행정동 유동인구 추이 분석
    - 피크 시간대 및 주요 타겟층 도출
    """
    target_district = state.get("target_district", "서교동")
    business_type = state.get("business_type", "카페")
    logger.info(f"--- [POPULATION ANALYST] {target_district} 입동인구 분석 시작 ---")

    # Redis 캐시 조회
    cache_key = f"population:{target_district}:{business_type}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = None if settings.debug else await _redis.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            logger.info(f"[population_analyst] 캐시 히트: {cache_key}")
            analysis = dict(state.get("analysis_results", {}))
            analysis["population_report"] = cached_data["population_report"]
            await _redis.aclose()
            _cached_metrics = cached_data.get("metrics", {}) or {}
            _cached_report = cached_data.get("population_report", "") or ""
            cached_attribution = build_attribution(
                agent_id="population_analyst",
                display_name="유동인구 분석",
                kind="LLM",
                sources=["seoul_adstrd_flpop", "sgis"],
                verdict=f"주 타겟 {_cached_metrics.get('main_target_age', 'N/A')} · 피크 {_cached_metrics.get('peak_time', '미확인')}",
                reasoning=str(_cached_report) if _cached_report else "유동인구 분석 (캐시)",
                confidence=0.8,
            )
            analysis["population_analyst_result"] = {"agent_attribution": cached_attribution}
            return {
                "analysis_results": analysis,
                "analysis_metrics": {**state.get("analysis_metrics", {}), **_cached_metrics},
                "current_agent": "population_analyst",
                "agent_attribution": cached_attribution,
            }
    except Exception as e:
        logger.warning(f"[population_analyst] Redis 캐시 조회 실패 (무시하고 계속): {e}")
        if _redis is not None:  # 조회 실패 시 연결 누수 방지
            try:
                await _redis.aclose()
            except Exception:
                pass
        _redis = None

    # 1. 실데이터 수집 (DB 연결 확인)
    if db_client.engine is None:
        await db_client.connect()

    # SGIS 상주인구 조회 (API 키 있을 때만)
    _init_sgis_client()

    async def _fetch_sgis_data() -> dict | None:
        if _sgis_client is None:
            return None
        try:
            dong_code = MAPO_DONG_CODES.get(target_district)
            if not dong_code:
                return None
            resident_pop = await _sgis_client.get_resident_population(dong_code)
            age_dist = await _sgis_client.get_age_distribution(dong_code)
            return {"resident_population": resident_pop, "age_distribution": age_dist}
        except Exception as e:
            logger.debug(f"[population_analyst] SGIS 조회 실패 ({target_district}): {e}")
            return None

    # district_ranking_node와 동일 dong에 대한 호출은 shared_population_trends가 dedupe
    pop_data, demo_data, sgis_data = await asyncio.gather(
        shared_population_trends(target_district),
        market_tool.get_commercial_insights(target_district, business_type),
        _fetch_sgis_data(),
    )

    if "error" in pop_data:
        logger.warning(f"[POPULATION ANALYST DATA ERROR] !!! {pop_data['error']}")
        analysis_results = state.get("analysis_results", {})
        analysis_results["population_report"] = f"{target_district} 인구 데이터 조회 실패: {pop_data['error']}"
        return {"analysis_results": analysis_results, "current_agent": "population_analyst"}

    # 성별/연령/피크시간 도출 (실측 매출 건수 기반)
    demo_summary = ""
    real_peak_time = None
    if "error" not in demo_data:
        demographics = {
            "남성": demo_data.get("male", 0) or 0,
            "여성": demo_data.get("female", 0) or 0,
            "20대": demo_data.get("age_20s", 0) or 0,
            "30대": demo_data.get("age_30s", 0) or 0,
            "40대": demo_data.get("age_40s", 0) or 0,
        }
        top_gender = "남성" if demographics["남성"] >= demographics["여성"] else "여성"
        age_groups = {k: v for k, v in demographics.items() if k.endswith("대")}
        top_age = max(age_groups, key=age_groups.get) if any(v > 0 for v in age_groups.values()) else "20대"
        real_peak_time = demo_data.get("peak_time")
        demo_summary = (
            f"- 주요 성별: {top_gender} (남성 {demographics['남성']:,} / 여성 {demographics['여성']:,})\n"
            f"- 연령대별: 20대 {demographics['20대']:,} / 30대 {demographics['30대']:,} / 40대 {demographics['40대']:,}\n"
            f"- 최다 고객층: {top_age} {top_gender}\n" + (f"- 피크 시간대: {real_peak_time}" if real_peak_time else "")
        )

    # 2. API 할당량 관리 (2초 대기)
    logger.debug("[WAIT] API 할당량 관리를 위해 2초 대기 중...")
    await asyncio.sleep(2)

    # 3. LLM 분석 (Structured Output)
    system_content = (
        "당신은 인구통계학 및 상권 유동인구 분석 전문가입니다. "
        "제보된 실데이터를 바탕으로 해당 지역의 유동인구 특성분석 리포트를 작성하세요.\n\n"
        f"### {target_district} 유동인구 실데이터:\n"
        f"- 현재 생활인구: {pop_data.get('current_pop', 0):,}명\n"
        f"- 전분기 대비 성장률(QoQ): {pop_data.get('qoq_growth', 0)}%\n"
        f"- 전년 대비 성장률(YoY): {pop_data.get('yoy_growth', 0)}%\n"
        f"- 종합 요약: {pop_data.get('summary', '')}\n"
        + (f"\n### 인구통계학적 특성 (실측 데이터):\n{demo_summary}\n" if demo_summary else "")
        + (
            f"\n### 상주인구 데이터 (SGIS 통계청):\n{json.dumps(sgis_data, ensure_ascii=False, default=str)[:800]}\n"
            if sgis_data
            else ""
        )
        + "\nreport 필드: 유동인구의 양적/질적 변화를 분석하고 창업 시 고려할 인구학적 통계치를 포함하세요.\n"
        "main_target_age 필드: 위 실측 인구통계 데이터를 반드시 반영하여 '20대 여성', '30대 남성', '20~30대 여성' 등 구체적인 성별+연령 조합으로 작성하세요.\n"
        + (
            f"peak_time 필드: 반드시 '{real_peak_time}'로 작성하세요 (실측 매출 건수 기준 피크 시간대).\n"
            if real_peak_time
            else "peak_time 필드: 업종과 지역 특성을 고려한 피크 시간대를 '18:00~21:00' 형식으로 작성하세요.\n"
        )
        + "어조: 정교하고 분석적인 톤을 유지하세요."
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
        logger.error(f"[POPULATION ANALYST ERROR] !!! {str(e)}")
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
            logger.info(f"[population_analyst] 캐시 저장: {cache_key} (TTL: {_CACHE_TTL}s)")
        except Exception as e:
            logger.warning(f"[population_analyst] Redis 캐시 저장 실패 (무시): {e}")
        finally:
            try:
                await _redis.aclose()
            except Exception:
                pass

    attribution = build_attribution(
        agent_id="population_analyst",
        display_name="유동인구 분석",
        kind="LLM",
        sources=["seoul_adstrd_flpop", "sgis"],
        verdict=f"주 타겟 {new_metrics.get('main_target_age', 'N/A')} · 피크 {new_metrics.get('peak_time', '미확인')}",
        reasoning=str(population_report) if population_report else "유동인구 분석 데이터 기반",
        confidence=0.8,
    )
    analysis_results["population_analyst_result"] = {"agent_attribution": attribution}

    return {
        "analysis_results": analysis_results,
        "analysis_metrics": {**state.get("analysis_metrics", {}), **new_metrics},
        "current_agent": "population_analyst",
        "agent_attribution": attribution,
    }
