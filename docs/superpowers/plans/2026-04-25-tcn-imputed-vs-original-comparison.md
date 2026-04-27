# TCN Imputed vs Original 매출 비교 학습 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매출 입력 데이터만 swap한 3개 TCN 가중치(Original / TCN-A / TCN-B)를 학습·백테스트하고 비교 리포트를 산출한다.

**Architecture:**
1) 매출 소스를 swap할 수 있도록 `load_sales_data()` 와 `prepare_dataloaders()` 에 `sales_csv_override` / `train_cutoff_quarter` 인자를 추가하고 `train.py` CLI에 노출한다.
2) imputed CSV 두 종류(마포 풀세트, 서울 monthly_sales-only)를 RDS 스키마로 어댑팅하는 스크립트를 만든 뒤, A/B 두 학습을 병렬로 실행하고 동일 백테스트로 비교한다.
3) 데이터 누수 방어: 학습 시 `quarter < 20241` 필터링.

**Tech Stack:** Python 3.11, pandas, PyTorch, sqlalchemy, ruff, pytest

**Spec:** [`docs/superpowers/specs/2026-04-25-tcn-imputed-vs-original-comparison-design.md`](../specs/2026-04-25-tcn-imputed-vs-original-comparison-design.md)

---

## File Structure

| 파일 | 변경 유형 | 책임 |
|---|---|---|
| `scripts/imputed_to_sales_schema.py` | 신규 | imputed CSV → district_sales 스키마 어댑터 (마포·서울 양쪽) |
| `tests/test_imputed_to_sales_schema.py` | 신규 | 어댑터 컬럼·인코딩 검증 |
| `models/lstm_forecast/data_prep.py` | 수정 | `sales_csv_override`·`train_cutoff_quarter` 인자 추가 (load_sales_data, prepare_dataloaders) |
| `tests/test_data_prep_overrides.py` | 신규 | override·cutoff 동작 단위 테스트 |
| `models/tcn_forecast/train.py` | 수정 | `--sales-csv`, `--train-cutoff-quarter` CLI 인자 추가 |
| `data/processed/sales_imp_mapo.csv` | 신규(산출) | Task 1 결과: 마포 imputed 풀세트 |
| `data/processed/sales_imp_seoul.csv` | 신규(산출) | Task 1 결과: 서울 imputed (monthly_sales만 swap, sub는 RDS) |
| `models/tcn_forecast/weights/finetuned_mapo_tcn_imp_a.pt` 외 | 신규(산출) | Task 5/6/7 학습 결과 |
| `validation/results/tcn_backtest_results_imp_a.csv` 외 | 신규(산출) | Task 8 백테스트 결과 |
| `validation/experiments/tcn/compare_imputed.py` | 신규 | 3개 결과 비교 + 마크다운 리포트 생성 |
| `tests/test_compare_imputed.py` | 신규 | 비교 스크립트 단위 테스트 |
| `docs/abm-simulation/tcn-imputed-comparison-report.md` | 신규(산출) | Task 10 최종 리포트 |

**담당 영역 주의:** 본 작업은 `models/`, `validation/`, `scripts/` 영역에 닿는다. 사용자(A1) 담당이 아닌 영역이므로 PR 시 B2(수지니, TCN 담당) 리뷰 필수. 모든 코드 수정은 default 인자 `None` 으로 기존 호출부 동작을 100% 보존한다.

---

## Task 1: imputed CSV → district_sales 스키마 어댑터

**Files:**
- Create: `scripts/imputed_to_sales_schema.py`
- Create: `tests/test_imputed_to_sales_schema.py`
- Source: `validation/results/imputed_mapo_full_v3.csv`, `validation/results/imputed_seoul_sales_63ind.csv`
- Output: `data/processed/sales_imp_mapo.csv`, `data/processed/sales_imp_seoul.csv`

**컨텍스트:** 두 imputed CSV의 스키마가 비대칭이다.
- 마포 풀세트는 `<col>`, `<col>_pred`, `<col>_imputed`, `<col>_final` 4개 변형이 모두 있고 `_final` 컬럼이 "결측 채움 완료된 최종값". → `_final` 컬럼을 base 컬럼명으로 rename해 사용.
- 서울 63업종은 `monthly_sales`(원본/NaN) + `imputed_sales`(채움완료) 만 있음. → `imputed_sales`를 `monthly_sales`로 덮어쓰고 sub-컬럼들은 누락. 학습 시 sub-컬럼은 RDS에서 별도 로드되므로 어댑터 출력에는 RDS와 join한 결과를 저장.
- 한글 컬럼 인코딩 깨짐(`������`)은 utf-8-sig·cp949 fallback 시도.

- [ ] **Step 1: 어댑터 스펙 테스트 작성 (마포)**

```python
# tests/test_imputed_to_sales_schema.py
from pathlib import Path
import pandas as pd
import pytest
from scripts.imputed_to_sales_schema import adapt_mapo_imputed


def test_adapt_mapo_imputed_renames_final_to_base(tmp_path):
    """_final 컬럼이 base 컬럼명으로 매핑되어야 한다."""
    src = pd.DataFrame({
        "quarter": [20191, 20192],
        "dong_code": ["11440555", "11440555"],
        "dong_name": ["서교동", "서교동"],
        "industry_code": ["CS100001", "CS100001"],
        "industry_name": ["한식음식점", "한식음식점"],
        "monthly_sales": [3.4e9, 3.5e9],
        "monthly_sales_final": [3.355e9, 3.5e9],
        "monthly_count": [94005, 95000],
        "monthly_count_final": [94005, 95000],
        "weekday_sales": [2.6e9, 2.7e9],
        "weekday_sales_final": [2.608e9, 2.7e9],
    })
    src_path = tmp_path / "src.csv"
    out_path = tmp_path / "out.csv"
    src.to_csv(src_path, index=False, encoding="utf-8-sig")

    adapt_mapo_imputed(src_path, out_path)
    out = pd.read_csv(out_path, dtype={"dong_code": str})

    # _final 값이 base 컬럼에 들어왔어야 함
    assert out.loc[0, "monthly_sales"] == pytest.approx(3.355e9)
    # _final / _pred / _imputed 컬럼은 출력에 남지 않아야 함
    assert "monthly_sales_final" not in out.columns
    assert "monthly_sales_pred" not in out.columns
    assert "monthly_sales_imputed" not in out.columns
    # 필수 base 컬럼은 모두 있어야 함
    for c in ["quarter", "dong_code", "dong_name", "industry_code", "industry_name", "monthly_sales", "monthly_count", "weekday_sales"]:
        assert c in out.columns
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

```bash
cd "C:/Users/804/Documents/final project"
pytest tests/test_imputed_to_sales_schema.py::test_adapt_mapo_imputed_renames_final_to_base -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.imputed_to_sales_schema'`

