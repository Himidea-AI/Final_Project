"""demographic_depth agent: 연령·성별·시간대·요일 매출 분해 + 브랜드 타겟 매칭.

설계 메모:
- parallel_analysis_node에 합류되는 4번째 에이전트 (market/population/legal/ranking + demographic)
- 캐시 키: v2:demographic:{brand}:{dong_code}:{industry_filter}
- legal_risks·overall_legal_risk는 건드리지 않음 (synthesis에서 합성)
"""

import asyncio
import json
import logging

import redis.asyncio as aioredis
from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.llms import get_fast_llm
from src.agents.nodes.market_analyst import db_client, market_tool
from src.config.settings import settings
from src.schemas.demographic import (
    AgeShare,
    CoreDemographic,
    DemographicAnalysis,
    DemographicReport,
)
from src.schemas.state import AgentState

logger = logging.getLogger(__name__)

_CACHE_TTL = 86400  # 24h

# 동명 → 코드 폴백 매핑 (legal.py의 _DISTRICT_ZONE_MAP과 일치)
_MAPO_DONG_CODE_FALLBACK: dict[str, str] = {
    # ── 행정동 (16개) ──────────────────────────────────────────
    "서교동": "11440660",
    "합정동": "11440680",
    "망원1동": "11440690",
    "망원2동": "11440700",
    "연남동": "11440710",
    "성산1동": "11440720",
    "성산2동": "11440730",
    "상암동": "11440740",
    "공덕동": "11440545",
    "아현동": "11440555",
    "도화동": "11440585",
    "용강동": "11440590",
    "신수동": "11440630",
    "서강동": "11440655",
    "염리동": "11440610",
    "대흥동": "11440565",
    # ── 법정동 별칭 ────────────────────────────────────────────
    "망원동": "11440690",
    "성산동": "11440720",
}


def _resolve_dong_code(district: str) -> str:
    """target_district가 이미 코드면 그대로, 동명이면 매핑. 매칭 실패 시 서교동 기본값."""
    if district and district.isdigit() and len(district) == 8:
        return district
    return _MAPO_DONG_CODE_FALLBACK.get(district, "11440660")


def _age_to_range(age_key: str) -> str:
    mapping = {
        "10": "10-20",
        "20": "20-30",
        "30": "30-40",
        "40": "40-50",
        "50": "50-60",
        "60+": "60+",
    }
    return mapping.get(age_key, age_key)


def _identify_core_demographic(sales: dict) -> CoreDemographic:
    """age_breakdown + gender_breakdown에서 최대 share 조합."""
    age_br = sales.get("age_breakdown", {})
    gender_br = sales.get("gender_breakdown", {})
    total = sales.get("monthly_sales", 0) or 1  # div-by-zero 방지

    # 최대 연령대
    top_age = max(age_br.items(), key=lambda x: x[1] or 0, default=("20", 0))
    age_bucket_label = _age_to_range(top_age[0])  # "20" → "20-30"

    # 최대 성별
    m = gender_br.get("male", 0) or 0
    f = gender_br.get("female", 0) or 0
    if m == 0 and f == 0:
        gender = "mixed"
    elif abs(m - f) / max(m + f, 1) < 0.1:
        gender = "mixed"
    else:
        gender = "male" if m > f else "female"

    # share 계산: 해당 연령+성별 세그먼트 근사치 = age_share * gender_share
    age_share = (top_age[1] or 0) / total
    gender_denom = max(m + f, 1)
    if gender == "male":
        gender_share = m / gender_denom
    elif gender == "female":
        gender_share = f / gender_denom
    else:
        gender_share = max(m, f) / gender_denom
    combined_share = round(age_share * gender_share, 3) if gender != "mixed" else round(age_share, 3)

    return CoreDemographic(age=age_bucket_label, gender=gender, share=min(combined_share, 1.0))


def _extract_top_3_age_groups(sales: dict) -> list[AgeShare]:
    """age_breakdown에서 상위 3개 (share 내림차순)."""
    age_br = sales.get("age_breakdown", {})
    total = sales.get("monthly_sales", 0) or 1
    sorted_ages = sorted(age_br.items(), key=lambda x: x[1] or 0, reverse=True)[:3]
    return [AgeShare(age_group=k, share=round((v or 0) / total, 3)) for k, v in sorted_ages]


