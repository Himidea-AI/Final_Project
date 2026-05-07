"""population_analyst.metrics 정확도 평가 (v7 재설계).

v6 까지: judge_score 0.7 + peak_match 0.3 (judge 의존)
v7 (2026-05-07): 연령·성별·피크 시간 3 차원 직접 비교 (judge 제거).

LLM 이 *판단* 하는 것 = adstrd_flpop / SGIS 데이터에서 main_target_age / main_target_gender /
   peak_time 도출. 정답은 데이터 자체에서 룰로 산출.

지표:
   - age_match    : analysis_metrics.main_target_age 가 입력 데이터 1위 연령대?
   - gender_match : main_target_gender 가 1위 성별?
   - peak_match   : peak_time 이 입력 데이터 최대 시간 bucket?
   - composite    : 3 개 평균
"""

from __future__ import annotations

from typing import Any

from src.evaluation.evaluator import BaseEvaluator, EvalResult, EvalSummary


def _expected_top_age(age_distribution: dict) -> str:
    if not age_distribution:
        return "unknown"
    top = max(age_distribution.items(), key=lambda x: x[1] or 0, default=("unknown", 0))[0]
    # 데이터 키 형식 그대로 (예: "20", "30", "60+")
    return str(top)


def _expected_top_gender(gender_distribution: dict) -> str:
    m = gender_distribution.get("male", 0) or 0
    f = gender_distribution.get("female", 0) or 0
    if m == 0 and f == 0:
        return "mixed"
    if abs(m - f) / max(m + f, 1) < 0.1:
        return "mixed"
    return "male" if m > f else "female"


def _expected_peak(time_distribution: dict) -> str:
    if not time_distribution:
        return "unknown"
    return max(time_distribution.items(), key=lambda x: x[1] or 0, default=("unknown", 0))[0]


def _normalize_age_label(label: str) -> str:
    """LLM 출력 형식 통일 ("20대" → "20", "20-30" → "20")."""
    s = str(label or "").strip().replace("대", "").replace("~", "-")
    if "-" in s:
        s = s.split("-")[0]
    return s


class PopulationEvaluator(BaseEvaluator):
    """population_analyst — 연령·성별·피크 직접 일치 (v7)."""

    agent_id = "population_analyst"

    def __init__(self, fixtures: list[dict] | None = None) -> None:
        # fixtures = [{
        #   "case_id": str,
        #   "age_distribution": dict,      # 시뮬 입력
        #   "gender_distribution": dict,
        #   "time_distribution": dict,
        #   "actual_age": str,
        #   "actual_gender": str,
        #   "actual_peak": str,
        # }]
        self._fixtures = fixtures

    async def prepare_dataset(self) -> list[dict]:
        return self._fixtures or []

    async def run_one(self, case: dict) -> dict:
        return {
            "age": case.get("actual_age", ""),
            "gender": case.get("actual_gender", ""),
            "peak": case.get("actual_peak", ""),
        }

    def score(self, case: dict, output: Any) -> EvalResult:
        out = output or {}
        actual_age = _normalize_age_label(out.get("age", ""))
        actual_gender = (out.get("gender", "") or "").lower()
        actual_peak = (out.get("peak", "") or "").strip()

        expected_age = _expected_top_age(case.get("age_distribution") or {})
        expected_gender = _expected_top_gender(case.get("gender_distribution") or {})
        expected_peak = _expected_peak(case.get("time_distribution") or {})

        age_m = actual_age == expected_age
        gender_m = actual_gender == expected_gender
        peak_m = actual_peak == expected_peak
        composite = (int(age_m) + int(gender_m) + int(peak_m)) / 3.0
        passed = composite >= 2 / 3  # 3 중 2 이상

        return EvalResult(
            case_id=case.get("case_id", "unknown"),
            agent_id=self.agent_id,
            expected=f"{expected_age}/{expected_gender}/{expected_peak}",
            actual=f"{actual_age}/{actual_gender}/{actual_peak}",
            metric_name="metrics_match",
            metric_value=composite,
            passed=passed,
            details={
                "age_match": age_m,
                "gender_match": gender_m,
                "peak_match": peak_m,
            },
        )

    def aggregate(self, results: list[EvalResult]) -> EvalSummary:
        n = len(results)
        n_pass = sum(1 for r in results if r.passed)
        values = [r.metric_value for r in results]
        rule_pass_rates: dict[str, float] = {}
        for k in ["age_match", "gender_match", "peak_match"]:
            hits = sum(1 for r in results if r.details.get(k))
            rule_pass_rates[k] = hits / n if n else 0.0
        return EvalSummary(
            agent_id=self.agent_id,
            n_cases=n,
            n_passed=n_pass,
            metric_name="metrics_match",
            metric_mean=sum(values) / n if n else 0.0,
            metric_min=min(values) if values else 0.0,
            metric_max=max(values) if values else 0.0,
            confusion_matrix={"rule_pass_rates": rule_pass_rates},
            raw_results=results,
        )
