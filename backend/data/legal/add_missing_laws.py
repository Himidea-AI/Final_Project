"""SP6+ — Ragas reference 본문 미수록 3개 법령 추가 fetch.

골든셋 CSV의 law 중 DB에 없는 것:
- 공정거래법 (독점규제 및 공정거래에 관한 법률)
- 장애인편의법 (장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률)
- 하수도법

Pipeline:
1. lawSearch.do?target=law&query=<name>     → 검색해서 MST 후보 list
2. lawService.do?target=law&MST=<MST>        → 본문 fetch
3. INSERT INTO law_legislations              → 기존 fetch_law_bodies 로직 재사용 가능

이후 사용자가 추가로 실행:
    python -m data.legal.build_law_chunks
    python -m data.legal.reingest --upsert
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psycopg
from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from data.legal.fetch_law_bodies import _extract_legislation_body  # noqa: E402

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/mapo_simulator")
LAW_OC = os.getenv("LAW_OC", "bat1120")
BASE_URL = "https://www.law.go.kr/DRF"
TIMEOUT = 20.0

# (CSV 표기, lawSearch query, 정확 매칭할 법령명 prefix)
TARGETS: list[tuple[str, str, str]] = [
    ("공정거래법", "독점규제 및 공정거래에 관한 법률", "독점규제 및 공정거래에 관한 법률"),
    ("장애인편의법", "장애인·노인·임산부 등의 편의증진 보장에 관한 법률", "장애인"),
    ("하수도법", "하수도법", "하수도법"),
]


async def _search_law(client: httpx.AsyncClient, query: str) -> list[dict]:
    """lawSearch.do 결과 list 반환."""
    r = await client.get(
        f"{BASE_URL}/lawSearch.do",
        params={"OC": LAW_OC, "target": "law", "type": "JSON", "query": query, "display": 20},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    laws = data.get("LawSearch", {}).get("law") or []
    if isinstance(laws, dict):
        laws = [laws]
    return laws


def _pick_best(laws: list[dict], prefix: str) -> dict | None:
    """현행, 법률 (시행령/시행규칙 X), 정확 prefix 매칭 우선."""
    candidates = []
    for law in laws:
        name = (law.get("법령명한글") or "").strip()
        ltype = (law.get("법령구분명") or "").strip()
        revision = (law.get("현행연혁코드") or "").strip()
        if not name.startswith(prefix):
            continue
        if "시행령" in name or "시행규칙" in name:
            continue
        if ltype != "법률":
            continue
        score = 0
        if revision == "현행":
            score += 10
        candidates.append((score, law))
    if not candidates:
        # fallback — 시행령/규칙 제외만
        for law in laws:
            name = (law.get("법령명한글") or "").strip()
            if name.startswith(prefix) and "시행령" not in name and "시행규칙" not in name:
                return law
        return None
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


async def _fetch_body(client: httpx.AsyncClient, mst: str) -> str:
    r = await client.get(
        f"{BASE_URL}/lawService.do",
        params={"OC": LAW_OC, "target": "law", "MST": mst, "type": "JSON"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return _extract_legislation_body(r.json())


def _upsert_legislation(item_id: str, title: str, short: str, raw_json: dict, body: str) -> None:
    now = datetime.now(timezone.utc)
    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO law_legislations
                    (item_id, title, law_short_name, promulgation_date, enforce_date,
                     promulgation_no, ministry_name, law_type, law_revision_type,
                     detail_link, raw_json, queries, collected_at, body_text, body_fetched_at)
                VALUES
                    (%(item_id)s, %(title)s, %(short)s, NULL, NULL,
                     %(no)s, %(ministry)s, %(ltype)s, %(rtype)s,
                     %(link)s, %(raw)s, %(queries)s, %(now)s, %(body)s, %(now)s)
                ON CONFLICT (item_id) DO UPDATE SET
                    body_text = EXCLUDED.body_text,
                    body_fetched_at = EXCLUDED.body_fetched_at,
                    raw_json = EXCLUDED.raw_json
                """,
                {
                    "item_id": item_id,
                    "title": title,
                    "short": short,
                    "no": str(raw_json.get("공포번호") or ""),
                    "ministry": raw_json.get("소관부처명") or "",
                    "ltype": raw_json.get("법령구분명") or "",
                    "rtype": raw_json.get("제개정구분명") or "",
                    "link": raw_json.get("법령상세링크") or "",
                    "raw": json.dumps(raw_json, ensure_ascii=False),
                    "queries": "ragas-missing-fill",
                    "now": now,
                    "body": body,
                },
            )
            conn.commit()


async def main() -> None:
    print(f"LAW_OC: {LAW_OC}")
    print(f"대상: {len(TARGETS)} 법령\n")

    async with httpx.AsyncClient() as client:
        for csv_label, query, prefix in TARGETS:
            print(f"=== {csv_label} ({query}) ===")
            try:
                laws = await _search_law(client, query)
            except Exception as e:
                print(f"  검색 실패: {e}\n")
                continue

            print(f"  검색 결과: {len(laws)}건")
            picked = _pick_best(laws, prefix)
            if not picked:
                print(f"  매칭 실패 — prefix '{prefix}'\n")
                continue

            mst = str(picked.get("법령일련번호") or "")
            title = (picked.get("법령명한글") or "").strip()
            short = (picked.get("법령약칭명") or "").strip()
            item_id = str(picked.get("법령ID") or mst or "")
            print(f"  매칭: {title} (MST={mst}, ID={item_id}, 약칭={short})")

            try:
                body = await _fetch_body(client, mst)
            except Exception as e:
                print(f"  본문 fetch 실패: {e}\n")
                continue

            print(f"  본문 길이: {len(body):,} chars")
            _upsert_legislation(item_id, title, short, picked, body)
            print(f"  DB upsert OK\n")

    print("완료. 다음 단계:")
    print("  python -m data.legal.build_law_chunks")
    print("  python -m data.legal.reingest --upsert")


if __name__ == "__main__":
    asyncio.run(main())
