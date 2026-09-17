import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './en.json';
import de from './de.json';

/**
 * Centralised i18n setup. Translation strings live in `en.json` / `de.json`;
 * components only ever reference keys through `useTranslation()`.
 */

export const SUPPORTED_LANGUAGES = [
  // Endonyms — the dropdown shows the same two labels in either language.
  { code: 'en', label: 'English' },
  { code: 'de', label: 'Deutsch' },
] as const;

export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]['code'];

export const DEFAULT_LANGUAGE: LanguageCode = 'en';

/** Frontend-only persistence. No backend language storage in this phase. */
const STORAGE_KEY = 'cybrain-qs.language';

function isSupported(value: string | null): value is LanguageCode {
  return SUPPORTED_LANGUAGES.some((entry) => entry.code === value);
}

function readStoredLanguage(): LanguageCode {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isSupported(stored)) return stored;
  } catch {
    // localStorage can be unavailable (private mode, blocked cookies).
  }
  return DEFAULT_LANGUAGE;
}

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    de: { translation: de },
  },
  lng: readStoredLanguage(),
  fallbackLng: DEFAULT_LANGUAGE,
  interpolation: {
    // React already escapes rendered values.
    escapeValue: false,
  },
});

/** Keep the document language and the stored preference in sync. */
function applyLanguage(language: string) {
  document.documentElement.lang = language;
  try {
    localStorage.setItem(STORAGE_KEY, language);
  } catch {
    // Persistence is best-effort; the UI still switches without it.
  }
}

applyLanguage(i18n.language);
i18n.on('languageChanged', applyLanguage);

export default i18n;
