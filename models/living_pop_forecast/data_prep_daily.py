"""일별 (date × dong × time_zone) 활동량 데이터 prep.

기존 분기 평균 task 의 한계 (naive R² 0.99 → 학습 불가) 를 극복하기 위한 task 변경.
주별 평균도 동일 한계. 일별은 사전 진단 결과 naive_lag7 R² ≈ 0.97 → 학습 여지 있음.

집계 단위: (date, dong_code, time_zone)
  - total_pop: 일별 시간대 활동량 (raw row 1개당 1값, 집계 불필요 / 결측 보간)
  - day_of_week: 0=Mon ~ 6=Sun
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from models.living_pop_forecast.data_prep import MAPO_DONG_CODES

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_RAW_CSV = DATA_DIR / "living_population_dong_mapo.csv"
DEFAULT_CACHE_PARQUET = DATA_DIR / "living_pop_daily.parquet"

# 마포 16동 정수 set — raw csv 의 ADSTRD_CODE_SE 가 int64 이므로 매칭용.
_MAPO_SET_INT = {int(c) for c in MAPO_DONG_CODES}


def load_living_pop_daily_raw(csv_path: Path | None = None) -> pd.DataFrame:
    """raw 일별 csv 로드 + 컬럼 정리 + day_of_week 파생.

    Returns
    -------
    pd.DataFrame
        columns: date, dong_code, time_zone, total_pop, day_of_week
    """
    path = Path(csv_path) if csv_path else DEFAULT_RAW_CSV
    if not path.exists():
        raise FileNotFoundError(f"raw csv 미발견: {path}")

    logger.info("raw 로드: %s", path)
    use_cols = ["STDR_DE_ID", "TMZON_PD_SE", "ADSTRD_CODE_SE", "TOT_LVPOP_CO"]
    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
        usecols=use_cols,
        dtype={
            "STDR_DE_ID": "int64",
            "TMZON_PD_SE": "int16",
            "ADSTRD_CODE_SE": "int64",
            "TOT_LVPOP_CO": "float64",
        },
    )
    logger.info("raw rows: %d", len(df))

    # 마포 16동 외 drop (안전망 — 파일이 마포 전용이지만 검증)
    df = df[df["ADSTRD_CODE_SE"].isin(_MAPO_SET_INT)].copy()

    df = df.rename(
        columns={
            "STDR_DE_ID": "date_int",
            "TMZON_PD_SE": "time_zone",
            "ADSTRD_CODE_SE": "dong_code",
            "TOT_LVPOP_CO": "total_pop",
        }
    )

    df["date"] = pd.to_datetime(df["date_int"].astype(str), format="%Y%m%d")
    df["dong_code"] = df["dong_code"].astype(str)
    df["day_of_week"] = df["date"].dt.dayofweek.astype("int16")
    df = df.drop(columns=["date_int"])

    logger.info(
        "16동 필터 후 rows: %d, date 범위: %s ~ %s",
        len(df),
        df["date"].min().date(),
        df["date"].max().date(),
    )
    return df[["date", "dong_code", "time_zone", "total_pop", "day_of_week"]]


def build_daily_aggregation(raw_df: pd.DataFrame) -> pd.DataFrame:
    """raw → (date, dong_code, time_zone, total_pop, day_of_week).

    raw 가 이미 (date, dong, time_zone) 단위 1 row 이지만 중복 row 가 있을 수
    있어 mean 으로 안전 집계. full grid 로 reindex 후 (dong, time_zone) 그룹
    내 시간순 선형 보간.
    """
    agg = (
        raw_df.groupby(["date", "dong_code", "time_zone"], as_index=False)
        .agg(total_pop=("total_pop", "mean"))
        .sort_values(["dong_code", "time_zone", "date"])
        .reset_index(drop=True)
    )
    logger.info("groupby 직후 rows: %d", len(agg))

    dates = sorted(agg["date"].unique().tolist())
    full_index = pd.MultiIndex.from_product(
        [dates, list(MAPO_DONG_CODES), list(range(24))],
        names=["date", "dong_code", "time_zone"],
    )
    full = agg.set_index(["date", "dong_code", "time_zone"]).reindex(full_index).reset_index()
    n_missing_before = int(full["total_pop"].isna().sum())
    logger.info("full grid rows: %d (그 중 결측: %d)", len(full), n_missing_before)

    gk = ["dong_code", "time_zone"]
    full = full.sort_values([*gk, "date"]).reset_index(drop=True)
    full["total_pop"] = full.groupby(gk)["total_pop"].transform(
        lambda x: x.interpolate(method="linear", limit_direction="both")
    )
    full["total_pop"] = full.groupby(gk)["total_pop"].transform(lambda x: x.ffill().bfill())
    full["total_pop"] = full["total_pop"].fillna(0.0).astype(float)

    full["day_of_week"] = pd.to_datetime(full["date"]).dt.dayofweek.astype("int16")
    full["time_zone"] = full["time_zone"].astype("int16")

    return full[["date", "dong_code", "time_zone", "total_pop", "day_of_week"]].reset_index(drop=True)


def load_living_pop_daily(
    cache_path: Path | None = None,
    raw_csv_path: Path | None = None,
    rebuild: bool = False,
) -> pd.DataFrame:
    """일별 raw 로드 + day_of_week 추가. 캐시 우선.

    Parameters
    ----------
    cache_path : parquet 캐시 경로 (default: data/processed/living_pop_daily.parquet)
    raw_csv_path : raw csv 경로 (default: living_population_dong_mapo.csv)
    rebuild : True 면 캐시 무시, raw → aggregate → 저장.
    """
    cache = Path(cache_path) if cache_path else DEFAULT_CACHE_PARQUET
    if cache.exists() and not rebuild:
        df = pd.read_parquet(cache)
        df["dong_code"] = df["dong_code"].astype(str)
        df["time_zone"] = df["time_zone"].astype("int16")
        df["day_of_week"] = df["day_of_week"].astype("int16")
        df["total_pop"] = df["total_pop"].astype(float)
        df["date"] = pd.to_datetime(df["date"])
        logger.info("캐시 로드: %s (%d rows)", cache, len(df))
        return df

    raw = load_living_pop_daily_raw(raw_csv_path)
    agg = build_daily_aggregation(raw)
    cache.parent.mkdir(parents=True, exist_ok=True)
    agg.to_parquet(cache, index=False)
    logger.info("캐시 저장: %s (%d rows)", cache, len(agg))
    return agg


def split_time_order_per_group(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """각 (dong_code, time_zone) 그룹 내에서 시간순 70/15/15 split.

    이전 evaluate_all.py 의 그룹 순서 기반 split 결함 (그룹 0~70% = train,
    이후 = test → 동일 시점이 train/test 양쪽에 분포) 을 피하기 위해
    *각 그룹 안에서* 진정한 시간순으로 분할.

    Returns
    -------
    (train_df, val_df, test_df)
        각각 입력 컬럼 그대로 + 그룹 내 split 라벨이 붙은 DataFrame.
    """
    if not (0 < train_ratio < 1 and 0 < val_ratio < 1 and train_ratio + val_ratio < 1):
        raise ValueError(f"비율 부적절: train={train_ratio}, val={val_ratio}")

    df = df.sort_values(["dong_code", "time_zone", "date"]).reset_index(drop=True)

    train_pieces: list[pd.DataFrame] = []
    val_pieces: list[pd.DataFrame] = []
    test_pieces: list[pd.DataFrame] = []

    for _, g in df.groupby(["dong_code", "time_zone"], sort=False):
        n = len(g)
        if n < 3:
            train_pieces.append(g)
            continue
        n_train = max(1, int(n * train_ratio))
        n_val = max(1, int(n * val_ratio))
        n_train = min(n_train, n - 2)
        n_val = min(n_val, n - n_train - 1)
        train_pieces.append(g.iloc[:n_train])
        val_pieces.append(g.iloc[n_train : n_train + n_val])
        test_pieces.append(g.iloc[n_train + n_val :])

    train_df = pd.concat(train_pieces, ignore_index=True) if train_pieces else df.iloc[0:0].copy()
    val_df = pd.concat(val_pieces, ignore_index=True) if val_pieces else df.iloc[0:0].copy()
    test_df = pd.concat(test_pieces, ignore_index=True) if test_pieces else df.iloc[0:0].copy()
    return train_df, val_df, test_df


# ---------------------------------------------------------------------------
# 피처 정의 — 일별 task (25 차원)
# ---------------------------------------------------------------------------

DAILY_DONG_FEATURES: list[str] = [f"dong_{dc}" for dc in MAPO_DONG_CODES]
DAILY_DOW_FEATURES: list[str] = [f"dow_{d}" for d in range(7)]
DAILY_FEATURES: list[str] = ["total_pop", "time_zone_norm"] + DAILY_DOW_FEATURES + DAILY_DONG_FEATURES
DAILY_TARGET_COL = "total_pop"


def _add_dong_one_hot_daily(df: pd.DataFrame) -> pd.DataFrame:
    """dong_code → 16개 one-hot 컬럼 추가 (마포 16동만)."""
    df = df.copy()
    for dc in MAPO_DONG_CODES:
        df[f"dong_{dc}"] = (df["dong_code"] == dc).astype(np.float32)
    bad = df[[f"dong_{dc}" for dc in MAPO_DONG_CODES]].sum(axis=1) == 0
    if bool(bad.any()):
        bad_codes = df.loc[bad, "dong_code"].unique().tolist()
        raise ValueError(f"알 수 없는 dong_code: {bad_codes}. 마포구 16동만 지원.")
    return df


def _add_dow_one_hot_daily(df: pd.DataFrame) -> pd.DataFrame:
    """day_of_week (0~6) → 7개 one-hot 컬럼."""
    df = df.copy()
    for d in range(7):
        df[f"dow_{d}"] = (df["day_of_week"].astype(int) == d).astype(np.float32)
    return df


def build_daily_features(df: pd.DataFrame) -> pd.DataFrame:
    """일별 cache → 피처 컬럼 추가 (time_zone_norm + dow_one_hot + dong_one_hot).

    25 차원 (total_pop + time_zone_norm + 7 dow + 16 dong) feature_cols 와 호환.
    """
    df = df.copy()
    df["time_zone_norm"] = df["time_zone"].astype(float) / 23.0
    df = _add_dow_one_hot_daily(df)
    df = _add_dong_one_hot_daily(df)
    df = df.sort_values(["dong_code", "time_zone", "date"]).reset_index(drop=True)
    return df


def prepare_sequences_daily(
    data: pd.DataFrame,
    window_size: int = 14,
    target_col: str = DAILY_TARGET_COL,
    mode: str = "residual_lag7",
    feature_cols: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, MinMaxScaler, MinMaxScaler]:
    """(dong_code, time_zone) 그룹별 sliding window 시퀀스 (일별 task).

    그룹: 16 dongs × 24 hours = 384
    그룹당 시계열: ~2,521 일 → ~2,500 sequences (window=14)
    총: ~960K sequences (mode='residual_lag7' 시 lag=7 거슬러 필요 → 약간 감소)

    피처 (25 차원, default):
        - total_pop (1)
        - time_zone_norm (1, 0~1)
        - dow_0..dow_6 one-hot (7)
        - dong_<code> one-hot (16)

    mode
    ----
    "absolute"
        target = y[t] (정규화). 절대값 학습.
    "residual_lag1"
        target = y[t] - y[t-1]. last_value = y[t-1].
    "residual_lag7"
        target = y[t] - y[t-7]. last_value = y[t-7]. (default — primary baseline)

    Parameters
    ----------
    data : pd.DataFrame
        load_living_pop_daily 출력 + build_daily_features 적용본.
    window_size : int, default 14
    target_col : str, default "total_pop"
    mode : "absolute" | "residual_lag1" | "residual_lag7"
    feature_cols : list[str] | None
        명시 시 그대로 사용. None 이면 DAILY_FEATURES.

    Returns
    -------
    X : np.ndarray (N, W, F) — 정규화된 피처 시퀀스
    y : np.ndarray (N,) — 정규화된 target (mode 별 정의)
    last_value_raw : np.ndarray (N,) — mode 별 last_value (raw, 비정규화)
        - absolute / residual_lag1 → y[t-1]
        - residual_lag7 → y[t-7]
    feat_scaler : MinMaxScaler
    tgt_scaler : MinMaxScaler
    """
    if feature_cols is None:
        feature_cols = list(DAILY_FEATURES)
    if target_col not in feature_cols and target_col in data.columns:
        feature_cols = list(feature_cols) + [target_col]
    feature_cols = [c for c in feature_cols if c in data.columns]
    if not feature_cols:
        raise ValueError("사용 가능한 피처 컬럼이 없습니다.")
    if mode not in ("absolute", "residual_lag1", "residual_lag7"):
        raise ValueError(f"mode 는 'absolute' / 'residual_lag1' / 'residual_lag7' 이어야 합니다. (현재: {mode!r})")
    if mode in ("residual_lag1", "residual_lag7") and target_col not in feature_cols:
        raise ValueError("residual mode 는 target_col 이 feature_cols 에 포함돼야 합니다.")

    target_idx = feature_cols.index(target_col)
    lag_offset = 7 if mode == "residual_lag7" else 1

    if window_size < lag_offset:
        raise ValueError(
            f"window_size ({window_size}) 가 lag_offset ({lag_offset}) 보다 작습니다 — "
            "residual_lag7 은 window 안에 lag=7 시점이 포함돼야 합니다."
        )

    feat_scaler = MinMaxScaler()
    feat_scaler.fit(data[feature_cols].values.astype(np.float32))

    tgt_scaler = MinMaxScaler()
    if mode == "absolute":
        tgt_scaler.fit(data[[target_col]].values.astype(np.float32))
    else:
        deltas: list[np.ndarray] = []
        for (_d, _h), g in data.groupby(["dong_code", "time_zone"]):
            if len(g) <= lag_offset:
                continue
            vals = g.sort_values("date")[target_col].values.astype(np.float32)
            d = vals[lag_offset:] - vals[:-lag_offset]
            deltas.append(d.reshape(-1, 1))
        if not deltas:
            raise ValueError(f"residual mode: 잔차 분포 계산 실패 — 그룹별 길이 부족 (lag={lag_offset})")
        all_deltas = np.concatenate(deltas, axis=0)
        tgt_scaler.fit(all_deltas)

    X_pieces: list[np.ndarray] = []
    raw_target_pieces: list[np.ndarray] = []  # mode 별 (y_raw 또는 delta_raw) 의 t 시점 raw
    last_pieces: list[np.ndarray] = []

    # 그룹별로 vectorized stride sliding window + batch transform → 968K-row scale 에서도 fast.
    for (_d, _h), group in data.groupby(["dong_code", "time_zone"], sort=True):
        if len(group) <= window_size:
            continue
        group_sorted = group.sort_values("date").reset_index(drop=True)
        feat_raw = group_sorted[feature_cols].values.astype(np.float32)
        feat_vals = feat_scaler.transform(feat_raw)
        raw_targets = group_sorted[target_col].values.astype(np.float32)
        n = len(group_sorted)
        n_seq = n - window_size

        # X 슬라이딩 윈도우 (n_seq, W, F) — np.lib.stride_tricks 은 뷰 → 한 번 copy.
        # 단순 구현: index 배열로 fancy index.
        idx = np.arange(window_size)[None, :] + np.arange(n_seq)[:, None]  # (n_seq, W)
        X_group = feat_vals[idx]  # (n_seq, W, F)
        X_pieces.append(X_group)

        y_raw = raw_targets[window_size : window_size + n_seq]  # (n_seq,)
        if mode == "absolute":
            raw_target_pieces.append(y_raw)
            last_raw = raw_targets[window_size - 1 : window_size - 1 + n_seq]
        elif mode == "residual_lag1":
            last_raw = raw_targets[window_size - 1 : window_size - 1 + n_seq]
            raw_target_pieces.append(y_raw - last_raw)
        else:  # residual_lag7
            last_raw = raw_targets[window_size - 7 : window_size - 7 + n_seq]
            raw_target_pieces.append(y_raw - last_raw)
        last_pieces.append(last_raw)

    if not X_pieces:
        raise ValueError(f"시퀀스 생성 실패: window_size={window_size} 보다 긴 그룹 없음")

    X = np.concatenate(X_pieces, axis=0).astype(np.float32)
    raw_target_concat = np.concatenate(raw_target_pieces, axis=0).astype(np.float32)
    last_value_raw = np.concatenate(last_pieces, axis=0).astype(np.float32)

    # 한 번에 정규화 (vectorized — 매우 빠름). shape (N, 1) — TCN 출력과 일치.
    y = tgt_scaler.transform(raw_target_concat.reshape(-1, 1)).astype(np.float32)

    feat_scaler.target_idx_ = int(target_idx)  # type: ignore[attr-defined]
    return X, y, last_value_raw, feat_scaler, tgt_scaler


def _summary(df: pd.DataFrame) -> dict:
    """캐시 진단 요약."""
    return {
        "rows": int(len(df)),
        "n_dongs": int(df["dong_code"].nunique()),
        "n_dates": int(df["date"].nunique()),
        "date_min": str(pd.to_datetime(df["date"]).min().date()),
        "date_max": str(pd.to_datetime(df["date"]).max().date()),
        "n_hours": int(df["time_zone"].nunique()),
        "total_pop_zero": int((df["total_pop"] == 0.0).sum()),
        "total_pop_nan": int(df["total_pop"].isna().sum()),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="(date × dong × time_zone) 일별 cache 생성")
    parser.add_argument("--rebuild", action="store_true", help="raw → 재집계 + 캐시 덮어쓰기")
    parser.add_argument("--cache", type=str, default=None, help=f"캐시 경로 (default: {DEFAULT_CACHE_PARQUET})")
    parser.add_argument("--raw", type=str, default=None, help=f"raw csv 경로 (default: {DEFAULT_RAW_CSV})")
    args = parser.parse_args(argv)

    df = load_living_pop_daily(
        cache_path=Path(args.cache) if args.cache else None,
        raw_csv_path=Path(args.raw) if args.raw else None,
        rebuild=args.rebuild,
    )
    summary = _summary(df)
    print("\n=== daily cache summary ===")
    for k, v in summary.items():
        print(f"  {k:20s}: {v}")
    expected = summary["n_dongs"] * summary["n_dates"] * 24
    print(f"  expected_rows (16*D*24): {expected}")
    print(f"  match: {summary['rows'] == expected}")
    return 0


__all__ = [
    "DAILY_DONG_FEATURES",
    "DAILY_DOW_FEATURES",
    "DAILY_FEATURES",
    "DAILY_TARGET_COL",
    "DEFAULT_CACHE_PARQUET",
    "DEFAULT_RAW_CSV",
    "build_daily_aggregation",
    "build_daily_features",
    "load_living_pop_daily",
    "load_living_pop_daily_raw",
    "main",
    "prepare_sequences_daily",
    "split_time_order_per_group",
]


if __name__ == "__main__":
    raise SystemExit(main())
