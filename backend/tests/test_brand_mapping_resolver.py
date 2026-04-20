"""brand_mapping_resolver 유닛/통합 테스트."""

from __future__ import annotations

import pytest

from src.services.brand_mapping_resolver import (
    BRAND_ALIASES,
    get_all_mapo_stores_by_brand,
    list_known_brands,
    resolve_brand_name,
)


class TestResolveBrandName:
    """resolve_brand_name — 순수 함수, DB 무관."""

    def test_standard_name_returns_self(self):
        assert resolve_brand_name("이디야커피") == "이디야커피"
        assert resolve_brand_name("빽다방") == "빽다방"

    def test_alias_resolves_to_standard(self):
        assert resolve_brand_name("이디야") == "이디야커피"
        assert resolve_brand_name("EDIYA") == "이디야커피"
        assert resolve_brand_name("백다방") == "빽다방"
        assert resolve_brand_name("교촌") == "교촌치킨"

    def test_case_insensitive(self):
        assert resolve_brand_name("starbucks") == "스타벅스"
        assert resolve_brand_name("Starbucks") == "스타벅스"
        assert resolve_brand_name("STARBUCKS") == "스타벅스"

    def test_spaces_and_parens_normalized(self):
        assert resolve_brand_name("Burger King") == "버거킹"
        assert resolve_brand_name("버거킹(Burger King)") == "버거킹"
        assert resolve_brand_name("A TWOSOME PLACE") == "투썸플레이스"

    def test_partial_match_in_place_name(self):
        assert resolve_brand_name("이디야커피 마포공덕역점") == "이디야커피"
        assert resolve_brand_name("파리바게뜨 광흥창역점") == "파리바게뜨"
        assert resolve_brand_name("맘스터치 홍대점") == "맘스터치"

    def test_unknown_brand_returns_none(self):
        assert resolve_brand_name("어서오십시오카페") is None
        assert resolve_brand_name("개인소규모식당") is None

    def test_none_or_empty_returns_none(self):
        assert resolve_brand_name(None) is None
        assert resolve_brand_name("") is None


class TestBrandAliases:
    """BRAND_ALIASES 무결성."""

    def test_standards_are_unique(self):
        assert len(BRAND_ALIASES) == len(set(BRAND_ALIASES))

    def test_no_alias_equals_other_standard(self):
        standards = set(BRAND_ALIASES.keys())
        for std, aliases in BRAND_ALIASES.items():
            for alias in aliases:
                assert alias not in standards - {std}, f"alias '{alias}' of '{std}' collides with another standard"

    def test_list_known_brands_returns_all(self):
        known = list_known_brands()
        assert "이디야커피" in known
        assert "빽다방" in known
        assert "맘스터치" in known
        assert len(known) == len(BRAND_ALIASES)


@pytest.mark.integration
class TestGetAllMapoStoresByBrand:
    """get_all_mapo_stores_by_brand — 실 DB 필요 (kakao_store)."""

    def test_ediya_returns_17_stores(self):
        """2026-04-20 실측: 이디야커피 마포 17개."""
        stores = get_all_mapo_stores_by_brand("이디야커피")
        assert len(stores) == 17
        for s in stores:
            assert s["lat"] is not None
            assert s["lon"] is not None
            assert s["dong_name"] is not None

    def test_megacoffee_returns_49_stores(self):
        """2026-04-20 실측: 메가MGC커피 마포 49개."""
        stores = get_all_mapo_stores_by_brand("메가MGC커피")
        assert len(stores) >= 45  # 데이터 추가 대비 여유

    def test_unknown_brand_returns_empty(self):
        stores = get_all_mapo_stores_by_brand("존재하지않는브랜드XYZ123")
        assert stores == []

    def test_store_schema(self):
        stores = get_all_mapo_stores_by_brand("빽다방")
        assert len(stores) > 0
        keys = {"kakao_id", "place_name", "brand_name", "lat", "lon", "dong_name", "address"}
        assert keys.issubset(stores[0].keys())
