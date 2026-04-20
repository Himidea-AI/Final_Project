"""
법규검토 Agent — RAG 기반 가맹사업법/상가임대차보호법 리스크 검토

주요 데이터 소스:
  - ChromaDB에 인덱싱된 가맹사업법 / 상가임대차보호법 조문
  - 업종별 용도지역 규제 (constants.py)

리스크 레벨:
  - "safe"    : 특별한 법률 리스크 없음
  - "caution" : 주의 필요, 사전 확인 권고
  - "danger"  : 위반 가능성 높음, 전문가 상담 필수
"""

import asyncio
import json

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.llms import get_fast_llm
from src.chains.prompts import LEGAL_AGENT_SYSTEM_PROMPT
from src.chains.retriever import LegalDocumentRetriever
from src.config.constants import DISTRICT_ZONE_MAP, ZONING_RULES
from src.config.settings import settings
from src.schemas.state import AgentState
from src.schemas.structured_output import LegalBatchOutput
from src.services.ftc_franchise import FtcFranchiseClient
from src.services.law_api import LawApiClient


async def _search_ftc_from_db(brand_name: str) -> dict | None:
    """
    ftc_brand_franchise 테이블에서 브랜드 정보 검색 (DB 직접 조회).

    API 호출 없이 DB에 적재된 34,000+ 건의 정보공개서 데이터에서 검색.
    최신 연도 기준으로 반환하며, 폐점률을 계산하여 리스크 판정에 사용.
    """
    from src.agents.nodes.market_analyst import db_client

    try:
        if db_client.engine is None:
            await db_client.connect()

        async with db_client.get_session() as session:
            from sqlalchemy import text

            # LIKE 검색 (부분 일치) — 브랜드명 내 %,_ 문자 이스케이프
            safe_brand = brand_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = text("""
                SELECT yr, "corpNm", "brandNm", "frcsCnt", "newFrcsRgsCnt",
                       "ctrtEndCnt", "ctrtCncltnCnt", "avrgSlsAmt"
                FROM ftc_brand_franchise
                WHERE "brandNm" LIKE :pattern ESCAPE '\\'
                ORDER BY yr DESC
                LIMIT 1
            """)
            row = (await session.execute(stmt, {"pattern": f"%{safe_brand}%"})).fetchone()

            if not row:
                return None

            store_count = int(row.frcsCnt or 0)
            end_count = int(row.ctrtEndCnt or 0)
            cancel_count = int(row.ctrtCncltnCnt or 0)
            avg_sales = int(row.avrgSlsAmt or 0) * 10000  # 만원 단위 → 원 단위

            churn_rate = (end_count + cancel_count) / max(store_count, 1)

            return {
                "brand_name": row.brandNm,
                "corp_name": row.corpNm,
                "store_count_total": store_count,
                "churn_rate": round(churn_rate, 4),
                "avg_sales_amount": avg_sales,
                "franchise_fee": 0,  # DB에 가맹금 컬럼 없음
            }

    except Exception as e:
        print(f"[_search_ftc_from_db] DB 조회 실패: {e}")
        return None


