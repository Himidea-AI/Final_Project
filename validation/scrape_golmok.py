"""골목상권 API 스크래퍼 — 마포구 외식업 전체 데이터 수집

수집 항목:
  - store: 점포수 (전체/일반/프랜차이즈)
  - survival: 생존율 (1년/3년/5년)
  - survival2: 연차별 생존율
  - operatingPeriod: 평균영업기간
  - opening: 개폐업 (개업수/폐업수/개업률/폐업률)
  - population: 인구수 (유동/건물/상주/직장)
  - income: 소득구간/가구수
  - sales: 평균월매출
"""

import time
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://golmok.seoul.go.kr"
MAPO_CD = "11440"

IND_CODES = {
    "CS100001": "한식", "CS100002": "중식", "CS100003": "일식",
    "CS100004": "양식", "CS100005": "제과", "CS100006": "패스트푸드",
    "CS100007": "치킨", "CS100008": "분식", "CS100009": "호프",
    "CS100010": "커피",
}

ENDPOINTS = {
    "store": "/region/selectStoreCount.json",
    "survival": "/region/selectSurvivalRate.json",
    "survival2": "/region/selectSurvivalRate2.json",
    "operatingPeriod": "/region/selectSurvivalAvg.json",
    "opening": "/region/selectOpening.json",
    "population": "/region/selectPopulation.json",
    "income": "/region/selectIncome.json",
    "sales": "/region/selectSalesStatus.json",
}

# API는 요청 분기 기준 최근 3분기를 반환 (FIRST=요청분기, SECOND=1전, THIRD=2전)
QUERY_QUARTERS = [
    (2019, 3),  # 2019Q3, Q2, Q1
    (2020, 2),  # 2020Q2, Q1, 2019Q4
    (2020, 4),  # 2020Q4, Q3, Q2
    (2021, 3),  # 2021Q3, Q2, Q1
    (2022, 2),  # 2022Q2, Q1, 2021Q4
    (2022, 4),  # 2022Q4, Q3, Q2
    (2023, 3),  # 2023Q3, Q2, Q1
    (2024, 2),  # 2024Q2, Q1, 2023Q4
    (2024, 4),  # 2024Q4, Q3, Q2
]

DONG_ONLY_CATEGORIES = {"population", "income"}


