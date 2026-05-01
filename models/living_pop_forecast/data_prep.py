"""
생활인구 시계열 데이터 전처리 — 동×시간대 분기 집계 시계열 생성

living_population(일별 × 시간대) → 분기 평균 집계 → 슬라이딩 윈도우 시퀀스

집계 단위: (dong_code, time_zone, quarter)
  - total_avg_pop  : 분기 전체 평균 유동인구 (타겟)
  - weekday_avg_pop: 평일 평균
  - weekend_avg_pop: 주말 평균

담당: B2 — 수지니
참조: models/lstm_forecast/data_prep.py (DB 접속 패턴 동일)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from dotenv import load_dotenv
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 경로 / DB 접속
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "processed"

# backend/.env 우선 로드 후 프로젝트 루트 .env 도 시도 (override=False — 기존 값 유지)
load_dotenv(PROJECT_ROOT / "backend" / ".env")
load_dotenv(PROJECT_ROOT / ".env", override=False)

DB_URL = os.environ.get("POSTGRES_URL")
if DB_URL is None or DB_URL == "":
    raise RuntimeError(
        "POSTGRES_URL 환경변수가 설정되지 않았습니다. "
        "프로젝트 루트의 .env 또는 backend/.env 파일에 POSTGRES_URL을 설정하세요."
    )

# ---------------------------------------------------------------------------
# 피처 정의
# ---------------------------------------------------------------------------

# 입력 피처 (스케일링 대상)
# v2 production: time_zone_norm + quarter_num + 인구 3개 (5차원 + dong_one_hot 16 = 21)
# 참고: v3 ablation (sin/cos + 외부 3 피처) 는 v2 대비 RMSE 8.3배 악화로 reject.
#       자세한 내용은 docs/abm-simulation/living-pop-forecast-v2-vs-v3-report.md 참조.
#       sin/cos 컬럼과 외부 피처는 build_timeseries 에서 여전히 계산되므로 cfg.feature_cols 로 선택 가능.
POP_FEATURES = [
    "total_avg_pop",  # 분기 전체 평균 유동인구 (타겟 겸 피처)
    "weekday_avg_pop",  # 평일 평균
    "weekend_avg_pop",  # 주말 평균
    "time_zone_norm",  # 시간대 정규화 (0~23 → 0~1)
    "quarter_num",  # 분기 번호 (1~4)
]

# v3 ablation 피처 (현재 production 미사용, cfg.feature_cols 로 선택 가능)
EXTERNAL_FEATURES_V3 = [
    "time_sin",
    "time_cos",
    "quarter_sin",
    "quarter_cos",
    "holiday_count",
    "trend_score",
    "cpi_index",
]

# v5 group_residual: residual learning + group-aware features (Plan Task 3)
# 분산의 98% 가 동×시간대 그룹 평균 차이에서 나옴 → explicit feature 로 제공.
POP_FEATURES_GROUP_RESIDUAL = [
    "total_avg_pop",
    "weekday_avg_pop",
    "weekend_avg_pop",
    "time_zone_norm",
    "quarter_num",
    "group_mean",  # train split 의 (dong_code, time_zone) 평균 — leakage 방지
    "group_relative",  # (y - group_mean) / group_mean
]

# v5 retry: group_mean 제거 (group_mean 은 (dong_code, time_zone) 당 단일값 →
# dong_one_hot + time_zone_norm 과 정보적으로 redundant + MinMaxScaler global fit
# 시 다른 피처를 압도. group_relative 만 보조 signal 로 유지.
# 진단: group_mean 의 (dong_code, time_zone) 별 unique value 개수 == 1 (확인됨).
POP_FEATURES_GROUP_REL_ONLY = [
    "total_avg_pop",
    "weekday_avg_pop",
    "weekend_avg_pop",
    "time_zone_norm",
    "quarter_num",
    "group_relative",  # (y - group_mean) / group_mean — 변동 신호만 유지
]

# 마포구 16동 정렬된 dong_code (one-hot 인덱스)
MAPO_DONG_CODES: tuple[str, ...] = (
    "11440555",  # 아현동
    "11440565",  # 공덕동
    "11440585",  # 도화동
    "11440590",  # 용강동
    "11440600",  # 대흥동
    "11440610",  # 염리동
    "11440630",  # 신수동
    "11440655",  # 서강동
    "11440660",  # 서교동
    "11440680",  # 합정동
    "11440690",  # 망원1동
    "11440700",  # 망원2동
    "11440710",  # 연남동
    "11440720",  # 성산1동
    "11440730",  # 성산2동
    "11440740",  # 상암동
)

DONG_FEATURES: list[str] = [f"dong_{dc}" for dc in MAPO_DONG_CODES]
ALL_FEATURES: list[str] = POP_FEATURES + DONG_FEATURES  # v2 production: 5 + 16 = 21

TARGET_COL = "total_avg_pop"


def _add_dong_one_hot(df: pd.DataFrame) -> pd.DataFrame:
    """dong_code → 16개 one-hot 컬럼 추가.

    Raises
    ------
    ValueError
        16동 외 동 입력 시.
    """
    df = df.copy()
    for dc in MAPO_DONG_CODES:
        df[f"dong_{dc}"] = (df["dong_code"] == dc).astype(np.float32)

    # 16동 외 row 검증
    df["_dong_sum"] = df[DONG_FEATURES].sum(axis=1)
    if (df["_dong_sum"] == 0).any():
        bad_codes = df[df["_dong_sum"] == 0]["dong_code"].unique().tolist()
        raise ValueError(f"알 수 없는 dong_code: {bad_codes}. 마포구 16동만 지원.")
    df = df.drop(columns=["_dong_sum"])
    return df


# ---------------------------------------------------------------------------
# DB 유틸
# ---------------------------------------------------------------------------


def _load_from_db(query: str, db_url: str = DB_URL) -> pd.DataFrame:
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url, echo=False)
    try:
        with engine.connect() as conn:
            return pd.read_sql(text(query), conn)
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# 데이터 로드 및 집계
# ---------------------------------------------------------------------------


def load_living_population(
    db_url: str = DB_URL,
    csv_path: str | Path | None = None,
) -> pd.DataFrame:
    """living_population을 동×시간대×분기 집계로 로드한다.

    CSV 캐시(data/processed/living_pop_quarterly.csv) 우선,
    없으면 DB 집계.

    Returns
    -------
    pd.DataFrame
        컬럼: quarter (int), dong_code, dong_name, time_zone,
               total_avg_pop, weekday_avg_pop, weekend_avg_pop
    """
    cache_csv = Path(csv_path) if csv_path else DATA_DIR / "living_pop_quarterly.csv"

    if cache_csv.exists():
        df = pd.read_csv(cache_csv, dtype={"dong_code": str})
        df["quarter"] = df["quarter"].astype(int)
        logger.info("생활인구 CSV 로드: %s (%d rows)", cache_csv, len(df))
        return df

    logger.info("living_population DB 집계 중...")
    try:
        df = _load_from_db(
            """
            SELECT
                (EXTRACT(YEAR FROM date)::int * 10
                 + EXTRACT(QUARTER FROM date)::int) AS quarter,
                dong_code,
                dong_name,
                time_zone,
                AVG(total_pop)                                           AS total_avg_pop,
                AVG(CASE WHEN EXTRACT(DOW FROM date) NOT IN (0, 6)
                         THEN total_pop END)                            AS weekday_avg_pop,
                AVG(CASE WHEN EXTRACT(DOW FROM date) IN (0, 6)
                         THEN total_pop END)                            AS weekend_avg_pop
            FROM living_population
            GROUP BY quarter, dong_code, dong_name, time_zone
            ORDER BY dong_code, time_zone, quarter
            """,
            db_url,
        )
        df["dong_code"] = df["dong_code"].astype(str)
        df["quarter"] = df["quarter"].astype(int)
        logger.info("DB 집계 완료: %d rows", len(df))

        # CSV 캐시 저장
        cache_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache_csv, index=False)
        logger.info("CSV 캐시 저장: %s", cache_csv)

        return df
    except Exception as exc:
        raise FileNotFoundError(f"living_population 로드 실패. DB: {exc}") from exc


# ---------------------------------------------------------------------------
# 피처 엔지니어링
# ---------------------------------------------------------------------------


def _load_holiday_count(db_url: str = DB_URL) -> pd.DataFrame:
    """분기별 공휴일 수 (RDS holiday_calendar)."""
    sql = """
        SELECT
            (EXTRACT(YEAR FROM date)::int * 10 + EXTRACT(QUARTER FROM date)::int) AS quarter,
            COUNT(*) AS holiday_count
        FROM holiday_calendar
        WHERE is_holiday = true OR is_substitute = true
        GROUP BY quarter
    """
    try:
        df = _load_from_db(sql, db_url)
        df["quarter"] = df["quarter"].astype(int)
        df["holiday_count"] = df["holiday_count"].astype(float)
        logger.info("holiday_calendar 로드: %d rows", len(df))
        return df
    except Exception as exc:
        logger.warning("holiday_calendar 로드 실패: %s", exc)
        return pd.DataFrame(columns=["quarter", "holiday_count"])


def _load_trend_score(db_url: str = DB_URL) -> pd.DataFrame:
    """동별 분기 네이버 검색 트렌드 (CSV 캐시 우선, DB fallback)."""
    csv_path = DATA_DIR / "naver_trend_quarterly.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        if "quarter" in df.columns:
            df["quarter"] = df["quarter"].astype(int)
        if "dong_name" in df.columns:
            cols = ["quarter", "dong_name", "trend_score"]
        elif "dong_code" in df.columns:
            df["dong_code"] = df["dong_code"].astype(str)
            cols = ["quarter", "dong_code", "trend_score"]
        else:
            logger.warning("naver_trend CSV에 dong_name/dong_code 컬럼이 없습니다.")
            return pd.DataFrame(columns=["quarter", "dong_name", "trend_score"])
        logger.info("naver_trend CSV 로드: %s (%d rows)", csv_path, len(df))
        return df[cols]

    sql = "SELECT quarter, dong_name, trend_score FROM naver_trend_quarterly"
    try:
        df = _load_from_db(sql, db_url)
        df["quarter"] = df["quarter"].astype(int)
        return df
    except Exception as exc:
        logger.warning("naver_trend 로드 실패: %s", exc)
        return pd.DataFrame(columns=["quarter", "dong_name", "trend_score"])


def _load_cpi_index(db_url: str = DB_URL) -> pd.DataFrame:
    """분기별 CPI 외식 지수 (전국 단일)."""
    csv_path = DATA_DIR / "cpi_dining_quarterly.csv"
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        df["quarter"] = df["quarter"].astype(int)
        logger.info("cpi_dining CSV 로드: %s (%d rows)", csv_path, len(df))
        return df[["quarter", "cpi_index"]]

    sql = "SELECT quarter, cpi_index FROM cpi_dining_quarterly"
    try:
        df = _load_from_db(sql, db_url)
        df["quarter"] = df["quarter"].astype(int)
        return df
    except Exception as exc:
        logger.warning("cpi_dining 로드 실패: %s", exc)
        return pd.DataFrame(columns=["quarter", "cpi_index"])


def _enrich_external_features(df: pd.DataFrame) -> pd.DataFrame:
    """외부 3 피처 (holiday/trend/cpi) join.

    결측 처리 정책:
    - cpi_index, trend_score: forward fill → 마지막 알려진 값으로 미래 분기 채움
      (외부 데이터가 train 범위까지만 존재하는 경우 0으로 채우면 정규화 후 분포가
       train 범위 밖으로 튀어 모델 일반화를 망친다. 시계열 표준인 last-observation-carry-forward 적용.)
    - holiday_count: 분기별 항상 존재해야 함 → 결측은 중앙값으로 채움 (방어적)
    """
    holiday_df = _load_holiday_count()
    trend_df = _load_trend_score()
    cpi_df = _load_cpi_index()

    if not holiday_df.empty:
        df = df.merge(holiday_df, on="quarter", how="left")

    if not trend_df.empty:
        if "dong_name" in df.columns and "dong_name" in trend_df.columns:
            df = df.merge(trend_df, on=["quarter", "dong_name"], how="left")
        elif "dong_code" in df.columns and "dong_code" in trend_df.columns:
            df = df.merge(trend_df, on=["quarter", "dong_code"], how="left")

    # holiday_count: 분기별 단일값 — 결측 시 중앙값(코드상 4)로 채움
    if "holiday_count" in df.columns:
        df["holiday_count"] = df["holiday_count"].fillna(df["holiday_count"].median()).astype(float)
    else:
        df["holiday_count"] = 4.0

    # trend_score: 동별 시계열 — 동·시간대별 forward fill 후 동·시간대별 backward fill
    if "trend_score" in df.columns:
        gk = ["dong_code", "time_zone"] if "time_zone" in df.columns else ["dong_code"]
        df = df.sort_values([*gk, "quarter"])
        df["trend_score"] = df.groupby(gk)["trend_score"].ffill().bfill()
        df["trend_score"] = df["trend_score"].fillna(0).astype(float)
    else:
        df["trend_score"] = 0.0

    # cpi_index 표 분기 단일값 → 분기 정렬 후 ffill/bfill (전국 단일 시계열)
    if not cpi_df.empty:
        df = df.merge(cpi_df, on="quarter", how="left")
    if "cpi_index" in df.columns:
        df = df.sort_values("quarter")
        df["cpi_index"] = df["cpi_index"].ffill().bfill().astype(float)
    else:
        df["cpi_index"] = 0.0

    return df


def build_timeseries(
    df: pd.DataFrame,
    *,
    add_group_features: bool = False,
    train_end_quarter: int | None = None,
) -> pd.DataFrame:
    """집계 데이터에 파생 피처를 추가하고 정렬한다.

    v2 production 피처: time_zone_norm, quarter_num.
    v3 ablation 피처 (선택적): time_sin/cos, quarter_sin/cos, holiday/trend/cpi.
    v5 group_residual: add_group_features=True 시 group_mean / group_relative 추가.

    Parameters
    ----------
    add_group_features : bool, default False
        True 시 (dong_code, time_zone) 그룹 평균 (group_mean) 과 group_relative 컬럼 추가.
    train_end_quarter : int | None, default None
        group_mean 계산 시 quarter <= train_end_quarter row 만 사용 (data leakage 방지).
        None 이면 전체 데이터 사용 (legacy 동작 / 빠른 테스트용).

    참고: v3 ablation 결과 v2 대비 RMSE 8.3배 악화로 production 채택 안 함.
    상세는 docs/abm-simulation/living-pop-forecast-v2-vs-v3-report.md 참조.
    """
    df = df.copy()

    # v2 production: 시간대 정규화 (0~23 → 0~1)
    df["time_zone_norm"] = df["time_zone"].astype(float) / 23.0

    # v2 production: 계절성 (분기 번호 1~4)
    df["quarter_num"] = (df["quarter"] % 10).astype(float)

    # v3 ablation: cyclical encoding (선택적, 비활성)
    df["time_sin"] = np.sin(2 * np.pi * df["time_zone"] / 24)
    df["time_cos"] = np.cos(2 * np.pi * df["time_zone"] / 24)
    df["quarter_sin"] = np.sin(2 * np.pi * df["quarter_num"] / 4)
    df["quarter_cos"] = np.cos(2 * np.pi * df["quarter_num"] / 4)

    # 코로나 시기 가중치 (2020~2021 → 0.5)
    year = df["quarter"] // 10
    df["sample_weight"] = np.where((year >= 2020) & (year <= 2021), 0.5, 1.0)

    # 결측치 처리 (그룹별 선형 보간)
    gk = ["dong_code", "time_zone"]
    for col in ["total_avg_pop", "weekday_avg_pop", "weekend_avg_pop"]:
        df[col] = df.groupby(gk)[col].transform(lambda x: x.interpolate(method="linear", limit_direction="both"))
        df[col] = df.groupby(gk)[col].transform(lambda x: x.ffill().bfill())
        df[col] = df[col].fillna(0).astype(float)

    # 외부 3 피처 join (holiday_count, trend_score, cpi_index)
    df = _enrich_external_features(df)

    # v5 group_residual: 그룹 평균을 explicit feature 로 broadcast
    if add_group_features:
        if train_end_quarter is not None:
            train_mask = df["quarter"] <= train_end_quarter
            if not train_mask.any():
                raise ValueError(f"train_end_quarter={train_end_quarter} 이하 row 가 없습니다. quarter 범위 확인 필요.")
            mean_src = df.loc[train_mask]
        else:
            mean_src = df

        group_mean = (
            mean_src.groupby(["dong_code", "time_zone"])["total_avg_pop"].mean().rename("group_mean").reset_index()
        )
        df = df.merge(group_mean, on=["dong_code", "time_zone"], how="left")
        # 누락 그룹 (train 에 없던 동·시간대) 은 전체 평균으로 fallback — 0 division 방지 안전망
        global_mean = float(df["total_avg_pop"].mean())
        df["group_mean"] = df["group_mean"].fillna(global_mean).astype(float)
        df["group_mean"] = df["group_mean"].replace(0.0, global_mean if global_mean > 0 else 1.0)

        df["group_relative"] = ((df["total_avg_pop"] - df["group_mean"]) / df["group_mean"]).astype(float)

    df = df.sort_values(["dong_code", "time_zone", "quarter"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# 시퀀스 생성
# ---------------------------------------------------------------------------


def prepare_sequences(
    data: pd.DataFrame,
    window_size: int = 8,
    target_col: str = TARGET_COL,
    feature_cols: list[str] | None = None,
    mode: str = "absolute",
) -> tuple[np.ndarray, np.ndarray, MinMaxScaler, MinMaxScaler, np.ndarray]:
    """(dong_code, time_zone) 그룹별 sliding window 시퀀스를 생성한다.

    mode="absolute" (default): y[t] 정규화값을 직접 예측 (기존 v2 동작).
    mode="residual": Δy = y[t] - y[t-1] (잔차) 를 예측. target_scaler 도 잔차 분포로 fit.
                     최종 예측 시 last_value(y[t-1]) 를 더해야 한다.
    mode="group_residual": (y[t] - group_mean) / group_mean (group-relative deviation)
                           을 예측 (option B explicit decomposition). target_scaler 는
                           해당 비율 분포에 fit. 최종 예측: y_pred = group_mean × (1 + r̂).
                           data 에 'group_mean' 컬럼 필요.
    """
    if feature_cols is None:
        feature_cols = [c for c in POP_FEATURES if c in data.columns]

    if target_col not in feature_cols and target_col in data.columns:
        feature_cols = feature_cols + [target_col]
    feature_cols = [c for c in feature_cols if c in data.columns]

    if not feature_cols:
        raise ValueError("사용 가능한 피처 컬럼이 없습니다.")

    if mode not in ("absolute", "residual", "group_residual"):
        raise ValueError(f"mode 는 'absolute' / 'residual' / 'group_residual' 이어야 합니다. (현재: {mode!r})")

    if mode in ("residual", "group_residual") and target_col not in feature_cols:
        raise ValueError(f"{mode} mode 는 target_col 이 feature_cols 에 포함돼야 합니다.")

    if mode == "group_residual" and "group_mean" not in data.columns:
        raise ValueError(
            "group_residual mode 는 'group_mean' 컬럼이 필요합니다. "
            "build_timeseries(..., add_group_features=True) 로 생성하세요."
        )

    target_idx = feature_cols.index(target_col)

    feat_scaler = MinMaxScaler()
    feat_scaler.fit(data[feature_cols].values.astype(np.float32))

    # absolute mode 는 raw y, residual 은 Δy, group_residual 은 (y-group_mean)/group_mean 분포에 fit
    tgt_scaler = MinMaxScaler()
    if mode == "absolute":
        tgt_scaler.fit(data[[target_col]].values.astype(np.float32))
    elif mode == "residual":
        # 잔차 분포 계산: 그룹별 첫 row 제외 후 diff
        deltas: list[np.ndarray] = []
        for (_dong, _tz), group in data.groupby(["dong_code", "time_zone"]):
            if len(group) < 2:
                continue
            vals = group[target_col].values.astype(np.float32)
            deltas.append(np.diff(vals).reshape(-1, 1))
        if not deltas:
            raise ValueError("residual mode: 잔차 분포 계산 실패 — 그룹별 길이 부족")
        all_deltas = np.concatenate(deltas, axis=0)
        tgt_scaler.fit(all_deltas)
    else:  # group_residual
        # (y - group_mean) / group_mean. 0 division 은 build_timeseries 에서 방지됨.
        ratios = (
            (data[target_col].astype(np.float32) - data["group_mean"].astype(np.float32))
            / data["group_mean"].astype(np.float32)
        ).values.reshape(-1, 1)
        if not np.isfinite(ratios).all():
            raise ValueError("group_residual mode: 비유한 ratio 발견 (group_mean 0 의심)")
        tgt_scaler.fit(ratios)

    X_list: list[np.ndarray] = []
    y_list: list[np.ndarray] = []
    w_list: list[float] = []
    has_weight = "sample_weight" in data.columns

    for (_dong, _tz), group in data.groupby(["dong_code", "time_zone"]):
        if len(group) <= window_size:
            continue
        feat_vals = feat_scaler.transform(group[feature_cols].values.astype(np.float32))
        raw_targets = group[target_col].values.astype(np.float32)
        group_means = group["group_mean"].values.astype(np.float32) if mode == "group_residual" else None
        weights = group["sample_weight"].values if has_weight else np.ones(len(group))

        for i in range(len(group) - window_size):
            X_list.append(feat_vals[i : i + window_size])
            if mode == "absolute":
                y_raw = raw_targets[i + window_size]
                y_norm = tgt_scaler.transform([[y_raw]])[0]
                y_list.append(y_norm.astype(np.float32))
            elif mode == "residual":
                y_raw = raw_targets[i + window_size]
                last_raw = raw_targets[i + window_size - 1]
                delta_raw = y_raw - last_raw
                delta_norm = tgt_scaler.transform([[delta_raw]])[0]
                y_list.append(delta_norm.astype(np.float32))
            else:  # group_residual
                y_raw = raw_targets[i + window_size]
                gm = float(group_means[i + window_size])  # type: ignore[index]
                ratio_raw = (y_raw - gm) / gm
                ratio_norm = tgt_scaler.transform([[ratio_raw]])[0]
                y_list.append(ratio_norm.astype(np.float32))
            w_list.append(float(weights[i + window_size]))

    if not X_list:
        raise ValueError(f"시퀀스를 생성할 수 없습니다. window_size={window_size}보다 긴 시계열이 없습니다.")

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    w = np.array(w_list, dtype=np.float32)
    # mark target_idx via attribute for downstream consumers (optional)
    feat_scaler.target_idx_ = int(target_idx)  # type: ignore[attr-defined]
    return X, y, feat_scaler, tgt_scaler, w


# ---------------------------------------------------------------------------
# DataLoader 생성
# ---------------------------------------------------------------------------


def prepare_dataloaders(
    config: dict,
) -> tuple[DataLoader, DataLoader, MinMaxScaler, MinMaxScaler, int]:
    """config 기반으로 학습/검증 DataLoader를 생성한다."""
    db_url = config.get("db_url", DB_URL)
    csv_path = config.get("csv_path", None)
    window_size = config.get("window_size", 8)
    batch_size = config.get("batch_size", 64)
    val_ratio = config.get("val_ratio", 0.2)
    target_col = config.get("target_col", TARGET_COL)
    feature_cols = config.get("feature_cols", None)

    df = load_living_population(db_url=db_url, csv_path=csv_path)
    df = build_timeseries(df)
    logger.info(
        "시계열 구성 완료: %s (%d 동 × 24 시간대)",
        df.shape,
        df["dong_code"].nunique(),
    )

    # 마포구 16동 dong_one_hot 16-dim 입력 피처 추가 (v3: 10 → 26차원)
    df = _add_dong_one_hot(df)
    logger.info("dong_one_hot 16-dim 추가 완료: %s", df.shape)

    if feature_cols is None:
        feature_cols = ALL_FEATURES

    X, y, feat_scaler, tgt_scaler, w = prepare_sequences(
        df, window_size=window_size, target_col=target_col, feature_cols=feature_cols
    )
    logger.info("시퀀스 생성 완료: X=%s, y=%s", X.shape, y.shape)

    input_size = X.shape[2]
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
