"""simulation_history REST API.

4 엔드포인트 (프론트는 `/api/*` 로 호출 → Vite proxy 가 `/api` 제거 후 백엔드 전달):
- POST   /simulation-history       — 신규 저장
- GET    /simulation-history       — 목록 (필터)
- GET    /simulation-history/{id}  — 상세
- DELETE /simulation-history/{id}  — 삭제

권한: 본인(manager_id=토큰 sub) 이력만 R/W.
role='manager' 또는 role='master' 모두 본인 user_id 범위로 적용.
(master가 하위 매니저 이력 조회는 Phase 2.)
"""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from src.schemas.simulation_history import (
    SimulationHistoryCreate,
    SimulationHistoryCreateResponse,
    SimulationHistoryDetail,
    SimulationHistoryListResponse,
    SortKey,
)
from src.services import simulation_history_service as svc
from src.services.jwt_auth import UserContext, get_current_user

router = APIRouter(prefix="/simulation-history", tags=["simulation-history"])


def _to_uuid(raw: str) -> UUID:
    try:
        return UUID(raw)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail=f"Invalid manager id in token: {exc}") from exc


@router.post("", response_model=SimulationHistoryCreateResponse, status_code=status.HTTP_201_CREATED)
def save_history(
    body: SimulationHistoryCreate,
    user: UserContext = Depends(get_current_user),
) -> SimulationHistoryCreateResponse:
    manager_uuid = _to_uuid(user.user_id)
    created = svc.create_history(
        manager_id=manager_uuid,
        client_name=body.client_name.strip(),
        district=body.district,
        brand_name=body.brand_name,
        business_type=body.business_type,
        scenario=body.scenario,
        simulation_result=body.simulation_result,
        ai_verdict_summary=body.ai_verdict_summary,
        market_entry_signal=body.market_entry_signal,
    )
    return SimulationHistoryCreateResponse(**created)


@router.get("", response_model=SimulationHistoryListResponse)
def list_history(
    client_name: Optional[str] = Query(default=None, description="고객명 부분 일치 (ILIKE %pattern%)"),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    sort: SortKey = Query(default="created_at_desc"),
    user: UserContext = Depends(get_current_user),
) -> SimulationHistoryListResponse:
    manager_uuid = _to_uuid(user.user_id)
    raw = svc.list_history(
        manager_id=manager_uuid,
        client_name=client_name,
        from_date=from_date,
        to_date=to_date,
        page=page,
        size=size,
        sort=sort,
    )
    return SimulationHistoryListResponse(**raw)


@router.get("/{history_id}", response_model=SimulationHistoryDetail)
def get_history(
    history_id: int,
    user: UserContext = Depends(get_current_user),
) -> SimulationHistoryDetail:
    manager_uuid = _to_uuid(user.user_id)
    detail = svc.get_history_detail(history_id=history_id, manager_id=manager_uuid)
    if detail is None:
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없거나 접근 권한이 없습니다")
    return SimulationHistoryDetail(**detail)


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(
    history_id: int,
    user: UserContext = Depends(get_current_user),
) -> Response:
    manager_uuid = _to_uuid(user.user_id)
    deleted = svc.delete_history(history_id=history_id, manager_id=manager_uuid)
    if not deleted:
        raise HTTPException(status_code=404, detail="이력을 찾을 수 없거나 접근 권한이 없습니다")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
