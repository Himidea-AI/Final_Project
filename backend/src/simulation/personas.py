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


def assign_personas(
    agents: list[Agent],
    seed: int = 42,
) -> dict[int, Persona]:
    """Tier S 에이전트들에게 아키타입 기반 페르소나 부여."""
    rng = random.Random(seed)
    out: dict[int, Persona] = {}

    for a in agents:
        if a.persona_id is None and a.tier.value == "S":
            # 점주는 owner 아키타입, 나머지는 일반
            if a.role == Role.OWNER:
                arc = ARCHETYPES[-1]
            else:
                arc = rng.choice(ARCHETYPES[:-1])
            a.persona_id = arc["id"]
            out[a.agent_id] = Persona(
                archetype_id=arc["id"],
                label=arc["label"],
                full_profile=_build_profile(a, arc),
            )
    return out


def _build_profile(agent: Agent, arc: dict) -> str:
    """Anthropic prompt cache에 들어갈 정적 페르소나 프로필 (~500 tok)."""
    return f"""당신은 마포구에 사는 {agent.name}({agent.age}세, {agent.gender})입니다.
타입: {arc["label"]}
특성: {arc["traits"]}
소비 패턴: {arc["spending"]}
선호 동: {", ".join(arc["preferred_dongs"])}
거주: {agent.home_dong}
소득 수준: {agent.income_level}/3 (1=저, 3=고)
오늘 예산: {int(agent.budget_today):,}원

당신은 위 특성에 맞춰 마포구 생활을 합니다. 모든 결정은:
1. 시간대(아침/점심/저녁/심야)
2. 현재 위치(어느 동에 있는가)
3. 당신의 취향과 예산
4. 날씨와 요일

을 고려해서 내립니다. 응답은 항상 JSON 형식으로 짧게:
{{
  "action": "visit|move|rest|work",
  "target_dong": "동 이름 또는 null",
  "category": "카페|음식점|편의점|주점|null",
  "spend": 예상지출원,
  "reason": "한 문장 이유 (스토리용)"
}}
"""
