"""서울 실시간 도시데이터 API 클라이언트 (citydata_ppltn).

서울시 OpenAPI: 27개 주요 POI(인구밀집지역)의 실시간 혼잡도/인구/연령 분포.
30분 주기로 갱신되는 데이터를 fetching → DB upsert.

API: http://openapi.seoul.go.kr:8088/{KEY}/xml/citydata_ppltn/1/1/{POI_ID}
응답 형식: XML (서울시 표준)

ABM 시뮬에서 사용:
    seoul_realtime_hotspots 테이블의 동×시간×연령 분포를
    score_store.popularity_boost 동적 가중치로 활용 (Peak hour 정확도 개선용).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET

import httpx


SEOUL_API_BASE = "http://openapi.seoul.go.kr:8088"

# ABM 마포 검증 범위 (4 POI)
MAPO_POI_IDS: list[str] = [
    "POI007",  # 홍대 관광특구 (서교동)
    "POI053",  # 합정역 (합정동)
    "POI073",  # 연남동
    "POI106",  # 월드컵공원 (상암동)
]

# 향후 서울 전체 27개 POI 확장 가능 (API 문서 참조)


def _parse_one_record(area_cd: str, root: ET.Element) -> dict[str, Any] | None:
    """citydata_ppltn XML 응답 → DB 스키마 dict.

    응답 구조:
        <Map>
          <SeoulRtd.citydata_ppltn>
            <AREA_NM>...</AREA_NM> <AREA_CD>...</AREA_CD>
            <AREA_CONGEST_LVL>...</AREA_CONGEST_LVL>
            <PPLTN_RATE_20>...</PPLTN_RATE_20>
            <PPLTN_TIME>2026-04-26 10:50</PPLTN_TIME>
            ...
          </SeoulRtd.citydata_ppltn>
        </Map>

    None 반환 시 응답 비정상 (POI 미존재, API 오류 등).
    """
    # tag 이름에 점(.) 포함 — ET 는 직접 검색 대신 iter 로 매치
    live = next((el for el in root if el.tag == "SeoulRtd.citydata_ppltn"), None)
    if live is None:
        # API 오류 응답 (RESULT/CODE 등) 일 수도 있음
        return None

    def _txt(tag: str) -> str | None:
        el = live.find(tag)
        return el.text.strip() if el is not None and el.text else None

    def _f(tag: str) -> float | None:
        v = _txt(tag)
        try:
            return float(v) if v not in (None, "") else None
        except ValueError:
            return None

    def _i(tag: str) -> int | None:
        v = _txt(tag)
        try:
            return int(v) if v not in (None, "") else None
        except ValueError:
            return None

    # PPLTN_TIME → datetime (서울시간 가정)
    ts_str = _txt("PPLTN_TIME") or ""
    try:
        # 서울시 형식: "2026-04-25 14:30"
        ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        ts = datetime.now(timezone.utc)

    return {
        "area_cd": area_cd,
        "area_nm": _txt("AREA_NM") or "",
        "collected_at": ts,
        "congest_level": _txt("AREA_CONGEST_LVL"),
        "congest_msg": _txt("AREA_CONGEST_MSG"),
        "pop_min": _i("AREA_PPLTN_MIN"),
        "pop_max": _i("AREA_PPLTN_MAX"),
        "male_rate": _f("MALE_PPLTN_RATE"),
        "female_rate": _f("FEMALE_PPLTN_RATE"),
        "age_0_10": _f("PPLTN_RATE_0"),
        "age_10s": _f("PPLTN_RATE_10"),
        "age_20s": _f("PPLTN_RATE_20"),
        "age_30s": _f("PPLTN_RATE_30"),
        "age_40s": _f("PPLTN_RATE_40"),
        "age_50s": _f("PPLTN_RATE_50"),
        "age_60s": _f("PPLTN_RATE_60"),
        "age_70_plus": _f("PPLTN_RATE_70"),
        "resident_rate": _f("RESNT_PPLTN_RATE"),
        "visitor_rate": _f("NON_RESNT_PPLTN_RATE"),
        # cmrc_* 는 별도 API (citydata 전체) 에서만 제공 → 본 함수는 None
        "cmrc_total_level": None,
        "cmrc_payment_cnt": None,
        "cmrc_payment_amt_min": None,
        "cmrc_payment_amt_max": None,
    }


def fetch_realtime_hotspot_one(
    poi_id: str,
    api_key: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any] | None:
    """단일 POI 실시간 데이터 조회."""
    key = api_key or os.environ.get("SEOUL_OPENDATA_KEY")
    if not key:
        raise RuntimeError("SEOUL_OPENDATA_KEY 환경변수 없음")

    url = f"{SEOUL_API_BASE}/{key}/xml/citydata_ppltn/1/1/{poi_id}"
    with httpx.Client(timeout=timeout) as client:
        r = client.get(url)
        r.raise_for_status()
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError:
        return None
    return _parse_one_record(poi_id, root)


def fetch_realtime_hotspots(
    poi_ids: list[str] | None = None,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """여러 POI 동시 조회 (직렬 — citydata API 는 동시 호출 제한 있음)."""
    targets = poi_ids or MAPO_POI_IDS
    out: list[dict[str, Any]] = []
    for pid in targets:
        try:
            rec = fetch_realtime_hotspot_one(pid, api_key=api_key)
            if rec:
                out.append(rec)
        except Exception as e:
            print(f"[seoul_realtime] {pid} 조회 실패: {e}")
    return out
