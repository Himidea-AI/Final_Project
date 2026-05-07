"""population.report LLM-as-judge + peak_time 매칭률."""

from __future__ import annotations

from typing import Any

from src.evaluation.evaluator import BaseEvaluator, EvalResult, EvalSummary
from src.evaluation.llm_as_judge import JudgeScore, judge_text


class PopulationEvaluator(BaseEvaluator):
    """population_analyst — judge_score 와 peak_time 매칭률 가중 평균."""

    agent_id = "population_analyst"

    def __init__(self, fixtures: list[dict] | None = None, threshold: float = 4.0) -> None:
        # fixtures = [{case_id, district, business_type, population_data,
        #              simulated_report, simulated_peak_time, expected_peak_time}]
        self._fixtures = fixtures
        self._threshold = threshold

    async def prepare_dataset(self) -> list[dict]:
        return self._fixtures or []

    async def run_one(self, case: dict) -> dict:
        if "simulated_report" in case and "simulated_peak_time" in case:
            return {
                "report": case["simulated_report"],
                "peak_time": case["simulated_peak_time"],
            }
        raise NotImplementedError("case 에 'simulated_report'/'simulated_peak_time' 미포함")

    def score(self, case: dict, output: Any) -> EvalResult:
        raise NotImplementedError("async 평가는 ascore 사용")

    async def ascore(self, case: dict, output: Any) -> EvalResult:
        report = (output or {}).get("report", "")
        actual_peak = (output or {}).get("peak_time", "")
        expected_peak = case.get("expected_peak_time", "")
        peak_match = 1.0 if actual_peak.strip() == expected_peak.strip() else 0.0

        input_data = {
            "district": case.get("district"),
            "business_type": case.get("business_type"),
            "population_data": case.get("population_data", {}),
        }
        judge: JudgeScore = await judge_text(
            input_data,
            report,
            extra_context=f"peak_time 예측({actual_peak}) 도 specificity 차원에서 같이 보세요.",
        )
        # 가중 평균: judge_score 0.7 + peak_match 0.3 (5점 척도로 환산)
        composite = (judge.mean * 0.7) + (peak_match * 5.0 * 0.3)
        is_passed = composite >= self._threshold
        return EvalResult(
            case_id=case.get("case_id", "unknown"),
            agent_id=self.agent_id,
            expected=f"composite >= {self._threshold}",
            actual=composite,
            metric_name="composite_score",
            metric_value=composite,
            passed=is_passed,
            details={
                "judge_mean": judge.mean,
                "peak_match": peak_match,
                "actual_peak": actual_peak,
                "expected_peak": expected_peak,
                "rationale": judge.rationale,
            },
        )

    async def run(self, max_cases: int | None = None) -> EvalSummary:
        cases = await self.prepare_dataset()
        if max_cases is not None:
            cases = cases[:max_cases]
        results: list[EvalResult] = []
        for case in cases:
            output = await self.run_one(case)
            results.append(await self.ascore(case, output))
        return self.aggregate(results)

    def aggregate(self, results: list[EvalResult]) -> EvalSummary:
        n = len(results)
        n_pass = sum(1 for r in results if r.passed)
        values = [r.metric_value for r in results]
        return EvalSummary(
            agent_id=self.agent_id,
            n_cases=n,
            n_passed=n_pass,
            metric_name="composite_score",
            metric_mean=sum(values) / n if n else 0.0,
            metric_min=min(values) if values else 0.0,
            metric_max=max(values) if values else 0.0,
            raw_results=results,
        )
