"""
Redis 연결 — 시뮬레이션 결과 캐시, Job 상태 관리
"""

import json

import redis.asyncio as aioredis


class RedisClient:
    """Redis 비동기 클라이언트"""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Redis 연결"""
        self._client = aioredis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)

    async def disconnect(self) -> None:
        """Redis 연결 종료"""
        if self._client:
            await self._client.close()
            self._client = None

    def _ensure_connected(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError("Redis 미연결. connect()를 먼저 호출하세요.")
        return self._client

    async def set_job_status(self, job_id: str, status: str, ttl: int = 3600) -> None:
        """Job 상태 설정 (1시간 TTL)"""
        client = self._ensure_connected()
        await client.set(f"job:{job_id}:status", status, ex=ttl)

    async def get_job_status(self, job_id: str) -> str:
        """Job 상태 조회. 없으면 'unknown' 반환."""
        client = self._ensure_connected()
        result = await client.get(f"job:{job_id}:status")
        return result or "unknown"

    async def cache_result(self, key: str, data: dict, ttl: int = 3600) -> None:
        """시뮬레이션 결과 캐시 (JSON 직렬화, 기본 1시간 TTL)"""
        client = self._ensure_connected()
        await client.set(f"cache:{key}", json.dumps(data, ensure_ascii=False, default=str), ex=ttl)

    async def get_cached_result(self, key: str) -> dict | None:
        """캐시된 결과 조회. 없으면 None 반환."""
        client = self._ensure_connected()
        result = await client.get(f"cache:{key}")
        if result is None:
            return None
        return json.loads(result)
