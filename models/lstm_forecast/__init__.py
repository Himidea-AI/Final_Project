"""
LSTM 시계열 예측 모델 -- 분기별 매출 추이 예측

사전학습(서울 전체 25개구) -> 파인튜닝(마포구) 전이학습 파이프라인.

  - model.py     : LSTMForecaster 모델 아키텍처 (PyTorch nn.Module)
  - data_prep.py : 시계열 전처리 (DB/CSV 로드, sliding window 시퀀스 생성)
  - train.py     : 사전학습(pretrain) + 파인튜닝(finetune) 학습 스크립트
  - predict.py   : 자기회귀 추론 (1분기씩 순차 예측)

담당: B2 -- 딥러닝 모델 / F -- PM

Usage:
    # 사전학습 (서울 전체)
    python -m models.lstm_forecast.train --mode pretrain

    # 파인튜닝 (마포구)
    python -m models.lstm_forecast.train --mode finetune

    # 추론
    from models.lstm_forecast import predict
    results = predict("1144053", "CS100001", n_months=4)
"""

from .data_prep import build_timeseries, prepare_dataloaders, prepare_sequences
from .model import LSTMForecaster
from .predict import forecast, predict
from .train import finetune, pretrain

__all__ = [
    "LSTMForecaster",
    "build_timeseries",
    "finetune",
    "forecast",
    "predict",
    "prepare_dataloaders",
    "prepare_sequences",
    "pretrain",
]
