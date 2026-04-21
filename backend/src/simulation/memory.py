"""계층화된 메모리 - Raw → 일일 요약 → Reflection.

토큰 절감 핵심:
- Raw: 모든 행동 로그 (메모리만, LLM에 안들어감)
- Reflection: 하루 끝에 1회 요약 (~50 tok) → 다음날 페르소나에 주입
- Embedding 검색은 별도 모듈 (chromadb 활용 권장)
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class MemoryEvent:
    day: int
    hour: int
    action: str
    target: str = ""
    detail: str = ""


@dataclass
class AgentMemory:
    agent_id: int
    raw: deque[MemoryEvent] = field(default_factory=lambda: deque(maxlen=200))
    daily_summary: list[str] = field(default_factory=list)  # day별 1줄

    def add(self, day: int, hour: int, action: str, target: str = "", detail: str = "") -> None:
        self.raw.append(MemoryEvent(day, hour, action, target, detail))

    def summarize_day(self, day: int) -> str:
        """LLM 없이 통계 기반 요약 (토큰 0)."""
        events = [e for e in self.raw if e.day == day]
        if not events:
            return f"D{day}: 활동 없음"
        visits = sum(1 for e in events if e.action == "visit")
        moves = sum(1 for e in events if e.action == "move")
        targets = [e.target for e in events if e.target][:3]
        line = f"D{day}: 방문 {visits}, 이동 {moves}, 주요지: {','.join(targets)}"
        self.daily_summary.append(line)
        return line


class MemoryStore:
    """전체 에이전트 메모리 컨테이너."""

    def __init__(self):
        self.by_agent: dict[int, AgentMemory] = {}

    def of(self, agent_id: int) -> AgentMemory:
        if agent_id not in self.by_agent:
            self.by_agent[agent_id] = AgentMemory(agent_id=agent_id)
        return self.by_agent[agent_id]

    def end_of_day(self, day: int) -> None:
        for mem in self.by_agent.values():
            mem.summarize_day(day)
