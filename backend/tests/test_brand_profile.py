"""brand_profile FTC 벤치마크 조회 테스트 (실 DB 필요)."""

from __future__ import annotations

import pytest

from src.services.brand_profile import (
    DEFAULT_YEAR,
    get_brand_benchmark,
    get_industry_peer_brands,
)


class TestGetBrandBenchmark:
    """2026-04-20 실측 FTC 2024 공시 데이터 기준."""

    def test_ediya_registered(self):
        """이디야커피 — FTC 등록, 2,805개 가맹점."""
        b = get_brand_benchmark("이디야커피")
        assert b["benchmark_available"] is True
        assert b["franchise_count_national"] == 2805
        # 195287 천원 = 195,287,000원
        assert b["avg_sales_per_store"] == 195_287_000
        assert b["industry_medium"] == "커피"
        assert b["reference_year"] == DEFAULT_YEAR

    def test_baekdabang_registered(self):
        """빽다방 — 1,449개, 3.19억."""
        b = get_brand_benchmark("빽다방")
        assert b["benchmark_available"] is True
        assert b["franchise_count_national"] == 1449
        assert b["avg_sales_per_store"] == 319_087_000
        assert b["industry_medium"] == "커피"
        # 폐업률: 20/1449 = 0.0138
        assert b["closure_rate"] == pytest.approx(0.0138, abs=0.001)

    def test_kyochon_registered(self):
        """교촌치킨 — 1,377개, 6.94억, 치킨."""
        b = get_brand_benchmark("교촌치킨")
        assert b["benchmark_available"] is True
        assert b["franchise_count_national"] == 1377
        assert b["avg_sales_per_store"] == 694_300_000
        assert b["industry_medium"] == "치킨"

    def test_momstouch_registered(self):
        """맘스터치 — 1,409개, 패스트푸드."""
        b = get_brand_benchmark("맘스터치")
        assert b["benchmark_available"] is True
        assert b["industry_medium"] == "패스트푸드"

    def test_starbucks_not_registered(self):
        """스타벅스 — 직영 체제로 FTC 미등재."""
        b = get_brand_benchmark("스타벅스")
        assert b["benchmark_available"] is False
        assert "미등재" in b["reason"]
        assert b["reference_year"] == DEFAULT_YEAR

    def test_nonexistent_brand(self):
        b = get_brand_benchmark("절대존재하지않는브랜드XYZ")
        assert b["benchmark_available"] is False


class TestGetIndustryPeerBrands:
    def test_coffee_peers_top5(self):
        """커피 업종 상위 5개 — 이디야커피 1위."""
        peers = get_industry_peer_brands("커피", top_n=5)
        assert len(peers) == 5
        # 가맹점 수 내림차순
        counts = [p["franchise_count"] for p in peers]
        assert counts == sorted(counts, reverse=True)
        # 이디야커피가 최상위
        assert peers[0]["brand_name"] == "이디야커피"
        assert peers[0]["franchise_count"] == 2805

    def test_chicken_peers(self):
        """치킨 업종 — BBQ 상위권."""
        peers = get_industry_peer_brands("치킨", top_n=3)
        assert len(peers) == 3
        brand_names = [p["brand_name"] for p in peers]
        assert "BBQ" in brand_names or "교촌치킨" in brand_names

    def test_unknown_industry_empty(self):
        peers = get_industry_peer_brands("존재하지않는업종XYZ", top_n=5)
        assert peers == []

    def test_peer_schema(self):
        peers = get_industry_peer_brands("커피", top_n=1)
        assert len(peers) == 1
        keys = {"brand_name", "franchise_count", "avg_sales", "closure_rate"}
        assert keys.issubset(peers[0].keys())
        # avg_sales 가 원 단위 (천원 × 1000)
        assert peers[0]["avg_sales"] is None or peers[0]["avg_sales"] > 1_000_000
