"""
RAG 검색 정확도 벤치마크 — Exact-match 기준

실행: cd backend && python -m tests.bench_rag_accuracy
"""

import asyncio
import selectors
import sys
import time
from pathlib import Path

from src.chains.retriever import LegalDocumentRetriever

# 벤치마크 케이스: (법률명, 쿼리, source_filter_attr, 기대 조문 리스트)
BENCHMARK_CASES = [
    (
        "가맹사업법",
        "영업지역 보장 동일 브랜드 출점 제한 가맹사업법",
        "FRANCHISE_LAW_SOURCES",
        ["제12조의4", "제14조", "제2조"],
    ),
    (
        "상가임대차보호법",
        "권리금 회수 기회 보호 계약갱신요구권 환산보증금 상가임대차보호법",
        "LEASE_LAW_STRICT_SOURCES",
        ["제10조의4", "제10조", "제10조의2"],
    ),
    (
        "식품위생법",
        "cafe 영업신고 허가 위생교육 시설기준 식품위생법",
        "FOOD_HYGIENE_SOURCES",
        ["제41조", "제37조", "제36조"],
    ),
    (
        "건축법",
        "cafe 건축물 용도 근린생활시설 용도변경 건축법",
        "BUILDING_LAW_SOURCES",
        ["제2조", "제19조", "제11조"],
    ),
    (
        "소방시설법",
        "cafe 소방시설 스프링클러 소화기 소방안전관리자 설치의무",
        "FIRE_SAFETY_SOURCES",
        ["제2조", "제13조", "제36조"],
    ),
    (
        "근로기준법",
        "근로계약서 최저임금 주휴수당 가산임금 4대보험 근로기준법",
        "LABOR_LAW_SOURCES",
        ["제2조", "제17조", "제63조"],
    ),
    (
        "부가가치세법",
        "사업자등록 일반과세자 간이과세자 세금계산서 부가가치세",
        "VAT_LAW_SOURCES",
        ["제8조", "제60조", "제34조"],
    ),
    (
        "개인정보보호법",
        "개인정보 수집 동의 처리방침 CCTV 고객정보",
        "PRIVACY_LAW_SOURCES",
        ["제15조", "제25조의2", "제30조"],
    ),
    (
        "장애인편의법",
        "cafe 편의시설 경사로 장애인 설치의무",
        "ACCESSIBILITY_LAW_SOURCES",
        ["제16조", "제2조", "제17조"],
    ),
    (
        "하수도법",
        "cafe 오수처리 유류분리기 그리스트랩 폐수 하수도",
        "SEWAGE_LAW_SOURCES",
        ["제34조", "제37조", "제2조"],
    ),
    (
        "공정거래법",
        "가맹본부 불공정거래 거래강제 필수물품 공급",
        "FAIR_TRADE_SOURCES",
        ["제45조", "제40조", "제2조"],
    ),
]


async def run_benchmark():
    retriever = LegalDocumentRetriever()

    total_expected = 0
    total_hit = 0
    results_table = []

    for law_name, query, filter_attr, expected_articles in BENCHMARK_CASES:
        source_filter = getattr(retriever, filter_attr, None)

        start = time.perf_counter()
        docs = await retriever.search(query, top_k=10, source_filter=source_filter)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 반환된 조문 추출
        returned_articles = []
        for d in docs:
            art = d.get("metadata", {}).get("article", "")
            if art and art not in ("전문", "미분류", "N/A") and art not in returned_articles:
                returned_articles.append(art)

        # Exact-match 적중 계산
        hits = sum(1 for ea in expected_articles if ea in returned_articles)
        total_expected += len(expected_articles)
        total_hit += hits

        results_table.append({
            "law": law_name,
            "expected": expected_articles,
            "returned": returned_articles[:5],
            "hits": hits,
            "total": len(expected_articles),
            "time_ms": round(elapsed_ms),
        })

    # --- LLM-as-judge 평가 ---
    # 반환됐지만 exact-match에 포함되지 않은 조문이 쿼리에 "관련성 있는지" LLM이 판정
    from langchain_openai import ChatOpenAI

    judge_llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0)

    judge_total = 0
    judge_relevant = 0
    judge_details = []

    for r in results_table:
        # exact-match에서 이미 적중한 조문 제외, 나머지 조문만 LLM 판정
        non_matched = [art for art in r["returned"] if art not in r["expected"]]
        if not non_matched:
            continue

        for art in non_matched:
            prompt = (
                f"법률: {r['law']}\n"
                f"검색 쿼리: {r['law']} 관련 프랜차이즈 창업 법률 검토\n"
                f"반환된 조문: {art}\n\n"
                f"이 조문이 프랜차이즈 창업 시 '{r['law']}' 관점에서 관련성이 있습니까?\n"
                f"'YES' 또는 'NO'로만 답하세요."
            )
            try:
                resp = await judge_llm.ainvoke(prompt)
                is_relevant = "YES" in resp.content.upper()
            except Exception as e:
                print(f"  LLM judge error: {e}")
                is_relevant = False

            judge_total += 1
            if is_relevant:
                judge_relevant += 1
            judge_details.append({
                "law": r["law"],
                "article": art,
                "relevant": is_relevant,
            })

    # 실질 정확도 = (exact-match 적중 + LLM 관련 판정) / 전체 반환 조문
    total_returned = sum(len(r["returned"]) for r in results_table)
    llm_relevant_total = total_hit + judge_relevant
    llm_pct = llm_relevant_total / total_returned * 100 if total_returned else 0

    # 결과를 파일로 저장 (UTF-8)
    import json as _json

    output_path = Path(__file__).resolve().parent.parent.parent / "bench_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        _json.dump(
            {
                "exact_match": {
                    "hit": total_hit,
                    "total": total_expected,
                    "accuracy_pct": round(total_hit / total_expected * 100, 1) if total_expected else 0,
                },
                "llm_judge": {
                    "exact_hit": total_hit,
                    "llm_relevant": judge_relevant,
                    "llm_not_relevant": judge_total - judge_relevant,
                    "total_returned": total_returned,
                    "relevance_pct": round(llm_pct, 1),
                    "details": judge_details,
                },
                "per_law": results_table,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Results saved to {output_path}")
    print(f"Exact-match: {total_hit}/{total_expected} ({total_hit / total_expected * 100:.1f}%)")
    print(f"LLM-judge relevance: {llm_relevant_total}/{total_returned} ({llm_pct:.1f}%)")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(run_benchmark(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(run_benchmark())
