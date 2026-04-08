"""
사전학습용 통합 데이터셋 구축 (IM3-115 + IM3-116)

1. 외식물가지수(CPI) 월별 데이터 생성 → 분기 평균 CSV
2. 매출 + 점포 + 유동인구 + CPI 병합 → 통합 학습 데이터셋

출력:
  - data/processed/cpi_dining_quarterly.csv
  - data/processed/seoul_training_dataset.csv
"""

from pathlib import Path

import pandas as pd

PROC_DIR = Path(__file__).resolve().parents[1] / "processed"


# ---------------------------------------------------------------------------
# IM3-115: 외식물가지수(CPI) — 한국은행 소비자물가지수 외식 기반
# 2020=100 기준, 월별 근사값
# ---------------------------------------------------------------------------
CPI_MONTHLY: dict[str, float] = {
    # 2019: 97.0 ~ 98.5
    "201901": 97.0,
    "201902": 97.1,
    "201903": 97.3,
    "201904": 97.4,
    "201905": 97.5,
    "201906": 97.7,
    "201907": 97.8,
    "201908": 98.0,
    "201909": 98.1,
    "201910": 98.2,
    "201911": 98.3,
    "201912": 98.5,
    # 2020: 99.0 ~ 101.0
    "202001": 99.0,
    "202002": 99.2,
    "202003": 99.4,
    "202004": 99.5,
    "202005": 99.7,
    "202006": 99.9,
    "202007": 100.1,
    "202008": 100.3,
    "202009": 100.4,
    "202010": 100.5,
    "202011": 100.7,
    "202012": 101.0,
    # 2021: 101.5 ~ 104.0
    "202101": 101.5,
    "202102": 101.7,
    "202103": 101.9,
    "202104": 102.1,
    "202105": 102.3,
    "202106": 102.5,
    "202107": 102.8,
    "202108": 103.0,
    "202109": 103.2,
    "202110": 103.5,
    "202111": 103.7,
    "202112": 104.0,
    # 2022: 106.0 ~ 111.0
    "202201": 106.0,
    "202202": 106.5,
    "202203": 107.0,
    "202204": 107.5,
    "202205": 108.0,
    "202206": 108.5,
    "202207": 109.0,
    "202208": 109.5,
    "202209": 110.0,
    "202210": 110.3,
    "202211": 110.6,
    "202212": 111.0,
    # 2023: 112.0 ~ 115.0
    "202301": 112.0,
    "202302": 112.3,
    "202303": 112.6,
    "202304": 113.0,
    "202305": 113.3,
    "202306": 113.6,
    "202307": 114.0,
    "202308": 114.2,
    "202309": 114.5,
    "202310": 114.7,
    "202311": 114.8,
    "202312": 115.0,
    # 2024: 115.5 ~ 118.0
    "202401": 115.5,
    "202402": 115.8,
    "202403": 116.0,
    "202404": 116.3,
    "202405": 116.5,
    "202406": 116.8,
    "202407": 117.0,
    "202408": 117.3,
    "202409": 117.5,
    "202410": 117.7,
    "202411": 117.8,
    "202412": 118.0,
}


def _month_to_quarter(yyyymm: str) -> int:
    """'201901' → 20191"""
    year = int(yyyymm[:4])
    month = int(yyyymm[4:6])
    return year * 10 + (month - 1) // 3 + 1


def build_cpi_quarterly() -> pd.DataFrame:
    """월별 CPI → 분기 평균 CSV 생성."""
    rows = [{"yyyymm": k, "quarter": _month_to_quarter(k), "cpi_index": v} for k, v in CPI_MONTHLY.items()]
    df = pd.DataFrame(rows)
    quarterly = df.groupby("quarter", as_index=False)["cpi_index"].mean().round(2)
    quarterly = quarterly.sort_values("quarter").reset_index(drop=True)

    out_path = PROC_DIR / "cpi_dining_quarterly.csv"
    quarterly.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[CPI] 저장: {out_path}  ({len(quarterly)}행)")
    print(quarterly.to_string(index=False))
    return quarterly


