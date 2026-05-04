"""LLM 에이전트 정확도 평가 framework.

7개 LLM 의존 에이전트의 출력을 측정 가능한 metric 으로 검증.
inflow / district_ranking 은 정량 룰엔진이라 평가 범위 외.

평가 분류:
  A. 자동 정량 (분류 라벨 정확도)  — trend_forecaster, competitor_intel
  B. LLM-as-judge (자연어 본문)    — market_analyst, population, demographic_depth, synthesis
  C. 인간 검수 (도메인 전문성)     — legal

공통 인터페이스는 BaseEvaluator (evaluator.py) 를 따름.
실행은 scripts/eval/run_*.py 로.
"""

from src.evaluation.evaluator import BaseEvaluator, EvalResult

__all__ = ["BaseEvaluator", "EvalResult"]
