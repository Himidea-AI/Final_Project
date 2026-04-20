"""
서울 생활인구 실시간 조회 — 서울 열린데이터광장 API 기반

마포구 16개 동의 최신 유동인구를 조회하여
일평균, 동별 상세, 시간대별 분포를 반환한다.
"""

import os
from datetime import datetime, timedelta

import httpx

# 마포구 행정동 코드 매핑
MAPO_DONG_CODES = {
    "아현동": "11440555",
    "공덕동": "11440565",
    "도화동": "11440585",
    "용강동": "11440590",
    "대흥동": "11440600",
    "염리동": "11440610",
    "신수동": "11440630",
    "서강동": "11440655",
    "서교동": "11440660",
    "합정동": "11440680",
    "망원1동": "11440690",
    "망원2동": "11440700",
    "연남동": "11440710",
    "성산1동": "11440720",
    "성산2동": "11440730",
    "상암동": "11440740",
}

DONG_CODE_TO_NAME = {v: k for k, v in MAPO_DONG_CODES.items()}

API_KEY = os.environ.get("SEOUL_OPENDATA_KEY", "")
BASE_URL = "http://openapi.seoul.go.kr:8088"


async def _find_latest_date(client: httpx.AsyncClient) -> str | None:
    """API에서 가장 최근 제공 가능한 날짜를 탐색한다 (최대 14일 전까지)."""
    for days_ago in range(1, 15):
        date_str = (datetime.now() - timedelta(days=days_ago)).strftime("%Y%m%d")
        url = f"{BASE_URL}/{API_KEY}/json/SPOP_LOCAL_RESD_DONG/1/1/{date_str}"
        try:
            resp = await client.get(url)
            if not resp.content:
                continue
            data = resp.json()
            if "SPOP_LOCAL_RESD_DONG" in data:
                return date_str
        except Exception:
            continue
    return None


async def _fetch_mapo_population(date_str: str) -> list[dict]:
    """특정 날짜의 마포구 전체 생활인구 데이터를 가져온다."""
    all_rows = []
    page_size = 1000
    start = 1

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            end = start + page_size - 1
            url = f"{BASE_URL}/{API_KEY}/json/SPOP_LOCAL_RESD_DONG/{start}/{end}/{date_str}"
            try:
                resp = await client.get(url)
                if not resp.content:
                    break
                data = resp.json()
            except Exception:
                break

            if "SPOP_LOCAL_RESD_DONG" not in data:
                break

            rows = data["SPOP_LOCAL_RESD_DONG"]["row"]
            total = int(data["SPOP_LOCAL_RESD_DONG"]["list_total_count"])

            # 마포구만 필터
            mapo_rows = [r for r in rows if r.get("ADSTRD_CODE_SE", "").startswith("11440")]
            all_rows.extend(mapo_rows)

            if start + page_size > total:
                break
            start += page_size

    return all_rows


