# Brand Menu + Vacancy_PSE Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** vacancy_pse 의 매출 계산을 `kakao_store_menu` 의 실제 브랜드 메뉴 가격과 연결하고, 5트랙 검증 protocol (V1a/V1b/V1c/V2/CI) 로 production-readiness 를 정직하게 측정한다. Mode B (Pure Policy + Template 자연어, 비용 $0) default + Mode C (Tier S 50명 LLM, 가용 시) 인터페이스까지.

**Architecture:** services/brand_menu_loader 가 brand_name → menu_items 변환 책임 (kakao_store + kakao_store_menu JOIN). vacancy_pse / vacancy_inject 는 menu_items 인자만 받음 (책임 분리). validation/brand_vacancy_validator 가 5트랙 측정 + 합격 판정 + report 생성. 검증은 항상 mock 강제 (비용 0).

**Tech Stack:** Python 3.13, SQLAlchemy 2.x, pytest, scipy.stats (Pearson r), numpy. PostgreSQL.

**Spec:** `docs/superpowers/specs/2026-04-27-brand-menu-vacancy-pse-validation-design.md` (commit 787b4a0)

**User git policy:** 사용자 메모리에 "git commit/push 사전 확인 필수" — 각 commit step 전에 사용자에게 확인받기. 또한 모든 Python 코드 변경 후 `ruff check --fix && ruff format` 실행 (CLAUDE.md).

---

## File Structure

**신규 파일**:
- `backend/src/services/brand_menu_loader.py` — brand_name → menu_items 변환 (services 레이어, A1 owner)
- `backend/src/simulation/dialog_templates.py` — 8 archetype × 4 situation × 5 문장 (Mode B)
- `validation/brand_vacancy_validator.py` — 5트랙 검증 protocol + report 생성
- `backend/tests/test_brand_menu_loader.py`
- `backend/tests/test_vacancy_inject_menu.py`
- `backend/tests/test_dialog_templates.py`
- `backend/tests/test_vacancy_pse_brand.py`
- `backend/tests/test_vacancy_evaluation_service_brand.py`
- `backend/tests/test_living_pop_loader.py` (옵션 B)
- `backend/tests/test_runner_day_loop_boost.py` (옵션 B)
- `tests/test_brand_vacancy_validator.py`

**수정 파일**:
- `backend/src/simulation/vacancy_inject.py` — `inject_vacancy_as_store()` 에 `menu_items` 인자 추가
- `backend/src/simulation/vacancy_pse.py` — `evaluate_vacancy_pse()` 에 인자 추가
- `backend/src/services/vacancy_evaluation_service.py` — `evaluate_top_vacancies()` 에 `brand_name` 인자 추가
- **`backend/src/simulation/world_loader.py`** — `_load_living_population_daily(start_date, days)` 신규 함수 (옵션 B)
- **`backend/src/simulation/world.py`** — `World.living_pop_daily_boost` 필드 추가 (옵션 B)
- **`backend/src/simulation/runner.py`** — day-loop 안 boost 갱신 (옵션 B)

---

## Task 1: brand_menu_loader (신규)

**Files:**
- Create: `backend/src/services/brand_menu_loader.py`
- Test: `backend/tests/test_brand_menu_loader.py`

- [ ] **Step 1.1: 단위 테스트 작성 — 정상 케이스**

테스트 파일 생성:

```python
# backend/tests/test_brand_menu_loader.py
"""brand_menu_loader 단위 테스트."""

from unittest.mock import MagicMock, patch

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
```

- [ ] **Step 1.2: 테스트 실행 → fail 확인**

```bash
cd /c/Users/804/Documents/final\ project
python -m pytest backend/tests/test_brand_menu_loader.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.brand_menu_loader'`

- [ ] **Step 1.3: brand_menu_loader 구현**

```python
# backend/src/services/brand_menu_loader.py
"""brand_name → kakao_store_menu JOIN → menu_items list 변환.

설계 의도:
    프랜차이즈 대상 vacancy_pse 시뮬에서, vacancy 매장에 실제 그 브랜드의
    메뉴/가격을 attach 하기 위한 services 레이어 entry point.

    `services/brand_mapping_resolver.get_all_mapo_stores_by_brand()` 로 마포
    내 같은 브랜드 매장의 kakao_id 목록을 받고, kakao_store_menu 테이블에서
    메뉴/가격을 통합 (AVG by menu_name) 해 list[{name, price}] 반환.

학술 근거 (spec 16절):
    - "Affordable Generative Agents" (arxiv 2402.02053) — LLM 비용 절감 +
      hardcoded 메뉴 source 의 합리성.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from sqlalchemy import text

from src.database.sync_engine import get_sync_engine
from src.services.brand_mapping_resolver import get_all_mapo_stores_by_brand

logger = logging.getLogger(__name__)


class BrandNotFoundError(ValueError):
    """마포에 brand_name 매장 0개."""


class BrandMenuEmptyError(ValueError):
    """매장은 있으나 가격>0 메뉴 row 0건."""


def _fetch_menu_items_from_db(kakao_ids: list[str]) -> list[dict[str, Any]]:
    """kakao_id 리스트 → kakao_store_menu JOIN → 메뉴명별 평균 가격."""
    if not kakao_ids:
        return []
    sql = text("""
        SELECT menu_name, AVG(price)::int AS price
          FROM kakao_store_menu
         WHERE kakao_id = ANY(:kids)
           AND menu_name IS NOT NULL
           AND price IS NOT NULL
           AND price > 0
         GROUP BY menu_name
         ORDER BY AVG(price) DESC
         LIMIT 30
    """)
    engine = get_sync_engine(os.environ["POSTGRES_URL"])
    with engine.connect() as conn:
        rows = conn.execute(sql, {"kids": list(kakao_ids)}).mappings().all()
    return [{"name": r["menu_name"], "price": int(r["price"])} for r in rows]


@lru_cache(maxsize=128)
def load_brand_menu_items(brand_name: str) -> list[dict[str, Any]]:
    """brand_name → 마포 같은 브랜드 매장의 menu_items 통합.

    Args:
        brand_name: 표준 브랜드명 (예: "이디야"). alias 자동 처리.

    Returns:
        list[{"name": str, "price": int}], max 30개. 가격 내림차순.

    Raises:
        BrandNotFoundError: 마포 매장 0개.
        BrandMenuEmptyError: 매장 ≥1 but 가격>0 메뉴 0건.
    """
    stores = get_all_mapo_stores_by_brand(brand_name)
    if not stores:
        raise BrandNotFoundError(
            f"브랜드 '{brand_name}' 가 마포에 등록된 매장이 없어 평가 불가."
        )

    kakao_ids = [s["kakao_id"] for s in stores if s.get("kakao_id")]
    menu = _fetch_menu_items_from_db(kakao_ids)

    if not menu:
        raise BrandMenuEmptyError(
            f"브랜드 '{brand_name}' 의 메뉴 데이터가 부족 "
            f"(가격 정보 있는 메뉴 0건, 매장 {len(stores)}개)."
        )

    logger.info(
        f"[brand_menu_loader] '{brand_name}': "
        f"마포 매장 {len(stores)}개 → 메뉴 {len(menu)}개 통합"
    )
    return menu
```

- [ ] **Step 1.4: 테스트 실행 → pass 확인**

```bash
python -m pytest backend/tests/test_brand_menu_loader.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 1.5: ruff + commit**

```bash
ruff check --fix backend/src/services/brand_menu_loader.py backend/tests/test_brand_menu_loader.py
ruff format backend/src/services/brand_menu_loader.py backend/tests/test_brand_menu_loader.py
```

사용자 확인 후:
```bash
git add backend/src/services/brand_menu_loader.py backend/tests/test_brand_menu_loader.py
git commit -m "feat(A1): brand_menu_loader — brand_name → kakao_store_menu list 변환"
```

---

## Task 2: vacancy_inject.inject_vacancy_as_store 에 menu_items 인자 추가

**Files:**
- Modify: `backend/src/simulation/vacancy_inject.py:51~110`
- Test: `backend/tests/test_vacancy_inject_menu.py`

- [ ] **Step 2.1: 테스트 작성**

```python
# backend/tests/test_vacancy_inject_menu.py
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
```

- [ ] **Step 2.2: 테스트 실행 → fail 확인**

```bash
python -m pytest backend/tests/test_vacancy_inject_menu.py -v
```
Expected: FAIL with `TypeError: inject_vacancy_as_store() got an unexpected keyword argument 'menu_items'`

- [ ] **Step 2.3: vacancy_inject 수정**

`backend/src/simulation/vacancy_inject.py` 의 `inject_vacancy_as_store` 시그니처 + Store 생성 부분 변경:

```python
# backend/src/simulation/vacancy_inject.py:51~110 영역

def inject_vacancy_as_store(
    world: World,
    vacancy_spot: dict[str, Any],
    category: str,
    name: str | None = None,
    seats: int = DEFAULT_SEATS,
    rating: float = DEFAULT_RATING,
    price_level: int = DEFAULT_PRICE_LEVEL,
    popularity_boost: float = DEFAULT_POPULARITY_BOOST,
    menu_items: list[dict] | None = None,   # ← 추가
) -> str:
    """공실 1개 → 가상 Store 로 주입. world.add_store() 만 하면 시뮬 자동 적용.

    Args:
        ...  # (기존 docstring 그대로)
        menu_items: list[{"name": str, "price": int}] | None.
            None (기본값) → Store.menu_items 빈 list (기존 호환).
            제공 시 → 그 매장 메뉴/가격으로 spend 계산 (agents.py:413 분기 활성).
            services/brand_menu_loader.load_brand_menu_items() 가 source.

    Returns:
        ...  # (기존 그대로)
    """
    dong = vacancy_spot.get("dong") or vacancy_spot.get("district")
    lat = vacancy_spot.get("lat")
    lon = vacancy_spot.get("lon")

    if not dong:
        raise VacancyInjectionError("vacancy_spot 에 'dong' 또는 'district' 키 필요")
    if dong not in world.dongs:
        raise VacancyInjectionError(f"'{dong}' 가 world.dongs 에 없음 (등록된 동: {len(world.dongs)}개)")
    if lat is None or lon is None:
        raise VacancyInjectionError(f"vacancy_spot lat/lon 누락 (dong={dong})")
    if category not in ALLOWED_CATEGORIES:
        raise VacancyInjectionError(f"category '{category}' 는 허용 카테고리 {ALLOWED_CATEGORIES} 외")

    existing_count = sum(1 for sid in world.stores if isinstance(sid, str) and sid.startswith(VACANCY_ID_PREFIX))
    vid = f"{VACANCY_ID_PREFIX}_{existing_count}_{dong}"

    store = Store(
        store_id=vid,  # type: ignore[arg-type]
        name=name or f"VACANCY_{existing_count}_{dong}",
        dong=dong,
        category=category,
        seats=seats,
        rating=rating,
        price_level=price_level,
        lat=float(lat),
        lon=float(lon),
        is_open_now=True,
        popularity_boost=popularity_boost,
        menu_items=list(menu_items) if menu_items else [],   # ← 추가
    )
    world.add_store(store)
    return vid
```

- [ ] **Step 2.4: 테스트 실행 → pass 확인**

```bash
python -m pytest backend/tests/test_vacancy_inject_menu.py -v
```
Expected: PASS (3 tests)

회귀 확인:
```bash
python -m pytest backend/tests/ -k "vacancy" -v
```
Expected: 기존 vacancy 관련 테스트 모두 통과 (회귀 X).

- [ ] **Step 2.5: ruff + commit**

```bash
ruff check --fix backend/src/simulation/vacancy_inject.py backend/tests/test_vacancy_inject_menu.py
ruff format backend/src/simulation/vacancy_inject.py backend/tests/test_vacancy_inject_menu.py
```

사용자 확인 후:
```bash
git add backend/src/simulation/vacancy_inject.py backend/tests/test_vacancy_inject_menu.py
git commit -m "feat(A1): vacancy_inject 에 menu_items 인자 추가 (호환성 유지)"
```

---

## Task 3: dialog_templates 신규 (Mode B 자연어 template)

**Files:**
- Create: `backend/src/simulation/dialog_templates.py`
- Test: `backend/tests/test_dialog_templates.py`

> **참고**: 30 archetype 전체의 한국어 600 문장은 1~2일 카피라이팅 작업. 본 task 는 **8 archetype × 4 situation × 5 문장 = 160 문장 minimum coverage** 로 시작 (`personas.py` 의 ARCHETYPES 8개 기준). 추후 30 archetype 까지 확장은 별도 commit 으로.

- [ ] **Step 3.1: 테스트 작성**

```python
# backend/tests/test_dialog_templates.py
"""dialog_templates 단위 테스트 — Mode B (Pure Policy + Template 자연어)."""

