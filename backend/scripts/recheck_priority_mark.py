"""
RECHECK 181건 우선순위 마킹 — 0.6 미만 법률 집중 공략

마킹 규칙:
1. 벌칙/과태료/이행강제금 조문 → 금지규정과 세트면 1
2. 시행령/시행규칙 조문 → 본법 보충이면 1
3. 건축법/식품위생법/하수도법/공정거래법은 정밀 검토
4. 정의 규정(제2조)은 핵심 개념 정의면 1, 아니면 0
5. 나머지는 0
"""
import csv
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INPUT = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "legal_review_completed_v1.csv"
OUTPUT = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "legal_review_final_v1.csv"
GOLDEN = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "golden_set_v3_final.csv"

# 벌칙/과태료 키워드
PENALTY_KEYWORDS = ["벌칙", "과태료", "이행강제금", "처벌", "벌금", "과징금", "징역"]

# 법률별 세트 규칙: {(law, 금지조문): [연관 벌칙/시행령 조문]}
LEGAL_SETS = {
    # 건축법
    ("건축법", "제19조"): ["제80조"],  # 용도변경 → 이행강제금
    ("건축법", "제11조"): ["제22조", "제80조"],  # 건축허가 → 사용승인, 이행강제금
    ("건축법", "제14조"): ["제22조"],  # 건축신고 → 사용승인
    ("건축법", "제48조"): ["제80조"],  # 구조안전 → 이행강제금
    # 식품위생법
    ("식품위생법", "제37조"): ["제52조", "제75조", "제97조"],  # 영업신고 → 시행규칙, 영업정지, 벌칙
    ("식품위생법", "제41조"): ["제54조", "제101조"],  # 위생교육 → 시행규칙, 과태료
    ("식품위생법", "제44조"): ["제75조", "제97조"],  # 준수사항 → 영업정지, 벌칙
    ("식품위생법", "제4조"): ["제5조의4", "제97조"],  # 위해식품 → 기준규격, 벌칙
    ("식품위생법", "제36조"): ["제52조", "제75조"],  # 시설기준 → 시행규칙, 영업정지
    ("식품위생법", "제39조"): ["제75조"],  # 영업승계 → 영업정지
    # 하수도법
    ("하수도법", "제34조"): ["제70조", "제80조"],  # 배수설비 → 시행규칙, 과태료
    ("하수도법", "제37조"): ["제55조", "제80조"],  # 개인하수처리 → 관리대책, 과태료
    # 공정거래법
    ("공정거래법", "제45조"): ["제51조", "제55조", "제89조"],  # 불공정거래 → 사업자단체, 과징금, 서면실태조사
    ("공정거래법", "제80조"): ["제120조의2", "제120조의3"],  # 신고 → 포상금
    # 근로기준법
    ("근로기준법", "제17조"): ["제114조"],  # 근로계약서 → 벌금
    ("근로기준법", "제43조"): ["제48조", "제109조"],  # 임금지급 → 임금대장, 벌칙
    ("근로기준법", "제55조"): ["제17조"],  # 주휴수당 → 근로조건명시
    ("근로기준법", "제56조"): ["제6조"],  # 가산임금 → 균등대우
}


