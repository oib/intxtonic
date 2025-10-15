from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from .security import decode_access_token
from .db import get_pool


def _get_token_from_header(request: Request) -> Optional[str]:
    # Prefer Authorization header, but fall back to httpOnly cookie set by auth endpoints
    # Cookie value is stored as "Bearer <token>" in auth.py
    auth = request.headers.get("Authorization") or request.cookies.get("access_token")
    if not auth:
        return None
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    # In case the cookie stores the raw token without the Bearer prefix
    if len(parts) == 1 and "." in parts[0]:  # crude check for JWT-like token
        return parts[0]
    return None


async def get_current_account_id(request: Request) -> str:
    token = _get_token_from_header(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    try:
        data = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    sub = data.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return sub


async def get_optional_account_id(request: Request) -> Optional[str]:
    token = _get_token_from_header(request)
    if not token:
        return None
    try:
        data = decode_access_token(token)
    except Exception:
        return None
    sub = data.get("sub")
    return sub if sub else None


async def require_role(request: Request, role: str) -> None:
    # Ensure the account has role via DB lookup
    account_id = await get_current_account_id(request)
    pool = get_pool(request)
    query = """
        SELECT 1
        FROM app.account_roles ar
        JOIN app.roles r ON r.id = ar.role_id
        WHERE ar.account_id = %s AND r.name = %s
        LIMIT 1
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (account_id, role))
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


# Typed helpers for common roles to be used in Depends() to avoid 422 due to untyped lambda params
async def require_admin(request: Request) -> None:
    await require_role(request, "admin")


async def require_moderator(request: Request) -> None:
    await require_role(request, "moderator")


async def require_admin_or_moderator(request: Request) -> None:
    account_id = await get_current_account_id(request)
    pool = get_pool(request)
    query = """
        SELECT 1
        FROM app.account_roles ar
        JOIN app.roles r ON r.id = ar.role_id
        WHERE ar.account_id = %s AND r.name IN ('admin', 'moderator')
        LIMIT 1
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (account_id,))
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


async def is_admin_account(pool, account_id: Optional[str]) -> bool:
    if not account_id:
        return False
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT 1
                FROM app.account_roles ar
                JOIN app.roles r ON r.id = ar.role_id
                WHERE ar.account_id = %s AND r.name = 'admin'
                LIMIT 1
                """,
                (account_id,),
            )
            row = await cur.fetchone()
    return bool(row)
