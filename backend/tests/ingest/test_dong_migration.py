"""ingest_dong_migration 골든 테스트."""

import csv
from pathlib import Path

from src.ingest.ingest_dong_migration import ingest_one_csv


FIXTURES = Path(__file__).parent / "fixtures"


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_ingest_one_csv_aggregates_by_dong_and_2030(tmp_seed_dir: Path):
    out = ingest_one_csv(
        FIXTURES / "migration_sample.csv",
        cleaned_dir=tmp_seed_dir / "cleaned",
        reject_dir=tmp_seed_dir / "reject",
        ym_tag="202503",
    )
    rows = _read_csv(out["migration"])
    by_dong = {r["dong_code"]: r for r in rows}

    h = by_dong["11440660"]
    assert h["ym"] == "202503"
    assert h["move_in_cnt"] == "500"
    assert h["move_out_cnt"] == "450"
    assert h["net_move"] == "50"
    assert h["move_in_2030"] == "350"
    assert h["move_out_2030"] == "270"

    m = by_dong["11440680"]
    assert m["move_in_2030"] == "140"
    assert m["move_out_2030"] == "160"


def test_ingest_one_csv_rejects_invalid_dong_code(tmp_seed_dir: Path):
    out = ingest_one_csv(
        FIXTURES / "migration_sample.csv",
        cleaned_dir=tmp_seed_dir / "cleaned",
        reject_dir=tmp_seed_dir / "reject",
        ym_tag="202503",
    )
    rejects = _read_csv(out["reject"]) if "reject" in out else []
    assert any("서울특별시" in r.get("dong_name", "") for r in rejects)
