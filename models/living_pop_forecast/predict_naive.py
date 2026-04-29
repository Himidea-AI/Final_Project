"""D 모델 production naive baseline.

학술 평가 결과 (6 라운드 모두 fail):
- v4_residual MASE_lag1 = 1.042 (naive 보다 살짝 못함)
- v7_daily_residual MASE_lag7 = 1.0004 (naive 동급)
- v2 / v3 / v5(3 변형) / ARIMA / v6 / v7 — 모두 naive 미달

따라서 production 은 naive baseline 사용.
- 분기 단위: y[t] = y[t-1] (직전 분기 같은 dong, time_zone 값)
- 일별 단위 (참고): y[t] = y[t-7] (1주 전 같은 요일) — 본 모듈은 분기 단위만 구현.

성능 (학습 plan 6 라운드 결과):
- naive_lag1 (분기) MAE 665, MAPE 2.62%, R² 0.9964
- naive_lag7 (일별) MAE 1,039, MAPE 3.71%, R² 0.9707

backend 호환:
- predict_peak_naive(dong_name | dong_code, n_quarters) 시그니처는
  기존 predict.predict_peak() 와 동일하게 dong_name (또는 dong_code) + n_quarters 받음.
- 결과 dict 구조도 동일: list[{quarter_offset, peak_time_zone, peak_pop, all_hours}].
"""

from __future__ import annotations

import logging

import pandas as pd

from .data_prep import DB_URL, MAPO_DONG_CODES, load_living_population

logger = logging.getLogger(__name__)


# DataFrame 캐시 — 시뮬마다 풀스캔 방지. db_url 키로 캐시.
_DF_CACHE: dict[str, pd.DataFrame] = {}


def _cached_load(db_url: str = DB_URL, csv_path: str | None = None) -> pd.DataFrame:
    """load_living_population 결과를 캐시. 두 번째 호출부터 0ms (DB I/O 없음)."""
    cache_key = f"{db_url}::{csv_path or ''}"
    if cache_key in _DF_CACHE:
        return _DF_CACHE[cache_key]
    df = load_living_population(db_url=db_url, csv_path=csv_path)
    _DF_CACHE[cache_key] = df
    return df


def _resolve_dong(df: pd.DataFrame, dong: str) -> tuple[str, str]:
    """dong_name 또는 dong_code 입력을 (dong_code, dong_name) 으로 정규화한다.

    - 마포 16동 dong_code 면 그대로 매칭.
    - 그 외에는 df 의 dong_name 매칭.
    - 매칭 실패 시 ValueError.
    """
    dong = str(dong).strip()
    if dong in MAPO_DONG_CODES:
        sub = df[df["dong_code"] == dong]
        if sub.empty:
            available = sorted(df["dong_code"].unique().tolist())
            raise ValueError(f"데이터 없음: dong_code='{dong}'\n사용 가능한 dong_code: {available}")
        return dong, str(sub["dong_name"].iloc[0])

    sub = df[df["dong_name"] == dong]
    if sub.empty:
        available = sorted(df["dong_name"].unique().tolist())
        raise ValueError(f"데이터 없음: dong='{dong}' (마포 16동만 지원)\n사용 가능한 동: {available}")
    return str(sub["dong_code"].iloc[0]), str(sub["dong_name"].iloc[0])


def _latest_quarter_for(df: pd.DataFrame, dong_code: str, time_zone: int) -> int:
    """(dong_code, time_zone) 의 가장 최근 분기."""
    sub = df[(df["dong_code"] == dong_code) & (df["time_zone"] == time_zone)]
    if sub.empty:
        raise ValueError(
            f"데이터 없음: dong_code='{dong_code}', time_zone={time_zone}. "
            f"naive baseline 은 직전 분기 데이터가 필요합니다."
        )
    return int(sub["quarter"].max())


def predict_naive_lag1(
    dong_code: str,
    time_zone: int,
    target_quarter: int | None = None,
    *,
    db_url: str = DB_URL,
    csv_path: str | None = None,
) -> float:
    """직전 분기 (dong_code, time_zone) 평균 인구.

    Parameters
    ----------
    dong_code : str
        마포 16동 dong_code (예: "11440660" = 서교동) 또는 dong_name.
    time_zone : int
        0~23 시간대.
    target_quarter : int | None
        예측 대상 분기 (예: 20253). None 이면 가장 최근 분기 + 1.
    db_url : str
        Postgres URL (테스트용 오버라이드).
    csv_path : str | None
        캐시 CSV 경로 (테스트용 오버라이드).

    Returns
    -------
    float
        target_quarter 의 직전 분기 (dong_code, time_zone) 평균 인구.

    Raises
    ------
    ValueError
        time_zone 이 0~23 범위 밖이거나, 매칭 데이터가 없거나,
        target_quarter 직전 분기 데이터가 비어있을 때.
    """
    if not (0 <= int(time_zone) <= 23):
        raise ValueError(f"time_zone 은 0~23 범위여야 합니다. (입력: {time_zone})")

    df = _cached_load(db_url=db_url, csv_path=csv_path)
    dc, _name = _resolve_dong(df, dong_code)

    if target_quarter is None:
        # 가장 최근 분기 + 1 (단, 직전 = 가장 최근)
        latest = _latest_quarter_for(df, dc, int(time_zone))
        prev_quarter = latest
    else:
        # target 의 직전 분기 = target - 1 (단순 -1, 분기 인코딩 (yyyy*10+q) 의 -1 처리)
        prev_quarter = _previous_quarter(int(target_quarter))

    sub = df[(df["dong_code"] == dc) & (df["time_zone"] == int(time_zone)) & (df["quarter"] == prev_quarter)]
    if sub.empty:
        # 직전 분기 데이터 누락 시: 더 이전 가장 최근 분기로 fallback
        prior = df[
            (df["dong_code"] == dc) & (df["time_zone"] == int(time_zone)) & (df["quarter"] <= prev_quarter)
        ].sort_values("quarter")
        if prior.empty:
            raise ValueError(
                f"naive baseline 직전 분기 데이터 없음: "
                f"dong_code={dc}, time_zone={time_zone}, prev_quarter={prev_quarter}"
            )
        return float(prior["total_avg_pop"].iloc[-1])
    return float(sub["total_avg_pop"].iloc[0])


