# TCN 시나리오 시뮬레이터 S3 구현 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** TCN 시나리오 시뮬레이터에 (1) 분기별로 비틀리는 그래프와 (2) Master-Detail 비교 UX를 추가한다.

**Architecture:** 배치 캐시(`sensitivity_cache.json`)의 elasticity 값을 단일 float에서 분기별 `list[float]`로 확장하고 슬라이더 5개 중 2개를 교체한다(rent_1f/floating_pop → cpi_index/opr_sale_mt_avg). 프론트는 좌측 후보 카드 리스트(Master) + 우측 드릴다운(Detail) 레이아웃으로 재구성한다.

**Tech Stack:** Python 3.11 / PyTorch / FastAPI / Pydantic v2 / pytest / React 18 / TypeScript / Tailwind / Recharts / vitest

**기반 스펙:** `docs/superpowers/specs/2026-05-03-tcn-scenario-simulator-s3-design.md`

---

## 작업 환경

- 브랜치: `sj_simul` (모든 구현 작업은 이 브랜치에서 진행, 추후 dev로 머지)
- 기존 코드 위치:
  - 백엔드 배치: `models/tcn_forecast/sensitivity.py`
  - 백엔드 API: `backend/src/api/sensitivity.py`
  - 백엔드 테스트: `tests/test_sensitivity.py`
  - 프론트 컨테이너: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictScenarioSimTab.tsx`
  - 프론트 훅: `frontend/src/hooks/useElasticity.ts`
  - 프론트 타입: `frontend/src/types/elasticity.ts`
- 새로 만들 디렉토리: `frontend/src/components/SimulationResult/dashboard/sub/predict/scenario/`

---

## File Structure

| 파일 | 역할 | 상태 |
|------|------|------|
| `models/tcn_forecast/sensitivity.py` | 배치 + perturb 함수 | 수정 |
| `backend/src/api/sensitivity.py` | API + Pydantic schema | 수정 |
| `tests/test_sensitivity.py` | 백엔드 단위 테스트 | 수정 + 추가 |
| `frontend/src/types/elasticity.ts` | 응답 타입 | 수정 |
| `frontend/src/hooks/useElasticity.ts` | 단일 후보 fetch | 수정 |
| `frontend/src/hooks/useScenarioCandidates.ts` | 후보 상태 격리 | 신규 |
| `frontend/src/hooks/useElasticityComparison.ts` | N개 병렬 fetch | 신규 |
| `frontend/src/components/.../scenario/ScenarioCandidateCard.tsx` | 후보 카드 | 신규 |
| `frontend/src/components/.../scenario/ScenarioCandidateList.tsx` | 좌측 패널 | 신규 |
| `frontend/src/components/.../scenario/ScenarioForecastChart.tsx` | 분기별 비틀린 곡선 | 신규 |
| `frontend/src/components/.../scenario/ScenarioDetailPanel.tsx` | 우측 드릴다운 | 신규 |
| `frontend/src/components/.../predict/PredictScenarioSimTab.tsx` | Master-Detail 컨테이너 | 수정 |

---

## Phase 1 — 백엔드 배치 파이프라인

### Task 1: SLIDER_FEATURES + CORRELATION_PAIRS 재구성

**Files:**
- Modify: `models/tcn_forecast/sensitivity.py:38-56`

- [ ] **Step 1: 모듈 docstring과 SLIDER_FEATURES 업데이트**

`models/tcn_forecast/sensitivity.py` 상단 docstring 한 줄과 `SLIDER_FEATURES` 딕셔너리, `CORRELATION_PAIRS` 리스트를 다음과 같이 교체.

```python
"""
TCN 시나리오 시뮬레이터 — 사전 배치 섭동 분석

슬라이더 5개(공실률/물가/상권 활성도/트렌드/계절)에 대해
156개 (동×업종) 조합의 분기별 탄성치 테이블을 사전 계산하여 JSON으로 저장한다.
...
"""

# 슬라이더명 → 실제 TCN 피처 목록
SLIDER_FEATURES: dict[str, list[str]] = {
    "vacancy_rate": ["vacancy_rate"],
    "trend_score": ["trend_score"],
    "cpi_index": ["cpi_index"],
    "opr_sale_mt_avg": ["opr_sale_mt_avg"],
}

# ±% 섭동 레벨 (quarter_num 제외)
PERTURBATION_LEVELS: list[int] = [-30, -20, -10, 0, 10, 20, 30]

# quarter_num 슬라이더용 분기 값 (categorical)
QUARTER_VALUES: dict[str, int] = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

# Pearson 상관계수 계산 대상 피처 쌍
CORRELATION_PAIRS: list[tuple[str, str]] = [
    ("vacancy_rate", "cpi_index"),
    ("vacancy_rate", "opr_sale_mt_avg"),
    ("cpi_index", "opr_sale_mt_avg"),
    ("trend_score", "opr_sale_mt_avg"),
]
```

- [ ] **Step 2: 기존 테스트 실행해서 깨지는 항목 확인**

Run: `pytest tests/test_sensitivity.py -v`
Expected: `test_compute_correlations_*` 일부 FAIL (rent_1f/floating_pop 키 사라짐). `test_get_feature_indices_*`는 PASS.

- [ ] **Step 3: tests/test_sensitivity.py의 상관계수 테스트를 새 키로 갱신**

`test_compute_correlations_perfect_positive` / `test_compute_correlations_missing_column` / `test_compute_correlations_rounds_to_4_decimals` 3건의 DataFrame 컬럼명과 assert 키를 새 슬라이더(`vacancy_rate`/`cpi_index`/`opr_sale_mt_avg`)에 맞춰 교체.

예시 (`test_compute_correlations_perfect_positive`):
```python
def test_compute_correlations_perfect_positive():
    df = pd.DataFrame(
        {
            "vacancy_rate": [1.0, 2.0, 3.0, 4.0],
            "cpi_index": [2.0, 4.0, 6.0, 8.0],
            "opr_sale_mt_avg": [8.0, 6.0, 4.0, 2.0],
        }
    )
    result = compute_correlations(df)
    assert "vacancy_rate→cpi_index" in result
    assert abs(result["vacancy_rate→cpi_index"] - 1.0) < 0.001
    assert abs(result["vacancy_rate→opr_sale_mt_avg"] + 1.0) < 0.001
    assert "cpi_index→opr_sale_mt_avg" in result
```

- [ ] **Step 4: 테스트 재실행해서 PASS 확인**

Run: `pytest tests/test_sensitivity.py -v -k correlations`
Expected: 모든 correlations 테스트 PASS.

- [ ] **Step 5: ruff + commit**

```bash
ruff check --fix models/tcn_forecast/sensitivity.py tests/test_sensitivity.py
ruff format models/tcn_forecast/sensitivity.py tests/test_sensitivity.py
git add models/tcn_forecast/sensitivity.py tests/test_sensitivity.py
git commit -m "feat(sensitivity): 슬라이더 재구성 — rent_1f/floating_pop 제거, cpi_index/opr_sale_mt_avg 추가"
```

---

### Task 2: perturb_and_predict() 분기별 list[float] 반환

**Files:**
- Modify: `models/tcn_forecast/sensitivity.py:113-154`
- Test: `tests/test_sensitivity.py` (신규 테스트 추가)

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_sensitivity.py` 하단에 추가:
```python
def test_perturb_and_predict_returns_list_of_4_quarters():
    """perturb_and_predict는 분기별 4개 값의 list[float]를 반환해야 한다."""
    import torch
    from sklearn.preprocessing import MinMaxScaler

    from models.tcn_forecast.sensitivity import perturb_and_predict

    class StubModel(torch.nn.Module):
        def forward(self, x):  # noqa: D401
            return torch.tensor([[0.1, 0.2, 0.3, 0.4]], dtype=torch.float32)

    model = StubModel().eval()
    tgt_scaler = MinMaxScaler()
    tgt_scaler.fit(np.array([[0.0], [10.0]]))
    seq = np.zeros((12, 5), dtype=np.float32)
    device = torch.device("cpu")

    result = perturb_and_predict(seq, [], 0.0, model, tgt_scaler, device)

    assert isinstance(result, list)
    assert len(result) == 4
    assert all(isinstance(v, float) for v in result)
    assert all(v >= 0.0 for v in result)
```

- [ ] **Step 2: 테스트 실행해서 FAIL 확인**

Run: `pytest tests/test_sensitivity.py::test_perturb_and_predict_returns_list_of_4_quarters -v`
Expected: FAIL (현재 구현은 float 반환).

- [ ] **Step 3: perturb_and_predict 구현 교체**

`models/tcn_forecast/sensitivity.py:113-154` 함수 전체를 다음으로 교체. docstring 반환 설명도 같이 갱신.

```python
def perturb_and_predict(
    seq_scaled: np.ndarray,
    feature_indices: list[int],
    delta_pct: float,
    model: torch.nn.Module,
    tgt_scaler: sklearn.preprocessing.StandardScaler | sklearn.preprocessing.MinMaxScaler,
    device: torch.device,
) -> list[float]:
    """특정 피처를 delta_pct% 변화시킨 후 TCN v2로 예측하여 분기별 매출(원) list를 반환한다.

    Returns
    -------
    list[float]
        길이 4의 분기별 매출 예측치 (Q1, Q2, Q3, Q4 순). 각 값은 원 단위, 음수 클립.
    """
    import torch

    seq_perturbed = seq_scaled.copy()
    for idx in feature_indices:
        seq_perturbed[:, idx] *= 1.0 + delta_pct / 100.0

    with torch.no_grad():
        t = torch.tensor(seq_perturbed, dtype=torch.float32).unsqueeze(0).to(device)
        raw = model(t).cpu().numpy().flatten()

    quarters: list[float] = []
    for v in raw:
        pred_log = float(tgt_scaler.inverse_transform([[float(v)]])[0][0])
        quarters.append(max(0.0, float(np.expm1(pred_log))))
    return quarters
```

