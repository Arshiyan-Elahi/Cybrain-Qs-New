import type { KnowledgeEvidence, KnowledgeObject } from '../../types';

export const PREVIEW_ITEM_LIMIT = 5;
export const TERMINOLOGY_SEARCH_MIN = 8;

/** Display sections for the By Knowledge Type view (canonical company grouping). */
export const KNOWLEDGE_TYPE_SECTIONS = [
  { id: 'terminology', types: ['terminology'] },
  { id: 'roles_responsibilities', types: ['role', 'responsibility'] },
  { id: 'workflows_processes', types: ['workflow', 'process'] },
  { id: 'business_rules', types: ['business_rule'] },
  { id: 'regulations', types: ['regulation'] },
  { id: 'records_forms', types: ['form_or_record'] },
  { id: 'relationships', types: ['relationship'] },
  { id: 'best_practices', types: ['best_practice'] },
  { id: 'document_structure', types: ['document_structure'] },
  { id: 'writing_style', types: ['writing_style'] },
  { id: 'ai_preferences', types: ['ai_preference'] },
] as const;

/** Subsections inside a By SOP accordion (Document Structure first). */
export const SOP_TYPE_SECTIONS = [
  { id: 'document_structure', types: ['document_structure'] },
  { id: 'terminology', types: ['terminology'] },
  { id: 'roles_responsibilities', types: ['role', 'responsibility'] },
  { id: 'workflows', types: ['workflow', 'process'] },
  { id: 'business_rules', types: ['business_rule'] },
  { id: 'regulations', types: ['regulation'] },
  { id: 'records_forms', types: ['form_or_record'] },
  { id: 'relationships', types: ['relationship'] },
  { id: 'writing_style', types: ['writing_style'] },
] as const;

export type KnowledgeTypeSectionId = (typeof KNOWLEDGE_TYPE_SECTIONS)[number]['id'];
export type SopTypeSectionId = (typeof SOP_TYPE_SECTIONS)[number]['id'];

export interface StructureNode {
  label: string;
  children: StructureNode[];
}

export function evidenceSources(item: KnowledgeObject): KnowledgeEvidence[] {
  const raw = item.payload.evidence;
  if (!Array.isArray(raw) || raw.length === 0) {
    if (!item.sourceDocumentId) return [];
    return [{ documentId: item.sourceDocumentId, documentName: item.sourceDocumentName }];
  }
  const seen = new Map<string, KnowledgeEvidence>();
  for (const entry of raw) {
    if (!entry || typeof entry !== 'object') continue;
    const record = entry as Record<string, unknown>;
    const documentId = typeof record.documentId === 'string' ? record.documentId : null;
    if (!documentId || seen.has(documentId)) continue;
    seen.set(documentId, {
      documentId,
      documentName: typeof record.documentName === 'string' ? record.documentName : item.sourceDocumentName,
      section: Array.isArray(record.section) ? record.section.filter((part): part is string => typeof part === 'string') : undefined,
      snippet: typeof record.snippet === 'string' ? record.snippet : undefined,
    });
  }
  if (seen.size === 0) {
    if (!item.sourceDocumentId) return [];
    return [{ documentId: item.sourceDocumentId, documentName: item.sourceDocumentName }];
  }
  return [...seen.values()];
}

export function objectMatchesOrigin(item: KnowledgeObject, origin: string): boolean {
  if (origin === 'onboarding') return item.sourceKind === 'onboarding';
  if (origin === 'document') {
    return item.sourceKind === 'uploaded_document' || item.sourceKind === 'ai_extracted';
  }
  return true;
}

export function objectMatchesDocument(item: KnowledgeObject, documentId: string): boolean {
  return evidenceSources(item).some((source) => source.documentId === documentId);
}

export function verifiedDependencyCount(items: KnowledgeObject[], documentId: string): number {
  return items.filter((item) =>
    (item.status === 'verified' || item.status === 'superseded')
    && objectMatchesDocument(item, documentId)).length;
}

export function headingPathsFromPayload(payload: Record<string, unknown>): string[][] {
  if (!Array.isArray(payload.headingPaths)) return [];
  return payload.headingPaths
    .filter((path): path is unknown[] => Array.isArray(path))
    .map((path) => path.filter((part): part is string => typeof part === 'string' && part.length > 0))
    .filter((path) => path.length > 0);
}

export function buildStructureTree(paths: string[][]): StructureNode[] {
  const root: StructureNode[] = [];
  for (const path of paths) {
    let level = root;
    for (const segment of path) {
      let node = level.find((entry) => entry.label === segment);
      if (!node) {
        node = { label: segment, children: [] };
        level.push(node);
      }
      level = node.children;
    }
  }
  return root;
}

export function knowledgeDetails(item: KnowledgeObject): string[] {
  if (item.type === 'writing_style') {
    const modals = typeof item.payload.modalCounts === 'object' && item.payload.modalCounts
      ? item.payload.modalCounts as Record<string, number>
      : {};
    return [
      `Sentences: ${item.payload.sentenceCount ?? 0}`,
      `Avg words/sentence: ${item.payload.averageWordsPerSentence ?? 0}`,
      ...['must', 'shall', 'should', 'may'].map((word) => `${word[0].toUpperCase()}${word.slice(1)}: ${modals[word] ?? 0}`),
    ];
  }
  if (item.type === 'document_structure') return [];
  for (const key of ['description', 'summary', 'value']) {
    if (typeof item.payload[key] === 'string') return [item.payload[key] as string];
  }
  if (typeof item.payload.count === 'number') return [`Count: ${item.payload.count}`];
  return [];
}

export function groupBySectionTypes(
  items: KnowledgeObject[],
  sections: ReadonlyArray<{ id: string; types: readonly string[] }>,
): Array<{ id: string; items: KnowledgeObject[] }> {
  return sections
    .map((section) => ({
      id: section.id,
      items: items.filter((item) => section.types.includes(item.type)),
    }))
    .filter((section) => section.items.length > 0);
}
