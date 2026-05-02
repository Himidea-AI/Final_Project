# TCN 시나리오 시뮬레이터 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** TCN 매출 예측에 인터랙티브 시나리오 시뮬레이터 추가 — 사전 배치 섭동 분석으로 탄성치 테이블을 만들고, API로 노출하여 프론트엔드 슬라이더가 즉각 차트 반응을 보여줄 수 있게 한다.

**Architecture:** 배치 스크립트(`sensitivity.py`)가 156개 (동×업종) 조합 × 5개 슬라이더 × 7단계 섭동으로 TCN v2를 재추론하여 탄성치 JSON을 사전 계산한다. FastAPI 라우터(`backend/src/api/sensitivity.py`)가 해당 JSON을 캐시로 로드하여 `GET /predict/sensitivity`로 제공한다. 프론트엔드(C1 담당)는 탄성치 + Pearson 상관계수를 사용해 슬라이더 조절 시 실시간 차트를 렌더링한다.

**Tech Stack:** Python 3.12, PyTorch, pandas (Pearson corr), FastAPI, Pydantic v2, pytest

---

## 파일 구조

| 파일 | 역할 | 신규/수정 | 담당 |
|---|---|---|---|
| `models/tcn_forecast/sensitivity.py` | 배치 섭동 계산 + 상관계수 + JSON 저장 | 신규 | B2 |
| `tests/test_sensitivity.py` | sensitivity.py 단위 테스트 | 신규 | B2 |
| `backend/src/api/sensitivity.py` | GET /predict/sensitivity 라우터 | 신규 | B2 |
| `backend/src/main.py` | 라우터 등록 (2줄 추가) | 수정 | B2 |
| `models/tcn_forecast/weights/sensitivity_cache.json` | 배치 실행 결과 (런타임 생성) | 런타임 생성 | - |
| `models/tcn_forecast/weights/feature_correlations.json` | Pearson 상관계수 (런타임 생성) | 런타임 생성 | - |
| `frontend/src/components/ScenarioSimulator.tsx` | 슬라이더 UI + 차트 | 신규 | **C1** |

---

## Task 1: sensitivity.py 핵심 함수 (TDD 준비)

**Files:**
- Create: `models/tcn_forecast/sensitivity.py`
- Create: `tests/test_sensitivity.py`

### sensitivity.py 뼈대 작성

- [x] **Step 1: sensitivity.py 파일 생성**

```python
"""
TCN 시나리오 시뮬레이터 — 사전 배치 섭동 분석

슬라이더 5개(임대료/공실률/유동인구/트렌드/계절)에 대해
156개 (동×업종) 조합의 탄성치 테이블을 사전 계산하여 JSON으로 저장한다.

실행 방법:
    python -m models.tcn_forecast.sensitivity

저장 위치:
    models/tcn_forecast/weights/sensitivity_cache.json
    models/tcn_forecast/weights/feature_correlations.json

담당: B2 — 수지니
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

# 슬라이더명 → 실제 TCN 피처 목록 (유동인구는 3개 동시 적용)
SLIDER_FEATURES: dict[str, list[str]] = {
    "rent_1f": ["rent_1f"],
    "vacancy_rate": ["vacancy_rate"],
    "floating_pop": ["bus_flpop", "adstrd_flpop", "floating_pop"],
    "trend_score": ["trend_score"],
}

# ±% 섭동 레벨 (quarter_num 제외)
PERTURBATION_LEVELS: list[int] = [-30, -20, -10, 0, 10, 20, 30]

# quarter_num 슬라이더용 분기 값 (categorical)
QUARTER_VALUES: dict[str, int] = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

# Pearson 상관계수 계산 대상 피처 쌍
CORRELATION_PAIRS: list[tuple[str, str]] = [
    ("floating_pop", "rent_1f"),
    ("floating_pop", "vacancy_rate"),
    ("rent_1f", "vacancy_rate"),
]


# ---------------------------------------------------------------------------
# 헬퍼 함수 (단위 테스트 가능)
# ---------------------------------------------------------------------------


def get_feature_indices(feature_names: list[str], target_features: list[str]) -> list[int]:
    """feature_names 리스트에서 target_features의 인덱스를 반환한다.

    Parameters
    ----------
    feature_names : list[str]
        TCN 입력 피처 전체 목록 (ALL_FEATURES 순서).
    target_features : list[str]
        인덱스를 찾을 피처명 목록.

    Returns
    -------
    list[int]
        target_features 각각의 feature_names 내 인덱스.
        없는 피처는 무시한다.
    """
    name_to_idx = {name: i for i, name in enumerate(feature_names)}
    return [name_to_idx[f] for f in target_features if f in name_to_idx]


def compute_correlations(df: pd.DataFrame) -> dict[str, float]:
    """학습 데이터 DataFrame에서 슬라이더 피처 간 Pearson 상관계수를 계산한다.

    Parameters
    ----------
    df : pd.DataFrame
        슬라이더 피처 컬럼을 포함하는 데이터프레임.

    Returns
    -------
    dict[str, float]
        {"floating_pop→rent_1f": 0.63, ...} 형태의 상관계수 딕셔너리.
        소수점 4자리 반올림.
    """
    result: dict[str, float] = {}
    for f1, f2 in CORRELATION_PAIRS:
        if f1 in df.columns and f2 in df.columns:
            valid = df[[f1, f2]].dropna()
            if len(valid) >= 2:
                corr = valid[f1].corr(valid[f2])
                result[f"{f1}→{f2}"] = round(float(corr), 4)
    return result
```

