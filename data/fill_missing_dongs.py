"""누락 동(망원2동/성산2동) district 파일 보강 스크립트."""

import numpy as np
import pandas as pd

DONG_MAP = {
    "11440555": "대흥동", "11440565": "염리동", "11440585": "용강동",
    "11440590": "서강동", "11440600": "서교동", "11440610": "합정동",
    "11440630": "망원1동", "11440655": "신수동", "11440660": "망원2동",
    "11440680": "아현동", "11440690": "공덕동", "11440700": "도화동",
    "11440710": "성산1동", "11440720": "성산2동", "11440730": "연남동",
    "11440740": "상암동",
}
NAME_TO_CODE = {v: k for k, v in DONG_MAP.items()}
MISSING = ["망원2동", "성산2동"]
PROC = "processed"


def load_living_pop():
    lp = pd.read_csv(f"{PROC}/living_population_dong_mapo.csv", dtype=str)
    lp_daily = lp[lp["TMZON_PD_SE"] == "00"].copy()
    num_cols = [c for c in lp_daily.columns if "LVPOP" in c or "생활인구" in c]
    for c in num_cols:
        lp_daily[c] = pd.to_numeric(lp_daily[c], errors="coerce")
    lp_daily["year"] = lp_daily["STDR_DE_ID"].str[:4].astype(int)
    lp_daily["month"] = lp_daily["STDR_DE_ID"].str[4:6].astype(int)
    lp_daily["STDR_YYQU_CD"] = lp_daily["year"] * 10 + ((lp_daily["month"] - 1) // 3 + 1)

    tot_col = "TOT_LVPOP_CO" if "TOT_LVPOP_CO" in lp_daily.columns else "총생활인구수"
    male_cols = [c for c in lp_daily.columns if "남자" in c or "MALE" in c]
    female_cols = [c for c in lp_daily.columns if "여자" in c or "FEMALE" in c]
    return lp_daily, tot_col, male_cols, female_cols


def fix_district_population(lp_daily, tot_col, male_cols, female_cols):
    print("=== 1. district_population.csv ===")
    dp = pd.read_csv(f"{PROC}/district_population.csv", dtype={"dong_code": str})
    drp = pd.read_csv(f"{PROC}/district_resident_pop.csv")

    for dong in MISSING:
        if dong in dp["dong_name"].values:
            continue
        code = NAME_TO_CODE[dong]
        d = lp_daily[lp_daily["ADSTRD_CODE_SE"] == code]
        res = drp[(drp["행정동명"] == dong) & (drp["year"] == 2024)]["total_population"].values
        new_row = {
            "dong_code": code, "dong_name": dong,
            "floating_pop": round(d[tot_col].mean(), 1),
            "floating_male": round(d[male_cols].mean().sum(), 1),
            "floating_female": round(d[female_cols].mean().sum(), 1),
            "worker_pop": np.nan,
            "resident_pop": res[0] if len(res) > 0 else np.nan,
        }
        dp = pd.concat([dp, pd.DataFrame([new_row])], ignore_index=True)

    dp.sort_values("dong_name").reset_index(drop=True).to_csv(
        f"{PROC}/district_population.csv", index=False, encoding="utf-8-sig"
    )
    print(f"  -> {dp['dong_name'].nunique()} dongs")


def fix_district_floating_pop(lp_daily, tot_col, male_cols, female_cols):
    print("=== 2. district_floating_pop.csv ===")
    dfp = pd.read_csv(f"{PROC}/district_floating_pop.csv", dtype={"행정동코드": str})
    quarters = sorted(dfp["STDR_YYQU_CD"].unique())

    new_rows = []
    for dong in MISSING:
        if dong in dfp["행정동명"].values:
            continue
        code = NAME_TO_CODE[dong]
        d = lp_daily[lp_daily["ADSTRD_CODE_SE"] == code]
        for q in quarters:
            qd = d[d["STDR_YYQU_CD"] == q]
            if len(qd) == 0:
                continue
            row = {
                "STDR_YYQU_CD": q, "행정동코드": code, "행정동명": dong,
                "TOT_FLPOP_CO": round(qd[tot_col].mean(), 1),
                "ML_FLPOP_CO": round(qd[male_cols].mean().sum(), 1),
                "FML_FLPOP_CO": round(qd[female_cols].mean().sum(), 1),
            }
            for c in dfp.columns:
                if c not in row:
                    row[c] = np.nan
            new_rows.append(row)

    dfp = pd.concat([dfp, pd.DataFrame(new_rows)], ignore_index=True)
    dfp.sort_values(["행정동명", "STDR_YYQU_CD"]).reset_index(drop=True).to_csv(
        f"{PROC}/district_floating_pop.csv", index=False, encoding="utf-8-sig"
    )
    print(f"  -> {dfp['행정동명'].nunique()} dongs")


def fix_district_worker_pop():
    print("=== 3. district_worker_pop.csv ===")
    dwp = pd.read_csv(f"{PROC}/district_worker_pop.csv", dtype={"행정동코드": str})
    quarters = sorted(dwp["STDR_YYQU_CD"].unique())

    new_rows = []
    for dong in MISSING:
        if dong in dwp["행정동명"].values:
            continue
        code = NAME_TO_CODE[dong]
        for q in quarters:
            row = {"STDR_YYQU_CD": q, "행정동코드": code, "행정동명": dong}
            for c in dwp.columns:
                if c not in row:
                    row[c] = np.nan
            new_rows.append(row)

    dwp = pd.concat([dwp, pd.DataFrame(new_rows)], ignore_index=True)
    dwp.sort_values(["행정동명", "STDR_YYQU_CD"]).reset_index(drop=True).to_csv(
        f"{PROC}/district_worker_pop.csv", index=False, encoding="utf-8-sig"
    )
    print(f"  -> {dwp['행정동명'].nunique()} dongs")


def fix_district_stores():
    print("=== 4. district_stores.csv ===")
    ds = pd.read_csv(f"{PROC}/district_stores.csv", dtype={"행정동코드": str})
    si = pd.read_csv(f"{PROC}/store_info_mapo.csv", low_memory=False)
    latest_q = ds["STDR_YYQU_CD"].max()

    new_rows = []
    for dong in MISSING:
        if dong in ds["행정동명"].values:
            continue
        code = NAME_TO_CODE[dong]
        stores = si[si["행정동명"] == dong]
        if "상권업종중분류명" not in stores.columns:
            continue
        by_ind = stores.groupby("상권업종중분류명").size().reset_index(name="STOR_CO")
        for _, ir in by_ind.iterrows():
            row = {
                "STDR_YYQU_CD": latest_q, "행정동코드": code, "행정동명": dong,
                "SVC_INDUTY_CD": "", "SVC_INDUTY_CD_NM": ir["상권업종중분류명"],
                "STOR_CO": ir["STOR_CO"],
            }
            for c in ds.columns:
                if c not in row:
                    row[c] = np.nan
            new_rows.append(row)

    ds = pd.concat([ds, pd.DataFrame(new_rows)], ignore_index=True)
    ds.sort_values(["행정동명", "STDR_YYQU_CD"]).reset_index(drop=True).to_csv(
        f"{PROC}/district_stores.csv", index=False, encoding="utf-8-sig"
    )
    print(f"  -> {ds['행정동명'].nunique()} dongs")


def fix_district_store_timeseries():
    print("=== 5. district_store_timeseries.csv ===")
    dst = pd.read_csv(f"{PROC}/district_store_timeseries.csv", dtype={"dong_code": str})
    si = pd.read_csv(f"{PROC}/store_info_mapo.csv", low_memory=False)
    latest_q = dst["quarter"].max()

    new_rows = []
    for dong in MISSING:
        if dong in dst["dong_name"].values:
            continue
        code = NAME_TO_CODE[dong]
        total = len(si[si["행정동명"] == dong])
        row = {
            "quarter": latest_q, "dong_code": code, "dong_name": dong,
            "industry_code": "ALL", "industry_name": "전체",
            "store_count": total, "open_count": np.nan, "close_count": np.nan,
        }
        for c in dst.columns:
            if c not in row:
                row[c] = np.nan
        new_rows.append(row)

    dst = pd.concat([dst, pd.DataFrame(new_rows)], ignore_index=True)
    dst.sort_values(["dong_name", "quarter"]).reset_index(drop=True).to_csv(
        f"{PROC}/district_store_timeseries.csv", index=False, encoding="utf-8-sig"
    )
    print(f"  -> {dst['dong_name'].nunique()} dongs")


def main():
    lp_daily, tot_col, male_cols, female_cols = load_living_pop()
    print(f"Living pop: {len(lp_daily)} daily rows, tot_col={tot_col}\n")

    fix_district_population(lp_daily, tot_col, male_cols, female_cols)
    fix_district_floating_pop(lp_daily, tot_col, male_cols, female_cols)
    fix_district_worker_pop()
    fix_district_stores()
    fix_district_store_timeseries()

    # sales/trend는 원본 매출 데이터가 없으므로 추가하지 않음
    print("\n=== 6-7. district_sales/trend_timeseries ===")
    print("  -> Skipped (no sales source for missing dongs)")

    print("\n=== ALL DONE ===")


if __name__ == "__main__":
    main()
