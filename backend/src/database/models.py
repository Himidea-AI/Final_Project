"""
SQLAlchemy 2.0 ORM 모델 — 마포구 상권분석 데이터베이스 테이블 정의

담당: A1 — 데이터 엔지니어 (찬영)
"""

import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
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
    industry_code = Column(
        String(20),
        ForeignKey("industry_master.industry_code", onupdate="CASCADE"),
        default="ALL",
        comment="업종 코드 (기본값: ALL)",
    )
    metrics = Column(JSONB, comment="지표 데이터 (JSON)")


class DistrictSales(Base):
    """행정동별 매출 통계 — 분기별 업종별 매출 및 건수"""

    __tablename__ = "district_sales"

    # 복합 PK
    quarter = Column(Integer, primary_key=True, comment="기준 분기 (YYYYQ)")
    dong_code = Column(String(10), primary_key=True, index=True, comment="행정동 코드")
    industry_code = Column(
        String(20),
        ForeignKey("industry_master.industry_code", onupdate="CASCADE"),
        primary_key=True,
        comment="업종 코드",
    )

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
    industry_code = Column(
        String(20),
        ForeignKey("industry_master.industry_code", onupdate="CASCADE"),
        primary_key=True,
        comment="업종 코드",
    )

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
    data_type = Column(String(20), index=True, comment="데이터 유형 (building_rent/rent_small_store)")
    area_name = Column(String(50), comment="지역명")
    year = Column(SmallInteger, comment="기준 연도")
    quarter = Column(SmallInteger, comment="기준 분기")
    rent = Column(Float, comment="임대료 (만원/m²)")
    vacancy_rate = Column(Float, comment="공실률")
    investment_return = Column(Float, comment="투자 수익률")
    income_return = Column(Float, comment="소득 수익률")
    capital_return = Column(Float, comment="자본 수익률")
    source = Column(String(20), comment="데이터 출처")


class GolmokRent(Base):
    """행정동별 환산임대료 — 서울 상권분석서비스(신용보증재단 기반)"""

    __tablename__ = "golmok_rent"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    year = Column(SmallInteger, index=True, comment="기준 연도")
    quarter = Column(SmallInteger, comment="기준 분기")
    dong_code = Column(String(10), index=True, comment="행정동코드")
    dong_name = Column(String(20), comment="행정동명")
    gubun = Column(String(10), comment="구분 (gu/dong)")
    rent_1f = Column(Integer, comment="1층 환산임대료 (원/3.3㎡)")
    rent_other = Column(Integer, comment="1층 외 환산임대료 (원/3.3㎡)")
    rent_total = Column(Integer, comment="전체 환산임대료 (원/3.3㎡)")


# ---------------------------------------------------------------------------
# 참조 / 매핑 테이블
# ---------------------------------------------------------------------------


class DongMapping(Base):
    """행정동 매핑 테이블 — 동코드 ↔ 동명, 인구, 상권 코드 매핑 (마포 16동 운영 마스터)

    ⚠️ FK 가이드 (dong_code 이중 master 혼선 주의):
    - **마포 한정** 데이터(16 row): district_sales/store_quarterly/store_info/
      living_population/living_population_grid/mapo_resident_pop/golmok_rent/
      seoul_adstrd_fclty 가 이 테이블 참조.
    - **서울 전역** 데이터(431 row): seoul_dong_master 참조 (아래 클래스).
    - 같은 `dong_code` 컬럼이 테이블마다 다른 master 가리킴 — 새 ETL 추가 시
      범위(마포/서울)에 맞춰 FK 대상 결정.
    """

    __tablename__ = "dong_mapping"

    dong_code = Column(String(10), primary_key=True, comment="행정동 코드")
    dong_name = Column(String(20), comment="행정동명")
    resident_pop = Column(Integer, comment="주민등록 인구")
    floating_pop = Column(Float, comment="유동인구")
    avg_age = Column(Float, comment="평균 연령")
    total_households = Column(Integer, comment="총 가구 수")
    trdar_codes = Column(JSONB, comment="상권 코드 목록 (JSON 배열)")


class IndustryMaster(Base):
    """업종 마스터 — 업종 코드 ↔ 업종명 매핑 (101 row).

    Alembic 마이그레이션 정의 없음 (직접 DDL 또는 외부 시드 스크립트로 생성).
    DB 측 FK constraint **미존재** (alembic versions 검색 0건 — 2026-05-05 검증).

    자식 industry_code 컬럼 type:
      - String(20): district_sales, store_quarterly, district_sales_seoul,
        seoul_adstrd_stor, seoul_signgu_selng, seoul_signgu_stor, golmok_commercial
      - Text: golmok_sales, golmok_stores, seoul_district_sales,
        seoul_district_stores, seoul_training_dataset
      → PostgreSQL string family 호환 (Text/VARCHAR 모두 String(20) PK 참조 가능)

    ORM ForeignKey 동기화 (2026-05-05): 자식 13개에 ForeignKey 추가하여 양방향
    lazy load + relationship() navigation 가능. DB 레벨 enforcement 부재 →
    별도 alembic 마이그레이션으로 NOT VALID + VALIDATE 추가 권장.
    """

    __tablename__ = "industry_master"

    industry_code = Column(String(20), primary_key=True, comment="업종 코드 (CS100001~CS100010, ALL 등)")
    industry_name = Column(String(100), nullable=False, comment="업종명 (한글명, 예: 한식음식점)")
    industry_name_alt = Column(String(100), comment="업종명 대체 표기 (별칭/영문명)")
    created_at = Column(DateTime, server_default=func.now(), comment="생성 일시")


class SeoulDongMaster(Base):
    """서울 행정동 마스터 — 서울 전체 ~425개 행정동 (8자리 코드, ML/분석용)

    alembic d1a2b3c4e5f6 (B-3.1)에서 신설. 마이그레이션이 자식 테이블 union으로 적재.
    11개 자식 테이블(seoul_*, district_sales_seoul, dong_subway_access 등)이 FK 참조.

    ⚠️ DongMapping (마포 16동) 과 dong_code 동일 컬럼 — 자식 테이블별 FK 대상 다름.
    DongMapping 클래스 docstring 참고.
    """

    __tablename__ = "seoul_dong_master"

    dong_code = Column(String(8), primary_key=True, comment="행정동 코드 (8자리)")
    dong_name = Column(Text, comment="행정동명 (정규화: '?' → '·')")
    sgg_code = Column(String(5), index=True, comment="자치구 코드 (5자리)")
    comment = Column(Text, comment="비고")
    created_at = Column(DateTime, server_default=func.now(), comment="생성 일시")


class JeonseDongMaster(Base):
    """법정동 마스터 — 국토부 전월세 신고 기준 (10자리 코드)

    alembic f3c4d5e6a7b8 (B-3.3)에서 신설. jeonse_monthly_rent.dong_code FK 참조.
    행정동(8자리)과 별개 체계 — 5번째 자리부터 다름.
    """

    __tablename__ = "jeonse_dong_master"

    dong_code = Column(String(10), primary_key=True, comment="법정동 코드 (10자리)")
    dong_name = Column(Text, comment="법정동명")
    gu_code = Column(String(5), comment="구 코드")
    gu_name = Column(Text, comment="구명")
    created_at = Column(DateTime, server_default=func.now(), comment="생성 일시")


class DongCentroid(Base):
    """동 대표 중심점 좌표 — store_info 평균 또는 카카오 좌표 (캐시용)

    alembic a8b2c4d6e8f0에서 신설. commercial_intelligence.get_dong_centroid의
    영구 storage. 추후 Kakao Geocoding API로 갱신 가능.
    현재 마포 16동만 적재 (서울 전체 425동 확장 가능).
    """

    __tablename__ = "dong_centroid"

    dong_code = Column(String(8), primary_key=True, comment="행정동 코드")
    dong_name = Column(Text, comment="행정동명")
    lat = Column(Float, nullable=False, comment="위도")
    lon = Column(Float, nullable=False, comment="경도")
    source = Column(String(32), nullable=False, default="store_info_avg", comment="데이터 출처")
    n_stores = Column(Integer, comment="평균 계산에 사용된 매장 수")
    created_at = Column(DateTime, server_default=func.now(), comment="생성 일시")
    updated_at = Column(DateTime, server_default=func.now(), comment="수정 일시")


