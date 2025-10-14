from __future__ import annotations

from typing import Optional, List
import json
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..core.db import get_pool
from ..core.deps import (
    require_role,
    require_admin,
    get_optional_account_id,
    is_admin_account,
)
from ..core.tag_access import (
    LANGUAGE_TAG_SLUGS,
    build_access_clause,
    fetch_accessible_tag_sets,
    tag_visibility_available,
)
from .auth import csrf_validate
from ..core.cache import get_redis

router = APIRouter(prefix="/tags", tags=["tags"])

CACHE_TTL_SECONDS = 120


async def invalidate_tag_cache(request: Request) -> None:
    redis = get_redis(request)
    if not redis:
        return
    try:
        keys = await redis.keys("tags:*")
        if keys:
            await redis.delete(*keys)
    except Exception:
        pass


def make_slug(label: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in label.strip().lower()).strip("-")


class TagCreateIn(BaseModel):
    label: str


class TagOut(BaseModel):
    id: str
    slug: str
    label: str
    is_banned: bool = False
    is_restricted: bool = False
    created_at: str
    created_by_admin: bool = False


class TagWithCountOut(BaseModel):
    id: str
    slug: str
    label: str
    usage_count: int
    is_banned: bool
    is_restricted: bool
    created_by_admin: bool = False


class TagVisibilityRole(BaseModel):
    id: str
    name: str


class TagVisibilityUser(BaseModel):
    id: str
    handle: str


class TagVisibilityOut(BaseModel):
    tag_id: str
    slug: str
    label: str
    roles: List[TagVisibilityRole]
    users: List[TagVisibilityUser]


class UserTagAssignmentOut(BaseModel):
    tag_id: str
    slug: str
    label: str
    created_at: Optional[str] = None


class UserTagVisibilityOut(BaseModel):
    account_id: str
    handle: str
    tags: List[UserTagAssignmentOut]


class TagVisibilityAssignIn(BaseModel):
    handle: str


class TagGroupOut(BaseModel):
    admin_created: list[TagOut]
    user_created: list[TagOut]


@router.get("", response_model=list[TagOut])
async def list_tags(
    request: Request,
    query: Optional[str] = Query(None),
    limit: int = 50,
    offset: int = 0,
    account_id: Optional[str] = Depends(get_optional_account_id),
    pool = Depends(get_pool),
):
    is_admin = await is_admin_account(pool, account_id)
    visibility_enabled = await tag_visibility_available(pool)

    sql = """
      SELECT t.id, t.slug, t.label, t.is_banned, t.is_restricted, t.created_at, t.created_by_admin
      FROM app.tags t
    """
    params: list[object] = []
    conditions: list[str] = []
    if query:
        like = f"%{query}%"
        conditions.append("(t.slug ILIKE %s OR t.label ILIKE %s)")
        params.extend([like, like])
    if not is_admin and visibility_enabled:
        clause, clause_params = build_access_clause("t", account_id)
        conditions.append(clause)
        params.extend(clause_params)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY t.created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    redis = get_redis(request)
    cache_key = None
    if redis and is_admin:
        cache_key = f"tags:list:{query or ''}:{limit}:{offset}"
        try:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            cache_key = None

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, tuple(params))
            rows = await cur.fetchall()
    payload = [
        {
            "id": str(r[0]),
            "slug": r[1],
            "label": r[2],
            "is_banned": r[3],
            "is_restricted": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
            "created_by_admin": bool(r[6]) if len(r) > 6 else False,
        }
        for r in rows
    ]
    if redis and cache_key:
        try:
            await redis.set(cache_key, json.dumps(payload), ex=CACHE_TTL_SECONDS)
        except Exception:
            pass
    return payload


