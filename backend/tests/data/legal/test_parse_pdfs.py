"""SP1 — parse_pdfs.py 단위 테스트

chunk_id 결정성 / 정규화 / 검증 로직."""

from __future__ import annotations

import pytest

from data.legal.parse_pdfs import (
    _make_chunk,
    _make_chunk_id,
    _normalize_for_hash,
    _validate_chunks,
    MIN_CHUNK_LENGTH,
)


class TestNormalize:
    def test_collapses_whitespace(self):
        assert _normalize_for_hash("권리금  보호") == "권리금 보호"
        assert _normalize_for_hash("권리금\n\n보호") == "권리금 보호"
        assert _normalize_for_hash("권리금\t보호") == "권리금 보호"

    def test_strips_edges(self):
        assert _normalize_for_hash("  권리금 보호  ") == "권리금 보호"


class TestMakeChunkId:
    def test_deterministic(self):
        id1 = _make_chunk_id("law.pdf", "제10조", "권리금 보호")
        id2 = _make_chunk_id("law.pdf", "제10조", "권리금 보호")
        assert id1 == id2

    def test_normalization_equivalent(self):
        """공백 차이만 있는 텍스트는 같은 chunk_id"""
        id1 = _make_chunk_id("law.pdf", "제10조", "권리금  보호")
        id2 = _make_chunk_id("law.pdf", "제10조", "권리금 보호")
        assert id1 == id2

    def test_changes_with_content(self):
        id1 = _make_chunk_id("law.pdf", "제10조", "권리금 보호")
        id2 = _make_chunk_id("law.pdf", "제10조", "권리금 회수")
        assert id1 != id2

    def test_changes_with_source(self):
        id1 = _make_chunk_id("law_a.pdf", "제10조", "동일 텍스트")
        id2 = _make_chunk_id("law_b.pdf", "제10조", "동일 텍스트")
        assert id1 != id2

    def test_changes_with_article(self):
        id1 = _make_chunk_id("law.pdf", "제10조", "동일 텍스트")
        id2 = _make_chunk_id("law.pdf", "제11조", "동일 텍스트")
        assert id1 != id2

    def test_length_16_hex(self):
        cid = _make_chunk_id("law.pdf", "제10조", "보호")
        assert len(cid) == 16
        assert all(c in "0123456789abcdef" for c in cid)


class TestMakeChunk:
    def test_returns_none_below_min_length(self):
        short = "x" * (MIN_CHUNK_LENGTH - 1)
        assert _make_chunk(short, "lease", "제10조", "law.pdf") is None

    def test_metadata_includes_chunk_id(self):
        text = "권리금 회수기회 보호에 관한 조항. " * 3
        chunk = _make_chunk(text, "lease", "제10조", "law.pdf")
        assert chunk is not None
        assert chunk["metadata"]["chunk_id"] == chunk["id"]

    def test_metadata_keys(self):
        text = "권리금 회수기회 보호에 관한 조항. " * 3
        chunk = _make_chunk(text, "lease_law", "제10조", "lease.pdf")
        assert set(chunk["metadata"].keys()) == {"source", "category", "article", "chunk_id"}
        assert chunk["metadata"]["source"] == "lease.pdf"
        assert chunk["metadata"]["category"] == "lease_law"
        assert chunk["metadata"]["article"] == "제10조"

    def test_top_level_id_matches_metadata_chunk_id(self):
        text = "충분히 긴 텍스트입니다. " * 3
        chunk = _make_chunk(text, "cat", "제1조", "src.pdf")
        assert chunk["id"] == chunk["metadata"]["chunk_id"]


class TestValidateChunks:
    def test_passes_for_unique_chunks(self):
        chunks = [
            {"id": "abc", "metadata": {"chunk_id": "abc"}},
            {"id": "def", "metadata": {"chunk_id": "def"}},
        ]
        _validate_chunks(chunks)  # should not raise

    def test_raises_on_duplicate_id(self):
        chunks = [
            {"id": "abc", "metadata": {"chunk_id": "abc"}},
            {"id": "abc", "metadata": {"chunk_id": "abc"}},
        ]
        with pytest.raises(ValueError, match="chunk_id 중복"):
            _validate_chunks(chunks)

    def test_raises_on_id_metadata_mismatch(self):
        chunks = [
            {"id": "abc", "metadata": {"chunk_id": "different"}},
        ]
        with pytest.raises(ValueError, match="id-metadata.chunk_id 불일치"):
            _validate_chunks(chunks)

    def test_raises_on_missing_metadata_chunk_id(self):
        chunks = [
            {"id": "abc", "metadata": {}},
        ]
        with pytest.raises(ValueError, match="id-metadata.chunk_id 불일치"):
            _validate_chunks(chunks)
