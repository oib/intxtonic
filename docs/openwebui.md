# OpenWebUI API Integration in SoulTribe.chat

This document provides a detailed analysis of how SoulTribe.chat connects to OpenWebUI via API for AI-powered features, with the purpose of serving as a reference for integration in other Windsurf projects.

## Overview

OpenWebUI serves as an AI integration layer in SoulTribe.chat, primarily used for generating personalized astrological match summaries and profile interpretations. It acts as a proxy to Ollama, providing an OpenAI-compatible API for chat completions.

## Integration Components

### 1. Purpose in SoulTribe.chat

- **Matchmaking Summaries**: Generates friendly, concise summaries for user matches based on astrological synastry metrics.
- **Profile Interpretations**: Provides personalized astrological readings for user profiles with conversational follow-up capabilities.

### 2. Backend Components

#### 2.1 API Endpoints
- `POST /api/match/annotate` (in `routes/match.py`)
  - **Input**: `{ "match_id": number }`
  - **Behavior**: Builds a compact prompt with score context, calls a Node CLI to interact with OpenWebUI, and stores the generated comment in the `Match.comment` field.
- `POST /api/profile/interpret` (in `routes/profile.py`)
  - **Input**: `{ message?: string, history?: Array<{ role: 'user'|'assistant', content: string }> }`
  - **Behavior**: Loads the current user's astrological data (`Radix.json`), builds a prompt including user information and chat history, calls the Node CLI, and returns the AI response.

