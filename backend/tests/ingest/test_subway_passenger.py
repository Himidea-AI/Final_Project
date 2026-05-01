"""ingest_subway_passenger 골든 테스트."""

import csv
from pathlib import Path

from src.ingest.ingest_subway_passenger import ingest_one_csv


FIXTURES = Path(__file__).parent / "fixtures"


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_ingest_one_csv_produces_passenger_and_master_rows(tmp_seed_dir: Path):
    out = ingest_one_csv(
        FIXTURES / "subway_sample.csv",
        cleaned_dir=tmp_seed_dir / "cleaned",
        reject_dir=tmp_seed_dir / "reject",
        ym_tag="202503",
    )
    master = _read_csv(out["master"])
    name_to_code = {(r["station_name"], r["line_name"]): r["station_code"] for r in master}
    assert ("홍대입구", "2호선") in name_to_code
    assert ("망원", "6호선") in name_to_code

    passenger = _read_csv(out["passenger"])
    holhik_code = name_to_code[("홍대입구", "2호선")]
    holhik_0301 = next(r for r in passenger if r["date"] == "2025-03-01" and r["station_code"] == holhik_code)
    assert holhik_0301["boarding_cnt"] == "12345"
    assert holhik_0301["alighting_cnt"] == "12100"


def test_ingest_one_csv_writes_reject_for_invalid_line(tmp_seed_dir: Path):
    out = ingest_one_csv(
        FIXTURES / "subway_sample.csv",
        cleaned_dir=tmp_seed_dir / "cleaned",
        reject_dir=tmp_seed_dir / "reject",
        ym_tag="202503",
    )
    reject = _read_csv(out["reject"]) if "reject" in out else []
    assert any(r.get("station_name") == "잘못된역" for r in reject)
