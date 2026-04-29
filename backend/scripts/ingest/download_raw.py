"""신흥 상권 B1 raw CSV 다운로더.

서울 열린데이터광장의 직접 다운로드 URL (datafile.seoul.go.kr) 사용.
WebFetch 의 10MB 한계 우회를 위해 urllib.request.urlretrieve 직접 호출.

사용법:
    cd backend
    python -m scripts.ingest.download_raw                # 모두 시도
    python -m scripts.ingest.download_raw --skip ttareungi  # 따릉이 빼고

KOSIS 전입출은 로그인 필요 가능성이 있어 최선 시도 후 실패하면 URL 안내.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path


_SOURCES = {
    "subway": {
        "url": "https://datafile.seoul.go.kr/bigfile/iot/sheet/csv/download.do?srvType=S&infId=OA-12921&serviceKind=1",
        "filename": "subway_passenger_OA12921.csv",
        "info_url": "https://data.seoul.go.kr/dataList/OA-12921/F/1/datasetView.do",
        "desc": "서울교통공사 일별 시간대별 역별 승하차",
    },
    "ttareungi": {
        "url": "https://datafile.seoul.go.kr/bigfile/iot/sheet/csv/download.do?srvType=F&infId=OA-15182&serviceKind=1",
        "filename": "ttareungi_OA15182.csv",
        "info_url": "https://data.seoul.go.kr/dataList/OA-15182/F/1/datasetView.do",
        "desc": "서울 공공자전거 따릉이 대여이력",
    },
    "migration": {
        "url": None,  # KOSIS 직접 URL 어려움 — manual fallback
        "filename": "kosis_migration.csv",
        "info_url": "https://kosis.kr/statHtml/statHtml.do?orgId=110&tblId=DT_1B26001",
        "desc": "행정안전부 주민등록 동별 인구이동 (KOSIS)",
    },
}


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/octet-stream,*/*",
}


def _download(url: str, dst: Path, *, max_mb: int = 2048) -> tuple[bool, str]:
    """Return (success, message). max_mb 초과 시 abort."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            content_length = resp.headers.get("Content-Length")
            ct = resp.headers.get("Content-Type", "")
            cd = resp.headers.get("Content-Disposition", "")
            print(f"  Content-Type: {ct}")
            print(f"  Content-Disposition: {cd}")
            print(f"  Content-Length: {content_length}")
            if content_length and int(content_length) > max_mb * 1024 * 1024:
                return False, f"too large ({int(content_length) / 1024 / 1024:.1f} MB > {max_mb} MB)"
            with dst.open("wb") as f:
                total = 0
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    total += len(chunk)
                    if total > max_mb * 1024 * 1024:
                        return False, f"download exceeded {max_mb} MB during stream"
        return True, f"saved {total / 1024 / 1024:.1f} MB → {dst.name}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return False, f"URLError: {e.reason}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--raw-base",
        type=Path,
        default=Path("data/seed/raw"),
        help="raw CSV 저장 root (default: data/seed/raw, backend/ 기준)",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        choices=list(_SOURCES.keys()),
        help="이 데이터셋 다운로드 건너뜀 (반복 가능)",
    )
    parser.add_argument(
        "--max-mb",
        type=int,
        default=2048,
        help="단일 파일 최대 크기 (MB, 초과 시 abort)",
    )
    args = parser.parse_args()

    failed: list[str] = []
    manual: list[str] = []

    for key, meta in _SOURCES.items():
        if key in args.skip:
            print(f"--- {key}: skip ---")
            continue
        print(f"--- {key} ({meta['desc']}) ---")
        if meta["url"] is None:
            manual.append(key)
            print(f"  [manual] {meta['info_url']}")
            continue
        dst = args.raw_base / key / meta["filename"]
        ok, msg = _download(meta["url"], dst, max_mb=args.max_mb)
        print(f"  → {msg}")
        if not ok:
            failed.append(key)
            print(f"  [fallback URL] {meta['info_url']}")

    print()
    print("=" * 72)
    if failed or manual:
        print("수동 다운로드 필요:")
        for k in failed + manual:
            m = _SOURCES[k]
            print(f"  -{m['desc']}")
            print(f"    URL  : {m['info_url']}")
            print(f"    저장 : {(args.raw_base / k).resolve()}")
    else:
        print("모든 자동 다운로드 성공.")
    print("=" * 72)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
