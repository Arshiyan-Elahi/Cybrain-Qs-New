import type { AnalysisMetric, OnboardingForm, OnboardingStartOption } from '../types';

/**
 * MOCK DATA — frontend only.
 * Replace with service calls once the backend exists.
 */

/** "0.1 Was möchtest du mitbringen?" choices, in the order drawn. */
export const ONBOARDING_START_OPTIONS: OnboardingStartOption[] = [
  {
    id: 'template',
    icon: 'wordTemplate',
    titleKey: 'onboarding.start.options.template.title',
    descriptionKey: 'onboarding.start.options.template.description',
  },
  {
    id: 'existing-sops',
    icon: 'documentsStack',
    titleKey: 'onboarding.start.options.existing-sops.title',
    descriptionKey: 'onboarding.start.options.existing-sops.description',
  },
  {
    id: 'nothing',
    icon: 'blankPage',
    titleKey: 'onboarding.start.options.nothing.title',
    descriptionKey: 'onboarding.start.options.nothing.description',
  },
];

/**
 * AI analysis summary shown beside the choices.
 *
 * These are **AI-produced confidence figures, not verified company knowledge.**
 * They are mock values here; a real implementation must keep them marked as
 * proposed and carry provenance. See `.claude/skills/ckm-domain`.
 */
export const ANALYSIS_OVERALL = { completion: 87, confidence: 94 };

export const ANALYSIS_METRICS: AnalysisMetric[] = [
  {
    id: 'document-structure',
    icon: 'docStructure',
    labelKey: 'onboarding.analysis.metrics.document-structure',
    value: 98,
  },
  {
    id: 'writing-style',
    icon: 'writingStyle',
    labelKey: 'onboarding.analysis.metrics.writing-style',
    value: 96,
  },
  {
    id: 'terminology',
    icon: 'terminology',
    labelKey: 'onboarding.analysis.metrics.terminology',
    value: 91,
  },
  {
    id: 'regulatory',
    icon: 'regulatoryScan',
    labelKey: 'onboarding.analysis.metrics.regulatory',
    value: 88,
  },
  {
    id: 'workflow-extraction',
    icon: 'workflowExtract',
    labelKey: 'onboarding.analysis.metrics.workflow-extraction',
    value: 85,
  },
  {
    id: 'metadata-extraction',
    icon: 'metadataExtract',
    labelKey: 'onboarding.analysis.metrics.metadata-extraction',
    value: 99,
  },
];

export const INITIAL_ONBOARDING_FORM: OnboardingForm = {
  startOptionId: 'template',
  documentPathId: 'upload-template',
  uploadedDocuments: [],
  uploadedTemplates: [],
  companyName: '',
  industryKey: '',
  locationKey: '',
  primaryLanguageKey: 'en',
  regulationIds: [],
  structurePreferenceId: 'standard',
  documentStructureNotes: '',
  toneId: 'neutral',
  formalityId: 'formal',
  personId: 'third',
  writingNotes: '',
  terminologyText: '',
  preferExistingTerms: true,
  departmentsText: '',
  rolesText: '',
  processesText: '',
  workflowNotes: '',
  templatePreferenceId: 'use-uploaded',
  layoutNotes: '',
  formsText: '',
  businessRulesText: '',
  relationshipsText: '',
  bestPracticesText: '',
  aiAssistLevelId: 'balanced',
  requireHumanVerification: true,
  qualityNotes: '',
};

export function documentPathForStartOption(startOptionId: string): string {
  if (startOptionId === 'existing-sops') return 'upload-sops';
  if (startOptionId === 'nothing') return 'continue-without';
  return 'upload-template';
}
