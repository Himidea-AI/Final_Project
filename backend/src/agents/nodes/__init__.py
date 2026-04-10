"""
Agent 노드 모듈 — 마포구 프랜차이즈 상권분석 시뮬레이터 (2노드 선형 체제)

이 패키지는 LangGraph 워크플로우를 구성하는 핵심 분석 엔진들을 포함합니다.
2026-04-10 아키텍처 리팩토링을 통해 기존 11개 노드를 다음 2개의 전략적 노드로 압축했습니다.

주요 노드:
  - context_analyst.py      : 마포구 16개동 전수 스카우팅, Top 3 선별 및 브랜드 경쟁력 대조 분석
  - strategy_synthesizer.py : 최적 입지 대상 법률 리스크(RAG) 검토 및 최종 전략 JSON 리포트 합성
"""

from .context_analyst import context_analyst_node
from .strategy_synthesizer import strategy_synthesizer_node

__all__ = ["context_analyst_node", "strategy_synthesizer_node"]