- [ ] **Step 4: 테스트 PASS 확인**

Run: `pytest tests/test_sensitivity.py::test_perturb_and_predict_returns_list_of_4_quarters -v`
Expected: PASS.

- [ ] **Step 5: Commit (run_batch는 다음 Task에서 함께 수정)**

```bash
ruff check --fix models/tcn_forecast/sensitivity.py tests/test_sensitivity.py
ruff format models/tcn_forecast/sensitivity.py tests/test_sensitivity.py
git add models/tcn_forecast/sensitivity.py tests/test_sensitivity.py
git commit -m "feat(sensitivity): perturb_and_predict 반환을 list[float] 4분기로 확장"
```

---

### Task 3: perturb_quarter_and_predict() 동일 변경

**Files:**
- Modify: `models/tcn_forecast/sensitivity.py:193-235`
- Test: `tests/test_sensitivity.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_sensitivity.py` 하단에 추가:
```python
def test_perturb_quarter_and_predict_returns_list_of_4_quarters():
    import torch
    from sklearn.preprocessing import MinMaxScaler

    from models.tcn_forecast.sensitivity import perturb_quarter_and_predict

    class StubModel(torch.nn.Module):
        def forward(self, x):
            return torch.tensor([[0.1, 0.2, 0.3, 0.4]], dtype=torch.float32)

    model = StubModel().eval()
    tgt_scaler = MinMaxScaler()
    tgt_scaler.fit(np.array([[0.0], [10.0]]))
    feat_scaler = MinMaxScaler()
    feat_scaler.fit(np.array([[1.0, 0.0], [4.0, 1.0]]))  # quarter_num 인덱스 0
    seq = np.zeros((12, 2), dtype=np.float32)
    device = torch.device("cpu")

    result = perturb_quarter_and_predict(seq, 0, 2, feat_scaler, model, tgt_scaler, device)

    assert isinstance(result, list)
    assert len(result) == 4
```

- [ ] **Step 2: 테스트 FAIL 확인**

Run: `pytest tests/test_sensitivity.py::test_perturb_quarter_and_predict_returns_list_of_4_quarters -v`
Expected: FAIL.

- [ ] **Step 3: 함수 구현 교체**

`models/tcn_forecast/sensitivity.py:193-235`의 `perturb_quarter_and_predict` 반환 타입과 본문을 perturb_and_predict와 동일 패턴으로 변경.

```python
def perturb_quarter_and_predict(
    seq_scaled: np.ndarray,
    quarter_idx: int,
    quarter_value: int,
    feat_scaler: sklearn.preprocessing.StandardScaler | sklearn.preprocessing.MinMaxScaler,
    model: torch.nn.Module,
    tgt_scaler: sklearn.preprocessing.StandardScaler | sklearn.preprocessing.MinMaxScaler,
    device: torch.device,
) -> list[float]:
    """quarter_num을 특정 분기값으로 설정 후 예측하여 분기별 매출(원) list를 반환한다."""
    import torch

    seq_perturbed = seq_scaled.copy()
    seq_perturbed[:, quarter_idx] = _scale_quarter_value(feat_scaler, quarter_idx, quarter_value)

    with torch.no_grad():
        t = torch.tensor(seq_perturbed, dtype=torch.float32).unsqueeze(0).to(device)
        raw = model(t).cpu().numpy().flatten()

    quarters: list[float] = []
    for v in raw:
        pred_log = float(tgt_scaler.inverse_transform([[float(v)]])[0][0])
        quarters.append(max(0.0, float(np.expm1(pred_log))))
    return quarters
```

- [ ] **Step 4: 테스트 PASS 확인**

Run: `pytest tests/test_sensitivity.py::test_perturb_quarter_and_predict_returns_list_of_4_quarters -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
ruff check --fix models/tcn_forecast/sensitivity.py tests/test_sensitivity.py
ruff format models/tcn_forecast/sensitivity.py tests/test_sensitivity.py
git add models/tcn_forecast/sensitivity.py tests/test_sensitivity.py
git commit -m "feat(sensitivity): perturb_quarter_and_predict 반환 list[float] 4분기로 확장"
```

---

### Task 4: run_batch() 캐시 schema list[float] 적용

**Files:**
- Modify: `models/tcn_forecast/sensitivity.py:243-401` (run_batch 본문)

- [ ] **Step 1: run_batch에서 baseline_q 별도 산출 블록 제거**

`models/tcn_forecast/sensitivity.py:346-354` (baseline_raw + baseline_q 산출 부분)을 다음으로 교체. perturb_and_predict 자체가 이제 list[float]를 반환하므로 별도 inverse_transform 루프 불필요.

```python
        # 기준 예측 (delta=0) — 4분기 list 반환
        baseline_q_raw = perturb_and_predict(seq_scaled, [], 0.0, model, tgt_scaler, device)
        baseline_q = [round(v, 0) for v in baseline_q_raw]
        baseline_total = sum(baseline_q_raw)
```

- [ ] **Step 2: 슬라이더 루프의 elasticity 계산을 분기별 list로 교체**

`models/tcn_forecast/sensitivity.py:358-372` 슬라이더 루프 전체를 다음으로 교체:

```python
        # ±% 슬라이더 (4개) — 분기별 % 변화율 list 저장
        for slider_name, target_feats in SLIDER_FEATURES.items():
            feat_indices = get_feature_indices(actual_features, target_feats)
            if not feat_indices:
                continue
            level_results: dict[str, list[float]] = {}
            for delta in PERTURBATION_LEVELS:
                pred_q = perturb_and_predict(
                    seq_scaled, feat_indices, float(delta), model, tgt_scaler, device
                )
                per_quarter: list[float] = []
                for q_idx, p in enumerate(pred_q):
                    base = baseline_q_raw[q_idx]
                    if base > 0:
                        per_quarter.append(round((p - base) / base * 100.0, 4))
                    else:
                        per_quarter.append(0.0)
                key_str = f"{'+' if delta > 0 else ''}{delta}"
                level_results[key_str] = per_quarter
            elasticity[slider_name] = level_results
```

- [ ] **Step 3: quarter_num 슬라이더도 분기별 list로 교체**

`models/tcn_forecast/sensitivity.py:374-386` quarter_num 블록을 다음으로 교체:

```python
        # quarter_num 슬라이더 (categorical) — 분기별 % 변화율 list 저장
        if quarter_idx is not None and "quarter_num" in actual_features:
            q_results: dict[str, list[float]] = {}
            for q_label, q_val in QUARTER_VALUES.items():
                pred_q = perturb_quarter_and_predict(
                    seq_scaled, quarter_idx, q_val, feat_scaler, model, tgt_scaler, device
                )
                per_quarter = []
                for q_idx, p in enumerate(pred_q):
                    base = baseline_q_raw[q_idx]
                    if base > 0:
                        per_quarter.append(round((p - base) / base * 100.0, 4))
                    else:
                        per_quarter.append(0.0)
                q_results[q_label] = per_quarter
            elasticity["quarter_num"] = q_results
```

- [ ] **Step 4: ruff + 빠른 import 검증**

```bash
ruff check --fix models/tcn_forecast/sensitivity.py
ruff format models/tcn_forecast/sensitivity.py
python -c "from models.tcn_forecast.sensitivity import run_batch; print('import OK')"
```
Expected: `import OK` 출력.

- [ ] **Step 5: Commit (실제 캐시 재생성은 Task 5에서)**

```bash
git add models/tcn_forecast/sensitivity.py
git commit -m "feat(sensitivity): run_batch 캐시 schema 분기별 list[float]로 확장"
```

---

### Task 5: 캐시 재생성 + 결과 검증

**Files:**
- 영향: `models/tcn_forecast/weights/sensitivity_cache.json` (재생성)
- 영향: `models/tcn_forecast/weights/feature_correlations.json` (재생성)

- [ ] **Step 1: 기존 캐시 백업 (롤백 대비)**

```bash
cp models/tcn_forecast/weights/sensitivity_cache.json models/tcn_forecast/weights/sensitivity_cache.json.bak
cp models/tcn_forecast/weights/feature_correlations.json models/tcn_forecast/weights/feature_correlations.json.bak
```

- [ ] **Step 2: 배치 실행**

```bash
python -m models.tcn_forecast.sensitivity
```
Expected: "유효 조합 수: ~150대"·"탄성치 캐시 저장: ..." 로그. 4,896회 추론 완료.

- [ ] **Step 3: 결과 schema 빠른 점검**

```bash
python -c "
import json
d = json.load(open('models/tcn_forecast/weights/sensitivity_cache.json', encoding='utf-8'))
key = next(iter(d))
entry = d[key]
print('샘플 키:', key)
print('baseline 길이:', len(entry['baseline']))
elast = entry['elasticity']
print('슬라이더:', list(elast.keys()))
sample_slider = list(elast.keys())[0]
sample_level = next(iter(elast[sample_slider]))
print(f'{sample_slider}[{sample_level}] →', elast[sample_slider][sample_level])
assert isinstance(elast[sample_slider][sample_level], list), 'level value must be list'
assert len(elast[sample_slider][sample_level]) == 4, 'must be 4 quarters'
print('OK: 분기별 list 검증 통과')
"
```
Expected: 슬라이더 5개(vacancy_rate/trend_score/cpi_index/opr_sale_mt_avg/quarter_num), 길이 4 list, "OK" 출력.

