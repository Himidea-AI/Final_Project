"""업종 매핑 단일 source of truth.

동일 업종 정보가 여러 dict 에 흩어져 있던 문제 해소를 위한 통합 테이블.
다음 6개 매핑이 한 dict 의 컬럼들로 통합됨:

    1. CS 코드           (store_quarterly.industry_code)
    2. DB 업종명          (store_quarterly.industry_name)
    3. Kakao 카테고리     (kakao_store.category)
    4. Kakao 검색 키워드  (Kakao Local Search API 입력)
    5. FTC 매칭 키워드    (FTC 정보공개서 indutyMlsfcNm 매칭용)
    6. UI 라벨            (한국어 / 영문 slug)

사용:
    from src.config.business_type_mapping import (
        BUSINESS_TYPE_MAPPING,
        by_cs_code,
        by_kakao_category,
    )

검증 (DB 실측, 2026-05-04):
    - store_quarterly.industry_name 과 kakao_store.category 가 10종 모두 동일.
    - 마포구 표본: 한식 946 / 중식 130 / 일식 268 / 양식 240 / 제과 185 /
      패스트푸드 65 / 치킨 137 / 분식 151 / 호프 250 / 커피 1549 (kakao_store).
    - store_quarterly: CS100001~CS100010 만 존재.
    - ftc_brand_franchise.indutyMlsfcNm 실제 표기 (DB top 매칭):
      한식·중식·일식·치킨·분식·주점·커피·패스트푸드는 단일 한글, 양식→"서양식",
      제과→"제과제빵", 커피의 비커피음료→"음료 (커피 외)" 표기.

비포함:
    - 편의점 (CS200009): 시뮬레이션 입력 옵션 외. store_quarterly 미존재.
      kakao_store(415)/ftc_brand_franchise(103) 데이터는 있으나 시뮬 흐름 미사용.
"""

from __future__ import annotations

from typing import TypedDict


class BusinessTypeEntry(TypedDict):
    """업종 한 건의 모든 매핑 키."""

    cs_code: str
    """store_quarterly.industry_code (CS100001~CS100010)"""

    db_industry_name: str
    """store_quarterly.industry_name = kakao_store.category (10종 일치 검증됨)"""

    kakao_category: str
    """kakao_store.category. db_industry_name 과 동일하지만 의미 분리 위해 별도 컬럼."""

    kakao_keyword: str
    """Kakao Local Search API query 입력 (단순 검색용)"""

    ftc_keywords: list[str]
    """FTC 정보공개서 indutyMlsfcNm 또는 brandNm fuzzy 매칭용 키워드 목록"""

    naver_industry: str
    """Naver DataLab API 의 industry 필터값 (예: '카페' — kakao 와 표기 다를 수 있음)"""

    label_kr: str
    """UI 표시용 한국어 라벨"""

    label_en: str
    """코드 식별자 (slug, snake_case)"""


# ---------------------------------------------------------------------------
# 메인 매핑 (단일 source of truth)
# ---------------------------------------------------------------------------

