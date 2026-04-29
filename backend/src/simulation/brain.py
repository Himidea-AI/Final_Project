"""LLM 라우터 - Tier S(Haiku+cache) / Tier A(Gemini Flash) / Mock.

핵심 토큰 절감:
- Anthropic prompt caching: 페르소나 프로필을 ephemeral 캐시
- 동적 컨텍스트는 100 tok 미만으로 압축
- Gemini Flash는 Tier A에 전용 (간결 출력 강제)
- mock 모드: API 키 없을 때 결정적 의사결정
"""

from __future__ import annotations

import json
import os
import random
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .agents import Decision
from .config import ModelConfig
from .personas import Persona

if TYPE_CHECKING:
    from .agents import Agent
    from .memory_index import PgVectorMemory
    from .world import World


@dataclass
class CallStats:
    tier_s_calls: int = 0
    tier_a_calls: int = 0
    tier_s_input_tokens: int = 0
    tier_s_output_tokens: int = 0
    tier_s_cache_read: int = 0
    tier_s_cache_write: int = 0
    tier_a_input_tokens: int = 0
    tier_a_output_tokens: int = 0
    failures: int = 0
    # Thought (시각화용 내적 독백) — smart_decide 와 분리 카운트
    thought_calls: int = 0
    thought_input_tokens: int = 0
    thought_output_tokens: int = 0
    thought_cache_read: int = 0


