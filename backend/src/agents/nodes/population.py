import json
import asyncio
import re
import redis.asyncio as aioredis
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.state import AgentState
from src.agents.nodes.market_analyst import market_tool
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
        cached = await _redis.get(cache_key)
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

    # 1. 실데이터 수집
    pop_data = await market_tool.get_population_trends(target_district)
    
    if "error" in pop_data:
        print(f"!!! [POPULATION ANALYST DATA ERROR] !!! {pop_data['error']}")
        analysis_results = state.get("analysis_results", {})
        analysis_results["population_report"] = f"{target_district} 인구 데이터 조회 실패: {pop_data['error']}"
        return {"analysis_results": analysis_results, "current_agent": "population_analyst"}

    # 2. API 할당량 관리 (2초 대기)
    print("⏳ API 할당량 관리를 위해 2초 대기 중...")
    await asyncio.sleep(2)

    # 3. LLM 분석 프롬프트
    prompt = (
        "당신은 인구통계학 및 상권 유동인구 분석 전문가입니다. "
        "제보된 실데이터를 바탕으로 해당 지역의 유동인구 특성분석 리포트를 작성하세요.\n\n"
        f"### {target_district} 유동인구 실데이터:\n"
        f"- 현재 생활인구: {pop_data.get('current_pop', 0):,}명\n"
        f"- 전분기 대비 성장률(QoQ): {pop_data.get('qoq_growth', 0)}%\n"
        f"- 전년 대비 성장률(YoY): {pop_data.get('yoy_growth', 0)}%\n"
        f"- 종합 요약: {pop_data.get('summary', '')}\n\n"
        "### 출력 요구사항:\n"
        "1. 리포트 본문: 유동인구의 양적/질적 변화를 분석하고, 창업 시 고려해야 할 인구학적 통계치를 설명하세요.\n"
        "2. 구조화 데이터: 마지막에 반드시 [JSON_START]와 [JSON_END] 태그를 사용하여 아래 지표를 포함하세요.\n"
        "   - { \"population_score\": 점수(1-10), \"main_target_age\": \"주타겟\", \"peak_time\": \"피크시간대\" }\n"
        "3. 어조: 정교하고 분석적인 톤을 유지하세요."
    )

    try:
        llm = get_fast_llm()
        response = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"{target_district} 지역의 유동인구 심층 분석을 수행해줘.")
        ])
        
        # content 추출
        if isinstance(response.content, list):
            raw_content = "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in response.content])
        else:
            raw_content = str(response.content)
            
        # 파싱
        population_report = re.sub(r'\[JSON_START\].*?\[JSON_END\]', '', raw_content, flags=re.DOTALL).strip()
        json_match = re.search(r'\[JSON_START\](.*?)\[JSON_END\]', raw_content, re.DOTALL)
        
        new_metrics = {}
        if json_match:
            try:
                json_str = re.sub(r'```json|```', '', json_match.group(1)).strip()
                new_metrics = json.loads(json_str)
            except: pass

    except Exception as e:
        print(f"!!! [POPULATION ANALYST ERROR] !!! {str(e)}")
        population_report = f"{target_district} 인구 분석 중 오류가 발생했습니다."
        new_metrics = {}

    analysis_results = state.get("analysis_results", {})
    analysis_results["population_report"] = population_report

    # Redis 캐시 저장
    if _redis is not None:
        try:
            await _redis.set(
                cache_key,
                json.dumps({"population_report": population_report, "metrics": new_metrics}, ensure_ascii=False),
                ex=_CACHE_TTL,
            )
            print(f"[population_analyst] 캐시 저장: {cache_key} (TTL: {_CACHE_TTL}s)")
            await _redis.aclose()
        except Exception as e:
            print(f"[population_analyst] Redis 캐시 저장 실패 (무시): {e}")

    return {
        "analysis_results": analysis_results,
        "analysis_metrics": {**state.get("analysis_metrics", {}), **new_metrics},
        "current_agent": "population_analyst"
    }
