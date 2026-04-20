from typing import Any, Dict, List, Optional
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.postgres import PostgresClient
from src.database.models import StoreInfo, LivingPopulation, DistrictSales, GolmokRent, DongMapping
from src.services.population_api import MAPO_DONG_CODES
from src.config.settings import settings

class MarketDataTool:
    """
    실데이터 기반 상권 분석 도구 모음 (Data Binding Tool)
    모든 데이터는 통계적으로 요약되어 에이전트가 이해하기 쉬운 형태로 변환됩니다.
    """

    def __init__(self, db_client: PostgresClient):
        self.db_client = db_client

    # 업종 코드 → kakao_store category 매핑
    _KAKAO_CATEGORY_MAP: Dict[str, str] = {
        "I212": "커피-음료", "카페": "커피-음료", "커피": "커피-음료", "cafe": "커피-음료", "coffee": "커피-음료",
        "I201": "한식음식점", "한식": "한식음식점", "음식점": "한식음식점", "restaurant": "한식음식점",
        "I206": "치킨전문점", "치킨": "치킨전문점", "chicken": "치킨전문점",
        "I207": "패스트푸드점", "피자": "패스트푸드점",
        "I209": "분식전문점", "분식": "분식전문점",
        "I211": "호프-간이주점", "주점": "호프-간이주점",
        "I213": "제과점", "베이커리": "제과점", "빵": "제과점",
        "G209": "패스트푸드점", "편의점": "패스트푸드점", "convenience": "편의점",
    }

    # 사용자 입력 업종명 → DistrictSales.industry_code 매핑 (골목상권 업종코드)
    # 서울 골목상권 CS 코드 공식 매핑 (2026-04 기준)
    # 기존 치킨/제과 코드가 잘못되어 있어 교정 + 중/일/양/패스트푸드/분식 신규 추가
    _SALES_CODE_MAP: Dict[str, str] = {
        # CS100001 한식
        "한식": "CS100001", "한식음식점": "CS100001", "음식점": "CS100001", "restaurant": "CS100001",
        # CS100002 중식
        "중식": "CS100002", "중식음식점": "CS100002", "짜장": "CS100002", "짬뽕": "CS100002",
        # CS100003 일식
        "일식": "CS100003", "일식음식점": "CS100003", "초밥": "CS100003", "스시": "CS100003",
        # CS100004 양식
        "양식": "CS100004", "양식음식점": "CS100004", "파스타": "CS100004", "스테이크": "CS100004",
        # CS100005 제과/베이커리 (기존 CS100011 오류 → CS100005로 교정)
        "제과점": "CS100005", "베이커리": "CS100005", "빵": "CS100005",
        # CS100006 패스트푸드 (기존 코드에선 치킨이 CS100006로 잘못 매핑돼 있었음)
        "패스트푸드": "CS100006", "패스트푸드점": "CS100006", "버거": "CS100006", "피자": "CS100006",
        # CS100007 치킨 (기존 CS100006 오류 → CS100007로 교정)
        "치킨": "CS100007", "치킨전문점": "CS100007", "chicken": "CS100007",
        # CS100008 분식
        "분식": "CS100008", "분식전문점": "CS100008", "떡볶이": "CS100008", "김밥": "CS100008",
        # CS100009 호프/주점
        "호프": "CS100009", "주점": "CS100009", "호프-간이주점": "CS100009", "맥주": "CS100009",
        # CS100010 카페/음료
        "카페": "CS100010", "커피": "CS100010", "커피-음료": "CS100010", "cafe": "CS100010", "coffee": "CS100010",
        "I212": "CS100010",
        # 편의점 (CS100 시리즈 외 별도 코드)
        "편의점": "CS200009", "convenience": "CS200009",
    }

    async def get_competitor_stats(self, lat: float, lon: float, industry_m_code: str, radius_m: int = 500) -> Dict[str, Any]:
        """
        kakao_store 기반 반경 내 현재 영업 중인 경쟁 업체 분석
        (store_info는 폐업 포함 누적 데이터라 kakao_store로 대체)
        """
        category = self._KAKAO_CATEGORY_MAP.get(industry_m_code, industry_m_code)
        lat_delta = radius_m / 111000.0
        lon_delta = radius_m / 88500.0

        async with self.db_client.get_session() as session:
            query = text("""
                SELECT place_name, category, lat, lon,
                       sqrt(power((lat - :lat) * 111000, 2) + power((lon - :lon) * 88500, 2)) AS distance_m
                FROM kakao_store
                WHERE category = :category
                  AND lat BETWEEN :lat_min AND :lat_max
                  AND lon BETWEEN :lon_min AND :lon_max
                ORDER BY distance_m ASC
            """)
            result = await session.execute(query, {
                "lat": lat, "lon": lon, "category": category,
                "lat_min": lat - lat_delta, "lat_max": lat + lat_delta,
                "lon_min": lon - lon_delta, "lon_max": lon + lon_delta,
            })
            competitors = result.fetchall()
            competitors = [c for c in competitors if c.distance_m <= radius_m]

        if not competitors:
            return {"competitor_count": 0, "density_level": "LOW", "summary": f"반경 {radius_m}m 내 경쟁 업체가 없습니다."}

        count = len(competitors)
        avg_dist = sum(c.distance_m for c in competitors) / count
        density = "HIGH" if count > 10 else "MEDIUM" if count > 3 else "LOW"

        return {
            "competitor_count": count,
            "density_level": density,
            "avg_distance_m": round(avg_dist, 1),
            "nearest_competitor": competitors[0].place_name,
            "summary": f"반경 {radius_m}m 내 현재 영업 중인 {count}개의 경쟁 업체 (평균 {round(avg_dist, 1)}m).",
        }

    async def get_population_trends(self, dong_name: str) -> Dict[str, Any]:
        """
        최근 1년(4분기) 유동인구 추이 및 인구통계 요약 (YoY, QoQ 포함)
        """
        dong_code = MAPO_DONG_CODES.get(dong_name)
        if not dong_code:
            return {"error": "행정동 정보를 찾을 수 없습니다."}

        async with self.db_client.get_session() as session:
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
        # 입력값을 DB의 골목상권 업종코드(CS1xxxxx)로 정규화
        normalized_code = self._SALES_CODE_MAP.get(industry_code, industry_code)
        async with self.db_client.get_session() as session:
            # 1. 최근 4분기 매출 트렌드 (마포구 코드 11440으로 한정)
            sales_stmt = select(DistrictSales)\
                .where(
                    DistrictSales.dong_code.like('11440%'),
                    DistrictSales.dong_name == dong_name,
                    DistrictSales.industry_code == normalized_code
                )\
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
            rent_stmt = select(GolmokRent)\
                .where(
                    GolmokRent.dong_code.like('11440%'),
                    GolmokRent.dong_name == dong_name
                )\
                .order_by(GolmokRent.year.desc(), GolmokRent.quarter.desc())\
                .limit(1)
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
