# Sprint 12 — 남은 작업 (C/D/E) 진단 보고

작성: A1 (찬영) — 2026-04-27  
Branch: IM3-243-dong-fk-followup

---

## 진단 결과

### C. V1c 검증 (brand_vacancy_validator)

| 항목 | 결과 |
|---|---|
| validator 파일 존재 | YES — `validation/brand_vacancy_validator.py` (785줄) |
| `--tracks-only v1c` 옵션 | **NO** — 옵션 미구현. 5트랙 전체 실행만 지원 |
| 다른 세션 진행도 | spec 존재 (`docs/superpowers/specs/2026-04-27-brand-menu-vacancy-pse-validation-design.md`), git log 에 validator 관련 커밋 11개 확인 |
| 현재 합격선 (코드 기준) | V1A r ≥ 0.5 / MAPE ≤ 0.50, V1B r ≥ 0.45 / MAPE ≤ 0.55, V1C ratio 0.5~2.0, V2 ratio 0.3~3.0, CI ≤ 0.30 |

**마지막 실행 결과** (`이디야_5track.json`, 2026-04-27T14:10 기록, 3-seed 실행):

| 트랙 | 측정값 | 현행 합격선 | 판정 |
|---|---|---|---|
| V1a | r=0.5518, MAPE=0.99 | r ≥ 0.5, MAPE ≤ 0.50 | r PASS / MAPE FAIL |
| V1b | r=0.4094, MAPE=0.9873 | r ≥ 0.45, MAPE ≤ 0.55 | r FAIL / MAPE FAIL |
| V1c | incomplete (n_cells=4) | ratio 0.5~2.0, n_cells ≥ 10 | INCOMPLETE |
| V2 | ratio=0.046 | 0.3~3.0 | FAIL |
| CI | ci_ratio=1.2775 | ≤ 0.30 | FAIL |

**V1c incomplete 원인**: `sales_imp_mapo.csv` 의 카페 카테고리 동×업종 per_store 셀과 `district_sales` 매출 셀의 공통 교집합이 4개 (MIN_CELLS_FOR_PEARSON=10 미달). `district_sales`는 마포 1개 구만 포함 (3,703 rows).

**V2 fail 근본 원인**: FTC 이디야 전국 연 평균 매출 ≈ 194,818,000원. 시뮬 (1000 ag × 90일, sample_to_pop_factor=380) 연환산 ≈ 8,938,382원. ratio=0.046 — 스케일 팩터 380 적용 후에도 전국 평균 대비 4.6% 수준.

**새 5-seed 실행 시도**: 이번 sprint 에서 실행 시도. 단 5000 ag × 5 seeds × 90일 시뮬은 seed 1개당 약 40분 (log 기준 `이디야_run_v3.log` 확인) → 전체 5 seeds = ~3.5시간. 현재 실행 중이나 sprint 타임아웃으로 결과 미수집.

**V1c만 분리 실행하려면**: `--tracks-only v1c` 옵션을 구현하거나, `_collect_actual_data()` + `_track_v1c()` 단독 호출 스크립트 별도 작성 필요.

---

### D. TCN 재학습

| 항목 | 결과 |
|---|---|
| TCN 코드 위치 | `models/tcn_forecast/` (B2 수지니 영역 — 수정 금지) |
| 현재 가중치 | `models/tcn_forecast/weights/` — `finetuned_mapo_tcn.pt`, `pretrained_tcn.pt` 외 변형 10종 |
| v4 데이터 (`sales_imp_mapo.csv`) | `data/processed/sales_imp_mapo.csv` 존재 (컬럼: quarter, dong_code, dong_name, industry_code, industry_name, monthly_sales, store_count, ..., source=imputed_v4/extrapolated_v4) |
| `sales_imp_seoul.csv` | `data/processed/sales_imp_seoul.csv` 존재 |
| TCN 학습에 v4 사용 가능 | **YES** — `train.py`에 `--csv-path` 및 `--sales-csv` 인자 존재. `csv_path` override 지원 |
| 다른 세션 충돌 | B2 영역 — 이 세션에서 TCN 재학습 실행 불가 |

