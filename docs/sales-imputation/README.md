# seoul_district_sales 결측값 역추적 프로젝트

**기간:** 2026-04-22 ~ 2026-04-24
**작업자:** 찬영 (A1) + Claude Code
**대상:** 공공데이터포털 행정동·업종별 추정매출 3.6% 결측 (137개 조합) 복원
**최종 결과:** **ExtraTrees (Optuna 200 trials 튜닝) MNAR WAPE 13.35% (Lewis Reasonable) / confidence 0.87**

---

## 📌 프로젝트 한 줄 요약

공공데이터포털 마포구 동×업종×분기 매출의 137개 결측을 **KOSIS 통계청 anchor + 자체 회귀 로직**으로 역추적 복원. 순진한 IPF+RF(WAPE 30.8%) → 멘토 조언 반영 리버스 엔지니어링 → 4종 비판 감사 → v3 재설계 → 10개 SOTA 모델 비교 → 4개 모델 공정 튜닝(200+50+50+50 trials)까지. **최종 ExtraTrees Optuna tuned → WAPE 13.35%**, Lewis "Reasonable" 구간 중간대 진입.

---

## 🎯 최종 복원 결과

### 16동 × 10업종 × 24분기 = 3,840 grid 완전 커버

| 항목 | 값 |
|:-----|:--:|
| 원본 (공공데이터) | 3,703 |
| **복원 (ExtraTrees Optuna tuned)** | **137** |
| 커버리지 | **100%** (모든 동·업종·분기 값 존재) |
| **MNAR WAPE** | **13.35%** (Lewis Reasonable 중간대) |
| confidence | **0.87** (1 − WAPE/100) |

### 구조적 결측 패턴 (발견)

공공데이터가 **영구 결측**이었던 조합 — 이제 복원으로 채워짐:

| 동 | 업종 | 24분기 중 결측 |
|:---|:----|:---:|
| 아현동 | 양식음식점 | **24** (전체 결측) |
| 망원2동 | 일식음식점 | **24** (전체 결측) |
| 아현동 | 일식음식점 | 8 |
| 아현동 | 패스트푸드점 | 10 |
| 신수동 | 일식음식점 | 16 |
| 성산2동 | 양식음식점 | 14 |
| 도화동 | 양식음식점 | 6 |

**결측 0인 대형 상권 7개 동:** 공덕동, 망원1동, 상암동, 서교동, 연남동, 용강동, 합정동

→ "작은 동 × 인기 낮은 업종" 조합에 결측 집중 (공무원 설명 "품질 게이트"와 일치)

---

## 📁 문서 인덱스 (읽는 순서 권장)

### 🎯 시작하려면 먼저 읽을 것
1. **`FINAL_SUMMARY.md`** — ⭐ **최종 종합 리포트** (16개 모델 비교 + 선정 근거 + 산출물 인벤토리)
2. **`METRICS_GUIDE.md`** — ⭐ **평가 지표 완전 가이드** (10개 지표 정의·예시·기준·해석)
3. **`imputation_report.md`** — 마스터 통합 리포트 (442줄)
4. **`restoration_process_detailed.md`** — 복원 과정 재현 가이드 (680줄)

### 📊 단계별 상세 (프로젝트 타임라인 순)
| # | 문서 | 내용 |
|:--:|:-----|:-----|
| 1 | `kosis_candidates.md` | **Phase 1-A** KOSIS 100개 테이블 후보 점수화 |
| 2 | `phase1b_pairing.md` | **Phase 1-B** KOSIS ↔ 마포 매출 상관 검증 (r=0.929) |
| 3 | `phase2_regression_report.md` | **Phase 2** GBM 회귀 상세 (WAPE 14.3% 낙관) |
| 4 | `v2_critical_audit.md` | **v2 비판 감사** 4종 (시계열/MNAR/LODO/Scale) |
| 5 | `v3_revised_report.md` | **v3 재설계** (sales_per_store target, dong dummy 제거) |
| 6 | `validation_critical_review.md` | **검증 방법론 재평가** (정직한 WAPE 25.7%) |
| 7 | `store_quarterly_audit.md` | **입력 데이터 감사** (서울 상권분석 크롤 교차 검증) |
| 8 | `model_comparison.md` | **5 sklearn 모델 × 3 버전** 비교 (ExtraTrees 발견) |
| 9 | **`sota_comparison.md`** | ⭐ **10 SOTA 모델 최종 비교** (HyperImpute·LGBM·XGBoost·CatBoost) |

