from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, EmailStr

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi import Header, Cookie
import secrets
import hashlib
import logging
from datetime import datetime, timedelta, timezone

from ..core.db import get_pool
from ..core.security import hash_password, verify_password, create_access_token
from ..core.deps import get_current_account_id, require_role
from ..core.cache import get_redis
from ..core.email import send_email
from ..core.config import get_settings

logger = logging.getLogger(__name__)

CONFIRM_TOKEN_TTL = timedelta(hours=24)
RESEND_TOKEN_INTERVAL = timedelta(minutes=5)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _send_confirmation_email(handle: str, email: str, token: str) -> None:
    settings = get_settings()
    base_url = settings.frontend_base_url.rstrip('/') if settings.frontend_base_url else ""
    link = f"{base_url}/confirm-email?token={token}"
    body = (
        f"Hi {handle},\n\n"
        "Please confirm your LangSum email address by clicking the link below:\n"
        f"{link}\n\n"
        "If you did not sign up for LangSum, you can safely ignore this email."
    )
    await send_email("Confirm your LangSum email", body, [email])


router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    handle: str
    email: Optional[EmailStr] = None
    password: str


class LoginIn(BaseModel):
    handle_or_email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    account_id: str
    csrf_token: Optional[str] = None


class MeOut(BaseModel):
    id: str
    handle: str
    display_name: str
    email: Optional[EmailStr] = None
    locale: str
    created_at: Optional[str] = None
    roles: list[str] = []
    is_admin: bool = False
    email_confirmed_at: Optional[str] = None


class ConfirmEmailIn(BaseModel):
    token: str


class ConfirmEmailOut(BaseModel):
    ok: bool = True
    email_confirmed_at: str


class ResendConfirmationOut(BaseModel):
    ok: bool = True
    email: EmailStr
    sent_at: str


async def _record_resend(redis, email: str) -> None:
    if not redis:
        return
    key = f"email:resend:{email.lower()}"
    try:
        await redis.set(key, "1", ex=int(RESEND_TOKEN_INTERVAL.total_seconds()))
    except Exception:
        pass


async def _can_resend(redis, email: str) -> bool:
    if not redis:
        return True
    key = f"email:resend:{email.lower()}"
    try:
        exists = await redis.exists(key)
        return not bool(exists)
    except Exception:
        return True


@router.post("/register", response_model=TokenOut)
async def register(body: RegisterIn, request: Request, response: Response, pool = Depends(get_pool)):
    # Basic validation
    handle = body.handle.strip()
    email = body.email.strip() if body.email else None
    if not handle or not body.password:
        raise HTTPException(status_code=400, detail="handle and password required")

    # Ensure unique handle
    token_plain: Optional[str] = None
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM app.accounts WHERE lower(handle)=lower(%s) LIMIT 1",
                (handle,),
            )
            if await cur.fetchone():
                raise HTTPException(status_code=409, detail="handle already exists")

            pw_hash = hash_password(body.password)
            await cur.execute(
                """
                INSERT INTO app.accounts (handle, display_name, email, password_hash)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (handle, handle, email, pw_hash),
            )
            row = await cur.fetchone()
            account_id = row[0]
            if email:
                token_plain = secrets.token_urlsafe(32)
                token_hash = _hash_token(token_plain)
                now = _now()
                expires_at = now + CONFIRM_TOKEN_TTL
                await cur.execute(
                    """
                    UPDATE app.accounts
                    SET email_confirmation_token=%s,
                        email_confirmation_token_expires=%s,
                        email_confirmation_sent_at=%s,
                        email_confirmed_at=NULL
                    WHERE id=%s
                    """,
                    (token_hash, expires_at, now, account_id),
                )

    token = create_access_token(subject=str(account_id))
    # Set JWT token in httpOnly cookie for security
    # Use secure only when running over HTTPS; allow HTTP during local development
    is_https = (request.url.scheme.lower() == "https")
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        secure=is_https,
        samesite="strict",
        max_age=60 * 60 * 24 * 7
    )
    # Issue CSRF token cookie (not httpOnly so frontend can read and send header)
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=is_https,
        samesite="strict",
        max_age=60 * 60  # 1 hour
    )
    if email and token_plain:
        try:
            await _send_confirmation_email(handle, email, token_plain)
        except Exception as exc:
            logger.exception("Failed to send confirmation email during registration", exc_info=exc)
            raise HTTPException(status_code=500, detail="Unable to send confirmation email")
    return TokenOut(access_token=token, account_id=str(account_id), csrf_token=csrf_token)


@router.post("/confirm-email", response_model=ConfirmEmailOut)
async def confirm_email(body: ConfirmEmailIn, pool = Depends(get_pool)):
    token = (body.token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="token required")
    token_hash = _hash_token(token)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, email_confirmation_token_expires
                FROM app.accounts
                WHERE email_confirmation_token = %s
                LIMIT 1
                """,
                (token_hash,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Invalid or expired token")
            account_id = row[0]
            expires_at = row[1]
            now = _now()
            if expires_at and expires_at < now:
                raise HTTPException(status_code=410, detail="Confirmation token expired")
            await cur.execute(
                """
                UPDATE app.accounts
                SET email_confirmed_at = %s,
                    email_confirmation_token = NULL,
                    email_confirmation_token_expires = NULL
                WHERE id = %s
                RETURNING email_confirmed_at
                """,
                (now, account_id),
            )
            confirmed_row = await cur.fetchone()
    confirmed_at = confirmed_row[0].isoformat() if confirmed_row and confirmed_row[0] else _now().isoformat()
    return ConfirmEmailOut(ok=True, email_confirmed_at=confirmed_at)


@router.post("/resend-confirmation", response_model=ResendConfirmationOut)
async def resend_confirmation(request: Request, account_id: str = Depends(get_current_account_id), pool = Depends(get_pool)):
    redis = get_redis(request)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT handle, email, email_confirmed_at
                FROM app.accounts
                WHERE id = %s
                """,
                (account_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Account not found")
            handle, email, confirmed_at = row
            if not email:
                raise HTTPException(status_code=400, detail="No email on account")
            if confirmed_at:
                raise HTTPException(status_code=409, detail="Email already confirmed")
            if not await _can_resend(redis, email):
                raise HTTPException(status_code=429, detail="Confirmation recently sent")

            token_plain = secrets.token_urlsafe(32)
            token_hash = _hash_token(token_plain)
            now = _now()
            expires_at = now + CONFIRM_TOKEN_TTL
            await cur.execute(
                """
                UPDATE app.accounts
                SET email_confirmation_token = %s,
                    email_confirmation_token_expires = %s,
                    email_confirmation_sent_at = %s
                WHERE id = %s
                RETURNING email
                """,
                (token_hash, expires_at, now, account_id),
            )
    await _record_resend(redis, email)
    try:
        await _send_confirmation_email(handle, email, token_plain)
    except Exception as exc:
        logger.exception("Failed to resend confirmation email", exc_info=exc)
        raise HTTPException(status_code=500, detail="Unable to send confirmation email")
    return ResendConfirmationOut(ok=True, email=email, sent_at=now.isoformat())


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, response: Response, pool = Depends(get_pool)):
    key = body.handle_or_email.strip()
    if not key or not body.password:
        raise HTTPException(status_code=400, detail="credentials required")

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, password_hash, email_confirmed_at
                FROM app.accounts
                WHERE (lower(handle)=lower(%s) OR lower(email)=lower(%s)) AND deleted_at IS NULL
                LIMIT 1
                """,
                (key, key),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
            account_id, password_hash_db, confirmed_at = row
            if not password_hash_db or not verify_password(body.password, password_hash_db):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=str(account_id))
    # Set JWT token in httpOnly cookie for security
    is_https = (request.url.scheme.lower() == "https")
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        secure=is_https,
        samesite="strict",
        max_age=60 * 60 * 24 * 7
    )
    # Issue CSRF token cookie
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=is_https,
        samesite="strict",
        max_age=60 * 60
    )
    return TokenOut(access_token=token, account_id=str(account_id), csrf_token=csrf_token)


