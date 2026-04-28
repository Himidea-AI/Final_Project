"""LODO 16-fold cross-validation — D 모델 일반화 검증.

각 동을 test로 빼고 나머지 15동으로 학습 → 16번 반복.
산출: 동별 test MAPE/MAE/RMSE.

사용:
    python -m validation.experiments.living_pop.lodo_validation
    python -m validation.experiments.living_pop.lodo_validation --epochs 50 --seed 2026
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = PROJECT_ROOT / "validation" / "results"


# ---------------------------------------------------------------------------
# MAPO_DONG_CODES (D-Task 1 미완 시 fallback)
# ---------------------------------------------------------------------------

try:
    from models.living_pop_forecast.data_prep import MAPO_DONG_CODES

    _SOURCE = "models.living_pop_forecast.data_prep"
except ImportError:
    MAPO_DONG_CODES = (
        "11440555",
        "11440565",
        "11440585",
        "11440590",
        "11440600",
        "11440610",
        "11440630",
        "11440655",
        "11440660",
        "11440680",
        "11440690",
        "11440700",
        "11440710",
        "11440720",
        "11440730",
        "11440740",
    )
    _SOURCE = "fallback (D-Task 1 미완)"


# ---------------------------------------------------------------------------
# LODO 실행
# ---------------------------------------------------------------------------


def run_lodo(
    epochs: int = 50,
    patience: int = 10,
    seed: int = 2026,
    version: str = "v2",
) -> pd.DataFrame:
    """16동 leave-one-out cross-validation.

    Parameters
    ----------
    version : str
        "v2" 또는 "v3" — train cfg 와 결과 CSV 파일명에 반영.

    Returns
    -------
    pd.DataFrame
        columns = [fold, holdout_dong, train_loss, val_loss, test_loss_holdout,
                   epochs_trained, elapsed_s]
    """
    try:
        from models.living_pop_forecast.train import train as train_model
    except ImportError as exc:
        raise RuntimeError(
            f"models.living_pop_forecast.train.train() 미사용 가능. D-Task 2 완료 후 재시도: {exc}"
        ) from exc

    rows: list[dict] = []
    t0 = time.time()
    for i, holdout_dong in enumerate(MAPO_DONG_CODES, 1):
        logger.info("[LODO %d/16] holdout=%s 시작", i, holdout_dong)
        cfg = {
            "exclude_dongs": [holdout_dong],
            "save_suffix": f"lodo_{holdout_dong}",
            "epochs": epochs,
            "patience": patience,
            "seed": seed,
            "version": version,
        }
        t_fold = time.time()

        try:
            result = train_model(cfg)
        except TypeError as exc:
            # train_model 시그니처 미지원 — D-Task 2 미완 신호
            raise RuntimeError(f"train_model() 가 cfg dict 시그니처 미지원. D-Task 2 완료 필요: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            # OOM, DB 연결 실패, ValueError 등 fold 단위 격리
            logger.error(
                "[LODO %d/16] %s 실패: %s. NaN 처리 후 다음 fold 진행.",
                i,
                holdout_dong,
                exc,
            )
            rows.append(
                {
                    "fold": i,
                    "holdout_dong": holdout_dong,
                    "train_loss": float("nan"),
                    "val_loss": float("nan"),
                    "test_loss_holdout": float("nan"),
                    "epochs_trained": 0,
                    "elapsed_s": time.time() - t_fold,
                    "error": str(exc)[:200],
                }
            )
            continue

        elapsed = time.time() - t_fold

        rows.append(
            {
                "fold": i,
                "holdout_dong": holdout_dong,
                "train_loss": float(result.get("train_loss", float("nan"))),
                "val_loss": float(result.get("val_loss", float("nan"))),
                "test_loss_holdout": float(result.get("test_loss", float("nan"))),
                "epochs_trained": int(result.get("epochs", 0)),
                "elapsed_s": elapsed,
            }
        )
        logger.info(
            "[LODO %d/16] %s: test_loss=%.6f (epochs=%d, %.0fs)",
            i,
            holdout_dong,
            rows[-1]["test_loss_holdout"],
            rows[-1]["epochs_trained"],
            elapsed,
        )

    df = pd.DataFrame(rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_csv = RESULTS_DIR / f"living_pop_lodo_{version}.csv"
    df.to_csv(results_csv, index=False, encoding="utf-8-sig")
    logger.info("LODO 완료: %s (%.0fs)", results_csv, time.time() - t0)
    return df


def summarize(df: pd.DataFrame) -> dict:
    """LODO 결과 요약 dict. NaN fold (실패) 는 통계에서 제외."""
    valid = df.dropna(subset=["test_loss_holdout"])
    n_failed = len(df) - len(valid)
    if len(valid) == 0:
        return {"n_folds": len(df), "n_failed": n_failed, "all_failed": True}

    test_losses = valid["test_loss_holdout"]
    summary = {
        "n_folds": len(df),
        "n_succeeded": len(valid),
        "n_failed": n_failed,
        "mean_test_loss": float(test_losses.mean()),
        "std_test_loss": float(test_losses.std()),
        "min_test_loss": float(test_losses.min()),
        "max_test_loss": float(test_losses.max()),
        "best_dong": valid.loc[test_losses.idxmin(), "holdout_dong"],
        "worst_dong": valid.loc[test_losses.idxmax(), "holdout_dong"],
        "cv_coefficient": float(test_losses.std() / max(abs(test_losses.mean()), 1e-9)),
    }
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="LODO 16-fold cross-validation")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--version", type=str, default="v2", help="가중치 버전 태그 (v2/v3)")
    args = parser.parse_args()

    logger.info("MAPO_DONG_CODES source: %s (version=%s)", _SOURCE, args.version)
    df = run_lodo(
        epochs=args.epochs,
        patience=args.patience,
        seed=args.seed,
        version=args.version,
    )
    summary = summarize(df)

    print("\n=== LODO 16-fold 요약 ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n=== 동별 test_loss ===")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
