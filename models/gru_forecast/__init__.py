"""
GRU 시계열 예측 모델 패키지

LSTM 대비 GRU 구조 사용:
- 파라미터 수 적음 → 학습 빠름
- cell state 없이 hidden state만 유지
- 동일한 Attention + FC 구조로 LSTM과 공정한 비교 가능

담당: B2 — 수지니
참조: models/lstm_forecast/ (data_prep 재사용)
"""

from models.gru_forecast.predict import predict

__all__ = ["predict"]
