"""(동 × 요일 × 시간대) 분기 평균 활동량 데이터 prep.

기존 data_prep.py 의 분기 평균 (동×시간대) 단위 → (동×요일×시간대) 단위로 task 변경.
변동성 ↑ → 모델 학습 가치 ↑.
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
DEFAULT_CACHE_CSV = DATA_DIR / "living_pop_dow_hour_quarterly.csv"

# 마포 16동만 — 그 외 dong_code row 는 drop.
_MAPO_SET = {int(c) for c in MAPO_DONG_CODES}


def load_living_population_raw(csv_path: Path | None = None) -> pd.DataFrame:
    """raw 일별 csv 로드 + 컬럼 정리 + day_of_week / quarter 파생.

    Returns
    -------
    pd.DataFrame
        columns: date, time_zone, dong_code, total_pop, day_of_week, quarter
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
    df = df[df["ADSTRD_CODE_SE"].isin(_MAPO_SET)].copy()

    df = df.rename(
        columns={
            "STDR_DE_ID": "date_int",
            "TMZON_PD_SE": "time_zone",
            "ADSTRD_CODE_SE": "dong_code",
            "TOT_LVPOP_CO": "total_pop",
        }
    )

    # date_int (YYYYMMDD) → datetime
    df["date"] = pd.to_datetime(df["date_int"].astype(str), format="%Y%m%d")
    df["dong_code"] = df["dong_code"].astype(str)

    # day_of_week: 0=Mon ~ 6=Sun
    df["day_of_week"] = df["date"].dt.dayofweek.astype("int16")

    # quarter = year*10 + Q (예: 20241)
    df["quarter"] = (df["date"].dt.year * 10 + df["date"].dt.quarter).astype("int32")

    df = df.drop(columns=["date_int"])
    logger.info("16동 필터 후 rows: %d, 분기 범위: %d ~ %d", len(df), df["quarter"].min(), df["quarter"].max())
    return df


def build_dow_hour_aggregation(df: pd.DataFrame) -> pd.DataFrame:
    """(dong_code, quarter, day_of_week, time_zone) 분기 평균 집계 + 결측 그룹 보간.

    Parameters
    ----------
    df : pd.DataFrame
        load_living_population_raw 의 출력.

    Returns
    -------
    pd.DataFrame
        columns: dong_code, quarter, day_of_week, time_zone, mean_pop
        총 16 × 7 × 24 × n_quarters row (결측은 보간).
    """
    agg = (
        df.groupby(["dong_code", "quarter", "day_of_week", "time_zone"], as_index=False)
        .agg(mean_pop=("total_pop", "mean"))
        .sort_values(["dong_code", "day_of_week", "time_zone", "quarter"])
        .reset_index(drop=True)
    )
    logger.info("groupby 직후 rows: %d", len(agg))

    # 결측 그룹 (특정 분기에 해당 dong/dow/hour 조합 데이터 0) → 전체 grid reindex
    quarters = sorted(agg["quarter"].unique().tolist())
    full_index = pd.MultiIndex.from_product(
        [list(MAPO_DONG_CODES), quarters, list(range(7)), list(range(24))],
        names=["dong_code", "quarter", "day_of_week", "time_zone"],
    )
    full = agg.set_index(["dong_code", "quarter", "day_of_week", "time_zone"]).reindex(full_index).reset_index()
    n_missing = int(full["mean_pop"].isna().sum())
    logger.info("full grid rows: %d (그 중 결측: %d)", len(full), n_missing)

    # (dong_code, day_of_week, time_zone) 그룹 내 quarter 순 선형 보간 → ffill/bfill → 0
    gk = ["dong_code", "day_of_week", "time_zone"]
    full = full.sort_values([*gk, "quarter"]).reset_index(drop=True)
    full["mean_pop"] = full.groupby(gk)["mean_pop"].transform(
        lambda x: x.interpolate(method="linear", limit_direction="both")
    )
    full["mean_pop"] = full.groupby(gk)["mean_pop"].transform(lambda x: x.ffill().bfill())
    full["mean_pop"] = full["mean_pop"].fillna(0.0).astype(float)

    full["day_of_week"] = full["day_of_week"].astype("int16")
    full["time_zone"] = full["time_zone"].astype("int16")
    full["quarter"] = full["quarter"].astype("int32")

    return full[["dong_code", "quarter", "day_of_week", "time_zone", "mean_pop"]].reset_index(drop=True)


