from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..core.db import get_pool
from ..core.config import get_settings
from ..core.deps import get_current_account_id, require_role, require_admin, is_admin_account
from ..core.tag_access import build_access_clause, fetch_accessible_tag_sets, tag_visibility_available
from ..core.notify import publish
from .auth import csrf_validate
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posts", tags=["posts"]) 

from .tags import make_slug


class PostTagOut(BaseModel):
    id: str
    slug: str
    label: str
    domain: str


class PostOut(BaseModel):
    id: str
    title: str
    body_md: str
    lang: Optional[str] = None
    visibility: str
    score: int
    reply_count: int
    created_at: Optional[str] = None
    author_id: Optional[str] = None
    author: Optional[str] = None
    tags: List[PostTagOut] = []
    highlight: Optional[str] = None


class PostsPage(BaseModel):
    items: List[PostOut]
    limit: int
    offset: int
    sort: str
    total: int
    next_cursor: Optional[str] = None


class PostPreviewOut(BaseModel):
    id: str
    title: str
    excerpt: str
    created_at: Optional[str] = None
    author: Optional[str] = None
    lang: Optional[str] = None


class PostCreateIn(BaseModel):
    title: str
    body_md: str
    lang: Optional[str] = "en"
    visibility: str = "logged_in"


@router.get("", response_model=PostsPage)
async def list_posts(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    cursor: Optional[str] = Query(None),
    sort: str = Query("newest"),
    tag: Optional[List[str]] = Query(None),
    q: Optional[str] = Query(None),
    account_id: str = Depends(get_current_account_id),
    pool = Depends(get_pool),
):
    logger.info(
        "List posts request",
        extra={
            "limit": limit,
            "offset": offset,
            "cursor": cursor,
            "sort": sort,
            "tags": tag,
            "query": q,
            "account_id": account_id,
        },
    )
    
    # Validate/normalize cursor if provided; be lenient and ignore invalid
    if cursor:
        try:
            # Normalize 'Z' to '+00:00' then parse
            c = cursor.strip()
            if c.endswith('Z'):
                c = c[:-1] + '+00:00'
            cursor_dt = datetime.fromisoformat(c)
            # Use ISO string with offset preserved
            cursor = cursor_dt.isoformat()
        except Exception as e:
            logger.warning(f"Cursor parsing failed, ignoring cursor: value='{cursor}', err={e}")
            cursor = None
    
    # Validate tags if provided and check existence
    search_query: Optional[str] = None
    if q:
        sq = q.strip()
        if sq:
            search_query = sq

    search_vector = "to_tsvector('simple', coalesce(p.title,'') || ' ' || coalesce(p.body_md,''))"
    highlight_select = "NULL::text AS highlight"
    rank_select = "0::float AS search_rank"
    search_condition = ""
    count_search_condition = ""
    if search_query:
        highlight_select = (
            "ts_headline('simple', p.body_md, plainto_tsquery('simple', %s), "
            "'MaxFragments=1, ShortWord=0, MaxWords=35, MinWords=10, FragmentDelimiter=…') AS highlight"
        )
        rank_select = f"ts_rank_cd({search_vector}, plainto_tsquery('simple', %s)) AS search_rank"
        search_condition = f" AND {search_vector} @@ plainto_tsquery('simple', %s)"
        count_search_condition = f" AND {search_vector} @@ plainto_tsquery('simple', %s)"
        cursor = None  # disable cursor pagination when searching

    tag_alias = "t"
    tag_list: Optional[list[str]] = None
    original_tags = list(tag or [])
    has_bookmarked_filter = False
    if original_tags:
        cleaned: list[str] = []
        seen: set[str] = set()
        for slug in original_tags:
            if slug == "bookmarked":
                has_bookmarked_filter = True
                continue
            if slug in seen:
                continue
            seen.add(slug)
            cleaned.append(slug)
        if cleaned:
            tag_list = cleaned

    # Skip pre-validation of tag slugs; unknown tags will simply yield 0 results in the main query

    # Admins can see all tags; only enforce visibility for non-admins when enabled
    is_admin = await is_admin_account(pool, account_id)
    visibility_enabled = await tag_visibility_available(pool)
    if tag_list and (not is_admin) and visibility_enabled:
        try:
            _, accessible_slugs = await fetch_accessible_tag_sets(pool, account_id)
        except Exception as e:
            logger.exception("Failed to fetch accessible tags", extra={"account_id": account_id})
            raise HTTPException(status_code=500, detail="Unable to verify tag permissions")
        inaccessible = [slug for slug in tag_list if slug not in accessible_slugs]
        if inaccessible:
            raise HTTPException(status_code=403, detail=f"Tag access forbidden: {', '.join(inaccessible)}")

    order_clause = "p.created_at DESC"
    if sort == "top":
        order_clause = "p.score DESC, p.created_at DESC"
    if search_query:
        order_clause = f"search_rank DESC, {order_clause}"

    params: list[object] = []
    cursor_condition = ""
    if cursor and not offset:
        cursor_condition = " AND p.created_at < %s::timestamptz"

    if is_admin or not visibility_enabled:
        access_clause_tag, access_params_tag = "TRUE", []
        access_clause_any, access_params_any = "TRUE", []
    else:
        access_clause_tag, access_params_tag = build_access_clause(tag_alias, account_id)
        access_clause_any, access_params_any = build_access_clause("t2", account_id)

    try:
        if has_bookmarked_filter and not tag_list:
            sql = f"""
              SELECT p.id, p.title, p.body_md, p.lang, p.visibility, p.score, p.reply_count,
                     p.created_at, a.handle AS author,
                     '[]'::jsonb AS tags,
                     {highlight_select},
                     {rank_select}
              FROM app.bookmarks b
              JOIN app.posts p ON p.id = b.target_id
              LEFT JOIN app.accounts a ON a.id = p.author_id
              WHERE b.account_id = %s AND b.target_type = 'post' AND p.deleted_at IS NULL
              {search_condition}
              {cursor_condition}
              ORDER BY {order_clause}
              LIMIT %s OFFSET %s
            """

            if search_query:
                params.append(search_query)  # for highlight_select
                params.append(search_query)  # for rank_select
            params.append(account_id)       # for b.account_id = %s
            if search_query:
                params.append(search_query)  # for search_condition
            if cursor and not offset:
                params.append(cursor)
                offset_to_use = 0
            else:
                offset_to_use = offset
            params.extend([limit, offset_to_use])

            count_sql = f"""
              SELECT COUNT(*)
              FROM app.bookmarks b
              JOIN app.posts p ON p.id = b.target_id
              WHERE b.account_id = %s AND b.target_type = 'post' AND p.deleted_at IS NULL
              {count_search_condition}
            """
            count_params = [account_id]
            if search_query:
                count_params.append(search_query)

        elif tag_list:
            sql = f"""
              SELECT p.id, p.title, p.body_md, p.lang, p.visibility, p.score, p.reply_count,
                     p.created_at, a.handle AS author,
                     COALESCE(
                       json_agg(DISTINCT jsonb_build_object('id', t.id, 'slug', t.slug, 'label', t.label, 'domain', t.domain))
                       FILTER (WHERE t.id IS NOT NULL), '[]') AS tags,
                     {highlight_select},
                     {rank_select}
              FROM app.posts p
              LEFT JOIN app.accounts a ON a.id = p.author_id
              JOIN app.post_tags pt ON pt.post_id = p.id
              JOIN app.tags t ON t.id = pt.tag_id
              WHERE p.deleted_at IS NULL AND t.slug = ANY(%s::text[])
              {search_condition}
              AND {access_clause_tag}
              {cursor_condition}
              GROUP BY p.id, p.title, p.body_md, p.lang, p.visibility, p.score, p.reply_count, p.created_at, a.handle
              HAVING COUNT(DISTINCT t.slug) = %s
              ORDER BY {order_clause}
              LIMIT %s OFFSET %s
            """

            if search_query:
                params.append(search_query)  # for highlight_select
                params.append(search_query)  # for rank_select
            params.append(list(tag_list))
            if search_query:
                params.append(search_query)
            params.extend(access_params_tag)
            if cursor and not offset:
                params.append(cursor)
                offset_to_use = 0
            else:
                offset_to_use = offset
            params.append(len(tag_list))
            params.extend([limit, offset_to_use])

            count_sql = f"""
              SELECT COUNT(*) FROM (
                SELECT p.id
                FROM app.posts p
                JOIN app.post_tags pt ON pt.post_id = p.id
                JOIN app.tags t ON t.id = pt.tag_id
                WHERE p.deleted_at IS NULL AND t.slug = ANY(%s::text[])
                {count_search_condition}
                AND {access_clause_tag}
                GROUP BY p.id
                HAVING COUNT(DISTINCT t.slug) = %s
              ) x
            """
            count_params = [list(tag_list)]
            if search_query:
                count_params.append(search_query)
            count_params.extend(access_params_tag)
            count_params.append(len(tag_list))
        else:
            sql = f"""
              SELECT p.id, p.title, p.body_md, p.lang, p.visibility, p.score, p.reply_count,
                     p.created_at, a.handle AS author,
                     COALESCE(
                       json_agg(DISTINCT jsonb_build_object('id', t.id, 'slug', t.slug, 'label', t.label, 'domain', t.domain))
                       FILTER (WHERE t.id IS NOT NULL), '[]') AS tags,
                     {highlight_select},
                     {rank_select}
              FROM app.posts p
              LEFT JOIN app.accounts a ON a.id = p.author_id
              LEFT JOIN app.post_tags pt ON pt.post_id = p.id
              LEFT JOIN app.tags t ON t.id = pt.tag_id
              WHERE p.deleted_at IS NULL
              {search_condition}
              AND (
                NOT EXISTS (
                  SELECT 1 FROM app.post_tags pt2
                  JOIN app.tags t2 ON t2.id = pt2.tag_id
                  WHERE pt2.post_id = p.id AND NOT ({access_clause_any})
                )
              )
              {cursor_condition}
              GROUP BY p.id, p.title, p.body_md, p.lang, p.visibility, p.score, p.reply_count, p.created_at, a.handle
              ORDER BY {order_clause}
              LIMIT %s OFFSET %s
            """

            if search_query:
                params.extend([search_query, search_query])
                params.append(search_query)
                params.extend(access_params_any)
                if cursor and not offset:
                    params.append(cursor)
                    offset_to_use = 0
                else:
                    offset_to_use = offset
                params.extend([limit, offset_to_use])
            else:
                params.extend(access_params_any)
                if cursor and not offset:
                    params.append(cursor)
                    offset_to_use = 0
                else:
                    offset_to_use = offset
                params.extend([limit, offset_to_use])

            count_sql = f"""
              SELECT COUNT(*) FROM (
                SELECT p.id
                FROM app.posts p
                WHERE p.deleted_at IS NULL
                {count_search_condition}
                AND (
                  NOT EXISTS (
                    SELECT 1 FROM app.post_tags pt2
                    JOIN app.tags t2 ON t2.id = pt2.tag_id
                    WHERE pt2.post_id = p.id AND NOT ({access_clause_any})
                  )
                )
                GROUP BY p.id
              ) x
            """
            count_params = []
            if search_query:
                count_params.append(search_query)
            count_params.extend(access_params_any)

        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute(count_sql, tuple(count_params))
                    total = (await cur.fetchone())[0]
                    await cur.execute(sql, tuple(params))
                    rows = await cur.fetchall()
                except Exception as db_err:
                    logger.error(f"Database error in list_posts: query={sql}, params={params}, error={str(db_err)}")
                    raise HTTPException(status_code=500, detail="Database query failed: check server logs")
        items = [
            {
                "id": str(r[0]),
                "title": r[1],
                "body_md": r[2],
                "lang": r[3],
                "visibility": r[4],
                "score": r[5],
                "reply_count": r[6],
                "created_at": r[7].isoformat() if isinstance(r[7], datetime) else (r[7] if isinstance(r[7], str) else None),
                "author": r[8],
                "tags": r[9] or [],
                "highlight": r[10] if r[10] else None,
            }
            for r in rows
        ]
        next_cursor = None
        if search_query:
            next_cursor = None
        elif len(items) == limit and total > (offset + limit):
            # created_at in items is already an ISO string
            next_cursor = items[-1]["created_at"] if items else None
        return {"items": items, "limit": limit, "offset": offset, "sort": sort, "total": total, "next_cursor": next_cursor}
    except HTTPException as he:
        raise he  # Re-raise HTTP exceptions for FastAPI to handle
    except Exception as e:
        logger.error(f"Unexpected error in list_posts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/public/latest", response_model=list[PostPreviewOut])
