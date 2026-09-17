import { getToken, request } from './apiClient';
import type { DocumentChunk, DocumentDetail, DocumentOperationProgress, DocumentSummary, Page } from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export function listDocuments(companyId: string): Promise<Page<DocumentSummary>> {
  return request<Page<DocumentSummary>>(`/companies/${companyId}/documents`);
}

export function getDocument(companyId: string, documentId: string): Promise<DocumentDetail> {
  return request<DocumentDetail>(`/companies/${companyId}/documents/${documentId}`);
}

export function uploadDocument(
  companyId: string,
  file: File,
  operationId: string,
  signal: AbortSignal,
  onUploadProgress: (percent: number) => void,
  kind: 'general' | 'sop' | 'template' = 'general',
): Promise<DocumentDetail> {
  const formData = new FormData();
  formData.append('file', file);
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const params = new URLSearchParams({
      operation_id: operationId,
      kind,
    });
    xhr.open('POST', `${BASE_URL}/companies/${companyId}/documents?${params}`);
    const token = getToken();
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onUploadProgress(Math.round((event.loaded / event.total) * 40));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
        return;
      }
      let message = `Upload failed (${xhr.status})`;
      try {
        const body = JSON.parse(xhr.responseText || '{}');
        if (typeof body?.error?.message === 'string') message = body.error.message;
        else if (typeof body?.detail === 'string') message = body.detail;
      } catch {
        // Keep status fallback.
      }
      reject(new Error(message));
    };
    xhr.onerror = () => reject(new Error('Upload failed.'));
    xhr.onabort = () => reject(new DOMException('Cancelled', 'AbortError'));
    signal.addEventListener('abort', () => xhr.abort(), { once: true });
    xhr.send(formData);
  });
}

export function cancelDocumentOperation(companyId: string, operationId: string): Promise<void> {
  return request<void>(`/companies/${companyId}/operations/${operationId}/cancel`, { method: 'POST' });
}

export function getDocumentOperation(companyId: string, operationId: string): Promise<DocumentOperationProgress> {
  return request<DocumentOperationProgress>(`/companies/${companyId}/operations/${operationId}`);
}

export function deleteDocument(companyId: string, documentId: string): Promise<void> {
  return request<void>(`/companies/${companyId}/documents/${documentId}`, {
    method: 'DELETE',
  });
}

export function listDocumentChunks(
  companyId: string,
  documentId: string,
): Promise<DocumentChunk[]> {
  return request<DocumentChunk[]>(`/companies/${companyId}/documents/${documentId}/chunks`);
}
