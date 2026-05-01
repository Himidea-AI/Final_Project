"""Operational Fit Score (OFS) — 동 단위 입지 매력도 종합 점수.

공식:
    OFS = 0.10 × subway_sub + 0.40 × bus_sub + 0.50 × fclty_sub
    각 서브점수는 마포 16동 min-max 정규화 (10~100, floor=10).

서브점수:
    A. subway_sub:
        raw = G(d, d₀) × 100 + subway_count_1km × 10
        G(d, d₀) = E2SFCA Gaussian decay (Luo & Qi 2009; Dai 2010)
                 = (exp(-0.5 × (d/d₀)²) - exp(-0.5)) / (1 - exp(-0.5))   if d < d₀
                 = 0                                                        if d ≥ d₀
        d₀ = 1000m

    B. bus_sub:
        raw = bus_sttn_co × 일평균_승하차
        (간이: bus_boarding_daily 평균 / 마포 정류장수)

    C. fclty_sub:
        raw = Σ (시설_개수 × 시설_가중치)
        가중치 (TOD 경험치 + Cervero 2002 elasticity 정신):
            종합병원/대학교/백화점 1.5
            극장 1.3
            유동인구시설/슈퍼마켓/고등 1.2
            중학교/초등학교 1.1
            공공청사/은행/숙박 1.0
            유치원/약국 0.8

가중치 캘리브레이션 (외부 OFS 보고서 인용):
    초기 휴리스틱 (TOD): 0.40 / 0.30 / 0.30 → R² = 0.33
    회귀 분석 (마포 16동 × 8분기 매출): 0.10 / 0.40 / 0.50 → R² = 0.55
    지하철 가중치 낮은 이유: 동 행정중심 좌표 기준이라 경계 환승역 반영 불가.

학술 근거:
    - Hansen (1959) JAIP 25(2):73-76 — 접근성 모델 골격
    - Luo & Qi (2009) Health & Place 15(4):1100-1107 — E2SFCA 본가
    - Dai (2010) — 가우시안 감쇠 함수 도입
    - Cervero (2002) Transportation Research Part D — 토지이용 elasticity

ABM 사용:
    runner.py 시뮬 시작 시 compute_ofs_scores() 호출 → World.ofs_dong_score 채움.
    score_store 의 OFS boost (Option E, role 별 차등) 가 자동 작동.
"""

from __future__ import annotations

import math
import os
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


load_dotenv()


# 14종 시설 가중치 (DB 컬럼명 → weight)
FCLTY_WEIGHTS: dict[str, float] = {
    "gehspt_co": 1.5,  # 종합병원
    "univ_co": 1.5,  # 대학교
    "drts_co": 1.5,  # 백화점
    "theat_co": 1.3,  # 극장
    "viatr_fclty_co": 1.2,  # 유동인구시설
    "supmk_co": 1.2,  # 슈퍼마켓
    "hgschl_co": 1.2,  # 고등학교
    "mskul_co": 1.1,  # 중학교
    "elesch_co": 1.1,  # 초등학교
    "pblofc_co": 1.0,  # 공공청사
    "bank_co": 1.0,  # 은행
    "stayng_fclty_co": 1.0,  # 숙박시설
    "kndrgr_co": 0.8,  # 유치원
    "parmacy_co": 0.8,  # 약국
}

# OFS 종합 가중치 (외부 회귀 분석 기반)
W_SUBWAY = 0.10
W_BUS = 0.40
W_FCLTY = 0.50

# E2SFCA Gaussian decay 파라미터
CATCHMENT_M = 1000.0  # 1km

# 정규화 파라미터
SCORE_MIN = 10
SCORE_MAX = 100


def _gaussian_decay(d_m: float, d0_m: float = CATCHMENT_M) -> float:
    """E2SFCA Gaussian decay (McGrail-Humphreys-style).

    G(d) = (exp(-0.5(d/d₀)²) - exp(-0.5)) / (1 - exp(-0.5))   if d < d₀
         = 0                                                   if d ≥ d₀
    """
    if d_m >= d0_m:
        return 0.0
    inner = math.exp(-0.5 * (d_m / d0_m) ** 2)
    base = math.exp(-0.5)
    denom = 1.0 - base
    return max(0.0, (inner - base) / denom)


def _minmax_normalize(values: dict[str, float]) -> dict[str, float]:
    """마포 16동 min-max → 10~100 (floor=10)."""
    if not values:
        return {}
    vmin = min(values.values())
    vmax = max(values.values())
    if vmax - vmin < 1e-9:
        return {k: SCORE_MIN for k in values}
    out = {}
    for k, v in values.items():
        out[k] = SCORE_MIN + (v - vmin) / (vmax - vmin) * (SCORE_MAX - SCORE_MIN)
    return out


def _load_subway_subscore(engine) -> dict[str, float]:
    """subway_sub raw — 마포 16동."""
    sql = text("""
        SELECT dong_name, subway_distance_m, subway_count_1km
        FROM dong_subway_access
        WHERE dong_code LIKE '1144%'
    """)
    out: dict[str, float] = {}
    with engine.connect() as c:
        for r in c.execute(sql).fetchall():
            d = float(r[1] or 9999)
            n = int(r[2] or 0)
            raw = _gaussian_decay(d) * 100 + n * 10
            out[r[0]] = raw
    return out