def _previous_quarter(quarter: int) -> int:
    """yyyyq (예: 20253) 인코딩에서 직전 분기 반환.

    - 20253 → 20252
    - 20251 → 20244
    """
    year, q = divmod(quarter, 10)
    if q <= 1:
        return (year - 1) * 10 + 4
    return year * 10 + (q - 1)


def _next_quarter(quarter: int) -> int:
    """yyyyq 인코딩에서 다음 분기 반환."""
    year, q = divmod(quarter, 10)
    if q >= 4:
        return (year + 1) * 10 + 1
    return year * 10 + (q + 1)


def predict_peak_naive(
    dong_name: str,
    n_quarters: int = 4,
    *,
    db_url: str = DB_URL,
    csv_path: str | None = None,
    confidence_pct: float = 0.05,
) -> list[dict]:
    """기존 predict_peak() 와 호환되는 시그니처의 naive 구현.

    각 미래 분기 (n_quarters 개) 에 대해 직전 분기의 (dong, time_zone) 평균 인구를
    그대로 사용. 모든 미래 분기는 동일한 24시간대 패턴을 반환한다 (lag-1 의 정의).

    Parameters
    ----------
    dong_name : str
        행정동명 (예: '서교동') 또는 dong_code (예: '11440660').
        backward compat 을 위해 두 형식 모두 허용.
    n_quarters : int
        예측 분기 수.
    db_url : str
        Postgres URL.
    csv_path : str | None
        캐시 CSV 경로 (테스트용).
    confidence_pct : float
        신뢰구간 ± 비율 (기본 5%). naive baseline MAPE 가 ~3% 라
        보수적으로 5% 사용.

    Returns
    -------
    list[dict]
        각 원소: {
            "quarter_offset": int,
            "peak_time_zone": int,   # 24h 중 최대 인구 시간대
            "peak_pop": float,
            "all_hours": list[dict], # 24 시간 모두
        }
    """
    if n_quarters < 1:
        raise ValueError(f"n_quarters 는 1 이상이어야 합니다. (입력: {n_quarters})")

    df = _cached_load(db_url=db_url, csv_path=csv_path)
    dc, name = _resolve_dong(df, dong_name)

    # 24 시간대 각각 가장 최근 분기 값 산출 — 모두 같은 분기일 가능성 높지만
    # 누락 분기 가능성 대비 시간대별 max(quarter) 사용.
    sub_dong = df[df["dong_code"] == dc]
    if sub_dong.empty:
        raise ValueError(f"데이터 없음: dong='{dong_name}' (resolved={dc}, {name})")

    latest_per_tz = (
        sub_dong.sort_values("quarter").groupby("time_zone").agg(predicted_pop=("total_avg_pop", "last")).reset_index()
    )

    all_hours: list[dict] = []
    for _, row in latest_per_tz.iterrows():
        tz = int(row["time_zone"])
        pop = float(row["predicted_pop"])
        margin = pop * confidence_pct
        all_hours.append(
            {
                "time_zone": tz,
                "predicted_pop": round(pop, 0),
                "confidence_lower": round(max(0.0, pop - margin), 0),
                "confidence_upper": round(pop + margin, 0),
            }
        )

    if not all_hours:
        raise ValueError(f"'{dong_name}' 시간대 데이터가 비어 있습니다.")

    all_hours.sort(key=lambda x: x["time_zone"])
    peak = max(all_hours, key=lambda x: x["predicted_pop"])

    # naive lag-1 은 모든 미래 분기가 직전 분기와 동일.
    # quarter_offset 1..n_quarters 모두 같은 24h 패턴 복제.
    results: list[dict] = []
    for q_idx in range(n_quarters):
        results.append(
            {
                "quarter_offset": q_idx + 1,
                "peak_time_zone": int(peak["time_zone"]),
                "peak_pop": peak["predicted_pop"],
                "all_hours": [dict(h) for h in all_hours],
            }
        )
    return results


__all__ = [
    "predict_naive_lag1",
    "predict_peak_naive",
]
