# OpenWebUI/Ollama Integration in inTXTonic

This document provides a detailed analysis of how inTXTonic connects to OpenWebUI/Ollama via API for AI-powered translation and summarization features, with the purpose of serving as a reference for integration in other Windsurf projects.

## Overview

OpenWebUI serves as an AI integration layer in inTXTonic, primarily used for generating translations and summaries of multilingual content. It acts as a proxy to Ollama, providing an OpenAI-compatible API for chat completions that power the translation and summarization worker processes.

## Integration Components

### 1. Purpose in inTXTonic

- **Content Translation**: Generates high-quality translations of blog posts and content to supported languages.
- **Content Summarization**: Creates concise summaries of longer posts for better user experience.
- **Background Processing**: Handles AI requests asynchronously through Redis queue workers.

### 2. Backend Components

#### 2.1 Node.js Client
- `src/backend/js/ollama.js`: OpenAI-compatible Chat Completions client for Node.js that reads environment variables:
  - `OLLAMA_BASE_URL` or `OLLAMA_BASE`: Base URL of the API (e.g., http://127.0.0.1:11434 or your OpenWebUI proxy).
  - `OLLAMA_API_KEY`: API key if required by your gateway.
  - `OLLAMA_MODEL`: Default model name (e.g., `llama3`, `qwen2`, `gemma2`).

#### 2.2 CLI Wrapper
- `src/backend/js/ollama_cli.mjs`: Thin wrapper around `ollama.js` that expects a JSON array of strings, runs the chat completion, and prints the reply.
- Used by Python backend via `subprocess.run()` for AI requests.

#### 2.3 AI Service Integration
- `src/backend/app/services/ai_service.py`: Python service that calls the Node CLI
  - `translate_text()`: Handles translation requests with proper prompt engineering
  - `summarize_text()`: Generates summaries with context-aware prompts
  - Includes retry logic, error handling, and text chunking for long content

#### 2.4 Background Worker
- `src/backend/app/workers/translation_worker.py`: Async worker that processes translation/summarization jobs
  - Consumes jobs from Redis queue `translation_jobs`
  - Calls AI service via Node CLI wrapper
  - Stores results in PostgreSQL `app.translations` table

### 3. Database Structure

- **`app.translations`**: Stores AI-generated translations and summaries
  - Fields: `id`, `account_id`, `source_type`, `source_id`, `target_language`, `source_text`, `translated_text`, `mode`, `created_at`
  - Supports both translation and summarization modes
  - Indexed for efficient lookup by user and content

### 4. API Integration

- **Translation Endpoint**: `POST /api/posts/{post_id}/translate`
  - Enqueues translation job with target language
  - Returns job ID for status tracking
  
- **Summarization Endpoint**: `POST /api/posts/{post_id}/summarize`
  - Enqueues summarization job with language preference
  - Returns job ID for status tracking

- **Job Status**: `GET /api/jobs/{job_id}`
  - Provides real-time status of AI processing jobs
  - Returns results when completed

## Technical Flow

1. **User Request**: Frontend requests translation/summarization via API endpoints
2. **Job Queuing**: Backend validates request and enqueues job to Redis
3. **Background Processing**: Worker consumes job and prepares content for AI
4. **Text Chunking**: Long content is split into manageable chunks (~1200 chars)
5. **AI Communication**: Node CLI sends requests to OpenWebUI's chat completions endpoint
6. **Response Assembly**: AI responses are combined and post-processed
7. **Database Storage**: Results are stored in `app.translations` table
8. **Status Update**: Job status is updated and results are made available

## Key API Interaction Details

- **Endpoint**: OpenWebUI provides an OpenAI-compatible API typically at `/v1/chat/completions`
- **Request Format**:
  - **Headers**: Includes `Content-Type: application/json` and optionally `Authorization: Bearer <API_KEY>`
  - **Payload**: Contains `model`, `messages` (system and user prompts), `temperature`, and `max_tokens`
- **Response**: Returns JSON with the AI-generated text in `choices[0].message.content`

## Environment Configuration

- **Variables**:
  - `OLLAMA_BASE_URL`: The base URL for the OpenWebUI/Ollama API
  - `OLLAMA_API_KEY`: Authentication key if required
  - `OLLAMA_MODEL`: Specifies the AI model to use (e.g., `llama3`, `qwen2`)
- **Location**: Stored in environment variables or `.env` files, ensuring accessibility to backend services and Node processes

## Security Considerations

- **Authentication**: API endpoints require valid JWT tokens for user authentication
- **Secrets Management**: API keys and other secrets are kept out of version control and logs
- **User Isolation**: Translation results are scoped to user accounts for privacy

## Adapting to Other Windsurf Projects

To integrate OpenWebUI into another project:

1. **Setup OpenWebUI Access**
   - Ensure access to an OpenWebUI instance or set up Ollama with OpenAI-compatible mode
   - Configure environment variables for base URL, API key, and model selection

2. **Create API Client**
   - Develop or adapt a client similar to `ollama.js` for OpenAI-compatible requests
   - Consider a CLI wrapper for backend integration

3. **Define Use Cases**
   - Identify where AI can enhance your application (e.g., content processing, user insights)
   - Design structured prompts for consistent, high-quality results

4. **Implement Queue-Based Processing**
   - Use Redis or similar queue system for background AI processing
   - Design workers to handle AI requests asynchronously

5. **Database Integration**
   - Plan storage for AI-generated content with appropriate metadata
   - Create tables for caching results and tracking job status

6. **Error Handling and Monitoring**
   - Build robust error handling for API failures
   - Implement job status tracking and retry logic
   - Add logging for debugging and monitoring

## Example Code Snippet (AI Service)

```python
# Example from ai_service.py
async def translate_text(text: str, target_language: str):
    """Calls OpenWebUI via Node CLI and returns translation."""
    cli_path = Path(__file__).parent.parent.parent / "js" / "ollama_cli.mjs"
    
    system_prompt = (
        f"You are a professional translator. Translate the following text "
        f"to {target_language}. Preserve the original meaning and tone. "
        f"Only return the translated text without explanations."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text}
    ]
    
    result = subprocess.run(
        ["node", str(cli_path), json.dumps(messages)],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    if result.returncode != 0:
        raise Exception(f"AI service error: {result.stderr}")
    
    return result.stdout.strip()
```

## Performance Optimization

- **Text Chunking**: Prevents timeouts for long content by splitting into manageable pieces
- **Async Processing**: Queue-based system prevents blocking user requests
- **Caching**: Stores results to avoid redundant AI calls for identical content
- **Rate Limiting**: Implements pacing to respect AI service limits

## Troubleshooting

- **Connection Issues**: Verify that OpenWebUI/Ollama base URL is reachable from the application environment
- **Authentication Errors**: Check that API keys are correct and properly set in environment variables
- **Response Quality**: Adjust prompt structure, temperature, and model selection for desired output
- **Performance**: Implement appropriate delays, rate limiting, and caching for frequent API calls
- **Node.js Issues**: Ensure Node.js is installed and CLI wrapper has proper permissions

## Conclusion

inTXTonic's integration with OpenWebUI demonstrates a robust approach to incorporating AI-powered content processing into a web application. By combining queue-based background processing, structured prompt engineering, and proper error handling, the system provides reliable translation and summarization features that enhance the multilingual blogging experience.
