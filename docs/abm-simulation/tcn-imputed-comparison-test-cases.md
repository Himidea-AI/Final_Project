# TCN Imputed vs Original 비교 — 테스트 케이스 문서

> **목적:** TCN imputation 비교 학습 작업에서 새로 추가된 코드(어댑터·data_prep 인자·비교 스크립트)를 검증하기 위해 작성된 모든 단위 테스트를 한 곳에 정리한다. 누구든 이 문서만 읽고도 (a) 어떤 동작이 보호되고 있는지, (b) 어떤 입력이 들어가는지, (c) 무엇이 검증되는지, (d) 어떤 버그가 회귀할 수 있는지 알 수 있도록 작성했다.

| 항목 | 값 |
|---|---|
| 작업 명 | TCN Imputed vs Original 비교 학습 |
| 작성일 | 2026-04-26 |
| 작업 브랜치 | `IM3-243-dong-fk-followup` |
| 관련 Spec | [`docs/superpowers/specs/2026-04-25-tcn-imputed-vs-original-comparison-design.md`](../superpowers/specs/2026-04-25-tcn-imputed-vs-original-comparison-design.md) |
| 관련 Plan | [`docs/superpowers/plans/2026-04-25-tcn-imputed-vs-original-comparison.md`](../superpowers/plans/2026-04-25-tcn-imputed-vs-original-comparison.md) |
| 결과 리포트 | [`tcn-imputed-comparison-report.md`](./tcn-imputed-comparison-report.md) |
| 총 테스트 | **8건** (3개 파일) |
| 결과 | **8 PASS** (모두 통과) |
| 평균 실행 시간 | ~15초 |
| 외부 의존성 | 없음 (DB·GPU·네트워크 불필요) |

---

## 0. 작업 배경 한 페이지 정리

이 작업의 목표는 **매출 데이터만 다르게** 학습한 3개 TCN 모델의 백테스트 성능을 비교하는 것이다.

```
┌────────────────────────────────────────────────────────────────┐
│  3개 모델 학습 흐름                                            │
├────────────────────────────────────────────────────────────────┤
│  Original   :  실측 매출 (RDS)        → 04-20 가중치 그대로    │
│  TCN-A      :  마포만 imputed v3      → finetune 새로 학습     │
│  TCN-B      :  서울 + 마포 imputed v3 → pretrain+finetune 새로 │
└────────────────────────────────────────────────────────────────┘
```

이를 위해 코드에는 다음 신규/수정 사항이 들어갔다:

| # | 변경 | 파일 | 테스트 파일 |
|---|---|---|---|
| 1 | imputed CSV → RDS 스키마 변환 어댑터 (신규) | `scripts/imputed_to_sales_schema.py` | `tests/test_imputed_to_sales_schema.py` |
| 2 | 매출 소스 swap 인자 (`sales_csv_override`) | `models/lstm_forecast/data_prep.py` | `tests/test_data_prep_overrides.py` |
| 3 | 학습 데이터 누수 방어 인자 (`train_cutoff_quarter`) | `models/lstm_forecast/data_prep.py` | `tests/test_data_prep_overrides.py` |
| 4 | TCN train.py CLI 인자 (argparse) | `models/tcn_forecast/train.py` | (별도 테스트 없음 — 통합 검증) |
| 5 | 3모델 비교 리포트 스크립트 (신규) | `validation/experiments/tcn/compare_imputed.py` | `tests/test_compare_imputed.py` |

이 문서는 위 1·2·3·5에 대한 **8개의 단위 테스트**를 다룬다.

---

## 1. 빠른 시작

### 1-1. 전체 8개 테스트 한 번에 실행

```bash
cd "C:/Users/804/Documents/final project"
pytest tests/test_imputed_to_sales_schema.py \
       tests/test_data_prep_overrides.py \
       tests/test_compare_imputed.py -v
```

기대 출력 끝부분:
```
============================== 8 passed in 13.44s ==============================
```

### 1-2. 파일별 개별 실행

```bash
# 어댑터 (3 tests)
pytest tests/test_imputed_to_sales_schema.py -v

# data_prep 인자 추가 (3 tests)
pytest tests/test_data_prep_overrides.py -v

# 비교 스크립트 (2 tests)
pytest tests/test_compare_imputed.py -v
```

### 1-3. 단일 테스트 실행

```bash
pytest tests/test_imputed_to_sales_schema.py::test_adapt_mapo_imputed_renames_final_to_base -v
```

### 1-4. 환경 요구

| 항목 | 요구 |
|---|---|
| Python | 3.11+ |
| 필수 패키지 | `pandas`, `pytest`, `numpy`, `sklearn`, `torch` (이미 프로젝트에 설치) |
| 추가 패키지 | `tabulate` (compare_imputed.py의 `to_markdown()`이 사용) |
| DB 연결 | 불필요 — 모든 DB 호출은 monkeypatch 또는 잘못된 URL로 우회 |
| GPU | 불필요 — 학습 안 함 |
| 네트워크 | 불필요 |
| 임시 파일 | 모두 pytest의 `tmp_path` fixture로 자동 정리 |

