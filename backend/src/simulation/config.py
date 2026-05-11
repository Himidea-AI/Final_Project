"""시뮬레이션 설정 - Tier 비율, 모델, 비용 추정."""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------
# Agent Tier 분포 (절대 카운트 — % 아님 주의)
# ---------------------------------------------------------------
@dataclass
class TierDistribution:
    """Tier S/A/B 절대 에이전트 수 (퍼센트 아님).

    기본값은 1000 agents 기준 50/200/750 (5%/20%/75%).
    `ModelConfig.n_personas` 로 PopulationMix 가 scale 될 때 runner.py 가
    이 분포도 비례 scale 한다 (5000 agents → S=250 / A=1000 / B=3750).

    main.py /simulate-abm 처럼 `TierDistribution(5, 20, 75)` 으로 % 비율을
    넣어도 동일 scale 룰이 적용돼 결과적으로 같은 분포가 나온다.
    """

    tier_s: int = 50  # 풀 LLM (Haiku + cache) — 대표 페르소나
    tier_a: int = 200  # SLM (Gemini Flash-Lite) — 간단한 결정
    tier_b: int = 750  # 규칙 기반 (LLM 0) — 통계 분포

    @property
    def total(self) -> int:
        return self.tier_s + self.tier_a + self.tier_b


# ---------------------------------------------------------------
# 모델 선택 (Tier별)
# ---------------------------------------------------------------
@dataclass
class ModelConfig:
    # Tier S: 풀 LLM + 캐싱 (provider별 모델은 brain에서 자동 선택)
    tier_s_provider: str = "anthropic"  # anthropic | openai | ollama
    tier_s_model: str = "claude-haiku-4-5-20251001"
    tier_s_max_tokens: int = 200

    # Tier A: 경량 모델
    tier_a_provider: str = "gemini"  # gemini | openai | ollama
    tier_a_model: str = "gemini-2.5-flash-lite"
    tier_a_max_tokens: int = 80

    # 캐싱 비활성화 (테스트 모드)
    enable_cache: bool = True

    # Mock 모드 (API 키 없을 때)
    mock_mode: bool = False

    # Ollama 로컬 endpoint (OpenAI 호환)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:3b"

    # B1 /api/simulate-abm 호환 — n_personas로 PopulationMix 총합 오버라이드
    # None이면 PopulationMix 기본값 사용
    n_personas: int | None = None


# ---------------------------------------------------------------
# 인구 구성 (마포구 실측 비율 근사)
# ---------------------------------------------------------------
@dataclass
class PopulationMix:
    """마포구 1000명 에이전트 인구 구성 — v12 baseline.

    실측 지표 Pareto 최적 (v12): RMSE 4.6% / Pearson 0.69 / KL 0.081 / External 92%.
    v14(420/120/80/60/220/100)는 통계청 근거가 탄탄했으나 RMSE·상관 희생 → v12 유지.
    """

    residents: int = 400  # 마포 거주자 (일상 생활)
    commuters: int = 100  # 마포 내 통근 (마포 거주+근무)
    visitors: int = 50  # 단기 방문 (마포 내)
    owners: int = 50  # 점주
    ext_commuters: int = 300  # 외부→마포 출근 (상암/공덕/도화)
    ext_visitors: int = 100  # 외부→마포 저녁 방문 (홍대/연남)