# ---------------------------------------------------------------------------
# 회원 관련 테이블
# ---------------------------------------------------------------------------


class User(Base):
    """회원 정보 — 프랜차이즈 본부 담당자 회원가입 데이터"""

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="회원 고유 ID (UUID v4)",
    )
    company_name = Column(String(100), nullable=False, comment="기업명 (프랜차이즈 본부명)")
    biz_number = Column(String(12), unique=True, nullable=False, comment="사업자등록번호 (000-00-00000)")
    contact_name = Column(String(50), nullable=False, comment="담당자명")
    position = Column(String(50), comment="직책")
    email = Column(String(100), unique=True, nullable=False, index=True, comment="업무용 이메일")
    phone = Column(String(20), nullable=False, comment="연락처 (010-0000-0000)")
    store_count = Column(Integer, comment="현재 가맹점 수")
    password_hash = Column(String(255), nullable=False, comment="비밀번호 해시")
    plan = Column(String(20), nullable=False, default="starter", comment="요금제 (starter/growth)")
    agree_terms = Column(Boolean, nullable=False, default=False, comment="이용약관 동의 여부")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="가입 일시",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="레코드 최종 수정 시각",
    )
    last_login_at = Column(
        DateTime(timezone=True),
        comment="마지막 로그인 시각 (auth.login 에서 갱신)",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        default=True,
        comment="계정 활성 여부 (소프트 삭제: false=탈퇴)",
    )
    email_verified = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
        comment="이메일 인증 완료 여부",
    )


class FtcBrandFranchise(Base):
    """공정거래위원회 프랜차이즈 브랜드 정보 — 회원가입 시 브랜드 자동 매핑용"""

    __tablename__ = "ftc_brand_franchise"
    __table_args__ = (UniqueConstraint("yr", "corpNm", "brandNm", name="uq_ftc_yr_corp_brand"),)

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    yr = Column(SmallInteger, index=True, comment="기준 연도")
    corpNm = Column(String(200), comment="법인명 (기업명)")
    brandNm = Column(String(200), index=True, comment="브랜드명")
    indutyLclasNm = Column(String(50), comment="업종 대분류명")
    indutyMlsfcNm = Column(String(50), comment="업종 중분류명")
    frcsCnt = Column(Integer, comment="가맹점 수")
    newFrcsRgsCnt = Column(Integer, comment="신규 가맹점 등록 수")
    ctrtEndCnt = Column(Integer, comment="계약 종료 수")
    ctrtCncltnCnt = Column(Integer, comment="계약 해지 수")
    nmChgCnt = Column(Integer, comment="명칭 변경 수")
    avrgSlsAmt = Column(BigInteger, comment="평균 매출액 (천원)")
    arUnitAvrgSlsAmt = Column(BigInteger, comment="면적당 평균 매출액")


class BizBrandMapping(Base):
    """사업자등록번호 ↔ 브랜드 매핑 — 회원가입 시 자동 축적"""

    __tablename__ = "biz_brand_mapping"

    biz_number = Column(String(12), primary_key=True, comment="사업자등록번호 (하이픈 제거)")
    company_name = Column(String(100), nullable=False, comment="기업명 (법인명)")
    brand_name = Column(String(100), comment="매핑된 브랜드명")
    industry_large = Column(String(50), comment="업종 대분류")
    industry_medium = Column(String(50), comment="업종 중분류")
    franchise_count = Column(Integer, comment="전국 가맹점 수")
    avg_sales = Column(BigInteger, comment="평균매출 (천원)")
    mapo_store_count = Column(Integer, comment="마포구 점포 수")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="등록 일시",
    )


class MartBrandTerritory(Base):
    """브랜드 영업지역 데이터 마트 — FTC 정보공개서·가맹계약서 추출 결과 (11,849 row).

    영업지역(territory) 텍스트와 표준 거리(m) 를 brand+corp+yr 단위로 적재.
    extraction_method/confidence 로 추출 품질 추적.
    consumer 미배선 (raw SQL 사용 0건) — 향후 territory 침해 분석 로직 배선 예정.
    Alembic 정의 없음 (외부 ETL 스크립트로 생성).
    """

    __tablename__ = "mart_brand_territory"
    __table_args__ = (UniqueConstraint("brand_name", "corp_name", "yr", name="uq_mart_brand_territory_brand_corp_yr"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="자동증가 PK")
    brand_name = Column(Text, nullable=False, index=True, comment="브랜드명")
    corp_name = Column(Text, comment="법인명")
    yr = Column(Integer, nullable=False, comment="기준 연도")
    territory_text = Column(Text, comment="영업지역 텍스트 설명 (가맹계약서 발췌)")
    territory_distance_m = Column(Float, index=True, comment="영업지역 표준 반경 (m)")
    extraction_method = Column(Text, comment="추출 방법 (not_in_ftc_list / ftc_text / contract_pdf 등)")
    extraction_confidence = Column(Float, comment="추출 신뢰도 (0~1)")
    extracted_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="추출 일시",
    )


class NaverVacancy(Base):
    """네이버 부동산 상가 공실 데이터 — 마포구 상가 임대/매매 매물"""

    __tablename__ = "naver_vacancy"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    trade_type = Column(String(10), comment="거래유형 (매매/전세/월세)")
    trade_code = Column(String(5), comment="거래코드 (B1/B2/B3)")
    lat = Column(Float, comment="위도")
    lon = Column(Float, comment="경도")
    listing_count = Column(Integer, comment="매물 건수")
    dong_name = Column(String(20), index=True, comment="행정동명")
    lgeo = Column(String(30), comment="네이버 지오코드")
    collected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="수집 일시",
    )


class KakaoStore(Base):
    """카카오 로컬 API 기반 실시간 점포 데이터 — 마포구 전수 (프랜차이즈 + 개인)"""

    __tablename__ = "kakao_store"

    kakao_id = Column(String(20), primary_key=True, comment="카카오 장소 ID")
    place_name = Column(String(200), comment="장소명 (점포명)")
    brand_name = Column(
        String(100),
        index=True,
        nullable=True,
        comment="정규화된 브랜드명 (프랜차이즈만, 개인 점포는 NULL)",
    )
    category = Column(String(30), index=True, comment="10대 업종 카테고리 + '기타'")
    category_detail = Column(String(200), comment="카카오 카테고리 상세 (category_name)")
    address = Column(Text, comment="지번 주소")
    road_address = Column(Text, comment="도로명 주소")
    dong_name = Column(String(20), index=True, comment="행정동명")
    lat = Column(Float, comment="위도")
    lon = Column(Float, comment="경도")
    phone = Column(String(20), comment="전화번호")
    place_url = Column(Text, comment="카카오맵 URL")
    is_franchise = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="프랜차이즈 여부 (NORMALIZE_RULES 매칭 결과)",
    )
    collected_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="수집 일시",
    )


class InviteCode(Base):
    """초대코드 — 팀장(users)이 발급, 매니저 가입 시 사용"""

    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    code = Column(String(20), unique=True, nullable=False, index=True, comment="초대코드 (8자리)")
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="발급한 팀장 ID",
    )
    max_uses = Column(Integer, nullable=False, default=10, comment="최대 사용 가능 횟수")
    used_count = Column(Integer, nullable=False, default=0, comment="현재 사용된 횟수")
    is_active = Column(Boolean, nullable=False, default=True, comment="활성 여부")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="발급 일시",
    )
    expires_at = Column(DateTime(timezone=True), comment="만료 일시 (NULL이면 무제한)")