class LLMBrain:
    """Tier S/A 라우터.

    실제 API 호출은 mock_mode=False 일 때만. 키가 없거나 mock_mode=True면
    내부적으로 결정적 fallback을 씀 → 비용 0으로 파이프라인 검증 가능.
    """

    def __init__(
        self,
        cfg: ModelConfig | None = None,
        seed: int = 42,
        memory_index: "PgVectorMemory | None" = None,
    ):
        self.cfg = cfg or ModelConfig()
        self.stats = CallStats()
        self.personas: dict[int, Persona] = {}
        self._rng = random.Random(seed)
        self._anth = None
        self._gemini = None
        self._gemini_s = None
        self._openai = None
        self._ollama = None
        self.memory_index = memory_index

        # provider 자동 다운그레이드: 키 없으면 openai → mock 순으로 fallback
        self._auto_downgrade()

        if not self.cfg.mock_mode:
            self._init_clients()

    # -----------------------------------------------------------
    def _key_ok(self, env_var: str) -> bool:
        v = os.getenv(env_var, "")
        return bool(v) and not v.startswith("your_")

    def _ollama_alive(self) -> bool:
        try:
            import httpx

            r = httpx.get(self.cfg.ollama_base_url.replace("/v1", "/api/tags"), timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def _auto_downgrade(self) -> None:
        """provider별 키 검사 후 사용 가능한 provider로 자동 전환.

        우선순위: 명시 provider → OpenAI → Ollama → mock
        """
        if self.cfg.mock_mode:
            return

        ollama_ok = self._ollama_alive()

        # Tier S
        if self.cfg.tier_s_provider == "anthropic" and not self._key_ok("ANTHROPIC_API_KEY"):
            if self._key_ok("OPENAI_API_KEY"):
                print("[brain] ANTHROPIC 키 없음 → Tier S를 OpenAI gpt-4o-mini로 다운그레이드")
                self.cfg.tier_s_provider = "openai"
                self.cfg.tier_s_model = "gpt-4o-mini"
            elif ollama_ok:
                print(f"[brain] ANTHROPIC/OPENAI 키 없음 → Tier S를 Ollama {self.cfg.ollama_model}로 다운그레이드")
                self.cfg.tier_s_provider = "ollama"
                self.cfg.tier_s_model = self.cfg.ollama_model
            else:
                self.cfg.mock_mode = True
        # OpenAI provider 명시했지만 키 부재 → silent AuthenticationError 회피.
        # ollama 가능하면 ollama 로, 아니면 mock_mode 강제 + 명시 로그.
        elif self.cfg.tier_s_provider == "openai" and not self._key_ok("OPENAI_API_KEY"):
            if ollama_ok:
                print(f"[brain] OPENAI 키 없음 → Tier S를 Ollama {self.cfg.ollama_model}로 다운그레이드")
                self.cfg.tier_s_provider = "ollama"
                self.cfg.tier_s_model = self.cfg.ollama_model
            else:
                print("[brain] ⚠️ OPENAI_API_KEY 부재 → Tier S MOCK 모드. .env 확인 필요.")
                self.cfg.mock_mode = True

        # Tier A
        if self.cfg.tier_a_provider == "gemini" and not (
            self._key_ok("GOOGLE_API_KEY") or self._key_ok("GEMINI_API_KEY")
        ):
            if ollama_ok:
                print(f"[brain] GEMINI 키 없음 → Tier A를 Ollama {self.cfg.ollama_model}로 다운그레이드")
                self.cfg.tier_a_provider = "ollama"
                self.cfg.tier_a_model = self.cfg.ollama_model
            elif self._key_ok("OPENAI_API_KEY"):
                print("[brain] GEMINI 키 없음 → Tier A를 OpenAI gpt-4.1-nano로 다운그레이드")
                self.cfg.tier_a_provider = "openai"
                self.cfg.tier_a_model = "gpt-4.1-nano"
        # Tier A 도 OpenAI 명시 + 키 부재 케이스 처리.
        elif self.cfg.tier_a_provider == "openai" and not self._key_ok("OPENAI_API_KEY"):
            if ollama_ok:
                print(f"[brain] OPENAI 키 없음 → Tier A를 Ollama {self.cfg.ollama_model}로 다운그레이드")
                self.cfg.tier_a_provider = "ollama"
                self.cfg.tier_a_model = self.cfg.ollama_model
            else:
                print("[brain] ⚠️ OPENAI_API_KEY 부재 → Tier A MOCK 모드.")
                self.cfg.mock_mode = True

    def _init_clients(self) -> None:
        # OpenAI (Tier S 또는 A에서 사용 가능)
        if "openai" in (self.cfg.tier_s_provider, self.cfg.tier_a_provider):
            try:
                from openai import OpenAI

                self._openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            except Exception as e:
                print(f"[brain] OpenAI 초기화 실패: {e}")
                self.cfg.mock_mode = True
                return

        # Ollama (OpenAI 호환 API → 같은 SDK 재사용)
        if "ollama" in (self.cfg.tier_s_provider, self.cfg.tier_a_provider):
            try:
                from openai import OpenAI

                self._ollama = OpenAI(
                    base_url=self.cfg.ollama_base_url,
                    api_key="ollama",  # 더미 (Ollama 검사 안 함)
                )
            except Exception as e:
                print(f"[brain] Ollama 클라이언트 초기화 실패: {e}")
                self.cfg.mock_mode = True
                return

        if self.cfg.tier_s_provider == "anthropic":
            try:
                import anthropic

                self._anth = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            except Exception as e:
                print(f"[brain] Anthropic 초기화 실패: {e}")
                self.cfg.mock_mode = True

        if "gemini" in (self.cfg.tier_s_provider, self.cfg.tier_a_provider):
            try:
                import google.generativeai as genai

                gkey = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
                genai.configure(api_key=gkey)
                # Tier A용 모델 (주 호출)
                self._gemini = genai.GenerativeModel(self.cfg.tier_a_model)
                # Tier S가 Gemini면 별도 모델 (동일/상위 모델)
                if self.cfg.tier_s_provider == "gemini":
                    self._gemini_s = genai.GenerativeModel(self.cfg.tier_s_model)
                else:
                    self._gemini_s = None
            except Exception as e:
                print(f"[brain] Gemini 초기화 실패: {e}")
                self._gemini = None
                self._gemini_s = None

    # -----------------------------------------------------------
    def register_personas(self, personas: dict[int, Persona]) -> None:
        self.personas.update(personas)

    # -----------------------------------------------------------
    # Tier S: Haiku + Prompt Cache
    # -----------------------------------------------------------
    def smart_decide(self, agent: "Agent", world: "World") -> Decision:
        self.stats.tier_s_calls += 1
        ctx = self._dynamic_context(agent, world)

        if self.cfg.mock_mode:
            return self._mock_decide(agent, world, tier="S")

        persona = self.personas.get(agent.agent_id)
        if persona is None:
            return self._mock_decide(agent, world, tier="S")

        if self.cfg.tier_s_provider == "openai":
            return self._smart_decide_openai(agent, world, ctx, persona)

        if self.cfg.tier_s_provider == "ollama":
            return self._smart_decide_ollama(agent, world, ctx, persona)

        if self.cfg.tier_s_provider == "gemini":
            return self._smart_decide_gemini(agent, world, ctx, persona)

        if self._anth is None:
            return self._mock_decide(agent, world, tier="S")

        try:
            resp = self._anth.messages.create(
                model=self.cfg.tier_s_model,
                max_tokens=self.cfg.tier_s_max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": persona.full_profile,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": ctx}],
            )
            usage = resp.usage
            self.stats.tier_s_input_tokens += getattr(usage, "input_tokens", 0)
            self.stats.tier_s_output_tokens += getattr(usage, "output_tokens", 0)
            self.stats.tier_s_cache_read += getattr(usage, "cache_read_input_tokens", 0)
            self.stats.tier_s_cache_write += getattr(usage, "cache_creation_input_tokens", 0)
            text = resp.content[0].text if resp.content else ""
            return self._parse_decision(text, agent, world)
        except Exception as e:
            self.stats.failures += 1
            print(f"[brain.S] {agent.agent_id} 실패: {e}")
            return self._mock_decide(agent, world, tier="S")

    # -----------------------------------------------------------
    # Tier S Gemini 경로 (페르소나 전체 컨텍스트)
    # -----------------------------------------------------------
    def _smart_decide_gemini(self, agent: "Agent", world: "World", ctx: str, persona: Persona) -> Decision:
        if self._gemini_s is None:
            return self._mock_decide(agent, world, tier="S")
        try:
            full_prompt = f"{persona.full_profile}\n\n{ctx}"
            resp = self._gemini_s.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": self.cfg.tier_s_max_tokens,
                    "response_mime_type": "application/json",
                },
            )
            text = resp.text or ""
            try:
                u = resp.usage_metadata
                self.stats.tier_s_input_tokens += u.prompt_token_count
                self.stats.tier_s_output_tokens += u.candidates_token_count
            except Exception:
                pass
            return self._parse_decision(text, agent, world)
        except Exception as e:
            self.stats.failures += 1
            print(f"[brain.S/gemini] {agent.agent_id} 실패: {e}")
            return self._mock_decide(agent, world, tier="S")

    # -----------------------------------------------------------
    # Tier S OpenAI 경로
    # -----------------------------------------------------------
    def _smart_decide_openai(self, agent: "Agent", world: "World", ctx: str, persona: Persona) -> Decision:
        if self._openai is None:
            return self._mock_decide(agent, world, tier="S")
        # 429 rate-limit 방어 — 0.5/1/2s backoff 로 3회 재시도.
        # ⚠️ ThreadPool worker 안에서 동기 sleep → 4 worker 동시 429 시 최대 7s pool 정지.
        # 정상 RPM 한도 (concurrency=4 + Semaphore=4 → ~320 RPM < 500) 면 거의 안 걸림.
        delay = 0.5
        for attempt in range(3):
            try:
                resp = self._openai.chat.completions.create(
                    model=self.cfg.tier_s_model,
                    max_tokens=self.cfg.tier_s_max_tokens,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": persona.full_profile},
                        {"role": "user", "content": ctx},
                    ],
                )
                usage = resp.usage
                self.stats.tier_s_input_tokens += getattr(usage, "prompt_tokens", 0) or 0
                self.stats.tier_s_output_tokens += getattr(usage, "completion_tokens", 0) or 0
                # OpenAI cached tokens
                cached = 0
                try:
                    cached = usage.prompt_tokens_details.cached_tokens or 0
                except Exception:
                    pass
                self.stats.tier_s_cache_read += cached
                text = resp.choices[0].message.content or ""
                return self._parse_decision(text, agent, world)
            except Exception as e:
                msg = str(e)
                is_rate_limit = "429" in msg or "rate_limit" in msg or "RateLimit" in type(e).__name__
                if is_rate_limit and attempt < 2:
                    time.sleep(delay)
                    delay *= 2  # 0.5 → 1 → 2s
                    continue
                self.stats.failures += 1
                print(f"[brain.S/openai] {agent.agent_id} 실패: {e}")
                return self._mock_decide(agent, world, tier="S")
        # 도달 불가 — for loop 의 모든 path 가 return. 정적 분석기 fallback 용.
        return self._mock_decide(agent, world, tier="S")

    # -----------------------------------------------------------
    # Tier A: Gemini Flash 또는 OpenAI nano
    # -----------------------------------------------------------
    def fast_decide(self, agent: "Agent", world: "World") -> Decision:
        self.stats.tier_a_calls += 1

        if self.cfg.mock_mode:
            return self._mock_decide(agent, world, tier="A")

        if self.cfg.tier_a_provider == "openai":
            return self._fast_decide_openai(agent, world)

        if self.cfg.tier_a_provider == "ollama":
            return self._fast_decide_ollama(agent, world)

        if self._gemini is None:
            return self._mock_decide(agent, world, tier="A")

        prompt = self._compact_prompt(agent, world)
        try:
            resp = self._gemini.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": self.cfg.tier_a_max_tokens,
                    "response_mime_type": "application/json",
                },
            )
            text = resp.text or ""
            # 토큰 카운트 (있으면)
            try:
                u = resp.usage_metadata
                self.stats.tier_a_input_tokens += u.prompt_token_count
                self.stats.tier_a_output_tokens += u.candidates_token_count
            except Exception:
                pass
            return self._parse_decision(text, agent, world)
        except Exception as e:
            self.stats.failures += 1
            print(f"[brain.A] {agent.agent_id} 실패: {e}")
            return self._mock_decide(agent, world, tier="A")

    # -----------------------------------------------------------
    # Tier S/A Ollama (Qwen) 경로 - OpenAI 호환 endpoint
    # -----------------------------------------------------------
    def _smart_decide_ollama(self, agent: "Agent", world: "World", ctx: str, persona: Persona) -> Decision:
        if self._ollama is None:
            return self._mock_decide(agent, world, tier="S")
        try:
            resp = self._ollama.chat.completions.create(
                model=self.cfg.tier_s_model,
                max_tokens=self.cfg.tier_s_max_tokens,
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": persona.full_profile},
                    {"role": "user", "content": ctx},
                ],
            )
            usage = resp.usage
            self.stats.tier_s_input_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.stats.tier_s_output_tokens += getattr(usage, "completion_tokens", 0) or 0
            text = resp.choices[0].message.content or ""
            return self._parse_decision(text, agent, world)
        except Exception as e:
            self.stats.failures += 1
            print(f"[brain.S/ollama] {agent.agent_id} 실패: {e}")
            return self._mock_decide(agent, world, tier="S")

    def _fast_decide_ollama(self, agent: "Agent", world: "World") -> Decision:
        if self._ollama is None:
            return self._mock_decide(agent, world, tier="A")
        prompt = self._compact_prompt(agent, world)
        try:
            resp = self._ollama.chat.completions.create(
                model=self.cfg.tier_a_model,
                max_tokens=self.cfg.tier_a_max_tokens,
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
            usage = resp.usage
            self.stats.tier_a_input_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.stats.tier_a_output_tokens += getattr(usage, "completion_tokens", 0) or 0
            text = resp.choices[0].message.content or ""
            return self._parse_decision(text, agent, world)
        except Exception as e:
            self.stats.failures += 1
            print(f"[brain.A/ollama] {agent.agent_id} 실패: {e}")
            return self._mock_decide(agent, world, tier="A")

    # -----------------------------------------------------------
    # Tier A OpenAI 경로
    # -----------------------------------------------------------
    def _fast_decide_openai(self, agent: "Agent", world: "World") -> Decision:
        if self._openai is None:
            return self._mock_decide(agent, world, tier="A")
        prompt = self._compact_prompt(agent, world)
        try:
            resp = self._openai.chat.completions.create(
                model=self.cfg.tier_a_model,
                max_tokens=self.cfg.tier_a_max_tokens,
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
            usage = resp.usage
            self.stats.tier_a_input_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.stats.tier_a_output_tokens += getattr(usage, "completion_tokens", 0) or 0
            text = resp.choices[0].message.content or ""
            return self._parse_decision(text, agent, world)
        except Exception as e:
            self.stats.failures += 1
            print(f"[brain.A/openai] {agent.agent_id} 실패: {e}")
            return self._mock_decide(agent, world, tier="A")

    # -----------------------------------------------------------
    # 컨텍스트 빌더 (동적 부분 - 캐시 X)
    # -----------------------------------------------------------
    def _dynamic_context(self, agent: "Agent", world: "World") -> str:
        """매 hour 유저 프롬프트 — caveman ultra (~25 tok, 이전 40 tok).

        토큰: prof_line 약어 (PS/CF), 시간 단위 'h', wkd→W/평, "JSON결정" 삭제 (system 에 명시).
        """
        nearby = [s.name for s in world.stores_in_dong(agent.current_dong)[:3]]
        memory_line = ""
        if self.memory_index is not None:
            try:
                query = f"{world.current_hour}시 {agent.current_dong}"
                hits = self.memory_index.search(agent.agent_id, query, k=2)
                if hits:
                    memory_line = f" 過:{' | '.join(h.text for h in hits)}"
            except Exception:
                pass
        prof_line = ""
        if agent.profile is not None:
            prof_line = f" [{agent.profile.lifestyle_tag} PS{agent.profile.price_sensitivity:.1f} CF{agent.profile.pref_cafe:.1f}]"
        wkd = "W" if world.is_weekend else "평"
        return (
            f"h{world.current_hour} {wkd} {world.weather}{world.temperature:.0f}도.{prof_line} "
            f"{agent.current_dong} 방문{len(agent.visited_today)} 지출{int(agent.spent_today):,}원. "
            f"근처:{','.join(nearby)}.{memory_line}"
        )

    def _compact_prompt(self, agent: "Agent", world: "World") -> str:
        """Tier A 압축 프롬프트 — caveman ultra (~50 tok, 이전 80 tok).

        축약: 시→h, 평일→평/W, 가성비→PS, 카페→CF, JSON 스키마 keys 단축.
        """
        tag = agent.profile.lifestyle_tag if agent.profile else agent.role.value
        extra = ""
        if agent.profile is not None:
            extra = f" PS{agent.profile.price_sensitivity:.1f} CF{agent.profile.pref_cafe:.1f}."
        wkd = "W" if world.is_weekend else "평"
        return (
            f"마포 {tag} {agent.age}{agent.current_dong} h{world.current_hour} {wkd}.{extra}"
            f" 잔여{int(agent.budget_today - agent.spent_today):,}원."
            f' JSON:{{"action":"visit|move|rest","category":"카페|음식점|편의점|주점|null","spend":원,"reason":"30자 fragment"}}'
        )

    # -----------------------------------------------------------
    # 결정 파서
    # -----------------------------------------------------------
    def _parse_decision(self, text: str, agent: "Agent", world: "World") -> Decision:
        try:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if not m:
                return self._mock_decide(agent, world, tier="P")
            data = json.loads(m.group())
            action = data.get("action", "rest")
            cat = data.get("category")
            spend = float(data.get("spend") or 0)
            reason = data.get("reason", "")[:100]
            target_dong = data.get("target_dong") or agent.current_dong
            store_id = None

            if action == "visit" and cat:
                stores = world.stores_in_dong(target_dong, cat)
                if stores:
                    store = max(stores, key=lambda s: s.rating)
                    store_id = store.store_id

            return Decision(
                action=action,
                target_dong=target_dong,
                target_store_id=store_id,
                spend=spend,
                reason=reason,
            )
        except Exception:
            return self._mock_decide(agent, world, tier="P")

    # -----------------------------------------------------------
    # Mock decide - API 없을 때 (Tier B 규칙과 동일하게 처리)
    # -----------------------------------------------------------
    def _mock_decide(self, agent: "Agent", world: "World", tier: str) -> Decision:
        from .agents import Agent as A

        # 위임 - Tier B 로직 재사용
        dec = A._rule_decide(agent, world, self._rng)
        if tier == "S":
            dec.reason = f"[mock-S] {agent.last_action}→{dec.action}"
        return dec

    # -----------------------------------------------------------
    # DSL 의사결정 (Tier 통합 — 출력은 V/M/R/W 단일 verb)
    # 프롬프트 길이만 Tier별로 다름 (S=풀, A=중, B=초압축)
    # -----------------------------------------------------------
    def dsl_decide(self, agent: "Agent", world: "World", tier_override: str | None = None) -> Decision:
        """DSL 모드 의사결정. Tier에 따라 프롬프트 길이 차등.

        출력 verb:
          V cafe|food|pub|cvs   - 카테고리 매장 방문
          M <dong>              - 다른 동으로 이동
          R                     - 휴식
          W                     - 점주 근무
        """

        tier = tier_override or agent.tier.value
        if tier == "S":
            self.stats.tier_s_calls += 1
        elif tier == "A":
            self.stats.tier_a_calls += 1
        # Tier B는 카운트하지 않음 (별도 통계 안 만듦)

        if self.cfg.mock_mode:
            return self._mock_decide(agent, world, tier=tier)

        prompt = self._build_dsl_prompt(agent, world, tier)
        text = self._call_dsl_llm(prompt, tier)
        if not text:
            return self._mock_decide(agent, world, tier=tier)
        return self._parse_dsl_decision(text, agent, world)

    def _build_dsl_prompt(self, agent: "Agent", world: "World", tier: str) -> str:
        """Tier별 DSL 프롬프트.

        S: 풀 페르소나 + 동적 컨텍스트 (~150 tok)
        A: 압축 태그 (~30 tok)
        B: 초압축 태그 (~15 tok)
        """
        h = world.current_hour
        wd = world.weekday
        budget_k = int((agent.budget_today - agent.spent_today) / 1000)
        weather_short = {"맑음": "맑", "비": "비", "눈": "눈", "약한비": "약비", "흐림": "흐"}.get(world.weather, "맑")

        if tier == "S":
            persona = self.personas.get(agent.agent_id)
            persona_block = persona.full_profile if persona else ""
            return (
                f"{persona_block}\n\n"
                f"지금 D{world.current_day} {h}시 ({'주말' if world.is_weekend else '평일'}{', 공휴일' if world.is_holiday else ''}), "
                f"{world.weather} {world.temperature:.0f}도, 현재 {agent.current_dong}, 예산잔여 {budget_k}k원.\n"
                f"행동을 단 한 줄 DSL로 출력하세요:\n"
                f"  V cafe | V food | V pub | V cvs   (현재 동에서 카테고리 매장 방문)\n"
                f"  M <동이름>                          (다른 동으로 이동)\n"
                f"  R                                   (휴식)\n"
                f"출력 예: V cafe"
            )

        if tier == "A":
            tag = agent.profile.lifestyle_tag if agent.profile else agent.role.value
            ps = agent.profile.price_sensitivity if agent.profile else 0.5
            cf = agent.profile.pref_cafe if agent.profile else 0.5
            return (
                f"마포 {tag} {agent.age}{agent.gender} {agent.current_dong} h{h} wd{wd} {weather_short} b{budget_k}k ps{ps:.1f} cf{cf:.1f}\n"
                f"DSL 1줄: V cafe|food|pub|cvs | M dong | R"
            )

        # Tier B (초압축)
        return (
            f"{agent.role.value[:3].upper()}{agent.age}{agent.gender} {agent.current_dong} h{h} {weather_short} b{budget_k}k\n"
            f"행동: V cafe|food|pub|cvs | M dong | R"
        )

    def _call_dsl_llm(self, prompt: str, tier: str) -> str:
        """DSL 응답용 LLM 호출 — max_tokens 작게."""
        cfg = self.cfg
        max_tok = 30 if tier == "S" else 12
        try:
            if cfg.tier_s_provider == "ollama" and self._ollama is not None:
                model = cfg.tier_s_model if tier == "S" else cfg.tier_a_model
                r = self._ollama.chat.completions.create(
                    model=model,
                    max_tokens=max_tok,
                    temperature=0.4,
                    messages=[{"role": "user", "content": prompt}],
                )
                u = r.usage
                if tier == "S":
                    self.stats.tier_s_input_tokens += getattr(u, "prompt_tokens", 0) or 0
                    self.stats.tier_s_output_tokens += getattr(u, "completion_tokens", 0) or 0
                else:
                    self.stats.tier_a_input_tokens += getattr(u, "prompt_tokens", 0) or 0
                    self.stats.tier_a_output_tokens += getattr(u, "completion_tokens", 0) or 0
                return r.choices[0].message.content or ""
            if cfg.tier_a_provider == "openai" and self._openai is not None:
                r = self._openai.chat.completions.create(
                    model=cfg.tier_a_model,
                    max_tokens=max_tok,
                    temperature=0.4,
                    messages=[{"role": "user", "content": prompt}],
                )
                u = r.usage
                if tier == "S":
                    self.stats.tier_s_input_tokens += getattr(u, "prompt_tokens", 0) or 0
                    self.stats.tier_s_output_tokens += getattr(u, "completion_tokens", 0) or 0
                else:
                    self.stats.tier_a_input_tokens += getattr(u, "prompt_tokens", 0) or 0
                    self.stats.tier_a_output_tokens += getattr(u, "completion_tokens", 0) or 0
                return r.choices[0].message.content or ""
        except Exception as e:
            self.stats.failures += 1
            print(f"[brain.dsl/{tier}] {e}")
        return ""

    def _parse_dsl_decision(self, text: str, agent: "Agent", world: "World") -> Decision:
        """DSL verb → Decision. V는 _pick_store에 위임."""
        import re as _re

        t = (text or "").strip()
        # 첫 라인 + 영문/한글만 추출
        first = t.split("\n")[0].strip()
        # ``` 등 마크다운 제거
        first = first.lstrip("`").rstrip("`").strip()
        m = _re.match(r"^([VMRW])\s*(.*)$", first.upper())
        if not m:
            return self._mock_decide(agent, world, tier="P")
        verb, rest = m.group(1), m.group(2).strip()

        if verb == "R":
            return Decision(action="rest", target_dong=agent.current_dong)
        if verb == "W":
            return Decision(action="work", target_dong=agent.home_dong)
        if verb == "V":
            cat_map = {"CAFE": "카페", "FOOD": "음식점", "PUB": "주점", "CVS": "편의점", "RESTAURANT": "음식점"}
            cat = cat_map.get(rest.split()[0].upper() if rest else "", None)
            if cat:
                return agent._pick_store(world, self._rng, cat)
            return Decision(action="rest", target_dong=agent.current_dong)
        if verb == "M":
            # M <dong>; 한글 그대로 첫 토큰
            target = first.split(maxsplit=1)[1].strip() if " " in first else None
            if target and any(target.startswith(d[:2]) for d in world.dongs):
                # 동 이름 정확 매칭 또는 prefix 매칭
                exact = next((d for d in world.dongs if d == target), None)
                if not exact:
                    exact = next((d for d in world.dongs if d.startswith(target[:2])), None)
                if exact and exact != agent.current_dong:
                    agent.current_dong = exact
                    return Decision(action="move", target_dong=exact)
            return Decision(action="rest", target_dong=agent.current_dong)

        return Decision(action="rest", target_dong=agent.current_dong)

    # -----------------------------------------------------------
    # Thought generator — Tier S 50명만 시각화용 한국어 내적 독백
    # 의사결정과 분리: trajectory 풍선/페르소나 카드 demo 용
    # -----------------------------------------------------------
    def generate_thought(
        self,
        agent: "Agent",
        world: "World",
    ) -> str:
        """Tier S agent 의 12자 이내 한국어 thought 1문장.

        Args:
            agent: Agent 인스턴스 (archetype, mood, hunger 참조).
            world: World 인스턴스 (current_hour, weather 참조).

        Returns:
            12자 이내 한국어 (마침표 없음). LLM 실패/키 부재 시
            dialog_templates 의 hardcoded 문장 fallback.

        비용:
            gpt-4.1-mini 기준 평균 326 input + 10 output token / call.
            Tier S 50명 × 24h = 1,200 call → cache 활성 시 ~$0.05/시뮬.

        설계:
            - 의사결정에 영향 X (Decision 반환 X) — Pearson r=0.95 보존
            - prompt cache 활용: 동일 system prompt 매 call 재사용
            - parallel batch 호출은 runner.py 가 asyncio.gather 로 처리
        """
        archetype = getattr(agent, "persona_id", "office_worker") or "office_worker"
        hour = world.current_hour % 24
        weather = getattr(world, "weather", "맑음")
        mood_label = "high" if agent.mood > 0.66 else "low" if agent.mood < 0.33 else "neutral"
        hunger = round(agent.hunger, 2)
        # dong 정보 — thought 텍스트가 실제 dot 위치와 일치해야 함 (mismatch fix)
        # 외부 시간엔 home_dong 으로 fallback (외부 dot 시각화는 ext skip 처리됨)
        current_dong = getattr(agent, "current_dong", None) or getattr(agent, "home_dong", None) or "마포"
        if current_dong == "외부":
            current_dong = getattr(agent, "home_dong", None) or "마포"

        # mock / 키 부재 → template fallback
        if self.cfg.mock_mode or self._openai is None:
            return self._thought_template_fallback(archetype, hour)

        try:
            resp = self._openai.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": _THOUGHT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"archetype={archetype}, hour={hour}, weather={weather}, "
                            f"mood={mood_label}, hunger={hunger}, dong={current_dong}"
                        ),
                    },
                ],
                max_tokens=30,
                temperature=1.2,
            )
            text = (resp.choices[0].message.content or "").strip()
            usage = resp.usage
            self.stats.thought_calls += 1
            if usage:
                self.stats.thought_input_tokens += usage.prompt_tokens
                self.stats.thought_output_tokens += usage.completion_tokens
                cached_obj = getattr(usage, "prompt_tokens_details", None)
                cached_n = getattr(cached_obj, "cached_tokens", 0) if cached_obj else 0
                self.stats.thought_cache_read += cached_n
            return text or self._thought_template_fallback(archetype, hour)
        except Exception:
            self.stats.failures += 1
            return self._thought_template_fallback(archetype, hour)

    def _thought_template_fallback(self, archetype: str, hour: int) -> str:
        """LLM 실패 시 dialog_templates 의 hardcoded 문장 fallback ($0)."""
        from .dialog_templates import TEMPLATES, pick_dialog

        # Unknown archetype → office_worker default ("..." 회피)
        arch = archetype if archetype in TEMPLATES else "office_worker"

        if 12 <= hour <= 13:
            situation = "lunch_decide"
        elif 18 <= hour <= 20:
            situation = "evening_decide"
        elif 21 <= hour <= 23:
            situation = "rest"
        else:
            situation = "morning_visit_cafe"
        return pick_dialog(arch, situation, hour, self._rng)


