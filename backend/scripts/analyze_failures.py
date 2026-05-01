"""
오답 분석 (Hard Negative Mining) — F1 < 1.0 사례 전수 조사

출력: data/legal/processed/fail_cases.json
구조: [{
    query, law, expected[], returned[],
    top1_wrong: {article, snippet, score},
    correct_missed: [article],
    confusion_pairs: [{wrong, correct, score_diff}],
    f1
}]
"""
import asyncio
import csv
import json
import re
import selectors
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.chains.retriever import LegalDocumentRetriever

GOLDEN = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "golden_set_500_v2.csv"
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "fail_cases.json"

QUERY_REWRITE = {
    "계약갱신요구권 임대차 기간 상가건물": "계약갱신요구권 갱신거절 임대차기간 10년 상가건물 임대차보호법",
    "소방안전관리자 선임 의무 소방시설법": "소방안전관리자 선임 자격 대상 특정소방대상물 소방시설법",
    "가맹본부 필수품목 구입강제 가맹사업법": "불공정거래행위 구속조건부 거래 필수품목 가맹사업법",
    "가맹본부가 내 매장 근처에 같은 브랜드 매장을 열었어요": "영업지역 침해 동일 브랜드 출점 제한 가맹사업법 제12조의4",
    "가맹점 반경 500m 동일 브랜드 출점": "영업지역 침해 부당한 영업지역 침해금지 가맹사업법 제12조의4",
    "가맹본부 물품 구입 강제 가맹사업법": "불공정거래행위 구속조건부 거래 필수품목 가맹사업법 제12조",
    "가맹본부 부당한 거래조건 강제": "불공정거래행위 구속조건부 거래 가맹사업법 제12조",
    "가맹본부 공산품 독점 공급 강제": "불공정거래행위 구속조건부 거래 가맹사업법 제12조",
    "가맹본부 식자재 독점 공급 문제": "불공정거래행위 구속조건부 거래 가맹사업법 제12조",
    "매출 보장 허위 광고 가맹사업법": "허위 과장 정보제공행위 예상매출액 산정서 가맹사업법 제9조",
    "월 매출 5000만원 보장한다고 했는데 실제 1500만원": "허위 과장 정보제공 예상매출액 가맹사업법 제9조",
    "허위 매출 정보 손해배상 가맹사업법": "허위 과장 정보제공 손해배상 가맹사업법 제9조 제10조",
    "임대차 기간 최소 보장 상가건물": "임대차기간 1년 계약갱신요구권 상가건물 임대차보호법 제9조",
    "묵시적 갱신 상가 임대차": "계약갱신요구권 갱신거절 통지 임대차기간 상가건물 제10조",
    "카페 영업신고 방법 절차": "식품접객업 영업신고 영업허가 식품위생법 제37조 제36조",
    "음식점 영업허가 필요 서류": "식품접객업 영업신고 영업허가 식품위생법 제37조 제36조",
    "사전 위생교육 이수 의무": "식품위생교육 영업 전 이수 의무 식품위생법 제41조",
    "위생교육 미이수 과태료": "식품위생교육 의무 과태료 식품위생법 제41조 제101조",
    "영업자 준수사항 위반 제재": "영업자 준수사항 위반 식품위생법 제44조",
    "영업정지 취소 사유": "영업허가취소 영업정지 식품위생법 제75조",
    "식품위생법 위반 과태료 벌칙": "과태료 벌칙 식품위생법 제97조 제101조",
    "위해식품 판매 금지": "위해식품 판매금지 식품위생법 제4조",
    "영업승계 신고 절차": "영업승계 지위승계 신고 식품위생법 제39조",
    "위반건축물 이행강제금": "위반건축물 이행강제금 건축법 제80조",
    "근로계약서 작성 교부 의무": "근로계약서 서면 명시 교부 의무 근로기준법 제17조",
    "근로계약서 미작성 벌금": "근로계약서 서면 명시 의무 벌금 근로기준법 제17조 제114조",
    "아르바이트 근로계약서 필수 사항": "단시간근로자 근로계약서 서면 명시 근로기준법 제17조",
    "주휴수당 지급 기준": "유급주휴일 주휴수당 근로기준법 제55조",
    "임금 체불 신고 방법": "임금 지급 체불 근로기준법 제43조",
    "4대보험 가입 의무 사업주": "국민연금 건강보험 고용보험 산업재해보상보험 근로기준법",
    "사업자등록증 발급 절차": "사업자등록 신청 발급 부가가치세법 제8조",
    "부가가치세 과세 대상 범위": "부가가치세 과세대상 재화 용역 부가가치세법 제1조 제4조",
    "동의 없이 수집 가능한 경우": "개인정보 수집 이용 동의 예외 개인정보보호법 제15조",
    "개인정보 제3자 제공 동의": "개인정보 제3자 제공 동의 개인정보보호법 제17조",
    "개인정보보호법 위반 과태료 벌칙": "과태료 벌칙 개인정보보호법 제71조 제75조",
    "음식점 편의시설 설치 의무 여부": "대상시설 편의시설 설치 의무 공중이용시설 장애인편의법 제7조",
    "그리스트랩 유류분리기 설치 의무": "유류분리기 오수처리시설 배수설비 하수도법 제34조",
    "배수설비 설치 기준": "배수설비 설치 기준 하수도법 제34조",
    "하수도법 위반 과태료 벌칙": "과태료 벌칙 하수도법 제80조",
    "불공정거래행위 금지 거래강제 공정거래법": "불공정거래행위 거래강제 공정거래법 제45조 제40조",
    "공정거래법 위반 과징금 벌칙": "과징금 벌칙 공정거래법 제55조",
    "공정거래위원회 신고 절차": "공정거래위원회 신고 절차 공정거래법 제80조",
    "부당 표시광고 금지": "부당한 표시광고 불공정거래행위 공정거래법 제45조",
}


