"""SP2 — DB에 수집된 법령/판례 본문을 chunks.json에 추가.

`law_legislations.body_text` (51건) 및 `law_precedents.body_text` (222건)을
조문/케이스 단위로 청킹하여 기존 `processed/chunks.json` (PDF 청크 1,307개) 에
병합한다. 기존 청크는 보존되며, 동일 chunk_id 는 dedup된다.

호출:
    cd backend && python -m data.legal.build_law_chunks

전제:
    - `fetch_law_bodies.py` 실행 완료 (body_text 채워짐)
    - parse_pdfs.py 가 이미 chunks.json 생성

환경변수:
    POSTGRES_URL: PostgreSQL 연결 주소

설계:
    - 법령: `제\\d+조(?:의\\d+)?[\\s(]` 정규식 split → 조문 청크.
      MAX_CHUNK_LEN(1000자) 초과 시 _split_article_semantic 으로 의미 단위 분할.
      category = "법령_본문", article = "제N조", source = law_short_name or title.
    - 판례: 1 케이스 = 1 청크 원칙. 1500자 초과 시 _split_long_text(1000, overlap=100).
      category = "판례", article = case_number (또는 "판례_본문"), source = case_name.
    - 모든 청크 metadata에 chunk_id, source, category, article 4개 키 포함.
    - parse_pdfs._make_chunk_id / _normalize_for_hash / _dedupe_chunks 재사용.
"""

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

# parse_pdfs 함수 재사용 (모듈로 import)
from . import parse_pdfs

if sys.platform == "win32":
    import asyncio

    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@db:5432/mapo_simulator")
CHUNKS_PATH = Path(__file__).parent / "processed" / "chunks.json"

# 법령 조문 청크 최대 길이 — 초과 시 _split_article_semantic 으로 추가 분할
MAX_CHUNK_LEN = 1000
# 판례 단일 청크 한도 — 이를 넘으면 슬라이딩 분할
PRECEDENT_SINGLE_CHUNK_LIMIT = 1500
PRECEDENT_SPLIT_SIZE = 1000
PRECEDENT_SPLIT_OVERLAP = 100

# 조문 시작 정규식 — parse_pdfs.split_by_article 와 동일 패턴
_ARTICLE_PATTERN = re.compile(r"(?=제\d+조(?:의\d+)?[\s(])")
_ARTICLE_NUM = re.compile(r"(제\d+조(?:의\d+)?)")

LEGISLATION_CATEGORY = "법령_본문"
PRECEDENT_CATEGORY = "판례"


def _fetch_legislation_rows(conn) -> list[tuple[str, str, str, str]]:
    """반환: [(item_id, title, law_short_name, body_text), ...] — body_text NULL 제외."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT item_id, title, law_short_name, body_text
            FROM law_legislations
            WHERE body_text IS NOT NULL AND length(body_text) > 0
            """
        )
        return cur.fetchall()


def _fetch_precedent_rows(conn) -> list[tuple[str, str, str, str]]:
    """반환: [(item_id, case_number, case_name, body_text), ...] — body_text NULL 제외."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT item_id, case_number, case_name, body_text
            FROM law_precedents
            WHERE body_text IS NOT NULL AND length(body_text) > 0
            """
        )
        return cur.fetchall()


def _build_legislation_chunks(rows: list[tuple[str, str, str, str]]) -> list[dict]:
    """법령 51건 → 조문 단위 청크."""
    chunks: list[dict] = []
    for item_id, title, law_short_name, body in rows:
        if not body:
            continue
        # source 우선순위: 약칭 → title → item_id (안전망)
        source = (law_short_name or title or item_id or "").strip()
        if not source:
            continue

        parts = _ARTICLE_PATTERN.split(body)
        for part in parts:
            part = (part or "").strip()
            if not part:
                continue

            article_match = _ARTICLE_NUM.match(part)
            article_num = article_match.group(1) if article_match else "미분류"

            if len(part) <= MAX_CHUNK_LEN:
                chunk = parse_pdfs._make_chunk(part, LEGISLATION_CATEGORY, article_num, source)
                if chunk:
                    chunks.append(chunk)
            else:
                # 항(①②③) → 문장 → 고정길이 순 의미 분할
                sub_parts = parse_pdfs._split_article_semantic(part, MAX_CHUNK_LEN, article_header=part)
                for sub in sub_parts:
                    chunk = parse_pdfs._make_chunk(sub, LEGISLATION_CATEGORY, article_num, source)
                    if chunk:
                        chunks.append(chunk)
    return chunks


def _build_precedent_chunks(rows: list[tuple[str, str, str, str]]) -> list[dict]:
    """판례 222건 → 케이스당 1청크 (긴 케이스만 분할)."""
    chunks: list[dict] = []
    for item_id, case_number, case_name, body in rows:
        if not body:
            continue

        source = (case_name or case_number or item_id or "").strip()
        article = (case_number or "판례_본문").strip()
        if not source:
            continue

        body = body.strip()
        if len(body) <= PRECEDENT_SINGLE_CHUNK_LIMIT:
            chunk = parse_pdfs._make_chunk(body, PRECEDENT_CATEGORY, article, source)
            if chunk:
                chunks.append(chunk)
        else:
            sub_parts = parse_pdfs._split_long_text(body, PRECEDENT_SPLIT_SIZE, PRECEDENT_SPLIT_OVERLAP)
            for sub in sub_parts:
                chunk = parse_pdfs._make_chunk(sub, PRECEDENT_CATEGORY, article, source)
                if chunk:
                    chunks.append(chunk)
    return chunks


def _load_existing_chunks() -> list[dict]:
    if not CHUNKS_PATH.exists():
        print(f"[WARN] {CHUNKS_PATH} 없음 — 빈 리스트로 시작 (PDF 청크 미생성 상태)")
        return []
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        existing = json.load(f)
    print(f"기존 chunks.json 로드: {len(existing)}개 청크")
    return existing


def main() -> None:
    import psycopg

    print("=== SP2 법령/판례 본문 청킹 ===")
    print(f"POSTGRES_URL: {POSTGRES_URL.split('@')[-1] if '@' in POSTGRES_URL else POSTGRES_URL}")

    with psycopg.connect(POSTGRES_URL) as conn:
        leg_rows = _fetch_legislation_rows(conn)
        prec_rows = _fetch_precedent_rows(conn)

    print(f"법령 본문 행: {len(leg_rows)}개")
    print(f"판례 본문 행: {len(prec_rows)}개")

    leg_chunks = _build_legislation_chunks(leg_rows)
    prec_chunks = _build_precedent_chunks(prec_rows)
    print(f"  → 법령 청크 {len(leg_chunks)}개")
    print(f"  → 판례 청크 {len(prec_chunks)}개")

    existing = _load_existing_chunks()
    merged = existing + leg_chunks + prec_chunks
    before = len(merged)
    deduped = parse_pdfs._dedupe_chunks(merged)
    after = len(deduped)
    print(f"병합 {before}개 → dedup 후 {after}개 (제거 {before - after}개)")

    CHUNKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)

    print()
    print(
        f"완료: 법령 청크 {len(leg_chunks)}개, 판례 청크 {len(prec_chunks)}개, "
        f"총 chunks.json {len(deduped)}개 → {CHUNKS_PATH}"
    )


if __name__ == "__main__":
    main()
