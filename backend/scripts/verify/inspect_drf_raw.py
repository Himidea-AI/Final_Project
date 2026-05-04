"""Inspect raw DRF API response structure for 식품위생법 article 41/43."""

import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

POSTGRES_URL = os.getenv("POSTGRES_URL")
LAW_OC = os.getenv("LAW_OC", "bat1120")

import psycopg  # noqa: E402

with psycopg.connect(POSTGRES_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT raw_json FROM law_legislations WHERE title='식품위생법'")
        (raw,) = cur.fetchone()

if isinstance(raw, str):
    raw = json.loads(raw)

mst = raw.get("법령일련번호")
print(f"MST={mst}")

# Re-fetch from API
url = "https://www.law.go.kr/DRF/lawService.do"
r = httpx.get(url, params={"OC": LAW_OC, "target": "law", "MST": str(mst), "type": "JSON"}, timeout=30.0)
r.raise_for_status()
data = r.json()

law = data.get("법령") or {}
jomun = law.get("조문") or {}
units = jomun.get("조문단위")
if isinstance(units, dict):
    units = [units]
units = units or []

print(f"조문단위 count = {len(units)}")
print()

# Find articles 39, 40, 41, 41-2, 42, 43
for u in units:
    article_no = u.get("조문번호") or u.get("조문번호_숫자") or "?"
    article_sub = u.get("조문가지번호") or ""
    article_title = u.get("조문제목") or ""
    article_yn = u.get("조문여부") or ""
    try:
        n_int = int(str(article_no).strip())
    except Exception:
        continue
    if 39 <= n_int <= 45:
        print(f"--- 조문번호={article_no} 가지={article_sub!r} 제목={article_title!r} 여부={article_yn!r} ---")
        print(f"  keys: {list(u.keys())}")
        # Show 조문내용 truncated
        content = u.get("조문내용") or ""
        if isinstance(content, list):
            content = " | ".join(str(x) for x in content)
        print(f"  조문내용[:200]: {str(content)[:200]!r}")
        # Show 항 first if any
        hangs = u.get("항")
        if hangs:
            if isinstance(hangs, dict):
                hangs = [hangs]
            print(f"  항 count={len(hangs)}")
            for h in hangs[:1]:
                hcontent = h.get("항내용") if isinstance(h, dict) else ""
                print(f"    항내용[:150]: {str(hcontent)[:150]!r}")
        print()
