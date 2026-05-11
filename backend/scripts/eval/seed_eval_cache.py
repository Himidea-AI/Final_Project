"""v7 평가용 시뮬 batch — Redis 캐시(v2:population, v2:market 등)를 채우는 스크립트.

배경:
  population_node / market_analyst_node 가 v2 prefix 로 raw 데이터까지 캐시하도록
  변경됐지만, 기존 캐시는 v1 (raw 없음) 이라 평가 불가. 새 시뮬을 batch 호출해서
  v2 캐시를 채워야 함.

사용:
  cd backend
  python -m scripts.eval.seed_eval_cache

전제:
  - 백엔드가 떠있고 (http://localhost:8000)
  - 노드 코드 변경 후 재시작됨
  - DB / Redis 연결 정상
"""

from __future__ import annotations

import asyncio
import io
import sys
import time

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

BACKEND = "http://localhost:8000"

# 다양성 — 브랜드·동·업종 분포로 평가 fixture 풍부화.
# 1 케이스당 약 60~90초 (TCN+ML+LLM+SHAP 풀 파이프라인).
CASES: list[dict] = [
    {"target": "서교동", "brand": "메가엠지씨커피", "biz": "cafe"},
    {"target": "합정동", "brand": "이디야커피", "biz": "cafe"},
    {"target": "연남동", "brand": "빽다방", "biz": "cafe"},
    {"target": "망원1동", "brand": "스타벅스", "biz": "cafe"},
    {"target": "성산2동", "brand": "컴포즈커피", "biz": "cafe"},
    {"target": "공덕동", "brand": "빽다방", "biz": "cafe"},
    {"target": "아현동", "brand": "메가엠지씨커피", "biz": "cafe"},
    {"target": "도화동", "brand": "이디야커피", "biz": "cafe"},
]


def _build_payload(case: dict) -> dict:
    """SimulationInput 최소 페이로드 — 평가에 필요한 필드만."""
    return {
        "business_type": case["biz"],
        "brand_name": case["brand"],
        "target_district": case["target"],
        "target_districts": [case["target"]],
        "existing_stores": [],
        "monthly_rent": 2_000_000,
        "scenarios": [],
        "store_area": 15.0,
        "target_price_range": "5to10k",
        "operating_hours": ["점심", "저녁"],
        "initial_capital": 50_000_000,
        "population_weight": True,
        "commercial_radius": 500,
    }


async def _wait_done(client: httpx.AsyncClient, status_url: str, timeout_s: float = 240) -> dict:
    """job status 폴링 — done 또는 timeout 까지."""
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            r = await client.get(status_url, timeout=10)
            data = r.json()
            status = (data.get("status") or "").lower()
            progress = data.get("progress", 0) or 0
            stage = data.get("stage", "")
            if status in {"done", "success", "completed"}:
                return {"ok": True, "elapsed": time.time() - start, "stage": stage}
            if status == "error":
                return {"ok": False, "elapsed": time.time() - start, "error": data.get("error", "")}
            print(f"    progress={progress:.0%} stage={stage}", end="\r", flush=True)
        except Exception as e:
            print(f"    polling error: {e}", end="\r")
        await asyncio.sleep(3)
    return {"ok": False, "elapsed": timeout_s, "error": "timeout"}


async def run_one(client: httpx.AsyncClient, case: dict, idx: int, total: int) -> dict:
    payload = _build_payload(case)
    case_id = f"{case['target']}/{case['brand']}/{case['biz']}"
    print(f"\n[{idx + 1}/{total}] {case_id}")

    # /predict/async + /analyze/llm/async 동시 호출 (서버는 두 큐 따로 관리)
    try:
        pred_resp = await client.post(f"{BACKEND}/predict/async", json=payload, timeout=30)
        pred_job = pred_resp.json().get("job_id")
        ana_resp = await client.post(f"{BACKEND}/analyze/llm/async", json=payload, timeout=30)
        ana_job = ana_resp.json().get("job_id")
    except Exception as e:
        return {"case": case_id, "ok": False, "error": f"start: {e}"}

    if not pred_job or not ana_job:
        return {"case": case_id, "ok": False, "error": "no job_id"}

    print(f"    predict={pred_job[:8]} analyze={ana_job[:8]} — 대기…")

    pred_res, ana_res = await asyncio.gather(
        _wait_done(client, f"{BACKEND}/predict/{pred_job}/status"),
        _wait_done(client, f"{BACKEND}/analyze/llm/{ana_job}/status"),
    )
    print(f"    ✓ predict({pred_res['elapsed']:.0f}s) analyze({ana_res['elapsed']:.0f}s)")
    return {
        "case": case_id,
        "ok": pred_res["ok"] and ana_res["ok"],
        "predict": pred_res,
        "analyze": ana_res,
    }


async def main() -> None:
    print("=" * 78)
    print(f"v7 평가용 시뮬 batch — {len(CASES)} 케이스")
    print("=" * 78)

    # 백엔드 헬스체크
    async with httpx.AsyncClient() as client:
        try:
            h = await client.get(f"{BACKEND}/health", timeout=5)
            if h.status_code != 200:
                print(f"❌ 백엔드 health 응답 비정상: {h.status_code}")
                return
        except Exception as e:
            print(f"❌ 백엔드 연결 실패: {e}\n   uvicorn 띄우고 다시 시도하세요.")
            return

        print("✓ 백엔드 정상")
        results = []
        t0 = time.time()
        for idx, case in enumerate(CASES):
            res = await run_one(client, case, idx, len(CASES))
            results.append(res)

    elapsed = time.time() - t0
    n_ok = sum(1 for r in results if r.get("ok"))
    print()
    print("=" * 78)
    print(f"완료 — {n_ok}/{len(CASES)} 성공 ({elapsed:.0f}s 소요)")
    print("=" * 78)
    for r in results:
        mark = "✓" if r.get("ok") else "✗"
        err = "" if r.get("ok") else f" — {r.get('error', '')}"
        print(f"  {mark} {r['case']}{err}")
    print()
    print("다음 단계: python -m scripts.eval.run_all_agents_v7 로 v7 재측정")


if __name__ == "__main__":
    asyncio.run(main())
