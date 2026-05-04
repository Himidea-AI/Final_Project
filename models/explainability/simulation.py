"""
시뮬레이션 데이터 변환 모듈

models/interface.py의 ModelOutput.generate() 결과(bep, quarterly_predictions)를
프론트엔드가 소비할 수 있는 형태로 변환한다.

[중요] bep["quarterly_simulation"] 실제 구조:
  interface.py의 _run_bep()는 simulate_quarterly()를 N분기(최대 40분기)로 호출한다.
  simulation_quarters = min(bep_quarters + 1, 40) 또는 bep_quarters == -1이면 40.
  각 원소: quarter(1~N), revenue, cost, profit, cumulative_profit, bep_reached.

주요 역할:
  - build_quarterly_projection : BEP N개 분기 + TCN 신뢰구간 결합 → N개 분기
  - build_quarterly_simple     : BEP N개 분기 데이터 → dict 리스트
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
    is_mock: bool = False,
    store_count: int = 1,
) -> list[dict]:
    """
    BEP 분기 시뮬레이션(N개)과 TCN 분기 예측 신뢰구간을 결합하여 N개 분기 결과를 반환한다.

    confidence 파라미터:
      "base"        → TCN predicted_sales   (모델 포인트 예측)
      "optimistic"  → TCN confidence_upper  (95% 신뢰구간 상한)
      "pessimistic" → TCN confidence_lower  (95% 신뢰구간 하한)

    Args:
        bep_quarterly_simulation: interface.generate()["bep"]["quarterly_simulation"]
                                N개 dict, 각 원소: quarter(1~N), revenue, cost,
                                profit, cumulative_profit, bep_reached
        quarterly_predictions:  interface.generate()["revenue_forecast"]["quarterly_predictions"]
                                4개 dict, 각 원소: quarter_offset(1~4), predicted_sales,
                                confidence_lower, confidence_upper
        confidence:             "base" | "optimistic" | "pessimistic" (기본값: "base")
        is_mock:                TCN 모델 mock 여부 (기본값: False)
        store_count:            점포 수 (기본값: 1) — Q1~Q4 TCN 예측값을 점포 1개 기준으로 환산

    Returns:
        list[dict] N개 — 분기 수는 bep_quarterly_simulation 길이와 동일
        {
            "quarter": int,            # 1~N
            "revenue": int,            # confidence 기준 TCN 매출, 점포 1개 기준 (float → int)
            "cumulative_profit": int,  # 해당 분기 누적수익 BEP에서 추출 (float → int)
            "confidence_lower": int,   # TCN 95% 신뢰구간 하한, 점포 1개 기준 (float → int)
            "confidence_upper": int,   # TCN 95% 신뢰구간 상한, 점포 1개 기준 (float → int)
            "is_mock": bool,           # TCN mock 여부
        }
    """
    if confidence not in _VALID_CONFIDENCE:
        logger.warning(
            "알 수 없는 confidence 값 '%s' — 'base'로 대체합니다. 허용값: %s",
            confidence,
            _VALID_CONFIDENCE,
        )
        confidence = "base"

    _revenue_key_map = {
        "base": "predicted_sales",
        "optimistic": "confidence_upper",
        "pessimistic": "confidence_lower",
    }
    revenue_key = _revenue_key_map[confidence]

    # quarterly_predictions를 quarter_offset 기준으로 딕셔너리화
    quarterly_map: dict[int, dict] = {row["quarter_offset"]: row for row in quarterly_predictions}
    # bep_quarterly_simulation을 quarter 기준으로 딕셔너리화 (BEP는 달성 시까지만 존재)
    bep_map: dict[int, dict] = {int(row["quarter"]): row for row in bep_quarterly_simulation}

    results: list[dict] = []
    divisor = max(store_count, 1)

    # 2026-05-04 R6 fix — 4분기 hard cap 제거. BEP simulation 길이(N)만큼 build.
    # TCN 은 4분기까지만 예측하므로 Q5+ 는 4분기 cycle 반복 (계절성 유지).
    # 예: TCN Q1~Q4 매출 = [A, B, C, D] → Q5=A, Q6=B, Q7=C, Q8=D, ...
    # cumulative_profit 은 bep_map 에 N분기까지 다 있으므로 그대로 가져옴.
    tcn_len = max(len(quarterly_predictions), 1)
    n_quarters = max(len(bep_quarterly_simulation), tcn_len)

    for q_idx in range(1, n_quarters + 1):
        # TCN 4분기 cycle: Q5→Q1, Q6→Q2, ... (1-based 모듈로)
        tcn_q = ((q_idx - 1) % tcn_len) + 1
        tcn_row = quarterly_map.get(tcn_q, {})
        bep_row = bep_map.get(q_idx, {})

        revenue = int(tcn_row.get(revenue_key, 0) / divisor)
        # BEP simulation에 해당 분기 없으면 cumulative_profit=0 (BEP 이미 달성)
        cumulative_profit = int(bep_row.get("cumulative_profit", 0))
        confidence_lower = int(tcn_row.get("confidence_lower", 0) / divisor)
        confidence_upper = int(tcn_row.get("confidence_upper", 0) / divisor)

        results.append(
            {
                "quarter": q_idx,
                "revenue": revenue,
                "cumulative_profit": cumulative_profit,
                "confidence_lower": confidence_lower,
                "confidence_upper": confidence_upper,
                "is_mock": is_mock,
            }
        )

    logger.info(
        "build_quarterly_projection 완료 — confidence=%s, 분기 수=%d (BEP simulation 기반)",
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

    반환 타입을 dict로 유지하는 이유:
      backend/src/schemas/simulation_output.py의 MonthlyProjection(Pydantic)을
      여기서 직접 import하면 models/ → backend/ 의존성이 생겨 패키지 구조가 깨진다.

    Args:
        bep_quarterly_simulation: interface.generate()["bep"]["quarterly_simulation"]
                                N개 분기 dict, 각 원소: quarter(1~N), revenue, cost,
                                profit, cumulative_profit, bep_reached

    Returns:
        list[dict] N개
        {
            "quarter": int,            # 분기 번호 1~N
            "revenue": int,            # 해당 분기 매출 (float → int 변환)
            "cumulative_profit": int,  # 누적수익 (float → int 변환)
        }
    """
    results: list[dict] = []

    for row in bep_quarterly_simulation:
        results.append(
            {
                "quarter": int(row["quarter"]),
                "revenue": int(row["revenue"]),
                "cumulative_profit": int(row["cumulative_profit"]),
            }
        )

    logger.info(
        "build_quarterly_simple 완료 — 원소 수=%d",
        len(results),
    )
    return results


