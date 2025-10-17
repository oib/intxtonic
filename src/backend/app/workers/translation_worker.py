from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from redis.asyncio import Redis

from psycopg_pool import AsyncConnectionPool

from ..core.config import get_settings
from ..services.ai_service import summarize_text, translate_text
from ..services.translation_cache import store_translation
from ..services.translation_queue import JOB_HASH_PREFIX, QUEUE_NAME

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SLEEP_ON_EMPTY_SECONDS = 2


async def update_job_status(
    redis: Redis,
    job_key: str,
    *,
    status: str,
    error: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    mapping: Dict[str, Any] = {"status": status}
    if error:
        mapping["error"] = error
    if extra:
        mapping.update({k: v for k, v in extra.items() if v is not None})
    await redis.hset(job_key, mapping=mapping)


async def process_job(redis: Redis, pool, job_json: str) -> None:
    try:
        job = json.loads(job_json)
    except json.JSONDecodeError:
        logger.error("Invalid job payload: %s", job_json)
        return

    job_id = job.get("job_id")
    job_key = f"{JOB_HASH_PREFIX}{job_id}" if job_id else None
    if not job_id or not job_key:
        logger.error("Job missing job_id: %s", job)
        return

    source_type = job.get("source_type")
    source_id = job.get("source_id")
    target_lang = job.get("target_lang")
    mode = job.get("mode")
    payload = job.get("payload") or {}

    if not all([source_type, source_id, target_lang, mode]):
        logger.error("Job missing required fields: %s", job)
        if job_key:
            await update_job_status(redis, job_key, status="failed", error="invalid job payload")
        return

    await update_job_status(redis, job_key, status="in_progress")

    try:
        if mode == "translate":
            await handle_translate(redis, pool, job_key, source_type, source_id, target_lang, payload)
        elif mode == "summarize":
            await handle_summarize(redis, pool, job_key, source_type, source_id, target_lang, payload)
        else:
            raise ValueError(f"Unsupported job mode: {mode}")
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Translation job failed", exc_info=exc)
        await update_job_status(redis, job_key, status="failed", error=str(exc))
    else:
        await update_job_status(redis, job_key, status="completed")


async def handle_translate(redis: Redis, pool, job_key: str, source_type: str, source_id: str, target_lang: str, payload: Dict[str, Any]) -> None:
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT body_md
                FROM app.posts
                WHERE id = %s AND deleted_at IS NULL
                """,
                (source_id,),
            )
            row = await cur.fetchone()
            if not row:
                raise ValueError("source not found")
            body_md = row[0]

    translated_text = await translate_text(body_md, target_lang)
    async with pool.connection() as conn:
        await store_translation(
            conn,
            source_type=source_type,
            source_id=source_id,
            target_lang=target_lang,
            body_trans_md=translated_text,
        )
        await conn.commit()
    await update_job_status(redis, job_key, status="completed", extra={"body_trans_md": translated_text})


async def handle_summarize(redis: Redis, pool, job_key: str, source_type: str, source_id: str, target_lang: str, payload: Dict[str, Any]) -> None:
    source_text = payload.get("source_text")
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            if source_text:
                body_md = source_text
            else:
                await cur.execute(
                    """
                    SELECT body_md
                    FROM app.posts
                    WHERE id = %s AND deleted_at IS NULL
                    """,
                    (source_id,),
                )
                row = await cur.fetchone()
                if not row:
                    raise ValueError("source not found")
                body_md = row[0]

    summary = await summarize_text(body_md, target_lang)
    async with pool.connection() as conn:
        existing_body_trans: str | None = None
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT body_trans_md
                FROM app.translations
                WHERE source_type = %s AND source_id = %s AND target_lang = %s
                LIMIT 1
                """,
                (source_type, source_id, target_lang),
            )
            row = await cur.fetchone()
            if row and row[0]:
                existing_body_trans = row[0]

        body_for_storage = existing_body_trans if existing_body_trans is not None else (body_md or "")

        await store_translation(
            conn,
            source_type=source_type,
            source_id=source_id,
            target_lang=target_lang,
            body_trans_md=body_for_storage,
            summary_md=summary,
        )
        await conn.commit()
    await update_job_status(redis, job_key, status="completed", extra={"summary_md": summary})


async def worker_loop(redis: Redis, pool: AsyncConnectionPool) -> None:
    while True:
        try:
            result = await redis.brpop(QUEUE_NAME, timeout=10)
            if not result:
                await asyncio.sleep(SLEEP_ON_EMPTY_SECONDS)
                continue
            _, job_json = result
            await process_job(redis, pool, job_json)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Worker error", exc_info=exc)
            await asyncio.sleep(5)


async def main() -> None:
    settings = get_settings()
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is not configured")
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    pool = AsyncConnectionPool(conninfo=settings.database_url, max_size=10, num_workers=3, open=False)
    await pool.open()

    logger.info("Translation worker started")
    try:
        await worker_loop(redis, pool)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
