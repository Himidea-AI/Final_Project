"""
생존률/폐업률 예측 모델 — LSTM 기반 시계열 예측

특정 동×업종의 점포 시계열 데이터(점포수, 폐업률, 프랜차이즈 비율 등)를
입력받아 향후 생존 확률을 예측한다.
B2(수지니)의 12개월 시뮬레이션 입력으로 활용.

  - model.py     : SurvivalPredictor (LSTM + Attention)
  - train.py     : 서울 사전학습 → 마포구 파인튜닝
  - predict.py   : predict(dong_code, industry_code) → 생존률 예측
  - data_prep.py : 시계열 전처리 (피처 엔지니어링, sliding window, 정규화)

담당: B2 — 딥러닝 모델 개발자
"""

from models.revenue_predictor.predict import predict

__all__ = ["predict"]
