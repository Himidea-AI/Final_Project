"""
행정동 추정매출 전처리 스크립트

- 원본: 서울시 상권분석서비스(추정매출-행정동) 2019~2024년 CSV 6개
- 마포구 16개 동 필터링
- 기존 district_sales.csv 교체 (13동 -> 16동)
- district_trend_timeseries.csv 교체 (13동 -> 16동)
"""

from pathlib import Path

import pandas as pd

SRC_DIR = Path(r"C:\Users\804\Desktop\데이터 파일")
PROC_DIR = Path("processed")

# 새 데이터 컬럼 -> 기존 컬럼 매핑
COL_MAP = {
    "기준_년분기_코드": "STDR_YYQU_CD",
    "행정동_코드": "행정동코드",
    "행정동_코드_명": "행정동명",
    "서비스_업종_코드": "SVC_INDUTY_CD",
    "서비스_업종_코드_명": "SVC_INDUTY_CD_NM",
    "당월_매출_금액": "THSMON_SELNG_AMT",
    "당월_매출_건수": "THSMON_SELNG_CO",
    "주중_매출_금액": "MDWK_SELNG_AMT",
    "주말_매출_금액": "WKEND_SELNG_AMT",
    "월요일_매출_금액": "MON_SELNG_AMT",
    "화요일_매출_금액": "TUES_SELNG_AMT",
    "수요일_매출_금액": "WED_SELNG_AMT",
    "목요일_매출_금액": "THUR_SELNG_AMT",
    "금요일_매출_금액": "FRI_SELNG_AMT",
    "토요일_매출_금액": "SAT_SELNG_AMT",
    "일요일_매출_금액": "SUN_SELNG_AMT",
    "시간대_00~06_매출_금액": "TMZON_00_06_SELNG_AMT",
    "시간대_06~11_매출_금액": "TMZON_06_11_SELNG_AMT",
    "시간대_11~14_매출_금액": "TMZON_11_14_SELNG_AMT",
    "시간대_14~17_매출_금액": "TMZON_14_17_SELNG_AMT",
    "시간대_17~21_매출_금액": "TMZON_17_21_SELNG_AMT",
    "시간대_21~24_매출_금액": "TMZON_21_24_SELNG_AMT",
    "남성_매출_금액": "ML_SELNG_AMT",
    "여성_매출_금액": "FML_SELNG_AMT",
    "연령대_10_매출_금액": "AGRDE_10_SELNG_AMT",
    "연령대_20_매출_금액": "AGRDE_20_SELNG_AMT",
    "연령대_30_매출_금액": "AGRDE_30_SELNG_AMT",
    "연령대_40_매출_금액": "AGRDE_40_SELNG_AMT",
    "연령대_50_매출_금액": "AGRDE_50_SELNG_AMT",
    "연령대_60_이상_매출_금액": "AGRDE_60_ABOVE_SELNG_AMT",
    "주중_매출_건수": "MDWK_SELNG_CO",
    "주말_매출_건수": "WKEND_SELNG_CO",
    "월요일_매출_건수": "MON_SELNG_CO",
    "화요일_매출_건수": "TUES_SELNG_CO",
    "수요일_매출_건수": "WED_SELNG_CO",
    "목요일_매출_건수": "THUR_SELNG_CO",
    "금요일_매출_건수": "FRI_SELNG_CO",
    "토요일_매출_건수": "SAT_SELNG_CO",
    "일요일_매출_건수": "SUN_SELNG_CO",
    "시간대_건수~06_매출_건수": "TMZON_00_06_SELNG_CO",
    "시간대_건수~11_매출_건수": "TMZON_06_11_SELNG_CO",
    "시간대_건수~14_매출_건수": "TMZON_11_14_SELNG_CO",
    "시간대_건수~17_매출_건수": "TMZON_14_17_SELNG_CO",
    "시간대_건수~21_매출_건수": "TMZON_17_21_SELNG_CO",
    "시간대_건수~24_매출_건수": "TMZON_21_24_SELNG_CO",
    "남성_매출_건수": "ML_SELNG_CO",
    "여성_매출_건수": "FML_SELNG_CO",
    "연령대_10_매출_건수": "AGRDE_10_SELNG_CO",
    "연령대_20_매출_건수": "AGRDE_20_SELNG_CO",
    "연령대_30_매출_건수": "AGRDE_30_SELNG_CO",
    "연령대_40_매출_건수": "AGRDE_40_SELNG_CO",
    "연령대_50_매출_건수": "AGRDE_50_SELNG_CO",
    "연령대_60_이상_매출_건수": "AGRDE_60_ABOVE_SELNG_CO",
}


