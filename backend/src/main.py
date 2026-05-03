import asyncio
import logging
import math
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

# Windows cp949 콘솔 인코딩 이슈 방지 — ABM simulation 이모지/em-dash 출력 crash 회피
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except AttributeError:
        pass

# Python root logger 구성 — backend 코드의 logger.info() / logger.warning() 화면 출력 활성화.
# LOG_LEVEL env (DEBUG/INFO/WARNING/ERROR) 로 조정. 미설정 시 INFO.
# force=True: uvicorn이 먼저 root logger에 핸들러 등록한 경우 덮어씀.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)
# 외부 라이브러리 noise 줄임
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("watchfiles").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# [ModuleNotFoundError 해결] src 디렉토리를 path에 추가하여 'import schemas' 등이 가능하게 함
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

# models/ 패키지 임포트를 위해 프로젝트 루트(Final_Project/)를 path에 추가
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import redis.asyncio as aioredis

# LangSmith 트레이싱: langchain import 전에 os.environ 주입 필수
# (langchain SDK는 import 시점에 LANGCHAIN_TRACING_V2를 읽으므로 순서가 중요)
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# cwd가 backend/든 repo root든 repo root의 .env를 찾도록 명시.
# biz_mapper.DB_URL 등은 import 시점에 os.environ을 읽어 localhost fallback을 확정하므로
# load_dotenv를 setting 모듈 import 전에 선행 실행해야 한다.
_REPO_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
if _REPO_ROOT_ENV.exists():
    load_dotenv(_REPO_ROOT_ENV)
else:
    load_dotenv()
_lc_api_key = os.environ.get("LANGCHAIN_API_KEY", "")
if _lc_api_key:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", os.environ.get("LANGCHAIN_TRACING_V2", "true"))
    os.environ.setdefault(
        "LANGCHAIN_ENDPOINT", os.environ.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com/")
    )
    os.environ.setdefault("LANGCHAIN_PROJECT", os.environ.get("LANGCHAIN_PROJECT", "mapo-franchise-simulator"))

from langchain_core.messages import HumanMessage
from src.agents.graph import compile_slow_graph, compile_workflow

# 절대 경로 임포트로 통일 (uvicorn src.main:app 실행 대응)
from src.config.settings import settings
from src.schemas.simulation_input import SimulationInput
from src.services.auth import AuthService
from src.services.biz_mapper import BizMapper

from models.explainability.shap_analysis import explain_tcn_prediction
from models.explainability.simulation import (
    build_quarterly_projection,
    build_scenarios,
)
from models.lstm_forecast.data_prep import ExcludedComboError
from models.revenue_predictor.bep import BEPCalculator
from src.schemas.simulation_output import DistrictPredictionResult

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

# IM3-259 — AI 분석 전용 slow_graph (inflow + ranking + LLM + synthesis)
# /analyze/llm endpoint에서 사용. ml_prediction은 포함하지 않음 (그건 /predict 측 책임).
slow_graph = compile_slow_graph()

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

# --- simulation_history REST (JWT Bearer 요구) ---
from src.api.simulation_history import router as _sim_history_router  # noqa: E402

app.include_router(_sim_history_router)

# --- vacancy_evaluation REST (ABM PSE 평가, 무인증) ---
from src.api.vacancy_evaluation import router as _vacancy_eval_router  # noqa: E402

app.include_router(_vacancy_eval_router)

# --- customer_segment REST (MLP 단발 호출, frontend 실시간 미리보기용) ---
from src.api.customer_segment import router as _customer_segment_router  # noqa: E402

app.include_router(_customer_segment_router)

# --- simulation_foresee REST (예측 결과 저장, JWT Bearer 요구) ---
from src.api.simulation_foresee import router as _sim_foresee_router  # noqa: E402

app.include_router(_sim_foresee_router)

# --- simulation_ai REST (AI 분석 저장, JWT Bearer 요구) ---
from src.api.simulation_ai import router as _sim_ai_router  # noqa: E402

app.include_router(_sim_ai_router)

# --- sensitivity REST (TCN 시나리오 시뮬레이터 탄성치 캐시 서빙) ---
from src.api.sensitivity import router as _sensitivity_router  # noqa: E402

app.include_router(_sensitivity_router)


# customer_revenue MLP 모델 startup 시 워밍업 — 첫 미리보기 호출 latency 0.5~1초 → ~100ms.
# 가중치 부재 환경에선 silent skip (배포 서버 분리 케이스 보호).
@app.on_event("startup")
def _warmup_customer_revenue() -> None:
    try:
        from models.interface import _run_customer_revenue

        _run_customer_revenue("11440680", "CS100010", profile_dict=None)
        print("[STARTUP] customer_revenue MLP 워밍업 완료")
    except Exception as exc:  # noqa: BLE001
        print(f"[STARTUP] customer_revenue 워밍업 skip: {exc}")


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
_pending_pipelines: dict[str, "asyncio.Task[Any]"] = {}

# /predict/async + /analyze/llm/async 의 background task strong ref.
# asyncio.create_task() 결과를 어디에도 보관 안 하면 event loop 가 weak ref 만 유지 →
# GC 가 task 를 도중에 수거할 수 있음 (Python docs 공식 함정). progress=0 무한 멈춤 회귀.
# 완료 시 done_callback 으로 자동 discard.
_async_job_tasks: set["asyncio.Task[Any]"] = set()


def _pipeline_key(input_data: Any) -> str:
    radius = getattr(input_data, "commercial_radius", 500)
    pop_w = getattr(input_data, "population_weight", True)
    rent = getattr(input_data, "monthly_rent", 0)
    area = getattr(input_data, "store_area", 15.0)
    return f"{input_data.target_district}:{input_data.business_type}:{input_data.brand_name}:{rent}:{area}:{radius}:{pop_w}"


