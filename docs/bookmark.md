# Bookmarks & Tagged Favorites

This document explains the server-side bookmark system introduced for LangSum. It covers database schema changes, API routes, and frontend integration for star-based bookmark toggles.

## Database Schema Overview

- **`app.bookmarks`**
  - Stores per-account bookmarks for posts, replies, or other resources.
  - Columns: `id`, `account_id`, `target_type` (`post|reply|other`), `target_id`, `created_at`.
  - Unique constraint on `(account_id, target_type, target_id)` prevents duplicate bookmarks.
  - Indexed by `(account_id, target_type)` for fast lookup.

- **`app.bookmark_tags`**
  - Optional per-bookmark tagging (e.g., `favorite`, `later`).
  - Columns: `bookmark_id`, `tag_slug`, `created_at`.
  - Primary key on `(bookmark_id, tag_slug)`; cascade delete when a bookmark is removed.

- **Global Tag Seed**
  - The migration seeds a `bookmarked` slug in `app.tags` with label `Bookmarked`.
  - When bookmarking a post, the backend ensures the post carries this tag in `app.post_tags`.

> Schema changes live in `src/backend/app/db/schema.sql`.

## Backend API (`src/backend/app/api/bookmarks.py`)

Routes are registered under `/bookmarks` in `src/backend/app/main.py`.

- `POST /bookmarks`
  - Body: `{ "target_type": "post", "target_id": "<uuid>", "tags": ["favorite"] }`
  - Upserts the bookmark, adds optional tag slugs (always including `bookmarked`).
  - For posts, also attaches the global `bookmarked` tag via `app.post_tags`.
  - Response: bookmark metadata including tags and `created_at`.

- `GET /bookmarks`
  - Query params: `limit`, `offset`, optional `tag`, optional `target_type`.
  - Returns a page of bookmarks (`items`, `total`).

- `DELETE /bookmarks`
  - Query params: `target_type`, `target_id`.
  - Removes the bookmark for the authenticated user.

- `PATCH /bookmarks/{bookmark_id}/tags`
  - Body: `{ "tags": ["favorite", "bookmarked"] }`.
  - Replaces the bookmark’s tag list (auto-includes `bookmarked`).

- `GET /bookmarks/lookup`
  - Query params: `target_type`, `target_ids` (comma-separated list).
  - Returns bookmark status for multiple targets, used to hydrate frontend stars.

All endpoints require authentication (`Depends(get_current_account_id)`), using the asyncpg pool via `get_pool`.

## Frontend Integration

- **Assets**: `star-outline.svg` and `star-filled.svg` in `src/frontend/assets/icons/`.
- **Styles**: `.bookmark-toggle` button defined in `src/frontend/css/components.css`. Outline star by default; filled star when `.is-active` class is present.
- **Script**: `src/frontend/js/bookmarks.js`
  - Handles global click delegation for `.bookmark-toggle` buttons.
  - Maintains local bookmark state, performing POST/DELETE as needed.
  - Provides `initBookmarkToggles(root)` to register buttons and prefetch state via `/bookmarks/lookup`.

### Page Usage

- `src/frontend/pages/dashboard.html`
  - Adds bookmark star to each post card (near score badge).
  - Imports `initBookmarkToggles` and calls it after rendering posts.

- `src/frontend/pages/post.html`
  - Adds a star next to the post metadata header to toggle the bookmark.
  - Calls `initBookmarkToggles` after post data loads and for the whole document.

- `src/frontend/pages/user.html`
  - Shows a personal **Bookmarks** tab when viewing your own profile.
  - Fetches `GET /users/{handle}/bookmarks` and renders bookmarked posts with active stars.
  - Uses `initBookmarkToggles` so removing a bookmark updates the list instantly.

## Profile Bookmarks Endpoint

- `GET /users/{handle}/bookmarks`
  - Returns the authenticated user's bookmarked posts (private—403 for other viewers).
  - Supports pagination with `limit` and `offset` (default `10`).
  - Each item includes `bookmark_id`, `post_id`, `title`, `excerpt`, `author`, `score`, tags, and the bookmark timestamp.

## Testing & Validation

1. **Database**: Verify new tables exist and `bookmarked` tag inserted.
2. **API**:
   - POST a bookmark for a post; check `app.bookmarks`, `app.bookmark_tags`, and `app.post_tags`.
   - DELETE the bookmark; confirm removal from `app.bookmarks` (global tag remains).
   - Lookup multiple posts via `/bookmarks/lookup` to ensure batching works.
3. **Frontend**:
   - Log in, open dashboard/post pages, toggle the star. The star should fill instantly and remain active after refresh.
   - Log out: stars appear unfilled and redirect to login on click.

## Future Enhancements

- Extend stars to reply lists and other content types.
- Add a dedicated “My Bookmarks” view using `GET /bookmarks` filters.
- Allow users to manage custom bookmark tags through the UI.
