"""brand_name → kakao_store_menu JOIN → menu_items list 변환.

설계 의도:
    프랜차이즈 대상 vacancy_pse 시뮬에서, vacancy 매장에 실제 그 브랜드의
    메뉴/가격을 attach 하기 위한 services 레이어 entry point.

    `services/brand_mapping_resolver.get_all_mapo_stores_by_brand()` 로 마포
    내 같은 브랜드 매장의 kakao_id 목록을 받고, kakao_store_menu 테이블에서
    메뉴/가격을 통합 (AVG by menu_name) 해 list[{name, price}] 반환.

학술 근거 (spec 16절):
    - "Affordable Generative Agents" (arxiv 2402.02053) — LLM 비용 절감 +
      hardcoded 메뉴 source 의 합리성.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from sqlalchemy import text

from src.database.sync_engine import get_sync_engine
from src.services.brand_mapping_resolver import get_all_mapo_stores_by_brand

logger = logging.getLogger(__name__)


class BrandNotFoundError(ValueError):
    """마포에 brand_name 매장 0개."""


class BrandMenuEmptyError(ValueError):
    """매장은 있으나 가격>0 메뉴 row 0건."""


def _fetch_menu_items_from_db(kakao_ids: list[str]) -> list[dict[str, Any]]:
    """kakao_id 리스트 → kakao_store_menu JOIN → 메뉴명별 평균 가격."""
    if not kakao_ids:
        return []
    sql = text("""
        SELECT menu_name, AVG(price)::int AS price
          FROM kakao_store_menu
         WHERE kakao_id = ANY(:kids)
           AND menu_name IS NOT NULL
           AND price IS NOT NULL
           AND price > 0
         GROUP BY menu_name
         ORDER BY AVG(price) DESC
         LIMIT 30
    """)
    engine = get_sync_engine(os.environ["POSTGRES_URL"])
    with engine.connect() as conn:
        rows = conn.execute(sql, {"kids": list(kakao_ids)}).mappings().all()
    return [{"name": r["menu_name"], "price": int(r["price"])} for r in rows]


@lru_cache(maxsize=128)
def load_brand_menu_items(brand_name: str) -> list[dict[str, Any]]:
    """brand_name → 마포 같은 브랜드 매장의 menu_items 통합.

    Args:
        brand_name: 표준 브랜드명 (예: "이디야"). alias 자동 처리.

    Returns:
        list[{"name": str, "price": int}], max 30개. 가격 내림차순.

    Raises:
        BrandNotFoundError: 마포 매장 0개.
        BrandMenuEmptyError: 매장 ≥1 but 가격>0 메뉴 0건.
    """
    stores = get_all_mapo_stores_by_brand(brand_name)
    if not stores:
        raise BrandNotFoundError(f"브랜드 '{brand_name}' 가 마포에 등록된 매장이 없어 평가 불가.")

    kakao_ids = [s["kakao_id"] for s in stores if s.get("kakao_id")]
    menu = _fetch_menu_items_from_db(kakao_ids)

    if not menu:
        raise BrandMenuEmptyError(
            f"브랜드 '{brand_name}' 의 메뉴 데이터가 부족 (가격 정보 있는 메뉴 0건, 매장 {len(stores)}개)."
        )

    logger.info(f"[brand_menu_loader] '{brand_name}': 마포 매장 {len(stores)}개 → 메뉴 {len(menu)}개 통합")
    return menu