- [ ] **Step 4: 백업 .bak 파일 정리 (성공 시)**

```bash
rm models/tcn_forecast/weights/sensitivity_cache.json.bak
rm models/tcn_forecast/weights/feature_correlations.json.bak
```

- [ ] **Step 5: .gitignore 확인 (캐시는 커밋하지 않음)**

```bash
git check-ignore models/tcn_forecast/weights/sensitivity_cache.json
```
Expected: 경로 출력(=ignore됨) 또는 명시적 .gitignore 라인. 만약 ignore되지 않는다면 `.gitignore`에 다음 라인 추가:
```
models/tcn_forecast/weights/sensitivity_cache.json
models/tcn_forecast/weights/feature_correlations.json
```
그 후 `git add .gitignore && git commit -m "chore(gitignore): TCN sensitivity 캐시 무시"`.

---

## Phase 2 — 백엔드 API

### Task 6: SensitivityResponse Pydantic schema 확장

**Files:**
- Modify: `backend/src/api/sensitivity.py:65-68`
- Test: `tests/test_sensitivity.py`

- [ ] **Step 1: API 응답 회귀 테스트 작성**

`tests/test_sensitivity.py` 하단에 추가:
```python
def test_sensitivity_response_elasticity_is_quarterly_list(tmp_path, monkeypatch):
    """API 응답의 elasticity[slider][level]은 길이 4의 list[float]여야 한다."""
    cache_path = tmp_path / "cache.json"
    corr_path = tmp_path / "corr.json"
    cache_path.write_text(
        '{"11440660_CS100001": {'
        '"baseline": [100.0, 110.0, 120.0, 130.0],'
        '"elasticity": {"vacancy_rate": {"+10": [-1.1, -1.2, -1.3, -1.4], "0": [0.0, 0.0, 0.0, 0.0]}}'
        "}}",
        encoding="utf-8",
    )
    corr_path.write_text('{"vacancy_rate→cpi_index": 0.42}', encoding="utf-8")
    monkeypatch.setenv("SENSITIVITY_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("SENSITIVITY_CORR_PATH", str(corr_path))

    # 모듈 재로드 (env var 반영)
    import importlib
    import src.api.sensitivity as sens_mod
    importlib.reload(sens_mod)

    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(sens_mod.router)
    client = TestClient(app)

    res = client.get("/predict/sensitivity?dong_code=11440660&industry_code=CS100001")
    assert res.status_code == 200, res.text
    body = res.json()
    assert isinstance(body["baseline_sales"], list) and len(body["baseline_sales"]) == 4
    val = body["elasticity"]["vacancy_rate"]["+10"]
    assert isinstance(val, list) and len(val) == 4
    assert val == [-1.1, -1.2, -1.3, -1.4]
```

- [ ] **Step 2: 테스트 FAIL 확인**

Run: `pytest tests/test_sensitivity.py::test_sensitivity_response_elasticity_is_quarterly_list -v`
Expected: FAIL — Pydantic validation 또는 schema 불일치 에러.

- [ ] **Step 3: SensitivityResponse 타입 변경**

`backend/src/api/sensitivity.py:65-68`:
```python
class SensitivityResponse(BaseModel):
    elasticity: dict[str, dict[str, list[float]]]
    correlations: dict[str, float]
    baseline_sales: list[float]
```

- [ ] **Step 4: 테스트 PASS 확인**

Run: `pytest tests/test_sensitivity.py -v`
Expected: 모든 백엔드 테스트 PASS.

- [ ] **Step 5: Commit**

```bash
ruff check --fix backend/src/api/sensitivity.py tests/test_sensitivity.py
ruff format backend/src/api/sensitivity.py tests/test_sensitivity.py
git add backend/src/api/sensitivity.py tests/test_sensitivity.py
git commit -m "feat(api/sensitivity): elasticity 응답을 분기별 list[float]로 확장"
```

---

### Task 7: ETag 회귀 검증

**Files:**
- Test: `tests/test_sensitivity.py`

- [ ] **Step 1: ETag 304 흐름이 schema 변경에도 깨지지 않는지 회귀 테스트**

`tests/test_sensitivity.py` 하단에 추가:
```python
def test_sensitivity_etag_returns_304_on_match(tmp_path, monkeypatch):
    cache_path = tmp_path / "cache.json"
    corr_path = tmp_path / "corr.json"
    cache_path.write_text(
        '{"k_v": {"baseline": [1.0, 1.0, 1.0, 1.0],'
        '"elasticity": {"vacancy_rate": {"0": [0.0, 0.0, 0.0, 0.0]}}}}',
        encoding="utf-8",
    )
    corr_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("SENSITIVITY_CACHE_PATH", str(cache_path))
    monkeypatch.setenv("SENSITIVITY_CORR_PATH", str(corr_path))

    import importlib
    import src.api.sensitivity as sens_mod
    importlib.reload(sens_mod)

    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(sens_mod.router)
    client = TestClient(app)

    first = client.get("/predict/sensitivity?dong_code=k&industry_code=v")
    etag = first.headers["etag"]
    second = client.get(
        "/predict/sensitivity?dong_code=k&industry_code=v",
        headers={"If-None-Match": etag},
    )
    assert second.status_code == 304
```

- [ ] **Step 2: 실행 + PASS 확인**

Run: `pytest tests/test_sensitivity.py::test_sensitivity_etag_returns_304_on_match -v`
Expected: PASS (ETag 로직은 schema와 무관).

- [ ] **Step 3: Commit**

```bash
git add tests/test_sensitivity.py
git commit -m "test(sensitivity): ETag 304 회귀 테스트 — schema 확장 후 동작 검증"
```

---

## Phase 3 — 프론트엔드 타입

### Task 8: types/elasticity.ts 갱신

**Files:**
- Modify: `frontend/src/types/elasticity.ts`

- [ ] **Step 1: 타입 정의 교체**

`frontend/src/types/elasticity.ts` 전체를 다음으로 교체:

```typescript
/**
 * Elasticity (TCN 시나리오 시뮬레이터 S3) 응답 타입.
 *
 * 백엔드 엔드포인트: GET /predict/sensitivity?dong_code=&industry_code=
 *
 * elasticity[feature][level] = 해당 피처를 level(%) 변동시켰을 때 분기별 매출 변화율(%) 4개 list.
 * 매출 식 (분기별): final[q] = baseline_sales[q] × (1 + Σ(elasticity[f][slider_pct][q]/100))
 * quarter_num은 categorical 슬라이더 (Q1~Q4 절댓값).
 *
 * level 키 형식: "-30", "-20", "-10", "0", "+10", "+20", "+30" (양수에 + prefix)
 * correlations 키 형식: "{from}→{to}"
 */

export interface ElasticityResponse {
  elasticity: {
    vacancy_rate: Record<string, number[]>;
    trend_score: Record<string, number[]>;
    cpi_index: Record<string, number[]>;
    opr_sale_mt_avg: Record<string, number[]>;
    quarter_num: Record<'Q1' | 'Q2' | 'Q3' | 'Q4', number[]>;
  };
  correlations: Record<string, number>;
  baseline_sales: number[];
}

export type ElasticityFeature =
  | 'vacancy_rate'
  | 'trend_score'
  | 'cpi_index'
  | 'opr_sale_mt_avg';
```

- [ ] **Step 2: TypeScript 컴파일 확인 — 깨지는 사용처 식별**

```bash
cd frontend && npx tsc --noEmit
```
Expected: `PredictScenarioSimTab.tsx`, `useElasticity.ts`, `ElasticitySlider`, `ScenarioComparisonChart` 등에서 다수 에러. 후속 Task에서 모두 수정.

- [ ] **Step 3: Commit (이 단계는 의도적으로 빨강 상태 — 후속 Task에서 차차 해소)**

```bash
cd frontend && npx prettier --write src/types/elasticity.ts
git add frontend/src/types/elasticity.ts
git commit -m "feat(types/elasticity): 분기별 list 응답 + 슬라이더 5개 재구성 타입 반영"
```

---

## Phase 4 — 프론트엔드 훅

### Task 9: useElasticity 단순화 (반환 타입은 ElasticityResponse 그대로)

**Files:**
- Modify: `frontend/src/hooks/useElasticity.ts`

- [ ] **Step 1: 현재 useElasticity 본문은 ElasticityResponse를 그대로 노출하므로 변경 최소**

useElasticity 자체는 응답 객체를 그대로 돌려주므로 코드 변경은 없음. 다만 docstring을 분기별 list 설명으로 갱신.

`frontend/src/hooks/useElasticity.ts:1-6` 헤더 주석을 다음으로 교체:
```typescript
/**
 * useElasticity — TCN 시나리오 탄성치 조회 훅 (단일 후보용, S3).
 *
 * 응답의 elasticity[feature][level] 은 분기별 4개 % 변화율 list.
 * dong_code 또는 industry_code 가 null 이면 호출 안 함.
 * AbortController 로 이전 요청 자동 cancel (dependency 변경 시).
 */
```

- [ ] **Step 2: tsc 통과 확인 (이 파일에 한해)**

```bash
cd frontend && npx tsc --noEmit src/hooks/useElasticity.ts 2>&1 | head -20
```
Expected: useElasticity 자체 에러 없음. 다른 파일 에러는 Task 12+에서 해소.

