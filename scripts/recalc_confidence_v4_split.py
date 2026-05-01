"""Sprint 4: 일반 셀 base (audit_v4_general_only 결과) + 외삽 0.4 cap 으로 confidence 재계산."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
WIDE_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4.csv"
DETAIL_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4_detail.csv"
GENERAL_AUDIT = REPO_ROOT / "validation" / "results" / "audit_v4_general_only.csv"

EXTRAPOLATION_PENALTY_TARGET = 0.4


def main() -> None:
    print("=== Sprint 4: confidence 분리 재계산 ===")
    wide = pd.read_csv(WIDE_CSV)
    audit = pd.read_csv(GENERAL_AUDIT)
    general_mnar = float(audit["mean"].iloc[0])
    print(f"[일반 셀 MNAR] {general_mnar:.2f}%")

    base = max(0.60, 1.0 - general_mnar / 100.0)
    print(f"[base] {base:.3f}")

    # detail 에서 monthly_sales ci_width_ratio 가져오기
    detail = pd.read_csv(DETAIL_CSV)
    monthly = detail[detail["column_name"] == "monthly_sales"][
        ["quarter", "dong_code", "industry_code", "ci_width_ratio"]
    ]
    wide_with_ci = wide.merge(monthly, on=["quarter", "dong_code", "industry_code"], how="left")

    extrap_mask = wide["extrapolation_flag"].astype(bool).values
    ci_ratio = wide_with_ci["ci_width_ratio"].fillna(0).values
    ci_penalty = np.where(ci_ratio > 0.5, 1.0 - np.minimum(0.3, ci_ratio - 0.5), 1.0)
    extrap_penalty = np.where(extrap_mask, EXTRAPOLATION_PENALTY_TARGET / max(base, 0.001), 1.0)
    conf = np.clip(base * ci_penalty * extrap_penalty, 0.10, 1.0)

    wide["confidence"] = conf

    n_general = int((~extrap_mask).sum())
    n_extrap = int(extrap_mask.sum())
    general_conf_mean = float(conf[~extrap_mask].mean()) if n_general > 0 else 0.0
    extrap_conf_mean = float(conf[extrap_mask].mean()) if n_extrap > 0 else 0.0

    print(f"\n[일반 셀 ({n_general}개)] confidence 평균 = {general_conf_mean:.3f}")
    print(f"[외삽 셀 ({n_extrap}개)] confidence 평균 = {extrap_conf_mean:.3f}")
    print(f"[합격선 1-4 (일반 셀 ≥ 0.75)] {'PASS' if general_conf_mean >= 0.75 else 'FAIL'}")
    print(f"[전체 평균 (참고)] {conf.mean():.3f}")

    wide.to_csv(WIDE_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {WIDE_CSV}")

    # detail confidence 갱신
    cell_conf = wide[["quarter", "dong_code", "industry_code", "confidence"]]
    detail = detail.drop(columns=["confidence"], errors="ignore")
    detail = detail.merge(cell_conf, on=["quarter", "dong_code", "industry_code"], how="left")
    detail.to_csv(DETAIL_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {DETAIL_CSV}")


if __name__ == "__main__":
    main()
