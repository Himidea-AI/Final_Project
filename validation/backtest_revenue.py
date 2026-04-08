"""
매출 예측 백테스팅 — LSTM 모델의 2024년 마포구 매출 예측 정확도 검증

2019~2023 데이터를 기반으로 2024년 매출을 예측하고 실제 값과 비교한다.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

from validation.accuracy_metrics import generate_accuracy_report, mae, mape

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 경로 / DB 설정
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
SALES_CSV = DATA_DIR / "district_sales.csv"
STORES_CSV = DATA_DIR / "district_stores.csv"

_pw = os.environ.get("POSTGRES_PASSWORD", "postgres")
_host = os.environ.get("POSTGRES_HOST", "192.168.0.28")
_port = os.environ.get("POSTGRES_PORT", "5432")
_db = os.environ.get("POSTGRES_DB", "mapo_simulator")
DB_URL = os.environ.get(
    "POSTGRES_URL",
    f"postgresql://postgres:{_pw}@{_host}:{_port}/{_db}",
)


# ---------------------------------------------------------------------------
# 컬럼 매핑
# ---------------------------------------------------------------------------
_SALES_COL_MAP = {
    "STDR_YYQU_CD": "quarter",
    "행정동코드": "dong_code",
    "행정동명": "dong_name",
    "SVC_INDUTY_CD": "industry_code",
    "SVC_INDUTY_CD_NM": "industry_name",
    "THSMON_SELNG_AMT": "monthly_sales",
    "THSMON_SELNG_CO": "monthly_count",
    "MDWK_SELNG_AMT": "weekday_sales",
    "WKEND_SELNG_AMT": "weekend_sales",
    "ML_SELNG_AMT": "male_sales",
    "FML_SELNG_AMT": "female_sales",
}


# ---------------------------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------------------------


def _load_sales_data() -> pd.DataFrame:
    """매출 데이터를 DB 또는 CSV에서 로드한다."""
    try:
        import sqlalchemy

        engine = sqlalchemy.create_engine(DB_URL)
        df = pd.read_sql("SELECT * FROM district_sales", engine)
        logger.info("DB에서 district_sales 로드 완료 (%d rows)", len(df))
        return df
    except Exception as exc:
        logger.warning("DB 연결 실패 (%s) — CSV fallback", exc)

    if not SALES_CSV.exists():
        raise FileNotFoundError(f"매출 CSV 파일을 찾을 수 없습니다: {SALES_CSV}")

    df = pd.read_csv(SALES_CSV, encoding="utf-8-sig")
    logger.info("CSV에서 district_sales 로드 완료 (%d rows)", len(df))
    return df


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """CSV 원본 컬럼명을 내부 통일 컬럼명으로 변환한다."""
    renamed = df.rename(columns=_SALES_COL_MAP)
    if "quarter" in renamed.columns:
        renamed["quarter"] = renamed["quarter"].astype(int)
    return renamed


# ---------------------------------------------------------------------------
# 모델 예측
# ---------------------------------------------------------------------------


def _predict_revenue(dong_code: str, industry_code: str) -> float | None:
    """LSTM 모델로 특정 동x업종의 2024년 연간 매출을 예측한다.

    가중치 파일이 없으면 None을 반환한다.
    """
    try:
        from models.lstm_forecast.predict import predict as lstm_predict

        # 4분기(1년) 예측
        results = lstm_predict(dong_code=dong_code, industry_code=industry_code, n_months=4)
        # 분기별 예측 매출 합산 → 연간 매출
        annual_sales = sum(r["predicted_sales"] for r in results)
        return annual_sales
    except FileNotFoundError as exc:
        logger.debug("모델 가중치 없음: %s", exc)
        return None
    except Exception as exc:
        logger.debug("예측 실패 (dong=%s, ind=%s): %s", dong_code, industry_code, exc)
        return None


# ---------------------------------------------------------------------------
# 백테스트 메인
# ---------------------------------------------------------------------------


def backtest_revenue(test_year: int = 2024) -> dict:
    """매출 예측 모델의 백테스트를 실행한다.

    Parameters
    ----------
    test_year : int
        평가 대상 연도 (기본 2024).

    Returns
    -------
    dict
        {
            "test_year": int,
            "overall": {"mape": ..., "mae": ..., "rmse": ..., "r_squared": ..., "n_samples": ...},
            "by_dong": {dong_name: {"mape": ..., "n_samples": ...}, ...},
            "by_industry": {industry_name: {"mape": ..., "n_samples": ...}, ...},
            "details": [{"dong_name": ..., "industry_name": ..., "actual": ..., "predicted": ...}, ...]
        }
    """
    # 1. 데이터 로드
    df = _load_sales_data()
    df = _normalize_columns(df)

    # 연도 추출
    df["year"] = df["quarter"] // 10

    # 2. 2024년 실제 매출 (동×업종별 연간 합산)
    df_actual = df[df["year"] == test_year].copy()
    if df_actual.empty:
        logger.warning("%d년 실제 매출 데이터가 없습니다.", test_year)
        return {"test_year": test_year, "error": f"{test_year}년 데이터 없음"}

    actual_agg = (
        df_actual.groupby(["dong_code", "dong_name", "industry_code", "industry_name"])
        .agg(actual_annual_sales=("monthly_sales", "sum"))
        .reset_index()
    )

    # 3. 각 동×업종에 대해 모델 예측 수행
    predictions: list[dict] = []
    skipped = 0

    for _, row in actual_agg.iterrows():
        dong_code = str(row["dong_code"])
        industry_code = str(row["industry_code"])
        pred_sales = _predict_revenue(dong_code, industry_code)

        if pred_sales is None:
            skipped += 1
            continue

        predictions.append(
            {
                "dong_code": dong_code,
                "dong_name": row["dong_name"],
                "industry_code": industry_code,
                "industry_name": row["industry_name"],
                "actual_annual_sales": float(row["actual_annual_sales"]),
                "predicted_annual_sales": float(pred_sales),
            }
        )

    if not predictions:
        logger.error(
            "모델 예측 결과가 없습니다 (전체 %d건 중 %d건 건너뜀). 가중치 파일이 있는지 확인하세요.",
            len(actual_agg),
            skipped,
        )
        return {
            "test_year": test_year,
            "error": "모델 예측 실패 — 가중치 파일이 없거나 모델 로드에 실패했습니다.",
            "skipped": skipped,
        }

    pred_df = pd.DataFrame(predictions)
    actual_vals = pred_df["actual_annual_sales"].values
    pred_vals = pred_df["predicted_annual_sales"].values

    # 4. 전체 정확도
    full_report = generate_accuracy_report(actual_vals, pred_vals)
    overall_report = full_report["overall"]
    overall_report["n_samples"] = len(actual_vals)

    # 5. 동별 MAPE
    by_dong: dict = {}
    for dong_name, grp in pred_df.groupby("dong_name"):
        a = grp["actual_annual_sales"].values
        p = grp["predicted_annual_sales"].values
        by_dong[dong_name] = {
            "mape": round(mape(a, p), 2),
            "mae": round(mae(a, p), 0),
            "n_samples": len(a),
        }

    # 6. 업종별 MAPE
    by_industry: dict = {}
    for ind_name, grp in pred_df.groupby("industry_name"):
        a = grp["actual_annual_sales"].values
        p = grp["predicted_annual_sales"].values
        by_industry[ind_name] = {
            "mape": round(mape(a, p), 2),
            "mae": round(mae(a, p), 0),
            "n_samples": len(a),
        }

    return {
        "test_year": test_year,
        "overall": {
            "mape": round(overall_report["mape"], 2),
            "mae": round(overall_report["mae"], 0),
            "rmse": round(overall_report["rmse"], 0),
            "r_squared": round(overall_report["r_squared"], 4),
            "n_samples": overall_report["n_samples"],
        },
        "by_dong": by_dong,
        "by_industry": by_industry,
        "details": predictions,
    }


# ---------------------------------------------------------------------------
# 출력 포맷
# ---------------------------------------------------------------------------


def print_report(result: dict) -> None:
    """백테스트 결과를 콘솔에 포맷팅하여 출력한다."""
    if "error" in result:
        print(f"\n[ERROR] {result['error']}")
        return

    test_year = result["test_year"]
    ov = result["overall"]

    print(f"\n=== 매출 예측 백테스팅 ({test_year}) ===")
    print(f"전체 MAPE: {ov['mape']:.1f}%")
    print(f"전체 MAE: {ov['mae']:,.0f}원")
    print(f"전체 RMSE: {ov['rmse']:,.0f}원")
    print(f"전체 R²: {ov['r_squared']:.4f}")
    print(f"샘플 수: {ov['n_samples']}")

    print("\n동별 MAPE:")
    for dong, info in sorted(result["by_dong"].items(), key=lambda x: x[1]["mape"]):
        print(f"  {dong}: {info['mape']:.1f}%")

    print("\n업종별 MAPE:")
    for ind, info in sorted(result["by_industry"].items(), key=lambda x: x[1]["mape"]):
        print(f"  {ind}: {info['mape']:.1f}%")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    result = backtest_revenue(test_year=2024)
    print_report(result)
