import logging
import sys
from pathlib import Path
import os
import uuid
import asyncio
from typing import Any, Dict

logger = logging.getLogger(__name__)

# [ModuleNotFoundError 해결] src 디렉토리를 path에 추가하여 'import schemas' 등이 가능하게 함
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

# models/ 패키지 임포트를 위해 프로젝트 루트(Final_Project/)를 path에 추가
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logger = logging.getLogger(__name__)

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

# 절대 경로 임포트로 통일 (uvicorn src.main:app 실행 대응)
from src.config.settings import settings
from src.schemas.simulation_input import SimulationInput
from src.agents.graph import compile_workflow
from src.services.biz_mapper import BizMapper
from src.services.auth import AuthService

from models.interface import ModelOutput
from models.explainability.simulation import (
    build_quarterly_projection,
)
from models.explainability.shap_analysis import explain_tcn_prediction

# ---------------------------------------------------------------------------
# Rate Limiting 설정
# ---------------------------------------------------------------------------
# LLM 파이프라인 엔드포인트(/simulate, /analyze)를 IP당 시간당 최대 횟수로 제한
_RATE_LIMITED_PATHS = {"/simulate", "/analyze"}
_RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", "10"))  # 시간당 최대 요청 수
_RATE_LIMIT_WINDOW = 3600  # 1시간(초)