- [x] **Step 2: 파일 저장 후 import 확인**

```bash
cd C:/AISpace/Final_Project_2 && python -c "from models.tcn_forecast.sensitivity import get_feature_indices, compute_correlations, SLIDER_FEATURES; print('OK')"
```

Expected: `OK`

- [x] **Step 3: Commit**

```bash
git add models/tcn_forecast/sensitivity.py
git commit -m "feat(sensitivity): sensitivity.py 뼈대 + 헬퍼 함수 추가"
```

---

## Task 2: 헬퍼 함수 단위 테스트

**Files:**
- Create: `tests/test_sensitivity.py`

- [x] **Step 1: 실패하는 테스트 작성**

```python
"""sensitivity.py 헬퍼 함수 단위 테스트."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from models.tcn_forecast.sensitivity import (
    CORRELATION_PAIRS,
    PERTURBATION_LEVELS,
    QUARTER_VALUES,
    SLIDER_FEATURES,
    compute_correlations,
    get_feature_indices,
)


def test_get_feature_indices_returns_correct_positions():
    features = ["a", "b", "c", "d", "e"]
    assert get_feature_indices(features, ["b", "d"]) == [1, 3]


def test_get_feature_indices_skips_missing():
    features = ["a", "b", "c"]
    # "z"는 없으므로 무시
    assert get_feature_indices(features, ["a", "z", "c"]) == [0, 2]


def test_get_feature_indices_empty_target():
    features = ["a", "b", "c"]
    assert get_feature_indices(features, []) == []


def test_compute_correlations_perfect_positive():
    df = pd.DataFrame({
        "floating_pop": [1.0, 2.0, 3.0, 4.0],
        "rent_1f":      [2.0, 4.0, 6.0, 8.0],   # 완벽한 양의 상관
        "vacancy_rate": [8.0, 6.0, 4.0, 2.0],   # 완벽한 음의 상관
    })
    result = compute_correlations(df)
    assert "floating_pop→rent_1f" in result
    assert "floating_pop→vacancy_rate" in result
    assert "rent_1f→vacancy_rate" in result
    assert abs(result["floating_pop→rent_1f"] - 1.0) < 0.001
    assert abs(result["floating_pop→vacancy_rate"] + 1.0) < 0.001


def test_compute_correlations_missing_column():
    # vacancy_rate 컬럼 없어도 나머지는 계산
    df = pd.DataFrame({
        "floating_pop": [1.0, 2.0, 3.0],
        "rent_1f":      [2.0, 4.0, 6.0],
    })
    result = compute_correlations(df)
    assert "floating_pop→rent_1f" in result
    assert "floating_pop→vacancy_rate" not in result
    assert "rent_1f→vacancy_rate" not in result


def test_compute_correlations_rounds_to_4_decimals():
    df = pd.DataFrame({
        "floating_pop": [1.0, 2.0, 3.0, 4.0, 5.0],
        "rent_1f":      [1.1, 2.3, 2.9, 4.2, 4.8],
        "vacancy_rate": [5.0, 4.0, 3.0, 2.0, 1.0],
    })
    result = compute_correlations(df)
    for v in result.values():
        assert len(str(v).split(".")[-1]) <= 4


def test_perturbation_levels_includes_zero():
    assert 0 in PERTURBATION_LEVELS


def test_perturbation_levels_symmetric():
    positives = [x for x in PERTURBATION_LEVELS if x > 0]
    negatives = [-x for x in PERTURBATION_LEVELS if x < 0]
    assert sorted(positives) == sorted(negatives)


def test_quarter_values_cover_all_quarters():
    assert set(QUARTER_VALUES.keys()) == {"Q1", "Q2", "Q3", "Q4"}
    assert set(QUARTER_VALUES.values()) == {1, 2, 3, 4}


def test_slider_features_floating_pop_maps_three_features():
    assert len(SLIDER_FEATURES["floating_pop"]) == 3
    assert "bus_flpop" in SLIDER_FEATURES["floating_pop"]
    assert "adstrd_flpop" in SLIDER_FEATURES["floating_pop"]
    assert "floating_pop" in SLIDER_FEATURES["floating_pop"]
```

- [x] **Step 2: 실패 확인**

```bash
cd C:/AISpace/Final_Project_2 && python -m pytest tests/test_sensitivity.py -v
```

Expected: 일부 FAIL (함수가 아직 완전히 구현되지 않은 경우) 또는 모두 PASS (뼈대가 이미 올바르면)

- [x] **Step 3: 테스트 통과 확인**

모든 테스트가 PASS여야 한다. 실패 시 `sensitivity.py`의 해당 함수를 수정.

```bash
cd C:/AISpace/Final_Project_2 && python -m pytest tests/test_sensitivity.py -v
```

Expected: 9 passed

- [x] **Step 4: Commit**

```bash
git add tests/test_sensitivity.py
git commit -m "test(sensitivity): 헬퍼 함수 단위 테스트 추가"
```

---

## Task 3: 섭동 추론 함수 구현

**Files:**
- Modify: `models/tcn_forecast/sensitivity.py`

`sensitivity.py`에 아래 함수들을 Task 1에서 만든 파일에 추가한다 (상수 정의 아래에 위치).

- [x] **Step 1: perturb_and_predict 함수 추가**

