"""
법률 에이전트 시나리오 테스트 — A2 담당

이 테스트가 하는 일:
  법률 에이전트(_run_legal_pipeline)가 실제 사용자 시나리오에서
  올바른 법률 리스크를 판정하는지 검증합니다.

  실제 DB/LLM/API 없이 mock으로 실행하여, 파이프라인의 "로직"을 검증합니다:
  - 14개 법률 항목이 빠짐없이 반환되는지
  - overall_legal_risk가 올바르게 집계되는지
  - 용도지역 제한이 걸리는 엣지 케이스에서 danger가 나오는지
  - Redis 캐시 미스 시에도 정상 동작하는지

실행:
    pytest tests/test_legal_scenarios.py -v
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from src.agents.nodes.legal import _run_legal_pipeline  # noqa: E402
from src.schemas.structured_output import LegalBatchOutput, LegalRiskItem  # noqa: E402


def _make_state(
    brand: str = "이디야커피",
    district: str = "서교동",
    business_type: str = "카페",
) -> dict:
    """테스트용 AgentState dict 생성"""
    return {
        "brand_name": brand,
        "target_district": district,
        "business_type": business_type,
        "analysis_results": {},
    }


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


def _mock_batch_llm_output(all_safe: bool = False) -> LegalBatchOutput:
    """배치 LLM Structured Output mock"""
    level = "safe" if all_safe else "caution"
    return LegalBatchOutput(
        items=[
            LegalRiskItem(
                type=t, level=level, summary=f"{t} 검토 완료", recommendation="확인 필요" if not all_safe else ""
            )
            for t in _BATCH_TYPES
        ]
    )


@pytest.fixture
def mock_dependencies():
    """RAG retriever, LLM, Redis, LawApiClient, FTC 전부 mock"""
    # Redis mock 객체
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # 캐시 미스
    mock_redis.set = AsyncMock()
    mock_redis.aclose = AsyncMock()

    # redis.asyncio 모듈 mock
    mock_redis_mod = MagicMock()
    mock_redis_mod.from_url.return_value = mock_redis

    with (
        patch("src.agents.nodes.legal.LegalDocumentRetriever") as MockRetriever,
        patch("src.agents.nodes.legal.get_fast_llm") as mock_get_fast_llm,
        patch("src.agents.nodes.legal.LawApiClient") as MockLawApi,
        patch("src.agents.nodes.legal.FtcFranchiseClient"),
        patch("src.agents.nodes.legal._search_ftc_from_db", new_callable=AsyncMock, return_value=None),
        patch("src.agents.nodes.legal.settings") as mock_settings,
        patch.dict("sys.modules", {"redis.asyncio": mock_redis_mod, "redis": MagicMock()}),
    ):
        # Retriever mock: 빈 결과 반환 (RAG 로직이 아닌 파이프라인 로직을 테스트)
        mock_retriever_instance = MockRetriever.return_value
        mock_retriever_instance.search = AsyncMock(return_value=[])
        # source_filter 상수들을 원본에서 복사
        from src.chains.retriever import LegalDocumentRetriever as RealRetriever

        for attr in dir(RealRetriever):
            if attr.endswith("_SOURCES") or attr == "RELEVANCE_THRESHOLD":
                setattr(MockRetriever, attr, getattr(RealRetriever, attr))

        # LLM mock: Structured Output 반환
        # MagicMock을 사용해야 .with_structured_output() 체이닝이 coroutine이 되지 않음
        mock_llm_instance = MagicMock()
        mock_llm_instance.with_structured_output.return_value.ainvoke = AsyncMock(return_value=_mock_batch_llm_output())
        mock_get_fast_llm.return_value = mock_llm_instance

        # LawApiClient mock: 빈 판례
        mock_law_instance = MockLawApi.return_value
        mock_law_instance.search_precedents = AsyncMock(return_value=[])

        # Settings mock
        mock_settings.ftc_api_key = ""
        mock_settings.redis_url = "redis://localhost:6379/0"

        yield {
            "retriever": mock_retriever_instance,
            "llm": mock_get_fast_llm,
            "law_api": mock_law_instance,
            "redis": mock_redis,
        }


# ── 시나리오 1: 일반상업지역 + 카페 (가장 흔한 케이스) ────────────────────────


class TestScenarioCafeCommercial:
    """
    시나리오: 이디야커피를 서교동(일반상업지역)에 출점
    기대: 용도지역은 safe, 나머지는 LLM 판정에 따름
    """

    @pytest.mark.asyncio
    async def test_returns_14_legal_risks(self, mock_dependencies):
        """14개 법률 항목이 모두 반환되는지 확인."""
        state = _make_state("이디야커피", "서교동", "카페")
        result = await _run_legal_pipeline(state)

        risks = result["analysis_results"]["legal_risks"]
        assert len(risks) == 14, f"14개 항목이어야 하지만 {len(risks)}개 반환됨"

    @pytest.mark.asyncio
    async def test_risk_types_complete(self, mock_dependencies):
        """14개 법률 리스크 타입이 빠짐없이 있는지 확인."""
        state = _make_state("이디야커피", "서교동", "카페")
        result = await _run_legal_pipeline(state)

        risk_types = {r["type"] for r in result["analysis_results"]["legal_risks"]}
        expected_types = {
            "franchise_law",
            "commercial_lease_law",
            "zoning_regulation",
            "food_hygiene",
            "safety_regulation",
            "ftc_franchise",
            "building_law",
            "fire_safety_law",
            "labor_law",
            "vat_law",
            "privacy_law",
            "accessibility_law",
            "sewage_law",
            "fair_trade_law",
        }
        assert risk_types == expected_types, f"누락된 타입: {expected_types - risk_types}"

    @pytest.mark.asyncio
    async def test_zoning_safe_in_commercial(self, mock_dependencies):
        """서교동(일반상업지역)에서 카페 용도지역은 safe."""
        state = _make_state("이디야커피", "서교동", "카페")
        result = await _run_legal_pipeline(state)

        zoning = next(r for r in result["analysis_results"]["legal_risks"] if r["type"] == "zoning_regulation")
        assert zoning["level"] == "safe"
        assert zoning["zone"] == "일반상업지역"

    @pytest.mark.asyncio
    async def test_overall_risk_aggregation(self, mock_dependencies):
        """모든 항목이 caution이면 overall도 caution."""
        state = _make_state("이디야커피", "서교동", "카페")
        result = await _run_legal_pipeline(state)

        # LLM mock이 전부 caution 반환 + zoning은 safe + ftc는 caution(API키 없음)
        assert result["overall_legal_risk"] == "caution"

    @pytest.mark.asyncio
    async def test_legal_info_returned(self, mock_dependencies):
        """legal_info가 빈 리스트가 아닌 결과를 포함."""
        state = _make_state("이디야커피", "서교동", "카페")
        result = await _run_legal_pipeline(state)

        # RAG 결과가 없으면 risks의 summary로 fallback
        assert "legal_info" in result
        assert len(result["legal_info"]) > 0


# ── 시나리오 2: 주거지역 + 음식점 (용도지역 제한 엣지 케이스) ─────────────────


class TestScenarioRestaurantResidential:
    """
    시나리오: BBQ치킨을 대흥동(제2종일반주거지역)에 출점
    기대: 용도지역 → danger (음식점 제한), overall → danger
    """

    @pytest.mark.asyncio
    async def test_zoning_danger_for_restaurant(self, mock_dependencies):
        """대흥동(제2종일반주거)에서 음식점은 danger."""
        state = _make_state("BBQ", "대흥동", "음식점")
        result = await _run_legal_pipeline(state)

        zoning = next(r for r in result["analysis_results"]["legal_risks"] if r["type"] == "zoning_regulation")
        assert zoning["level"] == "danger"
        assert zoning["allowed"] is False

    @pytest.mark.asyncio
    async def test_overall_danger_when_any_danger(self, mock_dependencies):
        """하나라도 danger면 overall은 danger."""
        state = _make_state("BBQ", "대흥동", "음식점")
        result = await _run_legal_pipeline(state)

        assert result["overall_legal_risk"] == "danger"

    @pytest.mark.asyncio
    async def test_zoning_danger_recommendation(self, mock_dependencies):
        """danger인 경우 토지이음 확인 권고 메시지 포함."""
        state = _make_state("BBQ", "대흥동", "음식점")
        result = await _run_legal_pipeline(state)

        zoning = next(r for r in result["analysis_results"]["legal_risks"] if r["type"] == "zoning_regulation")
        assert "토지이음" in zoning.get("recommendation", "") or "eum.go.kr" in zoning.get("recommendation", "")


# ── 시나리오 3: 주거지역 + 카페 (경계 케이스) ────────────────────────────────


class TestScenarioCafeResidential:
    """
    시나리오: 스타벅스를 대흥동(제2종일반주거지역)에 출점
    기대: 카페는 제2종일반주거지역에서 허용 → safe
    """

    @pytest.mark.asyncio
    async def test_cafe_allowed_in_residential_2(self, mock_dependencies):
        """대흥동(제2종일반주거)에서 카페는 safe."""
        state = _make_state("스타벅스", "대흥동", "카페")
        result = await _run_legal_pipeline(state)

        zoning = next(r for r in result["analysis_results"]["legal_risks"] if r["type"] == "zoning_regulation")
        assert zoning["level"] == "safe"


# ── 시나리오 4: 제3종일반주거지역 (연남동) ────────────────────────────────────


class TestScenarioYeonnam:
    """
    시나리오: 연남동(제3종일반주거지역)은 카페/음식점/편의점 모두 허용
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("business_type", ["카페", "음식점", "편의점"])
    async def test_all_types_safe_in_yeonnam(self, mock_dependencies, business_type):
        """연남동(제3종일반주거)에서 모든 업종 safe."""
        state = _make_state("테스트브랜드", "연남동", business_type)
        result = await _run_legal_pipeline(state)

        zoning = next(r for r in result["analysis_results"]["legal_risks"] if r["type"] == "zoning_regulation")
        assert zoning["level"] == "safe"


