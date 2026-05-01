"""384 그룹별 auto_arima fit + 분기별 forecast.

각 (dong_code, time_zone) 그룹별로 독립 ARIMA(p,d,q) 모델 학습.
M4 competition 표준 baseline 으로 활용.

마포구 16 동 × 24 시간대 = 384 그룹. 분기별 평균 유동인구(total_avg_pop) 시계열을
그룹마다 별도로 fit 하여 단순한 통계 베이스라인을 제공한다.

Usage:
    python -m models.living_pop_forecast.arima_baseline --train
    python -m models.living_pop_forecast.arima_baseline --evaluate

담당: B2 — 수지니
참조: docs/superpowers/plans/2026-04-29-living-pop-mase-target.md (Task 4)
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .data_prep import MAPO_DONG_CODES, TARGET_COL, load_living_population

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
DEFAULT_WEIGHTS_PATH = WEIGHTS_DIR / "arima_baseline_v4.pkl"

# pmdarima.auto_arima 가 발생시키는 ConvergenceWarning 등은 학습 진행을 가린다.
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


# ---------------------------------------------------------------------------
# 그룹 단위 fit / forecast
# ---------------------------------------------------------------------------


def _fit_single_group(
    series: np.ndarray,
    seasonal: bool,
    m: int,
    max_p: int = 3,
    max_q: int = 3,
) -> Any | None:
    """단일 그룹 시계열에 auto_arima fit.

    Returns
    -------
    pmdarima.ARIMA | None
        학습 실패 시 None.
    """
    from pmdarima import auto_arima  # 지연 import — 의존성 부재 시 모듈 import 만 막음

    if len(series) < 4:
        return None
    if not np.isfinite(series).all():
        return None
    # 분산이 0 인 시계열은 ARIMA 의미 없음
    if float(np.nanstd(series)) < 1e-9:
        return None

    # 계절 차분 (m=4) 을 시도하려면 최소 2*m+1 = 9 샘플 권장.
    use_seasonal = bool(seasonal and len(series) >= 2 * m + 1)

    try:
        model = auto_arima(
            series,
            seasonal=use_seasonal,
            m=m if use_seasonal else 1,
            max_p=max_p,
            max_q=max_q,
            max_d=2,
            start_p=0,
            start_q=0,
            stepwise=True,
            suppress_warnings=True,
            error_action="ignore",
            information_criterion="aicc",
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("auto_arima 실패: %s", exc)
        return None
    return model


def _quarter_filter(df: pd.DataFrame, quarters: list[int] | tuple[int, ...]) -> pd.DataFrame:
    if quarters is None:
        return df
    return df[df["quarter"].isin(list(quarters))].copy()


def fit_arima_per_group(
    df: pd.DataFrame,
    train_quarters: list[int] | tuple[int, ...] | None = None,
    seasonal: bool = True,
    m: int = 4,
    target_col: str = TARGET_COL,
    max_p: int = 3,
    max_q: int = 3,
    progress_every: int = 50,
) -> dict[tuple[str, int], Any]:
    """384 그룹별 auto_arima fit.

    Parameters
    ----------
    df : pd.DataFrame
        ``load_living_population()`` 출력. 컬럼: quarter, dong_code, time_zone, total_avg_pop.
    train_quarters : list[int], optional
        학습에 사용할 분기 코드 목록. None 이면 전체 분기 사용.
    seasonal : bool
        계절 ARIMA 사용 여부 (기본 True).
    m : int
        계절 주기 (기본 4 = 분기 → 연 단위).
    target_col : str
        시계열 대상 컬럼.
    max_p, max_q : int
        AR/MA 차수 상한 (속도 제한, 기본 3).
    progress_every : int
        몇 그룹마다 진행 로그를 찍을지.

    Returns
    -------
    dict
        ``{(dong_code, time_zone): pmdarima.ARIMA}`` — fit 실패 그룹은 dict 에서 제외.
    """
    work_df = _quarter_filter(df, train_quarters) if train_quarters else df
    if target_col not in work_df.columns:
        raise ValueError(f"target_col={target_col!r} 컬럼이 DataFrame 에 없습니다.")

    # 그룹 정렬 (재현성)
    work_df = work_df.sort_values(["dong_code", "time_zone", "quarter"]).reset_index(drop=True)

    models: dict[tuple[str, int], Any] = {}
    failed: list[tuple[str, int]] = []
    n_seen = 0
    n_total = work_df.groupby(["dong_code", "time_zone"]).ngroups
    t0 = time.time()

    for (dong, tz), group in work_df.groupby(["dong_code", "time_zone"], sort=True):
        n_seen += 1
        series = group[target_col].to_numpy(dtype=float)

        model = _fit_single_group(series, seasonal=seasonal, m=m, max_p=max_p, max_q=max_q)
        if model is None:
            failed.append((str(dong), int(tz)))
        else:
            models[(str(dong), int(tz))] = model

        if progress_every and n_seen % progress_every == 0:
            elapsed = time.time() - t0
            rate = n_seen / max(elapsed, 1e-9)
            eta = max(n_total - n_seen, 0) / max(rate, 1e-9)
            logger.info(
                "ARIMA fit 진행: %d/%d (성공 %d, 실패 %d) elapsed=%.1fs ETA=%.1fs",
                n_seen,
                n_total,
                len(models),
                len(failed),
                elapsed,
                eta,
            )

    elapsed = time.time() - t0
    logger.info(
        "ARIMA fit 완료: 총 %d 그룹 중 성공 %d, 실패 %d (소요 %.1fs)",
        n_total,
        len(models),
        len(failed),
        elapsed,
    )
    if failed:
        logger.warning("실패 그룹 (앞 5개): %s", failed[:5])
    return models


def forecast_arima(
    models: dict[tuple[str, int], Any],
    dong_code: str,
    time_zone: int,
    n_steps: int = 4,
) -> np.ndarray | None:
    """그룹 모델로 다음 ``n_steps`` 분기 예측.

    Returns
    -------
    np.ndarray | None
        모델 없으면 None — caller 가 fallback (예: lag=1 naive) 처리.
    """
    key = (str(dong_code), int(time_zone))
    model = models.get(key)
    if model is None:
        return None
    try:
        forecast = model.predict(n_periods=int(n_steps))
    except Exception as exc:  # noqa: BLE001
        logger.warning("forecast 실패 (%s, tz=%d): %s", dong_code, time_zone, exc)
        return None
    return np.asarray(forecast, dtype=float)


# ---------------------------------------------------------------------------
# 저장 / 로드
# ---------------------------------------------------------------------------


def save_arima_models(models: dict[tuple[str, int], Any], path: str | Path) -> None:
    """pickle 로 저장. 키 튜플은 pickle 가능."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(models, f)
    logger.info("ARIMA 모델 저장: %s (그룹 %d)", path, len(models))


