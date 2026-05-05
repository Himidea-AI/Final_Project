"""법률 룰 엔진 — 8개 결정적 카테고리.

사용자 입력(``business_type``, ``store_area_pyeong``, ``district``)으로
결정 가능한 항목은 룰로 처리. RAG/LLM 호출 없음 — 즉시 (~ms) 반환.

각 룰은 ``dict`` 를 반환:
    {
        "type": "<_BATCH_TYPES>",
        "level": "safe" | "caution" | "danger",
        "summary": "<업종/면적 맞춤 1~2문장>",
        "recommendation": "<체크리스트 형식>",
        "articles": [{"article_ref": "...", "content": "..."}],
    }

``LegalRiskItem`` Pydantic schema 와 직접 1:1 대응되지는 않는다
(schema 에는 ``articles`` 필드가 없음). 다운스트림 호환을 위해 dict 로 반환하며
orchestrator/legal_node 가 그대로 다운스트림에 전달한다.

설계 근거: ``docs/superpowers/specs/2026-05-02-legal-rule-engine-design.md``
"""

from __future__ import annotations

import logging
from math import asin, cos, radians, sin, sqrt

from src.config.constants import BIZ_NORMALIZE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 면적 임계값 — 시행령 별표 기준
# ---------------------------------------------------------------------------

# 다중이용업소법 시행령 제2조: 휴게/일반음식점 다중이용업 정의 (≥100㎡)
MULTI_USE_THRESHOLD_M2: float = 100.0

# 장애인편의증진법 시행령 별표 1: 편의시설 의무 대상 (≥300㎡)
ACCESSIBILITY_THRESHOLD_M2: float = 300.0

# 평 → ㎡ 환산 계수 (1평 = 3.305785㎡, UI 표기 단순화 위해 3.3 사용)
_PYEONG_TO_M2: float = 3.3


def _pyeong_to_m2(pyeong: float) -> float:
    """평수를 제곱미터로 환산. 0 미만은 0 으로 보정."""
    if pyeong is None or pyeong < 0:
        return 0.0
    return float(pyeong) * _PYEONG_TO_M2


def _normalize_biz(business_type: str) -> str:
    """영문/한글 혼용 입력을 한글 라벨로 정규화. 미상이면 입력 그대로."""
    if not business_type:
        return ""
    return BIZ_NORMALIZE.get(business_type.lower(), business_type)


def _format_recommendation(
    article_refs: list[str],
    actions: list[str],
    penalty: str,
) -> str:
    """``[근거: ...] / • 행동 / ❌ 위반 시: ...`` 형식 recommendation 텍스트 생성."""
    refs = ", ".join(article_refs) if article_refs else "관련 법령"
    head = f"[근거: {refs}]"
    body = "\n".join(f"• {a}" for a in actions)
    tail = f"❌ 위반 시: {penalty}"
    return f"{head}\n{body}\n{tail}"


# ---------------------------------------------------------------------------
# 1. food_hygiene — 식품위생법 영업신고
# ---------------------------------------------------------------------------


