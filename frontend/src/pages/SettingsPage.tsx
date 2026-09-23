import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Icon } from '../components/common/Icon';
import { LanguageSwitcher } from '../components/common/LanguageSwitcher';
import { PageHeader } from '../components/common/PageHeader';
import { ADVANCED_NAV } from '../constants/navigation';
import { AiRuntimeCard } from '../features/settings/AiRuntimeCard';
import styles from './SettingsPage.module.css';

export function SettingsPage() {
  const { t } = useTranslation();

  return (
    <div className={styles.page}>
      <PageHeader
        title={t('ux.settings.title')}
        description={t('ux.settings.description')}
        action={<LanguageSwitcher />}
      />

      <section className={styles.card}>
        <h2>{t('ux.settings.languageTitle')}</h2>
        <p>{t('ux.settings.languageBody')}</p>
        <LanguageSwitcher />
      </section>

      <details className={styles.advanced}>
        <summary>{t('ux.advanced')}</summary>
        <p className={styles.advancedLead}>{t('ux.settings.advancedLead')}</p>
        <AiRuntimeCard />
        <h3>{t('ux.settings.otherAreas')}</h3>
        <ul className={styles.linkList}>
          {ADVANCED_NAV.map((item) => (
            <li key={item.id}>
              <Link to={item.to} className={styles.link}>
                <Icon name={item.icon} size={18} />
                <span>{t(item.labelKey)}</span>
              </Link>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
