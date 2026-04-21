"""
seoul_adstrd_flpop → data/processed/adstrd_flpop_quarterly.csv 캐시 생성

서울 전체 행정동 분기별 유동인구(total_flpop)를 DB에서 읽어 CSV로 저장한다.
models/lstm_forecast/data_prep.py의 load_adstrd_flpop()이 이 파일을 우선 참조한다.

Usage:
    python -m scripts.cache_adstrd_flpop

담당: B2 — 수지니
참조: scripts/cache_bus_flpop.py (동일 패턴)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "processed"

_pw = os.environ.get("POSTGRES_PASSWORD", "postgres")
_host = os.environ.get("POSTGRES_HOST", "192.168.0.28")
_port = os.environ.get("POSTGRES_PORT", "5432")
_db = os.environ.get("POSTGRES_DB", "mapo_simulator")
DB_URL = os.environ.get(
    "POSTGRES_URL",
    f"postgresql://postgres:{_pw}@{_host}:{_port}/{_db}",
)


def cache_adstrd_flpop(db_url: str = DB_URL) -> Path:
    """seoul_adstrd_flpop.total_flpop을 분기별로 캐시 CSV로 저장한다.

    Parameters
    ----------
    db_url : str
        PostgreSQL 접속 URL.

    Returns
    -------
    Path
        저장된 CSV 파일 경로.
    """
    engine = create_engine(db_url, echo=False)
    try:
        df = pd.read_sql(
            "SELECT quarter, dong_code, total_flpop AS adstrd_flpop "
            "FROM seoul_adstrd_flpop ORDER BY quarter, dong_code",
            engine,
        )
    finally:
        engine.dispose()

    df["dong_code"] = df["dong_code"].astype(str)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / "adstrd_flpop_quarterly.csv"
    df.to_csv(out_path, index=False)
    logger.info("adstrd_flpop CSV 저장 완료: %s (%d rows)", out_path, len(df))
    return out_path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    cache_adstrd_flpop()
