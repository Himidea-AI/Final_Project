# demographic_depth Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. 각 Task 단위 commit.

**Goal:** SPOTTER에 신규 LangGraph agent `demographic_depth`를 추가. 매출을 연령/성별/시간대/요일로 분해하여 "누가 얼마 쓰는가" 분석.

**Architecture:** 기존 `parallel_analysis_node`의 asyncio.gather에 1개 에이전트 추가. Redis 캐시(v2 컨벤션) + 4 테이블 병렬 조회 + `get_fast_llm().with_structured_output()` LLM 해석 + synthesis에 `demographic_report` 필드로 전달(legal 14개 항목 보존 유지).

**Tech Stack:** Python 3.12 + SQLAlchemy 2.x (raw SQL where ORM absent) + Pydantic v2 + LangGraph + LangChain (Gemini Flash 또는 gpt-4.1-mini).

**Context:** 원 스펙은 `demographic_depth_agent` 작성 요청이었으나 실제 구조 조사로 여러 오류 확인:
- 스펙의 `backend/app/agents/` → 실제 `backend/src/agents/`
- 스펙의 `district_sales_seoul` (53컬럼) → 실제 `district_sales` (53컬럼, 마포구 한정 3703행)
- `elderly_ratio_region`: 시도 단위만(18 region). 행정동 단위 고령 비율 제공 불가 → 서울시 평균(20.7%) 사용 + 행정동 단위는 `seoul_adstrd_flpop.age_60_above` (유동인구 기반)로 보조
- `kosis_regional_income`: 서울특별시 시도 단위만 → 서울 평균 소득 사용
- `seoul_realtime_hotspots`: POI 단위. 마포 3개 POI(홍대/합정/연남) + 월드컵공원 1개 → POI-동 매핑 딕셔너리 필요
- `resident_pop_monthly.region_code`는 10자리(예: 1144066000 서교동), `district_sales.dong_code`는 8자리(11440660) — 매핑 공식 `region_code = dong_code + "00"`

## File Structure

### 신규 파일
- `backend/src/agents/nodes/demographic_depth.py` — 에이전트 본체
- `backend/src/schemas/demographic.py` — Pydantic Output 모델 (LLM structured output용)
- `backend/tests/test_demographic_depth.py` — 통합 테스트 (pytest-asyncio)

### 수정 파일
- `backend/src/agents/tools.py` — 3개 DB 조회 함수 추가 (`MarketDataTool` 클래스에 메서드 추가)
- `backend/src/schemas/state.py` — `AgentState`에 `brand_name`, `industry_filter`(이미 있으면 무시), `demographic_report` 필드 추가
- `backend/src/agents/graph.py` — `parallel_analysis_node`의 asyncio.gather에 `demographic_depth_node` 추가
- `backend/src/agents/nodes/synthesis.py` — 입력에서 `demographic_report` 읽어 프롬프트 섹션으로 추가 (**legal_risks 14개 보존 invariant 절대 유지** — 라인 66·173-174 주석 확인)
- `backend/src/main.py` — `/simulate` 응답 스키마에 `demographic_depth` 섹션 추가 (선택)

### 건드리지 않는 파일
- `backend/src/database/models.py` — ORM 모델 추가는 A1(찬영) 영역. raw SQL로 우회
- `backend/src/agents/nodes/{market_analyst,population,legal}.py`
- `frontend/*` — 이번 스펙 범위 아님 (나중에 C1에서 별도 PR)

## POI → Dong 매핑 상수

```python
# tools.py 상단 상수로 정의
_MAPO_POI_TO_DONG: dict[str, str] = {
    "POI007": "11440660",  # 홍대 관광특구 → 서교동
    "POI053": "11440680",  # 합정역 → 합정동
    "POI073": "11440710",  # 연남동 → 연남동
    "POI106": "11440740",  # 월드컵공원 → 상암동
}
```

역매핑(dong_code → POI list): 동 하나에 POI 여러 개 매핑될 수 있으므로 list.

---

## Task 1: `tools.py` — 3개 DB 조회 함수 (TDD, 1 commit per fn)

