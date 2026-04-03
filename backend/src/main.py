"""
마포구 프랜차이즈 상권분석 시뮬레이터 — FastAPI 메인 앱
"""
import uuid
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agents.graph import compile_graph
from src.agents.state import AgentState

app = FastAPI(
    title="마포구 프랜차이즈 상권분석 시뮬레이터",
    description="AI Agent 기반 프랜차이즈 출점 시뮬레이션 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 중에는 전체 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 서버가 시작될 때 미로피쉬가 포함된 LangGraph 전체 파이프라인을 컴파일합니다.
simulator_graph = compile_graph()

class SimulationInput(BaseModel):
    target_district: str
    business_type: str
    brand_name: str = ""

@app.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {"status": "ok"}

@app.post("/simulate")
def run_simulation(req: SimulationInput):
    """
    프론트엔드에서 버튼 클릭 시 미로피쉬 엔진 및 LangGraph 파이프라인 가동 요청
    - async 대신 동기 함수(def)를 사용하여 내부의 asyncio.run(Ollama) 충돌 방지 
    """
    request_id = str(uuid.uuid4())
    print(f"\n[API] 시뮬레이션 요청 수신 (ID: {request_id}) - 타겟: {req.target_district}, 업종: {req.business_type}")
    
    # 1. 초기 Pydantic State 객체 세팅
    initial_state = AgentState(
        request_id=request_id,
        target_district=req.target_district,
        business_type=req.business_type,
        brand_name=req.brand_name
    )
    
    # 2. 미로피쉬 엔진이 탑재된 LangGraph 노드 파이프라인 실행
    final_state = simulator_graph.invoke(initial_state)
    
    # 최종 결과물 추출 (강건성 확보)
    threat_level = "Unknown"
    mirofish_twin_summary = "No log generated"
    
    # LangGraph invoke의 결과물(final_state)은 Pydantic이 풀린 dict 형태임
    analysis_res = final_state.get("analysis_results") if isinstance(final_state, dict) else getattr(final_state, "analysis_results", None)
    
    # None일 수 있으므로 hasattr 대신 get 등을 사용
    if analysis_res:
        impact = analysis_res.get("cannibalization_impact", {}) if isinstance(analysis_res, dict) else getattr(analysis_res, "cannibalization_impact", {})
        if isinstance(impact, dict):
            threat_level = impact.get("threat_level", "Unknown")
            mirofish_twin_summary = impact.get("mirofish_twin_summary", "No log generated")
            
    # 지도 렌더링용 위도/경도 매핑 (하드코딩 샘플)
    MOCK_COORDS = {
        "망원1동": {"lat": 37.5561, "lng": 126.9023},
        "망원2동": {"lat": 37.5615, "lng": 126.9002},
        "합정동": {"lat": 37.5494, "lng": 126.9130},
        "서교동": {"lat": 37.5540, "lng": 126.9200},
    }
    
    req_district = final_state.get("target_district", req.target_district) if isinstance(final_state, dict) else getattr(final_state, "target_district", req.target_district)
    coords = MOCK_COORDS.get(req_district, {"lat": 37.5636, "lng": 126.9084}) # 마포구청 부근 디폴트

    return {
        "message": "Simulation completed successfully",
        "request_id": request_id,
        "district": req_district,
        "coordinates": coords,
        "threat_level": threat_level,
        "mirofish_summary": mirofish_twin_summary,
        "ai_recommendation": f"위험도: {threat_level} / 에이전트 결론 산출 완료"
    }

@app.get("/report/{request_id}")
async def get_report(request_id: str):
    """시뮬레이션 리포트 조회"""
    return {"message": "Not implemented yet"}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """시뮬레이션 진행 상태 조회"""
    return {"message": "Not implemented yet"}

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
