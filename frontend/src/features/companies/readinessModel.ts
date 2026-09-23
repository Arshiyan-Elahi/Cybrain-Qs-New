import type { CompanyStats, KnowledgeObject } from '../../types';

export type ReadinessStepId = 'setup' | 'documents' | 'review' | 'ready';

export type ReadinessStepState = 'done' | 'current' | 'upcoming' | 'attention';

export interface ReadinessStep {
  id: ReadinessStepId;
  state: ReadinessStepState;
}

export interface CompanyReadinessModel {
  steps: ReadinessStep[];
  /** First step the user still needs to finish. */
  current: ReadinessStepId | 'complete';
  proposed: number;
  verified: number;
  documents: number;
  progress: number;
}

function isComplete(state: ReadinessStepState): boolean {
  return state === 'done' || state === 'attention';
}

/**
 * Plain-language company progress. Does not change how knowledge is stored
 * or how SOPs are generated.
 */
export function deriveCompanyReadiness(
  stats: CompanyStats | null,
  knowledge: KnowledgeObject[],
): CompanyReadinessModel {
  const documents = stats?.documentCount ?? 0;
  const proposed = knowledge.filter((item) => item.status === 'proposed').length;
  const verified = knowledge.filter((item) => item.status === 'verified').length;
  const reviewed = knowledge.filter((item) => item.status !== 'superseded').length;
  const pendingReads = stats
    ? Math.max(
        0,
        stats.documentCount - stats.processedCount - stats.failedCount - stats.needsOcrCount,
      )
    : 0;
  const documentProblems = (stats?.failedCount ?? 0) > 0 || (stats?.needsOcrCount ?? 0) > 0;

  let documentsState: ReadinessStepState = 'current';
  if (documents === 0) documentsState = 'current';
  else if (pendingReads > 0) documentsState = 'current';
  else if (documentProblems) documentsState = 'attention';
  else documentsState = 'done';

  const documentsSettled = isComplete(documentsState) || (documents > 0 && pendingReads === 0);

  let reviewState: ReadinessStepState = 'upcoming';
  if (!documentsSettled || documents === 0) reviewState = 'upcoming';
  else if (proposed > 0 || reviewed === 0) reviewState = 'current';
  else reviewState = 'done';

  let readyState: ReadinessStepState = 'upcoming';
  if (reviewState === 'done' && verified > 0) readyState = 'done';
  else if (reviewState === 'done' && verified === 0) readyState = 'current';
  else if (reviewState === 'current') readyState = 'upcoming';

  const steps: ReadinessStep[] = [
    { id: 'setup', state: 'done' },
    { id: 'documents', state: documentsState },
    { id: 'review', state: reviewState },
    { id: 'ready', state: readyState },
  ];

  const current = steps.find((step) => !isComplete(step.state) && step.state !== 'upcoming')?.id
    ?? (readyState === 'done' ? 'complete' : steps.find((step) => step.state === 'upcoming')?.id ?? 'complete');

  const completed = steps.filter((step) => isComplete(step.state)).length;
  return {
    steps,
    current: current === 'setup' ? 'documents' : current,
    proposed,
    verified,
    documents,
    progress: Math.round((completed / steps.length) * 100),
  };
}