**Files:**
- Modify: `backend/src/agents/tools.py`
- Create: `backend/tests/test_tools_demographic.py`

### Step 1: `get_demographic_sales_breakdown(dong_code, industry_filter=None)`

```python
# 실패 테스트 먼저
import pytest
from src.agents.tools import MarketDataTool
from src.database.postgres import PostgresClient
from src.config.settings import settings

@pytest.mark.asyncio
async def test_demographic_sales_breakdown_seogyo_coffee():
    db = PostgresClient(settings.postgres_url)
    await db.connect()
    tool = MarketDataTool(db)
    result = await tool.get_demographic_sales_breakdown("11440660", industry_filter="CS100010")
    assert result["monthly_sales"] > 0
    assert "age_breakdown" in result and len(result["age_breakdown"]) == 6  # age_10~age_60_above
    assert "gender_breakdown" in result and set(result["gender_breakdown"].keys()) == {"male", "female"}
    assert "time_breakdown" in result and len(result["time_breakdown"]) == 6
    assert "weekday_breakdown" in result and len(result["weekday_breakdown"]) == 7
    assert "quarter" in result  # 최신 분기 identifier
```

구현 (async method on `MarketDataTool`):
```python
async def get_demographic_sales_breakdown(
    self, dong_code: str, industry_filter: str | None = None
) -> dict:
    async with self.db_client.get_session() as session:
        # 최신 분기 찾기
        latest_q = await session.execute(text(
            "SELECT MAX(quarter) FROM district_sales WHERE dong_code = :dc"
            + (" AND industry_code = :ic" if industry_filter else "")
        ), {"dc": dong_code, "ic": industry_filter})
        q = latest_q.scalar()
        if q is None:
            return {"error": "no sales data", "dong_code": dong_code}

        query = text("""
            SELECT
                SUM(monthly_sales) AS total_sales,
                SUM(age_10_sales) AS a10, SUM(age_20_sales) AS a20, SUM(age_30_sales) AS a30,
                SUM(age_40_sales) AS a40, SUM(age_50_sales) AS a50, SUM(age_60_above_sales) AS a60p,
                SUM(male_sales) AS male, SUM(female_sales) AS female,
                SUM(time_00_06_sales) AS t0_6, SUM(time_06_11_sales) AS t6_11, SUM(time_11_14_sales) AS t11_14,
                SUM(time_14_17_sales) AS t14_17, SUM(time_17_21_sales) AS t17_21, SUM(time_21_24_sales) AS t21_24,
                SUM(mon_sales) AS mon, SUM(tue_sales) AS tue, SUM(wed_sales) AS wed,
                SUM(thu_sales) AS thu, SUM(fri_sales) AS fri, SUM(sat_sales) AS sat, SUM(sun_sales) AS sun,
                SUM(weekday_sales) AS weekday, SUM(weekend_sales) AS weekend
            FROM district_sales
            WHERE dong_code = :dc AND quarter = :q
        """ + (" AND industry_code = :ic" if industry_filter else ""))
        params = {"dc": dong_code, "q": q}
        if industry_filter: params["ic"] = industry_filter

        r = (await session.execute(query, params)).mappings().one()
        total = r["total_sales"] or 0
        if total == 0:
            return {"error": "zero sales", "dong_code": dong_code, "quarter": q}

        return {
            "dong_code": dong_code,
            "quarter": q,
            "monthly_sales": total,
            "age_breakdown": {
                "10": r["a10"] or 0, "20": r["a20"] or 0, "30": r["a30"] or 0,
                "40": r["a40"] or 0, "50": r["a50"] or 0, "60+": r["a60p"] or 0,
            },
            "gender_breakdown": {"male": r["male"] or 0, "female": r["female"] or 0},
            "time_breakdown": {
                "00-06": r["t0_6"] or 0, "06-11": r["t6_11"] or 0, "11-14": r["t11_14"] or 0,
                "14-17": r["t14_17"] or 0, "17-21": r["t17_21"] or 0, "21-24": r["t21_24"] or 0,
            },
            "weekday_breakdown": {
                "mon": r["mon"] or 0, "tue": r["tue"] or 0, "wed": r["wed"] or 0,
                "thu": r["thu"] or 0, "fri": r["fri"] or 0, "sat": r["sat"] or 0, "sun": r["sun"] or 0,
            },
            "weekday_vs_weekend": {"weekday": r["weekday"] or 0, "weekend": r["weekend"] or 0},
        }
```

