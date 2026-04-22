"""
RAG 벤치마크 안정성 검증 — 동일 조건 5회 반복 측정

실행: cd backend && python -m tests.bench_stability
"""

import asyncio
import selectors
import sys
import time
import json
from pathlib import Path

if sys.platform == "win32":
    pass  # loop_factory로 처리

from src.chains.retriever import LegalDocumentRetriever

BENCHMARK_CASES = [
    ("가맹사업법", "영업지역 보장 동일 브랜드 출점 제한 가맹사업법", "FRANCHISE_LAW_SOURCES", ["제12조의4", "제14조", "제2조"]),
    ("상가임대차보호법", "권리금 회수 기회 보호 계약갱신요구권 환산보증금 상가임대차보호법", "LEASE_LAW_STRICT_SOURCES", ["제10조의4", "제10조", "제10조의2"]),
    ("식품위생법", "cafe 영업신고 허가 위생교육 시설기준 식품위생법", "FOOD_HYGIENE_SOURCES", ["제41조", "제37조", "제36조"]),
    ("건축법", "cafe 건축물 용도 근린생활시설 용도변경 건축법", "BUILDING_LAW_SOURCES", ["제2조", "제19조", "제11조"]),
    ("소방시설법", "cafe 소방시설 스프링클러 소화기 소방안전관리자 설치의무", "FIRE_SAFETY_SOURCES", ["제2조", "제13조", "제36조"]),
    ("근로기준법", "근로계약서 최저임금 주휴수당 가산임금 4대보험 근로기준법", "LABOR_LAW_SOURCES", ["제2조", "제17조", "제63조"]),
    ("부가가치세법", "사업자등록 일반과세자 간이과세자 세금계산서 부가가치세", "VAT_LAW_SOURCES", ["제8조", "제60조", "제34조"]),
    ("개인정보보호법", "개인정보 수집 동의 처리방침 CCTV 고객정보", "PRIVACY_LAW_SOURCES", ["제15조", "제25조의2", "제30조"]),
    ("장애인편의법", "cafe 편의시설 경사로 장애인 설치의무", "ACCESSIBILITY_LAW_SOURCES", ["제16조", "제2조", "제17조"]),
    ("하수도법", "cafe 오수처리 유류분리기 그리스트랩 폐수 하수도", "SEWAGE_LAW_SOURCES", ["제34조", "제37조", "제2조"]),
    ("공정거래법", "가맹본부 불공정거래 거래강제 필수물품 공급", "FAIR_TRADE_SOURCES", ["제45조", "제40조", "제2조"]),
]

NUM_RUNS = 5


async def single_run(retriever, run_id):
    total_expected = 0
    total_hit = 0
    per_law = {}

    for law_name, query, filter_attr, expected_articles in BENCHMARK_CASES:
        source_filter = getattr(retriever, filter_attr, None)
        docs = await retriever.search(query, top_k=10, source_filter=source_filter)

        returned_articles = []
        for d in docs:
            art = d.get("metadata", {}).get("article", "")
            if art and art not in ("전문", "미분류", "N/A") and art not in returned_articles:
                returned_articles.append(art)

        hits = sum(1 for ea in expected_articles if ea in returned_articles)
        total_expected += len(expected_articles)
        total_hit += hits
        per_law[law_name] = {"hits": hits, "total": len(expected_articles), "returned": returned_articles[:5]}

    pct = total_hit / total_expected * 100 if total_expected else 0
    return {"run": run_id, "hit": total_hit, "total": total_expected, "pct": round(pct, 1), "per_law": per_law}


async def run_stability():
    retriever = LegalDocumentRetriever()
    results = []

    for i in range(NUM_RUNS):
        r = await single_run(retriever, i + 1)
        results.append(r)
        print(f"Run {i+1}/{NUM_RUNS}: {r['hit']}/{r['total']} ({r['pct']}%)")

    # 통계
    pcts = [r["pct"] for r in results]
    mean_pct = sum(pcts) / len(pcts)
    variance = sum((p - mean_pct) ** 2 for p in pcts) / len(pcts)
    std_dev = variance ** 0.5

    # 법률별 안정성
    law_stability = {}
    for law_name in [c[0] for c in BENCHMARK_CASES]:
        hits_per_run = [r["per_law"][law_name]["hits"] for r in results]
        law_stability[law_name] = {
            "hits_per_run": hits_per_run,
            "min": min(hits_per_run),
            "max": max(hits_per_run),
            "stable": min(hits_per_run) == max(hits_per_run),
        }

    output = {
        "num_runs": NUM_RUNS,
        "exact_match_pcts": pcts,
        "mean": round(mean_pct, 2),
        "std_dev": round(std_dev, 2),
        "variance": round(variance, 2),
        "min": min(pcts),
        "max": max(pcts),
        "per_law_stability": law_stability,
    }

    output_path = Path(__file__).resolve().parent.parent.parent / "bench_stability.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"Runs: {NUM_RUNS}")
    print(f"Scores: {pcts}")
    print(f"Mean: {mean_pct:.2f}%")
    print(f"Std Dev: {std_dev:.2f}%")
    print(f"Range: {min(pcts)}% - {max(pcts)}%")
    print(f"\nPer-law stability:")
    for law, s in law_stability.items():
        status = "STABLE" if s["stable"] else f"UNSTABLE ({s['min']}-{s['max']})"
        print(f"  {law}: {s['hits_per_run']} -> {status}")
    print(f"\nSaved to {output_path}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.run(run_stability(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    else:
        asyncio.run(run_stability())
