"""B1 데이터 단독 신호 강도 측정.

각 B1 신호 (지하철 승하차 분기 증감, 20-30대 전입률) 의 change_ix transition AUC-ROC 측정.

LSTM AE 와 비교하여 단순 B1 baseline 만으로도 AUC > LSTM 인지 확인.

지하철: seoul_subway_passenger_daily (station_code 단위) → master_subway_station + dong_subway_access
        를 통해 각 동의 nearest_subway 와 매칭 후 분기 합계.
전입: seoul_dong_migration_monthly (move_in_2030, move_out_2030) → 분기 집계.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.metrics import roc_auc_score
from sqlalchemy import create_engine, text

from validation.experiments.emerging_district.change_ix_eval import (
    compute_transition_labels,
    load_change_ix,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "backend" / ".env")

DB_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://postgres:MapoSpotter1!%23@mapo-simulator.cx8eakyuk1jf.ap-northeast-2.rds.amazonaws.com:5432/mapo_simulator",
)


def _engine():
    if DB_URL is None:
        raise RuntimeError("POSTGRES_URL 미설정")
    return create_engine(DB_URL, isolation_level="AUTOCOMMIT")


def load_subway_quarterly(dong_prefix: str | None = None) -> pd.DataFrame:
    """seoul_subway_passenger_daily → 분기 집계.

    station_code → master_subway_station.station_name → dong_subway_access.nearest_subway
    경로로 각 동의 대표 역 (1km 내 가장 가까운 역) 의 boarding+alighting 합계.

    Parameters
    ----------
    dong_prefix : str | None
        None=서울 전체, "11440"=마포구.

    Returns
    -------
    pd.DataFrame
        columns: dong_code, quarter, passenger_count
    """
    engine = _engine()
    sql = """
        WITH dong_station AS (
            SELECT
                dsa.dong_code,
                mss.station_code
            FROM dong_subway_access dsa
            JOIN master_subway_station mss
              ON mss.station_name = SPLIT_PART(dsa.nearest_subway, ' ', 1)
            WHERE (:prefix IS NULL OR dsa.dong_code LIKE :prefix)
              AND dsa.nearest_subway IS NOT NULL
        )
        SELECT
            ds.dong_code,
            (EXTRACT(YEAR FROM s.date)::int * 10
             + EXTRACT(QUARTER FROM s.date)::int) AS quarter,
            SUM(s.boarding_cnt + s.alighting_cnt)::float AS passenger_count
        FROM seoul_subway_passenger_daily s
        JOIN dong_station ds ON ds.station_code = s.station_code
        GROUP BY ds.dong_code, quarter
    """
    prefix = f"{dong_prefix}%" if dong_prefix else None
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn, params={"prefix": prefix})
    if df.empty:
        return df
    df["dong_code"] = df["dong_code"].astype(str)
    df["quarter"] = df["quarter"].astype(int)
    df["passenger_count"] = df["passenger_count"].astype(float)
    return df


def compute_subway_quarterly_growth(df: pd.DataFrame) -> pd.DataFrame:
    """그룹별 quarter-over-quarter 증감률."""
    df = df.sort_values(["dong_code", "quarter"]).copy()
    df["prev"] = df.groupby("dong_code")["passenger_count"].shift(1)
    df["growth"] = (df["passenger_count"] - df["prev"]) / df["prev"].replace(0, np.nan)
    return df


def load_migration_2030(dong_prefix: str | None = None) -> pd.DataFrame:
    """seoul_dong_migration_monthly → 분기 집계 (dong_code, quarter, in_2030_rate).

    실제 컬럼: ym (YYYYMM int), dong_code, move_in_2030, move_out_2030.

    Parameters
    ----------
    dong_prefix : str | None
        None=서울 전체, "11440"=마포구.
    """
    engine = _engine()
    sql = """
        SELECT
            (ym / 100) * 10
            + ((ym % 100 - 1) / 3 + 1) AS quarter,
            dong_code,
            SUM(move_in_2030)::float AS in_2030,
            SUM(move_out_2030)::float AS out_2030
        FROM seoul_dong_migration_monthly
        WHERE (:prefix IS NULL OR dong_code LIKE :prefix)
        GROUP BY quarter, dong_code
    """
    prefix = f"{dong_prefix}%" if dong_prefix else None
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn, params={"prefix": prefix})
    if df.empty:
        return df
    df["dong_code"] = df["dong_code"].astype(str)
    df["quarter"] = df["quarter"].astype(int)
    df["in_2030_rate"] = (df["in_2030"] - df["out_2030"]) / df["in_2030"].replace(0, np.nan)
    return df


def evaluate_b1_auc(dong_prefix: str | None = None) -> dict:
    """각 B1 신호의 change_ix AUC.

    Parameters
    ----------
    dong_prefix : str | None
        None=서울 전체, "11440"=마포구.

    Returns
    -------
    dict
        AUC_subway_growth, AUC_migration_2030, n_emerging, n_declining 등.
    """
    # change_ix labels — load_change_ix 는 dong_prefix str (None 전달은 안됨), 서울 전체는 빈 prefix 처리
    if dong_prefix is None:
        # 서울 전체: dong_prefix='' 로 전달 → '%' 매칭
        change_df = load_change_ix(dong_prefix="")
    else:
        change_df = load_change_ix(dong_prefix=dong_prefix)
    labels = compute_transition_labels(change_df)

    out: dict = {
        "scope": "seoul" if dong_prefix is None else dong_prefix,
        "n_total_label_rows": int(len(labels)),
        "n_emerging": int(labels["is_emerging"].sum()),
        "n_declining": int(labels["is_declining"].sum()),
        "n_anomaly": int(labels["is_anomaly"].sum()),
    }

    # 지하철
    try:
        sub_raw = load_subway_quarterly(dong_prefix)
        if sub_raw.empty:
            logger.warning("subway 데이터 없음 (prefix=%s)", dong_prefix)
        else:
            sub = compute_subway_quarterly_growth(sub_raw)
            merged_sub = labels.merge(
                sub[["dong_code", "quarter", "growth"]],
                on=["dong_code", "quarter"],
                how="inner",
            )
            merged_sub = merged_sub.dropna(subset=["growth"])
            out["n_subway_merged"] = int(len(merged_sub))
            n_emerg_sub = int(merged_sub["is_emerging"].sum())
            n_decl_sub = int(merged_sub["is_declining"].sum())
            n_anom_sub = int(merged_sub["is_anomaly"].sum())
            out["n_subway_emerging"] = n_emerg_sub
            out["n_subway_declining"] = n_decl_sub
            if len(merged_sub) > 0 and 0 < n_anom_sub < len(merged_sub):
                out["AUC_subway_growth"] = float(roc_auc_score(merged_sub["is_anomaly"], merged_sub["growth"]))
            if len(merged_sub) > 0 and 0 < n_emerg_sub < len(merged_sub):
                out["AUC_subway_growth_emerging"] = float(
                    roc_auc_score(merged_sub["is_emerging"], merged_sub["growth"])
                )
            if len(merged_sub) > 0 and 0 < n_decl_sub < len(merged_sub):
                # decline 은 음의 성장이 더 강한 신호 → -growth 로 부호 뒤집어 AUC 계산
                out["AUC_subway_growth_declining"] = float(
                    roc_auc_score(merged_sub["is_declining"], -merged_sub["growth"])
                )
    except Exception as e:
        logger.warning("subway growth 측정 실패 (prefix=%s): %s", dong_prefix, e)

    # 20-30대 전입
    try:
        mig = load_migration_2030(dong_prefix)
        if mig.empty:
            logger.warning("migration 데이터 없음 (prefix=%s)", dong_prefix)
            out["n_migration_merged"] = 0
        else:
            merged_mig = labels.merge(
                mig[["dong_code", "quarter", "in_2030_rate"]],
                on=["dong_code", "quarter"],
                how="inner",
            )
            merged_mig = merged_mig.dropna(subset=["in_2030_rate"])
            out["n_migration_merged"] = int(len(merged_mig))
            n_emerg_mig = int(merged_mig["is_emerging"].sum())
            n_decl_mig = int(merged_mig["is_declining"].sum())
            n_anom_mig = int(merged_mig["is_anomaly"].sum())
            out["n_migration_emerging"] = n_emerg_mig
            out["n_migration_declining"] = n_decl_mig
            if len(merged_mig) > 0 and 0 < n_anom_mig < len(merged_mig):
                out["AUC_migration_2030"] = float(roc_auc_score(merged_mig["is_anomaly"], merged_mig["in_2030_rate"]))
            if len(merged_mig) > 0 and 0 < n_emerg_mig < len(merged_mig):
                out["AUC_migration_2030_emerging"] = float(
                    roc_auc_score(merged_mig["is_emerging"], merged_mig["in_2030_rate"])
                )
            if len(merged_mig) > 0 and 0 < n_decl_mig < len(merged_mig):
                out["AUC_migration_2030_declining"] = float(
                    roc_auc_score(merged_mig["is_declining"], -merged_mig["in_2030_rate"])
                )
    except Exception as e:
        logger.warning("migration 측정 실패 (prefix=%s): %s", dong_prefix, e)

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="B1 단독 신호 AUC 측정")
    parser.add_argument(
        "--dong-prefix",
        type=str,
        default=None,
        help='None=서울 전체, "11440"=마포구',
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    result = evaluate_b1_auc(dong_prefix=args.dong_prefix)
    scope = "서울 전체" if args.dong_prefix is None else f"prefix={args.dong_prefix}"
    print(f"\n=== B1 단독 신호 AUC vs change_ix transition ({scope}) ===")
    for k, v in result.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.4f}")
        else:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
