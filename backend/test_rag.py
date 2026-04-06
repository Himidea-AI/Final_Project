import asyncio
from src.agents.graph import compile_graph
from langchain_core.messages import HumanMessage
from src.config.settings import settings
import json

async def test_district(district: str):
    print(f"\n>>> TESTING DISTRICT: {district}")
    app = compile_graph()
    
    initial_state = {
        "messages": [HumanMessage(content=f"{district} 카페 창업 분석")],
        "business_type": "cafe",
        "brand_name": "TestBrand",
        "target_district": district,
        "market_data": {},
        "legal_info": [],
        "analysis_results": {},
        "current_agent": "start",
        "next_step": "",
        "errors": []
    }
    
    # PROD 모드 확인
    print(f"Current App Mode: {settings.app_mode}")
    
    final_state = await app.ainvoke(initial_state)
    
    print(f"--- RESULT FOR {district} ---")
    print(f"Legal Risks Summary: {final_state['analysis_results'].get('legal_risks')}")
    print(f"Number of legal docs found: {len(final_state.get('legal_info', []))}")
    if final_state.get('legal_info'):
        print(f"First doc relevance: {final_state['legal_info'][0]['metadata'].get('relevance')}")

async def main():
    # 1. 도화동 테스트
    await test_district("도화동")
    # 2. 서교동 테스트
    await test_district("서교동")

if __name__ == "__main__":
    asyncio.run(main())
