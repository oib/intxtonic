from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, constr

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..core.db import get_pool
from ..core.deps import get_current_account_id
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


class UpdatePasswordIn(BaseModel):
    current_password: constr(min_length=1)
    new_password: constr(min_length=8)


@router.patch("/me", response_model=UserOut)
async def update_me(req: Request, body: UpdateMeIn, account_id: str = Depends(get_current_account_id)):
    """
    Update current user's basic preferences like default language (locale).
    """
    pool = get_pool(req)
    new_locale: Optional[str] = None
    if body.locale is not None:
        # normalize simple codes like en, de, fr-CH
        loc = body.locale.strip()
        if not loc:
            new_locale = None
        else:
            if len(loc) > 16:
                raise HTTPException(status_code=422, detail="locale too long")
            new_locale = loc
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            if body.locale is not None:
                await cur.execute("UPDATE app.accounts SET locale=%s WHERE id=%s", (new_locale, account_id))
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
            if not stored_hash:
                raise HTTPException(status_code=409, detail="Password login disabled for this account")
            if not verify_password(body.current_password, stored_hash):
                raise HTTPException(status_code=403, detail="Current password incorrect")
            new_hash = get_password_hash(body.new_password)
            await cur.execute("UPDATE app.accounts SET password_hash=%s WHERE id=%s", (new_hash, account_id))
    return

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
            logger.info(f"Fetched {len(items)} replies for user {handle}")
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
