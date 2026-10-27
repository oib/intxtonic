from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from ..core.deps import get_current_account_id
from ..core.db import get_pool
from ..core.config import get_settings
from .auth import csrf_validate

router = APIRouter(prefix="/uploads", tags=["uploads"]) 

# Where to store files on disk (served by StaticFiles in main.py)
def _project_root_from_here() -> Path:
    """Compute project root as the parent of the 'src' directory.
    This file lives at <repo>/src/backend/app/api/uploads.py.
    """
    here = Path(__file__).resolve()
    for anc in here.parents:
        if anc.name == 'src':
            return anc.parent
    # Fallback: go up 4 levels (api -> app -> backend -> src) then parent
    try:
        return here.parents[4].parent
    except Exception:
        return here.parent

PROJECT_ROOT = _project_root_from_here()
BASE_DIR = (PROJECT_ROOT / "src" / "frontend" / "uploads").resolve()
BASE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}
MAX_BYTES = 5 * 1024 * 1024  # 5MB


@router.post("", status_code=201)
async def upload_image(
    file: UploadFile = File(...),
    account_id: str = Depends(get_current_account_id),
    pool = Depends(get_pool),
    __: bool = Depends(csrf_validate),
):
    """Accept an image upload and return a public URL.
    Disallows SVG for safety; only basic bitmap formats allowed.
    """
    if not file or not file.content_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="file is required")
    ctype = file.content_type.lower()
    if ctype not in ALLOWED_MIME:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported image type")

    # Daily upload cap (same app.rate_limits counter pattern as posts/replies)
    max_uploads = get_settings().default_max_uploads_per_day
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO app.rate_limits (account_id, day_utc, uploads_count)
                VALUES (%s, (now() at time zone 'UTC')::date, 1)
                ON CONFLICT (account_id, day_utc)
                DO UPDATE SET uploads_count = app.rate_limits.uploads_count + 1
                RETURNING uploads_count
                """,
                (account_id,),
            )
            if (await cur.fetchone())[0] > max_uploads:
                raise HTTPException(status_code=429, detail="Daily upload limit reached")

    # Limit size by reading up to MAX_BYTES + 1
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file too large (5MB max)")

    # Store under uploads/YYYY/MM/
    from datetime import datetime
    now = datetime.utcnow()
    subdir = BASE_DIR / f"{now.year:04d}" / f"{now.month:02d}"
    subdir.mkdir(parents=True, exist_ok=True)

    ext = ALLOWED_MIME[ctype]
    name = f"{uuid.uuid4().hex}{ext}"
    path = subdir / name

    try:
        with open(path, "wb") as f:
            f.write(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail="failed to store file") from e

    # Build public URL (served by StaticFiles mounted at /uploads)
    # Path relative to BASE_DIR
    rel = path.relative_to(BASE_DIR).as_posix()
    url = f"/uploads/{rel}"
    return {"ok": True, "url": url}
