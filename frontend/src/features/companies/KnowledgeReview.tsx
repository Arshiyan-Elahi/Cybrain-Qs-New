import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/common/Button';
import { Icon } from '../../components/common/Icon';
import { ROUTES } from '../../constants/navigation';
import { listDocuments } from '../../services/documents';
import {
  cancelKnowledgeExtraction,
  confirmKnowledgeObject,
  editKnowledgeObject,
  extractKnowledgeObjects,
  listAllKnowledgeObjects,
  rejectKnowledgeObject,
} from '../../services/knowledge';
import type { KnowledgeObject } from '../../types';
import {
  applyKnowledgeMutation,
  buildStructureTree,
  evidenceSources,
  formatSourceLine,
  groupForReview,
  headingPathsFromPayload,
  knowledgeDetails,
  reviewGroupIdForType,
  type ReviewGroupId,
  type StructureNode,
} from './knowledgeGrouping';
import styles from './KnowledgeReview.module.css';

interface KnowledgeReviewProps {
  companyId: string;
  companyName: string;
}

type StatusFilter = 'proposed' | 'verified' | 'rejected' | 'all';

interface ReviewCardProps {
  item: KnowledgeObject;
  focused: boolean;
  busy: string | null;
  cardRef?: (node: HTMLLIElement | null) => void;
  onEdit: (item: KnowledgeObject) => void;
  onAccept: (item: KnowledgeObject) => void;
  onReject: (item: KnowledgeObject) => void;
}

function statusLabelKey(status: KnowledgeObject['status']): string {
  if (status === 'verified') return 'ux.knowledge.status.ready';
  if (status === 'proposed') return 'ux.knowledge.status.needsReview';
  if (status === 'rejected') return 'ux.knowledge.status.rejected';
  return `knowledgeStatuses.${status}`;
}

function StructureNodeView({ node }: { node: StructureNode }) {
  return (
    <li>
      <span>{node.label}</span>
      {node.children.length > 0 && (
        <ul className={styles.structureTree}>
          {node.children.map((child) => (
            <StructureNodeView key={child.label} node={child} />
          ))}
        </ul>
      )}
    </li>
  );
}

