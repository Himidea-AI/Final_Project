"""RDS 기반 개인화된 AgentProfile 생성기.

데이터 소스:
- living_population (최신 1개월, time_zone=14) → 동별 연령×성별 분포
- dong_subway_access → 동별 이동성 점수
- apt_trade_real (최근 거래, 단위면적당 가격) → 동별 경제 index
- naver_trend_industry → 카테고리별 트렌드 가중치

결과: 각 에이전트마다 고유한 경제/취향/이동/라이프스타일 프로필.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from .agents import Role

load_dotenv()


# ---------------------------------------------------------------
# AgentProfile
# ---------------------------------------------------------------
@dataclass
class AgentProfile:
    """한 에이전트의 개성 벡터 - 개인 의사결정에 반영.

    v2 (2026-04) 확장: occupation/family_size/schedule_type/diet_pref/shopping_freq/
    exercise_habit/health_bucket — 정책 scoring 에 반영되는 개인 특성 추가.
    """

    age: int
    gender: str  # M/F
    home_dong: str
    role: Role

    # 경제
    income_level: int  # 1(저)~3(고)
    daily_budget: float
    price_sensitivity: float  # 0(프리미엄)~1(가성비)

    # 이동
    mobility_score: float  # 0~1 (지하철 접근성)

    # 취향 가중치 (카테고리별 선호도 0~1)
    pref_cafe: float
    pref_restaurant: float
    pref_pub: float
    pref_convenience: float

    # 라이프스타일 태그 (LLM 프롬프트에 주입)
    lifestyle_tag: str

    # v2 — 개인 디테일 확장
    occupation: str = "직장인"  # 대학생/직장인/프리랜서/주부/은퇴자/자영업
    family_size: int = 2  # 1=혼자, 2=커플, 3+=가족
    has_kids: bool = False
    schedule_type: str = "아침형"  # 아침형 / 올빼미 / 유연
    diet_pref: str = "일반"  # 일반 / 채식 / 저칼로리 / 매운맛 / 건강식
    shopping_freq: float = 0.5  # 0(드묾)~1(자주) 외식/장보기 빈도
    exercise_habit: float = 0.3  # 0(안함)~1(매일) — 시간대 이동 패턴 영향
    car_ownership: bool = False
    archetype: str = "balanced_commuter"  # archetypes.py 의 키 (role 별 샘플)

    # Nemotron-Personas-Korea (NVIDIA, CC BY 4.0) 차용 필드 — Argyle 2023 joint distribution 개선용
    nemotron_occupation: str | None = None  # 통계청 기반 실제 직업 분포
    nemotron_family_type: str | None = None  # 39종 가구형태
    nemotron_persona: str | None = None  # 500토큰 자연어 서사 (Tier S 프롬프트용)
    name: str | None = None  # nemotron persona 본문에서 추출한 이름 (예: "안채승")

    def category_weights(self) -> dict[str, float]:
        return {
            "카페": self.pref_cafe,
            "음식점": self.pref_restaurant,
            "주점": self.pref_pub,
            "편의점": self.pref_convenience,
        }

    def short_summary(self) -> str:
        g = "남" if self.gender == "M" else "여"
        return (
            f"{self.home_dong} {self.age}세 {g}, "
            f"소득{self.income_level}/3, "
            f"{self.lifestyle_tag}, "
            f"가성비성향 {self.price_sensitivity:.1f}, "
            f"이동성 {self.mobility_score:.1f}"
        )


# ---------------------------------------------------------------
# 연령 버킷 (living_population 컬럼명과 일치)
# ---------------------------------------------------------------
# 주의: living_population 의 male_70_74/female_70_74 컬럼은 100% NULL (audit 2026-05-04).
#       male_70_plus/female_70_plus 만 실데이터 보유. 70대 통합 버킷("70_plus") 만 사용.
#       70_74/70_79 등 분리 버킷 추가 금지 — column 자체가 비어 있음.
AGE_BUCKETS = [
    ("20_24", 20, 24),
    ("25_29", 25, 29),
    ("30_34", 30, 34),
    ("35_39", 35, 39),
    ("40_44", 40, 44),
    ("45_49", 45, 49),
    ("50_54", 50, 54),
    ("55_59", 55, 59),
    ("60_64", 60, 64),
    ("65_69", 65, 69),
    ("70_plus", 70, 79),
]


# ---------------------------------------------------------------
# 라이프스타일 태그 결정 (연령 × 성별 × 동)
# ---------------------------------------------------------------
def _lifestyle_tag(age: int, gender: str, dong: str, role: Role) -> str:
    if role == Role.OWNER:
        return "자영업자"
    if role == Role.VISITOR:
        return "단기 방문객"
    if age < 25:
        return "대학생" if dong in ("서교동", "합정동", "신수동") else "사회초년생"
    if age < 35:
        return "20~30대 직장인" if role == Role.COMMUTER else "20~30대 1인가구"
    if age < 50:
        return "30~40대 가족" if dong in ("상암동", "성산1동", "성산2동", "망원2동") else "30~40대 직장인"
    if age < 65:
        return "중년 주민"
    return "시니어"


# ---------------------------------------------------------------
# ProfileBuilder - DB 쿼리 + 샘플링
# ---------------------------------------------------------------
class ProfileBuilder:
    def __init__(self, db_url: str | None = None, seed: int = 42):
        # pool_pre_ping=True — stale connection (RDS idle timeout / network blip) 자동 검출 + reconnect.
        # pool_recycle 1800 — 30분 마다 connection 강제 재생 (idle close 보호).
        self.engine = create_engine(
            db_url or os.environ["POSTGRES_URL"],
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        self.rng = random.Random(seed)
        self._cache: dict[str, dict] = {}

    # -----------------------------------------------------------
    # DB 로더 (1회 캐시)
    # -----------------------------------------------------------
    def load_dong_mix(self) -> dict[str, dict]:
        """동별 연령×성별 분포 + 총 인구."""
        if "dong_mix" in self._cache:
            return self._cache["dong_mix"]

        # COALESCE — male_70_74/female_70_74 가 100% NULL 이지만 AGE_BUCKETS 는
        # "70_plus" 만 사용하므로 영향 없음. 그래도 다른 _XX_XX 컬럼 NULL row 방어.
        sql = text(f"""
            SELECT dong_name,
                   {", ".join(f"AVG(COALESCE(male_{k},0)) m_{k}" for k, _, _ in AGE_BUCKETS)},
                   {", ".join(f"AVG(COALESCE(female_{k},0)) f_{k}" for k, _, _ in AGE_BUCKETS)},
                   AVG(total_pop) total_pop
            FROM living_population
            WHERE date >= (SELECT MAX(date) - 30 FROM living_population)
              AND time_zone = 14
            GROUP BY dong_name
        """)
        out: dict[str, dict] = {}
        with self.engine.connect() as c:
            for row in c.execute(sql).mappings():
                buckets = {}
                for k, _, _ in AGE_BUCKETS:
                    v_m = row.get(f"m_{k}") or 0.0
                    v_f = row.get(f"f_{k}") or 0.0
                    if v_m > 0:
                        buckets[("M", k)] = float(v_m)
                    if v_f > 0:
                        buckets[("F", k)] = float(v_f)
                out[row["dong_name"]] = {
                    "buckets": buckets,
                    "total_pop": float(row["total_pop"] or 0),
                }
        self._cache["dong_mix"] = out
        return out

    def load_mobility(self) -> dict[str, float]:
        if "mobility" in self._cache:
            return self._cache["mobility"]
        with self.engine.connect() as c:
            rows = c.execute(text("SELECT dong_name, subway_distance_m FROM dong_subway_access")).fetchall()
        if not rows:
            self._cache["mobility"] = {}
            return {}
        max_d = max(r[1] for r in rows) or 1.0
        # 거리 반비례 + 0.2~1.0 범위
        out = {r[0]: round(0.2 + 0.8 * (1.0 - r[1] / max_d), 3) for r in rows}
        self._cache["mobility"] = out
        return out

    def load_rent_index(self) -> dict[str, float]:
        """apt_trade_real 최근 거래의 단위면적 가격 → 0~1 normalized.

        매핑 정책 (2026-05-04 강화):
          - 마포 16동 모두 명시 매핑 (망원2동/성산2동 누락 fix).
          - region_full 에 행정동 번호 존재 시 우선 (예: '망원2동' → 망원2동).
          - 매핑 실패 동은 인접 동 평균으로 fallback (income 0.5 default 회피).
        """
        if "rent" in self._cache:
            return self._cache["rent"]
        # 인접 동 (지리적 근접) — ILIKE 매칭 누락 시 평균 fallback 용.
        # 동명 약어 ILIKE 가 망원2동 / 성산2동 과 같은 번호 동을 1동에만 귀속시키는 문제 보완.
        neighbor_groups = {
            "망원1동": ["망원2동", "합정동", "서교동"],
            "망원2동": ["망원1동", "성산1동", "성산2동"],
            "성산1동": ["성산2동", "망원2동", "상암동"],
            "성산2동": ["성산1동", "연남동"],
            "공덕동": ["아현동", "도화동", "용강동"],
            "아현동": ["공덕동", "대흥동", "염리동"],
            "도화동": ["공덕동", "용강동"],
            "용강동": ["공덕동", "도화동"],
            "대흥동": ["아현동", "염리동", "신수동"],
            "염리동": ["대흥동", "아현동"],
            "신수동": ["대흥동", "서강동"],
            "서강동": ["신수동", "서교동"],
            "서교동": ["합정동", "연남동", "서강동"],
            "합정동": ["서교동", "망원1동"],
            "연남동": ["서교동", "성산2동"],
            "상암동": ["성산1동"],
        }
        # 망원2동 / 성산2동 도 region_full 에 직접 적시되는 경우 우선 매핑.
        sql = text("""
            SELECT
              CASE
                WHEN region_full ILIKE '%망원2%' OR region_full ILIKE '%망원 2%' THEN '망원2동'
                WHEN region_full ILIKE '%망원1%' OR region_full ILIKE '%망원 1%' THEN '망원1동'
                WHEN region_full ILIKE '%성산2%' OR region_full ILIKE '%성산 2%' THEN '성산2동'
                WHEN region_full ILIKE '%성산1%' OR region_full ILIKE '%성산 1%' THEN '성산1동'
                WHEN region_full ILIKE '%서교%' THEN '서교동'
                WHEN region_full ILIKE '%연남%' THEN '연남동'
                WHEN region_full ILIKE '%합정%' THEN '합정동'
                WHEN region_full ILIKE '%상암%' THEN '상암동'
                WHEN region_full ILIKE '%공덕%' THEN '공덕동'
                WHEN region_full ILIKE '%도화%' THEN '도화동'
                WHEN region_full ILIKE '%용강%' THEN '용강동'
                WHEN region_full ILIKE '%망원%' THEN '망원1동'
                WHEN region_full ILIKE '%신수%' THEN '신수동'
                WHEN region_full ILIKE '%대흥%' THEN '대흥동'
                WHEN region_full ILIKE '%염리%' THEN '염리동'
                WHEN region_full ILIKE '%아현%' THEN '아현동'
                WHEN region_full ILIKE '%성산%' THEN '성산1동'
                WHEN region_full ILIKE '%서강%' THEN '서강동'
                ELSE NULL
              END dong,
              AVG(price_won::double precision / NULLIF(area_sqm, 0)) avg_p
            FROM apt_trade_real
            WHERE deal_ym >= '2024' AND price_won > 0 AND area_sqm > 0
            GROUP BY 1
            HAVING AVG(price_won::double precision / NULLIF(area_sqm, 0)) IS NOT NULL
        """)
        with self.engine.connect() as c:
            rows = c.execute(sql).fetchall()
        valid = [(r[0], r[1]) for r in rows if r[0] and r[1]]
        if not valid:
            self._cache["rent"] = {}
            return {}
        # 1) 매핑된 동 → 가격
        raw = {d: float(v) for d, v in valid}
        # 2) 인접 동 평균 fallback — 매핑 실패한 마포 16동에 대해 보완
        from .config import MAPO_DONGS

        for dong in MAPO_DONGS:
            if dong in raw:
                continue
            neighbors = [raw[n] for n in neighbor_groups.get(dong, []) if n in raw]
            if neighbors:
                raw[dong] = sum(neighbors) / len(neighbors)
        # 3) 정규화 (전체 평균 활용)
        mn = min(raw.values())
        mx = max(raw.values())
        out = {d: round((v - mn) / (mx - mn), 3) if mx > mn else 0.5 for d, v in raw.items()}
        self._cache["rent"] = out
        return out

    def load_category_trend(self) -> dict[str, float]:
        """카테고리별 네이버 트렌드 평균 (최신 12개월)."""
        if "trend" in self._cache:
            return self._cache["trend"]
        sql = text("""
            SELECT industry, AVG(ratio) avg_r
            FROM naver_trend_industry
            WHERE period >= (SELECT MAX(period) - INTERVAL '12 months' FROM naver_trend_industry)
            GROUP BY industry
        """)
        with self.engine.connect() as c:
            rows = c.execute(sql).fetchall()
        # 업종 → 우리 카테고리 매핑
        mapping = {
            "카페": "카페",
            "커피": "카페",
            "디저트": "카페",
            "한식": "음식점",
            "양식": "음식점",
            "일식": "음식점",
            "중식": "음식점",
            "치킨": "음식점",
            "분식": "음식점",
            "주점": "주점",
            "호프": "주점",
            "편의점": "편의점",
        }
        buckets: dict[str, list[float]] = {}
        for industry, avg_r in rows:
            cat = next((v for k, v in mapping.items() if k in (industry or "")), None)
            if cat:
                buckets.setdefault(cat, []).append(float(avg_r or 0))
        out = {cat: round(sum(vs) / len(vs), 3) for cat, vs in buckets.items() if vs}
        # 기본값 (데이터 없으면 균등)
        for cat in ("카페", "음식점", "주점", "편의점"):
            out.setdefault(cat, 50.0)
        # 0.4~0.8 범위로 정규화 (카테고리간 차이 보존 + clamp 방지)
        mx = max(out.values()) or 1.0
        mn = min(out.values())
        rng = mx - mn if mx > mn else 1.0
        out = {k: round(0.4 + 0.4 * (v - mn) / rng, 3) for k, v in out.items()}
        self._cache["trend"] = out
        return out

    # -----------------------------------------------------------
    # 핵심: 1명분 샘플링
    # -----------------------------------------------------------
    def sample_profile(self, role: Role) -> AgentProfile:
        dong_mix = self.load_dong_mix()
        mobility = self.load_mobility()
        rent = self.load_rent_index()
        trend = self.load_category_trend()

        # 1) 동 샘플링 (total_pop 가중)
        dongs = list(dong_mix.keys())
        weights = [dong_mix[d]["total_pop"] for d in dongs]
        home_dong = self.rng.choices(dongs, weights=weights)[0]

        # 2) 연령×성별 샘플링 (동별 실제 분포)
        buckets = dong_mix[home_dong]["buckets"]
        if not buckets:
            gender, age = self.rng.choice(["M", "F"]), self.rng.randint(25, 45)
        else:
            keys = list(buckets.keys())
            bw = [buckets[k] for k in keys]
            chosen = self.rng.choices(keys, weights=bw)[0]
            gender, bucket_key = chosen
            # bucket_key → 실제 연령 범위 내 랜덤
            bk = next(b for b in AGE_BUCKETS if b[0] == bucket_key)
            age = self.rng.randint(bk[1], bk[2])

        # 3) 소득 level (rent index + 연령 보정)
        rent_score = rent.get(home_dong, 0.5)
        age_boost = 0.3 if 30 <= age <= 55 else 0.0
        income_raw = rent_score + age_boost + self.rng.uniform(-0.15, 0.15)
        if income_raw < 0.35:
            income_level = 1
        elif income_raw < 0.7:
            income_level = 2
        else:
            income_level = 3
        daily_budget = {1: 20000, 2: 40000, 3: 80000}[income_level] * self.rng.uniform(0.8, 1.3)

        # 4) 가성비 성향 (소득 역상관 + 연령 보정)
        price_sensitivity = max(
            0.0,
            min(1.0, 1.0 - income_level / 3.0 + (0.2 if age > 50 else 0.0) + self.rng.uniform(-0.1, 0.1)),
        )

        # 5) 이동성 점수 (동 기반)
        mobility_score = mobility.get(home_dong, 0.5)

        # 6) 카테고리 취향 (트렌드 + 연령 보정)
        def age_boost_cat(cat: str) -> float:
            if cat == "카페" and 20 <= age <= 35:
                return 0.25
            if cat == "주점" and 20 <= age <= 40:
                return 0.2
            if cat == "편의점" and (age < 25 or age > 55):
                return 0.15
            if cat == "음식점" and age >= 40:
                return 0.15
            return 0.0

        def prefs(cat: str) -> float:
            base = trend.get(cat, 0.5)
            return max(0.0, min(1.0, base + age_boost_cat(cat) + self.rng.uniform(-0.15, 0.15)))

        pref_cafe = prefs("카페")
        pref_restaurant = prefs("음식점")
        pref_pub = prefs("주점")
        pref_cvs = prefs("편의점")

        tag = _lifestyle_tag(age, gender, home_dong, role)

        # v2 확장 필드 — 인구통계 기반 파생
        # 직업 — age × role × lifestyle_tag
        if role.value == "owner":
            occupation = "자영업"
        elif tag == "대학생":
            occupation = "대학생"
        elif age >= 65:
            occupation = "은퇴자"
        elif gender == "F" and age in range(30, 45) and self.rng.random() < 0.15:
            occupation = "주부"
        elif self.rng.random() < 0.1:
            occupation = "프리랜서"
        else:
            occupation = "직장인"

        # 가구 크기 — age × 결혼 연령 근사
        if age < 28:
            family_size = self.rng.choices([1, 2, 3], weights=[0.6, 0.25, 0.15])[0]
        elif age < 40:
            family_size = self.rng.choices([1, 2, 3, 4], weights=[0.3, 0.35, 0.2, 0.15])[0]
        elif age < 55:
            family_size = self.rng.choices([1, 2, 3, 4], weights=[0.1, 0.3, 0.3, 0.3])[0]
        else:
            family_size = self.rng.choices([1, 2, 3], weights=[0.2, 0.55, 0.25])[0]
        has_kids = family_size >= 3 and 25 <= age <= 55

        # 스케줄 타입 — age × occupation
        if occupation == "대학생":
            schedule_type = self.rng.choice(["올빼미", "유연"])
        elif occupation in ("은퇴자", "주부"):
            schedule_type = "아침형"
        elif age < 35 and occupation == "직장인":
            schedule_type = self.rng.choices(["아침형", "올빼미", "유연"], weights=[0.4, 0.3, 0.3])[0]
        else:
            schedule_type = self.rng.choices(["아침형", "유연"], weights=[0.7, 0.3])[0]

        # 식사 선호 — age × income × 일반 분포
        diet_options = ["일반", "채식", "저칼로리", "매운맛", "건강식"]
        if age >= 50 and income_level >= 2:
            diet_weights = [0.3, 0.05, 0.2, 0.05, 0.4]
        elif age < 30:
            diet_weights = [0.5, 0.08, 0.1, 0.25, 0.07]
        else:
            diet_weights = [0.55, 0.07, 0.13, 0.15, 0.1]
        diet_pref = self.rng.choices(diet_options, weights=diet_weights)[0]

        # 외식/쇼핑 빈도 — income × age × family (혼자=높음, 가족=낮음)
        base_shop = 0.3 + (income_level - 1) * 0.15
        if family_size == 1:
            base_shop += 0.15
        elif family_size >= 4:
            base_shop -= 0.1
        if age < 30:
            base_shop += 0.1
        shopping_freq = max(0.05, min(1.0, base_shop + self.rng.uniform(-0.1, 0.1)))

        # 운동 습관 — age 역상관 + 랜덤
        base_ex = 0.4 - (max(0, age - 30) / 100) + self.rng.uniform(-0.15, 0.2)
        exercise_habit = max(0.0, min(1.0, base_ex))

        # 차량 보유 — age × income × family
        car_p = 0.2 + (income_level - 1) * 0.2 + (0.15 if family_size >= 3 else 0) + (0.1 if age >= 35 else -0.1)
        car_ownership = self.rng.random() < max(0.0, min(0.9, car_p))

        # Archetype 샘플 — role × age × income 분포
        from .archetypes import sample_archetype

        archetype = sample_archetype(role.value, self.rng, age=age, income_level=income_level)

        profile = AgentProfile(
            age=age,
            gender=gender,
            home_dong=home_dong,
            role=role,
            income_level=income_level,
            daily_budget=round(daily_budget, 0),
            price_sensitivity=round(price_sensitivity, 3),
            mobility_score=mobility_score,
            pref_cafe=round(pref_cafe, 3),
            pref_restaurant=round(pref_restaurant, 3),
            pref_pub=round(pref_pub, 3),
            pref_convenience=round(pref_cvs, 3),
            lifestyle_tag=tag,
            occupation=occupation,
            family_size=family_size,
            has_kids=has_kids,
            schedule_type=schedule_type,
            diet_pref=diet_pref,
            shopping_freq=round(shopping_freq, 3),
            exercise_habit=round(exercise_habit, 3),
            car_ownership=car_ownership,
            archetype=archetype,
        )
        # Nemotron feature 주입 (cache 있으면 보정, 없으면 no-op)
        self._attach_nemotron_features(profile)
        return profile

    def sample_many(self, counts: dict[Role, int]) -> list[AgentProfile]:
        """role별 count만큼 sample."""
        out: list[AgentProfile] = []
        for role, n in counts.items():
            for _ in range(n):
                out.append(self.sample_profile(role))
        return out

    # -----------------------------------------------------------
    # Nemotron-Personas-Korea (NVIDIA, CC BY 4.0) feature 보정
    # -----------------------------------------------------------
    def load_nemotron(self):
        """마포구 Nemotron parquet 로드 (캐시).

        없으면 None 반환 → _attach_nemotron_features() 는 no-op.
        scripts/load_nemotron_personas.py 로 선행 다운로드 필요.
        """
        if "nemotron" in self._cache:
            return self._cache["nemotron"]
        path = Path(__file__).resolve().parents[3] / "data/processed/nemotron_personas_mapo.parquet"
        if not path.exists():
            self._cache["nemotron"] = None
            return None
        try:
            import pandas as pd

            df = pd.read_parquet(path)
            self._cache["nemotron"] = df
            print(f"[loader] Nemotron 마포구 persona {len(df):,}건 로드 ({path.name})")
            return df
        except Exception as e:
            print(f"[loader] Nemotron 로드 실패 — fallback: {e}")
            self._cache["nemotron"] = None
            return None

    def _attach_nemotron_features(self, profile: "AgentProfile") -> None:
        """Nemotron 레코드에서 feature 추출해 profile 보정.

        매핑 규칙:
        - family_type (39종) → family_size, has_kids
        - occupation → nemotron_occupation 기록 (통계청 기반)
        - hobbies_and_interests_list → pref_cafe/pref_pub/exercise_habit 조정 (keyword boost)
        - education_level × occupation → income_level 재평가
        - housing_type → car_ownership 보정
        - persona (500토큰) → nemotron_persona (Tier S 프롬프트용)

        학술 근거:
        - Argyle et al. (2023) Political Analysis — 합성 persona joint distribution 개선
        - Park et al. (2023) UIST — 자연어 배경이 LLM 에이전트 리얼리즘 향상
        """
        df = self.load_nemotron()
        if df is None or len(df) == 0:
            return
        gender_kr = "남자" if profile.gender == "M" else "여자"
        mask = (
            (df["age"] >= max(19, profile.age - 3)) & (df["age"] <= min(99, profile.age + 3)) & (df["sex"] == gender_kr)
        )
        candidates = df[mask]
        if len(candidates) == 0:
            return
        record = candidates.sample(1, random_state=self.rng.randint(0, 10**9)).iloc[0]

        # family_type → family_size, has_kids (39종 joint distribution)
        ft = str(record.get("family_type") or "")
        if "배우자·자녀" in ft:
            profile.family_size = 3 + (1 if "3세대" in ft else 0)
            profile.has_kids = True
        elif "자녀와 거주" in ft:
            profile.family_size = 2
            profile.has_kids = True
        elif "혼자 거주" in ft:
            profile.family_size = 1
            profile.has_kids = False
        elif "배우자와 거주" in ft:
            profile.family_size = 2
            profile.has_kids = False

        # occupation 기록 (로컬 occupation 은 그대로 유지, 참조용 필드에 저장)
        profile.nemotron_occupation = str(record.get("occupation") or "") or None
        profile.nemotron_family_type = ft or None

        # hobbies → pref_* 조정 (keyword hit per hobby)
        hobbies_raw = record.get("hobbies_and_interests_list")
        hobbies: list[str] = []
        if hobbies_raw is not None:
            try:
                hobbies = list(hobbies_raw)
            except TypeError:
                hobbies = []
        hobbies_str = " ".join(str(h) for h in hobbies)
        cafe_kw = ["카페", "커피", "브런치", "베이커리", "독서", "디저트"]
        pub_kw = ["맥주", "와인", "술", "펍", "칵테일", "위스키"]
        exer_kw = ["운동", "헬스", "등산", "러닝", "요가", "수영", "자전거"]
        cafe_hits = sum(1 for k in cafe_kw if k in hobbies_str)
        pub_hits = sum(1 for k in pub_kw if k in hobbies_str)
        exer_hits = sum(1 for k in exer_kw if k in hobbies_str)
        profile.pref_cafe = round(max(0.0, min(1.0, profile.pref_cafe + 0.08 * cafe_hits)), 3)
        profile.pref_pub = round(max(0.0, min(1.0, profile.pref_pub + 0.08 * pub_hits)), 3)
        profile.exercise_habit = round(max(0.0, min(1.0, profile.exercise_habit + 0.1 * exer_hits)), 3)

        # education × occupation → income_level 재평가 (Nemotron 이 통계청 기반이라 신뢰도 높음)
        edu = str(record.get("education_level") or "")
        occ = str(record.get("occupation") or "")
        if edu == "대학원" or "박사" in edu:
            profile.income_level = 3
        elif "대학교" in edu and "컨설턴트" in occ or "전문가" in occ:
            profile.income_level = max(profile.income_level, 3)
        elif edu == "초등학교" or occ == "무직":
            profile.income_level = 1

        # housing_type → car 보정
        housing = str(record.get("housing_type") or "")
        if "아파트" in housing and self.rng.random() < 0.4:
            profile.car_ownership = True
        elif "단독" in housing and self.rng.random() < 0.3:
            profile.car_ownership = True

        # 자연어 persona 저장 (Tier S LLM 프롬프트용, 500자 제한)
        persona_text = str(record.get("persona") or "")
        if persona_text:
            profile.nemotron_persona = persona_text[:500]
        # 이름 추출 — persona 본문 시작 패턴 "<name> 씨는" / "<name> 씨 ".
        # nemotron 데이터셋이 한국어 인명 + " 씨" 로 자연어 시작. 정규식 first match.
        # 길이 2~4자 (한국 이름 보편) 만 허용 — 오추출 방지.
        import re as _re

        for src in (persona_text, str(record.get("professional_persona") or "")):
            m = _re.match(r"\s*([가-힣]{2,4})\s*씨", src)
            if m:
                profile.name = m.group(1)
                break

    # -----------------------------------------------------------
    # 실데이터 기반 시간×동×연령×요일 가중치
    # -----------------------------------------------------------
    def load_time_age_boost(self) -> dict:
        """실데이터 → (age_group, dong, hour, is_weekend_flag) boost.

        v2 (2026-04): living_population_grid (24h × 3년치) 우선, 실패 시 legacy living_population fallback.
            격자 데이터를 동 단위로 집계하되 시간 해상도는 24h 그대로 유지 → 6시간대 zone 보정 제거.
            요일 차원은 평일(0)/주말(1) 2값으로 축소 → peak hour 일치율 개선 목표.
        """
        if "time_age_boost" in self._cache:
            return self._cache["time_age_boost"]

        try:
            grid_boost = self._load_time_age_boost_from_grid()
            if grid_boost:
                self._cache["time_age_boost"] = grid_boost
                print(f"[loader] time_age_boost (grid) {len(grid_boost):,}개 항목 (24h × 평일/주말)")
                return grid_boost
        except Exception as e:
            print(f"[loader] grid-boost 로드 실패, legacy fallback: {e}")

        # 연령그룹 정의 (컬럼 직접 합산)
        groups_sql = {
            "20s": "male_20_24 + male_25_29 + female_20_24 + female_25_29",
            "30s": "male_30_34 + male_35_39 + female_30_34 + female_35_39",
            "40s": "male_40_44 + male_45_49 + female_40_44 + female_45_49",
            "50s": "male_50_54 + male_55_59 + female_50_54 + female_55_59",
            "60+": "male_60_64 + male_65_69 + male_70_plus + female_60_64 + female_65_69 + female_70_plus",
        }
        cols = ", ".join(f"AVG(COALESCE({expr},0)) g_{name.replace('+', 'plus')}" for name, expr in groups_sql.items())

        sql = text(f"""
            SELECT dong_name, time_zone,
                   EXTRACT(DOW FROM date)::int dow,
                   {cols}
            FROM living_population
            WHERE date >= (SELECT MAX(date) - 60 FROM living_population)
            GROUP BY dong_name, time_zone, dow
        """)

        rows = []
        with self.engine.connect() as c:
            for row in c.execute(sql).mappings():
                rows.append(dict(row))

        if not rows:
            self._cache["time_age_boost"] = {}
            return {}

        # (group, dong) 전체 평균
        from collections import defaultdict

        by_group_dong: dict[tuple[str, str], list[float]] = defaultdict(list)
        raw: dict[tuple[str, str, int, int], float] = {}
        for r in rows:
            for g_name in groups_sql:
                key = f"g_{g_name.replace('+', 'plus')}"
                v = float(r.get(key) or 0)
                if v > 0:
                    by_group_dong[(g_name, r["dong_name"])].append(v)
                    raw[(g_name, r["dong_name"], int(r["time_zone"]), int(r["dow"]))] = v

        # 평균 대비 비율
        mean_gd = {k: (sum(vs) / len(vs)) for k, vs in by_group_dong.items() if vs}
        boost: dict = {}
        for (g, d, tz, dow), v in raw.items():
            base = mean_gd.get((g, d))
            if not base or base <= 0:
                continue
            ratio = v / base
            # 0.5~2.0로 클램프
            ratio = max(0.5, min(2.0, ratio))
            # time_zone → 해당 시간대 전체에 적용 (6시는 6~10, 11은 11~13, 14는 14~16, 17은 17~19, 20은 20~23, 24는 0~5/24~25)
            hour_ranges = {
                6: list(range(6, 11)),
                11: list(range(11, 14)),
                14: list(range(14, 17)),
                17: list(range(17, 20)),
                20: list(range(20, 24)),
                24: list(range(0, 6)) + list(range(24, 26)),
            }
            for h in hour_ranges.get(tz, [tz]):
                # DOW: PostgreSQL은 일=0, 우리 weekday는 월=0 → 변환
                py_weekday = (dow - 1) % 7  # dow 1=월 → py 0
                if dow == 0:  # 일요일
                    py_weekday = 6
                boost[(g, d, h, py_weekday)] = round(ratio, 3)

        self._cache["time_age_boost"] = boost
        print(f"[loader] time_age_boost {len(boost):,}개 항목 계산 (실 생활인구 기반)")
        return boost

    def _load_time_age_boost_from_grid(self) -> dict:
        """living_population_grid (384 cells × 24h × 3년) → 동 집계 boost.

        반환: {(age_group, dong_name, hour, is_weekend): ratio} — ratio 0.5~2.0.
        """
        # 마포 동코드 ↔ 이름 — 격자 테이블은 code 만, boost key 는 name 필요
        from collections import defaultdict

        dong_code_to_name: dict[str, str] = {}
        with self.engine.connect() as c:
            for r in c.execute(
                text("SELECT DISTINCT dong_code, dong_name FROM living_population WHERE dong_code LIKE '1144%'")
            ).fetchall():
                dong_code_to_name[str(r[0])] = str(r[1])

        if not dong_code_to_name:
            return {}

        # 격자 → 동 시간별 연령대 집계. DOW 7분리 유지 (PostgreSQL: 일=0, 월=1, ..., 토=6).
        # 해상도: 24h × 7요일 — legacy 의 6 time-zone × 7요일보다 4배 세밀.
        sql = text("""
            SELECT dong_code,
                   tt,
                   EXTRACT(DOW FROM ymd)::int AS dow,
                   AVG(COALESCE(m_20_24,0)+COALESCE(m_25_29,0)+COALESCE(f_20_24,0)+COALESCE(f_25_29,0)) g_20s,
                   AVG(COALESCE(m_30_34,0)+COALESCE(m_35_39,0)+COALESCE(f_30_34,0)+COALESCE(f_35_39,0)) g_30s,
                   AVG(COALESCE(m_40_44,0)+COALESCE(m_45_49,0)+COALESCE(f_40_44,0)+COALESCE(f_45_49,0)) g_40s,
                   AVG(COALESCE(m_50_54,0)+COALESCE(m_55_59,0)+COALESCE(f_50_54,0)+COALESCE(f_55_59,0)) g_50s,
                   AVG(COALESCE(m_60_64,0)+COALESCE(m_65_69,0)+COALESCE(m_70_plus,0)
                       +COALESCE(f_60_64,0)+COALESCE(f_65_69,0)+COALESCE(f_70_plus,0)) g_60p
            FROM living_population_grid
            WHERE dong_code LIKE '1144%'
              AND ymd >= (SELECT MAX(ymd) - 365 FROM living_population_grid)
            GROUP BY dong_code, tt, dow
        """)
        rows: list[dict] = []
        with self.engine.connect() as c:
            for r in c.execute(sql).mappings():
                rows.append(dict(r))

        if not rows:
            return {}

        # (age_group, dong) 평균 기준 정규화
        groups = ["20s", "30s", "40s", "50s", "60+"]
        group_col = {"20s": "g_20s", "30s": "g_30s", "40s": "g_40s", "50s": "g_50s", "60+": "g_60p"}

        by_group_dong: dict[tuple, list[float]] = defaultdict(list)
        raw: dict[tuple, float] = {}
        for r in rows:
            dong_name = dong_code_to_name.get(str(r["dong_code"]))
            if not dong_name:
                continue
            tt = int(r["tt"])
            dow = int(r["dow"])  # 0=일, 1=월, ..., 6=토 (PostgreSQL)
            for g in groups:
                v = float(r.get(group_col[g]) or 0)
                if v > 0:
                    by_group_dong[(g, dong_name)].append(v)
                    raw[(g, dong_name, tt, dow)] = v

        mean_gd = {k: (sum(vs) / len(vs)) for k, vs in by_group_dong.items() if vs}
        boost: dict = {}
        for (g, d, tt, dow), v in raw.items():
            base = mean_gd.get((g, d))
            if not base or base <= 0:
                continue
            ratio = v / base
            ratio = max(0.5, min(2.0, ratio))
            # PostgreSQL DOW (일=0) → ABM py_weekday (월=0): py = (dow - 1) % 7, 일요일 dow=0 → py=6
            py_weekday = 6 if dow == 0 else dow - 1
            boost[(g, d, tt, py_weekday)] = round(ratio, 3)
        return boost

    # -----------------------------------------------------------
    # seoul_adstrd_flpop 기반 동×시간×요일 안정 평균 boost
    # (분기 단위 안정 데이터, 16동 전체 커버, time_age_boost 보완용)
    # -----------------------------------------------------------
    def load_adstrd_flpop_boost(self) -> dict:
        """seoul_adstrd_flpop 최신 quarter → (dong_name, hour, weekday) → ratio.

        시간 6구간 (00-06, 06-11, 11-14, 14-17, 17-21, 21-24) × 요일 7개.
        각 hour 는 자기 구간의 동별 ratio (동 평균 대비) 로 매핑됨.
        반환 ratio 는 0.5~2.0 클램프, 동별 평균=1.0.

        Returns:
            {(dong_name, hour, weekday): ratio float}
        """
        if "adstrd_flpop_boost" in self._cache:
            return self._cache["adstrd_flpop_boost"]

        sql = text("""
            SELECT dong_name,
                   time_00_06, time_06_11, time_11_14, time_14_17, time_17_21, time_21_24,
                   mon, tue, wed, thu, fri, sat, sun
            FROM seoul_adstrd_flpop
            WHERE dong_code LIKE '1144%'
              AND quarter = (SELECT MAX(quarter) FROM seoul_adstrd_flpop)
        """)
        with self.engine.connect() as c:
            rows = list(c.execute(sql).mappings())

        if not rows:
            self._cache["adstrd_flpop_boost"] = {}
            return {}

        # 시간 구간 → hour 매핑
        time_hours = {
            "time_00_06": list(range(0, 6)),
            "time_06_11": list(range(6, 11)),
            "time_11_14": list(range(11, 14)),
            "time_14_17": list(range(14, 17)),
            "time_17_21": list(range(17, 21)),
            "time_21_24": list(range(21, 24)),
        }
        weekday_cols = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

        boost: dict = {}
        for r in rows:
            dong = r["dong_name"]
            # 시간 구간 ratio (동별 평균 대비)
            time_vals = [float(r[k] or 0) for k in time_hours]
            t_mean = sum(time_vals) / max(len(time_vals), 1)
            # 요일 ratio
            wd_vals = [float(r[k] or 0) for k in weekday_cols]
            w_mean = sum(wd_vals) / max(len(wd_vals), 1)

            for tk_idx, (tk, hours) in enumerate(time_hours.items()):
                tval = float(r[tk] or 0)
                tr = tval / t_mean if t_mean > 0 else 1.0
                tr = max(0.5, min(2.0, tr))
                for h in hours:
                    for wd_idx, wd_col in enumerate(weekday_cols):
                        wval = float(r[wd_col] or 0)
                        wr = wval / w_mean if w_mean > 0 else 1.0
                        wr = max(0.5, min(2.0, wr))
                        # time × weekday 결합 (기하평균으로 절제 — 둘 다 영향받지만 폭발 방지)
                        combined = (tr * wr) ** 0.5
                        combined = max(0.5, min(2.0, combined))
                        boost[(dong, h, wd_idx)] = round(combined, 3)

        self._cache["adstrd_flpop_boost"] = boost
        print(f"[loader] adstrd_flpop_boost {len(boost):,}개 항목 (16동 × 24h × 7요일, 분기 안정 평균)")
        return boost


def age_to_group(age: int) -> str:
    """연령 → time_age_boost 키."""
    if age < 30:
        return "20s"
    if age < 40:
        return "30s"
    if age < 50:
        return "40s"
    if age < 60:
        return "50s"
    return "60+"
