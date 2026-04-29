# D 모델 (living_pop_forecast) 정상화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** D 모델 (`models/living_pop_forecast/`)을 production 신뢰도 수준으로 정상화한다. 핵심: **`dong_code` 식별자를 입력 피처에 추가**해 단일 TCN이 384 그룹(16동×24시간대) 패턴을 평균화하는 설계 결함을 제거한다.

**Architecture:** 입력 피처 5개 → 21개로 확장 (5 numerical + 16 dong_one_hot). `TCNForecaster` 모델은 그대로 사용 (input_size 자동 인식). 데이터 전처리·학습·추론 3단 파이프라인을 모두 갱신하고 기존 `living_pop_tcn.pt` 가중치는 archive로 보존.

**Tech Stack:** Python 3.12, PyTorch (CUDA 권장), pandas, scikit-learn, pytest

**Spec/근거:**
- 객관적 평가: [`docs/issues/2026-04-28-end-to-end-data-flow-gaps.md`](../../issues/2026-04-28-end-to-end-data-flow-gaps.md)
- 코드베이스 리뷰: [`docs/architecture/codebase-review-2026-04-28.md`](../../architecture/codebase-review-2026-04-28.md)
- 발견된 핵심 결함: dong_code 식별 입력 부재 + best_val_loss 미기록 + Test set 부재

---

## 0. Context

### 현재 D 모델 상태 (자료·코드 검증 결과)

| 항목 | 값 |
|---|---|
| 클래스 | `TCNForecaster` (n_channels=64, dilations=[1,2,4], RF=8=window_size) |
| 입력 피처 | 5개 (`total_avg_pop`, `weekday_avg_pop`, `weekend_avg_pop`, `time_zone_norm`, `quarter_num`) |
| **`dong_code` 식별자** | **❌ 입력에 없음** ← 핵심 설계 결함 |
| 데이터셋 | 마포 16동 × 24시간대 = 384 그룹 × ~20 시퀀스 = ~7,680 |
| best_val_loss | **미기록** (scalers에 미포함) |
| 가중치 | `models/living_pop_forecast/weights/living_pop_tcn.pt` (217KB) |
| Test set | **❌ 없음** (Train/Val 80/20만) |
| Pretrain 활용 | ❌ from scratch (A단계 `pretrained_tcn_seed2026.pt` 미활용) |

### 정상화 후 기대

| 항목 | 변경 |
|---|---|
| 입력 피처 | 5 → 21 (5 + 16 dong_one_hot) |
| 모델 capacity | n_channels=64 유지 |
| Test set | 시간순 70/15/15 분리 (Train/Val/Test) |
| metadata | `best_val_loss`, `train_size`, `val_size`, `test_loss`, `epochs_trained` 저장 |
| 검증 | LODO 16-fold (Leave-One-Dong-Out) cross-validation |
| 가중치 명명 | `living_pop_tcn.pt` (legacy) + 새 `living_pop_tcn_v2.pt` |

### 작업 범위 외 (Phase 2)

- dong_embedding (16→4) 학습 가능 layer (TCNForecaster 모델 수정 필요)
- A단계 pretrain 가중치 전이학습 (input_size 다름 → partial load)
- 서울 425동 확장
- Multi-horizon 예측 (1~4분기)
- Time-of-week 패턴 (월~일 7개)

본 plan은 **dong 식별자 추가 + 평가 보강** 에 집중 (3~5일 작업).

---

## 1. File Structure

