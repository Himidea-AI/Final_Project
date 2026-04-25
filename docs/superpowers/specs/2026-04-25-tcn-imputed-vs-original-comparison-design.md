# TCN Imputed vs Original 매출 비교 학습 — Design

**작성일:** 2026-04-25
**브랜치:** IM3-243-dong-fk-followup (또는 별도 feature 브랜치 분기 권장)
**작성자:** A1 (찬영)

---

## 1. 목표

동일한 TCN 구조·피처·하이퍼파라미터·시드를 유지한 채 **매출(`monthly_sales`) 입력 데이터만** 바꿔 두 가지 새 가중치를 학습하고, 기존 가중치까지 합쳐 **3개 모델**의 2024년 백테스트 결과를 비교한다.

| 모델 | Pretrain (서울) 입력 매출 | Finetune (마포) 입력 매출 |
|---|---|---|
| **Original** | 기존 RDS `seoul_district_sales` (실측+결측 + Hot Deck) | 기존 RDS `district_sales` (마포, Hot Deck) |
| **TCN-A (Imputed Finetune Only)** | 기존 그대로 (가중치 재사용) | `imputed_mapo_full_v3.csv` (마포 전체 셀 v3 예측값) |
| **TCN-B (Full Imputed)** | `imputed_seoul_sales_63ind.csv` (서울 전체 v3 예측) | `imputed_mapo_full_v3.csv` |

**비교 가설:** 매출 결측을 v3 imputation으로 채워서 학습하면 백테스트 MAPE/R²가 의미 있게 개선되는가? Pretrain까지 포함해 풀 imputed로 가야 효과가 극대화되는가?

---

## 2. 데이터 소스 교체 메커니즘

핵심 제약: 기존 학습 코드(`models/lstm_forecast/data_prep.py`, `models/tcn_forecast/train.py`)를 최소 침습적으로 변경한다. 매출 소스만 swap 가능한 분기를 추가한다.

### 2.1 `load_sales_data()` 분기

`models/lstm_forecast/data_prep.py:120` `load_sales_data()` 시그니처에 **`sales_csv_override: str | Path | None = None`** 인자를 추가한다.

- `sales_csv_override=None` (기본): 기존 동작 유지 (DB → CSV fallback)
- `sales_csv_override=<path>`: 해당 CSV를 매출 소스로 사용. 컬럼 매핑은 기존 `_SALES_COL_MAP`과 동일(이미 imputed CSV가 같은 스키마로 산출되었는지 확인 필요 — 다르면 어댑터 함수 추가)

### 2.2 환경변수 / CLI 플래그 노출

- `models/tcn_forecast/train.py`에 `--sales-csv` CLI 인자 추가 → `prepare_dataloaders()` config에 `sales_csv_override` 키로 전달
- `prepare_dataloaders()` 시그니처도 동일 키 패스스루
- `validation/experiments/tcn/backtest_tcn.py`는 **백테스트 시 매출 소스를 바꾸지 않는다** — 백테스트의 "실제 매출"은 항상 RDS의 실측이어야 공정 비교 가능

### 2.3 컬럼 호환성 사전 확인 (Phase 0)

`imputed_mapo_full_v3.csv`, `imputed_seoul_sales_63ind.csv`의 헤더가 `_SALES_COL_MAP` 키들과 일치하는지 검증한다. 다를 경우 두 가지 옵션:
- (a) `_SALES_COL_MAP` 확장
- (b) imputed CSV → district_sales 스키마로 변환하는 헬퍼 추가 (`scripts/imputed_to_sales_schema.py` 권장)

이 단계는 학습 들어가기 전 1회 실행하고 결과를 확인한다.

---

## 3. 가중치/결과 파일 네이밍

`--save-suffix` 메커니즘이 이미 존재하므로 그대로 사용한다.