- [ ] **Step 3: Commit**

```bash
cd frontend && npx prettier --write src/hooks/useElasticity.ts
git add frontend/src/hooks/useElasticity.ts
git commit -m "docs(useElasticity): S3 분기별 list 응답 설명 반영"
```

---

### Task 10: useScenarioCandidates 신규 (후보 상태 격리)

**Files:**
- Create: `frontend/src/hooks/useScenarioCandidates.ts`
- Test: `frontend/src/hooks/__tests__/useScenarioCandidates.test.ts`

- [ ] **Step 1: 실패 테스트 작성**

`frontend/src/hooks/__tests__/useScenarioCandidates.test.ts`:
```typescript
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useScenarioCandidates } from '../useScenarioCandidates';

describe('useScenarioCandidates', () => {
  it('add then select candidate', () => {
    const { result } = renderHook(() => useScenarioCandidates());
    expect(result.current.candidates).toEqual([]);

    act(() => {
      result.current.addCandidate({ dong: '서교동', dongCode: '11440660', industryCode: 'CS100001' });
    });
    expect(result.current.candidates).toHaveLength(1);
    expect(result.current.selectedId).toBe(result.current.candidates[0].id);
  });

  it('rejects duplicate (same dong+industry)', () => {
    const { result } = renderHook(() => useScenarioCandidates());
    act(() => {
      result.current.addCandidate({ dong: '서교동', dongCode: '11440660', industryCode: 'CS100001' });
      result.current.addCandidate({ dong: '서교동', dongCode: '11440660', industryCode: 'CS100001' });
    });
    expect(result.current.candidates).toHaveLength(1);
  });

  it('caps at 5 candidates', () => {
    const { result } = renderHook(() => useScenarioCandidates());
    act(() => {
      for (let i = 0; i < 7; i++) {
        result.current.addCandidate({
          dong: `dong${i}`,
          dongCode: `1144066${i}`,
          industryCode: 'CS100001',
        });
      }
    });
    expect(result.current.candidates).toHaveLength(5);
  });

  it('updateSliderValues isolates per candidate', () => {
    const { result } = renderHook(() => useScenarioCandidates());
    act(() => {
      result.current.addCandidate({ dong: 'A', dongCode: '11440001', industryCode: 'CS100001' });
      result.current.addCandidate({ dong: 'B', dongCode: '11440002', industryCode: 'CS100001' });
    });
    const [a, b] = result.current.candidates;
    act(() => {
      result.current.updateSliderValues(a.id, { vacancy_rate: 10 });
    });
    expect(result.current.candidates.find((c) => c.id === a.id)?.sliderValues.vacancy_rate).toBe(10);
    expect(result.current.candidates.find((c) => c.id === b.id)?.sliderValues.vacancy_rate).toBe(0);
  });

  it('removeCandidate updates selection', () => {
    const { result } = renderHook(() => useScenarioCandidates());
    act(() => {
      result.current.addCandidate({ dong: 'A', dongCode: '11440001', industryCode: 'CS100001' });
      result.current.addCandidate({ dong: 'B', dongCode: '11440002', industryCode: 'CS100001' });
    });
    const removed = result.current.candidates[1].id;
    act(() => result.current.selectCandidate(removed));
    act(() => result.current.removeCandidate(removed));
    expect(result.current.candidates).toHaveLength(1);
    expect(result.current.selectedId).toBe(result.current.candidates[0].id);
  });
});
```

- [ ] **Step 2: 테스트 FAIL 확인**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useScenarioCandidates.test.ts`
Expected: FAIL — `useScenarioCandidates` 모듈 없음.

- [ ] **Step 3: 훅 구현**

`frontend/src/hooks/useScenarioCandidates.ts`:
```typescript
/**
 * useScenarioCandidates — Master-Detail 비교 UX 후보 상태 관리.
 *
 * - 최대 5개 (영업팀 비교용 + UI 가독성)
 * - 동×업종 중복 차단
 * - 후보별 슬라이더 값 격리 (동마다 다른 가정 동시 비교)
 * - 세션 메모리만 (persist X)
 */

import { useCallback, useState } from 'react';
import type { ElasticityFeature } from '../types/elasticity';

export interface ScenarioCandidate {
  id: string;
  dong: string;
  dongCode: string;
  industryCode: string;
  sliderValues: Record<ElasticityFeature, number>;
  quarter: 'Q1' | 'Q2' | 'Q3' | 'Q4';
}

const INITIAL_SLIDERS: Record<ElasticityFeature, number> = {
  vacancy_rate: 0,
  trend_score: 0,
  cpi_index: 0,
  opr_sale_mt_avg: 0,
};

const MAX_CANDIDATES = 5;

export interface AddCandidateInput {
  dong: string;
  dongCode: string;
  industryCode: string;
}

export function useScenarioCandidates() {
  const [candidates, setCandidates] = useState<ScenarioCandidate[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const addCandidate = useCallback((input: AddCandidateInput) => {
    setCandidates((prev) => {
      const dup = prev.find(
        (c) => c.dongCode === input.dongCode && c.industryCode === input.industryCode,
      );
      if (dup) {
        setSelectedId(dup.id);
        return prev;
      }
      if (prev.length >= MAX_CANDIDATES) return prev;
      const id = `${input.dongCode}_${input.industryCode}_${Date.now()}`;
      const next: ScenarioCandidate = {
        id,
        dong: input.dong,
        dongCode: input.dongCode,
        industryCode: input.industryCode,
        sliderValues: { ...INITIAL_SLIDERS },
        quarter: 'Q1',
      };
      setSelectedId(id);
      return [...prev, next];
    });
  }, []);

  const removeCandidate = useCallback((id: string) => {
    setCandidates((prev) => {
      const next = prev.filter((c) => c.id !== id);
      setSelectedId((curr) => {
        if (curr !== id) return curr;
        return next.length > 0 ? next[0].id : null;
      });
      return next;
    });
  }, []);

  const selectCandidate = useCallback((id: string) => setSelectedId(id), []);

  const updateSliderValues = useCallback(
    (id: string, patch: Partial<Record<ElasticityFeature, number>>) => {
      setCandidates((prev) =>
        prev.map((c) =>
          c.id === id ? { ...c, sliderValues: { ...c.sliderValues, ...patch } } : c,
        ),
      );
    },
    [],
  );

  const setQuarter = useCallback((id: string, q: 'Q1' | 'Q2' | 'Q3' | 'Q4') => {
    setCandidates((prev) => prev.map((c) => (c.id === id ? { ...c, quarter: q } : c)));
  }, []);

  return {
    candidates,
    selectedId,
    addCandidate,
    removeCandidate,
    selectCandidate,
    updateSliderValues,
    setQuarter,
  };
}
```

- [ ] **Step 4: 테스트 PASS 확인**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useScenarioCandidates.test.ts`
Expected: 5/5 PASS.

- [ ] **Step 5: Commit**

```bash
cd frontend && npx prettier --write src/hooks/useScenarioCandidates.ts src/hooks/__tests__/useScenarioCandidates.test.ts
git add frontend/src/hooks/useScenarioCandidates.ts frontend/src/hooks/__tests__/useScenarioCandidates.test.ts
git commit -m "feat(hooks/useScenarioCandidates): Master-Detail 후보 상태 관리 훅 + 테스트"
```

---

### Task 11: useElasticityComparison 신규 (N개 병렬 fetch)

**Files:**
- Create: `frontend/src/hooks/useElasticityComparison.ts`

- [ ] **Step 1: 훅 구현 (단순 wrapper — 후보 N개에 대해 useElasticity 결과를 병렬 보관)**

`frontend/src/hooks/useElasticityComparison.ts`:
```typescript
/**
 * useElasticityComparison — N개 후보의 elasticity 응답을 병렬 fetch + ETag 캐시 활용.
 *
 * 각 후보(dongCode×industryCode)마다 독립 AbortController 사용.
 * 동일한 (dong, industry) 조합에 대한 중복 fetch는 useScenarioCandidates 단계에서
 * 차단되므로 여기서는 단순 N→N 매핑.
 */

import { useEffect, useState } from 'react';
import axios from 'axios';
import { fetchElasticity, ElasticityNotFoundError } from '../api/elasticity';
import type { ElasticityResponse } from '../types/elasticity';

interface CandidateKey {
  id: string;
  dongCode: string;
  industryCode: string;
}

export interface ElasticityState {
  data: ElasticityResponse | null;
  error: Error | null;
  loading: boolean;
}

export function useElasticityComparison(
  candidates: CandidateKey[],
): Record<string, ElasticityState> {
  const [byId, setById] = useState<Record<string, ElasticityState>>({});

  useEffect(() => {
    const controllers = new Map<string, AbortController>();
    const activeIds = new Set(candidates.map((c) => c.id));

    setById((prev) => {
      const next: Record<string, ElasticityState> = {};
      for (const c of candidates) {
        next[c.id] = prev[c.id] ?? { data: null, error: null, loading: true };
      }
      return next;
    });

    for (const c of candidates) {
      const controller = new AbortController();
      controllers.set(c.id, controller);
      fetchElasticity(c.dongCode, c.industryCode, controller.signal)
        .then((res) => {
          if (controller.signal.aborted) return;
          setById((prev) => ({ ...prev, [c.id]: { data: res, error: null, loading: false } }));
        })
        .catch((err) => {
          if (axios.isCancel(err) || controller.signal.aborted) return;
          const wrapped =
            err instanceof ElasticityNotFoundError
              ? err
              : err instanceof Error
                ? err
                : new Error('elasticity 조회 실패');
          setById((prev) => ({ ...prev, [c.id]: { data: null, error: wrapped, loading: false } }));
        });
    }

    return () => {
      for (const [id, ctrl] of controllers) {
        if (!activeIds.has(id)) ctrl.abort();
        else ctrl.abort();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidates.map((c) => c.id).join(',')]);

  return byId;
}
```

- [ ] **Step 2: tsc 통과 확인**

```bash
cd frontend && npx tsc --noEmit
```
Expected: useElasticityComparison 자체에는 에러 없음.

- [ ] **Step 3: Commit**

```bash
cd frontend && npx prettier --write src/hooks/useElasticityComparison.ts
git add frontend/src/hooks/useElasticityComparison.ts
git commit -m "feat(hooks/useElasticityComparison): N개 후보 병렬 elasticity fetch 훅"
```

---

## Phase 5 — 프론트엔드 컴포넌트

### Task 12: ScenarioCandidateCard (좌측 카드)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/sub/predict/scenario/ScenarioCandidateCard.tsx`
- Test: `frontend/src/components/SimulationResult/dashboard/sub/predict/scenario/__tests__/ScenarioCandidateCard.test.tsx`

- [ ] **Step 1: 실패 테스트 작성**

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ScenarioCandidateCard } from '../ScenarioCandidateCard';

