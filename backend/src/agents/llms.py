import time
import asyncio
from functools import wraps
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config.settings import settings
import os
from dotenv import load_dotenv

load_dotenv()

class LLMRetryProxy:
    """LLM 객체의 invoke/ainvoke를 낚아채서 429 재시도를 수행하는 프록시 클래스"""
    def __init__(self, llm):
        self._llm = llm

    def invoke(self, *args, **kwargs):
        max_retries = 5
        base_delay = 60 # 429 대응을 위해 기본 대기 시간을 60초로 상향
        for attempt in range(max_retries):
            try:
                return self._llm.invoke(*args, **kwargs)
            except Exception as e:
                err_str = str(e).upper()
                if any(x in err_str for x in ["429", "RESOURCE_EXHAUSTED", "503", "500", "504", "UNAVAILABLE"]):
                    wait_time = base_delay * (2 ** attempt)
                    print(f"⚠️ [API-SYNC RECOVERY] {wait_time}초 후 재시도... ({attempt+1}/{max_retries}) - Reason: {err_str[:50]}")
                    time.sleep(wait_time)
                else: raise e
        return self._llm.invoke(*args, **kwargs)

    async def ainvoke(self, *args, **kwargs):
        max_retries = 5
        base_delay = 60
        for attempt in range(max_retries):
            try:
                return await self._llm.ainvoke(*args, **kwargs)
            except Exception as e:
                err_str = str(e).upper()
                if any(x in err_str for x in ["429", "RESOURCE_EXHAUSTED", "503", "500", "504", "UNAVAILABLE"]):
                    wait_time = base_delay * (2 ** attempt)
                    print(f"⚠️ [API-ASYNC RECOVERY] {wait_time}초 후 재시도... ({attempt+1}/{max_retries}) - Reason: {err_str[:50]}")
                    await asyncio.sleep(wait_time)
                else: raise e
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
        # 이미 래핑된 경우 중복 래핑 방지
        if isinstance(llm, LLMRetryProxy):
            return llm
        return LLMRetryProxy(llm)
    return wrapper

@retry_on_429
def get_fast_llm():
    """Supervisor, Market Analyst용 고성능/저지연 모델"""
    if not hasattr(get_fast_llm, "_instance"):
        google_api_key = os.getenv("GOOGLE_API_KEY")
        get_fast_llm._instance = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            google_api_key=google_api_key,
            temperature=0.1,
        )
    return get_fast_llm._instance

@retry_on_429
def get_smart_llm():
    """Gemini 3.1 Pro (복잡한 추론용)"""
    if not hasattr(get_smart_llm, "_instance"):
        google_api_key = os.getenv("GOOGLE_API_KEY")
        get_smart_llm._instance = ChatGoogleGenerativeAI(
            model="gemini-3.1-pro-preview",
            google_api_key=google_api_key,
            temperature=0.1,
        )
    return get_smart_llm._instance
