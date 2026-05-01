"""competitor_intel 하이브리드 에이전트 노드.

Python 서비스 3개(경쟁 지형 / 카니발 / 브랜드 벤치마크 / 폐업 추세) 결과를
LLM 이 종합해 차별화 전략·기회·리스크·권고 액션을 생성한다.

출력은 `state["competitor_intel_result"]` 에 저장. legal_node 및 다른 에이전트
결과와 독립적으로 병렬 실행 가능.
"""

from __future__ import annotations

import asyncio
import json
import logging

import redis.asyncio as aioredis
from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.llms import get_fast_llm
from src.agents.nodes._attribution_helpers import build_attribution
from src.config.settings import settings
from src.schemas.state import AgentState
from src.schemas.structured_output import CompetitorIntelOutput
from src.services.brand_profile import get_brand_benchmark, get_industry_peer_brands
from src.services.commercial_intelligence import (
    analyze_cannibalization,
    analyze_competition,
    get_industry_closure_trend,
)
from src.services.dong_resolver import resolve_dong_code

logger = logging.getLogger(__name__)

_CACHE_TTL = 86400  # 24시간

# 브랜드 → (kakao category 키워드, store_quarterly 업종 코드, cannibal 업종 라벨)
# 2026-04-20 실측으로 확정. kakao_store/store_quarterly 모두 '커피-음료' = CS100010.
BRAND_INDUSTRY_MAP: dict[str, tuple[str, str, str]] = {
    # 커피
    "이디야커피": ("커피", "CS100010", "cafe"),
    "빽다방": ("커피", "CS100010", "cafe"),
    "메가MGC커피": ("커피", "CS100010", "cafe"),
    "스타벅스": ("커피", "CS100010", "cafe"),
    "투썸플레이스": ("커피", "CS100010", "cafe"),
    "컴포즈커피": ("커피", "CS100010", "cafe"),
    # 치킨
    "교촌치킨": ("치킨", "CS100007", "chicken"),
    "BBQ": ("치킨", "CS100007", "chicken"),
    "BHC": ("치킨", "CS100007", "chicken"),
    # 패스트푸드/버거
    "맘스터치": ("버거", "CS100006", "burger"),
    "롯데리아": ("버거", "CS100006", "burger"),
    "버거킹": ("버거", "CS100006", "burger"),
    # 베이커리 (FTC 등록됨, 확장 대비)
    "파리바게뜨": ("베이커리", "CS100009", "default"),
    "뚜레쥬르": ("베이커리", "CS100009", "default"),
}

# business_type → industry 매핑 (brand_name 매칭 실패 시 fallback)
BUSINESS_TYPE_FALLBACK: dict[str, tuple[str, str, str]] = {
    "cafe": ("커피", "CS100010", "cafe"),
    "coffee": ("커피", "CS100010", "cafe"),
    "카페": ("커피", "CS100010", "cafe"),
    "chicken": ("치킨", "CS100007", "chicken"),
    "치킨": ("치킨", "CS100007", "chicken"),
    "burger": ("버거", "CS100006", "burger"),
    "버거": ("버거", "CS100006", "burger"),
}

# LLM 시스템 프롬프트 — 프랜차이즈 본사 영업팀 관점
_SYSTEM_PROMPT = """[AGENT: competitor_intel] 경쟁 인텔리전스 에이전트 — LangSmith 식별용 라벨.

당신은 프랜차이즈 본사 영업팀을 지원하는 경쟁 분석 전문가입니다.
주어진 경쟁 지형·카니발리제이션·브랜드 벤치마크 데이터를 종합해 신규 출점 시의
시장 진입 신호와 차별화 전략을 제시하세요.

원칙:
- 데이터에 근거한 실사 가능한 권고를 제시할 것 (추상적 조언 금지)
- key_opportunities/risks 는 반드시 구체적 수치 포함 (예: '500m 내 경쟁점 3개, 포화도 medium')
- narrative 는 본사 의사결정자가 바로 쓸 수 있는 3~5줄 요약

market_entry_signal 판정 기준 (반드시 아래 임계값 기준으로 판단):
- green:  카니발율 <5%  AND  포화도 sparse/low        → 블루오션, 적극 진출 권고
- yellow: 카니발율 5~15% OR  포화도 medium           → 조건부 진출 (차별화 전략 필수)
- red:    카니발율 >15% OR   포화도 high/saturated   → 강력 재검토 권고, 대안 지역 탐색

마포구 상권 밀집도 참고 기준 (500m 반경):
- sparse:    동종 경쟁점 0~2개
- low:       3~5개
- medium:    6~10개
- high:      11~20개
- saturated: 21개 이상
"""