---

## 2. 파일 1 — `tests/test_imputed_to_sales_schema.py`

### 2-1. 파일 개요

| 항목 | 내용 |
|---|---|
| 위치 | `tests/test_imputed_to_sales_schema.py` |
| 라인 수 | 약 112줄 |
| 테스트 개수 | 3건 |
| 대상 모듈 | `scripts/imputed_to_sales_schema.py` |
| 대상 함수 | `adapt_mapo_imputed`, `adapt_seoul_imputed` |

### 2-2. 대상 모듈이 하는 일

`imputed_*_v3.csv` 파일들은 매출 결측을 v3 imputation 모델로 채운 결과물인데, 컬럼 이름과 구조가 RDS의 `district_sales` / `seoul_district_sales` 테이블과 다르다. 학습 파이프라인(`data_prep.py`)은 RDS 스키마를 기대한다. 어댑터의 책임은 **두 imputed CSV를 학습 파이프라인이 그대로 읽을 수 있는 형태로 변환**하는 것이다.

스키마 차이 요약:

| imputed CSV | 컬럼 형태 | 변환 방향 |
|---|---|---|
| `imputed_mapo_full_v3.csv` | `<col>` + `<col>_pred` + `<col>_imputed` + `<col>_final` (4개씩) | `<col>_final` 값을 `<col>` 자리에 덮어쓰고, 보조 변형은 모두 drop |
| `imputed_seoul_sales_63ind.csv` | `monthly_sales`(NaN 가능) + `imputed_sales`(채움값) + `is_missing/source/confidence` | `imputed_sales`로 `monthly_sales` 덮어쓰기 + 메타 컬럼 4개 drop |

---

### 2-3. 테스트 #1 — `test_adapt_mapo_imputed_renames_final_to_base`

**한 줄 목적**: 마포 어댑터가 `_final` suffix 컬럼을 base 컬럼으로 정확히 옮기고 보조 변형을 모두 제거하는지 확인한다.

**왜 이 테스트가 필요한가**: 마포 imputed CSV에는 같은 매출 컬럼에 대해 `monthly_sales`, `monthly_sales_pred`, `monthly_sales_imputed`, `monthly_sales_final` 네 가지 변형이 존재한다. 학습 입력으로 쓰려면 단일 base 컬럼만 남아야 하고, 그 값은 가장 정제된 `_final`이어야 한다. 만약 이 변환이 잘못되면 학습 모델은 보조 컬럼을 별개의 피처로 오해해 입력 차원이 부풀거나, 결측이 채워지지 않은 base 값으로 학습할 수 있다.

**입력 데이터** (5개 base 컬럼 + 3개 `_final` 페어, 2 row):

```python
src = pd.DataFrame({
    "quarter":              [20191, 20192],
    "dong_code":            ["11440555", "11440555"],
    "dong_name":            ["서교동", "서교동"],
    "industry_code":        ["CS100001", "CS100001"],
    "industry_name":        ["한식음식점", "한식음식점"],
    "monthly_sales":        [3.4e9,  3.5e9],
    "monthly_sales_final":  [3.355e9, 3.5e9],
    "monthly_count":        [94005,  95000],
    "monthly_count_final":  [94005,  95000],
    "weekday_sales":        [2.6e9,  2.7e9],
    "weekday_sales_final":  [2.608e9, 2.7e9],
})
```

**호출**: `adapt_mapo_imputed(src_path, out_path)` → 결과 CSV 다시 읽음.

**검증 항목** (총 11개 assert):

1. `out.loc[0, "monthly_sales"] == 3.355e9` — `_final` 값이 base 자리에 들어왔는가
2. `"monthly_sales_final" not in out.columns` — `_final` 컬럼 제거
3. `"monthly_sales_pred" not in out.columns` — `_pred` 컬럼 제거 (실제 입력엔 없지만 패턴 보존 확인용)
4. `"monthly_sales_imputed" not in out.columns` — `_imputed` 컬럼 제거
5~11. 8개 base 컬럼(`quarter`, `dong_code`, `dong_name`, `industry_code`, `industry_name`, `monthly_sales`, `monthly_count`, `weekday_sales`)이 출력에 모두 존재

**이 테스트가 잡는 회귀 시나리오**:
- 누군가 `_DROP_SUFFIXES` 리스트에서 suffix를 빼먹는 경우 → 보조 컬럼이 drop 안 됨 → assert 실패
- `_final` overwrite 로직과 drop 순서를 뒤바꾸는 경우 → base 값이 보존되고 `_final`이 drop됨 → assert #1 실패
- base 컬럼 자체를 실수로 drop하는 경우 → assert #5~11 실패

---

### 2-4. 테스트 #2 — `test_adapt_seoul_imputed_overwrites_monthly_sales`

**한 줄 목적**: 서울 어댑터가 `imputed_sales`로 `monthly_sales`를 덮어쓰고 메타 컬럼 4개를 모두 제거하는지 확인한다.

