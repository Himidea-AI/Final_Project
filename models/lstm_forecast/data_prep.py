"""
LSTM 시계열 데이터 전처리 -- 분기별 매출 시계열 생성

DB(PostgreSQL) 또는 CSV에서 분기별 매출/점포 데이터를 로드하여
(동코드 x 업종코드) 그룹별 시계열 시퀀스를 생성한다.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 기본 경로 / DB 접속 정보
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "processed"

_pw = os.environ.get("POSTGRES_PASSWORD", "postgres")
_host = os.environ.get("POSTGRES_HOST", "192.168.0.28")
_port = os.environ.get("POSTGRES_PORT", "5432")
_db = os.environ.get("POSTGRES_DB", "mapo_simulator")
DB_URL = os.environ.get(
    "POSTGRES_URL",
    f"postgresql://postgres:{_pw}@{_host}:{_port}/{_db}",
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

    Returns
    -------
    pd.DataFrame
        분기별 매출 데이터.
    """
    df = None

    # 1) DB에서 로드 시도
    try:
        # dong_prefix가 없으면 서울 전체 테이블, 있으면 마포구 등 필터링
        table = "seoul_district_sales" if dong_prefix is None else "district_sales"
        where = f" WHERE dong_code LIKE '{dong_prefix}%'" if dong_prefix else ""
        query = f"SELECT * FROM {table}{where} ORDER BY quarter, dong_code"  # noqa: S608
        df = _load_from_db(query, db_url)
        logger.info("DB에서 %s 로드 완료: %d rows", table, len(df))
    except Exception as exc:
        logger.warning("DB 접속 실패, CSV fallback 시도: %s", exc)

    # 2) CSV fallback
    if df is None or df.empty:
        if csv_path and Path(csv_path).exists():
            df = pd.read_csv(csv_path, dtype={"dong_code": str})
            logger.info("CSV에서 로드 완료: %s (%d rows)", csv_path, len(df))
        else:
            # 개별 파일 시도 (dong_prefix 없으면 서울 전체 우선)
            sales_csv = DATA_DIR / ("seoul_district_sales.csv" if dong_prefix is None else "district_sales.csv")
            if sales_csv.exists():
                df = pd.read_csv(sales_csv, dtype={"dong_code": str, "행정동코드": str})
                # rename if needed (원본 한글 컬럼명 → 영문)
                csv_rename = {
                    "STDR_YYQU_CD": "quarter",
                    "행정동코드": "dong_code",
                    "행정동명": "dong_name",
                    "SVC_INDUTY_CD": "industry_code",
                    "SVC_INDUTY_CD_NM": "industry_name",
                    "THSMON_SELNG_AMT": "monthly_sales",
                    "THSMON_SELNG_CO": "monthly_count",
                    "MDWK_SELNG_AMT": "weekday_sales",
                    "WKEND_SELNG_AMT": "weekend_sales",
                    "ML_SELNG_AMT": "male_sales",
                    "FML_SELNG_AMT": "female_sales",
                    "AGRDE_10_SELNG_AMT": "age_10_sales",
                    "AGRDE_20_SELNG_AMT": "age_20_sales",
                    "AGRDE_30_SELNG_AMT": "age_30_sales",
                    "AGRDE_40_SELNG_AMT": "age_40_sales",
                    "AGRDE_50_SELNG_AMT": "age_50_sales",
                    "AGRDE_60_ABOVE_SELNG_AMT": "age_60_above_sales",
                }
                df = df.rename(columns={k: v for k, v in csv_rename.items() if k in df.columns})
                logger.info("개별 CSV에서 로드: %s (%d rows)", sales_csv, len(df))
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

    try:
        table = "seoul_district_stores" if dong_prefix is None else "store_quarterly"
        where = f" WHERE dong_code LIKE '{dong_prefix}%'" if dong_prefix else ""
        query = f"SELECT * FROM {table}{where} ORDER BY quarter, dong_code"  # noqa: S608
        df = _load_from_db(query, db_url)
        logger.info("DB에서 %s 로드 완료: %d rows", table, len(df))
    except Exception as exc:
        logger.warning("DB 접속 실패, CSV fallback 시도: %s", exc)

    if df is None or df.empty:
        if csv_path and Path(csv_path).exists():
            df = pd.read_csv(csv_path, dtype={"dong_code": str})
        else:
            stores_csv = DATA_DIR / ("seoul_district_stores.csv" if dong_prefix is None else "district_stores.csv")
            if stores_csv.exists():
                df = pd.read_csv(stores_csv, dtype={"dong_code": str, "행정동코드": str})
                store_rename = {
                    "STDR_YYQU_CD": "quarter",
                    "행정동코드": "dong_code",
                    "행정동명": "dong_name",
                    "SVC_INDUTY_CD": "industry_code",
                    "SVC_INDUTY_CD_NM": "industry_name",
                    "STOR_CO": "store_count",
                    "OPBIZ_STOR_CO": "open_count",
                    "CLSBIZ_STOR_CO": "close_count",
                    "FRC_STOR_CO": "franchise_count",
                    "CLSBIZ_RT": "closure_rate",
                }
                df = df.rename(columns={k: v for k, v in store_rename.items() if k in df.columns})
                logger.info("개별 CSV에서 로드: %s (%d rows)", stores_csv, len(df))
            else:
                logger.warning("store_quarterly 데이터 없음, 빈 DataFrame 반환")
                return pd.DataFrame()

    if dong_prefix and "dong_code" in df.columns:
        df = df[df["dong_code"].astype(str).str.startswith(dong_prefix)]

    return df


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
    target_col: str = "monthly_sales",
    feature_cols: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, MinMaxScaler, MinMaxScaler]:
    """시계열 데이터를 LSTM 입력 시퀀스로 변환한다.

    (dong_code, industry_code) 그룹별로 sliding window를 적용하여
    ``(X, y)`` 시퀀스를 생성한다.

    Parameters
    ----------
    data : pd.DataFrame
        ``build_timeseries()`` 의 출력.
    window_size : int
        입력 시퀀스 길이 (분기 수).
    target_col : str
        예측 대상 컬럼.
    feature_cols : list[str], optional
        입력 피처 컬럼 목록.

    Returns
    -------
    X : np.ndarray, shape ``(N, window_size, n_features)``
    y : np.ndarray, shape ``(N, 1)``
    feature_scaler : MinMaxScaler
    target_scaler : MinMaxScaler
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
    has_weight = "sample_weight" in data.columns

    groups = data.groupby(["dong_code", "industry_code"])
    for (dong_code, industry_code), group in groups:
        # 극단적 이상치 조합 제외
        if (str(dong_code), str(industry_code)) in EXCLUDE_COMBOS:
            continue
        if len(group) <= window_size:
            continue

        feat_vals = feature_scaler.transform(group[feature_cols].values.astype(np.float32))
        tgt_vals = target_scaler.transform(group[[target_col]].values.astype(np.float32))
        weights = group["sample_weight"].values if has_weight else np.ones(len(group))

        for i in range(len(group) - window_size):
            X_list.append(feat_vals[i : i + window_size])
            y_list.append(tgt_vals[i + window_size])
            w_list.append(float(weights[i + window_size]))

    if not X_list:
        raise ValueError(f"시퀀스를 생성할 수 없습니다. window_size={window_size}보다 긴 시계열 그룹이 없습니다.")

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    w = np.array(w_list, dtype=np.float32)

    return X, y, feature_scaler, target_scaler, w


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

    # 데이터 로드
    sales_df = load_sales_data(db_url=db_url, csv_path=csv_path, dong_prefix=dong_prefix)
    store_df = load_store_data(db_url=db_url, dong_prefix=dong_prefix)

    # 시계열 구성
    ts = build_timeseries(sales_df, store_df, feature_cols)
    logger.info("시계열 DataFrame 크기: %s", ts.shape)

    # 시퀀스 생성
    X, y, feat_scaler, tgt_scaler, w = prepare_sequences(
        ts,
        window_size=window_size,
        target_col=target_col,
        feature_cols=feature_cols,
    )
    logger.info("시퀀스 생성 완료: X=%s, y=%s", X.shape, y.shape)

    input_size = X.shape[2]

    # Train / Val split (시간순 유지를 위해 뒤쪽을 val로 사용)
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