- [ ] **Step 3: 어댑터 스크립트 최소 구현 — 마포만**

```python
# scripts/imputed_to_sales_schema.py
"""imputed_*_v3.csv → RDS district_sales 스키마 형식 CSV로 변환.

마포 풀세트: <col>_final 컬럼을 base 컬럼명으로 rename, 보조 변형(_pred/_imputed/_final/_adjusted/_recovered)은 제거.
서울 monthly-only: imputed_sales → monthly_sales 덮어쓰기 + RDS sub 컬럼 join.

사용:
    python -m scripts.imputed_to_sales_schema mapo  validation/results/imputed_mapo_full_v3.csv  data/processed/sales_imp_mapo.csv
    python -m scripts.imputed_to_sales_schema seoul validation/results/imputed_seoul_sales_63ind.csv data/processed/sales_imp_seoul.csv
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# 보조 변형 suffix — 출력에서 제거
_DROP_SUFFIXES = ("_pred", "_imputed", "_adjusted", "_recovered")


def _read_csv_with_fallback(path: Path) -> pd.DataFrame:
    """utf-8-sig → cp949 → utf-8 순으로 인코딩 fallback."""
    for enc in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return pd.read_csv(path, dtype={"dong_code": str}, encoding=enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(str(path), b"", 0, 1, "all encodings failed")


def adapt_mapo_imputed(src_path: Path, out_path: Path) -> Path:
    """마포 imputed CSV를 base 컬럼 스키마로 변환한다.

    `<col>_final` 이 있으면 그 값을 `<col>` 자리에 덮어쓰고,
    `_pred` / `_imputed` / `_adjusted` / `_recovered` / `_final` 컬럼들은 모두 drop한다.
    """
    df = _read_csv_with_fallback(Path(src_path))

    # _final → base 덮어쓰기
    final_cols = [c for c in df.columns if c.endswith("_final")]
    for fc in final_cols:
        base = fc[: -len("_final")]
        if base in df.columns:
            df[base] = df[fc]

    # 보조 변형 모두 drop (마지막에 _final도)
    drop = [c for c in df.columns if c.endswith(("_final", *_DROP_SUFFIXES))]
    df = df.drop(columns=drop)

    # is_missing_monthly 등 부수 컬럼 drop (RDS 스키마에 없는 것들)
    for c in ("is_missing_monthly", "is_missing"):
        if c in df.columns:
            df = df.drop(columns=c)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info("마포 어댑터 완료: %s (%d rows, %d cols)", out_path, len(df), df.shape[1])
    return out_path


def adapt_seoul_imputed(src_path: Path, out_path: Path, db_url: str | None = None) -> Path:
    """서울 imputed CSV를 base 스키마로 변환 + RDS sub 컬럼 join.

    `imputed_sales` → `monthly_sales` 덮어쓰기. `imputed_sales`, `is_missing`, `source`, `confidence` 컬럼은 drop.
    sub-컬럼(monthly_count, weekday_sales 등)은 RDS `seoul_district_sales` 에서 left join.
    DB 연결 실패 시 sub 컬럼 없이(monthly_sales만) 저장하고 경고 로그.
    """
    df = _read_csv_with_fallback(Path(src_path))

    if "imputed_sales" in df.columns:
        df["monthly_sales"] = df["imputed_sales"]

    drop = [c for c in ("imputed_sales", "is_missing", "source", "confidence") if c in df.columns]
    df = df.drop(columns=drop)

    # RDS sub 컬럼 join
    if db_url:
        try:
            from sqlalchemy import create_engine, text

            engine = create_engine(db_url)
            with engine.connect() as conn:
                sub = pd.read_sql(text("SELECT * FROM seoul_district_sales"), conn)
            engine.dispose()

            sub["dong_code"] = sub["dong_code"].astype(str)
            df["dong_code"] = df["dong_code"].astype(str)
            key = ["quarter", "dong_code", "industry_code"]
            sub_only = [c for c in sub.columns if c not in df.columns and c not in key]
            df = df.merge(sub[key + sub_only], on=key, how="left")
            logger.info("RDS sub 컬럼 %d개 join 완료", len(sub_only))
        except Exception as exc:
            logger.warning("RDS join 실패 — monthly_sales만 저장: %s", exc)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info("서울 어댑터 완료: %s (%d rows, %d cols)", out_path, len(df), df.shape[1])
    return out_path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["mapo", "seoul"])
    p.add_argument("src")
    p.add_argument("out")
    p.add_argument("--db-url", default=None)
    args = p.parse_args()

    if args.mode == "mapo":
        adapt_mapo_imputed(Path(args.src), Path(args.out))
    else:
        adapt_seoul_imputed(Path(args.src), Path(args.out), db_url=args.db_url)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 마포 어댑터 테스트 통과 확인**

```bash
pytest tests/test_imputed_to_sales_schema.py::test_adapt_mapo_imputed_renames_final_to_base -v
```
Expected: PASS

- [ ] **Step 5: 서울 어댑터 테스트 추가**

```python
# tests/test_imputed_to_sales_schema.py 에 추가
from scripts.imputed_to_sales_schema import adapt_seoul_imputed


def test_adapt_seoul_imputed_overwrites_monthly_sales(tmp_path):
    """imputed_sales가 monthly_sales를 덮어써야 한다."""
    src = pd.DataFrame({
        "quarter": [20191],
        "dong_code": ["11440555"],
        "dong_name": ["서교동"],
        "industry_code": ["CS100001"],
        "industry_name": ["한식"],
        "store_count": [88],
        "kosis_index": [111.4],
        "monthly_sales": [None],            # 결측
        "imputed_sales": [3.355e9],         # 채움값
        "is_missing": [True],
        "source": ["v3"],
        "confidence": [0.85],
    })
    src_path = tmp_path / "seoul.csv"
    out_path = tmp_path / "out.csv"
    src.to_csv(src_path, index=False, encoding="utf-8-sig")

    adapt_seoul_imputed(src_path, out_path, db_url=None)  # DB 없이
    out = pd.read_csv(out_path, dtype={"dong_code": str})

    assert out.loc[0, "monthly_sales"] == pytest.approx(3.355e9)
    assert "imputed_sales" not in out.columns
    assert "is_missing" not in out.columns
    assert "source" not in out.columns
