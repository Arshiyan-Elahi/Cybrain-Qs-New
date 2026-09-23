import { useTranslation } from 'react-i18next';
import { ProgressBar } from '../../components/common/ProgressBar';
import { WIZARD_STEPS } from '../../constants/wizard';
import styles from './SopPreparationStep.module.css';

interface SopPreparationStepProps {
  loading: boolean;
  error: string | null;
  done: boolean;
}

/** Step 2 — plain-language preparation while blueprint/retrieval runs. */
export function SopPreparationStep({ loading, error, done }: SopPreparationStepProps) {
  const { t } = useTranslation();
  const step = WIZARD_STEPS[1];

  return (
    <div className={styles.panel}>
      <h2 className={styles.title}>
        {step.ordinal}. {t(step.labelKey)}
      </h2>
      <p className={styles.lead}>{t('sop.guided.step2.lead')}</p>

      <div className={styles.statusCard} aria-live="polite">
        {loading && (
          <>
            <p className={styles.statusTitle}>{t('sop.guided.step2.working')}</p>
            <ProgressBar value={55} size="lg" label={t('sop.guided.step2.working')} />
            <ul className={styles.checklist}>
              <li>{t('sop.guided.step2.task.knowledge')}</li>
              <li>{t('sop.guided.step2.task.outline')}</li>
              <li>{t('sop.guided.step2.task.evidence')}</li>
              <li>{t('sop.guided.step2.task.gaps')}</li>
            </ul>
          </>
        )}
        {!loading && error && (
          <p className={styles.error} role="alert">{error}</p>
        )}
        {!loading && !error && done && (
          <>
            <p className={styles.statusTitle}>{t('sop.guided.step2.done')}</p>
            <p className={styles.note}>{t('sop.guided.step2.doneBody')}</p>
          </>
        )}
      </div>
    </div>
  );
}
