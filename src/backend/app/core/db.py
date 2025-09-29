from __future__ import annotations

from typing import Optional

from psycopg_pool import AsyncConnectionPool
from fastapi import FastAPI, Request


POOL_KEY = "db_pool"


async def init_pool(app: FastAPI, dsn: str) -> None:
    # Create a global async connection pool stored in app.state
    pool = AsyncConnectionPool(conninfo=dsn, max_size=10, num_workers=3, open=False)
    await pool.open()
    app.state.__setattr__(POOL_KEY, pool)


async def close_pool(app: FastAPI) -> None:
    pool: Optional[AsyncConnectionPool] = getattr(app.state, POOL_KEY, None)
    if pool is not None:
        await pool.close()
        delattr(app.state, POOL_KEY)


def get_pool(request: Request) -> AsyncConnectionPool:
    """FastAPI dependency to retrieve the global AsyncConnectionPool from app.state.

    Using Request allows Depends() to resolve this correctly without trying to treat
    FastAPI as a Pydantic field type.
    """
    pool: Optional[AsyncConnectionPool] = getattr(request.app.state, POOL_KEY, None)
    if pool is None:
        raise RuntimeError("DB pool not initialized")
    return pool


async def get_conn(request: Request):
    pool = get_pool(request)
    async with pool.connection() as conn:
        yield conn