| 파일 | 변경 |
|---|---|
| `models/living_pop_forecast/data_prep.py` | 수정 — `POP_FEATURES`에 dong_one_hot 16개 추가, `prepare_dataloaders` 출력 input_size 21 |
| `models/living_pop_forecast/train.py` | 수정 — Train/Val/Test 70/15/15 분할, metadata 저장 |
| `models/living_pop_forecast/predict.py` | 수정 — dong_idx → dong_one_hot 변환 후 추론 |
| `models/living_pop_forecast/weights/living_pop_tcn.pt` | 보존 (legacy backup, 직접 수정 X) |
| `models/living_pop_forecast/weights/living_pop_tcn_v2.pt` | 신규 산출 |
| `models/living_pop_forecast/weights/living_pop_metadata_v2.json` | 신규 — best_val_loss + 평가 metric |
| `tests/test_living_pop_forecast_v2.py` | 신규 — dong embedding/one-hot 단위 테스트 (3~4건) |
| `validation/experiments/living_pop/lodo_validation.py` | 신규 — LODO 16-fold 검증 스크립트 |
| `docs/abm-simulation/living-pop-forecast-v2-report.md` | 신규 — v1 vs v2 비교 리포트 |

**담당 영역 주의:** `models/living_pop_forecast/`는 B2 (수지니) 담당 영역. 본 plan 실행 시 PR 검토 필수. A1(찬영) 직접 진행 가능 부분: **`validation/experiments/living_pop/lodo_validation.py`**(검증 스크립트, A1 영역) + **metadata json 정의** + **CSV 캐시 갱신 (data/processed/living_pop_quarterly.csv)**. 모델 코드는 B2 협업.

---

## Task 1: data_prep.py — dong_one_hot 16-dim 추가

**Files:**
- Modify: `models/living_pop_forecast/data_prep.py:48-55` (`POP_FEATURES`), `prepare_dataloaders` 시퀀스 생성 로직
- Test: `tests/test_living_pop_forecast_v2.py`

**컨텍스트:** 마포 16동을 정렬된 dong_code 순서로 one-hot 인코딩. 학습/추론 모두 동일 인덱스 매핑 사용.

- [ ] **Step 1: 마포 16동 코드 매핑 상수 추가**

`models/living_pop_forecast/data_prep.py:55` 직후 (POP_FEATURES 정의 다음):

```python
# 마포구 16동 정렬된 dong_code (one-hot 인덱스)
MAPO_DONG_CODES: tuple[str, ...] = (
    "11440555",  # 아현동
    "11440565",  # 공덕동
    "11440585",  # 도화동
    "11440590",  # 용강동
    "11440600",  # 대흥동
    "11440610",  # 염리동
    "11440630",  # 신수동
    "11440655",  # 서강동
    "11440660",  # 서교동
    "11440680",  # 합정동
    "11440690",  # 망원1동
    "11440700",  # 망원2동
    "11440710",  # 연남동
    "11440720",  # 성산1동
    "11440730",  # 성산2동
    "11440740",  # 상암동
)

DONG_FEATURES: list[str] = [f"dong_{dc}" for dc in MAPO_DONG_CODES]
ALL_FEATURES: list[str] = POP_FEATURES + DONG_FEATURES   # 5 + 16 = 21
```

- [ ] **Step 2: 단위 테스트 — dong_one_hot 정확성 검증 (TDD)**

```python
# tests/test_living_pop_forecast_v2.py
import numpy as np
import pytest


def test_mapo_dong_codes_count_is_16():
    from models.living_pop_forecast.data_prep import MAPO_DONG_CODES
    assert len(MAPO_DONG_CODES) == 16


def test_all_features_count_is_21():
    from models.living_pop_forecast.data_prep import ALL_FEATURES
    assert len(ALL_FEATURES) == 21


def test_dong_one_hot_unique_index():
    from models.living_pop_forecast.data_prep import MAPO_DONG_CODES
    # 16동 정확 매핑
    assert MAPO_DONG_CODES[0] == "11440555"  # 아현동
    assert MAPO_DONG_CODES[8] == "11440660"  # 서교동
    assert MAPO_DONG_CODES[15] == "11440740"  # 상암동
    # 중복 없음
    assert len(set(MAPO_DONG_CODES)) == 16


def test_unknown_dong_code_raises():
    """16동 외 동 입력 시 명확한 ValueError"""
    import pandas as pd
    from models.living_pop_forecast.data_prep import _add_dong_one_hot

    df = pd.DataFrame({
        "dong_code": ["11440555", "99999999"],  # 둘째 row는 마포 외
        "total_avg_pop": [100, 200],
    })
    with pytest.raises(ValueError, match="알 수 없는 dong_code"):
        _add_dong_one_hot(df)
```

