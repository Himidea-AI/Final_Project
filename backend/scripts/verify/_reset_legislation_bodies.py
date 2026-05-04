"""1회용: law_legislations 모든 row 의 body_fetched_at NULL set.
이후 fetch_law_bodies.py --retry-failed 로 수정된 _extract_legislation_body 적용 재 fetch.
"""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
for p in (Path(__file__).parents[2] / ".env", Path(__file__).parents[3] / ".env"):
    if p.exists():
        load_dotenv(p)
        break

with psycopg.connect(os.environ["POSTGRES_URL"]) as conn, conn.cursor() as cur:
    cur.execute(
        """
        UPDATE law_legislations
        SET body_fetched_at = NULL
        """
    )
    affected = cur.rowcount
    conn.commit()
    print(f"reset {affected} 건 (body_fetched_at NULL set)")
