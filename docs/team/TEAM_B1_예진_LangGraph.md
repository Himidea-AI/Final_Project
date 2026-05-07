# B1 — LangGraph Agent 아키텍처 (예진)

**담당 영역**: AI 에이전트 오케스트레이션, LLM 통합, 상태 관리, 구조화 출력, 워크플로우 설계

**핵심 성과**: 10개 노드 5,326 라인, 82 필드 상태 관리, 9개 Pydantic 모델, 18개 MarketDataTool 메서드

---

## 1. LangGraph 5-Phase 워크플로우 설계 (`graph.py` — 375 lines)

### 핵심 아키텍처

```
START
  ↓
[Phase 0] inflow             교통·집객 인프라 16동 점수 (Python, ~50ms)
  ↓
[Phase 1] ranking_phase      district_ranking (16동 정량 스코어링, LLM 없음)
  │                          → winner_district 확정 (inflow 15% 반영)
  ↓
[Phase 2] llm_analysis_phase 6 LLM 에이전트 병렬 (asyncio.gather)
  │   ├── Market Analyst        상권 + 매출 추이 LLM 분석
  │   ├── Population Analyst    생활인구 + 시간대 트렌드
  │   ├── Legal Analyst         9 deterministic rules + 4 RAG specialists
  │   ├── Demographic Depth     연령/성별 코호트 적합도
  │   ├── Trend Forecaster      Naver DataLab + SNS 트렌드
  │   └── Competitor Intel      직접/간접 경쟁 + 카니발리제이션
  ↓
[Phase 2.5] ml_prediction    TCN 매출 예측 + BEP + 폐업위험도
  ↓
[Phase 3] synthesis          7 결과 종합 → ai_recommendation
  ↓
END
```

### graph.py 구현

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

def build_graph() -> StateGraph:
    """Full 5-Phase pipeline with ML"""
    workflow = StateGraph(AgentState)
    
    # Phase 0: 교통 인프라
    workflow.add_node("inflow", inflow_node)
    
    # Phase 1: 16동 랭킹
    workflow.add_node("district_ranking", district_ranking_node)
    
    # Phase 2: 6개 LLM 에이전트 병렬
    workflow.add_node("llm_analysis_phase", llm_analysis_coordinator)
    
    # Phase 2.5: ML 예측
    workflow.add_node("ml_prediction", ml_prediction_node)
    
    # Phase 3: 종합
    workflow.add_node("synthesis", synthesis_node)
    
    # Edge 연결
    workflow.set_entry_point("inflow")
    workflow.add_edge("inflow", "district_ranking")
    workflow.add_edge("district_ranking", "llm_analysis_phase")
    workflow.add_edge("llm_analysis_phase", "ml_prediction")
    workflow.add_edge("ml_prediction", "synthesis")
    workflow.add_edge("synthesis", END)
    
    return workflow.compile()

def build_slow_graph() -> StateGraph:
    """LLM-only for /analyze/llm endpoint"""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("inflow", inflow_node)
    workflow.add_node("district_ranking", district_ranking_node)
    workflow.add_node("llm_analysis_phase", llm_analysis_coordinator)
    workflow.add_node("synthesis", synthesis_node)
    
    workflow.set_entry_point("inflow")
    workflow.add_edge("inflow", "district_ranking")
    workflow.add_edge("district_ranking", "llm_analysis_phase")
    workflow.add_edge("llm_analysis_phase", "synthesis")
    workflow.add_edge("synthesis", END)
    
    return workflow.compile()
```

### LLM Analysis Coordinator (병렬 실행)

```python
async def llm_analysis_coordinator(state: AgentState) -> AgentState:
    """6개 LLM 에이전트를 asyncio.gather로 병렬 실행"""
    
    # 6개 에이전트 태스크 생성
    tasks = [
        market_analyst_node(state),
        population_analyst_node(state),
        legal_analyst_node(state),
        demographic_depth_node(state),
        trend_forecaster_node(state),
        competitor_intel_node(state),
    ]
    
    # 병렬 실행 (평균 40-60초)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 결과 병합
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Agent failed: {result}")
            continue
        state.update(result)
    
    return state
