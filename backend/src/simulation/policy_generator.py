"""Policy Generator — LLM이 페르소나 행동 정책을 숫자 파라미터로 생성.

설계: docs/policy-generator-design.md

1000명 시뮬에서 LLM 호출을 5,000회 → 11회로 축소하는 핵심 모듈.
- LLM: 역할 × 날씨 조합별 PersonaPolicy 생성 (총 11회, Ollama Qwen2.5:3b 로컬)
- 결과: policy_cache.json에 저장 → 이후 실행은 LLM 호출 0회
- 에이전트 의사결정은 policy_executor.py의 순수 Python 점수 함수로 수행
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

from .config import MAPO_DONGS

load_dotenv()


# ---------------------------------------------------------------
# Policy 스키마
# ---------------------------------------------------------------
Role = Literal["resident", "commuter", "visitor", "owner", "ext_commuter", "ext_visitor"]
Weather = Literal["맑음", "비", "눈"]
TimeBlock = Literal["morning", "lunch", "afternoon", "evening", "night"]


@dataclass(frozen=True)
class PersonaPolicy:
    """페르소나 행동 정책 — 모든 필드 숫자(0~1) 또는 dict[str, float]."""

    # 식별자
    policy_id: str  # 예: "office_30s_rain"
    role: Role
    weather: Weather
    time_block: TimeBlock = "afternoon"

    # 이동/공간 성향 (0~1)
    mobility: float = 0.5
    indoor_preference: float = 0.5
    distance_sensitivity: float = 0.5
    crowd_tolerance: float = 0.5

    # 카테고리 선호 (0~1)
    cafe_preference: float = 0.5
    meal_preference: float = 0.5
    pub_preference: float = 0.3
    cvs_preference: float = 0.3

    # 동 선호 (상위 3개만 채우고 나머지는 중립 0.5)
    dong_affinity: dict[str, float] = field(default_factory=dict)

    # 행동 경향
    visit_probability: float = 0.4
    repeat_visit_bonus: float = 0.1
    spend_tendency: float = 0.5

    # LLM 생성 근거 (행동엔 영향 X)
    rationale: str = ""


# ---------------------------------------------------------------
# 정책 카탈로그 — v2 (2026-04): role × weather × time_block 확장
# ---------------------------------------------------------------
# 시간 블록 5구간
TIME_BLOCKS: list[TimeBlock] = ["morning", "lunch", "afternoon", "evening", "night"]


def hour_to_time_block(hour: int) -> TimeBlock:
    """hour (0-23) → time_block."""
    h = hour % 24
    if 6 <= h <= 10:
        return "morning"
    if 11 <= h <= 13:
        return "lunch"
    if 14 <= h <= 17:
        return "afternoon"
    if 18 <= h <= 21:
        return "evening"
    return "night"


# 11 → 55 조합 (role × weather × time_block), owner 는 weather 무관 (5 time_block × 1 = 5)
def _build_catalog() -> list[tuple[Role, Weather, TimeBlock]]:
    cat: list[tuple[Role, Weather, TimeBlock]] = []
    roles_with_weather: list[Role] = ["resident", "commuter", "visitor", "ext_commuter", "ext_visitor"]
    weathers: list[Weather] = ["맑음", "비"]
    for r in roles_with_weather:
        for w in weathers:
            for tb in TIME_BLOCKS:
                cat.append((r, w, tb))
    # owner — weather 무관, time_block 은 활용
    for tb in TIME_BLOCKS:
        cat.append(("owner", "맑음", tb))
    return cat


POLICY_CATALOG_V2: list[tuple[Role, Weather, TimeBlock]] = _build_catalog()
# 하위 호환: 기존 코드가 POLICY_CATALOG 를 참조하면 role×weather 만 (time_block 생략)
POLICY_CATALOG: list[tuple[Role, Weather]] = [
    ("resident", "맑음"),
    ("resident", "비"),
    ("commuter", "맑음"),
    ("commuter", "비"),
    ("visitor", "맑음"),
    ("visitor", "비"),
    ("ext_commuter", "맑음"),
    ("ext_commuter", "비"),
    ("ext_visitor", "맑음"),
    ("ext_visitor", "비"),
    ("owner", "맑음"),
]


def policy_id(role: Role, weather: Weather, time_block: TimeBlock | None = None) -> str:
    """role+weather+time_block 복합 키. time_block None 이면 기존 2-key (fallback)."""
    if time_block is None:
        return f"{role}_{weather}"
    return f"{role}_{weather}_{time_block}"


# ---------------------------------------------------------------
# JSON Schema (Gemini structured output용)
# ---------------------------------------------------------------
POLICY_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "mobility": {"type": "number"},
        "indoor_preference": {"type": "number"},
        "distance_sensitivity": {"type": "number"},
        "crowd_tolerance": {"type": "number"},
        "cafe_preference": {"type": "number"},
        "meal_preference": {"type": "number"},
        "pub_preference": {"type": "number"},
        "cvs_preference": {"type": "number"},
        "dong_affinity": {
            "type": "object",
            "additionalProperties": {"type": "number"},
        },
        "visit_probability": {"type": "number"},
        "repeat_visit_bonus": {"type": "number"},
        "spend_tendency": {"type": "number"},
        "rationale": {"type": "string"},
    },
    "required": [
        "mobility",
        "indoor_preference",
        "distance_sensitivity",
        "crowd_tolerance",
        "cafe_preference",
        "meal_preference",
        "pub_preference",
        "cvs_preference",
        "dong_affinity",
        "visit_probability",
        "repeat_visit_bonus",
        "spend_tendency",
        "rationale",
    ],
}


# ---------------------------------------------------------------
# 프롬프트 템플릿
# ---------------------------------------------------------------
PROMPT_TEMPLATE = """당신은 마포구 ABM 시뮬레이션의 행동 정책 생성자입니다.
다음 페르소나의 행동 성향을 JSON 파라미터로만 출력하세요.
서사 문장은 rationale 필드에만 1~2문장 허용, 그 외는 전부 숫자(0~1).