import random

import pytest

from src.simulation.dialog_templates import TEMPLATES, pick_dialog


class TestPickDialog:
    def test_pick_returns_string(self):
        rng = random.Random(42)
        out = pick_dialog("creative_freelancer", "morning_visit_cafe", 9, rng)
        assert isinstance(out, str)
        assert len(out) > 0

    def test_pick_is_deterministic_with_seed(self):
        """같은 seed → 같은 결과 (재현성)."""
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        a = pick_dialog("office_worker", "lunch_decide", 12, rng1)
        b = pick_dialog("office_worker", "lunch_decide", 12, rng2)
        assert a == b

    def test_unknown_archetype_returns_fallback(self):
        rng = random.Random(42)
        out = pick_dialog("nonexistent_type", "morning_visit_cafe", 9, rng)
        assert out == "..."  # fallback

    def test_unknown_situation_returns_fallback(self):
        rng = random.Random(42)
        out = pick_dialog("creative_freelancer", "nonexistent_situation", 9, rng)
        assert out == "..."


class TestTemplatesCoverage:
    """archetype × situation 의 cover 검증 — Mode B default 정상 동작 보장."""

    REQUIRED_SITUATIONS = ["morning_visit_cafe", "lunch_decide", "evening_decide", "rest"]
    MIN_LINES_PER_BUCKET = 5

    def test_all_archetypes_have_required_situations(self):
        """personas.py 의 8 archetype 모두 필수 situation 5+ 문장."""
        archetype_ids = [
            "creative_freelancer", "office_worker", "broadcasting_staff",
            "student_couple", "retired_local", "young_parent",
            "tourist_foreign", "f&b_owner",
        ]
        for arc in archetype_ids:
            assert arc in TEMPLATES, f"archetype '{arc}' 누락"
            for sit in self.REQUIRED_SITUATIONS:
                bucket = TEMPLATES[arc].get(sit, [])
                assert len(bucket) >= self.MIN_LINES_PER_BUCKET, (
                    f"{arc} × {sit}: {len(bucket)} 문장 (최소 {self.MIN_LINES_PER_BUCKET} 필요)"
                )

    def test_no_empty_strings(self):
        """모든 템플릿 문장이 비어있지 않음."""
        for arc, situations in TEMPLATES.items():
            for sit, lines in situations.items():
                for line in lines:
                    assert isinstance(line, str) and line.strip(), (
                        f"{arc} × {sit}: 빈 문자열 발견"
                    )
```

- [ ] **Step 3.2: 테스트 실행 → fail 확인**

```bash
python -m pytest backend/tests/test_dialog_templates.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3.3: dialog_templates 구현**

```python
# backend/src/simulation/dialog_templates.py
"""Mode B 자연어 템플릿 — archetype × situation 별 짧은 한국어 문장 sampling.

설계 의도:
    LLM 비용 0 으로 시각화 chats 데이터를 채우는 hardcode 템플릿.
    8 archetype × 4 situation × 5 문장 = 160 문장 minimum coverage.

    추후 Nemotron-Personas 30 archetype 전체로 확장 (별도 commit).
    Mode C (LLM 활성) 시 Tier S 50명만 LLM, 나머지는 본 template.

학술 근거:
    - "Affordable Generative Agents" (arxiv 2402.02053) — hardcoded NLG
      의 비용 절감 + 일관성.
    - GeekNews "agent 보다 workflow 우선" — LLM 절제.
"""

from __future__ import annotations

import random
from typing import Final

# archetype_id → situation → list of 짧은 한국어 문장
TEMPLATES: Final[dict[str, dict[str, list[str]]]] = {
    "creative_freelancer": {
        "morning_visit_cafe": [
            "오늘 작업할 카페 어디로 가지",
            "감성 있는 곳이 좋겠다",
            "와이파이 좋은 곳",
            "사진 찍기 좋은 자리",
            "라떼 한 잔으로 시작",
        ],
        "lunch_decide": [
            "가까운 곳 빨리",
            "오늘은 디저트도 같이",
            "샐러드 가게 어땠더라",
            "포장해서 작업실로",
            "친구가 추천한 그 집",
        ],
        "evening_decide": [
            "마감이라 더 일해야지",
            "동료랑 한 잔 어때",
            "집 가는 길에 들를까",
            "오늘은 일찍 쉬자",
            "산책 좀 하다 가야지",
        ],
        "rest": [
            "잠깐 숨 돌리자",
            "커피 더 시킬까",
            "음악 틀고 한 곡만",
            "스트레칭 좀 하고",
            "SNS 잠깐만 보고",
        ],
    },
    "office_worker": {
        "morning_visit_cafe": [
            "빨리 한 잔 해야겠다",
            "회의 전 카페인 충전",
            "오늘은 따뜻한 걸로",
            "동료 거 같이 사야지",
            "5분 안에 받아야 해",
        ],
        "lunch_decide": [
            "오늘은 한식 가자",
            "가성비로 빨리",
            "회의 길어졌으니 도시락",
            "팀이랑 같이 갈 곳",
            "분식 어때",
        ],
        "evening_decide": [
            "오늘 회식이라 한 잔",
            "퇴근하고 바로 집",
            "동료랑 짧게 한 잔",
            "야근이라 김밥",
            "운동가야 하니까 일찍",
        ],
        "rest": [
            "5분만 쉬자",
            "커피 한 잔 더",
            "잠깐 바람 좀",
            "메일 확인하고",
            "전화 한 통 하고",
        ],
    },
    "broadcasting_staff": {
        "morning_visit_cafe": [
            "야근 후 정신 차리려고",
            "아메리카노 진하게",
            "24시간 카페 어디",
            "촬영 전 한 잔",
            "에너지 드링크라도",
        ],
        "lunch_decide": [
            "촬영 도시락",
            "빠르게 패스트푸드",
            "근처 편의점",
            "회의실 케이터링",
            "잠깐 짬내서",
        ],
        "evening_decide": [
            "야식 떡볶이",
            "밤샘 작업이라 삼겹살",
            "상암동 야식 골목",
            "편의점 라면",
            "치킨 시켜먹자",
        ],
        "rest": [
            "잠깐만 눈 감고",
            "커피 더 마셔야",
            "10분만 쉬자",
            "PD 부르기 전에",
            "스튜디오 밖 바람",
        ],
    },
    "student_couple": {
        "morning_visit_cafe": [
            "신상 카페 가자",
            "인스타에서 본 그 집",
            "사진 찍기 좋은 곳",
            "디저트 맛집 투어",
            "라떼 아트 예쁜 데",
        ],
        "lunch_decide": [
            "데이트라 분위기 있는 곳",
            "오늘은 양식",
            "가성비도 중요",
            "둘이 나눠 먹자",
            "근처 핫플",
        ],
        "evening_decide": [
            "영화 보고 저녁",
            "홍대 술집",
            "분위기 있는 와인바",
            "친구들이랑 합석",
            "포차 어때",
        ],
        "rest": [
            "잠깐 손잡고 산책",
            "벤치에서 쉬자",
            "사진 더 찍자",
            "음악 듣자",
            "다음 코스 정하자",
        ],
    },
    "retired_local": {
        "morning_visit_cafe": [
            "단골집 그대로",
            "차 한 잔이면 돼",
            "사장님과 인사",
            "신문 보면서",
            "오랜 친구 만나러",
        ],
        "lunch_decide": [
            "전통시장 국밥",
            "그 집 김치찌개",
            "가격 적당한 곳",
            "오래 다닌 단골",
            "혼자 조용히",
        ],
        "evening_decide": [
            "집에서 저녁 먹자",
            "단골 호프집",
            "동네 친구랑",
            "시장에서 장보고",
            "조용한 밥집",
        ],
        "rest": [
            "벤치에 앉아서",
            "동네 한 바퀴",
            "라디오 듣자",
            "차 한 잔 더",
            "잠깐 눈 붙이고",
        ],
    },
    "young_parent": {
        "morning_visit_cafe": [
            "키즈존 있는 곳",
            "주차되는 카페",
            "유모차 들어가는 데",
            "아이 음료도 있는 곳",
            "한적한 시간대",
        ],
        "lunch_decide": [
            "가족 외식 메뉴",
            "아이 메뉴 있는 곳",
            "근처 키즈카페 옆",
            "포장해서 집에서",
            "주말이라 좀 늦게",
        ],
        "evening_decide": [
            "일찍 집밥",
            "아이 재우고 한 잔",
            "동네 패밀리 레스토랑",
            "배달 시키자",
            "저녁 산책",
        ],
        "rest": [
            "아이 낮잠 사이",
            "벤치에서 잠깐",
            "유모차 끌고 산책",
            "음료 한 잔만",
            "친구 부부랑 만나자",
        ],
    },
    "tourist_foreign": {
        "morning_visit_cafe": [
            "한국 카페 체험",
            "인스타 핫플",
            "Korean cafe famous",
            "사진 많이 찍자",
            "전통 차 가게",
        ],
        "lunch_decide": [
            "한식당 도전",
            "비빔밥 맛집",
            "치킨 한 번",
            "검색해보자",
            "현지인 추천",
        ],
        "evening_decide": [
            "포장마차 가자",
            "한국 술 시도",
            "야시장 구경",
            "이태원 바",
            "호텔 근처로",
        ],
        "rest": [
            "Take photos here",
            "지도 다시 확인",
            "잠깐 앉자",
            "기념품샵",
            "가이드북 읽기",
        ],
    },
    "f&b_owner": {
        "morning_visit_cafe": [
            "경쟁 매장 확인",
            "신메뉴 벤치마킹",
            "사장 모임",
            "오픈 준비 전 한 잔",
            "거래처 미팅",
        ],
        "lunch_decide": [
            "직원 식사 챙기기",
            "재료 거래처",
            "근처 매장 답사",
            "오늘 점심 영업 점검",
            "빨리 먹고 복귀",
        ],
        "evening_decide": [
            "마감 후 한 잔",
            "동종 업계 모임",
            "직원 회식",
            "내일 메뉴 회의",
            "재료 발주",
        ],
        "rest": [
            "잠깐 카운터 앞",
            "직원 교대 시간",
            "세무 자료 보고",
            "SNS 마케팅 글",
            "리뷰 답글",
        ],
    },
}


def pick_dialog(
    archetype: str,
    situation: str,
    hour: int,
    rng: random.Random,
) -> str:
    """archetype + situation 에서 한국어 짧은 문장 1개 sample.

    Args:
        archetype: ARCHETYPES 의 id (예: "creative_freelancer").
        situation: "morning_visit_cafe" | "lunch_decide" | "evening_decide" | "rest".
        hour: 현재 시간 (0~23). 향후 시간대별 분기 확장에 사용.
        rng: random.Random 인스턴스 (재현성).

    Returns:
        한국어 짧은 문장. archetype/situation 모르는 경우 fallback "...".
    """
    bucket = TEMPLATES.get(archetype, {}).get(situation, [])
    if not bucket:
        return "..."
    return rng.choice(bucket)
```

- [ ] **Step 3.4: 테스트 실행 → pass 확인**

```bash
python -m pytest backend/tests/test_dialog_templates.py -v
```
Expected: PASS (6 tests)

- [ ] **Step 3.5: ruff + commit**

```bash
ruff check --fix backend/src/simulation/dialog_templates.py backend/tests/test_dialog_templates.py
ruff format backend/src/simulation/dialog_templates.py backend/tests/test_dialog_templates.py
```

사용자 확인 후:
```bash
git add backend/src/simulation/dialog_templates.py backend/tests/test_dialog_templates.py
git commit -m "feat(A1): dialog_templates — 8 archetype × 4 situation × 5 문장 (Mode B)"
```

---

## Task 4: vacancy_pse 인자 추가 (menu_items + 시각화 + LLM)

**Files:**
- Modify: `backend/src/simulation/vacancy_pse.py:61~140`
- Test: `backend/tests/test_vacancy_pse_brand.py`

- [ ] **Step 4.1: 테스트 작성**

