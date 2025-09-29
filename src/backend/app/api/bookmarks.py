from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from ..core.db import get_pool
from ..core.deps import get_current_account_id


router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


class BookmarkCreateIn(BaseModel):
    target_type: str = Field(pattern="^(post|reply|tag|other)$")
    target_id: str
    tags: Optional[List[str]] = None


class BookmarkTagsIn(BaseModel):
    tags: List[str]


class BookmarkOut(BaseModel):
    id: str
    target_type: str
    target_id: str
    tags: List[str]
    created_at: Optional[str] = None


class BookmarkListOut(BaseModel):
    items: List[BookmarkOut]
    total: int
    limit: int
    offset: int


class BookmarkDeleteOut(BaseModel):
    ok: bool = True


class BookmarkLookupItem(BaseModel):
    target_id: str
    bookmark_id: str
    tags: List[str]
    created_at: Optional[str] = None


class BookmarkLookupOut(BaseModel):
    items: List[BookmarkLookupItem]


VALID_TARGETS = {"post", "reply", "tag", "other"}
BOOKMARKED_TAG_SLUG = "bookmarked"


async def _normalize_target_id(cur, target_type: str, raw_target_id: str) -> str:
    candidate = (raw_target_id or "").strip()
    if not candidate:
        raise HTTPException(status_code=422, detail="invalid target_id")
    if target_type == "post":
        try:
            uuid_value = UUID(candidate)
        except ValueError:
            raise HTTPException(status_code=422, detail="invalid post id")
        await cur.execute(
            "SELECT id FROM app.posts WHERE id = %s AND deleted_at IS NULL",
            (uuid_value,),
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")
        return str(row[0])
    if target_type == "reply":
        try:
            uuid_value = UUID(candidate)
        except ValueError:
            raise HTTPException(status_code=422, detail="invalid reply id")
        await cur.execute(
            "SELECT id FROM app.replies WHERE id = %s AND deleted_at IS NULL",
            (uuid_value,),
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Reply not found")
        return str(row[0])
    if target_type == "tag":
        try:
            uuid_value = UUID(candidate)
            await cur.execute("SELECT id FROM app.tags WHERE id = %s", (uuid_value,))
        except ValueError:
            await cur.execute("SELECT id FROM app.tags WHERE slug = %s", (candidate.lower(),))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Tag not found")
        return str(row[0])
    if target_type == "other":
        return candidate
    raise HTTPException(status_code=422, detail="invalid target_type")


async def _normalize_target_ids(cur, target_type: str, raw_ids: List[str]) -> List[str]:
    normalized: list[str] = []
    for raw in raw_ids:
        try:
            value = await _normalize_target_id(cur, target_type, raw)
        except HTTPException:
            continue
        if value not in normalized:
            normalized.append(value)
    return normalized


async def _ensure_target_exists(cur, target_type: str, target_id: str) -> str:
    return await _normalize_target_id(cur, target_type, target_id)


async def _get_bookmarked_tag_id(cur) -> Optional[str]:
    await cur.execute("SELECT id FROM app.tags WHERE slug = %s LIMIT 1", (BOOKMARKED_TAG_SLUG,))
    row = await cur.fetchone()
    return str(row[0]) if row else None


def _normalize_tags(tags: Optional[List[str]], include_default: bool = True) -> List[str]:
    slugs: set[str] = set()
    if include_default:
        slugs.add(BOOKMARKED_TAG_SLUG)
    if tags:
        for raw in tags:
            if not raw:
                continue
            slug = raw.strip().lower()
            if slug:
                slugs.add(slug)
    return sorted(slugs)


@router.post("", response_model=BookmarkOut, status_code=status.HTTP_201_CREATED)
async def create_bookmark(
    body: BookmarkCreateIn,
    account_id: str = Depends(get_current_account_id),
    pool=Depends(get_pool),
):
    target_type = body.target_type.lower()
    if target_type not in VALID_TARGETS:
        raise HTTPException(status_code=422, detail="invalid target_type")
    tags = _normalize_tags(body.tags, include_default=(target_type == "post"))
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await _ensure_target_exists(cur, target_type, body.target_id)
            await cur.execute(
                """
                INSERT INTO app.bookmarks (account_id, target_type, target_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (account_id, target_type, target_id)
                DO UPDATE SET target_type = EXCLUDED.target_type
                RETURNING id, created_at
                """,
                (account_id, target_type, body.target_id),
            )
            row = await cur.fetchone()
            bookmark_id, created_at = str(row[0]), row[1]
            for slug in tags:
                await cur.execute(
                    """
                    INSERT INTO app.bookmark_tags (bookmark_id, tag_slug)
                    VALUES (%s, %s)
                    ON CONFLICT (bookmark_id, tag_slug) DO NOTHING
                    """,
                    (bookmark_id, slug),
                )
            if target_type == "post":
                tag_id = await _get_bookmarked_tag_id(cur)
                if tag_id:
                    await cur.execute(
                        """
                        INSERT INTO app.post_tags (post_id, tag_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (body.target_id, tag_id),
                    )
            await cur.execute(
                "SELECT tag_slug FROM app.bookmark_tags WHERE bookmark_id = %s ORDER BY tag_slug",
                (bookmark_id,),
            )
            tags_rows = await cur.fetchall()
    return BookmarkOut(
        id=bookmark_id,
        target_type=target_type,
        target_id=body.target_id,
        tags=[r[0] for r in tags_rows],
        created_at=created_at.isoformat() if created_at else None,
    )


@router.get("", response_model=BookmarkListOut)
async def list_bookmarks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tag: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    account_id: str = Depends(get_current_account_id),
    pool=Depends(get_pool),
):
    tag_filter = tag.strip().lower() if tag else None
    target_filter = target_type.strip().lower() if target_type else None
    if target_filter and target_filter not in VALID_TARGETS:
        raise HTTPException(status_code=422, detail="invalid target_type")
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            params: list = [account_id]
            sql_filter = ""
            if target_filter:
                params.append(target_filter)
                sql_filter += " AND b.target_type = %s"
            if tag_filter:
                params.append(tag_filter)
                sql_filter += " AND EXISTS (SELECT 1 FROM app.bookmark_tags bt2 WHERE bt2.bookmark_id = b.id AND bt2.tag_slug = %s)"
            count_sql = f"SELECT COUNT(*) FROM app.bookmarks b WHERE b.account_id = %s{sql_filter}"
            await cur.execute(count_sql, tuple(params))
            total = (await cur.fetchone())[0]
            params_paginated = params + [limit, offset]
            data_sql = f"""
              SELECT b.id, b.target_type, b.target_id, b.created_at,
                     COALESCE(array_agg(bt.tag_slug ORDER BY bt.tag_slug)
                              FILTER (WHERE bt.tag_slug IS NOT NULL), ARRAY[]::text[]) AS tags
              FROM app.bookmarks b
              LEFT JOIN app.bookmark_tags bt ON bt.bookmark_id = b.id
              WHERE b.account_id = %s{sql_filter}
              GROUP BY b.id
              ORDER BY b.created_at DESC
              LIMIT %s OFFSET %s
            """
            await cur.execute(data_sql, tuple(params_paginated))
            rows = await cur.fetchall()
    items = [
        BookmarkOut(
            id=str(r[0]),
            target_type=r[1],
            target_id=str(r[2]),
            tags=list(r[4]),
            created_at=r[3].isoformat() if r[3] else None,
        )
        for r in rows
    ]
    return BookmarkListOut(items=items, total=total, limit=limit, offset=offset)


@router.delete("", response_model=BookmarkDeleteOut)
async def delete_bookmark(
    target_type: str = Query(...),
    target_id: str = Query(...),
    account_id: str = Depends(get_current_account_id),
    pool=Depends(get_pool),
):
    target_type_norm = target_type.strip().lower()
    if target_type_norm not in VALID_TARGETS:
        raise HTTPException(status_code=422, detail="invalid target_type")
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                DELETE FROM app.bookmarks
                WHERE account_id = %s AND target_type = %s AND target_id = %s
                RETURNING id
                """,
                (account_id, target_type_norm, target_id),
            )
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Bookmark not found")
    return BookmarkDeleteOut()


@router.patch("/{bookmark_id}/tags", response_model=BookmarkOut)
async def update_bookmark_tags(
    bookmark_id: str = Path(...),
    body: BookmarkTagsIn = ...,
    account_id: str = Depends(get_current_account_id),
    pool=Depends(get_pool),
):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT account_id, target_type, target_id, created_at FROM app.bookmarks WHERE id = %s",
                (bookmark_id,),
            )
            row = await cur.fetchone()
            if not row or str(row[0]) != account_id:
                raise HTTPException(status_code=404, detail="Bookmark not found")
            target_type, target_id, created_at = row[1], str(row[2]), row[3]
            tags = _normalize_tags(body.tags, include_default=(target_type == "post"))
            await cur.execute(
                "DELETE FROM app.bookmark_tags WHERE bookmark_id = %s",
                (bookmark_id,),
            )
            for slug in tags:
                await cur.execute(
                    """
                    INSERT INTO app.bookmark_tags (bookmark_id, tag_slug)
                    VALUES (%s, %s)
                    ON CONFLICT (bookmark_id, tag_slug) DO NOTHING
                    """,
                    (bookmark_id, slug),
                )
            if target_type == "post":
                tag_id = await _get_bookmarked_tag_id(cur)
                if tag_id:
                    await cur.execute(
                        """
                        INSERT INTO app.post_tags (post_id, tag_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (target_id, tag_id),
                    )
            await cur.execute(
                "SELECT tag_slug FROM app.bookmark_tags WHERE bookmark_id = %s ORDER BY tag_slug",
                (bookmark_id,),
            )
            tag_rows = await cur.fetchall()
    return BookmarkOut(
        id=bookmark_id,
        target_type=target_type,
        target_id=target_id,
        tags=[r[0] for r in tag_rows],
        created_at=created_at.isoformat() if created_at else None,
    )


@router.get("/lookup", response_model=BookmarkLookupOut)
async def lookup_bookmarks(
    target_type: str = Query(...),
    target_ids: str = Query(...),
    account_id: str = Depends(get_current_account_id),
    pool=Depends(get_pool),
):
    target_type_norm = target_type.strip().lower()
    if target_type_norm not in VALID_TARGETS:
        raise HTTPException(status_code=422, detail="invalid target_type")
    raw_ids = [t.strip() for t in target_ids.split(",") if t.strip()]
    if not raw_ids:
        return BookmarkLookupOut(items=[])
    try:
        uuid_ids = [UUID(r) for r in raw_ids]
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid target_ids")
    uuid_strings = [str(u) for u in uuid_ids]
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT b.id, b.target_id, b.created_at,
                       COALESCE(array_agg(bt.tag_slug ORDER BY bt.tag_slug)
                                FILTER (WHERE bt.tag_slug IS NOT NULL), ARRAY[]::text[]) AS tags
                FROM app.bookmarks b
                LEFT JOIN app.bookmark_tags bt ON bt.bookmark_id = b.id
                WHERE b.account_id = %s
                  AND b.target_type = %s
                  AND b.target_id = ANY(%s::uuid[])
                GROUP BY b.id
                """,
                (account_id, target_type_norm, uuid_strings),
            )
            rows = await cur.fetchall()
    items = [
        BookmarkLookupItem(
            target_id=str(r[1]),
            bookmark_id=str(r[0]),
            tags=list(r[3]),
            created_at=r[2].isoformat() if r[2] else None,
        )
        for r in rows
    ]
    return BookmarkLookupOut(items=items)