def rule_food_hygiene(business_type: str) -> dict:
    """카페/음식점/주점은 영업신고 또는 영업허가 필수 (danger).

    - 카페/음식점(휴게/일반음식점) → 영업신고 (식품위생법 제37조 제4항)
    - 주점 → 단란/유흥주점은 영업허가 (제37조 제1항), 일반주점은 영업신고
    - 그 외 업종 → caution (즉석조리 시 신고 의무 발생)
    """
    biz = _normalize_biz(business_type)

    if biz in ("카페", "음식점"):
        level = "danger"
        summary = (
            f"{biz} 영업은 식품위생법상 식품접객업으로 분류되어 영업신고 및 위생교육 이수가 "
            "필수이며, 미이행 시 영업개시 자체가 불가합니다."
        )
        actions = [
            "관할 구청 위생과에 영업신고 (식품위생법 제37조, 영업신고증 수령)",
            "식품접객업 위생교육 6시간 이수 (제41조, 한국외식업중앙회 등 지정 교육기관)",
            "영업장 시설기준 적합 확인 (제36조, 조리장·화장실·환기설비)",
        ]
        recommendation = _format_recommendation(
            ["식품위생법 제37조", "제41조", "제36조"],
            actions,
            "무신고 영업 시 5년 이하 징역 또는 5천만원 이하 벌금 (제97조)",
        )
        articles = [
            {
                "article_ref": "식품위생법 제37조",
                "content": (
                    "휴게음식점·일반음식점·제과점 등 식품접객업을 하려는 자는 "
                    "영업장 소재지 관할 시장·군수·구청장에게 영업신고를 하여야 한다."
                ),
            }
        ]
    elif biz == "주점":
        # 주점 — 단란/유흥주점은 영업허가, 일반주점(호프 등)은 영업신고
        level = "danger"
        summary = (
            f"{biz} 영업은 식품위생법상 식품접객업으로 단란주점·유흥주점은 영업허가(제37조 제1항), "
            "일반주점·호프는 영업신고(제37조 제4항) 대상이며, 미이행 시 영업개시 불가합니다."
        )
        actions = [
            "단란주점/유흥주점 → 관할 구청 위생과 영업허가 신청 (식품위생법 제37조 제1항, 시행령 제21조 제8호)",
            "일반주점/호프 → 관할 구청 위생과 영업신고 (제37조 제4항)",
            "식품접객업 위생교육 6시간 이수 (제41조)",
            "영업장 시설기준 적합 확인 — 객실/객석 구조, 환기설비 (제36조, 시행규칙 별표 14)",
            "유흥주점은 청소년보호법 제2조 청소년출입·고용금지업소 동시 적용",
        ]
        recommendation = _format_recommendation(
            ["식품위생법 제37조 제1항", "제37조 제4항", "시행령 제21조 제8호"],
            actions,
            "무허가/무신고 영업 시 5년 이하 징역 또는 5천만원 이하 벌금 (제97조)",
        )
        articles = [
            {
                "article_ref": "식품위생법 제37조",
                "content": (
                    "유흥주점·단란주점 영업은 시·도지사의 허가를 받아야 한다(제1항). "
                    "휴게음식점·일반음식점·제과점·일반주점 영업은 관할 시장·군수·구청장에게 "
                    "영업신고를 하여야 한다(제4항)."
                ),
            },
            {
                "article_ref": "식품위생법 시행령 제21조",
                "content": (
                    "식품접객업의 종류: 휴게음식점·일반음식점·단란주점·유흥주점·위탁급식·제과점 영업으로 구분한다."
                ),
            },
        ]
    else:
        level = "caution"
        summary = (
            f"{biz or '해당 업종'}은 일반 식품판매업은 영업신고 의무 없으나, "
            "즉석조리·도시락 등 식품접객 행위가 포함되면 휴게음식점 영업신고가 "
            "필수 (시행령 제21조 제8호) — 미신고 시 즉시 danger."
        )
        actions = [
            "즉석조리·도시락 판매 여부 사전 확인 (포함 시 휴게음식점 신고 = danger)",
            "식품접객 무관 시 식품판매업 신고만 진행 (관할 구청 위생과)",
            "포함 시 휴게음식점 영업신고 + 위생교육 이수 필수",
        ]
        recommendation = _format_recommendation(
            ["식품위생법 제37조", "시행령 제21조"],
            actions,
            "즉석조리 포함 매장이 무신고 시 5년 이하 징역 또는 5천만원 이하 벌금 (제97조)",
        )
        articles = [
            {
                "article_ref": "식품위생법 제37조",
                "content": "식품접객업 영업신고 의무 — 즉석조리·도시락 판매 시 적용.",
            }
        ]

    return {
        "type": "food_hygiene",
        "level": level,
        "summary": summary,
        "recommendation": recommendation,
        "articles": articles,
    }


# ---------------------------------------------------------------------------
# 2. safety_regulation — 다중이용업소법
# ---------------------------------------------------------------------------


