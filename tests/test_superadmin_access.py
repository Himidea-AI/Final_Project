"""superadmin role access 검증.

대상:
- jwt_auth.decode_token: superadmin 토큰 허용, 알 수 없는 role 거절
- simulation_ai_service.list_ai/get_ai_detail/delete_ai: superadmin은 access_filter='TRUE'
- simulation_foresee_service.list_foresee/get_foresee_detail/delete_foresee: 동일
- AuthService.login: is_superadmin=true 사용자에게 role='superadmin' 반환

DB 의존 케이스는 monkeypatch로 SQL 실행 가로채서 access_filter 분기만 검증.
실제 DB 통합은 별도 e2e 테스트 영역.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from jose import jwt
from src.config.settings import settings
from src.services import jwt_auth
from src.services import simulation_ai_service as ai_svc
from src.services import simulation_foresee_service as fs_svc

# ---------------------------------------------------------------------------
# jwt_auth.decode_token
# ---------------------------------------------------------------------------


def _make_token(role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "role": role,
        "email": "admin@example.com",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def test_decode_token_accepts_superadmin():
    token = _make_token("superadmin")
    ctx = jwt_auth.decode_token(token)
    assert ctx.role == "superadmin"


def test_decode_token_accepts_master():
    token = _make_token("master")
    ctx = jwt_auth.decode_token(token)
    assert ctx.role == "master"


def test_decode_token_accepts_manager():
    token = _make_token("manager")
    ctx = jwt_auth.decode_token(token)
    assert ctx.role == "manager"


def test_decode_token_rejects_unknown_role():
    token = _make_token("god")
    with pytest.raises(HTTPException) as excinfo:
        jwt_auth.decode_token(token)
    assert excinfo.value.status_code == 401
    assert "Unknown role" in excinfo.value.detail


# ---------------------------------------------------------------------------
# simulation_ai_service / simulation_foresee_service
# ---------------------------------------------------------------------------


class _SQLCapture:
    """get_sync_engine을 가로채 실행된 SQL과 params를 캡처."""

    def __init__(self, count_value: int = 0, rows: list | None = None, fetched=None, rowcount: int = 0):
        self.count_value = count_value
        self.rows = rows or []
        self.fetched = fetched
        self.rowcount = rowcount
        self.executed: list[tuple[str, dict]] = []

    def make_engine(self):
        capture = self

        class _Conn:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def execute(self_inner, stmt, params=None):
                capture.executed.append((str(stmt.text), dict(params or {})))
                result = MagicMock()
                result.scalar_one.return_value = capture.count_value
                result.fetchall.return_value = capture.rows
                result.fetchone.return_value = capture.fetched
                result.rowcount = capture.rowcount
                return result

        class _Engine:
            def connect(self_inner):
                return _Conn()

            def begin(self_inner):
                return _Conn()

        return _Engine()


def _patch_engine(monkeypatch, module, capture: _SQLCapture):
    monkeypatch.setattr(module, "get_sync_engine", lambda *_a, **_k: capture.make_engine())


def test_list_ai_superadmin_uses_no_manager_filter(monkeypatch):
    cap = _SQLCapture(count_value=42)
    _patch_engine(monkeypatch, ai_svc, cap)
    out = ai_svc.list_ai(manager_id=uuid4(), role="superadmin")
    assert out["total"] == 42
    # 첫 SQL = COUNT, 두 번째 = SELECT
    count_sql = cap.executed[0][0]
    list_sql = cap.executed[1][0]
    assert "WHERE TRUE" in count_sql
    assert "WHERE TRUE" in list_sql
    # superadmin은 manager_id 기반 격리 절대 없음
    assert "sa.manager_id = :manager_id" not in count_sql
    assert "owner_id = :manager_id" not in count_sql


def test_list_ai_master_uses_owner_branch(monkeypatch):
    cap = _SQLCapture(count_value=3)
    _patch_engine(monkeypatch, ai_svc, cap)
    ai_svc.list_ai(manager_id=uuid4(), role="master")
    sql = cap.executed[0][0]
    assert "sa.manager_id = :manager_id" in sql
    assert "owner_id = :manager_id" in sql
    assert "WHERE TRUE" not in sql


def test_list_ai_manager_uses_self_only(monkeypatch):
    cap = _SQLCapture(count_value=1)
    _patch_engine(monkeypatch, ai_svc, cap)
    ai_svc.list_ai(manager_id=uuid4(), role="manager")
    sql = cap.executed[0][0]
    assert "sa.manager_id = :manager_id" in sql
    assert "owner_id = :manager_id" not in sql
    assert "WHERE TRUE" not in sql


def test_get_ai_detail_superadmin_no_filter(monkeypatch):
    cap = _SQLCapture(fetched=None)
    _patch_engine(monkeypatch, ai_svc, cap)
    ai_svc.get_ai_detail(history_id=1, manager_id=uuid4(), role="superadmin")
    sql = cap.executed[0][0]
    assert "AND TRUE" in sql
    assert "sa.manager_id = :manager_id" not in sql


def test_delete_ai_superadmin_no_filter(monkeypatch):
    cap = _SQLCapture(rowcount=1)
    _patch_engine(monkeypatch, ai_svc, cap)
    ok = ai_svc.delete_ai(history_id=1, manager_id=uuid4(), role="superadmin")
    assert ok is True
    sql = cap.executed[0][0]
    assert "AND TRUE" in sql
    assert "manager_id = :manager_id" not in sql.replace("sa.manager_id", "")


def test_list_foresee_superadmin_no_filter(monkeypatch):
    cap = _SQLCapture(count_value=10)
    _patch_engine(monkeypatch, fs_svc, cap)
    fs_svc.list_foresee(manager_id=uuid4(), role="superadmin")
    count_sql = cap.executed[0][0]
    assert "WHERE TRUE" in count_sql
    assert "sf.manager_id = :manager_id" not in count_sql


def test_get_foresee_detail_superadmin_no_filter(monkeypatch):
    cap = _SQLCapture(fetched=None)
    _patch_engine(monkeypatch, fs_svc, cap)
    fs_svc.get_foresee_detail(history_id=1, manager_id=uuid4(), role="superadmin")
    sql = cap.executed[0][0]
    assert "AND TRUE" in sql


def test_delete_foresee_superadmin_no_filter(monkeypatch):
    cap = _SQLCapture(rowcount=1)
    _patch_engine(monkeypatch, fs_svc, cap)
    ok = fs_svc.delete_foresee(history_id=1, manager_id=uuid4(), role="superadmin")
    assert ok is True
    sql = cap.executed[0][0]
    assert "AND TRUE" in sql


# ---------------------------------------------------------------------------
# auth.login 의 role 분기 — 통합 mock
# ---------------------------------------------------------------------------


class _FakeRow:
    def __init__(self, mapping: dict):
        self._mapping = mapping


def _make_login_engine(user_dict: dict, brand_dict: dict | None):
    """auth.login() 이 호출하는 SELECT/UPDATE 스텁."""
    state: dict = {"step": 0}

    class _Conn:
        def __enter__(self_inner):
            return self_inner

        def __exit__(self_inner, *exc):
            return False

        def execute(self_inner, stmt, params=None):
            state["step"] += 1
            result = MagicMock()
            sql = str(stmt.text)
            if "FROM users" in sql:
                result.fetchone.return_value = _FakeRow(user_dict)
            elif "FROM biz_brand_mapping" in sql:
                result.fetchone.return_value = _FakeRow(brand_dict) if brand_dict else None
            else:
                result.fetchone.return_value = None
            return result

        def commit(self_inner):
            pass

    class _Engine:
        def connect(self_inner):
            return _Conn()

    return _Engine()


def test_login_returns_superadmin_role_when_flag_true(monkeypatch):
    import bcrypt
    from src.services import auth as auth_module

    pw = "pw1234!"
    hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    user = {
        "id": uuid4(),
        "company_name": "ACME",
        "biz_number": "1234567890",
        "contact_name": "관리자",
        "position": "CEO",
        "email": "admin@acme.com",
        "phone": "010-0000-0000",
        "store_count": 1,
        "password_hash": hashed,
        "plan": "starter",
        "is_active": True,
        "is_superadmin": True,
    }
    brand = {
        "brand_name": "ACME",
        "industry_large": "외식업",
        "industry_medium": "한식",
        "franchise_count": 5,
        "avg_sales": 10000,
        "mapo_store_count": 1,
    }

    engine = _make_login_engine(user, brand)
    monkeypatch.setattr(auth_module, "get_sync_engine", lambda *_a, **_k: engine)

    svc = auth_module.AuthService.__new__(auth_module.AuthService)
    svc._db_url = "postgresql://stub"
    svc._mapper = MagicMock()

    out = svc.login("admin@acme.com", pw)
    assert out["status"] == "success"
    assert out["user"]["role"] == "superadmin"


def test_login_returns_master_role_when_flag_false(monkeypatch):
    import bcrypt
    from src.services import auth as auth_module

    pw = "pw1234!"
    hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    user = {
        "id": uuid4(),
        "company_name": "ACME",
        "biz_number": "1234567890",
        "contact_name": "사장",
        "position": "대표",
        "email": "ceo@acme.com",
        "phone": "010-0000-0000",
        "store_count": 1,
        "password_hash": hashed,
        "plan": "starter",
        "is_active": True,
        "is_superadmin": False,
    }
    engine = _make_login_engine(user, None)
    monkeypatch.setattr(auth_module, "get_sync_engine", lambda *_a, **_k: engine)

    svc = auth_module.AuthService.__new__(auth_module.AuthService)
    svc._db_url = "postgresql://stub"
    svc._mapper = MagicMock()
    svc._mapper.search_brand_by_company.return_value = []

    out = svc.login("ceo@acme.com", pw)
    assert out["status"] == "success"
    assert out["user"]["role"] == "master"
