"""simulation_ai REST API — AI 분석 (Analyze 탭) 저장/조회/삭제.

엔드포인트:
- POST   /simulation-ai       — 신규 저장
- GET    /simulation-ai       — 목록 조회
- GET    /simulation-ai/{id}  — 상세 조회
- DELETE /simulation-ai/{id}  — 삭제

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

from src.services import simulation_ai_service as svc
from src.services.jwt_auth import UserContext, get_current_user

router = APIRouter(prefix="/simulation-ai", tags=["simulation-ai"])


def _to_uuid(raw: str) -> UUID:
    try:
        return UUID(raw)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail=f"Invalid user id: {exc}") from exc


class AISaveRequest(BaseModel):
    client_name: str
    brand_name: str
    business_type: str | None = None
    target_district: str | None = None
    winner_district: str | None = None
    ai_result: dict
    # scenario(=원본 SimulationInput) — DB 컬럼 추가 후 별 cycle 에서 service INSERT 에 활성.
    # schema 만 선반영 — 컬럼 부재 단계에선 pydantic이 받지만 service에서 무시(명시 필드만 INSERT).
    scenario: dict | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
def save_ai(
    body: AISaveRequest,
    user: UserContext = Depends(get_current_user),
):
    manager_uuid = _to_uuid(user.user_id)
    created = svc.create_ai(
        manager_id=manager_uuid,
        user_type=user.role,
        client_name=body.client_name.strip(),
        brand_name=body.brand_name,
        business_type=body.business_type,
        target_district=body.target_district,
        winner_district=body.winner_district,
        ai_result=body.ai_result,
    )
    return created


@router.get("")
def list_ai(
    client_name: Optional[str] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="created_at_desc"),
    user: UserContext = Depends(get_current_user),
):
    manager_uuid = _to_uuid(user.user_id)
    return svc.list_ai(
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
def get_ai(
    history_id: int,
    user: UserContext = Depends(get_current_user),
):
    manager_uuid = _to_uuid(user.user_id)
    detail = svc.get_ai_detail(history_id=history_id, manager_id=manager_uuid, role=user.role)
    if detail is None:
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없거나 접근 권한이 없습니다")
    return detail


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ai(
    history_id: int,
    user: UserContext = Depends(get_current_user),
) -> Response:
    manager_uuid = _to_uuid(user.user_id)
    deleted = svc.delete_ai(history_id=history_id, manager_id=manager_uuid, role=user.role)
    if not deleted:
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없거나 접근 권한이 없습니다")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
