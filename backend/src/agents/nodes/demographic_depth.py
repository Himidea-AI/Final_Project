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
from src.agents.nodes._attribution_helpers import build_attribution
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

# 동명 → 코드 폴백 매핑 (dong_mapping 테이블 기준, 2026-04-22 AWS RDS 실측 검증)
# TODO: 장기적으로 services/population_api.MAPO_DONG_CODES 또는 services/dong_resolver 로 통합해
#       Single Source of Truth 유지 (현재는 방어적 fallback 용도)
_MAPO_DONG_CODE_FALLBACK: dict[str, str] = {
    # ── 행정동 (16개) ──────────────────────────────────────────
    "아현동": "11440555",
    "공덕동": "11440565",
    "도화동": "11440585",
    "용강동": "11440590",
    "대흥동": "11440600",
    "염리동": "11440610",
    "신수동": "11440630",
    "서강동": "11440655",
    "서교동": "11440660",
    "합정동": "11440680",
    "망원1동": "11440690",
    "망원2동": "11440700",
    "연남동": "11440710",
    "성산1동": "11440720",
    "성산2동": "11440730",
    "상암동": "11440740",
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


def _make_empty_report(dong_name: str, brand_name: str | None) -> dict:
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
        narrative=f"{dong_name}: 매출 데이터 부족으로 분석 제한",
    ).model_dump()