async def get_population_by_dongs(dong_names: list[str] | None = None) -> dict:
    """
    마포구 동별 유동인구 조회 (최신 날짜 자동 탐색).

    Args:
        dong_names: 조회할 동 이름 리스트. None이면 16개 전체.

    Returns:
        {
            "status": "success",
            "date": "2026-04-10",
            "daily_average": 123456,
            "dong_details": [
                {"dong_name": "서교동", "daily_total": 45678, "peak_hour": 18, "peak_population": 5432, ...},
                ...
            ],
            "hourly_total": {0: 1234, 1: 1100, ..., 23: 2345}
        }
    """
    if not API_KEY:
        return {"status": "error", "message": "SEOUL_OPENDATA_KEY가 설정되지 않았습니다."}

    target_dongs = dong_names or list(MAPO_DONG_CODES.keys())
    target_codes = {MAPO_DONG_CODES[d] for d in target_dongs if d in MAPO_DONG_CODES}

    async with httpx.AsyncClient(timeout=30) as client:
        # 1. 최신 날짜 탐색
        latest_date = await _find_latest_date(client)
        if not latest_date:
            return {"status": "error", "message": "최근 14일 내 유동인구 데이터가 없습니다."}

    # 2. 마포구 전체 데이터 가져오기 (최신 + 전날)
    all_rows = await _fetch_mapo_population(latest_date)

    if not all_rows:
        return {"status": "error", "message": f"{latest_date} 마포구 유동인구 데이터가 없습니다."}

    # 전날 데이터 (비교용) — 최신 날짜 기준 1~3일 전 탐색
    prev_rows = []
    for offset in range(1, 4):
        prev_date = (datetime.strptime(latest_date, "%Y%m%d") - timedelta(days=offset)).strftime("%Y%m%d")
        prev_rows = await _fetch_mapo_population(prev_date)
        if prev_rows:
            break

    # 3. 요청한 동만 필터
    filtered = [r for r in all_rows if r["ADSTRD_CODE_SE"] in target_codes]

    # 4. 동별 집계
    dong_stats: dict[str, dict] = {}
    hourly_total: dict[int, float] = {}

    for row in filtered:
        code = row["ADSTRD_CODE_SE"]
        dong_name = DONG_CODE_TO_NAME.get(code, code)
        hour = int(row.get("TMZON_PD_SE", 0))
        pop = float(row.get("TOT_LVPOP_CO", 0))

        # 연령대별 집계 (20~39세)
        male_20_39 = sum(float(row.get(f"MALE_{age}_LVPOP_CO", 0)) for age in ["F20T24", "F25T29", "F30T34", "F35T39"])
        female_20_39 = sum(
            float(row.get(f"FEMALE_{age}_LVPOP_CO", 0)) for age in ["F20T24", "F25T29", "F30T34", "F35T39"]
        )

        if dong_name not in dong_stats:
            dong_stats[dong_name] = {
                "dong_name": dong_name,
                "dong_code": code,
                "daily_total": 0,
                "peak_hour": 0,
                "peak_population": 0,
                "hourly": {},
                "male_20_39": 0,
                "female_20_39": 0,
            }

        dong_stats[dong_name]["daily_total"] += pop
        dong_stats[dong_name]["hourly"][hour] = pop
        dong_stats[dong_name]["male_20_39"] += male_20_39
        dong_stats[dong_name]["female_20_39"] += female_20_39

        hourly_total[hour] = hourly_total.get(hour, 0) + pop

    # 피크 시간대 계산
    for dong_name, stats in dong_stats.items():
        hourly = stats["hourly"]
        if hourly:
            peak_hour = max(hourly, key=hourly.get)
            stats["peak_hour"] = peak_hour
            stats["peak_population"] = round(hourly[peak_hour])
        stats["daily_total"] = round(stats["daily_total"])
        stats["male_20_39"] = round(stats["male_20_39"])
        stats["female_20_39"] = round(stats["female_20_39"])

    # 5. 결과 조립
    dong_list = sorted(dong_stats.values(), key=lambda x: x["daily_total"], reverse=True)

    # hourly에서 dict 제거 (응답에 포함하면 너무 커짐)
    for d in dong_list:
        d.pop("hourly", None)

    daily_avg = round(sum(d["daily_total"] for d in dong_list) / len(dong_list)) if dong_list else 0

    # 전날 평균 계산 (비교용)
    prev_avg = 0
    change_pct = 0.0
    if prev_rows:
        prev_filtered = [r for r in prev_rows if r["ADSTRD_CODE_SE"] in target_codes]
        prev_dong_totals: dict[str, float] = {}
        for row in prev_filtered:
            code = row["ADSTRD_CODE_SE"]
            dong_name = DONG_CODE_TO_NAME.get(code, code)
            pop = float(row.get("TOT_LVPOP_CO", 0))
            prev_dong_totals[dong_name] = prev_dong_totals.get(dong_name, 0) + pop
        if prev_dong_totals:
            # 동일한 동 수로 비교 (최신 날짜에 있는 동만)
            matched_dongs = [d for d in dong_stats if d in prev_dong_totals]
            if matched_dongs:
                prev_avg = round(sum(prev_dong_totals[d] for d in matched_dongs) / len(matched_dongs))
                if prev_avg > 0:
                    change_pct = round((daily_avg - prev_avg) / prev_avg * 100, 1)

    formatted_date = f"{latest_date[:4]}-{latest_date[4:6]}-{latest_date[6:]}"

    return {
        "status": "success",
        "date": formatted_date,
        "data_delay_note": "서울시 생활인구 데이터는 3~5일 지연 제공됩니다.",
        "dong_count": len(dong_list),
        "daily_average": daily_avg,
        "prev_daily_average": prev_avg,
        "change_pct": change_pct,
        "total_population": sum(d["daily_total"] for d in dong_list),
        "dong_details": dong_list,
        "hourly_total": {k: round(v) for k, v in sorted(hourly_total.items())},
    }
