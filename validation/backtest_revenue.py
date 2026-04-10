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
        from sqlalchemy import create_engine, text

        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            df = pd.read_sql(text("SELECT * FROM district_sales"), conn)
        engine.dispose()
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


def _predict_revenue(
    dong_code: str,
    industry_code: str,
    timeseries_df: pd.DataFrame,
    feat_cols: list[str],
    feat_scaler,
    tgt_scaler,
    model,
    test_year: int = 2024,
    window_size: int = 6,
    n_steps: int = 4,
) -> float | None:
    """test_year 이전 데이터만 사용하여 4스텝 자기회귀 예측.

    데이터 누수를 방지하기 위해 predict.py를 호출하지 않고
    직접 시퀀스를 구성한다.
    """
    import numpy as np
    import torch

    group = timeseries_df[
        (timeseries_df["dong_code"] == dong_code) & (timeseries_df["industry_code"] == industry_code)
    ].sort_values("quarter")

    # test_year 이전 데이터만 입력으로 사용
    cutoff = test_year * 10  # 예: 20240
    group_before = group[group["quarter"] < cutoff + 1]  # test_year Q1 미포함

    if len(group_before) < window_size:
        return None

    # 마지막 window_size 분기를 입력으로 사용
    recent = group_before[feat_cols].tail(window_size).values.astype(np.float32)
    seq = feat_scaler.transform(recent)

    target_idx = feat_cols.index("monthly_sales") if "monthly_sales" in feat_cols else 0
    device = next(model.parameters()).device

    # 4스텝 자기회귀 예측
    predictions = []
    with torch.no_grad():
        current_seq = torch.from_numpy(seq).unsqueeze(0).to(device)
        for _ in range(n_steps):
            pred_scaled = model(current_seq)
            pred_val = pred_scaled.cpu().numpy().flatten()[0]
            pred_log = tgt_scaler.inverse_transform([[pred_val]])[0][0]
            pred_original = float(np.expm1(pred_log))
            predictions.append(max(0, pred_original))

            new_step = current_seq[0, -1, :].clone()
            new_step[target_idx] = float(pred_val)
            new_step = new_step.unsqueeze(0).unsqueeze(0)
            current_seq = torch.cat([current_seq[:, 1:, :], new_step], dim=1)

    return sum(predictions)


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
    import torch

    from models.lstm_forecast.data_prep import (
        ALL_FEATURES,
        build_timeseries,
        load_sales_data,
        load_store_data,
    )
    from models.lstm_forecast.model import WEIGHTS_DIR, LSTMForecaster
    from models.lstm_forecast.train import load_scalers

    # 1. 매출 데이터 로드 (실제값 비교용)
    df = _load_sales_data()
    df = _normalize_columns(df)
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

    # 3. 모델 + 스케일러 + 시계열 데이터 로드
    weights_path = WEIGHTS_DIR / "finetuned_mapo_v9.pt"
    scalers_path = WEIGHTS_DIR / "finetune_v9_scalers.pkl"

    if not weights_path.exists():
        # v9 없으면 v6b 폴백
        weights_path = WEIGHTS_DIR / "finetuned_mapo_v6b.pt"
        scalers_path = WEIGHTS_DIR / "finetune_v6b_scalers.pkl"

    feat_scaler, tgt_scaler = load_scalers(scalers_path)
    input_size = len(feat_scaler.scale_)

    model = LSTMForecaster(input_size=input_size, hidden_size=256, num_layers=2, dropout=0.2)
    model.load_weights(weights_path)
    device = torch.device("cpu")
    model.to(device)
    model.eval()

    # 시계열 구성 (전체 기간 — 내부에서 test_year 이전만 사용)
    sales_m = load_sales_data(dong_prefix="11440")
    stores_m = load_store_data(dong_prefix="11440")
    ts_m = build_timeseries(sales_m, stores_m)
    feat_cols_m = [c for c in ALL_FEATURES if c in ts_m.columns]

    # 4. 각 동×업종에 대해 모델 예측 수행 (데이터 누수 방지)
    predictions: list[dict] = []
    skipped = 0

    for _, row in actual_agg.iterrows():
        dong_code = str(row["dong_code"])
        industry_code = str(row["industry_code"])
        pred_sales = _predict_revenue(
            dong_code,
            industry_code,
            timeseries_df=ts_m,
            feat_cols=feat_cols_m,
            feat_scaler=feat_scaler,
            tgt_scaler=tgt_scaler,
            model=model,
            test_year=test_year,
        )

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
# FTC 브랜드 비교 백테스트
# ---------------------------------------------------------------------------

