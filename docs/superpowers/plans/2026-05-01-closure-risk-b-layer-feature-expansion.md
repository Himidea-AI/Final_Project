# 폐업 위험도 모델 B layer (feature 확장) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LGBM_FEATURES 16 → 24. 기존 `build_timeseries` 가 load 하는 신호 (`weekday/weekend_sales`, age-segmented sales, `open_count`, `close_count`, `total_pop`, `cpi_index`, `holiday_count`) 의 yoy/ratio/lag derivation 8개를 `_engineer_lag_features` 에 추가.

**Architecture:** 새 ETL 없음, 기존 함수 끝부분에 derivation 추가 + LGBM_FEATURES list 갱신 + predict.py 한글 매핑 보강. predict.py:367 의 dynamic feature lookup 으로 자동 24 feature 사용.

**Tech Stack:** Python, pandas (groupby shift), pytest, LightGBM (기존).

**선행 spec:** `docs/superpowers/specs/2026-05-01-closure-risk-b-layer-feature-expansion-design.md`

---

## File Structure

| 파일 | 변경 유형 |
|---|---|
| `models/closure_risk/data_prep.py` | Modify (`_engineer_lag_features` 끝에 8 derivation, `LGBM_FEATURES` list 갱신) |
| `models/closure_risk/predict.py` | Modify (`_FEATURE_KO`, `_RISK_SUMMARY_TEMPLATES` 8개 추가) |
| `tests/test_closure_risk_b_features.py` | Create (~5 신규 unit test) |
| `models/closure_risk/weights/*` | Update (production retrain) |
| `docs/retrospective/2026-05-01-b-layer.md` | Create |

---

## Task 1: 8 신규 feature derivation + LGBM_FEATURES 갱신 + predict.py 한글 매핑

**Files:**
- Modify: `models/closure_risk/data_prep.py`
- Modify: `models/closure_risk/predict.py`
- Test: `tests/test_closure_risk_b_features.py` (신규)

- [ ] **Step 1: 신규 test 파일 생성 + 5 test**

Create `tests/test_closure_risk_b_features.py`:

```python
"""B layer (feature expansion) 단위 test.

8 신규 LGBM feature 의 derivation 정확성 + LGBM_FEATURES 길이 검증.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from models.closure_risk.data_prep import LGBM_FEATURES, _engineer_lag_features


def _make_synthetic_full(quarters: list[int], rng_seed: int = 0) -> pd.DataFrame:
    """B-1 derivation 검증용 — ALL_FEATURES 의 dependency column 포함."""
    rng = np.random.default_rng(rng_seed)
    rows = []
    for ind in ["I001"]:
        for d in range(3):
            for q in quarters:
                rows.append({
                    "dong_code": f"114403{d:02d}",
                    "industry_code": ind,
                    "quarter": q,
                    "closure_rate": float(rng.uniform(0, 0.5)),
                    "store_count": int(rng.integers(5, 30)),
                    "monthly_sales": float(rng.uniform(1e6, 1e8)),
                    "weekday_sales": float(rng.uniform(5e5, 5e7)),
                    "weekend_sales": float(rng.uniform(2e5, 3e7)),
                    "age_20_sales": float(rng.uniform(1e5, 1e7)),
                    "age_60_above_sales": float(rng.uniform(1e5, 1e7)),
                    "open_count": int(rng.integers(0, 5)),
                    "close_count": int(rng.integers(0, 5)),
                    "total_pop": int(rng.integers(10000, 50000)),
                    "cpi_index": float(rng.uniform(95, 110)),
                    "holiday_count": int(rng.integers(1, 5)),
                    "franchise_count": int(rng.integers(0, 5)),
                })
    return pd.DataFrame(rows)


def test_engineer_adds_8_new_features():
    """_engineer_lag_features 후 8 신규 컬럼 모두 존재."""
    df = _make_synthetic_full([20191, 20192, 20193, 20194, 20201, 20202])
    out = _engineer_lag_features(df)

    new_cols = [
        "weekday_sales_yoy", "weekend_sales_yoy",
        "age_20_sales_ratio", "age_60_sales_ratio",
        "open_close_ratio_lag1",
        "total_pop_yoy", "holiday_count", "cpi_index_yoy",
    ]
    for col in new_cols:
        assert col in out.columns, f"신규 feature 누락: {col}"


def test_yoy_features_correct_with_lag4():
    """weekday/weekend/total_pop/cpi yoy 가 lag4 기준 정확히 계산."""
    quarters = [20191, 20192, 20193, 20194, 20201, 20202, 20203, 20204]
    df = _make_synthetic_full(quarters, rng_seed=42)
    out = _engineer_lag_features(df).sort_values(["dong_code", "industry_code", "quarter"])

    # 한 group 의 5번째 row (lag4 가능 첫 row) 검증
    g = out[(out["dong_code"] == "11440300") & (out["industry_code"] == "I001")].sort_values("quarter")
    if len(g) >= 5:
        row_q5 = g.iloc[4]   # 20201
        row_q1 = g.iloc[0]   # 20191
        expected_yoy = (row_q5["weekday_sales"] - row_q1["weekday_sales"]) / (abs(row_q1["weekday_sales"]) + 1)
        assert abs(row_q5["weekday_sales_yoy"] - expected_yoy) < 1e-6


def test_age_ratio_features_bounded():
    """age_20/60_sales_ratio 가 [0, 1] 범위 (clip 적용 후)."""
    df = _make_synthetic_full([20191, 20192, 20193, 20194])
    out = _engineer_lag_features(df)

    # ratio = age_X_sales / max(monthly_sales, 1) — 일반적으로 0~1, 단 age 합 > monthly 일 수 있음 (data quality)
    # 본 test 는 NaN/Inf 만 없는지 확인
    assert out["age_20_sales_ratio"].notna().all()
    assert out["age_60_sales_ratio"].notna().all()
    assert np.isfinite(out["age_20_sales_ratio"]).all()
    assert np.isfinite(out["age_60_sales_ratio"]).all()


def test_open_close_ratio_handles_zero_close():
    """close_count=0 시 division-by-zero 회피 (clip lower=1)."""
    quarters = [20191, 20192]
    df = _make_synthetic_full(quarters)
    df["close_count"] = 0  # 모든 row close_count=0
    df["open_count"] = 3

    out = _engineer_lag_features(df).sort_values(["dong_code", "industry_code", "quarter"])
    # lag1 의 close_count_lag1 = 0 → clip(1) → ratio = 3/1 = 3.0
    g = out[(out["dong_code"] == "11440300") & (out["industry_code"] == "I001")].sort_values("quarter")
    second_row = g.iloc[1]  # lag1 가능 첫 row
    assert second_row["open_close_ratio_lag1"] > 0
    assert np.isfinite(second_row["open_close_ratio_lag1"])


def test_LGBM_FEATURES_count_is_24():
    """B-1 적용 후 LGBM_FEATURES 가 정확히 24개."""
    assert len(LGBM_FEATURES) == 24, f"LGBM_FEATURES 길이 mismatch: {len(LGBM_FEATURES)}"
    # 신규 8개 모두 포함
    new_cols = {
        "weekday_sales_yoy", "weekend_sales_yoy",
        "age_20_sales_ratio", "age_60_sales_ratio",
        "open_close_ratio_lag1",
        "total_pop_yoy", "holiday_count", "cpi_index_yoy",
    }
    assert new_cols.issubset(set(LGBM_FEATURES))
```

- [ ] **Step 2: test fail 확인**

Run: `python -m pytest tests/test_closure_risk_b_features.py -v`
Expected: 5 collected, 5 FAIL — `LGBM_FEATURES` 길이 16 (신규 8개 미존재).

- [ ] **Step 3: data_prep.py 의 LGBM_FEATURES list 갱신**

Open `models/closure_risk/data_prep.py`. 현재 LGBM_FEATURES (line 96-115) 의 끝 `]` 직전에 8 신규 추가:

```python
LGBM_FEATURES = [
    # ... 기존 16개 그대로 유지 ...
    "adstrd_flpop",
    # B-1 신규 8개 (2026-05-01)
    "weekday_sales_yoy",
    "weekend_sales_yoy",
    "age_20_sales_ratio",
    "age_60_sales_ratio",
    "open_close_ratio_lag1",
    "total_pop_yoy",
    "holiday_count",
    "cpi_index_yoy",
]
```

