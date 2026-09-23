import type { SopContextOption, WizardStep } from '../types';

/** Guided Create SOP steps for QA users (reuses project + blueprint APIs). */
export const WIZARD_STEPS: WizardStep[] = [
  { ordinal: '01', labelKey: 'sop.steps.what-to-create' },
  { ordinal: '02', labelKey: 'sop.steps.preparing' },
  { ordinal: '03', labelKey: 'sop.steps.check-before' },
  { ordinal: '04', labelKey: 'sop.steps.sop-draft' },
];

/**
 * The design lays the context options out as one three-column row followed by
 * two-column rows, with the second column starting further right. Kept explicit
 * so the layout matches the drawing rather than whatever a uniform grid
 * happens to produce.
 */
export const SOP_CONTEXT_PRIMARY_COUNT = 3;

/** "Why is this SOP required?" options — kept for Advanced / API compatibility. */
export const SOP_CONTEXT_OPTIONS: SopContextOption[] = [
  { id: 'new-process', labelKey: 'sop.contextOptions.new-process' },
  { id: 'audit-finding', labelKey: 'sop.contextOptions.audit-finding' },
  { id: 'new-customer', labelKey: 'sop.contextOptions.new-customer' },
  { id: 'regulatory', labelKey: 'sop.contextOptions.regulatory' },
  { id: 'harmonisation', labelKey: 'sop.contextOptions.harmonisation' },
  { id: 'replaces-existing', labelKey: 'sop.contextOptions.replaces-existing' },
  { id: 'other', labelKey: 'sop.contextOptions.other' },
];