페르소나:
- 역할: {role_desc}
- 날씨: {weather}
- 시간대 전반

출력 JSON (모든 float는 0~1):
- mobility: 이동 반경 (비 오면 ↓)
- indoor_preference: 실내 선호 (비 오면 ↑)
- distance_sensitivity: 원거리 기피도 (높을수록 근거리 선호)
- crowd_tolerance: 혼잡 허용도
- cafe_preference / meal_preference / pub_preference / cvs_preference: 카테고리 선호
- dong_affinity: 마포 16개 동 중 상위 3개만 {{"동이름": 가중치}} (나머지는 기본 0.5)
- visit_probability: 시간대에 외출/방문 확률
- repeat_visit_bonus: 재방문 가중치
- spend_tendency: 예산 대비 소비율
- rationale: 이 사람이 이렇게 행동하는 이유 (1~2문장)

마포 동 목록: {dongs}

동 특성 참고 (정책별로 적절한 동을 고를 것):
- 오피스 권역 (직장인 출근/점심): 상암동, 공덕동, 도화동
- 유흥/카페 (저녁/주말): 서교동, 합정동, 연남동
- 거주/생활 (일상): 용강동, 대흥동, 염리동, 아현동, 망원2동, 성산1동, 성산2동, 도화동, 서강동
- 주거+상권 혼합: 망원1동, 신수동

중요: resident는 실제 인구가 많은 아현동/도화동/용강동/성산1동을 우선 고려할 것.
특정 동(용강/대흥)에만 몰리지 않고, 역할별로 3개 동을 서로 겹치지 않게 분산할 것.

중요 제약:
1. mobility와 indoor_preference는 음의 상관 (비 오면 mobility↓, indoor↑)
2. crowd_tolerance는 외향적일수록 ↑
3. **cafe_preference와 meal_preference는 서로 20% 이상 차이 나지 않게**
   (카페와 식사는 비슷한 빈도로 발생, 한쪽만 0.9, 다른쪽 0.2 같은 극단 금지)
4. **dong_affinity는 역할 특성에 맞는 동을 선택**:
   - resident: 주거/생활 동 위주
   - commuter: 오피스 동 (마포 내 근무)
   - ext_commuter: 상암·공덕·도화 중 2개 이상
   - ext_visitor: 서교·합정·연남 중 2개 이상
   - visitor: 유흥/카페 동 위주
   - owner: 주거+상권 혼합 또는 본인 지역
