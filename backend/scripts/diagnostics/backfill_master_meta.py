"""마스터 테이블 메타 backfill — DB derived data 로 NULL 채우기.

audit-null-orphan-2026-05-04 발견 NULL 100% 컬럼 중 다른 테이블에서 derive 가능한 것 채움.

채우는 항목:
1. ``dong_mapping.floating_pop`` ← ``living_population.total_pop`` 평균 (마포 16동)
2. ``dong_mapping.avg_age`` ← ``living_population`` 연령대별 인구 가중평균
3. ``dong_mapping.total_households`` ← ``sgis_household`` indicator='total_households' 2024 (12동, 4동 행정동 코드 변경)
4. ``industry_master.industry_name_alt`` ← ``BUSINESS_TYPE_MAPPING.label_en`` (CS100001~CS100010)

채울 수 없는 항목 (외부 데이터 또는 별 ETL 필요):
- ``dong_mapping.trdar_codes`` — trdar↔dong 매핑 테이블 부재
- ``dong_mapping.total_households`` 4동 (아현/공덕/도화/서강) — sgis 옛 행정동 코드와 매핑 필요
- ``master_ttareungi_station`` lat/lon/dong_code — 따릉이 API
- ``master_subway_station`` 261건 좌표 — 외부 지하철 마스터
- ``kakao_store.brand_name`` 3,214 — fuzzy 매칭 위험 (개인매장 다수)
- ``kakao_store_hours.mon~sun_hours`` — 카카오 API 재호출
- ``seoul_realtime_hotspots.cmrc_*`` — 서울 실시간 도시 API 재호출
- ``rent_cost`` 거래 4 컬럼 — 컬럼 정의 결함 (drop 권장)

Usage:
    cd backend && python scripts/diagnostics/backfill_master_meta.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.config.business_type_mapping import BUSINESS_TYPE_MAPPING  # noqa: E402
from src.config.settings import settings  # noqa: E402

# 생활인구 컬럼 → 대표 연령 (가중평균용)
AGE_MIDPOINTS = [
    ("male_0_9", "female_0_9", 5),
    ("male_10_14", "female_10_14", 12),
    ("male_15_19", "female_15_19", 17),
    ("male_20_24", "female_20_24", 22),
    ("male_25_29", "female_25_29", 27),
    ("male_30_34", "female_30_34", 32),
    ("male_35_39", "female_35_39", 37),
    ("male_40_44", "female_40_44", 42),
    ("male_45_49", "female_45_49", 47),
    ("male_50_54", "female_50_54", 52),
    ("male_55_59", "female_55_59", 57),
    ("male_60_64", "female_60_64", 62),
    ("male_65_69", "female_65_69", 67),
    ("male_70_plus", "female_70_plus", 75),
]


def _build_avg_age_sql() -> tuple[str, str]:
    """가중평균 SQL 의 분자/분모 표현식."""
    numerator = " + ".join(f"{mid} * (COALESCE(lp.{m},0) + COALESCE(lp.{f},0))" for m, f, mid in AGE_MIDPOINTS)
    denominator = " + ".join(f"COALESCE(lp.{m},0) + COALESCE(lp.{f},0)" for m, f, _ in AGE_MIDPOINTS)
    return numerator, denominator


def backfill_dong_mapping(conn: sa.engine.Connection) -> dict:
    """dong_mapping 의 floating_pop/avg_age/total_households 채움."""
    numerator, denominator = _build_avg_age_sql()

    # floating_pop + avg_age (16/16)
    pop_age = conn.execute(
        sa.text(
            f"""
        UPDATE dong_mapping dm SET
            floating_pop = sub.avg_total,
            avg_age = sub.weighted_avg_age
        FROM (
            SELECT
                lp.dong_code,
                AVG(lp.total_pop) AS avg_total,
                SUM({numerator}) / NULLIF(SUM({denominator}), 0) AS weighted_avg_age
            FROM living_population lp
            WHERE lp.dong_code IN (SELECT dong_code FROM dong_mapping)
            GROUP BY lp.dong_code
        ) sub
        WHERE dm.dong_code = sub.dong_code
        """
        )
    ).rowcount

    # total_households (12/16, 행정동 변경 4동 미매핑)
    hh = conn.execute(
        sa.text(
            """
        UPDATE dong_mapping dm SET total_households = ROUND(sub.value)::int
        FROM (
            SELECT LEFT(area_code, 8) AS dong, value
            FROM sgis_household
            WHERE indicator = 'total_households'
              AND year = (SELECT MAX(year) FROM sgis_household WHERE indicator = 'total_households')
              AND LEFT(area_code, 5) = '11440'
        ) sub
        WHERE dm.dong_code = sub.dong
        """
        )
    ).rowcount

    return {"floating_pop+avg_age": pop_age, "total_households": hh}


def backfill_industry_master(conn: sa.engine.Connection) -> int:
    """industry_master.industry_name_alt 를 BUSINESS_TYPE_MAPPING.label_en 로 채움 (10/101)."""
    updates = 0
    for entry in BUSINESS_TYPE_MAPPING.values():
        result = conn.execute(
            sa.text("UPDATE industry_master SET industry_name_alt = :alt WHERE industry_code = :code"),
            {"alt": entry["label_en"], "code": entry["cs_code"]},
        )
        updates += result.rowcount
    return updates


def main() -> None:
    engine = sa.create_engine(settings.postgres_url)
    with engine.begin() as conn:
        dong_result = backfill_dong_mapping(conn)
        industry_result = backfill_industry_master(conn)

    print("=== Backfill 결과 ===")
    print(f"  dong_mapping.floating_pop + avg_age: {dong_result['floating_pop+avg_age']} rows")
    print(f"  dong_mapping.total_households:        {dong_result['total_households']} rows (4동 미매핑)")
    print(f"  industry_master.industry_name_alt:    {industry_result} rows")

    with engine.connect() as conn:
        null_check = conn.execute(
            sa.text(
                """SELECT
            COUNT(*) FILTER (WHERE floating_pop IS NULL) AS fl,
            COUNT(*) FILTER (WHERE avg_age IS NULL) AS age,
            COUNT(*) FILTER (WHERE total_households IS NULL) AS hh,
            COUNT(*) FILTER (WHERE trdar_codes IS NULL) AS trdar
        FROM dong_mapping"""
            )
        ).fetchone()
        print()
        print("=== dong_mapping NULL 잔존 ===")
        print(f"  floating_pop:     {null_check[0]}/16")
        print(f"  avg_age:          {null_check[1]}/16")
        print(f"  total_households: {null_check[2]}/16 (행정동 변경 4동)")
        print(f"  trdar_codes:      {null_check[3]}/16 (trdar↔dong 매핑 부재)")


if __name__ == "__main__":
    main()
