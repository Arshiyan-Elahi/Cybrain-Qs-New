import type { SopTitleSuggestion } from '../types';

/**
 * MOCK DATA — frontend only.
 * In a later phase these suggestions come from a similarity search over the
 * client's existing SOP corpus; here they are static so the UI can be built.
 *
 * Display text is stored as i18n keys (see `src/i18n/`); counts and dates are
 * stored as values and interpolated into the translated sentence.
 */
export const SOP_TITLE_SUGGESTIONS: SopTitleSuggestion[] = [
  { id: 'supplier-management', labelKey: 'sop.suggestions.supplier-management' },
  { id: 'supplier-approval', labelKey: 'sop.suggestions.supplier-approval' },
  {
    id: 'external-provider-qualification',
    labelKey: 'sop.suggestions.external-provider-qualification',
  },
];
