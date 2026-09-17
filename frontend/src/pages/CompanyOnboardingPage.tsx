import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '../components/common/Button';
import { Icon } from '../components/common/Icon';
import { LanguageSwitcher } from '../components/common/LanguageSwitcher';
import { WizardStepper } from '../components/navigation/WizardStepper';
import { OnboardingStartStep } from '../features/companies/OnboardingStartStep';
import {
  OnboardingAiPreferencesStep,
  OnboardingBestPracticesStep,
  OnboardingBusinessRulesStep,
  OnboardingCompanyStep,
  OnboardingDocumentStructureStep,
  OnboardingFormsRecordsStep,
  OnboardingOrganisationStep,
  OnboardingProcessesStep,
  OnboardingRegulationsStep,
  OnboardingRelationshipsStep,
  OnboardingSummaryStep,
  OnboardingTemplatesStep,
  OnboardingTerminologyStep,
  OnboardingWritingStyleStep,
} from '../features/companies/OnboardingStepViews';
import {
  ONBOARDING_STEPS,
  SKIPPABLE_ONBOARDING_STEP_IDS,
} from '../constants/onboarding';
import { ROUTES } from '../constants/navigation';
import { INITIAL_ONBOARDING_FORM } from '../data/onboarding';
import { createCompany } from '../services/companies';
import { uploadDocument } from '../services/documents';
import { ApiError } from '../services/apiClient';
import type { CompanyOnboardingProfileInput, OnboardingForm } from '../types';
import {
  buildOnboardingDraft,
  clearOnboardingDraft,
  formFromDraft,
  loadOnboardingDraft,
  onboardingFileKey,
  saveOnboardingDraft,
} from '../utils/onboardingDraft';
import styles from './CompanyOnboardingPage.module.css';

type CreatePhase = 'idle' | 'creating' | 'uploading' | 'finalizing';

type PendingUpload = {
  file: File;
  kind: 'sop' | 'template';
  key: string;
};

const SUPPORTED_UPLOAD = /\.(pdf|docx)$/i;

function validateStep(stepId: string | undefined, form: OnboardingForm, t: (key: string) => string): string | null {
  if (stepId === 'start' && !form.startOptionId) {
    return t('onboarding.validation.startRequired');
  }
  if (stepId === 'company') {
    if (!form.companyName.trim()) return t('onboarding.validation.companyNameRequired');
    if (!form.industryKey) return t('onboarding.validation.industryRequired');
    if (!form.locationKey) return t('onboarding.validation.locationRequired');
  }
  return null;
}

function toOnboardingInput(form: OnboardingForm): CompanyOnboardingProfileInput {
  return {
    startOptionId: form.startOptionId,
    documentPathId: form.documentPathId,
    structurePreferenceId: form.structurePreferenceId,
    documentStructureNotes: form.documentStructureNotes,
    toneId: form.toneId,
    formalityId: form.formalityId,
    personId: form.personId,
    writingNotes: form.writingNotes,
    terminologyText: form.terminologyText,
    preferExistingTerms: form.preferExistingTerms,
    departmentsText: form.departmentsText,
    rolesText: form.rolesText,
    processesText: form.processesText,
    workflowNotes: form.workflowNotes,
    templatePreferenceId: form.templatePreferenceId,
    layoutNotes: form.layoutNotes,
    formsText: form.formsText,
    businessRulesText: form.businessRulesText,
    relationshipsText: form.relationshipsText,
    bestPracticesText: form.bestPracticesText,
    aiAssistLevelId: form.aiAssistLevelId,
    requireHumanVerification: form.requireHumanVerification,
    qualityNotes: form.qualityNotes,
    intendedDocumentNames: form.uploadedDocuments.map((file) => file.name),
    intendedTemplateNames: form.uploadedTemplates.map((file) => file.name),
  };
}

function pendingUploads(form: OnboardingForm): { uploads: PendingUpload[]; unsupported: string[] } {
  const byKey = new Map<string, PendingUpload>();
  const unsupported: string[] = [];

  const add = (file: File, kind: 'sop' | 'template') => {
    if (!SUPPORTED_UPLOAD.test(file.name)) {
      unsupported.push(file.name);
      return;
    }
    const key = onboardingFileKey(file);
    if (!byKey.has(key)) byKey.set(key, { file, kind, key });
  };

  for (const file of form.uploadedDocuments) add(file, 'sop');
  for (const file of form.uploadedTemplates) add(file, 'template');

  return { uploads: [...byKey.values()], unsupported };
}

/**
 * Client onboarding wizard — reached from "Create new company".
 * Finish persists the company profile, then uploads any selected documents.
 */
