"""Vacancy 평가 REST API.

엔드포인트:
- POST /vacancy-evaluation/single  — 단일 vacancy 평가 (PSE N=5)
- POST /vacancy-evaluation/batch   — 여러 vacancy 평가 + 순위
- GET  /vacancy-evaluation/health  — 모듈 ping

설계:
- ABM 시뮬은 5~10분 (PSE N=5, with_cannibalization=False) 또는 10~20분 (True)
- HTTP timeout 위험 — 클라이언트는 timeout >= 600s 권장
- 향후 비동기 큐 (RQ/Celery) 로 분리 고려
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vacancy-evaluation", tags=["vacancy-evaluation"])

ALLOWED_CATEGORIES = ("음식점", "카페", "주점", "편의점", "기타")


class VacancySpotIn(BaseModel):
    """단일 공실 입력 — district_ranking 또는 사용자 좌표."""

    dong: str = Field(..., description="마포 행정동명 (예: 서교동)")
    lat: float = Field(..., ge=37.5, le=37.6, description="위도")
    lon: float = Field(..., ge=126.85, le=126.97, description="경도")
    id: Optional[int] = Field(None, description="네이버 부동산 매물 id (선택)")
    listing_count: Optional[int] = Field(None, description="해당 좌표 매물 수")


class VacancyEvaluateRequest(BaseModel):
    """단일 평가 요청."""

    spot: VacancySpotIn
    category: str = Field(..., description=f"업종 — {ALLOWED_CATEGORIES} 중 1")
    n_seeds: int = Field(5, ge=1, le=20, description="PSE N (기본 5, 권장 ≥ 3)")
    days: int = Field(1, ge=1, le=7, description="시뮬 일수")
    with_cannibalization: bool = Field(False, description="카니발 측정 (시간 2배)")
    popularity_boost: Optional[float] = Field(
        None, ge=0.5, le=20.0, description="신규 매장 인지도 (생략 시 default 5.0)"
    )
    collect_trajectory: bool = Field(False, description="agent 시간대별 위치 수집 (시각화)")
    dump_visits: bool = Field(False, description="visits_events list 출력 (시각화)")
    async_mode: bool = Field(False, description="True 시 즉시 job_id 반환, 시뮬은 background")
    agents: int = Field(5000, ge=100, le=10000, description="에이전트 수 (plan #2 default 5000)")

    @field_validator("category")
    @classmethod
    def _check_category(cls, v: str) -> str:
        if v not in ALLOWED_CATEGORIES:
            raise ValueError(f"category must be one of {ALLOWED_CATEGORIES}")
        return v


class VacancyBatchRequest(BaseModel):
    """배치 평가 요청 — 여러 vacancy 동시 평가 + 순위."""

    spots: list[VacancySpotIn] = Field(..., min_length=1, max_length=10)
    category: str
    top_n: int = Field(5, ge=1, le=10, description="상위 N 개만 평가")
    n_seeds: int = Field(5, ge=1, le=20)
    days: int = Field(1, ge=1, le=7)
    with_cannibalization: bool = Field(False)
    popularity_boost: Optional[float] = Field(None, ge=0.5, le=20.0)

    @field_validator("category")
    @classmethod
    def _check_category(cls, v: str) -> str:
        if v not in ALLOWED_CATEGORIES:
            raise ValueError(f"category must be one of {ALLOWED_CATEGORIES}")
        return v


@router.get("/health")
def health() -> dict[str, Any]:
    """모듈 가용성 체크 (ABM 모듈 import 가능 여부)."""
    try:
        from src.simulation.vacancy_pse import evaluate_vacancy_pse  # noqa: F401
        from src.services.vacancy_evaluation_service import evaluate_top_vacancies  # noqa: F401

        return {"status": "ok", "modules": ["vacancy_pse", "vacancy_evaluation_service"]}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _mock_cfg():
    """API 호출 시 mock LLM 강제 — 비용 안정 + LLM 키 의존성 제거."""
    from src.simulation.config import ModelConfig

    cfg = ModelConfig()
    cfg.tier_s_provider = "mock"
    cfg.tier_a_provider = "mock"
    return cfg


@router.post("/single")
def evaluate_single(body: VacancyEvaluateRequest) -> dict[str, Any]:
    """단일 vacancy PSE 평가.

    응답 시간:
    - n_seeds=5, with_cannibalization=False: 약 5분
    - n_seeds=5, with_cannibalization=True:  약 10분
    - 클라이언트 timeout >= 600s 권장.

    LLM provider 는 mock 강제 (비용 0, 안정적). 진짜 LLM 평가는 별도 엔드포인트 권장.
    """
    from src.simulation.vacancy_inject import DEFAULT_POPULARITY_BOOST
    from src.simulation.vacancy_pse import evaluate_vacancy_pse

    # async_mode=True 시 즉시 job_id 반환 (시뮬은 background)
    if body.async_mode:
        from src.services.vacancy_evaluation_service import run_vacancy_pse_async

        job_id = run_vacancy_pse_async(
            spot=body.spot.model_dump(),
            category=body.category,
            n_seeds=body.n_seeds,
            days=body.days,
            with_cannibalization=body.with_cannibalization,
            popularity_boost=body.popularity_boost if body.popularity_boost is not None else 20.0,  # plan #2 default
            agents=body.agents,
            collect_trajectory=body.collect_trajectory,
            dump_visits=body.dump_visits,
        )
        return {"job_id": job_id, "status": "running"}

    pb = body.popularity_boost if body.popularity_boost is not None else DEFAULT_POPULARITY_BOOST

    try:
        result = evaluate_vacancy_pse(
            vacancy_spot={"dong": body.spot.dong, "lat": body.spot.lat, "lon": body.spot.lon},
            category=body.category,
            n_seeds=body.n_seeds,
            days=body.days,
            with_cannibalization=body.with_cannibalization,
            popularity_boost=pb,
            cfg=_mock_cfg(),
            verbose=False,
            collect_trajectory=body.collect_trajectory,
            dump_visits=body.dump_visits,
        )
    except Exception as e:
        logger.exception(f"vacancy evaluation 실패: {e}")
        raise HTTPException(status_code=500, detail=f"evaluation failed: {e}")

    return {
        "spot": body.spot.model_dump(),
        "category": body.category,
        "n_seeds": body.n_seeds,
        "with_cannibalization": body.with_cannibalization,
        "narrative": result["narrative"],
        "pse_summary": result["pse_summary"],
        "per_seed": result["per_seed"],
    }


@router.post("/batch")
def evaluate_batch(body: VacancyBatchRequest) -> dict[str, Any]:
    """여러 vacancy 평가 + visits 내림차순 순위.

    응답 시간:
    - spots × n_seeds × (1 또는 2) × ~55s
    - 예: 5 spots × 5 seeds × 2 (cannibal) = 50 sims = ~46분 ⚠️
    - 권장: spots ≤ 3, n_seeds ≤ 5, with_cannibalization=False (~14분)
    """
    from src.services.vacancy_evaluation_service import evaluate_top_vacancies, format_rankings_text

    spots_dict = [s.model_dump() for s in body.spots]
    try:
        rankings = evaluate_top_vacancies(
            vacancy_spots=spots_dict,
            category=body.category,
            top_n=body.top_n,
            n_seeds=body.n_seeds,
            days=body.days,
            with_cannibalization=body.with_cannibalization,
            popularity_boost=body.popularity_boost,
            verbose=False,
        )
    except Exception as e:
        logger.exception(f"batch vacancy evaluation 실패: {e}")
        raise HTTPException(status_code=500, detail=f"batch evaluation failed: {e}")

    return {
        "category": body.category,
        "n_spots_evaluated": len(rankings),
        "n_spots_requested": len(body.spots),
        "rankings": rankings,
        "summary_text": format_rankings_text(rankings),
    }


# ---------------------------------------------------------------------------
# 비동기 시각화 endpoint (Plan #3 Task 2)
# ---------------------------------------------------------------------------


def _get_cache():
    """vacancy_pse_cache 지연 import — 모듈 순환 방지."""
    from src.services.vacancy_evaluation_service import vacancy_pse_cache

    return vacancy_pse_cache


@router.get("/{job_id}/status")
def get_job_status(job_id: str) -> dict:
    """Job 상태 조회 — running / done / failed."""
    import time as _time

    cache = _get_cache()
    job = cache.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    return {
        "job_id": job_id,
        "status": job["status"],
        "elapsed_seconds": int(_time.time() - job["started_at"]),
        "error": job.get("error"),
    }


def _require_done_job(job_id: str) -> dict:
    cache = _get_cache()
    job = cache.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    if job["status"] == "running":
        raise HTTPException(status_code=409, detail="job still running")
    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=job.get("error", "unknown error"))
    return job["result"]


@router.get("/{job_id}/trajectory")
def get_job_trajectory(job_id: str) -> dict:
    """trajectory list — agent 시간대별 위치 (collect_trajectory=True 시만)."""
    result = _require_done_job(job_id)
    return {
        "job_id": job_id,
        "status": "done",
        "trajectory": result.get("trajectory") or [],
        "n_agents": result.get("pse_summary", {}).get("visits_per_day", {}).get("n", 0),
    }


@router.get("/{job_id}/visits")
def get_job_visits(job_id: str) -> dict:
    """visits_events list — vacancy 매장 방문 (dump_visits=True 시만)."""
    result = _require_done_job(job_id)
    return {
        "job_id": job_id,
        "visits_events": result.get("visits_events") or [],
        "vacancy_id": result.get("vacancy_spot", {}).get("dong"),
    }


@router.get("/{job_id}/stores")
def get_job_stores(job_id: str) -> dict:
    """vacancy + 주변 매장 좌표 + 매출 (per_seed 의 매장 정보)."""
    result = _require_done_job(job_id)
    return {
        "job_id": job_id,
        "vacancy_spot": result.get("vacancy_spot", {}),
        "stores": result.get("stores_info", []),  # vacancy_pse 의 결과 stores 정보
    }


@router.get("/{job_id}/chats")
def get_job_chats(job_id: str) -> dict:
    """archetype 별 자연어 대화 (Mode B template — visits_events 의 dialog 필드)."""
    result = _require_done_job(job_id)
    chats = []
    for ev in result.get("visits_events") or []:
        if "dialog" in ev:
            chats.append(
                {
                    "agent_id": ev["agent_id"],
                    "hour": ev["hour"],
                    "text": ev["dialog"],
                }
            )
    return {
        "job_id": job_id,
        "chats": chats,
    }
