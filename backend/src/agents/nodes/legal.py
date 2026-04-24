"""
법규검토 Agent — RAG 기반 가맹사업법/상가임대차보호법 리스크 검토

주요 데이터 소스:
  - ChromaDB에 인덱싱된 가맹사업법 / 상가임대차보호법 조문
  - 업종별 용도지역 규제 (constants.py)

리스크 레벨:
  - "safe"    : 특별한 법률 리스크 없음
  - "caution" : 주의 필요, 사전 확인 권고
  - "danger"  : 위반 가능성 높음, 전문가 상담 필수
"""

import asyncio
import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

from src.agents.llms import get_fast_llm
from src.agents.nodes._attribution_helpers import build_attribution
from src.chains.prompts import LEGAL_AGENT_SYSTEM_PROMPT
from src.chains.retriever import LegalDocumentRetriever
from src.config.constants import BIZ_NORMALIZE, BIZ_TYPE_LABEL, DISTRICT_ZONE_MAP, ZONING_RULES
from src.config.settings import settings
from src.schemas.state import AgentState
from src.schemas.structured_output import LegalBatchOutput
from src.services.ftc_franchise import FtcFranchiseClient
from src.services.law_api import LawApiClient

# 전체 조문 원본 인덱스 — chunks.json에서 (source, article) → 전체 본문 조립
# RAG는 "어떤 조문이 관련 있는지" 식별용으로만 사용하고, 실제 표시 본문은 여기서 가져옴
_ARTICLE_FULL_TEXT: dict[tuple[str, str], str] = {}
_TOTAL_CHUNK_COUNT: int = 0  # chunks.json 로드 시 실제 청크 수 저장
_CATEGORY_TO_SOURCES: dict[str, list[str]] = {}  # category → source 파일명 매핑

# 의무 조문 → 벌칙/과태료 조문 번호 매핑
# key: (카테고리, 의무조문), value: (카테고리, 벌칙조문) 리스트
# 벌칙 본문은 _ARTICLE_FULL_TEXT에서 자동 조회
_PENALTY_ARTICLE_MAP: dict[tuple[str, str], list[tuple[str, str]]] = {
    # 식품위생법: 의무 → 벌칙
    ("식품위생법", "제36조"): [("식품위생법", "제97조")],  # 시설기준 위반 → 과태료
    ("식품위생법", "제37조"): [("식품위생법", "제97조")],  # 영업허가/신고 미이행 → 과태료
    ("식품위생법", "제41조"): [("식품위생법", "제101조")],  # 위생교육 미이수 → 과태료
    ("식품위생법", "제43조"): [("식품위생법", "제101조")],  # 영업자 준수사항 위반 → 과태료
    ("식품위생법", "제44조"): [("식품위생법", "제75조")],  # 영업자 준수사항 위반 → 영업정지
    # 가맹사업법: 의무 → 벌칙
    ("가맹사업법", "제6조의2"): [("가맹사업법", "제42조")],  # 정보공개서 미등록 → 과태료
    ("가맹사업법", "제7조"): [("가맹사업법", "제43조")],  # 정보 미제공 → 과태료
    ("가맹사업법", "제9조"): [("가맹사업법", "제41조")],  # 허위과장 → 벌칙
    ("가맹사업법", "제12조의4"): [("가맹사업법", "제44조")],  # 영업지역 침해 → 과태료
    ("가맹사업법", "제14조"): [("가맹사업법", "제44조")],  # 부당한 계약 → 과태료
    # 소방시설법: 의무 → 벌칙
    ("소방시설법", "제12조"): [("소방시설법", "제57조")],  # 소방시설 미설치 → 벌칙
    ("소방시설법", "제13조"): [("소방시설법", "제57조")],  # 설치기준 위반 → 벌칙
    ("소방시설법", "제22조"): [("소방시설법", "제61조")],  # 자체점검 미실시 → 과태료
    ("소방시설법", "제24조"): [("소방시설법", "제61조")],  # 안전관리자 미선임 → 과태료
    # 근로기준법: 의무 → 벌칙
    ("근로기준법", "제17조"): [("근로기준법", "제114조")],  # 근로계약서 미교부 → 과태료
    ("근로기준법", "제43조"): [("근로기준법", "제109조")],  # 임금 미지급 → 벌칙
    ("근로기준법", "제50조"): [("근로기준법", "제110조")],  # 근로시간 위반 → 벌칙
    ("근로기준법", "제54조"): [("근로기준법", "제110조")],  # 휴게시간 미부여 → 벌칙
    ("근로기준법", "제56조"): [("근로기준법", "제109조")],  # 가산임금 미지급 → 벌칙
    # 개인정보보호법: 의무 → 벌칙
    ("개인정보보호법", "제15조"): [("개인정보보호법", "제75조")],  # 동의 없이 수집 → 과태료
    ("개인정보보호법", "제25조"): [("개인정보보호법", "제75조")],  # CCTV 규정 위반 → 과태료
    ("개인정보보호법", "제30조"): [("개인정보보호법", "제75조")],  # 처리방침 미공개 → 과태료
    # 하수도법: 의무 → 벌칙
    ("하수도법", "제34조"): [("하수도법", "제80조")],  # 배수설비 미설치 → 과태료
    ("하수도법", "제27조"): [("하수도법", "제78조")],  # 오수처리 위반 → 벌칙
    # 공정거래법: 의무 → 벌칙
    ("공정거래법", "제45조"): [("공정거래법", "제124조")],  # 불공정거래 → 벌칙
    ("공정거래법", "제40조"): [("공정거래법", "제130조")],  # 거래강제 → 과태료
    # 건축법: 의무 → 벌칙
    ("건축법", "제19조"): [("건축법", "제80조")],  # 용도변경 미이행 → 이행강제금
    ("건축법", "제11조"): [("건축법", "제80조")],  # 무허가 건축 → 이행강제금
}


