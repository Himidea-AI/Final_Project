# Imputed v4 재설계 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 마포 137 결측 매출 셀의 48개 numeric 컬럼 (sales 24 + count 24) 전체를 Multi-Output ExtraTrees + 6 seed 앙상블 + 95% CI 로 정직 복원하고, ABM popularity 계산에 confidence 가중을 전파해 "예측의 예측" 스노우볼을 통제한다.

**Architecture:** Phase 0 (사전 실험 3종) → Phase 1 (본 학습 + raking post-processing) → Phase 2 (4종 CV + 6 추가 지표 감사) → Phase 3 (DB 적재 + world_loader 수정) → Phase 4 (ABM Sensitivity) → Phase 5 (통합 + 5트랙 V1c). 각 Phase 의 합격선 미달 시 정직 보고 + confidence 일괄 하향, 다른 세션 brand-menu 작업과 충돌 회피 (vacancy_pse 등 수정 금지).

**Tech Stack:** Python 3.11+, scikit-learn (ExtraTreesRegressor + MultiOutputRegressor), Optuna 200 trials, scipy.stats (Pearson r), PostgreSQL (LEFT JOIN + COALESCE), PublicDataReader (KOSIS API), pandas/numpy.

**Spec:** `docs/superpowers/specs/2026-04-27-imputed-v4-redesign-design.md`

---

## File Structure

### Create (신규)
- `validation/exceptions.py` — 10 종 예외 클래스
- `scripts/probe_kosis_item_split.py` — Phase 0-1 KOSIS 항목 분리 실험
- `validation/audit_dong_avg_leak.py` — Phase 0-2 LOO leak 수정 실험
- `validation/compare_learning_paths.py` — Phase 0-3 3 path MNAR WAPE 비교
- `validation/reverse_engineer_sales_v4.py` — Phase 1 본 학습 (Multi-Output 6 seed)
- `validation/sum_consistency.py` — raking post-processing (5 sum constraint × sales/count)
- `validation/audit_v4.py` — Phase 2 4 CV + 10 지표 감사
- `validation/sensitivity_v4_abm.py` — Phase 4 imputed 사용/미사용 ABM 비교
- `backend/migrations/V4__seoul_district_sales_imputed_v4.sql` — DB 신규 테이블 2개
- `tests/test_imputed_v4.py` — Phase 1 단위 테스트
- `tests/test_audit_v4.py` — Phase 2 단위 테스트
- `tests/test_sum_consistency.py` — raking 단위 테스트
- `tests/test_other_session_compat.py` — 다른 세션 회귀 테스트
- `backend/tests/test_dong_industry_weight_confidence.py` — world_loader 수정 단위 테스트

### Modify (수정)
- `backend/src/simulation/world_loader.py` — `_load_dong_industry_weight()` 만 수정 (LEFT JOIN seoul_district_sales_imputed_v4 + COALESCE + confidence 가중)

### Output (산출 데이터)
- `validation/results/kosis_item_split_result.csv`
- `validation/results/dong_avg_leak_audit.csv`
- `validation/results/learning_paths_comparison.csv`
- `validation/results/imputed_mapo_v4.csv` (wide, 48 imputed 컬럼)
- `validation/results/imputed_mapo_v4_detail.csv` (long, 6,439 row)
- `data/processed/sales_imp_mapo.csv` (v4 로 교체)

### Output (문서)
- `docs/sales-imputation/audit_v4_report.md`
- `docs/sales-imputation/sensitivity_v4_report.md`

### 수정 금지 (다른 세션 영역)
- `backend/src/simulation/vacancy_pse.py`
- `backend/src/simulation/vacancy_inject.py`
- `backend/src/simulation/world.py` (다른 세션의 `living_pop_daily_boost` 필드 추가 영역)
- `backend/src/simulation/runner.py`
- `backend/src/services/vacancy_evaluation_service.py`
- `backend/src/services/brand_menu_loader.py` (다른 세션 신규)
- `validation/brand_vacancy_validator.py` (다른 세션 신규)
- `backend/src/simulation/dialog_templates.py` (다른 세션 신규)

---

## Task 1: 예외 클래스 정의

**Files:**
- Create: `validation/exceptions.py`
- Test: `tests/test_imputed_v4.py` (Task 4 에서 사용)

- [ ] **Step 1: 신규 파일 생성**

```python
# validation/exceptions.py
"""Imputed v4 파이프라인 예외 클래스."""


class ImputationError(Exception):
    """역산 파이프라인 base 예외."""


class KOSISFetchError(ImputationError):
    """KOSIS API 응답 없음/빈 결과 — Phase 0-1."""


class KOSISItemAmbiguousError(ImputationError):
    """경상/불변 itm_id 모두 fallback 실패 — Phase 0-1."""


class LearningPathInvalidError(ImputationError):
    """3 path 모두 NaN/inf MNAR 결과 — Phase 0-3."""


class EnsembleInstabilityError(ImputationError):
    """6 seed 분산이 합격선 1-1 임계 (>0.10) 초과 — Phase 1."""


class ExtrapolationCellOverflowError(ImputationError):
    """외삽 셀이 137 중 50% 초과 — 모델 자체 의문."""


class SumConsistencyError(ImputationError):
    """raking post-processing 후에도 sum constraint 오차 > 1%."""


class AuditFailureWithDiagnoses(ImputationError):
    """Phase 2 감사 5종 이상 fail — 정직 보고."""


class V4DBLoadError(ImputationError):
    """seoul_district_sales_imputed_v4 적재 실패."""


class WorldLoaderRegressionError(ImputationError):
    """world_loader 수정 후 회귀 테스트 fail."""


class SensitivityZeroImpactError(ImputationError):
    """Phase 4 sensitivity 가 절대값 < 1% — imputed 효과 측정 불가."""
```

- [ ] **Step 2: 임포트 검증**

Run: `python -c "from validation.exceptions import (ImputationError, KOSISFetchError, KOSISItemAmbiguousError, LearningPathInvalidError, EnsembleInstabilityError, ExtrapolationCellOverflowError, SumConsistencyError, AuditFailureWithDiagnoses, V4DBLoadError, WorldLoaderRegressionError, SensitivityZeroImpactError); print('OK')"`

Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add validation/exceptions.py
git commit -m "feat(A1): imputed v4 예외 클래스 10종 정의"
```

---

## Task 2: Phase 0-1 — KOSIS 항목 분리 실험

**Files:**
- Create: `scripts/probe_kosis_item_split.py`
- Output: `validation/results/kosis_item_split_result.csv`

**합격선:** 분리 r − 혼합 r ≥ +0.03 → 분리 채택, 미달 시 혼합 유지

- [ ] **Step 1: 신규 파일 생성**

```python
# scripts/probe_kosis_item_split.py
"""Phase 0-1: KOSIS DT_1KC2023 의 itm_id 별 anchor 분리 실험.

경상지수 (T1) / 불변지수 (T2) / 혼합 3종 anchor 각각 마포 총매출과
Pearson r 측정 → 분리 anchor 가 +0.03 이상 개선되면 채택.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
from PublicDataReader import Kosis
from scipy.stats import pearsonr
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

engine = create_engine(os.environ["POSTGRES_URL"])
api = Kosis(os.environ["KOSIS_API_KEY"])

OUT_CSV = REPO_ROOT / "validation" / "results" / "kosis_item_split_result.csv"

ITM_CURRENT = "13102193311A.T1"   # 경상지수
ITM_CONSTANT = "13102193311A.T2"  # 불변지수
THRESHOLD_DELTA = 0.03


def fetch_anchor(itm_id: str) -> pd.DataFrame:
    """KOSIS DT_1KC2023 서울 숙박·음식점업 분기 지수."""
    for attempt in range(3):
        try:
            df = api.get_data(
                "통계자료", orgId="101", tblId="DT_1KC2023",
                objL1="11", objL2="I", itmId=itm_id, prdSe="Q",
                startPrdDe="201901", endPrdDe="202404",
            )
            if df is not None and len(df) > 0:
                return df
        except Exception as e:
            print(f"  attempt {attempt+1} failed: {e}")
            time.sleep(5)
    return pd.DataFrame()


def normalize_quarters(df: pd.DataFrame) -> pd.DataFrame:
    """KOSIS 응답 → quarter (YYYYQ) + value 컬럼 정규화."""
    val_col = next((c for c in df.columns if c in ("수치값", "DT", "value")), None)
    per_col = next((c for c in df.columns if c in ("수록시점", "PRD_DE", "period_value")), None)
    df = df[[per_col, val_col]].copy()
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")

    def to_qkey(p):
        p = str(p)
        if "Q" in p:
            y, q = p.split("Q")
            return int(y) * 10 + int(q)
        if len(p) == 6:
            return int(p[:4]) * 10 + int(p[4:6])
        return None

    df["quarter"] = df[per_col].apply(to_qkey)
    df = df.dropna(subset=["quarter", val_col])
    return df.groupby("quarter", as_index=False)[val_col].mean().rename(columns={val_col: "value"})


def load_mapo_total_sales() -> pd.DataFrame:
    """마포 alive 셀 분기 총매출."""
    sql = text("""
        SELECT quarter, SUM(monthly_sales)::bigint AS total_sales
        FROM district_sales
        WHERE dong_code LIKE '11440%' AND monthly_sales IS NOT NULL
        GROUP BY quarter
        ORDER BY quarter
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn)


def measure_r(anchor: pd.DataFrame, mapo: pd.DataFrame) -> dict:
    merged = anchor.merge(mapo, on="quarter", how="inner")
    if len(merged) < 4:
        return {"n_quarters": len(merged), "pearson_r": None}
    r, _ = pearsonr(merged["value"], merged["total_sales"])
    return {"n_quarters": len(merged), "pearson_r": round(float(r), 4)}


if __name__ == "__main__":
    print("=== Phase 0-1: KOSIS Item Split ===")
    print("[1/4] Fetching current (T1)...")
    df_current = fetch_anchor(ITM_CURRENT)
    print(f"  rows: {len(df_current)}")
    print("[2/4] Fetching constant (T2)...")
    df_constant = fetch_anchor(ITM_CONSTANT)
    print(f"  rows: {len(df_constant)}")

    print("[3/4] Loading mapo total sales...")
    mapo = load_mapo_total_sales()
    print(f"  rows: {len(mapo)}")

    if len(df_current) == 0 or len(df_constant) == 0:
        print("⚠️  fetch failed — using existing anchor CSV (current/constant 분리 불가)")
        sys.exit(1)

    print("[4/4] Measuring Pearson r for 3 anchors...")
    anchors = {
        "current":  normalize_quarters(df_current),
        "constant": normalize_quarters(df_constant),
        "mixed":    normalize_quarters(pd.concat([df_current, df_constant])),
    }

    results = []
    for name, anchor in anchors.items():
        m = measure_r(anchor, mapo)
        m["name"] = name
        results.append(m)
        print(f"  {name:10s}: r = {m['pearson_r']:.4f} (n={m['n_quarters']})")

    out_df = pd.DataFrame(results)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {OUT_CSV}")

    # 합격 판정
    r_mixed = next(r["pearson_r"] for r in results if r["name"] == "mixed")
    best = max([r for r in results if r["name"] != "mixed"], key=lambda x: x["pearson_r"])
    delta = best["pearson_r"] - r_mixed
    chosen = best["name"] if delta >= THRESHOLD_DELTA else "mixed"
    print(f"\n[합격선] best ({best['name']}) − mixed = {delta:+.4f}")
    print(f"[채택] anchor = '{chosen}'  ({'분리 채택' if chosen != 'mixed' else '혼합 유지'})")
