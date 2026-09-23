import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/common/Button';
import { WIZARD_STEPS } from '../../constants/wizard';
import type { BlueprintSection, SopProject } from '../../types';
import { requiredGapQuestions } from './gapQuestions';
import styles from './SopDraftDocumentStep.module.css';

interface SopDraftDocumentStepProps {
  project: SopProject;
  gapAnswers: Record<string, string>;
  busy: boolean;
  onEdit: () => void;
  onRegenerate: () => void;
  onSaveDraft: () => void;
}

function sectionBody(
  section: BlueprintSection,
  t: (key: string, options?: Record<string, unknown>) => string,
) {
  const knowledge = section.evidence.filter((row) => row.kind === 'verified_knowledge');
  if (section.generationStatus === 'blocked') {
    return (
      <p className={styles.warning} role="status">
        {t('sop.guided.draft.blockedWarning', { heading: section.heading })}
      </p>
    );
  }
  if (knowledge.length === 0) {
    return (
      <p className={styles.warning} role="status">
        {t('sop.guided.draft.missingWarning', { heading: section.heading })}
      </p>
    );
  }
  return (
    <div className={styles.bodyBlock}>
      {knowledge.map((row) => (
        <p key={row.id}>{row.label}</p>
      ))}
      {section.generationStatus === 'partial' && (
        <p className={styles.warning} role="status">
          {t('sop.guided.draft.partialWarning')}
        </p>
      )}
    </div>
  );
}

/** Step 4 — document-like draft view. Blocked sections stay blocked. */
export function SopDraftDocumentStep({
  project,
  gapAnswers,
  busy,
  onEdit,
  onRegenerate,
  onSaveDraft,
}: SopDraftDocumentStepProps) {
  const { t } = useTranslation();
  const step = WIZARD_STEPS[3];
  const blueprint = project.blueprint;
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const questions = useMemo(
    () => (blueprint ? requiredGapQuestions(blueprint.sections) : []),
    [blueprint],
  );

  if (!blueprint) {
    return (
      <div className={styles.panel}>
        <p>{t('sop.guided.draft.noPlan')}</p>
      </div>
    );
  }

  return (
    <div className={sourcesOpen ? styles.layout : styles.layoutSingle}>
      <div className={styles.panel}>
        <div className={styles.stepHead}>
          <h2 className={styles.stepTitle}>
            {step.ordinal}. {t(step.labelKey)}
          </h2>
          <p className={styles.note}>{t('sop.guided.draft.lead')}</p>
        </div>

        <article className={styles.document} aria-label={t('sop.guided.draft.documentLabel')}>
          <header className={styles.docHeader}>
            <p className={styles.docEyebrow}>{t('sop.guided.draft.documentEyebrow')}</p>
            <h1 className={styles.docTitle}>{blueprint.title || project.title}</h1>
          </header>

          {blueprint.sections.map((section, index) => {
            const relatedAnswers = questions
              .filter((question) => question.sectionKey === section.sectionKey)
              .map((question) => ({
                question,
                answer: gapAnswers[question.key]?.trim() ?? '',
              }))
              .filter((entry) => entry.answer.length > 0);

            return (
              <section key={section.sectionKey} className={styles.docSection}>
                <h2>
                  {index + 1}. {section.heading}
                </h2>
                {sectionBody(section, t)}
                {relatedAnswers.map(({ question, answer }) => (
                  <aside key={question.key} className={styles.userNote}>
                    <strong>{t('sop.guided.draft.userNoteLabel')}</strong>
                    <p>{answer}</p>
                    <span>{t('sop.guided.draft.userNoteDisclaimer')}</span>
                  </aside>
                ))}
              </section>
            );
          })}
        </article>

        <div className={styles.actions}>
          <Button variant="outline" size="sm" disabled={busy} onClick={onEdit}>
            {t('sop.guided.draft.edit')}
          </Button>
          <Button variant="neutral" size="sm" disabled={busy} onClick={onRegenerate}>
            {t('sop.guided.draft.regenerate')}
          </Button>
          <Button size="sm" disabled={busy} onClick={onSaveDraft}>
            {busy ? t('sop.guided.draft.saving') : t('sop.guided.draft.save')}
          </Button>
        </div>

        <button
          type="button"
          className={styles.sourcesToggle}
          aria-expanded={sourcesOpen}
          onClick={() => setSourcesOpen((open) => !open)}
        >
          {sourcesOpen ? t('sop.guided.draft.hideSources') : t('sop.guided.draft.viewSources')}
        </button>
      </div>

      {sourcesOpen && (
        <aside className={styles.sources} aria-label={t('sop.guided.draft.sourcesLabel')}>
          <h3>{t('sop.guided.draft.sourcesTitle')}</h3>
          <p className={styles.note}>{t('sop.guided.draft.sourcesLead')}</p>

          {blueprint.sections.map((section) => {
            const knowledge = section.evidence.filter((row) => row.kind === 'verified_knowledge');
            const chunks = section.evidence.filter((row) => row.kind === 'source_chunk');
            return (
              <div key={section.sectionKey} className={styles.sourceSection}>
                <h4>
                  {section.heading}
                  <span> · {t(`sop.blueprint.status.${section.generationStatus}`)}</span>
                </h4>
                <p className={styles.groupLabel}>{t('sop.guided.draft.companyKnowledge')}</p>
                {knowledge.length === 0 ? (
                  <p className={styles.empty}>{t('sop.blueprint.noVerifiedKnowledge')}</p>
                ) : (
                  <ul>
                    {knowledge.map((row) => (
                      <li key={row.id}>
                        {row.label}
                        {row.sourceDocumentName && (
                          <span className={styles.sourceMeta}>
                            {row.sourceDocumentName}
                            {row.sourceLocation ? ` › ${row.sourceLocation}` : ''}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                <p className={styles.groupLabel}>{t('sop.guided.draft.sourceEvidence')}</p>
                {chunks.length === 0 ? (
                  <p className={styles.empty}>{t('sop.blueprint.noChunks')}</p>
                ) : (
                  <ul>
                    {chunks.map((row) => (
                      <li key={row.id}>
                        {row.sourceDocumentName}
                        {row.sourceLocation ? ` › ${row.sourceLocation}` : ''}
                        {row.snippet ? ` — ${row.snippet}` : ''}
                      </li>
                    ))}
                  </ul>
                )}
                {section.regulationIds.length > 0 && (
                  <>
                    <p className={styles.groupLabel}>{t('sop.guided.draft.regulations')}</p>
                    <p>{section.regulationIds.join(', ')}</p>
                  </>
                )}
              </div>
            );
          })}

          <details className={styles.advanced}>
            <summary>{t('ux.advanced')}</summary>
            <p>{t('sop.blueprint.structureSource')}: {t(`sop.blueprint.structure.${blueprint.structureSource}`)}</p>
            <p className={styles.note}>{blueprint.structureSourceNote}</p>
            {blueprint.retrievalNotes.map((note) => (
              <p key={note} className={styles.note}>{note}</p>
            ))}
          </details>
        </aside>
      )}
    </div>
  );
}
