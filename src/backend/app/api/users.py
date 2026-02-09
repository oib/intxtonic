from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, constr

from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from ..core.db import get_pool
from ..core.deps import get_current_account_id, require_admin
from ..core.security import verify_password, get_password_hash

router = APIRouter(prefix="/users", tags=["users"]) 


class UserOut(BaseModel):
    id: str
    handle: str
    display_name: str
    email: Optional[str] = None
    locale: Optional[str] = None
    created_at: Optional[str] = None


class UserPostsPage(BaseModel):
    items: List[dict]
    limit: int
    offset: int
    total: int


class UserRepliesPage(BaseModel):
    items: List[dict]
    limit: int
    offset: int
    total: int


class UserPostBookmarkItem(BaseModel):
    bookmark_id: str
    post_id: str
    title: str
    excerpt: str
    created_at: Optional[str] = None
    author: Optional[str] = None
    score: Optional[int] = None
    tags: List[dict]


class UserPostBookmarksPage(BaseModel):
    items: List[UserPostBookmarkItem]
    limit: int
    offset: int
    total: int


class UserTagBookmarkItem(BaseModel):
    bookmark_id: str
    tag_id: str
    slug: str
    label: str
    created_at: Optional[str] = None


class UserTagBookmarksPage(BaseModel):
    items: List[UserTagBookmarkItem]
    limit: int
    offset: int
    total: int


class UpdateMeIn(BaseModel):
    locale: Optional[str] = None
    display_name: Optional[str] = None


class UpdatePasswordIn(BaseModel):
    current_password: Optional[str] = None
    new_password: constr(min_length=8)


class AdminUserItem(BaseModel):
    id: str
    handle: str
    email: Optional[str] = None
    created_at: Optional[str] = None
    disabled_at: Optional[str] = None
    is_admin: bool = False


class AdminUserList(BaseModel):
    items: List[AdminUserItem]
    total: int