# 공공데이터포털 공정위 가맹정보 API
_FTC_DATA_API = "https://apis.data.go.kr/1130000/FftcBrandFrcsStatsService/getBrandFrcsStats"

# 브랜드명 → (업종코드, API 검색 키워드)
TEST_BRANDS = [
    {"name": "교촌치킨", "industry_code": "CS100007", "keyword": "교촌치킨"},
    {"name": "BHC", "industry_code": "CS100007", "keyword": "비에이치씨(BHC)"},
    {"name": "굽네치킨", "industry_code": "CS100007", "keyword": "굽네치킨"},
    {"name": "이디야커피", "industry_code": "CS100010", "keyword": "이디야커피"},
    {"name": "파리바게뜨", "industry_code": "CS100005", "keyword": "파리바게뜨"},
    {"name": "신전떡볶이", "industry_code": "CS100008", "keyword": "신전떡볶이"},
    {"name": "본죽", "industry_code": "CS100001", "keyword": "본죽"},
]


async def _fetch_brand_annual_sales(brands: list[dict], yr: str = "2023") -> dict[str, int]:
    """공공데이터포털 공정위 가맹정보 API에서 브랜드별 연평균 매출 조회.

    Returns
    -------
    dict[str, int]
        {브랜드명: 연평균매출(원)}. avrgSlsAmt 단위는 천원이므로 ×1000.
    """
    import httpx

    api_key = os.environ.get("FTC_API_KEY")
    if not api_key:
        raise ValueError("FTC_API_KEY 환경변수를 설정하세요.")

    # 전체 데이터 수집 (페이지네이션)
    all_items: list[dict] = []
    async with httpx.AsyncClient(timeout=30) as client:
        # 먼저 총 건수 확인
        params = {
            "serviceKey": api_key,
            "pageNo": "1",
            "numOfRows": "1",
            "resultType": "json",
            "yr": yr,
        }
        r = await client.get(_FTC_DATA_API, params=params)
        total = r.json().get("totalCount", 0)
        logger.info("FTC API 총 %d건 (yr=%s)", total, yr)

        # 100건씩 페이지 수집
        pages = (total // 100) + 1
        for page in range(1, pages + 1):
            params = {
                "serviceKey": api_key,
                "pageNo": str(page),
                "numOfRows": "100",
                "resultType": "json",
                "yr": yr,
            }
            r = await client.get(_FTC_DATA_API, params=params)
            items = r.json().get("items", [])
            all_items.extend(items)
            if len(items) < 100:
                break

    logger.info("FTC API 수집 완료: %d건", len(all_items))

    # 브랜드 매칭
    result = {}
    for brand in brands:
        keyword = brand["keyword"]
        matched = [i for i in all_items if keyword in i.get("brandNm", "")]
        if matched and matched[0].get("avrgSlsAmt", 0) > 0:
            amt = matched[0]["avrgSlsAmt"] * 1000  # 천원 → 원
            result[brand["name"]] = amt
            logger.info(
                "FTC: %s = %s원 (가맹점 %d개)",
                brand["name"],
                f"{amt:,}",
                matched[0].get("frcsCnt", 0),
            )
        else:
            logger.warning("FTC 매출 없음: %s", brand["name"])

    return result


async def backtest_brand_comparison(test_year: int = 2024) -> dict:
    """브랜드 보정계수를 적용한 점포당 예상매출 vs FTC 브랜드 매출 비교.

    보정계수 = FTC 브랜드 평균매출 / 마포구 업종 평균 점포당 매출
    브랜드 예상매출 = 모델 예측 점포당 매출 × 보정계수

    Returns
    -------
    dict
        test_year, correction_factors, summary_by_brand, details
    """
    import numpy as np
    import torch

    from models.lstm_forecast.data_prep import (
        ALL_FEATURES,
        build_timeseries,
        load_sales_data,
        load_store_data,
    )
    from models.lstm_forecast.model import WEIGHTS_DIR, LSTMForecaster
    from models.lstm_forecast.train import load_scalers

    # 1. 모델 로드
    weights_path = WEIGHTS_DIR / "finetuned_mapo_v9.pt"
    scalers_path = WEIGHTS_DIR / "finetune_v9_scalers.pkl"
    if not weights_path.exists():
        weights_path = WEIGHTS_DIR / "finetuned_mapo_v6b.pt"
        scalers_path = WEIGHTS_DIR / "finetune_v6b_scalers.pkl"

    feat_scaler, tgt_scaler = load_scalers(scalers_path)
    input_size = len(feat_scaler.scale_)

    model = LSTMForecaster(input_size=input_size, hidden_size=256, num_layers=2, dropout=0.2)
    model.load_weights(weights_path)
    device = torch.device("cpu")
    model.to(device)
    model.eval()

    # 2. 데이터 로드
    sales_m = load_sales_data(dong_prefix="11440")
    stores_m = load_store_data(dong_prefix="11440")
    ts_m = build_timeseries(sales_m, stores_m)
    feat_cols_m = [c for c in ALL_FEATURES if c in ts_m.columns]

    # 점포 수 준비
    stores_copy = stores_m.copy()
    stores_copy["dong_code"] = stores_copy["dong_code"].astype(str)
    stores_copy["industry_code"] = stores_copy["industry_code"].astype(str)
    stores_copy["year"] = stores_copy["quarter"].astype(int) // 10

    # test_year 동×업종별 평균 점포 수
    store_avg = (
        stores_copy[stores_copy["year"] == test_year].groupby(["dong_code", "industry_code"])["store_count"].mean()
    )

    # 동코드 → 동이름
    dong_map = {}
    if "dong_name" in sales_m.columns:
        for _, r in sales_m[["dong_code", "dong_name"]].drop_duplicates().iterrows():
            dong_map[str(r["dong_code"])] = r["dong_name"]

    # 3. FTC 브랜드 매출 조회
    brand_sales = await _fetch_brand_annual_sales(TEST_BRANDS)
    if not brand_sales:
        return {"test_year": test_year, "error": "FTC 브랜드 매출을 조회할 수 없습니다."}

    # 4. 브랜드 보정계수 계산
    #    보정계수 = FTC 브랜드 평균매출 / 마포구 업종 평균 점포당 연매출
    base_year = test_year - 1  # 데이터 누수 방지: 직전 연도 사용

    # 마포구 업종별 평균 점포당 연매출 (base_year 실제 데이터)
    sales_copy = sales_m.copy()
    sales_copy["dong_code"] = sales_copy["dong_code"].astype(str)
    sales_copy["industry_code"] = sales_copy["industry_code"].astype(str)
    sales_copy["year"] = sales_copy["quarter"].astype(int) // 10

    base_sales = sales_copy[sales_copy["year"] == base_year]
    ind_annual_sales = base_sales.groupby("industry_code")["monthly_sales"].sum()

    base_stores = stores_copy[stores_copy["year"] == base_year]
    ind_stores_per_q = (
        base_stores.groupby(["industry_code", "quarter"])["store_count"].sum().groupby("industry_code").mean()
    )

    industry_avg_per_store = (ind_annual_sales / ind_stores_per_q).to_dict()

    correction_factors = {}
    for brand in TEST_BRANDS:
        ftc_annual = brand_sales.get(brand["name"])
        if not ftc_annual:
            continue
        ind_avg = industry_avg_per_store.get(brand["industry_code"], 0)
        if ind_avg > 0:
            factor = ftc_annual / ind_avg
        else:
            factor = 1.0
        correction_factors[brand["name"]] = {
            "factor": round(factor, 3),
            "ftc_annual": ftc_annual,
            "industry_avg": round(ind_avg),
            "industry_code": brand["industry_code"],
        }

    # 5. 동×업종별 모델 예측 + 보정계수 적용
    comparisons = []
    for brand in TEST_BRANDS:
        ftc_annual = brand_sales.get(brand["name"])
        if not ftc_annual or brand["name"] not in correction_factors:
            continue

        industry_code = brand["industry_code"]
        factor = correction_factors[brand["name"]]["factor"]
        dong_codes = ts_m[ts_m["industry_code"] == industry_code]["dong_code"].unique()

        for dc in dong_codes:
            dc = str(dc)
            pred_annual = _predict_revenue(
                dc,
                industry_code,
                timeseries_df=ts_m,
                feat_cols=feat_cols_m,
                feat_scaler=feat_scaler,
                tgt_scaler=tgt_scaler,
                model=model,
                test_year=test_year,
            )
            if pred_annual is None:
                continue

            sc = store_avg.get((dc, industry_code), 0)
            if sc <= 0:
                continue

            pred_per_store = pred_annual / sc
            brand_adjusted = pred_per_store * factor
            dong_name = dong_map.get(dc, dc)

            comparisons.append(
                {
                    "brand": brand["name"],
                    "dong_name": dong_name,
                    "industry_code": industry_code,
                    "store_count": round(sc, 1),
                    "pred_industry_avg": round(pred_per_store),
                    "correction_factor": factor,
                    "brand_adjusted": round(brand_adjusted),
                    "ftc_brand_annual": ftc_annual,
                    "ratio": round(brand_adjusted / ftc_annual * 100, 1) if ftc_annual > 0 else 0,
                }
            )

    if not comparisons:
        return {"test_year": test_year, "error": "비교 가능한 데이터가 없습니다."}

    # 6. 브랜드별 요약
    df = pd.DataFrame(comparisons)
    summary = {}
    for brand_name, grp in df.groupby("brand"):
        adjusted_vals = grp["brand_adjusted"].values
        ftc_val = grp["ftc_brand_annual"].values[0]
        avg_adjusted = float(np.mean(adjusted_vals))
        mape_val = float(np.mean(np.abs(adjusted_vals - ftc_val) / ftc_val) * 100)
        summary[brand_name] = {
            "ftc_annual": int(ftc_val),
            "avg_brand_adjusted": int(avg_adjusted),
            "ratio": round(avg_adjusted / ftc_val * 100, 1) if ftc_val > 0 else 0,
            "mape_vs_ftc": round(mape_val, 1),
            "correction_factor": correction_factors[brand_name]["factor"],
            "industry_avg": correction_factors[brand_name]["industry_avg"],
            "n_dongs": len(grp),
        }

    return {
        "test_year": test_year,
        "correction_factors": correction_factors,
        "summary_by_brand": summary,
        "details": comparisons,
    }


def print_brand_report(result: dict) -> None:
    """브랜드 비교 백테스트 결과 출력."""
    if "error" in result:
        print(f"\n[ERROR] {result['error']}")
        return

    print(f"\n=== 브랜드 보정 예상매출 vs FTC 실제매출 ({result['test_year']}) ===")

    # 보정계수 표
    print("\n[보정계수]")
    for name, cf in result.get("correction_factors", {}).items():
        print(f"  {name}: ×{cf['factor']:.2f}  (FTC {cf['ftc_annual']:,}원 / 업종평균 {cf['industry_avg']:,}원)")

    # 브랜드별 요약
    print("\n[브랜드별 요약]")
    for brand_name, info in result["summary_by_brand"].items():
        print(f"\n  [{brand_name}] 보정계수 ×{info['correction_factor']:.2f}")
        print(f"    FTC 연평균:     {info['ftc_annual']:,}원")
        print(f"    보정 예측 평균: {info['avg_brand_adjusted']:,}원 ({info['ratio']}%)")
        print(f"    MAPE: {info['mape_vs_ftc']:.1f}% | 동 수: {info['n_dongs']}")

    # 동별 상세
    details = result["details"]
    print("\n[동별 상세]")
    seen_brands = []
    for d in details:
        if d["brand"] not in seen_brands:
            seen_brands.append(d["brand"])

    for brand_name in seen_brands:
        print(f"\n  [{brand_name}] (×{details[0]['correction_factor']:.2f})")
        brand_details = sorted(
            [d for d in details if d["brand"] == brand_name],
            key=lambda x: x["ratio"],
            reverse=True,
        )
        for d in brand_details:
            print(
                f"    {d['dong_name']}: "
                f"{d['brand_adjusted']:,}원 "
                f"(업종평균 {d['pred_industry_avg']:,}원 × {d['correction_factor']:.2f}) "
                f"→ FTC 대비 {d['ratio']}%"
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import asyncio

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    parser = argparse.ArgumentParser(description="매출 예측 백테스팅")
    parser.add_argument(
        "--mode",
        choices=["model", "brand"],
        default="brand",
        help="model: 모델 예측 vs 실제매출, brand: 모델 예측 vs FTC 브랜드",
    )
    args = parser.parse_args()

    if args.mode == "model":
        result = backtest_revenue(test_year=2024)
        print_report(result)
    else:
        result = asyncio.run(backtest_brand_comparison(test_year=2024))
        print_brand_report(result)