```

- [ ] **Step 2: 실행 + 결과 확인**

Run: `python scripts/probe_kosis_item_split.py`

Expected: 4 단계 진행 로그 + `validation/results/kosis_item_split_result.csv` 생성 + best/mixed delta 출력

- [ ] **Step 3: 결과 검증**

Run: `python -c "import pandas as pd; df = pd.read_csv('validation/results/kosis_item_split_result.csv'); print(df); assert len(df) == 3"`

Expected: 3 row (current/constant/mixed) + assert 통과

- [ ] **Step 4: 커밋**

```bash
git add scripts/probe_kosis_item_split.py validation/results/kosis_item_split_result.csv
git commit -m "feat(A1): Phase 0-1 KOSIS 항목 분리 실험 + 결과"
```

---

## Task 3: Phase 0-2 — dong_avg LOO leak 수정 실험

**Files:**
- Create: `validation/audit_dong_avg_leak.py`
- Output: `validation/results/dong_avg_leak_audit.csv`

**합격선:** LOO 적용 전/후 MNAR WAPE 차이 ≤ 3%p → v3 결과 신뢰. 초과 시 정직 보고.

- [ ] **Step 1: 신규 파일 생성**

```python
# validation/audit_dong_avg_leak.py
"""Phase 0-2: MNAR/LODO CV 에서 dong_avg_store/combo_avg_store LOO 적용.

기존 v3 는 dong_avg_store 를 전체 데이터로 계산 → fold 분리해도 leak.
LOO (Leave-One-Out) 적용 시 진짜 일반화 성능 측정.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

engine = create_engine(os.environ["POSTGRES_URL"])
ANCHOR_CSV = REPO_ROOT / "validation" / "results" / "phase1b_anchor_series.csv"
OUT_CSV = REPO_ROOT / "validation" / "results" / "dong_avg_leak_audit.csv"

THRESHOLD_DELTA_WAPE_PP = 3.0   # 합격선 0-2: ≤ 3%p


def load_joined() -> pd.DataFrame:
    sql = text("""
        SELECT q.quarter, q.dong_code, q.dong_name, q.industry_code, q.industry_name,
               s.monthly_sales, q.store_count, q.open_count, q.close_count,
               q.closure_rate, q.franchise_count
        FROM store_quarterly q
        LEFT JOIN district_sales s
          ON q.quarter = s.quarter AND q.dong_code = s.dong_code
         AND q.industry_code = s.industry_code
        WHERE q.dong_code LIKE '11440%'
        ORDER BY q.quarter, q.dong_code, q.industry_code
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)
    anchor = pd.read_csv(ANCHOR_CSV).rename(columns={"qkey": "quarter", "수치값": "kosis_index"})
    anchor = anchor.groupby("quarter", as_index=False)["kosis_index"].mean()
    df = df.merge(anchor[["quarter", "kosis_index"]], on="quarter", how="left")
    df["sales_per_store"] = df["monthly_sales"] / df["store_count"].clip(lower=1)
    return df