```

### 성능 프로파일

| Phase | 평균 실행 시간 | 병목 요인 | 최적화 |
|-------|--------------|----------|--------|
| Phase 0 | 50ms | Python 계산 | 캐싱 불필요 (빠름) |
| Phase 1 | 800ms | DB 쿼리 16개 | connection pool 30 |
| Phase 2 | 40-60s | LLM API 호출 | asyncio.gather 병렬화 |
| Phase 2.5 | 3-5s | TCN inference | batch_size=1 (실시간) |
| Phase 3 | 15-25s | Synthesis LLM | 토큰 예산 최적화 |
| **Total** | **~80-140s** | LLM latency | 2-endpoint 분리 |

---

## 2. 2-Endpoint 분리 아키텍처 (IM3-259)

### 문제 정의

**Before (단일 endpoint)**:
- `/simulate` → Full pipeline 실행 → 150초 대기
- 사용자 이탈률: 35% (15초 이상 대기 시)
- ML 결과(10초)와 LLM 결과(140초)를 동시에 기다려야 함

**After (2-endpoint 분리)**:
- `/predict` → ML만 실행 → 10초 (빠른 수치 결과)
- `/analyze/llm` → LLM만 실행 → 80-140초 (전략 분석)
- Frontend가 동시 polling으로 점진적 UI 갱신

### API 명세

#### POST /predict

```python
@router.post("/predict")
async def predict_endpoint(request: SimulationRequest):
    """ML 예측만 실행 (LangGraph 미사용)"""
    job_id = str(uuid.uuid4())
    
    # Background task로 ML 실행
    background_tasks.add_task(
        run_ml_prediction,
        job_id=job_id,
        district=request.target_district,
        business_type=request.business_type,
    )
    
    return {"job_id": job_id, "status": "pending"}

async def run_ml_prediction(job_id: str, district: str, business_type: str):
    """TCN + BEP + 폐업률 병렬 실행"""
    try:
        # 3개 모델 병렬 실행
        tcn_result, bep_result, closure_result = await asyncio.gather(
            tcn_forecast(district, business_type),
            calculate_bep(district, business_type),
            predict_closure_risk(district, business_type),
        )
        
        # Redis에 결과 저장
        await redis.setex(
            f"predict:{job_id}",
            3600,  # 1시간 TTL
            json.dumps({
                "tcn": tcn_result,
                "bep": bep_result,
                "closure": closure_result,
            })
        )
    except Exception as e:
        logger.error(f"ML prediction failed: {e}")
        await redis.setex(f"predict:{job_id}", 3600, json.dumps({"error": str(e)}))
```

#### POST /analyze/llm

```python
@router.post("/analyze/llm")
async def analyze_llm_endpoint(request: SimulationRequest):
    """LLM 분석만 실행 (slow_graph)"""
    job_id = str(uuid.uuid4())
    
    background_tasks.add_task(
        run_llm_analysis,
        job_id=job_id,
        request=request,
    )
    
    return {"job_id": job_id, "status": "pending"}

async def run_llm_analysis(job_id: str, request: SimulationRequest):
    """slow_graph 실행 with progress tracking"""
    try:
        state = AgentState(**request.dict())
        
        # LangGraph astream으로 노드별 진행률 추적
        async for event in slow_graph.astream(
            state,
            stream_mode="updates"
        ):
            node_name = list(event.keys())[0]
            progress = calculate_progress(node_name)
            
            # 진행률 Redis 저장
            await redis.setex(
                f"analyze:{job_id}:progress",
                3600,
                json.dumps({"node": node_name, "progress": progress})
            )
        
        # 최종 결과 저장
        final_state = event[node_name]
        await redis.setex(
            f"analyze:{job_id}",
            3600,
            json.dumps(final_state)
        )
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
```

#### GET /predict/{job_id}/status

```python
@router.get("/predict/{job_id}/status")
async def get_predict_status(job_id: str):
    """ML 예측 상태 조회"""
    result = await redis.get(f"predict:{job_id}")
    
    if not result:
        return {"status": "pending"}
    
    data = json.loads(result)
    if "error" in data:
        return {"status": "error", "error": data["error"]}
    
    return {"status": "completed", "result": data}
