"""행정안전부 동별 전입/전출 raw → seed CSV.

입력  : KOSIS / 주민등록이동통계 (행정구역코드/행정구역명/시점/연령대/전입자수/전출자수)
출력  : seed/cleaned/seoul_dong_migration_monthly_<ym>.csv
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from src.ingest import _common as C


_AGE_TOTAL = {"총계", "전체", "계"}
_AGE_2030 = {"20-29세", "30-39세", "20-29", "30-39"}


def _read_csv_any_encoding(path: Path) -> list[dict]:
    last_err: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            with path.open(encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError as e:
            last_err = e
    raise RuntimeError(f"unable to decode {path}: {last_err}")


def ingest_one_csv(
    src: Path,
    *,
    cleaned_dir: Path,
    reject_dir: Path,
    ym_tag: str,
) -> dict[str, Path]:
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    rows = _read_csv_any_encoding(src)

    agg: dict[str, dict] = defaultdict(
        lambda: {
            "move_in_cnt": None,
            "move_out_cnt": None,
            "move_in_2030": 0,
            "move_out_2030": 0,
        }
    )
    rejects: list[dict] = []

    for r in rows:
        dong_code = C.normalize_dong_code(r.get("행정구역코드"))
        dong_name = (r.get("행정구역명") or "").strip()
        if dong_code is None:
            rejects.append(
                {
                    "dong_code": str(r.get("행정구역코드") or ""),
                    "dong_name": dong_name,
                    "_reason": "invalid dong_code",
                }
            )
            continue
        try:
            ym = C.parse_ym(r.get("시점"))
        except ValueError as e:
            rejects.append({"dong_code": dong_code, "dong_name": dong_name, "_reason": str(e)})
            continue

        age = (r.get("연령대") or "").strip()
        in_cnt = C.parse_int_safe(r.get("전입자수")) or 0
        out_cnt = C.parse_int_safe(r.get("전출자수")) or 0
        key = f"{ym}|{dong_code}"
        bucket = agg[key]
        bucket["ym"] = ym
        bucket["dong_code"] = dong_code

        if age in _AGE_TOTAL:
            bucket["move_in_cnt"] = in_cnt
            bucket["move_out_cnt"] = out_cnt
        elif age in _AGE_2030:
            bucket["move_in_2030"] += in_cnt
            bucket["move_out_2030"] += out_cnt

    cleaned_rows = []
    for v in agg.values():
        if v["move_in_cnt"] is None or v["move_out_cnt"] is None:
            rejects.append({"dong_code": v["dong_code"], "_reason": "missing total row"})
            continue
        cleaned_rows.append(
            {
                "ym": v["ym"],
                "dong_code": v["dong_code"],
                "move_in_cnt": v["move_in_cnt"],
                "move_out_cnt": v["move_out_cnt"],
                "net_move": v["move_in_cnt"] - v["move_out_cnt"],
                "move_in_2030": v["move_in_2030"],
                "move_out_2030": v["move_out_2030"],
            }
        )

    out_migration = cleaned_dir / f"seoul_dong_migration_monthly_{ym_tag}.csv"
    fieldnames = [
        "ym",
        "dong_code",
        "move_in_cnt",
        "move_out_cnt",
        "net_move",
        "move_in_2030",
        "move_out_2030",
    ]
    with out_migration.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    result: dict[str, Path] = {"migration": out_migration}
    reject_path = C.write_reject_csv(reject_dir, f"migration_{ym_tag}", rejects)
    if reject_path is not None:
        result["reject"] = reject_path
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--cleaned-dir", type=Path, required=True)
    parser.add_argument("--reject-dir", type=Path, required=True)
    args = parser.parse_args()
    for src in sorted(args.raw_dir.glob("*.csv")):
        ym = src.stem[-6:] if src.stem[-6:].isdigit() else "unknown"
        ingest_one_csv(
            src,
            cleaned_dir=args.cleaned_dir,
            reject_dir=args.reject_dir,
            ym_tag=ym,
        )


if __name__ == "__main__":
    main()
