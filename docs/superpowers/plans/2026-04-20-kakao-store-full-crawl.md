# Kakao Store 전수 수집 파이프라인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 카카오 로컬 API를 그리드 기반 카테고리 검색으로 전환해 마포구 음식점(FD6)+카페(CE7) 전수 수집, 10개 세부 카테고리 자동 분류 후 `kakao_store`에 UPSERT 적재.

**Architecture:** 500m 그리드 분할 → FD6/CE7 category_group_code 검색 → 45건 초과 셀 adaptive 4분할 → `category_name` prefix 매칭으로 10개 카테고리 분류 → brand_name은 기존 `NORMALIZE_RULES` 매칭된 경우만 채움 → `ON CONFLICT (kakao_id) DO UPDATE`로 UPSERT (기존 `kakao_store_hours` FK 보존).

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 (psycopg2 on_conflict), Alembic, pandas, urllib, pytest (pytest-mock via `unittest.mock`).

**Spec:** `docs/superpowers/specs/2026-04-20-kakao-store-full-crawl-design.md`

---

## File Structure

- **Create:** `backend/alembic/versions/7a2b9e4d6f18_add_is_franchise_to_kakao_store.py` — 스키마 마이그레이션
- **Modify:** `backend/src/database/models.py:441-462` — `KakaoStore` 모델에 `is_franchise` 추가, `brand_name` nullable
- **Modify:** `data/pipeline/collect_kakao_stores.py` — 신규 함수 (`generate_grid`, `search_category`, `collect_cell`, `classify_category`, `upsert_stores`) + `--mode=brands|categories` CLI 플래그
- **Create:** `tests/test_kakao_crawl.py` — 단위 테스트 (grid/classifier/collect_cell mocked)

---

### Task 1: Alembic 마이그레이션 + 모델 업데이트

**Files:**
- Create: `backend/alembic/versions/7a2b9e4d6f18_add_is_franchise_to_kakao_store.py`
- Modify: `backend/src/database/models.py:441-462`

- [ ] **Step 1: 마이그레이션 파일 생성**

Create `backend/alembic/versions/7a2b9e4d6f18_add_is_franchise_to_kakao_store.py`:

```python
"""add is_franchise to kakao_store and make brand_name nullable

개인 점포까지 포함 전수 수집을 위해 is_franchise 컬럼 추가.
brand_name은 NORMALIZE_RULES 매칭된 경우만 채우도록 nullable화.

Revision ID: 7a2b9e4d6f18
Revises: b2d4e8f1c7a3
Create Date: 2026-04-20 10:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "7a2b9e4d6f18"
down_revision: Union[str, Sequence[str], None] = "b2d4e8f1c7a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(table, schema="public"):
        return False
    cols = sa.inspect(bind).get_columns(table, schema="public")
    return any(c["name"] == col for c in cols)


def upgrade() -> None:
    if not _has_column("kakao_store", "is_franchise"):
        op.add_column(
            "kakao_store",
            sa.Column(
                "is_franchise",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
                comment="프랜차이즈 여부 (NORMALIZE_RULES 매칭 결과)",
            ),
        )
        op.create_index(
            "ix_kakao_store_is_franchise",
            "kakao_store",
            ["is_franchise"],
        )

    op.alter_column(
        "kakao_store",
        "brand_name",
        existing_type=sa.String(100),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "kakao_store",
        "brand_name",
        existing_type=sa.String(100),
        nullable=False,
    )
    op.drop_index("ix_kakao_store_is_franchise", table_name="kakao_store")
    op.drop_column("kakao_store", "is_franchise")
```

- [ ] **Step 2: models.py 업데이트**

Modify `backend/src/database/models.py` lines 441-462, replace the `KakaoStore` class body:

