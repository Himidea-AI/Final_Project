"""ingest_ttareungi 골든 테스트."""

import csv
from pathlib import Path

from src.ingest.ingest_ttareungi import ingest_one_csv


FIXTURES = Path(__file__).parent / "fixtures"


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_ingest_one_csv_aggregates_daily_per_station(tmp_seed_dir: Path):
    out = ingest_one_csv(
        FIXTURES / "ttareungi_sample.csv",
        cleaned_dir=tmp_seed_dir / "cleaned",
        reject_dir=tmp_seed_dir / "reject",
        ym_tag="202503",
    )
    usage = _read_csv(out["usage"])
    by_key = {(r["date"], r["station_id"]): r for r in usage}

    a = by_key[("2025-03-01", "ST-100")]
    assert a["rent_cnt"] == "2"
    assert a["return_cnt"] == "1"

    b = by_key[("2025-03-01", "ST-200")]
    assert b["rent_cnt"] == "1"
    assert b["return_cnt"] == "1"

    c = by_key[("2025-03-02", "ST-300")]
    assert c["rent_cnt"] == "1"
    assert c["return_cnt"] == "0"


def test_ingest_one_csv_extracts_master_stations(tmp_seed_dir: Path):
    out = ingest_one_csv(
        FIXTURES / "ttareungi_sample.csv",
        cleaned_dir=tmp_seed_dir / "cleaned",
        reject_dir=tmp_seed_dir / "reject",
        ym_tag="202503",
    )
    master = _read_csv(out["master"])
    ids = {r["station_id"] for r in master}
    assert ids == {"ST-100", "ST-200", "ST-300"}
