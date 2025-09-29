# Internationalization (i18n) Code Snippets

This document collects the core stub implementations and admin UI entry points for the i18n system.

---

## Runtime Loader — `/static/js/i18n-runtime.js`
```javascript
/* i18n-runtime.js
   Minimal runtime loader and DOM applier for data-i18n attributes.
   Framework-agnostic and lightweight. */

let _dictActive = {};
let _dictFallback = {};
let _currentLang = 'en';
const _listeners = new Set();

function _notify() {
  for (const fn of _listeners) {
    try { fn(_currentLang); } catch {}
  }
}

export function onLanguageChanged(fn) {
  _listeners.add(fn);
  return () => _listeners.delete(fn);
}

export function getLanguage() {
  return _currentLang;
}

function _interpolate(str, params = {}) {
  return String(str).replace(/\{(\w+)\}/g, (_, k) => (params[k] ?? ''));
}

export function t(key, params = {}) {
  const raw = _dictActive[key] ?? _dictFallback[key] ?? key;
  return _interpolate(raw, params);
}

export function applyI18n(root = document) {
  root.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const params = el.dataset.i18nParams ? JSON.parse(el.dataset.i18nParams) : {};
    el.textContent = t(key, params);
  });

  root.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });

  root.querySelectorAll('[data-i18n-title]').forEach(el => {
    el.title = t(el.dataset.i18nTitle);
  });

  root.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
    el.setAttribute('aria-label', t(el.dataset.i18nAriaLabel));
  });
}

async function _safeFetchJSON(url) {
  try {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch {
    return {};
  }
}

export async function setLanguage(lang) {
  _currentLang = lang;
  const [active, fallback] = await Promise.all([
    _safeFetchJSON(`/i18n/${lang}.json`),
    _safeFetchJSON(`/i18n/en.json`)
  ]);
  _dictActive = active || {};
  _dictFallback = fallback || {};
  applyI18n(document);
  _notify();
}

export async function initI18n(defaultLang = 'en') {
  const mo = new MutationObserver(muts => {
    for (const m of muts) {
      m.addedNodes.forEach(node => {
        if (node.nodeType === 1) applyI18n(node);
      });
    }
  });
  mo.observe(document.documentElement, { childList: true, subtree: true });

  await setLanguage(defaultLang);
}

if (typeof window !== 'undefined') {
  const auto = document.currentScript?.dataset?.i18nInit;
  if (auto !== undefined) {
    initI18n(document.documentElement.lang || 'en');
  }
}
```

---

## Scanner Utility — `/scripts/i18n-scan.js`
```javascript
#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const CWD = process.cwd();

function parseArgs() {
  const args = process.argv.slice(2);
  const out = { root: './', en: './i18n/en.json', write: false };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--root') out.root = args[++i];
    else if (args[i] === '--en') out.en = args[++i];
    else if (args[i] === '--write') out.write = true;
  }
  return out;
}

function* walk(dir, exts = new Set(['.html', '.htm', '.js', '.jsx', '.ts', '.tsx'])) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const e of entries) {
    if (e.name.startsWith('.')) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) yield* walk(p, exts);
    else if (exts.has(path.extname(e.name))) yield p;
  }
}

function extractFromHTML(src) {
  const findings = [];
  src.replace(/<label[^>]*>([\s\S]*?)<\/label>/gi, (_, text) => {
    const v = cleanup(text);
    if (shouldKeep(v)) findings.push({ tag: 'label', text: v });
    return _;
  });
  src.replace(/<button[^>]*>([\s\S]*?)<\/button>/gi, (_, text) => {
    const v = cleanup(text);
    if (shouldKeep(v)) findings.push({ tag: 'button', text: v });
    return _;
  });
  src.replace(/<option[^>]*>([\s\S]*?)<\/option>/gi, (_, text) => {
    const v = cleanup(text);
    if (shouldKeep(v)) findings.push({ tag: 'option', text: v });
    return _;
  });
  src.replace(/\splaceholder=("([^"]+)"|'([^']+)')/gi, (_, __, dq, sq) => {
    const v = cleanup(dq ?? sq ?? '');
    if (shouldKeep(v)) findings.push({ attr: 'placeholder', text: v });
    return _;
  });
  src.replace(/\stitle=("([^"]+)"|'([^']+)')/gi, (_, __, dq, sq) => {
    const v = cleanup(dq ?? sq ?? '');
    if (shouldKeep(v)) findings.push({ attr: 'title', text: v });
    return _;
  });
  return findings;
}

function extractFromJS(src) {
  const findings = [];
  src.replace(/\b(toast\.(success|error|info)|alert|confirm)\(\s*("([^"]+)"|'([^']+)')/g, (_m, _fn, _t, _q, dq, sq) => {
    const v = cleanup(dq ?? sq ?? '');
    if (shouldKeep(v)) findings.push({ fn: 'call', text: v });
    return _m;
  });
  return findings;
}

function cleanup(s) {
  return s.replace(/\s+/g, ' ').replace(/&nbsp;/g, ' ').trim();
}

function shouldKeep(s) {
  if (!s) return false;
  if (s.length < 2) return false;
  if (/^[\{\[]/.test(s)) return false;
  if (/^\d+$/.test(s)) return false;
  if (/^\w{1,2}$/.test(s)) return false;
  if (/^\s*$/.test(s)) return false;
  return true;
}

function proposeKey(txt) {
  if (/email/i.test(txt)) return 'form.email';
  if (/password/i.test(txt)) return 'form.password';
  if (/login|sign in/i.test(txt)) return 'form.login.cta';
  if (/sign up|create account/i.test(txt)) return 'form.signup.cta';
  if (/save/i.test(txt)) return 'form.save';
  if (/cancel/i.test(txt)) return 'form.cancel';
  if (/delete/i.test(txt)) return 'confirm.delete.confirm';
  if (/search/i.test(txt)) return 'form.search';
  return 'misc.' + txt.toLowerCase().replace(/[^a-z0-9\s]/g, '').trim().split(/\s+/).slice(0, 5).join('_');
}

function main() {
  const { root, en, write } = parseArgs();
  const absRoot = path.resolve(CWD, root);
  const absEN = path.resolve(CWD, en);

  let enJSON = {};
  if (fs.existsSync(absEN)) {
    try { enJSON = JSON.parse(fs.readFileSync(absEN, 'utf8')); }
    catch { enJSON = {}; }
  }

  const candidates = new Map();
  for (const file of walk(absRoot)) {
    const src = fs.readFileSync(file, 'utf8');
    let findings = [];
    if (file.endsWith('.html') || file.endsWith('.htm')) findings = extractFromHTML(src);
    else findings = extractFromJS(src);
    for (const f of findings) {
      const key = proposeKey(f.text);
      if (!enJSON[key]) {
        if (!candidates.has(key)) candidates.set(key, f.text);
      }
    }
  }

  const added = {};
  for (const [k, v] of candidates.entries()) {
    enJSON[k] = enJSON[k] ?? v;
    added[k] = v;
  }

  if (write) {
    fs.mkdirSync(path.dirname(absEN), { recursive: true });
    fs.writeFileSync(absEN, JSON.stringify(enJSON, null, 2) + '\n', 'utf8');
    console.log(`i18n-scan: wrote ${Object.keys(added).length} keys to ${path.relative(CWD, absEN)}`);
  } else {
    console.log(JSON.stringify({ added, previewTarget: path.relative(CWD, absEN) }, null, 2));
  }
}

main();
```

