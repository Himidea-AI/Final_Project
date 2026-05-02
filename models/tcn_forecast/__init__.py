"""
TCN 시계열 예측 모델 패키지

LSTM/GRU 대비 TCN 구조 사용:
- 팽창 인과 컨볼루션(Dilated Causal Convolution)으로 시퀀스 처리
- 병렬 연산 가능 → 순환 신경망보다 학습 속도 빠름
- Residual connection으로 기울기 소실 방지
- window_size=4 기준 dilation=[1,2], kernel_size=2 → receptive field=4 정확히 일치

담당: B2 — 수지니
참조: models/lstm_forecast/ (data_prep 재사용), models/gru_forecast/ (구조 참조)
"""

from models.tcn_forecast import predict  # noqa: F401 — 모듈 자체 노출 (테스트 호환)
from models.tcn_forecast.predict import predict as predict_fn

__all__ = ["predict", "predict_fn"]