`CORRELATION_PAIRS` 상수 블록 바로 아래에 추가:

```python
# ---------------------------------------------------------------------------
# 섭동 추론
# ---------------------------------------------------------------------------


def perturb_and_predict(
    seq_scaled: np.ndarray,
    feature_indices: list[int],
    delta_pct: float,
    model: "torch.nn.Module",
    tgt_scaler: "sklearn.preprocessing.StandardScaler",
    device: "torch.device",
) -> float:
    """특정 피처를 delta_pct% 변화시킨 후 TCN v2로 예측하여 4분기 평균 매출(원)을 반환한다.

    Parameters
    ----------
    seq_scaled : np.ndarray
        shape (window_size, n_features). feat_scaler로 스케일링된 입력 시퀀스.
    feature_indices : list[int]
        섭동할 피처 인덱스 목록 (유동인구는 3개 동시 섭동).
    delta_pct : float
        변화율 (%). 예: 10.0 → +10%, -20.0 → -20%.
    model : TCNForecaster
        eval 모드의 TCN v2 모델 인스턴스.
    tgt_scaler : StandardScaler
        타겟 역변환용 스케일러.
    device : torch.device
        추론 디바이스 (CPU/CUDA).

    Returns
    -------
    float
        4분기 예측 매출 평균 (원 단위).
    """
    import torch

    seq_perturbed = seq_scaled.copy()
    for idx in feature_indices:
        seq_perturbed[:, idx] *= (1.0 + delta_pct / 100.0)

    with torch.no_grad():
        t = torch.tensor(seq_perturbed, dtype=torch.float32).unsqueeze(0).to(device)
        raw = model(t)  # (1, 4)
        raw_arr = raw.cpu().numpy().reshape(-1, 1)  # (4, 1)
        pred_log = float(tgt_scaler.inverse_transform(raw_arr).mean())
        return max(0.0, float(np.expm1(pred_log)))
```

- [x] **Step 2: quarter_num 섭동 함수 추가**

`perturb_and_predict` 함수 바로 아래에 추가:

```python
def perturb_quarter_and_predict(
    seq_scaled: np.ndarray,
    quarter_idx: int,
    quarter_value: int,
    feat_scaler: "sklearn.preprocessing.StandardScaler",
    model: "torch.nn.Module",
    tgt_scaler: "sklearn.preprocessing.StandardScaler",
    device: "torch.device",
) -> float:
    """quarter_num을 특정 분기값으로 설정 후 예측하여 4분기 평균 매출(원)을 반환한다.

    quarter_num은 ±% 섭동이 아닌 절댓값(1~4)으로 교체한다.
    feat_scaler로 다시 역변환 후 재스케일링하는 대신, 스케일링된 공간에서
    (quarter_value - scaler_mean) / scaler_std 로 직접 치환한다.

    Parameters
    ----------
    seq_scaled : np.ndarray
        shape (window_size, n_features). feat_scaler로 스케일링된 입력 시퀀스.
    quarter_idx : int
        ALL_FEATURES 내 quarter_num의 인덱스.
    quarter_value : int
        설정할 분기값 (1, 2, 3, 4).
    feat_scaler : StandardScaler
        피처 스케일러 (mean_, scale_ 접근용).
    model, tgt_scaler, device : 위와 동일.

    Returns
    -------
    float
        4분기 예측 매출 평균 (원 단위).
    """
    import torch

    seq_perturbed = seq_scaled.copy()
    # StandardScaler: scaled = (x - mean) / std
    mean_val = float(feat_scaler.mean_[quarter_idx])
    std_val = float(feat_scaler.scale_[quarter_idx])
    scaled_quarter = (quarter_value - mean_val) / std_val if std_val > 1e-10 else 0.0
    seq_perturbed[:, quarter_idx] = scaled_quarter

    with torch.no_grad():
        t = torch.tensor(seq_perturbed, dtype=torch.float32).unsqueeze(0).to(device)
        raw = model(t)  # (1, 4)
        raw_arr = raw.cpu().numpy().reshape(-1, 1)
        pred_log = float(tgt_scaler.inverse_transform(raw_arr).mean())
        return max(0.0, float(np.expm1(pred_log)))
```

- [x] **Step 3: import 확인**

```bash
cd C:/AISpace/Final_Project_2 && python -c "from models.tcn_forecast.sensitivity import perturb_and_predict, perturb_quarter_and_predict; print('OK')"
```

Expected: `OK`

- [x] **Step 4: 기존 테스트 통과 확인**

```bash
cd C:/AISpace/Final_Project_2 && python -m pytest tests/test_sensitivity.py -v
```

Expected: 9 passed

- [x] **Step 5: Commit**

```bash
git add models/tcn_forecast/sensitivity.py
git commit -m "feat(sensitivity): perturb_and_predict / perturb_quarter_and_predict 구현"
```

---

## Task 4: 배치 메인 러너 구현

**Files:**
- Modify: `models/tcn_forecast/sensitivity.py`

- [x] **Step 1: run_batch 함수 추가**

파일 맨 아래에 추가:

