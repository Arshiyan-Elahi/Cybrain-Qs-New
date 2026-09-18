import type { IconName } from '../components/common/Icon';

/**
 * Fields ending in `Key` / `Ids` hold i18n keys rather than display strings.
 * They are resolved with `t()` at render time so the same data serves both
 * languages. See `src/i18n/`.
 */

/** Paged list envelope returned by every list endpoint. */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

/** Signed-in user, as returned by `/auth/me`. */
export interface AuthUser {
  id: string;
  email: string;
  fullName: string;
  isActive: boolean;
}

export interface TokenResponse {
  accessToken: string;
  tokenType: string;
}

/** Dashboard counters for one company. Contains no AI-derived values. */
export interface CompanyStats {
  companyId: string;
  documentCount: number;
  processedCount: number;
  needsOcrCount: number;
  failedCount: number;
  chunkCount: number;
  totalBytes: number;
  /** False while the backend runs without an inference server. */
  aiFeaturesEnabled: boolean;
  embeddedChunkCount: number;
}

/** An uploaded source document. */
export interface DocumentSummary {
  id: string;
  companyId: string;
  filename: string;
  sourceFormat: string;
  status: 'uploaded' | 'processing' | 'processed' | 'failed' | 'needs_ocr' | 'cancelled';
  pageCount: number;
  byteSize: number;
  /** Parsing problems, surfaced rather than hidden. */
  warnings: string[];
  /** Origin: general upload, onboarding SOP, or onboarding template. */
  kind: 'general' | 'sop' | 'template';
  createdAt: string;
}

export interface DocumentDetail extends DocumentSummary {
  chunkCount: number;
  semanticChunkCount: number;
  embeddedChunkCount: number;
}

export interface DocumentOperationProgress {
  stage: string;
  progress: number;
  status: 'running' | 'cancelling' | 'cancelled' | 'completed' | 'failed';
  error: string | null;
}

export interface DocumentChunk {
  id: string;
  chunkOrder: number;
  text: string;
  headingPath: string[];
  pageStart: number | null;
  pageEnd: number | null;
  tier: 'company' | 'industry' | 'global';
  sectionId: string | null;
  structuredBlocks: Array<{ type: string; text: string; structured: Record<string, unknown> }>;
  isSemantic: boolean;
}

/** Evidence entry linking a company Knowledge Object to a supporting SOP. */
export interface KnowledgeEvidence {
  documentId: string;
  documentName: string;
  section?: string[];
  snippet?: string;
}

export type KnowledgeSourceKind =
  | 'onboarding'
  | 'uploaded_document'
  | 'human_created'
  | 'ai_extracted';

export interface KnowledgeObject {
  id: string;
  companyId: string;
  type: string;
  tier: 'company' | 'industry' | 'global';
  status: 'proposed' | 'verified' | 'rejected' | 'superseded';
  label: string;
  payload: Record<string, unknown>;
  sourceKind: KnowledgeSourceKind;
  sourceDocumentId: string | null;
  sourceDocumentName: string;
  sourceChunkId: string | null;
  sourceLocation: string;
  extractionMethod: string;
  modelName: string | null;
  modelProvider: string | null;
  extractedAt: string;
  verifiedBy: string | null;
  verifiedAt: string | null;
  rejectedBy: string | null;
  rejectedAt: string | null;
  supersedesId: string | null;
  version: number;
}

export interface KnowledgeExtractionResult {
  created: number;
  skippedChunks: number;
  status: 'completed' | 'cancelled';
}

export interface KnowledgeOnboardingResult {
  created: number;
}

export interface KnowledgeHistoryEntry {
  id: string;
  knowledgeObjectId: string;
  action: string;
  actorId: string | null;
  label: string;
  status: string;
  sourceKind: KnowledgeSourceKind;
  version: number;
  evidenceSnapshot: unknown[];
  payloadSnapshot: Record<string, unknown>;
  detail: string | null;
  createdAt: string;
}

/** Questionnaire answers persisted with a newly created company. */
export interface CompanyOnboardingProfileInput {
  startOptionId: string;
  documentPathId: string;
  structurePreferenceId?: string;
  documentStructureNotes?: string;
  toneId?: string;
  formalityId?: string;
  personId?: string;
  writingNotes?: string;
  terminologyText?: string;
  preferExistingTerms?: boolean;
  departmentsText?: string;
  rolesText?: string;
  processesText?: string;
  workflowNotes?: string;
  templatePreferenceId?: string;
  layoutNotes?: string;
  formsText?: string;
  businessRulesText?: string;
  relationshipsText?: string;
  bestPracticesText?: string;
  aiAssistLevelId?: string;
  requireHumanVerification?: boolean;
  qualityNotes?: string;
  intendedDocumentNames?: string[];
  intendedTemplateNames?: string[];
}