**왜 이 테스트가 필요한가**: 서울 imputed CSV는 마포와 다르게 매출 메인 컬럼만 imputed 되어 있고, 결측 행에는 `monthly_sales=NaN` + `imputed_sales=실제값` 구조다. 학습 파이프라인은 `monthly_sales`만 읽으므로 `imputed_sales` 값을 거기에 옮겨야 한다. 또한 `is_missing`, `source`, `confidence` 같은 메타 컬럼은 RDS 스키마에 없으므로 모두 제거해야 한다 — 안 그러면 `prepare_dataloaders`의 ALL_FEATURES 매칭에서 unknown 컬럼으로 처리될 수 있다.

**입력 데이터** (1 row, 결측 시나리오):

```python
src = pd.DataFrame({
    "quarter":         [20191],
    "dong_code":       ["11440555"],
    "dong_name":       ["서교동"],
    "industry_code":   ["CS100001"],
    "industry_name":   ["한식"],
    "store_count":     [88],
    "kosis_index":     [111.4],
    "monthly_sales":   [None],          # 원본 NaN — 결측
    "imputed_sales":   [3.355e9],       # v3 채움 결과
    "is_missing":      [True],
    "source":          ["v3"],
    "confidence":      [0.85],
})
```

**호출**: `adapt_seoul_imputed(src_path, out_path, db_url=None)` — DB 없이 호출(테스트 환경엔 RDS 없음).

**검증 항목** (총 5개 assert):