| Suffix | Pretrain 가중치 | Finetune 가중치 | Backtest CSV |
|---|---|---|---|
| (없음) | `pretrained_tcn.pt` (기존, 변경 없음) | `finetuned_mapo_tcn.pt` (기존) | `tcn_backtest_results.csv` |
| `imp_a` | (재사용: `pretrained_tcn_seed2026.pt`) | `finetuned_mapo_tcn_imp_a.pt` | `tcn_backtest_results_imp_a.csv` |
| `imp_b` | `pretrained_tcn_imp_b.pt` | `finetuned_mapo_tcn_imp_b.pt` | `tcn_backtest_results_imp_b.csv` |

스케일러도 자동으로 동일 suffix 따라간다 (`pretrain_tcn_scalers_imp_b.pkl`, `finetune_tcn_scalers_imp_a.pkl` 등).

**시드는 `seed=2026`로 고정** — 매출 차이의 효과만 분리하기 위해. 추후 시드 평균이 필요하면 별도 작업으로 확장.

---

## 4. 실행 파이프라인

### Phase 0 — 컬럼 호환성 검증 (5분)
```bash
python -c "import pandas as pd; print(pd.read_csv('validation/results/imputed_mapo_full_v3.csv', nrows=2).columns.tolist())"
python -c "import pandas as pd; print(pd.read_csv('validation/results/imputed_seoul_sales_63ind.csv', nrows=2).columns.tolist())"
```
필요 시 어댑터 스크립트 작성 후 통일된 형식의 CSV 산출 (`data/processed/sales_imp_mapo.csv`, `data/processed/sales_imp_seoul.csv`).

### Phase 1 — 동시 실행 (병렬, 백그라운드)
```bash
# A.finetune (기존 pretrain 가중치 + 마포 imputed)
python -m models.tcn_forecast.train --mode finetune \
  --sales-csv data/processed/sales_imp_mapo.csv \
  --train-cutoff-quarter 20241 \
  --save-suffix imp_a --seed 2026

# B.pretrain (서울 imputed)
python -m models.tcn_forecast.train --mode pretrain \
  --sales-csv data/processed/sales_imp_seoul.csv \
  --train-cutoff-quarter 20241 \
  --save-suffix imp_b --seed 2026
```

### Phase 2 — B.finetune (B.pretrain 완료 후)
```bash
python -m models.tcn_forecast.train --mode finetune \
  --sales-csv data/processed/sales_imp_mapo.csv \
  --save-suffix imp_b --seed 2026
```

### Phase 3 — 동시 백테스트 (병렬)
```bash
python -m validation.experiments.tcn.backtest_tcn --year 2024                          # Original 재실행
python -m validation.experiments.tcn.backtest_tcn --year 2024 --weights-suffix imp_a   # A
python -m validation.experiments.tcn.backtest_tcn --year 2024 --weights-suffix imp_b   # B
```

### Phase 4 — 비교 리포트 생성
신규 스크립트 `validation/experiments/tcn/compare_imputed.py`:
- 3개 결과 CSV 로드
- 전체 MAPE/MAE/RMSE/R² 비교 표
- 동별 MAPE 비교 표 (Original vs A vs B)
- 업종별 MAPE 비교 표
- 마크다운 리포트 출력 → `docs/abm-simulation/tcn-imputed-comparison-report.md`

---

## 5. 변경/신규 파일 목록