class ManagerUser(Base):
    """매니저 회원 — 팀장의 초대코드로 가입, 기업정보는 팀장에서 상속"""

    __tablename__ = "manager_users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="매니저 고유 ID (UUID v4)",
    )
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="소속 팀장 ID",
    )
    invite_code_id = Column(
        Integer,
        ForeignKey("invite_codes.id"),
        comment="사용한 초대코드 ID",
    )
    contact_name = Column(String(50), nullable=False, comment="매니저 이름")
    position = Column(String(50), comment="직책")
    email = Column(String(100), unique=True, nullable=False, index=True, comment="이메일")
    phone = Column(String(20), nullable=False, comment="연락처")
    password_hash = Column(String(255), nullable=False, comment="비밀번호 해시")
    is_active = Column(Boolean, nullable=False, default=True, comment="활성 여부")
    is_approved = Column(Boolean, nullable=False, default=False, comment="팀장 승인 여부")
    email_verified = Column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        default=False,
        comment="이메일 인증 완료 여부",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="가입 일시",
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="레코드 최종 수정 시각",
    )
    last_login_at = Column(
        DateTime(timezone=True),
        comment="마지막 로그인 시각 (auth.manager_login 에서 갱신)",
    )


# ---------------------------------------------------------------------------
# 외부 수집 / 보조 테이블 (CSV 시드 전용, ORM 사용 최소)
# ---------------------------------------------------------------------------


class CpiDiningQuarterly(Base):
    """분기별 외식 소비자물가지수 (통계청)"""

    __tablename__ = "cpi_dining_quarterly"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    quarter = Column(BigInteger, comment="분기 (YYYYQ)")
    cpi_index = Column(Float, comment="CPI 지수")


class GolmokSales(Base):
    """골목상권(trdar) 분기 매출 — 서울 상권분석서비스"""

    __tablename__ = "golmok_sales"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    quarter = Column(BigInteger, index=True, comment="분기 (YYYYQ)")
    trdar_code = Column(Text, index=True, comment="상권 코드")
    industry_code = Column(
        Text,
        ForeignKey("industry_master.industry_code", onupdate="CASCADE"),
        comment="업종 코드",
    )
    monthly_sales = Column(BigInteger, comment="월평균 매출")
    monthly_count = Column(BigInteger, comment="월평균 건수")
    weekday_sales = Column(BigInteger)
    weekend_sales = Column(BigInteger)
    mon_sales = Column(BigInteger)
    tue_sales = Column(BigInteger)
    wed_sales = Column(BigInteger)
    thu_sales = Column(BigInteger)
    fri_sales = Column(BigInteger)
    sat_sales = Column(BigInteger)
    sun_sales = Column(BigInteger)
    time_00_06_sales = Column(BigInteger)
    time_06_11_sales = Column(BigInteger)
    time_11_14_sales = Column(BigInteger)
    time_14_17_sales = Column(BigInteger)
    time_17_21_sales = Column(BigInteger)
    time_21_24_sales = Column(BigInteger)
    male_sales = Column(BigInteger)
    female_sales = Column(BigInteger)
    age_10_sales = Column(BigInteger)
    age_20_sales = Column(BigInteger)
    age_30_sales = Column(BigInteger)
    age_40_sales = Column(BigInteger)
    age_50_sales = Column(BigInteger)
    age_60_above_sales = Column(BigInteger)
    weekday_count = Column(BigInteger)
    weekend_count = Column(BigInteger)
    mon_count = Column(BigInteger)
    tue_count = Column(BigInteger)
    wed_count = Column(BigInteger)
    thu_count = Column(BigInteger)
    fri_count = Column(BigInteger)
    sat_count = Column(BigInteger)
    sun_count = Column(BigInteger)
    time_00_06_count = Column(BigInteger)
    time_06_11_count = Column(BigInteger)
    time_11_14_count = Column(BigInteger)
    time_14_17_count = Column(BigInteger)
    time_17_21_count = Column(BigInteger)
    time_21_24_count = Column(BigInteger)
    male_count = Column(BigInteger)
    female_count = Column(BigInteger)
    age_10_count = Column(BigInteger)
    age_20_count = Column(BigInteger)
    age_30_count = Column(BigInteger)
    age_40_count = Column(BigInteger)
    age_50_count = Column(BigInteger)
    age_60_above_count = Column(BigInteger)


class GolmokStores(Base):
    """골목상권 분기 점포 통계"""

    __tablename__ = "golmok_stores"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    quarter = Column(BigInteger, index=True, comment="분기 (YYYYQ)")
    trdar_code = Column(Text, index=True, comment="상권 코드")
    industry_code = Column(
        Text,
        ForeignKey("industry_master.industry_code", onupdate="CASCADE"),
        comment="업종 코드",
    )
    store_count = Column(BigInteger, comment="점포 수")
    similar_store_count = Column(BigInteger, comment="유사 점포 수")
    open_rate = Column(BigInteger, comment="개업률")
    open_count = Column(BigInteger, comment="개업 수")
    close_rate = Column(BigInteger, comment="폐업률")
    close_count = Column(BigInteger, comment="폐업 수")
    franchise_count = Column(BigInteger, comment="프랜차이즈 수")


class MapoResidentPop(Base):
    """마포구 행정동별 분기 주민등록인구"""

    __tablename__ = "mapo_resident_pop"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    quarter = Column(BigInteger, index=True, comment="분기 (YYYYQ)")
    dong_code = Column(Text, index=True, comment="행정동 코드")
    dong_name = Column(Text, comment="행정동명")
    resident_pop = Column(Float, comment="주민등록 인구")


class SeoulDistrictSales(Base):
    """서울 전체 행정동 분기 매출 — 사전학습용

    alembic e2b3c4d5f6a7 에서 seoul_dong_master FK 추가 완료 (NOT VALID + VALIDATE).
    """

    __tablename__ = "seoul_district_sales"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    quarter = Column(BigInteger, index=True)
    dong_code = Column(
        Text,
        ForeignKey("seoul_dong_master.dong_code", onupdate="CASCADE"),
        index=True,
    )
    dong_name = Column(Text)
    industry_code = Column(
        Text,
        ForeignKey("industry_master.industry_code", onupdate="CASCADE"),
    )
    industry_name = Column(Text)
    monthly_sales = Column(BigInteger)
    monthly_count = Column(BigInteger)
    weekday_sales = Column(BigInteger)
    weekend_sales = Column(BigInteger)
    mon_sales = Column(BigInteger)
    tue_sales = Column(BigInteger)
    wed_sales = Column(BigInteger)
    thu_sales = Column(BigInteger)
    fri_sales = Column(BigInteger)
    sat_sales = Column(BigInteger)
    sun_sales = Column(BigInteger)
    time_00_06_sales = Column(BigInteger)
    time_06_11_sales = Column(BigInteger)
    time_11_14_sales = Column(BigInteger)
    time_14_17_sales = Column(BigInteger)
    time_17_21_sales = Column(BigInteger)
    time_21_24_sales = Column(BigInteger)
    male_sales = Column(BigInteger)
    female_sales = Column(BigInteger)
    age_10_sales = Column(BigInteger)
    age_20_sales = Column(BigInteger)
    age_30_sales = Column(BigInteger)
    age_40_sales = Column(BigInteger)
    age_50_sales = Column(BigInteger)
    age_60_above_sales = Column(BigInteger)
    weekday_count = Column(BigInteger)
    weekend_count = Column(BigInteger)
    mon_count = Column(BigInteger)
    tue_count = Column(BigInteger)
    wed_count = Column(BigInteger)
    thu_count = Column(BigInteger)
    fri_count = Column(BigInteger)
    sat_count = Column(BigInteger)
    sun_count = Column(BigInteger)
    time_00_06_count = Column(BigInteger)
    time_06_11_count = Column(BigInteger)
    time_11_14_count = Column(BigInteger)
    time_14_17_count = Column(BigInteger)
    time_17_21_count = Column(BigInteger)
    time_21_24_count = Column(BigInteger)
    male_count = Column(BigInteger)
    female_count = Column(BigInteger)
    age_10_count = Column(BigInteger)
    age_20_count = Column(BigInteger)
    age_30_count = Column(BigInteger)
    age_40_count = Column(BigInteger)
    age_50_count = Column(BigInteger)
    age_60_above_count = Column(BigInteger)