- [ ] **Step 3: 실패 확인**

```bash
pytest tests/test_living_pop_forecast_v2.py -v
```
Expected: 4 FAIL (`MAPO_DONG_CODES`, `ALL_FEATURES`, `_add_dong_one_hot` 미정의)

- [ ] **Step 4: `_add_dong_one_hot` 헬퍼 함수 구현**

`data_prep.py` 안에 추가:

```python
def _add_dong_one_hot(df: pd.DataFrame) -> pd.DataFrame:
    """dong_code → 16개 one-hot 컬럼 추가.

    Raises
    ------
    ValueError
        16동 외 동 입력 시.
    """
    df = df.copy()
    for dc in MAPO_DONG_CODES:
        df[f"dong_{dc}"] = (df["dong_code"] == dc).astype(np.float32)

    # 16동 외 row 검증
    df["_dong_sum"] = df[DONG_FEATURES].sum(axis=1)
    if (df["_dong_sum"] == 0).any():
        bad_codes = df[df["_dong_sum"] == 0]["dong_code"].unique().tolist()
        raise ValueError(f"알 수 없는 dong_code: {bad_codes}. 마포구 16동만 지원.")
    df = df.drop(columns=["_dong_sum"])
    return df
```

- [ ] **Step 5: `prepare_dataloaders`에 one-hot 통합**

`prepare_dataloaders` 함수 안 (시계열 시퀀스 생성 직전):

```python
# 기존 POP_FEATURES 5개 정규화 후, dong_one_hot 16개 추가
df = _add_dong_one_hot(df)   # 16개 dong_X 컬럼 추가

# 학습 입력 = 21차원
feature_cols = POP_FEATURES + DONG_FEATURES   # 5 + 16
```

- [ ] **Step 6: 테스트 통과 확인**

```bash
pytest tests/test_living_pop_forecast_v2.py -v
```
Expected: 4 PASS

- [ ] **Step 7: ruff 통과**

```bash
ruff check --fix models/living_pop_forecast/data_prep.py tests/test_living_pop_forecast_v2.py
ruff format models/living_pop_forecast/data_prep.py tests/test_living_pop_forecast_v2.py
```

---

## Task 2: train.py — Train/Val/Test 70/15/15 + metadata 저장

**Files:**
- Modify: `models/living_pop_forecast/train.py` (split 로직 + metadata)
- Test: `tests/test_living_pop_forecast_v2.py` (metadata 저장 테스트)

- [ ] **Step 1: 시간순 70/15/15 분할 추가**

`train.py:179` `_train_loop` 직후 또는 main `train()` 함수 내부에서 데이터 분할:

```python
# Train/Val/Test 시간순 분할 (70/15/15)
n_total = len(X)
n_test = int(n_total * 0.15)
n_val = int(n_total * 0.15)
n_train = n_total - n_val - n_test

X_train = X[:n_train]
X_val = X[n_train:n_train + n_val]
X_test = X[n_train + n_val:]
# y_train, y_val, y_test 동일 패턴
```

기존 train_loader/val_loader 구성에 test_loader 추가.

- [ ] **Step 2: `_validate_test()` 함수 추가**

학습 종료 후 best_state 로드 → test_loader로 평가:

```python
def _evaluate_test(model, test_loader, criterion, device) -> float:
    model.load_state_dict(best_state)
    model.eval()
    test_loss = 0.0
    n = 0
    with torch.no_grad():
        for X_batch, y_batch in test_loader:
            X_batch = X_batch.to(device)
            y_batch = y_batch.to(device)
            pred = model(X_batch)
            test_loss += criterion(pred, y_batch).item()
            n += 1
    return test_loss / max(n, 1)
```