# ---------------------------------------------------------------
# 시뮬레이션 시간 설정
# ---------------------------------------------------------------
@dataclass
class TimeConfig:
    start_hour: int = 6  # 06:00
    end_hour: int = 26  # 익일 02:00 (= 24 + 2)
    step_minutes: int = 60  # 1시간 단위

    @property
    def total_steps(self) -> int:
        return (self.end_hour - self.start_hour) * (60 // self.step_minutes)


# ---------------------------------------------------------------
# 시나리오 (충격 테스트)
# ---------------------------------------------------------------
@dataclass
class Scenario:
    """시뮬 충격 변수.

    weekend_force: True면 모든 날을 주말로 처리
    rent_shock_pct: 점주 비용 + 소비자 가격 인상률 (0.30 = +30%)
    weather_override: "맑음"|"비"|"눈" 중 하나 지정 시 RDS 최신 날씨 무시
    date_override: "YYYY-MM-DD" 지정 시 weekday/is_holiday 자동 계산
    new_store: LangGraph 결과 신규 매장 스펙 (B1 /api/simulate-abm 연동용)
        {district, brand, category, score, estimated_revenue, ...}
    cannibalize_radius_m: 신규 매장 반경 내 기존 매장 잠식 계산 반경 (m)
    """

    weekend_force: bool = False
    rent_shock_pct: float = 0.0
    weather_override: str | None = None
    date_override: str | None = None
    new_store: dict | None = None
    cannibalize_radius_m: int = 500

    @property
    def price_multiplier(self) -> float:
        return 1.0 + self.rent_shock_pct


# ---------------------------------------------------------------
# 동별 상권 DNA - 오피스/유흥/트렌디/전통 성격
# ---------------------------------------------------------------
DONG_CHARACTER: dict[str, dict] = {
    "서교동": {"type": "nightlife", "cat_boost": {"주점": 1.5, "카페": 1.3, "음식점": 1.2}},
    "합정동": {"type": "nightlife", "cat_boost": {"주점": 1.4, "카페": 1.2, "음식점": 1.2}},
    "연남동": {"type": "trendy", "cat_boost": {"카페": 1.5, "음식점": 1.2}},
    "망원1동": {"type": "trendy", "cat_boost": {"카페": 1.3, "음식점": 1.2}},
    "상암동": {"type": "office", "cat_boost": {"음식점": 1.3, "카페": 1.2, "편의점": 1.2}},
    "공덕동": {"type": "office", "cat_boost": {"음식점": 1.3, "주점": 1.1, "카페": 1.1}},
    "도화동": {"type": "office", "cat_boost": {"음식점": 1.2, "카페": 1.1}},
    "용강동": {"type": "residential", "cat_boost": {"편의점": 1.2}},
    "망원2동": {"type": "traditional", "cat_boost": {"편의점": 1.2, "음식점": 1.1}},
    "아현동": {"type": "residential", "cat_boost": {"편의점": 1.3}},
    "염리동": {"type": "residential", "cat_boost": {"편의점": 1.2}},
    "대흥동": {"type": "residential", "cat_boost": {"편의점": 1.2, "음식점": 1.1}},
    "신수동": {"type": "nightlife", "cat_boost": {"주점": 1.3, "음식점": 1.2}},
    "서강동": {"type": "residential", "cat_boost": {}},
    "성산1동": {"type": "residential", "cat_boost": {"편의점": 1.1}},
    "성산2동": {"type": "residential", "cat_boost": {"편의점": 1.1}},
}

OFFICE_DONGS: list[str] = [d for d, m in DONG_CHARACTER.items() if m["type"] == "office"]
NIGHTLIFE_DONGS: list[str] = [d for d, m in DONG_CHARACTER.items() if m["type"] == "nightlife"]
TRENDY_DONGS: list[str] = [d for d, m in DONG_CHARACTER.items() if m["type"] == "trendy"]


# ---------------------------------------------------------------
# 마포구 행정동 (16개)
# ---------------------------------------------------------------
MAPO_DONGS: list[str] = [
    "공덕동",
    "아현동",
    "도화동",
    "용강동",
    "대흥동",
    "염리동",
    "신수동",
    "서강동",
    "서교동",
    "합정동",
    "망원1동",
    "망원2동",
    "연남동",
    "성산1동",
    "성산2동",
    "상암동",
]


# ---------------------------------------------------------------
# 비용 추정 (USD per 1M tokens, 2026-04 기준)
# ---------------------------------------------------------------
PRICING = {
    "claude-haiku-4-5-20251001": {
        "input": 1.0,
        "output": 5.0,
        "cache_read": 0.10,  # 90% 할인
        "cache_write": 1.25,  # 25% 추가
    },
    "gemini-2.0-flash": {
        "input": 0.10,
        "output": 0.40,
    },
    "gemini-2.5-flash-lite": {
        "input": 0.10,
        "output": 0.40,
    },
    # OpenAI fallback - 2026-04 기준
    "gpt-4o-mini": {
        "input": 0.15,
        "output": 0.60,
        "cache_read": 0.075,  # 50% 할인 (1024 tok 이상 자동)
        "cache_write": 0.15,  # 동일
    },
    "gpt-4.1-nano": {
        "input": 0.10,
        "output": 0.40,
    },
    "gpt-4.1-mini": {
        "input": 0.40,
        "output": 1.60,
        "cache_read": 0.10,
        "cache_write": 0.40,
    },
}


def log_llm_call(name: str, model: str, usage, n_agents: int = 1) -> float:
    """LLM 호출 직후 토큰/비용 콘솔 출력 + USD return.

    usage: openai SDK ChatCompletion.usage 객체. prompt_tokens / completion_tokens /
    prompt_tokens_details.cached_tokens 추출.
    """
    in_tok = getattr(usage, "prompt_tokens", 0) or 0
    out_tok = getattr(usage, "completion_tokens", 0) or 0
    details = getattr(usage, "prompt_tokens_details", None)
    cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0

    p = PRICING.get(model, {})
    in_rate = p.get("input", 0.0)
    out_rate = p.get("output", 0.0)
    cache_rate = p.get("cache_read", in_rate)

    fresh_in = max(0, in_tok - cached)
    in_cost = fresh_in * in_rate / 1e6
    cache_cost = cached * cache_rate / 1e6
    out_cost = out_tok * out_rate / 1e6
    total = in_cost + cache_cost + out_cost

    print(
        f"[LLM] {name:30s} model={model} n={n_agents:3d} "
        f"in={in_tok:5d}(cached={cached:5d}) out={out_tok:5d} "
        f"cost=${total:.5f}",
        flush=True,
    )
    return total


def estimate_cost(
    tier_s_calls: int,
    tier_a_calls: int,
    cfg: ModelConfig | None = None,
) -> dict[str, float]:
    """일일 시뮬레이션 비용 추정 (USD)."""
    cfg = cfg or ModelConfig()

    # Tier S — 풀 LLM + 캐싱 가정 (페르소나 500 tok 캐시)
    s_in = tier_s_calls * 100  # 동적 컨텍스트만 100 tok
    s_cache = 500  # 페르소나 (1회 작성, 매번 read)
    s_out = tier_s_calls * cfg.tier_s_max_tokens

    p = PRICING.get(cfg.tier_s_model, PRICING["gpt-4o-mini"])
    s_cost = s_in * p["input"] / 1e6 + s_out * p["output"] / 1e6
    if "cache_read" in p:
        s_cost += s_cache * p["cache_write"] / 1e6
        s_cost += s_cache * tier_s_calls * p["cache_read"] / 1e6
    else:
        s_cost += s_cache * tier_s_calls * p["input"] / 1e6  # 캐시 없으면 매번 풀 비용

    # Tier A — 경량
    a_in = tier_a_calls * 200
    a_out = tier_a_calls * cfg.tier_a_max_tokens
    pa = PRICING.get(cfg.tier_a_model, PRICING["gpt-4.1-nano"])
    a_cost = a_in * pa["input"] / 1e6 + a_out * pa["output"] / 1e6

    return {
        "tier_s_usd": round(s_cost, 4),
        "tier_a_usd": round(a_cost, 4),
        "total_usd": round(s_cost + a_cost, 4),
    }