def load_dow_hour_cache(
    cache_path: Path | None = None,
    raw_csv_path: Path | None = None,
    rebuild: bool = False,
) -> pd.DataFrame:
    """캐시 우선 로드, 없거나 rebuild=True 면 raw → build → 저장."""
    cache = Path(cache_path) if cache_path else DEFAULT_CACHE_CSV
    if cache.exists() and not rebuild:
        df = pd.read_csv(cache, dtype={"dong_code": str})
        df["quarter"] = df["quarter"].astype("int32")
        df["day_of_week"] = df["day_of_week"].astype("int16")
        df["time_zone"] = df["time_zone"].astype("int16")
        df["mean_pop"] = df["mean_pop"].astype(float)
        logger.info("캐시 로드: %s (%d rows)", cache, len(df))
        return df

    raw = load_living_population_raw(raw_csv_path)
    agg = build_dow_hour_aggregation(raw)
    cache.parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(cache, index=False)
    logger.info("캐시 저장: %s (%d rows)", cache, len(agg))
    return agg


def _add_dong_one_hot_dow_hour(df: pd.DataFrame) -> pd.DataFrame:
    """dong_code → 16개 one-hot 컬럼 추가 (dow_hour 전용 — 마포 16동만)."""
    df = df.copy()
    for dc in MAPO_DONG_CODES:
        df[f"dong_{dc}"] = (df["dong_code"] == dc).astype(np.float32)
    bad = df[[f"dong_{dc}" for dc in MAPO_DONG_CODES]].sum(axis=1) == 0
    if bool(bad.any()):
        bad_codes = df.loc[bad, "dong_code"].unique().tolist()
        raise ValueError(f"알 수 없는 dong_code: {bad_codes}. 마포구 16동만 지원.")
    return df


def _add_dow_one_hot(df: pd.DataFrame) -> pd.DataFrame:
    """day_of_week (0~6) → 7개 one-hot 컬럼 추가."""
    df = df.copy()
    for d in range(7):
        df[f"dow_{d}"] = (df["day_of_week"].astype(int) == d).astype(np.float32)
    return df


# 피처 정의 — dow_hour task 전용 (25 차원)
DOW_HOUR_DONG_FEATURES: list[str] = [f"dong_{dc}" for dc in MAPO_DONG_CODES]
DOW_HOUR_DOW_FEATURES: list[str] = [f"dow_{d}" for d in range(7)]
DOW_HOUR_FEATURES: list[str] = ["mean_pop", "time_zone_norm"] + DOW_HOUR_DOW_FEATURES + DOW_HOUR_DONG_FEATURES
DOW_HOUR_TARGET_COL = "mean_pop"


def prepare_sequences_dow_hour(
    data: pd.DataFrame,
    window_size: int = 8,
    target_col: str = DOW_HOUR_TARGET_COL,
    mode: str = "absolute",
    feature_cols: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, MinMaxScaler, MinMaxScaler]:
    """(dong, dow, hour) 그룹별 sliding window 시퀀스.

    그룹: 16 dongs × 7 dow × 24 hours = 2,688
    그룹당 시계열: 29 quarters → 21 sequences (window=8)
    총: ~56,448 sequences

    피처 (25 차원, default):
        - mean_pop (1)
        - time_zone_norm (1, 0~1)
        - dow_0..dow_6 one-hot (7)
        - dong_<code> one-hot (16)

    mode
    ----
    "absolute"
        target = y[t] (정규화). 기존 v2 동작.
    "residual"
        target = y[t] - y[t-1] (Δy). target_scaler 도 Δy 분포에 fit.
        최종 예측 시 last_value(y[t-1]) + Δŷ 로 합산.

    Parameters
    ----------
    data : pd.DataFrame
        load_dow_hour_cache 출력 + time_zone_norm + dong_one_hot + dow_one_hot 피처 추가본.
    window_size : int, default 8
    target_col : str, default "mean_pop"
    mode : "absolute" | "residual"
    feature_cols : list[str] | None
        명시 시 그대로 사용. None 이면 DOW_HOUR_FEATURES.

    Returns
    -------
    X : np.ndarray (N, W, F) — 정규화된 피처 시퀀스
    y : np.ndarray (N,) — 정규화된 target (mode 별 정의)
    feat_scaler : MinMaxScaler
    tgt_scaler : MinMaxScaler
    """
    if feature_cols is None:
        feature_cols = list(DOW_HOUR_FEATURES)
    if target_col not in feature_cols and target_col in data.columns:
        feature_cols = list(feature_cols) + [target_col]
    feature_cols = [c for c in feature_cols if c in data.columns]
    if not feature_cols:
        raise ValueError("사용 가능한 피처 컬럼이 없습니다.")
    if mode not in ("absolute", "residual"):
        raise ValueError(f"mode 는 'absolute' / 'residual' 이어야 합니다. (현재: {mode!r})")
    if mode == "residual" and target_col not in feature_cols:
        raise ValueError("residual mode 는 target_col 이 feature_cols 에 포함돼야 합니다.")

    target_idx = feature_cols.index(target_col)

    feat_scaler = MinMaxScaler()
    feat_scaler.fit(data[feature_cols].values.astype(np.float32))

    tgt_scaler = MinMaxScaler()
    if mode == "absolute":
        tgt_scaler.fit(data[[target_col]].values.astype(np.float32))
    else:  # residual
        deltas: list[np.ndarray] = []
        for (_d, _dw, _h), g in data.groupby(["dong_code", "day_of_week", "time_zone"]):
            if len(g) < 2:
                continue
            vals = g.sort_values("quarter")[target_col].values.astype(np.float32)
            deltas.append(np.diff(vals).reshape(-1, 1))
        if not deltas:
            raise ValueError("residual mode: 잔차 분포 계산 실패 — 그룹별 길이 부족")
        all_deltas = np.concatenate(deltas, axis=0)
        tgt_scaler.fit(all_deltas)

    X_list: list[np.ndarray] = []
    y_list: list[np.ndarray] = []

    for (_d, _dw, _h), group in data.groupby(["dong_code", "day_of_week", "time_zone"], sort=True):
        if len(group) <= window_size:
            continue
        group_sorted = group.sort_values("quarter").reset_index(drop=True)
        feat_vals = feat_scaler.transform(group_sorted[feature_cols].values.astype(np.float32))
        raw_targets = group_sorted[target_col].values.astype(np.float32)
        for i in range(len(group_sorted) - window_size):
            X_list.append(feat_vals[i : i + window_size])
            if mode == "absolute":
                y_raw = raw_targets[i + window_size]
                y_norm = tgt_scaler.transform([[y_raw]])[0]
                y_list.append(y_norm.astype(np.float32))
            else:  # residual
                y_raw = raw_targets[i + window_size]
                last_raw = raw_targets[i + window_size - 1]
                delta = y_raw - last_raw
                delta_norm = tgt_scaler.transform([[delta]])[0]
                y_list.append(delta_norm.astype(np.float32))

    if not X_list:
        raise ValueError(f"시퀀스 생성 실패: window_size={window_size} 보다 긴 그룹 없음")

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    feat_scaler.target_idx_ = int(target_idx)  # type: ignore[attr-defined]
    return X, y, feat_scaler, tgt_scaler


