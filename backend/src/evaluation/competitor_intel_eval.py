"""competitor_intel.market_entry_signal 정확도 평가.

정답 룰엔진 (시스템 프롬프트 명시 임계값):
  - green : 카니발율 < 5%  AND  포화도 ∈ {sparse, low}
  - yellow: 카니발율 5~15%  OR  포화도 == medium
  - red   : 카니발율 > 15%  OR  포화도 ∈ {high, saturated}

LLM 출력 vs 룰엔진 정답 → accuracy + confusion matrix.
"""

from __future__ import annotations

from typing import Any

from src.evaluation.evaluator import BaseEvaluator, EvalResult, EvalSummary


def _expected_signal(cannibal_pct: float, saturation_level: str) -> str:
    """시스템 프롬프트와 동일한 임계값으로 정답 라벨 생성."""
    sat = (saturation_level or "").lower()
    abs_cn = abs(cannibal_pct)  # cannibal_pct 는 음수로 들어옴 (-0.15 = 15% 잠식)
    if sat in {"high", "saturated"} or abs_cn > 0.15:
        return "red"
    if sat == "medium" or 0.05 <= abs_cn <= 0.15:
        return "yellow"
    if sat in {"sparse", "low"} and abs_cn < 0.05:
        return "green"
    # 임계값 사이 모호 — yellow 로 분류 (룰엔진 보수적 기본값)
    return "yellow"


class CompetitorIntelEvaluator(BaseEvaluator):
    """competitor_intel.market_entry_signal 룰엔진 비교 평가."""

    agent_id = "competitor_intel"

    def __init__(self, fixtures: list[dict] | None = None) -> None:
        # fixtures = [{case_id, dong_code, brand, business_type}, ...]
        # None 이면 마포 16동 × 시나리오 카페 표본을 prepare_dataset 가 만듦.
        self._fixtures = fixtures

    async def prepare_dataset(self) -> list[dict]:
        # 실제 운영에선 historical 시뮬 결과를 case 로 사용 (input + 시스템이 산출한 cannibal/saturation).
        # 여기선 fixtures 로 inject 하거나, 없으면 빈 리스트 반환 (호출처에서 결정).
        return self._fixtures or []

    async def run_one(self, case: dict) -> dict:
        """case input → competitor_intel 노드 실행 후 결과 dict.

        실제 노드 호출은 graph.run 또는 직접 _run_data_collection 후 LLM 호출.
        평가용으로는 캐시된 결과를 그대로 사용하거나 fixture 의 simulated 출력 사용.
        """
        # case["simulated_output"] 가 있으면 그 dict 사용 (사전 시뮬 결과).
        # 없으면 실제 노드 호출 — 비용 큰 작업이라 별도 진입점 필요.
        if "simulated_output" in case:
            return case["simulated_output"]
        raise NotImplementedError("case 에 'simulated_output' 미포함 — 실제 시뮬 호출 진입점 별도 구현 필요")

    def score(self, case: dict, output: Any) -> EvalResult:
        # output 은 competitor_intel 결과 dict — market_entry_signal + cannibalization + competition_500m 보유.
        actual_signal = (output or {}).get("market_entry_signal", "yellow").lower()
        cannibal_pct = (output or {}).get("cannibalization", {}).get("estimated_revenue_impact_pct", 0.0)
        sat_level = (output or {}).get("competition_500m", {}).get("saturation_level", "low")
        expected = _expected_signal(cannibal_pct, sat_level)
        passed = actual_signal == expected
        return EvalResult(
            case_id=case.get("case_id", "unknown"),
            agent_id=self.agent_id,
            expected=expected,
            actual=actual_signal,
            metric_name="signal_accuracy",
            metric_value=1.0 if passed else 0.0,
            passed=passed,
            details={
                "cannibal_pct": cannibal_pct,
                "saturation_level": sat_level,
            },
        )

    def aggregate(self, results: list[EvalResult]) -> EvalSummary:
        n = len(results)
        n_pass = sum(1 for r in results if r.passed)
        # confusion matrix: expected → actual 카운트
        cm: dict[str, dict[str, int]] = {}
        for r in results:
            cm.setdefault(r.expected, {}).setdefault(r.actual, 0)
            cm[r.expected][r.actual] += 1
        values = [r.metric_value for r in results]
        return EvalSummary(
            agent_id=self.agent_id,
            n_cases=n,
            n_passed=n_pass,
            metric_name="signal_accuracy",
            metric_mean=sum(values) / n if n else 0.0,
            metric_min=min(values) if values else 0.0,
            metric_max=max(values) if values else 0.0,
            confusion_matrix=cm,
            raw_results=results,
        )