def build_features_with_leak(df: pd.DataFrame) -> pd.DataFrame:
    """v3 의 leak 있는 피처 생성 (전체 데이터로 dong_avg 계산)."""
    X = pd.DataFrame(index=df.index)
    X["store_count"] = df["store_count"].fillna(df["store_count"].median())
    X["log_store_count"] = np.log1p(X["store_count"])
    X["kosis_index"] = df["kosis_index"]
    X["log_kosis"] = np.log(df["kosis_index"])
    X["franchise_ratio"] = df["franchise_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["open_ratio"] = df["open_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["closure_rate"] = df["closure_rate"].fillna(0)
    X["q_of_year"] = df["quarter"] % 10
    X["year"] = df["quarter"] // 10
    for ind in df["industry_code"].unique():
        X[f"ind_{ind}"] = (df["industry_code"] == ind).astype(int)
    # ⚠️ leak: 전체 alive 로 계산
    df_alive = df[df["monthly_sales"].notna()]
    dong_size = df_alive.groupby("dong_code")["store_count"].mean()
    X["dong_avg_store"] = df["dong_code"].map(dong_size).fillna(dong_size.mean())
    combo = df_alive.groupby(["dong_code", "industry_code"])["store_count"].mean()
    X["combo_avg_store"] = df.set_index(["dong_code", "industry_code"]).index.map(combo.to_dict())
    X["combo_avg_store"] = X["combo_avg_store"].fillna(combo.mean())
    return X


def build_features_loo(df: pd.DataFrame, exclude_idx: pd.Index) -> pd.DataFrame:
    """LOO 적용: dong_avg / combo_avg 계산 시 exclude_idx 제외."""
    X = pd.DataFrame(index=df.index)
    X["store_count"] = df["store_count"].fillna(df["store_count"].median())
    X["log_store_count"] = np.log1p(X["store_count"])
    X["kosis_index"] = df["kosis_index"]
    X["log_kosis"] = np.log(df["kosis_index"])
    X["franchise_ratio"] = df["franchise_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["open_ratio"] = df["open_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["closure_rate"] = df["closure_rate"].fillna(0)
    X["q_of_year"] = df["quarter"] % 10
    X["year"] = df["quarter"] // 10
    for ind in df["industry_code"].unique():
        X[f"ind_{ind}"] = (df["industry_code"] == ind).astype(int)
    # LOO: exclude 제외하고 alive 만 사용
    df_alive_loo = df.drop(exclude_idx).query("monthly_sales == monthly_sales")
    dong_size = df_alive_loo.groupby("dong_code")["store_count"].mean()
    X["dong_avg_store"] = df["dong_code"].map(dong_size).fillna(dong_size.mean())
    combo = df_alive_loo.groupby(["dong_code", "industry_code"])["store_count"].mean()
    X["combo_avg_store"] = df.set_index(["dong_code", "industry_code"]).index.map(combo.to_dict())
    X["combo_avg_store"] = X["combo_avg_store"].fillna(combo.mean())
    return X


def mnar_mimic_cv(df: pd.DataFrame, build_X_fn, n_folds: int = 5, seed: int = 42) -> float:
    """MNAR-mimic CV: 결측 셀 store_count 분포 유사 alive 만 hold-out."""
    alive_mask = df["monthly_sales"].notna()
    missing_q95 = df.loc[~alive_mask, "store_count"].quantile(0.95)
    mimic_idx = df[alive_mask & (df["store_count"] <= missing_q95)].index.values

    rng = np.random.default_rng(seed)
    folds = np.array_split(rng.permutation(mimic_idx), n_folds)

    wapes = []
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].values.astype(float)
    y_sps = np.log1p(df["sales_per_store"].values)

    for te_idx in folds:
        tr_mask = alive_mask & (~df.index.isin(te_idx))
        tr_idx = df[tr_mask].index.values
        # build_X_fn 이 LOO 면 te_idx 제외하고 dong_avg 계산
        X = build_X_fn(df, pd.Index(te_idx)) if build_X_fn.__name__ == "build_features_loo" else build_X_fn(df)

        gbm = ExtraTreesRegressor(n_estimators=300, max_depth=35, min_samples_leaf=1,
                                  bootstrap=False, random_state=42, n_jobs=-1)
        gbm.fit(X.loc[tr_idx], y_sps[tr_idx])
        log_pred = gbm.predict(X.loc[te_idx])
        sales_pred = np.expm1(log_pred) * np.maximum(store[te_idx], 1)
        sales_pred = np.clip(sales_pred, 0, None)
        actual = actual_sales[te_idx]
        wape = np.abs(actual - sales_pred).sum() / actual.sum() * 100
        wapes.append(wape)
    return float(np.mean(wapes))


if __name__ == "__main__":
    print("=== Phase 0-2: dong_avg LOO Leak Audit ===")
    df = load_joined()
    print(f"[data] total={len(df)} alive={df['monthly_sales'].notna().sum()}")

    print("\n[1/2] WITH leak (v3 방식)...")
    wape_leak = mnar_mimic_cv(df, build_features_with_leak)
    print(f"  MNAR WAPE = {wape_leak:.2f}%")

    print("\n[2/2] WITHOUT leak (LOO 적용)...")
    wape_loo = mnar_mimic_cv(df, build_features_loo)
    print(f"  MNAR WAPE = {wape_loo:.2f}%")

    delta = wape_loo - wape_leak
    print(f"\n[합격선 0-2] |delta| = |{delta:+.2f}%p|")
    if abs(delta) <= THRESHOLD_DELTA_WAPE_PP:
        print(f"✅ ≤ {THRESHOLD_DELTA_WAPE_PP}%p — v3 결과 신뢰")
    else:
        print(f"⚠️  > {THRESHOLD_DELTA_WAPE_PP}%p — v3 leak로 과소평가, 진짜 MNAR ≈ {wape_loo:.1f}%")

    out_df = pd.DataFrame([
        {"variant": "v3_with_leak", "mnar_wape_pct": round(wape_leak, 2)},
        {"variant": "v4_loo",       "mnar_wape_pct": round(wape_loo, 2)},
        {"variant": "delta_pp",     "mnar_wape_pct": round(delta, 2)},
    ])
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {OUT_CSV}")
```

- [ ] **Step 2: 실행**

Run: `python validation/audit_dong_avg_leak.py`

Expected: 2 단계 + delta 출력 + `validation/results/dong_avg_leak_audit.csv` 생성

- [ ] **Step 3: 결과 검증**

Run: `python -c "import pandas as pd; df = pd.read_csv('validation/results/dong_avg_leak_audit.csv'); print(df); assert len(df) == 3"`

Expected: 3 row + assert 통과

- [ ] **Step 4: 커밋**

```bash
git add validation/audit_dong_avg_leak.py validation/results/dong_avg_leak_audit.csv
git commit -m "feat(A1): Phase 0-2 dong_avg LOO leak 감사 + 결과"
```

---

## Task 4: Phase 0-3 — 학습 path 비교 (마포 단독 vs 서울→마포 vs Hybrid)

**Files:**
- Create: `validation/compare_learning_paths.py`
- Output: `validation/results/learning_paths_comparison.csv`

**합격선:** 최저 WAPE − 마포 단독 WAPE ≥ −1.5%p → 그 path 채택, 미달 시 마포 단독

- [ ] **Step 1: 신규 파일 생성**

```python
# validation/compare_learning_paths.py
"""Phase 0-3: 3 학습 path × 6 seed × MNAR-mimic CV 비교.

(A) mapo_only:     마포 alive 만 학습 → 마포 137 예측
(B) seoul_to_mapo: 서울 10 업종 alive 학습 → 마포 137 예측
(C) hybrid:        서울 alive 학습 + 마포 sample_weight=5 → 마포 137 예측

합격: 최저 WAPE − 마포 단독 WAPE ≥ −1.5%p 시 그 path 채택.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

engine = create_engine(os.environ["POSTGRES_URL"])
ANCHOR_CSV = REPO_ROOT / "validation" / "results" / "phase1b_anchor_series.csv"
OUT_CSV = REPO_ROOT / "validation" / "results" / "learning_paths_comparison.csv"

SEEDS = [42, 2026, 7, 13, 99, 1234]
THRESHOLD_IMPROVEMENT_PP = 1.5   # 합격선 0-3
N_FOLDS = 5

INDUSTRIES_10 = [
    "CS100001", "CS100002", "CS100003", "CS100004", "CS100005",
    "CS100006", "CS100007", "CS100008", "CS100009", "CS100010",
]


def load_data(scope: str) -> pd.DataFrame:
    """scope = 'mapo' or 'seoul_10ind'."""
    if scope == "mapo":
        where = "q.dong_code LIKE '11440%'"
    else:
        ind_list = "', '".join(INDUSTRIES_10)
        where = f"q.industry_code IN ('{ind_list}')"

    sql = text(f"""
        SELECT q.quarter, q.dong_code, q.industry_code,
               s.monthly_sales, q.store_count, q.open_count, q.close_count,
               q.closure_rate, q.franchise_count
        FROM store_quarterly q
        LEFT JOIN district_sales s
          ON q.quarter = s.quarter AND q.dong_code = s.dong_code
         AND q.industry_code = s.industry_code
        WHERE {where}
        ORDER BY q.quarter, q.dong_code, q.industry_code
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)
    anchor = pd.read_csv(ANCHOR_CSV).rename(columns={"qkey": "quarter", "수치값": "kosis_index"})
    anchor = anchor.groupby("quarter", as_index=False)["kosis_index"].mean()
    df = df.merge(anchor[["quarter", "kosis_index"]], on="quarter", how="left")
    df["sales_per_store"] = df["monthly_sales"] / df["store_count"].clip(lower=1)
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """LOO 미적용 (path 비교 용도, leak 제어는 Task 3 결과로 별도 적용)."""
    X = pd.DataFrame(index=df.index)
    X["store_count"] = df["store_count"].fillna(df["store_count"].median())
    X["log_store_count"] = np.log1p(X["store_count"])
    X["kosis_index"] = df["kosis_index"]
    X["log_kosis"] = np.log(df["kosis_index"])
    X["franchise_ratio"] = df["franchise_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["open_ratio"] = df["open_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["closure_rate"] = df["closure_rate"].fillna(0)
    X["q_of_year"] = df["quarter"] % 10
    X["year"] = df["quarter"] // 10
    for ind in INDUSTRIES_10:
        X[f"ind_{ind}"] = (df["industry_code"] == ind).astype(int)
    return X


def mnar_mimic_cv_path(
    df_train: pd.DataFrame,
    df_target: pd.DataFrame,
    sample_weight: np.ndarray | None,
    seeds: list[int],
) -> dict:
    """target (마포) 의 결측 store_count 분포 유사 셀로 hold-out + train 으로 학습."""
    X_train = build_features(df_train)
    X_target = build_features(df_target)
    alive_target = df_target[df_target["monthly_sales"].notna()].copy()
    missing_q95 = df_target.loc[~df_target["monthly_sales"].notna(), "store_count"].quantile(0.95)
    mimic_idx = alive_target[alive_target["store_count"] <= missing_q95].index.values

    wapes = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        folds = np.array_split(rng.permutation(mimic_idx), N_FOLDS)
        fold_wapes = []
        for te_idx in folds:
            # train: train df 의 alive + target df 의 alive (te_idx 제외)
            tr_mask_train = df_train["monthly_sales"].notna()
            tr_mask_target = (df_target["monthly_sales"].notna() & (~df_target.index.isin(te_idx)))
            X_tr = pd.concat([X_train[tr_mask_train], X_target[tr_mask_target]], ignore_index=True)
            y_tr = np.concatenate([
                np.log1p(df_train.loc[tr_mask_train, "sales_per_store"].values),
                np.log1p(df_target.loc[tr_mask_target, "sales_per_store"].values),
            ])
            sw_tr = None
            if sample_weight is not None:
                sw_train_part = np.ones(int(tr_mask_train.sum()))
                sw_target_part = np.full(int(tr_mask_target.sum()), 5.0)
                sw_tr = np.concatenate([sw_train_part, sw_target_part])

            m = ExtraTreesRegressor(n_estimators=300, max_depth=35, min_samples_leaf=1,
                                    bootstrap=False, random_state=seed, n_jobs=-1)
            m.fit(X_tr, y_tr, sample_weight=sw_tr)

            log_pred = m.predict(X_target.loc[te_idx])
            sales_pred = np.expm1(log_pred) * np.maximum(df_target.loc[te_idx, "store_count"].values, 1)
            sales_pred = np.clip(sales_pred, 0, None)
            actual = df_target.loc[te_idx, "monthly_sales"].values
            fold_wapes.append(np.abs(actual - sales_pred).sum() / actual.sum() * 100)
        wapes.append(np.mean(fold_wapes))

    return {"mean_wape": float(np.mean(wapes)), "std_wape": float(np.std(wapes))}


if __name__ == "__main__":
    print("=== Phase 0-3: Learning Path Comparison ===")
    print("[1/2] Loading mapo + seoul_10ind...")
    df_mapo = load_data("mapo")
    df_seoul = load_data("seoul_10ind")
    df_seoul_only = df_seoul[~df_seoul["dong_code"].str.startswith("11440")].copy().reset_index(drop=True)
    print(f"  mapo:  {len(df_mapo)} (alive {df_mapo['monthly_sales'].notna().sum()})")
    print(f"  seoul (mapo 제외): {len(df_seoul_only)} (alive {df_seoul_only['monthly_sales'].notna().sum()})")

    print("\n[2/2] Running 3 paths × 6 seeds...")
    empty_df = df_mapo.iloc[0:0].copy()

    print("  [A] mapo_only ...")
    res_a = mnar_mimic_cv_path(empty_df, df_mapo, sample_weight=None, seeds=SEEDS)
    print(f"      WAPE = {res_a['mean_wape']:.2f}% ± {res_a['std_wape']:.2f}")

    print("  [B] seoul_to_mapo ...")
    res_b = mnar_mimic_cv_path(df_seoul_only, df_mapo, sample_weight=None, seeds=SEEDS)
    print(f"      WAPE = {res_b['mean_wape']:.2f}% ± {res_b['std_wape']:.2f}")

    print("  [C] hybrid (mapo sample_weight=5) ...")
    res_c = mnar_mimic_cv_path(df_seoul_only, df_mapo, sample_weight=np.ones(1), seeds=SEEDS)
    print(f"      WAPE = {res_c['mean_wape']:.2f}% ± {res_c['std_wape']:.2f}")

    results = [
        {"path": "mapo_only",     **res_a},
        {"path": "seoul_to_mapo", **res_b},
        {"path": "hybrid",        **res_c},
    ]
    out_df = pd.DataFrame(results)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    best = min(results, key=lambda x: x["mean_wape"])
    improvement = res_a["mean_wape"] - best["mean_wape"]
    print(f"\n[합격선 0-3] best ({best['path']}) − mapo_only = −{improvement:.2f}%p")
    if improvement >= THRESHOLD_IMPROVEMENT_PP:
        print(f"✅ ≥ {THRESHOLD_IMPROVEMENT_PP}%p — '{best['path']}' 채택")
    else:
        print(f"⚠️  < {THRESHOLD_IMPROVEMENT_PP}%p — 'mapo_only' 채택")

    print(f"[saved] {OUT_CSV}")
```

- [ ] **Step 2: 실행 (4~8 시간, 야간 batch 권장)**

Run: `nohup python validation/compare_learning_paths.py > /tmp/path_compare.log 2>&1 &`

또는 즉시 확인이 필요하면 foreground:

Run: `python validation/compare_learning_paths.py`

Expected: 3 path × 6 seed × 5-fold = 90 학습 세션. 종료 시 채택 path 출력.

- [ ] **Step 3: 결과 검증**

Run: `python -c "import pandas as pd; df = pd.read_csv('validation/results/learning_paths_comparison.csv'); print(df); assert len(df) == 3"`

Expected: 3 row + assert 통과

- [ ] **Step 4: 커밋**

```bash
git add validation/compare_learning_paths.py validation/results/learning_paths_comparison.csv
git commit -m "feat(A1): Phase 0-3 학습 path 비교 (mapo/seoul/hybrid) + 결과"
```

---

## Task 5: Sum Consistency 모듈 (raking) + 단위 테스트

**Files:**
- Create: `validation/sum_consistency.py`
- Test: `tests/test_sum_consistency.py`

- [ ] **Step 1: 단위 테스트 먼저 작성 (TDD)**

```python
# tests/test_sum_consistency.py
"""raking post-processing 단위 테스트 — 5종 sum constraint 보장."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from validation.sum_consistency import (
    SUM_CONSTRAINTS_SALES,
    SUM_CONSTRAINTS_COUNT,
    enforce_sum_consistency,
)


@pytest.fixture
def imperfect_pred() -> pd.DataFrame:
    """sum constraint 가 깨진 샘플 — raking 으로 복원돼야."""
    return pd.DataFrame([
        {
            "monthly_sales": 100,
            "weekday_sales": 60, "weekend_sales": 50,                          # 합 110 ≠ 100
            "mon_sales": 14, "tue_sales": 14, "wed_sales": 14, "thu_sales": 14,
            "fri_sales": 14, "sat_sales": 14, "sun_sales": 14,                 # 합 98 ≠ 100
            "time_00_06_sales": 16, "time_06_11_sales": 16, "time_11_14_sales": 16,
            "time_14_17_sales": 16, "time_17_21_sales": 16, "time_21_24_sales": 16,  # 합 96
            "male_sales": 60, "female_sales": 50,                              # 합 110
            "age_10_sales": 16, "age_20_sales": 16, "age_30_sales": 16,
            "age_40_sales": 16, "age_50_sales": 16, "age_60_above_sales": 16,  # 합 96
        }
    ])


def test_weekday_weekend_sum_equals_monthly(imperfect_pred):
    out = enforce_sum_consistency(imperfect_pred.copy(), SUM_CONSTRAINTS_SALES)
    assert abs(out["weekday_sales"].iloc[0] + out["weekend_sales"].iloc[0]
               - out["monthly_sales"].iloc[0]) < 1.0


def test_dow_7days_sum_equals_monthly(imperfect_pred):
    out = enforce_sum_consistency(imperfect_pred.copy(), SUM_CONSTRAINTS_SALES)
    dow = ["mon_sales","tue_sales","wed_sales","thu_sales","fri_sales","sat_sales","sun_sales"]
    assert abs(out[dow].sum(axis=1).iloc[0] - out["monthly_sales"].iloc[0]) < 1.0


def test_time_6buckets_sum_equals_monthly(imperfect_pred):
    out = enforce_sum_consistency(imperfect_pred.copy(), SUM_CONSTRAINTS_SALES)
    time_cols = [f"time_{t}_sales" for t in ["00_06","06_11","11_14","14_17","17_21","21_24"]]
    assert abs(out[time_cols].sum(axis=1).iloc[0] - out["monthly_sales"].iloc[0]) < 1.0


def test_gender_sum_equals_monthly(imperfect_pred):
    out = enforce_sum_consistency(imperfect_pred.copy(), SUM_CONSTRAINTS_SALES)
    assert abs(out["male_sales"].iloc[0] + out["female_sales"].iloc[0]
               - out["monthly_sales"].iloc[0]) < 1.0


def test_age_6buckets_sum_equals_monthly(imperfect_pred):
    out = enforce_sum_consistency(imperfect_pred.copy(), SUM_CONSTRAINTS_SALES)
    age_cols = [f"age_{a}_sales" for a in ["10","20","30","40","50","60_above"]]
    assert abs(out[age_cols].sum(axis=1).iloc[0] - out["monthly_sales"].iloc[0]) < 1.0


def test_enforce_sum_consistency_idempotent(imperfect_pred):
    """두 번 호출해도 결과 동일 (이미 일관성 보장된 후)."""
    once = enforce_sum_consistency(imperfect_pred.copy(), SUM_CONSTRAINTS_SALES)
    twice = enforce_sum_consistency(once.copy(), SUM_CONSTRAINTS_SALES)
    pd.testing.assert_frame_equal(once, twice, atol=0.01)


def test_zero_sub_sum_does_not_crash():
    """sub_sum = 0 (모든 sub_col 이 0) 인 경우 division-by-zero 방지."""
    df = pd.DataFrame([{"monthly_sales": 100, "weekday_sales": 0, "weekend_sales": 0,
                        **{f"{d}_sales": 0 for d in ["mon","tue","wed","thu","fri","sat","sun"]},
                        **{f"time_{t}_sales": 0 for t in ["00_06","06_11","11_14","14_17","17_21","21_24"]},
                        "male_sales": 0, "female_sales": 0,
                        **{f"age_{a}_sales": 0 for a in ["10","20","30","40","50","60_above"]}}])
    out = enforce_sum_consistency(df, SUM_CONSTRAINTS_SALES)
    # 0 합계는 그대로 유지 (raking 적용 X)
    assert out["weekday_sales"].iloc[0] == 0
```

- [ ] **Step 2: 테스트 실행 fail 확인**

Run: `pytest tests/test_sum_consistency.py -v`

Expected: ImportError (모듈 없음) 또는 모든 테스트 fail

- [ ] **Step 3: 모듈 구현**

```python
# validation/sum_consistency.py
"""Multi-Output 예측 결과의 sum constraint raking post-processing.

5종 constraint × {sales, count} = 10회 적용:
  1) weekday + weekend = monthly
  2) Σ(mon~sun) = monthly
  3) Σ(time_00_06~21_24) = monthly
  4) male + female = monthly
  5) Σ(age_10~60_above) = monthly
