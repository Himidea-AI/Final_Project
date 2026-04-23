# seoul_district_sales 결측값 역추적 프로젝트

**기간:** 2026-04-22 ~ 2026-04-23
**작업자:** 찬영 (A1) + Claude Code
**대상:** 공공데이터포털 행정동·업종별 추정매출 3.6% 결측 (137개 조합) 복원
**최종 결과:** WAPE 25.7% (MNAR 기준, 정직 평가) / confidence 0.74

---

## 📌 프로젝트 한 줄 요약

공공데이터포털 마포구 동×업종×분기 매출 데이터의 137개 결측을 **KOSIS 통계청 anchor + 자체 회귀 로직**으로 역추적 복원. 순진한 IPF+RF 방식(WAPE 30.8%)에서 멘토 조언을 반영한 리버스 엔지니어링(WAPE 14.3% 낙관, 25.7% 정직)으로 진화시킨 전 과정의 결과·비판·개선 기록.

---

## 📁 문서 인덱스 (읽는 순서 권장)

### 🎯 시작하려면 먼저 읽을 것
1. **`imputation_report.md`** — ⭐ **마스터 통합 리포트** (442줄). 전체 프로젝트 요약·v1/v2/v3 비교·8개 평가지표 해설
2. **`restoration_process_detailed.md`** — ⭐ **복원 과정 재현 가이드** (680줄). 입력·피처·학습·예측 전 단계 수식·코드 포함

### 📊 단계별 상세 (프로젝트 타임라인 순)
| # | 문서 | 내용 |
|:--:|:-----|:-----|
| 1 | `kosis_candidates.md` | **Phase 1-A** KOSIS 100개 테이블 후보 점수화 |
| 2 | `phase1b_pairing.md` | **Phase 1-B** KOSIS ↔ 마포 매출 상관 검증 (r=0.929) |
| 3 | `phase2_regression_report.md` | **Phase 2** GBM 회귀 상세 (WAPE 14.3%) |
| 4 | `v2_critical_audit.md` | **v2 비판 감사** 4종 (시계열/MNAR/LODO/Scale) |
| 5 | `v3_revised_report.md` | **v3 재설계** (sales_per_store target, dong dummy 제거) |
| 6 | `validation_critical_review.md` | **검증 방법론 재평가** (정직한 WAPE 25.7%) |
| 7 | `store_quarterly_audit.md` | **입력 데이터 감사** (서울 상권분석 크롤 교차 검증) |

---

## 🔄 전체 작업 흐름도

```
[ Phase 0 ] 문제 파악
  ├─ 공무원 회신: "통계청과 비교해서 품질 게이트 통과 못하면 배포 안 함"
  └─ 살아있는 96.4%로 3.6% 결측 복원 가능성 탐색
            ↓
[ Phase 1 ] IPF + RF (v1) — 순진 접근
  ├─ Lewis(1982) + IPF SAE 논문으로 기준 수립
  ├─ 3차원 IPF + RandomForest 앙상블
  └─ 결과: WAPE 30.77%, 🥉 Marginal
            ↓
  💡 멘토 조언: "통계청 원천을 확보해 변환 로직을 AI로 역추적하라"
            ↓
[ Phase 2 ] KOSIS 리버스 엔지니어링 (v2)
  ├─ Phase 1-A: KOSIS 100개 테이블 점수화 → DT_1KC2023 선정
  ├─ Phase 1-B: 24분기 상관 검증 → r=0.929 확인 ✅
  ├─ Phase 2:   store_quarterly + KOSIS + 36 feature → GBM 회귀
  └─ 결과: WAPE 14.30% 🥇 (Target Achieved)  ← 당시 낙관적 판정
            ↓
[ Phase 3 ] 비판적 감사 (findings)
  ├─ A. Time-Series CV → 17.5% (시계열 누수 소폭)
  ├─ B. MNAR-Mimic     → 28.6% (결측 셀 실제 상황)
  ├─ C. LODO           → 41.0% (dong fixed effect 과의존)
  └─ D. Q1 작은 셀      → 27.7% (결측 프로파일 취약)
            ↓
  🚨 깨달음: "WAPE 14.3%는 과대평가. 실제 137 결측 복원은 ~28%"
            ↓
[ Phase 4 ] v3 재설계
  ├─ Target: log(sales) → log(sales_per_store) (규모 효과 제거)
  ├─ Dong one-hot 제거 → 동 레벨 통계 feature로 대체
  ├─ 주 판정 지표: Random CV → MNAR-Mimic CV
  └─ 결과: MNAR WAPE 25.7%, 🥉 Inaccurate (정직한 한계)
            ↓
[ Phase 5 ] 입력 데이터 감사 (store_quarterly)
  ├─ 내부 정합성 ✅
  ├─ seoul_district_stores 교차 일치 ✅
  ├─ 서울 상권분석 크롤(golmok) 24분기 비율 68.7~69.6% ✅
  └─ 결론: 입력 신뢰도 높음, 추가 조정 불필요
```

