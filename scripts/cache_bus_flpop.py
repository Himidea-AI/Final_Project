"""
버스 유동인구(bus_flpop) 분기별 집계 캐시 생성 스크립트

bus_boarding_daily(371만 행) GROUP BY → data/processed/bus_flpop_quarterly.csv
dong_subway_access.nearest_subway 기반으로 역명 → dong_code 매핑

매핑 전략:
1) dong_subway_access: dong_name + nearest_subway → 역명으로 버스 정류장 매칭
2) district_sales: dong_name → dong_code 역참조
3) 최종 CSV: quarter, dong_code, bus_flpop

Usage:
    python -m scripts.cache_bus_flpop

출력: data/processed/bus_flpop_quarterly.csv
  컬럼: quarter (int), dong_code (str), bus_flpop (float)

담당: B2 — 수지니
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "bus_flpop_quarterly.csv"

_pw = os.environ.get("POSTGRES_PASSWORD", "postgres")
_host = os.environ.get("POSTGRES_HOST", "192.168.0.28")
_port = os.environ.get("POSTGRES_PORT", "5432")
_db = os.environ.get("POSTGRES_DB", "mapo_simulator")
DB_URL = os.environ.get(
    "POSTGRES_URL",
    f"postgresql://postgres:{_pw}@{_host}:{_port}/{_db}",
)


def main() -> None:
    engine = create_engine(DB_URL, echo=False)

    try:
        # 1) dong_subway_access: dong_name + nearest_subway 로드
        logger.info("dong_subway_access 로드 중...")
        try:
            subway_df = pd.read_sql(
                text("SELECT dong_name, nearest_subway FROM dong_subway_access"),
                engine,
            )
            logger.info("dong_subway_access: %d rows", len(subway_df))
        except Exception as e:
            logger.warning("dong_subway_access 로드 실패: %s", e)
            subway_df = pd.DataFrame()

        # 2) district_sales: dong_name → dong_code 매핑 (마포구)
        logger.info("dong_name → dong_code 매핑 로드 중...")
        try:
            dong_map_df = pd.read_sql(
                text("SELECT DISTINCT dong_name, dong_code FROM district_sales WHERE dong_code LIKE '11440%'"),
                engine,
            )
            dong_map_df["dong_code"] = dong_map_df["dong_code"].astype(str)
            dong_name_to_code: dict[str, str] = dict(zip(dong_map_df["dong_name"], dong_map_df["dong_code"]))
            logger.info("dong_code 매핑: %d개 동", len(dong_name_to_code))
        except Exception as e:
            logger.warning("dong_code 매핑 로드 실패: %s", e)
            dong_name_to_code = {}

        # 3) bus_boarding_daily 분기별 집계 (역명별 승하차 합)
        logger.info("bus_boarding_daily 집계 중... (371만 행, 수 초 소요)")
        bus_df = pd.read_sql(
            text("""
                SELECT
                    (EXTRACT(YEAR FROM use_date)::int * 10
                     + EXTRACT(QUARTER FROM use_date)::int) AS quarter,
                    station_name,
                    SUM(boarding_count + alighting_count) AS bus_flpop_raw
                FROM bus_boarding_daily
                GROUP BY quarter, station_name
            """),
            engine,
        )
        logger.info("버스 집계 완료: %d rows", len(bus_df))

        # 4) dong_name 매핑
        if not subway_df.empty and dong_name_to_code:
            # nearest_subway = "합정역 6호선" → 역명만 추출("합정역") → station_name 매칭
            # station_name 예: "합정역", "합정역(가상)", "공덕역.공덕시장"
            subway_df["station_key"] = subway_df["nearest_subway"].str.split().str[0]
            subway_list = subway_df[["dong_name", "station_key"]].dropna().values.tolist()

            def match_dong_name(station: str) -> str | None:
                for dong_name, key in subway_list:
                    if key and str(key) in str(station):
                        return dong_name
                return None

            bus_df["dong_name"] = bus_df["station_name"].apply(match_dong_name)
        else:
            # fallback: 동 이름 직접 문자열 매칭 (정밀도 낮음)
            logger.warning("dong_name fallback 매핑 사용 중")
            known_dongs = list(dong_name_to_code.keys()) if dong_name_to_code else []

            def match_dong_name_fallback(station: str) -> str | None:  # type: ignore[misc]
                return next((d for d in known_dongs if d.replace("동", "") in str(station)), None)

            bus_df["dong_name"] = bus_df["station_name"].apply(match_dong_name_fallback)

        # 5) dong_name → dong_code 변환
        bus_df["dong_code"] = bus_df["dong_name"].map(dong_name_to_code)

        matched = bus_df[bus_df["dong_code"].notna()].copy()
        if matched.empty:
            logger.error("dong_code 매핑 실패 — bus_flpop CSV를 생성할 수 없습니다.")
            logger.info("매핑된 dong_name 샘플: %s", bus_df["dong_name"].dropna().unique()[:5])
            return

        logger.info("매핑 성공: %d / %d 역", matched["station_name"].nunique(), bus_df["station_name"].nunique())

        result = (
            matched.groupby(["quarter", "dong_code"], as_index=False)["bus_flpop_raw"]
            .sum()
            .rename(columns={"bus_flpop_raw": "bus_flpop"})
        )
        result["quarter"] = result["quarter"].astype(int)
        result["dong_code"] = result["dong_code"].astype(str)

        # 6) CSV 저장
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(OUTPUT_PATH, index=False)
        logger.info("저장 완료: %s (%d rows)", OUTPUT_PATH, len(result))
        logger.info("샘플:\n%s", result.head(10).to_string(index=False))

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
