from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ..core.db import get_pool
from ..core.deps import get_current_account_id
from ..schemas.ai import (
    TranslationRequest,
    SummarizationRequest,
    TranslationResponse,
    SummarizationResponse,
)
from ..services.translation_cache import fetch_translation
from ..services.ai_service import split_text_into_chunks
from ..core.cache import get_redis
from ..services.translation_queue import JOB_HASH_PREFIX, enqueue_translation_job

ai_route = APIRouter(prefix='/api', tags=['ai'])

_ALLOWED_LANG_CODES = {
    'bg', 'hr', 'cs', 'da', 'nl', 'en', 'et', 'fi', 'fr', 'de', 'el', 'hu',
    'ga', 'it', 'lv', 'lt', 'mt', 'pl', 'pt', 'ro', 'sk', 'sl', 'es', 'sv',
}


def _normalize_lang(code: str | None) -> str:
    if not code:
        return ''
    return code.strip().lower().split('-')[0]


def _select_allowed_lang(preferred: str | None, fallback: str = 'en') -> str:
    normalized = _normalize_lang(preferred)
    if normalized in _ALLOWED_LANG_CODES:
        return normalized
    normalized_fallback = _normalize_lang(fallback)
    if normalized_fallback in _ALLOWED_LANG_CODES:
        return normalized_fallback
    # As final safety, return English which is guaranteed in the allowed set
    return 'en'


@ai_route.get('/jobs/{job_id}')
async def get_job_status(job_id: str, request: Request):
    redis = get_redis(request)
    if redis is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Job tracking unavailable')

    key = f"{JOB_HASH_PREFIX}{job_id}"
    data = await redis.hgetall(key)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Job not found')
    return data


@ai_route.post('/posts/{post_id}/translate', response_model=TranslationResponse)
async def translate_post(
    post_id: str,
    request: TranslationRequest,
    fastapi_request: Request,
    pool = Depends(get_pool),
    account_id: str = Depends(get_current_account_id),
):
    body_md: str | None = None
    cached_translation: dict | None = None
    target_language: str | None = None

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT body_md FROM app.posts WHERE id = %s AND deleted_at IS NULL",
                (post_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
            body_md = row[0]

            target_language = (request.target_language or "").strip()
            if not target_language:
                await cur.execute(
                    "SELECT locale FROM app.accounts WHERE id = %s",
                    (account_id,),
                )
                locale_row = await cur.fetchone()
                if locale_row and locale_row[0]:
                    target_language = locale_row[0].strip()
            target_language = _select_allowed_lang(target_language)

        cached_translation = await fetch_translation(
            conn,
            source_type="post",
            source_id=post_id,
            target_lang=target_language,
        )

    if cached_translation and cached_translation.get("body_trans_md"):
        return TranslationResponse(translated_text=cached_translation["body_trans_md"])

    if len(body_md or "") > 1200:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Translation text too long (max 1200 characters)",
        )

    redis = get_redis(fastapi_request)
    if redis is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Translation queue unavailable')

    chunk_count = len(split_text_into_chunks(body_md or ""))

    job_id = await enqueue_translation_job(
        redis,
        source_type="post",
        source_id=post_id,
        target_lang=target_language,
        mode="translate",
        metadata={
            "requested_by": account_id,
            "chunk_count": chunk_count,
        },
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "pending", "job_id": job_id},
    )


@ai_route.post('/posts/{post_id}/summarize', response_model=SummarizationResponse)
async def summarize_post(
    post_id: str,
    request: SummarizationRequest,
    fastapi_request: Request,
    pool = Depends(get_pool),
    account_id: str = Depends(get_current_account_id),
):
    body_md: str | None = None
    summary_language: str | None = None
    cached_summary: dict | None = None

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            body_md: str | None = None
            if request.source_text:
                body_md = request.source_text
            else:
                await cur.execute(
                    "SELECT body_md FROM app.posts WHERE id = %s AND deleted_at IS NULL",
                    (post_id,),
                )
                row = await cur.fetchone()
                if not row:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Post not found')
                body_md = row[0]

            summary_language = (request.language or "").strip()
            if not summary_language:
                await cur.execute(
                    "SELECT locale FROM app.accounts WHERE id = %s",
                    (account_id,),
                )
                locale_row = await cur.fetchone()
                if locale_row and locale_row[0]:
                    summary_language = locale_row[0].strip()
            summary_language = _select_allowed_lang(summary_language)

        cached_summary = await fetch_translation(
            conn,
            source_type="post",
            source_id=post_id,
            target_lang=summary_language,
        )

    if cached_summary and cached_summary.get("summary_md"):
        return SummarizationResponse(summary=cached_summary["summary_md"])

    if len(body_md or "") > 1200:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Summarization text too long (max 1200 characters)",
        )

    redis = get_redis(fastapi_request)
    if redis is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='Summarization queue unavailable')

    payload = {}
    if request.source_text:
        payload["source_text"] = request.source_text

    job_id = await enqueue_translation_job(
        redis,
        source_type="post",
        source_id=post_id,
        target_lang=summary_language,
        mode="summarize",
        payload=payload,
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "pending", "job_id": job_id},
    )