class SeoulDistrictStores(Base):
    """서울 전체 행정동 분기 점포 — 사전학습용

    alembic e2b3c4d5f6a7 에서 seoul_dong_master FK 추가 완료.
    """

    __tablename__ = "seoul_district_stores"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    quarter = Column(BigInteger, index=True)
    dong_code = Column(
        Text,
        ForeignKey("seoul_dong_master.dong_code", onupdate="CASCADE"),
        index=True,
    )
    dong_name = Column(Text)
    industry_code = Column(
        Text,
        ForeignKey("industry_master.industry_code", onupdate="CASCADE"),
    )
    industry_name = Column(Text)
    store_count = Column(BigInteger)
    similar_store_count = Column(BigInteger)
    open_count = Column(BigInteger)
    close_count = Column(BigInteger)
    franchise_count = Column(BigInteger)
    closure_rate = Column(BigInteger)


class SeoulGolmokRent(Base):
    """서울 전체 골목상권 환산임대료 — 사전학습용

    alembic e2b3c4d5f6a7 에서 seoul_dong_master FK 추가 완료.
    """

    __tablename__ = "seoul_golmok_rent"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    year = Column(BigInteger, index=True)
    quarter = Column(BigInteger)
    dong_code = Column(
        Text,
        ForeignKey("seoul_dong_master.dong_code", onupdate="CASCADE"),
        index=True,
    )
    dong_name = Column(Text)
    gubun = Column(Text)
    rent_1f = Column(Float)
    rent_other = Column(Float)
    rent_total = Column(Float)
    quarter_code = Column(BigInteger)


class SeoulPopulationQuarterly(Base):
    """서울 행정동별 분기 인구

    alembic e2b3c4d5f6a7 에서 seoul_dong_master FK 추가 완료.
    """

    __tablename__ = "seoul_population_quarterly"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    quarter = Column(BigInteger, index=True)
    dong_code = Column(
        Text,
        ForeignKey("seoul_dong_master.dong_code", onupdate="CASCADE"),
        index=True,
    )
    total_pop = Column(Float)


class SeoulTrainingDataset(Base):
    """서울 LSTM 사전학습용 통합 데이터셋

    alembic e2b3c4d5f6a7 에서 seoul_dong_master FK 추가 완료.
    """

    __tablename__ = "seoul_training_dataset"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    quarter = Column(BigInteger, index=True)
    dong_code = Column(
        Text,
        ForeignKey("seoul_dong_master.dong_code", onupdate="CASCADE"),
        index=True,
    )
    dong_name = Column(Text)
    industry_code = Column(
        Text,
        ForeignKey("industry_master.industry_code", onupdate="CASCADE"),
    )
    industry_name = Column(Text)
    monthly_sales = Column(BigInteger)
    monthly_count = Column(BigInteger)
    store_count = Column(BigInteger)
    open_count = Column(BigInteger)
    close_count = Column(BigInteger)
    total_pop = Column(Float)
    cpi_index = Column(Float)


