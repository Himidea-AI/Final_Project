import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, text

from src.database.postgres import PostgresClient
from src.database.models import LivingPopulation, DistrictSales, GolmokRent
from src.services.population_api import MAPO_DONG_CODES

logger = logging.getLogger(__name__)


# POI → 마포구 행정동 코드 역매핑 (seoul_realtime_hotspots.area_cd → district_sales.dong_code)
# 2026-04 기준 수동 검증. `demographic_depth_agent` 계획 문서 참조.
_MAPO_POI_REVERSE: Dict[str, List[str]] = {
    "11440660": ["POI007"],  # 서교동 → 홍대 관광특구
    "11440680": ["POI053"],  # 합정동 → 합정역
    "11440710": ["POI073"],  # 연남동 → 연남동
    "11440740": ["POI106"],  # 상암동 → 월드컵공원
}


class MarketDataTool:
    """
    실데이터 기반 상권 분석 도구 모음 (Data Binding Tool)
    모든 데이터는 통계적으로 요약되어 에이전트가 이해하기 쉬운 형태로 변환됩니다.
    """

    def __init__(self, db_client: PostgresClient):
        self.db_client = db_client

    # 업종 코드 → kakao_store category 매핑
    _KAKAO_CATEGORY_MAP: Dict[str, str] = {
        "I212": "커피-음료",
        "카페": "커피-음료",
        "커피": "커피-음료",
        "cafe": "커피-음료",
        "coffee": "커피-음료",
        "I201": "한식음식점",
        "한식": "한식음식점",
        "음식점": "한식음식점",
        "restaurant": "한식음식점",
        "I206": "치킨전문점",
        "치킨": "치킨전문점",
        "chicken": "치킨전문점",
        "I207": "패스트푸드점",
        "피자": "패스트푸드점",
        "I209": "분식전문점",
        "분식": "분식전문점",
        "I211": "호프-간이주점",
        "주점": "호프-간이주점",
        "I213": "제과점",
        "베이커리": "제과점",
        "빵": "제과점",
        "G209": "패스트푸드점",
        "편의점": "패스트푸드점",
        "convenience": "편의점",
    }

    # 사용자 입력 업종명 → DistrictSales.industry_code 매핑 (골목상권 업종코드)
    # 서울 골목상권 CS 코드 공식 매핑 (2026-04 기준)
    # 기존 치킨/제과 코드가 잘못되어 있어 교정 + 중/일/양/패스트푸드/분식 신규 추가
    _SALES_CODE_MAP: Dict[str, str] = {
        # CS100001 한식
        "한식": "CS100001",
        "한식음식점": "CS100001",
        "음식점": "CS100001",
        "restaurant": "CS100001",
        # CS100002 중식
        "중식": "CS100002",
        "중식음식점": "CS100002",
        "짜장": "CS100002",
        "짬뽕": "CS100002",
        # CS100003 일식
        "일식": "CS100003",
        "일식음식점": "CS100003",
        "초밥": "CS100003",
        "스시": "CS100003",
        # CS100004 양식
        "양식": "CS100004",
        "양식음식점": "CS100004",
        "파스타": "CS100004",
        "스테이크": "CS100004",
        # CS100005 제과/베이커리 (기존 CS100011 오류 → CS100005로 교정)
        "제과점": "CS100005",
        "베이커리": "CS100005",
        "빵": "CS100005",
        # CS100006 패스트푸드 (기존 코드에선 치킨이 CS100006로 잘못 매핑돼 있었음)
        "패스트푸드": "CS100006",
        "패스트푸드점": "CS100006",
        "버거": "CS100006",
        "피자": "CS100006",
        # CS100007 치킨 (기존 CS100006 오류 → CS100007로 교정)
        "치킨": "CS100007",
        "치킨전문점": "CS100007",
        "chicken": "CS100007",
        # CS100008 분식
        "분식": "CS100008",
        "분식전문점": "CS100008",
        "떡볶이": "CS100008",
        "김밥": "CS100008",
        # CS100009 호프/주점
        "호프": "CS100009",
        "주점": "CS100009",
        "호프-간이주점": "CS100009",
        "맥주": "CS100009",
        # CS100010 카페/음료
        "카페": "CS100010",
        "커피": "CS100010",
        "커피-음료": "CS100010",
        "cafe": "CS100010",
        "coffee": "CS100010",
        "I212": "CS100010",
        # 편의점 (CS100 시리즈 외 별도 코드)
        "편의점": "CS200009",
        "convenience": "CS200009",
    }

    # 사용자 입력(CS 코드/브랜드/업종명) → naver_trend_industry.industry 값 매핑
    # naver DataLab은 '커피'/'카페'를 분리하지만 CS 코드는 CS100010 (카페/음료) 하나로 통합.
    # 브랜드 단위 정밀 매핑을 위해 브랜드명도 직접 키로 등록.
    #
    # ⚠️ DB 실측 (audit-2026-05-04): naver_trend_industry 에 별 industry 13종 존재 —
    # 한식·중식·일식·양식·제과·패스트푸드·치킨·분식·호프·카페·**피자**·편의점·**커피**.
    # "피자"/"커피" 가 카페·패스트푸드와 별 카테고리이므로 BUSINESS_TYPE_MAPPING.naver_industry
    # ("커피"→"카페", "피자"→흡수)와 의도적으로 다름. 변경 시 Naver 트렌드 데이터 손실.
    _NAVER_INDUSTRY_MAP: Dict[str, str] = {
        # CS 업종 코드 → naver industry (AgentState.industry_filter 수용)
        "CS100001": "한식",
        "CS100002": "중식",
        "CS100003": "일식",
        "CS100004": "양식",
        "CS100005": "제과",
        "CS100006": "패스트푸드",
        "CS100007": "치킨",
        "CS100008": "분식",
        "CS100009": "호프",
        "CS100010": "카페",
        "CS200009": "편의점",
        # 한글 업종명 (business_type)
        "한식": "한식",
        "중식": "중식",
        "일식": "일식",
        "양식": "양식",
        "제과": "제과",
        "베이커리": "제과",
        "빵": "제과",
        "패스트푸드": "패스트푸드",
        "버거": "패스트푸드",
        "치킨": "치킨",
        "분식": "분식",
        "호프": "호프",
        "주점": "호프",
        "카페": "카페",
        "커피": "커피",
        "피자": "피자",
        "편의점": "편의점",
        # 영문 (business_type 영문 케이스 방어)
        "cafe": "카페",
        "coffee": "커피",
        "restaurant": "한식",
        "chicken": "치킨",
        "burger": "패스트푸드",
        "pizza": "피자",
        "convenience": "편의점",
        # 브랜드 → naver industry (대표 프랜차이즈)
        "빽다방": "커피",
        "메가MGC커피": "커피",
        "메가커피": "커피",
        "이디야커피": "커피",
        "이디야": "커피",
        "컴포즈커피": "커피",
        "컴포즈": "커피",
        "스타벅스": "카페",
        "투썸플레이스": "카페",
        "투썸": "카페",
        "할리스": "카페",
        "폴바셋": "카페",
        "교촌치킨": "치킨",
        "교촌": "치킨",
        "BBQ": "치킨",
        "bhc": "치킨",
        "BHC": "치킨",
        "굽네치킨": "치킨",
        "굽네": "치킨",
        "맘스터치": "패스트푸드",
        "롯데리아": "패스트푸드",
        "버거킹": "패스트푸드",
        "맥도날드": "패스트푸드",
        "도미노피자": "피자",
        "피자헛": "피자",
        "미스터피자": "피자",
        "파리바게뜨": "제과",
        "뚜레쥬르": "제과",
        "던킨도너츠": "제과",
        "던킨": "제과",
    }

    def resolve_industry(
        self,
        industry_filter: Optional[str] = None,
        brand_name: Optional[str] = None,
        business_type: Optional[str] = None,
        default: str = "한식",
    ) -> str:
        """사용자 입력 → naver_trend_industry.industry 값.

        우선순위: industry_filter(CS 코드) → brand_name → business_type → default.
        대소문자 구분 없음 (소문자 fallback).
        """
        for candidate in (industry_filter, brand_name, business_type):
            if not candidate:
                continue
            if candidate in self._NAVER_INDUSTRY_MAP:
                return self._NAVER_INDUSTRY_MAP[candidate]
            lower = candidate.lower()
            if lower in self._NAVER_INDUSTRY_MAP:
                return self._NAVER_INDUSTRY_MAP[lower]
        return default

    async def get_competitor_stats(
        self, lat: float, lon: float, industry_m_code: str, radius_m: int = 500
    ) -> Dict[str, Any]:
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
            result = await session.execute(
                query,
                {
                    "lat": lat,
                    "lon": lon,
                    "category": category,
                    "lat_min": lat - lat_delta,
                    "lat_max": lat + lat_delta,
                    "lon_min": lon - lon_delta,
                    "lon_max": lon + lon_delta,
                },
            )
            competitors = result.fetchall()
            competitors = [c for c in competitors if c.distance_m <= radius_m]

        if not competitors:
            return {
                "competitor_count": 0,
                "density_level": "LOW",
                "summary": f"반경 {radius_m}m 내 경쟁 업체가 없습니다.",
            }

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
        # [dev 65408da] DongMapping DB 조회 → MAPO_DONG_CODES 직접 매핑 (0명 버그 해결)
        dong_code = MAPO_DONG_CODES.get(dong_name)
        if not dong_code:
            return {"error": "행정동 정보를 찾을 수 없습니다."}

        async with self.db_client.get_session() as session:
            # 최근 4분기 데이터 조회
            pop_stmt = (
                select(LivingPopulation.date, func.sum(LivingPopulation.total_pop).label("total_pop"))
                .where(LivingPopulation.dong_code == dong_code)
                .group_by(LivingPopulation.date)
                .order_by(LivingPopulation.date.desc())
                .limit(4)
            )

            pop_res = await session.execute(pop_stmt)
            trends = pop_res.fetchall()

            if len(trends) < 2:
                return {"current_pop": trends[0].total_pop if trends else 0, "trend": "정보 부족"}

            latest_pop = trends[0].total_pop
            prev_pop = trends[1].total_pop
            qoq_growth = ((latest_pop - prev_pop) / prev_pop) * 100

            # YoY는 1년 전 데이터가 존재할 경우 계산 (여기서는 4번째 데이터와 비교)
            yoy_growth = (
                ((latest_pop - trends[-1].total_pop) / trends[-1].total_pop) * 100 if len(trends) == 4 else None
            )

            return {
                "current_pop": round(latest_pop, 0),
                "qoq_growth": round(qoq_growth, 2),
                "yoy_growth": round(yoy_growth, 2) if yoy_growth is not None else "N/A",
                "trend_status": "UP" if qoq_growth > 0 else "DOWN",
                "summary": f"현재 유동인구는 {round(latest_pop, 0):,}명이며, 전분기 대비 {round(qoq_growth, 2)}% {'증가' if qoq_growth > 0 else '감소'}했습니다.",
            }

    async def get_commercial_insights(self, dong_name: str, industry_code: str) -> Dict[str, Any]:
        """
        최근 1년 매출 추이 및 '통계적 요약본' 리턴
        """
        # 입력값을 DB의 골목상권 업종코드(CS1xxxxx)로 정규화
        normalized_code = self._SALES_CODE_MAP.get(industry_code, industry_code)
        async with self.db_client.get_session() as session:
            # 1. 최근 4분기 매출 트렌드 (마포구 코드 11440으로 한정)
            sales_stmt = (
                select(DistrictSales)
                .where(
                    DistrictSales.dong_code.like("11440%"),
                    DistrictSales.dong_name == dong_name,
                    DistrictSales.industry_code == normalized_code,
                )
                .order_by(DistrictSales.quarter.desc())
                .limit(4)
            )

            sales_res = await session.execute(sales_stmt)
            rows = sales_res.scalars().all()

            if not rows:
                return {"error": "매출 데이터를 찾을 수 없습니다."}

            latest = rows[0]
            avg_revenue = latest.monthly_sales / latest.monthly_count if latest.monthly_count > 0 else 0

            # 성장성 분석
            qoq_sales = (
                ((latest.monthly_sales - rows[1].monthly_sales) / rows[1].monthly_sales * 100) if len(rows) > 1 else 0
            )
            yoy_sales = (
                ((latest.monthly_sales - rows[-1].monthly_sales) / rows[-1].monthly_sales * 100)
                if len(rows) == 4
                else 0
            )

            # 인구통계학적 특성 (가장 매출이 높은 성별/연령대 추출)
            demographics = {
                "male": latest.male_count,
                "female": latest.female_count,
                "age_20s": latest.age_20_count,
                "age_30s": latest.age_30_count,
                "age_40s": latest.age_40_count,
            }
            top_demo = max(demographics, key=demographics.get)

            # 피크 시간대 (실측 매출 건수 기반)
            time_slots = {
                "00:00~06:00": latest.time_00_06_count or 0,
                "06:00~11:00": latest.time_06_11_count or 0,
                "11:00~14:00": latest.time_11_14_count or 0,
                "14:00~17:00": latest.time_14_17_count or 0,
                "17:00~21:00": latest.time_17_21_count or 0,
                "21:00~24:00": latest.time_21_24_count or 0,
            }
            peak_time = max(time_slots, key=time_slots.get)

            return {
                "avg_monthly_revenue": round(avg_revenue, 0),
                "qoq_growth": round(qoq_sales, 2),
                "yoy_growth": round(yoy_sales, 2),
                "dominant_customer": top_demo,
                "male": latest.male_count or 0,
                "female": latest.female_count or 0,
                "age_20s": latest.age_20_count or 0,
                "age_30s": latest.age_30_count or 0,
                "age_40s": latest.age_40_count or 0,
                "peak_time": peak_time,
                "trend": "성장" if qoq_sales > 0 else "정체",
                "statistical_summary": f"건당 평균 결제액은 {round(avg_revenue, 0):,}원이며, {top_demo} 고객층이 주도하고 있습니다. 최근 1년 매출은 {round(yoy_sales, 2)}% 변화했습니다.",
            }

    async def get_rent_insight(self, dong_name: str) -> Dict[str, Any]:
        """
        임대료 데이터 조회 및 수익성 근거 마련
        """
        async with self.db_client.get_session() as session:
            rent_stmt = (
                select(GolmokRent)
                .where(GolmokRent.dong_code.like("11440%"), GolmokRent.dong_name == dong_name)
                .order_by(GolmokRent.year.desc(), GolmokRent.quarter.desc())
                .limit(1)
            )
            rent_res = await session.execute(rent_stmt)
            rent_data = rent_res.scalar()

            if not rent_data:
                return {"avg_rent_3_3m2": 0, "status": "데이터 없음"}

            # 마포구 평균 임대료와 비교 로직 (Expert Insights)
            # 여기서는 하드코딩된 임계치를 사용하거나 서브쿼리로 전체 평균 계산 가능
            mapo_avg = 150000  # 예시: 마포구 평균 15만원
            is_expensive = rent_data.rent_total > mapo_avg

            return {
                "avg_rent_3_3m2": rent_data.rent_total,
                "rent_1f": rent_data.rent_1f,
                "affordability": "CAUTION" if is_expensive else "SAFE",
                "summary": f"해당 지역의 평당(3.3㎡) 임대료는 {rent_data.rent_total:,}원 수준으로, 마포구 평균 대비 {'높은' if is_expensive else '낮은'} 편입니다.",
            }

    # ------------------------------------------------------------------
    # demographic_depth_agent 전용 쿼리 함수 (Task 1)
    # ------------------------------------------------------------------

    async def get_demographic_sales_breakdown(
        self,
        dong_code: str,
        industry_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        district_sales 최근 분기의 연령/성별/시간대/요일별 매출 breakdown.

        Args:
            dong_code: 행정동 코드 8자리 (예: "11440660")
            industry_filter: 업종 코드 (예: "CS100010"). None이면 전체 업종 합산.

        Returns:
            연령/성별/시간대/요일별 매출 분해 dict. 데이터 없으면 {"error": ...}.
        """
        async with self.db_client.get_session() as session:
            # 1) 최신 분기 찾기 (dong_code + optional industry_filter)
            if industry_filter:
                latest_q = await session.execute(
                    text("SELECT MAX(quarter) AS q FROM district_sales WHERE dong_code = :dc AND industry_code = :ic"),
                    {"dc": dong_code, "ic": industry_filter},
                )
            else:
                latest_q = await session.execute(
                    text("SELECT MAX(quarter) AS q FROM district_sales WHERE dong_code = :dc"),
                    {"dc": dong_code},
                )
            latest_quarter = latest_q.scalar()
            if latest_quarter is None:
                return {"error": "no sales data", "dong_code": dong_code}

            # 2) 한 쿼리로 모든 25개 breakdown 컬럼 SUM
            agg_sql = """
                SELECT
                    SUM(monthly_sales) AS monthly_sales,
                    SUM(age_10_sales) AS age_10, SUM(age_20_sales) AS age_20,
                    SUM(age_30_sales) AS age_30, SUM(age_40_sales) AS age_40,
                    SUM(age_50_sales) AS age_50, SUM(age_60_above_sales) AS age_60p,
                    SUM(male_sales) AS male, SUM(female_sales) AS female,
                    SUM(time_00_06_sales) AS t0006, SUM(time_06_11_sales) AS t0611,
                    SUM(time_11_14_sales) AS t1114, SUM(time_14_17_sales) AS t1417,
                    SUM(time_17_21_sales) AS t1721, SUM(time_21_24_sales) AS t2124,
                    SUM(mon_sales) AS mon, SUM(tue_sales) AS tue, SUM(wed_sales) AS wed,
                    SUM(thu_sales) AS thu, SUM(fri_sales) AS fri,
                    SUM(sat_sales) AS sat, SUM(sun_sales) AS sun,
                    SUM(weekday_sales) AS weekday, SUM(weekend_sales) AS weekend
                FROM district_sales
                WHERE dong_code = :dc AND quarter = :q
            """
            params: Dict[str, Any] = {"dc": dong_code, "q": latest_quarter}
            if industry_filter:
                agg_sql += " AND industry_code = :ic"
                params["ic"] = industry_filter

            row = (await session.execute(text(agg_sql), params)).fetchone()

            total = int(row.monthly_sales or 0)
            if total == 0:
                return {
                    "error": "zero sales",
                    "dong_code": dong_code,
                    "quarter": int(latest_quarter),
                }

            def _i(v: Any) -> int:
                return int(v or 0)

            return {
                "dong_code": dong_code,
                "quarter": int(latest_quarter),
                "monthly_sales": total,
                "age_breakdown": {
                    "10": _i(row.age_10),
                    "20": _i(row.age_20),
                    "30": _i(row.age_30),
                    "40": _i(row.age_40),
                    "50": _i(row.age_50),
                    "60+": _i(row.age_60p),
                },
                "gender_breakdown": {
                    "male": _i(row.male),
                    "female": _i(row.female),
                },
                "time_breakdown": {
                    "00-06": _i(row.t0006),
                    "06-11": _i(row.t0611),
                    "11-14": _i(row.t1114),
                    "14-17": _i(row.t1417),
                    "17-21": _i(row.t1721),
                    "21-24": _i(row.t2124),
                },
                "weekday_breakdown": {
                    "mon": _i(row.mon),
                    "tue": _i(row.tue),
                    "wed": _i(row.wed),
                    "thu": _i(row.thu),
                    "fri": _i(row.fri),
                    "sat": _i(row.sat),
                    "sun": _i(row.sun),
                },
                "weekday_vs_weekend": {
                    "weekday": _i(row.weekday),
                    "weekend": _i(row.weekend),
                },
            }

    async def get_realtime_resident_visitor(self, dong_code: str) -> Dict[str, Any]:
        """
        seoul_realtime_hotspots에서 최근 7일 평균 거주(resident_rate) / 방문(visitor_rate) 비율 조회.

        POI 위치 데이터를 행정동 단위로 역매핑 (`_MAPO_POI_REVERSE`).
        매핑되지 않은 dong_code는 null 응답.

        Args:
            dong_code: 행정동 코드 8자리

        Returns:
            {
                "resident_rate": float | None,    # 0-100 %
                "visitor_rate":  float | None,    # 0-100 %
                "source_poi":    list[str] | None,
                "sample_size":   int,              # 7일 내 수집된 행 수
            }
        """
        pois = _MAPO_POI_REVERSE.get(dong_code)
        if not pois:
            return {
                "resident_rate": None,
                "visitor_rate": None,
                "source_poi": None,
                "sample_size": 0,
            }

        async with self.db_client.get_session() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT AVG(resident_rate) AS r_avg, AVG(visitor_rate) AS v_avg, "
                        "COUNT(*) AS n "
                        "FROM seoul_realtime_hotspots "
                        "WHERE area_cd = ANY(:pois) "
                        "AND collected_at >= NOW() - INTERVAL '7 days'"
                    ),
                    {"pois": pois},
                )
            ).fetchone()

        sample = int(row.n or 0)
        return {
            "resident_rate": round(float(row.r_avg), 2) if row.r_avg is not None else None,
            "visitor_rate": round(float(row.v_avg), 2) if row.v_avg is not None else None,
            "source_poi": list(pois),
            "sample_size": sample,
        }

    # ---- 소득/고령/인구추세 헬퍼 (get_area_income_context 내부용) ----
    # NOTE: 각 헬퍼는 **독립 세션**을 사용합니다. SQLAlchemy AsyncSession + asyncpg는
    # 단일 커넥션에서 동시 쿼리를 지원하지 않아 (InterfaceError: another operation is
    # in progress), asyncio.gather 병렬 실행 시 세션을 분리해야 안정적입니다.

    async def _fetch_area_income(self) -> Optional[float]:
        """
        kosis_regional_income 서울(region_code='11')의 1인당 개인처분가능소득 최신값.

        item_code='T3' ("1인당 개인처분가능소득") 우선, fallback으로 item_name LIKE.
        단위: **천원** (2024년 실측 32,224 = 연 약 3,222만원/人).
        """
        async with self.db_client.get_session() as session:
            res = await session.execute(
                text(
                    "SELECT value_num FROM kosis_regional_income "
                    "WHERE region_code = '11' AND item_code = 'T3' "
                    "ORDER BY period_value DESC LIMIT 1"
                )
            )
            value = res.scalar()
            if value is not None:
                return float(value)

            # fallback — item_name 매칭 (스키마 변동 대비)
            res2 = await session.execute(
                text(
                    "SELECT value_num FROM kosis_regional_income "
                    "WHERE region_code = '11' AND item_name LIKE '%처분가능%' "
                    "ORDER BY period_value DESC LIMIT 1"
                )
            )
            v2 = res2.scalar()
            return float(v2) if v2 is not None else None

    async def _fetch_elderly_ratio(self) -> Optional[float]:
        """elderly_ratio_region 서울특별시 최신 ym의 노인 비율 (%)."""
        async with self.db_client.get_session() as session:
            res = await session.execute(
                text("SELECT elderly_ratio FROM elderly_ratio_region WHERE region = :region ORDER BY ym DESC LIMIT 1"),
                {"region": "서울특별시"},
            )
            v = res.scalar()
            return float(v) if v is not None else None

    async def _fetch_population_trend(self, dong_code: str) -> str:
        """
        resident_pop_monthly 최근 최대 6개월(해당 dong_code)에서 전/후 평균 비교.

        - ≥6 rows: 3-vs-3 split (최근 3개월 vs 과거 3개월)
        - 4-5 rows: half-vs-half split (n=5는 중간 row 무시)
        - ≤3 rows: 'unknown'

        mapping: district_sales.dong_code(8) + '00' = resident_pop_monthly.region_code(10)
        Returns: 'growing' | 'stable' | 'declining' | 'unknown'.
        """
        region_code = f"{dong_code}00"
        async with self.db_client.get_session() as session:
            res = await session.execute(
                text("SELECT ym, total_pop FROM resident_pop_monthly WHERE region_code = :rc ORDER BY ym DESC LIMIT 6"),
                {"rc": region_code},
            )
            rows = res.fetchall()
        n = len(rows)
        if n < 4:
            return "unknown"

        # rows는 ym DESC → 앞 half개가 최신(recent), 뒤 half개가 과거(older)
        half = n // 2
        recent_avg = sum(r.total_pop for r in rows[:half]) / half
        past_avg = sum(r.total_pop for r in rows[-half:]) / half
        if past_avg == 0:
            return "unknown"
        ratio = recent_avg / past_avg
        if ratio > 1.01:
            return "growing"
        if ratio < 0.99:
            return "declining"
        return "stable"

    @staticmethod
    def _classify_income_level(value_num: Optional[float]) -> str:
        """
        value_num 단위: 천원 (KOSIS 2024 기준 서울 T3 ≈ 32,224).
        - high: ≥ 35,000 천원 (3,500만원/年/人)
        - mid:  25,000 ~ 35,000
        - low:  < 25,000
        """
        if value_num is None:
            return "unknown"
        if value_num >= 35000:
            return "high"
        if value_num >= 25000:
            return "mid"
        return "low"

    async def get_area_income_context(self, dong_code: str) -> Dict[str, Any]:
        """
        해당 행정동의 소득·고령·인구추세 컨텍스트 집계.

        3개 서브쿼리를 asyncio.gather로 병렬 실행 (각 헬퍼는 독립 세션 사용).
        예외 발생 시 해당 필드만 None/'unknown'으로 fallback.

        Returns:
            {
                "area_income_per_capita": float | None,  # 천원/年/人 (KOSIS 서울시 단위)
                "elderly_ratio":          float | None,  # 0-100 %
                "population_trend":       "growing" | "stable" | "declining" | "unknown",
                "income_level":           "high" | "mid" | "low" | "unknown",
            }
        """
        results = await asyncio.gather(
            self._fetch_area_income(),
            self._fetch_elderly_ratio(),
            self._fetch_population_trend(dong_code),
            return_exceptions=True,
        )

        income_raw, elderly_raw, trend_raw = results

        if isinstance(income_raw, Exception):
            logger.warning("area_income fetch failed: %s", income_raw)
            income = None
        elif income_raw is None:
            income = None
        else:
            income = float(income_raw)

        if isinstance(elderly_raw, Exception):
            logger.warning("elderly_ratio fetch failed: %s", elderly_raw)
            elderly = None
        elif elderly_raw is None:
            elderly = None
        else:
            elderly = float(elderly_raw)

        if isinstance(trend_raw, Exception):
            logger.warning("population_trend fetch failed: %s", trend_raw)
            trend = "unknown"
        else:
            trend = trend_raw or "unknown"

        return {
            "area_income_per_capita": income,
            "elderly_ratio": elderly,
            "population_trend": trend,
            "income_level": self._classify_income_level(income),
        }

    # ============================================================
    # trend_forecaster agent support (업종 검색량 / 지역 모멘텀 /
    # 상권 변화 지표 / 거시 기준금리)
    # ============================================================

    async def get_industry_trend(self, industry: str, months_back: int = 24) -> Dict[str, Any]:
        """naver_trend_industry 업종 검색량 월별 추이.

        Args:
            industry: '커피'/'치킨'/'패스트푸드' 등 naver_trend_industry.industry 값.
                resolve_industry()로 먼저 정규화할 것.
            months_back: 최근 N개월.

        Returns:
            {
                "samples": [{"period": "2026-04-01", "ratio": 40.5}, ...],
                "current_ratio": float | None,
                "yoy_change_pct": float | None,
                "direction": "rising" | "stable" | "declining" | "unknown",
            }
        """
        async with self.db_client.get_session() as session:
            query = text(
                """
                SELECT period, ratio
                FROM naver_trend_industry
                WHERE industry = :industry
                  AND period >= (CURRENT_DATE - make_interval(months => :months))
                ORDER BY period ASC
                """
            )
            result = await session.execute(query, {"industry": industry, "months": months_back})
            rows = result.fetchall()

        if not rows:
            return {
                "samples": [],
                "current_ratio": None,
                "yoy_change_pct": None,
                "direction": "unknown",
            }

        samples = [{"period": str(r[0]), "ratio": float(r[1])} for r in rows]
        current = samples[-1]["ratio"]

        yoy: Optional[float] = None
        if len(samples) >= 13:
            prev = samples[-13]["ratio"]
            if prev > 0:
                yoy = ((current - prev) / prev) * 100

        if yoy is None:
            direction = "unknown"
        elif yoy > 5:
            direction = "rising"
        elif yoy < -5:
            direction = "declining"
        else:
            direction = "stable"

        return {
            "samples": samples,
            "current_ratio": current,
            "yoy_change_pct": yoy,
            "direction": direction,
        }

    async def get_dong_trend_quarterly(self, dong_name: str, quarters_back: int = 8) -> Dict[str, Any]:
        """naver_trend_quarterly 마포 동별 분기 트렌드 스코어.

        ⚠️ 2026-04 기준 최신 분기는 20244 (2024 Q4). 현재 시점과 1.5년 gap.

        Args:
            dong_name: 한글 동 이름 ('서교동'). target_district 값 그대로 사용.
            quarters_back: 최근 N분기.
        """
        async with self.db_client.get_session() as session:
            query = text(
                """
                SELECT quarter, trend_score
                FROM naver_trend_quarterly
                WHERE scope = 'mapo' AND dong_name = :dong_name
                ORDER BY quarter DESC
                LIMIT :limit
                """
            )
            result = await session.execute(query, {"dong_name": dong_name, "limit": quarters_back})
            rows = result.fetchall()

        if not rows:
            return {
                "samples": [],
                "recent_score": None,
                "slope_pct": None,
                "max_quarter": None,
            }

        samples = [{"quarter": int(r[0]), "score": float(r[1])} for r in reversed(rows)]
        recent = samples[-1]["score"]
        max_quarter = samples[-1]["quarter"]

        slope: Optional[float] = None
        if len(samples) >= 2 and samples[0]["score"] > 0:
            slope = ((recent - samples[0]["score"]) / samples[0]["score"]) * 100

        return {
            "samples": samples,
            "recent_score": recent,
            "slope_pct": slope,
            "max_quarter": max_quarter,
        }

    async def get_adstrd_change_ix(self, dong_name: str) -> Dict[str, Any]:
        """seoul_adstrd_change_ix 상권 변화 지표 (동 단위 최신 + 최근 4분기 이력).

        Args:
            dong_name: 한글 동 이름. 테이블에 dong_name 컬럼이 있어 code 변환 불필요.
        """
        async with self.db_client.get_session() as session:
            query = text(
                """
                SELECT quarter, change_ix, change_ix_name,
                       opr_sale_mt_avg, cls_sale_mt_avg,
                       su_opr_sale_mt_avg, su_cls_sale_mt_avg
                FROM seoul_adstrd_change_ix
                WHERE dong_name = :dong_name
                ORDER BY quarter DESC
                LIMIT 4
                """
            )
            result = await session.execute(query, {"dong_name": dong_name})
            rows = result.fetchall()

        if not rows:
            return {"current": None, "history": []}

        latest = rows[0]
        opr = float(latest[3]) if latest[3] is not None else None
        cls = float(latest[4]) if latest[4] is not None else None
        su_opr = float(latest[5]) if latest[5] is not None else None
        su_cls = float(latest[6]) if latest[6] is not None else None

        return {
            "current": {
                "quarter": int(latest[0]),
                "change_ix_class": latest[1],
                "change_ix_label": latest[2],
                "opr_months": opr,
                "cls_months": cls,
                "opr_vs_seoul_ratio": (opr / su_opr) if (opr and su_opr) else None,
                "cls_vs_seoul_ratio": (cls / su_cls) if (cls and su_cls) else None,
            },
            "history": [
                {
                    "quarter": int(r[0]),
                    "change_ix_label": r[2],
                    "opr_months": float(r[3]) if r[3] is not None else None,
                }
                for r in rows
            ],
        }

    async def get_base_rate_trend(self, months_back: int = 12) -> Dict[str, Any]:
        """ecos_timeseries 한국은행 기준금리 월별 추이.

        Step 0 검증으로 item_name1 = '한국은행 기준금리' exact match 확정.
        """
        async with self.db_client.get_session() as session:
            query = text(
                """
                SELECT period, data_value
                FROM ecos_timeseries
                WHERE item_name1 = '한국은행 기준금리'
                ORDER BY period DESC
                LIMIT :limit
                """
            )
            result = await session.execute(query, {"limit": months_back})
            rows = result.fetchall()

        if not rows:
            return {"current": None, "trend": "unknown", "samples": []}

        samples = [{"period": r[0], "rate": float(r[1])} for r in reversed(rows)]
        current = samples[-1]["rate"]
        oldest = samples[0]["rate"]

        if current > oldest + 0.25:
            trend = "rising"
        elif current < oldest - 0.25:
            trend = "declining"
        else:
            trend = "stable"

        return {"current": current, "trend": trend, "samples": samples}
