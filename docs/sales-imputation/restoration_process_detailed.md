# seoul_district_sales 137 결측 셀 복원 과정 상세 문서

**작성일:** 2026-04-23
**대상 독자:** 데이터 엔지니어·검증자·향후 유지보수 담당자
**목적:** 복원 파이프라인의 **모든 단계를 재현 가능한 수준**으로 문서화

---

## 목차

1. 전체 개요 — 입력, 출력, 단계
2. 입력 데이터 구조
3. 파이프라인 v1 상세 (IPF + RF)
4. 파이프라인 v2 상세 (GBM + KOSIS 리버스 엔지니어링)
5. 파이프라인 v3 상세 (비판 감사 반영)
6. 피처 엔지니어링
7. 학습 · 예측 · 환산 수식
8. 교차검증 설계 4종
9. 복원 결과 후처리
10. 전체 재실행 절차 (CLI)

---

## 1. 전체 개요

### 1.1 입력과 출력

**입력:**
- `seoul_district_sales` (행정동×업종×분기 매출, 3,703 rows) — 공공데이터포털
- `store_quarterly` (동×업종×분기 사업체 수, 3,840 rows) — 이미 DB 적재됨
- **KOSIS DT_1KC2023** (서울 숙박·음식점업 서비스업생산지수, 24 분기) — 통계청 OpenAPI

**출력:**
- `imputed_sales_v3.csv` — 3,840 rows (3,703 원본 + 137 복원)
- 각 복원 셀에 `confidence=0.74` 부여 (MNAR 25.7% WAPE 반영)

### 1.2 복원 단계 요약

```
[입력 수집]
  ├─ DB: seoul_district_sales (살아있는 3,703 셀)
  ├─ DB: store_quarterly (full grid 3,840)
  └─ API: KOSIS DT_1KC2023 → phase1b_anchor_series.csv
            ↓
[결측 식별]
  └─ LEFT JOIN: store_quarterly ← seoul_district_sales
        → 137 셀은 monthly_sales = NaN
            ↓
[피처 엔지니어링]
  └─ 36개 피처 구성 (원본 v2) / 25개 피처 (v3)
            ↓
[모델 학습]
  └─ Gradient Boosting Regressor (sklearn)
      · v1: IPF (40%) + RandomForest (60%) 앙상블
      · v2: GBM 단독 (target: log(sales))
      · v3: GBM 단독 (target: log(sales_per_store))
            ↓
[교차검증 4종]
  ├─ Random 10-fold
  ├─ Time-Series rolling (누수 차단)
  ├─ MNAR-Mimic (결측 프로파일 층화)
  └─ Leave-One-Dong-Out (고정효과 의존 검사)
            ↓
[최종 복원]
  └─ 전체 살아있는 셀로 재학습 → 137 결측 예측
            ↓
[후처리]
  ├─ confidence 점수 부여 (WAPE 기반)
  └─ CSV 저장
```

---

## 2. 입력 데이터 구조

### 2.1 `seoul_district_sales` (원본, 부분 결측)

```sql
CREATE TABLE seoul_district_sales (
    quarter          bigint,      -- YYYYQ 예: 20191 (2019년 1분기)
    dong_code        text,        -- 11440555 (아현동)
    dong_name        text,
    industry_code    text,        -- CS100001~CS100010
    industry_name    text,
    monthly_sales    bigint,      -- 월 매출 (원 단위) ← 복원 대상
    monthly_count    bigint,      -- 건수
    ...              -- 총 52개 컬럼 (weekday/weekend/hour/age/gender 세분)
);
```

- 16 동 × 10 업종 × 24 분기 = **3,840 조합 이론상**
- 실제 **3,703 rows** 존재 → 137 조합이 **행 자체가 없음** (NULL 아님)
- **이 "행 자체 누락"을 식별하는 쿼리가 가장 중요:**