5. pub_preference는 저녁/야간 활동 페르소나에만 0.5 이상
"""

ROLE_DESCRIPTIONS: dict[Role, str] = {
    "resident": "마포구 거주자 (일상 생활·장보기·카페)",
    "commuter": "마포 내 통근자 (마포 거주 + 마포 근무)",
    "visitor": "단기 방문자 (마포 내 관광·식사)",
    "owner": "점주 (영업시간 동안 본인 가게에 체류)",
    "ext_commuter": "외부에서 마포로 출근하는 직장인 (상암/공덕/도화)",
    "ext_visitor": "외부에서 마포로 저녁 방문하는 사람 (홍대/합정/연남)",
}


def build_prompt(role: Role, weather: Weather) -> str:
    return PROMPT_TEMPLATE.format(
        role_desc=ROLE_DESCRIPTIONS[role],
        weather=weather,
        dongs=", ".join(MAPO_DONGS),
    )


# ---------------------------------------------------------------
# LLM 호출 (OpenAI 우선, Ollama Qwen2.5:3b fallback, 둘 다 OpenAI 호환 API)
# ---------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_POLICY_MODEL", "qwen2.5:3b")
OPENAI_MODEL = os.getenv("OPENAI_POLICY_MODEL", "gpt-4o-mini")


def _get_openai_client():
    """OpenAI 클라이언트. 키 없으면 None."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI

        return OpenAI(api_key=key)
    except Exception as e:
        print(f"[policy_gen] OpenAI 클라이언트 초기화 실패: {e}")
        return None


def _call_openai(client, prompt: str) -> dict | None:
    """OpenAI 호출 + JSON 파싱. gpt-4o-mini는 response_format json_object 지원."""
    system_msg = (
        "You output ONLY valid JSON matching the requested schema. "
        "No preamble, no markdown, no explanation. "
        "All numeric fields must be floats in [0, 1]."
    )
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=600,
            temperature=0.4,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
        )
        text = resp.choices[0].message.content or "{}"
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[policy_gen] OpenAI JSON 파싱 실패: {e}")
        return None
    except Exception as e:
        print(f"[policy_gen] OpenAI 호출 실패: {e}")
        return None


