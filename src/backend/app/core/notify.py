from __future__ import annotations

import asyncio
from typing import Any, Dict, Set

# Very small in-memory pub-sub for SSE. Not suitable for multi-process without a shared broker.
# For production, replace with Redis pub/sub or Postgres LISTEN/NOTIFY.

_subscribers: Set[asyncio.Queue] = set()
_lock = asyncio.Lock()

async def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    async with _lock:
        _subscribers.add(q)
    return q

async def unsubscribe(q: asyncio.Queue) -> None:
    async with _lock:
        _subscribers.discard(q)

async def publish(event: Dict[str, Any]) -> None:
    # Push to all current subscribers, non-blocking best-effort
    async with _lock:
        targets = list(_subscribers)
    for q in targets:
        try:
            await q.put(event)
        except Exception:
            # Drop silently
            pass
