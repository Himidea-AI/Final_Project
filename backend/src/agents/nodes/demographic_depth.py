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
    ReverseTargetSuggestion,
    TargetAlignmentAlert,
)
from src.schemas.state import AgentState

# 동명 → 코드 매핑은 services.dong_resolver 가 SoT (2026-05-04 통합 완료).
# 기존 _MAPO_DONG_CODE_FALLBACK 은 dong_resolver.MAPO_DONG_MAP + _DONG_ALIASES 로 일원화.
from src.services.dong_resolver import resolve_dong_code_or_default

logger = logging.getLogger(__name__)

_CACHE_TTL = 86400  # 24h


def _resolve_dong_code(district: str) -> str:
    """target_district가 이미 코드면 그대로, 동명이면 매핑. 매칭 실패 시 서교동 기본값.

    NOTE: 시그니처/반환값 동일 — 기존 호출자(demographic_depth_node, 테스트) 영향 없음.
    """
    return resolve_dong_code_or_default(district)


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


# ---------------------------------------------------------------------------
# 사용자 타겟 vs 실측 분포 정렬 평가
# ---------------------------------------------------------------------------
# 사용자 입력 형식 → DB age_breakdown 키 매핑. 한국어 "30대" / 영문 "30s" 양쪽 흡수.
_AGE_INPUT_TO_KEY: dict[str, str] = {
    "10대": "10",
    "20대": "20",
    "30대": "30",
    "40대": "40",
    "50대": "50",
    "60대": "60+",
    "60대+": "60+",
    "60+": "60+",
    "10s": "10",
    "20s": "20",
    "30s": "30",
    "40s": "40",
    "50s": "50",
    "60s": "60+",
}

# operating_hours 한국어 카테고리 → time_breakdown 키. UI 가 어떤 라벨을 쓰든 흡수.
_HOURS_LABEL_TO_KEYS: dict[str, list[str]] = {
    "새벽": ["00-06"],
    "아침": ["06-11"],
    "오전": ["06-11"],
    "점심": ["11-14"],
    "오후": ["14-17"],
    "저녁": ["17-21"],
    "밤": ["21-24"],
    "심야": ["21-24", "00-06"],
}

# target_time_slots ('time_HH_HH') → time_breakdown 키.
_TIME_SLOT_TO_KEY: dict[str, str] = {
    "time_00_06": "00-06",
    "time_06_11": "06-11",
    "time_11_14": "11-14",
    "time_14_17": "14-17",
    "time_17_21": "17-21",
    "time_21_24": "21-24",
}

# 객단가 구간 → 추정 income tier. 동의 area_income_level(high/mid/low) 와 비교용.
# 5천원 이하는 박리다매, 1.5만원 이상은 프리미엄. 기준은 마포구 카페·요식 평균(2026 기준 추정).
_PRICE_TO_TIER: dict[str, str] = {
    "lt5k": "low",
    "5to10k": "mid",
    "10to15k": "mid",
    "15to20k": "high",
    "gt15k": "high",
    "gt20k": "high",
}


def _normalize_age_inputs(values: list[str]) -> list[str]:
    """사용자 타겟 연령 입력을 age_breakdown key 형식으로 정규화. 미상은 제외."""
    out: list[str] = []
    for v in values or []:
        key = _AGE_INPUT_TO_KEY.get(str(v).strip())
        if key and key not in out:
            out.append(key)
    return out


def _user_time_keys(operating_hours: list[str], time_slots: list[str]) -> list[str]:
    """operating_hours(한국어) + target_time_slots(코드) 합집합을 time_breakdown 키로 변환."""
    keys: set[str] = set()
    for h in operating_hours or []:
        for k in _HOURS_LABEL_TO_KEYS.get(str(h).strip(), []):
            keys.add(k)
    for ts in time_slots or []:
        k = _TIME_SLOT_TO_KEY.get(str(ts).strip())
        if k:
            keys.add(k)
    return list(keys)


def _age_label(key: str) -> str:
    """age_breakdown 키 → 사용자 친화 라벨."""
    return "60대+" if key == "60+" else f"{key}대"


