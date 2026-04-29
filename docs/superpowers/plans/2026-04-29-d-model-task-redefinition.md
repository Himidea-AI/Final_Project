# D 모델 Task 재정의 — Day-of-Week × Hour 활동량 예측

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development
>
> **Goal:** 분기 평균 유동인구 예측 (현재 task) → **(동 × 요일 × 시간대) 활동량 예측** 으로 task 정의 변경. 학술 표준 MASE < 0.7 달성.
>
> **현재 한계** (분기 평균 task): naive R² 0.989, MASE 0.997 → 모델 가치 거의 0.
> **목표 task**: 마포 동별 (월~일) × (0~23시) 168 시간 슬롯의 평균 활동량 예측. 변동성 ↑ → 모델 학습 가치 ↑.

---

## 0. Task 변경 근거

### 0.1 현재 task 의 본질적 한계
- 자기상관 0.86 (lag=1 median)
- 분산 98% 그룹간 / 2.3% 그룹내
- naive baseline 이 거의 optimal
- 어떤 architecture / 데이터 보강도 MASE 0.85 이상 어려움

### 0.2 새 task 가 더 가치 있는 이유

| 현재 task | 새 task |
|---|---|
| 분기 평균 1 값 (동×시간대당) | 분기 평균 168 값 (동×요일×시간대당) |
| 변동 폭 ~3% (Δy/y) | 변동 폭 ~30%+ (토요일 22시 vs 화요일 22시) |
| 매장 의사결정 가치 낮음 | 요일/시간대별 인력 배치 직접 활용 |
| 모델 학습 신호 0 | 학습 가능한 신호 풍부 |

### 0.3 데이터 가용성 확인 ✅
- `data/processed/living_population_dong_mapo.csv` (302MB)
- 컬럼: `STDR_DE_ID` (YYYYMMDD), `TMZON_PD_SE` (0~23), `ADSTRD_CODE_SE` (dong_code), `TOT_LVPOP_CO`
- 2019-02 부터 일별×시간대별×동별 raw 데이터
- → 16동 × 7요일 × 24시간 = **2,688 그룹** × ~25 분기 가능

---

## 1. 새 Task 정의

### 1.1 입력/출력

**입력**: 과거 N 분기의 (동 × 요일 × 시간대) 평균 인구 시계열
- shape per sample: `(window_size=8, n_features)`
- features: total_pop + day_of_week_one_hot(7) + hour_norm + dong_one_hot(16) = 25차원

**출력**: 다음 분기의 (동, 요일, 시간대) 평균 인구
- 단일 값 (해당 그룹의 분기 평균)

### 1.2 데이터 단위
- 그룹: (dong_code, day_of_week, time_zone) → 2,688 그룹
- 분기당 1 값 per 그룹 (해당 분기 내 같은 요일×시간대의 평균)
- 예: 2024Q3 합정동 토요일 22시 평균 인구

### 1.3 평가 baseline
- **naive lag=1**: 직전 분기 (dong, dow, hour) 평균값
- **seasonal lag=4**: 1년 전 같은 분기 (계절성 baseline)
- **dong×hour 평균** (요일 무시): 현재 D 모델의 대응

---

## 2. Architecture

```
Input: (B, window=8, 25 features)
       └─ total_pop, dow_oh×7, hour_norm, dong_oh×16
       │
       ▼
   TCNForecaster (n_channels=64, dilations=[1,2,4], dropout=0.2)
       │
       ▼
Output: (B, 1)  ← 다음 분기 (dong, dow, hour) 평균
```

**왜 TCN 재사용**: 기존 `models/tcn_forecast/model.py` 그대로 사용 가능. residual learning 도 지원.

**기대 MASE**: 0.5~0.7 (Same-period). 이유:
- 분기 평균에서 사라진 변동성이 (dong, dow, hour) 단위에서 살아남
- 토요일 vs 평일 패턴 학습 → naive 단순 lag 보다 우수 가능

---

## 3. Tasks

