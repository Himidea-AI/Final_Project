"""로컬 PostgreSQL DB의 모든 테이블을 CSV로 내보내기"""

import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect, text

DB_URL = "postgresql+psycopg://postgres:postgres@192.168.0.28:5432/mapo_simulator"
OUT_DIR = Path(__file__).resolve().parents[1] / "local_db_dump"
OUT_DIR.mkdir(exist_ok=True)

engine = create_engine(DB_URL, echo=False)
inspector = inspect(engine)
tables = inspector.get_table_names()

print(f"Found {len(tables)} tables. Exporting to {OUT_DIR} ...")

with engine.connect() as conn:
    for table in sorted(tables):
        try:
            df = pd.read_sql(text(f'SELECT * FROM "{table}"'), conn)  # noqa: S608
            path = OUT_DIR / f"{table}.csv"
            df.to_csv(path, index=False, encoding="utf-8-sig")
            print(f"  {table}: {len(df):,} rows -> {path.name}")
        except Exception as exc:
            print(f"  {table}: ERROR - {exc}")

engine.dispose()
print("\nDone!")