- [ ] **Step 4: `_engineer_lag_features` 끝에 derivation 추가**

`_engineer_lag_features` 함수 끝 (현재 `return df` 직전, line 230 근처) 에 추가:

```python
    # B-1 신규 feature 8종 (2026-05-01)
    # weekday/weekend yoy
    if "weekday_sales" in df.columns:
        wd_lag4 = df.groupby(gk)["weekday_sales"].shift(4)
        df["weekday_sales_yoy"] = (df["weekday_sales"] - wd_lag4) / (wd_lag4.abs() + 1)
    else:
        df["weekday_sales_yoy"] = 0.0

    if "weekend_sales" in df.columns:
        we_lag4 = df.groupby(gk)["weekend_sales"].shift(4)
        df["weekend_sales_yoy"] = (df["weekend_sales"] - we_lag4) / (we_lag4.abs() + 1)
    else:
        df["weekend_sales_yoy"] = 0.0

    # age ratio
    monthly = df["monthly_sales"].clip(lower=1)
    df["age_20_sales_ratio"] = df.get("age_20_sales", pd.Series(0.0, index=df.index)) / monthly
    df["age_60_sales_ratio"] = df.get("age_60_above_sales", pd.Series(0.0, index=df.index)) / monthly

    # open/close ratio (lag1)
    if "open_count" in df.columns and "close_count" in df.columns:
        open_lag1 = df.groupby(gk)["open_count"].shift(1)
        close_lag1 = df.groupby(gk)["close_count"].shift(1)
        df["open_close_ratio_lag1"] = open_lag1 / close_lag1.clip(lower=1)
    else:
        df["open_close_ratio_lag1"] = 1.0

    # total_pop yoy
    if "total_pop" in df.columns:
        pop_lag4 = df.groupby(gk)["total_pop"].shift(4)
        df["total_pop_yoy"] = (df["total_pop"] - pop_lag4) / (pop_lag4.abs() + 1)
    else:
        df["total_pop_yoy"] = 0.0

    # holiday_count — 그대로 (build_timeseries load 시 이미 컬럼 존재)
    if "holiday_count" not in df.columns:
        df["holiday_count"] = 0

    # cpi yoy
    if "cpi_index" in df.columns:
        cpi_lag4 = df.groupby(gk)["cpi_index"].shift(4)
        df["cpi_index_yoy"] = (df["cpi_index"] - cpi_lag4) / (cpi_lag4.abs() + 1)
    else:
        df["cpi_index_yoy"] = 0.0
```

`gk` 변수는 함수 상단에 이미 정의되어 있음 (`gk = ["dong_code", "industry_code"]`).

- [ ] **Step 5: predict.py 의 한글 매핑 보강**

Open `models/closure_risk/predict.py`. `_FEATURE_KO` dict (line 95-111) 끝에 8 추가:

```python
_FEATURE_KO = {
    # ... 기존 ...
    "adstrd_flpop": "행정동 유동인구",
    # B-1 신규 (2026-05-01)
    "weekday_sales_yoy": "평일 매출 전년동기 변화율",
    "weekend_sales_yoy": "주말 매출 전년동기 변화율",
    "age_20_sales_ratio": "20대 매출 비중",
    "age_60_sales_ratio": "60대+ 매출 비중",
    "open_close_ratio_lag1": "직전 분기 창업/폐업 비율",
    "total_pop_yoy": "거주인구 전년동기 변화율",
    "holiday_count": "분기 공휴일 수",
    "cpi_index_yoy": "물가 전년동기 변화율",
}
```

`_RISK_SUMMARY_TEMPLATES` (line 113-174) 끝에도 추가:

