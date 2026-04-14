import sys
from pathlib import Path
import os
import uuid
import asyncio
from typing import Any, Dict

# [ModuleNotFoundError 해결] src 디렉토리를 path에 추가하여 'import schemas' 등이 가능하게 함
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

# 절대 경로 임포트로 통일 (uvicorn src.main:app 실행 대응)
from src.schemas.simulation_input import SimulationInput
from src.agents.graph import compile_workflow
from src.services.biz_mapper import BizMapper
from src.services.auth import AuthService

app = FastAPI(
    title="마포구 프랜차이즈 상권분석 시뮬레이터",
    description="AI Agent 기반 프랜차이즈 출점 시뮬레이션 API",
    version="0.1.0",
)

# LangGraph 컴파일된 앱 초기화
app_graph = compile_workflow()

# CORS 설정: 프론트엔드(localhost:3000) 접근 허용 및 Docker nginx (localhost) 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [디폴트 값] 마포구청 (혹은 홍대입구역) 좌표 - 데이터 수집 실패 시 대비
DEFAULT_LAT = 37.5663
DEFAULT_LNG = 126.9015


def map_state_to_simulation_output(state: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """
    LangGraph AgentState를 프론트엔드 SimulationOutput 스키마로 변환
    [B1 고도화] 분석 리포트와 정량 지표(metrics)를 분리하여 반환
    """
    md = state.get("market_data", {})
    analysis = state.get("analysis_results", {})
    metrics = state.get("analysis_metrics", {})
    target_dist = state.get("target_district", "마포구")

    # [좌표 기본값 처리]
    lat = md.get("lat") if md.get("lat") else DEFAULT_LAT
    lng = md.get("lng") if md.get("lng") else DEFAULT_LNG

    # 법률 리스크 리스트 변환 (5인 체제 데이터 구조에 맞게 최적화)
    legal_risks_raw = analysis.get("legal_risks") or []
    legal_risks = [
        {
            "type": r.get("type", "General"),
            "risk_level": {"safe": "LOW", "caution": "MEDIUM", "danger": "HIGH"}.get(
                r.get("level", "safe").lower(), "LOW"
            ),
            "detail": r.get("summary", ""),
        }
        for r in legal_risks_raw
    ]

    # [B1 고도화] 응답 구조 재설계
    response_data = {
        "request_id": request_id,
        "target_district": target_dist,
        "analysis_report": analysis.get("market_summary", ""),  # 줄글 리포트
        "analysis_metrics": metrics,  # 차트용 정량 데이터
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
        "overall_legal_risk": analysis.get("overall_legal_risk", "safe"),
        "legal_risks": legal_risks,
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
        "financial_report": md.get("financial_metrics", {}),
    }

    print(f"\nDEBUG: [{target_dist}] API 응답 전송 (Grade: {metrics.get('district_grade', 'N/A')})")
    return response_data


@app.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {"status": "ok"}


@app.get("/report/{report_id}")
async def get_report(report_id: str):
    """결과 리포트용 Mock API - 프론트엔드 연결 검증용"""
    return {"status": "success", "data": {"request_id": report_id, "message": "This is a mock report response."}}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """작업 상태 조회용 Mock API - 프론트엔드 연결 검증용"""
    return {
        "status": "success",
        "data": {"job_id": job_id, "progress": 100, "message": "This is a mock status response."},
    }


@app.post("/analyze")
async def analyze_location(input_data: SimulationInput):
    """상권 분석 및 지도 데이터 요청"""
    request_id = str(uuid.uuid4())
    print(f"--- [API] /analyze 요청 수신: {input_data.target_district} ({input_data.business_type}) ---")

    initial_state = {
        "messages": [HumanMessage(content=f"{input_data.target_district} {input_data.brand_name} 분석 시작")],
        "business_type": input_data.business_type,
        "brand_name": input_data.brand_name,
        "target_district": input_data.target_district,
        "market_data": {},
        "legal_info": [],
        "analysis_results": {},
        "analysis_metrics": {},
        "overall_legal_risk": "safe",
        "current_agent": "start",
        "next_step": "",
        "errors": [],
    }

    try:
        final_state = await asyncio.wait_for(app_graph.ainvoke(initial_state), timeout=90.0)
        result = map_state_to_simulation_output(final_state, request_id)
        return {"status": "success", "data": result}
    except Exception as e:
        print(f"!!! [API ERROR] !!! {str(e)}")
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# 사업자등록번호 → 프랜차이즈 매핑 API
# ---------------------------------------------------------------------------


class BizLookupRequest(BaseModel):
    biz_number: str
    company_name: str


@app.post("/biz/lookup")
async def biz_lookup(req: BizLookupRequest):
    """사업자등록번호 + 기업명으로 프랜차이즈 브랜드 매핑"""
    mapper = BizMapper(
        nts_api_key=os.environ.get("NTS_API_KEY", ""),
    )
    try:
        result = await mapper.map_franchise(req.biz_number, req.company_name)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# 회원가입 API
# ---------------------------------------------------------------------------


class SignupRequest(BaseModel):
    companyName: str
    bizNumber: str
    contactName: str
    position: str = ""
    email: str
    phone: str
    storeCount: str = ""
    password: str
    plan: str = "starter"
    agreeTerms: bool = False


@app.post("/auth/signup")
async def signup(req: SignupRequest):
    """회원가입 — 사업자 검증 + 브랜드 매핑 + DB 저장"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await auth.signup(req.model_dump())
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# 로그인 API
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/auth/login")
async def login(req: LoginRequest):
    """로그인 — 이메일/비밀번호 검증 + 브랜드 정보 반환"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await run_in_threadpool(auth.login, req.email, req.password)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# 초대코드 API
# ---------------------------------------------------------------------------


class InviteCodeRequest(BaseModel):
    owner_id: str
    max_uses: int = 10


@app.post("/auth/invite-code")
async def generate_invite_code(req: InviteCodeRequest):
    """팀장이 초대코드를 발급"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await run_in_threadpool(auth.generate_invite_code, req.owner_id, req.max_uses)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


class VerifyInviteRequest(BaseModel):
    code: str


@app.post("/auth/verify-invite")
async def verify_invite_code(req: VerifyInviteRequest):
    """초대코드 검증 — 유효하면 팀장의 기업정보(사업자번호, 기업명, 가맹점수) 반환"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await run_in_threadpool(auth.verify_invite_code, req.code)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# 매니저 회원가입/로그인 API
# ---------------------------------------------------------------------------


class ManagerSignupRequest(BaseModel):
    inviteCode: str
    contactName: str
    position: str = ""
    email: str
    phone: str
    password: str


@app.post("/auth/manager/signup")
async def manager_signup(req: ManagerSignupRequest):
    """매니저 회원가입 — 초대코드로 팀장 기업정보 자동 상속"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await run_in_threadpool(auth.manager_signup, req.model_dump())
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/auth/manager/login")
async def manager_login(req: LoginRequest):
    """매니저 로그인"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await run_in_threadpool(auth.manager_login, req.email, req.password)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/simulate")
async def run_simulation(input_data: SimulationInput):
    """기본 시뮬레이션 엔드포인트"""
    request_id = str(uuid.uuid4())
    initial_state = {
        "messages": [HumanMessage(content=f"{input_data.target_district} 시뮬레이션 시작")],
        "business_type": input_data.business_type,
        "brand_name": input_data.brand_name,
        "target_district": input_data.target_district,
        "market_data": {},
        "legal_info": [],
        "analysis_results": {},
        "analysis_metrics": {},
        "overall_legal_risk": "safe",
        "current_agent": "start",
        "next_step": "",
        "errors": [],
    }
    try:
        final_state = await asyncio.wait_for(app_graph.ainvoke(initial_state), timeout=90.0)
        return map_state_to_simulation_output(final_state, request_id)
    except Exception as e:
        return {"status": "error", "message": str(e)}