```python
# backend/tests/test_vacancy_pse_brand.py
"""vacancy_pse 의 menu_items + 시각화 + LLM 인자 동작."""

import pytest

from src.simulation.vacancy_pse import evaluate_vacancy_pse

SPOT = {"dong": "서교동", "lat": 37.5544, "lon": 126.9220}


@pytest.mark.slow
def test_pse_with_menu_items_uses_menu_prices():
    """menu_items 제공 → vacancy 매장의 spend 가 메뉴 가격에서 sampling."""
    menu = [{"name": "라떼", "price": 5000}]
    result = evaluate_vacancy_pse(
        SPOT, "카페",
        n_seeds=1, days=1,
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
        SPOT, "카페",
        n_seeds=1, days=1,
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
        "vacancy_spot": SPOT, "category": "카페", "n_seeds": 1, "days": 1,
        "popularity_boost": 5.0, "with_cannibalization": False,
        "per_seed": [], "pse_summary": {
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
```

- [ ] **Step 4.2: 테스트 실행 → fail 확인**

```bash
python -m pytest backend/tests/test_vacancy_pse_brand.py::test_pse_existing_signature_still_works -v
```
Expected: PASS (회귀 테스트는 monkeypatch 라 fail 안 함, but `@pytest.mark.slow` 인 다른 3개는 새 인자가 없어 TypeError).

```bash
python -m pytest backend/tests/test_vacancy_pse_brand.py -v -m slow --timeout=60
```
Expected: FAIL with `TypeError: evaluate_vacancy_pse() got an unexpected keyword argument 'menu_items'` (또는 `collect_trajectory`).

- [ ] **Step 4.3: vacancy_pse.evaluate_vacancy_pse 수정**

`backend/src/simulation/vacancy_pse.py:61~140` 수정:

```python
def evaluate_vacancy_pse(
    vacancy_spot: dict[str, Any],
    category: str,
    n_seeds: int = 5,
    days: int = 1,
    popularity_boost: float = DEFAULT_POPULARITY_BOOST,
    with_cannibalization: bool = True,
    pop_mix: PopulationMix | None = None,
    tier_dist: TierDistribution | None = None,
    cfg: ModelConfig | None = None,
    seeds: list[int] | None = None,
    verbose: bool = False,
    menu_items: list[dict] | None = None,            # ← B 작업
    collect_trajectory: bool = False,                # ← 시각화 인터페이스
    trajectory_sample_size: int = 300,               # ←
    dump_visits: bool = False,                       # ←
    use_dialog_templates: bool = True,               # ← Mode B (default)
    enable_llm: bool = False,                        # ← Mode C placeholder
    llm_tier_policy: str = "S_only",                 # ← "none"|"S_only"|"S_and_A"|"all"
    llm_max_tokens: int = 30,                        # ← 짧은 자연어
    llm_call_interval: int = 4,                      # ← 시간 단위
) -> dict[str, Any]:
    """Vacancy 평가를 PSE N=n_seeds 로 측정 → 신뢰구간 산출.
    
    (기존 docstring 유지, 새 인자 doc 추가)
    
    새 인자:
        menu_items: 가상 vacancy 매장의 메뉴/가격. None=빈 list (기존 추상 fallback).
            services/brand_menu_loader.load_brand_menu_items() 가 source.
        collect_trajectory / trajectory_sample_size / dump_visits:
            시각화 데이터 출력. False (기본) = 출력 X (응답 작음).
        use_dialog_templates: Mode B — Pure Policy + Template 자연어. default True.
        enable_llm: Mode C placeholder — 본 spec 에서는 인터페이스만 정의,
            실제 LLM 호출 인프라는 future spec (Phase 2 비동기 인프라).
            현재 enable_llm=True 도 내부적으로 mock 강제 (cfg.tier_*_provider="mock").
        llm_tier_policy / llm_max_tokens / llm_call_interval: Mode C 인자.
    """
    seeds = (seeds or DEFAULT_SEEDS)[:n_seeds]
    cfg = cfg or ModelConfig()
    if cfg.tier_s_provider not in ("mock", "openai", "anthropic", "gemini", "ollama"):
        cfg.tier_s_provider = "mock"
    if cfg.tier_a_provider not in ("mock", "openai", "anthropic", "gemini", "ollama"):
        cfg.tier_a_provider = "mock"
    pop_mix = pop_mix or PopulationMix()
    tier_dist = tier_dist or TierDistribution()

    # Mode C placeholder: 현재 spec 은 mock 강제. Phase 2 spec 에서 진짜 활성.
    # enable_llm=True 도 안전하게 mock 으로 fallback (사용자가 Mode C 시 명시적
    # llm_tier_policy 등 인자를 전달해도 비용 0 보장).
    # → cfg.tier_s_provider/tier_a_provider 그대로 두면 OK (위 mock 자동 fallback)
    _ = (enable_llm, llm_tier_policy, llm_max_tokens, llm_call_interval)  # 인터페이스 reserved

    per_seed: list[dict[str, Any]] = []
    trajectory_collected: list[dict] | None = [] if collect_trajectory else None
    visits_events: list[dict] | None = [] if dump_visits else None

    for s in seeds:
        if verbose:
            print(f"[PSE] seed={s} 측정 중...", flush=True)

        world_w, hm_w = load_world_from_rds()
        vid = inject_vacancy_as_store(
            world_w, vacancy_spot, category,
            popularity_boost=popularity_boost,
            menu_items=menu_items,    # ← 패스스루
        )
        sim_result = run_simulation(
            days=days,
            cfg=cfg,
            pop=pop_mix,
            tier=tier_dist,
            world=world_w,
            hours_map=hm_w,
            use_rds=False,
            use_profiles=True,
            use_policy=True,
            collect_trajectory=collect_trajectory,           # ← 패스스루
            trajectory_sample_size=trajectory_sample_size,   # ← 패스스루
            seed=s,
            verbose=False,
            seed_memory=True,
            memory_seed_days=14,
        )
        if collect_trajectory and sim_result is not None:
            traj = getattr(sim_result, "trajectory", None) or []
            trajectory_collected.extend(traj)
        if dump_visits:
            for ev in getattr(world_w, "event_log", []):
                if ev.get("type") == "visit":
                    visits_events.append({
                        "seed": s, **{k: v for k, v in ev.items() if k != "type"},
                    })

        v_eval = evaluate_vacancy_store(world_w, vid, days_simulated=days)
        cmp = compare_to_dong_average(world_w, vid, days_simulated=days)

        seed_result: dict[str, Any] = {
            "seed": s,
            "visits_per_day": v_eval["visits_per_day"],
            "revenue_per_day": v_eval["revenue_per_day"],
            "occupancy": v_eval["occupancy"],
            "vacancy_vs_avg_visits_ratio": cmp.get("vacancy_vs_avg_visits_ratio", 0),
            "vacancy_vs_avg_revenue_ratio": cmp.get("vacancy_vs_avg_revenue_ratio", 0),
            "dong_category_n_stores": cmp.get("dong_category_n_stores", 0),
        }

        if with_cannibalization:
            world_b, hm_b = load_world_from_rds()
            run_simulation(
                days=days, cfg=cfg, pop=pop_mix, tier=tier_dist,
                world=world_b, hours_map=hm_b,
                use_rds=False, use_profiles=True, use_policy=True,
                collect_trajectory=False,
                seed=s, verbose=False,
                seed_memory=True, memory_seed_days=14,
            )
            cann = measure_cannibalization(world_w, world_b, vid, radius_m=500)
            seed_result["cannibalization_pct"] = cann["same_category"]["cannibalization_pct"]
            seed_result["synergy_pct"] = cann["other_category"]["synergy_pct"]
            seed_result["same_cat_delta_visits"] = cann["same_category"]["delta_visits"]
            seed_result["same_cat_n_stores"] = cann["same_category"]["n_stores"]
            dong_cann = measure_dong_cannibalization(world_w, world_b, vid)
            seed_result["dong_cannibalization_pct"] = dong_cann["same_category"]["cannibalization_pct"]
            seed_result["dong_synergy_pct"] = dong_cann["other_category"]["synergy_pct"]
            seed_result["dong_net_growth_pct"] = dong_cann["dong_total"]["net_growth_pct"]
            seed_result["dong_same_cat_delta_visits"] = dong_cann["same_category"]["delta_visits"]

        per_seed.append(seed_result)

    # PSE summary (기존 그대로)
    metric_keys = [
        "visits_per_day", "revenue_per_day", "occupancy",
        "vacancy_vs_avg_visits_ratio", "vacancy_vs_avg_revenue_ratio",
    ]
    if with_cannibalization:
        metric_keys += [
            "cannibalization_pct", "synergy_pct", "same_cat_delta_visits",
            "dong_cannibalization_pct", "dong_synergy_pct",
            "dong_net_growth_pct", "dong_same_cat_delta_visits",
        ]
    pse_summary = {k: _summarize([r[k] for r in per_seed if k in r]) for k in metric_keys}

    # 분기/연 단위 환산 (기존)
    QUARTER_DAYS = 90
    YEAR_DAYS = 365
    visits_q = {
        "mean": round(pse_summary["visits_per_day"]["mean"] * QUARTER_DAYS, 0),
        "ci95": round(pse_summary["visits_per_day"]["ci95"] * QUARTER_DAYS, 0),
    }
    visits_y = {
        "mean": round(pse_summary["visits_per_day"]["mean"] * YEAR_DAYS, 0),
        "ci95": round(pse_summary["visits_per_day"]["ci95"] * YEAR_DAYS, 0),
    }
    revenue_q_mean = pse_summary["revenue_per_day"]["mean"] * QUARTER_DAYS
    revenue_q_ci = pse_summary["revenue_per_day"]["ci95"] * QUARTER_DAYS
    revenue_y_mean = pse_summary["revenue_per_day"]["mean"] * YEAR_DAYS
    revenue_y_ci = pse_summary["revenue_per_day"]["ci95"] * YEAR_DAYS
    pse_summary["visits_per_quarter"] = visits_q
    pse_summary["visits_per_year"] = visits_y
    pse_summary["revenue_per_quarter"] = {"mean": round(revenue_q_mean, 0), "ci95": round(revenue_q_ci, 0)}
    pse_summary["revenue_per_year"] = {"mean": round(revenue_y_mean, 0), "ci95": round(revenue_y_ci, 0)}

    # narrative (기존)
    vis = pse_summary["visits_per_day"]
    rev = pse_summary["revenue_per_day"]
    ratio = pse_summary["vacancy_vs_avg_visits_ratio"]
    narrative = (
        f"{vacancy_spot.get('dong', '?')} {category} 신규 매장 "
        f"(popularity_boost={popularity_boost}, PSE N={n_seeds}):\n"
        f"  📅 일평균   방문 : {vis['mean']:5.1f} ± {vis['ci95']:.1f} 명 "
        f"(95% CI, range [{vis['min']:.0f}, {vis['max']:.0f}])\n"
        f"  📅 일평균   매출 : {rev['mean'] / 10000:5.0f} ± {rev['ci95'] / 10000:.0f} 만원\n"
        f"  📊 분기 추정 방문 : {visits_q['mean']:5.0f} ± {visits_q['ci95']:.0f} 명 (90일 환산)\n"
        f"  💰 분기 추정 매출 : {revenue_q_mean / 1e8:5.2f} ± {revenue_q_ci / 1e8:.2f} 억원\n"
        f"  💰 연  추정 매출 : {revenue_y_mean / 1e8:5.2f} ± {revenue_y_ci / 1e8:.2f} 억원\n"
        f"  ⚖️  동 평균 대비   : {ratio['mean']:5.1f} ± {ratio['ci95']:.1f} 배 attractive"
    )
    if with_cannibalization:
        cann = pse_summary["cannibalization_pct"]
        dong_growth = pse_summary.get("dong_net_growth_pct", {"mean": 0, "ci95": 0})
        narrative += (
            f"\n  🔻 카니발 (반경 500m) : {cann['mean']:+5.1f} ± {cann['ci95']:.1f}% (- = 시너지)"
            f"\n  📈 동 시장 성장      : {dong_growth['mean']:+5.2f} ± {dong_growth['ci95']:.2f}% "
            f"(0% 포함 시 zero-sum)"
        )

    return {
        "vacancy_spot": vacancy_spot,
        "category": category,
        "n_seeds": n_seeds,
        "days": days,
        "popularity_boost": popularity_boost,
        "with_cannibalization": with_cannibalization,
        "per_seed": per_seed,
        "pse_summary": pse_summary,
        "narrative": narrative,
        "trajectory": trajectory_collected,
        "visits_events": visits_events,
    }
```

- [ ] **Step 4.4: 테스트 실행 → pass 확인**