def fetch(category, year, quarter, ind_code):
    url = BASE_URL + ENDPOINTS[category]
    params = {
        "stdrYyCd": str(year), "stdrQuCd": str(quarter),
        "selectTerm": "quarter", "svcIndutyCdL": "CS100000",
        "svcIndutyCdM": ind_code, "stdrSigngu": MAPO_CD,
        "selectInduty": "1", "infoCategory": category,
        "stdrSlctQu": "", "stdrMnCd": "",
    }
    try:
        resp = requests.post(url, data=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [ERR] {category} {year}Q{quarter} {ind_code}: {e}")
        return []


def qtr_offset(year, qu, offset):
    """FIRST=offset0(요청분기), SECOND=offset1(1전), THIRD=offset2(2전)"""
    total_q = year * 4 + qu - offset
    y = (total_q - 1) // 4
    q = (total_q - 1) % 4 + 1
    return y * 10 + q


def safe_float(v):
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def parse_store(records, year, qu):
    rows = []
    for rec in records:
        if rec.get("GUBUN") != "dong":
            continue
        for i, prefix in enumerate(["FIRST", "SECOND", "THIRD"]):
            rows.append({
                "quarter": qtr_offset(year, qu, i),
                "dong_code": rec["CD"], "dong_name": rec["NM"],
                "store_total": safe_float(rec.get(f"{prefix}_TOT")),
                "store_normal": safe_float(rec.get(f"{prefix}_NOR")),
                "store_franchise": safe_float(rec.get(f"{prefix}_FRC")),
            })
    return rows


def parse_survival(records, year, qu):
    rows = []
    for rec in records:
        if rec.get("GUBUN") != "dong":
            continue
        for i, prefix in enumerate(["FIRST", "SECOND", "THIRD"]):
            rows.append({
                "quarter": qtr_offset(year, qu, i),
                "dong_code": rec["CD"], "dong_name": rec["NM"],
                "survival_1y": safe_float(rec.get(f"{prefix}_1Y")),
                "survival_3y": safe_float(rec.get(f"{prefix}_3Y")),
                "survival_5y": safe_float(rec.get(f"{prefix}_5Y")),
                "survival_1y_num": safe_float(rec.get(f"{prefix}_1Y_MOL")),
                "survival_1y_den": safe_float(rec.get(f"{prefix}_1Y_DEN")),
                "survival_3y_num": safe_float(rec.get(f"{prefix}_3Y_MOL")),
                "survival_3y_den": safe_float(rec.get(f"{prefix}_3Y_DEN")),
                "survival_5y_num": safe_float(rec.get(f"{prefix}_5Y_MOL")),
                "survival_5y_den": safe_float(rec.get(f"{prefix}_5Y_DEN")),
            })
    return rows


def parse_survival2(records, year, qu):
    rows = []
    for rec in records:
        if rec.get("GUBUN") != "dong":
            continue
        for i, prefix in enumerate(["FIRST", "SECOND", "THIRD"]):
            rows.append({
                "quarter": qtr_offset(year, qu, i),
                "dong_code": rec["CD"], "dong_name": rec["NM"],
                "surv2_1y": safe_float(rec.get(f"{prefix}_1Y")),
                "surv2_3y": safe_float(rec.get(f"{prefix}_3Y")),
                "surv2_5y": safe_float(rec.get(f"{prefix}_5Y")),
            })
    return rows


def parse_operating_period(records, year, qu):
    rows = []
    for rec in records:
        if rec.get("GUBUN") != "dong":
            continue
        # FIRSTAVG, SECONDAVG, THIRDAVG (전체 평균), *_90 (상위90%)
        for i, prefix in enumerate(["FIRST", "SECOND", "THIRD"]):
            rows.append({
                "quarter": qtr_offset(year, qu, i),
                "dong_code": rec["CD"], "dong_name": rec["NM"],
                "avg_oper_period": safe_float(rec.get(f"{prefix}AVG")),
                "avg_oper_period_90": safe_float(rec.get(f"{prefix}AVG_90")),
            })
    return rows


def parse_opening(records, year, qu):
    rows = []
    for rec in records:
        if rec.get("GUBUN") != "dong":
            continue
        for i in range(3):
            s = f"_{i+1}"
            rows.append({
                "quarter": qtr_offset(year, qu, i),
                "dong_code": rec["CD"], "dong_name": rec["NM"],
                "open_count": safe_float(rec.get(f"OPBIZ_STOR_CO{s}")),
                "close_count": safe_float(rec.get(f"CLSBIZ_STOR_CO{s}")),
                "open_rate": safe_float(rec.get(f"OPBIZ_RT{s}")),
                "close_rate": safe_float(rec.get(f"CLSBIZ_RT{s}")),
            })
    return rows


def parse_population(records, year, qu):
    rows = []
    for rec in records:
        if rec.get("GUBUN") != "dong":
            continue
        for i in range(3):
            s = f"_{i+1}"
            rows.append({
                "quarter": qtr_offset(year, qu, i),
                "dong_code": rec["CD"], "dong_name": rec["NM"],
                "floating_pop": safe_float(rec.get(f"TOT_FLPOP_CO{s}")),
                "building_pop": safe_float(rec.get(f"TOT_BDPOP_CO{s}")),
                "resident_pop_api": safe_float(rec.get(f"TOT_REPOP_CO{s}")),
                "worker_pop": safe_float(rec.get(f"TOT_WRC_POPLTN_CO{s}")),
            })
    return rows


def parse_income(records, year, qu):
    rows = []
    for rec in records:
        if rec.get("GUBUN") != "dong":
            continue
        for i in range(3):
            s = f"_{i+1}"
            income_raw = rec.get(f"INCOME_SCTN_CD{s}", "")
            # "9분위:4,890,362~6,945,811원" → 분위 숫자 추출
            income_level = None
            if income_raw and "분위" in str(income_raw):
                try:
                    income_level = int(str(income_raw).split("분위")[0])
                except ValueError:
                    pass
            rows.append({
                "quarter": qtr_offset(year, qu, i),
                "dong_code": rec["CD"], "dong_name": rec["NM"],
                "income_level": income_level,
                "income_raw": income_raw,
                "household_count": safe_float(rec.get(f"TOT_HSHLD_CO{s}")),
            })
    return rows


def parse_sales(records, year, qu):
    rows = []
    for rec in records:
        if rec.get("GUBUN") != "dong":
            continue
        for i in range(3):
            s = f"_{i+1}"
            rows.append({
                "quarter": qtr_offset(year, qu, i),
                "dong_code": rec["CD"], "dong_name": rec["NM"],
                "golmok_avg_sales": safe_float(rec.get(f"AVG_THSMON_SELNG_AMT{s}")),
            })
    return rows


PARSERS = {
    "store": parse_store,
    "survival": parse_survival,
    "survival2": parse_survival2,
    "operatingPeriod": parse_operating_period,
    "opening": parse_opening,
    "population": parse_population,
    "income": parse_income,
    "sales": parse_sales,
}


def main():
    out_dir = Path(__file__).parent.parent / "data" / "processed"
    all_data = {cat: [] for cat in ENDPOINTS}

    n_ind_cats = len(ENDPOINTS) - len(DONG_ONLY_CATEGORIES)
    total_reqs = (
        len(QUERY_QUARTERS) * len(DONG_ONLY_CATEGORIES)
        + len(QUERY_QUARTERS) * len(IND_CODES) * n_ind_cats
    )
    print(f"총 {total_reqs}개 요청 예정\n")
    req_count = 0

    for year, qu in QUERY_QUARTERS:
        print(f"  {year}Q{qu} 수집 중...")

        # 동 단위 카테고리 (population, income)
        for cat in DONG_ONLY_CATEGORIES:
            records = fetch(cat, year, qu, "all")
            if records:
                all_data[cat].extend(PARSERS[cat](records, year, qu))
            req_count += 1
            time.sleep(0.3)

        # 업종별 카테고리
        for ind_code, ind_name in IND_CODES.items():
            for cat in ENDPOINTS:
                if cat in DONG_ONLY_CATEGORIES:
                    continue
                records = fetch(cat, year, qu, ind_code)
                if records:
                    parsed = PARSERS[cat](records, year, qu)
                    for row in parsed:
                        row["industry_code"] = ind_code
                        row["industry_name"] = ind_name
                    all_data[cat].extend(parsed)
                req_count += 1
                if req_count % 50 == 0:
                    print(f"    {req_count}/{total_reqs} 완료")
                time.sleep(0.3)

    # 저장
    print(f"\n  저장 중...")
    for cat, rows in all_data.items():
        if not rows:
            print(f"  {cat}: 데이터 없음!")
            continue
        df = pd.DataFrame(rows)
        df = df[df["dong_code"].astype(str).str.startswith("11440")]
        dedup_cols = ["quarter", "dong_code"]
        if "industry_code" in df.columns:
            dedup_cols.append("industry_code")
        df = df.drop_duplicates(subset=dedup_cols, keep="first")
        path = out_dir / f"golmok_{cat}.csv"
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"  {cat}: {len(df)} rows → {path.name}")

    # 통합
    print(f"\n  통합 데이터셋 생성 중...")
    merge_all(all_data, out_dir)
    print(f"\n  완료! 총 {req_count}개 요청 처리")


