import asyncio
import json
import redis.asyncio as aioredis
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.state import AgentState
from src.schemas.structured_output import FinalStrategyResult
from src.agents.llms import get_smart_llm
from src.agents.nodes._attribution_helpers import build_attribution
from src.config.settings import settings

_CACHE_TTL = 86400  # 24시간


# 에이전트 결과 수집 순서 (id, analysis_results 내 result blob 키 또는 state 키)
_AGENT_KEYS_ORDERED: list[tuple[str, str]] = [
    ("market_analyst", "market_analyst_result"),
    ("population_analyst", "population_analyst_result"),
    ("legal", "legal_result"),
    ("district_ranking", "district_ranking_result"),
    ("inflow", "inflow_result"),
    ("demographic_depth", "demographic_depth_result"),
    ("trend_forecaster", "trend_forecaster_result"),
    ("competitor_intel", "competitor_intel_result"),
]


def _collect_upstream_attributions(state: dict, analysis_results: dict) -> list[dict]:
    """다른 에이전트 결과에서 agent_attribution 수집.

    각 에이전트가 analysis_results[<agent>_result]["agent_attribution"]으로 넣음.
    competitor_intel은 state["competitor_intel_result"]에 직접 저장되는 경우가 있어 fallback 포함.
    """
    attributions: list[dict] = []
    for _agent_id, state_key in _AGENT_KEYS_ORDERED:
        # 1차: analysis_results 안의 result blob
        result_blob = analysis_results.get(state_key) if isinstance(analysis_results, dict) else None
        # 2차: state top-level (competitor_intel_result 같은 경우)
        if not isinstance(result_blob, dict) or not result_blob.get("agent_attribution"):
            alt = state.get(state_key)
            if isinstance(alt, dict) and alt.get("agent_attribution"):
                result_blob = alt
        attr = result_blob.get("agent_attribution") if isinstance(result_blob, dict) else None
        if attr:
            attributions.append(attr)
    return attributions


