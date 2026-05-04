"""End-to-end verification of fetch_law_bodies + split_by_article fix.

Re-fetches 식품위생법 / 부가가치세법 / 근로기준법 / 하수도법 with the FIXED
_extract_legislation_body and runs split_by_article. Verifies metadata.article
matches the actual content.

NOTE: does NOT write to DB / chunks.json — read-only verification.
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from data.legal import fetch_law_bodies, parse_pdfs  # noqa: E402

POSTGRES_URL = os.getenv("POSTGRES_URL")
LAW_OC = os.getenv("LAW_OC", "bat1120")

# (title, [(article_num_int, expected_topic_keyword), ...])
TARGETS = [
    (
        "식품위생법",
        [
            (40, "건강진단"),
            (41, "식품위생교육"),
            (43, "영업 제한"),
            (51, "조리사"),
        ],
    ),
    (
        "부가가치세법",
        [
            (7, "과세 관할"),
            (8, "사업자등록"),
            (32, "세금계산서"),
            (33, "세금계산서 발급의무"),
            (34, "세금계산서 발급시기"),
            (61, "간이과세"),
            (62, "간이과세"),
            (63, "간이과세자"),
        ],
    ),
    (
        "근로기준법",
        [
            (43, "임금"),
            (56, "연장ㆍ야간"),
            (69, "근로시간"),
        ],
    ),
    (
        "하수도법",
        [
            (33, ""),
            (34, ""),
            (37, ""),
            (38, ""),
        ],
    ),
]


def fetch_law_body_via_api(title: str) -> str:
    """DB 에서 MST 만 가져와 API 재호출 (FIX 적용된 _extract_legislation_body 사용)."""
    import psycopg

    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT raw_json FROM law_legislations WHERE title=%s", (title,))
            row = cur.fetchone()
    if not row:
        return ""
    raw = row[0]
    if isinstance(raw, str):
        raw = json.loads(raw)
    mst = raw.get("법령일련번호")
    if not mst:
        return ""
    r = httpx.get(
        "https://www.law.go.kr/DRF/lawService.do",
        params={"OC": LAW_OC, "target": "law", "MST": str(mst), "type": "JSON"},
        timeout=30.0,
    )
    r.raise_for_status()
    return fetch_law_bodies._extract_legislation_body(r.json())


def verify(title: str, expectations: list[tuple[int, str]]) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")
    body = fetch_law_body_via_api(title)
    print(f"body len={len(body)}")
    chunks = parse_pdfs.split_by_article(body, "법령_본문", title)
    by_article: dict[str, list[dict]] = {}
    for c in chunks:
        a = c["metadata"]["article"]
        by_article.setdefault(a, []).append(c)
    print(f"chunks count={len(chunks)}, distinct articles={len(by_article)}")

    ok = 0
    fail = 0
    for n, topic in expectations:
        label = f"제{n}조"
        cs = by_article.get(label, [])
        if not cs:
            print(f"  [MISS] {label} → no chunk")
            fail += 1
            continue
        # show first chunk head
        head = cs[0]["text"][:120].replace("\n", " | ")
        # determine if topic keyword present
        if topic and topic in cs[0]["text"][:600]:
            print(f"  [OK]   {label} ({len(cs)} chunk) topic=[{topic}] HEAD={head!r}")
            ok += 1
        elif not topic:
            print(f"  [INFO] {label} ({len(cs)} chunk) HEAD={head!r}")
            ok += 1
        else:
            print(f"  [FAIL] {label} expected topic=[{topic}] not in HEAD={head!r}")
            fail += 1
    print(f"  → {ok}/{ok + fail} expected articles match content")


def main():
    for title, exp in TARGETS:
        verify(title, exp)


if __name__ == "__main__":
    main()