BUSINESS_TYPE_MAPPING: dict[str, BusinessTypeEntry] = {
    "한식": {
        "cs_code": "CS100001",
        "db_industry_name": "한식음식점",
        "kakao_category": "한식음식점",
        "kakao_keyword": "한식",
        "ftc_keywords": ["한식", "국밥", "설렁탕", "갈비", "삼겹살", "냉면", "보쌈", "족발"],
        "naver_industry": "한식",
        "label_kr": "한식음식점",
        "label_en": "korean",
    },
    "중식": {
        "cs_code": "CS100002",
        "db_industry_name": "중식음식점",
        "kakao_category": "중식음식점",
        "kakao_keyword": "중식",
        "ftc_keywords": ["중식", "중국", "짜장", "짬뽕", "마라"],
        "naver_industry": "중식",
        "label_kr": "중식음식점",
        "label_en": "chinese",
    },
    "일식": {
        "cs_code": "CS100003",
        "db_industry_name": "일식음식점",
        "kakao_category": "일식음식점",
        "kakao_keyword": "일식",
        "ftc_keywords": ["일식", "초밥", "스시", "돈가스", "라멘", "우동"],
        "naver_industry": "일식",
        "label_kr": "일식음식점",
        "label_en": "japanese",
    },
    "양식": {
        "cs_code": "CS100004",
        "db_industry_name": "양식음식점",
        "kakao_category": "양식음식점",
        "kakao_keyword": "양식",
        # DB 실측: ftc_brand_franchise.indutyMlsfcNm 은 "서양식" 표기 (838건).
        # "양식" 은 입력 호환용. "피자" 는 _ALIASES 와 충돌 가능 — 정책 결정 후 조정 (TODO).
        "ftc_keywords": ["서양식", "양식", "피자", "파스타", "스테이크"],
        "naver_industry": "양식",
        "label_kr": "양식음식점",
        "label_en": "western",
    },
    "제과": {
        "cs_code": "CS100005",
        "db_industry_name": "제과점",
        "kakao_category": "제과점",
        "kakao_keyword": "베이커리",
        # DB 실측: ftc_brand_franchise.indutyMlsfcNm 은 "제과제빵" 한 단어 표기 (827건).
        "ftc_keywords": ["제과제빵", "제과", "베이커리", "빵", "도넛", "와플"],
        "naver_industry": "제과",
        "label_kr": "제과점",
        "label_en": "bakery",
    },
    "패스트푸드": {
        "cs_code": "CS100006",
        "db_industry_name": "패스트푸드점",
        "kakao_category": "패스트푸드점",
        "kakao_keyword": "버거",
        "ftc_keywords": ["패스트푸드", "햄버거", "버거", "샌드위치"],
        "naver_industry": "패스트푸드",
        "label_kr": "패스트푸드점",
        "label_en": "fastfood",
    },
    "치킨": {
        "cs_code": "CS100007",
        "db_industry_name": "치킨전문점",
        "kakao_category": "치킨전문점",
        "kakao_keyword": "치킨",
        "ftc_keywords": ["치킨", "닭강정"],
        "naver_industry": "치킨",
        "label_kr": "치킨전문점",
        "label_en": "chicken",
    },
    "분식": {
        "cs_code": "CS100008",
        "db_industry_name": "분식전문점",
        "kakao_category": "분식전문점",
        "kakao_keyword": "분식",
        "ftc_keywords": ["분식", "떡볶이", "김밥", "튀김"],
        "naver_industry": "분식",
        "label_kr": "분식전문점",
        "label_en": "snack",
    },
    "호프": {
        "cs_code": "CS100009",
        "db_industry_name": "호프-간이주점",
        "kakao_category": "호프-간이주점",
        "kakao_keyword": "주점",
        "ftc_keywords": ["호프", "간이주점", "주점", "이자카야"],
        "naver_industry": "호프",
        "label_kr": "호프-간이주점",
        "label_en": "pub",
    },
    "커피": {
        "cs_code": "CS100010",
        "db_industry_name": "커피-음료",
        "kakao_category": "커피-음료",
        "kakao_keyword": "커피",  # main.py:_BIZ_TO_KAKAO_KW 기존값과 일치
        # DB 실측: "커피" 2397건 + "음료 (커피 외)" 307건 별도 표기.
        # 부분 매칭(LIKE '%음료%') 전제이지만 정확 매칭 호출자 대비해 풀네임 포함.
        "ftc_keywords": ["커피", "카페", "음료 (커피 외)", "음료", "디저트"],
        "naver_industry": "카페",  # tools.py:_NAVER_INDUSTRY_MAP 의 CS100010 → "카페" 와 일치
        "label_kr": "커피-음료",
        "label_en": "cafe",
    },
}


# ---------------------------------------------------------------------------
# 별칭 — 사용자 입력 다양성 대응 (예전 dict 들의 키 변형 흡수)
# ---------------------------------------------------------------------------

