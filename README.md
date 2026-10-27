# inTxTonic

Multilingual, tag‑centric social forum and blogging platform.

- **Frontend**: static HTML/CSS/JS in `src/frontend/` (mobile‑first, dark theme).
- **Backend**: FastAPI app in `src/backend/app/` with PostgreSQL and Redis.
- **Features**: tag‑based posts and replies, translations/summaries via AI worker, admin tools for tags and moderation.

## Features

**Posts & content**
- Markdown posts (up to 1200 chars) with tag-based organization, replies/nested comments, up/down voting and scores
- Visibility levels per post (`logged_in`, `private`, `unlisted`); soft-delete for posts and replies
- Full-text search with highlighted snippets (Postgres `tsvector`/`ts_headline`)
- Card previews with clamped excerpts, pagination and tag feeds
- Image/file uploads with alt text

**AI**
- Post translation via a background worker (`intxtonic-worker`), cached translations
- Summarize-from-translation flow (Summarize unlocks after translating)
- Read-time and chunking helpers for long bodies

**Accounts & auth**
- Email registration with confirmation links, magic-link login, password reset/set flows
- Session tokens + CSRF validation, user settings (language, notifications, password)
- Public user profile pages, per-user dashboards, daily post limits

**Discovery & notifications**
- Bookmarks (posts, replies, tags) with folders/notes, bookmark toggles on tag badges
- Real-time notifications over SSE (`/notify/events`), notification page
- Top-tags board, per-tag pages, tag visibility/restriction controls

**Admin & moderation**
- Admin dashboards for users, tags, moderation queue and i18n management
- Moderation queue with reports and actions, restricted-tag enforcement
- Translation/i18n runtime with admin-editable locale files (`i18n/`)

**Frontend & platform**
- Mobile-first dark theme, skip links/labels/aria on key UI, `<time>`-based locale dates
- Security headers (CSP, X-Frame-Options, nosniff), stored-XSS-safe Markdown renderer
- Cache-busted static assets (`?v=<git-sha>` + import map) so deploys take effect immediately
- Public landing + feature pages (`/features/*`) describing the platform

## Live site

- **Visit the live site**: https://intxtonic.net/

For detailed setup, database, and deployment instructions, see:

- `docs/README.md` – local development, database setup, deployment notes.
- `docs/structure.md` – high‑level codebase structure.