```python
class KakaoStore(Base):
    """카카오 로컬 API 기반 실시간 점포 데이터 — 마포구 전수 (프랜차이즈 + 개인)"""

    __tablename__ = "kakao_store"

    kakao_id = Column(String(20), primary_key=True, comment="카카오 장소 ID")
    place_name = Column(String(200), comment="장소명 (점포명)")
    brand_name = Column(
        String(100),
        index=True,
        nullable=True,
        comment="정규화된 브랜드명 (프랜차이즈만, 개인 점포는 NULL)",
    )
    category = Column(String(30), index=True, comment="10대 업종 카테고리 + '기타'")
    category_detail = Column(String(200), comment="카카오 카테고리 상세 (category_name)")
    address = Column(Text, comment="지번 주소")
    road_address = Column(Text, comment="도로명 주소")
    dong_name = Column(String(20), index=True, comment="행정동명")
    lat = Column(Float, comment="위도")
    lon = Column(Float, comment="경도")
    phone = Column(String(20), comment="전화번호")
    place_url = Column(Text, comment="카카오맵 URL")
    is_franchise = Column(
        Boolean,
        nullable=False,
        server_default=sa.false(),
        index=True,
        comment="프랜차이즈 여부",
    )
    collected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="수집 일시",
    )
```

Verify `Boolean` is imported at top of models.py. If not, add to the existing `from sqlalchemy import ...` line.

- [ ] **Step 3: 마이그레이션 적용 (로컬 DB)**

Run: `cd backend && alembic upgrade head`
Expected output: `INFO  [alembic.runtime.migration] Running upgrade b2d4e8f1c7a3 -> 7a2b9e4d6f18`

Verify: `psql $POSTGRES_URL -c "\d kakao_store" | grep -E "is_franchise|brand_name"`
Expected:
```
brand_name      | character varying(100)   |           |          |
is_franchise    | boolean                  |           | not null | false
```

- [ ] **Step 4: 커밋**

```bash
git add backend/alembic/versions/7a2b9e4d6f18_add_is_franchise_to_kakao_store.py backend/src/database/models.py
git commit -m "feat(db): kakao_store에 is_franchise 추가, brand_name nullable화"
```

---

### Task 2: Grid Generator (generate_grid)

**Files:**
- Modify: `data/pipeline/collect_kakao_stores.py` (add `generate_grid` function)
- Create: `tests/test_kakao_crawl.py`

- [ ] **Step 1: 실패 테스트 작성**

Create `tests/test_kakao_crawl.py`:

```python
"""data/pipeline/collect_kakao_stores.py 단위 테스트"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "data" / "pipeline"),
)

from collect_kakao_stores import generate_grid  # noqa: E402


def test_generate_grid_exact_division():
    """bbox가 셀 크기로 정확히 나눠지면 정사각 개수의 셀 반환."""
    # 마포 좌하단에서 ~1km × ~1km 영역, 500m 셀 → 2×2=4셀
    cells = generate_grid((126.88, 37.53, 126.89, 37.54), cell_m=500)
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
```

- [ ] **Step 2: 실패 확인**

Run: `cd "C:/Users/804/Documents/final project" && pytest tests/test_kakao_crawl.py -v`
Expected: `ImportError: cannot import name 'generate_grid'`

- [ ] **Step 3: generate_grid 구현**

In `data/pipeline/collect_kakao_stores.py`, add after the `MAPO_RECT` constant (around line 36):

```python
# 위도 1도 ≈ 111km (고정). 경도 1도 ≈ 111km × cos(lat) — 마포(~37.56°)에서 ≈ 88km.
_LAT_M_PER_DEG = 111_000.0
_LON_M_PER_DEG_MAPO = 88_000.0  # cos(37.56°) × 111000


def generate_grid(
    bbox: tuple[float, float, float, float],
    cell_m: int = 500,
) -> list[tuple[float, float, float, float]]:
    """bbox(west, south, east, north)를 cell_m 미터 격자로 분할.

    반환값: [(w, s, e, n), ...] 리스트. 경계가 딱 떨어지지 않으면 마지막 셀이 더 작다.
    """
    west, south, east, north = bbox
    lat_step = cell_m / _LAT_M_PER_DEG
    lon_step = cell_m / _LON_M_PER_DEG_MAPO

    cells: list[tuple[float, float, float, float]] = []
    lat = south
    while lat < north:
        lon = west
        next_lat = min(lat + lat_step, north)
        while lon < east:
            next_lon = min(lon + lon_step, east)
            cells.append((lon, lat, next_lon, next_lat))
            lon = next_lon
        lat = next_lat
    return cells
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd "C:/Users/804/Documents/final project" && pytest tests/test_kakao_crawl.py -v`
Expected: 3 tests pass.

- [ ] **Step 5: 커밋**

```bash
git add data/pipeline/collect_kakao_stores.py tests/test_kakao_crawl.py
git commit -m "feat(kakao): bbox 그리드 분할 함수 generate_grid 추가"
```