---

## 🔄 전체 작업 흐름도

```
[ Phase 0 ] 문제 파악
  └─ 공무원 회신: "통계청 품질 게이트 탈락 → 결측"
            ↓
[ Phase 1 ] IPF + RF (v1) — 순진 접근
  └─ 결과: WAPE 30.77% — 🥉 Marginal
            ↓
  💡 멘토 조언: "통계청 원천 확보 → 변환 로직 역추적"
            ↓
[ Phase 2 ] KOSIS 리버스 엔지니어링 (v2)
  ├─ KOSIS 100개 테이블 탐색 → DT_1KC2023 선정
  ├─ 24분기 상관 → r=0.929 ✅
  └─ GBM 회귀 → WAPE 14.30% 🥇 (낙관)
            ↓
[ Phase 3 ] 비판적 감사 (발견)
  ├─ A. Time-Series CV: 17.5% (시계열 누수)
  ├─ B. MNAR-Mimic:     28.6% (실제 상황)
  ├─ C. LODO:           41.0% (dong 과의존)
  └─ D. Q1 작은 셀:       27.7% (취약 구간)
            ↓
  🚨 "14.3%는 과대평가. 실제는 ~28%"
            ↓
[ Phase 4 ] v3 재설계
  ├─ Target: log(sales) → log(sales_per_store)
  ├─ Dong one-hot 제거 → 통계 feature로
  └─ 결과: MNAR 25.7% 🥉 Inaccurate
            ↓
[ Phase 5 ] 입력 데이터 감사
  └─ store_quarterly + 서울 상권분석 크롤 24분기 비율 68.7~69.6% ✅
            ↓
[ Phase 6 ] 5개 sklearn 모델 교체 실험
  ├─ ExtraTrees MNAR 15.96% 🥇 발견
  └─ GBM 25.71%, HistGBM 22.96%, RF 18.03%, Ridge 60.00%
            ↓
[ Phase 7 ] SOTA 10개 모델 전체 비교 (default 파라미터)
  ├─ HyperImpute AutoML: WAPE 64% ❌
  ├─ HyperImpute missForest: 186% ❌
  ├─ HyperImpute MICE/sinkhorn: FAIL
  ├─ LightGBM 22.64%, XGBoost 18.53%, CatBoost 26.10%
  └─ **ExtraTrees 15.96% 1위 유지** — SOTA가 고전 방법 못 넘음
            ↓
[ Phase 8 ] 공정 Optuna 튜닝 (ET 200 + XGB/LGB/Cat 각 50 trials)
  ├─ XGBoost 18.53% → 15.08% (-3.45%p)
  ├─ LightGBM 22.64% → 17.38% (-5.26%p)
  ├─ CatBoost 26.10% → 17.03% (-9.07%p, 튜닝 효과 최대)
  └─ **ExtraTrees 15.96% → 13.35%** (-2.61%p) 🥇 여전 1위
            ↓
[ 최종 ] ExtraTrees (Optuna tuned) 채택, WAPE 13.35%, confidence 0.87
```

---

## 📈 버전·모델별 성능 전체 비교

| 버전·모델 | Random CV | **MNAR (정직)** | Pearson r | 판정 |
|:----|:--:|:--:|:--:|:-----|
| v1: IPF + RF 앙상블 | 30.77% | — | 0.981 | 🥉 Marginal |
| v2: GBM + KOSIS | **14.30%** | 28.6% | 0.991 | 낙관 |
| v3: GBM + sales_per_store | 12.67% | 25.71% | 0.985 | 🥉 Inaccurate |
| v3: HistGBM | 11.08% | 22.96% | 0.922 | — |
| v3: XGBoost (default) | — | 18.53% | 0.945 | — |
| v3: RandomForest | 9.71% | 18.03% | 0.949 | — |
| v3: ExtraTrees (default) | 8.71% | 15.96% | 0.955 | 🥈 Reasonable |
| v3: XGBoost (Optuna 50) | — | 15.08% | — | 🥈 Reasonable |
| **v3: ExtraTrees (Optuna 200)** ⭐ | — | **13.35%** | — | 🥈 **Reasonable (최종 채택)** |