async def check_ftc_franchise(state: AgentState) -> dict:
    """
    공정위 가맹사업 정보공개서 검토 — 브랜드 폐점률·매출·가맹금 리스크 판정.

    주요 검토 항목:
    - 폐점률 (10% 초과 시 위험, 5% 초과 시 주의)
    - 평균 매출액 (1억 미만 시 주의)
    - 가맹금 수준 (1000만 원 초과 시 주의)

    Returns:
        dict: {type, level, summary, articles, recommendation}
    """
    brand = state.get("brand_name") or ""

    if not brand:
        return {
            "type": "ftc_franchise",
            "level": "caution",
            "summary": "브랜드명이 입력되지 않아 공정위 정보공개서 조회를 건너뜁니다.",
            "articles": [],
            "recommendation": "브랜드명 입력 후 재검토 권장",
        }

    # 1차: DB에서 검색 (ftc_brand_franchise 테이블 — 16,000+ 브랜드)
    # 2차: API 실패 시에도 DB fallback
    detail = await _search_ftc_from_db(brand)

    if not detail and settings.ftc_api_key:
        try:
            client = FtcFranchiseClient(api_key=settings.ftc_api_key)
            detail = await client.get_brand_detail(brand)
        except Exception as e:
            print(f"[check_ftc_franchise] API 실패 (DB fallback 사용): {e}")

    if not detail:
        return {
            "type": "ftc_franchise",
            "level": "caution",
            "summary": f"'{brand}' 브랜드의 공정위 정보공개서를 찾을 수 없습니다.",
            "articles": [],
            "recommendation": "공정위 가맹사업정보제공시스템 직접 확인 권장",
        }

    try:
        churn_rate = detail.get("churn_rate", 0.0)
        avg_sales = detail.get("avg_sales_amount", 0)
        franchise_fee = detail.get("franchise_fee", 0)
        store_count = detail.get("store_count_total", 0)

        # 리스크 레벨 판정
        if churn_rate > 0.10:
            level = "danger"
        elif churn_rate > 0.05 or avg_sales < 100_000_000:
            level = "caution"
        else:
            level = "safe"

        summary = (
            f"'{detail.get('brand_name', brand)}' ({detail.get('corp_name', '')}) "
            f"정보공개서 기준 — "
            f"전체 가맹점 수: {store_count}개, "
            f"폐점률: {churn_rate:.1%}, "
            f"평균 매출액: {avg_sales:,}원, "
            f"가입비: {franchise_fee:,}원. "
        )
        if level == "danger":
            summary += "폐점률이 10%를 초과하여 사업 안정성 리스크가 높습니다."
        elif level == "caution":
            summary += "폐점률 또는 매출 수준에서 주의가 필요합니다."
        else:
            summary += "공정위 지표 기준 안정적인 브랜드로 판단됩니다."

        recommendation = ""
        if level == "danger":
            recommendation = "가맹본부 재무 상태 및 폐점 원인 심층 확인 필수"
        elif level == "caution":
            recommendation = "가맹 계약 전 정보공개서 원문 직접 검토 권장"

        return {
            "type": "ftc_franchise",
            "level": level,
            "summary": summary,
            "articles": [],
            "recommendation": recommendation,
        }

    except Exception as e:
        return {
            "type": "ftc_franchise",
            "level": "caution",
            "summary": f"공정위 정보공개서 조회 중 오류 발생: {e}",
            "articles": [],
            "recommendation": "공정위 가맹사업정보제공시스템 직접 확인 권장",
        }


async def check_zoning_regulation(state: AgentState) -> dict:
    """
    용도지역 규제 검토 — 대상 행정동의 용도지역에서 해당 업종 영업 가능 여부.

    LLM 없이 constants 기반 규칙으로 판정 (빠르고 결정론적).

    Returns:
        dict: {type, level, zone, business_type, allowed, summary}
    """
    district = state.get("target_district", "")
    business_type = state.get("business_type", "")  # "cafe" | "restaurant" | "convenience"

    zone = DISTRICT_ZONE_MAP.get(district, "근린상업지역")  # 알 수 없는 동은 상업지역으로 가정
    rules = ZONING_RULES.get(zone, {"허용": [], "제한": []})

    # business_type 코드 → 한글 매핑 (확장 가능)
    _BIZ_TYPE_LABEL = {
        "cafe": "카페",
        "coffee": "카페",
        "카페": "카페",
        "restaurant": "음식점",
        "음식점": "음식점",
        "convenience": "편의점",
        "편의점": "편의점",
        "bakery": "카페",
        "제과": "카페",
        "chicken": "음식점",
        "치킨": "음식점",
        "fastfood": "음식점",
        "패스트푸드": "음식점",
    }
    type_label = _BIZ_TYPE_LABEL.get(business_type.lower(), business_type)

    if type_label in rules["제한"]:
        level = "danger"
        summary = f"'{district}'의 용도지역({zone})에서 '{type_label}' 영업은 제한될 수 있습니다."
    elif type_label in rules["허용"] or not rules["제한"]:
        level = "safe"
        summary = f"'{district}'의 용도지역({zone})에서 '{type_label}' 영업 가능합니다."
    else:
        level = "caution"
        summary = f"'{district}'의 용도지역({zone}) 규제를 현장 확인 후 영업 가능 여부를 판단하세요."

    return {
        "type": "zoning_regulation",
        "level": level,
        "zone": zone,
        "business_type": type_label,
        "allowed": level != "danger",
        "summary": summary,
        "articles": [],
        "recommendation": "토지이음(eum.go.kr)에서 실제 용도지역을 확인하세요." if level != "safe" else "",
    }