Commit: `feat(B1): demographic 매출 분해 쿼리 함수 추가`

### Step 2: `get_realtime_resident_visitor(dong_code)`

POI 매핑 기반. 매핑 없는 동은 `{"resident_rate": None, "visitor_rate": None, "source_poi": None}` 반환.

**TDD test**:
- 서교동(11440660) → POI007 매칭 → `resident_rate`, `visitor_rate` 실수 반환
- 염리동(11440610) → POI 없음 → None
- 최근 7일 평균 계산 (collected_at 기준)

구현 요점:
```python
async def get_realtime_resident_visitor(self, dong_code: str) -> dict:
    # dong_code -> POI list (역매핑)
    reverse = {"11440660":["POI007"], "11440680":["POI053"], "11440710":["POI073"], "11440740":["POI106"]}
    poi_list = reverse.get(dong_code, [])
    if not poi_list:
        return {"resident_rate": None, "visitor_rate": None, "source_poi": None}
    # 최근 7일 평균
    query = text("""
        SELECT AVG(resident_rate) AS r, AVG(visitor_rate) AS v, COUNT(*) AS n
        FROM seoul_realtime_hotspots
        WHERE area_cd = ANY(:pois) AND collected_at >= NOW() - INTERVAL '7 days'
    """)
    async with self.db_client.get_session() as session:
        r = (await session.execute(query, {"pois": poi_list})).mappings().one()
        return {
            "resident_rate": float(r["r"]) if r["r"] is not None else None,
            "visitor_rate": float(r["v"]) if r["v"] is not None else None,
            "source_poi": poi_list,
            "sample_size": r["n"],
        }
```

Commit: `feat(B1): 실시간 거주/방문 비율 조회 함수 추가 (POI→동 매핑)`

### Step 3: `get_area_income_context(dong_code)`

3개 서브쿼리 병렬:
- `kosis_regional_income` from region_code='11' (서울특별시), 최신 period_code, item_code='T3'(1인당 가계처분가능소득) → `area_income_per_capita`
- `elderly_ratio_region` where region='서울특별시' 최신 ym → `elderly_ratio` (서울 전체 평균)
- `resident_pop_monthly` where region_code = dong_code + '00', 최근 6개월 total_pop 추이 → `population_trend` (`growing`/`stable`/`declining`)

```python
async def get_area_income_context(self, dong_code: str) -> dict:
    async with self.db_client.get_session() as session:
        # 병렬 실행: asyncio.gather 3개 쿼리
        import asyncio
        results = await asyncio.gather(
            self._fetch_seoul_income(session),
            self._fetch_seoul_elderly(session),
            self._fetch_dong_pop_trend(session, dong_code),
            return_exceptions=True,
        )
        income, elderly, trend = results
        return {
            "area_income_per_capita": income if not isinstance(income, Exception) else None,
            "elderly_ratio": elderly if not isinstance(elderly, Exception) else None,
            "population_trend": trend if not isinstance(trend, Exception) else "unknown",
            "income_level": self._classify_income_level(income if not isinstance(income, Exception) else None),
        }

def _classify_income_level(self, income: float | None) -> str:
    if income is None: return "unknown"
    # 서울 1인당 처분가능소득 ~2500만원 기준. 전국 평균 약 2400만.
    if income > 2700: return "high"
    if income < 2300: return "low"
    return "mid"
```

(`_fetch_*` 프라이빗 메서드 3개 병기. trend 계산: 최근 3개월 vs 그 이전 3개월 총 인구 비교, >+1% → growing, <-1% → declining, else stable)

Commit: `feat(B1): 소득/고령/인구추세 컨텍스트 조회 함수 추가`

---

## Task 2: Pydantic Output 모델 + State 확장 (1 commit)