```python
# ---------------------------------------------------------------------------
# 배치 메인 러너
# ---------------------------------------------------------------------------


def run_batch(
    output_cache_path: Path | None = None,
    output_corr_path: Path | None = None,
) -> None:
    """156개 (동×업종) 조합 전체의 탄성치 테이블과 상관계수를 계산하여 JSON으로 저장한다.

    Parameters
    ----------
    output_cache_path : Path, optional
        탄성치 캐시 저장 경로. 기본: weights/sensitivity_cache.json
    output_corr_path : Path, optional
        상관계수 저장 경로. 기본: weights/feature_correlations.json
    """
    import pickle

    import torch

    from models.lstm_forecast.data_prep import (
        ALL_FEATURES,
        DB_URL,
        EXCLUDE_COMBOS,
        load_timeseries,
    )
    from models.tcn_forecast.model import WEIGHTS_DIR, TCNForecaster
    from models.tcn_forecast.train import load_scalers

    if output_cache_path is None:
        output_cache_path = WEIGHTS_DIR / "sensitivity_cache.json"
    if output_corr_path is None:
        output_corr_path = WEIGHTS_DIR / "feature_correlations.json"

    weights_path = WEIGHTS_DIR / "finetuned_mapo_tcn_v2.pt"
    scalers_path = WEIGHTS_DIR / "finetune_tcn_scalers_v2.pkl"

    if not weights_path.exists() or not scalers_path.exists():
        raise FileNotFoundError(
            f"v2 가중치 또는 스케일러 파일 없음: {weights_path}, {scalers_path}"
        )

    # 모델 + 스케일러 로드
    feat_scaler, tgt_scaler = load_scalers(scalers_path)
    input_size = len(feat_scaler.scale_)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = TCNForecaster(
        input_size=input_size,
        n_channels=128,
        kernel_size=2,
        dilations=[1, 2, 4, 8],
        dropout=0.2,
        output_size=4,
    )
    model.load_weights(weights_path)
    model.to(device)
    model.eval()
    logger.info("TCNForecaster v2 로드 완료 (input_size=%d)", input_size)

    feature_names = list(ALL_FEATURES)
    window_size = 12

    # 학습 데이터 전체 로드 (상관계수 계산 + 유효 조합 추출)
    logger.info("시계열 데이터 로드 중...")
    ts = load_timeseries(db_url=DB_URL, dong_prefix="1144")  # 마포구 전체 (dong_code 1144XXX)
    logger.info("데이터 로드 완료: %d 행", len(ts))

    # 상관계수 계산 (전체 데이터 기반)
    correlations = compute_correlations(ts)
    logger.info("상관계수 계산 완료: %s", correlations)

    # 유효 (dong_code, industry_code) 조합 추출 (window_size 이상 데이터 보유)
    valid_combos = []
    for (dong_code, industry_code), group in ts.groupby(["dong_code", "industry_code"]):
        dong_code, industry_code = str(dong_code), str(industry_code)
        if (dong_code, industry_code) in EXCLUDE_COMBOS:
            continue
        if len(group) >= window_size:
            valid_combos.append((dong_code, industry_code))

    logger.info("유효 조합 수: %d", len(valid_combos))

    # quarter_num 인덱스 확인
    quarter_idx_list = get_feature_indices(feature_names, ["quarter_num"])
    quarter_idx = quarter_idx_list[0] if quarter_idx_list else None

    cache: dict = {}
    total = len(valid_combos)

    for idx, (dong_code, industry_code) in enumerate(valid_combos):
        key = f"{dong_code}_{industry_code}"
        logger.info("[%d/%d] 처리 중: %s", idx + 1, total, key)

        group = ts[(ts["dong_code"] == dong_code) & (ts["industry_code"] == industry_code)]
        group = group.sort_values("quarter")
        actual_features = [c for c in feature_names if c in group.columns]

        if len(actual_features) != input_size:
            logger.warning("피처 수 불일치 (%s): skip", key)
            continue

        recent = group[actual_features].values.astype(np.float32)
        if len(recent) < window_size:
            pad_size = window_size - len(recent)
            recent = np.vstack([np.tile(recent[0], (pad_size, 1)), recent])

        seq_scaled = feat_scaler.transform(recent[-window_size:])

        # 기준 예측 (delta=0)
        baseline_raw = perturb_and_predict(seq_scaled, [], 0.0, model, tgt_scaler, device)
        baseline_q = []
        # 4분기 개별 값도 저장 (분기별 차트용)
        import torch
        with torch.no_grad():
            t = torch.tensor(seq_scaled, dtype=torch.float32).unsqueeze(0).to(device)
            raw = model(t).cpu().numpy().flatten()
        for ps in raw:
            pred_log = float(tgt_scaler.inverse_transform([[float(ps)]])[0][0])
            baseline_q.append(round(max(0.0, float(np.expm1(pred_log))), 0))

        elasticity: dict[str, dict] = {}

        # ±% 슬라이더 (4개)
        for slider_name, target_feats in SLIDER_FEATURES.items():
            feat_indices = get_feature_indices(actual_features, target_feats)
            if not feat_indices:
                continue
            level_results: dict[str, float] = {}
            for delta in PERTURBATION_LEVELS:
                pred = perturb_and_predict(
                    seq_scaled, feat_indices, float(delta), model, tgt_scaler, device
                )
                if baseline_raw > 0:
                    elast = round((pred - baseline_raw) / baseline_raw * 100.0, 4)
                else:
                    elast = 0.0
                key_str = f"{'+' if delta > 0 else ''}{delta}"
                level_results[key_str] = elast
            elasticity[slider_name] = level_results

        # quarter_num 슬라이더 (categorical)
        if quarter_idx is not None and "quarter_num" in actual_features:
            q_results: dict[str, float] = {}
            for q_label, q_val in QUARTER_VALUES.items():
                pred = perturb_quarter_and_predict(
                    seq_scaled, quarter_idx, q_val, feat_scaler, model, tgt_scaler, device
                )
                if baseline_raw > 0:
                    elast = round((pred - baseline_raw) / baseline_raw * 100.0, 4)
                else:
                    elast = 0.0
                q_results[q_label] = elast
            elasticity["quarter_num"] = q_results

        cache[f"{dong_code}_{industry_code}"] = {
            "baseline": baseline_q,
            "elasticity": elasticity,
        }

    # JSON 저장
    output_cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    logger.info("탄성치 캐시 저장: %s (%d 조합)", output_cache_path, len(cache))

    with open(output_corr_path, "w", encoding="utf-8") as f:
        json.dump(correlations, f, ensure_ascii=False, indent=2)
    logger.info("상관계수 저장: %s", output_corr_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_batch()
```

