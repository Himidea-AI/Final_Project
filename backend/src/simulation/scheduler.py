"""시간/공간 스케줄러 - LLM 호출 X.

- 시간 진행 (시간 단위)
- 에이전트 활성화 여부 (이벤트 기반 호출 절감)
- 일별 리셋
"""

from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .agents import Agent, Tier
from .conversation import ConversationEngine
from .world import World
from .world_loader import StoreHoursMap, store_open_at


@dataclass
class StepResult:
    hour: int
    activated: int  # 의사결정 수행한 에이전트 수
    skipped: int  # 이벤트 미발생으로 스킵
    decisions: list  # Decision 리스트


class Scheduler:
    """시간 단위로 진행. 이벤트 기반 활성화로 LLM 호출 절감."""

    def __init__(
        self,
        world: World,
        agents: list[Agent],
        seed: int = 42,
        hours_map: StoreHoursMap | None = None,
        llm_concurrency: int = 4,
        conversation: ConversationEngine | None = None,
    ):
        self.world = world
        self.agents = agents
        self.rng = random.Random(seed)
        self.hours_map = hours_map
        self.llm_concurrency = max(1, llm_concurrency)
        self.conversation = conversation

    # -----------------------------------------------------------
    def is_active(self, agent: Agent) -> bool:
        """이벤트 기반 활성화 - 행동 분기점만 LLM 호출."""
        h = self.world.current_hour
        # 휴식 시간대 (이른 새벽)는 95% 스킵
        if h < 7 or h >= 25:
            return self.rng.random() < 0.05
        # 분기점 시간대 (식사/이동)
        if h in (8, 12, 13, 18, 19, 20, 21):
            return True
        # 그 외 시간대는 30% 활성화
        return self.rng.random() < 0.3

    # -----------------------------------------------------------
    def step(self, brain) -> StepResult:
        """한 시간 진행."""
        decisions = []
        activated = 0
        skipped = 0

        # 매 시간 친구 간 원시어 대화 dispatch (Tier S 일부)
        if self.conversation is not None:
            try:
                self.conversation.step(self.world, self.agents)
            except Exception as e:
                print(f"[scheduler] conversation step 실패: {e}")

        # 매 시간 영업상태 갱신
        h = self.world.current_hour % 24
        wd = self.world.weekday
        if self.hours_map is not None:
            for sid, s in self.world.stores.items():
                s.is_open_now = store_open_at(self.hours_map, sid, wd, h)
        else:
            for s in self.world.stores.values():
                s.is_open_now = True

        # 에이전트 순서 셔플 (편향 방지)
        order = list(self.agents)
        self.rng.shuffle(order)

        # 활성 에이전트를 Tier별로 분리:
        # - B(규칙): LLM 호출 X → sequential 충분
        # - S/A(LLM): ThreadPoolExecutor로 동시 호출 → Ollama NUM_PARALLEL 활용
        rule_active: list[Agent] = []
        llm_active: list[Agent] = []
        for a in order:
            if not self.is_active(a):
                skipped += 1
                continue
            if a.tier == Tier.B:
                rule_active.append(a)
            else:
                llm_active.append(a)

        # 1) LLM 에이전트 병렬 결정 (apply는 아직 하지 않음 — race 방지)
        llm_decisions: list = []
        if llm_active:

            def _decide(a: Agent):
                return (a, a.decide(self.world, brain, self.rng))

            if self.llm_concurrency > 1:
                with ThreadPoolExecutor(max_workers=self.llm_concurrency) as ex:
                    llm_decisions = list(ex.map(_decide, llm_active))
            else:
                llm_decisions = [_decide(a) for a in llm_active]

        # 2) 결정 적용 (main thread — World 갱신 race 방지)
        for a, dec in llm_decisions:
            a.apply(dec, self.world)
            decisions.append((a.agent_id, dec))
            activated += 1

        # 3) 규칙 에이전트 (sequential, 저비용)
        for a in rule_active:
            dec = a.decide(self.world, brain, self.rng)
            a.apply(dec, self.world)
            decisions.append((a.agent_id, dec))
            activated += 1

        result = StepResult(
            hour=self.world.current_hour,
            activated=activated,
            skipped=skipped,
            decisions=decisions,
        )
        self.world.current_hour += 1
        return result

    # -----------------------------------------------------------
    def end_of_day(self) -> None:
        """일별 리셋."""
        self.world.reset_daily()
        self.world.current_hour = 6  # 다음날 06:00
        self.world.weekday = (self.world.weekday + 1) % 7
        self.world.is_weekend = self.world.weekday in (5, 6)
        for a in self.agents:
            a.budget_today = max(15000, a.budget_today * 0.5 + 30000)
            a.spent_today = 0
            a.visited_today.clear()
