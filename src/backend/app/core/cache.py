from __future__ import annotations

from typing import Optional

from fastapi import Request
from redis.asyncio import Redis

from .config import get_settings

REDIS_STATE_KEY = "redis_client"


async def init_redis(app, url: Optional[str] = None) -> None:
    settings = get_settings()
    redis_url = url or settings.redis_url
    if not redis_url:
        return
    client: Optional[Redis]
    try:
        client = Redis.from_url(redis_url, decode_responses=True)
        await client.ping()
    except Exception:
        client = None
    app.state.__setattr__(REDIS_STATE_KEY, client)


async def close_redis(app) -> None:
    client: Optional[Redis] = getattr(app.state, REDIS_STATE_KEY, None)
    if client is not None:
        try:
            await client.close()
        finally:
            delattr(app.state, REDIS_STATE_KEY)


def get_redis(request: Request) -> Optional[Redis]:
    return getattr(request.app.state, REDIS_STATE_KEY, None)
