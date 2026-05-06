"""슈퍼어드민 brand picker 엔드포인트 검증.

- require_superadmin: master/manager 403
- list_admin_brands: 시뮬 가능 업종 매핑·industry 필터·페이징
- list_supported_industries: 10종 모두 반환
- _resolve_business_type: indutyMlsfcNm → canonical key 매핑
- _industry_match_clause: 잘못된 key 400
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from src.api import admin_brands
from src.api.admin_brands import _industry_match_clause, _resolve_business_type, require_superadmin
from src.services.jwt_auth import UserContext

# ---------------------------------------------------------------------------
# require_superadmin
# ---------------------------------------------------------------------------


def _ctx(role: str) -> UserContext:
    return UserContext(user_id=str(uuid4()), role=role, email="x@y.z")


def test_require_superadmin_master_blocked():
    with pytest.raises(HTTPException) as exc:
        require_superadmin(_ctx("master"))
    assert exc.value.status_code == 403


def test_require_superadmin_manager_blocked():
    with pytest.raises(HTTPException) as exc:
        require_superadmin(_ctx("manager"))
    assert exc.value.status_code == 403


def test_require_superadmin_pass():
    out = require_superadmin(_ctx("superadmin"))
    assert out.role == "superadmin"


# ---------------------------------------------------------------------------
# _resolve_business_type
# ---------------------------------------------------------------------------


def test_resolve_korean():
    out = _resolve_business_type("한식")
    assert out == ("한식", "CS100001")


def test_resolve_coffee_variants():
    # FTC 표기 "음료 (커피 외)" 도 커피로 매핑
    assert _resolve_business_type("커피")[1] == "CS100010"
    assert _resolve_business_type("음료 (커피 외)")[1] == "CS100010"


def test_resolve_western_servery():
    # FTC 표기 "서양식" → 양식
    assert _resolve_business_type("서양식")[0] == "양식"


def test_resolve_pizza_to_fastfood():
    # 정책: 피자는 패스트푸드로 흡수
    assert _resolve_business_type("피자")[0] == "패스트푸드"


def test_resolve_unknown_returns_none():
    assert _resolve_business_type("기타외식") is None
    assert _resolve_business_type(None) is None
    assert _resolve_business_type("") is None


# ---------------------------------------------------------------------------
# _industry_match_clause
# ---------------------------------------------------------------------------


def test_industry_clause_specific():
    clause, params = _industry_match_clause("커피")
    # 커피 ftc_keywords 5개 (커피·카페·음료 (커피 외)·음료·디저트)
    assert clause.count("ILIKE") == 5
    assert any("커피" in v for v in params.values())


def test_industry_clause_all():
    clause, params = _industry_match_clause(None)
    # 10종 합집합 — 키 개수가 5 이상은 되어야 (대략 50+)
    assert clause.count("ILIKE") >= 30
    assert len(params) >= 30


def test_industry_clause_invalid_key():
    with pytest.raises(HTTPException) as exc:
        _industry_match_clause("기타외식")
    assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# list_admin_brands — DB 가로채 SQL 흐름 검증
# ---------------------------------------------------------------------------


class _SQLCapture:
    def __init__(self, total: int, rows: list):
        self.total = total
        self.rows = rows
        self.executed: list[tuple[str, dict]] = []

    def make_engine(self):
        cap = self

        class _Conn:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, *exc):
                return False

            def execute(self_inner, stmt, params=None):
                cap.executed.append((str(stmt.text), dict(params or {})))
                result = MagicMock()
                if "COUNT(*)" in str(stmt.text):
                    result.scalar_one.return_value = cap.total
                else:
                    result.fetchall.return_value = cap.rows
                return result

        class _Engine:
            def connect(self_inner):
                return _Conn()

        return _Engine()


class _Row:
    def __init__(self, mapping):
        self._mapping = mapping


def _row(brand_name, industry_medium, source="ftc", **kw):
    return _Row(
        {
            "brand_name": brand_name,
            "corp_name": kw.get("corp_name"),
            "biz_number": kw.get("biz_number"),
            "industry_medium": industry_medium,
            "franchise_count": kw.get("franchise_count"),
            "avg_sales": kw.get("avg_sales"),
            "source": source,
        }
    )


def test_list_admin_brands_filters_unsupported_industries(monkeypatch):
    cap = _SQLCapture(
        total=3,
        rows=[
            _row("스타벅스", "커피", franchise_count=1500),
            _row("이상한브랜드", "기타외식"),  # 매핑 안 되는 업종 → skip
            _row("BBQ", "치킨", franchise_count=2000),
        ],
    )
    monkeypatch.setattr(admin_brands, "get_sync_engine", lambda *_a, **_k: cap.make_engine())

    out = admin_brands.list_admin_brands(q=None, industry=None, page=1, size=50, _user=_ctx("superadmin"))
    # 매핑 안 되는 brand 는 응답에서 제외
    brand_names = [b["brand_name"] for b in out["items"]]
    assert "이상한브랜드" not in brand_names
    assert {"스타벅스", "BBQ"}.issubset(set(brand_names))

    starbucks = next(b for b in out["items"] if b["brand_name"] == "스타벅스")
    assert starbucks["business_type"] == "커피"
    assert starbucks["cs_code"] == "CS100010"


def test_list_admin_brands_search_param_propagates(monkeypatch):
    cap = _SQLCapture(total=0, rows=[])
    monkeypatch.setattr(admin_brands, "get_sync_engine", lambda *_a, **_k: cap.make_engine())

    admin_brands.list_admin_brands(q="스타", industry="커피", page=2, size=10, _user=_ctx("superadmin"))
    # 첫 SQL = COUNT, 두 번째 = SELECT
    count_sql, count_params = cap.executed[0]
    list_sql, list_params = cap.executed[1]

    assert "ILIKE :q_pat" in count_sql
    assert count_params["q_pat"] == "%스타%"
    assert list_params["limit"] == 10
    assert list_params["offset"] == 10  # (page-1) * size = 1 * 10


def test_list_admin_brands_supported_industries_metadata(monkeypatch):
    cap = _SQLCapture(total=0, rows=[])
    monkeypatch.setattr(admin_brands, "get_sync_engine", lambda *_a, **_k: cap.make_engine())

    out = admin_brands.list_admin_brands(q=None, industry=None, page=1, size=50, _user=_ctx("superadmin"))
    assert len(out["supported_industries"]) == 10
    keys = {it["key"] for it in out["supported_industries"]}
    assert {"한식", "커피", "치킨", "패스트푸드"}.issubset(keys)


def test_list_supported_industries_returns_10():
    out = admin_brands.list_supported_industries(_user=_ctx("superadmin"))
    assert len(out["industries"]) == 10
    cs_codes = {it["cs_code"] for it in out["industries"]}
    assert cs_codes == {f"CS10000{i}" for i in range(1, 10)} | {"CS100010"}
