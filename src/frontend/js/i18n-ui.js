import { setLanguage } from '/src/frontend/js/i18n-runtime.js';

const STORAGE_KEY = 'ui_lang';
const LANGS = [
  ['en', 'English'],
  ['de', 'Deutsch'],
  ['fr', 'Français'],
  ['es', 'Español'],
];

export function getSavedLang(){
  try { return localStorage.getItem(STORAGE_KEY) || document.documentElement.lang || 'en'; } catch { return 'en'; }
}

export async function initLanguageSwitcher(selectEl){
  if(!selectEl) return;
  const current = getSavedLang();
  // Populate if empty
  if(!selectEl.options.length){
    for (const [val, label] of LANGS){
      const opt = document.createElement('option');
      opt.value = val; opt.textContent = label; selectEl.appendChild(opt);
    }
  }
  selectEl.value = current;
  await setLanguage(current);
  selectEl.addEventListener('change', async () => {
    const lang = selectEl.value || 'en';
    try { localStorage.setItem(STORAGE_KEY, lang); } catch {}
    await setLanguage(lang);
    // also reflect on <html lang>
    try { document.documentElement.setAttribute('lang', lang); } catch {}
  });
}
