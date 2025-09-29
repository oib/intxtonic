# Multi‑User Blog Webapp — Comprehensive Conceptual Framework

## 1) Overview
This specification outlines the conceptual architecture of a **multi‑user blogging platform** designed to support structured, collaborative, and multilingual publishing. Unlike conventional forum systems that rely on hierarchical rooms or groups, this platform employs a **tag‑centric model** in which content is discovered, classified, and retrieved through two types of tags: **mandatory tags** (curated by administrators) and **free tags** (contributed by users).

Channels, conceived as persistent user‑defined queries, function as personalized feeds created from tag filters. Content remains dynamic and can be reconfigured at any time by adjusting tag combinations.

The system integrates **artificial intelligence services**, specifically summarization and translation via the **Open‑WebUI API**. These allow any authenticated reader to generate concise summaries or translations of posts into their preferred language, creating an environment where language barriers are minimized.

Access is deliberately restricted: the application is a **closed community**. Only authenticated users may access substantive content such as posts, replies, tags, and profiles. Unauthenticated visitors are limited to the **Welcome** and **Login/Register** interfaces.

---

## 2) Core Entities
- **Users**: Ontological bearers of agency, instantiated with attributes including display_name, handle, locale, and role. Roles modulate authority (reader, author, moderator, admin). Users are circumscribed by daily activity quotas and may be silenced either manually or algorithmically.
- **Posts**: Primary discursive artifacts. Posts must instantiate all mandatory tag categories and may also accommodate elective free tags. Embedded imagery is accepted, though such media are transformed into storage‑efficient formats.
- **Replies**: Hierarchically nested annotations affixed to posts, supporting recursive threading, evaluative voting, and sorting. Replies may be nested up to a defined maximum depth (e.g., 5 levels), after which additional replies are flattened to preserve readability and performance.
- **Tags**: Constitutive elements of the classification grammar.
  - Mandatory tags: Controlled vocabularies under administrative custodianship.
  - Free tags: Emergent folksonomies authored by users.
  - System tags: Automatically generated metadata (e.g., `user:<display_name>`, `lang:<locale>`).
- **Channels**: Persisted tag queries, functioning as individualized or communal interpretive streams.
- **Media**: Uploaded images, which undergo algorithmic normalization (resizing, recompression, metadata stripping).

---

## 3) Roles & Permissions
- **Administrator**: Maximal jurisdiction, encompassing configuration, user and role management, tag taxonomy maintenance, imposition of silences, and access to statistical dashboards. At instantiation, **user1** is elevated as the primordial administrator.
- **Moderator**: Sub‑administrative authority focused on discursive hygiene: retagging, resolving reports, enforcing silences. Moderator voting power is algorithmically magnified.
- **Author**: Entitled to instantiate posts and replies, apply tags, upload images, and invoke AI functions.
- **Reader**: Possesses the baseline capacity to browse, filter, vote, reply, and request AI assistance but is precluded from creating primary posts absent role elevation.

**Example Scenario**: When a user posts spam, a moderator can silence them temporarily (e.g., 24 hours), while an administrator has the authority to permanently ban the user or adjust system-wide settings like voting weights. This ensures efficient community management with clear role boundaries.

**Visibility Regime:** Substantive artifacts are accessible exclusively to authenticated participants. Guests encounter only initiation interfaces.

---

## 4) Tag Taxonomy
The taxonomy of tags constitutes the semiotic architecture of the system:
- **Mandatory Tags**: Posts must instantiate one tag from each mandatory category (e.g., Topic, Project, Visibility).
- **Free Tags**: Optional and user‑generated, enabling folksonomic elaboration.
- **Administrative Tools**: The Admin UI supports tag creation, deletion, prohibition, merging, renaming, and locking. Prohibited tags persist in archival form but are proscribed from new instantiation.

---

## 5) Data Model (Relational)

### Users
- **users**: Encapsulates role, silence states, and per-user limits.
- **groups**, **user_groups**: Facilitate collective associations.
- **user_limits**: Customized quota overrides.

