"""
operational_fit_scorer 테스트

1) 순수 수학 단위 테스트 (DB 불필요)
   - Gaussian decay 경계 조건
   - min-max 정규화
   - SHAP 가중치 캘리브레이션

2) 통합 테스트 (DB 필요, pytest -m db 로 실행)
   - 마포 16동 점수 계산 완주
   - Before/After 랭킹 비교 — operfit 도입 전/후 winner 변화 탐지

담당: A2 봉환
"""

from __future__ import annotations

import asyncio
import math
import os

import pytest

from src.services.operational_fit_scorer import (
    _gaussian_decay,
    _minmax_to_100,
    calibrate_weights_from_shap,
    score_all_districts,
)


# ---------------------------------------------------------------------------
# 1. 순수 수학 단위 테스트 — DB 불필요
# ---------------------------------------------------------------------------


def test_gaussian_decay_boundary_cases() -> None:
    """E2SFCA Gaussian decay 경계 조건."""
    # d=0: 최대값 1.0
    assert _gaussian_decay(0.0) == pytest.approx(1.0, abs=1e-6)
    # d>=d0(1000m): 정확히 0
    assert _gaussian_decay(1000.0) == 0.0
    assert _gaussian_decay(2000.0) == 0.0
    # 단조 감소
    assert _gaussian_decay(100.0) > _gaussian_decay(500.0) > _gaussian_decay(900.0) > 0.0


def test_gaussian_decay_formula() -> None:
    """E2SFCA 공식 그대로인지 검증 (d=500m, d0=1000m)."""
    d, d0 = 500.0, 1000.0
    expected = (math.exp(-0.5 * (d / d0) ** 2) - math.exp(-0.5)) / (1.0 - math.exp(-0.5))
    assert _gaussian_decay(d, d0) == pytest.approx(expected, abs=1e-9)


def test_minmax_to_100_normal() -> None:
    """min-max 정규화 — floor 10, 최고 100."""
    result = _minmax_to_100({"A": 0.0, "B": 50.0, "C": 100.0}, floor=10.0)
    assert result["A"] == pytest.approx(10.0)
    assert result["C"] == pytest.approx(100.0)
    assert result["B"] == pytest.approx(55.0)  # 중간값


def test_minmax_to_100_no_variance() -> None:
    """편차 없으면 전부 50."""
    result = _minmax_to_100({"A": 7.0, "B": 7.0, "C": 7.0})
    assert all(v == 50.0 for v in result.values())


def test_minmax_to_100_empty() -> None:
    assert _minmax_to_100({}) == {}


def test_calibrate_weights_from_shap_empty() -> None:
    """shap_result 비어있으면 default 가중치(실매출 R² 기반 0.10/0.40/0.50) 반환."""
    w_sub, w_bus, w_fclty = calibrate_weights_from_shap({})
    assert (w_sub, w_bus, w_fclty) == (0.10, 0.40, 0.50)


def test_calibrate_weights_from_shap_bus_dominant() -> None:
    """bus_flpop이 유일하게 기여하면 bus에 비-subway 예산 전량 배분."""
    shap_result = {
        "feature_importance": [
            {"feature": "bus_flpop", "abs_shap": 0.05},
            {"feature": "monthly_sales", "abs_shap": 0.03},  # operfit 비관련
        ]
    }
    w_sub, w_bus, w_fclty = calibrate_weights_from_shap(shap_result, subway_prior=0.40)
    assert w_sub == 0.40
    assert w_bus == pytest.approx(0.60, abs=1e-6)  # 1 - 0.40
    assert w_fclty == pytest.approx(0.00, abs=1e-6)


def test_calibrate_weights_from_shap_bus_and_fclty() -> None:
    """bus와 fclty 피처가 같은 크기면 remaining 예산을 50:50 분배."""
    shap_result = {
        "feature_importance": [
            {"feature": "bus_flpop", "abs_shap": 0.02},
            {"feature": "floating_pop", "abs_shap": 0.01},
            {"feature": "pop_per_store_gm", "abs_shap": 0.01},
        ]
    }
    w_sub, w_bus, w_fclty = calibrate_weights_from_shap(shap_result, subway_prior=0.40)
    assert w_sub == 0.40
    # bus=0.02, fclty=0.02 → 0.60 예산 50:50 → 0.30/0.30
    assert w_bus == pytest.approx(0.30, abs=1e-6)
    assert w_fclty == pytest.approx(0.30, abs=1e-6)
    assert w_sub + w_bus + w_fclty == pytest.approx(1.0, abs=1e-6)


