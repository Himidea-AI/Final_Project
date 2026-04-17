import json
import re
import redis.asyncio as aioredis
from src.schemas.state import AgentState, MarketData
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
    # 마포구 16개 행정동 중심 좌표 (경쟁사 반경 분석용)
    _DONG_COORDS: dict = {
        "아현동":  (37.5502, 126.9594),
        "공덕동":  (37.5430, 126.9519),
        "도화동":  (37.5393, 126.9457),
        "용강동":  (37.5382, 126.9383),
        "대흥동":  (37.5480, 126.9437),
        "염리동":  (37.5523, 126.9474),
        "신수동":  (37.5453, 126.9361),
        "서강동":  (37.5493, 126.9347),
        "서교동":  (37.5565, 126.9239),
        "합정동":  (37.5497, 126.9143),
        "망원1동": (37.5558, 126.9059),
        "망원2동": (37.5531, 126.9021),
        "연남동":  (37.5617, 126.9226),
        "성산1동": (37.5663, 126.9069),
        "성산2동": (37.5706, 126.9111),
        "상암동":  (37.5789, 126.8899),
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

    prompt = (
        "당신은 상권 분석 전문가이자 프랜차이즈 전략 컨설턴트입니다. "
        "공급된 실데이터를 분석하여 전문가 리포트와 시각화용 데이터를 정확히 구분하여 출력하세요.\n\n"
        f"### {target_district} 실데이터 분석 요약:\n"
        f"- 유동인구 추이: {pop_data.get('summary')}\n"
        f"- 매출 통계: {sales_data.get('statistical_summary')}\n"
        f"- 경쟁 및 밀집도: {comp_data.get('summary')}\n"
        f"- 임대료 및 적절성: {rent_data.get('summary')}\n\n"
        "### 출력 요구사항:\n"
        "1. 리포트 본문: 상세 분석과 하단 [프랜차이즈 전략팀 총평] 섹션을 포함할 것. '가장 큰 기회'와 '리스크'를 명시.\n"
        "2. 구조화 데이터: 리포트의 가장 마지막에 아래와 같이 JSON 형식을 포함할 것.\n"
        "   - 형식: [JSON_START]{ \"grade\": \"등급\", \"growth_rate\": 수치, \"competition_score\": 수치, \"rent_affordability\": \"등급\" }[JSON_END]\n"
        "   - grade: 반드시 EXCELLENT | GOOD | NORMAL | RISKY 중 하나 (대문자)\n"
        "   - growth_rate: 전분기 대비 매출 성장률 (단위: %, 예: 3.5 / -1.2)\n"
        "   - competition_score: 경쟁 밀집도 (0.0~1.0 사이의 소수, 낮을수록 경쟁 적음)\n"
        "   - rent_affordability: 임대료 부담 수준. 반드시 SAFE | CAUTION | DANGER 중 하나 (대문자)\n"
        "3. 어조: 비유적 표현이나 문학적 수사 없이, 구체적인 수치와 사실 중심으로 명확하고 이해하기 쉽게 작성하세요. 예비 창업자가 바로 이해할 수 있는 직관적인 표현을 사용하세요."
    )

    try:
        llm = get_fast_llm()
        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"{target_district} {business_type} 업종의 심화 분석 리포트와 JSON 지표를 작성해줘.")
        ])
        
        # content 추출 및 전처리
        if isinstance(response.content, list):
            raw_content = "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in response.content])
        else:
            raw_content = str(response.content)

        # 1. 리포트 본문 추출
        market_summary = re.sub(r'\[JSON_START\].*?\[JSON_END\]', '', raw_content, flags=re.DOTALL).strip()
        
        # 2. JSON 데이터 추출
        json_match = re.search(r'\[JSON_START\](.*?)\[JSON_END\]', raw_content, re.DOTALL)
        if json_match:
            try:
                json_str = json_match.group(1).strip()
                json_str = re.sub(r'```json|```', '', json_str).strip()
                final_metrics = json.loads(json_str)
                if "grade" in final_metrics:
                    final_metrics["district_grade"] = str(final_metrics["grade"]).upper()
            except Exception as je:
                final_metrics = {"district_grade": "NORMAL", "error": f"JSON 파싱 실패: {str(je)}"}
        else:
            final_metrics = {"district_grade": "NORMAL", "error": "JSON 태그 없음"}

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
