"""반경 기반 경쟁 지형 분석 + 카니발리제이션 + 업종 폐업률 추세.

주요 함수:
    - `analyze_competition` : 반경 내 같은 업종 경쟁점 집계
    - `analyze_cannibalization` : 동일 브랜드 자사 잠식 (Pancras 2013 decay)
    - `get_industry_closure_trend` : `store_quarterly` 기반 추세
    - `get_dong_centroid` : `store_info` 동별 평균 좌표 (dong_mapping 좌표 부재 대체)

주의: `dong_mapping` 테이블에 centroid 컬럼이 없어, `store_info` 의 dong_code 별
평균 lat/lon 을 사용한다. 기하학적 중심은 아니며 ±100m 내외 편차 가능.
"""

from __future__ import annotations

import os
from functools import lru_cache
from math import asin, cos, radians, sin, sqrt

from sqlalchemy import text

from src.database.sync_engine import get_sync_engine
from src.services.brand_mapping_resolver import (
    get_all_mapo_stores_by_brand,
    resolve_brand_name,
)

# ---------------------------------------------------------------------------
# 거리 계산
# ---------------------------------------------------------------------------

EARTH_RADIUS_M = 6_371_000


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간 구면 거리 (미터)."""
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


# ---------------------------------------------------------------------------
# Centroid 조회 (store_info 평균)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=64)
def get_dong_centroid(dong_code: str) -> tuple[float, float] | None:
    """dong_code 의 중심 좌표 — store_info 평균 lat/lon.

    dong_mapping 에 좌표가 없어 대체 사용. 매장 분포 편향으로 ±100m 편차 가능.
    """
    sql = text(
        """
        SELECT AVG(lat)::float AS lat, AVG(lon)::float AS lon
          FROM store_info
         WHERE dong_code = :code
           AND lat IS NOT NULL AND lon IS NOT NULL
        """
    )
    engine = get_sync_engine(os.environ["POSTGRES_URL"])
    with engine.connect() as conn:
        row = conn.execute(sql, {"code": dong_code}).first()
    if not row or row[0] is None:
        return None
    return (row[0], row[1])


# ---------------------------------------------------------------------------
# 반경 경쟁 분석
# ---------------------------------------------------------------------------


def _bounding_box(lat: float, lon: float, radius_m: int) -> tuple[float, float, float, float]:
    """반경 기반 lat/lon 박스 (DB 사전 필터용)."""
    dlat = radius_m / 111_000  # 위도 1도 ≈ 111km
    dlon = radius_m / (111_000 * cos(radians(lat)))
    return (lat - dlat, lat + dlat, lon - dlon, lon + dlon)


def analyze_competition(
    dong_code: str,
    industry_keyword: str,
    radius_m: int = 500,
    sample_limit: int = 20,
) -> dict:
    """후보지(동 centroid) 반경 내 같은 업종 경쟁 지형.

    Args:
        dong_code: 마포 행정동 코드 (예: '11440660' 서교동).
        industry_keyword: `kakao_store.category` 매칭 키워드 (예: '커피').
        radius_m: 반경 (미터).

    Returns:
        {
            "center_dong": str,
            "radius_m": int,
            "total_competitors": int,
            "brand_distribution": {brand: count, ...},  # 내림차순
            "franchise_count": int,
            "independent_count": int,
            "saturation_level": "sparse|low|medium|high|saturated",
            "saturation_score": int 0-100,
            "samples": [상위 20개 매장 정보]
        }
    """
    centroid = get_dong_centroid(dong_code)
    if not centroid:
        return {"error": f"centroid not found for {dong_code}"}

    lat0, lon0 = centroid
    lat_min, lat_max, lon_min, lon_max = _bounding_box(lat0, lon0, radius_m)

    sql = text(
        """
        SELECT kakao_id, place_name, brand_name, category,
               lat, lon, is_franchise
          FROM kakao_store
         WHERE lat BETWEEN :lat_min AND :lat_max
           AND lon BETWEEN :lon_min AND :lon_max
           AND (category ILIKE :kw OR category_detail ILIKE :kw)
        """
    )
    engine = get_sync_engine(os.environ["POSTGRES_URL"])
    with engine.connect() as conn:
        rows = (
            conn.execute(
                sql,
                {
                    "lat_min": lat_min,
                    "lat_max": lat_max,
                    "lon_min": lon_min,
                    "lon_max": lon_max,
                    "kw": f"%{industry_keyword}%",
                },
            )
            .mappings()
            .all()
        )

    within: list[dict] = []
    for r in rows:
        d = haversine_m(lat0, lon0, r["lat"], r["lon"])
        if d <= radius_m:
            # 프론트 관례에 맞춰 lon → lng 로 노출 (§05 지도 마커용)
            row_dict = {**dict(r), "distance_m": round(d, 1)}
            row_dict["lng"] = row_dict.pop("lon", None)
            within.append(row_dict)

    within.sort(key=lambda x: x["distance_m"])

    brand_dist: dict[str, int] = {}
    franchise_cnt = 0
    independent_cnt = 0
    for w in within:
        resolved = resolve_brand_name(w["brand_name"]) if w["brand_name"] else None
        key = resolved or (w["brand_name"] if w["brand_name"] else "독립점")
        brand_dist[key] = brand_dist.get(key, 0) + 1
        if w["is_franchise"]:
            franchise_cnt += 1
        else:
            independent_cnt += 1

    total = len(within)
    level, score = _saturation_bucket(total, radius_m)

    return {
        "center_dong": dong_code,
        "radius_m": radius_m,
        "industry_keyword": industry_keyword,
        "total_competitors": total,
        "brand_distribution": dict(sorted(brand_dist.items(), key=lambda x: -x[1])),
        "franchise_count": franchise_cnt,
        "independent_count": independent_cnt,
        "saturation_level": level,
        "saturation_score": score,
        "samples": within[:sample_limit],
    }


def _saturation_bucket(count: int, radius_m: int) -> tuple[str, int]:
    """반경 500m 기준 경쟁 밀집도 판정.
    임계값: sparse 0~2 / low 3~5 / medium 6~10 / high 11~20 / saturated 21+
    반경이 500m가 아닌 경우 면적비율로 보정.
    """
    area_ratio = (radius_m / 500) ** 2
    scaled = count / area_ratio if area_ratio else count

    if scaled >= 21:
        return ("saturated", 90)
    if scaled >= 11:
        return ("high", 72)
    if scaled >= 6:
        return ("medium", 50)
    if scaled >= 3:
        return ("low", 30)
    return ("sparse", 10)


# ---------------------------------------------------------------------------
# 카니발리제이션 (Pancras 2013 decay + 업계 임계값)
# ---------------------------------------------------------------------------


def estimate_cannibalization(
    distance_bins: dict[str, int],
    store_type: str = "neighborhood",
    industry: str = "cafe",
) -> dict:
    """학술(Pancras 2013) + 업계(GrowthFactor 2026) 조합.

    Args:
        distance_bins: {"0-300m": 1, "300-500m": 1, "500-1000m": 0, "1000-2000m": 2}
        store_type: "neighborhood" | "office" | "mall"
        industry: "cafe" | "coffee" | "chicken" | "burger" | "korean" | "default"

    Returns:
        {total_impact_pct, confidence, method, references}
    """
    base_by_industry = {
        "cafe": 0.25,
        "coffee": 0.25,
        "restaurant": 0.18,  # legal specialist 호출 — 일반 음식점 평균
        "chicken": 0.10,
        "burger": 0.20,
        "korean": 0.15,
        "convenience": 0.10,  # 편의점 — 자기잠식 효과 약함
        "default": 0.20,
    }
    base_rate = base_by_industry.get(industry, 0.20)

    bin_midpoint_km = {
        "0-300m": 0.15,
        "300-500m": 0.4,
        "500-1000m": 0.75,
        "1000-2000m": 1.5,
    }

    total = 0.0
    for bin_label, count in distance_bins.items():
        if count == 0 or bin_label not in bin_midpoint_km:
            continue
        dist_km = bin_midpoint_km[bin_label]
        # Pancras 2013: 1마일(1.609km)당 28.1% 감소. per-km decay는 선형 변환이 아닌 지수 루트.
        # 올바른 변환: (1 - 0.281)^(1/1.609) ≈ 0.8146 (rounded to 0.813).
        # 기존 선형 변환(0.281/1.609=0.1746)은 오류로 수정. (테스트 허용 오차 ±0.005)
        decay = 0.813**dist_km  # Pancras 2013 decay (per-km)
        total += base_rate * decay * count

    type_modifier = {"neighborhood": 1.0, "office": 0.6, "mall": 0.4}.get(store_type, 1.0)
    total *= type_modifier

    # 50% 캡 적용 — 누적 영향이 그 이상이면 잘림.
    # is_capped=true 일 때 프론트는 "≥50% (최대치 도달)" 표기로 정직성 확보.
    raw_total = total
    is_capped = raw_total > 0.50
    total = min(raw_total, 0.50)

    return {
        "total_impact_pct": -round(total, 3),
        "is_capped": is_capped,
        "confidence": "medium",
        "method": "Pancras_2013_decay + industry_threshold",
        "references": [
            "Pancras, Sriram, Kumar (2013) Management Science 59(5)",
            "GrowthFactor (2026): 20-25% overlap threshold",
            "Kalibrate (2025): up to 50% extreme cases",
        ],
    }


def analyze_cannibalization_at(
    lat: float,
    lon: float,
    brand_name: str,
    radius_m: int = 2000,
    store_type: str = "neighborhood",
    industry: str = "cafe",
) -> dict:
    """좌표 기준 동일 브랜드 자사 잠식 분석.

    공실 스팟 추천 위치 등 정확한 출점 후보지 (lat, lon) 기준으로 500m bin
    단위 카운트. 행정동 centroid 폴백을 쓰는 :func:`analyze_cannibalization`
    보다 정밀.

    Returns:
        ``analyze_cannibalization`` 와 동일 dict + ``ref_lat``, ``ref_lon`` 추가.
    """
    if lat is None or lon is None:
        return {"error": "lat/lon required for analyze_cannibalization_at"}
    all_same_brand = get_all_mapo_stores_by_brand(brand_name)

    nearby: list[dict] = []
    for s in all_same_brand:
        d = haversine_m(lat, lon, s["lat"], s["lon"])
        if d <= radius_m:
            nearby.append({**s, "distance_m": round(d, 1)})
    nearby.sort(key=lambda x: x["distance_m"])

    bins = {"0-300m": 0, "300-500m": 0, "500-1000m": 0, "1000-2000m": 0}
    for n in nearby:
        d = n["distance_m"]
        if d < 300:
            bins["0-300m"] += 1
        elif d < 500:
            bins["300-500m"] += 1
        elif d < 1000:
            bins["500-1000m"] += 1
        elif d < 2000:
            bins["1000-2000m"] += 1

    impact = estimate_cannibalization(bins, store_type=store_type, industry=industry)

    return {
        "brand_name": brand_name,
        "radius_m": radius_m,
        "ref_lat": lat,
        "ref_lon": lon,
        "ref_source": "spot_coord",
        "same_brand_nearby": len(nearby),
        "closest_distance_m": nearby[0]["distance_m"] if nearby else None,
        "distance_bins": bins,
        "estimated_revenue_impact_pct": impact["total_impact_pct"],
        "impact_method": impact["method"],
        "impact_references": impact["references"],
        "nearby_stores": nearby[:10],
        "note": "마포 내 매장만 포함. 인접구 매장은 Phase 2 과제.",
    }


def analyze_cannibalization(
    dong_code: str,
    brand_name: str,
    radius_m: int = 2000,
    store_type: str = "neighborhood",
    industry: str = "cafe",
) -> dict:
    """동일 브랜드 자사 잠식 분석 (행정동 centroid 기준 폴백).

    좌표가 명확한 경우 :func:`analyze_cannibalization_at` 우선 사용 권장.
    TODO: 인접 자치구(서대문/용산) 동일 브랜드 매장까지 포함 고려 (Phase 2).
    """
    centroid = get_dong_centroid(dong_code)
    if not centroid:
        return {"error": f"centroid not found for {dong_code}"}

    all_same_brand = get_all_mapo_stores_by_brand(brand_name)

    lat0, lon0 = centroid
    nearby: list[dict] = []
    for s in all_same_brand:
        d = haversine_m(lat0, lon0, s["lat"], s["lon"])
        if d <= radius_m:
            nearby.append({**s, "distance_m": round(d, 1)})
    nearby.sort(key=lambda x: x["distance_m"])

    bins = {"0-300m": 0, "300-500m": 0, "500-1000m": 0, "1000-2000m": 0}
    for n in nearby:
        d = n["distance_m"]
        if d < 300:
            bins["0-300m"] += 1
        elif d < 500:
            bins["300-500m"] += 1
        elif d < 1000:
            bins["500-1000m"] += 1
        elif d < 2000:
            bins["1000-2000m"] += 1

    impact = estimate_cannibalization(bins, store_type=store_type, industry=industry)

    return {
        "brand_name": brand_name,
        "radius_m": radius_m,
        "ref_lat": lat0,
        "ref_lon": lon0,
        "ref_source": "dong_centroid",
        "same_brand_nearby": len(nearby),
        "closest_distance_m": nearby[0]["distance_m"] if nearby else None,
        "distance_bins": bins,
        "estimated_revenue_impact_pct": impact["total_impact_pct"],
        "impact_is_capped": impact.get("is_capped", False),
        "impact_method": impact["method"],
        "impact_references": impact["references"],
        "nearby_stores": nearby[:10],
        "note": "마포 내 매장만 포함. 인접구 매장은 Phase 2 과제.",
    }


# ---------------------------------------------------------------------------
# 업종 폐업률 추세
# ---------------------------------------------------------------------------


def get_industry_closure_trend(dong_code: str, industry_code: str) -> dict:
    """store_quarterly 에서 이 동 + 이 업종 폐업률 추세 (최근 8 분기).

    Args:
        dong_code: 예 '11440660'
        industry_code: SPOTTER 표준 (예 'CS100010' 커피-음료).
    """
    sql = text(
        """
        SELECT quarter, store_count, open_count, close_count, closure_rate, franchise_count
          FROM store_quarterly
         WHERE dong_code = :dc
           AND industry_code = :ic
         ORDER BY quarter DESC
         LIMIT 8
        """
    )
    engine = get_sync_engine(os.environ["POSTGRES_URL"])
    with engine.connect() as conn:
        rows = conn.execute(sql, {"dc": dong_code, "ic": industry_code}).mappings().all()

    if not rows:
        return {
            "samples": [],
            "current_closure_rate": None,
            "historical_avg": None,
            "trend": "unknown",
        }

    samples = [dict(r) for r in reversed(rows)]
    current = samples[-1]["closure_rate"]

    if len(samples) > 1:
        past = [s["closure_rate"] for s in samples[:-1] if s["closure_rate"] is not None]
        avg_past = sum(past) / len(past) if past else current
    else:
        avg_past = current

    trend = "stable"
    if current is not None and avg_past:
        if current > avg_past * 1.2:
            trend = "worsening"
        elif current < avg_past * 0.8:
            trend = "improving"

    return {
        "samples": samples,
        "current_closure_rate": current,
        "historical_avg": round(avg_past, 4) if avg_past is not None else None,
        "trend": trend,
    }
