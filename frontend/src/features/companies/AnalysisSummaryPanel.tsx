import { useTranslation } from 'react-i18next';
import { Icon } from '../../components/common/Icon';
import { ProgressBar } from '../../components/common/ProgressBar';
import type { AnalysisMetric } from '../../types';
import styles from './AnalysisSummaryPanel.module.css';

interface AnalysisSummaryPanelProps {
  completion: number;
  confidence: number;
  metrics: AnalysisMetric[];
}

/**
 * "Zusammenfassung der KI-Analyse" — confidence figures produced by the AI
 * analysis of the client's uploaded material.
 *
 * These are proposed values, never verified company knowledge. The info glyph
 * beside each figure is where provenance will be surfaced once a backend
 * supplies it.
 */
export function AnalysisSummaryPanel({
  completion,
  confidence,
  metrics,
}: AnalysisSummaryPanelProps) {
  const { t } = useTranslation();

  const headlines = [
    {
      id: 'completion',
      label: t('onboarding.analysis.overall'),
      value: completion,
      readout: t('onboarding.analysis.completed', { value: completion }),
    },
    {
      id: 'confidence',
      label: t('onboarding.analysis.confidence'),
      value: confidence,
      readout: `${confidence}%`,
    },
  ];

  return (
    <section className={styles.panel}>
      <h3 className={styles.title}>{t('onboarding.analysis.title')}</h3>

      {headlines.map((row) => (
        <div key={row.id} className={styles.headline}>
          <div className={styles.headlineTop}>
            <span className={styles.headlineLabel}>{row.label}</span>
            <span className={styles.readout}>{row.readout}</span>
            <Icon
              name="alertCircle"
              size={16}
              strokeWidth={1.7}
              className={styles.info}
            />
          </div>
          <ProgressBar value={row.value} size="lg" label={row.label} />
        </div>
      ))}

      <hr className={styles.rule} />

      <ul className={styles.metrics}>
        {metrics.map((metric) => {
          const label = t(metric.labelKey);
          return (
            <li key={metric.id} className={styles.metric}>
              <span className={styles.metricIcon}>
                <Icon name={metric.icon} size={17} />
              </span>
              <div className={styles.metricBody}>
                <div className={styles.metricTop}>
                  <span className={styles.metricLabel}>{label}</span>
                  <span className={styles.readout}>{metric.value}%</span>
                  <Icon
                    name="alertCircle"
                    size={16}
                    strokeWidth={1.7}
                    className={styles.info}
                  />
                </div>
                <ProgressBar value={metric.value} label={label} />
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