describe('ScenarioCandidateCard', () => {
  const baseProps = {
    id: 'a',
    dong: '서교동',
    industryLabel: '카페',
    selected: false,
    quarterly: [100, 110, 120, 130],
    totalDeltaPct: 5.2,
    onSelect: vi.fn(),
    onRemove: vi.fn(),
  };

  it('renders dong + industry + delta badge', () => {
    render(<ScenarioCandidateCard {...baseProps} />);
    expect(screen.getByText('서교동')).toBeTruthy();
    expect(screen.getByText('카페')).toBeTruthy();
    expect(screen.getByText(/\+5\.2%/)).toBeTruthy();
  });

  it('select button triggers onSelect', () => {
    const onSelect = vi.fn();
    render(<ScenarioCandidateCard {...baseProps} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole('button', { name: /선택|서교동/ }));
    expect(onSelect).toHaveBeenCalledWith('a');
  });

  it('remove button triggers onRemove', () => {
    const onRemove = vi.fn();
    render(<ScenarioCandidateCard {...baseProps} onRemove={onRemove} />);
    fireEvent.click(screen.getByLabelText('후보 삭제'));
    expect(onRemove).toHaveBeenCalledWith('a');
  });
});
```

- [ ] **Step 2: 테스트 FAIL 확인**

Run: `cd frontend && npx vitest run src/components/SimulationResult/dashboard/sub/predict/scenario/__tests__/ScenarioCandidateCard.test.tsx`
Expected: FAIL.

- [ ] **Step 3: 컴포넌트 구현**

`ScenarioCandidateCard.tsx`:
```typescript
/**
 * ScenarioCandidateCard — Master 패널의 단일 후보 카드.
 *
 * - mini sparkline (Q1~Q4)
 * - 합계 % 변화 뱃지 (양수=success, 음수=danger)
 * - 선택 표시 + 삭제 버튼
 */

import { X } from 'lucide-react';

interface Props {
  id: string;
  dong: string;
  industryLabel: string;
  selected: boolean;
  quarterly: number[]; // 4개
  totalDeltaPct: number;
  onSelect: (id: string) => void;
  onRemove: (id: string) => void;
}

export function ScenarioCandidateCard({
  id,
  dong,
  industryLabel,
  selected,
  quarterly,
  totalDeltaPct,
  onSelect,
  onRemove,
}: Props) {
  const tone =
    totalDeltaPct > 0 ? 'text-success' : totalDeltaPct < 0 ? 'text-danger' : 'text-muted-foreground';
  const sign = totalDeltaPct >= 0 ? '+' : '';

  return (
    <div
      className={`relative rounded-2xl border bg-card p-3 transition-colors ${
        selected ? 'border-primary ring-2 ring-primary' : 'border-border hover:bg-secondary'
      }`}
    >
      <button
        type="button"
        onClick={() => onSelect(id)}
        className="block w-full text-left"
        aria-label={`${dong} 후보 선택`}
      >
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-black text-foreground">{dong}</span>
          <span className={`text-xs font-black tabular-nums ${tone}`}>
            {sign}
            {totalDeltaPct.toFixed(1)}%
          </span>
        </div>
        <div className="text-[0.625rem] font-bold text-muted-foreground mb-2">{industryLabel}</div>
        <Sparkline values={quarterly} />
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onRemove(id);
        }}
        aria-label="후보 삭제"
        className="absolute top-2 right-2 rounded p-0.5 text-muted-foreground hover:bg-secondary hover:text-foreground"
      >
        <X size={14} />
      </button>
    </div>
  );
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length === 0) return null;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const w = 80;
  const h = 24;
  const step = w / (values.length - 1 || 1);
  const points = values
    .map((v, i) => `${i * step},${h - ((v - min) / range) * h}`)
    .join(' ');
  return (
    <svg width={w} height={h} aria-hidden="true">
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        className="text-primary"
      />
    </svg>
  );
}
```

- [ ] **Step 4: 테스트 PASS 확인**

Run: `cd frontend && npx vitest run src/components/SimulationResult/dashboard/sub/predict/scenario/__tests__/ScenarioCandidateCard.test.tsx`
Expected: 3/3 PASS.

- [ ] **Step 5: Commit**

```bash
cd frontend && npx prettier --write 'src/components/SimulationResult/dashboard/sub/predict/scenario/**/*.{ts,tsx}'
git add frontend/src/components/SimulationResult/dashboard/sub/predict/scenario/
git commit -m "feat(scenario): 후보 카드 컴포넌트 + 테스트"
```

---

### Task 13: ScenarioCandidateList (좌측 패널)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/sub/predict/scenario/ScenarioCandidateList.tsx`

- [ ] **Step 1: 컴포넌트 구현**

`ScenarioCandidateList.tsx`:
```typescript
/**
 * ScenarioCandidateList — Master 패널 본체.
 *
 * - 후보 카드 목록 (최대 5개)
 * - "+ 후보 추가" 버튼 (현재 dong/industry 컨텍스트로 추가 요청)
 * - 0개일 때 안내
 */

import { Plus } from 'lucide-react';
import { ScenarioCandidateCard } from './ScenarioCandidateCard';
import type { ScenarioCandidate } from '../../../../../../hooks/useScenarioCandidates';

interface CandidateView {
  candidate: ScenarioCandidate;
  industryLabel: string;
  quarterly: number[];
  totalDeltaPct: number;
}

interface Props {
  views: CandidateView[];
  selectedId: string | null;
  canAdd: boolean;
  onSelect: (id: string) => void;
  onRemove: (id: string) => void;
  onAdd: () => void;
}

export function ScenarioCandidateList({
  views,
  selectedId,
  canAdd,
  onSelect,
  onRemove,
  onAdd,
}: Props) {
  return (
    <div className="rounded-3xl border border-border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-[0.6875rem] font-black uppercase tracking-widest text-muted-foreground">
          비교 후보 ({views.length}/5)
        </h4>
        <button
          type="button"
          onClick={onAdd}
          disabled={!canAdd}
          className="inline-flex items-center gap-1 rounded-lg border border-border bg-secondary px-2 py-1 text-[0.625rem] font-bold text-foreground transition-colors hover:bg-card disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Plus size={12} /> 추가
        </button>
      </div>
      {views.length === 0 ? (
        <p className="rounded-2xl bg-secondary p-6 text-center text-[0.6875rem] text-muted-foreground">
          상단에서 동·업종을 선택하고 "추가" 버튼으로 후보를 등록하세요.
        </p>
      ) : (
        <div className="space-y-2">
          {views.map((v) => (
            <ScenarioCandidateCard
              key={v.candidate.id}
              id={v.candidate.id}
              dong={v.candidate.dong}
              industryLabel={v.industryLabel}
              selected={selectedId === v.candidate.id}
              quarterly={v.quarterly}
              totalDeltaPct={v.totalDeltaPct}
              onSelect={onSelect}
              onRemove={onRemove}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: tsc 통과 확인**

Run: `cd frontend && npx tsc --noEmit src/components/SimulationResult/dashboard/sub/predict/scenario/ScenarioCandidateList.tsx`
Expected: 이 파일 자체 에러 없음.

- [ ] **Step 3: Commit**

```bash
cd frontend && npx prettier --write src/components/SimulationResult/dashboard/sub/predict/scenario/ScenarioCandidateList.tsx
git add frontend/src/components/SimulationResult/dashboard/sub/predict/scenario/ScenarioCandidateList.tsx
git commit -m "feat(scenario): 좌측 후보 리스트 컴포넌트"
```

---

### Task 14: ScenarioForecastChart (분기별 비틀린 곡선)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/sub/predict/scenario/ScenarioForecastChart.tsx`
- Test: `frontend/src/components/.../scenario/__tests__/ScenarioForecastChart.test.tsx`

- [ ] **Step 1: 실패 테스트**

