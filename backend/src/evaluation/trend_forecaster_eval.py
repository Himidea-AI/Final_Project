"""trend_forecaster.direction 정확도 백테스트.

LLM 의 direction(growth/stable/decline) 예측 vs Naver DataLab 실측 추세 비교.

백테스트 흐름:
  1. 시점 t (예: 2025-Q3) 의 입력 → trend_forecaster 실행 → direction 예측
  2. 시점 t+6m (2026-Q1) 의 Naver DataLab 실측 검색량 변화 → 정답 라벨화
     · 변화율 ≥ +10% → growth
     · 변화율 ≤ -10% → decline
     · 그 외        → stable
  3. accuracy + confusion matrix

운영에선 historical fixture 활용 또는 정기 batch 로 6개월 후 다시 채점.
"""

from __future__ import annotations

from typing import Any

from src.evaluation.evaluator import BaseEvaluator, EvalResult, EvalSummary


def _label_direction_from_change(change_pct: float) -> str:
    """실측 변화율 → 정답 라벨."""
    if change_pct >= 0.10:
        return "growth"
    if change_pct <= -0.10:
        return "decline"
    return "stable"


class TrendForecasterEvaluator(BaseEvaluator):
    """trend_forecaster.direction 백테스트 evaluator."""

    agent_id = "trend_forecaster"

    def __init__(self, fixtures: list[dict] | None = None) -> None:
        # fixtures = [{case_id, district, business_type, t0, prediction, actual_change_pct_6m}]
        # prediction = trend_forecaster 가 t0 시점에 산출한 direction (사전 캐시).
        # actual_change_pct_6m = Naver DataLab 의 t0+6m 실측 변화율 (예: 0.12 = +12%).
        self._fixtures = fixtures

    async def prepare_dataset(self) -> list[dict]:
        return self._fixtures or []

    async def run_one(self, case: dict) -> dict:
        """case 에 prediction 미리 들어 있으면 그대로 사용.
        없으면 trend_forecaster 노드 실행 (운영 시점 — 비용 발생).
        """
        if "prediction" in case:
            return {"direction": case["prediction"]}
        raise NotImplementedError(
            "case 에 'prediction' 미포함 — historical 캐시에서 미리 채워두거나 실시간 노드 호출 진입점 구현 필요"
        )

    def score(self, case: dict, output: Any) -> EvalResult:
        actual_dir = (output or {}).get("direction", "stable").lower()
        change_pct = case.get("actual_change_pct_6m", 0.0)
        expected = _label_direction_from_change(change_pct)
        passed = actual_dir == expected
        return EvalResult(
            case_id=case.get("case_id", "unknown"),
            agent_id=self.agent_id,
            expected=expected,
            actual=actual_dir,
            metric_name="direction_accuracy",
            metric_value=1.0 if passed else 0.0,
            passed=passed,
            details={"actual_change_pct_6m": change_pct},
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
