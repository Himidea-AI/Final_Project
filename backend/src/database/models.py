"""
SQLAlchemy 2.0 ORM 모델 — 마포구 상권분석 데이터베이스 테이블 정의

담당: A1 — 데이터 엔지니어 (찬영)
"""

import uuid

from sqlalchemy import BigInteger, Column, Date, Float, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy DeclarativeBase — 모든 ORM 모델의 기반 클래스"""


# ---------------------------------------------------------------------------
# 인구 관련 테이블
# ---------------------------------------------------------------------------


class LivingPopulation(Base):
    """생활인구 — 행정동 단위 시간대별 유동인구 (서울 열린데이터 광장)"""

    __tablename__ = "living_population"

    # 복합 PK
    date = Column(Date, primary_key=True, comment="기준 날짜")
    time_zone = Column(SmallInteger, primary_key=True, comment="시간대 구분 (0~23)")
    dong_code = Column(String(10), primary_key=True, comment="행정동 코드")

    dong_name = Column(String(20), comment="행정동명")
    total_pop = Column(Float, comment="전체 생활인구")

    # 남성 연령대 (5세 단위, 15개 구간)
    male_0_9 = Column(Float, comment="남성 0~9세")
    male_10_14 = Column(Float, comment="남성 10~14세")
    male_15_19 = Column(Float, comment="남성 15~19세")
    male_20_24 = Column(Float, comment="남성 20~24세")
    male_25_29 = Column(Float, comment="남성 25~29세")
    male_30_34 = Column(Float, comment="남성 30~34세")
    male_35_39 = Column(Float, comment="남성 35~39세")
    male_40_44 = Column(Float, comment="남성 40~44세")
    male_45_49 = Column(Float, comment="남성 45~49세")
    male_50_54 = Column(Float, comment="남성 50~54세")
    male_55_59 = Column(Float, comment="남성 55~59세")
    male_60_64 = Column(Float, comment="남성 60~64세")
    male_65_69 = Column(Float, comment="남성 65~69세")
    male_70_74 = Column(Float, comment="남성 70~74세")
    male_70_plus = Column(Float, comment="남성 70세 이상")

    # 여성 연령대 (5세 단위, 15개 구간)
    female_0_9 = Column(Float, comment="여성 0~9세")
    female_10_14 = Column(Float, comment="여성 10~14세")
    female_15_19 = Column(Float, comment="여성 15~19세")
    female_20_24 = Column(Float, comment="여성 20~24세")
    female_25_29 = Column(Float, comment="여성 25~29세")
    female_30_34 = Column(Float, comment="여성 30~34세")
    female_35_39 = Column(Float, comment="여성 35~39세")
    female_40_44 = Column(Float, comment="여성 40~44세")
    female_45_49 = Column(Float, comment="여성 45~49세")
    female_50_54 = Column(Float, comment="여성 50~54세")
    female_55_59 = Column(Float, comment="여성 55~59세")
    female_60_64 = Column(Float, comment="여성 60~64세")
    female_65_69 = Column(Float, comment="여성 65~69세")
    female_70_74 = Column(Float, comment="여성 70~74세")
    female_70_plus = Column(Float, comment="여성 70세 이상")


class SgisPopulation(Base):
    """SGIS 인구 통계 — 통계지리정보서비스 인구 지표"""

    __tablename__ = "sgis_population"

    year = Column(SmallInteger, primary_key=True, comment="기준 연도")
    area_code = Column(String(14), primary_key=True, comment="행정구역 코드")
    indicator = Column(String(30), primary_key=True, comment="지표명")

    value = Column(Float, comment="지표 값")


class SgisHousehold(Base):
    """SGIS 가구 통계 — 통계지리정보서비스 가구 지표"""

    __tablename__ = "sgis_household"

    year = Column(SmallInteger, primary_key=True, comment="기준 연도")
    area_code = Column(String(14), primary_key=True, comment="행정구역 코드")
    indicator = Column(String(30), primary_key=True, comment="지표명")

    value = Column(Float, comment="지표 값")


class SgisBusiness(Base):
    """SGIS 사업체 통계 — 통계지리정보서비스 사업체 지표"""

    __tablename__ = "sgis_business"

    year = Column(SmallInteger, primary_key=True, comment="기준 연도")
    area_code = Column(String(14), primary_key=True, comment="행정구역 코드")
    indicator = Column(String(30), primary_key=True, comment="지표명")

    value = Column(Float, comment="지표 값")


# ---------------------------------------------------------------------------
# 상권 관련 테이블
# ---------------------------------------------------------------------------


class GolmokCommercial(Base):
    """골목상권 상업 데이터 — 서울시 우리마을가게 상권분석 서비스"""

    __tablename__ = "golmok_commercial"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    quarter = Column(Integer, index=True, comment="기준 분기 (YYYYQ)")
    trdar_code = Column(String(10), comment="상권 코드")
    data_type = Column(String(20), index=True, comment="데이터 유형 (sales/store/population 등)")
    industry_code = Column(String(20), default="ALL", comment="업종 코드 (기본값: ALL)")
    metrics = Column(JSONB, comment="지표 데이터 (JSON)")


class DistrictSales(Base):
    """행정동별 매출 통계 — 분기별 업종별 매출 및 건수"""

    __tablename__ = "district_sales"

    # 복합 PK
    quarter = Column(Integer, primary_key=True, comment="기준 분기 (YYYYQ)")
    dong_code = Column(String(10), primary_key=True, index=True, comment="행정동 코드")
    industry_code = Column(String(20), primary_key=True, comment="업종 코드")

    dong_name = Column(String(20), comment="행정동명")
    industry_name = Column(String(50), comment="업종명")

    # 매출 금액 (월별/요일별/시간대별/성별/연령대별)
    monthly_sales = Column(BigInteger, comment="월 매출 금액")
    monthly_count = Column(Integer, comment="월 매출 건수")

    weekday_sales = Column(BigInteger, comment="평일 매출 금액")
    weekend_sales = Column(BigInteger, comment="주말 매출 금액")

    mon_sales = Column(BigInteger, comment="월요일 매출 금액")
    tue_sales = Column(BigInteger, comment="화요일 매출 금액")
    wed_sales = Column(BigInteger, comment="수요일 매출 금액")
    thu_sales = Column(BigInteger, comment="목요일 매출 금액")
    fri_sales = Column(BigInteger, comment="금요일 매출 금액")
    sat_sales = Column(BigInteger, comment="토요일 매출 금액")
    sun_sales = Column(BigInteger, comment="일요일 매출 금액")

    time_00_06_sales = Column(BigInteger, comment="00~06시 매출 금액")
    time_06_11_sales = Column(BigInteger, comment="06~11시 매출 금액")
    time_11_14_sales = Column(BigInteger, comment="11~14시 매출 금액")
    time_14_17_sales = Column(BigInteger, comment="14~17시 매출 금액")
    time_17_21_sales = Column(BigInteger, comment="17~21시 매출 금액")
    time_21_24_sales = Column(BigInteger, comment="21~24시 매출 금액")

    male_sales = Column(BigInteger, comment="남성 매출 금액")
    female_sales = Column(BigInteger, comment="여성 매출 금액")

    age_10_sales = Column(BigInteger, comment="10대 매출 금액")
    age_20_sales = Column(BigInteger, comment="20대 매출 금액")
    age_30_sales = Column(BigInteger, comment="30대 매출 금액")
    age_40_sales = Column(BigInteger, comment="40대 매출 금액")
    age_50_sales = Column(BigInteger, comment="50대 매출 금액")
    age_60_above_sales = Column(BigInteger, comment="60대 이상 매출 금액")

    # 매출 건수 (요일별/시간대별/성별/연령대별)
    weekday_count = Column(Integer, comment="평일 매출 건수")
    weekend_count = Column(Integer, comment="주말 매출 건수")

    mon_count = Column(Integer, comment="월요일 매출 건수")
    tue_count = Column(Integer, comment="화요일 매출 건수")
    wed_count = Column(Integer, comment="수요일 매출 건수")
    thu_count = Column(Integer, comment="목요일 매출 건수")
    fri_count = Column(Integer, comment="금요일 매출 건수")
    sat_count = Column(Integer, comment="토요일 매출 건수")
    sun_count = Column(Integer, comment="일요일 매출 건수")

    time_00_06_count = Column(Integer, comment="00~06시 매출 건수")
    time_06_11_count = Column(Integer, comment="06~11시 매출 건수")
    time_11_14_count = Column(Integer, comment="11~14시 매출 건수")
    time_14_17_count = Column(Integer, comment="14~17시 매출 건수")
    time_17_21_count = Column(Integer, comment="17~21시 매출 건수")
    time_21_24_count = Column(Integer, comment="21~24시 매출 건수")

    male_count = Column(Integer, comment="남성 매출 건수")
    female_count = Column(Integer, comment="여성 매출 건수")

    age_10_count = Column(Integer, comment="10대 매출 건수")
    age_20_count = Column(Integer, comment="20대 매출 건수")
    age_30_count = Column(Integer, comment="30대 매출 건수")
    age_40_count = Column(Integer, comment="40대 매출 건수")
    age_50_count = Column(Integer, comment="50대 매출 건수")
    age_60_above_count = Column(Integer, comment="60대 이상 매출 건수")


# ---------------------------------------------------------------------------
# 점포 관련 테이블
# ---------------------------------------------------------------------------


class StoreInfo(Base):
    """점포 기본 정보 — 업종, 위치, 주소 등"""

    __tablename__ = "store_info"

    store_id = Column(String(20), primary_key=True, comment="점포 고유 ID")
    store_name = Column(String(100), comment="점포명")
    dong_code = Column(String(10), index=True, comment="행정동 코드")
    dong_name = Column(String(20), index=True, comment="행정동명")
    address = Column(Text, comment="지번 주소")
    road_address = Column(Text, comment="도로명 주소")
    lat = Column(Float, comment="위도")
    lon = Column(Float, comment="경도")

    industry_l_code = Column(String(20), comment="대분류 업종 코드")
    industry_l = Column(String(50), comment="대분류 업종명")
    industry_m_code = Column(String(20), index=True, comment="중분류 업종 코드")
    industry_m = Column(String(50), index=True, comment="중분류 업종명")
    industry_s_code = Column(String(20), comment="소분류 업종 코드")
    industry_s = Column(String(50), comment="소분류 업종명")

    building_name = Column(String(100), comment="건물명")
    floor_info = Column(String(20), comment="층 정보")


class StoreQuarterly(Base):
    """점포 분기별 통계 — 개폐업 현황 및 프랜차이즈 수"""

    __tablename__ = "store_quarterly"

    # 복합 PK
    quarter = Column(Integer, primary_key=True, comment="기준 분기 (YYYYQ)")
    dong_code = Column(String(10), primary_key=True, index=True, comment="행정동 코드")
    industry_code = Column(String(20), primary_key=True, comment="업종 코드")

    dong_name = Column(String(20), comment="행정동명")
    industry_name = Column(String(50), comment="업종명")

    store_count = Column(Integer, comment="점포 수")
    open_count = Column(Integer, comment="개업 점포 수")
    close_count = Column(Integer, comment="폐업 점포 수")
    closure_rate = Column(Float, comment="폐업률")
    franchise_count = Column(Integer, comment="프랜차이즈 점포 수")


# ---------------------------------------------------------------------------
# 임대료 관련 테이블
# ---------------------------------------------------------------------------


class RentCost(Base):
    """임대료 데이터 — 상업용 부동산 임대료 및 공실률"""

    __tablename__ = "rent_cost"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    data_type = Column(String(20), index=True, comment="데이터 유형 (rent/transaction)")
    area_name = Column(String(50), comment="지역명")
    year = Column(SmallInteger, comment="기준 연도")
    quarter = Column(SmallInteger, comment="기준 분기")
    rent = Column(Float, comment="임대료 (만원/m²)")
    vacancy_rate = Column(Float, comment="공실률")
    investment_return = Column(Float, comment="투자 수익률")
    income_return = Column(Float, comment="소득 수익률")
    capital_return = Column(Float, comment="자본 수익률")
    transaction_date = Column(String(10), comment="거래 일자 (YYYY-MM-DD)")
    price = Column(BigInteger, comment="거래 금액 (만원)")
    floor_area = Column(Float, comment="전용 면적 (m²)")
    floor = Column(String(10), comment="층 정보")
    source = Column(String(20), comment="데이터 출처")


# ---------------------------------------------------------------------------
# 참조 / 매핑 테이블
# ---------------------------------------------------------------------------


class DongMapping(Base):
    """행정동 매핑 테이블 — 동코드 ↔ 동명, 인구, 상권 코드 매핑"""

    __tablename__ = "dong_mapping"

    dong_code = Column(String(10), primary_key=True, comment="행정동 코드")
    dong_name = Column(String(20), comment="행정동명")
    resident_pop = Column(Integer, comment="주민등록 인구")
    floating_pop = Column(Float, comment="유동인구")
    avg_age = Column(Float, comment="평균 연령")
    total_households = Column(Integer, comment="총 가구 수")
    trdar_codes = Column(JSONB, comment="상권 코드 목록 (JSON 배열)")


# ---------------------------------------------------------------------------
# 시뮬레이션 결과 테이블
# ---------------------------------------------------------------------------


class SimulationResult(Base):
    """시뮬레이션 결과 — 프랜차이즈 출점 분석 요청 및 결과 저장"""

    __tablename__ = "simulation_result"

    request_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="요청 고유 ID (UUID v4)",
    )
    created_at = Column(
        Date,
        server_default=func.now(),
        comment="요청 생성 일시",
    )
    input_params = Column(JSONB, comment="시뮬레이션 입력 파라미터 (JSON)")
    output_result = Column(JSONB, comment="시뮬레이션 분석 결과 (JSON)")
    status = Column(String(20), default="pending", comment="처리 상태 (pending/running/done/error)")
