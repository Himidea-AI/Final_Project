"""
마포구 프랜차이즈 상권분석 시뮬레이터 — 비즈니스 상수
모든 하드코딩 값은 여기에서 관리. 코드 내 매직 넘버 사용 금지.
"""

# ── 마포구 행정동 (16개) ──
MAPO_DISTRICTS = [
    "아현동", "공덕동", "도화동", "용강동",
    "대흥동", "염리동", "신수동", "서교동",
    "합정동", "망원1동", "망원2동", "연남동",
    "성산1동", "성산2동", "상암동", "서강동",
]

# ── MVP 비교 대상 동 (3개) ──
MVP_TARGET_DISTRICTS = ["망원1동", "공덕동", "대흥동"]

# ── MVP 지원 업종 (3개) ──
SUPPORTED_BUSINESS_TYPES = {
    "cafe": {"name": "카페", "avg_ticket": 6500, "target_age": [20, 39]},
    "restaurant": {"name": "음식점", "avg_ticket": 12000, "target_age": [25, 54]},
    "convenience": {"name": "편의점", "avg_ticket": 5000, "target_age": [15, 59]},
}

# ── 시뮬레이션 설정 ──
SIMULATION_MONTHS = 12          # 시뮬레이션 기간 (개월)
DEFAULT_INITIAL_INVESTMENT = 150_000_000  # 기본 초기 투자금 (원)

# ── 경쟁 분석 가중치 ──
COMPETITION_WEIGHTS = {
    "direct": 1.0,              # 직접 경쟁 (동일 업종)
    "cannibalization": 1.5,     # 카니발리제이션 (동일 브랜드) — 가장 높은 가중치
    "indirect": 0.5,            # 간접 경쟁 (대체재: 배달 야식 등)
}

# ── 경쟁 반경 (미터) ──
COMPETITION_RADIUS = {
    "danger": 500,              # 500m 이내: 높은 자기 잠식 위험
    "caution": 1000,            # 500m~1km: 부분 잠식
    "safe": 1500,               # 1km 이상: 독립 상권
}

# ── LLM 설정 ──
LLM_MODEL = "claude-sonnet-4-20250514"
LLM_TIMEOUT = 10
LLM_MAX_RETRIES = 2

# ── 소상공인진흥공단 업종코드 체계 (2024년 개편: 837개 → 247개) ──
# 주의: 과거 업종코드/상가업소번호와 연계 불가 (신규 체계)
SEMAS_BUSINESS_CATEGORIES = {
    "대분류": {
        "Q01": "음식",
        "Q02": "소매",
        "Q03": "생활서비스",
        "Q04": "학문/교육",
        "Q05": "부동산",
        "Q06": "숙박",
        "Q07": "스포츠",
        "Q08": "관광/여가/오락",
        "Q09": "의료",
        "Q10": "수리/개인",
    },
    # 중분류 75개, 소분류 247개는 API 조회 시 동적 로드
    "중분류_count": 75,
    "소분류_count": 247,
}

# MVP에서 사용하는 소분류 업종코드 매핑
MVP_SEMAS_CODES = {
    "cafe": "Q01A01",       # 커피전문점/카페
    "restaurant": "Q01A02",  # 한식음식점 (대표값, 세부 업종은 입력 시 선택)
    "convenience": "Q02A01", # 편의점
}

# ── 모드 ──
DEMO_MODE = False               # True면 캐시된 데이터로 즉각 응답
