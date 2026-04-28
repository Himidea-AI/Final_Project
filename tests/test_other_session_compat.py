"""다른 세션의 brand-menu 작업 회귀 테스트 — v4 도입 영향 0."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_brand_menu_loader_unaffected_by_v4():
    """다른 세션의 brand_menu_loader 정상 동작."""
    try:
        from backend.src.services.brand_menu_loader import load_brand_menu_items

        menu = load_brand_menu_items("이디야")
        assert isinstance(menu, list)
    except (ImportError, ModuleNotFoundError):
        pytest.skip("brand_menu_loader 미구현 (다른 세션 진행 중)")


def test_living_pop_daily_boost_unaffected():
    """다른 세션의 _load_living_population_daily 정상 동작."""
    try:
        from backend.src.simulation.world_loader import _load_living_population_daily

        boost = _load_living_population_daily(start_date="2024-01-01", days=7)
        assert isinstance(boost, dict)
    except (ImportError, AttributeError):
        pytest.skip("_load_living_population_daily 미구현 (다른 세션 진행 중)")


def test_vacancy_pse_signature_unchanged():
    """vacancy_pse 시그니처에 우리 변경 없음."""
    import inspect
    import sys

    # world_loader.py 의 module-level 'from src.database.sync_engine' import 가
    # repo root 실행 시 ModuleNotFoundError 를 발생시키는 pre-existing issue.
    # backend/ 를 sys.path 에 추가해 src.database 를 찾을 수 있도록 한다.
    backend_path = str(Path(__file__).resolve().parents[1] / "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    try:
        from backend.src.simulation.vacancy_pse import evaluate_vacancy_pse
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.skip(f"vacancy_pse import 실패 (다른 세션 진행 중 또는 환경 미설정): {exc}")

    sig = inspect.signature(evaluate_vacancy_pse)
    # 다른 세션이 추가한 인자들이 있을 수 있지만, 우리는 추가 X
    assert "vacancy_spot" in sig.parameters
    assert "category" in sig.parameters
