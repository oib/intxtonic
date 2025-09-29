# Roadmap

## Phase 1 · Immediate Focus
- **Backend**: ✅ `PATCH /users/me/password` implemented; ready for frontend integration
- **Frontend**: Admin moderation page polish (resolve actions, tag management create/ban/unban) [in progress]
- **Frontend**: Wire settings password change form to new backend endpoint and add confirmation UX
- **Docs**: Fill in step-by-step workflow for Windsurf in `docs/checklist.md`
- **Admin Tools**: Ship UI for assigning restricted tags to users/roles (surfacing visibility list, add/remove actions)

## Phase 2 · Next Up
- **Docs**: Finalize `layout.md` for 960px grid and mobile design
- **Docs**: Expand `admin.md` with moderator tasks and permissions
- **Dev & Docs**: Update README (profiles section, moderation notes, deployment with nginx reverse proxy)
- **Dev & Docs**: Add automated tests for user endpoints and multi-tag search scenarios
- **Dev & Ops**: Capture coverage artifacts in CI and surface them on PR comments
- **Backend**: Add integration tests enforcing restricted tag visibility (guests vs members vs admins)
- **Analytics**: Track tag usage and visibility changes for audit logs

## Phase 3 · Later
- **Product**: Improve search ranking and highlights (extend trigram/full-text experience on the frontend)
- **Infrastructure**: Evaluate Redis cache strategy for tag listings (per-account scoping, smarter invalidation)
