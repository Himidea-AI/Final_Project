"""
inflow_score ↔ 실매출 상관 검증 스크립트 (Phase B 검증)

목적:
    교통·집객 접근성 점수가 실제 마포 16동 매출과 얼마나 상관되는지 R²로 측정.
    심사에서 "왜 이 점수식이 타당한가"에 대한 실증 근거로 활용.

방법:
    1) score_all_districts()로 16동 inflow_score 계산
    2) seoul_district_sales 최신 8분기 평균 monthly_sales 집계
    3) Pearson 상관 + 단순 선형회귀 R² 계산
    4) 서브점수(subway/bus/fclty) 각각에 대한 R²도 개별 리포트

실행:
    cd backend
    RUN_DB_TESTS=1 python -m tests.validate_inflow_r2

이 스크립트는 pytest에 포함되지 않는다 (파일명이 test_* 아님).
담당: A2 봉환
"""

from __future__ import annotations

import asyncio
import logging
import statistics
from typing import Iterable

from sqlalchemy import func, select

from src.agents.nodes.market_analyst import db_client
from src.database.models import SeoulDistrictSales
from src.services.inflow_scorer import score_all_districts
from src.services.population_api import MAPO_DONG_CODES

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _pearson(xs: Iterable[float], ys: Iterable[float]) -> float:
    """Pearson 상관계수 (numpy 미사용)."""
    xs_l, ys_l = list(xs), list(ys)
    n = len(xs_l)
    if n < 2:
        return 0.0
    mx = statistics.fmean(xs_l)
    my = statistics.fmean(ys_l)
    num = sum((x - mx) * (y - my) for x, y in zip(xs_l, ys_l))
    dx = sum((x - mx) ** 2 for x in xs_l) ** 0.5
    dy = sum((y - my) ** 2 for y in ys_l) ** 0.5
    if dx == 0.0 or dy == 0.0:
        return 0.0
    return num / (dx * dy)


def _r_squared(xs: Iterable[float], ys: Iterable[float]) -> float:
    """단순 선형회귀 R² (Pearson^2와 동일)."""
    r = _pearson(xs, ys)
    return r * r


async def _load_mapo_sales(recent_n_quarters: int = 8) -> dict[str, float]:
    """마포 16동 최신 N개 분기 평균 monthly_sales (업종 전체 합계)."""
    if db_client.engine is None:
        await db_client.connect()

    mapo_codes = list(MAPO_DONG_CODES.values())
    code_to_name = {v: k for k, v in MAPO_DONG_CODES.items()}

    async with db_client.get_session() as session:
        quarter_stmt = (
            select(SeoulDistrictSales.quarter)
            .where(SeoulDistrictSales.dong_code.in_(mapo_codes))
            .distinct()
            .order_by(SeoulDistrictSales.quarter.desc())
            .limit(recent_n_quarters)
        )
        recent_quarters = [r[0] for r in (await session.execute(quarter_stmt)).fetchall()]
        if not recent_quarters:
            return {}

        sales_stmt = (
            select(
                SeoulDistrictSales.dong_code,
                func.avg(SeoulDistrictSales.monthly_sales).label("avg_sales"),
            )
            .where(
                SeoulDistrictSales.dong_code.in_(mapo_codes),
                SeoulDistrictSales.quarter.in_(recent_quarters),
            )
            .group_by(SeoulDistrictSales.dong_code)
        )
        rows = (await session.execute(sales_stmt)).fetchall()

    sales_by_dong: dict[str, float] = {}
    for r in rows:
        dong = code_to_name.get(r.dong_code)
        if dong:
            sales_by_dong[dong] = float(r.avg_sales or 0.0)
    return sales_by_dong


async def run_validation(recent_n_quarters: int = 8) -> None:
    logger.info("=" * 72)
    logger.info("inflow_score ↔ 실매출 R² 검증 시작")
    logger.info(f"매출 데이터 범위: 최신 {recent_n_quarters}개 분기 평균")
    logger.info("=" * 72)

    operfit_map, sales_map = await asyncio.gather(
        score_all_districts(),
        _load_mapo_sales(recent_n_quarters),
    )

    rows: list[tuple[str, float, float, float, float, float]] = []
    for dong in MAPO_DONG_CODES:
        of = operfit_map.get(dong, {})
        sales = sales_map.get(dong)
        if sales is None or not of:
            logger.warning(f"데이터 결측: {dong} (sales={sales}, operfit={'있음' if of else '없음'})")
            continue
        rows.append(
            (
                dong,
                of["inflow_score"],
                of["subway_sub"],
                of["bus_sub"],
                of["fclty_sub"],
                sales,
            )
        )

    if len(rows) < 3:
        logger.error("유효 데이터 3개 미만 — 회귀 불가")
        return

    operfit_vals = [r[1] for r in rows]
    subway_vals = [r[2] for r in rows]
    bus_vals = [r[3] for r in rows]
    fclty_vals = [r[4] for r in rows]
    sales_vals = [r[5] for r in rows]

    r2_total = _r_squared(operfit_vals, sales_vals)
    r2_subway = _r_squared(subway_vals, sales_vals)
    r2_bus = _r_squared(bus_vals, sales_vals)
    r2_fclty = _r_squared(fclty_vals, sales_vals)

    logger.info("")
    logger.info("=" * 72)
    logger.info(f"16동 중 유효 샘플: {len(rows)}개")
    logger.info("=" * 72)
    logger.info(f"  최종 점수 vs 매출       R² = {r2_total:.4f}  (r = {_pearson(operfit_vals, sales_vals):+.4f})")
    logger.info(f"  서브: 지하철 vs 매출    R² = {r2_subway:.4f}  (r = {_pearson(subway_vals, sales_vals):+.4f})")
    logger.info(f"  서브: 버스 vs 매출      R² = {r2_bus:.4f}  (r = {_pearson(bus_vals, sales_vals):+.4f})")
    logger.info(f"  서브: 집객시설 vs 매출  R² = {r2_fclty:.4f}  (r = {_pearson(fclty_vals, sales_vals):+.4f})")
    logger.info("")

    logger.info("상위 점수 동별 매출 대조 (내림차순):")
    logger.info(f"{'동':<10} {'총점':>6} {'지하철':>7} {'버스':>7} {'집객':>7} {'매출(만원)':>14}")
    for dong, total, sub, bus, fcl, sales in sorted(rows, key=lambda r: -r[1]):
        logger.info(f"{dong:<10} {total:>6.1f} {sub:>7.1f} {bus:>7.1f} {fcl:>7.1f} {sales / 10000:>14,.0f}")

    # 해석 가이드
    logger.info("")
    logger.info("=" * 72)
    logger.info("해석 가이드 (상권분석 도메인 경험치):")
    logger.info("  R² >= 0.50 : 강한 양의 상관 — 접근성이 매출의 유의미한 설명변수")
    logger.info("  0.30~0.49 : 중간 상관    — 보조 피처로 유효, winner 결정에 기여")
    logger.info("  0.10~0.29 : 약한 상관    — 가중치 재튜닝 또는 피처 보완 필요")
    logger.info("  < 0.10    : 상관 없음    — 점수식 근본 재검토 필요")
    logger.info("=" * 72)


if __name__ == "__main__":
    asyncio.run(run_validation())