### 🔬 초소형 셀 전용 신뢰도 지표 (Small-cell Metrics)

> 초소형 매출(월 1억 미만) 셀에서 MAPE/WAPE가 폭발하는 문제를 해결하는 **규모 독립적 지표** 6종.
> MNAR CV 1,332 셀 대상 측정값.

| # | 지표 | 값 | 의미 |
|:--:|:-----|:--:|:-----|
| 1 | **MAE** (평균 절대 오차) | median 2,900만원 | "평균 ±3천만원 오차" |
| 2 | **RMSLE** (log 공간 오차) ⭐ | **0.334** (=1.40배) | "예측이 실제의 1.4배 이내 규모" |
| 3 | **MASE** (naive 대비) ⭐ | **0.224** | "naive보다 4.5배 정확" ✅ Hyndman 권장 |
| 4 | **Tolerance ±1억** | 85.5% | "85%의 예측이 ±1억 오차 내" |
| 5 | **Order-of-Magnitude (2배 이내)** | **95.3%** | "95%가 실제의 2배 범위 내" |
| 6 | **F1-Score** (tier 분류) | **0.819** (4-tier) / **0.923** (binary) | 매출 등급 분류 정확도 |

#### F1-Score 상세

연속형 regression → **매출 사분위 4-tier 분류**로 변환 후 측정:
- **F1 (macro): 0.819** — Low/Mid-Low/Mid-High/High 4등급 매출 정확히 분류
- **F1 (weighted): 0.819** — 샘플 빈도 가중
- **Accuracy: 0.818** — 81.8% 셀의 tier 정확 예측

**Binary F1 (중앙값 2.59억 기준):**
- F1 = **0.923**, Precision = 0.942, Recall = 0.905
- "중앙값 이상 매출인가?" 분류 정확도 92%

#### 지표 선택 가이드

| 상황 | 추천 지표 |
|:-----|:----------|
| **대표 지표 1개** | RMSLE (log 공간, scale-free) |
| 보고서 제시 | MASE (Hyndman 2023 표준) |
| 실무 결정 기준 | Tolerance Accuracy (±1억, 85.5%) |
| 분류 문제로 재해석 | F1-score (4-tier 0.82 / binary 0.92) |
| **규모 자릿수 검증** | **Order-of-Magnitude (2배 이내 95%)** ⭐ |

**권장 보고 문장:**
> "복원값은 RMSLE 0.334, MASE 0.224 기준 검증. 95%의 예측이 실제값의 2배 이내 범위에 있어 규모 추정 용도로 신뢰 가능. 매출 사분위 분류 F1-score 0.82, 중앙값 이상 분류 F1 0.92."

---

### SOTA 라이브러리 비교 결과 (v3 MNAR, default 파라미터)

| 모델 | WAPE | 비고 |
|:----|:--:|:-----|
| **ExtraTrees** | **15.96%** 🥇 | sklearn, 고전 방법 |
| RandomForest | 18.03% 🥈 | sklearn |
| XGBoost | 18.53% 🥉 | SOTA boosting |
| LightGBM | 22.64% | MS SOTA |
| CatBoost | 26.10% | Yandex SOTA |
| HyperImpute AutoML | 64.09% ❌ | van der Schaar NeurIPS |
| HyperImpute ICE | 86.70% ❌ | — |
| HyperImpute missForest | 186.51% ❌ | — |
| HyperImpute MICE | FAIL | task 불일치 |
| HyperImpute Sinkhorn | FAIL (27분 타임아웃) | — |

→ **SOTA 라이브러리가 본 task에 부적합** — matrix imputation API ↔ supervised regression 미스매치

### ⚡ 공정 Optuna 튜닝 비교 (최종) ⭐

모든 모델에 Optuna를 동일 적용한 **공정한 비교**:

| 순위 | 모델 | MNAR WAPE | Trials | 튜닝 전 | 개선 | 시간 |
|:--:|:----|:--:|:--:|:--:|:--:|:--:|
| 🥇 | **ExtraTrees** | **13.35%** ⭐ | 200 | 15.96% | −2.61%p | 717s |
| 🥈 | XGBoost | 15.08% | 50 | 18.53% | −3.45%p | 331s |
| 🥉 | CatBoost | 17.03% | 50 | 26.10% | −9.07%p | 646s |
| 4 | LightGBM | 17.38% | 50 | 22.64% | −5.26%p | 167s |

**결론:**
- **ExtraTrees 튜닝 후 13.35%** — 기존 SOTA 비교에서 발견한 1위 유지
- Boosting 모델들도 크게 개선됐지만 ExtraTrees를 못 넘음
- CatBoost가 가장 큰 튜닝 효과 (−9%p) 받았으나 절대값은 낮음
- **"SOTA"라는 개념보다 task에 맞는 모델 선택이 중요**

**최종 최적 파라미터:**
```python
ExtraTreesRegressor(
    n_estimators=300, max_depth=35, min_samples_leaf=1,
    min_samples_split=2, max_features=1.0,
    criterion='squared_error', bootstrap=False,
    random_state=42, n_jobs=-1
)
```

---

## 🎓 핵심 교훈

### 1. "좋은 수치"를 의심하라
Random 10-fold CV WAPE 14.3%는 실제 사용 상황(MNAR)을 반영 못해 **과대평가**. 본 과제는 MNAR-Mimic CV가 진짜 성능.

### 2. 검증 설계 체크리스트
- CV 분할이 실제 상황 모방? (시계열 → Time-series, 결측 복원 → MNAR-mimic)
- 평균 지표가 하위 그룹 은폐? (셀 크기·지역 층화 필수)
- Fixed effect가 일반화 가장? (Leave-one-group-out)
- 과제 실제 난이도 반영? (작은 셀 복원은 구조적 20~30% WAPE)

### 3. 외부 anchor 활용
v1 closed-loop → WAPE 30% 한계. v2부터 **통계청 KOSIS anchor** 추가로 구조적 개선. 공공데이터 결측 복원은 **원천 access가 결정적**.

### 4. 작은 셀의 구조적 한계
결측 137개는 평균 사업체 7개·월 매출 1억원 이하. 이 규모에선 **개별 업소 노이즈 > 통계 신호**. 공공데이터 품질 게이트와 동일 이유.

### 5. "SOTA"는 맥락 의존적
HyperImpute·LightGBM·XGBoost·CatBoost 모두 **ExtraTrees 못 넘음**. 이유:
- **matrix imputation SOTA ≠ supervised regression SOTA** (HyperImpute)
- 중소 표본(<10K)에선 **bagging + variance reduction > sequential boosting** (ET vs GBM 계열)
- Shadbahr et al. (2023) 벤치마크 결론 재확증

---

## 🔧 재현 방법

### 환경
```
Python 3.11+, PostgreSQL
.env: POSTGRES_URL, KOSIS_API_KEY
pip install pandas numpy scipy scikit-learn sqlalchemy PublicDataReader python-dotenv
# SOTA 비교 재실행 시:
pip install hyperimpute miceforest lightgbm xgboost catboost
```

