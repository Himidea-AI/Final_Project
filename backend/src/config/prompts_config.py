"""
LLM 프롬프트 버전 관리
에이전트별 시스템 프롬프트를 중앙 관리하여 일관성 유지.

사용법:
  각 Agent 노드에서 LLM 호출 시 이 딕셔너리에서 프롬프트를 가져와 사용.
  프롬프트 수정 시 PROMPT_VERSION을 올려서 변경 이력 추적.

  예시:
    from src.config.prompts_config import AGENT_PROMPTS
    prompt = AGENT_PROMPTS["competition"]

참고: chains/prompts.py에 각 Agent의 기본 페르소나 프롬프트가 정의되어 있음.
      이 파일은 프로덕션용 버전 관리 목적. 개발 초기에는 chains/prompts.py를 우선 사용.
"""

# 프롬프트 버전 — 변경 시 반드시 올릴 것
PROMPT_VERSION = "v0.1.0"

# 에이전트별 프롬프트 템플릿
# 키: Agent 노드 이름 (graph.py의 노드명과 일치)
# 값: LLM system prompt 문자열 (빈 문자열이면 chains/prompts.py의 기본값 사용)
AGENT_PROMPTS = {
    "commercial": "",      # 상권분석 Agent
    "population": "",      # 유동인구 Agent
    "demographics": "",    # 인구통계 Agent
    "cost": "",            # 비용산정 Agent
    "competition": "",     # 경쟁분석 Agent (카니발리제이션 포함)
    "trend": "",           # 트렌드 Agent (Naver DataLab)
    "legal": "",           # 법규검토 Agent (RAG)
    "report": "",          # 리포트 생성 Agent
    "supervisor": "",      # Supervisor (재분석 판단)
}
