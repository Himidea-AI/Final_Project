"""brand_menu_loader 단위 테스트."""

from unittest.mock import patch

import pytest

from src.services.brand_menu_loader import (
    BrandMenuEmptyError,
    BrandNotFoundError,
    load_brand_menu_items,
)


class TestLoadBrandMenuItems:
    @patch("src.services.brand_menu_loader.get_all_mapo_stores_by_brand")
    @patch("src.services.brand_menu_loader._fetch_menu_items_from_db")
    def test_load_returns_menu_list(self, mock_fetch, mock_stores):
        """정상 — 마포 이디야 매장 5개, 메뉴 통합 list 반환."""
        mock_stores.return_value = [{"kakao_id": "k1"}, {"kakao_id": "k2"}]
        mock_fetch.return_value = [
            {"name": "아메리카노", "price": 4500},
            {"name": "라떼", "price": 5000},
        ]
        load_brand_menu_items.cache_clear()
        result = load_brand_menu_items("이디야")
        assert len(result) == 2
        assert all("name" in m and "price" in m for m in result)
        assert all(m["price"] > 0 for m in result)

    @patch("src.services.brand_menu_loader.get_all_mapo_stores_by_brand")
    def test_brand_not_in_mapo_raises(self, mock_stores):
        """마포에 매장 0개 → BrandNotFoundError."""
        mock_stores.return_value = []
        load_brand_menu_items.cache_clear()
        with pytest.raises(BrandNotFoundError, match="스타벅스"):
            load_brand_menu_items("스타벅스")

    @patch("src.services.brand_menu_loader.get_all_mapo_stores_by_brand")
    @patch("src.services.brand_menu_loader._fetch_menu_items_from_db")
    def test_brand_with_no_menu_raises(self, mock_fetch, mock_stores):
        """매장 N≥1 but 메뉴 0건 → BrandMenuEmptyError."""
        mock_stores.return_value = [{"kakao_id": "k1"}]
        mock_fetch.return_value = []
        load_brand_menu_items.cache_clear()
        with pytest.raises(BrandMenuEmptyError, match="신규브랜드"):
            load_brand_menu_items("신규브랜드")

    @patch("src.services.brand_menu_loader.get_all_mapo_stores_by_brand")
    @patch("src.services.brand_menu_loader._fetch_menu_items_from_db")
    def test_caching_single_db_call(self, mock_fetch, mock_stores):
        """같은 brand_name 두 번 호출 → DB 1회만 (lru_cache)."""
        mock_stores.return_value = [{"kakao_id": "k1"}]
        mock_fetch.return_value = [{"name": "라떼", "price": 5000}]
        load_brand_menu_items.cache_clear()
        load_brand_menu_items("이디야")
        load_brand_menu_items("이디야")
        assert mock_stores.call_count == 1
        assert mock_fetch.call_count == 1
