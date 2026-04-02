"""
실제 폐점 매장 기반 백테스트 — 모델 예측의 신뢰도 검증
"""


def run_backtest(historical_closures: list, model) -> dict:
    """
    실제 폐점 데이터로 모델 백테스트

    Args:
        historical_closures: 실제 폐점 매장 데이터
        model: 예측 모델

    Returns:
        dict: 적중률, 오탐률, F1 Score
    """
    # TODO: 폐점 매장의 과거 데이터로 예측 실행
    # TODO: 예측 결과와 실제 폐점 비교
    # TODO: 정확도 지표 산출
    pass
