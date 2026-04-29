"""
inflow_scorer — 후보 행정동의 교통·집객 접근성 점수 서비스

레퍼런스 체인:
- Hansen, W.G. (1959). How Accessibility Shapes Land Use. JAPA — gravity accessibility 이론 골격
- McGrail & Humphreys (2009). E2SFCA — Gaussian 거리감쇠 함수
- Networks and Spatial Economics (Springer 2025). Hansen's Accessibility Theory and ML: a Potential Merger
- 대한산업공학회지 (2024). 공공데이터·XAI 자영업 상권·생존 예측 — SHAP 가중치 캘리브레이션 근거

데이터 소스(전부 DB 적재 완료):
- dong_subway_access   : 동 중심좌표·최근접역·거리·1km내 역 개수
- bus_boarding_daily   : 정류장별 일별 승하차 (371만 행)
- seoul_adstrd_fclty   : 행정동별 집객시설 20종 분기 집계 (마포 16동 336행)

출력:
- 각 동별 {inflow_score, subway_sub, bus_sub, fclty_sub, evidence}

네이밍 주의:
- legal.py의 accessibility_law(장애인편의증진법)와 구분하기 위해 inflow_* 접두를 사용한다.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import timedelta
from typing import Any, TypedDict

from sqlalchemy import func, or_, select

from src.agents.nodes.market_analyst import db_client
from src.database.models import BusBoardingDaily, DongSubwayAccess, SeoulAdstrdFclty
from src.services.population_api import MAPO_DONG_CODES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수 (Phase A 휴리스틱 — Phase B에서 TCN SHAP 기여도로 캘리브레이션 예정)
# ---------------------------------------------------------------------------

# E2SFCA Gaussian decay — McGrail & Humphreys (2009)
_CATCHMENT_M = 1000  # d_0: TOD 역세권 500m의 2배, 버스·집객 포괄

# 역세권 1km 내 역 수 보너스 (Gaussian 본체가 거리 1개만 반영하므로 보완)
_SUBWAY_COUNT_BONUS = 10.0

# 버스 최근 집계 기간 — 371만 행 전체 평균은 비용 과다, 최신 추세만 반영
_BUS_RECENT_DAYS = 30

# 서브점수 가중치 — 2026-04-24 실매출 상관(R²) 리포트 기반 재조정
#
# 초기 휴리스틱(TOD 경험치) 0.40/0.30/0.30 → R² 0.33 중간상관
# 데이터 드리븐(마포 16동 × 최신 8분기 평균 매출 회귀):
#   - 지하철 서브 R² = 0.004 (상관 없음, r=-0.06)
#     * 동 행정중심 기준 물리적 거리라 동 경계 환승역(예: 홍대입구, 공덕) 반영 불가
#     * 가중치 대폭 축소
#   - 버스 서브   R² = 0.48  (중간~강한 상관, r=+0.69)
#   - 집객 서브   R² = 0.54  (강한 상관, r=+0.73)
# 최종 가중치: 0.10·지하철 + 0.40·버스 + 0.50·집객
# 예상 전체 R² : 0.33 → 0.50+
#
# Phase C (polygon 기반 동 경계 거리 재계산) 도입 시 지하철 가중치 상향 조정 재검토.
_W_SUBWAY_DEFAULT = 0.10
_W_BUS_DEFAULT = 0.40
_W_FCLTY_DEFAULT = 0.50

# 정류장 ↔ 마포 16동 매핑 화이트리스트
# Phase A: station_name ILIKE '%keyword%' 매칭 (TOPIS 좌표 수집은 Phase B)
_BUS_STATION_KEYWORDS: dict[str, list[str]] = {
    "아현동": ["아현", "애오개"],
    "공덕동": ["공덕"],
    "도화동": ["도화"],
    "용강동": ["용강", "토정"],
    "대흥동": ["대흥"],
    "염리동": ["염리"],
    "신수동": ["신수"],
    "서강동": ["서강", "광흥창"],
    "서교동": ["서교", "홍대입구", "상수"],
    "합정동": ["합정"],
    "망원1동": ["망원1", "망원역"],
    "망원2동": ["망원2"],
    "연남동": ["연남", "동교"],
    "성산1동": ["성산1"],
    "성산2동": ["성산2", "월드컵"],
    "상암동": ["상암", "디지털미디어"],
}

# 집객시설 컬럼 → 가중치 (Phase A)
# 종합병원·대학·백화점·극장 등 대규모 집객력 있는 시설에 높은 가중치.
# Phase B: 기존 TCN SHAP feature_importance에서 접근성 관련 피처 기여도로 재산정.
_FCLTY_WEIGHTS: dict[str, float] = {
    "gnrl_hsptl_co": 1.5,  # 종합병원
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


class InflowResult(TypedDict):
    """동별 접근성 점수 + 근거 수치."""

    inflow_score: float  # 0~100 최종 점수
    subway_sub: float  # 0~100 지하철 서브점수
    bus_sub: float  # 0~100 버스 서브점수
    fclty_sub: float  # 0~100 집객시설 서브점수
    evidence: dict[str, Any]  # 원천 수치 — synthesis 프롬프트 근거용


# ---------------------------------------------------------------------------
# 순수 수학 헬퍼
# ---------------------------------------------------------------------------


def _gaussian_decay(d: float, d0: float = _CATCHMENT_M) -> float:
    """E2SFCA (McGrail & Humphreys 2009) Gaussian 거리감쇠.

    G(d, d0) = (exp(-0.5 * (d/d0)^2) - exp(-0.5)) / (1 - exp(-0.5))
    for d <= d0, else 0.
    """
    if d >= d0:
        return 0.0
    e_half = math.exp(-0.5)
    numerator = math.exp(-0.5 * (d / d0) ** 2) - e_half
    return max(numerator / (1.0 - e_half), 0.0)


def _minmax_to_100(values: dict[str, float], floor: float = 10.0) -> dict[str, float]:
    """min-max 정규화 → [floor, 100]. 편차 없으면 50."""
    if not values:
        return {}
    vals = list(values.values())
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return {k: 50.0 for k in values}
    scale = 100.0 - floor
    return {k: floor + (v - lo) / (hi - lo) * scale for k, v in values.items()}


# ---------------------------------------------------------------------------
# 서브점수 쿼리
# ---------------------------------------------------------------------------


async def _subway_raw_scores() -> dict[str, tuple[float, dict[str, Any]]]:
    """동별 raw subway score + evidence.

    dong_subway_access는 동당 1행 — 최근접역 1개와 1km 내 역 개수만 보유.
    Gaussian decay를 최근접역 거리에 적용하고, 1km 내 역 수를 보너스로 가산한다.
    """
    async with db_client.get_session() as session:
        stmt = select(
            DongSubwayAccess.dong_name,
            DongSubwayAccess.nearest_subway,
            DongSubwayAccess.subway_distance_m,
            DongSubwayAccess.subway_count_1km,
        ).where(DongSubwayAccess.dong_name.in_(list(MAPO_DONG_CODES.keys())))
        rows = (await session.execute(stmt)).fetchall()

    result: dict[str, tuple[float, dict[str, Any]]] = {}
    for r in rows:
        dist = float(r.subway_distance_m or 9999)
        count = int(r.subway_count_1km or 0)
        # Gaussian 본체(0~1) × 100 + 역 수 가중
        raw = _gaussian_decay(dist) * 100.0 + count * _SUBWAY_COUNT_BONUS
        evidence = {
            "nearest_subway": r.nearest_subway,
            "subway_distance_m": r.subway_distance_m,
            "subway_count_1km": r.subway_count_1km,
        }
        result[r.dong_name] = (raw, evidence)

    # MAPO_DONG_CODES에 있지만 dong_subway_access에 없는 동은 0 처리
    for dong in MAPO_DONG_CODES:
        result.setdefault(dong, (0.0, {"nearest_subway": None, "subway_distance_m": None, "subway_count_1km": 0}))
    return result


async def _bus_raw_scores() -> dict[str, tuple[float, dict[str, Any]]]:
    """동별 raw bus score + evidence.

    최근 _BUS_RECENT_DAYS일 평균 승하차를 정류장명 키워드(ILIKE)로 매칭·합산.
    정류장 좌표 기반 Gaussian은 Phase B에서 TOPIS 수집 후 적용.
    """
    async with db_client.get_session() as session:
        max_date = (await session.execute(select(func.max(BusBoardingDaily.use_date)))).scalar()
        if not max_date:
            return {dong: (0.0, {"bus_stop_count": 0, "bus_daily_avg_boarding": 0.0}) for dong in MAPO_DONG_CODES}

        min_date = max_date - timedelta(days=_BUS_RECENT_DAYS)

        result: dict[str, tuple[float, dict[str, Any]]] = {}
        for dong, keywords in _BUS_STATION_KEYWORDS.items():
            name_filters = [BusBoardingDaily.station_name.ilike(f"%{kw}%") for kw in keywords]
            stmt = select(
                func.count(func.distinct(BusBoardingDaily.station_name)).label("stop_count"),
                func.avg(
                    func.coalesce(BusBoardingDaily.boarding_count, 0)
                    + func.coalesce(BusBoardingDaily.alighting_count, 0)
                ).label("daily_avg"),
            ).where(
                or_(*name_filters),
                BusBoardingDaily.use_date >= min_date,
                BusBoardingDaily.use_date <= max_date,
            )
            row = (await session.execute(stmt)).one()
            stop_count = int(row.stop_count or 0)
            daily_avg = float(row.daily_avg or 0.0)
            # 원점수: 정류장 수 × 일평균 승하차 (공급 총량 proxy)
            raw = stop_count * daily_avg
            evidence = {
                "bus_stop_count": stop_count,
                "bus_daily_avg_boarding": round(daily_avg, 1),
            }
            result[dong] = (raw, evidence)
    return result


async def _fclty_raw_scores() -> dict[str, tuple[float, dict[str, Any]]]:
    """동별 raw facility score + evidence (최신 분기 데이터)."""
    mapo_codes = list(MAPO_DONG_CODES.values())
    async with db_client.get_session() as session:
        max_q = (
            await session.execute(
                select(func.max(SeoulAdstrdFclty.quarter)).where(SeoulAdstrdFclty.dong_code.in_(mapo_codes))
            )
        ).scalar()
        if not max_q:
            return {dong: (0.0, {"fclty_count_by_type": {}, "quarter": None}) for dong in MAPO_DONG_CODES}

        stmt = select(SeoulAdstrdFclty).where(
            SeoulAdstrdFclty.dong_code.in_(mapo_codes),
            SeoulAdstrdFclty.quarter == max_q,
        )
        rows = (await session.execute(stmt)).scalars().all()

    code_to_name = {v: k for k, v in MAPO_DONG_CODES.items()}
    result: dict[str, tuple[float, dict[str, Any]]] = {}
    for r in rows:
        dong = code_to_name.get(r.dong_code) or r.dong_name
        if not dong:
            continue
        type_counts: dict[str, int] = {}
        raw = 0.0
        for col, weight in _FCLTY_WEIGHTS.items():
            count = int(getattr(r, col, 0) or 0)
            if count > 0:
                type_counts[col] = count
                raw += count * weight
        result[dong] = (raw, {"fclty_count_by_type": type_counts, "quarter": max_q})

    for dong in MAPO_DONG_CODES:
        result.setdefault(dong, (0.0, {"fclty_count_by_type": {}, "quarter": max_q}))
    return result


# ---------------------------------------------------------------------------
# SHAP 가중치 캘리브레이션 (Phase B — 2025 Springer Hansen+ML 방법론)
# ---------------------------------------------------------------------------

# TCN 피처 → inflow 서브점수 매핑
# 주의: 현재 TCN은 지하철·집객시설을 직접 피처로 학습하지 않았다.
#   - bus_flpop         : 버스 서브점수(bus_sub)의 직접 proxy
#   - floating_pop      : 집객 서브점수(fclty_sub)의 간접 proxy (골목상권 유동인구)
#   - pop_per_store_gm  : 집객 효율성 proxy
#   - holiday_count     : 집객 변동성 proxy (공휴일 수)
#   - 지하철             : 직접 피처 없음 — 캘리브레이션 시 prior 유지
# 풀 캘리브레이션을 위해선 TCN 재학습 + subway_count/subway_distance 피처 추가 필요(수지니 영역).
_SHAP_SUBWAY_FEATURES: list[str] = []  # 직접 피처 없음
_SHAP_BUS_FEATURES: list[str] = ["bus_flpop"]
_SHAP_FCLTY_FEATURES: list[str] = ["floating_pop", "pop_per_store_gm", "holiday_count"]


def calibrate_weights_from_shap(
    shap_result: dict[str, Any],
    subway_prior: float = _W_SUBWAY_DEFAULT,
) -> tuple[float, float, float]:
    """TCN SHAP 기여도로 (w_subway, w_bus, w_fclty) 가중치 캘리브레이션.

    Springer 2025 "Hansen's Accessibility Theory and ML: a Potential Merger" 노선.
    대한산업공학회지 2024 (공공데이터·XAI 자영업 상권·생존 예측) 캘리브레이션 기법 차용.

    한계:
        TCN 피처에 지하철·집객시설 직접 피처 없음. bus_flpop만 직접 매칭 가능.
        지하철은 prior 유지, 집객은 골목상권 유동인구 관련 피처 기여도 합으로 proxy.
        풀 캘리브레이션은 TCN 재학습 필요.

    반환:
        (w_subway, w_bus, w_fclty) — 합이 1.0이 되도록 정규화된 가중치 튜플.
        shap_result 비어있거나 유효 피처 없으면 default 가중치 반환.
    """
    importances = (shap_result or {}).get("feature_importance") or []
    if not importances:
        return _W_SUBWAY_DEFAULT, _W_BUS_DEFAULT, _W_FCLTY_DEFAULT

    feat_abs: dict[str, float] = {
        item.get("feature"): float(item.get("abs_shap") or 0.0)
        for item in importances
        if isinstance(item, dict) and item.get("feature")
    }

    # 각 카테고리별 abs_shap 합산 — 지하철은 직접 피처 없음
    bus_mass = sum(feat_abs.get(f, 0.0) for f in _SHAP_BUS_FEATURES)
    fclty_mass = sum(feat_abs.get(f, 0.0) for f in _SHAP_FCLTY_FEATURES)

    if bus_mass == 0.0 and fclty_mass == 0.0:
        # 유효 기여 없음 — default 유지
        return _W_SUBWAY_DEFAULT, _W_BUS_DEFAULT, _W_FCLTY_DEFAULT

    # subway_prior를 먼저 고정하고 나머지 (1 - prior)를 bus/fclty로 분배
    remaining = max(1.0 - subway_prior, 0.0)
    total = bus_mass + fclty_mass
    w_bus = remaining * (bus_mass / total) if total > 0 else _W_BUS_DEFAULT
    w_fclty = remaining * (fclty_mass / total) if total > 0 else _W_FCLTY_DEFAULT

    logger.info(
        f"[inflow] SHAP 캘리브레이션 — subway={subway_prior:.2f}(prior) "
        f"bus={w_bus:.2f}(SHAP {bus_mass:.4f}) fclty={w_fclty:.2f}(SHAP {fclty_mass:.4f})"
    )
    return subway_prior, w_bus, w_fclty


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


async def score_all_districts(
    w_subway: float = _W_SUBWAY_DEFAULT,
    w_bus: float = _W_BUS_DEFAULT,
    w_fclty: float = _W_FCLTY_DEFAULT,
    shap_result: dict[str, Any] | None = None,
) -> dict[str, InflowResult]:
    """마포 16동의 inflow_score 일괄 계산.

    Hansen(1959) gravity-based accessibility + E2SFCA(2009) Gaussian decay.

    shap_result 전달 시 bus/fclty 가중치를 SHAP 기여도로 자동 캘리브레이션한다
    (지하철은 TCN 직접 피처 없음으로 prior 유지).
    """
    if shap_result:
        w_subway, w_bus, w_fclty = calibrate_weights_from_shap(shap_result, subway_prior=w_subway)
    if db_client.engine is None:
        await db_client.connect()

    subway, bus, fclty = await asyncio.gather(
        _subway_raw_scores(),
        _bus_raw_scores(),
        _fclty_raw_scores(),
    )

    subway_norm = _minmax_to_100({k: v[0] for k, v in subway.items()})
    bus_norm = _minmax_to_100({k: v[0] for k, v in bus.items()})
    fclty_norm = _minmax_to_100({k: v[0] for k, v in fclty.items()})

    results: dict[str, InflowResult] = {}
    for dong in MAPO_DONG_CODES:
        s = subway_norm.get(dong, 50.0)
        b = bus_norm.get(dong, 50.0)
        f = fclty_norm.get(dong, 50.0)
        final = s * w_subway + b * w_bus + f * w_fclty
        evidence: dict[str, Any] = {}
        if dong in subway:
            evidence.update(subway[dong][1])
        if dong in bus:
            evidence.update(bus[dong][1])
        if dong in fclty:
            evidence.update(fclty[dong][1])
        results[dong] = InflowResult(
            inflow_score=round(final, 1),
            subway_sub=round(s, 1),
            bus_sub=round(b, 1),
            fclty_sub=round(f, 1),
            evidence=evidence,
        )

    score_vals = [r["inflow_score"] for r in results.values()]
    logger.info(
        f"[inflow] 16동 점수 범위 {min(score_vals):.1f}~{max(score_vals):.1f} "
        f"| 가중치 subway={w_subway} bus={w_bus} fclty={w_fclty}"
    )
    return results
