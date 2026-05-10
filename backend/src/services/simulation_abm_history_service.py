"""simulation_abm CRUD — ABM 시뮬 결과 (5K agent) 저장/조회/삭제.

simulation_foresee_service / simulation_ai_service 와 동일한 권한 모델:
- superadmin: 전체.
- master(팀장): 본인 + 소속 매니저 이력.
- manager: 본인 이력만.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text

from src.database.sync_engine import get_sync_engine


def _db_url() -> str:
    from src.config.settings import settings

    return settings.postgres_url


def create_abm(
    *,
    manager_id: UUID,
    user_type: str = "manager",
    client_name: str,
    brand_name: str,
    business_type: Optional[str],
    target_district: Optional[str],
    spot_lat: Optional[float],
    spot_lon: Optional[float],
    n_agents: Optional[int],
    days: Optional[int],
    scenario: Optional[dict[str, Any]],
    result: dict[str, Any],
) -> dict[str, Any]:
    """ABM 시뮬 결과 INSERT. 반환: {id, manager_id, client_name, created_at}"""
    engine = get_sync_engine(_db_url())
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO simulation_abm
                    (manager_id, user_type, client_name, brand_name, business_type,
                     target_district, spot_lat, spot_lon, n_agents, days,
                     scenario, result)
                VALUES
                    (:manager_id, :user_type, :client_name, :brand_name, :business_type,
                     :target_district, :spot_lat, :spot_lon, :n_agents, :days,
                     CAST(:scenario AS jsonb), CAST(:result AS jsonb))
                RETURNING id, manager_id, client_name, created_at
                """
            ),
            {
                "manager_id": str(manager_id),
                "user_type": user_type,
                "client_name": client_name,
                "brand_name": brand_name,
                "business_type": business_type,
                "target_district": target_district,
                "spot_lat": spot_lat,
                "spot_lon": spot_lon,
                "n_agents": n_agents,
                "days": days,
                "scenario": json.dumps(scenario) if scenario else None,
                "result": json.dumps(result),
            },
        ).fetchone()
    return dict(row._mapping)


def list_abm(
    *,
    manager_id: UUID,
    role: str = "manager",
    client_name: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = 1,
    size: int = 20,
    sort: str = "created_at_desc",
) -> dict[str, Any]:
    """목록 조회. superadmin: 전체. master: 본인+소속 매니저. manager: 본인만."""
    if role == "superadmin":
        where = ["TRUE"]
    elif role == "master":
        where = [
            "(sa.manager_id = :manager_id OR sa.manager_id IN "
            "(SELECT id FROM manager_users WHERE owner_id = :manager_id))"
        ]
    else:
        where = ["sa.manager_id = :manager_id"]
    params: dict[str, Any] = {"manager_id": str(manager_id)}

    if client_name and client_name.strip():
        where.append("sa.client_name ILIKE :client_pattern")
        params["client_pattern"] = f"%{client_name.strip()}%"
    if from_date is not None:
        where.append("sa.created_at >= :from_date")
        params["from_date"] = datetime.combine(from_date, datetime.min.time())
    if to_date is not None:
        where.append("sa.created_at < :to_date_exclusive")
        params["to_date_exclusive"] = datetime.combine(to_date + timedelta(days=1), datetime.min.time())

    where_sql = " AND ".join(where)
    order_sql = "sa.created_at DESC" if sort == "created_at_desc" else "sa.client_name ASC"
    offset = max(0, (page - 1) * size)
    params["limit"] = size
    params["offset"] = offset

    engine = get_sync_engine(_db_url())
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM simulation_abm sa WHERE {where_sql}"),
            params,
        ).scalar_one()

        rows = conn.execute(
            text(
                f"""
                SELECT sa.id, sa.client_name, sa.brand_name, sa.business_type,
                       sa.target_district, sa.spot_lat, sa.spot_lon,
                       sa.n_agents, sa.days, sa.created_at,
                       sa.manager_id, mu.contact_name AS manager_name
                FROM simulation_abm sa
                LEFT JOIN manager_users mu ON mu.id = sa.manager_id
                WHERE {where_sql}
                ORDER BY {order_sql}
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).fetchall()

    return {
        "total": int(total or 0),
        "page": page,
        "size": size,
        "items": [dict(r._mapping) for r in rows],
    }


def get_abm_detail(*, history_id: int, manager_id: UUID, role: str = "manager") -> Optional[dict[str, Any]]:
    """상세 조회. superadmin: 전체. master: 본인+소속 매니저. manager: 본인만."""
    if role == "superadmin":
        access_filter = "TRUE"
    elif role == "master":
        access_filter = (
            "(sa.manager_id = :manager_id OR sa.manager_id IN "
            "(SELECT id FROM manager_users WHERE owner_id = :manager_id))"
        )
    else:
        access_filter = "sa.manager_id = :manager_id"

    engine = get_sync_engine(_db_url())
    with engine.connect() as conn:
        row = conn.execute(
            text(
                f"""
                SELECT sa.*, mu.contact_name AS manager_name
                FROM simulation_abm sa
                LEFT JOIN manager_users mu ON mu.id = sa.manager_id
                WHERE sa.id = :history_id AND {access_filter}
                """
            ),
            {"history_id": history_id, "manager_id": str(manager_id)},
        ).fetchone()
    return dict(row._mapping) if row else None


def delete_abm(*, history_id: int, manager_id: UUID, role: str = "manager") -> bool:
    """삭제. superadmin: 전체. master: 본인+소속 매니저. manager: 본인만."""
    if role == "superadmin":
        access_filter = "TRUE"
    elif role == "master":
        access_filter = (
            "(manager_id = :manager_id OR manager_id IN (SELECT id FROM manager_users WHERE owner_id = :manager_id))"
        )
    else:
        access_filter = "manager_id = :manager_id"

    engine = get_sync_engine(_db_url())
    with engine.begin() as conn:
        result = conn.execute(
            text(f"DELETE FROM simulation_abm WHERE id = :history_id AND {access_filter}"),
            {"history_id": history_id, "manager_id": str(manager_id)},
        )
    return (result.rowcount or 0) > 0
