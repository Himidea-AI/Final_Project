"""ingest 테스트용 공통 fixture."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_seed_dir(tmp_path: Path) -> Path:
    """raw / cleaned / reject 서브디렉토리를 갖춘 임시 seed 디렉토리."""
    for sub in ("raw", "cleaned", "reject"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path
