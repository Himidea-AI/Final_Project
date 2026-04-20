"""
시뮬레이션 데이터 변환 모듈

models/interface.py의 ModelOutput.generate() 결과(bep, quarterly_predictions)를
프론트엔드가 소비할 수 있는 형태로 변환한다.

[중요] bep["quarterly_simulation"] 실제 구조:
  interface.py의 _run_bep()는 quarterly_predictions(4개 분기값)를
  simulate_monthly()에 그대로 넘기므로, 출력도 4개 원소(quarter 1~4)이다.
  quarter 1 = Q1, quarter 2 = Q2, quarter 3 = Q3, quarter 4 = Q4 로 대응.

주요 역할:
  - build_quarterly_projection : BEP 4개 분기 + TCN 신뢰구간 결합 → 분기별 4개
  - build_quarterly_simple     : BEP 4개 분기 데이터 → dict 리스트 (나중에 MonthlyProjection 연결)
  - build_scenarios            : TCN 분기 예측 → 낙관/기본/비관 3가지 시나리오

담당: B2 — 수지니
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 내부 상수 — confidence 파라미터 허용값
# ---------------------------------------------------------------------------

_VALID_CONFIDENCE = {"base", "optimistic", "pessimistic"}


# ---------------------------------------------------------------------------
# 1. build_quarterly_projection
# ---------------------------------------------------------------------------


def build_quarterly_projection(
    bep_quarterly_simulation: list[dict],
    quarterly_predictions: list[dict],
    confidence: str = "base",
) -> list[dict]:
    """
    BEP 분기 시뮬레이션(실제 4개, month 1~4)과 TCN 분기 예측 신뢰구간을
    결합하여 분기별 4개 결과를 반환한다.

    [bep_quarterly_simulation 구조 주의]
      interface.py가 4개 분기 매출값을 simulate_monthly()에 넘기므로
      실제 원소 수는 4개(month 1/2/3/4 = Q1/Q2/Q3/Q4).
      month 1~3 그룹핑(→12개월 전제)은 잘못된 가정이므로 사용하지 않는다.
      대신 인덱스로 직접 접근:
        bep_quarterly_simulation[0] → Q1 데이터
        bep_quarterly_simulation[1] → Q2 데이터
        bep_quarterly_simulation[2] → Q3 데이터
        bep_quarterly_simulation[3] → Q4 데이터

    confidence 파라미터:
      "base"        → TCN predicted_sales   (모델 포인트 예측)
      "optimistic"  → TCN confidence_upper  (95% 신뢰구간 상한)
      "pessimistic" → TCN confidence_lower  (95% 신뢰구간 하한)

    Args:
        bep_quarterly_simulation: interface.generate()["bep"]["quarterly_simulation"]
                                실제 4개 dict, 각 원소: quarter(1~4), revenue, cost,
                                profit, cumulative_profit, bep_reached
        quarterly_predictions:  interface.generate()["revenue_forecast"]["quarterly_predictions"]
                                4개 dict, 각 원소: quarter_offset(1~4), predicted_sales,
                                confidence_lower, confidence_upper
        confidence:             "base" | "optimistic" | "pessimistic" (기본값: "base")

    Returns:
        list[dict] 4개
        {
            "quarter": int,            # 1~4
            "revenue": int,            # confidence 기준 TCN 매출 (float → int)
            "cumulative_profit": int,  # 해당 분기 누적수익 BEP에서 추출 (float → int)
            "confidence_lower": int,   # TCN 95% 신뢰구간 하한 (float → int)
            "confidence_upper": int,   # TCN 95% 신뢰구간 상한 (float → int)
        }
    """
    # confidence 파라미터 유효성 검증
    # — 잘못된 값이 들어오면 기본값(base)으로 대체하고 경고 로그 출력
    if confidence not in _VALID_CONFIDENCE:
        logger.warning(
            "알 수 없는 confidence 값 '%s' — 'base'로 대체합니다. "
            "허용값: %s",
            confidence,
            _VALID_CONFIDENCE,
        )
        confidence = "base"

    # confidence → TCN 예측 키 매핑
    # — 어떤 필드값을 revenue로 사용할지 결정
    _revenue_key_map = {
        "base": "predicted_sales",
        "optimistic": "confidence_upper",
        "pessimistic": "confidence_lower",
    }
    revenue_key = _revenue_key_map[confidence]

    # quarterly_predictions를 quarter_offset 기준으로 딕셔너리화
    # — {quarter_offset: row} 구조로 O(1) 조회
    quarterly_map: dict[int, dict] = {
        row["quarter_offset"]: row for row in quarterly_predictions
    }

    results: list[dict] = []

    for q in range(1, 5):  # Q1~Q4 (1, 2, 3, 4)
        # bep_quarterly_simulation은 실제 4개 원소(인덱스 0~3)
        # q=1 → 인덱스 0(Q1), q=2 → 인덱스 1(Q2), ... 직접 접근
        bep_idx = q - 1
        if bep_idx < len(bep_quarterly_simulation):
            # 해당 분기의 BEP 누적수익 추출 (float → int 변환)
            bep_row = bep_quarterly_simulation[bep_idx]
            cumulative_profit = int(bep_row.get("cumulative_profit", 0))
        else:
            # 데이터가 없는 분기는 0으로 대체 (데이터 부족 방어)
            logger.warning("bep_quarterly_simulation 인덱스 %d 없음 — 0으로 대체", bep_idx)
            cumulative_profit = 0

        # TCN 분기 예측 데이터에서 revenue, 신뢰구간 추출 (float → int 변환)
        # — quarter_offset에 해당하는 row가 없으면 0으로 대체
        tcn_row = quarterly_map.get(q, {})
        revenue = int(tcn_row.get(revenue_key, 0))
        confidence_lower = int(tcn_row.get("confidence_lower", 0))
        confidence_upper = int(tcn_row.get("confidence_upper", 0))

        results.append(
            {
                "quarter": q,
                "revenue": revenue,
                "cumulative_profit": cumulative_profit,
                "confidence_lower": confidence_lower,
                "confidence_upper": confidence_upper,
            }
        )

    logger.info(
        "build_quarterly_projection 완료 — confidence=%s, 분기 수=%d",
        confidence,
        len(results),
    )
    return results


# ---------------------------------------------------------------------------
# 2. build_quarterly_simple
# ---------------------------------------------------------------------------


def build_quarterly_simple(
    bep_quarterly_simulation: list[dict],
) -> list[dict]:
    """
    BEP 시뮬레이션 결과에서 프론트엔드 필요 필드만 추출하여 반환한다.

    [실제 데이터 단위 주의]
      입력 bep_quarterly_simulation은 이름과 달리 실제 4개 분기 데이터이다.
      (interface.py에서 분기 매출 4개를 simulate_monthly()에 넘기기 때문)
      따라서 이 함수의 반환 원소도 4개(분기)이며,
      month 필드값은 1~4 (분기 번호)를 그대로 반환한다.

    반환 타입을 dict로 유지하는 이유:
      backend/src/schemas/simulation_output.py의 MonthlyProjection(Pydantic)을
      여기서 직접 import하면 models/ → backend/ 의존성이 생겨 패키지 구조가 깨진다.
      현재는 dict 형태로 반환하고, 나중에 프론트 연결 시
      MonthlyProjection으로 변환 예정.

    Args:
        bep_quarterly_simulation: interface.generate()["bep"]["quarterly_simulation"]
                                실제 4개 분기 dict, 각 원소: quarter(1~4), revenue, cost,
                                profit, cumulative_profit, bep_reached

    Returns:
        list[dict] 4개 (실제 분기 데이터 — 명칭은 monthly이나 단위는 분기)
        {
            "month": int,              # 분기 번호 1~4 (month 키 그대로 사용)
            "revenue": int,            # 해당 분기 매출 (float → int 변환)
            "cumulative_profit": int,  # 누적수익 (float → int 변환)
        }
    """
    results: list[dict] = []

    for row in bep_quarterly_simulation:
        # float → int 형변환
        # — BEP 계산 결과가 float로 나오므로 스키마(MonthlyProjection) int 타입에 맞게 변환
        results.append(
            {
                "month": int(row["month"]),              # 분기 번호 1~4
                "revenue": int(row["revenue"]),           # 분기 매출
                "cumulative_profit": int(row["cumulative_profit"]),  # 누적수익
            }
        )

    logger.info(
        "build_quarterly_simple 완료 — 원소 수=%d (실제 분기 데이터)",
        len(results),
    )
    return results


# ---------------------------------------------------------------------------
# 3. build_scenarios
# ---------------------------------------------------------------------------


def build_scenarios(
    quarterly_predictions: list[dict],
) -> dict:
    """
    TCN 분기 예측 결과(4개)로 낙관/기본/비관 3가지 시나리오를 생성한다.

    시나리오별 revenue 기준:
      optimistic  : confidence_upper  (95% 신뢰구간 상한 — 최선의 경우)
      base        : predicted_sales   (모델 포인트 예측 — 기본 시나리오)
      pessimistic : confidence_lower  (95% 신뢰구간 하한 — 최악의 경우)

    신뢰구간은 TCN predict()에서 이미 max(0, ...) 처리됨.
    그러나 int 변환 이후 안전을 위해 max(0, ...) 처리를 유지한다.

    Args:
        quarterly_predictions: interface.generate()["revenue_forecast"]["quarterly_predictions"]
                               4개 dict, 각 원소: quarter_offset(1~4), predicted_sales,
                               confidence_lower, confidence_upper

    Returns:
        dict
        {
            "optimistic":  list[dict] 4개,
            "base":        list[dict] 4개,
            "pessimistic": list[dict] 4개,
        }
        각 list 원소:
        {
            "quarter": int,   # 1~4 (quarter_offset 그대로)
            "revenue": int,   # 해당 시나리오 기준 분기 매출 (float → int 변환)
        }
    """
    # 시나리오 이름 → TCN 예측 필드 키 매핑
    # — 어떤 필드를 revenue로 쓸지 한 곳에서 관리하여 변경 용이하게
    _scenario_key_map = {
        "optimistic": "confidence_upper",
        "base": "predicted_sales",
        "pessimistic": "confidence_lower",
    }

    scenarios: dict[str, list[dict]] = {}

    for scenario_name, tcn_key in _scenario_key_map.items():
        scenario_rows: list[dict] = []

        for row in quarterly_predictions:
            # quarter_offset을 quarter로 그대로 사용 (값 동일: 1~4)
            quarter = int(row["quarter_offset"])

            # float → int 변환 및 음수 방어
            # — 신뢰구간 하한은 이론상 0 이상이지만 안전을 위해 max(0, ...) 유지
            revenue = max(0, int(row.get(tcn_key, 0)))

            scenario_rows.append(
                {
                    "quarter": quarter,
                    "revenue": revenue,
                }
            )

        scenarios[scenario_name] = scenario_rows

    logger.info(
        "build_scenarios 완료 — 시나리오 수=%d, 분기 수=%d",
        len(scenarios),
        len(quarterly_predictions),
    )
    return scenarios
