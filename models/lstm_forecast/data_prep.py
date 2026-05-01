"""
LSTM 시계열 데이터 전처리 -- 분기별 매출 시계열 생성

DB(PostgreSQL) 또는 CSV에서 분기별 매출/점포 데이터를 로드하여
(동코드 x 업종코드) 그룹별 시계열 시퀀스를 생성한다.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from dotenv import load_dotenv
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 프로세스 단위 DB 데이터 캐시 (TTL 5분)
# ---------------------------------------------------------------------------
_DATA_CACHE: dict = {}
_CACHE_TTL: int = 300  # seconds

# ---------------------------------------------------------------------------
# 기본 경로 / DB 접속 정보
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "processed"

# backend/.env 로드 (POSTGRES_URL 등) — 환경변수 미설정 시 RDS URL 사용
load_dotenv(PROJECT_ROOT / "backend" / ".env")

DB_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql://postgres:MapoSpotter1!%23@mapo-simulator.cx8eakyuk1jf.ap-northeast-2.rds.amazonaws.com:5432/mapo_simulator",
)

# 피처 컬럼 (district_sales 테이블 기준)
SALES_FEATURES = [
    "monthly_sales",
    "monthly_count",
    "weekday_sales",
    "weekend_sales",
    "male_sales",
    "female_sales",
    "age_10_sales",
    "age_20_sales",
    "age_30_sales",
    "age_40_sales",
    "age_50_sales",
    "age_60_above_sales",
]

STORE_FEATURES = [
    "store_count",
    "franchise_count",
    "open_count",
    "close_count",
    "closure_rate",
]

POP_FEATURES = [
    "total_pop",
    "avg_age",
    "total_households",
    "resident_pop",  # 주민등록 주거인구 (마포구 분기별)
]

RENT_FEATURES = [
    "rent_1f",
    "vacancy_rate",
]

EXTRA_FEATURES = [
    "cpi_index",
    "quarter_num",  # 계절성 피처 (1~4)
    "trend_score",  # 네이버 검색 트렌드 (서울 전체)
    "holiday_count",  # 분기 내 공휴일 수 (holiday_calendar)
    "bus_flpop",  # 동별 분기 버스 승하차 집계 (bus_boarding_daily)
    "adstrd_flpop",  # 행정동 분기 유동인구 (seoul_adstrd_flpop.total_flpop — 서울 전체 동 커버)
    "opr_sale_mt_avg",  # 동 단위 월평균 개업 수 (seoul_adstrd_change_ix)
    "cls_sale_mt_avg",  # 동 단위 월평균 폐업 수 (seoul_adstrd_change_ix)
    "industry_trend",  # 업종별 네이버 검색 트렌드 (naver_trend_industry)
]

GOLMOK_FEATURES = [
    "store_franchise",  # 골목상권 프랜차이즈 점포 수
    "store_normal",  # 골목상권 일반 점포 수
    "floating_pop",  # 골목상권 유동인구
    "pop_per_store_gm",  # 골목상권 점포당 유동인구 (파생)
    "normal_ratio",  # 일반 점포 비율 (store_normal / store_total)
]

ALL_FEATURES = SALES_FEATURES + STORE_FEATURES + POP_FEATURES + RENT_FEATURES + EXTRA_FEATURES + GOLMOK_FEATURES

# 극단적 MAPE 이상치 조합 제외 (MAPE 900%+ — 매출 규모 대비 예측 불가)
EXCLUDE_COMBOS: set[tuple[str, str]] = {
    ("11440610", "CS100002"),  # 염리동 중식
    ("11440720", "CS100005"),  # 성산1동 제과
}


class ExcludedComboError(Exception):
    """학습 데이터 부족으로 예측을 제공하지 않는 동×업종 조합.

    EXCLUDE_COMBOS에 등록된 조합에 대해 모델 predict() 진입 시 raise된다.
    interface.py에서 re-raise → B1(graph.py/main.py)에서 HTTP 400 변환 예정.
    ValueError를 상속하지 않으므로 기존 except ValueError 블록에 잡히지 않는다.
    """


# ---------------------------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------------------------


def _load_from_db(
    query: str,
    db_url: str = DB_URL,
) -> pd.DataFrame:
    """DB에서 SQL 쿼리를 실행하여 DataFrame을 반환한다."""
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url, echo=False)
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(query), conn)
    finally:
        engine.dispose()


def load_sales_data(
    db_url: str = DB_URL,
    csv_path: str | Path | None = None,
    dong_prefix: str | None = None,
    sales_csv_override: str | Path | None = None,
) -> pd.DataFrame:
    """district_sales 데이터를 로드한다.

    Parameters
    ----------
    db_url : str
        PostgreSQL 접속 URL.
    csv_path : str or Path, optional
        CSV 파일 경로 (DB 접속 불가 시 fallback).
    dong_prefix : str, optional
        행정동 코드 접두사 필터 (예: '11440' = 마포구).
    sales_csv_override : str or Path, optional
        지정 시 DB를 무시하고 이 CSV를 우선 로드 (imputation 비교 학습용).

    Returns
    -------
    pd.DataFrame
        분기별 매출 데이터.
    """
    df = None

    # 0) sales_csv_override 우선 — DB 시도 자체를 skip
    if sales_csv_override is not None:
        ov_path = Path(sales_csv_override)
        if not ov_path.exists():
            raise FileNotFoundError(f"sales_csv_override CSV가 존재하지 않습니다: {ov_path}")
        df = pd.read_csv(ov_path, dtype={"dong_code": str})
        logger.info("sales_csv_override 로드: %s (%d rows)", ov_path, len(df))
        if dong_prefix and "dong_code" in df.columns:
            df = df[df["dong_code"].astype(str).str.startswith(dong_prefix)]
        return df

    # 1) DB에서 로드 시도 (캐시 우선)
    _sales_key = ("sales", db_url, str(dong_prefix))
    if _sales_key in _DATA_CACHE:
        _cached_df, _cached_ts = _DATA_CACHE[_sales_key]
        if time.monotonic() - _cached_ts < _CACHE_TTL:
            logger.debug("캐시 히트 — sales data (%s)", dong_prefix)
            return _cached_df.copy()
    try:
        # dong_prefix가 없으면 서울 전체 테이블, 있으면 마포구 등 필터링
        table = "seoul_district_sales" if dong_prefix is None else "district_sales"
        where = f" WHERE dong_code LIKE '{dong_prefix}%'" if dong_prefix else ""
        query = f"SELECT * FROM {table}{where} ORDER BY quarter, dong_code"  # noqa: S608
        df = _load_from_db(query, db_url)
        logger.info("DB에서 %s 로드 완료: %d rows", table, len(df))
        _DATA_CACHE[_sales_key] = (df, time.monotonic())
    except Exception as exc:
        logger.warning("DB 접속 실패, CSV fallback 시도: %s", exc)

    # 2) CSV fallback
    if df is None or df.empty:
        if csv_path and Path(csv_path).exists():
            df = pd.read_csv(csv_path, dtype={"dong_code": str})
            logger.info("CSV에서 로드 완료: %s (%d rows)", csv_path, len(df))
        else:
            sales_csv = DATA_DIR / ("seoul_district_sales.csv" if dong_prefix is None else "district_sales.csv")
            if sales_csv.exists():
                df = pd.read_csv(sales_csv, dtype={"dong_code": str})
                logger.info("CSV에서 로드: %s (%d rows)", sales_csv, len(df))
            else:
                raise FileNotFoundError(f"데이터를 찾을 수 없습니다. DB 접속 실패 & CSV 없음: {sales_csv}")

    if dong_prefix and "dong_code" in df.columns:
        df = df[df["dong_code"].astype(str).str.startswith(dong_prefix)]

    return df


def load_store_data(
    db_url: str = DB_URL,
    csv_path: str | Path | None = None,
    dong_prefix: str | None = None,
) -> pd.DataFrame:
    """store_quarterly 데이터를 로드한다."""
    df = None

    # 1) DB에서 로드 시도 (캐시 우선)
    _store_key = ("store", db_url, str(dong_prefix))
    if _store_key in _DATA_CACHE:
        _cached_df, _cached_ts = _DATA_CACHE[_store_key]
        if time.monotonic() - _cached_ts < _CACHE_TTL:
            logger.debug("캐시 히트 — store data (%s)", dong_prefix)
            return _cached_df.copy()
    try:
        table = "seoul_district_stores" if dong_prefix is None else "store_quarterly"
        where = f" WHERE dong_code LIKE '{dong_prefix}%'" if dong_prefix else ""
        query = f"SELECT * FROM {table}{where} ORDER BY quarter, dong_code"  # noqa: S608
        df = _load_from_db(query, db_url)
        logger.info("DB에서 %s 로드 완료: %d rows", table, len(df))
        _DATA_CACHE[_store_key] = (df, time.monotonic())
    except Exception as exc:
        logger.warning("DB 접속 실패, CSV fallback 시도: %s", exc)

    # 2) CSV fallback
    if df is None or df.empty:
        if csv_path and Path(csv_path).exists():
            df = pd.read_csv(csv_path, dtype={"dong_code": str})
        else:
            stores_csv = DATA_DIR / ("seoul_district_stores.csv" if dong_prefix is None else "district_stores.csv")
            if stores_csv.exists():
                df = pd.read_csv(stores_csv, dtype={"dong_code": str})
                logger.info("CSV에서 로드: %s (%d rows)", stores_csv, len(df))
            else:
                logger.warning("store_quarterly 데이터 없음, 빈 DataFrame 반환")
                return pd.DataFrame()

    if dong_prefix and "dong_code" in df.columns:
        df = df[df["dong_code"].astype(str).str.startswith(dong_prefix)]

    return df


def load_timeseries(
    db_url: str = DB_URL,
    dong_prefix: str | None = None,
) -> pd.DataFrame:
    """load_sales_data + load_store_data + build_timeseries 를 합쳐서 캐싱한다.

    build_timeseries 내부에서 seoul_golmok_rent / holiday_calendar /
    load_adstrd_flpop 등 추가 DB 쿼리가 발생하므로, 결과 전체를 TTL 캐시로
    보관해 반복 호출 오버헤드를 제거한다.

    Parameters
    ----------
    db_url : str
        PostgreSQL 접속 URL.
    dong_prefix : str, optional
        행정동 코드 접두사 필터 (예: '11440' = 마포구).

    Returns
    -------
    pd.DataFrame
        build_timeseries 결과 (dong_code, industry_code, quarter, features).
    """
    _ts_key = ("ts", db_url, str(dong_prefix))
    if _ts_key in _DATA_CACHE:
        _cached_ts, _cached_time = _DATA_CACHE[_ts_key]
        if time.monotonic() - _cached_time < _CACHE_TTL:
            logger.debug("캐시 히트 — timeseries (%s)", dong_prefix)
            return _cached_ts.copy()

    sales_df = load_sales_data(db_url=db_url, dong_prefix=dong_prefix)
    store_df = load_store_data(db_url=db_url, dong_prefix=dong_prefix)
    ts = build_timeseries(sales_df, store_df)
    _DATA_CACHE[_ts_key] = (ts, time.monotonic())
    logger.info("timeseries 빌드 완료 → 캐시 저장 (%s, %d rows)", dong_prefix, len(ts))
    return ts.copy()


def load_adstrd_flpop(
    db_url: str = DB_URL,
    dong_prefix: str | None = None,
) -> pd.DataFrame:
    """seoul_adstrd_flpop에서 행정동 분기 유동인구를 로드한다.

    CSV 캐시 우선(scripts/cache_adstrd_flpop.py 실행 후 생성), 없으면 DB fallback.

    Parameters
    ----------
    db_url : str
        PostgreSQL 접속 URL.
    dong_prefix : str, optional
        행정동 코드 접두사 필터 (예: '11440' = 마포구). None이면 서울 전체.

    Returns
    -------
    pd.DataFrame
        컬럼: quarter, dong_code, adstrd_flpop
    """
    _csv = DATA_DIR / "adstrd_flpop_quarterly.csv"
    if _csv.exists():
        df = pd.read_csv(_csv, dtype={"dong_code": str})
        df["quarter"] = df["quarter"].astype(int)
        if dong_prefix:
            df = df[df["dong_code"].str.startswith(dong_prefix)]
        logger.info("adstrd_flpop CSV 로드: %s (%d rows)", _csv, len(df))
        return df[["quarter", "dong_code", "adstrd_flpop"]]

    try:
        where = f" WHERE dong_code LIKE '{dong_prefix}%'" if dong_prefix else ""
        query = (
            f"SELECT quarter, dong_code, total_flpop AS adstrd_flpop "  # noqa: S608
            f"FROM seoul_adstrd_flpop{where} ORDER BY quarter, dong_code"
        )
        df = _load_from_db(query, db_url)
        df["dong_code"] = df["dong_code"].astype(str)
        logger.info("DB에서 adstrd_flpop 로드 완료: %d rows", len(df))
        return df[["quarter", "dong_code", "adstrd_flpop"]]
    except Exception as exc:
        logger.warning("adstrd_flpop 로드 실패, 0으로 대체: %s", exc)
        return pd.DataFrame(columns=["quarter", "dong_code", "adstrd_flpop"])


# ---------------------------------------------------------------------------
# 결측치 처리 (guide-density Hot Deck 보간)
# ---------------------------------------------------------------------------


def _hot_deck(
    df: pd.DataFrame,
    col: str,
    donor_features: list[str],
) -> pd.DataFrame:
    """Hot Deck 보간: 결측치를 유사 행정동의 값으로 대체한다.

    1) 같은 분기 내에서 '2동' → '1동' 쌍이 있으면 해당 값 사용
    2) 없으면 NearestNeighbors로 가장 유사한 행의 값 사용
    """
    result = df.copy()
    dong_col = "dong_name" if "dong_name" in df.columns else None
    if dong_col is None:
        return result

    for _q, qdf in result.groupby("quarter"):
        miss = qdf[col].isna() | (qdf[col] == 0)
        if not miss.any():
            continue
        donors = qdf[~miss]
        recipients = qdf[miss]
        if donors.empty:
            continue

        for idx, row in recipients.iterrows():
            dn = str(row.get(dong_col, ""))
            donor_val = None

            # 1) 2동 → 1동 쌍 매칭
            if "2동" in dn:
                pair_name = dn.replace("2동", "1동")
                pair_rows = donors[donors[dong_col] == pair_name][col]
                if not pair_rows.empty:
                    donor_val = pair_rows.values[0]

            # 2) NearestNeighbors fallback
            if donor_val is None:
                avail_feats = [f for f in donor_features if f in donors.columns]
                if avail_feats:
                    nn_model = NearestNeighbors(n_neighbors=1)
                    nn_model.fit(donors[avail_feats].fillna(0).values)
                    _, d_idx = nn_model.kneighbors(row[avail_feats].fillna(0).values.reshape(1, -1).astype(float))
                    donor_val = donors.iloc[d_idx.flatten()[0]][col]

            if donor_val is not None:
                # int64 컬럼에 float 할당 시 TypeError 방지
                if result[col].dtype == np.int64:
                    result[col] = result[col].astype(float)
                result.at[idx, col] = donor_val * np.random.normal(1, 0.02)

    return result


def _impute_missing(
    df: pd.DataFrame,
    feature_cols: list[str] | None = None,
) -> pd.DataFrame:
    """guide-density 기반 결측치 처리.

    - 매출 컬럼: Hot Deck 보간
    - 점포/인구/임대 컬럼: 그룹별 선형 보간 + ffill/bfill
    - 나머지: fillna(0)
    """
    donor_features = [f for f in ["total_pop", "store_count"] if f in df.columns]
    gk = ["dong_code", "industry_code"]

    # 매출 컬럼: Hot Deck
    for col in SALES_FEATURES:
        if col in df.columns:
            df = _hot_deck(df, col, donor_features)

    # 점포/인구 컬럼: 그룹별 선형 보간
    interp_cols = [
        "store_count",
        "franchise_count",
        "open_count",
        "close_count",
        "total_pop",
        "resident_pop",
        "avg_age",
        "total_households",
    ]
    for col in interp_cols:
        if col in df.columns:
            df[col] = df.groupby(gk)[col].transform(lambda x: x.interpolate(method="linear", limit_direction="both"))
            df[col] = df.groupby(gk)[col].transform(lambda x: x.ffill().bfill())

    # 폐업률: 선형 보간
    if "closure_rate" in df.columns:
        df["closure_rate"] = df.groupby(gk)["closure_rate"].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both")
        )

    # 임대료: 동 단위 보간
    if "rent_1f" in df.columns:
        df["rent_1f"] = df.groupby("dong_code")["rent_1f"].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both")
        )
        df["rent_1f"] = df.groupby("dong_code")["rent_1f"].transform(lambda x: x.fillna(x.median()))

    # 공실률: 전체 선형 보간
    if "vacancy_rate" in df.columns:
        df["vacancy_rate"] = df["vacancy_rate"].interpolate(method="linear", limit_direction="both")

    # CPI: ffill/bfill
    if "cpi_index" in df.columns:
        df["cpi_index"] = df["cpi_index"].ffill().bfill()

    # 트렌드: 0 대체
    if "trend_score" in df.columns:
        df["trend_score"] = df["trend_score"].fillna(0)

    # 공휴일 수: 분기별 ffill 후 0 대체
    if "holiday_count" in df.columns:
        df["holiday_count"] = df["holiday_count"].ffill().bfill().fillna(0)

    # 버스 유동인구: 동별 선형 보간 후 0 대체
    if "bus_flpop" in df.columns:
        df["bus_flpop"] = df.groupby("dong_code")["bus_flpop"].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both")
        )
        df["bus_flpop"] = df["bus_flpop"].fillna(0)

    # 행정동 유동인구: 동별 선형 보간 후 0 대체
    if "adstrd_flpop" in df.columns:
        df["adstrd_flpop"] = df.groupby("dong_code")["adstrd_flpop"].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both")
        )
        df["adstrd_flpop"] = df["adstrd_flpop"].fillna(0)

    # opr_sale_mt_avg / cls_sale_mt_avg: 동별 선형 보간 후 0 대체
    for _new_feat in ("opr_sale_mt_avg", "cls_sale_mt_avg"):
        if _new_feat in df.columns:
            df[_new_feat] = df.groupby("dong_code")[_new_feat].transform(
                lambda x: x.interpolate(method="linear", limit_direction="both")
            )
            df[_new_feat] = df[_new_feat].fillna(0)

    # industry_trend: 업종별 선형 보간 후 0 대체
    if "industry_trend" in df.columns:
        df["industry_trend"] = df.groupby("industry_code")["industry_trend"].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both")
        )
        df["industry_trend"] = df["industry_trend"].fillna(0)

    # 나머지 피처: fillna(0)
    if feature_cols is None:
        feature_cols = ALL_FEATURES
    feat_available = [c for c in feature_cols if c in df.columns]
    df[feat_available] = df[feat_available].fillna(0)

    return df


# ---------------------------------------------------------------------------
# 피처 엔지니어링 / 시퀀스 생성
# ---------------------------------------------------------------------------


def build_timeseries(
    sales_df: pd.DataFrame,
    store_df: pd.DataFrame | None = None,
    feature_cols: list[str] | None = None,
) -> pd.DataFrame:
    """분기별 매출 + 점포 데이터를 (dong_code, industry_code, quarter) 기준으로
    정렬된 시계열 DataFrame으로 변환한다.

    Returns
    -------
    pd.DataFrame
        컬럼: dong_code, industry_code, quarter, + feature_cols
    """
    if feature_cols is None:
        feature_cols = ALL_FEATURES

    # 매출 테이블에서 사용 가능한 피처만 선택
    sales_cols = [c for c in SALES_FEATURES if c in sales_df.columns]
    key_cols = ["quarter", "dong_code", "industry_code"]
    extra_cols = ["dong_name"]  # 트렌드 매칭용
    avail_keys = [c for c in key_cols if c in sales_df.columns]
    avail_extra = [c for c in extra_cols if c in sales_df.columns]

    df = sales_df[avail_keys + avail_extra + sales_cols].copy()

    # 점포 데이터 병합
    if store_df is not None and not store_df.empty:
        store_cols = [c for c in STORE_FEATURES if c in store_df.columns]
        merge_keys = [c for c in ["quarter", "dong_code", "industry_code"] if c in store_df.columns]
        if merge_keys and store_cols:
            df = df.merge(
                store_df[merge_keys + store_cols],
                on=merge_keys,
                how="left",
            )

    # 유동인구 병합
    pop_csv = DATA_DIR / "seoul_population_quarterly.csv"
    if pop_csv.exists() and "quarter" in df.columns and "dong_code" in df.columns:
        pop_df = pd.read_csv(pop_csv, dtype={"dong_code": str})
        df = df.merge(pop_df[["quarter", "dong_code", "total_pop"]], on=["quarter", "dong_code"], how="left")

    # 추가 피처 로드 (CSV 기반)
    # 평균연령, 가구수
    demo_csv = DATA_DIR / "dong_demographics.csv"
    if demo_csv.exists() and "dong_code" in df.columns:
        dong_demo = pd.read_csv(demo_csv, dtype={"dong_code": str})
        df = df.merge(dong_demo[["dong_code", "avg_age", "total_households"]], on="dong_code", how="left")

    # 주거인구 (마포구 분기별)
    resident_csv = DATA_DIR / "mapo_resident_pop_quarterly.csv"
    if resident_csv.exists() and "quarter" in df.columns and "dong_code" in df.columns:
        res_df = pd.read_csv(resident_csv, dtype={"dong_code": str})
        df = df.merge(res_df[["quarter", "dong_code", "resident_pop"]], on=["quarter", "dong_code"], how="left")

    # 임대료 (서울 전체 행정동 단위 — DB)
    try:
        from sqlalchemy import create_engine

        engine = create_engine(DB_URL + "?connect_timeout=3", echo=False)
        rent_df = pd.read_sql(
            "SELECT dong_code, quarter_code AS quarter, rent_1f FROM seoul_golmok_rent WHERE rent_1f IS NOT NULL",
            engine,
        )
        rent_df["dong_code"] = rent_df["dong_code"].astype(str)
        df = df.merge(rent_df, on=["quarter", "dong_code"], how="left")
        engine.dispose()
    except Exception:
        pass

    # 공실률 (분기별 평균으로 집계 — 원본이 지역별 여러 행)
    vacancy_csv = DATA_DIR / "vacancy_rate_export.csv"
    if vacancy_csv.exists() and "quarter" in df.columns:
        vacancy_df = pd.read_csv(vacancy_csv)
        vacancy_df["quarter"] = vacancy_df["year"] * 10 + vacancy_df["q_num"]
        vacancy_agg = vacancy_df.groupby("quarter", as_index=False)["vacancy_rate"].mean()
        df = df.merge(vacancy_agg, on="quarter", how="left")

    # CPI 병합
    cpi_csv = DATA_DIR / "cpi_dining_quarterly.csv"
    if cpi_csv.exists() and "quarter" in df.columns:
        cpi_df = pd.read_csv(cpi_csv)
        df = df.merge(cpi_df[["quarter", "cpi_index"]], on="quarter", how="left")

    # 네이버 트렌드 병합 (서울 전체)
    trend_csv = DATA_DIR / "naver_trend_seoul_quarterly.csv"
    if trend_csv.exists() and "quarter" in df.columns and "dong_name" in df.columns:
        trend_df = pd.read_csv(trend_csv)
        df = df.merge(trend_df, on=["quarter", "dong_name"], how="left")

    # 골목상권 피처 병합 (golmok_merged.csv)
    golmok_csv = DATA_DIR / "golmok_merged.csv"
    if golmok_csv.exists() and "quarter" in df.columns and "dong_code" in df.columns:
        gm = pd.read_csv(golmok_csv, dtype={"dong_code": str, "industry_code": str})

        # 업종별 피처 (store_normal, store_franchise, store_total)
        gm_ind_cols = ["store_normal", "store_franchise", "store_total"]
        gm_ind_avail = [c for c in gm_ind_cols if c in gm.columns]
        if gm_ind_avail:
            gm_ind = gm[["quarter", "dong_code", "industry_code"] + gm_ind_avail].drop_duplicates(
                subset=["quarter", "dong_code", "industry_code"]
            )
            df = df.merge(gm_ind, on=["quarter", "dong_code", "industry_code"], how="left")

        # 동 단위 피처 (floating_pop)
        if "floating_pop" in gm.columns:
            gm_dong = gm[["quarter", "dong_code", "floating_pop"]].drop_duplicates(subset=["quarter", "dong_code"])
            df = df.merge(gm_dong, on=["quarter", "dong_code"], how="left")

        # 파생 피처: 일반 점포 비율 + 점포당 유동인구
        if "store_total" in df.columns:
            df["normal_ratio"] = np.where(df["store_total"] > 0, df["store_normal"] / df["store_total"], 0)
            if "floating_pop" in df.columns:
                df["pop_per_store_gm"] = np.where(df["store_total"] > 0, df["floating_pop"] / df["store_total"], 0)
            df = df.drop(columns=["store_total"], errors="ignore")

        # 골목상권 피처 보간 (그룹별 선형 보간 → forward/backward fill)
        gk = ["dong_code", "industry_code"]
        for feat in GOLMOK_FEATURES:
            if feat in df.columns:
                df[feat] = df.groupby(gk)[feat].transform(
                    lambda x: x.interpolate(method="linear", limit_direction="both")
                )
                df[feat] = df.groupby(gk)[feat].transform(lambda x: x.ffill().bfill())

    # 계절성 피처 추가 (분기 번호 1~4)
    if "quarter" in df.columns:
        df["quarter_num"] = (df["quarter"] % 10).astype(float)

    # 공휴일 수 피처 (holiday_calendar DB — 분기별 공휴일 count)
    try:
        from sqlalchemy import create_engine

        engine = create_engine(DB_URL + "?connect_timeout=3", echo=False)
        holiday_df = pd.read_sql(
            """
            SELECT
                (EXTRACT(YEAR FROM date)::int * 10 + EXTRACT(QUARTER FROM date)::int) AS quarter,
                COUNT(*) AS holiday_count
            FROM holiday_calendar
            WHERE is_holiday = true OR is_substitute = true
            GROUP BY quarter
            """,
            engine,
        )
        engine.dispose()
        holiday_df["quarter"] = holiday_df["quarter"].astype(int)
        df = df.merge(holiday_df, on="quarter", how="left")
        df["holiday_count"] = df["holiday_count"].fillna(0).astype(float)
    except Exception:
        df["holiday_count"] = 0.0

    # 버스 유동인구 피처 (CSV 캐시 우선, DB fallback)
    # 사전 집계 CSV: scripts/cache_bus_flpop.py 실행 후 생성
    # CSV 없으면 DB에서 실시간 집계 (371만 행 GROUP BY — 느림)
    _bus_csv = DATA_DIR / "bus_flpop_quarterly.csv"
    try:
        if _bus_csv.exists():
            bus_agg = pd.read_csv(_bus_csv, dtype={"dong_code": str})
            bus_agg["quarter"] = bus_agg["quarter"].astype(int)
            df = df.merge(bus_agg[["quarter", "dong_code", "bus_flpop"]], on=["quarter", "dong_code"], how="left")
            df["bus_flpop"] = df["bus_flpop"].fillna(0).astype(float)
        else:
            # DB fallback (느린 경로 — 사전 캐싱 권장: python -m scripts.cache_bus_flpop)
            logger.warning("bus_flpop CSV 없음, DB 실시간 집계 시도 (느릴 수 있음)")
            from sqlalchemy import create_engine

            engine = create_engine(DB_URL + "?connect_timeout=3", echo=False)
            bus_df = pd.read_sql(
                """
                SELECT
                    (EXTRACT(YEAR FROM use_date)::int * 10 + EXTRACT(QUARTER FROM use_date)::int) AS quarter,
                    station_name,
                    SUM(boarding_count + alighting_count) AS bus_flpop_raw
                FROM bus_boarding_daily
                GROUP BY quarter, station_name
                """,
                engine,
            )
            engine.dispose()

            if not bus_df.empty and "dong_name" in df.columns:
                dong_names = df["dong_name"].dropna().unique().tolist()
                bus_df["matched_dong"] = bus_df["station_name"].apply(
                    lambda s: next((d for d in dong_names if d.replace("동", "") in str(s)), None)
                )
                bus_agg2 = (
                    bus_df[bus_df["matched_dong"].notna()]
                    .groupby(["quarter", "matched_dong"], as_index=False)["bus_flpop_raw"]
                    .sum()
                    .rename(columns={"matched_dong": "dong_name", "bus_flpop_raw": "bus_flpop"})
                )
                bus_agg2["quarter"] = bus_agg2["quarter"].astype(int)
                df = df.merge(bus_agg2, on=["quarter", "dong_name"], how="left")
                df["bus_flpop"] = df["bus_flpop"].fillna(0).astype(float)
            else:
                df["bus_flpop"] = 0.0
    except Exception:
        df["bus_flpop"] = 0.0

    # 행정동 유동인구 피처 (seoul_adstrd_flpop.total_flpop — 서울 전체 동 커버)
    flpop_df = load_adstrd_flpop(db_url=DB_URL)
    if not flpop_df.empty and "quarter" in df.columns and "dong_code" in df.columns:
        flpop_df["quarter"] = flpop_df["quarter"].astype(int)
        df = df.merge(flpop_df, on=["quarter", "dong_code"], how="left")
        df["adstrd_flpop"] = df["adstrd_flpop"].fillna(0).astype(float)
    else:
        df["adstrd_flpop"] = 0.0

    # ── 신규 피처: opr_sale_mt_avg, cls_sale_mt_avg (seoul_adstrd_change_ix) ──
    try:
        from sqlalchemy import create_engine

        engine = create_engine(DB_URL + "?connect_timeout=3", echo=False)
        change_df = pd.read_sql(
            """
            SELECT
                quarter,
                dong_code,
                AVG(opr_sale_mt_avg) AS opr_sale_mt_avg,
                AVG(cls_sale_mt_avg) AS cls_sale_mt_avg
            FROM seoul_adstrd_change_ix
            GROUP BY quarter, dong_code
            """,
            engine,
        )
        engine.dispose()
        change_df["dong_code"] = change_df["dong_code"].astype(str)
        change_df["quarter"] = change_df["quarter"].astype(int)
        if "quarter" in df.columns and "dong_code" in df.columns:
            df = df.merge(change_df, on=["quarter", "dong_code"], how="left")
    except Exception:
        df["opr_sale_mt_avg"] = 0.0
        df["cls_sale_mt_avg"] = 0.0

    # ── 신규 피처: industry_trend (naver_trend_industry) ──
    try:
        from sqlalchemy import create_engine

        engine = create_engine(DB_URL + "?connect_timeout=3", echo=False)
        naver_df = pd.read_sql(
            """
            SELECT
                industry,
                (EXTRACT(YEAR FROM period)::int * 10
                 + EXTRACT(QUARTER FROM period)::int) AS quarter,
                AVG(ratio) AS industry_trend
            FROM naver_trend_industry
            GROUP BY industry, quarter
            """,
            engine,
        )
        engine.dispose()
        naver_df["quarter"] = naver_df["quarter"].astype(int)
        _CS_TO_NAVER_LOCAL: dict[str, str] = {
            "CS100001": "한식",
            "CS100002": "중식",
            "CS100003": "일식",
            "CS100004": "양식",
            "CS100005": "제과",
            "CS100006": "패스트푸드",
            "CS100007": "치킨",
            "CS100008": "분식",
            "CS100009": "호프",
            "CS100010": "커피",
        }
        if "industry_code" in df.columns:
            df["_naver_industry"] = df["industry_code"].map(_CS_TO_NAVER_LOCAL)
            naver_df = naver_df.rename(columns={"industry": "_naver_industry"})
            df = df.merge(naver_df, on=["quarter", "_naver_industry"], how="left")
            df = df.drop(columns=["_naver_industry"], errors="ignore")
    except Exception:
        df["industry_trend"] = 0.0

    # 코로나 시기 가중치 (2020~2021 → 0.5, 나머지 → 1.0)
    if "quarter" in df.columns:
        year = df["quarter"] // 10
        df["sample_weight"] = np.where((year >= 2020) & (year <= 2021), 0.5, 1.0)

    # 결측치 처리 (guide-density Hot Deck 보간)
    df = _impute_missing(df, feature_cols)

    # 로그 스케일 변환 (매출 관련 컬럼)
    log_cols = [c for c in SALES_FEATURES if c in df.columns]
    for col in log_cols:
        df[col] = np.log1p(df[col].clip(lower=0))  # log(1 + x), 0원 처리

    # 분기 기준 정렬
    df = df.sort_values(["dong_code", "industry_code", "quarter"]).reset_index(drop=True)

    return df


def prepare_sequences(
    data: pd.DataFrame,
    window_size: int = 4,
    output_size: int = 1,
    target_col: str = "monthly_sales",
    feature_cols: list[str] | None = None,
) -> tuple:
    """시계열 데이터를 LSTM 입력 시퀀스로 변환한다.

    (dong_code, industry_code) 그룹별로 sliding window를 적용하여
    ``(X, y)`` 시퀀스를 생성한다.

    Parameters
    ----------
    data : pd.DataFrame
        ``build_timeseries()`` 의 출력.
    window_size : int
        입력 시퀀스 길이 (분기 수).
    output_size : int
        예측 스텝 수. DMS=4, 기존 단일스텝=1 (기본값 1 → 하위 호환).
    target_col : str
        예측 대상 컬럼.
    feature_cols : list[str], optional
        입력 피처 컬럼 목록.

    Returns
    -------
    X : np.ndarray, shape ``(N, window_size, n_features)``
    y : np.ndarray, shape ``(N, output_size)``
    feature_scaler : MinMaxScaler
    target_scaler : MinMaxScaler
    w : np.ndarray, shape ``(N,)``
    first_pred_quarters : np.ndarray, shape ``(N,)``
    """
    if feature_cols is None:
        feature_cols = [c for c in ALL_FEATURES if c in data.columns]

    # 타겟 컬럼이 피처에 포함되어 있으면 그대로, 아니면 추가
    if target_col not in feature_cols and target_col in data.columns:
        feature_cols = feature_cols + [target_col]

    feature_cols = [c for c in feature_cols if c in data.columns]

    if not feature_cols:
        raise ValueError("사용 가능한 피처 컬럼이 없습니다.")

    # 스케일링
    feature_scaler = MinMaxScaler()
    target_scaler = MinMaxScaler()

    all_features = data[feature_cols].values.astype(np.float32)
    all_targets = data[[target_col]].values.astype(np.float32)

    feature_scaler.fit(all_features)
    target_scaler.fit(all_targets)

    X_list: list[np.ndarray] = []
    y_list: list[np.ndarray] = []
    w_list: list[float] = []
    first_pred_quarters_list: list[int] = []
    has_weight = "sample_weight" in data.columns

    groups = data.groupby(["dong_code", "industry_code"])
    for (dong_code, industry_code), group in groups:
        # 극단적 이상치 조합 제외
        if (str(dong_code), str(industry_code)) in EXCLUDE_COMBOS:
            continue
        if len(group) < window_size + output_size:
            continue

        feat_vals = feature_scaler.transform(group[feature_cols].values.astype(np.float32))
        tgt_vals = target_scaler.transform(group[[target_col]].values.astype(np.float32))
        weights = group["sample_weight"].values if has_weight else np.ones(len(group))
        quarter_vals = group["quarter"].values

        for i in range(len(group) - window_size - output_size + 1):
            X_list.append(feat_vals[i : i + window_size])
            y_list.append(tgt_vals[i + window_size : i + window_size + output_size].flatten())
            w_list.append(float(weights[i + window_size]))
            first_pred_quarters_list.append(int(quarter_vals[i + window_size]))

    if not X_list:
        raise ValueError(f"시퀀스를 생성할 수 없습니다. window_size={window_size}보다 긴 시계열 그룹이 없습니다.")

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    w = np.array(w_list, dtype=np.float32)
    first_pred_quarters = np.array(first_pred_quarters_list, dtype=np.int32)

    return X, y, feature_scaler, target_scaler, w, first_pred_quarters


# ---------------------------------------------------------------------------
# DataLoader 생성
# ---------------------------------------------------------------------------


def prepare_dataloaders(
    config: dict,
) -> tuple[DataLoader, DataLoader, MinMaxScaler, MinMaxScaler, int]:
    """config 기반으로 학습/검증 DataLoader를 생성한다.

    Parameters
    ----------
    config : dict
        필수 키:
        - db_url : str
        - dong_prefix : str or None  (None = 서울 전체)
        - window_size : int
        - batch_size : int
        - val_ratio : float
        선택 키:
        - csv_path : str
        - target_col : str (default: 'monthly_sales')
        - feature_cols : list[str]
        - sales_csv_override : str or Path
            지정 시 DB 무시하고 이 CSV를 매출 소스로 사용 (imputation 비교용).
        - train_cutoff_quarter : int, optional
            지정 시 quarter >= cutoff인 row를 학습/검증에서 제외 (데이터 누수 방어).

    Returns
    -------
    train_loader : DataLoader
    val_loader : DataLoader
    feature_scaler : MinMaxScaler
    target_scaler : MinMaxScaler
    input_size : int
        실제 사용된 피처 수 (모델 input_size에 전달).
    """
    db_url = config.get("db_url", DB_URL)
    dong_prefix = config.get("dong_prefix", None)
    window_size = config.get("window_size", 4)
    batch_size = config.get("batch_size", 64)
    val_ratio = config.get("val_ratio", 0.2)
    target_col = config.get("target_col", "monthly_sales")
    feature_cols = config.get("feature_cols", None)
    csv_path = config.get("csv_path", None)
    sales_csv_override = config.get("sales_csv_override", None)

    # 데이터 로드
    sales_df = load_sales_data(
        db_url=db_url,
        csv_path=csv_path,
        dong_prefix=dong_prefix,
        sales_csv_override=sales_csv_override,
    )
    store_df = load_store_data(db_url=db_url, dong_prefix=dong_prefix)

    # train_cutoff_quarter 적용 — 데이터 누수 방어 (백테스트 평가 연도 차단)
    train_cutoff_quarter = config.get("train_cutoff_quarter", None)
    if train_cutoff_quarter is not None and "quarter" in sales_df.columns:
        cutoff = int(train_cutoff_quarter)
        before_sales = len(sales_df)
        sales_df = sales_df[sales_df["quarter"] < cutoff].copy()
        logger.info(
            "train_cutoff_quarter=%s 적용 (sales_df): %d → %d rows",
            cutoff,
            before_sales,
            len(sales_df),
        )
        if "quarter" in store_df.columns:
            before_store = len(store_df)
            store_df = store_df[store_df["quarter"] < cutoff].copy()
            logger.info(
                "train_cutoff_quarter=%s 적용 (store_df): %d → %d rows",
                cutoff,
                before_store,
                len(store_df),
            )

    # 시계열 구성
    ts = build_timeseries(sales_df, store_df, feature_cols)
    logger.info("시계열 DataFrame 크기: %s", ts.shape)

    # 시퀀스 생성
    output_size = config.get("output_size", 1)
    X, y, feat_scaler, tgt_scaler, w, first_pred_quarters = prepare_sequences(
        ts,
        window_size=window_size,
        output_size=output_size,
        target_col=target_col,
        feature_cols=feature_cols,
    )
    logger.info("시퀀스 생성 완료: X=%s, y=%s", X.shape, y.shape)

    input_size = X.shape[2]

    # Train / Val split
    val_quarter = config.get("val_quarter", None)
    if val_quarter is not None:
        val_mask = first_pred_quarters >= int(val_quarter)
        if not np.any(~val_mask):
            raise ValueError(f"val_quarter={val_quarter} 적용 후 학습 데이터가 없습니다.")
        if not np.any(val_mask):
            raise ValueError(f"val_quarter={val_quarter} 적용 후 검증 데이터가 없습니다.")
        X_train, X_val = X[~val_mask], X[val_mask]
        y_train, y_val = y[~val_mask], y[val_mask]
        w_train = w[~val_mask]
        logger.info(
            "시간 기반 val 분할: val_quarter=%s → train=%d, val=%d",
            val_quarter,
            len(X_train),
            len(X_val),
        )
    else:
        n_val = max(1, int(len(X) * val_ratio))
        n_train = len(X) - n_val
        X_train, X_val = X[:n_train], X[n_train:]
        y_train, y_val = y[:n_train], y[n_train:]
        w_train = w[:n_train]

    train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train), torch.from_numpy(w_train))
    val_ds = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    return train_loader, val_loader, feat_scaler, tgt_scaler, input_size
