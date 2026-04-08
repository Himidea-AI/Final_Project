"""
법률 PDF 파싱 스크립트 — raw/ PDF를 청킹하여 processed/chunks.json 으로 저장

실행 방법:
    cd backend
    python data/legal/parse_pdfs.py

출력:
    backend/data/legal/processed/chunks.json
"""
import json
import re
from pathlib import Path

import pdfplumber

RAW_DIR = Path(__file__).parent / "raw"
PROCESSED_DIR = Path(__file__).parent / "processed"

# 파싱 대상 PDF 목록 — (파일명, 카테고리, 분류 전략)
# 전략: "article" = 조문 단위 분리, "sliding" = 슬라이딩 윈도우
PDF_TARGETS: list[tuple[str, str, str]] = [
    (
        "가맹사업거래의 공정화에 관한 법률(법률)(제20712호)(20250121).pdf",
        "가맹사업법",
        "article",
    ),
    (
        "가맹사업거래의 공정화에 관한 법률 시행령(대통령령)(제36220호)(20260324).pdf",
        "가맹사업법_시행령",
        "article",
    ),
    (
        "서울시_2023_상가임대차_상담사례집_내지_전자책.pdf",
        "상가임대차",
        "sliding",
    ),
    (
        "서울특별시 마포구 지역상권 상생협력에 관한 조례.pdf",
        "마포구_조례",
        "article",
    ),
]

# 조문 단위 분리 시 단일 청크 최대 길이 (초과 시 추가 분할)
MAX_ARTICLE_CHUNK = 500
# 슬라이딩 윈도우 설정
SLIDING_CHUNK_SIZE = 500
SLIDING_OVERLAP = 100
# 최소 청크 길이 — 이보다 짧으면 노이즈로 제거
MIN_CHUNK_LENGTH = 20
# PDF 페이지 헤더/푸터에 자주 등장하는 노이즈 패턴
_HEADER_NOISE_PATTERNS = re.compile(
    r"법제처\s*\d*\s*국가법령정보센터|"
    r"^\s*\d+\s*$|"           # 페이지 번호만 있는 줄
    r"공정거래위원회$"
)


def extract_text(pdf_path: Path) -> str:
    """pdfplumber로 전체 텍스트 추출"""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
    return "\n".join(pages)


def split_by_article(text: str, category: str, source_name: str) -> list[dict]:
    """
    조문(제N조) 단위로 청킹.
    조문이 MAX_ARTICLE_CHUNK 초과 시 추가 분할.
    """
    # 조문 시작 패턴: "제1조", "제1조의2" 등
    pattern = re.compile(r"(?=제\d+조(?:의\d+)?[\s(])")
    parts = pattern.split(text)

    chunks = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 조문 번호 추출
        article_match = re.match(r"(제\d+조(?:의\d+)?)", part)
        article_num = article_match.group(1) if article_match else "미분류"
        chunk_id_base = f"{category}_{article_num}"

        if len(part) <= MAX_ARTICLE_CHUNK:
            chunk = _make_chunk(chunk_id_base, part, category, article_num, source_name)
            if chunk:
                chunks.append(chunk)
        else:
            # 길면 MAX_ARTICLE_CHUNK 단위로 추가 분할
            sub_parts = _split_long_text(part, MAX_ARTICLE_CHUNK, overlap=50)
            for idx, sub in enumerate(sub_parts):
                chunk = _make_chunk(f"{chunk_id_base}_{idx}", sub, category, article_num, source_name)
                if chunk:
                    chunks.append(chunk)

    return chunks


def split_by_sliding_window(text: str, category: str, source_name: str) -> list[dict]:
    """슬라이딩 윈도우 청킹 — 조문 구분이 없는 문서용"""
    parts = _split_long_text(text, SLIDING_CHUNK_SIZE, SLIDING_OVERLAP)
    return [
        chunk
        for idx, part in enumerate(parts)
        if (chunk := _make_chunk(f"{category}_{idx}", part, category, "N/A", source_name))
    ]


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """텍스트를 chunk_size 단위로 분할, overlap만큼 겹침"""
    parts = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        parts.append(text[start:end].strip())
        start += chunk_size - overlap
    return [p for p in parts if p]


def _clean_text(text: str) -> str:
    """페이지 헤더/푸터 노이즈 제거"""
    lines = text.splitlines()
    cleaned = [line for line in lines if not _HEADER_NOISE_PATTERNS.search(line)]
    return "\n".join(cleaned).strip()


def _make_chunk(chunk_id: str, text: str, category: str, article: str, source: str) -> dict | None:
    """청크 생성 — 노이즈 제거 후 MIN_CHUNK_LENGTH 미만이면 None 반환"""
    cleaned = _clean_text(text)
    if len(cleaned) < MIN_CHUNK_LENGTH:
        return None
    return {
        "id": chunk_id,
        "text": cleaned,
        "metadata": {
            "source": source,
            "category": category,
            "article": article,
        },
    }


def parse_all() -> list[dict]:
    all_chunks: list[dict] = []

    for filename, category, strategy in PDF_TARGETS:
        pdf_path = RAW_DIR / filename
        if not pdf_path.exists():
            print(f"[SKIP] 파일 없음: {filename}")
            continue

        print(f"[PARSE] {filename}")
        text = extract_text(pdf_path)

        if strategy == "article":
            chunks = split_by_article(text, category, filename)
        else:
            chunks = split_by_sliding_window(text, category, filename)

        # 전체 순번을 ID에 추가해 중복 방지 (같은 조문 번호가 여러 번 나타날 수 있음)
        global_offset = len(all_chunks)
        for i, chunk in enumerate(chunks):
            chunk["id"] = f"{chunk['id']}__g{global_offset + i}"

        print(f"  → {len(chunks)}개 청크 생성")
        all_chunks.extend(chunks)

    return all_chunks


if __name__ == "__main__":
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    chunks = parse_all()

    output_path = PROCESSED_DIR / "chunks.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"\n완료: 총 {len(chunks)}개 청크 → {output_path}")