export interface CompanyOnboardingProfile extends CompanyOnboardingProfileInput {
  companyId: string;
  createdAt: string;
  updatedAt: string;
}

/** Fields accepted when creating or updating a company. */
export interface CompanyInput {
  name: string;
  industryKey: string;
  locationKey: string;
  primaryLanguageKey?: string;
  regulationIds?: string[];
  sopCount?: number;
  creationRequestId?: string;
  onboarding?: CompanyOnboardingProfileInput;
}

/** A company / client profile that backs a Company Knowledge Model. */
export interface Company {
  id: string;
  /** Proper noun — shown as-is in every language. */
  name: string;
  /** Number of SOPs uploaded and analysed for this CKM. */
  sopCount: number;
  /** ISO `YYYY-MM-DD`; formatted per locale by `utils/formatDate`. */
  createdAt: string;
  updatedAt: string;
  /** Key under `companyData.industry`. */
  industryKey: string;
  /** Key under `companyData.location`. */
  locationKey: string;
  /** Key under `companyData.language`. */
  primaryLanguageKey: string;
  /** Keys under `companyData.regulation`, shown as badges on the profile. */
  regulationIds: string[];
  creationRequestId?: string | null;
  onboarding?: CompanyOnboardingProfile | null;
}

/** A single navigation destination in the wide sidebar or the icon rail. */
export interface NavItem {
  id: string;
  /** Key under `nav`. */
  labelKey: string;
  icon: IconName;
  to: string;
}

/** A step in a wizard progress header. */
export interface WizardStep {
  /** Stable step id used for navigation and form validation. */
  id?: string;
  /** Two digit ordinal as printed in the design, e.g. "01". */
  ordinal: string;
  /** Translation key for the step name. */
  labelKey: string;
  /**
   * Render a "•••" gap before this step. Used by steppers that show only the
   * first few steps and the last, as the client onboarding design does.
   */
  truncatedBefore?: boolean;
}

/** A suggested SOP title derived from the client's existing SOP corpus. */
export interface SopTitleSuggestion {
  id: string;
  /** Key under `sop.suggestions`. */
  labelKey: string;
}

/** A reason-for-this-SOP option in the SOP context block. */
export interface SopContextOption {
  id: string;
  /** Key under `sop.contextOptions`. */
  labelKey: string;
}

/** Read-only Company Knowledge Model summary shown next to the client picker. */
export interface CkmStatus {
  companyId: string;
  sopsAnalysed: number;
  rolesIdentified: number;
  processesIdentified: number;
  /** Percentage, rendered as "Reliability: 94 %". */
  reliability: number;
  /**
   * Either a relative key under `sop.ckm.relative` (`today`, `yesterday`) or an
   * ISO `YYYY-MM-DD` date.
   */
  lastUpdated: string;
}

/** A "what do you already have?" choice in the client onboarding wizard. */
export interface OnboardingStartOption {
  id: string;
  icon: IconName;
  /** Keys under `onboarding.start.options.<id>`. */
  titleKey: string;
  descriptionKey: string;
}

/**
 * One row of the AI analysis summary.
 *
 * These figures are **AI output**, not verified company knowledge. They are
 * mock values in this phase; when a backend exists they must stay clearly
 * marked as proposed. See `.claude/skills/ckm-domain`.
 */
export interface AnalysisMetric {
  id: string;
  icon: IconName;
  /** Key under `onboarding.analysis.metrics`. */
  labelKey: string;
  /** Confidence percentage 0–100. */
  value: number;
}

/** Local form state for the client onboarding wizard. */
export interface OnboardingForm {
  startOptionId: string;
  documentPathId: string;
  uploadedDocuments: File[];
  uploadedTemplates: File[];
  companyName: string;
  industryKey: string;
  locationKey: string;
  primaryLanguageKey: string;
  regulationIds: string[];
  structurePreferenceId: string;
  documentStructureNotes: string;
  toneId: string;
  formalityId: string;
  personId: string;
  writingNotes: string;
  terminologyText: string;
  preferExistingTerms: boolean;
  departmentsText: string;
  rolesText: string;
  processesText: string;
  workflowNotes: string;
  templatePreferenceId: string;
  layoutNotes: string;
  formsText: string;
  businessRulesText: string;
  relationshipsText: string;
  bestPracticesText: string;
  aiAssistLevelId: string;
  requireHumanVerification: boolean;
  qualityNotes: string;
}

/** Local form state for step 01 of the wizard. */
export interface ProjectInitializationForm {
  title: string;
  companyId: string;
  contextOptionIds: string[];
  additionalContext: string;
}