```

- [ ] **Step 6: 테스트 실행 → PASS**

```bash
pytest tests/test_imputed_to_sales_schema.py -v
```
Expected: 2 PASS

- [ ] **Step 7: ruff 통과**

```bash
ruff check --fix scripts/imputed_to_sales_schema.py tests/test_imputed_to_sales_schema.py
ruff format scripts/imputed_to_sales_schema.py tests/test_imputed_to_sales_schema.py
```
Expected: All checks passed.

- [ ] **Step 8: 실제 imputed CSV 변환 (Phase 0 산출)**

```bash
python -m scripts.imputed_to_sales_schema mapo  validation/results/imputed_mapo_full_v3.csv      data/processed/sales_imp_mapo.csv
python -m scripts.imputed_to_sales_schema seoul validation/results/imputed_seoul_sales_63ind.csv data/processed/sales_imp_seoul.csv \
  --db-url "postgresql://postgres:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
```
Expected: 두 출력 CSV 생성. 각각의 row 수와 컬럼 수가 로그에 출력됨.

- [ ] **Step 9: 산출 CSV 검증**

```bash
python -c "
import pandas as pd
m = pd.read_csv('data/processed/sales_imp_mapo.csv', dtype={'dong_code': str})
s = pd.read_csv('data/processed/sales_imp_seoul.csv', dtype={'dong_code': str})
print('mapo:', m.shape, '— monthly_sales NaN:', m['monthly_sales'].isna().sum())
print('seoul:', s.shape, '— monthly_sales NaN:', s['monthly_sales'].isna().sum())
assert m['monthly_sales'].isna().sum() == 0, 'mapo monthly_sales에 NaN 잔존'
assert s['monthly_sales'].isna().sum() == 0, 'seoul monthly_sales에 NaN 잔존'
print('OK')
"
```
Expected: NaN 0개. `OK` 출력.

- [ ] **Step 10: Commit**

```bash
git add scripts/imputed_to_sales_schema.py tests/test_imputed_to_sales_schema.py
git commit -m "$(cat <<'EOF'
feat(scripts): imputed CSV → district_sales 스키마 어댑터 추가

마포 풀세트는 _final 컬럼을 base로 매핑하고, 서울은 imputed_sales를
monthly_sales로 덮어쓴 뒤 RDS sub 컬럼과 join. 인코딩 fallback 포함.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```
**(주의: data/processed/sales_imp_*.csv 는 .gitignore 권장 — 산출 데이터이므로. 커밋하지 않음.)**

---

## Task 2: data_prep.py에 sales_csv_override 인자 추가

**Files:**
- Modify: `models/lstm_forecast/data_prep.py:120-170` (`load_sales_data`), `models/lstm_forecast/data_prep.py:719-789` (`prepare_dataloaders`)
- Test: `tests/test_data_prep_overrides.py`

**컨텍스트:** 기존 `load_sales_data()` 시그니처는 `(db_url, csv_path, dong_prefix)`. `csv_path`는 "DB fallback" 의미라 의미가 다르다. 신규 인자 `sales_csv_override`는 "DB가 있어도 무시하고 이 CSV를 우선 사용". 기존 호출자 100% 호환을 위해 default `None`.

- [ ] **Step 1: 테스트 작성 — sales_csv_override가 DB보다 우선**

```python
# tests/test_data_prep_overrides.py
from pathlib import Path
import pandas as pd
import pytest
from models.lstm_forecast.data_prep import load_sales_data


def test_sales_csv_override_takes_precedence(tmp_path):
    """sales_csv_override 가 주어지면 DB를 시도하지 않고 CSV를 직접 읽어야 한다."""
    csv = tmp_path / "override.csv"
    pd.DataFrame({
        "quarter": [20191],
        "dong_code": ["11440555"],
        "dong_name": ["서교동"],
        "industry_code": ["CS100001"],
        "industry_name": ["한식"],
        "monthly_sales": [1.0e9],
    }).to_csv(csv, index=False, encoding="utf-8-sig")

    # DB URL을 일부러 잘못된 값으로 — override가 동작하면 DB를 안 건드려야 함
    df = load_sales_data(
        db_url="postgresql://invalid:invalid@localhost:1/nonexistent",
        sales_csv_override=str(csv),
        dong_prefix="11440",
    )
    assert len(df) == 1
    assert df.iloc[0]["monthly_sales"] == pytest.approx(1.0e9)
```

- [ ] **Step 2: 테스트 실행 → 실패**

```bash
pytest tests/test_data_prep_overrides.py::test_sales_csv_override_takes_precedence -v
```
Expected: FAIL with `TypeError: load_sales_data() got an unexpected keyword argument 'sales_csv_override'`

- [ ] **Step 3: load_sales_data 시그니처 수정**

`models/lstm_forecast/data_prep.py:120` 의 `load_sales_data` 함수 전체를 다음과 같이 수정 (기존 본문 위에 override 분기 추가):

```python
def load_sales_data(
    db_url: str = DB_URL,
    csv_path: str | Path | None = None,
    dong_prefix: str | None = None,
    sales_csv_override: str | Path | None = None,
) -> pd.DataFrame:
    """district_sales 데이터를 로드한다.

    Parameters
    ----------
    db_url : str
        PostgreSQL 접속 URL.
    csv_path : str or Path, optional
        CSV 파일 경로 (DB 접속 불가 시 fallback).
    dong_prefix : str, optional
        행정동 코드 접두사 필터 (예: '11440' = 마포구).
    sales_csv_override : str or Path, optional
        지정 시 DB를 무시하고 이 CSV를 우선 로드 (imputation 비교 학습용).

    Returns
    -------
    pd.DataFrame
        분기별 매출 데이터.
    """
    df = None

    # 0) sales_csv_override 우선 — DB 시도 자체를 skip
    if sales_csv_override is not None:
        ov_path = Path(sales_csv_override)
        if not ov_path.exists():
            raise FileNotFoundError(f"sales_csv_override CSV가 존재하지 않습니다: {ov_path}")
        df = pd.read_csv(ov_path, dtype={"dong_code": str})
        logger.info("sales_csv_override 로드: %s (%d rows)", ov_path, len(df))
        if dong_prefix and "dong_code" in df.columns:
            df = df[df["dong_code"].astype(str).str.startswith(dong_prefix)]
        return df

    # 1) DB에서 로드 시도 (기존 그대로)
    try:
        table = "seoul_district_sales" if dong_prefix is None else "district_sales"
        where = f" WHERE dong_code LIKE '{dong_prefix}%'" if dong_prefix else ""
        query = f"SELECT * FROM {table}{where} ORDER BY quarter, dong_code"  # noqa: S608
        df = _load_from_db(query, db_url)
        logger.info("DB에서 %s 로드 완료: %d rows", table, len(df))
    except Exception as exc:
        logger.warning("DB 접속 실패, CSV fallback 시도: %s", exc)

    # 2) CSV fallback (기존 그대로)
    if df is None or df.empty:
        if csv_path and Path(csv_path).exists():
            df = pd.read_csv(csv_path, dtype={"dong_code": str})
            logger.info("CSV에서 로드 완료: %s (%d rows)", csv_path, len(df))
        else:
            sales_csv = DATA_DIR / ("seoul_district_sales.csv" if dong_prefix is None else "district_sales.csv")
            if sales_csv.exists():
                df = pd.read_csv(sales_csv, dtype={"dong_code": str})
                logger.info("CSV에서 로드: %s (%d rows)", sales_csv, len(df))
            else:
                raise FileNotFoundError(f"데이터를 찾을 수 없습니다. DB 접속 실패 & CSV 없음: {sales_csv}")

    if dong_prefix and "dong_code" in df.columns:
        df = df[df["dong_code"].astype(str).str.startswith(dong_prefix)]

    return df
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_data_prep_overrides.py::test_sales_csv_override_takes_precedence -v
```
Expected: PASS

- [ ] **Step 5: prepare_dataloaders config 패스스루 추가**

`models/lstm_forecast/data_prep.py:746-757` 영역에서 config 키 읽기와 `load_sales_data` 호출을 다음과 같이 수정:

```python
def prepare_dataloaders(
    config: dict,
) -> tuple[DataLoader, DataLoader, MinMaxScaler, MinMaxScaler, int]:
    """config 기반으로 학습/검증 DataLoader를 생성한다.

    추가 config 키:
        sales_csv_override : str or Path, optional
            지정 시 DB 무시하고 이 CSV를 매출 소스로 사용 (imputation 비교용).
    """
    db_url = config.get("db_url", DB_URL)
    dong_prefix = config.get("dong_prefix", None)
    window_size = config.get("window_size", 4)
    batch_size = config.get("batch_size", 64)
    val_ratio = config.get("val_ratio", 0.2)
    target_col = config.get("target_col", "monthly_sales")
    feature_cols = config.get("feature_cols", None)
    csv_path = config.get("csv_path", None)
    sales_csv_override = config.get("sales_csv_override", None)

    # 데이터 로드
    sales_df = load_sales_data(
        db_url=db_url,
        csv_path=csv_path,
        dong_prefix=dong_prefix,
        sales_csv_override=sales_csv_override,
    )
    store_df = load_store_data(db_url=db_url, dong_prefix=dong_prefix)

    # 시계열 구성
    ts = build_timeseries(sales_df, store_df, feature_cols)
    logger.info("시계열 DataFrame 크기: %s", ts.shape)
    ...
    # (이하 기존 코드 그대로 유지)
