# Internationalization (i18n) — Concept (Windsurf Ready)

A lightweight, developer-friendly system for handling UI translations, defined conceptually here without code. It relies on marking translatable elements with `data-i18n` attributes, managing language keys in JSON files, and supporting batch translation of new languages through OpenWebUI (Ollama). All implementation details are documented separately in [i18n_code_snippets.md](i18n_code_snippets.md).

---

## Core Goals
- **Zero-friction adoption**: simply add `data-i18n` attributes to existing UI elements.
- **Single source of truth**: maintain one JSON file per locale, with English (`en`) as the root.
- **Resilient UX**: fall back to English for missing keys; highlight gaps in development mode.
- **Self-service admin UI**: allow administrators to add languages, import keys from English, and run batch translations.
- **Windsurf compatibility**: provide a clear structure and defined steps for rapid implementation.

---

## Project Structure (Conceptual)
- `/i18n/` — locale files (e.g., `en.json`, `de.json`, `fr.json`).
- `/admin/` — translation management UI (HTML, JS, CSS).
- `/scripts/` — developer utilities (scanner, validator).
- `/static/js/` — runtime i18n loader.

> Implementation details and working code are in [i18n_code_snippets.md](i18n_code_snippets.md).

---

## Language Key Strategy
- **Naming convention**: use clear, structured keys like `section.element.purpose` (e.g., `nav.login`, `form.signup.email_label`). This prevents ambiguity and avoids breaking translations when UI text changes.
- **Stable intent**: define keys by purpose rather than literal wording so they remain consistent across redesigns.
- **Pluralization**: allow variants such as `users.count.zero|one|other` to handle different grammatical forms.
- **Interpolation**: support placeholders like `{name}` or `{count}` so translators can preserve dynamic values without confusion.

**Example Starter Keys**
- Navigation: `nav.home`, `nav.login`, `nav.logout`, `nav.settings`
- Footer: `footer.imprint`, `footer.privacy`
- Forms: `form.submit`, `form.cancel`, `form.save`, `form.search`, `form.email`, `form.password`
- Authentication: `form.login.title`, `form.login.cta`, `form.signup.title`, `form.signup.cta`
- Notifications: `toast.saved`, `toast.error`
- Confirmation: `confirm.delete.title`, `confirm.delete.body`, `confirm.delete.confirm`, `confirm.delete.cancel`

---

## Markup Conventions
- **Visible text**: `data-i18n="key"`
- **Placeholders**: `data-i18n-placeholder="key"`
- **Titles/tooltips**: `data-i18n-title="key"`
- **Accessibility labels**: `data-i18n-aria-label="key"`
- **Parameters**: `data-i18n-params` with JSON (e.g., `{ "name": "Alice" }`).
- **Development aid**: optional `i18n` CSS class for styling or highlighting.

---

## Runtime Responsibilities
- Load the active locale file with English as fallback.
- Apply translations to DOM elements with `data-i18n*` attributes.
- Handle interpolation and simple plural logic.
- Expose functions to switch languages and refresh the UI dynamically.

> Full runtime implementation is documented in [i18n_code_snippets.md](i18n_code_snippets.md).

---

## Admin UI (Conceptual)
### Views
1. **Languages** — list available locales, set default/active, add new.
2. **Keys** — show all keys and values, allow inline editing, filter missing or unused, import from English.
3. **Batch Translation** — pick target locale, source (English), and model; translate only missing keys.
4. **API Settings** — configure OpenWebUI URL and API key; test connection.

### User Flows
- **Add Language** — enter locale code (e.g., `de`, `fr-CA`), create a JSON file with English keys, and optionally run batch translation.
- **Batch Translate** — translate missing keys only, keep placeholders `{...}`, and return plain text.

---

## OpenWebUI (Ollama) Integration

The project already uses a working OpenWebUI ↔ Ollama API connection, so integration can rely on that existing setup.

- **Configuration**: store base URL and API key securely server-side.
- **Model**: default to a local model, with flexibility to adjust.
- **Behavior**: low temperature for consistent phrasing; retry logic on timeouts; validation for placeholders.

---

## Backend Endpoints (Conceptual)
- **List languages** — return available locales and default.
- **Create language** — clone English keys into a new locale file.
- **Read keys** — return key/value map for a locale.
- **Write key** — add or update a single translation.
- **Import keys** — copy any missing keys from English without overwriting.
- **Batch translate** — translate missing keys for a locale using OpenWebUI.

> Suggested implementation with FastAPI; details in [i18n_code_snippets.md](i18n_code_snippets.md).

---

## Developer Utilities
- **Scanner** — detect UI strings in templates, propose keys, bootstrap `en.json`.
- **Validator** — check for missing or unused keys; integrate into CI.

---

## Implementation Steps in Windsurf
1. Create `/i18n/en.json` using the starter key set.
2. Add the runtime loader and initialize with English.
3. Mark templates with `data-i18n*` attributes.
4. Build the admin UI for languages, keys, batch translation, and API settings.
5. Implement backend endpoints and OpenWebUI connection.
6. Run the scanner to collect initial keys.
7. Add the validator and enforce checks in CI.

---

## Edge Cases and Rules

### Technical Rules
- **Placeholders**: preserve placeholders (e.g., `{name}`) in all translations.
- **Pluralization**: start basic; plan for ICU later.
- **HTML in strings**: avoid if possible; otherwise allow only whitelisted tags.

### Broader Concerns
- **RTL support**: detect RTL locales (e.g., `ar`, `he`) and set `dir="rtl"` on `<html>`.
- **Fallback**: always default to English.
- **Versioning**: include metadata version in each locale for cache busting.

---

## Security and Privacy
- Keep API keys on the server; never expose in the client.
- Rate-limit batch translation requests.
- Log only counts and statuses, not full source strings, to protect privacy.

---

## Open Tasks
- Finalize interpolation style (recommend `{name}`).
- Choose default model and temperature per language.
- Add placeholder validation and a “lock” option for sensitive keys.
- Provide import/export (JSON) for translators.
- Add a developer mode indicator for missing keys.

---

**Cross‑reference**: Implementation and code examples are in [i18n_code_snippets.md](i18n_code_snippets.md).