_CHECKLIST_RULES: list[tuple[list[str], str, str, bool]] = [
    # (키워드 목록, 중복 키, 체크리스트 텍스트, 필수 여부)
    # --- 가맹사업법 ---
    (["정보공개서"], "정보공개서", "가맹본부로부터 정보공개서 수령 및 내용 확인", True),
    (["14일", "숙고기간"], "숙고기간", "14일 숙고기간 확보 후 계약 체결", True),
    (["가맹금"], "가맹금", "가맹금 예치 여부 확인", True),
    (["영업지역", "지역"], "영업지역", "영업지역 독점 보호 조항 확인", False),
    # --- 상가임대차보호법 ---
    (["권리금"], "권리금", "권리금 회수 기회 보호 조항 확인", True),
    (["대항력", "확정일자"], "대항력", "임대차계약 확정일자 확보 (대항력 취득)", True),
    (["계약갱신"], "계약갱신", "계약갱신 요구권 행사 요건 확인 (10년)", True),
    (["보증금", "임차보증금"], "보증금", "임차보증금 반환 보장 장치 확인", True),
    # --- 식품위생법 ---
    (["위생", "영업신고"], "위생", "영업신고·위생교육 이수 증빙 준비", True),
    (["영업허가"], "영업허가", "영업허가(신고) 신청 및 허가증 수령", True),
    (["HACCP", "위해요소"], "HACCP", "HACCP 적용 대상 여부 확인", False),
    (["유통기한", "표시기준"], "유통기한", "식품 표시기준·유통기한 관리 체계 마련", False),
    # --- 건축법 ---
    (["용도변경"], "용도변경", "건축물 용도변경 허가·신고 필요 여부 확인", True),
    (["건축허가", "건축신고"], "건축허가", "건축허가(신고) 대상 여부 확인", True),
    (["불법건축", "이행강제금"], "불법건축", "불법 건축물 여부 확인 (이행강제금 리스크)", True),
    # --- 소방시설법 ---
    (["소방", "스프링클러"], "소방", "소방시설 설치 및 안전시설 완비증명 확보", True),
    (["소방안전관리자"], "소방관리자", "소방안전관리자 선임 의무 확인", True),
    (["방염"], "방염", "인테리어 방염 대상 자재 사용 여부 확인", False),
    # --- 근로기준법 ---
    (["근로계약", "최저임금"], "근로", "근로계약서 작성·교부 및 최저임금 준수 확인", True),
    (["주휴수당", "주휴"], "주휴수당", "주휴수당 지급 의무 확인 (주 15시간 이상)", True),
    (["퇴직급여", "퇴직금"], "퇴직금", "퇴직급여 지급 요건 확인 (1년 이상 근속)", True),
    (["4대보험", "사회보험"], "4대보험", "4대 사회보험 가입 의무 이행", True),
    # --- 부가가치세법 ---
    (["부가가치세", "부가세"], "부가세", "부가가치세 과세·면세 여부 확인", True),
    (["사업자등록"], "사업자등록", "사업자등록 신청 (개업일 전 20일 이내)", True),
    (["세금계산서"], "세금계산서", "전자세금계산서 발행 의무 확인", False),
    (["간이과세"], "간이과세", "간이과세자 적용 여부 확인", False),
    # --- 개인정보보호법 ---
    (["개인정보", "CCTV"], "개인정보", "개인정보 수집·이용 동의 절차 마련", True),
    (["개인정보처리방침"], "처리방침", "개인정보처리방침 작성·게시", True),
    (["영상정보"], "영상정보", "CCTV 설치 시 안내판 게시 및 운영 방침 수립", False),
    # --- 장애인편의증진법 ---
    (["편의시설", "장애인"], "편의시설", "장애인 편의시설 설치 의무 대상 확인", True),
    (["경사로", "점자"], "경사로", "출입구 경사로·점자블록 등 편의시설 설치", True),
    (["장애인주차"], "장애인주차", "장애인 전용 주차구역 확보 여부 확인", False),
    # --- 하수도법 ---
    (["배수설비", "하수"], "배수설비", "배수설비 설치 및 하수도 연결 신고", True),
    (["오수", "정화조"], "정화조", "개인 오수처리시설(정화조) 설치 의무 확인", True),
    (["폐수", "방류수"], "폐수", "폐수 배출 기준 충족 여부 확인", False),
    # --- 공정거래법 ---
    (["표시광고", "허위광고"], "표시광고", "허위·과장 광고 금지 사항 확인", True),
    (["불공정거래"], "불공정거래", "불공정 거래행위 해당 여부 검토", False),
    (["약관"], "약관", "표준약관 사용 또는 약관 공정성 검토", False),
    # --- 용도지역 (zoning_regulation) ---
    (["용도지역", "용도지구"], "용도지역", "해당 용도지역 내 영업 허용 여부 확인", True),
    (["학교환경위생"], "학교정화", "학교정화구역 내 영업제한 대상 확인", True),
]


_TYPE_TO_CATEGORY = {
    "franchise_law": "가맹사업법",
    "commercial_lease_law": "상가임대차보호법",
    "food_hygiene": "식품위생법",
    "building_law": "건축법",
    "fire_safety_law": "소방시설법",
    "labor_law": "근로기준법",
    "vat_law": "부가가치세법",
    "privacy_law": "개인정보보호법",
    "accessibility_law": "장애인편의증진법",
    "sewage_law": "하수도법",
    "fair_trade_law": "공정거래법",
    "zoning_regulation": "용도지역 규제",
    "safety_regulation": "안전관리법",
    "ftc_franchise": "공정위 정보공개서",
}

# 키워드 매칭 실패 시 타입별 기본 체크리스트
_DEFAULT_CHECKLIST: dict[str, list[dict]] = {
    "franchise_law": [
        {"text": "가맹본부로부터 정보공개서 수령 및 내용 확인", "isRequired": True},
        {"text": "14일 숙고기간 확보 후 계약 체결", "isRequired": True},
    ],
    "commercial_lease_law": [
        {"text": "임대차계약 확정일자 확보 (대항력 취득)", "isRequired": True},
        {"text": "권리금 회수 기회 보호 조항 확인", "isRequired": True},
    ],
    "food_hygiene": [
        {"text": "영업신고·위생교육 이수 증빙 준비", "isRequired": True},
        {"text": "영업허가(신고) 신청 및 허가증 수령", "isRequired": True},
    ],
    "building_law": [
        {"text": "건축물 용도변경 허가·신고 필요 여부 확인", "isRequired": True},
        {"text": "불법 건축물 여부 확인 (이행강제금 리스크)", "isRequired": True},
    ],
    "fire_safety_law": [
        {"text": "소방시설 설치 및 안전시설 완비증명 확보", "isRequired": True},
        {"text": "소방안전관리자 선임 의무 확인", "isRequired": True},
    ],
    "labor_law": [
        {"text": "근로계약서 작성·교부 및 최저임금 준수 확인", "isRequired": True},
        {"text": "4대 사회보험 가입 의무 이행", "isRequired": True},
    ],
    "vat_law": [
        {"text": "사업자등록 신청 (개업일 전 20일 이내)", "isRequired": True},
        {"text": "부가가치세 과세·면세 여부 확인", "isRequired": True},
    ],
    "privacy_law": [
        {"text": "개인정보 수집·이용 동의 절차 마련", "isRequired": True},
        {"text": "개인정보처리방침 작성·게시", "isRequired": True},
        {"text": "CCTV 설치 시 안내판 게시 및 운영 방침 수립", "isRequired": False},
    ],
    "accessibility_law": [
        {"text": "장애인 편의시설 설치 의무 대상 확인", "isRequired": True},
        {"text": "출입구 경사로·점자블록 등 편의시설 설치", "isRequired": True},
    ],
    "sewage_law": [
        {"text": "배수설비 설치 및 하수도 연결 신고", "isRequired": True},
        {"text": "개인 오수처리시설(정화조) 설치 의무 확인", "isRequired": True},
    ],
    "fair_trade_law": [
        {"text": "허위·과장 광고 금지 사항 확인", "isRequired": True},
        {"text": "표준약관 사용 또는 약관 공정성 검토", "isRequired": False},
    ],
    "zoning_regulation": [
        {"text": "해당 용도지역 내 영업 허용 여부 확인", "isRequired": True},
        {"text": "학교정화구역 내 영업제한 대상 확인", "isRequired": True},
    ],
    "safety_regulation": [
        {"text": "다중이용업소 안전관리 대상 여부 확인", "isRequired": True},
        {"text": "안전시설 등 세부점검표 작성 및 비치", "isRequired": True},
    ],
    "ftc_franchise": [
        {"text": "공정위 정보공개서 등록 여부 확인", "isRequired": True},
        {"text": "가맹본부 재무 현황 및 분쟁 이력 검토", "isRequired": False},
    ],
}


def _derive_checklist_from_articles(articles: list, risk_type: str) -> list[dict]:
    """조문 본문에서 창업 체크리스트 항목 파생.

    §13 법률 리스크 드로어의 체크리스트 UI 에 사용.
    1차: 조문 키워드 매칭, 2차: 타입별 기본 체크리스트 fallback.
    """
    items: list[dict] = []
    seen: set[str] = set()
    for a in (articles or [])[:8]:
        content = (a.get("content") if isinstance(a, dict) else "") or ""
        for keywords, dedup_key, text, required in _CHECKLIST_RULES:
            if dedup_key in seen:
                continue
            if any(kw in content for kw in keywords):
                items.append({"text": text, "isRequired": required})
                seen.add(dedup_key)
    # 키워드 매칭 결과가 부족하면 타입별 기본 체크리스트로 보충
    defaults = _DEFAULT_CHECKLIST.get(risk_type, [])
    if defaults:
        existing_texts = {it["text"] for it in items}
        for d in defaults:
            if d["text"] not in existing_texts:
                items.append(dict(d))
    if not items:
        label = _TYPE_TO_CATEGORY.get(risk_type, risk_type)
        items.append({"text": f"{label} 관련 조문 상세 검토", "isRequired": False})
    return items


