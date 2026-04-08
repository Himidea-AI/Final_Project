"""서울 전체 25개구 추정매출 + 점포수 전처리 스크립트.

IM3-111: 서울 전체 추정매출 전처리 -> seoul_district_sales.csv
IM3-112: 서울 전체 점포수 전처리 -> seoul_district_stores.csv

원본: 바탕화면 '데이터 파일' 폴더의 서울시 상권분석서비스 CSV (2019~2024)
"""

from pathlib import Path

import pandas as pd

SRC_DIR = Path(r"C:\Users\804\Desktop\데이터 파일")
PROC_DIR = Path(__file__).resolve().parent.parent / "processed"

# 음식점 10개 업종 코드
FOOD_INDUSTRY_CODES = [f"CS10000{i}" for i in range(1, 10)] + ["CS100010"]

# 서울시 행정동코드는 '11'로 시작 (25개 구)
SEOUL_PREFIX = "11"

# ── 추정매출 컬럼 매핑 (한글 -> 영문) ──
SALES_COL_MAP = {
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

# ── 점포수 컬럼 매핑 (한글 -> 영문) ──
STORES_COL_MAP = {
    "기준_년분기_코드": "STDR_YYQU_CD",
    "행정동_코드": "행정동코드",
    "행정동_코드_명": "행정동명",
    "서비스_업종_코드": "SVC_INDUTY_CD",
    "서비스_업종_코드_명": "SVC_INDUTY_CD_NM",
    "점포_수": "STOR_CO",
    "유사_업종_점포_수": "SIMILR_INDUTY_STOR_CO",
    "개업_점포_수": "OPBIZ_STOR_CO",
    "폐업_점포_수": "CLSBIZ_STOR_CO",
    "프랜차이즈_점포_수": "FRC_STOR_CO",
    "폐업_률": "CLSBIZ_RT",
}


def _read_csv(filepath: Path) -> pd.DataFrame:
    """cp949 / utf-8-sig / utf-8 순서로 시도하여 CSV를 읽는다."""
    for enc in ["cp949", "utf-8-sig", "utf-8"]:
        try:
            return pd.read_csv(
                filepath,
                encoding=enc,
                dtype={"행정동_코드": str},
                low_memory=False,
            )
        except (UnicodeDecodeError, LookupError):
            continue
    msg = f"Cannot decode {filepath}"
    raise ValueError(msg)


def _filter_seoul_food(df: pd.DataFrame) -> pd.DataFrame:
    """서울 전체 행정동 + 음식점 10개 업종만 필터."""
    mask_seoul = df["행정동_코드"].str.startswith(SEOUL_PREFIX, na=False)
    mask_food = df["서비스_업종_코드"].isin(FOOD_INDUSTRY_CODES)
    return df[mask_seoul & mask_food].copy()


# ────────────────────────────────────────────
# IM3-111: 서울 전체 추정매출
# ────────────────────────────────────────────
def build_seoul_sales() -> None:
    """6개 연도 추정매출 CSV -> seoul_district_sales.csv"""
    files = sorted(SRC_DIR.glob("*추정매출-행정동*년.csv"))
    print(f"[Sales] Found {len(files)} files")

    dfs: list[pd.DataFrame] = []
    for f in files:
        df = _read_csv(f)
        filtered = _filter_seoul_food(df)
        n_gu = filtered["행정동_코드"].str[:5].nunique()
        print(f"  {f.name}: {len(filtered):,} rows, {n_gu} gu")
        dfs.append(filtered)

    merged = pd.concat(dfs, ignore_index=True)

    # 컬럼 리네임
    rename = {k: v for k, v in SALES_COL_MAP.items() if k in merged.columns}
    merged = merged.rename(columns=rename)

    # 기존 district_sales.csv와 동일한 컬럼 순서
    target_cols = list(SALES_COL_MAP.values())
    available = [c for c in target_cols if c in merged.columns]
    merged = merged[available].copy()

    merged = merged.sort_values(["행정동코드", "STDR_YYQU_CD", "SVC_INDUTY_CD"]).reset_index(drop=True)

    outpath = PROC_DIR / "seoul_district_sales.csv"
    merged.to_csv(outpath, index=False, encoding="utf-8-sig")

    n_gu = merged["행정동코드"].str[:5].nunique()
    n_dong = merged["행정동코드"].nunique()
    period = f"{merged['STDR_YYQU_CD'].min()} ~ {merged['STDR_YYQU_CD'].max()}"
    print(f"\n  -> {outpath.name}: {len(merged):,} rows, {n_gu} gu, {n_dong} dongs, period {period}")


# ────────────────────────────────────────────
# IM3-112: 서울 전체 점포수
# ────────────────────────────────────────────
def build_seoul_stores() -> None:
    """6개 연도 점포 CSV -> seoul_district_stores.csv"""
    files = sorted(SRC_DIR.glob("*점포-행정동*년.csv"))
    print(f"\n[Stores] Found {len(files)} files")

    dfs: list[pd.DataFrame] = []
    for f in files:
        df = _read_csv(f)
        filtered = _filter_seoul_food(df)
        n_gu = filtered["행정동_코드"].str[:5].nunique()
        print(f"  {f.name}: {len(filtered):,} rows, {n_gu} gu")
        dfs.append(filtered)

    merged = pd.concat(dfs, ignore_index=True)

    # 컬럼 리네임
    rename = {k: v for k, v in STORES_COL_MAP.items() if k in merged.columns}
    merged = merged.rename(columns=rename)

    # 컬럼 순서 맞추기
    target_cols = list(STORES_COL_MAP.values())
    available = [c for c in target_cols if c in merged.columns]
    merged = merged[available].copy()

    merged = merged.sort_values(["행정동코드", "STDR_YYQU_CD", "SVC_INDUTY_CD"]).reset_index(drop=True)

    outpath = PROC_DIR / "seoul_district_stores.csv"
    merged.to_csv(outpath, index=False, encoding="utf-8-sig")

    n_gu = merged["행정동코드"].str[:5].nunique()
    n_dong = merged["행정동코드"].nunique()
    period = f"{merged['STDR_YYQU_CD'].min()} ~ {merged['STDR_YYQU_CD'].max()}"
    print(f"\n  -> {outpath.name}: {len(merged):,} rows, {n_gu} gu, {n_dong} dongs, period {period}")


def main() -> None:
    print("=" * 60)
    print("서울 전체 25개구 전처리 (추정매출 + 점포수)")
    print("=" * 60)

    PROC_DIR.mkdir(parents=True, exist_ok=True)

    build_seoul_sales()
    build_seoul_stores()

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