async def _check_rate_limit(ip: str) -> tuple[bool, int]:
    """
    Redis 고정 윈도우 방식으로 IP별 요청 횟수를 확인합니다.
    반환값: (초과 여부, 현재 카운트)
    Redis 연결 실패 시 제한 없이 통과(fail-open)합니다.
    """
    try:
        async with aioredis.from_url(settings.redis_url, decode_responses=True) as r:
            key = f"rate:{ip}"
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, _RATE_LIMIT_WINDOW)
            return count > _RATE_LIMIT_MAX, count
    except Exception as e:
        print(f"[RATE LIMIT] Redis 연결 실패 (통과 허용): {e}")
        return False, 0


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
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Tenant-ID"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """IP당 시간당 RATE_LIMIT_MAX회로 LLM 파이프라인 엔드포인트를 보호합니다."""
    if request.url.path in _RATE_LIMITED_PATHS:
        # X-Forwarded-For → 실제 클라이언트 IP (Nginx 프록시 환경 대응)
        forwarded_for = request.headers.get("X-Forwarded-For")
        client_ip = (
            forwarded_for.split(",")[0].strip()
            if forwarded_for
            else (request.client.host if request.client else "unknown")
        )
        exceeded, count = await _check_rate_limit(client_ip)
        if exceeded:
            print(f"[RATE LIMIT] {client_ip} 시간당 한도 초과 ({count}/{_RATE_LIMIT_MAX})")
            return JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "message": f"요청 횟수가 초과되었습니다. 시간당 최대 {_RATE_LIMIT_MAX}회 요청 가능합니다.",
                },
            )
    return await call_next(request)


# [디폴트 값] 마포구청 (혹은 홍대입구역) 좌표 - 데이터 수집 실패 시 대비
DEFAULT_LAT = 37.5663
DEFAULT_LNG = 126.9015

# 동일 파라미터 동시 요청 중복 실행 방지 (simulate + analyze 동시 호출 시 파이프라인 공유)
_pending_pipelines: Dict[str, "asyncio.Task[Any]"] = {}


def _pipeline_key(input_data: Any) -> str:
    radius = getattr(input_data, "commercial_radius", 500)
    pop_w = getattr(input_data, "population_weight", True)
    rent = getattr(input_data, "monthly_rent", 0)
    area = getattr(input_data, "store_area", 15.0)
    return f"{input_data.target_district}:{input_data.business_type}:{input_data.brand_name}:{rent}:{area}:{radius}:{pop_w}"


_BIZ_TYPE_NORMALIZE: Dict[str, str] = {
    "cafe": "카페",
    "coffee": "카페",
    "restaurant": "한식",
    "food": "한식",
    "chicken": "치킨",
    "convenience": "편의점",
    "bakery": "베이커리",
}

# 마포구 행정동명 → 행정동 코드 매핑은 dong_resolver 단일 소스 사용
# (기존 main.py 내 하드코딩 매핑은 dong_resolver와 15/16개 불일치로 TCN에 잘못된 코드 전달 버그 유발)
from src.services.dong_resolver import resolve_dong_code as _resolve_dong_code

# 업종명(한국어) → 골목상권 업종코드: tools.py MarketDataTool._SALES_CODE_MAP 재사용
from src.agents.tools import MarketDataTool as _MarketDataTool

_BIZ_TO_INDUSTRY_CODE: Dict[str, str] = _MarketDataTool._SALES_CODE_MAP


async def _run_pipeline(input_data: Any) -> Dict[str, Any]:
    """파이프라인 실행. 동일 키로 이미 실행 중인 Task가 있으면 공유하여 대기."""
    key = _pipeline_key(input_data)

    if key in _pending_pipelines and not _pending_pipelines[key].done():
        print(f"[DEDUP] 동일 요청 대기 중 - 기존 파이프라인 공유: {key}")
        return await _pending_pipelines[key]

    # 프론트엔드가 영문으로 보낼 경우 한국어로 정규화 (DB 쿼리 호환)
    normalized_biz = _BIZ_TYPE_NORMALIZE.get(input_data.business_type.lower(), input_data.business_type)
    normalized_brand = input_data.brand_name or "미지정 브랜드"

    initial_state = {
        "messages": [HumanMessage(content=f"{input_data.target_district} {normalized_brand} 분석 시작")],
        "business_type": normalized_biz,
        "brand_name": normalized_brand,
        "target_district": input_data.target_district,
        "industry_filter": getattr(input_data, "industry_filter", None),
        "commercial_radius": getattr(input_data, "commercial_radius", 500),
        "monthly_rent_budget": getattr(input_data, "monthly_rent", 0),
        "store_area": getattr(input_data, "store_area", 15.0),
        "population_weight": getattr(input_data, "population_weight", True),
        "target_price_range": getattr(input_data, "target_price_range", "5to10k"),
        "operating_hours": getattr(input_data, "operating_hours", ["점심", "저녁"]),
        "initial_capital": getattr(input_data, "initial_capital", 50_000_000),
        "market_data": {},
        "legal_info": [],
        "scouting_results": [],
        "top_3_candidates": [],
        "winner_district": input_data.target_district,
        "vacancy_spots": [],
        "vacancy_applied": False,
        "brand_analysis": {},
        "analysis_results": {},
        "analysis_metrics": {},
        "overall_legal_risk": "safe",
        "current_agent": "start",
        "next_step": "",
        "errors": [],
        "competitor_intel_result": {},
    }

    task: asyncio.Task[Any] = asyncio.create_task(asyncio.wait_for(app_graph.ainvoke(initial_state), timeout=120.0))
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
    metrics = state.get("analysis_metrics") or {
        "district_grade": "NORMAL",
        "growth_rate": 5,
        "competition_score": 0.5,
        "rent_affordability": "CAUTION",
        "population_score": 7,
    }
    target_dist = state.get("target_district", "마포구")

    # [좌표 기본값 처리]
    lat = md.get("lat") if md.get("lat") else DEFAULT_LAT
    lng = md.get("lng") if md.get("lng") else DEFAULT_LNG

    # 법률 리스크 리스트 변환 (articles 포함 — 프론트 근거 조항 drawer용)
    legal_risks_raw = analysis.get("legal_risks") or []
    legal_risks = [
        {
            "type": r.get("type", "General"),
            "risk_level": {"safe": "LOW", "caution": "MEDIUM", "danger": "HIGH"}.get(
                r.get("level", "safe").lower(), "LOW"
            ),
            "detail": r.get("summary", ""),
            "recommendation": r.get("recommendation", ""),
            "articles": [
                {"article_ref": a, "content": ""} if isinstance(a, str) else a
                for a in r.get("articles", [])
            ],
        }
        for r in legal_risks_raw
    ]

    # 한글 surrogate 문자 제거 헬퍼 (N1 fix)
    def _sanitize(val):
        if isinstance(val, str):
            return val.encode("utf-8", errors="ignore").decode("utf-8")
        if isinstance(val, list):
            return [_sanitize(v) for v in val]
        if isinstance(val, dict):
            return {k: _sanitize(v) for k, v in val.items()}
        return val

    # 랭킹 데이터
    district_rankings = _sanitize(analysis.get("district_rankings", []))
    winner_district = _sanitize(analysis.get("winner_district", target_dist))
    top_3_candidates = _sanitize(analysis.get("top_3_candidates", []))
    vacancy_spots = _sanitize(state.get("vacancy_spots", []))

    # ai_recommendation — synthesis FinalStrategyResult.summary
    final_report = analysis.get("final_report") or {}
    ai_recommendation = final_report.get("summary") or analysis.get("market_summary", "")[:120] or ""

    # market_report — 프론트엔드 chartData용 7개 정규화 지표 (0~100)
    competition_score = float(metrics.get("competition_score") or 0.5)
    growth_rate = float(metrics.get("growth_rate") or 5)
    rent_raw = str(metrics.get("rent_affordability") or "CAUTION").upper()
    pop_score = float(metrics.get("population_score") or 7)
    grade = str(metrics.get("district_grade") or "NORMAL").upper()

    # district_ranking scouting_results에서 타겟 동의 실점수 추출 (동별 차별화)
    # scouting_results는 16개 동을 실DB 데이터로 개별 점수화한 결과 — LLM 버케팅보다 정밀
    _scouting = state.get("scouting_results") or analysis.get("district_rankings") or []
    _target_row = next((r for r in _scouting if r.get("district") == target_dist), None)

    if _target_row:
        # 실데이터 기반 정밀 점수 사용 (0~100 정규화)
        _sales_sc = float(_target_row.get("sales_score") or 0)
        _pop_sc = float(_target_row.get("pop_score") or 0)
        _rent_sc = float(_target_row.get("rent_score") or 0)
        _overall_sc = float(_target_row.get("score") or 0)
        # rent_score가 높을수록 임대료 저렴 → rent_index 높게
        _rent_index_r = min(int(_rent_sc), 100)
        _estimated_rev_r = min(int(_sales_sc), 100)
        _floating_pop_r = min(int(_pop_sc), 100)
        _competition_r = max(0, min(int(competition_score * 100), 100))
        _survival_r = max(int(_overall_sc * 0.9), 30)
        _growth_r = min(int(abs(growth_rate) * 5) + int(_sales_sc * 0.2), 100)
    else:
        # fallback: LLM 등급 기반 이산 버케팅
        _rent_index_r = {"SAFE": 80, "CAUTION": 50, "DANGER": 25, "상": 25, "중": 50, "하": 80}.get(rent_raw, 50)
        _estimated_rev_r = {"EXCELLENT": 90, "GOOD": 75, "NORMAL": 60, "RISKY": 40}.get(grade, 60)
        _floating_pop_r = min(int(pop_score * 10), 100)
        _competition_r = min(int(competition_score * 100), 100)
        _survival_r = max(100 - _competition_r, 30)
        _growth_r = min(int(abs(growth_rate) * 5), 100)

    competition_intensity = _competition_r
    district_score = float(_target_row.get("score") if _target_row else {"EXCELLENT": 90, "GOOD": 75, "NORMAL": 60, "RISKY": 40}.get(grade, 60))

    market_report = {
        "floating_population": _floating_pop_r,
        "rent_index": _rent_index_r,
        "competition_intensity": competition_intensity,
        "estimated_revenue": _estimated_rev_r,
        "survival_rate": _survival_r,
        "growth_potential": _growth_r,
        "accessibility": min(int(float(metrics.get("accessibility_score") or 75)), 100),
    }

    # [Simulation 실제 연동] B2 ModelOutput + build_quarterly_projection 연결
    _biz_name = state.get("business_type", "카페")
    _dong_code = _resolve_dong_code(target_dist)
    if _dong_code is None:
        # silent 서교동 fallback 금지 — 잘못된 동명을 엉뚱한 동 분석으로 응답하는 버그 방지
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 행정동입니다: '{target_dist}'. 마포구 16개 동만 지원됩니다.",
        )
    _industry_code = _BIZ_TO_INDUSTRY_CODE.get(_biz_name, "CS100010")  # 기본값: 카페
    scenarios = None
    try:
        sim_result = ModelOutput.generate(_dong_code, _industry_code, _biz_name, model="tcn")
        quarterly = build_quarterly_projection(
            bep_quarterly_simulation=sim_result["bep"]["quarterly_simulation"],
            quarterly_predictions=sim_result["revenue_forecast"]["quarterly_predictions"],
            confidence="base",
        )
        scenarios = build_scenarios(
            quarterly_predictions=sim_result["revenue_forecast"]["quarterly_predictions"],
        )
    except Exception as _sim_err:
        print(f"[SIM] ModelOutput 호출 실패 (mock 사용): {_sim_err}")
        quarterly = [
            {
                "quarter": q,
                "revenue": 30_000_000,
                "cumulative_profit": -150_000_000 + q * 30_000_000,
                "confidence_lower": 25_000_000,
                "confidence_upper": 35_000_000,
            }
            for q in range(1, 5)
        ]

    # TCN SHAP 분석 실행 — 피처별 매출 기여도 계산
    try:
        shap_result = explain_tcn_prediction(
            dong_code=_dong_code,
            industry_code=_industry_code,
        )
    except Exception as e:
        logger.warning("SHAP 분석 실패: %s", e)
        shap_result = None

    # sim_result에서 타겟 동 예측값 추출 (모델 호출 성공 시)
    _sim_closure_rate = sim_result["closure_rate"]["closure_rate"] if "sim_result" in locals() else None
    _sim_bep_months = sim_result["bep"]["bep_months"] if "sim_result" in locals() else None

    # market_report에 모델 기반 폐업률 추가 (0~1 소수)
    market_report["closure_rate"] = _sim_closure_rate

    # 타겟 동의 bep_months, closure_rate를 district_rankings에 주입
    district_rankings = [
        {
            **r,
            **(
                {"bep_months": _sim_bep_months, "closure_rate": _sim_closure_rate}
                if r.get("district") == target_dist
                else {}
            ),
        }
        for r in district_rankings
    ]

    # [B1 고도화] 응답 구조 재설계
    response_data = {
        "request_id": request_id,
        "target_district": target_dist,
        "winner_district": winner_district,
        "top_3_candidates": top_3_candidates,
        "district_rankings": district_rankings,
        "vacancy_applied": state.get("vacancy_applied", False),  # 공실 DB 반영 여부 (프론트 배지용)
        "ai_recommendation": ai_recommendation,
        "market_report": market_report,
        "analysis_report": analysis.get("market_summary", ""),
        "analysis_metrics": metrics,
        "simulation_months": 12,
        "quarterly_projection": quarterly,
        "scenarios": scenarios,
        "comparison": [
            {
                "district": target_dist,
                "score": district_score,
                "revenue": md.get("avg_revenue", 30000000),
                "bep": int(metrics.get("bep_months") or final_report.get("bep_months") or 14),
                "survival": float(market_report["survival_rate"]),
                "cannibalization": float(metrics.get("cannibalization_impact") or 4),
            }
        ],
        "overall_legal_risk": analysis.get("overall_legal_risk", "safe"),
        "legal_risks": legal_risks,
        "demographic_report": analysis.get("demographic_report"),
        "trend_forecast": analysis.get("trend_forecast"),
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
            ]
            + [
                {
                    "id": f"vacancy_{s['id']}",
                    "lat": s["lat"],
                    "lng": s["lon"],
                    "label": s["dong_name"],
                    "type": "vacancy",
                    "listing_count": s["listing_count"],
                }
                for s in vacancy_spots
                if s.get("lat") and s.get("lon")
            ],
        },
        "vacancy_spots": vacancy_spots,
        "financial_report": md.get("financial_metrics", {}),
        # TCN SHAP 분석 결과 (실패 시 None)
        "shap_result": shap_result,
        # competitor_intel 하이브리드 에이전트 결과 (경쟁 지형·카니발·차별화)
        "competitor_intel": _sanitize(state.get("competitor_intel_result") or {}),
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
# 경량 랭킹 엔드포인트 — LLM 없이 빠른 입지 순위 조회
# ---------------------------------------------------------------------------


@app.post("/analyze/quick")
async def analyze_quick(input_data: SimulationInput):
    """
    LLM 없는 경량 랭킹 엔드포인트 (district_ranking 에이전트만 실행).

    전체 LLM 파이프라인 (~30s) 대신 DB 쿼리만으로 행정동 순위를 즉시 반환합니다.
    rate limiting 적용 없음 (LLM 비용 없음).

    응답: { district_rankings, winner_district, top_3_candidates }
    """
    from src.agents.nodes.district_ranking import district_ranking_node
    from src.agents.nodes.market_analyst import db_client

    normalized_biz = _BIZ_TYPE_NORMALIZE.get(input_data.business_type.lower(), input_data.business_type)

    print(f"--- [API] /analyze/quick 요청: {input_data.target_district} / {normalized_biz} ---")

    minimal_state = {
        "business_type": normalized_biz,
        "target_district": getattr(input_data, "target_district", "서교동"),
        "monthly_rent_budget": getattr(input_data, "monthly_rent", 0),
        "store_area": getattr(input_data, "store_area", 15.0),
        "population_weight": getattr(input_data, "population_weight", True),
    }

    try:
        if db_client.engine is None:
            await db_client.connect()

        ranking_result = await district_ranking_node(minimal_state)

        return {
            "status": "success",
            "data": {
                "winner_district": ranking_result["winner_district"],
                "top_3_candidates": ranking_result["top_3_candidates"],
                "district_rankings": ranking_result["scouting_results"],
            },
        }
    except Exception as e:
        print(f"!!! [QUICK API ERROR] !!! {str(e)}")
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
# 유동인구 실시간 API
# ---------------------------------------------------------------------------


@app.get("/population/live")
async def get_live_population(dongs: str | None = None):
    """
    마포구 동별 유동인구 실시간 조회 (서울 열린데이터 API).

    - dongs 미지정: 마포구 16개 동 전체
    - dongs=서교동,합정동,연남동: 특정 동만 조회

    응답:
    - daily_average: 요청한 동들의 일평균 유동인구
    - dong_details: 동별 일합계, 피크시간대, 2039 남녀 비율
    - hourly_total: 시간대별 합계 (차트용)
    """
    from src.services.population_api import get_population_by_dongs

    dong_list = [d.strip() for d in dongs.split(",")] if dongs else None
    return await get_population_by_dongs(dong_list)


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
        import traceback

        print(f"!!! [SIMULATE ERROR] !!! {type(e).__name__}: {e}")
        traceback.print_exc()
        return {
            "request_id": request_id,
            "target_district": input_data.target_district,
            "ai_recommendation": "",
            "market_report": None,
            "comparison": [],
            "legal_risks": [],
            "overall_legal_risk": "safe",
            "simulation_months": 12,
            "quarterly_projection": [],
            "analysis_report": f"분석 중 오류가 발생했습니다: {str(e)}",
            "analysis_metrics": {},
            "demographic_report": None,
            "trend_forecast": None,
            "map_data": None,
            "financial_report": {},
        }


# ---------------------------------------------------------------------------
# ABM 시뮬레이션 엔드포인트 — 기존 5 에이전트와 완전 독립
# /simulate 결과를 입력받아 행동 시뮬만 실행, 분석 결과에 영향 없음
# A1 인터페이스 계약 (policy-generator-design.md) 준수
# ---------------------------------------------------------------------------
class AbmScenarioParams(BaseModel):
    """GameMaster에 전달되는 시나리오 파라미터 (A1 Scenario dataclass와 1:1 대응)"""
    weather_override: str | None = None   # "맑음"|"비"|"눈"|None(RDS 최신 날씨)
    date_override: str | None = None      # "2026-04-25" ISO 날짜, None=오늘
    weekend_force: bool = False           # True=주말 강제, date_override 무시
    rent_shock_pct: float = 0.0           # 0.0~0.5 (0.3 = +30%)


class AbmSimulationRequest(BaseModel):
    # LangGraph 분석 컨텍스트
    target_district: str
    business_type: str
    brand_name: str
    langgraph_result: Dict[str, Any]
    # 시뮬 규모
    n_agents: int = 100                   # 100 | 1000
    days: int = 1
    # GameMaster 시나리오
    scenario: AbmScenarioParams = AbmScenarioParams()


@app.post("/api/simulate-abm")
async def run_abm_simulation(req: AbmSimulationRequest):
    """
    ABM 행동 시뮬레이션 — 의사결정 에이전트와 완전 분리된 독립 기능.
    LangGraph 5 에이전트 분석 결과를 시나리오로 주입해 소비자 행동을 시뮬한다.
    기존 분석 결과(analysis_report, analysis_metrics 등)는 절대 수정하지 않는다.
    """
    try:
        from src.simulation.runner import run_simulation as abm_run
        from src.simulation.config import (
            Scenario,
            ModelConfig,
            PopulationMix,
            TierDistribution,
        )
    except ImportError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "message": "ABM 시뮬레이션 모듈이 아직 배포되지 않았습니다. (simulation/ 브랜치 머지 대기)",
            },
        )

    # LangGraph 결과에서 new_store 스펙 구성
    lr = req.langgraph_result
    analysis_metrics = lr.get("analysis_metrics", {})
    market_report = lr.get("market_report") or {}

    new_store_spec = {
        "district": req.target_district,
        "brand": req.brand_name,
        "category": req.business_type,
        "score": lr.get("score"),
        "estimated_revenue": market_report.get("estimated_revenue"),
        "competition_intensity": market_report.get("competition_intensity"),
        "main_target_age": analysis_metrics.get("main_target_age"),
        "peak_time": analysis_metrics.get("peak_time"),
    }

    pop = PopulationMix(residents=60, commuters=25, visitors=10, owners=5)
    tier = TierDistribution(tier_s=5, tier_a=20, tier_b=75)
    cfg = ModelConfig(
        tier_s_provider="ollama",
        tier_s_model="qwen2.5:3b",
        n_personas=req.n_agents,
    )
    # A1 Scenario dataclass — weather_override / date_override / weekend_force / rent_shock_pct
    scenario = Scenario(
        new_store=new_store_spec,
        cannibalize_radius_m=500,
        weather_override=req.scenario.weather_override,
        date_override=req.scenario.date_override,
        weekend_force=req.scenario.weekend_force,
        rent_shock_pct=req.scenario.rent_shock_pct,
    )

    try:
        result = await run_in_threadpool(
            abm_run,
            pop=pop,
            tier=tier,
            cfg=cfg,
            use_rds=True,
            use_profiles=True,
            scenario=scenario,
            days=req.days,
        )
    except Exception as e:
        logger.error(f"[ABM] 시뮬레이션 실패: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"ABM 시뮬레이션 실패: {e}"},
        )

    return {
        "status": "ok",
        "target_district": req.target_district,
        "n_personas": req.n_agents,
        "scenario_applied": {
            "weather": req.scenario.weather_override or "현재날씨",
            "weekend": req.scenario.weekend_force,
            "rent_shock_pct": req.scenario.rent_shock_pct,
            "date": req.scenario.date_override or "오늘",
        },
        "daily_visits_mean": result.get("daily_visits", 0),
        "daily_visits_std": result.get("daily_visits_std", 0),
        "daily_revenue_mean": result.get("daily_revenue", 0),
        "daily_revenue_std": result.get("daily_revenue_std", 0),
        "monthly_revenue_estimate": round(result.get("daily_revenue", 0) * 25),
        "peak_hours": result.get("peak_hours", []),
        "customer_profile_dist": result.get("customer_profile_dist", {}),
        "cannibalization": result.get("cannibalization", {}),
        "narrator_summary": result.get("narrator_summary", ""),
        "trajectory": result.get("trajectory"),  # 미로피쉬 재생용
        # 원본 LangGraph 분석 결과 — 수정 없음
        "langgraph_result": lr,
    }
