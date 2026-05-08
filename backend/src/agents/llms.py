import asyncio
import os
import random
import time
from functools import wraps

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# LLMRetryProxy — 재시도 + jitter + fallback (OpenAI → Gemini)
# ---------------------------------------------------------------------------
# 재시도 트리거: 429 / RESOURCE_EXHAUSTED / 503 / 500 / 504 / UNAVAILABLE / RATE_LIMIT
# 백오프: base_delay × 2^attempt + jitter(0~30%) — thundering herd 분산
# Fallback: 주 모델 max_retries 모두 실패 시 fallback_llm 1회 시도 (없으면 raise)
#
# 설계 의도:
#   본 모델 = OpenAI (LLM_PROVIDER=openai 가 주력 — production 사용)
#   fallback = Gemini (GOOGLE_API_KEY 설정 시 자동 활성)
#   OpenAI 가 일시적 outage / rate limit / quota 초과 시 Gemini 로 자동 우회.
# ---------------------------------------------------------------------------

_RETRY_TRIGGERS = ("429", "RESOURCE_EXHAUSTED", "503", "500", "504", "UNAVAILABLE", "RATE_LIMIT")
_JITTER_RATIO = 0.3  # 백오프의 0~30% 랜덤 추가 — thundering herd 방지


def _backoff_with_jitter(base_delay: int, attempt: int) -> float:
    """지수 백오프 + jitter. 같은 시점 재시도 폭주 분산.

    base_delay × 2^attempt 가 deterministic 베이스 지연. 거기에 0~30% 의 랜덤
    jitter 를 더해 여러 client 가 동시에 동일 간격 retry → 서버 재폭주 패턴 차단.
    """
    base = base_delay * (2**attempt)
    jitter = random.uniform(0, base * _JITTER_RATIO)
    return base + jitter


def _is_retryable(err: Exception) -> bool:
    err_str = str(err).upper()
    return any(t in err_str for t in _RETRY_TRIGGERS)


class LLMRetryProxy:
    """LLM 객체의 invoke/ainvoke 를 낚아채서 재시도·fallback 수행하는 프록시.

    Args:
        llm: 주 모델 (OpenAI ChatOpenAI 등)
        fallback_llm: 주 모델 모든 retry 실패 시 1회 시도할 백업 모델 (Gemini 등).
                      None 이면 fallback 비활성 — 주 모델 실패 시 즉시 raise.
    """

    def __init__(self, llm, fallback_llm=None):
        self._llm = llm
        self._fallback_llm = fallback_llm

    def invoke(self, *args, **kwargs):
        max_retries = 5
        base_delay = 10
        last_err: Exception | None = None
        for attempt in range(max_retries):
            try:
                return self._llm.invoke(*args, **kwargs)
            except Exception as e:
                last_err = e
                if not _is_retryable(e):
                    raise
                wait = _backoff_with_jitter(base_delay, attempt)
                print(
                    f"[WARNING] [API-SYNC RECOVERY] {wait:.1f}초 후 재시도... "
                    f"({attempt + 1}/{max_retries}) - Reason: {str(e)[:50]}"
                )
                time.sleep(wait)
        # 주 모델 모든 retry 실패 → fallback 1회 시도
        if self._fallback_llm is not None:
            print("[WARNING] [API-FALLBACK] 주 모델 retry 모두 실패 — Gemini fallback 시도")
            try:
                return self._fallback_llm.invoke(*args, **kwargs)
            except Exception as fallback_err:
                print(f"[ERROR] [API-FALLBACK] Gemini fallback 도 실패: {str(fallback_err)[:80]}")
                raise fallback_err from last_err
        # fallback 없거나 실패 → 마지막 에러 raise
        if last_err:
            raise last_err
        return self._llm.invoke(*args, **kwargs)

    async def ainvoke(self, *args, **kwargs):
        max_retries = 5
        base_delay = 10
        last_err: Exception | None = None
        for attempt in range(max_retries):
            try:
                return await self._llm.ainvoke(*args, **kwargs)
            except Exception as e:
                last_err = e
                if not _is_retryable(e):
                    raise
                wait = _backoff_with_jitter(base_delay, attempt)
                print(
                    f"[WARNING] [API-ASYNC RECOVERY] {wait:.1f}초 후 재시도... "
                    f"({attempt + 1}/{max_retries}) - Reason: {str(e)[:50]}"
                )
                await asyncio.sleep(wait)
        if self._fallback_llm is not None:
            print("[WARNING] [API-FALLBACK] 주 모델 retry 모두 실패 — Gemini fallback 시도")
            try:
                return await self._fallback_llm.ainvoke(*args, **kwargs)
            except Exception as fallback_err:
                print(f"[ERROR] [API-FALLBACK] Gemini fallback 도 실패: {str(fallback_err)[:80]}")
                raise fallback_err from last_err
        if last_err:
            raise last_err
        return await self._llm.ainvoke(*args, **kwargs)

    def with_structured_output(self, *args, **kwargs):
        """with_structured_output 결과물도 fallback 포함해 LLMRetryProxy 로 재래핑."""
        runnable = self._llm.with_structured_output(*args, **kwargs)
        fallback_runnable = None
        if self._fallback_llm is not None:
            try:
                fallback_runnable = self._fallback_llm.with_structured_output(*args, **kwargs)
            except Exception as e:
                # 일부 LLM 은 with_structured_output 호환성 차이 — fallback 만 비활성으로 진행
                print(f"[WARNING] fallback with_structured_output 실패 (fallback 비활성): {e}")
        return LLMRetryProxy(runnable, fallback_llm=fallback_runnable)

    def __getattr__(self, name):
        return getattr(self._llm, name)