export function CompanyOnboardingPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const draft = loadOnboardingDraft();
  const [activeIndex, setActiveIndex] = useState(draft?.activeIndex ?? 0);
  const [form, setForm] = useState<OnboardingForm>(
    draft ? formFromDraft(draft) : INITIAL_ONBOARDING_FORM,
  );
  const [stepError, setStepError] = useState<string | null>(null);
  const [createPhase, setCreatePhase] = useState<CreatePhase>('idle');
  const [createProgress, setCreateProgress] = useState('');
  const [draftNotice, setDraftNotice] = useState<string | null>(() => {
    if (!draft) return null;
    const needsFiles = draft.documentNames.length > 0 || draft.templateNames.length > 0;
    return needsFiles
      ? t('onboarding.draft.restoredWithFiles')
      : t('onboarding.draft.restored');
  });

  const creationRequestIdRef = useRef<string | null>(draft?.creationRequestId ?? null);
  const createdCompanyIdRef = useRef<string | null>(draft?.createdCompanyId ?? null);
  const uploadedKeysRef = useRef<Set<string>>(new Set(draft?.uploadedKeys ?? []));
  const submittingRef = useRef(false);

  const activeStep = ONBOARDING_STEPS[activeIndex] ?? ONBOARDING_STEPS[0];
  const stepId = activeStep.id ?? 'start';
  const isFirstStep = activeIndex === 0;
  const isLastStep = activeIndex === ONBOARDING_STEPS.length - 1;
  const canSkip = SKIPPABLE_ONBOARDING_STEP_IDS.has(stepId);
  const busy = createPhase !== 'idle';

  useEffect(() => {
    if (busy) return;
    saveOnboardingDraft(
      buildOnboardingDraft(
        activeIndex,
        form,
        creationRequestIdRef.current,
        createdCompanyIdRef.current,
        [...uploadedKeysRef.current],
      ),
    );
  }, [activeIndex, form, busy]);

  const persistProgress = () => {
    saveOnboardingDraft(
      buildOnboardingDraft(
        activeIndex,
        form,
        creationRequestIdRef.current,
        createdCompanyIdRef.current,
        [...uploadedKeysRef.current],
      ),
    );
  };

  const goTo = (index: number) => {
    if (busy) return;
    setStepError(null);
    setDraftNotice(null);
    setActiveIndex(Math.max(0, Math.min(ONBOARDING_STEPS.length - 1, index)));
  };

  const finishOnboarding = async () => {
    if (submittingRef.current) return;
    submittingRef.current = true;

    const companyError = validateStep('company', form, t);
    if (companyError) {
      submittingRef.current = false;
      setStepError(companyError);
      const companyIndex = ONBOARDING_STEPS.findIndex((step) => step.id === 'company');
      if (companyIndex >= 0) setActiveIndex(companyIndex);
      return;
    }

    const { uploads, unsupported } = pendingUploads(form);
    const remaining = uploads.filter((item) => !uploadedKeysRef.current.has(item.key));
    if (unsupported.length > 0 && remaining.length === 0 && uploads.length === 0
      && (form.uploadedDocuments.length > 0 || form.uploadedTemplates.length > 0)) {
      submittingRef.current = false;
      setStepError(t('onboarding.validation.unsupportedFiles', { names: unsupported.join(', ') }));
      return;
    }

    setStepError(null);
    setDraftNotice(null);

    try {
      let companyId = createdCompanyIdRef.current;

      if (!companyId) {
        setCreatePhase('creating');
        setCreateProgress(t('onboarding.create.creating'));
        if (!creationRequestIdRef.current) {
          creationRequestIdRef.current = crypto.randomUUID();
        }
        const company = await createCompany({
          name: form.companyName.trim(),
          industryKey: form.industryKey,
          locationKey: form.locationKey,
          primaryLanguageKey: form.primaryLanguageKey || 'en',
          regulationIds: form.regulationIds,
          creationRequestId: creationRequestIdRef.current,
          onboarding: toOnboardingInput(form),
        });
        companyId = company.id;
        createdCompanyIdRef.current = company.id;
        persistProgress();
      }

      if (remaining.length > 0) {
        setCreatePhase('uploading');
        for (let index = 0; index < remaining.length; index += 1) {
          const item = remaining[index];
          setCreateProgress(t('onboarding.create.uploading', {
            current: index + 1,
            total: remaining.length,
            filename: item.file.name,
          }));
          const operationId = crypto.randomUUID();
          const controller = new AbortController();
          await uploadDocument(
            companyId,
            item.file,
            operationId,
            controller.signal,
            () => undefined,
            item.kind,
          );
          uploadedKeysRef.current.add(item.key);
          persistProgress();
        }
      }

      setCreatePhase('finalizing');
      setCreateProgress(t('onboarding.create.finalizing'));
      clearOnboardingDraft();
      navigate(ROUTES.companies, { state: { selectCompanyId: companyId } });
    } catch (caught) {
      // Keep wizard answers and any partial create/upload progress for retry.
      persistProgress();
      setCreatePhase('idle');
      setCreateProgress('');
      setStepError(
        caught instanceof ApiError || caught instanceof Error
          ? caught.message
          : t('common.requestFailed'),
      );
    } finally {
      submittingRef.current = false;
    }
  };

  const handleNext = () => {
    if (busy || submittingRef.current) return;
    const error = validateStep(stepId, form, t);
    if (error) {
      setStepError(error);
      return;
    }
    setStepError(null);
    setDraftNotice(null);
    if (isLastStep) {
      void finishOnboarding();
      return;
    }
    goTo(activeIndex + 1);
  };

  const handleSkip = () => {
    if (!canSkip || isLastStep || busy) return;
    setStepError(null);
    setDraftNotice(null);
    goTo(activeIndex + 1);
  };

  const renderStep = () => {
    const common = { value: form, onChange: setForm, error: stepError };
    switch (stepId) {
      case 'start':
        return <OnboardingStartStep {...common} />;
      case 'company':
        return <OnboardingCompanyStep {...common} />;
      case 'regulations':
        return <OnboardingRegulationsStep {...common} />;
      case 'documentStructure':
        return <OnboardingDocumentStructureStep {...common} />;
      case 'writingStyle':
        return <OnboardingWritingStyleStep {...common} />;
      case 'terminology':
        return <OnboardingTerminologyStep {...common} />;
      case 'organisation':
        return <OnboardingOrganisationStep {...common} />;
      case 'processes':
        return <OnboardingProcessesStep {...common} />;
      case 'templates':
        return <OnboardingTemplatesStep {...common} />;
      case 'formsRecords':
        return <OnboardingFormsRecordsStep {...common} />;
      case 'businessRules':
        return <OnboardingBusinessRulesStep {...common} />;
      case 'relationships':
        return <OnboardingRelationshipsStep {...common} />;
      case 'bestPractices':
        return <OnboardingBestPracticesStep {...common} />;
      case 'aiPreferences':
        return <OnboardingAiPreferencesStep {...common} />;
      case 'summary':
        return <OnboardingSummaryStep {...common} onEditStep={goTo} />;
      default:
        return <OnboardingStartStep {...common} />;
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.topBar}>
        <Button
          variant="neutral"
          size="sm"
          leadingIcon={<Icon name="chevronLeft" size={18} strokeWidth={1.9} />}
          disabled={busy}
          onClick={() => navigate(ROUTES.companies)}
        >
          {t('onboarding.back')}
        </Button>

        <LanguageSwitcher />
      </div>

      <WizardStepper
        steps={ONBOARDING_STEPS}
        activeIndex={activeIndex}
        onStepSelect={goTo}
        connected
        ariaLabelKey="onboarding.stepperLabel"
      />

      <p className={styles.progressLabel}>
        {t('onboarding.progress', {
          current: activeStep.ordinal,
          total: ONBOARDING_STEPS.length,
          label: t(activeStep.labelKey),
        })}
      </p>

      {draftNotice && (
        <p className={styles.createProgress} role="status">{draftNotice}</p>
      )}

      <div className={styles.body}>{renderStep()}</div>

      {createProgress && (
        <p className={styles.createProgress} role="status">{createProgress}</p>
      )}

      <footer className={styles.footer}>
        <Button
          variant="neutral"
          leadingIcon={<Icon name="arrowLeft" size={20} strokeWidth={1.9} />}
          disabled={isFirstStep || busy}
          onClick={() => goTo(activeIndex - 1)}
        >
          {t('onboarding.previous')}
        </Button>

        <div className={styles.footerActions}>
          {canSkip && (
            <Button variant="neutral" disabled={busy} onClick={handleSkip}>
              {t('onboarding.skip')}
            </Button>
          )}
          <Button
            trailingIcon={isLastStep || busy ? undefined : <Icon name="arrowRight" size={20} strokeWidth={1.9} />}
            disabled={busy}
            onClick={handleNext}
          >
            {busy
              ? t('onboarding.create.working')
              : isLastStep
                ? t('onboarding.create.submit')
                : t('onboarding.next')}
          </Button>
        </div>
      </footer>
    </div>
  );
}
