"""living_population 일별 boost loader 단위 테스트."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


@patch("src.simulation.world_loader.get_sync_engine")
def test_load_living_population_daily_returns_dict(mock_engine):
    """정상 — (dong, hour, day_idx) → boost dict 반환."""
    from src.simulation.world_loader import _load_living_population_daily

    mock_conn = MagicMock()
    mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.mappings.return_value = [
        {"dong_name": "서교동", "time_zone": 14, "day_idx": 0, "total_pop": 5000.0, "dong_avg": 4000.0},
        {"dong_name": "서교동", "time_zone": 14, "day_idx": 1, "total_pop": 4500.0, "dong_avg": 4000.0},
    ]

    result = _load_living_population_daily(date(2026, 1, 1), days=2)
    assert ("서교동", 14, 0) in result
    assert result[("서교동", 14, 0)] == pytest.approx(1.25, abs=0.01)
    assert result[("서교동", 14, 1)] == pytest.approx(1.125, abs=0.01)


@patch("src.simulation.world_loader.get_sync_engine")
def test_load_living_population_empty_returns_empty_dict(mock_engine):
    """DB 데이터 0건 → 빈 dict (시뮬은 fallback boost)."""
    from src.simulation.world_loader import _load_living_population_daily

    mock_conn = MagicMock()
    mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.mappings.return_value = []

    result = _load_living_population_daily(date(2026, 1, 1), days=90)
    assert result == {}


def test_world_has_living_pop_daily_boost_field():
    """World 데이터클래스에 living_pop_daily_boost 필드 존재."""
    from src.simulation.world import World

    w = World()
    assert hasattr(w, "living_pop_daily_boost")
    assert isinstance(w.living_pop_daily_boost, dict)
    assert w.living_pop_daily_boost == {}