class SeoulRealtimeHotspots(Base):
    """서울 27개 주요 POI 실시간 혼잡도/인구/성별/연령 (30분 주기 누적)"""

    __tablename__ = "seoul_realtime_hotspots"
    __table_args__ = (Index("idx_seoul_realtime_hotspots_area_time", "area_cd", "collected_at"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="자동증가 PK")
    area_cd = Column(String(20), nullable=False, comment="POI 코드")
    area_nm = Column(String(50), nullable=False, comment="POI 명")
    collected_at = Column(DateTime(timezone=True), nullable=False, comment="수집 시각")
    congest_level = Column(String(10), comment="혼잡도 등급 (여유/보통/약간 붐빔/붐빔)")
    congest_msg = Column(Text, comment="혼잡도 메시지")
    pop_min = Column(Integer, comment="추정 실시간 인구 하한")
    pop_max = Column(Integer, comment="추정 실시간 인구 상한")
    male_rate = Column(Float, comment="남성 비율 (%)")
    female_rate = Column(Float, comment="여성 비율 (%)")
    age_0_10 = Column(Float, comment="0~9세 비율 (%)")
    age_10s = Column(Float, comment="10대 비율 (%)")
    age_20s = Column(Float, comment="20대 비율 (%)")
    age_30s = Column(Float, comment="30대 비율 (%)")
    age_40s = Column(Float, comment="40대 비율 (%)")
    age_50s = Column(Float, comment="50대 비율 (%)")
    age_60s = Column(Float, comment="60대 비율 (%)")
    age_70_plus = Column(Float, comment="70대 이상 비율 (%)")
    resident_rate = Column(Float, comment="상주인구 비율 (%)")
    visitor_rate = Column(Float, comment="방문자 비율 (%)")
    cmrc_total_level = Column(String(10), comment="상권 종합 레벨")
    cmrc_payment_cnt = Column(String(20), comment="실시간 결제 건수 구간")
    cmrc_payment_amt_min = Column(String(30), comment="결제 금액 하한")
    cmrc_payment_amt_max = Column(String(30), comment="결제 금액 상한")


class ElderlyRatioRegion(Base):
    """시군구 월별 고령인구비율 (65세 이상 / 전체 인구)"""

    __tablename__ = "elderly_ratio_region"
    __table_args__ = (
        UniqueConstraint("region", "ym", name="elderly_ratio_region_region_ym_key"),
        Index("idx_err_region", "region"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="자동증가 PK")
    region = Column(Text, nullable=False, comment="행정구역명 (시/군/구)")
    ym = Column(Integer, nullable=False, comment="연월 (YYYYMM)")
    elderly_ratio = Column(Float, comment="고령인구비율 (%)")
    elderly_pop = Column(BigInteger, comment="65세 이상 인구")
    total_pop = Column(BigInteger, comment="전체 인구")


# ---------------------------------------------------------------------------
# 2026-04-17~20 신규 적재 테이블 (34종) — DB reflection 자동 생성
# ---------------------------------------------------------------------------


class AptTradeReal(Base):
    """apt_trade_real — reflected from DB (2026-04-20)."""

    __tablename__ = "apt_trade_real"

    id = Column(BigInteger, primary_key=True)
    sigungu = Column(Text)
    jibun_addr = Column(Text)
    bon_beon = Column(Text)
    bu_beon = Column(Text)
    apt_name = Column(Text)
    area_sqm = Column(Float)
    deal_ym = Column(Integer)
    deal_day = Column(Integer)
    price_won = Column(BigInteger)
    cancel_date = Column(Text)
    floor = Column(Integer)
    seller = Column(Text)
    buyer = Column(Text)
    build_year = Column(Integer)
    road_addr = Column(Text)
    realty_type = Column(Text)
    deal_type = Column(Text)
    region_full = Column(Text)
    cancel_reason = Column(Text)
    property_type = Column(Text)


class BusBoardingDaily(Base):
    """bus_boarding_daily — reflected from DB (2026-04-20)."""

    __tablename__ = "bus_boarding_daily"

    id = Column(BigInteger, primary_key=True)
    use_date = Column(Date, nullable=False)
    route_no = Column(String(20))
    route_name = Column(Text)
    ars_id = Column(String(15))
    station_name = Column(Text)
    boarding_count = Column(Integer)
    alighting_count = Column(Integer)


class DistrictSalesSeoul(Base):
    """district_sales_seoul — reflected from DB (2026-04-20).

    alembic e2b3c4d5f6a7 에서 seoul_dong_master FK 추가 완료.
    """

    __tablename__ = "district_sales_seoul"

    id = Column(BigInteger, primary_key=True)
    quarter = Column(Integer, nullable=False)
    dong_code = Column(
        String(15),
        ForeignKey("seoul_dong_master.dong_code", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    dong_name = Column(Text)
    industry_code = Column(
        String(20),
        ForeignKey("industry_master.industry_code", onupdate="CASCADE"),
        nullable=False,
    )
    industry_name = Column(Text)
    monthly_sales = Column(BigInteger)
    monthly_count = Column(Integer)
    raw_json = Column(JSONB)


class DongSubwayAccess(Base):
    """dong_subway_access — reflected from DB (2026-04-20)."""

    __tablename__ = "dong_subway_access"

    dong_name = Column(String(30), primary_key=True)
    center_lat = Column(Float)
    center_lon = Column(Float)
    nearest_subway = Column(String(50))
    subway_distance_m = Column(Integer)
    subway_count_1km = Column(Integer)


class EcosKeyStatistics(Base):
    """ecos_key_statistics — reflected from DB (2026-04-20)."""

    __tablename__ = "ecos_key_statistics"

    class_name = Column(Text)
    keystat_name = Column(Text, primary_key=True)
    data_value = Column(Float)
    cycle = Column(String(20), primary_key=True)
    unit_name = Column(Text)
    collected_at = Column(DateTime)


class EcosTimeseries(Base):
    """ecos_timeseries — reflected from DB (2026-04-20)."""

    __tablename__ = "ecos_timeseries"

    stat_code = Column(String(20), primary_key=True)
    stat_name = Column(Text)
    item_code1 = Column(String(30), primary_key=True)
    item_name1 = Column(Text)
    item_code2 = Column(String(30), primary_key=True)
    item_name2 = Column(Text)
    cycle = Column(String(10))
    period = Column(String(20), primary_key=True)
    data_value = Column(Float)
    unit_name = Column(Text)


class HolidayCalendar(Base):
    """holiday_calendar — reflected from DB (2026-04-20)."""

    __tablename__ = "holiday_calendar"

    date = Column(Date, primary_key=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    dow = Column(Integer, nullable=False)
    dow_name = Column(String(10))
    is_weekend = Column(Boolean, nullable=False)
    is_holiday = Column(Boolean, nullable=False)
    holiday_name = Column(String(50))
    is_substitute = Column(Boolean)
    day_type = Column(String(15))


class JeonseMonthlyRent(Base):
    """jeonse_monthly_rent — 국토부 전월세 신고 원본 (법정동 10자리).

    alembic f3c4d5e6a7b8 에서 jeonse_dong_master FK 추가 완료 (NOT VALID + VALIDATE).
    ORM 은 reflected 시 String(15) 였으나, 실제 데이터는 모두 10자리 → DB 마이그레이션 설계와 동기화.
    """

    __tablename__ = "jeonse_monthly_rent"

    id = Column(BigInteger, primary_key=True)
    rcpt_year = Column(Integer)
    gu_code = Column(String(10))
    gu_name = Column(Text)
    dong_code = Column(
        String(10),
        ForeignKey("jeonse_dong_master.dong_code", onupdate="CASCADE"),
        index=True,
    )
    dong_name = Column(Text)
    jibun_type = Column(Integer)
    jibun_type_name = Column(Text)
    bon_beon = Column(Integer)
    bu_beon = Column(Integer)
    floor = Column(Integer)
    contract_date = Column(Integer)
    trade_type = Column(String(10))
    area_sqm = Column(Float)
    deposit_manwon = Column(BigInteger)
    monthly_rent_manwon = Column(BigInteger)
    building_name = Column(Text)
    build_year = Column(Integer)
    building_type = Column(Text)
    contract_period = Column(Text)
    new_renew = Column(Text)
    renew_right_used = Column(Text)
    prev_deposit = Column(Float)
    prev_monthly_rent = Column(Float)


class KakaoStoreHours(Base):
    """kakao_store_hours — reflected from DB (2026-04-20)."""

    __tablename__ = "kakao_store_hours"

    kakao_id = Column(String(20), primary_key=True)
    headline_code = Column(String(20))
    headline_text = Column(Text)
    mon_hours = Column(Text)
    tue_hours = Column(Text)
    wed_hours = Column(Text)
    thu_hours = Column(Text)
    fri_hours = Column(Text)
    sat_hours = Column(Text)
    sun_hours = Column(Text)
    hours_json = Column(JSONB)
    collected_at = Column(DateTime)


class KakaoStoreMenu(Base):
    """카카오 panel3 응답의 menu.menus.items[] 저장 — 점포별 메뉴/가격."""

    __tablename__ = "kakao_store_menu"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    kakao_id = Column(
        String(20),
        ForeignKey("kakao_store.kakao_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="점포 FK",
    )
    product_id = Column(Integer, comment="카카오 내부 메뉴 ID")
    menu_name = Column(Text, nullable=False, comment="메뉴명")
    price = Column(Integer, index=True, comment="가격(원)")
    description = Column(Text, comment="메뉴 설명")
    photo_url = Column(Text, comment="사진 URL")
    mod_at = Column(DateTime, comment="카카오 측 최종 수정일")
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), comment="수집 일시")


class KosisRegionalIncome(Base):
    """kosis_regional_income — reflected from DB (2026-04-20)."""

    __tablename__ = "kosis_regional_income"

    id = Column(BigInteger, primary_key=True)
    tbl_id = Column(String(30), nullable=False)
    tbl_name = Column(Text)
    region_code = Column(String(20))
    region_name = Column(Text)
    item_code = Column(String(20))
    item_name = Column(Text)
    unit = Column(Text)
    period_code = Column(String(10))
    period_name = Column(String(20))
    period_value = Column(String(20))
    value_num = Column(Float)
    src_last_chn_de = Column(Date)


class LawLegislations(Base):
    """law_legislations — reflected from DB (2026-04-20)."""

    __tablename__ = "law_legislations"

    item_id = Column(String(50), primary_key=True)
    title = Column(Text, nullable=False)
    law_short_name = Column(Text)
    promulgation_date = Column(Date)
    enforce_date = Column(Date)
    promulgation_no = Column(String(50))
    ministry_name = Column(Text)
    law_type = Column(Text)
    law_revision_type = Column(Text)
    detail_link = Column(Text)
    raw_json = Column(JSONB)
    queries = Column(Text)
    collected_at = Column(DateTime)


class LawPrecedents(Base):
    """law_precedents — reflected from DB (2026-04-20)."""

    __tablename__ = "law_precedents"

    item_id = Column(String(50), primary_key=True)
    case_number = Column(String(100))
    case_name = Column(Text)
    case_type_code = Column(String(20))
    case_type_name = Column(String(50))
    sentence = Column(String(20))
    sentence_date = Column(Date)
    court_name = Column(Text)
    judgment_type = Column(String(50))
    detail_link = Column(Text)
    data_source = Column(Text)
    raw_json = Column(JSONB)
    queries = Column(Text)
    collected_at = Column(DateTime)


class MapoSnsSentiment(Base):
    """mapo_sns_sentiment — reflected from DB (2026-04-20)."""

    __tablename__ = "mapo_sns_sentiment"

    id = Column(BigInteger, primary_key=True)
    place_name = Column(Text, nullable=False)
    date = Column(Date, nullable=False)
    positive_count = Column(Integer)
    negative_count = Column(Integer)
    neutral_count = Column(Integer)


class MolitNrgTrade(Base):
    """molit_nrg_trade — reflected from DB (2026-04-20)."""

    __tablename__ = "molit_nrg_trade"

    id = Column(BigInteger, primary_key=True)
    lawd_cd = Column(String(10), nullable=False)
    gu_name = Column(String(20))
    deal_ym = Column(Integer, nullable=False)
    deal_day = Column(Integer)
    deal_amount = Column(BigInteger)
    building_use = Column(Text)
    building_ar = Column(Float)
    plottage_ar = Column(Float)
    building_type = Column(Text)
    realty_type = Column(Text)
    floor = Column(Text)
    build_year = Column(Text)
    sgg_nm = Column(Text)
    umd_nm = Column(Text)
    jibun = Column(Text)
    cdeal_type = Column(Text)
    cdeal_day = Column(Text)
    dealing_gbn = Column(Text)


class NaverTrendIndustry(Base):
    """naver_trend_industry — reflected from DB (2026-04-20)."""

    __tablename__ = "naver_trend_industry"

    id = Column(BigInteger, primary_key=True)
    industry = Column(Text, nullable=False)
    period = Column(Date, nullable=False)
    ratio = Column(Float)


class NaverTrendMonthly(Base):
    """naver_trend_monthly — reflected from DB (2026-04-20)."""

    __tablename__ = "naver_trend_monthly"

    id = Column(BigInteger, primary_key=True)
    keyword = Column(Text, nullable=False)
    period = Column(Date, nullable=False)
    ratio = Column(Float)
    scope = Column(String(10), nullable=False)


class NaverTrendQuarterly(Base):
    """naver_trend_quarterly — reflected from DB (2026-04-20)."""

    __tablename__ = "naver_trend_quarterly"

    id = Column(BigInteger, primary_key=True)
    quarter = Column(Integer, nullable=False)
    dong_name = Column(String(30), nullable=False)
    trend_score = Column(Float)
    scope = Column(String(10), nullable=False)


class RentCostSummary2025(Base):
    """rent_cost_summary_2025 — reflected from DB (2026-04-20)."""

    __tablename__ = "rent_cost_summary_2025"

    id = Column(BigInteger, primary_key=True)
    region1 = Column(Text)
    region2 = Column(Text)
    rent_1000won_sqm = Column(Float)
    vacancy_rate_pct = Column(Float)
    investment_return_pct = Column(Float)
    income_return_pct = Column(Float)
    capital_return_pct = Column(Float)
    source_file = Column(Text)


class ResidentPopMonthly(Base):
    """resident_pop_monthly — reflected from DB (2026-04-20)."""

    __tablename__ = "resident_pop_monthly"

    region_full = Column(Text, primary_key=True)
    region_code = Column(String(15))
    ym = Column(Integer, primary_key=True)
    total_pop = Column(Integer)
    households = Column(Integer)
    pop_per_household = Column(Float)
    male_pop = Column(Integer)
    female_pop = Column(Integer)
    male_female_ratio = Column(Float)


class SeoulAdstrdChangeIx(Base):
    """seoul_adstrd_change_ix — reflected from DB (2026-04-20).

    alembic e2b3c4d5f6a7 에서 seoul_dong_master FK 추가 완료.
    """

    __tablename__ = "seoul_adstrd_change_ix"

    quarter = Column(Integer, primary_key=True)
    dong_code = Column(
        String(15),
        ForeignKey("seoul_dong_master.dong_code", onupdate="CASCADE"),
        primary_key=True,
    )
    dong_name = Column(Text)
    change_ix = Column(String(10))
    change_ix_name = Column(String(50))
    opr_sale_mt_avg = Column(Float)
    cls_sale_mt_avg = Column(Float)
    su_opr_sale_mt_avg = Column(Float)
    su_cls_sale_mt_avg = Column(Float)


class SeoulAdstrdFclty(Base):
    """seoul_adstrd_fclty — reflected from DB (2026-04-20)."""

    __tablename__ = "seoul_adstrd_fclty"

    quarter = Column(Integer, primary_key=True)
    dong_code = Column(String(15), primary_key=True)
    dong_name = Column(Text)
    viatr_fclty_co = Column(Integer)
    pblofc_co = Column(Integer)
    bank_co = Column(Integer)
    gehspt_co = Column(Integer)
    gnrl_hsptl_co = Column(Integer)
    parmacy_co = Column(Integer)
    kndrgr_co = Column(Integer)
    elesch_co = Column(Integer)
    mskul_co = Column(Integer)
    hgschl_co = Column(Integer)
    univ_co = Column(Integer)
    drts_co = Column(Integer)
    supmk_co = Column(Integer)
    theat_co = Column(Integer)
    stayng_fclty_co = Column(Integer)
    arprt_co = Column(Integer)
    rlroad_statn_co = Column(Integer)
    bus_trminl_co = Column(Integer)
    subway_statn_co = Column(Integer)
    bus_sttn_co = Column(Integer)


class SeoulAdstrdFlpop(Base):
    """seoul_adstrd_flpop — reflected from DB (2026-04-20).

    alembic e2b3c4d5f6a7 에서 seoul_dong_master FK 추가 완료.
    """

    __tablename__ = "seoul_adstrd_flpop"

    quarter = Column(Integer, primary_key=True)
    dong_code = Column(
        String(15),
        ForeignKey("seoul_dong_master.dong_code", onupdate="CASCADE"),
        primary_key=True,
    )
    dong_name = Column(Text)
    total_flpop = Column(Integer)
    male_flpop = Column(Integer)
    female_flpop = Column(Integer)
    age_10 = Column(Integer)
    age_20 = Column(Integer)
    age_30 = Column(Integer)
    age_40 = Column(Integer)
    age_50 = Column(Integer)
    age_60_above = Column(Integer)
    time_00_06 = Column(Integer)
    time_06_11 = Column(Integer)
    time_11_14 = Column(Integer)
    time_14_17 = Column(Integer)
    time_17_21 = Column(Integer)
    time_21_24 = Column(Integer)
    mon = Column(Integer)
    tue = Column(Integer)
    wed = Column(Integer)
    thu = Column(Integer)
    fri = Column(Integer)
    sat = Column(Integer)
    sun = Column(Integer)


class SeoulAdstrdStor(Base):
    """seoul_adstrd_stor — reflected from DB (2026-04-20).

    alembic e2b3c4d5f6a7 에서 seoul_dong_master FK 추가 완료 (849k row VALIDATE).
    """

    __tablename__ = "seoul_adstrd_stor"

    quarter = Column(Integer, primary_key=True)
    dong_code = Column(
        String(15),
        ForeignKey("seoul_dong_master.dong_code", onupdate="CASCADE"),
        primary_key=True,
    )
    dong_name = Column(Text)
    industry_code = Column(
        String(20),
        ForeignKey("industry_master.industry_code", onupdate="CASCADE"),
        primary_key=True,
    )
    industry_name = Column(Text)
    store_count = Column(Integer)
    similar_store_count = Column(Integer)
    open_rate = Column(Float)
    open_count = Column(Integer)
    close_rate = Column(Float)
    close_count = Column(Integer)
    franchise_count = Column(Integer)


class SeoulSignguChangeIx(Base):
    """seoul_signgu_change_ix — reflected from DB (2026-04-20)."""

    __tablename__ = "seoul_signgu_change_ix"

    quarter = Column(Integer, primary_key=True)
    signgu_code = Column(String(10), primary_key=True)
    signgu_name = Column(Text)
    change_ix = Column(String(10))
    change_ix_name = Column(String(50))
    opr_sale_mt_avg = Column(Float)
    cls_sale_mt_avg = Column(Float)
    su_opr_sale_mt_avg = Column(Float)
    su_cls_sale_mt_avg = Column(Float)


class SeoulSignguFclty(Base):
    """seoul_signgu_fclty — reflected from DB (2026-04-20)."""

    __tablename__ = "seoul_signgu_fclty"

    quarter = Column(Integer, primary_key=True)
    signgu_code = Column(String(10), primary_key=True)
    signgu_name = Column(Text)
    viatr_fclty_co = Column(Integer)
    pblofc_co = Column(Integer)
    bank_co = Column(Integer)
    gehspt_co = Column(Integer)
    gnrl_hsptl_co = Column(Integer)
    parmacy_co = Column(Integer)
    kndrgr_co = Column(Integer)
    elesch_co = Column(Integer)
    mskul_co = Column(Integer)
    hgschl_co = Column(Integer)
    univ_co = Column(Integer)
    drts_co = Column(Integer)
    supmk_co = Column(Integer)
    theat_co = Column(Integer)
    stayng_fclty_co = Column(Integer)
    arprt_co = Column(Integer)
    rlroad_statn_co = Column(Integer)
    bus_trminl_co = Column(Integer)
    subway_statn_co = Column(Integer)
    bus_sttn_co = Column(Integer)


class SeoulSignguFlpop(Base):
    """seoul_signgu_flpop — reflected from DB (2026-04-20)."""

    __tablename__ = "seoul_signgu_flpop"

    quarter = Column(Integer, primary_key=True)
    signgu_code = Column(String(10), primary_key=True)
    signgu_name = Column(Text)
    total_flpop = Column(Integer)
    male_flpop = Column(Integer)
    female_flpop = Column(Integer)
    age_10 = Column(Integer)
    age_20 = Column(Integer)
    age_30 = Column(Integer)
    age_40 = Column(Integer)
    age_50 = Column(Integer)
    age_60_above = Column(Integer)
    time_00_06 = Column(Integer)
    time_06_11 = Column(Integer)
    time_11_14 = Column(Integer)
    time_14_17 = Column(Integer)
    time_17_21 = Column(Integer)
    time_21_24 = Column(Integer)
    mon = Column(Integer)
    tue = Column(Integer)
    wed = Column(Integer)
    thu = Column(Integer)
    fri = Column(Integer)
    sat = Column(Integer)
    sun = Column(Integer)


class SeoulSignguSelng(Base):
    """seoul_signgu_selng — reflected from DB (2026-04-20)."""

    __tablename__ = "seoul_signgu_selng"

    quarter = Column(Integer, primary_key=True)
    signgu_code = Column(String(10), primary_key=True)
    signgu_name = Column(Text)
    industry_code = Column(
        String(20),
        ForeignKey("industry_master.industry_code", onupdate="CASCADE"),
        primary_key=True,
    )
    industry_name = Column(Text)
    monthly_sales = Column(BigInteger)
    monthly_count = Column(BigInteger)
    weekday_sales = Column(BigInteger)
    weekend_sales = Column(BigInteger)
    mon_sales = Column(BigInteger)
    tue_sales = Column(BigInteger)
    wed_sales = Column(BigInteger)
    thu_sales = Column(BigInteger)
    fri_sales = Column(BigInteger)
    sat_sales = Column(BigInteger)
    sun_sales = Column(BigInteger)


class SeoulSignguStor(Base):
    """seoul_signgu_stor — reflected from DB (2026-04-20)."""

    __tablename__ = "seoul_signgu_stor"

    quarter = Column(Integer, primary_key=True)
    signgu_code = Column(String(10), primary_key=True)
    signgu_name = Column(Text)
    industry_code = Column(
        String(20),
        ForeignKey("industry_master.industry_code", onupdate="CASCADE"),
        primary_key=True,
    )
    industry_name = Column(Text)
    store_count = Column(Integer)
    similar_store_count = Column(Integer)
    open_rate = Column(Float)
    open_count = Column(Integer)
    close_rate = Column(Float)
    close_count = Column(Integer)
    franchise_count = Column(Integer)


class SeoulTrdarChangeIx(Base):
    """seoul_trdar_change_ix — reflected from DB (2026-04-20)."""

    __tablename__ = "seoul_trdar_change_ix"

    quarter = Column(Integer, primary_key=True)
    trdar_code = Column(String(15), primary_key=True)
    trdar_name = Column(Text)
    trdar_se = Column(String(10))
    trdar_se_name = Column(String(30))
    change_ix = Column(String(10))
    change_ix_name = Column(String(50))
    opr_sale_mt_avg = Column(Float)
    cls_sale_mt_avg = Column(Float)
    su_opr_sale_mt_avg = Column(Float)
    su_cls_sale_mt_avg = Column(Float)


class SeoulTrdarFclty(Base):
    """seoul_trdar_fclty — reflected from DB (2026-04-20)."""

    __tablename__ = "seoul_trdar_fclty"

    quarter = Column(Integer, primary_key=True)
    trdar_code = Column(String(15), primary_key=True)
    trdar_name = Column(Text)
    trdar_se = Column(String(10))
    trdar_se_name = Column(String(30))
    viatr_fclty_co = Column(Integer)
    pblofc_co = Column(Integer)
    bank_co = Column(Integer)
    gehspt_co = Column(Integer)
    gnrl_hsptl_co = Column(Integer)
    parmacy_co = Column(Integer)
    kndrgr_co = Column(Integer)
    elesch_co = Column(Integer)
    mskul_co = Column(Integer)
    hgschl_co = Column(Integer)
    univ_co = Column(Integer)
    drts_co = Column(Integer)
    supmk_co = Column(Integer)
    theat_co = Column(Integer)
    stayng_fclty_co = Column(Integer)
    arprt_co = Column(Integer)
    rlroad_statn_co = Column(Integer)
    bus_trminl_co = Column(Integer)
    subway_statn_co = Column(Integer)
    bus_sttn_co = Column(Integer)


class SeoulTrdarFlpop(Base):
    """seoul_trdar_flpop — reflected from DB (2026-04-20)."""

    __tablename__ = "seoul_trdar_flpop"

    quarter = Column(Integer, primary_key=True)
    trdar_code = Column(String(15), primary_key=True)
    trdar_name = Column(Text)
    trdar_se = Column(String(10))
    trdar_se_name = Column(String(30))
    total_flpop = Column(Integer)
    male_flpop = Column(Integer)
    female_flpop = Column(Integer)
    age_10 = Column(Integer)
    age_20 = Column(Integer)
    age_30 = Column(Integer)
    age_40 = Column(Integer)
    age_50 = Column(Integer)
    age_60_above = Column(Integer)
    time_00_06 = Column(Integer)
    time_06_11 = Column(Integer)
    time_11_14 = Column(Integer)
    time_14_17 = Column(Integer)
    time_17_21 = Column(Integer)
    time_21_24 = Column(Integer)
    mon = Column(Integer)
    tue = Column(Integer)
    wed = Column(Integer)
    thu = Column(Integer)
    fri = Column(Integer)
    sat = Column(Integer)
    sun = Column(Integer)


class SmallStoreRentQ(Base):
    """small_store_rent_q — reflected from DB (2026-04-20)."""

    __tablename__ = "small_store_rent_q"

    id = Column(BigInteger, primary_key=True)
    cls_id = Column(Integer, nullable=False)
    cls_full_nm = Column(Text, nullable=False)
    cls_nm = Column(Text)
    region = Column(Text, nullable=False)
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)
    rent = Column(Float)
    statbl_id = Column(Text)


class VacancyEnriched(Base):
    """vacancy_enriched — reflected from DB (2026-04-20)."""

    __tablename__ = "vacancy_enriched"

    id = Column(BigInteger, primary_key=True)
    lat = Column(Float)
    lon = Column(Float)
    dong_name = Column(String(30))
    nearest_subway = Column(String(50))
    subway_distance = Column(Integer)
    restaurant_500m = Column(Integer)
    cafe_500m = Column(Integer)
    mart_500m = Column(Integer)
    address = Column(Text)
    road_address = Column(Text)
    building_name = Column(String(200))
    listing_count = Column(Integer)


class WeatherDaily(Base):
    """weather_daily — reflected from DB (2026-04-20)."""

    __tablename__ = "weather_daily"

    date = Column(Date, primary_key=True)
    stn = Column(String(10), primary_key=True)
    stn_name = Column(String(20))
    wind_avg = Column(Float)
    wind_max = Column(Float)
    temp_avg = Column(Float)
    temp_max = Column(Float)
    temp_min = Column(Float)
    humidity_avg = Column(Float)
    humidity_min = Column(Float)
    pressure_avg = Column(Float)
    cloud_avg = Column(Float)
    sunshine_hours = Column(Float)
    insolation = Column(Float)
    rain_day = Column(Float)
    rain_60m_max = Column(Float)
    snow_new = Column(Float)
    snow_max = Column(Float)


# ---------------------------------------------------------------------------
# 고객 (매장 방문 기록)
# ---------------------------------------------------------------------------


class Customer(Base):
    """고객 — 매장 방문 고객 기본 정보 (고객당 방문 날짜 1건)"""

    __tablename__ = "customers"

    customer_id = Column(String(20), primary_key=True, comment="고객 아이디")
    customer_name = Column(Text, nullable=False, comment="고객 이름")
    visit_date = Column(Date, comment="방문 날짜")


# ---------------------------------------------------------------------------
# 시뮬레이션 이력 — simulation_history 는 미구현 기능으로 alembic 91b66e68ec18 에서 drop.
# 매니저 시뮬 저장은 simulation_ai / simulation_foresee 가 담당.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 예측 결과 이력 (Predict 탭)
# ---------------------------------------------------------------------------


class SimulationForesee(Base):
    """예측 결과 이력 — ML 기반 매출/재무/고객/신흥상권 예측 저장"""

    __tablename__ = "simulation_foresee"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    manager_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="작성자 ID — master면 users.id, manager면 manager_users.id",
    )
    user_type = Column(String(10), default="manager", comment="master | manager")
    client_name = Column(String(100), nullable=False, comment="예비 가맹점주 이름")
    brand_name = Column(String(100), nullable=False, comment="브랜드명")
    business_type = Column(String(50), comment="업종")
    districts = Column(JSONB, comment="선택 동 목록 (최대 4개)")
    target_district = Column(String(50), comment="대상 동")
    winner_district = Column(String(50), comment="1순위 추천 동")
    district_predictions = Column(
        JSONB, comment="동별 ML 예측 전체 (quarterly/bep/closure/shap/customer/living_pop/emerging)"
    )
    quarterly_projection = Column(JSONB, comment="분기 매출 예측 (단일 동 fallback)")
    scenarios = Column(JSONB, comment="낙관/기본/비관 시나리오")
    shap_result = Column(JSONB, comment="SHAP 피처 기여도")
    bep_months = Column(Integer, comment="BEP 도달 개월수")
    predicted_monthly_revenue = Column(BigInteger, comment="예측 월매출")
    closure_rate = Column(JSONB, comment="폐업률 (실측)")
    closure_risk = Column(JSONB, comment="폐업위험도 (LightGBM+TCN)")
    final_report = Column(JSONB, comment="수익성 시뮬 (profit_simulation)")
    market_report = Column(JSONB, comment="7개 지표 (생존율 등)")
    customer_segment = Column(JSONB, comment="고객 세그먼트 분석")
    living_pop_forecast = Column(JSONB, comment="유동인구 예측")
    scenario = Column(JSONB, comment="시뮬 시나리오 파라미터 (재실행용)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_foresee_manager_created", "manager_id", "created_at"),
        {"comment": "담당: 봉환 | 예측 결과 이력 (Predict 탭) | ML 매출/재무/고객/신흥상권"},
    )


# ---------------------------------------------------------------------------
# AI 분석 이력 (Analyze 탭)
# ---------------------------------------------------------------------------


class SimulationAI(Base):
    """AI 분석 이력 — LLM 기반 상권/법률/인구/트렌드/경쟁 분석 저장"""

    __tablename__ = "simulation_ai"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    manager_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="작성자 ID — master면 users.id, manager면 manager_users.id",
    )
    user_type = Column(String(10), default="manager", comment="master | manager")
    client_name = Column(String(100), nullable=False, comment="예비 가맹점주 이름")
    brand_name = Column(String(100), nullable=False, comment="브랜드명")
    business_type = Column(String(50), comment="업종")
    target_district = Column(String(50), comment="대상 동")
    winner_district = Column(String(50), comment="1순위 추천 동")
    top_3_candidates = Column(JSONB, comment="상위 3동")
    analysis_report = Column(Text, comment="synthesis 종합 리포트")
    ai_recommendation = Column(Text, comment="최종 권고")
    ai_verdict_summary = Column(Text, comment="한 줄 판단 요약")
    market_entry_signal = Column(String(10), comment="green | yellow | red")
    overall_legal_risk = Column(String(10), comment="safe | caution | danger")
    legal_risks = Column(JSONB, comment="14개 법률 리스크")
    market_report = Column(JSONB, comment="7개 정규화 지표")
    trend_forecast = Column(JSONB, comment="트렌드 전망")
    competitor_intel = Column(JSONB, comment="경쟁사 분석")
    demographic_report = Column(JSONB, comment="인구통계 심화")
    district_rankings = Column(JSONB, comment="16동 랭킹")
    agent_attributions = Column(JSONB, comment="에이전트별 판단 근거")
    vacancy_applied = Column(Boolean, default=False, comment="공실 페널티 반영 여부")
    all_competitor_locations = Column(JSONB, comment="경쟁점포 좌표 목록")
    scenario = Column(JSONB, comment="시뮬 시나리오 파라미터 (재실행용)")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_ai_manager_created", "manager_id", "created_at"),
        {"comment": "담당: 봉환 | AI 분석 이력 (Analyze 탭) | LLM 상권/법률/인구/트렌드/경쟁"},
    )


