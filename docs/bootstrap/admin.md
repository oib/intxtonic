# Admin & Moderator — UI & Task Concept

## Roles & Permissions

### Roles
- **Admin**: Full platform control.
- **Moderator**: Community safety & content curation; no access to critical system settings or billing.

### Moderator Task Checklist (daily)
- **Review queues**: Clear Flags, Low-score, and Image checks down to <10 pending items.
- **Respond to escalations**: Resolve user reports older than 12 hours; leave audit note for follow-up.
- **Spot-check content**: Sample 10 recent posts for guideline compliance; retag or warn as needed.
- **User status audit**: Confirm any auto-silenced accounts have a documented decision.
- **Sync with admins**: Surface trends (spam waves, tag misuse) via the shared moderation log channel.

### Permission Matrix (summary)
| Capability | Admin | Moderator |
|---|:--:|:--:|
| View dashboards & stats | ✅ | ✅ |
| Moderate posts/replies (approve, hide, delete, lock) | ✅ | ✅ |
| Tag management (create, merge, delete) | ✅ | ✅ (no hard delete) |
| User management (profile, roles, limits, silence, ban) | ✅ | Limited (no role elevate to Admin) |
| Voting weight configuration | ✅ | ❌ |
| Rate limits & quotas (per‑role, per‑user) | ✅ | ❌ |
| Registration policy (open/closed/invite-only) | ✅ | ❌ |
| Localization settings (28 EU langs) | ✅ | ❌ |
| System settings (storage, images, AI, SMTP) | ✅ | ❌ |
| Audit log & exports | ✅ | Read‑only |

### Escalation Guidelines
- **Critical security issues** (credential leak, mass spam bypass) → escalate immediately to Admin and disable affected features if possible.
- **Legal takedowns / GDPR requests** → Admin only; moderators collect metadata and notify Admin.
- **Repeat offenders**: After two silences in 30 days, moderators may recommend permanent bans; Admin approves final action.

### Moderator Permissions by Surface
| Surface | Read | Act | Notes |
|---|:--:|:--:|---|
| Moderation queues | ✅ | ✅ | Bulk approve/hide/delete; lock threads. |
| Content explorer | ✅ | ✅ | Cannot permanently delete; may soft-delete and tag. |
| Tag manager | ✅ | ⚠️ | Can create/merge/ban; delete escalated to Admin. |
| User directory | ✅ | ⚠️ | May warn, silence, temporary ban; cannot change roles/weights. |
| Reports analytics | ✅ | ⚠️ | May close reports with notes; cannot export datasets. |
| Audit log | ✅ | ❌ | Read-only for transparency. |
| Settings | ✅ (limited) | ❌ | See read-only overviews; no edits. |

---

## Admin Navigation (left sidebar)
1. **Overview**
2. **Moderation**
3. **Content**
4. **Tags**
5. **Users**
6. **Reports**
7. **Localization**
8. **Settings**
9. **Audit & Exports**

Moderator sidebar shows: Overview, Moderation, Content, Tags, Users (limited), Reports, Audit (read‑only).

---

## 1) Overview (Dashboards)
**Purpose:** At‑a‑glance health & workload.

**Widgets**
- Counters: *Users*, *Active today*, *Posts*, *Replies*, *Tags*, *Images*, *Storage used*.
- Community health: *Avg. score*, *Flags in queue*, *Auto‑silenced users*.
- Leaderboards: *Top users* (posts/replies/upvotes), *Top tags*.
- Trends: posts/day, new users/day.

**Actions**
- Quick toggles: **Open registration**, **Invite‑only**, **Closed**.
- Button: **Review queue** (go to Moderation).

---

## 2) Moderation
**Purpose:** Inbox for all items requiring attention.

**Queues**
- **Flags**: user‑flagged posts/replies.
- **Low‑score**: auto‑surfaced under threshold.
- **New users** (optional verification, if enabled).
- **Image checks**: oversized, failed conversion.

**Item card**
- Metadata: author, age, current score, tag(s), language, reports count.
- Previews: content + image (auto‑resized).
- Actions: **Approve**, **Hide**, **Delete**, **Lock thread**, **Tag**, **Warn**, **Silence (duration)**, **Ban**.
- Tools: **View author profile**, **History**, **Open in context**.

