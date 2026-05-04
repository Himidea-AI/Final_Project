"""
법률 PDF 파싱 스크립트 — raw/ PDF를 청킹하여 processed/chunks.json 으로 저장

실행 방법:
    cd backend
    python data/legal/parse_pdfs.py

출력:
    backend/data/legal/processed/chunks.json
"""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

RAW_DIR = Path(__file__).parent / "raw"
PROCESSED_DIR = Path(__file__).parent / "processed"

# 파싱 대상 PDF 목록 — (파일명, 카테고리, 분류 전략)
# 전략: "article" = 조문 단위 분리, "sliding" = 슬라이딩 윈도우
#
# 주: 법률 본문은 build_law_chunks.py 가 law_legislations.body_text(law.go.kr DRF API
#     lawService.do?type=JSON 으로 수집)에서 직접 청킹하여 chunks 에 합쳐진다.
#     따라서 아래 "법률(법률)(제…호)" 형식의 PDF 는 동일 본문을 중복으로 다루지 않도록
#     PDF_TARGETS 에서 제외한다 (raw/ 에 PDF 가 없으므로 SKIP 노이즈 방지 목적도 겸함).
#     law.go.kr 은 PDF 다운로드 endpoint 를 OPEN API 신청자에게만 열어주며, 현 OC 에는
#     PDF type 권한이 없어 자동 다운로드 불가 — 미래에 PDF 본을 확보하면 entry 를 복원.
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
    # ── 아래는 raw/ 에 PDF 가 없어 일시 비활성화 — DB body_text 로 대체 처리됨 ──
    # PDF 본을 raw/ 에 직접 넣은 뒤 entry 를 복원하면 그대로 동작.
    # (
    #     "상가건물 임대차보호법(법률)(제21065호)(20260102).pdf",
    #     "상가임대차보호법",
    #     "article",
    # ),
    # (
    #     "상가건물 임대차보호법 시행령(대통령령)(제35947호)(20260102).pdf",
    #     "상가임대차보호법_시행령",
    #     "article",
    # ),
    # (
    #     "식품위생법 시행규칙(총리령)(제02077호)(20260301).pdf",
    #     "식품위생법_시행규칙",
    #     "article",
    # ),
    # (
    #     "건축법(법률)(20250101).pdf",
    #     "건축법",
    #     "article",
    # ),
    # (
    #     "소방시설 설치 및 관리에 관한 법률(법률)(20250101).pdf",
    #     "소방시설법",
    #     "article",
    # ),
    # (
    #     "근로기준법(법률)(20250101).pdf",
    #     "근로기준법",
    #     "article",
    # ),
    # (
    #     "식품위생법(법률)(제21065호)(20251001).pdf",
    #     "식품위생법",
    #     "article",
    # ),
    # (
    #     "최저임금법(법률)(제17326호)(20200526).pdf",
    #     "최저임금법",
    #     "article",
    # ),
    # (
    #     "부가가치세법(법률)(제21065호)(20260102).pdf",
    #     "부가가치세법",
    #     "article",
    # ),
    # (
    #     "개인정보 보호법(법률)(제20897호)(20251002).pdf",
    #     "개인정보보호법",
    #     "article",
    # ),
    # (
    #     "장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(법률)(제20594호)(20251221).pdf",
    #     "장애인편의증진법",
    #     "article",
    # ),
    # (
    #     "독점규제 및 공정거래에 관한 법률(법률)(제21066호)(20251001).pdf",
    #     "공정거래법",
    #     "article",
    # ),
    # (
    #     "하수도법(법률)(제21065호)(20251001).pdf",
    #     "하수도법",
    #     "article",
    # ),
    # (
    #     "물환경보전법(법률)(제21368호)(20260219).pdf",
    #     "물환경보전법",
    #     "article",
    # ),
    # (
    #     "주세법(법률)(제20618호)(20250101).pdf",
    #     "주세법",
    #     "article",
    # ),
]

