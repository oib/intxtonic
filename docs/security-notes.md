# Security notes — rate limits, auth, abuse surface

Audit of endpoint groups (2026-10-27). Auth = `get_current_account_id` (session token);
mutations additionally require `csrf_validate`. Error responses are normalized by
`register_exception_handlers` (`{"error":{"message":…}}`).

## Daily counters (`app.rate_limits`, keyed by account_id + UTC day)

| Action | Counter | Default limit | Enforced in |
|---|---|---|---|
| Create post | `posts_count` | `DEFAULT_MAX_POSTS_PER_DAY` (env, required) | `posts.create_post` |
| Create reply | `replies_count` | `DEFAULT_MAX_REPLIES_PER_DAY` (env, required) | `posts.create_reply` |
| Upload image | `uploads_count` | `DEFAULT_MAX_UPLOADS_PER_DAY` (env, default 30) | `uploads.upload_image` |

Per-account overrides for posts/replies live in `app.user_limits`.

## Endpoint audit

- **uploads**: 5MB cap, bitmap MIME allowlist (no SVG), random `uuid` filenames under
  `uploads/YYYY/MM/`; now rate-limited daily. Residual: files are public-by-URL.
- **tags**: `POST /tags` is admin-only. Attaching an unknown slug on your own post
  auto-creates it as `domain='user_created'` — intended, not a bug. Banned → 403,
  restricted → 403 unless admin/allowed, non-author → 403, >7 tags/post → 400.
- **posts/replies**: author-only edit/delete paths; visibility levels enforced in
  queries; daily counters above; `body_md` capped at 1200 chars, title at 200.
- **votes/bookmarks**: single-row upserts; no counters — abuse surface is low
  (idempotent writes only).
- **ai translate/summarize**: enqueue-only; worker is a separate service; body length
  pre-checked (1200). Job status is per-id, no per-user listing.

## Known residuals (accepted for now)

- No per-IP/login throttling on auth endpoints (token guessing is unthrottled).
- Uploads are publicly fetchable by URL once known.
- Rate counters are per-account; multi-account abuse is unbounded.
