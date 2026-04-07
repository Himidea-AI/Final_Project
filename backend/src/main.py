import sys
import os
from pathlib import Path

# [ModuleNotFoundError 해결] src 디렉토리를 path에 추가하여 'import schemas' 등이 가능하게 함
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
import uuid
import asyncio
import json
from typing import Any, Dict

# 절대 경로 임포트로 통일 (uvicorn src.main:app 실행 대응)
from src.schemas.simulation_input import SimulationInput
from src.agents.graph import compile_graph

app = FastAPI(
    title="마포구 프랜차이즈 상권분석 시뮬레이터",
    description="AI Agent 기반 프랜차이즈 출점 시뮬레이션 API",
    version="0.1.0",
)

# LangGraph 컴파일된 앱 초기화
app_graph = compile_graph()

# CORS 설정: 프론트엔드(localhost:3000) 접근 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [디폴트 값] 마포구청 (혹은 홍대입구역) 좌표 - 데이터 수집 실패 시 대비
DEFAULT_LAT = 37.5663
DEFAULT_LNG = 126.9015


def map_state_to_simulation_output(
    state: Dict[str, Any], request_id: str
) -> Dict[str, Any]:
    """
    LangGraph AgentState를 프론트엔드 SimulationOutput 스키마로 변환
    """
    md = state.get("market_data", {})
    analysis = state.get("analysis_results", {})
    target_dist = state.get("target_district", "마포구")

    # [좌표 기본값 처리]
    lat = md.get("lat") if md.get("lat") else DEFAULT_LAT
    lng = md.get("lng") if md.get("lng") else DEFAULT_LNG

    # 법률 리스크 리스트 변환
    legal_risks = []
    if analysis.get("legal_risks"):
        legal_risks.append(
            {
                "type": "Legal Assessment",
                "risk_level": (
                    "WARNING"
                    if any(
                        word in analysis["legal_risks"]
                        for word in ["주의", "위험", "제한", "불가"]
                    )
                    else "SAFE"
                ),
                "detail": analysis["legal_risks"],
            }
        )

    # 공통 추천 메시지
    recommendation = f"[{target_dist}] 에이전트 분석 결과: {analysis.get('market_summary', '상권 데이터 수집 중')} {analysis.get('legal_risks', '')}"

    response_data = {
        "request_id": request_id,
        "target_district": target_dist,
        "simulation_months": 12,
        "monthly_projection": [
            {
                "month": 1,
                "revenue": md.get("avg_revenue", 30000000),
                "cumulative_profit": -150000000,
            }
        ],
        "comparison": [
            {
                "district": target_dist,
                "score": md.get("competition_score", 0.78) * 100,
                "revenue": md.get("avg_revenue", 30000000),
                "bep": 14,
                "survival": 88,
                "cannibalization": 4,
            }
        ],
        "legal_risks": legal_risks,
        "ai_recommendation": recommendation,
        "map_data": {
            "center": {"lat": lat, "lng": lng},
            "markers": [
                {
                    "id": "candidate_main",
                    "lat": lat,
                    "lng": lng,
                    "label": target_dist,
                    "type": "candidate",
                }
            ],
        },
        # [BEP 분석용 Mock 데이터]
        "financial_report": md.get("financial_metrics", {}),
    }

    # [검증용 로그 출력] 터미널에서 최종 데이터 확인 가능
    print("\n" + "=" * 50)
    print(f"DEBUG: [{target_dist}] 프론트엔드 전송 최종 JSON 데이터")
    print(json.dumps(response_data, indent=2, ensure_ascii=False))
    print("=" * 50 + "\n")

    return response_data


@app.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {"status": "ok"}


@app.post("/analyze")
async def analyze_location(input_data: SimulationInput):
    """상권 분석 및 지도 데이터 요청"""
    request_id = str(uuid.uuid4())
    print(
        f"--- [API] /analyze 요청 수신: {input_data.target_district} ({input_data.business_type}) ---"
    )

    initial_state = {
        "messages": [
            HumanMessage(
                content=f"{input_data.target_district} {input_data.brand_name} 분석 시작"
            )
        ],
        "business_type": input_data.business_type,
        "brand_name": input_data.brand_name,
        "target_district": input_data.target_district,
        "market_data": {},
        "legal_info": [],
        "analysis_results": {},
        "current_agent": "start",
        "next_step": "",
        "errors": [],
    }

    try:
        final_state = await asyncio.wait_for(
            app_graph.ainvoke(initial_state), timeout=45.0
        )
        result = map_state_to_simulation_output(final_state, request_id)
        return {"status": "success", "data": result}
    except Exception as e:
        print(f"!!! [API ERROR] !!! {str(e)}")
        return {"status": "error", "message": str(e)}


@app.post("/simulate")
async def run_simulation(input_data: SimulationInput):
    """기본 시뮬레이션 엔드포인트"""
    request_id = str(uuid.uuid4())
    initial_state = {
        "messages": [
            HumanMessage(content=f"{input_data.target_district} 시뮬레이션 시작")
        ],
        "business_type": input_data.business_type,
        "brand_name": input_data.brand_name,
        "target_district": input_data.target_district,
        "market_data": {},
        "legal_info": [],
        "analysis_results": {},
        "current_agent": "start",
        "next_step": "",
        "errors": [],
    }
    try:
        final_state = await asyncio.wait_for(
            app_graph.ainvoke(initial_state), timeout=45.0
        )
        return map_state_to_simulation_output(final_state, request_id)
    except Exception as e:
        return {"status": "error", "message": str(e)}
