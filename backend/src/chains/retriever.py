"""
RAG 문서 검색 — 하이브리드 (벡터 유사도 + BM25 키워드) + RRF 결합 + HyDE 쿼리 확장 + Cross-encoder Reranker
"""

import asyncio
import datetime
import json
import logging
import math
import os
import time
from pathlib import Path

from ..database.vector_db import LegalVectorDB

logger = logging.getLogger(__name__)


def _trace_candidate(doc_obj, score, rank: int, max_preview: int = 120) -> dict:
    """벡터 검색 후보 1건 → trace dict 변환. doc_obj는 langchain Document."""
    meta = getattr(doc_obj, "metadata", {}) or {}
    content = getattr(doc_obj, "page_content", "") or ""
    return {
        "rank": rank,
        "chunk_id": meta.get("chunk_id"),
        "score": round(float(score), 4) if score is not None else None,
        "source": meta.get("source"),
        "article": meta.get("article"),
        "preview": content[:max_preview],
    }


def _trace_bm25_candidate(idx: int, score: float, rank: int, bm25_docs: list, max_preview: int = 120) -> dict:
    """BM25 후보 1건 (chunk_idx, score) → trace dict."""
    if 0 <= idx < len(bm25_docs):
        text, meta = bm25_docs[idx]
    else:
        text, meta = "", {}
    return {
        "rank": rank,
        "chunk_idx": idx,
        "chunk_id": (meta or {}).get("chunk_id"),
        "score": round(float(score), 4),
        "source": (meta or {}).get("source"),
        "article": (meta or {}).get("article"),
        "preview": (text or "")[:max_preview],
    }


def _trace_merged_doc(doc: dict, rank: int, max_preview: int = 120) -> dict:
    """RRF/최종 doc dict → trace dict."""
    meta = doc.get("metadata", {}) or {}
    return {
        "rank": rank,
        "chunk_id": meta.get("chunk_id"),
        "source": meta.get("source"),
        "article": meta.get("article"),
        "relevance": meta.get("relevance"),
        "is_parent": bool(meta.get("is_parent", False)),
        "preview": (doc.get("content") or "")[:max_preview],
    }


def _write_trace_jsonl(trace: dict) -> None:
    """trace 1건을 시간 단위 JSONL 파일에 append. 실패는 무시 (warning).

    파일명: rag_trace_YYYYMMDD_HH.jsonl (UTC).
    """
    try:
        from src.config.settings import settings as _settings

        if not _settings.rag_trace_enabled:
            return
        trace_dir = Path(_settings.rag_trace_dir)
        trace_dir.mkdir(parents=True, exist_ok=True)
        fname = trace_dir / f"rag_trace_{datetime.datetime.utcnow().strftime('%Y%m%d_%H')}.jsonl"
        with open(fname, "a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"[rag_trace] JSONL 기록 실패 (무시): {e}")


# S-5 Parent-child: chunk_id → parent_text 매핑 모듈 top-level pre-load (race condition 회피)
def _load_parent_articles_eager() -> dict:
    path = Path(__file__).resolve().parent.parent.parent / "data" / "legal" / "processed" / "parent_articles.json"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"[retriever] parent_articles 로드: {len(data)} 매핑")
        return data
    except Exception as e:
        logger.warning(f"[retriever] parent_articles 로드 실패: {e}")
        return {}


_PARENT_ARTICLES: dict = _load_parent_articles_eager()