def load_all_years() -> pd.DataFrame:
    """6개 연도 CSV를 통합 로드, 마포구만 필터."""
    files = sorted(SRC_DIR.glob("*추정매출-행정동*년.csv"))
    print(f"Found {len(files)} files")

    dfs = []
    for f in files:
        for enc in ["cp949", "utf-8-sig", "utf-8"]:
            try:
                df = pd.read_csv(f, encoding=enc, dtype={"행정동_코드": str}, low_memory=False)
                break
            except (UnicodeDecodeError, LookupError):
                continue

        # 마포구 필터 (11440으로 시작)
        mapo = df[df["행정동_코드"].str.startswith("11440", na=False)].copy()
        print(f"  {f.name}: {len(mapo)} rows, {mapo['행정동_코드_명'].nunique()} dongs")
        dfs.append(mapo)

    result = pd.concat(dfs, ignore_index=True)
    return result


def build_district_sales(df: pd.DataFrame) -> None:
    """district_sales.csv 교체 (16개 동)."""
    # 컬럼명 변환
    rename = {k: v for k, v in COL_MAP.items() if k in df.columns}
    df_out = df.rename(columns=rename)

    # 기존 district_sales.csv 컬럼 순서에 맞추기
    existing = pd.read_csv(PROC_DIR / "district_sales.csv", nrows=0, low_memory=False)
    target_cols = existing.columns.tolist()

    # 존재하는 컬럼만 선택
    available = [c for c in target_cols if c in df_out.columns]
    df_out = df_out[available].copy()

    df_out = df_out.sort_values(["행정동명", "STDR_YYQU_CD", "SVC_INDUTY_CD"]).reset_index(drop=True)
    df_out.to_csv(PROC_DIR / "district_sales.csv", index=False, encoding="utf-8-sig")
    print(f"district_sales.csv: {len(df_out)} rows, {df_out['행정동명'].nunique()} dongs")


def build_trend_timeseries(df: pd.DataFrame) -> None:
    """district_trend_timeseries.csv 교체 (16개 동)."""
    rename = {k: v for k, v in COL_MAP.items() if k in df.columns}
    df_r = df.rename(columns=rename)

    df_out = pd.DataFrame({
        "quarter": df_r["STDR_YYQU_CD"],
        "dong_code": df_r["행정동코드"],
        "dong_name": df_r["행정동명"],
        "industry_code": df_r["SVC_INDUTY_CD"],
        "industry_name": df_r["SVC_INDUTY_CD_NM"],
        "monthly_sales": df_r["THSMON_SELNG_AMT"],
        "monthly_count": df_r["THSMON_SELNG_CO"],
    })

    df_out = df_out.sort_values(["dong_name", "quarter", "industry_code"]).reset_index(drop=True)
    df_out.to_csv(PROC_DIR / "district_trend_timeseries.csv", index=False, encoding="utf-8-sig")
    print(f"district_trend_timeseries.csv: {len(df_out)} rows, {df_out['dong_name'].nunique()} dongs")


def main():
    print("=== 행정동 추정매출 전처리 시작 ===\n")

    df = load_all_years()
    print(f"\nTotal Mapo: {len(df)} rows")
    print(f"Dongs: {sorted(df['행정동_코드_명'].unique())}")
    print(f"Period: {df['기준_년분기_코드'].min()} ~ {df['기준_년분기_코드'].max()}")
    print()

    build_district_sales(df)
    build_trend_timeseries(df)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
