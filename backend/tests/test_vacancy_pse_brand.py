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


def test_pse_existing_signature_preserves_old_kwargs():
    """기존 인자 (menu_items 등 새 인자 없이) 가 시그니처에 그대로 받아들여지는지 검증.

    inspect 로 시그니처를 확인 — TypeError 회귀를 빠르게 잡음.
    실제 시뮬 호출은 slow 테스트 (test_pse_with_menu_items_uses_menu_prices) 가 cover.
    """
    import inspect

    sig = inspect.signature(evaluate_vacancy_pse)
    params = sig.parameters

    # 기존 파라미터 보존
    for old in [
        "vacancy_spot",
        "category",
        "n_seeds",
        "days",
        "popularity_boost",
        "with_cannibalization",
        "pop_mix",
        "tier_dist",
        "cfg",
        "seeds",
        "verbose",
    ]:
        assert old in params, f"기존 파라미터 '{old}' 누락 — 회귀 의심"

    # 새 파라미터 추가 확인 (Task 4)
    for new in [
        "menu_items",
        "collect_trajectory",
        "trajectory_sample_size",
        "dump_visits",
        "use_dialog_templates",
        "enable_llm",
        "llm_tier_policy",
        "llm_max_tokens",
        "llm_call_interval",
    ]:
        assert new in params, f"새 파라미터 '{new}' 누락"

    # 새 파라미터 모두 default 가 있어야 (하위 호환성)
    for new in [
        "menu_items",
        "collect_trajectory",
        "trajectory_sample_size",
        "dump_visits",
        "use_dialog_templates",
        "enable_llm",
    ]:
        assert params[new].default is not inspect.Parameter.empty, (
            f"파라미터 '{new}' 가 default 없음 — 하위 호환성 깨짐"
        )
