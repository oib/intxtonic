# AI Integration: Translation & Summarization

This document explains how inTXTonic integrates with AI services for translation and summarization features. The system uses OpenAI-compatible APIs (e.g., Ollama, OpenWebUI) through a Node.js CLI wrapper with Redis queue-based background processing.

## Components

### Backend Services
- **`src/backend/app/services/ai_service.py`** — Core AI service for translation and summarization
  - `translate_text()` - Translates text to target language with chunking support
  - `summarize_text()` - Generates summaries of text content
  - `split_text_into_chunks()` - Handles long text by splitting into manageable chunks
  - Supports retry logic, prompt engineering, and error handling
  - Reads environment variables:
    - `OLLAMA_BASE_URL` — Base URL of the AI API (e.g., http://127.0.0.1:11434)
    - `OLLAMA_API_KEY` — API key if required by your gateway
    - `OLLAMA_MODEL` — Default model name for AI operations

- **`src/backend/app/services/translation_queue.py`** — Redis queue management
  - `enqueue_translation_job()` - Adds translation/summarization jobs to Redis queue
  - Job schema: `{ job_id, source_type, source_id, target_lang, mode, payload? }`
  - Modes: `translate`, `summarize`
  - Queue name: `translation_jobs`
  - Job status tracking in Redis hashes: `translation_job:{job_id}`

- **`src/backend/app/services/translation_cache.py`** — Database caching
  - `store_translation()` - Persists translation results to PostgreSQL
  - `fetch_translation()` - Retrieves cached translations
  - Stores in `app.translations` table with metadata

- **`src/backend/app/workers/translation_worker.py`** — Background worker
  - Consumes jobs from Redis queue `translation_jobs`
  - Processes translation and summarization requests
  - Updates job status and stores results in database
  - Handles errors and retry logic

### Node.js CLI Wrapper
- **`src/backend/js/ollama_cli.mjs`** — Node.js CLI wrapper
  - Imports OpenAI-compatible client from `src/backend/js/ollama.js`
  - Accepts JSON-serialized message arrays via command line
  - Performs single chat completion requests
  - Returns AI-generated text output

- **`src/backend/js/ollama.js`** — OpenAI-compatible API client
  - Handles HTTP requests to AI endpoints
  - Manages authentication, headers, and error handling
  - Reads configuration from environment variables

### API Endpoints
- **`POST /api/posts/{post_id}/translate`** (in `src/backend/app/api/ai.py`)
  - Input: `{ "target_language": "de" }`
  - Behavior: Enqueues translation job for post content
  - Response: `{ "job_id": "uuid", "status": "queued" }`

- **`POST /api/posts/{post_id}/summarize`** (in `src/backend/app/api/ai.py`)
  - Input: `{ "language": "en", "source_text": "optional" }`
  - Behavior: Enqueues summarization job
  - Response: `{ "job_id": "uuid", "status": "queued" }`

- **`GET /api/jobs/{job_id}`** (in `src/backend/app/api/ai.py`)
  - Behavior: Retrieves job status and results
  - Response: Job metadata with status, progress, and results when complete

## Supported Languages

The system supports translation to major European and Asian languages:
- **European**: bg, hr, cs, da, nl, en, et, fi, fr, de, el, hu, ga, it, lv, lt, mt, pl, pt, ro, sk, sl, es, sv
- **Asian**: ja, ko, zh
- **Other**: ru

## Processing Flow

### Translation Flow
1. HTTP client requests translation via `POST /api/posts/{id}/translate`
2. Backend validates request and enqueues job to Redis with `mode=translate`
3. Background worker consumes job, reads post content from database
4. Worker splits long text into chunks (max 1200 chars each)
5. Each chunk is sent to AI service via Node.js CLI
6. Translated chunks are reassembled and stored in `app.translations`
7. Job status is updated to `completed` with result metadata

### Summarization Flow
1. HTTP client requests summary via `POST /api/posts/{id}/summarize`
2. Backend enqueues job with `mode=summarize`
3. Worker processes content and generates concise summary
4. Result is stored and job marked complete

## Environment Configuration

Required environment variables:
```bash
# AI Service Configuration
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_API_KEY=your_api_key_if_needed
OLLAMA_MODEL=llama3

# Database and Queue
DATABASE_URL=postgresql://user:pass@localhost/langsum
REDIS_URL=redis://localhost:6379
```

## Database Schema

### `app.translations` table
- `id` - Primary key
- `account_id` - User who requested the translation
- `source_type` - Type of source content (e.g., 'post')
- `source_id` - ID of the source content
- `target_language` - Language code for translation
- `source_text` - Original text (optional, for summarization)
- `translated_text` - AI-generated translation/summary
- `mode` - 'translate' or 'summarize'
- `created_at` - Timestamp
- `updated_at` - Last update timestamp

## Error Handling

- **Node.js execution failures**: Returns 500 with "Failed to run ollama client"
- **CLI non-zero exit**: Returns 502 with CLI error output
- **Queue processing errors**: Logged and job status updated with error details
- **Rate limiting**: Implemented to prevent AI service overload

## Security Notes

- All AI endpoints require valid JWT authentication
- API keys and secrets are stored in environment variables, not in code
- Translation results are scoped by user account
- Admin users can view all translation jobs via admin queue management

## Performance Considerations

- Text chunking prevents AI service timeouts for long content
- Redis queue enables asynchronous processing without blocking HTTP requests
- Translation caching avoids redundant AI calls for identical content
- Background worker can be scaled independently of API servers

## Monitoring and Debugging

- Job status available via `/api/jobs/{job_id}` endpoint
- Detailed logs written to `dev/logs/translation-debug.log`
- Redis hashes provide real-time job progress tracking
- Admin queue management interface for monitoring background jobs

## Deployment Requirements

- Node.js available on system PATH for CLI execution
- Redis server for job queue management
- PostgreSQL database for storing translation results
- AI service (Ollama/OpenWebUI) accessible via configured base URL

## Example Usage

### Translate a post
```bash
curl -X POST \
  -H 'Authorization: Bearer <JWT>' \
  -H 'Content-Type: application/json' \
  -d '{"target_language":"de"}' \
  http://localhost:8002/api/posts/123/translate
```

### Check job status
```bash
curl http://localhost:8002/api/jobs/<job_id>
```

### Summarize content
```bash
curl -X POST \
  -H 'Authorization: Bearer <JWT>' \
  -H 'Content-Type: application/json' \
  -d '{"language":"en"}' \
  http://localhost:8002/api/posts/123/summarize
```

## Troubleshooting

- **401 Unauthorized**: Ensure valid JWT token is provided
- **500 Failed to run ollama client**: Check Node.js installation and CLI path
- **502 CLI error**: Verify AI service is running and accessible
- **Job stuck in queued status**: Check translation worker process and Redis connectivity
- **Translation quality issues**: Review prompts in `ai_service.py` and consider model selection