def _evaluate_target_alignment(
    state: dict,
    sales: dict,
    core: CoreDemographic,
    top3: list[AgeShare],
    peak: list[str],
    wd_we_ratio: float,
    income_level: str,
) -> tuple[list[TargetAlignmentAlert], float | None]:
    """사용자 입력 타겟 vs 실측 매출·소득 분포 매칭.

    각 차원(age/gender/hours/day/price) 별로 0-100 점수 산출 → 평균이 alignment_score.
    점수가 60 미만인 차원은 severity 와 함께 alert 로 노출. 입력이 None/[] 인 차원은
    skip(점수·alert 모두 미반영).
    """
    age_groups = state.get("target_age_groups") or []
    gender = state.get("target_gender")
    op_hours = state.get("operating_hours") or []
    time_slots = state.get("target_time_slots") or []
    day_type = state.get("target_day_type")
    price_range = state.get("target_price_range")

    alerts: list[TargetAlignmentAlert] = []
    scores: list[float] = []

    # ── age ────────────────────────────────────────────────────────────────
    user_age_keys = _normalize_age_inputs(age_groups)
    if user_age_keys:
        top_keys = [a.age_group for a in top3]
        # 차원 점수 = user 타겟 그룹들의 평균 매칭 점수.
        # top1=100, top2=70, top3=50, 외부=share*200(최대 30)
        per_user_scores: list[float] = []
        for uk in user_age_keys:
            if uk == top_keys[0] if top_keys else False:
                per_user_scores.append(100.0)
            elif len(top_keys) > 1 and uk == top_keys[1]:
                per_user_scores.append(70.0)
            elif len(top_keys) > 2 and uk == top_keys[2]:
                per_user_scores.append(50.0)
            else:
                # top3 외 — share 비율로 부분 점수 (최대 30)
                age_br = sales.get("age_breakdown", {}) or {}
                total = sales.get("monthly_sales", 0) or 1
                outside_share = (age_br.get(uk, 0) or 0) / total
                per_user_scores.append(min(30.0, outside_share * 200))
        age_score = sum(per_user_scores) / len(per_user_scores)
        scores.append(age_score)
        if age_score < 60:
            severity = "high" if age_score < 35 else "medium"
            top1 = top_keys[0] if top_keys else "unknown"
            top1_share = round((top3[0].share * 100) if top3 else 0, 1)
            alerts.append(
                TargetAlignmentAlert(
                    dimension="age",
                    severity=severity,
                    user_input=", ".join(_age_label(k) for k in user_age_keys),
                    actual=f"{_age_label(top1)} {top1_share}% (1위)",
                    message=(
                        f"입력 타겟({', '.join(_age_label(k) for k in user_age_keys)})이 "
                        f"실 매출 1위 연령대({_age_label(top1)})와 어긋남."
                    ),
                )
            )

    # ── gender ─────────────────────────────────────────────────────────────
    if gender in ("male", "female"):
        if core.gender == "mixed":
            gender_score = 70.0
        elif core.gender == gender:
            gender_score = 100.0
        else:
            gender_score = 20.0
        scores.append(gender_score)
        if gender_score < 60:
            label_ko = {"male": "남성", "female": "여성", "mixed": "혼재"}
            alerts.append(
                TargetAlignmentAlert(
                    dimension="gender",
                    severity="high" if gender_score < 35 else "medium",
                    user_input=label_ko.get(gender, gender),
                    actual=label_ko.get(core.gender, core.gender),
                    message=(
                        f"입력 타겟 성별({label_ko.get(gender, gender)})과 "
                        f"실 소비 주류({label_ko.get(core.gender, core.gender)})가 다름."
                    ),
                )
            )

    # ── hours ──────────────────────────────────────────────────────────────
    user_t_keys = _user_time_keys(op_hours, time_slots)
    if user_t_keys and peak:
        # 사용자 시간대가 매출 피크 top2 와 얼마나 겹치는지.
        overlap = len(set(user_t_keys) & set(peak))
        if overlap >= 2:
            hours_score = 100.0
        elif overlap == 1:
            hours_score = 70.0
        else:
            # 0 — 그래도 user time keys 의 평균 매출 share 로 부분 점수.
            tb = sales.get("time_breakdown", {}) or {}
            total = sales.get("monthly_sales", 0) or 1
            avg_share = sum((tb.get(k, 0) or 0) for k in user_t_keys) / max(len(user_t_keys), 1) / total
            hours_score = min(40.0, avg_share * 200)
        scores.append(hours_score)
        if hours_score < 60:
            alerts.append(
                TargetAlignmentAlert(
                    dimension="hours",
                    severity="high" if hours_score < 35 else "medium",
                    user_input=", ".join(sorted(user_t_keys)),
                    actual=f"피크 {', '.join(peak)}",
                    message=(
                        f"입력 영업·타겟 시간대({', '.join(sorted(user_t_keys))})와 "
                        f"실 매출 피크({', '.join(peak)})가 어긋남."
                    ),
                )
            )

    # ── day ────────────────────────────────────────────────────────────────
    if day_type in ("weekday", "weekend"):
        # weekday_weekend_ratio > 1 → 평일우위, < 1 → 주말우위
        is_weekday_dominant = wd_we_ratio > 1.1
        is_weekend_dominant = wd_we_ratio < 0.9
        match = (day_type == "weekday" and is_weekday_dominant) or (day_type == "weekend" and is_weekend_dominant)
        opposite = (day_type == "weekday" and is_weekend_dominant) or (day_type == "weekend" and is_weekday_dominant)
        day_score = 100.0 if match else (30.0 if opposite else 65.0)
        scores.append(day_score)
        if day_score < 60:
            actual_dominant = "주말 우위" if is_weekend_dominant else ("평일 우위" if is_weekday_dominant else "균형")
            label_ko = {"weekday": "평일", "weekend": "주말"}
            alerts.append(
                TargetAlignmentAlert(
                    dimension="day",
                    severity="high" if day_score < 35 else "medium",
                    user_input=label_ko.get(day_type, day_type),
                    actual=f"{actual_dominant} (평일/주말비 {wd_we_ratio})",
                    message=(
                        f"입력 타겟 요일({label_ko.get(day_type, day_type)})과 "
                        f"실 매출 분포({actual_dominant})가 어긋남."
                    ),
                )
            )

    # ── price ──────────────────────────────────────────────────────────────
    if price_range and income_level in ("high", "mid", "low"):
        user_tier = _PRICE_TO_TIER.get(str(price_range).strip(), "mid")
        # high price + low income, low price + high income 은 미스매치.
        # 같은 등급은 100, 한 단계 차이는 70, 두 단계는 30.
        order = {"low": 0, "mid": 1, "high": 2}
        diff = abs(order[user_tier] - order[income_level])
        price_score = {0: 100.0, 1: 70.0, 2: 30.0}[diff]
        scores.append(price_score)
        if price_score < 60:
            alerts.append(
                TargetAlignmentAlert(
                    dimension="price",
                    severity="high" if price_score < 35 else "medium",
                    user_input=f"{price_range} ({user_tier} 가격대)",
                    actual=f"동 소득 {income_level}",
                    message=(f"객단가({price_range}, {user_tier} 등급)와 동 소득 수준({income_level})이 어긋남."),
                )
            )

    if not scores:
        return [], None
    overall = round(sum(scores) / len(scores), 1)
    return alerts, overall


