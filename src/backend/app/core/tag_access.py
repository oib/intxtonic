from __future__ import annotations

from typing import Optional, Tuple, Set, List

_VISIBILITY_AVAILABLE: Optional[bool] = None

ACCESS_CLAUSE_TEMPLATE = """
(
    {alias}.is_restricted = false
    OR EXISTS (
        SELECT 1
        FROM app.tag_visibility tv
        WHERE tv.tag_id = {alias}.id
          AND (
            tv.account_id = %s
            OR (
                tv.role_id IS NOT NULL
                AND EXISTS (
                    SELECT 1
                    FROM app.account_roles ar
                    WHERE ar.account_id = %s AND ar.role_id = tv.role_id
                )
            )
          )
    )
)
"""


def build_access_clause(alias: str, account_id: Optional[str]) -> Tuple[str, List[object]]:
    if not account_id:
        return (f"{alias}.is_restricted = false", [])
    return (ACCESS_CLAUSE_TEMPLATE.format(alias=alias), [account_id, account_id])


def _rows_to_sets(rows) -> Tuple[Set[str], Set[str]]:
    ids: Set[str] = set()
    slugs: Set[str] = set()
    for row in rows:
        if not row:
            continue
        tag_id = row[0]
        slug = row[1] if len(row) > 1 else None
        if tag_id is not None:
            ids.add(str(tag_id))
        if slug is not None:
            slugs.add(str(slug))
    return ids, slugs


async def tag_visibility_available(pool) -> bool:
    global _VISIBILITY_AVAILABLE
    if _VISIBILITY_AVAILABLE is not None:
        return _VISIBILITY_AVAILABLE
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                  EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'app'
                      AND table_name = 'tags'
                      AND column_name = 'is_restricted'
                  ) AS has_col,
                  to_regclass('app.tag_visibility') IS NOT NULL AS has_table
                """
            )
            row = await cur.fetchone()
    has_col = bool(row and row[0])
    has_table = bool(row and len(row) > 1 and row[1])
    _VISIBILITY_AVAILABLE = bool(has_col and has_table)
    return _VISIBILITY_AVAILABLE


async def fetch_accessible_tag_sets(
    pool,
    account_id: Optional[str],
    is_admin: bool = False,
    visibility_enabled: bool = True,
) -> Tuple[Set[str], Set[str]]:
    if is_admin or not visibility_enabled:
        query = "SELECT id, slug FROM app.tags"
        params: tuple[object, ...] = ()
    elif not account_id:
        query = "SELECT id, slug FROM app.tags WHERE is_restricted = false"
        params = ()
    else:
        query = """
            SELECT id, slug FROM app.tags WHERE is_restricted = false
            UNION
            SELECT t.id, t.slug
            FROM app.tag_visibility tv
            JOIN app.tags t ON t.id = tv.tag_id
            WHERE tv.account_id = %s
            UNION
            SELECT t.id, t.slug
            FROM app.tag_visibility tv
            JOIN app.account_roles ar ON ar.role_id = tv.role_id
            JOIN app.tags t ON t.id = tv.tag_id
            WHERE ar.account_id = %s
        """
        params = (account_id, account_id)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()
    return _rows_to_sets(rows)
