# ui\_translate.md — UI Translation Concept (OpenWebUI-powered)

## 1) Goals

- Single source of truth in **English (en)**.
- Admins manage translations per **key** (field) via a **Key View**.
- Add a new language in one click, then **batch-translate all missing keys** with AI (OpenWebUI).
- Human review + approval before changes go live.
- Safe fallbacks, versioning, and audit trail.

---

## 2) Terminology

- **Namespace (ns):** logical grouping (e.g., `layout`, `dashboard`, `post_editor`).
- **Key:** unique identifier inside a namespace (e.g., `toast.saved`, `btn.submit`).
- **Entry:** the localized text for a language (e.g., `de`, `fr`).
- **Status:** `draft` (machine), `reviewed` (human checked), `approved` (live).
- **Source:** `machine` or `human`.

---

## 3) Data Model (DB-first)

> Postgres tables; minimal, extensible.

### 3.1 Tables

- `i18n_locales`\
  `code PK (text)`, `name`, `enabled bool`, `rtl bool default false`, `created_at`, `updated_at`

- `i18n_keys`\
  `id PK`, `namespace text`, `key text`, `description text`, `created_by`, `created_at`, `updated_at`, `UNIQUE(namespace, key)`

- `i18n_entries`\
  `id PK`, `key_id FK -> i18n_keys.id`, `lang text FK -> i18n_locales.code`,\
  `value text`, `status enum('draft','reviewed','approved')`,\
  `source enum('machine','human')`, `version int default 1`,\
  `updated_by`, `updated_at`, `UNIQUE(key_id, lang)`

- `i18n_jobs` (batch ops)\
  `id PK`, `job_type text` (e.g., `batch_translate_missing`), `lang text`,\
  `payload jsonb`, `status enum('queued','running','done','failed')`,\
  `progress int`, `created_by`, `created_at`, `updated_at`, `error text`

- `i18n_audit`\
  `id PK`, `key_id`, `lang`, `old_value`, `new_value`, `old_status`, `new_status`,\
  `actor`, `at`, `note`

*(Optional)* `i18n_tm_segments` for Translation Memory:

- `src_lang`, `src_text_hash`, `src_text`, `tgt_lang`, `tgt_text`, `uses int`, `last_used_at`

### 3.2 SQL — Postgres `CREATE TABLE`

```sql
-- locales
CREATE TABLE IF NOT EXISTS i18n_locales (
  code        TEXT PRIMARY KEY,
  name        TEXT NOT NULL,
  enabled     BOOLEAN NOT NULL DEFAULT FALSE,
  rtl         BOOLEAN NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- keys
CREATE TABLE IF NOT EXISTS i18n_keys (
  id          BIGSERIAL PRIMARY KEY,
  namespace   TEXT NOT NULL,
  key         TEXT NOT NULL,
  description TEXT,
  created_by  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT i18n_keys_unique UNIQUE(namespace, key)
);
CREATE INDEX IF NOT EXISTS idx_i18n_keys_ns ON i18n_keys(namespace);

-- entries (per language value)
CREATE TYPE i18n_entry_status AS ENUM('draft','reviewed','approved');
CREATE TYPE i18n_entry_source AS ENUM('machine','human');

CREATE TABLE IF NOT EXISTS i18n_entries (
  id          BIGSERIAL PRIMARY KEY,
  key_id      BIGINT NOT NULL REFERENCES i18n_keys(id) ON DELETE CASCADE,
  lang        TEXT NOT NULL REFERENCES i18n_locales(code) ON DELETE CASCADE,
  value       TEXT NOT NULL,
  status      i18n_entry_status NOT NULL DEFAULT 'draft',
  source      i18n_entry_source NOT NULL DEFAULT 'machine',
  version     INT NOT NULL DEFAULT 1,
  updated_by  TEXT,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT i18n_entries_unique UNIQUE(key_id, lang)
);
CREATE INDEX IF NOT EXISTS idx_i18n_entries_key_lang ON i18n_entries(key_id, lang);
CREATE INDEX IF NOT EXISTS idx_i18n_entries_status ON i18n_entries(status);

-- jobs (batch operations)
CREATE TYPE i18n_job_status AS ENUM('queued','running','done','failed');

CREATE TABLE IF NOT EXISTS i18n_jobs (
  id          BIGSERIAL PRIMARY KEY,
  job_type    TEXT NOT NULL, -- e.g., batch_translate_missing
  lang        TEXT NOT NULL REFERENCES i18n_locales(code) ON DELETE CASCADE,
  payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
  status      i18n_job_status NOT NULL DEFAULT 'queued',
  progress    INT NOT NULL DEFAULT 0,
  created_by  TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_i18n_jobs_status ON i18n_jobs(status);

-- audit
CREATE TABLE IF NOT EXISTS i18n_audit (
  id          BIGSERIAL PRIMARY KEY,
  key_id      BIGINT NOT NULL REFERENCES i18n_keys(id) ON DELETE CASCADE,
  lang        TEXT NOT NULL,
  old_value   TEXT,
  new_value   TEXT,
  old_status  i18n_entry_status,
  new_status  i18n_entry_status,
  actor       TEXT,
  at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_i18n_audit_key_lang ON i18n_audit(key_id, lang);

-- optional translation memory
CREATE TABLE IF NOT EXISTS i18n_tm_segments (
  id            BIGSERIAL PRIMARY KEY,
  src_lang      TEXT NOT NULL,
  src_text_hash TEXT NOT NULL,
  src_text      TEXT NOT NULL,
  tgt_lang      TEXT NOT NULL,
  tgt_text      TEXT NOT NULL,
  uses          INT NOT NULL DEFAULT 0,
  last_used_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_tm_src ON i18n_tm_segments(src_lang, src_text_hash);
CREATE INDEX IF NOT EXISTS idx_tm_tgt ON i18n_tm_segments(tgt_lang);
```

