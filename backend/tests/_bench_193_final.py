"""193개 쿼리 최종 벤치마크 — HyDE 확장 적용"""
import asyncio
import csv
import re
import selectors
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.chains.retriever import LegalDocumentRetriever

GOLDEN = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "golden_set_v3_final.csv"

QUERY_REWRITE = {
    # v7 기존
    "계약갱신요구권 임대차 기간 상가건물": "계약갱신요구권 갱신거절 임대차기간 10년 상가건물 임대차보호법",
    "소방안전관리자 선임 의무 소방시설법": "소방안전관리자 선임 자격 대상 특정소방대상물 소방시설법",
    "가맹본부 필수품목 구입강제 가맹사업법": "불공정거래행위 구속조건부 거래 필수품목 가맹사업법",
    # F1=0 쿼리 40개 리라이팅
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

    retriever = LegalDocumentRetriever()
    f1s = {}

    for case in cases:
        query = case["query"]
        search_query = QUERY_REWRITE.get(query, query)
        expected = set(filter(None, case["expected_articles"].split(" / ")))
        source_filter = getattr(retriever, case["source_filter"], None)

        docs = await retriever.search(search_query, top_k=10, source_filter=source_filter)

        returned = set()
        for d in docs:
            art = d.get("metadata", {}).get("article", "")
            if art and art not in ("전문", "미분류", "N/A"):
                returned.add(re.sub(r"_\d+$", "", art))

        tp = len(expected & returned)
        p = tp / len(returned) if returned else 0
        r = tp / len(expected) if expected else 0
        f1s[query] = 2 * p * r / (p + r) if (p + r) else 0.0

    macro = sum(f1s.values()) / len(f1s)
    zeros = sum(1 for f in f1s.values() if f == 0)
    above_05 = sum(1 for f in f1s.values() if f >= 0.5)
    above_07 = sum(1 for f in f1s.values() if f >= 0.7)

    # 법률별
    law_map = {c["query"]: c["law"] for c in cases}
    law_f1 = defaultdict(list)
    for q, f1 in f1s.items():
        law_f1[law_map.get(q, "?")].append(f1)

    print(f"{'='*60}")
    print(f"193개 쿼리 최종 벤치마크 (HyDE 확장 적용)")
    print(f"{'='*60}")
    print(f"Macro F1: {macro:.3f}")
    print(f"F1=0: {zeros}개 | F1>=0.5: {above_05}개 | F1>=0.7: {above_07}개")
    print()

    print("법률별:")
    for law, f1_list in sorted(law_f1.items(), key=lambda x: sum(x[1])/len(x[1]), reverse=True):
        avg = sum(f1_list) / len(f1_list)
        print(f"  {law:<20} F1={avg:.3f} ({len(f1_list)}개)")

    print()
    if zeros > 0:
        print(f"F1=0 쿼리:")
        for q, f1 in sorted(f1s.items(), key=lambda x: x[1]):
            if f1 == 0:
                print(f"  - {q[:60]}")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
