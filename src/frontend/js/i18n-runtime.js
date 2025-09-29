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