# 조문 단위 분리 시 단일 청크 최대 길이 (초과 시 추가 분할)
MAX_ARTICLE_CHUNK = 500
# 슬라이딩 윈도우 설정
SLIDING_CHUNK_SIZE = 500
SLIDING_OVERLAP = 100
# 최소 청크 길이 — 이보다 짧으면 노이즈로 제거
MIN_CHUNK_LENGTH = 20
# 라인 단위로 통째 제거할 노이즈 (페이지 헤더/푸터)
_LINE_NOISE_PATTERNS = re.compile(
    r"법제처\s*\d*\s*국가법령정보센터|"
    r"^\s*\d+\s*$|"  # 페이지 번호만 있는 줄
    r"공정거래위원회$|"
    r"^\s*\[부칙\][^\n]*$|"  # "[부칙]" 단독 마크
    r"조항\s+수정\s+조항"  # 파싱 산물
)
# 라인 안의 부분만 제거할 노이즈 (개정/시행일 stamp 등)
_INLINE_NOISE_PATTERNS = re.compile(
    r"\s*\[(?:개정|전문개정|타법개정|일부개정|본조신설|본조개정)"
    r"\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?"
    r"(?:\s*,\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?)*\]|"
    r"\s*\[시행일[:\s]*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?\]"
)
# 부칙 시행일 boilerplate — "제1조(시행일) 이 영은/법은 공포한 날부터 시행한다" 단독 짧은 청크는 제외
_SUPPLEMENTARY_BOILERPLATE = re.compile(
    r"^제1조\s*\(\s*시행일\s*\).*공포한\s*날.*시행한다",
    re.DOTALL,
)


def extract_text(pdf_path: Path) -> str:
    """pdfplumber로 전체 텍스트 추출 (lazy import — 단위 테스트가 PDF 의존성 없이 동작하도록)"""
    import pdfplumber

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

    # 타법 참조 필터 — 분리된 chunk 앞에 "법 ", "법률 " 등이 붙어있으면 타법 참조
    _OTHER_LAW_PREFIX = re.compile(r"(?:법|법률|시행령|시행규칙)\s*$")
    # 본문 내 조문 참조 감지 — 직전 part 가 조문 참조 연결 어미로 끝나면 현재 split 은
    # 본문 중간을 끊은 것으로 간주 (예: "...제5조, 제7조, " → "제8조 또는 제9조...").
    _IN_TEXT_REF_TAIL = re.compile(
        r"(?:,\s*|및\s*|또는\s*|에\s*따라\s*|에\s*따른\s*|에\s*해당하는\s*|"
        r"부터\s*|까지\s*|이내에서\s*|위반한\s*자는\s*)$"
    )
    # 진짜 조문 헤더는 "제N조(제목)" 또는 "제N조  " (공백 2+) 또는 "제N조  제목" 형태.
    # 본문 내 참조는 "제N조 및", "제N조,", "제N조 또는", "제N조 본문" 등 조사가 뒤따름.
    _ARTICLE_HEADER_HEAD = re.compile(r"^(제\d+조(?:의\d+)?)(?:\([^)]*\)|\s+\S+\s*\s+\S+|$)")
    # 강한 fragment 신호 — "제N조 본문/단서/또는/및/,/에서/제\d항" 직후 시작.
    _IN_TEXT_HEAD = re.compile(r"^제\d+조(?:의\d+)?\s*(?:본문|단서|또는|및|,|에서|제\d+항|또는\s+제)")

    chunks = []
    prev_part = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 조문 번호 추출
        article_match = re.match(r"(제\d+조(?:의\d+)?)", part)
        article_num = article_match.group(1) if article_match else "미분류"

        # 타법 참조 감지: 이전 chunk 끝이 "법 ", "법률 " 등이면 타법 조문 참조 → 버림
        if article_num != "미분류" and prev_part and _OTHER_LAW_PREFIX.search(prev_part):
            prev_part = part
            continue

        # 본문 내 조문 참조 fragment 감지: 두 신호 중 하나라도 강하면 fragment 로 간주 → drop.
        # (1) 직전 part 끝이 조문 참조 연결 어미 (예: "제7조, ", "또는 ") + 현재 part 의 헤더가
        #     진짜 조문 헤더 형태가 아님.
        # (2) 현재 part 가 "제N조 본문/단서/또는/및/," 같은 조문 참조 fragment 시그니처로 시작.
        # fragment 는 prev_part 본문 일부였다는 점은 인정 — 새 chunk 로 떼어내지 않고 합쳐서
        # 직전 chunk 에 흡수 (또는 단순 drop). 라벨 오염 방지가 우선.
        is_in_text_fragment = False
        if article_num != "미분류":
            head_is_real_header = bool(_ARTICLE_HEADER_HEAD.match(part))
            head_is_ref_fragment = bool(_IN_TEXT_HEAD.match(part))
            if head_is_ref_fragment:
                is_in_text_fragment = True
            elif prev_part and _IN_TEXT_REF_TAIL.search(prev_part) and not head_is_real_header:
                is_in_text_fragment = True

        if is_in_text_fragment:
            # fragment 는 라벨 없이 prev_part 의 일부로 취급 — 새 chunk 생성 X
            prev_part = prev_part + " " + part
            continue

        prev_part = part

        if len(part) <= MAX_ARTICLE_CHUNK:
            chunk = _make_chunk(part, category, article_num, source_name)
            if chunk:
                chunks.append(chunk)
        else:
            # 항(①②③) → 문장 → 고정길이 순으로 의미론적 분할
            # article_header로 조문 제목을 넘겨 하위 청크에 "[제N조]" 접두사 부여
            sub_parts = _split_article_semantic(part, MAX_ARTICLE_CHUNK, article_header=part)
            for sub in sub_parts:
                chunk = _make_chunk(sub, category, article_num, source_name)
                if chunk:
                    chunks.append(chunk)

    return chunks


