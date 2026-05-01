"""
법률 전문가 관점 AI 자동 마킹 — GPT-4o-mini로 is_legal_match 판정

판정 기준:
- "변호사/노무사가 상담 시 근거로 제시할 만한 조항이면 1"
- 본법+시행령 쌍, 준용 조항, 벌칙/과태료 조항도 1
- 질문과 다른 주제면 0

입력: docs/team/legal_review_pending_v1.csv
출력: docs/team/legal_review_completed_v1.csv
"""
import asyncio
import csv
import json
import os
import selectors
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

INPUT = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "legal_review_pending_v1.csv"
OUTPUT = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "legal_review_completed_v1.csv"

SYSTEM_PROMPT = """당신은 대한민국 프랜차이즈 창업 전문 변호사입니다.

사용자의 법률 질문과 검색된 법조문 후보를 보고, 이 조문이 질문에 대한 법적 근거로 적합한지 판정하세요.

판정 기준:
1. 질문이 묻는 법적 의무/금지/권리를 직접 규정하는 조문 → 1
2. 해당 의무의 시행령/시행규칙 조문 (구체적 기준/절차) → 1
3. 해당 위반에 대한 벌칙/과태료/시정명령 조문 → 1
4. "~를 준용한다"로 질문 주제에 연결되는 조문 → 1
5. 같은 법률이지만 질문과 다른 주제의 조문 → 0
6. 정의 규정(제2조 등)이 질문 주제의 핵심 개념을 정의하면 → 1, 아니면 → 0

반드시 JSON으로만 응답하세요:
{"match": 0 또는 1, "confidence": "high" 또는 "low", "reason": "판정 사유 (20자 이내)"}

confidence가 low면 확실하지 않다는 뜻입니다. 확실할 때만 high로 표시하세요."""


async def main():
    from openai import AsyncOpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("ERROR: OPENAI_API_KEY 없음")
        return
    client = AsyncOpenAI(api_key=api_key)

    with open(INPUT, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

    print(f"[1] 입력: {len(rows)}행")

    # 검수 대상만 필터
    pending = [(i, r) for i, r in enumerate(rows) if r.get("is_current_gt", "") != "1" and r.get("is_legal_match", "").strip() == ""]
    print(f"    검수 대상: {len(pending)}행")

    # 배치 처리
    BATCH = 20
    done = 0
    errors = 0

    for batch_start in range(0, len(pending), BATCH):
        batch = pending[batch_start:batch_start + BATCH]

        async def judge_one(idx, row):
            prompt = (
                f"질문: {row['user_query']}\n"
                f"현재 정답: {row['current_gt']}\n"
                f"검토 대상: {row['candidate_article']} - {row['candidate_title']}\n"
                f"조문 본문: {row['candidate_text'][:200]}"
            )
            try:
                resp = await asyncio.wait_for(
                    client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=80,
                        temperature=0,
                    ),
                    timeout=15.0,
                )
                content = resp.choices[0].message.content.strip()
                # JSON 파싱
                import re
                json_match = re.search(r'\{.*\}', content)
                if json_match:
                    result = json.loads(json_match.group())
                    confidence = result.get("confidence", "high")
                    match_val = str(result.get("match", 0))
                    reason = result.get("reason", "")
                    if confidence == "low":
                        return idx, "RECHECK", f"[LOW] {reason}"
                    return idx, match_val, reason
                return idx, "", "파싱 실패"
            except Exception as e:
                return idx, "", f"에러: {str(e)[:30]}"

        tasks = [judge_one(idx, row) for idx, row in batch]
        results = await asyncio.gather(*tasks)

        for idx, match, reason in results:
            rows[idx]["is_legal_match"] = match
            rows[idx]["legal_reason"] = reason
            if not match:
                errors += 1

        done += len(batch)

        # 중간 저장 (매 배치)
        with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        pct = done / len(pending) * 100
        print(f"    {done}/{len(pending)} ({pct:.0f}%)")

    # 통계
    marked_1 = sum(1 for r in rows if r.get("is_legal_match", "").strip() == "1")
    marked_0 = sum(1 for r in rows if r.get("is_legal_match", "").strip() == "0")
    recheck = sum(1 for r in rows if r.get("is_legal_match", "").strip() == "RECHECK")
    gt = sum(1 for r in rows if r.get("is_current_gt", "") == "1")

    print(f"\n[2] 완료:")
    print(f"    기존 정답: {gt}개")
    print(f"    AI 정답(1): {marked_1}개")
    print(f"    AI 무관(0): {marked_0}개")
    print(f"    RECHECK (사람 확인 필요): {recheck}개")
    print(f"    에러: {errors}개")
    print(f"    새 정답 총: {gt + marked_1}개")
    print(f"\n    저장: {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
