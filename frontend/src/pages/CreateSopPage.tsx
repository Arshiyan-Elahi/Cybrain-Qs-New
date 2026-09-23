import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '../components/common/Button';
import { Icon } from '../components/common/Icon';
import { LanguageSwitcher } from '../components/common/LanguageSwitcher';
import { WizardStepper } from '../components/navigation/WizardStepper';
import { ProjectInitializationStep } from '../features/sops/ProjectInitializationStep';
import { SopDraftDocumentStep } from '../features/sops/SopDraftDocumentStep';
import { SopPreparationStep } from '../features/sops/SopPreparationStep';
import { SopReadinessCheckStep } from '../features/sops/SopReadinessCheckStep';
import { WIZARD_STEPS } from '../constants/wizard';
import { ROUTES } from '../constants/navigation';
import {
  buildSopBlueprint,
  createSopProject,
  markSopGenerationReady,
} from '../services/sops';
import type { ProjectInitializationForm, SopProject } from '../types';
import styles from './CreateSopPage.module.css';

const INITIAL_FORM: ProjectInitializationForm = {
  title: '',
  companyId: '',
  contextOptionIds: [],
  additionalContext: '',
};

/** Guided Create SOP wizard for QA users. Reuses project + blueprint APIs. */
export function CreateSopPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const [activeIndex, setActiveIndex] = useState(0);
  const [form, setForm] = useState<ProjectInitializationForm>({
    ...INITIAL_FORM,
    companyId: searchParams.get('company') ?? '',
  });
  const [project, setProject] = useState<SopProject | null>(null);
  const [blueprintLoading, setBlueprintLoading] = useState(false);
  const [blueprintError, setBlueprintError] = useState<string | null>(null);
  const [gapAnswers, setGapAnswers] = useState<Record<string, string>>({});
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const autoAdvanceRef = useRef(false);

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
        next == null
        || next.companyId !== form.companyId
        || next.title !== form.title.trim()
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

  const startPreparation = async () => {
    autoAdvanceRef.current = true;
    setActiveIndex(1);
    const built = await ensureBlueprint();
    if (!built) {
      autoAdvanceRef.current = false;
    }
  };

  useEffect(() => {
    if (activeIndex !== 1) return;
    if (blueprintLoading) return;
    if (blueprintError) return;
    if (!project?.blueprint) return;
    if (!autoAdvanceRef.current) return;
    autoAdvanceRef.current = false;
    setActiveIndex(2);
  }, [activeIndex, blueprintLoading, blueprintError, project]);

  const createDraft = async () => {
    if (!project || !form.companyId) return;
    setSaveBusy(true);
    setSaveMessage(null);
    try {
      const next = await markSopGenerationReady(form.companyId, project.id);
      setProject(next);
      setActiveIndex(3);
    } catch (caught: unknown) {
      setBlueprintError(caught instanceof Error ? caught.message : t('common.requestFailed'));
    } finally {
      setSaveBusy(false);
    }
  };

  const saveDraft = async () => {
    if (!project || !form.companyId) return;
    setSaveBusy(true);
    setSaveMessage(null);
    try {
      const next = project.status === 'generation_ready'
        ? project
        : await markSopGenerationReady(form.companyId, project.id);
      setProject(next);
      setSaveMessage(t('sop.guided.draft.saved'));
    } catch (caught: unknown) {
      setBlueprintError(caught instanceof Error ? caught.message : t('common.requestFailed'));
    } finally {
      setSaveBusy(false);
    }
  };

  const regenerate = async () => {
    autoAdvanceRef.current = false;
    setActiveIndex(1);
    const built = await ensureBlueprint();
    if (built) setActiveIndex(2);
  };

  const footerBack = () => {
    if (activeIndex === 0) {
      navigate(-1);
      return;
    }
    setActiveIndex((index) => Math.max(0, index - 1));
  };

  return (
    <div className={styles.page}>
      <div className={styles.topBar}>
        <Button
          variant="neutral"
          size="sm"
          leadingIcon={<Icon name="chevronLeft" size={18} strokeWidth={1.9} />}
          onClick={() => navigate(ROUTES.sopLibrary)}
        >
          {t('sop.wizard.back')}
        </Button>
        <LanguageSwitcher />
      </div>

      <WizardStepper
        steps={WIZARD_STEPS}
        activeIndex={activeIndex}
        onStepSelect={(index) => {
          if (index <= activeIndex) setActiveIndex(index);
        }}
      />

      <div className={styles.body}>
        {activeIndex === 0 && (
          <ProjectInitializationStep value={form} onChange={setForm} />
        )}
        {activeIndex === 1 && (
          <SopPreparationStep
            loading={blueprintLoading}
            error={blueprintError}
            done={Boolean(project?.blueprint) && !blueprintLoading && !blueprintError}
          />
        )}
        {activeIndex === 2 && (
          <SopReadinessCheckStep
            project={project}
            gapAnswers={gapAnswers}
            onGapAnswerChange={(key, value) => {
              setGapAnswers((current) => ({ ...current, [key]: value }));
            }}
          />
        )}
        {activeIndex === 3 && project && (
          <SopDraftDocumentStep
            project={project}
            gapAnswers={gapAnswers}
            busy={saveBusy || blueprintLoading}
            onEdit={() => setActiveIndex(0)}
            onRegenerate={() => {
              void regenerate();
            }}
            onSaveDraft={() => {
              void saveDraft();
            }}
          />
        )}
        {saveMessage && (
          <p className={styles.saveMessage} role="status">{saveMessage}</p>
        )}
      </div>

      <footer className={styles.footer}>
        <Button
          variant="neutral"
          leadingIcon={<Icon name="chevronLeft" size={20} strokeWidth={1.9} />}
          onClick={footerBack}
          disabled={activeIndex === 1 && blueprintLoading}
        >
          {t('sop.wizard.back')}
        </Button>

        <div className={styles.footerActions}>
          {activeIndex === 0 && (
            <Button
              trailingIcon={<Icon name="arrowRight" size={20} strokeWidth={1.9} />}
              disabled={!canContinueFromInit || blueprintLoading}
              onClick={() => {
                void startPreparation();
              }}
            >
              {t('sop.guided.continue')}
            </Button>
          )}
          {activeIndex === 1 && blueprintError && (
            <Button
              onClick={() => {
                void startPreparation();
              }}
            >
              {t('sop.guided.retryPrepare')}
            </Button>
          )}
          {activeIndex === 1 && !blueprintLoading && !blueprintError && project?.blueprint && (
            <Button
              trailingIcon={<Icon name="arrowRight" size={20} strokeWidth={1.9} />}
              onClick={() => setActiveIndex(2)}
            >
              {t('sop.guided.continue')}
            </Button>
          )}
          {activeIndex === 2 && (
            <Button
              trailingIcon={<Icon name="arrowRight" size={20} strokeWidth={1.9} />}
              disabled={!project?.blueprint || saveBusy}
              onClick={() => {
                void createDraft();
              }}
            >
              {t('sop.guided.createDraft')}
            </Button>
          )}
          {activeIndex === 3 && (
            <Button
              onClick={() => navigate(`${ROUTES.sopLibrary}?company=${form.companyId}`)}
            >
              {t('sop.guided.done')}
            </Button>
          )}
        </div>
      </footer>
    </div>
  );
}
