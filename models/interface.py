"""
A1 → B2 인터페이스 모듈

A1(찬영) 딥러닝 모델 출력을 B2(수지니) 12개월 시뮬레이션 입력으로
전달하기 위한 통합 인터페이스.

- lstm_forecast : 월 예상매출, 신뢰구간
- revenue_predictor : 생존률, 리스크 레벨, 12개월 월별 생존률
- revenue_predictor/bep : BEP 개월수, 분기별 손익

모델 가중치가 없는 개발 환경에서는 mock 데이터를 반환한다.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MODEL_VERSION = "0.1.0"
DATA_PERIOD = "2019Q1~2024Q4"


# ---------------------------------------------------------------------------
# Mock 데이터 생성
# ---------------------------------------------------------------------------


def _mock_revenue_forecast() -> dict:
    """LSTM 매출 예측 mock 데이터 (4분기)."""
    base_sales = 15_000_000.0
    quarterly_predictions = []
    for q in range(1, 5):
        sales = base_sales * (1 + 0.03 * q)  # 완만한 상승 추세
        margin = sales * 0.05 * q
        quarterly_predictions.append(
            {
                "quarter_offset": q,
                "predicted_sales": round(sales),
                "confidence_lower": round(max(0, sales - margin)),
                "confidence_upper": round(sales + margin),
            }
        )
    quarterly_avg = sum(p["predicted_sales"] for p in quarterly_predictions) / 4
    return {
        "quarterly_avg": round(quarterly_avg),
        "quarterly_predictions": quarterly_predictions,
    }


def _mock_survival() -> dict:
    """생존률 mock 데이터."""
    survival_rate = 0.72
    monthly_decay = survival_rate ** (1 / 3)
    monthly_rates = []
    cumulative = 1.0
    for _ in range(12):
        cumulative *= monthly_decay
        monthly_rates.append(round(max(0.0, min(1.0, cumulative)), 4))
    return {
        "survival_rate": survival_rate,
        "risk_level": "safe",
        "monthly_survival_rates": monthly_rates,
    }


def _mock_bep(industry_name: str) -> dict:
    """BEP mock 데이터."""
    from models.revenue_predictor.bep import BEPCalculator

    cost_cfg = BEPCalculator.get_default_costs(industry_name)
    calc = BEPCalculator(cost_cfg)
    monthly_revenue = 15_000_000.0
    bep_result = calc.calculate_bep(monthly_revenue)

    monthly_simulation = calc.simulate_monthly([monthly_revenue] * 12)
    # simulate_monthly 에는 cost 키가 없으므로 변환
    simulation = []
    for row in monthly_simulation:
        simulation.append(
            {
                "month": row["month"],
                "revenue": row["revenue"],
                "cost": row["total_cost"],
                "profit": row["profit"],
                "cumulative_profit": row["cumulative_profit"],
                "bep_reached": row["bep_reached"],
            }
        )

    return {
        "bep_months": bep_result["bep_months"],
        "monthly_profit": bep_result["monthly_profit"],
        "total_initial_investment": bep_result["total_initial_investment"],
        "annual_roi": bep_result["annual_roi"],
        "quarterly_simulation": simulation,  # 실제 4개 분기 데이터 (키명 quarterly로 정정)
    }


# ---------------------------------------------------------------------------
# 실제 모델 호출 헬퍼
# ---------------------------------------------------------------------------


def _run_lstm_forecast(dong_code: str, industry_code: str) -> dict:
    """LSTM 매출 예측 모델 호출 → 분기별 결과 반환."""
    from models.lstm_forecast.predict import predict as lstm_predict

    quarterly_results = lstm_predict(dong_code, industry_code, n_months=4)

    quarterly_avg = (
        sum(qr["predicted_sales"] for qr in quarterly_results) / len(quarterly_results) if quarterly_results else 0.0
    )

    return {
        "quarterly_avg": round(quarterly_avg),
        "quarterly_predictions": quarterly_results,
    }


def _run_tcn_forecast(dong_code: str, industry_code: str) -> dict:
    """TCN 매출 예측 모델 호출 → 분기별 결과 반환."""
    from models.tcn_forecast.predict import predict as tcn_predict

    quarterly_results = tcn_predict(dong_code, industry_code, n_months=4)

    quarterly_avg = (
        sum(qr["predicted_sales"] for qr in quarterly_results) / len(quarterly_results) if quarterly_results else 0.0
    )

    return {
        "quarterly_avg": round(quarterly_avg),
        "quarterly_predictions": quarterly_results,
    }


def _run_gru_forecast(dong_code: str, industry_code: str) -> dict:
    """GRU 매출 예측 모델 호출 → 분기별 결과 반환."""
    from models.gru_forecast.predict import predict as gru_predict

    quarterly_results = gru_predict(dong_code, industry_code, n_months=4)

    quarterly_avg = (
        sum(qr["predicted_sales"] for qr in quarterly_results) / len(quarterly_results) if quarterly_results else 0.0
    )

    return {
        "quarterly_avg": round(quarterly_avg),
        "quarterly_predictions": quarterly_results,
    }


def _run_survival(dong_code: str, industry_code: str) -> dict:
    """생존률 예측 모델 호출."""
    from models.revenue_predictor.predict import predict as survival_predict

    result = survival_predict(dong_code, industry_code)
    return {
        "survival_rate": result["survival_rate"],
        "risk_level": result["closure_risk_level"],
        "monthly_survival_rates": result["monthly_survival_rates"],
    }


def _run_bep(
    quarterly_avg: float,  # 분기 평균 매출 (파라미터명 quarterly로 정정)
    quarterly_predictions: list[dict],  # 분기 예측 4개 (파라미터명 quarterly로 정정)
    industry_name: str,
    cost_config: dict | None,
) -> dict:
    """BEP 계산."""
    from models.revenue_predictor.bep import BEPCalculator

    if cost_config is None:
        cost_config = BEPCalculator.get_default_costs(industry_name)

    calc = BEPCalculator(cost_config)
    bep_result = calc.calculate_bep(quarterly_avg)  # 분기 평균 매출로 BEP 계산

    quarterly_revenues = [p["predicted_sales"] for p in quarterly_predictions]  # 분기별 매출 리스트
    quarterly_simulation_raw = calc.simulate_monthly(quarterly_revenues)  # simulate_monthly 함수명은 bep.py 유지
    simulation = []
    for row in quarterly_simulation_raw:  # 분기 시뮬레이션 루프
        simulation.append(
            {
                "month": row["month"],
                "revenue": row["revenue"],
                "cost": row["total_cost"],
                "profit": row["profit"],
                "cumulative_profit": row["cumulative_profit"],
                "bep_reached": row["bep_reached"],
            }
        )

    return {
        "bep_months": bep_result["bep_months"],
        "monthly_profit": bep_result["monthly_profit"],
        "total_initial_investment": bep_result["total_initial_investment"],
        "annual_roi": bep_result["annual_roi"],
        "quarterly_simulation": simulation,  # 분기별 4개 시뮬레이션 결과
    }


# ---------------------------------------------------------------------------
# 동 이름 조회
# ---------------------------------------------------------------------------


def _resolve_dong_name(dong_code: str) -> str:
    """dong_code → dong_name 변환. 실패 시 dong_code 그대로 반환."""
    try:
        from backend.src.services.dong_resolver import resolve_dong_name

        name = resolve_dong_name(dong_code)
        if name:
            return name
    except Exception:
        pass

    # fallback: 데이터에서 조회
    try:
        from models.revenue_predictor.data_prep import load_store_data

        df = load_store_data(seoul=False)
        match = df.loc[df["dong_code"].astype(str) == str(dong_code), "dong_name"]
        if not match.empty:
            return str(match.iloc[0])
    except Exception:
        logger.debug("dong_name 조회 실패 — dong_code를 그대로 사용합니다")
    return dong_code


# ---------------------------------------------------------------------------
# 통합 출력 클래스
# ---------------------------------------------------------------------------


class ModelOutput:
    """A1 모델 통합 출력 -- B2 시뮬레이션 입력용"""

    @staticmethod
    async def generate_with_brand(
        dong_code: str,
        industry_code: str,
        industry_name: str,
        brand_name: str,
        dong_name: str,
        ftc_api_key: str,
        db_session: AsyncSession,
        cost_config: dict | None = None,
    ) -> dict:
        """generate() 결과에 FTC 브랜드 비교 분석을 추가.

        Parameters
        ----------
        dong_code, industry_code, industry_name, cost_config :
            ``generate()``와 동일.
        brand_name : str
            FTC 브랜드명 (예: ``"메가커피"``).
        dong_name : str
            행정동명 (예: ``"망원동"``).
        ftc_api_key : str
            공정위 API 키.
        db_session : AsyncSession
            SQLAlchemy 비동기 세션.

        Returns
        -------
        dict
            ``generate()`` 결과 + ``brand_comparison`` 필드.
        """
        from src.services.ftc_franchise import FtcFranchiseClient

        # 1) 기존 모델 파이프라인
        result = ModelOutput.generate(dong_code, industry_code, industry_name, cost_config)

        # 2) FTC 브랜드 비교
        try:
            ftc_client = FtcFranchiseClient(ftc_api_key)
            comparison = await ftc_client.compare_brand_to_district(
                brand_name=brand_name,
                dong_name=dong_name,
                session=db_session,
            )
            result["brand_comparison"] = comparison
            logger.info("FTC 브랜드 비교 완료: %s", brand_name)
        except Exception as exc:
            logger.warning("FTC 브랜드 비교 실패: %s", exc)
            result["brand_comparison"] = {"error": str(exc)}

        return result

    @staticmethod
    def generate(
        dong_code: str,
        industry_code: str,
        industry_name: str,
        cost_config: dict | None = None,
        model: str = "lstm",
    ) -> dict:
        """전체 모델 파이프라인 실행 후 통합 결과 반환.

        모델 가중치가 없는 환경에서는 mock 데이터를 반환하므로
        B2 개발을 즉시 시작할 수 있다.

        Parameters
        ----------
        dong_code : str
            행정동 코드 (예: ``"1144053"``).
        industry_code : str
            업종 코드 (예: ``"CS100001"``).
        industry_name : str
            업종명 (예: ``"한식음식점"``). BEP 기본 비용 구조에 사용.
        cost_config : dict | None
            BEP 계산에 사용할 비용 구조. ``None`` 이면 업종별 기본값 사용.

        Returns
        -------
        dict
            아래 구조의 통합 결과::

                {
                    "input": { dong_code, dong_name, industry_code, industry_name },
                    "revenue_forecast": { quarterly_avg, quarterly_predictions },
                    "survival": { survival_rate, risk_level, monthly_survival_rates },
                    "bep": { bep_months, monthly_profit, total_initial_investment,
                             annual_roi, quarterly_simulation },
                    "metadata": { model_version, generated_at, data_period },
                }
        """
        use_mock = False

        # ---- 1) 매출 예측 (모델 선택: lstm / tcn / gru) ----
        forecast_fn = {
            "lstm": _run_lstm_forecast,
            "tcn": _run_tcn_forecast,
            "gru": _run_gru_forecast,
        }.get(model, _run_lstm_forecast)

        try:
            revenue_forecast = forecast_fn(dong_code, industry_code)
            logger.info("%s 매출 예측 완료", model.upper())
        except Exception as exc:
            logger.warning("%s 매출 예측 실패 (mock 사용): %s", model.upper(), exc)
            revenue_forecast = _mock_revenue_forecast()
            use_mock = True

        # ---- 2) 생존률 예측 ----
        try:
            survival = _run_survival(dong_code, industry_code)
            logger.info("생존률 예측 완료")
        except Exception as exc:
            logger.warning("생존률 예측 실패 (mock 사용): %s", exc)
            survival = _mock_survival()
            use_mock = True

        # ---- 3) BEP 계산 ----
        try:
            quarterly_avg = revenue_forecast["quarterly_avg"]
            quarterly_preds = revenue_forecast["quarterly_predictions"]
            bep = _run_bep(
                quarterly_avg=quarterly_avg,  # 분기 평균 매출 전달
                quarterly_predictions=quarterly_preds,  # 분기 예측 4개 전달
                industry_name=industry_name,
                cost_config=cost_config,
            )
            logger.info("BEP 계산 완료")
        except Exception as exc:
            logger.warning("BEP 계산 실패 (mock 사용): %s", exc)
            bep = _mock_bep(industry_name)
            use_mock = True

        # ---- dong_name 조회 ----
        dong_name = _resolve_dong_name(dong_code) if not use_mock else dong_code

        return {
            "input": {
                "dong_code": dong_code,
                "dong_name": dong_name,
                "industry_code": industry_code,
                "industry_name": industry_name,
            },
            "revenue_forecast": revenue_forecast,
            "survival": survival,
            "bep": bep,
            "metadata": {
                "model_version": MODEL_VERSION,
                "generated_at": datetime.now(tz=UTC).isoformat(),
                "data_period": DATA_PERIOD,
            },
        }
