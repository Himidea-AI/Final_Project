"""PersonaPool — Nemotron 합성 페르소나 7,187 개 (마포) parquet 로드 + sex/age 매칭 sample.

배경:
    `data/processed/nemotron_personas_mapo.parquet` 에 마포 7,187 명 풍부한 페르소나
    (occupation, education, persona text, hobbies, professional/sports/arts/travel/
    culinary/family persona 등 26 컬럼). ABM `spawn_agents` 가 이전엔 ProfileBuilder
    (RDS 기반 age/gender/dong 4 속성) 만 써서 풍부한 데이터 미사용.

설계:
    - parquet 1회 로드 (lru_cache 모듈 변수)
    - sex+age_bucket 별 인덱스 사전 구축 (bucket 매칭 sample 빠르게)
    - sample(sex, age) → PersonaProfile dict (occupation/persona/hobbies 등)
    - 동일 RNG seed 재사용 — spawn_agents 와 같은 결정론적 sampling 보장

수동 동기화 X — parquet 만 교체하면 됨. RDS 의존성 0.

사용자 피드백 (2026-05-06): 7,100 페르소나 있는데 왜 안 씀? → 통합.
"""

from __future__ import annotations

import logging
import random
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PARQUET_PATH = _PROJECT_ROOT / "data" / "processed" / "nemotron_personas_mapo.parquet"


# AGE_BUCKETS — profile_builder.py 와 동일 키. 70+ 통합.
_AGE_BUCKETS: list[tuple[str, int, int]] = [
    ("20_24", 20, 24),
    ("25_29", 25, 29),
    ("30_34", 30, 34),
    ("35_39", 35, 39),
    ("40_44", 40, 44),
    ("45_49", 45, 49),
    ("50_54", 50, 54),
    ("55_59", 55, 59),
    ("60_64", 60, 64),
    ("65_69", 65, 69),
    ("70_plus", 70, 999),
]


def _age_to_bucket(age: int) -> str:
    """나이 → bucket key. 19 이하/100 이상은 가장 가까운 bucket."""
    if age < 20:
        return "20_24"
    for k, lo, hi in _AGE_BUCKETS:
        if lo <= age <= hi:
            return k
    return "70_plus"


def _normalize_sex(sex_raw: Any) -> str:
    """parquet sex (한글 '남자'/'여자') → 'M'/'F'. 알 수 없으면 'M' 폴백."""
    if not isinstance(sex_raw, str):
        return "M"
    if "남" in sex_raw or sex_raw.upper() == "M":
        return "M"
    if "여" in sex_raw or sex_raw.upper() == "F":
        return "F"
    return "M"


@dataclass
class PersonaProfile:
    """spawn_agents 가 Agent 에 inject 할 페르소나 속성."""

    uuid: str
    age: int
    sex: str  # 'M' / 'F'
    occupation: str
    education_level: str
    persona_text: str  # 한 문단 요약
    hobbies: list[str]  # 취미 리스트
    professional_persona: str  # 직업 관련 상세
    cultural_background: str
    career_goals: str
    raw: dict[str, Any]  # 미파싱 원본 — 추후 LLM prompt 확장 용


@lru_cache(maxsize=1)
def _load_dataframe() -> pd.DataFrame | None:
    """parquet 1회 로드. 파일 없으면 None (PersonaPool 비활성)."""
    if not _PARQUET_PATH.exists():
        logger.warning(f"[PersonaPool] parquet 미발견: {_PARQUET_PATH} — 비활성")
        return None
    try:
        df = pd.read_parquet(_PARQUET_PATH)
        logger.info(f"[PersonaPool] parquet 로드 완료: {len(df):,} 페르소나 ({len(df.columns)} 컬럼)")
        return df
    except Exception as e:
        logger.exception(f"[PersonaPool] parquet 로드 실패: {e}")
        return None


@lru_cache(maxsize=1)
def _build_index() -> dict[tuple[str, str], list[int]]:
    """(sex, age_bucket) → DataFrame index list. 매 sample 시 lookup."""
    df = _load_dataframe()
    if df is None:
        return {}
    idx: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, row in df.iterrows():
        sex = _normalize_sex(row.get("sex"))
        age = int(row.get("age") or 0)
        bucket = _age_to_bucket(age)
        idx[(sex, bucket)].append(int(i))  # type: ignore[arg-type]
    return dict(idx)


