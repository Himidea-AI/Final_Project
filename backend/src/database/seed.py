"""
DB 초기 데이터 로드 — CSV 파일을 테이블에 적재 (이미 데이터가 있으면 스킵)

docker compose up 시 alembic upgrade head 이후 자동 실행됨.
"""

import csv
import os

from sqlalchemy import create_engine, text

_pw = os.environ.get("POSTGRES_PASSWORD", "postgres")

try:
    import psycopg  # noqa: F401

    _driver = "postgresql+psycopg"
except ImportError:
    _driver = "postgresql"

DB_URL = os.environ.get(
    "POSTGRES_URL",
    f"{_driver}://postgres:{_pw}@db:5432/mapo_simulator",
)

CSV_PATH = os.environ.get(
    "FTC_BRAND_CSV",
    "/app/data/processed/ftc_brand_franchise.csv",
)

INT_COLS = {"yr", "frcsCnt", "newFrcsRgsCnt", "ctrtEndCnt", "ctrtCncltnCnt", "nmChgCnt"}
BIGINT_COLS = {"avrgSlsAmt", "arUnitAvrgSlsAmt"}


def seed_ftc_brand_franchise():
    """ftc_brand_franchise 테이블에 CSV 데이터 적재 (이미 있으면 스킵)."""
    if not os.path.exists(CSV_PATH):
        print(f"[seed] CSV 파일 없음: {CSV_PATH} - 스킵")
        return

    engine = create_engine(DB_URL, echo=False)
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM ftc_brand_franchise")).scalar()
            if count and count > 0:
                print(f"[seed] ftc_brand_franchise 이미 {count}건 존재 - 스킵")
                return

            print(f"[seed] ftc_brand_franchise CSV 로딩: {CSV_PATH}")
            with open(CSV_PATH, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = []
                for row in reader:
                    parsed = {}
                    for k, v in row.items():
                        if k in INT_COLS:
                            parsed[k] = int(v) if v else 0
                        elif k in BIGINT_COLS:
                            parsed[k] = int(v) if v else 0
                        else:
                            parsed[k] = v
                    rows.append(parsed)

                if not rows:
                    print("[seed] CSV가 비어있음 - 스킵")
                    return

                # batch insert
                conn.execute(
                    text(
                        "INSERT INTO ftc_brand_franchise "
                        '(yr, "corpNm", "brandNm", "indutyLclasNm", "indutyMlsfcNm", '
                        '"frcsCnt", "newFrcsRgsCnt", "ctrtEndCnt", "ctrtCncltnCnt", '
                        '"nmChgCnt", "avrgSlsAmt", "arUnitAvrgSlsAmt") '
                        "VALUES (:yr, :corpNm, :brandNm, :indutyLclasNm, :indutyMlsfcNm, "
                        ":frcsCnt, :newFrcsRgsCnt, :ctrtEndCnt, :ctrtCncltnCnt, "
                        ":nmChgCnt, :avrgSlsAmt, :arUnitAvrgSlsAmt)"
                    ),
                    rows,
                )
                conn.commit()

            print(f"[seed] ftc_brand_franchise {len(rows)}건 적재 완료")
    finally:
        engine.dispose()


if __name__ == "__main__":
    seed_ftc_brand_franchise()