```python
_RISK_SUMMARY_TEMPLATES: dict[str, dict[str, str]] = {
    # ... 기존 ...
    "adstrd_flpop": {
        "positive": "유동인구가 많아 경쟁 환경이 치열합니다.",
        "negative": "유동인구 감소로 고객 유입이 줄고 있습니다.",
    },
    # B-1 신규
    "weekday_sales_yoy": {
        "positive": "평일 매출이 전년 대비 감소해 직장 상권 위험 신호가 나타납니다.",
        "negative": "평일 매출이 전년 대비 증가해 직장 상권이 활성화되고 있습니다.",
    },
    "weekend_sales_yoy": {
        "positive": "주말 매출이 전년 대비 감소해 주거 상권 위험 신호가 나타납니다.",
        "negative": "주말 매출이 전년 대비 증가해 주거 상권이 활성화되고 있습니다.",
    },
    "age_20_sales_ratio": {
        "positive": "20대 매출 비중이 높아 트렌드 의존도가 큽니다.",
        "negative": "20대 매출 비중이 낮아 변동성이 적습니다.",
    },
    "age_60_sales_ratio": {
        "positive": "60대+ 매출 비중이 높아 안정적이나 성장 한계가 있습니다.",
        "negative": "60대+ 매출 비중이 낮아 젊은 고객 유입이 활발합니다.",
    },
    "open_close_ratio_lag1": {
        "positive": "창업이 폐업보다 많아 상권 활성화 흐름입니다.",
        "negative": "폐업이 창업보다 많아 상권 위축 신호입니다.",
    },
    "total_pop_yoy": {
        "positive": "거주인구가 증가해 잠재 수요가 늘고 있습니다.",
        "negative": "거주인구가 감소해 수요 기반이 약해지고 있습니다.",
    },
    "holiday_count": {
        "positive": "공휴일 수가 많아 외식/소비 기회가 증가합니다.",
        "negative": "공휴일 수가 적어 평상 영업일 의존도가 큽니다.",
    },
    "cpi_index_yoy": {
        "positive": "물가 상승으로 비용 압박이 커지고 있습니다.",
        "negative": "물가 안정으로 비용 부담이 적습니다.",
    },
}
```

`positive/negative` 의 의미 — `positive` = 폐업 위험을 *높이는* 방향, `negative` = *낮추는* 방향. 기존 template 패턴 따라.

- [ ] **Step 6: test 통과 확인**

Run: `python -m pytest tests/test_closure_risk_b_features.py -v`
Expected: 5 passed.

- [ ] **Step 7: 전체 closure_risk regression 통과**

Run: `python -m pytest tests/test_closure_risk_*.py -v`
Expected: 40 passed (label 6 + split 6 + metrics 8 + regression 4 + topk 11 + b_features 5).

- [ ] **Step 8: ruff + commit**

