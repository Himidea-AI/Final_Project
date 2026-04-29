"""페르소나 - Tier S 50명용 풍부한 프로필 (LLM 캐싱 대상).

설계 의도:
- Tier S 에이전트마다 500토큰 페르소나 프로필을 생성
- Anthropic Prompt Cache의 ephemeral 캐시 키로 재사용 (90% 할인)
- 한 시뮬레이션 동안 동일 페르소나는 1회만 캐시 기록
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .agents import Agent, Role


# 마포구 라이프스타일 아키타입 (8종)
ARCHETYPES = [
    {
        "id": "creative_freelancer",
        "label": "프리랜서 크리에이터",
        "traits": "감성적, 카페 작업 선호, 인스타 인증샷 중요, 평점 4.5+ 우선",
        "spending": "월 카페비 30만원, 디저트 좋아함",
        "preferred_dongs": ["연남동", "합정동", "망원1동"],
    },
    {
        "id": "office_worker",
        "label": "공덕 직장인 30대",
        "traits": "효율 중시, 점심 짧게, 저녁 약속 잦음, 가성비 + 위치 중심",
        "spending": "점심 1만원, 저녁 회식 5만원",
        "preferred_dongs": ["공덕동", "도화동", "용강동"],
    },
    {
        "id": "broadcasting_staff",
        "label": "상암 방송국 스태프",
        "traits": "야근 잦음, 새벽 야식 수요, 24시 매장 선호",
        "spending": "야식 2만원/회",
        "preferred_dongs": ["상암동", "성산1동"],
    },
    {
        "id": "student_couple",
        "label": "홍대 대학생 커플",
        "traits": "트렌드 민감, 신상 매장 선호, SNS 검색 후 방문",
        "spending": "데이트 4만원/회",
        "preferred_dongs": ["서교동", "합정동", "연남동"],
    },
    {
        "id": "retired_local",
        "label": "마포 토박이 시니어",
        "traits": "단골 고집, 새 매장 회피, 가격 민감",
        "spending": "전통시장 위주, 외식 1.5만원",
        "preferred_dongs": ["대흥동", "염리동", "아현동"],
    },
    {
        "id": "young_parent",
        "label": "유아 동반 30대 부모",
        "traits": "주말 활동 위주, 키즈존 선호, 주차 가능 매장",
        "spending": "가족 외식 7만원",
        "preferred_dongs": ["성산2동", "상암동", "망원2동"],
    },
    {
        "id": "tourist_foreign",
        "label": "외국인 단기 관광객",
        "traits": "한국 음식 호기심, 검색 의존, 인스타 핫플 위주",
        "spending": "1일 8만원",
        "preferred_dongs": ["연남동", "홍대(서교)", "망원시장"],
    },
    {
        "id": "f&b_owner",
        "label": "F&B 점주 (자영업자)",
        "traits": "경쟁 매장 모니터링, 임대료 압박, SNS 마케팅 학습 중",
        "spending": "사업 운영 비용 위주",
        "preferred_dongs": ["자기 점포 위치"],
    },
]


@dataclass
class Persona:
    archetype_id: str
    label: str
    full_profile: str  # 캐시 대상 (~500 tok)


# home_dong 매칭 archetype 우선 비율 — 30% 는 다양성(noise) 보존
_HOME_MATCH_PROB = 0.7


def _pick_archetype_for(home_dong: str | None, rng: random.Random) -> dict:
    """home_dong 의 preferred_dongs 매칭 archetype 우선 (70%), 다양성 보존 (30%).

    학술 근거: Argyle et al. 2023 — synthetic persona 의 joint distribution 정합성.
    home_dong 별 archetype 분포가 다르도록 → spatial autocorrelation ↑.

    Args:
        home_dong: agent.home_dong 값. None/"" 이거나 매칭 동이 없으면 others 풀에서 random.
        rng: 재현 가능한 random.Random 인스턴스.

    Returns:
        선택된 archetype dict (f&b_owner 제외).
    """
    candidates = ARCHETYPES[:-1]  # f&b_owner 는 OWNER role 전용
    if not candidates:
        # 방어 코드: ARCHETYPES 가 1개 (f&b_owner only) 이거나 비어있는 비정상 상황
        raise ValueError("ARCHETYPES 가 OWNER 외 archetype 을 제공하지 않습니다.")

    # home_dong 정규화 — None/"" 는 매칭 0 으로 처리
    key = home_dong or ""

    matched: list[dict] = []
    others: list[dict] = []
    if key:
        for arc in candidates:
            prefs = arc["preferred_dongs"]
            # 정확 매칭 우선
            if key in prefs:
                matched.append(arc)
                continue
            # 부분 매칭 — "홍대(서교)" ↔ "서교동" 같은 비표준 표기 허용
            if any(key in pref or pref in key for pref in prefs):
                matched.append(arc)
            else:
                others.append(arc)
    else:
        others = list(candidates)

    if matched and rng.random() < _HOME_MATCH_PROB:
        return rng.choice(matched)
    if others:
        return rng.choice(others)
    # 모든 archetype 이 matched 면 (희박) — matched 에서 선택
    return rng.choice(matched)


def assign_personas(
    agents: list[Agent],
    seed: int = 42,
) -> dict[int, Persona]:
    """Tier S 에이전트들에게 아키타입 기반 페르소나 부여.

    home_dong 과 archetype.preferred_dongs 가 매칭되도록 가중 샘플링 (70%/30%).
    학술 현실성 + thought 자연스러움 ↑ + 같은 home_dong 끼리 cache 효율 ↑.
    """
    rng = random.Random(seed)
    out: dict[int, Persona] = {}

    for a in agents:
        if a.persona_id is None and a.tier.value == "S":
            # 점주는 owner 아키타입, 나머지는 home_dong 매칭
            if a.role == Role.OWNER:
                arc = ARCHETYPES[-1]
            else:
                arc = _pick_archetype_for(a.home_dong, rng)
            a.persona_id = arc["id"]
            out[a.agent_id] = Persona(
                archetype_id=arc["id"],
                label=arc["label"],
                full_profile=_build_profile(a, arc),
            )
    return out


def _build_profile(agent: Agent, arc: dict) -> str:
    """Anthropic prompt cache 정적 페르소나 — caveman 압축 (~150 tok, 이전 500 tok).

    토큰 절감: 50 agents × system prompt cache hit 시 입력 비용 -70%.
    Decision 다양성 보존 위해 핵심 trait·spending·preferred_dongs 유지.
    """
    return f"""마포 {agent.name} {agent.age}{agent.gender} 거주:{agent.home_dong} 소득{agent.income_level}/3 예산{int(agent.budget_today):,}원
타입:{arc["label"]} 특성:{arc["traits"]} 소비:{arc["spending"]} 선호동:{",".join(arc["preferred_dongs"])}
결정요인: 시간 위치 취향 예산 날씨. JSON 짧게:
{{"action":"visit|move|rest|work","target_dong":"동|null","category":"카페|음식점|편의점|주점|null","spend":원,"reason":"30자 이내 fragment, 관사·조사 최소"}}"""