def _alignment_from_report(state: dict, report: dict) -> tuple[list[dict], float | None]:
    """캐시 히트 경로용 — 저장된 report dict 만으로 alignment 재계산.

    캐시는 base demographic 만 저장하고 사용자 입력은 캐시 키에 포함하지 않음
    (사용자별 키 폭발 방지). 따라서 hit 경로에서도 사용자 입력에 맞춰 alignment 를
    매번 새로 계산해 report 에 덮어씀.
    """
    if not isinstance(report, dict):
        return [], None
    try:
        core_dict = report.get("core_demographic") or {}
        core = CoreDemographic(
            age=core_dict.get("age", "unknown"),
            gender=core_dict.get("gender", "mixed"),
            share=float(core_dict.get("share", 0.0) or 0.0),
        )
        top3 = [
            AgeShare(age_group=a.get("age_group", ""), share=float(a.get("share", 0.0) or 0.0))
            for a in (report.get("top_3_age_groups") or [])
            if isinstance(a, dict) and a.get("age_group")
        ]
        peak = list(report.get("peak_consumption_hours") or [])
        wd_we = float(report.get("weekday_weekend_ratio", 1.0) or 1.0)
        income_level = str(report.get("area_income_level", "unknown") or "unknown")
        # cached report 에는 raw sales 가 없음 — outside-top3 share fallback 만 영향받고
        # top1/top2/top3 매칭은 그대로 동작. 미스매치 검출엔 충분.
        sales_stub = {"age_breakdown": {}, "monthly_sales": 1, "time_breakdown": {}}
        alerts, score = _evaluate_target_alignment(state, sales_stub, core, top3, peak, wd_we, income_level)
        return [a.model_dump() for a in alerts], score
    except Exception as e:
        logger.warning("[demographic] alignment from cache 실패 (무시): %s", e)
        return [], None


# 영문 income_level → 권장 객단가 구간. 가격대 vs 소득 매칭 룰 (_PRICE_TO_TIER) 의 역방향.
_INCOME_TO_PRICE: dict[str, str] = {
    "low": "lt5k",
    "mid": "5to10k",
    "high": "10to15k",
}

