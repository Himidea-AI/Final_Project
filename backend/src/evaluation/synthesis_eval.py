"""synthesis 내부 정합성 평가 (v7 재설계).

v6 까지: LLM-as-judge — 자기참조 편향 + factuality 검증 본질적 한계
v7 (2026-05-07): synthesis 가 *판단* 하지 않고 *취합·계산* 만 하므로 정량 룰로 검증.

검증 항목 4개 (각 0/1, 평균 = composite):
   1. legal_risk_preserved : final_report.overall_legal_risk == legal node output
                              (synthesis 가 임의로 위험도 바꾸면 안 됨)
   2. profit_math          : net_profit ≈ revenue - cost (오차 1% 이내)
   3. grade_recommend_consistent : grade RISKY인데 추천 강한 긍정 톤이면 모순
   4. winner_match         : final_recommendation 안의 추천 입지가 winner_district 와 일치

→ synthesis 의 본질적 역할(데이터 보존 + 종합 톤) 검증에 집중.
"""

from __future__ import annotations

from typing import Any

from src.evaluation.evaluator import BaseEvaluator, EvalResult, EvalSummary


def _check_legal_preserved(case: dict) -> bool:
    """legal node 의 overall_legal_risk 가 synthesis final_report 에서 그대로 유지?"""
    legal_risk = (case.get("legal_risk") or "").lower()
    synth_risk = (case.get("synth_legal_risk") or "").lower()
    if not legal_risk or not synth_risk:
        return False
    return legal_risk == synth_risk


def _check_profit_math(case: dict, tolerance: float = 0.01) -> bool:
    """net_profit ≈ revenue - cost (1% 이내)?"""
    rev = case.get("monthly_revenue")
    cost = case.get("monthly_cost")
    net = case.get("net_profit")
    if rev is None or cost is None or net is None:
        return False
    expected = float(rev) - float(cost)
    if abs(expected) < 1.0:
        return abs(net) < 1.0
    return abs((float(net) - expected) / expected) <= tolerance


def _check_grade_recommend_consistent(case: dict) -> bool:
    """grade RISKY 인데 final_recommendation 이 강한 긍정 톤이면 모순.

    간이 키워드 검사 — 본격 LLM 채점 대신 명백한 모순만 잡음.
    """
    grade = (case.get("grade") or "").upper()
    recommendation = (case.get("final_recommendation") or "").lower()
    if grade != "RISKY":
        return True  # RISKY 아니면 검사 대상 X
    # 명백한 강한 긍정 표현 (RISKY 와 정면 충돌)
    strong_positive = ["탁월", "최적", "절호", "강력 추천", "주저없이"]
    has_strong_positive = any(kw in recommendation for kw in strong_positive)
    return not has_strong_positive


def _check_winner_match(case: dict) -> bool:
    """final_recommendation 첫 줄에 winner_district 가 등장해야 정합."""
    winner = (case.get("winner_district") or "").strip()
    recommendation = (case.get("final_recommendation") or "")[:300]
    if not winner:
        return False
    return winner in recommendation


class SynthesisEvaluator(BaseEvaluator):
    """synthesis 정량 정합성 평가 (v7).

    v6 LLM-judge 폐기. v7 = 4개 정량 룰 (정합성/수식/모순/winner).
    """

    agent_id = "synthesis"

    def __init__(self, fixtures: list[dict] | None = None) -> None:
        # fixtures = [{
        #   "case_id": str,
        #   "legal_risk": str,           # legal node output
        #   "synth_legal_risk": str,     # synthesis final_report.overall_legal_risk
        #   "monthly_revenue": float,
        #   "monthly_cost": float,
        #   "net_profit": float,
        #   "grade": str,                # ranking grade
        #   "final_recommendation": str,
        #   "winner_district": str,
        # }]
        self._fixtures = fixtures

    async def prepare_dataset(self) -> list[dict]:
        return self._fixtures or []

    async def run_one(self, case: dict) -> dict:
        return case  # 모든 검증 데이터가 case 안에 있음

    def score(self, case: dict, output: Any) -> EvalResult:
        checks = {
            "legal_preserved": _check_legal_preserved(case),
            "profit_math": _check_profit_math(case),
            "grade_consistent": _check_grade_recommend_consistent(case),
            "winner_match": _check_winner_match(case),
        }
        n_pass = sum(1 for v in checks.values() if v)
        composite = n_pass / 4.0
        passed = composite >= 0.75  # 4 중 3 이상

        return EvalResult(
            case_id=case.get("case_id", "unknown"),
            agent_id=self.agent_id,
            expected="4 정합성 룰 통과 (≥75%)",
            actual=f"{n_pass}/4",
            metric_name="consistency_score",
            metric_value=composite,
            passed=passed,
            details=checks,
        )

    def aggregate(self, results: list[EvalResult]) -> EvalSummary:
        n = len(results)
        n_pass = sum(1 for r in results if r.passed)
        values = [r.metric_value for r in results]
        # 룰별 통과율 — 어느 룰이 가장 자주 깨지는지
        rule_pass_rates: dict[str, float] = {}
        rule_keys = ["legal_preserved", "profit_math", "grade_consistent", "winner_match"]
        for k in rule_keys:
            hits = sum(1 for r in results if r.details.get(k))
            rule_pass_rates[k] = hits / n if n else 0.0

        return EvalSummary(
            agent_id=self.agent_id,
            n_cases=n,
            n_passed=n_pass,
            metric_name="consistency_score",
            metric_mean=sum(values) / n if n else 0.0,
            metric_min=min(values) if values else 0.0,
            metric_max=max(values) if values else 0.0,
            raw_results=results,
            confusion_matrix={"rule_pass_rates": rule_pass_rates},  # 룰별 통과율 dump
        )
