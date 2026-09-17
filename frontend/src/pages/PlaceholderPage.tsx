import { useTranslation } from 'react-i18next';
import { LanguageSwitcher } from '../components/common/LanguageSwitcher';
import { PageHeader } from '../components/common/PageHeader';
import styles from './PlaceholderPage.module.css';

interface PlaceholderPageProps {
  /** Translation key for the section name. */
  titleKey: string;
}

/**
 * Destination for rail entries that appear in the design's navigation but
 * have no screen in the source PDFs yet.
 */
export function PlaceholderPage({ titleKey }: PlaceholderPageProps) {
  const { t } = useTranslation();

  return (
    <div className={styles.page}>
      <PageHeader
        title={t(titleKey)}
        description={t('placeholder.description')}
        action={<LanguageSwitcher />}
      />
    </div>
  );
}