def _ollama_alive() -> bool:
    """Ollama 서버 응답 확인."""
    try:
        import httpx

        r = httpx.get(OLLAMA_BASE_URL.replace("/v1", "/api/tags"), timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def _get_ollama_client():
    """Ollama OpenAI 호환 클라이언트. 서버 다운이면 None."""
    if not _ollama_alive():
        return None
    try:
        from openai import OpenAI

        return OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
    except Exception as e:
        print(f"[policy_gen] Ollama 클라이언트 초기화 실패: {e}")
        return None


def _call_ollama(client, prompt: str) -> dict | None:
    """Ollama 호출 + JSON 파싱. Qwen2.5:3b는 response_format json_object 지원.

    실패 시 None 반환 → _mock_policy fallback.
    """
    system_msg = (
        "You output ONLY valid JSON matching the requested schema. "
        "No preamble, no markdown, no explanation. "
        "All numeric fields must be floats in [0, 1]."
    )
    try:
        resp = client.chat.completions.create(
            model=OLLAMA_MODEL,
            max_tokens=600,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
        )
        text = resp.choices[0].message.content or "{}"
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[policy_gen] JSON 파싱 실패: {e}")
        return None
    except Exception as e:
        print(f"[policy_gen] Ollama 호출 실패: {e}")
        return None


# ---------------------------------------------------------------
# Mock 정책 (LLM 불가 시 fallback)
# ---------------------------------------------------------------
_MOCK_BASE: dict[Role, dict] = {
    "resident": dict(
        mobility=0.5,
        indoor_preference=0.5,
        distance_sensitivity=0.65,
        crowd_tolerance=0.5,
        cafe_preference=0.6,
        meal_preference=0.6,
        pub_preference=0.25,
        cvs_preference=0.4,
        visit_probability=0.35,
        repeat_visit_bonus=0.15,
        spend_tendency=0.45,
    ),
    "commuter": dict(
        mobility=0.6,
        indoor_preference=0.5,
        distance_sensitivity=0.55,
        crowd_tolerance=0.55,
        cafe_preference=0.55,
        meal_preference=0.7,
        pub_preference=0.35,
        cvs_preference=0.45,
        visit_probability=0.45,
        repeat_visit_bonus=0.2,
        spend_tendency=0.5,
    ),
    "visitor": dict(
        mobility=0.8,
        indoor_preference=0.4,
        distance_sensitivity=0.4,
        crowd_tolerance=0.7,
        cafe_preference=0.7,
        meal_preference=0.6,
        pub_preference=0.5,
        cvs_preference=0.3,
        visit_probability=0.65,
        repeat_visit_bonus=0.08,
        spend_tendency=0.65,
    ),
    "owner": dict(
        mobility=0.1,
        indoor_preference=0.9,
        distance_sensitivity=0.8,
        crowd_tolerance=0.6,
        cafe_preference=0.2,
        meal_preference=0.3,
        pub_preference=0.15,
        cvs_preference=0.35,
        visit_probability=0.1,
        repeat_visit_bonus=0.05,
        spend_tendency=0.4,
    ),
    "ext_commuter": dict(
        mobility=0.55,
        indoor_preference=0.5,
        distance_sensitivity=0.5,
        crowd_tolerance=0.55,
        cafe_preference=0.55,
        meal_preference=0.7,
        pub_preference=0.3,
        cvs_preference=0.45,
        visit_probability=0.5,
        repeat_visit_bonus=0.18,
        spend_tendency=0.55,
    ),
    "ext_visitor": dict(
        mobility=0.85,
        indoor_preference=0.3,
        distance_sensitivity=0.35,
        crowd_tolerance=0.75,
        cafe_preference=0.5,
        meal_preference=0.6,
        pub_preference=0.75,
        cvs_preference=0.25,
        visit_probability=0.75,
        repeat_visit_bonus=0.05,
        spend_tendency=0.7,
    ),
}


def _mock_policy(role: Role, weather: Weather) -> PersonaPolicy:
    """(하위 호환) role×weather 단일 정책."""
    base = _MOCK_BASE[role].copy()
    if weather == "비":
        base["indoor_preference"] = min(1.0, base.get("indoor_preference", 0.5) * 1.3)
        base["mobility"] = max(0.1, base.get("mobility", 0.5) * 0.7)
    return PersonaPolicy(
        policy_id=policy_id(role, weather),
        role=role,
        weather=weather,
        rationale=f"[mock] {role} {weather} 기본 정책",
        **base,
    )


# ---------------------------------------------------------------
# v2 하드코딩 정책 — role × weather × time_block 55 조합
# ---------------------------------------------------------------
# time_block 별 field 배율 (role 독립적 기본 효과)
_TIME_BLOCK_DELTAS: dict[TimeBlock, dict[str, float]] = {
    "morning": {
        "visit_probability": 0.6,
        "cafe_preference": 1.1,
        "meal_preference": 0.8,
        "pub_preference": 0.1,
        "mobility": 1.0,
        "spend_tendency": 0.7,
    },
    "lunch": {
        "visit_probability": 1.6,
        "cafe_preference": 1.2,
        "meal_preference": 1.5,
        "pub_preference": 0.2,
        "mobility": 1.0,
        "spend_tendency": 1.1,
    },
    "afternoon": {
        "visit_probability": 1.1,
        "cafe_preference": 1.4,
        "meal_preference": 0.8,
        "pub_preference": 0.3,
        "mobility": 1.0,
        "spend_tendency": 0.9,
    },
    "evening": {
        "visit_probability": 1.7,
        "cafe_preference": 0.9,
        "meal_preference": 1.4,
        "pub_preference": 1.3,
        "mobility": 1.1,
        "spend_tendency": 1.2,
    },
    "night": {
        "visit_probability": 0.5,
        "cafe_preference": 0.4,
        "meal_preference": 0.6,
        "pub_preference": 1.5,
        "mobility": 0.7,
        "spend_tendency": 0.9,
    },
}

# role × time_block 특이 오버라이드 (출퇴근·영업 패턴)
_ROLE_TIME_OVERRIDES: dict[tuple[Role, TimeBlock], dict[str, float]] = {
    ("ext_commuter", "morning"): {"visit_probability": 1.2, "mobility": 1.3, "spend_tendency": 0.7},
    ("ext_commuter", "evening"): {"visit_probability": 0.8, "mobility": 1.3, "spend_tendency": 0.9},
    ("ext_commuter", "night"): {"visit_probability": 0.2, "mobility": 0.3},
    ("ext_visitor", "morning"): {"visit_probability": 0.2, "mobility": 0.3},
    ("ext_visitor", "evening"): {
        "visit_probability": 2.0,
        "pub_preference": 1.7,
        "mobility": 1.4,
        "spend_tendency": 1.4,
    },
    ("ext_visitor", "night"): {"visit_probability": 1.5, "pub_preference": 1.8, "mobility": 1.0},
    ("commuter", "lunch"): {"visit_probability": 2.0, "meal_preference": 1.7, "spend_tendency": 1.2},
    ("commuter", "evening"): {"visit_probability": 1.5, "meal_preference": 1.4, "pub_preference": 1.3},
    ("owner", "morning"): {"visit_probability": 0.3, "mobility": 0.1},
    ("owner", "lunch"): {"visit_probability": 0.2, "mobility": 0.05},
    ("owner", "afternoon"): {"visit_probability": 0.15, "mobility": 0.05},
    ("owner", "evening"): {"visit_probability": 0.4, "mobility": 0.1},
    ("owner", "night"): {"visit_probability": 0.5, "mobility": 0.2},
    ("resident", "morning"): {"visit_probability": 0.7, "cvs_preference": 1.3},
    ("resident", "night"): {"visit_probability": 0.4, "cvs_preference": 1.5},
    ("visitor", "morning"): {"visit_probability": 0.5},
    ("visitor", "afternoon"): {"visit_probability": 1.4, "cafe_preference": 1.3},
}


def expand_policy_to_time_block(base_policy: PersonaPolicy, time_block: TimeBlock) -> PersonaPolicy:
    """(v2) LLM 이 생성한 base PersonaPolicy 를 받아 time_block delta/override 적용.

    base_policy 는 보통 afternoon 기준으로 만든 값 → 다른 시간대로 변형.
    하드코딩 테이블 (TIME_BLOCK_DELTAS, ROLE_TIME_OVERRIDES) 을 곱셈 적용.
    """
    role = base_policy.role
    weather = base_policy.weather

    fields = {
        "mobility": base_policy.mobility,
        "indoor_preference": base_policy.indoor_preference,
        "distance_sensitivity": base_policy.distance_sensitivity,
        "crowd_tolerance": base_policy.crowd_tolerance,
        "cafe_preference": base_policy.cafe_preference,
        "meal_preference": base_policy.meal_preference,
        "pub_preference": base_policy.pub_preference,
        "cvs_preference": base_policy.cvs_preference,
        "visit_probability": base_policy.visit_probability,
        "repeat_visit_bonus": base_policy.repeat_visit_bonus,
        "spend_tendency": base_policy.spend_tendency,
    }

    # 1) time_block 기본 배율
    for k, mult in _TIME_BLOCK_DELTAS[time_block].items():
        if k in fields:
            fields[k] = max(0.01, min(1.0, fields[k] * mult))
    # 2) role × time_block 오버라이드
    ov = _ROLE_TIME_OVERRIDES.get((role, time_block))
    if ov:
        for k, mult in ov.items():
            if k in fields:
                fields[k] = max(0.01, min(1.0, fields[k] * mult))

    return replace(
        base_policy,
        policy_id=policy_id(role, weather, time_block),
        time_block=time_block,
        rationale=base_policy.rationale + f" | +time={time_block}",
        **fields,
    )


def _hardcoded_policy(role: Role, weather: Weather, time_block: TimeBlock) -> PersonaPolicy:
    """(fallback) LLM 없을 때만 사용 — _MOCK_BASE 에서 시작해 time_block 확장."""
    mock = _mock_policy(role, weather)
    return expand_policy_to_time_block(mock, time_block)


def _expand_base_to_v2(base_policies: dict[str, PersonaPolicy]) -> dict[str, PersonaPolicy]:
    """LLM 이 만든 11개 base (role×weather) → time_block 5개 delta 적용으로 55개로 확장.

    반환: 55 (role×weather×time_block) + 11 (legacy role×weather alias = afternoon) = 66 개.
    """
    out: dict[str, PersonaPolicy] = {}
    for base_key, base_pol in base_policies.items():
        for tb in TIME_BLOCKS:
            expanded = expand_policy_to_time_block(base_pol, tb)
            out[expanded.policy_id] = expanded
        # legacy alias: {role}_{weather} 키 → afternoon 값
        out[base_key] = out[policy_id(base_pol.role, base_pol.weather, "afternoon")]
    return out


# ---------------------------------------------------------------
# 메인 생성 함수
# ---------------------------------------------------------------
def generate_hardcoded_policies_v2() -> dict[str, PersonaPolicy]:
    """v2 — 55개 role×weather×time_block 하드코딩 정책 (LLM 0 호출)."""
    policies: dict[str, PersonaPolicy] = {}
    for role, weather, tb in POLICY_CATALOG_V2:
        pid = policy_id(role, weather, tb)
        pol = _hardcoded_policy(role, weather, tb)
        policies[pid] = pol

        # 하위 호환: tb=afternoon 을 기본 role_weather 키로도 노출 (time_block 없이 조회되는 경로 대비)
        if tb == "afternoon":
            legacy_key = policy_id(role, weather)
            policies[legacy_key] = pol
    return policies


def generate_policies(
    cache_path: str | Path | None = None,
    force_regenerate: bool = False,
    use_mock: bool = False,
    provider: str = "auto",
    use_hardcoded_v2: bool = True,
    llm_base_cache: str | Path | None = None,
) -> dict[str, PersonaPolicy]:
    """PersonaPolicy 생성 + 캐시.

    v2 (2026-04): use_hardcoded_v2=True (기본) 이면 LLM 0 호출, 55+11 개 하드코딩.
    기존 LLM 경로는 use_hardcoded_v2=False 로 유지.

    v3 (하이브리드): llm_base_cache 경로 지정 시 → LLM 11 base 로드 → time_block 확장 → 55+11 개 반환.
    """
    # [하이브리드] LLM base + time_block 확장
    if llm_base_cache is not None:
        base_path = Path(llm_base_cache)
        if not base_path.exists():
            raise FileNotFoundError(f"LLM base cache not found: {base_path}")
        base_policies = _load_cache(base_path)
        policies = _expand_base_to_v2(base_policies)
        print(f"[policy_gen] 하이브리드: LLM base {len(base_policies)} → expand {len(policies)} (time_block×5)")
        return policies

    if use_hardcoded_v2:
        policies = generate_hardcoded_policies_v2()
        print(f"[policy_gen] v2 하드코딩 {len(policies)}개 (role×weather×time_block)")
        if cache_path is None:
            cache_path = Path(__file__).resolve().parents[3] / "data" / "processed" / "policy_cache_v2.json"
        cache_path = Path(cache_path)
        _save_cache(cache_path, policies)
        return policies
    if cache_path is None:
        cache_path = Path(__file__).resolve().parents[3] / "data" / "processed" / "policy_cache.json"
    cache_path = Path(cache_path)

    # 캐시 로드
    if cache_path.exists() and not force_regenerate:
        print(f"[policy_gen] 캐시 재사용: {cache_path.name}")
        return _load_cache(cache_path)

    # 환경변수 POLICY_PROVIDER 가 설정되면 우선 적용 (테스트 토큰 절약용)
    # e.g., POLICY_PROVIDER=ollama → OpenAI 건너뛰고 Ollama만
    env_override = os.getenv("POLICY_PROVIDER", "").strip().lower()
    if env_override in ("openai", "ollama", "auto"):
        provider = env_override

    # Provider 결정
    client = None
    call_fn = None
    active_provider = None
    if not use_mock:
        if provider in ("openai", "auto"):
            client = _get_openai_client()
            if client is not None:
                call_fn = _call_openai
                active_provider = f"OpenAI {OPENAI_MODEL}"
        if client is None and provider in ("ollama", "auto"):
            client = _get_ollama_client()
            if client is not None:
                call_fn = _call_ollama
                active_provider = f"Ollama {OLLAMA_MODEL}"

    if client is None and not use_mock:
        print("[policy_gen] 사용 가능한 LLM 없음 → mock 정책 생성")
        use_mock = True
    elif active_provider:
        print(f"[policy_gen] {active_provider} 연결 완료 — 11회 호출 시작")

    policies: dict[str, PersonaPolicy] = {}
    for role, weather in POLICY_CATALOG:
        pid = policy_id(role, weather)
        if use_mock:
            pol = _mock_policy(role, weather)
        else:
            prompt = build_prompt(role, weather)
            raw = call_fn(client, prompt)
            if raw is None:
                print(f"  [{pid}] LLM 실패 → mock fallback")
                pol = _mock_policy(role, weather)
            else:
                pol = _parse_policy(pid, role, weather, raw)
        policies[pid] = pol
        print(
            f"  [{pid}] indoor={pol.indoor_preference:.2f} mobility={pol.mobility:.2f} "
            f"visit_p={pol.visit_probability:.2f}"
        )

    # 저장
    _save_cache(cache_path, policies)
    print(f"[policy_gen] 저장: {cache_path.name} ({len(policies)}개)")
    return policies


def _parse_policy(pid: str, role: Role, weather: Weather, raw: dict) -> PersonaPolicy:
    """Gemini JSON → PersonaPolicy. sanity check 포함."""

    def clamp(v, lo=0.0, hi=1.0):
        try:
            return max(lo, min(hi, float(v)))
        except (TypeError, ValueError):
            return 0.5

    dong_aff = raw.get("dong_affinity") or {}
    # 마포 동만 필터링
    dong_aff = {d: clamp(v) for d, v in dong_aff.items() if d in MAPO_DONGS}

    return PersonaPolicy(
        policy_id=pid,
        role=role,
        weather=weather,
        mobility=clamp(raw.get("mobility")),
        indoor_preference=clamp(raw.get("indoor_preference")),
        distance_sensitivity=clamp(raw.get("distance_sensitivity")),
        crowd_tolerance=clamp(raw.get("crowd_tolerance")),
        cafe_preference=clamp(raw.get("cafe_preference")),
        meal_preference=clamp(raw.get("meal_preference")),
        pub_preference=clamp(raw.get("pub_preference")),
        cvs_preference=clamp(raw.get("cvs_preference")),
        dong_affinity=dong_aff,
        visit_probability=clamp(raw.get("visit_probability")),
        repeat_visit_bonus=clamp(raw.get("repeat_visit_bonus")),
        spend_tendency=clamp(raw.get("spend_tendency")),
        rationale=str(raw.get("rationale", ""))[:500],
    )


# ---------------------------------------------------------------
# 캐시 I/O
# ---------------------------------------------------------------
def _save_cache(path: Path, policies: dict[str, PersonaPolicy]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {pid: asdict(p) for pid, p in policies.items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_cache(path: Path) -> dict[str, PersonaPolicy]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {pid: PersonaPolicy(**d) for pid, d in data.items()}


# ---------------------------------------------------------------
# 개체별 편차 (Python perturbation ±15%)
# ---------------------------------------------------------------
def apply_personal_variation(policy: PersonaPolicy, rng) -> PersonaPolicy:
    """정책 파라미터에 ±15% 개체 편차 부여.

    개체별 RNG로 호출하여 같은 정책 기반 1000명이 고유 행동하도록.
    """

    def jitter(v: float) -> float:
        return max(0.0, min(1.0, v * rng.uniform(0.85, 1.15)))

    return replace(
        policy,
        mobility=jitter(policy.mobility),
        indoor_preference=jitter(policy.indoor_preference),
        distance_sensitivity=jitter(policy.distance_sensitivity),
        crowd_tolerance=jitter(policy.crowd_tolerance),
        cafe_preference=jitter(policy.cafe_preference),
        meal_preference=jitter(policy.meal_preference),
        pub_preference=jitter(policy.pub_preference),
        cvs_preference=jitter(policy.cvs_preference),
        visit_probability=jitter(policy.visit_probability),
        repeat_visit_bonus=jitter(policy.repeat_visit_bonus),
        spend_tendency=jitter(policy.spend_tendency),
    )


# ---------------------------------------------------------------
# CLI 단독 실행
# ---------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="캐시 무시하고 재생성")
    parser.add_argument("--mock", action="store_true", help="LLM 호출 없이 mock만")
    parser.add_argument(
        "--provider",
        choices=["openai", "ollama", "auto"],
        default="auto",
        help="정책 생성 LLM (auto: OpenAI 우선, Ollama fallback)",
    )
    args = parser.parse_args()

    generate_policies(force_regenerate=args.force, use_mock=args.mock, provider=args.provider)
