"""Option B sanity fallback 영향 콤보 스캔 — 마포구 전체.

각 (동, 업종) 콤보에 대해 최신 분기 store/franchise + 최근 4분기 평균 매출 q_avg 를 계산하고,
Option B 조건 (ratio>4 AND per_store>200M) 을 평가한다.

실행:
    cd C:\\AISpace\\Final_Project_2
    python scripts/scan_option_b_cases.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from models.lstm_forecast.data_prep import load_sales_data, load_store_data

MAPO_PREFIX = "11440"
THRESHOLD_PER_STORE = 200_000_000
THRESHOLD_RATIO = 3.5  # 2026-05-06: 4 → 3.5 (성산2동×치킨 ratio 3.7 포함)
OLD_THRESHOLD = 300_000_000

# 동 코드 → 이름 (자주 등장하는 것만 부분 매핑; 없는 코드는 코드로 표시)
DONG_NAMES = {
    "11440515": "합정동",
    "11440545": "서교동",
    "11440555": "망원1동",
    "11440560": "망원2동",
    "11440565": "연남동",
    "11440535": "성산1동",
    "11440538": "성산2동",
    "11440580": "상암동",
    "11440505": "공덕동",
    "11440510": "아현동",
    "11440520": "신공덕동",
    "11440525": "도화동",
    "11440530": "용강동",
    "11440540": "대흥동",
    "11440550": "염리동",
    "11440570": "서강동",
    "11440575": "신수동",
    "11440585": "중동",
}

INDUSTRY_NAMES = {
    "CS100001": "한식",
    "CS100002": "중식",
    "CS100003": "일식",
    "CS100004": "양식",
    "CS100005": "분식",
    "CS100006": "치킨",
    "CS100007": "패스트푸드",
    "CS100008": "제과제빵",
    "CS100009": "커피",
    "CS100010": "주점",
}


def main() -> None:
    print("=" * 100)
    print("Option B (ratio>4 AND per_store>200M) — 마포구 콤보 영향 스캔")
    print("=" * 100)

    sales = load_sales_data(dong_prefix=MAPO_PREFIX)
    stores = load_store_data(dong_prefix=MAPO_PREFIX)

    print(f"\nsales rows={len(sales):,}, store rows={len(stores):,}")

    # 최신 분기 stores
    stores_latest = (
        stores.sort_values("quarter").groupby(["dong_code", "industry_code"]).tail(1).reset_index(drop=True)
    )

    # 최근 4분기 평균 분기 매출 q_avg (monthly_sales × 3 = quarterly)
    sales_sorted = sales.sort_values("quarter").copy()
    sales_sorted["quarterly_sales"] = sales_sorted["monthly_sales"] * 3
    last_quarters = sorted(sales_sorted["quarter"].unique())[-4:]
    sales_last4 = sales_sorted[sales_sorted["quarter"].isin(last_quarters)]
    q_avg = (
        sales_last4.groupby(["dong_code", "industry_code"])["quarterly_sales"]
        .mean()
        .reset_index()
        .rename(columns={"quarterly_sales": "q_avg"})
    )
    # 동/업종 이름 dict (sales 원본에서 추출)
    dong_name_map = dict(zip(sales_last4["dong_code"].astype(str), sales_last4["dong_name"].astype(str)))
    industry_name_map = dict(
        zip(sales_last4["industry_code"].astype(str), sales_last4["industry_name"].astype(str))
    )

    df = stores_latest.merge(q_avg, on=["dong_code", "industry_code"], how="inner")
    df["dong_code"] = df["dong_code"].astype(str)
    df["industry_code"] = df["industry_code"].astype(str)
    df["store_count"] = df["store_count"].fillna(0).astype(int)
    df["franchise_count"] = df["franchise_count"].fillna(0).astype(int)

    # 분류
    def classify(row):
        s, f, q = row["store_count"], row["franchise_count"], row["q_avg"]
        if s <= 0:
            return "store=0"
        ratio = f / s
        per_store = q / s
        opt_b = ratio > THRESHOLD_RATIO and per_store > THRESHOLD_PER_STORE
        old = (f > s) and per_store > OLD_THRESHOLD  # 이전 로직 (300M 임계 + franchise>store)
        return f"B={'✓' if opt_b else '✗'} OLD={'✓' if old else '✗'}"

    df["status"] = df.apply(classify, axis=1)
    df["ratio"] = df.apply(lambda r: r["franchise_count"] / r["store_count"] if r["store_count"] > 0 else 0, axis=1)
    df["per_store_M"] = df.apply(lambda r: r["q_avg"] / r["store_count"] / 1e6 if r["store_count"] > 0 else 0, axis=1)
    df["dong_name"] = df["dong_code"].map(dong_name_map).fillna(df["dong_code"])
    df["industry_name"] = df["industry_code"].map(industry_name_map).fillna(df["industry_code"])

    total = len(df)
    triggers_b = df[df["status"].str.contains("B=✓")]
    triggers_old = df[df["status"].str.contains("OLD=✓")]
    only_b = df[df["status"] == "B=✓ OLD=✗"]
    only_old = df[df["status"] == "B=✗ OLD=✓"]
    both = df[df["status"] == "B=✓ OLD=✓"]

    print("\n" + "=" * 100)
    print(f"전체 콤보 수: {total}")
    print(f"  Option B 발동: {len(triggers_b)} ({100 * len(triggers_b) / total:.1f}%)")
    print(f"  OLD 로직 발동: {len(triggers_old)} ({100 * len(triggers_old) / total:.1f}%)")
    print(f"  B만 발동 (OLD 못 잡았던 케이스): {len(only_b)}")
    print(f"  OLD만 발동 (B에서 빠진 케이스): {len(only_old)}")
    print(f"  둘 다 발동: {len(both)}")
    print("=" * 100)

    def print_rows(label: str, sub: pd.DataFrame) -> None:
        if sub.empty:
            print(f"\n[{label}] 없음")
            return
        print(f"\n[{label}] {len(sub)}건")
        cols = ["dong_name", "industry_name", "store_count", "franchise_count", "ratio", "per_store_M"]
        view = sub[cols].copy()
        view["ratio"] = view["ratio"].round(1)
        view["per_store_M"] = view["per_store_M"].round(1).astype(str) + "M"
        print(view.to_string(index=False))

    print_rows("✅ Option B 가 새로 잡는 케이스 (사용자가 원한 효과)", only_b)
    print_rows("⚠️ OLD 에서 잡혔지만 B 에서 빠지는 케이스 (false-negative 위험)", only_old)
    print_rows("✓ 둘 다 잡는 케이스", both)

    print("\n" + "=" * 100)
    print("주목할 합정동 케이스만 ↓")
    print("=" * 100)
    hapjeong = df[df["dong_name"].astype(str).str.contains("합정", na=False)].sort_values("per_store_M", ascending=False).head(10)
    if not hapjeong.empty:
        print(
            hapjeong[["industry_name", "store_count", "franchise_count", "ratio", "per_store_M", "status"]].to_string(
                index=False
            )
        )


if __name__ == "__main__":
    main()
