"""
5-Agent 시뮬레이션 스크립트
실데이터(PostgreSQL) 기반으로 5개 에이전트가 정상 작동하는지 검증

실행 방법:
    cd backend
    python simulate_agents.py

또는 특정 동/업종/브랜드를 인자로 넘길 수 있습니다:
    python simulate_agents.py --district 서교동 --business 카페 --brand "Antigravity Coffee"
"""

import asyncio
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

# backend/src 를 모듈 경로에 추가 (IDE 없이 실행 시 필요)
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage
from sqlalchemy import text
from src.agents.graph import compile_graph
from src.agents import tools as _tools_module
from src.agents.tools import MarketDataTool


# ────────────────────────────────────────────────
# Monkey-patch: get_competitor_stats
# tools.py 원본을 건드리지 않고 시뮬레이션 중에만 교체
# ────────────────────────────────────────────────
_BUSINESS_TYPE_TO_CODE: Dict[str, str] = {
    "카페": "I212", "커피": "I212", "비알코올": "I212",
    "음식점": "I201", "한식": "I201", "식당": "I201",
    "치킨": "I206", "피자": "I207", "분식": "I209",
    "주점": "I211", "편의점": "G209",
    "베이커리": "I213", "빵": "I213",
}

_original_get_competitor_stats = MarketDataTool.get_competitor_stats


async def _patched_get_competitor_stats(
    self, lat: float, lon: float, industry_m_code: str, radius_m: int = 500
) -> Dict[str, Any]:
    """location_vector 없이 lat/lon 유클리드 거리로 경쟁 업체를 검색하는 패치 버전"""
    resolved_code = _BUSINESS_TYPE_TO_CODE.get(industry_m_code, industry_m_code)
    lat_delta = radius_m / 111000.0
    lon_delta = radius_m / 88500.0

    async with self.db_client.get_session() as session:
        query = text("""
            SELECT store_name, industry_s, lat, lon,
                   sqrt(power((lat - :lat) * 111000, 2) + power((lon - :lon) * 88500, 2)) AS distance_m
            FROM store_info
            WHERE industry_m_code = :ind_code
              AND dong_code LIKE '11440%'
              AND lat BETWEEN :lat_min AND :lat_max
              AND lon BETWEEN :lon_min AND :lon_max
            ORDER BY distance_m ASC
        """)
        result = await session.execute(query, {
            "lat": lat, "lon": lon, "ind_code": resolved_code,
            "lat_min": lat - lat_delta, "lat_max": lat + lat_delta,
            "lon_min": lon - lon_delta, "lon_max": lon + lon_delta,
        })
        competitors = result.fetchall()
        competitors = [c for c in competitors if c.distance_m <= radius_m]

    if not competitors:
        return {"competitor_count": 0, "density_level": "LOW",
                "summary": f"반경 {radius_m}m 내 경쟁 업체가 없습니다."}

    count = len(competitors)
    avg_dist = sum(c.distance_m for c in competitors) / count
    density = "HIGH" if count > 10 else "MEDIUM" if count > 3 else "LOW"
    return {
        "competitor_count": count, "density_level": density,
        "avg_distance_m": round(avg_dist, 1),
        "nearest_competitor": competitors[0].store_name,
        "summary": f"반경 {radius_m}m 내 {count}개의 경쟁 업체 (평균 {round(avg_dist, 1)}m).",
    }


def apply_patches():
    MarketDataTool.get_competitor_stats = _patched_get_competitor_stats
    print("[PATCH] MarketDataTool.get_competitor_stats → lat/lon 거리 버전 적용")


def restore_patches():
    MarketDataTool.get_competitor_stats = _original_get_competitor_stats
    print("[PATCH] MarketDataTool.get_competitor_stats → 원본 복원 완료")


# ────────────────────────────────────────────────
# 초기 상태 정의
# ────────────────────────────────────────────────
def build_initial_state(district: str, business_type: str, brand_name: str) -> dict:
    return {
        "messages": [
            HumanMessage(
                content=f"{district} 지역에 {brand_name}({business_type}) 창업을 검토 중입니다. "
                        f"상권 분석, 유동인구 분석, 법률 리스크를 종합 검토해 주세요."
            )
        ],
        "business_type": business_type,
        "brand_name": brand_name,
        "target_district": district,
        "market_data": {
            "lat": 37.5565,
            "lng": 126.9239,
        },
        "legal_info": [],
        "scouting_results": [],
        "top_3_candidates": [],
        "winner_district": district,
        "brand_analysis": {},
        "analysis_results": {},
        "analysis_metrics": {},
        "overall_legal_risk": "Caution",
        "current_agent": "start",
        "next_step": "",
        "errors": [],
    }


# ────────────────────────────────────────────────
# 결과 출력 헬퍼
# ────────────────────────────────────────────────
SEPARATOR = "=" * 70

def print_section(title: str, content: str = "", max_len: int = 800):
    print(f"\n{SEPARATOR}")
    print(f"  {title}")
    print(SEPARATOR)
    if content:
        truncated = content[:max_len] + ("..." if len(content) > max_len else "")
        print(truncated)


