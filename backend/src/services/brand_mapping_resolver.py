"""브랜드 표기 차이 통합 + 마포 내 브랜드 매장 조회.

kakao_store 의 brand_name 컬럼을 표준명으로 정규화한다.
1차: biz_brand_mapping DB (5,900+ 브랜드) 조회.
2차: BRAND_ALIASES 수동 매핑 (fallback).

표준명은 FTC 가맹본부 공시 표기를 따른다 (예: "이디야커피", "맘스터치").
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache

from sqlalchemy import text

from src.database.sync_engine import get_sync_engine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 수동 매핑 (fallback) — DB 조회 실패 시 사용
# ---------------------------------------------------------------------------

BRAND_ALIASES: dict[str, list[str]] = {
    "이디야커피": ["이디야", "EDIYA", "EDIYA COFFEE"],
    # 빽다방 = 커피전문점. "빽다방빵연구소"는 베이커리 별개 가맹사업이라 alias 제외.
    # 가맹사업법 제12조의4 = 동일 업종 침해 금지. 베이커리는 다른 업종이라 카운트 X.
    "빽다방": ["백다방"],
    "메가엠지씨커피(MEGA MGC COFFEE)": ["메가커피", "메가MGC커피", "메가엠지씨커피", "MGC", "MEGA", "MEGA COFFEE"],
    "스타벅스": ["STARBUCKS", "스타벅스커피"],
    "투썸플레이스": ["TWOSOME", "A TWOSOME PLACE", "투썸"],
    "컴포즈커피": ["COMPOSE", "컴포즈"],
    "교촌치킨": ["교촌"],
    "BBQ": ["BBQ치킨", "비비큐"],
    "BHC": ["BHC치킨"],
    # 맘스터치 = 햄버거. "맘스터치 피자앤치킨"/"맘스터치피자"는 별개 가맹사업이라 alias 제외.
    "맘스터치": [],
    "롯데리아": ["LOTTERIA"],
    "버거킹": ["BURGER KING", "버거킹(Burger King)"],
    "파리바게뜨": ["PARIS BAGUETTE"],
    "뚜레쥬르": ["TOUS LES JOURS"],
}


# ILIKE 부분 매칭 false positive 제외 — canonical 별 별개 가맹사업 (다른 업종) 매장 명시.
# 예: "빽다방" 검색 시 ILIKE '%빽다방%' 가 "빽다방빵연구소" (베이커리) 도 매칭 → 가맹사업법
# 제12조의4 (동일 업종 침해 금지) 관점에서 카운트 안 됨. 후처리로 제외.
BRAND_EXCLUDE: dict[str, list[str]] = {
    "빽다방": ["빵연구소"],
    "맘스터치": ["피자앤치킨", "피자"],
}


# 역방향 매핑 — 사용자 입력 alias → canonical brand_name.
# 예: "메가커피" 입력 → canonical "메가엠지씨커피(MEGA MGC COFFEE)" 찾아 모든 변형 검색.
_REVERSE_ALIASES: dict[str, str] = {alt: canonical for canonical, alts in BRAND_ALIASES.items() for alt in alts}


def _norm(s: str) -> str:
    """비교용 정규화 — 소문자 + 공백/괄호 제거."""
    return s.lower().replace(" ", "").replace("(", "").replace(")", "")


@lru_cache(maxsize=1)
def _load_db_brands() -> dict[str, str]:
    """biz_brand_mapping에서 brand_name 전체 로드 → {정규화명: 원본명} 딕셔너리.

    서버 시작 후 첫 호출 시 1회만 로드 (lru_cache).
    """
    try:
        engine = get_sync_engine(os.environ.get("POSTGRES_URL", ""))
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT DISTINCT brand_name FROM biz_brand_mapping WHERE brand_name IS NOT NULL AND brand_name != ''"
                )
            ).fetchall()
        result = {}
        for r in rows:
            name = r[0]
            result[_norm(name)] = name
        logger.info("biz_brand_mapping 브랜드 %d개 로드 완료", len(result))
        return result
    except Exception:
        logger.warning("biz_brand_mapping 로드 실패 — BRAND_ALIASES fallback 사용")
        return {}


def resolve_brand_name(raw_name: str | None) -> str | None:
    """표기 차이 있는 이름 → 표준 브랜드명.

    1차: biz_brand_mapping DB (5,900+ 브랜드)에서 부분 문자열 매칭.
    2차: BRAND_ALIASES 수동 매핑 (fallback).
    독립점(매칭 실패)이면 None.

    Examples:
        >>> resolve_brand_name("이디야")
        '이디야커피'
        >>> resolve_brand_name("MEGA COFFEE")
        '메가엠지씨커피(MEGA MGC COFFEE)'
        >>> resolve_brand_name("어서오십시오")  # 독립점
        >>> resolve_brand_name(None)
    """
    if not raw_name:
        return None
    target = _norm(raw_name)

    # 1차: DB 브랜드 매칭
    db_brands = _load_db_brands()
    if db_brands:
        # 완전 일치
        if target in db_brands:
            return db_brands[target]
        # 부분 문자열 매칭 (짧은 쪽이 긴 쪽에 포함)
        for normed, original in db_brands.items():
            if len(target) >= 2 and (target in normed or normed in target):
                return original

    # 2차: 수동 매핑 fallback
    for standard, aliases in BRAND_ALIASES.items():
        candidates = [standard] + aliases
        for cand in candidates:
            if _norm(cand) in target or target in _norm(cand):
                return standard

    return None


def get_all_mapo_stores_by_brand(brand_name: str) -> list[dict]:
    """브랜드명으로 마포 내 모든 매장 좌표 조회 (kakao_store).

    biz_brand_mapping (DB 5,900) + BRAND_ALIASES (하드코딩 14, 양방향) 통합 검색.
    사용자 입력이 alias (예: "메가커피") 여도 canonical (예: "메가엠지씨커피(MEGA MGC COFFEE)") 로
    역추적 후 전체 변형 검색.
    dong_name NULL 인 매장은 제외.

    Returns:
        [{kakao_id, place_name, brand_name, lat, lon, dong_name, address,
          place_url, phone}, ...]
    """
    # 0차: DB 기반 canonical resolve (biz_brand_mapping 5,900개 활용)
    resolved = resolve_brand_name(brand_name) or brand_name
    # 1차: 하드코딩 alias 역추적, 그 다음 모든 정방향 변형 + 입력 자체 + DB resolved 포함
    canonical = _REVERSE_ALIASES.get(resolved, resolved)
    aliases_raw = list(BRAND_ALIASES.get(canonical, [])) + [canonical, brand_name, resolved]

    # 2차: FTC 표기 ↔ Kakao 표기 mismatch 보정.
    # FTC brandNm 은 등록번호/연도 접미사 또는 괄호 영문 alias 가 붙는 경우 다수
    # (홍콩반점0410, 메가엠지씨커피(MEGA MGC COFFEE), 비비큐(BBQ) 등).
    # kakao_store 는 일반 brand 명만 적재 → 다양한 변형 alias 추출하여 ILIKE 매칭 hit율 ↑.
    extra_short: list[str] = []
    for a in aliases_raw:
        if not a:
            continue
        # 끝 숫자 제거 (예: "홍콩반점0410" → "홍콩반점")
        s1 = re.sub(r"\d+$", "", a).strip()
        if s1 and s1 != a:
            extra_short.append(s1)
        # 괄호+내용 제거 — 한글 표기만 (예: "메가엠지씨커피(MEGA MGC COFFEE)" → "메가엠지씨커피")
        s2 = re.sub(r"\s*\([^)]*\)\s*$", "", a).strip()
        if s2 and s2 != a:
            extra_short.append(s2)
        # 괄호 안 영문/숫자 추출 — kakao_store 가 영문만 적재한 경우 (예: "비비큐(BBQ)" → "BBQ")
        m = re.search(r"\(([A-Za-z0-9][A-Za-z0-9 &-]*)\)", a)
        if m:
            paren = m.group(1).strip()
            if paren:
                extra_short.append(paren)
        # & 이후 suffix 제거 — kakao 가 첫 단어만 적재한 경우 (예: "본죽&비빔밥" → "본죽")
        s4 = re.sub(r"\s*&.*$", "", a).strip()
        if s4 and s4 != a:
            extra_short.append(s4)
    aliases = sorted(set(aliases_raw + extra_short))

    conditions = " OR ".join(f"brand_name ILIKE :a{i}" for i in range(len(aliases)))
    sql = text(
        f"""
        SELECT kakao_id, place_name, brand_name, lat, lon, dong_name, address,
               place_url, phone, category
          FROM kakao_store
         WHERE dong_name IS NOT NULL
           AND ({conditions})
        """
    )
    params = {f"a{i}": f"%{a}%" for i, a in enumerate(aliases)}

    engine = get_sync_engine(os.environ["POSTGRES_URL"])
    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()
    results = [dict(r) for r in rows]

    # ILIKE 부분 매칭 false positive 제외 — canonical 별 BRAND_EXCLUDE 단어 포함된 매장 제거.
    # 예: 빽다방 검색 시 "빽다방빵연구소" 매장은 "빵연구소" 키워드로 제외.
    excludes = BRAND_EXCLUDE.get(canonical, [])
    if excludes:
        before = len(results)
        results = [
            r
            for r in results
            if not any(ex in (r.get("brand_name") or "") for ex in excludes)
        ]
        if before != len(results):
            logger.debug(
                f"[get_all_mapo_stores_by_brand] {canonical} false positive {before - len(results)}개 제외 "
                f"(excludes={excludes})"
            )
    return results


@lru_cache(maxsize=1)
def list_known_brands() -> tuple[str, ...]:
    """등록된 표준 브랜드명 목록 (DB + 수동 매핑 통합)."""
    db_brands = _load_db_brands()
    all_brands = set(BRAND_ALIASES.keys()) | set(db_brands.values())
    return tuple(sorted(all_brands))