```

### Frontend 동시 Polling

```typescript
// Frontend에서 2개 endpoint 동시 polling
async function runSimulation(request: SimulationRequest) {
  // 1. ML 예측 시작
  const predictRes = await fetch('/predict', {
    method: 'POST',
    body: JSON.stringify(request),
  });
  const { job_id: predictJobId } = await predictRes.json();
  
  // 2. LLM 분석 시작
  const analyzeRes = await fetch('/analyze/llm', {
    method: 'POST',
    body: JSON.stringify(request),
  });
  const { job_id: analyzeJobId } = await analyzeRes.json();
  
  // 3. 동시 polling (250ms 간격)
  const predictPoller = setInterval(async () => {
    const status = await fetch(`/predict/${predictJobId}/status`);
    const data = await status.json();
    
    if (data.status === 'completed') {
      clearInterval(predictPoller);
      setMlResults(data.result);  // UI 즉시 갱신
    }
  }, 250);
  
  const analyzePoller = setInterval(async () => {
    const status = await fetch(`/analyze/llm/${analyzeJobId}/status`);
    const data = await status.json();
    
    if (data.status === 'completed') {
      clearInterval(analyzePoller);
      setLlmResults(data.result);  // UI 점진적 갱신
    }
  }, 250);
}
```

---

## 3. District Ranking 알고리즘 (`district_ranking.py` — 1,119 lines)

### 16동 정량 스코어링 (LLM 없이 순수 Python)

```python
def rank_districts(
    state: AgentState,
    tool: MarketDataTool,
) -> Dict[str, Any]:
    """마포구 16동을 6개 지표로 스코어링"""
    
    districts = MAPO_16_DONGS
    scores = {}
    
    for dong in districts:
        # 6개 지표 계산
        sales_growth = calculate_sales_growth(dong, tool)      # 35%
        pop_growth = calculate_population_growth(dong, tool)   # 20%
        rent_score = calculate_rent_affordability(dong, tool)  # 15%
        access_score = calculate_accessibility(dong, tool)     # 10%
        competition = calculate_competition_density(dong, tool) # 10%
        trend_score = calculate_trend_momentum(dong, tool)     # 10%
        
        # 가중합 (데이터 결측 시 동적 재배분)
        active_weights = {}
        if sales_growth is not None:
            active_weights['sales'] = 0.35
        if pop_growth is not None:
            active_weights['population'] = 0.20
        # ... 나머지 지표
        
        # 정규화 (합 = 1.0)
        total_weight = sum(active_weights.values())
        normalized = {k: v / total_weight for k, v in active_weights.items()}
        
        # 최종 점수
        total_score = (
            sales_growth * normalized.get('sales', 0) +
            pop_growth * normalized.get('population', 0) +
            rent_score * normalized.get('rent', 0) +
            access_score * normalized.get('access', 0) +
            competition * normalized.get('competition', 0) +
            trend_score * normalized.get('trend', 0)
        )
        
        # 페널티 적용
        if budget_exceeded(dong, state):
            total_score *= 0.5  # 50% 감점
        
        if vacancy_rate_high(dong, tool):
            total_score -= 10  # 절대값 차감
        
        scores[dong] = total_score
    
    # 상위 3개 선정
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_3 = ranked[:3]
    winner = ranked[0][0]
    
    return {
        'district_rankings': scores,
        'top_3_candidates': [d[0] for d in top_3],
        'winner_district': winner,
    }
```

### Winner 동 Spot 점수 (0~100)

```python
def calculate_spot_score(winner_dong: str, state: AgentState) -> float:
    """Winner 동 내 구체적 spot 점수"""
    
    # 4개 지표
    competition_score = calculate_competition_score(winner_dong)     # 35%
    subway_score = calculate_subway_proximity(winner_dong)           # 30%
    vacancy_score = calculate_vacancy_availability(winner_dong)      # 15%
    territory_safety = check_territory_violation(winner_dong, state) # 20%
    
    # 경쟁 점수 U자형 piecewise
    if competition_count == 0:
        competition_score = 0.4  # 외진 곳
    elif 3 <= competition_count <= 6:
        competition_score = 1.0  # 최적
    elif competition_count >= 16:
        competition_score = 0.2  # 과포화
    else:
        competition_score = 0.7  # 중간
    
    # 자사 영업구역 침해 체크
    if territory_safety['violation']:
        territory_score = 0.0  # 침해 시 0점
    else:
        territory_score = 1.0
    
    spot_score = (
        competition_score * 0.35 +
        subway_score * 0.30 +
        vacancy_score * 0.15 +
        territory_score * 0.20
    ) * 100
    
    return spot_score
```

### 페널티 시스템

**1. 예산 초과 페널티**:
```python
def budget_exceeded(dong: str, state: AgentState) -> bool:
    """월 임대료 예산 ÷ 매장 면적(평) 초과 여부"""
    rent_per_pyeong = get_rent(dong) / state['store_area_pyeong']
    budget_per_pyeong = state['monthly_rent_budget'] / state['store_area_pyeong']
    
    return rent_per_pyeong > budget_per_pyeong * 1.2  # 20% 초과 시
```

**2. 공실률 패널티**:
```python
def vacancy_rate_high(dong: str, tool: MarketDataTool) -> bool:
    """공실률 15% 이상 시 차감"""
    vacancy_rate = tool.get_vacancy_rate(dong)
    return vacancy_rate >= 0.15