def merge_all(all_data, out_dir):
    ind_cats = [c for c in ENDPOINTS if c not in DONG_ONLY_CATEGORIES]
    merged = None
    for cat in ind_cats:
        if not all_data[cat]:
            continue
        df = pd.DataFrame(all_data[cat])
        df = df[df["dong_code"].astype(str).str.startswith("11440")]
        dedup_cols = ["quarter", "dong_code", "industry_code"]
        df = df.drop_duplicates(subset=dedup_cols, keep="first")
        if merged is None:
            merged = df
        else:
            merge_keys = ["quarter", "dong_code", "industry_code"]
            new_cols = [c for c in df.columns
                        if c not in merged.columns and c not in merge_keys]
            if new_cols:
                merged = merged.merge(
                    df[merge_keys + new_cols], on=merge_keys, how="outer"
                )

    # 동 단위 데이터 병합
    for cat in DONG_ONLY_CATEGORIES:
        if not all_data[cat]:
            continue
        df = pd.DataFrame(all_data[cat])
        df = df[df["dong_code"].astype(str).str.startswith("11440")]
        df = df.drop_duplicates(subset=["quarter", "dong_code"], keep="first")
        if merged is not None:
            merge_keys = ["quarter", "dong_code"]
            new_cols = [c for c in df.columns
                        if c not in merged.columns and c not in merge_keys]
            if new_cols:
                merged = merged.merge(
                    df[merge_keys + new_cols], on=merge_keys, how="left"
                )

    if merged is not None and len(merged) > 0:
        merged = merged.sort_values(["dong_code", "industry_code", "quarter"])
        path = out_dir / "golmok_merged.csv"
        merged.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"  통합: {merged.shape} → {path.name}")
        print(f"  컬럼: {list(merged.columns)}")
        print(f"  분기 범위: {merged['quarter'].min()} ~ {merged['quarter'].max()}")
        print(f"  동 수: {merged['dong_code'].nunique()}")
        print(f"  업종 수: {merged['industry_code'].nunique()}")
    else:
        print("  통합 실패: 데이터 없음")


if __name__ == "__main__":
    main()