**Files:**
- Create: `backend/src/schemas/demographic.py`
- Modify: `backend/src/schemas/state.py`

```python
# demographic.py
from pydantic import BaseModel, Field
from typing import Optional

class CoreDemographic(BaseModel):
    age: str = Field(description="주타겟 연령대 (예: '20-30')")
    gender: str = Field(description="주타겟 성별 (male/female/mixed)")
    share: float = Field(description="해당 세그먼트 매출 비중 (0-1)")

class AgeShare(BaseModel):
    age_group: str
    share: float

class DemographicAnalysis(BaseModel):
    """LLM 생성: 브랜드 타겟 매칭 + 자연어 요약"""
    brand_target_match_score: Optional[float] = Field(None, description="0-100, 브랜드 없으면 None")
    match_rationale: Optional[str] = None
    narrative: str = Field(description="3-5줄 자연어 요약")

class DemographicReport(BaseModel):
    """에이전트 최종 출력 = State에 저장됨"""
    core_demographic: CoreDemographic
    top_3_age_groups: list[AgeShare]
    peak_consumption_hours: list[str]  # ["17-21", "11-14"]
    weekday_weekend_ratio: float
    resident_visitor_ratio: Optional[float]  # None = 데이터 없음
    area_income_level: str  # high/mid/low/unknown
    population_trend: str  # growing/stable/declining/unknown
    elderly_ratio: Optional[float]  # 서울 전체 평균 (행정동 단위 없음)
    brand_target_match_score: Optional[float]
    match_rationale: Optional[str]
    narrative: str
```

**state.py** 변경:
```python
class AgentState(TypedDict, total=False):
    # ... 기존 필드 ...
    industry_filter: Optional[str]  # 추가 (brand_name은 이미 있음)
    demographic_report: Optional[dict]  # DemographicReport.model_dump() 결과
```

Test (기본 스모크):
```python
def test_demographic_report_schema_roundtrip():
    from src.schemas.demographic import DemographicReport, CoreDemographic, AgeShare
    r = DemographicReport(
        core_demographic=CoreDemographic(age="20-30", gender="female", share=0.42),
        top_3_age_groups=[AgeShare(age_group="20", share=0.45), AgeShare(age_group="30", share=0.25), AgeShare(age_group="40", share=0.15)],
        peak_consumption_hours=["17-21"],
        weekday_weekend_ratio=1.2,
        resident_visitor_ratio=0.6,
        area_income_level="high",
        population_trend="stable",
        elderly_ratio=0.207,
        brand_target_match_score=78.0,
        match_rationale="20대 여성 주 고객과 정확히 매치",
        narrative="서교동 커피 매장은 ...",
    )
    assert r.core_demographic.share == 0.42
```

Commit: `feat(B1): DemographicReport Pydantic 스키마 + AgentState 확장`

---

## Task 3: `demographic_depth_node` 에이전트 본체 (1 commit, subagent)

**Files:**
- Create: `backend/src/agents/nodes/demographic_depth.py`

**구조** (synthesis.py 캐시 패턴 + market_analyst.py LLM 패턴 모방):

