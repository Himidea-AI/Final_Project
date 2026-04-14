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
from src.agents.graph import compile_graph
from src.agents.tools import MarketDataTool


# tools.py가 kakao_store 기반으로 수정됐으므로 monkey-patch 불필요
def apply_patches():
    print("[INFO] kakao_store 기반 tools.py 사용 — 패치 불필요")


def restore_patches():
    pass


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

    if node_name == "parallel_analysis":
        analysis = output.get("analysis_results", {})
        metrics = output.get("analysis_metrics", {})
        risks = analysis.get("legal_risks", [])
        print(f"  [상권 등급]   : {metrics.get('district_grade', 'N/A')}")
        print(f"  [경쟁 점수]   : {metrics.get('competition_score', 'N/A')}")
        print(f"  [인구 점수]   : {metrics.get('population_score', 'N/A')}")
        print(f"  [법률 리스크] : {output.get('overall_legal_risk', 'N/A')} ({len(risks)}개 항목)")
        for r in risks[:3]:
            print(f"    - {r.get('type', '?')} | {r.get('level', '?')} | {r.get('summary', '')[:60]}")
        if len(risks) > 3:
            print(f"    ... 외 {len(risks) - 3}개 항목")

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
