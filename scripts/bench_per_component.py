"""ModelOutput.generate() 각 컴포넌트별 단독 실행 시간 계측.

병렬화가 이론과 달리 느린 원인을 찾기 위해, 각 ML 컴포넌트를 직접 호출해
순수 실행 시간을 측정한다. 결과를 통해 (a) 단일 병목 컴포넌트의 존재,
(b) DB/import 오버헤드, (c) GIL/thread 비용을 분리해 분석한다.
"""

from __future__ import annotations

import statistics
import time

# 측정 대상 동/업종 (마포구 진짜 코드 - spotter-single-source skill 참조)
TARGETS = [
    ("11440660", "CS100001", "Seogyo"),
    ("11440680", "CS100001", "Hapjeong"),
]

WARMUP = 1
N_RUNS = 3


def _time(fn, *args, **kwargs) -> tuple[float, object | None, str | None]:
    t = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
        return time.perf_counter() - t, result, None
    except Exception as exc:
        return time.perf_counter() - t, None, f"{type(exc).__name__}: {str(exc)[:80]}"


def bench_target(dong_code: str, industry_code: str, dong_name_kr: str) -> None:
    print(f"\n{'=' * 70}\n  {dong_name_kr} (dong={dong_code}, industry={industry_code})\n{'=' * 70}")

    # ---- 컴포넌트 함수들 import (warmup) ----
    from models.interface import (
        _run_tcn_forecast,
        _run_closure_rate,
        _run_bep,
        _resolve_dong_name,
        _get_latest_store_count,
    )
    from models.closure_risk.predict import predict as closure_risk_predict
    from models.living_pop_forecast.predict_naive import predict_peak_naive
    from models.emerging_district.predict import predict as predict_ae
    from models.emerging_district.predict_fallback import predict_emerging_4tier
    from models.revenue_predictor.bep import BEPCalculator

    # ---- warmup (각 모델 캐시 로드) ----
    print("\n[WARMUP]")
    for name, fn, args in [
        ("TCN", _run_tcn_forecast, (dong_code, industry_code)),
        ("closure_rate", _run_closure_rate, (dong_code, industry_code)),
        ("closure_risk", closure_risk_predict, (dong_code, industry_code)),
        ("emerging_ae", predict_ae, (dong_code, industry_code)),
        ("emerging_fallback", predict_emerging_4tier, (dong_code, industry_code)),
        ("resolve_dong_name", _resolve_dong_name, (dong_code,)),
    ]:
        t, _, err = _time(fn, *args)
        marker = "FAIL" if err else "OK"
        print(f"  warmup {name:25s} {t:6.2f}s  [{marker}] {err or ''}")

    dong_name_resolved = _resolve_dong_name(dong_code) or dong_code
    t, _, err = _time(predict_peak_naive, dong_name_resolved, 4)
    print(f"  warmup {'living_pop':25s} {t:6.2f}s  [{'FAIL' if err else 'OK'}] {err or ''}")

    # ---- 측정 ----
    print(f"\n[MEASUREMENT - {N_RUNS} runs each]")
    components: list[tuple[str, object, tuple]] = [
        ("TCN forecast", _run_tcn_forecast, (dong_code, industry_code)),
        ("closure_rate", _run_closure_rate, (dong_code, industry_code)),
        ("closure_risk", closure_risk_predict, (dong_code, industry_code)),
        ("living_pop", predict_peak_naive, (dong_name_resolved, 4)),
        ("emerging_fallback", predict_emerging_4tier, (dong_code, industry_code)),
        ("emerging_ae", predict_ae, (dong_code, industry_code)),
        ("resolve_dong_name", _resolve_dong_name, (dong_code,)),
    ]

    times_summary: dict[str, float] = {}
    for name, fn, args in components:
        runs = []
        last_err = None
        for _ in range(N_RUNS):
            t, _, err = _time(fn, *args)
            runs.append(t)
            if err:
                last_err = err
        avg = statistics.mean(runs)
        std = statistics.stdev(runs) if len(runs) > 1 else 0.0
        marker = "FAIL" if last_err else "OK "
        times_summary[name] = avg
        print(
            f"  {name:25s} avg={avg:6.3f}s ± {std:6.3f}s  "
            f"min={min(runs):6.3f}s max={max(runs):6.3f}s  [{marker}] {last_err or ''}"
        )

    # _get_latest_store_count + _run_bep (TCN 결과 의존, 별도)
    print(f"\n[Phase 2 (TCN dep)]")
    tcn_t, tcn_res, tcn_err = _time(_run_tcn_forecast, dong_code, industry_code)
    if tcn_res:
        runs_sc = []
        for _ in range(N_RUNS):
            t, _, _ = _time(_get_latest_store_count, dong_code, industry_code)
            runs_sc.append(t)
        print(f"  {'_get_latest_store_count':25s} avg={statistics.mean(runs_sc):6.3f}s")

        cost_cfg = BEPCalculator.get_default_costs(
            "Korean", initial_capital=130_000_000, monthly_rent=2_000_000
        )
        store_count = _get_latest_store_count(dong_code, industry_code)
        qps = round(tcn_res["quarterly_avg"] / store_count) if store_count else 0
        runs_bep = []
        for _ in range(N_RUNS):
            t, _, _ = _time(
                _run_bep,
                quarterly_per_store=qps,
                quarterly_predictions=tcn_res["quarterly_predictions"],
                industry_name="Korean",
                cost_config=cost_cfg,
                store_count=store_count,
            )
            runs_bep.append(t)
        print(f"  {'_run_bep':25s} avg={statistics.mean(runs_bep):6.3f}s")

    # ---- 직렬 합 vs 병렬 max ----
    print(f"\n[ANALYSIS]")
    parallel_set = ["TCN forecast", "closure_rate", "closure_risk", "living_pop", "emerging_fallback", "emerging_ae"]
    serial_sum = sum(times_summary.get(k, 0) for k in parallel_set)
    parallel_max = max(times_summary.get(k, 0) for k in parallel_set)
    print(f"  Phase 1 컴포넌트 6개 (병렬화 대상)")
    print(f"    직렬 합:   {serial_sum:6.3f}s  ← sequential 시 이만큼")
    print(f"    병렬 max:  {parallel_max:6.3f}s  ← ThreadPool 시 이론적 최소")
    print(f"    이론적 절감: {serial_sum - parallel_max:6.3f}s ({(1 - parallel_max/serial_sum)*100:.1f}%)")


def main() -> None:
    for dc, ic, name in TARGETS:
        bench_target(dc, ic, name)


if __name__ == "__main__":
    main()
