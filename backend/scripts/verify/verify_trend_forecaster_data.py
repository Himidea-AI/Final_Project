"""trend_forecaster agent: 실제 DB 구조 검증.

실행:
    cd backend && python -m scripts.verify_trend_forecaster_data

검증 대상:
1. ecos_timeseries: 기준금리의 정확한 item_name1 값
2. naver_trend_industry: 최신 기간 + 13종 업종 목록
3. naver_trend_quarterly: 마포 16동 커버 + 최신 분기
4. seoul_adstrd_change_ix: 마포 16동 2025 Q4 데이터
"""

import asyncio

from sqlalchemy import text

from src.config.settings import settings
from src.database.postgres import PostgresClient


async def main() -> None:
    client = PostgresClient(settings.postgres_url)
    await client.connect()

    try:
        async with client.get_session() as session:
            print("\n=== [1] ECOS 기준금리 정확한 item_name1 ===")
            result = await session.execute(
                text(
                    """
                    SELECT stat_code, stat_name, item_name1, item_name2, COUNT(*) AS n_rows
                    FROM ecos_timeseries
                    WHERE stat_name ILIKE '%기준금리%' OR item_name1 ILIKE '%기준금리%'
                    GROUP BY stat_code, stat_name, item_name1, item_name2
                    ORDER BY n_rows DESC
                    LIMIT 20
                    """
                )
            )
            for row in result:
                print(row)

            print("\n=== [2] naver_trend_industry 최신 period + 업종 목록 ===")
            result = await session.execute(
                text("SELECT MAX(period) AS latest, COUNT(DISTINCT industry) AS n_ind FROM naver_trend_industry")
            )
            print(result.first())
            result = await session.execute(
                text(
                    "SELECT DISTINCT industry FROM naver_trend_industry ORDER BY industry"
                )
            )
            industries = [r[0] for r in result]
            print(f"업종 {len(industries)}종: {industries}")

            print("\n=== [3] naver_trend_quarterly 마포 동 목록 + 최신 분기 ===")
            result = await session.execute(
                text(
                    "SELECT DISTINCT dong_name FROM naver_trend_quarterly WHERE scope='mapo' ORDER BY dong_name"
                )
            )
            dongs = [r[0] for r in result]
            print(f"마포 {len(dongs)}동: {dongs}")
            result = await session.execute(
                text(
                    "SELECT MAX(quarter), MIN(quarter) FROM naver_trend_quarterly WHERE scope='mapo'"
                )
            )
            print(f"분기 범위: {result.first()}")

            print("\n=== [4] seoul_adstrd_change_ix 마포 최신 분기 ===")
            result = await session.execute(
                text(
                    """
                    SELECT quarter, dong_code, dong_name, change_ix, change_ix_name,
                           ROUND(opr_sale_mt_avg::numeric, 1) AS opr,
                           ROUND(su_opr_sale_mt_avg::numeric, 1) AS seoul_opr
                    FROM seoul_adstrd_change_ix
                    WHERE dong_code LIKE '11440%'
                      AND quarter = (
                          SELECT MAX(quarter) FROM seoul_adstrd_change_ix
                          WHERE dong_code LIKE '11440%'
                      )
                    ORDER BY dong_code
                    """
                )
            )
            for row in result:
                print(row)

            print("\n=== [5] 서교동(11440660) 샘플: 2026-04 커피 naver ratio ===")
            result = await session.execute(
                text(
                    """
                    SELECT period, ratio FROM naver_trend_industry
                    WHERE industry='커피'
                    ORDER BY period DESC LIMIT 5
                    """
                )
            )
            for row in result:
                print(row)

    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