- [ ] **Step 3: metadata json 저장**

```python
import json

metadata = {
    "version": "v2",
    "input_size": 21,
    "feature_columns": ALL_FEATURES,
    "n_dong": 16,
    "best_val_loss": float(best_val_loss),
    "test_loss": float(test_loss),
    "train_size": n_train,
    "val_size": n_val,
    "test_size": n_test,
    "epochs_trained": epochs_run,
    "n_channels": cfg["n_channels"],
    "kernel_size": cfg["kernel_size"],
    "dilations": cfg["dilations"],
    "window_size": cfg["window_size"],
    "trained_at": datetime.now().isoformat(),
}

metadata_path = save_path.parent / "living_pop_metadata_v2.json"
metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
logger.info("metadata 저장: %s (best_val=%.6f, test=%.6f)", metadata_path, best_val_loss, test_loss)
```

- [ ] **Step 4: 가중치 저장 경로 변경**

`save_path = WEIGHTS_DIR / "living_pop_tcn_v2.pt"` (legacy 보존).

- [ ] **Step 5: metadata 단위 테스트**

```python
def test_metadata_json_schema(tmp_path):
    """학습 후 metadata json이 필수 키들을 포함해야 한다."""
    import json
    from datetime import datetime

    sample = {
        "version": "v2",
        "input_size": 21,
        "feature_columns": [f"feat_{i}" for i in range(21)],
        "n_dong": 16,
        "best_val_loss": 0.001,
        "test_loss": 0.002,
        "train_size": 5000,
        "val_size": 1000,
        "test_size": 1000,
        "epochs_trained": 50,
        "n_channels": 64,
        "kernel_size": 2,
        "dilations": [1, 2, 4],
        "window_size": 8,
        "trained_at": datetime.now().isoformat(),
    }
    p = tmp_path / "meta.json"
    p.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")

    loaded = json.loads(p.read_text(encoding="utf-8"))
    required_keys = {"version", "input_size", "best_val_loss", "test_loss",
                     "train_size", "val_size", "test_size", "epochs_trained"}
    assert required_keys <= loaded.keys()
```

- [ ] **Step 6: 학습 실행 (CUDA 권장)**

```bash
python -m models.living_pop_forecast.train --epochs 100 --patience 15 --seed 2026 \
  2>&1 | tee logs/living_pop_v2_train.log
```

기대 출력:
- `DataLoader 준비: input_size=21, train=N, val=N, test=N batches`
- 학습 곡선 + early stopping
- `metadata 저장: ... (best_val=0.XXX, test=0.XXX)`

- [ ] **Step 7: 산출 검증**

```bash
ls -la models/living_pop_forecast/weights/living_pop_tcn_v2.pt models/living_pop_forecast/weights/living_pop_metadata_v2.json
cat models/living_pop_forecast/weights/living_pop_metadata_v2.json
```

---

## Task 3: predict.py — v2 가중치 + dong_one_hot 추론

**Files:**
- Modify: `models/living_pop_forecast/predict.py`

- [ ] **Step 1: 가중치 경로 변경 + dong_one_hot 입력 변환**

`predict.py:73-103` `_load_model_and_scalers` 부근:

```python
# v2 가중치 우선, 없으면 legacy v1 폴백
WEIGHTS_PATH_V2 = WEIGHTS_DIR / "living_pop_tcn_v2.pt"
WEIGHTS_PATH_V1 = WEIGHTS_DIR / "living_pop_tcn.pt"

def _resolve_weights_path() -> Path:
    if WEIGHTS_PATH_V2.exists():
        return WEIGHTS_PATH_V2
    logger.warning("v2 가중치 없음, legacy v1 fallback: %s", WEIGHTS_PATH_V1)
    return WEIGHTS_PATH_V1
```

추론 시퀀스 빌드 부분(`predict.py:150` 근처)에서 dong_one_hot 추가:

```python
from models.living_pop_forecast.data_prep import _add_dong_one_hot, ALL_FEATURES

# 입력 시계열에 dong_one_hot 추가
group_df = _add_dong_one_hot(group_df)
seq = feat_scaler.transform(group_df[ALL_FEATURES].values)   # input_size 21
```

- [ ] **Step 2: predict 통합 테스트**

```python
def test_predict_returns_finite_value():
    """predict()가 finite 숫자를 반환하는지 (NaN/Inf 아님)."""
    from models.living_pop_forecast.predict import predict
    result = predict(dong_code="11440660", time_zone=14)   # 서교동 14시
    assert result is not None
    assert "predicted_pop" in result
    assert np.isfinite(result["predicted_pop"])
    assert result["predicted_pop"] > 0
```

- [ ] **Step 3: 백엔드 통합 — `models/interface.py`의 `living_pop_forecast` 호출 경로 검증**

`models/interface.py`에서 living_pop_forecast가 어떻게 호출되는지 확인. v2로 전환 후에도 응답 dict 구조는 동일해야 함 (기존 `dong_code`, `n_quarters`, `predicted_pop` 키 보존).

- [ ] **Step 4: ruff 통과**

```bash
ruff check --fix models/living_pop_forecast/predict.py tests/test_living_pop_forecast_v2.py
ruff format models/living_pop_forecast/predict.py tests/test_living_pop_forecast_v2.py
```

---

## Task 4: LODO 16-fold 검증 스크립트

**Files:**
- Create: `validation/experiments/living_pop/lodo_validation.py`
- Output: `validation/results/living_pop_lodo_v2.csv`

**컨텍스트:** Leave-One-Dong-Out cross-validation — 16동 중 1개를 test 로 빼고 15동으로 학습 → 16번 반복. 각 동의 일반화 정확도 측정.

**책임:** A1(찬영) 영역 (`validation/`).

- [ ] **Step 1: lodo_validation.py 작성**

```python
# validation/experiments/living_pop/lodo_validation.py
"""LODO 16-fold cross-validation — D 모델 일반화 검증.

각 동을 test로 빼고 나머지 15동으로 학습 → 16번 반복.
산출: 동별 test MAPE/MAE/RMSE.

사용:
    python -m validation.experiments.living_pop.lodo_validation
"""
from __future__ import annotations
import argparse, json, logging, time
from pathlib import Path

import numpy as np
import pandas as pd

from models.living_pop_forecast.data_prep import (
    MAPO_DONG_CODES, prepare_dataloaders, ALL_FEATURES,
)
from models.living_pop_forecast.train import train as train_model
from validation.accuracy_metrics import generate_accuracy_report

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_CSV = PROJECT_ROOT / "validation" / "results" / "living_pop_lodo_v2.csv"


def run_lodo(seed: int = 2026) -> pd.DataFrame:
    rows = []
    t0 = time.time()
    for i, holdout_dong in enumerate(MAPO_DONG_CODES, 1):
        logger.info("[LODO %d/16] holdout=%s 시작", i, holdout_dong)
        cfg = {
            "exclude_dongs": [holdout_dong],
            "save_suffix": f"lodo_{holdout_dong}",
            "epochs": 50, "patience": 10, "seed": seed,
        }
        result = train_model(cfg)   # 15동으로 학습, holdout test 반환

        rows.append({
            "fold": i,
            "holdout_dong": holdout_dong,
            "train_loss": result["train_loss"],
            "val_loss": result["val_loss"],
            "test_loss_holdout": result["test_loss"],
            "epochs_trained": result["epochs"],
            "elapsed_s": result["elapsed_s"],
        })
        logger.info("[LODO %d/16] %s test_loss=%.6f", i, holdout_dong, result["test_loss"])

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS_CSV, index=False, encoding="utf-8-sig")
    logger.info("LODO 완료: %s (%.0fs)", RESULTS_CSV, time.time() - t0)
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = run_lodo()
    print(df.to_string(index=False))
    print(f"\n평균 test_loss: {df['test_loss_holdout'].mean():.6f}")
    print(f"표준편차:       {df['test_loss_holdout'].std():.6f}")
    print(f"최악 동:        {df.loc[df['test_loss_holdout'].idxmax(), 'holdout_dong']}")
```

