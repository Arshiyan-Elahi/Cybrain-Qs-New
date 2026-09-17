import type { WizardStep } from '../types';

/**
 * Full client onboarding flow — fifteen sections covering start method through
 * summary review. Navigation uses this list; the header stepper may truncate.
 */
export const ONBOARDING_STEPS: WizardStep[] = [
  { id: 'start', ordinal: '01', labelKey: 'onboarding.steps.start' },
  { id: 'company', ordinal: '02', labelKey: 'onboarding.steps.company' },
  { id: 'regulations', ordinal: '03', labelKey: 'onboarding.steps.regulations' },
  { id: 'documentStructure', ordinal: '04', labelKey: 'onboarding.steps.documentStructure' },
  { id: 'writingStyle', ordinal: '05', labelKey: 'onboarding.steps.writingStyle' },
  { id: 'terminology', ordinal: '06', labelKey: 'onboarding.steps.terminology' },
  { id: 'organisation', ordinal: '07', labelKey: 'onboarding.steps.organisation' },
  { id: 'processes', ordinal: '08', labelKey: 'onboarding.steps.processes' },
  { id: 'templates', ordinal: '09', labelKey: 'onboarding.steps.templates' },
  { id: 'formsRecords', ordinal: '10', labelKey: 'onboarding.steps.formsRecords' },
  { id: 'businessRules', ordinal: '11', labelKey: 'onboarding.steps.businessRules' },
  { id: 'relationships', ordinal: '12', labelKey: 'onboarding.steps.relationships' },
  { id: 'bestPractices', ordinal: '13', labelKey: 'onboarding.steps.bestPractices' },
  { id: 'aiPreferences', ordinal: '14', labelKey: 'onboarding.steps.aiPreferences' },
  { id: 'summary', ordinal: '15', labelKey: 'onboarding.steps.summary' },
];

/**
 * Optional truncated header presentation (first five + summary). The live
 * wizard navigates the full `ONBOARDING_STEPS` list.
 */
export const VISIBLE_ONBOARDING_STEPS: WizardStep[] = [
  ...ONBOARDING_STEPS.slice(0, 5),
  { ...ONBOARDING_STEPS[ONBOARDING_STEPS.length - 1], truncatedBefore: true },
];

export const ONBOARDING_INDUSTRY_KEYS = ['pharma', 'medtech', 'biotech', 'cosmetics'] as const;
export const ONBOARDING_LOCATION_KEYS = ['vienna-at', 'zurich-ch', 'munich-de', 'graz-at', 'berlin-de'] as const;
export const ONBOARDING_LANGUAGE_KEYS = ['de', 'en'] as const;
export const ONBOARDING_REGULATION_KEYS = [
  'eu-gmp', 'fda', 'ich-09', 'ich-q10', 'annex-11', 'annex-1', 'iso-13485', 'mdr', 'fda-21-cfr-820', 'iso-22716',
] as const;

export const SKIPPABLE_ONBOARDING_STEP_IDS = new Set([
  'documentStructure',
  'writingStyle',
  'terminology',
  'organisation',
  'processes',
  'templates',
  'formsRecords',
  'businessRules',
  'relationships',
  'bestPractices',
  'aiPreferences',
  'regulations',
]);
