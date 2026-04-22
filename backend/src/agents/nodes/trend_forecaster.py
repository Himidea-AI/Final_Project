"""trend_forecaster 에이전트: 업종 검색량 + 지역 모멘텀 + 상권 변화 + 거시 기준금리 종합.

향후 12개월 시장 전망을 LLM structured output으로 도출.
market_analyst.py 패턴을 미러링 — 싱글톤, Redis try/finally, asyncio.gather, get_fast_llm.
"""

import asyncio
import json

import redis.asyncio as aioredis
from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.llms import get_fast_llm
from src.agents.nodes._attribution_helpers import build_attribution
from src.agents.tools import MarketDataTool
from src.config.settings import settings
from src.database.postgres import PostgresClient
from src.schemas.state import AgentState
from src.schemas.trend_forecast import TrendForecastOutput

# 싱글톤 (market_analyst 패턴)
db_client = PostgresClient(settings.postgres_url)
market_tool = MarketDataTool(db_client)

_CACHE_TTL = 86400  # 24시간
_FORECAST_HORIZON_MONTHS = 12  # 하드코딩 (프론트 토글 미요구)


async def trend_forecaster_node(state: AgentState) -> dict:
    """업종·지역·상권·거시 4개 시계열 종합 → 향후 12개월 전망."""
    target_district = state.get("target_district", "서교동")
    business_type = state.get("business_type", "카페")
    brand_name = state.get("brand_name") or ""
    industry_filter = state.get("industry_filter")  # B1 추가 필드, CS 코드

    # 입력 → naver_trend_industry.industry 값으로 정규화
    industry = market_tool.resolve_industry(
        industry_filter=industry_filter,
        brand_name=brand_name,
        business_type=business_type,
    )

    print(f"--- [TREND FORECASTER] {target_district} / {industry} (brand={brand_name or 'N/A'}) 분석 시작 ---")

    cache_key = f"trend_forecast:{target_district}:{industry}:{brand_name or 'none'}"

    # [1] Redis 캐시 조회 (try/finally aclose — 누수 방지)
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = await _redis.get(cache_key)
        if cached:
            print(f"[trend_forecaster] 캐시 히트: {cache_key}")
            cached_data = json.loads(cached)
            await _redis.aclose()
            _cached_report = cached_data.get("report") or {}
            _cached_forecast = _cached_report.get("forecast", {}) if isinstance(_cached_report, dict) else {}
            _cached_narr = _cached_forecast.get("narrative", "") if isinstance(_cached_forecast, dict) else ""
            cached_trend_attr = build_attribution(
                agent_id="trend_forecaster",
                display_name="트렌드 전망",
                kind="LLM",
                sources=[
                    "naver_trend_industry",
                    "naver_trend_quarterly",
                    "seoul_adstrd_change_ix",
                    "ecos_timeseries",
                ],
                verdict=f"12개월 전망 {_cached_forecast.get('score', 0)}/100 · {_cached_forecast.get('direction', 'N/A')}",
                reasoning=str(_cached_narr)[:300] if _cached_narr else "추세 예측 (캐시)",
                confidence=0.75,
            )
            _cached_analysis = {
                **state.get("analysis_results", {}),
                "trend_forecast": _cached_report,
                "trend_forecaster_result": {"agent_attribution": cached_trend_attr},
            }
            return {
                "analysis_results": _cached_analysis,
                "analysis_metrics": {
                    **state.get("analysis_metrics", {}),
                    **cached_data["metrics"],
                },
                "current_agent": "trend_forecaster",
                "agent_attribution": cached_trend_attr,
            }
    except Exception as e:
        print(f"[trend_forecaster] Redis 캐시 조회 실패 (무시하고 계속): {e}")
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass
        _redis = None

    # [2] DB lazy connect
    if db_client.engine is None:
        await db_client.connect()

    # [3] 병렬 데이터 수집
    try:
        industry_data, dong_data, change_ix_data, rate_data = await asyncio.gather(
            market_tool.get_industry_trend(industry, months_back=24),
            market_tool.get_dong_trend_quarterly(target_district, quarters_back=8),
            market_tool.get_adstrd_change_ix(target_district),
            market_tool.get_base_rate_trend(months_back=12),
        )
    except Exception as e:
        print(f"!!! [TREND FORECASTER ERROR] !!! DB 수집 실패: {e}")
        error_trend_attr = build_attribution(
            agent_id="trend_forecaster",
            display_name="트렌드 전망",
            kind="LLM",
            sources=[
                "naver_trend_industry",
                "naver_trend_quarterly",
                "seoul_adstrd_change_ix",
                "ecos_timeseries",
            ],
            verdict="DB 수집 실패 · 분석 제한",
            reasoning=f"{target_district} {industry} 전망 데이터 수집 실패: {str(e)[:200]}",
            confidence=0.2,
        )
        return {
            "analysis_results": {
                **state.get("analysis_results", {}),
                "trend_forecast": {
                    "error": str(e),
                    "narrative": f"{target_district} {industry} 전망 데이터 수집 실패.",
                },
                "trend_forecaster_result": {"agent_attribution": error_trend_attr},
            },
            "current_agent": "trend_forecaster",
            "errors": state.get("errors", []) + [f"trend_forecaster: {e}"],
            "agent_attribution": error_trend_attr,
        }

    # [4] LLM 호출 전 API quota 관리
    print("[WAIT] API 할당량 관리를 위해 2초 대기 중...")
    await asyncio.sleep(2)

    change_ix_current = change_ix_data.get("current") or {}

    system_content = (
        "당신은 프랜차이즈 본사 영업팀을 지원하는 상권 분석 전문가입니다. "
        "업종 검색량·지역 모멘텀·상권 변화 지표·거시 기준금리 4개 시계열을 "
        "종합하여 향후 12개월 시장 전망을 판단하세요.\n\n"
        "모든 판단은 제공된 수치에 근거해야 하며, key_drivers와 risks에는 "
        "반드시 구체적 수치를 포함하세요 (예: '커피 검색량 YoY +15%'). "
        "데이터가 결측이거나 최신성이 떨어지는 경우 forecast_confidence를 낮추세요."
    )

    human_content = (
        f"### 분석 대상\n"
        f"- 행정동: {target_district}\n"
        f"- 업종: {industry}\n"
        f"- 브랜드: {brand_name or 'N/A'}\n\n"
        f"### [1] 업종 검색량 추이 (네이버 DataLab, 월별 0-100 상대값)\n"
        f"- 최근 월 ratio: {industry_data.get('current_ratio')}\n"
        f"- 전년 동월 대비 (YoY): {industry_data.get('yoy_change_pct')}%\n"
        f"- 방향: {industry_data.get('direction')}\n"
        f"- 최근 12개월 샘플: {industry_data.get('samples', [])[-12:]}\n\n"
        f"### [2] 지역 모멘텀 ({target_district} 분기 트렌드 스코어)\n"
        f"- 최신 분기: {dong_data.get('max_quarter')} (⚠ 최신 데이터 2024 Q4 기준, 참고 수준)\n"
        f"- 최신 스코어: {dong_data.get('recent_score')}\n"
        f"- 8분기 증감률: {dong_data.get('slope_pct')}%\n\n"
        f"### [3] 상권 변화 지표 (서울시 행정동 단위)\n"
        f"- 분류: {change_ix_current.get('change_ix_label', 'N/A')} ({change_ix_current.get('change_ix_class', '')})\n"
        f"- 이 동 영업 기간 평균: {change_ix_current.get('opr_months')}개월\n"
        f"- 서울 평균 대비: {change_ix_current.get('opr_vs_seoul_ratio')}배\n"
        f"- 이 동 폐업 소요 평균: {change_ix_current.get('cls_months')}개월\n"
        f"- 서울 폐업 평균 대비: {change_ix_current.get('cls_vs_seoul_ratio')}배\n\n"
        f"### [4] 거시경제 (한국은행 기준금리)\n"
        f"- 현재: {rate_data.get('current')}%\n"
        f"- 방향: {rate_data.get('trend')}\n"
        f"- 최근 12개월: {rate_data.get('samples', [])}\n\n"
        f"위 데이터를 종합해 향후 {_FORECAST_HORIZON_MONTHS}개월 전망을 판단하세요."
    )

    llm = get_fast_llm().with_structured_output(TrendForecastOutput)

    try:
        parsed: TrendForecastOutput = await llm.ainvoke(
            [
                SystemMessage(content=system_content),
                HumanMessage(content=human_content),
            ]
        )
    except Exception as e:
        print(f"!!! [TREND FORECASTER LLM ERROR] !!! {e}")
        parsed = TrendForecastOutput(
            forecast_score=50,
            forecast_direction="stable",
            forecast_confidence="low",
            key_drivers=[],
            risks=["LLM 호출 실패, 정량 지표만 참고"],
            narrative=(
                f"{target_district} {industry} 향후 {_FORECAST_HORIZON_MONTHS}개월 전망: "
                "LLM 해석 실패. 첨부 정량 데이터로만 판단 요망."
            ),
        )

    # [5] 결과 조립
    report = {
        "industry_trend": {
            "industry": industry,
            "current_ratio": industry_data.get("current_ratio"),
            "yoy_change_pct": industry_data.get("yoy_change_pct"),
            "direction": industry_data.get("direction"),
            "samples": industry_data.get("samples", [])[-12:],
        },
        "dong_trend": {
            "dong_name": target_district,
            "recent_score": dong_data.get("recent_score"),
            "slope_pct": dong_data.get("slope_pct"),
            "max_quarter": dong_data.get("max_quarter"),
            "samples": dong_data.get("samples", []),
            "data_staleness_note": "naver_trend_quarterly 최신 2024 Q4 — 참고 지표",
        },
        "change_ix": change_ix_current,
        "macro": {
            "current_base_rate": rate_data.get("current"),
            "base_rate_trend": rate_data.get("trend"),
            "samples": rate_data.get("samples", []),
        },
        "forecast": {
            "score": parsed.forecast_score,
            "direction": parsed.forecast_direction,
            "confidence": parsed.forecast_confidence,
            "horizon_months": _FORECAST_HORIZON_MONTHS,
            "key_drivers": parsed.key_drivers,
            "risks": parsed.risks,
            "narrative": parsed.narrative,
        },
    }

    metrics = {
        "trend_forecast_score": parsed.forecast_score,
        "trend_forecast_direction": parsed.forecast_direction,
        "trend_forecast_confidence": parsed.forecast_confidence,
        "trend_industry_yoy_pct": industry_data.get("yoy_change_pct"),
        "trend_change_ix_label": change_ix_current.get("change_ix_label"),
        "trend_base_rate": rate_data.get("current"),
    }

    # [6] Redis 저장 (try/finally aclose — 누수 방지)
    if _redis is not None:
        try:
            await _redis.set(
                cache_key,
                json.dumps({"report": report, "metrics": metrics}, ensure_ascii=False, default=str),
                ex=_CACHE_TTL,
            )
            print(f"[trend_forecaster] 캐시 저장: {cache_key} (TTL: {_CACHE_TTL}s)")
        except Exception as e:
            print(f"[trend_forecaster] 캐시 저장 실패 (무시): {e}")
        finally:
            try:
                await _redis.aclose()
            except Exception:
                pass

    trend_attr = build_attribution(
        agent_id="trend_forecaster",
        display_name="트렌드 전망",
        kind="LLM",
        sources=[
            "naver_trend_industry",
            "naver_trend_quarterly",
            "seoul_adstrd_change_ix",
            "ecos_timeseries",
        ],
        verdict=f"12개월 전망 {parsed.forecast_score}/100 · {parsed.forecast_direction}",
        reasoning=str(parsed.narrative)[:300] if parsed and parsed.narrative else "추세 예측 데이터 기반",
        confidence=0.75,
    )

    return {
        "analysis_results": {
            **state.get("analysis_results", {}),
            "trend_forecast": report,
            "trend_forecaster_result": {"agent_attribution": trend_attr},
        },
        "analysis_metrics": {
            **state.get("analysis_metrics", {}),
            **metrics,
        },
        "current_agent": "trend_forecaster",
        "agent_attribution": trend_attr,
    }
