"""
MiniLM 파인튜닝용 Triplet Dataset 생성

소스: fail_cases.json (192건 오답 분석) + chunks.json (원본 조문)
출력: data/legal/processed/train_triplets.jsonl

1단계: fail_cases에서 (query, positive_chunk, hard_negative_chunk) 추출
2단계: LLM으로 정답 조문별 질문 5개 증강 (Self-Instruct)
3단계: JSONL 저장
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

FAIL_PATH = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "fail_cases.json"
CHUNKS_PATH = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "chunks.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "train_triplets.jsonl"


def find_chunk_text(chunks, source_kw, article, max_len=300):
    """청크에서 해당 조문 텍스트 추출"""
    for c in chunks:
        src = c.get("metadata", {}).get("source", "")
        art = re.sub(r"_\d+$", "", c.get("metadata", {}).get("article", ""))
        if source_kw in src and art == article:
            return c.get("text", c.get("content", ""))[:max_len]
    return ""


# 법률명 → source 키워드 매핑
LAW_TO_SOURCE = {
    "가맹사업법": "가맹사업거래",
    "상가임대차보호법": "상가건물 임대차보호법",
    "식품위생법": "식품위생법",
    "건축법": "건축법",
    "소방시설법": "소방시설 설치 및 관리",
    "근로기준법": "근로기준법",
    "부가가치세법": "부가가치세법",
    "개인정보보호법": "개인정보 보호법",
    "장애인편의법": "장애인",
    "하수도법": "하수도법",
    "공정거래법": "독점규제 및 공정거래",
}


async def main():
    with open(FAIL_PATH, encoding="utf-8") as f:
        fails = json.load(f)
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"[1] fail_cases: {len(fails)}건, chunks: {len(chunks)}개")

    # 1단계: 기본 트리플렛 추출
    triplets = []
    for case in fails:
        query = case["query"]
        law = case["law"]
        source_kw = LAW_TO_SOURCE.get(law, "")
        if not source_kw:
            continue

        # positive: 정답 조문 중 첫 번째
        for correct_art in case.get("correct_missed", []) + case.get("correct_found", []):
            pos_text = find_chunk_text(chunks, source_kw, correct_art)
            if not pos_text:
                continue

            # negative: 혼동 쌍에서 오답 조문
            for cp in case.get("confusion_pairs", []):
                neg_text = find_chunk_text(chunks, source_kw, cp["wrong"])
                if neg_text and neg_text != pos_text:
                    triplets.append({
                        "query": query,
                        "pos": pos_text,
                        "neg": neg_text,
                    })

            # top1이 오답이면 그것도 negative로
            if case.get("top1_wrong"):
                neg_art = case["top1_wrong"]["article"]
                neg_text = find_chunk_text(chunks, source_kw, neg_art)
                if neg_text and neg_text != pos_text:
                    triplets.append({
                        "query": query,
                        "pos": pos_text,
                        "neg": neg_text,
                    })

    # 중복 제거
    seen = set()
    unique_triplets = []
    for t in triplets:
        key = (t["query"], t["pos"][:50], t["neg"][:50])
        if key not in seen:
            seen.add(key)
            unique_triplets.append(t)

    print(f"[2] 기본 트리플렛: {len(unique_triplets)}개 (중복 제거 후)")

    # 2단계: LLM으로 질문 증강
    print("[3] 질문 증강 시작 (gpt-4o-mini)...")
    from openai import AsyncOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("  OPENAI_API_KEY 없음 - 증강 스킵")
        augmented = []
    else:
        client = AsyncOpenAI(api_key=api_key)

        # 고유 (law, article, pos_text) 쌍만 증강
        pos_texts_seen = set()
        augment_targets = []
        for t in unique_triplets:
            key = t["pos"][:80]
            if key not in pos_texts_seen:
                pos_texts_seen.add(key)
                augment_targets.append(t)

        print(f"  증강 대상: {len(augment_targets)}개 고유 조문")

        augmented = []
        BATCH = 15

        for batch_start in range(0, len(augment_targets), BATCH):
            batch = augment_targets[batch_start:batch_start + BATCH]

            async def gen_questions(t):
                try:
                    resp = await asyncio.wait_for(
                        client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[
                                {
                                    "role": "system",
                                    "content": "주어진 법조문을 찾기 위해 일반 창업자가 던질 법한 일상어 질문을 5개 생성하세요. 번호 없이 한 줄씩 출력.",
                                },
                                {"role": "user", "content": f"법조문:\n{t['pos']}"},
                            ],
                            max_tokens=300,
                            temperature=0.5,
                        ),
                        timeout=20.0,
                    )
                    questions = [
                        q.strip()
                        for q in resp.choices[0].message.content.strip().split("\n")
                        if q.strip() and len(q.strip()) > 5
                    ][:5]
                    return [(q, t["pos"], t["neg"]) for q in questions]
                except Exception:
                    return []

            tasks = [gen_questions(t) for t in batch]
            results = await asyncio.gather(*tasks)
            for result in results:
                for q, pos, neg in result:
                    augmented.append({"query": q, "pos": pos, "neg": neg})

            done = min(batch_start + BATCH, len(augment_targets))
            print(f"  {done}/{len(augment_targets)} ({done / len(augment_targets) * 100:.0f}%)")

    print(f"[4] 증강 트리플렛: {len(augmented)}개")

    # 합치기
    all_triplets = unique_triplets + augmented

    # 최종 중복 제거
    seen2 = set()
    final = []
    for t in all_triplets:
        key = (t["query"][:50], t["pos"][:30])
        if key not in seen2:
            seen2.add(key)
            final.append(t)

    # JSONL 저장
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for t in final:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    print(f"\n[5] 최종: {len(final)}개 트리플렛")
    print(f"    기본: {len(unique_triplets)}개")
    print(f"    증강: {len(augmented)}개")
    print(f"    저장: {OUTPUT_PATH}")

    # 샘플 3개
    print(f"\n[6] 샘플:")
    for t in final[:3]:
        print(f"  Q: {t['query'][:60]}")
        print(f"  +: {t['pos'][:60]}")
        print(f"  -: {t['neg'][:60]}")
        print()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
