# scripts/probe_kosis_item_split.py
"""Phase 0-1: KOSIS DT_1KC2023 의 itm_id 별 anchor 분리 실험.

경상지수 (T1) / 불변지수 (T2) / 혼합 3종 anchor 각각 마포 총매출과
Pearson r 측정 → 분리 anchor 가 +0.03 이상 개선되면 채택.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
from PublicDataReader import Kosis
from scipy.stats import pearsonr
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]


def _get_engine():
    return create_engine(os.environ["POSTGRES_URL"])


def _get_kosis_api():
    return Kosis(os.environ["KOSIS_API_KEY"])


OUT_CSV = REPO_ROOT / "validation" / "results" / "kosis_item_split_result.csv"

ITM_CURRENT = "13102193311A.T1"  # 경상지수 (API itmId: T1)
ITM_CONSTANT = "13102193311A.T2"  # 불변지수 (API itmId: T2)
THRESHOLD_DELTA = 0.03

# KOSIS API 실제 itmId 매핑 (full id → short id)
_API_ITM_MAP = {
    "13102193311A.T1": "T1",
    "13102193311A.T2": "T2",
}


def fetch_anchor(itm_id: str) -> pd.DataFrame:
    """KOSIS DT_1KC2023 서울 숙박·음식점업 분기 지수."""
    api = _get_kosis_api()
    api_itm = _API_ITM_MAP.get(itm_id, itm_id)
    for attempt in range(3):
        try:
            df = api.get_data(
                "통계자료",
                orgId="101",
                tblId="DT_1KC2023",
                objL1="11",
                objL2="I",
                itmId=api_itm,
                prdSe="Q",
                startPrdDe="201901",
                endPrdDe="202404",
            )
            if df is not None and len(df) > 0:
                return df
        except Exception as e:
            print(f"  attempt {attempt + 1} failed: {e}")
            time.sleep(5)
    return pd.DataFrame()


def normalize_quarters(df: pd.DataFrame) -> pd.DataFrame:
    """KOSIS 응답 → quarter (YYYYQ) + value 컬럼 정규화."""
    val_col = next((c for c in df.columns if c in ("수치값", "DT", "value")), None)
    per_col = next((c for c in df.columns if c in ("수록시점", "PRD_DE", "period_value")), None)
    if val_col is None or per_col is None:
        raise ValueError(f"normalize_quarters: expected value/period columns not found. Got: {list(df.columns)}")
    df = df[[per_col, val_col]].copy()
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")

    def to_qkey(p):
        p = str(p)
        if "Q" in p:
            y, q = p.split("Q")
            return int(y) * 10 + int(q)
        if len(p) == 6:
            return int(p[:4]) * 10 + int(p[4:6])
        return None

    df["quarter"] = df[per_col].apply(to_qkey)
    df = df.dropna(subset=["quarter", val_col])
    return df.groupby("quarter", as_index=False)[val_col].mean().rename(columns={val_col: "value"})


def load_mapo_total_sales() -> pd.DataFrame:
    """마포 alive 셀 분기 총매출."""
    engine = _get_engine()
    sql = text("""
        SELECT quarter, SUM(monthly_sales)::bigint AS total_sales
        FROM seoul_district_sales
        WHERE dong_code LIKE '11440%' AND monthly_sales IS NOT NULL
        GROUP BY quarter
        ORDER BY quarter
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn)


def measure_r(anchor: pd.DataFrame, mapo: pd.DataFrame) -> dict:
    merged = anchor.merge(mapo, on="quarter", how="inner")
    if len(merged) < 4:
        return {"n_quarters": len(merged), "pearson_r": None}
    r, _ = pearsonr(merged["value"], merged["total_sales"])
    return {"n_quarters": len(merged), "pearson_r": round(float(r), 4)}


if __name__ == "__main__":
    for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

    print("=== Phase 0-1: KOSIS Item Split ===")
    print("[1/4] Fetching current (T1)...")
    df_current = fetch_anchor(ITM_CURRENT)
    print(f"  rows: {len(df_current)}")
    print("[2/4] Fetching constant (T2)...")
    df_constant = fetch_anchor(ITM_CONSTANT)
    print(f"  rows: {len(df_constant)}")

    print("[3/4] Loading mapo total sales...")
    mapo = load_mapo_total_sales()
    print(f"  rows: {len(mapo)}")

    if len(df_current) == 0 or len(df_constant) == 0:
        print("⚠️  fetch failed — using existing anchor CSV (current/constant 분리 불가)")
        sys.exit(1)

    print("[4/4] Measuring Pearson r for 3 anchors...")
    anchors = {
        "current": normalize_quarters(df_current),
        "constant": normalize_quarters(df_constant),
        # NOTE: mixed = mean(경상, 불변) — 단위 다른 두 지수의 산술 평균.
        # 의미론적 비교 anchor 가 아니라 "분리 효과 측정용" baseline 으로만 사용.
        "mixed": normalize_quarters(pd.concat([df_current, df_constant])),
    }

    results = []
    for name, anchor in anchors.items():
        m = measure_r(anchor, mapo)
        m["name"] = name
        results.append(m)
        r_str = f"{m['pearson_r']:.4f}" if m["pearson_r"] is not None else "N/A"
        print(f"  {name:10s}: r = {r_str} (n={m['n_quarters']})")

    # CSV note 컬럼: mixed 는 단위 다른 두 지수의 산술 평균(baseline) 임을 명시
    for r in results:
        r["note"] = "baseline (mean of T1+T2, semantic mixing)" if r["name"] == "mixed" else "single index"

    out_df = pd.DataFrame(results)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {OUT_CSV}")

    # 합격 판정
    valid = [r for r in results if r["name"] != "mixed" and r["pearson_r"] is not None]
    if not valid:
        print("⚠️  분리 anchor 모두 측정 실패 — 혼합 유지")
        chosen = "mixed"
    else:
        best = max(valid, key=lambda x: x["pearson_r"])
        r_mixed = next((r["pearson_r"] for r in results if r["name"] == "mixed"), None)
        if r_mixed is None:
            print("⚠️  mixed anchor 측정 실패 — best 단독 채택")
            chosen = best["name"]
        else:
            delta = best["pearson_r"] - r_mixed
            chosen = best["name"] if delta >= THRESHOLD_DELTA else "mixed"
            print(f"\n[합격선] best ({best['name']}) − mixed = {delta:+.4f}")
            print(f"[채택] anchor = '{chosen}'  ({'분리 채택' if chosen != 'mixed' else '혼합 유지'})")
