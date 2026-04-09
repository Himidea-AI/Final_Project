import sys
import os
import asyncio
import json
from pathlib import Path
from dotenv import load_dotenv

# .env 로드
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# backend/src 경로 추가
sys.path.append(str(project_root / "backend"))

from langchain_core.messages import HumanMessage
from src.agents.graph import compile_graph
from src.main import map_state_to_simulation_output
from src.agents.nodes.market_analyst import market_tool
from unittest.mock import AsyncMock

async def test_full_simulation():
    print("="*60)
    print("🚀 [FULL WORKFLOW TEST] 실데이터 기반 지능형 시뮬레이션 시작 (MOCKED DB)")
    print("="*60)
    
    # DB 툴 모킹 (실제 DB 연결 없이 AI 로직 및 워크플로우 검증)
    market_tool.get_population_trends = AsyncMock(return_value={
        "current_pop": 158200, "qoq_growth": 4.2, "yoy_growth": 12.5, 
        "summary": "서교동은 최근 1년 유동인구가 12.5% 증가한 초우량 상권입니다.",
        "peak_hour": 18, "dominant_age_group": "2030대"
    })
    market_tool.get_commercial_insights = AsyncMock(return_value={
        "avg_monthly_revenue": 45000000, "qoq_growth": 8.5, "yoy_growth": 14.2,
        "dominant_customer": "female_20s", "trend": "성장",
        "statistical_summary": "건당 평균 결제액 14,200원, 20대 여성 고객 주도, 전년 대비 매출 14.2% 상향세"
    })
    market_tool.get_competitor_stats = AsyncMock(return_value={
        "competitor_count": 14, "density_level": "HIGH", "avg_distance_m": 120.5,
        "summary": "반경 500m 내 경쟁 업체 14개로 밀집도가 높으나 배후 수요가 충분함"
    })
    market_tool.get_rent_insight = AsyncMock(return_value={
        "avg_rent_3_3m2": 210000, "affordability": "CAUTION",
        "summary": "평당 임대료 21만원 수준으로 마포구 평균 대비 높으나 수익성으로 커버 가능"
    })
    
    # 1. 그래프 컴파일
    app = compile_graph()
    
    # 2. 초기 상태 설정
    initial_state = {
        "messages": [
            HumanMessage(content="서교동에 메가커피 창업하고 싶어. 상권 분석이랑 인구 분석 좀 해줘.")
        ],
        "business_type": "카페",
        "brand_name": "메가커피",
        "target_district": "서교동",
        "market_data": {"lat": 37.5565, "lng": 126.9239},
        "legal_info": [],
        "analysis_results": {},
        "analysis_metrics": {},
        "current_agent": "start",
        "next_step": "",
        "errors": []
    }
    
    # 3. 그래프 실행 및 이벤트 로깅
    print("\n--- [시뮬레이션 루프 가동] ---")
    final_state = initial_state
    
    try:
        async for event in app.astream(initial_state):
            for node_name, output in event.items():
                print(f"\n▶ [실행 완료 노드: {node_name}]")
                if "next_step" in output:
                    print(f"👉 Supervisor 결정: {output['next_step']}")
                
                # 상태 업데이트
                final_state.update(output)
                # analysis_results/metrics는 Dict이므로 명시적 병합 제안 (LangGraph가 처리하지만 안전하게)
                if "analysis_results" in output:
                    final_state["analysis_results"].update(output["analysis_results"])
                if "analysis_metrics" in output:
                    final_state["analysis_metrics"].update(output["analysis_metrics"])

        # 4. 최종 결과 매핑 (main.py 로직 활용)
        print("\n" + "="*60)
        print("🔗 최종 데이터 매핑 및 JSON 생성 중...")
        final_output = map_state_to_simulation_output(final_state, "simulation-full-test-001")
        
        # 5. 결과 출력
        print("\n[최종 종합 분석 결과 (JSON)]")
        print(json.dumps(final_output, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"\n❌ 시뮬레이션 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_full_simulation())
