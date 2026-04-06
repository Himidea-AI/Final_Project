"""
매장용빌딩 임대료·공실률·수익률 전처리 스크립트

- 원본: 매장용빌딩+임대료·공실률+및+수익률_20260406093748.csv (서울 열린데이터)
- 마포구 관련 상권(영등포신촌지역) + 서울 평균 필터링
- 기존 rent_small_store_mapo.csv와 통합하여 2019~2025 시계열 생성
- 출력: data/processed/rent_building_mapo.csv
"""

from pathlib import Path

import pandas as pd

# --- 경로 설정 ---
RAW_FILE = Path(
    r"C:\Users\804\Desktop\데이터 파일\매장용빌딩+임대료·공실률+및+수익률_20260406093748.csv"
)
EXISTING_RENT = Path("processed/rent_small_store_mapo.csv")
OUTPUT_FILE = Path("processed/rent_building_mapo.csv")


def parse_building_rent(filepath: Path) -> pd.DataFrame:
    """멀티헤더 와이드 CSV를 long format으로 변환."""
    # 3행 헤더 스킵, 데이터만 로드
    df_raw = pd.read_csv(filepath, header=None, skiprows=3, encoding="utf-8-sig")

    # 헤더 행 읽기 (분기/지표 매핑용)
    headers = pd.read_csv(filepath, header=None, nrows=3, encoding="utf-8-sig")

    # row1: 기간 (2019 1/4, ..., 2019, 2020, ...)
    # row2: 지표명 (임대료, 공실률, 수익률 정보 ...)
    # row3: 세부 (소계, 투자수익률, 소득수익률, 자본수익률)
    periods = headers.iloc[0].tolist()
    metrics = headers.iloc[1].tolist()
    sub_metrics = headers.iloc[2].tolist()

    # 분기별 컬럼만 추출 (연간 집계 제외)
    # 분기: "2019 1/4" 형태, 연간: "2019" 형태
    quarterly_cols = []
    for i in range(2, len(periods)):
        p = str(periods[i]).strip()
        if "/" in p:  # 분기 데이터
            year = p.split()[0]
            quarter = p.split()[1].replace("/4", "")
            metric = str(metrics[i]).strip()
            sub = str(sub_metrics[i]).strip()

            # 지표 이름 정리
            if "임대료" in metric:
                col_name = "rent"
            elif "공실률" in metric:
                col_name = "vacancy_rate"
            elif "수익률" in metric:
                if "투자" in sub:
                    col_name = "investment_return"
                elif "소득" in sub:
                    col_name = "income_return"
                elif "자본" in sub:
                    col_name = "capital_return"
                else:
                    continue
            else:
                continue

            quarterly_cols.append(
                {
                    "col_idx": i,
                    "year": int(year),
                    "quarter": int(quarter),
                    "period": f"{year}_{quarter}분기",
                    "metric": col_name,
                }
            )

    # 데이터 추출
    rows = []
    for _, row in df_raw.iterrows():
        region1 = str(row[0]).strip().strip('"')
        region2 = str(row[1]).strip().strip('"')

        for col_info in quarterly_cols:
            val = row[col_info["col_idx"]]
            if pd.isna(val) or str(val).strip() in ("-", ""):
                continue
            try:
                val = float(val)
            except (ValueError, TypeError):
                continue

            rows.append(
                {
                    "region_group": region1,
                    "region": region2,
                    "year": col_info["year"],
                    "quarter": col_info["quarter"],
                    "period": col_info["period"],
                    "metric": col_info["metric"],
                    "value": val,
                }
            )

    df_long = pd.DataFrame(rows)
    return df_long


def filter_mapo_regions(df: pd.DataFrame) -> pd.DataFrame:
    """마포구 관련 상권 + 서울 전체 평균 필터링."""
    # 마포구 관련: 영등포신촌지역 전체 + 서울 소계
    mask = (df["region_group"] == "영등포신촌지역") | (
        (df["region_group"] == "서울") & (df["region"] == "소계")
    )
    df_filtered = df[mask].copy()

    # 지역명 정리: 행정동 매핑에 사용할 표준 이름
    region_mapping = {
        ("서울", "소계"): "서울_평균",
        ("영등포신촌지역", "소계"): "영등포신촌_평균",
        ("영등포신촌지역", "공덕역"): "공덕역",
        ("영등포신촌지역", "당산역"): "당산역",
        ("영등포신촌지역", "동교/연남"): "동교/연남",
        ("영등포신촌지역", "망원역"): "망원역",
        ("영등포신촌지역", "신촌/이대"): "신촌/이대",
        ("영등포신촌지역", "영등포"): "영등포",
        ("영등포신촌지역", "홍대/합정"): "홍대/합정",
    }
    df_filtered["area_name"] = df_filtered.apply(
        lambda r: region_mapping.get((r["region_group"], r["region"]), r["region"]),
        axis=1,
    )
    return df_filtered