```python
import asyncio, json
import redis.asyncio as aioredis
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.state import AgentState
from src.schemas.demographic import DemographicReport, CoreDemographic, AgeShare, DemographicAnalysis
from src.agents.nodes.market_analyst import market_tool, db_client
from src.agents.llms import get_fast_llm
from src.config.settings import settings

_CACHE_TTL = 86400

async def demographic_depth_node(state: AgentState) -> dict:
    dong_code = _resolve_dong_code(state.get("target_district", "서교동"))  # 동명→코드
    brand_name = state.get("brand_name")
    industry_filter = state.get("industry_filter")  # CS100010 등

    cache_key = f"v2:demographic:{brand_name or 'nobrand'}:{dong_code}:{industry_filter or 'all'}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = await _redis.get(cache_key)
        if cached:
            await _redis.aclose()
            return {"analysis_results": {**state.get("analysis_results", {}), "demographic_report": json.loads(cached)}, "current_agent": "demographic_depth"}
    except Exception as e:
        print(f"[demographic] cache miss: {e}")
        if _redis:
            try: await _redis.aclose()
            except: pass
        _redis = None

    if db_client.engine is None:
        await db_client.connect()

    # 3 DB 병렬
    sales, resvis, context = await asyncio.gather(
        market_tool.get_demographic_sales_breakdown(dong_code, industry_filter),
        market_tool.get_realtime_resident_visitor(dong_code),
        market_tool.get_area_income_context(dong_code),
        return_exceptions=True,
    )
    def _safe(x, default): return x if not isinstance(x, Exception) else default
    sales = _safe(sales, {"error": "sales fail"})
    resvis = _safe(resvis, {"resident_rate": None, "visitor_rate": None})
    context = _safe(context, {"income_level": "unknown", "population_trend": "unknown", "elderly_ratio": None})

    # 매출 없으면 조기 종료 (mock narrative)
    if sales.get("error") or sales.get("monthly_sales", 0) == 0:
        default_report = _make_empty_report(dong_code, brand_name)
        return {"analysis_results": {**state.get("analysis_results", {}), "demographic_report": default_report}, "current_agent": "demographic_depth"}

    # 정량 계산
    core = _identify_core_demographic(sales)  # CoreDemographic
    top3 = _extract_top_3_age(sales)  # list[AgeShare]
    peak = _extract_peak_hours(sales)  # list[str] top 2
    wd_we = _calc_wd_we_ratio(sales)  # float

    # LLM 호출 (structured output)
    prompt = _build_prompt(sales, resvis, context, brand_name, core, top3, peak)
    try:
        llm = get_fast_llm().with_structured_output(DemographicAnalysis)
        analysis: DemographicAnalysis = await llm.ainvoke([
            SystemMessage(content="당신은 상권 소비자 분석 전문가입니다."),
            HumanMessage(content=prompt),
        ])
    except Exception as e:
        print(f"[demographic] LLM fail: {e}")
        analysis = DemographicAnalysis(
            narrative=f"{dong_code} 분석: 주 소비층 {core.age}대 {core.gender} ({core.share*100:.0f}%). 피크 시간 {', '.join(peak)}.",
            brand_target_match_score=None, match_rationale=None,
        )

    # 최종 DemographicReport 조립
    resident_visitor_ratio = None
    if resvis.get("resident_rate") and resvis.get("visitor_rate"):
        denom = resvis["resident_rate"] + resvis["visitor_rate"]
        if denom > 0: resident_visitor_ratio = resvis["visitor_rate"] / denom

    report = DemographicReport(
        core_demographic=core, top_3_age_groups=top3,
        peak_consumption_hours=peak, weekday_weekend_ratio=wd_we,
        resident_visitor_ratio=resident_visitor_ratio,
        area_income_level=context.get("income_level", "unknown"),
        population_trend=context.get("population_trend", "unknown"),
        elderly_ratio=context.get("elderly_ratio"),
        brand_target_match_score=analysis.brand_target_match_score if brand_name else None,
        match_rationale=analysis.match_rationale if brand_name else None,
        narrative=analysis.narrative,
    ).model_dump()

    # 캐시 저장
    if _redis is None:
        try: _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        except: pass
    if _redis is not None:
        try:
            await _redis.set(cache_key, json.dumps(report, ensure_ascii=False), ex=_CACHE_TTL)
        except: pass
        finally:
            try: await _redis.aclose()
            except: pass

    return {"analysis_results": {**state.get("analysis_results", {}), "demographic_report": report}, "current_agent": "demographic_depth"}
```

유틸 함수들:
```python
def _identify_core_demographic(sales: dict) -> CoreDemographic: ...
def _extract_top_3_age(sales: dict) -> list[AgeShare]: ...
def _extract_peak_hours(sales: dict) -> list[str]: ...
def _calc_wd_we_ratio(sales: dict) -> float: ...
def _build_prompt(...) -> str: ...
def _resolve_dong_code(name: str) -> str:
    # 기존 legal.py의 _DISTRICT_ZONE_MAP 활용 또는 tools.py _DONG_MAP 참조
    ...
def _make_empty_report(dong_code, brand_name) -> dict: ...
```