---

### Task 3: Category Classifier (classify_category)

**Files:**
- Modify: `data/pipeline/collect_kakao_stores.py` (add `classify_category`)
- Modify: `tests/test_kakao_crawl.py` (add tests)

- [ ] **Step 1: 실패 테스트 작성**

Append to `tests/test_kakao_crawl.py`:

```python
from collect_kakao_stores import classify_category  # noqa: E402


def test_classify_korean():
    assert classify_category("음식점 > 한식 > 국밥") == "한식음식점"
    assert classify_category("음식점 > 한식") == "한식음식점"


def test_classify_chinese():
    assert classify_category("음식점 > 중식 > 짜장면") == "중식음식점"


def test_classify_japanese():
    assert classify_category("음식점 > 일식 > 돈까스") == "일식음식점"


def test_classify_western():
    assert classify_category("음식점 > 양식 > 이탈리안") == "양식음식점"


def test_classify_cafe():
    assert classify_category("카페 > 커피전문점 > 스타벅스") == "커피-음료"
    assert classify_category("카페") == "커피-음료"


def test_classify_chicken():
    assert classify_category("음식점 > 치킨 > BBQ치킨") == "치킨전문점"


def test_classify_snack():
    assert classify_category("음식점 > 분식 > 떡볶이") == "분식전문점"


def test_classify_bakery():
    assert classify_category("음식점 > 제과,베이커리 > 파리바게뜨") == "제과점"


def test_classify_fastfood():
    assert classify_category("음식점 > 패스트푸드 > 햄버거") == "패스트푸드점"


def test_classify_pub():
    assert classify_category("음식점 > 술집 > 호프") == "호프-간이주점"


def test_classify_etc():
    assert classify_category("음식점 > 도시락") == "기타"
    assert classify_category("음식점 > 간식 > 토스트") == "기타"
    assert classify_category("") == "기타"
    assert classify_category("음식점") == "기타"
```

- [ ] **Step 2: 실패 확인**

Run: `cd "C:/Users/804/Documents/final project" && pytest tests/test_kakao_crawl.py::test_classify_korean -v`
Expected: `ImportError: cannot import name 'classify_category'`

- [ ] **Step 3: classify_category 구현**

In `data/pipeline/collect_kakao_stores.py`, add after `generate_grid`:

```python
# category_name prefix → 프로젝트 카테고리 매핑
_CATEGORY_PREFIX_MAP: list[tuple[str, str]] = [
    ("음식점 > 한식", "한식음식점"),
    ("음식점 > 중식", "중식음식점"),
    ("음식점 > 일식", "일식음식점"),
    ("음식점 > 양식", "양식음식점"),
    ("음식점 > 치킨", "치킨전문점"),
    ("음식점 > 분식", "분식전문점"),
    ("음식점 > 패스트푸드", "패스트푸드점"),
    ("음식점 > 제과", "제과점"),  # "제과,베이커리" 포함
    ("음식점 > 술집", "호프-간이주점"),
    ("카페", "커피-음료"),
]


def classify_category(category_name: str) -> str:
    """카카오 category_name → 프로젝트 10개 카테고리 + '기타'."""
    if not category_name:
        return "기타"
    for prefix, label in _CATEGORY_PREFIX_MAP:
        if category_name.startswith(prefix):
            return label
    return "기타"
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd "C:/Users/804/Documents/final project" && pytest tests/test_kakao_crawl.py -v`
Expected: 모든 분류 테스트 통과.

- [ ] **Step 5: 커밋**

```bash
git add data/pipeline/collect_kakao_stores.py tests/test_kakao_crawl.py
git commit -m "feat(kakao): category_name → 10개 카테고리 분류 classify_category 추가"
```

---

### Task 4: Category API 클라이언트 (search_category)

**Files:**
- Modify: `data/pipeline/collect_kakao_stores.py` (add `search_category`)
- Modify: `tests/test_kakao_crawl.py` (add mock-based tests)

- [ ] **Step 1: 실패 테스트 작성**

Append to `tests/test_kakao_crawl.py`:

```python
import json
from unittest.mock import MagicMock, patch

from collect_kakao_stores import search_category  # noqa: E402


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
    mock_urlopen.return_value = _fake_response(
        [{"id": "1", "place_name": "a"}], is_end=False
    )
    docs, is_end = search_category("CE7", (126.88, 37.53, 126.89, 37.54))
    assert docs == [{"id": "1", "place_name": "a"}]
    assert is_end is False
```

- [ ] **Step 2: 실패 확인**

Run: `cd "C:/Users/804/Documents/final project" && pytest tests/test_kakao_crawl.py::test_search_category_builds_correct_url -v`
Expected: `ImportError: cannot import name 'search_category'`

- [ ] **Step 3: search_category 구현**

In `data/pipeline/collect_kakao_stores.py`, add after `classify_category`:

```python
def search_category(
    category_group_code: str,
    rect: tuple[float, float, float, float],
    page: int = 1,
) -> tuple[list[dict], bool]:
    """카카오 카테고리 검색 API. (documents, is_end) 반환."""
    rect_str = f"{rect[0]},{rect[1]},{rect[2]},{rect[3]}"
    params = urllib.parse.urlencode(
        {
            "category_group_code": category_group_code,
            "rect": rect_str,
            "size": 15,
            "page": page,
        }
    )
    url = f"https://dapi.kakao.com/v2/local/search/category.json?{params}"
    req = urllib.request.Request(
        url, headers={"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("documents", []), data.get("meta", {}).get("is_end", True)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd "C:/Users/804/Documents/final project" && pytest tests/test_kakao_crawl.py -v`
Expected: search_category 테스트 2개 통과.

- [ ] **Step 5: 커밋**

```bash
git add data/pipeline/collect_kakao_stores.py tests/test_kakao_crawl.py
git commit -m "feat(kakao): category_group_code 기반 검색 search_category 추가"
```

---

### Task 5: Adaptive Cell Collector (collect_cell)

**Files:**
- Modify: `data/pipeline/collect_kakao_stores.py` (add `collect_cell`)
- Modify: `tests/test_kakao_crawl.py`

- [ ] **Step 1: 실패 테스트 작성**

Append to `tests/test_kakao_crawl.py`:

```python
from collect_kakao_stores import collect_cell  # noqa: E402


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
    # 부모 45 + 자식 4 = 49 (중복은 kakao_id로 dedupe — 겹치지 않도록 분기했음)
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
```

- [ ] **Step 2: 실패 확인**

Run: `cd "C:/Users/804/Documents/final project" && pytest tests/test_kakao_crawl.py::test_collect_cell_single_page_stops_when_is_end -v`
Expected: `ImportError: cannot import name 'collect_cell'`

- [ ] **Step 3: collect_cell 구현**

In `data/pipeline/collect_kakao_stores.py`, add after `search_category`:

```python
MAX_PAGE = 3  # 카카오 API: page 1~3 (15 × 3 = 45건)


def _split_rect(
    rect: tuple[float, float, float, float],
) -> list[tuple[float, float, float, float]]:
    """bbox를 4분할 (남서/남동/북서/북동)."""
    w, s, e, n = rect
    mid_lon = (w + e) / 2
    mid_lat = (s + n) / 2
    return [
        (w, s, mid_lon, mid_lat),
        (mid_lon, s, e, mid_lat),
        (w, mid_lat, mid_lon, n),
        (mid_lon, mid_lat, e, n),
    ]


def collect_cell(
    category_group_code: str,
    rect: tuple[float, float, float, float],
    max_depth: int = 3,
    _depth: int = 0,
) -> list[dict]:
    """한 셀의 모든 문서 수집. page3까지도 is_end=False면 4분할 재귀."""
    docs: list[dict] = []
    reached_limit = False

    for page in range(1, MAX_PAGE + 1):
        batch, is_end = search_category(category_group_code, rect, page)
        docs.extend(batch)
        if is_end:
            break
        if page == MAX_PAGE:
            reached_limit = True
        time.sleep(0.05)

    if reached_limit and _depth < max_depth:
        for sub in _split_rect(rect):
            docs.extend(
                collect_cell(
                    category_group_code, sub, max_depth=max_depth, _depth=_depth + 1
                )
            )
    return docs
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd "C:/Users/804/Documents/final project" && pytest tests/test_kakao_crawl.py -v`
Expected: 모든 collect_cell 테스트 4개 통과.

- [ ] **Step 5: 커밋**