def _enrich_penalty_info(risks: list) -> None:
    """법률 리스크 리스트의 recommendation에 벌칙 조문 본문을 자동 추가.

    캐시/비캐시 모두에서 호출하여 벌칙 정보가 항상 포함되도록 보장.
    이미 벌칙 정보가 붙어있으면 중복 추가하지 않음.
    """
    for _r in risks:
        if not isinstance(_r, dict):
            continue
        rtype = _r.get("type", "")
        cat = _TYPE_TO_CATEGORY.get(rtype, "")
        if not cat:
            continue
        existing_rec = _r.get("recommendation", "")
        if "⚖️" in existing_rec:
            continue  # 이미 벌칙 정보가 붙어있음
        penalty_parts = []
        for art_item in _r.get("articles") or []:
            art_ref = art_item.get("article_ref", "") if isinstance(art_item, dict) else ""
            art_match = re.match(r"(제\d+조(?:의\d+)?)", art_ref)
            if not art_match:
                continue
            penalty_text = _lookup_penalty(cat, art_match.group(1))
            if penalty_text:
                penalty_parts.append(penalty_text)
        if penalty_parts:
            penalty_info = "\n• ⚖️ 위반 시 제재 (법률 원문): " + " / ".join(penalty_parts)
            _r["recommendation"] = existing_rec + penalty_info


def _lookup_penalty(category: str, article: str) -> str | None:
    """의무 조문에 연결된 벌칙 조문 본문을 chunks.json 인덱스에서 조회.

    반환: "위반 시: ... (제97조)" 형태의 요약 문자열, 매핑 없으면 None.
    _ARTICLE_FULL_TEXT의 key는 (source_filename, article)이므로
    category → source 변환 후 조회.
    """
    _load_article_index()
    key = (category, article)
    penalty_refs = _PENALTY_ARTICLE_MAP.get(key)
    if not penalty_refs:
        return None

    parts = []
    for p_cat, p_art in penalty_refs:
        # category → source 변환 후 _ARTICLE_FULL_TEXT에서 조회
        sources = _CATEGORY_TO_SOURCES.get(p_cat, [])
        found_text = ""
        for src in sources:
            text = _ARTICLE_FULL_TEXT.get((src, p_art), "")
            if text:
                found_text = text
                break
        if not found_text:
            continue
        # 본문에서 핵심 제재 내용 추출 (첫 200자)
        snippet = found_text[:200].replace("\n", " ").strip()
        parts.append(f"({p_art}) {snippet}")

    return " / ".join(parts) if parts else None


def _load_article_index() -> None:
    """chunks.json을 읽어 조문별 전체 본문 인덱스를 구축합니다."""
    global _ARTICLE_FULL_TEXT, _TOTAL_CHUNK_COUNT, _CATEGORY_TO_SOURCES
    if _ARTICLE_FULL_TEXT:
        return  # 이미 로드됨
    from pathlib import Path

    chunks_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "legal" / "processed" / "chunks.json"
    if not chunks_path.exists():
        logger.warning(f"[legal_node] chunks.json 없음: {chunks_path}")
        return
    with open(chunks_path, encoding="utf-8") as f:
        chunks = json.load(f)
    _TOTAL_CHUNK_COUNT = len(chunks)

    # category → source 파일명 매핑 구축
    for c in chunks:
        cat = c.get("metadata", {}).get("category", "")
        src = c.get("metadata", {}).get("source", "")
        if cat and src:
            _CATEGORY_TO_SOURCES.setdefault(cat, [])
            if src not in _CATEGORY_TO_SOURCES[cat]:
                _CATEGORY_TO_SOURCES[cat].append(src)

    # (source, article) → [(chunk_id, text)] 그룹핑
    grouped: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for c in chunks:
        meta = c.get("metadata", {})
        source = meta.get("source", "")
        article = meta.get("article", "")
        chunk_id = meta.get("chunk_id", "")
        text = c.get("text", "")
        if article and article not in ("전문", "미분류", "N/A") and text:
            key = (source, article)
            grouped.setdefault(key, []).append((chunk_id, text))

    # 조문 본문 조립:
    # 1) 모든 청크를 합친 뒤 "제N조(제목)" 위치를 찾아 거기부터 추출
    # 2) 다음 조문 "제M조(" 이 나오면 거기서 자름
    # → 목차, 연락처, 장 제목 등 쓰레기가 자동으로 제거됨
    _next_art_pattern = re.compile(r"(?=제\d+조(?:의\d+)?\s*[\(（])")
    _chapter_pattern = re.compile(r"\n제\d+장\s")

    for key, pairs in grouped.items():
        _, article = key
        pairs.sort(key=lambda x: x[0])
        raw = "\n".join(t for _, t in pairs)

        # "제N조(..." 또는 "제N조의M(..." 실제 조문 시작 위치 찾기
        art_start_re = re.compile(rf"(?={re.escape(article)}\s*[\(（])")
        match = art_start_re.search(raw)
        if match:
            text_from_article = raw[match.start() :]
            # 본문에서 다음 조문 시작 위치 찾기 (자기 자신 제외)
            all_matches = list(_next_art_pattern.finditer(text_from_article))
            if len(all_matches) > 1:
                # 두 번째 매치가 다음 조문의 시작
                text_from_article = text_from_article[: all_matches[1].start()].strip()
            # 조문 뒤에 나오는 노이즈 구분자에서 자르기
            _noise_patterns = (
                _chapter_pattern,  # 제N장
                re.compile(r"\n제\d+편\s"),  # 제N편
                re.compile(r"\n부칙[\s<]"),  # 부칙
                re.compile(r"\n\[별표"),  # [별표
                re.compile(r"\n[가-힣\s]+(?:법|령|규칙|법률)\s*$", re.MULTILINE),  # 법률 제목
            )
            for noise_pat in _noise_patterns:
                noise_match = noise_pat.search(text_from_article)
                if noise_match:
                    text_from_article = text_from_article[: noise_match.start()].strip()
            # 끝이 쉼표면 마지막 완전한 문장까지 자르기
            if text_from_article.rstrip().endswith(","):
                last_period = max(
                    text_from_article.rfind("다."),
                    text_from_article.rfind(")"),
                    text_from_article.rfind("한다"),
                    text_from_article.rfind("]"),
                )
                if last_period > len(text_from_article) * 0.5:
                    text_from_article = text_from_article[: last_period + 1]
            _ARTICLE_FULL_TEXT[key] = text_from_article
        else:
            # "제N조(" 패턴을 못 찾으면 가장 긴 청크 사용
            longest = max(pairs, key=lambda x: len(x[1]))
            _ARTICLE_FULL_TEXT[key] = longest[1]

    logger.info(f"[legal_node] 조문 인덱스 로드 완료: {len(_ARTICLE_FULL_TEXT)}개 조문")


