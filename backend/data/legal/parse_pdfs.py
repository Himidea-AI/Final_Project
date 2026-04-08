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
    (
        "상가건물 임대차보호법(법률)(제21065호)(20260102).pdf",
        "상가임대차보호법",
        "article",
    ),
    (
        "상가건물 임대차보호법 시행령(대통령령)(제35947호)(20260102).pdf",
        "상가임대차보호법_시행령",
        "article",
    ),
    (
        "[한국외식업중앙회] 2026 위생교육교재 (표지 포함).pdf",
        "위생교육교재",
        "sliding",
    ),
    (
        "210226_ 「다중이용업소의 안전관리에 관한 특별법」업무처리 지침.pdf",
        "다중이용업소_업무처리지침",
        "sliding",
    ),
    (
        "제4차(2024~2028) 다중이용업소 안전관리 기본계획(전문).pdf",
        "다중이용업소_안전관리기본계획",
        "sliding",
    ),
    (
        "식품위생법 시행규칙(총리령)(제02077호)(20260301).pdf",
        "식품위생법_시행규칙",
        "article",
    ),
    # ── 추가 법령 (창업 필수) ──────────────────────────────────────────
    (
        "건축법(법률)(20250101).pdf",
        "건축법",
        "article",
    ),
    (
        "소방시설 설치 및 관리에 관한 법률(법률)(20250101).pdf",
        "소방시설법",
        "article",
    ),
    (
        "근로기준법(법률)(20250101).pdf",
        "근로기준법",
        "article",
    ),
    # ── 추가 법령 (창업 필수 2차) ─────────────────────────────────────────
    (
        "식품위생법(법률)(제21065호)(20251001).pdf",
        "식품위생법",
        "article",
    ),
    (
        "최저임금법(법률)(제17326호)(20200526).pdf",
        "최저임금법",
        "article",
    ),
    (
        "부가가치세법(법률)(제21065호)(20260102).pdf",
        "부가가치세법",
        "article",
    ),
    (
        "개인정보 보호법(법률)(제20897호)(20251002).pdf",
        "개인정보보호법",
        "article",
    ),
    (
        "장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(법률)(제20594호)(20251221).pdf",
        "장애인편의증진법",
        "article",
    ),
    (
        "독점규제 및 공정거래에 관한 법률(법률)(제21066호)(20251001).pdf",
        "공정거래법",
        "article",
    ),
    (
        "하수도법(법률)(제21065호)(20251001).pdf",
        "하수도법",
        "article",
    ),
    (
        "물환경보전법(법률)(제21368호)(20260219).pdf",
        "물환경보전법",
        "article",
    ),
    (
        "주세법(법률)(제20618호)(20250101).pdf",
        "주세법",
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
    r"^\s*\d+\s*$|"  # 페이지 번호만 있는 줄
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
        # source는 확장자 제거한 stem — retriever.py의 *_SOURCES 상수와 일치
        source_name = Path(filename).stem

        if strategy == "article":
            chunks = split_by_article(text, category, source_name)
        else:
            chunks = split_by_sliding_window(text, category, source_name)

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
