# Agents

This repository uses queue-driven background workers to perform autonomous AI tasks.
Requests enter via HTTP endpoints, are enqueued in Redis, and processed by an async
worker that calls local/remote LLMs through a Node.js CLI. Results are persisted in
PostgreSQL and can be retrieved over HTTP.

## Agent Directory

| Agent | Role | Trigger/Entry | Input | Output | Permissions | Source |
| --- | --- | --- | --- | --- | --- | --- |
| translation_worker | Translate and summarize posts using LLM. | Redis queue `translation_jobs` (enqueued by HTTP: POST `/api/posts/{id}/translate`, `/api/posts/{id}/summarize`) | Job JSON: `{ job_id, source_type, source_id, target_lang, mode, payload? }`. Modes: `translate`, `summarize`. | Updates DB row via `store_translation`. Job status in Redis hash `translation_job:{job_id}`. | Redis (R/W), PostgreSQL (R/W to `app.posts`, `app.translations`), Network to Ollama via Node CLI, Local process exec of `backend/js/ollama_cli.mjs`. | `src/backend/app/workers/translation_worker.py` |

## Configuration

- Env vars (via `get_settings()`):
  - `OLLAMA_BASE` (optional): base URL for Ollama.
  - `OLLAMA_API_KEY` (optional): API key for Ollama.
  - `OLLAMA_MODEL` (optional): model name.
  - `REDIS_URL`: Redis connection string (required by worker and HTTP status routes).
  - `DATABASE_URL`: Postgres connection string (required by worker and API routes).
- Entry points:
  - Worker: `python -m src.backend.app.workers.translation_worker` (or run file).
  - HTTP:
    - POST `/api/posts/{post_id}/translate`
    - POST `/api/posts/{post_id}/summarize`
    - GET `/api/jobs/{job_id}`
- Auth placeholders:
  - API routes depend on `get_current_account_id` and role checks in other routers.
- LLM CLI:
  - `backend/js/ollama_cli.mjs` invoked by `ai_service.py` via Node.

## Interfaces/Protocols

- translation_worker
  - Queue: Redis list `translation_jobs`.
  - Job schema (JSON):
    ```json
    {
      "job_id": "uuid",
      "source_type": "post",
      "source_id": "<id>",
      "target_lang": "en|de|...",
      "mode": "translate|summarize",
      "payload": {"source_text": "optional"},
      "queued_at": "ISO-8601"
    }
    ```
  - Status hash: `translation_job:{job_id}` with fields
    `status`, `mode`, `source_type`, `source_id`, `target_lang`, `queued_at`,
    optional `chunk_count`, and result snippets like `body_trans_md`, `summary_md`.
  - HTTP enqueuers and status:
    - POST `/api/posts/{id}/translate` -> enqueues `mode=translate`.
    - POST `/api/posts/{id}/summarize` -> enqueues `mode=summarize`.
    - GET `/api/jobs/{job_id}` -> reads Redis hash.
  - LLM calls: `ai_service.translate_text` and `ai_service.summarize_text` invoke Node
    CLI `ollama_cli.mjs`, passing a chat sequence JSON on stdin/argv.

- Schemas (Pydantic)
  - Request: `TranslationRequest { target_language?: string }`
  - Response: `TranslationResponse { translated_text: string }`
  - Request: `SummarizationRequest { language?: string, source_text?: string }`
  - Response: `SummarizationResponse { summary: string }`
  - Source: `src/backend/app/schemas/ai.py`

## Security & Permissions

- Least privilege:
  - Worker reads from `app.posts` and writes to `app.translations` only via
    `store_translation`. Do not grant broader DB roles.
  - Redis: restrict to list and hash keys with prefixes `translation_jobs` and
    `translation_job:*`.
  - Network: allow egress only to Ollama base URL if remote. Prefer localhost.
  - Filesystem: worker executes Node CLI; no broad FS access required.
- Secrets:
  - Manage `OLLAMA_API_KEY`, `DATABASE_URL`, `REDIS_URL` via environment/secret store.

## Interaction Flows

- Translate flow
  - HTTP client -> POST `/api/posts/{id}/translate`.
  - API enqueues job to `translation_jobs` with `mode=translate`.
  - Worker BRPOP -> fetches job, reads source body, calls LLM translator.
  - Worker writes translation to DB and job hash, sets `status=completed`.

- Summarize flow
  - HTTP client -> POST `/api/posts/{id}/summarize`.
  - API enqueues job with `mode=summarize` (+ optional `source_text`).
  - Worker reads source or provided text, calls summarizer, stores `summary_md`.

## Examples

- Enqueue translation
  ```sh
  curl -X POST \
    -H 'Content-Type: application/json' \
    -d '{"target_language":"de"}' \
    http://localhost:8000/api/posts/123/translate
  ```

- Enqueue summarization
  ```sh
  curl -X POST \
    -H 'Content-Type: application/json' \
    -d '{"language":"en"}' \
    http://localhost:8000/api/posts/123/summarize
  ```

- Check job status
  ```sh
  curl http://localhost:8000/api/jobs/<job_id>
  ```

## Changelog

### 2025-10-24 — Agent registry refresh; schema updates detected
- Added `translation_worker` (Redis queue consumer) with translate/summarize modes.
- Documented HTTP enqueuers and job/status schemas.
- Recorded permissions and security notes.

### 2025-10-22 — Support and fixes for AGENTS.md
