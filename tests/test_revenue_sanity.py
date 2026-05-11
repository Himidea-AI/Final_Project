"""
점포당 매출 단위 회귀 테스트

배경: 2026-05-04 연남×치킨 점포당 월 매출 357만(분기 1,070만) 비현실 사건.
원인: `_get_latest_store_count`가 `max(store_count, franchise_count, 1)` 보정으로
       franchise_count(데이터 오류)를 분모로 선택해 점포당 매출이 ~3.5배 작게 산출.
재발 방지: store_count 우선 + 점포당 분기 매출 합리성 검증.

검증 항목:
  1. _get_latest_store_count: store_count > 0 이면 store_count 사용 (franchise 무시)
  2. _get_latest_store_count: store_count == 0 또는 결측 시 franchise_count fallback
  3. _get_latest_store_count: 둘 다 0 / 결측이면 1 floor
  4. _run_bep: 점포당 분기 매출 < 1,500만(=월 500만) 이면 결과 dict 에 sanity_warning 플래그
  5. _run_bep: 점포당 분기 매출 정상 범위([1,500만, 3억]) 이면 sanity_warning 없음

담당: B2 — 수지니
"""

from __future__ import annotations

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# _get_latest_store_count — load_store_data 를 monkeypatch 로 가짜 DF 주입
# ---------------------------------------------------------------------------


def _make_store_df(dong_code: str, industry_code: str, store_count, franchise_count) -> pd.DataFrame:
    """단일 행 store_quarterly DF — 마지막 분기 하나만."""
    return pd.DataFrame(
        [
            {
                "dong_code": dong_code,
                "industry_code": industry_code,
                "quarter": 20244,
                "store_count": store_count,
                "franchise_count": franchise_count,
            }
        ]
    )


def test_store_count_prefers_store_when_positive(monkeypatch):
    """franchise > store 라도 store_count 가 양수면 store_count 사용 (연남×치킨 회귀)."""
    from models import interface
    from models.lstm_forecast import data_prep

    monkeypatch.setattr(data_prep, "load_store_data", lambda **kw: _make_store_df("11440710", "CS100007", 2, 7))

    sc = interface._get_latest_store_count("11440710", "CS100007")
    assert sc == 2, f"store_count(2) 우선이어야 함. franchise(7) 잘못 선택: {sc}"


def test_store_count_falls_back_to_franchise_when_store_zero(monkeypatch):
    """store_count == 0 이면 franchise_count fallback (실데이터 결측 케이스)."""
    from models import interface
    from models.lstm_forecast import data_prep

    monkeypatch.setattr(data_prep, "load_store_data", lambda **kw: _make_store_df("11440660", "CS100007", 0, 5))
    sc = interface._get_latest_store_count("11440660", "CS100007")
    assert sc == 5


def test_store_count_floor_one_when_both_zero(monkeypatch):
    """둘 다 0 이면 1 floor (BEPCalculator 0 division 회피)."""
    from models import interface
    from models.lstm_forecast import data_prep

    monkeypatch.setattr(data_prep, "load_store_data", lambda **kw: _make_store_df("11440555", "CS100007", 0, 0))
    sc = interface._get_latest_store_count("11440555", "CS100007")
    assert sc == 1


def test_store_count_returns_one_when_no_data(monkeypatch):
    """동×업종 매칭 없으면 1 (예외 안 던지고 안전 fallback)."""
    from models import interface
    from models.lstm_forecast import data_prep

    monkeypatch.setattr(data_prep, "load_store_data", lambda **kw: pd.DataFrame())
    sc = interface._get_latest_store_count("11440710", "CS999999")
    assert sc == 1


# ---------------------------------------------------------------------------
# _run_bep — 점포당 분기 매출 합리성 검증
# ---------------------------------------------------------------------------


def _quarterly_predictions(per_store_quarter: float, store_count: int) -> list[dict]:
    """4분기 예측 dict 리스트 (동 전체 매출 = per_store × store_count)."""
    total = per_store_quarter * store_count
    return [
        {
            "quarter_offset": q,
            "predicted_sales": total,
            "confidence_lower": total * 0.9,
            "confidence_upper": total * 1.1,
        }
        for q in range(1, 5)
    ]


def test_run_bep_flags_unrealistic_low_per_store_revenue():
    """점포당 분기 매출 1,070만(= 월 357만, 연남×치킨 회귀값) → sanity_warning."""
    from models.interface import _run_bep

    bep = _run_bep(
        quarterly_per_store=10_700_000,
        quarterly_predictions=_quarterly_predictions(10_700_000, 7),
        industry_name="치킨전문점",
        cost_config=None,
        store_count=7,
    )
    assert bep.get("sanity_warning") is not None, "비현실적 점포당 매출 → warning 누락"
    assert "low" in bep["sanity_warning"]["reason"].lower()


def test_run_bep_no_warning_for_realistic_revenue():
    """점포당 분기 5,000만(월 1,667만, 정상 치킨집) → warning 없음."""
    from models.interface import _run_bep

    bep = _run_bep(
        quarterly_per_store=50_000_000,
        quarterly_predictions=_quarterly_predictions(50_000_000, 2),
        industry_name="치킨전문점",
        cost_config=None,
        store_count=2,
    )
    assert bep.get("sanity_warning") is None


def test_run_bep_flags_unrealistic_high_per_store_revenue():
    """점포당 분기 5억(월 1.6억, 비현실적 상한) → sanity_warning."""
    from models.interface import _run_bep

    bep = _run_bep(
        quarterly_per_store=500_000_000,
        quarterly_predictions=_quarterly_predictions(500_000_000, 1),
        industry_name="치킨전문점",
        cost_config=None,
        store_count=1,
    )
    assert bep.get("sanity_warning") is not None
    assert "high" in bep["sanity_warning"]["reason"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
