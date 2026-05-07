"""legal specialist 인간 검수 인터페이스.

자동 평가 불가능 — 변호사·도메인 전문가 샘플 검수 필요.
이 evaluator 는 다음 역할만:
  1. 검수 대상 fixture 추출 (level + 인용 조문 + 권고)
  2. 변호사가 채점한 결과(JSON) 를 받아 EvalSummary 로 집계
  3. 자동 sanity 체크 (인용 조문 형식·필수 필드 존재 등)

실제 평가 흐름:
  · scripts/eval/export_legal_for_review.py — fixture → 변호사용 markdown/CSV
  · 변호사 채점 → review_results.json 작성
  · scripts/eval/run_legal_eval.py — review_results.json 로드 → EvalSummary
"""

from __future__ import annotations

import re
from typing import Any

from src.evaluation.evaluator import BaseEvaluator, EvalResult, EvalSummary

# 가맹사업법·식품위생법 등 조문 인용 형식 (예: "제12조의4", "제97조") 검증.
_ARTICLE_REF_RE = re.compile(r"제\d+조(의\d+)?")


class LegalEvaluator(BaseEvaluator):
    """legal specialist — 인간 검수 결과 집계 + 자동 sanity 만 수행."""

    agent_id = "legal"

    def __init__(
        self,
        fixtures: list[dict] | None = None,
        review_results: dict[str, dict] | None = None,
    ) -> None:
        # fixtures = [{case_id, brand, district, business_type, simulated_risk_items}]
        # review_results = {case_id: {level_correct: bool, articles_correct: bool,
        #                              recommendation_quality: 0~5, comments: str}}
        self._fixtures = fixtures
        self._review = review_results or {}

    async def prepare_dataset(self) -> list[dict]:
        return self._fixtures or []

    async def run_one(self, case: dict) -> Any:
        if "simulated_risk_items" in case:
            return case["simulated_risk_items"]
        raise NotImplementedError("case 에 'simulated_risk_items' 미포함")

    def score(self, case: dict, output: Any) -> EvalResult:
        case_id = case.get("case_id", "unknown")
        risk_items = output or []
        review = self._review.get(case_id)

        # 자동 sanity: 모든 risk_item 에 type/level/recommendation 존재 + 조문 인용 형식 OK.
        sanity_passed = self._sanity_check(risk_items)

        if review is None:
            # 인간 검수 미완료 — sanity 만 점수화 (인간 검수는 후속 작업).
            return EvalResult(
                case_id=case_id,
                agent_id=self.agent_id,
                expected="human_review_pending",
                actual="sanity_only",
                metric_name="composite_score",
                metric_value=1.0 if sanity_passed else 0.0,
                passed=sanity_passed,
                details={"sanity_passed": sanity_passed, "review_pending": True},
            )

        # 인간 검수 결과 포함 — level/articles/recommendation 가중 평균 (0~1).
        level_score = 1.0 if review.get("level_correct") else 0.0
        articles_score = 1.0 if review.get("articles_correct") else 0.0
        rec_quality = review.get("recommendation_quality", 0) / 5.0  # 0~5 → 0~1
        composite = level_score * 0.4 + articles_score * 0.3 + rec_quality * 0.3
        is_passed = composite >= 0.7 and sanity_passed
        return EvalResult(
            case_id=case_id,
            agent_id=self.agent_id,
            expected="composite >= 0.7 + human review",
            actual=composite,
            metric_name="composite_score",
            metric_value=composite,
            passed=is_passed,
            details={
                "level_correct": level_score,
                "articles_correct": articles_score,
                "recommendation_quality": rec_quality,
                "sanity_passed": sanity_passed,
                "comments": review.get("comments", ""),
            },
        )

    def _sanity_check(self, risk_items: list[dict]) -> bool:
        """자동 sanity — 형식·필수 필드 검증."""
        if not isinstance(risk_items, list) or len(risk_items) < 12:
            return False
        for item in risk_items:
            if not isinstance(item, dict):
                return False
            if item.get("level") not in {"safe", "caution", "danger"}:
                return False
            if not item.get("type") or not item.get("recommendation"):
                return False
            # 조문 인용 형식 검증 (articles 안에 "제N조" 패턴 존재)
            arts = item.get("articles", [])
            if isinstance(arts, list) and arts:
                refs = " ".join(str(a.get("article_ref", "")) for a in arts if isinstance(a, dict))
                if not _ARTICLE_REF_RE.search(refs):
                    return False
        return True

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
