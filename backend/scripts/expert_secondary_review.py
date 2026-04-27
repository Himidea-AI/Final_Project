"""
2차 정밀 재검토 — 146건 '0' 판정 중 법률 전문가 3대 원칙으로 재발굴

원칙 1: 수직적 통합 (본법→시행령/시행규칙 번호 매칭)
원칙 2: 제재 연결 (금지규정→벌칙/과태료/영업정지)
원칙 3: 절차적 완결성 (신청→서식/서류/기간)
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INPUT = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "legal_review_final_v1.csv"
OUTPUT = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "legal_review_final_v2.csv"
GOLDEN = Path(__file__).resolve().parent.parent.parent / "docs" / "team" / "golden_set_v3_final.csv"
CHUNKS = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "chunks.json"

# 법률별 벌칙/제재 조문 매핑
SANCTION_ARTICLES = {
    "가맹사업법": {"제41조", "제43조", "제33조", "제34조", "제35조"},
    "식품위생법": {"제75조", "제76조", "제77조", "제78조", "제83조", "제97조", "제101조"},
    "건축법": {"제80조", "제80조의2", "제106조", "제110조", "제111조"},
    "소방시설법": {"제57조", "제58조", "제59조", "제60조"},
    "근로기준법": {"제107조", "제108조", "제109조", "제110조", "제114조", "제116조"},
    "부가가치세법": {"제60조"},
    "개인정보보호법": {"제71조", "제72조", "제73조", "제74조", "제75조"},
    "장애인편의법": {"제25조", "제26조"},
    "하수도법": {"제78조", "제79조", "제80조", "제81조"},
    "공정거래법": {"제55조", "제89조", "제124조", "제125조", "제126조", "제127조", "제128조", "제129조"},
    "상가임대차보호법": set(),
}

# 절차/서식 관련 조문 패턴
PROCEDURE_KEYWORDS = ["신청", "서식", "제출", "서류", "절차", "기간", "방법", "양식", "신고서", "허가서", "등록서"]

# 준용 규정 탐지
JUNCHYONG_PATTERN = re.compile(r"준용|따른다|적용한다")


def check_vertical_integration(row, chunks_by_source):
    """원칙 1: 본법-시행령 번호 매칭"""
    current_gt = set(row.get("current_gt", "").split(" / "))
    candidate = row["candidate_article"]
    cand_num = re.search(r"제(\d+)조", candidate)
    if not cand_num:
        return False

    for gt_art in current_gt:
        gt_num = re.search(r"제(\d+)조", gt_art)
        if gt_num and gt_num.group(1) == cand_num.group(1) and gt_art != candidate:
            return True
    return False


def check_sanction_matching(row):
    """원칙 2: 금지규정→벌칙/과태료 연결"""
    law = row["law"]
    candidate = row["candidate_article"]
    candidate_text = row.get("candidate_text", "").lower()

    # 법률별 벌칙 조문에 해당하면 1
    if law in SANCTION_ARTICLES and candidate in SANCTION_ARTICLES[law]:
        return True

    # 조문 텍스트에 벌칙 키워드
    penalty_kw = ["벌금", "징역", "과태료", "과징금", "영업정지", "허가취소", "영업취소", "이행강제금"]
    for kw in penalty_kw:
        if kw in candidate_text:
            return True

    return False


def check_procedural_completion(row):
    """원칙 3: 절차적 완결성"""
    query = row["user_query"].lower()
    candidate_text = row.get("candidate_text", "").lower()

    # 쿼리가 절차를 묻는 경우
    query_procedure = any(kw in query for kw in ["절차", "방법", "서류", "신고", "신청", "등록", "허가"])
    if not query_procedure:
        return False

    # 후보가 세부 절차를 규정하는 경우
    cand_procedure = any(kw in candidate_text for kw in PROCEDURE_KEYWORDS)
    return cand_procedure


def check_junchyong(row, chunks_data):
    """준용 규정 검토"""
    candidate_text = row.get("candidate_text", "")
    if JUNCHYONG_PATTERN.search(candidate_text):
        return True
    return False


def main():
    with open(INPUT, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

    # chunks 로드 (준용 규정 검토용)
    with open(CHUNKS, encoding="utf-8") as f:
        chunks = json.load(f)

    # 0으로 판정된 RECHECK 항목만 재검토
    targets = [
        (i, r) for i, r in enumerate(rows)
        if r.get("legal_reason", "").startswith("RECHECK->0")
    ]

    print(f"[1] 재검토 대상: {len(targets)}건")

    upgraded = 0
    reasons_count = {"수직적 통합": 0, "제재 연결": 0, "절차적 완결성": 0, "준용 규정": 0}

    for idx, row in targets:
        reason = None

        # 원칙 1: 수직적 통합
        if check_vertical_integration(row, None):
            reason = "수직적 통합 (본법-시행령 번호 매칭)"
            reasons_count["수직적 통합"] += 1

        # 원칙 2: 제재 연결
        elif check_sanction_matching(row):
            reason = "제재 연결 (벌칙/과태료/영업정지)"
            reasons_count["제재 연결"] += 1

        # 원칙 3: 절차적 완결성
        elif check_procedural_completion(row):
            reason = "절차적 완결성 (세부 시행규칙)"
            reasons_count["절차적 완결성"] += 1

        # 준용 규정
        elif check_junchyong(row, chunks):
            reason = "준용 규정 연결"
            reasons_count["준용 규정"] += 1

        if reason:
            rows[idx]["is_legal_match"] = "1"
            rows[idx]["legal_reason"] = reason
            upgraded += 1

    print(f"    0→1 변경: {upgraded}건")
    for r, c in reasons_count.items():
        if c > 0:
            print(f"      {r}: {c}건")

    # 저장
    with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n    저장: {OUTPUT}")

    # Golden set 업데이트
    from collections import defaultdict

    with open(GOLDEN, encoding="utf-8-sig") as f:
        golden_rows = list(csv.DictReader(f))

    query_expected = defaultdict(set)
    query_meta = {}
    for r in golden_rows:
        query_meta[r["query"]] = {"law": r["law"], "filter": r["source_filter"]}
        for art in r["expected_articles"].split(" / "):
            query_expected[r["query"]].add(art.strip())

    new_added = 0
    for r in rows:
        if r.get("is_legal_match", "").strip() == "1" and r.get("legal_reason", "").startswith(("수직", "제재", "절차", "준용")):
            q = r["user_query"]
            art = r.get("candidate_article", "").strip()
            if art and q in query_expected and art not in query_expected[q]:
                query_expected[q].add(art)
                new_added += 1

    print(f"\n[2] Golden set: +{new_added}개 정답 추가")

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

    total = sum(len(v) for v in query_expected.values())
    print(f"    총 정답: {total}개 (평균 {total / len(query_expected):.1f}개/쿼리)")


if __name__ == "__main__":
    main()