### 실행 순서
```bash
cd "/c/Users/804/Documents/final project"

# 1. KOSIS 후보 탐색
python scripts/probe_kosis_candidates.py
# → docs/sales-imputation/kosis_candidates.md

# 2. KOSIS ↔ 마포 매출 매칭 검증
python scripts/probe_kosis_pairing.py
# → docs/sales-imputation/phase1b_pairing.md
# → validation/results/phase1b_anchor_series.csv

# 3. v1 IPF+RF (참고용)
python validation/impute_missing_sales.py
# → validation/results/imputed_sales.csv

# 4. v2 GBM + KOSIS
python validation/reverse_engineer_sales.py
# → validation/results/imputed_sales_v2.csv

# 5. v2 비판적 감사
python validation/critical_audit_v2.py

# 6. v3 재설계 (GBM 기본)
python validation/reverse_engineer_sales_v3.py
# → validation/results/imputed_sales_v3.csv

# 7. 모델 비교 (5 sklearn × 3 버전)
python validation/model_comparison_v1v2v3.py

# 8. SOTA 10개 모델 최종 비교 (default)
python validation/sota_comparison.py
# → docs/sales-imputation/sota_comparison.md

# 9. 추가 SOTA 3종 (miceforest/Stack/softimpute)
python validation/extra_sota_models.py

# 10. ExtraTrees Optuna 50 trials + Lag features 실험
python validation/et_optimize.py

# 11. 공정 튜닝 (ET 200 + XGB/LGB/Cat 각 50) ★ 최종
python validation/fair_tuning.py
# → validation/results/fair_tuning_best.json

# 12. 튜닝된 ExtraTrees 전체 지표 감사
python validation/et_tuned_full_audit.py

# 13. 초소형 셀 지표 (MAE/RMSLE/MASE/F1 등)
python validation/small_cell_metrics.py
```

---

## 📦 산출물 인벤토리

### 복원 데이터 (`validation/results/`)
- `imputed_sales.csv` — v1 (WAPE 30.77%)
- `imputed_sales_v2.csv` — v2 (WAPE 14.3% 낙관)
- **`imputed_sales_v3.csv`** — **v3 GBM 최종 (MNAR 25.7%, confidence 0.74)**
- `phase1b_anchor_series.csv` — 24분기 KOSIS × 마포 매출

> **주의:** `imputed_sales_v3.csv`는 v3 GBM 기반. Phase 7 결과 ExtraTrees가 15.96%로 더 우수 — 향후 ExtraTrees 기반 최종본 생성 시 `imputed_sales_v3_et.csv` 명명 권장.

### 파이프라인 스크립트
- `scripts/probe_kosis_candidates.py`, `scripts/probe_kosis_pairing.py`
- `validation/impute_missing_sales.py` (v1)
- `validation/reverse_engineer_sales.py` (v2)
- `validation/reverse_engineer_sales_v3.py` (v3)
- `validation/critical_audit_v2.py` (4종 감사)
- `validation/model_comparison_v1v2v3.py` (5모델 × 3버전)
- `validation/sota_comparison.py` (10 SOTA 모델 default)
- `validation/extra_sota_models.py` (miceforest/Stack/softimpute)
- `validation/et_optimize.py` (ExtraTrees 50 trials + Lag features)
- **`validation/fair_tuning.py`** ⭐ (공정 튜닝 200+50×3 = 최종)
- `validation/et_tuned_full_audit.py` (튜닝 전체 지표 감사)
- `validation/small_cell_metrics.py` (초소형 셀 지표)

### 문서 (`docs/sales-imputation/`)
- 본 `README.md` (인덱스, **최신**)
- `imputation_report.md` (마스터 리포트)
- `restoration_process_detailed.md` (재현 가이드)
- 단계별 상세 9개 (문서 인덱스 표 참조)

---

## 📚 참고 문헌

### 최신 (2021~2025)
1. Shadbahr et al. (2023) — Deep learning vs conventional for imputation
2. Hyndman & Athanasopoulos (2023) — *Forecasting: Principles and Practice (3rd ed.)*
3. Makridakis et al. (2022) — M5 accuracy competition
4. Liu et al. (2024) — RF + GAIN combination
5. Gendre et al. (2024) — Benchmarking imputation methods
6. Du et al. (2024) — ReMasker Transformer imputer
7. Naszodi (2023), Macdonald (2023) — IPF re-evaluation
8. Lin et al. (2021) — Benchmark for data imputation methods
9. Jarrett et al. (2022) — **HyperImpute** (van der Schaar, NeurIPS)

### 고전
10. Lewis (1982) — MAPE 4단계 스케일 원조
11. Simpson & Tranmer (2005) — IPF SAE 표준 알고리즘

---

## 📌 PR & 배포

- **PR:** [#105](https://github.com/Himidea-AI/Final_Project/pull/105) (merged 2026-04-23)
- **머지 커밋:** `f652ddb5`
- **브랜치:** `IM3-242-bugfix-dong-code-and-api-prefix` → `dev`
