"""
시뮬레이션 요청 입력 모델 — 클라이언트에서 API로 보내는 요청 스키마
"""

from pydantic import BaseModel, Field


class ExistingStoreInput(BaseModel):
    """기존 매장 정보 입력"""

    district: str
    address: str
    monthly_revenue: int = 0


class SimulationInput(BaseModel):
    """시뮬레이션 요청 입력 스키마"""

    business_type: str = Field(..., description="업종 코드 (cafe, restaurant, convenience)")
    brand_name: str = Field(..., description="브랜드명")
    # 사용자 회원가입 사업자번호 — corp_brand_resolver 가 다업종 corp 의 적합 brand 자동 선택용.
    # 미입력 시 회원 검증 skip + brand_name 그대로 사용 (개인사업자 / 비회원 호환).
    biz_number: str | None = Field(default=None, description="사업자등록번호 (corp 검증 + auto-brand-resolve)")
    target_district: str = Field(..., description="출점 후보 행정동 (대표 1개)")
    target_districts: list[str] = Field(
        default_factory=list, description="사용자가 선택한 후보 행정동 목록 (복수 선택 지원)"
    )
    existing_stores: list[ExistingStoreInput] = Field(default_factory=list, description="기존 매장 목록")
    monthly_rent: int = Field(default=0, description="월 임대료 (원, 0이면 자동 추정)")
    scenarios: list[str] = Field(default_factory=lambda: ["base"], description="시나리오 목록")

    # 사용자 입력 확장 파라미터
    store_area: float = Field(default=15.0, description="점포 면적 (평)")
    target_price_range: str = Field(default="5to10k", description="목표 객단가 구간 (예: 5to10k, 10to15k)")
    operating_hours: list[str] = Field(default_factory=lambda: ["점심", "저녁"], description="주 타겟 영업 시간대")
    initial_capital: int = Field(default=50_000_000, description="초기 자본금 (원)")
    commercial_radius: int = Field(default=500, description="상권 분석 반경 (m)")
    # 자사 영업구역 거리. 가맹사업법 제12조의4 인접 출점 정량 룰에 사용.
    # 미입력 시 specialists.py 의 기본 500m 임계값 적용.
    territory_radius_m: int | None = Field(
        default=None, description="자사 영업구역 거리(m) — 사용자 입력 (메가 250m / 빽다방 350m / 이디야 500m 등)"
    )
    population_weight: bool = Field(default=True, description="인구 가중치 반영 여부")
    industry_filter: str | None = Field(
        default=None, description="CS 업종 코드 필터 (예: CS100010). 미지정 시 전체 업종."
    )

    # 출점 후보지 좌표 — 학교환경위생정화구역(rule_school_zone) 거리 계산 트리거
    lat: float | None = Field(default=None, description="출점 후보지 위도 (학교 거리 룰 트리거)")
    lon: float | None = Field(default=None, description="출점 후보지 경도")

    # [customer_revenue P1-C] 타겟 고객 프로필 — models/customer_revenue/predict.py 입력
    # 값은 SegmentProfile 스펙 그대로 (age: "30대", time: "time_11_14", day: "weekday|weekend")
    target_age_groups: list[str] = Field(
        default_factory=list, description="타겟 연령대 (빈 리스트=전체). 예: ['30대', '40대']"
    )
    target_gender: str | None = Field(default=None, description="타겟 성별: 'male' | 'female' | None(전체)")
    target_time_slots: list[str] = Field(
        default_factory=list,
        description="타겟 시간대 (빈 리스트=전체). 예: ['time_11_14', 'time_14_17']",
    )
    target_day_type: str | None = Field(default=None, description="타겟 요일: 'weekday' | 'weekend' | None(전체)")
    target_monthly_sales: int | None = Field(default=None, description="예상 월매출 (원). None=비율만 계산, 금액 제외")
