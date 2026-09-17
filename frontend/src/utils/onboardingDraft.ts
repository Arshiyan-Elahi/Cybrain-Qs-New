import type { OnboardingForm } from '../types';
import { INITIAL_ONBOARDING_FORM } from '../data/onboarding';

const DRAFT_KEY = 'cybrain.companyOnboarding.draft';
const DRAFT_VERSION = 1 as const;

export type OnboardingDraftPersisted = {
  version: typeof DRAFT_VERSION;
  activeIndex: number;
  form: Omit<OnboardingForm, 'uploadedDocuments' | 'uploadedTemplates'>;
  documentNames: string[];
  templateNames: string[];
  creationRequestId: string | null;
  createdCompanyId: string | null;
  uploadedKeys: string[];
};

function fileKey(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

export function onboardingFileKey(file: File): string {
  return fileKey(file);
}

export function buildOnboardingDraft(
  activeIndex: number,
  form: OnboardingForm,
  creationRequestId: string | null,
  createdCompanyId: string | null,
  uploadedKeys: string[],
): OnboardingDraftPersisted {
  const {
    uploadedDocuments: _docs,
    uploadedTemplates: _templates,
    ...serializable
  } = form;
  return {
    version: DRAFT_VERSION,
    activeIndex,
    form: serializable,
    documentNames: form.uploadedDocuments.map((file) => file.name),
    templateNames: form.uploadedTemplates.map((file) => file.name),
    creationRequestId,
    createdCompanyId,
    uploadedKeys,
  };
}

export function saveOnboardingDraft(draft: OnboardingDraftPersisted): void {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch {
    // Quota or private mode — wizard still works without draft persistence.
  }
}

export function clearOnboardingDraft(): void {
  try {
    localStorage.removeItem(DRAFT_KEY);
  } catch {
    // Ignore storage failures on clear.
  }
}

export function loadOnboardingDraft(): OnboardingDraftPersisted | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as OnboardingDraftPersisted;
    if (parsed?.version !== DRAFT_VERSION || typeof parsed.activeIndex !== 'number') {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function formFromDraft(draft: OnboardingDraftPersisted): OnboardingForm {
  return {
    ...INITIAL_ONBOARDING_FORM,
    ...draft.form,
    uploadedDocuments: [],
    uploadedTemplates: [],
  };
}
