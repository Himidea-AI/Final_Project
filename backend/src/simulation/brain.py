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
from .config import ModelConfig, log_llm_call
from .personas import Persona

# LangSmith 토큰/비용 추적 — LANGCHAIN_TRACING_V2=true 일 때만 동작.
# langsmith 미설치 / 환경변수 OFF 면 no-op 데코레이터로 graceful degrade.
#
# ABM trace 그룹화 전략: runner.run_simulation 에 부모 @traceable(run_type="chain")
# 를 부착하여 ABM 1회 = root trace 1개로 묶고, brain.* / policy_gen.* 호출은 그
# 부모 run 의 child 로 nested 된다. → LangSmith UI 메인 화면은 abm.simulation_run
# 1줄로만 보이고, expand 시 200+ LLM 호출이 펼쳐짐. LangGraph 에이전트(synthesis 등)
# trace 는 별도 root 로 그대로 남아 묻히지 않는다.
#
# 옵션: ABM_LANGCHAIN_PROJECT 환경변수로 별도 프로젝트 분리도 가능 (기본 None=같은 프로젝트).
ABM_LS_PROJECT = os.getenv("ABM_LANGCHAIN_PROJECT") or None


def _slim_inputs(inputs: dict) -> dict:
    """LangSmith @traceable input filter — World/Agent 통째 직렬화 회피.

    cProfile 측정 시 langsmith repr/json.dumps 가 16x 슬로우다운 (5000 agents
    + 3592 stores 객체를 매 호출마다 직렬화). 핵심 식별자만 노출:
      - agent: agent_id / role / tier
      - world: hour / weekday / weather (식별 가능 minimal)
      - 그 외 dict / list / primitive 는 그대로 전달
    """
    slim: dict = {}
    for k, v in inputs.items():
        if k == "self":
            continue
        cls_name = type(v).__name__
        if cls_name == "World":
            slim[k] = {
                "hour": getattr(v, "current_hour", None),
                "weekday": getattr(v, "weekday", None),
                "weather": getattr(v, "weather", None),
                "is_weekend": getattr(v, "is_weekend", None),
            }
        elif cls_name == "Agent":
            slim[k] = {
                "agent_id": getattr(v, "agent_id", None),
                "role": str(getattr(v, "role", "")),
                "tier": str(getattr(v, "tier", "")),
                "current_dong": getattr(v, "current_dong", None),
            }
        elif isinstance(v, list) and v and type(v[0]).__name__ == "Agent":
            # batch — agent_id 만 노출, agent 객체 직렬화 회피
            slim[k] = {
                "n_agents": len(v),
                "agent_ids": [getattr(a, "agent_id", None) for a in v[:10]],
            }
        else:
            slim[k] = v
    return slim


try:
    from langsmith import traceable as _ls_traceable

    def traceable(*dargs, **dkwargs):
        # 환경변수로 별도 프로젝트 명시한 경우에만 라우팅
        if ABM_LS_PROJECT and "project_name" not in dkwargs:
            dkwargs["project_name"] = ABM_LS_PROJECT
        # 기본 input slim — 호출자가 별도 process_inputs 전달 시 그대로 사용.
        if "process_inputs" not in dkwargs:
            dkwargs["process_inputs"] = _slim_inputs
        return _ls_traceable(*dargs, **dkwargs)
except Exception:

    def traceable(*dargs, **dkwargs):
        def _decorator(fn):
            return fn

        if dargs and callable(dargs[0]):
            return dargs[0]
        return _decorator


# Nemotron 26-col persona → 짧은 prompt brief.
# spawn_agents 가 a.persona_text / a.occupation / a.hobbies / a.professional_persona_text /
# a.cultural_background / a.career_goals_text 를 inject 함. 이전엔 LLM prompt 에서 사용 안 됐음.
# 토큰 절감 위해 직업 + persona 1-2 줄 요약 + 취미 3개 만 추출.
def _nemotron_brief(agent) -> str:
    """Nemotron 페르소나 → ' | <occ> · <persona 80자> · 취미: a/b/c' 형식."""
    parts: list[str] = []
    occ = getattr(agent, "occupation", "") or ""
    if occ and occ != "알 수 없음":
        parts.append(occ)
    pt = getattr(agent, "persona_text", "") or ""
    if pt:
        # 첫 80자 (한국어 약 40자) — 토큰 폭발 방지
        snippet = pt.replace("\n", " ").strip()[:80]
        if snippet:
            parts.append(snippet)
    hobbies = getattr(agent, "hobbies", None) or []
    if hobbies:
        # list[str] 또는 str 모두 지원
        if isinstance(hobbies, list):
            top = ", ".join(str(h) for h in hobbies[:3])
        else:
            top = str(hobbies)[:30]
        if top:
            parts.append(f"취미:{top}")
    if not parts:
        return ""
    return " | " + " · ".join(parts)


