# Files inventory and purpose

This document lists every file in the repository with a short purpose description, plus clean‑up recommendations for legacy, misplaced, or empty items.

## Root

| File | Purpose |
|------|---------|
| `LICENSE` | MIT license text for GitHub. |
| `README.md` | High‑level project description and pointer to docs. |
| `Makefile` | Convenience targets for linting, tests, and dev workflows. |
| `package.json` | Node.js dependencies and scripts used by tooling. |
| `requirements.txt` | Python dependencies for backend/worker. |
| `.env` | **Runtime config** (not tracked). Copy from `config/env/.env.example`. |
| `.gitignore` | Git ignore rules (Python, Node, env files, caches). |
| `.github/` | GitHub-specific config (e.g. workflows, issue templates). |

## `src/`

### `src/__init__.py`
- Marks `src` as a Python package (empty).

### `src/backend/`

#### `src/backend/app/main.py`
- FastAPI app entrypoint: registers routers, middleware, static serving.

#### `src/backend/app/api/` (HTTP routers)
| File | Purpose |
|------|---------|
| `__init__.py` | Marks as Python package. |
| `admin_queue.py` | Admin moderation queue stubs (reports, new content). |
| `ai.py` | AI endpoints: translate/summarize posts, job status. |
| `auth.py` | Authentication: register, login, logout, magic link, password reset, me. |
| `bookmarks.py` | Bookmark/unbookmark posts, list bookmarks. |
| `i18n_admin.py` | Admin UI for managing translation strings and locales. |
| `moderation.py` | Moderation helpers (reports, review actions). |
| `notify.py` | Notification preferences and subscription endpoints. |
| `posts.py` | CRUD for posts and replies, voting, pagination, tag filtering. |
| `tags.py` | Tag CRUD, search, ban/unban, admin tag management. |
| `uploads.py` | File upload handling (images, attachments). |
| `users.py` | User profiles, preferences, search, admin user management. |

#### `src/backend/app/core/` (core utilities)
| File | Purpose |
|------|---------|
| `cache.py` | Redis cache wrapper (tag list acceleration). |
| `config.py` | Settings loader from `.env` and defaults. |
| `db.py` | Async PostgreSQL pool setup. |
| `deps.py` | FastAPI dependencies: auth, rate limits, DB session. |
| `email.py` | Email sending utilities (SMTP, templates). |
| `errors.py` | Global error handlers returning standardized JSON. |
| `notify.py` | Notification queue helpers (Redis). |
| `security.py` | Password hashing, JWT handling, token utilities. |
| `tag_access.py` | Tag visibility rules (admin‑only tags). |

#### `src/backend/app/db/` (database)
| File | Purpose |
|------|---------|
| `schema.sql` | Full database schema (tables, indexes, policies). |
| `seeds/initial.sql` | Seed data (admin user, default tags). |
| `patches/` | Migration/patch SQL files (named versions). |

#### `src/backend/app/schemas/`
| File | Purpose |
|------|---------|
| `ai.py` | Pydantic schemas for AI translation/summarization requests/responses. |

#### `src/backend/app/services/` (business logic)
| File | Purpose |
|------|---------|
| `ai_service.py` | Calls Node.js Ollama CLI for translation/summarization. |
| `language_utils.py` | Language detection/locale helpers. |
| `translation_cache.py` | Caches translation results in Redis. |
| `translation_queue.py` | Enqueues translation jobs for background worker. |

#### `src/backend/app/workers/`
| File | Purpose |
|------|---------|
| `translation_worker.py` | Redis queue consumer for translation/summarization jobs. |

#### `src/backend/js/` (Node.js bridge)
| File | Purpose |
|------|---------|
| `ollama.js` | Wrapper to call Ollama API (used by CLI). |
| `ollama_cli.mjs` | Minimal CLI invoked by `ai_service.py`. |

### `src/frontend/`

#### `src/frontend/pages/` (HTML pages)
| File | Purpose |
|------|---------|
| `index.html` | Landing page for guests (hero, feature cards). |
| `home.html` | Authenticated user home (welcome, latest posts). |
| `login.html` | Login form. |
| `register.html` | Registration form. |
| `magic-login.html` | Magic‑link login page. |
| `reset-password.html` | Password reset request form. |
| `set-password.html` | Set new password after reset. |
| `dashboard.html` | Main feed with tag filtering and pagination. |
| `create.html` | Post/reply creation editor. |
| `post.html` | Post detail with replies, voting, AI tools. |
| `tags.html` | Tag listing/search. |
| `tagstop.html` | Top tags page. |
| `user.html` | User profile (posts, replies, avatar placeholder). |
| `settings.html` | Account settings (language, password, notifications). |
| `notification.html` | Notifications list. |
| `admin.html` | Admin dashboard hub (links to sub‑pages). |
| `admin-*.html` | Dedicated admin pages: i18n, moderation, queue, tags, users. |
| `confirm-email.html` | Email confirmation page. |
| `features/` | Feature‑detail pages linked from landing. |
| `features/*.html` | Static feature documentation pages (translation engine, UI localization, etc.). |

#### `src/frontend/css/` (stylesheets)
| File | Purpose |
|------|---------|
| `base.css` | Base styles, CSS variables, resets. |
| `components.css` | Reusable UI components (badges, cards, buttons). |
| `layout.css` | Layout utilities (container, nav, footer). |
| `pages/` | Page‑specific CSS. |
| `pages/*.css` | Styles per page (index, home, dashboard, create, post, etc.). |
| `components/preloader.css` | Preloader component styles. |