# HyDE용 일상 용어 → 법률 용어 매핑 (LLM 호출 없이 빠르게 치환)
_LEGAL_SYNONYM_MAP: dict[str, str] = {
    "월세": "차임 월 차임",
    "보증금": "임대차보증금 환산보증금",
    "알바": "단시간근로자 기간제근로자",
    "파트타임": "단시간근로자",
    "야간수당": "야간근로 가산임금",
    "주말수당": "휴일근로 가산임금",
    "퇴직금": "퇴직급여 퇴직연금",
    "CCTV": "영상정보처리기기",
    "고객정보": "개인정보 정보주체",
    "영업허가": "영업허가 영업신고 영업등록",
    "소방점검": "작동기능점검 종합정밀점검 자체점검",
    "비상구": "피난시설 비상구 안전시설",
    "장애인화장실": "장애인등편의시설 편의시설",
    "경사로": "장애인등편의시설 경사로 접근",
    "가맹비": "가맹금 가입비",
    "로열티": "가맹금 계약이행보증금",
    "본사 갑질": "불공정거래행위 거래강제 부당한 차별취급",
    "불법건축물": "위반건축물 이행강제금",
    "용도변경": "건축물 용도변경 근린생활시설",
    # 상가임대차 관련
    "권리금": "권리금 회수기회 보호 제10조의4",
    "임대료인상": "차임증감청구 차임증액",
    "환산보증금": "환산보증금 보증금 환산",
    "묵시적갱신": "묵시적갱신 계약갱신",
    # 근로기준법 관련
    "연장근로": "연장근로 가산임금 통상임금",
    "해고": "해고 경영상 이유 부당해고",
    "근로계약서": "근로조건 서면명시 제17조",
    # 개인정보보호법 관련
    "동의서": "개인정보 수집 이용 동의 제15조",
    "처리방침": "개인정보 처리방침 공개 제30조",
    # 건축법 관련
    "근린생활시설": "제1종근린생활시설 제2종근린생활시설",
    "건축허가": "건축허가 건축신고 제11조",
    # 하수도법 관련 — 일상용어와 법률용어 불일치 보정
    "배수설비": "배수설비 오수 하수 공공하수도 유입 개인하수처리시설",
    "폐수": "폐수배출시설 수질오염물질",
    "오수처리": "오수 하수 개인하수처리시설 배수설비 공공하수도 배수구역",
    "오수": "오수 하수 개인하수처리시설 배수설비",
    "유류분리기": "유분분리기 유류분리기 오수처리 그리스트랩 개인하수처리시설 배수설비",
    "그리스트랩설치": "그리스트랩 유류분리기 개인하수처리시설 배수설비 오수 배출",
    "하수도": "하수 오수 배수설비 개인하수처리시설 공공하수도 배수구역",
    # 가맹사업법 보강
    "정보공개서": "정보공개서 등록 제6조의2 제6조의3",
    "가맹계약": "가맹계약 체결 해제 제10조",
    "영업지역": "영업지역 설정 보장 제12조의4",
    "가맹금반환": "가맹금 반환 예치 제10조 제15조의2",
    "출점제한": "영업지역 출점 제한 동일업종 제12조의4",
    # 상가임대차 보강
    "차임": "차임 증감청구 증액 제11조",
    "보증금반환": "보증금 반환 임차인 명도",
    "명도": "명도 계약종료 인도 퇴거",
    # 식품위생법 보강
    "영업신고": "영업신고 영업허가 등록 제37조 제36조",
    "위생교육": "위생교육 식품접객업 제41조",
    "시설기준": "시설기준 조리시설 영업장 제36조",
    "영업자준수사항": "영업자 준수사항 위생관리 제3조 제44조",
    # 소방시설법 보강
    "자체점검": "자체점검 정기점검 작동기능점검 제22조",
    "소방시설설치": "소방시설 설치 의무 기준 제12조 제13조",
    # 근로기준법 보강
    "임금지급": "임금 지급 체불 제43조",
    "가산임금": "가산임금 연장근로 야간근로 휴일근로 제56조",
    "근로시간": "근로시간 소정근로 법정근로 제50조",
    "휴게시간": "휴게시간 휴게 제54조",
    "휴일": "유급휴일 주휴일 휴일근로 제55조",
    # 부가가치세법 보강
    "사업자등록": "사업자등록 신청 제8조",
    "세금계산서": "세금계산서 발급 의무 제32조 제34조",
    "간이과세자": "간이과세자 과세특례 공급대가 개인사업자 제61조 제63조",
    "간이과세": "간이과세자 공급대가 8천만원 개인사업자 과세표준",
    "과세특례": "간이과세자 과세특례 공급대가 과세표준 납부의무",
    # 개인정보보호법 보강
    "영상정보": "영상정보처리기기 CCTV 제25조 제25조의2",
    "처리방침공개": "개인정보 처리방침 수립 공개 제30조 제31조",
    # 건축법 보강
    "건축신고": "건축신고 건축허가 제14조 제11조",
    # 장애인편의법 보강
    "편의시설": "편의시설 설치 의무 대상시설 공공건물 공중이용시설 제7조 제8조",
    "편의시설기준": "편의시설 설치기준 경사로 출입구 제16조 제17조",
    "대상시설": "대상시설 편의시설 공공건물 공중이용시설 공동주택 제7조",
    "편의시설설치": "편의시설 설치 대상시설 규모 용도 제8조",
    # 공정거래법 보강
    "필수물품": "필수물품 공급 부당한 거래 제47조",
    # 가맹사업법 보강 (Issue A — 영업지역)
    "매장 근처": "영업지역 침해 부당한 영업지역 침해금지 제12조의4",
    "같은 브랜드": "동일 브랜드 출점 영업지역 침해 제12조의4",
    "반경 500m": "영업지역 설정 가맹계약서 영업지역 침해 제12조의4",
    # 가맹사업법 보강 (Issue B — 필수품목 구입강제)
    "필수품목": "불공정거래행위 구속조건부 거래 필수품목 가맹사업법 제12조",
    "구입강제": "불공정거래행위 구속조건부 거래 가맹사업법 제12조",
    "물품 구입 강제": "불공정거래행위 구속조건부 거래 가맹사업법 제12조",
    "독점 공급": "불공정거래행위 구속조건부 거래 가맹사업법 제12조",
    "식자재 독점": "불공정거래행위 구속조건부 거래 가맹사업법 제12조",
    "거래조건 강제": "불공정거래행위 구속조건부 거래 가맹사업법 제12조",
    # 가맹사업법 보강 (Issue C — 허위과장)
    "매출 보장": "허위 과장 정보제공 예상매출액 산정서 제9조",
    "5000만원 보장": "허위 과장 정보제공 예상매출액 제9조",
    "허위 매출": "허위 과장 정보제공 예상매출액 제9조 손해배상",
    "매출 과장": "허위 과장 정보제공 예상매출액 산정서 제9조",
    "허위 광고": "허위 과장 정보제공행위 가맹사업법 제9조",
    # 상가임대차보호법 보강
    "계약갱신": "계약갱신요구권 갱신거절 임대차기간 10년 제10조 제10조의2",
    "갱신요구권": "계약갱신요구권 갱신거절 임대차기간 제10조 제10조의2 제9조",
    "임대차 기간 최소": "기간을 정하지 아니한 임대차 1년 제9조 임대차기간",
    "묵시적 갱신": "임대인 갱신거절 통지 계약갱신 제10조",
    # 식품위생법 보강
    "카페 영업신고": "식품접객업 영업신고 영업허가 제37조 제36조",
    "음식점 영업허가": "식품접객업 영업허가 영업신고 제37조 제36조",
    "위생교육 미이수": "식품위생교육 의무 과태료 제41조 제101조",
    "사전 위생교육": "영업 전 식품위생교육 이수 의무 제41조",
    "영업정지": "영업허가취소 영업정지 제75조",
    "영업승계": "영업승계 지위승계 신고 제39조",
    "위해식품": "위해식품 판매금지 제4조",
    "영업자 준수사항": "영업자 준수사항 위반 제44조",
    # 건축법 보강
    "이행강제금": "위반건축물 이행강제금 제80조",
    # 근로기준법 보강
    "근로계약서 작성": "근로계약서 서면 명시 교부 의무 제17조",
    "근로계약서 미작성": "근로계약서 서면 명시 의무 벌금 제17조 제114조",
    "아르바이트": "단시간근로자 기간제근로자 근로계약서 제17조",
    "주휴수당": "유급주휴일 주휴수당 제55조",
    "임금 체불": "임금 지급 체불 제43조",
    "4대보험": "국민연금 건강보험 고용보험 산업재해보상보험 제17조",
    # 부가가치세법 보강
    "사업자등록증": "사업자등록 신청 발급 제8조",
    "과세 대상": "부가가치세 과세대상 재화 용역 제1조 제4조",
    # 개인정보보호법 보강
    "동의 없이 수집": "개인정보 수집 이용 동의 예외 제15조",
    "제3자 제공": "개인정보 제3자 제공 동의 제17조",
    "과태료 벌칙": "위반 과태료 벌칙 벌금",
    # 장애인편의법 보강
    "음식점 편의시설": "대상시설 편의시설 설치 의무 공중이용시설 제7조",
    # 하수도법 보강
    "그리스트랩": "유류분리기 오수처리시설 배수설비 제34조",
    "배수설비 설치": "배수설비 설치 기준 하수도법 제34조",
    # 소방시설법 보강
    "소방안전관리자": "소방안전관리자 선임 의무 자격 특정소방대상물 제24조 제25조",
    # 공정거래법 보강
    "거래강제": "거래강제 불공정거래행위 제45조 제40조",
    "과징금": "과징금 위반 시정명령 제55조",
    "공정거래위원회 신고": "공정거래위원회 신고 제80조",
    "부당 표시": "부당한 표시광고 불공정거래행위 제45조",
    "담합": "부당한 공동행위 담합 카르텔 제40조",
}


SOURCE_TO_SHORT_MAP = {
    "가맹사업거래": "가맹사업법",
    "상가건물 임대차보호법": "상가임대차보호법",
    "식품위생법": "식품위생법",
    "건축법": "건축법",
    "소방시설 설치 및 관리": "소방시설법",
    "근로기준법": "근로기준법",
    "최저임금법": "최저임금법",
    "부가가치세법": "부가가치세법",
    "개인정보 보호법": "개인정보보호법",
    "장애인": "장애인편의법",
    "편의증진": "장애인편의법",
    "하수도법": "하수도법",
    "물환경보전법": "물환경보전법",
    "독점규제 및 공정거래": "공정거래법",
}


