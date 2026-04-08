from langchain_google_genai import ChatGoogleGenerativeAI
from src.config.settings import settings
import os
from dotenv import load_dotenv

# .env 파일 로드 호출 보강
load_dotenv()

"""
[B1 트랙] Gemini 하이브리드 모델 지연 초기화 (Lazy Initialization)
- 서버 기동 시 API 키가 없어도 크래시가 나지 않도록 함수 호출 시점에 생성합니다.
"""


def get_fast_llm():
    """Supervisor, Market Analyst용 고성능/저지연 모델"""
    if not hasattr(get_fast_llm, "_instance"):
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            print("WARNING: GOOGLE_API_KEY is not set in environment or .env file.")
        get_fast_llm._instance = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            google_api_key=google_api_key,
            temperature=0.1,
        )
    return get_fast_llm._instance


def get_smart_llm():
    """Returns a more powerful LLM (Gemini 3 Pro) for complex analysis."""
    if not hasattr(get_smart_llm, "_instance"):
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            print("WARNING: GOOGLE_API_KEY is not set in environment or .env file.")
        get_smart_llm._instance = ChatGoogleGenerativeAI(
            model="gemini-3.1-pro-preview",
            google_api_key=google_api_key,
            temperature=0.1,
        )
    return get_smart_llm._instance


# 노드에서 직접 임포트하여 사용할 수 있도록 팩토리 함수 형태로 제공하거나,
# 프록시 객체를 만들 수 있지만 여기서는 노드에서 함수를 호출하도록 변경하는 것이 안전합니다.