def _extract_peak_hours(sales: dict) -> list[str]:
    """time_breakdown 상위 2개 시간대."""
    tb = sales.get("time_breakdown", {})
    sorted_times = sorted(tb.items(), key=lambda x: x[1] or 0, reverse=True)[:2]
    return [k for k, _ in sorted_times]


def _calc_weekday_weekend_ratio(sales: dict) -> float:
    we = sales.get("weekday_vs_weekend", {})
    wd = we.get("weekday", 0) or 0
    wk = we.get("weekend", 0) or 0
    if wk == 0:
        return 5.0  # 완전 평일 shop을 표현하는 과장값
    return round(wd / wk, 2)


def _build_prompt(
    sales: dict,
    resvis: dict,
    context: dict,
    brand_name: str | None,
    core: CoreDemographic,
    top3: list[AgeShare],
    peak: list[str],
    wd_we: float,
) -> str:
    parts = []
    parts.append(f"### 대상 지역: {sales.get('dong_code')} (분기 {sales.get('quarter')})\n")
    parts.append(f"- 월매출: {sales.get('monthly_sales', 0):,}원\n")
    parts.append(f"- 주 소비층: {core.age} {core.gender} (매출 점유 {core.share * 100:.1f}%)\n")
    parts.append("- 상위 3 연령대: " + ", ".join(f"{a.age_group}({a.share * 100:.1f}%)" for a in top3) + "\n")
    parts.append(f"- 피크 시간대: {', '.join(peak)}\n")
    parts.append(f"- 평일/주말 매출비: {wd_we}\n")
    if resvis.get("resident_rate") is not None:
        parts.append(f"- 거주율: {resvis['resident_rate']:.1f}% / 방문율: {resvis['visitor_rate']:.1f}%\n")
    parts.append(
        f"- 소득 수준: {context.get('income_level', 'unknown')} / 고령 비율: {context.get('elderly_ratio')}%\n"
    )
    parts.append(f"- 인구 추세: {context.get('population_trend', 'unknown')}\n\n")

    if brand_name:
        parts.append(f"### 평가 브랜드: {brand_name}\n")
        parts.append("위 지역 데이터와 브랜드 주 고객층 매칭도를 0~100점으로 평가하고 근거를 설명하세요.\n")
        parts.append("그리고 3~5문장 자연어 요약을 작성하세요.\n")
    else:
        parts.append("3~5문장 자연어 요약만 작성하세요 (매칭 점수·근거는 None).\n")
    return "".join(parts)


def _make_empty_report(dong_code: str, brand_name: str | None) -> dict:
    return DemographicReport(
        core_demographic=CoreDemographic(age="unknown", gender="mixed", share=0.0),
        top_3_age_groups=[],
        peak_consumption_hours=[],
        weekday_weekend_ratio=1.0,
        resident_visitor_ratio=None,
        area_income_level="unknown",
        population_trend="unknown",
        elderly_ratio=None,
        brand_target_match_score=None,
        match_rationale=None,
        narrative=f"{dong_code}: 매출 데이터 부족으로 분석 제한",
    ).model_dump()