def load_arima_models(path: str | Path) -> dict[tuple[str, int], Any]:
    """pickle 로드."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"ARIMA 가중치 없음: {path}")
    with open(path, "rb") as f:
        models = pickle.load(f)  # noqa: S301 — 신뢰된 내부 weights 파일
    logger.info("ARIMA 모델 로드: %s (그룹 %d)", path, len(models))
    return models


# ---------------------------------------------------------------------------
# 평가용 메트릭 (validation.metrics 우선, fallback inline)
# ---------------------------------------------------------------------------


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_naive: np.ndarray) -> dict:
    """validation/metrics 모듈 우선, 없으면 inline 계산."""
    try:
        from validation.metrics.forecast_metrics import evaluate_all

        return evaluate_all(y_true, y_pred, y_naive)
    except Exception as exc:  # noqa: BLE001
        logger.warning("validation.metrics 사용 불가 — inline 계산 (%s)", exc)
        eps = 1e-9
        mae = float(np.mean(np.abs(y_true - y_pred)))
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        mape = float(np.mean(np.abs((y_true - y_pred) / np.maximum(np.abs(y_true), eps))) * 100.0)
        smape = float(np.mean(np.abs(y_true - y_pred) / np.maximum((np.abs(y_true) + np.abs(y_pred)) / 2, eps)) * 100.0)
        ss_res = float(np.sum((y_true - y_pred) ** 2))
        ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
        r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
        naive_mae = float(np.mean(np.abs(y_true - y_naive)))
        mase = float(mae / naive_mae) if naive_mae > 0 else float("nan")
        return {
            "MAE": mae,
            "RMSE": rmse,
            "MAPE_pct": mape,
            "sMAPE_pct": smape,
            "R2": r2,
            "MASE": mase,
        }


def _split_quarters_70_15_15(quarters_sorted: list[int]) -> tuple[list[int], list[int], list[int]]:
    """시간순 70/15/15 split."""
    n = len(quarters_sorted)
    n_train = max(1, int(n * 0.70))
    n_val = max(1, int(n * 0.15))
    # test 는 남은 분기 (≥ 1)
    n_test = max(1, n - n_train - n_val)
    # 보정 (rounding)
    if n_train + n_val + n_test > n:
        n_train = n - n_val - n_test
    train = quarters_sorted[:n_train]
    val = quarters_sorted[n_train : n_train + n_val]
    test = quarters_sorted[n_train + n_val : n_train + n_val + n_test]
    return train, val, test


# ---------------------------------------------------------------------------
# CLI 모드 — 학습 / 평가
# ---------------------------------------------------------------------------


def run_train(
    csv_path: str | Path | None = None,
    save_path: str | Path = DEFAULT_WEIGHTS_PATH,
    seasonal: bool = True,
    m: int = 4,
) -> dict:
    """전체 데이터(전체 분기) 로 ARIMA 학습 후 weights 저장."""
    df = load_living_population(csv_path=csv_path)
    df = df[df["dong_code"].isin(MAPO_DONG_CODES)].copy()
    logger.info("학습 데이터: rows=%d, dong=%d, 분기=%d", len(df), df["dong_code"].nunique(), df["quarter"].nunique())

    t0 = time.time()
    models = fit_arima_per_group(df, train_quarters=None, seasonal=seasonal, m=m)
    elapsed = time.time() - t0

    save_arima_models(models, save_path)
    return {
        "n_groups_total": int(df.groupby(["dong_code", "time_zone"]).ngroups),
        "n_groups_fit": len(models),
        "save_path": str(save_path),
        "elapsed_sec": float(elapsed),
        "seasonal": bool(seasonal),
        "m": int(m),
    }


def run_evaluate(
    csv_path: str | Path | None = None,
    seasonal: bool = True,
    m: int = 4,
    target_col: str = TARGET_COL,
) -> dict:
    """train 분기로 fit → test 분기로 평가. naive lag=1 baseline 도 동시 보고."""
    df = load_living_population(csv_path=csv_path)
    df = df[df["dong_code"].isin(MAPO_DONG_CODES)].copy()
    df = df.sort_values(["dong_code", "time_zone", "quarter"]).reset_index(drop=True)

    quarters_sorted = sorted(df["quarter"].unique().tolist())
    train_q, val_q, test_q = _split_quarters_70_15_15(quarters_sorted)
    logger.info(
        "분기 split: train=%d (%d~%d), val=%d (%d~%d), test=%d (%d~%d)",
        len(train_q),
        train_q[0],
        train_q[-1],
        len(val_q),
        val_q[0],
        val_q[-1],
        len(test_q),
        test_q[0],
        test_q[-1],
    )

    # train 분기로 fit (val 은 단순 평가용으로는 사용하지 않음 — Task 5 ensemble 에서 활용)
    t0 = time.time()
    models = fit_arima_per_group(df, train_quarters=train_q, seasonal=seasonal, m=m, target_col=target_col)
    fit_elapsed = time.time() - t0

    # test 분기 각 row 에 대해 forecast — group 별로 모은 뒤 step 별 예측 추출
    y_true_all: list[float] = []
    y_pred_all: list[float] = []
    y_naive_all: list[float] = []
    n_fallback_naive = 0

    for (dong, tz), group in df.groupby(["dong_code", "time_zone"], sort=True):
        group = group.sort_values("quarter").reset_index(drop=True)
        train_block = group[group["quarter"].isin(train_q)]
        test_block = group[group["quarter"].isin(test_q)]
        if len(test_block) == 0 or len(train_block) == 0:
            continue

        # forecast n_steps = len(val_q) + len(test_q) → val 구간 건너뛰고 test 구간만 추출
        n_steps = len(val_q) + len(test_q)
        forecast = forecast_arima(models, str(dong), int(tz), n_steps=n_steps)
        last_train_value = float(train_block[target_col].iloc[-1])

        if forecast is None or len(forecast) < n_steps:
            # fallback: 마지막 학습 값으로 모든 step 채움
            forecast = np.full(n_steps, last_train_value, dtype=float)
            n_fallback_naive += 1

        # test 구간 인덱스: val 직후 → 끝까지
        test_pred = forecast[len(val_q) :][: len(test_block)]
        y_true_all.extend(test_block[target_col].tolist())
        y_pred_all.extend(test_pred.tolist())

        # naive lag=1: 첫 test row 는 train 마지막 값, 이후는 직전 test 실값
        naive_seq = []
        prev = last_train_value
        for actual in test_block[target_col].tolist():
            naive_seq.append(prev)
            prev = actual
        y_naive_all.extend(naive_seq)

    if not y_true_all:
        raise RuntimeError("평가 가능한 그룹이 없습니다.")

    y_true = np.asarray(y_true_all, dtype=float)
    y_pred = np.asarray(y_pred_all, dtype=float)
    y_naive = np.asarray(y_naive_all, dtype=float)

    metrics_arima = _compute_metrics(y_true, y_pred, y_naive)
    metrics_naive = _compute_metrics(y_true, y_naive, y_naive)

    summary = {
        "fit_elapsed_sec": float(fit_elapsed),
        "n_groups_fit": int(len(models)),
        "n_test_points": int(len(y_true)),
        "n_fallback_groups": int(n_fallback_naive),
        "split": {
            "train_quarters": train_q,
            "val_quarters": val_q,
            "test_quarters": test_q,
        },
        "arima": metrics_arima,
        "naive_lag1": metrics_naive,
    }
    return summary


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="ARIMA per-group baseline (D model)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--train", action="store_true", help="384 그룹 ARIMA 학습 후 weights 저장")
    mode.add_argument("--evaluate", action="store_true", help="train fit → test 평가 (학술 metric 출력)")
    parser.add_argument("--csv-path", type=str, default=None, help="living_pop_quarterly.csv 경로")
    parser.add_argument("--save-path", type=str, default=str(DEFAULT_WEIGHTS_PATH))
    parser.add_argument("--no-seasonal", action="store_true", help="계절성(m=4) 비활성")
    parser.add_argument("--m", type=int, default=4, help="계절 주기 (default=4)")
    args = parser.parse_args()

    seasonal = not args.no_seasonal

    if args.train:
        result = run_train(csv_path=args.csv_path, save_path=args.save_path, seasonal=seasonal, m=args.m)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        result = run_evaluate(csv_path=args.csv_path, seasonal=seasonal, m=args.m)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


__all__ = [
    "DEFAULT_WEIGHTS_PATH",
    "fit_arima_per_group",
    "forecast_arima",
    "load_arima_models",
    "run_evaluate",
    "run_train",
    "save_arima_models",
]


if __name__ == "__main__":
    main()
