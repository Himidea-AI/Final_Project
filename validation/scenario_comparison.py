"""
시나리오별 결과 비교 분석 — base vs what-if 시나리오 결과 비교

models/explainability/simulation.py의 결과물을 입력으로 받아
낙관/기본/비관 시나리오 간 핵심 지표를 비교하고
민감도 분석 결과를 반환한다.

담당: B2 — 수지니
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def compare_scenarios(base_result: list[dict], scenario_results: dict) -> dict:
    """
    시나리오별 결과 비교 분석

    build_quarterly_projection()과 build_scenarios()의 출력을 받아
    낙관/기본/비관 세 시나리오의 핵심 지표를 비교하고
    변화율 및 민감도 분석 결과를 반환한다.

    [시그니처 변경 이유]
      원래 scenario_results: list[dict]였으나
      build_scenarios() 반환값이 dict(3개 시나리오 묶음)이므로
      dict로 변경하여 실제 데이터 구조에 맞춤.

    Args:
        base_result: build_quarterly_projection() 반환값
                     list[dict] 4개, 각 원소:
                     {quarter, revenue, cumulative_profit,
                      confidence_lower, confidence_upper}

        scenario_results: build_scenarios() 반환값
                          {
                            "optimistic":  [{"quarter": int, "revenue": int}, ...],  # 4개
                            "base":        [{"quarter": int, "revenue": int}, ...],  # 4개
                            "pessimistic": [{"quarter": int, "revenue": int}, ...],  # 4개
                          }

    Returns:
        dict:
        {
            "summary": {
                "optimistic":  {"total_revenue": int, "final_cumulative_profit": int, "bep_quarter": int | None},
                "base":        {"total_revenue": int, "final_cumulative_profit": int, "bep_quarter": int | None},
                "pessimistic": {"total_revenue": int, "final_cumulative_profit": int, "bep_quarter": int | None},
            },
            "change_rate": {
                "optimistic_vs_base":  float,   # % 단위 (소수점 2자리)
                "pessimistic_vs_base": float,   # % 단위 (소수점 2자리)
            },
            "sensitivity": {
                "revenue_range": int,   # 낙관 - 비관 총매출 차이 (원)
                "profit_range":  int,   # 낙관 - 비관 누적수익 차이 (원)
                "risk_level":    str,   # "low" | "medium" | "high"
            }
        }
    """

    # -------------------------------------------------------------------------
    # 1) 시나리오별 총매출(total_revenue) 계산
    #    — 4분기 revenue 합산
    # -------------------------------------------------------------------------

    # 각 시나리오의 분기별 revenue를 합산하여 총매출 산출
    # 키가 없을 경우 0으로 대체하여 KeyError 방어
    optimistic_list: list[dict] = scenario_results.get("optimistic", [])
    base_list: list[dict] = scenario_results.get("base", [])
    pessimistic_list: list[dict] = scenario_results.get("pessimistic", [])

    optimistic_total: int = sum(row.get("revenue", 0) for row in optimistic_list)
    base_total: int = sum(row.get("revenue", 0) for row in base_list)
    pessimistic_total: int = sum(row.get("revenue", 0) for row in pessimistic_list)

    logger.info(
        "총매출 계산 완료 — optimistic=%d, base=%d, pessimistic=%d",
        optimistic_total, base_total, pessimistic_total,
    )

    # -------------------------------------------------------------------------
    # 2) bep_quarter 계산
    #    — base_result의 cumulative_profit >= 0 인 첫 분기 탐색
    #    — 없으면 None 반환
    #    — 세 시나리오 공통으로 base_result 기준 사용
    #      (scenario_results에는 cumulative_profit 필드가 없음)
    # -------------------------------------------------------------------------

    bep_quarter: int | None = None
    for row in base_result:
        # cumulative_profit이 0 이상이면 BEP 도달 분기로 판단
        if row.get("cumulative_profit", -1) >= 0:
            bep_quarter = row.get("quarter")
            break  # 첫 번째 도달 분기만 기록

    logger.info("bep_quarter 계산 완료 — %s", bep_quarter)

    # -------------------------------------------------------------------------
    # 3) final_cumulative_profit 계산
    #    — base: base_result Q4(마지막 원소)의 cumulative_profit 그대로 사용
    #    — optimistic/pessimistic: base 누적수익을 총매출 비율로 스케일링
    #      이유: scenario_results에는 cumulative_profit이 없으므로
    #            매출 비율을 이용해 근사 추정
    #    — base_total = 0이면 스케일링 불가 → base cumulative_profit 그대로 사용
    # -------------------------------------------------------------------------

    # Q4 데이터: base_result의 마지막 원소 (quarter=4)
    # 정렬 보장을 위해 quarter 기준으로 최대값 선택
    base_q4_row = max(base_result, key=lambda r: r.get("quarter", 0)) if base_result else {}
    base_cumulative: int = int(base_q4_row.get("cumulative_profit", 0))

    if base_total != 0:
        # 총매출 비율로 누적수익을 근사 추정
        # — 비용 구조가 동일하다는 가정 하에 매출 비율 = 수익 비율로 근사
        optimistic_cumulative = int(base_cumulative * (optimistic_total / base_total))
        pessimistic_cumulative = int(base_cumulative * (pessimistic_total / base_total))
    else:
        # base_total이 0이면 스케일링 불가 — 모두 base 값으로 통일
        logger.warning("base_total=0 — final_cumulative_profit 스케일링 불가, base 값으로 대체")
        optimistic_cumulative = base_cumulative
        pessimistic_cumulative = base_cumulative

    # -------------------------------------------------------------------------
    # 4) summary 구성
    #    — 3개 시나리오 각각의 핵심 지표 묶음
    # -------------------------------------------------------------------------

    summary: dict = {
        "optimistic": {
            "total_revenue": optimistic_total,
            "final_cumulative_profit": optimistic_cumulative,
            "bep_quarter": bep_quarter,   # base_result 기준 공통 적용
        },
        "base": {
            "total_revenue": base_total,
            "final_cumulative_profit": base_cumulative,
            "bep_quarter": bep_quarter,
        },
        "pessimistic": {
            "total_revenue": pessimistic_total,
            "final_cumulative_profit": pessimistic_cumulative,
            "bep_quarter": bep_quarter,
        },
    }

    # -------------------------------------------------------------------------
    # 5) change_rate 계산 (% 단위)
    #    — 낙관/비관이 기본 대비 몇 % 차이나는지
    #    — base_total = 0이면 ZeroDivisionError 방어 → 0.0 반환
    # -------------------------------------------------------------------------

    if base_total != 0:
        optimistic_vs_base = round((optimistic_total - base_total) / base_total * 100, 2)
        pessimistic_vs_base = round((pessimistic_total - base_total) / base_total * 100, 2)
    else:
        # base 총매출이 0이면 변화율 계산 불가 — 0.0으로 대체
        logger.warning("base_total=0 — change_rate 계산 불가, 0.0으로 대체")
        optimistic_vs_base = 0.0
        pessimistic_vs_base = 0.0

    change_rate: dict = {
        "optimistic_vs_base": optimistic_vs_base,
        "pessimistic_vs_base": pessimistic_vs_base,
    }

    # -------------------------------------------------------------------------
    # 6) sensitivity 계산
    #    — revenue_range: 낙관 - 비관 총매출 차이 (변동폭)
    #    — profit_range : 낙관 - 비관 누적수익 차이 (변동폭)
    #    — risk_level   : 낙관·비관 변화율 합산 절댓값 기준
    #        10% 미만  → "low"
    #        10~20%    → "medium"
    #        20% 초과  → "high"
    # -------------------------------------------------------------------------

    revenue_range: int = optimistic_total - pessimistic_total
    profit_range: int = optimistic_cumulative - pessimistic_cumulative

    # 낙관 vs 비관 변화율 스프레드 계산
    # — 두 변화율의 절댓값 차이로 시나리오 간 불확실성 크기를 측정
    spread = abs(optimistic_vs_base - pessimistic_vs_base)

    if spread < 10.0:
        risk_level = "low"
    elif spread <= 20.0:
        risk_level = "medium"
    else:
        risk_level = "high"

    sensitivity: dict = {
        "revenue_range": revenue_range,
        "profit_range": profit_range,
        "risk_level": risk_level,
    }

    logger.info(
        "sensitivity 계산 완료 — revenue_range=%d, profit_range=%d, risk_level=%s",
        revenue_range, profit_range, risk_level,
    )

    # -------------------------------------------------------------------------
    # 최종 반환
    # -------------------------------------------------------------------------

    return {
        "summary": summary,
        "change_rate": change_rate,
        "sensitivity": sensitivity,
    }
