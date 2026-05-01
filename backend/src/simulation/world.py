"""마포구 환경 (World) - 동, 점포, 시간 관리."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .config import MAPO_DONGS

if TYPE_CHECKING:
    from .agents import Agent


@dataclass
class Store:
    """점포 - 마포구 실제 점포의 단순화 모델."""

    store_id: int
    name: str
    dong: str
    category: str  # 카페/음식점/편의점/주점/기타
    seats: int = 30
    rating: float = 4.0  # 1~5
    price_level: int = 2  # 1(저)~3(고)
    visits_today: int = 0
    revenue_today: float = 0.0
    is_open_now: bool = True  # 매 시간 갱신
    lat: float | None = None
    lon: float | None = None
    # kakao_store_menu JOIN 결과
    menu_items: list[dict] = field(default_factory=list)  # [{name, price}]
    # district_sales_seoul / mapo_sns_sentiment 기반 매장 인기 가중치
    popularity_boost: float = 1.0

    @property
    def occupancy(self) -> float:
        return min(1.0, self.visits_today / max(self.seats, 1))


@dataclass
class World:
    """마포구 World - 시간/공간/점포/에이전트 컨테이너."""

    current_hour: int = 6
    current_day: int = 1
    weekday: int = 0  # 0=월 ~ 6=일
    is_weekend: bool = False
    is_holiday: bool = False
    holiday_name: str | None = None
    weather: str = "맑음"  # 맑음/흐림/비/눈
    temperature: float = 18.0  # 섭씨
    rain_mm: float = 0.0  # 일 강수량 (mm)
    price_multiplier: float = 1.0  # 임대료 충격 등 가격 배수
    use_dsl: bool = False  # True면 모든 Tier가 brain.dsl_decide() 호출

    dongs: list[str] = field(default_factory=lambda: list(MAPO_DONGS))
    stores: dict[int, Store] = field(default_factory=dict)
    stores_by_dong: dict[str, list[int]] = field(default_factory=dict)
    agents: list["Agent"] = field(default_factory=list)

    # living_population 기반 실데이터 가중치
    # {(age_group, dong, hour, weekday): boost 0.5~2.0}
    time_age_boost: dict = field(default_factory=dict)

    # 지하철 시간대별 외부유입 (subway_inflow_by_dong_hour.csv)
    # {(dong, hour): {"board": x, "alight": y, "net_inflow": z}}
    subway_inflow: dict = field(default_factory=dict)

    # inflow_score (외부 모듈 산출) — {dong_name: 10~100 점수}
    # 외부 inflow potential + destination 자산 종합. score_store 에서
    # ext_commuter/ext_visitor 매장 선호 boost 로 사용 (Option E).
    # 비어있으면 boost 미적용 (1.0 multiplier) — 기존 동작 보존.
    ofs_dong_score: dict[str, float] = field(default_factory=dict)

    # seoul_adstrd_flpop 기반 동×시간×요일 안정 평균 boost (분기 단위)
    # {(dong_name, hour, weekday): ratio 0.5~2.0} — 동 평균=1.0
    # time_age_boost (grid 기반) 와 별개로 score_store 에서 곱셈 결합.
    adstrd_flpop_boost: dict = field(default_factory=dict)

    # ---------------------------
    # 옵션 B (2026-04-27): living_population 기반 일별 boost
    # ---------------------------
    # {(dong_name, hour, day_idx): ratio 0.5~2.0} — 매일 다른 boost (90일 분량).
    # day_idx = 0 (시뮬 첫째 날) ~ days-1.
    # 빈 dict 면 기존 정적 adstrd_flpop_boost fallback (하위 호환성).
    living_pop_daily_boost: dict = field(default_factory=dict)

    # Policy Generator 캐시 — {policy_id: PersonaPolicy}
    # 활성 시 use_policy=True → agents.decide() 가 policy_executor.policy_decide 호출
    policy_cache: dict = field(default_factory=dict)
    use_policy: bool = False

    # Realism v10 — 환경 변수
    air_quality_pm25: float = 0.0  # 미세먼지 μg/m³ (>75 bad, >150 very bad)
    month: int = 4  # 현재 월 (계절 보정)
    is_payday: bool = False  # 월급일 +/- 3일

    # 이벤트 로그 (분석용)
    event_log: list[dict] = field(default_factory=list)

    def add_store(self, store: Store) -> None:
        self.stores[store.store_id] = store
        self.stores_by_dong.setdefault(store.dong, []).append(store.store_id)

    def stores_in_dong(self, dong: str, category: str | None = None) -> list[Store]:
        ids = self.stores_by_dong.get(dong, [])
        out = [self.stores[i] for i in ids]
        if category:
            out = [s for s in out if s.category == category]
        return out

    def reset_daily(self) -> None:
        for s in self.stores.values():
            s.visits_today = 0
            s.revenue_today = 0.0
        self.current_day += 1

    def log_event(self, **kwargs) -> None:
        self.event_log.append(
            {
                "day": self.current_day,
                "hour": self.current_hour,
                **kwargs,
            }
        )


def seed_synthetic_world(
    n_stores_per_dong: int = 30,
    seed: int = 42,
) -> World:
    """RDS 미연동 PoC용 합성 World 생성."""
    rng = random.Random(seed)
    world = World()

    categories = ["카페", "음식점", "편의점", "주점", "기타"]
    cat_weights = [0.30, 0.40, 0.10, 0.15, 0.05]

    sid = 1
    for dong in MAPO_DONGS:
        for _ in range(n_stores_per_dong):
            cat = rng.choices(categories, weights=cat_weights)[0]
            world.add_store(
                Store(
                    store_id=sid,
                    name=f"{dong}_{cat}_{sid}",
                    dong=dong,
                    category=cat,
                    seats=rng.randint(8, 80),
                    rating=round(rng.uniform(3.0, 5.0), 1),
                    price_level=rng.randint(1, 3),
                )
            )
            sid += 1
    return world
