"""
법률 PDF 파싱 스크립트 — A2 담당

사용법:
    python data/legal/parse_pdfs.py

동작 흐름:
    1. backend/data/legal/raw/ 에 있는 PDF 파일들을 읽음
    2. pdfplumber로 텍스트 추출
    3. "제N조" 패턴으로 조문 단위 청킹
    4. backend/data/legal/processed/chunks.json 저장
    5. 이후 retriever.ingest_from_json()으로 ChromaDB에 적재

PDF 파일 준비:
    - backend/data/legal/raw/가맹사업법.pdf
    - backend/data/legal/raw/상가임대차보호법.pdf
    (파일명에 법률 이름이 포함되어 있으면 자동으로 source 메타데이터에 반영됨)
"""

import json
import re
import sys
from pathlib import Path

import pdfplumber

# ── 경로 설정 ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # Final_Project/
RAW_DIR = PROJECT_ROOT / "backend" / "data" / "legal" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "backend" / "data" / "legal" / "processed"
OUTPUT_PATH = PROCESSED_DIR / "chunks.json"

# 조문 하나가 이 글자 수를 초과하면 슬라이딩 윈도우로 추가 분할
# 가맹사업법 조문은 보통 300~800자, 드물게 1500자 이상인 조문도 있음
MAX_CHARS = 800
OVERLAP_CHARS = 100  # 분할된 청크 간 중복 글자 수 (문맥 연결용)

# 조문 시작 패턴: "제1조", "제1조의2", "제12조" 등
ARTICLE_PATTERN = re.compile(r"(제\d+조(?:의\d+)?)")


def extract_text_from_pdf(pdf_path: Path) -> str:
    """PDF에서 전체 텍스트 추출."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n".join(pages)


def _clean_text(text: str) -> str:
    """불필요한 공백/개행 정리."""
    # 연속 공백 → 단일 공백
    text = re.sub(r"[ \t]+", " ", text)
    # 3개 이상 연속 개행 → 2개로 압축
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_long_chunk(text: str, max_chars: int, overlap: int) -> list[str]:
    """
    max_chars를 초과하는 텍스트를 슬라이딩 윈도우로 분할.

    예) max=800, overlap=100이면:
        [0:800], [700:1500], [1400:2200] ...
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def parse_articles(raw_text: str, source_name: str, start_seq: int = 0) -> list[dict]:
    """
    조문 단위로 텍스트를 분할하여 청크 리스트 반환.

    Args:
        raw_text: PDF에서 추출한 전체 텍스트
        source_name: 법률 이름 (메타데이터 source 필드)
        start_seq: 전역 시퀀스 시작값 (동일 문서 내 중복 조문번호 방지)

    Returns:
        [{"id": str, "text": str, "metadata": dict}, ...]
    """
    text = _clean_text(raw_text)

    # "제N조" 위치를 기준으로 분할
    splits = ARTICLE_PATTERN.split(text)
    # split() 결과: [전문, "제1조", 내용1, "제2조", 내용2, ...]
    # 인덱스: 0=전문, 1=조번호, 2=내용, 3=조번호, 4=내용 ...

    chunks: list[dict] = []
    seq = start_seq  # 전역 시퀀스 — 파일 내 중복 조문번호가 있어도 ID 충돌 방지

    # 전문(제1조 이전 텍스트)이 있으면 별도 청크로 추가
    preamble = splits[0].strip()
    if preamble:
        chunks.append(
            {
                "id": f"{source_name}_preamble_{seq}",
                "text": preamble,
                "metadata": {"source": source_name, "article": "전문", "law_article": "전문", "title": "전문"},
            }
        )
        seq += 1

    # 조번호 + 내용 쌍을 순회
    i = 1
    while i + 1 < len(splits):
        article_num = splits[i].strip()  # "제N조"
        article_body = splits[i + 1].strip()  # 해당 조문 내용
        i += 2

        if not article_body:
            continue

        # 조문 제목 추출: "제1조(목적)" → title="목적"
        title_match = re.match(r"^\(([^)]+)\)", article_body)
        title = title_match.group(1) if title_match else ""

        full_text = f"{article_num} {article_body}"

        # 긴 조문은 슬라이딩 윈도우로 추가 분할
        sub_chunks = _split_long_chunk(full_text, MAX_CHARS, OVERLAP_CHARS)
        for idx, sub in enumerate(sub_chunks):
            chunks.append(
                {
                    "id": f"{source_name}_{article_num}_{seq}_{idx}",
                    "text": sub,
                    "metadata": {
                        "source": source_name,
                        "article": article_num,
                        "law_article": article_num,
                        "title": title,
                    },
                }
            )
        seq += 1

    return chunks


def _infer_source_name(pdf_path: Path) -> str:
    """파일명에서 법률 이름 추출. 예) '가맹사업법.pdf' → '가맹사업법'"""
    return pdf_path.stem  # 확장자 제거


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(RAW_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"[오류] {RAW_DIR} 에 PDF 파일이 없습니다.")
        print("  → data/legal/raw/ 에 가맹사업법.pdf, 상가임대차보호법.pdf 를 넣으세요.")
        sys.exit(1)

    all_chunks: list[dict] = []
    global_seq = 0  # 파일 간 시퀀스 연속 — 전체에서 ID 중복 완전 차단

    for pdf_path in pdf_files:
        source_name = _infer_source_name(pdf_path)
        print(f"[파싱 중] {pdf_path.name} ...")

        raw_text = extract_text_from_pdf(pdf_path)
        chunks = parse_articles(raw_text, source_name, start_seq=global_seq)
        global_seq += len(chunks)

        print(f"  → {len(chunks)}개 청크 생성")
        all_chunks.extend(chunks)

    OUTPUT_PATH.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[완료] {len(all_chunks)}개 청크 저장 → {OUTPUT_PATH}")
    print("다음 단계: retriever.ingest_from_json() 으로 ChromaDB에 적재하세요.")


if __name__ == "__main__":
    main()
