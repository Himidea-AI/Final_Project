"""Phase 3: imputed_mapo_v4.csv -> seoul_district_sales_imputed_v4 적재."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

engine = create_engine(os.environ["POSTGRES_URL"])

WIDE_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4.csv"
DETAIL_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4_detail.csv"

if __name__ == "__main__":
    print("[1/2] wide 적재 ...")
    wide = pd.read_csv(WIDE_CSV)
    # 컬럼 정렬 (DB 스키마와 일치) — dong_name, industry_name, store_count 제외
    wide = wide.drop(columns=["dong_name", "industry_name", "store_count"], errors="ignore")

    # Re-run safety: TRUNCATE first to preserve schema/index/comment
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE seoul_district_sales_imputed_v4"))
    wide.to_sql(
        "seoul_district_sales_imputed_v4",
        engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=50,
    )
    print(f"  {len(wide)} row 적재")

    print("[2/2] detail 적재 ...")
    detail = pd.read_csv(DETAIL_CSV)

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE seoul_district_sales_imputed_v4_detail"))
    detail.to_sql(
        "seoul_district_sales_imputed_v4_detail",
        engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=200,
    )
    print(f"  {len(detail)} row 적재")

    print("[done] v4 DB 적재 완료")
