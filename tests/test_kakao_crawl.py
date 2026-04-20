"""data/pipeline/collect_kakao_stores.py 단위 테스트"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "data" / "pipeline"),
)

from collect_kakao_stores import generate_grid  # noqa: E402


def test_generate_grid_exact_division():
    """bbox가 셀 크기로 정확히 2×2로 나눠지는 케이스."""
    # 500m 기준: lat 스텝 ≈ 0.004504°, lon 스텝 ≈ 0.005682°
    # lat 0.009° (2 rows), lon 0.01° (2 cols) → 4셀
    cells = generate_grid((126.88, 37.53, 126.89, 37.539), cell_m=500)
    assert len(cells) == 4
    # 모든 셀은 (west, south, east, north) 순
    for w, s, e, n in cells:
        assert w < e and s < n


def test_generate_grid_covers_bbox():
    """생성된 셀들이 원본 bbox를 완전히 덮는다 (중복 허용, 누락 불가)."""
    cells = generate_grid((126.88, 37.53, 126.96, 37.59), cell_m=500)
    # 좌하단·우상단이 각각 최소 하나의 셀에 포함
    assert any(w <= 126.88 and s <= 37.53 for w, s, _, _ in cells)
    assert any(e >= 126.96 and n >= 37.59 for _, _, e, n in cells)


def test_generate_grid_mapo_size():
    """마포 전체 bbox를 500m로 나누면 150~250 셀 범위."""
    cells = generate_grid((126.88, 37.53, 126.96, 37.59), cell_m=500)
    assert 150 <= len(cells) <= 250