async def synthesis_node(state: AgentState) -> dict:
    """
    최종 합성 에이전트 (Synthesis Agent):
    - [데이터 보존] legal_node가 생성한 14개 법률 리스크 데이터를 절대 훼손하지 않고 그대로 유지합니다.
    - 상권 분석, 유동인구 분석, 법률 검토 결과를 종합하여 최종 창업 전략 리포트를 생성합니다.
    - FinalStrategyResult 스키마에 맞춰 정형화된 JSON 데이터를 생성합니다.
    """
    print("--- [SYNTHESIS] 최종 전략 합성 및 데이터 검증 시작 ---")

    brand_name = state.get("brand_name", "미지정 브랜드")
    business_type = state.get("business_type", "카페")
    target_district = state.get("target_district", "마포구")
    target_price_range = state.get("target_price_range", "")
    operating_hours = state.get("operating_hours", [])
    initial_capital = state.get("initial_capital", 0)
    monthly_rent_budget = state.get("monthly_rent_budget", 0)
    store_area = state.get("store_area", 15.0)

    # Redis 캐시 조회 (사용자 조건이 달라지면 다른 캐시 사용)
    # v7: SHAP 주입 + bep_months 스키마 추가 — 이전 v6 캐시 무효화
    _winner_for_cache = state.get("winner_district", target_district)
    _raw_td = state.get("target_districts") or [target_district]
    _td_key = ",".join(sorted(set(d for d in _raw_td if d)))
    cache_key = f"v7:synthesis:{brand_name}:{_winner_for_cache}:{_td_key}:{business_type}:{monthly_rent_budget}:{store_area}:{state.get('population_weight', True)}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = None if settings.debug else await _redis.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            print(f"[synthesis] 캐시 히트: {cache_key}")
            analysis = dict(state.get("analysis_results", {}))
            analysis["final_report"] = cached_data["final_report"]
            analysis["market_summary"] = cached_data["market_summary"]
            # [#3] 캐시 히트 시 legal_risks 복원 (캐시에 저장된 값 우선, 없으면 state에서 유지)
            if "legal_risks" in cached_data:
                analysis["legal_risks"] = cached_data["legal_risks"]
            # ranking 결과는 캐시되지 않음 — Phase 1 ranking_phase가 state top-level에 둔 값을 analysis_results로 승격.
            # 누락 시 main.py 응답의 district_rankings/winner_district/top_3_candidates 가 비어 프론트에서
            # "입지 랭킹 데이터가 없습니다" 가 표시되던 회귀를 막는다.
            _state_scouting = state.get("scouting_results") or []
            if _state_scouting or not analysis.get("district_rankings"):
                analysis["district_rankings"] = _state_scouting or analysis.get("district_rankings", [])
            _state_winner = state.get("winner_district")
            if _state_winner or not analysis.get("winner_district"):
                analysis["winner_district"] = _state_winner or analysis.get("winner_district")
            _state_top3 = state.get("top_3_candidates") or []
            if _state_top3 or not analysis.get("top_3_candidates"):
                analysis["top_3_candidates"] = _state_top3 or analysis.get("top_3_candidates", [])
            await _redis.aclose()

            # 캐시 히트 시에도 agent_attributions 집계 — 다른 에이전트의 attribution은 state/analysis에서 수집
            cached_attributions: list[dict] = _collect_upstream_attributions(state, analysis)
            cached_overall = cached_data.get("overall_legal_risk", "caution")
            cached_summary_text = ""
            try:
                cached_summary_text = (cached_data.get("final_report") or {}).get("summary", "")
            except Exception:
                cached_summary_text = ""
            cached_synth_attr = build_attribution(
                agent_id="synthesis",
                display_name="전략 종합",
                kind="LLM",
                sources=[f"{len(cached_attributions)}개 에이전트 결과"],
                verdict=f"종합 판단 · 법률 {cached_overall}",
                reasoning=str(cached_summary_text) if cached_summary_text else "전략 종합 (캐시)",
                confidence=0.85,
            )
            cached_attributions.append(cached_synth_attr)
            analysis["agent_attributions"] = cached_attributions

            return {
                "analysis_results": analysis,
                "overall_legal_risk": cached_overall,
                "current_agent": "synthesis",
                "agent_attributions": cached_attributions,
            }
    except Exception as e:
        print(f"[synthesis] Redis 캐시 조회 실패 (무시하고 계속): {e}")
        if _redis is not None:  # [#1] 조회 실패 시 연결 누수 방지
            try:
                await _redis.aclose()
            except Exception:
                pass
        _redis = None

    # 1. 데이터 추출 (기존 에이전트들의 결과물)
    analysis_results = state.get("analysis_results", {})
    market_report = analysis_results.get("market_report", "상권 분석 정보 없음")
    population_report = analysis_results.get("population_report", "인구 분석 정보 없음")

    # [중요] 14개의 법률 리스크 데이터 (절대 보존)
    legal_risks = analysis_results.get("legal_risks", [])
    overall_legal_risk = state.get("overall_legal_risk", "Caution")

    # 랭킹 데이터 추출
    winner_district = state.get("winner_district", target_district)
    top_3_candidates = state.get("top_3_candidates", [])
    scouting_results = state.get("scouting_results", [])

    # 랭킹 요약 (상위 4개 동, 핵심 수치만)
    ranking_summary = ""
    if scouting_results:
        ranking_summary = " / ".join(f"{r['rank']}위:{r['district']}({r['score']}점)" for r in scouting_results[:4])

    # 공실 정보 추출 (scouting_results에 vacancy_rate 포함 시)
    vacancy_summary = ""
    if scouting_results:
        winner_row = next((r for r in scouting_results if r["district"] == winner_district), None)
        if winner_row and winner_row.get("vacancy_rate", 0) > 0:
            vr = winner_row["vacancy_rate"]
            vacancy_label = "높음(상권 주의)" if vr >= 10 else ("보통" if vr >= 5 else "낮음(상권 활발)")
            vacancy_summary = (
                f"공실률({winner_district}): {vr}% — {vacancy_label} (2026년 4월 기준 네이버 부동산 상가 월세 매물)"
            )

    # 2. LLM 합성용 컨텍스트 구성
    # [토큰 절감] 중간 에이전트 리포트 전문 대신 핵심 수치만 전달
    # legal: summary 60자 이내로 축약 (level이 핵심)
    legal_summary_for_llm = "\n".join(
        [f"- {r.get('type', '미분류')}: {r.get('level', 'Normal')} — {r.get('summary', '')[:300]}" for r in legal_risks]
    )

    # trend_forecaster 결과 요약 (legal 뒤에 독립 배치, legal 블록 미접촉)
    trend_forecast_data = analysis_results.get("trend_forecast", {})
    trend_summary_for_llm = ""
    if trend_forecast_data and "forecast" in trend_forecast_data:
        f = trend_forecast_data["forecast"]
        industry_dir = trend_forecast_data.get("industry_trend", {}).get("direction", "unknown")
        change_label = (trend_forecast_data.get("change_ix") or {}).get("change_ix_label", "N/A")
        trend_summary_for_llm = (
            f"- 전망 점수: {f.get('score')}/100 ({f.get('direction')}, 신뢰도 {f.get('confidence')})\n"
            f"- 업종 검색량 방향: {industry_dir} | 상권 분류: {change_label}\n"
            f"- 요약: {(f.get('narrative') or '')[:250]}"
        )

    # 법률 DANGER 시 대안 지역 강조
    if overall_legal_risk == "danger":
        legal_override = (
            f"\n⚠️ 경고: 법률 리스크 DANGER. {target_district} 출점은 법률 위반 가능성이 높습니다. "
            f"final_recommendation에 대안 지역({', '.join(top_3_candidates[:2]) if top_3_candidates else '다른 지역'})을 최우선 제시하세요."
        )
    else:
        legal_override = ""

    # [NEW] demographic_depth 결과를 LLM 프롬프트에 추가 (legal 블록 뒤에 배치, legal 블록은 그대로 보존)
    demographic = analysis_results.get("demographic_report") or {}
    demographic_context = ""
    if demographic:
        dc = demographic
        core = dc.get("core_demographic") or {}
        demographic_context = "\n\n[타겟 소비자 분석]\n"
        demographic_context += f"- 주 소비층: {core.get('age', 'N/A')} {core.get('gender', 'N/A')}\n"
        peak_hours = dc.get("peak_consumption_hours") or []
        demographic_context += f"- 피크 시간대: {', '.join(peak_hours) if peak_hours else 'N/A'}\n"
        demographic_context += (
            f"- 소득 수준: {dc.get('area_income_level', 'N/A')} / 고령 비율: {dc.get('elderly_ratio', 'N/A')}%\n"
        )
        if dc.get("brand_target_match_score") is not None:
            demographic_context += f"- 브랜드 타겟 매칭: {dc['brand_target_match_score']}/100\n"
            demographic_context += f"  → {dc.get('match_rationale', '')}\n"

    # TCN ML 실측 수치 (Phase 2.5에서 계산된 값 — 없으면 빈 블록)
    _tcn = state.get("tcn_sim_result") or {}
    _tcn_rev = _tcn.get("revenue_forecast", {}).get("monthly_per_store")
    _tcn_bep = _tcn.get("bep", {}).get("bep_months")
    _tcn_closure = _tcn.get("closure_rate", {}).get("closure_rate")
    _tcn_risk = (_tcn.get("closure_risk") or {}).get("risk_score")
    if _tcn_rev or _tcn_bep or _tcn_closure or _tcn_risk:
        tcn_block = (
            "\n[ML 모델 실측 수치 — 추측 금지, 아래 수치를 profit_simulation에 그대로 사용]\n"
            + (f"- 월 예상 매출(monthly_revenue): {_tcn_rev:,.0f}원\n" if _tcn_rev else "")
            + (f"- 손익분기점(bep_months): {_tcn_bep}개월\n" if _tcn_bep else "")
            + (f"- 3년 폐업률: {_tcn_closure * 100:.1f}%\n" if _tcn_closure is not None else "")
            + (f"- 폐업 위험도: {_tcn_risk * 100:.1f}%\n" if _tcn_risk is not None else "")
        )
    else:
        tcn_block = ""

    # TCN 분기별 예측 (4분기 흐름 — 계절성 판단용)
    _quarterly_preds = (_tcn.get("revenue_forecast") or {}).get("quarterly_predictions") or []
    if _quarterly_preds:
        _q_lines = " / ".join(
            f"Q{p.get('quarter_offset', i + 1)}: {p.get('predicted_sales', 0):,.0f}원"
            for i, p in enumerate(_quarterly_preds[:4])
        )
        quarterly_block = f"\n[TCN 분기별 매출 예측 — 계절성·성장 방향 근거로 활용]\n{_q_lines}"
    else:
        quarterly_block = ""

    # SHAP 상위 3개 피처 (Phase 2.5에서 계산 — final_recommendation 근거로 활용)
    _shap = state.get("shap_result") or {}
    _shap_features = (_shap.get("feature_importance") or [])[:3]
    if _shap_features:
        _shap_lines = "\n".join(
            f"  {i + 1}위. {f['feature_ko']} "
            f"(기여도 {'+' if f['direction'] == 'positive' else '-'}{f['abs_shap']:.4f}, "
            f"{'매출 상승 요인' if f['direction'] == 'positive' else '매출 하락 요인'})"
            for i, f in enumerate(_shap_features)
        )
        shap_block = f"\n[SHAP 매출 예측 상위 기여 요인 — 추천 근거에 구체적으로 언급]\n{_shap_lines}"
    else:
        shap_block = ""

    # competitor_intel 요약 (경쟁/카니발/차별화) — legal_risks 와 독립적으로 병합
    competitor_intel = state.get("competitor_intel_result", {}) or {}
    if competitor_intel and "error" not in competitor_intel:
        ci_signal = competitor_intel.get("market_entry_signal", "N/A")
        ci_narrative = (competitor_intel.get("narrative") or "")[:220].replace("\n", " ")
        ci_cannibal = competitor_intel.get("cannibalization", {}).get("estimated_revenue_impact_pct", 0)
        ci_saturation = competitor_intel.get("competition_500m", {}).get("saturation_level", "N/A")
        competitor_block = (
            f"\n경쟁인텔({ci_signal}): 500m 포화={ci_saturation}, 카니발={ci_cannibal * 100:.1f}%. {ci_narrative}"
        )
    else:
        competitor_block = ""

    # Phase 2 (llm_analysis_phase)에서 이미 winner 동 기준으로 분석이 실행됐음
    # target_district == winner_district (graph.py Phase 2에서 교체)
    prompt = (
        "[AGENT: synthesis] 최종 전략 합성 에이전트 — LangSmith 식별용 라벨.\n\n"
        "프랜차이즈 창업 전략 컨설턴트로서 아래 데이터를 종합해 최종 리포트를 작성하세요.\n\n"
        f"브랜드:{brand_name}({business_type}) | 추천입지:{winner_district} | 법률리스크:{overall_legal_risk}\n"
        f"입지랭킹: {ranking_summary}\n"
        f"상권({winner_district}):\n{market_report[:2500]}\n"
        f"인구({winner_district}):\n{population_report[:2500]}\n"
        + (f"{vacancy_summary}\n" if vacancy_summary else "")
        + (f"향후 12개월 시장 전망:\n{trend_summary_for_llm}\n" if trend_summary_for_llm else "")
        + (f"{tcn_block}\n" if tcn_block else "")
        + (f"{quarterly_block}\n" if quarterly_block else "")
        + (f"{shap_block}\n" if shap_block else "")
        + (f"{competitor_block}\n" if competitor_block else "")
        + f"법률(14개):\n{legal_summary_for_llm}\n"
        f"{legal_override}"
        f"{demographic_context}\n"
        f"창업조건: 객단가={target_price_range or '미지정'} | 시간대={','.join(operating_hours) or '미지정'} | "
        f"자본금={initial_capital:,}원 | 임대예산={monthly_rent_budget:,}원({store_area}평)\n\n"
        "요구사항:\n"
        f"1. 1순위 추천 지역은 반드시 [{winner_district}]로 시작, SHAP 상위 요인을 근거로 구체적 이유 설명\n"
        "2. 창업자 조건(객단가·시간대·자본금·임대예산) 적합성 판단\n"
        "3. 경쟁인텔(market_entry_signal·카니발)을 final_recommendation 에 반영\n"
        "4. 분기별 매출 흐름(성수기·비수기)을 창업 타이밍 제안에 활용\n"
        "5. FinalStrategyResult 스키마로 응답\n"
        f"6. overall_legal_risk는 반드시 '{overall_legal_risk}'\n"
        "8. [중요] final_recommendation 출력 형식 — 가독성을 위해 반드시 아래 마크다운 구조로 작성:\n"
        "   - 각 섹션은 '## 섹션제목' 형식의 H2 헤더로 시작 (프론트에서 큰 글씨로 렌더됨)\n"
        "   - 섹션 사이는 빈 줄(\\n\\n) 두 번 들여 문단 분리\n"
        "   - 한 섹션 안에서도 논점이 바뀌면 빈 줄로 문단을 나눌 것\n"
        "   - 핵심 수치·근거는 '- ' bullet 또는 **굵게** 강조\n"
        "   - 필수 섹션 (이 순서대로):\n"
        f"     ## 추천 입지 ({winner_district})\n"
        "     ## 핵심 근거\n"
        "     ## 수익성 전망\n"
        "     ## 리스크 및 대응\n"
        "     ## 창업 타이밍 제언\n"
        "   - 한 줄에 모든 내용을 몰아쓰지 말 것. 줄글이라도 2~3 문장마다 문단 분리\n"
        "   - 시간 범위·수치 범위 표기 시 물결표(~) 대신 하이픈(-) 사용 "
        "(예: '11시-14시', '30대-40대', '월 200-300만원'). "
        "물결표는 마크다운 취소선(~~text~~)과 충돌해 텍스트가 잘려 보일 수 있음.\n"
        "9. summary 는 한 줄(80자 내) 짧은 헤드라인으로 작성 — final_recommendation 과 중복 금지\n"
        + (
            "7. profit_simulation에 ML 실측 수치를 반드시 사용:\n"
            + (f"   - monthly_revenue = {_tcn_rev:,.0f}원 (TCN 점포평균 월매출, 변경 금지)\n" if _tcn_rev else "")
            + (
                f"   - bep_months = {_tcn_bep} (TCN 예측값, profit_simulation.bep_months 필드에 정수로 입력)\n"
                if _tcn_bep
                else ""
            )
            + "   - monthly_cost = 임대료 + 인건비(매출의 25%) + 재료비(매출의 30%) + 기타(5%)\n"
            + "   - net_profit = monthly_revenue - monthly_cost\n"
            + "   - margin_rate = net_profit / monthly_revenue (소수점 2자리)\n"
            if tcn_block
            else "7. profit_simulation 계산 기준:\n"
            "   - monthly_revenue = 일평균 유동인구 × 방문 전환율 3% × 객단가(원)\n"
            "   - monthly_cost = 임대료 + 인건비(매출의 25%) + 재료비(매출의 30%) + 기타(5%)\n"
            "   - net_profit = monthly_revenue - monthly_cost\n"
            "   - margin_rate = net_profit / monthly_revenue (소수점 2자리)\n"
            "   - bep_months = 초기자본금 / max(net_profit, 1) (정수 반올림)\n"
        )
        + "   ※ 추측값 사용 금지 — 제공된 실데이터 수치만 사용\n"
    )

    try:
        # LLM 호출 (Structured Output)
        llm = get_smart_llm().with_structured_output(FinalStrategyResult)

        # API 할당량 관리를 위한 미세 대기
        await asyncio.sleep(1.5)

        final_strategy: FinalStrategyResult = await llm.ainvoke(
            [
                SystemMessage(content=prompt),
                HumanMessage(content=f"{brand_name}의 {winner_district} 출점 최종 전략 보고서를 완성해줘."),
            ]
        )

        print(f"--- [SYNTHESIS] 최종 보고서 생성 완료 (등급: {final_strategy.overall_legal_risk}) ---")

    except Exception as e:
        print(f"!!! [SYNTHESIS ERROR] !!! {str(e)}")
        # 에러 발생 시 Fallback (데이터 보존을 위한 최소 데이터 구성)
        final_strategy = FinalStrategyResult(
            summary=f"{brand_name} {target_district} 분석 결과 요약 생성 중 오류 발생",
            is_direct=False,
            brand_category="franchise",
            overall_legal_risk=overall_legal_risk,
            profit_simulation={"monthly_revenue": 0, "net_profit": 0, "margin_rate": 0.0},
            competitor_analysis={"count": 0, "density": "NORMAL"},
            final_recommendation=f"분석 중 기술적 오류가 발생했습니다: {str(e)}",
        )

    # 3. 데이터 업데이트 (기존 legal_risks를 100% 보존하며 final_report 추가)
    new_analysis_results = dict(analysis_results)
    new_analysis_results["final_report"] = final_strategy.model_dump()
    # main.py가 analysis_report로 읽는 키
    new_analysis_results["market_summary"] = final_strategy.summary + "\n\n" + final_strategy.final_recommendation

    # 랭킹 결과 보존 (main.py → 프론트엔드 전달용)
    new_analysis_results["district_rankings"] = scouting_results
    new_analysis_results["winner_district"] = winner_district
    new_analysis_results["top_3_candidates"] = top_3_candidates

    # [검증] legal_risks가 누락되지 않았는지 다시 한 번 확인
    if "legal_risks" not in new_analysis_results:
        new_analysis_results["legal_risks"] = legal_risks

    # Redis 캐시 저장
    if _redis is not None:
        try:
            await _redis.set(
                cache_key,
                json.dumps(
                    {
                        "final_report": new_analysis_results["final_report"],
                        "market_summary": new_analysis_results["market_summary"],
                        "overall_legal_risk": overall_legal_risk,
                        "legal_risks": legal_risks,  # [#3] 캐시에 legal_risks 포함하여 히트 시 복원 가능
                    },
                    ensure_ascii=False,
                ),
                ex=_CACHE_TTL,
            )
            print(f"[synthesis] 캐시 저장: {cache_key} (TTL: {_CACHE_TTL}s)")
        except Exception as e:
            print(f"[synthesis] Redis 캐시 저장 실패 (무시): {e}")
        finally:  # [#2] 저장 성공/실패 무관하게 항상 연결 종료
            try:
                await _redis.aclose()
            except Exception:
                pass

    # [ATTRIBUTION] 7개 에이전트 attribution 수집 + synthesis 자신 1개 = 최대 8개
    agent_attributions: list[dict] = _collect_upstream_attributions(state, new_analysis_results)
    synthesis_attr = build_attribution(
        agent_id="synthesis",
        display_name="전략 종합",
        kind="LLM",
        sources=[f"{len(agent_attributions)}개 에이전트 결과"],
        verdict=f"종합 판단 · 법률 {overall_legal_risk}",
        reasoning=str(final_strategy.summary if final_strategy else ""),
        confidence=0.85,
    )
    agent_attributions.append(synthesis_attr)
    new_analysis_results["agent_attributions"] = agent_attributions

    return {
        "analysis_results": new_analysis_results,
        "overall_legal_risk": overall_legal_risk,
        "competitor_intel_result": competitor_intel,  # state 에서 파이프라인 끝까지 유지
        "current_agent": "synthesis",
        "agent_attributions": agent_attributions,
    }