function ReviewCard({
  item,
  focused,
  busy,
  cardRef,
  onEdit,
  onAccept,
  onReject,
}: ReviewCardProps) {
  const { t } = useTranslation();
  const sources = evidenceSources(item);
  const details = knowledgeDetails(item);
  const sourceLine = formatSourceLine(item);
  const structureTree = item.type === 'document_structure'
    ? buildStructureTree(headingPathsFromPayload(item.payload))
    : [];
  const badgeClass = item.status === 'proposed'
    ? styles.badge_proposed
    : item.status === 'verified'
      ? styles.badge_verified
      : item.status === 'rejected'
        ? styles.badge_rejected
        : undefined;

  return (
    <li
      ref={cardRef}
      id={`review-card-${item.id}`}
      className={focused ? `${styles.card} ${styles.cardFocused}` : styles.card}
    >
      <p className={styles.statement}>{item.label}</p>
      {sourceLine && (
        <p className={styles.source}>
          {t('ux.knowledge.source', { value: sourceLine })}
        </p>
      )}
      <span className={[styles.badge, badgeClass].filter(Boolean).join(' ')}>
        {t(statusLabelKey(item.status))}
      </span>

      <div className={styles.cardActions}>
        {item.status === 'proposed' && (
          <Button size="xs" disabled={busy !== null} onClick={() => onAccept(item)}>
            {t('ux.knowledge.actions.accept')}
          </Button>
        )}
        {(item.status === 'proposed' || item.status === 'verified') && (
          <Button variant="neutral" size="xs" disabled={busy !== null} onClick={() => onEdit(item)}>
            {t('ux.knowledge.actions.edit')}
          </Button>
        )}
        {item.status === 'proposed' && (
          <Button variant="neutral" size="xs" disabled={busy !== null} onClick={() => onReject(item)}>
            {t('ux.knowledge.actions.reject')}
          </Button>
        )}
      </div>

      {(sources.length > 0 || details.length > 0 || structureTree.length > 0) && (
        <details className={styles.expand}>
          <summary>{t('ux.knowledge.showSource')}</summary>
          {structureTree.length > 0 && (
            <ul className={styles.structureTree}>
              {structureTree.map((node) => (
                <StructureNodeView key={node.label} node={node} />
              ))}
            </ul>
          )}
          {details.map((detail) => (
            <p key={detail} className={styles.evidenceText}>{detail}</p>
          ))}
          {sources.map((source) => (
            <div key={source.documentId} className={styles.evidenceBlock}>
              <strong>{source.documentName}</strong>
              {source.section && source.section.length > 0 && (
                <span>{source.section.join(' > ')}</span>
              )}
              {source.snippet && <p className={styles.evidenceText}>{source.snippet}</p>}
            </div>
          ))}
        </details>
      )}

      <details className={styles.expand}>
        <summary>{t('ux.knowledge.advancedDetails')}</summary>
        <dl className={styles.advancedList}>
          <div>
            <dt>{t('ux.knowledge.advanced.type')}</dt>
            <dd>{t(`knowledgeTypes.${item.type}`, { defaultValue: item.type.replaceAll('_', ' ') })}</dd>
          </div>
          <div>
            <dt>{t('ux.knowledge.advanced.tier')}</dt>
            <dd>{t(`knowledgeTiers.${item.tier}`)}</dd>
          </div>
          <div>
            <dt>{t('ux.knowledge.advanced.version')}</dt>
            <dd>{item.version}</dd>
          </div>
          {item.verifiedAt && (
            <div>
              <dt>{t('ux.knowledge.advanced.acceptedAt')}</dt>
              <dd>{item.verifiedAt}</dd>
            </div>
          )}
          {item.rejectedAt && (
            <div>
              <dt>{t('ux.knowledge.advanced.rejectedAt')}</dt>
              <dd>{item.rejectedAt}</dd>
            </div>
          )}
          <div>
            <dt>{t('ux.knowledge.advanced.origin')}</dt>
            <dd>{t(`knowledgeSourceKinds.${item.sourceKind}`)}</dd>
          </div>
          {item.sourceLocation && (
            <div>
              <dt>{t('ux.knowledge.advanced.location')}</dt>
              <dd>{item.sourceLocation}</dd>
            </div>
          )}
        </dl>
      </details>
    </li>
  );
}

