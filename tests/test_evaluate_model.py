from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def test_compute_mape_basic():
    from scripts.evaluate_model import compute_mape

    pred = np.array([1100.0, 2200.0, 3300.0, 4400.0])
    true = np.array([1000.0, 2000.0, 3000.0, 4000.0])
    assert compute_mape(pred, true) == pytest.approx(10.0)


def test_compute_mape_excludes_near_zero():
    from scripts.evaluate_model import compute_mape

    # 경계값 검증: true=999원 → 제외, true=1000원 → 포함, true=100원 → 제외
    pred = np.array([110.0, 500.0, 1100.0])
    true = np.array([100.0, 999.0, 1000.0])  # 999원 제외, 1000원 포함
    # 포함 포인트: (pred=1100, true=1000) 1개 → MAPE = 10%
    assert compute_mape(pred, true) == pytest.approx(10.0)


def test_compute_mape_all_near_zero_returns_nan():
    from scripts.evaluate_model import compute_mape

    # 999원 미만 전부 → nan
    assert np.isnan(compute_mape(np.array([500.0]), np.array([999.0])))


def test_compute_wa_mape_basic():
    from scripts.evaluate_model import compute_wa_mape

    # Σ|pred-true| / Σtrue = (100+100) / (1000+2000) * 100 = 6.667%
    pred = np.array([1100.0, 2100.0])
    true = np.array([1000.0, 2000.0])
    assert compute_wa_mape(pred, true) == pytest.approx(200.0 / 3000.0 * 100)


def test_compute_wa_mape_excludes_near_zero():
    from scripts.evaluate_model import compute_wa_mape

    # true=999 제외, true=1000만 포함 → |100|/1000 * 100 = 10%
    pred = np.array([500.0, 1100.0])
    true = np.array([999.0, 1000.0])
    assert compute_wa_mape(pred, true) == pytest.approx(10.0)


def test_compute_wa_mape_all_near_zero_returns_nan():
    from scripts.evaluate_model import compute_wa_mape

    assert np.isnan(compute_wa_mape(np.array([500.0]), np.array([999.0])))


def test_compute_mae():
    from scripts.evaluate_model import compute_mae

    assert compute_mae(np.array([110.0, 90.0]), np.array([100.0, 100.0])) == pytest.approx(10.0)


def test_compute_rmse():
    from scripts.evaluate_model import compute_rmse

    assert compute_rmse(np.array([110.0, 90.0]), np.array([100.0, 100.0])) == pytest.approx(10.0)


def test_compute_bias_positive():
    from scripts.evaluate_model import compute_bias

    assert compute_bias(np.array([110.0, 220.0]), np.array([100.0, 200.0])) == pytest.approx(15.0)


def test_compute_bias_negative():
    from scripts.evaluate_model import compute_bias

    assert compute_bias(np.array([90.0, 180.0]), np.array([100.0, 200.0])) == pytest.approx(-15.0)


def test_compute_per_quarter_mape_values():
    from scripts.evaluate_model import compute_per_quarter_mape

    pred = np.array([[1100.0, 2200.0, 3300.0, 4400.0]])
    true = np.array([[1000.0, 2000.0, 3000.0, 4000.0]])
    assert compute_per_quarter_mape(pred, true) == pytest.approx([10.0, 10.0, 10.0, 10.0])


def test_compute_per_quarter_mape_returns_four():
    from scripts.evaluate_model import compute_per_quarter_mape

    pred = np.array([[1100.0, 2200.0, 3300.0, 4400.0], [1050.0, 2100.0, 3150.0, 4200.0]])
    true = np.array([[1000.0, 2000.0, 3000.0, 4000.0], [1000.0, 2000.0, 3000.0, 4000.0]])
    assert len(compute_per_quarter_mape(pred, true)) == 4


def test_compute_directional_accuracy_all_correct():
    from scripts.evaluate_model import compute_directional_accuracy

    q0 = np.array([1000.0, 1000.0])
    pred = np.array([[1100.0, 900.0, 1100.0, 900.0], [1100.0, 900.0, 1100.0, 900.0]])
    true = np.array([[1200.0, 800.0, 1300.0, 700.0], [1200.0, 800.0, 1300.0, 700.0]])
    assert compute_directional_accuracy(q0, pred, true) == pytest.approx(100.0)


def test_compute_directional_accuracy_all_wrong():
    from scripts.evaluate_model import compute_directional_accuracy

    q0 = np.array([1000.0])
    pred = np.array([[900.0, 1100.0, 900.0, 1100.0]])
    true = np.array([[1200.0, 800.0, 1300.0, 700.0]])
    assert compute_directional_accuracy(q0, pred, true) == pytest.approx(0.0)


