import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FieldCard } from '../../components/forms/FieldCard';
import { Checkbox } from '../../components/forms/Checkbox';
import { RadioOption } from '../../components/forms/RadioOption';
import { TextArea } from '../../components/forms/TextArea';
import { TextField } from '../../components/forms/TextField';
import { CkmStatusPanel } from '../../components/sop/CkmStatusPanel';
import { SopSuggestionList } from '../../components/sop/SopSuggestionList';
import {
  SOP_CONTEXT_OPTIONS,
  SOP_CONTEXT_PRIMARY_COUNT,
  WIZARD_STEPS,
} from '../../constants/wizard';
import { SOP_TITLE_SUGGESTIONS } from '../../data/sopProjects';
import { getCompanyStats, listCompanies } from '../../services/companies';
import type {
  Company,
  CompanyStats,
  ProjectInitializationForm,
  SopContextOption,
} from '../../types';
import styles from './ProjectInitializationStep.module.css';

interface ProjectInitializationStepProps {
  value: ProjectInitializationForm;
  onChange: (next: ProjectInitializationForm) => void;
}

/** Step 01 of the SOP creation wizard, with live company and document data. */
export function ProjectInitializationStep({
  value,
  onChange,
}: ProjectInitializationStepProps) {
  const { t } = useTranslation();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companiesLoading, setCompaniesLoading] = useState(true);
  const [companiesError, setCompaniesError] = useState<string | null>(null);
  const [stats, setStats] = useState<CompanyStats>();
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);

  const step = WIZARD_STEPS[0];
  const client = companies.find((entry) => entry.id === value.companyId);

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
    // Initial company loading should not restart on every form edit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!value.companyId) {
      setStats(undefined);
      return;
    }
    let cancelled = false;
    setStatsLoading(true);
    setStatsError(null);
    getCompanyStats(value.companyId)
      .then((next) => {
        if (!cancelled) setStats(next);
      })
      .catch((caught: unknown) => {
        if (!cancelled) {
          setStats(undefined);
          setStatsError(caught instanceof Error ? caught.message : t('common.requestFailed'));
        }
      })
      .finally(() => {
        if (!cancelled) setStatsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [value.companyId, t]);

  const toggleContextOption = (id: string, checked: boolean) => {
    const contextOptionIds = checked
      ? [...value.contextOptionIds, id]
      : value.contextOptionIds.filter((entry) => entry !== id);
    onChange({ ...value, contextOptionIds });
  };

  const primaryContextOptions = SOP_CONTEXT_OPTIONS.slice(0, SOP_CONTEXT_PRIMARY_COUNT);
  const secondaryContextOptions = SOP_CONTEXT_OPTIONS.slice(SOP_CONTEXT_PRIMARY_COUNT);

  const renderContextOption = (option: SopContextOption) => (
    <Checkbox
      key={option.id}
      label={t(option.labelKey)}
      checked={value.contextOptionIds.includes(option.id)}
      onChange={(checked) => toggleContextOption(option.id, checked)}
    />
  );

  return (
    <div className={styles.panel}>
      <h2 className={styles.title}>
        {step.ordinal}. {t(step.labelKey)}
      </h2>
      <p className={styles.subtitle}>{t('sop.step01.subtitle')}</p>

      <div className={styles.grid}>
        <FieldCard
          title={t('sop.step01.titleField.label')}
          hint={t('sop.step01.titleField.hint')}
        >
          <TextField
            value={value.title}
            onChange={(title) => onChange({ ...value, title })}
            placeholder={t('sop.step01.titleField.placeholder')}
            aria-label={t('sop.step01.titleField.label')}
          />
          <p className={styles.suggestionsLabel}>{t('sop.step01.suggestionsLabel')}</p>
          <SopSuggestionList
            suggestions={SOP_TITLE_SUGGESTIONS}
            onSelect={(title) => onChange({ ...value, title })}
          />
        </FieldCard>

        <FieldCard
          title={t('sop.step01.client.label')}
          hint={t('sop.step01.client.hint')}
          density="roomy"
        >
          <div className={styles.clientRow}>
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

            <CkmStatusPanel
              companyName={client?.name ?? t('sop.ckm.noCompany')}
              stats={stats}
              loading={statsLoading}
              error={statsError}
            />
          </div>
        </FieldCard>

        <FieldCard title={t('sop.step01.context.label')} hint={t('sop.step01.context.hint')}>
          <div className={styles.contextRows}>
            <div className={styles.contextRowPrimary}>
              {primaryContextOptions.map(renderContextOption)}
            </div>
            <div className={styles.contextRowSecondary}>
              {secondaryContextOptions.map(renderContextOption)}
            </div>
          </div>
        </FieldCard>

        <FieldCard title={t('sop.step01.additionalContext.label')} density="roomy">
          <TextArea
            value={value.additionalContext}
            onChange={(additionalContext) => onChange({ ...value, additionalContext })}
            placeholder={t('sop.step01.additionalContext.placeholder')}
            aria-label={t('sop.step01.additionalContext.aria')}
          />
        </FieldCard>
      </div>
    </div>
  );
}
