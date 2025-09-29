# Done

## Frontend
- Base styles and components: `src/frontend/css/base.css`, `components.css`, `layout.css`
- Toasts and browser notifications: `src/frontend/js/toast.js`, `src/frontend/js/notify.js`
- Pages: `index.html`, `login.html`, `dashboard.html`, `post.html`, `user.html`
- Tag filtering UX on dashboard with deep links (`?tags=`), removable chips, ESC clear, persistence
- Posts search (`q`) with combined tag filters, per-page limit, total count, Load more UX
- Admin tag controls on post page: attach/detach by slug; public tag chips deep-link to dashboard
- i18n Admin Page Enhancements: Completed batch and per-key translation, added debug panel, and ensured dynamic UI updates.
- Navbar Layout Standardization: Implemented centered brand and edge-aligned controls across all pages using a 3-column grid.

## Backend
- FastAPI app with CORS allowlist, security headers, CSP (non-dev/test)
- Config loader `core/config.py` with env support (`.env`)
- DB pool (psycopg-pool), schema and seeds
- Auth: register/login/me (JWT), Pydantic request/response models
- Tags API: list/search, create (admin), ban/unban (admin)
- Posts API: list (tags inline, `q` search, sort, pagination, total), get, replies, vote
- Post-tag endpoints: list, attach (admin), detach (admin)
- Users API: `GET /users/{handle}`, `GET /users/{handle}/posts`
- Rate limits on posting/replying
- Global error handlers (standardized JSON)
- Backend AI Translation Improvements: Strengthened prompts to avoid identical outputs, added retry logic, and fixed syntax errors in API files.

## Tests & CI
- Pytest with httpx ASGI tests
- Tests: health, auth/posts, tags/replies, permissions (403), rate limits (429), posts tags & filtering
- GitHub Actions workflow with Postgres service, schema+seeds apply, and tests

## Deployment & Dev
- User-level systemd unit: `templates/langsum-gunicorn.user.service`
- Dev runner: `scripts/dev_run.sh`
- Makefile targets: venv, install, apply-schema, seeds, dev, test, ci
- README with setup, tag filtering/management

## Documentation
- Read and incorporated all .md files in docs/bootstrap into project context; updated based on content review.

## Recently Completed
- Backend: Profiles - Add `GET /users/{handle}/replies` to show recent replies on profile
- Frontend: Simplified guest landing (`index.html`) and introduced authenticated home page (`home.html`)
- Frontend: Added dedicated Top Tags page (`tagstop.html`) with supporting route and `/tags/list-top` API
- Frontend: Added notifications center (`notification.html`) backed by `/notify/list`
- Frontend: Reworked account settings (`settings.html`) for language preference, notification test, and password change form
- Frontend: Replaced navbar notification labels with bell icon for consistent UX
- Frontend: Enabled infinite scroll on user profile posts/replies and fixed dashboard sentinel logic
- Backend: Resolved notify module imports and exposed `/user/settings` clean route
- Backend: Upgraded `/posts` search to PostgreSQL full-text ranking with snippets for matches
- Backend: Added Redis caching helpers for tag APIs and documented deployment requirements
