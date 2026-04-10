"""
실제 폐점 매장 기반 백테스트 - 모델 예측의 신뢰도 검증
"""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from validation.accuracy_metrics import mae, mape, r_squared, rmse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 내부 로그 헬퍼 - [시각][BacktestClosure][STATUS] - 메시지 형식
# ---------------------------------------------------------------------------


def _log(level: str, message: str) -> None:
    """지정 형식으로 로그를 출력한다."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}][BacktestClosure][{level}] - {message}"
    if level == "INFO":
        logger.info(formatted)
    elif level == "WARNING":
        logger.warning(formatted)
    elif level == "ERROR":
        logger.error(formatted)
    else:
        logger.debug(formatted)


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------


def _load_store_data() -> pd.DataFrame:
    """
    store_quarterly 점포 집계 데이터를 로드한다.

    models.revenue_predictor.data_prep.load_store_data() 를 재사용하여
    DB 우선 로드 후 실패 시 CSV fallback 처리한다.

    Returns:
        pd.DataFrame: 점포 시계열 데이터. 로드 실패 시 빈 DataFrame 반환.
    """
    try:
        from models.revenue_predictor.data_prep import load_store_data

        df = load_store_data(seoul=False)
        _log("INFO", f"점포 집계 데이터 로드 완료 - {len(df)}행")
        return df
    except Exception as exc:
        # DB/CSV 모두 실패한 경우 빈 DataFrame 으로 처리
        _log("WARNING", f"점포 집계 데이터 로드 실패 - 빈 DataFrame 반환: {exc}")
        return pd.DataFrame()


def _predict_survival(dong_code: str, industry_code: str) -> dict | None:
    """
    특정 동x업종의 생존률(폐업률 역수)을 예측한다.

    Args:
        dong_code:     행정동 코드 (예: "11440530")
        industry_code: 업종 코드   (예: "CS100001")

    Returns:
        dict | None:
            생존률 예측 결과 dict. 가중치 파일 없거나 예측 실패 시 None 반환.
            dict 구조: {survival_rate, closure_risk_level,
                       monthly_survival_rates, quarterly_predictions}
    """
    try:
        from models.revenue_predictor.predict import predict as survival_predict

        result = survival_predict(dong_code, industry_code)
        return result
    except FileNotFoundError as exc:
        # 가중치 파일 없음 - 정상적인 개발 환경에서 발생 가능
        _log("WARNING", f"모델 가중치 없음 (dong={dong_code}, ind={industry_code}) - None 반환: {exc}")
        return None
    except Exception as exc:
        # 데이터 부족, 피처 오류 등 예측 실패
        _log("WARNING", f"폐업률 예측 실패 (dong={dong_code}, ind={industry_code}) - None 반환: {exc}")
        return None


def _calc_regression_metrics(
    actual: list[float],
    predicted: list[float],
) -> dict:
    """
    폐업률 예측의 회귀 정확도 지표를 산출한다.

    폐업률은 연속값(%)이므로 분류 지표 대신 회귀 지표를 사용한다.
    accuracy_metrics.py 의 함수를 재사용한다.

    Args:
        actual:    실제 폐업률 리스트 (%)
        predicted: 모델 예측 폐업률 리스트 (%)

    Returns:
        dict:
            mape     : MAPE (%) - 실제값이 0인 항목 제외
            mae      : MAE  - 평균 절대 오차
            rmse     : RMSE - 평균 제곱근 오차
            r_squared: R²   - 결정계수
    """
    return {
        "mape": round(mape(actual, predicted), 4),
        "mae": round(mae(actual, predicted), 6),
        "rmse": round(rmse(actual, predicted), 6),
        "r_squared": round(r_squared(actual, predicted), 6),
    }


# ---------------------------------------------------------------------------
# 메인 함수
# ---------------------------------------------------------------------------


def run_backtest(test_year: int = 2024) -> dict:
    """
    store_quarterly 폐업률 실제값과 생존률 모델 예측값을 비교하여
    모델의 신뢰도를 검증한다.

    실제값 기준: test_year Q4 (quarter == test_year * 10 + 4) 단일 포인트의 closure_rate (%).
    예측값 기준: _predict_survival() 의 survival_rate → (1 - survival_rate) * 100 변환 (%).
    비교 지표:   회귀 지표 (MAE, RMSE, R²) - 폐업률은 연속값.

    Parameters
    ----------
    test_year : int
        평가 대상 연도 (기본 2024).

    Returns
    -------
    dict
        {
            "test_year": int,
            "overall": {"mape", "mae", "rmse", "r_squared", "n_samples"},
            "by_dong": {dong_name: {"mape", "mae", "n_samples"}, ...},
            "by_industry": {industry_name: {"mape", "mae", "n_samples"}, ...},
            "details": [...],
            "skipped": int,
        }
    """
    # ---- 1) 점포 집계 데이터 로드 ----
    df = _load_store_data()
    if df.empty:
        _log("ERROR", "점포 집계 데이터가 없습니다 - 백테스트를 중단합니다")
        return {
            "test_year": test_year,
            "error": "점포 집계 데이터 로드 실패",
            "skipped": 0,
            "overall": None,
            "by_dong": {},
            "by_industry": {},
            "details": [],
        }

    # ---- 2) test_year Q4 실제값 필터 ----
    # 분기 코드 형식: YYYYQ (예: 20244 = 2024년 4분기)
    q4_code = test_year * 10 + 4
    df_q4 = df[df["quarter"].astype(int) == q4_code].copy()

    if df_q4.empty:
        _log("WARNING", f"{test_year}년 Q4 데이터가 없습니다 (quarter={q4_code})")
        return {
            "test_year": test_year,
            "error": f"{test_year}년 Q4 데이터 없음",
            "skipped": 0,
            "overall": None,
            "by_dong": {},
            "by_industry": {},
            "details": [],
        }

    _log("INFO", f"{test_year} Q4 데이터 {len(df_q4)}건 확인")

    # ---- 3) 동x업종별 루프 - 예측 vs 실제 수집 ----
    predictions: list[dict] = []
    skipped = 0

    for _, row in df_q4.iterrows():
        dong_code = str(row["dong_code"])
        industry_code = str(row["industry_code"])

        # 실제 폐업률 (%) - 컬럼 없으면 skip
        try:
            actual_closure_rate = float(row["closure_rate"])
        except KeyError:
            _log("WARNING", f"closure_rate 컬럼 없음 (dong={dong_code}, ind={industry_code}) - skip")
            skipped += 1
            continue

        # 비정상 데이터 방어: 0~100% 범위로 클리핑
        actual_closure_rate = max(0.0, min(100.0, actual_closure_rate))

        # 폐업률 예측 - 실패 시 skip
        pred = _predict_survival(dong_code, industry_code)
        if pred is None:
            skipped += 1
            continue

        # 예측 생존률 → 폐업률 변환: (1 - survival_rate) * 100
        predicted_closure_rate = round((1.0 - float(pred["survival_rate"])) * 100, 4)

        predictions.append(
            {
                "dong_code": dong_code,
                "dong_name": str(row.get("dong_name", dong_code)),
                "industry_code": industry_code,
                "industry_name": str(row.get("industry_name", industry_code)),
                "actual_closure_rate": round(actual_closure_rate, 4),
                "predicted_closure_rate": predicted_closure_rate,
                "closure_risk_level": pred["closure_risk_level"],
            }
        )

    # ---- 4) 예측 결과가 하나도 없으면 early return ----
    if not predictions:
        _log(
            "ERROR",
            f"예측 결과 없음 (전체 {len(df_q4)}건 중 {skipped}건 skip) - "
            "가중치 파일이 있는지 확인하세요",
        )
        return {
            "test_year": test_year,
            "error": "모델 예측 실패 - 가중치 파일이 없거나 모델 로드에 실패했습니다",
            "skipped": skipped,
            "overall": None,
            "by_dong": {},
            "by_industry": {},
            "details": [],
        }

    pred_df = pd.DataFrame(predictions)
    # 폐업률 (%) 기준으로 비교
    actual_vals = pred_df["actual_closure_rate"].tolist()
    pred_vals = pred_df["predicted_closure_rate"].tolist()

    # ---- 5) 전체 회귀 정확도 지표 ----
    # closure_rate=0 항목은 MAPE 계산에서 제외되므로 사전 경고
    zero_count = actual_vals.count(0.0)
    if zero_count > 0:
        _log(
            "WARNING",
            f"실제 폐업률이 0.0인 항목 {zero_count}건 - MAPE 계산 시 해당 항목 제외됩니다",
        )

    overall_metrics = _calc_regression_metrics(actual_vals, pred_vals)
    overall_metrics["n_samples"] = len(predictions)

    _log(
        "INFO",
        f"백테스트 완료 - {len(predictions)}건 평가, {skipped}건 skip, "
        f"MAE={overall_metrics['mae']:.4f}",
    )

    # ---- 6) 동별 지표 ----
    by_dong: dict = {}
    for dong_name, grp in pred_df.groupby("dong_name"):
        a = grp["actual_closure_rate"].tolist()
        p = grp["predicted_closure_rate"].tolist()
        by_dong[dong_name] = {
            "mape": round(mape(a, p), 4),
            "mae": round(mae(a, p), 6),
            "n_samples": len(a),
        }

    # ---- 7) 업종별 지표 ----
    by_industry: dict = {}
    for ind_name, grp in pred_df.groupby("industry_name"):
        a = grp["actual_closure_rate"].tolist()
        p = grp["predicted_closure_rate"].tolist()
        by_industry[ind_name] = {
            "mape": round(mape(a, p), 4),
            "mae": round(mae(a, p), 6),
            "n_samples": len(a),
        }

    return {
        "test_year": test_year,
        "overall": overall_metrics,
        "by_dong": by_dong,
        "by_industry": by_industry,
        "details": predictions,
        "skipped": skipped,
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

    print(f"\n=== 폐업률 예측 백테스팅 ({test_year} Q4) ===")
    print(f"전체 MAE  : {ov['mae']:.4f}")
    print(f"전체 RMSE : {ov['rmse']:.4f}")
    print(f"전체 R²   : {ov['r_squared']:.4f}")
    print(f"전체 MAPE : {ov['mape']:.2f}%")
    print(f"샘플 수   : {ov['n_samples']} (skip: {result.get('skipped', 0)})")

    print("\n동별 MAE:")
    for dong, info in sorted(result["by_dong"].items(), key=lambda x: x[1]["mae"]):
        print(f"  {dong}: MAE={info['mae']:.4f} (n={info['n_samples']})")

    print("\n업종별 MAE:")
    for ind, info in sorted(result["by_industry"].items(), key=lambda x: x[1]["mae"]):
        print(f"  {ind}: MAE={info['mae']:.4f} (n={info['n_samples']})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    result = run_backtest(test_year=2024)
    print_report(result)