| 파일 | 변경 유형 | 작업 |
|---|---|---|
| `models/lstm_forecast/data_prep.py` | 수정 | `load_sales_data()`에 `sales_csv_override` 인자 + `train_cutoff_quarter`(예: 20241) 인자 추가, `prepare_dataloaders()` config 패스스루 |
| `models/tcn_forecast/train.py` | 수정 | `--sales-csv`, `--train-cutoff-quarter` CLI 인자 추가 (TCN-A/B 모두 `20241`로 호출) |
| `scripts/imputed_to_sales_schema.py` | 신규(필요시) | imputed CSV → district_sales 스키마 어댑터 |
| `validation/experiments/tcn/compare_imputed.py` | 신규 | 3개 백테스트 결과 비교 리포트 생성 |
| `data/processed/sales_imp_mapo.csv` | 신규(데이터) | Phase 0 산출물 |
| `data/processed/sales_imp_seoul.csv` | 신규(데이터) | Phase 0 산출물 |
| `models/tcn_forecast/weights/finetuned_mapo_tcn_imp_a.pt` 외 | 신규(산출) | 학습 결과 |
| `validation/results/tcn_backtest_results_imp_a.csv` 외 | 신규(산출) | 백테스트 결과 |
| `docs/abm-simulation/tcn-imputed-comparison-report.md` | 신규 | 최종 리포트 |

**담당 영역 주의:** 본인 담당은 `backend/src/database/`, `services/`, `data/`. 본 작업은 `models/`, `validation/` 영역에 닿으므로 PR 시 B2(수지니, TCN 담당) 리뷰 필요. data_prep과 train.py 변경은 기존 동작과 100% 하위 호환(default None) 유지.

---

## 6. 평가 지표 / 성공 기준

| 지표 | 비교 단위 | 표기 |
|---|---|---|
| 전체 MAPE / MAE / RMSE / R² | 마포 2024 전체 (EXCLUDE_COMBOS 제거 후) | 표 + 막대그래프(선택) |
| 동별 MAPE | 16개 행정동 | 표 |
| 업종별 MAPE | 마포에 존재하는 업종 | 표 |
| 학습 시간 | Pretrain/Finetune 각각 wall-clock | 표 |

**성공 기준:** 수치 비교만 정확히 산출되면 성공. 가설 검증(개선 여부)은 결과 해석 단계에서 별도 판단.

---

## 7. 위험·주의사항

1. **Imputed CSV 스키마 미스매치** — Phase 0에서 컬럼명/수가 RDS와 다를 가능성 큼. 어댑터 작업 시간 추가 발생 가능.
2. **자원 경합** — Phase 1 병렬 실행 시 CPU/RAM 압박. 16GB RAM 미만이면 순차 실행 권장.
3. **데이터 누수** — imputed v3는 2019~2024 전 기간을 한 번에 imputation한 결과물. 이걸 그대로 학습 입력에 넣으면 백테스트 평가 연도(2024)의 정보가 학습에 포함됨 → **데이터 누수**. 채택 방어책: data_prep에 `train_cutoff_quarter` 인자 추가 후 `< 20241` 필터링 (Sec 5 변경 파일 목록·Sec 4 명령어에 반영). 추가 보강이 필요하면 imputed CSV를 2024 이전으로 재산출 후 교체.
4. **시드 의존성** — 단일 시드 비교는 random variance에 취약. 결과 해석 시 "시드 1개 비교" 한계를 명시. 추후 시드 6개로 확장 시 별도 작업.
5. **EXCLUDE_COMBOS 일관성** — 3개 모델 모두 동일 EXCLUDE_COMBOS 적용. backtest_tcn.py에 이미 반영되어 있음 — 추가 작업 없음.

---

## 8. 산출물 (Done 정의)

- [ ] Phase 0: imputed CSV 컬럼 호환성 검증 + 필요 시 어댑터 산출
- [ ] Phase 1~2: `finetuned_mapo_tcn_imp_a.pt`, `pretrained_tcn_imp_b.pt`, `finetuned_mapo_tcn_imp_b.pt` 가중치 + 해당 스케일러
- [ ] Phase 3: `tcn_backtest_results.csv` (재실행), `_imp_a.csv`, `_imp_b.csv`
- [ ] Phase 4: `docs/abm-simulation/tcn-imputed-comparison-report.md` 비교 리포트
- [ ] `models/lstm_forecast/data_prep.py`, `models/tcn_forecast/train.py` 수정에 대한 ruff check + format 통과
- [ ] B2 (수지니) 리뷰 요청 (담당 영역)

---