def split_by_sliding_window(text: str, category: str, source_name: str) -> list[dict]:
    """슬라이딩 윈도우 청킹 — 조문 구분이 없는 문서용"""
    parts = _split_long_text(text, SLIDING_CHUNK_SIZE, SLIDING_OVERLAP)
    chunks = []
    for idx, part in enumerate(parts):
        # sliding window는 조문이 없으므로 article에 idx로 위치 정보 인코딩
        # → 같은 텍스트가 다른 위치에 나타나도 다른 chunk_id
        chunk = _make_chunk(part, category, f"slide_{idx}", source_name)
        if chunk:
            chunks.append(chunk)
    return chunks


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """텍스트를 chunk_size 단위로 분할, overlap만큼 겹침 (슬라이딩 윈도우 전용)"""
    parts = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        parts.append(text[start:end].strip())
        start += chunk_size - overlap
    return [p for p in parts if p]


# 항(①②③…⑳) 패턴 — 법률 조문의 의미 단위 구분자
_HANG_PATTERN = re.compile(r"(?=\s*[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳])")
# 문장 종결 패턴 — 한국어 법률 문서 기준
_SENTENCE_END = re.compile(
    r"(?<=[다음란함임됨음것임]\.)\s+|(?<=한다\.)\s+|(?<=된다\.)\s+|(?<=있다\.)\s+|(?<=없다\.)\s+|(?<=않는다\.)\s+|(?<=아니다\.)\s+"
)


def _split_by_hang(text: str) -> list[str]:
    """조문을 항(①②③) 단위로 분할. 항 마커가 없으면 원문 그대로 반환."""
    parts = _HANG_PATTERN.split(text)
    parts = [p.strip() for p in parts if p.strip()]
    return parts if len(parts) > 1 else [text]


def _split_by_sentence(text: str, max_len: int) -> list[str]:
    """텍스트를 문장 단위로 분할하여 max_len 이하 청크로 결합."""
    sentences = _SENTENCE_END.split(text)
    if len(sentences) <= 1:
        # 문장 분리 실패 시 마침표 기준 fallback
        sentences = [s.strip() + "." for s in text.split(".") if s.strip()]
    if not sentences:
        return [text]

    chunks = []
    current = ""
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if current and len(current) + len(sent) + 1 > max_len:
            chunks.append(current.strip())
            current = sent
        else:
            current = f"{current} {sent}".strip() if current else sent
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text]


def _split_article_semantic(text: str, max_len: int, article_header: str = "") -> list[str]:
    """
    조문 의미론적 분할: 항(①②③) → 문장 → 고정길이 (최후 수단)
    500자 고정 분할 대신 의미 단위를 보존하면서 max_len 이하로 분할.

    article_header: 조문 제목 (예: "제45조(불공정거래행위의 금지)")
        — 첫 청크 이후 분할된 청크에 "[제45조]" 접두사를 붙여 검색 매칭률 보장
    """
    # 조문 번호 추출 (예: "제45조(불공정거래행위...)" → "제45조")
    _art_num_match = re.match(r"(제\d+조(?:의\d+)?)", article_header) if article_header else None
    _art_prefix = f"[{_art_num_match.group(1)}] " if _art_num_match else ""

    # 1단계: 항 단위 분할
    hang_parts = _split_by_hang(text)

    result = []
    for i, part in enumerate(hang_parts):
        # 첫 청크는 조문 제목이 이미 포함되어 있으므로 접두사 불필요
        prefix = _art_prefix if i > 0 else ""
        prefixed = f"{prefix}{part}"

        if len(prefixed) <= max_len:
            result.append(prefixed)
        else:
            # 2단계: 문장 단위 분할
            sent_chunks = _split_by_sentence(part, max_len - len(prefix))
            for sc in sent_chunks:
                sc_prefixed = f"{prefix}{sc}"
                if len(sc_prefixed) <= max_len:
                    result.append(sc_prefixed)
                else:
                    # 3단계: 최후 수단 — 고정 길이 분할 (overlap 50자)
                    for piece in _split_long_text(sc, max_len - len(prefix), overlap=50):
                        result.append(f"{prefix}{piece}")

    return [r for r in result if r.strip()]