```

(`...` 부분은 기존 코드를 그대로 둠 — `prepare_sequences` 호출, train/val split, DataLoader 생성 등 모두 동일.)

- [ ] **Step 6: prepare_dataloaders 통합 테스트 추가**

```python
# tests/test_data_prep_overrides.py 에 추가
from models.lstm_forecast.data_prep import prepare_dataloaders


def test_prepare_dataloaders_passes_override_through(tmp_path, monkeypatch):
    """config['sales_csv_override']가 load_sales_data까지 전달되어야 한다."""
    captured = {}

    from models.lstm_forecast import data_prep as dp

    real_load = dp.load_sales_data

    def spy(*args, **kwargs):
        captured["sales_csv_override"] = kwargs.get("sales_csv_override")
        return real_load(*args, **kwargs)

    monkeypatch.setattr(dp, "load_sales_data", spy)

    csv = tmp_path / "stub.csv"
    pd.DataFrame({
        "quarter": [20191] * 8 + [20192] * 8 + [20193] * 8 + [20194] * 8 + [20201] * 8,
        "dong_code": ["11440555"] * 40,
        "dong_name": ["서교동"] * 40,
        "industry_code": ["CS100001"] * 40,
        "industry_name": ["한식"] * 40,
        "monthly_sales": list(range(1_000_000_000, 1_000_000_000 + 40 * 1_000_000, 1_000_000)),
    }).to_csv(csv, index=False, encoding="utf-8-sig")

    cfg = {
        "db_url": "postgresql://invalid:invalid@localhost:1/x",
        "dong_prefix": "11440",
        "window_size": 4,
        "batch_size": 4,
        "val_ratio": 0.2,
        "target_col": "monthly_sales",
        "feature_cols": ["monthly_sales"],
        "sales_csv_override": str(csv),
    }
    try:
        prepare_dataloaders(cfg)
    except Exception:
        pass  # store_df 로드 실패는 무시 — override 전달만 검증
    assert captured.get("sales_csv_override") == str(csv)
```

- [ ] **Step 7: 테스트 실행**

```bash
pytest tests/test_data_prep_overrides.py -v
```
Expected: 2 PASS

- [ ] **Step 8: ruff 통과**

```bash
ruff check --fix models/lstm_forecast/data_prep.py tests/test_data_prep_overrides.py
ruff format   models/lstm_forecast/data_prep.py tests/test_data_prep_overrides.py
```
Expected: All checks passed.

- [ ] **Step 9: Commit**

```bash
git add models/lstm_forecast/data_prep.py tests/test_data_prep_overrides.py
git commit -m "$(cat <<'EOF'
feat(data_prep): sales_csv_override 인자 추가 — imputation 비교 학습용

load_sales_data와 prepare_dataloaders에 sales_csv_override 인자 추가.
DB가 있어도 우선 이 CSV를 매출 소스로 사용. 기존 호출 default=None로 100% 호환.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: data_prep.py에 train_cutoff_quarter 인자 추가

**Files:**
- Modify: `models/lstm_forecast/data_prep.py` `prepare_dataloaders`
- Test: `tests/test_data_prep_overrides.py`

**컨텍스트:** imputed CSV는 2024 데이터까지 포함 → 학습에 그대로 쓰면 백테스트(2024 평가)에 데이터 누수. cutoff을 prepare_dataloaders 내부에서 적용한다 (sales_df 로드 직후).

- [ ] **Step 1: cutoff 테스트 추가**

