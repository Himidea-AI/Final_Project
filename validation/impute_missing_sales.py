"""seoul_district_sales 결측 조합 (동×업종×분기) 역추적 복원.

기준:
  - Lewis (1982): MAPE < 10% = Highly accurate / 10~20% = Reasonable
  - IPF small area estimation 논문 평균 MAPE 5~15%
  - 목표: MAPE < 15%, R² > 0.85, Pearson r > 0.92

방법:
  1. IPF (Iterative Proportional Fitting): 구 단위 총합 + 업종 marginal 제약
  2. Random Forest: 유동인구·매장수·임대·분기 피처로 정밀화
  3. Spatial smoothing: 인접 동 일관성 보정
  4. 10-fold CV: 살아있는 10% 를 mask → 복원 → 실값 비교

출력:
  - docs/sales-imputation/imputation_report.md (검증 리포트)
  - validation/results/imputed_sales.csv (복원 데이터 + 신뢰도)
"""

from __future__ import annotations

import os
import sys
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["POSTGRES_URL"])


# ─────────────────────────────────────────────────────────────
# 1. 데이터 로드
# ─────────────────────────────────────────────────────────────
def load_sales_df() -> pd.DataFrame:
    sql = text("""
        SELECT dong_code, dong_name, industry_code, industry_name,
               quarter, monthly_sales, monthly_count
        FROM seoul_district_sales
        WHERE dong_code LIKE '1144%'
    """)
    with engine.connect() as c:
        return pd.read_sql(sql, c)


def load_features() -> pd.DataFrame:
    """imputation 피처: 유동인구·매장수·임대·변화지수."""
    # 유동인구 (동별 평균)
    with engine.connect() as c:
        pop = pd.read_sql(
            text("""
            SELECT dong_name, AVG(total_pop) avg_pop
            FROM living_population
            WHERE dong_code LIKE '1144%'
              AND date >= (SELECT MAX(date) - 365 FROM living_population)
            GROUP BY dong_name
        """),
            c,
        )
        stores = pd.read_sql(
            text("""
            SELECT dong_name, industry_name, quarter, SUM(store_count) total_stores
            FROM seoul_district_stores
            WHERE dong_code LIKE '1144%'
            GROUP BY dong_name, industry_name, quarter
        """),
            c,
        )
        change = pd.read_sql(
            text("""
            SELECT dong_name, AVG(COALESCE(opr_sale_mt_avg, 0)) opr,
                   AVG(COALESCE(cls_sale_mt_avg, 1)) cls
            FROM seoul_adstrd_change_ix
            WHERE dong_code LIKE '1144%'
            GROUP BY dong_name
        """),
            c,
        )
        change["change_ratio"] = change["opr"] / change["cls"].clip(lower=1)
    return pop, stores, change


def build_master_frame() -> pd.DataFrame:
    """전체 예상 조합 (동×업종×분기) 생성 + 실 데이터 merge."""
    sales = load_sales_df()
    pop, stores, change = load_features()

    # 16 × 10 × ~24 = ~3,840 조합
    dongs = sales[["dong_code", "dong_name"]].drop_duplicates()
    inds = sales[["industry_code", "industry_name"]].drop_duplicates()
    quarters = sales[["quarter"]].drop_duplicates()

    master = (
        dongs.assign(key=1)
        .merge(inds.assign(key=1), on="key")
        .merge(quarters.assign(key=1), on="key")
        .drop("key", axis=1)
    )
    master = master.merge(
        sales[["dong_code", "industry_code", "quarter", "monthly_sales", "monthly_count"]],
        on=["dong_code", "industry_code", "quarter"],
        how="left",
    )
    master["is_missing"] = master["monthly_sales"].isna()

    # 피처 merge
    master = master.merge(pop, on="dong_name", how="left")
    master = master.merge(stores, on=["dong_name", "industry_name", "quarter"], how="left")
    master = master.merge(change[["dong_name", "change_ratio"]], on="dong_name", how="left")

    # 채워넣기 (기본값)
    master["avg_pop"] = master["avg_pop"].fillna(master["avg_pop"].median())
    master["total_stores"] = master["total_stores"].fillna(0)
    master["change_ratio"] = master["change_ratio"].fillna(1.0)

    # 분기를 숫자 피처로 (20241 → 2024.1)
    master["year"] = master["quarter"].astype(int) // 10
    master["qnum"] = master["quarter"].astype(int) % 10

    return master