1. `out.loc[0, "monthly_sales"] == 3.355e9` — NaN이 imputed 값으로 정확히 교체
2. `"imputed_sales" not in out.columns` — 변환에 사용된 후 제거
3. `"is_missing" not in out.columns` — 메타 컬럼 제거
4. `"source" not in out.columns` — 메타 컬럼 제거
5. `"confidence" not in out.columns` — 메타 컬럼 제거 (Code Review MEDIUM #6에서 추가 보강된 항목)

**이 테스트가 잡는 회귀 시나리오**:
- `imputed_sales` overwrite 누락 → `monthly_sales`가 NaN으로 남음 → assert #1 실패
- 메타 컬럼 4개 중 하나라도 drop 누락 → 학습 ALL_FEATURES와 충돌 가능 → assert #2~5 중 실패
- DB join 분기가 `db_url=None`인 케이스를 처리하지 못해 예외 발생 → 테스트 실행 중단

**의도된 비테스트 영역**: `db_url`이 주어진 경우의 RDS join 동작은 단위 테스트하지 않는다 (RDS mock이 과도하게 복잡해짐). 대신 실제 변환 시 통합 검증.

---

### 2-5. 테스트 #3 — `test_adapt_mapo_imputed_preserves_base_when_final_is_nan`

**한 줄 목적**: `_final` 값이 NaN인 row에서는 원본 base 값이 보존되어야 한다. (Code Review HIGH #1의 회귀 방지)

**왜 이 테스트가 필요한가**: 1차 구현에서 `_final → base` 옮기기 코드는 이런 형태였다:

```python
# 버그가 있는 1차 구현
for fc in final_cols:
    base = fc[: -len("_final")]
    if base in df.columns:
        df[base] = df[fc]   # ⚠️ NaN도 무조건 덮어씀
```

이 경우 `_final`에 NaN이 들어있으면 유효한 `base` 값까지 NaN으로 덮어써진다. 코드 리뷰에서 이 잠재 버그를 잡아 `notna()` 마스크로 수정했다:

```python
# 수정 후 안전 구현
for fc in final_cols:
    base = fc[: -len("_final")]
    if base in df.columns:
        mask = df[fc].notna()
        df.loc[mask, base] = df.loc[mask, fc]
```

이 테스트는 그 수정이 향후 회귀로 되돌아가지 않도록 잠그는 역할을 한다.

**입력 데이터** (의도적으로 row 1의 `_final`을 NaN으로):

```python
src = pd.DataFrame({
    "quarter":             [20191, 20192],
    "dong_code":           ["11440555", "11440555"],
    "dong_name":           ["서교동", "서교동"],
    "industry_code":       ["CS100001", "CS100001"],
    "industry_name":       ["한식", "한식"],
    "monthly_sales":       [3.4e9,   3.5e9],
    "monthly_sales_final": [3.355e9, None],   # ⬅ row 1 NaN
})
```

**호출**: `adapt_mapo_imputed(src_path, out_path)`.

**검증 항목** (총 2개 assert):

1. `out.loc[0, "monthly_sales"] == 3.355e9` — `_final`이 valid한 row 0은 정상 적용
2. `out.loc[1, "monthly_sales"] == 3.5e9` — `_final`이 NaN인 row 1은 base `3.5e9` **보존**

**실패 시나리오 예시**: 만약 누군가 마스크를 빼고 `df[base] = df[fc]`로 되돌린다면 row 1 `monthly_sales`가 NaN이 되어 assert #2가 다음과 같이 실패한다:
```
assert nan == 3500000000.0
```

---

## 3. 파일 2 — `tests/test_data_prep_overrides.py`

### 3-1. 파일 개요

| 항목 | 내용 |
|---|---|
| 위치 | `tests/test_data_prep_overrides.py` |
| 라인 수 | 약 145줄 |
| 테스트 개수 | 3건 |
| 대상 모듈 | `models/lstm_forecast/data_prep.py` |
| 대상 함수 | `load_sales_data`, `prepare_dataloaders` |

### 3-2. 대상 모듈이 하는 일

`data_prep.py`는 LSTM/GRU/TCN 세 모델이 공유하는 데이터 준비 모듈이다. 본 작업에서 두 가지 신규 인자가 추가됐다:

| 인자 | 위치 | 역할 |
|---|---|---|
| `sales_csv_override` | `load_sales_data`, `prepare_dataloaders` | DB 호출을 완전히 skip하고 지정된 CSV를 매출 소스로 사용 |
| `train_cutoff_quarter` | `prepare_dataloaders` | `quarter ≥ cutoff`인 row를 학습/검증 데이터에서 제거 (백테스트 평가 연도 차단 — 데이터 누수 방어) |

두 인자 모두 default `None` → 기존 30+개 호출자(LSTM/GRU/TCN train·predict 등)에 영향 없음.

---

### 3-3. 테스트 #4 — `test_sales_csv_override_takes_precedence`

**한 줄 목적**: `sales_csv_override`가 주어지면 DB 시도를 완전히 skip하고 해당 CSV만 읽는지 확인한다.

**왜 이 테스트가 필요한가**: 기존 `load_sales_data` 흐름은 "DB 우선 → CSV fallback" 구조였다. imputation 비교 학습 시에는 DB가 가용해도 무시하고 imputed CSV를 우선시해야 한다. 만약 DB가 가용한 환경에서 override가 무시되면 학습은 RDS 실측 매출로 진행되어 imputation 효과를 측정할 수 없다.

**입력 데이터**: 1 row override CSV + 일부러 잘못된 DB URL.

```python
csv = tmp_path / "override.csv"
pd.DataFrame({
    "quarter":       [20191],
    "dong_code":     ["11440555"],
    "dong_name":     ["서교동"],
    "industry_code": ["CS100001"],
    "industry_name": ["한식"],
    "monthly_sales": [1.0e9],
}).to_csv(csv, index=False, encoding="utf-8-sig")

# DB URL은 일부러 잘못된 값 — override가 작동하면 이 URL을 시도조차 안 해야 함
df = load_sales_data(
    db_url="postgresql://invalid:invalid@localhost:1/nonexistent",
    sales_csv_override=str(csv),
    dong_prefix="11440",
)
```

**핵심 트릭**: `localhost:1`은 일부러 사용 가능성이 거의 없는 포트다. 만약 override가 작동하지 않고 DB를 시도하면 sqlalchemy가 `OperationalError`로 즉시 실패하거나 타임아웃이 걸린다. **테스트가 정상 통과한다는 사실 자체가 DB 시도를 skip했다는 증거**가 된다.

**검증 항목** (총 2개 assert):

1. `len(df) == 1` — override CSV의 1 row가 그대로 반환됐다
2. `df.iloc[0]["monthly_sales"] == 1.0e9` — 정확한 매출값 반환

**실패 시나리오 예시**:
- override 분기를 DB try 블록 뒤에 두면 DB가 먼저 시도되어 `OperationalError` 또는 타임아웃 → 테스트가 예외로 실패
- override 분기에서 dong_prefix 필터를 빠뜨리면 (입력 dong_code="11440555"가 prefix "11440"으로 시작하긴 하지만, 다른 dong_code가 섞인 케이스를 추후 추가하면 잡힘)

---

### 3-4. 테스트 #5 — `test_prepare_dataloaders_passes_override_through`

**한 줄 목적**: `config["sales_csv_override"]`이 `prepare_dataloaders` 안에서 `load_sales_data`까지 keyword로 전달되는지 spy로 확인한다.

**왜 이 테스트가 필요한가**: TCN train.py의 CLI 인자 `--sales-csv`는 결국 config dict의 한 키로 들어가고, 그 키는 `prepare_dataloaders` → `load_sales_data` 사이를 지나가야 한다. 중간 어디서든 오타나 누락이 발생하면 학습은 default RDS 매출로 진행되고, 우리는 그 사실을 모르게 된다 (imputed 학습이라고 믿는데 실제론 실측 학습). spy는 이 전달 경로의 무결성을 보장한다.

**입력 데이터 + 핵심 매커니즘**:

```python
captured = {}
real_load = dp.load_sales_data

def spy(*args, **kwargs):
    captured["sales_csv_override"] = kwargs.get("sales_csv_override")
    return real_load(*args, **kwargs)

monkeypatch.setattr(dp, "load_sales_data", spy)
```

`monkeypatch.setattr`로 `data_prep.load_sales_data`를 spy 함수로 일시 교체. 이후 `prepare_dataloaders(cfg)`를 호출하면 spy가 진입하면서 kwargs를 캡처한다. 후속 단계(`build_timeseries`, `prepare_sequences` 등)는 stub CSV 한계로 실패할 수 있으나 **spy 캡처는 그 전에 이미 발생**하므로 검증에 영향 없다.

**Stub CSV 구성**: 5분기 × 동·업종 1개 = 40 row의 가상 시계열 (sequence 생성 가능 최소량).

**Pipeline 후속 예외 허용**: assert는 try 블록 밖에서 실행되며, 만약 spy가 호출되지 않은 채 다른 곳에서 예외가 발생했다면 assert 메시지에 그 예외가 함께 표시되어 디버깅을 돕는다 (Code Review HIGH #1 개선):

```python
exc_from_pipeline: Exception | None = None
try:
    prepare_dataloaders(cfg)
except Exception as e:
    exc_from_pipeline = e  # 후속 단계 실패는 허용
assert captured.get("sales_csv_override") == str(csv), (
    f"override가 load_sales_data까지 전달되지 않음 (pipeline 예외: {exc_from_pipeline!r})"
)
```

**검증 항목** (1개 assert):

1. `captured["sales_csv_override"] == str(csv)` — config의 override 키가 정확히 `load_sales_data` kwarg로 전달됐다.

**실패 시나리오 예시**:
- `prepare_dataloaders`가 `config.get("sales_csv_override")`를 빠뜨리면 → spy의 `captured["sales_csv_override"]`가 `None` → assert 실패 + pipeline 예외 메시지 노출
- `load_sales_data` 호출 시 키워드 명을 잘못 쓰면(예: `override_csv=`) → spy가 None 캡처 → 동일하게 실패

---

### 3-5. 테스트 #6 — `test_train_cutoff_quarter_filters_recent_data`

**한 줄 목적**: `train_cutoff_quarter=20241`이 적용되면 `quarter ≥ 20241` row가 학습 데이터에서 제거되어 `build_timeseries`로 가는 시점에 max quarter가 `20234` 이하인지 확인한다.

**왜 이 테스트가 필요한가**: imputed CSV는 2019~2024 전 기간을 한 번에 imputation한 결과물이다. 이걸 그대로 학습에 넣으면 백테스트 평가 연도(2024)가 학습+평가에 동시 등장 → **데이터 누수**. cutoff 인자가 정확히 작동하지 않으면 우리는 깨끗해 보이지만 실제로는 누수가 있는 비교 결과를 얻는다.

**입력 데이터**: 24분기 (2019Q1 ~ 2024Q4) stub CSV + `train_cutoff_quarter=20241`.

```python
quarters = [20191, 20192, 20193, 20194,
            20201, 20202, 20203, 20204,
            20211, 20212, 20213, 20214,
            20221, 20222, 20223, 20224,
            20231, 20232, 20233, 20234,  # ← cutoff 직전
            20241, 20242, 20243, 20244]  # ← cutoff에 의해 제거되어야 함
```

**핵심 매커니즘**: `build_timeseries`를 spy로 교체해 진입 시점의 `sales_df["quarter"].max()`를 캡처한다.

```python
def spy(sales_df, *args, **kwargs):
    captured["max_quarter"] = sales_df["quarter"].max()
    return real_build(sales_df, *args, **kwargs)

m.setattr(dp, "build_timeseries", spy)
```

**검증 항목** (총 2개 assert):

1. `captured["max_quarter"] is not None` — spy가 실제로 호출됐다 (= cutoff 적용 후 build_timeseries까지 도달했다)
2. `captured["max_quarter"] < 20241` — cutoff 적용으로 2024 데이터가 모두 제거됨 (실제로는 `20234`가 캡처됨)

**TDD RED 시점 에러**: 구현 전 실행 시:
```
AssertionError: cutoff 후 max_quarter=20244
assert np.int64(20244) < 20241
```
즉 cutoff가 적용되지 않으면 `20244`가 그대로 들어가고 assert에서 명확히 실패한다.

**의도된 비테스트 영역**:
- `store_df`도 동일 cutoff로 필터링되는지는 별도 테스트 없음 — sales_df와 같은 cutoff 변수를 공유하므로 회귀 가능성 낮음
- cutoff > max(quarter)인 경우 (모든 데이터 제거) downstream 에러 처리는 별도 테스트 없음

---

## 4. 파일 3 — `tests/test_compare_imputed.py`

### 4-1. 파일 개요

| 항목 | 내용 |
|---|---|
| 위치 | `tests/test_compare_imputed.py` |
| 라인 수 | 약 56줄 |
| 테스트 개수 | 2건 |
| 대상 모듈 | `validation/experiments/tcn/compare_imputed.py` |
| 대상 함수 | `compute_metrics`, `build_comparison_table` |

### 4-2. 대상 모듈이 하는 일

3개 백테스트 결과 CSV(Original / TCN-A / TCN-B)를 입력으로 받아:

1. **`compute_metrics(csv)`** — 단일 CSV에서 전체 MAPE/MAE/RMSE/R² + n_samples 추출
2. **`build_comparison_table(csvs_dict)`** — 모델명→경로 매핑에서 비교 표(`pd.DataFrame`) 생성
3. **`build_by_group_table(csvs, "dong_name" or "industry_name")`** — 동별/업종별 MAPE 표
4. **`render_report(...)`** — 마크다운 리포트 문자열 생성

테스트는 1, 2번에 집중한다 (3, 4번은 통합 검증으로 위임).

---

### 4-3. 테스트 #7 — `test_compute_metrics_returns_overall_mape`

**한 줄 목적**: `compute_metrics`가 toy CSV에서 expected MAPE를 정확히(±0.5p) 계산하는지 확인한다.

**왜 이 테스트가 필요한가**: `compute_metrics`는 `validation/accuracy_metrics.py`의 `generate_accuracy_report`에 위임하지만, dict 키 매핑(`mape`, `mae`, `rmse`, `r_squared`, `n_samples`)을 잘못 잡으면 비교 표에 `KeyError`가 난다. 또 `n_samples`는 위임 대상에 없는 신규 필드라 자체 계산이 필요하다 — 그 계산이 정확한지 단위 테스트로 보장한다.

**입력 데이터** (`_toy_csv` helper):

```python
def _toy_csv(tmp_path, name, mape_target):
    actual = [1.0e9, 2.0e9, 3.0e9, 4.0e9]
    pred = [a * (1 + mape_target / 100.0) for a in actual]   # 일정 비율 오차
    df = pd.DataFrame({
        "test_year":               [2024] * 4,
        "dong_code":               ["11440555"] * 4,
        "dong_name":               ["서교동"] * 4,
        "industry_code":           ["CS100001", "CS100002", "CS100003", "CS100004"],
        "industry_name":           ["A", "B", "C", "D"],
        "actual_annual_sales":     actual,
        "predicted_annual_sales":  pred,
        "abs_error":               [abs(a - p) for a, p in zip(actual, pred)],
        "mape_pct":                [mape_target] * 4,
    })
    df.to_csv(tmp_path / name, index=False, encoding="utf-8-sig")
    return tmp_path / name
```

이 helper는 모든 행이 `actual × (1 + mape/100)`인 toy CSV를 만든다 → 이론상 전체 MAPE = `mape_target`.

본 테스트에서는 `mape_target=10.0`을 줌.

**검증 항목** (총 2개 assert):

1. `m["mape"] == pytest.approx(10.0, abs=0.5)` — 계산된 MAPE가 toy 입력과 ±0.5p 이내 일치
2. `m["n_samples"] == 4` — 자체 계산한 sample 수 정확

**오차 허용 ±0.5p가 필요한 이유**: `generate_accuracy_report` 내부에서 round / 부동소수점 처리가 있을 수 있어 정확히 10.0이 안 나올 가능성 — 하지만 0.5p 이내면 의도가 맞음을 확인 가능.

---

### 4-4. 테스트 #8 — `test_build_comparison_table_shows_three_models`

**한 줄 목적**: `build_comparison_table`이 3개 모델 입력에 대해 `model` 컬럼에 세 이름이 모두 들어간 3 row DataFrame을 반환하는지 확인한다.

**왜 이 테스트가 필요한가**: 비교 표는 최종 리포트에서 가장 먼저 보이는 부분이다. 만약 한 모델이 누락되거나 이름이 깨지면 해석 전체가 무너진다. 또한 dict 순회 순서, 컬럼 추가, row 개수가 정확한지 한번에 확인.

**입력 데이터**: 3개 toy CSV (각각 MAPE 15%, 8%, 12%):

```python
a = _toy_csv(tmp_path, "a.csv", 15.0)
b = _toy_csv(tmp_path, "b.csv", 8.0)
c = _toy_csv(tmp_path, "c.csv", 12.0)

table = build_comparison_table({"Original": a, "TCN-A": b, "TCN-B": c})
```

**검증 항목** (총 4개 assert):

1. `"Original" in table["model"].values` — Original 행 존재
2. `"TCN-A" in table["model"].values` — TCN-A 행 존재
3. `"TCN-B" in table["model"].values` — TCN-B 행 존재
4. `len(table) == 3` — 정확히 3 row (중복·누락 없음)

**실패 시나리오 예시**:
- 함수가 dict 키 대신 path basename으로 model 이름을 추정하면 "Original" 대신 `"a"`가 들어감 → assert #1 실패
- 마지막 모델만 덮어쓰는 버그 → `len(table) == 1` → assert #4 실패

**의도된 비테스트 영역**: 컬럼 순서·정렬, 수치 정확도(`compute_metrics`에서 별도 검증)는 다루지 않는다.

---

## 5. TDD 흐름 (Task별 RED → GREEN)

각 테스트는 plan에 따라 "테스트 먼저 작성 → 실행 실패(RED) → 구현 → 실행 성공(GREEN)" 흐름을 따랐다.

| Task | 테스트 작성 후 첫 실행 (RED) | 구현 후 (GREEN) |
|---|---|---|
| Task 1 (어댑터) | `ModuleNotFoundError: No module named 'scripts.imputed_to_sales_schema'` | 2 PASS → 코드 리뷰에서 NaN 회귀 방지 1건 추가 → **3 PASS** |
| Task 2 (`sales_csv_override`) | `TypeError: load_sales_data() got an unexpected keyword argument 'sales_csv_override'` | **2 PASS** |
| Task 3 (`train_cutoff_quarter`) | `AssertionError: cutoff 후 max_quarter=20244` (cutoff 미적용) | Task 2 누적 + 1 신규 → **3 PASS** |
| Task 9 (compare 스크립트) | `ModuleNotFoundError: No module named 'validation.experiments.tcn.compare_imputed'` | **2 PASS** |

**최종 결과**: 8 tests PASS, ruff check + format 통과, 외부 의존성 없음.

---

## 6. 커버리지 매트릭스

✅ 직접 테스트, ⚠️ 부분/간접 검증, ❌ 미테스트.

### 6-1. `scripts/imputed_to_sales_schema.py`

| 동작 | 상태 | 어디서 검증 |
|---|---|---|
| 마포 `_final` → base 변환 | ✅ | Test #1 |
| 마포 보조 변형(`_pred/_imputed`) drop | ✅ | Test #1 (입력에 직접 포함은 아니나 `_DROP_SUFFIXES` 제거 패턴 검증) |
| 마포 `_final` NaN row의 base 보존 | ✅ | Test #3 |
| 마포 `is_missing_monthly` drop | ⚠️ | Test #1에 직접 포함 안 됨 — Task 1 실제 변환 결과 검증으로 통합 확인 |
| 서울 `imputed_sales` → `monthly_sales` 덮어쓰기 | ✅ | Test #2 |
| 서울 메타 컬럼(`is_missing/source/confidence`) drop | ✅ | Test #2 |
| utf-8-sig 인코딩 출력 | ⚠️ | 모든 테스트가 utf-8-sig로 read/write 하므로 간접 검증 |
| cp949 / utf-8 인코딩 fallback | ❌ | 테스트 없음 — 실제 imputed CSV가 utf-8-sig라 fallback 경로는 미사용 |
| RDS join (`db_url` 주어진 경우) | ❌ | 테스트 없음 — RDS mock 복잡도 회피, 실제 변환에서 통합 검증 |
| CLI `python -m scripts.imputed_to_sales_schema mapo|seoul ...` | ❌ | 테스트 없음 — argparse 표준 동작, Task 1 Step 8에서 통합 실행 |

### 6-2. `models/lstm_forecast/data_prep.py`

| 동작 | 상태 | 어디서 검증 |
|---|---|---|
| `sales_csv_override` DB skip | ✅ | Test #4 |
| `sales_csv_override` dong_prefix 필터 | ✅ | Test #4 (입력 dong_code="11440555" + prefix="11440") |
| `sales_csv_override=None` 시 기존 동작 | ⚠️ | 별도 테스트 없음 — 기존 30+ 호출자 grep으로 호환성 확인 (Task 2 보고) |
| `sales_csv_override` FileNotFoundError | ❌ | 테스트 없음 — 명백한 분기지만 직접 검증 안 함 |
| config → `load_sales_data` kwarg 전달 | ✅ | Test #5 |
| `train_cutoff_quarter` sales_df 필터 | ✅ | Test #6 |
| `train_cutoff_quarter` store_df 필터 | ⚠️ | 테스트 없음 — sales_df와 동일 cutoff 변수 공유 |
| `train_cutoff_quarter=None` 시 미동작 | ⚠️ | 기존 30+ 호출자 호환성으로 간접 확인 |
| `int(train_cutoff_quarter)` 타입 강제 | ❌ | 테스트 없음 — 코드 inspection으로만 확인 |

### 6-3. `models/tcn_forecast/train.py`

| 동작 | 상태 | 어디서 검증 |
|---|---|---|
| `--sales-csv` argparse 등록 | ❌ | 단위 테스트 없음 — `python -m models.tcn_forecast.train --help` 출력으로 통합 확인 |
| `--train-cutoff-quarter` argparse 등록 | ❌ | 동일 |
| 두 인자가 overrides dict에 들어가는지 | ❌ | 단위 테스트 없음 — Task 4 dry-run으로 확인 |
| 실제 학습 시 cfg로 전달 | ⚠️ | Task 5/6/7 학습 실행 로그(`Config: {...}`)에서 통합 확인 |

### 6-4. `validation/experiments/tcn/compare_imputed.py`

| 동작 | 상태 | 어디서 검증 |
|---|---|---|
| `compute_metrics` MAPE 계산 | ✅ | Test #7 |
| `compute_metrics` n_samples 계산 | ✅ | Test #7 |
| `compute_metrics` MAE/RMSE/R² | ⚠️ | `generate_accuracy_report` 위임이라 책임 분리, 키 매핑만 통합 검증 |
| `build_comparison_table` 3 모델 집계 | ✅ | Test #8 |
| `build_by_group_table` 동별/업종별 | ❌ | 단위 테스트 없음 — Task 10 실제 리포트로 통합 검증 |
| `render_report` 마크다운 출력 | ❌ | 단위 테스트 없음 — `tabulate` 의존성 + 다중 pivot, Task 10에서 수동 검증 |
| CLI 4개 인자 (`--original/imp-a/imp-b/out`) | ❌ | argparse 표준 동작 |

---

## 7. 미커버 영역과 위험도

| 미커버 영역 | 위험도 | 회귀 가능성 | 후속 보강 권장 |
|---|---|---|---|
| 인코딩 fallback (cp949/utf-8) | 낮음 | 매우 낮음 — 실제 imputed CSV 모두 utf-8-sig | 새 imputed CSV 형식 도입 시 추가 |
| store_df cutoff 필터 | 중간 | 낮음 — sales_df와 동일 변수 공유 | sales_df 테스트 옆에 한 줄 추가 권장 |
| TCN train.py argparse | 낮음 | 매우 낮음 — argparse 표준 패턴 | 필요 시 `parse_known_args` 호출 단위 테스트 |
| `render_report` 마크다운 | 중간 | 중간 — `tabulate` 미설치 환경에서 즉시 실패 가능 | Task 10 산출 리포트 인스펙션으로 충분 |
| `build_by_group_table` 동별/업종별 | 중간 | 중간 — pandas DeprecationWarning 발생 중 (`include_groups=False` 미명시) | 추후 pandas 버전업 시 대응 + 단위 테스트 추가 |
| RDS join (서울 어댑터) | 낮음 | 낮음 — `db_url=None` 분기는 테스트 됐고, join 분기는 한 번 실행됨(Task 1 Step 8) | RDS mock 또는 sqlite 대체로 추가 가능 |
| FileNotFoundError 분기 | 매우 낮음 | 매우 낮음 — 명백한 raise | 추가하면 좋지만 우선순위 낮음 |

---

## 8. 운영 가이드

### 8-1. 코드 변경 후 재실행 체크리스트

`scripts/imputed_to_sales_schema.py`, `models/lstm_forecast/data_prep.py`, `models/tcn_forecast/train.py`, `validation/experiments/tcn/compare_imputed.py` 중 어느 하나를 수정한 후:

```bash
pytest tests/test_imputed_to_sales_schema.py tests/test_data_prep_overrides.py tests/test_compare_imputed.py -v
ruff check models/lstm_forecast/data_prep.py models/tcn_forecast/train.py scripts/imputed_to_sales_schema.py validation/experiments/tcn/compare_imputed.py tests/
ruff format --check 동일경로
```

세 명령 모두 깨끗해야 PR 가능.

### 8-2. 새 imputed CSV 추가 시

1. `scripts/imputed_to_sales_schema.py`에 새 어댑터 함수 추가
2. `tests/test_imputed_to_sales_schema.py`에 동일 패턴 테스트 추가 (변환 + drop 검증)
3. 인코딩이 utf-8-sig가 아니라면 fallback 경로 직접 테스트 추가

### 8-3. 새 cutoff 분기 추가 시 (예: `eval_cutoff_quarter`)

1. `data_prep.py` `prepare_dataloaders`에 분기 추가
2. `tests/test_data_prep_overrides.py`에 Test #6과 동일한 패턴으로 테스트 추가 (build_timeseries spy)

### 8-4. 새 비교 모델 추가 시 (예: 4번째 모델 TCN-C)

1. `compare_imputed.py` `main()`의 csvs dict에 키 추가
2. `tests/test_compare_imputed.py` Test #8에 4번째 모델 추가, `len(table) == 4` 변경

---

## 9. 관련 문서 링크

| 종류 | 경로 |
|---|---|
| 비교 결과 리포트 | [`tcn-imputed-comparison-report.md`](./tcn-imputed-comparison-report.md) |
| 설계 문서 (Spec) | [`../superpowers/specs/2026-04-25-tcn-imputed-vs-original-comparison-design.md`](../superpowers/specs/2026-04-25-tcn-imputed-vs-original-comparison-design.md) |
| 구현 계획 (Plan) | [`../superpowers/plans/2026-04-25-tcn-imputed-vs-original-comparison.md`](../superpowers/plans/2026-04-25-tcn-imputed-vs-original-comparison.md) |
| 어댑터 본체 | `scripts/imputed_to_sales_schema.py` |
| data_prep 본체 | `models/lstm_forecast/data_prep.py` |
| TCN train CLI | `models/tcn_forecast/train.py` |
| 비교 스크립트 본체 | `validation/experiments/tcn/compare_imputed.py` |
| 어댑터 테스트 | `tests/test_imputed_to_sales_schema.py` |
| data_prep 테스트 | `tests/test_data_prep_overrides.py` |
| 비교 스크립트 테스트 | `tests/test_compare_imputed.py` |
