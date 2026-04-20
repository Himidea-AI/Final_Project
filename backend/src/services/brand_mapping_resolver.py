"""브랜드 표기 차이 통합 + 마포 내 브랜드 매장 조회.

kakao_store 의 brand_name 컬럼을 표준명으로 정규화한다.
`biz_brand_mapping` 테이블은 row 1개뿐이라 사용하지 않는다 (2026-04-20 실측 확인).

표준명은 FTC 가맹본부 공시 표기를 따른다 (예: "이디야커피", "맘스터치").
"""

from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import text

from src.database.sync_engine import get_sync_engine

# ---------------------------------------------------------------------------
# 수동 매핑 — FTC 표준 표기 기준
# ---------------------------------------------------------------------------

# 표준명 → alias 목록. alias 매칭은 case-insensitive, 부분 문자열.
BRAND_ALIASES: dict[str, list[str]] = {
    # 커피
    "이디야커피": ["이디야", "EDIYA", "EDIYA COFFEE"],
    "빽다방": ["백다방", "빽다방빵연구소"],
    "메가MGC커피": ["메가커피", "메가엠지씨커피", "MGC", "MEGA", "MEGA COFFEE"],
    "스타벅스": ["STARBUCKS", "스타벅스커피"],
    "투썸플레이스": ["TWOSOME", "A TWOSOME PLACE", "투썸"],
    "컴포즈커피": ["COMPOSE", "컴포즈"],
    # 치킨
    "교촌치킨": ["교촌"],
    "BBQ": ["BBQ치킨", "비비큐"],
    "BHC": ["BHC치킨"],
    # 패스트푸드
    "맘스터치": ["맘스터치 피자앤치킨", "맘스터치피자"],
    "롯데리아": ["LOTTERIA"],
    "버거킹": ["BURGER KING", "버거킹(Burger King)"],
    # 베이커리 (추후 확장)
    "파리바게뜨": ["PARIS BAGUETTE"],
    "뚜레쥬르": ["TOUS LES JOURS"],
}


def _norm(s: str) -> str:
    """비교용 정규화 — 소문자 + 공백/괄호 제거."""
    return s.lower().replace(" ", "").replace("(", "").replace(")", "")


def resolve_brand_name(raw_name: str | None) -> str | None:
    """표기 차이 있는 이름 → 표준 브랜드명.

    독립점(매칭 실패)이면 None. BRAND_ALIASES 밖 브랜드도 None.

    Examples:
        >>> resolve_brand_name("이디야")
        '이디야커피'
        >>> resolve_brand_name("MEGA COFFEE")
        '메가MGC커피'
        >>> resolve_brand_name("어서오십시오")  # 독립점
        >>> resolve_brand_name(None)
    """
    if not raw_name:
        return None
    target = _norm(raw_name)
    for standard, aliases in BRAND_ALIASES.items():
        candidates = [standard] + aliases
        for cand in candidates:
            if _norm(cand) in target or target in _norm(cand):
                return standard
    return None


def get_all_mapo_stores_by_brand(brand_name: str) -> list[dict]:
    """브랜드명으로 마포 내 모든 매장 좌표 조회 (kakao_store).

    BRAND_ALIASES 기반으로 표기 변형 모두 검색. dong_name NULL 인 매장은 제외.

    Returns:
        [{kakao_id, place_name, brand_name, lat, lon, dong_name, address}, ...]
    """
    aliases = BRAND_ALIASES.get(brand_name, []) + [brand_name]
    aliases = sorted(set(aliases))

    conditions = " OR ".join(f"brand_name ILIKE :a{i}" for i in range(len(aliases)))
    sql = text(
        f"""
        SELECT kakao_id, place_name, brand_name, lat, lon, dong_name, address
          FROM kakao_store
         WHERE dong_name IS NOT NULL
           AND ({conditions})
        """
    )
    params = {f"a{i}": f"%{a}%" for i, a in enumerate(aliases)}

    engine = get_sync_engine(os.environ["POSTGRES_URL"])
    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()
    return [dict(r) for r in rows]


@lru_cache(maxsize=1)
def list_known_brands() -> tuple[str, ...]:
    """등록된 표준 브랜드명 목록 (FTC/수동 매핑 기준)."""
    return tuple(BRAND_ALIASES.keys())