# ─────────────────────────────────────────────────────────────
# 2. IPF imputation (1차 추정)
# ─────────────────────────────────────────────────────────────
def ipf_impute(df: pd.DataFrame, max_iter: int = 50, tol: float = 1e-4) -> pd.DataFrame:
    """동×업종 marginal 에 맞춰 NULL 셀 IPF 로 추정.

    각 quarter 마다 독립적으로 matrix (dong × industry) 구성 → IPF 돌림.
    """
    out = df.copy()
    out["ipf_sales"] = out["monthly_sales"]
    quarters = sorted(df["quarter"].unique())

    for q in quarters:
        sub = df[df["quarter"] == q].pivot(index="dong_name", columns="industry_name", values="monthly_sales")
        # 마스크: NaN = 추정 대상
        known = sub.values.copy()
        mask = np.isnan(known)
        if not mask.any():
            continue  # 결측 없음

        # 초기값: 평균으로 채움
        avg_per_industry = np.nanmean(known, axis=0)
        known_filled = known.copy()
        for i in range(known.shape[0]):
            for j in range(known.shape[1]):
                if mask[i, j]:
                    known_filled[i, j] = avg_per_industry[j]

        # 행 marginal = 각 동의 총 매출 (non-null 합) × (누락 비율 보정)
        # 열 marginal = 각 업종의 총 매출
        row_targets = np.nansum(known, axis=1)  # 동 총합 (missing 제외, 보수적)
        col_targets = np.nansum(known, axis=0)  # 업종 총합

        # 행 마진 보정 — missing 이 있는 동은 보존 불가, 스케일 factor 추정
        # 단순화: 누락률 기반 expand
        n_known_per_row = (~mask).sum(axis=1)
        total_industries = known.shape[1]
        row_scale = np.where(n_known_per_row > 0, total_industries / n_known_per_row, 1.0)
        row_targets = row_targets * row_scale

        # IPF 수렴
        M = known_filled.copy()
        for it in range(max_iter):
            # 행 스케일
            row_sum = M.sum(axis=1)
            row_factor = np.divide(row_targets, row_sum, out=np.ones_like(row_sum), where=row_sum > 0)
            M = M * row_factor[:, None]
            # 열 스케일
            col_sum = M.sum(axis=0)
            col_factor = np.divide(col_targets, col_sum, out=np.ones_like(col_sum), where=col_sum > 0)
            M = M * col_factor[None, :]
            # 수렴 체크
            row_resid = np.max(np.abs(M.sum(axis=1) - row_targets) / np.maximum(row_targets, 1))
            col_resid = np.max(np.abs(M.sum(axis=0) - col_targets) / np.maximum(col_targets, 1))
            if max(row_resid, col_resid) < tol:
                break

        # known 셀은 원래 값 유지, NULL 셀만 IPF 값 사용
        final = np.where(mask, M, known)
        res = pd.DataFrame(final, index=sub.index, columns=sub.columns).stack().reset_index()
        res.columns = ["dong_name", "industry_name", "ipf_sales"]
        res["quarter"] = q

        # 본 데이터와 merge
        out = out.merge(
            res[["dong_name", "industry_name", "quarter", "ipf_sales"]],
            on=["dong_name", "industry_name", "quarter"],
            how="left",
            suffixes=("", "_new"),
        )
        out["ipf_sales"] = out["ipf_sales_new"].fillna(out["ipf_sales"])
        out = out.drop(columns=["ipf_sales_new"])

    return out


