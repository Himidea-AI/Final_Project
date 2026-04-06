"""
PostgreSQL 비동기 클라이언트 — SQLAlchemy 2.0 async engine + session
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base


class PostgresClient:
    """PostgreSQL async 클라이언트."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self._session_factory = None

    async def connect(self) -> None:
        """async engine + session factory 초기화."""
        async_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://")
        self.engine = create_async_engine(async_url, echo=False, pool_size=5)
        self._session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def disconnect(self) -> None:
        """엔진 종료."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self._session_factory = None

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """async session context manager."""
        if self._session_factory is None:
            raise RuntimeError("Not connected. Call connect() first.")
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def create_tables(self) -> None:
        """모든 테이블 생성 (개발/테스트용)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        """모든 테이블 삭제 (테스트용)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