def _resolve_industry(brand_name: str, business_type: str) -> tuple[str, str | None, str]:
    """brand_name 우선, 없으면 business_type fallback. 그래도 없으면 default."""
    if brand_name in BRAND_INDUSTRY_MAP:
        return BRAND_INDUSTRY_MAP[brand_name]
    if business_type in BUSINESS_TYPE_FALLBACK:
        return BUSINESS_TYPE_FALLBACK[business_type]
    return ("", None, "default")


async def _try_cache_get(cache_key: str) -> dict | None:
    """Redis 캐시 조회. 실패 시 None 반환 + 연결 정리."""
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = await _redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"[competitor_intel] 캐시 조회 실패: {e}")
    finally:
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass
    return None


async def _try_cache_set(cache_key: str, payload: dict) -> None:
    """Redis 캐시 저장. 실패 무시."""
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        await _redis.setex(cache_key, _CACHE_TTL, json.dumps(payload, ensure_ascii=False, default=str))
    except Exception as e:
        logger.warning(f"[competitor_intel] 캐시 저장 실패: {e}")
    finally:
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass


def _run_data_collection(dong_code: str, brand_name: str, keyword: str, ind_code: str | None, ind_label: str) -> dict:
    """Python 서비스 4개 호출 (동기). asyncio.to_thread 로 래핑해서 사용."""
    comp_500 = analyze_competition(dong_code, keyword, radius_m=500)
    comp_1000 = analyze_competition(dong_code, keyword, radius_m=1000)
    cannibal = analyze_cannibalization(dong_code, brand_name, radius_m=2000, industry=ind_label)
    brand_bench = get_brand_benchmark(brand_name)
    peers: list[dict] = []
    if brand_bench.get("benchmark_available") and brand_bench.get("industry_medium"):
        peers = get_industry_peer_brands(brand_bench["industry_medium"], top_n=5)
    closure_trend = None
    if ind_code:
        closure_trend = get_industry_closure_trend(dong_code, ind_code)
    return {
        "competition_500m": comp_500,
        "competition_1000m": comp_1000,
        "cannibalization": cannibal,
        "brand_benchmark": brand_bench,
        "peer_brands": peers,
        "industry_closure_trend": closure_trend,
    }


def _compute_adjusted_revenue(brand_bench: dict, cannibal: dict, comp_500: dict) -> int | None:
    """전국 평균 매출에 카니발 + 포화도 보정 적용."""
    if not brand_bench.get("benchmark_available"):
        return None
    base = brand_bench.get("avg_sales_per_store")
    if not base:
        return None
    cannibal_impact = cannibal.get("estimated_revenue_impact_pct") or 0
    saturation_adj = {
        "sparse": 0.10,
        "low": 0.05,
        "medium": 0.0,
        "high": -0.10,
        "saturated": -0.20,
    }.get(comp_500.get("saturation_level", "medium"), 0)
    adjusted = base * (1 + cannibal_impact + saturation_adj)
    return int(adjusted)