def rule_safety_regulation(business_type: str, store_area_pyeong: float) -> dict:
    """다중이용업소법 — 면적 ≥100㎡ + 카페/음식점 → danger. 주점은 면적 무관 danger."""
    biz = _normalize_biz(business_type)
    area_m2 = _pyeong_to_m2(store_area_pyeong)

    is_food_biz = biz in ("카페", "음식점")
    if biz == "주점":
        # 다중이용업소법 시행령 제2조 — 단란/유흥주점은 면적 무관 다중이용업.
        # 일반주점은 100㎡ 기준이지만 보수적으로 모두 danger 처리 (안전사고 위험성 ↑).
        level = "danger"
        summary = (
            f"{biz} 영업장은 다중이용업소법 시행령 제2조에 따라 면적과 무관하게 "
            "다중이용업으로 분류되어 안전시설 완비증명서 없이는 영업개시가 불가합니다 "
            f"(현재 {store_area_pyeong:.0f}평 / {area_m2:.1f}㎡)."
        )
        actions = [
            "관할 소방서에 안전시설 등 완비증명서 발급 신청 (다중이용업소법 제9조)",
            "비상구·간이스프링클러·피난유도등·방염물품 시설기준 충족 (제2조, 제13조)",
            "다중이용업주 안전교육 4시간 이수 (제8조)",
            "주점 특화: 객실 내부 잠금장치 금지·내부 구조 점검·화재배상책임보험 가입 (제13조의2)",
        ]
        recommendation = _format_recommendation(
            ["다중이용업소법 제2조", "제9조", "제13조", "제13조의2"],
            actions,
            "안전시설 미비/완비증명 미수령 시 1년 이하 징역 또는 1천만원 이하 벌금",
        )
    elif is_food_biz and area_m2 >= MULTI_USE_THRESHOLD_M2:
        level = "danger"
        summary = (
            f"{biz} 영업장이 {store_area_pyeong:.0f}평({area_m2:.1f}㎡)으로 100㎡ 이상이므로 "
            "다중이용업소법상 안전관리 대상이며, 안전시설 등 완비증명서 없이는 영업개시 불가."
        )
        actions = [
            "관할 소방서에 안전시설 등 완비증명서 발급 신청 (다중이용업소법 제9조)",
            "비상구·간이스프링클러·피난유도등·방염물품 등 시설기준 충족 (제2조, 제13조)",
            "다중이용업주 안전교육 4시간 이수 (제8조)",
        ]
        recommendation = _format_recommendation(
            ["다중이용업소법 제2조", "제9조", "제13조"],
            actions,
            "안전시설 미비/완비증명 미수령 시 1년 이하 징역 또는 1천만원 이하 벌금",
        )
    elif is_food_biz:
        level = "safe"
        summary = (
            f"{biz} 영업장이 {store_area_pyeong:.0f}평({area_m2:.1f}㎡)으로 100㎡ 미만이므로 "
            "다중이용업소법상 다중이용업 정의에 해당하지 않습니다."
        )
        actions = [
            "면적 확장 시 100㎡ 이상이 되면 안전시설 완비증명 의무 발생 — 사전 확인",
        ]
        recommendation = _format_recommendation(
            ["다중이용업소법 시행령 제2조"],
            actions,
            "면적 ≥100㎡ 확장 후 미신고 시 시정명령 + 과태료",
        )
    else:
        level = "safe"
        summary = (
            f"{biz or '해당 업종'}은 다중이용업소법상 다중이용업 분류 대상에서 제외되어 "
            "안전시설 완비증명 의무가 발생하지 않습니다."
        )
        actions = [
            "노래연습장·주점 등 영업 추가 시 다중이용업 해당 여부 재검토",
        ]
        recommendation = _format_recommendation(
            ["다중이용업소법 제2조"],
            actions,
            "다중이용업 신규 추가 시 영업개시 전 안전시설 완비증명 필수",
        )

    articles = [
        {
            "article_ref": "다중이용업소법 제2조",
            "content": (
                "다중이용업이란 영업장의 바닥면적의 합계가 100제곱미터 이상인 휴게음식점·"
                "일반음식점·제과점 영업 등 화재 등 재난 발생 시 생명·신체·재산상의 피해가 "
                "발생할 우려가 높은 영업을 말한다."
            ),
        }
    ]

    return {
        "type": "safety_regulation",
        "level": level,
        "summary": summary,
        "recommendation": recommendation,
        "articles": articles,
    }


# ---------------------------------------------------------------------------
# 3. fire_safety_law — 소방시설법
# ---------------------------------------------------------------------------


def rule_fire_safety(business_type: str, store_area_pyeong: float) -> dict:
    """소방시설법 — 면적 ≥100㎡ → danger / <100㎡ → caution. 주점은 면적 무관 danger."""
    biz = _normalize_biz(business_type)
    area_m2 = _pyeong_to_m2(store_area_pyeong)

    if biz == "주점":
        # 주점은 다중이용업이자 화재위험 업종 — 면적 무관 소방시설 강화 대상.
        level = "danger"
        summary = (
            f"{biz} 영업은 다중이용업소법·소방시설법상 면적과 무관하게 특정소방대상물로 "
            "분류되어 소방시설 설치·자체점검·화재배상책임보험 가입이 의무입니다 "
            f"(현재 {store_area_pyeong:.0f}평 / {area_m2:.1f}㎡)."
        )
        actions = [
            "용도·면적별 소방시설 설치 (소방시설법 제12조, 시행령 별표 4 — 소화기·간이스프링클러)",
            "소방안전관리자 선임 (제24조 / 주점은 객실 구조상 2급 이상 권장)",
            "연 1~2회 자체점검 실시 + 결과 보고 (제22조)",
            "화재배상책임보험 가입 (다중이용업소법 제13조의2 — 주점 의무)",
        ]
        recommendation = _format_recommendation(
            ["소방시설법 제12조", "제22조", "제24조", "다중이용업소법 제13조의2"],
            actions,
            "소방시설 미설치 시 3년 이하 징역 또는 3천만원 이하 벌금 (제57조)",
        )
    elif area_m2 >= MULTI_USE_THRESHOLD_M2:
        level = "danger"
        summary = (
            f"영업장 면적 {store_area_pyeong:.0f}평({area_m2:.1f}㎡)이 100㎡ 이상으로 "
            "소방시설법상 특정소방대상물에 해당하여 소방시설 설치 및 자체점검 의무가 발생합니다."
        )
        actions = [
            "용도·면적별 소방시설 설치 (소방시설법 제12조, 시행령 별표 4 — 소화기·간이스프링클러 등)",
            "소방안전관리자 선임 (제24조 / 영업장 규모에 따라 1·2·3급)",
            "연 1~2회 자체점검 실시 + 결과 보고 (제22조)",
        ]
        recommendation = _format_recommendation(
            ["소방시설법 제12조", "제22조", "제24조"],
            actions,
            "소방시설 미설치 시 3년 이하 징역 또는 3천만원 이하 벌금 (제57조)",
        )
    else:
        level = "caution"
        summary = (
            f"영업장 면적 {store_area_pyeong:.0f}평({area_m2:.1f}㎡)이 100㎡ 미만이지만 "
            "소화기 비치, 비상구 확보 등 기본 소방시설 의무는 모든 영업장에 적용됩니다."
        )
        actions = [
            "소화기 1대 이상 비치 (소방시설법 시행령 별표 4)",
            "비상구·피난통로 확보 및 폐쇄 금지",
            "전기·가스시설 안전 점검",
        ]
        recommendation = _format_recommendation(
            ["소방시설법 제12조", "제22조"],
            actions,
            "소화기 미비치 등 기본 시설 미흡 시 200만원 이하 과태료 (제61조)",
        )

    articles = [
        {
            "article_ref": "소방시설법 제12조",
            "content": (
                "특정소방대상물의 관계인은 대통령령으로 정하는 소방시설을 화재안전기준에 따라 설치·관리하여야 한다."
            ),
        }
    ]

    return {
        "type": "fire_safety_law",
        "level": level,
        "summary": summary,
        "recommendation": recommendation,
        "articles": articles,
    }