### Task 1: 데이터 prep + 캐시 생성

**Files:**
- Create: `models/living_pop_forecast/data_prep_dow_hour.py`
- Create: `data/processed/living_pop_dow_hour_quarterly.csv` (캐시)
- Create: `tests/test_data_prep_dow_hour.py`

**핵심 함수**:
```python
def build_dow_hour_aggregation(raw_df: pd.DataFrame) -> pd.DataFrame:
    """일별 raw → (dong_code, quarter, day_of_week, time_zone, mean_pop) 집계.

    quarter = year * 10 + quarter_num (예: 20241).
    day_of_week = 0 (월) ~ 6 (일).
    time_zone = 0 ~ 23.
    """

def load_dow_hour_cache(cache_path: Path | None = None) -> pd.DataFrame:
    """캐시 우선 로드. 없으면 raw csv 에서 build."""
```

**검증**:
- 합계 row 수 = 16 dongs × 7 dow × 24 hours × ~25 quarters = ~67,200
- 결측 fillna(group median) (특정 (dong, dow, hour, quarter) 조합 데이터 부재 시)

### Task 2: Naive + Seasonal baseline 측정

**Files:**
- Create: `validation/experiments/living_pop/baseline_dow_hour.py`

**핵심**:
1. Task 1 데이터 로드
2. 시간순 70/15/15 split (분기 기준)
3. naive_lag1: 직전 분기 같은 (dong, dow, hour) 값
4. seasonal_lag4: 1년 전 분기 같은 (dong, dow, hour) 값
5. metric (MAE/RMSE/MAPE/R²) 산출 + stdout

**기대**: naive R² ~0.85~0.95 (분기 평균보다 낮을 것), MASE 자기 자신 = 1.0

### Task 3: 모델 학습

**Files:**
- Create: `models/living_pop_forecast/train_dow_hour.py`
- Modify: `models/living_pop_forecast/data_prep_dow_hour.py` (prepare_sequences 추가)

**핵심**:
- TCN 학습 with cfg `version="v6_dow_hour"`
- POP_FEATURES_DOW_HOUR = `total_pop` + `time_zone_norm` + `dow_one_hot×7` + `dong_one_hot×16` = **25 dim**
- 또는 residual mode 도 지원 (`v6_dow_hour_residual`)
- 가중치: `living_pop_tcn_v6_dow_hour.pt` (분리 보장)
- LODO 적용 (Task 4 통합 검증)

### Task 4: evaluate_all 통합 + 비교 리포트

**Files:**
- Modify: `validation/experiments/living_pop/evaluate_all.py` (`_evaluate_v6_dow_hour` 추가)
- Create: `docs/abm-simulation/living-pop-dow-hour-report.md`

**핵심**:
1. evaluate_all 에 v6 evaluator 추가
2. 새 baseline (naive_lag1_dow_hour) 도 추가
3. 학술 metric pipeline 그대로 재사용 (Task 1 forecast_metrics)
4. v4_residual (현재 task) vs v6_dow_hour (새 task) 비교 — **단 다른 task 라 단순 비교 X**
5. v6 의 naive 대비 개선만 측정

**MASE 게이트**:
- v6_dow_hour MASE < 0.85 → 의미있는 개선 (현재 v4 수준)
- v6_dow_hour MASE < 0.7 → 진짜 학술 통과
- v6_dow_hour MASE > 1.0 → task 변경도 효과 없음, D 모델 재정의 실패

### Task 5: (선택) 백엔드 API 통합

**Files:**
- Modify: `models/living_pop_forecast/predict_dow_hour.py` (생성)
- Modify: `backend/src/agents/nodes/ml_prediction.py` (선택)
- Modify: `backend/src/schemas/simulation_input.py` (선택, dow + time_zone 입력 받기)

**핵심**:
- 신규 endpoint: `predict_dow_hour(dong_name, target_quarter, day_of_week, time_zone) -> int`
- 기존 endpoint (`predict_peak`) 는 v4_residual 그대로 유지 — 호환성 보장