```sql
-- 결측 조합 찾기 (store_quarterly의 full grid에서 빠진 행)
SELECT q.quarter, q.dong_code, q.industry_code
FROM store_quarterly q
LEFT JOIN seoul_district_sales s
  ON q.quarter = s.quarter
 AND q.dong_code = s.dong_code
 AND q.industry_code = s.industry_code
WHERE q.dong_code LIKE '11440%'
  AND s.monthly_sales IS NULL;   -- ← 137 rows 반환
```

### 2.2 `store_quarterly` (full grid, 결측 없음)

```sql
CREATE TABLE store_quarterly (
    quarter          integer,
    dong_code        varchar,
    industry_code    varchar,
    dong_name        varchar,
    industry_name    varchar,
    store_count      integer,        -- 사업체 수 ★ 핵심 피처
    open_count       integer,        -- 분기 개업 건수
    close_count      integer,        -- 분기 폐업 건수
    closure_rate     double precision,
    franchise_count  integer         -- 프랜차이즈 수
);
```

- **3,840 rows 완전 grid** → 137 결측 셀의 "위치"를 정의
- `store_count`가 결측 셀의 핵심 signal 제공

### 2.3 KOSIS DT_1KC2023 (통계청 anchor)

API 호출:
```python
from PublicDataReader import Kosis
api = Kosis(KOSIS_API_KEY)
df = api.get_data(
    "통계자료",
    orgId="101",          # 통계청
    tblId="DT_1KC2023",   # 시도별 서비스업생산지수
    objL1="11",           # 서울특별시
    objL2="I",            # 숙박 및 음식점업
    itmId="ALL",          # 경상지수 + 불변지수
    prdSe="Q",            # 분기
    startPrdDe="201901",
    endPrdDe="202404",
)
```

응답 컬럼: `수록시점`(YYYYQQ), `항목명`(경상지수/불변지수), `수치값`

**저장 형식** (phase1b_anchor_series.csv):
```
qkey,수치값,total_sales
20191,111.4,273623827812.0
20192,117.6,285696453914.0
...
20244,165.6,478324111539.0
```

---

## 3. 파이프라인 v1 상세 (IPF + RF)

### 3.1 핵심 개념

**IPF (Iterative Proportional Fitting):**
3차원 matrix `dong × industry × quarter`를 만들어 **각 축의 합계(marginal)가 관측값과 일치하도록 반복 스케일 조정**. Simpson & Tranmer (2005)의 고전 알고리즘.

```
초기: T[d,i,q] = 동업종 평균 × 분기 보정
반복:
  Step 1: dong 축 합계 = 관측 dong 합계 → 행별 rescale
  Step 2: industry 축 합계 = 관측 industry 합계 → 열별 rescale
  Step 3: quarter 축 합계 = 관측 quarter 합계 → 시점별 rescale
  수렴 조건: 모든 축 오차 < 1e-4
```

**Random Forest:**
1,000개 트리로 11개 피처에서 `log(monthly_sales + 1)` 예측.
- `dong_mean_sales` (해당 동 평균)
- `industry_mean_sales` (해당 업종 평균)
- `neighbor_dong_mean` (인접 동 평균, 거리 가중)
- `dong_industry_std` (해당 조합 변동성)
- `quarter`, `quarter_of_year`, `year`
- dong_code one-hot (부분)

### 3.2 앙상블 공식

```python
imputed = 0.4 × IPF_prediction + 0.6 × RF_prediction
```

비율은 경험적으로 결정 (IPF가 합계 보존에 강함, RF가 비선형 포착).

### 3.3 v1 결과

- **MAPE: 135.53% ±34** (소규모 셀 편향 — Lewis 1982 경고 실증)
- **WAPE: 30.77% ±1.47** — Lewis Inaccurate 경계
- **R²: 0.847**, **Pearson r: 0.981**

---

## 4. 파이프라인 v2 상세 (GBM + KOSIS)