@lru_cache(maxsize=1)
def _uuid_by_idx() -> dict[int, str]:
    """DataFrame index → uuid string 매핑. 1회 prime 후 dict lookup → O(1).

    사용자 피드백 (2026-05-09): 이전 sample() 의 exclude_uuids 분기에서
    `df.iloc[i].get("uuid")` 를 candidates 마다 호출 → 5K agent × ~500 candidates =
    2.5M iloc 호출로 spawn 30-120s 페널티. 미리 dict 로 캐시해 lookup 으로 변경.
    """
    df = _load_dataframe()
    if df is None:
        return {}
    # values 직접 접근 — iloc 보다 빠름. uuid 컬럼 없으면 빈 dict.
    if "uuid" not in df.columns:
        return {}
    return {int(i): str(v) if v is not None else "" for i, v in enumerate(df["uuid"].values)}


def _safe_str(v: Any, default: str = "") -> str:
    """None/NaN 안전 문자열화."""
    if v is None:
        return default
    try:
        if pd.isna(v):
            return default
    except (TypeError, ValueError):
        pass
    return str(v)


def _parse_list(v: Any) -> list[str]:
    """parquet list-like (str repr of list 또는 actual list) → list[str]."""
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x]
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("[") and s.endswith("]"):
            # "['a', 'b']" 형태 — ast.literal_eval 안전 파싱
            import ast

            try:
                parsed = ast.literal_eval(s)
                if isinstance(parsed, (list, tuple)):
                    return [str(x) for x in parsed if x]
            except (ValueError, SyntaxError):
                pass
        # 그냥 텍스트 — comma split fallback
        return [t.strip() for t in s.split(",") if t.strip()]
    return []


def _row_to_profile(row: pd.Series) -> PersonaProfile:
    """DataFrame row → PersonaProfile."""
    raw = row.to_dict()
    return PersonaProfile(
        uuid=_safe_str(row.get("uuid")),
        age=int(row.get("age") or 0),
        sex=_normalize_sex(row.get("sex")),
        occupation=_safe_str(row.get("occupation"), "알 수 없음"),
        education_level=_safe_str(row.get("education_level"), "미상"),
        persona_text=_safe_str(row.get("persona")),
        hobbies=_parse_list(row.get("hobbies_and_interests_list")),
        professional_persona=_safe_str(row.get("professional_persona")),
        cultural_background=_safe_str(row.get("cultural_background")),
        career_goals=_safe_str(row.get("career_goals_and_ambitions")),
        raw=raw,
    )


def is_available() -> bool:
    """parquet 로드 가능 여부 (spawn_agents 가 사전 체크 후 사용)."""
    return _load_dataframe() is not None


def sample(
    sex: str,
    age: int,
    rng: random.Random | None = None,
    exclude_uuids: set[str] | None = None,
) -> PersonaProfile | None:
    """sex (M/F) + age 에 매칭되는 페르소나 1개 무작위 sample.

    매칭:
        1) (sex, age_bucket) 정확 매칭
        2) 비면 (sex, ANY bucket)
        3) 비면 None

    exclude_uuids 가 주어지면 해당 uuid 는 후보에서 제외 (without-replacement sampling).
    spawn_agents 가 5,000 agent 분배 시 페르소나 중복 방지용.
    """
    df = _load_dataframe()
    if df is None:
        return None
    sex_norm = "M" if sex.upper().startswith("M") else "F"
    bucket = _age_to_bucket(age)
    idx_map = _build_index()
    candidates = idx_map.get((sex_norm, bucket), [])
    if not candidates:
        # bucket fallback — 같은 sex 의 모든 row
        candidates = [i for (s, _b), idxs in idx_map.items() if s == sex_norm for i in idxs]

    # exclude 적용 — 이미 사용된 uuid 제거. uuid 사전 캐시 (_uuid_by_idx) 사용 →
    # df.iloc 5K×500 호출 회피 → spawn 단계 30-120s 절약.
    if exclude_uuids:
        uuid_map = _uuid_by_idx()
        candidates = [i for i in candidates if uuid_map.get(i, "") not in exclude_uuids]
        if not candidates:
            # bucket 소진 — sex 전체에서 unused 재시도
            broader = [i for (s, _b), idxs in idx_map.items() if s == sex_norm for i in idxs]
            candidates = [i for i in broader if uuid_map.get(i, "") not in exclude_uuids]

    if not candidates:
        return None
    rng = rng or random
    chosen_idx = rng.choice(candidates)
    return _row_to_profile(df.iloc[chosen_idx])


def stats() -> dict[str, Any]:
    """진단용 — 로드 상태 + bucket 분포 요약."""
    df = _load_dataframe()
    if df is None:
        return {"loaded": False}
    idx = _build_index()
    bucket_counts = {f"{s}/{b}": len(v) for (s, b), v in sorted(idx.items())}
    return {
        "loaded": True,
        "total": len(df),
        "buckets": bucket_counts,
        "path": str(_PARQUET_PATH),
    }
