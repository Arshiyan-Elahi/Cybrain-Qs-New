import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '../components/common/Button';
import { Icon } from '../components/common/Icon';
import { LanguageSwitcher } from '../components/common/LanguageSwitcher';
import { WizardStepper } from '../components/navigation/WizardStepper';
import { ProjectInitializationStep } from '../features/sops/ProjectInitializationStep';
import { WIZARD_STEPS } from '../constants/wizard';
import type { ProjectInitializationForm } from '../types';
import styles from './CreateSopPage.module.css';

/** Initial form state reproducing the populated state shown in the design. */
const INITIAL_FORM: ProjectInitializationForm = {
  title: '',
  companyId: '',
  contextOptionIds: ['audit-finding'],
  additionalContext: '',
};

/** SOP creation wizard. Only step 01 is designed in the source PDFs. */
export function CreateSopPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [activeIndex, setActiveIndex] = useState(0);
  const [form, setForm] = useState<ProjectInitializationForm>(INITIAL_FORM);

  const isFirstStep = activeIndex === 0;
  const isLastStep = activeIndex === WIZARD_STEPS.length - 1;
  const activeStep = WIZARD_STEPS[activeIndex];
  const nextStep = WIZARD_STEPS[activeIndex + 1];

  return (
    <div className={styles.page}>
      <div className={styles.topBar}>
        <Button
          variant="neutral"
          size="sm"
          leadingIcon={<Icon name="chevronLeft" size={18} strokeWidth={1.9} />}
          onClick={() => navigate(-1)}
        >
          {t('sop.wizard.back')}
        </Button>

        <LanguageSwitcher />
      </div>

      <WizardStepper
        steps={WIZARD_STEPS}
        activeIndex={activeIndex}
        onStepSelect={setActiveIndex}
      />

      <div className={styles.body}>
        {isFirstStep ? (
          <ProjectInitializationStep value={form} onChange={setForm} />
        ) : (
          <div className={styles.notDesigned}>
            <h2 className={styles.notDesignedTitle}>
              {activeStep.ordinal}. {t(activeStep.labelKey)}
            </h2>
            <p className={styles.notDesignedText}>{t('sop.wizard.notDesigned')}</p>
          </div>
        )}
      </div>

      <footer className={styles.footer}>
        <Button
          variant="neutral"
          leadingIcon={<Icon name="chevronLeft" size={20} strokeWidth={1.9} />}
          disabled={isFirstStep}
          onClick={() => setActiveIndex((index) => Math.max(0, index - 1))}
        >
          {t('sop.wizard.back')}
        </Button>

        <div className={styles.footerActions}>
          <Button
            variant="outline"
            leadingIcon={<Icon name="search" size={20} strokeWidth={1.9} />}
            disabled
            title={t('sop.wizard.searchUnavailable')}
          >
            {t('sop.wizard.searchSimilar')}
          </Button>

          <Button
            trailingIcon={<Icon name="arrowRight" size={20} strokeWidth={1.9} />}
            disabled={isLastStep}
            onClick={() =>
              setActiveIndex((index) => Math.min(WIZARD_STEPS.length - 1, index + 1))
            }
          >
            {nextStep
              ? t('sop.wizard.continueTo', { step: t(nextStep.labelKey) })
              : t('sop.wizard.finish')}
          </Button>
        </div>
      </footer>
    </div>
  );
}
