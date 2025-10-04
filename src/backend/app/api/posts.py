from __future__ import annotations

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ..core.db import get_pool
from ..core.config import get_settings
from ..core.deps import get_current_account_id, require_role, require_admin, is_admin_account
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


class PostOut(BaseModel):
    id: str
    title: str
    body_md: str
    lang: Optional[str] = None
    visibility: str
    score: int
    reply_count: int
    created_at: Optional[str] = None
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
    logger.info(f"List posts request: limit={limit}, offset={offset}, cursor={cursor}, sort={sort}, tag={tag}, q={q}, account_id={account_id}")
    
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

    if tag:
        try:
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT slug FROM app.tags WHERE slug = ANY(%s)", (tag,))
                    existing_tags = [row[0] for row in await cur.fetchall()]
                    missing_tags = set(tag) - set(existing_tags)
                    if missing_tags:
                        logger.warning(f"Tag(s) not found: {missing_tags}")
                        raise HTTPException(status_code=404, detail=f"Tag(s) not found: {', '.join(missing_tags)}")
        except Exception as e:
            logger.error(f"Error validating tags: {str(e)}")
            raise HTTPException(status_code=500, detail="Tag validation failed")

    order_clause = "p.created_at DESC"
    if sort == "top":
        order_clause = "p.score DESC, p.created_at DESC"
    if search_query:
        order_clause = f"search_rank DESC, {order_clause}"

    params: list[object] = []
    cursor_condition = ""
    if cursor and not offset:
        cursor_condition = " AND p.created_at < %s::timestamptz"

    try:
        if tag:
            sql = f"""
              SELECT p.id, p.title, p.body_md, p.lang, p.visibility, p.score, p.reply_count,
                     p.created_at, a.handle AS author,
                     COALESCE(
                       json_agg(DISTINCT jsonb_build_object('id', t.id, 'slug', t.slug, 'label', t.label))
                       FILTER (WHERE t.id IS NOT NULL), '[]') AS tags,
                     {highlight_select},
                     {rank_select}
              FROM app.posts p
              LEFT JOIN app.accounts a ON a.id = p.author_id
              JOIN app.post_tags pt ON pt.post_id = p.id
              JOIN app.tags t ON t.id = pt.tag_id
              WHERE p.deleted_at IS NULL AND t.slug = ANY(%s::text[])
              {search_condition}
              {cursor_condition}
              GROUP BY p.id, p.title, p.body_md, p.lang, p.visibility, p.score, p.reply_count, p.created_at, a.handle
              HAVING COUNT(DISTINCT t.slug) = %s
              ORDER BY {order_clause}
              LIMIT %s OFFSET %s
            """

            if search_query:
                params.extend([search_query, search_query])
            params.append(tag)
            if search_query:
                params.append(search_query)
            if cursor and not offset:
                params.append(cursor)
                offset_to_use = 0
            else:
                offset_to_use = offset
            params.extend([len(tag), limit, offset_to_use])

            count_sql = f"""
              SELECT COUNT(*) FROM (
                SELECT p.id
                FROM app.posts p
                JOIN app.post_tags pt ON pt.post_id = p.id
                JOIN app.tags t ON t.id = pt.tag_id
                WHERE p.deleted_at IS NULL AND t.slug = ANY(%s::text[])
                {count_search_condition}
                GROUP BY p.id
                HAVING COUNT(DISTINCT t.slug) = %s
              ) x
            """
            count_params = [tag]
            if search_query:
                count_params.append(search_query)
            count_params.append(len(tag))
        else:
            sql = f"""
              SELECT p.id, p.title, p.body_md, p.lang, p.visibility, p.score, p.reply_count,
                     p.created_at, a.handle AS author,
                     COALESCE(
                       json_agg(DISTINCT jsonb_build_object('id', t.id, 'slug', t.slug, 'label', t.label))
                       FILTER (WHERE t.id IS NOT NULL), '[]') AS tags,
                     {highlight_select},
                     {rank_select}
              FROM app.posts p
              LEFT JOIN app.accounts a ON a.id = p.author_id
              LEFT JOIN app.post_tags pt ON pt.post_id = p.id
              LEFT JOIN app.tags t ON t.id = pt.tag_id
              WHERE p.deleted_at IS NULL
              {search_condition}
              {cursor_condition}
              GROUP BY p.id, p.title, p.body_md, p.lang, p.visibility, p.score, p.reply_count, p.created_at, a.handle
              ORDER BY {order_clause}
              LIMIT %s OFFSET %s
            """

            if search_query:
                params.extend([search_query, search_query])
                params.append(search_query)
                if cursor and not offset:
                    params.append(cursor)
                    offset_to_use = 0
                else:
                    offset_to_use = offset
                params.extend([limit, offset_to_use])
            else:
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
                GROUP BY p.id
              ) x
            """
            count_params = []
            if search_query:
                count_params.append(search_query)

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
    if body.visibility not in ("logged_in", "private", "unlisted"):
        raise HTTPException(status_code=422, detail="invalid visibility")

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
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
            # Auto-attach language tag based on user's locale (e.g., 'en', 'de')
            try:
                await cur.execute("SELECT locale, handle FROM app.accounts WHERE id=%s", (account_id,))
                row_loc = await cur.fetchone()
                locale = (row_loc[0] or '').strip() if row_loc else ''
                author_handle = (row_loc[1] or '').strip() if row_loc else ''
                lang_slug = ''
                if locale:
                    # Take primary language code before '-' and lowercase
                    lang_slug = locale.split('-')[0].split('_')[0].lower()
                    # Limit to EU languages we support
                    eu_langs = {
                        'bg','hr','cs','da','nl','en','et','fi','fr','de','el','hu','ga','it','lv','lt','mt','pl','pt','ro','sk','sl','es','sv'
                    }
                    if lang_slug not in eu_langs:
                        lang_slug = ''
                if lang_slug:
                    # Ensure tag exists (create if missing)
                    await cur.execute("SELECT id FROM app.tags WHERE slug=%s LIMIT 1", (lang_slug,))
                    r = await cur.fetchone()
                    if r:
                        tag_id = r[0]
                    else:
                        # Minimal label = uppercased slug (e.g., EN)
                        label = lang_slug.upper()
                        await cur.execute(
                            """
                            INSERT INTO app.tags (id, slug, label)
                            VALUES (gen_random_uuid(), %s, %s)
                            ON CONFLICT (slug) DO NOTHING
                            RETURNING id
                            """,
                            (lang_slug, label),
                        )
                        r2 = await cur.fetchone()
                        if r2:
                            tag_id = r2[0]
                        else:
                            await cur.execute("SELECT id FROM app.tags WHERE slug=%s LIMIT 1", (lang_slug,))
                            tag_id = (await cur.fetchone())[0]
                    # Attach the language tag to the post (ignore if already attached)
                    await cur.execute(
                        """
                        INSERT INTO app.post_tags (post_id, tag_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (new_id, tag_id),
                    )

                # Also auto-tag with the author's handle as a slug (e.g., user1)
                handle_slug = ''
                if author_handle:
                    s = author_handle.lower()
                    # sanitize into slug: alnum and -_. ; spaces -> '-'
                    handle_slug = ''.join(ch if (ch.isalnum() or ch in '-_.') else ('-' if ch.isspace() else '-') for ch in s).strip('-')
                    if not handle_slug:
                        handle_slug = ''
                if handle_slug:
                    await cur.execute("SELECT id FROM app.tags WHERE slug=%s LIMIT 1", (handle_slug,))
                    r = await cur.fetchone()
                    if r:
                        handle_tag_id = r[0]
                    else:
                        label = author_handle
                        await cur.execute(
                            """
                            INSERT INTO app.tags (id, slug, label)
                            VALUES (gen_random_uuid(), %s, %s)
                            ON CONFLICT (slug) DO NOTHING
                            RETURNING id
                            """,
                            (handle_slug, label),
                        )
                        r2 = await cur.fetchone()
                        if r2:
                            handle_tag_id = r2[0]
                        else:
                            await cur.execute("SELECT id FROM app.tags WHERE slug=%s LIMIT 1", (handle_slug,))
                            handle_tag_id = (await cur.fetchone())[0]
                    await cur.execute(
                        """
                        INSERT INTO app.post_tags (post_id, tag_id)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (new_id, handle_tag_id),
                    )
            except Exception:
                # Non-fatal: if tagging fails, continue without blocking post creation
                pass
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
    return OkOut()


@router.delete("/reply/{reply_id}", response_model=OkOut)
async def delete_reply(reply_id: str, account_id: str = Depends(get_current_account_id), pool = Depends(get_pool)):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT author_id FROM app.replies WHERE id=%s AND deleted_at IS NULL",
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
            admin = await is_admin_account(pool, account_id)
            if not (is_owner or admin):
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
                    INSERT INTO app.tags (id, slug, label, is_restricted)
                    VALUES (gen_random_uuid(), %s, %s, false)
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
    _: str = Depends(get_current_account_id),  # any logged-in user
    pool = Depends(get_pool),
    csrf: bool = Depends(csrf_validate),
):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM app.post_tags WHERE post_id=%s AND tag_id=%s", (post_id, tag_id))
    return {"ok": True}


@router.get("/{post_id}", response_model=PostOut)
async def get_post(post_id: str, account_id: str = Depends(get_current_account_id), pool = Depends(get_pool)):
    sql = """
      SELECT p.id, p.title, p.body_md, p.lang, p.visibility, p.score, p.reply_count,
             p.created_at, a.handle AS author
      FROM app.posts p
      LEFT JOIN app.accounts a ON a.id = p.author_id
      WHERE p.id = %s AND p.deleted_at IS NULL
      LIMIT 1
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, (post_id,))
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Post not found")
    return {
        "id": str(row[0]),
        "title": row[1],
        "body_md": row[2],
        "lang": row[3],
        "visibility": row[4],
        "score": row[5],
        "reply_count": row[6],
        "created_at": row[7].isoformat() if row[7] else None,
        "author": row[8],
    }


@router.get("/{post_id}/tags", response_model=List[PostTagOut])
async def list_post_tags(post_id: str, account_id: str = Depends(get_current_account_id), pool = Depends(get_pool)):
    sql = """
      SELECT t.id, t.slug, t.label, t.is_banned, t.created_at
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
            "is_banned": r[3],
            "created_at": r[4].isoformat() if r[4] else None,
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
