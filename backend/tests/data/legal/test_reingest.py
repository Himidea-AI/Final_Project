"""SP1 — reingest.py 통합 테스트

실제 PostgreSQL 연결 사용 (DB 모킹 금지). 트랜잭션 롤백으로 격리.
DB 연결 불가 시 자동 skip.

전제:
- POSTGRES_URL 환경변수 (conftest.py에서 설정)
- alembic 마이그레이션 적용 완료 (uq_legal_chunk_id, idx_legal_cmetadata_gin)
- pgvector 확장 활성화

실행:
    cd backend && pytest tests/data/legal/test_reingest.py -v
"""

from __future__ import annotations

import json
import os
import uuid

import pytest

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/mapo_simulator")


def _try_connect():
    try:
        import psycopg

        conn = psycopg.connect(POSTGRES_URL, connect_timeout=3)
        return conn
    except Exception:
        return None


@pytest.fixture(scope="module")
def db_available() -> bool:
    conn = _try_connect()
    if conn is None:
        return False
    conn.close()
    return True


@pytest.fixture
def conn(db_available):
    if not db_available:
        pytest.skip("PostgreSQL 연결 불가 — 통합 테스트 skip")
    import psycopg

    c = psycopg.connect(POSTGRES_URL)
    yield c
    c.close()


@pytest.fixture
def test_collection(conn):
    """격리된 임시 collection — 테스트 후 삭제"""
    name = f"_test_legal_{uuid.uuid4().hex[:8]}"
    cid = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO langchain_pg_collection (uuid, name, cmetadata) VALUES (%s, %s, %s)",
            (cid, name, json.dumps({})),
        )
        conn.commit()

    yield str(cid)

    with conn.cursor() as cur:
        cur.execute("DELETE FROM langchain_pg_embedding WHERE collection_id = %s", (str(cid),))
        cur.execute("DELETE FROM langchain_pg_collection WHERE uuid = %s", (cid,))
        conn.commit()


def _fake_vector(dim: int = 384) -> list[float]:
    """384D 고정 벡터 — 임베딩 모델 호출 회피"""
    return [0.01] * dim


def _make_test_chunk(chunk_id: str, text: str = "테스트 텍스트") -> dict:
    return {
        "id": chunk_id,
        "text": text,
        "metadata": {
            "source": "test.pdf",
            "category": "test",
            "article": "제1조",
            "chunk_id": chunk_id,
        },
    }


class TestUpsertIdempotency:
    def test_double_upsert_keeps_single_row(self, conn, test_collection):
        from data.legal.reingest import _upsert_batch

        chunks = [_make_test_chunk("aaa111", "원본")]
        vectors = [_fake_vector()]

        _upsert_batch(conn, test_collection, chunks, vectors)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM langchain_pg_embedding WHERE collection_id = %s",
                (test_collection,),
            )
            count_after_first = cur.fetchone()[0]
        assert count_after_first == 1

        # 같은 chunk_id 두 번째 호출 — UPDATE 발생, 행 수 유지
        chunks_v2 = [_make_test_chunk("aaa111", "갱신")]
        _upsert_batch(conn, test_collection, chunks_v2, vectors)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*), document FROM langchain_pg_embedding WHERE collection_id = %s GROUP BY document",
                (test_collection,),
            )
            rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 1
        assert rows[0][1] == "갱신"


class TestGhostCleanup:
    def test_chunks_not_in_new_set_are_deleted(self, conn, test_collection):
        from data.legal.reingest import _delete_by_chunk_ids, _upsert_batch

        # 사전: 3행 적재
        chunks = [
            _make_test_chunk("keep1", "유지1"),
            _make_test_chunk("ghost1", "유령1"),
            _make_test_chunk("ghost2", "유령2"),
        ]
        _upsert_batch(conn, test_collection, chunks, [_fake_vector()] * 3)
        conn.commit()

        # 새 chunks.json은 keep1만 보유 → ghost1, ghost2 삭제
        ghost_ids = {"ghost1", "ghost2"}
        deleted = _delete_by_chunk_ids(conn, test_collection, ghost_ids)
        conn.commit()
        assert deleted == 2

        with conn.cursor() as cur:
            cur.execute(
                "SELECT cmetadata->>'chunk_id' FROM langchain_pg_embedding WHERE collection_id = %s",
                (test_collection,),
            )
            remaining = {row[0] for row in cur.fetchall()}
        assert remaining == {"keep1"}

    def test_empty_ghost_set_no_op(self, conn, test_collection):
        from data.legal.reingest import _delete_by_chunk_ids

        deleted = _delete_by_chunk_ids(conn, test_collection, [])
        assert deleted == 0


class TestInvariants:
    def test_passes_after_clean_upsert(self, conn, test_collection):
        from data.legal.reingest import _upsert_batch, _verify_invariants

        chunks = [
            _make_test_chunk("c1"),
            _make_test_chunk("c2"),
            _make_test_chunk("c3"),
        ]
        _upsert_batch(conn, test_collection, chunks, [_fake_vector()] * 3)
        conn.commit()

        # expected = 3 (3개 청크 적재)
        _verify_invariants(conn, test_collection, expected=3)

    def test_raises_on_count_mismatch(self, conn, test_collection):
        from data.legal.reingest import _upsert_batch, _verify_invariants

        chunks = [_make_test_chunk("c1")]
        _upsert_batch(conn, test_collection, chunks, [_fake_vector()])
        conn.commit()

        with pytest.raises(AssertionError, match="DB="):
            _verify_invariants(conn, test_collection, expected=99)


class TestFetchExistingChunkIds:
    def test_returns_existing_chunk_ids_only(self, conn, test_collection):
        from data.legal.reingest import _fetch_existing_chunk_ids, _upsert_batch

        chunks = [
            _make_test_chunk("xyz111"),
            _make_test_chunk("xyz222"),
        ]
        _upsert_batch(conn, test_collection, chunks, [_fake_vector()] * 2)
        conn.commit()

        ids = _fetch_existing_chunk_ids(conn, test_collection)
        assert ids == {"xyz111", "xyz222"}

    def test_empty_collection_returns_empty_set(self, conn, test_collection):
        from data.legal.reingest import _fetch_existing_chunk_ids

        ids = _fetch_existing_chunk_ids(conn, test_collection)
        assert ids == set()
