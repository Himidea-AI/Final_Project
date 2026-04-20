"""
동기 SQLAlchemy Engine 싱글톤 헬퍼.

서비스 레이어(`auth.py`, `biz_mapper.py`, `dong_resolver.py`)에서 요청마다
`create_engine()`을 호출해 RDS 커넥션 슬롯이 포화되던 문제를 해결하기 위함.
URL별로 단 하나의 Engine만 생성하고 커넥션 풀을 재사용한다.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

_engines: dict[str, Engine] = {}


def get_sync_engine(db_url: str) -> Engine:
    """URL별 싱글톤 동기 Engine 반환."""
    engine = _engines.get(db_url)
    if engine is None:
        engine = create_engine(
            db_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
        )
        _engines[db_url] = engine
    return engine


def dispose_all() -> None:
    """등록된 모든 Engine dispose (테스트/셧다운용)."""
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()
