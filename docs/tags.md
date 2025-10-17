# Tags & Permissions

## Overview
- **Source**: API behavior defined in `src/backend/app/api/tags.py` with helpers in `src/backend/app/core/tag_access.py`.
- **Purpose**: Control which tags appear to different users based on ban/restriction flags, direct assignments, and role-based visibility.

## Tag States
- **Normal**: `is_banned = false`, `is_restricted = false`. Visible to everyone.
- **Restricted**: `is_restricted = true`. Hidden from non-authorized users unless they are explicitly assigned or granted via roles.
- **Banned**: `is_banned = true`. Hidden from all tag listings and blocked from new usage; only admins can view/manage.

## Visibility Rules
- **Guests / Unauthenticated**: Only see tags where `is_restricted = false`.
- **Authenticated users**: Same as guests plus restricted tags assigned directly to them or shared through their roles.
- **Admins** (`require_admin`): Bypass visibility filters and can view all tags regardless of restriction/ban state.
- **Role-based access**: If a role has access to a restricted tag (`app.tag_visibility.role_id`), every account holding that role inherits tag visibility.

## Key Endpoints
- `GET /tags`: Lists tags respecting visibility rules. Uses `build_access_clause()` to filter restricted tags.
- `GET /tags/list-top`: Returns top tags with usage counts and applies the same visibility filtering for non-admins.
- `POST /tags`: Admin-only. Creates a new tag with `is_restricted = true` by default so admins must explicitly grant visibility.
- `POST /tags` auto-detects language slugs (`en`, `de`, `fr`, `es`, `it`, `pt`, `zh`, `ja`, `ko`, `ru`) and makes them unrestricted immediately.
- `POST /tags/{id}/unrestrict`: Admin-only. Sets `is_restricted = false` so the tag becomes visible to all audiences (subject to bans).
- `POST /tags/{id}/ban` & `POST /tags/{id}/unban`: Admin-only toggles for ban state.
- `GET /tags/visibility`: Admin-only snapshot of which roles/users can see each restricted tag.
- `GET /tags/visibility/users/{handle}`: Admin-only lookup of tags assigned to a specific user.
- `POST /tags/{id}/visibility/users`: Admin-only assignment of a restricted tag to a user (`app.tag_visibility.account_id`).
- `DELETE /tags/{id}/visibility/users/{handle}`: Admin-only removal of a user assignment.
- **Admin UI route**: `/admin/tags` renders `src/frontend/pages/admin-tags.html`, exposing Tag Management (create tag, review admin/user groups, manage visibility). The `/admin` landing page now links out to this dedicated view and no longer embeds tag creation controls.

## Dashboard Tag Filter Wiring
- **Frontend entrypoint**: `src/frontend/pages/dashboard.html` registers event handlers when the page loads and immediately invokes `loadTags()` and `loadPosts()`.
- **Tag chips**: `loadTags()` fetches `GET /tags` (or `GET /tags?query=` when searching) with auth headers. It excludes pseudo-tag `bookmarked` and, for non-admins, filters out restricted tags, mirroring backend visibility rules. Each chip toggles membership in the `selectedTags` set and triggers `loadPosts()`.
- **Admin helpers**: When the viewer is an admin, holding <kbd>Alt</kbd> and clicking a chip executes `POST /tags/{id}/ban` or `/tags/{id}/unban`. The inline "Create tag" form sends `POST /tags` and refreshes the list.
- **URL/state sync**: `renderFilters()` updates the badge list, persists state to `localStorage`, and calls `updateUrlFromState()`, which rewrites the query string (`?tag=slug&tag=other`) so deep links like `dashboard.html?tag=foo` restore filters. The special bookmarked toggle stores `tag=bookmarked` and clears normal tags.
- **Post results**: `loadPosts()` builds a `URLSearchParams` payload with repeated `tag` keys (or the `bookmarked` sentinel) plus search/sort options, then calls `GET /posts?...`. The response `items[i].tags` array is rendered as `.chip-tag` buttons that, when clicked, replace the current filter with that slug and reload both tags and posts.
- **Response schema guard**: Tag-filtered queries now reuse the same column order as other `/posts` branches (`src/backend/app/api/posts.py`), ensuring `author`, `tags`, and `highlight` serialize correctly so filters remain functional.
- **Permissions feedback**: If `/posts` returns `403` listing inaccessible tags, the handler prunes those slugs from `selectedTags`, re-renders filters, and surfaces a warning badge so users understand why filters disappeared.
- **Database lookups**: The `/tags` handler in `src/backend/app/api/tags.py` executes a SELECT on `app.tags`, applying optional `ILIKE` queries plus `build_access_clause()` joins to `app.tag_visibility` for restricted tags. The `/posts` handler in `src/backend/app/api/posts.py` branches its SQL: bookmarked feeds join `app.bookmarks`, tag-filtered feeds join `app.post_tags`/`app.tags` with `HAVING COUNT(DISTINCT t.slug)`, and the default feed enforces visibility with a `NOT EXISTS` subquery so restricted tags without access are excluded. Each branch wraps results with `json_agg` to emit per-post tag objects.