def _build_llm_prompt(brand_name: str, dong_name: str, data: dict, adjusted_revenue: int | None) -> str:
    """수집 데이터를 LLM 프롬프트로 정리."""
    comp_500 = data["competition_500m"]
    cannibal = data["cannibalization"]
    bench = data["brand_benchmark"]
    peers = data["peer_brands"]
    trend = data["industry_closure_trend"]

    bench_block = (
        f"전국 가맹점 {bench.get('franchise_count_national')}개, "
        f"연평균 매출 {(bench.get('avg_sales_per_store', 0) / 1e8):.2f}억원, "
        f"폐업률 {(bench.get('closure_rate', 0) * 100):.2f}%"
        if bench.get("benchmark_available")
        else f"FTC 미등재 (이유: {bench.get('reason', 'N/A')})"
    )

    adj_block = (
        f"{(adjusted_revenue / 1e8):.2f}억원 (전국 평균 × (1 + 카니발 + 포화도 보정))"
        if adjusted_revenue is not None
        else "N/A (벤치마크 없음)"
    )

    return f"""후보지: 마포구 {dong_name} / 브랜드: {brand_name}

[500m 경쟁 지형]
- 총 경쟁점: {comp_500.get("total_competitors", "N/A")}개
- 포화도: {comp_500.get("saturation_level")} (score {comp_500.get("saturation_score")})
- 브랜드 분포: {json.dumps(comp_500.get("brand_distribution", {}), ensure_ascii=False)}
- 프랜차이즈 {comp_500.get("franchise_count", 0)}개 / 독립점 {comp_500.get("independent_count", 0)}개

[카니발리제이션 2km]
- 자사 기존 매장: {cannibal.get("same_brand_nearby", 0)}개
- 최근접 거리: {cannibal.get("closest_distance_m")}m
- 거리 분포: {cannibal.get("distance_bins")}
- 예상 매출 잠식률: {(cannibal.get("estimated_revenue_impact_pct", 0) * 100):.1f}%
- 공식: {cannibal.get("impact_method")}

[브랜드 벤치마크] ({brand_name})
- {bench_block}

[업종 경쟁 브랜드 Top 5]
{json.dumps(peers, ensure_ascii=False)}

[이 동 업종 폐업률 추세]
{json.dumps(trend, ensure_ascii=False, default=str) if trend else "N/A"}

[보정 예상 매출]
{adj_block}

위 데이터를 바탕으로 CompetitorIntelOutput 스키마에 따라 답하세요.
"""


