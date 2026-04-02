"""
LSTM 시계열 예측 모델 — 12개월 매출 추이 예측 (추후 개발)

과거 매출 시계열 데이터를 입력받아 향후 12개월 매출을 자기회귀 방식으로 예측.

  - model.py     : LSTM 모델 아키텍처 (PyTorch)
  - train.py     : 학습 스크립트
  - predict.py   : 자기회귀 추론 (1개월씩 순차 예측)
  - data_prep.py : 시계열 전처리 (sliding window 시퀀스 생성)

담당: F — PM / 검증 / 발표
"""
