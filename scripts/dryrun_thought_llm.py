"""LLM thought 생성 dry-run — gpt-4.1-mini 50 sample 실측.

옵션 2 (자연어 thought) 도입 결정 전 sanity check:
    - 실제 input/output token 측정 → 비용 추정 정확도 검증
    - 출력 quality 검증 (template 대비 LLM 우위 여부)
    - latency 측정

실행:
    set -a && source .env && set +a
    python scripts/dryrun_thought_llm.py

비용: 약 $0.003 (50 call × 평균 90 token).
"""

from __future__ import annotations

import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# ---------------------------------------------------------------------------
# Prompt 설계 — brain.py 와 동기화 (production 과 동일 prompt 측정)
# ---------------------------------------------------------------------------
# brain.py 의 _THOUGHT_SYSTEM_PROMPT 를 그대로 사용
import sys as _sys

_sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from src.simulation.brain import _THOUGHT_SYSTEM_PROMPT as SYSTEM_PROMPT  # noqa: E402

# user prompt 템플릿 — brain.generate_thought 과 동일 (dong 포함, situation 제외)
USER_TEMPLATE = "archetype={archetype}, hour={hour}, weather={weather}, mood={mood}, hunger={hunger}, dong={dong}"

# brain.py 의 dialog_templates 8 archetype 일치
ARCHETYPES = [
    "creative_freelancer",
    "office_worker",
    "broadcasting_staff",
    "student_couple",
    "retired_local",
    "young_parent",
    "tourist_foreign",
    "f&b_owner",
]

# 마포 16동 — archetype-dong mismatch 테스트용
DONGS = [
    "공덕동",
    "도화동",
    "용강동",
    "대흥동",
    "염리동",
    "아현동",
    "신수동",
    "서교동",
    "합정동",
    "연남동",
    "망원1동",
    "망원2동",
    "성산1동",
    "성산2동",
    "상암동",
    "서강동",
]

WEATHERS = ["맑음", "비", "흐림", "약한비"]
MOODS = ["high", "neutral", "low"]


def build_samples(n: int = 50, seed: int = 42) -> list[dict]:
    """archetype × dong × hour × weather 격자에서 n 개 sample 추출."""
    rng = random.Random(seed)
    samples = []
    for _ in range(n):
        samples.append(
            {
                "archetype": rng.choice(ARCHETYPES),
                "hour": rng.randint(7, 23),
                "weather": rng.choice(WEATHERS),
                "mood": rng.choice(MOODS),
                "hunger": round(rng.random(), 2),
                "dong": rng.choice(DONGS),
            }
        )
    return samples


# ---------------------------------------------------------------------------
# OpenAI 호출
# ---------------------------------------------------------------------------
def call_openai(samples: list[dict], model: str = "gpt-4.1-mini") -> list[dict]:
    """각 sample 에 대해 LLM 호출 + token/latency 기록."""
    try:
        from openai import OpenAI
    except ImportError:
        raise SystemExit("openai 패키지 필요: pip install openai")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY 미설정 — .env 확인")

    client = OpenAI(api_key=api_key)
    results = []
    for i, s in enumerate(samples):
        user_msg = USER_TEMPLATE.format(**s)
        t0 = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=30,
                temperature=0.8,
            )
            elapsed = time.perf_counter() - t0
            usage = resp.usage
            text = resp.choices[0].message.content.strip()
            cached = getattr(usage, "prompt_tokens_details", None)
            cached_tokens = getattr(cached, "cached_tokens", 0) if cached else 0
            results.append(
                {
                    "i": i,
                    "input": s,
                    "output": text,
                    "input_tokens": usage.prompt_tokens,
                    "output_tokens": usage.completion_tokens,
                    "cached_tokens": cached_tokens,
                    "latency_s": round(elapsed, 3),
                }
            )
            print(
                f'[{i + 1:02d}] {s["archetype"]:22s} h={s["hour"]:02d} {s["weather"]:5s} {s["mood"]:8s} {s["dong"]:7s} → "{text}" ({usage.prompt_tokens}+{usage.completion_tokens}t, {elapsed:.2f}s)'
            )
        except Exception as e:
            print(f"[{i + 1:02d}] FAIL: {e}")
    return results


# ---------------------------------------------------------------------------
# 비용 추정 (gpt-4.1-mini 가격 기준 2026-04)
# ---------------------------------------------------------------------------
PRICE_INPUT_PER_M = 0.4  # $/M token (uncached)
PRICE_CACHED_INPUT_PER_M = 0.1  # $/M token (cached)
PRICE_OUTPUT_PER_M = 1.6  # $/M token


def report(results: list[dict]) -> None:
    if not results:
        print("결과 없음")
        return
    n = len(results)
    in_total = sum(r["input_tokens"] for r in results)
    out_total = sum(r["output_tokens"] for r in results)
    cached_total = sum(r["cached_tokens"] for r in results)
    uncached_in = in_total - cached_total
    lat_total = sum(r["latency_s"] for r in results)
    cost = (
        uncached_in / 1_000_000 * PRICE_INPUT_PER_M
        + cached_total / 1_000_000 * PRICE_CACHED_INPUT_PER_M
        + out_total / 1_000_000 * PRICE_OUTPUT_PER_M
    )

    avg_in = in_total / n
    avg_out = out_total / n
    avg_lat = lat_total / n

    # 5000 agents × 24h × 1day × 5% sampling = 6000 calls 추정
    SCALE = 6000 / n
    scaled_cost = cost * SCALE
    scaled_in = in_total * SCALE
    scaled_out = out_total * SCALE
    scaled_cached = cached_total * SCALE

    print()
    print("=" * 72)
    print(f"DRY-RUN 결과 ({n} samples)")
    print("=" * 72)
    print(f"input  token 평균: {avg_in:.1f}  (총 {in_total:,})")
    print(f"output token 평균: {avg_out:.1f}  (총 {out_total:,})")
    print(f"cached token 총: {cached_total:,} ({100 * cached_total / max(in_total, 1):.1f}% of input)")
    print(f"latency 평균: {avg_lat:.2f}s  (총 {lat_total:.1f}s)")
    print(f"실측 비용: ${cost:.4f}")
    print()
    print("※ 5000 agents × 24h × 5% sampling = 6,000 calls 시 추정:")
    print(f"  input  token: {scaled_in:,.0f}")
    print(f"  output token: {scaled_out:,.0f}")
    print(f"  cached token: {scaled_cached:,.0f}")
    print(f"  비용/시뮬: ${scaled_cost:.3f}")
    print(f"  직렬 latency: {avg_lat * 6000 / 60:.1f} 분 (parallel 50 batch: {avg_lat * 6000 / 50 / 60:.1f} 분)")
    print()


def main() -> None:
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    samples = build_samples(n=n, seed=42)
    results = call_openai(samples)
    report(results)
    # 다양성 측정 — unique 비율
    if results:
        outputs = [r["output"] for r in results]
        unique_n = len(set(outputs))
        print(f"  unique 비율: {unique_n}/{len(outputs)} ({100 * unique_n / len(outputs):.0f}%)")


if __name__ == "__main__":
    main()
