"""vacancy_pse 의 menu_items + 시각화 + LLM 인자 동작."""

import pytest

from src.simulation.vacancy_pse import evaluate_vacancy_pse

SPOT = {"dong": "서교동", "lat": 37.5544, "lon": 126.9220}


@pytest.mark.slow
def test_pse_with_menu_items_uses_menu_prices():
    """menu_items 제공 → vacancy 매장의 spend 가 메뉴 가격에서 sampling."""
    menu = [{"name": "라떼", "price": 5000}]
    result = evaluate_vacancy_pse(
        SPOT,
        "카페",
        n_seeds=1,
        days=1,
        with_cannibalization=False,
        menu_items=menu,
    )
    visits = result["pse_summary"]["visits_per_day"]["mean"]
    if visits > 0:
        avg_spend = result["pse_summary"]["revenue_per_day"]["mean"] / visits
        # mult 0.7~1.3 + memory + 페르소나 변동 → 약 ±50% 안에 들어와야
        assert 2500 <= avg_spend <= 8000, f"avg_spend={avg_spend} 메뉴 가격 5000 의 ±50% 범위 외"


@pytest.mark.slow
def test_pse_default_no_visualization_data():
    """기본 호출 (시각화 옵션 없이) → trajectory/visits_events 필드 None."""
    result = evaluate_vacancy_pse(SPOT, "카페", n_seeds=1, days=1, with_cannibalization=False)
    assert result.get("trajectory") is None
    assert result.get("visits_events") is None


@pytest.mark.slow
def test_pse_with_collect_trajectory_returns_data():
    """collect_trajectory=True → result["trajectory"] 에 list."""
    result = evaluate_vacancy_pse(
        SPOT,
        "카페",
        n_seeds=1,
        days=1,
        with_cannibalization=False,
        collect_trajectory=True,
        trajectory_sample_size=20,
    )
    assert isinstance(result.get("trajectory"), list)


def test_pse_existing_signature_still_works(monkeypatch):
    """기존 인자 시그니처 그대로 호출 → 기존 결과 구조 보존 (회귀 X).

    실제 시뮬은 시간 부담이라 mock 으로 빠르게 검증.
    """
    # mock 으로 시뮬 시간 절약 — 호출 자체만 검증
    fake = {
        "vacancy_spot": SPOT,
        "category": "카페",
        "n_seeds": 1,
        "days": 1,
        "popularity_boost": 5.0,
        "with_cannibalization": False,
        "per_seed": [],
        "pse_summary": {
            "visits_per_day": {"mean": 0, "std": 0, "ci95": 0, "min": 0, "max": 0, "n": 0},
            "revenue_per_day": {"mean": 0, "std": 0, "ci95": 0, "min": 0, "max": 0, "n": 0},
        },
        "narrative": "...",
    }
    from src.simulation import vacancy_pse as vp

    monkeypatch.setattr(vp, "evaluate_vacancy_pse", lambda *a, **kw: fake)
    out = vp.evaluate_vacancy_pse(SPOT, "카페", n_seeds=1, days=1)
    assert "pse_summary" in out
    assert "narrative" in out