def build_dow_hour_features(df: pd.DataFrame) -> pd.DataFrame:
    """집계 캐시 → 피처 컬럼 (time_zone_norm + dow_one_hot + dong_one_hot) 추가.

    25 차원 (mean_pop + time_zone_norm + 7 dow + 16 dong) feature_cols 와 호환.
    """
    df = df.copy()
    df["time_zone_norm"] = df["time_zone"].astype(float) / 23.0
    df = _add_dow_one_hot(df)
    df = _add_dong_one_hot_dow_hour(df)
    df = df.sort_values(["dong_code", "day_of_week", "time_zone", "quarter"]).reset_index(drop=True)
    return df


def _summary(df: pd.DataFrame) -> dict:
    """캐시 진단 요약."""
    return {
        "rows": int(len(df)),
        "n_dongs": int(df["dong_code"].nunique()),
        "n_quarters": int(df["quarter"].nunique()),
        "quarter_min": int(df["quarter"].min()),
        "quarter_max": int(df["quarter"].max()),
        "n_dow": int(df["day_of_week"].nunique()),
        "n_hours": int(df["time_zone"].nunique()),
        "mean_pop_zero_groups": int((df["mean_pop"] == 0.0).sum()),
        "mean_pop_nan": int(df["mean_pop"].isna().sum()),
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="(동×요일×시간대) 분기 평균 cache 생성")
    parser.add_argument("--rebuild", action="store_true", help="raw → 재집계 + 캐시 덮어쓰기")
    parser.add_argument("--cache", type=str, default=None, help=f"캐시 경로 (default: {DEFAULT_CACHE_CSV})")
    parser.add_argument("--raw", type=str, default=None, help=f"raw csv 경로 (default: {DEFAULT_RAW_CSV})")
    args = parser.parse_args(argv)

    df = load_dow_hour_cache(
        cache_path=Path(args.cache) if args.cache else None,
        raw_csv_path=Path(args.raw) if args.raw else None,
        rebuild=args.rebuild,
    )
    summary = _summary(df)
    print("\n=== dow_hour cache summary ===")
    for k, v in summary.items():
        print(f"  {k:24s}: {v}")
    expected = summary["n_dongs"] * summary["n_quarters"] * 7 * 24
    print(f"  expected_rows (16*7*24*Q): {expected}")
    print(f"  match: {summary['rows'] == expected}")
    return 0


__all__ = [
    "DEFAULT_CACHE_CSV",
    "DEFAULT_RAW_CSV",
    "DOW_HOUR_DONG_FEATURES",
    "DOW_HOUR_DOW_FEATURES",
    "DOW_HOUR_FEATURES",
    "DOW_HOUR_TARGET_COL",
    "build_dow_hour_aggregation",
    "build_dow_hour_features",
    "load_dow_hour_cache",
    "load_living_population_raw",
    "main",
    "prepare_sequences_dow_hour",
]


if __name__ == "__main__":
    raise SystemExit(main())