**Bulk actions**
- Select many → approve/hide/delete/tag/move.

**Automation** (configurable)
- Auto‑hide below score X after Y votes.
- Auto‑silence if rolling score < threshold for N items (as specified in concept).

---

## 3) Content
**Browse & manage posts/replies**
- Filters: timeframe, language, tag, score range, author, status (visible/hidden/deleted/locked).
- Batch: retag, lock/unlock, hide/unhide, delete.
- Open item: full thread, revision history, moderation notes.

**Pinned/Featured**
- Set homepage featured posts per language.

---

## 4) Tags
**Purpose:** Taxonomy curation.

**Tag list**: name, usage count, last used, language scope.

**Actions**
- **Create** tag (name, slug, description, language scope).
- **Merge** tag A → B (migrates content, preserves redirects).
- **Delete** (Admin only; Moderator soft‑delete/hide).
- **Ban** tag (disallow usage, auto‑flag on use).

**Rules**
- Reserved tags (system) locked from deletion.

---

## 5) Users
**Directory** with search: name/email/id, status (active/silenced/banned), role, language(s), join date, karma.

**User profile (admin panel)**
- **Overview**: stats, recent activity, scores, flags.
- **Roles & weights**: set role (User/Moderator/Admin)*, adjust **voting weight** (Admin only).
- **Limits**: daily post/reply caps; **rate limits**; **image upload cap**.
- **Status**: **Warn**, **Silence (duration)**, **Ban** (reason & expiry), **Unsilence/Unban**.
- **Security**: reset password (if local auth), revoke sessions, require re‑verify.
- **Localization**: preferred UI language(s).

*Moderators cannot grant Admin role.

---

## 6) Reports
**Flag intake & analytics**
- Filters by reason, tag, language, time.
- Reporter reputation (weight flags by reporter trust).
- Outcomes dashboard: approved/hidden/deleted ratios.

---

## 7) Localization (28 EU langs)
**UI translation management**
- Keys table: search missing/outdated; inline edit; export/import JSON/PO.
- **Machine‑assist**: enqueue key(s) → request translations via OpenWebUI API; human review before publish.

**Content workflows**
- Per‑post actions: *Request summary/translation* (on‑demand); store translated variants; show request status.

**Policies**
- Legal pages per language (Imprint/Privacy/Terms) with versioning.

---

## 8) Settings
Grouped tabs:

**General**
- Site name/logo/theme (dark theme primary: orange text, ice blue/white outlines).
- Registration policy: Open / Invite‑only / Closed.
- Voting model: up/down with score; **Moderator votes count x2** (from concept).

**Content**
- Post/reply limits per role/day; cooldowns.
- Score thresholds for auto‑hide/auto‑silence.
- Image handling: max width, auto‑resize, format (WebP/AVIF), compression levels, storage path/bucket.

**AI Integration**
- OpenWebUI endpoint & key; models for **summary**, **translation**, **moderation assist**; per‑day caps.

**Localization**
- Enabled languages; default; fallback chain.

**Email / Notifications**
- SMTP settings; templates per language; rate limits.

**Security**
- Password policy; 2FA (if enabled); session TTL; invite codes management.

**Backups & Data**
- Export/Import site data; scheduled backups (metadata only, not images).

---

## 9) Audit & Exports
- **Audit log**: who did what, when (role, action, target, diff snapshot).
- Filters + CSV/JSON export.
- **Transparency report**: quarterly stats for community.

---

## Moderator Toolkit (quick panel)
- **Search** anything (users, posts, tags) with keyboard shortcut.
- **Create canned responses** (warnings, guidance) with variables.
- **Context preview**: open thread inline while staying in queue.
- **One-click actions**: Hide + Warn, Lock + Pin, Tag + approve.
- **Escalate button**: Send item to Admin inbox with required note template (reason, impact, suggested action).
- **Shift hand-off**: End-of-day summary auto-generates from resolved items and pending escalations.

## Expanded Moderator Tasks and Permissions

### Moderator Workflows
- **Flag Review**: Moderators can access a queue of flagged content, review reports, and decide on actions like hiding or deleting posts. Example: Use the moderation dashboard to filter flags by reason and apply bulk actions for efficiency.
- **User Management**: Moderators can silence or ban users for violations, with options to set durations and reasons. Sub-step: After banning, send a notification to the user with appeal instructions.
- **Content Moderation**: Handle low-score content auto-flags, lock threads to prevent further replies, and manage tag applications to maintain community standards.
- **Reporting and Auditing**: Moderators have read-only access to audit logs to review actions, ensuring transparency in moderation decisions.

