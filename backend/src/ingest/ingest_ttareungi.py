"""따릉이 raw 대여이력 → 일×대여소 집계 + master.

입력  : data.seoul.go.kr 따릉이 월별 대여이력 (수십~수백만 행)
출력  : seed/cleaned/seoul_ttareungi_usage_daily_<ym>.csv
        seed/cleaned/master_ttareungi_station_<ym>.csv
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def _detect_encoding(path: Path) -> str:
    """파일 첫 4KB 를 각 인코딩으로 시도해 strict decode 가능한 첫 번째 반환."""
    sample = path.open("rb").read(4096)
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            sample.decode(enc, errors="strict")
            return enc
        except UnicodeDecodeError:
            continue
    return "cp949"  # fallback


def _iter_csv_any_encoding(path: Path):
    enc = _detect_encoding(path)
    with path.open(encoding=enc, errors="replace", newline="") as f:
        yield from csv.DictReader(f)


def ingest_one_csv(
    src: Path,
    *,
    cleaned_dir: Path,
    reject_dir: Path,
    ym_tag: str,
) -> dict[str, Path]:
    cleaned_dir.mkdir(parents=True, exist_ok=True)

    rent_counts: dict[tuple[str, str], int] = defaultdict(int)
    return_counts: dict[tuple[str, str], int] = defaultdict(int)
    master: dict[str, str] = {}

    # 형식 감지: peek first row to see columns
    iterator = _iter_csv_any_encoding(src)
    try:
        first = next(iterator)
    except StopIteration:
        raise RuntimeError(f"empty CSV: {src}")
    cols = set(first.keys())
    cols_stripped = {c.strip() for c in cols}
    is_raw_history = ("대여일시" in cols) and ("반납일시" in cols)
    is_daily_aggregate = ("대여일자" in cols_stripped) and ("이용건수" in cols_stripped)

    def process(r: dict) -> None:
        if is_raw_history:
            rent_dt = (r.get("대여일시") or "").strip()
            rent_id = (r.get("대여 대여소번호") or "").strip()
            rent_name = (r.get("대여 대여소명") or "").strip()
            ret_dt = (r.get("반납일시") or "").strip()
            ret_id = (r.get("반납 대여소번호") or "").strip()
            ret_name = (r.get("반납 대여소명") or "").strip()
            if rent_dt and rent_id:
                d = rent_dt[:10]
                rent_counts[(d, rent_id)] += 1
                if rent_id not in master:
                    master[rent_id] = rent_name
            if ret_dt and ret_id:
                d = ret_dt[:10]
                return_counts[(d, ret_id)] += 1
                if ret_id not in master:
                    master[ret_id] = ret_name
        elif is_daily_aggregate:
            # OA-15246: 대여일자 / 대여소번호 / 대여소 / 대여구분코드 / 성별 / 연령대 / 이용건수
            date_raw = (r.get("대여일자") or "").strip()
            sid = (r.get("대여소번호") or "").strip()
            name = (r.get("대여소") or "").strip()
            cnt_raw = (r.get("이용건수") or r.get(" 이용건수") or "").strip()
            try:
                cnt = int(float(cnt_raw.replace(",", "")))
            except (ValueError, TypeError):
                cnt = 0
            if not date_raw or not sid:
                return
            # date 정규화 (YYYY-MM-DD)
            d = (
                date_raw
                if len(date_raw) == 10 and date_raw[4] == "-"
                else (f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}" if len(date_raw) == 8 else date_raw)
            )
            rent_counts[(d, sid)] += cnt
            if sid not in master:
                master[sid] = name

    process(first)
    for r in iterator:
        process(r)

    keys = set(rent_counts.keys()) | set(return_counts.keys())
    rows = [
        {
            "date": d,
            "station_id": sid,
            "rent_cnt": rent_counts.get((d, sid), 0),
            "return_cnt": return_counts.get((d, sid), 0),
        }
        for (d, sid) in sorted(keys)
    ]

    out_usage = cleaned_dir / f"seoul_ttareungi_usage_daily_{ym_tag}.csv"
    with out_usage.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "station_id", "rent_cnt", "return_cnt"])
        writer.writeheader()
        writer.writerows(rows)

    out_master = cleaned_dir / f"master_ttareungi_station_{ym_tag}.csv"
    master_rows = [
        {
            "station_id": sid,
            "station_name": name,
            "sigungu_code": "",
            "dong_code": "",
            "lat": "",
            "lon": "",
            "opened_at": "",
        }
        for sid, name in sorted(master.items())
    ]
    with out_master.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "station_id",
                "station_name",
                "sigungu_code",
                "dong_code",
                "lat",
                "lon",
                "opened_at",
            ],
        )
        writer.writeheader()
        writer.writerows(master_rows)

    return {"usage": out_usage, "master": out_master}


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
