"""imputed_mapo_v4.csv → sales_imp_mapo.csv 형식으로 변환.

기존 컬럼 (monthly_sales, store_count) 위치 보존 + 새 컬럼
(lower_95/upper_95/confidence/extrapolation_flag) 끝에 추가.
v3 백업에만 존재하는 컬럼(kosis_index 등)은 fallback join으로 보완.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
WIDE_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4.csv"
DETAIL_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4_detail.csv"
V3_BACKUP = REPO_ROOT / "data" / "processed" / "sales_imp_mapo.csv.v3_backup"
OUT_CSV = REPO_ROOT / "data" / "processed" / "sales_imp_mapo.csv"

if __name__ == "__main__":
    wide = pd.read_csv(WIDE_CSV)
    detail = pd.read_csv(DETAIL_CSV)

    # detail 에서 monthly_sales lower/upper 추출
    monthly_ci = detail[detail["column_name"] == "monthly_sales"][
        ["quarter", "dong_code", "industry_code", "lower_95", "upper_95"]
    ]
    out = wide.merge(monthly_ci, on=["quarter", "dong_code", "industry_code"], how="left")

    # v3 백업에만 존재하는 컬럼 fallback join (예: kosis_index)
    if V3_BACKUP.exists():
        v3_back = pd.read_csv(V3_BACKUP)
        core_cols = {"quarter", "dong_code", "industry_code"}
        v4_cols = set(out.columns)
        missing_cols = sorted(set(v3_back.columns) - v4_cols - core_cols)
        if missing_cols:
            print(f"[fallback] v3 에서 누락 컬럼 보완: {missing_cols}")
            extra = v3_back[["quarter", "dong_code", "industry_code", *missing_cols]]
            out = out.merge(extra, on=["quarter", "dong_code", "industry_code"], how="left")
        else:
            print("[info] v3 누락 컬럼 없음 — fallback 불필요")
    else:
        print("[warn] v3 백업 없음 — fallback 스킵")

    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {OUT_CSV}  ({len(out)} 셀, {len(out.columns)} 컬럼)")
