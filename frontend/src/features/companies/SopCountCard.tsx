import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/common/Button';
import { Icon } from '../../components/common/Icon';
import { getCompanyStats } from '../../services/companies';
import {
  deleteDocument,
  cancelDocumentOperation,
  getDocumentOperation,
  getDocument,
  listDocumentChunks,
  listDocuments,
  uploadDocument,
} from '../../services/documents';
import {
  confirmKnowledgeObject,
  cancelKnowledgeExtraction,
  editKnowledgeObject,
  extractKnowledgeObjects,
  listAllKnowledgeObjects,
  rejectKnowledgeObject,
} from '../../services/knowledge';
import { ApiError } from '../../services/apiClient';
import type {
  CompanyStats,
  DocumentChunk,
  DocumentDetail,
  KnowledgeObject,
} from '../../types';
import {
  PREVIEW_ITEM_LIMIT,
  TERMINOLOGY_SEARCH_MIN,
  KNOWLEDGE_TYPE_SECTIONS,
  SOP_TYPE_SECTIONS,
  buildStructureTree,
  evidenceSources,
  groupBySectionTypes,
  headingPathsFromPayload,
  knowledgeDetails,
  objectMatchesDocument,
  verifiedDependencyCount,
  type StructureNode,
} from './knowledgeGrouping';
import styles from './SopCountCard.module.css';

interface SopCountCardProps {
  companyId: string;
  onChanged?: () => void;
}

type UploadState = 'uploading' | 'extracting' | 'structuring' | 'processing' | 'embedding' | 'finalizing' | 'completed' | 'cancelling' | 'cancelled' | 'processed' | 'failed' | 'needs_ocr';
type KnowledgeViewMode = 'byType' | 'bySop';

interface UploadItem {
  key: string;
  filename: string;
  state: UploadState;
  detail?: string;
  progress: number;
  stage: string;
}

interface KnowledgeItemCardProps {
  item: KnowledgeObject;
  busy: string | null;
  onEdit: (item: KnowledgeObject) => void;
  onConfirm: (item: KnowledgeObject) => void;
  onReject: (item: KnowledgeObject) => void;
  showType?: boolean;
}

interface CollapsibleSectionProps {
  title: string;
  count: number;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}

const ACCEPTED = '.pdf,.docx';