- [x] **Step 2: 실행 가능 여부 확인 (가중치 없어도 import만 확인)**

```bash
cd C:/AISpace/Final_Project_2 && python -c "from models.tcn_forecast.sensitivity import run_batch; print('run_batch OK')"
```

Expected: `run_batch OK`

- [x] **Step 3: ruff check**

```bash
cd C:/AISpace/Final_Project_2 && ruff check --fix models/tcn_forecast/sensitivity.py && ruff format models/tcn_forecast/sensitivity.py
```

Expected: 오류 없음

- [x] **Step 4: 기존 테스트 통과 확인**

```bash
cd C:/AISpace/Final_Project_2 && python -m pytest tests/test_sensitivity.py -v
```

Expected: 9 passed

- [x] **Step 5: Commit**

```bash
git add models/tcn_forecast/sensitivity.py
git commit -m "feat(sensitivity): run_batch 배치 러너 구현 (섭동 + 상관계수 + JSON 저장)"
```

---

## Task 5: 배치 실행 (가중치 파일 있을 때)

**Files:**
- Runtime 생성: `models/tcn_forecast/weights/sensitivity_cache.json`
- Runtime 생성: `models/tcn_forecast/weights/feature_correlations.json`

> **주의**: 이 Task는 v2 가중치 파일(`finetuned_mapo_tcn_v2.pt`, `finetune_tcn_scalers_v2.pkl`)이 존재해야 실행 가능하다.

- [x] **Step 1: 배치 실행**

```bash
cd C:/AISpace/Final_Project_2 && python -m models.tcn_forecast.sensitivity
```

Expected 로그 (약 10~30분 소요):
```
[INFO] TCNForecaster v2 로드 완료 (input_size=34)
[INFO] 시계열 데이터 로드 중...
[INFO] 유효 조합 수: 154
[INFO] [1/154] 처리 중: 11440530_CS100001
...
[INFO] 탄성치 캐시 저장: .../sensitivity_cache.json (154 조합)
[INFO] 상관계수 저장: .../feature_correlations.json
```

- [x] **Step 2: 생성 파일 확인**

```bash
python -c "
import json
with open('models/tcn_forecast/weights/sensitivity_cache.json') as f:
    cache = json.load(f)
print(f'조합 수: {len(cache)}')
first_key = next(iter(cache))
print(f'첫 번째 키: {first_key}')
print(f'baseline 분기 수: {len(cache[first_key][\"baseline\"])}')
print(f'elasticity 슬라이더: {list(cache[first_key][\"elasticity\"].keys())}')
"
```

Expected:
```
조합 수: 154
첫 번째 키: 11440530_CS100001
baseline 분기 수: 4
elasticity 슬라이더: ['rent_1f', 'vacancy_rate', 'floating_pop', 'trend_score', 'quarter_num']
```

- [x] **Step 3: 상관계수 확인**

```bash
python -c "
import json
with open('models/tcn_forecast/weights/feature_correlations.json') as f:
    corr = json.load(f)
print(json.dumps(corr, indent=2))
"
```

Expected: 세 쌍의 상관계수 출력 (floating_pop→rent_1f 등)

- [x] **Step 4: Commit (JSON 파일은 .gitignore에 있으므로 스크립트만)**

```bash
git add models/tcn_forecast/sensitivity.py
git commit -m "feat(sensitivity): 배치 실행 완료 확인 (sensitivity_cache.json 생성됨)"
```

---

## Task 6: API 라우터 구현

**Files:**
- Create: `backend/src/api/sensitivity.py`

- [x] **Step 1: 실패하는 API 테스트 먼저 작성**

`tests/test_sensitivity.py` 파일 하단에 아래 테스트를 추가:

```python
def test_sensitivity_endpoint_returns_correct_structure(monkeypatch, tmp_path):
    """캐시 파일을 mock으로 주입하여 /predict/sensitivity 응답 구조를 검증."""
    import sys
    from pathlib import Path

    _BACKEND = Path(__file__).resolve().parents[1] / "backend"
    if str(_BACKEND) not in sys.path:
        sys.path.insert(0, str(_BACKEND))

    from fastapi.testclient import TestClient

    # mock 캐시 파일 생성
    mock_cache = {
        "11440530_CS100001": {
            "baseline": [15000000.0, 15500000.0, 16000000.0, 15800000.0],
            "elasticity": {
                "rent_1f": {"-30": -8.2, "-20": -5.1, "-10": -2.4, "0": 0.0, "+10": 2.6, "+20": 5.3, "+30": 8.1},
                "vacancy_rate": {"-30": -3.1, "-20": -2.0, "-10": -1.0, "0": 0.0, "+10": 1.1, "+20": 2.2, "+30": 3.4},
                "floating_pop": {"-30": -12.0, "-20": -8.0, "-10": -4.0, "0": 0.0, "+10": 4.1, "+20": 8.3, "+30": 12.5},
                "trend_score": {"-30": -5.0, "-20": -3.3, "-10": -1.6, "0": 0.0, "+10": 1.7, "+20": 3.4, "+30": 5.2},
                "quarter_num": {"Q1": -3.2, "Q2": 1.1, "Q3": 5.8, "Q4": -2.4},
            },
        }
    }
    mock_corr = {
        "floating_pop→rent_1f": 0.63,
        "floating_pop→vacancy_rate": -0.41,
        "rent_1f→vacancy_rate": -0.38,
    }

    cache_file = tmp_path / "sensitivity_cache.json"
    corr_file = tmp_path / "feature_correlations.json"
    cache_file.write_text(__import__("json").dumps(mock_cache))
    corr_file.write_text(__import__("json").dumps(mock_corr))

    # 환경변수로 경로 오버라이드
    monkeypatch.setenv("SENSITIVITY_CACHE_PATH", str(cache_file))
    monkeypatch.setenv("SENSITIVITY_CORR_PATH", str(corr_file))

    # 모듈 리로드 (환경변수 반영)
    import importlib
    import src.api.sensitivity as sens_mod
    importlib.reload(sens_mod)

    from src.api.sensitivity import router
    from fastapi import FastAPI
    app_test = FastAPI()
    app_test.include_router(router)

    client = TestClient(app_test)
    response = client.get("/predict/sensitivity?dong_code=11440530&industry_code=CS100001")

    assert response.status_code == 200
    body = response.json()
    assert "elasticity" in body
    assert "correlations" in body
    assert "baseline_sales" in body
    assert len(body["baseline_sales"]) == 4
    assert set(body["elasticity"].keys()) == {
        "rent_1f", "vacancy_rate", "floating_pop", "trend_score", "quarter_num"
    }


def test_sensitivity_endpoint_404_for_unknown_combo(monkeypatch, tmp_path):
    """캐시에 없는 조합 요청 시 404 반환."""
    import sys
    from pathlib import Path
    import json

    _BACKEND = Path(__file__).resolve().parents[1] / "backend"
    if str(_BACKEND) not in sys.path:
        sys.path.insert(0, str(_BACKEND))

    from fastapi.testclient import TestClient

    cache_file = tmp_path / "sensitivity_cache.json"
    corr_file = tmp_path / "feature_correlations.json"
    cache_file.write_text("{}")
    corr_file.write_text("{}")

    monkeypatch.setenv("SENSITIVITY_CACHE_PATH", str(cache_file))
    monkeypatch.setenv("SENSITIVITY_CORR_PATH", str(corr_file))

    import importlib
    import src.api.sensitivity as sens_mod
    importlib.reload(sens_mod)

    from src.api.sensitivity import router
    from fastapi import FastAPI
    app_test = FastAPI()
    app_test.include_router(router)

    client = TestClient(app_test)
    response = client.get("/predict/sensitivity?dong_code=99999999&industry_code=CS999999")
    assert response.status_code == 404
```

- [x] **Step 2: 테스트 실패 확인 (라우터 파일 없음)**

```bash
cd C:/AISpace/Final_Project_2 && python -m pytest tests/test_sensitivity.py::test_sensitivity_endpoint_returns_correct_structure -v
```

Expected: ERROR (ModuleNotFoundError: src.api.sensitivity)

- [x] **Step 3: API 라우터 구현**

```python
"""
GET /predict/sensitivity — TCN 시나리오 시뮬레이터 탄성치 API

사전 계산된 sensitivity_cache.json + feature_correlations.json을 로드하여
프론트엔드 슬라이더에 필요한 탄성치 테이블과 피처 상관계수를 반환한다.

환경변수 오버라이드:
    SENSITIVITY_CACHE_PATH: 캐시 JSON 경로 (기본: models/tcn_forecast/weights/sensitivity_cache.json)
    SENSITIVITY_CORR_PATH: 상관계수 JSON 경로 (기본: models/tcn_forecast/weights/feature_correlations.json)

담당: B2 — 수지니
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/predict", tags=["sensitivity"])

# ---------------------------------------------------------------------------
# 캐시 경로 (환경변수 오버라이드 지원 — 테스트용)
# ---------------------------------------------------------------------------

_DEFAULT_CACHE = Path(__file__).resolve().parents[3] / "models" / "tcn_forecast" / "weights" / "sensitivity_cache.json"
_DEFAULT_CORR = Path(__file__).resolve().parents[3] / "models" / "tcn_forecast" / "weights" / "feature_correlations.json"

_CACHE_PATH = Path(os.environ.get("SENSITIVITY_CACHE_PATH", str(_DEFAULT_CACHE)))
_CORR_PATH = Path(os.environ.get("SENSITIVITY_CORR_PATH", str(_DEFAULT_CORR)))


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# 모듈 로드 시점에 캐시 읽기 (FastAPI 워커 startup과 동일 시점)
_SENSITIVITY_CACHE: dict[str, Any] = _load_json(_CACHE_PATH)
_CORRELATIONS: dict[str, float] = _load_json(_CORR_PATH)


# ---------------------------------------------------------------------------
# 응답 스키마
# ---------------------------------------------------------------------------


class SensitivityResponse(BaseModel):
    elasticity: dict[str, dict[str, float]]
    correlations: dict[str, float]
    baseline_sales: list[float]


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------


@router.get("/sensitivity", response_model=SensitivityResponse)
def get_sensitivity(dong_code: str, industry_code: str) -> SensitivityResponse:
    """특정 (동×업종) 조합의 탄성치 테이블과 피처 상관계수를 반환한다.

    Parameters
    ----------
    dong_code : str
        행정동 코드 (예: "11440530")
    industry_code : str
        업종 코드 (예: "CS100001")

    Returns
    -------
    SensitivityResponse
        elasticity: 슬라이더별 탄성치 테이블
        correlations: 피처 간 Pearson 상관계수
        baseline_sales: TCN 기준 예측 4분기 매출
    """
    key = f"{dong_code}_{industry_code}"
    entry = _SENSITIVITY_CACHE.get(key)

    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"탄성치 데이터 없음: {key}. 배치 스크립트를 먼저 실행하세요.",
        )

    return SensitivityResponse(
        elasticity=entry["elasticity"],
        correlations=_CORRELATIONS,
        baseline_sales=entry["baseline"],
    )
```

