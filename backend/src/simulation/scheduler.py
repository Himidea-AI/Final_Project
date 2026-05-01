"""시간/공간 스케줄러 - LLM 호출 X.

- 시간 진행 (시간 단위)
- 에이전트 활성화 여부 (이벤트 기반 호출 절감)
- 일별 리셋
"""

from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .agents import Agent, Decision, Tier
from .conversation import ConversationEngine
from .world import World
from .world_loader import StoreHoursMap, store_open_at


@dataclass
class StepResult:
    hour: int
    activated: int  # 의사결정 수행한 에이전트 수
    skipped: int  # 이벤트 미발생으로 스킵
    decisions: list[tuple[int, Decision]]  # (agent_id, Decision) 튜플 리스트


class Scheduler:
    """시간 단위로 진행. 이벤트 기반 활성화로 LLM 호출 절감."""

    def __init__(
        self,
        world: World,
        agents: list[Agent],
        seed: int = 42,
        hours_map: StoreHoursMap | None = None,
        llm_concurrency: int = 8,
        conversation: ConversationEngine | None = None,
    ):
        self.world = world
        self.agents = agents
        self.rng = random.Random(seed)
        self.hours_map = hours_map
        self.llm_concurrency = max(1, llm_concurrency)
        self.conversation = conversation
        # ThreadPool 재사용 — 매 step 생성/소멸 비용 회피 (1일 시뮬 = 20 step).
        self._executor: ThreadPoolExecutor | None = (
            ThreadPoolExecutor(max_workers=self.llm_concurrency) if self.llm_concurrency > 1 else None
        )

    # -----------------------------------------------------------
    def is_active(self, agent: Agent) -> bool:
        """시간대별 활성률 — 통계청 「2024년 생활시간조사」 raw table 기반.

        출처: 통계청 「2024년 생활시간조사 결과」 (보도자료 2025-07-28, PDF p.17, 23, 29)
            kostat.go.kr/board.es?mid=a10301010000&bid=220&list_no=437764
        시간별 일·근로 행위자 비율 (2024 전체):
            18:00 25.0% / 18:30 22.1% / 19:00 17.4% / 19:30 16.3%
            20:00 13.5% / 20:30 12.6% / 21:00 9.8%
        시간별 수면 행위자 비율:
            21:00 26.9% / 22:00 19.4% / 23:00 12.8% / 24:00 7.3%
        18-21시 종합 (PDF p.17): 일·근로 15.3% + 식사 14.1% + 개인유지 6.1% +
            가사 5.9% + TV 5.5% = ~47% (이동 제외)
        → "활성" = 외출/이동/방문/근무 등 외부 활동. TV·식사·가사는 비활성으로 분류.

        시간별 활성률 (외부 활동만):
            새벽/심야 (0~6, 24+): 5% (수면 90%+)
            아침 출근 (7, 8): 85% / 70% (출근 피크)
            점심 (12, 13): 70% (외식·이동 빈번)
            저녁 (18, 19): 75% / 50% (퇴근 → 19시 일·근로 17%)
            늦저녁 (20, 21): 35% / 25% (TV·식사 비중 ↑, 일·근로 9.8%)
            22, 23: 15% (수면 준비)
            기타 주간: 30% (의무활동 30.6%)
        """
        h = self.world.current_hour
        # 새벽/심야 — 수면
        if h < 7 or h >= 24:
            return self.rng.random() < 0.05
        # 출근 피크 (08시 일·근로 시작)
        if h == 8:
            return self.rng.random() < 0.85
        if h == 7:
            return self.rng.random() < 0.50
        # 점심 (외식·이동)
        if h in (12, 13):
            return self.rng.random() < 0.70
        # 퇴근/저녁 외출 (18시 일·근로 25% + 외출/식사)
        if h == 18:
            return self.rng.random() < 0.75
        if h == 19:
            return self.rng.random() < 0.50
        # 늦저녁 — 일·근로 비율 급감
        if h == 20:
            return self.rng.random() < 0.35
        if h == 21:
            return self.rng.random() < 0.25
        # 22-23: 수면 준비
        if h in (22, 23):
            return self.rng.random() < 0.15
        # 기타 주간 (9~11, 14~17) — 의무활동
        return self.rng.random() < 0.30

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
        # Tier S: batch_smart_decide 로 N agents 한 번에 호출 (~10x 호출 절감)
        # Tier A: 기존 ThreadPool 병렬 호출 유지
        llm_decisions: list = []
        if llm_active:
            tier_s_active: list[Agent] = []
            tier_a_active: list[Agent] = []
            for a in llm_active:
                if a.tier == Tier.S:
                    tier_s_active.append(a)
                else:
                    tier_a_active.append(a)

            # Tier S — Hierarchical Planning + batch fallback
            # 1단계: daily_plan 슬롯 있으면 LLM 호출 없이 변환 (paper UIST'23 패턴)
            # 2단계: 슬롯 없는 agent 만 batch_smart_decide 로 묶어 1 호출
            if tier_s_active and getattr(self.world, "tier_s_llm_only", False) and hasattr(brain, "batch_smart_decide"):
                planned: list[Agent] = []
                unplanned: list[Agent] = []
                hour = self.world.current_hour
                for a in tier_s_active:
                    slot = a.get_plan_slot(hour) if hasattr(a, "get_plan_slot") else None
                    if slot is not None:
                        planned.append(a)
                        try:
                            dec = brain.decision_from_plan_slot(a, self.world, slot)
                        except Exception as e:
                            print(f"[scheduler] plan slot → Decision 실패: {e}")
                            dec = a.decide(self.world, brain, self.rng)
                        llm_decisions.append((a, dec))
                    else:
                        unplanned.append(a)
                # 슬롯 없는 agent 는 batch LLM
                if unplanned:
                    try:
                        pairs = brain.batch_smart_decide(unplanned, self.world)
                        by_id = {a.agent_id: a for a in unplanned}
                        for aid, dec in pairs:
                            a = by_id.get(aid)
                            if a is not None:
                                llm_decisions.append((a, dec))
                    except Exception as e:
                        print(f"[scheduler] batch_smart_decide 실패 — single fallback: {e}")
                        for a in unplanned:
                            llm_decisions.append((a, a.decide(self.world, brain, self.rng)))
            else:
                # 기존 single-call 경로 (tier_s_llm_only=False 또는 batch 미지원)
                for a in tier_s_active:
                    llm_decisions.append((a, a.decide(self.world, brain, self.rng)))

            # Tier A — 기존 ThreadPool 병렬
            if tier_a_active:

                def _decide(a: Agent):
                    return (a, a.decide(self.world, brain, self.rng))

                if self._executor is not None:
                    llm_decisions.extend(list(self._executor.map(_decide, tier_a_active)))
                else:
                    llm_decisions.extend([_decide(a) for a in tier_a_active])

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
    def shutdown(self) -> None:
        """시뮬 종료 시 ThreadPool 정리. run_simulation finally 에서 호출 권장."""
        if self._executor is not None:
            self._executor.shutdown(wait=False)
            self._executor = None

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
