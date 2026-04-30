"""
SP2 — 법령/판례 본문을 law.go.kr DRF API에서 수집하여 DB에 캐시.

호출:
    cd backend && python -m data.legal.fetch_law_bodies [--retry-failed]

대상:
    - law_legislations: 법령일련번호(raw_json['법령일련번호']) → lawService.do?target=law&MST=
    - law_precedents:   판례일련번호(raw_json['판례일련번호']) → lawService.do?target=prec&ID=

저장:
    body_text         : 평문 본문 (HTML 태그 제거 후)
    body_fetched_at   : 수집 시각

멱등성:
    body_fetched_at IS NOT NULL인 행은 기본 skip. --retry-failed로 NULL만 재시도.

API rate limit 보호:
    - 동시 N=5개 요청 (semaphore)
    - 각 요청 timeout 15s, 1회 재시도
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/mapo_simulator")
LAW_OC = os.getenv("LAW_OC", "bat1120")
BASE_URL = "https://www.law.go.kr/DRF"
TIMEOUT = 15.0
CONCURRENCY = 5  # 동시 API 요청 한도 (politeness)
MAX_RETRIES = 1


def _strip_html(value) -> str:
    """API 응답 HTML 태그 제거 + 공백 정규화.

    DRF API는 같은 필드를 dict/list/str/nested-list 등 다양한 형태로 반환.
    재귀적으로 평탄화하여 안전하게 평문화.
    """
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_strip_html(x) for x in value if x is not None).strip()
    if isinstance(value, dict):
        return " ".join(_strip_html(v) for v in value.values() if v is not None).strip()
    if not isinstance(value, str):
        value = str(value)
    cleaned = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_legislation_body(data: dict) -> str:
    """lawService.do (target=law) JSON → 조문 본문 평문 결합"""
    law = data.get("법령") or {}
    parts: list[str] = []

    # 기본 정보
    basic = law.get("기본정보") or {}
    title = basic.get("법령명_한글") or basic.get("법령명한글") or ""
    if title:
        parts.append(f"[법령명] {title}")

    # 조문 본문
    jomun = law.get("조문") or {}
    units = jomun.get("조문단위")
    if isinstance(units, dict):
        units = [units]
    units = units or []

    for u in units:
        # 조문내용 + 항(전부) + 호(전부)을 단일 텍스트로 평탄화
        # _strip_html은 list/dict/nested 안전 처리
        merged_unit = " ".join(_strip_html(v) for v in u.values() if v is not None).strip()
        if merged_unit:
            parts.append(merged_unit)

    # 부칙
    booklet = law.get("부칙") or {}
    addenda = booklet.get("부칙단위")
    if isinstance(addenda, dict):
        addenda = [addenda]
    if addenda:
        for ad in addenda:
            adtext = _strip_html(ad.get("부칙내용", ""))
            if adtext:
                parts.append(f"[부칙] {adtext}")

    return "\n".join(parts).strip()


def _extract_precedent_body(data: dict) -> str:
    """lawService.do (target=prec) JSON → 판시사항+판결요지+참조조문 결합"""
    p = data.get("PrecService") or {}
    parts: list[str] = []
    for k, label in [("판시사항", "판시사항"), ("판결요지", "판결요지"), ("참조조문", "참조조문")]:
        text = _strip_html(p.get(k, ""))
        if text:
            parts.append(f"[{label}]\n{text}")
    return "\n\n".join(parts).strip()


async def _fetch_legislation(client: httpx.AsyncClient, sem: asyncio.Semaphore, mst: str) -> str:
    async with sem:
        for attempt in range(MAX_RETRIES + 1):
            try:
                r = await client.get(
                    f"{BASE_URL}/lawService.do",
                    params={"OC": LAW_OC, "target": "law", "MST": mst, "type": "JSON"},
                    timeout=TIMEOUT,
                )
                r.raise_for_status()
                return _extract_legislation_body(r.json())
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                if attempt < MAX_RETRIES:
                    print(f"  [retry {attempt + 1}] MST={mst}: {e}")
                    continue
                raise
        return ""


async def _fetch_precedent(client: httpx.AsyncClient, sem: asyncio.Semaphore, prec_id: str) -> str:
    async with sem:
        for attempt in range(MAX_RETRIES + 1):
            try:
                r = await client.get(
                    f"{BASE_URL}/lawService.do",
                    params={"OC": LAW_OC, "target": "prec", "ID": prec_id, "type": "JSON"},
                    timeout=TIMEOUT,
                )
                r.raise_for_status()
                return _extract_precedent_body(r.json())
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                if attempt < MAX_RETRIES:
                    print(f"  [retry {attempt + 1}] PREC={prec_id}: {e}")
                    continue
                raise
        return ""


async def fetch_legislations(retry_failed: bool = False) -> tuple[int, int]:
    """반환: (시도, 성공)"""
    import psycopg

    where = "WHERE body_fetched_at IS NULL" if retry_failed else "WHERE body_text IS NULL"
    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT item_id, raw_json FROM law_legislations {where}")
            rows = cur.fetchall()

    print(f"법령 대상: {len(rows)}개")
    if not rows:
        return 0, 0

    sem = asyncio.Semaphore(CONCURRENCY)
    success = 0
    async with httpx.AsyncClient() as client:
        for i, (item_id, raw) in enumerate(rows, 1):
            if isinstance(raw, str):
                raw = json.loads(raw)
            mst = (raw or {}).get("법령일련번호")
            if not mst:
                print(f"  [{i}/{len(rows)}] {item_id}: 법령일련번호 없음 - skip")
                continue
            try:
                body = await _fetch_legislation(client, sem, str(mst))
            except Exception as e:
                print(f"  [{i}/{len(rows)}] {item_id} MST={mst} 실패: {e}")
                continue

            now = datetime.now(timezone.utc)
            with psycopg.connect(POSTGRES_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE law_legislations SET body_text=%s, body_fetched_at=%s WHERE item_id=%s",
                        (body, now, item_id),
                    )
                    conn.commit()
            success += 1
            if i % 5 == 0 or i == len(rows):
                print(f"  법령 진행 {i}/{len(rows)} (성공 {success})")
    return len(rows), success


async def fetch_precedents(retry_failed: bool = False) -> tuple[int, int]:
    import psycopg

    where = "WHERE body_fetched_at IS NULL" if retry_failed else "WHERE body_text IS NULL"
    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT item_id, raw_json FROM law_precedents {where}")
            rows = cur.fetchall()

    print(f"판례 대상: {len(rows)}개")
    if not rows:
        return 0, 0

    sem = asyncio.Semaphore(CONCURRENCY)
    success = 0
    async with httpx.AsyncClient() as client:
        for i, (item_id, raw) in enumerate(rows, 1):
            if isinstance(raw, str):
                raw = json.loads(raw)
            prec_id = (raw or {}).get("판례일련번호")
            if not prec_id:
                print(f"  [{i}/{len(rows)}] {item_id}: 판례일련번호 없음 - skip")
                continue
            try:
                body = await _fetch_precedent(client, sem, str(prec_id))
            except Exception as e:
                print(f"  [{i}/{len(rows)}] {item_id} ID={prec_id} 실패: {e}")
                continue

            now = datetime.now(timezone.utc)
            with psycopg.connect(POSTGRES_URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE law_precedents SET body_text=%s, body_fetched_at=%s WHERE item_id=%s",
                        (body, now, item_id),
                    )
                    conn.commit()
            success += 1
            if i % 20 == 0 or i == len(rows):
                print(f"  판례 진행 {i}/{len(rows)} (성공 {success})")
    return len(rows), success


async def main() -> None:
    retry_failed = "--retry-failed" in sys.argv

    print(f"LAW_OC: {LAW_OC}")
    print(f"동시성: {CONCURRENCY}, timeout: {TIMEOUT}s, retry-failed: {retry_failed}")
    print()

    print("=== 법령 본문 수집 ===")
    leg_total, leg_ok = await fetch_legislations(retry_failed)
    print()
    print("=== 판례 본문 수집 ===")
    prec_total, prec_ok = await fetch_precedents(retry_failed)
    print()
    print(f"완료: 법령 {leg_ok}/{leg_total}, 판례 {prec_ok}/{prec_total}")


if __name__ == "__main__":
    asyncio.run(main())
