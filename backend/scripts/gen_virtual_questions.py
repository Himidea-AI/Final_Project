"""
Multi-Vector Q2Q — 법률 청크별 예상 질문 생성 + 저장

조문당 대표 청크 1개에 대해 gpt-4o-mini로 예상 질문 3개 생성.
결과: data/legal/processed/virtual_questions.json
구조: [{chunk_idx, source, article, questions: [q1, q2, q3]}, ...]
"""
import asyncio
import json
import os
import re
import selectors
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

CHUNKS_PATH = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "chunks.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "virtual_questions.json"

SYSTEM_PROMPT = """당신은 프랜차이즈 창업 법률 상담 전문가입니다.
주어진 법조문을 읽고, 이 조문을 찾기 위해 일반 창업자가 던질 법한 일상어 질문을 정확히 3개 생성하세요.

규칙:
- 법률 용어가 아닌 일상어/구어체로 작성
- 각 질문은 서로 다른 관점 (의무/벌칙/절차 등)
- 한 줄에 하나씩, 번호 없이 출력
- 질문만 출력 (설명 금지)"""


async def main():
    from openai import AsyncOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("ERROR: OPENAI_API_KEY 없음")
        return
    client = AsyncOpenAI(api_key=api_key)

    # 청크 로드
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)

    # 조문별 대표 청크 추출
    article_map = {}
    for i, c in enumerate(chunks):
        art = c.get("metadata", {}).get("article", "")
        if not art or art in ("전문", "미분류", "N/A"):
            continue
        src = c.get("metadata", {}).get("source", "")
        base = re.sub(r"_\d+$", "", art)
        key = (src, base)
        text = c.get("text", c.get("content", ""))
        if key not in article_map or len(text) > len(article_map[key]["text"]):
            article_map[key] = {"idx": i, "text": text, "source": src, "article": base}

    print(f"[1] 대상 조문: {len(article_map)}개")

    # 기존 결과 로드 (중간 저장 복원)
    existing = {}
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            for item in json.load(f):
                existing[(item["source"], item["article"])] = item
        print(f"    기존 결과 로드: {len(existing)}개")

    # 생성
    results = list(existing.values())
    remaining = [(k, v) for k, v in article_map.items() if k not in existing]
    print(f"    남은 생성: {len(remaining)}개")

    BATCH_SIZE = 20  # 동시 호출 수
    total_done = len(existing)
    t_start = time.perf_counter()

    for batch_start in range(0, len(remaining), BATCH_SIZE):
        batch = remaining[batch_start : batch_start + BATCH_SIZE]

        async def gen_one(key, info):
            try:
                resp = await asyncio.wait_for(
                    client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": f"법조문:\n{info['text'][:500]}"},
                        ],
                        max_tokens=200,
                        temperature=0.3,
                    ),
                    timeout=30.0,
                )
                questions = [
                    q.strip()
                    for q in resp.choices[0].message.content.strip().split("\n")
                    if q.strip() and len(q.strip()) > 5
                ][:3]
                return {
                    "chunk_idx": info["idx"],
                    "source": info["source"],
                    "article": info["article"],
                    "questions": questions,
                }
            except Exception as e:
                return {
                    "chunk_idx": info["idx"],
                    "source": info["source"],
                    "article": info["article"],
                    "questions": [],
                    "error": str(e)[:80],
                }

        tasks = [gen_one(k, v) for k, v in batch]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)
        total_done += len(batch)

        # 중간 저장 (매 배치)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        elapsed = time.perf_counter() - t_start
        rate = total_done / elapsed if elapsed > 0 else 0
        eta = (len(article_map) - total_done) / rate if rate > 0 else 0
        print(f"    {total_done}/{len(article_map)} ({total_done/len(article_map)*100:.0f}%) | {rate:.1f}/s | ETA {eta:.0f}s")

    # 최종 통계
    total_q = sum(len(r.get("questions", [])) for r in results)
    errors = sum(1 for r in results if r.get("error"))
    print(f"\n[2] 완료: {len(results)}개 조문, {total_q}개 질문, {errors}개 에러")
    print(f"    저장: {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