@pytest.fixture
def sample_ts():
    """2개 동×업종 조합, 각 24분기 (2019Q1~2024Q4)"""
    quarters = [y * 10 + q for y in range(2019, 2025) for q in range(1, 5)]
    rows = []
    for dong in ["1144010100", "1144010200"]:
        for ind in ["CS100001", "CS100002"]:
            for qtr in quarters:
                rows.append(
                    {
                        "dong_code": dong,
                        "industry_code": ind,
                        "quarter": qtr,
                        "monthly_sales": 1_000_000.0,
                    }
                )
    return pd.DataFrame(rows)


def test_split_train_val_boundary(sample_ts):
    from scripts.evaluate_model import split_train_val

    train, val = split_train_val(sample_ts)
    assert train["quarter"].max() < 20241
    assert val["quarter"].min() >= 20241


def test_split_train_val_no_overlap(sample_ts):
    from scripts.evaluate_model import split_train_val

    train, val = split_train_val(sample_ts)
    assert set(train["quarter"]) & set(val["quarter"]) == set()


def test_get_valid_combos_all_sufficient(sample_ts):
    from scripts.evaluate_model import get_valid_combos

    assert len(get_valid_combos(sample_ts)) == 4


def test_get_valid_combos_excludes_short_train(sample_ts):
    from scripts.evaluate_model import get_valid_combos

    short_train = sample_ts[
        (sample_ts["dong_code"] == "1144010100")
        & (sample_ts["industry_code"] == "CS100001")
        & (sample_ts["quarter"] < 20241)
    ].tail(7)
    ts_mod = pd.concat(
        [
            sample_ts[
                ~(
                    (sample_ts["dong_code"] == "1144010100")
                    & (sample_ts["industry_code"] == "CS100001")
                    & (sample_ts["quarter"] < 20241)
                )
            ],
            short_train,
        ]
    )
    combos = get_valid_combos(ts_mod)
    assert ("1144010100", "CS100001") not in combos
    assert len(combos) == 3


def test_autoregressive_predict_returns_four_values():
    from scripts.evaluate_model import _autoregressive_predict
    from unittest.mock import MagicMock
    import torch

    mock_model = MagicMock()
    mock_model.return_value = torch.tensor([[0.0]])
    mock_tgt_scaler = MagicMock()
    mock_tgt_scaler.inverse_transform.return_value = [[0.0]]

    seq = np.zeros((4, 3), dtype=np.float32)
    result = _autoregressive_predict(
        mock_model, seq, target_idx=0, n_steps=4,
        tgt_scaler=mock_tgt_scaler, device=torch.device("cpu"),
    )
    assert len(result) == 4
    assert all(isinstance(v, float) for v in result)


def test_autoregressive_predict_applies_expm1():
    from scripts.evaluate_model import _autoregressive_predict
    from unittest.mock import MagicMock
    import torch

    mock_model = MagicMock()
    mock_model.return_value = torch.tensor([[0.0]])
    mock_tgt_scaler = MagicMock()
    mock_tgt_scaler.inverse_transform.return_value = [[0.0]]  # log1p=0.0 → expm1=0.0

    seq = np.zeros((4, 3), dtype=np.float32)
    result = _autoregressive_predict(
        mock_model, seq, target_idx=0, n_steps=1,
        tgt_scaler=mock_tgt_scaler, device=torch.device("cpu"),
    )
    assert result[0] == pytest.approx(0.0)


def test_dms_predict_returns_four_values():
    from scripts.evaluate_model import _dms_predict
    from unittest.mock import MagicMock
    import torch

    mock_model = MagicMock()
    mock_model.return_value = torch.tensor([[0.1, 0.2, 0.3, 0.4]])
    mock_tgt_scaler = MagicMock()
    mock_tgt_scaler.inverse_transform.return_value = [[0.0]]

    result = _dms_predict(
        mock_model, np.zeros((8, 3), dtype=np.float32),
        tgt_scaler=mock_tgt_scaler, device=torch.device("cpu"),
    )
    assert len(result) == 4


def test_dms_predict_applies_expm1():
    from scripts.evaluate_model import _dms_predict
    from unittest.mock import MagicMock
    import torch

    mock_model = MagicMock()
    mock_model.return_value = torch.tensor([[0.0, 0.0, 0.0, 0.0]])
    mock_tgt_scaler = MagicMock()
    mock_tgt_scaler.inverse_transform.return_value = [[0.0]]

    result = _dms_predict(
        mock_model, np.zeros((8, 3), dtype=np.float32),
        tgt_scaler=mock_tgt_scaler, device=torch.device("cpu"),
    )
    assert all(v == pytest.approx(0.0) for v in result)