---

## 4) File/Bundle Format delivered to the frontend

- API serves per-namespace JSON bundles:
  ```http
  GET /api/i18n/:lang?ns=layout,post_editor
  → {
    "layout": { "btn.submit": "Senden", ... },
    "post_editor": { "label.title": "Titel", ... }
  }
  ```
- Include `ETag` + `Cache-Control`; client caches by `lang+ns` with version pinning.
- Fallback chain: `requested_lang → en`.

---

## 5) Admin UI — “Key View” (Wireframe)

```
+-------------------------------------------------------------------------------------+
| Admin › Translations                                                                  |
| Filters: [namespace ▼] [lang ▼] [status ▼] [☑ missing only]      (Search: 🔎_____)   |
| Toolbar: [Add Language] [Batch Translate Missing] [Export] [Import]                  |
+-------------------------------------------------------------------------------------+
| Namespace | Key           | English (en)     | de                | fr                |
|-----------+---------------+------------------+-------------------+-------------------|
| layout    | btn.submit    | Submit           | Senden [draft]    | Envoyer [approved]|
| layout    | toast.saved   | Saved            | (missing) [Add➕]  | Enregistré [rev.] |
| editor    | label.title   | Title            | Titel [approved]  | Titre [approved]  |
+-------------------------------------------------------------------------------------+
| Row actions per cell: [Edit] [AI Generate] [Approve] [History]                       |
+-------------------------------------------------------------------------------------+
```

**Cell Panel (right drawer):**

- English (readonly)
- Target lang textarea
- Buttons: **AI Generate**, **Save Draft**, **Approve**, **History**
- Badges: Status, Source, Version

**Batch Dialog (Add Language):**

- Select language (code+name)
- Toggle **Enable language**
- Option: **Batch Translate Missing now**
- Scope: All namespaces / Selected namespaces
- Options: **Dry-run**, Max concurrency, Stop-on-error

---

## 6) Adding a New Language (Batch Flow)

