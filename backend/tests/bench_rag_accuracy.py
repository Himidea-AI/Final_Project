"""
RAG 검색 정확도 벤치마크 — F1-score + Exact-match + LLM-judge

실행: cd backend && python -m tests.bench_rag_accuracy
"""

import asyncio
import re
import selectors
import sys
import time
from pathlib import Path

from src.chains.retriever import LegalDocumentRetriever

# Golden dataset v3 — 법률 원문 기반 독립 선별, 쿼리별 정답 분리
# 각 법률을 여러 주제(쿼리)로 나누고, 쿼리가 묻는 범위에 해당하는 조문만 정답으로 지정
# chunks.json에 존재하는 조문만 포함
BENCHMARK_CASES = [
    # ── 가맹사업법 ──
    (
        "가맹사업법",
        "영업지역 보장 동일 브랜드 출점 제한 가맹사업법",
        "FRANCHISE_LAW_SOURCES",
        ["제12조의4", "제12조의5", "제14조"],
    ),
    (
        "가맹사업법",
        "정보공개서 등록 의무 가맹본부 가맹사업법",
        "FRANCHISE_LAW_SOURCES",
        ["제6조의2", "제6조의3", "제7조"],
    ),
    (
        "가맹사업법",
        "가맹금 반환 예치 가맹계약 해제 가맹사업법",
        "FRANCHISE_LAW_SOURCES",
        ["제10조", "제6조의5", "제15조의2"],
    ),
    # ── 상가임대차보호법 ──
    (
        "상가임대차보호법",
        "권리금 회수 기회 보호 상가임대차보호법",
        "LEASE_LAW_STRICT_SOURCES",
        ["제10조의4", "제10조의5"],
    ),
    (
        "상가임대차보호법",
        "계약갱신요구권 임대차 기간 상가건물",
        "LEASE_LAW_STRICT_SOURCES",
        ["제10조", "제10조의2", "제9조"],
    ),
    (
        "상가임대차보호법",
        "환산보증금 차임 증감청구 보증금 보호",
        "LEASE_LAW_STRICT_SOURCES",
        ["제2조", "제11조", "제12조"],
    ),
    # ── 식품위생법 ──
    (
        "식품위생법",
        "영업신고 영업허가 절차 식품위생법",
        "FOOD_HYGIENE_SOURCES",
        ["제37조", "제36조"],
    ),
    (
        "식품위생법",
        "위생교육 식품접객업 의무 식품위생법",
        "FOOD_HYGIENE_SOURCES",
        ["제41조", "제43조"],
    ),
    (
        "식품위생법",
        "시설기준 영업자 준수사항 식품위생법",
        "FOOD_HYGIENE_SOURCES",
        ["제3조", "제44조"],
    ),
    # ── 건축법 ──
    (
        "건축법",
        "건축물 용도변경 근린생활시설 건축법",
        "BUILDING_LAW_SOURCES",
        ["제19조", "제2조"],
    ),
    (
        "건축법",
        "건축허가 건축신고 절차 건축법",
        "BUILDING_LAW_SOURCES",
        ["제11조", "제14조"],
    ),
    # ── 소방시설법 ──
    (
        "소방시설법",
        "소방시설 설치 의무 기준 소방시설법",
        "FIRE_SAFETY_SOURCES",
        ["제12조", "제13조"],
    ),
    (
        "소방시설법",
        "소방안전관리자 선임 의무 소방시설법",
        "FIRE_SAFETY_SOURCES",
        ["제24조", "제25조"],
    ),
    (
        "소방시설법",
        "소방시설 자체점검 정기점검 소방시설법",
        "FIRE_SAFETY_SOURCES",
        ["제22조", "제23조"],
    ),
    # ── 근로기준법 ──
    (
        "근로기준법",
        "근로계약서 서면 명시 의무 근로기준법",
        "LABOR_LAW_SOURCES",
        ["제17조", "제2조"],
    ),
    (
        "근로기준법",
        "임금 지급 최저임금 주휴수당 가산임금 근로기준법",
        "LABOR_LAW_SOURCES",
        ["제43조", "제56조"],
    ),
    (
        "근로기준법",
        "근로시간 휴게 휴일 연장근로 근로기준법",
        "LABOR_LAW_SOURCES",
        ["제50조", "제54조", "제55조"],
    ),
    # ── 부가가치세법 ──
    (
        "부가가치세법",
        "사업자등록 신청 절차 부가가치세법",
        "VAT_LAW_SOURCES",
        ["제8조"],
    ),
    (
        "부가가치세법",
        "세금계산서 발급 의무 부가가치세법",
        "VAT_LAW_SOURCES",
        ["제32조", "제34조"],
    ),
    (
        "부가가치세법",
        "간이과세자 공급대가 개인사업자 과세표준 부가가치세법",
        "VAT_LAW_SOURCES",
        ["제61조", "제63조"],
    ),
    # ── 개인정보보호법 ──
    (
        "개인정보보호법",
        "개인정보 수집 이용 동의 목적 개인정보보호법",
        "PRIVACY_LAW_SOURCES",
        ["제15조", "제16조"],
    ),
    (
        "개인정보보호법",
        "CCTV 영상정보처리기기 설치 운영 개인정보보호법",
        "PRIVACY_LAW_SOURCES",
        ["제25조", "제25조의2"],
    ),
    (
        "개인정보보호법",
        "개인정보 처리방침 수립 공개 의무 개인정보보호법",
        "PRIVACY_LAW_SOURCES",
        ["제30조", "제31조"],
    ),
    # ── 장애인편의법 ──
    (
        "장애인편의법",
        "대상시설 편의시설 설치 공공건물 공중이용시설 장애인편의법",
        "ACCESSIBILITY_LAW_SOURCES",
        ["제7조", "제8조"],
    ),
    (
        "장애인편의법",
        "편의시설 설치기준 경사로 출입구 장애인편의법",
        "ACCESSIBILITY_LAW_SOURCES",
        ["제16조", "제17조"],
    ),
    # ── 하수도법 ──
    (
        "하수도법",
        "오수 배출 개인하수처리시설 설치 배수설비 하수도법",
        "SEWAGE_LAW_SOURCES",
        ["제34조", "제37조"],
    ),
    (
        "하수도법",
        "공공하수도 배수구역 배수설비 유입 설치 하수도법",
        "SEWAGE_LAW_SOURCES",
        ["제27조", "제28조"],
    ),
    # ── 공정거래법 ──
    (
        "공정거래법",
        "불공정거래행위 금지 거래강제 공정거래법",
        "FAIR_TRADE_SOURCES",
        ["제45조", "제40조"],
    ),
    (
        "공정거래법",
        "가맹본부 필수물품 공급 부당한 거래 공정거래법",
        "FAIR_TRADE_SOURCES",
        ["제47조", "제55조"],
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
        docs = await retriever.search(query, top_k=5, source_filter=source_filter)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # 반환된 조문 추출 — 항 분할 접미사(_0, _1 등) 제거하여 조 단위로 정규화
        returned_articles = []
        for d in docs:
            art = d.get("metadata", {}).get("article", "")
            if art and art not in ("전문", "미분류", "N/A"):
                # "제2조_0" → "제2조", "제45조_3" → "제45조" (항 분할 접미사 제거)
                normalized = re.sub(r"_\d+$", "", art)
                if normalized not in returned_articles:
                    returned_articles.append(normalized)

        # Exact-match 적중 계산
        hits = sum(1 for ea in expected_articles if ea in returned_articles)
        total_expected += len(expected_articles)
        total_hit += hits

        results_table.append({
            "law": law_name,
            "query": query,
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
                "당신은 한국 법률 전문가입니다. 아래 조문이 검색 쿼리의 주제에 **직접적으로** 관련이 있는지 엄격하게 판단하세요.\n\n"
                "판단 기준:\n"
                "- YES: 해당 조문이 쿼리 주제의 의무·권리·절차·요건을 직접 규정하는 경우만\n"
                "- NO: 같은 법률이라도 쿼리 주제와 다른 영역의 조문이면 NO\n"
                "- NO: 다른 법률의 조문이면 무조건 NO\n"
                "- NO: 벌칙·부칙·경과규정 등 간접 조문이면 NO\n"
                "- NO: 조문 내용을 확실히 알지 못하면 NO (추측 금지)\n\n"
                "[예시]\n"
                "법률: 식품위생법 / 쿼리: 영업신고 절차 / 조문: 제37조(영업허가 등) → YES (영업신고를 직접 규정)\n"
                "법률: 식품위생법 / 쿼리: 영업신고 절차 / 조문: 제97조(벌칙) → NO (벌칙 조문, 간접)\n"
                "법률: 소방시설법 / 쿼리: 소방시설 설치 / 조문: 제10조의4(상가임대차) → NO (다른 법률 조문)\n"
                "법률: 근로기준법 / 쿼리: 근로계약서 / 조문: 제34조(근로시간) → NO (다른 주제)\n\n"
                "[판단 대상]\n"
                f"법률: {r['law']}\n"
                f"검색 쿼리: {r['query']}\n"
                f"반환된 조문: {art}\n\n"
                "'YES' 또는 'NO'로만 답하세요."
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
                "query": r["query"],
                "article": art,
                "relevant": is_relevant,
            })

    # 실질 정확도 = (exact-match 적중 + LLM 관련 판정) / 전체 반환 조문
    total_returned = sum(len(r["returned"]) for r in results_table)
    llm_relevant_total = total_hit + judge_relevant
    llm_pct = llm_relevant_total / total_returned * 100 if total_returned else 0

    # --- F1-score 계산 (Precision / Recall / F1) ---
    # 쿼리별 + 전체 매크로/마이크로 F1
    f1_per_query = []
    micro_tp = 0  # True Positive (기대 조문 중 반환된 것)
    micro_fp = 0  # False Positive (반환됐지만 기대에 없는 것)
    micro_fn = 0  # False Negative (기대했지만 반환 안 된 것)

    for r in results_table:
        expected_set = set(r["expected"])
        returned_set = set(r["returned"])
        tp = len(expected_set & returned_set)
        fp = len(returned_set - expected_set)
        fn = len(expected_set - returned_set)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        f1_per_query.append({
            "law": r["law"],
            "query": r["query"],
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "tp": tp, "fp": fp, "fn": fn,
        })
        micro_tp += tp
        micro_fp += fp
        micro_fn += fn

    # 마이크로 F1 (전체 합산)
    micro_precision = micro_tp / (micro_tp + micro_fp) if (micro_tp + micro_fp) > 0 else 0.0
    micro_recall = micro_tp / (micro_tp + micro_fn) if (micro_tp + micro_fn) > 0 else 0.0
    micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall) if (micro_precision + micro_recall) > 0 else 0.0

    # 매크로 F1 (쿼리별 평균)
    macro_f1 = sum(r["f1"] for r in f1_per_query) / len(f1_per_query) if f1_per_query else 0.0

    # --- 콘솔 출력 ---
    print("\n=== F1-Score 결과 ===")
    print(f"{'법률':<16} {'쿼리':<30} {'Prec':>5} {'Rec':>5} {'F1':>5}")
    print("-" * 65)
    for r in f1_per_query:
        q_short = r['query'][:28]
        print(f"{r['law']:<16} {q_short:<30} {r['precision']:>5.3f} {r['recall']:>5.3f} {r['f1']:>5.3f}")
    print("-" * 65)
    print(f"{'Micro':<48} {micro_precision:>5.3f} {micro_recall:>5.3f} {micro_f1:>5.3f}")
    print(f"{'Macro':<48} {'':>5} {'':>5} {macro_f1:>5.3f}")

    # 결과를 파일로 저장 (UTF-8)
    import json as _json

    output_path = Path(__file__).resolve().parent.parent.parent / "bench_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        _json.dump(
            {
                "f1_score": {
                    "micro_precision": round(micro_precision, 4),
                    "micro_recall": round(micro_recall, 4),
                    "micro_f1": round(micro_f1, 4),
                    "macro_f1": round(macro_f1, 4),
                    "per_query": f1_per_query,
                },
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
                "per_query": results_table,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\nResults saved to {output_path}")
    print(f"Exact-match: {total_hit}/{total_expected} ({total_hit / total_expected * 100:.1f}%)")
    print(f"LLM-judge relevance: {llm_relevant_total}/{total_returned} ({llm_pct:.1f}%)")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(run_benchmark(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(run_benchmark())