# ---------------------------------------------------------------------------
# 4. accessibility_law — 장애인편의증진법
# ---------------------------------------------------------------------------


def rule_accessibility(business_type: str, store_area_pyeong: float) -> dict:
    """면적 ≥300㎡ + 카페/음식점/주점 → danger. <300㎡ → safe."""
    biz = _normalize_biz(business_type)
    area_m2 = _pyeong_to_m2(store_area_pyeong)

    is_food_biz = biz in ("카페", "음식점", "주점")
    if is_food_biz and area_m2 >= ACCESSIBILITY_THRESHOLD_M2:
        level = "danger"
        summary = (
            f"{biz} 영업장이 {store_area_pyeong:.0f}평({area_m2:.1f}㎡)으로 300㎡ 이상이므로 "
            "장애인편의증진법상 편의시설 설치 의무 대상시설(공중이용시설)에 해당합니다."
        )
        actions = [
            "주출입구 경사로·점자블록 설치 (편의증진법 제8조, 시행령 별표 2)",
            "장애인 화장실 1실 이상 설치 (객실/화장실 모두 의무)",
            "장애인 주차구역 1면 이상 (시행규칙 별표 1)",
        ]
        recommendation = _format_recommendation(
            ["장애인편의증진법 제7조", "제8조"],
            actions,
            "편의시설 미설치 시 시정명령 + 3천만원 이하 이행강제금",
        )
    else:
        level = "safe"
        summary = (
            f"영업장 면적 {store_area_pyeong:.0f}평({area_m2:.1f}㎡)이 300㎡ 미만으로 "
            "장애인편의증진법상 편의시설 설치 의무 대상시설에 해당하지 않습니다."
        )
        actions = [
            "면적 확장 시 300㎡ 이상이 되면 편의시설 의무 발생 — 사전 시설 계획 검토",
            "권장: 주출입구 경사로·접근통로 등 임의 설치로 고객층 확대",
        ]
        recommendation = _format_recommendation(
            ["장애인편의증진법 제7조"],
            actions,
            "면적 확장 후 미설치 시 시정명령 + 이행강제금",
        )

    articles = [
        {
            "article_ref": "장애인편의증진법 제7조",
            "content": (
                "공중이용시설 중 대통령령으로 정하는 시설의 시설주는 장애인등이 그 시설을 "
                "이용함에 있어 불편이 없도록 편의시설을 설치하여야 한다."
            ),
        }
    ]

    return {
        "type": "accessibility_law",
        "level": level,
        "summary": summary,
        "recommendation": recommendation,
        "articles": articles,
    }


# ---------------------------------------------------------------------------
# 5. commercial_lease_law — 상가임대차보호법 (항상 caution)
# ---------------------------------------------------------------------------


