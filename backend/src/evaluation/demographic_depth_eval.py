"""demographic_depth LLM-as-judge + brand_target_match_score 분포 검증."""

from __future__ import annotations

from typing import Any

from src.evaluation.evaluator import BaseEvaluator, EvalResult, EvalSummary
from src.evaluation.llm_as_judge import JudgeScore, judge_text, passed


class DemographicDepthEvaluator(BaseEvaluator):
    """demographic_depth — judge_score + brand_target_match_score 분포 sanity check."""

    agent_id = "demographic_depth"

    def __init__(self, fixtures: list[dict] | None = None, threshold: float = 4.0) -> None:
        # fixtures = [{case_id, brand, business_type, demographic_data,
        #              simulated_report, simulated_match_score (0~100)}]
        self._fixtures = fixtures
        self._threshold = threshold

    async def prepare_dataset(self) -> list[dict]:
        return self._fixtures or []

    async def run_one(self, case: dict) -> dict:
        if "simulated_report" in case:
            return {
                "report": case["simulated_report"],
                "match_score": case.get("simulated_match_score"),
            }
        raise NotImplementedError("case 에 'simulated_report' 미포함")

    def score(self, case: dict, output: Any) -> EvalResult:
        raise NotImplementedError("async 평가는 ascore 사용")

    async def ascore(self, case: dict, output: Any) -> EvalResult:
        report = (output or {}).get("report", "")
        match_score = (output or {}).get("match_score")

        input_data = {
            "brand": case.get("brand"),
            "business_type": case.get("business_type"),
            "demographic_data": case.get("demographic_data", {}),
        }
        judge: JudgeScore = await judge_text(input_data, report)

        # match_score sanity: 0~100 범위. 50±5 (= 평균 근처 무의미한 값) 비율 누적 시 의심.
        # 단일 case 에선 단순 범위 체크만.
        score_valid = (
            match_score is not None
            and isinstance(match_score, (int, float))
            and 0 <= match_score <= 100
        )

        composite = judge.mean * (1.0 if score_valid else 0.7)
        is_passed = composite >= self._threshold and score_valid
        return EvalResult(
            case_id=case.get("case_id", "unknown"),
            agent_id=self.agent_id,
            expected=f"judge_mean >= {self._threshold} AND match_score in [0,100]",
            actual=composite,
            metric_name="composite_score",
            metric_value=composite,
            passed=is_passed,
            details={
                "judge_mean": judge.mean,
                "match_score": match_score,
                "score_valid": score_valid,
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
