import sys
from pathlib import Path

import pytest_asyncio

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend.app.main import app
from src.backend.app.core.config import get_settings
from src.backend.app.core.db import init_pool, close_pool, POOL_KEY


@pytest_asyncio.fixture(autouse=True)
async def ensure_db_pool():
    if getattr(app.state, POOL_KEY, None) is None:
        settings = get_settings()
        await init_pool(app, settings.database_url)
    try:
        yield
    finally:
        pool = getattr(app.state, POOL_KEY, None)
        if pool is not None:
            await close_pool(app)


TABLES_TO_CLEAN = [
    "app.notifications",
    "app.moderation_actions",
    "app.translations",
    "app.post_tags",
    "app.post_media",
    "app.media_assets",
    "app.replies",
    "app.votes",
    "app.posts",
    "app.bookmark_tags",
    "app.bookmarks",
    "app.rate_limits",
    "app.user_limits",
    "app.account_roles",
    "app.accounts",
    "app.tags",
]


def auth_headers(client, token, csrf_token=None, extra=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    csrf_value = csrf_token or client.cookies.get("csrf_token")
    if csrf_value:
        headers["X-CSRF-Token"] = csrf_value
    if extra:
        headers.update(extra)
    return headers


@pytest_asyncio.fixture(autouse=True)
async def clean_database(ensure_db_pool):
    pool = getattr(app.state, POOL_KEY)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            for table in TABLES_TO_CLEAN:
                await cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
    yield