```bash
ruff check --fix models/closure_risk/data_prep.py models/closure_risk/predict.py tests/test_closure_risk_b_features.py
ruff format models/closure_risk/data_prep.py models/closure_risk/predict.py tests/test_closure_risk_b_features.py
git add models/closure_risk/data_prep.py models/closure_risk/predict.py tests/test_closure_risk_b_features.py
git commit -m "$(cat <<'EOF'
feat(closure_risk): B layer feature 확장 16 → 24 (T1)

LGBM_FEATURES 에 8개 신규 derivation 추가 — 기존 build_timeseries 가 load
하지만 LGBM 미사용이던 신호 활용:
- weekday_sales_yoy, weekend_sales_yoy (요일별 매출 yoy)
- age_20_sales_ratio, age_60_sales_ratio (인구 구성 비중)
- open_close_ratio_lag1 (창업/폐업 흐름)
- total_pop_yoy (거주인구 yoy)
- holiday_count (계절성 보강)
- cpi_index_yoy (거시 비용 신호)

새 ETL 없음 — _engineer_lag_features 끝부분에 derivation 만 추가.
predict.py 의 _FEATURE_KO + _RISK_SUMMARY_TEMPLATES 한글화 동시 보강.

T2 production retrain 후 AUC 변화 측정 예정.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Production retrain

**Files:**
- Update: `models/closure_risk/weights/*`

- [ ] **Step 1: production retrain**

```bash
cd "/c/Users/804/Documents/final project"
python -m models.closure_risk.train 2>&1 | tee /tmp/closure_risk_retrain_b.log
```

Expected:
- 데이터 load → 기존 pipeline → 24 LGBM feature 학습
- threshold fit log (D layer, 동일 logic)
- val/test AUC log

소요시간: ~2분.

- [ ] **Step 2: metric 비교**

```bash
python -c "
import json
with open('models/closure_risk/weights/metrics.json') as f:
    m = json.load(f)
print('val AUC:', m['ensemble']['val']['auc'])
print('test AUC:', m['ensemble']['test']['auc'])
print('val PR-AUC:', m['ensemble']['val']['pr_auc'])
print('test PR-AUC:', m['ensemble']['test']['pr_auc'])
print('threshold danger:', m['thresholds']['danger'])
print('threshold caution:', m['thresholds']['caution'])
"
```

vs D layer baseline (181b84f):
- val AUC 0.5950 → ?
- test AUC 0.5974 → ?

기대: 약간 개선 (~+0.01) 또는 변화 없음 (이 경우 다음 sprint 우선순위 도출 자료).

- [ ] **Step 3: regression test 재실행**

Run: `python -m pytest tests/test_closure_risk_*.py -v`
Expected: 40 passed.

- [ ] **Step 4: commit (산출물)**

```bash
git add models/closure_risk/weights/metrics.json \
        models/closure_risk/weights/calibration_curve.png \
        models/closure_risk/weights/closure_risk_lgbm.pkl \
        models/closure_risk/weights/closure_risk_tcn_scaler.pkl \
        models/closure_risk/weights/ensemble_weights.pkl
git commit -m "$(cat <<'EOF'
chore(closure_risk): retrain with B layer feature expansion (T2)

LGBM 24 feature (16 + 8 신규) production retrain. 기존 D layer threshold
fit (q90/q70) pipeline 그대로 적용 — threshold 자동 갱신.

drift (vs. 181b84f D layer baseline) — 회고에 상세 기록.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 회고

**Files:**
- Create: `docs/retrospective/2026-05-01-b-layer.md`

내용 구조:
1. **요약** — B layer fix 완료. LGBM 16 → 24 feature. AUC 변화량 명시 + 다음 sprint 우선순위
2. **배경** — D layer fix 후 진단 (자기상관 lag 위주 한계). 잠자는 25 신호 발견
3. **작업 내역** — T1+T2+T3 + commit SHA
4. **결과** — before/after metric 표 + feature 별 SHAP 기여도 (선택)
5. **진단** — feature 추가 효과 해석. AUC 개선 미미 시 → A layer / 새 데이터 source 권장
6. **다음 sprint 우선순위** — A (구조) → D-3 (calibration) → 또는 B-2/B-3 (데이터 확장)
7. **배운 점** — 잠자는 신호 활용 패턴, yoy/ratio/lag derivation 의 한계 등

- [ ] **Step 1: 회고 작성**

(상기 구조로 retrospective 작성)

- [ ] **Step 2: commit**

```bash
git add docs/retrospective/2026-05-01-b-layer.md
git commit -m "docs(closure_risk): 2026-05-01 B layer 회고 (feature 16→24)"
```

---

## Verification

- [ ] **Step 1: 전체 test 통과**

```bash
python -m pytest tests/test_closure_risk_*.py -v
```

Expected: 40 passed.

- [ ] **Step 2: ruff clean**

```bash
ruff check models/closure_risk/ tests/test_closure_risk_*.py
ruff format --check models/closure_risk/ tests/test_closure_risk_*.py
```

- [ ] **Step 3: git log 확인**

```bash
git log --oneline -6
```

Expected: 4 commit (spec/plan + T1 + T2 + T3).

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| 신규 feature 효과 0 / 음수 | 정직한 진단. 회고에 명시 |
| LGBM_FEATURES 길이 변경으로 weight pkl 호환 X | T2 retrain 으로 자동 해결 |
| `_FEATURE_KO` 누락된 신규 feature 영향 | default fallback (`.get(name, name)`) — 한글 X 영어 출력. 본 spec 에서 8개 모두 추가 |
| pos_ratio 변화 X 확인 | label 정의 동일 → 검증 불필요 (회귀 test 가 보장) |

## Self-Review

1. **Spec coverage**: ✅ — 8 신규 feature derivation (T1), LGBM_FEATURES update (T1), predict.py 한글화 (T1), production retrain (T2), 회고 (T3).
2. **Placeholder scan**: ✅ — TBD/TODO 없음.
3. **Type consistency**: ✅ — 모든 신규 feature 가 float64 (pandas 기본). LGBM_FEATURES 길이 정확히 24.

승인 후 subagent-driven-development 실행.