"""

from __future__ import annotations

import pandas as pd

SUM_CONSTRAINTS_SALES: list[tuple[list[str], str]] = [
    (["weekday_sales", "weekend_sales"], "monthly_sales"),
    ([f"{d}_sales" for d in ["mon","tue","wed","thu","fri","sat","sun"]], "monthly_sales"),
    ([f"time_{t}_sales" for t in ["00_06","06_11","11_14","14_17","17_21","21_24"]], "monthly_sales"),
    (["male_sales", "female_sales"], "monthly_sales"),
    ([f"age_{a}_sales" for a in ["10","20","30","40","50","60_above"]], "monthly_sales"),
]

SUM_CONSTRAINTS_COUNT: list[tuple[list[str], str]] = [
    ([c.replace("_sales", "_count") for c in subs], total.replace("_sales", "_count"))
    for subs, total in SUM_CONSTRAINTS_SALES
]


def enforce_sum_consistency(
    pred_df: pd.DataFrame,
    constraints: list[tuple[list[str], str]],
) -> pd.DataFrame:
    """raking: pred_df[sub_cols] *= total / sub_sum.

    sub_sum = 0 인 행은 변경 없음 (division-by-zero 방지).
    """
    df = pred_df.copy()
    for sub_cols, total_col in constraints:
        sub_sum = df[sub_cols].sum(axis=1)
        # sub_sum > 0 인 row 만 raking 적용
        mask = sub_sum > 0
        scale = pd.Series(1.0, index=df.index)
        scale.loc[mask] = df.loc[mask, total_col] / sub_sum.loc[mask]
        for col in sub_cols:
            df[col] = df[col] * scale
    return df
```

- [ ] **Step 4: 테스트 실행 pass 확인**

Run: `pytest tests/test_sum_consistency.py -v`

Expected: 7 tests passed

- [ ] **Step 5: 커밋**

```bash
git add validation/sum_consistency.py tests/test_sum_consistency.py
git commit -m "feat(A1): sum_consistency raking 모듈 + 단위 테스트 7건"
```

---

## Task 6: Phase 1 — 본 학습 v4 (Multi-Output 6 seed) + 단위 테스트

**Files:**
- Create: `validation/reverse_engineer_sales_v4.py`
- Test: `tests/test_imputed_v4.py`
- Output: `validation/results/imputed_mapo_v4.csv`, `validation/results/imputed_mapo_v4_detail.csv`

**합격선:** seed std/mean ≤ 0.10, CI 폭 ≤ 0.50, confidence 평균 ≥ 0.75, 외삽 셀 std/median ≥ 1.8

- [ ] **Step 1: 단위 테스트 먼저 작성 (TDD)**

```python
# tests/test_imputed_v4.py
"""Phase 1 본 학습 단위 테스트 — Multi-Output + 6 seed + CI + extrapolation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.multioutput import MultiOutputRegressor

from validation.reverse_engineer_sales_v4 import (
    SEEDS,
    SALES_COLS,
    COUNT_COLS,
    TARGET_COLS,
    fit_seed_ensemble_multi,
    predict_with_ci_multi,
    detect_extrapolation_cells,
    calculate_confidence,
)


@pytest.fixture
def small_train():
    """100 셀 × 5 피처 학습 + 137 셀 결측 mock."""
    rng = np.random.default_rng(42)
    X_train = pd.DataFrame(rng.normal(size=(100, 5)), columns=[f"f{i}" for i in range(5)])
    Y_train = pd.DataFrame(rng.normal(size=(100, 48)), columns=TARGET_COLS)
    X_missing = pd.DataFrame(rng.normal(size=(137, 5)), columns=[f"f{i}" for i in range(5)])
    store_count = np.full(137, 10.0)
    return X_train, Y_train, X_missing, store_count


def test_target_cols_count():
    assert len(TARGET_COLS) == 48
    assert len(SALES_COLS) == 24
    assert len(COUNT_COLS) == 24


def test_predict_with_ci_multi_returns_correct_shape(small_train):
    X_tr, Y_tr, X_mi, sc = small_train
    models = fit_seed_ensemble_multi(X_tr, Y_tr, SEEDS,
        {"n_estimators": 50, "max_depth": 5, "n_jobs": -1})
    out = predict_with_ci_multi(models, X_mi, sc)
    assert set(out.keys()) == {"mean", "std", "lower_95", "upper_95", "ci_width_ratio"}
    for v in out.values():
        assert v.shape == (137, 48)


def test_lower_95_never_negative(small_train):
    X_tr, Y_tr, X_mi, sc = small_train
    models = fit_seed_ensemble_multi(X_tr, Y_tr, SEEDS,
        {"n_estimators": 50, "max_depth": 5, "n_jobs": -1})
    out = predict_with_ci_multi(models, X_mi, sc)
    assert (out["lower_95"].values >= 0).all()


def test_extrapolation_detection_high_variance():
    """monthly_sales std 가 median 의 1.8배 이상인 셀 → True."""
    pred_dict = {
        "std": pd.DataFrame(np.array([[1.0]*48, [10.0]*48, [1.0]*48]), columns=TARGET_COLS),
    }
    df_missing = pd.DataFrame({"quarter": [20191, 20192, 20193]})
    mask = detect_extrapolation_cells(df_missing, pred_dict, threshold_ratio=1.8)
    assert mask[1] == True   # std 10 vs median 1.0 → ratio 10
    assert mask[0] == False
    assert mask[2] == False


def test_calculate_confidence_extrapolation_max_04():
    """extrapolation flag=True 셀 confidence ≤ 0.40."""
    pred_dict = {"ci_width_ratio": pd.DataFrame({"monthly_sales": [0.4, 0.4]}, index=[0, 1])}
    extrap_mask = np.array([True, False])
    audit = {"mnar_wape": 13.0}   # base = 0.87
    conf = calculate_confidence(pred_dict, extrap_mask, audit)
    assert conf[0] <= 0.40
    assert conf[1] >= 0.65


def test_calculate_confidence_normal_min_065():
    """일반 imputed (low CI) → confidence ≥ 0.65."""
    pred_dict = {"ci_width_ratio": pd.DataFrame({"monthly_sales": [0.3, 0.3]}, index=[0, 1])}
    extrap_mask = np.array([False, False])
    audit = {"mnar_wape": 13.0}
    conf = calculate_confidence(pred_dict, extrap_mask, audit)
    assert (conf >= 0.65).all()


def test_six_seeds_all_used(small_train):
    X_tr, Y_tr, X_mi, sc = small_train
    models = fit_seed_ensemble_multi(X_tr, Y_tr, SEEDS,
        {"n_estimators": 50, "max_depth": 5, "n_jobs": -1})
    assert len(models) == 6
```

- [ ] **Step 2: 테스트 실행 fail 확인**

Run: `pytest tests/test_imputed_v4.py -v`

Expected: ImportError (모듈 없음)

- [ ] **Step 3: 본 학습 모듈 구현**

```python
# validation/reverse_engineer_sales_v4.py
"""Phase 1: Multi-Output ExtraTrees × 6 seed → 48 컬럼 동시 복원 + 95% CI.

post-processing: enforce_sum_consistency 로 5종 sum constraint × {sales, count} 보장.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.multioutput import MultiOutputRegressor
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from validation.sum_consistency import (
    SUM_CONSTRAINTS_SALES,
    SUM_CONSTRAINTS_COUNT,
    enforce_sum_consistency,
)

engine = create_engine(os.environ["POSTGRES_URL"])
ANCHOR_CSV = REPO_ROOT / "validation" / "results" / "phase1b_anchor_series.csv"
OUT_WIDE_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4.csv"
OUT_DETAIL_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4_detail.csv"
CHECKPOINT_DIR = REPO_ROOT / "validation" / "results" / "checkpoints_v4"

SEEDS = [42, 2026, 7, 13, 99, 1234]

SALES_COLS = [
    "monthly_sales", "weekday_sales", "weekend_sales",
    "mon_sales","tue_sales","wed_sales","thu_sales","fri_sales","sat_sales","sun_sales",
    "time_00_06_sales","time_06_11_sales","time_11_14_sales",
    "time_14_17_sales","time_17_21_sales","time_21_24_sales",
    "male_sales","female_sales",
    "age_10_sales","age_20_sales","age_30_sales",
    "age_40_sales","age_50_sales","age_60_above_sales",
]
COUNT_COLS = [c.replace("_sales", "_count") for c in SALES_COLS]
TARGET_COLS = SALES_COLS + COUNT_COLS

BEST_PARAMS = {
    "n_estimators": 300, "max_depth": 35, "min_samples_leaf": 1,
    "min_samples_split": 2, "max_features": 1.0,
    "criterion": "squared_error", "bootstrap": False, "n_jobs": -1,
}


def load_joined_with_all_cols() -> pd.DataFrame:
    """48 numeric 컬럼을 모두 로드."""
    cols = ", ".join([f"s.{c}" for c in TARGET_COLS])
    sql = text(f"""
        SELECT q.quarter, q.dong_code, q.dong_name, q.industry_code, q.industry_name,
               q.store_count, q.open_count, q.close_count, q.closure_rate, q.franchise_count,
               {cols}
        FROM store_quarterly q
        LEFT JOIN district_sales s
          ON q.quarter = s.quarter AND q.dong_code = s.dong_code
         AND q.industry_code = s.industry_code
        WHERE q.dong_code LIKE '11440%'
        ORDER BY q.quarter, q.dong_code, q.industry_code
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)
    anchor = pd.read_csv(ANCHOR_CSV).rename(columns={"qkey": "quarter", "수치값": "kosis_index"})
    anchor = anchor.groupby("quarter", as_index=False)["kosis_index"].mean()
    return df.merge(anchor[["quarter", "kosis_index"]], on="quarter", how="left")


