import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FieldCard } from '../../components/forms/FieldCard';
import { RadioOption } from '../../components/forms/RadioOption';
import { TextArea } from '../../components/forms/TextArea';
import { TextField } from '../../components/forms/TextField';
import { WIZARD_STEPS } from '../../constants/wizard';
import { listCompanies } from '../../services/companies';
import type { Company, ProjectInitializationForm } from '../../types';
import styles from './ProjectInitializationStep.module.css';

interface ProjectInitializationStepProps {
  value: ProjectInitializationForm;
  onChange: (next: ProjectInitializationForm) => void;
}

/** Step 1 — what to create. Company stays required; context options stay under Advanced. */
export function ProjectInitializationStep({
  value,
  onChange,
}: ProjectInitializationStepProps) {
  const { t } = useTranslation();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(true);
  const [companiesError, setCompaniesError] = useState<string | null>(null);
  const step = WIZARD_STEPS[0];

  useEffect(() => {
    let cancelled = false;
    setCompaniesLoading(true);
    setCompaniesError(null);
    listCompanies()
      .then((page) => {
        if (cancelled) return;
        setCompanies(page.items);
        if (page.items.length > 0 && !page.items.some((entry) => entry.id === value.companyId)) {
          onChange({ ...value, companyId: page.items[0].id });
        }
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setCompaniesError(caught instanceof Error ? caught.message : t('common.requestFailed'));
        }
      })
      .finally(() => {
        if (!cancelled) setCompaniesLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={styles.panel}>
      <h2 className={styles.title}>
        {step.ordinal}. {t(step.labelKey)}
      </h2>
      <p className={styles.subtitle}>{t('sop.guided.step1.subtitle')}</p>

      <div className={styles.simpleStack}>
        <FieldCard
          title={t('sop.guided.step1.titleLabel')}
          hint={t('sop.guided.step1.titleHint')}
        >
          <TextField
            value={value.title}
            onChange={(title) => onChange({ ...value, title })}
            placeholder={t('sop.guided.step1.titlePlaceholder')}
            aria-label={t('sop.guided.step1.titleLabel')}
          />
        </FieldCard>

        <FieldCard
          title={t('sop.guided.step1.instructionsLabel')}
          hint={t('sop.guided.step1.instructionsHint')}
          density="roomy"
        >
          <TextArea
            value={value.additionalContext}
            onChange={(additionalContext) => onChange({ ...value, additionalContext })}
            placeholder={t('sop.guided.step1.instructionsPlaceholder')}
            aria-label={t('sop.guided.step1.instructionsLabel')}
          />
        </FieldCard>

        <details className={styles.advanced}>
          <summary>{t('ux.advanced')}</summary>
          <FieldCard
            title={t('sop.step01.client.label')}
            hint={t('sop.step01.client.hint')}
            density="roomy"
          >
            <div className={styles.clientPicker}>
              {companies.map((entry) => (
                <RadioOption
                  key={entry.id}
                  name="wizard-client"
                  value={entry.id}
                  label={entry.name}
                  checked={entry.id === value.companyId}
                  onChange={(companyId) => onChange({ ...value, companyId })}
                />
              ))}
              {companiesLoading && <span>{t('common.loading')}</span>}
              {companiesError && <span role="alert">{companiesError}</span>}
            </div>
          </FieldCard>
        </details>
      </div>
    </div>
  );
}
