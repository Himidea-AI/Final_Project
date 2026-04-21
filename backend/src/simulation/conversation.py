"""에이전트 간 원시어 DSL 대화 시스템.

극단적 토큰 절감 목표:
- 메시지 1회: 발신 ~40 tok + 응답 ~10 tok
- 하루 총 ~1,000 tok (1000 에이전트 기준, Tier S 대화만)

문법 (단일 라인, 대괄호로 구분):
  [INV cat=카페 dong=연남 h=14]   ← 14시 연남 카페 초대
  [ACC]                            ← 승낙
  [DEC reason=budget]              ← 거절 + 이유
  [PROMO sid=42]                   ← 점주 → 친구 매장 홍보
  [INFO sid=42 rate=good]          ← 경험 공유

영향:
  - INV 수락 → receiver의 pending_invites 에 추가 → 다음 decide 때 category/dong 힌트
  - PROMO → receiver의 store bias
  - INFO → pgvector memory 기록 + 다음 decide 참조
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agents import Agent
    from .brain import LLMBrain
    from .world import World


# ---------------------------------------------------------------
# DSL 파서
# ---------------------------------------------------------------
DSL_RE = re.compile(r"\[(\w+)([^\]]*)\]")
KV_RE = re.compile(r"(\w+)=([^\s\]]+)")

VERBS = {"INV", "ACC", "DEC", "PROMO", "INFO"}


@dataclass
class Message:
    verb: str  # INV/ACC/DEC/PROMO/INFO
    sender_id: int
    receiver_id: int
    hour: int
    args: dict[str, str] = field(default_factory=dict)
    raw: str = ""

    def encoded(self) -> str:
        """DSL 문자열로."""
        if not self.args:
            return f"[{self.verb}]"
        pairs = " ".join(f"{k}={v}" for k, v in self.args.items())
        return f"[{self.verb} {pairs}]"


def parse_dsl(text: str) -> Message | None:
    """LLM 응답에서 [VERB k=v] 패턴 추출."""
    if not text:
        return None
    m = DSL_RE.search(text)
    if not m:
        return None
    verb = m.group(1).upper()
    if verb not in VERBS:
        return None
    args = dict(KV_RE.findall(m.group(2) or ""))
    return Message(verb=verb, sender_id=-1, receiver_id=-1, hour=0, args=args, raw=m.group(0))


# ---------------------------------------------------------------
# 친구 네트워크 빌더
# ---------------------------------------------------------------
def build_friends(agents: list["Agent"], k_per_agent: int = 3, seed: int = 42) -> None:
    """같은 동 + 연령 ±10 에이전트 중 랜덤 k명을 친구로 양방향 연결."""
    rng = random.Random(seed)
    from collections import defaultdict

    by_dong: dict[str, list["Agent"]] = defaultdict(list)
    for a in agents:
        by_dong[a.home_dong].append(a)

    for a in agents:
        pool = [b for b in by_dong[a.home_dong] if b.agent_id != a.agent_id and abs(b.age - a.age) <= 10]
        if not pool:
            pool = [b for b in by_dong[a.home_dong] if b.agent_id != a.agent_id]
        if not pool:
            continue
        picks = rng.sample(pool, min(k_per_agent, len(pool)))
        for p in picks:
            if p.agent_id not in a.friends:
                a.friends.append(p.agent_id)
            if a.agent_id not in p.friends:
                p.friends.append(a.agent_id)


# ---------------------------------------------------------------
# ConversationEngine
# ---------------------------------------------------------------
class ConversationEngine:
    """매 시간 Tier S 에이전트 pair 중 일부가 원시어 메시지 교환."""

    def __init__(
        self,
        brain: "LLMBrain",
        max_chats_per_step: int = 2,
        seed: int = 42,
    ):
        self.brain = brain
        self.max_chats_per_step = max_chats_per_step
        self.rng = random.Random(seed)
        self.log: list[Message] = []

    # -----------------------------------------------------------
    def step(self, world: "World", agents: list["Agent"]) -> list[Message]:
        """한 시간 step에서 대화 dispatch."""
        # Tier S 에이전트 중 friends 있는 애들만
        from .agents import Tier

        tier_s = [a for a in agents if a.tier == Tier.S and a.friends]
        if not tier_s:
            return []

        msgs: list[Message] = []
        # 최대 N 쌍 랜덤 선택
        candidates = list(tier_s)
        self.rng.shuffle(candidates)

        for sender in candidates[: self.max_chats_per_step]:
            # sender의 friends 중 랜덤 1명
            by_id = {a.agent_id: a for a in agents}
            friend_id = self.rng.choice(sender.friends)
            receiver = by_id.get(friend_id)
            if receiver is None:
                continue

            msg = self._chat_once(world, sender, receiver)
            if msg is not None:
                msgs.append(msg)
                self._apply_effect(msg, sender, receiver, world)

        self.log.extend(msgs)
        return msgs

    # -----------------------------------------------------------
    def _chat_once(self, world: "World", sender: "Agent", receiver: "Agent") -> Message | None:
        """LLM 1회 호출 (Tier S 모델). 발신 DSL 생성."""
        # 현재 brain의 Tier S 채널 재사용
        if self.brain.cfg.mock_mode:
            return self._mock_msg(sender, receiver, world)

        prompt = self._build_prompt(sender, receiver, world)
        text = self._call_llm(prompt)
        parsed = parse_dsl(text)
        if parsed is None:
            return None
        parsed.sender_id = sender.agent_id
        parsed.receiver_id = receiver.agent_id
        parsed.hour = world.current_hour
        return parsed

    # -----------------------------------------------------------
    def _build_prompt(self, sender: "Agent", receiver: "Agent", world: "World") -> str:
        """극도 압축 프롬프트 (~40 tok)."""
        sender_tag = sender.profile.lifestyle_tag if sender.profile else sender.role.value
        receiver_tag = receiver.profile.lifestyle_tag if receiver.profile else receiver.role.value
        return (
            f"당신은 {sender.name}({sender_tag}). 친구 {receiver.name}({receiver_tag})에게 "
            f"지금 {world.current_hour}시, 원시어 DSL 1줄로 제안 or 거절:\n"
            f"[INV cat=카페|음식점|주점 dong=동명 h=시] | [ACC] | [DEC reason=budget|tired] | [INFO sid=번호 rate=good|bad]\n"
            f"출력: 대괄호 1개만."
        )

    def _call_llm(self, prompt: str) -> str:
        """brain 내부의 Tier S 채널 호출. ollama/openai/gemini 지원."""
        cfg = self.brain.cfg
        try:
            if cfg.tier_s_provider == "ollama" and self.brain._ollama is not None:
                r = self.brain._ollama.chat.completions.create(
                    model=cfg.tier_s_model,
                    max_tokens=30,
                    temperature=0.5,
                    messages=[{"role": "user", "content": prompt}],
                )
                usage = r.usage
                self.brain.stats.tier_s_input_tokens += getattr(usage, "prompt_tokens", 0) or 0
                self.brain.stats.tier_s_output_tokens += getattr(usage, "completion_tokens", 0) or 0
                return r.choices[0].message.content or ""
            if cfg.tier_s_provider == "openai" and self.brain._openai is not None:
                r = self.brain._openai.chat.completions.create(
                    model=cfg.tier_s_model,
                    max_tokens=30,
                    temperature=0.5,
                    messages=[{"role": "user", "content": prompt}],
                )
                usage = r.usage
                self.brain.stats.tier_s_input_tokens += getattr(usage, "prompt_tokens", 0) or 0
                self.brain.stats.tier_s_output_tokens += getattr(usage, "completion_tokens", 0) or 0
                return r.choices[0].message.content or ""
            if cfg.tier_s_provider == "gemini" and self.brain._gemini_s is not None:
                r = self.brain._gemini_s.generate_content(
                    prompt,
                    generation_config={"temperature": 0.5, "max_output_tokens": 30},
                )
                try:
                    u = r.usage_metadata
                    self.brain.stats.tier_s_input_tokens += u.prompt_token_count
                    self.brain.stats.tier_s_output_tokens += u.candidates_token_count
                except Exception:
                    pass
                return r.text or ""
        except Exception as e:
            print(f"[chat] LLM 실패: {e}")
        return ""

    # -----------------------------------------------------------
    def _mock_msg(self, sender: "Agent", receiver: "Agent", world: "World") -> Message:
        verb = self.rng.choice(["INV", "ACC", "INFO"])
        if verb == "INV":
            cat = self.rng.choice(["카페", "음식점", "주점"])
            args = {"cat": cat, "dong": sender.current_dong, "h": str(world.current_hour + 1)}
        elif verb == "INFO":
            args = {"sid": str(self.rng.randint(1, 100)), "rate": self.rng.choice(["good", "bad"])}
        else:
            args = {}
        return Message(
            verb=verb,
            sender_id=sender.agent_id,
            receiver_id=receiver.agent_id,
            hour=world.current_hour,
            args=args,
            raw=f"[{verb}]",
        )

    # -----------------------------------------------------------
    # 대화 결과 → 상태 변경
    # -----------------------------------------------------------
    def _apply_effect(self, msg: Message, sender: "Agent", receiver: "Agent", world: "World") -> None:
        if msg.verb == "INV":
            cat = msg.args.get("cat")
            dong = msg.args.get("dong") or sender.current_dong
            if cat:
                # 'h=8시' 같은 유닛 섞인 값 방어 (숫자만 추출)
                h_raw = str(msg.args.get("h", world.current_hour + 1))
                h_digits = re.sub(r"\D", "", h_raw) or str(world.current_hour + 1)
                try:
                    hour = int(h_digits)
                except ValueError:
                    hour = world.current_hour + 1
                receiver.pending_invites.append(
                    {
                        "from": sender.agent_id,
                        "cat": cat,
                        "dong": dong,
                        "hour": hour,
                    }
                )
        elif msg.verb == "PROMO":
            sid = msg.args.get("sid")
            if sid:
                try:
                    receiver.store_bias[int(sid)] = receiver.store_bias.get(int(sid), 1.0) * 1.5
                except Exception:
                    pass
        elif msg.verb == "INFO":
            sid = msg.args.get("sid")
            rate = msg.args.get("rate", "good")
            if sid:
                try:
                    factor = 1.3 if rate == "good" else 0.7
                    receiver.store_bias[int(sid)] = receiver.store_bias.get(int(sid), 1.0) * factor
                except Exception:
                    pass
