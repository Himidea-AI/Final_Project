"""models/living_pop_forecast/arima_baseline.py 단위 테스트."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PMDARIMA_AVAILABLE = importlib.util.find_spec("pmdarima") is not None

if not PMDARIMA_AVAILABLE:
    pytest.skip("pmdarima 미설치 — ARIMA 베이스라인 테스트 건너뜀", allow_module_level=True)

from models.living_pop_forecast.arima_baseline import (  # noqa: E402
    _fit_single_group,
    fit_arima_per_group,
    forecast_arima,
    load_arima_models,
    run_train,
    save_arima_models,
)

# ---------------------------------------------------------------------------
# 합성 데이터 헬퍼
# ---------------------------------------------------------------------------


def _make_ar1_series(n: int = 60, phi: float = 0.7, sigma: float = 1.0, seed: int = 42) -> np.ndarray:
    """AR(1) 합성 시계열: y_t = phi * y_{t-1} + eps."""
    rng = np.random.default_rng(seed)
    y = np.zeros(n, dtype=float)
    for t in range(1, n):
        y[t] = phi * y[t - 1] + rng.normal(0.0, sigma)
    return y + 100.0  # 상수 offset 추가 (양수)


def _make_synthetic_df(n_dong: int = 2, n_tz: int = 2, n_quarters: int = 24, seed: int = 0) -> pd.DataFrame:
    """미니 DataFrame: dong × time_zone × quarter 격자."""
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    for d_idx in range(n_dong):
        dong = f"1144055{d_idx}"
        for tz in range(n_tz):
            level = 1000 + 500 * d_idx + 200 * tz
            series = _make_ar1_series(n=n_quarters, phi=0.6, sigma=20.0, seed=seed + d_idx * 10 + tz)
            series = series + level
            for q_idx in range(n_quarters):
                year = 2019 + q_idx // 4
                quarter_num = (q_idx % 4) + 1
                quarter_code = year * 10 + quarter_num
                rows.append(
                    {
                        "quarter": int(quarter_code),
                        "dong_code": dong,
                        "dong_name": f"테스트동{d_idx}",
                        "time_zone": int(tz),
                        "total_avg_pop": float(series[q_idx] + rng.normal(0, 5)),
                        "weekday_avg_pop": float(series[q_idx]),
                        "weekend_avg_pop": float(series[q_idx]),
                    }
                )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------


def test_fit_arima_synthetic_ar1():
    """AR(1) 합성 데이터에 auto_arima fit 후 forecast 가 합리적."""
    series = _make_ar1_series(n=80, phi=0.7, seed=1)
    model = _fit_single_group(series, seasonal=False, m=1)
    assert model is not None, "AR(1) 시계열 fit 실패"
    forecast = model.predict(n_periods=4)
    assert forecast.shape == (4,)
    # 학습 데이터 평균 부근에서 크게 벗어나지 않아야 함 (반환 형태 확인)
    train_mean = float(np.mean(series))
    train_std = float(np.std(series))
    assert np.all(np.abs(np.asarray(forecast) - train_mean) < 5 * (train_std + 1.0)), (
        "forecast 가 학습 분포에서 비정상적으로 벗어남"
    )


def test_fit_arima_constant_series_returns_none():
    """분산 0 인 상수 시계열은 None 반환."""
    series = np.full(20, 100.0, dtype=float)
    model = _fit_single_group(series, seasonal=False, m=1)
    assert model is None


def test_forecast_unknown_group_returns_none():
    """학습 안 된 그룹 forecast 시 None."""
    df = _make_synthetic_df(n_dong=2, n_tz=2, n_quarters=20)
    models = fit_arima_per_group(df, seasonal=False, progress_every=0)
    # 학습 안 된 임의 키
    result = forecast_arima(models, dong_code="99999999", time_zone=99, n_steps=4)
    assert result is None


def test_forecast_shape_for_known_group():
    """학습된 그룹 forecast shape 검증."""
    df = _make_synthetic_df(n_dong=2, n_tz=2, n_quarters=24)
    models = fit_arima_per_group(df, seasonal=False, progress_every=0)
    assert len(models) > 0
    (dong, tz) = next(iter(models.keys()))
    out = forecast_arima(models, dong_code=dong, time_zone=tz, n_steps=4)
    assert out is not None
    assert out.shape == (4,)
    assert np.isfinite(out).all()


def test_save_load_round_trip(tmp_path: Path):
    """pickle 저장/로드 후 같은 forecast 재현."""
    df = _make_synthetic_df(n_dong=2, n_tz=2, n_quarters=20)
    models = fit_arima_per_group(df, seasonal=False, progress_every=0)
    assert models, "최소 1 개 그룹 fit 필요"
    path = tmp_path / "arima_test.pkl"
    save_arima_models(models, path)
    assert path.exists()

    reloaded = load_arima_models(path)
    assert set(reloaded.keys()) == set(models.keys())

    # forecast 동일성
    (dong, tz) = next(iter(models.keys()))
    a = forecast_arima(models, dong, tz, n_steps=4)
    b = forecast_arima(reloaded, dong, tz, n_steps=4)
    assert a is not None and b is not None
    np.testing.assert_allclose(a, b, atol=1e-9)


def test_fit_arima_per_group_reports_progress(caplog):
    """progress logging 동작 확인 (50 그룹마다)."""
    df = _make_synthetic_df(n_dong=2, n_tz=2, n_quarters=20)
    # 4 그룹 — progress_every=2 로 강제
    with caplog.at_level("INFO", logger="models.living_pop_forecast.arima_baseline"):
        fit_arima_per_group(df, seasonal=False, progress_every=2)
    msgs = [rec.message for rec in caplog.records]
    assert any("ARIMA fit 진행" in m for m in msgs) or any("ARIMA fit 완료" in m for m in msgs)


def test_main_train_smoke(monkeypatch, tmp_path: Path):
    """run_train 진입점이 mini DataFrame 으로 동작 + weights 파일 생성."""
    df = _make_synthetic_df(n_dong=2, n_tz=2, n_quarters=20)
    csv_path = tmp_path / "mini_living_pop.csv"
    df.to_csv(csv_path, index=False)

    # MAPO_DONG_CODES 필터를 우회하기 위해 _make_synthetic_df 의 dong_code 와 일치시키기
    from models.living_pop_forecast import arima_baseline as ab

    # 현재 합성 dong_code: 11440550, 11440551 — MAPO 16동 prefix 와 다르므로 monkeypatch
    monkeypatch.setattr(ab, "MAPO_DONG_CODES", tuple(df["dong_code"].unique().tolist()))

    save_path = tmp_path / "arima_smoke.pkl"
    result = run_train(csv_path=csv_path, save_path=save_path, seasonal=False, m=1)
    assert save_path.exists()
    assert result["n_groups_fit"] >= 1
    assert result["save_path"] == str(save_path)