```bash
git add data/pipeline/collect_kakao_stores.py tests/test_kakao_crawl.py
git commit -m "feat(kakao): 45건 초과 시 adaptive 4분할하는 collect_cell 추가"
```

---

### Task 6: UPSERT Loader (upsert_stores)

**Files:**
- Modify: `data/pipeline/collect_kakao_stores.py` (add `upsert_stores`)

- [ ] **Step 1: upsert_stores 구현**

In `data/pipeline/collect_kakao_stores.py`, add after existing `load_to_db` (around line 392) — keep `load_to_db` for backward compatibility with `--mode=brands`, add new:

```python
UPSERT_SQL = text(
    """
    INSERT INTO kakao_store (
        kakao_id, place_name, brand_name, category, category_detail,
        address, road_address, dong_name, lat, lon, phone, place_url,
        is_franchise
    ) VALUES (
        :kakao_id, :place_name, :brand_name, :category, :category_detail,
        :address, :road_address, :dong_name, :lat, :lon, :phone, :place_url,
        :is_franchise
    )
    ON CONFLICT (kakao_id) DO UPDATE SET
        place_name = EXCLUDED.place_name,
        category = EXCLUDED.category,
        category_detail = EXCLUDED.category_detail,
        address = EXCLUDED.address,
        road_address = EXCLUDED.road_address,
        dong_name = EXCLUDED.dong_name,
        lat = EXCLUDED.lat,
        lon = EXCLUDED.lon,
        phone = EXCLUDED.phone,
        place_url = EXCLUDED.place_url,
        is_franchise = kakao_store.is_franchise OR EXCLUDED.is_franchise,
        brand_name = COALESCE(EXCLUDED.brand_name, kakao_store.brand_name),
        collected_at = NOW();
    """
)


def upsert_stores(df: pd.DataFrame, db_url: str, chunksize: int = 500) -> int:
    """DataFrame을 kakao_store에 UPSERT. 반환: 처리 행 수."""
    engine = create_engine(db_url)
    Base.metadata.create_all(engine, checkfirst=True)

    records = df.to_dict(orient="records")
    with engine.begin() as conn:
        for i in range(0, len(records), chunksize):
            conn.execute(UPSERT_SQL, records[i : i + chunksize])
    return len(records)
```

- [ ] **Step 2: Ruff 정렬**

Run: `ruff check --fix data/pipeline/collect_kakao_stores.py && ruff format data/pipeline/collect_kakao_stores.py`
Expected: clean output (or `N fixed`).

- [ ] **Step 3: 커밋**

```bash
git add data/pipeline/collect_kakao_stores.py
git commit -m "feat(kakao): ON CONFLICT 기반 UPSERT 함수 upsert_stores 추가"
```

---

### Task 7: CLI Wiring (--mode=categories)

**Files:**
- Modify: `data/pipeline/collect_kakao_stores.py` (`main()` + `collect_all_by_category()`)

- [ ] **Step 1: collect_all_by_category 구현**

In `data/pipeline/collect_kakao_stores.py`, add before `main()` (around line 411):

```python
# 음식점(FD6), 카페(CE7) 두 코드만 사용
CATEGORY_GROUP_CODES = ["FD6", "CE7"]


def _doc_to_row(doc: dict, category_group_code: str) -> dict | None:
    """카카오 document → kakao_store row dict. 마포 외면 None."""
    addr = doc.get("address_name", "")
    road = doc.get("road_address_name", "")
    if "마포구" not in addr and "마포구" not in road:
        return None

    place_name = doc["place_name"]
    category_name = doc.get("category_name", "")
    category = classify_category(category_name)

    # 브랜드 매칭 시도: NORMALIZE_RULES에 걸리는 경우만 is_franchise=True
    brand = None
    for pat, bname in NORMALIZE_RULES:
        if re.match(pat, place_name):
            brand = bname
            break

    return {
        "kakao_id": doc["id"],
        "place_name": place_name,
        "brand_name": brand,
        "category": category,
        "category_detail": category_name,
        "address": addr,
        "road_address": road,
        "dong_name": extract_dong(addr),
        "lat": float(doc["y"]),
        "lon": float(doc["x"]),
        "phone": doc.get("phone", ""),
        "place_url": doc.get("place_url", ""),
        "is_franchise": brand is not None,
    }


def collect_all_by_category(
    bbox: tuple[float, float, float, float] = None,
    cell_m: int = 500,
) -> pd.DataFrame:
    """그리드 × FD6/CE7로 전수 수집."""
    if bbox is None:
        parts = [float(x) for x in MAPO_RECT.split(",")]
        bbox = (parts[0], parts[1], parts[2], parts[3])

    cells = generate_grid(bbox, cell_m=cell_m)
    print(f"그리드: {len(cells)}셀 (bbox={bbox}, cell={cell_m}m)")

    seen: set[str] = set()
    rows: list[dict] = []
    for idx, cell in enumerate(cells, 1):
        for code in CATEGORY_GROUP_CODES:
            try:
                docs = collect_cell(code, cell)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{idx}/{len(cells)}] {code} 셀 실패 {cell}: {exc}")
                continue
            for doc in docs:
                kid = doc.get("id")
                if not kid or kid in seen:
                    continue
                row = _doc_to_row(doc, code)
                if row is None:
                    continue
                seen.add(kid)
                rows.append(row)
        if idx % 20 == 0:
            print(f"  진행 {idx}/{len(cells)} 셀, 누적 {len(rows)}건")

    df = pd.DataFrame(rows)
    print(f"\n총 {len(df)}건 수집 (마포 필터, dedupe 후)")
    return df
```