class LegalDocumentRetriever:
    """법률 문서 검색기 — 하이브리드 RAG (벡터 + BM25 + RRF).

    싱글톤: 매 specialist 호출마다 새 인스턴스 생성 시 BM25 인덱스가
    매번 재구축되는 문제 차단 (구축 비용 ~30초). __new__ 기반 싱글톤 +
    BM25 인덱스/문서 리스트는 인스턴스 변수로 1회 빌드 후 재사용.
    """

    _instance: "LegalDocumentRetriever | None" = None

    def __new__(cls):
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._db = LegalVectorDB()
            inst._bm25_index = None
            inst._bm25_docs = None  # type: ignore[attr-defined]
            cls._instance = inst
        return cls._instance

    def __init__(self):
        # 싱글톤 — __new__ 에서 이미 _db / _bm25_index 초기화 완료. 추가 작업 불필요.
        pass

    # ------------------------------------------------------------------
    # HyDE (Hypothetical Document Embeddings) — LLM 가상 조문 생성
    # ------------------------------------------------------------------

    @staticmethod
    async def _expand_query_hybrid(query: str) -> str:
        """하이브리드 쿼리 확장: 사전 키워드 + LLM 가상 조문 결합.

        1차: _LEGAL_SYNONYM_MAP 사전 기반 확장 (기존)
        2차: LLM으로 가상 법조문 생성 (HYDE_ENABLED 시)
        결합: [원문] ||| [사전 확장] ||| [가상 조문]

        폴백: LLM 실패/timeout 시 사전 결과만 반환.
        캐시: Redis v3:hyde:{hash} 24h TTL.
        """
        from src.config.settings import settings

        # 1차: 사전 기반 확장
        dict_expanded = LegalDocumentRetriever._hyde_expand(query)

        # HyDE 비활성이면 사전 결과만
        if not settings.hyde_enabled:
            return dict_expanded

        # 2차: LLM 가상 조문 생성
        import hashlib

        # SP3: 의미 동일 + 표기 차이 (공백/대소문자/구두점) 쿼리는 같은 캐시 히트
        import re

        normalized = re.sub(r"\s+", " ", query.lower()).strip()
        normalized = re.sub(r"[?!.,()\[\]{}\"']", "", normalized)
        cache_key = f"v3:hyde:{hashlib.sha256(normalized.encode()).hexdigest()[:32]}"

        # Redis 캐시 조회
        hyde_text = None
        _redis = None
        try:
            import redis.asyncio as aioredis

            _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            cached = await _redis.get(cache_key)
            if cached:
                hyde_text = cached
                logger.info(f"[HyDE] cache HIT: {cache_key[:20]}")
        except Exception as e:
            logger.warning(f"[HyDE] Redis 조회 실패: {e}")

        # 캐시 미스 -> LLM 호출
        if hyde_text is None:
            try:
                import asyncio
                from src.chains.prompts import HYDE_FEW_SHOT, HYDE_SYSTEM_PROMPT

                # Few-shot 메시지 구성
                messages = [{"role": "system", "content": HYDE_SYSTEM_PROMPT}]
                for ex in HYDE_FEW_SHOT:
                    messages.append({"role": "user", "content": ex["input"]})
                    messages.append({"role": "assistant", "content": ex["output"]})
                messages.append({"role": "user", "content": query})

                # SP3: 유효 키만 사용 (placeholder 거부) — env로 prefer 가능
                _ant_key = settings.anthropic_api_key or ""
                _oai_key = settings.openai_api_key or ""
                _ant_valid = _ant_key.startswith("sk-ant-")
                _oai_valid = _oai_key.startswith("sk-")
                _prefer = os.getenv("HYDE_PROVIDER", "auto").lower()  # "openai" | "anthropic" | "auto"

                # Anthropic SDK (claude-haiku-4.5)
                if _ant_valid and (_prefer == "anthropic" or (_prefer == "auto" and not _oai_valid)):
                    from anthropic import AsyncAnthropic

                    client = AsyncAnthropic(api_key=_ant_key)
                    resp = await asyncio.wait_for(
                        client.messages.create(
                            model="claude-haiku-4-5-20251001",
                            max_tokens=500,
                            system=HYDE_SYSTEM_PROMPT,
                            messages=[
                                {"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"
                            ],
                        ),
                        timeout=10.0,
                    )
                    hyde_text = resp.content[0].text.strip()
                # OpenAI (gpt-4o-mini)
                elif _oai_valid:
                    from openai import AsyncOpenAI

                    client = AsyncOpenAI(api_key=settings.openai_api_key)
                    resp = await asyncio.wait_for(
                        client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=messages,
                            max_tokens=500,
                            temperature=0,
                        ),
                        timeout=10.0,
                    )
                    hyde_text = resp.choices[0].message.content.strip()
                else:
                    logger.warning("[HyDE] API 키 없음 - 사전 결과만 반환")

                # Redis 캐시 저장
                if hyde_text and _redis:
                    try:
                        await _redis.setex(cache_key, 86400, hyde_text)
                    except Exception as e:
                        logger.warning(f"[HyDE] Redis 캐시 저장 실패: {e}")

                if hyde_text:
                    logger.info(f"[HyDE] LLM 생성 완료 ({len(hyde_text)}자)")

            except asyncio.TimeoutError:
                logger.warning("[HyDE] LLM timeout (5s) - 사전 결과만 반환")
                hyde_text = None
            except Exception as e:
                logger.warning(f"[HyDE] LLM 호출 실패: {e} - 사전 결과만 반환")
                hyde_text = None
            finally:
                if _redis:
                    try:
                        await _redis.aclose()
                    except Exception as e:
                        logger.warning(f"[HyDE] Redis aclose 실패: {e}")

        # 결합: 원문 + 사전 확장 + 가상 조문
        if hyde_text:
            return f"{dict_expanded} {hyde_text}"
        return dict_expanded

    # 청크가 인덱싱된 source 메타데이터 값.
    # SP2 후 두 종류의 source 형식이 공존:
    #   1) PDF chunks: parse_pdfs.py의 파일명 stem (전체 명칭)
    #   2) 법령_본문 chunks: build_law_chunks.py의 law_short_name (단축명, e.g. "가맹사업법")
    # Vector $in 매칭은 정확 일치만 → 두 형식 모두 명시 등록.
    FRANCHISE_LAW_SOURCES = [
        "가맹사업거래의 공정화에 관한 법률(법률)(제20712호)(20250121)",
        "가맹사업거래의 공정화에 관한 법률 시행령(대통령령)(제36220호)(20260324)",
        "가맹사업법",
        "가맹사업법 시행령",
        "가맹사업진흥법",
        "가맹사업진흥법 시행령",
    ]
    LEASE_LAW_SOURCES = [
        "상가건물 임대차보호법(법률)(제21065호)(20260102)",
        "상가건물 임대차보호법 시행령(대통령령)(제35947호)(20260102)",
        "서울시_2023_상가임대차_상담사례집_내지_전자책",
        "상가임대차법",
        "상가임대차법 시행령",
        "상가건물 임대차계약서상의 확정일자 부여 및 임대차 정보제공에 관한 규칙",
    ]
    # 조문 검색 전용 — 상담사례집 제외 (비조문 문서가 조문 검색 정확도를 낮춤)
    LEASE_LAW_STRICT_SOURCES = [
        "상가건물 임대차보호법(법률)(제21065호)(20260102)",
        "상가건물 임대차보호법 시행령(대통령령)(제35947호)(20260102)",
        "상가임대차법",
        "상가임대차법 시행령",
    ]
    MAPO_SOURCES = [
        "서울특별시 마포구 지역상권 상생협력에 관한 조례",
    ]
    FOOD_HYGIENE_SOURCES = [
        "식품위생법(법률)(제21065호)(20251001)",
        "식품위생법 시행규칙(총리령)(제02077호)(20260301)",
        "[한국외식업중앙회] 2026 위생교육교재 (표지 포함)",
        "식품위생법",
        "식품위생법 시행령",
        "식품위생법 시행규칙",
        "식품위생 분야 종사자의 건강진단 규칙",
    ]
    SAFETY_SOURCES = [
        "210226_ 「다중이용업소의 안전관리에 관한 특별법」업무처리 지침",
        "제4차(2024~2028) 다중이용업소 안전관리 기본계획(전문)",
        "다중이용업소법",
        "다중이용업소법 시행령",
        "다중이용업소법 시행규칙",
    ]
    BUILDING_LAW_SOURCES = [
        "건축법(법률)(20250101)",
        "건축법",
        "건축법 시행령",
        "건축법 시행규칙",
        "녹색건축법",
        "녹색건축법 시행령",
        "녹색건축법 시행규칙",
    ]
    FIRE_SAFETY_SOURCES = [
        "소방시설 설치 및 관리에 관한 법률(법률)(20250101)",
        "소방시설법",
        "소방시설법 시행령",
        "소방시설법 시행규칙",
        "소방시설공사업법",
        "소방시설공사업법 시행령",
        "소방시설공사업법 시행규칙",
    ]
    # 화재예방법 (소방안전관리자 선임 의무 등) — 화재예방법은 소방시설법과 별개 법률
    FIRE_PREVENTION_SOURCES = [
        "화재의 예방 및 안전관리에 관한 법률",
        "화재의 예방 및 안전관리에 관한 법률 시행령",
        "화재의 예방 및 안전관리에 관한 법률 시행규칙",
        "화재예방법",
        "화재예방법 시행령",
        "화재예방법 시행규칙",
    ]
    LABOR_LAW_SOURCES = [
        "근로기준법(법률)(20250101)",
        "최저임금법(법률)(제17326호)(20200526)",
        "근로기준법",
        "근로기준법 시행령",
        "근로기준법 시행규칙",
        "최저임금법",
        "최저임금법 시행령",
        "최저임금법 시행규칙",
    ]
    VAT_LAW_SOURCES = [
        "부가가치세법(법률)(제21065호)(20260102)",
        "부가가치세법",
        "부가가치세법 시행령",
        "부가가치세법 시행규칙",
        "외국인관광객면세규정",
        "영농기자재등면세규정",
    ]
    PRIVACY_LAW_SOURCES = [
        "개인정보 보호법(법률)(제20897호)(20251002)",
        "개인정보 보호법",
        "개인정보 보호법 시행령",
        "개인정보 보호위원회 직제",
        "개인정보 보호위원회 직제 시행규칙",
    ]
    ACCESSIBILITY_LAW_SOURCES = [
        "장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(법률)(제20594호)(20251221)",
        "장애인편의법",
        "장애인편의법 시행령",
        "장애인편의법 시행규칙",
    ]
    FAIR_TRADE_SOURCES = [
        "독점규제 및 공정거래에 관한 법률(법률)(제21066호)(20251001)",
        "공정거래법",
        "공정거래법 시행령",
        "공정거래법 시행규칙",
    ]
    SEWAGE_LAW_SOURCES = [
        "하수도법(법률)(제21065호)(20251001)",
        "물환경보전법(법률)(제21368호)(20260219)",
        "하수도법",
        "하수도법 시행령",
        "하수도법 시행규칙",
        "물환경보전법",
        "물환경보전법 시행령",
        "물환경보전법 시행규칙",
    ]
    LIQUOR_LAW_SOURCES = [
        "주세법(법률)(제20618호)(20250101)",
    ]

    # 관련성 임계값 — 이 점수 미만인 문서는 LLM 컨텍스트에서 제외
    RELEVANCE_THRESHOLD = 0.3

    # RRF 파라미터 — settings에서 외부화 (SP3). .env로 RRF_K/RRF_VECTOR_WEIGHT/RRF_BM25_WEIGHT 조정 가능.
    @property
    def _RRF_K(self) -> int:
        from src.config.settings import settings

        return settings.rrf_k

    @property
    def _VECTOR_WEIGHT(self) -> float:
        from src.config.settings import settings

        return settings.rrf_vector_weight

    @property
    def _BM25_WEIGHT(self) -> float:
        from src.config.settings import settings

        return settings.rrf_bm25_weight

    # Reranker — Cross-encoder. settings.rerank_enabled로 toggle.
    # 이전 baseline (MiniLM + 4배 중복) 측정 시 마이너스 → 비활성. SP3 후 재측정 권장.
    _reranker = None

    @property
    def _RERANK_ENABLED(self) -> bool:
        from src.config.settings import settings

        return settings.rerank_enabled

    @property
    def _RERANK_MODEL(self) -> str:
        from src.config.settings import settings

        return settings.rerank_model

    # Multi-Vector Q2Q (예상 질문 벡터 검색)
    _vq_index = None  # 지연 로딩

    # 오답 방지 필터 (Hard Negative Mining)
    _confusion_map = None  # 지연 로딩: {(law_keyword, wrong_article): {correct_articles}}

    # SP3: Kiwi 형태소 토크나이저 — BM25 한국어 정확도 향상
    # 의미 토큰만 보존 (조사/어미 제거): 명사/동사/형용사/부사/숫자/한자/외래어
    _BM25_KEEP_TAGS = (
        "NNG",  # 일반명사
        "NNP",  # 고유명사
        "NNB",  # 의존명사
        "NR",  # 수사
        "VV",  # 동사
        "VA",  # 형용사
        "MAG",  # 일반부사
        "MAJ",  # 접속부사
        "SL",  # 외국어
        "SN",  # 숫자
        "SH",  # 한자
    )
    _kiwi = None  # 지연 초기화 (모델 로드 ~100ms)

    @classmethod
    def _get_kiwi(cls):
        if cls._kiwi is None:
            from kiwipiepy import Kiwi

            cls._kiwi = Kiwi()
        return cls._kiwi

    @classmethod
    def _tokenize_korean(cls, text: str) -> list[str]:
        """SP3: Kiwi 형태소 분석으로 의미 토큰만 추출. 조사/어미 제거.

        예: "권리금을 회수할 수 있다" → ["권리금", "회수", "수", "있"]
        (이전: "권리금을", "회수할", "수", "있다" — 조사/어미 포함)
        """
        if not text:
            return []
        kiwi = cls._get_kiwi()
        return [tok.form for tok in kiwi.tokenize(text) if tok.tag in cls._BM25_KEEP_TAGS and len(tok.form) > 0]

    def _build_bm25_index(self) -> None:
        """chunks.json에서 BM25 인덱스를 메모리에 구축합니다."""
        if self._bm25_index is not None:
            return
        chunks_path = Path(__file__).resolve().parent.parent.parent / "data" / "legal" / "processed" / "chunks.json"
        if not chunks_path.exists():
            self._bm25_index = {}
            return

        with open(chunks_path, encoding="utf-8") as f:
            chunks = json.load(f)

        # 역인덱스: {토큰: [(chunk_idx, tf), ...]}
        # 문서: [(text, metadata), ...]
        self._bm25_docs: list[tuple[str, dict]] = []
        inv_index: dict[str, list[tuple[int, int]]] = {}
        self._bm25_doc_lens: list[int] = []
        for i, c in enumerate(chunks):
            text = c.get("text", "")
            meta = c.get("metadata", {})
            self._bm25_docs.append((text, meta))
            # SP3: Kiwi 형태소 토크나이저 (단순 split 대체)
            tokens = self._tokenize_korean(text)
            self._bm25_doc_lens.append(len(tokens))
            tf_map: dict[str, int] = {}
            for t in tokens:
                tf_map[t] = tf_map.get(t, 0) + 1
            for token, tf in tf_map.items():
                inv_index.setdefault(token, []).append((i, tf))

        self._bm25_index = inv_index
        self._bm25_doc_count = len(self._bm25_docs)
        self._bm25_avg_dl = sum(self._bm25_doc_lens) / max(len(self._bm25_doc_lens), 1)
        logger.info(f"[BM25] Kiwi 인덱스 구축 완료: 문서 {self._bm25_doc_count}, 평균 토큰 {self._bm25_avg_dl:.1f}")

    # 부칙(supplementary) 청크 패턴 — 본법의 적용례/경과조치/특례. 본문 article과 같은 번호를
    # 재사용하지만 의미가 다름 → 정답 article 본문을 BM25 상위에서 밀어내는 주범.
    _SUPPLEMENTARY_PATTERNS = (
        "경과조치)",
        "적용례)",
        "에 관한 경과조치",
        "에 관한 적용례",
        "에 관한 특례",
        "이 법 시행 당시",
        "이 법 시행 전에",
        "이 법 시행 이후",
        "이 영 시행 당시",
        "이 영 시행 전에",
        "이 영 시행 이후",
        "이 규칙 시행 당시",
        "이 규칙 시행 전에",
        "이 규칙 시행 이후",
        "종전법 시행 당시",
        "종전의 규정에 따라",
    )

    @classmethod
    def _is_supplementary_chunk(cls, text: str) -> bool:
        """부칙(적용례/경과조치/특례) 청크 여부. text 의 앞쪽 80자 기준."""
        head = text[:80] if text else ""
        return any(p in head for p in cls._SUPPLEMENTARY_PATTERNS)

    def _bm25_search(
        self,
        query: str,
        source_filter: list[str] | None = None,
        top_k: int = 20,
        supplementary_penalty: float = 0.0,
    ) -> list[tuple[int, float]]:
        """BM25 스코어 계산. Returns: [(chunk_idx, score), ...] top_k개.

        supplementary_penalty: 부칙(적용례/경과조치) 청크에 곱해지는 감점 비율 (0.0 = 비활성).
            예: 0.5 → 부칙 청크 score *= 0.5 (본법 본문 article 우선).
        """
        self._build_bm25_index()
        if not self._bm25_index:
            return []

        k1 = 1.5
        b = 0.75
        # SP3: Kiwi 형태소 토크나이저 — 쿼리도 동일 방식
        query_tokens = self._tokenize_korean(query)
        scores: dict[int, float] = {}

        for qt in query_tokens:
            # SP3: 형태소 단위 정확 매칭 (이전 부분 매칭 `qt in token` 제거 — false positive 야기)
            entries = self._bm25_index.get(qt)
            if not entries:
                continue

            # IDF 계산 — 매칭 토큰의 고유 문서 수 기준
            doc_ids = set(e[0] for e in entries)
            df = len(doc_ids)
            idf = math.log((self._bm25_doc_count - df + 0.5) / (df + 0.5) + 1)

            for doc_idx, tf in entries:
                dl = self._bm25_doc_lens[doc_idx]
                tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / self._bm25_avg_dl))
                scores[doc_idx] = scores.get(doc_idx, 0) + idf * tf_norm

        # 부칙 청크 감점 — 본법 본문 article 을 상위로 끌어올림
        if supplementary_penalty > 0 and supplementary_penalty <= 1.0:
            multiplier = 1.0 - supplementary_penalty
            for doc_idx in list(scores.keys()):
                text, _ = self._bm25_docs[doc_idx]
                if self._is_supplementary_chunk(text):
                    scores[doc_idx] *= multiplier

        # source_filter 적용
        if source_filter:
            scores = {
                idx: s
                for idx, s in scores.items()
                if any(sf in self._bm25_docs[idx][1].get("source", "") for sf in source_filter)
            }

        # 상위 top_k
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

    @staticmethod
    def _is_primary_law_source(source: str) -> bool:
        """주 법률(본법)인지 판별. 시행령/시행규칙/조례/지침/규정/특례 등은 False.

        예:
            "식품위생법" -> True
            "식품위생법 시행규칙" -> False
            "식품위생법(법률)(제21065호)(20251001)" -> True
            "[한국외식업중앙회] 위생교육교재" -> False (지침/교재)
        """
        if not source:
            return False
        # 시행령/시행규칙/규칙/규정/특례/지침/조례/직제/계획/사례집/교재 등은 보조 자료
        secondary_kw = (
            "시행령",
            "시행규칙",
            " 규칙",
            "규정",
            "특례규정",
            "지침",
            "조례",
            "직제",
            "기본계획",
            "사례집",
            "교재",
            "단체소송",
            "보호 규칙",
        )
        for kw in secondary_kw:
            if kw in source:
                return False
        # 시작이 [...] (보조 자료/판례) 인 경우도 비주
        if source.startswith("["):
            return False
        # 판례/사건/위반 키워드 (사건명/판례)
        case_kw = ("위반", "취소", "반환", "손해배상", "양도", "사건", "청구")
        if any(kw in source for kw in case_kw):
            return False
        return True

    @staticmethod
    def _rrf_merge(
        vector_results: list[dict],
        bm25_results: list[tuple[int, float]],
        bm25_docs: list[tuple[str, dict]],
        k: int = 60,
        vector_w: float = 0.5,
        bm25_w: float = 0.5,
        primary_law_boost: float = 0.0,
    ) -> list[dict]:
        """Reciprocal Rank Fusion으로 벡터 + BM25 결과를 결합합니다.

        primary_law_boost: 주 법률(본법) source 의 RRF 스코어에 곱해지는 보너스 (0.0 = 비활성).
            예: 0.10 → 본법 청크의 score *= 1.10 (시행령/시행규칙/판례를 본법보다 위로 못 올리게).
        """

        # chunk_id 기반 통합 (없으면 content hash)
        def _key(meta: dict, content: str = "") -> str:
            return meta.get("chunk_id", "") or str(hash(content))[:16]

        rrf_scores: dict[str, float] = {}
        doc_map: dict[str, dict] = {}

        # 벡터 결과 RRF
        for rank, doc in enumerate(vector_results):
            key = _key(doc["metadata"], doc["content"])
            rrf_scores[key] = rrf_scores.get(key, 0) + vector_w / (k + rank + 1)
            doc_map[key] = doc

        # BM25 결과 RRF
        for rank, (idx, _score) in enumerate(bm25_results):
            text, meta = bm25_docs[idx]
            key = _key(meta, text)
            rrf_scores[key] = rrf_scores.get(key, 0) + bm25_w / (k + rank + 1)
            if key not in doc_map:
                doc_map[key] = {
                    "content": text,
                    "metadata": {**meta, "relevance": 0.4},  # BM25 전용은 고정 관련도
                }

        # 주 법률(본법) boost — 시행령/시행규칙/판례를 본법보다 위로 못 올리게
        if primary_law_boost > 0:
            for key, doc in doc_map.items():
                src = doc.get("metadata", {}).get("source", "")
                if LegalDocumentRetriever._is_primary_law_source(src):
                    rrf_scores[key] = rrf_scores.get(key, 0) * (1.0 + primary_law_boost)

        # RRF 스코어 순 정렬
        sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)
        return [doc_map[k] for k in sorted_keys if k in doc_map]

    @staticmethod
    def _hyde_expand(query: str) -> str:
        """HyDE 쿼리 확장 — 일상 용어를 법률 용어로 치환하여 원래 쿼리에 추가합니다."""
        expansions: list[str] = []
        for everyday, legal in _LEGAL_SYNONYM_MAP.items():
            if everyday in query:
                expansions.append(legal)
        if expansions:
            return query + " " + " ".join(expansions)
        return query

    async def search(
        self,
        query: str,
        top_k: int = 10,
        source_filter: list[str] | None = None,
        prefer_primary_law: bool = True,
    ) -> list[dict]:
        """
        하이브리드 법률 문서 검색 (HyDE 확장 + 벡터 + BM25 + RRF)

        0차: HyDE 쿼리 확장 (일상 용어 → 법률 용어 동의어 추가)
        1차: 벡터 유사도 검색 (pgvector 임베딩)
        2차: BM25 키워드 검색 (메모리 역인덱스)
        3차: RRF(Reciprocal Rank Fusion)로 결합

        Args:
            query: 검색 쿼리
            top_k: 반환할 문서 수
            source_filter: 검색할 source 목록
            prefer_primary_law: True면 RRF 결합 시 본법 source에 가산점 부여 (시행령/시행규칙/판례
                밀어내기). settings.primary_law_boost 값 사용. False면 boost 0 (legacy 동작).

        Returns:
            list[dict]: 관련 법률 문서 리스트
        """
        vs = self._db.vectorstore
        if vs is None:
            logger.warning(f"[LegalDocumentRetriever] vectorstore 초기화 실패 — '{query}' 검색 skip")
            return []

        from src.config.settings import settings as _settings

        # trace 수집용 컨테이너 (rag_trace_enabled 시에만 채움 — 비활성 시 거의 비용 없음)
        _trace_on = bool(_settings.rag_trace_enabled)
        trace: dict = {
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "kind": "search",
            "query": query,
            "source_filter": source_filter,
            "top_k": top_k,
            "elapsed_ms": {},
        }
        _t_total = time.perf_counter()

        # 0차: 하이브리드 HyDE 쿼리 확장 (사전 + LLM)
        _t = time.perf_counter()
        expanded_query = await self._expand_query_hybrid(query)
        if _trace_on:
            trace["expanded_query"] = expanded_query
            trace["elapsed_ms"]["hyde"] = round((time.perf_counter() - _t) * 1000, 2)

        # 0.5차: S-2 Multi-query — cheap LLM이 1쿼리 → N개 변형 (settings.multi_query_enabled)
        from src.chains.multi_query import expand_query as _multi_expand

        _t = time.perf_counter()
        mq_variants: list[str] = []
        if _settings.multi_query_enabled:
            try:
                mq_variants = await _multi_expand(query, n=_settings.multi_query_n)
            except Exception as e:
                logger.warning(f"[LegalDocumentRetriever] multi-query 실패 (무시): {e}")
        if _trace_on:
            trace["multi_query_variants"] = mq_variants
            trace["elapsed_ms"]["multi_query"] = round((time.perf_counter() - _t) * 1000, 2)

        filter_dict = {"source": {"$in": source_filter}} if source_filter else None

        # 1차: 벡터 유사도 검색 — 원래 + HyDE 확장 + Multi-query 변형 모두 병렬 검색 후 합침
        # SSL connection abort 등 transient 오류는 1회 재시도 (pool_recycle 적용 후에도 발생).
        async def _vsearch(q: str, k: int) -> list:
            try:
                return await vs.asimilarity_search_with_relevance_scores(q, k=k, filter=filter_dict)
            except Exception as e:
                msg = str(e)
                if "connection" in msg.lower() or "ssl" in msg.lower():
                    logger.warning(f"[LegalDocumentRetriever] 1회 재시도 (transient): {type(e).__name__}")
                    return await vs.asimilarity_search_with_relevance_scores(q, k=k, filter=filter_dict)
                raise

        search_queries = [(query, top_k * 2)]
        if expanded_query != query:
            search_queries.append((expanded_query, top_k))
        for v in mq_variants:
            search_queries.append((v, top_k))

        _t = time.perf_counter()
        all_results = await asyncio.gather(*[_vsearch(q, k) for q, k in search_queries])
        docs_with_score = list(all_results[0])
        seen_contents = {doc.page_content[:100] for doc, _ in docs_with_score}
        for extra_docs in all_results[1:]:
            for doc, score in extra_docs:
                if doc.page_content[:100] not in seen_contents:
                    docs_with_score.append((doc, score))
                    seen_contents.add(doc.page_content[:100])

        if not docs_with_score and source_filter:
            docs_with_score = await vs.asimilarity_search_with_relevance_scores(query, k=top_k * 2)

        if _trace_on:
            trace["vector_candidates"] = [
                _trace_candidate(doc, score, i + 1) for i, (doc, score) in enumerate(docs_with_score[:10])
            ]
            trace["elapsed_ms"]["vector_search"] = round((time.perf_counter() - _t) * 1000, 2)

        vector_results = [
            {
                "content": doc.page_content,
                "metadata": {**doc.metadata, "relevance": round(score, 4)},
            }
            for doc, score in docs_with_score
            if score >= self.RELEVANCE_THRESHOLD
        ]
        # FALLBACK: RELEVANCE_THRESHOLD 컷 후 0건이지만 raw 결과는 있다면,
        # 임계 무시하고 raw top_k 사용 — specialist LLM 에 "(자료 없음)" 보내는 케이스 차단.
        # (한국어 임베딩 코사인 < 0.3 발생 시 building/privacy 등 specialist RAG 실패 사례.)
        if not vector_results and docs_with_score:
            logger.warning(
                f"[LegalDocumentRetriever] RELEVANCE_THRESHOLD({self.RELEVANCE_THRESHOLD}) "
                f"컷 후 0건 — raw 결과 {len(docs_with_score)}건 임계 무시 폴백 적용"
            )
            vector_results = [
                {
                    "content": doc.page_content,
                    "metadata": {**doc.metadata, "relevance": round(score, 4)},
                }
                for doc, score in docs_with_score[: top_k * 2]
            ]

        # 2차: BM25 키워드 검색 — 부칙(적용례/경과조치) 감점 적용 (settings.bm25_supplementary_penalty)
        _t = time.perf_counter()
        supp_penalty = float(getattr(_settings, "bm25_supplementary_penalty", 0.0))
        bm25_ranked = self._bm25_search(
            query,
            source_filter,
            top_k=top_k * 2,
            supplementary_penalty=supp_penalty,
        )
        if _trace_on:
            bm25_docs_ref = getattr(self, "_bm25_docs", []) or []
            trace["bm25_candidates"] = [
                _trace_bm25_candidate(idx, sc, i + 1, bm25_docs_ref) for i, (idx, sc) in enumerate(bm25_ranked[:10])
            ]
            trace["elapsed_ms"]["bm25"] = round((time.perf_counter() - _t) * 1000, 2)

        # 3차: RRF 결합 — prefer_primary_law 시 본법 source에 boost 적용
        _t = time.perf_counter()
        boost = float(getattr(_settings, "primary_law_boost", 0.15)) if prefer_primary_law else 0.0
        if bm25_ranked and hasattr(self, "_bm25_docs"):
            merged = self._rrf_merge(
                vector_results,
                bm25_ranked,
                self._bm25_docs,
                k=self._RRF_K,
                vector_w=self._VECTOR_WEIGHT,
                bm25_w=self._BM25_WEIGHT,
                primary_law_boost=boost,
            )
        else:
            merged = vector_results
        if _trace_on:
            trace["rrf_merged"] = [_trace_merged_doc(d, i + 1) for i, d in enumerate(merged[:10])]
            trace["elapsed_ms"]["rrf"] = round((time.perf_counter() - _t) * 1000, 2)

        # 4차: Multi-Vector Q2Q — 비활성 (RRF 결합 시 기존 결과를 밀어내는 역효과 확인)
        # 파일럿에서 개별 유사도 +0.1~0.28 개선 확인했으나 전체 F1 -0.012 하락
        # 향후: Q2Q를 fallback으로만 사용 (기존 top-1 relevance < 0.3일 때만)
        vq_results = []  # await self._search_virtual_questions(query, source_filter, top_k=top_k)
        if vq_results:
            # RRF로 기존 결과 + Q2Q 결과 결합
            combined_scores: dict[str, float] = {}
            combined_docs: dict[str, dict] = {}

            def _doc_key(doc):
                m = doc.get("metadata", {})
                return f"{m.get('source', '')}|{m.get('article', '')}|{doc.get('content', '')[:50]}"

            # 기존 merged 스코어
            for rank, doc in enumerate(merged):
                key = _doc_key(doc)
                combined_scores[key] = combined_scores.get(key, 0) + 0.5 / (60 + rank + 1)
                combined_docs[key] = doc

            # Q2Q 스코어
            for rank, doc in enumerate(vq_results):
                key = _doc_key(doc)
                combined_scores[key] = combined_scores.get(key, 0) + 0.5 / (60 + rank + 1)
                if key not in combined_docs:
                    combined_docs[key] = doc

            sorted_keys = sorted(combined_scores, key=lambda k: combined_scores[k], reverse=True)
            merged = [combined_docs[k] for k in sorted_keys if k in combined_docs]

        # 5차: Reranker — settings.rerank_provider="openai" (default) → gpt-4.1-mini list-wise
        if self._RERANK_ENABLED and len(merged) > 1:
            rerank_provider = getattr(_settings, "rerank_provider", "openai")
            if rerank_provider == "openai":
                merged = await self._rerank_openai(query, merged[:30], top_k)
            else:
                merged = self._rerank(query, merged[:30], top_k)

        # 6차: 오답 방지 필터 (비활성 — 페널티가 정답까지 밀어내는 역효과 확인)
        # merged = self._apply_failure_filter(merged, source_filter)

        # 7차: Parent-child 후처리 — chunk_id → parent_text 치환 + parent 단위 dedup
        # 검색은 작은 child로 (정밀), 반환은 article 단위 parent로 (cover ↑)
        _t = time.perf_counter()
        _before_count = len(merged)
        _dropped_chunk_ids: list = []
        _parent_replacements: list = []
        parent_map = _PARENT_ARTICLES
        if parent_map:
            seen_parents: set[str] = set()
            deduped: list[dict] = []
            for d in merged:
                cid = d.get("metadata", {}).get("chunk_id")
                parent_text = parent_map.get(cid) if cid else None
                if parent_text:
                    parent_key = parent_text[:100]
                    if parent_key in seen_parents:
                        if _trace_on:
                            _dropped_chunk_ids.append(cid)
                        continue
                    seen_parents.add(parent_key)
                    if _trace_on:
                        _parent_replacements.append([cid, parent_text[:100]])
                    new_d = dict(d)
                    new_d["content"] = parent_text
                    new_d["metadata"] = {**d.get("metadata", {}), "is_parent": True}
                    deduped.append(new_d)
                else:
                    deduped.append(d)
            merged = deduped
        if _trace_on:
            trace["parent_dedup"] = {
                "before_count": _before_count,
                "after_count": len(merged),
                "dropped_chunk_ids": _dropped_chunk_ids,
                "parent_replacements": _parent_replacements,
            }
            trace["elapsed_ms"]["parent_dedup"] = round((time.perf_counter() - _t) * 1000, 2)

        final_docs = merged[:top_k]
        if _trace_on:
            trace["final_top_k"] = [_trace_merged_doc(d, i + 1) for i, d in enumerate(final_docs)]
            trace["elapsed_ms"]["total"] = round((time.perf_counter() - _t_total) * 1000, 2)
            _write_trace_jsonl(trace)
        return final_docs

    @classmethod
    def _load_confusion_map(cls) -> dict:
        """fail_cases.json에서 혼동 매핑 로드"""
        import json as _json
        from pathlib import Path

        fail_path = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "fail_cases.json"
        if not fail_path.exists():
            return {}

        with open(fail_path, encoding="utf-8") as f:
            fails = _json.load(f)

        cmap = {}  # (law_keyword, wrong_article) -> {correct_articles}
        for c in fails:
            law = c.get("law", "")
            for cp in c.get("confusion_pairs", []):
                wrong = cp.get("wrong", "")
                correct = cp.get("correct", "")
                if wrong and correct:
                    key = (law, wrong)
                    if key not in cmap:
                        cmap[key] = set()
                    cmap[key].add(correct)

        return cmap

    def _apply_failure_filter(self, docs: list[dict], source_filter: list[str] | None) -> list[dict]:
        """오답 방지 필터 — 혼동되는 조문이 상위에 있으면 순위 하락.

        전략: 재정렬이 아닌 "페널티" — 혼동 조문을 제거하지 않고 뒤로 밀기만 함.
        안전장치: 혼동 매핑에 없는 조문은 건드리지 않음.
        """
        import re

        if self.__class__._confusion_map is None:
            self.__class__._confusion_map = self._load_confusion_map()
            logger.info(f"[FailureFilter] 혼동 매핑 로드: {len(self.__class__._confusion_map)}개")

        cmap = self.__class__._confusion_map
        if not cmap:
            return docs

        # 현재 반환 조문 목록
        doc_articles = []
        for d in docs:
            art = d.get("metadata", {}).get("article", "")
            art = re.sub(r"_\d+$", "", art)
            doc_articles.append(art)

        # source에서 법률 추출
        law_keyword = ""
        if docs:
            src = docs[0].get("metadata", {}).get("source", "")
            for kw, short in SOURCE_TO_SHORT_MAP.items():
                if kw in src:
                    law_keyword = short
                    break

        if not law_keyword:
            return docs

        # 혼동 조문 판별 — 반환 목록에 "오답"이 있고 "정답"이 없으면 페널티
        penalty_indices = set()
        for i, art in enumerate(doc_articles):
            key = (law_keyword, art)
            if key in cmap:
                correct_should_be = cmap[key]
                # 정답이 이미 반환 목록에 있으면 페널티 불필요
                if not correct_should_be.intersection(set(doc_articles)):
                    penalty_indices.add(i)

        if not penalty_indices:
            return docs

        # 페널티 적용 — 해당 문서를 뒤로 밀기
        normal = [d for i, d in enumerate(docs) if i not in penalty_indices]
        penalized = [d for i, d in enumerate(docs) if i in penalty_indices]
        return normal + penalized

    async def _search_virtual_questions(
        self, query: str, source_filter: list[str] | None, top_k: int = 5
    ) -> list[dict]:
        """예상 질문 벡터 인덱스에서 유사 질문 검색 → 원본 청크 반환"""
        import json as _json
        from pathlib import Path

        import numpy as np

        # 지연 로딩
        if self.__class__._vq_index is None:
            vq_path = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "vq_index.npz"
            if not vq_path.exists():
                return []
            try:
                data = np.load(vq_path)
                mapping_path = vq_path.with_suffix(".json")
                with open(mapping_path, encoding="utf-8") as f:
                    mapping = _json.load(f)
                self.__class__._vq_index = {
                    "embeddings": data["embeddings"],
                    "chunk_indices": data["chunk_indices"],
                    "mapping": mapping,
                }
                logger.info(f"[Q2Q] 인덱스 로드: {len(mapping)}개 질문 벡터")
            except Exception as e:
                logger.warning(f"[Q2Q] 인덱스 로드 실패: {e}")
                return []

        idx = self.__class__._vq_index
        vq_embs = idx["embeddings"]
        vq_mapping = idx["mapping"]

        # 쿼리 임베딩 (동기, 캐시된 모델 사용)
        from sentence_transformers import SentenceTransformer

        if not hasattr(self.__class__, "_st_model"):
            self.__class__._st_model = SentenceTransformer("BAAI/bge-m3")
        q_emb = self.__class__._st_model.encode([query])[0]

        # source_filter 적용
        if source_filter:
            valid_mask = np.array([any(sf in m.get("source", "") for sf in source_filter) for m in vq_mapping])
        else:
            valid_mask = np.ones(len(vq_mapping), dtype=bool)

        if not valid_mask.any():
            return []

        # 코사인 유사도
        filtered_embs = vq_embs[valid_mask]
        filtered_indices = np.where(valid_mask)[0]

        scores = np.dot(filtered_embs, q_emb) / (np.linalg.norm(filtered_embs, axis=1) * np.linalg.norm(q_emb) + 1e-8)

        # top_k 추출
        top_k_idx = np.argsort(scores)[::-1][: top_k * 2]

        # 원본 청크 로드
        chunks_path = Path(__file__).resolve().parent.parent / "data" / "legal" / "processed" / "chunks.json"
        if not hasattr(self.__class__, "_chunks_cache"):
            with open(chunks_path, encoding="utf-8") as f:
                self.__class__._chunks_cache = _json.load(f)

        results = []
        seen_articles = set()
        for idx_pos in top_k_idx:
            real_idx = int(filtered_indices[idx_pos])
            chunk_idx = int(vq_mapping[real_idx]["chunk_idx"])
            article = vq_mapping[real_idx].get("article", "")

            if article in seen_articles:
                continue
            seen_articles.add(article)

            if chunk_idx < len(self.__class__._chunks_cache):
                chunk = self.__class__._chunks_cache[chunk_idx]
                results.append(
                    {
                        "content": chunk.get("text", chunk.get("content", "")),
                        "metadata": {
                            **chunk.get("metadata", {}),
                            "relevance": float(scores[idx_pos]),
                            "via": "q2q",
                        },
                    }
                )
            if len(results) >= top_k:
                break

        return results

    @classmethod
    def _rerank(cls, query: str, docs: list[dict], top_k: int) -> list[dict]:
        """Two-Stage Reranker — BGE-Reranker-v2-m3로 노이즈 필터링.

        이전 실패 원인: 순서 재정렬 → 좋은 결과를 밀어냄
        이번 전략: 재정렬 + 노이즈 필터링 (score < 0.01 제거)
        폴백: 필터 후 결과가 top_k 미만이면 원본 RRF 결과로 보충
        """
        from src.config.settings import settings

        if cls._reranker is None:
            from sentence_transformers import CrossEncoder

            model_name = settings.rerank_model  # property 회피 — settings에서 직접
            cls._reranker = CrossEncoder(model_name, max_length=512)
            logger.info(f"[Reranker] {model_name} 로드 완료")

        pairs = [(query, d["content"][:300]) for d in docs]  # 300자 제한 (속도)
        scores = cls._reranker.predict(pairs, batch_size=32)

        # 점수순 정렬
        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)

        # 노이즈 필터링 (score < 0.01 제거)
        filtered = [(d, s) for d, s in ranked if s >= 0.01]

        # 폴백: 필터 후 top_k 미만이면 원본 RRF 순서로 보충
        if len(filtered) < top_k:
            existing = {id(d) for d, _ in filtered}
            for d in docs:
                if id(d) not in existing and len(filtered) < top_k:
                    filtered.append((d, 0.0))

        return [d for d, s in filtered[:top_k]]

    async def _rerank_openai(self, query: str, docs: list[dict], top_k: int) -> list[dict]:
        """OpenAI gpt-4.1-mini list-wise rerank.

        한 호출로 30개 문서 ranking — 비용 효율적.
        반환: 모델이 가장 관련 높다고 판단한 순서대로 top_k 개.
        실패 시 원본 순서 유지.
        """
        if not docs:
            return docs

        from src.config.settings import settings

        oai_key = settings.openai_api_key or ""
        if not oai_key.startswith("sk-"):
            logger.warning("[Reranker-openai] OPENAI_API_KEY 없음 - 원본 순서 유지")
            return docs[:top_k]

        # 프롬프트 — 각 문서 200자 발췌 + index
        doc_lines: list[str] = []
        for i, d in enumerate(docs):
            preview = (d.get("content") or "")[:200].replace("\n", " ")
            meta = d.get("metadata", {})
            src = meta.get("source", "")
            art = meta.get("article", "")
            doc_lines.append(f"[{i}] {src} {art}: {preview}")
        docs_block = "\n".join(doc_lines)

        prompt = (
            "한국 법률 검색 결과 reranking. 사용자 질문에 직접 관련된 조문을 가장 관련 높은 순으로 다시 정렬.\n\n"
            f"질문: {query}\n\n"
            f"검색 결과 ({len(docs)}개):\n{docs_block}\n\n"
            f"가장 관련 높은 {min(top_k, len(docs))}개의 인덱스를 콤마 구분으로만 출력 (예: 3,7,1,12,5).\n"
            "다른 텍스트 없이 인덱스 리스트만."
        )

        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=oai_key)
            resp = await client.chat.completions.create(
                model=getattr(settings, "rerank_openai_model", "gpt-4.1-mini"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0,
            )
            text = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning(f"[Reranker-openai] 호출 실패 ({e}) - 원본 순서 유지")
            return docs[:top_k]

        # 인덱스 파싱
        import re

        indices: list[int] = []
        seen: set[int] = set()
        for tok in re.findall(r"\d+", text):
            try:
                idx = int(tok)
                if 0 <= idx < len(docs) and idx not in seen:
                    indices.append(idx)
                    seen.add(idx)
            except ValueError:
                continue
            if len(indices) >= top_k:
                break

        if not indices:
            logger.warning(f"[Reranker-openai] 응답 파싱 실패 ({text[:80]!r}) - 원본 순서 유지")
            return docs[:top_k]

        # 누락된 docs 보충 (top_k 미달 시)
        for i in range(len(docs)):
            if i not in seen and len(indices) < top_k:
                indices.append(i)

        return [docs[i] for i in indices[:top_k]]

    async def search_precedents(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[dict]:
        """판례 카테고리만 검색 — ``metadata.category == '판례'`` 필터.

        - 단순화: multi-query/HyDE 미사용 (판례는 키워드 직접 매칭이 더 정확).
        - BM25 보조 매칭은 ``category=='판례'`` 청크에 한정해서 결합.
        - 실패 시 빈 리스트 반환 (graceful degradation).

        Returns:
            list[dict]: ``[{"content", "metadata"}]`` (top_k 이내).
        """
        vs = self._db.vectorstore
        if vs is None:
            logger.warning(f"[search_precedents] vectorstore 미초기화 — '{query}' skip")
            return []

        from src.config.settings import settings as _settings

        _trace_on = bool(_settings.rag_trace_enabled)
        trace: dict = {
            "ts": datetime.datetime.utcnow().isoformat() + "Z",
            "kind": "search_precedents",
            "query": query,
            "source_filter": None,
            "category_filter": "판례",
            "top_k": top_k,
            "elapsed_ms": {},
        }
        _t_total = time.perf_counter()

        # 1차: 벡터 유사도 (PGVector JSONB 메타데이터 필터)
        filter_dict = {"category": {"$eq": "판례"}}
        _t = time.perf_counter()
        try:
            docs_with_score = await vs.asimilarity_search_with_relevance_scores(query, k=top_k * 3, filter=filter_dict)
        except Exception as e:
            msg = str(e)
            if "connection" in msg.lower() or "ssl" in msg.lower():
                logger.warning(f"[search_precedents] 1회 재시도 (transient): {type(e).__name__}")
                try:
                    docs_with_score = await vs.asimilarity_search_with_relevance_scores(
                        query, k=top_k * 3, filter=filter_dict
                    )
                except Exception as e2:
                    logger.warning(f"[search_precedents] 재시도 실패: {e2}")
                    return []
            else:
                logger.warning(f"[search_precedents] 벡터 검색 실패: {e}")
                return []

        if _trace_on:
            trace["vector_candidates"] = [
                _trace_candidate(doc, score, i + 1) for i, (doc, score) in enumerate(docs_with_score[:10])
            ]
            trace["elapsed_ms"]["vector_search"] = round((time.perf_counter() - _t) * 1000, 2)

        vector_results = [
            {
                "content": doc.page_content,
                "metadata": {**doc.metadata, "relevance": round(score, 4)},
            }
            for doc, score in docs_with_score
            if score >= self.RELEVANCE_THRESHOLD
        ]
        # FALLBACK: 판례도 동일 — 임계 컷 후 0건이지만 raw 있으면 임계 무시 사용.
        if not vector_results and docs_with_score:
            logger.warning(
                f"[search_precedents] RELEVANCE_THRESHOLD({self.RELEVANCE_THRESHOLD}) "
                f"컷 후 0건 — raw {len(docs_with_score)}건 폴백"
            )
            vector_results = [
                {
                    "content": doc.page_content,
                    "metadata": {**doc.metadata, "relevance": round(score, 4)},
                }
                for doc, score in docs_with_score[: top_k * 2]
            ]

        # 2차: BM25 — 판례 청크만 대상으로 필터 (메모리 인덱스에서 category 필터링).
        _t = time.perf_counter()
        try:
            self._build_bm25_index()
        except Exception as e:
            logger.warning(f"[search_precedents] BM25 index 구축 실패: {e}")

        bm25_ranked: list[tuple[int, float]] = []
        if self._bm25_index and hasattr(self, "_bm25_docs"):
            # 전체 BM25 후 category 필터 (인덱스 분리는 비용 대비 이득 적음).
            raw = self._bm25_search(query, source_filter=None, top_k=top_k * 5)
            bm25_ranked = [(idx, sc) for idx, sc in raw if (self._bm25_docs[idx][1] or {}).get("category") == "판례"][
                : top_k * 2
            ]
        if _trace_on:
            bm25_docs_ref = getattr(self, "_bm25_docs", []) or []
            trace["bm25_candidates"] = [
                _trace_bm25_candidate(idx, sc, i + 1, bm25_docs_ref) for i, (idx, sc) in enumerate(bm25_ranked[:10])
            ]
            trace["elapsed_ms"]["bm25"] = round((time.perf_counter() - _t) * 1000, 2)

        # 3차: RRF 결합
        _t = time.perf_counter()
        if bm25_ranked:
            merged = self._rrf_merge(
                vector_results,
                bm25_ranked,
                self._bm25_docs,
                k=self._RRF_K,
                vector_w=self._VECTOR_WEIGHT,
                bm25_w=self._BM25_WEIGHT,
            )
        else:
            merged = vector_results
        if _trace_on:
            trace["rrf_merged"] = [_trace_merged_doc(d, i + 1) for i, d in enumerate(merged[:10])]
            trace["elapsed_ms"]["rrf"] = round((time.perf_counter() - _t) * 1000, 2)

        final_docs = merged[:top_k]
        if _trace_on:
            trace["final_top_k"] = [_trace_merged_doc(d, i + 1) for i, d in enumerate(final_docs)]
            trace["elapsed_ms"]["total"] = round((time.perf_counter() - _t_total) * 1000, 2)
            _write_trace_jsonl(trace)
        return final_docs

    async def ingest_from_json(self, json_path: str | Path) -> int:
        """
        processed/chunks.json을 읽어 pgvector에 일괄 적재

        parse_pdfs.py 실행 후 이 메서드로 인덱싱하는 흐름:
            1. python data/legal/parse_pdfs.py
            2. retriever.ingest_from_json("data/legal/processed/chunks.json")

        Args:
            json_path: chunks.json 경로

        Returns:
            int: 적재된 청크 수
        """
        with open(json_path, encoding="utf-8") as f:
            chunks = json.load(f)

        from langchain_core.documents import Document

        docs = [Document(page_content=c["text"], metadata=c["metadata"]) for c in chunks]

        vs = self._db.vectorstore
        if vs is None:
            raise RuntimeError("VectorStore 초기화 실패 — POSTGRES_URL 및 PostgreSQL 연결을 확인하세요.")
        await vs.aadd_documents(docs)

        # BM25 인덱스 재구축
        self._bm25_index = None
        self._build_bm25_index()

        return len(docs)