@router.get("/me", response_model=MeOut)
async def me(request: Request, account_id: str = Depends(get_current_account_id), pool = Depends(get_pool)):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, handle, display_name, email, locale, created_at, email_confirmed_at
                FROM app.accounts WHERE id=%s
                """,
                (account_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Account not found")
            await cur.execute(
                """
                SELECT r.name
                FROM app.account_roles ar
                JOIN app.roles r ON r.id = ar.role_id
                WHERE ar.account_id = %s
                ORDER BY r.name
                """,
                (account_id,),
            )
            roles = [r[0] for r in await cur.fetchall()]
            return MeOut(
                id=str(row[0]),
                handle=row[1],
                display_name=row[2],
                email=row[3],
                locale=row[4],
                created_at=row[5].isoformat() if row[5] else None,
                roles=roles,
                is_admin=("admin" in roles),
                email_confirmed_at=row[6].isoformat() if row[6] else None,
            )


@router.post("/logout")
async def logout(request: Request, response: Response):
    """
    Log out the current user by clearing the httpOnly access_token cookie.
    Also safe to call if no cookie is present.
    """
    # Ensure cookie is cleared for the correct scope
    response.delete_cookie(
        key="access_token",
        path="/",
        samesite="strict",
    )
    return {"ok": True}


@router.post("/admin/set-password")
async def admin_set_password(
    req: Request,
    handle: str,
    new_password: str,
    _: None = Depends(lambda request: require_role(request, "admin")),
):
    if not handle or not new_password:
        raise HTTPException(status_code=400, detail="handle and new_password required")

    pool = get_pool(req)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM app.accounts WHERE lower(handle)=lower(%s) LIMIT 1",
                (handle,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="handle not found")
            pw_hash = hash_password(new_password)
            await cur.execute(
                "UPDATE app.accounts SET password_hash=%s WHERE id=%s",
                (pw_hash, row[0]),
            )
    return {"ok": True}

class CSRFTokenOut(BaseModel):
    csrf_token: str
    expires_at: str

@router.get("/csrf-token", response_model=CSRFTokenOut)
async def get_csrf_token(request: Request, response: Response):
    """
    Generate a fresh CSRF token and set it as a cookie. The token is also returned
    so clients can mirror it in the X-CSRF-Token header on mutating requests.
    """
    is_https = (request.url.scheme.lower() == "https")
    csrf_token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(seconds=60 * 60)).isoformat() + "Z"
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=is_https,
        samesite="strict",
        max_age=60 * 60
    )
    return {"csrf_token": csrf_token, "expires_at": expires_at}

async def csrf_validate(
    csrf_token_header: Optional[str] = Header(None, alias="X-CSRF-Token"),
    csrf_token_cookie: Optional[str] = Cookie(None, alias="csrf_token"),
):
    """Validate CSRF by comparing header to cookie value."""
    if not csrf_token_header or not csrf_token_cookie:
        raise HTTPException(status_code=403, detail="CSRF token required")
    if not secrets.compare_digest(csrf_token_header, csrf_token_cookie):
        raise HTTPException(status_code=403, detail="CSRF token validation failed")
    return True