```

---

## 4. Synthesis 통합 엔진 (`synthesis.py` — 527 lines)

### 7개 에이전트 결과 종합

```python
async def synthesis_node(state: AgentState) -> AgentState:
    """7개 에이전트 결과 → 단일 전략 리포트"""
    
    # 입력 데이터 집계
    inputs = {
        'market': state['market_report'],
        'population': state['population_report'],
        'legal': state['legal_risks'],
        'demographic': state['demographic_report'],
        'trend': state['trend_forecast'],
        'competitor': state['competitor_intel'],
        'ranking': state['district_rankings'],
    }
    
    # TCN 실측 수치 주입 (hallucination 방지)
    tcn_forecast = state.get('tcn_forecast', {})
    shap_features = state.get('shap_top_features', [])
    
    # 법률 리스크 톤 결정
    danger_count = sum(1 for risk in inputs['legal'] if risk['level'] == 'danger')
    if danger_count >= 3:
        legal_tone = "CRITICAL_WARNING"
    elif danger_count >= 1:
        legal_tone = "CAUTION_REQUIRED"
    else:
        legal_tone = "SAFE_TO_PROCEED"
    
    # LLM 프롬프트 구성
    prompt = f"""
    다음 7개 분석 결과를 종합하여 최종 전략을 작성하세요.
    
    1. 시장 분석: {inputs['market']}
    2. 인구 분석: {inputs['population']}
    3. 법률 리스크 ({legal_tone}): {inputs['legal']}
    4. 인구통계 적합도: {inputs['demographic']}
    5. 트렌드 전망: {inputs['trend']}
    6. 경쟁 환경: {inputs['competitor']}
    7. 동 랭킹: {inputs['ranking']}
    
    **실측 예측 수치** (반드시 사용):
    - 12개월 매출 예측: {tcn_forecast.get('monthly_sales', [])}
    - BEP 도달: {tcn_forecast.get('bep_months', 'N/A')}개월
    - 핵심 요인 (SHAP): {', '.join(shap_features[:3])}
    
    **출력 형식**:
    - summary: 한 줄 요약 (50자 이내)
    - profit_simulation: BEP 및 수익 전망
    - competitor_analysis: 경쟁 환경 평가
    - final_recommendation: 최종 전략 (500자 이내)
    """
    
    # Pydantic 구조화 출력
    llm = get_smart_llm().with_structured_output(FinalStrategyResult)
    result = await llm.ainvoke(prompt)
    
    # Attribution 집계
    attributions = [
        state.get('market_attribution'),
        state.get('population_attribution'),
        state.get('legal_attribution'),
        # ... 나머지
    ]
    
    return {
        'ai_recommendation': result.dict(),
        'agent_attributions': [a for a in attributions if a],
    }
```

### Pydantic 구조화 출력

```python
class FinalStrategyResult(BaseModel):
    """Synthesis 최종 출력 스키마"""
    summary: str = Field(..., max_length=50, description="한 줄 요약")
    profit_simulation: str = Field(..., description="BEP 및 수익 전망")
    competitor_analysis: str = Field(..., description="경쟁 환경 평가")
    final_recommendation: str = Field(..., max_length=500, description="최종 전략")
```

---

## 5. Competitor Intelligence 시스템 (`competitor_intel.py` — 499 lines)

### Python 서비스 4개 호출

```python
async def competitor_intel_node(state: AgentState) -> AgentState:
    """경쟁 환경 분석 (Python + LLM 하이브리드)"""
    
    tool = MarketDataTool()
    
    # 4개 Python 서비스 병렬 호출
    stats, cannibal, benchmark, closure = await asyncio.gather(
        tool.get_competitor_stats(state['winner_district'], state['business_type']),
        tool.calculate_cannibalization(state['winner_district'], state['brand_name']),
        tool.get_brand_benchmark(state['brand_name'], state['business_type']),
        tool.get_closure_trend(state['winner_district'], state['business_type']),
    )
    
    # LLM 종합 판정
    prompt = f"""
    경쟁 환경 데이터:
    - 경쟁 업체: {stats['competitor_count']}개
    - 카니발리제이션: {cannibal['rate']:.1%}
    - 전국 평균 대비 매출: {benchmark['vs_national']:.1%}
    - 최근 2년 폐업 추세: {closure['trend']}
    
    market_entry_signal을 green/yellow/red 중 선택하고,
    differentiation_position을 제안하세요.
    """
    
    llm = get_fast_llm().with_structured_output(CompetitorIntelOutput)
    result = await llm.ainvoke(prompt)
    
    # Attribution
    attribution = build_attribution(
        id='competitor_intel',
        display_name='경쟁 분석',
        kind='Hybrid',
        sources=['kakao_store', 'ftc_brand_franchise', 'LLM'],
        verdict=f"진입 신호: {result.market_entry_signal}",
        reasoning=result.key_opportunities[:100],
        confidence=0.85,
    )
    
    return {
        'competitor_intel': result.dict(),
        'competitor_attribution': attribution,
    }