# ===========================================================================
# Emerging Trend B1 — 인구·이동성 (2026-04-29)
# spec: docs/superpowers/specs/2026-04-29-emerging-trend-data-b1-design.md
# ===========================================================================


class MasterSubwayStation(Base):
    """서울 전체 지하철역 마스터 — 호선/sigungu_code/좌표"""

    __tablename__ = "master_subway_station"

    station_code = Column(String(10), primary_key=True, comment="역코드 (운영사별 통합)")
    station_name = Column(String(50), nullable=False, comment="역명")
    line_name = Column(String(20), comment="호선/노선")
    sigungu_code = Column(String(5), index=True, comment="자치구 코드 (마포=11440)")
    lat = Column(Float, comment="위도")
    lon = Column(Float, comment="경도")
    created_at = Column(DateTime, server_default=func.now(), comment="생성 일시")


class MasterTtareungiStation(Base):
    """서울 전체 따릉이 대여소 마스터"""

    __tablename__ = "master_ttareungi_station"

    station_id = Column(String(20), primary_key=True, comment="대여소 ID")
    station_name = Column(String(100), nullable=False, comment="대여소명")
    sigungu_code = Column(String(5), index=True, comment="자치구 코드")
    dong_code = Column(
        String(8),
        ForeignKey("seoul_dong_master.dong_code"),
        index=True,
        comment="행정동 코드 (8자리 FK)",
    )
    lat = Column(Float, comment="위도")
    lon = Column(Float, comment="경도")
    opened_at = Column(Date, comment="개소일 (있으면)")
    created_at = Column(DateTime, server_default=func.now(), comment="생성 일시")