async def demographic_depth_node(state: AgentState) -> dict:
    target = state.get("target_district", "서교동")
    dong_code = _resolve_dong_code(target)
    brand_name = state.get("brand_name")
    industry_filter = state.get("industry_filter")

    cache_key = f"v2:demographic:{brand_name or 'nobrand'}:{dong_code}:{industry_filter or 'all'}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = await _redis.get(cache_key)
        if cached:
            print(f"[demographic] 캐시 히트: {cache_key}")
            analysis = dict(state.get("analysis_results", {}) or {})
            analysis["demographic_report"] = json.loads(cached)
            await _redis.aclose()
            return {
                "analysis_results": analysis,
                "current_agent": "demographic_depth",
            }
    except Exception as e:
        print(f"[demographic] Redis 캐시 조회 실패 (무시): {e}")
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass
        _redis = None

    # DB 연결 보장
    if db_client.engine is None:
        await db_client.connect()

    # 3개 병렬 DB 호출
    sales_r, resvis_r, ctx_r = await asyncio.gather(
        market_tool.get_demographic_sales_breakdown(dong_code, industry_filter),
        market_tool.get_realtime_resident_visitor(dong_code),
        market_tool.get_area_income_context(dong_code),
        return_exceptions=True,
    )

    def _safe(x, default):
        if isinstance(x, Exception):
            logger.warning("demographic_depth fetch failed: %s", x)
            return default
        return x

    sales = _safe(sales_r, {"error": "sales fetch failed"})
    resvis = _safe(resvis_r, {"resident_rate": None, "visitor_rate": None, "source_poi": None})
    context = _safe(
        ctx_r,
        {"income_level": "unknown", "population_trend": "unknown", "elderly_ratio": None},
    )

    # 매출 데이터 없으면 기본 리포트
    if sales.get("error") or (sales.get("monthly_sales", 0) or 0) == 0:
        report = _make_empty_report(dong_code, brand_name)
        analysis = dict(state.get("analysis_results", {}) or {})
        analysis["demographic_report"] = report
        # 캐시 핸들 정리
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass
        return {
            "analysis_results": analysis,
            "current_agent": "demographic_depth",
        }

    # 정량 계산
    core = _identify_core_demographic(sales)
    top3 = _extract_top_3_age_groups(sales)
    peak = _extract_peak_hours(sales)
    wd_we = _calc_weekday_weekend_ratio(sales)

    # LLM 호출
    try:
        prompt = _build_prompt(sales, resvis, context, brand_name, core, top3, peak, wd_we)
        llm = get_fast_llm().with_structured_output(DemographicAnalysis)
        analysis_out: DemographicAnalysis = await llm.ainvoke(
            [
                SystemMessage(content="당신은 상권 소비자 분석 전문가입니다. 한국어로 응답."),
                HumanMessage(content=prompt),
            ]
        )
    except Exception as e:
        logger.warning("demographic_depth LLM failed: %s", e)
        analysis_out = DemographicAnalysis(
            narrative=(
                f"{dong_code} 분석: 주 소비층 {core.age} {core.gender} "
                f"(매출 점유 {core.share * 100:.1f}%). 피크 {', '.join(peak)}. "
                f"평일/주말 매출비 {wd_we}."
            ),
            brand_target_match_score=None,
            match_rationale=None,
        )

    # resident/visitor ratio 계산
    rv_ratio = None
    rr = resvis.get("resident_rate")
    vr = resvis.get("visitor_rate")
    if rr is not None and vr is not None and (rr + vr) > 0:
        rv_ratio = round(vr / (rr + vr), 3)

    report = DemographicReport(
        core_demographic=core,
        top_3_age_groups=top3,
        peak_consumption_hours=peak,
        weekday_weekend_ratio=wd_we,
        resident_visitor_ratio=rv_ratio,
        area_income_level=context.get("income_level", "unknown"),
        population_trend=context.get("population_trend", "unknown"),
        elderly_ratio=context.get("elderly_ratio"),
        brand_target_match_score=analysis_out.brand_target_match_score if brand_name else None,
        match_rationale=analysis_out.match_rationale if brand_name else None,
        narrative=analysis_out.narrative,
    ).model_dump()

    # 캐시 저장
    if _redis is None:
        try:
            _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            _redis = None
    if _redis is not None:
        try:
            await _redis.set(
                cache_key,
                json.dumps(report, ensure_ascii=False),
                ex=_CACHE_TTL,
            )
            print(f"[demographic] 캐시 저장: {cache_key} (TTL {_CACHE_TTL}s)")
        except Exception as e:
            print(f"[demographic] 캐시 저장 실패: {e}")
        finally:
            try:
                await _redis.aclose()
            except Exception:
                pass

    analysis_results = dict(state.get("analysis_results", {}) or {})
    analysis_results["demographic_report"] = report
    return {
        "analysis_results": analysis_results,
        "current_agent": "demographic_depth",
    }