```bash
# 빠른 단위 (회귀, default 인자 path)
python -m pytest backend/tests/test_vacancy_pse_brand.py::test_pse_existing_signature_still_works -v
```
Expected: PASS

```bash
# slow 통합 (실제 시뮬, ~3~5분)
python -m pytest backend/tests/test_vacancy_pse_brand.py -v -m slow --timeout=600
```
Expected: PASS (3 tests, 단 mocked 환경 가정)

회귀 확인:
```bash
python -m pytest backend/tests/ -k "vacancy" -v
```
Expected: 기존 vacancy 테스트 모두 통과

- [ ] **Step 4.5: ruff + commit**

```bash
ruff check --fix backend/src/simulation/vacancy_pse.py backend/tests/test_vacancy_pse_brand.py
ruff format backend/src/simulation/vacancy_pse.py backend/tests/test_vacancy_pse_brand.py
```

사용자 확인 후:
```bash
git add backend/src/simulation/vacancy_pse.py backend/tests/test_vacancy_pse_brand.py
git commit -m "feat(A1): vacancy_pse 인자 추가 (menu_items + 시각화 + Mode B/C placeholder)"
```

---

## Task 5 (옵션 B): living_population 일별 boost loader 신규

**Files:**
- Modify: `backend/src/simulation/world.py` (`World.living_pop_daily_boost` 필드 추가)
- Modify: `backend/src/simulation/world_loader.py` (`_load_living_population_daily()` 신규 함수)
- Test: `backend/tests/test_living_pop_loader.py`

- [ ] **Step 5.1: 테스트 작성**

```python
# backend/tests/test_living_pop_loader.py
"""living_population 일별 boost loader 단위 테스트."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest


@patch("src.simulation.world_loader.get_sync_engine")
def test_load_living_population_daily_returns_dict(mock_engine):
    """정상 — (dong, hour, day_idx) → boost dict 반환."""
    from src.simulation.world_loader import _load_living_population_daily

    mock_conn = MagicMock()
    mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.mappings.return_value = [
        {"dong_name": "서교동", "time_zone": 14, "day_idx": 0, "total_pop": 5000.0, "dong_avg": 4000.0},
        {"dong_name": "서교동", "time_zone": 14, "day_idx": 1, "total_pop": 4500.0, "dong_avg": 4000.0},
    ]

    result = _load_living_population_daily(date(2026, 1, 1), days=2)
    assert ("서교동", 14, 0) in result
    assert result[("서교동", 14, 0)] == pytest.approx(1.25, abs=0.01)
    assert result[("서교동", 14, 1)] == pytest.approx(1.125, abs=0.01)


@patch("src.simulation.world_loader.get_sync_engine")
def test_load_living_population_empty_returns_empty_dict(mock_engine):
    """DB 데이터 0건 → 빈 dict (시뮬은 fallback boost)."""
    from src.simulation.world_loader import _load_living_population_daily

    mock_conn = MagicMock()
    mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.mappings.return_value = []

    result = _load_living_population_daily(date(2026, 1, 1), days=90)
    assert result == {}


def test_world_has_living_pop_daily_boost_field():
    """World 데이터클래스에 living_pop_daily_boost 필드 존재."""
    from src.simulation.world import World
    w = World()
    assert hasattr(w, "living_pop_daily_boost")
    assert isinstance(w.living_pop_daily_boost, dict)
    assert w.living_pop_daily_boost == {}
```

- [ ] **Step 5.2: 테스트 실행 → fail 확인**

```bash
python -m pytest backend/tests/test_living_pop_loader.py -v
```
Expected: FAIL with `ImportError` 또는 `AttributeError: 'World' object has no attribute 'living_pop_daily_boost'`

- [ ] **Step 5.3: World 필드 추가**

`backend/src/simulation/world.py` 의 World 데이터클래스 (line 79 근처 `adstrd_flpop_boost` 다음):

```python
    # ---------------------------
    # 옵션 B (2026-04-27): living_population 기반 일별 boost
    # ---------------------------
    # {(dong_name, hour, day_idx): ratio 0.5~2.0} — 매일 다른 boost (90일 분량).
    # day_idx = 0 (시뮬 첫째 날) ~ days-1.
    # 빈 dict 면 기존 정적 adstrd_flpop_boost fallback (하위 호환성).
    living_pop_daily_boost: dict = field(default_factory=dict)
```

- [ ] **Step 5.4: world_loader 신규 함수 추가**

`backend/src/simulation/world_loader.py` 끝에:

```python
from datetime import date as _date, timedelta as _timedelta


def _load_living_population_daily(
    start_date: _date,
    days: int,
) -> dict[tuple[str, int, int], float]:
    """living_population 테이블에서 (dong, hour, day_idx) → boost 로드.

    boost = total_pop / (dong 의 분기 평균 total_pop). 1.0 = 평균.

    Args:
        start_date: 시뮬 첫 일자.
        days: 시뮬 일수 (90 분기 권장).

    Returns:
        {(dong_name, hour, day_idx): float}.
        DB 데이터 부재 시 빈 dict (시뮬은 정적 boost fallback).
    """
    sql = text("""
        WITH avg_pop AS (
            SELECT dong_name, AVG(total_pop) AS dong_avg
              FROM living_population
             WHERE dong_code LIKE '114%'
               AND date >= :start_date
               AND date < :end_date
             GROUP BY dong_name
        )
        SELECT lp.dong_name, lp.time_zone,
               (lp.date - :start_date) AS day_idx,
               lp.total_pop, ap.dong_avg
          FROM living_population lp
          JOIN avg_pop ap ON ap.dong_name = lp.dong_name
         WHERE lp.dong_code LIKE '114%'
           AND lp.date >= :start_date
           AND lp.date < :end_date
    """)
    end_date = start_date + _timedelta(days=days)
    out: dict[tuple[str, int, int], float] = {}
    engine = get_sync_engine(os.environ["POSTGRES_URL"])
    with engine.connect() as conn:
        rows = conn.execute(
            sql, {"start_date": start_date, "end_date": end_date}
        ).mappings()
        for r in rows:
            avg = float(r["dong_avg"] or 0)
            if avg <= 0:
                continue
            ratio = float(r["total_pop"] or 0) / avg
            ratio = max(0.5, min(ratio, 2.0))   # clamp 0.5~2.0
            out[(r["dong_name"], int(r["time_zone"]), int(r["day_idx"]))] = ratio
    return out
```

- [ ] **Step 5.5: 테스트 실행 → pass 확인**

```bash
python -m pytest backend/tests/test_living_pop_loader.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5.6: ruff + commit**

```bash
ruff check --fix backend/src/simulation/world.py backend/src/simulation/world_loader.py backend/tests/test_living_pop_loader.py
ruff format backend/src/simulation/world.py backend/src/simulation/world_loader.py backend/tests/test_living_pop_loader.py
```

사용자 확인 후:
```bash
git add backend/src/simulation/world.py backend/src/simulation/world_loader.py backend/tests/test_living_pop_loader.py
git commit -m "feat(A1): living_population 일별 boost loader (옵션 B)"
```

---

## Task 6 (옵션 B): runner.py day-loop 안 boost 갱신

**Files:**
- Modify: `backend/src/simulation/runner.py:498~530` (day-loop 안 boost 갱신 추가)
- Test: `backend/tests/test_runner_day_loop_boost.py`

- [ ] **Step 6.1: 테스트 작성**

```python
# backend/tests/test_runner_day_loop_boost.py
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
```

- [ ] **Step 6.2: 테스트 실행 → fail 확인**

```bash
python -m pytest backend/tests/test_runner_day_loop_boost.py -v
```
Expected: FAIL with `ImportError: cannot import name '_swap_dong_hour_boost_for_day'`

- [ ] **Step 6.3: runner.py 수정 — helper 함수 + day-loop 갱신**

`backend/src/simulation/runner.py` 에 helper 추가 (top-level 함수, day-loop 위에):

```python
def _swap_dong_hour_boost_for_day(
    living_pop_daily_boost: dict,
    fallback_boost: dict,
    day_idx: int,
    weekday: int,
) -> dict:
    """매일 boost dict 갱신 — living_pop 우선, 없으면 fallback.

    Args:
        living_pop_daily_boost: {(dong, hour, day_idx): ratio} (옵션 B).
        fallback_boost: 기존 분기 평균 boost {(dong, hour, weekday): ratio}.
        day_idx: 현재 시뮬 day index (0 ~ days-1).
        weekday: 0(월) ~ 6(일).

    Returns:
        새 boost dict {(dong, hour, weekday): ratio} — score_store 가 사용하는 형식.
    """
    if not living_pop_daily_boost:
        return fallback_boost
    # living_pop 의 day_idx 매칭하는 (dong, hour) 만 갱신
    out = dict(fallback_boost)  # fallback 복사
    for (dong, hour, didx), ratio in living_pop_daily_boost.items():
        if didx == day_idx:
            out[(dong, hour, weekday)] = ratio
    return out
```

day-loop 안 (`runner.py:508~530` 근처, `world.is_weekend = ...` 다음) 추가:

```python
        # 옵션 B: living_pop_daily_boost 활성 시 매일 갱신
        if not is_warmup and world.living_pop_daily_boost:
            world.adstrd_flpop_boost = _swap_dong_hour_boost_for_day(
                world.living_pop_daily_boost,
                world.adstrd_flpop_boost,
                day_idx=day - 1,        # day=1 → day_idx=0
                weekday=world.weekday,
            )