function fileKey(file: File): string {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function normalizedSections(chunks: DocumentChunk[]) {
  const sections = new Map<string, { path: string[]; chunks: DocumentChunk[] }>();
  for (const chunk of chunks) {
    const key = chunk.sectionId ?? `administrative-${chunk.id}`;
    const section = sections.get(key) ?? { path: chunk.headingPath, chunks: [] };
    section.chunks.push(chunk);
    sections.set(key, section);
  }
  return [...sections.values()];
}

function StructureTreeView({ nodes }: { nodes: StructureNode[] }) {
  if (nodes.length === 0) return null;
  return (
    <ul className={styles.structureTree}>
      {nodes.map((node) => (
        <li key={node.label}>
          <span className={styles.structureLabel}>{node.label}</span>
          {node.children.length > 0 && <StructureTreeView nodes={node.children} />}
        </li>
      ))}
    </ul>
  );
}

function CollapsibleSection({ title, count, open, onToggle, children }: CollapsibleSectionProps) {
  return (
    <section className={styles.knowledgeGroup}>
      <button type="button" className={styles.sectionToggle} aria-expanded={open} onClick={onToggle}>
        <Icon name={open ? 'chevronDown' : 'chevronRight'} size={16} />
        <h4>{title} <span>({count})</span></h4>
      </button>
      {open && children}
    </section>
  );
}

function KnowledgeItemCard({
  item,
  busy,
  onEdit,
  onConfirm,
  onReject,
  showType = false,
}: KnowledgeItemCardProps) {
  const { t } = useTranslation();
  const sources = evidenceSources(item);
  const details = knowledgeDetails(item);
  const structureTree = item.type === 'document_structure'
    ? buildStructureTree(headingPathsFromPayload(item.payload))
    : [];

  return (
    <li className={styles.knowledgeItem}>
      <div className={styles.knowledgeBody}>
        {showType && (
          <span className={styles.knowledgeType}>
            {t(`knowledgeTypes.${item.type}`, { defaultValue: item.type.replaceAll('_', ' ') })}
          </span>
        )}
        <strong className={styles.knowledgeValue}>{item.label}</strong>
        {structureTree.length > 0 && <StructureTreeView nodes={structureTree} />}
        {details.length > 0 && (
          <ul className={styles.knowledgeDetails}>
            {details.map((detail) => <li key={detail}>{detail}</li>)}
          </ul>
        )}
        <div className={styles.knowledgeMeta}>
          <span>{t('companyDetail.sopCount.tier', { value: t(`knowledgeTiers.${item.tier}`) })}</span>
          <span>{t('companyDetail.sopCount.knowledgeStatus', { value: t(`knowledgeStatuses.${item.status}`) })}</span>
          {sources.length > 1 ? (
            <span>{t('companyDetail.sopCount.sourcesCount', { count: sources.length })}: {sources.map((source) => source.documentName).join(', ')}</span>
          ) : (
            <span>{t('companyDetail.sopCount.provenance')}: {item.sourceDocumentName} · {item.sourceLocation}</span>
          )}
        </div>
      </div>
      <div className={styles.knowledgeActions}>
        {(item.status === 'proposed' || item.status === 'verified') && (
          <Button variant="neutral" size="xs" disabled={busy !== null} onClick={() => onEdit(item)}>
            {t('companyDetail.sopCount.editKnowledge')}
          </Button>
        )}
        {item.status === 'proposed' && (
          <>
            <Button variant="neutral" size="xs" disabled={busy !== null} onClick={() => onConfirm(item)}>
              {t('companyDetail.sopCount.confirmKnowledge')}
            </Button>
            <Button variant="neutral" size="xs" disabled={busy !== null} onClick={() => onReject(item)}>
              {t('companyDetail.sopCount.rejectKnowledge')}
            </Button>
          </>
        )}
      </div>
    </li>
  );
}

interface TruncatedKnowledgeListProps {
  items: KnowledgeObject[];
  sectionId: string;
  busy: string | null;
  expanded: boolean;
  onExpand: () => void;
  search?: string;
  onSearchChange?: (value: string) => void;
  onEdit: (item: KnowledgeObject) => void;
  onConfirm: (item: KnowledgeObject) => void;
  onReject: (item: KnowledgeObject) => void;
  showType?: boolean;
}

function TruncatedKnowledgeList({
  items,
  sectionId,
  busy,
  expanded,
  onExpand,
  search,
  onSearchChange,
  onEdit,
  onConfirm,
  onReject,
  showType,
}: TruncatedKnowledgeListProps) {
  const { t } = useTranslation();
  const searchable = sectionId === 'terminology' && items.length >= TERMINOLOGY_SEARCH_MIN;
  const query = (search ?? '').trim().toLowerCase();
  const visiblePool = searchable && query
    ? items.filter((item) => item.label.toLowerCase().includes(query) || knowledgeDetails(item).some((detail) => detail.toLowerCase().includes(query)))
    : items;
  const visible = expanded || visiblePool.length <= PREVIEW_ITEM_LIMIT
    ? visiblePool
    : visiblePool.slice(0, PREVIEW_ITEM_LIMIT);
  const hiddenCount = visiblePool.length - visible.length;

  return (
    <div className={styles.sectionBody}>
      {searchable && onSearchChange && (
        <input
          className={styles.terminologySearch}
          type="search"
          value={search ?? ''}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={t('companyDetail.sopCount.searchTerminology')}
          aria-label={t('companyDetail.sopCount.searchTerminology')}
        />
      )}
      {visiblePool.length === 0 ? (
        <p className={styles.description}>{t('companyDetail.sopCount.noSearchMatches')}</p>
      ) : (
        <ul className={styles.knowledgeList}>
          {visible.map((item) => (
            <KnowledgeItemCard
              key={item.id}
              item={item}
              busy={busy}
              onEdit={onEdit}
              onConfirm={onConfirm}
              onReject={onReject}
              showType={showType}
            />
          ))}
        </ul>
      )}
      {hiddenCount > 0 && (
        <Button variant="neutral" size="xs" onClick={onExpand}>
          {t('companyDetail.sopCount.showAll', { count: visiblePool.length })}
        </Button>
      )}
    </div>
  );
}

/** Live document counters, multi-file upload, persisted list and deletion. */
export function SopCountCard({ companyId, onChanged }: SopCountCardProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const inFlight = useRef(new Set<string>());
  const uploadOperations = useRef(new Map<string, { id: string; controller: AbortController }>());
  const knowledgeOperation = useRef<{ id: string; controller: AbortController } | null>(null);

  const [stats, setStats] = useState<CompanyStats | null>(null);
  const [documents, setDocuments] = useState<DocumentDetail[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeObject[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [expandedDocumentId, setExpandedDocumentId] = useState<string | null>(null);
  const [chunks, setChunks] = useState<Record<string, DocumentChunk[]>>({});
  const [chunkError, setChunkError] = useState<string | null>(null);
  const [chunksLoading, setChunksLoading] = useState(false);
  const [knowledgeBusy, setKnowledgeBusy] = useState<string | null>(null);
  const [knowledgeError, setKnowledgeError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ document: DocumentDetail; chunks: DocumentChunk[] } | null>(null);
  const [previewQueue, setPreviewQueue] = useState<Array<{ document: DocumentDetail; chunks: DocumentChunk[] }>>([]);
  const [pendingDelete, setPendingDelete] = useState<DocumentDetail | null>(null);
  const [blockedDelete, setBlockedDelete] = useState<{ document: DocumentDetail; count: number } | null>(null);
  const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [documentFilter, setDocumentFilter] = useState('all');
  const [viewMode, setViewMode] = useState<KnowledgeViewMode>('byType');
  const [openTypeSections, setOpenTypeSections] = useState<Set<string>>(new Set());
  const [openSopIds, setOpenSopIds] = useState<Set<string>>(new Set());
  const [openSopSections, setOpenSopSections] = useState<Set<string>>(new Set());
  const [expandedLists, setExpandedLists] = useState<Set<string>>(new Set());
  const [terminologySearch, setTerminologySearch] = useState<Record<string, string>>({});
  const typeDefaultsApplied = useRef(false);
  const sopDefaultsApplied = useRef(false);

  const filteredKnowledge = useMemo(() => knowledge.filter((item) =>
    (typeFilter === 'all' || item.type === typeFilter) &&
    (statusFilter === 'all' || item.status === statusFilter) &&
    (documentFilter === 'all' || objectMatchesDocument(item, documentFilter))),
  [knowledge, typeFilter, statusFilter, documentFilter]);

  const typeSections = useMemo(
    () => groupBySectionTypes(filteredKnowledge, KNOWLEDGE_TYPE_SECTIONS),
    [filteredKnowledge],
  );

  const sopGroups = useMemo(() => {
    const byDoc = new Map<string, {
      id: string;
      name: string;
      status: string | null;
      embeddingLabel: string | null;
      items: KnowledgeObject[];
    }>();

    for (const document of documents) {
      byDoc.set(document.id, {
        id: document.id,
        name: document.filename,
        status: document.status,
        embeddingLabel: stats?.aiFeaturesEnabled && document.status === 'processed' && document.embeddedChunkCount < document.semanticChunkCount
          ? t('companyDetail.sopCount.embeddingCount', { embedded: document.embeddedChunkCount, chunks: document.semanticChunkCount })
          : null,
        items: [],
      });
    }

    for (const item of filteredKnowledge) {
      for (const source of evidenceSources(item)) {
        const group = byDoc.get(source.documentId) ?? {
          id: source.documentId,
          name: source.documentName,
          status: null,
          embeddingLabel: null,
          items: [],
        };
        if (!group.items.some((entry) => entry.id === item.id)) {
          group.items.push(item);
        }
        byDoc.set(source.documentId, group);
      }
    }

    return [...byDoc.values()]
      .filter((group) => group.items.length > 0)
      .map((group) => ({
        ...group,
        sections: groupBySectionTypes(group.items, SOP_TYPE_SECTIONS),
      }));
  }, [documents, filteredKnowledge, stats?.aiFeaturesEnabled, t]);

  useEffect(() => {
    typeDefaultsApplied.current = false;
    sopDefaultsApplied.current = false;
    setOpenTypeSections(new Set());
    setOpenSopIds(new Set());
    setOpenSopSections(new Set());
    setExpandedLists(new Set());
    setTerminologySearch({});
    setViewMode('byType');
    setTypeFilter('all');
    setStatusFilter('all');
    setDocumentFilter('all');
  }, [companyId]);

  useEffect(() => {
    if (viewMode !== 'byType' || typeDefaultsApplied.current || typeSections.length === 0) return;
    setOpenTypeSections(new Set([typeSections[0].id]));
    typeDefaultsApplied.current = true;
  }, [typeSections, viewMode]);

  useEffect(() => {
    if (viewMode !== 'bySop' || sopDefaultsApplied.current || sopGroups.length === 0) return;
    const firstSop = sopGroups[0];
    const firstSection = firstSop.sections[0];
    setOpenSopIds(new Set([firstSop.id]));
    if (firstSection) setOpenSopSections(new Set([`${firstSop.id}:${firstSection.id}`]));
    sopDefaultsApplied.current = true;
  }, [sopGroups, viewMode]);

  useEffect(() => {
    if (!preview && previewQueue.length > 0) {
      setPreview(previewQueue[0]);
      setPreviewQueue((current) => current.slice(1));
    }
  }, [preview, previewQueue]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [nextStats, page, knowledgeItems] = await Promise.all([
        getCompanyStats(companyId),
        listDocuments(companyId),
        listAllKnowledgeObjects(companyId),
      ]);
      setStats(nextStats);
      setDocuments(
        await Promise.all(page.items.map((item) => getDocument(companyId, item.id))),
      );
      setKnowledge(knowledgeItems);
    } catch (caught) {
      setLoadError(caught instanceof Error ? caught.message : t('common.requestFailed'));
    } finally {
      setLoading(false);
    }
  }, [companyId, t]);

  useEffect(() => {
    setUploads([]);
    void refresh();
  }, [refresh]);

  const updateUpload = (key: string, update: Partial<UploadItem>) => {
    setUploads((current) =>
      current.map((item) => (item.key === key ? { ...item, ...update } : item)),
    );
  };

  const handleFiles = async (selected: FileList) => {
    const unique = Array.from(selected).filter((file, index, all) => {
      const key = fileKey(file);
      return !inFlight.current.has(key) && all.findIndex((entry) => fileKey(entry) === key) === index;
    });
    if (unique.length === 0) return;

    unique.forEach((file) => inFlight.current.add(fileKey(file)));
    setUploads((current) => [
      ...unique.map((file) => ({
        key: fileKey(file),
        filename: file.name,
        state: 'uploading' as const,
        progress: 0,
        stage: 'uploading',
      })),
      ...current.filter((item) => !unique.some((file) => fileKey(file) === item.key)),
    ]);

    await Promise.all(
      unique.map(async (file) => {
        const key = fileKey(file);
        const operation = { id: crypto.randomUUID(), controller: new AbortController() };
        uploadOperations.current.set(key, operation);
        const poll = window.setInterval(async () => {
          try {
            const state = await getDocumentOperation(companyId, operation.id);
            updateUpload(key, { state: state.stage as UploadState, stage: state.stage, progress: state.progress, detail: state.error ?? undefined });
          } catch { /* Operation may not be registered until upload completes. */ }
        }, 500);
        try {
          const document = await uploadDocument(companyId, file, operation.id, operation.controller.signal,
            (progress) => updateUpload(key, { state: 'uploading', stage: 'uploading', progress }));
          updateUpload(key, {
            state: document.status === 'cancelled' ? 'cancelled' : document.status === 'needs_ocr' ? 'needs_ocr' : document.status === 'failed' ? 'failed' : 'processed',
            stage: document.status === 'processed' ? 'completed' : document.status,
            progress: document.status === 'processed' ? 100 : 0,
            detail: document.warnings[0],
          });
          if (document.status === 'processed') {
            const persistedChunks = await listDocumentChunks(companyId, document.id);
            setPreviewQueue((current) => [...current, { document, chunks: persistedChunks }]);
          }
        } catch (caught) {
          updateUpload(key, {
            state: operation.controller.signal.aborted ? 'cancelled' : 'failed',
            stage: operation.controller.signal.aborted ? 'cancelled' : 'failed',
            detail: caught instanceof Error ? caught.message : t('common.requestFailed'),
          });
        } finally {
          window.clearInterval(poll);
          inFlight.current.delete(key);
          uploadOperations.current.delete(key);
        }
      }),
    );

    await refresh();
    onChanged?.();
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleDelete = async (document: DocumentDetail) => {
    const documentId = document.id;
    setDeletingIds((current) => new Set(current).add(documentId));
    setLoadError(null);
    try {
      await deleteDocument(companyId, documentId);
      setPendingDelete(null);
      setBlockedDelete(null);
      setDeleteSuccess(t('companyDetail.sopCount.deleteSuccess', { filename: document.filename }));
      // Immediate UI update, then reconcile from the server.
      setDocuments((current) => current.filter((item) => item.id !== documentId));
      setKnowledge((current) => current.filter((item) => item.sourceDocumentId !== documentId));
      setStats((current) => current ? {
        ...current,
        documentCount: Math.max(0, current.documentCount - 1),
        processedCount: Math.max(0, current.processedCount - (document.status === 'processed' ? 1 : 0)),
        chunkCount: Math.max(0, current.chunkCount - document.chunkCount),
        embeddedChunkCount: Math.max(0, current.embeddedChunkCount - document.embeddedChunkCount),
        totalBytes: Math.max(0, current.totalBytes - document.byteSize),
      } : current);
      setChunks((current) => {
        const next = { ...current };
        delete next[documentId];
        return next;
      });
      if (expandedDocumentId === documentId) setExpandedDocumentId(null);
      if (preview?.document.id === documentId) setPreview(null);
      setPreviewQueue((current) => current.filter((item) => item.document.id !== documentId));
      await refresh();
      onChanged?.();
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        const count = typeof caught.details.verifiedDependencyCount === 'number'
          ? caught.details.verifiedDependencyCount
          : Math.max(1, verifiedDependencyCount(knowledge, documentId));
        setPendingDelete(null);
        setBlockedDelete({ document, count });
        setLoadError(null);
      } else {
        setLoadError(caught instanceof Error ? caught.message : t('common.requestFailed'));
      }
    } finally {
      setDeletingIds((current) => {
        const next = new Set(current);
        next.delete(documentId);
        return next;
      });
    }
  };

  const requestDelete = (document: DocumentDetail) => {
    setLoadError(null);
    setDeleteSuccess(null);
    const count = verifiedDependencyCount(knowledge, document.id);
    if (count > 0) {
      setPendingDelete(null);
      setBlockedDelete({ document, count });
      return;
    }
    setBlockedDelete(null);
    setPendingDelete(document);
  };

  const toggleChunks = async (documentId: string) => {
    if (expandedDocumentId === documentId) {
      setExpandedDocumentId(null);
      return;
    }
    setExpandedDocumentId(documentId);
    setChunkError(null);
    if (chunks[documentId]) return;
    setChunksLoading(true);
    try {
      const items = await listDocumentChunks(companyId, documentId);
      setChunks((current) => ({ ...current, [documentId]: items }));
    } catch (caught) {
      setChunkError(caught instanceof Error ? caught.message : t('common.requestFailed'));
    } finally {
      setChunksLoading(false);
    }
  };

  const uploading = uploads.some((item) => item.state === 'uploading');

  const cancelUpload = async (item: UploadItem) => {
    const operation = uploadOperations.current.get(item.key);
    if (!operation) return;
    updateUpload(item.key, { state: 'cancelling' });
    await cancelDocumentOperation(companyId, operation.id).catch(() => undefined);
    operation.controller.abort();
  };

  const openPreview = async (document: DocumentDetail) => {
    setPreview({ document, chunks: await listDocumentChunks(companyId, document.id) });
  };

  const runKnowledgeAction = async (key: string, action: () => Promise<unknown>) => {
    setKnowledgeBusy(key);
    setKnowledgeError(null);
    try {
      await action();
      await refresh();
    } catch (caught) {
      setKnowledgeError(caught instanceof Error ? caught.message : t('common.requestFailed'));
    } finally {
      setKnowledgeBusy(null);
    }
  };

  const handleEditKnowledge = (item: KnowledgeObject) => {
    const label = window.prompt(t('companyDetail.sopCount.editPrompt'), item.label)?.trim();
    if (label && label !== item.label) {
      void runKnowledgeAction(item.id, () => editKnowledgeObject(companyId, item.id, label));
    }
  };

  const startExtraction = async () => {
    const operation = { id: crypto.randomUUID(), controller: new AbortController() };
    knowledgeOperation.current = operation;
    await runKnowledgeAction('extract', () => extractKnowledgeObjects(companyId, operation.id, operation.controller.signal));
    knowledgeOperation.current = null;
  };

  const cancelExtraction = async () => {
    const operation = knowledgeOperation.current;
    if (!operation) return;
    setKnowledgeBusy('cancelling');
    await cancelKnowledgeExtraction(companyId, operation.id).catch(() => undefined);
    operation.controller.abort();
  };

  const toggleSet = (current: Set<string>, key: string) => {
    const next = new Set(current);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  };

  const listKey = (scope: string, sectionId: string) => `${scope}:${sectionId}`;

  const renderList = (
    items: KnowledgeObject[],
    sectionId: string,
    scope: string,
    showType = false,
  ) => (
    <TruncatedKnowledgeList
      items={items}
      sectionId={sectionId}
      busy={knowledgeBusy}
      expanded={expandedLists.has(listKey(scope, sectionId))}
      onExpand={() => setExpandedLists((current) => new Set(current).add(listKey(scope, sectionId)))}
      search={terminologySearch[listKey(scope, sectionId)] ?? ''}
      onSearchChange={(value) => setTerminologySearch((current) => ({ ...current, [listKey(scope, sectionId)]: value }))}
      onEdit={handleEditKnowledge}
      onConfirm={(item) => void runKnowledgeAction(item.id, () => confirmKnowledgeObject(companyId, item.id))}
      onReject={(item) => void runKnowledgeAction(item.id, () => rejectKnowledgeObject(companyId, item.id))}
      showType={showType}
    />
  );

  return (
    <div className={styles.card}>
      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <div className={styles.sectionHeading}>
            <span className={styles.tileIcon}><Icon name="buildingSolid" size={28} /></span>
            <span>
              <h3 className={styles.title}>{t('companyDetail.sopCount.documents')}</h3>
              <span className={styles.documentCount}>{loading ? '…' : t('companyDetail.sopCount.documentCount', { count: stats?.documentCount ?? 0 })}</span>
            </span>
          </div>
          <Button variant="outline" size="xs" disabled={uploading} onClick={() => inputRef.current?.click()}>
            {uploading ? t('companyDetail.sopCount.uploading') : t('companyDetail.sopCount.uploadDocuments')}
          </Button>
        </div>
        <p className={styles.description}>
          {loadError ?? t('companyDetail.sopCount.description')}
        </p>
        {deleteSuccess && (
          <p className={styles.deleteSuccess} role="status">{deleteSuccess}</p>
        )}

        {uploads.length > 0 && (
          <ul className={styles.statusList} aria-label={t('companyDetail.sopCount.uploadStatus')}>
            {uploads.map((item) => (
              <li key={item.key}>
                <span>{item.filename}</span>
                <span className={['uploading', 'processing', 'embedding', 'cancelling'].includes(item.state) ? styles.runningStatus : undefined}>{t(`companyDetail.sopCount.status.${item.state}`)}</span>
                <span>{item.progress}% · {t(`companyDetail.sopCount.stage.${item.stage}`)}</span>
                <progress className={styles.progress} max="100" value={item.progress}>{item.progress}%</progress>
                {item.detail && <span title={item.detail}>{item.detail}</span>}
                {['uploading', 'processing', 'embedding', 'cancelling'].includes(item.state) && (
                  <Button variant="neutral" size="xs" disabled={item.state === 'cancelling'} onClick={() => void cancelUpload(item)}>{t('companyDetail.sopCount.cancel')}</Button>
                )}
              </li>
            ))}
          </ul>
        )}

        <ul className={styles.documentList} aria-label={t('companyDetail.sopCount.documents')}>
          {documents.map((document) => (
            <li key={document.id}>
              <button
                type="button"
                className={styles.documentName}
                title={document.filename}
                aria-expanded={expandedDocumentId === document.id}
                onClick={() => void toggleChunks(document.id)}
              >
                {document.filename}
              </button>
              <span>{document.status === 'processed'
                ? stats?.aiFeaturesEnabled && document.embeddedChunkCount < document.semanticChunkCount
                  ? `${t('companyDetail.sopCount.embeddingCount', { embedded: document.embeddedChunkCount, chunks: document.semanticChunkCount })} · ${t('companyDetail.sopCount.status.embedding')}`
                  : t('companyDetail.sopCount.status.completed')
                : t(`companyDetail.sopCount.status.${document.status}`)}</span>
              <Button
                variant="neutral"
                size="xs"
                disabled={deletingIds.has(document.id)}
                onClick={() => requestDelete(document)}
              >
                {deletingIds.has(document.id)
                  ? t('companyDetail.sopCount.deleting')
                  : t('companyDetail.sopCount.delete')}
              </Button>
              {document.status === 'processed' && <Button variant="neutral" size="xs" onClick={() => void openPreview(document)}>{t('companyDetail.sopCount.preview')}</Button>}
              {expandedDocumentId === document.id && (
                <ul className={styles.chunkList}>
                  {chunksLoading && <li>{t('common.loading')}</li>}
                  {chunkError && <li role="alert">{chunkError}</li>}
                  {!chunksLoading && !chunkError && (chunks[document.id]?.length ?? 0) === 0 && (
                    <li>{t('companyDetail.sopCount.noChunks')}</li>
                  )}
                  {chunks[document.id]?.map((chunk) => (
                    <li key={chunk.id}>
                      <strong>{chunk.headingPath.join(' › ') || `#${chunk.chunkOrder + 1}`}</strong>
                      <span>{chunk.text}</span>
                      <span>{t('companyDetail.sopCount.tier', { value: chunk.tier })}</span>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>

      </section>

      <section className={styles.section}>
        <div className={styles.sectionHeader}>
          <h3 className={styles.title}>{t('companyDetail.sopCount.knowledgeObjects')}</h3>
          <div className={styles.knowledgeHeaderActions}>
            <Button variant="outline" size="xs" disabled={knowledgeBusy !== null || documents.length === 0}
              onClick={() => void startExtraction()}>
              {knowledgeBusy === 'cancelling' ? t('companyDetail.sopCount.cancelling') : knowledgeBusy === 'extract' ? t('companyDetail.sopCount.extracting') : t('companyDetail.sopCount.extractKnowledge')}
            </Button>
            {knowledgeBusy && <Button variant="neutral" size="xs" disabled={knowledgeBusy === 'cancelling'} onClick={() => void cancelExtraction()}>{t('companyDetail.sopCount.cancel')}</Button>}
          </div>
        </div>
        {knowledgeError && <p className={styles.description} role="alert">{knowledgeError}</p>}
        <p className={styles.knowledgeCounts}>{t('companyDetail.sopCount.knowledgeCounts', {
          proposed: knowledge.filter((item) => item.status === 'proposed').length,
          confirmed: knowledge.filter((item) => item.status === 'verified').length,
          rejected: knowledge.filter((item) => item.status === 'rejected').length,
        })}</p>

        <div className={styles.viewToggle} role="tablist" aria-label={t('companyDetail.sopCount.viewMode')}>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === 'byType'}
            className={viewMode === 'byType' ? styles.viewToggleActive : undefined}
            onClick={() => setViewMode('byType')}
          >
            {t('companyDetail.sopCount.viewByType')}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={viewMode === 'bySop'}
            className={viewMode === 'bySop' ? styles.viewToggleActive : undefined}
            onClick={() => setViewMode('bySop')}
          >
            {t('companyDetail.sopCount.viewBySop')}
          </button>
        </div>

        <div className={styles.knowledgeFilters}>
          <select aria-label={t('companyDetail.sopCount.filterType')} value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
            <option value="all">{t('companyDetail.sopCount.allTypes')}</option>
            {[...new Set(knowledge.map((item) => item.type))].sort().map((type) => (
              <option key={type} value={type}>{t(`knowledgeTypes.${type}`, { defaultValue: type.replaceAll('_', ' ') })}</option>
            ))}
          </select>
          <select aria-label={t('companyDetail.sopCount.filterStatus')} value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="all">{t('companyDetail.sopCount.allStatuses')}</option>
            {['proposed', 'verified', 'rejected'].map((status) => (
              <option key={status} value={status}>{t(`knowledgeStatuses.${status}`)}</option>
            ))}
          </select>
          <select aria-label={t('companyDetail.sopCount.filterDocument')} value={documentFilter} onChange={(event) => setDocumentFilter(event.target.value)}>
            <option value="all">{t('companyDetail.sopCount.allDocuments')}</option>
            {documents.map((document) => (
              <option key={document.id} value={document.id}>{document.filename}</option>
            ))}
          </select>
        </div>

        {knowledge.length === 0 ? (
          <p className={styles.description}>{t('companyDetail.sopCount.noKnowledgeObjects')}</p>
        ) : viewMode === 'byType' ? (
          typeSections.length === 0 ? (
            <p className={styles.description}>{t('companyDetail.sopCount.noFilterMatches')}</p>
          ) : (
            <div className={styles.knowledgeGroups}>
              {typeSections.map((section) => (
                <CollapsibleSection
                  key={section.id}
                  title={t(`companyDetail.sopCount.knowledgeSections.${section.id}`)}
                  count={section.items.length}
                  open={openTypeSections.has(section.id)}
                  onToggle={() => setOpenTypeSections((current) => toggleSet(current, section.id))}
                >
                  {renderList(section.items, section.id, 'type', section.id === 'roles_responsibilities' || section.id === 'workflows_processes')}
                </CollapsibleSection>
              ))}
            </div>
          )
        ) : sopGroups.length === 0 ? (
          <p className={styles.description}>{t('companyDetail.sopCount.noFilterMatches')}</p>
        ) : (
          <div className={styles.knowledgeGroups}>
            {sopGroups.map((group) => {
              const statusLabel = group.embeddingLabel
                ?? (group.status
                  ? group.status === 'processed'
                    ? t('companyDetail.sopCount.status.completed')
                    : t(`companyDetail.sopCount.status.${group.status}`, { defaultValue: group.status })
                  : t('companyDetail.sopCount.status.processed'));
              return (
                <section key={group.id} className={styles.sopGroup}>
                  <button
                    type="button"
                    className={styles.sectionToggle}
                    aria-expanded={openSopIds.has(group.id)}
                    onClick={() => setOpenSopIds((current) => toggleSet(current, group.id))}
                  >
                    <Icon name={openSopIds.has(group.id) ? 'chevronDown' : 'chevronRight'} size={16} />
                    <div className={styles.sopHeading}>
                      <h4>{group.name}</h4>
                      <span className={styles.sopMeta}>
                        {statusLabel} · {t('companyDetail.sopCount.extractedCount', { count: group.items.length })}
                      </span>
                    </div>
                  </button>
                  {openSopIds.has(group.id) && (
                    <div className={styles.sopSections}>
                      {group.sections.map((section) => {
                        const key = `${group.id}:${section.id}`;
                        return (
                          <CollapsibleSection
                            key={key}
                            title={t(`companyDetail.sopCount.knowledgeSections.${section.id}`)}
                            count={section.items.length}
                            open={openSopSections.has(key)}
                            onToggle={() => setOpenSopSections((current) => toggleSet(current, key))}
                          >
                            {section.id === 'document_structure'
                              ? section.items.map((item) => (
                                <div key={item.id} className={styles.structureBlock}>
                                  <StructureTreeView nodes={buildStructureTree(headingPathsFromPayload(item.payload))} />
                                  <div className={styles.knowledgeMeta}>
                                    <span>{t('companyDetail.sopCount.knowledgeStatus', { value: t(`knowledgeStatuses.${item.status}`) })}</span>
                                  </div>
                                  <div className={styles.knowledgeActions}>
                                    {(item.status === 'proposed' || item.status === 'verified') && (
                                      <Button variant="neutral" size="xs" disabled={knowledgeBusy !== null} onClick={() => handleEditKnowledge(item)}>
                                        {t('companyDetail.sopCount.editKnowledge')}
                                      </Button>
                                    )}
                                    {item.status === 'proposed' && (
                                      <>
                                        <Button variant="neutral" size="xs" disabled={knowledgeBusy !== null} onClick={() => void runKnowledgeAction(item.id, () => confirmKnowledgeObject(companyId, item.id))}>
                                          {t('companyDetail.sopCount.confirmKnowledge')}
                                        </Button>
                                        <Button variant="neutral" size="xs" disabled={knowledgeBusy !== null} onClick={() => void runKnowledgeAction(item.id, () => rejectKnowledgeObject(companyId, item.id))}>
                                          {t('companyDetail.sopCount.rejectKnowledge')}
                                        </Button>
                                      </>
                                    )}
                                  </div>
                                </div>
                              ))
                              : renderList(section.items, section.id, group.id, section.id === 'roles_responsibilities' || section.id === 'workflows')}
                          </CollapsibleSection>
                        );
                      })}
                    </div>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </section>

      <input
        ref={inputRef}
        className="visuallyHidden"
        type="file"
        accept={ACCEPTED}
        multiple
        onChange={(event) => {
          if (event.target.files) void handleFiles(event.target.files);
        }}
      />

      {preview && (
        <div className={styles.modalBackdrop} role="presentation" onMouseDown={() => setPreview(null)}>
          <section className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="extraction-preview-title" onMouseDown={(event) => event.stopPropagation()}>
            <header className={styles.modalHeader}>
              <div><h3 id="extraction-preview-title">{t('companyDetail.sopCount.previewSuccess')}</h3><strong>{preview.document.filename}</strong></div>
              <Button variant="neutral" size="xs" onClick={() => setPreview(null)}>{t('companyDetail.sopCount.close')}</Button>
            </header>
            <div className={styles.previewMeta}>{preview.document.sourceFormat.toUpperCase()} · {preview.document.status} · {preview.document.chunkCount} {t('companyDetail.sopCount.sections')} · {preview.document.embeddedChunkCount} {t('companyDetail.sopCount.embeddings')}</div>
            <h4>{t('companyDetail.sopCount.documentStructure')}</h4>
            <StructureTreeView
              nodes={buildStructureTree(
                normalizedSections(preview.chunks)
                  .map((section) => section.path)
                  .filter((path) => path.length > 0),
              )}
            />
            <h4>{t('companyDetail.sopCount.extractedContent')}</h4>
            <div className={styles.previewContent}>{normalizedSections(preview.chunks).map((section) => <details key={section.chunks[0].sectionId ?? section.chunks[0].id}><summary>{section.path.join(' › ') || t('companyDetail.sopCount.administrativeContent')}</summary>{section.chunks.map((chunk) => <div key={chunk.id}><p>{chunk.text}</p><small>{chunk.structuredBlocks.map((block) => block.type).join(', ')} · {t('companyDetail.sopCount.provenance')}: {preview.document.filename}</small></div>)}</details>)}</div>
          </section>
        </div>
      )}

      {pendingDelete && (
        <div className={styles.modalBackdrop} role="presentation" onMouseDown={() => !deletingIds.has(pendingDelete.id) && setPendingDelete(null)}>
          <section className={styles.confirmModal} role="alertdialog" aria-modal="true" aria-labelledby="delete-sop-title" onMouseDown={(event) => event.stopPropagation()}>
            <h3 id="delete-sop-title">{t('companyDetail.sopCount.deleteTitle')}</h3>
            <p>{pendingDelete.filename}</p>
            <p>{t('companyDetail.sopCount.deleteWarning')}</p>
            {loadError && <p className={styles.deleteError} role="alert">{loadError}</p>}
            <div className={styles.confirmActions}>
              <Button variant="neutral" size="sm" disabled={deletingIds.has(pendingDelete.id)} onClick={() => setPendingDelete(null)}>{t('companyDetail.sopCount.cancel')}</Button>
              <Button size="sm" disabled={deletingIds.has(pendingDelete.id)} onClick={() => void handleDelete(pendingDelete)}>
                {deletingIds.has(pendingDelete.id) ? t('companyDetail.sopCount.deleting') : t('companyDetail.sopCount.deletePermanently')}
              </Button>
            </div>
          </section>
        </div>
      )}

      {blockedDelete && (
        <div className={styles.modalBackdrop} role="presentation" onMouseDown={() => setBlockedDelete(null)}>
          <section className={styles.confirmModal} role="alertdialog" aria-modal="true" aria-labelledby="blocked-delete-title" onMouseDown={(event) => event.stopPropagation()}>
            <h3 id="blocked-delete-title">{t('companyDetail.sopCount.deleteBlockedTitle')}</h3>
            <p>{blockedDelete.document.filename}</p>
            <p>{t('companyDetail.sopCount.deleteBlockedMessage')}</p>
            <p>{t('companyDetail.sopCount.deleteBlockedCount', { count: blockedDelete.count })}</p>
            <div className={styles.confirmActions}>
              <Button size="sm" onClick={() => setBlockedDelete(null)}>{t('companyDetail.sopCount.close')}</Button>
            </div>
          </section>
        </div>
      )}

    </div>
  );
}
