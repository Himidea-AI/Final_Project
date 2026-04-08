"""
서울 전체 유동인구 전처리 스크립트 (IM3-113)

- 원본: LOCAL_PEOPLE_DONG_YYYYMM.csv (86개 파일, 2019.01~2026.02)
- 일×시간대×동 → 분기×동 평균 유동인구로 집계
- 서울 전체 + 2019Q1~2024Q4만 필터링
- 출력: data/processed/seoul_population_quarterly.csv
"""

import sys
from pathlib import Path

import pandas as pd

SRC_DIR = Path(r"C:\Users\804\Desktop\데이터 파일")
PROC_DIR = Path(__file__).resolve().parents[1] / "processed"


def month_to_quarter(yyyymm: str) -> int:
    """'201901' → 20191"""
    year = int(yyyymm[:4])
    month = int(yyyymm[4:6])
    quarter = (month - 1) // 3 + 1
    return year * 10 + quarter


def process_file(fpath: Path) -> pd.DataFrame | None:
    """월별 파일 하나를 읽어서 동별 일평균 유동인구 반환."""
    yyyymm = fpath.stem.replace("LOCAL_PEOPLE_DONG_", "")
    year = int(yyyymm[:4])

    # 2019~2024만 처리
    if year < 2019 or year > 2024:
        return None

    import csv as csv_mod

    rows = []
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            with open(fpath, encoding=enc) as f:
                reader = csv_mod.reader(f)
                next(reader)  # skip header
                for row in reader:
                    if len(row) >= 4 and row[2].startswith("11"):
                        rows.append(row[:4])
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        print(f"  [SKIP] {fpath.name}: 인코딩 실패")
        return None

    if not rows:
        return None

    df = pd.DataFrame(rows, columns=["date", "time_zone", "dong_code", "total_pop"])

    # 일평균 유동인구 (시간대 00 = 전체 합계)
    daily = df[df["time_zone"] == "00"].copy()
    daily["total_pop"] = pd.to_numeric(daily["total_pop"], errors="coerce")

    # 동별 월평균
    monthly = daily.groupby("dong_code", as_index=False)["total_pop"].mean()
    monthly["quarter"] = month_to_quarter(yyyymm)
    monthly["yyyymm"] = yyyymm

    return monthly[["quarter", "yyyymm", "dong_code", "total_pop"]]


def main() -> None:
    print("=== 서울 전체 유동인구 전처리 시작 ===\n")

    files = sorted(SRC_DIR.glob("LOCAL_PEOPLE_DONG_*.csv"))
    print(f"총 파일: {len(files)}개")

    frames = []
    for i, fpath in enumerate(files):
        result = process_file(fpath)
        if result is not None:
            frames.append(result)
            if (i + 1) % 12 == 0:
                print(f"  {i + 1}/{len(files)} 처리 완료")

    if not frames:
        print("[오류] 처리된 파일이 없습니다.")
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True)

    # 월별 데이터를 분기별 평균으로 집계
    quarterly = combined.groupby(["quarter", "dong_code"], as_index=False)["total_pop"].mean().round(1)

    # 2019Q1 ~ 2024Q4 필터링
    quarterly = quarterly[(quarterly["quarter"] >= 20191) & (quarterly["quarter"] <= 20244)].copy()
    quarterly = quarterly.sort_values(["dong_code", "quarter"]).reset_index(drop=True)

    PROC_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROC_DIR / "seoul_population_quarterly.csv"
    quarterly.to_csv(out_path, index=False, encoding="utf-8-sig")

    print("\n=== 완료 ===")
    print(f"출력: {out_path}")
    print(f"행수: {len(quarterly):,}")
    print(f"동 수: {quarterly['dong_code'].nunique()}")
    print(f"분기: {quarterly['quarter'].min()} ~ {quarterly['quarter'].max()}")


if __name__ == "__main__":
    main()
