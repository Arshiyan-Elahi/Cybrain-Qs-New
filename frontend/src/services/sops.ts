import { request } from './apiClient';
import type { SopProject } from '../types';

export function createSopProject(
  companyId: string,
  payload: {
    title: string;
    topic: string;
    contextOptionIds?: string[];
    additionalContext?: string;
  },
): Promise<SopProject> {
  return request<SopProject>(`/companies/${companyId}/sop-projects`, {
    method: 'POST',
    body: payload,
  });
}

export function getSopProject(companyId: string, projectId: string): Promise<SopProject> {
  return request<SopProject>(`/companies/${companyId}/sop-projects/${projectId}`);
}

export function buildSopBlueprint(companyId: string, projectId: string): Promise<SopProject> {
  return request<SopProject>(`/companies/${companyId}/sop-projects/${projectId}/blueprint`, {
    method: 'POST',
    body: {},
  });
}

export function markSopGenerationReady(companyId: string, projectId: string): Promise<SopProject> {
  return request<SopProject>(`/companies/${companyId}/sop-projects/${projectId}/ready`, {
    method: 'POST',
  });
}