⚠️ **Task 5 는 v6_dow_hour 가 학술 게이트 통과한 경우만 진행**. fail 시 task 4 결과 보고로 종료.

---

## 4. 검증 (각 Task 후)

```bash
cd "C:/Users/804/Documents/final project"

# Task 1 후
python -m pytest tests/test_data_prep_dow_hour.py -v
ls -la data/processed/living_pop_dow_hour_quarterly.csv  # 캐시 생성 확인

# Task 2 후
python -m validation.experiments.living_pop.baseline_dow_hour
# stdout 에 MAE, MAPE, R² 출력 — 정직한 baseline 수치

# Task 3 후
python -m models.living_pop_forecast.train_dow_hour --epochs 100 --patience 15 --seed 2026
ls -la models/living_pop_forecast/weights/living_pop_tcn_v6_dow_hour.pt

# Task 4 후
python -m validation.experiments.living_pop.evaluate_all --filter v6_dow_hour
# 또는 전체:
python -m validation.experiments.living_pop.evaluate_all
```

---

## 5. Risk & Mitigation

| Risk | 가능성 | Mitigation |
|---|---|---|
| (dong, dow, hour) 단위에서도 자기상관 여전히 강함 | 중간 | Task 2 baseline 측정으로 즉시 진단. naive R² > 0.95 면 데이터 자체 한계, 다른 architecture 도 효과 X |
| 결측 그룹 (특정 조합 데이터 0) | 중간 | fillna(group median) + interpolation. test 에서 결측 ratio 확인 |
| 데이터량 폭증으로 학습 시간 ↑ | 낮음 | 그룹당 ~25 분기 시퀀스 — 충분히 작음. 7~10분 학습 예상 |
| v4_residual 가중치 손상 | 낮음 | version="v6_dow_hour" 강제 + save_path 자동 분리 |
| 백엔드 통합 시 기존 API 깨짐 | 낮음 | predict_peak() 그대로 유지 + 신규 endpoint 만 추가 |

---

## 6. 의사결정 게이트

```
Task 2 baseline 측정 후:
  naive R² < 0.95?  YES → 진짜 변동성 있음, Task 3 진입
                    NO → 새 task 도 stationary, 종료 권장 (D 모델 재정의 효과 없음)

Task 3 학습 후 → Task 4 평가:
  v6 MASE < 0.85?   YES → 의미있는 개선, Task 5 (백엔드 통합) 진입 권장
                    NO → 본 task 도 한계 close, Task 5 보류 + 다른 R&D 방향
  v6 MASE < 0.7?    YES → 학술 통과, production 채택 강력 권장
                    NO → fallback 유지 (v4_residual 또는 naive)
```

---

## 7. 예상 일정

| Phase | Task | 예상 소요 |
|---|---|---|
| 1 | Task 1 (데이터 prep) | 0.5일 |
| 1 | Task 2 (baseline 측정) | 0.5일 (병렬) |
| 2 | Task 3 (모델 학습) | 1일 |
| 2 | Task 4 (evaluate + 리포트) | 0.5일 |
| 3 | Task 5 (백엔드 통합, 게이트 통과 시) | 1일 |
| 합계 | – | **2.5~3.5일** |

---

## 8. Out-of-Scope

- **프론트엔드 UI 갱신** — 사용자가 dow + hour 선택하는 UI. 별도 ticket
- **C/E 모델도 동일 task 변경** — D 결과 보고 결정
- **분기 단위 외 다른 단위** (월/주) — D task 변경 평가 후 결정
- **Foundation models (Chronos)** — D task 변경 결과 보고 결정

---

## 9. 참고

- 현재 D 모델 한계: `docs/abm-simulation/living-pop-forecast-v2-vs-v3-report.md` § 10
- 학술 metric pipeline: `validation/metrics/forecast_metrics.py`
- 데이터: `data/processed/living_population_dong_mapo.csv` (raw, 302MB)
- 기존 v4_residual 가중치: production fallback 으로 유지
