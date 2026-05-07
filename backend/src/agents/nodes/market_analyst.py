import json
import redis.asyncio as aioredis
from src.schemas.state import AgentState, MarketData
from src.schemas.structured_output import MarketAnalysisOutput
from src.config.settings import settings
from src.agents.llms import get_fast_llm
from src.agents.tools import MarketDataTool
from src.agents.nodes._attribution_helpers import build_attribution
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
    # v2: raw_inputs(qoq_growth_pct/saturation_level) 추가 — v7 grade 분류 평가용.
    cache_key = f"v2:market:{target_district}:{business_type}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = None if settings.debug else await _redis.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            print(f"[market_analyst] 캐시 히트: {cache_key}")
            analysis = dict(state.get("analysis_results", {}))
            analysis["market_report"] = cached_data["market_report"]
            await _redis.aclose()
            _cached_metrics = cached_data.get("metrics", {}) or {}
            cached_attribution = build_attribution(
                agent_id="market_analyst",
                display_name="시장 분석",
                kind="LLM",
                sources=["district_sales", "kakao_store", "golmok_rent"],
                verdict=f"상권 등급 {_cached_metrics.get('district_grade', 'NORMAL')} / 성장률 {_cached_metrics.get('growth_rate', 0)}%",
                reasoning=str(cached_data.get("market_report", "")) or "시장 분석 데이터 기반 (캐시)",
                confidence=0.85,
            )
            analysis["market_analyst_result"] = {"agent_attribution": cached_attribution}
            return {
                "market_data": cached_data["market_data"],
                "analysis_results": analysis,
                "analysis_metrics": {**state.get("analysis_metrics", {}), **_cached_metrics},
                "current_agent": "market_analyst",
                "agent_attribution": cached_attribution,
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
    # 마포구 16개 행정동 중심 좌표 (경쟁사 반경 분석용)
    _DONG_COORDS: dict = {
        "아현동": (37.5502, 126.9594),
        "공덕동": (37.5430, 126.9519),
        "도화동": (37.5393, 126.9457),
        "용강동": (37.5382, 126.9383),
        "대흥동": (37.5480, 126.9437),
        "염리동": (37.5523, 126.9474),
        "신수동": (37.5453, 126.9361),
        "서강동": (37.5493, 126.9347),
        "서교동": (37.5565, 126.9239),
        "합정동": (37.5497, 126.9143),
        "망원1동": (37.5558, 126.9059),
        "망원2동": (37.5531, 126.9021),
        "연남동": (37.5617, 126.9226),
        "성산1동": (37.5663, 126.9069),
        "성산2동": (37.5706, 126.9111),
        "상암동": (37.5789, 126.8899),
    }
    _default_lat, _default_lng = _DONG_COORDS.get(target_district, (37.5565, 126.9239))
    lat = state.get("market_data", {}).get("lat") or _default_lat
    lon = state.get("market_data", {}).get("lng") or _default_lng
    commercial_radius = state.get("commercial_radius", 500)

    # 병렬 데이터 수집 (속도 최적화)
    import asyncio

    pop_task = market_tool.get_population_trends(target_district)
    sales_task = market_tool.get_commercial_insights(target_district, business_type)
    comp_task = market_tool.get_competitor_stats(lat, lon, business_type, radius_m=commercial_radius)
    rent_task = market_tool.get_rent_insight(target_district)

    pop_data, sales_data, comp_data, rent_data = await asyncio.gather(pop_task, sales_task, comp_task, rent_task)

    # 데이터 통합
    real_market_data: MarketData = {
        "district": target_district,
        "lat": lat,
        "lng": lon,
        "floating_population": {
            "total": pop_data.get("current_pop", 0),
            "trend": pop_data.get("summary", ""),
            "qoq_growth": pop_data.get("qoq_growth"),
        },
        "competition_score": comp_data.get("competitor_count", 0) / 100,
        "average_rent": rent_data.get("avg_rent_3_3m2", 0),
        "sales_insight": sales_data.get("statistical_summary", ""),
        "rent_status": rent_data.get("summary", ""),
        "financial_metrics": state.get("market_data", {}).get("financial_metrics", {}),
    }

    # 4. 전문 요약 및 구조화된 필드 생성 (Gemini 3 Flash 사용)
    # [API Quota 관리] 호출 전 2초 대기
    print("[WAIT] API 할당량 관리를 위해 2초 대기 중...")
    await asyncio.sleep(2)

    system_content = (
        "[AGENT: market_analyst] 상권 분석 에이전트 — LangSmith 식별용 라벨.\n\n"
        "당신은 상권 분석 전문가이자 프랜차이즈 전략 컨설턴트입니다. "
        "공급된 실데이터를 분석하여 전문가 리포트와 정량 지표를 출력하세요.\n\n"
        f"### {target_district} 실데이터 분석 요약:\n"
        f"- 유동인구 추이: {pop_data.get('summary')}\n"
        f"- 매출 통계: {sales_data.get('statistical_summary')}\n"
        f"- 경쟁 및 밀집도: {comp_data.get('summary')}\n"
        f"- 임대료 및 적절성: {rent_data.get('summary')}\n\n"
        "grade 판정 기준 (반드시 아래 기준으로 판단):\n"
        "- EXCELLENT: 유동인구 QoQ 증가율 >3% AND 경쟁 포화도 낮음 AND 임대료 시장평균 이하\n"
        "- GOOD:      위 3가지 중 2가지 충족, 또는 매출 성장 추세가 뚜렷한 경우\n"
        "- NORMAL:    위 3가지 중 1가지만 충족, 또는 데이터가 부분적인 경우\n"
        "- RISKY:     유동인구 감소 OR 경쟁 포화 OR 임대료 시장평균 150% 초과 중 하나라도 해당\n\n"
        "report 필드 필수 구조:\n"
        "1) 수치 요약 (유동인구·경쟁·임대료·매출 4개 지표)\n"
        "2) 가장 큰 기회 (구체적 수치 포함)\n"
        "3) 핵심 리스크 (구체적 수치 포함)\n"
        "4) [프랜차이즈 전략팀 총평] — 3문장 이내, 예비 창업자 직관적 표현\n"
        "어조: 수치·사실 중심, 추상적 표현 금지."
    )

    try:
        llm = get_fast_llm().with_structured_output(MarketAnalysisOutput)
        result: MarketAnalysisOutput = await llm.ainvoke(
            [
                SystemMessage(content=system_content),
                HumanMessage(content=f"{target_district} {business_type} 업종의 심화 분석을 수행해줘."),
            ]
        )

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
            # v7 평가용 raw_inputs — 룰엔진이 expected_grade 산출에 사용.
            # qoq_growth_pct: pop_data.qoq_growth (% → 비율: 12 → 0.12)
            # saturation_level: comp_data 명시 필드 또는 competitor_count 기반 추론.
            _qoq_raw = pop_data.get("qoq_growth")
            _qoq_pct = (float(_qoq_raw) / 100.0) if _qoq_raw is not None else None
            _comp_count = comp_data.get("competitor_count", 0) or 0
            _sat_level = comp_data.get("saturation_level")
            if not _sat_level:
                # competitor_count → saturation_level 추론 (반경 500m 기준)
                if _comp_count >= 16:
                    _sat_level = "saturated"
                elif _comp_count >= 11:
                    _sat_level = "high"
                elif _comp_count >= 7:
                    _sat_level = "medium"
                elif _comp_count >= 3:
                    _sat_level = "low"
                else:
                    _sat_level = "sparse"
            raw_inputs = {
                "qoq_growth_pct": _qoq_pct,
                "saturation_level": _sat_level,
                "competitor_count": _comp_count,
            }
            await _redis.set(
                cache_key,
                json.dumps(
                    {
                        "market_report": market_summary,
                        "market_data": real_market_data,
                        "metrics": final_metrics,
                        "raw_inputs": raw_inputs,  # v7 평가 — 룰엔진 expected_grade 산출용
                    },
                    ensure_ascii=False,
                    default=str,
                ),
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

    attribution = build_attribution(
        agent_id="market_analyst",
        display_name="시장 분석",
        kind="LLM",
        sources=["district_sales", "kakao_store", "golmok_rent"],
        verdict=f"상권 등급 {final_metrics.get('district_grade', 'NORMAL')} / 성장률 {final_metrics.get('growth_rate', 0)}%",
        reasoning=str(market_summary) if market_summary else "시장 분석 데이터 기반",
        confidence=0.85,
    )
    analysis_results["market_analyst_result"] = {"agent_attribution": attribution}

    return {
        "market_data": real_market_data,
        "analysis_results": analysis_results,
        "analysis_metrics": {**state.get("analysis_metrics", {}), **final_metrics},
        "current_agent": "market_analyst",
        "agent_attribution": attribution,
    }