def _clean_text(text: str) -> str:
    """페이지 헤더/푸터 + intra-line 개정/시행일 stamp 제거"""
    lines = text.splitlines()
    kept: list[str] = []
    for line in lines:
        if _LINE_NOISE_PATTERNS.search(line):
            continue
        line = _INLINE_NOISE_PATTERNS.sub("", line)
        if line.strip():
            kept.append(line)
    return "\n".join(kept).strip()


def _normalize_for_hash(text: str) -> str:
    """공백 정규화 — 동일 의미 텍스트가 동일 ID 갖도록"""
    return re.sub(r"\s+", " ", text).strip()


def _make_chunk_id(source: str, article: str, text: str) -> str:
    """결정적 chunk_id — 같은 (source, article, 정규화 텍스트) → 같은 16자 hex"""
    raw = f"{source}|{article}|{_normalize_for_hash(text)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _make_chunk(text: str, category: str, article: str, source: str) -> dict | None:
    """청크 생성 — 노이즈 제거 후 None 반환 조건:
    1) 정제 후 길이 < MIN_CHUNK_LENGTH
    2) article == "미분류" (article 추출 실패 청크 = 전문/표지)
    3) 부칙 boilerplate ("제1조(시행일) ... 공포한 날부터 시행한다") + 짧은 청크
    """
    cleaned = _clean_text(text)
    if len(cleaned) < MIN_CHUNK_LENGTH:
        return None
    if article == "미분류":
        return None
    if len(cleaned) < 100 and _SUPPLEMENTARY_BOILERPLATE.match(cleaned):
        return None
    chunk_id = _make_chunk_id(source, article, cleaned)
    return {
        "id": chunk_id,
        "text": cleaned,
        "metadata": {
            "source": source,
            "category": category,
            "article": article,
            "chunk_id": chunk_id,
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

        print(f"  → {len(chunks)}개 청크 생성")
        all_chunks.extend(chunks)

    return all_chunks


def _dedupe_chunks(chunks: list[dict]) -> list[dict]:
    """중복 chunk_id 제거 (첫 번째 keep) + id-metadata 일치 검증.

    중복은 PDF에 동일 조항이 부칙/별표 등에 반복되거나 청킹이 같은 부분을
    두 번 캐치할 때 자연스럽게 발생. RAG 의미상 동일 청크이므로 한 개만 보존.
    """
    seen: set[str] = set()
    result: list[dict] = []
    for c in chunks:
        cid = c["id"]
        if c["metadata"].get("chunk_id") != cid:
            raise ValueError(
                f"id-metadata.chunk_id 불일치: id={cid} vs metadata.chunk_id={c['metadata'].get('chunk_id')}"
            )
        if cid in seen:
            continue
        seen.add(cid)
        result.append(c)

    dropped = len(chunks) - len(result)
    if dropped:
        dup_ids = [k for k, v in Counter(c["id"] for c in chunks).items() if v > 1]
        print(f"  중복 청크 {dropped}개 제거 (동일 source+article+text). 예: {dup_ids[:3]}")
    return result


def _validate_chunks(chunks: list[dict]) -> None:
    """엄격 검증 — 중복/불일치 시 raise. 단위 테스트용 (parse_all은 dedupe 사용)."""
    ids = [c["id"] for c in chunks]
    if len(ids) != len(set(ids)):
        dups = [k for k, v in Counter(ids).items() if v > 1]
        raise ValueError(
            f"chunk_id 중복 {len(dups)}개. 예: {dups[:5]}. "
            "동일 (source, article, 정규화 텍스트) 청크가 중복 존재. "
            "청킹 로직 또는 PDF에서 동일 조항 반복 여부 확인."
        )

    for c in chunks:
        if c["metadata"].get("chunk_id") != c["id"]:
            raise ValueError(
                f"id-metadata.chunk_id 불일치: id={c['id']} vs metadata.chunk_id={c['metadata'].get('chunk_id')}"
            )


if __name__ == "__main__":
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    chunks = parse_all()
    chunks = _dedupe_chunks(chunks)

    output_path = PROCESSED_DIR / "chunks.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"\n완료: 총 {len(chunks)}개 청크, 모두 unique chunk_id -> {output_path}")
