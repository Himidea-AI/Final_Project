"""Sprint 3: 외삽 threshold 1.8 -> 2.5 완화 + confidence 재계산.

이미 학습된 mean/std 보존 (imputed_mapo_v4_detail.csv).
detect_extrapolation_cells / calculate_confidence 만 재호출 후 CSV 갱신.

Note: detail CSV 에서 monthly_sales 는 의도적으로 제외됨 (reverse_engineer_sales_v4.py line 331).
monthly_sales std proxy = weekday_sales std + weekend_sales std (raking 후 monthly = weekday + weekend).
monthly_sales ci_width_ratio proxy = weekday_sales ci_width_ratio (weekday 가 월 매출의 주 요인).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

WIDE_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4.csv"
DETAIL_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4_detail.csv"

NEW_THRESHOLD = 2.5
EXTRAPOLATION_PENALTY_TARGET = 0.4
MNAR_WAPE_FOR_BASE = 21.23  # Sprint 1 Task 7 audit 결과 사용


def main() -> None:
    print("=== Sprint 3: confidence recalc (threshold 1.8 -> 2.5) ===")

    wide = pd.read_csv(WIDE_CSV)
    detail = pd.read_csv(DETAIL_CSV)

    # monthly_sales 는 detail CSV 에서 의도적으로 제외됨 (reverse_engineer_sales_v4.py:331).
    # proxy: monthly_sales std = weekday_sales std + weekend_sales std (raking 후 monthly = weekday + weekend)
    wday = (
        detail[detail["column_name"] == "weekday_sales"][
            ["quarter", "dong_code", "industry_code", "std", "ci_width_ratio"]
        ]
        .rename(columns={"std": "wday_std", "ci_width_ratio": "monthly_ci_ratio"})
        .copy()
    )
    wend = (
        detail[detail["column_name"] == "weekend_sales"][["quarter", "dong_code", "industry_code", "std"]]
        .rename(columns={"std": "wend_std"})
        .copy()
    )
    std_df = wday.merge(wend, on=["quarter", "dong_code", "industry_code"], how="outer")
    std_df["monthly_std"] = std_df["wday_std"].fillna(0) + std_df["wend_std"].fillna(0)

    wide = wide.merge(
        std_df[["quarter", "dong_code", "industry_code", "monthly_std", "monthly_ci_ratio"]],
        on=["quarter", "dong_code", "industry_code"],
        how="left",
    )

    # 외삽 detection 재실행
    monthly_std_vals = wide["monthly_std"].values
    median_std = float(np.median(monthly_std_vals))
    print(f"[median_std] {median_std:.0f} (weekday+weekend proxy)")

    # 24Q 전체 결측: dong + industry 조합이 24개 모두 미싱 (wide 자체가 결측 셀 only)
    n_per_combo = wide.groupby(["dong_code", "industry_code"]).size()
    full_combos = set(n_per_combo[n_per_combo >= 24].index)

    high_var = monthly_std_vals >= NEW_THRESHOLD * median_std
    full_missing_mask = np.array(
        [
            (r["dong_code"], r["industry_code"]) in full_combos
            for _, r in wide[["dong_code", "industry_code"]].iterrows()
        ]
    )
    extrap_mask = high_var | full_missing_mask

    print(
        f"[extrapolation] threshold={NEW_THRESHOLD}, "
        f"count={extrap_mask.sum()}/{len(wide)} ({extrap_mask.sum() / len(wide) * 100:.1f}%)"
    )
    print(f"  - full_missing: {full_missing_mask.sum()}")
    print(f"  - high_var only: {(extrap_mask & ~full_missing_mask).sum()}")

    # confidence 재계산
    base = max(0.60, 1.0 - MNAR_WAPE_FOR_BASE / 100.0)
    print(f"[confidence base] {base:.3f} (from MNAR WAPE {MNAR_WAPE_FOR_BASE}%)")

    ci_ratio = wide["monthly_ci_ratio"].values
    ci_penalty = np.where(ci_ratio > 0.5, 1.0 - np.minimum(0.3, ci_ratio - 0.5), 1.0)
    extrap_penalty = np.where(extrap_mask, EXTRAPOLATION_PENALTY_TARGET / max(base, 0.001), 1.0)
    conf = np.clip(base * ci_penalty * extrap_penalty, 0.10, 1.0)

    wide["extrapolation_flag"] = extrap_mask
    wide["confidence"] = conf
    wide["source"] = np.where(extrap_mask, "extrapolated_v4", "imputed_v4")
    # merge 로 추가된 임시 컬럼 제거
    wide = wide.drop(columns=["monthly_std", "monthly_ci_ratio"], errors="ignore")

    print(f"\n[confidence] mean={conf.mean():.3f}  min={conf.min():.3f}  max={conf.max():.3f}")
    pass_fail = "PASS" if conf.mean() >= 0.75 else "FAIL"
    print(f"[합격선 1-4] confidence 평균 >= 0.75: {pass_fail}")

    wide.to_csv(WIDE_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {WIDE_CSV}")

    # detail 의 confidence 도 갱신
    cell_conf = wide[["quarter", "dong_code", "industry_code", "confidence"]]
    detail = detail.drop(columns=["confidence"], errors="ignore")
    detail = detail.merge(cell_conf, on=["quarter", "dong_code", "industry_code"], how="left")
    detail.to_csv(DETAIL_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {DETAIL_CSV}")


if __name__ == "__main__":
    main()