async def _search_ftc_from_db(brand_name: str) -> dict | None:
    """
    ftc_brand_franchise 테이블에서 브랜드 정보 검색 (DB 직접 조회).

    API 호출 없이 DB에 적재된 34,000+ 건의 정보공개서 데이터에서 검색.
    최신 연도 기준으로 반환하며, 폐점률을 계산하여 리스크 판정에 사용.
    """
    from src.agents.nodes.market_analyst import db_client

    try:
        if db_client.engine is None:
            await db_client.connect()

        async with db_client.get_session() as session:
            from sqlalchemy import text

            # LIKE 검색 (부분 일치) — 브랜드명 내 %,_ 문자 이스케이프
            safe_brand = brand_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = text("""
                SELECT yr, "corpNm", "brandNm", "frcsCnt", "newFrcsRgsCnt",
                       "ctrtEndCnt", "ctrtCncltnCnt", "avrgSlsAmt"
                FROM ftc_brand_franchise
                WHERE "brandNm" LIKE :pattern ESCAPE '\\'
                ORDER BY yr DESC
                LIMIT 1
            """)
            row = (await session.execute(stmt, {"pattern": f"%{safe_brand}%"})).fetchone()

            if not row:
                return None

            store_count = int(row.frcsCnt or 0)
            end_count = int(row.ctrtEndCnt or 0)
            cancel_count = int(row.ctrtCncltnCnt or 0)
            avg_sales = int(row.avrgSlsAmt or 0) * 10000  # 만원 단위 → 원 단위

            churn_rate = (end_count + cancel_count) / max(store_count, 1)

            return {
                "brand_name": row.brandNm,
                "corp_name": row.corpNm,
                "store_count_total": store_count,
                "churn_rate": round(churn_rate, 4),
                "avg_sales_amount": avg_sales,
                "franchise_fee": None,  # DB에 가맹금 컬럼 없음 — 0은 무료와 혼동
            }

    except Exception as e:
        logger.warning(f"[_search_ftc_from_db] DB 조회 실패: {e}")
        return None


async def check_ftc_franchise(state: AgentState) -> dict:
    """
    공정위 가맹사업 정보공개서 검토 — 브랜드 폐점률·매출·가맹금 리스크 판정.

    주요 검토 항목:
    - 폐점률 (10% 초과 시 위험, 5% 초과 시 주의)
    - 평균 매출액 (1억 미만 시 주의)
    - 가맹금 수준 (1000만 원 초과 시 주의)

    Returns:
        dict: {type, level, summary, articles, recommendation}
    """
    brand = state.get("brand_name") or ""

    if not brand:
        return {
            "type": "ftc_franchise",
            "level": "caution",
            "summary": "브랜드명이 입력되지 않아 공정위 정보공개서 조회를 건너뜁니다.",
            "articles": [],
            "recommendation": "브랜드명 입력 후 재검토 권장",
            "is_fallback": True,
        }

    # 1차: DB에서 검색 (ftc_brand_franchise 테이블 — 16,000+ 브랜드)
    # 2차: API 실패 시에도 DB fallback
    detail = await _search_ftc_from_db(brand)

    if not detail and settings.ftc_api_key:
        try:
            client = FtcFranchiseClient(api_key=settings.ftc_api_key)
            detail = await client.get_brand_detail(brand)
        except Exception as e:
            logger.warning(f"[check_ftc_franchise] API 실패 (DB fallback 사용): {e}")

    if not detail:
        return {
            "type": "ftc_franchise",
            "level": "caution",
            "summary": f"'{brand}' 브랜드의 공정위 정보공개서를 찾을 수 없습니다.",
            "articles": [
                {
                    "article_ref": "[정보공개서 미등록]",
                    "content": (
                        f"'{brand}' 브랜드의 정보공개서가 공정위 가맹사업정보제공시스템에 "
                        f"등록되어 있지 않거나, 브랜드명이 다르게 등록되어 있을 수 있습니다.\n"
                        f"직접 확인: https://franchise.ftc.go.kr"
                    ),
                }
            ],
            "recommendation": "공정위 가맹사업정보제공시스템 직접 확인 권장",
            "is_fallback": True,
        }

    try:
        churn_rate = detail.get("churn_rate", 0.0)
        avg_sales = detail.get("avg_sales_amount", 0)
        franchise_fee = detail.get("franchise_fee")  # None이면 "정보 없음" 표시
        store_count = detail.get("store_count_total", 0)

        # 리스크 레벨 판정
        if churn_rate > 0.10:
            level = "danger"
        elif churn_rate > 0.05 or avg_sales < 100_000_000:
            level = "caution"
        else:
            level = "safe"

        summary = (
            f"'{detail.get('brand_name', brand)}' ({detail.get('corp_name', '')}) "
            f"정보공개서 기준 — "
            f"전체 가맹점 수: {store_count}개, "
            f"폐점률: {churn_rate:.1%}, "
            f"평균 매출액: {avg_sales:,}원, "
            f"가입비: {f'{franchise_fee:,}원' if franchise_fee is not None else '정보 없음'}. "
        )
        if level == "danger":
            summary += "폐점률이 10%를 초과하여 사업 안정성 리스크가 높습니다."
        elif level == "caution":
            summary += "폐점률 또는 매출 수준에서 주의가 필요합니다."
        else:
            summary += "공정위 지표 기준 안정적인 브랜드로 판단됩니다."

        recommendation = ""
        if level == "danger":
            recommendation = "가맹본부 재무 상태 및 폐점 원인 심층 확인 필수"
        elif level == "caution":
            recommendation = "가맹 계약 전 정보공개서 원문 직접 검토 권장"

        # FTC API 결과를 articles로 변환 (RAG 대신 정보공개서 데이터)
        ftc_articles = [
            {
                "article_ref": "[정보공개서]",
                "content": (
                    f"브랜드: {detail.get('brand_name', brand)} ({detail.get('corp_name', '')})\n"
                    f"전체 가맹점 수: {store_count}개\n"
                    f"폐점률: {churn_rate:.1%}\n"
                    f"평균 매출액: {avg_sales:,}원\n"
                    f"가입비: {f'{franchise_fee:,}원' if franchise_fee is not None else '정보 없음'}"
                ),
            }
        ]

        return {
            "type": "ftc_franchise",
            "level": level,
            "summary": summary,
            "articles": ftc_articles,
            "recommendation": recommendation,
        }

    except Exception as e:
        return {
            "type": "ftc_franchise",
            "level": "caution",
            "summary": f"공정위 정보공개서 조회 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "공정위 가맹사업정보제공시스템 직접 확인 권장",
            "is_fallback": True,
        }


async def check_zoning_regulation(state: AgentState) -> dict:
    """
    용도지역 규제 검토 — 대상 행정동의 용도지역에서 해당 업종 영업 가능 여부.

    LLM 없이 constants 기반 규칙으로 판정 (빠르고 결정론적).

    Returns:
        dict: {type, level, zone, business_type, allowed, summary}
    """
    district = state.get("target_district", "")
    business_type = state.get("business_type", "")  # "cafe" | "restaurant" | "convenience"

    zone = DISTRICT_ZONE_MAP.get(district, "근린상업지역")  # 알 수 없는 동은 상업지역으로 가정
    rules = ZONING_RULES.get(zone, {"허용": [], "제한": []})

    # business_type 코드 → 한글 매핑 (constants.py 단일 소스)
    type_label = BIZ_TYPE_LABEL.get(business_type.lower(), business_type)

    if type_label in rules["제한"]:
        level = "danger"
        summary = f"'{district}'의 용도지역({zone})에서 '{type_label}' 영업은 제한될 수 있습니다."
    elif type_label in rules["허용"] or not rules["제한"]:
        level = "safe"
        summary = f"'{district}'의 용도지역({zone})에서 '{type_label}' 영업 가능합니다."
    else:
        level = "caution"
        summary = f"'{district}'의 용도지역({zone}) 규제를 현장 확인 후 영업 가능 여부를 판단하세요."

    zoning_articles = [
        {
            "article_ref": "[용도지역 판정]",
            "content": (
                f"행정동: {district}\n"
                f"용도지역: {zone}\n"
                f"업종: {type_label}\n"
                f"영업 가능 여부: {'가능' if level != 'danger' else '제한'}\n"
                f"허용 업종: {', '.join(rules['허용']) if rules['허용'] else '별도 확인 필요'}\n"
                f"제한 업종: {', '.join(rules['제한']) if rules['제한'] else '없음'}"
            ),
        }
    ]

    return {
        "type": "zoning_regulation",
        "level": level,
        "zone": zone,
        "business_type": type_label,
        "allowed": level != "danger",
        "summary": summary,
        "articles": zoning_articles,
        "recommendation": "토지이음(eum.go.kr)에서 실제 용도지역을 확인하세요." if level != "safe" else "",
    }