@router.patch("/me", response_model=UserOut)
async def update_me(req: Request, body: UpdateMeIn, account_id: str = Depends(get_current_account_id)):
    """
    Update current user's basic preferences like default language (locale).
    """
    pool = get_pool(req)
    new_locale: Optional[str] = None
    new_display_name: Optional[str] = None
    if body.locale is not None:
        # normalize simple codes like en, de, fr-CH
        loc = body.locale.strip()
        if not loc:
            new_locale = None
        else:
            if len(loc) > 16:
                raise HTTPException(status_code=422, detail="locale too long")
            new_locale = loc
    if body.display_name is not None:
        name_raw = body.display_name
        name = name_raw.strip()
        if not name:
            new_display_name = None
        else:
            if len(name) > 80:
                raise HTTPException(status_code=422, detail="display_name too long")
            new_display_name = name
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            updates = []
            params = []
            if body.locale is not None:
                updates.append("locale=%s")
                params.append(new_locale)
            if body.display_name is not None:
                updates.append("display_name=%s")
                params.append(new_display_name)
            if updates:
                params.append(account_id)
                await cur.execute(f"UPDATE app.accounts SET {', '.join(updates)} WHERE id=%s", params)
            await cur.execute(
                """
                SELECT id, handle, display_name, email, locale, created_at
                FROM app.accounts
                WHERE id=%s
                LIMIT 1
                """,
                (account_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            return {
                "id": str(row[0]),
                "handle": row[1],
                "display_name": row[2],
                "email": row[3],
                "locale": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
            }


@router.patch("/me/password", status_code=204)
async def change_password(req: Request, body: UpdatePasswordIn, account_id: str = Depends(get_current_account_id)):
    pool = get_pool(req)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT password_hash FROM app.accounts WHERE id=%s LIMIT 1", (account_id,))
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            stored_hash = row[0] or ""
            provided_current = (body.current_password or "").strip()
            # If no password is set yet (e.g., magic-link accounts), or the request omits the current password,
            # allow setting the password directly. Otherwise, verify the supplied current password first.
            if stored_hash and provided_current:
                if not verify_password(provided_current, stored_hash):
                    raise HTTPException(status_code=403, detail="Current password incorrect")
            new_hash = get_password_hash(body.new_password)
            await cur.execute("UPDATE app.accounts SET password_hash=%s WHERE id=%s", (new_hash, account_id))
    return


@router.delete("/me", status_code=204)
async def delete_account(req: Request, account_id: str = Depends(get_current_account_id)):
    pool = get_pool(req)
    now = datetime.now(timezone.utc)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT handle FROM app.accounts WHERE id=%s AND deleted_at IS NULL LIMIT 1",
                (account_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Account not found")
            current_handle = row[0] or "account"
            suffix = secrets.token_urlsafe(6)
            recycled_handle = f"{current_handle}__deleted__{suffix}"[:80]
            await cur.execute(
                """
                UPDATE app.posts
                SET deleted_at=%s,
                    updated_at=%s,
                    title='[deleted]',
                    body_md='[deleted]'
                WHERE author_id=%s AND deleted_at IS NULL
                """,
                (now, now, account_id),
            )
            await cur.execute(
                """
                UPDATE app.replies
                SET deleted_at=%s,
                    updated_at=%s,
                    body_md='[deleted]'
                WHERE author_id=%s AND deleted_at IS NULL
                """,
                (now, now, account_id),
            )
            await cur.execute(
                "DELETE FROM app.bookmarks WHERE account_id=%s",
                (account_id,),
            )
            await cur.execute(
                "DELETE FROM app.account_roles WHERE account_id=%s",
                (account_id,),
            )
            await cur.execute(
                "DELETE FROM app.tag_visibility WHERE account_id=%s",
                (account_id,),
            )
            await cur.execute(
                "DELETE FROM app.tags WHERE lower(slug)=lower(%s) AND created_by_admin = false",
                (current_handle,),
            )
            await cur.execute(
                """
                UPDATE app.accounts
                SET deleted_at=%s,
                    updated_at=%s,
                    handle=%s,
                    email=NULL,
                    password_hash=NULL,
                    magic_login_token=NULL,
                    magic_login_token_expires=NULL,
                    magic_login_sent_at=NULL,
                    email_confirmation_token=NULL,
                    email_confirmation_token_expires=NULL,
                    email_confirmation_sent_at=NULL
                WHERE id=%s
                """,
                (now, now, recycled_handle, account_id),
            )
    return Response(status_code=204)


@router.get("/admin", response_model=AdminUserList)
async def admin_list_users(
    req: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None),
    _: None = Depends(require_admin),
):
    pool = get_pool(req)
    q_like = None
    if q:
        q_like = f"%{q.lower().strip()}%"
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            if q_like:
                await cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM app.accounts a
                    WHERE a.deleted_at IS NULL
                      AND (
                        lower(a.handle) LIKE %s OR
                        lower(COALESCE(a.email, '')) LIKE %s
                      )
                    """,
                    (q_like, q_like),
                )
            else:
                await cur.execute(
                    "SELECT COUNT(*) FROM app.accounts a WHERE a.deleted_at IS NULL",
                )
            total = (await cur.fetchone())[0]

            if q_like:
                await cur.execute(
                    """
                    SELECT a.id, a.handle, a.email, a.created_at, a.disabled_at,
                           EXISTS (
                             SELECT 1
                             FROM app.account_roles ar
                             JOIN app.roles r ON r.id = ar.role_id
                             WHERE ar.account_id = a.id AND lower(r.name) = 'admin'
                           ) AS is_admin
                    FROM app.accounts a
                    WHERE a.deleted_at IS NULL
                      AND (
                        lower(a.handle) LIKE %s OR
                        lower(COALESCE(a.email, '')) LIKE %s
                      )
                    ORDER BY a.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (q_like, q_like, limit, offset),
                )
            else:
                await cur.execute(
                    """
                    SELECT a.id, a.handle, a.email, a.created_at, a.disabled_at,
                           EXISTS (
                             SELECT 1
                             FROM app.account_roles ar
                             JOIN app.roles r ON r.id = ar.role_id
                             WHERE ar.account_id = a.id AND lower(r.name) = 'admin'
                           ) AS is_admin
                    FROM app.accounts a
                    WHERE a.deleted_at IS NULL
                    ORDER BY a.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            rows = await cur.fetchall()
    items = [
        AdminUserItem(
            id=str(r[0]),
            handle=r[1],
            email=r[2],
            created_at=r[3].isoformat() if r[3] else None,
            disabled_at=r[4].isoformat() if r[4] else None,
            is_admin=bool(r[5]),
        )
        for r in rows
    ]
    return AdminUserList(items=items, total=total)


@router.post("/admin/{account_id}/disable", status_code=204)
async def admin_disable_user(
    account_id: str,
    req: Request,
    _: None = Depends(require_admin),
):
    pool = get_pool(req)
    now = datetime.now(timezone.utc)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE app.accounts
                SET disabled_at=%s
                WHERE id=%s AND deleted_at IS NULL AND disabled_at IS NULL
                """,
                (now, account_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Account not found or already disabled")
    return Response(status_code=204)


@router.post("/admin/{account_id}/enable", status_code=204)
async def admin_enable_user(
    account_id: str,
    req: Request,
    _: None = Depends(require_admin),
):
    pool = get_pool(req)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE app.accounts
                SET disabled_at=NULL
                WHERE id=%s AND deleted_at IS NULL AND disabled_at IS NOT NULL
                """,
                (account_id,),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Account not found or not disabled")
    return Response(status_code=204)

@router.get("/{handle}", response_model=UserOut)
async def get_user(req: Request, handle: str):
    pool = get_pool(req)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, handle, display_name, email, locale, created_at
                FROM app.accounts
                WHERE lower(handle)=lower(%s)
                LIMIT 1
                """,
                (handle,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            return {
                "id": str(row[0]),
                "handle": row[1],
                "display_name": row[2],
                "email": row[3],
                "locale": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
            }


@router.get("/{handle}/posts", response_model=UserPostsPage)
async def get_user_posts(
    req: Request,
    handle: str,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("newest"),
):
    pool = get_pool(req)
    order_clause = "p.created_at DESC" if sort != "top" else "p.score DESC, p.created_at DESC"
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # find user id
            await cur.execute(
                "SELECT id FROM app.accounts WHERE lower(handle)=lower(%s) LIMIT 1",
                (handle,),
            )
            r = await cur.fetchone()
            if not r:
                raise HTTPException(status_code=404, detail="User not found")
            account_id = r[0]

            # total
            await cur.execute(
                "SELECT COUNT(*) FROM app.posts p WHERE p.deleted_at IS NULL AND p.author_id=%s",
                (account_id,),
            )
            total = (await cur.fetchone())[0]

            # items with tags aggregated
            await cur.execute(
                f"""
                SELECT p.id, p.title, p.body_md, p.created_at, p.score,
                       COALESCE(json_agg(DISTINCT jsonb_build_object('slug', t.slug) ) FILTER (WHERE t.id IS NOT NULL), '[]') AS tags
                FROM app.posts p
                LEFT JOIN app.post_tags pt ON pt.post_id = p.id
                LEFT JOIN app.tags t ON t.id = pt.tag_id
                WHERE p.deleted_at IS NULL AND p.author_id = %s
                GROUP BY p.id, p.title, p.body_md, p.created_at, p.score
                ORDER BY {order_clause}
                LIMIT %s OFFSET %s
                """,
                (account_id, limit, offset),
            )
            rows = await cur.fetchall()
            items = [
                {
                    "id": str(x[0]),
                    "title": x[1],
                    "body_md": x[2],
                    "created_at": x[3].isoformat() if x[3] else None,
                    "score": x[4],
                    "tags": x[5] or [],
                }
                for x in rows
            ]
            return {"items": items, "limit": limit, "offset": offset, "total": total}


@router.get("/{handle}/replies", response_model=UserRepliesPage)
async def get_user_replies(
    req: Request,
    handle: str,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("newest"),
):
    import logging
    logger = logging.getLogger(__name__)
    pool = get_pool(req)
    order_clause = "r.created_at DESC" if sort != "top" else "r.score DESC, r.created_at DESC"
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Find user ID
            await cur.execute(
                "SELECT id FROM app.accounts WHERE lower(handle)=lower(%s) LIMIT 1",
                (handle,),
            )
            r = await cur.fetchone()
            if not r:
                logger.warning(f"User not found for handle: {handle}")
                raise HTTPException(status_code=404, detail="User not found")
            account_id = r[0]

            # Get total count of replies
            await cur.execute(
                "SELECT COUNT(*) FROM app.replies r WHERE r.deleted_at IS NULL AND r.author_id = %s",
                (account_id,),
            )
            total = (await cur.fetchone())[0]

            # Fetch replies
            await cur.execute(
                f"""
                SELECT r.id, r.post_id, r.body_md, r.created_at, r.score
                FROM app.replies r
                WHERE r.deleted_at IS NULL AND r.author_id = %s
                ORDER BY {order_clause}
                LIMIT %s OFFSET %s
                """,
                (account_id, limit, offset),
            )
            rows = await cur.fetchall()
            items = [
                {
                    "id": str(x[0]),
                    "post_id": str(x[1]) if x[1] else None,
                    "body_md": x[2],
                    "created_at": x[3].isoformat() if x[3] else None,
                    "score": x[4],
                    "tags": [],  # Tags not applicable for replies based on current schema
                }
                for x in rows
            ]
            # logger.info(f"Fetched {len(items)} replies for user {handle}")
            return {"items": items, "limit": limit, "offset": offset, "total": total}


@router.get("/{handle}/bookmarks", response_model=UserPostBookmarksPage)
async def get_user_post_bookmarks(
    req: Request,
    handle: str,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    account_id: str = Depends(get_current_account_id),
):
    pool = get_pool(req)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM app.accounts WHERE lower(handle)=lower(%s) LIMIT 1",
                (handle,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            profile_account_id = str(row[0])
            if profile_account_id != account_id:
                raise HTTPException(status_code=403, detail="Bookmarks are private")

            await cur.execute(
                """
                SELECT COUNT(*)
                FROM app.bookmarks b
                JOIN app.posts p ON p.id = b.target_id
                WHERE b.account_id = %s
                  AND b.target_type = 'post'
                  AND p.deleted_at IS NULL
                """,
                (profile_account_id,),
            )
            total = (await cur.fetchone())[0]

            await cur.execute(
                """
                SELECT b.id AS bookmark_id,
                       b.created_at,
                       p.id AS post_id,
                       p.title,
                       p.body_md,
                       p.created_at AS post_created_at,
                       p.score,
                       a.handle AS author,
                       COALESCE(
                         json_agg(DISTINCT jsonb_build_object('id', t.id, 'slug', t.slug, 'label', t.label))
                           FILTER (WHERE t.id IS NOT NULL),
                         '[]'
                       ) AS tags
                FROM app.bookmarks b
                JOIN app.posts p ON p.id = b.target_id
                LEFT JOIN app.accounts a ON a.id = p.author_id
                LEFT JOIN app.post_tags pt ON pt.post_id = p.id
                LEFT JOIN app.tags t ON t.id = pt.tag_id
                WHERE b.account_id = %s
                  AND b.target_type = 'post'
                  AND p.deleted_at IS NULL
                GROUP BY b.id, b.created_at, p.id, p.title, p.body_md, p.created_at, p.score, a.handle
                ORDER BY b.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (profile_account_id, limit, offset),
            )
            rows = await cur.fetchall()

    items = []
    for (bookmark_id, bookmark_created_at, post_id, title, body_md, post_created_at, score, author_handle, tags) in rows:
        body = body_md or ""
        excerpt = " ".join(body.split())
        if len(excerpt) > 220:
            excerpt = excerpt[:220].rstrip() + "…"
        items.append(
            {
                "bookmark_id": str(bookmark_id),
                "post_id": str(post_id),
                "title": title or "Untitled",
                "excerpt": excerpt,
                "created_at": bookmark_created_at.isoformat() if bookmark_created_at else None,
                "author": author_handle,
                "score": score,
                "tags": tags or [],
            }
        )

    return {"items": items, "limit": limit, "offset": offset, "total": total}


@router.get("/{handle}/tag-bookmarks", response_model=UserTagBookmarksPage)
async def get_user_tag_bookmarks(
    req: Request,
    handle: str,
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    account_id: str = Depends(get_current_account_id),
):
    pool = get_pool(req)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM app.accounts WHERE lower(handle)=lower(%s) LIMIT 1",
                (handle,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            profile_account_id = str(row[0])
            if profile_account_id != account_id:
                raise HTTPException(status_code=403, detail="Bookmarks are private")

            await cur.execute(
                """
                SELECT COUNT(*)
                FROM app.bookmarks b
                JOIN app.tags t ON t.id = b.target_id
                WHERE b.account_id = %s
                  AND b.target_type = 'tag'
                """,
                (profile_account_id,),
            )
            total = (await cur.fetchone())[0]

            await cur.execute(
                """
                SELECT b.id AS bookmark_id,
                       b.created_at,
                       t.id AS tag_id,
                       t.slug,
                       t.label
                FROM app.bookmarks b
                JOIN app.tags t ON t.id = b.target_id
                WHERE b.account_id = %s
                  AND b.target_type = 'tag'
                ORDER BY b.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (profile_account_id, limit, offset),
            )
            rows = await cur.fetchall()

    items = [
        {
            "bookmark_id": str(r[0]),
            "created_at": r[1].isoformat() if r[1] else None,
            "tag_id": str(r[2]),
            "slug": r[3],
            "label": r[4],
        }
        for r in rows
    ]

    return {"items": items, "limit": limit, "offset": offset, "total": total}
