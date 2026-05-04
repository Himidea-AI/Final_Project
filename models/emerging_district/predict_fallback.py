"""E 모델 production endpoint — 4-tier fallback + 4-class classifier.

Tier 1: change_ix 직접 (서울시 공식 stage, 가장 신뢰)
Tier 1.5: 4-class change_ix classifier (features 기반 예측 — change_ix 미발표 분기 시)
Tier 2: B1 trend baseline (subway_growth + migration_2030)
Tier 3: slope baseline (sales/store_count slope)
Tier 4: normal (모든 데이터 부재)

Classifier 학습 결과 (마포 한정):
- test accuracy: 0.8903
- macro F1: 0.8675
- baseline F1: 0.1912 (4.5배 우수)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TypedDict

import numpy as np
import torch
import torch.nn as nn
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
DB_URL = os.environ.get("POSTGRES_URL")


class EmergingFallbackResult(TypedDict):
    dong_code: str
    industry_code: str
    signal: str  # emerging / declining / normal
    tier: str  # change_ix / classifier / b1_trend / slope / none
    raw: dict
    summary: str


_SIGNAL_KO = {
    "emerging": "신흥 상권",
    "declining": "쇠퇴 상권",
    "normal": "안정 상권",
}


_CHANGE_IX_SIGNAL = {
    "LH": "emerging",
    "HH": "normal",
    "HL": "declining",
    "LL": "normal",
}


# ---------------------------------------------------------------------------
# Tier 1 — change_ix 직접 조회
# ---------------------------------------------------------------------------


def _lookup_change_ix(dong_code: str, target_quarter: int | None = None) -> str | None:
    if DB_URL is None:
        return None
    try:
        e = create_engine(DB_URL, isolation_level="AUTOCOMMIT")
        sql = "SELECT change_ix FROM seoul_adstrd_change_ix WHERE dong_code = :d ORDER BY quarter DESC LIMIT 1"
        with e.connect() as c:
            row = c.execute(text(sql), {"d": dong_code}).fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.warning("change_ix 조회 실패: %s", e)
        return None


# ---------------------------------------------------------------------------
# Tier 1.5 — 4-class classifier (change_ix 미발표 시 features 기반 예측)
# ---------------------------------------------------------------------------


class _ChangeIxClassifier(nn.Module):
    def __init__(self, d):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(d, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, 4),
        )

    def forward(self, x):
        return self.net(x)


_CLASSIFIER_BUNDLE: dict | None = None


def _load_classifier() -> dict | None:
    global _CLASSIFIER_BUNDLE
    if _CLASSIFIER_BUNDLE is not None:
        return _CLASSIFIER_BUNDLE
    weights_path = Path(__file__).parent / "weights" / "change_ix_classifier_mapo.pt"
    if not weights_path.exists():
        return None
    try:
        bundle = torch.load(weights_path, map_location="cpu", weights_only=False)
        model = _ChangeIxClassifier(len(bundle["feat_cols"]))
        model.load_state_dict(bundle["state_dict"])
        model.eval()
        bundle["model"] = model
        _CLASSIFIER_BUNDLE = bundle
        return bundle
    except Exception as e:
        logger.warning("classifier 로드 실패: %s", e)
        return None


def _classifier_predict(dong_code: str, industry_code: str) -> tuple[str, float] | None:
    """4-class classifier 로 change_ix stage 예측.

    Returns
    -------
    tuple[str, float] | None
        (예측 stage HH/HL/LH/LL, 최대 softmax 확률) 또는 None.
    """
    bundle = _load_classifier()
    if bundle is None:
        return None
    try:
        from models.emerging_district.data_prep import load_emerging_data

        df = load_emerging_data(dong_prefix=dong_code[:5])
        g = df[(df["dong_code"] == dong_code) & (df["industry_code"] == industry_code)]
        if g.empty:
            return None
        latest = g.sort_values("quarter").tail(1).iloc[0]

        feat_cols = bundle["feat_cols"]
        base_features = bundle["base_features"]
        mapo_dongs = bundle["mapo_dongs"]
        scaler_mean = np.array(bundle["scaler_mean"], dtype=np.float32)
        scaler_scale = np.array(bundle["scaler_scale"], dtype=np.float32)

        x = np.zeros(len(feat_cols), dtype=np.float32)
        for i, c in enumerate(base_features):
            x[i] = float(latest.get(c, 0.0) or 0.0)
        x[: len(base_features)] = (x[: len(base_features)] - scaler_mean) / scaler_scale
        if dong_code in mapo_dongs:
            x[len(base_features) + mapo_dongs.index(dong_code)] = 1.0
        else:
            return None  # 마포 외 동 미지원

        with torch.no_grad():
            logits = bundle["model"](torch.from_numpy(x).unsqueeze(0))
            probs = torch.softmax(logits, dim=1).squeeze(0).numpy()
        cls_idx = int(probs.argmax())
        return bundle["classes"][cls_idx], float(probs[cls_idx])
    except Exception as e:
        logger.warning("classifier 추론 실패: %s", e)
        return None


# ---------------------------------------------------------------------------
# Tier 2 — B1 trend baseline
# ---------------------------------------------------------------------------


def _lookup_b1_trend(dong_code: str) -> dict | None:
    if DB_URL is None:
        return None
    try:
        from validation.experiments.emerging_district.b1_signal_strength import (
            compute_subway_quarterly_growth,
            load_migration_2030,
            load_subway_quarterly,
        )

        sub = compute_subway_quarterly_growth(load_subway_quarterly(dong_code[:5]))
        sub_recent = sub[sub["dong_code"] == dong_code].sort_values("quarter").tail(1)
        mig = load_migration_2030(dong_code[:5])
        mig_recent = mig[mig["dong_code"] == dong_code].sort_values("quarter").tail(1)

        if sub_recent.empty and mig_recent.empty:
            return None
        return {
            "subway_growth": float(sub_recent["growth"].iloc[0]) if not sub_recent.empty else 0.0,
            "migration_2030_rate": float(mig_recent["in_2030_rate"].iloc[0]) if not mig_recent.empty else 0.0,
        }
    except Exception as e:
        logger.warning("B1 trend 조회 실패: %s", e)
        return None


def _b1_trend_to_signal(trend: dict) -> str:
    sg = trend.get("subway_growth", 0.0)
    mr = trend.get("migration_2030_rate", 0.0)
    if sg > 0.05 and mr > 0:
        return "emerging"
    if sg < -0.05:
        return "declining"
    return "normal"


# ---------------------------------------------------------------------------
# Tier 3 — slope baseline
# ---------------------------------------------------------------------------


def _lookup_slope(dong_code: str, industry_code: str) -> dict | None:
    if DB_URL is None:
        return None
    try:
        from models.emerging_district.data_prep import load_emerging_data

        df = load_emerging_data(dong_prefix=dong_code[:5])
        g = df[(df["dong_code"] == dong_code) & (df["industry_code"] == industry_code)].sort_values("quarter").tail(3)
        if len(g) < 3:
            return None
        x = np.arange(3, dtype=float)
        return {
            "sales_slope": float(np.polyfit(x, g["monthly_sales"].values.astype(float), 1)[0]),
            "store_slope": float(np.polyfit(x, g["store_count"].values.astype(float), 1)[0]),
        }
    except Exception as e:
        logger.warning("slope 조회 실패: %s", e)
        return None


def _slope_verb(value: float) -> str:
    """slope 부호별 사용자 친화 한국어 동사. 임계 0.5는 frontend chip 부호와 동일."""
    if value > 0.5:
        return "상승"
    if value < -0.5:
        return "하락"
    return "유지"


def _slope_to_signal(slope: dict) -> str:
    ss = slope.get("sales_slope", 0.0)
    sts = slope.get("store_slope", 0.0)
    if ss > 0 and sts >= 0:
        return "emerging"
    if ss < 0 or sts < 0:
        return "declining"
    return "normal"


# ---------------------------------------------------------------------------
# Production endpoint
# ---------------------------------------------------------------------------


def predict_emerging_4tier(dong_code: str, industry_code: str) -> EmergingFallbackResult:
    """4-tier fallback predict — change_ix → classifier → B1 → slope → normal."""
    # Tier 1: change_ix 직접
    cix = _lookup_change_ix(dong_code)
    if cix is not None:
        signal = _CHANGE_IX_SIGNAL.get(cix, "normal")
        return EmergingFallbackResult(
            dong_code=dong_code,
            industry_code=industry_code,
            signal=signal,
            tier="change_ix",
            raw={"change_ix": cix},
            summary=f"서울시 상권변화지표 기준 — {_SIGNAL_KO[signal]}",
        )

    # Tier 1.5: classifier 예측
    cls_result = _classifier_predict(dong_code, industry_code)
    if cls_result is not None:
        cls_stage, prob = cls_result
        signal = _CHANGE_IX_SIGNAL.get(cls_stage, "normal")
        return EmergingFallbackResult(
            dong_code=dong_code,
            industry_code=industry_code,
            signal=signal,
            tier="classifier",
            raw={"predicted_stage": cls_stage, "confidence": round(prob, 4)},
            summary=f"AI 모델 판정 — {_SIGNAL_KO[signal]} (신뢰도 {prob * 100:.0f}%)",
        )

    # Tier 2: B1 trend
    b1 = _lookup_b1_trend(dong_code)
    if b1 is not None:
        signal = _b1_trend_to_signal(b1)
        return EmergingFallbackResult(
            dong_code=dong_code,
            industry_code=industry_code,
            signal=signal,
            tier="b1_trend",
            raw=b1,
            summary=(
                f"지하철 {b1['subway_growth']:+.1%} · "
                f"20·30대 유입 {b1['migration_2030_rate']:+.1%} — "
                f"{_SIGNAL_KO[signal]} 신호"
            ),
        )

    # Tier 3: slope
    slope = _lookup_slope(dong_code, industry_code)
    if slope is not None:
        signal = _slope_to_signal(slope)
        sales_verb = _slope_verb(slope["sales_slope"])
        store_verb = _slope_verb(slope["store_slope"])
        return EmergingFallbackResult(
            dong_code=dong_code,
            industry_code=industry_code,
            signal=signal,
            tier="slope",
            raw=slope,
            summary=(f"최근 3분기 매출 {sales_verb} · 점포수 {store_verb} — {_SIGNAL_KO[signal]} 신호"),
        )

    # Tier 4: 모든 데이터 부재
    return EmergingFallbackResult(
        dong_code=dong_code,
        industry_code=industry_code,
        signal="normal",
        tier="none",
        raw={},
        summary="데이터 검증 중 — 안정 상권으로 가정",
    )