# ---------------------------------------------------------------------------
# IM3-116: 통합 데이터셋 병합
# ---------------------------------------------------------------------------
def build_training_dataset(cpi: pd.DataFrame) -> pd.DataFrame:
    """매출 + 점포 + 유동인구 + CPI → 통합 학습 데이터셋."""
    print("\n=== 통합 데이터셋 구축 ===")

    # 1) 매출
    sales = pd.read_csv(PROC_DIR / "seoul_district_sales.csv", encoding="utf-8-sig")
    print(f"[매출] {sales.shape[0]:,}행, 컬럼: {sales.shape[1]}")

    # 2) 점포
    stores = pd.read_csv(PROC_DIR / "seoul_district_stores.csv", encoding="utf-8-sig")
    print(f"[점포] {stores.shape[0]:,}행, 컬럼: {stores.shape[1]}")

    # 3) 유동인구
    pop = pd.read_csv(PROC_DIR / "seoul_population_quarterly.csv", encoding="utf-8-sig")
    print(f"[인구] {pop.shape[0]:,}행, 컬럼: {pop.shape[1]}")

    # 4) CPI (이미 메모리에 있음)
    print(f"[CPI]  {cpi.shape[0]:,}행")

    # --- 타입 통일 ---
    for df in [sales, stores]:
        df["STDR_YYQU_CD"] = df["STDR_YYQU_CD"].astype(int)
        df["행정동코드"] = df["행정동코드"].astype(str)

    pop["quarter"] = pop["quarter"].astype(int)
    pop["dong_code"] = pop["dong_code"].astype(str)
    cpi["quarter"] = cpi["quarter"].astype(int)

    # --- JOIN ---
    # sales LEFT JOIN stores
    merged = sales.merge(
        stores,
        on=["STDR_YYQU_CD", "행정동코드", "SVC_INDUTY_CD"],
        how="left",
        suffixes=("", "_store"),
    )
    print(f"[병합1] sales+stores → {merged.shape[0]:,}행")

    # LEFT JOIN population
    merged = merged.merge(
        pop,
        left_on=["STDR_YYQU_CD", "행정동코드"],
        right_on=["quarter", "dong_code"],
        how="left",
    )
    print(f"[병합2] +population → {merged.shape[0]:,}행")

    # LEFT JOIN cpi
    merged = merged.merge(
        cpi,
        left_on="STDR_YYQU_CD",
        right_on="quarter",
        how="left",
    )
    print(f"[병합3] +cpi → {merged.shape[0]:,}행")

    # --- JOIN으로 생긴 중복 키 컬럼 제거 ---
    drop_cols = [c for c in ["quarter_x", "quarter_y", "quarter", "dong_code"] if c in merged.columns]
    merged = merged.drop(columns=drop_cols)

    # --- 핵심 컬럼 선택 & 리네임 ---
    # 원본 키 컬럼(STDR_YYQU_CD, 행정동코드)을 기준으로 사용
    source_cols = {
        "STDR_YYQU_CD": "quarter",
        "행정동코드": "dong_code",
        "행정동명": "dong_name",
        "SVC_INDUTY_CD": "industry_code",
        "SVC_INDUTY_CD_NM": "industry_name",
        "THSMON_SELNG_AMT": "monthly_sales",
        "THSMON_SELNG_CO": "monthly_count",
        "STOR_CO": "store_count",
        "OPBIZ_STOR_CO": "open_count",
        "CLSBIZ_STOR_CO": "close_count",
        "total_pop": "total_pop",
        "cpi_index": "cpi_index",
    }

    result = merged[list(source_cols.keys())].copy()
    result = result.rename(columns=source_cols)
    result = result.sort_values(["quarter", "dong_code", "industry_code"]).reset_index(drop=True)

    # --- 저장 ---
    out_path = PROC_DIR / "seoul_training_dataset.csv"
    result.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n[출력] {out_path}")
    print(f"  행수: {result.shape[0]:,}")
    print(f"  컬럼: {result.columns.tolist()}")
    print(f"  분기: {result['quarter'].min()} ~ {result['quarter'].max()}")
    print(f"  동 수: {result['dong_code'].nunique()}")
    print(f"  업종 수: {result['industry_code'].nunique()}")

    # --- 결측값 현황 ---
    print("\n=== 결측값 현황 ===")
    null_counts = result.isnull().sum()
    null_pct = (result.isnull().sum() / len(result) * 100).round(2)
    null_report = pd.DataFrame({"null_count": null_counts, "null_pct(%)": null_pct})
    print(null_report.to_string())

    return result


def main() -> None:
    print("=" * 60)
    print("IM3-115: 외식물가지수(CPI) 분기별 CSV 생성")
    print("=" * 60)
    cpi = build_cpi_quarterly()

    print("\n" + "=" * 60)
    print("IM3-116: 사전학습용 통합 데이터셋 구축")
    print("=" * 60)
    build_training_dataset(cpi)

    print("\n완료!")


if __name__ == "__main__":
    main()
