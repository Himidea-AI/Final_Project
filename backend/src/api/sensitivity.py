"""
GET /predict/sensitivity — TCN 시나리오 시뮬레이터 탄성치 API

사전 계산된 sensitivity_cache.json + feature_correlations.json을 로드하여
프론트엔드 슬라이더에 필요한 탄성치 테이블과 피처 상관계수를 반환한다.

환경변수 오버라이드:
    SENSITIVITY_CACHE_PATH: 캐시 JSON 경로 (기본: models/tcn_forecast/weights/sensitivity_cache.json)
    SENSITIVITY_CORR_PATH: 상관계수 JSON 경로 (기본: models/tcn_forecast/weights/feature_correlations.json)

담당: B2 — 수지니
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["sensitivity"])

_DEFAULT_CACHE = Path(__file__).resolve().parents[3] / "models" / "tcn_forecast" / "weights" / "sensitivity_cache.json"
_DEFAULT_CORR = (
    Path(__file__).resolve().parents[3] / "models" / "tcn_forecast" / "weights" / "feature_correlations.json"
)

_CACHE_PATH = Path(os.environ.get("SENSITIVITY_CACHE_PATH", str(_DEFAULT_CACHE)))
_CORR_PATH = Path(os.environ.get("SENSITIVITY_CORR_PATH", str(_DEFAULT_CORR)))


def _load_json(path: Path, *, label: str = "data") -> dict:
    if not path.exists():
        logger.warning(
            "Sensitivity router %s file not found: %s — returning empty dict. Did you run the batch script?",
            label,
            path,
        )
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        logger.error(
            "Failed to parse sensitivity router %s file %s: %s — returning empty dict",
            label,
            path,
            exc,
        )
        return {}


# 모듈 로드 시점에 캐시 읽기 (FastAPI startup과 동일 시점)
_SENSITIVITY_CACHE: dict[str, Any] = _load_json(_CACHE_PATH, label="sensitivity cache")
_CORRELATIONS: dict[str, float] = _load_json(_CORR_PATH, label="feature correlations")


class SensitivityResponse(BaseModel):
    elasticity: dict[str, dict[str, float]]
    correlations: dict[str, float]
    baseline_sales: list[float]


@router.get("/sensitivity", response_model=SensitivityResponse)
def get_sensitivity(dong_code: str, industry_code: str) -> SensitivityResponse:
    """특정 (동×업종) 조합의 탄성치 테이블과 피처 상관계수를 반환한다."""
    key = f"{dong_code}_{industry_code}"
    entry = _SENSITIVITY_CACHE.get(key)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"탄성치 데이터 없음: {key}. 배치 스크립트를 먼저 실행하세요.",
        )
    return SensitivityResponse(
        elasticity=entry["elasticity"],
        correlations=_CORRELATIONS,
        baseline_sales=entry["baseline"],
    )
