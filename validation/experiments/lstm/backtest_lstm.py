"""
LSTM 매출 예측 백테스팅 — 2024년 마포구 매출 예측 정확도 검증

GRU backtest_gru.py 구조를 그대로 따르되, 아래 항목을 LSTM에 맞게 변경:
- GRUForecaster → LSTMForecaster
- 가중치 경로: gru_forecast/weights/ → lstm_forecast/weights/
- 가중치 파일: finetuned_mapo_gru.pt → finetuned_mapo.pt
- 스케일러 파일: finetune_gru_scalers.pkl → finetune_scalers.pkl
- 결과를 validation/results/lstm_backtest_results.csv 로 저장

window_size=4, hidden_size=128 은 GRU와 동일 — 공정한 비교를 위해 통일.

담당: B2 — 수지니
참조: validation/experiments/gru/backtest_gru.py (구조 동일)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

# 정확도 지표 함수 재사용 — validation/accuracy_metrics.py 에서 import
from validation.accuracy_metrics import generate_accuracy_report, mae, mape

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 경로 / DB 설정
# ---------------------------------------------------------------------------

# 프로젝트 루트: 이 파일 위치 기준 3단계 상위 (experiments/lstm/ → experiments/ → validation/ → root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# 결과 저장 경로 — validation/results/lstm_backtest_results.csv
RESULTS_DIR = PROJECT_ROOT / "validation" / "results"
RESULTS_CSV = RESULTS_DIR / "lstm_backtest_results.csv"

# DB 연결 URL — 환경변수에서 로드 (GRU backtest_gru.py와 동일 방식)
_pw = os.environ.get("POSTGRES_PASSWORD", "postgres")
_host = os.environ.get("POSTGRES_HOST", "192.168.0.28")
_port = os.environ.get("POSTGRES_PORT", "5432")
_db = os.environ.get("POSTGRES_DB", "mapo_simulator")
DB_URL = os.environ.get(
    "POSTGRES_URL",
    f"postgresql://postgres:{_pw}@{_host}:{_port}/{_db}",
)


# ---------------------------------------------------------------------------
# 컬럼 매핑 — CSV 원본 컬럼명 → 내부 통일 컬럼명
# GRU backtest_gru.py와 동일한 매핑 사용 (데이터 포맷이 같으므로)
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
# 데이터 로드 함수
# ---------------------------------------------------------------------------


def _load_sales_data() -> pd.DataFrame:
    """매출 데이터를 DB 또는 CSV fallback으로 로드한다.

    DB 연결 실패 시 data/processed/district_sales.csv 를 사용한다.
    GRU backtest_gru.py의 동일 함수와 구조 동일 — 데이터 소스가 같으므로.
    """
    # DB 우선 시도
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            df = pd.read_sql(text("SELECT * FROM district_sales"), conn)
        engine.dispose()
        logger.info("DB에서 district_sales 로드 완료 (%d rows)", len(df))
        return df
    except Exception as exc:
        logger.warning("DB 연결 실패 (%s) — CSV fallback", exc)

    # CSV fallback
    sales_csv = PROJECT_ROOT / "data" / "processed" / "district_sales.csv"
    if not sales_csv.exists():
        raise FileNotFoundError(f"매출 CSV 파일을 찾을 수 없습니다: {sales_csv}")

    df = pd.read_csv(sales_csv, encoding="utf-8-sig")
    logger.info("CSV에서 district_sales 로드 완료 (%d rows)", len(df))
    return df


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """CSV 원본 컬럼명을 내부 통일 컬럼명으로 변환한다.

    DB에서 로드 시 이미 영문 컬럼이므로 rename이 적용되지 않아도 무방하다.
    """
    renamed = df.rename(columns=_SALES_COL_MAP)
    if "quarter" in renamed.columns:
        renamed["quarter"] = renamed["quarter"].astype(int)
    return renamed


# ---------------------------------------------------------------------------
# LSTM 모델 예측 함수
# ---------------------------------------------------------------------------


def _predict_revenue_lstm(
    dong_code: str,
    industry_code: str,
    timeseries_df: pd.DataFrame,
    feat_cols: list[str],
    feat_scaler,
    tgt_scaler,
    model,
    test_year: int = 2024,
    window_size: int = 4,   # LSTM train config 일치: 4
    n_steps: int = 4,
) -> float | None:
    """test_year 이전 데이터만 사용하여 4스텝 자기회귀 예측 (데이터 누수 방지).

    predict.py를 직접 호출하지 않고 시퀀스를 직접 구성하는 이유:
    - predict.py는 전체 기간 데이터를 사용하므로 test_year 이후 데이터가 포함될 수 있음
    - 백테스트는 반드시 test_year 이전 데이터만 입력으로 사용해야 공정한 평가 가능
    - GRU backtest_gru.py의 _predict_revenue_gru() 와 동일한 방식

    Parameters
    ----------
    dong_code : str
        행정동 코드
    industry_code : str
        업종 코드
    timeseries_df : pd.DataFrame
        build_timeseries()로 생성된 전체 시계열 데이터
    feat_cols : list[str]
        실제 사용 가능한 피처 컬럼 목록
    feat_scaler : sklearn scaler
        피처 스케일러 (MinMaxScaler 등)
    tgt_scaler : sklearn scaler
        타겟 스케일러 (역변환용)
    model : LSTMForecaster
        로드된 LSTM 모델
    test_year : int
        평가 연도 — 이 연도 이전 데이터만 입력으로 사용
    window_size : int
        입력 시퀀스 길이 (LSTM: 4)
    n_steps : int
        예측할 분기 수 (연간 = 4분기)

    Returns
    -------
    float or None
        연간 예측 매출 합산. 데이터 부족 시 None 반환.
    """
    import numpy as np
    import torch

    # 해당 동×업종 시계열 추출 및 분기 정렬
    group = timeseries_df[
        (timeseries_df["dong_code"] == dong_code)
        & (timeseries_df["industry_code"] == industry_code)
    ].sort_values("quarter")

    # 데이터 누수 방지: test_year Q1 이전 데이터만 입력으로 사용
    # cutoff = test_year * 10 (예: 2024 → 20240)
    # quarter 형식: 연도4자리 + 분기1자리 (예: 20241, 20242, ...)
    cutoff = test_year * 10
    group_before = group[group["quarter"] < cutoff + 1]  # test_year Q1 미포함

    # 과거 데이터가 window_size보다 적으면 예측 불가
    if len(group_before) < window_size:
        return None

    # 마지막 window_size 분기를 입력 시퀀스로 사용
    recent = group_before[feat_cols].tail(window_size).values.astype(np.float32)
    seq = feat_scaler.transform(recent)

    # 타겟 컬럼 인덱스 — 자기회귀 시 예측값을 다음 입력에 반영하기 위해 필요
    target_idx = feat_cols.index("monthly_sales") if "monthly_sales" in feat_cols else 0
    device = next(model.parameters()).device

    # 4스텝 자기회귀 예측 루프 (sliding window)
    predictions: list[float] = []
    with torch.no_grad():
        current_seq = torch.from_numpy(seq).unsqueeze(0).to(device)

        for _ in range(n_steps):
            # LSTM 순전파 → 스케일된 예측값
            pred_scaled = model(current_seq)
            pred_val = pred_scaled.cpu().numpy().flatten()[0]

            # 역변환: scaled → log → 원래 매출 단위
            pred_log = tgt_scaler.inverse_transform([[pred_val]])[0][0]
            pred_original = float(np.expm1(pred_log))  # log1p 역변환
            predictions.append(max(0, pred_original))   # 음수 방지

            # 다음 입력 시퀀스 구성 (sliding window)
            new_step = current_seq[0, -1, :].clone()
            new_step[target_idx] = float(pred_val)  # 타겟 피처만 예측값으로 교체
            new_step = new_step.unsqueeze(0).unsqueeze(0)  # (1, 1, features)
            current_seq = torch.cat([current_seq[:, 1:, :], new_step], dim=1)

    # 4분기 예측 합산 → 연간 예측 매출
    return sum(predictions)


# ---------------------------------------------------------------------------
# 백테스트 메인 함수
# ---------------------------------------------------------------------------


def backtest_lstm(test_year: int = 2024, weights_suffix: str = "") -> dict:
    """LSTM 매출 예측 모델의 백테스트를 실행한다.

    2019~2023 데이터를 기반으로 2024년 4분기 매출을 예측하고
    실제 2024년 매출과 비교하여 정확도를 측정한다.

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
            "by_dong": {dong_name: {"mape": ..., "mae": ..., "n_samples": ...}, ...},
            "by_industry": {industry_name: {"mape": ..., "mae": ..., "n_samples": ...}, ...},
            "details": [{"dong_name": ..., "industry_name": ..., "actual": ..., "predicted": ...}, ...]
        }
    """
    import torch

    # LSTM 전용 모듈 import
    from models.lstm_forecast.model import WEIGHTS_DIR, LSTMForecaster
    from models.lstm_forecast.train import load_scalers

    # data_prep은 lstm_forecast에서 직접 import — GRU/TCN과 동일한 데이터 소스
    from models.lstm_forecast.data_prep import (
        ALL_FEATURES,
        EXCLUDE_COMBOS,  # 극단적 이상치 조합 (염리동 중식, 성산1동 제과) 제외용
        build_timeseries,
        load_sales_data,
        load_store_data,
    )

    # -----------------------------------------------------------------------
    # 1. 실제 매출 데이터 로드 (비교용)
    # -----------------------------------------------------------------------
    df = _load_sales_data()
    df = _normalize_columns(df)
    df["year"] = df["quarter"] // 10

    # test_year 실제 매출 추출
    df_actual = df[df["year"] == test_year].copy()
    if df_actual.empty:
        logger.warning("%d년 실제 매출 데이터가 없습니다.", test_year)
        return {"test_year": test_year, "error": f"{test_year}년 데이터 없음"}

    # 동×업종별 연간 매출 합산
    actual_agg = (
        df_actual.groupby(["dong_code", "dong_name", "industry_code", "industry_name"])
        .agg(actual_annual_sales=("monthly_sales", "sum"))
        .reset_index()
    )
    logger.info("실제 %d년 데이터: %d 조합", test_year, len(actual_agg))

    # -----------------------------------------------------------------------
    # 2. LSTM 모델 + 스케일러 로드
    # -----------------------------------------------------------------------
    # 파인튜닝 가중치 사용 (마포구 특화 학습 결과)
    # weights_suffix가 있으면 파일명에 추가 (예: run2 → _run2 → finetuned_mapo_run2.pt)
    # 없으면 기존 기본 파일명 그대로 사용
    _sfx = f"_{weights_suffix}" if weights_suffix else ""
    weights_path = WEIGHTS_DIR / f"finetuned_mapo{_sfx}.pt"
    scalers_path = WEIGHTS_DIR / f"finetune_scalers{_sfx}.pkl"

    if not weights_path.exists():
        return {
            "test_year": test_year,
            "error": f"LSTM 가중치 파일 없음: {weights_path}\n먼저 finetune을 실행하세요.",
        }

    if not scalers_path.exists():
        return {
            "test_year": test_year,
            "error": f"LSTM 스케일러 파일 없음: {scalers_path}",
        }

    # 스케일러 로드 — input_size 추론에도 사용
    feat_scaler, tgt_scaler = load_scalers(scalers_path)
    input_size = len(feat_scaler.scale_)

    # LSTM 모델 초기화 및 가중치 로드
    # hidden_size=128, num_layers=2: LSTM train config와 일치
    model = LSTMForecaster(
        input_size=input_size,
        hidden_size=128,
        num_layers=2,
        dropout=0.2,
    )
    model.load_weights(weights_path)
    device = torch.device("cpu")   # 추론은 CPU에서 수행
    model.to(device)
    model.eval()
    logger.info("LSTM 모델 로드 완료 (input_size=%d, hidden_size=128)", input_size)

    # -----------------------------------------------------------------------
    # 3. 시계열 데이터 구성 (전체 기간 — _predict_revenue_lstm 내부에서 cutoff 적용)
    # -----------------------------------------------------------------------
    sales_m = load_sales_data(dong_prefix="11440")   # 마포구 전체
    stores_m = load_store_data(dong_prefix="11440")
    ts_m = build_timeseries(sales_m, stores_m)

    # 실제 존재하는 피처 컬럼만 사용
    feat_cols_m = [c for c in ALL_FEATURES if c in ts_m.columns]
    logger.info("사용 피처 수: %d", len(feat_cols_m))

    # -----------------------------------------------------------------------
    # 4. 각 동×업종에 대해 LSTM 예측 수행 (데이터 누수 방지)
    # -----------------------------------------------------------------------
    predictions: list[dict] = []
    skipped = 0

    for _, row in actual_agg.iterrows():
        dong_code = str(row["dong_code"])
        industry_code = str(row["industry_code"])

        # 극단적 이상치 조합 제외 — MAPE 300%+ 조합은 백테스트 지표를 왜곡하므로 제외
        # (염리동 중식: 연간 860만원, 성산1동 제과: 연간 1,673만원 — 매출 규모가 너무 작아 MAPE 폭발)
        if (dong_code, industry_code) in EXCLUDE_COMBOS:
            skipped += 1
            logger.debug("이상치 조합 제외: dong=%s, industry=%s", dong_code, industry_code)
            continue

        # test_year 이전 데이터만 사용하여 4분기 자기회귀 예측
        pred_sales = _predict_revenue_lstm(
            dong_code=dong_code,
            industry_code=industry_code,
            timeseries_df=ts_m,
            feat_cols=feat_cols_m,
            feat_scaler=feat_scaler,
            tgt_scaler=tgt_scaler,
            model=model,
            test_year=test_year,
            window_size=4,  # LSTM train config 일치: 4
        )

        # 데이터 부족 시 건너뜀
        if pred_sales is None:
            skipped += 1
            logger.debug("데이터 부족 건너뜀: dong=%s, industry=%s", dong_code, industry_code)
            continue

        actual_val = float(row["actual_annual_sales"])

        # 개별 오차 계산 — 결과 CSV에 포함하기 위해 미리 계산
        abs_err = abs(actual_val - pred_sales)
        mape_val = abs(actual_val - pred_sales) / actual_val * 100 if actual_val != 0 else float("nan")

        predictions.append(
            {
                "test_year": test_year,
                "dong_code": dong_code,
                "dong_name": row["dong_name"],
                "industry_code": industry_code,
                "industry_name": row["industry_name"],
                "actual_annual_sales": actual_val,
                "predicted_annual_sales": float(pred_sales),
                "abs_error": round(abs_err, 0),
                "mape_pct": round(mape_val, 2),
            }
        )

    logger.info(
        "예측 완료: %d건 성공 / %d건 건너뜀 (전체 %d건)",
        len(predictions),
        skipped,
        len(actual_agg),
    )

    # 예측 결과가 하나도 없으면 오류 반환
    if not predictions:
        logger.error("모델 예측 결과 없음 — 가중치 파일 또는 데이터를 확인하세요.")
        return {
            "test_year": test_year,
            "error": "모델 예측 실패 — 가중치 파일이 없거나 데이터 부족",
            "skipped": skipped,
        }

    pred_df = pd.DataFrame(predictions)
    actual_vals = pred_df["actual_annual_sales"].values
    pred_vals = pred_df["predicted_annual_sales"].values

    # -----------------------------------------------------------------------
    # 5. 전체 정확도 계산 (accuracy_metrics.py 재사용)
    # -----------------------------------------------------------------------
    full_report = generate_accuracy_report(actual_vals, pred_vals)
    overall_report = full_report["overall"]
    overall_report["n_samples"] = len(actual_vals)

    # -----------------------------------------------------------------------
    # 6. 동별 세분화 리포트
    # -----------------------------------------------------------------------
    by_dong: dict = {}
    for dong_name, grp in pred_df.groupby("dong_name"):
        a = grp["actual_annual_sales"].values
        p = grp["predicted_annual_sales"].values
        by_dong[dong_name] = {
            "mape": round(mape(a, p), 2),
            "mae": round(mae(a, p), 0),
            "n_samples": len(a),
        }

    # -----------------------------------------------------------------------
    # 7. 업종별 세분화 리포트
    # -----------------------------------------------------------------------
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
        "details": predictions,  # CSV 저장에도 사용
    }


# ---------------------------------------------------------------------------
# 결과 CSV 저장 함수
# ---------------------------------------------------------------------------


def save_results_csv(result: dict, results_csv: Path | None = None) -> Path:
    """백테스트 결과를 CSV 파일로 저장한다.

    결과 재현성과 GRU/TCN과의 비교 분석을 위해 CSV 저장.
    GRU backtest_gru.py의 save_results_csv() 와 동일한 구조.

    Parameters
    ----------
    result : dict
        backtest_lstm()의 반환값
    results_csv : Path, optional
        저장할 CSV 경로. None이면 기본값(RESULTS_CSV) 사용.
        --weights-suffix 실행 시 suffix 포함 경로를 전달하면 별도 파일로 저장됨.

    Returns
    -------
    Path
        저장된 CSV 파일 경로
    """
    # 오류 결과는 저장하지 않음
    if "error" in result:
        logger.warning("오류 결과는 저장하지 않습니다: %s", result["error"])
        return None

    # 저장 경로: 인자로 받은 경로 우선, 없으면 모듈 기본 경로(RESULTS_CSV) 사용
    csv_path = results_csv if results_csv is not None else RESULTS_CSV

    # results 디렉토리 없으면 생성
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 상세 결과를 DataFrame으로 변환 후 저장
    df = pd.DataFrame(result["details"])

    # 컬럼 순서 정렬: 가독성을 위해 중요 컬럼을 앞으로
    col_order = [
        "test_year",
        "dong_code",
        "dong_name",
        "industry_code",
        "industry_name",
        "actual_annual_sales",
        "predicted_annual_sales",
        "abs_error",
        "mape_pct",
    ]
    df = df[[c for c in col_order if c in df.columns]]

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info("결과 저장 완료: %s (%d rows)", csv_path, len(df))

    return csv_path


# ---------------------------------------------------------------------------
# 결과 출력 함수
# ---------------------------------------------------------------------------


def print_report_lstm(result: dict) -> None:
    """백테스트 결과를 콘솔에 포맷팅하여 출력한다.

    GRU backtest_gru.py의 print_report_gru() 와 동일한 형식.
    동별/업종별 MAPE를 오름차순 정렬하여 출력한다.
    """
    if "error" in result:
        print(f"\n[ERROR] {result['error']}")
        return

    test_year = result["test_year"]
    ov = result["overall"]

    # 전체 정확도 출력
    print(f"\n=== LSTM 매출 예측 백테스팅 ({test_year}) ===")
    print(f"전체 MAPE:  {ov['mape']:.1f}%")
    print(f"전체 MAE:   {ov['mae']:,.0f}원")
    print(f"전체 RMSE:  {ov['rmse']:,.0f}원")
    print(f"전체 R²:    {ov['r_squared']:.4f}")
    print(f"샘플 수:    {ov['n_samples']}")

    # 동별 MAPE — 오름차순 정렬 (낮을수록 정확)
    print("\n동별 MAPE:")
    for dong, info in sorted(result["by_dong"].items(), key=lambda x: x[1]["mape"]):
        print(f"  {dong}: {info['mape']:.1f}%  (n={info['n_samples']})")

    # 업종별 MAPE — 오름차순 정렬
    print("\n업종별 MAPE:")
    for ind, info in sorted(result["by_industry"].items(), key=lambda x: x[1]["mape"]):
        print(f"  {ind}: {info['mape']:.1f}%  (n={info['n_samples']})")


# ---------------------------------------------------------------------------
# CLI 진입점
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    # 로그 설정
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="LSTM 매출 예측 백테스팅")
    parser.add_argument(
        "--year",
        type=int,
        default=2024,
        help="평가 대상 연도 (기본 2024)",
    )
    parser.add_argument(
        "--weights-suffix",
        type=str,
        default="",
        help="가중치/스케일러/CSV 파일명 suffix (예: run2 → finetuned_mapo_run2.pt, lstm_backtest_results_run2.csv)",
    )
    args = parser.parse_args()

    # 백테스트 실행 — weights_suffix 전달 (기본값 "" = 기존 동작 유지)
    result = backtest_lstm(test_year=args.year, weights_suffix=args.weights_suffix)

    # 콘솔 출력
    print_report_lstm(result)

    # CSV 저장 (오류 없을 경우에만)
    if "error" not in result:
        # suffix가 있으면 결과 CSV도 suffix 포함 파일명으로 저장
        # 없으면 기본 파일명(lstm_backtest_results.csv) 그대로 사용
        _sfx = f"_{args.weights_suffix}" if args.weights_suffix else ""
        results_csv = RESULTS_DIR / f"lstm_backtest_results{_sfx}.csv"
        saved_path = save_results_csv(result, results_csv=results_csv)
        if saved_path:
            print(f"\n결과 저장 완료: {saved_path}")