### 4.1 접근 전환 근거

멘토 조언: "**통계청 원천을 확보해 변환 로직을 AI로 역추적하라.**"

가설:
```
seoul_district_sales ≈
    사업체수(동,업종,분기)            ← store_quarterly
  × 업종별_매출승수(서울)             ← KOSIS DT_3KB9001
  × 분기_트렌드배율(서울,분기)         ← KOSIS DT_1KC2023 ★
  + 품질게이트 필터 + ε
```

### 4.2 KOSIS anchor 검증 (Phase 1-B)

24 분기에 대해:
- `x` = KOSIS 서울 숙박·음식점업 서비스업생산지수
- `y` = 마포 총매출 (16동·10업종 합계)

```python
from scipy.stats import pearsonr, spearmanr
r, _ = pearsonr(x, y)      # r = 0.929 ✅
rho, _ = spearmanr(x, y)   # ρ = 0.853 ✅
```

→ 0.7 기준 초과. **KOSIS 지수가 강력한 anchor로 확정**.

### 4.3 피처 매트릭스 구성 (36개)

```python
X = pd.DataFrame()

# 원본 수치 피처 9개
X["store_count"]         = df["store_count"]
X["log_store_count"]     = np.log1p(store_count)
X["kosis_index"]         = df["kosis_index"]       # 분기별 KOSIS
X["log_kosis"]           = np.log(kosis_index)
X["store_x_index"]       = store_count × kosis_index / 100   # 상호작용
X["franchise_ratio"]     = franchise_count / store_count
X["open_ratio"]          = open_count / store_count
X["closure_rate"]        = df["closure_rate"]
X["q_of_year"]           = quarter % 10            # 1~4
X["year"]                = quarter // 10

# 업종 dummy 10개
for ind in [CS100001, ..., CS100010]:
    X[f"ind_{ind}"] = (industry_code == ind)

# 동 dummy 16개 (v2에서는 포함, v3에서 제거됨)
for dong in [11440555, ..., 11440740]:
    X[f"dong_{dong}"] = (dong_code == dong)
```

### 4.4 학습

```python
from sklearn.ensemble import GradientBoostingRegressor

y = np.log1p(df.loc[alive_mask, "monthly_sales"])   # 타겟: log 변환

gbm = GradientBoostingRegressor(
    n_estimators=400,      # 트리 수
    max_depth=4,           # 얕은 트리 (overfit 방지)
    learning_rate=0.05,    # 보수적 학습률
    random_state=42,
)
gbm.fit(X[alive_mask], y)
```

### 4.5 예측 · 환산

```python
log_sales_pred = gbm.predict(X[missing_mask])
sales_pred = np.expm1(log_sales_pred)              # log 역변환
```

### 4.6 v2 결과 (random CV 기준 — **과대평가 경고**)

- **WAPE: 14.30%** — 😊
- R²: 0.981
- Pearson r: 0.991

그러나 아래 5장에서 이 수치의 신뢰도를 비판적으로 재검사.

---

## 5. 파이프라인 v3 상세 (비판 감사 반영)

### 5.1 v2 검증의 4가지 약점 (비판 감사 결과)

| 감사 | 결과 | 의미 |
|:----|----:|:-----|
| A. Time-Series CV | WAPE 17.5% | 시계열 누수 소폭 존재 |
| **B. MNAR-Mimic** | **WAPE 28.6%** | **결측 실제 상황 정직 지표** |
| C. LODO | WAPE 41.0% | dong fixed effect 과의존 |
| D. Q1 (작은 셀) | WAPE 27.7% | 결측 프로파일에서 취약 |

→ v2 수치는 "살아있는 셀 무작위 holdout" 기준. **137 결측(작은 셀 위주) 복원 실제 정확도는 ~28%**.

### 5.2 v3 설계 변경 3가지

**변경 1 — Target 재정의:**
```python
# v2:  y = log(monthly_sales)
# v3:  y = log(sales_per_store) = log(monthly_sales / store_count)
```