## Tag Detail Page (`/tags/{slug}`)
- **Routing**: `src/backend/app/main.py` serves the clean URL `/tags/{slug}` by returning the static `src/frontend/pages/tags.html` template. There is no dedicated REST endpoint; the page bootstraps itself via client-side JavaScript.
- **Frontend flow**: `tags.html` parses the slug from `location.pathname`, enforces auth (redirects guests to `/login`), and calls `GET /posts?tag={slug}` with pagination and sort parameters to load the feed. Additional posts are fetched by incrementing `offset` and repeating the same request.
- **Database queries**: Because the page reuses `GET /posts`, it hits the tag-filtered branch in `list_posts()` (see `src/backend/app/api/posts.py`). That branch joins `app.post_tags` to `app.tags` with `JOIN` filters, constrains `t.slug = ANY(%s::text[])`, and uses `HAVING COUNT(DISTINCT t.slug) = %s` to ensure all requested slugs match. Visibility guards reuse `build_access_clause()` so restricted tags without access raise a `403`, mirroring dashboard behavior.

## Permission Differences
- **Admins**: `list_tags()` skips `build_access_clause()` for admins so `/tags` returns restricted and banned tags, enabling the dashboard to surface every tag (`src/backend/app/api/tags.py`). Admins manage creation/ban actions exclusively through `/admin/tags`; dashboard chips still support Alt+Click ban/unban shortcuts via `/tags/{id}/ban|unban`.
- **Regular users**: Non-admin calls to `/tags` apply `build_access_clause()`, limiting results to unrestricted tags plus those explicitly granted (`app.tag_visibility`). When `/posts` executes, the tag-filtered branch adds the access clause and can respond `403` if a selected tag is inaccessible; the dashboard catches this and removes the offending slugs (`src/backend/app/api/posts.py`, `dashboard.html`).
- **Guests**: Without a token, both `dashboard.html` and `tags.html` redirect to `/login` before fetching data. Backend endpoints such as `/posts` require `get_current_account_id`, so unauthenticated requests are rejected with `401`.

## Database Structures
- **`app.tags`**: Stores tag metadata and flags (`is_banned`, `is_restricted`).
- **`app.tag_visibility`**: Junction table linking tags to either `account_id` (user-specific access) or `role_id` (role-wide access).
- **`app.account_roles`**: Used to determine inherited visibility when a tag is granted to a role.

## Caching Notes
- Admin responses for `GET /tags` and `GET /tags/list-top` may be cached in Redis for 120 seconds. Cache invalidated on tag create/ban/unban.

## Usage Guidelines
- **Creating tags**: After `POST /tags`, grant visibility to roles/users before the tag is usable by non-admins.
- **Opening tags**: Use `POST /tags/{id}/unrestrict` once a tag should be globally visible without per-user assignments.
- **Language tags**: Slugs like `en`, `de`, `fr`, `es`, `it`, `pt`, `zh`, `ja`, `ko`, `ru` are always public; no unrestriction or assignments needed.
- **Assigning roles**: Prefer role assignments when multiple users need the same restricted tag access.
- **Auditing access**: Use `GET /tags/visibility` (global) and `GET /tags/visibility/users/{handle}` (per-user) to verify assignments.
- **Managing bans**: Banned tags remain in the database for history but should not appear publicly until unbanned.
- **Admin vs post tagging**: Only tags created through `/admin/tags` (Tag Management > Create tag) are flagged `created_by_admin`. Tags added inline while authoring posts—whether by admins or other users—are treated as user-created and appear under the "User-created tags" list in `admin-tags.html`.