def pivot_to_wide(df: pd.DataFrame) -> pd.DataFrame:
    """long → wide: 지역 × 기간별 지표 컬럼."""
    df_pivot = df.pivot_table(
        index=["area_name", "year", "quarter", "period"],
        columns="metric",
        values="value",
        aggfunc="first",
    ).reset_index()

    df_pivot.columns.name = None

    # 컬럼 순서 정리
    col_order = ["area_name", "year", "quarter", "period"]
    metric_cols = [
        "rent",
        "vacancy_rate",
        "investment_return",
        "income_return",
        "capital_return",
    ]
    for mc in metric_cols:
        if mc in df_pivot.columns:
            col_order.append(mc)

    return (
        df_pivot[col_order]
        .sort_values(["area_name", "year", "quarter"])
        .reset_index(drop=True)
    )


def merge_with_existing(df_new: pd.DataFrame, existing_path: Path) -> pd.DataFrame:
    """기존 rent_small_store_mapo.csv와 통합."""
    if not existing_path.exists():
        print(f"[WARN] 기존 파일 없음: {existing_path}, 새 데이터만 사용")
        return df_new

    df_old = pd.read_csv(existing_path)

    # 기존 데이터: wide → long 변환
    old_rows = []
    for _, row in df_old.iterrows():
        region = str(row["지역"]).strip()
        # 지역명 표준화
        region = (
            region.replace("서울 영등포신촌 ", "")
            .replace("서울  영등포신촌", "")
            .strip()
        )
        if not region:
            region = "영등포신촌_평균"
        # 공백 제거 후 매핑
        region = (
            region.replace("홍대합정", "홍대/합정").replace("신촌", "신촌/이대")
            if "신촌/이대" not in region
            else region
        )

        for col in df_old.columns:
            if col in ("source_year", "지역"):
                continue
            val = row[col]
            if pd.isna(val):
                continue
            # "2019_1분기" → year=2019, quarter=1
            parts = col.split("_")
            year = int(parts[0])
            quarter = int(parts[1].replace("분기", ""))

            old_rows.append(
                {
                    "area_name": region,
                    "year": year,
                    "quarter": quarter,
                    "period": col,
                    "rent": float(val),
                    "source": "rent_small_store",
                }
            )

    df_old_long = pd.DataFrame(old_rows)

    # 새 데이터에 source 표시
    df_new["source"] = "building_rent"

    # 통합: 새 데이터 우선 (같은 지역/기간이면 새 데이터 사용)
    df_merged = pd.concat([df_old_long, df_new], ignore_index=True)
    df_merged = df_merged.drop_duplicates(
        subset=["area_name", "year", "quarter", "period"],
        keep="last",  # 새 데이터(building_rent) 우선
    )
    return df_merged.sort_values(["area_name", "year", "quarter"]).reset_index(
        drop=True
    )


def main():
    print("=== 매장용빌딩 임대료 전처리 시작 ===")

    # Step 1: 파싱
    print("[1/4] CSV 파싱 (멀티헤더 → long format)...")
    df_long = parse_building_rent(RAW_FILE)
    print(f"  전체: {len(df_long)}행, 지역: {df_long['region_group'].nunique()}개 그룹")

    # Step 2: 마포구 관련 필터링
    print("[2/4] 마포구 관련 상권 필터링...")
    df_mapo = filter_mapo_regions(df_long)
    print(
        f"  필터링 후: {len(df_mapo)}행, 상권: {df_mapo['area_name'].unique().tolist()}"
    )

    # Step 3: wide format 변환
    print("[3/4] wide format 변환...")
    df_wide = pivot_to_wide(df_mapo)
    print(f"  피벗 후: {df_wide.shape}")

    # Step 4: 기존 데이터와 통합
    print("[4/4] 기존 rent_small_store_mapo.csv와 통합...")
    df_final = merge_with_existing(df_wide, EXISTING_RENT)

    # 저장
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"\n=== 완료: {OUTPUT_FILE} ({len(df_final)}행) ===")

    # 요약 출력
    print("\n--- 데이터 요약 ---")
    print(f"지역 수: {df_final['area_name'].nunique()}")
    print(
        f"기간: {df_final['year'].min()} Q{df_final['quarter'].min()} ~ "
        f"{df_final['year'].max()} Q{df_final['quarter'].max()}"
    )
    if "rent" in df_final.columns:
        print(
            f"임대료 범위: {df_final['rent'].min():.1f} ~ {df_final['rent'].max():.1f} 천원/㎡"
        )
    if "vacancy_rate" in df_final.columns:
        non_null = df_final["vacancy_rate"].notna().sum()
        print(f"공실률 데이터: {non_null}행")


if __name__ == "__main__":
    main()
