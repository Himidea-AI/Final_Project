"""각 에이전트 노드에서 AgentAttribution dict를 만드는 헬퍼."""

from typing import Optional

from src.schemas.structured_output import AgentAttribution


def build_attribution(
    agent_id: str,
    display_name: str,
    kind: str,
    sources: list[str],
    verdict: str,
    reasoning: str,
    confidence: Optional[float] = None,
    status: str = "success",
) -> dict:
    """AgentAttribution을 dict로 반환. 노드 return dict에 'agent_attribution' 키로 넣음."""
    attr = AgentAttribution(
        id=agent_id,  # type: ignore[arg-type]
        display_name=display_name,
        kind=kind,  # type: ignore[arg-type]
        sources=sources,
        verdict=verdict[:80],  # 80자 제한
        reasoning=reasoning[:400],  # 안전 제한
        confidence=confidence,
        status=status,  # type: ignore[arg-type]
    )
    return attr.model_dump()