def _load_bus_subscore(engine) -> dict[str, float]:
    """bus_sub raw — 마포 16동.

    간이: 동내 정류장수 × 동 추정 평균 승하차.
    bus_boarding_daily 가 정류장 단위라 동 단위 매핑이 복잡 → 정류장수만 1차.
    추후 정밀화 시 정류장-동 매핑 + 일평균 결합.
    """
    # 1) seoul_adstrd_fclty 의 bus_sttn_co 활용 (동 단위 정류장수)
    sql = text("""
        SELECT dong_name, bus_sttn_co
        FROM seoul_adstrd_fclty
        WHERE dong_code LIKE '1144%'
          AND quarter = (SELECT MAX(quarter) FROM seoul_adstrd_fclty)
    """)
    out: dict[str, float] = {}
    with engine.connect() as c:
        for r in c.execute(sql).fetchall():
            n = float(r[1] or 0)
            # 마포 평균 승하차 약 50,000명/정류장/일 (간이 추정)
            out[r[0]] = n * 50000.0
    # 2) 가능하면 bus_boarding_daily 평균으로 보정
    try:
        sql2 = text("""
            SELECT AVG(daily_total) FROM (
                SELECT (board_count + alight_count) AS daily_total
                FROM bus_boarding_daily
                WHERE date >= (SELECT MAX(date) - 30 FROM bus_boarding_daily)
            ) sub
        """)
        with engine.connect() as c:
            avg_total = c.execute(sql2).scalar()
        if avg_total:
            # 정확한 일평균으로 다시 곱셈
            out = {k: (v / 50000.0) * float(avg_total) for k, v in out.items()}
    except Exception:
        pass
    return out


def _load_fclty_subscore(engine) -> dict[str, float]:
    """fclty_sub raw — 14종 가중합."""
    cols = list(FCLTY_WEIGHTS.keys())
    cols_sql = ", ".join(cols)
    sql = text(f"""
        SELECT dong_name, {cols_sql}
        FROM seoul_adstrd_fclty
        WHERE dong_code LIKE '1144%'
          AND quarter = (SELECT MAX(quarter) FROM seoul_adstrd_fclty)
    """)
    out: dict[str, float] = {}
    with engine.connect() as c:
        for r in c.execute(sql).mappings().fetchall():
            row = dict(r)
            raw = sum(float(row.get(col) or 0) * w for col, w in FCLTY_WEIGHTS.items())
            out[row["dong_name"]] = raw
    return out


def compute_ofs_scores(db_url: str | None = None) -> dict[str, float]:
    """마포 16동 OFS 종합 점수 계산.

    Returns:
        {dong_name: score 10~100}
    """
    url = db_url or os.environ["POSTGRES_URL"]
    engine = create_engine(url, isolation_level="AUTOCOMMIT")

    subway_raw = _load_subway_subscore(engine)
    bus_raw = _load_bus_subscore(engine)
    fclty_raw = _load_fclty_subscore(engine)

    # 각 서브점수 정규화 (10~100)
    subway = _minmax_normalize(subway_raw)
    bus = _minmax_normalize(bus_raw)
    fclty = _minmax_normalize(fclty_raw)

    # 종합 — 모든 동 합집합
    all_dongs = set(subway) | set(bus) | set(fclty)
    out: dict[str, float] = {}
    for d in all_dongs:
        s = subway.get(d, SCORE_MIN)
        b = bus.get(d, SCORE_MIN)
        f = fclty.get(d, SCORE_MIN)
        out[d] = round(W_SUBWAY * s + W_BUS * b + W_FCLTY * f, 2)
    return out


def compute_ofs_breakdown(db_url: str | None = None) -> dict[str, dict[str, float]]:
    """디버깅용 — 동별 서브점수 + 종합 분해 반환.

    Returns:
        {dong_name: {subway, bus, fclty, total}}
    """
    url = db_url or os.environ["POSTGRES_URL"]
    engine = create_engine(url, isolation_level="AUTOCOMMIT")

    subway = _minmax_normalize(_load_subway_subscore(engine))
    bus = _minmax_normalize(_load_bus_subscore(engine))
    fclty = _minmax_normalize(_load_fclty_subscore(engine))

    all_dongs = set(subway) | set(bus) | set(fclty)
    out: dict[str, dict[str, float]] = {}
    for d in all_dongs:
        s = subway.get(d, SCORE_MIN)
        b = bus.get(d, SCORE_MIN)
        f = fclty.get(d, SCORE_MIN)
        out[d] = {
            "subway": round(s, 2),
            "bus": round(b, 2),
            "fclty": round(f, 2),
            "total": round(W_SUBWAY * s + W_BUS * b + W_FCLTY * f, 2),
        }
    return out


def attach_ofs_to_world(world: Any, db_url: str | None = None, verbose: bool = False) -> int:
    """World.ofs_dong_score 에 16동 OFS 주입.

    Returns: 주입된 동 개수.
    """
    scores = compute_ofs_scores(db_url=db_url)
    world.ofs_dong_score = scores
    if verbose:
        top3 = sorted(scores.items(), key=lambda x: -x[1])[:3]
        print(f"  [loader] OFS 16동 주입 — top3: {top3}")
    return len(scores)
