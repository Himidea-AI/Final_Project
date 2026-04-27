"""
Context Enrichment — 법률 청크에 [법령명 + 조문 제목] 맥락 접두어 주입

before: "② 가맹본부가 가맹계약 갱신과정에서..."
after:  "[가맹사업법 제12조의4 부당한 영업지역 침해금지] ② 가맹본부가 가맹계약 갱신과정에서..."

임베딩 모델이 청크의 법적 맥락을 벡터에 포함하도록 하여 검색 정확도를 높인다.
기존 chunks.json → enriched_chunks.json 생성 (원본 보존)
"""

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CHUNKS_PATH = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "chunks.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "enriched_chunks.json"

# 법률 source → 약칭 매핑
SOURCE_TO_SHORT = {
    "가맹사업거래": "가맹사업법",
    "상가건물 임대차보호법": "상가임대차보호법",
    "식품위생법": "식품위생법",
    "건축법": "건축법",
    "소방시설 설치 및 관리": "소방시설법",
    "근로기준법": "근로기준법",
    "최저임금법": "최저임금법",
    "부가가치세법": "부가가치세법",
    "개인정보 보호법": "개인정보보호법",
    "장애인": "장애인편의법",
    "편의증진": "장애인편의법",
    "하수도법": "하수도법",
    "물환경보전법": "물환경보전법",
    "독점규제 및 공정거래": "공정거래법",
    "다중이용업소": "다중이용업소법",
    "주세법": "주세법",
    "위생교육교재": "위생교육교재",
    "마포구": "마포구조례",
}


def get_law_short(source: str) -> str:
    """source 메타데이터에서 법률 약칭 추출"""
    for keyword, short in SOURCE_TO_SHORT.items():
        if keyword in source:
            return short
    return ""


def extract_article_title(text: str) -> str:
    """텍스트에서 '제N조(제목)' 패턴 추출"""
    # 제12조의4(부당한 영업지역 침해금지)
    m = re.search(r"(제\d+조(?:의\d+)?)\s*[\(（]([^)）]+)[\)）]", text)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return ""


def build_article_title_cache(chunks: list) -> dict:
    """전체 청크에서 조문별 제목 캐시 구축"""
    cache = {}  # (source, article) -> title
    for c in chunks:
        source = c.get("metadata", {}).get("source", "")
        article = c.get("metadata", {}).get("article", "")
        if not article or article in ("전문", "미분류", "N/A"):
            continue

        # 항 분할 접미사 제거
        base_article = re.sub(r"_\d+$", "", article)
        key = (source, base_article)

        if key not in cache:
            text = c.get("text", c.get("content", ""))
            title = extract_article_title(text)
            if title:
                cache[key] = title

    return cache


def enrich_chunk(chunk: dict, title_cache: dict) -> dict:
    """단일 청크에 맥락 접두어 주입"""
    source = chunk.get("metadata", {}).get("source", "")
    article = chunk.get("metadata", {}).get("article", "")
    text = chunk.get("text", chunk.get("content", ""))

    if not article or article in ("전문", "미분류", "N/A"):
        return chunk  # 비조문 청크는 그대로

    law_short = get_law_short(source)
    base_article = re.sub(r"_\d+$", "", article)

    # 조문 제목 조회
    title = title_cache.get((source, base_article), "")

    # 접두어 구성
    if law_short and title:
        prefix = f"[{law_short} {title}]"
    elif law_short and base_article:
        prefix = f"[{law_short} {base_article}]"
    elif base_article:
        prefix = f"[{base_article}]"
    else:
        return chunk

    # 이미 접두어가 있으면 스킵
    if text.startswith("[") and "]" in text[:80]:
        return chunk

    # 접두어 + 원본 텍스트
    enriched_text = f"{prefix} {text}"

    new_chunk = dict(chunk)
    if "text" in new_chunk:
        new_chunk["text"] = enriched_text
    elif "content" in new_chunk:
        new_chunk["content"] = enriched_text
    return new_chunk


def main():
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"[1] 원본 로드: {len(chunks)}개 청크")

    # 조문 제목 캐시
    title_cache = build_article_title_cache(chunks)
    print(f"[2] 조문 제목 캐시: {len(title_cache)}개")

    # 맥락 주입
    enriched = [enrich_chunk(c, title_cache) for c in chunks]

    # 변경 통계
    changed = 0
    for orig, new in zip(chunks, enriched):
        orig_text = orig.get("text", orig.get("content", ""))
        new_text = new.get("text", new.get("content", ""))
        if orig_text != new_text:
            changed += 1
    print(f"[3] 맥락 주입: {changed}/{len(chunks)}개 변경")

    # 샘플 5개
    print(f"\n[4] 샘플 5개:")
    shown = 0
    for orig, new in zip(chunks, enriched):
        orig_text = orig.get("text", orig.get("content", ""))
        new_text = new.get("text", new.get("content", ""))
        if orig_text != new_text:
            print(f"  BEFORE: {orig_text[:80]}...")
            print(f"  AFTER:  {new_text[:100]}...")
            print()
            shown += 1
            if shown >= 5:
                break

    # 저장
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)
    print(f"[5] 저장: {OUTPUT_PATH}")
    print(f"    원본: {CHUNKS_PATH} (보존)")


if __name__ == "__main__":
    main()
