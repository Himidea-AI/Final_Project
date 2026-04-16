"""
동이름 ↔ 동코드 변환 유틸리티

동이름("서교동") → 동코드("11440660") 변환.
DongMapping 테이블 또는 하드코딩 매핑 사용.

담당: A1 — 데이터 엔지니어 (찬영)
"""

import os

from sqlalchemy import create_engine, text

_pw = os.environ.get("POSTGRES_PASSWORD", "postgres")
DB_URL = os.environ.get(
    "POSTGRES_URL",
    f"postgresql://postgres:{_pw}@localhost:5432/mapo_simulator",
)

# 하드코딩 매핑 (DB 접속 불가 시 fallback)
MAPO_DONG_MAP = {
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

DONG_CODE_TO_NAME = {v: k for k, v in MAPO_DONG_MAP.items()}


def resolve_dong_code(dong_name: str, db_url: str | None = None) -> str | None:
    """동이름 → 동코드 변환 (DB 우선, fallback 하드코딩).

    Args:
        dong_name: 행정동명 (예: "서교동", "망원1동")
        db_url: DB 접속 URL (None이면 환경변수 사용)

    Returns:
        동코드 문자열 (예: "11440660") 또는 None
    """
    # 1. 하드코딩 매핑 먼저 (빠름)
    if dong_name in MAPO_DONG_MAP:
        return MAPO_DONG_MAP[dong_name]

    # 2. DB에서 조회
    try:
        engine = create_engine(db_url or DB_URL, echo=False)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT dong_code FROM dong_mapping WHERE dong_name = :name"),
                {"name": dong_name},
            ).fetchone()
            if row:
                return str(row[0])
        engine.dispose()
    except Exception:
        pass

    return None


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
        engine = create_engine(db_url or DB_URL, echo=False)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT dong_name FROM dong_mapping WHERE dong_code = :code"),
                {"code": dong_code},
            ).fetchone()
            if row:
                return str(row[0])
        engine.dispose()
    except Exception:
        pass

    return None
