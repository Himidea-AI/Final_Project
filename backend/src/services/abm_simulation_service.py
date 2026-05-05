"""ABM 시뮬레이션 비동기 실행 서비스.

목적:
    /simulate-abm 엔드포인트에서 시뮬이 180~300s 걸려 nginx 300s 또는
    클라이언트 abort 로 끊기면 ThreadPool 작업은 계속 진행되는데 사용자에게는
    "실패" 로 표시되는 자원 낭비/UX 문제 해결.

설계 (vacancy_evaluation_service.run_vacancy_pse_async 동일 패턴):
    - in-memory dict cache (TTL 1시간)
    - threading.Thread daemon 으로 백그라운드 시뮬
    - 클라이언트 disconnect 해도 시뮬 끝까지 진행, 결과 cache 에 보존
    - GET /simulate-abm/{job_id}/status, /result 로 polling 조회

저장 형식:
    abm_jobs_cache[job_id] = {
        "status": "running" | "done" | "failed",
        "started_at": float (epoch),
        "result": dict | None,    # /simulate-abm 동기 응답과 동일 schema
        "error": str | None,
        "progress": str | None,   # 선택적 진행 단계
        "cache_key": str | None,  # Redis 캐시 SETEX 시 사용
    }
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# In-memory cache (TTL 1시간) — vacancy_pse_cache 와 별도 dict (이름 충돌 방지)
abm_jobs_cache: dict[str, dict[str, Any]] = {}
_cache_lock = threading.Lock()


def _set_progress(job_id: str, progress: str) -> None:
    """진행 단계 갱신 (lock 안전)."""
    with _cache_lock:
        if job_id in abm_jobs_cache:
            abm_jobs_cache[job_id]["progress"] = progress


def _build_response(
    *,
    result: dict[str, Any],
    target_district: str,
    n_agents: int,
    weather_override: str | None,
    weekend_force: bool,
    rent_shock_pct: float,
    date_override: str | None,
    langgraph_result: dict[str, Any],
) -> dict[str, Any]:
    """abm_run() 결과 → /simulate-abm 응답 dict (동기/비동기 공유 후처리).

    main.py:1750~1817 의 후처리 로직과 1:1 동일. 동기 경로도 이 함수를 호출하면
    중복 제거 가능 (현재는 비동기 경로 only — 동기 경로는 backward compat 위해 유지).
    """
    # 동별 집계에서 target_district 만 추출
    dong_totals = result.get("dong_totals") or {}
    target_dong_stats = dong_totals.get(target_district, {})
    target_visits = int(target_dong_stats.get("visits", 0))
    target_revenue = float(target_dong_stats.get("revenue", 0))

    # fallback — target_district 매장이 없으면 전체 평균
    if target_visits == 0 and dong_totals:
        all_visits = sum(d.get("visits", 0) for d in dong_totals.values())
        all_revenue = sum(d.get("revenue", 0) for d in dong_totals.values())
        target_visits = int(all_visits / max(len(dong_totals), 1))
        target_revenue = all_revenue / max(len(dong_totals), 1)

    target_narrator = (
        f"{target_district} 상권 기준 일 방문 {target_visits:,}회, "
        f"일 매출 약 {int(target_revenue):,}원. "
        f"시나리오: {weather_override or '현재날씨'} · "
        f"{'주말' if weekend_force else '평일'} · "
        f"임대료 +{int(rent_shock_pct * 100)}%."
    )

    return {
        "status": "ok",
        "target_district": target_district,
        "n_personas": n_agents,
        "scenario_applied": {
            "weather": weather_override or "현재날씨",
            "weekend": weekend_force,
            "rent_shock_pct": rent_shock_pct,
            "date": date_override or "오늘",
        },
        "daily_visits_mean": target_visits,
        "daily_visits_std": result.get("daily_visits_std", 0),
        "daily_revenue_mean": target_revenue,
        "daily_revenue_std": result.get("daily_revenue_std", 0),
        "monthly_revenue_estimate": round(target_revenue * 25),
        "total_daily_visits": result.get("daily_visits", 0),
        "total_daily_revenue": result.get("daily_revenue", 0),
        "peak_hours": result.get("peak_hours", []),
        "customer_profile_dist": result.get("customer_profile_dist", {}),
        "dong_totals": dong_totals,
        "cannibalization": result.get("cannibalization", {}),
        "narrator_summary": target_narrator,
        "trajectory": result.get("trajectory"),
        "density_grid": result.get("density_grid"),
        "new_store_visits": result.get("new_store_visits", 0),
        "new_store_revenue": result.get("new_store_revenue", 0.0),
        "new_store_visit_share_pct": result.get("new_store_visit_share_pct", 0.0),
        "new_store_role_dist": result.get("new_store_role_dist", {}),
        "thoughts": result.get("thoughts", []),
        "thought_calls": result.get("thought_calls", 0),
        "thought_input_tokens": result.get("thought_input_tokens", 0),
        "thought_output_tokens": result.get("thought_output_tokens", 0),
        "thought_cached_tokens": result.get("thought_cached_tokens", 0),
        "tier_s_meta": result.get("tier_s_meta"),
        "tier_s_calls": result.get("tier_s_calls", 0),
        "tier_a_calls": result.get("tier_a_calls", 0),
        "estimated_cost_usd": result.get("estimated_cost_usd", 0.0),
        "cached": False,
        "langgraph_result": langgraph_result,
    }


def run_abm_async(
    *,
    pop: Any,
    tier: Any,
    cfg: Any,
    scenario: Any,
    days: int,
    enable_llm_thought: bool,
    collect_trajectory: bool,
    seed_memory: bool,
    use_llm_decisions: bool,
    llm_concurrency: int,
    target_district: str,
    n_agents: int,
    weather_override: str | None,
    weekend_force: bool,
    rent_shock_pct: float,
    date_override: str | None,
    langgraph_result: dict[str, Any],
    cache_key: str | None = None,
    redis_url: str | None = None,
) -> str:
    """ABM 시뮬을 백그라운드 thread 에서 실행 — job_id 즉시 반환.

    Args:
        pop, tier, cfg, scenario, days, enable_llm_thought, collect_trajectory,
        seed_memory, use_llm_decisions, llm_concurrency: simulation.runner.run_simulation
            에 그대로 전달되는 인자.
        target_district, n_agents, weather_override, weekend_force, rent_shock_pct,
        date_override, langgraph_result: _build_response() 가 응답 dict 를 조립할 때
            사용. main.py 동기 경로의 후처리와 1:1 동일.
        cache_key, redis_url: 시뮬 완료 후 결과를 Redis SETEX 1h 로 저장 (선택).
            None 이면 Redis 저장 건너뜀.

    Returns:
        uuid4 형식의 job_id. /simulate-abm/{job_id}/status, /result 로 polling.
    """
    job_id = str(uuid.uuid4())
    with _cache_lock:
        abm_jobs_cache[job_id] = {
            "status": "running",
            "started_at": time.time(),
            "result": None,
            "error": None,
            "progress": "queued",
            "cache_key": cache_key,
        }

    def _run() -> None:
        try:
            # 지연 import — 모듈 순환 방지
            from src.simulation.runner import run_simulation as abm_run

            _set_progress(job_id, "running_simulation")
            result = abm_run(
                pop=pop,
                tier=tier,
                cfg=cfg,
                use_rds=True,
                use_profiles=True,
                scenario=scenario,
                days=days,
                enable_llm_thought=enable_llm_thought,
                collect_trajectory=collect_trajectory,
                seed_memory=seed_memory,
                use_llm_decisions=use_llm_decisions,
                llm_concurrency=llm_concurrency,
            )

            _set_progress(job_id, "building_response")
            response = _build_response(
                result=result,
                target_district=target_district,
                n_agents=n_agents,
                weather_override=weather_override,
                weekend_force=weekend_force,
                rent_shock_pct=rent_shock_pct,
                date_override=date_override,
                langgraph_result=langgraph_result,
            )

            with _cache_lock:
                abm_jobs_cache[job_id]["status"] = "done"
                abm_jobs_cache[job_id]["result"] = response
                abm_jobs_cache[job_id]["progress"] = "done"

            # Redis SETEX 1h — 같은 입력 재요청 시 동기/비동기 모두 즉시 반환
            if cache_key and redis_url:
                _save_to_redis(cache_key=cache_key, redis_url=redis_url, response=response)

            logger.info(f"[ABM async] job_id={job_id} done")
        except Exception as e:
            logger.exception(f"[ABM async] simulation failed: job_id={job_id}")
            with _cache_lock:
                abm_jobs_cache[job_id]["status"] = "failed"
                abm_jobs_cache[job_id]["error"] = str(e)
                abm_jobs_cache[job_id]["progress"] = "failed"

    threading.Thread(target=_run, daemon=True, name=f"abm-sim-{job_id[:8]}").start()
    return job_id


def _save_to_redis(*, cache_key: str, redis_url: str, response: dict[str, Any]) -> None:
    """동기 redis client 로 SETEX 1h. trajectory 는 무거우니 캐시 제외 (main.py 동기 경로와 동일)."""
    try:
        import json as _json

        import redis as _redis_sync

        cache_body = {k: v for k, v in response.items() if k != "trajectory"}
        # daemon thread 안이라 sync redis 가 안전 (asyncio loop 부재)
        client = _redis_sync.from_url(redis_url, decode_responses=True)
        try:
            # TTL 1h → 24h (2026-05-04 사용자 피드백) — main.py 와 동기.
            client.setex(cache_key, 86400, _json.dumps(cache_body, ensure_ascii=False))
            logger.info(f"[ABM async] redis SET key={cache_key[:16]}... ttl=86400s")
        finally:
            client.close()
    except Exception as e:
        logger.warning(f"[ABM async] redis 저장 실패(무시): {e}")


def get_job(job_id: str) -> dict[str, Any] | None:
    """job_id 로 cache entry 조회 (lock 안전 복사본)."""
    with _cache_lock:
        job = abm_jobs_cache.get(job_id)
        if job is None:
            return None
        # 얕은 복사 — result 는 딕셔너리이지만 호출자가 그대로 반환만 함
        return dict(job)


def cleanup_old_jobs(ttl_seconds: int = 3600) -> int:
    """TTL 초과 job 제거. status/result endpoint 진입 시 가볍게 호출 권장.

    Returns:
        제거된 job 수.
    """
    now = time.time()
    with _cache_lock:
        expired = [k for k, v in abm_jobs_cache.items() if now - v["started_at"] > ttl_seconds]
        for k in expired:
            del abm_jobs_cache[k]
    if expired:
        logger.info(f"[ABM async] cleanup expired jobs: {len(expired)}")
    return len(expired)
