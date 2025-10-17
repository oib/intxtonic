from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..core.cache import get_redis
from ..core.deps import require_admin_or_moderator
from ..services.translation_queue import list_queue_jobs

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/queue")
async def get_translation_queue(
    request: Request,
    _: None = Depends(require_admin_or_moderator),
    limit: int = 100,
):
    redis = get_redis(request)
    if redis is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Redis unavailable")
    jobs = await list_queue_jobs(redis, limit=limit)
    return {"jobs": jobs}