Unit test (mock된 market_tool + mock LLM):
- `test_demographic_depth_seogyo_coffee` — 서교동 빽다방 커피 시나리오 (실 DB, 실 LLM)
- `test_demographic_depth_no_brand` — `brand_name=None`이면 `match_score=None`
- `test_demographic_depth_no_sales_data` — 매출 데이터 없으면 기본 narrative 반환

Commit: `feat(B1): demographic_depth_node 구현 — 캐시/병렬DB/LLM 통합`

---

## Task 4: Graph + Synthesis + API 통합 (1 commit, 신중)

**Files:**
- Modify: `backend/src/agents/graph.py`
- Modify: `backend/src/agents/nodes/synthesis.py`
- Modify: `backend/src/main.py`

### graph.py
`parallel_analysis_node`의 asyncio.gather에 `demographic_depth_node(state)` 추가. 결과를 merge 시 `analysis_results` 병합 로직 확인.

### synthesis.py (⚠️ 가장 민감)

- `analysis_results.get("demographic_report")` 읽어서 프롬프트에 "주 소비층·피크 시간·타겟 매칭" 섹션 추가
- **절대 건드리지 않기**:
  - line 66 legal_risks 복원
  - line 173-174 legal_risks 보존 주석
  - `overall_legal_risk` 유지 로직
- 캐시 키는 v2 그대로 (demographic_report는 내부 참고용, 캐시에 포함할 필요 X — or include로 갈지 팀 결정). 초기에는 캐시에 포함 안 함 (캐시 invalidation 복잡화 방지).

### main.py
`SimulationOutput` 응답 스키마에 `demographic_report` 필드 추가 (Optional[dict]). 기존 필드 유지.

Test:
- `test_e2e_pipeline_with_demographic` — `/simulate` 호출하여 `demographic_report`가 응답에 포함되는지 확인
- `test_legal_risks_14_preserved` — synthesis 후에도 `legal_risks` 길이가 14인지 확인 (**regression guard**)

Commit: `feat(B1): parallel_analysis에 demographic_depth 통합 + synthesis/main.py 확장`

---

## Task 5: 통합 검증 (commit 안 함, QA)

1. RDS 연결 확인
2. `pytest backend/tests/test_demographic_depth.py -v` 전부 통과
3. FastAPI 로컬 기동 → `/simulate` 실 호출 → response에 `demographic_report` 섹션
4. 응답 시간 측정 (기존 50초 대비 +10초 이내 목표)
5. legal_risks 14개 보존 확인

## Acceptance Criteria (5개)

1. ✅ 4개 DB 테이블 모두 실데이터 조회 성공 (district_sales, seoul_realtime_hotspots, kosis_regional_income, elderly_ratio_region, resident_pop_monthly)
2. ✅ `/simulate` 응답에 `demographic_report` 섹션 정상 채워짐
3. ✅ `brand_name` 미지정 시 `brand_target_match_score=None`
4. ✅ LLM 실패 fallback 동작 (에러 시에도 narrative 기본값 반환)
5. ✅ synthesis 수정 후에도 기존 legal_risks 14개 항목 100% 보존

## 주의사항

1. **Memory:** AGENTS.md 규칙상 `backend/` 디렉토리는 B1(예진) 영역. 사용자(강민·C1)가 명시적으로 도움 요청하여 예외 진행.
2. **할루시네이션 금지:** 컬럼명은 DB 조사 결과(이 문서 앞부분)만 사용. 확실하지 않으면 실 DB 재조회.
3. **단위 검증:** `district_sales.monthly_sales`는 bigint 원 단위 확인됨. 비율 컬럼(`resident_rate`)은 double 0-100 % 단위 확인 필요.
4. **Redis 캐시 TTL:** 24시간. 디버깅 시 캐시 flush 필요 가능.
5. **Subagent 분할:** Task 1 → Task 2 → Task 3 → Task 4 순차. 각 Task 후 spec 리뷰 + 코드 품질 리뷰.
6. **인수인계:** 최종 PR은 예진 님에게 리뷰 요청. 시연 영상 첨부.