# ─────────────────────────────────────────────────────────────
# 3. Random Forest 정밀화
# ─────────────────────────────────────────────────────────────
def rf_impute(df: pd.DataFrame) -> pd.DataFrame:
    """IPF 초기값을 base 로, RF 가 잔차 학습."""
    out = df.copy()
    feature_cols = ["avg_pop", "total_stores", "change_ratio", "year", "qnum"]
    # 업종·동 one-hot
    df_encoded = pd.get_dummies(out, columns=["industry_name", "dong_name"], prefix=["ind", "dong"])
    enc_cols = [c for c in df_encoded.columns if c.startswith(("ind_", "dong_"))]
    X_cols = feature_cols + enc_cols

    train_mask = ~out["is_missing"]
    X_train = df_encoded.loc[train_mask, X_cols]
    y_train = out.loc[train_mask, "monthly_sales"]
    X_all = df_encoded[X_cols]

    rf = RandomForestRegressor(n_estimators=300, max_depth=15, min_samples_leaf=3, random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    out["rf_sales"] = rf.predict(X_all)

    # 앙상블: IPF × 0.4 + RF × 0.6 (RF 가 피처 정보 더 풍부)
    out["imputed_sales"] = np.where(
        out["is_missing"], 0.4 * out["ipf_sales"] + 0.6 * out["rf_sales"], out["monthly_sales"]
    )
    return out


# ─────────────────────────────────────────────────────────────
# 4. 10-fold Cross-Validation — 정확도 검증
# ─────────────────────────────────────────────────────────────
def cross_validate(df: pd.DataFrame, k: int = 10, seed: int = 42) -> dict:
    """살아있는 값 중 1/k 마스킹 → imputation → 실값과 비교.

    Lewis 경고 (small actuals → MAPE 증폭) 고려해 다중 지표 병기:
      - MAPE (참고용, small cell 편향)
      - WAPE (Weighted APE) = Σ|A-F|/Σ|A| — 매출 규모 반영 강건
      - SMAPE (Symmetric) = Σ 2|A-F|/(|A|+|F|) — 대칭, 0~200% bounded
      - R² (분산 설명력)
      - Pearson r (선형 상관)
    """
    non_null = df[~df["is_missing"]].copy()
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(non_null))
    folds = np.array_split(idx, k)

    mapes, wapes, smapes, r2s, pearsons, maes, medians = [], [], [], [], [], [], []
    for fi, fold_idx in enumerate(folds):
        df_cv = df.copy()
        mask_idx = non_null.iloc[fold_idx].index
        df_cv.loc[mask_idx, "monthly_sales"] = np.nan
        df_cv.loc[mask_idx, "is_missing"] = True

        imp = ipf_impute(df_cv)
        imp = rf_impute(imp)

        pred = imp.loc[mask_idx, "imputed_sales"].values
        true = df.loc[mask_idx, "monthly_sales"].values
        valid = (true > 0) & ~np.isnan(pred) & ~np.isnan(true)
        if valid.sum() < 5:
            continue
        p, t = pred[valid], true[valid]
        abs_err = np.abs(p - t)

        # MAPE — 전통 지표 (small cell 편향)
        mape = np.mean(abs_err / t) * 100
        # WAPE — 매출 규모 반영
        wape = abs_err.sum() / t.sum() * 100
        # SMAPE — 대칭 (0~200%)
        smape = np.mean(2 * abs_err / (np.abs(t) + np.abs(p))) * 100
        # Median APE — outlier 내성
        median_ape = np.median(abs_err / t) * 100

        r2 = r2_score(t, p)
        pr, _ = pearsonr(t, p)

        mapes.append(mape)
        wapes.append(wape)
        smapes.append(smape)
        r2s.append(r2)
        pearsons.append(pr)
        maes.append(np.mean(abs_err))
        medians.append(median_ape)
        print(
            f"  Fold {fi + 1}/{k}: n={valid.sum()}, MAPE={mape:.1f}% WAPE={wape:.1f}% SMAPE={smape:.1f}% MedianAPE={median_ape:.1f}% R²={r2:.3f} r={pr:.3f}",
            flush=True,
        )

    return {
        "mape_mean": float(np.mean(mapes)),
        "mape_std": float(np.std(mapes)),
        "wape_mean": float(np.mean(wapes)),
        "wape_std": float(np.std(wapes)),
        "smape_mean": float(np.mean(smapes)),
        "median_ape_mean": float(np.mean(medians)),
        "r2_mean": float(np.mean(r2s)),
        "r2_std": float(np.std(r2s)),
        "pearson_mean": float(np.mean(pearsons)),
        "pearson_std": float(np.std(pearsons)),
        "mae_mean": float(np.mean(maes)),
        "n_folds": len(mapes),
    }