# ── 시나리오 5: LLM 응답이 비정상인 경우 (배치 프롬프트 실패) ──────────────────


class TestScenarioLlmFailure:
    """
    시나리오: LLM Structured Output 호출이 예외 발생
    기대: 12개 항목 모두 caution으로 fallback, 에러 없이 완료
    """

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_json(self, mock_dependencies):
        """LLM ainvoke가 예외를 발생시켜도 에러 없이 처리 (Structured Output 파싱 실패 시뮬레이션)."""
        mock_dependencies["llm"].return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            side_effect=Exception("Structured Output 파싱 실패")
        )
        state = _make_state("테스트", "서교동", "카페")
        result = await _run_legal_pipeline(state)

        risks = result["analysis_results"]["legal_risks"]
        assert len(risks) == 14  # zoning + ftc + 12개 caution fallback

        # LLM 실패 시 12개 항목은 모두 caution
        llm_risks = [r for r in risks if r["type"] not in ("zoning_regulation", "ftc_franchise")]
        for r in llm_risks:
            assert r["level"] == "caution"

    @pytest.mark.asyncio
    async def test_llm_raises_exception(self, mock_dependencies):
        """LLM 호출 자체가 예외를 발생시켜도 에러 없이 처리."""
        mock_dependencies["llm"].return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            side_effect=Exception("API timeout")
        )
        state = _make_state("테스트", "서교동", "카페")
        result = await _run_legal_pipeline(state)

        risks = result["analysis_results"]["legal_risks"]
        assert len(risks) == 14

    @pytest.mark.asyncio
    async def test_llm_returns_partial_json(self, mock_dependencies):
        """LLM이 12개 중 일부만 반환해도 나머지를 caution으로 보완."""
        partial_output = LegalBatchOutput(
            items=[
                LegalRiskItem(type="franchise_law", level="safe", summary="안전", recommendation=""),
                LegalRiskItem(type="food_hygiene", level="danger", summary="위험", recommendation="확인"),
            ]
        )
        mock_dependencies["llm"].return_value.with_structured_output.return_value.ainvoke = AsyncMock(
            return_value=partial_output
        )
        state = _make_state("테스트", "서교동", "카페")
        result = await _run_legal_pipeline(state)

        risks = result["analysis_results"]["legal_risks"]
        risk_map = {r["type"]: r for r in risks}

        # 명시적으로 반환된 항목
        assert risk_map["franchise_law"]["level"] == "safe"
        assert risk_map["food_hygiene"]["level"] == "danger"

        # 누락된 항목은 caution으로 보완
        assert risk_map["labor_law"]["level"] == "caution"

        # danger가 있으므로 overall도 danger
        assert result["overall_legal_risk"] == "danger"


# ── 시나리오 6: 브랜드명 없는 경우 ───────────────────────────────────────────


class TestScenarioNoBrand:
    """
    시나리오: 브랜드명 없이 업종+지역만 있는 경우
    기대: ftc_franchise는 caution (브랜드 없어서 조회 불가), 나머지 정상
    """

    @pytest.mark.asyncio
    async def test_ftc_skipped_without_brand(self, mock_dependencies):
        """브랜드명 없으면 FTC 정보공개서 조회를 건너뜀."""
        state = _make_state(brand="", district="합정동", business_type="카페")
        result = await _run_legal_pipeline(state)

        ftc = next(r for r in result["analysis_results"]["legal_risks"] if r["type"] == "ftc_franchise")
        assert ftc["level"] == "caution"
        assert "브랜드명" in ftc["summary"] or "입력되지" in ftc["summary"]
