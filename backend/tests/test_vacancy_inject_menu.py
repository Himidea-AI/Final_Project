"""vacancy_inject.inject_vacancy_as_store 의 menu_items 인자 동작."""

import pytest

from src.simulation.vacancy_inject import inject_vacancy_as_store
from src.simulation.world import World


@pytest.fixture
def world_with_dong():
    """동 1개만 있는 minimal World."""
    w = World()
    w.dongs = ["서교동"]
    return w


SPOT = {"dong": "서교동", "lat": 37.5544, "lon": 126.9220}


def test_inject_with_menu_items_sets_store_menu(world_with_dong):
    """menu_items 인자 → Store.menu_items 에 그대로 set."""
    menu = [{"name": "라떼", "price": 5000}, {"name": "아메리카노", "price": 4500}]
    vid = inject_vacancy_as_store(world_with_dong, SPOT, "카페", menu_items=menu)
    assert world_with_dong.stores[vid].menu_items == menu


def test_inject_without_menu_items_default_empty(world_with_dong):
    """menu_items=None (기본값) → Store.menu_items = [] (하위 호환성)."""
    vid = inject_vacancy_as_store(world_with_dong, SPOT, "카페")
    assert world_with_dong.stores[vid].menu_items == []


def test_inject_with_empty_menu_items(world_with_dong):
    """menu_items=[] 명시 전달 → 빈 list 그대로."""
    vid = inject_vacancy_as_store(world_with_dong, SPOT, "카페", menu_items=[])
    assert world_with_dong.stores[vid].menu_items == []
