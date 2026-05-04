"""
전체 마포구 행정동 입지 랭킹 에이전트

LLM 없이 Python 연산만으로 16개 행정동을 정량 점수화하여 순위를 산출합니다.
market / population / legal 에이전트와 asyncio.gather로 병렬 실행됩니다.

점수 산식 (100점 만점, A안 가중치 + 정규화 강제):
  population_weight=True  (기본): 매출 35% + 인구 20% + 임대료 15% + 접근성 10% + 경쟁밀도 10% + 트렌드 10%
  population_weight=False       : 매출 50% + 인구 10% + 임대료 20% + 접근성  5% + 경쟁밀도  5% + 트렌드 10%

  * 데이터 결측 시: 결측 지표 가중치를 활성 지표에 비례 분배해 합 항상 1.0 유지.
  * 매출 floor 제거 — 정규화로 음수/0 발생 불가.

추가 패널티:
  - 임대료 예산 초과: 1.5배 초과 시 -50%, 1~1.5배 초과 시 비례 감점
  - 공실률 패널티: 5~10% → -15%, 10%+ → -30% (네이버 부동산 월세 매물 기준, 2026-04)
  - 용도지역 패널티: danger(영업 제한) → -50%, caution(회색지역) → -15%
"""

import asyncio
import json
import logging
import math

import redis.asyncio as aioredis
from sqlalchemy import func, select

from src.agents.nodes._attribution_helpers import build_attribution
from src.agents.nodes.market_analyst import db_client, market_tool
from src.config.constants import BIZ_NORMALIZE, BIZ_TYPE_LABEL, DISTRICT_ZONE_MAP, MAPO_DISTRICTS, ZONING_RULES
from src.config.settings import settings
from src.database.models import KakaoStore, MasterSubwayStation, NaverVacancy, StoreQuarterly
from src.schemas.state import AgentState
from src.services.inflow_scorer import score_all_districts as _score_inflow
from src.services.population_api import MAPO_DONG_CODES

logger = logging.getLogger(__name__)

_CACHE_TTL = 86400  # 24시간

# ── SEMAS / NAVER 클라이언트 (싱글톤, API 키 없으면 None) ──
_semas_client = None
_naver_client = None


def _init_optional_clients():
    """API 키가 있을 때만 클라이언트 생성 (서버 시작 시 1회)"""
    global _semas_client, _naver_client
    if _semas_client is None and settings.semas_api_key:
        from src.services.semas_api import SemasAPIClient

        _semas_client = SemasAPIClient(api_key=settings.semas_api_key)
    if _naver_client is None and settings.naver_client_id and settings.naver_client_secret:
        from src.services.sns_trend import NaverTrendClient

        _naver_client = NaverTrendClient(
            client_id=settings.naver_client_id,
            client_secret=settings.naver_client_secret,
        )


# 사용자 입력 업종명 → kakao_store.category 매핑 (vacancy spot 경쟁밀도 계산용).
# tools.py 의 _KAKAO_CATEGORY_MAP 과 동일 정책 — import 의존 줄이려고 핵심 키만 인라인.
_VACANCY_SPOT_KAKAO_CATEGORY: dict[str, str] = {
    "카페": "커피-음료",
    "커피": "커피-음료",
    "cafe": "커피-음료",
    "coffee": "커피-음료",
    "한식": "한식음식점",
    "음식점": "한식음식점",
    "restaurant": "한식음식점",
    "치킨": "치킨전문점",
    "분식": "분식전문점",
    "주점": "호프-간이주점",
    "베이커리": "제과점",
    "빵": "제과점",
    "제과점": "제과점",
    "편의점": "편의점",
}


def _spot_haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간 거리(m). vacancy_inject._haversine_m 과 동일 식 — 외부 의존 없는 사본."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