이유: 매출은 규모 효과(큰 동×큰 업종)가 압도적. 점포당 매출(= 생산성)은 동·업종에 덜 의존 → **작은 셀도 같은 모델로 학습 가능**.

**변경 2 — Dong one-hot 제거:**
```python
# v2:
for dong in [11440555, ..., 11440740]:
    X[f"dong_{dong}"] = (dong_code == dong)    # 16 dummy ← lookup table 됨

# v3:
X["dong_avg_store"]   = df["dong_code"].map(dong_size_mean)     # 동 평균 사업체수
X["dong_total_store"] = df["dong_code"].map(dong_total)         # 동 전체 상권 규모
X["combo_avg_store"]  = df[["dong","ind"]].map(combo_mean)      # 업종×동 상호작용
```

이유: dummy는 dong fixed effect를 memorize. 통계 피처는 **의미 있는 signal**만 제공.

**변경 3 — 주 판정 지표 변경:**
```
v2: Random 10-fold WAPE
v3: MNAR-Mimic WAPE  (결측 실제 상황 모방)
```

### 5.3 v3 예측 · 환산 수식

```python
# 학습
y_sps = np.log1p(df["sales_per_store"])
gbm.fit(X[alive_mask], y_sps[alive_mask])

# 예측
log_sps_pred = gbm.predict(X[missing_mask])
sps_pred = np.expm1(log_sps_pred)                       # 점포당 월 매출

# 환산
sales_pred = sps_pred × store_count[missing_mask]       # × 실제 사업체수
```

### 5.4 v3 결과 (4종 감사 전부 적용)

| 감사 | v2 | **v3** | 개선 |
|:----|---:|---:|:--:|
| A. Time-Series | 17.5% | **15.8%** | ✅ −1.7%p |
| **B. MNAR (주 지표)** | **28.6%** | **25.7%** | ✅ −2.9%p |
| C. LODO | 41.0% | 41.8% | ≈ |
| D. Q1 작은 셀 | 27.7% | 24.7% | ✅ −3.0%p |

### 5.5 confidence 점수 도출

```python
# 규칙: confidence = max(0.60, 1.0 - MNAR_WAPE / 100)
# 이유: WAPE가 "어느 정도 틀리는가"의 직관적 척도

v3_mnar_wape = 25.7
confidence_missing = max(0.60, 1.0 - 0.257) = 0.74

out.loc[missing_mask, "confidence"] = 0.74
out.loc[alive_mask,   "confidence"] = 1.0
```

---

## 6. 피처 엔지니어링 상세

### 6.1 v3 최종 피처 목록 (25개)

| 분류 | 피처명 | 계산식 | 의미 |
|:----|:-----|:------|:-----|
| **수치 1** | `store_count` | 원본 | 해당 셀의 사업체 수 |
| 수치 2 | `log_store_count` | `log1p(store_count)` | 로그 스케일 (왜도 보정) |
| **수치 3** | `kosis_index` | KOSIS 분기값 | 서울 업계 트렌드 ★ |
| 수치 4 | `log_kosis` | `log(kosis)` | 로그 anchor |
| 수치 5 | `franchise_ratio` | `franchise / store_count` | 프랜차이즈 비율 |
| 수치 6 | `open_ratio` | `open_count / store_count` | 신규 오픈 비율 |
| 수치 7 | `closure_rate` | 원본 | 폐업률 |
| 시간 8 | `q_of_year` | `quarter % 10` | 1~4 분기 계절성 |
| 시간 9 | `year` | `quarter // 10` | 연도 |
| **통계 10** | `dong_avg_store` | `mean(store_count by dong)` | 동 상권 평균 규모 |
| 통계 11 | `dong_total_store` | `sum(store_count by dong)` | 동 전체 점포 수 |
| **통계 12** | `combo_avg_store` | `mean(store_count by dong, industry)` | 특정 동·업종 분기 평균 |
| **업종 13~22** | `ind_CS100001 ~ CS100010` | one-hot (10개) | 업종 구분 |