class SeoulSubwayPassengerDaily(Base):
    """서울 전체 지하철 일별 승하차"""

    __tablename__ = "seoul_subway_passenger_daily"

    date = Column(Date, primary_key=True, comment="영업일")
    station_code = Column(
        String(10),
        ForeignKey("master_subway_station.station_code"),
        primary_key=True,
        comment="역코드",
    )
    boarding_cnt = Column(Integer, comment="승차 인원")
    alighting_cnt = Column(Integer, comment="하차 인원")

    __table_args__ = (Index("ix_subway_passenger_station", "station_code"),)


class SeoulDongMigrationMonthly(Base):
    """서울 전체 동별 월간 전입/전출 (20-30대 별도 컬럼)"""

    __tablename__ = "seoul_dong_migration_monthly"

    ym = Column(Integer, primary_key=True, comment="YYYYMM")
    dong_code = Column(
        String(8),
        ForeignKey("seoul_dong_master.dong_code"),
        primary_key=True,
        comment="행정동 코드",
    )
    move_in_cnt = Column(Integer, comment="전입 총수")
    move_out_cnt = Column(Integer, comment="전출 총수")
    net_move = Column(Integer, comment="순이동 (전입 - 전출)")
    move_in_2030 = Column(Integer, comment="20-30대 전입자 수")
    move_out_2030 = Column(Integer, comment="20-30대 전출자 수")


class SeoulTtareungiUsageDaily(Base):
    """서울 전체 따릉이 일×대여소 집계"""

    __tablename__ = "seoul_ttareungi_usage_daily"

    date = Column(Date, primary_key=True, comment="이용일")
    station_id = Column(
        String(20),
        ForeignKey("master_ttareungi_station.station_id"),
        primary_key=True,
        comment="대여소 ID",
    )
    rent_cnt = Column(Integer, comment="대여 건수")
    return_cnt = Column(Integer, comment="반납 건수")

    __table_args__ = (Index("ix_ttareungi_usage_station", "station_id"),)
