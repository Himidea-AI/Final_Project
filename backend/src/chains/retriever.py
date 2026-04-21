"""
RAG 문서 검색 — 하이브리드 (벡터 유사도 + BM25 키워드) + RRF 결합 + HyDE 쿼리 확장
"""

import json
import math
from pathlib import Path

from ..database.vector_db import LegalVectorDB

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
}


class LegalDocumentRetriever:
    """법률 문서 검색기 — 하이브리드 RAG (벡터 + BM25 + RRF)"""

    def __init__(self):
        self._db = LegalVectorDB()
        self._bm25_index: dict | None = None  # 지연 초기화

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
        top_k: int = 5,
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

        # 0차: HyDE 쿼리 확장
        expanded_query = self._hyde_expand(query)

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

        return merged[:top_k]

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
