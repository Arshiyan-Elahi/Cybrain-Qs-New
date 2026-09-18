import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '../components/common/LanguageSwitcher';
import { PageHeader } from '../components/common/PageHeader';
import { AiRuntimeCard } from '../features/settings/AiRuntimeCard';
import styles from './SettingsPage.module.css';

export function SettingsPage() {
  const { t } = useTranslation();

  return (
    <div className={styles.page}>
      <PageHeader
        title={t('nav.settings')}
        description={t('settings.description')}
        action={<LanguageSwitcher />}
      />
      <AiRuntimeCard />
    </div>
  );
}