# time_breakdown 키 → 한국어 영업시간 카테고리 (역방향: _HOURS_LABEL_TO_KEYS).
# 한 키가 여러 라벨에 매핑될 수 있어 "가장 일반적인" 단일 라벨로 매핑.
_TIME_KEY_TO_LABEL: dict[str, str] = {
    "00-06": "심야",
    "06-11": "아침",
    "11-14": "점심",
    "14-17": "오후",
    "17-21": "저녁",
    "21-24": "밤",
}


def _build_reverse_suggestion(
    alerts: list[TargetAlignmentAlert],
    core: CoreDemographic,
    top3: list[AgeShare],
    peak: list[str],
    wd_we_ratio: float,
    income_level: str,
) -> ReverseTargetSuggestion | None:
    """alert 중 high 가 1개 이상이면 실측 기반 권장 타겟 프로필 생성.

    "이 입지를 그대로 두고 타겟·운영전략을 바꿔서 정렬도 90+ 만들려면 이렇게" 의
    역제안. 입지가 고정일 때 사용자가 객단가·운영시간·홍보 타겟을 재정의할
    근거로 활용.
    """
    has_high = any(a.severity == "high" for a in alerts)
    if not has_high:
        return None

    # 권장 연령 — 매출 상위 1-2개 (top3 중 share 5% 이상만).
    rec_ages: list[str] = []
    for a in top3[:2]:
        if a.share >= 0.05:
            rec_ages.append(_age_label(a.age_group))

    # 권장 성별 — core 가 mixed 면 None.
    rec_gender: str | None = None
    if core.gender in ("male", "female"):
        rec_gender = core.gender

    # 권장 시간대 — 피크 top2 를 한국어 라벨로.
    rec_hours: list[str] = []
    seen: set[str] = set()
    for tk in peak[:2]:
        label = _TIME_KEY_TO_LABEL.get(tk)
        if label and label not in seen:
            rec_hours.append(label)
            seen.add(label)

    # 권장 요일 — wd_we_ratio 로 판정.
    rec_day: str | None = None
    if wd_we_ratio > 1.1:
        rec_day = "weekday"
    elif wd_we_ratio < 0.9:
        rec_day = "weekend"

    # 권장 객단가 — 동 income_level 매핑.
    rec_price = _INCOME_TO_PRICE.get(income_level)

    # rationale — 실측 근거 1-2 문장.
    parts: list[str] = []
    if rec_ages:
        parts.append(f"매출 상위 연령대 {', '.join(rec_ages)}")
    if rec_hours:
        parts.append(f"피크 시간대 {', '.join(rec_hours)}")
    if rec_day:
        parts.append("평일 우위" if rec_day == "weekday" else "주말 우위")
    if rec_price:
        parts.append(f"동 소득 {income_level} → {rec_price} 객단가")
    base = " · ".join(parts) if parts else "실측 분포"
    rationale = f"이 입지의 실 소비층은 {base}. 타겟·운영전략을 이에 맞춰 재정의하면 정렬도 향상 가능."

    return ReverseTargetSuggestion(
        recommended_age_groups=rec_ages,
        recommended_gender=rec_gender,
        recommended_hours=rec_hours,
        recommended_day_type=rec_day,
        recommended_price_range=rec_price,
        rationale=rationale,
    )