async def _run_legal_pipeline(state: dict) -> dict:
    """
    2단계 풀 파이프라인으로 법률 검토 수행.

    Phase 1 (병렬 18개): RAG×13 + 판례×4 + FTC API
                         zoning은 I/O 없는 규칙 기반이므로 즉시 실행
    Phase 2 (병렬 12개): LLM 기반 check 함수 동시 실행

    기존 순차 실행 대비 ~35~68초 → ~8~12초로 단축.
    동일 brand+district+business_type 조합은 Redis에 24시간 캐시.
    """

    import redis.asyncio as aioredis

    from src.config.settings import settings

    brand = state.get("brand_name") or "해당 브랜드"
    district = state.get("target_district", "")
    business_type = state.get("business_type", "")

    # 캐시 키 정규화 — 영문/한글 혼용 시 동일 캐시 히트 보장 (constants.py 단일 소스)
    _normalized_biz = BIZ_NORMALIZE.get(business_type.lower(), business_type)

    # Redis 캐시 조회 — 동일 조합 재요청 시 LLM 호출 없이 즉시 반환
    _CACHE_TTL = 86400  # 24시간
    # v4: articles 필드가 list[str] → list[{article_ref, content}]로 변경되어 캐시 무효화
    cache_key = f"v4:legal:{brand}:{district}:{_normalized_biz}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = None if settings.debug else await _redis.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            legal_risks = cached_data.get("legal_risks")
            legal_info = cached_data.get("legal_info")
            if legal_risks is None or legal_info is None:
                logger.warning(f"[legal_node] 캐시 데이터 손상 - 재계산: {cache_key}")
            else:
                logger.info(f"[legal_node] 캐시 히트: {cache_key}")
                # 캐시 데이터에도 checklist + 벌칙 매핑 보강 (구 캐시 호환)
                for _r in legal_risks or []:
                    if isinstance(_r, dict) and "checklist" not in _r:
                        _r["checklist"] = _derive_checklist_from_articles(
                            _r.get("articles") or [],
                            _r.get("type", "unknown"),
                        )
                _enrich_penalty_info(legal_risks)
                # DEBUG: 캐시된 articles가 새 dict 포맷인지 확인
                try:
                    first_risk = legal_risks[0] if legal_risks else {}
                    first_arts = first_risk.get("articles", []) if isinstance(first_risk, dict) else []
                    logger.info(
                        f"[legal_node] 캐시 articles 샘플 타입={type(first_arts[0]).__name__ if first_arts else 'empty'} "
                        f"값={first_arts[0] if first_arts else None}"
                    )
                except Exception as _e:
                    logger.warning(f"[legal_node] 캐시 articles 샘플 확인 실패: {_e}")
                analysis = dict(state.get("analysis_results") or {})
                analysis["legal_risks"] = legal_risks
                overall_cached = cached_data.get("overall_legal_risk", "caution")
                analysis["overall_legal_risk"] = overall_cached
                _cached_high = sum(1 for r in (legal_risks or []) if isinstance(r, dict) and r.get("level") == "danger")
                cached_legal_attr = build_attribution(
                    agent_id="legal",
                    display_name="법률 리스크",
                    kind="RAG",
                    sources=[f"legal_rag_chunks ({_TOTAL_CHUNK_COUNT})"],
                    verdict=f"14 법률 위험도 · overall {overall_cached}",
                    reasoning=f"14개 법률 조항 RAG 검색 (chunks 3775). {_cached_high}건 HIGH 위험.",
                    confidence=0.85,
                )
                analysis["legal_result"] = {"agent_attribution": cached_legal_attr}
                try:
                    await _redis.aclose()
                except Exception:
                    pass
                return {
                    **state,
                    "analysis_results": analysis,
                    "legal_info": legal_info,
                    "overall_legal_risk": overall_cached,
                    "agent_attribution": cached_legal_attr,
                }
    except Exception as e:
        logger.warning(f"[legal_node] Redis 캐시 조회 실패 (무시하고 계속): {e}")
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass
            _redis = None

    # LegalDocumentRetriever — 모듈 레벨 싱글톤 (임베딩 모델 재로딩 방지)
    if not hasattr(_run_legal_pipeline, "_retriever"):
        _run_legal_pipeline._retriever = LegalDocumentRetriever()
    retriever = _run_legal_pipeline._retriever

    franchise_q = f"{brand} 영업지역 보장 동일 브랜드 출점 제한 가맹사업법"
    lease_q = "권리금 회수 기회 보호 계약갱신요구권 환산보증금 상가임대차보호법"
    food_q = f"{business_type} 영업신고 허가 위생교육 시설기준 식품위생법"
    safety_q = f"{business_type} 다중이용업소 소방시설 안전시설 완비증명 의무"
    summary_q = f"{business_type} {district} 프랜차이즈 법률 검토"
    building_q = f"{business_type} 건축물 용도 근린생활시설 용도변경 건축법"
    fire_q = f"{business_type} 소방시설 스프링클러 소화기 소방안전관리자 설치의무"
    labor_q = "근로계약서 최저임금 주휴수당 가산임금 4대보험 근로기준법"
    vat_q = "사업자등록 일반과세자 간이과세자 세금계산서 부가가치세"
    privacy_q = "개인정보 수집 동의 처리방침 CCTV 고객정보"
    accessibility_q = f"{business_type} 대상시설 편의시설 설치 공공건물 공중이용시설 장애인편의증진법"
    sewage_q = f"{business_type} 오수 배출 개인하수처리시설 설치 배수설비 공공하수도 하수도법"
    fair_trade_q = f"{brand} 가맹본부 불공정거래 거래강제 필수물품 공급"

    # LawApiClient — 모듈 레벨 싱글톤 (매 요청 인스턴스 생성 방지)
    if not hasattr(_run_legal_pipeline, "_law_client"):
        _run_legal_pipeline._law_client = LawApiClient()
    law_client = _run_legal_pipeline._law_client

    # zoning: I/O 없는 규칙 기반 — 즉시 실행 후 Phase 1 병렬 대기
    zoning_result = await check_zoning_regulation(state)

    # Phase 1: RAG + 판례 + FTC — 커넥션 풀(8) 고갈 방지를 위해 2배치로 분할
    # Batch A: RAG 7개 + FTC (DB 커넥션 최대 7개 동시 사용)
    _batch_a = await asyncio.gather(
        retriever.search(franchise_q, top_k=10, source_filter=LegalDocumentRetriever.FRANCHISE_LAW_SOURCES),
        retriever.search(lease_q, top_k=10, source_filter=LegalDocumentRetriever.LEASE_LAW_STRICT_SOURCES),
        retriever.search(food_q, top_k=10, source_filter=LegalDocumentRetriever.FOOD_HYGIENE_SOURCES),
        retriever.search(safety_q, top_k=10, source_filter=LegalDocumentRetriever.SAFETY_SOURCES),
        retriever.search(summary_q, top_k=10),
        retriever.search(building_q, top_k=10, source_filter=LegalDocumentRetriever.BUILDING_LAW_SOURCES),
        retriever.search(fire_q, top_k=10, source_filter=LegalDocumentRetriever.FIRE_SAFETY_SOURCES),
        check_ftc_franchise(state),
        return_exceptions=True,
    )
    # Batch B: RAG 6개 + 판례 6개 (판례는 외부 API라 DB 커넥션 무관)
    _batch_b = await asyncio.gather(
        retriever.search(labor_q, top_k=10, source_filter=LegalDocumentRetriever.LABOR_LAW_SOURCES),
        retriever.search(vat_q, top_k=10, source_filter=LegalDocumentRetriever.VAT_LAW_SOURCES),
        retriever.search(privacy_q, top_k=10, source_filter=LegalDocumentRetriever.PRIVACY_LAW_SOURCES),
        retriever.search(accessibility_q, top_k=10, source_filter=LegalDocumentRetriever.ACCESSIBILITY_LAW_SOURCES),
        retriever.search(sewage_q, top_k=10, source_filter=LegalDocumentRetriever.SEWAGE_LAW_SOURCES),
        retriever.search(fair_trade_q, top_k=10, source_filter=LegalDocumentRetriever.FAIR_TRADE_SOURCES),
        law_client.search_precedents("가맹사업 영업지역", display=3),
        law_client.search_precedents("권리금 회수", display=3),
        law_client.search_precedents("식품위생 영업허가", display=3),
        law_client.search_precedents("다중이용업소 소방", display=3),
        law_client.search_precedents("건축물 용도변경 근린생활시설", display=2),
        law_client.search_precedents("근로계약 최저임금", display=2),
        return_exceptions=True,
    )
    # 결과 합치기 (기존 인덱스 순서 유지)
    _phase1_results = (
        list(_batch_a[:7])
        + [_batch_a[7]]
        + [  # RAG 0-6 + FTC placeholder
            *_batch_b[:6],  # RAG 7-12
            *_batch_b[6:12],  # 판례 6개
        ]
    )
    # 재배치: [RAG 0..6, summary(4), RAG 7..12, 판례 0..5, FTC]
    _phase1_results = [
        _batch_a[0],  # franchise
        _batch_a[1],  # lease
        _batch_a[2],  # food
        _batch_a[3],  # safety
        _batch_a[4],  # summary
        _batch_a[5],  # building
        _batch_a[6],  # fire
        _batch_b[0],  # labor
        _batch_b[1],  # vat
        _batch_b[2],  # privacy
        _batch_b[3],  # accessibility
        _batch_b[4],  # sewage
        _batch_b[5],  # fair_trade
        _batch_b[6],  # precedent: 가맹
        _batch_b[7],  # precedent: 권리금
        _batch_b[8],  # precedent: 식품위생
        _batch_b[9],  # precedent: 다중이용
        _batch_b[10],  # precedent: 건축물
        _batch_b[11],  # precedent: 근로계약
        _batch_a[7],  # FTC
    ]

    # 예외 결과를 빈 리스트/caution dict로 대체
    _rag_labels = [
        "franchise",
        "lease",
        "food",
        "safety",
        "summary",
        "building",
        "fire",
        "labor",
        "vat",
        "privacy",
        "accessibility",
        "sewage",
        "fair_trade",
        "prec_가맹",
        "prec_권리금",
        "prec_식품",
        "prec_다중",
        "prec_건축",
        "prec_근로",
        "ftc",
    ]
    _rag_debug: list[str] = []

    def _safe_list(r: object, idx: int = -1) -> list:
        label = _rag_labels[idx] if 0 <= idx < len(_rag_labels) else f"idx{idx}"
        if isinstance(r, Exception):
            _rag_debug.append(f"{label}: EXCEPTION {type(r).__name__}: {r}")
            return []
        result = r if isinstance(r, list) else []
        _rag_debug.append(f"{label}: {len(result)} docs")
        return result

    def _safe_ftc(r: object) -> dict:
        if isinstance(r, Exception):
            logger.warning(f"[legal_node] FTC API 실패 (무시하고 계속): {r}")
            return {
                "type": "ftc_franchise",
                "level": "caution",
                "summary": f"FTC API 오류: {r}",
                "articles": [],
                "recommendation": "",
            }
        return r  # type: ignore[return-value]

    (
        franchise_docs,
        lease_docs,
        food_docs,
        safety_docs,
        legal_info_docs,
        building_docs,
        fire_docs,
        labor_docs,
        vat_docs,
        privacy_docs,
        accessibility_docs,
        sewage_docs,
        fair_trade_docs,
        franchise_prec,
        lease_prec,
        food_prec,
        safety_prec,
        building_prec,
        labor_prec,
        ftc_result,
    ) = (
        *[_safe_list(_phase1_results[i], i) for i in range(19)],
        _safe_ftc(_phase1_results[19]),
    )

    # Phase 2: 12개 법률 항목을 단일 LLM 배치 호출로 처리 (12회 → 1회)
    _BATCH_TYPES = [
        "franchise_law",
        "commercial_lease_law",
        "food_hygiene",
        "safety_regulation",
        "building_law",
        "fire_safety_law",
        "labor_law",
        "vat_law",
        "privacy_law",
        "accessibility_law",
        "sewage_law",
        "fair_trade_law",
    ]
    _BATCH_LABELS = {
        "franchise_law": "가맹사업법 — 영업지역 침해 여부, 정보공개서 기재사항, 가맹금 예치 의무",
        "commercial_lease_law": "상가임대차보호법 — 권리금 회수기회 보호(제10조의4), 계약갱신요구권(10년), 환산보증금(서울 9억)",
        "food_hygiene": "식품위생법 — 영업 종류별 신고·허가 의무, 위생교육 이수, 영업장 시설 기준",
        "safety_regulation": "다중이용업소법 — 면적·업종 기준 해당 여부, 소방시설 설치, 안전시설 완비증명서",
        "building_law": "건축법 — 건축물 용도 적합(근린생활시설 등), 용도변경 신고·허가, 불법건축물 리스크",
        "fire_safety_law": "소방시설법 — 면적별 소방시설 설치(스프링클러·소화기), 소방안전관리자 선임, 정기점검",
        "labor_law": "근로기준법 — 근로계약서 작성·교부, 최저임금(2026년 기준), 주휴수당·가산임금, 4대보험",
        "vat_law": "부가가치세법 — 사업자등록(개업 전), 일반과세 vs 간이과세(연 8천만원), 세금계산서 발행",
        "privacy_law": "개인정보보호법 — 고객 정보 수집 동의, 개인정보 처리방침 공개, CCTV 안내판 부착",
        "accessibility_law": "장애인편의증진법 — 편의시설 설치 대상(300㎡ 이상), 경사로·장애인화장실·점자블록",
        "sewage_law": "하수도법/물환경보전법 — 오수처리시설, 유류분리기(그리스트랩) 설치, 폐수 배출 기준",
        "fair_trade_law": "공정거래법 — 가맹본부 불공정 거래 금지, 부당 거래 강제(필수 물품 고가 공급), 공정위 신고",
    }

    # 조문 인덱스 로드 (최초 1회만)
    _load_article_index()

    # 법률별 RAG 조문 추출 — 조문 제목 + 핵심 한 줄 요약
    _re = re

    _valid_art_re = _re.compile(r"^제\d+조(?:의\d+)?\s*[\(（]")
    _art_title_re = _re.compile(r"^(제\d+조(?:의\d+)?)\s*[\(（]([^)）]+)[\)）]")

    # "다음과 같다" 류 — 첫 문장만으로는 내용 파악 불가, 후속 항/호를 포함해야 함
    _INCOMPLETE_ENDINGS = _re.compile(r"다음과 같다|다음 각 호와 같다|다음 각 호의|아래와 같다")
    # ① ② 등 항 번호 패턴
    _HANG_PATTERN = _re.compile(r"[①-⑳]\s*")

    def _summarize_article(art: str, full_text: str) -> str:
        """조문 전문에서 '제목 — 핵심 의무/규정' 요약을 추출합니다."""
        m = _art_title_re.match(full_text.strip())
        title = m.group(2) if m else ""
        rest = full_text[m.end() :].strip() if m else full_text.strip()
        flat = rest.replace("\n", " ")

        # 본문이 너무 짧으면 (제목 + ① 만 있는 경우) 전문 그대로 반환
        if len(flat) < 10:
            return f"{title}" if title else full_text.strip()[:100]

        # 첫 번째 완전한 문장 추출
        sent_match = _re.search(
            r"(.+?(?:한다|된다|있다|이다|않다|둔다|같다|아니한다|수 있다|하여야 한다|받아야 한다)\.)",
            flat,
        )
        if sent_match:
            key_point = sent_match.group(1).strip()

            # "다음과 같다"로 끝나면 → 후속 항/호 번호 목록 추가
            if _INCOMPLETE_ENDINGS.search(key_point):
                after = flat[sent_match.end() :].strip()
                # 번호 항목(1. 2. 가. 나. 등) 추출 — 최대 5개
                items = _re.findall(r"(\d+\.\s*[^\d]{5,60}?)(?=\d+\.|$)", after)
                if not items:
                    items = _re.findall(r"([가-힣]\.\s*[^\n]{5,60}?)(?=[가-힣]\.|$)", after)
                if items:
                    item_text = " ".join(f"[{it.strip()[:50]}]" for it in items[:5])
                    key_point = f"{key_point} {item_text}"

            # ① 에서 끊기는 경우 → 해당 항 내용까지 포함
            elif key_point.rstrip().endswith("①") or len(key_point) < 20:
                after = flat[sent_match.end() :].strip() if sent_match else flat[len(key_point) :].strip()
                # ② 이전까지 또는 최대 200자 가져오기
                next_hang = _re.search(r"[②-⑳]", after)
                extend = after[: next_hang.start()].strip() if next_hang else after[:200].strip()
                if extend:
                    key_point = f"{key_point} {extend}"

            if len(key_point) > 300:
                key_point = key_point[:297] + "…"
        else:
            # 완전한 문장을 못 찾은 경우 — ① 이후 내용까지 포함
            hang_match = _HANG_PATTERN.search(flat)
            if hang_match:
                after_hang = flat[hang_match.end() :].strip()
                # ② 이전까지 또는 최대 200자
                next_hang = _re.search(r"[②-⑳]", after_hang)
                key_point = after_hang[: next_hang.start()].strip() if next_hang else after_hang[:200].strip()
            else:
                key_point = flat[:200].strip()
            if len(flat) > len(key_point):
                key_point += "…"
        return f"{title} — {key_point}" if title else key_point

    def _extract_articles(docs: list[dict]) -> list[dict]:
        """RAG 검색 결과에서 관련 조문을 식별하고, 조문 제목 + 핵심 한 줄 요약을 반환합니다."""
        _SKIP = ("전문", "미분류", "N/A")
        seen: set[str] = set()
        articles: list[dict] = []
        for d in docs:
            art = d.get("metadata", {}).get("article", "")
            source = d.get("metadata", {}).get("source", "")
            if not art or art in _SKIP or art in seen:
                continue
            seen.add(art)
            full_text = _ARTICLE_FULL_TEXT.get((source, art), "")
            if not full_text:
                for (s, a), txt in _ARTICLE_FULL_TEXT.items():
                    if a == art:
                        full_text = txt
                        break
            if not full_text:
                full_text = d.get("content", "")
            if len(full_text) < 30 or not _valid_art_re.match(full_text.strip()):
                continue
            articles.append({"article_ref": art, "content": _summarize_article(art, full_text)})
            if len(articles) >= 5:
                break
        # 조문이 없는 문서(지침, 계획서 등)
        if not articles and docs:
            for d in docs[:2]:
                content = d.get("content", "")
                source = d.get("metadata", {}).get("source", "참고 문서")
                if content:
                    articles.append({"article_ref": f"[{source[:30]}]", "content": content[:150]})
        return articles

    # 모든 RAG 문서를 법률별로 정리하여 컨텍스트 구성
    docs_context = ""
    docs_map = {
        "franchise_law": franchise_docs + franchise_prec,
        "commercial_lease_law": lease_docs + lease_prec,
        "food_hygiene": food_docs + food_prec,
        "safety_regulation": safety_docs + safety_prec,
        "building_law": building_docs + building_prec,
        "fire_safety_law": fire_docs,
        "labor_law": labor_docs + labor_prec,
        "vat_law": vat_docs,
        "privacy_law": privacy_docs,
        "accessibility_law": accessibility_docs,
        "sewage_law": sewage_docs,
        "fair_trade_law": fair_trade_docs,
    }
    # 법률별 균등 분배 — 12개 법률에 각 최대 1000자씩 (뒤쪽 법률 잘림 방지)
    _MAX_PER_LAW = 1000
    for law_type, docs in docs_map.items():
        if docs:
            snippets = " | ".join(d["content"][:400] for d in docs[:3])
            if len(snippets) > _MAX_PER_LAW:
                snippets = snippets[:_MAX_PER_LAW] + "…"
            docs_context += f"[{_BATCH_LABELS[law_type]}] {snippets}\n"

    items_desc = "\n".join(f'{i + 1}. type="{t}" — {_BATCH_LABELS[t]}' for i, t in enumerate(_BATCH_TYPES))

    system_content = (
        f"{LEGAL_AGENT_SYSTEM_PROMPT}\n\n"
        f"리스크 레벨 기준 (창업 전 관점 — 미이행 시 결과 기준으로 판정):\n"
        f"- safe: 해당 업종/지역에 적용되지 않거나, 별도 조치 없이 준수 가능\n"
        f"- caution: 사전 확인·서류 준비 필요, 미이행 시 과태료·시정명령 가능\n"
        f"- danger: 미이행 시 영업신고 불가·영업정지·허가취소·형사처벌. 반드시 창업 전 완료 필수\n"
        f"  (예: 식품위생법 영업신고, 건축법 용도변경, 소방 안전시설완비증명, 가맹사업법 정보공개서 등)\n\n"
        f"[평가 항목]\n{items_desc}\n\n"
        "12개 항목을 빠짐없이 items 리스트에 포함하세요.\n"
        "summary: 이 법률의 목적과 핵심 의무를 1~2문장으로 설명하세요.\n"
        "recommendation: 아래 형식의 체크리스트로 작성하세요:\n"
        "• [구체적 행동 항목] (관할 기관, 필요 서류 포함)\n"
        "• ❌ 위반 시: [과태료/벌금/영업정지 등 구체적 제재]\n"
        "반드시 해당 업종과 지역에 맞춰 구체적으로 작성하세요."
    )

    user_content = (
        f"브랜드: {brand} / 업종: {business_type} / 지역: {district}\n\n"
        f"[참고 법률 문서 발췌]\n{docs_context}\n\n"
        f"위 자료를 바탕으로 12개 법률 항목의 '{business_type}' 업종 '{district}' 지역 창업 리스크를 평가하세요. "
        "각 항목의 '—' 뒤에 적힌 검토 포인트를 반드시 확인하세요."
    )

    batch_results: list[dict] = []
    try:
        llm = get_fast_llm().with_structured_output(LegalBatchOutput)
        result: LegalBatchOutput = await llm.ainvoke(
            [
                SystemMessage(content=system_content),
                HumanMessage(content=user_content),
            ]
        )
        seen = set()
        for item in result.items:
            if item.type in _BATCH_TYPES and item.type not in seen:
                batch_results.append(
                    {
                        "type": item.type,
                        "level": item.level,
                        "summary": item.summary,
                        "articles": _extract_articles(docs_map.get(item.type, [])),
                        "recommendation": item.recommendation,
                        "is_fallback": False,
                    }
                )
                seen.add(item.type)
        # 누락된 항목 caution으로 보완
        for t in _BATCH_TYPES:
            if t not in seen:
                batch_results.append(
                    {
                        "type": t,
                        "level": "caution",
                        "summary": "LLM 응답 누락 — 수동 검토 필요",
                        "articles": [],
                        "recommendation": "전문가 상담 권장",
                        "is_fallback": True,
                    }
                )
        logger.info(f"[legal_node] 배치 LLM 완료 (Structured Output) - {len(batch_results)}개 항목 처리")
    except Exception as e:
        logger.error(f"[legal_node] 배치 LLM 실패: {e} - 전체 caution 처리")
        batch_results = [
            {
                "type": t,
                "level": "caution",
                "summary": f"LLM 분석 실패: {e}",
                "articles": [],
                "recommendation": "전문가 상담 권장",
                "is_fallback": True,
            }
            for t in _BATCH_TYPES
        ]

    # batch_results를 타입별로 인덱싱
    _batch_map = {r["type"]: r for r in batch_results}

    risks = [
        _batch_map.get(
            "franchise_law",
            {
                "type": "franchise_law",
                "level": "caution",
                "summary": "",
                "articles": [],
                "recommendation": "",
                "is_fallback": True,
            },
        ),
        _batch_map.get(
            "commercial_lease_law",
            {
                "type": "commercial_lease_law",
                "level": "caution",
                "summary": "",
                "articles": [],
                "recommendation": "",
                "is_fallback": True,
            },
        ),
        zoning_result,
        _batch_map.get(
            "food_hygiene",
            {
                "type": "food_hygiene",
                "level": "caution",
                "summary": "",
                "articles": [],
                "recommendation": "",
                "is_fallback": True,
            },
        ),
        _batch_map.get(
            "safety_regulation",
            {
                "type": "safety_regulation",
                "level": "caution",
                "summary": "",
                "articles": [],
                "recommendation": "",
                "is_fallback": True,
            },
        ),
        ftc_result,
        _batch_map.get(
            "building_law",
            {
                "type": "building_law",
                "level": "caution",
                "summary": "",
                "articles": [],
                "recommendation": "",
                "is_fallback": True,
            },
        ),
        _batch_map.get(
            "fire_safety_law",
            {
                "type": "fire_safety_law",
                "level": "caution",
                "summary": "",
                "articles": [],
                "recommendation": "",
                "is_fallback": True,
            },
        ),
        _batch_map.get(
            "labor_law",
            {
                "type": "labor_law",
                "level": "caution",
                "summary": "",
                "articles": [],
                "recommendation": "",
                "is_fallback": True,
            },
        ),
        _batch_map.get(
            "vat_law",
            {
                "type": "vat_law",
                "level": "caution",
                "summary": "",
                "articles": [],
                "recommendation": "",
                "is_fallback": True,
            },
        ),
        _batch_map.get(
            "privacy_law",
            {
                "type": "privacy_law",
                "level": "caution",
                "summary": "",
                "articles": [],
                "recommendation": "",
                "is_fallback": True,
            },
        ),
        _batch_map.get(
            "accessibility_law",
            {
                "type": "accessibility_law",
                "level": "caution",
                "summary": "",
                "articles": [],
                "recommendation": "",
                "is_fallback": True,
            },
        ),
        _batch_map.get(
            "sewage_law",
            {
                "type": "sewage_law",
                "level": "caution",
                "summary": "",
                "articles": [],
                "recommendation": "",
                "is_fallback": True,
            },
        ),
        _batch_map.get(
            "fair_trade_law",
            {
                "type": "fair_trade_law",
                "level": "caution",
                "summary": "",
                "articles": [],
                "recommendation": "",
                "is_fallback": True,
            },
        ),
    ]

    # §13 드로어 체크리스트 필드 — 각 risk 의 articles 에서 휴리스틱으로 파생
    # 14개 risks 개수 invariant 유지; checklist 는 항상 1개 이상 반환
    for _r in risks:
        if isinstance(_r, dict) and "checklist" not in _r:
            _r["checklist"] = _derive_checklist_from_articles(
                _r.get("articles") or [],
                _r.get("type", "unknown"),
            )

    # 의무 법률 최소 위험도 보정 — 미이행 시 영업불가인 법률은 safe로 내려가지 않도록 강제
    _MUST_CAUTION = {"franchise_law", "commercial_lease_law", "vat_law", "privacy_law", "fair_trade_law"}
    _MUST_DANGER = {"food_hygiene", "building_law", "fire_safety_law", "labor_law", "safety_regulation"}
    for _r in risks:
        if not isinstance(_r, dict):
            continue
        rtype = _r.get("type", "")
        level = _r.get("level", "")
        if rtype in _MUST_DANGER and level != "danger":
            _r["level"] = "danger"
        elif rtype in _MUST_CAUTION and level == "safe":
            _r["level"] = "caution"

    # 벌칙 조문 본문을 recommendation에 자동 추가
    _enrich_penalty_info(risks)

    # overall_level: danger 하나라도 있으면 danger, caution 있으면 caution, 전부 safe면 safe
    levels = [r.get("level", "caution") for r in risks if isinstance(r, dict)]
    if "danger" in levels:
        overall_level = "danger"
    elif "caution" in levels:
        overall_level = "caution"
    else:
        overall_level = "safe"

    precedents = franchise_prec + lease_prec + food_prec + safety_prec + building_prec + labor_prec
    legal_info = (legal_info_docs + precedents) or [
        {"content": r["summary"], "metadata": {"source": r["type"], "relevance": 1.0}} for r in risks
    ]

    analysis = dict(state.get("analysis_results") or {})
    analysis["legal_risks"] = risks
    analysis["overall_legal_risk"] = overall_level

    # Redis 캐시 저장 — RAG 실패 시 빈 articles가 캐시되는 것을 방지
    # articles가 있는 리스크가 3개 미만이면 캐시하지 않음 (재실행 시 정상 결과 기대)
    _risks_with_articles = sum(1 for r in risks if r.get("articles"))
    try:
        if _redis is not None and _risks_with_articles >= 3:
            await _redis.set(
                cache_key,
                json.dumps(
                    {"legal_risks": risks, "legal_info": legal_info, "overall_legal_risk": overall_level},
                    ensure_ascii=False,
                ),
                ex=_CACHE_TTL,
            )
            logger.info(f"[legal_node] 캐시 저장: {cache_key} (TTL: {_CACHE_TTL}s)")
        elif _redis is not None:
            logger.warning(f"[legal_node] articles 부족({_risks_with_articles}/14) - 캐시 저장 건너뜀 (RAG 실패 의심)")
    except Exception as e:
        logger.warning(f"[legal_node] Redis 캐시 저장 실패 (무시하고 계속): {e}")
    finally:
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass

    _high_count = sum(1 for r in risks if isinstance(r, dict) and r.get("level") == "danger")
    legal_attr = build_attribution(
        agent_id="legal",
        display_name="법률 리스크",
        kind="RAG",
        sources=[f"legal_rag_chunks ({_TOTAL_CHUNK_COUNT})"],
        verdict=f"14 법률 위험도 · overall {overall_level}",
        reasoning=f"14개 법률 조항 RAG 검색 (chunks 3775). {_high_count}건 HIGH 위험.",
        confidence=0.85,
    )
    analysis["legal_result"] = {"agent_attribution": legal_attr}

    return {
        **state,
        "analysis_results": analysis,
        "legal_info": legal_info,
        "overall_legal_risk": overall_level,
        "agent_attribution": legal_attr,
    }


async def legal_node(state) -> dict:
    """
    법규검토 Agent 메인 노드 — LangGraph에서 호출되는 진입점.

    2단계 풀 파이프라인(_run_legal_pipeline)을 직접 await로 실행.
    Pydantic AgentState / TypedDict AgentState 양쪽 모두 지원.

    파이프라인:
      Phase 1: RAG×13 + 판례×4 + FTC API + zoning 병렬 (총 18개 I/O)
      Phase 2: LLM check×12 병렬
    """
    if not isinstance(state, dict):
        state = state.model_dump()
    return await _run_legal_pipeline(state)