/** Guided company-knowledge review for non-technical QA users. */
export function KnowledgeReview({ companyId, companyName }: KnowledgeReviewProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const knowledgeOperation = useRef<{ id: string; controller: AbortController } | null>(null);
  const cardRefs = useRef(new Map<string, HTMLLIElement>());

  const [items, setItems] = useState<KnowledgeObject[]>([]);
  const [documentCount, setDocumentCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('proposed');
  const [focusIndex, setFocusIndex] = useState(0);
  const [acceptAllOpen, setAcceptAllOpen] = useState(false);
  const [openGroups, setOpenGroups] = useState<Set<ReviewGroupId>>(new Set());
  const groupsDefaulted = useRef(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [knowledge, documents] = await Promise.all([
        listAllKnowledgeObjects(companyId, { includeSuperseded: true }),
        listDocuments(companyId),
      ]);
      setItems(knowledge);
      setDocumentCount(documents.total);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t('common.requestFailed'));
    } finally {
      setLoading(false);
    }
  }, [companyId, t]);

  useEffect(() => {
    groupsDefaulted.current = false;
    setFocusIndex(0);
    void refresh();
  }, [refresh]);

  const initialFilterApplied = useRef(false);
  useEffect(() => {
    initialFilterApplied.current = false;
  }, [companyId]);

  const active = useMemo(
    () => items.filter((item) => item.status !== 'superseded'),
    [items],
  );

  const counts = useMemo(() => ({
    ready: active.filter((item) => item.status === 'verified').length,
    needsReview: active.filter((item) => item.status === 'proposed').length,
    rejected: active.filter((item) => item.status === 'rejected').length,
  }), [active]);

  useEffect(() => {
    if (loading || initialFilterApplied.current) return;
    initialFilterApplied.current = true;
    if (counts.needsReview > 0) setStatusFilter('proposed');
    else if (counts.ready > 0) setStatusFilter('verified');
    else if (counts.rejected > 0) setStatusFilter('rejected');
    else setStatusFilter('all');
    groupsDefaulted.current = false;
  }, [loading, counts.needsReview, counts.ready, counts.rejected]);

  const reviewedCount = counts.ready + counts.rejected;
  const totalCount = active.length;

  const visible = useMemo(() => {
    if (statusFilter === 'all') return active;
    return active.filter((item) => item.status === statusFilter);
  }, [active, statusFilter]);

  const proposedVisible = useMemo(
    () => visible.filter((item) => item.status === 'proposed'),
    [visible],
  );

  const groups = useMemo(() => groupForReview(visible), [visible]);

  useEffect(() => {
    if (groupsDefaulted.current || groups.length === 0) return;
    setOpenGroups(new Set([groups[0].id]));
    groupsDefaulted.current = true;
  }, [groups]);

  useEffect(() => {
    setFocusIndex((current) => {
      if (proposedVisible.length === 0) return 0;
      return Math.min(current, proposedVisible.length - 1);
    });
  }, [proposedVisible]);

  const focusedId = proposedVisible[focusIndex]?.id ?? null;

  useEffect(() => {
    if (!focusedId) return;
    const node = cardRefs.current.get(focusedId);
    node?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [focusedId]);

  const runAction = async (previousId: string, action: () => Promise<KnowledgeObject>) => {
    setBusy(previousId);
    setError(null);
    try {
      const result = await action();
      setItems((current) => applyKnowledgeMutation(current, previousId, result));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t('common.requestFailed'));
    } finally {
      setBusy(null);
    }
  };

  const handleAccept = (item: KnowledgeObject) => {
    void runAction(item.id, () => confirmKnowledgeObject(companyId, item.id));
  };

  const handleReject = (item: KnowledgeObject) => {
    void runAction(item.id, () => rejectKnowledgeObject(companyId, item.id));
  };

  const handleEdit = (item: KnowledgeObject) => {
    const label = window.prompt(t('ux.knowledge.editPrompt'), item.label);
    if (!label || !label.trim() || label.trim() === item.label) return;
    void runAction(item.id, () => editKnowledgeObject(companyId, item.id, label.trim()));
  };

  const handleAcceptAll = async () => {
    const queue = proposedVisible;
    if (queue.length === 0) return;
    setAcceptAllOpen(false);
    setBusy('accept-all');
    setError(null);
    try {
      for (const item of queue) {
        const result = await confirmKnowledgeObject(companyId, item.id);
        setItems((current) => applyKnowledgeMutation(current, item.id, result));
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t('common.requestFailed'));
      await refresh();
    } finally {
      setBusy(null);
    }
  };

  const revealItem = (item: KnowledgeObject | undefined) => {
    if (!item) return;
    const groupId = reviewGroupIdForType(item.type);
    setOpenGroups((current) => new Set(current).add(groupId));
  };

  const goNext = () => {
    if (proposedVisible.length === 0) return;
    const nextIndex = (focusIndex + 1) % proposedVisible.length;
    setFocusIndex(nextIndex);
    revealItem(proposedVisible[nextIndex]);
  };

  const goPrevious = () => {
    if (proposedVisible.length === 0) return;
    const nextIndex = (focusIndex - 1 + proposedVisible.length) % proposedVisible.length;
    setFocusIndex(nextIndex);
    revealItem(proposedVisible[nextIndex]);
  };

  const startExtraction = async () => {
    const operation = { id: crypto.randomUUID(), controller: new AbortController() };
    knowledgeOperation.current = operation;
    setBusy('extract');
    setError(null);
    try {
      await extractKnowledgeObjects(companyId, operation.id, operation.controller.signal);
      await refresh();
    } catch (caught) {
      if (!operation.controller.signal.aborted) {
        setError(caught instanceof Error ? caught.message : t('common.requestFailed'));
      }
    } finally {
      if (knowledgeOperation.current?.id === operation.id) {
        knowledgeOperation.current = null;
      }
      setBusy(null);
    }
  };

  const cancelExtraction = async () => {
    const operation = knowledgeOperation.current;
    if (!operation) return;
    setBusy('cancelling');
    operation.controller.abort();
    try {
      await cancelKnowledgeExtraction(companyId, operation.id);
    } catch {
      // Local abort is enough for the UI; server cancel is best-effort.
    } finally {
      knowledgeOperation.current = null;
      setBusy(null);
    }
  };

  const toggleGroup = (id: ReviewGroupId) => {
    setOpenGroups((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const showCreateCta = counts.ready > 0;

  return (
    <section className={styles.panel} aria-label={t('ux.knowledge.reviewLabel')}>
      <header className={styles.hero}>
        <h2 className={styles.heroTitle}>{t('ux.knowledge.heroTitle')}</h2>
        <p className={styles.heroBody}>{t('ux.knowledge.heroBody')}</p>
      </header>

      {loading && <p className={styles.note}>{t('common.loading')}</p>}
      {error && (
        <p className={styles.error} role="alert">
          {t('common.loadFailed', { message: error })}{' '}
          <button type="button" className={styles.retry} onClick={() => void refresh()}>
            {t('common.retry')}
          </button>
        </p>
      )}

      {!loading && (
        <>
          <div className={styles.summary} role="tablist" aria-label={t('ux.knowledge.summaryLabel')}>
            {([
              ['verified', 'ux.knowledge.status.ready', counts.ready],
              ['proposed', 'ux.knowledge.status.needsReview', counts.needsReview],
              ['rejected', 'ux.knowledge.status.rejected', counts.rejected],
            ] as const).map(([value, labelKey, count]) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={statusFilter === value}
                className={statusFilter === value ? `${styles.summaryChip} ${styles.summaryChipActive}` : styles.summaryChip}
                onClick={() => {
                  setStatusFilter(value);
                  setFocusIndex(0);
                  groupsDefaulted.current = false;
                }}
              >
                <strong>{count}</strong>
                <span>{t(labelKey)}</span>
              </button>
            ))}
            <button
              type="button"
              role="tab"
              aria-selected={statusFilter === 'all'}
              className={statusFilter === 'all' ? `${styles.summaryChip} ${styles.summaryChipActive}` : styles.summaryChip}
              onClick={() => {
                setStatusFilter('all');
                setFocusIndex(0);
                groupsDefaulted.current = false;
              }}
            >
              <strong>{totalCount}</strong>
              <span>{t('ux.knowledge.status.all')}</span>
            </button>
          </div>

          <div className={styles.toolbar}>
            <p className={styles.progress} aria-live="polite">
              {t('ux.knowledge.progress', { reviewed: reviewedCount, total: totalCount })}
            </p>
            <div className={styles.toolbarActions}>
              <Button
                variant="outline"
                size="sm"
                disabled={busy !== null || proposedVisible.length === 0}
                onClick={() => setAcceptAllOpen(true)}
              >
                {t('ux.knowledge.actions.acceptAll')}
              </Button>
              <Button
                variant="neutral"
                size="sm"
                disabled={busy !== null || proposedVisible.length === 0}
                onClick={goPrevious}
                leadingIcon={<Icon name="chevronLeft" size={16} />}
              >
                {t('ux.knowledge.actions.previous')}
              </Button>
              <Button
                variant="neutral"
                size="sm"
                disabled={busy !== null || proposedVisible.length === 0}
                onClick={goNext}
                trailingIcon={<Icon name="chevronRight" size={16} />}
              >
                {t('ux.knowledge.actions.next')}
              </Button>
            </div>
          </div>

          {proposedVisible.length > 0 && (
            <p className={styles.focusHint}>
              {t('ux.knowledge.focusHint', {
                current: focusIndex + 1,
                total: proposedVisible.length,
              })}
            </p>
          )}

          {active.length === 0 ? (
            <div className={styles.empty}>
              <p>{t('ux.knowledge.noItems')}</p>
              {documentCount > 0 && (
                <div className={styles.emptyActions}>
                  <Button
                    size="sm"
                    disabled={busy !== null}
                    onClick={() => void startExtraction()}
                  >
                    {busy === 'extract'
                      ? t('ux.knowledge.finding')
                      : t('ux.knowledge.findInDocuments')}
                  </Button>
                  {busy === 'extract' && (
                    <Button variant="neutral" size="sm" onClick={() => void cancelExtraction()}>
                      {t('companyDetail.sopCount.cancel')}
                    </Button>
                  )}
                </div>
              )}
              {documentCount === 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate(`${ROUTES.companies}?company=${companyId}`)}
                >
                  {t('ux.knowledge.goToDocuments')}
                </Button>
              )}
            </div>
          ) : groups.length === 0 ? (
            <p className={styles.note}>{t('ux.knowledge.noFilterMatches')}</p>
          ) : (
            <div className={styles.groups}>
              {groups.map((group) => (
                <section key={group.id} className={styles.group}>
                  <button
                    type="button"
                    className={styles.groupToggle}
                    aria-expanded={openGroups.has(group.id)}
                    onClick={() => toggleGroup(group.id)}
                  >
                    <Icon name={openGroups.has(group.id) ? 'chevronDown' : 'chevronRight'} size={16} />
                    <h3>
                      {t(`ux.knowledge.groups.${group.id}`)}
                      <span> ({group.items.length})</span>
                    </h3>
                  </button>
                  {openGroups.has(group.id) && (
                    <ul className={styles.cardList}>
                      {group.items.map((item) => (
                        <ReviewCard
                          key={item.id}
                          item={item}
                          focused={item.id === focusedId}
                          busy={busy}
                          cardRef={(node) => {
                            if (node) cardRefs.current.set(item.id, node);
                            else cardRefs.current.delete(item.id);
                          }}
                          onEdit={handleEdit}
                          onAccept={handleAccept}
                          onReject={handleReject}
                        />
                      ))}
                    </ul>
                  )}
                </section>
              ))}
            </div>
          )}

          {showCreateCta && (
            <div className={styles.cta}>
              <div>
                <h3>{t('ux.knowledge.ctaTitle')}</h3>
                <p>{t('ux.knowledge.ctaBody', { count: counts.ready, company: companyName })}</p>
              </div>
              <Button onClick={() => navigate(`${ROUTES.sopCreate}?company=${companyId}`)}>
                {t('ux.knowledge.ctaAction')}
              </Button>
            </div>
          )}

          <details className={styles.pageAdvanced}>
            <summary>{t('ux.advanced')}</summary>
            <p className={styles.note}>{t('ux.knowledge.advancedLead')}</p>
            <div className={styles.emptyActions}>
              <Button
                variant="outline"
                size="sm"
                disabled={busy !== null || documentCount === 0}
                onClick={() => void startExtraction()}
              >
                {busy === 'extract'
                  ? t('ux.knowledge.finding')
                  : t('ux.knowledge.findInDocuments')}
              </Button>
              {busy === 'extract' && (
                <Button variant="neutral" size="sm" onClick={() => void cancelExtraction()}>
                  {t('companyDetail.sopCount.cancel')}
                </Button>
              )}
            </div>
          </details>
        </>
      )}

      {acceptAllOpen && (
        <div
          className={styles.modalBackdrop}
          role="presentation"
          onMouseDown={() => busy === null && setAcceptAllOpen(false)}
        >
          <section
            className={styles.modal}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="accept-all-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <h3 id="accept-all-title">{t('ux.knowledge.acceptAllTitle')}</h3>
            <p>{t('ux.knowledge.acceptAllBody', { count: proposedVisible.length })}</p>
            <div className={styles.modalActions}>
              <Button variant="neutral" size="sm" onClick={() => setAcceptAllOpen(false)}>
                {t('companyDetail.sopCount.cancel')}
              </Button>
              <Button size="sm" onClick={() => void handleAcceptAll()}>
                {t('ux.knowledge.actions.acceptAll')}
              </Button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