async def demographic_depth_node(state: AgentState) -> dict:
    target = state.get("target_district", "서교동")
    dong_code = _resolve_dong_code(target)
    brand_name = state.get("brand_name")
    industry_filter = state.get("industry_filter")

    cache_key = f"v3:demographic:{brand_name or 'nobrand'}:{dong_code}:{industry_filter or 'all'}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = await _redis.get(cache_key)
        if cached:
            print(f"[demographic] 캐시 히트: {cache_key}")
            analysis = dict(state.get("analysis_results", {}) or {})
            _cached_report = json.loads(cached)
            analysis["demographic_report"] = _cached_report
            await _redis.aclose()
            _core = _cached_report.get("core_demographic") if isinstance(_cached_report, dict) else None
            _age = (_core or {}).get("age", "N/A") if isinstance(_core, dict) else "N/A"
            _gender = (_core or {}).get("gender", "") if isinstance(_core, dict) else ""
            _share_raw = (_core or {}).get("share", 0) if isinstance(_core, dict) else 0
            try:
                _share_pct = round(float(_share_raw) * 100, 1)
            except Exception:
                _share_pct = 0
            cached_demo_attr = build_attribution(
                agent_id="demographic_depth",
                display_name="인구 심층분석",
                kind="LLM",
                sources=[
                    "district_sales",
                    "seoul_realtime_hotspots",
                    "kosis_regional_income",
                    "elderly_ratio_region",
                ],
                verdict=f"주 소비층 {_age} {_gender} ({_share_pct}%)",
                reasoning=(_cached_report.get("narrative", "") if isinstance(_cached_report, dict) else "")
                or "소비자 심층 분석 (캐시)",
                confidence=0.8,
            )
            analysis["demographic_depth_result"] = {"agent_attribution": cached_demo_attr}
            return {
                "analysis_results": analysis,
                "current_agent": "demographic_depth",
                "agent_attribution": cached_demo_attr,
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

    # 업종 필터 데이터 없으면 전체 업종으로 재시도 (fallback)
    industry_used = industry_filter
    if industry_filter and (sales.get("error") or (sales.get("monthly_sales", 0) or 0) == 0):
        print(f"[demographic] {dong_code} 업종 {industry_filter} 데이터 없음 → 전체 업종 fallback")
        fallback_r = await market_tool.get_demographic_sales_breakdown(dong_code, None)
        if (
            not isinstance(fallback_r, Exception)
            and not fallback_r.get("error")
            and (fallback_r.get("monthly_sales", 0) or 0) > 0
        ):
            sales = fallback_r
            industry_used = None  # fallback 사용 표시

    # 그래도 데이터 없으면 기본 리포트
    if sales.get("error") or (sales.get("monthly_sales", 0) or 0) == 0:
        report = _make_empty_report(target, brand_name)
        analysis = dict(state.get("analysis_results", {}) or {})
        analysis["demographic_report"] = report
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass
        empty_demo_attr = build_attribution(
            agent_id="demographic_depth",
            display_name="인구 심층분석",
            kind="LLM",
            sources=[
                "district_sales",
                "seoul_realtime_hotspots",
                "kosis_regional_income",
                "elderly_ratio_region",
            ],
            verdict="매출 데이터 없음 · 분석 제한",
            reasoning=f"{target} 매출 레코드 부재로 데모그래픽 심층 분석 제한.",
            confidence=0.3,
            status="skipped",
        )
        analysis["demographic_depth_result"] = {"agent_attribution": empty_demo_attr}
        return {
            "analysis_results": analysis,
            "current_agent": "demographic_depth",
            "agent_attribution": empty_demo_attr,
        }

    # 정량 계산
    core = _identify_core_demographic(sales)
    top3 = _extract_top_3_age_groups(sales)
    peak = _extract_peak_hours(sales)
    wd_we = _calc_weekday_weekend_ratio(sales)

    # LLM 호출
    fallback_note = (
        f"\n※ 해당 업종({industry_filter}) 특화 데이터 부족으로 전체 업종 기준 분석."
        if (industry_filter and industry_used is None)
        else ""
    )
    try:
        prompt = _build_prompt(sales, resvis, context, brand_name, core, top3, peak, wd_we) + fallback_note
        llm = get_fast_llm().with_structured_output(DemographicAnalysis)
        analysis_out: DemographicAnalysis = await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "[AGENT: demographic_depth] 매출 세그먼트 분해 + 타겟 적합도 에이전트 — LangSmith 식별용 라벨.\n\n"
                        "당신은 마포구 상권 소비자 분석 전문가입니다. 한국어로 응답하세요.\n\n"
                        "역할: 연령·성별·시간대·요일 매출 데이터를 분해해 주 고객층을 식별하고,\n"
                        "브랜드의 타겟 고객층과의 적합도를 0~100점으로 평가합니다.\n\n"
                        "brand_target_match_score 채점 기준 (반드시 준수):\n"
                        "- 85~100: 탁월한 적합 — 핵심 타겟 연령·성별이 매출 1위 세그먼트와 90% 이상 일치\n"
                        "- 70~84:  좋은 적합   — 핵심 타겟이 매출 상위 2개 세그먼트 안에 포함\n"
                        "- 50~69:  중간 적합   — 핵심 타겟이 보조 세그먼트에 위치, 피크 시간대 불일치 가능\n"
                        "- 30~49:  낮은 적합   — 타겟 고객층과 실 소비층 간 연령·성별 괴리 뚜렷\n"
                        "- 0~29:   부적합      — 주력 소비층이 브랜드 타겟과 정반대 (예: 고령층 밀집 vs 2030 카페)\n\n"
                        "마포구 상권 특성 참고:\n"
                        "- 서교동·합정동: 20~30대 여성 비중 높음, SNS 소비 활발, 저녁 피크\n"
                        "- 공덕동·아현동: 30~40대 직장인 중심, 점심·퇴근 피크\n"
                        "- 상암동: 20~40대 미디어·IT 종사자, 점심 집중\n"
                        "- 망원동·연남동: 20~30대 로컬 탐방 수요, 주말 강세\n\n"
                        "match_rationale: 점수 근거를 수치 중심으로 2~3문장 설명 (추상 표현 금지).\n"
                        "narrative: 지역 소비 특성과 브랜드 적합성을 예비 창업자가 바로 이해할 수 있게 3~5문장으로 작성."
                    )
                ),
                HumanMessage(content=prompt),
            ]
        )
    except Exception as e:
        logger.warning("demographic_depth LLM failed: %s", e)
        analysis_out = DemographicAnalysis(
            narrative=(
                f"{target} 분석: 주 소비층 {core.age} {core.gender} "
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

    try:
        _share_pct_main = round(float(core.share) * 100, 1)
    except Exception:
        _share_pct_main = 0
    demo_attr = build_attribution(
        agent_id="demographic_depth",
        display_name="인구 심층분석",
        kind="LLM",
        sources=[
            "district_sales",
            "seoul_realtime_hotspots",
            "kosis_regional_income",
            "elderly_ratio_region",
        ],
        verdict=f"주 소비층 {core.age} {core.gender} ({_share_pct_main}%)",
        reasoning=str(analysis_out.narrative)
        if analysis_out and analysis_out.narrative
        else "소비자 심층 분석 데이터 기반",
        confidence=0.8,
    )
    analysis_results["demographic_depth_result"] = {"agent_attribution": demo_attr}

    return {
        "analysis_results": analysis_results,
        "current_agent": "demographic_depth",
        "agent_attribution": demo_attr,
    }