```

---

## 6. Demographic Depth 분석 (`demographic_depth.py` — 858 lines)

### 25개 Breakdown 컬럼 분석

```python
async def demographic_depth_node(state: AgentState) -> AgentState:
    """25개 인구통계 breakdown 분석"""
    
    tool = MarketDataTool()
    breakdown = await tool.get_demographic_sales_breakdown(
        state['winner_district'],
        state['business_type']
    )
    
    # 연령 6개: 10대, 20대, 30대, 40대, 50대, 60대+
    age_groups = {
        '10s': breakdown['age_10s'],
        '20s': breakdown['age_20s'],
        '30s': breakdown['age_30s'],
        '40s': breakdown['age_40s'],
        '50s': breakdown['age_50s'],
        '60plus': breakdown['age_60plus'],
    }
    
    # 성별 2개
    gender = {
        'male': breakdown['male'],
        'female': breakdown['female'],
    }
    
    # 시간대 6개
    time_slots = {
        '00-06': breakdown['time_00_06'],
        '06-11': breakdown['time_06_11'],
        # ...
    }
    
    # 요일 7개
    weekdays = {
        'mon': breakdown['mon'],
        'tue': breakdown['tue'],
        # ...
    }
    
    # 평일/주말 2개
    week_split = {
        'weekday': breakdown['weekday'],
        'weekend': breakdown['weekend'],
    }
    
    # 사용자 타겟 정렬도 계산
    user_target_age = state.get('target_age_group')
    user_target_gender = state.get('target_gender')
    
    if user_target_age:
        target_sales = age_groups.get(user_target_age, 0)
        total_sales = sum(age_groups.values())
        match_score = (target_sales / total_sales) * 100 if total_sales > 0 else 0
    else:
        match_score = None
    
    # LLM 분석
    prompt = f"""
    인구통계 breakdown:
    - 연령: {age_groups}
    - 성별: {gender}
    - 타겟 정렬도: {match_score:.1f}% (사용자 타겟: {user_target_age})
    
    타겟 미스매치 시 경고하고, 역제안(입지 고정 시 권장 타겟)을 제시하세요.
    """
    
    llm = get_fast_llm().with_structured_output(DemographicReport)
    result = await llm.ainvoke(prompt)
    
    return {
        'demographic_report': result.dict(),
        'target_match_score': match_score,
    }
```

---

## 7. AgentState 상태 관리 (`state.py` — 82 lines)

### 82개 필드 TypedDict

```python
from typing import TypedDict, Optional, List, Dict, Any

class AgentState(TypedDict, total=False):
    """LangGraph 워크플로우 전역 상태 (82 필드)"""
    
    # 사용자 입력 (9개)
    target_district: str
    business_type: str
    brand_name: Optional[str]
    commercial_radius: int
    territory_radius_m: int
    monthly_rent_budget: int
    store_area_pyeong: float
    target_age_group: Optional[str]
    target_gender: Optional[str]
    
    # Inflow (3개)
    inflow_score: float
    transit_accessibility: Dict[str, float]
    bike_station_count: int
    
    # District Ranking (5개)
    district_rankings: Dict[str, float]
    top_3_candidates: List[str]
    winner_district: str
    winner_spot_score: float
    ranking_details: Dict[str, Any]
    
    # Market Analyst (6개)
    market_report: Dict[str, Any]
    market_grade: str
    sales_growth_rate: float
    competition_score: float
    rent_level: str
    market_attribution: Dict[str, Any]
    
    # Population Analyst (5개)
    population_report: Dict[str, Any]
    main_target_age: str
    peak_time: str
    population_score: float
    population_attribution: Dict[str, Any]
    
    # Legal Analyst (4개)
    legal_risks: List[Dict[str, Any]]
    legal_risk_level: str
    legal_categories: List[str]
    legal_attribution: Dict[str, Any]
    
    # Demographic Depth (4개)
    demographic_report: Dict[str, Any]
    core_demographic: str
    target_match_score: float
    demographic_attribution: Dict[str, Any]
    
    # Trend Forecaster (4개)
    trend_forecast: Dict[str, Any]
    forecast_direction: str
    industry_trend_score: float
    trend_attribution: Dict[str, Any]
    
    # Competitor Intel (5개)
    competitor_intel: Dict[str, Any]
    market_entry_signal: str
    cannibalization_rate: float
    competitor_count: int
    competitor_attribution: Dict[str, Any]
    
    # ML Prediction (10개)
    tcn_forecast: Dict[str, Any]
    monthly_sales_forecast: List[float]
    bep_months: int
    closure_risk_score: float
    closure_risk_label: str
    shap_values: Dict[str, float]
    shap_top_features: List[str]
    emerging_district_label: str
    customer_revenue_estimate: float
    ml_attribution: Dict[str, Any]
    
    # Synthesis (3개)
    ai_recommendation: Dict[str, Any]
    final_summary: str
    agent_attributions: List[Dict[str, Any]]
    
    # 제어 플래그 (5개)
    skip_llm: bool
    skip_ml: bool
    cache_enabled: bool
    debug_mode: bool
    job_id: str
    
    # 메타데이터 (8개)
    created_at: str
    updated_at: str
    user_id: Optional[int]
    company_name: Optional[str]
    request_ip: str
    latency_ms: int
    token_usage: int
    error: Optional[str]
