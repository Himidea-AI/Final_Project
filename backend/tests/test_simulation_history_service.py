"""simulation_history_service.list_history 응답 검증.

master role 시 LEFT JOIN manager_users 가 결과에 포함되는지를 mock-based 로 확인.
실 DB 의존 0 — sqlalchemy execute 결과를 직접 mock.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

from src.services import simulation_history_service as svc


def _make_row(**kwargs):
    """sqlalchemy Row mock — _mapping 속성 + attribute 접근 둘 다 가능."""
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    row._mapping = kwargs
    return row


def test_list_history_master_includes_manager_name():
    """master 호출 시 응답 items 에 manager_name 필드가 포함된다."""
    master_id = uuid4()
    sample_row = _make_row(
        id=1,
        manager_id=uuid4(),
        manager_name="홍길동",
        client_name="강남 카페",
        district="역삼동",
        brand_name="스타벅스",
        business_type="카페",
        ai_verdict_summary="positive",
        market_entry_signal="green",
        created_at="2026-04-28T10:00:00",
    )

    fake_conn = MagicMock()
    fake_conn.execute.return_value.scalar_one.return_value = 1
    fake_conn.execute.return_value.fetchall.return_value = [sample_row]

    fake_engine = MagicMock()
    fake_engine.connect.return_value.__enter__.return_value = fake_conn

    with patch.object(svc, "get_sync_engine", return_value=fake_engine):
        result = svc.list_history(
            manager_id=master_id,
            role="master",
            owner_id=None,
            client_name=None,
            from_date=None,
            to_date=None,
            page=1,
            size=20,
            sort="created_at_desc",
        )

    assert result["total"] == 1
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["manager_name"] == "홍길동"
    assert item["client_name"] == "강남 카페"


def test_list_history_manager_only_self():
    """manager 호출 시 WHERE 절에 sh.manager_id = :manager_id 단일 조건만."""
    manager_id = uuid4()

    fake_conn = MagicMock()
    fake_conn.execute.return_value.scalar_one.return_value = 0
    fake_conn.execute.return_value.fetchall.return_value = []

    fake_engine = MagicMock()
    fake_engine.connect.return_value.__enter__.return_value = fake_conn

    with patch.object(svc, "get_sync_engine", return_value=fake_engine):
        svc.list_history(
            manager_id=manager_id,
            role="manager",
            owner_id=None,
            client_name=None,
            from_date=None,
            to_date=None,
            page=1,
            size=20,
            sort="created_at_desc",
        )

    # SELECT 호출 2번 (COUNT + main). 둘 다 sh.manager_id = :manager_id 포함, OR 분기 미포함.
    sql_calls = [str(c.args[0]) for c in fake_conn.execute.call_args_list]
    main_sql = next(s for s in sql_calls if "LEFT JOIN" in s)
    assert "sh.manager_id = :manager_id" in main_sql
    assert "owner_id = :manager_id" not in main_sql  # master 분기 미적용
