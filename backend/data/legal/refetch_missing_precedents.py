"""SP2 보강 — body_text 가 빈 판례를 LSW/precInfoR.do (HTML mirror) 로 재수집.

배경:
    fetch_law_bodies.py 는 lawService.do?target=prec&ID=... 를 호출하지만,
    국세법령정보시스템(taxlaw.nts.go.kr)에서 수집된 일부 판례 (사건종류코드 400107,
    데이터출처명 '국세법령정보시스템') 는 lawService.do 가 "일치하는 판례 없음"
    응답을 반환한다. 이는 해당 판례들이 DRF lawService 백엔드의 prec 인덱스에는
    없지만 law.go.kr 일반 사이트의 LSW/precInfoR.do mirror 페이지에는 존재하기
    때문이다. lawSearch.do 에서는 동일 일련번호로 검색이 되지만 본문은 fetch
    되지 않는다.

해결:
    https://www.law.go.kr/LSW/precInfoR.do?precSeq={판례일련번호}
    HTML 페이지에서 본문을 파싱한다 (script/style 제거 + 태그 제거 + 공백 정규화).

호출:
    cd backend && python -m data.legal.refetch_missing_precedents

대상:
    law_precedents WHERE length(body_text) = 0

저장:
    body_text         : 평문 본문 (LSW HTML 에서 파싱)
    body_fetched_at   : 수집 시각

API politeness:
    - 동시 N=5 요청 (semaphore)
    - 요청 사이 50ms sleep
    - 각 요청 timeout 15s, 1회 재시도
    - 본문 길이 < 200 자는 매핑 실패로 간주, body_text 갱신하지 않음
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

POSTGRES_URL = os.environ["POSTGRES_URL"]
LAW_OC = os.getenv("LAW_OC", "bat1120")
LSW_URL = "https://www.law.go.kr/LSW/precInfoR.do"
TIMEOUT = 15.0
CONCURRENCY = 5
MAX_RETRIES = 1
SLEEP_BETWEEN = 0.05  # 50ms politeness
MIN_BODY_LEN = 200  # 이보다 짧으면 매핑 실패로 간주


def _strip_html(html: str) -> str:
    """script/style 제거 + 태그 제거 + 공백 정규화."""
    if not html:
        return ""
    cleaned = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<style[^>]*>.*?</style>", " ", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"&nbsp;", " ", cleaned)
    cleaned = re.sub(r"&lt;", "<", cleaned)
    cleaned = re.sub(r"&gt;", ">", cleaned)
    cleaned = re.sub(r"&amp;", "&", cleaned)
    cleaned = re.sub(r"&quot;", '"', cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


async def _fetch_lsw_body(client: httpx.AsyncClient, sem: asyncio.Semaphore, prec_seq: str) -> str:
    """LSW/precInfoR.do?precSeq={prec_seq} 의 본문 평문 반환."""
    async with sem:
        for attempt in range(MAX_RETRIES + 1):
            try:
                r = await client.get(
                    LSW_URL,
                    params={"precSeq": prec_seq},
                    timeout=TIMEOUT,
                    follow_redirects=True,
                )
                if r.status_code != 200:
                    return ""
                text = _strip_html(r.text)
                # "본 컨텐츠는 국세법령정보시스템 에서 수집한 데이터로..." 안내 문구는 유지
                # (본문 일부로 간주)
                return text
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                if attempt < MAX_RETRIES:
                    print(f"  [retry {attempt + 1}] precSeq={prec_seq}: {e}")
                    await asyncio.sleep(0.5)
                    continue
                raise
        return ""


async def refetch_empty_bodies() -> tuple[int, int, int, list[str]]:
    """반환: (대상수, 성공수, 매핑실패수, 실패샘플)"""
    import psycopg

    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT item_id, raw_json
                FROM law_precedents
                WHERE length(body_text) = 0
                """
            )
            rows = cur.fetchall()

    total = len(rows)
    print(f"빈 body 대상: {total}건")
    if not rows:
        return 0, 0, 0, []

    sem = asyncio.Semaphore(CONCURRENCY)
    success = 0
    fail = 0
    fail_samples: list[str] = []

    async with httpx.AsyncClient() as client:
        for i, (item_id, raw) in enumerate(rows, 1):
            if isinstance(raw, str):
                raw = json.loads(raw)
            prec_seq = (raw or {}).get("판례일련번호")
            if not prec_seq:
                fail += 1
                if len(fail_samples) < 5:
                    fail_samples.append(f"{item_id}: 판례일련번호 없음")
                continue

            try:
                body = await _fetch_lsw_body(client, sem, str(prec_seq))
            except Exception as e:
                fail += 1
                if len(fail_samples) < 5:
                    fail_samples.append(f"{item_id} precSeq={prec_seq}: {e}")
                print(f"  [{i}/{total}] {item_id} precSeq={prec_seq} 에러: {e}")
                await asyncio.sleep(SLEEP_BETWEEN)
                continue

            if not body or len(body) < MIN_BODY_LEN:
                fail += 1
                if len(fail_samples) < 5:
                    case_no = (raw or {}).get("사건번호", "")
                    fail_samples.append(
                        f"{item_id} precSeq={prec_seq} 사건번호={case_no}: 본문 너무 짧음 "
                        f"(len={len(body) if body else 0})"
                    )
                await asyncio.sleep(SLEEP_BETWEEN)
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

            if i % 10 == 0 or i == total:
                print(f"  진행 {i}/{total} (성공 {success}, 실패 {fail})")
            await asyncio.sleep(SLEEP_BETWEEN)

    return total, success, fail, fail_samples


async def main() -> None:
    print(f"LAW_OC: {LAW_OC}")
    print(f"endpoint: {LSW_URL}")
    print(f"concurrency: {CONCURRENCY}, timeout: {TIMEOUT}s, min_body_len: {MIN_BODY_LEN}")
    print()

    print("=== 빈 body 판례 LSW HTML 보강 ===")
    total, ok, fail, samples = await refetch_empty_bodies()
    print()
    print("=== 결과 ===")
    print(f"  대상   : {total}")
    print(f"  성공   : {ok}")
    print(f"  실패   : {fail}")
    if total:
        print(f"  성공률 : {ok / total * 100:.1f}%")
    if samples:
        print("\n  실패 샘플:")
        for s in samples:
            print(f"    - {s}")

    # 최종 채움률
    import psycopg

    with psycopg.connect(POSTGRES_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM law_precedents")
            (full_total,) = cur.fetchone()
            cur.execute("SELECT COUNT(*) FROM law_precedents WHERE length(body_text) > 0")
            (full_ok,) = cur.fetchone()
    print(f"\n  전체 채움률: {full_ok}/{full_total} = {full_ok / full_total * 100:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
