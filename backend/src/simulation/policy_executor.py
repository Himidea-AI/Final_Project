"""Policy Executor — PersonaPolicy 기반 순수 Python 행동 함수.

설계: docs/policy-generator-design.md §6, §8.5

LLM 호출 0회. 정책 파라미터 + feature score로 deterministic 행동 결정.
- GameMaster: 환경 이벤트(날씨/충격/공휴일) → 정책 미세 조정
- score_store: 매장 선호도 점수
- should_visit: 방문 여부 결정
- pick_store_with_spillover: OTR-style 만석 fallback
"""

from __future__ import annotations

import random
from dataclasses import replace
from typing import TYPE_CHECKING

from .policy_generator import PersonaPolicy, apply_personal_variation, hour_to_time_block
from .archetypes import get_multipliers as _archetype_muls

if TYPE_CHECKING:
    from .agents import Agent, Decision
    from .world import Store, World


# ---------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------
def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


import math as _math  # noqa: E402

# 마포 중심 좌표 (대략 합정~공덕 중간)
_MAPO_CENTER = (37.555, 126.923)
# Haversine 기반 km 거리 → 0~1 정규화 (마포 대각선 최대 약 6km)
_MAX_KM = 6.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 사이 km 거리."""
    r = 6371.0
    p1, p2 = _math.radians(lat1), _math.radians(lat2)
    dp, dl = _math.radians(lat2 - lat1), _math.radians(lon2 - lon1)
    a = _math.sin(dp / 2) ** 2 + _math.cos(p1) * _math.cos(p2) * _math.sin(dl / 2) ** 2
    return 2 * r * _math.asin(_math.sqrt(a))


def _dong_distance(a: str, b: str, dongs: list[str]) -> float:
    """간이 동간 거리 (0~1). Haversine fallback. 같으면 0, 최대 1."""
    if a == b:
        return 0.0
    try:
        ia, ib = dongs.index(a), dongs.index(b)
    except ValueError:
        return 1.0
    return min(1.0, abs(ia - ib) / max(1, len(dongs) - 1))


def _store_distance_km(agent_lat: float | None, agent_lon: float | None, store) -> float:
    """에이전트 현재 위치 → 매장 Haversine 거리. 좌표 없으면 마포 중심 기준."""
    if store.lat is None or store.lon is None:
        return 0.5  # 중립값
    alat = agent_lat if agent_lat is not None else _MAPO_CENTER[0]
    alon = agent_lon if agent_lon is not None else _MAPO_CENTER[1]
    return _haversine_km(alat, alon, store.lat, store.lon)


# ---------------------------------------------------------------
# Realism v10 — 체류·이동·학습 유틸
# ---------------------------------------------------------------
_DWELL_HOURS: dict[str, tuple[int, int]] = {
    # (min, max) 체류 시간 (tick 단위, 1 tick = 1 hour)
    "카페": (0, 1),  # 빠른 테이크아웃 ~ 1h 체류
    "음식점": (0, 1),  # 점심은 45분~1h
    "편의점": (0, 0),  # 순간 소비
    "주점": (1, 2),  # 1-2h 체류
    "기타": (0, 1),
}


def compute_dwell_time(category: str, rng) -> int:
    """매장 체류 시간 (tick 수). 0이면 같은 tick에 다른 곳 갈 수 있음."""
    lo, hi = _DWELL_HOURS.get(category, (0, 1))
    if hi == 0:
        return 0
    return rng.randint(lo, hi)


def compute_travel_time(dist_km: float) -> int:
    """km 거리 → 이동 소요 tick 수.

    - < 0.5km: 0 tick (도보)
    - 0.5~2km: 0 tick (여전히 현실적으로 같은 시간)
    - 2~4km: 1 tick (지하철 한 정거장)
    - 4km+: 2 tick (환승)
    """
    if dist_km < 2.0:
        return 0
    if dist_km < 4.0:
        return 1
    return 2


# 계절 보정 (월별 카테고리 부스트)
_SEASON_CATEGORY: dict[int, dict[str, float]] = {
    # 1월, 2월: 추위 → 실내 음식점·카페 ↑, 주점 ↑ (송년/신년회)
    1: {"카페": 1.15, "음식점": 1.1, "주점": 1.2, "편의점": 1.1},
    2: {"카페": 1.1, "음식점": 1.1, "주점": 1.05, "편의점": 1.05},
    # 3-5월: 봄 테라스 카페, 야외 활동
    3: {"카페": 1.1, "음식점": 1.0, "주점": 1.0},
    4: {"카페": 1.15, "음식점": 1.0, "주점": 1.05},  # 벚꽃
    5: {"카페": 1.1, "음식점": 1.0, "주점": 1.1},
    # 6-8월: 여름 — 빙수/냉음료, 주점 ↑ (휴가)
    6: {"카페": 1.2, "음식점": 0.95, "주점": 1.15, "편의점": 1.15},
    7: {"카페": 1.25, "음식점": 0.9, "주점": 1.2, "편의점": 1.25},
    8: {"카페": 1.25, "음식점": 0.9, "주점": 1.2, "편의점": 1.25},
    # 9-11월: 가을 단풍, 외식 피크
    9: {"카페": 1.1, "음식점": 1.05, "주점": 1.1},
    10: {"카페": 1.15, "음식점": 1.1, "주점": 1.1},
    11: {"카페": 1.05, "음식점": 1.05, "주점": 1.1},
    # 12월: 송년회, 편의점 핫팩
    12: {"카페": 1.1, "음식점": 1.15, "주점": 1.3, "편의점": 1.15},
}


# ---------------------------------------------------------------
# GameMaster — 환경 이벤트 → 정책 미세 조정 (§8.5A)
# ---------------------------------------------------------------
class GameMaster:
    """날씨·충격·공휴일을 정책 파라미터에 주입.

    LLM 재호출 없이 시나리오 충격 즉시 반영.
    """

    @staticmethod
    def adjust(policy: PersonaPolicy, world: "World") -> PersonaPolicy:
        adj = policy

        # 날씨
        if world.weather == "비":
            adj = replace(
                adj,
                indoor_preference=_clamp(adj.indoor_preference * 1.3),
                mobility=_clamp(adj.mobility * 0.7),
            )
        elif world.weather == "눈":
            adj = replace(
                adj,
                indoor_preference=_clamp(adj.indoor_preference * 1.5),
                mobility=_clamp(adj.mobility * 0.4),
            )
        elif world.weather == "약한비":
            adj = replace(
                adj,
                indoor_preference=_clamp(adj.indoor_preference * 1.1),
                mobility=_clamp(adj.mobility * 0.85),
            )

        # 임대료/가격 충격 (rent_shock_pct → price_multiplier)
        mult = getattr(world, "price_multiplier", 1.0)
        if mult > 1.0:
            shock = mult - 1.0  # 0.30 = 30% 상승
            adj = replace(
                adj,
                spend_tendency=_clamp(adj.spend_tendency * (1.0 - shock * 0.5)),
                visit_probability=_clamp(adj.visit_probability * (1.0 - shock * 0.3)),
            )

        # 공휴일 — 방문 확률 ↑
        if getattr(world, "is_holiday", False):
            adj = replace(
                adj,
                visit_probability=_clamp(adj.visit_probability * 1.3),
                mobility=_clamp(adj.mobility * 1.15),
            )

        # 주말 — 야간 활동 ↑
        if getattr(world, "is_weekend", False):
            adj = replace(adj, pub_preference=_clamp(adj.pub_preference * 1.2))

        # 미세먼지 (PM2.5 μg/m³) — 75+ 나쁨, 150+ 매우 나쁨
        pm = getattr(world, "air_quality_pm25", 0.0)
        if pm > 150:
            adj = replace(
                adj,
                indoor_preference=_clamp(adj.indoor_preference * 1.4),
                mobility=_clamp(adj.mobility * 0.5),
                visit_probability=_clamp(adj.visit_probability * 0.7),
            )
        elif pm > 75:
            adj = replace(
                adj,
                indoor_preference=_clamp(adj.indoor_preference * 1.2),
                mobility=_clamp(adj.mobility * 0.8),
                visit_probability=_clamp(adj.visit_probability * 0.85),
            )
        elif pm > 35:
            adj = replace(
                adj,
                indoor_preference=_clamp(adj.indoor_preference * 1.05),
                mobility=_clamp(adj.mobility * 0.95),
            )

        # 월급일 — 소비·방문 확률 ↑
        if getattr(world, "is_payday", False):
            adj = replace(
                adj,
                spend_tendency=_clamp(adj.spend_tendency * 1.3),
                visit_probability=_clamp(adj.visit_probability * 1.15),
            )

        return adj


# ---------------------------------------------------------------
# Score 함수 (§6.1)
# ---------------------------------------------------------------
# indoor_score — 카페 편향 억제 위해 카페/음식점 유사 수준으로
_CATEGORY_INDOOR_SCORE = {
    "카페": 0.85,
    "음식점": 0.9,
    "편의점": 0.7,
    "주점": 0.9,
    "기타": 0.4,
}


# ---------------------------------------------------------------
# 성별·연령 카테고리 보정 — 2024 오픈서베이·통계청·KCHS·트렌드모니터 기반
# 출처:
#   - 오픈서베이 카페 트렌드 2025 (30대 여성 옵션 커스터마이징 2.9개 최다)
#   - KCHS 고위험 음주율 (30대 66.3% / 남성 +5%p)
#   - 통계청 가계동향 2024Q4 (40-50대 외식비 15.8% 최고)
#   - 트렌드모니터 편의점 2025 (50·60대 매출 +18~21%, 20대 의존도 최고)
# 기본 1.0, 범위 0.3~1.8
# ---------------------------------------------------------------
_AGE_GENDER_BOOST: dict[tuple[str, str, str], float] = {
    # (category, age_bin, gender): multiplier
    # age_bin: "20s", "30s", "40s", "50s", "60s"
    # 카페
    ("카페", "20s", "F"): 1.70,
    ("카페", "20s", "M"): 1.15,
    ("카페", "30s", "F"): 1.55,
    ("카페", "30s", "M"): 1.10,
    ("카페", "40s", "F"): 1.30,
    ("카페", "40s", "M"): 0.90,
    ("카페", "50s", "F"): 1.00,
    ("카페", "50s", "M"): 0.70,
    ("카페", "60s", "F"): 0.75,
    ("카페", "60s", "M"): 0.55,
    # 음식점
    ("음식점", "20s", "F"): 1.05,
    ("음식점", "20s", "M"): 1.10,
    ("음식점", "30s", "F"): 1.15,
    ("음식점", "30s", "M"): 1.25,
    ("음식점", "40s", "F"): 1.30,
    ("음식점", "40s", "M"): 1.35,
    ("음식점", "50s", "F"): 1.20,
    ("음식점", "50s", "M"): 1.25,
    ("음식점", "60s", "F"): 1.00,
    ("음식점", "60s", "M"): 1.05,
    # 주점
    ("주점", "20s", "F"): 1.35,
    ("주점", "20s", "M"): 1.55,
    ("주점", "30s", "F"): 1.25,
    ("주점", "30s", "M"): 1.60,
    ("주점", "40s", "F"): 0.95,
    ("주점", "40s", "M"): 1.30,
    ("주점", "50s", "F"): 0.65,
    ("주점", "50s", "M"): 1.05,
    ("주점", "60s", "F"): 0.35,
    ("주점", "60s", "M"): 0.60,
    # 편의점
    ("편의점", "20s", "F"): 1.45,
    ("편의점", "20s", "M"): 1.55,
    ("편의점", "30s", "F"): 1.15,
    ("편의점", "30s", "M"): 1.30,
    ("편의점", "40s", "F"): 0.95,
    ("편의점", "40s", "M"): 1.05,
    ("편의점", "50s", "F"): 1.05,
    ("편의점", "50s", "M"): 1.25,
    ("편의점", "60s", "F"): 0.90,
    ("편의점", "60s", "M"): 1.15,
}


def _age_bin(age: int) -> str:
    if age < 30:
        return "20s"
    if age < 40:
        return "30s"
    if age < 50:
        return "40s"
    if age < 60:
        return "50s"
    return "60s"


def _age_gender_time_bonus(age: int, gender: str, category: str, hour: int, weekday: int) -> float:
    """시간대 × 성별·연령 특이 패턴 (4종).

    1. 20대 여성 카페 14-17시 디저트·수다 피크 ×1.25
    2. 30-50대 남성 주점 금·토 19-22시 회식 피크 ×1.40
    3. 50대+ 남성 편의점 07-09시 출근 담배·커피·해장 ×1.30
    4. 20대 편의점 22-02시 야식 피크 ×1.35
    """
    h = hour % 24
    if category == "카페" and age < 30 and gender == "F" and h in (14, 15, 16, 17):
        return 1.25
    if category == "주점" and 30 <= age < 60 and gender == "M" and weekday in (4, 5) and h in (19, 20, 21, 22):
        return 1.40
    if category == "편의점" and age >= 50 and gender == "M" and h in (7, 8, 9):
        return 1.30
    if category == "편의점" and age < 30 and (h >= 22 or h <= 2):
        return 1.35
    return 1.0


# 시간대별 카테고리 부스트 — 실제 소비 패턴 반영
# 점심/저녁엔 음식점, 오후·야간엔 카페, 밤엔 주점, 새벽엔 편의점
_TIME_CATEGORY_BOOST: dict[str, dict[int, float]] = {
    # 음식점 — 점심/저녁 크게 상향 (실측 69% 반영)
    "음식점": {
        7: 1.2,
        8: 1.1,
        11: 1.5,
        12: 2.3,
        13: 2.1,
        14: 1.2,
        17: 1.4,
        18: 2.4,
        19: 2.2,
        20: 1.7,
        21: 1.2,
    },
    # 카페 — 전반 하향 (17% 수준 목표)
    "카페": {
        9: 1.1,
        10: 1.2,
        11: 1.0,
        14: 1.3,
        15: 1.3,
        16: 1.2,
        17: 0.9,
        21: 0.8,
        22: 0.7,
    },
    "주점": {
        18: 1.3,
        19: 2.0,
        20: 2.5,
        21: 2.8,
        22: 2.8,
        23: 2.5,
        24: 2.0,
        0: 1.7,
        1: 1.3,
    },
    "편의점": {
        6: 1.4,
        7: 1.3,
        22: 1.2,
        23: 1.4,
        0: 1.6,
        1: 1.6,
        2: 1.4,
    },
}


def score_store(store: "Store", agent: "Agent", policy: PersonaPolicy, world: "World") -> float:
    """매장 선호도 점수 (높을수록 선택 확률 ↑).

    정책 + 개인 취향(profile) + 나이×동×시간 실측 가중치(time_age_boost) + 시간×카테고리 부스트
    를 모두 곱해서 개별성을 반영한 점수 산출.

    [perf] cProfile 측정 (5.7M 호출 / 90s tottime) 결과 dict literal/enum/getattr
    오버헤드가 self-time 의 30% 차지. inline if/elif + 외부 cache 로 회귀 없는 micro-opt.
    """
    cat = store.category
    h = world.current_hour % 24

    # 1. 정책 카테고리 선호 — inline if/elif (dict literal 생성 회피, 5.7M × 매번)
    if cat == "카페":
        cat_pref = policy.cafe_preference
    elif cat == "음식점":
        cat_pref = policy.meal_preference
    elif cat == "주점":
        cat_pref = policy.pub_preference
    elif cat == "편의점":
        cat_pref = policy.cvs_preference
    else:
        cat_pref = 0.3

    # 2. 시간대별 카테고리 부스트
    inner = _TIME_CATEGORY_BOOST.get(cat)
    if inner is not None:
        cat_pref *= inner.get(h, 1.0)

    # 3. 개인 profile 취향 (AgentProfile 있으면) — 완만 적용 (0.75~1.25)
    profile = agent.profile  # cache 1회
    if profile is not None:
        if cat == "카페":
            profile_cat_pref = profile.pref_cafe
        elif cat == "음식점":
            profile_cat_pref = profile.pref_restaurant
        elif cat == "주점":
            profile_cat_pref = profile.pref_pub
        elif cat == "편의점":
            profile_cat_pref = profile.pref_convenience
        else:
            profile_cat_pref = 0.5
        cat_pref *= 0.75 + 0.5 * profile_cat_pref

    # 4. 실측 연령×동×시간×요일 가중치 (living_population 13,440 entries)
    age_time_boost = 1.0
    tab = world.time_age_boost if hasattr(world, "time_age_boost") else None
    if tab:
        from .profile_builder import age_to_group

        g = age_to_group(agent.age)
        age_time_boost = tab.get((g, store.dong, h, world.weekday), 1.0)

    # 5. 성별·연령별 카테고리 보정 (2024 실측 통계 기반)
    age = agent.age
    gender = agent.gender
    age_cat_mult = _AGE_GENDER_BOOST.get((cat, _age_bin(age), gender), 1.0)
    # 시간대 × 성별·연령 특이 패턴 (20대 여성 카페, 50대 남성 아침 편의점 등)
    age_cat_mult *= _age_gender_time_bonus(age, gender, cat, h, world.weekday)

    # 6. 가격 민감도 (price_sensitivity 높으면 저가 매장 선호)
    price_mult = 1.0
    if profile is not None:
        ps = profile.price_sensitivity
        if ps > 0.5:
            price_mult = max(0.2, 1.3 - 0.3 * store.price_level)
        else:
            price_mult = max(0.2, 0.4 + 0.3 * store.price_level)

    # 기본 feature
    indoor_score = _CATEGORY_INDOOR_SCORE.get(cat, 0.4)
    # Haversine 실거리 (km) + 동 순서 거리 blend
    store_dong = store.dong
    agent_dong = agent.current_dong
    dong_cost = _dong_distance(agent_dong, store_dong, world.dongs)
    km = _store_distance_km(None, None, store) if store_dong != agent_dong else 0.2
    haversine_cost = min(1.0, km / _MAX_KM)
    distance_cost = 0.4 * dong_cost + 0.6 * haversine_cost
    seats = store.seats
    congestion_penalty = min(1.0, store.visits_today / seats) if seats > 0 else 1.0
    dong_aff = policy.dong_affinity.get(store_dong, 0.5)
    popularity = max(0.3, min(2.0, store.popularity_boost))

    # 재방문 보너스 + 학습된 만족도
    sid = store.store_id
    repeat_bonus = policy.repeat_visit_bonus if sid in agent.visited_today else 0.0
    satisfaction = agent.store_satisfaction.get(sid, 0.0)  # 0~1

    # Layer 2 기억: visit_history 기반 누적 만족도 + habit + blacklist
    blacklist = getattr(agent, "blacklist", None)
    if blacklist is not None and sid in blacklist:
        return 0.0  # 블랙리스트 완전 배제
    recalled = agent.recall_satisfaction(sid) if hasattr(agent, "recall_satisfaction") else None
    memory_bonus = 0.0
    if recalled is not None:
        memory_bonus = (recalled - 0.5) * 0.8  # 만족도>0.5 면 +, <0.5 면 -
    # 습관 (같은 시간대 자주 감)
    habit_store_map = getattr(agent, "habit_store", None)
    habit_bonus = 0.4 if habit_store_map is not None and habit_store_map.get(h) == sid else 0.0
    # Layer 2 category 학습 선호 (exponential moving average 로 업데이트된 값)
    learned_prefs = getattr(agent, "learned_prefs", None)
    learned_cat = learned_prefs.get(cat, 0.5) if learned_prefs is not None else 0.5
    learned_mult = 0.7 + 0.6 * learned_cat  # 0.7~1.3

    # Layer 5 친구 추천 반영
    rec_bonus = 0.0
    pending_recs = getattr(agent, "pending_recommendations", None)
    if pending_recs:
        for rec in pending_recs:
            if rec.get("store_id") == sid:
                rec_bonus = 0.3 * rec.get("strength", 0.5)
                break

    # 계절 보정
    month = getattr(world, "month", 4)
    season_inner = _SEASON_CATEGORY.get(month)
    season_mult = season_inner.get(cat, 1.0) if season_inner is not None else 1.0

    # 영업 마감 직전 러시 (카페·편의점만, close 1시간 전)
    close_rush = 1.15 if (cat == "편의점" or cat == "카페") and (h == 22 or h == 23) else 1.0

    score = (
        policy.indoor_preference * indoor_score
        + cat_pref * age_cat_mult * price_mult * season_mult * close_rush * learned_mult
        + dong_aff
        + popularity * 0.3
        + repeat_bonus
        + satisfaction * 0.5  # 학습된 만족도 가중 (0~0.5)
        + memory_bonus  # Layer 2: 장기 기억 (-0.4 ~ +0.4)
        + habit_bonus  # Layer 2: 습관 (0 or +0.4)
        + rec_bonus  # Layer 5: 친구 추천 (0 ~ +0.3)
        - policy.distance_sensitivity * distance_cost
        - (1.0 - policy.crowd_tolerance) * congestion_penalty
    )
    # 실측 age×dong×time 가중치 — 완만하게 적용 (0.7~1.3 범위로 클램프)
    score *= 0.7 + 0.3 * max(0.0, min(2.0, age_time_boost))

    # seoul_adstrd_flpop 분기 안정 평균 boost (16동 전체 커버, 동×시간×요일)
    # time_age_boost (grid 기반, noise 큼) 와 별개 — 분기 평균이라 안정
    # Phase A (sprint 2026-04-27) 시도: 0.5+0.5 강화 → -0.007 noise, revert.
    af_boost_map = getattr(world, "adstrd_flpop_boost", None)
    if af_boost_map:
        af = af_boost_map.get((store_dong, h, world.weekday), 1.0)
        score *= 0.9 + 0.1 * max(0.5, min(2.0, af))  # 0.95~1.10 범위 — 보수적

    # 평점 가중
    score += (store.rating - 3.0) * 0.1

    # OFS dong score boost (외부 입지 매력도, Option E — role별 차등)
    # 외부 agent 일수록 OFS 같은 거시 신호에 의존, 거주민은 본인 휴리스틱 사용.
    # ofs_dong_score 비어있으면 1.0 (기존 동작 보존).
    ofs_map = world.ofs_dong_score
    if ofs_map:
        ofs = ofs_map.get(store_dong)
        if ofs is not None:
            ofs_norm = max(0.0, min(1.0, ofs / 100.0))  # 10~100 → 0.1~1.0
            role_v = agent.role.value if hasattr(agent.role, "value") else str(agent.role)
            if role_v == "ext_commuter" or role_v == "ext_visitor":
                ofs_mult = 0.5 + 0.5 * ofs_norm  # 0.5~1.0 (강한 영향)
            elif role_v == "commuter" or role_v == "visitor":
                ofs_mult = 0.85 + 0.3 * ofs_norm  # 0.85~1.15 (약한 영향)
            else:  # resident, owner
                ofs_mult = 1.0  # 영향 없음
            score *= ofs_mult

    return max(0.0, score)


def should_visit(agent: "Agent", policy: PersonaPolicy, world: "World", rng: random.Random) -> bool:
    """시간대 방문 여부 결정."""
    raw_h = world.current_hour
    h = raw_h % 24

    # 이른 새벽 (04~06시 전)만 강하게 억제. 24~26시(심야)는 주점 시간대라 유지
    if raw_h < 6:
        return rng.random() < policy.visit_probability * 0.1

    # 식사 시간대는 확률 부스트 — 개별화로 감소한 visit 수 회복
    boost = 1.0
    if h in (12, 13):  # 점심
        boost = 1.8
    elif h in (18, 19, 20):  # 저녁
        boost = 1.9
    elif h in (21, 22):  # 저녁 연장 (주점 피크 타임)
        boost = 1.4
    elif h in (10, 11, 14, 15, 16):  # 카페 타임
        boost = 1.3
    elif h in (23, 24):  # 심야
        boost = 0.9

    # profile의 mobility_score도 반영
    personal_mob = getattr(agent.profile, "mobility_score", 0.5) if agent.profile else 0.5

    # Layer 3: 내부 상태 반영
    hunger = getattr(agent, "hunger", 0.0)
    fatigue = getattr(agent, "fatigue", 0.0)
    mood = getattr(agent, "mood", 0.5)
    # 배고프면 식사 시간대 visit ↑, 피곤하면 visit ↓, 기분 좋으면 visit ↑
    state_mult = 1.0
    if h in (12, 13, 18, 19, 20) and hunger > 0.5:
        state_mult *= 1.0 + 0.6 * hunger  # 배고픔 × 점심/저녁 → visit_p 최대 1.6배
    state_mult *= 1.0 - 0.4 * fatigue  # fatigue=1.0 면 0.6배
    state_mult *= 0.7 + 0.6 * mood  # mood=0 이면 0.7, mood=1 이면 1.3

    p = _clamp(policy.visit_probability * boost * personal_mob * state_mult)
    return rng.random() < p


# ---------------------------------------------------------------
# OTR Spillover — 상위 후보 중 capacity 여유 매장 선택 (§8.5C)
# ---------------------------------------------------------------
def _prefilter_candidates(
    candidates: list["Store"],
    agent: "Agent",
    policy: PersonaPolicy,
) -> list["Store"]:
    """score_store 호출 전 명백히 탈락할 매장 사전 컷.

    score_store 가 0.0 반환하거나 후속 capacity check 에서 어차피 탈락하는
    매장을 미리 거름. cProfile 측정 결과 score_store 가 5.7M 호출 / 90s
    (cumtime 60%) bottleneck 이라 호출 자체를 줄이는 게 ROI 가장 큼.

    필터 기준 (각각 score_store 안에서도 0/탈락 처리되던 케이스):
      1. blacklist 매장 — score_store:444 score=0 반환
      2. 만석 매장 — score_store 다 거치고 _has_capacity=False 로 탈락
      3. 카테고리 선호도 0.05 미만 — score_store:380 cat_pref 0 가까워 score 무의미

    검증 안전성:
      - 1, 2 는 score_store 결과와 동치 (0 또는 탈락)
      - 3 은 cat_pref < 0.05 일 때 다른 항(distance/popularity) 합으로 1~2 정도
        score 가능 → top_k=5 진입 거의 불가능 (다른 카테고리 score 5~20)
        보수적 기준 0.05 채택 (visit 매출 회귀 < 1%)
    """
    out: list[Store] = []
    blacklist = getattr(agent, "blacklist", None) or set()
    for s in candidates:
        # 1. blacklist
        if s.store_id in blacklist:
            continue
        # 2. 만석
        if s.seats > 0 and s.visits_today >= s.seats:
            continue
        # 3. 카테고리 선호도 매우 낮음
        cat = s.category
        if cat == "카페":
            cp = policy.cafe_preference
        elif cat == "음식점":
            cp = policy.meal_preference
        elif cat == "주점":
            cp = policy.pub_preference
        elif cat == "편의점":
            cp = policy.cvs_preference
        else:
            cp = 0.3  # 기타 카테고리 default
        if cp < 0.05:
            continue
        out.append(s)
    return out


def pick_store_with_spillover(
    agent: "Agent",
    policy: PersonaPolicy,
    world: "World",
    rng: random.Random,
    top_k: int = 5,
) -> "Store | None":
    """현재 동에서 점수 상위 top_k 중 capacity 여유 첫 매장 선택.

    모두 만석이면 인접 동으로 spillover.
    """
    # 1) 현재 동 후보 점수화
    candidates = world.stores_in_dong(agent.current_dong)
    candidates = [s for s in candidates if s.is_open_now]

    # mobility 높으면 인접 동 상위 매장도 후보에 추가
    if policy.mobility > 0.6:
        others = [d for d in world.dongs if d != agent.current_dong]
        # 정책 dong_affinity 기준 상위 2개 동만
        ranked = sorted(others, key=lambda d: policy.dong_affinity.get(d, 0.5), reverse=True)[:2]
        for d in ranked:
            nearby = [s for s in world.stores_in_dong(d) if s.is_open_now]
            # 삽입 순서 bias 방지 — popularity_boost 기준 상위 30개
            nearby.sort(key=lambda s: s.popularity_boost, reverse=True)
            candidates.extend(nearby[:30])

    if not candidates:
        return None

    # 1.5) Prefilter — score_store 호출 부담 -30~40% (cProfile bottleneck 완화)
    candidates = _prefilter_candidates(candidates, agent, policy)
    if not candidates:
        return None

    # 2) 점수화 + 정렬
    scored = [(s, score_store(s, agent, policy, world)) for s in candidates]
    scored.sort(key=lambda x: -x[1])

    # 3) 상위 top_k 중 capacity 여유 첫 매장
    for store, _ in scored[:top_k]:
        if _has_capacity(store):
            return store

    # 4) Spillover — 인접 동에서 capacity 여유 매장 찾기
    for d in _adjacent_dongs(agent.current_dong, world.dongs):
        for s in world.stores_in_dong(d):
            if s.is_open_now and _has_capacity(s):
                return s

    # 5) 그래도 없으면 상위 1개를 그냥 반환 (혼잡해도 visit)
    return scored[0][0] if scored else None


def _has_capacity(store: "Store") -> bool:
    return (store.visits_today / max(store.seats, 1)) < 1.0


def _adjacent_dongs(dong: str, all_dongs: list[str]) -> list[str]:
    """리스트 순서 기준 앞뒤 2개 동을 인접으로 가정.

    추후 dong_subway_access 기반 실제 인접 그래프로 교체.
    """
    if dong not in all_dongs:
        return all_dongs[:3]
    i = all_dongs.index(dong)
    pool = all_dongs[max(0, i - 2) : i] + all_dongs[i + 1 : i + 3]
    return [d for d in pool if d != dong]


# ---------------------------------------------------------------
# 가격·소비 (policy.spend_tendency + agent.profile)
# ---------------------------------------------------------------
_CATEGORY_BASE_PRICE = {"카페": 6000, "음식점": 15000, "편의점": 5000, "주점": 25000, "기타": 10000}


def compute_spend(
    store: "Store",
    agent: "Agent",
    policy: PersonaPolicy,
    world: "World",
    rng: random.Random,
) -> float:
    mult = getattr(world, "price_multiplier", 1.0)
    # 메뉴가 있으면 spend_tendency로 가격대 선택 — price 필드 없는 항목은 제외
    valid_menus = [m for m in (store.menu_items or []) if isinstance(m, dict) and m.get("price")]
    if valid_menus:
        menus = sorted(valid_menus, key=lambda m: m["price"])
        if policy.spend_tendency < 0.5:
            pool = menus[: max(1, len(menus) // 2)]
        else:
            pool = menus[-max(1, len(menus) // 2) :]
        chosen = rng.choice(pool)
        spend = chosen["price"] * mult
    else:
        base = _CATEGORY_BASE_PRICE.get(store.category, 10000)
        spend = base * store.price_level * rng.uniform(0.7, 1.3) * mult * (0.7 + 0.6 * policy.spend_tendency)
    return round(spend, 0)


# ---------------------------------------------------------------
# 메인 Decide 함수 — Agent에서 호출
# ---------------------------------------------------------------
def policy_decide(
    agent: "Agent",
    world: "World",
    rng: random.Random,
) -> "Decision":
    """정책 기반 의사결정 — LLM 0회."""
    from .agents import Decision, Role

    h = world.current_hour

    # External 진입/퇴장은 체류·이동 체크보다 우선 (귀환 보장)
    if agent.role == Role.EXT_COMMUTER:
        if h == agent.arrival_hour and agent.current_dong == "외부":
            agent.current_dong = agent.work_dong or agent.home_dong
            agent.busy_until_hour = -1  # 진입 후 체류 lock 해제
            agent.in_transit_until = -1
            return Decision(action="move", target_dong=agent.current_dong)
        if h >= agent.departure_hour and agent.current_dong != "외부":
            agent.current_dong = "외부"
            agent.busy_until_hour = -1
            agent.in_transit_until = -1
            return Decision(action="move", target_dong="외부")
        if agent.current_dong == "외부":
            return Decision(action="rest")

    if agent.role == Role.EXT_VISITOR:
        if h == agent.arrival_hour and agent.current_dong == "외부":
            agent.current_dong = agent.work_dong or "서교동"
            agent.busy_until_hour = -1
            agent.in_transit_until = -1
            return Decision(action="move", target_dong=agent.current_dong)
        if h >= agent.departure_hour and agent.current_dong != "외부":
            agent.current_dong = "외부"
            agent.busy_until_hour = -1
            agent.in_transit_until = -1
            return Decision(action="move", target_dong="외부")
        if agent.current_dong == "외부":
            return Decision(action="rest")

    # Realism: 체류/이동 중이면 rest (External 처리 후에 체크)
    if agent.busy_until_hour > h:
        return Decision(action="rest", target_dong=agent.current_dong)
    if agent.in_transit_until > h:
        return Decision(action="rest", target_dong=agent.current_dong)

    # Owner는 영업시간 동안 본인 가게
    if agent.role == Role.OWNER:
        if 9 <= h <= 22:
            return Decision(action="work", target_dong=agent.home_dong)
        return Decision(action="rest")

    # 1. 정책 조회 — weather 키 정규화 (약한비 → 비, 기본 → 맑음)
    weather_key = world.weather if world.weather in ("맑음", "비", "눈") else "맑음"
    if weather_key == "눈":
        weather_key = "비"  # 눈은 비 정책 공유 (§3 스펙)
    tb = hour_to_time_block(h)
    # v2: role × weather × time_block 키 우선 조회, 없으면 role × weather fallback
    policy_key_v2 = f"{agent.role.value}_{weather_key}_{tb}"
    policy_key = f"{agent.role.value}_{weather_key}"
    if agent.role.value == "owner":
        policy_key_v2 = f"owner_맑음_{tb}"
        policy_key = "owner_맑음"

    policy = world.policy_cache.get(policy_key_v2) or world.policy_cache.get(policy_key)
    if policy is None:
        # 정책 미로드 — rule_decide로 fallback, 최초 1회만 경고
        if not getattr(world, "_policy_miss_warned", False):
            print(f"[policy] cache miss: {policy_key_v2}/{policy_key} — rule_decide fallback 활성")
            world._policy_miss_warned = True  # type: ignore[attr-defined]
        return agent._rule_decide(world, rng)

    # 2. GameMaster 조정
    policy = GameMaster.adjust(policy, world)

    # 3. 개체별 편차 (±15%)
    policy = apply_personal_variation(policy, rng)

    # 3.5 Archetype multiplier — 개인 성격 유형별 field 배율 (profile 에 기록)
    prof = getattr(agent, "profile", None)
    if prof is not None and getattr(prof, "archetype", None):
        muls = _archetype_muls(prof.archetype)
        if muls:
            patch: dict = {}
            for f in (
                "visit_probability",
                "mobility",
                "cafe_preference",
                "meal_preference",
                "pub_preference",
                "cvs_preference",
                "spend_tendency",
                "crowd_tolerance",
                "distance_sensitivity",
                "repeat_visit_bonus",
            ):
                m = muls.get(f)
                if m is not None:
                    patch[f] = max(0.01, min(1.0, getattr(policy, f) * m))
            # time_block bias (morning/lunch/afternoon/evening/night) — visit_probability 에만 반영
            tb_bias = muls.get(f"{tb}_bias", 1.0)
            if tb_bias != 1.0 and "visit_probability" not in patch:
                patch["visit_probability"] = max(0.01, min(1.0, policy.visit_probability * tb_bias))
            elif tb_bias != 1.0:
                patch["visit_probability"] = max(0.01, min(1.0, patch["visit_probability"] * tb_bias))
            if patch:
                policy = replace(policy, **patch)

    # 4. 친구 동반 — 시간 decay 적용.
    # 출처: HRC Research (2021) 식당 선택 시 58% 가 주변 사람 추천 참고.
    # "방금 다녀온 가게 즉시 follow" 의 직접 통계 부재 → 보수적 추정:
    #   - 1시간 내: 25% (즉시 따라가기, 추천 58% × 시간 근접 가중)
    #   - 1~2시간 내: 15% (시간 경과로 감쇠)
    # 이전 30% 일괄 적용은 1-2시간 모두 동일 → 시간 decay 미반영 회귀 fix.
    friend_store = None
    if agent.friend_visits:
        # 1시간 내 / 1~2시간 별도 분류
        fresh_1h = [(sid, fh) for sid, fh in agent.friend_visits if (h - fh) <= 1]
        fresh_2h = [(sid, fh) for sid, fh in agent.friend_visits if 1 < (h - fh) <= 2]
        chosen = None
        if fresh_1h and rng.random() < 0.25:
            chosen = rng.choice(fresh_1h)
        elif fresh_2h and rng.random() < 0.15:
            chosen = rng.choice(fresh_2h)
        if chosen is not None:
            sid, _ = chosen
            fs = world.stores.get(sid)
            if fs and fs.is_open_now and fs.visits_today < fs.seats:
                friend_store = fs

    # 5. 방문 여부 (친구 동반이면 강제 visit)
    if friend_store is None and not should_visit(agent, policy, world, rng):
        return Decision(action="rest", target_dong=agent.current_dong)

    # 6. 매장 선택 — 친구 매장 우선, 없으면 OTR Spillover
    store = friend_store or pick_store_with_spillover(agent, policy, world, rng)
    if store is None:
        return Decision(action="rest", target_dong=agent.current_dong)

    spend = compute_spend(store, agent, policy, world, rng)

    # 예산 체크
    if spend > agent.budget_today - agent.spent_today:
        return Decision(action="rest", target_dong=agent.current_dong)

    # Realism: 동 이동 시 이동 시간 consumption
    if store.dong != agent.current_dong:
        dist_km = _store_distance_km(None, None, store)
        travel = compute_travel_time(dist_km)
        if travel > 0:
            agent.in_transit_until = h + travel
            # 이동 중에도 current_dong은 목적지로 갱신 (다음 tick 도착)
        agent.current_dong = store.dong

    # Realism: 매장 체류 시간 lock
    dwell = compute_dwell_time(store.category, rng)
    if dwell > 0:
        agent.busy_until_hour = h + dwell

    # Realism: 방문 후 만족도 학습 (rating + popularity 기반)
    new_sat = _clamp((store.rating - 3.0) / 2.0 + (store.popularity_boost - 1.0) * 0.3)
    prev = agent.store_satisfaction.get(store.store_id, 0.3)
    agent.store_satisfaction[store.store_id] = 0.7 * prev + 0.3 * new_sat

    # Realism: 친구들에게 이 방문을 알림 (peer influence)
    for fid in agent.friends[:5]:  # 상위 5명 친구에게만 (계산 비용 제어)
        friend = next((a for a in world.agents if a.agent_id == fid), None)
        if friend is not None:
            friend.friend_visits.append((store.store_id, h))
            # 최근 10개만 유지
            if len(friend.friend_visits) > 10:
                friend.friend_visits = friend.friend_visits[-10:]

    return Decision(
        action="visit",
        target_dong=store.dong,
        target_store_id=store.store_id,
        spend=spend,
    )