def _reverse_from_report(report: dict, alerts_dicts: list[dict]) -> dict | None:
    """캐시 hit 경로용 — report dict + 새로 계산된 alerts dict 로 역제안 생성."""
    if not alerts_dicts:
        return None
    try:
        core_dict = report.get("core_demographic") or {}
        core = CoreDemographic(
            age=core_dict.get("age", "unknown"),
            gender=core_dict.get("gender", "mixed"),
            share=float(core_dict.get("share", 0.0) or 0.0),
        )
        top3 = [
            AgeShare(age_group=a.get("age_group", ""), share=float(a.get("share", 0.0) or 0.0))
            for a in (report.get("top_3_age_groups") or [])
            if isinstance(a, dict) and a.get("age_group")
        ]
        peak = list(report.get("peak_consumption_hours") or [])
        wd_we = float(report.get("weekday_weekend_ratio", 1.0) or 1.0)
        income_level = str(report.get("area_income_level", "unknown") or "unknown")
        # alerts_dicts → TargetAlignmentAlert 로 복원
        alerts_objs = [
            TargetAlignmentAlert(**a)
            for a in alerts_dicts
            if isinstance(a, dict) and a.get("dimension") and a.get("severity")
        ]
        sug = _build_reverse_suggestion(alerts_objs, core, top3, peak, wd_we, income_level)
        return sug.model_dump() if sug else None
    except Exception as e:
        logger.warning("[demographic] reverse suggestion 생성 실패 (무시): %s", e)
        return None


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

    # v4: target_alignment 필드 추가 (base report 만 캐시, alignment 는 사용자 입력별 fresh).
    # v5: reverse_target_suggestion 필드 추가 (사용자 입력별 fresh, 캐시 무관).
    cache_key = f"v5:demographic:{brand_name or 'nobrand'}:{dong_code}:{industry_filter or 'all'}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = await _redis.get(cache_key)
        if cached:
            print(f"[demographic] 캐시 히트: {cache_key}")
            analysis = dict(state.get("analysis_results", {}) or {})
            _cached_report = json.loads(cached)
            # 사용자 입력 타겟 정렬은 캐시 키에 안 포함 — hit 경로에서 매번 fresh 계산.
            _alerts: list = []
            _ascore: float | None = None
            if isinstance(_cached_report, dict):
                _alerts, _ascore = _alignment_from_report(state, _cached_report)
                _cached_report["target_alignment"] = _alerts
                _cached_report["target_alignment_score"] = _ascore
                _cached_report["reverse_target_suggestion"] = _reverse_from_report(_cached_report, _alerts)
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
            _cached_verdict = f"주 소비층 {_age} {_gender} ({_share_pct}%)"
            if isinstance(_ascore, (int, float)):
                _cached_verdict += f" · 타겟 정렬 {_ascore:.0f}/100"
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
                verdict=_cached_verdict,
                reasoning=(_cached_report.get("narrative", "") if isinstance(_cached_report, dict) else "")
                or "소비자 심층 분석 (캐시)",
                confidence=0.85,
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

    # 사용자 입력 타겟 정렬 평가 (실측 기반 — 캐시 저장본은 base report 만, alignment 는
    # 항상 사용자 입력 따라 fresh 계산. 캐시 키에 사용자 입력 포함하지 않는 이유.)
    income_level = str(context.get("income_level", "unknown") or "unknown")
    alignment_alerts, alignment_score = _evaluate_target_alignment(state, sales, core, top3, peak, wd_we, income_level)
    reverse_suggestion = _build_reverse_suggestion(alignment_alerts, core, top3, peak, wd_we, income_level)

    base_report = DemographicReport(
        core_demographic=core,
        top_3_age_groups=top3,
        peak_consumption_hours=peak,
        weekday_weekend_ratio=wd_we,
        resident_visitor_ratio=rv_ratio,
        area_income_level=income_level,
        population_trend=context.get("population_trend", "unknown"),
        elderly_ratio=context.get("elderly_ratio"),
        brand_target_match_score=analysis_out.brand_target_match_score if brand_name else None,
        match_rationale=analysis_out.match_rationale if brand_name else None,
        narrative=analysis_out.narrative,
        target_alignment=alignment_alerts,
        target_alignment_score=alignment_score,
        reverse_target_suggestion=reverse_suggestion,
    ).model_dump()

    # 캐시는 alignment + 역제안 제외한 base 만 저장 — 사용자 입력별 키 폭발 방지.
    cacheable_report = {
        **base_report,
        "target_alignment": [],
        "target_alignment_score": None,
        "reverse_target_suggestion": None,
    }
    if _redis is None:
        try:
            _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        except Exception:
            _redis = None
    if _redis is not None:
        try:
            await _redis.set(
                cache_key,
                json.dumps(cacheable_report, ensure_ascii=False),
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

    # state 에는 alignment 포함된 full report 주입.
    report = base_report
    analysis_results = dict(state.get("analysis_results", {}) or {})
    analysis_results["demographic_report"] = report

    try:
        _share_pct_main = round(float(core.share) * 100, 1)
    except Exception:
        _share_pct_main = 0
    _verdict_main = f"주 소비층 {core.age} {core.gender} ({_share_pct_main}%)"
    if alignment_score is not None:
        _verdict_main += f" · 타겟 정렬 {alignment_score:.0f}/100"
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
        verdict=_verdict_main,
        reasoning=str(analysis_out.narrative)
        if analysis_out and analysis_out.narrative
        else "소비자 심층 분석 데이터 기반",
        confidence=0.85,
    )
    analysis_results["demographic_depth_result"] = {"agent_attribution": demo_attr}

    return {
        "analysis_results": analysis_results,
        "current_agent": "demographic_depth",
        "agent_attribution": demo_attr,
    }