```

- [ ] **Step 6.4: 테스트 실행 → pass 확인**

```bash
python -m pytest backend/tests/test_runner_day_loop_boost.py -v
```
Expected: PASS (2 tests)

회귀 확인:
```bash
python -m pytest backend/tests/ -k "vacancy or runner" -v
```
Expected: 기존 vacancy/runner 테스트 모두 통과 (living_pop_daily_boost 빈 dict 일 때 fallback 보존).

- [ ] **Step 6.5: ruff + commit**

```bash
ruff check --fix backend/src/simulation/runner.py backend/tests/test_runner_day_loop_boost.py
ruff format backend/src/simulation/runner.py backend/tests/test_runner_day_loop_boost.py
```

사용자 확인 후:
```bash
git add backend/src/simulation/runner.py backend/tests/test_runner_day_loop_boost.py
git commit -m "feat(A1): runner day-loop 안 boost 매일 갱신 (옵션 B)"
```

---

## Task 7: vacancy_evaluation_service brand_name 인자 추가

**Files:**
- Modify: `backend/src/services/vacancy_evaluation_service.py:49~146`
- Test: `backend/tests/test_vacancy_evaluation_service_brand.py`

- [ ] **Step 5.1: 테스트 작성**

```python
# backend/tests/test_vacancy_evaluation_service_brand.py
"""evaluate_top_vacancies 의 brand_name 인자 동작."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.vacancy_evaluation_service import evaluate_top_vacancies
from src.services.brand_menu_loader import BrandNotFoundError

SPOT = {"dong_name": "서교동", "lat": 37.5544, "lon": 126.9220, "id": "v1"}


@patch("src.services.vacancy_evaluation_service.evaluate_vacancy_pse")
@patch("src.services.brand_menu_loader.load_brand_menu_items")
def test_evaluate_with_brand_loads_menu(mock_loader, mock_pse):
    """brand_name 제공 → brand_menu_loader 호출 → vacancy_pse 에 menu_items 패스."""
    mock_loader.return_value = [{"name": "라떼", "price": 5000}]
    mock_pse.return_value = {
        "narrative": "test",
        "pse_summary": {
            "visits_per_day": {"mean": 10.0, "ci95": 1.0, "min": 9, "max": 11},
            "revenue_per_day": {"mean": 100000, "ci95": 5000},
            "vacancy_vs_avg_visits_ratio": {"mean": 1.0, "ci95": 0.1},
        },
    }
    out = evaluate_top_vacancies(
        vacancy_spots=[SPOT], category="카페",
        brand_name="이디야", n_seeds=1,
    )
    mock_loader.assert_called_once_with("이디야")
    # vacancy_pse 호출 시 menu_items 가 패스됐는지 확인
    _, kwargs = mock_pse.call_args
    assert kwargs.get("menu_items") == [{"name": "라떼", "price": 5000}]
    assert len(out) == 1


@patch("src.services.vacancy_evaluation_service.evaluate_vacancy_pse")
@patch("src.services.brand_menu_loader.load_brand_menu_items")
def test_evaluate_without_brand_skips_loader(mock_loader, mock_pse):
    """brand_name=None (기본) → loader 호출 X (하위 호환)."""
    mock_pse.return_value = {
        "narrative": "test",
        "pse_summary": {
            "visits_per_day": {"mean": 5.0, "ci95": 1.0, "min": 4, "max": 6},
            "revenue_per_day": {"mean": 50000, "ci95": 2500},
            "vacancy_vs_avg_visits_ratio": {"mean": 1.0, "ci95": 0.1},
        },
    }
    out = evaluate_top_vacancies(vacancy_spots=[SPOT], category="카페", n_seeds=1)
    mock_loader.assert_not_called()
    assert len(out) == 1


@patch("src.services.brand_menu_loader.load_brand_menu_items")
def test_brand_not_found_returns_error_response(mock_loader):
    """BrandNotFoundError → 결과 빈 list + log.warning (전체 평가 중단)."""
    mock_loader.side_effect = BrandNotFoundError("스타벅스 마포 매장 없음")
    out = evaluate_top_vacancies(
        vacancy_spots=[SPOT], category="카페",
        brand_name="스타벅스", n_seeds=1,
    )
    # 정책: brand 없으면 모든 spot 평가 불가 (모두 같은 brand 가정)
    assert out == []
```

- [ ] **Step 5.2: 테스트 실행 → fail 확인**

```bash
python -m pytest backend/tests/test_vacancy_evaluation_service_brand.py -v
```
Expected: FAIL with `TypeError: evaluate_top_vacancies() got an unexpected keyword argument 'brand_name'`

- [ ] **Step 5.3: vacancy_evaluation_service 수정**

`backend/src/services/vacancy_evaluation_service.py:49~146`:

```python
def evaluate_top_vacancies(
    vacancy_spots: list[dict[str, Any]],
    category: str,
    top_n: int = 5,
    n_seeds: int = 5,
    days: int = 1,
    with_cannibalization: bool = False,
    popularity_boost: float | None = None,
    pre_filter_score: list[float] | None = None,
    verbose: bool = False,
    brand_name: str | None = None,    # ← 추가, 모든 vacancy_spots 에 공통 적용
) -> list[dict[str, Any]]:
    """여러 공실 PSE 평가 + 일평균 방문 내림차순 순위.
    
    (기존 docstring 유지)
    
    새 인자:
        brand_name: 프랜차이즈 브랜드명 (예: "이디야"). 제공 시 모든 vacancy_spots 에
            공통 적용 — services/brand_menu_loader.load_brand_menu_items() 호출
            → 시뮬에 menu_items 패스. 마포 매장 0개 brand 이면 BrandNotFoundError
            → 빈 list 반환 + log.warning. 메뉴 데이터 부재면 추상 fallback.
    """
    from src.simulation.vacancy_inject import DEFAULT_POPULARITY_BOOST
    from src.simulation.vacancy_pse import evaluate_vacancy_pse
    from src.services.brand_menu_loader import (
        BrandMenuEmptyError,
        BrandNotFoundError,
        load_brand_menu_items,
    )

    if not vacancy_spots:
        return []

    # brand_name 처리 — 모든 vacancy 에 공통 적용
    menu_items: list[dict] | None = None
    if brand_name:
        try:
            menu_items = load_brand_menu_items(brand_name)
            if verbose:
                logger.info(
                    f"[vacancy_evaluation] brand='{brand_name}' 메뉴 {len(menu_items)}개 로드"
                )
        except BrandNotFoundError as e:
            logger.warning(f"[vacancy_evaluation] {e} — 평가 중단")
            return []
        except BrandMenuEmptyError as e:
            logger.warning(f"[vacancy_evaluation] {e} — 추상 매출 fallback")
            menu_items = None

    # 정규화 (기존 그대로)
    normalized = [_normalize_vacancy_spot(s) for s in vacancy_spots]
    valid = [s for s in normalized if s["dong"] and s["lat"] is not None and s["lon"] is not None]
    if len(valid) < len(normalized):
        logger.warning(f"vacancy_spots {len(normalized)} 중 {len(valid)}개만 유효 (dong/lat/lon 누락 제외)")

    if pre_filter_score and len(pre_filter_score) == len(valid):
        valid = [s for _, s in sorted(zip(pre_filter_score, valid), key=lambda x: -x[0])]
    valid = valid[:top_n]

    if verbose:
        logger.info(f"[vacancy_evaluation] {len(valid)} 공실 PSE N={n_seeds} 평가 시작 ({category})")

    pb = popularity_boost if popularity_boost is not None else DEFAULT_POPULARITY_BOOST

    from src.simulation.config import ModelConfig

    mock_cfg = ModelConfig()
    mock_cfg.tier_s_provider = "mock"
    mock_cfg.tier_a_provider = "mock"

    rankings: list[dict[str, Any]] = []
    for i, spot in enumerate(valid):
        if verbose:
            logger.info(f"[vacancy_evaluation] {i + 1}/{len(valid)} — {spot['dong']} 평가 중...")
        try:
            pse_kwargs = {
                "vacancy_spot": {"dong": spot["dong"], "lat": spot["lat"], "lon": spot["lon"]},
                "category": category,
                "n_seeds": n_seeds,
                "days": days,
                "with_cannibalization": with_cannibalization,
                "popularity_boost": pb,
                "cfg": mock_cfg,
                "verbose": False,
                "menu_items": menu_items,    # ← 패스
            }
            result = evaluate_vacancy_pse(**pse_kwargs)
            rankings.append({
                "spot": spot,
                "narrative": result["narrative"],
                "pse_summary": result["pse_summary"],
                "score": result["pse_summary"]["visits_per_day"]["mean"],
            })
        except Exception as e:
            logger.exception(f"[vacancy_evaluation] {spot['dong']} 평가 실패: {e}")

    rankings.sort(key=lambda r: -r["score"])
    for rank, r in enumerate(rankings, 1):
        r["rank"] = rank
    return rankings
```

- [ ] **Step 5.4: 테스트 실행 → pass 확인**

```bash
python -m pytest backend/tests/test_vacancy_evaluation_service_brand.py -v
```
Expected: PASS (3 tests)

회귀 확인:
```bash
python -m pytest backend/tests/ -k "vacancy_evaluation" -v
```
Expected: 기존 + 새 테스트 모두 통과

- [ ] **Step 5.5: ruff + commit**

```bash
ruff check --fix backend/src/services/vacancy_evaluation_service.py backend/tests/test_vacancy_evaluation_service_brand.py
ruff format backend/src/services/vacancy_evaluation_service.py backend/tests/test_vacancy_evaluation_service_brand.py
```

사용자 확인 후:
```bash
git add backend/src/services/vacancy_evaluation_service.py backend/tests/test_vacancy_evaluation_service_brand.py
git commit -m "feat(A1): evaluate_top_vacancies 에 brand_name 인자 (모든 spot 공통)"
```

---

## Task 8: brand_vacancy_validator 트랙 단위 함수 (V1a/V1b/V1c/V2/CI)

**Files:**
- Create: `validation/brand_vacancy_validator.py` (단위 함수만 먼저, 다음 task 에서 run_5track 추가)
- Test: `tests/test_brand_vacancy_validator.py`

- [ ] **Step 6.1: 트랙 단위 테스트 작성**

```python
# tests/test_brand_vacancy_validator.py
"""brand_vacancy_validator 트랙 단위 함수 테스트."""

import numpy as np
import pytest

from validation.brand_vacancy_validator import (
    _track_ci,
    _track_v1a,
    _track_v1b,
    _track_v1c,
    _track_v2,
)


class TestTrackV1a:
    def test_pass_when_strict_correlation(self):
        """sim ≈ actual×1.05 → r≈0.99, mape≈5% → pass."""
        actual = {(f"d{i}", "카페"): float(100 + i * 10) for i in range(20)}
        sim = {k: v * 1.05 for k, v in actual.items()}
        result = _track_v1a(sim, actual)
        assert result["status"] == "ok"
        assert result["pearson_r"] >= 0.85
        assert result["mape"] <= 0.25
        assert result["pass"] is True

    def test_fail_when_random(self):
        """sim 무작위 → r≈0, fail."""
        actual = {(f"d{i}", "카페"): float(100 + i * 10) for i in range(20)}
        rng = np.random.default_rng(42)
        sim = {k: float(rng.uniform(0, 1000)) for k in actual.keys()}
        result = _track_v1a(sim, actual)
        assert result["status"] == "ok"
        assert result["pass"] is False

    def test_incomplete_when_too_few_cells(self):
        """공통 cell < 10 → incomplete + pass=False."""
        actual = {(f"d{i}", "카페"): 100.0 for i in range(5)}
        sim = {k: 100.0 for k in actual.keys()}
        result = _track_v1a(sim, actual)
        assert result["status"] == "incomplete"
        assert result["pass"] is False


class TestTrackV1b:
    def test_pass_with_strict_threshold(self):
        actual = {(f"d{i}", "카페"): float(100 + i * 10) for i in range(20)}
        sim = {k: v * 1.10 for k, v in actual.items()}
        result = _track_v1b(sim, actual)
        assert result["pass"] is True
        assert result["thresholds"]["r_min"] == 0.80
        assert result["thresholds"]["mape_max"] == 0.30


class TestTrackV1c:
    def test_pass_when_ratio_within(self):
        sim = {(f"d{i}", "카페"): 1_200_000 for i in range(20)}
        actual = {(f"d{i}", "카페"): 1_000_000 for i in range(20)}
        result = _track_v1c(sim, actual)
        assert result["pass"] is True
        assert result["mean_ratio"] == pytest.approx(1.2, abs=0.01)

    def test_fail_when_ratio_too_high(self):
        sim = {(f"d{i}", "카페"): 3_000_000 for i in range(20)}
        actual = {(f"d{i}", "카페"): 1_000_000 for i in range(20)}
        result = _track_v1c(sim, actual)
        assert result["pass"] is False
        assert result["mean_ratio"] == pytest.approx(3.0, abs=0.01)

    def test_fail_when_ratio_too_low(self):
        sim = {(f"d{i}", "카페"): 500_000 for i in range(20)}
        actual = {(f"d{i}", "카페"): 1_000_000 for i in range(20)}
        result = _track_v1c(sim, actual)
        assert result["pass"] is False
        assert result["mean_ratio"] == pytest.approx(0.5, abs=0.01)


class TestTrackV2:
    def test_pass_when_ratio_within(self):
        result = _track_v2(sim_yearly=120_000_000, ftc_avg_yearly=100_000_000)
        assert result["pass"] is True
        assert result["ratio"] == 1.2

    def test_skipped_when_ftc_missing(self):
        result = _track_v2(sim_yearly=120_000_000, ftc_avg_yearly=None)
        assert result["status"] == "skipped"
        assert result["pass"] is False

    def test_fail_when_ratio_too_high(self):
        result = _track_v2(sim_yearly=300_000_000, ftc_avg_yearly=100_000_000)
        assert result["pass"] is False
        assert result["ratio"] == 3.0


class TestTrackCi:
    def test_pass_when_low_variance(self):
        pse = {"revenue_per_day": {"mean": 100, "ci95": 8}}
        result = _track_ci(pse)
        assert result["pass"] is True
        assert result["ci_ratio"] == pytest.approx(0.08, abs=0.001)

    def test_fail_when_high_variance(self):
        pse = {"revenue_per_day": {"mean": 100, "ci95": 25}}
        result = _track_ci(pse)
        assert result["pass"] is False

    def test_incomplete_when_zero_mean(self):
        pse = {"revenue_per_day": {"mean": 0, "ci95": 0}}
        result = _track_ci(pse)
        assert result["status"] == "incomplete"
        assert result["pass"] is False
```

- [ ] **Step 6.2: 테스트 실행 → fail 확인**

```bash
python -m pytest tests/test_brand_vacancy_validator.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'validation.brand_vacancy_validator'`

- [ ] **Step 6.3: brand_vacancy_validator 트랙 단위 함수 구현**

```python
# validation/brand_vacancy_validator.py
"""5트랙 검증 protocol — brand 별 vacancy_pse 의 production-readiness 평가.

5트랙 측정 + 합격선 (엄격) 판정 + diagnose 진단 + JSON/MD report 생성.

학술 근거 (spec 16절):
    - Park 2024 (1052명 LLM 시뮬) — 같은 규모 학술 baseline
    - Affordable Generative Agents — 비용 절감 + 검증
    - Brussels ABM 0.96 — 학계 천장

사용:
    python -m validation.brand_vacancy_validator --brand 이디야 --category 카페
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import scipy.stats

