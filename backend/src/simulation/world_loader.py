"""RDS에서 마포 실제 점포를 로드해 World를 구성.

소스 테이블:
- kakao_store        : 마포 점포 메타 (792건, 동/카테고리/위경도)
- kakao_store_hours  : 요일별 영업시간 (744건)

카카오 카테고리 → 시뮬 카테고리 매핑:
  커피/디저트/베이커리          → 카페
  한식/일식/중식/양식/분식/패스트푸드/치킨 → 음식점
  호프-주점/주점/와인바         → 주점
  편의점                        → 편의점
  나머지                        → 기타
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from .world import Store, World


def load_subway_inflow_csv(path: str | Path | None = None) -> dict:
    """subway_inflow_by_dong_hour.csv → {(dong, hour): {board, alight, net_inflow}}.

    파일이 없으면 빈 dict (시뮬은 하드코딩 fallback 사용).
    """
    if path is None:
        path = Path(__file__).resolve().parents[3] / "data" / "processed" / "subway_inflow_by_dong_hour.csv"
    p = Path(path)
    out: dict[tuple[str, int], dict[str, float]] = {}
    if not p.exists():
        return out
    with open(p, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                dong = row["dong"].strip()
                hour = int(float(row["hour"]))
                out[(dong, hour)] = {
                    "board": float(row.get("board") or 0),
                    "alight": float(row.get("alight") or 0),
                    "net_inflow": float(row.get("net_inflow") or 0),
                }
            except (KeyError, ValueError):
                continue
    return out


# ---------------------------------------------------------------
# 카테고리 매핑 (카카오 → 시뮬)
# ---------------------------------------------------------------
CAFE_KEYWORDS = ("커피", "디저트", "베이커리", "케이크", "도넛", "아이스크림", "차")
PUB_KEYWORDS = ("호프", "주점", "와인", "바,", "맥주", "포차")
RESTAURANT_KEYWORDS = (
    "한식",
    "일식",
    "중식",
    "양식",
    "분식",
    "패스트푸드",
    "치킨",
    "피자",
    "샐러드",
    "샌드위치",
    "햄버거",
    "음식점",
    "고기",
    "회",
)
CVS_KEYWORDS = ("편의점",)


def _map_category(kakao_category: str) -> str:
    if not kakao_category:
        return "기타"
    cat = kakao_category.strip()
    if any(k in cat for k in PUB_KEYWORDS):
        return "주점"
    if any(k in cat for k in CAFE_KEYWORDS):
        return "카페"
    if any(k in cat for k in CVS_KEYWORDS):
        return "편의점"
    if any(k in cat for k in RESTAURANT_KEYWORDS):
        return "음식점"
    return "기타"


# ---------------------------------------------------------------
# 동명 정규화 (kakao_store dong_name → MAPO_DONGS와 매칭)
# ---------------------------------------------------------------
DONG_ALIASES = {
    "성산동": "성산1동",  # 기본은 1동으로
    "망원동": "망원1동",
    "동교동": "서교동",
    "창전동": "신수동",
    "노고산동": "신수동",
    "중동": "성산2동",
    "구수동": "신수동",
    "현석동": "용강동",
    "당인동": "합정동",
    "신정동": "도화동",
}


def _normalize_dong(name: str | None) -> str | None:
    if not name:
        return None
    n = name.strip()
    if n in DONG_ALIASES:
        return DONG_ALIASES[n]
    return n


# ---------------------------------------------------------------
# 영업시간 파싱
# ---------------------------------------------------------------
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*[-~]\s*(\d{1,2}):(\d{2})")


@dataclass
class OpenHours:
    """0~23시 영업 여부. True=영업중."""

    bits: list[bool]  # 길이 24

    @classmethod
    def all_open(cls) -> "OpenHours":
        return cls([True] * 24)

    @classmethod
    def parse(cls, text_value: str | None) -> "OpenHours":
        if not text_value:
            return cls.all_open()
        m = TIME_RE.search(text_value)
        if not m:
            return cls.all_open()
        sh, sm, eh, em = (int(x) for x in m.groups())
        if eh < sh:  # 24시 넘는 매장 (예: 18-02)
            eh += 24
        bits = [False] * 24
        for h in range(sh, min(eh, 30)):
            bits[h % 24] = True
        return cls(bits)


# ---------------------------------------------------------------
# 메인 로더
# ---------------------------------------------------------------
@dataclass
class StoreHoursMap:
    """store_id → 요일별 영업시간 (mon=0 ~ sun=6)."""

    by_store: dict[int, list[OpenHours]]


def _load_menu_map(engine) -> dict[str, list[dict]]:
    """kakao_id → [{name, price}, ...]. 가격 null/음수는 제외, 매장당 상위 20개."""
    sql = text("""
        SELECT kakao_id, menu_name, price
        FROM kakao_store_menu
        WHERE menu_name IS NOT NULL AND price IS NOT NULL AND price > 0
        ORDER BY kakao_id, price DESC
    """)
    out: dict[str, list[dict]] = {}
    with engine.connect() as conn:
        for row in conn.execute(sql):
            kid = row[0]
            if kid not in out:
                out[kid] = []
            if len(out[kid]) < 20:
                out[kid].append({"name": row[1], "price": int(row[2])})
    return out


def _load_dong_industry_weight(engine) -> dict[tuple[str, str], float]:
    """(dong, category) → 매출 index 0.5~1.5 (최신 분기).

    district_sales_seoul의 industry_name을 우리 카테고리(카페/음식점/주점/편의점)로 매핑.
    """
    cat_map = {
        "커피-음료": "카페",
        "제과점": "카페",
        "한식음식점": "음식점",
        "중식음식점": "음식점",
        "일식음식점": "음식점",
        "양식음식점": "음식점",
        "패스트푸드점": "음식점",
        "분식전문점": "음식점",
        "치킨전문점": "음식점",
        "호프-간이주점": "주점",
        "편의점": "편의점",
    }
    sql = text("""
        SELECT dong_name, industry_name, AVG(monthly_sales)::double precision avg_sales
        FROM district_sales_seoul
        WHERE quarter >= (SELECT MAX(quarter) - 1 FROM district_sales_seoul)
        GROUP BY 1, 2
    """)
    raw: dict[tuple[str, str], float] = {}
    with engine.connect() as conn:
        for row in conn.execute(sql):
            d, i, v = row[0], row[1], row[2]
            cat = cat_map.get(i)
            if cat and v and v > 0:
                raw[(d, cat)] = max(raw.get((d, cat), 0), float(v))
    if not raw:
        return {}
    mx = max(raw.values()) or 1.0
    return {k: round(0.5 + (v / mx), 3) for k, v in raw.items()}


def _load_sentiment_map(engine) -> dict[str, float]:
    """place_name → 감성 점수 0.7~1.3 (긍정/부정 비율 기반, 최신 월)."""
    sql = text("""
        SELECT place_name,
               SUM(positive_count)::double precision pos,
               SUM(negative_count)::double precision neg,
               SUM(neutral_count)::double precision neu
        FROM mapo_sns_sentiment
        WHERE date >= (SELECT MAX(date) - INTERVAL '180 days' FROM mapo_sns_sentiment)
        GROUP BY place_name
    """)
    out: dict[str, float] = {}
    with engine.connect() as conn:
        for row in conn.execute(sql):
            name = row[0]
            pos, neg, neu = row[1] or 0, row[2] or 0, row[3] or 0
            total = pos + neg + neu
            if total < 10:
                continue
            score = (pos - neg) / total  # -1~1
            out[name] = round(1.0 + 0.3 * score, 3)  # 0.7~1.3
    return out


def load_world_from_rds(
    db_url: str | None = None,
    limit: int | None = None,
    skip_unknown_dong: bool = True,
) -> tuple[World, StoreHoursMap]:
    """RDS의 카카오 점포 + 메뉴 + 매출/감성 보정으로 World 구성."""
    load_dotenv()
    db_url = db_url or os.environ["POSTGRES_URL"]
    engine = create_engine(db_url, echo=False)

    sql = text("""
        SELECT k.kakao_id, k.place_name, k.brand_name, k.category,
               k.dong_name, k.lat, k.lon,
               h.mon_hours, h.tue_hours, h.wed_hours, h.thu_hours,
               h.fri_hours, h.sat_hours, h.sun_hours
        FROM kakao_store k
        LEFT JOIN kakao_store_hours h USING(kakao_id)
    """)

    print("[loader] 메뉴/매출/감성 보조 데이터 로드 중...")
    menu_map = _load_menu_map(engine)
    dong_industry_w = _load_dong_industry_weight(engine)
    sentiment_map = _load_sentiment_map(engine)
    print(
        f"[loader] 메뉴 {len(menu_map):,}개 매장 / 매출 {len(dong_industry_w):,} (동×업종) / 감성 {len(sentiment_map):,}"
    )

    world = World()
    hours_map: dict[int, list[OpenHours]] = {}
    sid = 1
    skipped = 0

    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()

    for r in rows:
        if limit and sid > limit:
            break
        dong = _normalize_dong(r.dong_name)
        if not dong:
            skipped += 1
            continue
        if skip_unknown_dong and dong not in world.dongs:
            skipped += 1
            continue

        cat = _map_category(r.category)
        # 편의점·기타 카테고리는 시뮬 대상에서 제외 (분석 대상: 음식점/카페/주점 3종)
        if cat not in ("음식점", "카페", "주점"):
            skipped += 1
            continue
        menu = menu_map.get(r.kakao_id, [])
        # price_level 자동 산출 (메뉴 가격 중간값 기반)
        if menu:
            prices = sorted(m["price"] for m in menu)
            median = prices[len(prices) // 2]
            if median < 8000:
                price_level = 1
            elif median < 20000:
                price_level = 2
            else:
                price_level = 3
        else:
            price_level = 2 if cat in ("카페", "음식점") else 1

        # 인기 보정 (매출 × 감성)
        pop = dong_industry_w.get((dong, cat), 1.0) * sentiment_map.get(r.place_name or "", 1.0)

        store = Store(
            store_id=sid,
            name=r.place_name or r.brand_name or f"store_{sid}",
            dong=dong,
            category=cat,
            seats=30,
            rating=4.0,
            price_level=price_level,
            lat=float(r.lat) if r.lat is not None else None,
            lon=float(r.lon) if r.lon is not None else None,
            menu_items=menu,
            popularity_boost=round(pop, 3),
        )
        world.add_store(store)

        hours_map[sid] = [
            OpenHours.parse(r.mon_hours),
            OpenHours.parse(r.tue_hours),
            OpenHours.parse(r.wed_hours),
            OpenHours.parse(r.thu_hours),
            OpenHours.parse(r.fri_hours),
            OpenHours.parse(r.sat_hours),
            OpenHours.parse(r.sun_hours),
        ]
        sid += 1

    print(f"[loader] RDS 로드 완료: {len(world.stores)}개 점포 ({skipped}개 스킵)")
    return world, StoreHoursMap(by_store=hours_map)


def store_open_at(
    hours_map: StoreHoursMap,
    store_id: int,
    weekday: int,  # 0=월 ~ 6=일
    hour: int,
) -> bool:
    arr = hours_map.by_store.get(store_id)
    if not arr:
        return True
    return arr[weekday].bits[hour % 24]


# ---------------------------------------------------------------
# 옵션 B (2026-04-27): living_population 일별 boost loader
# ---------------------------------------------------------------
from datetime import date as _date, timedelta as _timedelta  # noqa: E402

from src.database.sync_engine import get_sync_engine  # noqa: E402


def _load_living_population_daily(
    start_date: _date,
    days: int,
) -> dict[tuple[str, int, int], float]:
    """living_population 테이블에서 (dong, hour, day_idx) → boost 로드.

    boost = total_pop / (dong 의 분기 평균 total_pop). 1.0 = 평균.

    Args:
        start_date: 시뮬 첫 일자.
        days: 시뮬 일수 (90 분기 권장).

    Returns:
        {(dong_name, hour, day_idx): float}.
        DB 데이터 부재 시 빈 dict (시뮬은 정적 boost fallback).
    """
    sql = text("""
        WITH avg_pop AS (
            SELECT dong_name, AVG(total_pop) AS dong_avg
              FROM living_population
             WHERE dong_code LIKE '114%'
               AND date >= :start_date
               AND date < :end_date
             GROUP BY dong_name
        )
        SELECT lp.dong_name, lp.time_zone,
               (lp.date - :start_date) AS day_idx,
               lp.total_pop, ap.dong_avg
          FROM living_population lp
          JOIN avg_pop ap ON ap.dong_name = lp.dong_name
         WHERE lp.dong_code LIKE '114%'
           AND lp.date >= :start_date
           AND lp.date < :end_date
    """)
    end_date = start_date + _timedelta(days=days)
    out: dict[tuple[str, int, int], float] = {}
    db_url = os.environ.get("POSTGRES_URL")
    if not db_url:
        return out
    engine = get_sync_engine(db_url)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"start_date": start_date, "end_date": end_date}).mappings()
        for r in rows:
            avg = float(r["dong_avg"] or 0)
            if avg <= 0:
                continue
            ratio = float(r["total_pop"] or 0) / avg
            ratio = max(0.5, min(ratio, 2.0))  # clamp 0.5~2.0
            out[(r["dong_name"], int(r["time_zone"]), int(r["day_idx"]))] = ratio
    return out