# ---------------------------------------------------------------------------
# _generate_report 테스트
# ---------------------------------------------------------------------------


def _dummy_metrics():
    return dict(mape=15.0, wa_mape=12.0, mae=1_000_000.0, rmse=1_200_000.0,
                da=70.0, bias=50_000.0, pq_mape=[10.0, 12.0, 15.0, 18.0])


def test_generate_report_creates_file(tmp_path):
    from scripts.evaluate_model import _generate_report
    path = _generate_report(
        metrics_v1=_dummy_metrics(), metrics_v2=_dummy_metrics(),
        v1_weights_name="v1.pt", v2_weights_name="v2.pt",
        n_combos=10, reports_dir=tmp_path,
        residual_std=None, warn_combos=[],
    )
    assert path.exists()


def test_generate_report_contains_required_sections(tmp_path):
    from scripts.evaluate_model import _generate_report
    path = _generate_report(
        metrics_v1=_dummy_metrics(), metrics_v2=_dummy_metrics(),
        v1_weights_name="v1.pt", v2_weights_name="v2.pt",
        n_combos=10, reports_dir=tmp_path,
        residual_std=None, warn_combos=[],
    )
    content = path.read_text(encoding="utf-8")
    for section in ["전체 지표 비교", "분기별 MAPE", "결론"]:
        assert section in content


def test_generate_report_auto_creates_dir(tmp_path):
    from scripts.evaluate_model import _generate_report
    new_dir = tmp_path / "reports"
    _generate_report(
        metrics_v1=_dummy_metrics(), metrics_v2=_dummy_metrics(),
        v1_weights_name="v1.pt", v2_weights_name="v2.pt",
        n_combos=10, reports_dir=new_dir,
        residual_std=None, warn_combos=[],
    )
    assert new_dir.exists()


def test_generate_report_includes_residual_std(tmp_path):
    from scripts.evaluate_model import _generate_report
    path = _generate_report(
        metrics_v1=_dummy_metrics(), metrics_v2=_dummy_metrics(),
        v1_weights_name="v1.pt", v2_weights_name="v2.pt",
        n_combos=10, reports_dir=tmp_path,
        residual_std=[1_200_000.0, 1_450_000.0, 1_680_000.0, 1_920_000.0],
        warn_combos=[],
    )
    assert "신뢰구간" in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# run_evaluation 테스트
# ---------------------------------------------------------------------------


from unittest.mock import MagicMock, patch


def test_run_evaluation_returns_path(tmp_path, sample_ts):
    from scripts.evaluate_model import run_evaluation
    import torch

    fake_w = tmp_path / "v2.pt"
    fake_s = tmp_path / "v2_scalers.pkl"
    fake_w.touch(); fake_s.touch()

    mock_feat = MagicMock()
    mock_feat.transform.side_effect = lambda x: x
    mock_feat.scale_ = [1.0]
    mock_tgt = MagicMock()
    mock_tgt.inverse_transform.return_value = [[0.0]]

    mock_v1 = MagicMock()
    mock_v1.return_value = torch.tensor([[0.0]])
    mock_v2 = MagicMock()
    mock_v2.return_value = torch.tensor([[0.0, 0.0, 0.0, 0.0]])

    with patch("scripts.evaluate_model.load_timeseries", return_value=sample_ts), \
         patch("scripts.evaluate_model.load_scalers", return_value=(mock_feat, mock_tgt)), \
         patch("scripts.evaluate_model.TCNForecaster", side_effect=[mock_v1, mock_v2]), \
         patch("scripts.evaluate_model.REPORTS_DIR", tmp_path / "reports"):
        result = run_evaluation(v2_weights=fake_w, v2_scalers=fake_s,
                                v1_weights=fake_w, v1_scalers=fake_s)

    assert isinstance(result, Path)
    assert result.exists()