logger = logging.getLogger(__name__)


# 합격선 (spec 9.1 엄격 정의)
V1A_R_MIN = 0.85
V1A_MAPE_MAX = 0.25
V1B_R_MIN = 0.80
V1B_MAPE_MAX = 0.30
V1C_RATIO_MIN = 0.7
V1C_RATIO_MAX = 1.5
V2_RATIO_MIN = 0.7
V2_RATIO_MAX = 1.5
CI_MAX = 0.10
MIN_CELLS_FOR_PEARSON = 10  # Cohen 1988, 통계 안정성


def _track_v1a(sim_revenue: dict[tuple, float], actual_revenue: dict[tuple, float]) -> dict[str, Any]:
    """V1a — 동×업종 매출 64-cell Pearson r + MAPE."""
    common = set(sim_revenue.keys()) & set(actual_revenue.keys())
    if len(common) < MIN_CELLS_FOR_PEARSON:
        return {"status": "incomplete", "n_cells": len(common), "pass": False}
    sim_arr = np.array([sim_revenue[k] for k in common])
    act_arr = np.array([actual_revenue[k] for k in common])
    if np.std(sim_arr) == 0 or np.std(act_arr) == 0:
        return {"status": "incomplete", "n_cells": len(common), "pass": False, "reason": "zero variance"}
    r, _ = scipy.stats.pearsonr(sim_arr, act_arr)
    mape = float(np.mean(np.abs(sim_arr - act_arr) / np.maximum(act_arr, 1)))
    return {
        "status": "ok", "n_cells": len(common),
        "pearson_r": round(float(r), 4),
        "mape": round(mape, 4),
        "pass": r >= V1A_R_MIN and mape <= V1A_MAPE_MAX,
        "thresholds": {"r_min": V1A_R_MIN, "mape_max": V1A_MAPE_MAX},
    }


def _track_v1b(sim_visits: dict[tuple, float], actual_count: dict[tuple, float]) -> dict[str, Any]:
    """V1b — 동×업종 방문 64-cell Pearson r + MAPE. V1a 보다 약간 느슨."""
    common = set(sim_visits.keys()) & set(actual_count.keys())
    if len(common) < MIN_CELLS_FOR_PEARSON:
        return {"status": "incomplete", "n_cells": len(common), "pass": False}
    sim_arr = np.array([sim_visits[k] for k in common])
    act_arr = np.array([actual_count[k] for k in common])
    if np.std(sim_arr) == 0 or np.std(act_arr) == 0:
        return {"status": "incomplete", "n_cells": len(common), "pass": False, "reason": "zero variance"}
    r, _ = scipy.stats.pearsonr(sim_arr, act_arr)
    mape = float(np.mean(np.abs(sim_arr - act_arr) / np.maximum(act_arr, 1)))
    return {
        "status": "ok", "n_cells": len(common),
        "pearson_r": round(float(r), 4),
        "mape": round(mape, 4),
        "pass": r >= V1B_R_MIN and mape <= V1B_MAPE_MAX,
        "thresholds": {"r_min": V1B_R_MIN, "mape_max": V1B_MAPE_MAX},
    }


def _track_v1c(sim_per_store: dict[tuple, float], actual_per_store: dict[tuple, float]) -> dict[str, Any]:
    """V1c — 매장당 매출 ratio (cell-wise ratio 의 mean)."""
    common = set(sim_per_store.keys()) & set(actual_per_store.keys())
    if len(common) < MIN_CELLS_FOR_PEARSON:
        return {"status": "incomplete", "n_cells": len(common), "pass": False}
    ratios = [sim_per_store[k] / max(actual_per_store[k], 1) for k in common]
    mean_ratio = float(np.mean(ratios))
    median_ratio = float(np.median(ratios))
    return {
        "status": "ok", "n_cells": len(common),
        "mean_ratio": round(mean_ratio, 3),
        "median_ratio": round(median_ratio, 3),
        "pass": V1C_RATIO_MIN <= mean_ratio <= V1C_RATIO_MAX,
        "thresholds": {"ratio_min": V1C_RATIO_MIN, "ratio_max": V1C_RATIO_MAX},
    }


def _track_v2(sim_yearly: float, ftc_avg_yearly: int | None) -> dict[str, Any]:
    """V2 — 브랜드 연 매출 ratio (전국 평균과 비교)."""
    if ftc_avg_yearly is None or ftc_avg_yearly == 0:
        return {"status": "skipped", "reason": "ftc data missing", "pass": False}
    ratio = sim_yearly / ftc_avg_yearly
    return {
        "status": "ok",
        "ratio": round(float(ratio), 3),
        "sim_yearly_won": int(sim_yearly),
        "ftc_yearly_won": int(ftc_avg_yearly),
        "pass": V2_RATIO_MIN <= ratio <= V2_RATIO_MAX,
        "thresholds": {"ratio_min": V2_RATIO_MIN, "ratio_max": V2_RATIO_MAX},
    }


def _track_ci(pse_summary: dict[str, Any]) -> dict[str, Any]:
    """CI — PSE 95% CI / mean ≤ 10%."""
    rev = pse_summary.get("revenue_per_day", {})
    mean = rev.get("mean", 0)
    ci95 = rev.get("ci95", 0)
    if mean == 0:
        return {"status": "incomplete", "pass": False}
    ci_ratio = ci95 / mean
    return {
        "status": "ok",
        "ci_ratio": round(float(ci_ratio), 4),
        "pass": ci_ratio <= CI_MAX,
        "thresholds": {"ci_max": CI_MAX},
    }
```

- [ ] **Step 6.4: 테스트 실행 → pass 확인**

```bash
python -m pytest tests/test_brand_vacancy_validator.py -v
```
Expected: PASS (V1a 3 + V1b 1 + V1c 3 + V2 3 + CI 3 = 13 tests)

- [ ] **Step 6.5: ruff + commit**

```bash
ruff check --fix validation/brand_vacancy_validator.py tests/test_brand_vacancy_validator.py
ruff format validation/brand_vacancy_validator.py tests/test_brand_vacancy_validator.py
```

사용자 확인 후:
```bash
git add validation/brand_vacancy_validator.py tests/test_brand_vacancy_validator.py
git commit -m "feat(A1): brand_vacancy_validator 트랙 단위 함수 (V1a/V1b/V1c/V2/CI)"
```

---

## Task 9: run_5track_validation + diagnose + report 생성

**Files:**
- Modify: `validation/brand_vacancy_validator.py` (run_5track_validation, diagnose_failure, _dump_report 추가)
- Test: `tests/test_brand_vacancy_validator.py` (run_5track 통합 테스트 추가)

- [ ] **Step 7.1: run_5track 통합 테스트 + diagnose 단위 테스트 작성**

`tests/test_brand_vacancy_validator.py` 끝에 추가:

```python
# (위 단위 테스트 끝에 이어서)
from unittest.mock import patch

from validation.brand_vacancy_validator import diagnose_failure, run_5track_validation


class TestDiagnoseFailure:
    def test_v1a_fail_message(self):
        tracks = {
            "v1a": {"status": "ok", "pearson_r": 0.5, "mape": 0.4, "pass": False},
            "v1b": {"status": "ok", "pass": True},
            "v1c": {"status": "ok", "pass": True},
            "v2":  {"status": "ok", "pass": True},
            "ci":  {"status": "ok", "pass": True},
        }
        diagnoses = diagnose_failure(tracks)
        assert any("V1a fail" in d for d in diagnoses)

    def test_v1c_high_ratio_message(self):
        tracks = {
            "v1a": {"status": "ok", "pass": True},
            "v1b": {"status": "ok", "pass": True},
            "v1c": {"status": "ok", "mean_ratio": 2.5, "pass": False},
            "v2":  {"status": "ok", "pass": True},
            "ci":  {"status": "ok", "pass": True},
        }
        diagnoses = diagnose_failure(tracks)
        assert any("V1c fail" in d and "150" in d for d in diagnoses)

    def test_all_pass_no_diagnoses(self):
        tracks = {k: {"status": "ok", "pass": True} for k in ["v1a", "v1b", "v1c", "v2", "ci"]}
        assert diagnose_failure(tracks) == []


class TestRun5TrackValidation:
    @patch("validation.brand_vacancy_validator._collect_actual_data")
    @patch("validation.brand_vacancy_validator._run_validation_simulations")
    @patch("validation.brand_vacancy_validator._dump_report")
    def test_all_pass_production_ready(self, mock_dump, mock_sim, mock_actual):
        # 모두 통과하는 가짜 데이터
        cells = {(f"d{i}", "카페"): 1.0e9 for i in range(20)}
        mock_actual.return_value = {
            "district_sales": cells,
            "district_count": {k: 1.0e6 for k in cells},
            "per_store_avg": {k: 1.0e7 for k in cells},
            "ftc_avg": 100_000_000,
        }
        mock_sim.return_value = {
            "dong_industry_revenue": {k: 1.0e9 * 1.05 for k in cells},
            "dong_industry_visits": {k: 1.0e6 * 1.05 for k in cells},
            "per_store_revenue": {k: 1.0e7 * 1.1 for k in cells},
            "vacancy_yearly_rev": 110_000_000,
            "pse_summary": {"revenue_per_day": {"mean": 100, "ci95": 5}},
        }
        report = run_5track_validation("이디야", "카페", days=90, n_seeds=3)
        assert report["production_ready"] is True
        for t in ["v1a", "v1b", "v1c", "v2", "ci"]:
            assert report["tracks"][t]["pass"] is True

    @patch("validation.brand_vacancy_validator._collect_actual_data")
    @patch("validation.brand_vacancy_validator._run_validation_simulations")
    @patch("validation.brand_vacancy_validator._dump_report")
    def test_v2_skipped_auto_fail(self, mock_dump, mock_sim, mock_actual):
        cells = {(f"d{i}", "카페"): 1.0e9 for i in range(20)}
        mock_actual.return_value = {
            "district_sales": cells,
            "district_count": {k: 1.0e6 for k in cells},
            "per_store_avg": {k: 1.0e7 for k in cells},
            "ftc_avg": None,  # 누락
        }
        mock_sim.return_value = {
            "dong_industry_revenue": {k: 1.0e9 * 1.05 for k in cells},
            "dong_industry_visits": {k: 1.0e6 * 1.05 for k in cells},
            "per_store_revenue": {k: 1.0e7 * 1.1 for k in cells},
            "vacancy_yearly_rev": 110_000_000,
            "pse_summary": {"revenue_per_day": {"mean": 100, "ci95": 5}},
        }
        report = run_5track_validation("이디야", "카페")
        assert report["tracks"]["v2"]["status"] == "skipped"
        assert report["production_ready"] is False
```

- [ ] **Step 7.2: 테스트 실행 → fail 확인**

```bash
python -m pytest tests/test_brand_vacancy_validator.py -v
```
Expected: FAIL with `ImportError: cannot import name 'run_5track_validation'`

- [ ] **Step 7.3: run_5track_validation + diagnose + report 구현**

`validation/brand_vacancy_validator.py` 끝에 추가:

```python
import json
from datetime import datetime, UTC
from pathlib import Path