파일 경로: `backend/src/api/sensitivity.py`

- [x] **Step 4: 테스트 통과 확인**

```bash
cd C:/AISpace/Final_Project_2 && python -m pytest tests/test_sensitivity.py::test_sensitivity_endpoint_returns_correct_structure tests/test_sensitivity.py::test_sensitivity_endpoint_404_for_unknown_combo -v
```

Expected: 2 passed

- [x] **Step 5: 전체 sensitivity 테스트 통과**

```bash
cd C:/AISpace/Final_Project_2 && python -m pytest tests/test_sensitivity.py -v
```

Expected: 11 passed

- [x] **Step 6: ruff check**

```bash
cd C:/AISpace/Final_Project_2 && ruff check --fix backend/src/api/sensitivity.py && ruff format backend/src/api/sensitivity.py
```

- [x] **Step 7: Commit**

```bash
git add backend/src/api/sensitivity.py tests/test_sensitivity.py
git commit -m "feat(api): GET /predict/sensitivity 라우터 + 테스트 추가"
```

---

## Task 7: main.py에 라우터 등록

**Files:**
- Modify: `backend/src/main.py`

- [x] **Step 1: main.py에서 customer_segment 라우터 등록 패턴 확인**

`backend/src/main.py` 라인 152-155:
```python
# --- customer_segment REST (MLP 단발 호출, frontend 실시간 미리보기용) ---
from src.api.customer_segment import router as _customer_segment_router  # noqa: E402

app.include_router(_customer_segment_router)
```

- [x] **Step 2: 같은 패턴으로 sensitivity 라우터 등록**

`backend/src/main.py`에서 `app.include_router(_customer_segment_router)` 바로 뒤에 추가:

```python
# --- sensitivity REST (TCN 시나리오 시뮬레이터 탄성치 캐시 조회) ---
from src.api.sensitivity import router as _sensitivity_router  # noqa: E402

app.include_router(_sensitivity_router)
```

- [x] **Step 3: 서버 기동 확인**

```bash
cd C:/AISpace/Final_Project_2/backend && python -c "from src.main import app; print('라우터 등록 OK:', [r.path for r in app.routes if 'sensitivity' in r.path])"
```

Expected:
```
라우터 등록 OK: ['/predict/sensitivity']
```

- [x] **Step 4: 전체 테스트 이상 없음 확인**

```bash
cd C:/AISpace/Final_Project_2 && python -m pytest tests/test_sensitivity.py tests/test_predict_contract.py -v
```

Expected: 모두 passed

- [x] **Step 5: ruff check**

```bash
cd C:/AISpace/Final_Project_2 && ruff check --fix backend/src/main.py && ruff format backend/src/main.py
```

- [x] **Step 6: Commit**

```bash
git add backend/src/main.py
git commit -m "feat(main): /predict/sensitivity 라우터 등록"
```

---

## Task 8: C1 인터페이스 계약 (B2 → C1 전달용)

> **이 Task는 B2가 구현하지 않는다. C1(강민)에게 아래 명세를 전달한다.**

**API 명세 (B2 완료 후 사용 가능):**

```
GET /predict/sensitivity?dong_code={dong_code}&industry_code={industry_code}

응답 예시:
{
  "elasticity": {
    "rent_1f":      {"-30": -8.2, "-20": -5.1, "-10": -2.4, "0": 0.0, "+10": 2.6, "+20": 5.3, "+30": 8.1},
    "vacancy_rate": {"-30": -3.1, ..., "+30": 3.4},
    "floating_pop": {"-30": -12.0, ..., "+30": 12.5},
    "trend_score":  {"-30": -5.0, ..., "+30": 5.2},
    "quarter_num":  {"Q1": -3.2, "Q2": 1.1, "Q3": 5.8, "Q4": -2.4}
  },
  "correlations": {
    "floating_pop→rent_1f":      0.63,
    "floating_pop→vacancy_rate": -0.41,
    "rent_1f→vacancy_rate":      -0.38
  },
  "baseline_sales": [15000000.0, 15500000.0, 16000000.0, 15800000.0]
}
```

**프론트엔드 시나리오 매출 계산 로직 (C1 참고):**