async def competitor_intel_node(state: AgentState) -> dict:
    """competitor_intel 노드 — Python 서비스 + LLM 하이브리드."""
    target_district = state.get("target_district", "")
    brand_name = state.get("brand_name", "")
    business_type = state.get("business_type", "")

    logger.info(f"[competitor_intel] 시작 — {target_district} / {brand_name}")
    print(f"--- [COMPETITOR_INTEL] {target_district} / {brand_name} 분석 시작 ---")

    def _make_competitor_attr(
        verdict: str,
        reasoning: str,
        confidence: float = 0.7,
        status: str = "success",
    ) -> dict:
        return build_attribution(
            agent_id="competitor_intel",
            display_name="경쟁 인텔리전스",
            kind="Hybrid",
            sources=["kakao_store", "ftc_brand_franchise", "store_quarterly"],
            verdict=verdict,
            reasoning=reasoning,
            confidence=confidence,
            status=status,
        )

    # brand_name 필수
    if not brand_name:
        _attr = _make_competitor_attr(
            "브랜드명 미입력 · 분석 제한",
            "브랜드명이 없어 카니발리제이션·벤치마크 비교 불가.",
            0.2,
            status="skipped",
        )
        return {
            "competitor_intel_result": {
                "error": "brand_name 이 없어 카니발리제이션 분석을 수행할 수 없습니다.",
                "narrative": "경쟁 정보 분석을 위해 브랜드명 입력이 필요합니다.",
                "agent_attribution": _attr,
            },
            "current_agent": "competitor_intel",
            "agent_attribution": _attr,
        }

    # dong 이름 → code
    dong_code = resolve_dong_code(target_district)
    if not dong_code:
        _attr = _make_competitor_attr(
            "행정동 식별 실패 · 분석 제한",
            f"{target_district} dong_code를 찾지 못해 반경 분석 불가.",
            0.2,
            status="error",
        )
        return {
            "competitor_intel_result": {
                "error": f"dong_code 를 찾을 수 없습니다: {target_district}",
                "narrative": "대상 행정동을 식별할 수 없어 분석을 건너뜁니다.",
                "agent_attribution": _attr,
            },
            "current_agent": "competitor_intel",
            "agent_attribution": _attr,
        }

    # 업종 정보
    keyword, ind_code, ind_label = _resolve_industry(brand_name, business_type)
    if not keyword:
        _attr = _make_competitor_attr(
            "업종 매핑 실패 · 분석 제한",
            f"브랜드/업종 매핑 실패: {brand_name}/{business_type}",
            0.2,
            status="error",
        )
        return {
            "competitor_intel_result": {
                "error": f"브랜드/업종 매핑 실패: {brand_name}/{business_type}",
                "narrative": "지원하지 않는 브랜드/업종 조합입니다.",
                "agent_attribution": _attr,
            },
            "current_agent": "competitor_intel",
            "agent_attribution": _attr,
        }

    # Redis 캐시 조회
    cache_key = f"v2:competitor_intel:{dong_code}:{brand_name}"
    cached = await _try_cache_get(cache_key)
    if cached:
        print(f"[competitor_intel] 캐시 히트: {cache_key}")
        _cached_signal = cached.get("market_entry_signal", "N/A") if isinstance(cached, dict) else "N/A"
        _cached_sat = (
            (cached.get("competition_500m") or {}).get("saturation_level", "N/A") if isinstance(cached, dict) else "N/A"
        )
        _cached_narr = cached.get("narrative", "") if isinstance(cached, dict) else ""
        _cached_attr = _make_competitor_attr(
            f"진입 신호 {_cached_signal} · 포화 {_cached_sat}",
            str(_cached_narr) if _cached_narr else "경쟁 인텔 (캐시 · Pancras 2013 decay 모델 반영)",
            0.8,
        )
        cached_with_attr = dict(cached) if isinstance(cached, dict) else {"cached": cached}
        cached_with_attr["agent_attribution"] = _cached_attr
        return {
            "competitor_intel_result": cached_with_attr,
            "current_agent": "competitor_intel",
            "agent_attribution": _cached_attr,
        }

    # Python 서비스 데이터 수집 (동기 DB 호출이라 별도 스레드)
    try:
        data = await asyncio.to_thread(_run_data_collection, dong_code, brand_name, keyword, ind_code, ind_label)
    except Exception as e:
        logger.exception(f"[competitor_intel] 서비스 호출 실패: {e}")
        _attr = _make_competitor_attr(
            "서비스 호출 실패 · 분석 제한",
            f"경쟁 데이터 수집 오류: {type(e).__name__}",
            0.2,
            status="error",
        )
        return {
            "competitor_intel_result": {
                "error": f"서비스 호출 실패: {type(e).__name__}: {e}",
                "narrative": "경쟁 데이터 수집 중 오류가 발생했습니다.",
                "agent_attribution": _attr,
            },
            "current_agent": "competitor_intel",
            "agent_attribution": _attr,
        }

    adjusted_revenue = _compute_adjusted_revenue(
        data["brand_benchmark"], data["cannibalization"], data["competition_500m"]
    )

    # LLM 해석 (structured output)
    llm = get_fast_llm()
    structured_llm = llm.with_structured_output(CompetitorIntelOutput)

    prompt = _build_llm_prompt(brand_name, target_district, data, adjusted_revenue)
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=prompt)]

    try:
        llm_out: CompetitorIntelOutput = await structured_llm.ainvoke(messages)
        llm_parsed = llm_out.model_dump() if hasattr(llm_out, "model_dump") else dict(llm_out)
        llm_status = "success"
    except Exception as e:
        logger.exception(f"[competitor_intel] LLM 호출 실패: {e}")
        llm_parsed = {
            "market_entry_signal": None,
            "differentiation_position": "LLM 해석 실패 — 데이터만 반환",
            "key_opportunities": [],
            "key_risks": [f"LLM 오류: {type(e).__name__}"],
            "recommended_actions": [],
            "narrative": "경쟁 데이터는 수집됐으나 LLM 종합 해석에 실패했습니다.",
        }
        llm_status = "partial"

    # 최종 payload
    result: dict = {
        **data,
        "adjusted_estimated_revenue": adjusted_revenue,
        **llm_parsed,
        "meta": {
            "dong_code": dong_code,
            "dong_name": target_district,
            "brand_name": brand_name,
            "industry_keyword": keyword,
            "industry_code": ind_code,
            "industry_label": ind_label,
        },
    }

    # 캐시 저장
    await _try_cache_set(cache_key, result)

    competitor_attr = _make_competitor_attr(
        f"진입 신호 {llm_parsed.get('market_entry_signal', 'N/A')} · 포화 {(data.get('competition_500m') or {}).get('saturation_level', 'N/A')}",
        str(llm_parsed.get("narrative") or "")
        or "경쟁 인텔 종합 (Pancras 2013 distance-decay 기반 카니발 보정).",
        0.8,
        status=llm_status,
    )
    result["agent_attribution"] = competitor_attr

    return {
        "competitor_intel_result": result,
        "current_agent": "competitor_intel",
        "agent_attribution": competitor_attr,
    }
