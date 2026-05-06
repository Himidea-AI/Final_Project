"""market_analyst.report LLM-as-judge 평가."""

from __future__ import annotations

from typing import Any

from src.evaluation.evaluator import BaseEvaluator, EvalResult, EvalSummary
from src.evaluation.llm_as_judge import JudgeScore, judge_text, passed


class MarketAnalystEvaluator(BaseEvaluator):
    """market_analyst.report 자연어 본문 LLM-as-judge."""

    agent_id = "market_analyst"

    def __init__(self, fixtures: list[dict] | None = None, threshold: float = 4.0) -> None:
        # fixtures = [{case_id, district, business_type, market_data, simulated_report}]
        self._fixtures = fixtures
        self._threshold = threshold

    async def prepare_dataset(self) -> list[dict]:
        return self._fixtures or []

    async def run_one(self, case: dict) -> str:
        if "simulated_report" in case:
            return case["simulated_report"]
        raise NotImplementedError("case 에 'simulated_report' 미포함")

    def score(self, case: dict, output: Any) -> EvalResult:
        # judge 는 async 라 score 안에서 await 가 필요. 동기 호출용 sync wrapper.
        # 운영은 BaseEvaluator.run() override 또는 async 직접 호출 권장.
        raise NotImplementedError("async 평가는 ascore 사용")

    async def ascore(self, case: dict, output: Any) -> EvalResult:
        report = output or ""
        input_data = {
            "district": case.get("district"),
            "business_type": case.get("business_type"),
            "market_data": case.get("market_data", {}),
        }
        judge: JudgeScore = await judge_text(input_data, report)
        return EvalResult(
            case_id=case.get("case_id", "unknown"),
            agent_id=self.agent_id,
            expected="judge_mean >= 4.0",
            actual=judge.mean,
            metric_name="judge_score",
            metric_value=judge.mean,
            passed=passed(judge, self._threshold),
            details={
                "factuality": judge.factuality,
                "relevance": judge.relevance,
                "specificity": judge.specificity,
                "coherence": judge.coherence,
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
            metric_name="judge_score",
            metric_mean=sum(values) / n if n else 0.0,
            metric_min=min(values) if values else 0.0,
            metric_max=max(values) if values else 0.0,
            raw_results=results,
        )
