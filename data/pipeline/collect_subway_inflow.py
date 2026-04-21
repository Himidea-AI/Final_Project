"""
서울 열린데이터 지하철 시간대별 승하차 → 마포구 외부 유입 추정

담당: A1 -- 데이터 엔지니어 (찬영)

수집 방식:
  - CardSubwayTime API: YYYYMM × 역 × 시간(04~다음날03시) 승하차 인원
  - 게이트 태그 기준이라 환승객은 자동 제외 (호선간 환승 미포함)
  - 마포구 행정동에 매핑된 역만 추출

내부 이동 보정:
  - 시간별 net_inflow = 하차 - 승차
  - 마포 내부 이동(예: 홍대→마포역)은 하차+1, 승차+1로 상쇄됨
  - 양수 = 외부에서 마포 진입 (출근 8~9시 오피스, 저녁 18~22시 홍대/합정)
  - 음수 = 마포에서 외부 유출 (저녁 18시 오피스 떠남)

Usage:
    python data/pipeline/collect_subway_inflow.py --month 202604
    python data/pipeline/collect_subway_inflow.py --months 202601 202602 202603
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd  # noqa: E402
import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

OUT_DIR = ROOT / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("SEOUL_OPENDATA_KEY", "")
BASE_URL = "http://openapi.seoul.go.kr:8088"
SERVICE = "CardSubwayTime"

# 마포구 지하철역 -> 행정동 매핑 (게이트 단위, 환승역은 한 번만 카운트)
# 같은 역명에 여러 호선이 운영되어도 API 응답은 LINE_NUM별로 분리되므로 합산 처리
MAPO_STATIONS: dict[str, str] = {
    "공덕": "공덕동",
    "마포": "도화동",
    "대흥(서강대앞)": "대흥동",
    "애오개": "염리동",
    "광흥창(서강)": "신수동",
    "홍대입구": "서교동",
    "합정": "합정동",
    "망원": "망원1동",
    "마포구청": "성산1동",
    "월드컵경기장(성산)": "성산2동",
    "디지털미디어시티": "상암동",
    "아현": "아현동",
}

HOUR_RANGE = list(range(4, 24)) + [0, 1, 2, 3]  # 04시~익일 03시

# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


def fetch_month(month: str, retries: int = 3) -> list[dict]:
    """월별 전체 역 시간대 승하차 (한 번에 1000행씩 페이지네이션)."""
    if not API_KEY:
        raise RuntimeError("SEOUL_OPENDATA_KEY 환경변수 필요")

    all_rows: list[dict] = []
    start = 1
    page = 1000

    while True:
        end = start + page - 1
        url = f"{BASE_URL}/{API_KEY}/json/{SERVICE}/{start}/{end}/{month}"
        for attempt in range(retries):
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                break
            except (requests.RequestException, ValueError) as e:
                if attempt == retries - 1:
                    print(f"  [!] {month} {start}-{end} 실패: {e}")
                    return all_rows
                time.sleep(3 * (attempt + 1))

        body = data.get(SERVICE, {})
        result_code = body.get("RESULT", {}).get("CODE", "")
        if result_code not in ("INFO-000", ""):
            msg = body.get("RESULT", {}).get("MESSAGE", "")
            print(f"  [!] API 응답: {result_code} {msg}")
            break

        rows = body.get("row", [])
        if not rows:
            break
        all_rows.extend(rows)
        print(f"  ... {start}-{end}: {len(rows)}행 (누적 {len(all_rows)})")

        if len(rows) < page:
            break
        start += page
        time.sleep(0.5)

    return all_rows


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------


def parse_rows(rows: list[dict]) -> pd.DataFrame:
    """원시 응답을 long-format DataFrame으로."""
    records = []
    for r in rows:
        station = (r.get("STTN") or r.get("SUB_STA_NM") or "").strip()
        dong = MAPO_STATIONS.get(station)
        if not dong:
            continue

        month = r.get("USE_MM") or r.get("USE_DT") or ""
        line = r.get("SBWY_ROUT_LN_NM") or r.get("LINE_NUM", "")

        for h in HOUR_RANGE:
            on_key = f"HR_{h}_GET_ON_NOPE"
            off_key = f"HR_{h}_GET_OFF_NOPE"
            board = _safe_int(r.get(on_key))
            alight = _safe_int(r.get(off_key))
            if board == 0 and alight == 0:
                continue
            records.append(
                {
                    "month": month,
                    "hour": h,
                    "station": station,
                    "dong": dong,
                    "line": line,
                    "board": board,
                    "alight": alight,
                }
            )

    return pd.DataFrame(records)


def _safe_int(v) -> int:
    if v is None or v == "":
        return 0
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------


def aggregate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """역×시간 합계 + 동×시간 평균 두 단계 집계.

    CardSubwayTime은 월간 누적이므로 일평균으로 정규화 (월 30일 기준)."""
    # 1) 같은 역의 여러 호선 합산 (월×시간×역×동)
    by_station = df.groupby(["month", "hour", "station", "dong"], as_index=False)[["board", "alight"]].sum()
    by_station["net_inflow"] = by_station["alight"] - by_station["board"]

    # 2) 동×시간으로 월평균 → 30일로 나눠 일평균 환산
    by_dong_hour = by_station.groupby(["dong", "hour"], as_index=False)[["board", "alight", "net_inflow"]].mean()
    for col in ("board", "alight", "net_inflow"):
        by_dong_hour[col] = (by_dong_hour[col] / 30).round(1)

    return by_station, by_dong_hour


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="서울 지하철 마포구 외부유입 수집")
    parser.add_argument("--month", help="단일 월 YYYYMM (예: 202604)")
    parser.add_argument("--months", nargs="+", help="복수 월 (예: 202601 202602 202603)")
    args = parser.parse_args()

    months = args.months or ([args.month] if args.month else [])
    if not months:
        # 기본: 최근 3개월
        today = pd.Timestamp.today()
        months = [(today - pd.DateOffset(months=i + 1)).strftime("%Y%m") for i in range(3)][::-1]

    print("=" * 60)
    print("  서울 지하철 마포구 시간대별 승하차 수집")
    print(f"  대상 월: {', '.join(months)}")
    print(f"  대상 역: {len(MAPO_STATIONS)}개")
    print("=" * 60)

    all_rows: list[dict] = []
    for m in months:
        print(f"\n[{m}] 수집 중...")
        rows = fetch_month(m)
        print(f"  -> 원시 {len(rows)}행")
        all_rows.extend(rows)

    if not all_rows:
        print("\n[!] 수집된 데이터 없음 (API 키 또는 월 확인)")
        return 1

    print(f"\n[파싱] 마포 역만 추출 중... (전체 {len(all_rows)}행)")
    df = parse_rows(all_rows)
    print(f"  -> 마포 매칭 {len(df)}행 ({df['station'].nunique()}개 역)")

    if df.empty:
        print("[!] 마포 역 매칭 0건")
        return 1

    by_station, by_dong_hour = aggregate(df)

    out_raw = OUT_DIR / "subway_mapo_raw.csv"
    out_dong = OUT_DIR / "subway_inflow_by_dong_hour.csv"
    by_station.to_csv(out_raw, index=False, encoding="utf-8-sig")
    by_dong_hour.to_csv(out_dong, index=False, encoding="utf-8-sig")
    print(f"\n[저장] {out_raw.name} ({len(by_station)}행)")
    print(f"[저장] {out_dong.name} ({len(by_dong_hour)}행)")

    # 요약
    print("\n" + "=" * 60)
    print("  동×시간대 평일 평균 net_inflow TOP")
    print("=" * 60)
    top = by_dong_hour.nlargest(10, "net_inflow")[["dong", "hour", "alight", "board", "net_inflow"]]
    for _, r in top.iterrows():
        print(
            f"  {r['dong']:>6} {int(r['hour']):>2}시: 하차 {r['alight']:>7.0f} - 승차 {r['board']:>7.0f}"
            f" = +{r['net_inflow']:>7.0f}"
        )

    print("\n  유출 TOP (음수)")
    bot = by_dong_hour.nsmallest(5, "net_inflow")[["dong", "hour", "alight", "board", "net_inflow"]]
    for _, r in bot.iterrows():
        print(
            f"  {r['dong']:>6} {int(r['hour']):>2}시: 하차 {r['alight']:>7.0f} - 승차 {r['board']:>7.0f}"
            f" = {r['net_inflow']:>+8.0f}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
