import { setLanguage } from '/src/frontend/js/i18n-runtime.js';

const STORAGE_KEY = 'ui_lang';
const LANGUAGE_OPTIONS = [
  { code: 'bg', label: 'Български (Bulgarian)', key: 'landing.lang_option_bg' },
  { code: 'hr', label: 'Hrvatski (Croatian)', key: 'landing.lang_option_hr' },
  { code: 'cs', label: 'Čeština (Czech)', key: 'landing.lang_option_cs' },
  { code: 'da', label: 'Dansk (Danish)', key: 'landing.lang_option_da' },
  { code: 'nl', label: 'Nederlands (Dutch)', key: 'landing.lang_option_nl' },
  { code: 'en', label: 'English', key: 'landing.lang_option_en' },
  { code: 'et', label: 'Eesti (Estonian)', key: 'landing.lang_option_et' },
  { code: 'fi', label: 'Suomi (Finnish)', key: 'landing.lang_option_fi' },
  { code: 'fr', label: 'Français (French)', key: 'landing.lang_option_fr' },
  { code: 'de', label: 'Deutsch (German)', key: 'landing.lang_option_de' },
  { code: 'el', label: 'Ελληνικά (Greek)', key: 'landing.lang_option_el' },
  { code: 'hu', label: 'Magyar (Hungarian)', key: 'landing.lang_option_hu' },
  { code: 'ga', label: 'Gaeilge (Irish)', key: 'landing.lang_option_ga' },
  { code: 'it', label: 'Italiano (Italian)', key: 'landing.lang_option_it' },
  { code: 'lv', label: 'Latviešu (Latvian)', key: 'landing.lang_option_lv' },
  { code: 'lt', label: 'Lietuvių (Lithuanian)', key: 'landing.lang_option_lt' },
  { code: 'mt', label: 'Malti (Maltese)', key: 'landing.lang_option_mt' },
  { code: 'pl', label: 'Polski (Polish)', key: 'landing.lang_option_pl' },
  { code: 'pt', label: 'Português (Portuguese)', key: 'landing.lang_option_pt' },
  { code: 'ro', label: 'Română (Romanian)', key: 'landing.lang_option_ro' },
  { code: 'sk', label: 'Slovenčina (Slovak)', key: 'landing.lang_option_sk' },
  { code: 'sl', label: 'Slovenščina (Slovenian)', key: 'landing.lang_option_sl' },
  { code: 'es', label: 'Español (Spanish)', key: 'landing.lang_option_es' },
  { code: 'sv', label: 'Svenska (Swedish)', key: 'landing.lang_option_sv' },
];

function detectBrowserLang(){
  try {
    const supported = new Set(LANGUAGE_OPTIONS.map(({ code }) => code));
    const prefs = Array.isArray(navigator.languages) && navigator.languages.length
      ? navigator.languages
      : (navigator.language ? [navigator.language] : []);
    for (const pref of prefs){
      if (!pref) continue;
      const normalized = pref.toLowerCase().split('-')[0];
      if (supported.has(normalized)) return normalized;
    }
  } catch {}
  return null;
}

export function getSavedLang(){
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return stored;
    const docLang = document.documentElement.lang;
    if (docLang) return docLang;
    const detected = detectBrowserLang();
    if (detected) return detected;
  } catch {}
  return 'en';
}

export async function initLanguageSwitcher(selectEl){
  if(!selectEl) return;
  const current = getSavedLang();
  // Populate if empty
  if(!selectEl.options.length){
    const autoOption = document.createElement('option');
    autoOption.value = '';
    autoOption.textContent = 'Auto (browser default)';
    autoOption.dataset.i18n = 'landing.lang_auto';
    selectEl.appendChild(autoOption);
    for (const { code, label, key } of LANGUAGE_OPTIONS){
      const opt = document.createElement('option');
      opt.value = code;
      opt.textContent = label;
      if (key) opt.dataset.i18n = key;
      selectEl.appendChild(opt);
    }
  }
  if (LANGUAGE_OPTIONS.some(({ code }) => code === current)) {
    selectEl.value = current;
  } else {
    selectEl.value = '';
  }
  await setLanguage(current);
  selectEl.addEventListener('change', async () => {
    let lang = selectEl.value;
    if (!lang){
      try { localStorage.removeItem(STORAGE_KEY); } catch {}
      lang = detectBrowserLang() || 'en';
    } else {
      try { localStorage.setItem(STORAGE_KEY, lang); } catch {}
    }
    await setLanguage(lang);
    try { document.documentElement.setAttribute('lang', lang); } catch {}
  });
}
