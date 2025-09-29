from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator, Optional

from datetime import datetime

from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse
from pydantic import BaseModel

from ..core.notify import subscribe, unsubscribe
from ..core.deps import get_current_account_id
from ..core.db import get_pool

router = APIRouter(prefix="/notify", tags=["notify"]) 


async def _event_stream() -> AsyncGenerator[bytes, None]:
    q = await subscribe()
    try:
        # Send initial comment to keep connection open
        yield b":ok\n\n"
        while True:
            event = await q.get()
            payload = json.dumps(event, ensure_ascii=False)
            data = f"data: {payload}\n\n".encode("utf-8")
            yield data
    except asyncio.CancelledError:
        # client disconnected
        pass
    finally:
        await unsubscribe(q)


@router.get("/events")
async def list_events():
    """Server-Sent Events endpoint for real-time notifications.
    Frontend can connect with: new EventSource('/notify/events')
    """
    return StreamingResponse(_event_stream(), media_type="text/event-stream")


class NotificationOut(BaseModel):
    id: str
    kind: str
    ref_type: Optional[str] = None
    ref_id: Optional[str] = None
    payload: dict
    is_read: bool
    created_at: str


@router.get("/list", response_model=list[NotificationOut])
async def list_notifications(
    account_id: str = Depends(get_current_account_id),
    pool = Depends(get_pool),
):
    sql = """
      SELECT id, kind, ref_type, ref_id, payload, is_read, created_at
      FROM app.notifications
      WHERE recipient_id = %s
      ORDER BY created_at DESC
      LIMIT 200
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (account_id,))
            rows = await cur.fetchall()
    results: list[NotificationOut] = []
    for row in rows:
        created = row[6].isoformat() if row[6] else datetime.utcnow().isoformat()
        results.append(
            NotificationOut(
                id=str(row[0]),
                kind=row[1],
                ref_type=row[2],
                ref_id=str(row[3]) if row[3] else None,
                payload=row[4] or {},
                is_read=bool(row[5]),
                created_at=created,
            )
        )
    return results
