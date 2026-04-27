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

from models.lstm_forecast.data_prep import EXCLUDE_COMBOS, ExcludedComboError

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
        "is_mock": True,
    }


def _mock_closure_rate() -> dict:
    """폐업률 계산 실패 시 반환 — predict._mock_result() 구조와 동일."""
    from models.revenue_predictor.predict import _mock_result as _closure_mock

    raw = _closure_mock()
    return {
        "closure_rate": raw["closure_rate"],
        "risk_level": raw["closure_rate_level"],
        "monthly_closure_rates": raw["monthly_closure_rates"],
        "is_mock": True,
    }


def _mock_bep(industry_name: str) -> dict:
    """BEP mock 데이터."""
    from models.revenue_predictor.bep import BEPCalculator

    cost_cfg = BEPCalculator.get_default_costs(industry_name)
    calc = BEPCalculator(cost_cfg)
    quarterly_revenue = 45_000_000.0  # 분기 매출 (월 15M × 3)
    bep_result = calc.calculate_bep(quarterly_revenue)

    simulation_quarters = 8  # mock은 2년 고정
    quarterly_simulation_raw = calc.simulate_quarterly([quarterly_revenue] * simulation_quarters)
    simulation = []
    for row in quarterly_simulation_raw:
        simulation.append(
            {
                "quarter": row["quarter"],
                "revenue": row["revenue"],
                "cost": row["quarterly_total_cost"],
                "profit": row["quarterly_profit"],
                "cumulative_profit": row["cumulative_profit"],
                "bep_reached": row["bep_reached"],
            }
        )

    return {
        "bep_quarters": bep_result["bep_quarters"],
        "quarterly_profit": bep_result["quarterly_profit"],
        "total_initial_investment": bep_result["total_initial_investment"],
        "annual_roi": bep_result["annual_roi"],
        "quarterly_simulation": simulation,
        "simulation_quarters": simulation_quarters,
        "is_mock": True,
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

    quarterly_results = tcn_predict(dong_code, industry_code, n_quarters=4)

    quarterly_avg = (
        sum(qr["predicted_sales"] for qr in quarterly_results) / len(quarterly_results) if quarterly_results else 0.0
    )

    return {
        "quarterly_avg": round(quarterly_avg),
        "quarterly_predictions": quarterly_results,
        "is_mock": False,
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


def _get_latest_store_count(dong_code: str, industry_code: str) -> int:
    """해당 동×업종의 최신 분기 store_count 반환. 조회 실패 시 1."""
    try:
        from models.lstm_forecast.data_prep import load_store_data

        dong_prefix = dong_code[:5] if len(dong_code) >= 5 else dong_code
        store_df = load_store_data(dong_prefix=dong_prefix)
        mask = (store_df["dong_code"].astype(str) == dong_code) & (
            store_df["industry_code"].astype(str) == industry_code
        )
        subset = store_df[mask]
        if subset.empty:
            return 1
        latest = subset.sort_values("quarter").iloc[-1]
        return max(int(latest.get("store_count", 1)), 1)
    except Exception as exc:
        logger.warning("store_count 조회 실패 (1로 대체): %s", exc)
        return 1


def _run_closure_rate(dong_code: str, industry_code: str) -> dict:
    """폐업률 예측 모델 호출."""
    from models.revenue_predictor.predict import predict as closure_predict

    result = closure_predict(dong_code, industry_code)
    return {
        "closure_rate": result["closure_rate"],
        "risk_level": result["closure_rate_level"],
        "monthly_closure_rates": result["monthly_closure_rates"],
        "is_mock": result.get("is_mock", False),
    }


def _run_bep(
    quarterly_per_store: float,  # 점포 1개 기준 분기 매출
    quarterly_predictions: list[dict],  # 분기 예측 4개
    industry_name: str,
    cost_config: dict | None,
    store_count: int = 1,
) -> dict:
    """BEP 계산 (분기 단위)."""
    from models.revenue_predictor.bep import BEPCalculator

    if cost_config is None:
        cost_config = BEPCalculator.get_default_costs(industry_name)

    calc = BEPCalculator(cost_config)
    bep_result = calc.calculate_bep(quarterly_per_store)

    raw_bep = bep_result["bep_quarters"]
    if raw_bep == -1:
        simulation_quarters = 40  # 도달 불가 → 10년 표시
    else:
        simulation_quarters = min(raw_bep + 1, 40)  # BEP+1분기 버퍼, 최대 10년

    base_revenues = [p["predicted_sales"] / store_count for p in quarterly_predictions]
    quarterly_revenues_list = [base_revenues[i % len(base_revenues)] for i in range(simulation_quarters)]

    quarterly_simulation_raw = calc.simulate_quarterly(quarterly_revenues_list)
    simulation = []
    for row in quarterly_simulation_raw:
        simulation.append(
            {
                "quarter": row["quarter"],
                "revenue": row["revenue"],
                "cost": row["quarterly_total_cost"],
                "profit": row["quarterly_profit"],
                "cumulative_profit": row["cumulative_profit"],
                "bep_reached": row["bep_reached"],
            }
        )

    return {
        "bep_quarters": bep_result["bep_quarters"],
        "quarterly_profit": bep_result["quarterly_profit"],
        "total_initial_investment": bep_result["total_initial_investment"],
        "annual_roi": bep_result["annual_roi"],
        "quarterly_simulation": simulation,
        "simulation_quarters": simulation_quarters,
        "is_mock": False,
    }


# ---------------------------------------------------------------------------
# 타겟 고객 세그먼트 분석
# ---------------------------------------------------------------------------


def _run_customer_revenue(
    dong_code: str,
    industry_code: str,
    profile_dict: dict | None = None,
    monthly_sales: float | None = None,
    quarter_num: int = 1,
) -> dict:
    """타겟 고객 매출 기여 예측 (P1-C MLP).

    Parameters
    ----------
    dong_code : str
    industry_code : str
    profile_dict : dict, optional
        프로필 딕셔너리. 키: age_groups, gender, time_slots, day_type.
        None이면 기본 프로필(전체 고객) 사용.
    monthly_sales : float, optional
        기준 월 매출. 있으면 세그먼트 절대 매출도 반환.
    quarter_num : int
        분기 번호 (1~4).
    """
    from models.customer_revenue.predict import SegmentProfile
    from models.customer_revenue.predict import predict as segment_predict

    if profile_dict is None:
        profile_dict = {}
    profile = SegmentProfile(
        age_groups=profile_dict.get("age_groups", []),
        gender=profile_dict.get("gender", "all"),
        time_slots=profile_dict.get("time_slots", []),
        day_type=profile_dict.get("day_type", "all"),
    )
    return segment_predict(dong_code, industry_code, profile, monthly_sales, quarter_num)


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
        segment_profile: dict | None = None,
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
                    "closure_rate": { closure_rate, risk_level, monthly_closure_rates },
                    "closure_risk": { risk_score, risk_level, top_signals, model, is_mock },
                    "bep": { bep_months, monthly_profit, total_initial_investment,
                             annual_roi, quarterly_simulation },
                    "segment_analysis": { segment_ratio, segment_sales, profile_summary,
                                          dimension_ratios } | None,
                    "metadata": { model_version, generated_at, data_period },
                }
        """
        use_mock = False

        # EXCLUDE_COMBOS 차단 — 모델 실행 전 선제 차단
        if (dong_code, industry_code) in EXCLUDE_COMBOS:
            raise ExcludedComboError(
                f"해당 조합은 데이터 부족으로 예측을 제공하지 않습니다: "
                f"dong_code={dong_code}, industry_code={industry_code}"
            )

        # ---- 1) 매출 예측 (모델 선택: lstm / tcn / gru) ----
        forecast_fn = {
            "lstm": _run_lstm_forecast,
            "tcn": _run_tcn_forecast,
            "gru": _run_gru_forecast,
        }.get(model, _run_tcn_forecast)

        try:
            revenue_forecast = forecast_fn(dong_code, industry_code)
            logger.info("%s 매출 예측 완료", model.upper())
        except ExcludedComboError:
            raise  # 차단 예외는 mock fallback 없이 상위로 전파
        except Exception as exc:
            logger.warning("%s 매출 예측 실패 (mock 사용): %s", model.upper(), exc)
            revenue_forecast = _mock_revenue_forecast()
            use_mock = True

        # ---- 2) 폐업률 예측 ----
        try:
            closure_rate_result = _run_closure_rate(dong_code, industry_code)
            logger.info("폐업률 예측 완료")
        except ExcludedComboError:
            raise  # 차단 예외는 mock fallback 없이 상위로 전파
        except Exception as exc:
            logger.warning("폐업률 예측 실패 (mock 사용): %s", exc)
            closure_rate_result = _mock_closure_rate()
            use_mock = True

        # ---- 3) 폐업위험도 예측 (LightGBM + TCN 앙상블) ----
        try:
            from models.closure_risk.predict import predict as closure_risk_predict

            closure_risk_result = closure_risk_predict(dong_code, industry_code)
            logger.info("폐업위험도 예측 완료 (score=%.3f)", closure_risk_result["risk_score"])
        except ExcludedComboError:
            raise  # 차단 예외는 mock fallback 없이 상위로 전파
        except Exception as exc:
            logger.warning("폐업위험도 예측 실패 (mock 사용): %s", exc)
            from models.closure_risk.predict import _mock_result

            closure_risk_result = _mock_result()

        # ---- 4) BEP 계산 ----
        try:
            quarterly_avg = revenue_forecast["quarterly_avg"]
            quarterly_preds = revenue_forecast["quarterly_predictions"]

            # district_sales.monthly_sales = 분기 합계(3개월치, 컬럼명 오기)
            # quarterly_avg = 4분기 예측의 평균 → 분기 합계 단위
            # ÷ store_count : 점포 1개 기준 (분기→월 환산 불필요: bep.py 내부에서 ×3 처리)
            store_count = _get_latest_store_count(dong_code, industry_code)
            quarterly_per_store = round(quarterly_avg / store_count)
            revenue_forecast["store_count"] = store_count
            revenue_forecast["quarterly_per_store"] = quarterly_per_store
            logger.info("store_count=%d → quarterly_per_store=%s원", store_count, f"{quarterly_per_store:,}")

            bep = _run_bep(
                quarterly_per_store=quarterly_per_store,
                quarterly_predictions=quarterly_preds,
                industry_name=industry_name,
                cost_config=cost_config,
                store_count=store_count,
            )
            logger.info("BEP 계산 완료")
        except Exception as exc:
            logger.warning("BEP 계산 실패 (mock 사용): %s", exc)
            bep = _mock_bep(industry_name)
            use_mock = True

        # ---- 5) 타겟 고객 세그먼트 분석 (P1-C, 선택적) ----
        segment_analysis: dict | None = None
        if segment_profile is not None:
            try:
                quarterly_avg = revenue_forecast.get("quarterly_avg")
                # 현재 월 기준 분기 계산 (계절성 반영)
                current_quarter = (datetime.now(tz=UTC).month - 1) // 3 + 1
                segment_analysis = _run_customer_revenue(
                    dong_code,
                    industry_code,
                    profile_dict=segment_profile,
                    monthly_sales=quarterly_avg,
                    quarter_num=current_quarter,
                )
                logger.info("세그먼트 분석 완료: %s", segment_analysis.get("profile_summary"))
            except Exception as exc:
                logger.warning("세그먼트 분석 실패 (건너뜀): %s", exc)

        # ---- dong_name 조회 ----
        dong_name = _resolve_dong_name(dong_code) if not use_mock else dong_code

        # ---- 6) [D — living_pop_forecast P1-D] 유동인구 피크 시간 예측 (TCN) ----
        # predict_peak(dong_name, n_quarters) 사용 — 24시간대 × 분기별 피크 시간 산출.
        # 가중치/스케일러 부재 또는 데이터 부족 시 graceful degradation (None).
        living_pop_result: dict | None = None
        try:
            from models.living_pop_forecast.predict import (
                predict_peak as _predict_peak,
            )

            quarters_pred = _predict_peak(dong_name, n_quarters=4)
            living_pop_result = {
                "dong_code": dong_code,
                "dong_name": dong_name,
                "n_quarters": len(quarters_pred),
                "quarters": quarters_pred,  # [{quarter_offset, peak_time_zone, peak_pop, all_hours}]
                "is_mock": False,
            }
            logger.info(
                "유동인구 피크 예측 완료 — q1 peak_tz=%s",
                quarters_pred[0]["peak_time_zone"] if quarters_pred else "N/A",
            )
        except Exception as exc:
            logger.warning("유동인구 피크 예측 실패 (건너뜀): %s", exc)
            living_pop_result = None

        # ---- 7) [E — emerging_district P1-E] 신흥 상권 조기 감지 (LSTM Autoencoder) ----
        emerging_result: dict | None = None
        try:
            from models.emerging_district.predict import predict as _predict_emerging

            emerging_result = dict(_predict_emerging(dong_code, industry_code))
            logger.info(
                "신흥 상권 감지 완료 — signal=%s anomaly=%.3f",
                emerging_result.get("signal"),
                emerging_result.get("anomaly_score", 0.0),
            )
        except Exception as exc:
            logger.warning("신흥 상권 감지 실패 (건너뜀): %s", exc)
            emerging_result = None

        return {
            "input": {
                "dong_code": dong_code,
                "dong_name": dong_name,
                "industry_code": industry_code,
                "industry_name": industry_name,
            },
            "revenue_forecast": revenue_forecast,
            "closure_rate": closure_rate_result,
            "closure_risk": closure_risk_result,
            "bep": bep,
            "segment_analysis": segment_analysis,
            # [D] 유동인구 피크 시간 예측 (TCN). dict | None
            "living_pop_forecast": living_pop_result,
            # [E] 신흥 상권 조기 감지 (LSTM Autoencoder). dict | None
            "emerging_signal": emerging_result,
            "metadata": {
                "model_version": MODEL_VERSION,
                "generated_at": datetime.now(tz=UTC).isoformat(),
                "data_period": DATA_PERIOD,
            },
        }
