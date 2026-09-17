import { request } from './apiClient';
import type { AuthUser, TokenResponse } from '../types';

export function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: { email, password },
  });
}

export function register(
  email: string,
  password: string,
  fullName: string,
): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/register', {
    method: 'POST',
    body: { email, password, fullName },
  });
}

export function me(): Promise<AuthUser> {
  return request<AuthUser>('/auth/me');
}
