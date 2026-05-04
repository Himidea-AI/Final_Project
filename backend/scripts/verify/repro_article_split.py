"""Reproduce article split off-by-one bug for 식품위생법.

Run from backend dir:
    cd backend && python scripts/verify/repro_article_split.py
"""

import os
import re
from pathlib import Path

from dotenv import load_dotenv

# Force load from project root .env
ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

POSTGRES_URL = os.getenv("POSTGRES_URL")
print(f"DB host: {POSTGRES_URL.split('@')[-1] if POSTGRES_URL else 'NONE'}")

import psycopg  # noqa: E402  # imported after dotenv to ensure POSTGRES_URL is loaded

ARTICLE_PATTERN = re.compile(r"(?=제\d+조(?:의\d+)?[\s(])")
ARTICLE_NUM = re.compile(r"(제\d+조(?:의\d+)?)")

TARGET_LAWS = ["식품위생법", "부가가치세법", "근로기준법", "하수도법"]


def fetch_law(conn, title: str):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT title, length(body_text), body_text FROM law_legislations WHERE title=%s",
            (title,),
        )
        return cur.fetchone()


def analyze_split(title: str, body: str, focus_articles: list[int]) -> None:
    print(f"\n{'=' * 80}\n{title} (len={len(body)})\n{'=' * 80}")

    # Show raw context around each focus article
    for n in focus_articles:
        art = f"제{n}조"
        positions = [m.start() for m in re.finditer(re.escape(art) + r"(?:의\d+)?[\s(]", body)]
        print(f"\n[raw] {art} occurrences (with [\\s(] suffix) = {len(positions)}: {positions[:3]}")
        for p in positions[:2]:
            ctx_before = body[max(0, p - 60) : p].replace("\n", "|")
            ctx_at = body[p : p + 100].replace("\n", "|")
            print(f"  @{p}: ...{ctx_before!r} >>> {ctx_at!r}")

    # Run the split
    parts = ARTICLE_PATTERN.split(body)
    print(f"\n[split] total parts = {len(parts)}")

    # Walk through parts and show those covering articles around focus
    focus_min = min(focus_articles) - 2
    focus_max = max(focus_articles) + 2
    for i, p in enumerate(parts):
        p_strip = p.strip()
        if not p_strip:
            continue
        m = ARTICLE_NUM.match(p_strip)
        if not m:
            continue
        label = m.group(1)
        nm = re.match(r"제(\d+)조", label)
        if not nm:
            continue
        n = int(nm.group(1))
        if focus_min <= n <= focus_max:
            head = p_strip[:200].replace("\n", " | ")
            tail = p_strip[-100:].replace("\n", " | ") if len(p_strip) > 200 else ""
            print(f"\n  part {i:3d} label={label:12s} len={len(p_strip):5d}")
            print(f"    HEAD: {head!r}")
            if tail:
                print(f"    TAIL: {tail!r}")


def main():
    targets = [
        ("식품위생법", [40, 41, 43, 51]),
        ("부가가치세법", [7, 8, 31, 32, 33, 34, 60, 61, 62, 63]),
        ("근로기준법", [43, 56, 69]),
        ("하수도법", [33, 34, 37, 38]),
    ]

    with psycopg.connect(POSTGRES_URL) as conn:
        for title, focus in targets:
            row = fetch_law(conn, title)
            if not row:
                print(f"[ERR] {title} not found in DB")
                continue
            _, _, body = row
            analyze_split(title, body, focus)


if __name__ == "__main__":
    main()
