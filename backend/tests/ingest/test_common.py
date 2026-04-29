"""scripts/ingest/_common.py 단위 테스트."""

import csv
from pathlib import Path

import pytest

from src.ingest import _common as C


def test_normalize_dong_code_pads_8_digits():
    assert C.normalize_dong_code("11440660") == "11440660"
    assert C.normalize_dong_code("1144066000") == "11440660"  # 10자리 → 8자리 trunc
    assert C.normalize_dong_code(11440660) == "11440660"
    assert C.normalize_dong_code("0") is None
    assert C.normalize_dong_code(None) is None
    assert C.normalize_dong_code("") is None


def test_parse_ym_handles_variants():
    assert C.parse_ym("202503") == 202503
    assert C.parse_ym("2025-03") == 202503
    assert C.parse_ym("2025/3") == 202503
    assert C.parse_ym(202503) == 202503
    with pytest.raises(ValueError):
        C.parse_ym("2025")
    with pytest.raises(ValueError):
        C.parse_ym("not-a-date")


def test_parse_int_safe_handles_commas_and_blanks():
    assert C.parse_int_safe("1,234") == 1234
    assert C.parse_int_safe("0") == 0
    assert C.parse_int_safe("") is None
    assert C.parse_int_safe(None) is None
    assert C.parse_int_safe("N/A") is None


def test_write_reject_csv_creates_file_with_header(tmp_seed_dir: Path):
    rows = [{"dong_code": "BAD", "reason": "not 8-digit"}]
    out = C.write_reject_csv(tmp_seed_dir / "reject", "subway_202503", rows)
    assert out is not None
    assert out.exists()
    with out.open() as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == ["dong_code", "reason"]
        assert next(reader) == {"dong_code": "BAD", "reason": "not 8-digit"}


def test_write_reject_csv_no_op_when_empty(tmp_seed_dir: Path):
    out = C.write_reject_csv(tmp_seed_dir / "reject", "empty", [])
    assert out is None
