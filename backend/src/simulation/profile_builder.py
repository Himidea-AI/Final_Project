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

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from .agents import Role

load_dotenv()


# ---------------------------------------------------------------
# AgentProfile
# ---------------------------------------------------------------
@dataclass
class AgentProfile:
    """한 에이전트의 개성 벡터 - 개인 의사결정에 반영."""

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
        self.engine = create_engine(
            db_url or os.environ["POSTGRES_URL"],
            isolation_level="AUTOCOMMIT",
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

        sql = text(f"""
            SELECT dong_name,
                   {", ".join(f"AVG(male_{k}) m_{k}" for k, _, _ in AGE_BUCKETS)},
                   {", ".join(f"AVG(female_{k}) f_{k}" for k, _, _ in AGE_BUCKETS)},
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
        """apt_trade_real 최근 거래의 단위면적 가격 → 0~1 normalized."""
        if "rent" in self._cache:
            return self._cache["rent"]
        sql = text("""
            SELECT
              CASE
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
        mn = min(v for _, v in valid)
        mx = max(v for _, v in valid)
        out = {d: round((v - mn) / (mx - mn), 3) if mx > mn else 0.5 for d, v in valid}
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

        return AgentProfile(
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
        )

    def sample_many(self, counts: dict[Role, int]) -> list[AgentProfile]:
        """role별 count만큼 sample."""
        out: list[AgentProfile] = []
        for role, n in counts.items():
            for _ in range(n):
                out.append(self.sample_profile(role))
        return out

    # -----------------------------------------------------------
    # 실데이터 기반 시간×동×연령×요일 가중치
    # -----------------------------------------------------------
    def load_time_age_boost(self) -> dict:
        """living_population 최신 60일 → (age_group, dong, hour, weekday) boost.

        방식:
        - 각 (연령그룹 × 동)의 전체 평균 인구를 기준(1.0)으로 해서
          (연령그룹, 동, 시간대, 요일)의 상대비를 0.5~2.0 범위로 정규화.
        - 예: 상암동 30대가 평일 14시에 평균 1.8배 → 오피스 유입 반영.
              서교동 20대가 금요일 20시에 평균 2.2배 → 홍대 금요일 저녁.
        """
        if "time_age_boost" in self._cache:
            return self._cache["time_age_boost"]

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
