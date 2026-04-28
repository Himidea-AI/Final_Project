"""simulation_history CRUD — 동기 엔진 기반 (auth.py·district_ranking.py와 동일 전략).

async 엔진 도입은 별도 리팩터. 이번 단계는 최소 침습적으로 기존 패턴 재사용.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import text

from src.database.sync_engine import get_sync_engine


def _db_url() -> str:
    # auth.py가 사용하는 동일 설정 경로
    from src.config.settings import settings

    return settings.postgres_url


def create_history(
    *,
    manager_id: UUID,
    user_type: str = "manager",  # 'master'(팀장/users) | 'manager'(매니저/manager_users)
    client_name: str,
    district: str,
    brand_name: str,
    business_type: Optional[str],
    scenario: Optional[dict[str, Any]],
    simulation_result: dict[str, Any],
    ai_verdict_summary: Optional[str],
    market_entry_signal: Optional[str],
) -> dict[str, Any]:
    """신규 이력 INSERT. 팀장/매니저 모두 저장 가능. 반환: {id, manager_id, client_name, created_at}"""
    import json

    engine = get_sync_engine(_db_url())
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO simulation_history
                    (manager_id, user_type, client_name, district, brand_name, business_type,
                     scenario, simulation_result, ai_verdict_summary, market_entry_signal)
                VALUES
                    (:manager_id, :user_type, :client_name, :district, :brand_name, :business_type,
                     CAST(:scenario AS jsonb), CAST(:simulation_result AS jsonb),
                     :ai_verdict_summary, :market_entry_signal)
                RETURNING id, manager_id, client_name, created_at
                """
            ),
            {
                "manager_id": str(manager_id),
                "user_type": user_type,
                "client_name": client_name,
                "district": district,
                "brand_name": brand_name,
                "business_type": business_type,
                "scenario": json.dumps(scenario) if scenario is not None else None,
                "simulation_result": json.dumps(simulation_result),
                "ai_verdict_summary": ai_verdict_summary,
                "market_entry_signal": market_entry_signal,
            },
        ).fetchone()
    return dict(row._mapping)


def list_history(
    *,
    manager_id: UUID,
    role: str = "manager",
    owner_id: Optional[str] = None,
    client_name: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = 1,
    size: int = 20,
    sort: str = "created_at_desc",
) -> dict[str, Any]:
    """필터 조건 AND 결합. 페이지네이션.

    master(팀장): 본인 + 소속 매니저 이력 모두 조회.
    manager: 본인 이력만.
    """
    if role == "master":
        # 팀장 본인 이력 + 소속 매니저 이력
        where = [
            "(manager_id = :manager_id OR manager_id IN (SELECT id FROM manager_users WHERE owner_id = :manager_id))"
        ]
    else:
        where = ["manager_id = :manager_id"]
    params: dict[str, Any] = {"manager_id": str(manager_id)}

    if client_name and client_name.strip():
        where.append("client_name ILIKE :client_pattern")
        params["client_pattern"] = f"%{client_name.strip()}%"

    if from_date is not None:
        where.append("created_at >= :from_date")
        params["from_date"] = datetime.combine(from_date, datetime.min.time())

    if to_date is not None:
        # 포함 끝 — 다음날 00:00 미만
        where.append("created_at < :to_date_exclusive")
        params["to_date_exclusive"] = datetime.combine(to_date + timedelta(days=1), datetime.min.time())

    where_sql = " AND ".join(where)
    order_sql = "created_at DESC" if sort == "created_at_desc" else "client_name ASC"
    offset = max(0, (page - 1) * size)
    params["limit"] = size
    params["offset"] = offset

    engine = get_sync_engine(_db_url())
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM simulation_history WHERE {where_sql}"),
            params,
        ).scalar_one()

        rows = conn.execute(
            text(
                f"""
                SELECT id, client_name, district, brand_name, business_type,
                       ai_verdict_summary, market_entry_signal, created_at
                FROM simulation_history
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


def get_history_detail(*, history_id: int, manager_id: UUID, role: str = "manager") -> Optional[dict[str, Any]]:
    """master: 본인+소속 매니저 이력 조회. manager: 본인만."""
    if role == "master":
        access_filter = (
            "(manager_id = :manager_id OR manager_id IN (SELECT id FROM manager_users WHERE owner_id = :manager_id))"
        )
    else:
        access_filter = "manager_id = :manager_id"

    engine = get_sync_engine(_db_url())
    with engine.connect() as conn:
        row = conn.execute(
            text(
                f"""
                SELECT id, manager_id, client_name, district, brand_name, business_type,
                       scenario, simulation_result,
                       ai_verdict_summary, market_entry_signal,
                       created_at, updated_at
                FROM simulation_history
                WHERE id = :history_id AND {access_filter}
                """
            ),
            {"history_id": history_id, "manager_id": str(manager_id)},
        ).fetchone()
    return dict(row._mapping) if row else None


def delete_history(*, history_id: int, manager_id: UUID, role: str = "manager") -> bool:
    """master: 본인+소속 매니저 이력 삭제 가능. manager: 본인만. 삭제 성공 True."""
    if role == "master":
        access_filter = (
            "(manager_id = :manager_id OR manager_id IN (SELECT id FROM manager_users WHERE owner_id = :manager_id))"
        )
    else:
        access_filter = "manager_id = :manager_id"

    engine = get_sync_engine(_db_url())
    with engine.begin() as conn:
        result = conn.execute(
            text(
                f"""
                DELETE FROM simulation_history
                WHERE id = :history_id AND {access_filter}
                """
            ),
            {"history_id": history_id, "manager_id": str(manager_id)},
        )
    return (result.rowcount or 0) > 0
