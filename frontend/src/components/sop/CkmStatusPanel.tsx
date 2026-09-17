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

/** Live document/knowledge readiness summary for the selected company. */
export function CkmStatusPanel({
  companyName,
  stats,
  loading = false,
  error,
}: CkmStatusPanelProps) {
  const { t } = useTranslation();

  const facts = stats
    ? [
        t('sop.ckm.documentsAnalysed', { value: stats.processedCount }),
        t('sop.ckm.chunksAvailable', { value: stats.chunkCount }),
        t('sop.ckm.embeddingsAvailable', { value: stats.embeddedChunkCount }),
        t('sop.ckm.aiStatus', {
          value: t(stats.aiFeaturesEnabled ? 'common.enabled' : 'common.disabled'),
        }),
      ]
    : [
        loading
          ? t('common.loading')
          : error
            ? t('common.loadFailed', { message: error })
            : t('sop.ckm.noData'),
      ];

  return (
    <section className={styles.panel}>
      <h4 className={styles.title}>{t('sop.ckm.title', { company: companyName })}</h4>
      <ul className={styles.facts}>
        {facts.map((fact) => (
          <li key={fact} className={styles.fact}>
            <Icon name="checkCircle" size={14} strokeWidth={1.8} className={styles.icon} />
            <span>{fact}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