def rule_commercial_lease() -> dict:
    """모든 임차 영업에 적용 — 항상 caution."""
    summary = (
        "상가건물 임대차계약 체결 시 권리금 회수기회 보호(제10조의4)·계약갱신요구권(10년)"
        "·환산보증금(서울 9억) 등을 반드시 사전 검토해야 합니다."
    )
    actions = [
        "확정일자 부여로 대항력·우선변제권 확보 (상가임대차보호법 제5조)",
        "권리금 회수기회 보호 조항 명문화 — 임대인 방해 금지 (제10조의4)",
        "계약갱신요구권 10년 한도 사전 고지 및 갱신 거절 사유 확인 (제10조)",
        "환산보증금 (서울 9억원) 초과 여부 확인 — 초과 시 보호 범위 축소",
    ]
    recommendation = _format_recommendation(
        ["상가임대차보호법 제10조", "제10조의4", "제5조"],
        actions,
        "임대인의 권리금 회수 방해 시 손해배상 청구 가능 (제10조의4 제3항)",
    )
    articles = [
        {
            "article_ref": "상가임대차보호법 제10조의4",
            "content": (
                "임대인은 임대차기간이 끝나기 6개월 전부터 임대차 종료 시까지 정당한 사유 "
                "없이 임차인이 주선한 신규임차인이 되려는 자로부터 권리금을 지급받는 것을 "
                "방해하여서는 아니 된다."
            ),
        }
    ]
    return {
        "type": "commercial_lease_law",
        "level": "caution",
        "summary": summary,
        "recommendation": recommendation,
        "articles": articles,
    }


# ---------------------------------------------------------------------------
# 6. labor_law — 근로기준법 + 최저임금법 (항상 caution)
# ---------------------------------------------------------------------------


def rule_labor() -> dict:
    """근로자 채용 시 항상 적용 — 항상 caution."""
    summary = (
        "근로자(아르바이트 포함) 채용 시 근로계약서 서면 작성·교부, 최저임금 준수, "
        "주휴수당·가산임금 지급, 4대보험 가입은 모든 사업장에 의무 적용됩니다."
    )
    actions = [
        "근로계약서 서면 작성·교부 (근로기준법 제17조, 미교부 시 500만원 이하 과태료)",
        "최저임금 준수 (최저임금법 제6조, 2026년 시간당 기준 확인)",
        "주 15시간 이상 근무 시 주휴수당 지급 (제55조)",
        "연장·야간·휴일근로 시 가산임금 50% 지급 (제56조)",
        "4대보험 (국민연금·건강보험·고용보험·산재보험) 가입",
    ]
    recommendation = _format_recommendation(
        ["근로기준법 제17조", "제56조", "최저임금법 제6조"],
        actions,
        "임금 미지급 시 3년 이하 징역 또는 3천만원 이하 벌금 (제109조)",
    )
    articles = [
        {
            "article_ref": "근로기준법 제17조",
            "content": (
                "사용자는 근로계약을 체결할 때에 근로자에게 임금, 소정근로시간, 휴일, "
                "연차 유급휴가 등 대통령령으로 정하는 사항을 명시하여야 한다. "
                "근로조건을 서면으로 명시하고 근로자에게 교부하여야 한다."
            ),
        }
    ]
    return {
        "type": "labor_law",
        "level": "caution",
        "summary": summary,
        "recommendation": recommendation,
        "articles": articles,
    }


# ---------------------------------------------------------------------------
# 7. vat_law — 부가가치세법 (항상 caution)
# ---------------------------------------------------------------------------


def rule_vat() -> dict:
    """모든 사업자에 적용 — 항상 caution."""
    summary = (
        "사업 개시 전 사업자등록(개업일 전 20일 이내), 일반과세/간이과세 선택, "
        "세금계산서 발행 의무는 모든 영업자에 공통 적용됩니다."
    )
    actions = [
        "사업자등록 신청 (부가가치세법 제8조, 개업일 전 20일 이내 관할 세무서)",
        "직전연도 공급대가 8천만원 미만 개인사업자는 간이과세자 선택 가능 (제61조)",
        "전자세금계산서 발행 의무 확인 (제32조, 법인사업자/직전연도 공급가액 8천만원 이상)",
        "분기 또는 6개월 단위 부가가치세 신고·납부",
    ]
    recommendation = _format_recommendation(
        ["부가가치세법 제8조", "제32조", "제61조"],
        actions,
        "사업자 미등록 영업 시 공급가액의 1% 가산세 + 매입세액 불공제",
    )
    articles = [
        {
            "article_ref": "부가가치세법 제8조",
            "content": (
                "사업자는 사업장마다 사업 개시일부터 20일 이내에 사업자등록을 신청하여야 한다. "
                "신규로 사업을 시작하려는 자는 사업 개시일 이전이라도 사업자등록을 신청할 수 있다."
            ),
        }
    ]
    return {
        "type": "vat_law",
        "level": "caution",
        "summary": summary,
        "recommendation": recommendation,
        "articles": articles,
    }


# ---------------------------------------------------------------------------
# 8. sewage_law — 하수도법
# ---------------------------------------------------------------------------


