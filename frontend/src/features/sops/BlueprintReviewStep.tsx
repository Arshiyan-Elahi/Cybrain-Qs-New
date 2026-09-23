import { useTranslation } from 'react-i18next';
import { Button } from '../../components/common/Button';
import { StatusBadge } from '../../components/common/StatusBadge';
import type { BlueprintSection, SopProject } from '../../types';
import styles from './BlueprintReviewStep.module.css';

interface BlueprintReviewStepProps {
  project: SopProject | null;
  loading: boolean;
  error: string | null;
  onRebuild: () => void;
}

export function BlueprintReviewStep({
  project,
  loading,
  error,
  onRebuild,
}: BlueprintReviewStepProps) {
  const { t } = useTranslation();
  const blueprint = project?.blueprint;

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div>
          <h2 className={styles.title}>{t('sop.blueprint.title')}</h2>
          <p className={styles.subtitle}>{t('sop.blueprint.subtitle')}</p>
        </div>
        <Button variant="outline" size="sm" onClick={onRebuild} disabled={loading || !project}>
          {loading ? t('sop.blueprint.building') : t('sop.blueprint.rebuild')}
        </Button>
      </div>

      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      {loading && !blueprint && <p>{t('common.loading')}</p>}

      {blueprint && (
        <>
          <p>
            {t('sop.blueprint.summary', {
              grounded: blueprint.summary.grounded,
              partial: blueprint.summary.partial,
              blocked: blueprint.summary.blocked,
              gaps: blueprint.summary.gapCount,
              verified: blueprint.summary.verifiedKnowledgeMapped,
            })}
          </p>

          <details className={styles.advanced}>
            <summary>{t('ux.advanced')}</summary>
            <div className={styles.meta}>
              <p>
                <strong>{t('sop.blueprint.structureSource')}:</strong>{' '}
                {t(`sop.blueprint.structure.${blueprint.structureSource}`)}
              </p>
              <p className={styles.note}>{blueprint.structureSourceNote}</p>
              {blueprint.retrievalNotes.map((note) => (
                <p key={note} className={styles.note}>
                  {note}
                </p>
              ))}
            </div>
            {blueprint.generationGuidance.length > 0 && (
              <div className={styles.guidance}>
                <h3>{t('sop.blueprint.guidance')}</h3>
                <ul>
                  {blueprint.generationGuidance.map((item) => (
                    <li key={item.id}>
                      {item.type}: {item.label}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </details>

          <ol className={styles.sections}>
            {blueprint.sections.map((section) => (
              <SectionCard key={section.sectionKey} section={section} />
            ))}
          </ol>
        </>
      )}
    </div>
  );
}

function SectionCard({ section }: { section: BlueprintSection }) {
  const { t } = useTranslation();
  const knowledge = section.evidence.filter((row) => row.kind === 'verified_knowledge');
  const chunks = section.evidence.filter((row) => row.kind === 'source_chunk');

  return (
    <li className={styles.section}>
      <div className={styles.sectionHead}>
        <h3 className={styles.heading}>{section.heading}</h3>
        <StatusBadge>{t(`sop.blueprint.status.${section.generationStatus}`)}</StatusBadge>
      </div>
      <p className={styles.objective}>{section.objective}</p>

      <p className={styles.groupLabel}>{t('sop.blueprint.mappedKnowledge')}</p>
      {knowledge.length === 0 ? (
        <p className={styles.empty}>{t('sop.blueprint.noVerifiedKnowledge')}</p>
      ) : (
        <ul>
          {knowledge.map((row) => (
            <li key={row.id}>
              <strong>{row.label}</strong>
              <details>
                <summary>{t('ux.details')}</summary>
                <span>
                  {row.type}, {row.tier}, {row.status}
                  {row.sourceLocation ? ` — ${row.sourceLocation}` : ''}
                </span>
              </details>
            </li>
          ))}
        </ul>
      )}

      <details>
        <summary>{t('sop.blueprint.sourceEvidence')}</summary>
        {chunks.length === 0 ? (
          <p className={styles.empty}>{t('sop.blueprint.noChunks')}</p>
        ) : (
          <ul>
            {chunks.map((row) => (
              <li key={row.id}>
                {row.sourceDocumentName} — {row.sourceLocation}
                {row.snippet ? `: ${row.snippet}` : ''}
              </li>
            ))}
          </ul>
        )}
      </details>

      {section.regulationIds.length > 0 && (
        <p>
          {t('sop.blueprint.regulations')}: {section.regulationIds.join(', ')}
        </p>
      )}

      <p className={styles.groupLabel}>{t('sop.blueprint.gaps')}</p>
      {section.gaps.length === 0 ? (
        <p className={styles.empty}>{t('sop.blueprint.noGaps')}</p>
      ) : (
        <ul>
          {section.gaps.map((gap) => (
            <li key={`${gap.field}-${gap.reason}`}>
              <StatusBadge>{t(`sop.blueprint.severity.${gap.severity}`)}</StatusBadge>{' '}
              {gap.reason}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
