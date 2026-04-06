"""
법규검토 Agent — RAG 기반 가맹사업법/상가임대차보호법 리스크 검토

주요 데이터 소스:
  - pgvector에 인덱싱된 가맹사업법 / 상가임대차보호법 조문
  - 업종별 용도지역 규제 (constants.py)

리스크 레벨:
  - "safe"    : 특별한 법률 리스크 없음
  - "caution" : 주의 필요, 사전 확인 권고
  - "danger"  : 위반 가능성 높음, 전문가 상담 필수
"""

import asyncio
from typing import List, Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from src.schemas.state import AgentState
from src.database.vector_db import legal_db
from src.config.settings import settings
from src.agents.llms import get_smart_llm

# ── 용도지역별 허용 업종 규칙 ────────────────────────────────────────────────
_ZONING_RULES: dict[str, dict] = {
    "제1종전용주거지역": {"허용": [], "제한": ["카페", "음식점", "편의점"]},
    "제2종전용주거지역": {"허용": [], "제한": ["카페", "음식점", "편의점"]},
    "제1종일반주거지역": {"허용": ["편의점"], "제한": ["카페", "음식점"]},
    "제2종일반주거지역": {"허용": ["편의점", "카페"], "제한": ["음식점"]},
    "제3종일반주거지역": {"허용": ["편의점", "카페", "음식점"], "제한": []},
    "준주거지역": {"허용": ["편의점", "카페", "음식점"], "제한": []},
    "일반상업지역": {"허용": ["편의점", "카페", "음식점"], "제한": []},
    "근린상업지역": {"허용": ["편의점", "카페", "음식점"], "제한": []},
}

_DISTRICT_ZONE_MAP: dict[str, str] = {
    "서교동": "일반상업지역",
    "합정동": "근린상업지역",
    "공덕동": "일반상업지역",
    "망원1동": "근린상업지역",
    "망원2동": "근린상업지역",
    "연남동": "제3종일반주거지역",
    "대흥동": "제2종일반주거지역",
    "염리동": "제2종일반주거지역",
    "성산1동": "근린상업지역",
    "성산2동": "근린상업지역",
    "상암동": "일반상업지역",
    "아현동": "근린상업지역",
    "도화동": "근린상업지역",
    "용강동": "근린상업지역",
    "신수동": "제2종일반주거지역",
    "서강동": "근린상업지역",
}


async def legal_analyst_node(state: AgentState) -> dict:
    """
    법률 검토 에이전트 메인 노드:
    - PROD: pgvector 기반 실데이터 검색(RAG) + Gemini 3.1 Pro 활용 심층 분석
    - 용도지역 규제 및 가맹사업법/임대차법 리스크 통합 검토
    """
    target_dist = state.get("target_district", "해당")
    business_type = state.get("business_type", "cafe")
    print(f"--- [LEGAL ANALYST] {target_dist} 법률 검토 시작 ---")

    # 0. DB 상태 확인 로그
    total_docs = legal_db.get_total_count()
    print(f"DEBUG: 현재 Legal DB 내 총 문서 개수: {total_docs}개")

    # 1. 문서 검색 (RAG) - 와이드 검색(Wide Search) 적용
    wide_query = (
        f"{target_dist} 마포구 {business_type} "
        f"상권 규제 가맹사업법 업종별 행정 처분 법률 리스크"
    )

    if settings.app_mode == "DEV":
        search_results = [
            {
                "content": "상가건물 임대차보호법 제10조: 임대차기간 만료 전 계약갱신 요구권...",
                "metadata": {"source": "상가임대차법", "relevance": 0.95},
            }
        ]
    else:
        print(f"DEBUG: Vector DB 와이드 검색 ('{wide_query}')")
        search_results = await legal_db.asearch_legal_docs(wide_query)

    # 2. 분석에 사용할 문서 필터링 (임계값 0.3으로 하향 조정)
    context_docs = [
        doc
        for doc in search_results
        if doc.get("metadata", {}).get("relevance", 0) >= 0.3
    ]
    
    # 3. 용도지역 규제 체크 (규칙 기반)
    zone = _DISTRICT_ZONE_MAP.get(target_dist, "근린상업지역")
    rules = _ZONING_RULES.get(zone, {"허용": [], "제한": []})
    type_label = {"cafe": "카페", "restaurant": "음식점", "convenience": "편의점"}.get(business_type, business_type)
    
    zoning_info = ""
    if type_label in rules["제한"]:
        zoning_info = f"주의: {target_dist}의 용도지역({zone})에서 {type_label} 영업은 제한될 수 있습니다. "
    else:
        zoning_info = f"{target_dist}의 용도지역({zone})에서 {type_label} 영업은 법적으로 허용되는 구역입니다. "

    # 4. 요약 리포트 생성 (Gemini 3.1 Pro 심층 분석)
    legal_risks_summary = ""
    
    if not context_docs:
        # [기본 가이드라인 출력] 데이터가 없는 경우 Fallback
        legal_risks_summary = (
            f"{zoning_info}서울특별시 공통 상권 가이드라인: 상가임대차보호법에 따른 권리금 보호 및 "
            "임대료 인상 상한선(5%)을 준수해야 하며, 프랜차이즈 가맹사업법상 정보공개서 등록 의무를 확인하십시오."
        )
        print("DEBUG: 검색 결과가 없어 기본 가이드라인(Fallback)을 사용합니다.")
    else:
        context_str = "\n\n".join([f"[법규/사례] {doc['content']}" for doc in context_docs])
        prompt = (
            "당신은 마포구 창업 전문 AI 법률 상담 전담 변호사입니다. 아래 검색된 실제 법령 및 조례 정보를 바탕으로 "
            f"사용자의 '{target_dist} {type_label}' 창업 시나리오를 심층 분석하세요.\n\n"
            f"현지 용도지역 분석: {zoning_info}\n\n"
            "가이드라인:\n"
            f"1. 반드시 '{target_dist}' 상권의 특이점(예: 오피스 밀집 지역 조례, 인근 통학로 제한 등)을 언급하세요.\n"
            "2. '~이므로 ~주의가 필요합니다'와 같이 전문적으로 요약하세요.\n"
            "3. 전체 내용을 3문장 이내로 정리하세요.\n"
            f"### 관련 법률 데이터:\n{context_str}"
        )

        try:
            llm = get_smart_llm()
            response = await llm.ainvoke([
                SystemMessage(content=prompt),
                HumanMessage(content=f"{target_dist} 법률 분석 리포트를 작성해줘.")
            ])
            legal_risks_summary = str(response.content)
        except Exception as e:
            print(f"!!! [LEGAL ANALYST ERROR] !!! {str(e)}")
            legal_risks_summary = f"{zoning_info} 법률 분석 도중 오류가 발생했습니다. 상가임대차보호법 일반 원칙을 준수하세요."

    print(f"DEBUG: Gemini Pro 법률 분석 완료")

    return {
        "legal_info": search_results,
        "analysis_results": {
            **state.get("analysis_results", {}),
            "legal_risks": legal_risks_summary,
        },
        "current_agent": "legal_analyst",
    }
