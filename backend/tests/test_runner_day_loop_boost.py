"""runner day-loop 안 living_pop_daily_boost 갱신 동작."""

from src.simulation.world import World


def test_world_default_living_pop_empty():
    """기본 World 의 living_pop_daily_boost 빈 dict (회귀 보호)."""
    w = World()
    assert w.living_pop_daily_boost == {}


def test_runner_swaps_adstrd_boost_per_day_when_living_pop_set():
    """runner 가 매일 boost 를 swap 하는 helper 단위 동작.

    실제 day-loop 는 통합 테스트 (slow). 본 테스트는 helper 함수만 단위 검증.
    """
    from src.simulation.runner import _swap_dong_hour_boost_for_day

    living = {
        ("서교동", 14, 0): 1.5,
        ("서교동", 14, 1): 0.8,
    }
    fallback = {("서교동", 14, 1): 1.0}  # 정적 (요일 평균)

    # day_idx=0 → living 의 1.5
    out = _swap_dong_hour_boost_for_day(living, fallback, day_idx=0, weekday=1)
    assert out[("서교동", 14, 1)] == 1.5

    # day_idx=1 → living 의 0.8
    out = _swap_dong_hour_boost_for_day(living, fallback, day_idx=1, weekday=1)
    assert out[("서교동", 14, 1)] == 0.8

    # day_idx=2 (living 없음) → fallback
    out = _swap_dong_hour_boost_for_day(living, fallback, day_idx=2, weekday=1)
    assert out[("서교동", 14, 1)] == 1.0


def test_runner_swap_empty_living_returns_fallback():
    """living_pop_daily_boost 빈 dict → fallback 그대로 반환 (회귀 보호)."""
    from src.simulation.runner import _swap_dong_hour_boost_for_day

    fallback = {("서교동", 14, 1): 1.2}
    out = _swap_dong_hour_boost_for_day({}, fallback, day_idx=0, weekday=1)
    assert out is fallback  # 빈 dict 면 동일 객체 반환 (복사 비용 절감)