```python
# tests/test_data_prep_overrides.py 에 추가
def test_train_cutoff_quarter_filters_recent_data(tmp_path):
    """train_cutoff_quarter=20241 이면 quarter >= 20241 row가 학습 데이터에서 제외되어야 한다."""
    csv = tmp_path / "stub.csv"
    quarters = [20191, 20192, 20193, 20194, 20201, 20202, 20203, 20204,
                20211, 20212, 20213, 20214, 20221, 20222, 20223, 20224,
                20231, 20232, 20233, 20234, 20241, 20242, 20243, 20244]
    pd.DataFrame({
        "quarter": quarters,
        "dong_code": ["11440555"] * len(quarters),
        "dong_name": ["서교동"] * len(quarters),
        "industry_code": ["CS100001"] * len(quarters),
        "industry_name": ["한식"] * len(quarters),
        "monthly_sales": [1.0e9 + i * 1e7 for i in range(len(quarters))],
    }).to_csv(csv, index=False, encoding="utf-8-sig")

    from models.lstm_forecast import data_prep as dp

    captured = {}
    real_build = dp.build_timeseries

    def spy(sales_df, *args, **kwargs):
        captured["max_quarter"] = sales_df["quarter"].max()
        return real_build(sales_df, *args, **kwargs)

    import pytest as _pt
    with _pt.MonkeyPatch.context() as m:
        m.setattr(dp, "build_timeseries", spy)
        cfg = {
            "db_url": "postgresql://invalid:invalid@localhost:1/x",
            "dong_prefix": "11440",
            "window_size": 4,
            "batch_size": 4,
            "val_ratio": 0.2,
            "target_col": "monthly_sales",
            "feature_cols": ["monthly_sales"],
            "sales_csv_override": str(csv),
            "train_cutoff_quarter": 20241,
        }
        try:
            dp.prepare_dataloaders(cfg)
        except Exception:
            pass
    assert captured.get("max_quarter") is not None
    assert captured["max_quarter"] < 20241, f"cutoff 후 max_quarter={captured['max_quarter']}"
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/test_data_prep_overrides.py::test_train_cutoff_quarter_filters_recent_data -v
```
Expected: FAIL — `max_quarter == 20244` (cutoff 미적용).

- [ ] **Step 3: prepare_dataloaders에 cutoff 로직 추가**

`models/lstm_forecast/data_prep.py` `prepare_dataloaders` 함수의 `sales_df = load_sales_data(...)` 직후에 다음 블록 삽입:

```python
    sales_df = load_sales_data(
        db_url=db_url,
        csv_path=csv_path,
        dong_prefix=dong_prefix,
        sales_csv_override=sales_csv_override,
    )
    store_df = load_store_data(db_url=db_url, dong_prefix=dong_prefix)

    # train_cutoff_quarter 적용 — 데이터 누수 방어 (백테스트 평가 연도 차단)
    train_cutoff_quarter = config.get("train_cutoff_quarter", None)
    if train_cutoff_quarter is not None and "quarter" in sales_df.columns:
        before = len(sales_df)
        sales_df = sales_df[sales_df["quarter"] < int(train_cutoff_quarter)].copy()
        logger.info(
            "train_cutoff_quarter=%s 적용: %d → %d rows",
            train_cutoff_quarter, before, len(sales_df),
        )
        if "quarter" in store_df.columns:
            store_df = store_df[store_df["quarter"] < int(train_cutoff_quarter)].copy()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_data_prep_overrides.py -v
```
Expected: 3 PASS

- [ ] **Step 5: ruff 통과**

```bash
ruff check --fix models/lstm_forecast/data_prep.py tests/test_data_prep_overrides.py
ruff format   models/lstm_forecast/data_prep.py tests/test_data_prep_overrides.py
```

- [ ] **Step 6: Commit**

```bash
git add models/lstm_forecast/data_prep.py tests/test_data_prep_overrides.py
git commit -m "$(cat <<'EOF'
feat(data_prep): train_cutoff_quarter 인자 추가 — 학습 데이터 누수 방어

prepare_dataloaders config에 train_cutoff_quarter 추가. 지정 시 sales_df와
store_df에서 quarter >= cutoff인 row를 제거. imputed CSV로 학습할 때 백테스트
평가 연도(2024) 데이터가 학습에 들어가는 것을 방지.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: tcn_forecast/train.py에 CLI 인자 추가

**Files:**
- Modify: `models/tcn_forecast/train.py:497-573` (CLI parser + override 매핑)

- [ ] **Step 1: train.py CLI 파서에 두 인자 추가**

`models/tcn_forecast/train.py` `main()` 함수의 argparse 추가 영역(`parser.add_argument("--seed", ...)` 직후)에 삽입:

```python
    parser.add_argument(
        "--sales-csv",
        type=str,
        default=None,
        help="매출 소스 CSV override 경로 (DB 무시하고 이 파일을 사용; imputation 비교 학습용)",
    )
    parser.add_argument(
        "--train-cutoff-quarter",
        type=int,
        default=None,
        help="이 분기 코드 이상의 데이터를 학습에서 제외 (예: 20241 → 2024 Q1 이상 차단)",
    )
```

그리고 `overrides` 딕셔너리 구성 부분에 추가:

```python
    if args.sales_csv:
        overrides["sales_csv_override"] = args.sales_csv
    if args.train_cutoff_quarter:
        overrides["train_cutoff_quarter"] = args.train_cutoff_quarter
```

- [ ] **Step 2: 동작 확인 — DB 없이 override + cutoff로 dry-run**

```bash
python -c "
from models.tcn_forecast.train import DEFAULT_FINETUNE_CONFIG
cfg = {**DEFAULT_FINETUNE_CONFIG, 'sales_csv_override': 'data/processed/sales_imp_mapo.csv', 'train_cutoff_quarter': 20241}
print({k: v for k, v in cfg.items() if 'sales' in k or 'cutoff' in k})
"
```
Expected: `{'sales_csv_override': 'data/processed/sales_imp_mapo.csv', 'train_cutoff_quarter': 20241}`

- [ ] **Step 3: ruff 통과**

```bash
ruff check --fix models/tcn_forecast/train.py
ruff format   models/tcn_forecast/train.py
```

- [ ] **Step 4: Commit**

```bash
git add models/tcn_forecast/train.py
git commit -m "$(cat <<'EOF'
feat(tcn): train.py CLI에 --sales-csv, --train-cutoff-quarter 추가

imputation 비교 학습을 CLI 한 번 호출로 가능하게 한다.
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: TCN-A 학습 (마포 finetune만, 기존 pretrained 재사용)

**Files:**
- Output: `models/tcn_forecast/weights/finetuned_mapo_tcn_imp_a.pt`, `models/tcn_forecast/weights/finetune_tcn_scalers_imp_a.pkl`

- [ ] **Step 1: 사전 점검 — 기존 pretrained_tcn_seed2026.pt 존재 확인**

```bash
ls -la models/tcn_forecast/weights/pretrained_tcn_seed2026.pt models/tcn_forecast/weights/pretrain_tcn_scalers_seed2026.pkl
```
Expected: 두 파일 존재. 없으면 Task 6과 동일하게 pretrain seed2026 부터 실행 필요.

- [ ] **Step 2: TCN-A finetune 실행 (백그라운드)**

