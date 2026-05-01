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

                # batch insert (ON CONFLICT DO NOTHING — UNIQUE 제약으로 중복 방지)
                conn.execute(
                    text(
                        "INSERT INTO ftc_brand_franchise "
                        '(yr, "corpNm", "brandNm", "indutyLclasNm", "indutyMlsfcNm", '
                        '"frcsCnt", "newFrcsRgsCnt", "ctrtEndCnt", "ctrtCncltnCnt", '
                        '"nmChgCnt", "avrgSlsAmt", "arUnitAvrgSlsAmt") '
                        "VALUES (:yr, :corpNm, :brandNm, :indutyLclasNm, :indutyMlsfcNm, "
                        ":frcsCnt, :newFrcsRgsCnt, :ctrtEndCnt, :ctrtCncltnCnt, "
                        ":nmChgCnt, :avrgSlsAmt, :arUnitAvrgSlsAmt) "
                        'ON CONFLICT (yr, "corpNm", "brandNm") DO NOTHING'
                    ),
                    rows,
                )
                conn.commit()

            print(f"[seed] ftc_brand_franchise {len(rows)}건 적재 완료")
    finally:
        engine.dispose()


def seed_dong_mapping():
    """dong_mapping 마포 16개 동 정적 INSERT (idempotent).

    빈 db (e.g. docker compose up 신규 환경)에서 alembic upgrade 후
    master가 0행이라 후속 INSERT가 FK 위반으로 막히는 문제 방지.
    운영 코드(agents/tools.py, ABM 등)가 의존하는 마포 16동을 항상 보장.
    """
    from src.services.population_api import MAPO_DONG_CODES

    engine = create_engine(DB_URL, echo=False)
    try:
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM dong_mapping")).scalar()
            if count and count >= 16:
                print(f"[seed] dong_mapping 이미 {count}건 존재 - 스킵")
                return

            print("[seed] dong_mapping 마포 16개 동 적재")
            rows = [{"dong_code": code, "dong_name": name} for name, code in MAPO_DONG_CODES.items()]
            conn.execute(
                text(
                    "INSERT INTO dong_mapping (dong_code, dong_name) "
                    "VALUES (:dong_code, :dong_name) "
                    "ON CONFLICT (dong_code) DO NOTHING"
                ),
                rows,
            )
            conn.commit()
            print(f"[seed] dong_mapping {len(rows)}건 적재 완료")
    finally:
        engine.dispose()


