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

from src.agents.nodes._attribution_helpers import build_attribution
from src.config.constants import (
    BIZ_NORMALIZE,
    BIZ_TYPE_LABEL,
    DISTRICT_ZONE_MAP,
    ZONING_RULES,
)
from src.config.settings import settings
from src.schemas.state import AgentState
from src.services.ftc_franchise import FtcFranchiseClient

# LawApiClient: SP2 후 사용 안 함. 외부 API fallback 필요 시 다시 import.
# Legacy single-LLM batch 경로 (Phase 1 RAG + chunk_compressor + LegalBatchOutput)는
# 2026-05-02 룰엔진 단일 모드 전환 시 제거. 복귀 필요 시 git history 참조.

logger = logging.getLogger(__name__)

# 전체 조문 원본 인덱스 — chunks.json에서 (source, article) → 전체 본문 조립
# RAG는 "어떤 조문이 관련 있는지" 식별용으로만 사용하고, 실제 표시 본문은 여기서 가져옴
_ARTICLE_FULL_TEXT: dict[tuple[str, str], str] = {}
_TOTAL_CHUNK_COUNT: int = 0  # chunks.json 로드 시 실제 청크 수 저장
_CATEGORY_TO_SOURCES: dict[str, list[str]] = {}  # category → source 파일명 매핑
# uvicorn 멀티 워커 + 첫 요청 동시 진입 시 chunks.json 중복 로드 방지
_ARTICLE_INDEX_LOCK = __import__("threading").Lock()

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
    (["학교환경위생", "정화구역", "학교보건법"], "학교정화", "학교정화구역 내 영업제한 대상 확인", True),
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
    "school_zone": "학교보건법",
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
    "school_zone": [
        {"text": "출점 후보지에서 가장 가까운 학교까지의 거리 측정", "isRequired": True},
        {"text": "절대정화구역(50m)/상대정화구역(200m) 해당 여부 확인", "isRequired": True},
        {
            "text": "상대정화구역 내 주점은 학교환경위생정화위원회 심의 신청",
            "isRequired": False,
        },
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


def _make_fallback_risk(
    type_name: str,
    summary: str = "",
    recommendation: str = "",
) -> dict:
    """SP4: 통일된 fallback risk dict 생성 (15+ 군데 verbose 중복 제거)."""
    return {
        "type": type_name,
        "level": "caution",
        "summary": summary,
        "articles": [],
        "recommendation": recommendation,
        "is_fallback": True,
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
    """chunks.json을 읽어 조문별 전체 본문 인덱스를 구축합니다.

    동시 첫 요청에서 중복 로드 + 부분 채워진 dict 노출을 막기 위해 lock 사용.
    """
    global _ARTICLE_FULL_TEXT, _TOTAL_CHUNK_COUNT, _CATEGORY_TO_SOURCES
    if _ARTICLE_FULL_TEXT:
        return  # 이미 로드됨 (lock 외부 빠른 경로)
    with _ARTICLE_INDEX_LOCK:
        if _ARTICLE_FULL_TEXT:
            return  # double-checked locking
        from pathlib import Path

        chunks_path = (
            Path(__file__).resolve().parent.parent.parent.parent / "data" / "legal" / "processed" / "chunks.json"
        )
        if not chunks_path.exists():
            logger.warning(f"[legal_node] chunks.json 없음: {chunks_path}")
            return
        with open(chunks_path, encoding="utf-8") as f:
            chunks = json.load(f)
        _TOTAL_CHUNK_COUNT = len(chunks)

        # 이하 lock 보호 영역 — global state 변경
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
        _next_art_pattern = re.compile(r"(?=제\d+조(?:의\d+)?\s*[\(（])")
        _chapter_pattern = re.compile(r"\n제\d+장\s")

        for key, pairs in grouped.items():
            _, article = key
            pairs.sort(key=lambda x: x[0])
            raw = "\n".join(t for _, t in pairs)

            art_start_re = re.compile(rf"(?={re.escape(article)}\s*[\(（])")
            match = art_start_re.search(raw)
            if match:
                text_from_article = raw[match.start() :]
                all_matches = list(_next_art_pattern.finditer(text_from_article))
                if len(all_matches) > 1:
                    text_from_article = text_from_article[: all_matches[1].start()].strip()
                _noise_patterns = (
                    _chapter_pattern,
                    re.compile(r"\n제\d+편\s"),
                    re.compile(r"\n부칙[\s<]"),
                    re.compile(r"\n\[별표"),
                    re.compile(r"\n[가-힣\s]+(?:법|령|규칙|법률)\s*$", re.MULTILINE),
                )
                for noise_pat in _noise_patterns:
                    noise_match = noise_pat.search(text_from_article)
                    if noise_match:
                        text_from_article = text_from_article[: noise_match.start()].strip()
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
    법률 검토 파이프라인 — 룰엔진 단일 경로 (2026-05-02 전환).

    흐름:
      1. brand/district/business_type/store_area/lat/lon 추출 + 정규화
      2. Redis 캐시 lookup (v7 prefix — school_zone + 좌표 키 포함)
      3. zoning + ftc 병렬 실행
      4. orchestrator.run_legal_evaluation — 9 룰 + 4 specialist 병렬 (13 dict)
         실패 시 → 13 항목 caution fallback (_make_fallback_risk)
      5. risks = orchestrator 13 + zoning + ftc = 15 (인덱스 기반 다운스트림 호환)
      6. checklist 보강 + _enrich_penalty_info + overall_legal_risk 계산
      7. Redis 캐시 저장
    """

    import redis.asyncio as aioredis

    from src.config.settings import settings

    brand = state.get("brand_name") or "해당 브랜드"
    district = state.get("target_district", "")
    business_type = state.get("business_type", "")
    # store_area: 룰 엔진(rule_safety_regulation/rule_accessibility 등)에서 면적 의존.
    # AgentState 누락/None 방어 — default 15.0 평.
    store_area = state.get("store_area", 15.0) or 15.0
    # 출점 후보지 좌표 — rule_school_zone 트리거. 주점이 아니면 미사용.
    _raw_lat = state.get("lat")
    _raw_lon = state.get("lon")
    try:
        lat_val: float | None = float(_raw_lat) if _raw_lat is not None else None
    except (TypeError, ValueError):
        lat_val = None
    try:
        lon_val: float | None = float(_raw_lon) if _raw_lon is not None else None
    except (TypeError, ValueError):
        lon_val = None

    # 캐시 키 정규화 — brand/district/business_type 모두 strip+lowercase
    # + store_area 는 소수 1자리 반올림으로 동일 키 보장.
    _norm_brand = (brand or "").strip().lower()[:100]
    _norm_district = (district or "").strip()
    _normalized_biz = BIZ_NORMALIZE.get(business_type.lower(), business_type)
    _norm_biz = _normalized_biz.strip()

    # Redis 캐시 조회 — 동일 조합 재요청 시 즉시 반환
    _CACHE_TTL = 86400  # 24시간
    # v7: school_zone 룰 추가(13 룰 + zoning + ftc = 15 risks) + lat/lon 좌표 키 포함.
    # v8: territory_radius_m 사용자 입력 추가 (가맹사업법 제12조의4 정량 룰).
    # 좌표 누락 시 "none" 으로 정규화 — 좌표·영업구역 입력 시 자동 invalidation.
    _coord_key = f"{lat_val:.5f},{lon_val:.5f}" if lat_val is not None and lon_val is not None else "none"
    _territory_key = state.get("territory_radius_m") or "none"
    cache_key = f"v8:legal:{_norm_brand}:{_norm_district}:{_norm_biz}:{float(store_area):.1f}:{_coord_key}:{_territory_key}"
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
                _cached_caution = sum(
                    1 for r in (legal_risks or []) if isinstance(r, dict) and r.get("level") == "caution"
                )
                _cached_safe = sum(1 for r in (legal_risks or []) if isinstance(r, dict) and r.get("level") == "safe")
                _cached_danger_types = [
                    r.get("type", "?")
                    for r in (legal_risks or [])
                    if isinstance(r, dict) and r.get("level") == "danger"
                ]
                _cached_total_arts = sum(
                    len(r.get("articles") or []) for r in (legal_risks or []) if isinstance(r, dict)
                )
                # 사용자 친화 라벨
                _CACHE_LABEL_KO = {
                    "franchise_law": "가맹사업법",
                    "commercial_lease_law": "상가임대차보호법",
                    "food_hygiene": "식품위생법",
                    "safety_regulation": "다중이용업소 안전법",
                    "building_law": "건축법",
                    "fire_safety_law": "소방시설법",
                    "labor_law": "근로기준법",
                    "vat_law": "부가가치세법",
                    "privacy_law": "개인정보보호법",
                    "accessibility_law": "장애인편의법",
                    "sewage_law": "하수도법",
                    "school_zone": "학교환경위생정화구역",
                    "fair_trade_law": "공정거래법",
                    "zoning_regulation": "용도지역",
                    "ftc_franchise": "공정위 정보공개서",
                }
                _cached_danger_labels = [_CACHE_LABEL_KO.get(t, t) for t in _cached_danger_types]
                _cached_overall_label = {"danger": "위험", "caution": "주의", "safe": "안전"}.get(
                    overall_cached, overall_cached
                )
                if _cached_high == 0:
                    _cached_summary = (
                        f"별도 위험 사항은 발견되지 않았으나, 주의 항목 {_cached_caution}건의 사전 확인을 권장합니다."
                    )
                else:
                    _cached_summary = (
                        f"특히 {', '.join(_cached_danger_labels[:3])}"
                        f"{' 등' if len(_cached_danger_labels) > 3 else ''} "
                        f"미이행 시 영업정지·과태료·형사처벌 위험이 있습니다."
                    )
                _cached_reasoning = (
                    f"창업 관련 15개 법률을 검토한 결과 종합 위험도는 '{_cached_overall_label}'로 판정되었습니다. "
                    f"전체 15개 항목 중 위험 {_cached_high}개, 주의 {_cached_caution}개, 안전 {_cached_safe}개로 "
                    f"분류되었으며, 각 법률의 핵심 조문 총 {_cached_total_arts}개를 근거로 검토했습니다. "
                    f"{_cached_summary}"
                )
                cached_legal_attr = build_attribution(
                    agent_id="legal",
                    display_name="법률 리스크",
                    kind="RAG",
                    sources=[
                        f"legal_rag_chunks ({_TOTAL_CHUNK_COUNT})",
                        "ftc_brand_franchise",
                        "ftc_api",
                    ],
                    verdict=(
                        f"종합 위험도: {_cached_overall_label} "
                        f"(위험 {_cached_high}건 / 주의 {_cached_caution}건 / 안전 {_cached_safe}건)"
                    ),
                    reasoning=_cached_reasoning,
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

    # zoning + ftc 병렬 실행 — 외부 I/O 없는 zoning 규칙 + FTC DB 조회
    # rule engine specialist (franchise/privacy)에 ftc_data 주입을 위해 사전 실행.
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

    _zoning_raw, _ftc_raw = await asyncio.gather(
        check_zoning_regulation(state),
        check_ftc_franchise(state),
        return_exceptions=True,
    )
    zoning_result = (
        _zoning_raw
        if isinstance(_zoning_raw, dict)
        else {
            "type": "zoning_regulation",
            "level": "caution",
            "summary": f"zoning 평가 오류: {_zoning_raw}",
            "articles": [],
            "recommendation": "",
            "is_fallback": True,
        }
    )
    ftc_result = _safe_ftc(_ftc_raw)

    # 룰엔진 결과 invariant 검증용 — orchestrator._RULE_ENGINE_ORDER 와 동일 13종.
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
        "school_zone",
        "sewage_law",
        "fair_trade_law",
    ]

    # 조문 인덱스 로드 (벌칙 매핑/체크리스트 보강에 활용; 최초 1회만)
    _load_article_index()

    # ------------------------------------------------------------------
    # 룰엔진 단일 경로: 8 결정적 룰 + 4 specialist (자체 RAG) 병렬 평가 → 12 dict.
    # 실패 시 12 항목 caution fallback (legacy LLM batch 경로 없음).
    # 스펙: docs/superpowers/specs/2026-05-02-legal-rule-engine-design.md
    # ------------------------------------------------------------------
    batch_results: list[dict] = []
    try:
        from src.agents.legal.orchestrator import run_legal_evaluation

        logger.info(f"[legal_node] rule engine 실행 (brand={_norm_brand[:20]}, biz={_norm_biz}, area={store_area})")
        engine_results = await run_legal_evaluation(
            brand=brand,
            business_type=business_type,
            district=district,
            store_area_pyeong=float(store_area),
            ftc_data=ftc_result if isinstance(ftc_result, dict) else None,
            lat=lat_val,
            lon=lon_val,
            territory_radius_m=state.get("territory_radius_m"),
        )
        _rule_seen: set[str] = set()
        for r in engine_results:
            if not isinstance(r, dict):
                continue
            rtype = r.get("type", "")
            if rtype in _BATCH_TYPES and rtype not in _rule_seen:
                batch_results.append(r)
                _rule_seen.add(rtype)
        for _t in _BATCH_TYPES:
            if _t not in _rule_seen:
                batch_results.append(
                    _make_fallback_risk(
                        _t,
                        summary="rule engine 결과 누락 - 수동 검토 필요",
                        recommendation="전문가 상담 권장",
                    )
                )
        logger.info(f"[legal_node] rule engine 완료 - {len(batch_results)}개 항목 (12 expected)")
    except Exception as e:
        # 룰엔진 전체 실패 → 12 항목 caution fallback (legacy 경로 없음)
        logger.error(f"[legal_node] rule engine 실패 - 전체 caution fallback: {e}")
        batch_results = [
            _make_fallback_risk(
                t,
                summary=f"rule engine 평가 실패: {e}",
                recommendation="전문가 상담 권장",
            )
            for t in _BATCH_TYPES
        ]
    # batch_results를 타입별로 인덱싱
    _batch_map = {r["type"]: r for r in batch_results}

    # SP4: 15 risks 구성 — _batch_map(13 룰 항목) + zoning_result + ftc_result
    # 순서는 다운스트림(인덱스 기반) 호환을 위해 유지
    def _r(type_name: str) -> dict:
        return _batch_map.get(type_name, _make_fallback_risk(type_name))

    risks = [
        _r("franchise_law"),
        _r("commercial_lease_law"),
        zoning_result,
        _r("food_hygiene"),
        _r("safety_regulation"),
        ftc_result,
        _r("building_law"),
        _r("fire_safety_law"),
        _r("labor_law"),
        _r("vat_law"),
        _r("privacy_law"),
        _r("accessibility_law"),
        _r("school_zone"),
        _r("sewage_law"),
        _r("fair_trade_law"),
    ]

    # §13 드로어 체크리스트 필드 — 각 risk 의 articles 에서 휴리스틱으로 파생
    # 15개 risks 개수 invariant 유지; checklist 는 항상 1개 이상 반환
    for _r in risks:
        if isinstance(_r, dict) and "checklist" not in _r:
            _r["checklist"] = _derive_checklist_from_articles(
                _r.get("articles") or [],
                _r.get("type", "unknown"),
            )

    # 룰엔진은 결정적이라 safe 보정 불필요 (legacy LLM batch 경로 _SAFE_FLOOR 후처리 제거).

    # 벌칙 조문 본문을 recommendation에 자동 추가
    _enrich_penalty_info(risks)

    # SP4: overall_level 결정 — 핵심 카테고리 + 임계값 룰
    # 핵심 = 미이행 시 영업정지/형사처벌이 직접적인 영역
    # (식품위생/소방/건축 + 학교환경위생정화구역)
    # 핵심 1개라도 danger → overall=danger
    # 비핵심 danger 2개 이상 → overall=danger (다중 위험)
    # 그 외 danger 1개 또는 caution 존재 → caution
    # 전부 safe → safe
    _CRITICAL_TYPES = {"food_hygiene", "fire_safety_law", "building_law", "school_zone"}

    danger_types = [r.get("type", "") for r in risks if isinstance(r, dict) and r.get("level") == "danger"]
    has_critical_danger = any(t in _CRITICAL_TYPES for t in danger_types)
    has_caution = any(r.get("level") == "caution" for r in risks if isinstance(r, dict))

    if has_critical_danger or len(danger_types) >= 2:
        overall_level = "danger"
    elif danger_types or has_caution:
        overall_level = "caution"
    else:
        overall_level = "safe"

    # 룰엔진 단일 모드 — RAG 판례 docs 없음. risks summary 로 legal_info 구성.
    legal_info = [
        {"content": r["summary"], "metadata": {"source": r["type"], "relevance": 1.0}}
        for r in risks
        if isinstance(r, dict) and r.get("summary")
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
            logger.warning(
                f"[legal_node] articles 부족({_risks_with_articles}/{len(risks)}) - 캐시 저장 건너뜀 (RAG 실패 의심)"
            )
    except Exception as e:
        logger.warning(f"[legal_node] Redis 캐시 저장 실패 (무시하고 계속): {e}")
    finally:
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass

    _high_count = sum(1 for r in risks if isinstance(r, dict) and r.get("level") == "danger")
    _caution_count = sum(1 for r in risks if isinstance(r, dict) and r.get("level") == "caution")
    _safe_count = sum(1 for r in risks if isinstance(r, dict) and r.get("level") == "safe")
    _danger_types = [r.get("type", "?") for r in risks if isinstance(r, dict) and r.get("level") == "danger"]
    _total_articles = sum(len(r.get("articles") or []) for r in risks if isinstance(r, dict))

    # 사용자 친화 라벨 (법 모르는 사람용)
    _LAW_LABEL_KO = {
        "franchise_law": "가맹사업법",
        "commercial_lease_law": "상가임대차보호법",
        "food_hygiene": "식품위생법",
        "safety_regulation": "다중이용업소 안전법",
        "building_law": "건축법",
        "fire_safety_law": "소방시설법",
        "labor_law": "근로기준법",
        "vat_law": "부가가치세법",
        "privacy_law": "개인정보보호법",
        "accessibility_law": "장애인편의법",
        "sewage_law": "하수도법",
        "school_zone": "학교환경위생정화구역",
        "fair_trade_law": "공정거래법",
        "zoning_regulation": "용도지역",
        "ftc_franchise": "공정위 정보공개서",
    }
    _danger_labels = [_LAW_LABEL_KO.get(t, t) for t in _danger_types]
    _overall_label = {"danger": "위험", "caution": "주의", "safe": "안전"}.get(overall_level, overall_level)

    if _high_count == 0:
        _summary_line = f"별도 위험 사항은 발견되지 않았으나, 주의 항목 {_caution_count}건의 사전 확인을 권장합니다."
    else:
        _summary_line = (
            f"특히 {', '.join(_danger_labels[:3])}"
            f"{' 등' if len(_danger_labels) > 3 else ''} "
            f"미이행 시 영업정지·과태료·형사처벌 위험이 있습니다."
        )

    _reasoning = (
        f"창업 관련 15개 법률을 검토한 결과 종합 위험도는 '{_overall_label}'로 판정되었습니다. "
        f"전체 15개 항목 중 위험 {_high_count}개, 주의 {_caution_count}개, 안전 {_safe_count}개로 분류되었으며, "
        f"각 법률의 핵심 조문 총 {_total_articles}개를 근거로 검토했습니다. "
        f"{_summary_line}"
    )
    legal_attr = build_attribution(
        agent_id="legal",
        display_name="법률 리스크",
        kind="RAG",
        sources=[
            f"legal_rag_chunks ({_TOTAL_CHUNK_COUNT})",
            "ftc_brand_franchise",
            "ftc_api",
        ],
        verdict=(
            f"종합 위험도: {_overall_label} (위험 {_high_count}건 / 주의 {_caution_count}건 / 안전 {_safe_count}건)"
        ),
        reasoning=_reasoning,
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
    법규검토 Agent 메인 노드 — LangGraph 진입점.

    파이프라인(_run_legal_pipeline) 단일 룰엔진 경로:
      - zoning + ftc 병렬
      - 9 결정적 룰 + 4 specialist (RAG+LLM) 병렬 평가 → 13 risks
      - + zoning + ftc = 15 risks
      - Pydantic / TypedDict AgentState 양쪽 지원 (lat/lon 좌표 입력 시 학교 거리 룰 활성)
    """
    if not isinstance(state, dict):
        state = state.model_dump()
    return await _run_legal_pipeline(state)
