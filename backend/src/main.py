"""
마포구 프랜차이즈 상권분석 시뮬레이터 — FastAPI 메인 앱
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="마포구 프랜차이즈 상권분석 시뮬레이터",
    description="AI Agent 기반 프랜차이즈 출점 시뮬레이션 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 중에는 전체 허용, 프로덕션에서 도메인 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {"status": "ok"}


@app.post("/simulate")
async def run_simulation():
    """시뮬레이션 실행 요청"""
    # TODO: SimulationInput 스키마로 요청 받기
    # TODO: LangGraph 워크플로우 실행
    # TODO: 결과 반환
    return {"message": "Not implemented yet"}


@app.get("/report/{request_id}")
async def get_report(request_id: str):
    """시뮬레이션 리포트 조회"""
    # TODO: DB에서 결과 조회
    return {"message": "Not implemented yet"}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """시뮬레이션 진행 상태 조회"""
    # TODO: Redis에서 Job 상태 조회
    return {"message": "Not implemented yet"}
