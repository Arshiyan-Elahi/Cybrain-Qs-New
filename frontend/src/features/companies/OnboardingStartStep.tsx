import { useTranslation } from 'react-i18next';
import { OptionCard } from '../../components/forms/OptionCard';
import { RadioOption } from '../../components/forms/RadioOption';
import { FieldCard } from '../../components/forms/FieldCard';
import {
  ANALYSIS_METRICS,
  ANALYSIS_OVERALL,
  documentPathForStartOption,
  ONBOARDING_START_OPTIONS,
} from '../../data/onboarding';
import type { OnboardingForm } from '../../types';
import { AnalysisSummaryPanel } from './AnalysisSummaryPanel';
import { OnboardingFilesField } from './OnboardingFilesField';
import styles from './OnboardingStartStep.module.css';
import layoutStyles from './OnboardingStepLayout.module.css';

interface OnboardingStartStepProps {
  value: OnboardingForm;
  onChange: (next: OnboardingForm) => void;
  error?: string | null;
}

/** Section 0 of the client onboarding wizard: "what do you already have?". */
export function OnboardingStartStep({ value, onChange, error }: OnboardingStartStepProps) {
  const { t } = useTranslation();

  const selectStart = (startOptionId: string) => {
    onChange({
      ...value,
      startOptionId,
      documentPathId: documentPathForStartOption(startOptionId),
    });
  };

  return (
    <div className={styles.panel}>
      <div className={styles.columns}>
        <section className={styles.choices}>
          <h2 className={styles.title}>{t('onboarding.start.title')}</h2>
          <p className={styles.subtitle}>{t('onboarding.start.subtitle')}</p>
          {error && <p className={layoutStyles.error} role="alert">{error}</p>}

          <h3 className={styles.question}>{t('onboarding.start.question')}</h3>

          <div className={styles.options}>
            {ONBOARDING_START_OPTIONS.map((option) => (
              <OptionCard
                key={option.id}
                name="onboarding-start"
                value={option.id}
                icon={option.icon}
                title={t(option.titleKey)}
                description={t(option.descriptionKey)}
                checked={option.id === value.startOptionId}
                onChange={selectStart}
              />
            ))}
          </div>

          <div className={styles.pathBlock}>
            <FieldCard title={t('onboarding.start.pathTitle')} hint={t('onboarding.start.pathHint')}>
              <div className={layoutStyles.optionGrid}>
                {['upload-template', 'upload-sops', 'continue-without'].map((id) => (
                  <RadioOption
                    key={id}
                    name="onboarding-document-path"
                    value={id}
                    label={t(`onboarding.start.paths.${id}`)}
                    checked={value.documentPathId === id}
                    onChange={(documentPathId) => onChange({ ...value, documentPathId })}
                  />
                ))}
              </div>
            </FieldCard>

            {value.documentPathId === 'upload-sops' && (
              <FieldCard title={t('onboarding.start.uploadSopsTitle')} hint={t('onboarding.start.uploadSopsHint')}>
                <OnboardingFilesField
                  files={value.uploadedDocuments}
                  onChange={(uploadedDocuments) => onChange({ ...value, uploadedDocuments })}
                  addLabel={t('onboarding.files.addDocuments')}
                  emptyLabel={t('onboarding.files.emptyDocuments')}
                  removeLabel={t('onboarding.files.remove')}
                />
              </FieldCard>
            )}

            {value.documentPathId === 'upload-template' && (
              <FieldCard title={t('onboarding.start.uploadTemplateTitle')} hint={t('onboarding.start.uploadTemplateHint')}>
                <OnboardingFilesField
                  files={value.uploadedTemplates}
                  accept=".pdf,.docx"
                  multiple={false}
                  onChange={(uploadedTemplates) => onChange({ ...value, uploadedTemplates })}
                  addLabel={t('onboarding.files.addTemplate')}
                  emptyLabel={t('onboarding.files.emptyTemplate')}
                  removeLabel={t('onboarding.files.remove')}
                />
              </FieldCard>
            )}

            {value.documentPathId === 'continue-without' && (
              <p className={layoutStyles.empty}>{t('onboarding.start.continueWithoutHelper')}</p>
            )}
          </div>
        </section>

        <AnalysisSummaryPanel
          completion={ANALYSIS_OVERALL.completion}
          confidence={ANALYSIS_OVERALL.confidence}
          metrics={ANALYSIS_METRICS}
        />
      </div>
    </div>
  );
}