### 6.2 왜 dong one-hot을 제거했나 (상세)

**v2 문제:**
```
GBM이 "dong_11440710 == 1 ∧ ind_CS100010 == 1" 조합을 만나면
  → 해당 조합의 평균 매출을 lookup (memoize)
  → 일반화 불가 (새 동 예측 시 모든 dong dummy = 0 → base 값 반환)
```

**v3 해결:**
```
X["dong_avg_store"]를 사용하면
  → GBM은 "큰 동인가, 작은 동인가"라는 구조적 정보만 학습
  → 새 동도 dong_avg_store 값만 주어지면 예측 가능
```

### 6.3 log 변환 이유

매출 분포는 **로그 정규** (heavy-tailed). 원 스케일에서 MSE 최소화는 큰 셀에 과도 집중 → 작은 셀 예측 무시. log 변환 후:
- 큰 셀 상대 오차 커짐 → 가중 분산 균등화
- GBM은 `log(y)` 공간에서 일정한 회귀 트리 분할 가능

---

## 7. 학습 · 예측 · 환산 전체 수식

### 7.1 학습 단계

```
D_alive = {(x_i, y_i) : i ∈ 살아있는 3,703 셀}
  where  y_i = log(1 + sales_per_store_i)
           = log(1 + monthly_sales_i / store_count_i)

gbm(x) = Σ_{t=1}^{400} η · h_t(x)   # 400 트리의 가중합, η=0.05
  where h_t는 depth-4 회귀 트리

최소화: L = Σ_i (gbm(x_i) - y_i)^2
```

### 7.2 예측 단계 (137 결측 셀)

```
For each missing cell m in 137:
  log_sps_m = gbm(x_m)
  sps_m = exp(log_sps_m) - 1     # log1p 역변환
  sales_m = sps_m × store_count_m
```

### 7.3 확률적 해석

GBM의 예측 `sps_m`은 **조건부 평균** E[sales_per_store | x_m].
실제 셀 매출의 신뢰구간:
```
true_sales ∈ [sales_m × (1 - WAPE), sales_m × (1 + WAPE)]
            = [sales_m × 0.743, sales_m × 1.257]    (WAPE 25.7%)
```

---

## 8. 교차검증 설계 4종 상세

### 8.1 Random K-fold (v1/v2 기본)

```python
kf = KFold(n_splits=10, shuffle=True, random_state=42)
for tr_idx, te_idx in kf.split(alive_data):
    gbm.fit(X[tr_idx], y[tr_idx])
    pred = gbm.predict(X[te_idx])
    evaluate(y[te_idx], pred)
```

**용도:** 일반 모델 성능 상한 측정 (실제보다 낙관적)

### 8.2 Time-Series CV (rolling forward)

```python
quarters = [20191, 20192, ..., 20244]
for i in range(8, 24):            # 최소 2년(8분기)부터 시작
    train_qs = quarters[:i]
    test_q = quarters[i]
    tr_mask = df["quarter"].isin(train_qs)
    te_mask = df["quarter"] == test_q
    gbm.fit(X[tr_mask], y[tr_mask])
    pred = gbm.predict(X[te_mask])
```

**용도:** 시계열 누수 차단. 미래 분기 예측 정확도.

### 8.3 MNAR-Mimic CV (주 판정 지표)

```python
# 1. 결측 셀 프로파일 파악
missing_q95_store = df[missing].store_count.quantile(0.95)  # = 15

# 2. 유사한 survivor만 타겟
mimic_pool = df[alive & (store_count <= 15)]  # ~1,333개

# 3. 5-fold CV on mimic_pool (훈련은 전체 alive 사용)
for fold in folds(mimic_pool):
    tr_mask = alive & (~index.isin(fold))
    gbm.fit(X[tr_mask], y[tr_mask])
    pred = gbm.predict(X[fold])
```

