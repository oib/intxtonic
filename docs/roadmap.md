# 2025 inTXTonic Roadmap

*Project: intxtonic.net*

## 🚀 Phase 1 · Immediate Focus
- **Frontend**: Admin moderation page polish (resolve actions, tag management create/ban/unban) [in progress]
- **Frontend**: Admin user list enhancements (search, pagination, disable/enable, email visibility)
- **Admin Tools**: Confirm UI parity with restricted tag assignments (roles, bulk ops, audit logs)

## ⏭️ Phase 2 · Next Up
- **Docs**: Finalize `layout.md` for 960px grid and mobile design
- **Docs**: Expand `admin.md` with moderator tasks and permissions
- **Dev & Docs**: Update README (profiles section, moderation notes, deployment with nginx reverse proxy)
- **Dev & Docs**: Add automated tests for user endpoints and multi-tag search scenarios
- **Dev & Ops**: Capture coverage artifacts in CI and surface them on PR comments
- **Backend**: Add integration tests enforcing restricted tag visibility (guests vs members vs admins)
- **Analytics**: Track tag usage and visibility changes for audit logs

## 🔮 Phase 3 · Later
- **Product**: Improve search ranking and highlights (extend trigram/full-text experience on the frontend)
- **Infrastructure**: Evaluate Redis cache strategy for tag listings (per-account scoping, smarter invalidation)

## ✅ Completed

### 🎨 Frontend
- Base styles and components documented in `src/frontend/css/base.css`, `components.css`, `layout.css`
- Toasts and browser notifications via `src/frontend/js/toast.js` and `src/frontend/js/notify.js`
- Landing and account pages: `index.html`, `login.html`, `dashboard.html`, `post.html`, `user.html`
- Tag filtering UX on dashboard with deep links (`?tags=`), removable chips, ESC clear, and persistence
- Posts search (`q`) combined with tag filters, per-page limit, total count, and Load more UX
- Admin tag controls on post page for slug-based attach/detach with public tag chips deep-linking to dashboard
- Admin user management overview with handle/email/status, disable/enable actions, and tag assignment workflows (`admin-users.html`)
- i18n Admin page enhancements with batch/per-key translation, debug panel, and dynamic UI updates
- Navbar layout standardization (centered brand, edge-aligned controls) using a 3-column grid
- Simplified guest landing (`index.html`) plus authenticated home (`home.html`)
- Landing hero reflowed for alternating layout with summary-focused copy and 50/50 grid
- Reworked account settings (`settings.html`) for language preference, notification test, password change form, and navbar consistency
- Notifications center (`notification.html`) powered by `/notify/list`
- Infinite scroll for user profile posts/replies and refined dashboard sentinel logic
- Settings password change form wired to `PATCH /users/me/password` with inline validation and success toasts
- Tags admin tools now include `POST /tags/{id}/unrestrict` for opening restricted tags globally
- FastAPI app with CORS allowlist, security headers, and CSP outside dev/test
- Config loader `core/config.py` with environment support
- Psycopg pool, schema, and seed data
- Tags API (list/search, create, ban/unban) and posts API (list with tags/search/sort/pagination/total, get, replies, vote)
- Users API: `GET /users/{handle}`, `GET /users/{handle}/posts`, `GET /users/{handle}/replies`
- Admin user endpoints for listing accounts and toggling disabled state (`GET /users/admin`, `POST /users/admin/{id}/disable`, `POST /users/admin/{id}/enable`)
- Rate limits on posting and replying with standardized JSON error handlers
- Backend AI translation improvements: prompt hardening, retries, syntax fixes
- Resolved notify module imports and exposed `/user/settings`
- Upgraded `/posts` search to PostgreSQL full-text ranking with snippets
- Redis caching helpers for tag APIs and documented deployment requirements
- Covered password rotation scenarios (`/users/me/password`) with async tests in `tests/test_users_password.py`
- Added test coverage for tag unrestriction flow in `tests/test_tags_replies.py`
- Established `log/` folder for capturing manual responses (e.g., `log/login_response.json`) and future app logs; prefer `journalctl --user -u intxtonic.service` and app logs for auditing requests instead of manual snapshots
- Landing language picker now auto-detects browser locale (fallbacks to `en` if unsupported)

### 🧪 Tests & CI
- Pytest with httpx ASGI coverage of health, auth/posts, tags/replies, permissions (403), rate limits (429), and post filtering
- GitHub Actions workflow with Postgres service, schema + seeds apply, and test execution
### ⚙️ Deployment & Development Tooling
- User-level systemd unit template `templates/langsum-gunicorn.user.service`
- Dev runner script `scripts/dev_run.sh`
- Makefile targets for venv, install, schema apply, seeds, dev, test, ci
- README covering setup and tag filtering/management workflows

### 📚 Documentation
- Reviewed and incorporated all `docs/bootstrap/` materials into project context with updates as needed
- This roadmap kept current with admin tooling, hero UX, and backend visibility milestones

## 🧭 Operational Checklist

### ☀️ Daily Setup
- [ ] Pull latest changes from main branch
- [ ] Activate poetry/venv and ensure dependencies installed
- [ ] Start backend services (Postgres, FastAPI via gunicorn or uvicorn)
- [ ] Launch frontend dev server (if applicable)
- [ ] Verify .env configuration matches environment (API keys, DB URL)

### 🧩 Step-by-step Workflow (Windsurf)
1. Launch inTXTonic and open the target workspace.
2. Run `/ns` to identify the next actionable step from the user's request.
3. Use `update_plan` to record 3-5 concise steps for the task.
4. Inspect relevant files (via `Read` or editor) before modifying anything.
5. Apply changes with `apply_patch`, keeping diffs minimal and scoped.
6. Run targeted verifications or tests locally; capture commands in notes.
7. Update docs or TODOs impacted by the change.
8. Summarize work in the final response with sections: Summary, Verification, Status.
9. Mark completed plan steps and close with next-step guidance if needed.

### 📥 Task Intake
- [ ] Read issue/ticket description and acceptance criteria
- [ ] Review related files or previous tasks in docs/
- [ ] Confirm target branch and code ownership guidelines
- [ ] Update docs/todo.md with tasks in progress

### 🔁 Development Loop
- [ ] Create/update plan using Cascade `update_plan`
- [ ] Implement backend changes with minimal diff via `apply_patch`
- [ ] Implement frontend changes and keep styling consistent
- [ ] Run relevant automated tests (pytest, frontend tests)
- [ ] Perform manual QA (HTTP requests, UI interactions)
- [ ] Log or capture evidence of fixes (screenshots, console output)

### 📝 Review & Documentation
- [ ] Update docs/done.md and docs/todo.md accordingly
- [ ] Note configuration or deployment steps in docs/
- [ ] Ensure new endpoints/components are documented
- [ ] Mention migration or schema changes explicitly

### 🚢 Delivery
- [ ] Summarize changes with sections: Summary, Verification, Recommended Actions
- [ ] Provide commands for verification (tests, service restarts)
- [ ] Highlight follow-up work or known limitations
- [ ] Confirm deployment status or next steps
