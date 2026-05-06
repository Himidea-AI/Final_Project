"""synthesis.final_recommendation LLM-as-judge.

종합 자연어 본문 평가 — 4 차원에 추가로 '내부 일관성 (다른 에이전트 결과와 결론 정합)' 강조.
"""

from __future__ import annotations

from typing import Any

from src.evaluation.evaluator import BaseEvaluator, EvalResult, EvalSummary
from src.evaluation.llm_as_judge import JudgeScore, judge_text, passed


class SynthesisEvaluator(BaseEvaluator):
    """synthesis.final_recommendation — 다른 에이전트 출력과의 정합성 강조."""

    agent_id = "synthesis"

    def __init__(self, fixtures: list[dict] | None = None, threshold: float = 4.0) -> None:
        # fixtures = [{case_id, brand, district, agent_outputs, simulated_recommendation}]
        # agent_outputs = {market_report, population_report, legal_summary, ranking_winner, ...}
        self._fixtures = fixtures
        self._threshold = threshold

    async def prepare_dataset(self) -> list[dict]:
        return self._fixtures or []

    async def run_one(self, case: dict) -> str:
        if "simulated_recommendation" in case:
            return case["simulated_recommendation"]
        raise NotImplementedError("case 에 'simulated_recommendation' 미포함")

    def score(self, case: dict, output: Any) -> EvalResult:
        raise NotImplementedError("async 평가는 ascore 사용")

    async def ascore(self, case: dict, output: Any) -> EvalResult:
        recommendation = output or ""
        input_data = {
            "brand": case.get("brand"),
            "district": case.get("district"),
            "agent_outputs": case.get("agent_outputs", {}),
        }
        judge: JudgeScore = await judge_text(
            input_data,
            recommendation,
            extra_context=(
                "synthesis 는 종합 출력이라 다른 에이전트(market/population/legal/ranking) 출력과 "
                "결론이 정합하는지 coherence 차원에서 특히 엄격히 보세요. "
                "예: legal danger 면 final_recommendation 도 위험 언급 필요. "
                "ranking winner 와 추천 입지가 다르면 자기모순."
            ),
        )
        return EvalResult(
            case_id=case.get("case_id", "unknown"),
            agent_id=self.agent_id,
            expected=f"judge_mean >= {self._threshold}",
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