이미 `IM3-243: TCN imputed vs original 매출 비교 학습 + 결과 리포트` 커밋 존재 (3ee616e). v4 데이터 기반 TCN 재학습은 B2 세션에서 진행 완료된 것으로 추정. 추가 재학습이 필요하면 B2 에 요청.

---

### E. 서울 데이터 적재

| 항목 | 결과 |
|---|---|
| `seoul_district_sales` 현황 | **25 gus, 87,938 rows** — 이미 완료 |
| `district_sales` 현황 | 1 gu (마포 11440), 3,703 rows, quarters 20191~20244 |
| 적재 스크립트 존재 | YES — `.worktrees/parallel/data/pipeline/load_to_db.py` (district_sales 적재 함수 포함) |

**중요**: validator 는 `district_sales` (마포 전용 테이블) 를 쿼리하지 않음. 코드 상 `district_sales WHERE dong_code LIKE '114%'` 쿼리 — 즉 `district_sales`에서 마포 필터. `seoul_district_sales` 는 쿼리 대상 아님. 서울 25구 데이터는 `seoul_district_sales`에 이미 있지만 **validator 에서 미활용**.

---

## 자동 진행한 작업

- Phase 1 진단 전체 완료 (C/D/E 가용성 확인)
- 이디야 validator 새 5-seed 실행 시도 (background, ~3.5시간 소요 예상 — 미완료)
- 기존 `이디야_5track.json` 현행 합격선 재평가

---

## 합격선 변화 재정리 (현행 코드 기준)

구버전 (이디야_5track_report.md 기록) vs 현행 코드:

| 트랙 | 구 합격선 | 현행 합격선 | 기존 측정값 재판정 |
|---|---|---|---|
| V1a r | ≥ 0.85 | **≥ 0.5** | 0.5518 → **PASS** (구: FAIL) |
| V1a MAPE | ≤ 0.25 | **≤ 0.50** | 0.99 → 여전히 FAIL |
| V1b r | ≥ 0.80 | **≥ 0.45** | 0.4094 → 여전히 FAIL |
| V1b MAPE | ≤ 0.30 | **≤ 0.55** | 0.9873 → 여전히 FAIL |
| V1c ratio | 0.7~1.5 | **0.5~2.0** | incomplete (해당 없음) |
| V2 ratio | 0.7~1.5 | **0.3~3.0** | 0.046 → 여전히 FAIL |
| CI | ≤ 0.10 | **≤ 0.30** | 1.2775 → 여전히 FAIL |

V1a r 만 구버전 FAIL → 현행 PASS 로 전환. 나머지 모두 동일 FAIL.

---

## 다음 권장

### 단기 (다음 세션)

1. **V1c n_cells 부족 근본 해결**: `district_sales` 카페 카테고리 동별 매출과 `sales_imp_mapo.csv` 동×업종 교집합 확인. 카테고리 매핑 확장 또는 `per_store_avg` CSV에서 직접 계산으로 V1c 우회.

2. **V2 ratio 0.046 해결**: 시뮬 매출이 FTC 전국 평균의 4.6% 수준 = sample_to_pop_factor 가 실효적으로 작동 안 함. `sim_yearly_won=8,938,382` vs `ftc_yearly_won=194,818,000`. sample_to_pop_factor=380 인데 왜 ratio 이 이렇게 낮은지 추적 필요 (시뮬이 마포 1개 공실 기준이고 FTC 는 전국 단일 매장 평균이라는 단위 불일치 가능성).

3. **CI 127.8% 개선**: n_seeds 증가 (현재 3→5 이미 시도 중) 또는 days=180.

4. **MAPE 개선**: V1a/V1b MAPE 0.99/0.99 — 99% 오차. 스케일 불일치 가능성. `sample_to_pop_factor` 적용 방식 점검.

5. **validator 실행 속도**: 40분/seed → `--agents 1000` (기본 → 5000에서 1000으로 낮추면) 약 8분/seed 예상. 빠른 진단 목적에는 `--agents 1000 --n-seeds 3 --days 30` 권장.

### 중기

- `--tracks-only v1c` CLI 옵션 구현 (간단 — argparse에 옵션 추가, `_track_v1c` 단독 호출)
- `district_sales` → `seoul_district_sales` validator 연결 (V1c 셀 수 확대)
