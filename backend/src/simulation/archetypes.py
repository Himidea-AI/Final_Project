"""Agent Archetype 하드코딩 모듈.

v2 (2026-04): 각 role 안에 여러 "사람 유형" 을 하드코딩으로 정의.
- LLM base policy (role × weather) + time_block deltas + **ARCHETYPE 계수** → 최종 decision
- 같은 role 이어도 다른 행동 패턴 → 내부 다양성 확보 → 시간대별 쏠림/현실감 개선

구조:
    ARCHETYPES[archetype_id] = {field: multiplier}  # 0~3 배 범위
    ROLE_ARCHETYPE_WEIGHTS[role] = [(archetype_id, weight), ...]

사용:
    from .archetypes import sample_archetype, get_multipliers
    archetype = sample_archetype("ext_commuter", rng, age=32)
    muls = get_multipliers(archetype)  # {"meal_preference": 1.5, ...}
"""

from __future__ import annotations

import random
from typing import Literal

Role = Literal["resident", "commuter", "visitor", "owner", "ext_commuter", "ext_visitor"]

# ---------------------------------------------------------------
# 30+ 하드코딩 Archetype — 각 필드 multiplier (기준 1.0)
# ---------------------------------------------------------------
ARCHETYPES: dict[str, dict[str, float]] = {
    # === resident (마포 거주자) 7 종 ===
    "homebody": {
        "visit_probability": 0.5,
        "mobility": 0.6,
        "cvs_preference": 1.4,
        "cafe_preference": 0.7,
        "pub_preference": 0.3,
        "meal_preference": 0.8,
        "spend_tendency": 0.7,
    },
    "routine_local": {
        "visit_probability": 1.1,
        "mobility": 0.7,
        "repeat_visit_bonus": 1.8,
        "cafe_preference": 1.1,
        "meal_preference": 1.1,
        "distance_sensitivity": 1.3,  # 근거리 고집
    },
    "trendy_local": {
        "visit_probability": 1.3,
        "mobility": 1.2,
        "repeat_visit_bonus": 0.4,
        "cafe_preference": 1.6,
        "crowd_tolerance": 1.3,
        "spend_tendency": 1.2,
    },
    "family_cook": {
        "visit_probability": 0.7,
        "meal_preference": 0.6,
        "cvs_preference": 1.3,
        "cafe_preference": 0.9,
        "pub_preference": 0.2,
        "spend_tendency": 0.8,
    },
    "fitness": {
        "visit_probability": 1.1,
        "mobility": 1.4,
        "exercise_bias": 1.5,
        "cafe_preference": 1.2,
        "meal_preference": 1.0,
        "pub_preference": 0.3,
        "cvs_preference": 1.1,  # 프로틴 바
    },
    "night_owl": {
        "visit_probability": 1.1,
        "mobility": 0.9,
        "pub_preference": 1.8,
        "cvs_preference": 1.4,
        "cafe_preference": 1.0,
        "meal_preference": 1.1,
        "evening_bias": 1.5,
        "night_bias": 1.8,
    },
    "senior_walker": {
        "visit_probability": 0.8,
        "mobility": 0.9,
        "cafe_preference": 0.8,
        "meal_preference": 1.1,
        "pub_preference": 0.2,
        "morning_bias": 1.4,  # 오전 산책
        "spend_tendency": 0.7,
        "distance_sensitivity": 1.5,
    },
    # === commuter (마포 내 통근) 5 종 ===
    "balanced_commuter": {  # 기본형
        "visit_probability": 1.0,
        "meal_preference": 1.0,
        "cafe_preference": 1.0,
    },
    "social_luncher": {
        "visit_probability": 1.3,
        "meal_preference": 1.5,
        "lunch_bias": 1.6,
        "spend_tendency": 1.2,
        "cafe_preference": 1.2,  # 식후 커피
    },
    "quiet_escapist": {
        "visit_probability": 1.0,
        "cafe_preference": 1.5,
        "crowd_tolerance": 0.5,
        "meal_preference": 0.9,
        "pub_preference": 0.4,
    },
    "after_work_social": {
        "visit_probability": 1.2,
        "pub_preference": 1.6,
        "evening_bias": 1.5,
        "spend_tendency": 1.2,
    },
    "smoker_cvs": {
        "visit_probability": 1.1,
        "cvs_preference": 1.7,
        "cafe_preference": 0.9,
        "meal_preference": 0.9,
    },
    # === visitor (단기 방문) 4 종 ===
    "tourist": {
        "visit_probability": 1.3,
        "mobility": 1.3,
        "cafe_preference": 1.2,
        "meal_preference": 1.3,
        "spend_tendency": 1.3,
        "repeat_visit_bonus": 0.3,
    },
    "business_meeter": {
        "visit_probability": 1.1,
        "cafe_preference": 1.6,
        "crowd_tolerance": 0.6,
        "afternoon_bias": 1.5,
        "meal_preference": 0.8,
        "spend_tendency": 1.1,
    },
    "student_studier": {
        "visit_probability": 1.1,
        "cafe_preference": 1.8,
        "mobility": 0.5,
        "repeat_visit_bonus": 1.5,
        "crowd_tolerance": 0.7,
        "spend_tendency": 0.8,
    },
    "event_goer": {
        "visit_probability": 1.2,
        "mobility": 1.3,
        "meal_preference": 1.2,
        "pub_preference": 1.3,
        "evening_bias": 1.5,
        "spend_tendency": 1.2,
    },
    # === owner (점주) 3 종 ===
    "long_hours": {
        "visit_probability": 0.2,
        "mobility": 0.1,
        "spend_tendency": 0.6,
    },
    "early_close": {
        "visit_probability": 0.6,
        "mobility": 0.5,
        "evening_bias": 1.3,
        "night_bias": 0.8,
    },
    "weekend_warrior": {
        "visit_probability": 0.3,
        "mobility": 0.2,
        "weekend_bias": 1.5,
        "spend_tendency": 0.7,
    },
    # === ext_commuter (외부→마포 출근) 5 종 ===
    "workaholic_ext": {
        "visit_probability": 1.1,
        "meal_preference": 0.9,
        "cafe_preference": 1.2,
        "cvs_preference": 1.4,
        "pub_preference": 0.2,
        "spend_tendency": 0.8,
        "lunch_bias": 0.8,
    },
    "lunch_foodie_ext": {
        "visit_probability": 1.3,
        "meal_preference": 1.7,
        "lunch_bias": 1.7,
        "spend_tendency": 1.3,
        "cafe_preference": 1.1,
    },
    "after_work_drinker_ext": {
        "visit_probability": 1.2,
        "pub_preference": 2.0,
        "evening_bias": 1.7,
        "mobility": 1.2,
        "spend_tendency": 1.3,
    },
    "coffee_run_ext": {
        "visit_probability": 1.2,
        "cafe_preference": 1.7,
        "morning_bias": 1.5,
        "afternoon_bias": 1.3,
        "spend_tendency": 1.0,
    },
    "health_ext": {
        "visit_probability": 1.0,
        "meal_preference": 1.1,
        "cvs_preference": 0.7,
        "pub_preference": 0.3,
        "cafe_preference": 1.0,
        "spend_tendency": 0.9,  # 샐러드 비쌈 상쇄
    },
    # === ext_visitor (외부→마포 저녁/주말) 7 종 ===
    "couple_date": {
        "visit_probability": 1.3,
        "meal_preference": 1.4,
        "cafe_preference": 1.3,
        "pub_preference": 0.9,
        "spend_tendency": 1.5,
        "crowd_tolerance": 0.7,
        "evening_bias": 1.6,
    },
    "nightlife_ext": {
        "visit_probability": 1.4,
        "pub_preference": 2.2,
        "evening_bias": 1.8,
        "night_bias": 2.0,
        "mobility": 1.4,
        "spend_tendency": 1.4,
    },
    "foodie_explorer_ext": {
        "visit_probability": 1.3,
        "meal_preference": 1.8,
        "mobility": 1.3,
        "repeat_visit_bonus": 0.4,
        "spend_tendency": 1.3,
    },
    "cafe_crawler_ext": {
        "visit_probability": 1.3,
        "cafe_preference": 2.0,
        "afternoon_bias": 1.5,
        "mobility": 1.1,
        "meal_preference": 0.8,
        "pub_preference": 0.3,
    },
    "photo_tourist_ext": {
        "visit_probability": 1.2,
        "mobility": 1.5,
        "cafe_preference": 1.4,
        "meal_preference": 1.2,
        "afternoon_bias": 1.3,
        "crowd_tolerance": 1.2,
    },
    "concert_goer_ext": {
        "visit_probability": 1.3,
        "mobility": 1.3,
        "pub_preference": 1.6,
        "meal_preference": 1.3,
        "evening_bias": 1.7,
        "night_bias": 1.6,
        "spend_tendency": 1.3,
    },
    "group_friends_ext": {
        "visit_probability": 1.3,
        "pub_preference": 1.7,
        "meal_preference": 1.4,
        "evening_bias": 1.5,
        "crowd_tolerance": 1.3,
        "spend_tendency": 1.2,
    },
}

