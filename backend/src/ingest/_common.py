"""ingest 공통 헬퍼 — 동코드/연월/정수 파서 + reject CSV writer."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable


_YM_RE = re.compile(r"^(\d{4})[-/.]?(\d{1,2})$")


def normalize_dong_code(value) -> str | None:
    """행정동 코드를 8자리 문자열로 정규화. 매칭 불가 시 None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s == "0":
        return None
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) < 8:
        return None
    return digits[:8]


def parse_ym(value) -> int:
    """YYYYMM int 로 정규화. 형식 불일치 시 ValueError."""
    if isinstance(value, int) and 100000 <= value <= 999912:
        return value
    s = str(value).strip()
    m = _YM_RE.match(s)
    if not m:
        raise ValueError(f"unparseable ym: {value!r}")
    year, month = int(m.group(1)), int(m.group(2))
    if not (1 <= month <= 12):
        raise ValueError(f"invalid month in ym: {value!r}")
    return year * 100 + month


def parse_int_safe(value) -> int | None:
    """문자열/숫자를 int 로. 빈 값/N/A 등은 None."""
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if not s or s.upper() in {"N/A", "NULL", "-"}:
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def write_reject_csv(reject_dir: Path, name: str, rows: Iterable[dict]) -> Path | None:
    """reject row 들을 reject_dir/<name>.csv 로 기록. 빈 입력 시 None."""
    rows_list = list(rows)
    if not rows_list:
        return None
    reject_dir.mkdir(parents=True, exist_ok=True)
    out = reject_dir / f"{name}.csv"
    fieldnames = list(rows_list[0].keys())
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_list)
    return out