```typescript
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { ScenarioForecastChart } from '../ScenarioForecastChart';

describe('ScenarioForecastChart', () => {
  it('renders 4 quarter points (twisted, not parallel)', () => {
    const baseline = [100, 110, 120, 130];
    const adjusted = [95, 110, 130, 145]; // 분기별 다른 변화율
    const { container } = render(
      <ScenarioForecastChart baseline={baseline} adjusted={adjusted} />,
    );
    // recharts dots: 베이스라인 4 + 시나리오 4 = 8
    const dots = container.querySelectorAll('.recharts-dot');
    expect(dots.length).toBeGreaterThanOrEqual(4);
  });
});
```

- [ ] **Step 2: 테스트 FAIL 확인**

Run: `cd frontend && npx vitest run src/components/SimulationResult/dashboard/sub/predict/scenario/__tests__/ScenarioForecastChart.test.tsx`
Expected: FAIL.

- [ ] **Step 3: 컴포넌트 구현 (Recharts LineChart, X축 "N분기 후")**

`ScenarioForecastChart.tsx`:
```typescript
/**
 * ScenarioForecastChart — 분기별 비틀린 곡선 차트.
 *
 * baseline 4개 + adjusted 4개를 X축 "1분기 후"~"4분기 후"로 그린다.
 * 슬라이더의 분기별 % 변화율이 다르므로 곡선 모양 자체가 변한다 (단순 평행이동 X).
 */

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface Props {
  baseline: number[]; // 길이 4
  adjusted: number[]; // 길이 4
}

const X_LABELS = ['1분기 후', '2분기 후', '3분기 후', '4분기 후'];

export function ScenarioForecastChart({ baseline, adjusted }: Props) {
  const data = X_LABELS.map((label, i) => ({
    label,
    baseline: baseline[i] ?? 0,
    adjusted: adjusted[i] ?? 0,
  }));

  return (
    <div style={{ width: '100%', height: 280 }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 10, right: 16, bottom: 10, left: 16 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => formatKrw(v)}
            width={64}
          />
          <Tooltip
            formatter={(v: number) => `₩${formatKrw(v)}`}
            labelStyle={{ fontWeight: 700 }}
          />
          <Line
            type="monotone"
            dataKey="baseline"
            stroke="#94a3b8"
            strokeWidth={2}
            dot
            name="기준선"
          />
          <Line
            type="monotone"
            dataKey="adjusted"
            stroke="#ec4899"
            strokeWidth={2.5}
            dot
            name="시나리오"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function formatKrw(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}억`;
  if (abs >= 10_000) return `${Math.round(value / 10_000).toLocaleString('ko-KR')}만`;
  return `${Math.round(value).toLocaleString('ko-KR')}`;
}
```

- [ ] **Step 4: 테스트 PASS 확인**

Run: `cd frontend && npx vitest run src/components/SimulationResult/dashboard/sub/predict/scenario/__tests__/ScenarioForecastChart.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd frontend && npx prettier --write 'src/components/SimulationResult/dashboard/sub/predict/scenario/ScenarioForecastChart.tsx' 'src/components/SimulationResult/dashboard/sub/predict/scenario/__tests__/ScenarioForecastChart.test.tsx'
git add frontend/src/components/SimulationResult/dashboard/sub/predict/scenario/ScenarioForecastChart.tsx frontend/src/components/SimulationResult/dashboard/sub/predict/scenario/__tests__/ScenarioForecastChart.test.tsx
git commit -m "feat(scenario): 분기별 비틀린 곡선 차트 + 테스트"
```

---

### Task 15: ScenarioDetailPanel (우측 드릴다운)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/sub/predict/scenario/ScenarioDetailPanel.tsx`

- [ ] **Step 1: 컴포넌트 구현 (슬라이더 5개 + 차트 + 인사이트 카드)**

`ScenarioDetailPanel.tsx`:
```typescript
/**
 * ScenarioDetailPanel — 선택된 후보의 우측 드릴다운 패널.
 *
 * - 슬라이더 5개 (vacancy_rate / trend_score / cpi_index / opr_sale_mt_avg / quarter_num)
 * - 분기별 비틀린 곡선 (ScenarioForecastChart)
 * - 합산 안내 문구 (선형 합 가정)
 * - 슬라이더 옆 ⓘ 툴팁 (상관 변수)
 */

import { Info, RotateCcw } from 'lucide-react';
import type {
  ElasticityFeature,
  ElasticityResponse,
} from '../../../../../../types/elasticity';
import { ElasticitySlider } from '../../../charts/ElasticitySlider';
import { ScenarioForecastChart } from './ScenarioForecastChart';

const SLIDERS: { key: ElasticityFeature; label: string }[] = [
  { key: 'vacancy_rate', label: '공실률' },
  { key: 'trend_score', label: '검색 트렌드' },
  { key: 'cpi_index', label: '물가지수' },
  { key: 'opr_sale_mt_avg', label: '상권 활성도' },
];

interface Props {
  data: ElasticityResponse | null;
  loading: boolean;
  error: Error | null;
  sliderValues: Record<ElasticityFeature, number>;
  quarter: 'Q1' | 'Q2' | 'Q3' | 'Q4';
  onSliderChange: (feature: ElasticityFeature, value: number) => void;
  onQuarterChange: (q: 'Q1' | 'Q2' | 'Q3' | 'Q4') => void;
  onReset: () => void;
}

const elasticityKey = (v: number): string => (v > 0 ? `+${v}` : String(v));

export function ScenarioDetailPanel({
  data,
  loading,
  error,
  sliderValues,
  quarter,
  onSliderChange,
  onQuarterChange,
  onReset,
}: Props) {
  if (loading) return <SkeletonState />;
  if (error || !data) {
    return (
      <div className="rounded-3xl border border-dashed border-border bg-secondary p-12 text-center text-xs text-muted-foreground">
        {error ? '데이터 불러오기 실패' : '후보를 선택하세요'}
      </div>
    );
  }

  // 분기별 시나리오 계산: final[q] = baseline[q] × (1 + Σ slider_elasticity[q] / 100)
  const quarters = [0, 1, 2, 3] as const;
  const adjusted = quarters.map((q) => {
    let pct = 0;
    for (const { key } of SLIDERS) {
      const v = sliderValues[key];
      const arr =
        data.elasticity[key]?.[elasticityKey(v)] ?? data.elasticity[key]?.[String(v)] ?? null;
      if (arr && arr.length === 4) pct += arr[q] / 100;
    }
    const qPct = data.elasticity.quarter_num?.[quarter];
    if (qPct && qPct.length === 4) pct += qPct[q] / 100;
    return data.baseline_sales[q] * (1 + pct);
  });

  const totalDelta =
    adjusted.reduce((s, v) => s + v, 0) - data.baseline_sales.reduce((s, v) => s + v, 0);
  const totalDeltaPct = (totalDelta / data.baseline_sales.reduce((s, v) => s + v, 0)) * 100;

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-dashed border-primary/40 bg-primary/5 p-3 text-[0.6875rem] text-foreground">
        ※ 각 슬라이더는 다른 조건이 동일하다는 가정 하의 단일 변수 시뮬레이션입니다 (민감도 분석).
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="lg:col-span-5 space-y-3">
          <div className="rounded-3xl border border-border bg-card p-6 space-y-3">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-[0.6875rem] font-black uppercase tracking-widest text-muted-foreground">
                What-if 변수 조정
              </h4>
              <button
                type="button"
                onClick={onReset}
                className="inline-flex items-center gap-1 text-[0.625rem] font-bold text-muted-foreground hover:text-foreground"
              >
                <RotateCcw size={12} /> 리셋
              </button>
            </div>
            {SLIDERS.map(({ key, label }) => (
              <SliderRow
                key={key}
                feature={key}
                label={label}
                value={sliderValues[key]}
                elasticity={data.elasticity[key] ?? {}}
                correlations={data.correlations}
                onChange={(v) => onSliderChange(key, v)}
              />
            ))}
            <QuarterSelect quarter={quarter} onChange={onQuarterChange} />
          </div>
        </div>

        <div className="lg:col-span-7 space-y-4">
          <div className="rounded-3xl border border-border bg-card p-6">
            <div className="flex items-baseline justify-between mb-2">
              <h4 className="text-[0.6875rem] font-black uppercase tracking-widest text-muted-foreground">
                4분기 매출 시뮬 — 분기별 비틀림
              </h4>
              <span
                className={`text-sm font-black tabular-nums ${
                  totalDeltaPct > 0
                    ? 'text-success'
                    : totalDeltaPct < 0
                      ? 'text-danger'
                      : 'text-muted-foreground'
                }`}
              >
                {totalDeltaPct >= 0 ? '+' : ''}
                {totalDeltaPct.toFixed(1)}%
              </span>
            </div>
            <ScenarioForecastChart baseline={data.baseline_sales} adjusted={adjusted} />
          </div>
        </div>
      </div>
    </div>
  );
}

function SliderRow({
  feature,
  label,
  value,
  elasticity,
  correlations,
  onChange,
}: {
  feature: ElasticityFeature;
  label: string;
  value: number;
  elasticity: Record<string, number[]>;
  correlations: Record<string, number>;
  onChange: (v: number) => void;
}) {
  // 분기별 list → 평균 % 표시용 (slider 컴포넌트는 단일 % 기대)
  const elasticityAvg: Record<string, number> = {};
  for (const [level, arr] of Object.entries(elasticity)) {
    if (Array.isArray(arr) && arr.length > 0) {
      elasticityAvg[level] = arr.reduce((s, v) => s + v, 0) / arr.length;
    }
  }

  // 상관 변수 추출 (|r| ≥ 0.5)
  const peers = extractPeers(feature, correlations).filter((p) => Math.abs(p.r) >= 0.5);
  const tooltipText = peers
    .map((p) => `${labelFor(p.peer)} 상관 r=${p.r >= 0 ? '+' : ''}${p.r.toFixed(2)}`)
    .join(' · ');

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1">
        <ElasticitySlider
          feature={feature}
          label={label}
          value={value}
          onChange={onChange}
          elasticity={elasticityAvg}
          peerCorrelations={peers}
        />
        {tooltipText && (
          <span title={tooltipText} className="text-muted-foreground" aria-label={tooltipText}>
            <Info size={12} />
          </span>
        )}
      </div>
    </div>
  );
}

function QuarterSelect({
  quarter,
  onChange,
}: {
  quarter: 'Q1' | 'Q2' | 'Q3' | 'Q4';
  onChange: (q: 'Q1' | 'Q2' | 'Q3' | 'Q4') => void;
}) {
  const opts: ('Q1' | 'Q2' | 'Q3' | 'Q4')[] = ['Q1', 'Q2', 'Q3', 'Q4'];
  return (
    <label className="flex items-center justify-between gap-2 rounded-lg border border-border bg-secondary px-3 py-2 text-xs font-bold">
      <span className="text-muted-foreground">분기 (계절성)</span>
      <select
        value={quarter}
        onChange={(e) => onChange(e.target.value as 'Q1' | 'Q2' | 'Q3' | 'Q4')}
        className="bg-transparent text-foreground font-bold focus:outline-none"
        aria-label="분기 선택"
      >
        {opts.map((q) => (
          <option key={q} value={q}>
            {q}
          </option>
        ))}
      </select>
    </label>
  );
}

interface PeerCorrelation {
  peer: ElasticityFeature;
  r: number;
}

function extractPeers(
  feature: ElasticityFeature,
  correlations: Record<string, number>,
): PeerCorrelation[] {
  const peers: PeerCorrelation[] = [];
  const known = new Set<ElasticityFeature>([
    'vacancy_rate',
    'trend_score',
    'cpi_index',
    'opr_sale_mt_avg',
  ]);
  for (const [key, r] of Object.entries(correlations)) {
    const [a, b] = key.split('→');
    if (!a || !b) continue;
    if (a === feature && known.has(b as ElasticityFeature)) {
      peers.push({ peer: b as ElasticityFeature, r });
    } else if (b === feature && known.has(a as ElasticityFeature)) {
      peers.push({ peer: a as ElasticityFeature, r });
    }
  }
  return peers;
}

function labelFor(f: ElasticityFeature): string {
  switch (f) {
    case 'vacancy_rate':
      return '공실률';
    case 'trend_score':
      return '검색 트렌드';
    case 'cpi_index':
      return '물가지수';
    case 'opr_sale_mt_avg':
      return '상권 활성도';
  }
}

function SkeletonState() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
      <div className="lg:col-span-5 rounded-3xl border border-border bg-card p-6 space-y-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-16 rounded-2xl bg-secondary animate-pulse" aria-hidden="true" />
        ))}
      </div>
      <div className="lg:col-span-7">
        <div className="h-72 rounded-3xl bg-secondary animate-pulse" aria-hidden="true" />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: tsc 통과 확인**

```bash
cd frontend && npx tsc --noEmit
```
Expected: 새 파일들에서 에러 없음. 잔존 에러는 PredictScenarioSimTab.tsx(다음 Task에서 수정).

- [ ] **Step 3: Commit**

```bash
cd frontend && npx prettier --write src/components/SimulationResult/dashboard/sub/predict/scenario/ScenarioDetailPanel.tsx
git add frontend/src/components/SimulationResult/dashboard/sub/predict/scenario/ScenarioDetailPanel.tsx
git commit -m "feat(scenario): 우측 드릴다운 Detail 패널 (슬라이더 5개+비틀림 차트)"
```

---

### Task 16: PredictScenarioSimTab Master-Detail 컨테이너 재구성

**Files:**
- Modify: `frontend/src/components/SimulationResult/dashboard/sub/predict/PredictScenarioSimTab.tsx`

- [ ] **Step 1: PredictScenarioSimTab 전체를 Master-Detail 컨테이너로 교체**

`PredictScenarioSimTab.tsx` 전체를 다음으로 교체:
```typescript
/**
 * PredictScenarioSimTab — TCN 시나리오 시뮬레이터 (S3, Master-Detail).
 *
 * 좌측: 후보 카드 리스트 (최대 5개). 우측: 선택된 후보의 슬라이더+비틀림 차트.
 * 매출 식: final[q] = baseline[q] × (1 + Σ elasticity[f][slider_pct][q] / 100)
 *   (분기별 list 기반, 단순 평행이동이 아닌 비틀린 곡선)
 *
 * dong_code: 사용자가 dropdown 으로 직접 선택. industry_code: store.params.business_type 매핑.
 * "+추가" 버튼이 현재 dong+industry 조합을 후보로 등록한다.
 */

