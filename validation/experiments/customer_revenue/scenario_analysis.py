"""C 모델 Scenario 2 분석 — 합정 카페 30대 여성 vs 50대 부부 타겟.

비교: C 모델 결과 vs naive (group_mean baseline).
- 30대 여성 비율 (age_30_ratio × female_ratio, 분포 독립 가정)
- 50대 비율 (age_50_ratio)
- 차이가 5%p 이상이면 사용자 결정 다를 가능성 (임계 명시).

Note
----
plan 의 ``load_segment_data`` / ``encode_inputs`` 는 ``data_prep.py`` 에 존재하지
않아서, T3 (evaluate_c.py) 와 동일하게 ``load_district_sales`` + ``_compute_ratios``
+ 인라인 인코딩 헬퍼로 재구성한다.

Test split 기준은 T3 와 동일: 분기 시간순 정렬 후 상위 70%/15%/15% 분할.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from models.customer_revenue.data_prep import (
    DB_URL,
    DONG_TO_IDX,
    INDUSTRY_TO_IDX,
    SEGMENT_COLS,
    YEAR_BASE,
    YEAR_SCALE,
    _compute_ratios,
    load_district_sales,
)
from models.customer_revenue.model import WEIGHTS_DIR, MLPPredictor
from validation.experiments.customer_revenue.baseline_c import group_mean_baseline

logger = logging.getLogger(__name__)
RESULTS_DIR = Path("validation/results")

# 합정동 = 11440680 / 카페 = CS100002 (data_prep INDUSTRY_CODES 기반)
SCENARIO_DONGS: list[str] = ["11440680"]
SCENARIO_INDUSTRIES: list[str] = ["CS100002"]
# 결정_달라짐 임계값: 5%p (0.05) — 30대 여성 또는 50대 비율 차이가 이 이상이면 True
DECISION_THRESHOLD: float = 0.05


def _load_segment_df(db_url: str = DB_URL) -> pd.DataFrame:
    """district_sales 로드 + 비율 계산 + 마포 16동 / 10업종 / 유효 분기 필터."""
    df = load_district_sales(db_url=db_url)
    df = _compute_ratios(df)
    df["dong_code"] = df["dong_code"].astype(str)
    df["industry_code"] = df["industry_code"].astype(str)
    df = df[df["dong_code"].isin(DONG_TO_IDX) & df["industry_code"].isin(INDUSTRY_TO_IDX)]
    df = df[df["quarter"] % 10 != 0]
    if df.empty:
        raise RuntimeError("district_sales 데이터가 비어있습니다. DB 연결/필터 조건 확인 필요.")
    return df.reset_index(drop=True)


def _encode_inputs(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(dong_idx, industry_idx, quarter_enc[N,3]) 반환. T3 evaluate_c._encode_inputs 와 동일."""
    dong_idx = df["dong_code"].map(DONG_TO_IDX).values.astype(np.int64)
    industry_idx = df["industry_code"].map(INDUSTRY_TO_IDX).values.astype(np.int64)

    years = (df["quarter"].values // 10).astype(np.float32)
    year_norms = (years - YEAR_BASE) / YEAR_SCALE
    quarter_nums = (df["quarter"] % 10).values
    quarter_enc = np.array(
        [
            [
                math.sin(2 * math.pi * (q - 1) / 4),
                math.cos(2 * math.pi * (q - 1) / 4),
                year_norms[i],
            ]
            for i, q in enumerate(quarter_nums)
        ],
        dtype=np.float32,
    )
    return dong_idx, industry_idx, quarter_enc


def scenario2_analysis(db_url: str = DB_URL) -> pd.DataFrame:
    """합정 카페 (test 분기) 에서 C 모델 vs naive 의 30대 여성 vs 50대 비율 비교.

    Returns
    -------
    pd.DataFrame
        rows: 시나리오 조합 × test 분기 수
        cols: dong_code, industry_code, quarter,
              model_30대여성, naive_30대여성, diff_30대여성_pp,
              model_50대, naive_50대, diff_50대_pp,
              결정_달라짐
    """
    df = _load_segment_df(db_url=db_url)

    # T3 와 동일한 시간순 70/15/15 split (분기 기준)
    quarters = sorted(df["quarter"].unique())
    n = len(quarters)
    if n < 3:
        raise RuntimeError(f"분기 수가 부족합니다 ({n}). 시나리오 분석 불가.")
    train_q = quarters[: int(n * 0.70)]
    test_q = quarters[int(n * 0.85) :]
    df_train = df[df["quarter"].isin(train_q)].reset_index(drop=True)

    df_test = df[
        df["dong_code"].isin(SCENARIO_DONGS)
        & df["industry_code"].isin(SCENARIO_INDUSTRIES)
        & df["quarter"].isin(test_q)
    ].reset_index(drop=True)

    if df_test.empty:
        raise RuntimeError(
            f"시나리오 데이터 없음: dong={SCENARIO_DONGS} × industry={SCENARIO_INDUSTRIES} × test_quarters={test_q}"
        )

    logger.info(
        "시나리오 분석: dong=%s industry=%s test_quarters=%s rows=%d",
        SCENARIO_DONGS,
        SCENARIO_INDUSTRIES,
        test_q,
        len(df_test),
    )

    # C 모델 추론
    weights_path = WEIGHTS_DIR / "customer_mlp.pt"
    if not weights_path.exists():
        raise FileNotFoundError(
            f"학습 가중치를 찾을 수 없습니다: {weights_path}. models/customer_revenue/train.py 를 먼저 실행하세요."
        )
    model = MLPPredictor()
    model.load_weights(weights_path)
    model.eval()

    dong_idx, ind_idx, q_enc = _encode_inputs(df_test)
    with torch.no_grad():
        y_model = (
            model(
                torch.from_numpy(dong_idx).long(),
                torch.from_numpy(ind_idx).long(),
                torch.from_numpy(q_enc).float(),
            )
            .cpu()
            .numpy()
            .astype(np.float64)
        )

    # naive baseline (train 기준 group_mean)
    gm = group_mean_baseline(df_train, SEGMENT_COLS)
    glob_vals = df_train[SEGMENT_COLS].mean().values.astype(np.float64)

    y_naive = np.array(
        [
            gm.loc[(r.dong_code, r.industry_code)].values if (r.dong_code, r.industry_code) in gm.index else glob_vals
            for r in df_test.itertuples(index=False)
        ],
        dtype=np.float64,
    )

    age30_idx = SEGMENT_COLS.index("age_30_ratio")
    female_idx = SEGMENT_COLS.index("female_ratio")
    age50_idx = SEGMENT_COLS.index("age_50_ratio")

    rows = []
    for i in range(len(df_test)):
        row = df_test.iloc[i]

        # 30대 여성 = age_30_ratio * female_ratio (분포 독립 가정 — 근사)
        age30_model = float(y_model[i, age30_idx])
        female_model = float(y_model[i, female_idx])
        age30_female_model = age30_model * female_model

        age30_naive = float(y_naive[i, age30_idx])
        female_naive = float(y_naive[i, female_idx])
        age30_female_naive = age30_naive * female_naive

        age50_model = float(y_model[i, age50_idx])
        age50_naive = float(y_naive[i, age50_idx])

        diff_30f = age30_female_model - age30_female_naive
        diff_50 = age50_model - age50_naive

        rows.append(
            {
                "dong_code": row["dong_code"],
                "industry_code": row["industry_code"],
                "quarter": int(row["quarter"]),
                "model_30대여성": round(age30_female_model, 4),
                "naive_30대여성": round(age30_female_naive, 4),
                "diff_30대여성_pp": round(diff_30f * 100, 2),
                "model_50대": round(age50_model, 4),
                "naive_50대": round(age50_naive, 4),
                "diff_50대_pp": round(diff_50 * 100, 2),
                "결정_달라짐": bool(abs(diff_30f) > DECISION_THRESHOLD or abs(diff_50) > DECISION_THRESHOLD),
            }
        )

    df_out = pd.DataFrame(rows)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "customer_revenue_scenario2.csv"
    df_out.to_csv(out_path, index=False, encoding="utf-8-sig")
    logger.info("결과 저장: %s", out_path)
    return df_out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    df = scenario2_analysis()
    print("\n=== Scenario 2: 합정 카페 타겟 분석 ===")
    print(df.to_string(index=False))
    if "결정_달라짐" in df.columns and len(df) > 0:
        true_n = int(df["결정_달라짐"].sum())
        print(
            f"\n결정_달라짐: True={true_n}/{len(df)} "
            f"({true_n / len(df) * 100:.1f}%) | False={len(df) - true_n}/{len(df)} "
            f"({(len(df) - true_n) / len(df) * 100:.1f}%) | 임계값={DECISION_THRESHOLD * 100:.0f}%p"
        )


if __name__ == "__main__":
    main()