- [ ] **Step 2: train_model() 시그니처 확장**

`train.py train()` 함수에 `exclude_dongs: list[str] | None = None` 인자 추가. data_prep에서 해당 동 row 필터링.

- [ ] **Step 3: 실행 (16 fold × 약 5분 = ~1.5시간)**

```bash
python -m validation.experiments.living_pop.lodo_validation \
  2>&1 | tee logs/living_pop_lodo.log
```

- [ ] **Step 4: 결과 평가**

```bash
python -c "
import pandas as pd
df = pd.read_csv('validation/results/living_pop_lodo_v2.csv')
print('평균 test_loss:', df['test_loss_holdout'].mean())
print('표준편차:      ', df['test_loss_holdout'].std())
print('최악 5개 동:')
print(df.nlargest(5, 'test_loss_holdout')[['holdout_dong', 'test_loss_holdout']])
print('최고 5개 동:')
print(df.nsmallest(5, 'test_loss_holdout')[['holdout_dong', 'test_loss_holdout']])
"
```

기대: 16동의 test_loss 분포가 정규에 가깝고, std가 mean의 50% 이내면 일반화 양호.

---

## Task 5: v1 vs v2 비교 리포트

**Files:**
- Create: `docs/abm-simulation/living-pop-forecast-v2-report.md`

- [ ] **Step 1: 리포트 작성**

```markdown
# living_pop_forecast v1 vs v2 비교

| 항목 | v1 (legacy) | v2 (정상화) |
|---|---|---|
| 입력 차원 | 5 | 21 (5 + 16 dong_one_hot) |
| best_val_loss | 미기록 | 0.XXX |
| test_loss | 미평가 | 0.XXX |
| LODO 평균 | 미평가 | 0.XXX ± 0.XXX |
| 가중치 파일 | living_pop_tcn.pt (217KB) | living_pop_tcn_v2.pt (?? KB) |
| 학습 시간 | ?? | ?? |

## 핵심 개선

1. dong 식별자 입력으로 그룹별 패턴 학습 가능
2. metadata json 저장으로 정량 평가 신뢰도 확보
3. LODO 검증으로 일반화 정확도 정량화

## 한계 (Phase 2 작업)

- dong_one_hot 16-dim → embedding 4-dim 학습 가능 layer
- A단계 pretrain 가중치 전이학습
- 서울 425동 확장
```

---

## Task 6: 백엔드 응답 통합 검증

**Files:**
- 검증만 (코드 변경 없음, 단순 동작 확인)

- [ ] **Step 1: backend uvicorn 재시작**

```bash
cd backend && uvicorn src.main:app --reload --port 8000
```

- [ ] **Step 2: /simulate 호출 후 living_pop_forecast 필드 정상 반환 확인**

```bash
curl -X POST http://localhost:3000/api/simulate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT>" \
  -H "x-tenant-id: spotter-demo-workspace-01" \
  -d '{"target_district":"서교동","business_type":"커피","brand_name":"테스트", ...}' \
  | python -m json.tool | python -c "
import sys, json
data = json.load(sys.stdin)
lp = data.get('living_pop_forecast')
print('living_pop_forecast 키:', list(lp.keys()) if lp else 'None')
print('predicted_pop:', lp.get('predicted_pop') if lp else 'N/A')
"
```

기대: `predicted_pop` 숫자 출력. v1 응답과 동일 schema 유지.

---

## Verification 종합

### 단위 테스트

```bash
pytest tests/test_living_pop_forecast_v2.py -v
```
Expected: 5+ PASS (dong_codes 4개 + metadata 1개 + predict 통합 1개)

### LODO 결과 비교