_BIZ_TYPE_NORMALIZE: dict[str, str] = {
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
# 업종명(한국어) → 골목상권 업종코드: tools.py MarketDataTool._SALES_CODE_MAP 재사용
from src.agents.tools import MarketDataTool as _MarketDataTool
from src.services.commercial_intelligence import analyze_competition as _analyze_competition
from src.services.dong_resolver import resolve_dong_code as _resolve_dong_code

_BIZ_TO_INDUSTRY_CODE: dict[str, str] = _MarketDataTool._SALES_CODE_MAP

# 업종 → kakao 검색 키워드 매핑
_BIZ_TO_KAKAO_KW: dict[str, str] = {
    "치킨전문점": "치킨",
    "커피-음료": "커피",
    "한식음식점": "한식",
    "중식음식점": "중식",
    "일식음식점": "일식",
    "양식음식점": "양식",
    "제과점": "베이커리",
    "패스트푸드점": "버거",
    "분식전문점": "분식",
    "호프-간이주점": "주점",
    "치킨": "치킨",
    "커피": "커피",
    "카페": "커피",
    "한식": "한식",
    "중식": "중식",
    "일식": "일식",
    "양식": "양식",
    "베이커리": "베이커리",
    "버거": "버거",
    "분식": "분식",
    "주점": "주점",
    "chicken": "치킨",
    "cafe": "커피",
    "coffee": "커피",
    "burger": "버거",
    "bakery": "베이커리",
    "korean": "한식",
}


async def _collect_all_competitor_locations(
    winner: str,
    top3: list,
    business_type: str,
) -> list[dict]:
    """winner + top3 추천 동 각각의 500m 반경 경쟁업체 좌표를 수집해 통합 반환."""
    keyword = _BIZ_TO_KAKAO_KW.get(business_type, business_type)
    districts = list({winner} | set(top3 or []))
    print(f"[all_competitors] 수집 시작 — business_type={business_type} keyword={keyword} districts={districts}")
    results: list[dict] = []
    seen_ids: set = set()

    async def _fetch_one(dong_name: str):
        try:
            dong_code = _resolve_dong_code(dong_name)
            if not dong_code:
                print(f"[all_competitors] dong_code 없음: {dong_name}")
                return
            data = await asyncio.to_thread(_analyze_competition, dong_code, keyword, 500)
            samples = data.get("samples") or []
            print(f"[all_competitors] {dong_name}({dong_code}) → {len(samples)}개 샘플")
            for s in samples:
                cid = s.get("kakao_id") or f"{s.get('place_name')}_{s.get('lat')}_{s.get('lon')}"
                if cid in seen_ids:
                    continue
                seen_ids.add(cid)
                if s.get("lat") and s.get("lon"):
                    results.append(
                        {
                            "id": cid,
                            "place_name": s.get("place_name", ""),
                            "brand_name": s.get("brand_name", ""),
                            "lat": s["lat"],
                            "lng": s["lon"],
                            "distance_m": s.get("distance_m"),
                            "is_franchise": s.get("is_franchise", False),
                            "category": s.get("category", ""),
                            "source_dong": dong_name,
                        }
                    )
        except Exception as e:
            import traceback

            print(f"[all_competitors] {dong_name} 수집 실패: {e}\n{traceback.format_exc()}")

    await asyncio.gather(*[_fetch_one(d) for d in districts])
    print(f"[all_competitors] 최종 결과: {len(results)}개")
    return results


def _build_initial_state(input_data: Any) -> dict[str, Any]:
    """SimulationInput에서 LangGraph initial state dict 생성.

    /simulate, /analyze, /analyze/llm 등 모든 그래프 진입점이 공유한다.
    """
    normalized_biz = _BIZ_TYPE_NORMALIZE.get(input_data.business_type.lower(), input_data.business_type)
    normalized_brand = input_data.brand_name or "미지정 브랜드"

    return {
        "messages": [HumanMessage(content=f"{input_data.target_district} {normalized_brand} 분석 시작")],
        "business_type": normalized_biz,
        "brand_name": normalized_brand,
        "target_district": input_data.target_district,
        "target_districts": getattr(input_data, "target_districts", None) or [input_data.target_district],
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
        "overall_legal_risk": None,
        "current_agent": "start",
        "next_step": "",
        "errors": [],
        "competitor_intel_result": {},
        # [customer_revenue P1-C] 사용자 타겟 입력 → state 주입
        "target_age_groups": getattr(input_data, "target_age_groups", None) or [],
        "target_gender": getattr(input_data, "target_gender", None),
        "target_time_slots": getattr(input_data, "target_time_slots", None) or [],
        "target_day_type": getattr(input_data, "target_day_type", None),
        "target_monthly_sales": getattr(input_data, "target_monthly_sales", None),
    }


async def _run_pipeline(input_data: Any) -> dict[str, Any]:
    """파이프라인 실행. 동일 키로 이미 실행 중인 Task가 있으면 공유하여 대기."""
    key = _pipeline_key(input_data)

    if key in _pending_pipelines and not _pending_pipelines[key].done():
        print(f"[DEDUP] 동일 요청 대기 중 - 기존 파이프라인 공유: {key}")
        return await _pending_pipelines[key]

    initial_state = _build_initial_state(input_data)

    task: asyncio.Task[Any] = asyncio.create_task(asyncio.wait_for(app_graph.ainvoke(initial_state), timeout=600.0))
    _pending_pipelines[key] = task
    try:
        return await task
    finally:
        _pending_pipelines.pop(key, None)


def _safe_json(obj: Any) -> Any:
    """numpy 타입 / NaN / Inf → JSON-safe Python 기본 타입으로 재귀 변환.

    FastAPI ASGI 직렬화 단계에서 numpy.float64, numpy.int64, float('nan') 등이
    포함된 dict를 JSONResponse로 반환할 때 발생하는 직렬화 오류를 방지한다.
    """
    try:
        import numpy as np  # numpy가 없는 환경 방어

        _has_numpy = True
    except ImportError:
        _has_numpy = False

    if isinstance(obj, dict):
        return {k: _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_json(v) for v in obj]
    if _has_numpy:
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            v = float(obj)
            return None if (math.isnan(v) or math.isinf(v)) else v
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return [_safe_json(x) for x in obj.tolist()]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def _build_segment_profile(input_data: SimulationInput) -> dict[str, Any] | None:
    """Build optional target customer profile for ModelOutput.generate()."""
    profile = {
        "age_groups": getattr(input_data, "target_age_groups", None) or [],
        "gender": getattr(input_data, "target_gender", None),
        "time_slots": getattr(input_data, "target_time_slots", None) or [],
        "day_type": getattr(input_data, "target_day_type", None),
    }
    cleaned = {key: value for key, value in profile.items() if value not in (None, "", [])}
    return cleaned or None


async def _predict_single_district(
    dong_name: str,
    industry_code: str,
    industry_name: str,
    cost_config: dict,
    segment_profile: dict | None = None,
    progress_cb: "Callable[[str], None] | None" = None,
) -> DistrictPredictionResult:
    """단일 동 ML 예측 실행 (/predict 병렬 호출용).

    progress_cb 가 주어지면 4 sub-stage 끝마다 호출됨 (ModelOutput/projection/SHAP/조립).
    /predict/async 의 real-time progress 와이어링용 — 동 단위 보다 세분화된 % 표시.
    """
    from models.interface import ModelOutput

    dong_code = _resolve_dong_code(dong_name)
    if not dong_code:
        if progress_cb:
            progress_cb("dong_code_missing")
        return DistrictPredictionResult(district=dong_name)

    try:
        sim_result = await run_in_threadpool(
            ModelOutput.generate,
            dong_code,
            industry_code,
            industry_name,
            cost_config,
            "tcn",
            segment_profile,
        )
    except ExcludedComboError:
        if progress_cb:
            progress_cb("excluded_combo")
        return DistrictPredictionResult(district=dong_name, dong_code=dong_code, is_excluded_combo=True)
    except Exception as e:
        print(f"[PREDICT] {dong_name} ML 실패: {e}")
        if progress_cb:
            progress_cb("ml_failed")
        return DistrictPredictionResult(district=dong_name, dong_code=dong_code)
    if progress_cb:
        progress_cb("ml_done")

    # quarterly_projection + 시나리오 빌드
    quarterly: list = []
    scenarios_result = None
    try:
        store_count = sim_result["revenue_forecast"].get("store_count", 1)
        quarterly = build_quarterly_projection(
            bep_quarterly_simulation=sim_result["bep"]["quarterly_simulation"],
            quarterly_predictions=sim_result["revenue_forecast"]["quarterly_predictions"],
            confidence="base",
            is_mock=sim_result["revenue_forecast"].get("is_mock", False),
            store_count=store_count,
        )
        scenarios_result = build_scenarios(
            quarterly_predictions=sim_result["revenue_forecast"]["quarterly_predictions"],
            store_count=store_count,
        )
    except Exception as e:
        print(f"[PREDICT] {dong_name} projection 빌드 실패: {e}")
    if progress_cb:
        progress_cb("projection_done")

    # SHAP 빌드
    shap_result = None
    try:
        shap_raw = await run_in_threadpool(explain_tcn_prediction, dong_code, industry_code)
        shap_result = shap_raw if shap_raw else None
    except Exception as e:
        print(f"[PREDICT] {dong_name} SHAP 실패 (무시): {e}")
    if progress_cb:
        progress_cb("shap_done")

    is_mock = sim_result["revenue_forecast"].get("is_mock", False)

    result = DistrictPredictionResult(
        district=dong_name,
        dong_code=dong_code,
        is_excluded_combo=False,
        is_mock=is_mock,
        quarterly_projection=quarterly,
        scenarios=scenarios_result,
        bep=sim_result.get("bep"),
        closure_rate=sim_result.get("closure_rate"),
        closure_risk=sim_result.get("closure_risk"),
        shap_result=shap_result,
        customer_segment=sim_result.get("customer_segment"),
        living_pop_forecast=sim_result.get("living_pop_forecast"),
        emerging_signal=sim_result.get("emerging_signal"),
    )
    if progress_cb:
        progress_cb("assembled")
    return result


def map_state_to_simulation_output(state: dict[str, Any], request_id: str) -> dict[str, Any]:
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
    # winner_district 우선 사용 — Phase1에서 선택 동 중 1위로 확정된 동
    target_dist = state.get("winner_district") or state.get("target_district", "마포구")

    # [좌표 기본값 처리]
    lat = md.get("lat") if md.get("lat") else DEFAULT_LAT
    lng = md.get("lng") if md.get("lng") else DEFAULT_LNG

    # 법률 리스크 리스트 변환 (articles 포함 — 프론트 근거 조항 drawer용)
    legal_risks_raw = analysis.get("legal_risks") or []

    # 벌칙 조문 자동 매핑 — 캐시/비캐시 모두 대응 (legal_node 내부 캐시 경유 시에도 적용)
    from src.agents.legal.categories import get_legal_group
    from src.agents.nodes.legal import _enrich_penalty_info

    _enrich_penalty_info(legal_risks_raw)

    legal_risks = [
        {
            "type": r.get("type", "General"),
            "risk_level": {"safe": "LOW", "caution": "MEDIUM", "danger": "HIGH"}.get(
                r.get("level", "safe").lower(), "LOW"
            ),
            # 입지(location) vs 운영(operation) 그룹 — frontend 분리 UI 에서 사용
            "group": get_legal_group(r.get("type", "")),
            "detail": r.get("summary", ""),
            "recommendation": r.get("recommendation", ""),
            "articles": [{"article_ref": a, "content": ""} if isinstance(a, str) else a for a in r.get("articles", [])],
            "checklist": r.get("checklist", []),
            "is_fallback": r.get("is_fallback", False),
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

    # 랭킹 데이터 — analysis_results 누락 시 state top-level (ranking_phase) 폴백.
    # synthesis 캐시 히트 등으로 analysis_results 에 ranking 결과가 안 실리는 케이스 방어.
    district_rankings = _sanitize(analysis.get("district_rankings") or state.get("scouting_results") or [])
    winner_district = _sanitize(analysis.get("winner_district") or state.get("winner_district") or target_dist)
    top_3_candidates = _sanitize(analysis.get("top_3_candidates") or state.get("top_3_candidates") or [])
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
        # 2026-04-27: scouting_results 부재 시 LLM 등급 매핑(SAFE→80, EXCELLENT→90 등)으로
        # 7지표를 채워 보내던 fallback 제거. 임의값이 UI에서 실데이터처럼 보여
        # 거짓 양성 판정을 만들었음 (api-contract-frontend-input.md §3.7 위반).
        # → None으로 흘려보내 프론트가 '—' 또는 차트 비활성으로 정직하게 처리.
        _rent_index_r = None
        _estimated_rev_r = None
        _floating_pop_r = None
        _competition_r = None
        _survival_r = None
        _growth_r = None

    competition_intensity = _competition_r
    # district_score도 동일 정신 — _target_row 없으면 None.
    # comparison[].score를 받는 프론트 DistrictComparison.score는 nullable로 동기화 완료.
    district_score = float(_target_row.get("score") or 0) if _target_row else None

    accessibility_raw = metrics.get("inflow_score")
    if accessibility_raw is None:
        accessibility_raw = metrics.get("accessibility_score")

    market_report = {
        "floating_population": _floating_pop_r,
        "rent_index": _rent_index_r,
        "competition_intensity": competition_intensity,
        "estimated_revenue": _estimated_rev_r,
        "survival_rate": _survival_r,
        "growth_potential": _growth_r,
        # inflow_score (Hansen 1959 + E2SFCA 2009) 우선, 구형 accessibility_score 폴백.
        # 값이 없으면 임의 기본값(예: 75)을 만들지 않고 None으로 내려보낸다.
        "accessibility": (min(int(float(accessibility_raw)), 100) if accessibility_raw is not None else None),
    }

    # [Phase 2.5] graph.py ml_prediction_phase_node에서 실행된 TCN 결과를 state에서 읽음
    # (중복 실행 제거 — 이전에는 여기서 ModelOutput.generate를 별도 호출했음)
    _dong_code = _resolve_dong_code(target_dist)
    if _dong_code is None:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 행정동입니다: '{target_dist}'. 마포구 16개 동만 지원됩니다.",
        )
    _industry_code = _BIZ_TO_INDUSTRY_CODE.get(state.get("business_type", "카페"), "CS100010")
    sim_result = state.get("tcn_sim_result") or {}

    scenarios = None
    try:
        _store_count = sim_result.get("revenue_forecast", {}).get("store_count", 1)
        quarterly = build_quarterly_projection(
            bep_quarterly_simulation=sim_result["bep"]["quarterly_simulation"],
            quarterly_predictions=sim_result["revenue_forecast"]["quarterly_predictions"],
            confidence="base",
            store_count=_store_count,
        )
        scenarios = build_scenarios(
            quarterly_predictions=sim_result["revenue_forecast"]["quarterly_predictions"],
            store_count=_store_count,
        )
    except Exception as _sim_err:
        print(f"[SIM] quarterly 빌드 실패 (empty 사용): {_sim_err}")
        quarterly = []

    # SHAP 분석 — Phase 2.5에서 이미 계산된 값을 state에서 읽음 (중복 실행 방지)
    shap_result = state.get("shap_result") or None
    if not shap_result:
        try:
            shap_result = explain_tcn_prediction(
                dong_code=_dong_code,
                industry_code=_industry_code,
            )
        except Exception as e:
            logger.warning("SHAP 분석 실패: %s", e)
            shap_result = None

    _sim_closure_rate = (sim_result.get("closure_rate") or {}).get("closure_rate")
    _sim_bep_quarters = (sim_result.get("bep") or {}).get("bep_quarters")

    # market_report에 모델 기반 폐업률 추가 (0~1 소수)
    market_report["closure_rate"] = _sim_closure_rate

    # 타겟 동의 bep_quarters, closure_rate를 district_rankings에 주입
    district_rankings = [
        {
            **r,
            **(
                {"bep_quarters": _sim_bep_quarters, "closure_rate": _sim_closure_rate}
                if r.get("district") == target_dist
                else {}
            ),
        }
        for r in district_rankings
    ]

    # 사용자 선택 동이 상단에 오도록 정렬: winner → 나머지 선택 동 → 미선택 동
    _selected = set(state.get("target_districts") or [target_dist])
    district_rankings = sorted(
        district_rankings,
        key=lambda r: 0 if r.get("district") == winner_district else 1 if r.get("district") in _selected else 2,
    )

    # [B1 고도화] 응답 구조 재설계
    _avg_revenue = md.get("avg_revenue")
    comparison = []
    if any(
        v is not None
        for v in (
            district_score,
            _avg_revenue,
            _sim_bep_quarters,
            market_report.get("survival_rate"),
            metrics.get("cannibalization_impact"),
        )
    ):
        comparison.append(
            {
                "district": target_dist,
                "score": district_score,
                # avg_revenue는 원(₩) 단위 — 프론트가 ×10000 표시하므로 만원으로 환산.
                # 값이 없으면 None으로 내려보낸다.
                "revenue": (_avg_revenue // 10000) if _avg_revenue is not None else None,
                "bep": (
                    metrics.get("bep_quarters")
                    or (final_report.get("profit_simulation") or {}).get("bep_quarters")
                    or _sim_bep_quarters
                    or None
                ),
                "survival": (
                    float(market_report["survival_rate"]) if market_report.get("survival_rate") is not None else None
                ),
                "cannibalization": (
                    float(metrics["cannibalization_impact"])
                    if metrics.get("cannibalization_impact") is not None
                    else None
                ),
            }
        )

    competitor_intel = state.get("competitor_intel_result")

    response_data = {
        "request_id": request_id,
        "target_district": target_dist,
        "target_districts": state.get("target_districts") or [target_dist],
        "winner_district": winner_district,
        "top_3_candidates": top_3_candidates,
        "district_rankings": district_rankings,
        "vacancy_applied": state.get("vacancy_applied", False),  # 공실 DB 반영 여부 (프론트 배지용)
        "ai_recommendation": ai_recommendation,
        "final_report": final_report,
        "market_report": market_report,
        "analysis_report": analysis.get("market_summary", ""),
        "analysis_metrics": metrics,
        "simulation_quarters": (sim_result.get("bep") or {}).get("simulation_quarters"),
        "quarterly_projection": quarterly,
        "scenarios": scenarios,
        "comparison": comparison,
        "overall_legal_risk": analysis.get("overall_legal_risk"),
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
        # 과거 12개월 폐업률 추이 — 실측 누적 (예측 아님)
        "closure_rate": sim_result.get("closure_rate") if "sim_result" in locals() else None,
        # 폐업위험도 (LightGBM + TCN 앙상블) — 모델 호출 실패 시 None
        "closure_risk": sim_result.get("closure_risk") if "sim_result" in locals() else None,
        # [C] 타겟 고객 매출 분석 (customer_revenue MLP) — 모델 호출 실패 시 None
        # (c822f98에서 매핑 누락된 회귀 — D/E 활성화와 함께 수정)
        "customer_segment": sim_result.get("customer_segment") if "sim_result" in locals() else None,
        # [D] 유동인구 피크 시간 예측 (TCN) — 모델 호출 실패 시 None
        "living_pop_forecast": sim_result.get("living_pop_forecast") if "sim_result" in locals() else None,
        # [E] 신흥 상권 조기 감지 (LSTM Autoencoder) — 모델 호출 실패 시 None
        "emerging_signal": sim_result.get("emerging_signal") if "sim_result" in locals() else None,
        # competitor_intel 하이브리드 에이전트 결과 (경쟁 지형·카니발·차별화)
        "competitor_intel": _sanitize(competitor_intel) if competitor_intel else None,
        # 8 에이전트 판단 근거 (AgentAttribution)
        "agent_attributions": _sanitize(analysis.get("agent_attributions") or state.get("agent_attributions") or []),
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
async def analyze_location(input_data: SimulationInput, response: Response):
    """[DEPRECATED] 풀파이프 상권 분석 — 전환 기간 동안만 유지.

    IM3-259로 endpoint를 분리(/predict + /analyze/llm)했으므로 신규 호출은
    그쪽으로 옮길 것. 이 endpoint는 기존 프론트/테스트 호환을 위해 유지하다가
    충분히 검증되면 제거 예정.
    """
    from src.config.constants import MAPO_DISTRICTS

    # IM3-259: deprecation 헤더 — 클라이언트가 /predict + /analyze/llm 으로 옮길 것을 알림
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</predict>; rel="successor-version", </analyze/llm>; rel="successor-version"'

    if input_data.target_district not in MAPO_DISTRICTS:
        return {
            "status": "error",
            "message": f"지원하지 않는 행정동입니다: {input_data.target_district}. 마포구 16개 동만 지원합니다.",
        }

    request_id = str(uuid.uuid4())
    print(f"--- [API] /analyze 요청 수신 [DEPRECATED]: {input_data.target_district} ({input_data.business_type}) ---")

    # 테스트 모드 — LLM 5 에이전트 분석 건너뛰기 (토큰 절약)
    if os.getenv("LLM_AGENTS_DISABLED", "").strip() == "1":
        print(f"[ANALYZE] LLM_AGENTS_DISABLED=1 — mock 반환 (target={input_data.target_district})")
        return {
            "status": "success",
            "data": _mock_simulation_response(input_data.target_district, request_id),
        }

    try:
        final_state = await _run_pipeline(input_data)
        result = map_state_to_simulation_output(final_state, request_id)
        # 추천 동 전체(winner + top3)의 경쟁업체 좌표 수집 — 지도 멀티핀용
        winner = result.get("winner_district") or input_data.target_district
        top3 = result.get("top_3_candidates") or []
        print(f"[all_competitors] winner={winner}, top3={top3}")
        result["all_competitor_locations"] = await _collect_all_competitor_locations(
            winner, top3, input_data.business_type
        )
        return {"status": "success", "data": result}
    except Exception as e:
        print(f"!!! [API ERROR] !!! {str(e)}")
        return {"status": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# IM3-259 — /analyze/llm: AI 분석 전용 endpoint (TCN/ML 분리, LLM only)
# ---------------------------------------------------------------------------
# /predict (B2 단발 ML)와 독립 병렬 호출. inflow + ranking + LLM 6 +
# synthesis 단계만 실행하며, ml_prediction은 포함하지 않는다 (그건 /predict 측).
# 응답: AnalysisOutput
# ---------------------------------------------------------------------------


@app.post("/analyze/llm")
async def analyze_llm(input_data: SimulationInput):
    """AI 분석 전용 endpoint — slow_graph 실행 (~80-140초).

    /predict와 독립 병렬 호출 가능. winner는 ranking 단계에서 자체 결정.
    """
    from src.config.constants import MAPO_DISTRICTS
    from src.schemas.simulation_output import AnalysisOutput

    if input_data.target_district not in MAPO_DISTRICTS:
        return {
            "status": "error",
            "message": f"지원하지 않는 행정동입니다: {input_data.target_district}. 마포구 16개 동만 지원합니다.",
        }

    request_id = str(uuid.uuid4())
    print(
        f"--- [API] /analyze/llm 요청 수신: {input_data.target_district} "
        f"({input_data.business_type}) | id={request_id} ---"
    )

    if os.getenv("LLM_AGENTS_DISABLED", "").strip() == "1":
        print(f"[ANALYZE/LLM] LLM_AGENTS_DISABLED=1 — mock 반환 (target={input_data.target_district})")
        return {"status": "success", "data": _mock_simulation_response(input_data.target_district, request_id)}

    initial_state = _build_initial_state(input_data)
    try:
        final_state = await asyncio.wait_for(slow_graph.ainvoke(initial_state), timeout=600.0)
    except Exception as e:
        import traceback

        print(f"!!! [ANALYZE/LLM ERROR] !!! {type(e).__name__}: {e}")
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

    # 풀파이프와 동일한 매퍼 재사용 — AnalysisOutput에 해당하는 필드만 자동 추출됨.
    full = map_state_to_simulation_output(final_state, request_id)

    # 경쟁업체 좌표 수집 (지도 멀티핀용) — winner 기준
    winner = full.get("winner_district") or input_data.target_district
    top3 = full.get("top_3_candidates") or []
    try:
        full["all_competitor_locations"] = await _collect_all_competitor_locations(
            winner, top3, input_data.business_type
        )
    except Exception as e:
        print(f"[ANALYZE/LLM] all_competitor_locations 수집 실패 (무시): {e}")
        full["all_competitor_locations"] = []

    # AnalysisOutput에 정의된 필드만 추출하여 응답 (PR 후 추가/제거 시 schema가 source of truth)
    analysis_keys = set(AnalysisOutput.model_fields.keys())
    payload = {k: v for k, v in full.items() if k in analysis_keys}
    payload["request_id"] = request_id
    payload["target_district"] = full.get("target_district") or input_data.target_district

    return {"status": "success", "data": payload}


# ---------------------------------------------------------------------------
# Real-time progress 지원 — /analyze/llm/async + /analyze/llm/{job_id}/status.
# slow_graph.astream(stream_mode="updates") 로 노드 완료 이벤트 hook.
# 4 노드 (inflow → ranking_phase → llm_analysis_phase → synthesis) 기준 25%/50%/75%/100%.
# stream_mode="values" 와 동시 수신해 final_state 도 같은 루프에서 캡처.
# ---------------------------------------------------------------------------
_SLOW_GRAPH_NODE_TOTAL = 4


@app.post("/analyze/llm/async")
async def analyze_llm_async(input_data: SimulationInput) -> dict[str, Any]:
    """AI 분석 비동기 시작 — 즉시 job_id 반환. LangGraph 노드별 진행률 추적."""
    from src.config.constants import MAPO_DISTRICTS
    from src.schemas.simulation_output import AnalysisOutput
    from src.services.job_progress_store import (
        create_job,
        set_done,
        set_error,
        set_progress,
    )

    if input_data.target_district not in MAPO_DISTRICTS:
        return {
            "status": "error",
            "message": f"지원하지 않는 행정동입니다: {input_data.target_district}.",
        }

    job_id = create_job("analyze_llm")
    request_id = str(uuid.uuid4())
    logger.info(
        f"[/analyze/llm/async] 시작 job={job_id[:8]} target={input_data.target_district} biz={input_data.business_type}"
    )

    async def _run() -> None:
        logger.info(f"[/analyze/llm/async] _run 진입 job={job_id[:8]}")
        try:
            if os.getenv("LLM_AGENTS_DISABLED", "").strip() == "1":
                # mock 경로도 진행률 시뮬 (인스턴트 done)
                payload = _mock_simulation_response(input_data.target_district, request_id)
                set_done(job_id, payload)
                return

            initial_state = _build_initial_state(input_data)
            done_count = 0
            final_state: dict[str, Any] | None = None

            # multi-mode stream — "updates" 로 노드 완료 이벤트, "values" 로 누적 state.
            async for mode, chunk in slow_graph.astream(initial_state, stream_mode=["updates", "values"]):
                if mode == "updates":
                    # chunk = {"node_name": state_diff_dict}
                    for node_name in chunk.keys():
                        if node_name.startswith("__"):  # langgraph internal
                            continue
                        done_count += 1
                        set_progress(
                            job_id,
                            min(1.0, done_count / _SLOW_GRAPH_NODE_TOTAL),
                            stage=node_name,
                        )
                elif mode == "values":
                    # 매 yield 가 누적 state — 마지막이 최종.
                    if isinstance(chunk, dict):
                        final_state = chunk

            if final_state is None:
                set_error(job_id, "LangGraph stream 이 final state 를 반환하지 않음")
                return

            full = map_state_to_simulation_output(final_state, request_id)
            winner = full.get("winner_district") or input_data.target_district
            top3 = full.get("top_3_candidates") or []
            try:
                full["all_competitor_locations"] = await _collect_all_competitor_locations(
                    winner, top3, input_data.business_type
                )
            except Exception as ce:
                logger.warning(f"[/analyze/llm/async] all_competitor_locations 실패 (무시): {ce}")
                full["all_competitor_locations"] = []

            analysis_keys = set(AnalysisOutput.model_fields.keys())
            payload = {k: v for k, v in full.items() if k in analysis_keys}
            payload["request_id"] = request_id
            payload["target_district"] = full.get("target_district") or input_data.target_district
            set_done(job_id, _safe_json(payload))
            logger.info(f"[/analyze/llm/async] 완료 job={job_id[:8]}")
        except Exception as e:
            import traceback

            logger.error(f"[/analyze/llm/async] 오류: {e}\n{traceback.format_exc()}")
            set_error(job_id, str(e))

    # GC race 방지 — strong ref 보관, 완료 시 자동 discard.
    task = asyncio.create_task(_run())
    _async_job_tasks.add(task)
    task.add_done_callback(_async_job_tasks.discard)
    return {"job_id": job_id, "status": "running"}


@app.get("/analyze/llm/{job_id}/status")
async def analyze_llm_job_status(job_id: str) -> dict[str, Any]:
    """AI 분석 async job 상태 조회."""
    from src.services.job_progress_store import get_job, serialize_status

    job = get_job(job_id)
    if job is None or job["kind"] != "analyze_llm":
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": f"job {job_id} not found"},
        )
    return serialize_status(job)


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
    company_name: str = ""


@app.post("/biz/lookup")
async def biz_lookup(req: BizLookupRequest):
    """사업자등록번호 + 기업명으로 프랜차이즈 브랜드 매핑.

    company_name 미입력 시 biz_brand_mapping에서 사업자번호로 기업명을 먼저 조회.
    """
    from sqlalchemy import text as sa_text
    from src.database.sync_engine import get_sync_engine

    mapper = BizMapper(
        nts_api_key=os.environ.get("NTS_API_KEY", ""),
    )
    biz_clean = req.biz_number.replace("-", "")
    company = req.company_name.strip()

    # 기업명 미입력 시 biz_brand_mapping에서 조회
    if not company:
        try:
            engine = get_sync_engine(os.environ.get("POSTGRES_URL", ""))
            with engine.connect() as conn:
                row = conn.execute(
                    sa_text(
                        "SELECT company_name, brand_name, industry_large, industry_medium, "
                        "franchise_count, avg_sales, mapo_store_count "
                        "FROM biz_brand_mapping WHERE biz_number = :biz"
                    ),
                    {"biz": biz_clean},
                ).fetchone()
            engine.dispose()
            if row:
                d = dict(row._mapping)
                return {
                    "status": "success",
                    "data": {
                        "verification": {"biz_number": biz_clean, "status": "", "tax_type": "", "valid": True},
                        "brands": [
                            {
                                "brand_name": d["brand_name"],
                                "corp_name": d["company_name"],
                                "industry_large": d.get("industry_large", ""),
                                "industry_medium": d.get("industry_medium", ""),
                                "franchise_count": d["franchise_count"],
                                "avrgSlsAmt": d["avg_sales"],
                                "mapo_store_count": d["mapo_store_count"],
                            }
                        ],
                        "matched_count": 1,
                    },
                }
        except Exception:
            pass
        return {"status": "error", "message": "기업명을 입력해주세요."}

    try:
        result = await mapper.map_franchise(biz_clean, company)
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
    """회원가입 — 사업자 검증 + 브랜드 매핑 + DB 저장 + JWT 발급."""
    from src.services.jwt_auth import create_access_token  # 지역 import (login 패턴 동일)

    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await auth.signup(req.model_dump())
        if result.get("status") == "success" and result.get("user"):
            u = result["user"]
            result["access_token"] = create_access_token(
                user_id=str(u["id"]),
                role="master",
                email=u.get("email", req.email),
            )
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
    """로그인 — 이메일/비밀번호 검증 + 브랜드 정보 + JWT access_token 반환."""
    from src.services.jwt_auth import create_access_token  # 지역 import

    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await run_in_threadpool(auth.login, req.email, req.password)
        if result.get("status") == "success" and result.get("user"):
            u = result["user"]
            result["access_token"] = create_access_token(
                user_id=str(u["id"]),
                role="master",
                email=u.get("email", req.email),
            )
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
    """매니저 회원가입 — 초대코드로 팀장 기업정보 자동 상속.

    [보안] is_approved=false 로 INSERT 되므로 access_token 발급 금지.
    팀장 승인 후 /auth/manager/login 으로만 로그인 가능. (manager_login 은 is_approved 검증 보유)
    """
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await run_in_threadpool(auth.manager_signup, req.model_dump())
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/auth/manager/login")
async def manager_login(req: LoginRequest):
    """매니저 로그인 — JWT access_token 포함."""
    from src.services.jwt_auth import create_access_token

    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await run_in_threadpool(auth.manager_login, req.email, req.password)
        if result.get("status") == "success" and result.get("user"):
            u = result["user"]
            result["access_token"] = create_access_token(
                user_id=str(u["id"]),
                role="manager",
                email=u.get("email", req.email),
                owner_id=str(u.get("owner_id")) if u.get("owner_id") else None,
            )
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
# 회원 탈퇴 API
# ---------------------------------------------------------------------------


class DeactivateBody(BaseModel):
    password: str


@app.post("/auth/user/{user_id}/deactivate")
async def deactivate_user(user_id: str, body: DeactivateBody):
    """팀장 회원 탈퇴 (소프트 삭제 — is_active=false, 소속 매니저·초대코드 일괄 비활성화)"""
    auth = AuthService(nts_api_key=os.environ.get("NTS_API_KEY", ""))
    try:
        result = await run_in_threadpool(auth.deactivate_user, user_id, body.password)
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


@app.get("/mapo/spots/{dong_name}")
async def get_mapo_spots(dong_name: str, limit: int = 4):
    """마포 행정동의 대표 스팟 4개 (지하철역 + 상점 3개) 좌표 조회.

    ABM 프론트엔드 시각화용 — 하드코딩된 DONG_STORE_NODES 대체.
    데이터 소스: data/processed/dong_subway_access.csv + store_info_mapo.csv.
    """
    from src.services.mapo_spots import get_dong_spots

    spots = get_dong_spots(dong_name, limit=limit)
    return {"dong_name": dong_name, "spots": spots}


@app.get("/mapo/spots-all")
async def get_mapo_spots_all(per_dong: int = 3):
    """마포 16동 전체 spot pool (ABM 시각화 마포 전체 dot spread 용).

    동 별 per_dong 개 spot (지하철 + 매장) 합집합 = 16 × per_dong spot.
    AbmPersonaMap 가 마포 전체 spot 풀에서 agent source/target 분배.
    """
    from src.services.mapo_spots import get_all_mapo_spots

    spots = get_all_mapo_spots(per_dong=per_dong)
    return {"per_dong": per_dong, "spots": spots, "n_spots": len(spots)}


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


def _mock_simulation_response(target_district: str, request_id: str) -> dict:
    """LLM_AGENTS_DISABLED=1 테스트 모드 — LangGraph 5 에이전트 건너뛰고 mock 반환.

    ABM 시뮬 (/simulate-abm) 만 테스트할 때 토큰 비용 절약.
    """
    return {
        "request_id": request_id,
        "target_district": target_district,
        "ai_recommendation": f"[테스트 모드] {target_district} — LLM 분석 비활성, ABM만 사용하세요.",
        "market_report": None,
        "comparison": [],
        "legal_risks": [],
        "overall_legal_risk": None,
        "simulation_quarters": 0,
        "quarterly_projection": [],
        "analysis_metrics": {},
        "status": "ok",
        "test_mode": True,
        "data_source": "mock",
    }


@app.post("/predict")
async def predict_districts(input_data: SimulationInput):
    """
    선택 동 1~4개 ML 예측 전용 엔드포인트 (LangGraph 미사용)

    - district_ranking, winner 로직 없음
    - target_districts 전체에 대해 TCN/BEP/폐업률/폐업위험도/SHAP 병렬 실행
    - 응답: 동별 예측 결과 리스트 (프론트 멀티라인 차트용)
    """
    from src.config.constants import MAPO_DISTRICTS

    target_districts = getattr(input_data, "target_districts", None) or [input_data.target_district]
    target_districts = [d for d in target_districts if d in MAPO_DISTRICTS][:4]

    if not target_districts:
        return {"status": "error", "message": "유효한 마포구 행정동이 없습니다."}

    try:
        normalized_biz = _BIZ_TYPE_NORMALIZE.get(
            (input_data.business_type or "").lower(), input_data.business_type or "커피-음료"
        )
        industry_code = _BIZ_TO_INDUSTRY_CODE.get(normalized_biz, "CS100010")

        cost_config = BEPCalculator.get_default_costs(
            normalized_biz,
            initial_capital=getattr(input_data, "initial_capital", 50_000_000),
            monthly_rent=getattr(input_data, "monthly_rent", 2_000_000),
        )

        print(f"--- [/predict] {target_districts} / {normalized_biz} 병렬 ML 예측 시작 ---")

        segment_profile = _build_segment_profile(input_data)

        raw = await asyncio.gather(
            *[
                _predict_single_district(dong, industry_code, normalized_biz, cost_config, segment_profile)
                for dong in target_districts
            ],
            return_exceptions=True,
        )
        results: list[DistrictPredictionResult] = []
        for dong, res in zip(target_districts, raw):
            if isinstance(res, Exception):
                print(f"[/predict] {dong} 예외 (부분 실패 처리): {res}")
                results.append(DistrictPredictionResult(district=dong))
            else:
                results.append(res)

        print(f"--- [/predict] 완료 ({len(results)}개 동) ---")

        payload = _safe_json({"status": "success", "data": [r.model_dump() for r in results]})
        return JSONResponse(content=payload)

    except Exception as e:
        import traceback

        print(f"[/predict] 예상치 못한 오류: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"예측 처리 중 오류가 발생했습니다: {e}"},
        )


# ---------------------------------------------------------------------------
# Real-time progress 지원 — /predict/async + /predict/{job_id}/status.
# 기존 sync /predict 는 회귀 방지 위해 그대로 유지. frontend 가 async 모드로
# 전환 후 실측 진행률(슬라이스 완료 비율)을 250ms polling 으로 받음.
# 단계: 동별 _predict_single_district 가 끝날 때마다 progress = done/total.
# ---------------------------------------------------------------------------
@app.post("/predict/async")
async def predict_districts_async(input_data: SimulationInput) -> dict[str, Any]:
    """ML 예측 비동기 시작 — 즉시 job_id 반환. 진행률은 status endpoint 폴링."""
    from src.config.constants import MAPO_DISTRICTS
    from src.services.job_progress_store import (
        create_job,
        set_done,
        set_error,
        set_progress,
    )

    target_districts = getattr(input_data, "target_districts", None) or [input_data.target_district]
    target_districts = [d for d in target_districts if d in MAPO_DISTRICTS][:4]
    if not target_districts:
        return {"status": "error", "message": "유효한 마포구 행정동이 없습니다."}

    job_id = create_job("predict")
    logger.info(f"[/predict/async] 시작 job={job_id[:8]} dongs={target_districts} biz={input_data.business_type}")

    async def _run() -> None:
        logger.info(f"[/predict/async] _run 진입 job={job_id[:8]}")
        try:
            normalized_biz = _BIZ_TYPE_NORMALIZE.get(
                (input_data.business_type or "").lower(),
                input_data.business_type or "커피-음료",
            )
            industry_code = _BIZ_TO_INDUSTRY_CODE.get(normalized_biz, "CS100010")
            cost_config = BEPCalculator.get_default_costs(
                normalized_biz,
                initial_capital=getattr(input_data, "initial_capital", 50_000_000),
                monthly_rent=getattr(input_data, "monthly_rent", 2_000_000),
            )
            segment_profile = _build_segment_profile(input_data)

            total = len(target_districts)
            # 동별 4 sub-stage (ml_done / projection_done / shap_done / assembled).
            # 단일 동 시뮬도 0% → 25% → 50% → 75% → 100% 단계로 보임.
            # 4동 병렬이면 16 step 누적 — 매 sub-step 마다 6.25%p 진행.
            sub_total = total * 4
            sub_done = 0

            def make_cb(dong: str) -> Callable[[str], None]:
                def cb(label: str) -> None:
                    nonlocal sub_done
                    sub_done += 1
                    set_progress(
                        job_id,
                        min(1.0, sub_done / sub_total),
                        stage=f"{dong} {label}",
                    )

                return cb

            async def _one(dong: str) -> tuple[str, Any]:
                # 진입 즉시 stage 갱신 — progress 는 sub_done 누적 그대로(가짜 % 안 만듦),
                # stage 만 "ML 모델 로딩 중" 으로 변경해 0% 머무는 동안의 시각 신호 제공.
                # ModelOutput.generate 가 가장 무거워 첫 sub-stage(ml_done)까지 5~30s 걸릴 수 있음.
                set_progress(
                    job_id,
                    sub_done / sub_total,
                    stage=f"{dong} ML 모델 추론 중",
                )
                try:
                    r = await _predict_single_district(
                        dong,
                        industry_code,
                        normalized_biz,
                        cost_config,
                        segment_profile,
                        progress_cb=make_cb(dong),
                    )
                except Exception as exc:
                    r = exc
                return dong, r

            raw = await asyncio.gather(*[_one(d) for d in target_districts])

            results: list[DistrictPredictionResult] = []
            for dong, res in raw:
                if isinstance(res, Exception):
                    logger.warning(f"[/predict/async] {dong} 예외 (부분 실패 처리): {res}")
                    results.append(DistrictPredictionResult(district=dong))
                else:
                    results.append(res)

            payload = _safe_json([r.model_dump() for r in results])
            set_done(job_id, payload)
            logger.info(f"[/predict/async] 완료 job={job_id[:8]} count={len(results)}")
        except Exception as e:
            import traceback

            logger.error(f"[/predict/async] 예상치 못한 오류: {e}\n{traceback.format_exc()}")
            set_error(job_id, str(e))

    # GC race 방지 — strong ref 보관, 완료 시 자동 discard.
    task = asyncio.create_task(_run())
    _async_job_tasks.add(task)
    task.add_done_callback(_async_job_tasks.discard)
    return {"job_id": job_id, "status": "running"}


@app.get("/predict/{job_id}/status")
async def predict_job_status(job_id: str) -> dict[str, Any]:
    """ML 예측 async job 상태 조회 — running/done/error + progress 0~1."""
    from src.services.job_progress_store import get_job, serialize_status

    job = get_job(job_id)
    if job is None or job["kind"] != "predict":
        return JSONResponse(
            status_code=404,
            content={"status": "error", "message": f"job {job_id} not found"},
        )
    return serialize_status(job)


@app.post("/simulate", deprecated=True)
async def run_simulation(input_data: SimulationInput, response: Response):
    """기본 시뮬레이션 엔드포인트"""
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</predict>; rel="successor-version", </analyze/llm>; rel="successor-version"'

    from src.config.constants import MAPO_DISTRICTS

    if input_data.target_district not in MAPO_DISTRICTS:
        return {
            "status": "error",
            "message": f"지원하지 않는 행정동입니다: {input_data.target_district}. 마포구 16개 동만 지원합니다.",
        }

    request_id = str(uuid.uuid4())

    # 테스트 모드 — LLM 5 에이전트 분석 건너뛰기 (토큰 절약)
    if os.getenv("LLM_AGENTS_DISABLED", "").strip() == "1":
        print(f"[SIMULATE] LLM_AGENTS_DISABLED=1 — mock 반환 (target={input_data.target_district})")
        return _mock_simulation_response(input_data.target_district, request_id)

    try:
        final_state = await _run_pipeline(input_data)
        result = map_state_to_simulation_output(final_state, request_id)

        # /analyze 와 동일하게 winner+top3 의 경쟁업체 좌표 수집 — 지도 멀티핀용.
        # (이전: /simulate 만 누락돼 frontend `allCompetitorLocations: undefined`)
        winner = result.get("winner_district") or input_data.target_district
        top3 = result.get("top_3_candidates") or []
        try:
            result["all_competitor_locations"] = await _collect_all_competitor_locations(
                winner, top3, input_data.business_type
            )
        except Exception as ce:
            print(f"[SIMULATE] all_competitor_locations 수집 실패 (무시): {ce}")
            result["all_competitor_locations"] = []

        # competitor_intel 진단 — None/error 면 frontend 에서 hex/카드 안 보임.
        ci = result.get("competitor_intel")
        if ci is None:
            print("[SIMULATE] WARNING: competitor_intel is None — competitor_intel_node 미실행 또는 state 누락.")
        elif isinstance(ci, dict) and ci.get("error"):
            print(f"[SIMULATE] WARNING: competitor_intel error — {ci.get('error')}")
        elif isinstance(ci, dict) and not ci.get("competition_500m"):
            print(f"[SIMULATE] WARNING: competitor_intel.competition_500m 누락 — keys: {list(ci.keys())}")

        return result
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
            "overall_legal_risk": None,
            "simulation_quarters": 0,
            "quarterly_projection": [],
            "analysis_report": f"분석 중 오류가 발생했습니다: {str(e)}",
            "analysis_metrics": {},
            "demographic_report": None,
            "trend_forecast": None,
            "map_data": None,
            "financial_report": {},
            # [스키마 일관성] SimulationOutput optional 필드 명시적 null
            "winner_district": None,
            "top_3_candidates": [],
            "district_rankings": [],
            "vacancy_applied": False,
            "vacancy_spots": [],
            "shap_result": None,
            "scenarios": None,
            "closure_rate": None,
            "closure_risk": None,
            "competitor_intel": None,
            "agent_attributions": [],
            "customer_segment": None,
            "living_pop_forecast": None,
            "emerging_signal": None,
        }


# ---------------------------------------------------------------------------
# ABM 시뮬레이션 엔드포인트 — 기존 5 에이전트와 완전 독립
# /simulate 결과를 입력받아 행동 시뮬만 실행, 분석 결과에 영향 없음
# A1 인터페이스 계약 (policy-generator-design.md) 준수
# ---------------------------------------------------------------------------
class AbmScenarioParams(BaseModel):
    """GameMaster에 전달되는 시나리오 파라미터 (A1 Scenario dataclass와 1:1 대응)"""

    weather_override: str | None = None  # "맑음"|"비"|"눈"|None(RDS 최신 날씨)
    date_override: str | None = None  # "2026-04-25" ISO 날짜, None=오늘
    weekend_force: bool = False  # True=주말 강제, date_override 무시
    rent_shock_pct: float = 0.0  # 0.0~0.5 (0.3 = +30%)


class AbmSimulationRequest(BaseModel):
    # LangGraph 분석 컨텍스트
    target_district: str
    business_type: str
    brand_name: str
    langgraph_result: dict[str, Any]
    # 시뮬 규모
    n_agents: int = 100  # 100 | 1000
    days: int = 1
    # GameMaster 시나리오
    scenario: AbmScenarioParams = AbmScenarioParams()
    # 공실 스팟 클릭 시 그 좌표 (optional) — 지도에 매장 정확히 찍기 위해
    spot_lat: float | None = None
    spot_lon: float | None = None
    # 신규 매장 평수 (frontend storeArea state) — seats=store_area*2 로 capacity 영향.
    # 작은 매장은 daily visits cap, 큰 매장은 cap 여유 → 시뮬 정확도 ↑.
    store_area: float = 15.0
    # Tier S 50 LLM thought 활성 (default off, 비용 발생 — demo 시나리오용)
    enable_llm_thought: bool = False
    # Tier S/A LLM 의사결정 활성 (default off, $0.5~2/sim, +60~180s)
    # True 시 use_policy=False → Tier S→Haiku, Tier A→Gemini Flash, Tier B→rule
    # False 시 전 Tier policy_decide (deterministic, $0)
    enable_llm_decisions: bool = False
    # 비동기 모드 — True 시 즉시 job_id 반환, 시뮬은 background thread.
    # 클라이언트 disconnect 해도 시뮬 끝까지 진행, 결과는 in-memory cache 보존.
    # GET /simulate-abm/{job_id}/status, /result 로 polling 조회.
    async_mode: bool = False


@app.post("/simulate-abm")
async def run_abm_simulation(req: AbmSimulationRequest):
    """
    ABM 행동 시뮬레이션 — 의사결정 에이전트와 완전 분리된 독립 기능.
    LangGraph 5 에이전트 분석 결과를 시나리오로 주입해 소비자 행동을 시뮬한다.
    기존 분석 결과(analysis_report, analysis_metrics 등)는 절대 수정하지 않는다.
    """
    try:
        from src.simulation.config import (
            ModelConfig,
            PopulationMix,
            Scenario,
            TierDistribution,
        )
        from src.simulation.runner import run_simulation as abm_run
        from src.simulation.vacancy_inject import DEFAULT_POPULARITY_BOOST
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

    # 신규 매장 popularity_boost — calibration 값.
    # 출처: Pancras, Sriram & Kumar (2012) Mgmt Sci 58(11) — chain 내 cannibalization
    # 13.3%, incremental 86.7%. 본 boost(2.0) 는 직접 도출 X, vacancy_inject DEFAULT 5.0
    # (마케팅 가정) 대비 1.5~2.5x 범위에서 보정한 calibration.
    # TODO: KOSIS 외식업체 경영실태조사로 신규/기존 매출비 별도 검증 필요.
    _NEW_STORE_BOOST = 2.0

    # seats 계산 — 카테고리별 좌석밀도. 한국 실증 데이터로 검증 완료.
    # 출처:
    #   - Neufert Architects' Data (4판): dining 1.4~1.6 m²/석 → ≈ 2.0~2.4 석/평
    #   - 한국 식품위생법 시행규칙 별표 14: 좌석밀도 정량 기준 없음 (자유)
    #   - 한국 카페 실측: 스타벅스 1호점(이대점) 80평/100석 = 1.25 석/평,
    #     일반 카페 창업 가이드 10평/11석 = 1.1 석/평 → 평균 ~1.2 석/평 적정
    #   - 한국 음식점 실측: 건축계획 1인당 1.2~1.5㎡ → 2.2~2.75 석/평,
    #     구내식당 1.5~2㎡/인 → 1.65~2.2 석/평 → 중간값 2.0 적정
    #   - 한국 주점: 호프집 4인 테이블 + 통로 → 1.7~1.9 석/평 (업계 통념, 공식 통계 부재)
    _SEATS_PER_PYEONG = {
        "카페": 1.2,  # 한국 일반 카페 1.1~1.25 평균
        "음식점": 2.0,  # Neufert + 한국 건축계획 중간값
        "주점": 1.8,  # 한국 호프집 통념 (1.7~1.9)
    }
    _seat_ratio = _SEATS_PER_PYEONG.get(req.business_type, 2.0)
    # min 8 (작은 키오스크), max 200 (대형 매장). visits_today / seats 기반 capacity 모델링.
    _seats = max(8, min(200, int(round(req.store_area * _seat_ratio))))

    new_store_spec = {
        "district": req.target_district,
        "brand": req.brand_name,
        "category": req.business_type,
        "score": lr.get("score"),
        "estimated_revenue": market_report.get("estimated_revenue"),
        "competition_intensity": market_report.get("competition_intensity"),
        "main_target_age": analysis_metrics.get("main_target_age"),
        "peak_time": analysis_metrics.get("peak_time"),
        # 공실 스팟 클릭 시 좌표 (Optional) — 지도에 정확한 위치 표시
        "lat": req.spot_lat,
        "lon": req.spot_lon,
        # 신규 매장 weight 부스트 — 기존 매장 (~100+개) 와 경쟁할 수 있도록
        "popularity_boost": _NEW_STORE_BOOST,
        # 평수 → seats — capacity 모델링 (작은 매장은 visits cap)
        "store_area": req.store_area,
        "seats": _seats,
    }

    # PopulationMix — SGIS API 직접 회수 데이터 기반 재캘리브.
    # 출처: 통계청 SGIS Open API (sgisapi.mods.go.kr/OpenAPI3) — 2026-04-29 호출.
    #   adm_cd=11140 (마포구) 인구주택총조사 + 전국사업체조사 2023 회수:
    #     /stats/population.json: 거주 361,380 / 가구 167,410 / 평균연령 42.2 /
    #                             인구밀도 15,155.5/km² / 평균가구원 2.1
    #     /stats/company.json:    사업체 52,888 / 종사자 281,385
    #   통근 유입 추정 (SGIS /stats/move/* endpoint 부재 → 간접 추정):
    #     - 마포 거주 노동인구 (15-64세 × 경활률 65%) ≈ 165K
    #     - 마포 내 근무 거주민 (마포 통근율 30-40% 가정) ≈ 50-70K
    #     - 외부 유입 통근 ≈ 281K - 60K = 221K (peak hour)
    #     - 24h 평균 외부 비중 = 9h × 221K / (361K × 24) ≈ 18%
    #     - Peak hour 활성 비중 ≈ 30-37%
    #     → 본 코드 25% ext 는 평균과 peak 사이 적정값.
    # 이전 (residents 12%, ext 80%) 은 강남(11230 종사자/거주=1.51)급 가정 →
    # 마포(0.78) 실측 대비 과도. 25% 로 보정.
    # TODO: SGIS jobmap API 또는 KOSIS DT_201004_O020021 직접 회수 시 추가 검증.
    pop = PopulationMix(
        residents=300,  # 60% — 마포 거주민 (SGIS 361,380 비례)
        commuters=50,  # 10% — 마포 내 통근 (거주+근무)
        visitors=20,  # 4% — 마포 거주 단기 방문
        owners=5,  # 1% — 점주
        ext_commuters=100,  # 20% — 외부→마포 통근 (사업체 종사 281,385 일부)
        ext_visitors=25,  # 5% — 외부 방문 (홍대·연남 야간)
    )
    # Tier 분배 — enable_llm_decisions 시 Tier S 정확히 50명 고정 (시각화 풍선 50과 1:1).
    # 미사용 시 5/20/75 비율로 두면 runner.py 가 n_personas 기준 자동 scale.
    if req.enable_llm_decisions:
        # tier_total == n_personas 면 runner.py 의 auto-scale 건너뜀 → 50 그대로 유지.
        tier = TierDistribution(
            tier_s=50,
            tier_a=200,
            tier_b=max(0, req.n_agents - 250),
        )
    else:
        tier = TierDistribution(tier_s=5, tier_a=20, tier_b=75)
    # 전 Tier OpenAI gpt-4.1-mini 통일 — Anthropic/Gemini 키 분기 제거,
    # 단일 provider 로 비용·rate-limit 단순화. generate_thought 도 동일 모델 사용 중.
    cfg = ModelConfig(
        n_personas=req.n_agents,
        tier_s_provider="openai",
        tier_s_model="gpt-4.1-mini",
        tier_a_provider="openai",
        tier_a_model="gpt-4.1-mini",
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

    # --- Redis 캐시 키 구성 (스팟·시나리오·규모 조합) ---
    import hashlib
    import json as _json

    cache_payload = {
        "district": req.target_district,
        "category": req.business_type,
        "brand": req.brand_name,
        "n_agents": req.n_agents,
        "days": req.days,
        "spot_lat": req.spot_lat,
        "spot_lon": req.spot_lon,
        "weather": req.scenario.weather_override,
        "date": req.scenario.date_override,
        "weekend": req.scenario.weekend_force,
        "rent_shock": req.scenario.rent_shock_pct,
        "enable_llm_thought": req.enable_llm_thought,
        "enable_llm_decisions": req.enable_llm_decisions,
    }
    # cache 버전 prefix — 응답 schema 변경(trajectory/thoughts 추가) 시 bump 해 기존 캐시 무효화.
    # v2: collect_trajectory=True 회귀 fix + thoughts 필드 (2026-04-28).
    # v3: 신규 매장 popularity_boost=5.0 적용 (visits=0 회귀 fix, 2026-04-28).
    # v4: Tier S/A LLM decisions 도입 (use_llm_decisions, 2026-04-29).
    # v5: 전 Tier OpenAI gpt-4.1-mini 통일 (Haiku/Gemini 제거, 2026-04-29).
    # v6: Tier S 50 전용 LLM 모드 (Tier A/B → policy_decide, 2026-04-29).
    cache_key = (
        "abm_sim:v6:"
        + hashlib.sha256(_json.dumps(cache_payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32]
    )

    cached_result: dict | None = None
    try:
        async with aioredis.from_url(settings.redis_url, decode_responses=True) as r:
            raw = await r.get(cache_key)
            if raw:
                cached_result = _json.loads(raw)
                logger.info(f"[ABM] cache HIT key={cache_key[:16]}...")
    except Exception as e:
        logger.warning(f"[ABM] Redis 캐시 조회 실패(무시): {e}")

    if cached_result is not None:
        # 캐시 히트 — 저장된 응답 그대로 반환 (request_id 만 새로)
        cached_result["cached"] = True
        return cached_result

    # ----------------------------------------------------------------------
    # async_mode=True — job_id 즉시 반환, 시뮬은 background thread.
    # 클라이언트 disconnect 해도 시뮬 끝까지 진행, 결과는 abm_jobs_cache 에 보존.
    # 동기 모드는 backward compat 위해 아래 기존 코드 그대로 유지.
    # ----------------------------------------------------------------------
    if req.async_mode:
        from src.services.abm_simulation_service import run_abm_async

        job_id = run_abm_async(
            pop=pop,
            tier=tier,
            cfg=cfg,
            scenario=scenario,
            days=req.days,
            enable_llm_thought=req.enable_llm_thought,
            collect_trajectory=True,
            seed_memory=False,
            use_llm_decisions=req.enable_llm_decisions,
            llm_concurrency=8,
            target_district=req.target_district,
            n_agents=req.n_agents,
            weather_override=req.scenario.weather_override,
            weekend_force=req.scenario.weekend_force,
            rent_shock_pct=req.scenario.rent_shock_pct,
            date_override=req.scenario.date_override,
            langgraph_result=lr,
            cache_key=cache_key,
            redis_url=settings.redis_url,
        )
        logger.info(f"[ABM] async job started: job_id={job_id}")
        return {"job_id": job_id, "status": "running", "cached": False}

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
            enable_llm_thought=req.enable_llm_thought,
            # ⚠️ 누락 시 trajectory=None 반환 → 프론트 trajectory 기반 렌더 전부 차단.
            # vacancy_evaluation 엔드포인트는 정상 전달 중 — 여기만 누락된 회귀였음.
            collect_trajectory=True,
            # 매 호출마다 5000 agent × 14일 가상 visit history 생성하던 cold-start
            # mitigation — /simulate-abm 시연용엔 불필요 (응답 2~5s 절감).
            seed_memory=False,
            # Tier S 전용 LLM 의사결정 옵션 — Tier A/B는 policy_decide 유지.
            use_llm_decisions=req.enable_llm_decisions,
            # LLM 동시 호출 수 — 모드별 단일 메커니즘 활성:
            #   - enable_llm_decisions=True: smart_decide ThreadPool(8) 만 사용
            #   - enable_llm_decisions=False + enable_llm_thought=True: thought Semaphore(8) 만 사용
            # 8 concurrent × 1.5s/call ≈ 320 RPM (OpenAI Tier 1 500 RPM 안).
            # 4→8 상향으로 Tier S LLM 대기 60-90s 절감 (5000 agents 기준).
            # 429 발생 시 brain.py:_smart_decide_openai 가 0.5/1/2s backoff 로 재시도.
            llm_concurrency=8,
        )
    except Exception as e:
        logger.error(f"[ABM] 시뮬레이션 실패: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"ABM 시뮬레이션 실패: {e}"},
        )

    # 동별 집계에서 target_district만 추출 (동마다 지표 달라지도록)
    dong_totals = result.get("dong_totals") or {}
    target_dong_stats = dong_totals.get(req.target_district, {})
    target_visits = int(target_dong_stats.get("visits", 0))
    target_revenue = float(target_dong_stats.get("revenue", 0))

    # fallback — target_district 매장이 없으면 전체 평균으로 대체 (비교 가능하게)
    if target_visits == 0 and dong_totals:
        # 마포 전체 평균값 × 1동 비율 (16개 동 기준)
        all_visits = sum(d.get("visits", 0) for d in dong_totals.values())
        all_revenue = sum(d.get("revenue", 0) for d in dong_totals.values())
        target_visits = int(all_visits / max(len(dong_totals), 1))
        target_revenue = all_revenue / max(len(dong_totals), 1)

    # narrator를 target_district 맞춤으로 재작성
    target_narrator = (
        f"{req.target_district} 상권 기준 일 방문 {target_visits:,}회, "
        f"일 매출 약 {int(target_revenue):,}원. "
        f"시나리오: {req.scenario.weather_override or '현재날씨'} · "
        f"{'주말' if req.scenario.weekend_force else '평일'} · "
        f"임대료 +{int(req.scenario.rent_shock_pct * 100)}%."
    )

    response = {
        "status": "ok",
        "target_district": req.target_district,
        "n_personas": req.n_agents,
        "scenario_applied": {
            "weather": req.scenario.weather_override or "현재날씨",
            "weekend": req.scenario.weekend_force,
            "rent_shock_pct": req.scenario.rent_shock_pct,
            "date": req.scenario.date_override or "오늘",
        },
        # target_district 중심 지표 (동별로 다름)
        "daily_visits_mean": target_visits,
        "daily_visits_std": result.get("daily_visits_std", 0),
        "daily_revenue_mean": target_revenue,
        "daily_revenue_std": result.get("daily_revenue_std", 0),
        "monthly_revenue_estimate": round(target_revenue * 25),
        # 전체 지표 (참고용)
        "total_daily_visits": result.get("daily_visits", 0),
        "total_daily_revenue": result.get("daily_revenue", 0),
        "peak_hours": result.get("peak_hours", []),
        "customer_profile_dist": result.get("customer_profile_dist", {}),
        "dong_totals": dong_totals,  # 프론트에서 동별 비교 차트용
        "cannibalization": result.get("cannibalization", {}),
        "narrator_summary": target_narrator,
        "trajectory": result.get("trajectory"),  # 미로피쉬 재생용
        # 5000 agent 전체 시간별 위치 집계 — frontend 히트맵 layer (28×24 격자, ~43KB).
        "density_grid": result.get("density_grid"),
        # 신규 매장(공실 스팟 클릭) 지표 — 프론트 결과 카드용
        "new_store_visits": result.get("new_store_visits", 0),
        "new_store_revenue": result.get("new_store_revenue", 0.0),
        "new_store_visit_share_pct": result.get("new_store_visit_share_pct", 0.0),
        # Tier S thought (시각화용 내적 독백) — enable_llm_thought=True 일 때만 채워짐
        "thoughts": result.get("thoughts", []),
        "thought_calls": result.get("thought_calls", 0),
        "thought_input_tokens": result.get("thought_input_tokens", 0),
        "thought_output_tokens": result.get("thought_output_tokens", 0),
        "thought_cached_tokens": result.get("thought_cached_tokens", 0),
        "tier_s_calls": result.get("tier_s_calls", 0),
        "tier_a_calls": result.get("tier_a_calls", 0),
        "estimated_cost_usd": result.get("estimated_cost_usd", 0.0),
        # 캐시 여부 (cache miss 라 False)
        "cached": False,
        # 원본 LangGraph 분석 결과 — 수정 없음
        "langgraph_result": lr,
    }

    # 응답 Redis 캐시 저장 (TTL 1시간) — 같은 스팟·시나리오 재요청 시 즉시 반환
    # trajectory 는 무거우니 캐시 본문에서 제거 후 저장 (핵심 지표만 보존)
    try:
        async with aioredis.from_url(settings.redis_url, decode_responses=True) as r:
            cache_body = {k: v for k, v in response.items() if k != "trajectory"}
            await r.setex(cache_key, 3600, _json.dumps(cache_body, ensure_ascii=False))
            logger.info(f"[ABM] cache SET key={cache_key[:16]}... ttl=3600s")
    except Exception as e:
        logger.warning(f"[ABM] Redis 캐시 저장 실패(무시): {e}")

    return response


# ---------------------------------------------------------------------------
# /simulate-abm 비동기 polling 엔드포인트 (job_id 패턴)
# 시뮬은 background thread 에서 진행, 결과는 abm_jobs_cache 보존.
# vacancy_evaluation.py 의 _require_done_job 패턴 차용.
# ---------------------------------------------------------------------------
@app.get("/simulate-abm/{job_id}/status")
def get_abm_job_status(job_id: str) -> dict[str, Any]:
    """ABM async job 상태 조회 — running / done / failed.

    응답:
        {
            "job_id": str,
            "status": "running" | "done" | "failed",
            "elapsed_seconds": int,
            "progress": str | None,    # "queued"|"running_simulation"|"building_response"|"done"|"failed"
            "error": str | None,       # failed 시만
        }
    """
    import time as _time

    from src.services.abm_simulation_service import cleanup_old_jobs, get_job

    # status endpoint 진입 시 가벼운 cleanup (만료 1h 초과 job 제거)
    cleanup_old_jobs(ttl_seconds=3600)

    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    return {
        "job_id": job_id,
        "status": job["status"],
        "elapsed_seconds": int(_time.time() - job["started_at"]),
        "progress": job.get("progress"),
        "error": job.get("error"),
    }


@app.get("/simulate-abm/{job_id}/result")
def get_abm_job_result(job_id: str) -> dict[str, Any]:
    """ABM async job 결과 조회.

    상태별 응답:
        - done: cache[job_id]["result"] (동기 /simulate-abm 응답과 동일 schema)
        - running: 409 Conflict
        - failed: 500 Internal Server Error
        - not found: 404
    """
    from src.services.abm_simulation_service import get_job

    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    if job["status"] == "running":
        raise HTTPException(status_code=409, detail="job still running")
    if job["status"] == "failed":
        raise HTTPException(status_code=500, detail=job.get("error", "unknown error"))
    # done — Redis 저장은 run_abm_async 내부에서 이미 처리됨
    return job["result"]
