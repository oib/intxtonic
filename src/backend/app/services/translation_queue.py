from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Iterable

from redis.asyncio import Redis

QUEUE_NAME = "translation_jobs"
JOB_HASH_PREFIX = "translation_job:"
DEFAULT_TTL_SECONDS = 60 * 60  # 1 hour


async def enqueue_translation_job(
    redis: Redis,
    *,
    source_type: str,
    source_id: str,
    target_lang: str,
    mode: str,
    payload: Optional[Mapping[str, Any]] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str:
    """
    Enqueue a translation-related job and initialize its Redis hash entry.

    Returns the generated job_id.
    """
    job_id = str(uuid.uuid4())
    job_data = {
        "job_id": job_id,
        "source_type": source_type,
        "source_id": source_id,
        "target_lang": target_lang,
        "mode": mode,
        "payload": payload or {},
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    if metadata:
        for key, value in metadata.items():
            if value is None:
                continue
            job_data[key] = value

    job_json = json.dumps(job_data)

    job_key = f"{JOB_HASH_PREFIX}{job_id}"
    hash_mapping: dict[str, Any] = {
        "status": "pending",
        "mode": mode,
        "source_type": source_type,
        "source_id": source_id,
        "target_lang": target_lang,
        "queued_at": job_data.get("queued_at", ""),
    }
    if metadata:
        for key, value in metadata.items():
            if value is None:
                continue
            hash_mapping[key] = value
    await redis.hset(job_key, mapping=hash_mapping)
    if ttl_seconds:
        await redis.expire(job_key, ttl_seconds)

    await redis.lpush(QUEUE_NAME, job_json)
    return job_id


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _merge_job(base: dict[str, Any], extra: Mapping[str, Any] | None) -> dict[str, Any]:
    if not extra:
        return base
    for key, value in extra.items():
        if key == "chunk_count":
            parsed = _safe_int(value)
            if parsed is not None:
                base[key] = parsed
            continue
        base[key] = value
    return base


async def list_queue_jobs(
    redis: Redis,
    *,
    limit: int = 100,
    include_in_progress: bool = True,
) -> list[dict[str, Any]]:
    """Return queued (and optionally in-progress) translation jobs."""

    jobs: dict[str, dict[str, Any]] = {}

    max_range = -1 if limit <= 0 else limit - 1
    raw_items = await redis.lrange(QUEUE_NAME, 0, max_range)
    # Queue is LPUSH newest; reverse to show oldest first
    for raw in reversed(raw_items):
        try:
            job_data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        job_id = job_data.get("job_id")
        if not job_id:
            continue
        entry: dict[str, Any] = {
            "job_id": job_id,
            "source_type": job_data.get("source_type"),
            "source_id": job_data.get("source_id"),
            "target_lang": job_data.get("target_lang"),
            "mode": job_data.get("mode"),
            "payload": job_data.get("payload") or {},
            "chunk_count": job_data.get("chunk_count"),
            "queued_at": job_data.get("queued_at"),
        }
        hash_key = f"{JOB_HASH_PREFIX}{job_id}"
        hash_data = await redis.hgetall(hash_key)
        entry = _merge_job(entry, hash_data)
        if entry.get("chunk_count") is None:
            chunk_from_payload = entry.get("payload", {}).get("chunk_count") if isinstance(entry.get("payload"), dict) else None
            parsed = _safe_int(chunk_from_payload)
            if parsed is not None:
                entry["chunk_count"] = parsed
        jobs[job_id] = entry

    if include_in_progress:
        keys: Iterable[str] = await redis.keys(f"{JOB_HASH_PREFIX}*")
        for key in keys:
            job_id = key.replace(JOB_HASH_PREFIX, "", 1)
            if job_id in jobs:
                continue
            hash_data = await redis.hgetall(key)
            if not hash_data:
                continue
            status = (hash_data.get("status") or "").lower()
            if status not in {"pending", "in_progress"}:
                continue
            entry: dict[str, Any] = {
                "job_id": job_id,
            }
            entry = _merge_job(entry, hash_data)
            chunk_from_hash = entry.get("chunk_count")
            if chunk_from_hash is not None:
                entry["chunk_count"] = _safe_int(chunk_from_hash)
            jobs[job_id] = entry

    def sort_key(item: dict[str, Any]) -> tuple[str, str]:
        queued = item.get("queued_at") or ""
        return (queued, item.get("job_id") or "")

    return sorted(jobs.values(), key=sort_key)