async def list_public_latest_posts(limit: int = Query(5, ge=1, le=10), pool = Depends(get_pool)):
    sql = """
      SELECT p.id, p.title, p.body_md, p.created_at, a.handle, p.lang
      FROM app.posts p
      LEFT JOIN app.accounts a ON a.id = p.author_id
      WHERE p.deleted_at IS NULL AND p.visibility IN ('logged_in', 'public')
      ORDER BY p.created_at DESC
      LIMIT %s
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (limit,))
            rows = await cur.fetchall()
    previews: list[PostPreviewOut] = []
    for row in rows:
        body_raw = row[2] or ""
        excerpt = " ".join(body_raw.split())
        if len(excerpt) > 180:
            excerpt = excerpt[:180].rstrip() + "…"
        previews.append(
            PostPreviewOut(
                id=str(row[0]),
                title=row[1] or "Untitled",
                excerpt=excerpt,
                created_at=row[3].isoformat() if row[3] else None,
                author=row[4],
                lang=row[5],
            )
        )
    return previews


class IdOut(BaseModel):
    id: str


class OkOut(BaseModel):
    ok: bool = True


@router.post("", response_model=IdOut)
async def create_post(body: PostCreateIn, account_id: str = Depends(get_current_account_id), pool = Depends(get_pool), csrf: bool = Depends(csrf_validate)):
    title = (body.title or "").strip()
    text = (body.body_md or "").strip()
    if not title or not text:
        raise HTTPException(status_code=400, detail="title and body_md required")
    if len(text) > 1200:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Post body too long (max 1200 characters)")
    if body.visibility not in ("logged_in", "private", "unlisted"):
        raise HTTPException(status_code=422, detail="invalid visibility")

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Get user info for auto-tagging and notification
            await cur.execute(
                "SELECT handle, locale FROM app.accounts WHERE id=%s",
                (account_id,)
            )
            user_row = await cur.fetchone()
            if not user_row:
                raise HTTPException(status_code=404, detail="User not found")
            author_handle, user_locale = user_row[0], user_row[1] or "en"
            
            # Rate limit check (posts/day)
            settings = get_settings()
            await cur.execute(
                """
                WITH lim AS (
                  SELECT COALESCE(ul.max_posts_per_day, %s) AS max_posts,
                         COALESCE(ul.max_replies_per_day, %s) AS max_replies
                  FROM app.user_limits ul
                  WHERE ul.account_id = %s
                ), c AS (
                  SELECT posts_count, replies_count
                  FROM app.rate_limits
                  WHERE account_id = %s AND day_utc = (now() at time zone 'UTC')::date
                )
                SELECT COALESCE((SELECT max_posts FROM lim), %s) AS max_posts,
                       COALESCE((SELECT posts_count FROM c), 0) AS posts_count
                """,
                (
                    settings.default_max_posts_per_day,
                    settings.default_max_replies_per_day,
                    account_id,
                    account_id,
                    settings.default_max_posts_per_day,
                ),
            )
            row = await cur.fetchone()
            max_posts, posts_count = row[0], row[1]
            if posts_count >= max_posts:
                raise HTTPException(status_code=429, detail="Daily post limit reached")
            await cur.execute(
                """
                INSERT INTO app.posts (id, author_id, title, body_md, lang, visibility)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (account_id, title, text, body.lang if body.lang else "en", body.visibility),
            )
            new_id = (await cur.fetchone())[0]
            
            # Auto-tag: user handle tag
            handle_slug = make_slug(author_handle)
            if handle_slug:
                await cur.execute(
                    """
                    INSERT INTO app.tags (id, slug, label, domain, is_restricted, created_by_admin)
                    VALUES (gen_random_uuid(), %s, %s, 'user_handle', false, false)
                    ON CONFLICT (slug) DO NOTHING
                    RETURNING id
                    """,
                    (handle_slug, author_handle),
                )
                tag_row = await cur.fetchone()
                if tag_row:
                    handle_tag_id = tag_row[0]
                else:
                    await cur.execute("SELECT id FROM app.tags WHERE slug=%s", (handle_slug,))
                    handle_tag_id = (await cur.fetchone())[0]
                
                await cur.execute(
                    "INSERT INTO app.post_tags (post_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (new_id, handle_tag_id),
                )
            
            # Auto-tag: user default language tag
            if user_locale and user_locale != "en":
                lang_slug = make_slug(user_locale)
                if lang_slug:
                    lang_name = user_locale.upper()
                    # Map common language codes to names
                    lang_names = {
                        'de': 'German', 'fr': 'French', 'es': 'Spanish', 'it': 'Italian',
                        'pt': 'Portuguese', 'nl': 'Dutch', 'pl': 'Polish', 'ru': 'Russian',
                        'ja': 'Japanese', 'ko': 'Korean', 'zh': 'Chinese', 'ar': 'Arabic',
                        'hi': 'Hindi', 'tr': 'Turkish', 'sv': 'Swedish', 'no': 'Norwegian',
                        'da': 'Danish', 'fi': 'Finnish', 'cs': 'Czech', 'sk': 'Slovak',
                        'hu': 'Hungarian', 'ro': 'Romanian', 'bg': 'Bulgarian', 'hr': 'Croatian',
                        'sr': 'Serbian', 'sl': 'Slovenian', 'et': 'Estonian', 'lv': 'Latvian',
                        'lt': 'Lithuanian', 'el': 'Greek', 'he': 'Hebrew', 'th': 'Thai',
                        'vi': 'Vietnamese', 'uk': 'Ukrainian', 'be': 'Belarusian'
                    }
                    lang_name = lang_names.get(user_locale, lang_name)
                    
                    await cur.execute(
                        """
                        INSERT INTO app.tags (id, slug, label, domain, is_restricted, created_by_admin)
                        VALUES (gen_random_uuid(), %s, %s, 'language', false, false)
                        ON CONFLICT (slug) DO NOTHING
                        RETURNING id
                        """,
                        (lang_slug, lang_name),
                    )
                    tag_row = await cur.fetchone()
                    if tag_row:
                        lang_tag_id = tag_row[0]
                    else:
                        await cur.execute("SELECT id FROM app.tags WHERE slug=%s", (lang_slug,))
                        lang_tag_id = (await cur.fetchone())[0]
                    
                    await cur.execute(
                        "INSERT INTO app.post_tags (post_id, tag_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (new_id, lang_tag_id),
                    )
            
            # Bump posts_count
            await cur.execute(
                """
                INSERT INTO app.rate_limits (account_id, day_utc, posts_count, replies_count)
                VALUES (%s, (now() at time zone 'UTC')::date, 1, 0)
                ON CONFLICT (account_id, day_utc)
                DO UPDATE SET posts_count = app.rate_limits.posts_count + 1
                """,
                (account_id,),
            )
    # Fire-and-forget notification (no await needed here but we keep async)
    try:
        await publish({
            "type": "post_created",
            "id": str(new_id),
            "title": title,
            "author": author_handle,
        })
    except Exception:
        pass
    return {"id": str(new_id)}