```bash
python -m models.tcn_forecast.train --mode finetune \
  --sales-csv data/processed/sales_imp_mapo.csv \
  --train-cutoff-quarter 20241 \
  --save-suffix imp_a \
  --seed 2026 \
  2>&1 | tee logs/tcn_imp_a_finetune.log
```
Expected: 로그에 `TCN 파인튜닝 완료. 가중치 저장: .../finetuned_mapo_tcn_imp_a.pt`. 학습 시간 보통 5~15분(CPU).

> 참고: `--save-suffix imp_a` 가 finetune 모드일 때 `--pretrained_path` 도 `pretrained_tcn_imp_a.pt` 로 자동 변경되도록 train.py 562~568 줄에 작성되어 있음. 즉 imp_a 용 pretrain 가중치가 별도로 필요. 이를 회피하기 위해 **DEFAULT_FINETUNE_CONFIG의 `pretrained_path` 를 명시적으로 override** 한다 — 다음 명령으로 대체 실행:

```bash
python - <<'PY'
import logging
logging.basicConfig(level=logging.INFO)

from models.tcn_forecast.train import finetune, DEFAULT_FINETUNE_CONFIG, WEIGHTS_DIR
import random, numpy as np, torch
random.seed(2026); np.random.seed(2026); torch.manual_seed(2026)

cfg = {
    **DEFAULT_FINETUNE_CONFIG,
    "sales_csv_override": "data/processed/sales_imp_mapo.csv",
    "train_cutoff_quarter": 20241,
    "pretrained_path": str(WEIGHTS_DIR / "pretrained_tcn_seed2026.pt"),
    "save_path": str(WEIGHTS_DIR / "finetuned_mapo_tcn_imp_a.pt"),
}
finetune(cfg)
PY
```
Expected: `finetuned_mapo_tcn_imp_a.pt` 와 `finetune_tcn_scalers_imp_a.pkl` 생성.

- [ ] **Step 3: 산출 가중치 검증**

```bash
ls -la models/tcn_forecast/weights/finetuned_mapo_tcn_imp_a.pt models/tcn_forecast/weights/finetune_tcn_scalers_imp_a.pkl
```
Expected: 두 파일 존재. 가중치 파일 ~589KB 크기.

- [ ] **Step 4: 산출물 git 추적 (가중치는 LFS 또는 별도 처리 — 프로젝트 정책 확인 후)**

기존 가중치들이 git에 commit되어 있는지 먼저 확인:
```bash
git log --oneline -- models/tcn_forecast/weights/finetuned_mapo_tcn_seed2026.pt | head -3
```
- 추적되어 있으면 → `git add models/tcn_forecast/weights/finetuned_mapo_tcn_imp_a.pt models/tcn_forecast/weights/finetune_tcn_scalers_imp_a.pkl` 후 commit
- 추적되어 있지 않으면 → 산출 후 `.gitignore` 확인하고 커밋 생략 (별도 산출물 보관 정책 따름)

```bash
git add models/tcn_forecast/weights/finetuned_mapo_tcn_imp_a.pt models/tcn_forecast/weights/finetune_tcn_scalers_imp_a.pkl
git commit -m "feat(tcn): TCN-A 학습 가중치 추가 — 마포 imputed v3 finetune (seed=2026, cutoff=20241)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: TCN-B 사전학습 (서울 imputed)

**Files:**
- Output: `models/tcn_forecast/weights/pretrained_tcn_imp_b.pt`, `models/tcn_forecast/weights/pretrain_tcn_scalers_imp_b.pkl`

**병렬화 노트:** 이 task는 Task 5와 동시에 백그라운드로 실행 가능 (서로 다른 데이터·suffix). 자원 여유가 있으면 두 개 셸을 띄워 동시 실행.

- [ ] **Step 1: TCN-B pretrain 실행**

```bash
python -m models.tcn_forecast.train --mode pretrain \
  --sales-csv data/processed/sales_imp_seoul.csv \
  --train-cutoff-quarter 20241 \
  --save-suffix imp_b \
  --seed 2026 \
  2>&1 | tee logs/tcn_imp_b_pretrain.log
```
Expected: 로그에 `TCN 사전학습 완료. 가중치 저장: .../pretrained_tcn_imp_b.pt`. 서울 전체 → 학습 시간 30분~수 시간(CPU 기준).

- [ ] **Step 2: 산출 검증**

```bash
ls -la models/tcn_forecast/weights/pretrained_tcn_imp_b.pt models/tcn_forecast/weights/pretrain_tcn_scalers_imp_b.pkl
```
Expected: 두 파일 존재.

- [ ] **Step 3: Commit (Task 5 정책과 동일)**

```bash
git add models/tcn_forecast/weights/pretrained_tcn_imp_b.pt models/tcn_forecast/weights/pretrain_tcn_scalers_imp_b.pkl
git commit -m "feat(tcn): TCN-B pretrain 가중치 추가 — 서울 imputed v3 (seed=2026, cutoff=20241)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: TCN-B 파인튜닝 (마포 imputed)

**Files:**
- Output: `models/tcn_forecast/weights/finetuned_mapo_tcn_imp_b.pt`, `models/tcn_forecast/weights/finetune_tcn_scalers_imp_b.pkl`

**의존성:** Task 6 완료 후 실행.

- [ ] **Step 1: TCN-B finetune 실행**

`--save-suffix imp_b` 가 자동으로 `pretrained_tcn_imp_b.pt` 를 사용하므로 그냥 호출:

```bash
python -m models.tcn_forecast.train --mode finetune \
  --sales-csv data/processed/sales_imp_mapo.csv \
  --train-cutoff-quarter 20241 \
  --save-suffix imp_b \
  --seed 2026 \
  2>&1 | tee logs/tcn_imp_b_finetune.log
```
Expected: `finetuned_mapo_tcn_imp_b.pt` 생성.

- [ ] **Step 2: 산출 검증**

```bash
ls -la models/tcn_forecast/weights/finetuned_mapo_tcn_imp_b.pt models/tcn_forecast/weights/finetune_tcn_scalers_imp_b.pkl
```
Expected: 두 파일 존재.

- [ ] **Step 3: Commit**

```bash
git add models/tcn_forecast/weights/finetuned_mapo_tcn_imp_b.pt models/tcn_forecast/weights/finetune_tcn_scalers_imp_b.pkl
git commit -m "feat(tcn): TCN-B finetune 가중치 추가 — 마포 imputed v3 (seed=2026, cutoff=20241)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: 백테스트 3개 (Original / A / B)

**Files:**
- Output: `validation/results/tcn_backtest_results.csv` (재실행), `validation/results/tcn_backtest_results_imp_a.csv`, `validation/results/tcn_backtest_results_imp_b.csv`

**중요:** 백테스트 매출 소스는 **항상 RDS의 실측**이어야 한다 (`backtest_tcn.py` 기본값). `--sales-csv` 등 override 인자를 백테스트에 사용해서는 안 된다 — 평가의 ground truth는 실측이다.

- [ ] **Step 1: Original 모델 백테스트 (재현용)**

```bash
python -m validation.experiments.tcn.backtest_tcn --year 2024 --weights-suffix seed2026 \
  2>&1 | tee logs/tcn_backtest_original.log
