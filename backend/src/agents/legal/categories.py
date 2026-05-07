"""법률 카테고리 → 그룹(입지/운영) 매핑 단일 소스.

자영업자 도메인 분리 기준:

- ``location``  : 출점 의사결정 단계에서 critical. 후보지/면적/용도지역 등
                  현장 조건에 의해 결정되며, 잘못 선정 시 영업 자체가 불가능.
- ``operation`` : 운영 단계에서 마주치는 일상 의무. 자영업자가 통상 인지하고
                  있는 영역(식품위생/노동/세무/개인정보/하수도) 으로, 출점
                  결정에는 secondary.

main.py 응답 변환과 frontend `LegalRisk.group` 가 이 매핑에 의존한다.
새 카테고리를 추가하면 반드시 여기에 그룹을 명시할 것 — 누락 시
LEGAL_GROUP_DEFAULT(``operation``) 로 폴백.
"""

LEGAL_GROUP_LOCATION = "location"
LEGAL_GROUP_OPERATION = "operation"
LEGAL_GROUP_DEFAULT = LEGAL_GROUP_OPERATION


# 카테고리 → 그룹 매핑 (단일 소스)
LEGAL_CATEGORY_GROUP: dict[str, str] = {
    # ── 입지 그룹 (출점 결정 critical) ──
    "building_law": LEGAL_GROUP_LOCATION,  # 용도지역/용도변경
    "school_zone": LEGAL_GROUP_LOCATION,  # 학교환경위생정화구역 (50/200m)
    "safety_regulation": LEGAL_GROUP_LOCATION,  # 다중이용업소 면적 트리거
    "fire_safety_law": LEGAL_GROUP_LOCATION,  # 소방시설 면적
    "accessibility_law": LEGAL_GROUP_LOCATION,  # 편의시설 면적
    "franchise_law": LEGAL_GROUP_LOCATION,  # 영업지역 침해 (인접 출점)
    "fair_trade_law": LEGAL_GROUP_LOCATION,  # 공정거래/마포구 조례
    "commercial_lease_law": LEGAL_GROUP_LOCATION,  # 임대차 — 출점 시 결정
    "zoning_regulation": LEGAL_GROUP_LOCATION,  # legacy 호환
    "ftc_franchise": LEGAL_GROUP_LOCATION,  # 정보공개서 — 출점 전 검토
    # ── 운영 그룹 (자영업자 통상 인지) ──
    "food_hygiene": LEGAL_GROUP_OPERATION,
    "labor_law": LEGAL_GROUP_OPERATION,
    "vat_law": LEGAL_GROUP_OPERATION,
    "privacy_law": LEGAL_GROUP_OPERATION,
    "sewage_law": LEGAL_GROUP_OPERATION,
}


def get_legal_group(risk_type: str) -> str:
    """카테고리 타입에서 그룹(location/operation)을 반환.

    매핑 누락 카테고리는 안전한 default(``operation``) 로 폴백 — frontend 에서
    secondary 섹션에 표시되어 사용자에게 노출 자체는 보존됨.
    """
    return LEGAL_CATEGORY_GROUP.get(risk_type, LEGAL_GROUP_DEFAULT)
