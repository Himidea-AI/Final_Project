import asyncio
import json
import redis.asyncio as aioredis
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.state import AgentState
from src.schemas.structured_output import FinalStrategyResult
from src.agents.llms import get_smart_llm
from src.config.settings import settings

_CACHE_TTL = 86400  # 24시간

async def synthesis_node(state: AgentState) -> dict:
    """
    최종 합성 에이전트 (Synthesis Agent):
    - [데이터 보존] legal_node가 생성한 14개 법률 리스크 데이터를 절대 훼손하지 않고 그대로 유지합니다.
    - 상권 분석, 유동인구 분석, 법률 검토 결과를 종합하여 최종 창업 전략 리포트를 생성합니다.
    - FinalStrategyResult 스키마에 맞춰 정형화된 JSON 데이터를 생성합니다.
    """
    print("--- [SYNTHESIS] 최종 전략 합성 및 데이터 검증 시작 ---")

    brand_name = state.get("brand_name", "미지정 브랜드")
    business_type = state.get("business_type", "카페")
    target_district = state.get("target_district", "마포구")
    target_price_range = state.get("target_price_range", "")
    operating_hours = state.get("operating_hours", [])
    initial_capital = state.get("initial_capital", 0)
    monthly_rent_budget = state.get("monthly_rent_budget", 0)
    store_area = state.get("store_area", 15.0)

    # Redis 캐시 조회 (사용자 조건이 달라지면 다른 캐시 사용)
    cache_key = f"v2:synthesis:{brand_name}:{target_district}:{business_type}:{monthly_rent_budget}:{store_area}:{state.get('population_weight', True)}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = None if settings.debug else await _redis.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            print(f"[synthesis] 캐시 히트: {cache_key}")
            analysis = dict(state.get("analysis_results", {}))
            analysis["final_report"] = cached_data["final_report"]
            analysis["market_summary"] = cached_data["market_summary"]
            # [#3] 캐시 히트 시 legal_risks 복원 (캐시에 저장된 값 우선, 없으면 state에서 유지)
            if "legal_risks" in cached_data:
                analysis["legal_risks"] = cached_data["legal_risks"]
            await _redis.aclose()
            return {
                "analysis_results": analysis,
                "overall_legal_risk": cached_data["overall_legal_risk"],
                "current_agent": "synthesis",
            }
    except Exception as e:
        print(f"[synthesis] Redis 캐시 조회 실패 (무시하고 계속): {e}")
        if _redis is not None:  # [#1] 조회 실패 시 연결 누수 방지
            try:
                await _redis.aclose()
            except Exception:
                pass
        _redis = None

    # 1. 데이터 추출 (기존 에이전트들의 결과물)
    analysis_results = state.get("analysis_results", {})
    market_report = analysis_results.get("market_report", "상권 분석 정보 없음")
    population_report = analysis_results.get("population_report", "인구 분석 정보 없음")

    # [중요] 14개의 법률 리스크 데이터 (절대 보존)
    legal_risks = analysis_results.get("legal_risks", [])
    overall_legal_risk = state.get("overall_legal_risk", "Caution")

    # 랭킹 데이터 추출
    winner_district = state.get("winner_district", target_district)
    top_3_candidates = state.get("top_3_candidates", [])
    scouting_results = state.get("scouting_results", [])

    # 랭킹 요약 (상위 4개 동, 핵심 수치만)
    ranking_summary = ""
    if scouting_results:
        ranking_summary = " / ".join(
            f"{r['rank']}위:{r['district']}({r['score']}점)"
            for r in scouting_results[:4]
        )

    # 공실 정보 추출 (scouting_results에 vacancy_rate 포함 시)
    vacancy_summary = ""
    if scouting_results:
        winner_row = next((r for r in scouting_results if r["district"] == winner_district), None)
        if winner_row and winner_row.get("vacancy_rate", 0) > 0:
            vr = winner_row["vacancy_rate"]
            vacancy_label = "높음(상권 주의)" if vr >= 10 else ("보통" if vr >= 5 else "낮음(상권 활발)")
            vacancy_summary = f"공실률({winner_district}): {vr}% — {vacancy_label} (2026년 4월 기준 네이버 부동산 상가 월세 매물)"

    # 2. LLM 합성용 컨텍스트 구성
    # [토큰 절감] 중간 에이전트 리포트 전문 대신 핵심 수치만 전달
    # market_report: 앞 150자 (등급·성장률 수치가 앞부분에 집중됨)
    # population_report: 앞 120자 (인구 수치 요약)
    # legal: summary 60자 이내로 축약 (level이 핵심)
    market_summary_short = market_report[:150].replace("\n", " ")
    pop_summary_short = population_report[:120].replace("\n", " ")

    legal_summary_for_llm = "\n".join([
        f"- {r.get('type', '미분류')}: {r.get('level', 'Normal')} — {r.get('summary', '')[:300]}"
        for r in legal_risks
    ])

    # 법률 DANGER 시 대안 지역 강조
    if overall_legal_risk == "danger":
        legal_override = (
            f"\n⚠️ 경고: 법률 리스크 DANGER. {target_district} 출점은 법률 위반 가능성이 높습니다. "
            f"final_recommendation에 대안 지역({', '.join(top_3_candidates[:2]) if top_3_candidates else '다른 지역'})을 최우선 제시하세요."
        )
    else:
        legal_override = ""

    prompt = (
        "프랜차이즈 창업 전략 컨설턴트로서 아래 데이터를 종합해 최종 리포트를 작성하세요.\n\n"
        f"브랜드:{brand_name}({business_type}) | 선택지역:{target_district} | 법률리스크:{overall_legal_risk}\n"
        f"입지랭킹: {ranking_summary}\n"
        f"상권({target_district}):\n{market_report[:1500]}\n"
        f"인구({target_district}):\n{population_report[:1500]}\n"
        + (f"{vacancy_summary}\n" if vacancy_summary else "")
        + f"법률(14개):\n{legal_summary_for_llm}\n"
        f"{legal_override}\n"
        f"창업조건: 객단가={target_price_range or '미지정'} | 시간대={','.join(operating_hours) or '미지정'} | "
        f"자본금={initial_capital:,}원 | 임대예산={monthly_rent_budget:,}원({store_area}평)\n\n"
        "요구사항:\n"
        "1. 1순위 추천 지역과 이유, 2~4순위 후보 간략 설명\n"
        "2. 창업자 조건(객단가·시간대·자본금·임대예산) 적합성 판단\n"
        "3. 창업 가부 결정 및 전략 제안\n"
        "4. FinalStrategyResult 스키마로 응답\n"
        f"5. overall_legal_risk는 반드시 '{overall_legal_risk}'\n"
    )

    try:
        # LLM 호출 (Structured Output)
        llm = get_smart_llm().with_structured_output(FinalStrategyResult)
        
        # API 할당량 관리를 위한 미세 대기
        await asyncio.sleep(1.5)
        
        final_strategy: FinalStrategyResult = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"{brand_name}의 {target_district} 출점 최종 전략 보고서를 완성해줘.")
        ])
        
        print(f"--- [SYNTHESIS] 최종 보고서 생성 완료 (등급: {final_strategy.overall_legal_risk}) ---")

    except Exception as e:
        print(f"!!! [SYNTHESIS ERROR] !!! {str(e)}")
        # 에러 발생 시 Fallback (데이터 보존을 위한 최소 데이터 구성)
        final_strategy = FinalStrategyResult(
            summary=f"{brand_name} {target_district} 분석 결과 요약 생성 중 오류 발생",
            is_direct=False,
            brand_category="franchise",
            overall_legal_risk=overall_legal_risk,
            profit_simulation={"monthly_revenue": 0, "net_profit": 0, "margin_rate": 0.0},
            competitor_analysis={"count": 0, "density": "NORMAL"},
            final_recommendation=f"분석 중 기술적 오류가 발생했습니다: {str(e)}"
        )

    # 3. 데이터 업데이트 (기존 legal_risks를 100% 보존하며 final_report 추가)
    new_analysis_results = dict(analysis_results)
    new_analysis_results["final_report"] = final_strategy.model_dump()
    # main.py가 analysis_report로 읽는 키
    new_analysis_results["market_summary"] = (
        final_strategy.summary + "\n\n" + final_strategy.final_recommendation
    )

    # 랭킹 결과 보존 (main.py → 프론트엔드 전달용)
    new_analysis_results["district_rankings"] = scouting_results
    new_analysis_results["winner_district"] = winner_district
    new_analysis_results["top_3_candidates"] = top_3_candidates

    # [검증] legal_risks가 누락되지 않았는지 다시 한 번 확인
    if "legal_risks" not in new_analysis_results:
        new_analysis_results["legal_risks"] = legal_risks

    # Redis 캐시 저장
    if _redis is not None:
        try:
            await _redis.set(
                cache_key,
                json.dumps({
                    "final_report": new_analysis_results["final_report"],
                    "market_summary": new_analysis_results["market_summary"],
                    "overall_legal_risk": overall_legal_risk,
                    "legal_risks": legal_risks,  # [#3] 캐시에 legal_risks 포함하여 히트 시 복원 가능
                }, ensure_ascii=False),
                ex=_CACHE_TTL,
            )
            print(f"[synthesis] 캐시 저장: {cache_key} (TTL: {_CACHE_TTL}s)")
        except Exception as e:
            print(f"[synthesis] Redis 캐시 저장 실패 (무시): {e}")
        finally:  # [#2] 저장 성공/실패 무관하게 항상 연결 종료
            try:
                await _redis.aclose()
            except Exception:
                pass

    return {
        "analysis_results": new_analysis_results,
        "overall_legal_risk": overall_legal_risk,
        "current_agent": "synthesis"
    }