#### `src/frontend/js/` (frontend modules)
| File | Purpose |
|------|---------|
| `auth.js` | Token handling, login/logout, auth headers. |
| `toast.js` | Toast notification system. |
| `notify.js` | Browser notification helpers. |
| `i18n-runtime.js` | Runtime i18n string resolver. |
| `i18n-ui.js` | UI language switcher logic. |
| `preloader.js` | Preloader component logic. |
| `ai.js` | Frontend AI tools (translate/summarize UI). |
| `bookmarks.js` | Bookmark/unbookmark UI logic. |

#### `src/frontend/assets/`
| File | Purpose |
|------|---------|
| `favicon.svg` | Site favicon (linked from HTML `<head>`). |
| `icons/` | Small SVG icons (notify, star filled/outline). |
| `topics/` | Hero and feature illustration images for landing page. |
| `uploads/` | **Runtime uploads** (user images/attachments). Not tracked. |

## `i18n/`
- JSON translation files for UI strings (`en.json`, `de.json`, etc.). Used by `i18n-runtime.js` and `i18n-ui.js`.

## `config/`
| File | Purpose |
|------|---------|
| `env/.env.example` | Template for runtime `.env` (DB, Redis, secrets). |
| `nginx/nginx.conf.example` | Nginx reverse‑proxy example with HSTS. |
| `systemd/langsum-gunicorn.user.service.example` | Systemd user service template for Gunicorn. |

## `scripts/`
| File | Purpose |
|------|---------|
| `send_test_email.py` | Send a test email (SMTP validation). |

## `dev/`
| File | Purpose |
|------|---------|
| `scripts/dev_run.sh` | Convenience script to start the app in dev mode. |
| `tests/` | Pytest test suite (auth, posts, tags, users, rate limits). |

## `docs/`
| File | Purpose |
|------|---------|
| `README.md` | Main development/deployment guide (already comprehensive). |
| `structure.md` | High‑level codebase structure map. |
| `files.md` | This file: detailed file inventory and clean‑up notes. |
| `CHANGELOG.md` | Version history. |
| `AGENTS.md` | Background workers and AI job documentation. |
| `HSTS-SETUP-INSTRUCTIONS.md` | HSTS/nginx setup notes. |
| `i18n.md` | Internationalization developer guide. |
| `notify_events.md` | Notification event types and payloads. |
| `openwebui.md` | OpenWebUI integration notes. |
| `roadmap.md` | Product roadmap. |
| `tags.md` | Tag system design and admin behavior. |
| `ai.md` | AI features (translation/summarization) guide. |
| `bookmark.md` | Bookmark feature documentation. |
| `bootstrap/` | Legacy bootstrap documentation (likely outdated). |
| `export/` | Placeholder for export utilities (empty). |

---

## Clean‑up recommendations

### Legacy files to consider deleting
| Path | Reason |
|------|--------|
| `dev/intxtonic.sql` | Full dump; prefer `schema.sql` + seeds/patches. |
| `dev/logs/translation-debug.log` | Large debug log; should not be tracked. |
| `docs/bootstrap/` | Outdated bootstrap docs; no longer referenced. |
| `docs/export/` | Empty placeholder directory. |

### Files in wrong locations that should be moved and rewired
| Path | Suggested new location | Notes |
|------|------------------------|-------|
| `dev/templates/nginx-config-with-hsts.conf` | Already moved to `config/nginx/nginx.conf.example`. |
| `dev/templates/langsum-gunicorn.user.service` | Already moved to `config/systemd/langsum-gunicorn.user.service.example`. |
| `dev/scripts/send_test_email.py` | Already moved to `scripts/send_test_email.py` (root). |
| `dev/logs/` | Should be git‑ignored and not tracked. | |

### Empty folders to delete
| Path | Reason |
|------|--------|
| `docs/export/` | Empty placeholder. |
| `src/frontend/uploads/` | Runtime uploads; should be git‑ignored and not tracked. |
| `src/__pycache__/`, `src/backend/app/__pycache__/`, `src/backend/app/api/__pycache__/`, `src/backend/app/core/__pycache__/`, `src/backend/app/db/__pycache__/`, `src/backend/app/schemas/__pycache__/`, `src/backend/app/services/__pycache__/`, `src/backend/app/workers/__pycache__/` | Python bytecode cache; should be ignored. |
| `dev/tests/__pycache__/` | Same as above. |
| `dev/templates/` | Empty after moving templates. |
| `dev/scripts/` | Empty after moving send_test_email.py. |
| `dev/logs/` | Empty after removing debug log. |

### Gitignore additions to prevent tracking unwanted files
Add to `.gitignore` if not already present:
```
# Runtime uploads
src/frontend/uploads/
# Logs
dev/logs/
*.log
# Python cache
__pycache__/
*.pyc
# Environment
.env
```

---

## Summary

- The codebase is well organized: backend under `src/backend/app`, frontend under `src/frontend`, docs in `docs/`, and deployment helpers in `dev/`.
- Main clean‑up targets: remove runtime uploads from git, delete the large debug log, archive the full SQL dump, and move deployment templates to `config/`.
- After removing the above, the repo will be clean and ready for a public GitHub push.