def rule_sewage(business_type: str) -> dict:
    """음식점·카페(휴게음식점)·주점 모두 배수설비/그리스트랩 검토 의무.

    - 음식점: 유분 다량 배출 → 그리스트랩 필수 → caution
    - 카페: 휴게음식점 = 식품위생법 시행규칙 별표 14 시설기준 적용 →
            세척수·음료 잔여물 배출 시 배수설비 기준 검토 필요 → caution
    - 주점: 알코올 잔여물·세척수·안주 조리 유분 배출 → 배수설비/그리스트랩 검토 → caution
    - 그 외: safe (조리 무관 업종)
    """
    biz = _normalize_biz(business_type)

    if biz in ("음식점", "카페", "주점"):
        level = "caution"
        if biz == "음식점":
            summary = (
                f"{biz} 영업장은 조리과정에서 발생하는 유분(기름)을 공공하수도로 직접 배출할 수 없어 "
                "유분분리기(그리스트랩) 등 개인하수처리시설 또는 배수설비 설치가 요구됩니다."
            )
            actions = [
                "주방 배수구에 유분분리기(그리스트랩) 설치 (하수도법 제34조, 시행규칙 별표 14)",
                "관할 구청 하수과에 배수설비 설치 신고",
                "정기 청소·점검으로 유분 누적 방지 — 위반 시 시정명령",
            ]
        elif biz == "카페":
            # 카페 (휴게음식점) — 세척수·음료 잔여물 배출 시 배수설비 기준 적용
            summary = (
                "카페(휴게음식점)는 식품위생법 시행규칙 별표 14 시설기준에 따라 "
                "싱크대·세척대 배수구를 하수도법 기준에 맞게 연결해야 하며, "
                "음료 잔여물·세척수 배출 형태에 따라 그리스트랩 설치 검토 필요합니다."
            )
            actions = [
                "주방·세척대 배수설비를 하수도법 기준에 맞게 설치 (제34조)",
                "음용수 제조·우유 가공 등 유분/유기물 배출 시 그리스트랩 또는 침전조 설치 검토",
                "관할 구청 하수과에 배수설비 설치 신고 (식품위생법 별표 14 연계)",
            ]
        else:
            # 주점 — 알코올 잔여물·안주 조리 유분 배출
            summary = (
                "주점 영업장은 알코올 잔여물·안주 조리 시 발생하는 유분과 세척수를 "
                "공공하수도로 직접 배출할 수 없어 유분분리기(그리스트랩) 및 배수설비 설치가 "
                "요구되며, 식품위생법 시행규칙 별표 14 시설기준이 함께 적용됩니다."
            )
            actions = [
                "주방·세척대 배수구에 유분분리기(그리스트랩) 설치 (하수도법 제34조, 시행규칙 별표 14)",
                "알코올 폐액·세척수 배수설비를 하수도법 기준에 맞게 연결",
                "관할 구청 하수과에 배수설비 설치 신고 (식품위생법 별표 14 시설기준 연계)",
                "정기 청소·점검으로 유분 누적 방지 — 위반 시 시정명령",
            ]
        recommendation = _format_recommendation(
            ["하수도법 제34조", "식품위생법 시행규칙 별표 14"],
            actions,
            "배수설비 미설치/기준 위반 시 1천만원 이하 과태료 (제80조)",
        )
        articles = [
            {
                "article_ref": "하수도법 제34조",
                "content": (
                    "공공하수도의 사용자는 공공하수도에 하수를 유입시키기 위하여 필요한 "
                    "배수설비를 설치하여야 한다. 식품접객업(휴게/일반음식점)은 "
                    "유분·유기물 배출량에 따라 개인하수처리시설 설치가 의무이다."
                ),
            }
        ]
    else:
        level = "safe"
        summary = (
            f"{biz or '해당 업종'}은 조리 시설이 없거나 유분 배출량이 적어 "
            "하수도법상 개인하수처리시설(유분분리기) 설치 의무 대상이 아닙니다."
        )
        actions = [
            "조리시설 추가 시 배수설비/유분분리기 설치 의무 재검토",
        ]
        recommendation = _format_recommendation(
            ["하수도법 제34조"],
            actions,
            "조리시설 추가 후 배수설비 미신고 시 시정명령",
        )
        articles = [
            {
                "article_ref": "하수도법 제34조",
                "content": "공공하수도 사용자의 배수설비 설치 의무 — 음식점 외 적용 범위 한정.",
            }
        ]

    return {
        "type": "sewage_law",
        "level": level,
        "summary": summary,
        "recommendation": recommendation,
        "articles": articles,
    }


# ---------------------------------------------------------------------------
# 9. school_zone — 학교환경위생정화구역 (학교보건법 제6조)
# ---------------------------------------------------------------------------

# 학교보건법 제6조 정화구역 거리
SCHOOL_ABSOLUTE_ZONE_M: float = 50.0  # 절대정화구역 (모든 술집/노래방 영업금지)
SCHOOL_RELATIVE_ZONE_M: float = 200.0  # 상대정화구역 (정화위원회 심의 대상)


