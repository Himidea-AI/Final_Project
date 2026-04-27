"""
법률 전문가 검수용 Golden Set 확장 시트 생성

F1 < 1.0인 쿼리에 대해 top_k=10 검색 결과를 뽑아서
전문가가 is_legal_match를 마킹할 수 있는 CSV 생성.

출력: docs/team/legal_review_pending_v1.csv
"""
import asyncio
import csv
import re
import selectors
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.chains.retriever import LegalDocumentRetriever

GOLDEN = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "golden_set_500_v2.csv"
OUTPUT = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "legal_review_pending_v1.csv"

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

    retriever = LegalDocumentRetriever()
    rows = []
    query_id = 0

    print(f"[1] {len(cases)}개 쿼리 검색 (top_k=10)...")

    for case in cases:
        query = case["query"]
        search_query = QUERY_REWRITE.get(query, query)
        expected = set(filter(None, case["expected_articles"].split(" / ")))
        source_filter = getattr(retriever, case["source_filter"], None)

        docs = await retriever.search(search_query, top_k=10, source_filter=source_filter)

        # F1 계산
        returned_arts = set()
        for d in docs:
            art = re.sub(r"_\d+$", "", d.get("metadata", {}).get("article", ""))
            if art and art not in ("전문", "미분류", "N/A"):
                returned_arts.add(art)
        ret5 = set(list(returned_arts)[:5])
        tp = len(expected & ret5)
        p = tp / len(ret5) if ret5 else 0
        r = tp / len(expected) if expected else 0
        f1 = 2 * p * r / (p + r) if (p + r) else 0.0

        # F1 < 1.0인 것만
        if f1 >= 1.0:
            continue

        query_id += 1
        seen = set()
        for rank, d in enumerate(docs, 1):
            art = re.sub(r"_\d+$", "", d.get("metadata", {}).get("article", ""))
            if not art or art in ("전문", "미분류", "N/A") or art in seen:
                continue
            seen.add(art)

            content = d.get("content", "")[:200].replace("\n", " ").strip()
            score = d.get("metadata", {}).get("relevance", 0)
            is_current_gt = "1" if art in expected else ""

            # 조문 제목 추출
            title_match = re.search(r"(제\d+조(?:의\d+)?)\s*[\(（]([^)）]+)[\)）]", content)
            article_title = f"{title_match.group(1)}({title_match.group(2)})" if title_match else art

            rows.append({
                "query_id": query_id,
                "law": case["law"],
                "user_query": query,
                "current_gt": " / ".join(sorted(expected)),
                "current_f1": f"{f1:.3f}",
                "candidate_rank": rank,
                "candidate_article": art,
                "candidate_title": article_title,
                "candidate_text": content,
                "relevance_score": f"{score:.3f}" if isinstance(score, float) else str(score),
                "is_current_gt": is_current_gt,
                "is_legal_match": "",
                "legal_reason": "",
            })

    # 저장
    fieldnames = [
        "query_id", "law", "user_query", "current_gt", "current_f1",
        "candidate_rank", "candidate_article", "candidate_title", "candidate_text",
        "relevance_score", "is_current_gt", "is_legal_match", "legal_reason",
    ]
    with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # 통계
    total_queries = len(set(r["query_id"] for r in rows))
    already_gt = sum(1 for r in rows if r["is_current_gt"] == "1")
    pending = sum(1 for r in rows if r["is_current_gt"] != "1")

    print(f"\n[2] 검수 시트 생성 완료:")
    print(f"    총 쿼리: {total_queries}개 (F1<1.0)")
    print(f"    총 행: {len(rows)}개")
    print(f"    이미 정답: {already_gt}개 (is_current_gt=1)")
    print(f"    검수 필요: {pending}개 (is_legal_match 마킹 필요)")
    print(f"\n    저장: {OUTPUT}")
    print(f"\n[3] 검수 가이드:")
    print(f"    - is_legal_match=1: 변호사/노무사가 상담 시 근거로 제시할 만한 조항")
    print(f"    - is_legal_match=0: 질문과 무관하거나 다른 주제의 조항")
    print(f"    - legal_reason: 정답 인정 사유 (본법-시행령 쌍, 준용 조항, 벌칙 규정 등)")
    print(f"\n    중점 검수:")
    print(f"    1. 본법 + 시행령 쌍")
    print(f"    2. 준용 조항 (~를 준용한다)")
    print(f"    3. 벌칙/과태료 조항")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
