"""
LSTM 시계열 예측 모델 정의 — 12개월 매출 추이 예측 (추후 개발)
"""


class LSTMForecaster:
    """LSTM 기반 시계열 매출 예측 모델"""

    def __init__(self, input_size: int = 10, hidden_size: int = 64, num_layers: int = 2):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        # TODO: PyTorch LSTM 레이어 정의

    def forward(self, x):
        """순전파"""
        # TODO: 시퀀스 입력 → 12개월 매출 예측
        pass
