"""
피처 상관관계 분석 스크립트 — TCN 고도화 Stage 2 피처 선정용

실행:
    python -m scripts.feature_analysis
    python -m scripts.feature_analysis --dong_prefix 11440  # 마포구만
    python -m scripts.feature_analysis --threshold 0.1

출력:
    - 히트맵 이미지: data/processed/feature_correlation_heatmap.png
    - 터미널: |상관계수| < threshold 피처 목록 (제거 후보)

담당: B2 — 수지니
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from models.lstm_forecast.data_prep import (  # noqa: E402
    ALL_FEATURES,
    build_timeseries,
    load_sales_data,
    load_store_data,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

# 상관관계 분석에서 제외할 비피처 컬럼
_EXCLUDE_COLS = {"sample_weight", "dong_code", "industry_code", "quarter", "dong_name"}


def compute_correlations(
    ts: pd.DataFrame,
    target_col: str = "monthly_sales",
    feature_cols: list[str] | None = None,
) -> tuple[pd.Series, pd.Series]:
    """Pearson 동시점 + lag-1 상관관계 계산.

    Returns
    -------
    pearson_corr : pd.Series   index=피처명, 값=상관계수
    lag1_corr    : pd.Series   index=피처명, 값=lag-1 상관계수
    """
    if feature_cols is None:
        feature_cols = [c for c in ALL_FEATURES if c in ts.columns and c != target_col]

    feature_cols = [c for c in feature_cols if c in ts.columns and c not in _EXCLUDE_COLS]

    if target_col not in ts.columns:
        raise ValueError(f"target_col '{target_col}'이 DataFrame에 없습니다.")

    # 1) 동시점 Pearson
    pearson_corr = ts[feature_cols].corrwith(ts[target_col])

    # 2) lag-1 상관관계: t-1 피처 vs t 타겟
    # (dong_code, industry_code) 그룹별로 1분기 shift
    ts_shifted = ts.copy()
    ts_shifted[feature_cols] = ts.groupby(["dong_code", "industry_code"])[feature_cols].shift(1)
    ts_shifted = ts_shifted.dropna(subset=feature_cols + [target_col])
    lag1_corr = ts_shifted[feature_cols].corrwith(ts_shifted[target_col])

    return pearson_corr, lag1_corr


def plot_heatmap(
    pearson_corr: pd.Series,
    lag1_corr: pd.Series,
    output_path: Path,
    threshold: float = 0.1,
) -> None:
    """Pearson + lag-1 상관계수 히트맵 저장."""
    df_plot = pd.DataFrame({"Pearson (동시점)": pearson_corr, "lag-1 상관관계": lag1_corr}).sort_values(
        "Pearson (동시점)", ascending=False
    )

    fig, ax = plt.subplots(figsize=(4, max(8, len(df_plot) * 0.35)))
    sns.heatmap(
        df_plot,
        annot=True,
        fmt=".2f",
        cmap="RdYlGn",
        center=0,
        vmin=-1,
        vmax=1,
        ax=ax,
        linewidths=0.3,
    )
    ax.set_title(f"피처 상관관계 히트맵 (|threshold|={threshold})")
    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("히트맵 저장: %s", output_path)


def print_removal_candidates(
    pearson_corr: pd.Series,
    lag1_corr: pd.Series,
    threshold: float = 0.1,
) -> list[str]:
    """두 분석 모두 |상관계수| < threshold인 제거 후보 출력."""
    both_low = [
        feat
        for feat in pearson_corr.index
        if abs(pearson_corr[feat]) < threshold and abs(lag1_corr.get(feat, 0)) < threshold
    ]

    print("\n" + "=" * 60)
    print(f"제거 후보 피처 (|Pearson| < {threshold} AND |lag-1| < {threshold})")
    print("=" * 60)
    if both_low:
        for feat in both_low:
            print(f"  {feat:30s}  Pearson={pearson_corr[feat]:+.3f}  lag1={lag1_corr.get(feat, 0):+.3f}")
    else:
        print("  없음 (모든 피처가 threshold 이상)")

    print("\n전체 피처 상관계수:")
    for feat in pearson_corr.sort_values(key=abs, ascending=False).index:
        flag = " ← 제거 후보" if feat in both_low else ""
        print(f"  {feat:30s}  Pearson={pearson_corr[feat]:+.3f}  lag1={lag1_corr.get(feat, 0):+.3f}{flag}")

    return both_low


def main() -> None:
    parser = argparse.ArgumentParser(description="TCN 피처 상관관계 분석")
    parser.add_argument("--dong_prefix", default=None, help="행정동 코드 접두사 (예: 11440=마포구)")
    parser.add_argument("--threshold", type=float, default=0.1, help="제거 후보 임계값 (기본 0.1)")
    args = parser.parse_args()

    logger.info("데이터 로드 중 (dong_prefix=%s) ...", args.dong_prefix)
    sales_df = load_sales_data(dong_prefix=args.dong_prefix)
    store_df = load_store_data(dong_prefix=args.dong_prefix)

    logger.info("시계열 구성 중 ...")
    ts = build_timeseries(sales_df, store_df)
    logger.info("시계열 크기: %s", ts.shape)

    pearson_corr, lag1_corr = compute_correlations(ts)

    output_path = OUTPUT_DIR / "feature_correlation_heatmap.png"
    plot_heatmap(pearson_corr, lag1_corr, output_path, threshold=args.threshold)

    removal_candidates = print_removal_candidates(pearson_corr, lag1_corr, threshold=args.threshold)

    print(f"\n총 피처 수: {len(pearson_corr)}")
    print(f"제거 후보 수: {len(removal_candidates)}")
    print(f"잔류 피처 수 (예상): {len(pearson_corr) - len(removal_candidates)}")


if __name__ == "__main__":
    main()