def test_calibrate_weights_from_shap_no_relevant_features() -> None:
    """operfit 비관련 피처만 있으면 default(R² 기반) 반환."""
    shap_result = {
        "feature_importance": [
            {"feature": "monthly_sales", "abs_shap": 0.10},
            {"feature": "rent_1f", "abs_shap": 0.05},
        ]
    }
    w_sub, w_bus, w_fclty = calibrate_weights_from_shap(shap_result)
    assert (w_sub, w_bus, w_fclty) == (0.10, 0.40, 0.50)


# ---------------------------------------------------------------------------
# 2. 통합 테스트 — DB 필요, RUN_DB_TESTS=1 환경변수에서만 실행
# ---------------------------------------------------------------------------


_DB_TESTS_ENABLED = os.environ.get("RUN_DB_TESTS", "").strip() == "1"


@pytest.mark.skipif(not _DB_TESTS_ENABLED, reason="RUN_DB_TESTS=1에서만 실행")
def test_score_all_districts_integration() -> None:
    """마포 16동 점수 계산 완주 + 분포 sanity."""
    results = asyncio.run(score_all_districts())

    assert len(results) == 16, f"16동 예상, 실제 {len(results)}동"
    for dong, r in results.items():
        assert 0.0 <= r["operational_fit_score"] <= 100.0, f"{dong} 점수 범위 이탈: {r}"
        assert 0.0 <= r["subway_sub"] <= 100.0
        assert 0.0 <= r["bus_sub"] <= 100.0
        assert 0.0 <= r["fclty_sub"] <= 100.0
        assert "evidence" in r

    scores = [r["operational_fit_score"] for r in results.values()]
    assert max(scores) - min(scores) > 5.0, "16동 점수 분포 너무 좁음 — 정규화 점검 필요"


@pytest.mark.skipif(not _DB_TESTS_ENABLED, reason="RUN_DB_TESTS=1에서만 실행")
def test_before_after_ranking_integration() -> None:
    """operfit 도입 전후 랭킹 비교 — winner·점수 변화 탐지.

    비교 방식: 같은 raw 데이터로 operfit 없이 / 있이 두 번 랭킹해 1위 동·점수 diff 기록.
    Windows cp949 콘솔 인코딩 대응으로 ASCII-only 출력 사용.
    """
    import sys

    from src.agents.nodes.district_ranking import _normalize_and_rank

    # Windows 콘솔 UTF-8 재구성 (pytest 환경에서 이모지/한글 출력 대응)
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except AttributeError:
            pass

    # 최소 raw 샘플 (실제 DB 값 아니지만 정규화 로직 검증용)
    raw = [
        {
            "district": "서강동",
            "sales_growth": 0.15,
            "pop_growth": 0.10,
            "avg_rent": 80000,
            "semas_density": 50,
            "naver_trend": 70,
        },
        {
            "district": "공덕동",
            "sales_growth": 0.12,
            "pop_growth": 0.08,
            "avg_rent": 90000,
            "semas_density": 60,
            "naver_trend": 65,
        },
        {
            "district": "상암동",
            "sales_growth": 0.08,
            "pop_growth": 0.05,
            "avg_rent": 60000,
            "semas_density": 30,
            "naver_trend": 50,
        },
    ]

    operfit_map = asyncio.run(score_all_districts())
    print("\n=== operational_fit 16-dong scores ===")
    for dong, r in sorted(operfit_map.items(), key=lambda kv: -kv[1]["operational_fit_score"]):
        print(
            f"  {dong:10s} {r['operational_fit_score']:5.1f} "
            f"(sub={r['subway_sub']:.1f} bus={r['bus_sub']:.1f} fclty={r['fclty_sub']:.1f})"
        )

    without = _normalize_and_rank(raw, population_weight=True)
    with_operfit = _normalize_and_rank(raw, population_weight=True, operfit_map=operfit_map)

    w_winner = without[0]["district"] if without else None
    o_winner = with_operfit[0]["district"] if with_operfit else None
    w_score = without[0]["score"] if without else None
    o_score = with_operfit[0]["score"] if with_operfit else None
    print("\n=== Winner comparison ===")
    print(f"  without operfit : {w_winner} (score={w_score})")
    print(f"  with    operfit : {o_winner} (score={o_score})")
    print(f"  winner changed  : {'YES' if w_winner != o_winner else 'NO (same in this sample)'}")

    # 이 테스트는 분석 로깅용 — 결과와 관계없이 성공시킴 (샘플이 작아 winner 안 바뀔 수도 있음)
    assert with_operfit, "operfit 포함 랭킹 비어있음"
