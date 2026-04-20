"""카카오 place-api panel3 로 kakao_store 전수 점포의 메뉴+영업시간 수집.

엔드포인트: https://place-api.map.kakao.com/places/panel3/{kakao_id}
- open_hours: 영업시간 → kakao_store_hours (UPSERT)
- menu.menus.items[]: 메뉴 → kakao_store_menu (REPLACE per kakao_id)

실행: python scripts/collect_kakao_menus.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Windows 콘솔 UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

DB_URL = os.environ["POSTGRES_URL"]
engine = create_engine(DB_URL, echo=False)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Referer": "https://place.map.kakao.com/",
    "Accept": "application/json, text/plain, */*",
    "pf": "web",
}

DAY_MAP = {
    "월": "mon",
    "화": "tue",
    "수": "wed",
    "목": "thu",
    "금": "fri",
    "토": "sat",
    "일": "sun",
}

UPSERT_HOURS_SQL = text(
    """
    INSERT INTO kakao_store_hours (
        kakao_id, headline_code, headline_text,
        mon_hours, tue_hours, wed_hours, thu_hours,
        fri_hours, sat_hours, sun_hours, hours_json, collected_at
    ) VALUES (
        :kakao_id, :headline_code, :headline_text,
        :mon_hours, :tue_hours, :wed_hours, :thu_hours,
        :fri_hours, :sat_hours, :sun_hours, CAST(:hours_json AS JSONB), NOW()
    )
    ON CONFLICT (kakao_id) DO UPDATE SET
        headline_code = EXCLUDED.headline_code,
        headline_text = EXCLUDED.headline_text,
        mon_hours = EXCLUDED.mon_hours,
        tue_hours = EXCLUDED.tue_hours,
        wed_hours = EXCLUDED.wed_hours,
        thu_hours = EXCLUDED.thu_hours,
        fri_hours = EXCLUDED.fri_hours,
        sat_hours = EXCLUDED.sat_hours,
        sun_hours = EXCLUDED.sun_hours,
        hours_json = EXCLUDED.hours_json,
        collected_at = NOW();
    """
)

DELETE_MENU_SQL = text("DELETE FROM kakao_store_menu WHERE kakao_id = :kakao_id")
INSERT_MENU_SQL = text(
    """
    INSERT INTO kakao_store_menu (
        kakao_id, product_id, menu_name, price, description, photo_url, mod_at
    ) VALUES (
        :kakao_id, :product_id, :menu_name, :price, :description, :photo_url, :mod_at
    )
    ON CONFLICT (kakao_id, product_id) DO UPDATE SET
        menu_name = EXCLUDED.menu_name,
        price = EXCLUDED.price,
        description = EXCLUDED.description,
        photo_url = EXCLUDED.photo_url,
        mod_at = EXCLUDED.mod_at,
        collected_at = NOW();
    """
)


def parse_hours(open_hours: dict | None) -> dict:
    out: dict = {f"{v}_hours": None for v in DAY_MAP.values()}
    out["headline_code"] = None
    out["headline_text"] = None
    if not isinstance(open_hours, dict):
        return out
    headline = open_hours.get("headline", {}) or {}
    out["headline_code"] = headline.get("code")
    out["headline_text"] = headline.get("display_text")
    for period in (open_hours.get("all") or {}).get("periods") or []:
        for day in period.get("days", []):
            desc = day.get("day_of_the_week_desc", "")
            time_desc = (day.get("on_days") or {}).get("start_end_time_desc") or (day.get("off_days") or {}).get(
                "display_text"
            )
            for kor, eng in DAY_MAP.items():
                if kor in desc:
                    out[f"{eng}_hours"] = time_desc
    return out


def parse_menu_items(menu: dict | None) -> list[dict]:
    """panel3 응답의 menu.menus.items[] → row dict 리스트."""
    if not isinstance(menu, dict):
        return []
    items = ((menu.get("menus") or {}).get("items")) or []
    rows: list[dict] = []
    for it in items:
        pid = it.get("product_id")
        if pid is None:
            continue
        mod_raw = it.get("mod_at")
        mod_dt = None
        if mod_raw:
            try:
                mod_dt = datetime.strptime(mod_raw, "%Y-%m-%d %H:%M:%S")
            except Exception:
                mod_dt = None
        price = it.get("price")
        if isinstance(price, str):
            price = int("".join(filter(str.isdigit, price)) or 0)
        # Kakao 센티넬 -1 (가격 미등록) 은 NULL 로 정규화
        if not isinstance(price, int) or price <= 0:
            price = None
        rows.append(
            {
                "product_id": int(pid),
                "menu_name": (it.get("name") or "").strip() or "(무명)",
                "price": price,
                "description": it.get("desc"),
                "photo_url": it.get("photo_url"),
                "mod_at": mod_dt,
            }
        )
    return rows


async def fetch_panel3(client: httpx.AsyncClient, kakao_id: str) -> dict | None:
    url = f"https://place-api.map.kakao.com/places/panel3/{kakao_id}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


async def worker(
    sem: asyncio.Semaphore,
    client: httpx.AsyncClient,
    kakao_id: str,
) -> tuple[str, dict | None, list[dict]]:
    async with sem:
        data = await fetch_panel3(client, kakao_id)
        if not data:
            return kakao_id, None, []
        hours_parsed = parse_hours(data.get("open_hours"))
        menu_rows = parse_menu_items(data.get("menu"))
        # open_hours 원본은 jsonb 로 저장
        hours_parsed["hours_json"] = json.dumps(data.get("open_hours") or {}, ensure_ascii=False)
        return kakao_id, hours_parsed, menu_rows


async def main() -> None:
    # 대상 점포 로드
    with engine.connect() as c:
        kakao_ids = [r[0] for r in c.execute(text("SELECT kakao_id FROM kakao_store ORDER BY kakao_id"))]
    print(f"대상: {len(kakao_ids)}개 점포\n")

    sem = asyncio.Semaphore(8)  # 동시 8개
    t0 = time.time()
    hours_count = 0
    menu_count_total = 0
    no_hours = 0
    no_menu = 0

    async with httpx.AsyncClient() as client:
        tasks = [worker(sem, client, kid) for kid in kakao_ids]
        batch: list[tuple[str, dict | None, list[dict]]] = []

        for i, task in enumerate(asyncio.as_completed(tasks), 1):
            kid, hours, menu_rows = await task
            batch.append((kid, hours, menu_rows))

            # 100건마다 DB 플러시
            if len(batch) >= 100 or i == len(kakao_ids):
                with engine.begin() as c:
                    for k, h, items in batch:
                        if h is not None:
                            c.execute(UPSERT_HOURS_SQL, {"kakao_id": k, **h})
                            hours_count += 1
                        else:
                            no_hours += 1
                        # menu 는 kakao_id 별 REPLACE 후 재삽입
                        if items:
                            c.execute(DELETE_MENU_SQL, {"kakao_id": k})
                            for item in items:
                                c.execute(INSERT_MENU_SQL, {"kakao_id": k, **item})
                            menu_count_total += len(items)
                        else:
                            no_menu += 1
                elapsed = time.time() - t0
                rate = i / elapsed if elapsed > 0 else 0
                eta = (len(kakao_ids) - i) / rate if rate > 0 else 0
                print(
                    f"  [{i:>4}/{len(kakao_ids)}] hours={hours_count} menus={menu_count_total} "
                    f"(skip hours={no_hours}, no-menu={no_menu}) "
                    f"| {rate:.1f}/s, ETA {eta:.0f}s"
                )
                batch.clear()

    print(f"\n완료: {time.time() - t0:.1f}s")
    print(f"영업시간 저장: {hours_count} / 전체 {len(kakao_ids)}")
    print(f"메뉴 아이템 저장: {menu_count_total} (메뉴 있는 점포 {len(kakao_ids) - no_menu})")


if __name__ == "__main__":
    asyncio.run(main())