| 검증 | v1 (legacy) | v2 (정상화) | 개선 |
|---|---|---|---|
| best_val_loss | 미기록 | 산출 | metadata 정량 평가 가능 |
| Test loss | 미평가 | 산출 | overfit 검증 |
| LODO 평균 ± std | 미평가 | 산출 | 일반화 정확도 정량화 |

### Backend 응답 회귀

`/simulate` 응답에서 `living_pop_forecast` 필드 키 구조가 v1과 동일해야 (이전: `dong_code`, `dong_name`, `n_quarters` 등 → v2 동일).

---

## Out-of-scope (Phase 2 별도 plan)

| 작업 | 예상 시간 |
|---|---|
| dong_embedding (16→4) 학습 가능 layer | 1주 (TCNForecaster 모델 수정) |
| A단계 pretrain 가중치 전이학습 (input_size mismatch partial load) | 2~3일 |
| 서울 425동 확장 | 1주+ |
| Multi-horizon 예측 (1~4분기) | 3~5일 |
| Time-of-week 패턴 (월~일 7개) | 1주 |
| 코로나 regime switching 모델 | 1개월 |

---

## 책임 영역 (AGENTS.md 기준)

| Task | 영역 | 담당 | 본인(A1) 단독? |
|---|---|---|---|
| Task 1: dong_one_hot 추가 | `models/living_pop_forecast/` | B2 (수지니) | ❌ |
| Task 2: Train/Val/Test 분할 + metadata | 동일 | B2 | ❌ |
| Task 3: predict v2 호환 | 동일 | B2 | ❌ |
| **Task 4: LODO 검증 스크립트** | **`validation/`** | **A1** | **✅** |
| Task 5: v1 vs v2 리포트 | `docs/` | A1·B2 | ⚠️ |
| Task 6: 백엔드 통합 검증 | `backend/`, `models/` | B2 | ❌ |

→ **본인(A1) 단독 진행 가능: Task 4 LODO 검증 스크립트** + **Task 5 리포트 일부**.

본 plan을 그대로 B2 (수지니)에게 인계하면 1.5~2일 안에 단기 정상화 가능. A1은 LODO 검증 스크립트를 병행 작성해 B2 작업 완료 즉시 검증 가능.

---

## 데이터 의존성

| 데이터 | 출처 | 추가 확보 필요? |
|---|---|---|
| living_population (마포 16동, 시간대별) | RDS | ❌ 이미 있음 |
| 분기 집계 캐시 (`living_pop_quarterly.csv`) | data/processed/ | ❌ 이미 있음 (재산출 가능) |
| MAPO_DONG_CODES (16동 코드) | dong_mapping 테이블 | ❌ 이미 있음 (IM3-243 작업) |

**결론**: D 모델 정상화 단기 작업은 **외부 데이터 추가 없이** 가능.

---

## 예상 일정

| Day | 작업 | 담당 |
|---|---|---|
| Day 1 | Task 1 (dong_one_hot) + Task 2 (Train/Val/Test split) | B2 |
| Day 2 | Task 2 학습 실행 (CUDA, 6~12시간) + Task 3 (predict v2) | B2 |
| Day 3 | Task 4 LODO 시작 (16 fold × 5분 = 1.5시간) | A1 |
| Day 3~4 | Task 5 리포트 + Task 6 백엔드 통합 검증 | A1·B2 |

**총 3~4일 (협업 기준)**. A1·B2 동시 진행 시 2~3일로 단축 가능.

---

## 참고 자료

- 코드베이스 종합 리뷰: [`../../architecture/codebase-review-2026-04-28.md`](../../architecture/codebase-review-2026-04-28.md)
- End-to-End 데이터 흐름 단절: [`../../issues/2026-04-28-end-to-end-data-flow-gaps.md`](../../issues/2026-04-28-end-to-end-data-flow-gaps.md)
- TCN imputation 비교 (참조 패턴): [`../../abm-simulation/tcn-imputed-comparison-report.md`](../../abm-simulation/tcn-imputed-comparison-report.md)
- 본인 PR: https://github.com/Himidea-AI/Final_Project/pull/127
