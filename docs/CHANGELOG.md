# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning where applicable.

## [Unreleased]

### Added
- Daily upload rate limit (default 30/day, `DEFAULT_MAX_UPLOADS_PER_DAY`).
- Redis per-IP/per-account auth throttling: login (10 fails/IP, 5/account per 10min → 429, cleared on success), register (10/IP), magic-link requests (5/IP), token validation (15 fails/IP).
- Plain daily `pg_dump` cron on the container → `/var/lib/autopostgresqlbackup/plain/intxtonic/` (directly restorable, unlike autopostgresqlbackup output which embeds `CREATE DATABASE`/`\connect`).
- Gitea push-mirror to GitHub (sync_on_commit, 1h interval) — `origin` stays a mirror target, no manual dual-push needed.
- Shared `src/frontend/js/markdown.js` (renderer + escapeHTML, replaces 3 copies) with an 11-case `node:test` suite; `make test-js`.
- `docs/security-notes.md` endpoint-group audit.

### Changed
- `dashboard.html`/`home.html` inline module scripts extracted to `src/frontend/js/pages/` (import map covers them).
- App split out of `webapps-unified` into dedicated `intxtonic.service` on :8100 (dispatcher APPSPEC cleaned; nginx repointed).
- Gitea remote URLs no longer embed the token — moved to `~/.git-credentials` on at1 and the server.

## 2026-10-27

### Security
- Fixed stored XSS in the post/reply Markdown renderer: `escapeHTML` now escapes quotes so `src="…"`/`href="…"` attribute injection is closed; tag slugs, reply authors and server error text are also escaped (`post.html`, `create.html`).
- Escaped AI output before `innerHTML` insertion in translate/summarize paths (`ai.js`).

### Added
- `Cache-Control: no-cache` on all `text/html` responses and on `/src/frontend` + `/i18n` statics.
- Cache-busted static assets: `page_response()` stamps `?v=<git-sha>` on `/src/frontend/` URLs and injects an import map so relative module imports resolve to the same versioned URL.
- Summarize button explains its disabled state ("Translate the post first"); visible hint + `aria-describedby`.
- Server error messages surfaced on Create (publish) and in translate/summarize toasts.
- Tag-attach failures reported on Create; Publish disabled after success.
- Markdown tables render; consecutive list items no longer split into separate lists.
- `<time>` elements with locale-formatted dates; skip link, meta description, labels on all inputs, `aria-label`s on vote buttons; consistent header across home/post/create pages.
- Backend title length validation (max 200 chars) matching the UI.

### Fixed
- Headings keep full contrast (`--tx-0`) after muting `--tx-2` for meta text.
- White flash on load (preloader `!important` colors no longer override the dark fallback).
- Double toast on Share; wrong "max 600" message corrected to 1200.

## 2025-10-24

### Added
- Introduced `AGENTS.md`: initial agent registry with Agent Directory, configuration, interfaces/protocols, security & permissions, interaction flows, and examples.
