"""demographic_depth.core_demographic 일치율 평가 (v7 재설계).

v6 까지: LLM-as-judge + match_score sanity check
v7 (2026-05-07): 핵심 연령·성별 직접 비교.
   LLM 이 *판단* 하는 것 = age_breakdown / gender_breakdown 분포에서
   1위 연령대·1위 성별 도출. 정답은 데이터 그 자체에서 룰로 산출 가능.

평가 지표:
   - age_match    : core_demographic.age 가 매출 1위 age_breakdown bucket 과 동일?
   - gender_match : core_demographic.gender 가 매출 1위 gender 와 동일? (mixed 허용)
   - composite    : 두 라벨 모두 맞으면 1.0, 한쪽만 0.5, 둘 다 틀리면 0.0
"""

from __future__ import annotations

from typing import Any

from src.evaluation.evaluator import BaseEvaluator, EvalResult, EvalSummary


def _expected_top_age(age_breakdown: dict) -> str:
    """매출 비중 1위 연령대 (예: '20' → '20-30')."""
    if not age_breakdown:
        return "unknown"
    top = max(age_breakdown.items(), key=lambda x: x[1] or 0, default=("unknown", 0))[0]
    mapping = {
        "10": "10-20",
        "20": "20-30",
        "30": "30-40",
        "40": "40-50",
        "50": "50-60",
        "60+": "60+",
    }
    return mapping.get(top, top)


def _expected_top_gender(gender_breakdown: dict) -> str:
    """매출 비중 1위 성별. 차이 10% 미만이면 mixed."""
    m = gender_breakdown.get("male", 0) or 0
    f = gender_breakdown.get("female", 0) or 0
    if m == 0 and f == 0:
        return "mixed"
    if abs(m - f) / max(m + f, 1) < 0.1:
        return "mixed"
    return "male" if m > f else "female"


class DemographicDepthEvaluator(BaseEvaluator):
    """demographic_depth.core_demographic 정확도 (v7).

    v6 LLM-as-judge 폐기. v7 = 데이터 분포에서 룰로 정답 산출 후 LLM 출력과 직접 비교.
    """

    agent_id = "demographic_depth"

    def __init__(self, fixtures: list[dict] | None = None) -> None:
        # fixtures = [{
        #   "case_id": str,
        #   "age_breakdown": dict,        # 시뮬 입력 (DB 매출 분해)
        #   "gender_breakdown": dict,     # 시뮬 입력
        #   "actual_age": str,            # LLM 출력 core_demographic.age (예: '20-30')
        #   "actual_gender": str,         # LLM 출력 core_demographic.gender
        # }]
        self._fixtures = fixtures

    async def prepare_dataset(self) -> list[dict]:
        return self._fixtures or []

    async def run_one(self, case: dict) -> dict:
        if "actual_age" in case and "actual_gender" in case:
            return {"age": case["actual_age"], "gender": case["actual_gender"]}
        raise NotImplementedError("case 에 'actual_age'/'actual_gender' 미포함")

    def score(self, case: dict, output: Any) -> EvalResult:
        actual_age = (output or {}).get("age", "")
        actual_gender = (output or {}).get("gender", "")
        expected_age = _expected_top_age(case.get("age_breakdown") or {})
        gender_breakdown = case.get("gender_breakdown") or {}

        age_match = actual_age.strip() == expected_age.strip()

        # gender 차원: gender_breakdown 이 비어있으면 평가 자체 보류 (캐시 데이터 한계).
        # age_match 만으로 score 결정. (이전 v7 초기 룰: gender 항상 fail → 50% 상한 회귀 차단.)
        if gender_breakdown:
            expected_gender = _expected_top_gender(gender_breakdown)
            gender_match = actual_gender.strip().lower() == expected_gender.strip().lower()
            composite = (1.0 if age_match else 0.0) * 0.5 + (1.0 if gender_match else 0.0) * 0.5
            passed = age_match and gender_match
            details = {
                "age_match": age_match,
                "gender_match": gender_match,
                "expected_age": expected_age,
                "expected_gender": expected_gender,
                "actual_age": actual_age,
                "actual_gender": actual_gender,
            }
            expected_label = f"{expected_age} / {expected_gender}"
        else:
            # gender 평가 보류 — age 만으로 평가
            composite = 1.0 if age_match else 0.0
            passed = age_match
            details = {
                "age_match": age_match,
                "gender_match": None,  # 평가 보류
                "expected_age": expected_age,
                "actual_age": actual_age,
                "actual_gender": actual_gender,
                "note": "gender_breakdown 캐시 부재 — age 차원만 평가",
            }
            expected_label = f"{expected_age} (gender 보류)"

        return EvalResult(
            case_id=case.get("case_id", "unknown"),
            agent_id=self.agent_id,
            expected=expected_label,
            actual=f"{actual_age} / {actual_gender}",
            metric_name="core_match",
            metric_value=composite,
            passed=passed,
            details=details,
        )

    def aggregate(self, results: list[EvalResult]) -> EvalSummary:
        n = len(results)
        n_pass = sum(1 for r in results if r.passed)
        values = [r.metric_value for r in results]
        return EvalSummary(
            agent_id=self.agent_id,
            n_cases=n,
            n_passed=n_pass,
            metric_name="core_match",
            metric_mean=sum(values) / n if n else 0.0,
            metric_min=min(values) if values else 0.0,
            metric_max=max(values) if values else 0.0,
            raw_results=results,
        )