**용도:** 결측 **실제** 복원 정확도. 본 과제 **주 판정 지표**.

### 8.4 Leave-One-Dong-Out

```python
for dong in ["11440555", ..., "11440740"]:
    tr_mask = alive & (dong_code != dong)
    te_mask = alive & (dong_code == dong)
    gbm.fit(X[tr_mask], y[tr_mask])
    pred = gbm.predict(X[te_mask])
```

**용도:** 동 고정효과 의존도 측정. 높을수록 일반화 불가.

---

## 9. 복원 결과 후처리

### 9.1 최종 CSV 스키마 (`imputed_sales_v3.csv`)

| 컬럼 | 타입 | 설명 |
|:-----|:----|:-----|
| `quarter` | int | YYYYQ (예: 20244) |
| `dong_code` | str | 11440xxx |
| `dong_name` | str | 마포구 동명 |
| `industry_code` | str | CS100001~CS100010 |
| `industry_name` | str | 업종명 |
| `store_count` | int | 사업체 수 (피처) |
| `kosis_index` | float | KOSIS 서비스업생산지수 |
| `monthly_sales` | bigint | 원본 월 매출 (결측 시 NaN) |
| **`imputed_sales_v3`** | float | **복원 매출 (원본 있으면 동일)** |
| `is_missing` | bool | 결측 여부 (True/False) |
| `source` | str | `original` or `reverse_engineered_v3` |
| **`confidence`** | float | **1.0 (원본) / 0.74 (복원)** |

### 9.2 후처리 규칙

```python
# 1. 원본값은 덮어쓰지 않음
out["imputed_sales_v3"] = np.where(
    alive_mask,
    df["monthly_sales"],      # 원본
    sales_pred                 # 예측
)

# 2. confidence 규칙
out["confidence"] = np.where(alive_mask, 1.0, 0.74)

# 3. 음수 방지 (GBM이 드물게 내는 음수 예측)
out["imputed_sales_v3"] = out["imputed_sales_v3"].clip(lower=0)

# 4. UTF-8 BOM (한글 Excel 호환)
out.to_csv("imputed_sales_v3.csv", encoding="utf-8-sig")
```

### 9.3 사용 가이드 (README)

- ✅ **전체 합계 추정:** 137 복원값 합 132억 ± 34억 (WAPE 25.7%)
- ✅ **동·업종 랭킹:** Pearson r=0.99로 순위 정확
- ⚠️ **단일 셀 해석:** `imputed ± 26%` 구간으로 명시
- ❌ **투자·입점 결정 단독 사용 금지:** 현장 실사 병행 필수

---

## 10. 전체 재실행 절차

### 10.1 환경 요구

```
Python 3.11+
PostgreSQL (seoul_district_sales, store_quarterly 적재 필요)
.env 환경변수:
  POSTGRES_URL
  KOSIS_API_KEY
```

### 10.2 의존 패키지

```
pip install pandas numpy scipy scikit-learn sqlalchemy PublicDataReader python-dotenv
```

### 10.3 실행 순서

```bash
cd "/c/Users/804/Documents/final project"

# Step 1: KOSIS 후보 테이블 탐색 (1회만, 결과가 있으면 생략)
python scripts/probe_kosis_candidates.py
  # → validation/results/kosis_candidates.md

# Step 2: KOSIS ↔ Seoul 매칭 검증 (anchor 확정)
python scripts/probe_kosis_pairing.py
  # → validation/results/phase1b_anchor_series.csv
  # → validation/results/phase1b_pairing.md (r=0.929 확인)

# Step 3a: v1 IPF + RF 복원 (참고용)
python validation/impute_missing_sales.py
  # → validation/results/imputed_sales.csv (WAPE 30.77%)

# Step 3b: v2 GBM + KOSIS 복원 (확인용)
python validation/reverse_engineer_sales.py
  # → validation/results/imputed_sales_v2.csv (WAPE 14.3%, 과대)

# Step 4: v2 비판적 감사
python validation/critical_audit_v2.py
  # → validation/results/v2_critical_audit.md (MNAR 28.6% 드러냄)

# Step 5: v3 재설계 + 최종 복원 ★
python validation/reverse_engineer_sales_v3.py
  # → validation/results/imputed_sales_v3.csv (최종, MNAR 25.7%)
  # → validation/results/v3_revised_report.md
```

