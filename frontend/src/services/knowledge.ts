import { request } from './apiClient';
import type { KnowledgeExtractionResult, KnowledgeObject, Page } from '../types';

export function listKnowledgeObjects(
  companyId: string,
  limit = 200,
  offset = 0,
): Promise<Page<KnowledgeObject>> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return request<Page<KnowledgeObject>>(`/companies/${companyId}/knowledge-objects?${params}`);
}

/** Loads every page until the company Knowledge Object set is complete. */
export async function listAllKnowledgeObjects(companyId: string): Promise<KnowledgeObject[]> {
  const items: KnowledgeObject[] = [];
  let offset = 0;
  const limit = 200;
  for (;;) {
    const page = await listKnowledgeObjects(companyId, limit, offset);
    items.push(...page.items);
    offset += page.items.length;
    if (offset >= page.total || page.items.length === 0) break;
  }
  return items;
}

export function extractKnowledgeObjects(companyId: string, operationId: string, signal: AbortSignal): Promise<KnowledgeExtractionResult> {
  return request<KnowledgeExtractionResult>(`/companies/${companyId}/knowledge-objects/extract?operation_id=${operationId}`, { method: 'POST', signal });
}

export function cancelKnowledgeExtraction(companyId: string, operationId: string): Promise<void> {
  return request<void>(`/companies/${companyId}/knowledge-objects/operations/${operationId}/cancel`, { method: 'POST' });
}

export function editKnowledgeObject(companyId: string, objectId: string, label: string): Promise<KnowledgeObject> {
  return request<KnowledgeObject>(`/companies/${companyId}/knowledge-objects/${objectId}`, { method: 'PATCH', body: { label } });
}

export function confirmKnowledgeObject(companyId: string, objectId: string): Promise<KnowledgeObject> {
  return request<KnowledgeObject>(`/companies/${companyId}/knowledge-objects/${objectId}/confirm`, { method: 'POST' });
}

export function rejectKnowledgeObject(companyId: string, objectId: string): Promise<KnowledgeObject> {
  return request<KnowledgeObject>(`/companies/${companyId}/knowledge-objects/${objectId}/reject`, { method: 'POST' });
}
