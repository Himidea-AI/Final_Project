"""pgvector 기반 에이전트 메모리 인덱스.

기존 langchain_pg_embedding 테이블 재사용:
- 새 컬렉션: sim_agent_memory
- 동일 임베딩 모델: paraphrase-multilingual-MiniLM-L12-v2 (384차원, 한글)
- legal_documents 컬렉션과 충돌 없음 (collection_id로 분리)

저장:
    add(agent_id, day, hour, action, target, reason)

검색:
    search(agent_id, query, k=3)
    → 본인 과거 행동 top-k → Tier S 컨텍스트에 주입

토큰 절감 효과:
- 메모리 요약 대신 의미 검색 → 관련 행동만 LLM에 전달
- 검색 자체는 로컬 임베딩 (비용 0)
- 컨텍스트 +50 tok (검색 결과 3개) → 의사결정 품질 향상
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
_COLLECTION = "sim_agent_memory"


@dataclass
class MemoryHit:
    agent_id: int
    day: int
    hour: int
    text: str
    score: float


class PgVectorMemory:
    """동기 PGVector 래퍼 - 시뮬용.

    배치 add를 권장 (per-step add는 임베딩 호출 비용 큼 → CPU GPU 자원).
    하루 마무리에 일별 요약을 한 번에 add하는 패턴.
    """

    def __init__(
        self,
        collection_name: str = _COLLECTION,
        db_url: str | None = None,
        lazy: bool = True,
    ):
        self.collection_name = collection_name
        self.db_url = db_url or os.environ.get("POSTGRES_URL", "")
        self._store = None
        self._embed = None
        if not lazy:
            self._init()

    # -----------------------------------------------------------
    def _init(self) -> None:
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_postgres.vectorstores import PGVector

        self._embed = HuggingFaceEmbeddings(
            model_name=_EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        # 동기 버전 — psycopg URL
        conn = self.db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        self._store = PGVector(
            connection=conn,
            embeddings=self._embed,
            collection_name=self.collection_name,
            use_jsonb=True,
        )
        print(f"[memory_index] PGVector 연결: collection={self.collection_name}")

    @property
    def store(self):
        if self._store is None:
            self._init()
        return self._store

    # -----------------------------------------------------------
    def add_batch(self, items: list[dict]) -> int:
        """items: [{agent_id, day, hour, action, target, reason}, ...]"""
        if not items:
            return 0
        texts = [self._format(it) for it in items]
        metas = [
            {
                "agent_id": int(it["agent_id"]),
                "day": int(it["day"]),
                "hour": int(it["hour"]),
                "action": it.get("action", ""),
                "target": str(it.get("target", "")),
            }
            for it in items
        ]
        self.store.add_texts(texts=texts, metadatas=metas)
        return len(items)

    @staticmethod
    def _format(it: dict) -> str:
        action = it.get("action", "")
        target = it.get("target", "")
        reason = it.get("reason", "")
        return f"D{it.get('day')}-H{it.get('hour')} {action} {target} {reason}".strip()

    # -----------------------------------------------------------
    def search(self, agent_id: int, query: str, k: int = 3) -> list[MemoryHit]:
        """본인 과거 행동만 필터링하여 top-k."""
        try:
            docs = self.store.similarity_search_with_score(
                query=query,
                k=k,
                filter={"agent_id": agent_id},
            )
        except Exception as e:
            print(f"[memory_index] search 실패: {e}")
            return []

        out: list[MemoryHit] = []
        for doc, score in docs:
            md = doc.metadata or {}
            out.append(
                MemoryHit(
                    agent_id=int(md.get("agent_id", 0)),
                    day=int(md.get("day", 0)),
                    hour=int(md.get("hour", 0)),
                    text=doc.page_content,
                    score=float(score),
                )
            )
        return out

    # -----------------------------------------------------------
    def clear_collection(self) -> None:
        """시뮬 시작 전 컬렉션 비우기 (개발용)."""
        try:
            self.store.delete_collection()
            self._store = None
            print(f"[memory_index] {self.collection_name} 컬렉션 초기화")
        except Exception as e:
            print(f"[memory_index] clear 실패: {e}")
