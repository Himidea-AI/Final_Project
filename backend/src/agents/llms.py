import time
import asyncio
from functools import wraps
import os
from dotenv import load_dotenv

load_dotenv()


class LLMRetryProxy:
    """LLM 객체의 invoke/ainvoke를 낚아채서 429 재시도를 수행하는 프록시 클래스"""
    def __init__(self, llm):
        self._llm = llm

    def invoke(self, *args, **kwargs):
        max_retries = 5
        base_delay = 10
        for attempt in range(max_retries):
            try:
                return self._llm.invoke(*args, **kwargs)
            except Exception as e:
                err_str = str(e).upper()
                if any(x in err_str for x in ["429", "RESOURCE_EXHAUSTED", "503", "500", "504", "UNAVAILABLE", "RATE_LIMIT"]):
                    wait_time = base_delay * (2 ** attempt)
                    print(f"⚠️ [API-SYNC RECOVERY] {wait_time}초 후 재시도... ({attempt+1}/{max_retries}) - Reason: {err_str[:50]}")
                    time.sleep(wait_time)
                else:
                    raise e
        return self._llm.invoke(*args, **kwargs)

    async def ainvoke(self, *args, **kwargs):
        max_retries = 5
        base_delay = 10
        for attempt in range(max_retries):
            try:
                return await self._llm.ainvoke(*args, **kwargs)
            except Exception as e:
                err_str = str(e).upper()
                if any(x in err_str for x in ["429", "RESOURCE_EXHAUSTED", "503", "500", "504", "UNAVAILABLE", "RATE_LIMIT"]):
                    wait_time = base_delay * (2 ** attempt)
                    print(f"⚠️ [API-ASYNC RECOVERY] {wait_time}초 후 재시도... ({attempt+1}/{max_retries}) - Reason: {err_str[:50]}")
                    await asyncio.sleep(wait_time)
                else:
                    raise e
        return await self._llm.ainvoke(*args, **kwargs)

    def with_structured_output(self, *args, **kwargs):
        """with_structured_output 결과물도 LLMRetryProxy로 래핑하여 반환"""
        runnable = self._llm.with_structured_output(*args, **kwargs)
        return LLMRetryProxy(runnable)

    def __getattr__(self, name):
        return getattr(self._llm, name)


def retry_on_429(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        llm = func(*args, **kwargs)
        if isinstance(llm, LLMRetryProxy):
            return llm
        return LLMRetryProxy(llm)
    return wrapper


def _build_llm(model: str):
    """LLM_PROVIDER 환경변수에 따라 LangChain LLM 객체를 생성."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.1,
        )
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1,
        )
    raise ValueError(f"지원하지 않는 LLM_PROVIDER: {provider}")


@retry_on_429
def get_fast_llm():
    """Market Analyst, Population, Synthesis용 빠른 모델"""
    if not hasattr(get_fast_llm, "_instance"):
        get_fast_llm._instance = _build_llm("gpt-4.1-mini")
    return get_fast_llm._instance


@retry_on_429
def get_smart_llm():
    """복잡한 추론이 필요한 경우용 모델 (현재 fast와 동일 모델 사용)"""
    if not hasattr(get_smart_llm, "_instance"):
        get_smart_llm._instance = _build_llm("gpt-4.1-mini")
    return get_smart_llm._instance