@router.delete("/{post_id}", response_model=OkOut)
async def delete_post(post_id: str, account_id: str = Depends(get_current_account_id), pool = Depends(get_pool)):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT author_id FROM app.posts WHERE id=%s AND deleted_at IS NULL",
                (post_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Post not found")
            author_id = str(row[0]) if row[0] is not None else None
            if author_id != account_id:
                raise HTTPException(status_code=403, detail="Not allowed to delete this post")
            await cur.execute(
                "UPDATE app.posts SET deleted_at = now() WHERE id=%s",
                (post_id,),
            )
            await cur.execute(
                "DELETE FROM app.translations WHERE source_type = 'post' AND source_id = %s",
                (post_id,),
            )
    return OkOut()


@router.delete("/reply/{reply_id}", response_model=OkOut)
async def delete_reply(reply_id: str, account_id: str = Depends(get_current_account_id), pool = Depends(get_pool)):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT author_id, post_id FROM app.replies WHERE id=%s AND deleted_at IS NULL",
                (reply_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Reply not found")
            author_id = str(row[0]) if row[0] is not None else None
            if author_id != account_id:
                raise HTTPException(status_code=403, detail="Not allowed to delete this reply")
            await cur.execute(
                "UPDATE app.replies SET deleted_at = now() WHERE id=%s",
                (reply_id,),
            )
            await cur.execute(
                "DELETE FROM app.translations WHERE source_type = 'reply' AND source_id = %s",
                (reply_id,),
            )
    return OkOut()


class ReplyCreateIn(BaseModel):
    post_id: str
    body_md: str
    parent_id: Optional[str] = None
    lang: Optional[str] = "en"


class ReplyOut(BaseModel):
    id: str
    parent_id: Optional[str] = None
    author_id: Optional[str] = None
    author: Optional[str] = None
    body_md: str
    lang: Optional[str] = None
    score: int
    created_at: Optional[str] = None


@router.post("/reply", response_model=ReplyOut)
async def create_reply(
    body: ReplyCreateIn,
    account_id: str = Depends(get_current_account_id),
    pool = Depends(get_pool),
    csrf: bool = Depends(csrf_validate),
):
    text = (body.body_md or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="body_md required")

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            settings = get_settings()
            await cur.execute(
                """
                WITH lim AS (
                  SELECT COALESCE(ul.max_posts_per_day, %s) AS max_posts,
                         COALESCE(ul.max_replies_per_day, %s) AS max_replies
                  FROM app.user_limits ul
                  WHERE ul.account_id = %s
                ), c AS (
                  SELECT posts_count, replies_count
                  FROM app.rate_limits
                  WHERE account_id = %s AND day_utc = (now() at time zone 'UTC')::date
                )
                SELECT COALESCE((SELECT max_replies FROM lim), %s) AS max_replies,
                       COALESCE((SELECT replies_count FROM c), 0) AS replies_count
                """,
                (
                    settings.default_max_posts_per_day,
                    settings.default_max_replies_per_day,
                    account_id,
                    account_id,
                    settings.default_max_replies_per_day,
                ),
            )
            row = await cur.fetchone()
            max_replies, replies_count = row[0], row[1]
            if replies_count >= max_replies:
                raise HTTPException(status_code=429, detail="Daily reply limit reached")

            await cur.execute(
                """
                INSERT INTO app.replies (id, post_id, parent_id, author_id, body_md, lang)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (body.post_id, body.parent_id, account_id, text, body.lang or "en"),
            )
            new_id = (await cur.fetchone())[0]

            await cur.execute(
                """
                INSERT INTO app.rate_limits (account_id, day_utc, posts_count, replies_count)
                VALUES (%s, (now() at time zone 'UTC')::date, 0, 1)
                ON CONFLICT (account_id, day_utc)
                DO UPDATE SET replies_count = app.rate_limits.replies_count + 1
                """,
                (account_id,),
            )

    return ReplyOut(
        id=str(new_id),
        parent_id=body.parent_id,
        author_id=account_id,
        author=None,
        body_md=text,
        lang=body.lang or "en",
        score=0,
        created_at=None,
    )


class VoteIn(BaseModel):
    target_type: str  # 'post'|'reply'
    target_id: str
    value: int       # -1 or 1


@router.post("/vote", response_model=OkOut)
async def cast_vote(
    body: VoteIn,
    account_id: str = Depends(get_current_account_id),
    pool = Depends(get_pool),
    csrf: bool = Depends(csrf_validate),
):
    if body.target_type not in ("post", "reply"):
        raise HTTPException(status_code=422, detail="invalid target_type")
    if body.value not in (-1, 1):
        raise HTTPException(status_code=422, detail="invalid value")
    logger.info(
        f"Vote attempt: account_id={account_id}, target_type={body.target_type}, target_id={body.target_id}, value={body.value}"
    )
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            if body.target_type == "post":
                await cur.execute(
                    """
                    SELECT value FROM app.votes
                    WHERE account_id=%s AND target_type='post' AND target_id=%s
                    LIMIT 1
                    """,
                    (account_id, body.target_id),
                )
                existing = await cur.fetchone()
                if existing:
                    logger.info(
                        f"Existing vote found for account_id={account_id}, target_type={body.target_type}, target_id={body.target_id}"
                    )
                    raise HTTPException(status_code=409, detail="already voted on this post")
                await cur.execute(
                    """
                    INSERT INTO app.votes (account_id, target_type, target_id, value)
                    VALUES (%s, 'post', %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (account_id, body.target_id, body.value),
                )
                logger.info(
                    f"Vote recorded for account_id={account_id}, target_type={body.target_type}, target_id={body.target_id}, value={body.value}"
                )
                await cur.execute(
                    "UPDATE app.posts SET score = COALESCE(score,0) + %s WHERE id=%s",
                    (body.value, body.target_id),
                )
            else:
                await cur.execute(
                    """
                    SELECT value FROM app.votes
                    WHERE account_id=%s AND target_type='reply' AND target_id=%s
                    LIMIT 1
                    """,
                    (account_id, body.target_id),
                )
                existing = await cur.fetchone()
                if existing:
                    raise HTTPException(status_code=409, detail="already voted on this reply")
                await cur.execute(
                    """
                    INSERT INTO app.votes (account_id, target_type, target_id, value)
                    VALUES (%s, 'reply', %s, %s)
                    """,
                    (account_id, body.target_id, body.value),
                )
                await cur.execute(
                    "UPDATE app.replies SET score = COALESCE(score,0) + %s WHERE id=%s",
                    (body.value, body.target_id),
                )
    return {"ok": True}


class MyVoteOut(BaseModel):
    voted: bool
    value: Optional[int] = None


@router.get("/{post_id}/my-vote", response_model=MyVoteOut)
async def get_my_vote(post_id: str, account_id: str = Depends(get_current_account_id), pool = Depends(get_pool)):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT value FROM app.votes
                WHERE account_id=%s AND target_type='post' AND target_id=%s
                LIMIT 1
                """,
                (account_id, post_id),
            )
            row = await cur.fetchone()
    if row:
        return {"voted": True, "value": int(row[0])}
    return {"voted": False, "value": None}


class TagAttachIn(BaseModel):
    slug: str
    label: Optional[str] = None


@router.post("/{post_id}/tags", response_model=OkOut)
async def attach_tag(
    post_id: str,
    body: TagAttachIn,
    account_id: str = Depends(get_current_account_id),
    pool = Depends(get_pool),
    csrf: bool = Depends(csrf_validate),
):
    raw_slug = (body.slug or "").strip()
    slug = make_slug(raw_slug)
    if not slug:
        raise HTTPException(status_code=400, detail="slug required")
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT author_id FROM app.posts WHERE id=%s AND deleted_at IS NULL",
                (post_id,),
            )
            owner_row = await cur.fetchone()
            if not owner_row:
                raise HTTPException(status_code=404, detail="post not found")
            owner_id = str(owner_row[0]) if owner_row[0] is not None else None
            is_owner = owner_id and owner_id == account_id
            if not is_owner:
                raise HTTPException(status_code=403, detail="only the author can modify tags")
            # find tag and ensure not banned
            await cur.execute("SELECT id, is_banned FROM app.tags WHERE slug=%s", (slug,))
            row = await cur.fetchone()
            if not row:
                label = (body.label or raw_slug or slug).strip()
                if not label:
                    label = slug.replace('-', ' ').replace('_', ' ').replace('.', ' ').title() or slug
                await cur.execute(
                    """
                    INSERT INTO app.tags (id, slug, label, domain, is_restricted, created_by_admin)
                    VALUES (gen_random_uuid(), %s, %s, 'user_created', false, false)
                    ON CONFLICT (slug) DO NOTHING
                    RETURNING id, is_banned
                    """,
                    (slug, label),
                )
                row = await cur.fetchone()
                if not row:
                    await cur.execute("SELECT id, is_banned FROM app.tags WHERE slug=%s", (slug,))
                    row = await cur.fetchone()
                if not row:
                    raise HTTPException(status_code=500, detail="failed to create tag")
            tag_id, is_banned = row[0], row[1]
            if is_banned:
                raise HTTPException(status_code=403, detail="tag is banned")
            # enforce max 7 tags per post
            await cur.execute("SELECT COUNT(*) FROM app.post_tags WHERE post_id=%s", (post_id,))
            cnt = (await cur.fetchone())[0]
            if cnt >= 7:
                raise HTTPException(status_code=400, detail="maximum 7 tags per post")
            await cur.execute(
                """
                INSERT INTO app.post_tags (post_id, tag_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (post_id, tag_id),
            )
    return {"ok": True}


@router.delete("/{post_id}/tags/{tag_id}", response_model=OkOut)
async def detach_tag(
    post_id: str,
    tag_id: str,
    account_id: str = Depends(get_current_account_id),
    pool = Depends(get_pool),
    csrf: bool = Depends(csrf_validate),
):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT author_id FROM app.posts WHERE id=%s AND deleted_at IS NULL",
                (post_id,),
            )
            owner_row = await cur.fetchone()
            if not owner_row:
                raise HTTPException(status_code=404, detail="post not found")
            owner_id = str(owner_row[0]) if owner_row[0] is not None else None
            is_owner = owner_id and owner_id == account_id
            if not is_owner:
                raise HTTPException(status_code=403, detail="only the author can modify tags")
            
            # Check tag domain - only allow removal of user_created tags
            await cur.execute(
                "SELECT domain FROM app.tags WHERE id=%s",
                (tag_id,),
            )
            tag_row = await cur.fetchone()
            if not tag_row:
                raise HTTPException(status_code=404, detail="tag not found")
            
            tag_domain = tag_row[0]
            if tag_domain in ('admin', 'user_handle', 'language'):
                raise HTTPException(status_code=403, detail=f"Cannot remove {tag_domain} tags")
            
            await cur.execute("DELETE FROM app.post_tags WHERE post_id=%s AND tag_id=%s", (post_id, tag_id))
    return {"ok": True}


@router.delete("/{post_id}", response_model=OkOut)
async def delete_post(
    post_id: str,
    account_id: str = Depends(get_current_account_id),
    pool = Depends(get_pool),
    csrf: bool = Depends(csrf_validate),
):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Check if post exists and user is the author
            await cur.execute(
                "SELECT author_id FROM app.posts WHERE id=%s AND deleted_at IS NULL",
                (post_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Post not found")
            
            author_id = str(row[0]) if row[0] else None
            if author_id != account_id:
                raise HTTPException(status_code=403, detail="Only the author can delete their posts")
            
            # Soft delete the post
            await cur.execute(
                "UPDATE app.posts SET deleted_at = NOW() WHERE id=%s",
                (post_id,),
            )
    return {"ok": True}


@router.get("/{post_id}", response_model=PostOut)
async def get_post(post_id: str, account_id: str = Depends(get_current_account_id), pool = Depends(get_pool)):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT p.id, p.title, p.body_md, p.lang, p.visibility, p.score, p.reply_count,
                       p.created_at, p.author_id, a.handle AS author
                FROM app.posts p
                LEFT JOIN app.accounts a ON a.id = p.author_id
                WHERE p.id = %s AND p.deleted_at IS NULL
                LIMIT 1
                """,
                (post_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Post not found")

            # Ensure viewer has access to all tags attached to this post
            await cur.execute(
                """
                SELECT t.id, t.slug, t.domain
                FROM app.post_tags pt
                JOIN app.tags t ON t.id = pt.tag_id
                WHERE pt.post_id = %s
                """,
                (post_id,),
            )
            tags = await cur.fetchall()

    if tags:
        _, accessible_slugs = await fetch_accessible_tag_sets(pool, account_id)
        for tag_row in tags:
            tag_slug = tag_row[1]
            if tag_slug and tag_slug.lower() not in {slug.lower() for slug in accessible_slugs}:
                raise HTTPException(status_code=403, detail="Forbidden")

    return {
        "id": str(row[0]),
        "title": row[1],
        "body_md": row[2],
        "lang": row[3],
        "visibility": row[4],
        "score": row[5],
        "reply_count": row[6],
        "created_at": row[7].isoformat() if row[7] else None,
        "author_id": str(row[8]) if row[8] else None,
        "author": row[9],
    }


@router.get("/{post_id}/tags", response_model=List[PostTagOut])
async def list_post_tags(post_id: str, account_id: str = Depends(get_current_account_id), pool = Depends(get_pool)):
    sql = """
      SELECT t.id, t.slug, t.label, t.domain, t.is_banned, t.created_at
      FROM app.post_tags pt
      JOIN app.tags t ON t.id = pt.tag_id
      WHERE pt.post_id = %s
      ORDER BY t.label ASC
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (post_id,))
            rows = await cur.fetchall()
    return [
        {
            "id": str(r[0]),
            "slug": r[1],
            "label": r[2],
            "domain": r[3],
            "is_banned": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
        }
        for r in rows
    ]


@router.get("/{post_id}/replies", response_model=List[ReplyOut])
async def list_replies(post_id: str, limit: int = 100, offset: int = 0, account_id: str = Depends(get_current_account_id), pool = Depends(get_pool)):
    logger.info(f"Fetching replies for post_id={post_id}, user={account_id}, limit={limit}, offset={offset}")
    try:
        # Check if post exists first
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1 FROM app.posts WHERE id = %s AND deleted_at IS NULL LIMIT 1", (post_id,))
                if not await cur.fetchone():
                    raise HTTPException(status_code=404, detail="Post not found")
        # Proceed with replies query
        sql = """
          SELECT r.id, r.parent_id, r.author_id, a.handle AS author, r.body_md, r.lang, r.score, r.created_at
          FROM app.replies r
          LEFT JOIN app.accounts a ON a.id = r.author_id
          WHERE r.post_id = %s AND r.deleted_at IS NULL
          ORDER BY r.created_at ASC
          LIMIT %s OFFSET %s
        """
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, (post_id, limit, offset))
                rows = await cur.fetchall()
                logger.info(f"Replies query returned {len(rows)} rows for post_id={post_id}")
        return [
            {
                "id": str(r[0]),
                "parent_id": (str(r[1]) if r[1] else None),
                "author_id": (str(r[2]) if r[2] else None),
                "author": r[3],
                "body_md": r[4],
                "lang": r[5],
                "score": r[6],
                "created_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Error loading replies for post_id={post_id}: {str(e)}")
        raise