### Content
- **posts**, **post_tags**: Discursive artifacts and their taxonomic mappings.
- **replies**: Nested discourse units with evaluative metrics.
- **media**: Digitally transformed image metadata.
- **channels**: Personalized feeds based on tag filters.

### Metadata & Governance
- **tags**, **tag_permissions**, **tag_categories**: Ontological scaffolding of classification.
- **invites**: Tokens for curated admission.
- **reports**: Abuse flagging and moderation workflow.
- **app_settings**: Centralized repository of registration mode, verification rules, quotas, media processing parameters, auto-silence thresholds, and voting weights.

### Metrics & AI
- **votes**: Atomic evaluative acts.
- **ai_outputs**: Persisted AI-generated artifacts.
- **user_metrics_daily**, **stats_rollup**: Longitudinal analytical tables.

Automatic assignment of system tags occurs upon post creation or modification.

---

## 6) Filter & Channel Logic
The **filter bar** constitutes the primary epistemic navigation apparatus. It presents categorical chips, predictive search for free tags, and reset affordances. Composite filters can be persisted as **channels**, which represent enduring perspectives upon the corpus. Channels may be designated as public (communal visibility) or private (individual utility).

---

## 7) AI Features
- **Summarization**: Algorithmic condensation of discourse objects.
- **Translation**: On‑demand linguistic transformation into the reader’s locale.
- **Caching**: Computationally expensive outputs are retained for reuse.
- **Administrative Configuration**: API endpoint, authentication credentials, and model selection are specified within system settings.

---

## 8) Voting & Replies
- **Voting Dynamics**: Posts and replies may be valorized or disfavored via up/down votes. Moderator and administrator votes are algorithmically weighted.
- **Sorting Modalities**: Content ordering supports Hot, Top, New, and Controversial typologies.
- **Threaded Replies**: Replies permit recursive nesting with collapsibility.
- **Auto‑Silence**: Users whose contributions are adjudged negatively at scale may be algorithmically silenced under administratively defined thresholds.

---

## 9) User Interface and Experience (UI/UX)
The user experience can be described in role-based perspectives:
- **Guests**: Presented only with Welcome, Login, and Register portals.
- **Authenticated Users**:
  - **Readers**: Use the filter bar, view post cards, open detail pages with threaded replies, and access AI tools.
  - **Authors**: In addition to reader features, compose posts with mandatory tag pickers and media upload tools. Daily quotas are shown near the composer.
  - **Silenced Users**: Encounter a disabled composer with explanatory details (reason, duration).
  - **Administrators/Moderators**: Access specialized dashboards for user management, silencing, reporting workflows, system settings, and statistical review.
- **Voting Interface**: Provides up/down voting with tooltips clarifying weighted vote effects.
- **Guests**: Confronted with Welcome, Login, and Register portals.
- **Readers**: Access filter bar, post cards, detail pages with threaded replies, and AI tools.
- **Authors**: Employ composition interfaces with mandatory tag pickers and media upload affordances. Quotas are visibly annotated.
- **Silenced Users**: Encounter disabled composition interfaces with explanatory metadata (reason, duration).
- **Voting UI**: Tooltips explicate weighted voting logic.
- **Administrators/Moderators**: Access dashboards for user management, silencing, reporting workflows, system settings, and statistical review.

---

## 10) API (Conceptual Sketch)
- **Authentication**: Registration (open or invite‑only), login, logout.
- **Limits & Silence**:
  - `GET /me/limits` — Return residual quota.
  - `PATCH /admin/users/{id}/limits` — Adjust per‑user limits.
  - `PATCH /admin/users/{id}/silence` — Enforce or rescind silence.
- **Posts**: CRUD, voting, quota enforcement, silence checks.
- **Replies**: CRUD, hierarchical nesting, voting.
- **Votes**: Weighted aggregation implemented server‑side.
- **Media**: Upload with algorithmic transformation; deletion.
- **AI**: Summarization and translation endpoints.
- **Administration**: User, role, invite, tag, settings, and analytics endpoints.