# ---------------------------------------------------------------
# Role → Archetype 분포 (실측 근사, 합=1.0)
# ---------------------------------------------------------------
ROLE_ARCHETYPE_WEIGHTS: dict[Role, list[tuple[str, float]]] = {
    "resident": [
        ("homebody", 0.20),
        ("routine_local", 0.22),
        ("trendy_local", 0.10),
        ("family_cook", 0.20),
        ("fitness", 0.08),
        ("night_owl", 0.08),
        ("senior_walker", 0.12),
    ],
    "commuter": [
        ("balanced_commuter", 0.35),
        ("social_luncher", 0.25),
        ("quiet_escapist", 0.15),
        ("after_work_social", 0.18),
        ("smoker_cvs", 0.07),
    ],
    "visitor": [
        ("tourist", 0.30),
        ("business_meeter", 0.25),
        ("student_studier", 0.20),
        ("event_goer", 0.25),
    ],
    "owner": [
        ("long_hours", 0.60),
        ("early_close", 0.30),
        ("weekend_warrior", 0.10),
    ],
    "ext_commuter": [
        ("workaholic_ext", 0.35),
        ("lunch_foodie_ext", 0.25),
        ("after_work_drinker_ext", 0.15),
        ("coffee_run_ext", 0.15),
        ("health_ext", 0.10),
    ],
    "ext_visitor": [
        ("couple_date", 0.15),
        ("nightlife_ext", 0.20),
        ("foodie_explorer_ext", 0.18),
        ("cafe_crawler_ext", 0.15),
        ("photo_tourist_ext", 0.10),
        ("concert_goer_ext", 0.10),
        ("group_friends_ext", 0.12),
    ],
}


