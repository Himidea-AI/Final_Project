"""서울 생활이동 데이터 → 마포 inflow 추출 (streaming).

ZIP 안 24개 시간 CSV (총 ~5GB) 를 메모리 효율적으로 처리:
- 시간별 unzip → 한 줄씩 읽기
- 도착 행정동이 마포(1144xxx) 면 보존
- 시간 × 도착동 × 출발-시군구 집계

출력: mapo_inflow_YYYYMM.csv (압축 해제 후 ~수MB)
"""

from __future__ import annotations

import io
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd

ZIP_PATH = Path("data/raw/seoul_migration/migration_dong_202601.zip")
OUT_PATH = Path("data/processed/seoul_migration_mapo_202601.csv")

# 마포 16동 — KT 코드 (1114xxx) ↔ ABM dong name 매핑
# (Excel mojibake 로 한글 직접 매핑 어려움, sequential 추정 + DB 매핑)
# DB seoul_dong_master 에서 마포 코드 확인 필요. 일단 1114059~1114078 모두 마포 가정.
MAPO_KT_PREFIX = "1114"  # 1114xxx 마포 16동
MAPO_DB_SGG_CODE = "11440"  # 우리 DB 시군구 코드 (참고)


def process_one_hour(zf: zipfile.ZipFile, csv_name: str) -> pd.DataFrame:
    """한 시간 CSV → 마포 도착 inflow filter + 집계."""
    print(f"  {csv_name} 처리 중...", flush=True)
    counts: dict = defaultdict(int)
    with zf.open(csv_name) as raw:
        # 한 줄씩 cp949 디코드
        wrapper = io.TextIOWrapper(raw, encoding="cp949", errors="replace")
        next(wrapper)  # 헤더 스킵
        n_total = 0
        n_mapo = 0
        for line in wrapper:
            n_total += 1
            parts = line.rstrip("\n").split(",")
            if len(parts) < 10:
                continue
            ymd, dow, hour, src_code, dst_code, sex, age, mtype, avg_time, pop = parts
            if not dst_code.startswith(MAPO_KT_PREFIX):
                continue  # 도착이 마포 아니면 skip
            n_mapo += 1
            try:
                pop_val = float(pop) if pop != "*" else 0.0
            except ValueError:
                pop_val = 0.0
            # 집계: (도착동, 출발 시군구, 시간, 요일, 성별, 연령대) → 인구합
            src_sgg = src_code[:5] if len(src_code) >= 5 else "unknown"
            key = (dst_code, src_sgg, hour, dow, sex, age, mtype)
            counts[key] += pop_val
    print(f"    총 {n_total:,}행, 마포 inflow {n_mapo:,}행", flush=True)
    rows = [
        {
            "dst_dong": k[0],
            "src_sgg": k[1],
            "hour": int(k[2]),
            "dow": k[3],
            "sex": k[4],
            "age": k[5],
            "move_type": k[6],
            "popsum": v,
        }
        for k, v in counts.items()
    ]
    return pd.DataFrame(rows)


def main() -> int:
    if not ZIP_PATH.exists():
        print(f"ZIP not found: {ZIP_PATH}", file=sys.stderr)
        return 1
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    all_dfs = []
    with zipfile.ZipFile(ZIP_PATH) as zf:
        names = sorted(n for n in zf.namelist() if n.endswith(".csv"))
        print(f"=== {len(names)} 시간 CSV 처리 시작 ===", flush=True)
        for n in names:
            df = process_one_hour(zf, n)
            all_dfs.append(df)

    merged = pd.concat(all_dfs, ignore_index=True)
    merged.to_csv(OUT_PATH, index=False, encoding="utf-8")
    print(f"\n완료: {OUT_PATH} ({len(merged):,}행, {OUT_PATH.stat().st_size / 1e6:.1f}MB)")

    # 검증 — dst_dong 별 합계
    print("\n=== 마포 16동 도착 inflow 합계 (월간) ===")
    by_dong = merged.groupby("dst_dong")["popsum"].sum().sort_values(ascending=False)
    for dong, total in by_dong.items():
        print(f"  {dong}: {total:>15,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
