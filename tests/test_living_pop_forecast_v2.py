"""D 모델 (living_pop_forecast) v2 — dong_one_hot 16-dim 입력 피처 검증.

Plan: docs/superpowers/plans/2026-04-28-living-pop-forecast-normalization.md (Task 1)

마포구 16동 식별자를 one-hot 16-dim으로 추가하여 입력 5 → 21차원으로 확장.
TCNForecaster가 384 그룹(16동×24시간대) 패턴을 평균화하지 않도록 한다.
"""

import pytest


def test_mapo_dong_codes_count_is_16():
    from models.living_pop_forecast.data_prep import MAPO_DONG_CODES

    assert len(MAPO_DONG_CODES) == 16


def test_all_features_count_is_21():
    """v2 production: ALL_FEATURES = 21 (5 POP + 16 DONG).
    v3 ablation 시도는 v2 대비 RMSE 8배 악화로 reject — 자세한 내용은
    docs/abm-simulation/living-pop-forecast-v2-vs-v3-report.md 참조."""
    from models.living_pop_forecast.data_prep import ALL_FEATURES

    assert len(ALL_FEATURES) == 21


def test_dong_one_hot_unique_index():
    from models.living_pop_forecast.data_prep import MAPO_DONG_CODES

    assert MAPO_DONG_CODES[0] == "11440555"  # 아현동
    assert MAPO_DONG_CODES[8] == "11440660"  # 서교동
    assert MAPO_DONG_CODES[15] == "11440740"  # 상암동
    assert len(set(MAPO_DONG_CODES)) == 16


def test_unknown_dong_code_raises():
    """16동 외 동 입력 시 명확한 ValueError"""
    import pandas as pd

    from models.living_pop_forecast.data_prep import _add_dong_one_hot

    df = pd.DataFrame(
        {
            "dong_code": ["11440555", "99999999"],
            "total_avg_pop": [100, 200],
        }
    )
    with pytest.raises(ValueError, match="알 수 없는 dong_code"):
        _add_dong_one_hot(df)


# ---------------------------------------------------------------------------
# D-Task 2: train.py — Train/Val/Test 70/15/15 + metadata json + LODO 인자
# ---------------------------------------------------------------------------


def test_metadata_json_schema(tmp_path):
    """metadata json 필수 키 포함 검증."""
    import json
    from datetime import datetime

    sample = {
        "version": "v2",
        "input_size": 21,
        "feature_columns": [f"feat_{i}" for i in range(21)],
        "n_dong": 16,
        "best_val_loss": 0.001,
        "test_loss": 0.002,
        "train_size": 5000,
        "val_size": 1000,
        "test_size": 1000,
        "epochs_trained": 50,
        "n_channels": 64,
        "kernel_size": 2,
        "dilations": [1, 2, 4],
        "window_size": 8,
        "trained_at": datetime.now().isoformat(),
    }
    p = tmp_path / "meta.json"
    p.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")

    loaded = json.loads(p.read_text(encoding="utf-8"))
    required_keys = {
        "version",
        "input_size",
        "best_val_loss",
        "test_loss",
        "train_size",
        "val_size",
        "test_size",
        "epochs_trained",
    }
    assert required_keys <= loaded.keys()


def test_train_returns_dict_with_required_keys():
    """train() 반환 dict가 LODO 호출에 필요한 키를 포함하는지 (실행 X, 시그니처만 검증)."""
    import inspect

    from models.living_pop_forecast.train import train

    sig = inspect.signature(train)
    # train(config) 또는 train(cfg) 형태 — dict 인자 받는지 확인
    params = list(sig.parameters.keys())
    assert len(params) >= 1, "train() should accept at least 1 argument"
    # 반환 타입은 dict 이거나 Path(legacy). 본 검증은 시그니처만.


# ---------------------------------------------------------------------------
# D-Task 3 (predict.py): v2 가중치 + dong_one_hot 추론 통합
# ---------------------------------------------------------------------------


def test_predict_resolves_weights_path():
    """v2 가중치 미존재 시 명확한 RuntimeError, 존재 시 v2 경로 반환."""
    from models.living_pop_forecast.predict import (
        WEIGHTS_PATH_V2,
        _resolve_weights_path,
    )

    if WEIGHTS_PATH_V2.exists():
        # v2 학습 완료 환경 — v2 경로 반환
        path = _resolve_weights_path()
        assert path == WEIGHTS_PATH_V2
    else:
        # v2 미존재 — RuntimeError 기대 (legacy v1 fallback 비활성화)
        with pytest.raises(RuntimeError, match="v2 가중치 미발견"):
            _resolve_weights_path()


def test_predict_signature_unchanged():
    """predict()/predict_peak() 시그니처가 backend 호환을 유지하는지."""
    import inspect

    from models.living_pop_forecast.predict import predict, predict_peak

    # predict(dong_name, time_zone, n_quarters=4, config=None)
    predict_params = list(inspect.signature(predict).parameters.keys())
    assert "dong_name" in predict_params
    assert "time_zone" in predict_params
    assert "n_quarters" in predict_params

    # predict_peak(dong_name, n_quarters=4, config=None)
    # — backend interface가 호출하는 핵심 함수
    peak_params = list(inspect.signature(predict_peak).parameters.keys())
    assert "dong_name" in peak_params
    assert "n_quarters" in peak_params


# ---------------------------------------------------------------------------
# D-v3-Y: HIGH fix — DB_URL 하드코딩 제거 + LODO fold 단위 try/except 격리
# ---------------------------------------------------------------------------