---

## Admin Access Button

### HTML Example
```html
<a href="/admin/i18n.html" class="btn btn-ghost i18n" data-i18n="admin.i18n">
  i18n
</a>
```

### Translation Keys
```json
{
  "admin.i18n": "Translations",
  "admin.i18n.batch": "Batch translate",
  "admin.i18n.add_lang": "Add language",
  "admin.i18n.settings": "API settings"
}
```

### FastAPI Guard
```python
from fastapi import Depends, Request, HTTPException
from fastapi.responses import HTMLResponse

def require_admin(user=Depends(current_user)):
    if not user or user.role not in {"admin", "moderator"}:
        raise HTTPException(status_code=403)
    return user

@app.get("/admin/i18n.html", response_class=HTMLResponse)
async def i18n_admin_page(user=Depends(require_admin)):
    return templates.TemplateResponse("admin/i18n.html", {"request": Request})
```

### Client-Side Guard (SPA)
```js
if (!window.currentUser?.isAdmin) {
  document.querySelectorAll('a[href="/admin/i18n.html"]').forEach(el => el.remove());
}
```

---

## Starter Admin UI — `admin/i18n.html`
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title data-i18n="admin.i18n">Translations</title>
  <link rel="stylesheet" href="/static/css/admin.css">
  <script type="module" src="/static/js/i18n-runtime.js" data-i18n-init></script>
</head>
<body>
  <header>
    <h1 data-i18n="admin.i18n">Translations</h1>
  </header>

  <main>
    <section>
      <button id="addLangBtn" data-i18n="admin.i18n.add_lang">Add language</button>
      <button id="batchBtn" data-i18n="admin.i18n.batch">Batch translate</button>
    </section>

    <section id="langList">
      <!-- List of available languages will be populated here -->
    </section>

    <section id="keyTable">
      <!-- Table of translation keys/values -->
      <table>
        <thead>
          <tr>
            <th data-i18n="misc.key">Key</th>
            <th data-i18n="misc.value">Value</th>
          </tr>
        </thead>
        <tbody id="translationRows">
          <!-- Rows injected dynamically -->
        </tbody>
      </table>
    </section>
  </main>

  <script type="module">
    import { applyI18n } from '/static/js/i18n-runtime.js';

    document.getElementById('addLangBtn').addEventListener('click', () => {
      alert('TODO: Add new language');
    });

    document.getElementById('batchBtn').addEventListener('click', () => {
      alert('TODO: Trigger batch translation');
    });

    // Initial render
    applyI18n(document);
  </script>
</body>
</html>
```

---

## Summary
These snippets provide the foundation for internationalization in the project:
- A runtime loader to handle translations in the browser.
- A CLI scanner to extract candidate strings and propose keys.
- An admin entry point with server- and client-side guards.
- A starter HTML skeleton for the translation admin UI.

Together, these components enable developers and administrators to manage translations efficiently while keeping the workflow lightweight and developer-friendly.

