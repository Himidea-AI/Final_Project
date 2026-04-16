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
from src.schemas.simulation_output import SimulationOutput
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
_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost").split(
    ","
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

# [디폴트 값] 마포구청 (혹은 홍대입구역) 좌표 - 데이터 수집 실패 시 대비
DEFAULT_LAT = 37.5663
DEFAULT_LNG = 126.9015

# 동일 파라미터 동시 요청 중복 실행 방지 (simulate + analyze 동시 호출 시 파이프라인 공유)
_pending_pipelines: Dict[str, "asyncio.Task[Any]"] = {}


def _pipeline_key(input_data: Any) -> str:
    return f"{input_data.target_district}:{input_data.business_type}:{input_data.brand_name}"


async def _run_pipeline(input_data: Any) -> Dict[str, Any]:
    """파이프라인 실행. 동일 키로 이미 실행 중인 Task가 있으면 공유하여 대기."""
    key = _pipeline_key(input_data)

    if key in _pending_pipelines and not _pending_pipelines[key].done():
        print(f"[DEDUP] 동일 요청 대기 중 — 기존 파이프라인 공유: {key}")
        return await _pending_pipelines[key]

    initial_state = {
        "messages": [HumanMessage(content=f"{input_data.target_district} {input_data.brand_name} 분석 시작")],
        "business_type": input_data.business_type,
        "brand_name": input_data.brand_name,
        "target_district": input_data.target_district,
        "market_data": {},
        "legal_info": [],
        "scouting_results": [],
        "top_3_candidates": [],
        "winner_district": input_data.target_district,
        "brand_analysis": {},
        "analysis_results": {},
        "analysis_metrics": {},
        "overall_legal_risk": "safe",
        "current_agent": "start",
        "next_step": "",
        "errors": [],
    }

    task: asyncio.Task[Any] = asyncio.create_task(
        asyncio.wait_for(app_graph.ainvoke(initial_state), timeout=120.0)
    )
    _pending_pipelines[key] = task
    try:
        return await task
    finally:
        _pending_pipelines.pop(key, None)


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

    # 법률 리스크 리스트 변환
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

    # 랭킹 데이터
    district_rankings = analysis.get("district_rankings", [])
    winner_district = analysis.get("winner_district", target_dist)
    top_3_candidates = analysis.get("top_3_candidates", [])

    # ai_recommendation — synthesis FinalStrategyResult.summary
    final_report = analysis.get("final_report") or {}
    ai_recommendation = (
        final_report.get("summary")
        or analysis.get("market_summary", "")[:120]
        or ""
    )

    # market_report — 프론트엔드 chartData용 7개 정규화 지표 (0~100)
    competition_score = float(metrics.get("competition_score") or 0.5)
    growth_rate = float(metrics.get("growth_rate") or 5)
    rent_raw = str(metrics.get("rent_affordability") or "CAUTION").upper()
    pop_score = float(metrics.get("population_score") or 7)
    grade = str(metrics.get("district_grade") or "NORMAL").upper()

    # 임대료: SAFE=저렴(높은 점수), DANGER=비쌈(낮은 점수)
    rent_index = {"SAFE": 80, "CAUTION": 50, "DANGER": 25, "상": 25, "중": 50, "하": 80}.get(rent_raw, 50)
    estimated_revenue = {"EXCELLENT": 90, "GOOD": 75, "NORMAL": 60, "RISKY": 40}.get(grade, 60)
    competition_intensity = min(int(competition_score * 100), 100)
    district_score = float({"EXCELLENT": 90, "GOOD": 75, "NORMAL": 60, "RISKY": 40}.get(grade, 60))

    market_report = {
        "floating_population": min(int(pop_score * 10), 100),
        "rent_index": rent_index,
        "competition_intensity": competition_intensity,
        "estimated_revenue": estimated_revenue,
        "survival_rate": max(100 - competition_intensity, 30),
        "growth_potential": min(int(abs(growth_rate) * 5), 100),
        "accessibility": 75,
    }

    # [B1 고도화] 응답 구조 재설계
    response_data = {
        "request_id": request_id,
        "target_district": target_dist,
        "winner_district": winner_district,
        "top_3_candidates": top_3_candidates,
        "district_rankings": district_rankings,
        "ai_recommendation": ai_recommendation,
        "market_report": market_report,
        "analysis_report": analysis.get("market_summary", ""),
        "analysis_metrics": metrics,
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
                "score": district_score,
                "revenue": md.get("avg_revenue", 30000000),
                "bep": 14,
                "survival": float(market_report["survival_rate"]),
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

    print(f"\nDEBUG: [{target_dist}] API 응답 전송 (Grade: {grade}, ai_rec: {ai_recommendation[:40]}...)")
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
    from src.config.constants import MAPO_DISTRICTS

    if input_data.target_district not in MAPO_DISTRICTS:
        return {
            "status": "error",
            "message": f"지원하지 않는 행정동입니다: {input_data.target_district}. 마포구 16개 동만 지원합니다.",
        }

    request_id = str(uuid.uuid4())
    print(f"--- [API] /analyze 요청 수신: {input_data.target_district} ({input_data.business_type}) ---")

    try:
        final_state = await _run_pipeline(input_data)
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


@app.get("/auth/managers")
async def get_managers(owner_id: str):
    """팀장 소속 매니저 전체 목록 조회 (승인 상태 포함)"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await run_in_threadpool(auth.get_managers, owner_id)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


class ManagerApprovalBody(BaseModel):
    owner_id: str
    assigned_gu: str | None = None
    assigned_dongs: list[str] | None = None


@app.patch("/auth/manager/{manager_id}/approve")
async def approve_manager(manager_id: str, body: ManagerApprovalBody):
    """팀장이 매니저 가입을 승인"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await run_in_threadpool(
            auth.approve_manager, body.owner_id, manager_id, body.assigned_gu, body.assigned_dongs
        )
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.patch("/auth/manager/{manager_id}/reject")
async def reject_manager(manager_id: str, body: ManagerApprovalBody):
    """팀장이 매니저 가입을 거절"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await run_in_threadpool(auth.reject_manager, body.owner_id, manager_id)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# 마이페이지 API
# ---------------------------------------------------------------------------


class ProfileUpdateBody(BaseModel):
    contact_name: str | None = None
    position: str | None = None
    phone: str | None = None
    store_count: int | None = None


class PasswordChangeBody(BaseModel):
    role: str  # master or manager
    old_password: str
    new_password: str


@app.get("/auth/user/{user_id}")
async def get_user_profile(user_id: str):
    """팀장 프로필 조회"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        return await run_in_threadpool(auth.get_user_profile, user_id)
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.put("/auth/user/{user_id}")
async def update_user_profile(user_id: str, body: ProfileUpdateBody):
    """팀장 프로필 수정"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        return await run_in_threadpool(auth.update_user_profile, user_id, body.model_dump(exclude_none=True))
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/auth/manager/{manager_id}/profile")
async def get_manager_profile(manager_id: str):
    """매니저 프로필 조회"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        return await run_in_threadpool(auth.get_manager_profile, manager_id)
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.put("/auth/manager/{manager_id}/profile")
async def update_manager_profile(manager_id: str, body: ProfileUpdateBody):
    """매니저 프로필 수정"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        return await run_in_threadpool(auth.update_manager_profile, manager_id, body.model_dump(exclude_none=True))
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.put("/auth/user/{user_id}/password")
async def change_password(user_id: str, body: PasswordChangeBody):
    """비밀번호 변경 (팀장/매니저 공용)"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        return await run_in_threadpool(auth.change_password, user_id, body.role, body.old_password, body.new_password)
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/auth/organization/{owner_id}")
async def get_organization(owner_id: str):
    """팀장 조직 전체 정보 (멀티테넌시)"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        return await run_in_threadpool(auth.get_organization, owner_id)
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# 시뮬레이션 API
# ---------------------------------------------------------------------------


@app.post("/simulate")
async def run_simulation(input_data: SimulationInput):
    """기본 시뮬레이션 엔드포인트"""
    from src.config.constants import MAPO_DISTRICTS

    if input_data.target_district not in MAPO_DISTRICTS:
        return {
            "status": "error",
            "message": f"지원하지 않는 행정동입니다: {input_data.target_district}. 마포구 16개 동만 지원합니다.",
        }

    request_id = str(uuid.uuid4())
    try:
        final_state = await _run_pipeline(input_data)
        return map_state_to_simulation_output(final_state, request_id)
    except Exception as e:
        print(f"!!! [SIMULATE ERROR] !!! {str(e)}")
        return {
            "request_id": request_id,
            "target_district": input_data.target_district,
            "ai_recommendation": "",
            "market_report": None,
            "comparison": [],
            "legal_risks": [],
            "overall_legal_risk": "safe",
            "simulation_months": 12,
            "monthly_projection": [],
            "analysis_report": f"분석 중 오류가 발생했습니다: {str(e)}",
            "analysis_metrics": {},
            "map_data": None,
            "financial_report": {},
        }