def test_run_evaluation_report_contains_metrics(tmp_path, sample_ts):
    from scripts.evaluate_model import run_evaluation
    import torch

    fake_w = tmp_path / "v2.pt"
    fake_s = tmp_path / "v2_scalers.pkl"
    fake_w.touch(); fake_s.touch()

    mock_feat = MagicMock()
    mock_feat.transform.side_effect = lambda x: x
    mock_feat.scale_ = [1.0]
    mock_tgt = MagicMock()
    mock_tgt.inverse_transform.return_value = [[0.0]]

    mock_v1 = MagicMock()
    mock_v1.return_value = torch.tensor([[0.0]])
    mock_v2 = MagicMock()
    mock_v2.return_value = torch.tensor([[0.0, 0.0, 0.0, 0.0]])

    with patch("scripts.evaluate_model.load_timeseries", return_value=sample_ts), \
         patch("scripts.evaluate_model.load_scalers", return_value=(mock_feat, mock_tgt)), \
         patch("scripts.evaluate_model.TCNForecaster", side_effect=[mock_v1, mock_v2]), \
         patch("scripts.evaluate_model.REPORTS_DIR", tmp_path / "reports"):
        result = run_evaluation(v2_weights=fake_w, v2_scalers=fake_s,
                                v1_weights=fake_w, v1_scalers=fake_s)

    content = result.read_text(encoding="utf-8")
    assert "MAPE" in content
    assert "결론" in content


# ---------------------------------------------------------------------------
# detect_anomaly_combos 테스트
# ---------------------------------------------------------------------------


def _make_ts(dong, ind, train_sales, val_sales):
    """조합 하나짜리 DataFrame 생성 헬퍼. 분기 코드 YYYYQ 형식 준수."""
    def _gen_quarters(n, start_y=2019, start_q=1):
        qs, y, q = [], start_y, start_q
        for _ in range(n):
            qs.append(y * 10 + q)
            q += 1
            if q > 4:
                q = 1
                y += 1
        return qs

    train_qs = _gen_quarters(len(train_sales), 2019, 1)
    val_qs   = _gen_quarters(len(val_sales), 2024, 1)
    rows = []
    for q, s in zip(train_qs + val_qs, train_sales + val_sales):
        rows.append({"dong_code": dong, "industry_code": ind,
                     "quarter": q, "monthly_sales": np.log1p(s)})
    return pd.DataFrame(rows)


def test_detect_anomaly_normal():
    """정상 조합 → anomaly 없음."""
    from scripts.evaluate_model import detect_anomaly_combos
    # 평균 1M, 표준편차 약 50K인 정상 데이터
    rng = np.random.default_rng(42)
    sales = list(1_000_000.0 + rng.normal(0, 50_000, 20))
    val   = list(1_000_000.0 + rng.normal(0, 30_000, 4))
    ts = _make_ts("1144010100", "CS100001", sales, val)
    result = detect_anomaly_combos(ts, [("1144010100", "CS100001")])
    assert result == {}


def test_detect_anomaly_structural_break():
    """val 2분기 이상 연속 급락 → structural_break."""
    from scripts.evaluate_model import detect_anomaly_combos
    rng = np.random.default_rng(42)
    sales = list(1_000_000.0 + rng.normal(0, 50_000, 20))
    val   = [100_000.0, 100_000.0, 100_000.0, 100_000.0]  # 급락 (z >> 2.5)
    ts = _make_ts("1144010100", "CS100001", sales, val)
    result = detect_anomaly_combos(ts, [("1144010100", "CS100001")])
    assert ("1144010100", "CS100001") in result
    assert result[("1144010100", "CS100001")]["type"] == "structural_break"


def test_detect_anomaly_outlier():
    """val 1분기만 급락 → outlier."""
    from scripts.evaluate_model import detect_anomaly_combos
    rng = np.random.default_rng(42)
    sales = list(1_000_000.0 + rng.normal(0, 50_000, 20))
    val   = [100_000.0, 1_000_000.0, 1_000_000.0, 1_000_000.0]  # Q1만 급락
    ts = _make_ts("1144010100", "CS100001", sales, val)
    result = detect_anomaly_combos(ts, [("1144010100", "CS100001")])
    assert ("1144010100", "CS100001") in result
    assert result[("1144010100", "CS100001")]["type"] == "outlier"


def test_detect_anomaly_returns_affected_quarters():
    """탐지 결과에 이탈 분기 목록 포함."""
    from scripts.evaluate_model import detect_anomaly_combos
    rng = np.random.default_rng(42)
    sales = list(1_000_000.0 + rng.normal(0, 50_000, 20))
    val   = [100_000.0, 100_000.0, 1_000_000.0, 1_000_000.0]
    ts = _make_ts("1144010100", "CS100001", sales, val)
    result = detect_anomaly_combos(ts, [("1144010100", "CS100001")])
    assert "quarters" in result[("1144010100", "CS100001")]
    assert len(result[("1144010100", "CS100001")]["quarters"]) == 2
