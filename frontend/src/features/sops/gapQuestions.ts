import type { BlueprintGap, BlueprintSection } from '../../types';

export interface GapQuestion {
  key: string;
  sectionKey: string;
  sectionHeading: string;
  field: string;
  severity: BlueprintGap['severity'];
  reason: string;
  questionKey: string;
  questionParams?: Record<string, string>;
}

const FIELD_QUESTION_KEYS: Record<string, string> = {
  training_record_retention_period: 'sop.gaps.questions.retention',
  training_or_retraining_frequency: 'sop.gaps.questions.frequency',
  unverified_source_evidence: 'sop.gaps.questions.unverifiedEvidence',
};

const FIELD_NEED_KEYS: Record<string, string> = {
  training_record_retention_period: 'sop.gaps.needs.retention',
  training_or_retraining_frequency: 'sop.gaps.needs.frequency',
  unverified_source_evidence: 'sop.gaps.needs.unverifiedEvidence',
};

/** Short plain-language label for a required gap in the “Needs information” list. */
export function gapNeedLabelKey(gap: BlueprintGap): string {
  return FIELD_NEED_KEYS[gap.field] ?? 'sop.gaps.needs.generic';
}

/** Build plain-language questions for required blueprint gaps. */
export function requiredGapQuestions(sections: BlueprintSection[]): GapQuestion[] {
  const questions: GapQuestion[] = [];
  for (const section of sections) {
    for (const gap of section.gaps) {
      if (gap.severity !== 'required') continue;
      const key = `${section.sectionKey}:${gap.field}`;
      const known = FIELD_QUESTION_KEYS[gap.field];
      questions.push({
        key,
        sectionKey: section.sectionKey,
        sectionHeading: section.heading,
        field: gap.field,
        severity: gap.severity,
        reason: gap.reason,
        questionKey: known ?? 'sop.gaps.questions.generic',
        questionParams: known ? undefined : { heading: section.heading },
      });
    }
  }
  return questions;
}
