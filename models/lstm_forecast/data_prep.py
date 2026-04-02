"""
LSTM 시계열 데이터 전처리 (추후 개발)
"""


def prepare_sequences(data: list, window_size: int = 6) -> tuple:
    """
    시계열 데이터를 LSTM 입력 시퀀스로 변환

    Args:
        data: 시계열 데이터
        window_size: 입력 시퀀스 길이

    Returns:
        tuple: (X_sequences, y_targets)
    """
    # TODO: sliding window로 시퀀스 생성
    # TODO: 정규화
    pass