---

## 11) Security & Governance
- **Authentication Wall**: Content sequestered behind authentication.
- **Registration Regimes**: Configurable (open vs. invite‑only).
- **RBAC**: Role‑based access control enforced server‑side.
- **Quota and Silence Enforcement**: Hard limitations on activity; silenced users restricted from content production and evaluation.
- **Auto‑Silence**: Algorithmic suppression of persistently disvalued users.
- **Weighted Voting**: Configurable role‑based multipliers.
- **Media Pipeline**: Strips sensitive metadata, constrains dimensions, compresses, optionally virus‑scans.
- **Auditing**: Immutable records of administrative interventions.

---

## 12) Performance & Information Retrieval
- **Indexes**: Exhaustive indexing across all core entities.
- **Counters**: Trigger‑maintained weighted aggregates.
- **Caching**: Volatile stores (e.g., Redis) for high‑traffic operations.
- **Storage**: Configurable (local file system or S3‑compatible object store).
- **Jobs**: Scheduled evaluations of auto‑silence criteria.

---

## 13) Internationalization
- **Linguistic Range**: The user interface is translated into **28 European languages**.
- **Locale Preference**: Persisted per user.
- **Formatting**: Temporal and numerical representations are localized.
- **Language Tags**: Distinct from UI locale; reflect content language.

---

## 14) Migration & Administrative Interface
Administrative tooling encompasses:
- Registration mode toggling
- AI provider configuration
- Image pipeline parameters
- Activity quotas
- Voting weights
- Auto‑silence thresholds
- Tag management (CRUD and ban logic)
- User management (role elevation, silencing)
- Statistical and diagnostic dashboards

---

## 15) Minimum Viable Product (MVP) Checklist
- Authentication wall with registration modality control
- Seeding of user1 as administrator
- Mandatory tag category enforcement
- CRUD for posts, tagging, filter bar, and channels
- Replies with voting and weighted aggregation
- AI summarization/translation invocation
- Daily quota enforcement with overrides
- Image pipeline (resize, compress, strip EXIF)
- Tag management UI
- Administrative statistics dashboard
- Silence and auto‑silence enforcement

---

## 16) Prospective Extensions
- **Syndication**: RSS/Atom channel feeds.
- **Integrations**: Event‑triggered webhooks.
- **Semantic Expansion**: Tag synonymy and aliasing.
- **Storage Control**: Per‑user media quotas.
- **Advanced Moderation**: Queues with automated heuristics.
- **Expanded Attachments**: Support for documents, audio, video.

---

## Appendix A — SQL DDL
- **Enumerated Types**: user_role, tag_type, post_status, reply_status, ai_kind, vote_subject
- **Relational Schemas**: users, app_settings, invites, tags, tag_categories, tag_permissions, posts, post_tags, replies, votes, media, user_limits, ai_outputs, channels, reports, user_metrics_daily, stats_rollup
- **Procedures**: Weighted vote aggregation, auto‑silence evaluation
- **Initialization**: Seeding of user1 as administrator

## Appendix B — Endpoint Stubs
- FastAPI exemplars for authentication, posts, replies, votes, media, administration, silence, limits, and statistics.

## Appendix C — Seed & Invite Helpers
- SQL exemplars for initializing mandatory tags
- Invite code generation routines

## Appendix D — /auth/register Logic
- Distinctions between open and invite‑only registration
- Error taxonomies
- Pseudocode with security annotations

## Appendix E — Media Upload Endpoint
- FastAPI stub for `/media/upload`
- Pillow‑based `transform_image()` for resizing, compression, EXIF removal, and format conversion

## Appendix F — Silence & Weighted Voting
- Administrative and algorithmic silencing mechanisms
- Automated silence routine predicated on vote ratios
- Weighted voting for elevated roles
- SQL triggers for maintaining aggregated vote metrics
