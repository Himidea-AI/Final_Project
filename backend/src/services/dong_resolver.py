"""
동이름 ↔ 동코드 변환 유틸리티 — Single Source of Truth

마포구 16개 행정동 코드 매핑의 정식 정의 위치.
다른 모듈은 이 파일에서 import 해서 재사용 (population_api, demographic_depth 등).

담당: A1 — 데이터 엔지니어 (찬영)
"""

import logging
import os

from sqlalchemy import text

from src.database.sync_engine import get_sync_engine

logger = logging.getLogger(__name__)

_pw = os.environ.get("POSTGRES_PASSWORD", "postgres")
DB_URL = os.environ.get(
    "POSTGRES_URL",
    f"postgresql://postgres:{_pw}@localhost:5432/mapo_simulator",
)

# ─────────────────────────────────────────────────────────────────────────────
# Single Source of Truth: 마포구 16개 행정동 매핑
# 다른 모듈은 반드시 이 dict 를 import 해서 사용 (재정의 금지).
# ─────────────────────────────────────────────────────────────────────────────
MAPO_DONG_MAP: dict[str, str] = {
    "아현동": "11440555",
    "공덕동": "11440565",
    "도화동": "11440585",
    "용강동": "11440590",
    "대흥동": "11440600",
    "염리동": "11440610",
    "신수동": "11440630",
    "서강동": "11440655",
    "서교동": "11440660",
    "합정동": "11440680",
    "망원1동": "11440690",
    "망원2동": "11440700",
    "연남동": "11440710",
    "성산1동": "11440720",
    "성산2동": "11440730",
    "상암동": "11440740",
}

# 법정동 별칭 (행정동과 1:1 매핑되지 않는 호출자 대응용)
# resolve_dong_code 에서만 사용. MAPO_DONG_MAP 본체는 16개 행정동만 유지.
_DONG_ALIASES: dict[str, str] = {
    "망원동": "11440690",  # 행정동: 망원1동
    "성산동": "11440720",  # 행정동: 성산1동
}

# 코드 → 동이름 역매핑 (16개 행정동 기준)
DONG_CODE_TO_NAME: dict[str, str] = {v: k for k, v in MAPO_DONG_MAP.items()}

# Backward-compat alias — population_api.py 가 기존에 노출하던 이름 그대로 재export.
# 신규 호출자는 MAPO_DONG_MAP 사용 권장. 단 인터페이스 호환을 위해 유지.
MAPO_DONG_CODES: dict[str, str] = MAPO_DONG_MAP

# 기본 fallback 동코드 (서교동) — 동명/코드 모두 매칭 실패 시 사용.
# 마포구 핵심 상권으로 demographic_depth 등 분석 노드의 안정성 보장 용도.
DEFAULT_MAPO_DONG_CODE = "11440660"


def resolve_dong_code(
    dong_name: str | None,
    db_url: str | None = None,
    default: str | None = None,
) -> str | None:
    """동이름 → 동코드 변환 (DB 우선, fallback 하드코딩 + 별칭).

    Args:
        dong_name: 행정동명 (예: "서교동", "망원1동") 또는 별칭 ("망원동").
                   None/"" 이면 default 반환.
        db_url: DB 접속 URL (None이면 환경변수 사용).
        default: 매칭 실패 시 반환할 fallback 코드. None 이면 None 반환 (silent miss).

    Returns:
        동코드 문자열 (예: "11440660") 또는 default.
    """
    if not dong_name:
        return default

    # 0. 이미 8자리 숫자 코드면 그대로 통과 (호출자 편의 — 동명/코드 혼용 입력 방어)
    if dong_name.isdigit() and len(dong_name) == 8:
        return dong_name

    # 1. 하드코딩 매핑 먼저 (빠름)
    if dong_name in MAPO_DONG_MAP:
        return MAPO_DONG_MAP[dong_name]

    # 2. 법정동 별칭
    if dong_name in _DONG_ALIASES:
        return _DONG_ALIASES[dong_name]

    # 3. DB에서 조회
    try:
        engine = get_sync_engine(db_url or DB_URL)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT dong_code FROM dong_mapping WHERE dong_name = :name"),
                {"name": dong_name},
            ).fetchone()
            if row:
                return str(row[0])
    except Exception as e:
        logger.warning(f"[resolve_dong_code] DB 조회 실패 dong={dong_name}: {e}")

    return default


def resolve_dong_code_or_default(
    dong_name: str | None,
    fallback: str = DEFAULT_MAPO_DONG_CODE,
    db_url: str | None = None,
) -> str:
    """resolve_dong_code 의 default 보장 helper — 매칭 실패 시 마포 기본동(서교동) 반환.

    분석 노드(demographic_depth 등) 처럼 None 을 처리하기 곤란한 호출자용.
    """
    return resolve_dong_code(dong_name, db_url=db_url, default=fallback) or fallback


def resolve_dong_name(dong_code: str, db_url: str | None = None) -> str | None:
    """동코드 → 동이름 변환.

    Args:
        dong_code: 행정동 코드 (예: "11440660")
        db_url: DB 접속 URL

    Returns:
        동이름 문자열 (예: "서교동") 또는 None
    """
    if dong_code in DONG_CODE_TO_NAME:
        return DONG_CODE_TO_NAME[dong_code]

    try:
        engine = get_sync_engine(db_url or DB_URL)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT dong_name FROM dong_mapping WHERE dong_code = :code"),
                {"code": dong_code},
            ).fetchone()
            if row:
                return str(row[0])
    except Exception as e:
        logger.warning(f"[resolve_dong_name] DB 조회 실패 code={dong_code}: {e}")

    return None
