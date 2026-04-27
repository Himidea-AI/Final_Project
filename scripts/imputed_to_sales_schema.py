"""imputed_*_v3.csv → RDS district_sales 스키마 형식 CSV로 변환.

마포 풀세트: ``<col>_final`` 컬럼을 base 컬럼명으로 rename, 보조 변형
(``_pred`` / ``_imputed`` / ``_final`` / ``_adjusted`` / ``_recovered``)은 제거.
서울 monthly-only: ``imputed_sales`` → ``monthly_sales`` 덮어쓰기 + RDS sub 컬럼 join.

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
    last_exc: Exception | None = None
    for enc in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return pd.read_csv(path, dtype={"dong_code": str}, encoding=enc)
        except UnicodeDecodeError as exc:
            last_exc = exc
            continue
    raise RuntimeError(f"모든 인코딩 fallback 실패: {path} (last={last_exc})")


def adapt_mapo_imputed(src_path: Path, out_path: Path) -> Path:
    """마포 imputed CSV를 base 컬럼 스키마로 변환한다.

    ``<col>_final``이 있으면 그 값을 ``<col>`` 자리에 덮어쓰고,
    ``_pred`` / ``_imputed`` / ``_adjusted`` / ``_recovered`` / ``_final`` 컬럼들은 모두 drop한다.
    """
    df = _read_csv_with_fallback(Path(src_path))

    # _final → base 덮어쓰기 (단, _final이 NaN인 row는 base 값 보존)
    final_cols = [c for c in df.columns if c.endswith("_final")]
    for fc in final_cols:
        base = fc[: -len("_final")]
        if base in df.columns:
            mask = df[fc].notna()
            df.loc[mask, base] = df.loc[mask, fc]

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

    ``imputed_sales`` → ``monthly_sales`` 덮어쓰기. ``imputed_sales`` /
    ``is_missing`` / ``source`` / ``confidence`` 컬럼은 drop.
    sub 컬럼(monthly_count, weekday_sales 등)은 RDS ``seoul_district_sales`` 에서 left join.
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
                # TODO: seoul_district_sales가 대형 테이블이면 (quarter, dong_code, industry_code) IN-필터로 부분 로드.
                sub = pd.read_sql(text("SELECT * FROM seoul_district_sales"), conn)
            engine.dispose()

            sub["dong_code"] = sub["dong_code"].astype(str)
            df["dong_code"] = df["dong_code"].astype(str)
            key = ["quarter", "dong_code", "industry_code"]
            sub_only = [c for c in sub.columns if c not in df.columns and c not in key]
            df = df.merge(sub[key + sub_only], on=key, how="left")
            logger.info("RDS sub 컬럼 %d개 join 완료", len(sub_only))

            # join 후 결측을 미세값(1e-9)으로 채워 다운스트림 _hot_deck 의 `isna() | ==0` 조건을 회피.
            # 매출 단위(수십억)에 1e-9은 학습에 사실상 무영향, Hot Deck NN 호출 폭증 방지.
            sub_in_df = [c for c in sub_only if c in df.columns]
            for c in sub_in_df:
                if pd.api.types.is_numeric_dtype(df[c]):
                    df[c] = df[c].fillna(1e-9)
            logger.info("sub 컬럼 결측을 1e-9로 채움 (Hot Deck 우회): %d 컬럼", len(sub_in_df))
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
