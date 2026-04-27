"""TCN imputation 비교 백테스트 결과 분석.

3개 모델(Original/TCN-A/TCN-B)의 백테스트 CSV를 받아 전체·동별·업종별
MAPE/MAE/RMSE/R² 비교 표를 만들고 마크다운 리포트로 저장한다.

사용:
    python -m validation.experiments.tcn.compare_imputed
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from validation.accuracy_metrics import generate_accuracy_report

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = PROJECT_ROOT / "validation" / "results"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "abm-simulation" / "tcn-imputed-comparison-report.md"


def compute_metrics(csv_path: Path) -> dict:
    """백테스트 CSV에서 전체 정확도 지표를 계산한다."""
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    actual = df["actual_annual_sales"].to_numpy()
    pred = df["predicted_annual_sales"].to_numpy()
    rep = generate_accuracy_report(actual, pred)["overall"]
    return {
        "mape": round(rep["mape"], 2),
        "mae": round(rep["mae"], 0),
        "rmse": round(rep["rmse"], 0),
        "r_squared": round(rep["r_squared"], 4),
        "n_samples": len(df),
    }


def build_comparison_table(csvs: dict[str, Path]) -> pd.DataFrame:
    """모델명 → CSV 경로 매핑을 받아 비교 표 DataFrame을 반환."""
    rows = []
    for name, path in csvs.items():
        m = compute_metrics(path)
        rows.append({"model": name, **m})
    return pd.DataFrame(rows)


def build_by_group_table(csvs: dict[str, Path], group_col: str) -> pd.DataFrame:
    """동별/업종별 MAPE 비교 표 (long format)."""
    frames = []
    for name, path in csvs.items():
        df = pd.read_csv(path, encoding="utf-8-sig")
        agg = (
            df.groupby(group_col)
            .apply(
                lambda g: pd.Series(
                    {
                        "mape": float(
                            np.mean(
                                np.abs(g["actual_annual_sales"] - g["predicted_annual_sales"])
                                / g["actual_annual_sales"]
                            )
                            * 100
                        ),
                        "n": len(g),
                    }
                )
            )
            .reset_index()
        )
        agg["model"] = name
        frames.append(agg)
    return pd.concat(frames, ignore_index=True)


def render_report(overall: pd.DataFrame, by_dong: pd.DataFrame, by_ind: pd.DataFrame) -> str:
    """마크다운 리포트 문자열 생성."""
    lines = ["# TCN Imputation 비교 백테스트 리포트", ""]
    lines.append("**생성 시점:** 자동 산출 — `validation/experiments/tcn/compare_imputed.py`")
    lines.append("")
    lines.append("## 전체 정확도")
    lines.append("")
    lines.append(overall.to_markdown(index=False))
    lines.append("")
    lines.append("## 동별 MAPE")
    lines.append("")
    pivot_d = by_dong.pivot(index="dong_name", columns="model", values="mape").round(2)
    lines.append(pivot_d.to_markdown())
    lines.append("")
    lines.append("## 업종별 MAPE")
    lines.append("")
    pivot_i = by_ind.pivot(index="industry_name", columns="model", values="mape").round(2)
    lines.append(pivot_i.to_markdown())
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--original", default=str(RESULTS_DIR / "tcn_backtest_results_seed2026.csv"))
    p.add_argument("--imp-a", default=str(RESULTS_DIR / "tcn_backtest_results_imp_a.csv"))
    p.add_argument("--imp-b", default=str(RESULTS_DIR / "tcn_backtest_results_imp_b.csv"))
    p.add_argument("--out", default=str(DEFAULT_REPORT_PATH))
    args = p.parse_args()

    csvs = {
        "Original": Path(args.original),
        "TCN-A": Path(args.imp_a),
        "TCN-B": Path(args.imp_b),
    }
    for name, path in csvs.items():
        if not path.exists():
            raise FileNotFoundError(f"{name} 결과 CSV 없음: {path}")

    overall = build_comparison_table(csvs)
    by_dong = build_by_group_table(csvs, "dong_name")
    by_ind = build_by_group_table(csvs, "industry_name")

    report = render_report(overall, by_dong, by_ind)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    logger.info("리포트 저장: %s", out)
    print(report)


if __name__ == "__main__":
    main()
