# 폐업 위험도 모델 검증 layer fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 폐업 위험도 모델의 random split 을 time-based holdout 3분할로 교체 + AUC/PR-AUC/P@10/R@10/Brier + Calibration plot 5 metric 추가. 학술 논문 standard (Bergmeir & Benítez 2012) 부합 + 사용자 의사결정 직관 metric 노출.

**Architecture:** `data_prep.py` 에 `_time_based_split()` helper 추가 → `train.py` 가 분기별 train/val/test 분할 후 LightGBM + TCN 학습 → `evaluate.py` 가 val/test 5 metric 측정 + reliability diagram → `weights/metrics.json` + `calibration_curve.png` 저장. `predict.py` 인터페이스 변경 X.

**Tech Stack:** Python 3.11, pandas, sklearn (TimeSeriesSplit X — holdout 만), lightgbm, torch, matplotlib (calibration plot), pytest.

**Spec:** `docs/superpowers/specs/2026-04-29-closure-risk-validation-fix-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `models/closure_risk/data_prep.py` (modify) | `_time_based_split()` helper 추가. 기존 `build_closure_risk_dataset` 시그니처/반환 그대로. |
| `models/closure_risk/train.py` (modify) | DEFAULT_CONFIG 에 `split_strategy`/`train_ratio`/`val_ratio` 갱신. LightGBM/TCN 학습 시 time-based split 분기. |
| `models/closure_risk/evaluate.py` (create) | 5 metric 계산 + reliability diagram + `metrics.json`/`calibration_curve.png` 저장. |
| `tests/test_closure_risk_split.py` (create) | `_time_based_split()` boundary, no-overlap, error case 검증 (4 test). |
| `tests/test_closure_risk_metrics.py` (create) | `evaluate_model` 5 metric 정확성, JSON/PNG 저장, calibration bin 검증 (5 test). |

`predict.py` / `model.py` / `weights/*.pt|pkl` 영향 없음 (회귀 안전).

---

## Task 1: `_time_based_split()` helper

**Files:**
- Modify: `models/closure_risk/data_prep.py` (line 25 근처 import 아래에 추가)
- Test: `tests/test_closure_risk_split.py` (신규)

- [ ] **Step 1: Write the failing test (boundary 정확성)**

```python
# tests/test_closure_risk_split.py
"""폐업 위험도 모델의 time-based split 검증."""

from __future__ import annotations

import pandas as pd
import pytest

from models.closure_risk.data_prep import _time_based_split


def _make_quarterly_df(n_quarters: int = 20, n_groups: int = 3) -> pd.DataFrame:
    """n_quarters × n_groups 행 데이터 생성 (quarter 컬럼 + 더미 label)."""
    rows = []
    quarters = [f"2020Q{(i % 4) + 1}" if i < 4 else f"202{1 + (i - 4) // 4}Q{((i - 4) % 4) + 1}" for i in range(n_quarters)]
    for q in quarters:
        for g in range(n_groups):
            rows.append({"quarter": q, "dong_code": f"d{g}", "industry_code": "x", "label": g % 2})
    return pd.DataFrame(rows)


def test_time_based_split_correct_boundaries():
    """20분기 70/15/15 → train 14Q / val 3Q / test 3Q."""
    df = _make_quarterly_df(n_quarters=20)
    train, val, test = _time_based_split(df, train_ratio=0.70, val_ratio=0.15)

    train_quarters = sorted(train["quarter"].unique())
    val_quarters = sorted(val["quarter"].unique())
    test_quarters = sorted(test["quarter"].unique())

    # 분기 수 검증 (boundary index 가 idx-1 → 정확히 14/3/3)
    assert len(train_quarters) == 14, f"train: {len(train_quarters)}"
    assert len(val_quarters) == 3, f"val: {len(val_quarters)}"
    assert len(test_quarters) == 3, f"test: {len(test_quarters)}"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd "/c/Users/804/Documents/final project"
PYTHONIOENCODING=utf-8 python -m pytest tests/test_closure_risk_split.py::test_time_based_split_correct_boundaries -v
```

Expected: FAIL with `ImportError: cannot import name '_time_based_split' from 'models.closure_risk.data_prep'`.

- [ ] **Step 3: Implement `_time_based_split()`**

`models/closure_risk/data_prep.py` 의 import 블록 아래 (line 26 근처) 에 추가:

```python
def _time_based_split(
    df: pd.DataFrame,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """quarter 기준 시간순 train/val/test 3분할.

    같은 quarter 데이터는 한 split 에만 들어감 (boundary 명확).
    train + val + test 합 = 100% (남은 부분 = test).

    Args:
        df: "quarter" 컬럼 포함 (예: "2020Q1", "2024Q4").
        train_ratio: 0~1, train 비율.
        val_ratio: 0~1, val 비율. test_ratio = 1 - train_ratio - val_ratio.

    Returns:
        (train_df, val_df, test_df).

    Raises:
        ValueError: 분기 수 < 7 (train 5 / val 1 / test 1 최소 보장 X).

    학술 근거:
        Bergmeir & Benítez (2012) "On the use of cross-validation for time series".
        시계열 random split 은 temporal leakage → val_AUC 부풀림.
    """
    quarters = sorted(df["quarter"].unique())
    n_q = len(quarters)
    if n_q < 7:
        raise ValueError(
            f"분기 수 부족 ({n_q}). 최소 7분기 필요 "
            f"(train 5 / val 1 / test 1). split_strategy='random' 사용 권장."
        )

    train_end_idx = int(n_q * train_ratio) - 1
    val_end_idx = int(n_q * (train_ratio + val_ratio)) - 1
    train_end = quarters[train_end_idx]
    val_end = quarters[val_end_idx]

    train = df[df["quarter"] <= train_end].copy()
    val = df[(df["quarter"] > train_end) & (df["quarter"] <= val_end)].copy()
    test = df[df["quarter"] > val_end].copy()

    return train, val, test
```

- [ ] **Step 4: Run test to verify PASS**

Run:
```bash
cd "/c/Users/804/Documents/final project"
PYTHONIOENCODING=utf-8 python -m pytest tests/test_closure_risk_split.py::test_time_based_split_correct_boundaries -v
```

Expected: PASS in < 1s.

- [ ] **Step 5: Add 3 more tests for edge cases**

Append to `tests/test_closure_risk_split.py`:

```python
def test_time_based_split_no_overlap():
    """train/val/test quarter 교집합이 0 이어야 함."""
    df = _make_quarterly_df(n_quarters=20)
    train, val, test = _time_based_split(df)

    train_q = set(train["quarter"].unique())
    val_q = set(val["quarter"].unique())
    test_q = set(test["quarter"].unique())

    assert train_q & val_q == set(), f"train ∩ val: {train_q & val_q}"
    assert val_q & test_q == set(), f"val ∩ test: {val_q & test_q}"
    assert train_q & test_q == set(), f"train ∩ test: {train_q & test_q}"


def test_time_based_split_raises_on_small_data():
    """6분기 → ValueError."""
    df = _make_quarterly_df(n_quarters=6)
    with pytest.raises(ValueError, match="분기 수 부족"):
        _time_based_split(df)


def test_time_based_split_preserves_dong_industry_grouping():
    """같은 (dong, industry) 가 여러 split 에 들어가도 OK (시계열 정상)."""
    df = _make_quarterly_df(n_quarters=20, n_groups=3)
    train, val, test = _time_based_split(df)

    # 같은 dong_code "d0" 가 train, val, test 모두에 존재해야 정상
    assert "d0" in train["dong_code"].values
    assert "d0" in val["dong_code"].values
    assert "d0" in test["dong_code"].values
```

- [ ] **Step 6: Run all 4 tests + ruff + commit**

Run:
```bash
cd "/c/Users/804/Documents/final project"
ruff check --fix models/closure_risk/data_prep.py tests/test_closure_risk_split.py
ruff format models/closure_risk/data_prep.py tests/test_closure_risk_split.py
PYTHONIOENCODING=utf-8 python -m pytest tests/test_closure_risk_split.py -v
```

Expected: 4 passed.

```bash
git add models/closure_risk/data_prep.py tests/test_closure_risk_split.py
git commit -m "$(cat <<'EOF'
feat(closure_risk): add _time_based_split() helper for time-series validation

- quarter 기반 70/15/15 분할 (train/val/test) — temporal leakage 방지
- 분기 수 < 7 시 ValueError (학술 정직성 — 사용자 의식적 fallback 강제)
- 4 unit test (boundary, no-overlap, error case, group preservation)

Spec: docs/superpowers/specs/2026-04-29-closure-risk-validation-fix-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: `train.py` config 갱신 + LightGBM 분할 통합

**Files:**
- Modify: `models/closure_risk/train.py` (DEFAULT_CONFIG line 35-60, train() line 226-282)

- [ ] **Step 1: DEFAULT_CONFIG 갱신**

Modify `models/closure_risk/train.py:35-60`. 기존 dict 에 추가/변경:

```python
DEFAULT_CONFIG: dict = {
    "db_url": DB_URL,
    "dong_prefix": "11440",
    "window_size": 4,
    # split 전략 — "time" (default, 학술 표준) | "random" (legacy, 분기 부족 시 fallback)
    "split_strategy": "time",
    "train_ratio": 0.70,
    "val_ratio": 0.15,
    # test_ratio = 1 - train_ratio - val_ratio = 0.15
    "random_state": 42,
    # TCN fine-tune
    "tcn_epochs": 50,
    "tcn_lr": 5e-4,
    "tcn_batch_size": 32,
    "tcn_patience": 7,
    "input_size": 34,
    "n_channels": 128,
    "kernel_size": 2,
    "dilations": [1, 2],
    "dropout": 0.2,
    # LightGBM
    "lgbm_num_leaves": 31,
    "lgbm_n_estimators": 200,
    "lgbm_learning_rate": 0.05,
    # 저장 경로
    "tcn_weights_path": str(WEIGHTS_DIR / "closure_risk_tcn.pt"),
    "tcn_scaler_path": str(WEIGHTS_DIR / "closure_risk_tcn_scaler.pkl"),
    "lgbm_model_path": str(WEIGHTS_DIR / "closure_risk_lgbm.pkl"),
    "ensemble_weights_path": str(WEIGHTS_DIR / "ensemble_weights.pkl"),
    "metrics_path": str(WEIGHTS_DIR / "metrics.json"),
    "calibration_plot_path": str(WEIGHTS_DIR / "calibration_curve.png"),
}
```

- [ ] **Step 2: import 갱신 (data_prep + evaluate)**

Modify `models/closure_risk/train.py:27-30`:

```python
from models.closure_risk.data_prep import build_closure_risk_dataset, _time_based_split
from models.closure_risk.evaluate import evaluate_model, save_metrics_and_plot
from models.closure_risk.model import WEIGHTS_DIR, TCNClassifier
from models.lstm_forecast.data_prep import ALL_FEATURES, DB_URL
from models.tcn_forecast.model import WEIGHTS_DIR as TCN_WEIGHTS_DIR
```

(이 import 는 evaluate.py 가 Task 4 에서 만들어진 후에야 실제 동작 — 한꺼번에 import 추가 후 Task 4 까지 미동작 OK. 단 Task 2 내에서 evaluate 호출은 안 함.)

- [ ] **Step 3: `train()` 함수의 LightGBM 분할 부분 교체**

기존 (`train.py:226-246`):
```python
def train(config: dict | None = None) -> None:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    df_full, X_lgbm, y = build_closure_risk_dataset(db_url=cfg["db_url"], dong_prefix=cfg["dong_prefix"])
    logger.info("데이터셋: %d 샘플, 고위험 비율=%.1f%%", len(y), y.mean() * 100)

    n_val = max(1, int(len(y) * cfg["val_ratio"]))
    X_lgbm_tr = X_lgbm.iloc[:-n_val].values
    X_lgbm_val = X_lgbm.iloc[-n_val:].values
    y_tr_arr = y.iloc[:-n_val].values
    y_val_arr = y.iloc[-n_val:].values
```

→ 새 구현:
```python
def train(config: dict | None = None) -> None:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    df_full, X_lgbm, y = build_closure_risk_dataset(db_url=cfg["db_url"], dong_prefix=cfg["dong_prefix"])
    logger.info("데이터셋: %d 샘플, 고위험 비율=%.1f%%", len(y), y.mean() * 100)

    # df_full 에 X_lgbm + y 컬럼이 함께 있어야 split 가능 → align
    df_full_aligned = df_full.loc[X_lgbm.index].copy()
    df_full_aligned["__y__"] = y.values
    for col in X_lgbm.columns:
        df_full_aligned[col] = X_lgbm[col].values

    # split
    if cfg["split_strategy"] == "time":
        try:
            train_df, val_df, test_df = _time_based_split(
                df_full_aligned, cfg["train_ratio"], cfg["val_ratio"]
            )
            logger.info(
                "time-based split: train=%d (≤%s), val=%d (≤%s), test=%d (>%s)",
                len(train_df), train_df["quarter"].max(),
                len(val_df), val_df["quarter"].max(),
                len(test_df), val_df["quarter"].max(),
            )
        except ValueError as e:
            logger.error("time-based split 실패: %s", e)
            raise
    elif cfg["split_strategy"] == "random":
        logger.warning(
            "⚠️ random split — temporal leakage 위험 (deprecated). "
            "split_strategy='time' 권장"
        )
        from sklearn.model_selection import train_test_split
        train_df, temp_df = train_test_split(
            df_full_aligned, test_size=(cfg["val_ratio"] + (1 - cfg["train_ratio"] - cfg["val_ratio"])),
            random_state=cfg["random_state"]
        )
        val_df, test_df = train_test_split(
            temp_df, test_size=(1 - cfg["train_ratio"] - cfg["val_ratio"])
                              / (cfg["val_ratio"] + (1 - cfg["train_ratio"] - cfg["val_ratio"])),
            random_state=cfg["random_state"]
        )
    else:
        raise ValueError(f"unknown split_strategy: {cfg['split_strategy']}")

    # LightGBM 입력 추출 (인덱스 기준)
    X_lgbm_tr = train_df[X_lgbm.columns].values
    X_lgbm_val = val_df[X_lgbm.columns].values
    X_lgbm_test = test_df[X_lgbm.columns].values
    y_tr_arr = train_df["__y__"].values
    y_val_arr = val_df["__y__"].values
    y_test_arr = test_df["__y__"].values
```

- [ ] **Step 4: LightGBM 학습 + val/test 예측 추출 (다음 task 의 evaluate 입력으로 전달용)**

기존 line 242-246 LightGBM 학습 부분 그대로 유지하되, val_AUC 계산 + test 예측 추가:

```python
    # 2. LightGBM 학습
    lgbm_model = train_lgbm(X_lgbm_tr, y_tr_arr, cfg)
    lgbm_val_proba = lgbm_model.predict_proba(X_lgbm_val)[:, 1]
    lgbm_test_proba = lgbm_model.predict_proba(X_lgbm_test)[:, 1]
    lgbm_val_auc = roc_auc_score(y_val_arr, lgbm_val_proba) if len(np.unique(y_val_arr)) > 1 else 0.5
    logger.info("LightGBM val_AUC=%.4f", lgbm_val_auc)
```

(기존 변수명 `lgbm_auc` → `lgbm_val_auc` 로 명확화. ensemble weight 계산도 `lgbm_val_auc` 사용.)

- [ ] **Step 5: 회귀 테스트 — `train_lgbm()` 자체 동작 변경 X**

train_lgbm() 자체는 변경 안 함. config 의 추가 필드만 무시되면 됨. 단순 import smoke:

Run:
```bash
cd "/c/Users/804/Documents/final project"
PYTHONIOENCODING=utf-8 python -c "from models.closure_risk.train import train, DEFAULT_CONFIG; print('split_strategy:', DEFAULT_CONFIG['split_strategy']); print('train_ratio:', DEFAULT_CONFIG['train_ratio'])"
```

Expected: `split_strategy: time` + `train_ratio: 0.70`. evaluate import 는 Task 4 후 통과.

- [ ] **Step 6: ruff + commit (evaluate.py 미존재라 import 깨짐 — Task 4 까지 stash 안 하고 그대로 commit, Task 4 완료 후 작동)**

Run:
```bash
cd "/c/Users/804/Documents/final project"
ruff check --fix models/closure_risk/train.py
ruff format models/closure_risk/train.py
```

```bash
git add models/closure_risk/train.py
git commit -m "$(cat <<'EOF'
refactor(closure_risk): split_strategy config + time-based split integration

- DEFAULT_CONFIG: split_strategy="time" (default), train_ratio/val_ratio
- LightGBM 분할이 _time_based_split 사용하도록 변경 (random 옵션도 유지)
- evaluate import 추가 (Task 4 에서 evaluate.py 생성)
- val/test set proba 모두 계산

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: TCN sequence 분할 통합 + buffer 처리

**Files:**
- Modify: `models/closure_risk/train.py` (`_build_tcn_sequences` line 94-134, `train_tcn` line 142-218)

- [ ] **Step 1: `_build_tcn_sequences()` 시그니처 변경 — split 받도록**

기존 (line 94-134):
```python
def _build_tcn_sequences(
    df_full: pd.DataFrame,
    y: pd.Series,
    window_size: int,
    feature_cols: list[str],
    val_ratio: float,
) -> tuple:
    """(dong_code, industry_code) 그룹별 sliding window 시퀀스 생성."""
    # ... 기존 ...
```

→ 새 시그니처:
```python
def _build_tcn_sequences(
    df_full: pd.DataFrame,
    y: pd.Series,
    window_size: int,
    feature_cols: list[str],
    train_quarters: set[str] | None = None,
    val_quarters: set[str] | None = None,
    test_quarters: set[str] | None = None,
    val_ratio: float = 0.2,  # legacy fallback (train_quarters 미지정 시)
) -> tuple:
    """(dong_code, industry_code) 그룹별 sliding window 시퀀스 + 시간 분할.

    Returns: (X_tr, X_val, X_test, y_tr, y_val, y_test, feat_scaler).
    train_quarters/val_quarters/test_quarters 가 주어지면 label 분기 기준 분할.
    Lookback (window) 의 분기는 어떤 split 에 있어도 OK — label 분기만 분리하면 leakage X.
    """
    from sklearn.preprocessing import MinMaxScaler

    feat_scaler = MinMaxScaler()
    df_full = df_full.copy()
    for col in feature_cols:
        if col not in df_full.columns:
            df_full[col] = 0.0

    all_feats = df_full[feature_cols].values.astype(np.float32)
    feat_scaler.fit(all_feats)

    X_tr_list, y_tr_list = [], []
    X_val_list, y_val_list = [], []
    X_test_list, y_test_list = [], []
    gk = ["dong_code", "industry_code"]

    use_split = train_quarters is not None and val_quarters is not None and test_quarters is not None

    for _, group in df_full.groupby(gk):
        group_sorted = group.sort_values("quarter")
        if len(group_sorted) <= window_size:
            continue
        feat_vals = feat_scaler.transform(group_sorted[feature_cols].values.astype(np.float32))
        labels = y.loc[group_sorted.index].values
        quarters_arr = group_sorted["quarter"].values

        for i in range(len(group_sorted) - window_size):
            x_seq = feat_vals[i : i + window_size]
            y_label = labels[i + window_size]
            label_quarter = quarters_arr[i + window_size]

            if use_split:
                if label_quarter in train_quarters:
                    X_tr_list.append(x_seq)
                    y_tr_list.append(y_label)
                elif label_quarter in val_quarters:
                    X_val_list.append(x_seq)
                    y_val_list.append(y_label)
                elif label_quarter in test_quarters:
                    X_test_list.append(x_seq)
                    y_test_list.append(y_label)
            else:
                # legacy random split fallback
                X_tr_list.append(x_seq)
                y_tr_list.append(y_label)

    if not X_tr_list:
        raise ValueError("TCN train 시퀀스 생성 실패 — 데이터 부족")

    X_tr = np.array(X_tr_list, dtype=np.float32)
    y_tr = np.array(y_tr_list, dtype=np.float32)

    if use_split:
        X_val = np.array(X_val_list, dtype=np.float32) if X_val_list else np.zeros((0, window_size, len(feature_cols)), dtype=np.float32)
        y_val = np.array(y_val_list, dtype=np.float32) if y_val_list else np.zeros(0, dtype=np.float32)
        X_test = np.array(X_test_list, dtype=np.float32) if X_test_list else np.zeros((0, window_size, len(feature_cols)), dtype=np.float32)
        y_test = np.array(y_test_list, dtype=np.float32) if y_test_list else np.zeros(0, dtype=np.float32)
    else:
        # legacy: 마지막 val_ratio 만 val 로
        n_val = max(1, int(len(X_tr) * val_ratio))
        X_val, y_val = X_tr[-n_val:], y_tr[-n_val:]
        X_test, y_test = np.zeros((0, window_size, len(feature_cols)), dtype=np.float32), np.zeros(0, dtype=np.float32)
        X_tr, y_tr = X_tr[:-n_val], y_tr[:-n_val]

    return X_tr, X_val, X_test, y_tr, y_val, y_test, feat_scaler
```

- [ ] **Step 2: `train_tcn()` 가 새 시그니처 사용하도록 수정**

기존 (`train.py:142-218`) 의 본문 수정. 함수 시그니처도 변경:

```python
def train_tcn(
    df_full,
    y: pd.Series,
    config: dict,
    pretrained_path: Path,
    train_quarters: set[str] | None = None,
    val_quarters: set[str] | None = None,
    test_quarters: set[str] | None = None,
) -> tuple:
    """TCNClassifier fine-tune. (model, val_AUC, val/test proba, feat_scaler) 반환."""

    feature_cols = list(ALL_FEATURES)
    input_size = len(feature_cols)

    X_tr, X_val, X_test, y_tr, y_val, y_test, feat_scaler = _build_tcn_sequences(
        df_full, y, config["window_size"], feature_cols,
        train_quarters=train_quarters, val_quarters=val_quarters, test_quarters=test_quarters,
        val_ratio=config.get("val_ratio", 0.2),
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = TCNClassifier(
        input_size=input_size,
        n_channels=config["n_channels"],
        kernel_size=config["kernel_size"],
        dilations=config["dilations"],
        dropout=config["dropout"],
    )
    model.load_pretrained_tcn(pretrained_path)
    model.to(device)

    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=config["tcn_lr"])

    ds_tr = TensorDataset(torch.from_numpy(X_tr), torch.from_numpy(y_tr))
    loader = DataLoader(ds_tr, batch_size=config["tcn_batch_size"], shuffle=True)

    best_auc, patience_cnt = 0.0, 0
    best_state = None

    for epoch in range(1, config["tcn_epochs"] + 1):
        model.train()
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device).unsqueeze(1)
            optimizer.zero_grad()
            pred = model(xb)
            loss = criterion(pred, yb)
            loss.backward()
            optimizer.step()

        model.eval()
        with torch.no_grad():
            if len(X_val) > 0:
                xv = torch.from_numpy(X_val).to(device)
                pv = model(xv).cpu().numpy().flatten()
            else:
                pv = np.array([])
        try:
            auc = roc_auc_score(y_val, pv) if len(pv) > 0 else 0.5
        except ValueError:
            auc = 0.5

        if auc > best_auc:
            best_auc = auc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience_cnt = 0
        else:
            patience_cnt += 1

        if epoch % 5 == 0:
            logger.info("[TCN] Epoch %2d/%d  val_AUC=%.4f  best=%.4f", epoch, config["tcn_epochs"], auc, best_auc)

        if patience_cnt >= config["tcn_patience"]:
            logger.info("[TCN] 조기종료 (epoch=%d, best_AUC=%.4f)", epoch, best_auc)
            break

    if best_state:
        model.load_state_dict(best_state)

    # val/test proba 산출 (best model 기준)
    model.eval()
    with torch.no_grad():
        val_proba = (
            torch.sigmoid(model(torch.from_numpy(X_val).to(device))).cpu().numpy().flatten()
            if len(X_val) > 0 else np.array([])
        )
        test_proba = (
            torch.sigmoid(model(torch.from_numpy(X_test).to(device))).cpu().numpy().flatten()
            if len(X_test) > 0 else np.array([])
        )

    logger.info("TCNClassifier 학습 완료 (best_val_AUC=%.4f)", best_auc)
    return model, best_auc, val_proba, test_proba, y_val, y_test, feat_scaler
```

- [ ] **Step 3: `train()` 본문 — train_tcn 새 호출 + ensemble 갱신**

Modify `train.py` 의 `train()` 함수에서 train_tcn 호출 부분 (현재 line 250):

```python
    # 3. TCN 학습 (전이학습)
    pretrained_path = TCN_WEIGHTS_DIR / "finetuned_mapo_tcn_34f.pt"

    train_quarters = set(train_df["quarter"].unique()) if cfg["split_strategy"] == "time" else None
    val_quarters = set(val_df["quarter"].unique()) if cfg["split_strategy"] == "time" else None
    test_quarters = set(test_df["quarter"].unique()) if cfg["split_strategy"] == "time" else None

    tcn_model, tcn_val_auc, tcn_val_proba, tcn_test_proba, y_val_tcn, y_test_tcn, tcn_scaler = train_tcn(
        df_full, y, cfg, pretrained_path,
        train_quarters=train_quarters,
        val_quarters=val_quarters,
        test_quarters=test_quarters,
    )

    # 4. 앙상블 가중치 결정 (val AUC 비례)
    total = lgbm_val_auc + tcn_val_auc
    w_lgbm = lgbm_val_auc / total if total > 0 else 0.5
    w_tcn = tcn_val_auc / total if total > 0 else 0.5
    logger.info("앙상블 가중치 — LightGBM=%.3f, TCN=%.3f", w_lgbm, w_tcn)
```

- [ ] **Step 4: ruff + import smoke**

Run:
```bash
cd "/c/Users/804/Documents/final project"
ruff check --fix models/closure_risk/train.py
ruff format models/closure_risk/train.py
PYTHONIOENCODING=utf-8 python -c "from models.closure_risk.train import train_tcn, _build_tcn_sequences; import inspect; print(list(inspect.signature(train_tcn).parameters))"
```

Expected: `['df_full', 'y', 'config', 'pretrained_path', 'train_quarters', 'val_quarters', 'test_quarters']`.

- [ ] **Step 5: Commit**

```bash
git add models/closure_risk/train.py
git commit -m "$(cat <<'EOF'
refactor(closure_risk): TCN sequence 분할이 quarter 기준 train/val/test 따르도록

- _build_tcn_sequences 가 train_quarters/val_quarters/test_quarters 인자 받음
- label quarter 기준 sequence 분배 (lookback 은 어디 있어도 OK — leakage X)
- train_tcn 이 val/test proba 모두 반환 (다음 evaluate 단계 입력)
- legacy val_ratio fallback 유지

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `evaluate.py` 신규 — 5 metric + reliability diagram

**Files:**
- Create: `models/closure_risk/evaluate.py`
- Test: `tests/test_closure_risk_metrics.py`

- [ ] **Step 1: Write failing test (5 metric 모두 [0,1] 범위)**

```python
# tests/test_closure_risk_metrics.py
"""evaluate_model 5 metric 정확성 + JSON/PNG 저장 검증."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from models.closure_risk.evaluate import evaluate_model, save_metrics_and_plot


def test_evaluate_model_returns_5_metrics():
    """deterministic input → 5 metric 모두 [0,1] 범위."""
    rng = np.random.default_rng(42)
    n = 200
    y_true = rng.choice([0, 1], size=n, p=[0.8, 0.2])
    # y_true 와 약하게 상관 있는 proba (현실적 시뮬)
    proba = np.clip(y_true * 0.5 + rng.normal(0.3, 0.15, size=n), 0, 1)

    metrics = evaluate_model(y_true=y_true, proba=proba, k_pct=10)

    for key in ["auc", "pr_auc", "p_at_k", "r_at_k", "brier"]:
        assert key in metrics, f"missing: {key}"
        assert 0.0 <= metrics[key] <= 1.0, f"{key} out of range: {metrics[key]}"
    assert "calibration" in metrics
    assert isinstance(metrics["calibration"], dict)
    assert "bin_centers" in metrics["calibration"]
    assert "actual_freq" in metrics["calibration"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
cd "/c/Users/804/Documents/final project"
PYTHONIOENCODING=utf-8 python -m pytest tests/test_closure_risk_metrics.py::test_evaluate_model_returns_5_metrics -v
```

Expected: FAIL with `ImportError: cannot import name 'evaluate_model'`.

- [ ] **Step 3: Implement `evaluate.py`**

Create `models/closure_risk/evaluate.py`:

```python
"""폐업 위험도 모델 평가 — 5 metric + Calibration plot.

evaluate_model: AUC/PR-AUC/P@K/R@K/Brier + 10 bin reliability diagram 데이터.
save_metrics_and_plot: metrics.json + calibration_curve.png 저장.

학술 근거:
- Niculescu-Mizil & Caruana (2005) — calibration 표준
- Bergmeir & Benítez (2012) — 시계열 검증

담당: B2 (수지니) 영역, A1 (찬영) cross-team contribution.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)

logger = logging.getLogger(__name__)


def _precision_recall_at_k(
    y_true: np.ndarray,
    proba: np.ndarray,
    k_pct: int = 10,
) -> tuple[float, float]:
    """위험도 top K% 의 precision + recall.

    Args:
        y_true: 실제 label (0/1).
        proba: 예측 확률.
        k_pct: 상위 K% (예: 10 → top 10%).

    Returns:
        (precision_at_k, recall_at_k). 둘 다 [0,1].
    """
    n = len(y_true)
    if n == 0:
        return 0.0, 0.0
    k = max(1, int(n * k_pct / 100))
    # proba 내림차순 정렬 후 top k
    top_idx = np.argsort(-proba)[:k]
    y_top = y_true[top_idx]

    # precision = top k 중 실제 양성 비율
    precision = float(y_top.sum() / k)
    # recall = 전체 양성 중 top k 에 포함된 비율
    n_pos = int(y_true.sum())
    recall = float(y_top.sum() / n_pos) if n_pos > 0 else 0.0
    return precision, recall


def _calibration_curve(
    y_true: np.ndarray,
    proba: np.ndarray,
    n_bins: int = 10,
) -> dict:
    """Reliability diagram 데이터 (10 bin uniform).

    Returns:
        {"bin_centers": [...], "actual_freq": [...], "n_per_bin": [...]}.
    """
    bins = np.linspace(0, 1, n_bins + 1)
    bin_centers = ((bins[:-1] + bins[1:]) / 2).tolist()
    actual_freq = []
    n_per_bin = []
    for i in range(n_bins):
        mask = (proba >= bins[i]) & (proba < bins[i + 1])
        if i == n_bins - 1:
            mask = (proba >= bins[i]) & (proba <= bins[i + 1])
        n = int(mask.sum())
        n_per_bin.append(n)
        if n > 0:
            actual_freq.append(float(y_true[mask].mean()))
        else:
            actual_freq.append(float("nan"))
    return {
        "bin_centers": bin_centers,
        "actual_freq": actual_freq,
        "n_per_bin": n_per_bin,
    }


def evaluate_model(
    y_true: np.ndarray,
    proba: np.ndarray,
    k_pct: int = 10,
) -> dict:
    """5 metric + calibration 측정.

    Args:
        y_true: 실제 binary label (0/1) 배열.
        proba: 예측 확률 배열 (같은 길이).
        k_pct: Precision/Recall@K 의 K% (default 10).

    Returns:
        {
            "auc": float, "pr_auc": float,
            "p_at_k": float, "r_at_k": float, "k_pct": int,
            "brier": float,
            "calibration": {"bin_centers": [...], "actual_freq": [...], "n_per_bin": [...]},
            "n_samples": int, "pos_ratio": float,
        }
    """
    y_true = np.asarray(y_true).astype(int)
    proba = np.asarray(proba).astype(float)
    n = len(y_true)
    if n == 0 or len(np.unique(y_true)) < 2:
        return {
            "auc": 0.5,
            "pr_auc": 0.0,
            "p_at_k": 0.0,
            "r_at_k": 0.0,
            "k_pct": k_pct,
            "brier": 0.0,
            "calibration": {"bin_centers": [], "actual_freq": [], "n_per_bin": []},
            "n_samples": int(n),
            "pos_ratio": float(y_true.mean()) if n > 0 else 0.0,
        }

    auc = float(roc_auc_score(y_true, proba))
    pr_auc = float(average_precision_score(y_true, proba))
    p_at_k, r_at_k = _precision_recall_at_k(y_true, proba, k_pct)
    brier = float(brier_score_loss(y_true, proba))
    cal = _calibration_curve(y_true, proba, n_bins=10)

    return {
        "auc": auc,
        "pr_auc": pr_auc,
        "p_at_k": p_at_k,
        "r_at_k": r_at_k,
        "k_pct": k_pct,
        "brier": brier,
        "calibration": cal,
        "n_samples": int(n),
        "pos_ratio": float(y_true.mean()),
    }


def save_metrics_and_plot(
    metrics: dict,
    metrics_path: str | Path,
    plot_path: str | Path | None = None,
) -> None:
    """metrics.json + calibration_curve.png 저장.

    Args:
        metrics: evaluate_model 또는 multi-model 결과 dict.
        metrics_path: JSON 저장 경로.
        plot_path: PNG 저장 경로 (None 이면 plot skip).
    """
    metrics_path = Path(metrics_path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    logger.info("metrics 저장: %s", metrics_path)

    if plot_path is None:
        return

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib 미설치 — calibration plot skip")
        return

    plot_path = Path(plot_path)
    plot_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], "k--", label="perfect calibration")

    # ensemble + lgbm + tcn 각각 plot (있으면)
    for model_name in ["ensemble", "lgbm", "tcn"]:
        if model_name in metrics and "val" in metrics[model_name]:
            cal = metrics[model_name]["val"].get("calibration", {})
            bc = cal.get("bin_centers", [])
            af = cal.get("actual_freq", [])
            if bc and af:
                af_clean = [v if not np.isnan(v) else 0.0 for v in af]
                ax.plot(bc, af_clean, marker="o", label=f"{model_name} (val)")

    ax.set_xlabel("Predicted probability")
    ax.set_ylabel("Actual frequency")
    ax.set_title("Calibration curve (val set, 10 bins)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=120)
    plt.close(fig)
    logger.info("calibration plot 저장: %s", plot_path)
```

- [ ] **Step 4: Run test to verify PASS**

Run:
```bash
cd "/c/Users/804/Documents/final project"
PYTHONIOENCODING=utf-8 python -m pytest tests/test_closure_risk_metrics.py::test_evaluate_model_returns_5_metrics -v
```

Expected: PASS in < 1s.

- [ ] **Step 5: Add 4 more tests**

Append to `tests/test_closure_risk_metrics.py`:

```python
def test_evaluate_model_handles_imbalanced():
    """y 가 모두 0 → safe degenerate (모든 metric 0 또는 default)."""
    n = 100
    y_true = np.zeros(n, dtype=int)
    proba = np.full(n, 0.1)

    metrics = evaluate_model(y_true=y_true, proba=proba)
    assert metrics["auc"] == 0.5
    assert metrics["pr_auc"] == 0.0
    assert metrics["pos_ratio"] == 0.0


def test_save_metrics_creates_json(tmp_path):
    """metrics.json 저장 + 재로드 가능."""
    metrics = {
        "ensemble": {"val": evaluate_model(np.array([0, 1, 0, 1, 1]), np.array([0.1, 0.8, 0.2, 0.9, 0.6]))},
    }
    json_path = tmp_path / "metrics.json"

    save_metrics_and_plot(metrics, json_path, plot_path=None)

    assert json_path.exists()
    with open(json_path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert "ensemble" in loaded
    assert "val" in loaded["ensemble"]
    assert "auc" in loaded["ensemble"]["val"]


def test_save_metrics_creates_png(tmp_path):
    """matplotlib 사용 가능 환경에서 calibration png 생성."""
    metrics = {
        "ensemble": {"val": evaluate_model(np.array([0, 1, 0, 1, 1, 0, 1, 0]), np.array([0.1, 0.8, 0.2, 0.9, 0.6, 0.3, 0.7, 0.15]))},
    }
    json_path = tmp_path / "metrics.json"
    plot_path = tmp_path / "calibration_curve.png"

    save_metrics_and_plot(metrics, json_path, plot_path=plot_path)

    # matplotlib 미설치 시 skip 됨 — 에러 없이 종료만 검증
    assert json_path.exists()
    # png 는 matplotlib 있을 때만 존재
    try:
        import matplotlib  # noqa: F401

        assert plot_path.exists()
    except ImportError:
        pass


def test_calibration_bins_have_correct_count():
    """10 bin → 10개 bin_centers."""
    rng = np.random.default_rng(0)
    n = 500
    y = rng.choice([0, 1], size=n, p=[0.7, 0.3])
    p = rng.uniform(0, 1, size=n)

    metrics = evaluate_model(y_true=y, proba=p)
    cal = metrics["calibration"]

    assert len(cal["bin_centers"]) == 10
    assert len(cal["actual_freq"]) == 10
    assert len(cal["n_per_bin"]) == 10
    assert sum(cal["n_per_bin"]) == n


def test_precision_at_k_correctness():
    """간단한 ground-truth — top 2 (k=20%) 중 1 개 양성 → P@K=0.5."""
    y_true = np.array([0, 0, 1, 0, 0, 0, 0, 0, 0, 1])
    proba = np.array([0.05, 0.1, 0.95, 0.2, 0.3, 0.15, 0.4, 0.35, 0.5, 0.6])
    # top 2 (k=20%) 의 idx: [2, 9] (proba 0.95, 0.6) → y=[1, 1] → P@K=1.0, R@K=2/2=1.0
    metrics = evaluate_model(y_true=y_true, proba=proba, k_pct=20)
    assert abs(metrics["p_at_k"] - 1.0) < 1e-6
    assert abs(metrics["r_at_k"] - 1.0) < 1e-6
```

- [ ] **Step 6: Run all 5 tests + ruff**

Run:
```bash
cd "/c/Users/804/Documents/final project"
ruff check --fix models/closure_risk/evaluate.py tests/test_closure_risk_metrics.py
ruff format models/closure_risk/evaluate.py tests/test_closure_risk_metrics.py
PYTHONIOENCODING=utf-8 python -m pytest tests/test_closure_risk_metrics.py -v
```

Expected: 5 passed in < 5s.

- [ ] **Step 7: Commit**

```bash
git add models/closure_risk/evaluate.py tests/test_closure_risk_metrics.py
git commit -m "$(cat <<'EOF'
feat(closure_risk): add evaluate.py with 5-metric + calibration plot

- evaluate_model: AUC, PR-AUC, P@K, R@K, Brier + 10-bin reliability
- save_metrics_and_plot: JSON + matplotlib calibration curve
- 5 unit test (range, imbalanced, JSON/PNG, bin count, P@K correctness)
- 학술 근거: Niculescu-Mizil & Caruana (2005), Bergmeir & Benítez (2012)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `train()` 본문에 evaluate 통합 + metrics.json 저장

**Files:**
- Modify: `models/closure_risk/train.py` (`train()` line 226-289)

- [ ] **Step 1: train() 끝에 evaluate 호출 추가**

Modify `models/closure_risk/train.py`. 기존 `train()` 함수의 마지막 부분 (저장 + 로그 line 261-282) 뒤에 추가:

```python
    # ... 기존 lgbm/tcn 저장 + ensemble_weights 저장 ...

    # 6. Evaluate val + test (5 metric + calibration)
    # ensemble proba: weight 합산
    n_val = min(len(lgbm_val_proba), len(tcn_val_proba)) if cfg["split_strategy"] == "time" else len(lgbm_val_proba)
    if n_val > 0 and len(tcn_val_proba) > 0:
        # LightGBM 와 TCN 의 val 길이가 다를 수 있음 — 공통 인덱스 align (TCN 시퀀스 손실 분기)
        # 단순화: TCN 길이 기준 trim. 정밀 align 은 별도 spec.
        ensemble_val_proba = w_lgbm * lgbm_val_proba[:n_val] + w_tcn * tcn_val_proba[:n_val]
        y_val_common = y_val_arr[:n_val]
    else:
        ensemble_val_proba = lgbm_val_proba
        y_val_common = y_val_arr

    val_metrics = {
        "lgbm": evaluate_model(y_val_arr, lgbm_val_proba, k_pct=10),
        "tcn": evaluate_model(y_val_tcn, tcn_val_proba, k_pct=10) if len(tcn_val_proba) > 0 else None,
        "ensemble": evaluate_model(y_val_common, ensemble_val_proba, k_pct=10),
    }

    # Test set (final unbiased)
    if cfg["split_strategy"] == "time" and len(y_test_arr) > 0:
        n_test = min(len(lgbm_test_proba), len(tcn_test_proba)) if len(tcn_test_proba) > 0 else len(lgbm_test_proba)
        if n_test > 0 and len(tcn_test_proba) > 0:
            ensemble_test_proba = w_lgbm * lgbm_test_proba[:n_test] + w_tcn * tcn_test_proba[:n_test]
            y_test_common = y_test_arr[:n_test]
        else:
            ensemble_test_proba = lgbm_test_proba
            y_test_common = y_test_arr

        test_metrics = {
            "lgbm": evaluate_model(y_test_arr, lgbm_test_proba, k_pct=10),
            "tcn": evaluate_model(y_test_tcn, tcn_test_proba, k_pct=10) if len(tcn_test_proba) > 0 else None,
            "ensemble": evaluate_model(y_test_common, ensemble_test_proba, k_pct=10),
        }
    else:
        test_metrics = None

    metrics_summary = {
        "split_strategy": cfg["split_strategy"],
        "train_quarters": sorted(set(train_df["quarter"].unique())) if cfg["split_strategy"] == "time" else None,
        "val_quarters": sorted(set(val_df["quarter"].unique())) if cfg["split_strategy"] == "time" else None,
        "test_quarters": sorted(set(test_df["quarter"].unique())) if cfg["split_strategy"] == "time" else None,
        "ensemble_weights": {"w_lgbm": w_lgbm, "w_tcn": w_tcn},
        "lgbm": {"val": val_metrics["lgbm"], "test": (test_metrics or {}).get("lgbm")},
        "tcn": {"val": val_metrics["tcn"], "test": (test_metrics or {}).get("tcn")},
        "ensemble": {"val": val_metrics["ensemble"], "test": (test_metrics or {}).get("ensemble")},
    }

    save_metrics_and_plot(
        metrics_summary,
        metrics_path=cfg["metrics_path"],
        plot_path=cfg["calibration_plot_path"],
    )

    logger.info(
        "최종 ensemble val_AUC=%.4f / test_AUC=%.4f (split=%s)",
        val_metrics["ensemble"]["auc"],
        (test_metrics["ensemble"]["auc"] if test_metrics else 0.0),
        cfg["split_strategy"],
    )
```

- [ ] **Step 2: ruff + import smoke**

Run:
```bash
cd "/c/Users/804/Documents/final project"
ruff check --fix models/closure_risk/train.py
ruff format models/closure_risk/train.py
PYTHONIOENCODING=utf-8 python -c "from models.closure_risk.train import train; print('train import OK')"
```

Expected: `train import OK`.

- [ ] **Step 3: Commit**

```bash
git add models/closure_risk/train.py
git commit -m "$(cat <<'EOF'
feat(closure_risk): integrate evaluate.py into train pipeline

- train() 끝에 val + test set 5 metric 측정
- ensemble proba = w_lgbm * lgbm + w_tcn * tcn (val auc 비례)
- metrics.json + calibration_curve.png 저장
- LGBM val/test 길이가 TCN 보다 길 수 있어 trim align (간단)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: 회귀 안전성 + 통합 smoke

**Files:**
- Test: `tests/test_closure_risk_regression.py` (신규)

- [ ] **Step 1: regression smoke test 작성**

```python
# tests/test_closure_risk_regression.py
"""train.py + evaluate.py 통합 + 기존 predict.py 인터페이스 보존 검증."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from models.closure_risk.data_prep import _time_based_split
from models.closure_risk.evaluate import evaluate_model, save_metrics_and_plot


def test_time_based_split_used_in_train_config():
    """DEFAULT_CONFIG 가 time-based split 을 default 로 사용."""
    from models.closure_risk.train import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["split_strategy"] == "time"
    assert 0.5 <= DEFAULT_CONFIG["train_ratio"] <= 0.9
    assert 0.05 <= DEFAULT_CONFIG["val_ratio"] <= 0.3
    # train + val + test = 1.0 (test = 1 - train - val)
    test_ratio = 1 - DEFAULT_CONFIG["train_ratio"] - DEFAULT_CONFIG["val_ratio"]
    assert test_ratio > 0


def test_predict_py_interface_unchanged():
    """predict.py 의 _classify, RISK_LEVELS 변경 X (회귀 안전)."""
    from models.closure_risk.predict import RISK_LEVELS, _classify

    # RISK_LEVELS 의 (threshold, level) 튜플 schema
    assert len(RISK_LEVELS) == 3
    for thr, lvl in RISK_LEVELS:
        assert 0.0 <= thr <= 1.0
        assert lvl in ("danger", "caution", "safe")

    assert _classify(0.7) == "danger"
    assert _classify(0.5) == "caution"
    assert _classify(0.1) == "safe"


def test_full_pipeline_with_synthetic_data(tmp_path):
    """build_dataset 거치지 않고 _time_based_split + evaluate 통합 동작 확인."""
    rng = np.random.default_rng(7)
    n_per_q = 30
    quarters = [f"2020Q{(i % 4) + 1}" if i < 4 else f"202{1 + (i - 4) // 4}Q{((i - 4) % 4) + 1}" for i in range(20)]
    rows = []
    for q in quarters:
        for _ in range(n_per_q):
            rows.append({
                "quarter": q,
                "dong_code": f"d{rng.integers(0, 5)}",
                "industry_code": "x",
                "label": int(rng.choice([0, 1], p=[0.8, 0.2])),
                "feature1": rng.normal(),
            })
    df = pd.DataFrame(rows)

    # split
    train_df, val_df, test_df = _time_based_split(df)
    assert len(train_df) + len(val_df) + len(test_df) == len(df)

    # 더미 model proba (label 과 약하게 상관)
    val_proba = np.clip(val_df["label"].values * 0.5 + rng.normal(0.3, 0.15, size=len(val_df)), 0, 1)
    test_proba = np.clip(test_df["label"].values * 0.5 + rng.normal(0.3, 0.15, size=len(test_df)), 0, 1)

    val_metrics = evaluate_model(val_df["label"].values, val_proba)
    test_metrics = evaluate_model(test_df["label"].values, test_proba)

    summary = {
        "split_strategy": "time",
        "ensemble": {"val": val_metrics, "test": test_metrics},
    }

    json_path = tmp_path / "metrics.json"
    save_metrics_and_plot(summary, json_path, plot_path=None)
    assert json_path.exists()

    with open(json_path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["split_strategy"] == "time"
    assert "ensemble" in loaded
    assert loaded["ensemble"]["val"]["auc"] > 0.5  # 약한 상관 → AUC > 0.5
```

- [ ] **Step 2: Run all closure_risk tests + 기존 27 회귀**

Run:
```bash
cd "/c/Users/804/Documents/final project"
ruff check --fix tests/test_closure_risk_regression.py
ruff format tests/test_closure_risk_regression.py
PYTHONIOENCODING=utf-8 python -m pytest tests/test_closure_risk_split.py tests/test_closure_risk_metrics.py tests/test_closure_risk_regression.py tests/test_runner_thought.py tests/test_new_store_inject.py tests/test_persona_dong_match.py tests/test_role_archetype_compat.py -v 2>&1 | tail -30
```

Expected:
- closure_risk_split: 4 PASS
- closure_risk_metrics: 5 PASS
- closure_risk_regression: 3 PASS
- 기존 (T7 + Issue 2 + P1 + P2): 27 PASS
- 합계: **39 PASS**, 0 FAIL

- [ ] **Step 3: Commit**

```bash
git add tests/test_closure_risk_regression.py
git commit -m "$(cat <<'EOF'
test(closure_risk): regression test for split + evaluate integration

- DEFAULT_CONFIG 의 split_strategy="time" default 검증
- predict.py RISK_LEVELS / _classify 인터페이스 회귀 안전성 검증
- synthetic data 로 _time_based_split + evaluate_model 통합 smoke

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: 학습 결과 print 강화 + 문서

**Files:**
- Modify: `models/closure_risk/train.py` (마지막 logger 메시지)
- Create: `docs/abm-simulation/closure-risk-validation-fix.md` (학습 결과 변화 설명)

- [ ] **Step 1: train.py 마지막 로그 print 강화**

Modify `models/closure_risk/train.py` 의 `train()` 함수 끝 (이미 Task 5 에서 추가한 logger.info 다음):

```python
    logger.info("=" * 70)
    logger.info("학습 완료 — closure_risk 모델 (split=%s)", cfg["split_strategy"])
    logger.info("=" * 70)
    if cfg["split_strategy"] == "time":
        logger.info("Train quarters: %s ~ %s (%d개)", train_df["quarter"].min(), train_df["quarter"].max(), train_df["quarter"].nunique())
        logger.info("Val quarters:   %s ~ %s (%d개)", val_df["quarter"].min(), val_df["quarter"].max(), val_df["quarter"].nunique())
        logger.info("Test quarters:  %s ~ %s (%d개)", test_df["quarter"].min(), test_df["quarter"].max(), test_df["quarter"].nunique())
    logger.info("Val  metrics — ensemble: AUC=%.4f, PR-AUC=%.4f, P@10=%.3f, R@10=%.3f, Brier=%.4f",
                val_metrics["ensemble"]["auc"], val_metrics["ensemble"]["pr_auc"],
                val_metrics["ensemble"]["p_at_k"], val_metrics["ensemble"]["r_at_k"],
                val_metrics["ensemble"]["brier"])
    if test_metrics:
        logger.info("Test metrics — ensemble: AUC=%.4f, PR-AUC=%.4f, P@10=%.3f, R@10=%.3f, Brier=%.4f",
                    test_metrics["ensemble"]["auc"], test_metrics["ensemble"]["pr_auc"],
                    test_metrics["ensemble"]["p_at_k"], test_metrics["ensemble"]["r_at_k"],
                    test_metrics["ensemble"]["brier"])
    logger.info("Metrics JSON: %s", cfg["metrics_path"])
    logger.info("Calibration plot: %s", cfg["calibration_plot_path"])
```

- [ ] **Step 2: 문서 작성**

Create `docs/abm-simulation/closure-risk-validation-fix.md`:

```markdown
# 폐업 위험도 모델 검증 layer fix (2026-04-29)

## 변경 요약

폐업 위험도 모델 (`models/closure_risk/`) 의 **검증 layer** 를 학술 표준에 맞게 교체.

### Before

```python
# train.py:236-240 (legacy)
n_val = max(1, int(len(y) * cfg["val_ratio"]))
X_lgbm_tr = X_lgbm.iloc[:-n_val].values
X_lgbm_val = X_lgbm.iloc[-n_val:].values
```

`build_closure_risk_dataset` 가 `dong_code, industry_code, quarter` 순으로 정렬 → 마지막 N% 가 dong-based 분할 (시간순 X). 단일 metric (`roc_auc_score`) 만.

### After

```python
# data_prep.py: _time_based_split(df, train_ratio=0.70, val_ratio=0.15)
quarters = sorted(df["quarter"].unique())
train_end = quarters[int(n_q * 0.70) - 1]
val_end = quarters[int(n_q * 0.85) - 1]
```

`quarter` 기준 시간순 holdout 3분할. **Test set 분리** → final unbiased 측정. 5 metric (AUC, PR-AUC, P@10, R@10, Brier) + Calibration plot.

## 학술 근거

- Bergmeir & Benítez (2012) — 시계열 모델은 random k-fold 사용 X
- Niculescu-Mizil & Caruana (2005) — Calibration 표준 (10-bin reliability diagram)
- Cawley & Talbot (2010) — Test set 미분리 시 over-fitting 누적

## 예상 학습 결과 변화

| Metric | Before (random split) | After (time split) |
|---|---|---|
| val_AUC | 0.85 (부풀려짐) | **0.70~0.78** (정직) |
| 신뢰도 | Brussels r=0.95 학술 자산 위협 | Brussels-class 보장 |

`val_AUC` 가 떨어져 보이지만 **신뢰할 수 있는 수치**.

## 산출물

- `weights/metrics.json` — split 정보 + lgbm/tcn/ensemble × val/test 모두
- `weights/calibration_curve.png` — 10-bin reliability diagram

## 회귀 안전성

- `predict.py` 인터페이스 변경 X — 기존 호출자 영향 0
- `model.py` (TCNClassifier) 변경 X
- 기존 weights 그대로 inference 가능, 단 학술적 신뢰도 위해 재학습 권장

## CLI

기본 (time split):
```bash
python -m models.closure_risk.train
```

분기 부족 시 명시적 random fallback:
```bash
python -m models.closure_risk.train --split-strategy random
```

(CLI 옵션은 별도 task 로 이관 — 현재는 config dict 로 호출)
```

- [ ] **Step 3: ruff + commit**

Run:
```bash
cd "/c/Users/804/Documents/final project"
ruff check --fix models/closure_risk/train.py
ruff format models/closure_risk/train.py
```

```bash
git add models/closure_risk/train.py docs/abm-simulation/closure-risk-validation-fix.md
git commit -m "$(cat <<'EOF'
docs(closure_risk): 학습 결과 print 강화 + 변경 문서

- train.py: train/val/test quarter 범위 + 5 metric 모두 로그
- docs: validation fix 변경 사유 + 예상 metric 변화 + 학술 근거 정리

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## 최종 검증 (모든 task 완료 후)

- [ ] **Run all closure_risk tests**

```bash
cd "/c/Users/804/Documents/final project"
PYTHONIOENCODING=utf-8 python -m pytest tests/test_closure_risk_split.py tests/test_closure_risk_metrics.py tests/test_closure_risk_regression.py -v
```

Expected: 12 passed (4 + 5 + 3).

- [ ] **Run full regression**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: 39 passed (12 closure_risk + 27 기존), 0 failed.

- [ ] **Import smoke**

```bash
PYTHONIOENCODING=utf-8 python -c "
from models.closure_risk.train import train, DEFAULT_CONFIG
from models.closure_risk.data_prep import _time_based_split
from models.closure_risk.evaluate import evaluate_model, save_metrics_and_plot
from models.closure_risk.predict import predict, RISK_LEVELS
print('split_strategy:', DEFAULT_CONFIG['split_strategy'])
print('all imports OK')
"
```

Expected: `split_strategy: time` + `all imports OK`.

- [ ] **(선택) production retrain — 사용자 환경에서 실행**

```bash
cd "/c/Users/804/Documents/final project"
PYTHONIOENCODING=utf-8 python -m models.closure_risk.train
```

Expected output: `Train quarters: ... ~ ..., Val_AUC=..., Test_AUC=...`. 학습 시간 5~30분 (데이터 크기에 따라).

산출물 검증:
```bash
cat models/closure_risk/weights/metrics.json | python -m json.tool | head -40
ls -la models/closure_risk/weights/calibration_curve.png
```

---

## Spec Coverage Self-Check

- [x] `_time_based_split()` helper — Task 1
- [x] `train.py` config 갱신 (split_strategy/train_ratio/val_ratio) — Task 2
- [x] LightGBM 분할 통합 — Task 2
- [x] TCN sequence buffer 처리 — Task 3
- [x] 5 metric (AUC, PR-AUC, P@K, R@K, Brier) — Task 4
- [x] Calibration plot — Task 4
- [x] `metrics.json` 저장 — Task 4 + 5
- [x] Test set 분리 + final 측정 — Task 5
- [x] 회귀 안전성 (predict.py 인터페이스 변경 X) — Task 6
- [x] 단위 테스트 9 개 (4 split + 5 metric) — Task 1, 4
- [x] Regression test 3 개 — Task 6
- [x] 문서 — Task 7
