"""
RAG 문서 검색 — 하이브리드 (벡터 유사도 + BM25 키워드) + RRF 결합 + HyDE 쿼리 확장 + Cross-encoder Reranker
"""

import json
import logging
import math
from pathlib import Path

from ..database.vector_db import LegalVectorDB

logger = logging.getLogger(__name__)


# HyDE용 일상 용어 → 법률 용어 매핑 (LLM 호출 없이 빠르게 치환)
_LEGAL_SYNONYM_MAP: dict[str, str] = {
    "4대보험": "국민연금 건강보험 고용보험 산업재해보상보험",
    "월세": "차임 월 차임",
    "보증금": "임대차보증금 환산보증금",
    "알바": "단시간근로자 기간제근로자",
    "파트타임": "단시간근로자",
    "야간수당": "야간근로 가산임금",
    "주말수당": "휴일근로 가산임금",
    "퇴직금": "퇴직급여 퇴직연금",
    "CCTV": "영상정보처리기기",
    "고객정보": "개인정보 정보주체",
    "간이과세": "간이과세자 납부의무 면제",
    "영업허가": "영업허가 영업신고 영업등록",
    "소방점검": "작동기능점검 종합정밀점검 자체점검",
    "비상구": "피난시설 비상구 안전시설",
    "장애인화장실": "장애인등편의시설 편의시설",
    "경사로": "장애인등편의시설 경사로 접근",
    "그리스트랩": "유류분리기 오수처리시설",
    "가맹비": "가맹금 가입비",
    "로열티": "가맹금 계약이행보증금",
    "본사 갑질": "불공정거래행위 거래강제 부당한 차별취급",
    "불법건축물": "위반건축물 이행강제금",
    "용도변경": "건축물 용도변경 근린생활시설",
    # 상가임대차 관련
    "권리금": "권리금 회수기회 보호 제10조의4",
    "계약갱신": "계약갱신요구권 제10조",
    "임대료인상": "차임증감청구 차임증액",
    "환산보증금": "환산보증금 보증금 환산",
    "묵시적갱신": "묵시적갱신 계약갱신",
    # 근로기준법 관련
    "주휴수당": "주휴일 유급휴일 주휴수당",
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
    "소방안전관리자": "소방안전관리자 선임 제24조 제25조",
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
    "거래강제": "거래강제 불공정거래행위 제45조 제40조",
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
    """법률 문서 검색기 — 하이브리드 RAG (벡터 + BM25 + RRF)"""

    def __init__(self):
        self._db = LegalVectorDB()
        self._bm25_index: dict | None = None  # 지연 초기화

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

        cache_key = f"v3:hyde:{hashlib.sha256(query.encode()).hexdigest()[:32]}"

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
        except Exception:
            pass

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

                # Anthropic SDK (claude-haiku-4.5)
                if settings.anthropic_api_key:
                    from anthropic import AsyncAnthropic
                    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
                    resp = await asyncio.wait_for(
                        client.messages.create(
                            model="claude-haiku-4-5-20251001",
                            max_tokens=500,
                            system=HYDE_SYSTEM_PROMPT,
                            messages=[
                                {"role": m["role"], "content": m["content"]}
                                for m in messages
                                if m["role"] != "system"
                            ],
                        ),
                        timeout=10.0,
                    )
                    hyde_text = resp.content[0].text.strip()
                # OpenAI fallback (gpt-4o-mini)
                elif settings.openai_api_key:
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
                    except Exception:
                        pass

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
                    except Exception:
                        pass

        # 결합: 원문 + 사전 확장 + 가상 조문
        if hyde_text:
            return f"{dict_expanded} {hyde_text}"
        return dict_expanded

    # 청크가 인덱싱된 source 메타데이터 값 (parse_pdfs.py의 파일명 stem과 일치)
    FRANCHISE_LAW_SOURCES = [
        "가맹사업거래의 공정화에 관한 법률(법률)(제20712호)(20250121)",
        "가맹사업거래의 공정화에 관한 법률 시행령(대통령령)(제36220호)(20260324)",
    ]
    LEASE_LAW_SOURCES = [
        "상가건물 임대차보호법(법률)(제21065호)(20260102)",
        "상가건물 임대차보호법 시행령(대통령령)(제35947호)(20260102)",
        "서울시_2023_상가임대차_상담사례집_내지_전자책",
    ]
    # 조문 검색 전용 — 상담사례집 제외 (비조문 문서가 조문 검색 정확도를 낮춤)
    LEASE_LAW_STRICT_SOURCES = [
        "상가건물 임대차보호법(법률)(제21065호)(20260102)",
        "상가건물 임대차보호법 시행령(대통령령)(제35947호)(20260102)",
    ]
    MAPO_SOURCES = [
        "서울특별시 마포구 지역상권 상생협력에 관한 조례",
    ]
    FOOD_HYGIENE_SOURCES = [
        "식품위생법(법률)(제21065호)(20251001)",
        "식품위생법 시행규칙(총리령)(제02077호)(20260301)",
        "[한국외식업중앙회] 2026 위생교육교재 (표지 포함)",
    ]
    SAFETY_SOURCES = [
        "210226_ 「다중이용업소의 안전관리에 관한 특별법」업무처리 지침",
        "제4차(2024~2028) 다중이용업소 안전관리 기본계획(전문)",
    ]
    BUILDING_LAW_SOURCES = [
        "건축법(법률)(20250101)",
    ]
    FIRE_SAFETY_SOURCES = [
        "소방시설 설치 및 관리에 관한 법률(법률)(20250101)",
    ]
    LABOR_LAW_SOURCES = [
        "근로기준법(법률)(20250101)",
        "최저임금법(법률)(제17326호)(20200526)",
    ]
    VAT_LAW_SOURCES = [
        "부가가치세법(법률)(제21065호)(20260102)",
    ]
    PRIVACY_LAW_SOURCES = [
        "개인정보 보호법(법률)(제20897호)(20251002)",
    ]
    ACCESSIBILITY_LAW_SOURCES = [
        "장애인ㆍ노인ㆍ임산부 등의 편의증진 보장에 관한 법률(법률)(제20594호)(20251221)",
    ]
    FAIR_TRADE_SOURCES = [
        "독점규제 및 공정거래에 관한 법률(법률)(제21066호)(20251001)",
    ]
    SEWAGE_LAW_SOURCES = [
        "하수도법(법률)(제21065호)(20251001)",
        "물환경보전법(법률)(제21368호)(20260219)",
    ]
    LIQUOR_LAW_SOURCES = [
        "주세법(법률)(제20618호)(20250101)",
    ]

    # 관련성 임계값 — 이 점수 미만인 문서는 LLM 컨텍스트에서 제외
    RELEVANCE_THRESHOLD = 0.3

    # RRF 파라미터
    _RRF_K = 60  # Reciprocal Rank Fusion 상수
    _VECTOR_WEIGHT = 0.5
    _BM25_WEIGHT = 0.5

    # Reranker (전부 비활성 — 3종 모두 역효과 확인)
    # ms-marco-MiniLM: F1 -0.247
    # mmarco-mMiniLMv2: F1 -0.128
    # BGE-Reranker-v2-m3: F1 -0.030, F1>=0.7: 43→20 폭락
    # 결론: 현재 RRF(벡터+BM25) 순서가 리랭커보다 우수
    _reranker = None
    _RERANK_ENABLED = False
    _RERANK_MODEL = "BAAI/bge-reranker-v2-m3"

    # Multi-Vector Q2Q (예상 질문 벡터 검색)
    _vq_index = None  # 지연 로딩

    # 오답 방지 필터 (Hard Negative Mining)
    _confusion_map = None  # 지연 로딩: {(law_keyword, wrong_article): {correct_articles}}

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
        for i, c in enumerate(chunks):
            text = c.get("text", "")
            meta = c.get("metadata", {})
            self._bm25_docs.append((text, meta))
            # 단순 공백 토크나이저 (한국어 법률은 띄어쓰기 기반으로 충분)
            tokens = text.split()
            tf_map: dict[str, int] = {}
            for t in tokens:
                tf_map[t] = tf_map.get(t, 0) + 1
            for token, tf in tf_map.items():
                inv_index.setdefault(token, []).append((i, tf))

        self._bm25_index = inv_index
        self._bm25_doc_count = len(self._bm25_docs)
        # 문서별 토큰 수
        self._bm25_doc_lens = [len(d[0].split()) for d in self._bm25_docs]
        self._bm25_avg_dl = sum(self._bm25_doc_lens) / max(len(self._bm25_doc_lens), 1)

    def _bm25_search(
        self,
        query: str,
        source_filter: list[str] | None = None,
        top_k: int = 20,
    ) -> list[tuple[int, float]]:
        """BM25 스코어 계산. Returns: [(chunk_idx, score), ...] top_k개."""
        self._build_bm25_index()
        if not self._bm25_index:
            return []

        k1 = 1.5
        b = 0.75
        query_tokens = query.split()
        scores: dict[int, float] = {}

        for qt in query_tokens:
            # 부분 매칭: 쿼리 토큰을 포함하는 모든 인덱스 키를 찾음
            matching_entries: list[tuple[int, int]] = []
            for token, entries in self._bm25_index.items():
                if qt in token or token in qt:
                    matching_entries.extend(entries)

            if not matching_entries:
                continue

            # IDF 계산 — 매칭된 고유 문서 수 기준
            doc_ids = set(e[0] for e in matching_entries)
            df = len(doc_ids)
            idf = math.log((self._bm25_doc_count - df + 0.5) / (df + 0.5) + 1)

            for doc_idx, tf in matching_entries:
                dl = self._bm25_doc_lens[doc_idx]
                tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / self._bm25_avg_dl))
                scores[doc_idx] = scores.get(doc_idx, 0) + idf * tf_norm

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
    def _rrf_merge(
        vector_results: list[dict],
        bm25_results: list[tuple[int, float]],
        bm25_docs: list[tuple[str, dict]],
        k: int = 60,
        vector_w: float = 0.5,
        bm25_w: float = 0.5,
    ) -> list[dict]:
        """Reciprocal Rank Fusion으로 벡터 + BM25 결과를 결합합니다."""

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

        Returns:
            list[dict]: 관련 법률 문서 리스트
        """
        vs = self._db.vectorstore
        if vs is None:
            print(f"[LegalDocumentRetriever] WARNING: vectorstore가 초기화되지 않아 '{query}' 검색을 건너뜁니다.")
            return []

        # 0차: 하이브리드 HyDE 쿼리 확장 (사전 + LLM)
        expanded_query = await self._expand_query_hybrid(query)

        filter_dict = {"source": {"$in": source_filter}} if source_filter else None

        # 1차: 벡터 유사도 검색 — 원래 쿼리 + 확장 쿼리 모두 검색 후 합침
        docs_with_score = await vs.asimilarity_search_with_relevance_scores(query, k=top_k * 2, filter=filter_dict)
        if expanded_query != query:
            # 확장 쿼리로 추가 검색
            extra_docs = await vs.asimilarity_search_with_relevance_scores(expanded_query, k=top_k, filter=filter_dict)
            # 중복 제거하여 합침
            seen_contents = {doc.page_content[:100] for doc, _ in docs_with_score}
            for doc, score in extra_docs:
                if doc.page_content[:100] not in seen_contents:
                    docs_with_score.append((doc, score))
                    seen_contents.add(doc.page_content[:100])

        if not docs_with_score and source_filter:
            docs_with_score = await vs.asimilarity_search_with_relevance_scores(query, k=top_k * 2)

        vector_results = [
            {
                "content": doc.page_content,
                "metadata": {**doc.metadata, "relevance": round(score, 4)},
            }
            for doc, score in docs_with_score
            if score >= self.RELEVANCE_THRESHOLD
        ]

        # 2차: BM25 키워드 검색
        bm25_ranked = self._bm25_search(query, source_filter, top_k=top_k * 2)

        # 3차: RRF 결합
        if bm25_ranked and hasattr(self, "_bm25_docs"):
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

        # 5차: Reranker (비활성)
        if self._RERANK_ENABLED and len(merged) > 1:
            merged = self._rerank(query, merged[:30], top_k)

        # 6차: 오답 방지 필터 (비활성 — 페널티가 정답까지 밀어내는 역효과 확인)
        # merged = self._apply_failure_filter(merged, source_filter)

        return merged[:top_k]

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
            self.__class__._st_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        q_emb = self.__class__._st_model.encode([query])[0]

        # source_filter 적용
        if source_filter:
            valid_mask = np.array([
                any(sf in m.get("source", "") for sf in source_filter)
                for m in vq_mapping
            ])
        else:
            valid_mask = np.ones(len(vq_mapping), dtype=bool)

        if not valid_mask.any():
            return []

        # 코사인 유사도
        filtered_embs = vq_embs[valid_mask]
        filtered_indices = np.where(valid_mask)[0]

        scores = np.dot(filtered_embs, q_emb) / (
            np.linalg.norm(filtered_embs, axis=1) * np.linalg.norm(q_emb) + 1e-8
        )

        # top_k 추출
        top_k_idx = np.argsort(scores)[::-1][:top_k * 2]

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
                results.append({
                    "content": chunk.get("text", chunk.get("content", "")),
                    "metadata": {
                        **chunk.get("metadata", {}),
                        "relevance": float(scores[idx_pos]),
                        "via": "q2q",
                    },
                })
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
        if cls._reranker is None:
            from sentence_transformers import CrossEncoder
            cls._reranker = CrossEncoder(cls._RERANK_MODEL, max_length=512)
            logger.info(f"[Reranker] {cls._RERANK_MODEL} 로드 완료")

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
