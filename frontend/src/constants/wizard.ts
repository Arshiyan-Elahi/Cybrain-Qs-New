import type { SopContextOption, WizardStep } from '../types';

/** The six wizard steps, in the order drawn in the design. */
export const WIZARD_STEPS: WizardStep[] = [
  { ordinal: '01', labelKey: 'sop.steps.project-initialization' },
  { ordinal: '02', labelKey: 'sop.steps.knowledge-selection' },
  { ordinal: '03', labelKey: 'sop.steps.blueprint-builder' },
  { ordinal: '04', labelKey: 'sop.steps.knowledge-mapping' },
  { ordinal: '05', labelKey: 'sop.steps.draft-generation' },
  { ordinal: '06', labelKey: 'sop.steps.review-iteration' },
];

/**
 * The design lays the context options out as one three-column row followed by
 * two-column rows, with the second column starting further right. Kept explicit
 * so the layout matches the drawing rather than whatever a uniform grid
 * happens to produce.
 */
export const SOP_CONTEXT_PRIMARY_COUNT = 3;

/** "Why is this SOP required?" options, in the order shown. */
export const SOP_CONTEXT_OPTIONS: SopContextOption[] = [
  { id: 'new-process', labelKey: 'sop.contextOptions.new-process' },
  { id: 'audit-finding', labelKey: 'sop.contextOptions.audit-finding' },
  { id: 'new-customer', labelKey: 'sop.contextOptions.new-customer' },
  { id: 'regulatory', labelKey: 'sop.contextOptions.regulatory' },
  { id: 'harmonisation', labelKey: 'sop.contextOptions.harmonisation' },
  { id: 'replaces-existing', labelKey: 'sop.contextOptions.replaces-existing' },
  { id: 'other', labelKey: 'sop.contextOptions.other' },
];
