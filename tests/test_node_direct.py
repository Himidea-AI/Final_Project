import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# .env 로드
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# backend/src 경로 추가
sys.path.append(str(project_root / "backend"))


async def test_node_logic():
    print("--- [NODE LOGIC TEST] market_analyst_node 실데이터 분석 테스트 (MOKCED) ---")

    try:
        from unittest.mock import AsyncMock

        from src.agents.nodes.market_analyst import market_analyst_node, market_tool
        from src.main import map_state_to_simulation_output

        # DB 호출 모킹 (실제 DB 연결 없이 로직 검증)
        market_tool.get_population_trends = AsyncMock(
            return_value={
                "current_pop": 150000,
                "summary": "최근 1년 유동인구 15% 증가 추세",
                "qoq_growth": 3.5,
                "yoy_growth": 15.2,
                "trend": "성장",
            }
        )
        market_tool.get_commercial_insights = AsyncMock(
            return_value={
                "statistical_summary": "건당 평균 결제액 12,500원, 20대 여성 고객 주도, 전년 대비 매출 8.5% 증가",
                "yoy_growth": 8.5,
                "qoq_growth": 1.2,
                "trend": "성장",
            }
        )
        market_tool.get_competitor_stats = AsyncMock(
            return_value={
                "summary": "반경 500m 내 경쟁 업체 12개 존재, 밀집도 높음",
                "competitor_count": 12,
                "density_level": "HIGH",
            }
        )
        market_tool.get_rent_insight = AsyncMock(
            return_value={
                "summary": "평당 임대료 18만원 수준으로 마포구 평균 대비 높음",
                "avg_rent_3_3m2": 180000,
                "affordability": "CAUTION",
            }
        )

        # 1. 테스트용 가짜 상태(State) 준비
        mock_state = {
            "target_district": "서교동",
            "business_type": "카페",
            "brand_name": "메가커피",
            "market_data": {"lat": 37.5565, "lng": 126.9239},
            "analysis_results": {},
            "analysis_metrics": {},
            "messages": [],
        }

        # 2. 노드 직접 실행 (PROD 모드 강제 및 LLM 모킹)
        print("🚀 노드 실행 중 (LLM 응답 모킹)...")
        import src.agents.nodes.market_analyst as analyst_mod

        analyst_mod.settings.app_mode = "PROD"

        # LLM 응답 모킹 (Quota 에러 우회 및 파싱 검증용)
        mock_llm = AsyncMock()
        mock_response = AsyncMock()
        mock_response.content = (
            "서교동은 현재 매우 활발한 상권입니다. 유동인구가 전년 대비 15% 증가했으며, "
            "카페 업종의 밀집도가 높지만 객단가가 상승하고 있어 수익성이 양호합니다.\n\n"
            "[프랜차이즈 전략팀 총평]\n"
            "- 가장 큰 기회: 20대 젊은 층의 안정적인 유입과 높은 객단가 형성.\n"
            "- 가장 큰 리스크: 임대료 상승 속도가 매출 성장보다 빨라질 가능성.\n\n"
            "[JSON_START]{\n"
            '  "grade": "EXCELLENT",\n'
            '  "growth_rate": 15.2,\n'
            '  "competition_score": 0.85,\n'
            '  "rent_affordability": "GOOD"\n'
            "}[JSON_END]"
        )
        mock_llm.ainvoke.return_value = mock_response

        # analyst_mod 내부의 get_fast_llm을 모킹
        analyst_mod.get_fast_llm = lambda: mock_llm

        result_node = await market_analyst_node(mock_state)

        # 3. main.py의 매핑 함수 호출 (분리 여부 확인)
        print("🔗 API 응답 매핑 중...")
        final_response = map_state_to_simulation_output(result_node, "test-uuid-123")

        # 4. 결과 출력
        print("\n" + "=" * 50)
        print("✅ [결과 검증 성공! (MOCKED LLM)]")
        print("-" * 50)
        print(f"1. analysis_report (줄글 리포트):\n{final_response.get('analysis_report')}")
        print("-" * 50)
        print("2. analysis_metrics (숫자 지표):")
        print(json.dumps(final_response.get("analysis_metrics"), indent=2, ensure_ascii=False))
        print("=" * 50)

    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # OS 호환성을 위한 루프 설정
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_node_logic())
