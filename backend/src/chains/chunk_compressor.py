"""SP6 — RAG 청크 압축 (Chunk Compression).

cheap LLM이 카테고리별 5 청크를 1~2문장 핵심 요약 → 메인 LLM 컨텍스트 -73% 감소.

흐름:
    [12 카테고리 × 5 청크 × 400자 = 24K]
       ↓ cheap LLM (gpt-4.1-mini, 12 병렬)
    [12 카테고리 × 100~150자 = 1.5K]

호출:
    from src.chains.chunk_compressor import compress_docs_map
    compressed = await compress_docs_map(docs_map, brand, business_type, district)

env:
    CHUNK_COMPRESSION_ENABLED=true        # 활성화
    CHUNK_COMPRESSION_MODEL=gpt-4.1-mini  # cheap model
"""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


_COMPRESSION_PROMPT = (
    "당신은 한국 법률 전문가입니다. 아래 RAG 검색 결과 청크들을 바탕으로 "
    "'{law_label}' 법률에서 '{brand}' 브랜드의 '{biz}' 업종 '{district}' 지역 창업 시 "
    "**가장 중요한 의무·위험 조항을 1~2문장**으로 압축 요약해주세요.\n\n"
    "원칙:\n"
    "- 일반론 금지. 입력 케이스에 적용되는 구체적 의무만.\n"
    "- 조문 번호가 본문에 있으면 '제N조' 인용.\n"
    "- 위반 시 제재(과태료/영업정지/형사처벌)가 본문에 있으면 명시.\n"
    "- 100~200자 이내. 두괄식.\n"
    "- 해당 업종에 무관한 청크면 '해당 없음' 출력.\n\n"
    "[청크들]\n{chunks_text}\n\n"
    "압축 요약:"
)


async def _compress_one(
    law_type: str,
    law_label: str,
    docs: list[dict],
    brand: str,
    biz: str,
    district: str,
    llm,
) -> str:
    """카테고리 1개 압축. 빈 docs면 '해당 자료 없음'."""
    if not docs:
        return "해당 자료 없음"

    # 청크 5개 합치기 (각 400자, 메타 노이즈는 cheap LLM이 무시)
    chunks_text = "\n---\n".join((d.get("content") or "")[:400] for d in docs[:5])

    prompt = _COMPRESSION_PROMPT.format(
        law_label=law_label,
        brand=brand,
        biz=biz,
        district=district,
        chunks_text=chunks_text,
    )

    try:
        from langchain_core.messages import HumanMessage

        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        text = (resp.content or "").strip()
        # 너무 길면 자름
        if len(text) > 300:
            text = text[:297] + "…"
        return text or "해당 자료 없음"
    except Exception as e:
        logger.warning(f"[chunk_compressor] {law_type} 압축 실패: {e}")
        # fallback: 첫 청크 첫 200자
        if docs:
            return (docs[0].get("content") or "")[:200] + "…"
        return "해당 자료 없음"


async def compress_docs_map(
    docs_map: dict[str, list[dict]],
    law_labels: dict[str, str],
    brand: str,
    biz: str,
    district: str,
) -> dict[str, str]:
    """12 카테고리 docs_map → 압축된 {category: 1~2문장 요약}.

    병렬 12 cheap LLM call. 약 2~3초 + ~$0.001.

    Returns:
        {law_type: compressed_summary}
    """
    from src.config.settings import settings

    if not settings.chunk_compression_enabled:
        # 비활성 시 비어있는 dict 반환 → caller가 raw chunks 사용
        return {}

    # cheap LLM 인스턴스 — provider별로 분기
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    model = settings.chunk_compression_model

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=model,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0,
            max_tokens=300,
        )
    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        # gemini-1.5-flash 권장 (free tier 더 관대)
        gemini_model = model if "gemini" in model else "gemini-1.5-flash"
        llm = ChatGoogleGenerativeAI(
            model=gemini_model,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0,
            max_output_tokens=300,
        )
    else:
        logger.warning(f"[chunk_compressor] LLM_PROVIDER={provider} 미지원, compression skip")
        return {}

    # 병렬 12 호출
    tasks = [
        _compress_one(law_type, law_labels.get(law_type, law_type), docs, brand, biz, district, llm)
        for law_type, docs in docs_map.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    compressed: dict[str, str] = {}
    for (law_type, _), res in zip(docs_map.items(), results, strict=True):
        if isinstance(res, Exception):
            logger.warning(f"[chunk_compressor] {law_type} 예외: {res}")
            compressed[law_type] = "압축 실패 — raw 청크 fallback"
        else:
            compressed[law_type] = res

    return compressed
