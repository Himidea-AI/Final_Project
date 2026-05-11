"""/predict 엔드포인트 응답 시간 실측."""

import json
import time
import urllib.request

URL = "http://127.0.0.1:8000/predict"
PAYLOAD = {
    "business_type": "한식음식점",
    "brand_name": "벤치마크",
    "target_districts": ["서교동", "합정동", "망원동", "연남동"],
    "target_district": "서교동",
    "initial_capital": 130_000_000,
    "monthly_rent": 2_000_000,
    "store_area": 15,
}


def main():
    body = json.dumps(PAYLOAD).encode("utf-8")
    req = urllib.request.Request(
        URL, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    runs = []
    for i in range(3):
        t = time.perf_counter()
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read())
        elapsed = time.perf_counter() - t
        runs.append(elapsed)
        n = len(data.get("data", []))
        st = data.get("status")
        print(f"call {i+1}: wall={elapsed:.2f}s  status={st}  n_dongs={n}")
    if runs:
        avg = sum(runs) / len(runs)
        print(f"\navg={avg:.2f}s  min={min(runs):.2f}s  max={max(runs):.2f}s")


if __name__ == "__main__":
    main()
