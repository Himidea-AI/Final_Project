# -*- coding: utf-8 -*-
import asyncio
import json
import re
import os
from src.agents.graph import compile_workflow  # 그래프 컴파일 함수
from src.schemas.state import AgentState

async def test_main():
    # --- [리모컨 세팅: 여기만 바꾸면 됩니다] ---
    # Unicode escape를 사용하여 한글 깨짐 방지 (연남동, 스타벅스)
    target_district = "\uc5f0\ub0a8\ub3d9" 
    brand_name = "\uc2a4\ud0c0\ubc85\uc2a4"
    # ------------------------------------------

    # UTF-8 출력 강제 (윈도우 터미널 대응)
    import sys
    import io
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print(f"[{target_district}] [{brand_name}] simulation starting...")
    print(f"DEBUG: target_district = {target_district}")
    print(f"DEBUG: target_district hex = {target_district.encode('utf-8').hex()}")

    # 1. 초기 상태 설정 (필수 필드 포함)
    initial_state = {
        "messages": [],
        "business_type": "\uce74\ud398", # 카페
        "target_district": target_district,
        "brand_name": brand_name,
        "market_data": {},
        "legal_info": [],
        "analysis_results": {},
        "analysis_metrics": {},
        "current_agent": "start",
        "next_step": "",
        "errors": []
    }

    # 2. 전체 그래프(엔진) 실행
    app = compile_workflow()
    
    print("--- 워크플로우 실행 중... (약 10~20초 소요) ---")
    final_state = await app.ainvoke(initial_state)
    
    # 3. 결과 리포트 추출
    full_report = final_state["analysis_results"].get("market_summary", "")

    # 4. [핵심 기능] JSON 블록만 추출하여 Pretty Print
    print("\n" + "="*20 + " [추출된 정형 데이터] " + "="*20)
    try:
        # [JSON_START]와 [JSON_END] 사이의 내용만 정규식으로 추출
        match = re.search(r"\[JSON_START\](.*?)\[JSON_END\]", full_report, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            # 마크다운 코드 블록 및 불필요한 공백 제거
            json_str = re.sub(r'```json|```', '', json_str).strip()
            json_data = json.loads(json_str)
            # 예쁘게 출력 (indent=4)
            print(json.dumps(json_data, indent=4, ensure_ascii=False))
        else:
            print("[X] JSON 태그를 찾을 수 없습니다. 리포트 형식을 확인하세요.")
            # 태그가 없을 경우 전체 리포트 출력 (디버깅)
            print(f"--- 원본 리포트 (일부) ---\n{full_report[:500]}...")
    except Exception as e:
        print(f"[X] JSON 파싱 오류: {e}")
        if 'json_str' in locals():
            print(f"--- 파싱 시도한 데이터 ---\n{json_str}")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_main())
