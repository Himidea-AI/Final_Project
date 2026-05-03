"""Async job progress store — /predict + /analyze/llm 의 real-time 진행률 저장소.

설계 (abm_simulation_service.abm_jobs_cache 패턴 참조):
    - asyncio 단일 스레드 환경 가정 → asyncio.Lock 불필요, dict 직접 접근.
    - in-memory dict (TTL 1시간 cleanup 별도). 단일 프로세스/단일 워커 데모 환경.
    - 멀티 워커/스케일아웃 시 Redis 로 교체 필요 — 현재 아님.

저장 형식:
    job_progress_jobs[job_id] = {
        "kind":        "predict" | "analyze_llm",
        "status":      "running" | "done" | "error",
        "progress":    float (0.0 ~ 1.0),     # 진짜 노드/슬라이스 완료 비율
        "stage":       str (현재 진행 단계 라벨, optional),
        "data":        dict | list | None,    # done 시 채움 (sync endpoint 응답과 동일 schema)
        "error":       str | None,
        "started_at":  float (epoch),
        "finished_at": float | None,
    }
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Literal

logger = logging.getLogger(__name__)

JobKind = Literal["predict", "analyze_llm"]

# In-memory dict — asyncio 단일 스레드 가정. lock 없음.
job_progress_jobs: dict[str, dict[str, Any]] = {}

# TTL — 1시간 후 자동 정리 대상. 명시 cleanup 호출 시에만 제거됨.
_TTL_SECONDS = 3600


def create_job(kind: JobKind) -> str:
    """새 job_id 발급 + running 상태로 초기화. progress=0.0 부터 시작."""
    job_id = str(uuid.uuid4())
    job_progress_jobs[job_id] = {
        "kind": kind,
        "status": "running",
        "progress": 0.0,
        "stage": None,
        "data": None,
        "error": None,
        "started_at": time.time(),
        "finished_at": None,
    }
    logger.info(f"[job_progress] create kind={kind} id={job_id[:8]}")
    return job_id


def set_progress(job_id: str, progress: float, stage: str | None = None) -> None:
    """진행률 갱신. progress 는 0.0~1.0 클램프. stage 는 optional 단계 라벨.

    job 이 이미 done/error 면 무시 (race 방어 — late callback 이 완료 상태 덮어쓰기 방지).
    """
    job = job_progress_jobs.get(job_id)
    if job is None:
        return
    if job["status"] != "running":
        return
    job["progress"] = max(0.0, min(1.0, float(progress)))
    if stage is not None:
        job["stage"] = stage


def set_done(job_id: str, data: Any) -> None:
    """job 완료 — progress=1.0, status='done', data 채움."""
    job = job_progress_jobs.get(job_id)
    if job is None:
        return
    job["status"] = "done"
    job["progress"] = 1.0
    job["data"] = data
    job["finished_at"] = time.time()


def set_error(job_id: str, message: str) -> None:
    """job 실패 — status='error', error 채움. progress 는 마지막 값 유지."""
    job = job_progress_jobs.get(job_id)
    if job is None:
        return
    job["status"] = "error"
    job["error"] = message
    job["finished_at"] = time.time()


def get_job(job_id: str) -> dict[str, Any] | None:
    """job 조회 + 만료(TTL 초과) 시 cleanup 후 None 반환."""
    job = job_progress_jobs.get(job_id)
    if job is None:
        return None
    if time.time() - job["started_at"] > _TTL_SECONDS:
        job_progress_jobs.pop(job_id, None)
        return None
    return job


def serialize_status(job: dict[str, Any]) -> dict[str, Any]:
    """polling endpoint 응답용 dict — data 는 done 일 때만 포함."""
    payload: dict[str, Any] = {
        "status": job["status"],
        "progress": job["progress"],
        "stage": job["stage"],
        "elapsed_seconds": round((job["finished_at"] or time.time()) - job["started_at"], 2),
    }
    if job["status"] == "done":
        payload["data"] = job["data"]
    elif job["status"] == "error":
        payload["error"] = job["error"]
    return payload