async def _run_legal_pipeline(state: dict) -> dict:
    """
    2단계 풀 파이프라인으로 법률 검토 수행.

    Phase 1 (병렬 18개): RAG×13 + 판례×4 + FTC API
                         zoning은 I/O 없는 규칙 기반이므로 즉시 실행
    Phase 2 (병렬 12개): LLM 기반 check 함수 동시 실행

    기존 순차 실행 대비 ~35~68초 → ~8~12초로 단축.
    동일 brand+district+business_type 조합은 Redis에 24시간 캐시.
    """

    import redis.asyncio as aioredis

    from src.config.settings import settings

    brand = state.get("brand_name") or "해당 브랜드"
    district = state.get("target_district", "")
    business_type = state.get("business_type", "")

    # 캐시 키 정규화 — 영문/한글 혼용 시 동일 캐시 히트 보장
    _BIZ_NORMALIZE = {"cafe": "카페", "restaurant": "음식점", "convenience": "편의점"}
    _normalized_biz = _BIZ_NORMALIZE.get(business_type.lower(), business_type)

    # Redis 캐시 조회 — 동일 조합 재요청 시 LLM 호출 없이 즉시 반환
    _CACHE_TTL = 86400  # 24시간
    cache_key = f"v3:legal:{brand}:{district}:{_normalized_biz}"
    _redis = None
    try:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        cached = None if settings.debug else await _redis.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            legal_risks = cached_data.get("legal_risks")
            legal_info = cached_data.get("legal_info")
            if legal_risks is None or legal_info is None:
                print(f"[legal_node] 캐시 데이터 손상 - 재계산: {cache_key}")
            else:
                print(f"[legal_node] 캐시 히트: {cache_key}")
                analysis = dict(state.get("analysis_results") or {})
                analysis["legal_risks"] = legal_risks
                overall_cached = cached_data.get("overall_legal_risk", "caution")
                analysis["overall_legal_risk"] = overall_cached
                await _redis.aclose()
                return {
                    **state,
                    "analysis_results": analysis,
                    "legal_info": legal_info,
                    "overall_legal_risk": overall_cached,
                }
    except Exception as e:
        print(f"[legal_node] Redis 캐시 조회 실패 (무시하고 계속): {e}")
        if _redis is not None:  # 조회 실패 시 연결 누수 방지
            try:
                await _redis.aclose()
            except Exception:
                pass
        _redis = None

    retriever = LegalDocumentRetriever()

    franchise_q = f"{brand} 영업지역 보장 동일 브랜드 출점 제한 가맹사업법"
    lease_q = "권리금 회수 기회 보호 계약갱신요구권 환산보증금 상가임대차보호법"
    food_q = f"{business_type} 영업신고 허가 위생교육 시설기준 식품위생법"
    safety_q = f"{business_type} 다중이용업소 소방시설 안전시설 완비증명 의무"
    summary_q = f"{business_type} {district} 프랜차이즈 법률 검토"
    building_q = f"{business_type} 건축물 용도 근린생활시설 용도변경 건축법"
    fire_q = f"{business_type} 소방시설 스프링클러 소화기 소방안전관리자 설치의무"
    labor_q = "근로계약서 최저임금 주휴수당 가산임금 4대보험 근로기준법"
    vat_q = "사업자등록 일반과세자 간이과세자 세금계산서 부가가치세"
    privacy_q = "개인정보 수집 동의 처리방침 CCTV 고객정보"
    accessibility_q = f"{business_type} 편의시설 경사로 장애인 설치의무"
    sewage_q = f"{business_type} 오수처리 유류분리기 그리스트랩 폐수 하수도"
    fair_trade_q = f"{brand} 가맹본부 불공정거래 거래강제 필수물품 공급"

    law_client = LawApiClient()

    # zoning: I/O 없는 규칙 기반 — 즉시 실행 후 Phase 1 병렬 대기
    zoning_result = await check_zoning_regulation(state)

    # Phase 1: RAG×13 + 판례×6 + FTC API 병렬 실행 (총 20개)
    # return_exceptions=True — 한 개 실패해도 나머지 결과 유지
    _phase1_results = await asyncio.gather(
        # RAG 검색 (13개)
        retriever.search(franchise_q, top_k=5, source_filter=LegalDocumentRetriever.FRANCHISE_LAW_SOURCES),
        retriever.search(lease_q, top_k=5, source_filter=LegalDocumentRetriever.LEASE_LAW_SOURCES),
        retriever.search(food_q, top_k=5, source_filter=LegalDocumentRetriever.FOOD_HYGIENE_SOURCES),
        retriever.search(safety_q, top_k=5, source_filter=LegalDocumentRetriever.SAFETY_SOURCES),
        retriever.search(summary_q, top_k=10),
        retriever.search(building_q, top_k=5, source_filter=LegalDocumentRetriever.BUILDING_LAW_SOURCES),
        retriever.search(fire_q, top_k=5, source_filter=LegalDocumentRetriever.FIRE_SAFETY_SOURCES),
        retriever.search(labor_q, top_k=5, source_filter=LegalDocumentRetriever.LABOR_LAW_SOURCES),
        retriever.search(vat_q, top_k=5, source_filter=LegalDocumentRetriever.VAT_LAW_SOURCES),
        retriever.search(privacy_q, top_k=5, source_filter=LegalDocumentRetriever.PRIVACY_LAW_SOURCES),
        retriever.search(accessibility_q, top_k=5, source_filter=LegalDocumentRetriever.ACCESSIBILITY_LAW_SOURCES),
        retriever.search(sewage_q, top_k=5, source_filter=LegalDocumentRetriever.SEWAGE_LAW_SOURCES),
        retriever.search(fair_trade_q, top_k=5, source_filter=LegalDocumentRetriever.FAIR_TRADE_SOURCES),
        # 판례 검색 (6개) — 키워드를 구체화하여 판례 품질 향상
        law_client.search_precedents("가맹사업 영업지역", display=3),
        law_client.search_precedents("권리금 회수", display=3),
        law_client.search_precedents("식품위생 영업허가", display=3),
        law_client.search_precedents("다중이용업소 소방", display=3),
        law_client.search_precedents("건축물 용도변경 근린생활시설", display=2),
        law_client.search_precedents("근로계약 최저임금", display=2),
        # FTC API — RAG docs 불필요, Phase 1에서 선행 실행
        check_ftc_franchise(state),
        return_exceptions=True,
    )

    # 예외 결과를 빈 리스트/caution dict로 대체
    def _safe_list(r: object) -> list:
        if isinstance(r, Exception):
            print(f"[legal_node] Phase 1 검색 실패 (무시하고 계속): {r}")
            return []
        return r  # type: ignore[return-value]

    def _safe_ftc(r: object) -> dict:
        if isinstance(r, Exception):
            print(f"[legal_node] FTC API 실패 (무시하고 계속): {r}")
            return {
                "type": "ftc_franchise",
                "level": "caution",
                "summary": f"FTC API 오류: {r}",
                "articles": [],
                "recommendation": "",
            }
        return r  # type: ignore[return-value]

    (
        franchise_docs,
        lease_docs,
        food_docs,
        safety_docs,
        legal_info_docs,
        building_docs,
        fire_docs,
        labor_docs,
        vat_docs,
        privacy_docs,
        accessibility_docs,
        sewage_docs,
        fair_trade_docs,
        franchise_prec,
        lease_prec,
        food_prec,
        safety_prec,
        building_prec,
        labor_prec,
        ftc_result,
    ) = (
        *[_safe_list(_phase1_results[i]) for i in range(19)],
        _safe_ftc(_phase1_results[19]),
    )

    # Phase 2: 12개 법률 항목을 단일 LLM 배치 호출로 처리 (12회 → 1회)
    _BATCH_TYPES = [
        "franchise_law",
        "commercial_lease_law",
        "food_hygiene",
        "safety_regulation",
        "building_law",
        "fire_safety_law",
        "labor_law",
        "vat_law",
        "privacy_law",
        "accessibility_law",
        "sewage_law",
        "fair_trade_law",
    ]
    _BATCH_LABELS = {
        "franchise_law": "가맹사업법 — 영업지역 침해 여부, 정보공개서 기재사항, 가맹금 예치 의무",
        "commercial_lease_law": "상가임대차보호법 — 권리금 회수기회 보호(제10조의4), 계약갱신요구권(10년), 환산보증금(서울 9억)",
        "food_hygiene": "식품위생법 — 영업 종류별 신고·허가 의무, 위생교육 이수, 영업장 시설 기준",
        "safety_regulation": "다중이용업소법 — 면적·업종 기준 해당 여부, 소방시설 설치, 안전시설 완비증명서",
        "building_law": "건축법 — 건축물 용도 적합(근린생활시설 등), 용도변경 신고·허가, 불법건축물 리스크",
        "fire_safety_law": "소방시설법 — 면적별 소방시설 설치(스프링클러·소화기), 소방안전관리자 선임, 정기점검",
        "labor_law": "근로기준법 — 근로계약서 작성·교부, 최저임금(2026년 기준), 주휴수당·가산임금, 4대보험",
        "vat_law": "부가가치세법 — 사업자등록(개업 전), 일반과세 vs 간이과세(연 8천만원), 세금계산서 발행",
        "privacy_law": "개인정보보호법 — 고객 정보 수집 동의, 개인정보 처리방침 공개, CCTV 안내판 부착",
        "accessibility_law": "장애인편의증진법 — 편의시설 설치 대상(300㎡ 이상), 경사로·장애인화장실·점자블록",
        "sewage_law": "하수도법/물환경보전법 — 오수처리시설, 유류분리기(그리스트랩) 설치, 폐수 배출 기준",
        "fair_trade_law": "공정거래법 — 가맹본부 불공정 거래 금지, 부당 거래 강제(필수 물품 고가 공급), 공정위 신고",
    }

    # 법률별 RAG 조문 번호 추출 (articles 필드 채우기용)
    def _extract_articles(docs: list[dict]) -> list[str]:
        """RAG 문서 메타데이터에서 조문 번호(article) 추출, 중복 제거."""
        seen = set()
        articles = []
        for d in docs:
            art = d.get("metadata", {}).get("article", "")
            if art and art != "전문" and art not in seen:
                seen.add(art)
                articles.append(art)
        return articles[:5]  # 최대 5개

    # 모든 RAG 문서를 법률별로 정리하여 컨텍스트 구성
    docs_context = ""
    docs_map = {
        "franchise_law": franchise_docs + franchise_prec,
        "commercial_lease_law": lease_docs + lease_prec,
        "food_hygiene": food_docs + food_prec,
        "safety_regulation": safety_docs + safety_prec,
        "building_law": building_docs + building_prec,
        "fire_safety_law": fire_docs,
        "labor_law": labor_docs + labor_prec,
        "vat_law": vat_docs,
        "privacy_law": privacy_docs,
        "accessibility_law": accessibility_docs,
        "sewage_law": sewage_docs,
        "fair_trade_law": fair_trade_docs,
    }
    # 법률별 균등 분배 — 12개 법률에 각 최대 1000자씩 (뒤쪽 법률 잘림 방지)
    _MAX_PER_LAW = 1000
    for law_type, docs in docs_map.items():
        if docs:
            snippets = " | ".join(d["content"][:400] for d in docs[:3])
            if len(snippets) > _MAX_PER_LAW:
                snippets = snippets[:_MAX_PER_LAW] + "…"
            docs_context += f"[{_BATCH_LABELS[law_type]}] {snippets}\n"

    items_desc = "\n".join(f'{i + 1}. type="{t}" — {_BATCH_LABELS[t]}' for i, t in enumerate(_BATCH_TYPES))

    system_content = (
        f"{LEGAL_AGENT_SYSTEM_PROMPT}\n\n"
        f"리스크 레벨 기준:\n"
        f"- safe: 법률 위반 가능성 없음, 일반적 준수사항만 존재\n"
        f"- caution: 사전 확인·준비 필요, 미이행 시 과태료·행정처분 가능\n"
        f"- danger: 법률 위반 가능성 높음, 영업정지·허가취소·형사처벌 위험\n\n"
        f"[평가 항목]\n{items_desc}\n\n"
        "12개 항목을 빠짐없이 items 리스트에 포함하세요. summary는 1~2문장, recommendation은 구체적 행동 권고."
    )

    user_content = (
        f"브랜드: {brand} / 업종: {business_type} / 지역: {district}\n\n"
        f"[참고 법률 문서 발췌]\n{docs_context}\n\n"
        "위 자료를 바탕으로 12개 법률 항목의 창업 리스크를 평가하세요. "
        "각 항목의 '—' 뒤에 적힌 검토 포인트를 반드시 확인하세요."
    )

    batch_results: list[dict] = []
    try:
        llm = get_fast_llm().with_structured_output(LegalBatchOutput)
        result: LegalBatchOutput = await llm.ainvoke(
            [
                SystemMessage(content=system_content),
                HumanMessage(content=user_content),
            ]
        )
        seen = set()
        for item in result.items:
            if item.type in _BATCH_TYPES and item.type not in seen:
                batch_results.append(
                    {
                        "type": item.type,
                        "level": item.level,
                        "summary": item.summary,
                        "articles": _extract_articles(docs_map.get(item.type, [])),
                        "recommendation": item.recommendation,
                    }
                )
                seen.add(item.type)
        # 누락된 항목 caution으로 보완
        for t in _BATCH_TYPES:
            if t not in seen:
                batch_results.append(
                    {
                        "type": t,
                        "level": "caution",
                        "summary": "LLM 응답 누락 — 수동 검토 필요",
                        "articles": [],
                        "recommendation": "전문가 상담 권장",
                    }
                )
        print(f"[legal_node] 배치 LLM 완료 (Structured Output) - {len(batch_results)}개 항목 처리")
    except Exception as e:
        print(f"[legal_node] 배치 LLM 실패: {e} - 전체 caution 처리")
        batch_results = [
            {
                "type": t,
                "level": "caution",
                "summary": f"LLM 분석 실패: {e}",
                "articles": [],
                "recommendation": "전문가 상담 권장",
            }
            for t in _BATCH_TYPES
        ]

    # batch_results를 타입별로 인덱싱
    _batch_map = {r["type"]: r for r in batch_results}

    risks = [
        _batch_map.get(
            "franchise_law",
            {"type": "franchise_law", "level": "caution", "summary": "", "articles": [], "recommendation": ""},
        ),
        _batch_map.get(
            "commercial_lease_law",
            {"type": "commercial_lease_law", "level": "caution", "summary": "", "articles": [], "recommendation": ""},
        ),
        zoning_result,
        _batch_map.get(
            "food_hygiene",
            {"type": "food_hygiene", "level": "caution", "summary": "", "articles": [], "recommendation": ""},
        ),
        _batch_map.get(
            "safety_regulation",
            {"type": "safety_regulation", "level": "caution", "summary": "", "articles": [], "recommendation": ""},
        ),
        ftc_result,
        _batch_map.get(
            "building_law",
            {"type": "building_law", "level": "caution", "summary": "", "articles": [], "recommendation": ""},
        ),
        _batch_map.get(
            "fire_safety_law",
            {"type": "fire_safety_law", "level": "caution", "summary": "", "articles": [], "recommendation": ""},
        ),
        _batch_map.get(
            "labor_law", {"type": "labor_law", "level": "caution", "summary": "", "articles": [], "recommendation": ""}
        ),
        _batch_map.get(
            "vat_law", {"type": "vat_law", "level": "caution", "summary": "", "articles": [], "recommendation": ""}
        ),
        _batch_map.get(
            "privacy_law",
            {"type": "privacy_law", "level": "caution", "summary": "", "articles": [], "recommendation": ""},
        ),
        _batch_map.get(
            "accessibility_law",
            {"type": "accessibility_law", "level": "caution", "summary": "", "articles": [], "recommendation": ""},
        ),
        _batch_map.get(
            "sewage_law",
            {"type": "sewage_law", "level": "caution", "summary": "", "articles": [], "recommendation": ""},
        ),
        _batch_map.get(
            "fair_trade_law",
            {"type": "fair_trade_law", "level": "caution", "summary": "", "articles": [], "recommendation": ""},
        ),
    ]

    # overall_level: danger 하나라도 있으면 danger, caution 있으면 caution, 전부 safe면 safe
    levels = [r.get("level", "caution") for r in risks if isinstance(r, dict)]
    if "danger" in levels:
        overall_level = "danger"
    elif "caution" in levels:
        overall_level = "caution"
    else:
        overall_level = "safe"

    precedents = franchise_prec + lease_prec + food_prec + safety_prec + building_prec + labor_prec
    legal_info = (legal_info_docs + precedents) or [
        {"content": r["summary"], "metadata": {"source": r["type"], "relevance": 1.0}} for r in risks
    ]

    analysis = dict(state.get("analysis_results") or {})
    analysis["legal_risks"] = risks
    analysis["overall_legal_risk"] = overall_level

    # Redis 캐시 저장 — overall_legal_risk 포함
    # finally 블록으로 파이프라인 중간 exception 시에도 반드시 연결 종료
    try:
        if _redis is not None:
            await _redis.set(
                cache_key,
                json.dumps(
                    {"legal_risks": risks, "legal_info": legal_info, "overall_legal_risk": overall_level},
                    ensure_ascii=False,
                ),
                ex=_CACHE_TTL,
            )
            print(f"[legal_node] 캐시 저장: {cache_key} (TTL: {_CACHE_TTL}s)")
    except Exception as e:
        print(f"[legal_node] Redis 캐시 저장 실패 (무시하고 계속): {e}")
    finally:
        if _redis is not None:
            try:
                await _redis.aclose()
            except Exception:
                pass

    return {**state, "analysis_results": analysis, "legal_info": legal_info, "overall_legal_risk": overall_level}


async def legal_node(state) -> dict:
    """
    법규검토 Agent 메인 노드 — LangGraph에서 호출되는 진입점.

    2단계 풀 파이프라인(_run_legal_pipeline)을 직접 await로 실행.
    Pydantic AgentState / TypedDict AgentState 양쪽 모두 지원.

    파이프라인:
      Phase 1: RAG×13 + 판례×4 + FTC API + zoning 병렬 (총 18개 I/O)
      Phase 2: LLM check×12 병렬
    """
    if not isinstance(state, dict):
        state = state.model_dump()
    return await _run_legal_pipeline(state)