```
Expected: `validation/results/tcn_backtest_results_seed2026.csv` 갱신. 콘솔에 전체 MAPE / R² / 동별·업종별 출력.

- [ ] **Step 2: TCN-A 백테스트**

```bash
python -m validation.experiments.tcn.backtest_tcn --year 2024 --weights-suffix imp_a \
  2>&1 | tee logs/tcn_backtest_imp_a.log
```
Expected: `validation/results/tcn_backtest_results_imp_a.csv` 생성.

- [ ] **Step 3: TCN-B 백테스트**

```bash
python -m validation.experiments.tcn.backtest_tcn --year 2024 --weights-suffix imp_b \
  2>&1 | tee logs/tcn_backtest_imp_b.log
```
Expected: `validation/results/tcn_backtest_results_imp_b.csv` 생성.

- [ ] **Step 4: 3개 CSV 존재 확인**

```bash
ls -la validation/results/tcn_backtest_results_seed2026.csv validation/results/tcn_backtest_results_imp_a.csv validation/results/tcn_backtest_results_imp_b.csv
```
Expected: 3개 파일 존재. 각 파일 row 수가 비슷해야 함(동일 마포 동×업종 조합).

- [ ] **Step 5: Commit**

```bash
git add validation/results/tcn_backtest_results_imp_a.csv validation/results/tcn_backtest_results_imp_b.csv validation/results/tcn_backtest_results_seed2026.csv
git commit -m "feat(validation): TCN imputation 비교 백테스트 결과 3종

Original(seed2026) / TCN-A(imp_a) / TCN-B(imp_b) 마포 2024 백테스트 결과.
세 모델 모두 동일한 RDS 실측 매출로 평가.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: 비교 리포트 스크립트

**Files:**
- Create: `validation/experiments/tcn/compare_imputed.py`
- Test: `tests/test_compare_imputed.py`
- Output: `docs/abm-simulation/tcn-imputed-comparison-report.md`

- [ ] **Step 1: 비교 함수 테스트 작성**

```python
# tests/test_compare_imputed.py
from pathlib import Path
import pandas as pd
import pytest
from validation.experiments.tcn.compare_imputed import compute_metrics, build_comparison_table


def _toy_csv(tmp_path: Path, name: str, mape_target: float) -> Path:
    """주어진 MAPE를 만족하는 toy 백테스트 CSV 생성."""
    actual = [1.0e9, 2.0e9, 3.0e9, 4.0e9]
    pred = [a * (1 + mape_target / 100.0) for a in actual]
    df = pd.DataFrame({
        "test_year": [2024] * 4,
        "dong_code": ["11440555"] * 4,
        "dong_name": ["서교동"] * 4,
        "industry_code": ["CS100001", "CS100002", "CS100003", "CS100004"],
        "industry_name": ["A", "B", "C", "D"],
        "actual_annual_sales": actual,
        "predicted_annual_sales": pred,
        "abs_error": [abs(a - p) for a, p in zip(actual, pred)],
        "mape_pct": [mape_target] * 4,
    })
    p = tmp_path / name
    df.to_csv(p, index=False, encoding="utf-8-sig")
    return p


def test_compute_metrics_returns_overall_mape(tmp_path):
    csv = _toy_csv(tmp_path, "x.csv", 10.0)
    m = compute_metrics(csv)
    assert m["mape"] == pytest.approx(10.0, abs=0.5)
    assert m["n_samples"] == 4


def test_build_comparison_table_shows_three_models(tmp_path):
    a = _toy_csv(tmp_path, "a.csv", 15.0)
    b = _toy_csv(tmp_path, "b.csv", 8.0)
    c = _toy_csv(tmp_path, "c.csv", 12.0)
    table = build_comparison_table({"Original": a, "TCN-A": b, "TCN-B": c})
    assert "Original" in table["model"].values
    assert "TCN-A" in table["model"].values
    assert "TCN-B" in table["model"].values
    assert len(table) == 3
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/test_compare_imputed.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'validation.experiments.tcn.compare_imputed'`

- [ ] **Step 3: compare_imputed.py 구현**

```python
# validation/experiments/tcn/compare_imputed.py
"""TCN imputation 비교 백테스트 결과 분석.

3개 모델(Original/TCN-A/TCN-B)의 백테스트 CSV를 받아 전체·동별·업종별
MAPE/MAE/RMSE/R² 비교 표를 만들고 마크다운 리포트로 저장한다.

사용:
    python -m validation.experiments.tcn.compare_imputed
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from validation.accuracy_metrics import generate_accuracy_report

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = PROJECT_ROOT / "validation" / "results"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "abm-simulation" / "tcn-imputed-comparison-report.md"


def compute_metrics(csv_path: Path) -> dict:
    """백테스트 CSV에서 전체 정확도 지표를 계산한다."""
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    actual = df["actual_annual_sales"].to_numpy()
    pred = df["predicted_annual_sales"].to_numpy()
    rep = generate_accuracy_report(actual, pred)["overall"]
    return {
        "mape": round(rep["mape"], 2),
        "mae": round(rep["mae"], 0),
        "rmse": round(rep["rmse"], 0),
        "r_squared": round(rep["r_squared"], 4),
        "n_samples": len(df),
    }


def build_comparison_table(csvs: dict[str, Path]) -> pd.DataFrame:
    """모델명 → CSV 경로 매핑을 받아 비교 표 DataFrame을 반환."""
    rows = []
    for name, path in csvs.items():
        m = compute_metrics(path)
        rows.append({"model": name, **m})
    return pd.DataFrame(rows)


def build_by_group_table(csvs: dict[str, Path], group_col: str) -> pd.DataFrame:
    """동별/업종별 MAPE 비교 표 (long format)."""
    frames = []
    for name, path in csvs.items():
        df = pd.read_csv(path, encoding="utf-8-sig")
        agg = df.groupby(group_col).apply(
            lambda g: pd.Series({
                "mape": float(np.mean(np.abs(g["actual_annual_sales"] - g["predicted_annual_sales"]) / g["actual_annual_sales"]) * 100),
                "n": len(g),
            })
        ).reset_index()
        agg["model"] = name
        frames.append(agg)
    return pd.concat(frames, ignore_index=True)


def render_report(overall: pd.DataFrame, by_dong: pd.DataFrame, by_ind: pd.DataFrame) -> str:
    """마크다운 리포트 문자열 생성."""
    lines = ["# TCN Imputation 비교 백테스트 리포트", ""]
    lines.append("**생성 시점:** 자동 산출 — `validation/experiments/tcn/compare_imputed.py`")
    lines.append("")
    lines.append("## 전체 정확도")
    lines.append("")
    lines.append(overall.to_markdown(index=False))
    lines.append("")
    lines.append("## 동별 MAPE")
    lines.append("")
    pivot_d = by_dong.pivot(index="dong_name", columns="model", values="mape").round(2)
    lines.append(pivot_d.to_markdown())
    lines.append("")
    lines.append("## 업종별 MAPE")
    lines.append("")
    pivot_i = by_ind.pivot(index="industry_name", columns="model", values="mape").round(2)
    lines.append(pivot_i.to_markdown())
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--original", default=str(RESULTS_DIR / "tcn_backtest_results_seed2026.csv"))
    p.add_argument("--imp-a",    default=str(RESULTS_DIR / "tcn_backtest_results_imp_a.csv"))
    p.add_argument("--imp-b",    default=str(RESULTS_DIR / "tcn_backtest_results_imp_b.csv"))
    p.add_argument("--out",      default=str(DEFAULT_REPORT_PATH))
    args = p.parse_args()

    csvs = {
        "Original": Path(args.original),
        "TCN-A": Path(args.imp_a),
        "TCN-B": Path(args.imp_b),
    }
    for name, path in csvs.items():
        if not path.exists():
            raise FileNotFoundError(f"{name} 결과 CSV 없음: {path}")

    overall = build_comparison_table(csvs)
    by_dong = build_by_group_table(csvs, "dong_name")
    by_ind = build_by_group_table(csvs, "industry_name")

    report = render_report(overall, by_dong, by_ind)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    logger.info("리포트 저장: %s", out)
    print(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_compare_imputed.py -v
```
Expected: 2 PASS