_ALIASES: dict[str, str] = {
    # 한식 ─────────────────────────────────
    "한식음식점": "한식",
    "음식점": "한식",
    "food": "한식",
    "restaurant": "한식",
    "korean": "한식",
    # 중식 ─────────────────────────────────
    "중식음식점": "중식",
    "짜장": "중식",
    "짬뽕": "중식",
    "마라": "중식",
    "chinese": "중식",
    # 일식 ─────────────────────────────────
    "일식음식점": "일식",
    "초밥": "일식",
    "스시": "일식",
    "돈가스": "일식",
    "라멘": "일식",
    "우동": "일식",
    "japanese": "일식",
    # 양식 ─────────────────────────────────
    "양식음식점": "양식",
    "파스타": "양식",
    "스테이크": "양식",
    "western": "양식",
    # 제과 ─────────────────────────────────
    "제과점": "제과",
    "베이커리": "제과",
    "빵": "제과",
    "도넛": "제과",
    "와플": "제과",
    "bakery": "제과",
    # 패스트푸드 ──────────────────────────
    # 주의: 피자는 양식과 혼재. _SALES_CODE_MAP 의 기존 매핑(패스트푸드)을 따름.
    "패스트푸드점": "패스트푸드",
    "버거": "패스트푸드",
    "햄버거": "패스트푸드",
    "피자": "패스트푸드",
    "샌드위치": "패스트푸드",
    "burger": "패스트푸드",
    "fastfood": "패스트푸드",
    # 치킨 ─────────────────────────────────
    "치킨전문점": "치킨",
    "닭강정": "치킨",
    "chicken": "치킨",
    # 분식 ─────────────────────────────────
    "분식전문점": "분식",
    "떡볶이": "분식",
    "김밥": "분식",
    "튀김": "분식",
    "snack": "분식",
    # 호프 ─────────────────────────────────
    "호프-간이주점": "호프",
    "주점": "호프",
    "맥주": "호프",
    "이자카야": "호프",
    "pub": "호프",
    # 커피 ─────────────────────────────────
    "커피-음료": "커피",
    "카페": "커피",
    "cafe": "커피",
    "coffee": "커피",
}


def normalize_key(raw: str) -> str | None:
    """사용자/외부 입력을 canonical 업종 키로 변환.

    Examples:
        >>> normalize_key("패스트푸드점")
        '패스트푸드'
        >>> normalize_key("burger")
        '패스트푸드'
        >>> normalize_key("커피")
        '커피'
        >>> normalize_key("알수없음")
    """
    if not raw:
        return None
    raw = raw.strip()
    if raw in BUSINESS_TYPE_MAPPING:
        return raw
    return _ALIASES.get(raw.lower(), _ALIASES.get(raw))


def get_entry(raw: str) -> BusinessTypeEntry | None:
    """raw 입력 → 매핑 entry 전체 반환."""
    key = normalize_key(raw)
    return BUSINESS_TYPE_MAPPING.get(key) if key else None


def by_cs_code(cs: str) -> BusinessTypeEntry | None:
    """CS 코드 (예: 'CS100006') 로 entry 조회."""
    for entry in BUSINESS_TYPE_MAPPING.values():
        if entry["cs_code"] == cs:
            return entry
    return None


def by_kakao_category(category: str) -> BusinessTypeEntry | None:
    """kakao_store.category 값 (예: '패스트푸드점') 으로 entry 조회."""
    for entry in BUSINESS_TYPE_MAPPING.values():
        if entry["kakao_category"] == category:
            return entry
    return None


def by_db_industry_name(name: str) -> BusinessTypeEntry | None:
    """store_quarterly.industry_name 값으로 entry 조회.

    db_industry_name == kakao_category 이므로 by_kakao_category 와 동일 결과.
    의미 명확화 위해 별도 함수 제공.
    """
    return by_kakao_category(name)


# ---------------------------------------------------------------------------
# Convenience accessors (기존 dict 마이그레이션 시 1:1 대체용)
# ---------------------------------------------------------------------------


def all_cs_codes() -> list[str]:
    """등록된 모든 CS 코드 목록."""
    return [e["cs_code"] for e in BUSINESS_TYPE_MAPPING.values()]


def all_kakao_categories() -> list[str]:
    """등록된 모든 kakao_store.category 값 목록."""
    return [e["kakao_category"] for e in BUSINESS_TYPE_MAPPING.values()]


def all_kakao_keywords() -> list[str]:
    """등록된 모든 Kakao 검색 키워드 목록."""
    return [e["kakao_keyword"] for e in BUSINESS_TYPE_MAPPING.values()]


def cs_code_of(raw: str) -> str | None:
    """raw 입력 → CS 코드 (예: '패스트푸드' → 'CS100006')."""
    e = get_entry(raw)
    return e["cs_code"] if e else None


def kakao_category_of(raw: str) -> str | None:
    """raw 입력 → kakao_store.category 값."""
    e = get_entry(raw)
    return e["kakao_category"] if e else None


def kakao_keyword_of(raw: str) -> str | None:
    """raw 입력 → Kakao 검색 키워드."""
    e = get_entry(raw)
    return e["kakao_keyword"] if e else None


def naver_industry_of(raw: str) -> str | None:
    """raw 입력 → Naver DataLab industry 필터값.

    예: "커피" → "카페" (Naver 표기), "한식" → "한식".
    """
    e = get_entry(raw)
    return e["naver_industry"] if e else None
