"""
Naver DataLab 트렌드 전면 재수집 (2019-01 ~ 2026-04, timeUnit=month)

현재 naver_trend_monthly의 (scope, keyword) 조합 전체를 DataLab API로 재조회하여
UPSERT. 이후 naver_trend_quarterly를 AVG(ratio) 기준으로 재계산.

실행: python scripts/collect_naver_trend_rebuild.py
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(".env")

NAVER_ID = os.environ["NAVER_CLIENT_ID"]
NAVER_SECRET = os.environ["NAVER_CLIENT_SECRET"]
DB_URL = os.environ["POSTGRES_URL"]

START_DATE = "2019-01-01"
END_DATE = "2026-04-19"
TIME_UNIT = "month"
GROUP_SIZE = 5
SLEEP_BETWEEN = 0.12

API_URL = "https://openapi.naver.com/v1/datalab/search"
HEADERS = {
    "X-Naver-Client-Id": NAVER_ID,
    "X-Naver-Client-Secret": NAVER_SECRET,
    "Content-Type": "application/json",
}


def fetch_group(keywords: list[str]) -> dict[str, list[tuple[date, float]]]:
    body = {
        "startDate": START_DATE,
        "endDate": END_DATE,
        "timeUnit": TIME_UNIT,
        "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in keywords],
    }
    for attempt in range(3):
        try:
            with httpx.Client(timeout=30) as client:
                r = client.post(API_URL, json=body, headers=HEADERS)
                r.raise_for_status()
                data = r.json()
            break
        except Exception as exc:
            if attempt == 2:
                raise
            print(f"    retry {attempt + 1}: {exc}", flush=True)
            time.sleep(2**attempt)

    out: dict[str, list[tuple[date, float]]] = {}
    for res in data.get("results", []):
        kw = res["title"]
        series = [(date.fromisoformat(pt["period"]), float(pt["ratio"])) for pt in res.get("data", [])]
        out[kw] = series
    return out


def main() -> int:
    eng = create_engine(DB_URL, pool_size=1, max_overflow=0)

    with eng.connect() as c:
        pairs = c.execute(
            text("SELECT DISTINCT scope, keyword FROM naver_trend_monthly ORDER BY scope, keyword")
        ).fetchall()

    by_scope: dict[str, list[str]] = {}
    for scope, kw in pairs:
        by_scope.setdefault(scope, []).append(kw)
    total_kw = sum(len(v) for v in by_scope.values())
    print(f"키워드 총 {total_kw}개 / scope별: " + ", ".join(f"{s}={len(v)}" for s, v in by_scope.items()), flush=True)

    all_rows: list[tuple[str, str, date, float]] = []

    for scope, kws in by_scope.items():
        groups = [kws[i : i + GROUP_SIZE] for i in range(0, len(kws), GROUP_SIZE)]
        print(f"\n=== scope={scope}: {len(kws)} kw / {len(groups)} 요청 ===", flush=True)
        for gi, group in enumerate(groups, 1):
            try:
                res = fetch_group(group)
            except Exception as exc:
                print(f"  [error] group {gi}: {exc}", flush=True)
                continue
            hit = sum(len(v) for v in res.values())
            for kw, series in res.items():
                for per, rat in series:
                    all_rows.append((scope, kw, per, rat))
            print(f"  [{gi:3d}/{len(groups)}] {group} → {hit}행", flush=True)
            time.sleep(SLEEP_BETWEEN)

    print(f"\n수집 완료: 총 {len(all_rows):,} 행", flush=True)

    # UPSERT monthly (DELETE + INSERT 단순화)
    print("\n=== monthly 적재 ===", flush=True)
    with eng.begin() as c:
        n_del = c.execute(text("DELETE FROM naver_trend_monthly")).rowcount
        print(f"  기존 {n_del:,} 행 삭제", flush=True)
        # bulk insert
        CHUNK = 1000
        for i in range(0, len(all_rows), CHUNK):
            chunk = all_rows[i : i + CHUNK]
            c.execute(
                text("INSERT INTO naver_trend_monthly (keyword, period, ratio, scope) VALUES (:kw, :pe, :ra, :sc)"),
                [{"kw": r[1], "pe": r[2], "ra": r[3], "sc": r[0]} for r in chunk],
            )
        print(f"  {len(all_rows):,} 행 insert 완료", flush=True)

    # Quarterly 재계산: scope, dong, quarter 별 AVG(ratio)
    # dong_name = keyword의 첫 공백 앞 토큰
    print("\n=== quarterly 재계산 ===", flush=True)
    with eng.begin() as c:
        c.execute(text("DELETE FROM naver_trend_quarterly"))
        c.execute(
            text("""
            INSERT INTO naver_trend_quarterly (quarter, dong_name, trend_score, scope)
            SELECT
              (EXTRACT(YEAR FROM period)::int) * 10 + EXTRACT(QUARTER FROM period)::int AS quarter,
              split_part(keyword, ' ', 1) AS dong_name,
              AVG(ratio) AS trend_score,
              scope
            FROM naver_trend_monthly
            GROUP BY quarter, dong_name, scope
            ORDER BY quarter, scope, dong_name
        """)
        )
        n = c.execute(text("SELECT COUNT(*) FROM naver_trend_quarterly")).scalar()
        print(f"  quarterly {n:,} 행 재계산 완료", flush=True)

    # Verify
    print("\n=== 검증 ===", flush=True)
    with eng.connect() as c:
        mn, mx = c.execute(text("SELECT MIN(period), MAX(period) FROM naver_trend_monthly")).fetchone()
        print(f"  monthly 기간: {mn} ~ {mx}")
        mn_q, mx_q = c.execute(text("SELECT MIN(quarter), MAX(quarter) FROM naver_trend_quarterly")).fetchone()
        print(f"  quarterly 범위: {mn_q} ~ {mx_q}")
        for q in (20244, 20251, 20261):
            v = c.execute(
                text(
                    "SELECT trend_score FROM naver_trend_quarterly WHERE scope='mapo' AND dong_name='공덕동' AND quarter=:q"
                ),
                {"q": q},
            ).scalar()
            print(f"  공덕동 (mapo) {q}: {v}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