import { useEffect, useMemo, useState } from 'react';
import { Sliders } from 'lucide-react';
import type { SimulationOutput } from '../../../../../types';
import type { ElasticityFeature } from '../../../../../types/elasticity';
import { useElasticityComparison } from '../../../../../hooks/useElasticityComparison';
import {
  useScenarioCandidates,
  type ScenarioCandidate,
} from '../../../../../hooks/useScenarioCandidates';
import { ElasticityNotFoundError } from '../../../../../api/elasticity';
import { resolveBizToIndustry } from '../../../../../constants/bizToIndustry';
import { MAPO_DONGS, resolveDongCode } from '../../../../../constants/mapoDongs';
import { useSimulationStore } from '../../../../../stores/simulationStore';
import { useToastStore } from '../../../../../stores/toastStore';
import { ScenarioCandidateList } from './scenario/ScenarioCandidateList';
import { ScenarioDetailPanel } from './scenario/ScenarioDetailPanel';
import { CorrelationInsightCard } from './scenario/CorrelationInsightCard';

interface Props {
  simResult?: SimulationOutput | null;
}

const elasticityKey = (v: number): string => (v > 0 ? `+${v}` : String(v));

export function PredictScenarioSimTab({ simResult }: Props) {
  const winnerDistrict = simResult?.winner_district ?? null;
  const initialDong =
    winnerDistrict && MAPO_DONGS.some((d) => d.name === winnerDistrict)
      ? winnerDistrict
      : MAPO_DONGS[0].name;
  const [selectedDong, setSelectedDong] = useState<string>(initialDong);
  const dongCode = resolveDongCode(selectedDong);

  const businessType = useSimulationStore((s) => s.params?.business_type ?? null);
  const industryCode = resolveBizToIndustry(businessType);

  const cands = useScenarioCandidates();
  const elasticityById = useElasticityComparison(
    cands.candidates.map((c) => ({
      id: c.id,
      dongCode: c.dongCode,
      industryCode: c.industryCode,
    })),
  );

  // 토스트 (404/일반 에러)
  const pushToast = useToastStore((s) => s.push);
  useEffect(() => {
    for (const id of Object.keys(elasticityById)) {
      const err = elasticityById[id]?.error;
      if (err instanceof ElasticityNotFoundError) {
        pushToast({ variant: 'error', title: '일시 오류, 다른 동 시도해주세요' });
      } else if (err) {
        pushToast({
          variant: 'error',
          title: '데이터 로드 실패',
          description: '잠시 후 다시 시도하세요.',
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Object.values(elasticityById).map((s) => s.error?.message ?? '').join('|')]);

  // 카드 합계 % 변화 / sparkline 데이터
  const cardViews = useMemo(() => {
    return cands.candidates.map((c) => {
      const state = elasticityById[c.id];
      const data = state?.data;
      if (!data) {
        return {
          candidate: c,
          industryLabel: industryCode ?? c.industryCode,
          quarterly: [0, 0, 0, 0],
          totalDeltaPct: 0,
        };
      }
      const adjusted = computeAdjusted(c, data);
      const baseTotal = data.baseline_sales.reduce((s, v) => s + v, 0);
      const adjTotal = adjusted.reduce((s, v) => s + v, 0);
      const pct = baseTotal > 0 ? ((adjTotal - baseTotal) / baseTotal) * 100 : 0;
      return {
        candidate: c,
        industryLabel: industryCode ?? c.industryCode,
        quarterly: adjusted,
        totalDeltaPct: pct,
      };
    });
  }, [cands.candidates, elasticityById, industryCode]);

  const selected = cands.candidates.find((c) => c.id === cands.selectedId) ?? null;
  const selectedState = selected ? elasticityById[selected.id] : null;

  const businessMissing = !industryCode;
  const canAdd =
    !businessMissing &&
    cands.candidates.length < 5 &&
    !!dongCode &&
    !cands.candidates.some(
      (c) => c.dongCode === dongCode && c.industryCode === industryCode,
    );

  const handleAdd = () => {
    if (!dongCode || !industryCode) return;
    cands.addCandidate({ dong: selectedDong, dongCode, industryCode });
  };

  return (
    <div className="space-y-6">
      <Header
        selectedDong={selectedDong}
        onSelectDong={setSelectedDong}
        onAdd={handleAdd}
        canAdd={canAdd}
      />

      {businessMissing && (
        <div className="rounded-3xl border border-dashed border-border bg-secondary p-8 text-center">
          <Sliders size={32} className="mx-auto mb-3 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm font-bold text-foreground">업종 정보 필요</p>
          <p className="mt-2 text-[0.6875rem] text-muted-foreground">
            시뮬레이션 인풋(업종)을 먼저 입력해주세요.
          </p>
        </div>
      )}

      {!businessMissing && (
        <>
          {selectedState?.data && (
            <CorrelationInsightCard correlations={selectedState.data.correlations} />
          )}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="lg:col-span-3">
              <ScenarioCandidateList
                views={cardViews}
                selectedId={cands.selectedId}
                canAdd={canAdd}
                onSelect={cands.selectCandidate}
                onRemove={cands.removeCandidate}
                onAdd={handleAdd}
              />
            </div>
            <div className="lg:col-span-9">
              <ScenarioDetailPanel
                data={selectedState?.data ?? null}
                loading={selectedState?.loading ?? false}
                error={selectedState?.error ?? null}
                sliderValues={
                  selected?.sliderValues ?? {
                    vacancy_rate: 0,
                    trend_score: 0,
                    cpi_index: 0,
                    opr_sale_mt_avg: 0,
                  }
                }
                quarter={selected?.quarter ?? 'Q1'}
                onSliderChange={(f, v) => {
                  if (!selected) return;
                  cands.updateSliderValues(selected.id, { [f]: v });
                }}
                onQuarterChange={(q) => {
                  if (!selected) return;
                  cands.setQuarter(selected.id, q);
                }}
                onReset={() => {
                  if (!selected) return;
                  cands.updateSliderValues(selected.id, {
                    vacancy_rate: 0,
                    trend_score: 0,
                    cpi_index: 0,
                    opr_sale_mt_avg: 0,
                  });
                }}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function computeAdjusted(
  c: ScenarioCandidate,
  data: { elasticity: Record<string, Record<string, number[]>>; baseline_sales: number[] },
): number[] {
  const features: ElasticityFeature[] = [
    'vacancy_rate',
    'trend_score',
    'cpi_index',
    'opr_sale_mt_avg',
  ];
  return [0, 1, 2, 3].map((q) => {
    let pct = 0;
    for (const f of features) {
      const v = c.sliderValues[f];
      const arr = data.elasticity[f]?.[elasticityKey(v)] ?? data.elasticity[f]?.[String(v)];
      if (arr && arr.length === 4) pct += arr[q] / 100;
    }
    const qArr = data.elasticity.quarter_num?.[c.quarter];
    if (qArr && qArr.length === 4) pct += qArr[q] / 100;
    return data.baseline_sales[q] * (1 + pct);
  });
}

function Header({
  selectedDong,
  onSelectDong,
  onAdd,
  canAdd,
}: {
  selectedDong: string;
  onSelectDong: (next: string) => void;
  onAdd: () => void;
  canAdd: boolean;
}) {
  return (
    <header>
      <div className="flex flex-wrap items-start gap-4">
        <div>
          <h3 className="flex items-center gap-3 text-2xl font-black italic text-foreground">
            <Sliders className="text-primary" /> 시나리오 시뮬레이터
          </h3>
          <p className="text-xs text-muted-foreground mt-2">
            What-if 분석 — 슬라이더로 변수 조정해 분기별 매출 비틀림 시뮬 (최대 5개 비교)
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs font-bold transition-colors focus-within:ring-2 focus-within:ring-primary focus-within:ring-offset-1">
            <span className="text-muted-foreground">행정동</span>
            <select
              value={selectedDong}
              onChange={(e) => onSelectDong(e.target.value)}
              className="bg-transparent text-foreground font-bold focus:outline-none"
              aria-label="행정동 선택"
            >
              {MAPO_DONGS.map((d) => (
                <option key={d.code} value={d.name}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={onAdd}
            disabled={!canAdd}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs font-bold text-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-40"
          >
            + 후보 추가
          </button>
        </div>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: tsc — CorrelationInsightCard import 에러 확인 (다음 Task에서 생성)**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -i CorrelationInsight
```
Expected: "Cannot find module './scenario/CorrelationInsightCard'" — Task 17에서 해소.

- [ ] **Step 3: Commit (의도된 미완 — 다음 Task가 메우는 구조)**

```bash
git add frontend/src/components/SimulationResult/dashboard/sub/predict/PredictScenarioSimTab.tsx
git commit -m "feat(scenario): PredictScenarioSimTab Master-Detail 컨테이너 재구성"
```

---

### Task 17: CorrelationInsightCard (상관관계 정보 박스)

**Files:**
- Create: `frontend/src/components/SimulationResult/dashboard/sub/predict/scenario/CorrelationInsightCard.tsx`

- [ ] **Step 1: 컴포넌트 구현**

`CorrelationInsightCard.tsx`:
```typescript
/**
 * CorrelationInsightCard — 시뮬레이터 상단 데이터 인사이트 박스.
 *
 * 학습 데이터의 슬라이더 피처 간 상관계수를 표로 노출한다.
 * 자동 연동(슬라이더 1개 움직이면 다른 것도 자동 조정)은 채택하지 않음.
 */

import { BarChart3 } from 'lucide-react';

interface Props {
  correlations: Record<string, number>;
}

const FEATURE_LABELS: Record<string, string> = {
  vacancy_rate: '공실률',
  trend_score: '검색 트렌드',
  cpi_index: '물가지수',
  opr_sale_mt_avg: '상권 활성도',
};

export function CorrelationInsightCard({ correlations }: Props) {
  const entries = Object.entries(correlations).filter(([k]) => k.includes('→'));
  if (entries.length === 0) return null;
  return (
    <div className="rounded-3xl border border-border bg-secondary p-4">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 size={14} className="text-primary" />
        <h4 className="text-[0.6875rem] font-black uppercase tracking-widest text-muted-foreground">
          데이터 인사이트 — 변수 간 상관
        </h4>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {entries.map(([key, r]) => {
          const [a, b] = key.split('→');
          const tone = r > 0 ? 'text-success' : r < 0 ? 'text-danger' : 'text-muted-foreground';
          return (
            <div key={key} className="rounded-lg border border-border bg-card px-3 py-2">
              <div className="text-[0.625rem] font-bold text-muted-foreground">
                {FEATURE_LABELS[a] ?? a} ↔ {FEATURE_LABELS[b] ?? b}
              </div>
              <div className={`text-sm font-black tabular-nums ${tone}`}>
                r = {r >= 0 ? '+' : ''}
                {r.toFixed(2)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: tsc 전체 통과 확인**

```bash
cd frontend && npx tsc --noEmit
```
Expected: 0 에러.

- [ ] **Step 3: 빌드 확인**

```bash
cd frontend && npm run build
```
Expected: 성공.

- [ ] **Step 4: Commit**

```bash
cd frontend && npx prettier --write src/components/SimulationResult/dashboard/sub/predict/scenario/CorrelationInsightCard.tsx
git add frontend/src/components/SimulationResult/dashboard/sub/predict/scenario/CorrelationInsightCard.tsx
git commit -m "feat(scenario): 상관관계 인사이트 정보 박스"
```

---

## Phase 6 — 통합 검증 + 안내

### Task 18: 회귀 테스트 + 운영 안내

**Files:**
- 영향: 전체 백엔드/프론트 테스트

- [ ] **Step 1: 백엔드 전체 테스트**

```bash
pytest tests/test_sensitivity.py -v
```
Expected: 모든 테스트 PASS (기존 + 신규).

- [ ] **Step 2: 프론트 전체 테스트 + tsc + 빌드**

```bash
cd frontend && npx vitest run
cd frontend && npx tsc --noEmit
cd frontend && npm run build
```
Expected: 모두 성공.

- [ ] **Step 3: 백엔드 수동 smoke test**

백엔드 서버 띄운 뒤:
```bash
cd backend && uvicorn src.main:app --reload &
sleep 3
curl -s "http://localhost:8000/predict/sensitivity?dong_code=11440660&industry_code=CS100001" | python -m json.tool | head -40
```
Expected: `elasticity.vacancy_rate.+10`이 길이 4 list, `baseline_sales`가 길이 4 list.

- [ ] **Step 4: 디스코드 안내 메시지 작성 (수동 발송)**

다음 메시지를 C1·백엔드 담당에게 디스코드로 보낼 준비.
```
[Scenario Simulator S3] schema breaking change 안내

- /predict/sensitivity 응답이 변경됩니다:
  · elasticity[slider][level]: float → list[float] (길이 4, 분기별)
  · baseline_sales: 변경 없음 (이미 list)
- 슬라이더 5개 중 2개 교체:
  · 제거: rent_1f, floating_pop
  · 추가: cpi_index, opr_sale_mt_avg
- 프론트 타입 갱신 필요 (frontend/src/types/elasticity.ts)
- 운영 캐시 재생성: python -m models.tcn_forecast.sensitivity 실행 필요
- 브랜치: sj_simul (dev 머지 예정)
```

- [ ] **Step 5: 최종 정리 커밋 (필요시)**

미커밋 잔여 변경 확인:
```bash
git status
```
잔여물 있으면 적절한 메시지로 커밋. 없으면 종료.

---

## 완료 기준

- [ ] Phase 1 — 백엔드 배치: SLIDER_FEATURES 재구성, perturb 함수 list[float] 반환, 캐시 재생성 완료
- [ ] Phase 2 — API: SensitivityResponse list[float] schema, ETag 회귀 통과
- [ ] Phase 3 — 타입: ElasticityResponse 갱신
- [ ] Phase 4 — 훅: useElasticity 갱신, useScenarioCandidates·useElasticityComparison 신규
- [ ] Phase 5 — 컴포넌트: 5개 신규 + 1개 수정
- [ ] Phase 6 — 통합: 모든 테스트 PASS, 빌드 성공, smoke test 확인, 디스코드 안내 발송



