"""Sprint 8: KOSIS 추가 anchor 후보 시도.

DT_3KB9001 — 시도/산업별 매출액 (2023~2024)
DT_1K41017 — 음식점포함 소매판매액지수 (2010~2026)
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
from scipy.stats import pearsonr
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

ANCHOR_CSV = REPO_ROOT / "validation" / "results" / "phase1b_anchor_series.csv"
OUT_CSV = REPO_ROOT / "validation" / "results" / "sprint8_kosis_anchor_probe.csv"


def load_mapo_sales(engine) -> pd.DataFrame:
    """마포 총매출 (분기) — 기존 DB 에서 로드."""
    with engine.connect() as conn:
        mapo = pd.read_sql(
            text("""
                SELECT quarter, SUM(monthly_sales)::bigint AS total_sales
                FROM seoul_district_sales
                WHERE dong_code LIKE '11440%' AND monthly_sales IS NOT NULL
                GROUP BY quarter ORDER BY quarter
            """),
            conn,
        )
    return mapo


def compute_correlation(series_a: pd.Series, series_b: pd.Series, name: str) -> dict:
    """두 시리즈의 Pearson r 계산 (공통 인덱스 기준)."""
    common = series_a.index.intersection(series_b.index)
    if len(common) < 4:
        return {"name": name, "r": None, "n": len(common), "note": "공통 분기 부족"}
    a = series_a.loc[common].values.astype(float)
    b = series_b.loc[common].values.astype(float)
    r, pval = pearsonr(a, b)
    return {"name": name, "r": round(float(r), 4), "n": len(common), "pval": round(float(pval), 4)}


def probe_dt_1k41017(api, mapo: pd.DataFrame) -> dict:
    """DT_1K41017 음식점포함 소매판매액지수 — 시도(서울) 분기."""
    print("\n[fetch] DT_1K41017 (음식점포함 소매판매액지수)...")
    try:
        df = api.get_data(
            "통계자료",
            orgId="101",
            tblId="DT_1K41017",
            objL1="ALL",
            itmId="ALL",
            prdSe="Q",
            startPrdDe="201901",
            endPrdDe="202404",
        )
        if df is None or len(df) == 0:
            print("  결과 없음")
            return {"name": "DT_1K41017", "r": None, "n": 0, "note": "API 결과 없음"}
        print(f"  rows: {len(df)}, columns: {df.columns.tolist()[:10]}")

        # 분기 컬럼 표준화 (수록시점 → qkey 변환)
        # PublicDataReader 반환 컬럼: '수록시점' = 기간, '수치값' = 값
        period_col = next(
            (
                c
                for c in df.columns
                if c in ("수록시점", "수록기간") or "기간" in c or "period" in c.lower() or "PRD" in c
            ),
            None,
        )
        val_col = next(
            (c for c in df.columns if c in ("수치값",) or ("수치" in c and "값" in c) or "DATA" in c.upper()),
            None,
        )
        if period_col is None or val_col is None:
            print(f"  컬럼 매핑 실패: {df.columns.tolist()}")
            return {"name": "DT_1K41017", "r": None, "n": 0, "note": f"컬럼 매핑 실패: {df.columns.tolist()}"}

        df2 = df[[period_col, val_col]].dropna()
        df2.columns = ["qkey", "value"]
        df2["value"] = pd.to_numeric(df2["value"], errors="coerce")
        df2 = df2.dropna()
        # qkey 정규화: "2019Q1" → 20191, "2019/1" → 20191 등
        df2["qkey"] = (
            df2["qkey"].astype(str).str.replace(r"[^\d]", "", regex=True).pipe(lambda s: s.str[:4] + s.str[4:5])
        )
        df2 = df2[df2["qkey"].str.len() == 5]
        df2["qkey"] = df2["qkey"].astype(int)
        series_new = df2.groupby("qkey")["value"].mean()

        # 기존 anchor
        anchor = pd.read_csv(ANCHOR_CSV)
        series_old = anchor.set_index("qkey")["수치값"]

        # 마포 매출과 상관
        mapo_series = mapo.set_index("quarter")["total_sales"]
        r_old = compute_correlation(series_old, mapo_series, "DT_1KC2023 (기존)")
        r_new = compute_correlation(series_new, mapo_series, "DT_1K41017 (신규)")
        print(f"  [기존 anchor] r = {r_old['r']}")
        print(f"  [DT_1K41017] r = {r_new['r']}")
        return r_new
    except Exception as e:
        print(f"  error: {e}")
        return {"name": "DT_1K41017", "r": None, "n": 0, "note": str(e)}


def probe_dt_3kb9001(api, mapo: pd.DataFrame) -> dict:
    """DT_3KB9001 시도/산업별 매출액 — 서울/숙박음식점업 연간."""
    print("\n[fetch] DT_3KB9001 (시도/산업별 매출액)...")
    try:
        df = api.get_data(
            "통계자료",
            orgId="101",
            tblId="DT_3KB9001",
            objL1="11",
            objL2="I",
            itmId="ALL",
            prdSe="Y",
            startPrdDe="2023",
            endPrdDe="2024",
        )
        if df is None or len(df) == 0:
            print("  결과 없음")
            return {"name": "DT_3KB9001", "r": None, "n": 0, "note": "API 결과 없음 (연간 데이터 — 분기 보간 필요)"}
        print(f"  rows: {len(df)}, columns: {df.columns.tolist()[:10]}")
        return {"name": "DT_3KB9001", "r": None, "n": len(df), "note": "연간 데이터 — 분기 보간 후 사용 가능"}
    except Exception as e:
        print(f"  error: {e}")
        return {"name": "DT_3KB9001", "r": None, "n": 0, "note": str(e)}


def main() -> None:
    try:
        from PublicDataReader import Kosis
    except ImportError:
        print("[error] PublicDataReader 미설치 — pip install PublicDataReader")
        sys.exit(1)

    api_key = os.environ.get("KOSIS_API_KEY", "").strip()
    if not api_key:
        print("[error] KOSIS_API_KEY 환경변수 없음")
        sys.exit(1)

    api = Kosis(api_key)
    engine = create_engine(os.environ["POSTGRES_URL"])

    print("[1/3] 마포 분기 매출 로드...")
    mapo = load_mapo_sales(engine)
    print(f"  {len(mapo)} quarters: {mapo['quarter'].min()} ~ {mapo['quarter'].max()}")

    # 기존 anchor r 계산 (비교 기준)
    anchor_old = pd.read_csv(ANCHOR_CSV)
    series_old = anchor_old.set_index("qkey")["수치값"]
    mapo_series = mapo.set_index("quarter")["total_sales"]
    r_baseline = compute_correlation(series_old, mapo_series, "DT_1KC2023 (Sprint 1 baseline)")
    print(f"\n[기존 anchor DT_1KC2023] r = {r_baseline['r']} (n={r_baseline['n']})")

    print("\n[2/3] 추가 anchor 후보 조회...")
    results = [r_baseline]

    r1 = probe_dt_1k41017(api, mapo)
    results.append(r1)
    time.sleep(2)

    r2 = probe_dt_3kb9001(api, mapo)
    results.append(r2)

    # 결과 저장
    out_df = pd.DataFrame(results)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n[saved] {OUT_CSV}")

    print("\n=== Sprint 8 KOSIS anchor 프로브 결과 ===")
    for row in results:
        better = ""
        if row.get("r") is not None and r_baseline.get("r") is not None:
            if row["r"] > r_baseline["r"]:
                better = " ← 개선 후보"
        print(f"  {row['name']}: r={row.get('r')} n={row.get('n')} {row.get('note', '')} {better}")

    best_r = max((row["r"] for row in results if row.get("r") is not None), default=None)
    baseline_r = r_baseline.get("r")
    if best_r is not None and baseline_r is not None and best_r > baseline_r:
        print(f"\n[판정] 더 나은 anchor 존재 (r={best_r} > baseline r={baseline_r}) → anchor 교체 검토")
    else:
        print(f"\n[판정] 기존 anchor (r={baseline_r}) 유지 — 대안 없음 또는 개선 없음")


if __name__ == "__main__":
    main()