```typescript
// 슬라이더 값 → 탄성치 보간 → 복합 효과 가산
function calcScenarioSales(
  baselineSales: number[],         // 4개 분기
  elasticity: Record<string, Record<string, number>>,
  sliderValues: {                  // 현재 슬라이더 상태
    rent_1f: number,               // -30 ~ +30
    vacancy_rate: number,
    floating_pop: number,
    trend_score: number,
    quarter_num: "Q1" | "Q2" | "Q3" | "Q4",
  },
  correlations: Record<string, number>,
): number[] {
  // 1. 상관계수 연동 (유동인구 → 임대료, 공실률 자동 조절)
  const adjRent = sliderValues.rent_1f
    + sliderValues.floating_pop * (correlations["floating_pop→rent_1f"] ?? 0);
  const adjVacancy = sliderValues.vacancy_rate
    + sliderValues.floating_pop * (correlations["floating_pop→vacancy_rate"] ?? 0);

  // 2. 각 슬라이더 탄성치 보간 (선형)
  const rentElast = interpolateElasticity(elasticity.rent_1f, adjRent);
  const vacElast  = interpolateElasticity(elasticity.vacancy_rate, adjVacancy);
  const popElast  = interpolateElasticity(elasticity.floating_pop, sliderValues.floating_pop);
  const trendElast = interpolateElasticity(elasticity.trend_score, sliderValues.trend_score);
  const quarterElast = elasticity.quarter_num?.[sliderValues.quarter_num] ?? 0;

  // 3. 복합 가산
  const totalElast = (rentElast + vacElast + popElast + trendElast + quarterElast) / 100;
  return baselineSales.map(q => Math.round(q * (1 + totalElast)));
}

// 선형 보간 헬퍼
function interpolateElasticity(
  table: Record<string, number>,  // {"-30": -8.2, ..., "+30": 8.1}
  value: number,                   // e.g., 15
): number {
  const keys = Object.keys(table).map(Number).sort((a, b) => a - b);
  if (value <= keys[0]) return table[String(keys[0])];
  if (value >= keys[keys.length - 1]) return table[`+${keys[keys.length - 1]}`] ?? table[String(keys[keys.length - 1])];
  const lower = keys.filter(k => k <= value).pop()!;
  const upper = keys.find(k => k > value)!;
  const t = (value - lower) / (upper - lower);
  const lKey = lower >= 0 ? `+${lower}` : String(lower);
  const uKey = upper >= 0 ? `+${upper}` : String(upper);
  // "0" key는 "+0"이 아님
  const lVal = table[lower === 0 ? "0" : lKey] ?? 0;
  const uVal = table[upper === 0 ? "0" : uKey] ?? 0;
  return lVal + t * (uVal - lVal);
}
```

**차트 구성 (C1 참고):**
- Recharts `LineChart`
- x축: `["Q1", "Q2", "Q3", "Q4"]`
- y축: 매출액 (원, formatKrw 포맷)
- `Line` 두 개: `dataKey="baseline"` (파란색), `dataKey="scenario"` (주황색)
- 툴팁: 두 선의 차이값 (±원) 표시
- 위치: 기존 매출 예측 결과 카드 내 접기/펼치기 `<details>` 또는 `<Collapse>`

---

## 최종 확인 체크리스트

- [x] `python -m pytest tests/test_sensitivity.py -v` → **20 passed** (계획 시 11 → 실제 ETag/logging 테스트 추가로 20)
- [x] `python -m models.tcn_forecast.sensitivity` 배치 실행 성공 (153 조합, 계획 시 154 → 실제 EXCLUDE_COMBOS 적용 후 153)
- [x] `GET /predict/sensitivity?dong_code=11440530&industry_code=CS100001` → 200 OK
- [x] `GET /predict/sensitivity?dong_code=99999999&industry_code=CS999999` → 404
- [x] `ruff check backend/src/api/sensitivity.py models/tcn_forecast/sensitivity.py` → 오류 없음
- [x] C1에게 Task 8 인터페이스 계약 전달 준비 완료 (디스코드 메시지 작성 — 사용자가 발송)

---

## 계획 외 추가 작업 (2026-05-02)

- **Important fix (커밋 `0559b84`)**: `_load_json`에 `logging.warning`/`logger.error` 추가 — 캐시 미존재/JSON 파싱 실패 시 운영 진단성 확보, FastAPI 부팅 실패 방지
- **Refactor (커밋 `1a6ec19`)**: `_load_json`에 `label` 파라미터 추가 (sensitivity_cache vs feature_correlations 로그 구분), 테스트 파일 import 부트스트랩 정리
- **ETag 지원 (커밋 `36721ba`)**: 캐시 파일 mtime+size 기반 ETag 응답, If-None-Match 일치 시 304 Not Modified, `Cache-Control: public, must-revalidate` 헤더 — 별도 엔드포인트 분리의 캐싱 이점 실제 활용

## 운영 정책 (확정)

- 캐시 파일 배포: **수동** (운영 서버에서 `python -m models.tcn_forecast.sensitivity` 실행)
- 캐시 갱신 적용: **백엔드 재기동** (모듈 import 시점 로드, 핫리로드 미지원)
- HTTP 캐시: **ETag + must-revalidate** (브라우저 자동 처리, 캐시 갱신 시 ETag 자동 변경)
- 환경변수 오버라이드: `SENSITIVITY_CACHE_PATH`, `SENSITIVITY_CORR_PATH`
