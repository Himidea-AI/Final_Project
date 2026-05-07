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

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
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


def _to_float_list(value: Any, *, length: int) -> list[float]:
    if isinstance(value, list):
        values: list[float] = []
        for item in value[:length]:
            try:
                values.append(float(item))
            except (TypeError, ValueError):
                values.append(0.0)
        if len(values) < length:
            values.extend([values[-1] if values else 0.0] * (length - len(values)))
        return values

    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return [number] * length


def _normalize_elasticity(entry: dict[str, Any]) -> dict[str, dict[str, list[float]]]:
    """Return v3 list-valued elasticity while accepting older scalar caches."""
    quarter_count = len(entry.get("baseline") or []) or 4
    raw_elasticity = entry.get("elasticity") or {}
    normalized: dict[str, dict[str, list[float]]] = {}

    if not isinstance(raw_elasticity, dict):
        return normalized

    for slider_name, level_map in raw_elasticity.items():
        if not isinstance(level_map, dict):
            continue
        normalized[str(slider_name)] = {
            str(level): _to_float_list(value, length=quarter_count)
            for level, value in level_map.items()
        }

    return normalized


class SensitivityResponse(BaseModel):
    elasticity: dict[str, dict[str, list[float]]]
    correlations: dict[str, float]
    baseline_sales: list[float]
    # v3 + 점포당 매출 표시 전환 (2026-05-03):
    # store_count는 (동×업종) 조합의 최근 분기 점포 수, baseline_per_store는 분기별
    # 점포당 매출(원). 기존 캐시(이 필드들이 없는)와의 호환을 위해 Optional 유지.
    store_count: int | None = None
    baseline_per_store: list[float] | None = None


def _compute_etag() -> str:
    """캐시 파일 mtime+size 기반 ETag.

    캐시 파일이 동일하면 모든 (동×업종) 조합이 같은 ETag를 갖지만,
    브라우저 캐시 키는 URL(쿼리 포함)이므로 조합별로 독립 캐싱된다.
    캐시 파일이 갱신되면 ETag도 변경되어 304 미스가 발생한다.
    """
    if not _CACHE_PATH.exists():
        return '"no-cache"'
    stat = _CACHE_PATH.stat()
    raw = f"{stat.st_mtime_ns}-{stat.st_size}"
    return f'"{hashlib.md5(raw.encode()).hexdigest()[:16]}"'


@router.get("/sensitivity", response_model=SensitivityResponse)
def get_sensitivity(
    dong_code: str,
    industry_code: str,
    request: Request,
    response: Response,
) -> SensitivityResponse:
    """특정 (동×업종) 조합의 탄성치 테이블과 피처 상관계수를 반환한다.

    ETag/If-None-Match 기반 조건부 GET 지원: 클라이언트가 보낸 If-None-Match가
    현재 캐시 파일 ETag와 일치하면 304 Not Modified로 응답한다.
    """
    etag = _compute_etag()
    cache_headers = {"ETag": etag, "Cache-Control": "public, must-revalidate"}

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cache_headers)

    key = f"{dong_code}_{industry_code}"
    entry = _SENSITIVITY_CACHE.get(key)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"탄성치 데이터 없음: {key}. 배치 스크립트를 먼저 실행하세요.",
        )

    for header, value in cache_headers.items():
        response.headers[header] = value
    return SensitivityResponse(
        elasticity=_normalize_elasticity(entry),
        correlations=_CORRELATIONS,
        baseline_sales=entry["baseline"],
        store_count=entry.get("store_count"),
        baseline_per_store=entry.get("baseline_per_store"),
    )
