from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.postgres import PostgresClient
from src.database.models import StoreInfo, LivingPopulation, DistrictSales, GolmokRent, DongMapping
from src.config.settings import settings

class MarketDataTool:
    """
    실데이터 기반 상권 분석 도구 모음 (Data Binding Tool)
    모든 데이터는 통계적으로 요약되어 에이전트가 이해하기 쉬운 형태로 변환됩니다.
    """

    def __init__(self, db_client: PostgresClient):
        self.db_client = db_client

    async def get_competitor_stats(self, lat: float, lon: float, industry_m_code: str, radius_m: int = 500) -> Dict[str, Any]:
        """
        pgvector를 사용하여 반경 내 유사 업종 경쟁 업체 분석 및 밀집도 리턴
        """
        async with self.db_client.get_session() as session:
            # 1. pgvector L2 거리 연산 (<->)을 사용하여 반경 내 점포 검색 (HNSW 인덱스 활용)
            # 좌표는 [lat, lon] 벡터 형태라고 가정
            query = text("""
                SELECT store_name, industry_s, lat, lon,
                       (location_vector <-> CAST(:vec AS vector)) as distance
                FROM store_info
                WHERE industry_m_code = :ind_code
                AND (location_vector <-> CAST(:vec AS vector)) < :radius_limit
                ORDER BY distance ASC
            """)

            # asyncpg 호환을 위해 vector를 string 형태로 전달 (ARRAY[]::vector 구문 미지원)
            # 500m 반경 제한 (위경도 단위 근사치 사용 혹은 PostGIS st_distance_sphere 연계)
            result = await session.execute(query, {
                "vec": f"[{lat},{lon}]",
                "ind_code": industry_m_code,
                "radius_limit": radius_m / 111000.0 # 미터를 위경도 도 단위로 대략 변환
            })
            
            competitors = result.fetchall()
            
            if not competitors:
                return {"competitor_count": 0, "density_level": "LOW", "detail": "반경 500m 내 경쟁 업체가 없습니다."}

            count = len(competitors)
            avg_dist = sum(c.distance * 111000 for c in competitors) / count # 다시 m로 변환
            
            density = "HIGH" if count > 10 else "MEDIUM" if count > 3 else "LOW"
            
            return {
                "competitor_count": count,
                "density_level": density,
                "avg_distance_m": round(avg_dist, 1),
                "nearest_competitor": competitors[0].store_name if competitors else None,
                "summary": f"반경 500m 내 {count}개의 경쟁 업체가 밀집해 있으며, 평균 거리는 {round(avg_dist, 1)}m입니다."
            }

    async def get_population_trends(self, dong_name: str) -> Dict[str, Any]:
        """
        최근 1년(4분기) 유동인구 추이 및 인구통계 요약 (YoY, QoQ 포함)
        """
        async with self.db_client.get_session() as session:
            # 행정동 코드로 매핑
            mapping_stmt = select(DongMapping.dong_code).where(DongMapping.dong_name == dong_name)
            mapping_res = await session.execute(mapping_stmt)
            dong_code = mapping_res.scalar()
            
            if not dong_code:
                return {"error": "행정동 정보를 찾을 수 없습니다."}

            # 최근 4분기 데이터 조회
            pop_stmt = select(
                LivingPopulation.date,
                func.sum(LivingPopulation.total_pop).label("total_pop")
            ).where(LivingPopulation.dong_code == dong_code)\
             .group_by(LivingPopulation.date)\
             .order_by(LivingPopulation.date.desc())\
             .limit(4)
            
            pop_res = await session.execute(pop_stmt)
            trends = pop_res.fetchall()
            
            if len(trends) < 2:
                return {"current_pop": trends[0].total_pop if trends else 0, "trend": "정보 부족"}

            latest_pop = trends[0].total_pop
            prev_pop = trends[1].total_pop
            qoq_growth = ((latest_pop - prev_pop) / prev_pop) * 100
            
            # YoY는 1년 전 데이터가 존재할 경우 계산 (여기서는 4번째 데이터와 비교)
            yoy_growth = ((latest_pop - trends[-1].total_pop) / trends[-1].total_pop) * 100 if len(trends) == 4 else None

            return {
                "current_pop": round(latest_pop, 0),
                "qoq_growth": round(qoq_growth, 2),
                "yoy_growth": round(yoy_growth, 2) if yoy_growth is not None else "N/A",
                "trend_status": "UP" if qoq_growth > 0 else "DOWN",
                "summary": f"현재 유동인구는 {round(latest_pop, 0):,}명이며, 전분기 대비 {round(qoq_growth, 2)}% {'증가' if qoq_growth > 0 else '감소'}했습니다."
            }

    async def get_commercial_insights(self, dong_name: str, industry_code: str) -> Dict[str, Any]:
        """
        최근 1년 매출 추이 및 '통계적 요약본' 리턴
        """
        async with self.db_client.get_session() as session:
            # 1. 최근 4분기 매출 트렌드
            sales_stmt = select(DistrictSales)\
                .where(DistrictSales.dong_name == dong_name, DistrictSales.industry_code == industry_code)\
                .order_by(DistrictSales.quarter.desc())\
                .limit(4)
            
            sales_res = await session.execute(sales_stmt)
            rows = sales_res.scalars().all()
            
            if not rows:
                return {"error": "매출 데이터를 찾을 수 없습니다."}

            latest = rows[0]
            avg_revenue = latest.monthly_sales / latest.monthly_count if latest.monthly_count > 0 else 0
            
            # 성장성 분석
            qoq_sales = ((latest.monthly_sales - rows[1].monthly_sales) / rows[1].monthly_sales * 100) if len(rows) > 1 else 0
            yoy_sales = ((latest.monthly_sales - rows[-1].monthly_sales) / rows[-1].monthly_sales * 100) if len(rows) == 4 else 0

            # 인구통계학적 특성 (가장 매출이 높은 성별/연령대 추출)
            demographics = {
                "male": latest.male_count,
                "female": latest.female_count,
                "age_20s": latest.age_20_count,
                "age_30s": latest.age_30_count,
                "age_40s": latest.age_40_count
            }
            top_demo = max(demographics, key=demographics.get)

            return {
                "avg_monthly_revenue": round(avg_revenue, 0),
                "qoq_growth": round(qoq_sales, 2),
                "yoy_growth": round(yoy_sales, 2),
                "dominant_customer": top_demo,
                "trend": "성장" if qoq_sales > 0 else "정체",
                "statistical_summary": f"건당 평균 결제액은 {round(avg_revenue, 0):,}원이며, {top_demo} 고객층이 주도하고 있습니다. 최근 1년 매출은 {round(yoy_sales, 2)}% 변화했습니다."
            }

    async def get_rent_insight(self, dong_name: str) -> Dict[str, Any]:
        """
        임대료 데이터 조회 및 수익성 근거 마련
        """
        async with self.db_client.get_session() as session:
            rent_stmt = select(GolmokRent).where(GolmokRent.dong_name == dong_name).order_by(GolmokRent.year.desc(), GolmokRent.quarter.desc()).limit(1)
            rent_res = await session.execute(rent_stmt)
            rent_data = rent_res.scalar()

            if not rent_data:
                return {"avg_rent_3_3m2": 0, "status": "데이터 없음"}

            # 마포구 평균 임대료와 비교 로직 (Expert Insights)
            # 여기서는 하드코딩된 임계치를 사용하거나 서브쿼리로 전체 평균 계산 가능
            mapo_avg = 150000 # 예시: 마포구 평균 15만원
            is_expensive = rent_data.rent_total > mapo_avg

            return {
                "avg_rent_3_3m2": rent_data.rent_total,
                "rent_1f": rent_data.rent_1f,
                "affordability": "CAUTION" if is_expensive else "SAFE",
                "summary": f"해당 지역의 평당(3.3㎡) 임대료는 {rent_data.rent_total:,}원 수준으로, 마포구 평균 대비 {'높은' if is_expensive else '낮은'} 편입니다."
            }