def _build_openai(model: str, max_tokens: int | None = None):
    from langchain_openai import ChatOpenAI

    kwargs = dict(model=model, openai_api_key=os.getenv("OPENAI_API_KEY"), temperature=0.1)
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(**kwargs)


def _build_gemini(model: str, max_tokens: int | None = None):
    from langchain_google_genai import ChatGoogleGenerativeAI

    kwargs = dict(model=model, google_api_key=os.getenv("GOOGLE_API_KEY"), temperature=0.1)
    if max_tokens is not None:
        kwargs["max_output_tokens"] = max_tokens
    return ChatGoogleGenerativeAI(**kwargs)


def _build_llm(model: str, max_tokens: int | None = None):
    """LLM_PROVIDER 환경변수에 따라 LangChain LLM 객체를 생성."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "openai":
        return _build_openai(model, max_tokens)
    if provider == "gemini":
        return _build_gemini(model, max_tokens)
    raise ValueError(f"지원하지 않는 LLM_PROVIDER: {provider}")


def _build_fallback(max_tokens: int | None = None):
    """주 모델 다운 시 사용할 백업 LLM 빌드.

    LLM_PROVIDER=openai (default) 면 fallback=Gemini, 반대로 LLM_PROVIDER=gemini 면
    fallback=OpenAI. 백업 모델 키 (GOOGLE_API_KEY / OPENAI_API_KEY) 가 .env 에 없으면
    fallback 비활성 (None 반환) — get_fast_llm/get_smart_llm 에서 자동 graceful degrade.

    백업 모델은 FALLBACK_LLM_MODEL 환경변수로 명시 가능. 미설정 시 default:
        - OpenAI 주력 → gemini-2.0-flash
        - Gemini 주력 → gpt-4.1-mini
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    fallback_model_env = os.getenv("FALLBACK_LLM_MODEL")
    if provider == "openai":
        if not os.getenv("GOOGLE_API_KEY"):
            return None
        model = fallback_model_env or "gemini-2.0-flash"
        try:
            return _build_gemini(model, max_tokens)
        except Exception as e:
            print(f"[WARNING] Gemini fallback 빌드 실패 (fallback 비활성): {e}")
            return None
    if provider == "gemini":
        if not os.getenv("OPENAI_API_KEY"):
            return None
        model = fallback_model_env or "gpt-4.1-mini"
        try:
            return _build_openai(model, max_tokens)
        except Exception as e:
            print(f"[WARNING] OpenAI fallback 빌드 실패 (fallback 비활성): {e}")
            return None
    return None


def retry_on_429(func):
    """LLM 빌더 함수를 LLMRetryProxy 로 자동 래핑 (fallback 자동 부착)."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        llm = func(*args, **kwargs)
        if isinstance(llm, LLMRetryProxy):
            return llm
        fallback = _build_fallback()
        return LLMRetryProxy(llm, fallback_llm=fallback)

    return wrapper


@retry_on_429
def get_fast_llm():
    """Market Analyst, Population Analyst용 경량 모델 (Structured Output — max_tokens 미설정).
    모델: FAST_LLM_MODEL 환경변수 우선, 미설정 시 gpt-4.1-mini / gemini-2.0-flash.
    Fallback: OpenAI 주력일 때 Gemini, 반대도 동일 (GOOGLE_API_KEY/OPENAI_API_KEY 둘 다 있을 때만).
    """
    if not hasattr(get_fast_llm, "_instance"):
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
        default = "gpt-4.1-mini" if provider == "openai" else "gemini-2.0-flash"
        model = os.getenv("FAST_LLM_MODEL", default)
        get_fast_llm._instance = _build_llm(model)
    return get_fast_llm._instance


@retry_on_429
def get_smart_llm():
    """Synthesis 전용 LLM — 최종 리포트 합성에만 사용.

    기본값은 fast LLM 과 동일 (gpt-4.1-mini / gemini-2.0-flash). Synthesis 는 상위 에이전트가
    이미 정리한 결과를 구조화 스키마로 재구성하는 작업이라 mini 로 충분함.
    품질 비교 후 상위 모델이 필요하면 SMART_LLM_MODEL 환경변수로 옵트인 (예: gpt-4.1).
    """
    if not hasattr(get_smart_llm, "_instance"):
        provider = os.getenv("LLM_PROVIDER", "openai").lower()
        default = "gpt-4.1-mini" if provider == "openai" else "gemini-2.0-flash"
        model = os.getenv("SMART_LLM_MODEL", default)
        get_smart_llm._instance = _build_llm(model)
    return get_smart_llm._instance