def print_agent_result(node_name: str, output: dict):
    """각 에이전트 실행 결과를 보기 좋게 출력"""
    print(f"\n{'─'*70}")
    print(f"  ▶ 노드 완료: [{node_name.upper()}]")
    print(f"{'─'*70}")

    if node_name == "supervisor":
        print(f"  다음 단계 결정: {output.get('next_step', '?')}")

    elif node_name == "market_analyst":
        analysis = output.get("analysis_results", {})
        report = analysis.get("market_report", "")
        metrics = output.get("analysis_metrics", {})
        print(f"  [상권 등급]   : {metrics.get('district_grade', 'N/A')}")
        print(f"  [경쟁 점수]   : {metrics.get('competition_score', 'N/A')}")
        print(f"  [임대 적합성] : {metrics.get('rent_affordability', 'N/A')}")
        if report:
            print(f"\n  [리포트 미리보기]\n{report[:400]}...")

    elif node_name == "population_analyst":
        analysis = output.get("analysis_results", {})
        report = analysis.get("population_report", "")
        metrics = output.get("analysis_metrics", {})
        print(f"  [인구 점수]    : {metrics.get('population_score', 'N/A')}")
        print(f"  [주요 타겟]    : {metrics.get('main_target_age', 'N/A')}")
        print(f"  [피크 시간대]  : {metrics.get('peak_time', 'N/A')}")
        if report:
            print(f"\n  [리포트 미리보기]\n{report[:400]}...")

    elif node_name == "legal_analyst":
        analysis = output.get("analysis_results", {})
        risks = analysis.get("legal_risks", [])
        overall = output.get("overall_legal_risk", "N/A")
        print(f"  [종합 리스크]  : {overall}")
        print(f"  [법률 항목 수] : {len(risks)}개")
        for r in risks[:5]:
            print(f"    - {r.get('type', '?')} | {r.get('level', '?')} | {r.get('summary', '')[:60]}")
        if len(risks) > 5:
            print(f"    ... 외 {len(risks) - 5}개 항목")

    elif node_name == "synthesis":
        analysis = output.get("analysis_results", {})
        final = analysis.get("final_report", {})
        print(f"  [종합 요약]    : {final.get('summary', 'N/A')}")
        print(f"  [법률 리스크]  : {final.get('overall_legal_risk', 'N/A')}")
        sim = final.get("profit_simulation", {})
        print(f"  [월 예상 매출] : {sim.get('monthly_revenue', 0):,}원")
        print(f"  [월 순이익]    : {sim.get('net_profit', 0):,}원")
        print(f"  [수익률]       : {sim.get('margin_rate', 0)}%")
        comp = final.get("competitor_analysis", {})
        print(f"  [경쟁 점포 수] : {comp.get('count', 'N/A')}개 ({comp.get('density', 'N/A')})")
        print(f"\n  [최종 제언]\n{final.get('final_recommendation', 'N/A')}")

    errors = output.get("errors", [])
    if errors:
        print(f"\n  ⚠️  에러 목록:")
        for e in errors:
            print(f"    - {e}")


# ────────────────────────────────────────────────
# 메인 시뮬레이션
# ────────────────────────────────────────────────
async def run_simulation(district: str, business_type: str, brand_name: str):
    print_section(
        f"5-Agent 시뮬레이션 시작",
        f"  대상 지역  : {district}\n"
        f"  업종       : {business_type}\n"
        f"  브랜드명   : {brand_name}"
    )

    apply_patches()
    try:
        app = compile_graph()
        initial_state = build_initial_state(district, business_type, brand_name)

        agent_order = []
        final_state = dict(initial_state)
        start_time = time.time()

        print("\n[그래프 스트리밍 시작...]\n")

        async for event in app.astream(initial_state):
            for node_name, output in event.items():
                agent_order.append(node_name)
                final_state.update(output)
                print_agent_result(node_name, output)

        elapsed = time.time() - start_time

        # ── 최종 요약 ──
        print_section("시뮬레이션 완료 — 최종 요약")
        print(f"  실행 순서  : {' → '.join(agent_order)}")
        print(f"  총 소요 시간: {elapsed:.1f}초")

        analysis = final_state.get("analysis_results", {})
        print(f"\n  [수집된 분석 키]")
        for k in analysis.keys():
            val = analysis[k]
            if isinstance(val, str):
                print(f"    ✅ {k}: {val[:60]}...")
            elif isinstance(val, list):
                print(f"    ✅ {k}: {len(val)}개 항목")
            elif isinstance(val, dict):
                print(f"    ✅ {k}: dict ({len(val)} keys)")
            else:
                print(f"    ✅ {k}: {val}")

        errors_total = final_state.get("errors", [])
        if errors_total:
            print(f"\n  ❌ 누적 에러 ({len(errors_total)}건):")
            for e in errors_total:
                print(f"    - {e}")
        else:
            print("\n  ✅ 에러 없음 — 5개 에이전트 정상 작동 확인")

        print(f"\n{SEPARATOR}\n")

    finally:
        restore_patches()


def main():
    parser = argparse.ArgumentParser(description="5-Agent 시뮬레이션")
    parser.add_argument("--district", default="서교동", help="분석 행정동 (기본: 서교동)")
    parser.add_argument("--business", default="카페", help="업종 (기본: 카페)")
    parser.add_argument("--brand", default="Antigravity Coffee", help="브랜드명")
    args = parser.parse_args()

    asyncio.run(run_simulation(args.district, args.business, args.brand))


if __name__ == "__main__":
    main()
