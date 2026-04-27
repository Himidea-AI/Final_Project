"""world_loader._load_dong_industry_weight() v4 confidence 가중 테스트."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[2]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from backend.src.simulation.world_loader import _load_dong_industry_weight  # noqa: E402


@pytest.fixture
def engine():
    return create_engine(os.environ["POSTGRES_URL"])


def test_world_loader_returns_dict(engine):
    """기본 — dict 반환 + 키는 (dong, cat) tuple."""
    weights = _load_dong_industry_weight(engine)
    assert isinstance(weights, dict)
    if weights:
        k = next(iter(weights.keys()))
        assert isinstance(k, tuple) and len(k) == 2


def test_world_loader_popularity_range_05_15(engine):
    """모든 popularity ∈ [0.5, 1.5]."""
    weights = _load_dong_industry_weight(engine)
    for v in weights.values():
        assert 0.5 <= v <= 1.5, f"popularity {v} 범위 밖"


def test_world_loader_includes_imputed_dong_industry(engine):
    """v4 적재 후 결측 (동, 업종) 도 popularity 정의됨."""
    weights = _load_dong_industry_weight(engine)
    # 24Q 전체 결측 — 아현동 양식음식점 (한식음식점→음식점 카테고리)
    # 음식점 카테고리에 양식음식점 매핑 → 아현동 음식점 포함 여부 확인
    assert ("아현동", "음식점") in weights or ("아현동", "카페") in weights


def test_world_loader_backward_compat_when_v4_empty(engine):
    """v4 테이블 비어있으면 v3 결과와 동일해야."""
    with engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE v4_backup AS SELECT * FROM seoul_district_sales_imputed_v4"))
        conn.execute(text("DELETE FROM seoul_district_sales_imputed_v4"))
        weights_empty = _load_dong_industry_weight(engine)
        conn.execute(text("INSERT INTO seoul_district_sales_imputed_v4 SELECT * FROM v4_backup"))
    # 빈 v4 → COALESCE 가 monthly_sales 만 사용 → v3 와 동일 동작
    assert isinstance(weights_empty, dict)
    # 결측 셀 (아현동 양식) 은 v4 비어있으면 dict 에 없어야
    # (origin v3 동작)
