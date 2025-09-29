# AI Integration: OpenWebUI / Ollama

This document explains how the backend talks to an OpenAI-compatible API (e.g., OpenWebUI -> Ollama) and how the frontend uses it. It also covers environment variables, request/response formats, and example calls.

## Components

- Backend wrappers
  - `dev/ollama.js` — OpenAI-compatible Chat Completions client (Node). Reads `.env`:
    - `OLLAMA_BASE` — Base URL of the API (e.g., http://127.0.0.1:11434 or your OpenWebUI proxy)
    - `OLLAMA_API_KEY` — API key if required by your gateway
    - `OLLAMA_MODEL` — Default model name
  - `dev/ollama_cli.mjs` — Small Node CLI that imports `dev/ollama.js` and performs a single chat completion from a provided sequence of strings. The backend uses this via `subprocess.run()`.

- Backend endpoints
  - `POST /api/match/annotate` (in `routes/match.py`)
    - Input: `{ "match_id": number }`
    - Behavior: Builds a compact prompt with score context and calls Node CLI; stores the one-line comment in `Match.comment`.
  - `POST /api/profile/interpret` (in `routes/profile.py`)
    - Input: `{ message?: string, history?: Array<{ role: 'user'|'assistant', content: string }> }`
    - Behavior: Loads the current user’s `Radix.json`, builds a short system intro + user display name + radix JSON, then appends optional chat history and/or `message`. Calls Node CLI and returns `{ reply: string }`.

- Frontend hooks
  - Dashboard (`web/dashboard.js`)
    - “Generate AI comment” button: ensures a match via `/api/match/create`, then calls `/api/match/annotate`.
  - Profile (`web/profile.html`, `web/profile.js`)
    - “AI Interpretation” section: 
      - `Get Interpretation` calls `POST /api/profile/interpret` without a `message` to fetch a concise initial reading.
      - Follow-up messages append to a local `history` array sent along with each `message` to the same endpoint.

## Sequence Design

The Node CLI receives a JSON-serialized array of strings (a simple linear “sequence”):

- For match annotation:
  - Lines include `Match <id>`, perspective, other display name, numerical score, score breakdown JSON, and an instruction to produce a one-sentence friendly comment that addresses “you” and the other’s name.
- For profile interpretation:
  - Lines include a short “system” guidance (friendly, concise astrologer), `User: <display_name>`, `Radix: <json>`, optional chat history lines prefixed as `User:` or `You:`, and the last turn (question or request).

CLI output is treated as the final reply. The backend may apply post-processing (e.g. sanitize A/B to “you” and the other’s name in match annotations).

## Environment

- `.env` variables used by `dev/ollama.js`:
  - `OLLAMA_BASE` — Base URL for the OpenAI-compatible endpoint.
  - `OLLAMA_API_KEY` — API key if your gateway requires one.
  - `OLLAMA_MODEL` — Default model, e.g. `llama3`, `qwen2`, etc.

Make sure your backend service environment inherits these variables so the Node process (spawned by FastAPI via `subprocess`) can see them.

## Requirements

- Node.js available on the system PATH (the backend calls `node dev/ollama_cli.mjs ...`).
- The OpenAI-compatible API should accept Chat Completions requests. OpenWebUI can proxy to Ollama in OpenAI-compatible mode.

## Example Requests

- Match annotation (frontend flow):
  1. `POST /api/match/create` with `{ a_user_id, b_user_id }` → returns `{ match_id }` (idempotent).
  2. `POST /api/match/annotate` with `{ match_id }` → returns `{ match_id, comment }` and persists it.

- Profile interpretation (curl):

```bash
curl -X POST http://127.0.0.1:8001/api/profile/interpret \
  -H 'Authorization: Bearer <JWT>' \
  -H 'Content-Type: application/json' \
  -d '{"message": null, "history": []}'
```

- Follow-up (ping-pong):

```bash
curl -X POST http://127.0.0.1:8001/api/profile/interpret \
  -H 'Authorization: Bearer <JWT>' \
  -H 'Content-Type: application/json' \
  -d '{
        "message": "Can you elaborate on the Moon aspect?",
        "history": [
          {"role":"assistant","content":"<first reply>"}
        ]
      }'
```

## Error Handling

- If Node cannot be executed or times out, the backend returns `500` with `Failed to run ollama client`.
- If the CLI returns non-zero, the backend returns `502` with the CLI error output.

## Security Notes

- The AI endpoints require a valid JWT via the usual auth dependency.
- Do not log secrets. Keep `.env` out of version control.

## Troubleshooting

- 405 Method Not Allowed on `/api/profile/interpret`: ensure the server has reloaded after adding the endpoint (restart `make dev` or systemd unit).
- Ensure Node is installed and available in the service environment.
- Verify `OLLAMA_BASE` points to a reachable OpenAI-compatible endpoint.
