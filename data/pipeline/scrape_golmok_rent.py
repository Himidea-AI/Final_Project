import json, time, csv
from pathlib import Path
import requests
import pandas as pd

OUT_DIR = Path(__file__).resolve().parent.parent / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUT_DIR / "golmok_rent_seoul.csv"
BASE = "https://golmok.seoul.go.kr"

def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": f"{BASE}/stateArea.do",
        "X-Requested-With": "XMLHttpRequest",
    })
    session.get(f"{BASE}/stateArea.do")

    all_rows = []
    total = 7 * 4
    count = 0

    for year in range(2019, 2026):
        for qu in range(1, 5):
            count += 1
            params = {
                "stdrYyCd": str(year),
                "stdrQuCd": str(qu),
                "stdrSlctQu": "1",
                "selectTerm": "QU",
                "svcIndutyCdL": "CS000000",
                "svcIndutyCdM": "all",
                "stdrSigngu": "11",
                "selectInduty": "1",
                "infoCategory": "rent",
            }
            try:
                resp = session.post(f"{BASE}/region/selectRentalPrice.json", data=params, timeout=30)
                if resp.ok:
                    data = resp.json()
                    for row in data:
                        row["year"] = year
                        row["quarter"] = qu
                    all_rows.extend(data)
                    print(f"[{count}/{total}] {year}Q{qu}: {len(data)} rows")
                else:
                    print(f"[{count}/{total}] {year}Q{qu}: HTTP {resp.status_code}")
            except Exception as e:
                print(f"[{count}/{total}] {year}Q{qu}: ERROR {e}")
            time.sleep(0.5)

    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
        print(f"Saved: {OUT_CSV}")
        print(f"Total rows: {len(df)}")
        print(f"Columns: {list(df.columns)}")
        print(df.head())
    else:
        print("No data collected!")

if __name__ == "__main__":
    main()