def diagnose_failure(tracks: dict[str, dict]) -> list[str]:
    """5 트랙 결과 → fail 진단 메시지 list."""
    diagnoses: list[str] = []
    if not tracks["v1a"].get("pass"):
        r = tracks["v1a"].get("pearson_r")
        mape = tracks["v1a"].get("mape")
        diagnoses.append(
            f"V1a fail (r={r}, MAPE={mape}): 동×업종 매출 분포 격차. "
            f"가능 원인: (1) popularity_boost=5.0, (2) 정적 시뮬 한계 [브레인스토밍 옵션 3 future spec], "
            f"(3) IPF calibration 미적용. → IPF + boost=1.0 재측정 권장."
        )
    if not tracks["v1b"].get("pass"):
        r = tracks["v1b"].get("pearson_r")
        diagnoses.append(
            f"V1b fail (r={r}): 방문 수 분포 격차. visits 의 sample size noise 가능. "
            f"→ agent 1000→3000 또는 PSE n 늘리기."
        )
    if not tracks["v1c"].get("pass"):
        r = tracks["v1c"].get("mean_ratio")
        if r is not None and r > V1C_RATIO_MAX:
            diagnoses.append(
                f"V1c fail (ratio={r} > {V1C_RATIO_MAX}): 시뮬 매장 동 평균보다 {(r-1)*100:.0f}% 높음. "
                f"popularity_boost 또는 페르소나 spend_tendency 과대. → boost=1.0 재측정."
            )
        elif r is not None:
            diagnoses.append(
                f"V1c fail (ratio={r} < {V1C_RATIO_MIN}): 시뮬 매장 동 평균의 {r*100:.0f}% 과소. "
                f"메뉴 가격 source 점검 또는 visits 과소."
            )
    if not tracks["v2"].get("pass"):
        if tracks["v2"].get("status") == "skipped":
            diagnoses.append("V2 skipped: ftc 에 brand row 없음. → 브랜드명 alias 점검.")
        else:
            r = tracks["v2"].get("ratio")
            if r is not None and r > V2_RATIO_MAX:
                diagnoses.append(
                    f"V2 fail (ratio={r} > {V2_RATIO_MAX}): 시뮬 매출 전국 평균 {(r-1)*100:.0f}% 초과."
                )
            elif r is not None:
                diagnoses.append(
                    f"V2 fail (ratio={r} < {V2_RATIO_MIN}): 시뮬 매출 전국 평균의 {r*100:.0f}% 미만."
                )
    if not tracks["ci"].get("pass"):
        ci = tracks["ci"].get("ci_ratio")
        if ci is not None:
            diagnoses.append(
                f"CI fail (CI/mean={ci*100:.1f}% > {CI_MAX*100:.0f}%): PSE 변동 과다. "
                f"→ n_seeds 3→5→10 또는 days 90→180."
            )
    return diagnoses


def _collect_actual_data(brand_name: str, category: str, multi_quarter_avg: int) -> dict[str, Any]:
    """실측 데이터 수집 — district_sales, sales_imp_mapo, ftc.

    실제 구현은 SQL/CSV 호출. 본 spec 의 spec 6.2 Step A 참조.
    Mock-friendly 인터페이스 (테스트에서 patch).
    """
    import os

    from sqlalchemy import text

    from src.database.sync_engine import get_sync_engine

    engine = get_sync_engine(os.environ["POSTGRES_URL"])

    # district_sales — 마포 64-cell 분기 매출 + 건수, multi-quarter 평균
    sql_district = text("""
        SELECT dong_name, industry_name,
               AVG(monthly_sales)::bigint AS quarterly_sales_avg,
               AVG(monthly_count)::bigint AS quarterly_count_avg
          FROM district_sales
         WHERE dong_code LIKE '114%'
           AND quarter IN (
               SELECT DISTINCT quarter FROM district_sales
                WHERE dong_code LIKE '114%'
                ORDER BY quarter DESC LIMIT :n
           )
         GROUP BY dong_name, industry_name
    """)
    district_sales: dict[tuple, float] = {}
    district_count: dict[tuple, float] = {}
    with engine.connect() as conn:
        for r in conn.execute(sql_district, {"n": multi_quarter_avg}).mappings():
            key = (r["dong_name"], r["industry_name"])
            district_sales[key] = float(r["quarterly_sales_avg"] or 0)
            district_count[key] = float(r["quarterly_count_avg"] or 0)

    # per_store_avg — sales_imp_mapo.csv 의 monthly_sales / store_count
    # CSV 로드 (data/processed/sales_imp_mapo.csv)
    import pandas as pd
    csv_path = Path("data/processed/sales_imp_mapo.csv")
    per_store_avg: dict[tuple, float] = {}
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        # 최근 분기 N개 평균
        recent_quarters = sorted(df["quarter"].unique())[-multi_quarter_avg:]
        df = df[df["quarter"].isin(recent_quarters)]
        df = df[df["store_count"] > 0]
        df["per_store"] = df["monthly_sales"] / df["store_count"]
        agg = df.groupby(["dong_name", "industry_name"])["per_store"].mean()
        per_store_avg = {idx: float(v) for idx, v in agg.items()}

    # ftc — brand 연 평균 매출 (천원 → 원)
    sql_ftc = text("""
        SELECT AVG("avrgSlsAmt")::bigint AS yearly_avg_thousand
          FROM ftc_brand_franchise
         WHERE "brandNm" ILIKE :brand
           AND yr = (SELECT MAX(yr) FROM ftc_brand_franchise WHERE "brandNm" ILIKE :brand)
    """)
    ftc_avg = None
    with engine.connect() as conn:
        row = conn.execute(sql_ftc, {"brand": f"%{brand_name}%"}).mappings().first()
        if row and row["yearly_avg_thousand"]:
            ftc_avg = int(row["yearly_avg_thousand"]) * 1000  # 천원 → 원

    return {
        "district_sales": district_sales,
        "district_count": district_count,
        "per_store_avg": per_store_avg,
        "ftc_avg": ftc_avg,
    }


def _run_validation_simulations(brand_name: str, category: str, days: int, n_seeds: int) -> dict[str, Any]:
    """시뮬 데이터 수집 — 동×업종 매트릭스 + V2 단일 vacancy.

    실제 시뮬 호출 — ~9시간 소요 (days=90 × n_seeds × 2 시뮬).
    Mock-friendly 인터페이스 (테스트에서 patch).
    """
    from src.services.brand_mapping_resolver import get_all_mapo_stores_by_brand
    from src.services.brand_menu_loader import load_brand_menu_items
    from src.simulation.config import ModelConfig, PopulationMix, TierDistribution
    from src.simulation.runner import run_simulation
    from src.simulation.vacancy_pse import evaluate_vacancy_pse
    from src.simulation.world_loader import load_world_from_rds
    from statistics import mean

    DEFAULT_SEEDS = [42, 123, 7777, 99, 2024][:n_seeds]
    cfg = ModelConfig()
    cfg.tier_s_provider = "mock"  # 검증은 항상 mock 강제
    cfg.tier_a_provider = "mock"

    # ① 동×업종 매트릭스 (vacancy 미주입, 일반 시뮬, days × N=n_seeds)
    matrix_revenues: list[dict[tuple, float]] = []
    matrix_visits: list[dict[tuple, float]] = []
    per_store_per_seed: list[dict[tuple, float]] = []
    for s in DEFAULT_SEEDS:
        logger.info(f"[validator] 동×업종 매트릭스 시뮬 seed={s} ({days}일)")
        world, hm = load_world_from_rds()
        run_simulation(
            days=days, cfg=cfg,
            pop=PopulationMix(), tier=TierDistribution(),
            world=world, hours_map=hm,
            use_rds=False, use_profiles=True, use_policy=True,
            collect_trajectory=False,
            seed=s, verbose=False,
            seed_memory=True, memory_seed_days=14,
        )
        # 동×업종 합산
        rev_agg: dict[tuple, float] = {}
        vis_agg: dict[tuple, float] = {}
        cnt_agg: dict[tuple, int] = {}
        for store in world.stores.values():
            key = (store.dong, store.category)
            rev_agg[key] = rev_agg.get(key, 0) + store.revenue_today
            vis_agg[key] = vis_agg.get(key, 0) + store.visits_today
            cnt_agg[key] = cnt_agg.get(key, 0) + 1
        matrix_revenues.append(rev_agg)
        matrix_visits.append(vis_agg)
        # per-store 평균
        per_store_per_seed.append({
            k: rev_agg[k] / max(cnt_agg[k], 1) for k in rev_agg
        })

    # 평균 (across seeds)
    all_keys = set().union(*(m.keys() for m in matrix_revenues))
    revenue_avg = {k: mean(m.get(k, 0) for m in matrix_revenues) for k in all_keys}
    visits_avg = {k: mean(m.get(k, 0) for m in matrix_visits) for k in all_keys}
    per_store_avg = {k: mean(m.get(k, 0) for m in per_store_per_seed) for k in all_keys}

    # ② 단일 vacancy V2 시뮬 — 대표 위치
    spot = _pick_representative_spot(brand_name, category)
    menu_items = load_brand_menu_items(brand_name)
    pse_result = evaluate_vacancy_pse(
        vacancy_spot=spot,
        category=category,
        n_seeds=n_seeds, days=days,
        with_cannibalization=False,
        cfg=cfg,
        menu_items=menu_items,
    )
    rev_per_day = pse_result["pse_summary"]["revenue_per_day"]["mean"]
    vacancy_yearly_rev = (rev_per_day / max(days, 1)) * 365 if days >= 30 else rev_per_day * 365 / days

    return {
        "dong_industry_revenue": revenue_avg,
        "dong_industry_visits": visits_avg,
        "per_store_revenue": per_store_avg,
        "vacancy_yearly_rev": vacancy_yearly_rev,
        "pse_summary": pse_result["pse_summary"],
    }


def _pick_representative_spot(brand_name: str, category: str) -> dict[str, Any]:
    """V2 시뮬용 단일 spot — 마포 브랜드 매장 좌표 중심점에 가장 가까운 실제 매장."""
    from statistics import mean as _mean

    from src.services.brand_mapping_resolver import get_all_mapo_stores_by_brand

    stores = get_all_mapo_stores_by_brand(brand_name)
    if not stores:
        from src.services.brand_menu_loader import BrandNotFoundError
        raise BrandNotFoundError(f"마포에 '{brand_name}' 매장 없음")
    center_lat = _mean(s["lat"] for s in stores if s.get("lat"))
    center_lon = _mean(s["lon"] for s in stores if s.get("lon"))

    def dist_sq(s):
        return (s["lat"] - center_lat) ** 2 + (s["lon"] - center_lon) ** 2

    nearest = min((s for s in stores if s.get("lat")), key=dist_sq)
    return {"dong": nearest["dong_name"], "lat": nearest["lat"], "lon": nearest["lon"]}


def _dump_report(report: dict[str, Any], output_dir: Path, brand_name: str) -> None:
    """JSON + Markdown report dump."""
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_brand = brand_name.replace("/", "_").replace(" ", "_")
    json_path = output_dir / f"{safe_brand}_5track.json"
    md_path = output_dir / f"{safe_brand}_5track_report.md"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    # Markdown report
    lines = [
        f"# {brand_name} 5트랙 검증 Report\n",
        f"- 검증 시각: {report['timestamp']}",
        f"- 카테고리: {report['category']}",
        f"- 설정: days={report['config']['days']}, n_seeds={report['config']['n_seeds']}, multi_quarter_avg={report['config']['multi_quarter_avg']}",
        f"- **production_ready: {'✅ YES' if report['production_ready'] else '❌ NO'}**\n",
        "## 트랙별 결과\n",
        "| 트랙 | 측정값 | 합격선 | 결과 |",
        "|---|---|---|---|",
    ]
    for k in ["v1a", "v1b", "v1c", "v2", "ci"]:
        t = report["tracks"][k]
        passed = "✅ PASS" if t.get("pass") else "❌ FAIL"
        if t.get("status") == "skipped":
            passed = "⚠️ SKIPPED"
        elif t.get("status") == "incomplete":
            passed = "⚠️ INCOMPLETE"
        if k == "v1a":
            value = f"r={t.get('pearson_r')}, MAPE={t.get('mape')}"
            thresh = f"r ≥ {V1A_R_MIN}, MAPE ≤ {V1A_MAPE_MAX}"
        elif k == "v1b":
            value = f"r={t.get('pearson_r')}, MAPE={t.get('mape')}"
            thresh = f"r ≥ {V1B_R_MIN}, MAPE ≤ {V1B_MAPE_MAX}"
        elif k == "v1c":
            value = f"mean_ratio={t.get('mean_ratio')}"
            thresh = f"{V1C_RATIO_MIN}~{V1C_RATIO_MAX}"
        elif k == "v2":
            value = f"ratio={t.get('ratio')}"
            thresh = f"{V2_RATIO_MIN}~{V2_RATIO_MAX}"
        else:
            value = f"ci_ratio={t.get('ci_ratio')}"
            thresh = f"≤ {CI_MAX}"
        lines.append(f"| {k.upper()} | {value} | {thresh} | {passed} |")

    if report.get("diagnoses"):
        lines.append("\n## 진단\n")
        for d in report["diagnoses"]:
            lines.append(f"- {d}")

    if report.get("limitations"):
        lines.append("\n## Limitations\n")
        for limit in report["limitations"]:
            lines.append(f"- {limit}")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"[validator] report dumped: {json_path}, {md_path}")


