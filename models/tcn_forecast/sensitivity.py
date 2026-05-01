"""
TCN 시나리오 시뮬레이터 — 사전 배치 섭동 분석

슬라이더 5개(임대료/공실률/유동인구/트렌드/계절)에 대해
156개 (동×업종) 조합의 탄성치 테이블을 사전 계산하여 JSON으로 저장한다.

실행 방법:
    python -m models.tcn_forecast.sensitivity

저장 위치:
    models/tcn_forecast/weights/sensitivity_cache.json
    models/tcn_forecast/weights/feature_correlations.json

담당: B2 — 수지니
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

# 슬라이더명 → 실제 TCN 피처 목록 (유동인구는 3개 동시 적용)
SLIDER_FEATURES: dict[str, list[str]] = {
    "rent_1f": ["rent_1f"],
    "vacancy_rate": ["vacancy_rate"],
    "floating_pop": ["bus_flpop", "adstrd_flpop", "floating_pop"],
    "trend_score": ["trend_score"],
}

# ±% 섭동 레벨 (quarter_num 제외)
PERTURBATION_LEVELS: list[int] = [-30, -20, -10, 0, 10, 20, 30]

# quarter_num 슬라이더용 분기 값 (categorical)
QUARTER_VALUES: dict[str, int] = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

# Pearson 상관계수 계산 대상 피처 쌍
CORRELATION_PAIRS: list[tuple[str, str]] = [
    ("floating_pop", "rent_1f"),
    ("floating_pop", "vacancy_rate"),
    ("rent_1f", "vacancy_rate"),
]


# ---------------------------------------------------------------------------
# 헬퍼 함수 (단위 테스트 가능)
# ---------------------------------------------------------------------------


def get_feature_indices(feature_names: list[str], target_features: list[str]) -> list[int]:
    """feature_names 리스트에서 target_features의 인덱스를 반환한다.

    Parameters
    ----------
    feature_names : list[str]
        TCN 입력 피처 전체 목록 (ALL_FEATURES 순서).
    target_features : list[str]
        인덱스를 찾을 피처명 목록.

    Returns
    -------
    list[int]
        target_features 각각의 feature_names 내 인덱스.
        없는 피처는 무시한다.
    """
    name_to_idx = {name: i for i, name in enumerate(feature_names)}
    return [name_to_idx[f] for f in target_features if f in name_to_idx]


def compute_correlations(df: pd.DataFrame) -> dict[str, float]:
    """학습 데이터 DataFrame에서 슬라이더 피처 간 Pearson 상관계수를 계산한다.

    Parameters
    ----------
    df : pd.DataFrame
        슬라이더 피처 컬럼을 포함하는 데이터프레임.

    Returns
    -------
    dict[str, float]
        {"floating_pop→rent_1f": 0.63, ...} 형태의 상관계수 딕셔너리.
        소수점 4자리 반올림.
    """
    result: dict[str, float] = {}
    for f1, f2 in CORRELATION_PAIRS:
        if f1 in df.columns and f2 in df.columns:
            valid = df[[f1, f2]].dropna()
            if len(valid) >= 2:
                corr = valid[f1].corr(valid[f2])
                result[f"{f1}→{f2}"] = round(float(corr), 4)
    return result