async def main():
    with open(GOLDEN, encoding="utf-8-sig") as f:
        cases = list(csv.DictReader(f))
    print(f"[1] {len(cases)}개 쿼리 분석 시작...")

    retriever = LegalDocumentRetriever()
    fail_cases = []

    for case in cases:
        query = case["query"]
        search_query = QUERY_REWRITE.get(query, query)
        expected = set(filter(None, case["expected_articles"].split(" / ")))
        source_filter = getattr(retriever, case["source_filter"], None)

        docs = await retriever.search(search_query, top_k=10, source_filter=source_filter)

        # 반환 조문 추출
        returned = []
        for d in docs:
            art = d.get("metadata", {}).get("article", "")
            if art and art not in ("전문", "미분류", "N/A"):
                normalized = re.sub(r"_\d+$", "", art)
                score = d.get("metadata", {}).get("relevance", 0)
                snippet = d.get("content", "")[:150].replace("\n", " ").strip()
                if normalized not in [r["article"] for r in returned]:
                    returned.append({"article": normalized, "score": score, "snippet": snippet})

        ret_set = set(r["article"] for r in returned)
        tp = len(expected & ret_set)
        p = tp / len(ret_set) if ret_set else 0
        r = tp / len(expected) if expected else 0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0

        # F1 < 1.0인 사례만 수집
        if f1 >= 1.0:
            continue

        # 오답 분석
        correct_found = expected & ret_set
        correct_missed = sorted(expected - ret_set)
        wrong_returned = [r for r in returned if r["article"] not in expected]

        # top1이 오답인 경우
        top1_wrong = None
        if returned and returned[0]["article"] not in expected:
            top1_wrong = returned[0]

        # 혼동 쌍 (오답 vs 정답)
        confusion_pairs = []
        for wrong in wrong_returned[:3]:
            for correct in sorted(correct_missed)[:2]:
                confusion_pairs.append({
                    "wrong": wrong["article"],
                    "wrong_snippet": wrong["snippet"][:80],
                    "correct": correct,
                    "wrong_score": wrong["score"],
                })

        fail_cases.append({
            "query": query,
            "law": case["law"],
            "expected": sorted(expected),
            "returned": [r["article"] for r in returned[:5]],
            "f1": round(f1, 3),
            "correct_found": sorted(correct_found),
            "correct_missed": correct_missed,
            "top1_wrong": top1_wrong,
            "confusion_pairs": confusion_pairs,
        })

    # 저장
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(fail_cases, f, ensure_ascii=False, indent=2)

    # 통계
    f1_zero = [c for c in fail_cases if c["f1"] == 0]
    f1_partial = [c for c in fail_cases if 0 < c["f1"] < 1.0]
    top1_wrong_count = sum(1 for c in fail_cases if c["top1_wrong"])

    print(f"\n[2] 오답 분석 완료:")
    print(f"    전체: {len(cases)}개 쿼리")
    print(f"    F1=1.0 (완벽): {len(cases) - len(fail_cases)}개")
    print(f"    F1=0 (완전 실패): {len(f1_zero)}개")
    print(f"    0<F1<1 (부분 실패): {len(f1_partial)}개")
    print(f"    Top-1이 오답: {top1_wrong_count}개")
    print(f"    총 혼동 쌍: {sum(len(c['confusion_pairs']) for c in fail_cases)}개")
    print(f"\n    저장: {OUTPUT}")

    # Top 혼동 패턴
    confusion_freq = defaultdict(int)
    for c in fail_cases:
        for cp in c["confusion_pairs"]:
            confusion_freq[(c["law"], cp["wrong"], cp["correct"])] += 1

    print(f"\n[3] 자주 혼동되는 쌍 TOP 10:")
    for (law, wrong, correct), count in sorted(confusion_freq.items(), key=lambda x: -x[1])[:10]:
        print(f"    {count}회 [{law}] {wrong}(오답) vs {correct}(정답)")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