# ---------------------------------------------------------------------------
# Thought system prompt — caveman 압축 (~700 tok → ~280 tok, -60%).
# 첫 cache write 비용 절감, dialog_templates.py 8 archetype 어휘 표 유지.
# 출처: github.com/JuliusBrussee/caveman SKILL.md (drop articles, fragments OK).
# ---------------------------------------------------------------------------
_THOUGHT_SYSTEM_PROMPT = """마포 ABM 내적독백. 12자 한국어 1문장, 마침표/따옴표 X.

archetype 어휘 (1개 이상 필수):
creative_freelancer: 라떼/감성/카페/와이파이/작업/디저트/플레이리스트
office_worker: 회의/카페인/점심/회식/메일/김밥/가성비/팀
broadcasting_staff: 야식/편의점/촬영/대본/스튜디오/24시/컵라면
student_couple: 데이트/신상/SNS/인스타/홍대/카페투어
retired_local: 단골/시장/된장/국밥/막걸리/벤치/산책
young_parent: 키즈/아이/주차/배달/주말/유모차
tourist_foreign: 한식/포토스팟/시장/명물/구경
f&b_owner: 매출/경쟁/직원/원가/세무/벤치마킹

규칙:
- weather/mood/hunger 반영: 비→실내, mood low→짧게, hunger0.7+→음식 명시
- dong=현재위치 일치. 그 동 표현 우선 ("공덕 김밥"). 다른 동은 이동어 ("연남 가볼까")
- 금지: dong 모순 (dong=공덕인데 "홍대 카페투어" X)
- 어미 다양화 (할까/먹자/가야지/들를까/시키자). "땡기네/생각나네" 반복 X
- 명사 구체화 (커피→라떼/콜드브루). "따뜻한 ~ 한잔" 안전답 X

예시:
creative+비14h+dong=합정: "합정 카페 작업하자"
office+12h+dong=공덕: "공덕 김밥 먹자"
retired+19h+dong=대흥: "단골 국밥집 가야지"
student_couple+14h+dong=공덕: "연남까지 가볼까"
f&b_owner+9h+dong=상암: "원가 점검 먼저\""""