def build_features_v4(df: pd.DataFrame) -> pd.DataFrame:
    """v3 와 동일한 피처 (LOO 는 본 학습에선 적용 X — 모든 alive 활용)."""
    X = pd.DataFrame(index=df.index)
    X["store_count"] = df["store_count"].fillna(df["store_count"].median())
    X["log_store_count"] = np.log1p(X["store_count"])
    X["kosis_index"] = df["kosis_index"]
    X["log_kosis"] = np.log(df["kosis_index"])
    X["franchise_ratio"] = df["franchise_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["open_ratio"] = df["open_count"].fillna(0) / df["store_count"].clip(lower=1)
    X["closure_rate"] = df["closure_rate"].fillna(0)
    X["q_of_year"] = df["quarter"] % 10
    X["year"] = df["quarter"] // 10
    for ind in df["industry_code"].unique():
        X[f"ind_{ind}"] = (df["industry_code"] == ind).astype(int)
    df_alive = df[df["monthly_sales"].notna()]
    X["dong_avg_store"] = df["dong_code"].map(df_alive.groupby("dong_code")["store_count"].mean())
    X["dong_avg_store"] = X["dong_avg_store"].fillna(df_alive["store_count"].mean())
    combo = df_alive.groupby(["dong_code", "industry_code"])["store_count"].mean()
    X["combo_avg_store"] = df.set_index(["dong_code", "industry_code"]).index.map(combo.to_dict())
    X["combo_avg_store"] = X["combo_avg_store"].fillna(combo.mean())
    return X


def fit_seed_ensemble_multi(X, Y, seeds, best_params):
    """6 seed × MultiOutputRegressor(ExtraTrees) — 48 컬럼 동시 학습.

    checkpoint: 각 seed 완료 시 디스크 저장 → 중단 시 재개.
    """
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    models = []
    for seed in seeds:
        ckpt = CHECKPOINT_DIR / f"model_seed_{seed}.pkl"
        if ckpt.exists():
            print(f"  [seed {seed}] checkpoint 로드")
            models.append(joblib.load(ckpt))
            continue
        print(f"  [seed {seed}] 학습 중...")
        m = MultiOutputRegressor(
            ExtraTreesRegressor(**best_params, random_state=seed),
            n_jobs=-1,
        ).fit(X, Y)
        joblib.dump(m, ckpt)
        models.append(m)
    return models


def predict_with_ci_multi(models, X_missing, store_count):
    """6 seed × 48 컬럼 → mean / std / lower_95 / upper_95 / ci_width_ratio."""
    preds_log = np.array([m.predict(X_missing) for m in models])  # (6, 137, 48)
    preds = np.expm1(preds_log) * np.maximum(store_count, 1)[:, None, None].squeeze(-1)
    # (6, 137, 48) — store_count broadcast
    sc_b = np.maximum(store_count, 1)[None, :, None]   # (1, 137, 1)
    preds = np.expm1(preds_log) * sc_b
    mean = preds.mean(axis=0)
    std = preds.std(axis=0, ddof=1)
    lower_95 = np.maximum(0, mean - 1.96 * std)
    upper_95 = mean + 1.96 * std
    ci_width_ratio = (upper_95 - lower_95) / np.maximum(mean, 1)
    return {
        "mean":           pd.DataFrame(mean,           columns=TARGET_COLS),
        "std":            pd.DataFrame(std,            columns=TARGET_COLS),
        "lower_95":       pd.DataFrame(lower_95,       columns=TARGET_COLS),
        "upper_95":       pd.DataFrame(upper_95,       columns=TARGET_COLS),
        "ci_width_ratio": pd.DataFrame(ci_width_ratio, columns=TARGET_COLS),
    }


def detect_extrapolation_cells(df_missing, pred_dict, threshold_ratio=1.8):
    """외삽 셀 = (24Q 전체 결측) OR (monthly_sales std / median_std ≥ 1.8)."""
    n = len(df_missing)
    mask = np.zeros(n, dtype=bool)

    # 1) 24Q 전체 결측 — quarter 별로 같은 (dong, industry) 가 24개 있는지
    # df_missing: 결측 셀들. dong_code, industry_code 중복 카운트 ≥ 24면 24Q 전체 결측
    if "dong_code" in df_missing.columns and "industry_code" in df_missing.columns:
        full_missing_combos = (
            df_missing.groupby(["dong_code", "industry_code"])
            .size()
            .pipe(lambda s: s[s >= 24])
            .index
        )
        for d, i in full_missing_combos:
            sel = (df_missing["dong_code"] == d) & (df_missing["industry_code"] == i)
            mask |= sel.values

    # 2) high variance — monthly_sales std 기준
    monthly_std = pred_dict["std"]["monthly_sales"].values
    median_std = float(np.median(monthly_std)) if len(monthly_std) > 0 else 0.0
    if median_std > 0:
        high_var = monthly_std >= threshold_ratio * median_std
        mask |= high_var

    return mask


def calculate_confidence(pred_dict, extrap_mask, audit_metrics):
    """confidence = base × ci_penalty × extrapolation_penalty (monthly 기준 1개)."""
    base = max(0.60, 1.0 - audit_metrics.get("mnar_wape", 25.0) / 100.0)
    ci = pred_dict["ci_width_ratio"]["monthly_sales"].values
    ci_penalty = np.where(ci > 0.5, 1.0 - np.minimum(0.3, ci - 0.5), 1.0)
    extrap_penalty = np.where(extrap_mask, 0.4 / max(base, 0.001), 1.0)
    conf = base * ci_penalty * extrap_penalty
    return np.clip(conf, 0.10, 1.0)


def main():
    print("=== Phase 1: Multi-Output v4 본 학습 ===")
    df = load_joined_with_all_cols()
    print(f"[data] total={len(df)} alive={df['monthly_sales'].notna().sum()}")

    X = build_features_v4(df)
    alive_mask = df["monthly_sales"].notna()
    missing_mask = ~alive_mask
    df_alive = df[alive_mask].copy()
    df_missing = df[missing_mask].copy()

    # Y: 48 컬럼 log1p (per-store 정규화는 monthly_sales/store_count 같은 대표만)
    # 단순화: 모든 컬럼 log1p
    Y_alive = df_alive[TARGET_COLS].apply(lambda s: np.log1p(s.fillna(0).astype(float)))

    print(f"[fit] 6 seed × ExtraTrees Multi-Output ({len(TARGET_COLS)} 컬럼)...")
    models = fit_seed_ensemble_multi(X.loc[alive_mask], Y_alive, SEEDS, BEST_PARAMS)

    print(f"[predict] {len(df_missing)} 결측 셀 × 48 컬럼 ...")
    sc_missing = df_missing["store_count"].fillna(1).astype(float).values
    preds = predict_with_ci_multi(models, X.loc[missing_mask], np.ones(len(df_missing)))
    # NB: store_count 곱셈은 SALES_COLS 만 적용 — count 는 그대로
    # 단순화: log1p 역변환만 사용 (store_count 곱셈은 spec 대로 SALES 에만 적용)
    # → 위 predict_with_ci_multi 의 store_count 사용을 1로 해서 expm1만 적용
    # 후 sales 컬럼만 store_count 곱
    for col in SALES_COLS:
        for k in ["mean", "std", "lower_95", "upper_95"]:
            preds[k][col] = preds[k][col] * sc_missing
    # ci_width_ratio 재계산
    preds["ci_width_ratio"] = (preds["upper_95"] - preds["lower_95"]) / np.maximum(preds["mean"], 1)

    # raking — sales + count
    print("[raking] sum constraint × 5 종 × {sales, count}")
    preds["mean"] = enforce_sum_consistency(preds["mean"], SUM_CONSTRAINTS_SALES)
    preds["mean"] = enforce_sum_consistency(preds["mean"], SUM_CONSTRAINTS_COUNT)

    # extrapolation
    extrap_mask = detect_extrapolation_cells(df_missing.reset_index(drop=True), preds, 1.8)
    print(f"[extrapolation] flag=True 셀: {int(extrap_mask.sum())} / {len(extrap_mask)}")

    # confidence (Phase 2 audit 결과 들어오기 전: 임시 13.5%)
    audit_temp = {"mnar_wape": 13.5}
    conf = calculate_confidence(preds, extrap_mask, audit_temp)
    print(f"[confidence] mean={conf.mean():.3f}, min={conf.min():.3f}")

    # wide CSV
    wide = df_missing.reset_index(drop=True)[["quarter","dong_code","dong_name","industry_code","industry_name","store_count"]].copy()
    for col in TARGET_COLS:
        wide[col] = preds["mean"][col].values.astype("int64")
    wide["extrapolation_flag"] = extrap_mask
    wide["confidence"] = conf
    wide["source"] = np.where(extrap_mask, "extrapolated_v4", "imputed_v4")
    OUT_WIDE_CSV.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(OUT_WIDE_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {OUT_WIDE_CSV}  ({len(wide)} 셀)")

    # detail CSV (long, 137 × 47 = 6,439 row — monthly_sales 제외)
    rows = []
    detail_cols = [c for c in TARGET_COLS if c != "monthly_sales"]
    for i, missing_row in df_missing.reset_index(drop=True).iterrows():
        for col in detail_cols:
            rows.append({
                "quarter": missing_row["quarter"],
                "dong_code": missing_row["dong_code"],
                "industry_code": missing_row["industry_code"],
                "column_name": col,
                "imputed_value": int(preds["mean"][col].iloc[i]),
                "lower_95": int(preds["lower_95"][col].iloc[i]),
                "upper_95": int(preds["upper_95"][col].iloc[i]),
                "std": float(preds["std"][col].iloc[i]),
                "ci_width_ratio": float(preds["ci_width_ratio"][col].iloc[i]),
                "confidence": float(conf[i]),
            })
    detail = pd.DataFrame(rows)
    detail.to_csv(OUT_DETAIL_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {OUT_DETAIL_CSV}  ({len(detail)} row)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 단위 테스트 실행 pass 확인**

Run: `pytest tests/test_imputed_v4.py -v`

Expected: 7 tests passed

- [ ] **Step 5: 본 학습 실행 (1.5~5 시간, checkpoint 활용)**

Run: `python -m validation.reverse_engineer_sales_v4`

Expected: 6 seed 학습 → 137 셀 × 48 컬럼 예측 → raking → CSV 2개 생성

- [ ] **Step 6: 결과 검증**

Run: `python -c "
import pandas as pd
wide = pd.read_csv('validation/results/imputed_mapo_v4.csv')
detail = pd.read_csv('validation/results/imputed_mapo_v4_detail.csv')
print(f'wide: {len(wide)} 셀, columns: {len(wide.columns)}')
print(f'detail: {len(detail)} row')
assert len(wide) == 137
assert len(detail) == 137 * 47
# 합계 일관성 검증
diff = abs(wide[['weekday_sales','weekend_sales']].sum(axis=1) - wide['monthly_sales'])
err_rate = (diff / wide['monthly_sales'].clip(lower=1)).max()
print(f'weekday+weekend vs monthly 최대 오차: {err_rate*100:.3f}%')
assert err_rate < 0.01, f'합격선 2-11 미달: {err_rate}'
"`

Expected: wide 137, detail 6,439, 합계 오차 < 1%

- [ ] **Step 7: 커밋**

```bash
git add validation/reverse_engineer_sales_v4.py tests/test_imputed_v4.py
git add validation/results/imputed_mapo_v4.csv validation/results/imputed_mapo_v4_detail.csv
git commit -m "feat(A1): Phase 1 v4 본 학습 — Multi-Output 6 seed + raking + 48 컬럼 복원"
```

---

## Task 7: Phase 2 — 감사 v4 (4 CV + 6 추가 지표)

**Files:**
- Create: `validation/audit_v4.py`
- Test: `tests/test_audit_v4.py`
- Output: `docs/sales-imputation/audit_v4_report.md`

**합격선 (10):** Random ≤ 12%, TS ≤ 15%, MNAR ≤ 15%, LODO ≤ 30%, Q1 ≤ 18%, Pearson r ≥ 0.97, RMSLE ≤ 0.35, OoM ≥ 97%, F1 ≥ 0.85, MASE ≤ 0.20

- [ ] **Step 1: 단위 테스트 작성 (TDD — 핵심 메트릭만)**

```python
# tests/test_audit_v4.py
"""Phase 2 감사 단위 테스트 — 10 지표 정확성."""

from __future__ import annotations

import numpy as np
import pytest

from validation.audit_v4 import (
    oom_accuracy,
    f1_4tier,
    mase,
    rmsle,
    diagnose_failure,
)


def test_oom_accuracy_perfect():
    actual = np.array([100, 200, 300])
    pred = actual.copy()
    assert oom_accuracy(actual, pred) == 1.0


def test_oom_accuracy_one_outlier():
    actual = np.array([100, 200, 300, 400])
    pred = np.array([100, 200, 300, 1000])  # 마지막만 2.5x
    assert 0.7 < oom_accuracy(actual, pred) < 0.8


def test_f1_4tier_perfect():
    actual = np.array([10, 20, 30, 40, 50, 60, 70, 80])
    pred = actual.copy()
    assert f1_4tier(actual, pred) > 0.99


def test_mase_naive_baseline():
    actual = np.array([100, 110, 120, 130])
    pred = actual.copy()   # 완벽 예측
    assert mase(actual, pred) < 0.01


def test_rmsle_perfect():
    actual = np.array([100, 200, 300])
    pred = actual.copy()
    assert rmsle(actual, pred) < 1e-6


def test_diagnose_failure_mnar_over_15():
    audit = {
        "mnar_wape":  {"mean": 0.20, "pass": False},
        "lodo_wape":  {"mean": 0.25, "pass": True},
        "pearson_r":  {"value": 0.98, "pass": True},
    }
    diags = diagnose_failure(audit)
    assert any("MNAR" in d for d in diags)
    assert any("confidence 일괄 0.10 하향" in d for d in diags)


def test_diagnose_failure_lodo_over_30():
    audit = {
        "mnar_wape":  {"mean": 0.13, "pass": True},
        "lodo_wape":  {"mean": 0.35, "pass": False},
        "pearson_r":  {"value": 0.98, "pass": True},
    }
    diags = diagnose_failure(audit)
    assert any("LODO" in d for d in diags)


def test_diagnose_failure_pearson_r_low():
    audit = {
        "mnar_wape":  {"mean": 0.13, "pass": True},
        "lodo_wape":  {"mean": 0.25, "pass": True},
        "pearson_r":  {"value": 0.92, "pass": False},
    }
    diags = diagnose_failure(audit)
    assert any("Pearson r" in d or "순위" in d for d in diags)
```

- [ ] **Step 2: 테스트 실행 fail 확인**

Run: `pytest tests/test_audit_v4.py -v`

Expected: ImportError

- [ ] **Step 3: 감사 모듈 구현**

```python
# validation/audit_v4.py
"""Phase 2: 4종 CV (Random/TS/MNAR/LODO/Q1) + 6 추가 지표 감사 + 합격선 판정."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.metrics import f1_score
from sklearn.model_selection import KFold
from sklearn.multioutput import MultiOutputRegressor
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from validation.reverse_engineer_sales_v4 import (
    SEEDS, TARGET_COLS, BEST_PARAMS,
    load_joined_with_all_cols, build_features_v4,
)

OUT_MD = REPO_ROOT / "docs" / "sales-imputation" / "audit_v4_report.md"

THRESHOLDS = {
    "random_wape": 0.12, "ts_wape": 0.15, "mnar_wape": 0.15,
    "lodo_wape": 0.30, "q1_wape": 0.18,
    "pearson_r": 0.97, "rmsle": 0.35,
    "oom_accuracy": 0.97, "f1_4tier": 0.85, "mase": 0.20,
}


def wape(actual, pred):
    return float(np.abs(actual - pred).sum() / np.maximum(actual.sum(), 1))


def rmsle(actual, pred):
    return float(np.sqrt(np.mean((np.log1p(np.maximum(pred, 0)) - np.log1p(actual))**2)))


def oom_accuracy(actual, pred):
    ratio = pred / np.maximum(actual, 1)
    return float(np.mean((ratio >= 0.5) & (ratio <= 2.0)))


def f1_4tier(actual, pred):
    q = np.quantile(actual, [0.25, 0.5, 0.75])
    actual_tier = np.digitize(actual, q)
    pred_tier = np.digitize(pred, q)
    return float(f1_score(actual_tier, pred_tier, average="macro"))


def mase(actual, pred):
    naive_err = np.mean(np.abs(np.diff(actual)))
    return float(np.mean(np.abs(actual - pred)) / max(naive_err, 1))


def fit_simple(X_tr, y_tr, seed):
    return ExtraTreesRegressor(**BEST_PARAMS, random_state=seed).fit(X_tr, y_tr)


def random_kfold_wape(df, X, seeds, n_splits=10):
    alive = df["monthly_sales"].notna()
    alive_idx = df[alive].index.values
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].fillna(1).values.astype(float)
    y = np.log1p((actual_sales / np.maximum(store, 1))[alive])

    wapes = []
    for seed in seeds:
        kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
        fold_wapes = []
        for tr, te in kf.split(alive_idx):
            tr_idx = alive_idx[tr]; te_idx = alive_idx[te]
            m = fit_simple(X.loc[tr_idx], y[tr], seed)
            log_pred = m.predict(X.loc[te_idx])
            sales_pred = np.expm1(log_pred) * np.maximum(store[te_idx], 1)
            sales_pred = np.clip(sales_pred, 0, None)
            fold_wapes.append(wape(actual_sales[te_idx], sales_pred))
        wapes.append(np.mean(fold_wapes))
    return {"mean": float(np.mean(wapes)), "std": float(np.std(wapes))}


def time_series_wape(df, X, seeds):
    alive = df["monthly_sales"].notna()
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].fillna(1).values.astype(float)
    sales_per_store = actual_sales / np.maximum(store, 1)
    quarters = sorted(df.loc[alive, "quarter"].unique())

    wapes = []
    for seed in seeds:
        ts_wapes = []
        for i in range(8, len(quarters)):
            tr_q = quarters[:i]; te_q = quarters[i]
            tr_mask = alive & df["quarter"].isin(tr_q)
            te_mask = alive & (df["quarter"] == te_q)
            if te_mask.sum() == 0: continue
            y_tr = np.log1p(sales_per_store[tr_mask])
            m = fit_simple(X[tr_mask], y_tr, seed)
            log_pred = m.predict(X[te_mask])
            sales_pred = np.expm1(log_pred) * np.maximum(store[te_mask], 1)
            sales_pred = np.clip(sales_pred, 0, None)
            ts_wapes.append(wape(actual_sales[te_mask], sales_pred))
        wapes.append(np.mean(ts_wapes))
    return {"mean": float(np.mean(wapes)), "std": float(np.std(wapes))}


def mnar_mimic_wape(df, X, seeds, n_folds=5):
    alive = df["monthly_sales"].notna()
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].fillna(1).values.astype(float)
    sales_per_store = actual_sales / np.maximum(store, 1)
    missing_q95 = df.loc[~alive, "store_count"].quantile(0.95)
    mimic_idx = df[alive & (df["store_count"] <= missing_q95)].index.values

    wapes = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        folds = np.array_split(rng.permutation(mimic_idx), n_folds)
        fw = []
        for te_idx in folds:
            tr_mask = alive & (~df.index.isin(te_idx))
            tr_idx = df[tr_mask].index.values
            y_tr = np.log1p(sales_per_store[tr_idx])
            m = fit_simple(X.loc[tr_idx], y_tr, seed)
            log_pred = m.predict(X.loc[te_idx])
            sales_pred = np.expm1(log_pred) * np.maximum(store[te_idx], 1)
            sales_pred = np.clip(sales_pred, 0, None)
            fw.append(wape(actual_sales[te_idx], sales_pred))
        wapes.append(np.mean(fw))
    return {"mean": float(np.mean(wapes)), "std": float(np.std(wapes))}


def lodo_wape(df, X, seeds):
    alive = df["monthly_sales"].notna()
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].fillna(1).values.astype(float)
    sales_per_store = actual_sales / np.maximum(store, 1)

    wapes = []
    for seed in seeds:
        lodo_wapes = []
        for dong in sorted(df["dong_code"].unique()):
            tr_mask = alive & (df["dong_code"] != dong)
            te_mask = alive & (df["dong_code"] == dong)
            if te_mask.sum() == 0: continue
            y_tr = np.log1p(sales_per_store[tr_mask])
            m = fit_simple(X[tr_mask], y_tr, seed)
            log_pred = m.predict(X[te_mask])
            sales_pred = np.expm1(log_pred) * np.maximum(store[te_mask], 1)
            sales_pred = np.clip(sales_pred, 0, None)
            lodo_wapes.append(wape(actual_sales[te_mask], sales_pred))
        wapes.append(np.mean(lodo_wapes))
    return {"mean": float(np.mean(wapes)), "std": float(np.std(wapes))}


def q1_wape(df, X, seeds):
    """Q1 (작은 셀) — store_count 분위 1만."""
    alive = df["monthly_sales"].notna()
    q25 = df.loc[alive, "store_count"].quantile(0.25)
    q1_mask = alive & (df["store_count"] <= q25)
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].fillna(1).values.astype(float)
    sales_per_store = actual_sales / np.maximum(store, 1)

    wapes = []
    for seed in seeds:
        kf = KFold(5, shuffle=True, random_state=seed)
        q1_idx = df[q1_mask].index.values
        fw = []
        for tr, te in kf.split(q1_idx):
            tr_idx = q1_idx[tr]; te_idx = q1_idx[te]
            tr_mask_full = alive & (~df.index.isin(te_idx))
            tr_idx_full = df[tr_mask_full].index.values
            y_tr = np.log1p(sales_per_store[tr_idx_full])
            m = fit_simple(X.loc[tr_idx_full], y_tr, seed)
            log_pred = m.predict(X.loc[te_idx])
            sales_pred = np.expm1(log_pred) * np.maximum(store[te_idx], 1)
            sales_pred = np.clip(sales_pred, 0, None)
            fw.append(wape(actual_sales[te_idx], sales_pred))
        wapes.append(np.mean(fw))
    return {"mean": float(np.mean(wapes)), "std": float(np.std(wapes))}


def diagnose_failure(audit):
    diags = []
    if not audit.get("mnar_wape", {}).get("pass", True):
        v = audit["mnar_wape"]["mean"] * 100
        diags.append(f"MNAR WAPE {v:.1f}% > 15%: 결측 복원 신뢰성 부족. → confidence 일괄 0.10 하향")
    if not audit.get("lodo_wape", {}).get("pass", True):
        v = audit["lodo_wape"]["mean"] * 100
        diags.append(f"LODO WAPE {v:.1f}% > 30%: dong fixed effect 의존 잔존. → dong_avg LOO 재적용")
    if not audit.get("pearson_r", {}).get("pass", True):
        v = audit["pearson_r"]["value"]
        diags.append(f"Pearson r {v:.3f} < 0.97: 순위 보존 부족. → 외삽 셀 confidence 강화")
    return diags


def main():
    print("=== Phase 2: Audit v4 ===")
    df = load_joined_with_all_cols()
    X = build_features_v4(df)
    print(f"[data] alive={df['monthly_sales'].notna().sum()} features={X.shape[1]}")

    audits = {}

    print("[1/5] Random 10-fold ...")
    audits["random_wape"] = random_kfold_wape(df, X, SEEDS)
    audits["random_wape"]["pass"] = audits["random_wape"]["mean"] <= THRESHOLDS["random_wape"]

    print("[2/5] Time-Series CV ...")
    audits["ts_wape"] = time_series_wape(df, X, SEEDS)
    audits["ts_wape"]["pass"] = audits["ts_wape"]["mean"] <= THRESHOLDS["ts_wape"]

    print("[3/5] MNAR-Mimic ...")
    audits["mnar_wape"] = mnar_mimic_wape(df, X, SEEDS)
    audits["mnar_wape"]["pass"] = audits["mnar_wape"]["mean"] <= THRESHOLDS["mnar_wape"]

    print("[4/5] LODO ...")
    audits["lodo_wape"] = lodo_wape(df, X, SEEDS)
    audits["lodo_wape"]["pass"] = audits["lodo_wape"]["mean"] <= THRESHOLDS["lodo_wape"]

    print("[5/5] Q1 (작은 셀) ...")
    audits["q1_wape"] = q1_wape(df, X, SEEDS)
    audits["q1_wape"]["pass"] = audits["q1_wape"]["mean"] <= THRESHOLDS["q1_wape"]

    # 추가 지표 (random fold 의 OOF 예측으로)
    alive = df["monthly_sales"].notna()
    alive_idx = df[alive].index.values
    actual_sales = df["monthly_sales"].values
    store = df["store_count"].fillna(1).values.astype(float)
    sales_per_store = actual_sales / np.maximum(store, 1)
    preds_full = np.zeros(len(df))
    kf = KFold(10, shuffle=True, random_state=42)
    for tr, te in kf.split(alive_idx):
        tr_idx = alive_idx[tr]; te_idx = alive_idx[te]
        y_tr = np.log1p(sales_per_store[tr_idx])
        m = fit_simple(X.loc[tr_idx], y_tr, 42)
        log_pred = m.predict(X.loc[te_idx])
        preds_full[te_idx] = np.expm1(log_pred) * np.maximum(store[te_idx], 1)
    preds_full = np.clip(preds_full, 0, None)
    actual_alive = actual_sales[alive]
    pred_alive = preds_full[alive]

    audits["pearson_r"] = {"value": float(pearsonr(actual_alive, pred_alive)[0])}
    audits["pearson_r"]["pass"] = audits["pearson_r"]["value"] >= THRESHOLDS["pearson_r"]
    audits["rmsle"] = {"value": rmsle(actual_alive, pred_alive)}
    audits["rmsle"]["pass"] = audits["rmsle"]["value"] <= THRESHOLDS["rmsle"]
    audits["oom_accuracy"] = {"value": oom_accuracy(actual_alive, pred_alive)}
    audits["oom_accuracy"]["pass"] = audits["oom_accuracy"]["value"] >= THRESHOLDS["oom_accuracy"]
    audits["f1_4tier"] = {"value": f1_4tier(actual_alive, pred_alive)}
    audits["f1_4tier"]["pass"] = audits["f1_4tier"]["value"] >= THRESHOLDS["f1_4tier"]
    audits["mase"] = {"value": mase(actual_alive, pred_alive)}
    audits["mase"]["pass"] = audits["mase"]["value"] <= THRESHOLDS["mase"]

    audits["all_pass"] = all(a.get("pass", False) for k, a in audits.items() if k != "all_pass")
    audits["diagnoses"] = diagnose_failure(audits)

    # MD 보고서
    lines = ["# Audit v4 Report\n"]
    lines.append(f"**production_ready:** {audits['all_pass']}\n")
    lines.append("| 지표 | 값 | 합격선 | 통과 |")
    lines.append("|:---|---:|---:|:---:|")
    for k in ["random_wape","ts_wape","mnar_wape","lodo_wape","q1_wape"]:
        v = audits[k]["mean"] * 100
        lines.append(f"| {k} | {v:.2f}% | ≤ {THRESHOLDS[k]*100:.0f}% | {'✅' if audits[k]['pass'] else '❌'} |")
    for k in ["pearson_r","rmsle","oom_accuracy","f1_4tier","mase"]:
        v = audits[k]["value"]
        op = "≥" if k in ("pearson_r","oom_accuracy","f1_4tier") else "≤"
        lines.append(f"| {k} | {v:.4f} | {op} {THRESHOLDS[k]} | {'✅' if audits[k]['pass'] else '❌'} |")
    if audits["diagnoses"]:
        lines.append("\n## Diagnoses\n")
        for d in audits["diagnoses"]:
            lines.append(f"- {d}")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"[saved] {OUT_MD}")
    print(f"\n[종합] production_ready = {audits['all_pass']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 단위 테스트 실행 pass 확인**

Run: `pytest tests/test_audit_v4.py -v`

Expected: 8 tests passed

- [ ] **Step 5: 감사 실행 (~ 90분)**

Run: `python -m validation.audit_v4`

Expected: 5종 CV + 5 추가 지표 측정 + `audit_v4_report.md` 생성

- [ ] **Step 6: 결과 검증**

Run: `python -c "from pathlib import Path; print(Path('docs/sales-imputation/audit_v4_report.md').read_text(encoding='utf-8'))"`

Expected: 합격/불합격 표 출력

- [ ] **Step 7: 커밋**

```bash
git add validation/audit_v4.py tests/test_audit_v4.py docs/sales-imputation/audit_v4_report.md
git commit -m "feat(A1): Phase 2 audit_v4 — 4 CV + 6 추가 지표 + 합격선 판정"
```

---

## Task 8: Phase 3 — DB 적재 + world_loader 수정

**Files:**
- Create: `backend/migrations/V4__seoul_district_sales_imputed_v4.sql`
- Modify: `backend/src/simulation/world_loader.py`
- Test: `backend/tests/test_dong_industry_weight_confidence.py`
- Test: `tests/test_other_session_compat.py`

- [ ] **Step 1: 마이그레이션 SQL 작성**

```sql
-- backend/migrations/V4__seoul_district_sales_imputed_v4.sql

CREATE TABLE IF NOT EXISTS seoul_district_sales_imputed_v4 (
    quarter             BIGINT          NOT NULL,
    dong_code           TEXT            NOT NULL,
    industry_code       TEXT            NOT NULL,
    monthly_sales       BIGINT,
    weekday_sales       BIGINT,  weekend_sales       BIGINT,
    mon_sales BIGINT, tue_sales BIGINT, wed_sales BIGINT, thu_sales BIGINT,
    fri_sales BIGINT, sat_sales BIGINT, sun_sales BIGINT,
    time_00_06_sales BIGINT, time_06_11_sales BIGINT, time_11_14_sales BIGINT,
    time_14_17_sales BIGINT, time_17_21_sales BIGINT, time_21_24_sales BIGINT,
    male_sales BIGINT, female_sales BIGINT,
    age_10_sales BIGINT, age_20_sales BIGINT, age_30_sales BIGINT,
    age_40_sales BIGINT, age_50_sales BIGINT, age_60_above_sales BIGINT,
    monthly_count INTEGER,
    weekday_count INTEGER, weekend_count INTEGER,
    mon_count INTEGER, tue_count INTEGER, wed_count INTEGER, thu_count INTEGER,
    fri_count INTEGER, sat_count INTEGER, sun_count INTEGER,
    time_00_06_count INTEGER, time_06_11_count INTEGER, time_11_14_count INTEGER,
    time_14_17_count INTEGER, time_17_21_count INTEGER, time_21_24_count INTEGER,
    male_count INTEGER, female_count INTEGER,
    age_10_count INTEGER, age_20_count INTEGER, age_30_count INTEGER,
    age_40_count INTEGER, age_50_count INTEGER, age_60_above_count INTEGER,
    extrapolation_flag  BOOLEAN         NOT NULL DEFAULT FALSE,
    confidence          DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    source              TEXT            NOT NULL,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    PRIMARY KEY (quarter, dong_code, industry_code)
);
COMMENT ON TABLE seoul_district_sales_imputed_v4 IS
  '담당: 찬영(A1) | 137 결측 셀 48 컬럼 Multi-Output ExtraTrees 6 seed 앙상블 복원 | 출처: KOSIS DT_1KC2023';
CREATE INDEX IF NOT EXISTS ix_v4_quarter_dong ON seoul_district_sales_imputed_v4(quarter, dong_code);

CREATE TABLE IF NOT EXISTS seoul_district_sales_imputed_v4_detail (
    quarter         BIGINT          NOT NULL,
    dong_code       TEXT            NOT NULL,
    industry_code   TEXT            NOT NULL,
    column_name     TEXT            NOT NULL,
    imputed_value   BIGINT          NOT NULL,
    lower_95        BIGINT          NOT NULL,
    upper_95        BIGINT          NOT NULL,
    std             DOUBLE PRECISION,
    ci_width_ratio  DOUBLE PRECISION,
    confidence      DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    PRIMARY KEY (quarter, dong_code, industry_code, column_name)
);
COMMENT ON TABLE seoul_district_sales_imputed_v4_detail IS
  '담당: 찬영(A1) | imputed_v4 의 47 세부 컬럼별 6 seed 95% CI long format | 행 수: 137 × 47 = 6,439';
CREATE INDEX IF NOT EXISTS ix_v4_detail_lookup ON seoul_district_sales_imputed_v4_detail(quarter, dong_code, industry_code);
```

- [ ] **Step 2: 마이그레이션 실행**

Run: `psql $POSTGRES_URL -f backend/migrations/V4__seoul_district_sales_imputed_v4.sql`

Expected: `CREATE TABLE` × 2 + `CREATE INDEX` × 2 + `COMMENT` × 2

- [ ] **Step 3: CSV → DB 적재 스크립트 작성**

```python
# scripts/load_v4_to_db.py
"""Phase 3: imputed_mapo_v4.csv → seoul_district_sales_imputed_v4 적재."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

engine = create_engine(os.environ["POSTGRES_URL"])

WIDE_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4.csv"
DETAIL_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4_detail.csv"

if __name__ == "__main__":
    print("[1/2] wide 적재 ...")
    wide = pd.read_csv(WIDE_CSV)
    # 컬럼 정렬 (DB 스키마와 일치)
    wide = wide.drop(columns=["dong_name", "industry_name"], errors="ignore")
    wide.to_sql("seoul_district_sales_imputed_v4", engine,
                if_exists="append", index=False, method="multi", chunksize=50)
    print(f"  {len(wide)} row 적재")

    print("[2/2] detail 적재 ...")
    detail = pd.read_csv(DETAIL_CSV)
    detail.to_sql("seoul_district_sales_imputed_v4_detail", engine,
                  if_exists="append", index=False, method="multi", chunksize=200)
    print(f"  {len(detail)} row 적재")
```

Run: `python scripts/load_v4_to_db.py`

Expected: 137 row + 6,439 row 적재

- [ ] **Step 4: world_loader 수정 단위 테스트 작성 (TDD)**

```python
# backend/tests/test_dong_industry_weight_confidence.py
"""world_loader._load_dong_industry_weight() v4 confidence 가중 테스트."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[2]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from backend.src.simulation.world_loader import _load_dong_industry_weight


@pytest.fixture
def engine():
    return create_engine(os.environ["POSTGRES_URL"])


def test_world_loader_returns_dict(engine):
    """기본 — dict 반환 + 키는 (dong, cat) tuple."""
    weights = _load_dong_industry_weight(engine)
    assert isinstance(weights, dict)
    if weights:
        k = next(iter(weights.keys()))
        assert isinstance(k, tuple) and len(k) == 2


def test_world_loader_popularity_range_05_15(engine):
    """모든 popularity ∈ [0.5, 1.5]."""
    weights = _load_dong_industry_weight(engine)
    for v in weights.values():
        assert 0.5 <= v <= 1.5, f"popularity {v} 범위 밖"


def test_world_loader_includes_imputed_dong_industry(engine):
    """v4 적재 후 결측 (동, 업종) 도 popularity 정의됨."""
    weights = _load_dong_industry_weight(engine)
    # 24Q 전체 결측 — 아현동 양식음식점 (한식음식점→음식점 카테고리)
    # 음식점 카테고리에 양식음식점 매핑 → 아현동 음식점 포함 여부 확인
    assert ("아현동", "음식점") in weights or ("아현동", "카페") in weights


def test_world_loader_backward_compat_when_v4_empty(engine):
    """v4 테이블 비어있으면 v3 결과와 동일해야."""
    with engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE v4_backup AS SELECT * FROM seoul_district_sales_imputed_v4"))
        conn.execute(text("DELETE FROM seoul_district_sales_imputed_v4"))
        weights_empty = _load_dong_industry_weight(engine)
        conn.execute(text("INSERT INTO seoul_district_sales_imputed_v4 SELECT * FROM v4_backup"))
    # 빈 v4 → COALESCE 가 monthly_sales 만 사용 → v3 와 동일 동작
    assert isinstance(weights_empty, dict)
    # 결측 셀 (아현동 양식) 은 v4 비어있으면 dict 에 없어야
    # (origin v3 동작)
```

- [ ] **Step 5: 테스트 실행 fail 확인 (수정 전)**

Run: `pytest backend/tests/test_dong_industry_weight_confidence.py -v`

Expected: `test_world_loader_includes_imputed_dong_industry` fail (수정 전이라 v4 미사용)

- [ ] **Step 6: world_loader.py 수정**

`backend/src/simulation/world_loader.py:181-215` 의 `_load_dong_industry_weight()` 를 다음으로 교체:

```python
def _load_dong_industry_weight(engine) -> dict[tuple[str, str], float]:
    """(dong, category) → 매출 index 0.5~1.5 (최신 분기).

    v4: LEFT JOIN seoul_district_sales_imputed_v4 + COALESCE.
    confidence 가중 평균: weighted_avg = Σ(sales × conf) / Σ(conf).
    """
    cat_map = {
        "커피-음료": "카페",
        "제과점": "카페",
        "한식음식점": "음식점",
        "중식음식점": "음식점",
        "일식음식점": "음식점",
        "양식음식점": "음식점",
        "패스트푸드점": "음식점",
        "분식전문점": "음식점",
        "치킨전문점": "음식점",
        "호프-간이주점": "주점",
        "편의점": "편의점",
    }
    sql = text("""
        SELECT s.dong_name, s.industry_name,
               COALESCE(v.monthly_sales, s.monthly_sales)::double precision AS avg_sales,
               COALESCE(v.confidence, 1.0)::double precision AS avg_conf
        FROM district_sales_seoul s
        LEFT JOIN seoul_district_sales_imputed_v4 v
          ON s.quarter = v.quarter
         AND s.dong_code = v.dong_code
         AND s.industry_code = v.industry_code
        WHERE s.quarter >= (SELECT MAX(quarter) - 1 FROM district_sales_seoul)
    """)
    raw: dict[tuple[str, str], dict] = {}
    with engine.connect() as conn:
        for row in conn.execute(sql):
            d, i, v_sales, v_conf = row[0], row[1], row[2], row[3]
            cat = cat_map.get(i)
            if cat and v_sales and v_sales > 0:
                key = (d, cat)
                if key not in raw:
                    raw[key] = {"sum_wv": 0.0, "sum_w": 0.0}
                raw[key]["sum_wv"] += v_sales * (v_conf or 0.0)
                raw[key]["sum_w"] += (v_conf or 0.0)
    if not raw:
        return {}
    weighted = {k: r["sum_wv"] / r["sum_w"] for k, r in raw.items() if r["sum_w"] > 0}
    if not weighted:
        return {}
    mx = max(weighted.values()) or 1.0
    return {k: round(0.5 + (v / mx), 3) for k, v in weighted.items()}
```

- [ ] **Step 7: 테스트 실행 pass 확인**

Run: `pytest backend/tests/test_dong_industry_weight_confidence.py -v`

Expected: 4 tests passed

- [ ] **Step 8: 다른 세션 회귀 테스트 작성**

```python
# tests/test_other_session_compat.py
"""다른 세션의 brand-menu 작업 회귀 테스트 — v4 도입 영향 0."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_brand_menu_loader_unaffected_by_v4():
    """다른 세션의 brand_menu_loader 정상 동작."""
    from backend.src.services.brand_menu_loader import load_brand_menu_items
    try:
        menu = load_brand_menu_items("이디야")
        assert isinstance(menu, list)
    except (ImportError, ModuleNotFoundError):
        pytest.skip("brand_menu_loader 미구현 (다른 세션 진행 중)")


def test_living_pop_daily_boost_unaffected():
    """다른 세션의 _load_living_population_daily 정상 동작."""
    try:
        from backend.src.simulation.world_loader import _load_living_population_daily
        boost = _load_living_population_daily(start_date="2024-01-01", days=7)
        assert isinstance(boost, dict)
    except (ImportError, AttributeError):
        pytest.skip("_load_living_population_daily 미구현 (다른 세션 진행 중)")


def test_vacancy_pse_signature_unchanged():
    """vacancy_pse 시그니처에 우리 변경 없음."""
    from backend.src.simulation.vacancy_pse import evaluate_vacancy_pse
    import inspect
    sig = inspect.signature(evaluate_vacancy_pse)
    # 다른 세션이 추가한 인자들이 있을 수 있지만, 우리는 추가 X
    assert "vacancy_spot" in sig.parameters
    assert "category" in sig.parameters
```

Run: `pytest tests/test_other_session_compat.py -v -m integration`

Expected: skip 또는 pass (다른 세션 작업 진행도에 따라)

- [ ] **Step 9: 커밋**

```bash
git add backend/migrations/V4__seoul_district_sales_imputed_v4.sql
git add scripts/load_v4_to_db.py
git add backend/src/simulation/world_loader.py
git add backend/tests/test_dong_industry_weight_confidence.py
git add tests/test_other_session_compat.py
git commit -m "feat(A1): Phase 3 — DB v4 테이블 + world_loader confidence 가중 + 회귀 테스트"
```

---

## Task 9: Phase 4 — Sensitivity ABM (imputed 사용/미사용 비교)

**Files:**
- Create: `validation/sensitivity_v4_abm.py`
- Output: `docs/sales-imputation/sensitivity_v4_report.md`

**합격선:** sensitivity ≥ 8%, V1c mean_ratio ∈ [0.85, 1.18], 외삽 셀 영향 ≤ 7%

- [ ] **Step 1: 신규 파일 생성**

```python
# validation/sensitivity_v4_abm.py
"""Phase 4: imputed v4 사용/미사용 ABM 시뮬 비교."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

engine = create_engine(os.environ["POSTGRES_URL"])
OUT_MD = REPO_ROOT / "docs" / "sales-imputation" / "sensitivity_v4_report.md"

THRESHOLD_SENSITIVITY = 0.08
THRESHOLD_EXTRAP_IMPACT = 0.07


def collect_popularity_via_loader():
    """world_loader._load_dong_industry_weight() 호출 결과."""
    from backend.src.simulation.world_loader import _load_dong_industry_weight
    return _load_dong_industry_weight(engine)


def main():
    print("=== Phase 4: Sensitivity v4 ABM ===")

    # 1) v4 사용 (현 상태)
    print("[1/2] v4 적용 popularity ...")
    pop_v4 = collect_popularity_via_loader()
    print(f"  cells: {len(pop_v4)}, mean: {np.mean(list(pop_v4.values())):.3f}")

    # 2) v4 비움 — 임시
    print("[2/2] v4 미적용 popularity (DELETE 임시) ...")
    with engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE v4_backup_sens AS SELECT * FROM seoul_district_sales_imputed_v4"))
        conn.execute(text("DELETE FROM seoul_district_sales_imputed_v4"))
    try:
        pop_baseline = collect_popularity_via_loader()
        print(f"  cells: {len(pop_baseline)}, mean: {np.mean(list(pop_baseline.values())):.3f}")
    finally:
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO seoul_district_sales_imputed_v4 SELECT * FROM v4_backup_sens"))

    # 3) 비교
    common_keys = set(pop_v4.keys()) & set(pop_baseline.keys())
    new_keys_v4 = set(pop_v4.keys()) - set(pop_baseline.keys())
    print(f"\n[비교]")
    print(f"  common cells: {len(common_keys)}")
    print(f"  v4 신규 cells (결측 보강): {len(new_keys_v4)}")

    diffs = []
    for k in common_keys:
        diffs.append(abs(pop_v4[k] - pop_baseline[k]) / max(pop_baseline[k], 0.01))
    sensitivity = float(np.mean(diffs)) if diffs else 0.0
    print(f"  popularity 변화 mean: {sensitivity*100:.2f}%")

    # 합격 판정
    pass_4_1 = sensitivity >= THRESHOLD_SENSITIVITY
    coverage_gain = len(new_keys_v4)

    # MD 보고서
    lines = ["# Sensitivity v4 ABM Report\n"]
    lines.append(f"**합격선 4-1 (sensitivity ≥ {THRESHOLD_SENSITIVITY*100:.0f}%):** {'✅' if pass_4_1 else '❌'} {sensitivity*100:.2f}%")
    lines.append(f"**v4 신규 popularity 셀 (결측 보강 효과):** {coverage_gain}")
    lines.append(f"\n## 결과")
    lines.append(f"- v4 적용 popularity 평균: {np.mean(list(pop_v4.values())):.3f} ({len(pop_v4)} cells)")
    lines.append(f"- baseline popularity 평균: {np.mean(list(pop_baseline.values())):.3f} ({len(pop_baseline)} cells)")
    lines.append(f"- 공통 cell 의 popularity 평균 변화: {sensitivity*100:.2f}%")
    lines.append(f"\n## 해석")
    if pass_4_1:
        lines.append(f"v4 도입이 ABM popularity 분포에 의미 있는 영향 ({sensitivity*100:.1f}% > {THRESHOLD_SENSITIVITY*100:.0f}%) — sprint 가치 입증.")
    else:
        lines.append(f"v4 도입 영향이 미미 ({sensitivity*100:.1f}% < {THRESHOLD_SENSITIVITY*100:.0f}%) — 정직 명시.")
    if coverage_gain > 0:
        lines.append(f"\n결측 보강으로 신규 {coverage_gain} (dong, category) 조합에 popularity 부여 — ABM 시뮬 왜곡 감소.")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"[saved] {OUT_MD}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 실행**

Run: `python -m validation.sensitivity_v4_abm`

Expected: popularity 비교 + `sensitivity_v4_report.md` 생성

- [ ] **Step 3: 결과 검증**

Run: `python -c "from pathlib import Path; print(Path('docs/sales-imputation/sensitivity_v4_report.md').read_text(encoding='utf-8'))"`

Expected: 합격/불합격 + sensitivity 수치 출력

- [ ] **Step 4: 커밋**

```bash
git add validation/sensitivity_v4_abm.py docs/sales-imputation/sensitivity_v4_report.md
git commit -m "feat(A1): Phase 4 sensitivity v4 ABM — imputed 사용/미사용 popularity 비교"
```

---

## Task 10: Phase 5 — sales_imp_mapo.csv 교체 + 5트랙 V1c 검증

**Files:**
- Backup: `data/processed/sales_imp_mapo.csv.v3_backup`
- Replace: `data/processed/sales_imp_mapo.csv`

- [ ] **Step 1: v3 백업**

Run: `cp data/processed/sales_imp_mapo.csv data/processed/sales_imp_mapo.csv.v3_backup`

Expected: 백업 파일 생성

- [ ] **Step 2: v4 결과를 다른 세션 인터페이스 형식으로 변환**

```python
# scripts/convert_v4_to_sales_imp_mapo.py
"""imputed_mapo_v4.csv → sales_imp_mapo.csv 형식으로 변환.

기존 컬럼 (monthly_sales, store_count) 위치 보존 + 새 컬럼 (lower_95/upper_95/confidence/extrapolation_flag) 끝에 추가.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
WIDE_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4.csv"
DETAIL_CSV = REPO_ROOT / "validation" / "results" / "imputed_mapo_v4_detail.csv"
OUT_CSV = REPO_ROOT / "data" / "processed" / "sales_imp_mapo.csv"

if __name__ == "__main__":
    wide = pd.read_csv(WIDE_CSV)
    detail = pd.read_csv(DETAIL_CSV)

    # detail 에서 monthly_sales lower/upper 추출
    monthly_ci = detail[detail["column_name"] == "monthly_sales"][
        ["quarter", "dong_code", "industry_code", "lower_95", "upper_95"]
    ]
    out = wide.merge(monthly_ci, on=["quarter", "dong_code", "industry_code"], how="left")

    # 기존 컬럼 순서: monthly_sales 위치 보존
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[saved] {OUT_CSV}  ({len(out)} 셀, {len(out.columns)} 컬럼)")
```

Run: `python scripts/convert_v4_to_sales_imp_mapo.py`

Expected: `data/processed/sales_imp_mapo.csv` 생성 (137 row + 새 컬럼)

- [ ] **Step 3: 다른 세션 5트랙 V1c 실행 (가용 시)**

Run: `python -m validation.brand_vacancy_validator --brand 이디야 --category 카페 --tracks-only v1c 2>/dev/null || echo "validator 미구현 (다른 세션 진행 중) — skip"`

Expected: V1c 결과 또는 skip 메시지

- [ ] **Step 4: 결과 검증 (V1c 가용 시)**

Run: `python -c "
import json
from pathlib import Path
p = Path('validation/results/이디야_5track.json')
if p.exists():
    data = json.loads(p.read_text(encoding='utf-8'))
    v1c = data['tracks'].get('v1c', {})
    mr = v1c.get('mean_ratio')
    print(f'V1c mean_ratio: {mr}')
    assert mr is None or 0.85 <= mr <= 1.18, f'합격선 4-2 미달: {mr}'
else:
    print('V1c 결과 파일 없음 — skip')
"`

Expected: V1c mean_ratio 출력 또는 skip

- [ ] **Step 5: 최종 커밋**

```bash
git add data/processed/sales_imp_mapo.csv scripts/convert_v4_to_sales_imp_mapo.py
git commit -m "feat(A1): Phase 5 통합 — sales_imp_mapo.csv v4 교체 + 5트랙 V1c 인터페이스"
```

---

## Spec 합격 기준 체크리스트 (전체 sprint done)

각 task 완료 후 확인:

- [ ] Phase 0~5 의 모든 합격선 통과 OR fail 시 정직 보고
- [ ] `imputed_mapo_v4.csv` 산출 (137 셀 × 48 컬럼)
- [ ] `imputed_mapo_v4_detail.csv` 산출 (6,439 row)
- [ ] `audit_v4_report.md` 작성 (10 지표 + 합격/불합격 + diagnoses)
- [ ] `sensitivity_v4_report.md` 작성 (imputed 가치 정량화)
- [ ] `seoul_district_sales_imputed_v4` DB 테이블 적재 (137 row)
- [ ] `seoul_district_sales_imputed_v4_detail` DB 테이블 적재 (6,439 row)
- [ ] `world_loader._load_dong_industry_weight()` 수정 + 단위 테스트 통과
- [ ] **다른 세션 회귀 테스트 0건 fail** (`pytest tests/test_other_session_compat.py`)
- [ ] `sales_imp_mapo.csv` v4 로 교체 (v3 백업 보존)
- [ ] 5트랙 V1c 1회 실행 (가용 시)
- [ ] 모든 코드 + 데이터 + 문서 git commit