def sample_archetype(role: str, rng: random.Random, age: int | None = None, income_level: int | None = None) -> str:
    """role + age + income 기반 archetype 샘플.

    age/income 교차 조정:
      - 나이 많으면 senior/family/quiet 류 선호, nightlife 비중 감소
      - 소득 높으면 trendy/foodie/couple_date 비중 상승
    """
    choices = ROLE_ARCHETYPE_WEIGHTS.get(role) or [("balanced_commuter", 1.0)]
    names, weights = zip(*choices, strict=False)
    weights = list(weights)

    # age 보정
    if age is not None and role in ("resident",):
        for i, nm in enumerate(names):
            if nm in ("night_owl", "trendy_local") and age >= 50:
                weights[i] *= 0.3
            elif nm in ("senior_walker",) and age < 50:
                weights[i] *= 0.2
            elif nm in ("family_cook",) and (age < 28 or age >= 65):
                weights[i] *= 0.5
            elif nm in ("fitness",) and age >= 60:
                weights[i] *= 0.3
    if age is not None and role in ("ext_visitor",):
        for i, nm in enumerate(names):
            if nm in ("nightlife_ext", "concert_goer_ext") and age >= 45:
                weights[i] *= 0.3
            elif nm in ("group_friends_ext",) and age >= 50:
                weights[i] *= 0.5
            elif nm in ("couple_date",) and age < 22:
                weights[i] *= 0.4

    # income 보정
    if income_level is not None:
        for i, nm in enumerate(names):
            if nm in ("trendy_local", "foodie_explorer_ext", "couple_date", "cafe_crawler_ext"):
                weights[i] *= 0.7 + 0.3 * income_level  # lvl1: 1.0, lvl3: 1.6
            elif nm in ("homebody", "family_cook", "smoker_cvs", "health_ext"):
                weights[i] *= 1.3 - 0.2 * income_level  # 저소득 가중

    return rng.choices(names, weights=weights)[0]


def get_multipliers(archetype: str) -> dict[str, float]:
    """archetype → field multiplier dict (없으면 빈 dict)."""
    return ARCHETYPES.get(archetype, {})