- [ ] **Step 2: main() 에 --mode 분기 추가**

Replace the existing `main()` function (around line 411-436) with:

```python
def main() -> None:
    parser = argparse.ArgumentParser(description="카카오 로컬 API → kakao_store 적재")
    parser.add_argument(
        "--mode",
        choices=["brands", "categories"],
        default="brands",
        help="brands=기존 150개 프랜차이즈 키워드, categories=FD6+CE7 전수",
    )
    parser.add_argument("--db-url", default=DB_URL)
    parser.add_argument("--csv-only", action="store_true", help="CSV만 저장")
    parser.add_argument("--cell-m", type=int, default=500, help="그리드 셀 크기(m)")
    args = parser.parse_args()

    if args.mode == "brands":
        print("=== 카카오 로컬 API 프랜차이즈 수집 시작 ===\n")
        df = collect_all()
        out_csv = OUT_CSV
    else:
        print("=== 카카오 로컬 API 전수 수집 (카테고리 모드) ===\n")
        df = collect_all_by_category(cell_m=args.cell_m)
        out_csv = OUT_CSV.with_name("kakao_store_full_mapo.csv")

    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\nCSV 저장: {out_csv}")

    if args.csv_only:
        return

    if args.mode == "brands":
        cnt = load_to_db(df, args.db_url)
        print(f"DB 적재 (TRUNCATE+INSERT): {cnt}건 → kakao_store")
    else:
        cnt = upsert_stores(df, args.db_url)
        print(f"DB 적재 (UPSERT): {cnt}건 → kakao_store")

    # 카테고리별 Top 3 (브랜드 모드일 때만 의미있음)
    if args.mode == "brands":
        print("\n=== 카테고리별 브랜드 Top 3 ===\n")
        for cat in BRANDS:
            subset = df[df["category"] == cat]
            top3 = subset["brand_name"].value_counts().head(3)
            print(f"  {cat}:")
            for rank, (brand, n) in enumerate(top3.items(), 1):
                print(f"    {rank}. {brand} : {n}개")
            print()
    else:
        print("\n=== 카테고리별 점포수 / 프랜차이즈 비율 ===\n")
        summary = (
            df.groupby("category")
            .agg(total=("kakao_id", "count"), franchise=("is_franchise", "sum"))
            .sort_values("total", ascending=False)
        )
        print(summary.to_string())
```

- [ ] **Step 3: Ruff 정렬**

Run: `ruff check --fix data/pipeline/collect_kakao_stores.py && ruff format data/pipeline/collect_kakao_stores.py`
Expected: clean output.

- [ ] **Step 4: CLI 동작 확인 (CSV only, 작은 bbox)**

Run: `python data/pipeline/collect_kakao_stores.py --mode=categories --csv-only --cell-m=500` — 이건 마포 전체라 오래 걸립니다. 먼저 단위 테스트만 확인:

Run: `cd "C:/Users/804/Documents/final project" && pytest tests/test_kakao_crawl.py -v`
Expected: 모든 테스트 통과 (신규 모듈 import 에러 없음).