- [ ] **Step 5: ruff 통과**

```bash
ruff check --fix validation/experiments/tcn/compare_imputed.py tests/test_compare_imputed.py
ruff format   validation/experiments/tcn/compare_imputed.py tests/test_compare_imputed.py
```

- [ ] **Step 6: Commit (코드만, 리포트는 Task 10에서)**

```bash
git add validation/experiments/tcn/compare_imputed.py tests/test_compare_imputed.py
git commit -m "$(cat <<'EOF'
feat(validation): TCN imputation 3모델 비교 리포트 스크립트

compare_imputed.py — 3개 백테스트 CSV에서 전체·동별·업종별 MAPE 비교 표 +
마크다운 리포트 산출. Original / TCN-A / TCN-B 비교용.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: 리포트 산출 + 최종 정리

**Files:**
- Output: `docs/abm-simulation/tcn-imputed-comparison-report.md`

- [ ] **Step 1: 리포트 생성**

```bash
python -m validation.experiments.tcn.compare_imputed
```
Expected: 콘솔에 전체/동별/업종별 표 출력, 파일 `docs/abm-simulation/tcn-imputed-comparison-report.md` 저장.

- [ ] **Step 2: 리포트 가독성 확인 + 해석 섹션 수동 추가**

`docs/abm-simulation/tcn-imputed-comparison-report.md` 파일 끝에 "## 해석" 섹션을 수동으로 추가:

```markdown
## 해석

- **전체 MAPE 비교:** [Original / TCN-A / TCN-B 의 MAPE 차이를 한 줄로]
- **TCN-A vs Original:** [마포 finetune만 imputed로 바꾼 효과]
- **TCN-B vs TCN-A:** [pretrain까지 풀 imputed로 갔을 때 추가 효과]
- **동/업종 편향:** [어떤 동·업종에서 특히 차이가 크게 났는지]
- **결론:** [비교 가설(매출 imputation이 백테스트 MAPE 개선에 기여하는가?)에 대한 결론]
```

(실제 수치는 Step 1 산출 결과를 보고 채움.)

- [ ] **Step 3: Commit**

```bash
git add docs/abm-simulation/tcn-imputed-comparison-report.md
git commit -m "$(cat <<'EOF'
docs(abm-simulation): TCN imputation 비교 백테스트 최종 리포트

Original vs TCN-A vs TCN-B 마포 2024 백테스트 결과와 해석.
매출 imputation의 학습 기여 효과 검증.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: 전체 점검 — 모든 변경 파일·산출물 git 정리 상태 확인**

```bash
git log --oneline -15
git status
```
Expected: 본 plan 관련 commit 8~10개. uncommitted file 없음(또는 의도적 산출 데이터만 남음).

- [ ] **Step 5: PR 준비 (선택)**

`finishing-a-development-branch` 스킬을 호출해 PR 생성 여부 결정. B2(수지니, TCN 담당) 리뷰 명시.

---

## 부록: 병렬 실행 권장 패턴

자원 여유가 있을 때(16GB+ RAM, GPU 또는 멀티코어 CPU):

**터미널 1 (Task 5):**
```bash
python - <<'PY' 2>&1 | tee logs/tcn_imp_a_finetune.log
# Task 5 Step 2의 PY 스크립트 그대로
PY
```

**터미널 2 (Task 6):**
```bash
python -m models.tcn_forecast.train --mode pretrain \
  --sales-csv data/processed/sales_imp_seoul.csv \
  --train-cutoff-quarter 20241 \
  --save-suffix imp_b --seed 2026 \
  2>&1 | tee logs/tcn_imp_b_pretrain.log
```

**터미널 1 종료 → A 백테스트, 터미널 2 종료 → Task 7 → B 백테스트.** 또는 `superpowers:dispatching-parallel-agents` 스킬을 활용해 두 학습을 별도 subagent로 백그라운드 dispatch.

---

## Self-Review 결과

- **Spec 커버리지:** Sec 2 (데이터 swap 메커니즘) → Tasks 2~4. Sec 3 (네이밍) → Tasks 5~8. Sec 4 (실행 파이프라인) → Tasks 1, 5~8. Sec 5 (변경 파일) → 모든 Task. Sec 6 (평가) → Tasks 8~10. Sec 7.3 (데이터 누수 방어) → Task 3.
- **Placeholder 스캔:** "TBD" / "implement later" 없음. Step 2의 "해석" 섹션은 실제 수치 산출 후 작성하는 것이 합리적이므로 **빈 곳을 일부러 둔 게 아니라** Step 1 결과 의존이라 명시.
- **Type 일관성:** `sales_csv_override` 인자명, `train_cutoff_quarter` 인자명이 모든 Task(2,3,4,5,6,7)에서 동일. CLI 플래그 `--sales-csv`, `--train-cutoff-quarter` 도 모든 호출에서 동일.
- **백테스트 매출 override 금지** Task 8 첫머리에 명시 — 평가 정합성.
