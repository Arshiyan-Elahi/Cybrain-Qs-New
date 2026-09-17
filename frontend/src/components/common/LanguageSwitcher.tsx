import { useTranslation } from 'react-i18next';
import { Icon } from './Icon';
import { SUPPORTED_LANGUAGES } from '../../i18n';
import styles from './LanguageSwitcher.module.css';

/**
 * Global language selector. Rendered in the top row of every screen.
 *
 * Uses a native `<select>` so keyboard and screen-reader behaviour comes for
 * free; the chevron is drawn on top and the native arrow is suppressed to match
 * the design's control styling.
 */
export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();

  const current =
    SUPPORTED_LANGUAGES.find((entry) => entry.code === i18n.language) ?? SUPPORTED_LANGUAGES[0];

  return (
    <div className={styles.wrapper}>
      <select
        className={styles.select}
        value={current.code}
        aria-label={t('language.label')}
        onChange={(event) => void i18n.changeLanguage(event.target.value)}
      >
        {SUPPORTED_LANGUAGES.map((entry) => (
          <option key={entry.code} value={entry.code}>
            {entry.label}
          </option>
        ))}
      </select>
      <Icon name="chevronDown" size={16} strokeWidth={1.9} className={styles.chevron} />
    </div>
  );
}
