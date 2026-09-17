import { request } from './apiClient';
import type { Company, CompanyInput, CompanyStats, Page } from '../types';

export function listCompanies(
  search?: string,
  limit = 50,
  offset = 0,
): Promise<Page<Company>> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (search?.trim()) params.set('search', search.trim());
  return request<Page<Company>>(`/companies?${params}`);
}

export function getCompany(id: string): Promise<Company> {
  return request<Company>(`/companies/${id}`);
}

export function createCompany(input: CompanyInput): Promise<Company> {
  return request<Company>('/companies', { method: 'POST', body: input });
}

export function updateCompany(id: string, input: Partial<CompanyInput>): Promise<Company> {
  return request<Company>(`/companies/${id}`, { method: 'PATCH', body: input });
}

export function deleteCompany(id: string): Promise<void> {
  return request<void>(`/companies/${id}`, { method: 'DELETE' });
}

export function getCompanyStats(id: string): Promise<CompanyStats> {
  return request<CompanyStats>(`/companies/${id}/stats`);
}
