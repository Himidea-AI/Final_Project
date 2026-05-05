"""competitor_intel 실제 LLM 정확도 측정.

Redis 캐시(`v3:competitor_intel:*`) 의 실제 시뮬 결과를 fixture 로 변환 후
CompetitorIntelEvaluator 실행 → LLM market_entry_signal vs 룰엔진 정답 비교.

사용:
    cd backend
    python -m scripts.eval.run_competitor_intel_real

전제:
    - Redis 띄워져 있음 (settings.redis_url)
    - v3:competitor_intel:* 키에 시뮬 결과 캐시되어 있음 (≥1건)
"""

from __future__ import annotations

import asyncio
import io
import json
import sys

# Windows cp949 콘솔 → UTF-8 강제
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, "C:\\dev\\Final_project\\backend")  # noqa

import redis.asyncio as aioredis

from src.config.settings import settings
from src.evaluation.competitor_intel_eval import CompetitorIntelEvaluator


async def dump_redis_to_fixtures(pattern: str = "v3:competitor_intel:*") -> list[dict]:
    """Redis 에서 캐시된 시뮬 결과 → evaluator fixture 로 변환."""
    fixtures: list[dict] = []
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        keys = await r.keys(pattern)
        print(f"[dump] Redis 패턴 '{pattern}' → {len(keys)}개 키 발견")
        for key in keys:
            raw = await r.get(key)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception as e:
                print(f"  [skip] {key}: JSON parse 실패 — {e}")
                continue
            # fixture 변환 — case_id 는 dong:brand 조합
            # 키 형식: v3:competitor_intel:{dong_code}:{brand_name}
            parts = key.split(":", 3)
            case_id = ":".join(parts[2:]) if len(parts) >= 4 else key
            fixtures.append(
                {
                    "case_id": case_id,
                    "simulated_output": payload,
                }
            )
    finally:
        await r.aclose()
    return fixtures


async def main() -> None:
    fixtures = await dump_redis_to_fixtures()
    if not fixtures:
        print("⚠️  v3:competitor_intel:* 캐시 없음 — 시뮬 1회 이상 돌린 후 재실행.")
        return

    evaluator = CompetitorIntelEvaluator(fixtures=fixtures)
    summary = await evaluator.run()

    print("=" * 70)
    print(f"competitor_intel 실측 LLM 정확도 (Redis dump {len(fixtures)}건)")
    print("=" * 70)
    for line in summary.report_lines():
        print(line)
    print()
    print("케이스별 결과:")
    for r in summary.raw_results:
        mark = "✓" if r.passed else "✗"
        cn = r.details.get("cannibal_pct", 0)
        sat = r.details.get("saturation_level", "?")
        print(
            f"  {mark} {r.case_id}: "
            f"expected={r.expected:6} actual={r.actual:6} "
            f"(cannibal={cn * 100:.1f}% sat={sat})"
        )
    print()
    print("=" * 70)
    print(f"📊 실측 정확도: {summary.metric_mean:.1%} ({summary.n_passed}/{summary.n_cases})")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
