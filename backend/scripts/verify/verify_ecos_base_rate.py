"""ECOS 기준금리 item_name1 정확한 값 확정.

콘솔 cp949 인코딩 문제 회피 → UTF-8 파일로 출력.
실행: cd backend && python -m scripts.verify_ecos_base_rate
결과: backend/scripts/_ecos_verify_out.txt
"""

import asyncio
from pathlib import Path

from sqlalchemy import text

from src.config.settings import settings
from src.database.postgres import PostgresClient

OUT = Path(__file__).parent / "_ecos_verify_out.txt"


async def main() -> None:
    lines: list[str] = []

    def log(s: str) -> None:
        lines.append(s)

    client = PostgresClient(settings.postgres_url)
    await client.connect()
    try:
        async with client.get_session() as session:
            log("=== [A] 722Y001 stat_code의 모든 item_name1 ===")
            result = await session.execute(
                text(
                    """
                    SELECT DISTINCT item_name1
                    FROM ecos_timeseries
                    WHERE stat_code = '722Y001'
                    ORDER BY item_name1
                    """
                )
            )
            for row in result:
                log(f"  - {row[0]!r}")

            log("\n=== [B] '기준금리'만 포함, '대출/여수신' 제외 필터 후 남는 item_name1 ===")
            result = await session.execute(
                text(
                    """
                    SELECT DISTINCT item_name1
                    FROM ecos_timeseries
                    WHERE item_name1 ILIKE '%기준금리%'
                      AND item_name1 NOT ILIKE '%대출%'
                      AND item_name1 NOT ILIKE '%여수신%'
                    """
                )
            )
            for row in result:
                log(f"  - {row[0]!r}")

            log("\n=== [C] 최신 12개월 기준금리 샘플 (정확히 '한국은행 기준금리'로 추정) ===")
            result = await session.execute(
                text(
                    """
                    SELECT period, data_value, item_name1
                    FROM ecos_timeseries
                    WHERE item_name1 ILIKE '%기준금리%'
                      AND item_name1 NOT ILIKE '%대출%'
                      AND item_name1 NOT ILIKE '%여수신%'
                    ORDER BY period DESC
                    LIMIT 12
                    """
                )
            )
            for row in result:
                log(f"  {row[0]} | {row[1]} | {row[2]!r}")

            log("\n=== [D] item_name2 세부 분류 확인 (혹시 있는지) ===")
            result = await session.execute(
                text(
                    """
                    SELECT DISTINCT item_name1, item_name2, COUNT(*) AS n
                    FROM ecos_timeseries
                    WHERE item_name1 ILIKE '%기준금리%'
                    GROUP BY item_name1, item_name2
                    ORDER BY n DESC
                    """
                )
            )
            for row in result:
                log(f"  ({row[0]!r}, {row[1]!r}) -> {row[2]} rows")
    finally:
        await client.disconnect()

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(lines)} lines to {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
