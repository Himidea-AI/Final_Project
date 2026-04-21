"""
생활인구 시간대별 유동인구 TCN 예측 모듈 (D단계)

living_population → 마포구 16개 동 × 24시간대 분기 집계 → TCN 학습/예측

출력 예시: "합정동 내년 봄 주말 오후(14~18시) 예상 유동인구 X만명"

담당: B2 — 수지니
참조: B2_DL_model_roadmap.md D단계
"""

from .predict import predict, predict_peak

__all__ = ["predict", "predict_peak"]
