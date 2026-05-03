"""simulation_foresee REST API — 예측 결과 (Predict 탭) 저장/조회/삭제.

엔드포인트:
- POST   /simulation-foresee       — 신규 저장
- GET    /simulation-foresee       — 목록 조회
- GET    /simulation-foresee/{id}  — 상세 조회
- DELETE /simulation-foresee/{id}  — 삭제

권한:
- master(팀장): 본인 이력 + 소속 매니저 이력 조회/삭제 가능.
- manager: 본인 이력만 R/W.
"""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from src.services import simulation_foresee_service as svc
from src.services.jwt_auth import UserContext, get_current_user

router = APIRouter(prefix="/simulation-foresee", tags=["simulation-foresee"])


def _to_uuid(raw: str) -> UUID:
    try:
        return UUID(raw)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail=f"Invalid user id: {exc}") from exc


class ForeseeSaveRequest(BaseModel):
    client_name: str
    brand_name: str
    business_type: str | None = None
    districts: list[str] | None = None
    target_district: str | None = None
    winner_district: str | None = None
    foresee_result: dict


@router.post("", status_code=status.HTTP_201_CREATED)
def save_foresee(
    body: ForeseeSaveRequest,
    user: UserContext = Depends(get_current_user),
):
    manager_uuid = _to_uuid(user.user_id)
    created = svc.create_foresee(
        manager_id=manager_uuid,
        user_type=user.role,
        client_name=body.client_name.strip(),
        brand_name=body.brand_name,
        business_type=body.business_type,
        districts=body.districts,
        target_district=body.target_district,
        winner_district=body.winner_district,
        foresee_result=body.foresee_result,
    )
    return created


@router.get("")
def list_foresee(
    client_name: Optional[str] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="created_at_desc"),
    user: UserContext = Depends(get_current_user),
):
    manager_uuid = _to_uuid(user.user_id)
    return svc.list_foresee(
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
def get_foresee(
    history_id: int,
    user: UserContext = Depends(get_current_user),
):
    manager_uuid = _to_uuid(user.user_id)
    detail = svc.get_foresee_detail(history_id=history_id, manager_id=manager_uuid, role=user.role)
    if detail is None:
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없거나 접근 권한이 없습니다")
    return detail


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_foresee(
    history_id: int,
    user: UserContext = Depends(get_current_user),
) -> Response:
    manager_uuid = _to_uuid(user.user_id)
    deleted = svc.delete_foresee(history_id=history_id, manager_id=manager_uuid, role=user.role)
    if not deleted:
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없거나 접근 권한이 없습니다")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
