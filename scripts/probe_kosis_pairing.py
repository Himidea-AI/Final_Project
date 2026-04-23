"""Phase 1-B: KOSIS 원천 vs seoul_district_sales 페어 구성 및 매칭 가능성 검증.

핵심 테스트:
  (1) KOSIS DT_1KC2023 서울 숙박·음식점업 서비스업생산지수 (분기) ←→ 마포 총매출 (분기)
  (2) KOSIS DT_1KC2020 산업세분류 지수 ←→ 업종별 매출 비중
  (3) KOSIS DT_3KB9001 사업체당 매출액 (시도, 2023~2024) ←→ 매출 승수

기대:
  - 시도 트렌드 지수 vs 마포 총매출 상관 r > 0.7 이면 anchor 사용 가능
  - 업종 세분류 지수 비중 vs 업종 매출 비중 매칭 가능성 검증

출력: docs/sales-imputation/phase1b_pairing.md + validation/results/phase1b_anchor_series.csv
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from PublicDataReader import Kosis
from scipy.stats import pearsonr, spearmanr
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

engine = create_engine(os.environ["POSTGRES_URL"])
api = Kosis(os.environ["KOSIS_API_KEY"])

OUT_MD = REPO_ROOT / "docs" / "sales-imputation" / "phase1b_pairing.md"
OUT_CSV = REPO_ROOT / "validation" / "results" / "phase1b_anchor_series.csv"


def quarters_list(start: int, end: int) -> list[int]:
    """2019~2024 분기 리스트 (YYYYQ 형식, 20191 ~ 20244)."""
    qs = []
    for y in range(start, end + 1):
        for q in range(1, 5):
            qs.append(y * 10 + q)
    return qs


def fetch_kosis_service_index() -> pd.DataFrame:
    """DT_1KC2023 시도별 서비스업생산지수 — 서울 × 숙박 및 음식점업(I) × 분기."""
    print("[kosis] fetching DT_1KC2023 (서울 숙박음식점업 분기 지수)")
    df = api.get_data(
        "통계자료",
        orgId="101",
        tblId="DT_1KC2023",
        objL1="11",  # 서울특별시
        objL2="I",  # 숙박 및 음식점업
        itmId="13102193311A.T1",  # 경상지수 (정확한 itm은 meta로 확인 필요)
        prdSe="Q",
        startPrdDe="201901",
        endPrdDe="202404",
    )
    if df is None or len(df) == 0:
        # itmId 모르면 ALL
        df = api.get_data(
            "통계자료",
            orgId="101",
            tblId="DT_1KC2023",
            objL1="11",
            objL2="I",
            itmId="ALL",
            prdSe="Q",
            startPrdDe="201901",
            endPrdDe="202404",
        )
    print(f"  rows: {len(df) if df is not None else 0}")
    return df


def fetch_kosis_service_index_detail() -> pd.DataFrame:
    """DT_1KC2020 산업 세분류별 서비스업생산지수 — I56 음식점업 세분류."""
    print("[kosis] fetching DT_1KC2020 (전국 음식점 세분류 분기)")
    df = api.get_data(
        "통계자료",
        orgId="101",
        tblId="DT_1KC2020",
        objL1="ALL",
        itmId="ALL",
        prdSe="Q",
        startPrdDe="201901",
        endPrdDe="202404",
    )
    if df is not None:
        # 음식점(I56) 만 필터
        code_col = next((c for c in df.columns if "분류값ID1" in c or "분류값ID" in c), None)
        name_col = next((c for c in df.columns if "분류값명1" in c or "분류값명" in c), None)
        if code_col and name_col:
            mask = df[code_col].astype(str).str.startswith("I56") | df[name_col].astype(str).str.contains(
                "음식|주점|카페|커피", na=False
            )
            df = df[mask]
    print(f"  rows (I56 필터 후): {len(df) if df is not None else 0}")
    return df


def load_seoul_sales_by_quarter() -> pd.DataFrame:
    """살아있는 마포 매출을 분기 합계로 집계."""
    print("[db] loading seoul_district_sales (마포)")
    sql = text("""
        SELECT quarter, industry_code, industry_name,
               SUM(monthly_sales) AS total_sales,
               COUNT(*) AS n_cells
        FROM seoul_district_sales
        WHERE dong_code LIKE '11440%' AND monthly_sales IS NOT NULL
        GROUP BY quarter, industry_code, industry_name
        ORDER BY quarter, industry_code
    """)
    with engine.connect() as c:
        df = pd.read_sql(sql, c)
    print(f"  rows: {len(df)}")
    return df


def compute_correlation_tests(kosis_df: pd.DataFrame, seoul_df: pd.DataFrame) -> dict:
    """KOSIS 지수 vs 마포 매출 분기 시계열 상관."""
    if kosis_df is None or len(kosis_df) == 0:
        return {"error": "no kosis data"}

    # KOSIS 응답에서 분기 추출 (수록시점 컬럼)
    val_col = next((c for c in kosis_df.columns if c in ("수치값", "DT", "value")), None)
    per_col = next((c for c in kosis_df.columns if c in ("수록시점", "PRD_DE", "period_value")), None)
    itm_col = next((c for c in kosis_df.columns if c in ("항목명", "ITM_NM", "item_name")), None)
    if not val_col or not per_col:
        return {"error": f"unknown kosis columns: {kosis_df.columns.tolist()}"}

    k = kosis_df[[per_col, val_col] + ([itm_col] if itm_col else [])].copy()
    k[val_col] = pd.to_numeric(k[val_col], errors="coerce")
    if itm_col:
        # 경상지수만 (원/불변이 아닌 가격 반영 지수)
        mask = k[itm_col].astype(str).str.contains("경상", na=False)
        if mask.sum() > 0:
            k = k[mask]

    # 분기 코드 정규화 — KOSIS는 prdSe='Q'일 때 'YYYYQQ' (QQ=01~04 분기 번호)로 반환
    def norm_q(p):
        p = str(p)
        if "Q" in p:
            y, q = p.split("Q")
            return int(y) * 10 + int(q)
        if len(p) == 6:  # YYYYQQ (분기 번호 01~04)
            y = int(p[:4])
            q = int(p[4:6])
            if 1 <= q <= 4:
                return y * 10 + q
        if len(p) == 5:  # YYYYQ directly
            return int(p)
        return None

    k["qkey"] = k[per_col].apply(norm_q)
    k = k.dropna(subset=["qkey", val_col]).groupby("qkey")[val_col].mean().reset_index()

    # 서울 쪽 집계: 전 업종 총합
    s = seoul_df.groupby("quarter")["total_sales"].sum().reset_index()
    s = s.rename(columns={"quarter": "qkey"})

    merged = k.merge(s, on="qkey", how="inner")
    print(f"  matched quarters: {len(merged)}")
    if len(merged) < 4:
        return {"error": "too few overlapping quarters", "n": len(merged)}

    r, _ = pearsonr(merged[val_col], merged["total_sales"])
    rs, _ = spearmanr(merged[val_col], merged["total_sales"])
    return {
        "n_quarters": len(merged),
        "pearson_r": round(float(r), 3),
        "spearman_rho": round(float(rs), 3),
        "kosis_min": float(merged[val_col].min()),
        "kosis_max": float(merged[val_col].max()),
        "seoul_min": int(merged["total_sales"].min()),
        "seoul_max": int(merged["total_sales"].max()),
        "data": merged,
    }


def write_report(service_idx_result: dict, seoul_breakdown: pd.DataFrame) -> None:
    lines: list[str] = []
    lines.append("# Phase 1-B: KOSIS ↔ seoul_district_sales 매칭 결과\n")
    lines.append("**목적:** KOSIS 시도 트렌드 지수가 마포 매출의 anchor로 사용 가능한지 검증\n")
    lines.append("---\n")

    lines.append("## 1. DT_1KC2023 서울 숙박·음식점업 지수 ↔ 마포 총매출 (분기)\n")
    if "error" in service_idx_result:
        lines.append(f"❌ **실패:** {service_idx_result['error']}\n")
    else:
        lines.append(f"- **매칭 분기 수:** {service_idx_result['n_quarters']}개")
        lines.append(f"- **Pearson r:** {service_idx_result['pearson_r']}")
        lines.append(f"- **Spearman ρ:** {service_idx_result['spearman_rho']}")
        lines.append(
            f"- KOSIS 지수 범위: {service_idx_result['kosis_min']:.1f} ~ {service_idx_result['kosis_max']:.1f}"
        )
        lines.append(f"- 마포 총매출 범위: {service_idx_result['seoul_min']:,} ~ {service_idx_result['seoul_max']:,}\n")

        r = service_idx_result["pearson_r"]
        if r >= 0.7:
            lines.append(f"✅ **판정:** r={r} ≥ 0.7 → anchor로 사용 가능\n")
        elif r >= 0.5:
            lines.append(f"⚠️ **판정:** r={r} — 보조 지표로만 사용 (단독 anchor는 부족)\n")
        else:
            lines.append(f"❌ **판정:** r={r} — anchor 부적합, 다른 테이블 탐색 필요\n")

    lines.append("## 2. 마포 매출 업종 구성 (참고)\n")
    if len(seoul_breakdown) > 0:
        by_ind = seoul_breakdown.groupby(["industry_code", "industry_name"])["total_sales"].sum()
        by_ind = by_ind.sort_values(ascending=False)
        total = by_ind.sum()
        lines.append("| 업종코드 | 업종명 | 총매출 (억원) | 비중 |")
        lines.append("|----|----|----:|----:|")
        for (code, name), v in by_ind.items():
            lines.append(f"| {code} | {name} | {v / 1e8:,.0f} | {v / total * 100:.1f}% |")

    lines.append("\n## 3. 다음 단계 (Phase 2)\n")
    lines.append("- 트렌드 anchor 확보 시: 분기 배율 정규화 (base=2020Q1)")
    lines.append("- SEMAS 상가정보 호출 → 동별 사업체 수 획득")
    lines.append("- 회귀 모형: `seoul_sales = α × 사업체수 × 지수 + β + ε` 학습")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"[saved] {OUT_MD}")

    # 매칭 시계열도 CSV 저장
    if "error" not in service_idx_result and "data" in service_idx_result:
        service_idx_result["data"].to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
        print(f"[saved] {OUT_CSV}")


if __name__ == "__main__":
    print("=== Phase 1-B: KOSIS Pairing Probe ===\n")
    kosis_df = fetch_kosis_service_index()
    seoul_df = load_seoul_sales_by_quarter()
    result = compute_correlation_tests(kosis_df, seoul_df)
    print(f"\n[result] {result if 'error' in result else {k: v for k, v in result.items() if k != 'data'}}")
    write_report(result, seoul_df)