def seed_seoul_dong_master():
    """seoul_dong_master 자식 테이블 union 적재 fallback (idempotent).

    alembic B-3.1이 동일 작업을 하지만, 자식 테이블이 비어있던 환경에서
    이후 자식 데이터가 채워진 후 docker compose 재시작 시 master 보강용.
    이미 채워져있으면 스킵 (ON CONFLICT DO NOTHING으로 안전).
    """
    engine = create_engine(DB_URL, echo=False)
    try:
        with engine.connect() as conn:
            # 테이블 존재 확인 (alembic이 안 돌았으면 스킵)
            exists = conn.execute(text("SELECT to_regclass('public.seoul_dong_master') IS NOT NULL")).scalar()
            if not exists:
                print("[seed] seoul_dong_master 테이블 없음 - 스킵")
                return

            count = conn.execute(text("SELECT COUNT(*) FROM seoul_dong_master")).scalar()
            if count and count > 0:
                print(f"[seed] seoul_dong_master 이미 {count}건 존재 - 스킵")
                return

            print("[seed] seoul_dong_master 자식 테이블 union 적재")
            conn.execute(
                text("""
                WITH all_codes AS (
                    SELECT DISTINCT dong_code FROM dong_mapping WHERE dong_code IS NOT NULL
                    UNION SELECT DISTINCT dong_code FROM seoul_district_sales WHERE dong_code IS NOT NULL
                    UNION SELECT DISTINCT dong_code FROM seoul_district_stores WHERE dong_code IS NOT NULL
                    UNION SELECT DISTINCT dong_code FROM seoul_population_quarterly WHERE dong_code IS NOT NULL
                    UNION SELECT DISTINCT dong_code FROM seoul_training_dataset WHERE dong_code IS NOT NULL
                    UNION SELECT DISTINCT dong_code FROM seoul_golmok_rent WHERE dong_code IS NOT NULL
                    UNION SELECT DISTINCT dong_code FROM district_sales_seoul WHERE dong_code IS NOT NULL
                    UNION SELECT DISTINCT dong_code FROM seoul_adstrd_change_ix WHERE dong_code IS NOT NULL
                    UNION SELECT DISTINCT dong_code FROM seoul_adstrd_flpop WHERE dong_code IS NOT NULL
                    UNION SELECT DISTINCT dong_code FROM seoul_adstrd_stor WHERE dong_code IS NOT NULL
                    UNION SELECT DISTINCT dong_code FROM seoul_adstrd_fclty WHERE dong_code IS NOT NULL
                    UNION SELECT DISTINCT dong_code FROM dong_subway_access WHERE dong_code IS NOT NULL
                    UNION SELECT DISTINCT dong_code FROM seoul_resident_pop_quarterly WHERE dong_code IS NOT NULL
                ),
                pair_pool AS (
                    SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·') AS name
                      FROM dong_mapping WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
                    UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
                      FROM seoul_district_sales WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
                    UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
                      FROM seoul_district_stores WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
                    UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
                      FROM seoul_golmok_rent WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
                    UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
                      FROM seoul_adstrd_change_ix WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
                    UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
                      FROM seoul_adstrd_flpop WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
                    UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
                      FROM seoul_adstrd_stor WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
                    UNION SELECT DISTINCT dong_code, REPLACE(dong_name, '?', '·')
                      FROM seoul_adstrd_fclty WHERE dong_code IS NOT NULL AND dong_name IS NOT NULL
                ),
                resolved AS (
                    SELECT dong_code, MAX(name) AS dong_name
                    FROM pair_pool
                    GROUP BY dong_code
                )
                INSERT INTO seoul_dong_master (dong_code, dong_name, sgg_code)
                SELECT c.dong_code, r.dong_name, LEFT(c.dong_code, 5)
                FROM all_codes c
                LEFT JOIN resolved r USING (dong_code)
                ON CONFLICT (dong_code) DO NOTHING
            """)
            )
            conn.commit()
            new_count = conn.execute(text("SELECT COUNT(*) FROM seoul_dong_master")).scalar()
            print(f"[seed] seoul_dong_master {new_count}건 적재 완료")
    finally:
        engine.dispose()


def seed_jeonse_dong_master():
    """jeonse_dong_master 자식 테이블 union 적재 fallback (idempotent).

    법정동 10자리 코드 마스터. jeonse_monthly_rent 자체 union.
    """
    engine = create_engine(DB_URL, echo=False)
    try:
        with engine.connect() as conn:
            exists = conn.execute(text("SELECT to_regclass('public.jeonse_dong_master') IS NOT NULL")).scalar()
            if not exists:
                print("[seed] jeonse_dong_master 테이블 없음 - 스킵")
                return

            count = conn.execute(text("SELECT COUNT(*) FROM jeonse_dong_master")).scalar()
            if count and count > 0:
                print(f"[seed] jeonse_dong_master 이미 {count}건 존재 - 스킵")
                return

            print("[seed] jeonse_dong_master 자식 테이블 union 적재")
            conn.execute(
                text("""
                INSERT INTO jeonse_dong_master (dong_code, dong_name, gu_code, gu_name)
                SELECT
                    dong_code,
                    MAX(REPLACE(dong_name, '?', '·')) AS dong_name,
                    MAX(gu_code) AS gu_code,
                    MAX(gu_name) AS gu_name
                FROM jeonse_monthly_rent
                WHERE dong_code IS NOT NULL
                GROUP BY dong_code
                ON CONFLICT (dong_code) DO NOTHING
            """)
            )
            conn.commit()
            new_count = conn.execute(text("SELECT COUNT(*) FROM jeonse_dong_master")).scalar()
            print(f"[seed] jeonse_dong_master {new_count}건 적재 완료")
    finally:
        engine.dispose()


if __name__ == "__main__":
    # master 테이블 먼저 (자식 테이블 FK 위반 방지)
    seed_dong_mapping()
    seed_seoul_dong_master()
    seed_jeonse_dong_master()
    # 그 다음 일반 seed
    seed_ftc_brand_franchise()
