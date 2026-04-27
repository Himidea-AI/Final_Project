"""
폐업률 추론 함수 — 과거 실측값 기반 (최근 4분기 단순 평균)

predict(dong_code, industry_code) → 폐업률 결과
B2(수지니)의 12개월 시뮬레이션 입력으로 사용된다.

변경 이력:
- 기존: LSTM 모델(closure_model.pt) 미래 예측
- 변경: store_quarterly 최근 4분기 실측 closure_rate 평균 사용
  이유: 폐업률은 미래 예측보다 과거 실측 기반이 신뢰도 높음
       closure_risk(폐업위험도)가 이미 AI 기반 미래 예측을 담당
       계절성 자동 해소 (4분기 = 1년 포함)

담당: B2 — 수지니
"""

from __future__ import annotations

import logging

import numpy as np

from models.revenue_predictor.data_prep import engineer_features, load_store_data

logger = logging.getLogger(__name__)

# 최근 몇 분기 평균을 낼지
_LOOKBACK_QUARTERS = 4


# ---------------------------------------------------------------------------
# 위험도 분류
# ---------------------------------------------------------------------------


def _classify_risk(closure_rate: float) -> str:
    """폐업률 기반 위험도 분류."""
    if closure_rate <= 0.3:
        return "safe"
    elif closure_rate <= 0.6:
        return "caution"
    else:
        return "danger"


# ---------------------------------------------------------------------------
# 12개월 월별 폐업률 보간
# ---------------------------------------------------------------------------


def _interpolate_monthly(quarterly_closure: float, months: int = 12) -> list[float]:
    """
    분기 폐업률을 12개월 월별 누적 폐업률로 보간한다.

    분기 폐업률을 월별 증가율로 변환하여 누적 적용.
    """
    quarterly_retain = 1.0 - quarterly_closure
    monthly_decay = quarterly_retain ** (1 / 3)

    monthly_rates = []
    cumulative = 1.0
    for _ in range(months):
        cumulative *= monthly_decay
        closure = round(max(0.0, min(1.0, 1.0 - cumulative)), 4)
        monthly_rates.append(closure)

    return monthly_rates


# ---------------------------------------------------------------------------
# 메인 예측 함수
# ---------------------------------------------------------------------------


def predict(dong_code: str | int, industry_code: str) -> dict:
    """
    특정 동x업종의 폐업률을 최근 4분기 실측값 평균으로 반환한다.

    Args:
        dong_code:     행정동 코드 (예: "11440530")
        industry_code: 업종 코드 (예: "CS100001")

    Returns:
        dict:
            closure_rate:          최근 4분기 평균 폐업률 (0~1). 계산 실패 시 None.
            closure_risk_level:    위험도 ("safe" / "caution" / "danger" / "unknown")
            monthly_closure_rates: 12개월 월별 누적 폐업률 리스트. 실패 시 빈 리스트.
            quarterly_predictions: 최근 4분기 실측값 리스트 (추세 참고용). 실패 시 빈 리스트.
    """
    dong_code = str(dong_code)

    try:
        df = load_store_data(seoul=False)
        df = engineer_features(df)

        mask = (df["dong_code"].astype(str) == dong_code) & (df["industry_code"].astype(str) == industry_code)
        subset = df.loc[mask].sort_values("quarter")

        if subset.empty:
            logger.warning("데이터 없음: dong=%s, industry=%s — 업종 평균 사용", dong_code, industry_code)
            return _fallback_by_industry(df, industry_code)

        # 최근 4분기 실측값 추출 (closure_rate_pred = closure_rate / 100)
        recent = subset["closure_rate_pred"].tail(_LOOKBACK_QUARTERS).values
        quarterly_predictions = [round(float(v), 4) for v in recent]

        # 단순 평균 (최근 4분기 = 1년 → 계절성 자동 해소)
        closure_rate = round(float(np.mean(recent)), 4)

    except Exception as exc:
        logger.warning("폐업률 계산 실패 — None 반환: %s", exc)
        return _mock_result()

    risk_level = _classify_risk(closure_rate)
    monthly_rates = _interpolate_monthly(closure_rate)

    return {
        "closure_rate": closure_rate,
        "closure_risk_level": risk_level,
        "monthly_closure_rates": monthly_rates,
        "quarterly_predictions": quarterly_predictions,
    }


# ---------------------------------------------------------------------------
# Fallback 헬퍼
# ---------------------------------------------------------------------------


def _fallback_by_industry(df, industry_code: str) -> dict:
    """해당 업종의 마포구 평균 폐업률로 fallback."""
    industry_df = df[df["industry_code"].astype(str) == industry_code]
    if not industry_df.empty:
        avg = round(float(industry_df["closure_rate_pred"].mean()), 4)
        logger.info("업종 평균 폐업률 사용: %s → %.4f", industry_code, avg)
        risk_level = _classify_risk(avg)
        return {
            "closure_rate": avg,
            "closure_risk_level": risk_level,
            "monthly_closure_rates": _interpolate_monthly(avg),
            "quarterly_predictions": [avg] * 4,
        }
    return _mock_result()


def _mock_result() -> dict:
    """최종 fallback — 계산 실패 신호 반환 (임의값 노출 방지)."""
    return {
        "closure_rate": None,
        "closure_risk_level": "unknown",
        "monthly_closure_rates": [],
        "quarterly_predictions": [],
    }
