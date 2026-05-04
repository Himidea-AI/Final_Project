"""평가 base class — 7 에이전트 evaluator 공통 인터페이스.

각 evaluator 는 다음 메서드 구현:
  - prepare_dataset: 평가용 입력·정답 라벨 (또는 기준) 준비
  - run_one: 입력 1건 → 에이전트 실행 → 출력
  - score: 출력 vs 정답 → metric 산출
  - aggregate: 여러 케이스 결과 → 종합 점수
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalResult:
    """단일 평가 케이스 결과."""

    case_id: str
    """케이스 식별자 (예: '2025-Q3_아현동_커피')."""

    agent_id: str
    """평가 대상 에이전트 (예: 'trend_forecaster')."""

    expected: Any
    """정답 라벨 또는 기준 (분류·점수·기준 자연어)."""

    actual: Any
    """에이전트 실제 출력."""

    metric_name: str
    """주 metric 이름 (예: 'accuracy', 'f1', 'judge_score')."""

    metric_value: float
    """metric 값 (0.0~1.0 또는 0~5)."""

    passed: bool
    """기준 통과 여부."""

    details: dict = field(default_factory=dict)
    """부가 정보 (confusion matrix raw, judge 평가 코멘트 등)."""


@dataclass
class EvalSummary:
    """여러 케이스 종합."""

    agent_id: str
    n_cases: int
    n_passed: int
    metric_name: str
    metric_mean: float
    metric_min: float
    metric_max: float
    confusion_matrix: dict | None = None
    raw_results: list[EvalResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.n_passed / self.n_cases if self.n_cases > 0 else 0.0

    def report_lines(self) -> list[str]:
        lines = [
            f"[{self.agent_id}] n={self.n_cases} pass={self.n_passed}/{self.n_cases} ({self.pass_rate:.1%})",
            f"  {self.metric_name}: mean={self.metric_mean:.3f} min={self.metric_min:.3f} max={self.metric_max:.3f}",
        ]
        if self.confusion_matrix:
            lines.append(f"  confusion: {self.confusion_matrix}")
        return lines


class BaseEvaluator(ABC):
    """7 에이전트 evaluator 공통 인터페이스."""

    agent_id: str = "base"

    @abstractmethod
    async def prepare_dataset(self) -> list[dict]:
        """평가용 케이스 리스트 반환.

        각 케이스 = {"case_id": str, "input": dict, "expected": Any}
        """
        ...

    @abstractmethod
    async def run_one(self, case: dict) -> Any:
        """1 케이스 실행 → 에이전트 출력 (raw)."""
        ...

    @abstractmethod
    def score(self, case: dict, output: Any) -> EvalResult:
        """1 케이스 채점."""
        ...

    @abstractmethod
    def aggregate(self, results: list[EvalResult]) -> EvalSummary:
        """여러 케이스 종합."""
        ...

    async def run(self, max_cases: int | None = None) -> EvalSummary:
        """전체 평가 흐름. 디폴트 구현."""
        cases = await self.prepare_dataset()
        if max_cases is not None:
            cases = cases[:max_cases]
        results: list[EvalResult] = []
        for case in cases:
            output = await self.run_one(case)
            results.append(self.score(case, output))
        return self.aggregate(results)