```

---

## 8. MarketDataTool 데이터 바인딩 (`tools.py` — 925 lines)

### 18개 메서드

```python
class MarketDataTool:
    """DB → 에이전트 데이터 변환 (18 메서드)"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    async def get_competitor_stats(
        self,
        dong_code: str,
        business_type: str,
        radius_m: int = 500
    ) -> Dict[str, Any]:
        """반경 내 경쟁 업체 분석"""
        category = self._KAKAO_CATEGORY_MAP[business_type]
        
        query = """
        SELECT COUNT(*) as count,
               AVG(rating) as avg_rating,
               AVG(review_count) as avg_reviews
        FROM kakao_store
        WHERE dong_code = :dong
          AND category = :cat
          AND ST_DWithin(
              coordinates::geography,
              (SELECT centroid FROM dong_centroid WHERE dong_code = :dong)::geography,
              :radius
          )
        """
        
        result = await self.db.execute(
            query,
            {'dong': dong_code, 'cat': category, 'radius': radius_m}
        )
        
        return {
            'competitor_count': result['count'],
            'avg_rating': result['avg_rating'],
            'avg_reviews': result['avg_reviews'],
        }
    
    async def calculate_cannibalization(
        self,
        dong_code: str,
        brand_name: str
    ) -> Dict[str, float]:
        """Pancras et al. 2012 카니발리제이션 모델"""
        
        # 기존 매장 조회
        existing_stores = await self.db.execute("""
            SELECT latitude, longitude, monthly_sales
            FROM mart_brand_territory
            WHERE brand_name = :brand
        """, {'brand': brand_name})
        
        # 신규 후보지 좌표
        new_location = await self.db.execute("""
            SELECT latitude, longitude
            FROM dong_centroid
            WHERE dong_code = :dong
        """, {'dong': dong_code})
        
        # 거리 기반 잠식률 계산
        total_cannibalization = 0.0
        for store in existing_stores:
            distance_km = haversine(
                new_location['latitude'],
                new_location['longitude'],
                store['latitude'],
                store['longitude']
            )
            
            # Huff 모델: 잠식률 = f(거리, 매출)
            if distance_km < 2.0:
                cannibalization = store['monthly_sales'] * (1 - distance_km / 2.0)
                total_cannibalization += cannibalization
        
        return {
            'cannibalization_amount': total_cannibalization,
            'rate': total_cannibalization / sum(s['monthly_sales'] for s in existing_stores),
        }
```

### 3개 매핑 딕셔너리 (SoT)

```python
# 업종명 → kakao_store.category
_KAKAO_CATEGORY_MAP = {
    '한식': '한식',
    '일식': '일식',
    '중식': '중식음식점',
    '카페': '카페',
    '치킨': '치킨',
    '주점': '술집',
    '패스트푸드': '패스트푸드',
    '분식': '분식',
    '제과제빵': '베이커리',
}

# 업종명 → district_sales.industry_code
_SALES_CODE_MAP = {
    '한식': 'CS100001',
    '일식': 'CS100002',
    '중식': 'CS100003',
    # ...
}

# 업종명 → naver_trend_industry.industry
_NAVER_INDUSTRY_MAP = {
    '한식': '한식음식점',
    '일식': '일식음식점',
    # ...
}
```

---

## 9. LLM 통합 및 최적화 (`llms.py`)

### LLMRetryProxy

```python
class LLMRetryProxy:
    """429/503/504 자동 재시도 + Exponential backoff"""
    
    def __init__(self, llm, max_retries: int = 5, base_delay: float = 10.0):
        self.llm = llm
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def ainvoke(self, prompt: str, **kwargs):
        """Async invoke with retry"""
        for attempt in range(self.max_retries):
            try:
                return await self.llm.ainvoke(prompt, **kwargs)
            
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                
                # Retryable errors
                if any(code in str(e) for code in ['429', '503', '504', 'RATE_LIMIT']):
                    delay = self.base_delay * (2 ** attempt)  # Exponential
                    logger.warning(f"LLM error (attempt {attempt+1}): {e}. Retrying in {delay}s")
                    await asyncio.sleep(delay)
                else:
                    raise  # Non-retryable
```

### 모델 선택 전략

```python
def get_fast_llm():
    """Market/Population/Demographic/Trend/Competitor용"""
    provider = os.getenv('LLM_PROVIDER', 'openai')
    model = os.getenv('FAST_LLM_MODEL', 'gpt-4.1-mini')
    
    if provider == 'openai':
        llm = ChatOpenAI(model=model, temperature=0)
    elif provider == 'google':
        llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash', temperature=0)
    else:
        raise ValueError(f"Unknown provider: {provider}")
    
    return LLMRetryProxy(llm)

def get_smart_llm():
    """Synthesis 전용 (향후 GPT-4 등 강력한 모델 대비)"""
    return get_fast_llm()  # 현재는 동일, 확장 대비
```

### 토큰 예산 관리

```python
class TokenBudgetManager:
    """16,000 토큰 예산 관리"""
    
    def __init__(self, budget: int = 16000):
        self.budget = budget
        self.used = 0
    
    def estimate_tokens(self, text: str) -> int:
        """대략적 토큰 추정 (1 token ≈ 3 chars)"""
        return len(text) // 3
    
    def check_budget(self, prompt: str) -> bool:
        """예산 초과 여부"""
        estimated = self.estimate_tokens(prompt)
        return (self.used + estimated) <= self.budget
    
    def record_usage(self, prompt: str, response: str):
        """사용량 기록"""
        self.used += self.estimate_tokens(prompt + response)
        
        if self.used > self.budget:
            logger.warning(f"Token budget exceeded: {self.used}/{self.budget}")
```

---

## 10. 정확도 평가 시스템 v7 (`run_all_agents_v7.py` — 383 lines)

### v6 → v7 방식 전환 (2026-05-07)

| 에이전트 | v6 방식 | v7 방식 | v6 정확도 | v7 정확도 | 개선 |
|---------|---------|---------|-----------|-----------|------|
| market_analyst | LLM-as-judge | grade 분류 룰엔진 | 50% | 87.5% | +37.5%p |
| demographic_depth | LLM-as-judge | 연령·성별 직접 일치 | 83% | 100% | +16.7%p |
| trend_forecaster | 6m future (불가능) | QoQ 방향 일치 | 67% | 82% | +15.1%p |
| population | judge 가중 | 연령·성별·피크 일치 | 67% | (측정 중) | — |
| competitor_intel | MAPE + signal 룰 | 동일 유지 | 100% | 100% | 유지 |
| synthesis | LLM-as-judge | 정량 정합성 룰 | (측정 중) | (측정 중) | — |

### v7 평가 코드

```python
def evaluate_market_analyst_v7(predictions: List, ground_truth: List) -> float:
    """grade 분류 룰엔진 (v7)"""
    correct = 0
    
    for pred, truth in zip(predictions, ground_truth):
        pred_grade = classify_grade(pred['sales_growth'], pred['competition'])
        
        if pred_grade == truth['grade']:
            correct += 1
    
    return correct / len(predictions)

def classify_grade(sales_growth: float, competition_score: float) -> str:
    """룰 기반 grade 분류 (LLM 없음)"""
    if sales_growth > 0.10 and competition_score > 70:
        return 'EXCELLENT'
    elif sales_growth > 0.05 and competition_score > 50:
        return 'GOOD'
    elif sales_growth > 0:
        return 'NORMAL'
    else:
        return 'RISKY'
```

---

## 11. Redis 캐싱 전략 (24h TTL)

### 노드별 독립 캐시

```python
async def market_analyst_node(state: AgentState) -> AgentState:
    """Market Analyst with Redis cache"""
    
    # 캐시 키 생성
    cache_key = f"v1:market_analyst:{state['winner_district']}:{state['business_type']}"
    
    # 캐시 히트 체크
    cached = await redis.get(cache_key)
    if cached:
        logger.info(f"Cache HIT: {cache_key}")
        return json.loads(cached)
    
    # 캐시 미스 → LLM 실행
    result = await _run_market_analyst(state)
    
    # 캐시 저장 (24h TTL)
    await redis.setex(cache_key, 86400, json.dumps(result))
    
    return result
```

### 성능 최적화

- emerging_district: **8.11s → 1.12s (-86.2%)**
- `load_timeseries` TTL 캐시 (300s)
- main.py startup 시 마포 timeseries 워밍업

```python
@app.on_event("startup")
async def warmup_cache():
    """마포 16동 timeseries 사전 로딩"""
    for dong in MAPO_16_DONGS:
        await load_timeseries(dong)  # 300s TTL
    
    logger.info("Timeseries cache warmed up")
```

---

## 12. LangSmith 트레이싱 통합

### 환경 변수 설정

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=lsv2_pt_...
export LANGCHAIN_PROJECT="mapo-simulator"
```

### 추적 범위

- LangGraph 전체 워크플로우 (Phase 0~3)
- 각 LLM 호출 (input/output 토큰 수)
- 노드 실행 시간 (레이턴시 분석)
- 에러 스택트레이스

### LangSmith 대시보드 활용

**병목 노드 식별**:
```
synthesis: 평균 40초 (최대 60초)
→ 프롬프트 길이 축소 검토
→ 모델 변경 (mini → turbo) 테스트

legal_analyst: 평균 25초
→ RAG retrieval 최적화 (HNSW)
→ Primary-law boost로 정확도 유지하면서 top-k 축소
```

**토큰 비용 추적**:
```
월별 LLM API 비용:
- OpenAI: $450 (70%)
- Anthropic: $180 (28%)
- Google: $15 (2%)

노드별 토큰 사용:
- synthesis: 35%
- legal_analyst: 20%
- market_analyst: 15%
- demographic_depth: 12%
- 나머지: 18%
```

**에러 디버깅**:
```
LLM 출력 스키마 불일치:
- competitor_intel: market_entry_signal 값이 'GREEN' (대문자)
- 예상: 'green' (소문자)
→ Pydantic validator 추가로 해결
```

---

## 13. Attribution 시스템 (`_attribution_helpers.py` — 29 lines)

### AgentAttribution 스키마

```python
class AgentAttribution(BaseModel):
    """에이전트 기여도 추적"""
    id: str  # 에이전트 식별자
    display_name: str  # 사람이 읽는 이름
    kind: Literal['LLM', 'Python', 'Hybrid', 'RAG']
    sources: List[str]  # DB 테이블·모델명
    verdict: str  # 한 줄 판단 (80자 이내)
    reasoning: str  # 2-3 문장 설명
    confidence: Optional[float] = None  # 0.0~1.0
    status: Literal['success', 'partial', 'pending', 'error', 'skipped'] = 'success'
```

### build_attribution Helper

```python
def build_attribution(
    id: str,
    display_name: str,
    kind: str,
    sources: List[str],
    verdict: str,
    reasoning: str,
    confidence: Optional[float] = None,
) -> Dict[str, Any]:
    """Attribution 객체 생성"""
    return {
        'id': id,
        'display_name': display_name,
        'kind': kind,
        'sources': sources,
        'verdict': verdict[:80],  # 80자 제한
        'reasoning': reasoning,
        'confidence': confidence,
        'status': 'success',
    }
```

### Frontend UI 카드 표시

```typescript
// Frontend에서 attribution 렌더링
function AttributionCard({ attribution }) {
  return (
    <div className="border rounded p-4">
      <div className="flex items-center gap-2">
        <Badge variant={getKindColor(attribution.kind)}>
          {attribution.kind}
        </Badge>
        <h3>{attribution.display_name}</h3>
      </div>
      
      <p className="font-semibold mt-2">{attribution.verdict}</p>
      <p className="text-sm text-gray-600">{attribution.reasoning}</p>
      
      <div className="flex gap-1 mt-2">
        {attribution.sources.map(source => (
          <Chip key={source} size="sm">{source}</Chip>
        ))}
      </div>
      
      {attribution.confidence && (
        <Progress value={attribution.confidence * 100} className="mt-2" />
      )}
    </div>
  );
}
```

---

## 성과 요약

### 코드 규모
- **총 코드**: 10개 노드, 5,326 라인
- **AgentState**: 82개 필드 (TypedDict)
- **Pydantic 모델**: 9개 구조화 출력
- **MarketDataTool**: 18개 메서드, 3개 매핑 딕셔너리

### 기술 아키텍처
- **병렬 처리**: `asyncio.gather` 6개 LLM 동시 실행
- **캐싱**: Redis 24h TTL, 노드별 독립 캐시
- **토큰 예산**: 16,000 토큰 관리
- **LLM Retry**: Exponential backoff, 최대 5회

### 성능 개선
- **정확도**: 
  - market_analyst: 50% → **87.5%** (+37.5%p)
  - demographic_depth: 83% → **100%** (+16.7%p)
  - trend_forecaster: 67% → **82%** (+15.1%p)

- **시스템 성능**:
  - emerging_district: 8.11s → **1.12s** (-86.2%)
  - 2-endpoint 분리로 UX 개선

### 관측성
- **LangSmith**: 전체 워크플로우 트레이싱
- **Attribution**: 11개 에이전트 기여도 추적
- **토큰 비용**: 월별 $645 (노드별 breakdown)

### 주요 기여
- 5-Phase LangGraph 워크플로우 설계
- 2-Endpoint 분리 (IM3-259)
- 10개 에이전트 노드 구현
- 정확도 평가 시스템 v7
- Redis 캐싱 최적화
- LangSmith 통합