@router.get("/admin/groups", response_model=TagGroupOut)
async def list_admin_tag_groups(
    pool = Depends(get_pool),
    _: None = Depends(require_admin),
):
    language_slugs = [slug.lower() for slug in LANGUAGE_TAG_SLUGS]
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT t.id, t.slug, t.label, t.is_banned, t.is_restricted, t.created_at, t.created_by_admin
                FROM app.tags t
                WHERE NOT (LOWER(t.slug) = ANY(%s))
                  AND NOT EXISTS (
                    SELECT 1 FROM app.accounts a
                    WHERE LOWER(a.handle) = LOWER(t.slug)
                  )
                ORDER BY t.label ASC
                """,
                (language_slugs,),
            )
            rows = await cur.fetchall()

    admin_created: list[TagOut] = []
    user_created: list[TagOut] = []
    for row in rows:
        data = TagOut(
            id=str(row[0]),
            slug=row[1],
            label=row[2],
            is_banned=bool(row[3]),
            is_restricted=bool(row[4]),
            created_at=row[5].isoformat() if row[5] else None,
            created_by_admin=bool(row[6]),
        )
        if data.created_by_admin:
            admin_created.append(data)
        else:
            user_created.append(data)

    return TagGroupOut(admin_created=admin_created, user_created=user_created)


@router.get("/list-top", response_model=list[TagWithCountOut])
async def list_top_tags(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    account_id: Optional[str] = Depends(get_optional_account_id),
    pool = Depends(get_pool),
):
    is_admin = await is_admin_account(pool, account_id)
    visibility_enabled = await tag_visibility_available(pool)

    redis = get_redis(request)
    cache_key = None
    if redis and is_admin:
        cache_key = f"tags:list-top:{limit}"
        try:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            cache_key = None

    sql = """
      SELECT t.id, t.slug, t.label, t.is_banned, t.is_restricted, COALESCE(p.cnt, 0) AS usage_count, t.created_by_admin
      FROM app.tags t
      LEFT JOIN (
        SELECT tag_id, COUNT(*) AS cnt
        FROM app.post_tags
        GROUP BY tag_id
      ) p ON p.tag_id = t.id
      WHERE t.is_banned = false
      ORDER BY usage_count DESC, t.slug ASC
      LIMIT %s
    """

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (limit,))
            rows = await cur.fetchall()

    if not is_admin and visibility_enabled:
        accessible_ids, _ = await fetch_accessible_tag_sets(
            pool,
            account_id,
            is_admin=is_admin,
            visibility_enabled=visibility_enabled,
        )
        rows = [row for row in rows if str(row[0]) in accessible_ids]

    payload = [
        {
            "id": str(r[0]),
            "slug": r[1],
            "label": r[2],
            "is_banned": bool(r[3]),
            "is_restricted": bool(r[4]),
            "usage_count": int(r[5] or 0),
            "created_by_admin": bool(r[6]) if len(r) > 6 else False,
        }
        for r in rows
    ]

    if redis and cache_key:
        try:
            await redis.set(cache_key, json.dumps(payload), ex=CACHE_TTL_SECONDS)
        except Exception:
            pass

    return payload


class OkOut(BaseModel):
    ok: bool = True


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
async def create_tag(
    request: Request,
    body: TagCreateIn,
    _: None = Depends(require_admin),
    pool = Depends(get_pool),
    csrf: bool = Depends(csrf_validate),
):
    label = (body.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="label required")
    slug = make_slug(label)
    if not slug:
        raise HTTPException(status_code=400, detail="invalid label")
    is_restricted = slug not in LANGUAGE_TAG_SLUGS

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO app.tags (id, slug, label, is_restricted, created_by_admin)
                VALUES (gen_random_uuid(), %s, %s, %s, true)
                ON CONFLICT (slug) DO NOTHING
                RETURNING id, slug, label, is_banned, is_restricted, created_at, created_by_admin
                """,
                (slug, label, is_restricted),
            )
            row = await cur.fetchone()
            if not row:
                await cur.execute(
                    "SELECT id, slug, label, is_banned, is_restricted, created_at, created_by_admin FROM app.tags WHERE slug=%s",
                    (slug,),
                )
                row = await cur.fetchone()
            await invalidate_tag_cache(request)
            return {
                "id": str(row[0]),
                "slug": row[1],
                "label": row[2],
                "is_banned": row[3],
                "is_restricted": row[4],
                "created_at": row[5].isoformat() if row[5] else None,
                "created_by_admin": bool(row[6]) if len(row) > 6 else True,
            }


