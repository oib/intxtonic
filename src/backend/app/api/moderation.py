from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..core.db import get_pool
from ..core.deps import require_role, get_current_account_id
from ..core.notify import publish
from .auth import csrf_validate

router = APIRouter(prefix="/moderation", tags=["moderation"])


class ReportOut(BaseModel):
    id: str
    target_type: str
    target_id: str
    reason: Optional[str] = None
    reported_by: Optional[str] = None
    created_at: Optional[str] = None


class NewContentOut(BaseModel):
    id: str
    type: str  # 'post' or 'reply'
    title: Optional[str] = None
    body_md: str
    author: Optional[str] = None
    created_at: Optional[str] = None


class ReportsPage(BaseModel):
    items: List[ReportOut]
    limit: int
    offset: int
    total: int


class NewContentPage(BaseModel):
    items: List[NewContentOut]
    limit: int
    offset: int
    total: int


@router.get("/reports", response_model=ReportsPage)
async def list_reports(
    req: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: None = Depends(lambda request: require_role(request, "moderator")),  # Restrict to moderators or admins
):
    """Fetch a paginated list of reported content for moderation review."""
    pool = get_pool(req)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Get total count of reports
            await cur.execute(
                "SELECT COUNT(*) FROM app.moderation_actions WHERE action = 'report'"
            )
            total = (await cur.fetchone())[0]

            # Fetch paginated reports
            await cur.execute(
                """
                SELECT ma.id, ma.target_type, ma.target_id, ma.reason, a.handle AS reported_by, ma.created_at
                FROM app.moderation_actions ma
                LEFT JOIN app.accounts a ON a.id = ma.actor_id
                WHERE ma.action = 'report'
                ORDER BY ma.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = await cur.fetchall()
            items = [
                {
                    "id": str(r[0]),
                    "target_type": r[1],
                    "target_id": str(r[2]),
                    "reason": r[3],
                    "reported_by": r[4],
                    "created_at": r[5].isoformat() if r[5] else None,
                }
                for r in rows
            ]
            return {"items": items, "limit": limit, "offset": offset, "total": total}


class ReportCreateIn(BaseModel):
    target_type: str  # 'post' | 'reply'
    target_id: str
    reason: Optional[str] = None


@router.post("/report")
async def create_report(
    body: ReportCreateIn,
    account_id: str = Depends(get_current_account_id),
    pool = Depends(get_pool),
    _: bool = Depends(csrf_validate),
):
    """Allow any logged-in user to file a report. Emits report_queued event."""
    tt = (body.target_type or '').lower().strip()
    if tt not in ("post", "reply"):
        raise HTTPException(status_code=422, detail="invalid target_type")
    tid = (body.target_id or '').strip()
    if not tid:
        raise HTTPException(status_code=400, detail="target_id required")
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO app.moderation_actions (id, action, target_type, target_id, reason, actor_id, created_at)
                VALUES (gen_random_uuid(), 'report', %s, %s, %s, %s, now())
                RETURNING id
                """,
                (tt, tid, body.reason, account_id),
            )
            rid = (await cur.fetchone())[0]
    try:
        await publish({
            "type": "report_queued",
            "id": str(rid),
            "target_type": tt,
            "target_id": tid,
            "reason": body.reason or "",
        })
    except Exception:
        pass
    return {"ok": True, "id": str(rid)}


class ReportProcessOut(BaseModel):
    ok: bool = True


@router.post("/reports/{report_id}/resolve", response_model=ReportProcessOut)
async def resolve_report(
    report_id: str,
    _: None = Depends(lambda request: require_role(request, "moderator")),
    __: bool = Depends(csrf_validate),
    pool = Depends(get_pool),
):
    """Mark a report as processed (simple delete). Emits report_processed event."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM app.moderation_actions WHERE id=%s AND action='report'",
                (report_id,),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="report not found")
    try:
        await publish({
            "type": "report_processed",
            "id": str(report_id),
        })
    except Exception:
        pass
    return {"ok": True}


@router.get("/new-content", response_model=NewContentPage)
async def list_new_content(
    req: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: None = Depends(lambda request: require_role(request, "moderator")),  # Restrict to moderators or admins
):
    """Fetch a paginated list of new posts and replies for moderation review."""
    pool = get_pool(req.app)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Get total count of new content (posts + replies)
            await cur.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT id FROM app.posts WHERE deleted_at IS NULL
                    UNION ALL
                    SELECT id FROM app.replies WHERE deleted_at IS NULL
                ) combined
                """
            )
            total = (await cur.fetchone())[0]

            # Fetch paginated new content (combine posts and replies using UNION)
            await cur.execute(
                """
                SELECT 'post' AS type, p.id, p.title, p.body_md, a.handle AS author, p.created_at
                FROM app.posts p
                LEFT JOIN app.accounts a ON a.id = p.author_id
                WHERE p.deleted_at IS NULL
                UNION ALL
                SELECT 'reply' AS type, r.id, NULL AS title, r.body_md, a.handle AS author, r.created_at
                FROM app.replies r
                LEFT JOIN app.accounts a ON a.id = r.author_id
                WHERE r.deleted_at IS NULL
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = await cur.fetchall()
            items = [
                {
                    "id": str(r[1]),
                    "type": r[0],
                    "title": r[2],
                    "body_md": r[3],
                    "author": r[4],
                    "created_at": r[5].isoformat() if r[5] else None,
                }
                for r in rows
            ]
            return {"items": items, "limit": limit, "offset": offset, "total": total}