#### 2.2 Node.js Wrappers
- `dev/ollama.js`: An OpenAI-compatible Chat Completions client for Node.js that reads environment variables:
  - `OLLAMA_BASE` or `OPENWEBUI_BASE_URL`: Base URL of the API (e.g., http://127.0.0.1:11434 or your OpenWebUI proxy).
  - `OLLAMA_API_KEY` or `OPENWEBUI_API_KEY`: API key if required by your gateway.
  - `OLLAMA_MODEL` or `OPENWEBUI_MODEL`: Default model name (e.g., `gemma2:9b`).
- `dev/ollama_cli.mjs`: A small Node CLI that imports `dev/ollama.js` and performs a single chat completion from a provided sequence of strings. The backend uses this via `subprocess.run()`.

#### 2.3 Batch Processing for Pairwise Evaluations
- **Script**: `batch_pair_eval.py` (located in `/root/scripts/soultribe/`)
- **Behavior**:
  - Pulls all users from the database.
  - Iterates through all unique user pairs.
  - Computes astrological compatibility scores.
  - Calls OpenWebUI to generate a comment for each pair.
  - Stores results in `pairwise_ai_evals` (for all pairs) and `matches` (for visible matches with score ≥ 50).
- **Scheduling**: Runs nightly via systemd timer or cron job for regular updates.

### 3. Database Structure

- **pairwise_ai_evals**: Stores AI replies for every user pair (visible or hidden).
  - Fields: `user_a_id`, `user_b_id`, `pair_key` (unique), `score`, `score_vector`, `ai_reply`, `ai_model`, `eval_lang`, etc.
- **matches**: Stores match information and AI comments only for visible matches (score ≥ 50).
  - Fields: `user_a_id`, `user_b_id`, `score`, `score_vector`, `ai_comment`, `ai_model`, `status` ('visible' or 'hidden'), etc.

### 4. Frontend Integration

- **Dashboard (`web/dashboard.js`)**:
  - Features a "Generate AI comment" button that ensures a match via `/api/match/create`, then calls `/api/match/annotate`.
- **Profile Section (`web/profile.html`, `web/profile.js`)**:
  - "AI Interpretation" section allows users to get initial readings and ask follow-up questions via `POST /api/profile/interpret`.

## Technical Flow

1. **User Pair Evaluation**: A batch script evaluates all user pairs, calculating astrological compatibility.
2. **Prompt Construction**: Structured prompts are created including match metrics or user profile data.
3. **API Interaction**: The Node CLI (`ollama_cli.mjs`) sends requests to OpenWebUI's chat completions endpoint.
4. **Response Storage**: AI responses are stored in the database, with selective display based on match scores.
5. **User Display**: Users see AI-generated content for high-scoring matches or personal interpretations without numerical scores or ratings.

## Key API Interaction Details

- **Endpoint**: OpenWebUI provides an OpenAI-compatible API typically at `/v1/chat/completions`.
- **Request Format**:
  - **Headers**: Includes `Content-Type: application/json` and optionally `Authorization: Bearer <API_KEY>`.
  - **Payload**: Contains `model`, `messages` (array of system and user prompts), `temperature`, and `max_tokens`.
- **Response**: Returns JSON with the AI-generated text in `choices[0].message.content`.

## Environment Configuration

- **Variables**:
  - `OPENWEBUI_BASE_URL`: The base URL for the OpenWebUI API.
  - `OPENWEBUI_API_KEY`: Authentication key if required.
  - `OPENWEBUI_MODEL`: Specifies the AI model to use.
  - `OPENWEBUI_RATE_DELAY_SEC`: Controls pacing of requests to avoid overwhelming the service.
- **Location**: Stored in environment variables or `.env` files, ensuring they are accessible to backend services and Node processes.

## Security Considerations

- **Authentication**: API endpoints require valid JWT tokens for user authentication.
- **Secrets Management**: API keys and other secrets are kept out of version control and logs.

## Adapting to Other Windsurf Projects

To integrate OpenWebUI into another project:

1. **Setup OpenWebUI Access**:
   - Ensure you have access to an OpenWebUI instance or set up a new one proxying to Ollama.
   - Configure environment variables for base URL, API key (if needed), and model selection.

2. **Create API Client**:
   - Develop or adapt a client similar to `ollama.js` for making OpenAI-compatible requests.
   - Consider a CLI or direct API calls depending on your backend architecture.

3. **Define Use Cases**:
   - Identify where AI can enhance your application (e.g., content generation, user insights).
   - Design structured prompts that provide context and elicit desired responses.

4. **Database Integration**:
   - Plan storage for AI-generated content, considering whether all responses or only specific ones should be user-visible.
   - Create appropriate tables or fields to store responses alongside relevant metadata (model used, language, timestamps).

5. **Frontend Features**:
   - Implement UI elements to trigger AI content generation and display results.
   - Handle conversational flows if applicable, maintaining history for context.

6. **Batch Processing (if needed)**:
   - For bulk operations, design scripts to process data and interact with OpenWebUI.
   - Implement scheduling for regular updates.

7. **Error Handling and Rate Limiting**:
   - Build robust error handling for API failures.
   - Implement rate limiting to respect service constraints.

## Example Code Snippet (Batch Script)

```python
# Example from batch_pair_eval.py
def openwebui_comment(res, ua, ub, lang="en"):
    """Calls OpenWebUI and returns text reply (single string)."""
    url = f"{OPENWEBUI_BASE_URL}/v1/chat/completions"
    headers = {"Content-Type":"application/json"}
    if OPENWEBUI_API_KEY:
        headers["Authorization"] = f"Bearer {OPENWEBUI_API_KEY}"

    system = (
        "You write concise, friendly, non-cringe match summaries based on astrological factors. "
        "Do not mention numeric scores or star ratings. No therapy, no medical or legal advice."
    )
    user_prompt = (
        f"Two users were matched with synastry metrics.\n"
        f"Return one short paragraph (max 90 words) and a 3-bullet strengths list.\n"
        f"Language: {lang}\n\n"
        # ... rest of prompt with metrics and names
    )

    payload = {
        "model": OPENWEBUI_MODEL,
        "messages": [
            {"role":"system","content": system},
            {"role":"user","content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=120)
    r.raise_for_status()
    data = r.json()
    txt = data["choices"][0]["message"]["content"].strip()
    return txt
```

## Troubleshooting

- **Connection Issues**: Verify that the OpenWebUI base URL is reachable from your application environment.
- **Authentication Errors**: Check that the API key is correct and properly set in environment variables.
- **Response Quality**: Adjust prompt structure and parameters like `temperature` for desired output style.
- **Performance**: Implement appropriate delays or rate limiting if API calls are frequent.

## Conclusion

SoulTribe.chat's integration with OpenWebUI demonstrates a robust approach to incorporating AI-generated content into a web application. By adapting the components and patterns described, other Windsurf projects can leverage AI capabilities through OpenWebUI for various use cases, enhancing user experience with personalized, dynamic content.