# ---------------------------------------------------------------------------
# 3. build_scenarios
# ---------------------------------------------------------------------------


def build_scenarios(
    quarterly_predictions: list[dict],
    store_count: int = 1,
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
        store_count:           점포 수 (기본값: 1) — 시나리오 revenue를 점포 1개 기준으로 환산

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
            "revenue": int,   # 해당 시나리오 기준 분기 매출, 점포 1개 기준 (float → int 변환)
        }
    """
    # 시나리오 이름 → TCN 예측 필드 키 매핑
    # — 어떤 필드를 revenue로 쓸지 한 곳에서 관리하여 변경 용이하게
    _scenario_key_map = {
        "optimistic": "confidence_upper",
        "base": "predicted_sales",
        "pessimistic": "confidence_lower",
    }

    divisor = max(store_count, 1)
    scenarios: dict[str, list[dict]] = {}

    for scenario_name, tcn_key in _scenario_key_map.items():
        scenario_rows: list[dict] = []

        for row in quarterly_predictions:
            # quarter_offset을 quarter로 그대로 사용 (값 동일: 1~4)
            quarter = int(row["quarter_offset"])

            # float → int 변환, 점포 1개 기준 환산, 음수 방어
            revenue = max(0, int(row.get(tcn_key, 0) / divisor))

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