### Additional Permissions Details
- Moderators can perform content curation but are restricted from system-level changes like role assignments or site settings.
- Integration with AI: Moderators can use AI-assisted tools for content review, such as automatic flagging of inappropriate language, but final decisions remain human-driven.
- Moderators may schedule follow-up reminders for unresolved cases; reminders surface in the Overview dashboard the next day.

### Updated Permission Matrix with Examples
| Capability | Admin | Moderator | Example |
|---|:--:|:--:|:--|
| View dashboards & stats | ✅ | ✅ | Admins can view full analytics, while moderators see community health metrics. |
| Moderate posts/replies (approve, hide, delete, lock) | ✅ | ✅ | Moderators can hide a post flagged for misinformation, with an audit log entry. |
| Tag management (create, merge, delete) | ✅ | ✅ (no hard delete) | Moderators can merge tags but not permanently delete them to avoid data loss. |
| User management (profile, roles, limits, silence, ban) | ✅ | Limited (no role elevate to Admin) | Moderators can silence users for 24 hours, but only admins can change user roles. |
| Voting weight configuration | ✅ | ❌ | Admins adjust voting weights to combat spam, e.g., reducing weight for new accounts. |
| Rate limits & quotas (per-role, per-user) | ✅ | ❌ | Admins set daily post limits, e.g., 5 posts per day for new users. |
| Registration policy (open/closed/invite-only) | ✅ | ❌ | Admins switch to invite-only mode during high traffic. |
| Localization settings (28 EU langs) | ✅ | ❌ | Admins manage language options, ensuring compliance with EU multilingual requirements. |
| System settings (storage, images, AI, SMTP) | ✅ | ❌ | Admins configure AI API keys for moderation tools. |
| Audit log & exports | ✅ | Read-only | Moderators can view but not export logs for transparency.

---

## Workflows

### A) Flag → Decision
1. Item flagged → appears in **Moderation > Flags**.
2. Moderator opens card, reviews context & history.
3. Choose action: Approve / Hide / Delete / Lock; optionally **Warn/Silence** author.
4. Log written to **Audit**; reporter(s) optionally notified.

### B) Auto‑silence recovery
1. User auto‑silenced by threshold rule.
2. Moderator reviews **Users > Status**.
3. Options: uphold silence (adjust duration) or **Unsilence** with note.

### C) Tag merge
1. Tags > select A then **Merge** into B.
2. System reindexes content; redirects A → B.
3. Audit entry recorded.

### D) Translation request (on‑demand)
1. Reader clicks **Translate/Summarize**.
2. Job queued (OpenWebUI); status visible in **Localization > Jobs**.
3. Result stored and linked to original post; moderator can **Approve** to publish as official translation.

---

## Data Model (admin‑relevant)
- **User**: role, languages, limits {posts/day, replies/day, img quota}, status {active, silenced_until, banned_until}, voting_weight.
- **Content**: post/reply, language, tags[], score, status, history[].
- **Tag**: name, slug, language scope, status {active, banned}, redirects.
- **Flag**: target(id,type), reasons[], reporter_id, created_at, decision.
- **Audit**: actor_id, action, target_ref, diff, created_at.
- **LocalizationJob**: type {summary, translation, key}, source_lang, target_lang, status, result_ref.
- **Settings**: grouped JSON blobs with versioning.

---

## KPIs & Health
- Median time‑to‑first‑moderation.
- % content auto‑hidden vs manually.
- New user 7‑day retention.
- Ratio: translations requested → approved.

---

## Access Controls & Safety Notes
- Moderators cannot change **system settings**, **registration policy**, **voting weights**, or grant **Admin** role.
- High‑risk actions (delete tag, ban user, hard delete content) require confirmation + reason.
- All actions write to **Audit**.

---

## Roadmap (Backlog)
- Moderator mobile UI.
- Saved filters & shared queues.
- Per‑language moderator teams.
- Appeal workflow for bans/silences.
- Granular image NSFW detection (server‑side).