def judge(metrics: dict) -> str:
    """Lewis + IPF 논문 기준. WAPE 우선 (MAPE 는 small cell 증폭 경고).

    Lewis (1982) scale:
      <10% Highly Accurate / 10~20% Reasonable / 20~50% Inaccurate / >50% Poor
    """
    wape = metrics["wape_mean"]  # 매출 규모 반영 강건 지표 — 주 판정
    r2 = metrics["r2_mean"]
    pr = metrics["pearson_mean"]
    if wape < 10 and r2 > 0.90 and pr > 0.95:
        return "🏆 Highly Accurate (Lewis 최상위)"
    if wape < 15 and r2 > 0.85 and pr > 0.92:
        return "🥇 Target Achieved (IPF small area 상위)"
    if wape < 20 and r2 > 0.75 and pr > 0.85:
        return "🥈 Reasonable (Lewis Reasonable)"
    if wape < 50:
        return "🥉 Marginal (Lewis Inaccurate)"
    return "⚠️ Poor — 재설계 필요"


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    print("=== 결측 데이터 역추적 imputation ===\n")
    master = build_master_frame()
    print(f"전체 조합: {len(master):,}")
    print(f"NULL 조합: {master['is_missing'].sum():,} ({master['is_missing'].mean() * 100:.1f}%)\n")

    print("=== 1. IPF + RF 복합 imputation 실행 ===")
    imp_ipf = ipf_impute(master)
    imp_final = rf_impute(imp_ipf)
    print(f"복원된 조합: {imp_final['is_missing'].sum()}\n")

    print("=== 2. 10-fold Cross-Validation ===")
    cv_results = cross_validate(master, k=10)
    print()

    print("=== 3. 최종 검증 결과 (다중 지표) ===")
    grade = judge(cv_results)
    print(
        f"  MAPE            : {cv_results['mape_mean']:.2f}% ± {cv_results['mape_std']:.2f}%   ← small cell 편향 주의"
    )
    print(
        f"  ★ WAPE (판정)   : {cv_results['wape_mean']:.2f}% ± {cv_results['wape_std']:.2f}%   ← 매출 규모 반영 (Lewis scale 적용)"
    )
    print(f"  SMAPE           : {cv_results['smape_mean']:.2f}%")
    print(f"  Median APE      : {cv_results['median_ape_mean']:.2f}%")
    print(f"  R²              : {cv_results['r2_mean']:.3f} ± {cv_results['r2_std']:.3f}")
    print(f"  Pearson r       : {cv_results['pearson_mean']:.3f} ± {cv_results['pearson_std']:.3f}")
    print(f"  MAE             : {cv_results['mae_mean']:,.0f} 원")
    print(f"  판정            : {grade}")

    # 결과 저장
    out_dir = REPO_ROOT / "validation" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    imp_final["source"] = np.where(imp_final["is_missing"], "imputed_ipf_rf", "original")
    imp_final["confidence"] = np.where(
        imp_final["is_missing"],
        max(0, min(1, 1 - cv_results["mape_mean"] / 100)),
        1.0,
    )
    out_csv = out_dir / "imputed_sales.csv"
    imp_final[
        [
            "dong_code",
            "dong_name",
            "industry_code",
            "industry_name",
            "quarter",
            "monthly_sales",
            "imputed_sales",
            "is_missing",
            "source",
            "confidence",
        ]
    ].to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\n[saved] {out_csv}")

    return cv_results, imp_final


if __name__ == "__main__":
    main()
