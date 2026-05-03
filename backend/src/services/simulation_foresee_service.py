"""simulation_foresee CRUD — 예측 결과 (Predict 탭) 저장/조회/삭제.

simulation_history_service.py 패턴 재사용.
master(팀장): 본인 + 소속 매니저 이력 조회/삭제 가능.
manager: 본인 이력만.
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


def create_foresee(
    *,
    manager_id: UUID,
    user_type: str = "manager",
    client_name: str,
    brand_name: str,
    business_type: Optional[str],
    districts: Optional[list],
    target_district: Optional[str],
    winner_district: Optional[str],
    foresee_result: dict[str, Any],
    scenario: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """예측 결과 INSERT. 반환: {id, manager_id, client_name, created_at}"""
    engine = get_sync_engine(_db_url())
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO simulation_foresee
                    (manager_id, user_type, client_name, brand_name, business_type,
                     districts, target_district, winner_district,
                     district_predictions, quarterly_projection, scenarios,
                     shap_result, bep_months, predicted_monthly_revenue,
                     closure_rate, closure_risk, final_report, market_report,
                     customer_segment, living_pop_forecast, scenario)
                VALUES
                    (:manager_id, :user_type, :client_name, :brand_name, :business_type,
                     CAST(:districts AS jsonb), :target_district, :winner_district,
                     CAST(:district_predictions AS jsonb), CAST(:quarterly_projection AS jsonb),
                     CAST(:scenarios AS jsonb), CAST(:shap_result AS jsonb),
                     :bep_months, :predicted_monthly_revenue,
                     CAST(:closure_rate AS jsonb), CAST(:closure_risk AS jsonb),
                     CAST(:final_report AS jsonb), CAST(:market_report AS jsonb),
                     CAST(:customer_segment AS jsonb), CAST(:living_pop_forecast AS jsonb),
                     CAST(:scenario AS jsonb))
                RETURNING id, manager_id, client_name, created_at
                """
            ),
            {
                "manager_id": str(manager_id),
                "user_type": user_type,
                "client_name": client_name,
                "brand_name": brand_name,
                "business_type": business_type,
                "districts": json.dumps(districts) if districts else None,
                "target_district": target_district,
                "winner_district": winner_district,
                "district_predictions": json.dumps(foresee_result.get("district_predictions")),
                "quarterly_projection": json.dumps(foresee_result.get("quarterly_projection")),
                "scenarios": json.dumps(foresee_result.get("scenarios")),
                "shap_result": json.dumps(foresee_result.get("shap_result")),
                "bep_months": foresee_result.get("bep_months"),
                "predicted_monthly_revenue": foresee_result.get("predicted_monthly_revenue"),
                "closure_rate": json.dumps(foresee_result.get("closure_rate")),
                "closure_risk": json.dumps(foresee_result.get("closure_risk")),
                "final_report": json.dumps(foresee_result.get("final_report")),
                "market_report": json.dumps(foresee_result.get("market_report")),
                "customer_segment": json.dumps(foresee_result.get("customer_segment")),
                "living_pop_forecast": json.dumps(foresee_result.get("living_pop_forecast")),
                "scenario": json.dumps(scenario) if scenario else None,
            },
        ).fetchone()
    return dict(row._mapping)


def list_foresee(
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
    """목록 조회. master: 본인+소속 매니저. manager: 본인만."""
    if role == "master":
        where = [
            "(sf.manager_id = :manager_id OR sf.manager_id IN "
            "(SELECT id FROM manager_users WHERE owner_id = :manager_id))"
        ]
    else:
        where = ["sf.manager_id = :manager_id"]
    params: dict[str, Any] = {"manager_id": str(manager_id)}

    if client_name and client_name.strip():
        where.append("sf.client_name ILIKE :client_pattern")
        params["client_pattern"] = f"%{client_name.strip()}%"
    if from_date is not None:
        where.append("sf.created_at >= :from_date")
        params["from_date"] = datetime.combine(from_date, datetime.min.time())
    if to_date is not None:
        where.append("sf.created_at < :to_date_exclusive")
        params["to_date_exclusive"] = datetime.combine(to_date + timedelta(days=1), datetime.min.time())

    where_sql = " AND ".join(where)
    order_sql = "sf.created_at DESC" if sort == "created_at_desc" else "sf.client_name ASC"
    offset = max(0, (page - 1) * size)
    params["limit"] = size
    params["offset"] = offset

    engine = get_sync_engine(_db_url())
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM simulation_foresee sf WHERE {where_sql}"),
            params,
        ).scalar_one()

        rows = conn.execute(
            text(
                f"""
                SELECT sf.id, sf.client_name, sf.brand_name, sf.business_type,
                       sf.target_district, sf.winner_district, sf.bep_months,
                       sf.predicted_monthly_revenue, sf.created_at,
                       sf.manager_id, mu.contact_name AS manager_name
                FROM simulation_foresee sf
                LEFT JOIN manager_users mu ON mu.id = sf.manager_id
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


def get_foresee_detail(*, history_id: int, manager_id: UUID, role: str = "manager") -> Optional[dict[str, Any]]:
    """상세 조회."""
    if role == "master":
        access_filter = (
            "(sf.manager_id = :manager_id OR sf.manager_id IN "
            "(SELECT id FROM manager_users WHERE owner_id = :manager_id))"
        )
    else:
        access_filter = "sf.manager_id = :manager_id"

    engine = get_sync_engine(_db_url())
    with engine.connect() as conn:
        row = conn.execute(
            text(
                f"""
                SELECT sf.*, mu.contact_name AS manager_name
                FROM simulation_foresee sf
                LEFT JOIN manager_users mu ON mu.id = sf.manager_id
                WHERE sf.id = :history_id AND {access_filter}
                """
            ),
            {"history_id": history_id, "manager_id": str(manager_id)},
        ).fetchone()
    return dict(row._mapping) if row else None


def delete_foresee(*, history_id: int, manager_id: UUID, role: str = "manager") -> bool:
    """삭제."""
    if role == "master":
        access_filter = (
            "(manager_id = :manager_id OR manager_id IN (SELECT id FROM manager_users WHERE owner_id = :manager_id))"
        )
    else:
        access_filter = "manager_id = :manager_id"

    engine = get_sync_engine(_db_url())
    with engine.begin() as conn:
        result = conn.execute(
            text(f"DELETE FROM simulation_foresee WHERE id = :history_id AND {access_filter}"),
            {"history_id": history_id, "manager_id": str(manager_id)},
        )
    return (result.rowcount or 0) > 0