async def _load_spot_score_features(
    business_type: str | None,
    brand_name: str | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """winner 동 spot 점수 산출용 보조 좌표 — 마포 지하철역 / 동종업종 매장 / 자사 매장.

    동 단위 데이터(임대료/유동인구)는 같은 동 안 spot 들끼리 차별화 안 돼서 제외.
    spot 단위 차별화 가능한 신호:
      - 지하철 접근성 (가까울수록 ↑)
      - 경쟁 밀도 (반경 500m 동종 매장 수, 적을수록 ↑)
      - 자사 영업구역 안전 (territory_radius_m 안 자사 매장 0개일수록 ↑)

    Args:
        brand_name: 자사 매장 좌표 로드용 (영업구역 침해 페널티 산출). None 이면 자사 매장 [].
    """
    target_cat: str | None = None
    if business_type:
        bt = business_type.lower().strip()
        target_cat = _VACANCY_SPOT_KAKAO_CATEGORY.get(bt) or _VACANCY_SPOT_KAKAO_CATEGORY.get(business_type)
    try:
        async with db_client.get_session() as session:
            subway_stmt = select(MasterSubwayStation.lat, MasterSubwayStation.lon).where(
                MasterSubwayStation.sigungu_code == "11440",
                MasterSubwayStation.lat.isnot(None),
                MasterSubwayStation.lon.isnot(None),
            )
            subway_rows = (await session.execute(subway_stmt)).fetchall()
            subway = [{"lat": float(r.lat), "lon": float(r.lon)} for r in subway_rows]

            store_stmt = select(KakaoStore.lat, KakaoStore.lon).where(
                KakaoStore.lat.isnot(None),
                KakaoStore.lon.isnot(None),
            )
            if target_cat:
                store_stmt = store_stmt.where(KakaoStore.category == target_cat)
            store_rows = (await session.execute(store_stmt)).fetchall()
            stores = [{"lat": float(r.lat), "lon": float(r.lon)} for r in store_rows]
        # 자사 매장 좌표 로드 — brand_mapping_resolver (BRAND_ALIASES 양방향 + DB 5,900 매핑).
        # 마포 전체에서 검색 후 동 무관하게 좌표만 추출 (영업구역 거리 계산은 winner spot 과의 직선거리).
        same_brand: list[dict] = []
        if brand_name:
            try:
                from src.services.brand_mapping_resolver import get_all_mapo_stores_by_brand

                rows = await asyncio.to_thread(get_all_mapo_stores_by_brand, brand_name)
                same_brand = [
                    {"lat": float(r["lat"]), "lon": float(r["lon"])}
                    for r in rows
                    if r.get("lat") is not None and r.get("lon") is not None
                ]
            except Exception as e:
                logger.warning(f"[district_ranking] 자사 매장 좌표 로드 실패: {e}")
                same_brand = []
        logger.info(
            f"[district_ranking] spot 점수 보조데이터 로드 — 지하철 {len(subway)}개, 동종매장 {len(stores)}개 "
            f"(cat={target_cat}), 자사 {len(same_brand)}개 (brand={brand_name})"
        )
        return subway, stores, same_brand
    except Exception as e:
        logger.warning(f"[district_ranking] spot 점수 보조데이터 로드 실패: {e}")
        return [], [], []


def _score_winner_spots(
    spots: list[dict],
    winner_district: str,
    subway_coords: list[dict],
    competitor_coords: list[dict],
    same_brand_coords: list[dict] | None = None,
    territory_radius_m: int | None = None,
    radius_m: int = 500,
) -> None:
    """winner 동 spot 들에 점수 4분할 in-place 부여.

    가중치: 경쟁 0.35 + 지하철 0.30 + 매물 0.15 + 자사영업구역 안전 0.20.
    영업구역 안전 = territory_radius_m 안 자사 매장 0개 → 1.0, 1개 이상 → 0.0.
    territory_radius_m 미입력 또는 자사 매장 데이터 없으면 영업구역 항목 비활성 (3분할로 fallback).

    동 내 min-max 정규화 — winner 동 spot 들끼리만 비교. 결측 항목은 가중치 비례 재배분.

    추가 in-place 필드: nearest_same_brand_m, territory_violation
    """
    if not winner_district:
        return
    target_spots = [s for s in spots if s.get("dong_name") == winner_district]
    if not target_spots:
        return

    for spot in target_spots:
        lat = spot.get("lat")
        lon = spot.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            spot["score"] = None
            spot["subway_distance_m"] = None
            spot["competitor_count_500m"] = None
            spot["nearest_same_brand_m"] = None
            spot["territory_violation"] = None
            continue

        if subway_coords:
            spot["subway_distance_m"] = round(
                min(_spot_haversine_m(lat, lon, s["lat"], s["lon"]) for s in subway_coords)
            )
        else:
            spot["subway_distance_m"] = None

        if competitor_coords:
            spot["competitor_count_500m"] = sum(
                1 for s in competitor_coords if _spot_haversine_m(lat, lon, s["lat"], s["lon"]) <= radius_m
            )
        else:
            spot["competitor_count_500m"] = None

        # 자사 영업구역 침해 판정 — 자사 매장 중 가장 가까운 거리.
        # territory_radius_m 안에 1개라도 있으면 violation=True (영업구역 안전 점수 0).
        if same_brand_coords:
            nearest = min(
                (_spot_haversine_m(lat, lon, s["lat"], s["lon"]) for s in same_brand_coords),
                default=None,
            )
            spot["nearest_same_brand_m"] = round(nearest) if nearest is not None else None
            if territory_radius_m and nearest is not None:
                spot["territory_violation"] = nearest <= territory_radius_m
            else:
                spot["territory_violation"] = None
        else:
            spot["nearest_same_brand_m"] = None
            spot["territory_violation"] = None

    def _minmax(values: list[float | None], reverse: bool) -> list[float | None]:
        ok = [v for v in values if v is not None]
        if not ok:
            return [None] * len(values)
        lo, hi = min(ok), max(ok)
        if hi == lo:
            return [0.5 if v is not None else None for v in values]
        out: list[float | None] = []
        for v in values:
            if v is None:
                out.append(None)
                continue
            n = (v - lo) / (hi - lo)
            out.append(1.0 - n if reverse else n)
        return out

    comp_norm = _minmax([s.get("competitor_count_500m") for s in target_spots], reverse=True)
    sub_norm = _minmax([s.get("subway_distance_m") for s in target_spots], reverse=True)
    list_norm = _minmax([s.get("listing_count") for s in target_spots], reverse=False)
    # 영업구역 안전 — 0 (침해) / 1 (안전). territory_radius_m 미입력 시 None (가중치 미적용).
    territory_norm: list[float | None] = []
    for s in target_spots:
        v = s.get("territory_violation")
        if v is None:
            territory_norm.append(None)
        else:
            territory_norm.append(0.0 if v else 1.0)

    for spot, c, su, li, tr in zip(target_spots, comp_norm, sub_norm, list_norm, territory_norm):
        parts: list[tuple[float, float]] = []
        if c is not None:
            parts.append((c, 0.35))
        if su is not None:
            parts.append((su, 0.30))
        if li is not None:
            parts.append((li, 0.15))
        if tr is not None:
            parts.append((tr, 0.20))
        if not parts:
            spot["score"] = None
            continue
        w_total = sum(w for _, w in parts)
        score = sum(v * (w / w_total) for v, w in parts) * 100.0
        spot["score"] = round(score, 2)

    # 검증 로그 — 영업구역 침해 spot 이 후순위로 밀리는지 확인.
    sorted_spots = sorted(target_spots, key=lambda s: -(s.get("score") or 0))
    print(
        f"[spot_score:{winner_district}] top5 검증 "
        f"(총 {len(target_spots)}개 spot, territory={territory_radius_m}m):"
    )
    for i, s in enumerate(sorted_spots[:5], 1):
        lat_v = s.get("lat")
        lon_v = s.get("lon")
        coord = f"({lat_v:.4f},{lon_v:.4f})" if isinstance(lat_v, (int, float)) and isinstance(lon_v, (int, float)) else "(좌표X)"
        viol = s.get("territory_violation")
        viol_str = "침해" if viol is True else ("안전" if viol is False else "—")
        print(
            f"  #{i} score={s.get('score')} | "
            f"경쟁={s.get('competitor_count_500m')}개 / "
            f"지하철={s.get('subway_distance_m')}m / "
            f"매물={s.get('listing_count')} / "
            f"자사최근접={s.get('nearest_same_brand_m')}m({viol_str}) @ {coord}"
        )


async def _load_vacancy_spots(dong_names: list[str]) -> list[dict]:
    """
    지정 동들의 실제 공실 좌표 목록 반환 (월세 매물, 좌표 유효한 것만)

    Returns: [{id, lat, lon, dong_name, listing_count}, ...]
    winner_district spot 들은 이후 `_score_winner_spots` 로 score / subway_distance_m /
    competitor_count_500m 가 추가된다.
    """
    try:
        async with db_client.get_session() as session:
            stmt = select(
                NaverVacancy.id,
                NaverVacancy.lat,
                NaverVacancy.lon,
                NaverVacancy.dong_name,
                NaverVacancy.listing_count,
            ).where(
                NaverVacancy.trade_type == "월세",
                NaverVacancy.dong_name.in_(dong_names),
                NaverVacancy.lat.isnot(None),
                NaverVacancy.lon.isnot(None),
            )
            rows = (await session.execute(stmt)).fetchall()
        spots = [
            {
                "id": r.id,
                "lat": r.lat,
                "lon": r.lon,
                "dong_name": r.dong_name,
                "listing_count": r.listing_count or 1,
            }
            for r in rows
        ]
        logger.info(f"[district_ranking] 공실 스팟 {len(spots)}개 로드 (동: {dong_names})")
        return spots
    except Exception as e:
        logger.warning(f"[district_ranking] 공실 스팟 로드 실패: {e}")
        return []


# 동일 invocation 내 중복 DB 쿼리 방지용 비동기 Task 공유 dict.
# district_ranking_node와 population_analyst_node가 asyncio.gather로 병렬 실행되어
# 동일 target_district에 대해 market_tool.get_population_trends를 두 번 호출하는 문제를 막는다.
# parallel_analysis_node 진입 시 _clear_shared_population_cache()로 초기화.
_pop_trends_tasks: dict[str, asyncio.Task] = {}

# DB 커넥션 풀 고갈 방지 — 16개 동 동시 조회 시 pool_size(3)+overflow(5)=8 초과 방지
_db_semaphore = asyncio.Semaphore(4)


async def _safe_population_trends(dong: str) -> dict:
    """get_population_trends를 호출하되 exception 시 빈 dict 반환 (다른 awaiter 보호)."""
    try:
        return await market_tool.get_population_trends(dong)
    except Exception as e:
        logger.warning(f"[shared_population_trends] {dong} 인구 데이터 조회 실패: {e}")
        return {"error": str(e)}


def shared_population_trends(dong: str) -> asyncio.Task:
    """동일 dong에 대한 get_population_trends 호출을 단일 Task로 dedupe.

    첫 호출자가 Task를 생성하고, 같은 dong에 대한 후속 호출자는 같은 Task를 await한다.
    asyncio는 cooperative multitasking이므로 if-check와 dict 할당 사이에 race condition은 없다.
    _safe_population_trends로 감싸서 exception이 다른 awaiter에 전파되지 않음.
    """
    if dong not in _pop_trends_tasks:
        _pop_trends_tasks[dong] = asyncio.create_task(_safe_population_trends(dong))
    return _pop_trends_tasks[dong]


def _clear_shared_population_cache() -> None:
    """parallel_analysis_node 진입 시 호출 — 요청 간 Task 누적 방지."""
    _pop_trends_tasks.clear()


async def _load_vacancy_map() -> tuple[dict[str, float], bool]:
    """
    동별 공실률 계산 (2026-04 기준 네이버 부동산 월세 매물)

    공실률 = 월세 매물 수 / 최신 분기 영업 점포 수 * 100
    store_quarterly 최신 분기 기준 (방법 B — 더 정확)

    Returns:
        (vacancy_rate_map, success): DB 로드 성공 여부 플래그 포함.
        성공 시 success=True, 실패 시 빈 dict + success=False
        (프론트/응답에서 '공실 데이터 반영됨' vs '공실 미반영' 구분 표시용)
    """
    try:
        async with db_client.get_session() as session:
            # 1) 동별 월세 매물 수 합산
            vacancy_stmt = (
                select(NaverVacancy.dong_name, func.sum(NaverVacancy.listing_count).label("wolse_count"))
                .where(NaverVacancy.trade_type == "월세")
                .group_by(NaverVacancy.dong_name)
            )
            vacancy_rows = (await session.execute(vacancy_stmt)).fetchall()
            wolse_map = {r.dong_name: int(r.wolse_count) for r in vacancy_rows}

            # 2) 동별 최신 분기 영업 점포 수
            max_quarter_stmt = select(func.max(StoreQuarterly.quarter))
            max_quarter = (await session.execute(max_quarter_stmt)).scalar()

            store_stmt = (
                select(StoreQuarterly.dong_name, func.sum(StoreQuarterly.store_count).label("store_count"))
                .where(StoreQuarterly.quarter == max_quarter)
                .group_by(StoreQuarterly.dong_name)
            )
            store_rows = (await session.execute(store_stmt)).fetchall()
            store_map = {r.dong_name: int(r.store_count) for r in store_rows if r.store_count}

        # 3) 공실률 계산 — 점포 데이터 없는 동은 0.0이 아닌 미반영 처리
        vacancy_rate_map: dict[str, float] = {}
        for dong in MAPO_DISTRICTS:
            wolse = wolse_map.get(dong, 0)
            store_count = store_map.get(dong, 0)
            if store_count > 0:
                vacancy_rate_map[dong] = round(wolse / store_count * 100, 2)
            # store_count=0이면 vacancy_rate_map에 미포함 → 패널티 0 (데이터 부재와 0% 구분)

        logger.info(
            f"[district_ranking] 공실률 로드 완료 - 상위 3개: "
            f"{sorted(vacancy_rate_map.items(), key=lambda x: -x[1])[:3]}"
        )
        return vacancy_rate_map, True

    except Exception as e:
        logger.warning(f"[district_ranking] 공실률 로드 실패 (패널티 비활성화): {e}")
        return {}, False


async def _fetch_semas_density(dong_name: str, business_type: str) -> int | None:
    """SEMAS API — 행정동 업종 밀집도 (점포 수). API 키 없거나 실패 시 None."""
    if _semas_client is None:
        return None
    try:
        dong_code = MAPO_DONG_CODES.get(dong_name)
        if not dong_code:
            return None
        biz_code = {"카페": "Q01A01", "음식점": "Q01A02", "편의점": "Q02A01"}.get(
            BIZ_TYPE_LABEL.get(business_type.lower(), business_type), "Q01"
        )
        result = await _semas_client.get_business_density(dong_code, biz_code)
        items = result.get("items", [])
        return sum(item.get("store_count", 0) for item in items) if items else None
    except Exception as e:
        logger.debug(f"[district_ranking] SEMAS 밀집도 조회 실패 ({dong_name}): {e}")
        return None


async def _fetch_naver_trend(dong_name: str, business_type: str) -> float | None:
    """NAVER 검색 트렌드 점수 — DB(naver_trend_quarterly) 최신 분기 값.

    2026-05-02: 외부 NAVER DataLab API 호출 → DB 조회로 전환.
    이유: API 키 부재 시 모든 동 None 반환 → trend_score 16동 모두 None →
    프론트 "동 검색량 16동 중 N위" 산출 불가. DB에는 ETL(`collect_naver_trend_rebuild.py`)
    로 이미 16동 데이터 적재되어 있음 (AVG(ratio) per quarter, 2024 Q4 stale 노트 별도).

    business_type 인자는 호환성 유지용 (현재 DB 산식이 키워드 평균이라 업종별 분리 X).
    """
    _ = business_type  # 시그니처 호환 — 향후 업종별 키워드 분리 시 활성화
    try:
        if db_client.engine is None:
            await db_client.connect()
        async with db_client.get_session() as session:
            from sqlalchemy import text

            result = await session.execute(
                text(
                    """
                    SELECT trend_score
                    FROM naver_trend_quarterly
                    WHERE scope = 'mapo' AND dong_name = :dong
                    ORDER BY quarter DESC
                    LIMIT 1
                    """
                ),
                {"dong": dong_name},
            )
            row = result.fetchone()
            return float(row[0]) if row and row[0] is not None else None
    except Exception as e:
        logger.debug(f"[district_ranking] DB trend 조회 실패 ({dong_name}): {e}")
        return None


async def _score_single_district(dong_name: str, business_type: str) -> dict:
    """
    단일 행정동 원시 지표 수집.
    DB 데이터 없는 항목은 None으로 반환 — 0.0과 구분하여 정규화 왜곡 방지.
    SEMAS 밀집도, NAVER 트렌드는 API 키 있을 때만 조회 (없으면 None).
    """
    try:
        # 기본 3축 + 선택 2축 병렬 조회
        results = await asyncio.gather(
            market_tool.get_commercial_insights(dong_name, business_type),
            shared_population_trends(dong_name),
            market_tool.get_rent_insight(dong_name),
            _fetch_semas_density(dong_name, business_type),
            _fetch_naver_trend(dong_name, business_type),
            return_exceptions=True,
        )
        sales_data, pop_data, rent_data, semas_density, naver_trend = results

        # None = DB 데이터 없음, 0.0 = 실제 성장률 0
        sales_growth = None
        if not isinstance(sales_data, Exception) and "error" not in (sales_data or {}):
            sales_growth = float(sales_data.get("qoq_growth") or 0)

        pop_growth = None
        if not isinstance(pop_data, Exception) and "error" not in (pop_data or {}):
            pop_growth = float(pop_data.get("qoq_growth") or 0)

        avg_rent = None
        if not isinstance(rent_data, Exception) and "error" not in (rent_data or {}):
            val = rent_data.get("avg_rent_3_3m2")
            if val:
                avg_rent = float(val)

        # SEMAS/NAVER는 Exception이면 None 처리
        if isinstance(semas_density, Exception):
            semas_density = None
        if isinstance(naver_trend, Exception):
            naver_trend = None

        logger.debug(
            f"[district_ranking] {dong_name}: sales={sales_growth}, pop={pop_growth}, "
            f"rent={avg_rent}, density={semas_density}, trend={naver_trend}"
        )
        return {
            "district": dong_name,
            "sales_growth": sales_growth,
            "pop_growth": pop_growth,
            "avg_rent": avg_rent,
            "semas_density": semas_density,
            "naver_trend": naver_trend,
        }
    except Exception as e:
        logger.warning(f"[district_ranking] {dong_name} 점수 산출 실패 (무시): {e}")
        return {
            "district": dong_name,
            "sales_growth": None,
            "pop_growth": None,
            "avg_rent": None,
            "semas_density": None,
            "naver_trend": None,
        }


def _normalize_and_rank(
    raw: list[dict],
    population_weight: bool = True,
    monthly_rent_budget: int = 0,
    store_area: float = 15.0,
    vacancy_rate_map: dict[str, float] | None = None,
    business_type: str = "",
    operfit_map: dict[str, dict] | None = None,
) -> list[dict]:
    """
    16개 동의 원시 지표를 0~100으로 정규화 후 가중 합산 → 내림차순 정렬

    population_weight=True  : 매출35% + 인구20% + 임대료15% + 접근성10% + 경쟁밀도10% + 트렌드10%
    population_weight=False : 매출50% + 인구10% + 임대료20% + 접근성 5% + 경쟁밀도 5% + 트렌드10%
    데이터 결측 시 활성 지표에만 합 1.0 강제 정규화 (결측 가중치를 활성에 비례 분배).
    monthly_rent_budget > 0 : 예산 초과 동에 페널티 적용
    vacancy_rate_map        : 공실률 높은 동 추가 패널티 (5~10%: -15%, 10%+: -30%)
    business_type           : 용도지역 규제 패널티 판정용 업종 코드
    operfit_map             : inflow_scorer 결과 (dict[dong, InflowResult])
                              Hansen(1959) + E2SFCA(2009) 교통·집객 접근성 점수
    """
    if not raw:
        return []

    vacancy_rate_map = vacancy_rate_map or {}
    operfit_map = operfit_map or {}

    # A안 가중치 (합 1.00) — 6개 지표 독립 정의. 매출에서만 차감하던 기존 비대칭 제거.
    # 데이터 결측 시 활성 지표만 모아 합 1.0 강제 정규화 (결측 가중치를 활성에 비례 분배).
    if population_weight:
        weights = {
            "sales": 0.35,  # 결과 변수 — 가장 강한 신호
            "pop": 0.20,  # 매출 선행 지표 (유동인구 성장률)
            "rent": 0.15,  # 비용 부담 (낮을수록 점수 ↑)
            "access": 0.10,  # 인구 유입 메커니즘 (Hansen + E2SFCA)
            "density": 0.10,  # 경쟁 포화도 (낮을수록 점수 ↑)
            "trend": 0.10,  # 미래 시장 성장 (NAVER 트렌드)
        }
    else:
        weights = {
            "sales": 0.50,
            "pop": 0.10,
            "rent": 0.20,
            "access": 0.05,
            "density": 0.05,
            "trend": 0.10,
        }

    # 예산 기반 평당 허용 임대료 계산 (0이면 필터 비활성화)
    budget_per_3_3m2 = (monthly_rent_budget / max(store_area, 1)) if monthly_rent_budget > 0 else 0

    def _minmax(vals: list[float | None], reverse: bool = False, floor: float = 0.0) -> list[float]:
        """
        None = DB 데이터 없음 → 중간값(50) 부여, 실데이터만 min-max 정규화.
        전체가 None이거나 실데이터 편차 없으면 50 반환.

        floor: 최저 score 하한 (UX 가독성용). 기본 0, 예: 10 이면 최저 10, 최고 100.
            - 정규화 결과가 0으로 떨어지면 프론트에서 "데이터 없음"처럼 보여 혼란 → 소폭 floor 부여.
        """
        real = [v for v in vals if v is not None]
        if not real:
            return [50.0] * len(vals)
        lo, hi = min(real), max(real)
        scale = 100.0 - floor
        results = []
        for v in vals:
            if v is None:
                results.append(50.0)  # 데이터 없음 → 중간값
            elif hi == lo:
                results.append(50.0)
            else:
                raw_norm = (v - lo) / (hi - lo)  # 0.0 ~ 1.0
                if reverse:
                    raw_norm = 1.0 - raw_norm
                results.append(raw_norm * scale + floor)
        return results

    # [FIX] pop/sales/rent 모두 floor 10 적용 — min-max 최저값이 0 으로 떨어져
    # IndicatorGrid 에 "유동인구 0" 같은 결측처럼 보이는 문제 방지 (UX 가독성).
    sales_norm = _minmax([r["sales_growth"] for r in raw], floor=10.0)
    pop_norm = _minmax([r["pop_growth"] for r in raw], floor=10.0)
    rent_norm = _minmax([r["avg_rent"] for r in raw], reverse=True, floor=10.0)  # 낮은 임대료 = 높은 점수

    # SEMAS 밀집도 (역방향 — 적을수록 좋음: 경쟁 낮음)
    density_vals = [r.get("semas_density") for r in raw]
    has_density = any(v is not None for v in density_vals)
    density_norm = _minmax(density_vals, reverse=True) if has_density else None

    # NAVER 트렌드 (정방향 — 높을수록 좋음: 상승 상권)
    trend_vals = [r.get("naver_trend") for r in raw]
    has_trend = any(v is not None for v in trend_vals)
    trend_norm = _minmax(trend_vals) if has_trend else None

    # inflow — 교통·집객 접근성 (Hansen 1959 + E2SFCA 2009, 0~100 사전 정규화)
    operfit_vals = [operfit_map.get(r["district"], {}).get("inflow_score") if operfit_map else None for r in raw]
    has_operfit = any(v is not None for v in operfit_vals)
    operfit_norm = _minmax(operfit_vals, floor=10.0) if has_operfit else None

    # 데이터 커버리지 로그
    sales_hit = sum(1 for r in raw if r["sales_growth"] is not None)
    pop_hit = sum(1 for r in raw if r["pop_growth"] is not None)
    rent_hit = sum(1 for r in raw if r["avg_rent"] is not None)
    density_hit = sum(1 for v in density_vals if v is not None)
    trend_hit = sum(1 for v in trend_vals if v is not None)
    operfit_hit = sum(1 for v in operfit_vals if v is not None)
    logger.info(
        f"[district_ranking] 데이터 커버리지 — 매출:{sales_hit}/16, 인구:{pop_hit}/16, "
        f"임대료:{rent_hit}/16, 밀집도:{density_hit}/16, 트렌드:{trend_hit}/16, "
        f"접근성:{operfit_hit}/16"
    )

    # 활성 지표만 추려서 합 1.0으로 강제 정규화 (결측 지표 가중치 → 활성에 비례 분배).
    # sales/pop/rent 는 항상 활성 (raw 입력에서 None 이어도 _minmax 가 50 으로 채움).
    active = {"sales": weights["sales"], "pop": weights["pop"], "rent": weights["rent"]}
    if has_density:
        active["density"] = weights["density"]
    if has_trend:
        active["trend"] = weights["trend"]
    if has_operfit:
        active["access"] = weights["access"]
    _total = sum(active.values())
    norm = {k: v / _total for k, v in active.items()}  # 합 == 1.0 보장

    ranked = []
    for i, r in enumerate(raw):
        score = sales_norm[i] * norm["sales"] + pop_norm[i] * norm["pop"] + rent_norm[i] * norm["rent"]
        if density_norm is not None and "density" in norm:
            score += density_norm[i] * norm["density"]
        if trend_norm is not None and "trend" in norm:
            score += trend_norm[i] * norm["trend"]
        if operfit_norm is not None and "access" in norm:
            score += operfit_norm[i] * norm["access"]

        # 예산 초과 페널티
        if budget_per_3_3m2 > 0 and r["avg_rent"] is not None and r["avg_rent"] > 0:
            if r["avg_rent"] > budget_per_3_3m2 * 1.5:
                score *= 0.5
            elif r["avg_rent"] > budget_per_3_3m2:
                ratio = r["avg_rent"] / budget_per_3_3m2
                score *= max(1.0 - (ratio - 1.0) * 0.5, 0.5)

        # 공실률 패널티: 높은 공실 = 상권 활력 저하
        vacancy_rate = vacancy_rate_map.get(r["district"], 0.0)
        if vacancy_rate >= 10.0:
            score *= 0.70  # 공실률 10% 이상: -30%
        elif vacancy_rate >= 5.0:
            score *= 0.85  # 공실률 5~10%: -15%

        # 용도지역 규제 패널티: legal_node와 동일한 DISTRICT_ZONE_MAP/ZONING_RULES 사용
        zoning_risk = "safe"
        if business_type:
            type_label = BIZ_TYPE_LABEL.get(business_type.lower(), business_type)
            zone = DISTRICT_ZONE_MAP.get(r["district"], "근린상업지역")
            rules = ZONING_RULES.get(zone, {"허용": [], "제한": []})
            if type_label in rules["제한"]:
                zoning_risk = "danger"
                score *= 0.50  # 영업 제한 업종: -50%
            elif type_label not in rules["허용"] and rules["제한"]:
                zoning_risk = "caution"
                score *= 0.85  # 회색지역: -15%

        _operfit_entry = operfit_map.get(r["district"], {}) if operfit_map else {}
        ranked.append(
            {
                **r,
                # None → 0.0으로 직렬화 (프론트엔드 호환)
                "sales_growth": r["sales_growth"] if r["sales_growth"] is not None else 0.0,
                "pop_growth": r["pop_growth"] if r["pop_growth"] is not None else 0.0,
                "avg_rent": r["avg_rent"] if r["avg_rent"] is not None else 0.0,
                "score": round(score, 1),
                "sales_score": round(sales_norm[i], 1),
                "pop_score": round(pop_norm[i], 1),
                "rent_score": round(rent_norm[i], 1),
                "density_score": round(density_norm[i], 1) if density_norm else None,
                "trend_score": round(trend_norm[i], 1) if trend_norm else None,
                "inflow_score": _operfit_entry.get("inflow_score"),
                "inflow_subway": _operfit_entry.get("subway_sub"),
                "inflow_bus": _operfit_entry.get("bus_sub"),
                "inflow_fclty": _operfit_entry.get("fclty_sub"),
                "semas_density": r.get("semas_density"),
                "naver_trend": r.get("naver_trend"),
                "vacancy_rate": vacancy_rate,
                "zoning_risk": zoning_risk,
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)

    for idx, item in enumerate(ranked):
        item["rank"] = idx + 1

    return ranked


async def district_ranking_node(state: AgentState) -> dict:
    """
    마포구 16개 행정동 전수 스코어링 노드

    market / population / legal 에이전트와 함께 asyncio.gather로 병렬 실행됩니다.
    결과:
      scouting_results  : 점수 내림차순 전체 랭킹 리스트 (vacancy_rate 포함)
      winner_district   : 1순위 행정동
      top_3_candidates  : 2~4순위 행정동 리스트
    """
    business_type = state.get("business_type", "카페")
    population_weight = state.get("population_weight", True)
    monthly_rent_budget = state.get("monthly_rent_budget", 0)
    store_area = state.get("store_area", 15.0)

    # 사용자 선택 동 목록 (winner 결정 범위)
    _raw_target_dists = state.get("target_districts") or [state.get("target_district", "")]
    _target_dists_set = set(d for d in _raw_target_dists if d)
    # 캐시 키에 포함할 정렬된 선택 동 문자열
    _sorted_dists_key = ",".join(sorted(_target_dists_set)) if _target_dists_set else "all"

    # 캐시 키 정규화 (constants.py 단일 소스)
    _normalized_biz = BIZ_NORMALIZE.get(business_type.lower(), business_type)

    # Redis 캐시 조회 — 동일 조건 재요청 시 DB 쿼리 없이 즉시 반환 (DEBUG=true 시 스킵)
    # v5: target_districts를 캐시 키에 포함 — 선택 동이 다르면 별도 캐시 (v4 무효화)
    # v6: top_3도 선택 동 내로 제한 (v5 잘못된 top_3 캐시 무효화)
    # v7: inflow(교통·집객 접근성) 점수 추가 — Hansen/E2SFCA (v6 무효화)
    # v8: A안 가중치 + 정규화 강제 (매출 5%→35%, 인구 45%→20%, 합 1.0 보장 — v7 무효화)
    # v9: _fetch_naver_trend 외부 API → DB 조회 전환 (v8 trend_score=None 캐시 무효화)
    # v10: inflow_scorer 가중치(subway 10→25/bus 40/fclty 50→35) + baseline 정규화 도입 (v9 무효화)
    # v11: vacancy_spots 에 spot 단위 score/subway_distance_m/competitor_count_500m 추가 (v10 무효화)
    # v12: spot 점수에 자사 영업구역 안전 항목 추가 (territory_radius_m 반영) — brand_name/territory 키 포함.
    _brand_key = state.get("brand_name") or "none"
    _territory_key = state.get("territory_radius_m") or "none"
    cache_key = (
        f"v12:ranking:{_normalized_biz}:{population_weight}:{monthly_rent_budget}:{store_area}:"
        f"{_sorted_dists_key}:{_brand_key}:{_territory_key}"
    )
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = None if settings.debug else await _redis.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            logger.info(f"[district_ranking] 캐시 히트: {cache_key}")
            try:
                await _redis.aclose()
            except Exception:
                pass
            _cached_ranked = cached_data.get("scouting_results", []) or []
            # 캐시 히트 시 winner = 사용자 선택 동 중 점수 1위 (선택 동 없으면 전체 1위)
            _user_ranked = [r for r in _cached_ranked if isinstance(r, dict) and r.get("district") in _target_dists_set]
            _winner_pool = _user_ranked if _user_ranked else ([r for r in _cached_ranked if isinstance(r, dict)] or [])
            _cached_winner = _winner_pool[0]["district"] if _winner_pool else cached_data.get("winner_district", "")
            _cached_top_3 = [
                r["district"]
                for r in _cached_ranked
                if isinstance(r, dict)
                and r.get("district") != _cached_winner
                and r.get("district") in _target_dists_set
            ][:3]
            # winner_pool[0]은 사용자 선택 동 중 1위 = _cached_winner. 점수도 거기서 가져와야
            # verdict의 동 이름과 점수가 일치한다. 이전엔 _cached_ranked[0](마포 16동 전체 1위)의
            # 점수를 사용해 "공덕동 (63.8점)"처럼 다른 동의 점수가 표시되는 거짓 양성이 있었다.
            _cached_winner_score = 0
            if _winner_pool:
                _first = _winner_pool[0] if isinstance(_winner_pool[0], dict) else {}
                _cached_winner_score = _first.get("score") or 0
            cached_ranking_attr = build_attribution(
                agent_id="district_ranking",
                display_name="행정동 랭킹",
                kind="Python",
                sources=[
                    "district_sales",
                    "golmok_rent",
                    "seoul_adstrd_flpop",
                    "naver_trend_quarterly",
                    "store_quarterly",
                ],
                verdict=f"1위 {_cached_winner} ({_cached_winner_score}점)",
                reasoning="마포 16동 정량 스코어링 — 매출/인구/임대료 가중합 (캐시)",
                confidence=0.9,
            )
            _cached_analysis = dict(state.get("analysis_results", {}))
            _cached_analysis["district_ranking_result"] = {"agent_attribution": cached_ranking_attr}
            _cached_operfit = cached_data.get("inflow_results") or {}
            _cached_winner_operfit = _cached_operfit.get(_cached_winner, {}) if _cached_winner else {}
            return {
                "scouting_results": cached_data["scouting_results"],
                "winner_district": _cached_winner,  # ranked[0] 재계산값
                "top_3_candidates": _cached_top_3,  # ranked[1:4] 재계산값
                "vacancy_applied": cached_data.get("vacancy_applied", False),
                "vacancy_spots": cached_data.get("vacancy_spots", []),
                "current_agent": "district_ranking",
                "analysis_results": _cached_analysis,
                "analysis_metrics": {
                    "inflow_score": _cached_winner_operfit.get("inflow_score"),
                    "inflow_subway": _cached_winner_operfit.get("subway_sub"),
                    "inflow_bus": _cached_winner_operfit.get("bus_sub"),
                    "inflow_fclty": _cached_winner_operfit.get("fclty_sub"),
                    "inflow_evidence": _cached_winner_operfit.get("evidence"),
                },
                "inflow_results": _cached_operfit,
                "agent_attribution": cached_ranking_attr,
            }
    except Exception as e:
        logger.warning(f"[district_ranking] Redis 캐시 조회 실패 (무시하고 계속): {e}")
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass
        _redis = None

    # 직접 호출 시(예: /analyze/quick) parallel_analysis_node를 거치지 않으므로
    # stale Task 방지를 위해 자체 초기화
    _clear_shared_population_cache()

    logger.info(
        f"--- [DISTRICT RANKING] 마포구 {len(MAPO_DISTRICTS)}개 행정동 스코어링 시작 "
        f"(인구가중치={population_weight}, 예산={monthly_rent_budget:,}원, 면적={store_area}평) ---"
    )

    _init_optional_clients()

    if db_client.engine is None:
        await db_client.connect()

    # 16개 동 점수 + 공실률 병렬 로드 (세마포어로 동시 DB 접근 제한)
    async def _guarded_score(dong: str) -> dict:
        async with _db_semaphore:
            return await _score_single_district(dong, business_type)

    tasks = [_guarded_score(dong) for dong in MAPO_DISTRICTS]

    # inflow은 Phase 0 (inflow_node)에서 미리 계산되어 state에 주입됨.
    # 그래프 우회 호출(/analyze/quick)에서는 state에 없을 수 있어 fallback 실행.
    operfit_map: dict[str, dict] = state.get("inflow_results") or {}

    if not operfit_map:

        async def _fallback_operfit() -> dict[str, dict]:
            try:
                return await _score_inflow()
            except Exception as exc:
                logger.warning(f"[district_ranking] inflow fallback 실패 (무시하고 계속): {exc}")
                return {}

        raw_scores, vacancy_result, operfit_map = await asyncio.gather(
            asyncio.gather(*tasks),
            _load_vacancy_map(),
            _fallback_operfit(),
        )
    else:
        raw_scores, vacancy_result = await asyncio.gather(
            asyncio.gather(*tasks),
            _load_vacancy_map(),
        )
    vacancy_rate_map, vacancy_applied = vacancy_result

    ranked = _normalize_and_rank(
        list(raw_scores),
        population_weight=population_weight,
        monthly_rent_budget=monthly_rent_budget,
        store_area=store_area,
        vacancy_rate_map=vacancy_rate_map,
        business_type=business_type,
        operfit_map=operfit_map,
    )

    # winner = 사용자 선택 동(_target_dists_set) 중 점수 1위
    # 선택 동이 없거나 전체 16개 선택인 경우 전체 1위 반환
    _user_ranked = [r for r in ranked if r.get("district") in _target_dists_set]
    winner_row = _user_ranked[0] if _user_ranked else (ranked[0] if ranked else None)
    winner = winner_row["district"] if winner_row else state.get("target_district", "서교동")
    # top_3: 사용자 선택 동 중 winner 제외 상위 3개
    top_3 = [r["district"] for r in ranked if r["district"] != winner and r["district"] in _target_dists_set][:3]

    # winner + top_3 + 사용자 선택 동의 실제 공실 좌표 조회
    target_district = state.get("target_district", winner)
    dong_names = list(dict.fromkeys([winner, target_district] + top_3))
    vacancy_spots = await _load_vacancy_spots(dong_names)

    # winner 동 spot 들에 spot 단위 점수 부여.
    # 가중치: 경쟁 0.35 + 지하철 0.30 + 매물 0.15 + 자사영업구역 안전 0.20.
    # 사용자 입력 territory_radius_m 안 자사 매장 ≥1 spot 은 영업구역 안전=0 → 후순위.
    if winner and vacancy_spots:
        _brand = state.get("brand_name")
        _territory = state.get("territory_radius_m")
        spot_subway, spot_stores, spot_same_brand = await _load_spot_score_features(business_type, _brand)
        _score_winner_spots(
            vacancy_spots,
            winner,
            spot_subway,
            spot_stores,
            same_brand_coords=spot_same_brand,
            territory_radius_m=_territory,
        )

    logger.info(
        f"--- [DISTRICT RANKING] 완료 - 1위: {winner}, 후보: {top_3}, 공실반영={vacancy_applied}, 스팟={len(vacancy_spots)}개 ---"
    )

    # Redis 캐시 저장
    if _redis is not None:
        try:
            await _redis.set(
                cache_key,
                json.dumps(
                    {
                        "scouting_results": ranked,
                        "winner_district": winner,
                        "top_3_candidates": top_3,
                        "vacancy_applied": vacancy_applied,
                        "vacancy_spots": vacancy_spots,
                        "inflow_results": operfit_map,
                    },
                    ensure_ascii=False,
                ),
                ex=_CACHE_TTL,
            )
            logger.info(f"[district_ranking] 캐시 저장: {cache_key} (TTL: {_CACHE_TTL}s)")
        except Exception as e:
            logger.warning(f"[district_ranking] Redis 캐시 저장 실패 (무시): {e}")
        finally:
            try:
                await _redis.aclose()
            except Exception:
                pass

    # winner_row는 사용자 선택 동 중 1위 = winner. 점수도 거기서 가져와야 verdict의
    # 동 이름과 점수가 일치한다. 이전엔 ranked[0](마포 16동 전체 1위) 점수를 사용해
    # 다른 동의 점수가 표시되는 거짓 양성이 있었다 (캐시 path도 동일 fix).
    _winner_score = 0
    if winner_row:
        _winner_score = winner_row.get("score") or 0
    _sources = [
        "district_sales",
        "golmok_rent",
        "seoul_adstrd_flpop",
        "naver_trend_quarterly",
        "store_quarterly",
    ]
    if operfit_map:
        _sources.extend(["dong_subway_access", "bus_boarding_daily", "seoul_adstrd_fclty"])
    ranking_attr = build_attribution(
        agent_id="district_ranking",
        display_name="행정동 랭킹",
        kind="Python",
        sources=_sources,
        verdict=f"1위 {winner} ({_winner_score}점)",
        reasoning=(
            "마포 16동 정량 스코어링 — 매출/인구/임대료"
            + (" + 교통·집객 접근성(Hansen 1959, E2SFCA 2009)" if operfit_map else "")
            + " 가중합"
        ),
        confidence=0.9,
    )
    _analysis = dict(state.get("analysis_results", {}))
    _analysis["district_ranking_result"] = {"agent_attribution": ranking_attr}

    # winner 동의 inflow_score를 analysis_metrics에 주입 (main.py가 market_report.accessibility로 사용)
    winner_operfit = operfit_map.get(winner, {}) if operfit_map else {}

    return {
        "scouting_results": ranked,
        "winner_district": winner,
        "top_3_candidates": top_3,
        "vacancy_applied": vacancy_applied,
        "vacancy_spots": vacancy_spots,
        "current_agent": "district_ranking",
        "analysis_results": _analysis,
        "analysis_metrics": {
            "inflow_score": winner_operfit.get("inflow_score"),
            "inflow_subway": winner_operfit.get("subway_sub"),
            "inflow_bus": winner_operfit.get("bus_sub"),
            "inflow_fclty": winner_operfit.get("fclty_sub"),
            "inflow_evidence": winner_operfit.get("evidence"),
        },
        "inflow_results": operfit_map,
        "agent_attribution": ranking_attr,
    }
