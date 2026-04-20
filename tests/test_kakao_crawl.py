"""data/pipeline/collect_kakao_stores.py 단위 테스트"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "data" / "pipeline"),
)

import json
from unittest.mock import MagicMock, patch

from collect_kakao_stores import (  # noqa: E402
    classify_category,
    collect_cell,
    generate_grid,
    search_category,
)


def test_generate_grid_exact_division():
    """bbox가 셀 크기로 정확히 2×2로 나눠지는 케이스."""
    # 500m 기준: lat 스텝 ≈ 0.004504°, lon 스텝 ≈ 0.005682°
    # lat 0.009° (2 rows), lon 0.01° (2 cols) → 4셀
    cells = generate_grid((126.88, 37.53, 126.89, 37.539), cell_m=500)
    assert len(cells) == 4
    # 모든 셀은 (west, south, east, north) 순
    for w, s, e, n in cells:
        assert w < e and s < n


def test_generate_grid_covers_bbox():
    """생성된 셀들이 원본 bbox를 완전히 덮는다 (중복 허용, 누락 불가)."""
    cells = generate_grid((126.88, 37.53, 126.96, 37.59), cell_m=500)
    # 좌하단·우상단이 각각 최소 하나의 셀에 포함
    assert any(w <= 126.88 and s <= 37.53 for w, s, _, _ in cells)
    assert any(e >= 126.96 and n >= 37.59 for _, _, e, n in cells)


def test_generate_grid_mapo_size():
    """마포 전체 bbox를 500m로 나누면 150~250 셀 범위."""
    cells = generate_grid((126.88, 37.53, 126.96, 37.59), cell_m=500)
    assert 150 <= len(cells) <= 250


def test_classify_korean():
    assert classify_category("음식점 > 한식 > 국밥") == "한식음식점"
    assert classify_category("음식점 > 한식") == "한식음식점"
    # 도시락은 BRANDS 정의(한솥·본도시락)와 일치시켜 한식으로
    assert classify_category("음식점 > 도시락 > 한솥도시락") == "한식음식점"
    assert classify_category("음식점 > 도시락") == "한식음식점"


def test_classify_chinese():
    assert classify_category("음식점 > 중식 > 짜장면") == "중식음식점"


def test_classify_japanese():
    assert classify_category("음식점 > 일식 > 돈까스") == "일식음식점"


def test_classify_western():
    assert classify_category("음식점 > 양식 > 이탈리안") == "양식음식점"


def test_classify_cafe():
    # 실제 Kakao 포맷
    assert classify_category("음식점 > 카페 > 커피전문점 > 스타벅스") == "커피-음료"
    assert classify_category("음식점 > 카페") == "커피-음료"
    # fallback 포맷
    assert classify_category("카페 > 커피전문점 > 스타벅스") == "커피-음료"
    assert classify_category("카페") == "커피-음료"


def test_classify_chicken():
    assert classify_category("음식점 > 치킨 > BBQ치킨") == "치킨전문점"


def test_classify_snack():
    assert classify_category("음식점 > 분식 > 떡볶이") == "분식전문점"


def test_classify_bakery():
    # 실제 Kakao 포맷: "음식점 > 간식 > 제과,베이커리"
    assert classify_category("음식점 > 간식 > 제과,베이커리 > 파리바게뜨") == "제과점"
    assert classify_category("음식점 > 간식 > 제과,베이커리") == "제과점"
    # fallback
    assert classify_category("음식점 > 제과,베이커리 > 파리바게뜨") == "제과점"


def test_classify_fastfood():
    assert classify_category("음식점 > 패스트푸드 > 햄버거") == "패스트푸드점"


def test_classify_pub():
    assert classify_category("음식점 > 술집 > 호프") == "호프-간이주점"


def test_classify_etc():
    assert classify_category("음식점 > 간식 > 토스트") == "기타"
    assert classify_category("음식점 > 아시아음식 > 베트남음식") == "기타"
    assert classify_category("") == "기타"
    assert classify_category("음식점") == "기타"


def _fake_response(documents: list[dict], is_end: bool = True) -> MagicMock:
    payload = json.dumps({"documents": documents, "meta": {"is_end": is_end}}).encode()
    resp = MagicMock()
    resp.read.return_value = payload
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, *a: None
    return resp


@patch("collect_kakao_stores.urllib.request.urlopen")
def test_search_category_builds_correct_url(mock_urlopen):
    mock_urlopen.return_value = _fake_response([])
    search_category("FD6", (126.88, 37.53, 126.89, 37.54), page=2)

    req = mock_urlopen.call_args[0][0]
    url = req.full_url
    assert "category.json" in url
    assert "category_group_code=FD6" in url
    assert "rect=126.88%2C37.53%2C126.89%2C37.54" in url
    assert "page=2" in url
    assert req.headers["Authorization"].startswith("KakaoAK ")


@patch("collect_kakao_stores.urllib.request.urlopen")
def test_search_category_returns_documents_and_is_end(mock_urlopen):
    mock_urlopen.return_value = _fake_response([{"id": "1", "place_name": "a"}], is_end=False)
    docs, is_end = search_category("CE7", (126.88, 37.53, 126.89, 37.54))
    assert docs == [{"id": "1", "place_name": "a"}]
    assert is_end is False


def _fake_doc(i: int) -> dict:
    return {
        "id": str(i),
        "place_name": f"가게{i}",
        "category_name": "음식점 > 한식 > 국밥",
        "address_name": "서울 마포구 공덕동 123",
        "road_address_name": "서울 마포구 공덕로 1",
        "x": "126.95",
        "y": "37.55",
        "phone": "02-0000-0000",
        "place_url": "http://kakao.example/1",
    }


@patch("collect_kakao_stores.search_category")
def test_collect_cell_single_page_stops_when_is_end(mock_search):
    mock_search.return_value = ([_fake_doc(1), _fake_doc(2)], True)
    result = collect_cell("FD6", (126.88, 37.53, 126.89, 37.54))
    assert len(result) == 2
    assert mock_search.call_count == 1


@patch("collect_kakao_stores.search_category")
def test_collect_cell_walks_pages_until_is_end(mock_search):
    # page1: 15건 !is_end, page2: 15건 !is_end, page3: 10건 is_end
    mock_search.side_effect = [
        ([_fake_doc(i) for i in range(15)], False),
        ([_fake_doc(i) for i in range(15, 30)], False),
        ([_fake_doc(i) for i in range(30, 40)], True),
    ]
    result = collect_cell("FD6", (126.88, 37.53, 126.89, 37.54))
    assert len(result) == 40
    assert mock_search.call_count == 3


@patch("collect_kakao_stores.search_category")
def test_collect_cell_subdivides_when_page3_not_is_end(mock_search):
    # 부모 셀 page1~3 모두 15건 && is_end=False → 4분할 재귀.
    # 자식 셀들은 모두 1건씩, is_end=True.
    parent_pages = [
        ([_fake_doc(i) for i in range(15)], False),
        ([_fake_doc(i) for i in range(15, 30)], False),
        ([_fake_doc(i) for i in range(30, 45)], False),
    ]
    child_cells = [([_fake_doc(100 + i)], True) for i in range(4)]
    mock_search.side_effect = parent_pages + child_cells

    result = collect_cell("FD6", (126.88, 37.53, 126.89, 37.54), max_depth=1)
    # 부모 45 + 자식 4 = 49
    assert len(result) == 49
    # 3 (parent pages) + 4 (children) = 7 calls
    assert mock_search.call_count == 7


@patch("collect_kakao_stores.search_category")
def test_collect_cell_honors_max_depth(mock_search):
    # max_depth=0 에서 page3까지 차면 더 안 쪼갠다
    mock_search.side_effect = [
        ([_fake_doc(i) for i in range(15)], False),
        ([_fake_doc(i) for i in range(15, 30)], False),
        ([_fake_doc(i) for i in range(30, 45)], False),
    ]
    result = collect_cell("FD6", (126.88, 37.53, 126.89, 37.54), max_depth=0)
    assert len(result) == 45
    assert mock_search.call_count == 3
