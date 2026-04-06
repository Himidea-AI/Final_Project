"""
ETL pipeline — 41 processed CSV files → PostgreSQL tables

담당: A1 — 데이터 엔지니어 (찬영)

Usage:
    python data/pipeline/load_to_db.py                   # load all tables
    python data/pipeline/load_to_db.py --table living_population
    python data/pipeline/load_to_db.py --db-url postgresql://user:pw@host/db
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Path setup — add backend/src to sys.path so ORM models are importable
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "src"))
from database.models import Base  # noqa: E402

PROC = Path(__file__).resolve().parents[1] / "processed"
DB_URL = "postgresql://postgres:ghdcksdud1@localhost:5432/mapo_simulator"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_csv(filename: str, **kwargs) -> pd.DataFrame:
    """Read a CSV from PROC directory, trying utf-8-sig then utf-8 encoding."""
    path = PROC / filename
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc, **kwargs)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot read {path} with utf-8-sig or utf-8 encoding")


def get_engine(db_url: str = DB_URL):
    """Create a sync SQLAlchemy engine and ensure all ORM tables exist."""
    engine = create_engine(db_url, echo=False)
    Base.metadata.create_all(engine)
    return engine


# ---------------------------------------------------------------------------
# Table 1: living_population
# ---------------------------------------------------------------------------


def load_living_population(engine) -> int:
    """Load living_population_dong_mapo.csv → living_population table."""
    df = _read_csv(
        "living_population_dong_mapo.csv",
        dtype={"ADSTRD_CODE_SE": str},
    )

    # The Korean column names appear in positional order:
    # cols[4..17]  → male age groups  (0-9, 10-14, ..., 65-69, 70+)
    # cols[18..31] → female age groups
    male_cols = list(df.columns[4:18])
    female_cols = list(df.columns[18:32])

    male_targets = [
        "male_0_9",
        "male_10_14",
        "male_15_19",
        "male_20_24",
        "male_25_29",
        "male_30_34",
        "male_35_39",
        "male_40_44",
        "male_45_49",
        "male_50_54",
        "male_55_59",
        "male_60_64",
        "male_65_69",
        "male_70_plus",
    ]
    female_targets = [
        "female_0_9",
        "female_10_14",
        "female_15_19",
        "female_20_24",
        "female_25_29",
        "female_30_34",
        "female_35_39",
        "female_40_44",
        "female_45_49",
        "female_50_54",
        "female_55_59",
        "female_60_64",
        "female_65_69",
        "female_70_plus",
    ]

    rename = {
        "STDR_DE_ID": "date",
        "TMZON_PD_SE": "time_zone",
        "ADSTRD_CODE_SE": "dong_code",
        "TOT_LVPOP_CO": "total_pop",
    }
    rename.update(dict(zip(male_cols, male_targets)))
    rename.update(dict(zip(female_cols, female_targets)))
    df = df.rename(columns=rename)

    # Convert date string YYYYMMDD → date
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d").dt.date

    # Numeric coercion
    numeric_cols = ["total_pop"] + male_targets + female_targets
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop the extra male_70_74 / female_70_74 columns (model has 70_plus not 70_74)
    # The source has 14 age groups (index 4-17 = 14 cols): 0-9,10-14,...,65-69,70+
    # So male_cols has exactly 14 entries → map correctly to male_targets (also 14)

    keep = (
        ["date", "time_zone", "dong_code", "dong_name", "total_pop"]
        + male_targets
        + female_targets
    )
    df = df[[c for c in keep if c in df.columns]]

    df.to_sql(
        "living_population",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5000,
    )
    return len(df)


# ---------------------------------------------------------------------------
# Table 2: sgis_population
# ---------------------------------------------------------------------------


def load_sgis_population(engine) -> int:
    """Load SGIS population files → sgis_population table."""
    frames = []

    # Pure long-format SGIS files (year, area_code, indicator_code, value)
    sgis_files = [
        "sgis_population_total.csv",
        "sgis_population_avg_age.csv",
        "sgis_population_density.csv",
        "sgis_population_aging.csv",
        "sgis_population_age_gender.csv",
    ]
    for fname in sgis_files:
        df = _read_csv(fname, dtype={"area_code": str})
        df = df.rename(columns={"indicator_code": "indicator"})
        frames.append(df[["year", "area_code", "indicator", "value"]])

    # district_resident_pop.csv — wide → long (year, 행정동코드, total_population, area_count, 행정동명)
    df_rp = _read_csv("district_resident_pop.csv", dtype={"행정동코드": str})
    df_rp = df_rp.rename(columns={"행정동코드": "area_code"})
    for col in ["total_population", "area_count"]:
        if col in df_rp.columns:
            tmp = df_rp[["year", "area_code", col]].copy()
            tmp = tmp.rename(columns={col: "value"})
            tmp["indicator"] = col
            frames.append(tmp[["year", "area_code", "indicator", "value"]])

    # district_avg_age.csv
    df_aa = _read_csv("district_avg_age.csv", dtype={"행정동코드": str})
    df_aa = df_aa.rename(columns={"행정동코드": "area_code"})
    tmp = df_aa[["year", "area_code", "avg_age"]].copy()
    tmp = tmp.rename(columns={"avg_age": "value"})
    tmp["indicator"] = "avg_age"
    frames.append(tmp[["year", "area_code", "indicator", "value"]])

    # district_demographics.csv — dong_code, dong_name, avg_age, total_households
    # Use a dummy year (0) since no year column
    df_dem = _read_csv("district_demographics.csv", dtype={"dong_code": str})
    for col in ["avg_age", "total_households"]:
        if col in df_dem.columns:
            tmp = df_dem[["dong_code", col]].copy()
            tmp = tmp.rename(columns={"dong_code": "area_code", col: "value"})
            tmp["year"] = 0
            tmp["indicator"] = f"dem_{col}"
            frames.append(tmp[["year", "area_code", "indicator", "value"]])

    combined = pd.concat(frames, ignore_index=True)
    combined["year"] = pd.to_numeric(combined["year"], errors="coerce").astype("Int64")
    combined["value"] = pd.to_numeric(combined["value"], errors="coerce")
    combined = combined.drop_duplicates(subset=["year", "area_code", "indicator"])

    combined.to_sql(
        "sgis_population",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5000,
    )
    return len(combined)


# ---------------------------------------------------------------------------
# Table 3: sgis_household
# ---------------------------------------------------------------------------


def load_sgis_household(engine) -> int:
    """Load SGIS household files → sgis_household table."""
    frames = []

    for fname in ["sgis_household_total.csv", "sgis_household_composition.csv"]:
        df = _read_csv(fname, dtype={"area_code": str})
        df = df.rename(columns={"indicator_code": "indicator"})
        frames.append(df[["year", "area_code", "indicator", "value"]])

    # district_households.csv
    df_hh = _read_csv("district_households.csv", dtype={"행정동코드": str})
    df_hh = df_hh.rename(columns={"행정동코드": "area_code"})
    tmp = df_hh[["year", "area_code", "total_households"]].copy()
    tmp = tmp.rename(columns={"total_households": "value"})
    tmp["indicator"] = "total_households"
    frames.append(tmp[["year", "area_code", "indicator", "value"]])

    combined = pd.concat(frames, ignore_index=True)
    combined["year"] = pd.to_numeric(combined["year"], errors="coerce").astype("Int64")
    combined["value"] = pd.to_numeric(combined["value"], errors="coerce")
    combined = combined.drop_duplicates(subset=["year", "area_code", "indicator"])

    combined.to_sql(
        "sgis_household",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5000,
    )
    return len(combined)


# ---------------------------------------------------------------------------
# Table 4: sgis_business
# ---------------------------------------------------------------------------


def load_sgis_business(engine) -> int:
    """Load SGIS business files → sgis_business table."""
    frames = []

    for fname in [
        "sgis_business_major_count.csv",
        "sgis_business_major_workers.csv",
        "sgis_business_mid_count.csv",
        "sgis_business_mid_workers.csv",
    ]:
        df = _read_csv(fname, dtype={"area_code": str})
        df = df.rename(columns={"indicator_code": "indicator"})
        frames.append(df[["year", "area_code", "indicator", "value"]])

    combined = pd.concat(frames, ignore_index=True)
    combined["year"] = pd.to_numeric(combined["year"], errors="coerce").astype("Int64")
    combined["value"] = pd.to_numeric(combined["value"], errors="coerce")
    combined = combined.drop_duplicates(subset=["year", "area_code", "indicator"])

    combined.to_sql(
        "sgis_business",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5000,
    )
    return len(combined)


# ---------------------------------------------------------------------------
# Table 5: golmok_commercial
# ---------------------------------------------------------------------------


def _golmok_to_rows(df: pd.DataFrame, data_type: str) -> pd.DataFrame:
    """Convert a golmok CSV dataframe to the golmok_commercial schema."""
    # Identify the quarter column (contains YYQU pattern or is STDR_YYQU_CD)
    quarter_col = "STDR_YYQU_CD"
    trdar_col = "TRDAR_CD"
    industry_col = "SVC_INDUTY_CD"

    # Columns that go into metrics (everything except the key columns)
    key_cols = {
        quarter_col,
        trdar_col,
        industry_col,
        "TRDAR_SE_CD",
        "TRDAR_SE_CD_NM",
        "TRDAR_CD_NM",
        "SVC_INDUTY_CD_NM",
    }
    metric_cols = [c for c in df.columns if c not in key_cols]

    rows = []
    for _, row in df.iterrows():
        quarter_val = row.get(quarter_col)
        trdar_code = (
            str(row.get(trdar_col, "")) if pd.notna(row.get(trdar_col)) else None
        )
        industry_code = (
            str(row.get(industry_col, "ALL"))
            if pd.notna(row.get(industry_col, "ALL"))
            else "ALL"
        )
        metrics = {
            col: (None if pd.isna(row[col]) else row[col]) for col in metric_cols
        }
        rows.append(
            {
                "quarter": quarter_val,
                "trdar_code": trdar_code,
                "data_type": data_type,
                "industry_code": industry_code,
                "metrics": json.dumps(metrics, ensure_ascii=False, default=str),
            }
        )
    return pd.DataFrame(rows)


def load_golmok_commercial(engine) -> int:
    """Load golmok_* and commercial_change CSV files → golmok_commercial table."""
    file_type_map = {
        "golmok_sales_mapo.csv": "sales",
        "golmok_stores_mapo.csv": "stores",
        "golmok_floating_pop_mapo.csv": "floating_pop",
        "golmok_worker_pop_mapo.csv": "worker_pop",
        "golmok_index_mapo.csv": "index",
        "commercial_change_mapo.csv": "change",
    }

    frames = []
    for fname, dtype in file_type_map.items():
        df = _read_csv(fname)

        # commercial_change_mapo.csv has different column structure
        if fname == "commercial_change_mapo.csv":
            # Columns: 기준_년분기_코드, 행정동_코드, 행정동_코드_명, 상권_변화_지표, ...
            df = df.rename(
                columns={
                    "기준_년분기_코드": "STDR_YYQU_CD",
                    "행정동_코드": "TRDAR_CD",
                }
            )
            if "SVC_INDUTY_CD" not in df.columns:
                df["SVC_INDUTY_CD"] = "ALL"

        frames.append(_golmok_to_rows(df, dtype))

    combined = pd.concat(frames, ignore_index=True)
    combined["quarter"] = pd.to_numeric(combined["quarter"], errors="coerce").astype(
        "Int64"
    )

    combined.to_sql(
        "golmok_commercial",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5000,
    )
    return len(combined)


# ---------------------------------------------------------------------------
# Table 6: district_sales
# ---------------------------------------------------------------------------


def load_district_sales(engine) -> int:
    """Load district_sales.csv → district_sales table."""
    df = _read_csv("district_sales.csv", dtype={"행정동코드": str})

    rename = {
        "STDR_YYQU_CD": "quarter",
        "행정동코드": "dong_code",
        "행정동명": "dong_name",
        "SVC_INDUTY_CD": "industry_code",
        "SVC_INDUTY_CD_NM": "industry_name",
        "THSMON_SELNG_AMT": "monthly_sales",
        "THSMON_SELNG_CO": "monthly_count",
        "MDWK_SELNG_AMT": "weekday_sales",
        "WKEND_SELNG_AMT": "weekend_sales",
        "MON_SELNG_AMT": "mon_sales",
        "TUES_SELNG_AMT": "tue_sales",
        "WED_SELNG_AMT": "wed_sales",
        "THUR_SELNG_AMT": "thu_sales",
        "FRI_SELNG_AMT": "fri_sales",
        "SAT_SELNG_AMT": "sat_sales",
        "SUN_SELNG_AMT": "sun_sales",
        "TMZON_00_06_SELNG_AMT": "time_00_06_sales",
        "TMZON_06_11_SELNG_AMT": "time_06_11_sales",
        "TMZON_11_14_SELNG_AMT": "time_11_14_sales",
        "TMZON_14_17_SELNG_AMT": "time_14_17_sales",
        "TMZON_17_21_SELNG_AMT": "time_17_21_sales",
        "TMZON_21_24_SELNG_AMT": "time_21_24_sales",
        "ML_SELNG_AMT": "male_sales",
        "FML_SELNG_AMT": "female_sales",
        "AGRDE_10_SELNG_AMT": "age_10_sales",
        "AGRDE_20_SELNG_AMT": "age_20_sales",
        "AGRDE_30_SELNG_AMT": "age_30_sales",
        "AGRDE_40_SELNG_AMT": "age_40_sales",
        "AGRDE_50_SELNG_AMT": "age_50_sales",
        "AGRDE_60_ABOVE_SELNG_AMT": "age_60_above_sales",
        "MDWK_SELNG_CO": "weekday_count",
        "WKEND_SELNG_CO": "weekend_count",
        "MON_SELNG_CO": "mon_count",
        "TUES_SELNG_CO": "tue_count",
        "WED_SELNG_CO": "wed_count",
        "THUR_SELNG_CO": "thu_count",
        "FRI_SELNG_CO": "fri_count",
        "SAT_SELNG_CO": "sat_count",
        "SUN_SELNG_CO": "sun_count",
        "TMZON_00_06_SELNG_CO": "time_00_06_count",
        "TMZON_06_11_SELNG_CO": "time_06_11_count",
        "TMZON_11_14_SELNG_CO": "time_11_14_count",
        "TMZON_14_17_SELNG_CO": "time_14_17_count",
        "TMZON_17_21_SELNG_CO": "time_17_21_count",
        "TMZON_21_24_SELNG_CO": "time_21_24_count",
        "ML_SELNG_CO": "male_count",
        "FML_SELNG_CO": "female_count",
        "AGRDE_10_SELNG_CO": "age_10_count",
        "AGRDE_20_SELNG_CO": "age_20_count",
        "AGRDE_30_SELNG_CO": "age_30_count",
        "AGRDE_40_SELNG_CO": "age_40_count",
        "AGRDE_50_SELNG_CO": "age_50_count",
        "AGRDE_60_ABOVE_SELNG_CO": "age_60_above_count",
    }
    df = df.rename(columns=rename)

    # Numeric columns
    int_cols = [
        "monthly_sales",
        "monthly_count",
        "weekday_sales",
        "weekend_sales",
        "mon_sales",
        "tue_sales",
        "wed_sales",
        "thu_sales",
        "fri_sales",
        "sat_sales",
        "sun_sales",
        "time_00_06_sales",
        "time_06_11_sales",
        "time_11_14_sales",
        "time_14_17_sales",
        "time_17_21_sales",
        "time_21_24_sales",
        "male_sales",
        "female_sales",
        "age_10_sales",
        "age_20_sales",
        "age_30_sales",
        "age_40_sales",
        "age_50_sales",
        "age_60_above_sales",
        "weekday_count",
        "weekend_count",
        "mon_count",
        "tue_count",
        "wed_count",
        "thu_count",
        "fri_count",
        "sat_count",
        "sun_count",
        "time_00_06_count",
        "time_06_11_count",
        "time_11_14_count",
        "time_14_17_count",
        "time_17_21_count",
        "time_21_24_count",
        "male_count",
        "female_count",
        "age_10_count",
        "age_20_count",
        "age_30_count",
        "age_40_count",
        "age_50_count",
        "age_60_above_count",
    ]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    df["quarter"] = pd.to_numeric(df["quarter"], errors="coerce").astype("Int64")

    df.to_sql(
        "district_sales",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5000,
    )
    return len(df)


# ---------------------------------------------------------------------------
# Table 7: store_info
# ---------------------------------------------------------------------------


def load_store_info(engine) -> int:
    """Load store_info_mapo.csv → store_info table."""
    df = _read_csv(
        "store_info_mapo.csv",
        dtype={"행정동코드": str, "법정동코드": str, "상가업소번호": str},
    )

    rename = {
        "상가업소번호": "store_id",
        "상호명": "store_name",
        "상권업종대분류코드": "industry_l_code",
        "상권업종대분류명": "industry_l",
        "상권업종중분류코드": "industry_m_code",
        "상권업종중분류명": "industry_m",
        "상권업종소분류코드": "industry_s_code",
        "상권업종소분류명": "industry_s",
        "행정동코드": "dong_code",
        "행정동명": "dong_name",
        "지번주소": "address",
        "도로명주소": "road_address",
        "건물명": "building_name",
        "층정보": "floor_info",
        "경도": "lon",
        "위도": "lat",
    }
    df = df.rename(columns=rename)

    for col in ["lat", "lon"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    keep = [
        "store_id",
        "store_name",
        "dong_code",
        "dong_name",
        "address",
        "road_address",
        "lat",
        "lon",
        "industry_l_code",
        "industry_l",
        "industry_m_code",
        "industry_m",
        "industry_s_code",
        "industry_s",
        "building_name",
        "floor_info",
    ]
    df = df[[c for c in keep if c in df.columns]]

    df.to_sql(
        "store_info",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5000,
    )
    return len(df)


# ---------------------------------------------------------------------------
# Table 8: store_quarterly
# ---------------------------------------------------------------------------


def load_store_quarterly(engine) -> int:
    """Load district_stores.csv → store_quarterly table."""
    df = _read_csv("district_stores.csv", dtype={"행정동코드": str})

    rename = {
        "STDR_YYQU_CD": "quarter",
        "행정동코드": "dong_code",
        "행정동명": "dong_name",
        "SVC_INDUTY_CD": "industry_code",
        "SVC_INDUTY_CD_NM": "industry_name",
        "STOR_CO": "store_count",
        "OPBIZ_STOR_CO": "open_count",
        "CLSBIZ_STOR_CO": "close_count",
        "CLSBIZ_RT": "closure_rate",
        "FRC_STOR_CO": "franchise_count",
    }
    df = df.rename(columns=rename)

    for col in ["store_count", "open_count", "close_count", "franchise_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    if "closure_rate" in df.columns:
        df["closure_rate"] = pd.to_numeric(df["closure_rate"], errors="coerce")

    df["quarter"] = pd.to_numeric(df["quarter"], errors="coerce").astype("Int64")

    keep = [
        "quarter",
        "dong_code",
        "dong_name",
        "industry_code",
        "industry_name",
        "store_count",
        "open_count",
        "close_count",
        "closure_rate",
        "franchise_count",
    ]
    df = df[[c for c in keep if c in df.columns]]

    df.to_sql(
        "store_quarterly",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5000,
    )
    return len(df)


# ---------------------------------------------------------------------------
# Table 9: rent_cost
# ---------------------------------------------------------------------------


def load_rent_cost(engine) -> int:
    """Load rent_building_mapo.csv + commercial_trade_mapo.csv → rent_cost table."""
    frames = []

    # rent_building_mapo.csv — area_name, year, quarter, rent, vacancy_rate, etc.
    df_rent = _read_csv("rent_building_mapo.csv")
    df_rent["data_type"] = df_rent.get(
        "source", pd.Series(["building_rent"] * len(df_rent))
    )
    df_rent = df_rent.rename(columns={"source": "source"})

    for col in [
        "rent",
        "vacancy_rate",
        "investment_return",
        "income_return",
        "capital_return",
    ]:
        if col in df_rent.columns:
            df_rent[col] = pd.to_numeric(df_rent[col], errors="coerce")
    for col in ["year", "quarter"]:
        if col in df_rent.columns:
            df_rent[col] = pd.to_numeric(df_rent[col], errors="coerce").astype("Int64")

    keep_rent = [
        "data_type",
        "area_name",
        "year",
        "quarter",
        "rent",
        "vacancy_rate",
        "investment_return",
        "income_return",
        "capital_return",
        "source",
    ]
    frames.append(df_rent[[c for c in keep_rent if c in df_rent.columns]])

    # commercial_trade_mapo.csv
    df_trade = _read_csv("commercial_trade_mapo.csv", dtype=str)

    # Map columns
    df_trade = df_trade.rename(
        columns={
            "시군구": "area_name",
            "계약년월": "transaction_date",
            "거래금액(만원)": "price_raw",
            "전용/연면적(㎡)": "floor_area",
            "층": "floor",
            "도로명": "road_name",
        }
    )

    df_trade["data_type"] = "trade"
    df_trade["source"] = "molit_trade"

    # Clean price — remove commas and convert
    if "price_raw" in df_trade.columns:
        df_trade["price"] = pd.to_numeric(
            df_trade["price_raw"].str.replace(",", "", regex=False), errors="coerce"
        ).astype("Int64")
    if "floor_area" in df_trade.columns:
        df_trade["floor_area"] = pd.to_numeric(df_trade["floor_area"], errors="coerce")

    # Parse transaction_date YYYYMM → YYYY-MM
    if "transaction_date" in df_trade.columns:
        df_trade["transaction_date"] = df_trade["transaction_date"].apply(
            lambda x: f"{x[:4]}-{x[4:6]}" if pd.notna(x) and len(str(x)) >= 6 else None
        )

    # Extract year and quarter from transaction_date
    if "transaction_date" in df_trade.columns:
        df_trade["year"] = df_trade["transaction_date"].apply(
            lambda x: (
                int(x[:4])
                if pd.notna(x) and isinstance(x, str) and len(x) >= 4
                else None
            )
        )
        df_trade["year"] = pd.array(df_trade["year"], dtype="Int64")

    keep_trade = [
        "data_type",
        "area_name",
        "year",
        "price",
        "floor_area",
        "floor",
        "transaction_date",
        "source",
    ]
    frames.append(df_trade[[c for c in keep_trade if c in df_trade.columns]])

    combined = pd.concat(frames, ignore_index=True)
    combined.to_sql(
        "rent_cost",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=5000,
    )
    return len(combined)


# ---------------------------------------------------------------------------
# Table 10: dong_mapping
# ---------------------------------------------------------------------------


def load_dong_mapping(engine) -> int:
    """Build dong_mapping table from district_population, trdar_dong_mapping, district_demographics."""
    # Base: district_population (has dong_code, dong_name, floating_pop, resident_pop)
    df_pop = _read_csv("district_population.csv", dtype={"dong_code": str})
    df_pop = df_pop[["dong_code", "dong_name", "floating_pop", "resident_pop"]].copy()
    df_pop["floating_pop"] = pd.to_numeric(df_pop["floating_pop"], errors="coerce")
    df_pop["resident_pop"] = pd.to_numeric(
        df_pop["resident_pop"], errors="coerce"
    ).astype("Int64")

    # trdar_dong_mapping — group by dong_name (행정동명), collect TRDAR_CD list
    df_trdar = _read_csv(
        "trdar_dong_mapping.csv", dtype={"TRDAR_CD": str, "행정동코드": str}
    )
    df_trdar = df_trdar.rename(
        columns={"행정동코드": "dong_code", "행정동명": "dong_name_trdar"}
    )
    trdar_groups = (
        df_trdar.groupby("dong_code")["TRDAR_CD"]
        .apply(
            lambda x: json.dumps(
                sorted(x.dropna().unique().tolist()), ensure_ascii=False
            )
        )
        .reset_index()
        .rename(columns={"TRDAR_CD": "trdar_codes"})
    )

    # district_demographics — avg_age, total_households
    df_dem = _read_csv("district_demographics.csv", dtype={"dong_code": str})
    df_dem = df_dem[["dong_code", "avg_age", "total_households"]].copy()
    df_dem["avg_age"] = pd.to_numeric(df_dem["avg_age"], errors="coerce")
    df_dem["total_households"] = pd.to_numeric(
        df_dem["total_households"], errors="coerce"
    )
    df_dem["total_households"] = df_dem["total_households"].where(
        df_dem["total_households"].notna(), None
    )

    # Merge all together
    result = df_pop.merge(trdar_groups, on="dong_code", how="left")
    result = result.merge(df_dem, on="dong_code", how="left")

    keep = [
        "dong_code",
        "dong_name",
        "resident_pop",
        "floating_pop",
        "avg_age",
        "total_households",
        "trdar_codes",
    ]
    result = result[[c for c in keep if c in result.columns]]

    result.to_sql(
        "dong_mapping",
        engine,
        if_exists="replace",
        index=False,
        method="multi",
        chunksize=1000,
    )
    return len(result)


# ---------------------------------------------------------------------------
# LOADERS registry
# ---------------------------------------------------------------------------

LOADERS: dict = {
    "living_population": load_living_population,
    "sgis_population": load_sgis_population,
    "sgis_household": load_sgis_household,
    "sgis_business": load_sgis_business,
    "golmok_commercial": load_golmok_commercial,
    "district_sales": load_district_sales,
    "store_info": load_store_info,
    "store_quarterly": load_store_quarterly,
    "rent_cost": load_rent_cost,
    "dong_mapping": load_dong_mapping,
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load processed CSV files into PostgreSQL"
    )
    parser.add_argument("--table", type=str, help="Load a specific table only")
    parser.add_argument("--db-url", default=DB_URL, help="PostgreSQL connection URL")
    args = parser.parse_args()

    engine = get_engine(args.db_url)

    if args.table:
        if args.table not in LOADERS:
            print(f"Unknown table '{args.table}'. Available: {', '.join(LOADERS)}")
            sys.exit(1)
        tables_to_load = {args.table: LOADERS[args.table]}
    else:
        tables_to_load = LOADERS

    total = len(tables_to_load)
    for i, (name, loader) in enumerate(tables_to_load.items(), 1):
        print(f"[{i}/{total}] {name}...")
        try:
            n = loader(engine)
            print(f"  -> {n:,} rows loaded")
        except Exception as exc:
            print(f"  -> ERROR: {exc}")
            raise

    print("\nRow counts:")
    with engine.connect() as conn:
        for table in LOADERS:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))  # noqa: S608
                print(f"  {table}: {result.scalar():,} rows")
            except Exception:
                print(f"  {table}: (not found)")

    engine.dispose()


if __name__ == "__main__":
    main()
