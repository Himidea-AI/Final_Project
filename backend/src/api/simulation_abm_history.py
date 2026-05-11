"""simulation_abm REST API — ABM 시뮬 결과 (5K agent 행동) 저장/조회/삭제.

엔드포인트:
- POST   /history/abm       — 신규 저장
- GET    /history/abm       — 목록 조회
- GET    /history/abm/{id}  — 상세 조회
- DELETE /history/abm/{id}  — 삭제

권한:
- master(팀장): 본인 + 소속 매니저 이력 조회/삭제 가능.
- manager: 본인 이력만 R/W.

본 라우터는 simulation_foresee / simulation_ai 패턴을 따른다. 차이점:
- result JSONB 한 컬럼에 /simulate-abm/{job_id}/result 응답을 그대로 저장.
- scenario 컬럼은 ABM 전용 (weather_override / weekend_force / rent_shock_pct /
  date_override / store_area).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from src.services import simulation_abm_history_service as svc
from src.services.jwt_auth import UserContext, get_current_user

router = APIRouter(prefix="/history/abm", tags=["simulation-abm-history"])


def _to_uuid(raw: str) -> UUID:
    try:
        return UUID(raw)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail=f"Invalid user id: {exc}") from exc


class AbmSaveRequest(BaseModel):
    """ABM 시뮬 저장 요청 — result 는 /simulate-abm/{job_id}/result 응답 그대로."""

    client_name: str
    brand_name: str
    business_type: str | None = None
    target_district: str | None = None
    spot_lat: float | None = None
    spot_lon: float | None = None
    n_agents: int | None = None
    days: int | None = None
    scenario: dict[str, Any] | None = None
    result: dict[str, Any]


@router.post("", status_code=status.HTTP_201_CREATED)
def save_abm(
    body: AbmSaveRequest,
    user: UserContext = Depends(get_current_user),
):
    manager_uuid = _to_uuid(user.user_id)
    created = svc.create_abm(
        manager_id=manager_uuid,
        user_type=user.role,
        client_name=body.client_name.strip(),
        brand_name=body.brand_name,
        business_type=body.business_type,
        target_district=body.target_district,
        spot_lat=body.spot_lat,
        spot_lon=body.spot_lon,
        n_agents=body.n_agents,
        days=body.days,
        scenario=body.scenario,
        result=body.result,
    )
    return created


@router.get("")
def list_abm(
    client_name: Optional[str] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="created_at_desc"),
    user: UserContext = Depends(get_current_user),
):
    manager_uuid = _to_uuid(user.user_id)
    return svc.list_abm(
        manager_id=manager_uuid,
        role=user.role,
        client_name=client_name,
        from_date=from_date,
        to_date=to_date,
        page=page,
        size=size,
        sort=sort,
    )


@router.get("/{history_id}")
def get_abm(
    history_id: int,
    user: UserContext = Depends(get_current_user),
):
    manager_uuid = _to_uuid(user.user_id)
    detail = svc.get_abm_detail(history_id=history_id, manager_id=manager_uuid, role=user.role)
    if detail is None:
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없거나 접근 권한이 없습니다")
    return detail


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_abm(
    history_id: int,
    user: UserContext = Depends(get_current_user),
) -> Response:
    manager_uuid = _to_uuid(user.user_id)
    deleted = svc.delete_abm(history_id=history_id, manager_id=manager_uuid, role=user.role)
    if not deleted:
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없거나 접근 권한이 없습니다")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
