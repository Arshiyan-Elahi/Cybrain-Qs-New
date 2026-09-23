import { useTranslation } from 'react-i18next';
import { Icon } from '../common/Icon';
import type { CompanyStats } from '../../types';
import styles from './CkmStatusPanel.module.css';

interface CkmStatusPanelProps {
  companyName: string;
  stats?: CompanyStats;
  loading?: boolean;
  error?: string | null;
}

/** Plain readiness summary. Section and embedding counts stay under Details. */
export function CkmStatusPanel({
  companyName,
  stats,
  loading = false,
  error,
}: CkmStatusPanelProps) {
  const { t } = useTranslation();

  const summary = !stats
    ? loading
      ? t('common.loading')
      : error
        ? t('common.loadFailed', { message: error })
        : t('sop.ckm.noData')
    : stats.documentCount === 0
      ? t('ux.ckm.noDocuments')
      : t('ux.ckm.documentsReady', { value: stats.processedCount });

  return (
    <section className={styles.panel}>
      <h4 className={styles.title}>{t('ux.ckm.title', { company: companyName })}</h4>
      <ul className={styles.facts}>
        <li className={styles.fact}>
          <Icon name="checkCircle" size={14} strokeWidth={1.8} className={styles.icon} />
          <span>{summary}</span>
        </li>
      </ul>
      {stats && (
        <details className={styles.details}>
          <summary>{t('ux.details')}</summary>
          <ul className={styles.facts}>
            <li className={styles.fact}>{t('sop.ckm.chunksAvailable', { value: stats.chunkCount })}</li>
            <li className={styles.fact}>{t('sop.ckm.embeddingsAvailable', { value: stats.embeddedChunkCount })}</li>
            <li className={styles.fact}>
              {t('sop.ckm.aiStatus', {
                value: t(stats.aiFeaturesEnabled ? 'common.enabled' : 'common.disabled'),
              })}
            </li>
          </ul>
        </details>
      )}
    </section>
  );
}
