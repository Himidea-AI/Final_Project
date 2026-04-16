"""
모델 설명 가능성 패키지 — SHAP 기반 예측 근거 시각화 + 시뮬레이션 변환

매출 예측 결과에 대해 어떤 피처(유동인구, 경쟁도 등)가
얼마나 기여했는지를 시각적으로 설명.

  - shap_analysis.py : SHAP 값 계산 + summary plot 생성
  - simulation.py    : BEP/TCN 결과 → 분기별·월별 시뮬레이션 변환

담당: C — 딥러닝 모델 개발자 (shap_analysis)
      B2 — 수지니 (simulation)
"""

# simulation.py의 공개 함수 노출
# — 외부에서 from models.explainability import build_quarterly_projection 형태로 사용 가능
from models.explainability.simulation import (
    build_monthly_projection,
    build_quarterly_projection,
    build_scenarios,
)