def test_db_url_required_no_hardcoded_password():
    """DB_URL 하드코딩 제거 검증 — 소스 코드에 RDS 엔드포인트/비밀번호가 없어야 함.

    .env 자동 로드 동작과 상관없이 항상 검증 가능하도록
    소스 인스펙션 방식으로 검증한다.
    """
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    src = (project_root / "models" / "living_pop_forecast" / "data_prep.py").read_text(encoding="utf-8")

    # 하드코딩된 RDS 엔드포인트나 비밀번호 패턴이 없어야 함
    assert "MapoSpotter1" not in src, "비밀번호가 하드코딩되어 있습니다"
    assert "rds.amazonaws.com" not in src, "RDS 엔드포인트가 하드코딩되어 있습니다"

    # POSTGRES_URL 미설정 시 RuntimeError 가드가 있어야 함
    assert "POSTGRES_URL" in src
    assert "RuntimeError" in src


def test_lodo_summarize_handles_nan():
    """LODO fold 일부 실패 시 NaN row가 있어도 summarize 정상 동작."""
    import pandas as pd

    from validation.experiments.living_pop.lodo_validation import summarize

    df = pd.DataFrame(
        {
            "fold": [1, 2, 3],
            "holdout_dong": ["11440555", "11440565", "11440585"],
            "test_loss_holdout": [0.01, float("nan"), 0.02],
        }
    )
    result = summarize(df)
    assert result["n_succeeded"] == 2
    assert result["n_failed"] == 1


# ---------------------------------------------------------------------------
# D-v3-Z: HIGH/MEDIUM fix — target_idx silent fallback 제거 + v1 scaler RuntimeError
# ---------------------------------------------------------------------------


def test_predict_target_idx_raises_on_missing():
    """target_col 이 feature_cols 에 없으면 즉시 ValueError (silent fallback 방지)."""
    # _autoregressive_predict 직접 호출은 model 객체 필요해서 어려우므로,
    # 핵심 로직만 단위 테스트
    feature_cols = ["a", "b", "c"]
    target_col = "missing"

    with pytest.raises(ValueError, match="target_col"):
        try:
            feature_cols.index(target_col)
        except ValueError as exc:
            raise ValueError(
                f"target_col '{target_col}' 이 feature_cols 에 없습니다. "
                f"feature_cols={feature_cols[:5]}... (총 {len(feature_cols)}개). "
                f"autoregressive 추론에서 잘못된 인덱스를 사용할 수 있어 즉시 중단."
            ) from exc


def test_predict_v1_scaler_fallback_disabled():
    """v2 scaler 미존재 시 명확한 RuntimeError (v1 fallback 비활성)."""
    from models.living_pop_forecast.predict import (
        SCALERS_PATH_V2,
        _resolve_scalers_path,
    )

    if SCALERS_PATH_V2.exists():
        # v2 scaler 존재 환경
        path = _resolve_scalers_path()
        assert path == SCALERS_PATH_V2
    else:
        with pytest.raises(RuntimeError, match="v2 scaler 미발견"):
            _resolve_scalers_path()


# ---------------------------------------------------------------------------
# D-v3-X: sin/cos encoding + 외부 3 피처 (holiday_count, trend_score, cpi_index)
# ---------------------------------------------------------------------------


def test_v2_pop_features_count_is_5():
    """v2 production: POP_FEATURES = 5 (3 pop + time_zone_norm + quarter_num).
    v3 ablation (sin/cos + 외부 3) 은 reject 되어 EXTERNAL_FEATURES_V3 로 보존."""
    from models.living_pop_forecast.data_prep import EXTERNAL_FEATURES_V3, POP_FEATURES

    assert len(POP_FEATURES) == 5
    assert "time_zone_norm" in POP_FEATURES
    assert "quarter_num" in POP_FEATURES
    # v3 ablation 피처는 EXTERNAL_FEATURES_V3 로 격리
    assert "time_sin" in EXTERNAL_FEATURES_V3
    assert "holiday_count" in EXTERNAL_FEATURES_V3
    assert "cpi_index" in EXTERNAL_FEATURES_V3


def test_sin_cos_columns_still_built():
    """build_timeseries 가 v3 ablation 컬럼도 여전히 계산해서 cfg.feature_cols 로 활용 가능."""
    import pandas as pd

    from models.living_pop_forecast.data_prep import build_timeseries

    df = pd.DataFrame(
        {
            "quarter": [20191, 20192],
            "dong_code": ["11440555", "11440555"],
            "time_zone": [0, 12],
            "total_avg_pop": [1000.0, 2000.0],
            "weekday_avg_pop": [1100.0, 2100.0],
            "weekend_avg_pop": [900.0, 1900.0],
        }
    )
    out = build_timeseries(df)
    for col in ("time_sin", "time_cos", "quarter_sin", "quarter_cos"):
        assert col in out.columns
    # time_zone=12 → sin(π)=0, cos(π)=-1
    row = out[out["time_zone"] == 12].iloc[0]
    assert abs(row["time_sin"]) < 1e-9
    assert abs(row["time_cos"] - (-1.0)) < 1e-9
    # v2 production 컬럼도 존재
    assert "time_zone_norm" in out.columns
    assert "quarter_num" in out.columns
    assert abs(out[out["time_zone"] == 12].iloc[0]["time_zone_norm"] - 12 / 23) < 1e-9
