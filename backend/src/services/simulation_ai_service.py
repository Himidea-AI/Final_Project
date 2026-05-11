"""simulation_ai CRUD — AI 분석 (Analyze 탭) 저장/조회/삭제.

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


def create_ai(
    *,
    manager_id: UUID,
    user_type: str = "manager",
    client_name: str,
    brand_name: str,
    business_type: Optional[str],
    target_district: Optional[str],
    winner_district: Optional[str],
    ai_result: dict[str, Any],
    scenario: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """AI 분석 INSERT. 반환: {id, manager_id, client_name, created_at}"""
    engine = get_sync_engine(_db_url())
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO simulation_ai
                    (manager_id, user_type, client_name, brand_name, business_type,
                     target_district, winner_district, top_3_candidates,
                     analysis_report, ai_recommendation, ai_verdict_summary,
                     market_entry_signal, overall_legal_risk,
                     legal_risks, market_report, trend_forecast,
                     competitor_intel, demographic_report,
                     district_rankings, agent_attributions,
                     vacancy_applied, all_competitor_locations, scenario)
                VALUES
                    (:manager_id, :user_type, :client_name, :brand_name, :business_type,
                     :target_district, :winner_district, CAST(:top_3_candidates AS jsonb),
                     :analysis_report, :ai_recommendation, :ai_verdict_summary,
                     :market_entry_signal, :overall_legal_risk,
                     CAST(:legal_risks AS jsonb), CAST(:market_report AS jsonb),
                     CAST(:trend_forecast AS jsonb), CAST(:competitor_intel AS jsonb),
                     CAST(:demographic_report AS jsonb), CAST(:district_rankings AS jsonb),
                     CAST(:agent_attributions AS jsonb),
                     :vacancy_applied, CAST(:all_competitor_locations AS jsonb),
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
                "target_district": target_district,
                "winner_district": winner_district,
                "top_3_candidates": json.dumps(ai_result.get("top_3_candidates")),
                "analysis_report": ai_result.get("analysis_report"),
                "ai_recommendation": ai_result.get("ai_recommendation"),
                "ai_verdict_summary": ai_result.get("ai_verdict_summary"),
                "market_entry_signal": ai_result.get("market_entry_signal"),
                "overall_legal_risk": ai_result.get("overall_legal_risk"),
                "legal_risks": json.dumps(ai_result.get("legal_risks")),
                "market_report": json.dumps(ai_result.get("market_report")),
                "trend_forecast": json.dumps(ai_result.get("trend_forecast")),
                "competitor_intel": json.dumps(ai_result.get("competitor_intel")),
                "demographic_report": json.dumps(ai_result.get("demographic_report")),
                "district_rankings": json.dumps(ai_result.get("district_rankings")),
                "agent_attributions": json.dumps(ai_result.get("agent_attributions")),
                "vacancy_applied": ai_result.get("vacancy_applied", False),
                "all_competitor_locations": json.dumps(ai_result.get("all_competitor_locations")),
                "scenario": json.dumps(scenario) if scenario else None,
            },
        ).fetchone()
    return dict(row._mapping)


def list_ai(
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
            text(f"SELECT COUNT(*) FROM simulation_ai sa WHERE {where_sql}"),
            params,
        ).scalar_one()

        rows = conn.execute(
            text(
                f"""
                SELECT sa.id, sa.client_name, sa.brand_name, sa.business_type,
                       sa.target_district, sa.winner_district,
                       sa.ai_verdict_summary, sa.market_entry_signal,
                       sa.overall_legal_risk, sa.created_at,
                       sa.manager_id, mu.contact_name AS manager_name
                FROM simulation_ai sa
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


def get_ai_detail(*, history_id: int, manager_id: UUID, role: str = "manager") -> Optional[dict[str, Any]]:
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
                FROM simulation_ai sa
                LEFT JOIN manager_users mu ON mu.id = sa.manager_id
                WHERE sa.id = :history_id AND {access_filter}
                """
            ),
            {"history_id": history_id, "manager_id": str(manager_id)},
        ).fetchone()
    return dict(row._mapping) if row else None


def delete_ai(*, history_id: int, manager_id: UUID, role: str = "manager") -> bool:
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
            text(f"DELETE FROM simulation_ai WHERE id = :history_id AND {access_filter}"),
            {"history_id": history_id, "manager_id": str(manager_id)},
        )
    return (result.rowcount or 0) > 0
