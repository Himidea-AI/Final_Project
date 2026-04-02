"""
경쟁분석 Agent — 직접경쟁 + 카니발리제이션 + 간접경쟁(대체재) 분석

3가지 레이어의 경쟁을 분석:
  Layer 1 (직접경쟁): 동일 업종 매장 수 및 거리
  Layer 2 (카니발리제이션): 동일 브랜드 기존 매장과의 영향권 중첩
  Layer 3 (간접경쟁): 대체재 카테고리 매장 (배달 야식 등)
"""
from src.agents.state import AgentState
from src.config.constants import COMPETITION_WEIGHTS, COMPETITION_RADIUS


def analyze_direct_competition(state: AgentState) -> dict:
    """
    직접 경쟁 분석 — 동일 업종 매장과의 경쟁 밀도 계산

    Returns:
        dict: 반경별 동일 업종 매장 수, 포화도 지수
    """
    # TODO: 소상공인 API에서 동일 업종 매장 데이터 조회
    # TODO: 반경 500m / 1km / 1.5km별 매장 수 계산
    # TODO: 포화도 = 점포 수 / 유동인구 * 10000
    pass


def analyze_cannibalization(state: AgentState) -> dict:
    """
    카니발리제이션(자기 잠식) 분석 — 동일 브랜드 기존 매장과의 매출 잠식률 계산

    Returns:
        dict: 기존 매장별 잠식률, 본사 순증 매출
    """
    # TODO: 기존 매장과 후보지 간 거리 계산
    # TODO: 영향권 중첩도 산출 (500m 이내 → 높은 잠식, 1.5km 이상 → 독립)
    # TODO: 기존 매장별 예상 매출 감소율 계산
    # TODO: 본사 순증 매출 = 신규 매장 매출 - Σ(기존 매장 잠식분)
    pass


def analyze_indirect_competition(state: AgentState) -> dict:
    """
    간접 경쟁 분석 — 대체재 카테고리와의 소비 예산 경쟁

    치킨집의 경쟁상대 = 다른 치킨집 + 피자/족발/중식 등 배달 야식 전체

    Returns:
        dict: 간접 경쟁 압력 지수, 카테고리별 점포 수
    """
    # TODO: 반경 내 대체재 카테고리 매장 수 조회
    # TODO: 가중치 적용: 직접(1.0), 간접(0.5), 전체 음식점(0.2)
    # TODO: 경쟁 압력 지수 = Σ(매장 수 × 가중치)
    pass


def competition_node(state: AgentState) -> AgentState:
    """
    경쟁분석 Agent 메인 노드 — LangGraph에서 호출되는 진입점

    직접경쟁 + 카니발리제이션 + 간접경쟁을 종합하여 state에 결과 추가
    """
    # TODO: 3가지 분석 실행 후 state.analysis_results에 반영
    pass