---

## 📈 버전별 성능 비교

| 버전 | 접근법 | Random CV WAPE | MNAR WAPE | R² | Pearson r | 판정 |
|:----|:------|:--:|:--:|:--:|:--:|:-----|
| v1 | IPF + RandomForest 앙상블 | 30.77% | — | 0.847 | 0.981 | 🥉 Marginal |
| v2 | GBM + KOSIS anchor | **14.30%** | 28.6% (감사 발견) | 0.981 | 0.991 | 🥇 (낙관) |
| **v3** | GBM + sales_per_store + stats feature | 17.8% | **25.7%** | 0.967 | 0.985 | 🥉 **정직한 최종** |

---

## 🎓 핵심 교훈

### 1. "좋은 수치"를 의심하라
Random 10-fold CV WAPE 14.3%는 데이터 분할이 실제 사용 상황(MNAR)을 반영하지 못해 **과대평가**. 본 과제의 경우 MNAR-Mimic CV가 진짜 성능.

### 2. 검증 설계 체크리스트
- CV 분할이 실제 상황을 모방하는가? (시계열 → Time-series CV, 결측 복원 → MNAR-mimic)
- 평균 지표가 주요 하위 그룹을 가리지 않는가? (셀 크기·지역 층화)
- Fixed effect가 일반화를 가장하지 않는가? (Leave-one-group-out)
- "과제의 실제 난이도"를 반영한 기준인가? (작은 셀 복원은 구조적으로 20~30% WAPE)

### 3. 외부 anchor 활용
v1은 "살아있는 셀만으로" closed-loop → WAPE 30%가 한계. v2부터 **통계청 KOSIS 원천 anchor** 추가로 구조적 개선. 공공데이터 결측 복원은 **원천 데이터 access가 결정적**.

### 4. 작은 셀의 구조적 한계
결측 137개는 평균 사업체 7개·월 매출 1억원 이하의 작은 셀. 이 규모에선 **개별 업소 노이즈 > 통계 신호**. 공공데이터 품질 게이트가 애초에 이들을 걸러낸 이유와 동일.

---

## 🔧 재현 방법

### 환경
```
Python 3.11+, PostgreSQL
.env: POSTGRES_URL, KOSIS_API_KEY
pip install pandas numpy scipy scikit-learn sqlalchemy PublicDataReader python-dotenv
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
# → validation/results/imputed_sales.csv, docs/sales-imputation/imputation_report.md

# 4. v2 GBM + KOSIS
python validation/reverse_engineer_sales.py
# → validation/results/imputed_sales_v2.csv, docs/sales-imputation/phase2_regression_report.md

# 5. v2 비판적 감사
python validation/critical_audit_v2.py
# → docs/sales-imputation/v2_critical_audit.md

# 6. v3 재설계 (최종)
python validation/reverse_engineer_sales_v3.py
# → validation/results/imputed_sales_v3.csv, docs/sales-imputation/v3_revised_report.md
```

---

## 📦 산출물 인벤토리

### 복원 데이터 (`validation/results/`)
- `imputed_sales.csv` — v1 (WAPE 30.77%)
- `imputed_sales_v2.csv` — v2 (WAPE 14.3% 낙관)
- **`imputed_sales_v3.csv`** — **v3 최종 (MNAR 25.7%, confidence 0.74)**
- `phase1b_anchor_series.csv` — 24분기 KOSIS × 마포 매출 (anchor)

### 파이프라인 스크립트
- `scripts/probe_kosis_candidates.py`
- `scripts/probe_kosis_pairing.py`
- `validation/impute_missing_sales.py` (v1)
- `validation/reverse_engineer_sales.py` (v2)
- `validation/critical_audit_v2.py` (감사)
- `validation/reverse_engineer_sales_v3.py` (v3 최종)

### 문서 (`docs/sales-imputation/`)
- 본 `README.md` (인덱스)
- `imputation_report.md` (마스터 리포트)
- `restoration_process_detailed.md` (재현 가이드)
- 단계별 상세 7개 (위 문서 인덱스 표 참조)

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

### 고전
9. Lewis (1982) — MAPE 4단계 스케일 원조
10. Simpson & Tranmer (2005) — IPF SAE 표준 알고리즘
