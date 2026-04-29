"""D 모델 production naive baseline 단위 테스트.

학술 평가 결과 (6 라운드 fail) 후 production endpoint 가 naive baseline 으로
교체되었음을 검증. 기존 backend 호출부 (predict_peak) 와 시그니처 호환 확인.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUARTERLY_CSV = PROJECT_ROOT / "data" / "processed" / "living_pop_quarterly.csv"

pytestmark = pytest.mark.skipif(
    not QUARTERLY_CSV.exists(),
    reason=f"{QUARTERLY_CSV} 캐시가 필요. data_prep 으로 먼저 생성하세요.",
)


def _reset_caches() -> None:
    """모듈 레벨 DataFrame 캐시 초기화 (테스트 격리용)."""
    from models.living_pop_forecast import predict_naive

    predict_naive._DF_CACHE.clear()


def test_predict_naive_lag1_returns_previous_quarter():
    """target_quarter 의 직전 분기 (dong_code, time_zone) 평균 인구 반환."""
    _reset_caches()
    from models.living_pop_forecast.predict_naive import predict_naive_lag1

    df = pd.read_csv(QUARTERLY_CSV, dtype={"dong_code": str})
    df = df.sort_values("quarter")

    # 서교동 (11440660) tz=12 의 가장 최근 분기와 직전 분기를 직접 추출
    sub = df[(df["dong_code"] == "11440660") & (df["time_zone"] == 12)].sort_values("quarter")
    assert len(sub) >= 2, "테스트 픽스처: 최소 2 분기 필요"
    target_quarter = int(sub["quarter"].iloc[-1])
    expected_prev_value = float(sub["total_avg_pop"].iloc[-2])

    result = predict_naive_lag1(
        "11440660",
        time_zone=12,
        target_quarter=target_quarter,
        csv_path=str(QUARTERLY_CSV),
    )
    assert result == pytest.approx(expected_prev_value, rel=1e-6)


def test_predict_naive_lag1_default_target_uses_latest():
    """target_quarter=None 시 가장 최근 분기 값을 그대로 반환 (production 사용 패턴)."""
    _reset_caches()
    from models.living_pop_forecast.predict_naive import predict_naive_lag1

    df = pd.read_csv(QUARTERLY_CSV, dtype={"dong_code": str})
    sub = df[(df["dong_code"] == "11440660") & (df["time_zone"] == 0)].sort_values("quarter")
    expected = float(sub["total_avg_pop"].iloc[-1])

    result = predict_naive_lag1("11440660", time_zone=0, csv_path=str(QUARTERLY_CSV))
    assert result == pytest.approx(expected, rel=1e-6)


def test_predict_naive_lag1_invalid_time_zone_raises():
    """time_zone 0~23 범위 밖이면 ValueError."""
    _reset_caches()
    from models.living_pop_forecast.predict_naive import predict_naive_lag1

    with pytest.raises(ValueError, match="time_zone"):
        predict_naive_lag1("11440660", time_zone=24, csv_path=str(QUARTERLY_CSV))


def test_predict_peak_naive_returns_24_hours():
    """24 시간대 모두 포함."""
    _reset_caches()
    from models.living_pop_forecast.predict_naive import predict_peak_naive

    result = predict_peak_naive("서교동", n_quarters=4, csv_path=str(QUARTERLY_CSV))

    assert len(result) == 4
    for q in result:
        assert "quarter_offset" in q
        assert "peak_time_zone" in q
        assert "peak_pop" in q
        assert "all_hours" in q
        # 24 시간대 전부 (학습 데이터 결손 없는 마포 16동 기준)
        time_zones = sorted({h["time_zone"] for h in q["all_hours"]})
        assert time_zones == list(range(24)), f"24h 누락: {time_zones}"


def test_predict_peak_naive_signature_compat():
    """predict_peak() 기존 시그니처 (dong_name, n_quarters) 와 호환."""
    from models.living_pop_forecast.predict_naive import predict_peak_naive

    params = list(inspect.signature(predict_peak_naive).parameters.keys())
    # backend 가 predict_peak(dong_name, n_quarters=4) 를 호출하므로 두 인자가 앞에 있어야 함
    assert params[0] == "dong_name"
    assert "n_quarters" in params


def test_predict_peak_accepts_dong_name_or_code():
    """backward compat: dong_name 과 dong_code 둘 다 입력 가능."""
    _reset_caches()
    from models.living_pop_forecast.predict_naive import predict_peak_naive

    by_name = predict_peak_naive("서교동", n_quarters=1, csv_path=str(QUARTERLY_CSV))
    by_code = predict_peak_naive("11440660", n_quarters=1, csv_path=str(QUARTERLY_CSV))

    assert by_name[0]["peak_pop"] == by_code[0]["peak_pop"]
    assert by_name[0]["peak_time_zone"] == by_code[0]["peak_time_zone"]


def test_predict_peak_naive_unknown_dong_raises():
    """16동 외 입력 시 명확한 ValueError."""
    _reset_caches()
    from models.living_pop_forecast.predict_naive import predict_peak_naive

    with pytest.raises(ValueError, match="데이터 없음"):
        predict_peak_naive("강남동", n_quarters=4, csv_path=str(QUARTERLY_CSV))


def test_predict_peak_naive_quarters_repeat_lag1_pattern():
    """naive lag-1 정의: 모든 미래 분기가 직전 분기와 동일한 24h 패턴."""
    _reset_caches()
    from models.living_pop_forecast.predict_naive import predict_peak_naive

    result = predict_peak_naive("합정동", n_quarters=4, csv_path=str(QUARTERLY_CSV))
    # 모든 분기가 동일 peak 값/시간대
    peak_pops = {q["peak_pop"] for q in result}
    peak_tzs = {q["peak_time_zone"] for q in result}
    assert len(peak_pops) == 1, f"naive lag-1 은 분기별 동일해야 함: {peak_pops}"
    assert len(peak_tzs) == 1


def test_predict_peak_via_legacy_entrypoint_uses_naive():
    """models.living_pop_forecast.predict.predict_peak 가 naive 로 위임되어 정상 동작."""
    _reset_caches()
    from models.living_pop_forecast.predict import predict_peak

    result = predict_peak("서교동", n_quarters=2, config={"csv_path": str(QUARTERLY_CSV)})
    assert len(result) == 2
    for q in result:
        assert {"quarter_offset", "peak_time_zone", "peak_pop", "all_hours"} <= q.keys()
        assert len(q["all_hours"]) == 24


def test_predict_peak_naive_invalid_n_quarters_raises():
    """n_quarters < 1 일 때 ValueError."""
    _reset_caches()
    from models.living_pop_forecast.predict_naive import predict_peak_naive

    with pytest.raises(ValueError, match="n_quarters"):
        predict_peak_naive("서교동", n_quarters=0, csv_path=str(QUARTERLY_CSV))


def test_previous_quarter_year_rollover():
    """yyyyq 인코딩 분기 - 1: 20251 → 20244, 20253 → 20252."""
    from models.living_pop_forecast.predict_naive import _previous_quarter

    assert _previous_quarter(20253) == 20252
    assert _previous_quarter(20251) == 20244
    assert _previous_quarter(20261) == 20254
