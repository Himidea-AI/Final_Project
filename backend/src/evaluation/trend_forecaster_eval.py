"""trend_forecaster QoQ 방향 일치 평가 (v7 재설계).

v6 까지: 6개월 후 Naver DataLab 실측 변화율 vs LLM 예측 (구조적 미달성 — 정답 데이터 없음)
v7 (2026-05-07): "미래 예측" 자체가 원천 검증 불가 → *현재 QoQ 데이터 해석* 일치도로 교체.

LLM 이 *판단* 하는 것 = 입력으로 받은 QoQ 수치(예: +12%) 의 방향(증가/감소/유지) 분류.
정답은 수치 자체에서 룰로 산출.

룰:
   QoQ ≥ +5% → growth
   QoQ ≤ -5% → decline
   그 외      → stable
"""

from __future__ import annotations

from typing import Any

from src.evaluation.evaluator import BaseEvaluator, EvalResult, EvalSummary


def _expected_direction(qoq_pct: float) -> str:
    """QoQ 변화율 → 정답 방향 라벨 (시스템 프롬프트와 동일 임계값)."""
    if qoq_pct >= 0.05:
        return "growth"
    if qoq_pct <= -0.05:
        return "decline"
    return "stable"


class TrendForecasterEvaluator(BaseEvaluator):
    """trend_forecaster.direction = QoQ 해석 일치 (v7).

    v6 6m future vs 실측 비교 폐기 — 정답 데이터 부재 + 미래 예측은 본질적 평가 불가.
    v7 = 현재 QoQ 수치 해석의 방향 정확도. LLM 이 +12% 를 'growth' 로 읽는지 검증.
    """

    agent_id = "trend_forecaster"

    def __init__(self, fixtures: list[dict] | None = None) -> None:
        # fixtures = [{
        #   "case_id": str,
        #   "qoq_pct": float,            # 시뮬에 주입된 QoQ
        #   "actual_direction": str,     # LLM 출력 direction
        # }]
        self._fixtures = fixtures

    async def prepare_dataset(self) -> list[dict]:
        return self._fixtures or []

    async def run_one(self, case: dict) -> dict:
        if "actual_direction" in case:
            return {"direction": case["actual_direction"]}
        raise NotImplementedError("case 에 'actual_direction' 미포함")

    def score(self, case: dict, output: Any) -> EvalResult:
        actual = (output or {}).get("direction", "").lower()
        qoq = case.get("qoq_pct", 0.0) or 0.0
        expected = _expected_direction(qoq)
        passed = actual == expected
        return EvalResult(
            case_id=case.get("case_id", "unknown"),
            agent_id=self.agent_id,
            expected=expected,
            actual=actual or "unknown",
            metric_name="direction_accuracy",
            metric_value=1.0 if passed else 0.0,
            passed=passed,
            details={"qoq_pct": qoq},
        )

    def aggregate(self, results: list[EvalResult]) -> EvalSummary:
        n = len(results)
        n_pass = sum(1 for r in results if r.passed)
        cm: dict[str, dict[str, int]] = {}
        for r in results:
            cm.setdefault(r.expected, {}).setdefault(r.actual, 0)
            cm[r.expected][r.actual] += 1
        values = [r.metric_value for r in results]
        return EvalSummary(
            agent_id=self.agent_id,
            n_cases=n,
            n_passed=n_pass,
            metric_name="direction_accuracy",
            metric_mean=sum(values) / n if n else 0.0,
            metric_min=min(values) if values else 0.0,
            metric_max=max(values) if values else 0.0,
            confusion_matrix=cm,
            raw_results=results,
        )
