"""S-2 Multi-query expansion — cheap LLM이 1 쿼리 → N개 변형 생성.

기대: Recall +10~15%. 다양한 phrasing/synonym/관점 cover.

사용:
    from src.chains.multi_query import expand_query
    variants = await expand_query("권리금 회수 보호", n=3)
    # 예: ["임차인 권리금 회수 청구 요건", "상가건물 권리금 회수 임대인 방해 금지", ...]
"""

from __future__ import annotations

import asyncio
import logging
import re

from src.config.settings import settings

logger = logging.getLogger(__name__)

_SYS_PROMPT = """당신은 법률 RAG 검색용 쿼리 변형 생성기입니다.
주어진 질의를 의미는 동일하되 표현/용어/관점을 다르게 한 N개 변형으로 생성하세요.

원칙:
1. 법률 용어/약어/유사 표현 활용 ("권리금" ↔ "임차인 영업권 가치", "임대차" ↔ "상가건물 임대차")
2. 핵심 키워드는 유지 — 너무 추상화하지 말 것
3. 길이는 원본과 비슷하게 (10~30자)
4. 한 줄에 하나씩, 번호 없이 출력
5. 원본은 포함하지 마세요 (별도로 합쳐짐)
"""


# SP6 보안: 무제한 증가 방지를 위해 LRU 흉내 (insertion order = oldest first).
# Python dict는 3.7+ 부터 insertion order 보존 → maxsize 초과 시 oldest pop.
# cachetools 추가 없이 동작하도록 직접 구현. 멀티 워커 환경에선 워커당 캐시.
_CACHE_MAXSIZE = 500
_cache: dict[str, list[str]] = {}


async def expand_query(query: str, n: int | None = None) -> list[str]:
    """1 쿼리 → N개 변형 list (원본 미포함)."""
    if not settings.multi_query_enabled:
        return []

    n = n or settings.multi_query_n
    cache_key = f"{query}|{n}"
    if cache_key in _cache:
        # LRU: 사용된 키를 끝으로 이동 (최근 사용 = 가장 늦게 evict)
        _cache[cache_key] = _cache.pop(cache_key)
        return _cache[cache_key]

    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model=settings.multi_query_model, temperature=0.3)
        prompt = f"{_SYS_PROMPT}\n\n원본 질의: {query}\n\n변형 {n}개:"
        resp = await llm.ainvoke(prompt)
        text = (resp.content or "").strip()
    except Exception as e:
        logger.warning(f"[multi_query] LLM 실패: {e}")
        return []

    variants: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # 번호/불릿 제거 ("1. ", "- ", "• " 등)
        line = re.sub(r"^[0-9]+[\.\)]\s*|^[-•·]\s*", "", line)
        if line and line != query:
            variants.append(line)
    variants = variants[:n]
    # maxsize 초과 시 가장 오래된 키 evict (LRU)
    if len(_cache) >= _CACHE_MAXSIZE:
        _cache.pop(next(iter(_cache)))
    _cache[cache_key] = variants
    return variants