# fallback mock 학교 (DB 미연동/조회 실패 시)
_MOCK_MAPO_SCHOOLS: list[dict] = [
    {
        "name": "망원초등학교",
        "school_type": "초등학교",
        "lat": 37.5567,
        "lon": 126.9038,
        "district": "망원1동",
    },
    {
        "name": "합정중학교",
        "school_type": "중학교",
        "lat": 37.5495,
        "lon": 126.9112,
        "district": "합정동",
    },
    {
        "name": "서울서교초등학교",
        "school_type": "초등학교",
        "lat": 37.5532,
        "lon": 126.9217,
        "district": "서교동",
    },
    {
        "name": "공덕초등학교",
        "school_type": "초등학교",
        "lat": 37.5435,
        "lon": 126.9519,
        "district": "공덕동",
    },
    {
        "name": "홍익대학교",
        "school_type": "대학교",
        "lat": 37.5511,
        "lon": 126.9249,
        "district": "서교동",
    },
]


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간 구면 거리 (미터) — services/commercial_intelligence 와 동일 공식."""
    R = 6_371_000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


def _fetch_mapo_schools() -> list[dict]:
    """mapo_schools 테이블 SELECT — DB 미연동 시 mock 5개 fallback.

    실패 시 logger.warning 후 mock 반환 (룰 평가는 caution 으로 진행).
    """
    try:
        import os

        from sqlalchemy import text

        from src.database.sync_engine import get_sync_engine

        db_url = os.environ.get("POSTGRES_URL")
        if not db_url:
            logger.warning("[rule_school_zone] POSTGRES_URL 미설정 — mock fallback")
            return list(_MOCK_MAPO_SCHOOLS)

        sql = text(
            """
            SELECT name, school_type, lat, lon, district
              FROM mapo_schools
             WHERE lat IS NOT NULL AND lon IS NOT NULL
            """
        )
        engine = get_sync_engine(db_url)
        with engine.connect() as conn:
            rows = conn.execute(sql).fetchall()

        out = [
            {
                "name": r[0],
                "school_type": r[1],
                "lat": float(r[2]),
                "lon": float(r[3]),
                "district": r[4],
            }
            for r in rows
            if r[0] and r[2] is not None and r[3] is not None
        ]
        if not out:
            logger.warning("[rule_school_zone] mapo_schools 비어 있음 — mock fallback")
            return list(_MOCK_MAPO_SCHOOLS)
        return out
    except Exception as e:
        logger.warning(f"[rule_school_zone] mapo_schools 조회 실패 ({e}) — mock fallback")
        return list(_MOCK_MAPO_SCHOOLS)


def rule_school_zone(
    business_type: str,
    lat: float | None,
    lon: float | None,
    schools: list[dict] | None = None,
) -> dict:
    """학교환경위생정화구역 (학교보건법 제6조) 거리 룰.

    - 절대정화구역 50m: 모든 술집/노래방 금지 → 주점 danger
    - 상대정화구역 200m: 학교환경위생정화위원회 심의 (대부분 거부) → 주점 danger
    - 카페/음식점은 적용 X (safe)

    schools=None 이면 DB 조회. lat/lon 없으면 caution fallback (시뮬 시작 시점 정상 케이스).

    ⚠️ D3 알림 (mock 데이터 위험):
    mapo_schools 테이블이 비어있거나 POSTGRES_URL 미설정이면 ``_fetch_mapo_schools`` 가
    ``_MOCK_MAPO_SCHOOLS`` (5개 학교 좌표) fallback 으로 전환된다. mock 결과는
    실제 마포구 학교 분포의 일부에 불과하므로 danger/safe 판정을 그대로 신뢰하면 안 된다.
    프로덕션 환경에서는 mapo_schools 적재 후에만 정확한 거리 계산을 보장한다.
    """
    biz = _normalize_biz(business_type)

    # 카페/음식점/그 외 → 적용 안 됨
    if biz != "주점":
        return {
            "type": "school_zone",
            "level": "safe",
            "summary": (f"{biz or '해당 업종'}은 학교환경위생정화구역 영업 제한 대상이 아닙니다."),
            "recommendation": (
                "[근거: 학교보건법 제6조] 정화구역 영업제한은 술집·노래방 등에 "
                "한정 적용 — 카페·음식점은 별도 거리 제한 없음."
            ),
            "articles": [
                {
                    "article_ref": "학교보건법 제6조",
                    "content": (
                        "누구든지 학교환경위생정화구역에서는 「식품위생법」에 따른 "
                        "유흥주점·단란주점·노래연습장 등 학생의 보건·위생에 영향을 "
                        "미치는 행위·시설을 하여서는 아니 된다."
                    ),
                }
            ],
        }

    # 좌표 미입력 시 → 보수적 caution
    if lat is None or lon is None:
        return {
            "type": "school_zone",
            "level": "caution",
            "summary": ("주점 영업장 좌표 미입력 — 학교환경위생정화구역 거리 확인이 필요합니다."),
            "recommendation": _format_recommendation(
                ["학교보건법 제6조"],
                [
                    "출점 후보지 좌표(lat/lon) 입력 시 절대(50m)/상대(200m) 정화구역 자동 계산",
                    "관할 교육지원청에 학교환경위생정화구역 도면 사전 확인",
                    "절대정화구역 내 주점 영업은 원천 금지, 상대정화구역은 정화위원회 심의 필요",
                ],
                "정화구역 내 주점 영업 시 영업정지 + 1년 이하 징역 또는 1천만원 이하 벌금",
            ),
            "articles": [
                {
                    "article_ref": "학교보건법 제6조",
                    "content": (
                        "정화구역 안에서는 유흥주점·단란주점·노래연습장 등을 운영할 수 없으며, "
                        "절대정화구역(50m)은 예외 없이 금지, 상대정화구역(200m)은 학교환경위생"
                        "정화위원회 심의를 거쳐야 한다."
                    ),
                }
            ],
        }

    # schools 미주입 시 DB 조회
    if schools is None:
        schools = _fetch_mapo_schools()

    nearest_50: list[dict] = []
    nearest_200: list[dict] = []
    for s in schools or []:
        try:
            s_lat = float(s["lat"])
            s_lon = float(s["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        d = _haversine_m(lat, lon, s_lat, s_lon)
        if d <= SCHOOL_ABSOLUTE_ZONE_M:
            nearest_50.append({**s, "distance_m": round(d, 1)})
        elif d <= SCHOOL_RELATIVE_ZONE_M:
            nearest_200.append({**s, "distance_m": round(d, 1)})
    nearest_50.sort(key=lambda x: x["distance_m"])
    nearest_200.sort(key=lambda x: x["distance_m"])

    articles_default = [
        {
            "article_ref": "학교보건법 제6조",
            "content": (
                "누구든지 학교환경위생정화구역에서는 유흥주점·단란주점·노래연습장 등 "
                "학생의 보건·위생에 영향을 미치는 시설을 운영할 수 없다. "
                "절대정화구역은 학교 출입문 50미터 이내, 상대정화구역은 200미터 이내이다."
            ),
        }
    ]

    if nearest_50:
        s = nearest_50[0]
        return {
            "type": "school_zone",
            "level": "danger",
            "summary": (
                f"주점 영업 후보지가 '{s.get('name')}' 으로부터 {s['distance_m']:.0f}m 떨어져 "
                f"있어 학교보건법 제6조 절대정화구역(50m) 내에 위치 — 영업이 원천 금지됩니다."
            ),
            "recommendation": _format_recommendation(
                ["학교보건법 제6조", "시행령 제3조"],
                [
                    f"가장 가까운 학교: {s.get('name')} ({s.get('school_type') or '학교'}) "
                    f"— 거리 {s['distance_m']:.0f}m (절대정화구역 50m 이내)",
                    "절대정화구역 내 주점·유흥주점·단란주점·노래연습장 영업 원천 금지",
                    "출점 후보지 변경 또는 비주류(카페/음식점) 업종 전환 검토",
                ],
                "절대정화구역 내 영업 시 즉시 영업정지 + 1년 이하 징역 또는 1천만원 이하 벌금",
            ),
            "articles": articles_default,
            "nearest_school": s,
        }
    if nearest_200:
        s = nearest_200[0]
        return {
            "type": "school_zone",
            "level": "danger",
            "summary": (
                f"주점 영업 후보지가 '{s.get('name')}' 으로부터 {s['distance_m']:.0f}m 떨어져 "
                f"있어 학교보건법 제6조 상대정화구역(200m) 내에 위치 — 학교환경위생정화"
                "위원회 심의 대상이며, 통상 거부됩니다."
            ),
            "recommendation": _format_recommendation(
                ["학교보건법 제6조", "시행령 제3조"],
                [
                    f"가장 가까운 학교: {s.get('name')} ({s.get('school_type') or '학교'}) "
                    f"— 거리 {s['distance_m']:.0f}m (상대정화구역 200m 이내)",
                    "관할 교육지원청 학교환경위생정화위원회 심의 신청 (대부분 거부 사례)",
                    "심의 거부 시 출점 불가 — 후보지 변경 또는 업종 전환 권장",
                ],
                "심의 미신청·거부 후 영업 시 영업정지 + 1년 이하 징역 또는 1천만원 이하 벌금",
            ),
            "articles": articles_default,
            "nearest_school": s,
        }

    return {
        "type": "school_zone",
        "level": "safe",
        "summary": (
            "주점 영업 후보지 반경 200m 이내에 학교가 없어 학교환경위생정화구역 영업 제한 대상에서 제외됩니다."
        ),
        "recommendation": _format_recommendation(
            ["학교보건법 제6조"],
            [
                "주변 200m 이내 학교 없음 — 정화구역 영업 제한 미해당",
                "신규 학교 설립 시 정화구역 적용 가능 — 영업 중 학교 신설 모니터링 권장",
            ],
            "주변 학교 신설 후 정화구역 편입 시 영업정지 가능",
        ),
        "articles": articles_default,
    }
