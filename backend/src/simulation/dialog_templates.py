"""Mode B 자연어 템플릿 — archetype × situation 별 짧은 한국어 문장 sampling.

설계 의도:
    LLM 비용 0 으로 시각화 chats 데이터를 채우는 hardcode 템플릿.
    8 archetype × 4 situation × 5 문장 = 160 문장 minimum coverage.

    추후 Nemotron-Personas 30 archetype 전체로 확장 (별도 commit).
    Mode C (LLM 활성) 시 Tier S 50명만 LLM, 나머지는 본 template.

학술 근거:
    - "Affordable Generative Agents" (arxiv 2402.02053) — hardcoded NLG
      의 비용 절감 + 일관성.
    - GeekNews "agent 보다 workflow 우선" — LLM 절제.
"""

from __future__ import annotations

import random
from typing import Final

# archetype_id → situation → list of 짧은 한국어 문장
TEMPLATES: Final[dict[str, dict[str, list[str]]]] = {
    "creative_freelancer": {
        "morning_visit_cafe": [
            "오늘 작업할 카페 어디로 가지",
            "감성 있는 곳이 좋겠다",
            "와이파이 좋은 곳",
            "사진 찍기 좋은 자리",
            "라떼 한 잔으로 시작",
        ],
        "lunch_decide": [
            "가까운 곳 빨리",
            "오늘은 디저트도 같이",
            "샐러드 가게 어땠더라",
            "포장해서 작업실로",
            "친구가 추천한 그 집",
        ],
        "evening_decide": [
            "마감이라 더 일해야지",
            "동료랑 한 잔 어때",
            "집 가는 길에 들를까",
            "오늘은 일찍 쉬자",
            "산책 좀 하다 가야지",
        ],
        "rest": [
            "잠깐 숨 돌리자",
            "커피 더 시킬까",
            "음악 틀고 한 곡만",
            "스트레칭 좀 하고",
            "SNS 잠깐만 보고",
        ],
    },
    "office_worker": {
        "morning_visit_cafe": [
            "빨리 한 잔 해야겠다",
            "회의 전 카페인 충전",
            "오늘은 따뜻한 걸로",
            "동료 거 같이 사야지",
            "5분 안에 받아야 해",
        ],
        "lunch_decide": [
            "오늘은 한식 가자",
            "가성비로 빨리",
            "회의 길어졌으니 도시락",
            "팀이랑 같이 갈 곳",
            "분식 어때",
        ],
        "evening_decide": [
            "오늘 회식이라 한 잔",
            "퇴근하고 바로 집",
            "동료랑 짧게 한 잔",
            "야근이라 김밥",
            "운동가야 하니까 일찍",
        ],
        "rest": [
            "5분만 쉬자",
            "커피 한 잔 더",
            "잠깐 바람 좀",
            "메일 확인하고",
            "전화 한 통 하고",
        ],
    },
    "broadcasting_staff": {
        "morning_visit_cafe": [
            "야근 후 정신 차리려고",
            "아메리카노 진하게",
            "24시간 카페 어디",
            "촬영 전 한 잔",
            "에너지 드링크라도",
        ],
        "lunch_decide": [
            "촬영 도시락",
            "빠르게 패스트푸드",
            "근처 편의점",
            "회의실 케이터링",
            "잠깐 짬내서",
        ],
        "evening_decide": [
            "야식 떡볶이",
            "밤샘 작업이라 삼겹살",
            "상암동 야식 골목",
            "편의점 라면",
            "치킨 시켜먹자",
        ],
        "rest": [
            "잠깐만 눈 감고",
            "커피 더 마셔야",
            "10분만 쉬자",
            "PD 부르기 전에",
            "스튜디오 밖 바람",
        ],
    },
    "student_couple": {
        "morning_visit_cafe": [
            "신상 카페 가자",
            "인스타에서 본 그 집",
            "사진 찍기 좋은 곳",
            "디저트 맛집 투어",
            "라떼 아트 예쁜 데",
        ],
        "lunch_decide": [
            "데이트라 분위기 있는 곳",
            "오늘은 양식",
            "가성비도 중요",
            "둘이 나눠 먹자",
            "근처 핫플",
        ],
        "evening_decide": [
            "영화 보고 저녁",
            "홍대 술집",
            "분위기 있는 와인바",
            "친구들이랑 합석",
            "포차 어때",
        ],
        "rest": [
            "잠깐 손잡고 산책",
            "벤치에서 쉬자",
            "사진 더 찍자",
            "음악 듣자",
            "다음 코스 정하자",
        ],
    },
    "retired_local": {
        "morning_visit_cafe": [
            "단골집 그대로",
            "차 한 잔이면 돼",
            "사장님과 인사",
            "신문 보면서",
            "오랜 친구 만나러",
        ],
        "lunch_decide": [
            "전통시장 국밥",
            "그 집 김치찌개",
            "가격 적당한 곳",
            "오래 다닌 단골",
            "혼자 조용히",
        ],
        "evening_decide": [
            "집에서 저녁 먹자",
            "단골 호프집",
            "동네 친구랑",
            "시장에서 장보고",
            "조용한 밥집",
        ],
        "rest": [
            "벤치에 앉아서",
            "동네 한 바퀴",
            "라디오 듣자",
            "차 한 잔 더",
            "잠깐 눈 붙이고",
        ],
    },
    "young_parent": {
        "morning_visit_cafe": [
            "키즈존 있는 곳",
            "주차되는 카페",
            "유모차 들어가는 데",
            "아이 음료도 있는 곳",
            "한적한 시간대",
        ],
        "lunch_decide": [
            "가족 외식 메뉴",
            "아이 메뉴 있는 곳",
            "근처 키즈카페 옆",
            "포장해서 집에서",
            "주말이라 좀 늦게",
        ],
        "evening_decide": [
            "일찍 집밥",
            "아이 재우고 한 잔",
            "동네 패밀리 레스토랑",
            "배달 시키자",
            "저녁 산책",
        ],
        "rest": [
            "아이 낮잠 사이",
            "벤치에서 잠깐",
            "유모차 끌고 산책",
            "음료 한 잔만",
            "친구 부부랑 만나자",
        ],
    },
    "tourist_foreign": {
        "morning_visit_cafe": [
            "한국 카페 체험",
            "인스타 핫플",
            "Korean cafe famous",
            "사진 많이 찍자",
            "전통 차 가게",
        ],
        "lunch_decide": [
            "한식당 도전",
            "비빔밥 맛집",
            "치킨 한 번",
            "검색해보자",
            "현지인 추천",
        ],
        "evening_decide": [
            "포장마차 가자",
            "한국 술 시도",
            "야시장 구경",
            "이태원 바",
            "호텔 근처로",
        ],
        "rest": [
            "Take photos here",
            "지도 다시 확인",
            "잠깐 앉자",
            "기념품샵",
            "가이드북 읽기",
        ],
    },
    "f&b_owner": {
        "morning_visit_cafe": [
            "경쟁 매장 확인",
            "신메뉴 벤치마킹",
            "사장 모임",
            "오픈 준비 전 한 잔",
            "거래처 미팅",
        ],
        "lunch_decide": [
            "직원 식사 챙기기",
            "재료 거래처",
            "근처 매장 답사",
            "오늘 점심 영업 점검",
            "빨리 먹고 복귀",
        ],
        "evening_decide": [
            "마감 후 한 잔",
            "동종 업계 모임",
            "직원 회식",
            "내일 메뉴 회의",
            "재료 발주",
        ],
        "rest": [
            "잠깐 카운터 앞",
            "직원 교대 시간",
            "세무 자료 보고",
            "SNS 마케팅 글",
            "리뷰 답글",
        ],
    },
}


def pick_dialog(
    archetype: str,
    situation: str,
    hour: int,
    rng: random.Random,
) -> str:
    """archetype + situation 에서 한국어 짧은 문장 1개 sample.

    Args:
        archetype: ARCHETYPES 의 id (예: "creative_freelancer").
        situation: "morning_visit_cafe" | "lunch_decide" | "evening_decide" | "rest".
        hour: 현재 시간 (0~23). 향후 시간대별 분기 확장에 사용.
        rng: random.Random 인스턴스 (재현성).

    Returns:
        한국어 짧은 문장. archetype/situation 모르는 경우 fallback "...".
    """
    bucket = TEMPLATES.get(archetype, {}).get(situation, [])
    if not bucket:
        return "..."
    return rng.choice(bucket)
