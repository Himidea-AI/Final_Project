"""
손익분기점(BEP) 계산 모듈

BEP(개월) = 초기투자비 / (월 예상매출 - 월 고정비 - 월 변동비)

매출 예측값(LSTM 모델 출력)과 비용 항목을 받아 BEP를 산출합니다.
담당: B2 — 딥러닝 모델
"""

from __future__ import annotations

import math

# 업종별 기본 비용 구조
INDUSTRY_DEFAULTS: dict[str, dict] = {
    "한식음식점": {"variable_cost_rate": 0.35, "monthly_labor": 5_000_000},
    "중식음식점": {"variable_cost_rate": 0.33, "monthly_labor": 4_500_000},
    "일식음식점": {"variable_cost_rate": 0.38, "monthly_labor": 5_500_000},
    "양식음식점": {"variable_cost_rate": 0.35, "monthly_labor": 5_000_000},
    "제과점": {"variable_cost_rate": 0.30, "monthly_labor": 4_000_000},
    "패스트푸드점": {"variable_cost_rate": 0.32, "monthly_labor": 3_500_000},
    "치킨전문점": {"variable_cost_rate": 0.40, "monthly_labor": 3_500_000},
    "분식전문점": {"variable_cost_rate": 0.30, "monthly_labor": 3_000_000},
    "호프-간이주점": {"variable_cost_rate": 0.35, "monthly_labor": 4_000_000},
    "커피-음료": {"variable_cost_rate": 0.25, "monthly_labor": 4_000_000},
}


class BEPCalculator:
    """손익분기점 계산기

    사용자가 비용 항목을 직접 조정할 수 있도록 config dict 기반으로 동작합니다.

    Args:
        config: 비용 구조 딕셔너리.
            - initial_investment: 보증금(deposit), 권리금(premium),
              인테리어(interior), 가맹비(franchise_fee)
            - monthly_fixed_cost: 월세(rent), 관리비(maintenance),
              인건비(labor)
            - variable_cost_rate: 원가율 (매출 대비 비율, 0~1)
    """

    def __init__(self, config: dict) -> None:
        self.initial_investment: dict[str, float] = config.get("initial_investment", {})
        self.monthly_fixed_cost: dict[str, float] = config.get("monthly_fixed_cost", {})
        self.variable_cost_rate: float = config.get("variable_cost_rate", 0.35)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _total_initial_investment(self) -> float:
        """초기투자비 합계 (보증금 + 권리금 + 인테리어 + 가맹비)"""
        return sum(self.initial_investment.values())

    def _total_monthly_fixed_cost(self) -> float:
        """월 고정비 합계 (임대료 + 관리비 + 인건비)"""
        return sum(self.monthly_fixed_cost.values())

    def _monthly_variable_cost(self, monthly_revenue: float) -> float:
        """월 변동비 (매출 × 원가율)"""
        return monthly_revenue * self.variable_cost_rate

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_bep(self, monthly_revenue: float) -> dict:
        """단일 월 매출 기준 BEP 산출

        Args:
            monthly_revenue: 월 예상매출 (원)

        Returns:
            dict with keys:
                bep_months             — BEP 도달 개월 수
                monthly_profit         — 월 순이익
                monthly_fixed_cost     — 월 고정비 합계
                monthly_variable_cost  — 월 변동비
                total_initial_investment — 초기투자비 합계
                annual_roi             — 연간 ROI (%)
        """
        total_initial = self._total_initial_investment()
        fixed = self._total_monthly_fixed_cost()
        variable = self._monthly_variable_cost(monthly_revenue)
        monthly_profit = monthly_revenue - fixed - variable

        # BEP 개월 수: 순이익이 0 이하이면 도달 불가(무한)
        if monthly_profit <= 0:
            bep_months = -1  # -1 은 "도달 불가"를 의미
            annual_roi = 0.0
        else:
            bep_months = math.ceil(total_initial / monthly_profit)
            annual_roi = (monthly_profit * 12) / total_initial * 100 if total_initial > 0 else 0.0

        return {
            "bep_months": bep_months,
            "monthly_profit": monthly_profit,
            "monthly_fixed_cost": fixed,
            "monthly_variable_cost": variable,
            "total_initial_investment": total_initial,
            "annual_roi": round(annual_roi, 2),
        }

    def simulate_monthly(self, monthly_revenues: list[float]) -> list[dict]:
        """12개월 매출 리스트를 받아 월별 손익 시뮬레이션

        Args:
            monthly_revenues: 월별 예상 매출 리스트 (예: 12개월)

        Returns:
            list of dict — 각 항목은:
                month              — 월 번호 (1-based)
                revenue            — 해당 월 매출
                fixed_cost         — 월 고정비
                variable_cost      — 월 변동비
                total_cost         — 월 총비용
                profit             — 월 순이익
                cumulative_profit  — 누적 순이익 (초기투자비 차감 후)
                bep_reached        — 이 달에 BEP 도달 여부 (bool)
        """
        total_initial = self._total_initial_investment()
        fixed = self._total_monthly_fixed_cost()
        cumulative_profit = -total_initial  # 초기투자비를 빚으로 시작
        bep_already_reached = False
        results: list[dict] = []

        for idx, revenue in enumerate(monthly_revenues, start=1):
            variable = self._monthly_variable_cost(revenue)
            total_cost = fixed + variable
            profit = revenue - total_cost
            cumulative_profit += profit

            reached_this_month = False
            if not bep_already_reached and cumulative_profit >= 0:
                reached_this_month = True
                bep_already_reached = True

            results.append(
                {
                    "month": idx,
                    "revenue": revenue,
                    "fixed_cost": fixed,
                    "variable_cost": variable,
                    "total_cost": total_cost,
                    "profit": profit,
                    "cumulative_profit": cumulative_profit,
                    "bep_reached": reached_this_month,
                }
            )

        return results

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def get_default_costs(industry_name: str) -> dict:
        """업종별 기본 비용 구조 반환

        지원 업종: 한식음식점, 중식음식점, 일식음식점, 양식음식점, 제과점,
                   패스트푸드점, 치킨전문점, 분식전문점, 호프-간이주점, 커피-음료

        Args:
            industry_name: 업종명 (예: "한식음식점")

        Returns:
            dict — config 형식과 동일한 기본 비용 구조.
            업종이 목록에 없으면 한식음식점 기본값을 사용합니다.
        """
        defaults = INDUSTRY_DEFAULTS.get(industry_name, INDUSTRY_DEFAULTS["한식음식점"])

        return {
            "initial_investment": {
                "deposit": 50_000_000,
                "premium": 30_000_000,
                "interior": 40_000_000,
                "franchise_fee": 10_000_000,
            },
            "monthly_fixed_cost": {
                "rent": 2_000_000,
                "maintenance": 300_000,
                "labor": defaults["monthly_labor"],
            },
            "variable_cost_rate": defaults["variable_cost_rate"],
        }
