import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from typing import Any, Dict
from sqlalchemy import text
from langsmith.evaluation import evaluate, EvaluationResult
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.agents.graph import compile_graph  # 예진님의 5인 체제 에이전트
from src.agents.tools import MarketDataTool

# ─────────────────────────────────────────────
# Monkey-patch: location_vector 없이 lat/lon 거리 계산
# tools.py 원본을 건드리지 않고 평가 실행 중에만 교체
# ─────────────────────────────────────────────
_BUSINESS_TYPE_TO_CODE: Dict[str, str] = {
    "카페": "I212", "커피": "I212", "비알코올": "I212",
    "음식점": "I201", "한식": "I201", "식당": "I201",
    "치킨": "I206", "피자": "I207", "분식": "I209",
    "주점": "I211", "편의점": "G209",
    "베이커리": "I213", "빵": "I213",
}
_original_get_competitor_stats = MarketDataTool.get_competitor_stats

async def _patched_get_competitor_stats(
    self, lat: float, lon: float, industry_m_code: str, radius_m: int = 500
) -> Dict[str, Any]:
    resolved_code = _BUSINESS_TYPE_TO_CODE.get(industry_m_code, industry_m_code)
    lat_delta = radius_m / 111000.0
    lon_delta = radius_m / 88500.0
    async with self.db_client.get_session() as session:
        query = text("""
            SELECT store_name, industry_s, lat, lon,
                   sqrt(power((lat - :lat) * 111000, 2) + power((lon - :lon) * 88500, 2)) AS distance_m
            FROM store_info
            WHERE industry_m_code = :ind_code
              AND dong_code LIKE '11440%'
              AND lat BETWEEN :lat_min AND :lat_max
              AND lon BETWEEN :lon_min AND :lon_max
            ORDER BY distance_m ASC
        """)
        result = await session.execute(query, {
            "lat": lat, "lon": lon, "ind_code": resolved_code,
            "lat_min": lat - lat_delta, "lat_max": lat + lat_delta,
            "lon_min": lon - lon_delta, "lon_max": lon + lon_delta,
        })
        competitors = [c for c in result.fetchall() if c.distance_m <= radius_m]
    if not competitors:
        return {"competitor_count": 0, "density_level": "LOW",
                "summary": f"반경 {radius_m}m 내 경쟁 업체가 없습니다."}
    count = len(competitors)
    avg_dist = sum(c.distance_m for c in competitors) / count
    density = "HIGH" if count > 10 else "MEDIUM" if count > 3 else "LOW"
    return {
        "competitor_count": count, "density_level": density,
        "avg_distance_m": round(avg_dist, 1),
        "nearest_competitor": competitors[0].store_name,
        "summary": f"반경 {radius_m}m 내 {count}개의 경쟁 업체 (평균 {round(avg_dist, 1)}m).",
    }

MarketDataTool.get_competitor_stats = _patched_get_competitor_stats

graph = compile_graph()

DATASET_NAME = "Market-Analysis-Test"  # 랭스미스에 만든 문제집 이름

# ─────────────────────────────────────────────
# 1. 우리 에이전트(학생)가 문제를 푸는 과정
# ─────────────────────────────────────────────
def predict_agent(inputs: dict) -> dict:
    """
    LangSmith 데이터셋 inputs 구조 (두 가지 형식 지원):
      - 구조화: {"district": "서교동", "business_type": "카페", "brand_name": "브랜드명", "query": "..."}
      - 자유형: {"query": "서교동 카페 창업 어떨까?"}  ← query에서 지역/업종 파싱 시도
    """
    query = inputs.get("query", "")
    district = inputs.get("district") or _parse_district(query)
    business_type = inputs.get("business_type") or _parse_business_type(query)
    brand_name = inputs.get("brand_name", "테스트 브랜드")

    initial_state = {
        "messages": [("user", query)],
        "business_type": business_type,
        "brand_name": brand_name,
        "target_district": district,
        "market_data": {"lat": 37.5565, "lng": 126.9239},
        "legal_info": [],
        "scouting_results": [],
        "top_3_candidates": [],
        "winner_district": district,
        "brand_analysis": {},
        "analysis_results": {},
        "analysis_metrics": {},
        "overall_legal_risk": "Caution",
        "current_agent": "start",
        "next_step": "",
        "errors": [],
    }

    result = asyncio.run(graph.ainvoke(initial_state))

    # 실제 분석 결과를 출력으로 반환 (messages[-1]은 입력 메시지이므로 사용 안 함)
    analysis = result.get("analysis_results", {})
    final_report = analysis.get("final_report", {})
    market_summary = analysis.get("market_summary", "")
    market_report = analysis.get("market_report", "")
    population_report = analysis.get("population_report", "")
    legal_risks = analysis.get("legal_risks", [])

    # 수익 시뮬레이션
    sim = final_report.get("profit_simulation", {})
    sim_text = ""
    if sim:
        sim_text = (
            f"[수익 시뮬레이션]\n"
            f"- 월 예상 매출: {sim.get('monthly_revenue', 0):,}원\n"
            f"- 월 순이익: {sim.get('net_profit', 0):,}원\n"
            f"- 수익률: {sim.get('margin_rate', 0)}%"
        )

    # 법률 리스크 요약
    legal_text = ""
    if legal_risks:
        risk_lines = "\n".join(
            f"  - {r.get('type', '?')} [{r.get('level', '?')}]: {r.get('summary', '')}"
            for r in legal_risks[:5]
        )
        legal_text = f"[법률 리스크]\n{risk_lines}"

    output_text = "\n\n".join(filter(None, [
        market_summary,
        f"[상권 분석]\n{market_report}" if market_report else "",
        f"[유동인구 분석]\n{population_report}" if population_report else "",
        legal_text,
        sim_text,
        f"[최종 제언]\n{final_report.get('final_recommendation', '')}" if final_report else "",
    ]))

    return {"output": output_text or "분석 결과 없음"}