# Gemini 등 wrap_*가 미지원인 SDK는 함수 안에서 직접 토큰 정보를 현재 run에 첨부.
# LangSmith UI는 usage_metadata 의 input_tokens / output_tokens / total_tokens 키를 인식해
# 토큰·비용 칼럼에 표시한다. (Anthropic SDK schema 와 동일)
def _ls_attach_usage(input_tokens: int = 0, output_tokens: int = 0, model: str | None = None) -> None:
    try:
        from langsmith.run_helpers import get_current_run_tree

        rt = get_current_run_tree()
        if rt is None:
            return
        rt.add_metadata(
            {
                "usage_metadata": {
                    "input_tokens": int(input_tokens),
                    "output_tokens": int(output_tokens),
                    "total_tokens": int(input_tokens) + int(output_tokens),
                },
                **({"ls_model_name": model} if model else {}),
            }
        )
    except Exception:
        pass


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
        # 사용자 시나리오 (신규 매장 등) — runner.py 가 sim 시작 시 주입.
        # plan/decide/thought prompt 에 시나리오 컨텍스트 반영해 입력별 결과 분기.
        self.scenario_context: dict | None = None

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
        # LangSmith wrapper — 자동 토큰/비용 추적용. 없으면 identity passthrough.
        try:
            from langsmith.wrappers import wrap_openai as _wrap_openai
        except Exception:

            def _wrap_openai(c):
                return c

        try:
            from langsmith.wrappers import wrap_anthropic as _wrap_anthropic
        except Exception:

            def _wrap_anthropic(c):
                return c

        # OpenAI (Tier S 또는 A에서 사용 가능)
        if "openai" in (self.cfg.tier_s_provider, self.cfg.tier_a_provider):
            try:
                from openai import OpenAI

                self._openai = _wrap_openai(OpenAI(api_key=os.getenv("OPENAI_API_KEY")))
            except Exception as e:
                print(f"[brain] OpenAI 초기화 실패: {e}")
                self.cfg.mock_mode = True
                return

        # Ollama (OpenAI 호환 API → 같은 SDK 재사용)
        if "ollama" in (self.cfg.tier_s_provider, self.cfg.tier_a_provider):
            try:
                from openai import OpenAI

                self._ollama = _wrap_openai(
                    OpenAI(
                        base_url=self.cfg.ollama_base_url,
                        api_key="ollama",  # 더미 (Ollama 검사 안 함)
                    )
                )
            except Exception as e:
                print(f"[brain] Ollama 클라이언트 초기화 실패: {e}")
                self.cfg.mock_mode = True
                return

        if self.cfg.tier_s_provider == "anthropic":
            try:
                import anthropic

                self._anth = _wrap_anthropic(anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")))
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
    @traceable(run_type="chain", name="brain.tier_s.smart_decide")
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
    @traceable(run_type="llm", name="brain.tier_s.gemini")
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
                _ls_attach_usage(
                    input_tokens=u.prompt_token_count,
                    output_tokens=u.candidates_token_count,
                    model=self.cfg.tier_s_model,
                )
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
    @traceable(run_type="llm", name="brain.tier_s.openai")
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
    # Tier S 배치 의사결정 — N agents 한 prompt 에 묶어 1 호출.
    # 호출 수 ~10x 감소 + LangSmith trace 정리.
    # OpenAI provider 만 우선 지원, 그 외에는 single-call 자동 fallback.
    # -----------------------------------------------------------
    BATCH_SIZE_TIER_S = 10

    def batch_smart_decide(self, agents: list["Agent"], world: "World") -> list[tuple[int, "Decision"]]:
        """Tier S 다수 agent 를 BATCH_SIZE 청크로 묶어 LLM 호출.

        반환: [(agent_id, Decision), ...] — 입력 순서 보존 보장 X
        실패 시: 각 agent single-call fallback.
        """
        if not agents:
            return []

        # mock 또는 OpenAI 외 provider → 기존 single-call 경로 사용
        if self.cfg.mock_mode or self._openai is None or self.cfg.tier_s_provider != "openai":
            return [(a.agent_id, self.smart_decide(a, world)) for a in agents]

        results: list[tuple[int, "Decision"]] = []
        for i in range(0, len(agents), self.BATCH_SIZE_TIER_S):
            chunk = agents[i : i + self.BATCH_SIZE_TIER_S]
            results.extend(self._batch_smart_decide_openai(chunk, world))
        return results

    @traceable(run_type="llm", name="brain.tier_s.batch.openai")
    def _batch_smart_decide_openai(self, agents: list["Agent"], world: "World") -> list[tuple[int, "Decision"]]:
        # agent별 user block — 페르소나 첫 줄 (lifestyle) + Nemotron 26-col + dynamic ctx
        user_blocks: list[str] = []
        for a in agents:
            persona = self.personas.get(a.agent_id)
            ctx = self._dynamic_context(a, world)
            # full_profile 첫 1~2 줄만 (batch 토큰 폭발 방지). 약 ~120 자 cap
            persona_brief = ""
            if persona is not None:
                first = persona.full_profile.split("\n", 1)[0]
                persona_brief = first[:200]
            nemo = _nemotron_brief(a)
            user_blocks.append(f"#{a.agent_id} | {persona_brief}{nemo}\n{ctx}")

        user_prompt = (
            "\n\n".join(user_blocks) + "\n\n각 agent 결정을 JSON 객체 {decisions:[...]} 로 반환. "
            'item: {"agent_id":int,"action":"visit|move|rest","category":"카페|음식점|편의점|주점|null",'
            '"target_dong":str,"spend":int,"reason":"30자 fragment"}. '
            "agent 마다 다른 카테고리/이유 — 다양성 우선, 같은 패턴 반복 금지."
        )
        system_prompt = (
            "마포구 ABM 시뮬레이터. 다음 N명의 페르소나·컨텍스트를 보고 "
            "각 agent 의 한 시점 결정을 한 번에 JSON 으로 반환하라."
        )

        # stat 누적은 호출당 N 만큼
        self.stats.tier_s_calls += len(agents)

        # max_tokens — agent 1명당 ~80 tok 응답 가정 (cfg.tier_s_max_tokens 그대로 사용)
        per_agent = max(80, self.cfg.tier_s_max_tokens)
        max_out = min(8192, per_agent * len(agents) + 200)

        delay = 0.5
        for attempt in range(3):
            try:
                resp = self._openai.chat.completions.create(
                    model=self.cfg.tier_s_model,
                    max_tokens=max_out,
                    temperature=0.5,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                usage = resp.usage
                self.stats.tier_s_input_tokens += getattr(usage, "prompt_tokens", 0) or 0
                self.stats.tier_s_output_tokens += getattr(usage, "completion_tokens", 0) or 0
                cached = 0
                try:
                    cached = usage.prompt_tokens_details.cached_tokens or 0
                except Exception:
                    pass
                self.stats.tier_s_cache_read += cached
                text = resp.choices[0].message.content or ""
                return self._parse_batch_decisions(text, agents, world)
            except Exception as e:
                msg = str(e)
                is_rate_limit = "429" in msg or "rate_limit" in msg or "RateLimit" in type(e).__name__
                if is_rate_limit and attempt < 2:
                    time.sleep(delay)
                    delay *= 2
                    continue
                self.stats.failures += 1
                print(f"[brain.S/batch] 실패: {e} — single-call fallback")
                return [(a.agent_id, self._mock_decide(a, world, tier="S")) for a in agents]
        return [(a.agent_id, self._mock_decide(a, world, tier="S")) for a in agents]

    def _parse_batch_decisions(self, text: str, agents: list["Agent"], world: "World") -> list[tuple[int, "Decision"]]:
        """JSON 응답 → (agent_id, Decision) 목록.

        파싱 실패한 agent 는 _mock_decide 로 fallback (single-call 재호출 X — 무한 루프 회피).
        """
        items: list = []
        try:
            data = json.loads(text)
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # 기대 key 우선순위: decisions / agents / 첫 list 값
                for k in ("decisions", "agents", "results"):
                    v = data.get(k)
                    if isinstance(v, list):
                        items = v
                        break
                else:
                    for v in data.values():
                        if isinstance(v, list):
                            items = v
                            break
        except Exception as e:
            print(f"[brain.S/batch] JSON parse 실패: {e}")

        by_id: dict[int, dict] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            aid = item.get("agent_id")
            try:
                by_id[int(aid)] = item
            except (TypeError, ValueError):
                continue

        results: list[tuple[int, "Decision"]] = []
        for a in agents:
            item = by_id.get(a.agent_id)
            if item is None:
                results.append((a.agent_id, self._mock_decide(a, world, tier="S")))
                continue
            try:
                text_one = json.dumps(item, ensure_ascii=False)
                dec = self._parse_decision(text_one, a, world)
            except Exception as e:
                # silent fallback 이전 → 어느 agent 가 실패했는지 추적 가능 (review #5).
                print(f"[brain.S/batch] agent {a.agent_id} parse 실패: {e}")
                dec = self._mock_decide(a, world, tier="S")
            results.append((a.agent_id, dec))
        return results

    # -----------------------------------------------------------
    # Hierarchical Planning (Stanford Generative Agents UIST'23 적용)
    # 시뮬 시작 시 Tier S agent 의 하루 일정을 batch 로 1회 생성.
    # plan 이 있는 hour 는 LLM 호출 없이 슬롯 → Decision 변환.
    # 효과: LLM 호출 추가 절감 + 일관성 ↑ (점심 한 번만 등 paper 핵심)
    # -----------------------------------------------------------
    BATCH_SIZE_PLAN = 10

    def generate_daily_plans_batch(self, agents: list["Agent"], world: "World") -> dict[int, list[dict]]:
        """Tier S agents 에게 하루 일정 생성 (batch). 반환: agent_id → schedule.

        chunk 5개 (50 agents) 를 asyncio.gather 로 병렬 실행.
        sequential 4 × 26s = 106s/sim → parallel ~26s/sim.
        thought batch 와 동일 패턴.
        """
        if not agents:
            return {}
        if self.cfg.mock_mode or self._openai is None or self.cfg.tier_s_provider != "openai":
            return {}

        import asyncio as _aio

        chunks = [agents[i : i + self.BATCH_SIZE_PLAN] for i in range(0, len(agents), self.BATCH_SIZE_PLAN)]

        async def _run_all() -> dict[int, list[dict]]:
            # OpenAI Tier 1 RPM=500 보호. thought 5 + plan 5 동시 → 8 cap 충분.
            sem = _aio.Semaphore(8)

            async def _bounded(chunk):
                async with sem:
                    try:
                        return await _aio.to_thread(self._generate_daily_plans_openai, chunk, world)
                    except Exception as e:
                        # chunk 1개 실패 → 시뮬 abort 방지. 빈 dict.
                        print(f"[brain.S/plan] chunk 실패 ({len(chunk)} agents): {e}")
                        return {}

            results = await _aio.gather(*[_bounded(c) for c in chunks])
            merged: dict[int, list[dict]] = {}
            for r in results:
                merged.update(r)
            return merged

        try:
            return _aio.run(_run_all())
        except RuntimeError as e:
            msg = str(e)
            if "running event loop" not in msg and "no current event loop" not in msg:
                raise
            loop = _aio.new_event_loop()
            try:
                return loop.run_until_complete(_run_all())
            finally:
                loop.close()

    @traceable(run_type="llm", name="brain.tier_s.plan.openai")
    def _generate_daily_plans_openai(self, agents: list["Agent"], world: "World") -> dict[int, list[dict]]:
        user_blocks: list[str] = []
        for a in agents:
            persona = self.personas.get(a.agent_id)
            persona_brief = ""
            if persona is not None:
                first = persona.full_profile.split("\n", 1)[0]
                persona_brief = first[:200]
            nemo = _nemotron_brief(a)
            # ext_commuter/ext_visitor 는 마포 체류 시간만 표기 (외부 시간 슬롯은 policy 가 무시).
            window = ""
            arr = getattr(a, "arrival_hour", None)
            dep = getattr(a, "departure_hour", None)
            if a.role.value in ("ext_commuter", "ext_visitor") and arr is not None and dep is not None:
                window = f", 마포체류={arr:02d}-{dep:02d}h, work={getattr(a, 'work_dong', None) or '?'}"
            user_blocks.append(
                f"#{a.agent_id} | home={a.home_dong}, age={a.age}, role={a.role.value}{window} | {persona_brief}{nemo}"
            )

        wkd_label = "주말" if getattr(world, "is_weekend", False) else "평일"
        weather = getattr(world, "weather", "맑음")

        # 시나리오 신규 매장 컨텍스트 — 사용자 입력 (district/category/brand) 가
        # 매 실행마다 다르므로 prompt 에 명시해야 plan 결과 분기. 미주입 시 일반 plan.
        # 주의: 너무 강한 prompt → 모든 agent 가 신규 매장 방문하는 비현실 결과.
        # "20-30%만 호기심 방문 / 나머지는 평소 routine" 으로 분포 강제.
        scenario_block = ""
        sc = getattr(self, "scenario_context", None)
        if sc:
            ns_brand = sc.get("brand") or "신규 매장"
            ns_dong = sc.get("district") or sc.get("dong") or "?"
            ns_cat = sc.get("category") or "음식점"
            ns_target = sc.get("main_target_age") or ""
            ns_peak = sc.get("peak_time") or ""
            ns_boost = sc.get("popularity_boost") or 1.0
            scenario_block = (
                f"\n\n[오늘 신규 오픈] {ns_dong} '{ns_brand}' ({ns_cat}). popularity_boost={ns_boost}."
                + (f" 주 타겟: {ns_target}." if ns_target else "")
                + (f" 피크: {ns_peak}." if ns_peak else "")
                + " 방문 분포 룰:"
                + " (1) 10명 중 2-3명만 호기심에 1회 visit 슬롯 추가 — 페르소나가 주 타겟과 일치하거나 home_dong 가 인접한 경우만."
                + " (2) 나머지 7-8명은 신규 매장 무시. 평소 일과 (재택/식사/휴식) 그대로."
                + " (3) 신규 매장 방문은 1회만. 동일 매장 두 번 연속 슬롯 금지 (예: 12-13 visit + 14-17 visit 같은 곳 X)."
                + " (4) 노년층/육아층 등 페르소나 안 맞는 agent 는 호기심 방문 X."
            )

        user_prompt = (
            "\n".join(user_blocks)
            + f"\n\n오늘={wkd_label}, 날씨={weather}."
            + scenario_block
            + "\n각 agent 의 하루 일정을 6시~26시 (=익일 02시) 시간 슬롯으로 생성. "
            + 'JSON {"plans":[{"agent_id":int,"schedule":[{"start":int,"end":int,"action":str,'
            + '"dong":str,"category":str|null,"reason":"30자 fragment","hourly":["12자 한국어",...]}]}]}.\n'
            + "action: work|visit|rest|move 중 하나.\n"
            + "category (visit 슬롯만): 카페|음식점|편의점|주점.\n"
            + 'hourly: slot 의 (end-start) 길이만큼 12자 한국어 내적독백 array. 시간 흐름 (도착→몰입→마무리) 자연스럽게. 마침표/따옴표 X. 예: ["카페 도착","수다 한참","마저 대화"].\n'
            + "agent 페르소나·home_dong 반영. 점심·저녁·휴식 자연스럽게 분배. "
            + "슬롯 6~8개. visit 슬롯 0~2개 (대부분 0~1). reason 20자 이내. dong 짧게. "
            + "시간 겹치지 않게 연속 배치. 같은 카테고리 2회 이상 금지. 같은 매장 연속 슬롯 절대 금지. "
            + "ext_commuter (외부→마포 출근): 마포체류 범위 안에서만 슬롯. work_dong 위주. "
            + "출근 직후 (도착~+1h) 카페 visit 1슬롯 강제 권장 (출근길 커피). 점심 (12-13) visit 1슬롯 권장. "
            + "ext_visitor (외부→마포 저녁 방문): 마포체류 안에서 visit 슬롯 1-2개 (저녁 식사·주점·카페). "
            + "ext_*는 외부 시간 슬롯 만들지 않음 (마포체류 밖은 자동 외부 처리)."
        )
        system_prompt = (
            "마포구 ABM 시뮬레이터. N명 페르소나의 하루 일정을 시간 슬롯으로 한 번에 생성. "
            "Stanford Generative Agents 의 hierarchical planning 패턴: 일관된 활동 흐름을 보장해 "
            "에이전트가 점심을 두 번 먹는 등의 비현실적 행동을 차단."
        )

        # plan 호출도 stat 카운트 — 토큰 추적용
        self.stats.tier_s_calls += len(agents)
        # 1 agent 당 8 슬롯 × ~80 tok + hourly array (~120 tok) = 880 tok 응답. JSON wrapper + 여유 600 tok.
        # 이전 4200 cap → "Unterminated string" 절단 발생. 16000 으로 안전마진.
        max_out = min(16000, 1000 * len(agents) + 600)

        try:
            resp = self._openai.chat.completions.create(
                model=self.cfg.tier_s_model,
                max_tokens=max_out,
                temperature=0.7,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            usage = resp.usage
            self.stats.tier_s_input_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.stats.tier_s_output_tokens += getattr(usage, "completion_tokens", 0) or 0
            log_llm_call("brain.S.plan.batch", self.cfg.tier_s_model, usage, n_agents=len(agents))
            text = resp.choices[0].message.content or ""
            return self._parse_daily_plans(text, agents)
        except Exception as e:
            print(f"[brain.S/plan] 실패: {e}")
            self.stats.failures += 1
            return {}

    def _parse_daily_plans(self, text: str, agents: list["Agent"]) -> dict[int, list[dict]]:
        """plan JSON → agent_id → 슬롯 list. 잘못된 슬롯은 skip.

        truncation 복구: max_tokens cap 도달 시 응답 끝이 `"reason":"...`
        형태로 잘림 → 마지막 완성된 `]}` (= schedule 닫힘) 직후로 자르고 wrapper 재구성.
        """
        items: list = []

        def _try_parse(t: str):
            data = json.loads(t)
            if isinstance(data, dict):
                for k in ("plans", "agents", "schedules"):
                    v = data.get(k)
                    if isinstance(v, list):
                        return v
                for v in data.values():
                    if isinstance(v, list):
                        return v
            elif isinstance(data, list):
                return data
            return []

        try:
            items = _try_parse(text)
        except Exception as e:
            # 1차 실패 - truncation 복구 시도 (max_tokens cap 도달 시)
            last_close = text.rfind("]}")
            if last_close > 0:
                # 마지막 완성된 schedule 까지 + wrapper 강제 닫기
                repaired = text[: last_close + 2] + "]}"
                try:
                    items = _try_parse(repaired)
                except Exception as e2:
                    print(f"[brain.S/plan] JSON parse 실패 (recovery 시도 후): {e2}")
                    return {}
                print(f"[brain.S/plan] truncation recovery OK at char {last_close}")
            else:
                print(f"[brain.S/plan] JSON parse 실패: {e}")
                return {}

        valid_actions = {"visit", "move", "rest", "work"}
        valid_cats = {"카페", "음식점", "편의점", "주점", None}
        out: dict[int, list[dict]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                aid = int(item.get("agent_id"))
            except (TypeError, ValueError):
                continue
            schedule = item.get("schedule") or item.get("slots") or []
            if not isinstance(schedule, list):
                continue
            valid_slots: list[dict] = []
            for slot in schedule:
                if not isinstance(slot, dict):
                    continue
                try:
                    start = int(slot.get("start", -1))
                    end = int(slot.get("end", -1))
                except (TypeError, ValueError):
                    continue
                # prompt 가 6시~26시 명시 → start<6 또는 end>26 슬롯은 폐기.
                # 이전 start<0 / end>30 만 차단 → 시뮬 hour 범위 (보통 6~22) 밖
                # 슬롯이 silent miss 됨 (review #8 fix).
                if start < 6 or end <= start or end > 26:
                    continue
                action = slot.get("action", "rest")
                if action not in valid_actions:
                    action = "rest"
                cat = slot.get("category")
                if cat == "":
                    cat = None
                if cat not in valid_cats:
                    cat = None
                hourly_raw = slot.get("hourly")
                hourly: list[str] = []
                if isinstance(hourly_raw, list):
                    for h in hourly_raw:
                        if isinstance(h, str) and h.strip():
                            hourly.append(h.strip()[:30])
                valid_slots.append(
                    {
                        "start": start,
                        "end": end,
                        "action": action,
                        "dong": (slot.get("dong") or "").strip(),
                        "category": cat,
                        "reason": (slot.get("reason") or "")[:60],
                        "hourly": hourly,
                    }
                )
            if valid_slots:
                # 시간 정렬
                valid_slots.sort(key=lambda s: s["start"])
                out[aid] = valid_slots
        return out

    # -----------------------------------------------------------
    # Thought batch — N agents 1 LLM call (10x 호출 절감)
    # 기존: 50 agents × 16h = 800 단발 호출
    # 신: 50/10 = 5 batch × 16h = 80 호출
    # -----------------------------------------------------------
    BATCH_SIZE_THOUGHT = 10

    def generate_thoughts_batch(self, agents: list["Agent"], world: "World") -> dict[int, str]:
        """N agents thought 를 batch (10/call) 동시 호출. agent_id → 12자 문장.

        chunk 5개 (50 agents) 를 asyncio.gather 로 병렬 실행.
        sequential 5 × 1.5s = 7.5s/hour → parallel ~1.5s/hour.
        16h sim 기준 150s → 30s 절감.
        """
        if not agents:
            return {}
        if self.cfg.mock_mode or self._openai is None:
            hour = getattr(world, "current_hour", 0) % 24
            return {
                a.agent_id: self._thought_template_fallback(
                    getattr(a, "persona_id", "office_worker") or "office_worker", hour
                )
                for a in agents
            }

        import asyncio as _aio

        chunks = [agents[i : i + self.BATCH_SIZE_THOUGHT] for i in range(0, len(agents), self.BATCH_SIZE_THOUGHT)]

        hour_for_fb = getattr(world, "current_hour", 0) % 24

        def _chunk_fallback(chunk: list["Agent"]) -> dict[int, str]:
            return {
                a.agent_id: self._thought_template_fallback(
                    getattr(a, "persona_id", "office_worker") or "office_worker", hour_for_fb
                )
                for a in chunk
            }

        async def _run_all() -> dict[int, str]:
            # OpenAI Tier 1 RPM=500 보호. 5 chunk + decision/plan 동시 사용 고려해 8 cap.
            sem = _aio.Semaphore(8)

            async def _bounded(chunk):
                async with sem:
                    try:
                        return await _aio.to_thread(self._generate_thoughts_openai, chunk, world)
                    except Exception as e:
                        # chunk 1개 실패 → 시뮬 abort 방지. template fallback.
                        print(f"[brain.thought.batch] chunk 실패 ({len(chunk)} agents): {e}")
                        return _chunk_fallback(chunk)

            # return_exceptions=False 이지만 _bounded 가 모든 예외를 swallow → 안전.
            results = await _aio.gather(*[_bounded(c) for c in chunks])
            merged: dict[int, str] = {}
            for r in results:
                merged.update(r)
            return merged

        try:
            return _aio.run(_run_all())
        except RuntimeError as e:
            # FastAPI/Jupyter event loop 안에서 호출된 케이스만 좁혀 처리.
            msg = str(e)
            if "running event loop" not in msg and "no current event loop" not in msg:
                raise
            loop = _aio.new_event_loop()
            try:
                return loop.run_until_complete(_run_all())
            finally:
                loop.close()

    @traceable(run_type="llm", name="brain.thought.batch.openai")
    def _generate_thoughts_openai(self, agents: list["Agent"], world: "World") -> dict[int, str]:
        hour = getattr(world, "current_hour", 0) % 24
        weather = getattr(world, "weather", "맑음")

        user_blocks: list[str] = []
        for a in agents:
            archetype = getattr(a, "persona_id", "office_worker") or "office_worker"
            mood_label = "high" if a.mood > 0.66 else "low" if a.mood < 0.33 else "neutral"
            hunger = round(a.hunger, 2)
            current_dong = getattr(a, "current_dong", None) or getattr(a, "home_dong", None) or "마포"
            if current_dong == "외부":
                current_dong = getattr(a, "home_dong", None) or "마포"
            user_blocks.append(
                f"#{a.agent_id} archetype={archetype} hour={hour} weather={weather} "
                f"mood={mood_label} hunger={hunger} dong={current_dong}{_nemotron_brief(a)}"
            )

        user_prompt = (
            "\n".join(user_blocks)
            + '\n\n각 #id 마다 12자 한국어 1문장. JSON {"thoughts":[{"agent_id":int,"thought":str}]}.'
        )

        # 1 thought ≈ 30 tok 응답. 헤드 + JSON overhead 200 tok 여유.
        max_out = min(8000, 30 * len(agents) + 200)

        try:
            resp = self._openai.chat.completions.create(
                model="gpt-5.4-nano",
                messages=[
                    {"role": "system", "content": _THOUGHT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_out,
                temperature=1.2,
                response_format={"type": "json_object"},
            )
            text = resp.choices[0].message.content or ""
            usage = resp.usage
            # N 단발 등가 — stat 비교 시 1 batch ≠ N call 헷갈림 방지 위해 N 으로 카운트
            self.stats.thought_calls += len(agents)
            if usage:
                self.stats.thought_input_tokens += usage.prompt_tokens
                self.stats.thought_output_tokens += usage.completion_tokens
                cached_obj = getattr(usage, "prompt_tokens_details", None)
                cached_n = getattr(cached_obj, "cached_tokens", 0) if cached_obj else 0
                self.stats.thought_cache_read += cached_n
                log_llm_call("brain.S.thought.batch", self.cfg.tier_s_model, usage, n_agents=len(agents))
            return self._parse_thoughts(text, agents, hour)
        except Exception as e:
            print(f"[brain.thought.batch] 실패: {e}")
            self.stats.failures += 1
            return {
                a.agent_id: self._thought_template_fallback(
                    getattr(a, "persona_id", "office_worker") or "office_worker", hour
                )
                for a in agents
            }

    def _parse_thoughts(self, text: str, agents: list["Agent"], hour: int) -> dict[int, str]:
        """thought batch JSON → agent_id → 문장. 누락/파싱실패는 template fallback."""
        out: dict[int, str] = {}
        items: list = []
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                for k in ("thoughts", "results", "items"):
                    v = data.get(k)
                    if isinstance(v, list):
                        items = v
                        break
                else:
                    for v in data.values():
                        if isinstance(v, list):
                            items = v
                            break
            elif isinstance(data, list):
                items = data
        except Exception as e:
            print(f"[brain.thought.batch] JSON parse 실패: {e}")

        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                aid = int(item.get("agent_id"))
            except (TypeError, ValueError):
                continue
            thought = (item.get("thought") or "").strip()
            if thought:
                out[aid] = thought[:60]

        # 누락 agent → template fallback
        for a in agents:
            if a.agent_id not in out:
                arch = getattr(a, "persona_id", "office_worker") or "office_worker"
                out[a.agent_id] = self._thought_template_fallback(arch, hour)
        return out

    def decision_from_plan_slot(self, agent: "Agent", world: "World", slot: dict) -> "Decision":
        """plan 슬롯 → Decision 변환 (LLM 호출 X)."""
        action = slot.get("action", "rest")
        target_dong = slot.get("dong") or agent.current_dong
        cat = slot.get("category")
        reason = slot.get("reason") or ""

        store_id = None
        spend = 0.0
        if action == "visit" and cat:
            stores = world.stores_in_dong(target_dong, cat)
            if stores:
                # 가중 선택: rating × popularity_boost (최소 0 clamp).
                # 이전 max(rating) 만 → 신규 매장 popularity_boost 무시되어 입력 시나리오
                # 변화에도 동일 매장 선택. agents.py:435 weighted random 과 일관.
                # boost ≤ 0 인 데이터 오류 시 max 가 첫 항목 반환 / 음수면 역전 → clamp.
                store = max(stores, key=lambda s: s.rating * max(0.0, getattr(s, "popularity_boost", 1.0)))
                store_id = store.store_id
                # 카테고리별 기본 지출 추정
                spend = float(getattr(store, "avg_price", 0) or 8000)
            else:
                # 매장 없음 → action=rest fallback
                action = "rest"

        return Decision(
            action=action,
            target_dong=target_dong,
            target_store_id=store_id,
            spend=spend,
            reason=reason,
        )

    # -----------------------------------------------------------
    # Tier A: Gemini Flash 또는 OpenAI nano
    # -----------------------------------------------------------
    @traceable(run_type="chain", name="brain.tier_a.fast_decide")
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
                _ls_attach_usage(
                    input_tokens=u.prompt_token_count,
                    output_tokens=u.candidates_token_count,
                    model=self.cfg.tier_a_model,
                )
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
    @traceable(run_type="llm", name="brain.tier_s.ollama")
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

    @traceable(run_type="llm", name="brain.tier_a.ollama")
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
    @traceable(run_type="llm", name="brain.tier_a.openai")
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
            # cat="" 정규화 — _parse_daily_plans 와 일관. visit + cat="" 는 store
            # 미해결되어 silent drop 되던 버그 → action="rest" 로 명시 폴백.
            if cat == "":
                cat = None
            spend = float(data.get("spend") or 0)
            reason = data.get("reason", "")[:100]
            target_dong = data.get("target_dong") or agent.current_dong
            store_id = None

            if action == "visit" and cat:
                stores = world.stores_in_dong(target_dong, cat)
                if stores:
                    # popularity_boost 가중 — decision_from_plan_slot 와 일관.
                    store = max(stores, key=lambda s: s.rating * max(0.0, getattr(s, "popularity_boost", 1.0)))
                    store_id = store.store_id
            if action == "visit" and not cat:
                # category 누락된 visit → rest fallback (apply_decision 무시 대신 명시).
                action = "rest"

            return Decision(
                action=action,
                target_dong=target_dong,
                target_store_id=store_id,
                spend=spend,
                reason=reason,
            )
        except Exception as e:
            # silent fallback 이전 → 어느 agent / 어떤 LLM 응답에서 실패했는지 추적 불가.
            # _parse_decision 은 Tier S/A 모든 경로의 최종 파서라 디버깅 가시성 필수.
            print(f"[brain._parse_decision] agent {agent.agent_id} 실패: {e}")
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
            nemo = _nemotron_brief(agent)
            return (
                f"{persona_block}{nemo}\n\n"
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
    @traceable(run_type="llm", name="brain.thought.openai")
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
            gpt-5.4-nano 기준 평균 326 input + 10 output token / call.
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
                model="gpt-5.4-nano",
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
