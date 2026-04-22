"""에이전트 클래스 - Tier S/A/B 분류 + 행동 정의."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .brain import LLMBrain
    from .profile_builder import AgentProfile
    from .world import World


# ---------------------------------------------------------------
# 요일 × 시간 × 연령 × 동 × 카테고리 가중치
# (실데이터 기반 - living_population + district_sales_seoul)
# ---------------------------------------------------------------
def age_dong_time_boost(
    age: int,
    dong: str,
    category: str,
    hour: int,
    weekday: int,
    archetype: str | None = None,
    time_age_boost: dict | None = None,
) -> float:
    """실데이터 기반 교차 가중치.

    1) living_population (연령그룹 × 동 × 시간 × 요일) → 실 생활인구 비율
    2) DONG_CHARACTER.cat_boost → 동별 업종 매출 통념 (district_sales_seoul로 이미 popularity_boost 반영됨)
    3) 아키타입별 소수 규칙만 유지 (실데이터에 없는 행동 패턴)
    """
    from .config import DONG_CHARACTER
    from .profile_builder import age_to_group

    w = 1.0

    # 1) 실데이터 시간×동×연령×요일 boost (0.5~2.0)
    if time_age_boost:
        g = age_to_group(age)
        key = (g, dong, hour % 24, weekday)
        real = time_age_boost.get(key)
        if real is not None:
            w *= real
        # 없으면 1.0 그대로

    # 2) 동×카테고리 상권 DNA (매출 데이터 기반 static)
    char = DONG_CHARACTER.get(dong, {})
    w *= char.get("cat_boost", {}).get(category, 1.0)

    # 3) 아키타입 — 실데이터에 없는 세분 행동만 유지
    if archetype == "bcst" and dong == "상암동":  # 방송사 새벽 야식
        # 편의점은 시뮬 제외 — 음식점만 야식 부스트
        if hour in (23, 0, 1, 2) and category == "음식점":
            w *= 1.6
    if archetype == "prnt" and weekday >= 5:  # 유아 부모 주말
        if dong in ("상암동", "성산2동", "망원2동"):
            w *= 1.2

    return w


class Tier(str, Enum):
    S = "S"  # 풀 LLM (Haiku + cache)
    A = "A"  # SLM (Gemini Flash)
    B = "B"  # 규칙 기반 (LLM 0)


class Role(str, Enum):
    RESIDENT = "resident"  # 마포 거주자
    COMMUTER = "commuter"  # 마포 내 통근자
    VISITOR = "visitor"  # 단기 방문 (마포 내)
    OWNER = "owner"  # 점주
    EXT_COMMUTER = "ext_commuter"  # 외부→마포 출근 (강남/여의도/종로 등)
    EXT_VISITOR = "ext_visitor"  # 외부→마포 저녁/주말 방문


@dataclass
class Decision:
    """에이전트의 한 시점 의사결정."""

    action: str  # visit/work/rest/move/leave
    target_dong: str | None = None
    target_store_id: int | None = None
    spend: float = 0.0
    reason: str = ""  # Tier S만 채움 (스토리용)


@dataclass
class Agent:
    """기본 에이전트."""

    agent_id: int
    tier: Tier
    role: Role
    name: str
    age: int
    gender: str  # M/F
    home_dong: str
    work_dong: str | None = None
    income_level: int = 2  # 1(저)~3(고)
    budget_today: float = 30000.0
    visited_today: list[int] = field(default_factory=list)
    spent_today: float = 0.0
    current_dong: str = ""
    last_action: str = "rest"

    # Tier S만 사용
    persona_id: str | None = None
    memory_summary: str = ""

    # DB 기반 개인 프로필 (전 tier 공통)
    profile: "AgentProfile | None" = None

    # 사회적 상호작용 (원시어 DSL 대화용)
    friends: list[int] = field(default_factory=list)
    pending_invites: list[dict] = field(default_factory=list)
    store_bias: dict[int, float] = field(default_factory=dict)  # store_id → 가중치

    # External 에이전트 진입/퇴장 시간 (지하철 inflow로 calibrate)
    arrival_hour: int = 8
    departure_hour: int = 18

    # Realism v10 — 체류·이동·학습·친구 동반
    busy_until_hour: int = -1  # 매장 체류 중 끝나는 시간 (-1이면 idle)
    in_transit_until: int = -1  # 이동 중 도착 시간
    store_satisfaction: dict[int, float] = field(default_factory=dict)  # store_id → 0~1 만족도
    friend_visits: list[tuple[int, int]] = field(default_factory=list)  # 친구가 최근 간 (store_id, hour)

    def __post_init__(self):
        if not self.current_dong:
            self.current_dong = self.home_dong

    # -----------------------------------------------------------
    # 의사결정 라우터 - tier에 따라 다른 경로
    # DSL 모드면 모든 Tier가 brain.dsl_decide() 호출
    # -----------------------------------------------------------
    def decide(self, world: "World", brain: "LLMBrain", rng: random.Random) -> Decision:
        # Policy Generator 모드 — LLM 호출 0회, 순수 Python 점수 함수
        if getattr(world, "use_policy", False):
            from .policy_executor import policy_decide

            return policy_decide(self, world, rng)

        # DSL 모드 — 전원 LLM (Tier B 포함), Tier별 프롬프트 깊이만 다름
        if getattr(world, "use_dsl", False):
            return brain.dsl_decide(self, world)

        # 기존 풀 JSON 모드
        if self.tier == Tier.B:
            return self._rule_decide(world, rng)
        if self.tier == Tier.A:
            return brain.fast_decide(self, world)
        return brain.smart_decide(self, world)

    # -----------------------------------------------------------
    # Tier B: 규칙 기반 (LLM 호출 0)
    # profile 참조로 개인별 취향 반영
    # -----------------------------------------------------------
    def _rule_decide(self, world: "World", rng: random.Random) -> Decision:
        h = world.current_hour

        # 점주는 영업시간 동안 가게에 머무름
        if self.role == Role.OWNER:
            if 9 <= h <= 22:
                return Decision(action="work", target_dong=self.home_dong)
            return Decision(action="rest")

        # External_Commuter: arrival_hour 외부→마포, departure_hour 마포→외부
        if self.role == Role.EXT_COMMUTER:
            if h == self.arrival_hour and self.current_dong == "외부":
                self.current_dong = self.work_dong or self.home_dong
                return Decision(action="move", target_dong=self.current_dong)
            if h == self.departure_hour and self.current_dong != "외부":
                self.current_dong = "외부"
                return Decision(action="move", target_dong="외부")
            if self.current_dong == "외부":
                return Decision(action="rest")
            # 마포 시간대 — 일반 의사결정 진행

        # External_Visitor: arrival_hour 외부→마포, departure_hour 마포→외부
        if self.role == Role.EXT_VISITOR:
            if h == self.arrival_hour and self.current_dong == "외부":
                self.current_dong = self.work_dong or self.home_dong or "서교동"
                return Decision(action="move", target_dong=self.current_dong)
            if h == self.departure_hour and self.current_dong != "외부":
                self.current_dong = "외부"
                return Decision(action="move", target_dong="외부")
            if self.current_dong == "외부":
                return Decision(action="rest")

        # 친구 초대(INV) 우선 처리 - 해당 시간이 현재면 수락 가중
        for inv in list(self.pending_invites):
            if inv.get("hour") == h and rng.random() < 0.7:
                self.pending_invites.remove(inv)
                # 초대 동으로 이동 또는 직접 매장 선택
                cat = inv.get("cat", "카페")
                target_dong = inv.get("dong", self.current_dong)
                if target_dong != self.current_dong:
                    self.current_dong = target_dong
                return self._pick_store(world, rng, cat)
            # 시간 지난 초대는 삭제
            if inv.get("hour", h) < h:
                self.pending_invites.remove(inv)

        # 식사/카페 시간대 가중치
        meal_hour = h in (12, 13, 18, 19, 20)
        cafe_hour = h in (10, 11, 14, 15, 16)
        leisure_hour = h in (21, 22, 23)

        # 주중 출퇴근
        if self.role == Role.COMMUTER and not world.is_weekend:
            if h in (8, 9):
                return Decision(action="move", target_dong=self.work_dong or self.home_dong)
            if h == 18:
                return Decision(action="move", target_dong=self.home_dong)

        # 날씨 보정: 비/눈 → 이동 확률 감소
        weather_mult = 1.0
        if world.weather in ("비", "눈"):
            weather_mult = 0.4
        elif world.weather == "약한비":
            weather_mult = 0.7
        # 공휴일은 여가 활동 ↑
        holiday_bonus = 1.3 if world.is_holiday else 1.0

        # 목적지 가중치 함수: time_age_boost로 사람 같은 선택
        def weighted_dest_choice() -> str | None:
            others = [d for d in world.dongs if d != self.current_dong]
            if not others:
                return None
            from .profile_builder import age_to_group

            tab = getattr(world, "time_age_boost", None)
            if tab and self.profile:
                g = age_to_group(self.age)
                wd = world.weekday
                weights = [tab.get((g, d, h % 24, wd), 1.0) for d in others]
                return rng.choices(others, weights=weights)[0]
            return rng.choice(others)

        # 점심/저녁에 근처 동 원정 (mobility_score 높을수록 자주)
        mob = self.profile.mobility_score if self.profile else 0.5
        if h in (12, 19, 20) and rng.random() < 0.25 * mob * weather_mult * holiday_bonus:
            target = weighted_dest_choice()
            if target:
                self.current_dong = target
                return Decision(action="move", target_dong=target)

        # Visitor는 1~2시간마다 이동 (관광)
        if self.role == Role.VISITOR and rng.random() < 0.35 * weather_mult * holiday_bonus:
            target = weighted_dest_choice()
            if target:
                self.current_dong = target
                return Decision(action="move", target_dong=target)

        # 휴식 (이른 새벽/늦은 밤)
        if h < 8 or h >= 24:
            return Decision(action="rest")

        # 개인 취향 가중치 (profile 없으면 기본값)
        # 편의점은 시뮬 대상에서 제외 (분석 3종: 음식점/카페/주점)
        if self.profile is not None:
            p_meal = 0.5 + 0.4 * self.profile.pref_restaurant
            p_cafe = 0.2 + 0.4 * self.profile.pref_cafe
            p_pub = 0.1 + 0.3 * self.profile.pref_pub
        else:
            p_meal, p_cafe, p_pub = 0.7, 0.4, 0.3

        # 식사/카페/유흥 결정
        if meal_hour and rng.random() < p_meal:
            return self._pick_store(world, rng, "음식점")
        if cafe_hour and rng.random() < p_cafe:
            return self._pick_store(world, rng, "카페")
        if leisure_hour and rng.random() < p_pub:
            return self._pick_store(world, rng, "주점")

        return Decision(action="rest", target_dong=self.current_dong)

    def _pick_store(self, world: "World", rng: random.Random, category: str) -> Decision:
        candidates = world.stores_in_dong(self.current_dong, category)
        # 영업성 높은 에이전트는 인접 동 매장도 후보 (사람들이 동 경계에 갇히지 않음)
        mob = self.profile.mobility_score if self.profile else 0.5
        if mob > 0.6:
            # 동 좌표 기준 인접 2개 동 매장 추가
            from .profile_builder import age_to_group

            tab = getattr(world, "time_age_boost", None)
            others = [d for d in world.dongs if d != self.current_dong]
            if tab and self.profile:
                g = age_to_group(self.age)
                wd = world.weekday
                h_now = world.current_hour % 24
                ranked = sorted(others, key=lambda d: tab.get((g, d, h_now, wd), 1.0), reverse=True)[:2]
            else:
                ranked = rng.sample(others, min(2, len(others)))
            for d in ranked:
                candidates.extend(world.stores_in_dong(d, category)[:30])  # 인접 동에서 최대 30개

        # 영업시간 필터
        candidates = [s for s in candidates if s.is_open_now]
        if not candidates:
            return Decision(action="rest")

        # 평점 + 가격 민감도 + 친구 추천 + 매출/감성 + 요일×시간×연령×동 교차
        ps = self.profile.price_sensitivity if self.profile else 0.5
        arch = self.persona_id
        h_cur = world.current_hour % 24
        wd = world.weekday
        weights = []
        for s in candidates:
            rating_w = s.rating
            if ps > 0.5:
                price_w = max(0.1, 1.3 - 0.3 * s.price_level)
            else:
                price_w = max(0.1, 0.4 + 0.3 * s.price_level)
            bias = self.store_bias.get(s.store_id, 1.0)
            cross = age_dong_time_boost(
                self.age,
                s.dong,
                s.category,
                h_cur,
                wd,
                arch,
                time_age_boost=getattr(world, "time_age_boost", None),
            )
            weights.append(rating_w * price_w * bias * s.popularity_boost * cross)

        store = rng.choices(candidates, weights=weights)[0]

        # 메뉴가 있으면 실제 메뉴에서 선택 (가성비성향 고려), 없으면 base 가격
        mult = getattr(world, "price_multiplier", 1.0)
        if store.menu_items:
            # 가성비 지향은 저렴한 메뉴, 프리미엄은 비싼 메뉴
            menus = sorted(store.menu_items, key=lambda m: m["price"])
            if ps > 0.5:
                pool = menus[: max(1, len(menus) // 2)]  # 저가 절반
            else:
                pool = menus[-max(1, len(menus) // 2) :]  # 고가 절반
            chosen = rng.choice(pool)
            spend = chosen["price"] * mult
        else:
            base = {"카페": 6000, "음식점": 15000, "편의점": 5000, "주점": 25000}
            spend = base.get(category, 10000) * store.price_level * rng.uniform(0.7, 1.3) * mult

        if spend > self.budget_today - self.spent_today:
            return Decision(action="rest")
        # 다른 동 매장 선택 시 current_dong 갱신 (자연스러운 이동)
        if store.dong != self.current_dong:
            self.current_dong = store.dong
        return Decision(
            action="visit",
            target_dong=store.dong,
            target_store_id=store.store_id,
            spend=round(spend, 0),
        )

    # -----------------------------------------------------------
    # 의사결정 적용 - World 상태 갱신
    # -----------------------------------------------------------
    def apply(self, dec: Decision, world: "World") -> None:
        self.last_action = dec.action

        if dec.action == "move" and dec.target_dong:
            self.current_dong = dec.target_dong

        elif dec.action == "visit" and dec.target_store_id:
            store = world.stores.get(dec.target_store_id)
            if store:
                store.visits_today += 1
                store.revenue_today += dec.spend
                self.visited_today.append(dec.target_store_id)
                self.spent_today += dec.spend
                self.current_dong = store.dong

        elif dec.action == "work":
            # 점주는 자기 가게 매출 반영 (Tier B 점주는 visit 카운트로만)
            pass


# ---------------------------------------------------------------
# 에이전트 팩토리
# ---------------------------------------------------------------
KOREAN_SURNAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임"]
KOREAN_NAMES_M = ["민준", "서준", "도윤", "하준", "지호", "준우", "은우", "선우"]
KOREAN_NAMES_F = ["서연", "지유", "하윤", "서윤", "지우", "수아", "하은", "지아"]


def _gen_name(rng: random.Random, gender: str) -> str:
    sn = rng.choice(KOREAN_SURNAMES)
    given = rng.choice(KOREAN_NAMES_M if gender == "M" else KOREAN_NAMES_F)
    return f"{sn}{given}"


def spawn_agents(
    n_residents: int,
    n_commuters: int,
    n_visitors: int,
    n_owners: int,
    tier_s: int,
    tier_a: int,
    dongs: list[str],
    seed: int = 42,
    use_profiles: bool = False,
    n_ext_commuters: int = 0,
    n_ext_visitors: int = 0,
    subway_inflow: dict | None = None,
) -> list[Agent]:
    """인구 구성과 Tier 비율에 따라 에이전트 생성.

    use_profiles=True면 RDS 기반 ProfileBuilder로 개인화된 속성 생성.
    (동/연령/성별/소득/취향이 모두 실 데이터 분포 반영)
    """
    rng = random.Random(seed)
    agents: list[Agent] = []
    aid = 1

    role_quota = [
        (Role.RESIDENT, n_residents),
        (Role.COMMUTER, n_commuters),
        (Role.VISITOR, n_visitors),
        (Role.OWNER, n_owners),
        (Role.EXT_COMMUTER, n_ext_commuters),
        (Role.EXT_VISITOR, n_ext_visitors),
    ]

    # 프로필 일괄 생성 (DB 1회 접속)
    profiles: list = []
    if use_profiles:
        from .profile_builder import ProfileBuilder

        pb = ProfileBuilder(seed=seed)
        counts = {role: n for role, n in role_quota}
        profiles = pb.sample_many(counts)

    # Commuter는 오피스 동(상암/공덕/도화/용강 등)에 출근 — 현실 반영
    from .config import OFFICE_DONGS, NIGHTLIFE_DONGS, TRENDY_DONGS

    office_pool = OFFICE_DONGS if OFFICE_DONGS else dongs
    visit_pool = NIGHTLIFE_DONGS + TRENDY_DONGS if (NIGHTLIFE_DONGS and TRENDY_DONGS) else dongs

    # 지하철 inflow 기반 ext_commuter / ext_visitor (도착동, 진입시간) 가중치 샘플
    # 진입: 6-10시 양수 net_inflow / 17-22시 양수 net_inflow
    # 퇴장: 17-20시 음수 net_inflow (commuter) / 22-26시 음수 (visitor)
    ext_commuter_arrivals: list[tuple[str, int]] = []
    ext_commuter_departures: list[int] = []
    ext_visitor_arrivals: list[tuple[str, int]] = []
    ext_visitor_departures: list[int] = []

    if subway_inflow:
        morning_in = [
            ((d, h), info["net_inflow"])
            for (d, h), info in subway_inflow.items()
            if 6 <= h <= 10 and info["net_inflow"] > 0 and d in dongs
        ]
        evening_out = [
            (h, -info["net_inflow"])
            for (d, h), info in subway_inflow.items()
            if 17 <= h <= 20 and info["net_inflow"] < 0 and d in dongs
        ]
        evening_in = [
            ((d, h), info["net_inflow"])
            for (d, h), info in subway_inflow.items()
            if 17 <= h <= 22 and info["net_inflow"] > 0 and d in dongs
        ]
        night_out = [
            (h if h >= 4 else h + 24, -info["net_inflow"])
            for (d, h), info in subway_inflow.items()
            if (h >= 21 or h <= 2) and info["net_inflow"] < 0 and d in dongs
        ]

        if morning_in and n_ext_commuters > 0:
            keys, weights = zip(*morning_in, strict=False)
            ext_commuter_arrivals = list(rng.choices(keys, weights=weights, k=n_ext_commuters))
        if evening_out and n_ext_commuters > 0:
            hours, weights = zip(*evening_out, strict=False)
            ext_commuter_departures = list(rng.choices(hours, weights=weights, k=n_ext_commuters))
        if evening_in and n_ext_visitors > 0:
            keys, weights = zip(*evening_in, strict=False)
            ext_visitor_arrivals = list(rng.choices(keys, weights=weights, k=n_ext_visitors))
        if night_out and n_ext_visitors > 0:
            hours, weights = zip(*night_out, strict=False)
            ext_visitor_departures = list(rng.choices(hours, weights=weights, k=n_ext_visitors))

    # 인덱스 카운터 (make 안에서 pop하기 위함)
    ext_c_idx = [0]
    ext_v_idx = [0]

    def make(role: Role, tier: Tier, prof) -> Agent:
        nonlocal aid
        # External 에이전트는 home_dong을 외부 표시("외부"), work/visit dong을 마포 내 결정
        arr_h = 8
        dep_h = 18
        if role == Role.EXT_COMMUTER:
            home = "외부"
            if ext_commuter_arrivals and ext_c_idx[0] < len(ext_commuter_arrivals):
                work, arr_h = ext_commuter_arrivals[ext_c_idx[0]]
            else:
                work = rng.choice(office_pool)
                arr_h = rng.choice([7, 8, 8, 9])  # 약한 fallback 분산
            if ext_commuter_departures and ext_c_idx[0] < len(ext_commuter_departures):
                dep_h = ext_commuter_departures[ext_c_idx[0]]
            else:
                dep_h = rng.choice([17, 18, 18, 19])
            # 진입·퇴장 시간 역전/동일 보정 — 최소 4시간 체류
            if dep_h <= arr_h + 2:
                dep_h = arr_h + rng.randint(4, 8)
            ext_c_idx[0] += 1
            current = home
        elif role == Role.EXT_VISITOR:
            home = "외부"
            if ext_visitor_arrivals and ext_v_idx[0] < len(ext_visitor_arrivals):
                work, arr_h = ext_visitor_arrivals[ext_v_idx[0]]
            else:
                work = rng.choice(visit_pool) if visit_pool else "서교동"
                arr_h = rng.choice([18, 19, 19, 20, 21])
            if ext_visitor_departures and ext_v_idx[0] < len(ext_visitor_departures):
                dep_h = ext_visitor_departures[ext_v_idx[0]]
            else:
                dep_h = rng.choice([22, 23, 24, 25])
            # 진입 후 최소 2시간 체류 보장
            if dep_h <= arr_h + 1:
                dep_h = arr_h + rng.randint(2, 5)
            ext_v_idx[0] += 1
            current = home
        elif prof is not None:
            home = prof.home_dong
            work = rng.choice(office_pool) if role == Role.COMMUTER else None
            current = home
        else:
            home = rng.choice(dongs)
            work = rng.choice(office_pool) if role == Role.COMMUTER else None
            current = home

        if prof is not None and role not in (Role.EXT_COMMUTER, Role.EXT_VISITOR):
            gender = prof.gender
            age = prof.age
            income = prof.income_level
            budget = prof.daily_budget
            profile_obj = prof
        else:
            gender = rng.choice(["M", "F"])
            # External은 20~50대, 소득 중상위 가정
            if role == Role.EXT_COMMUTER:
                age = rng.randint(25, 55)
                income = rng.choices([1, 2, 3], weights=[0.1, 0.5, 0.4])[0]
                budget = rng.uniform(20000, 60000)
            elif role == Role.EXT_VISITOR:
                age = rng.randint(20, 45)
                income = rng.choices([1, 2, 3], weights=[0.2, 0.5, 0.3])[0]
                budget = rng.uniform(30000, 100000)
            else:
                age = rng.randint(20, 65)
                income = rng.choices([1, 2, 3], weights=[0.3, 0.5, 0.2])[0]
                budget = rng.uniform(15000, 80000)
            profile_obj = prof  # External은 prof 없을 수 있음

        a = Agent(
            agent_id=aid,
            tier=tier,
            role=role,
            name=_gen_name(rng, gender),
            age=age,
            gender=gender,
            home_dong=home,
            work_dong=work,
            income_level=income,
            budget_today=budget,
            current_dong=current,
            profile=profile_obj,
            arrival_hour=arr_h,
            departure_hour=dep_h,
        )
        aid += 1
        return a

    # Tier 분배 (랜덤 샘플링) — total = sum of all roles
    total = sum(q for _, q in role_quota)
    s_idx = set(rng.sample(range(total), tier_s))
    remaining = [i for i in range(total) if i not in s_idx]
    a_idx = set(rng.sample(remaining, tier_a))

    flat_idx = 0
    prof_idx = 0
    for role, n in role_quota:
        for _ in range(n):
            if flat_idx in s_idx:
                tier = Tier.S
            elif flat_idx in a_idx:
                tier = Tier.A
            else:
                tier = Tier.B
            prof = profiles[prof_idx] if use_profiles and prof_idx < len(profiles) else None
            agents.append(make(role, tier, prof))
            flat_idx += 1
            prof_idx += 1

    return agents