1. **Admin → Locales → “Add Language”** (e.g., `pl` = Polish). Sets `enabled=true`.
2. Prompt to **Batch Translate Missing**:
   - Scope selection: all namespaces or selected.
   - Options:
     - **Dry-run** (estimate token cost + #keys)
     - Max concurrency (rate-limit)
     - Stop on error vs. continue
     - Minimum confidence (if model returns score)
3. Create `i18n_jobs` row; background worker:
   - For each missing `(key, pl)`:
     - Source = English `value`
     - Call OpenWebUI → write `i18n_entries.value`, `status='draft'`, `source='machine'`
     - Update `progress`
4. Admin reviews **Key View → lang=pl, filter: draft**:
   - Edit where needed, click **Approve** when OK.
5. Frontend starts requesting `pl` bundles after rollout toggled.

---

## 7) OpenWebUI Integration (generic, model-agnostic)

[... existing content ...]

---

## 23) Optional: CLI Seeds & Maintenance Snippets

[... existing content ...]

---

## 24) Approval Queue UI (Per‑Language Drafts Review)

A focused view for reviewers to process machine‑translated drafts efficiently.

**Route:** `/admin/i18n/queue/:lang`

**Header:**

- Language picker
- Counters: `Draft`, `Reviewed`, `Approved`, `Missing`
- Controls: `[Prev]  [Next]  [Approve ✓]  [Reject ↺ to Draft]  [Skip]  [Save]`
- Bulk controls: `[Approve All on Page]  [Send Back All to Draft]`

**Layout (two‑pane):**

```
+-------------------------------+----------------------------------------------+
| Left: Queue List              | Right: Detail                                 |
|-------------------------------+----------------------------------------------|
| Filters: [ns] [search]        | EN (read‑only)                                |
|                               | -------------------------------------------- |
| • layout.btn.submit  DRAFT    | Target (editable textarea)                    |
| • layout.toast.saved  DRAFT   |  - Status chips: draft/reviewed/approved      |
| • editor.label.title  REVIEW  |  - Source chip: machine/human                 |
| ...                           |  - Badges: ICU ok ✓ / Placeholders ok ✓       |
|                               |  - Actions: AI Regenerate • Copy EN           |
+-------------------------------+----------------------------------------------+
```

**Keyboard shortcuts:** `A` Approve, `R` Back to Draft, `S` Save, `J/K` Next/Prev, `G` AI Regenerate

**Workflow:**

1. Select item → validators run → badges (ICU/placeholder/HTML) show.
2. If invalid, block **Approve** and list fixes with deep‑links to the problem span.
3. On **Approve**, write audit row and auto‑advance to the next queued key.

**Pagination:** server‑side `?status=draft&ns=layout&limit=50&cursor=…`

**API:**

- `GET /api/admin/i18n/queue?lang=de&status=draft&ns=layout&cursor=…`
- `PUT /api/admin/i18n/entry/:id` (value/status)
- `POST /api/admin/i18n/entry/:id/ai-generate?lang=de`

---

## 25) Validator Cheatsheet (Placeholders, ICU, Basic HTML)

Use these checks before allowing **Approve**.

### 25.1 Placeholders

- **Curly placeholders (simple):** `{name}`, `{count}`
  - **Extract (JS regex):** `\{[A-Za-z0-9_.]+\}`
  - Compare **sets** EN vs target; must match exactly.
- **Mustache style:** `{{variable}}`
  - **Extract:** `\{\{\s*[A-Za-z0-9_.]+\s*\}\}`

**Block if:** placeholder names translated or punctuation added inside `{}`.

### 25.2 ICU MessageFormat (plural/select)

- **Detect plural:** `\{\s*([A-Za-z0-9_.]+)\s*,\s*plural\s*,`
- **Detect select:** `\{\s*([A-Za-z0-9_.]+)\s*,\s*select\s*,`
- **Brace balance:** counts of `{` and `}` must match after removing escaped braces.
- **Categories:** if EN has `one`/`other`, target must too.

**Structural check (pseudo):**

```
if !sameICUSkeleton(en, tgt): error("ICU structure mismatch")
if !balancedBraces(tgt):     error("Unbalanced braces")
if missingCategories:        error("Missing ICU category")
```

### 25.3 Basic HTML tags inside strings

- Allowlist: `b i strong em code br span`
- Verify tags preserved & closed; no new disallowed tags.
- **Extract tags (JS regex):** `</?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>`
- Compare **multiset of tag names** EN vs target.

### 25.4 Whitespace & Quotes

- Trim edges; strip surrounding quotes only if EN has none.
- Collapse newlines if EN is single‑line.

### 25.5 Aggregate pre‑approve

```
placeholdersMatch(en,tgt) &&
( !hasICU(en) || icuValid(en,tgt) ) &&
htmlAllowedAndSameTags(en,tgt) &&
lengthOK(en,tgt)
```

### 25.6 Handy Regex Snippets

- **All placeholders (either style):** `\{\{[^}]+\}\}|\{[^}]+\}`
- **ICU options:** `\b(one|other|few|many|zero|two)\s*\{`
- **Curly count (JS):** `(tgt.match(/\{/g)||[]).length === (tgt.match(/\}/g)||[]).length`

---

## 26) Reviewer Aids & Quality Controls

- Side‑by‑side diff (token‑level) to spot placeholder drift.
- Glossary lock: highlight violations (e.g., “Submit”→“Senden”).
- Length hint: EN vs target ratio.
- Language hints: e.g., French NBSP before `: ; ! ?`.
- Casing rules per language (e.g., German nouns capitalized).

**Auto‑fixes (optional):** restore placeholders, fix common ICU typos, re‑apply allowlisted tags from EN.

---

## 27) Minimal Unit Tests (Pseudo)

```
TEST placeholders_match:
  en = "Hello {name}!"
  de_ok = "Hallo {name}!"
  de_bad = "Hallo {Name}!"
  assert placeholders(en) == placeholders(de_ok)
  assert placeholders(en) != placeholders(de_bad)

TEST icu_plural_structure:
  en = "{count, plural, one {# item} other {# items}}"
  fr_ok = "{count, plural, one {# article} other {# articles}}"
  fr_bad = "{compte, plural, one {# article} other {# articles}}"  # var name changed
  assert icuSkeleton(en) == icuSkeleton(fr_ok)
  assert icuSkeleton(en) != icuSkeleton(fr_bad)

TEST html_tags_preserved:
  en = "Click <b>Save</b>"
  es_ok = "Haz clic en <b>Guardar</b>"
  es_bad = "Haz clic en <strong>Guardar</strong>"
  assert tags(en) == tags(es_ok)
  assert tags(en) != tags(es_bad)
```



---

## 28) API Queue Response Example

Example payload for `/api/admin/i18n/queue?lang=de&status=draft&ns=layout&limit=2&cursor=...`

```json
{
  "cursor": "eyJpZCI6MTIzfQ==",
  "items": [
    {
      "entry_id": 501,
      "namespace": "layout",
      "key": "btn.submit",
      "lang": "de",
      "en_value": "Submit",
      "value": "Senden",
      "status": "draft",
      "source": "machine",
      "description": "Primary submit button label",
      "updated_at": "2025-09-21T08:12:00Z"
    },
    {
      "entry_id": 502,
      "namespace": "layout",
      "key": "toast.saved",
      "lang": "de",
      "en_value": "Saved",
      "value": null,
      "status": null,
      "source": null,
      "description": "Short toast after successful save",
      "updated_at": null
    }
  ]
}
```

---

## 29) Frontend Fetch + Pagination Snippet

Minimal example (JS/TS) for consuming the queue API with cursor‑based pagination.

```ts
async function fetchQueue(lang: string, status = 'draft', ns = 'layout', cursor?: string) {
  const params = new URLSearchParams({ lang, status, ns, limit: '50' });
  if (cursor) params.set('cursor', cursor);

  const res = await fetch(`/api/admin/i18n/queue?${params.toString()}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function reviewLoop(lang: string) {
  let cursor: string | undefined;
  while (true) {
    const page = await fetchQueue(lang, 'draft', 'layout', cursor);
    for (const item of page.items) {
      renderQueueItem(item);
    }
    if (!page.cursor) break;
    cursor = page.cursor;
  }
}

function renderQueueItem(item) {
  console.log(`${item.namespace}.${item.key} → EN:"${item.en_value}" DE:"${item.value}"`);
}
```

---



---

## 28) Queue API — Example Response

**GET** `/api/admin/i18n/queue?lang=de&status=draft&ns=layout&limit=2&cursor=eyJpZCI6MTIzfQ`\
**200 OK**

```json
{
  "lang": "de",
  "status": "draft",
  "namespace": "layout",
  "items": [
    {
      "entry_id": 981,
      "key_id": 42,
      "namespace": "layout",
      "key": "btn.submit",
      "en_value": "Submit",
      "tgt_value": null,
      "has_icu": false,
      "placeholders": [],
      "updated_at": "2025-09-21T08:40:00Z"
    },
    {
      "entry_id": 982,
      "key_id": 43,
      "namespace": "layout",
      "key": "toast.saved",
      "en_value": "Saved",
      "tgt_value": "Gespeichert",
      "has_icu": false,
      "placeholders": [],
      "updated_at": "2025-09-21T08:41:00Z"
    }
  ],
  "next_cursor": "eyJpZCI6MTI2fQ",
  "total": 217
}
```

**Notes**

- `cursor` is an opaque token (server generated). If `next_cursor` is null, you reached the end.
- Server should also accept `ns=ns1,ns2` (comma separated) to filter multiple namespaces.

---

## 29) Frontend Fetch + Pagination (TypeScript)

A simple hook-like helper to page through the queue. Framework agnostic.

```ts
export type QueueItem = {
  entry_id: number;
  key_id: number;
  namespace: string;
  key: string;
  en_value: string;
  tgt_value: string | null;
  has_icu: boolean;
  placeholders: string[];
  updated_at: string;
};

export type QueuePage = {
  lang: string;
  status: 'draft' | 'reviewed' | 'approved';
  namespace?: string;
  items: QueueItem[];
  next_cursor: string | null;
  total: number;
};

async function fetchQueue(params: {
  lang: string;
  status?: 'draft' | 'reviewed' | 'approved';
  ns?: string;             // e.g. 'layout,editor'
  limit?: number;          // e.g. 50
  cursor?: string | null;  // opaque
}): Promise<QueuePage> {
  const q = new URLSearchParams();
  q.set('lang', params.lang);
  if (params.status) q.set('status', params.status);
  if (params.ns) q.set('ns', params.ns);
  if (params.limit) q.set('limit', String(params.limit));
  if (params.cursor) q.set('cursor', params.cursor);

  const res = await fetch(`/api/admin/i18n/queue?${q.toString()}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function* queueIterator(opts: {
  lang: string;
  status?: 'draft' | 'reviewed' | 'approved';
  ns?: string;
  limit?: number;
}) {
  let cursor: string | null = null;
  do {
    const page = await fetchQueue({ ...opts, cursor });
    yield page;
    cursor = page.next_cursor;
  } while (cursor);
}

// Example usage in a component
// for await (const page of queueIterator({ lang: 'de', status: 'draft', ns: 'layout', limit: 50 })) {
//   render(page.items);
// }
```

**UI idea**

- Keep a sticky pager with Prev/Next, show `items.length` and a small progress bar based on `total`.
- Disable Approve when validators fail; show inline errors and a quick-fix menu.



---

## 30) Approve Flow — PUT Example

**Endpoint:** `PUT /api/admin/i18n/entry/:id`

**Request**

```json
{
  "value": "Senden",
  "status": "approved",
  "updated_by": "admin"
}
```

**Response**

```json
{
  "entry_id": 981,
  "key_id": 42,
  "lang": "de",
  "value": "Senden",
  "status": "approved",
  "source": "human",
  "version": 2,
  "updated_by": "admin",
  "updated_at": "2025-09-21T09:45:00Z"
}
```

**Notes**

- Server should increment `version` on each update.
- Write an audit record (old\_value, new\_value, old\_status, new\_status).
- Reject update if `placeholders`/ICU validation fails.

---

## 31) AI Regenerate Action — Handler

**Endpoint:** `POST /api/admin/i18n/entry/:id/ai-generate?lang=de`

**Flow**

1. Lookup EN source from DB (`i18n_entries` with `lang='en'`).
2. Send prompt to OpenWebUI client with namespace/key/description.
3. Run validators (placeholders, ICU, HTML).
4. If valid → update entry with `status='draft'`, `source='machine'`.
5. Respond with updated entry.

**Example Request**

```http
POST /api/admin/i18n/entry/981/ai-generate?lang=de
```

**Response**

```json
{
  "entry_id": 981,
  "key_id": 42,
  "lang": "de",
  "value": "Absenden",
  "status": "draft",
  "source": "machine",
  "version": 3,
  "updated_by": "worker",
  "updated_at": "2025-09-21T09:46:12Z"
}
```

**Frontend Hook (TS)**

```ts
async function regenerate(entryId: number, lang: string) {
  const res = await fetch(`/api/admin/i18n/entry/${entryId}/ai-generate?lang=${lang}`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
```

**UI idea:** Add a small “AI ↻” button next to each draft cell that triggers this call, shows a spinner, and replaces the value on success.



---

## 30) Approve Flow — `PUT /api/admin/i18n/entry/:id`

**Goal:** Save an edited value and mark it approved (after validators pass).

**Request**

```
PUT /api/admin/i18n/entry/981
Content-Type: application/json

{
  "value": "Senden",
  "status": "approved",
  "notes": "Reviewed by moderator"
}
```

**Response**

```
200 OK
{
  "entry_id": 981,
  "lang": "de",
  "status": "approved",
  "version": 2,
  "updated_at": "2025-09-21T08:55:00Z"
}
```

**Server steps (pseudo):**

```
1) authz: require role ∈ {admin, moderator}
2) fetch entry+source EN text and key meta
3) run validators (placeholders, ICU, HTML)
4) if invalid → 422 with error list
5) UPDATE i18n_entries
     SET value=$value, status='approved', source='human',
         version=version+1, updated_by=$actor, updated_at=now()
     WHERE id=$entry_id
6) INSERT i18n_audit (old_value, new_value, old_status, new_status, actor, note)
7) respond 200 with new version
```

**SQL sketch**

```sql
WITH prev AS (
  SELECT id, value AS old_value, status AS old_status
  FROM i18n_entries WHERE id = $1 FOR UPDATE
), upd AS (
  UPDATE i18n_entries
     SET value = $2,
         status = 'approved',
         source = 'human',
         version = version + 1,
         updated_by = $3,
         updated_at = now()
   WHERE id = (SELECT id FROM prev)
   RETURNING id, key_id, lang, version, updated_at
)
INSERT INTO i18n_audit (key_id, lang, old_value, new_value, old_status, new_status, actor, note)
SELECT u.key_id, u.lang, p.old_value, $2, p.old_status, 'approved', $3, $4
FROM upd u JOIN prev p ON p.id = u.id;
```

---

## 31) AI Regenerate — `POST /api/admin/i18n/entry/:id/ai-generate?lang=XX`

**Goal:** Re-run MT for a single key into target `lang`, store as `draft/machine`.

**Frontend handler (TS)**

```ts
export async function aiRegenerate(entryId: number, lang: string) {
  const res = await fetch(`/api/admin/i18n/entry/${entryId}/ai-generate?lang=${encodeURIComponent(lang)}`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data; // { entry_id, lang, value, status: 'draft' }
}
```

**Backend route (pseudo, Python-ish)**

```
@post('/api/admin/i18n/entry/:id/ai-generate')
require_role(editor|moderator|admin)
  entry = db.getEntry(params.id)
  key   = db.getKey(entry.key_id)
  en    = db.getEntryByKeyLang(key.id, 'en')

  text  = openwebui.translate(
            english_text=en.value,
            target_lang=query.lang,
            namespace=key.namespace,
            key=key.key,
            notes=key.description or ''
          )
  out   = sanitize(text, en.value)
  if !out.valid: return 422 { errors: out.errors }

  db.upsertEntry(
    key_id=key.id,
    lang=query.lang,
    value=out.value,
    status='draft',
    source='machine',
    updated_by=actor
  )
  return 200 { entry_id: entry.id, lang: query.lang, value: out.value, status: 'draft' }
```

**Notes**

- Keep temperature low (0–0.2) for determinism.
- Respect rate limits; backoff on 429/5xx.
- Consider idempotency key: `Idempotency-Key: ai-regenerate:{entry_id}:{lang}:{en_hash}` to avoid duplicate MT writes.



---

## 32) Error Payload Schemas & Rate Limits

### 32.1 Standard Errors

- **401 Unauthorized** — not logged in

```json
{
  "error": "unauthorized",
  "message": "You must log in."
}
```

- **403 Forbidden** — lacks role

```json
{
  "error": "forbidden",
  "message": "Insufficient permissions."
}
```

- **404 Not Found** — invalid key/entry id

```json
{
  "error": "not_found",
  "message": "Entry not found."
}
```

- **422 Validation Failed** — placeholder/ICU/HTML mismatch

```json
{
  "error": "validation_failed",
  "issues": [
    { "type": "placeholders", "message": "Missing {count} in target" },
    { "type": "icu", "message": "ICU category 'other' missing" }
  ]
}
```

- **429 Too Many Requests** — exceeded rate limit

```json
{
  "error": "rate_limited",
  "retry_after": 15,
  "message": "Too many AI requests. Retry after 15 seconds."
}
```

- **500 Internal Server Error**

```json
{
  "error": "internal",
  "message": "Unexpected error. Contact admin."
}
```

### 32.2 Response Headers

- `RateLimit-Limit: 100` — max calls per minute (per user or per IP)
- `RateLimit-Remaining: 78`
- `RateLimit-Reset: 30` — seconds until reset

### 32.3 Idempotency

For mutation endpoints (`PUT /entry/:id`, `POST /ai-generate`), allow client to send:

```
Idempotency-Key: ai-regenerate:981:de:hash123
```

- Server stores last response keyed by `(user, Idempotency-Key)` for 24h.
- If same key arrives again → return cached response instead of re‑running.

---



---

## 32) Error Payload Schemas

Standardize admin API error bodies for predictable handling in the UI.

### 32.1 401 / 403 — Auth

```json
{
  "error": {
    "type": "auth",
    "code": 401,
    "message": "Unauthorized"
  }
}
```

### 32.2 404 — Not Found

```json
{
  "error": {
    "type": "not_found",
    "code": 404,
    "resource": "i18n_entry",
    "id": 981
  }
}
```

### 32.3 409 — Conflict (Concurrent Update)

```json
{
  "error": {
    "type": "conflict",
    "code": 409,
    "message": "Version mismatch",
    "expected_version": 2,
    "actual_version": 3
  }
}
```

### 32.4 422 — Validation Errors (Aggregated)

```json
{
  "error": {
    "type": "validation",
    "code": 422,
    "message": "Validation failed",
    "details": [
      { "field": "value", "rule": "placeholders", "message": "Missing {name}" },
      { "field": "value", "rule": "icu", "message": "ICU category 'other' missing" },
      { "field": "value", "rule": "html", "message": "Unexpected tag <strong>" }
    ]
  }
}
```

**Notes**

- Keep `details` stable so the UI can map rules → help text.
- For batch jobs, return a `job_id` even if some items are invalid, and mark them per‑item in job results.

---

## 33) Rate Limiting & Headers

Apply consistent headers for both admin and public i18n endpoints.

**Response headers**

```
RateLimit-Limit: 120      # max requests in window
RateLimit-Remaining: 117
RateLimit-Reset: 28       # seconds till reset
Retry-After: 30           # only on 429/503
ETag: "W/\"lang=de;ns=layout;v=7\""   # for bundle endpoints
Cache-Control: public, max-age=300
```

**Behavior**

- On **429 Too Many Requests**, include `Retry-After` and a JSON body:

```json
{ "error": { "type": "rate_limit", "code": 429, "message": "Slow down" } }
```

- Bundle endpoints (`GET /api/i18n/:lang`) must support `If-None-Match` with `ETag`.

---

## 34) Idempotency — Singles & Batch Jobs

Prevent duplicate writes from retries or double‑clicks.

### 34.1 Singles (approve / ai‑regenerate)

- Accept `Idempotency-Key` header.
- Store a short‑lived key → response cache keyed by `(user, method, path, idempotency_key)` for \~10 minutes.
- On duplicate request with same key, return cached 200/422 body.

**Example**

```
Idempotency-Key: ai-regenerate:entry=981:lang=de:enhash=ab12cd
```

### 34.2 Batch Jobs

- Compute a stable `job_dedup_key` from `(job_type, lang, namespaces_sorted, en_version_hash)`.
- If a queued/running job with same key exists, return that job instead of creating a new one.
- Expose in response:

```json
{ "job_id": 1234, "dedup": true }
```

---

## 35) Small UI/UX Touches

- Surface `RateLimit-Remaining` in admin footer to explain slowdowns.
- Disable buttons during in‑flight requests; show spinner + idempotency note on hover.
- On 409 conflict, fetch latest entry and open a 3‑way merge modal (yours vs current vs EN).

