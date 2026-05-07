"""emerging_ae 내부 단계별 시간 분해 측정.

predict() 내부를 (1) load_emerging_data, (2) recent forward, (3) consecutive forward loop,
(4) detect_signal, (5) 기타로 분해해 진짜 병목을 식별한다.
"""

from __future__ import annotations

import statistics
import time

TARGETS = [
    ("11440660", "CS100001", "Seogyo"),
    ("11440680", "CS100001", "Hapjeong"),
]

N_RUNS = 3


def _t(label, fn, *a, **kw):
    t = time.perf_counter()
    r = fn(*a, **kw)
    return time.perf_counter() - t, r


def main():
    import numpy as np
    import torch
    from sklearn.preprocessing import MinMaxScaler

    from models.emerging_district.predict import (
        _load_model,
        _detect_signal,
        _count_consecutive_anomalies,
    )
    from models.emerging_district.data_prep import DB_URL, load_emerging_data

    # warmup
    _load_model()
    load_emerging_data(db_url=DB_URL, dong_prefix="11440")

    for dong, ind, name in TARGETS:
        print(f"\n=== {name} ({dong}/{ind}) ===")

        breakdown = {"load_data": [], "recent_fwd": [], "consec_loop": [], "detect_signal": []}

        for _ in range(N_RUNS):
            # 1) load_emerging_data — 캐시 hit/miss 모두 측정
            t, df = _t("load", load_emerging_data, db_url=DB_URL, dong_prefix=dong[:5])
            breakdown["load_data"].append(t)

            model, meta = _load_model()
            window_size = meta["window_size"]
            feature_names = meta["feature_names"]

            group = df[(df["dong_code"] == dong) & (df["industry_code"] == ind)].copy()
            if group.empty or len(group) < window_size:
                print("  데이터 부족 — skip")
                break
            group = group.sort_values("quarter")

            scaler = MinMaxScaler()
            feat_vals = group[feature_names].values.astype(np.float32)
            feat_scaled = scaler.fit_transform(feat_vals)

            # 2) recent forward (최근 window 1회)
            recent_seq = feat_scaled[-window_size:]
            dev = next(model.parameters()).device
            x_t = torch.from_numpy(recent_seq).unsqueeze(0).to(dev)
            t = time.perf_counter()
            with torch.no_grad():
                _ = model(x_t)
            breakdown["recent_fwd"].append(time.perf_counter() - t)

            # 3) consecutive anomaly forward loop
            t, _ = _t("consec", _count_consecutive_anomalies, group, model, meta, scaler)
            breakdown["consec_loop"].append(t)

            # 4) detect_signal
            t, _ = _t("sig", _detect_signal, group)
            breakdown["detect_signal"].append(t)

        for k, v in breakdown.items():
            if v:
                print(f"  {k:18s} avg={statistics.mean(v)*1000:7.1f}ms  min={min(v)*1000:7.1f}  max={max(v)*1000:7.1f}")

        total = sum(statistics.mean(v) for v in breakdown.values() if v)
        print(f"  {'합계':18s}     {total*1000:7.1f}ms")


if __name__ == "__main__":
    main()