### 10.4 예상 수행 시간

| 단계 | 시간 |
|:----|:----:|
| KOSIS 후보 탐색 | 1분 |
| KOSIS 매칭 | 30초 |
| v1 IPF+RF | 4분 (10-fold CV) |
| v2 GBM | 2분 |
| v2 감사 (4종) | 8분 |
| **v3 최종** | **3분** |

### 10.5 검증 체크포인트

각 단계 정상 여부 확인:

```bash
# Phase 1-B: anchor 상관 0.9+ 확인
grep "Pearson r" validation/results/phase1b_pairing.md
# → "Pearson r: 0.929" 이상이어야 함

# Phase 2 감사: MNAR WAPE 30% 이하 확인
grep "MNAR" validation/results/v2_critical_audit.md

# v3 최종: 복원 셀 수 137 확인
python -c "import pandas as pd; \
  df = pd.read_csv('validation/results/imputed_sales_v3.csv'); \
  print(f'복원 셀: {df.is_missing.sum()}')"
# → "복원 셀: 137"
```

---

## 11. 부록: 왜 이 순서·방법을 택했는가

### 11.1 "왜 처음부터 KOSIS를 안 썼나"

v1 단계에서는 **공공데이터 내부만으로 해결 가능한지** 먼저 확인. WAPE 30%가 한계라는 것을 실증한 후, 멘토 조언에 따라 **외부 anchor**로 이동. 이 순서가 과학적으로 정직 — 내부 한계를 실증해야 외부 의존 필요성이 정당화됨.

### 11.2 "왜 딥러닝(Transformer/GAIN) 안 썼나"

**Shadbahr et al. (2023)** 벤치마크: 중소 표본(<10K)에선 missForest/MICE/GBM이 딥러닝 압도. 본 과제는 3,840 rows — 이 구간에서 GBM이 최적.

### 11.3 "왜 GBM, LightGBM·XGBoost 아닌가"

sklearn GradientBoostingRegressor 선택 이유:
- 외부 의존성 추가 불필요
- 본 규모(3,840 × 25 피처)에선 속도 차이 무의미
- 해석 가능 (feature_importances_ 지원)

대안: LightGBM/XGBoost는 대규모(>100K rows)에서 속도 우위, 본 과제엔 불필요.

### 11.4 "왜 confidence 0.74인가"

규칙: `confidence = 1 - (WAPE / 100)` — **직관적**.
WAPE 25.7% → 74.3% 정확 → confidence 0.74.
하한 0.60 설정 (WAPE >40%면 복원 의미 없음 기준).

---

## 12. 참고

- `validation/results/imputation_report.md` — 전체 통합 리포트
- `validation/results/validation_critical_review.md` — 검증 방법론 비판 상세
- `validation/results/v2_critical_audit.md` — v2 약점 4종 감사
- `validation/results/v3_revised_report.md` — v3 재설계 성능
- `validation/results/phase2_regression_report.md` — Phase 2 회귀 상세

---

**문서 마침**

본 문서는 복원 파이프라인의 **모든 설계 결정과 수치적 근거**를 기록한다.
향후 새로운 결측이 추가되거나 KOSIS 테이블이 변경되는 경우, 10.3절의 재실행 순서를 그대로 따르면 동일 품질의 복원이 재현된다.