# 자유형 query에서 지역/업종을 간단히 파싱하는 헬퍼
_DISTRICT_KEYWORDS = [
    "서교동", "합정동", "공덕동", "마포동", "망원동", "연남동",
    "상암동", "성산동", "대흥동", "용강동", "아현동", "염리동",
    "신수동", "창전동", "도화동", "토정동",
]
_BUSINESS_KEYWORDS = {
    "카페": "카페", "커피": "카페", "음식점": "음식점", "식당": "음식점",
    "치킨": "치킨", "피자": "피자", "분식": "분식", "주점": "주점",
    "편의점": "편의점", "베이커리": "베이커리",
}

def _parse_district(query: str) -> str:
    for d in _DISTRICT_KEYWORDS:
        if d in query:
            return d
    return "서교동"  # 기본값

def _parse_business_type(query: str) -> str:
    for keyword, btype in _BUSINESS_KEYWORDS.items():
        if keyword in query:
            return btype
    return "카페"  # 기본값


# ─────────────────────────────────────────────
# 2. 깐깐한 채점관 소환 (Gemini 2.0 Flash - 무료 API 키 활용)
# ─────────────────────────────────────────────
_judge = ChatGoogleGenerativeAI(model="gemini-3-flash-preview", temperature=0)

def claude_qa_evaluator(run, example) -> EvaluationResult:
    """
    Claude가 에이전트 출력을 평가합니다.
    - 참조 답안(answer)이 있으면: 비교 채점
    - 참조 답안이 없으면: 출력 품질 자체를 절대 평가
    """
    output = (run.outputs or {}).get("output", "")
    reference = (example.outputs or {}).get("answer", "")

    if not output or output == "분석 결과 없음":
        return EvaluationResult(key="correctness", score=0.0, comment="에이전트 출력 없음")

    if reference:
        # 참조 답안 있음 → 비교 채점
        system_msg = (
            "당신은 상권분석 AI 에이전트의 출력을 평가하는 채점관입니다. "
            "참조 답안과 비교하여 에이전트의 답변이 얼마나 정확하고 유용한지 평가하세요. "
            "점수는 0.0(완전 오답)~1.0(완벽) 사이 숫자를 첫 줄에만 출력하고, "
            "두 번째 줄부터 평가 이유를 간단히 작성하세요."
        )
        user_msg = (
            f"[참조 답안]\n{reference}\n\n"
            f"[에이전트 출력]\n{output}\n\n"
            "점수(0.0~1.0)를 첫 줄에 숫자만 출력하세요."
        )
    else:
        # 참조 답안 없음 → 절대 품질 평가
        system_msg = (
            "당신은 프랜차이즈 상권분석 AI 에이전트의 출력을 평가하는 전문 채점관입니다. "
            "아래 기준으로 출력 품질을 0.0~1.0 사이로 평가하세요.\n"
            "평가 기준:\n"
            "- 상권/유동인구/법률 분석 내용이 구체적으로 포함되어 있는가 (0.4점)\n"
            "- 수익 시뮬레이션 등 정량적 수치가 제시되어 있는가 (0.3점)\n"
            "- 창업 전략적 제언이 명확하고 실용적인가 (0.3점)\n"
            "점수를 첫 줄에 숫자만 출력하고, 두 번째 줄부터 평가 이유를 작성하세요."
        )
        user_msg = (
            f"[에이전트 출력]\n{output}\n\n"
            "위 출력의 품질 점수(0.0~1.0)를 첫 줄에 숫자만 출력하세요."
        )

    prompt = [SystemMessage(content=system_msg), HumanMessage(content=user_msg)]
    response = _judge.invoke(prompt)

    # Gemini는 content가 list로 올 수 있음
    raw = response.content
    if isinstance(raw, list):
        raw = "".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in raw)
    else:
        raw = str(raw)

    lines = raw.strip().splitlines()
    try:
        score = max(0.0, min(1.0, float(lines[0].strip())))
    except ValueError:
        score = 0.0
    comment = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

    return EvaluationResult(key="correctness", score=score, comment=comment)


# ─────────────────────────────────────────────
# 3. 시험 시작!
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("[START] 클로드 채점관이 에이전트 자동 평가를 시작합니다...")

    try:
        evaluate(
            predict_agent,
            data=DATASET_NAME,
            evaluators=[claude_qa_evaluator],
            experiment_prefix="5-Agent-Eval-Claude",
        )
        print("[DONE] 평가 완료! 랭스미스 웹사이트에서 성적표를 확인하세요.")
    finally:
        MarketDataTool.get_competitor_stats = _original_get_competitor_stats
        print("[PATCH] MarketDataTool.get_competitor_stats -> 원본 복원 완료")
