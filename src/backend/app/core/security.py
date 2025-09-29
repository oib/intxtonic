from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import bcrypt
import jwt

from .config import get_settings


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def get_password_hash(plain: str) -> str:
    """Compatibility alias for legacy imports."""
    return hash_password(plain)


def create_access_token(subject: str, claims: Dict[str, Any] | None = None, expires_minutes: int = 60) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    # Coerce subject to string to avoid UUID serialization errors
    subject_str = str(subject)
    payload: Dict[str, Any] = {
        "sub": subject_str,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    if claims:
        payload.update(claims)
    # Use Settings.secret_key (defined in core/config.py)
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    settings = get_settings()
    # Use Settings.secret_key (defined in core/config.py)
    data = jwt.decode(token, settings.secret_key, algorithms=["HS256"])  # raises on error
    return data

# Note: JWT tokens are now set in httpOnly cookies for enhanced security, as implemented in auth.py.
# This prevents client-side JavaScript from accessing the token, reducing the risk of XSS attacks.
# Future enhancements should include CSRF token validation for form-like actions (e.g., POST requests)
# to protect against cross-site request forgery. CSRF tokens can be stored in a separate session cookie
# and validated via middleware on protected endpoints.
