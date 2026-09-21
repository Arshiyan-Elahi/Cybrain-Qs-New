import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '../components/common/Button';
import { Icon } from '../components/common/Icon';
import { LanguageSwitcher } from '../components/common/LanguageSwitcher';
import { WizardStepper } from '../components/navigation/WizardStepper';
import { BlueprintReviewStep } from '../features/sops/BlueprintReviewStep';
import { ProjectInitializationStep } from '../features/sops/ProjectInitializationStep';
import { WIZARD_STEPS } from '../constants/wizard';
import { buildSopBlueprint, createSopProject } from '../services/sops';
import type { ProjectInitializationForm, SopProject } from '../types';
import styles from './CreateSopPage.module.css';

/** Initial form state reproducing the populated state shown in the design. */
const INITIAL_FORM: ProjectInitializationForm = {
  title: '',
  companyId: '',
  contextOptionIds: ['audit-finding'],
  additionalContext: '',
};

/** SOP creation wizard. Blueprint review is functional; later steps stay undesigned. */
export function CreateSopPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [activeIndex, setActiveIndex] = useState(0);
  const [form, setForm] = useState<ProjectInitializationForm>(INITIAL_FORM);
  const [project, setProject] = useState<SopProject | null>(null);
  const [blueprintLoading, setBlueprintLoading] = useState(false);
  const [blueprintError, setBlueprintError] = useState<string | null>(null);

  const isFirstStep = activeIndex === 0;
  const isLastStep = activeIndex === WIZARD_STEPS.length - 1;
  const activeStep = WIZARD_STEPS[activeIndex];
  const nextStep = WIZARD_STEPS[activeIndex + 1];
  const showBlueprint = activeIndex >= 1 && activeIndex <= 3;
  const canContinueFromInit = Boolean(form.title.trim() && form.companyId);

  const ensureBlueprint = async () => {
    if (!form.companyId || !form.title.trim()) {
      setBlueprintError(t('sop.blueprint.needTitleAndCompany'));
      return null;
    }
    setBlueprintLoading(true);
    setBlueprintError(null);
    try {
      const topic = form.title.trim();
      let next = project;
      if (
        next == null ||
        next.companyId !== form.companyId ||
        next.title !== form.title.trim()
      ) {
        next = await createSopProject(form.companyId, {
          title: form.title.trim(),
          topic,
          contextOptionIds: form.contextOptionIds,
          additionalContext: form.additionalContext,
        });
      }
      next = await buildSopBlueprint(form.companyId, next.id);
      setProject(next);
      return next;
    } catch (caught: unknown) {
      setBlueprintError(caught instanceof Error ? caught.message : t('common.requestFailed'));
      return null;
    } finally {
      setBlueprintLoading(false);
    }
  };

  const goNext = async () => {
    if (isFirstStep) {
      const built = await ensureBlueprint();
      if (!built) return;
    }
    setActiveIndex((index) => Math.min(WIZARD_STEPS.length - 1, index + 1));
  };

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
        ) : showBlueprint ? (
          <BlueprintReviewStep
            project={project}
            loading={blueprintLoading}
            error={blueprintError}
            onRebuild={() => {
              void ensureBlueprint();
            }}
          />
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
            disabled={isLastStep || blueprintLoading || (isFirstStep && !canContinueFromInit)}
            onClick={() => {
              void goNext();
            }}
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