@router.post("/{tag_id}/unrestrict", response_model=TagOut)
async def unrestrict_tag(
    tag_id: str,
    request: Request,
    _: None = Depends(require_admin),
    pool = Depends(get_pool),
    csrf: bool = Depends(csrf_validate),
):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE app.tags
                SET is_restricted = false
                WHERE id = %s
                RETURNING id, slug, label, is_banned, is_restricted, created_at, created_by_admin
                """,
                (tag_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="tag not found")
    await invalidate_tag_cache(request)
    return {
        "id": str(row[0]),
        "slug": row[1],
        "label": row[2],
        "is_banned": row[3],
        "is_restricted": row[4],
        "created_at": row[5].isoformat() if row[5] else None,
        "created_by_admin": bool(row[6]) if len(row) > 6 else False,
    }


@router.post("/{tag_id}/ban", response_model=OkOut)
async def ban_tag(
    tag_id: str,
    request: Request,
    _: None = Depends(require_admin),
    pool = Depends(get_pool),
    csrf: bool = Depends(csrf_validate),
):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE app.tags SET is_banned = true WHERE id = %s", (tag_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="tag not found")
    await invalidate_tag_cache(request)
    return {"ok": True}


@router.post("/{tag_id}/unban", response_model=OkOut)
async def unban_tag(
    tag_id: str,
    request: Request,
    _: None = Depends(require_admin),
    pool = Depends(get_pool),
    csrf: bool = Depends(csrf_validate),
):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("UPDATE app.tags SET is_banned = false WHERE id = %s", (tag_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="tag not found")
    await invalidate_tag_cache(request)
    return {"ok": True}


@router.get("/visibility", response_model=list[TagVisibilityOut])
async def list_tag_visibility(
    request: Request,
    query: Optional[str] = Query(None),
    pool = Depends(get_pool),
    _: None = Depends(require_admin),
):
    sql = """
      SELECT
        t.id,
        t.slug,
        t.label,
        COALESCE(jsonb_agg(DISTINCT jsonb_build_object('id', r.id, 'name', r.name))
                 FILTER (WHERE r.id IS NOT NULL), '[]'::jsonb) AS roles_json,
        COALESCE(jsonb_agg(DISTINCT jsonb_build_object('id', a.id, 'handle', a.handle))
                 FILTER (WHERE a.id IS NOT NULL), '[]'::jsonb) AS accounts_json
      FROM app.tags t
      LEFT JOIN app.tag_visibility tv ON tv.tag_id = t.id
      LEFT JOIN app.roles r ON r.id = tv.role_id
      LEFT JOIN app.accounts a ON a.id = tv.account_id
    """
    params: list[object] = []
    if query:
        sql += " WHERE t.slug ILIKE %s OR t.label ILIKE %s"
        like = f"%{query}%"
        params.extend([like, like])
    sql += " GROUP BY t.id, t.slug, t.label ORDER BY t.slug ASC"

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, tuple(params))
            rows = await cur.fetchall()

    payload: List[TagVisibilityOut] = []
    for row in rows:
        roles_data = row[3] or []
        users_data = row[4] or []
        roles = [
            TagVisibilityRole(id=str(item.get("id")), name=item.get("name") or "")
            for item in roles_data
            if item
        ]
        users = [
            TagVisibilityUser(id=str(item.get("id")), handle=item.get("handle") or "")
            for item in users_data
            if item
        ]
        payload.append(
            TagVisibilityOut(
                tag_id=str(row[0]),
                slug=row[1],
                label=row[2],
                roles=roles,
                users=users,
            )
        )
    return payload


@router.get("/visibility/users/{handle}", response_model=UserTagVisibilityOut)
async def list_user_tag_visibility(
    handle: str,
    pool = Depends(get_pool),
    _: None = Depends(require_admin),
):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, handle FROM app.accounts WHERE lower(handle)=lower(%s) LIMIT 1",
                (handle,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            account_id = str(row[0])
            canonical_handle = row[1]
            await cur.execute(
                """
                SELECT t.id, t.slug, t.label, tv.created_at
                FROM app.tag_visibility tv
                JOIN app.tags t ON t.id = tv.tag_id
                WHERE tv.account_id = %s
                ORDER BY t.slug ASC
                """,
                (account_id,),
            )
            rows = await cur.fetchall()
    assignments = [
        UserTagAssignmentOut(
            tag_id=str(r[0]),
            slug=r[1],
            label=r[2],
            created_at=r[3].isoformat() if r[3] else None,
        )
        for r in rows
    ]
    return UserTagVisibilityOut(account_id=account_id, handle=canonical_handle, tags=assignments)


@router.post("/{tag_id}/visibility/users", response_model=UserTagAssignmentOut)
async def assign_tag_to_user(
    tag_id: str,
    body: TagVisibilityAssignIn,
    pool = Depends(get_pool),
    _: None = Depends(require_admin),
):
    handle = (body.handle or "").strip()
    if not handle:
        raise HTTPException(status_code=400, detail="handle required")
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, slug, label FROM app.tags WHERE id=%s",
                (tag_id,),
            )
            tag_row = await cur.fetchone()
            if not tag_row:
                raise HTTPException(status_code=404, detail="Tag not found")
            await cur.execute(
                "SELECT id FROM app.accounts WHERE lower(handle)=lower(%s) LIMIT 1",
                (handle,),
            )
            account_row = await cur.fetchone()
            if not account_row:
                raise HTTPException(status_code=404, detail="User not found")
            account_id = str(account_row[0])
            await cur.execute(
                "SELECT id, created_at FROM app.tag_visibility WHERE tag_id=%s AND account_id=%s LIMIT 1",
                (tag_id, account_id),
            )
            existing = await cur.fetchone()
            if existing:
                created_at = existing[1]
            else:
                await cur.execute(
                    """
                    INSERT INTO app.tag_visibility (tag_id, account_id)
                    VALUES (%s, %s)
                    RETURNING created_at
                    """,
                    (tag_id, account_id),
                )
                created_at = (await cur.fetchone())[0]
    return UserTagAssignmentOut(
        tag_id=str(tag_row[0]),
        slug=tag_row[1],
        label=tag_row[2],
        created_at=created_at.isoformat() if created_at else None,
    )


@router.delete("/{tag_id}/visibility/users/{handle}", response_model=OkOut)
async def unassign_tag_from_user(
    tag_id: str,
    handle: str,
    pool = Depends(get_pool),
    _: None = Depends(require_admin),
):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM app.tags WHERE id=%s",
                (tag_id,),
            )
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Tag not found")
            await cur.execute(
                "SELECT id FROM app.accounts WHERE lower(handle)=lower(%s) LIMIT 1",
                (handle,),
            )
            account_row = await cur.fetchone()
            if not account_row:
                raise HTTPException(status_code=404, detail="User not found")
            account_id = str(account_row[0])
            await cur.execute(
                "DELETE FROM app.tag_visibility WHERE tag_id=%s AND account_id=%s",
                (tag_id, account_id),
            )
    return OkOut()
