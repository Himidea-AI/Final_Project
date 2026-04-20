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
    Integer,
    SmallInteger,
    String,
    Text,
    func,
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
    workspace_id = Column(String(100), index=True, comment="워크스페이스 ID (멀티테넌시)")
    input_params = Column(JSONB, comment="시뮬레이션 입력 파라미터 (JSON)")
    output_result = Column(JSONB, comment="시뮬레이션 분석 결과 (JSON)")
    status = Column(String(20), default="pending", comment="처리 상태 (pending/running/done/error)")


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
    plan = Column(String(20), default="starter", comment="요금제 (starter/growth)")
    agree_terms = Column(Boolean, default=False, comment="이용약관 동의 여부")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="가입 일시",
    )


class FtcBrandFranchise(Base):
    """공정거래위원회 프랜차이즈 브랜드 정보 — 회원가입 시 브랜드 자동 매핑용"""

    __tablename__ = "ftc_brand_franchise"

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
    max_uses = Column(Integer, default=10, comment="최대 사용 가능 횟수")
    used_count = Column(Integer, default=0, comment="현재 사용된 횟수")
    is_active = Column(Boolean, default=True, comment="활성 여부")
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
    is_active = Column(Boolean, default=True, comment="활성 여부")
    is_approved = Column(Boolean, default=False, comment="팀장 승인 여부")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="가입 일시",
    )


# ---------------------------------------------------------------------------
# 외부 수집 / 보조 테이블 (CSV 시드 전용, ORM 사용 최소)
# ---------------------------------------------------------------------------


class BrandLogo(Base):
    """브랜드 로고 수집 결과"""

    __tablename__ = "brand_logo"

    brand_name = Column(String(100), primary_key=True, comment="브랜드명")
    domain = Column(String(100), comment="도메인")
    logo_url = Column(Text, comment="로고 URL")
    logo_source = Column(String(30), comment="수집 소스")
    collected_at = Column(DateTime(timezone=True), server_default=func.now(), comment="수집 시각")


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
    industry_code = Column(Text, comment="업종 코드")
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
    industry_code = Column(Text, comment="업종 코드")
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
    """서울 전체 행정동 분기 매출 — 사전학습용"""

    __tablename__ = "seoul_district_sales"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    quarter = Column(BigInteger, index=True)
    dong_code = Column(Text, index=True)
    dong_name = Column(Text)
    industry_code = Column(Text)
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
    """서울 전체 행정동 분기 점포 — 사전학습용"""

    __tablename__ = "seoul_district_stores"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    quarter = Column(BigInteger, index=True)
    dong_code = Column(Text, index=True)
    dong_name = Column(Text)
    industry_code = Column(Text)
    industry_name = Column(Text)
    store_count = Column(BigInteger)
    similar_store_count = Column(BigInteger)
    open_count = Column(BigInteger)
    close_count = Column(BigInteger)
    franchise_count = Column(BigInteger)
    closure_rate = Column(BigInteger)


class SeoulGolmokRent(Base):
    """서울 전체 골목상권 환산임대료 — 사전학습용"""

    __tablename__ = "seoul_golmok_rent"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    year = Column(BigInteger, index=True)
    quarter = Column(BigInteger)
    dong_code = Column(Text, index=True)
    dong_name = Column(Text)
    gubun = Column(Text)
    rent_1f = Column(Float)
    rent_other = Column(Float)
    rent_total = Column(Float)
    quarter_code = Column(BigInteger)


class SeoulPopulationQuarterly(Base):
    """서울 행정동별 분기 인구"""

    __tablename__ = "seoul_population_quarterly"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    quarter = Column(BigInteger, index=True)
    dong_code = Column(Text, index=True)
    total_pop = Column(Float)


class SeoulTrainingDataset(Base):
    """서울 LSTM 사전학습용 통합 데이터셋"""

    __tablename__ = "seoul_training_dataset"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="자동증가 PK")
    quarter = Column(BigInteger, index=True)
    dong_code = Column(Text, index=True)
    dong_name = Column(Text)
    industry_code = Column(Text)
    industry_name = Column(Text)
    monthly_sales = Column(BigInteger)
    monthly_count = Column(BigInteger)
    store_count = Column(BigInteger)
    open_count = Column(BigInteger)
    close_count = Column(BigInteger)
    total_pop = Column(Float)
    cpi_index = Column(Float)