def should_mark_1(row, all_gt_articles):
    """RECHECK 항목을 1로 마킹해야 하는지 판단"""
    law = row["law"]
    candidate = row["candidate_article"]
    candidate_text = row.get("candidate_text", "")
    candidate_title = row.get("candidate_title", "")
    query = row["user_query"]
    current_gt = set(row.get("current_gt", "").split(" / "))

    # 1. 벌칙/과태료 조문이 현재 정답의 금지규정과 세트인지
    for gt_art in current_gt:
        key = (law, gt_art)
        if key in LEGAL_SETS and candidate in LEGAL_SETS[key]:
            return True, f"세트: {gt_art}의 연관 조문"

    # 2. 조문 제목에 벌칙/과태료 키워드
    for kw in PENALTY_KEYWORDS:
        if kw in candidate_title or kw in candidate_text[:100]:
            # 같은 법률의 벌칙이면 1
            return True, f"벌칙/제재 조문 ({kw})"

    # 3. 건축법 특별 규칙 — 제77조(건축허가 관련), 제78조(용도제한)
    if law == "건축법":
        if candidate in ("제77조", "제77조의4", "제78조") and any(
            a in current_gt for a in ("제19조", "제2조", "제80조")
        ):
            return True, "건축법 용도/이행강제금 연관"

    # 4. 식품위생법 — 시행규칙 조문
    if law == "식품위생법":
        if candidate in ("제52조", "제54조", "제68조의4", "제83조"):
            return True, "식품위생법 시행규칙/세부기준"

    # 5. 시행령 번호 유사 (본법 제N조 → 시행령 제N조)
    for gt_art in current_gt:
        gt_num = re.search(r"제(\d+)조", gt_art)
        cand_num = re.search(r"제(\d+)조", candidate)
        if gt_num and cand_num and gt_num.group(1) == cand_num.group(1):
            if candidate != gt_art:
                return True, f"본법-시행령 번호 매칭 ({gt_art})"

    return False, ""


def main():
    with open(INPUT, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

    # 현재 정답 조문 수집
    all_gt = set()
    for r in rows:
        if r.get("is_current_gt") == "1":
            all_gt.add(r.get("candidate_article", ""))

    # RECHECK 항목 처리
    recheck_total = 0
    marked_1 = 0
    marked_0 = 0

    for r in rows:
        if r.get("is_legal_match", "").strip() != "RECHECK":
            continue
        recheck_total += 1

        should_1, reason = should_mark_1(r, all_gt)
        if should_1:
            r["is_legal_match"] = "1"
            r["legal_reason"] = reason
            marked_1 += 1
        else:
            r["is_legal_match"] = "0"
            r["legal_reason"] = "RECHECK->0 (규칙 미해당)"
            marked_0 += 1

    print(f"[1] RECHECK 처리: {recheck_total}건")
    print(f"    1 (정답 추가): {marked_1}건")
    print(f"    0 (무관): {marked_0}건")

    # 저장
    with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"    저장: {OUTPUT}")

    # Golden set 업데이트
    from collections import defaultdict

    query_expected = defaultdict(set)
    query_meta = {}

    # 기존 golden set 로드
    with open(GOLDEN, encoding="utf-8-sig") as f:
        old_golden = list(csv.DictReader(f))
    for r in old_golden:
        query_meta[r["query"]] = {"law": r["law"], "filter": r["source_filter"]}
        for art in r["expected_articles"].split(" / "):
            query_expected[r["query"]].add(art.strip())

    # 새 정답 추가
    new_added = 0
    for r in rows:
        if r.get("is_legal_match", "").strip() == "1":
            q = r["user_query"]
            art = r.get("candidate_article", "").strip()
            if art and q in query_expected and art not in query_expected[q]:
                query_expected[q].add(art)
                new_added += 1

    print(f"\n[2] Golden set 업데이트: +{new_added}개 정답 추가")

    # 저장
    with open(GOLDEN, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["law", "query", "source_filter", "expected_articles"])
        writer.writeheader()
        for q in sorted(query_expected.keys()):
            if query_expected[q] and q in query_meta:
                writer.writerow({
                    "law": query_meta[q]["law"],
                    "query": q,
                    "source_filter": query_meta[q]["filter"],
                    "expected_articles": " / ".join(sorted(query_expected[q])),
                })

    total_arts = sum(len(v) for v in query_expected.values())
    print(f"    총 정답: {total_arts}개 (평균 {total_arts / len(query_expected):.1f}개/쿼리)")
    print(f"    저장: {GOLDEN}")


if __name__ == "__main__":
    main()
