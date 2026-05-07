"""market_analyst.grade 분류 정확도 평가 (v7 재설계).

v6 까지: LLM-as-judge 4축 채점 (factuality 등) → MAPE 0.1% 무의미
   문제: LLM 에 주입된 수치를 그대로 출력하는 걸 "잘 맞춘다" 로 측정.

v7 재설계 (2026-05-07): grade 분류 정확도.
   LLM 이 실제로 *판단* 하는 것 = 주어진 수치(QoQ성장률 / 경쟁포화도 / 임대료) 로
   EXCELLENT/GOOD/NORMAL/RISKY 등급을 매기는 일.
   → 동일 수치를 룰엔진(임계값) 으로 expected_grade 산출 → LLM grade 와 비교.

룰엔진 임계값 (시스템 프롬프트 명시 기준 추론):
   EXCELLENT : QoQ ≥ +15% AND saturation in {sparse, low}
   GOOD      : QoQ ≥ +5%  AND saturation in {sparse, low, medium}
   NORMAL    : -5% ≤ QoQ ≤ +5% AND saturation != saturated
   RISKY     : QoQ ≤ -5%  OR saturation in {high, saturated}
"""

from __future__ import annotations

from typing import Any

from src.evaluation.evaluator import BaseEvaluator, EvalResult, EvalSummary


def _expected_grade(qoq_growth_pct: float, saturation_level: str) -> str:
    """수치 → 룰엔진 정답 grade. 시스템 프롬프트 임계값과 동일하게.

    Args:
        qoq_growth_pct: 분기 성장률 (0.15 = +15%, -0.05 = -5%)
        saturation_level: sparse/low/medium/high/saturated

    Returns:
        "EXCELLENT" | "GOOD" | "NORMAL" | "RISKY"
    """
    sat = (saturation_level or "").lower()
    qoq = qoq_growth_pct or 0.0

    # RISKY 우선 (가장 보수적)
    if qoq <= -0.05 or sat in {"high", "saturated"}:
        return "RISKY"
    # EXCELLENT — 강성장 + 저포화 둘 다
    if qoq >= 0.15 and sat in {"sparse", "low"}:
        return "EXCELLENT"
    # GOOD — 성장 + 중간 이하 포화
    if qoq >= 0.05 and sat in {"sparse", "low", "medium"}:
        return "GOOD"
    # 그 외 = NORMAL
    return "NORMAL"


class MarketAnalystEvaluator(BaseEvaluator):
    """market_analyst.grade 룰엔진 비교 평가 (v7).

    v6 LLM-as-judge 폐기 — MAPE 0.1% 가 LLM 의 주입 수치 echo 일 뿐 진짜 판단 측정 X.
    v7 = LLM 이 실제로 판단하는 *분류 라벨* 정확도로 교체.
    """

    agent_id = "market_analyst"

    def __init__(self, fixtures: list[dict] | None = None) -> None:
        # fixtures = [{
        #   "case_id": str,
        #   "qoq_growth_pct": float,           # 시뮬에 주입된 QoQ
        #   "saturation_level": str,           # 시뮬에 주입된 포화도
        #   "actual_grade": str,               # LLM 이 출력한 grade
        # }]
        self._fixtures = fixtures

    async def prepare_dataset(self) -> list[dict]:
        return self._fixtures or []

    async def run_one(self, case: dict) -> dict:
        if "actual_grade" in case:
            return {"grade": case["actual_grade"]}
        raise NotImplementedError("case 에 'actual_grade' 미포함 — Redis 캐시 dump 필요")

    def score(self, case: dict, output: Any) -> EvalResult:
        actual = (output or {}).get("grade", "").upper()
        expected = _expected_grade(
            case.get("qoq_growth_pct", 0.0) or 0.0,
            case.get("saturation_level", "low") or "low",
        )
        passed = actual == expected
        return EvalResult(
            case_id=case.get("case_id", "unknown"),
            agent_id=self.agent_id,
            expected=expected,
            actual=actual or "UNKNOWN",
            metric_name="grade_accuracy",
            metric_value=1.0 if passed else 0.0,
            passed=passed,
            details={
                "qoq_growth_pct": case.get("qoq_growth_pct"),
                "saturation_level": case.get("saturation_level"),
            },
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
            metric_name="grade_accuracy",
            metric_mean=sum(values) / n if n else 0.0,
            metric_min=min(values) if values else 0.0,
            metric_max=max(values) if values else 0.0,
            confusion_matrix=cm,
            raw_results=results,
        )