- [ ] **Step 5: 커밋**

```bash
git add data/pipeline/collect_kakao_stores.py
git commit -m "feat(kakao): --mode=categories CLI 추가 (마포 전수 수집)"
```

---

### Task 8: 소규모 스모크 테스트 (합정동 bbox)

**Files:** 없음 (수동 검증)

- [ ] **Step 1: 작은 bbox로 CSV 모드 실행**

합정동 일대 bbox (≈ 500m × 500m, 약 1~2셀):

Run: `python data/pipeline/collect_kakao_stores.py --mode=categories --csv-only --cell-m=500`

하지만 위 명령은 마포 전체를 돈다. 한 번만 소규모 검증하려면 스크립트에 임시 `--bbox` 옵션이 필요하지만 본 작업 범위 밖. 대신 파이썬 REPL로 직접 호출:

```bash
python -c "
import sys; sys.path.insert(0, 'data/pipeline')
from collect_kakao_stores import collect_all_by_category
df = collect_all_by_category(bbox=(126.910, 37.549, 126.916, 37.553), cell_m=500)
print(df[['place_name','category','is_franchise','brand_name','lat','lon']].head(20))
print('total:', len(df))
"
```

Expected: 수 건~수십 건 출력. `category` 컬럼이 한식/중식/카페/기타 등으로 채워지고 일부는 `is_franchise=True, brand_name=<브랜드>`, 나머지는 `is_franchise=False, brand_name=None`.

- [ ] **Step 2: UPSERT 멱등성 확인 (DB)**

Run:
```bash
python -c "
import sys; sys.path.insert(0, 'data/pipeline')
from collect_kakao_stores import collect_all_by_category, upsert_stores, DB_URL
df = collect_all_by_category(bbox=(126.910, 37.549, 126.916, 37.553), cell_m=500)
n1 = upsert_stores(df, DB_URL)
n2 = upsert_stores(df, DB_URL)  # 두 번째 호출은 모두 UPDATE
print('upsert 1:', n1, 'upsert 2:', n2)
"
```
Expected: n1 == n2. DB에 에러 없음.

Verify: `psql $POSTGRES_URL -c "SELECT category, COUNT(*), COUNT(*) FILTER (WHERE is_franchise) AS franchise FROM kakao_store GROUP BY category ORDER BY 2 DESC;"`
Expected: 카테고리별 건수 분포가 출력되고, `is_franchise=true` 건수가 0 이상.

- [ ] **Step 3: 기존 `kakao_store_hours` FK 유지 확인**

Run: `psql $POSTGRES_URL -c "SELECT COUNT(*) FROM kakao_store_hours;"` 
Expected: UPSERT 전후로 동일 값 (영업시간 데이터 손실 없음).

- [ ] **Step 4: 결과 기록 커밋 (없으면 skip)**

스모크 단계에서 코드 수정 없었으면 커밋 생략. 만약 수정이 있었으면:
```bash
git add <수정파일>
git commit -m "fix(kakao): 스모크 테스트에서 발견한 <issue> 수정"
```

---

## Self-Review Notes

- ✅ Alembic 체인: `b2d4e8f1c7a3` → `7a2b9e4d6f18` (신규). idempotent `_has_column` 헬퍼 적용.
- ✅ `classify_category`: 10개 + "기타" 전부 테스트 커버.
- ✅ `collect_cell`: `_depth` 파라미터로 최대 깊이 제한, 테스트 4종으로 분기 전부 검증.
- ✅ UPSERT: `is_franchise`는 OR 머지 (브랜드 모드와 카테고리 모드 교차 실행 시 보존), `brand_name`은 COALESCE.
- ✅ 기존 `--mode=brands`(기본값) 동작 100% 보존.
- ✅ 실제 API 호출 없이 단위 테스트 완결 (mock 기반).

## Spec Coverage

| Spec 요구사항 | 구현 Task |
|---|---|
| 그리드 기반 카테고리 검색 | Task 2 (generate_grid), Task 5 (collect_cell) |
| category_name 10+1 분류 | Task 3 (classify_category) |
| is_franchise 컬럼 + brand_name nullable | Task 1 (migration + model) |
| UPSERT (FK 보존) | Task 6 (upsert_stores) |
| `--mode=categories` CLI | Task 7 (main 분기) |
| 검증 쿼리 | Task 8 (스모크) |
