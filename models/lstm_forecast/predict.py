"""
LSTM 시계열 추론 함수 (추후 개발)
"""


def forecast(input_sequence: list, months: int = 12) -> list:
    """
    12개월 매출 추이 예측

    Args:
        input_sequence: 과거 매출 시계열 데이터
        months: 예측 기간 (개월)

    Returns:
        list: 월별 예측 매출 리스트
    """
    # TODO: 모델 로드
    # TODO: 시퀀스 전처리
    # TODO: 자기회귀 예측 (1개월씩 순차 예측)
    pass