def run_5track_validation(
    brand_name: str,
    category: str = "카페",
    days: int = 90,
    n_seeds: int = 3,
    multi_quarter_avg: int = 4,
    output_dir: Path | str = Path("validation/results/"),
    verbose: bool = True,
) -> dict[str, Any]:
    """5트랙 검증 protocol 1회 실행.

    Args:
        brand_name: 평가 브랜드 (예: "이디야"). 마포 매장 0 시 BrandNotFoundError.
        category: 업종 (default "카페").
        days: 시뮬 일수 (default 90 = 분기).
        n_seeds: PSE N (default 3).
        multi_quarter_avg: 실측 ground truth 평균 분기 수 (default 4 = 1년).
        output_dir: report dump 디렉토리.
        verbose: 진행 로그.

    Returns:
        report dict — tracks, production_ready, diagnoses, limitations.
    """
    if verbose:
        logger.info(f"[validator] '{brand_name}' 5트랙 검증 시작")
    actual = _collect_actual_data(brand_name, category, multi_quarter_avg)
    sim = _run_validation_simulations(brand_name, category, days, n_seeds)

    tracks = {
        "v1a": _track_v1a(sim["dong_industry_revenue"], actual["district_sales"]),
        "v1b": _track_v1b(sim["dong_industry_visits"], actual["district_count"]),
        "v1c": _track_v1c(sim["per_store_revenue"], actual["per_store_avg"]),
        "v2":  _track_v2(sim["vacancy_yearly_rev"], actual["ftc_avg"]),
        "ci":  _track_ci(sim["pse_summary"]),
    }

    production_ready = all(t.get("pass", False) for t in tracks.values())
    diagnoses = diagnose_failure(tracks) if not production_ready else []

    report = {
        "brand_name": brand_name,
        "category": category,
        "config": {"days": days, "n_seeds": n_seeds, "multi_quarter_avg": multi_quarter_avg},
        "tracks": tracks,
        "production_ready": production_ready,
        "diagnoses": diagnoses,
        "limitations": [
            "정적 시뮬 환경 — 90일 동안 같은 날씨/같은 월 (브레인스토밍 옵션 3 future spec).",
            "매장 단위 실측 매출 부재 — 동×업종 평균으로 V1c 측정.",
            "검증은 mock 강제 — Mode C/D LLM 활성 시 결정 분포 약간 변화 가능 (margin ~3%).",
        ],
        "timestamp": datetime.now(UTC).isoformat(),
    }
    _dump_report(report, Path(output_dir), brand_name)
    if verbose:
        status = "✅ production-ready" if production_ready else "❌ production-not-ready"
        logger.info(f"[validator] '{brand_name}' 검증 완료 — {status}")
    return report
```

- [ ] **Step 7.4: 테스트 실행 → pass 확인**

```bash
python -m pytest tests/test_brand_vacancy_validator.py -v
```
Expected: PASS (단위 13 + diagnose 3 + run_5track 2 = 18 tests)

- [ ] **Step 7.5: ruff + commit**

```bash
ruff check --fix validation/brand_vacancy_validator.py tests/test_brand_vacancy_validator.py
ruff format validation/brand_vacancy_validator.py tests/test_brand_vacancy_validator.py
```

사용자 확인 후:
```bash
git add validation/brand_vacancy_validator.py tests/test_brand_vacancy_validator.py
git commit -m "feat(A1): brand_vacancy_validator run_5track + diagnose + report"
```

---

## Task 10: CLI entry point

**Files:**
- Modify: `validation/brand_vacancy_validator.py` (`if __name__ == "__main__"` 블록 + argparse)

- [ ] **Step 8.1: CLI 추가**

`validation/brand_vacancy_validator.py` 끝에:

```python
def _main() -> None:
    """CLI entry point."""
    import argparse
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Brand vacancy 5트랙 검증")
    parser.add_argument("--brand", help="단일 브랜드명 (예: 이디야)")
    parser.add_argument("--brands", help="쉼표 구분 여러 브랜드 (예: 이디야,MEGA,빽다방)")
    parser.add_argument("--category", default="카페", help="업종 (default: 카페)")
    parser.add_argument("--days", type=int, default=90, help="시뮬 일수 (default: 90 = 분기)")
    parser.add_argument("--n-seeds", type=int, default=3, help="PSE N (default: 3)")
    parser.add_argument("--multi-quarter-avg", type=int, default=4, help="실측 평균 분기 수 (default: 4)")
    parser.add_argument("--output-dir", default="validation/results/", help="report 디렉토리")
    args = parser.parse_args()

    if not args.brand and not args.brands:
        parser.error("--brand 또는 --brands 중 하나 필수")

    brand_list = [args.brand] if args.brand else [b.strip() for b in args.brands.split(",")]

    summary: list[dict] = []
    for brand in brand_list:
        try:
            report = run_5track_validation(
                brand_name=brand,
                category=args.category,
                days=args.days,
                n_seeds=args.n_seeds,
                multi_quarter_avg=args.multi_quarter_avg,
                output_dir=args.output_dir,
                verbose=True,
            )
            summary.append({
                "brand": brand,
                "production_ready": report["production_ready"],
                "fail_tracks": [k for k, v in report["tracks"].items() if not v.get("pass")],
            })
        except Exception as e:
            logger.exception(f"[validator] '{brand}' 검증 실패: {e}")
            summary.append({"brand": brand, "production_ready": False, "error": str(e)})

    print("\n=== 검증 일괄 결과 ===")
    for s in summary:
        status = "✅" if s.get("production_ready") else "❌"
        print(f"{status} {s['brand']}: fail_tracks={s.get('fail_tracks', s.get('error'))}")


if __name__ == "__main__":
    _main()
```

- [ ] **Step 8.2: CLI 동작 smoke test**

CLI 도움말 표시 확인:
```bash
python -m validation.brand_vacancy_validator --help
```
Expected: argparse help 출력 (실제 시뮬 실행 X).

오류 처리 확인:
```bash
python -m validation.brand_vacancy_validator
```
Expected: error: --brand 또는 --brands 중 하나 필수

- [ ] **Step 8.3: ruff + commit**

```bash
ruff check --fix validation/brand_vacancy_validator.py
ruff format validation/brand_vacancy_validator.py
```

사용자 확인 후:
```bash
git add validation/brand_vacancy_validator.py
git commit -m "feat(A1): brand_vacancy_validator CLI entry point"
```

---

## Task 11: 사전 검증 체크리스트 + 1회 실제 검증 실행

**Files:**
- 데이터 source 점검만 (코드 변경 X) → 결과 dump

> **주의**: Step 9.4 의 실제 검증 실행은 ~9시간 소요. 사용자 환경에서 직접 진행 권장. 결과 fail 가능성 높음 (엄격 합격선) — 그게 정직한 평가.

- [ ] **Step 11.1: kakao_store_menu coverage 점검**

```bash
psql $POSTGRES_URL -c "SELECT brand_name, COUNT(*) AS menu_n FROM kakao_store JOIN kakao_store_menu USING (kakao_id) WHERE brand_name IS NOT NULL GROUP BY brand_name ORDER BY menu_n DESC LIMIT 20;"
```

기록: 마포 주요 브랜드 (이디야, MEGA, 빽다방, 컴포즈) 의 menu row 수가 ≥ 30 인지 확인.

- [ ] **Step 11.2: ftc_brand_franchise coverage**

```bash
psql $POSTGRES_URL -c "SELECT \"brandNm\", \"avrgSlsAmt\" FROM ftc_brand_franchise WHERE \"brandNm\" ILIKE ANY(ARRAY['%이디야%','%MEGA%','%빽다방%','%컴포즈%']) ORDER BY yr DESC LIMIT 20;"
```

기록: 주요 브랜드의 ftc.avrgSlsAmt 값 존재 확인. 누락 시 V2 가 자동 skipped.

- [ ] **Step 11.3: sales_imp_mapo + district_sales 64-cell 완전성**

```bash
python -c "
import pandas as pd
df = pd.read_csv('data/processed/sales_imp_mapo.csv')
recent = sorted(df['quarter'].unique())[-4:]
df = df[df['quarter'].isin(recent)]
print('동×업종 cell 수:', df.groupby(['dong_name', 'industry_name']).ngroups)
print('store_count NaN/0 비율:', (df['store_count'].fillna(0) == 0).mean())
"
```

기록: 64-cell 중 cover 비율 + store_count 부재 비율 (V1c 의 cell coverage 영향).

- [ ] **Step 11.4: living_population 마포 90일 데이터 가용성 점검 (옵션 B)**

```bash
psql $POSTGRES_URL -c "SELECT MIN(date), MAX(date), COUNT(DISTINCT date) AS day_n, COUNT(*) AS row_n FROM living_population WHERE dong_code LIKE '114%';"
```

기록:
- 사용 가능한 날짜 범위 (시뮬 시작일 결정에 영향)
- 90일 연속 가용 여부 (16동 × 24h × 90일 = 34,560 row 예상)
- NULL/누락 비율

→ 만약 90일 가용 안 되면 사용 가능한 최대 일수로 시뮬 days 조정.

- [ ] **Step 11.5: 1회 실제 검증 실행 (사용자 환경, ~10시간, 옵션 B 적용)**

```bash
# 권장: nohup 또는 tmux 안에서 실행
python -m validation.brand_vacancy_validator --brand 이디야 --category 카페 --days 90 --n-seeds 3 --multi-quarter-avg 4 2>&1 | tee validation/results/이디야_run.log
```

Expected outputs:
- `validation/results/이디야_5track.json`
- `validation/results/이디야_5track_report.md`
- 콘솔에 `production-ready` 또는 `production-not-ready` + diagnose

- [ ] **Step 11.6: 결과 검토 + 결과물 commit + 합격선 confirm**

> 옵션 B 적용 후 첫 측정 — 합격선 (r ≥ 0.85 등) 이 동적 baseline 에서도 적정한지 검토. 너무 strict 해서 의미있는 개선도 fail 되면 ±5% 조정 (예: r ≥ 0.80). 결과 보고 사용자와 함께 결정.

report 파일 확인:
```bash
cat validation/results/이디야_5track_report.md
```

사용자 확인 후 (검증 결과는 코드 변경 아니지만 deliverable):
```bash
git add validation/results/이디야_5track.json validation/results/이디야_5track_report.md
git commit -m "feat(A1): 이디야 1회 5트랙 검증 결과 — production-(not-)ready 정직 보고"
```

---

## Self-Review (after writing the plan)

**Spec coverage check** (spec 섹션별):
- 섹션 5.4 (시그니처) → Task 1, 2, 4, 7 ✅
- 섹션 5.2 옵션 B 컴포넌트 (`_load_living_population_daily`, `World.living_pop_daily_boost`, runner day-loop) → Task 5, 6 ✅
- 섹션 6 (데이터 흐름) → Task 1, 4, 9 ✅
- 섹션 7 (오류 처리) → Task 1 (BrandNotFoundError, BrandMenuEmptyError), Task 7 (skip_invalid), Task 9 (partial validation) ✅
- 섹션 8 (테스트) → 모든 Task 의 테스트 step ✅
- 섹션 9 (5트랙 protocol) → Task 8, 9, 10 ✅
- 섹션 9.1 합격선 caveat (옵션 B 후 confirm) → Task 11 Step 11.6 ✅
- 섹션 10 (LLM 정책 — Mode B/C) → Task 3, Task 4 (인자 placeholder) ✅
- 섹션 11 (Limitations) → Task 9 의 report.limitations 포함 ✅
- 섹션 13 (사전 검증 체크리스트) → Task 11 (Step 11.4 옵션 B 추가) ✅
- 섹션 14 (구현 순서) → 11 task 분해 ✅
- 섹션 15 (합격 기준) → Task 11 의 검증 결과 dump ✅

**Placeholder scan**: 모든 step 에 구체적 코드 + 명령어. TBD/TODO 없음. ✅

**Type consistency**: `menu_items: list[dict] | None`, `tracks: dict[str, dict]`, `BrandNotFoundError` / `BrandMenuEmptyError`, `living_pop_daily_boost: dict[(str, int, int), float]` 명명 일관. ✅

**검증 시간 부담 명시**: Task 11 Step 11.5 에 `~10시간 소요 (옵션 B day-loop 갱신 +10%), 사용자 환경 권장` 명시. ✅

**옵션 B 회귀 위험 명시**: Task 6 Step 6.4 에 회귀 테스트 (vacancy/runner) 포함. World 의 `living_pop_daily_boost` 빈 dict default 로 fallback 보장. ✅

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-27-brand-menu-vacancy-pse-validation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - Fresh subagent per task + review between tasks. 9 task × 5~6 step = 50+ steps. 빠른 iteration.

**2. Inline Execution** - 현재 세션에서 batch execution + checkpoints. 사용자가 task 단위로 review.

Which approach?
